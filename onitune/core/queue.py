"""Cola de descargas: varias a la vez, pausar, cancelar, reintentar y guardar al cerrar.

Cada descarga es un proceso de yt-dlp que corre en su propio hilo.
"Pausar" detiene el proceso; al reanudar, yt-dlp continúa donde iba
gracias a los archivos .part que deja en la carpeta temporal.
"""

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from . import paths, proc, ytdlp
from .history import History, HistoryEntry
from .i18n import t
from .notify import notify
from .settings import Settings

# Estados posibles de una descarga
WAITING = "waiting"
DOWNLOADING = "downloading"
PROCESSING = "processing"  # ffmpeg convirtiendo / uniendo
PAUSED = "paused"
ERROR = "error"
DONE = "done"

ACTIVE = (DOWNLOADING, PROCESSING)


@dataclass
class DownloadItem:
    url: str
    title: str
    options: dict
    out_dir: str
    status: str = WAITING
    fraction: Optional[float] = 0.0
    speed: str = ""
    eta: str = ""
    downloaded: float = 0
    total: float = 0
    error: str = ""
    filepath: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # Lo que sigue no se guarda en el archivo
    _process: Optional[subprocess.Popen] = field(default=None, repr=False, compare=False)
    _stop_reason: str = field(default="", repr=False, compare=False)

    SAVED_FIELDS = ("url", "title", "options", "out_dir", "status", "fraction", "error", "filepath", "id", "created")

    @property
    def kind(self) -> str:
        return self.options.get("kind", "audio")

    @property
    def label(self) -> str:
        return ytdlp.describe_options(self.options)

    @property
    def tmp_dir(self) -> str:
        return str(paths.temp_dir() / self.id)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.SAVED_FIELDS}


def _kill_tree(process: subprocess.Popen) -> None:
    """Detiene yt-dlp y también el ffmpeg que haya lanzado."""
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                **proc.hidden_kwargs(),
            )
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except Exception:
        process.kill()


def _fmt_eta(seconds: Optional[float]) -> str:
    if seconds is None:
        return ""
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class DownloadQueue:
    def __init__(self, settings: Settings, history: History):
        self.settings = settings
        self.history = history
        self.items: list[DownloadItem] = []
        self._lock = threading.RLock()
        self._file = paths.data_dir() / "queue.json"
        self._last_notify: dict[str, float] = {}
        self._finished_in_session = 0
        self._closing = False

        # Funciones que la interfaz registra para enterarse de los cambios.
        # Se llaman desde otros hilos: la interfaz debe pasarlas a su propio hilo.
        self.listeners: list[Callable[[Optional[DownloadItem]], None]] = []

        self._load()

    # ------------------------------------------------------------ guardar / cargar

    def _load(self) -> None:
        for d in paths.read_json(self._file, []):
            try:
                item = DownloadItem(**{k: d[k] for k in DownloadItem.SAVED_FIELDS if k in d})
            except (TypeError, AttributeError):
                continue
            if not ytdlp.is_url(item.url):
                continue  # solo enlaces web (ver ytdlp.is_url)
            if item.status in ACTIVE:
                item.status = WAITING  # se cortó al cerrar: sigue cuando haya hueco
            self.items.append(item)

    def save(self) -> None:
        with self._lock:
            data = [item.to_dict() for item in self.items]
        try:
            paths.write_json(self._file, data)
        except OSError:
            pass

    # ------------------------------------------------------------ avisar a la interfaz

    def _changed(self, item: Optional[DownloadItem] = None, throttle: bool = False) -> None:
        if throttle and item is not None:
            now = time.monotonic()
            if now - self._last_notify.get(item.id, 0) < 0.4:
                return
            self._last_notify[item.id] = now
        for listener in list(self.listeners):
            try:
                listener(item)
            except Exception:
                pass

    # ------------------------------------------------------------ consultas

    def find(self, item_id: str) -> Optional[DownloadItem]:
        with self._lock:
            return next((i for i in self.items if i.id == item_id), None)

    def count(self, *statuses: str) -> int:
        with self._lock:
            return sum(1 for i in self.items if i.status in statuses)

    @property
    def pending(self) -> int:
        """Descargas que aún no terminan (para el número de la pestaña Cola)."""
        return self.count(WAITING, DOWNLOADING, PROCESSING, PAUSED, ERROR)

    # ------------------------------------------------------------ acciones

    def start(self) -> None:
        """Arranca las descargas que quedaron pendientes de la última vez."""
        self._pump()

    def add(self, url: str, title: str, options: dict, out_dir: str) -> DownloadItem:
        item = DownloadItem(url=url, title=title, options=dict(options), out_dir=out_dir)
        with self._lock:
            self.items.append(item)
        self.save()
        self._changed()
        self._pump()
        return item

    def pause(self, item_id: str) -> None:
        item = self.find(item_id)
        if not item:
            return
        if item.status in ACTIVE:
            item._stop_reason = "pause"
            if item._process:
                _kill_tree(item._process)
        elif item.status == WAITING:
            item.status = PAUSED
            self.save()
            self._changed(item)

    def resume(self, item_id: str) -> None:
        item = self.find(item_id)
        if item and item.status == PAUSED:
            item.status = WAITING
            self.save()
            self._changed(item)
            self._pump()

    def retry(self, item_id: str) -> None:
        item = self.find(item_id)
        if item and item.status == ERROR:
            item.status, item.error, item.fraction = WAITING, "", 0.0
            self.save()
            self._changed(item)
            self._pump()

    def cancel(self, item_id: str) -> None:
        item = self.find(item_id)
        if not item:
            return
        if item.status in ACTIVE:
            item._stop_reason = "cancel"  # el hilo de la descarga lo quita de la lista
            if item._process:
                _kill_tree(item._process)
            return
        self._remove(item)

    def _remove(self, item: DownloadItem) -> None:
        with self._lock:
            if item in self.items:
                self.items.remove(item)
        shutil.rmtree(item.tmp_dir, ignore_errors=True)
        self.save()
        self._changed()

    def pause_all(self) -> None:
        with self._lock:
            ids = [i.id for i in self.items if i.status in (WAITING, *ACTIVE)]
        for item_id in ids:
            self.pause(item_id)

    def resume_all(self) -> None:
        with self._lock:
            for item in self.items:
                if item.status == PAUSED:
                    item.status = WAITING
        self.save()
        self._changed()
        self._pump()

    def clear_done(self) -> None:
        with self._lock:
            self.items = [i for i in self.items if i.status != DONE]
        self.save()
        self._changed()

    def set_parallel(self, n: int) -> None:
        self.settings.max_parallel = max(1, min(5, n))
        self.settings.save()
        self._pump()

    def shutdown(self) -> None:
        """Al cerrar la app: detiene todo y lo deja guardado para la próxima vez."""
        self._closing = True
        with self._lock:
            running = [i for i in self.items if i.status in ACTIVE]
        for item in running:
            item._stop_reason = "shutdown"
            if item._process:
                _kill_tree(item._process)
        with self._lock:
            for item in running:
                item.status = WAITING
        self.save()

    # ------------------------------------------------------------ motor

    def _pump(self) -> None:
        """Empieza descargas en espera mientras haya huecos libres."""
        if self._closing:
            return
        with self._lock:
            running = sum(1 for i in self.items if i.status in ACTIVE)
            for item in self.items:
                if running >= self.settings.max_parallel:
                    break
                if item.status == WAITING:
                    item.status = DOWNLOADING
                    item.error = ""
                    item._stop_reason = ""
                    running += 1
                    threading.Thread(target=self._run, args=(item,), daemon=True).start()
        self._changed()

    def _run(self, item: DownloadItem) -> None:
        last_error = ""
        popen_kwargs = proc.hidden_kwargs()
        if sys.platform != "win32":
            popen_kwargs["start_new_session"] = True  # para poder detener también a ffmpeg

        try:
            # Si la carpeta no se puede crear (p. ej. un pendrive desconectado), la
            # descarga queda con error en vez de quedarse "Descargando" para siempre
            try:
                os.makedirs(item.out_dir, exist_ok=True)
                os.makedirs(item.tmp_dir, exist_ok=True)
            except OSError:
                raise RuntimeError(t("error.folder", folder=item.out_dir)) from None
            args = ytdlp.download_args(item.url, item.options, item.out_dir, item.tmp_dir, self.settings)
            item._process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **popen_kwargs,
            )
            if item._stop_reason:  # lo pausaron o cancelaron justo al arrancar
                _kill_tree(item._process)
            for raw in item._process.stdout:
                line = raw.strip()
                progress = ytdlp.parse_progress(line)
                if progress:
                    if progress["status"] == "finished":
                        item.status = PROCESSING
                        item.speed = item.eta = ""
                    else:
                        item.status = DOWNLOADING
                        item.fraction = progress["fraction"]
                        item.downloaded = progress["downloaded"]
                        item.total = progress["total"]
                        item.speed = (ytdlp.fmt_size(progress["speed"]) + "/s") if progress["speed"] else ""
                        item.eta = _fmt_eta(progress["eta"])
                    self._changed(item, throttle=progress["status"] != "finished")
                elif line.startswith(ytdlp.TITLE_TAG):
                    item.title = line[len(ytdlp.TITLE_TAG):].strip() or item.title
                    self._changed(item)
                elif line.startswith(ytdlp.FILE_TAG):
                    item.filepath = line[len(ytdlp.FILE_TAG):].strip()
                elif line.startswith("ERROR:"):
                    last_error = line
            item._process.wait()
            code = item._process.returncode
        except Exception as exc:  # no se pudo crear la carpeta o arrancar yt-dlp
            code, last_error = -1, f"ERROR: {exc}"

        item._process = None
        reason = item._stop_reason

        if reason == "cancel":
            self._remove(item)
        elif reason == "shutdown":
            return  # shutdown() ya lo dejó guardado como pendiente
        elif reason == "pause":
            item.status = PAUSED
            item.speed = item.eta = ""
        elif code == 0:
            self._finish(item)
        else:
            item.status = ERROR
            item.error = ytdlp.friendly_error(last_error or t("error.download_failed"))
            item.speed = item.eta = ""

        self.save()
        self._changed(item)
        self._pump()
        self._maybe_queue_done()

    def _finish(self, item: DownloadItem) -> None:
        item.status = DONE
        item.fraction = 1.0
        item.speed = item.eta = ""
        shutil.rmtree(item.tmp_dir, ignore_errors=True)
        size = 0
        if item.filepath and os.path.exists(item.filepath):
            size = os.path.getsize(item.filepath)
        self.history.add(
            HistoryEntry(
                title=item.title,
                url=item.url,
                kind=item.kind,
                options=item.options,
                label=item.label,
                filepath=item.filepath,
                size=size,
            )
        )
        self._finished_in_session += 1
        if self.settings.notify_each:
            notify(t("notify.done"), item.title)

    def _maybe_queue_done(self) -> None:
        if self._closing or self._finished_in_session == 0:
            return
        if self.count(WAITING, *ACTIVE) == 0:
            done = self._finished_in_session
            self._finished_in_session = 0
            if self.settings.notify_queue_done:
                errors = self.count(ERROR)
                text = t("notify.ready", n=done)
                if errors:
                    text = t("notify.ready_errors", ready=text, errors=errors)
                notify(t("notify.all_done"), text)
