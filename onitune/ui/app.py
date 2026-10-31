"""La ventana de Onitune hecha con pywebview.

Cómo está armada:
- La interfaz es una página web (web/index.html + style.css + app.js) que se
  muestra con el navegador del sistema (Edge WebView2 en Windows).
- La página llama a Python con `pywebview.api.<función>()` (ver api.py).
  Cada llamada corre en su propio hilo, así la ventana nunca se congela.
- Python avisa a la página con `Bridge.emit()`. Los avisos se juntan y se
  mandan en un solo paquete cada 0,1 s: aunque haya 5 descargas avanzando,
  la página recibe pocos mensajes y solo cambia lo que hace falta.
"""

import base64
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import webview

from .. import APP_NAME
from ..core import clipboard, deps, paths, updates, ytdlp
from ..core.history import History, HistoryEntry
from ..core.queue import DOWNLOADING, PROCESSING, DownloadItem, DownloadQueue
from ..core.settings import Settings
from . import themes

WEB_DIR = Path(__file__).resolve().parent / "web"


# ---------------------------------------------------------------- datos para la página


def video_id(url: str) -> str:
    """Saca el id de un enlace de YouTube (para mostrar su miniatura)."""
    for mark in ("v=", "youtu.be/", "/shorts/"):
        if mark in url:
            return url.split(mark, 1)[1].split("&")[0].split("?")[0].split("/")[0][:20]
    return ""


def item_dict(item: DownloadItem) -> dict:
    """Una descarga de la cola, lista para mandarla a la página."""
    return {
        "id": item.id,
        "title": item.title,
        "kind": item.kind,
        "status": item.status,
        "fraction": item.fraction,
        "speed": item.speed,
        "eta": item.eta,
        "label": item.label,
        "error": item.error,
        "file": os.path.basename(item.filepath) if item.filepath else "",
        "vid": video_id(item.url),
    }


def entry_dict(entry: HistoryEntry) -> dict:
    """Una entrada del historial, lista para la página."""
    return {
        "id": entry.id,
        "title": entry.title,
        "kind": entry.kind,
        "label": entry.label,
        "size": ytdlp.fmt_size(entry.size),
        "date": entry.date,
        "exists": entry.file_exists,
        "vid": video_id(entry.url),
    }


class Bridge:
    """Junta los avisos para la página y los manda en paquetes."""

    def __init__(self):
        self.window: Optional[webview.Window] = None
        self.ready = False  # la página ya cargó y pidió los datos
        self.closing = False
        self._pending: dict[str, tuple[str, Any]] = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def emit(self, event: str, data: Any = None, key: Optional[str] = None) -> None:
        """Programa un aviso. Con la misma `key`, el último reemplaza al anterior.

        `data` puede ser una función: se calcula justo antes de enviar (así,
        si llegan 10 cambios seguidos del historial, se arma una sola vez).
        """
        with self._lock:
            self._pending.pop(key or event, None)  # al final, para mantener el orden
            self._pending[key or event] = (event, data)
        self._wake.set()

    def _loop(self) -> None:
        while not self.closing:
            self._wake.wait()
            time.sleep(0.1)  # deja que se junten los avisos que llegan seguidos
            if not self.ready or not self.window:
                continue
            with self._lock:
                batch = list(self._pending.values())
                self._pending.clear()
                self._wake.clear()
            if not batch:
                continue
            events = [[name, data() if callable(data) else data] for name, data in batch]
            try:
                self.window.run_js(f"window.onitune && onitune.receive({json.dumps(events)})")
            except Exception:
                pass  # la ventana se está cerrando


class OnituneApp:
    def __init__(self):
        self.settings = Settings.load()
        self.history = History()
        self.queue: Optional[DownloadQueue] = None
        self.bridge = Bridge()
        self.window: Optional[webview.Window] = None
        self.ytdlp_status = {"ok": True, "message": ""}
        self.app_update: Optional[dict] = None
        self.clip_ignored: set[str] = set()
        self.on_ready: Optional[Callable[["OnituneApp"], None]] = None  # lo usan los scripts de prueba

    # ------------------------------------------------------------ arranque

    def run(self) -> None:
        from .api import Api  # aquí para evitar una importación circular

        palette = themes.get(self.settings.theme)
        self.window = webview.create_window(
            APP_NAME,
            url=str(WEB_DIR / "index.html"),
            js_api=Api(self),
            width=1200,
            height=820,
            min_size=(760, 560),
            background_color=palette.bg,  # sin destello blanco al abrir
        )
        self.bridge.window = self.window
        self.window.events.closing += self._on_closing
        icon = paths.assets_dir() / "icon.ico"
        webview.start(icon=str(icon) if icon.exists() else None, debug=bool(os.environ.get("ONITUNE_DEBUG")))

    def icon_data(self) -> str:
        """El icono como imagen incrustada (la página no tiene acceso a assets/)."""
        icon = paths.assets_dir() / "icon.png"
        if not icon.exists():
            return ""
        return "data:image/png;base64," + base64.b64encode(icon.read_bytes()).decode("ascii")

    def start_main(self) -> None:
        """Arranca la cola y las tareas de fondo (una sola vez, tras el primer arranque)."""
        if self.queue:
            return
        self.queue = DownloadQueue(self.settings, self.history)
        self.queue.listeners.append(self._on_queue_change)
        self.history.listeners.append(self._on_history_change)
        self.queue.start()
        if self.settings.auto_update_ytdlp:
            threading.Thread(target=self._auto_update, daemon=True).start()
        if self.settings.check_app_updates:
            threading.Thread(target=self._check_app_update, daemon=True).start()
        threading.Thread(target=self._watch_clipboard, daemon=True).start()
        if self.on_ready:
            threading.Thread(target=self.on_ready, args=(self,), daemon=True).start()

    # ------------------------------------------------------------ datos

    def queue_list(self) -> list[dict]:
        return [item_dict(i) for i in list(self.queue.items)] if self.queue else []

    def history_list(self) -> list[dict]:
        return [entry_dict(e) for e in list(self.history.entries)]

    def counts(self) -> dict:
        q = self.queue
        if not q:
            return {"pending": 0, "running": 0}
        return {"pending": q.pending, "running": q.count(DOWNLOADING, PROCESSING)}

    # ------------------------------------------------------------ cambios (llegan desde otros hilos)

    def _on_queue_change(self, item: Optional[DownloadItem]) -> None:
        if item is not None and item in self.queue.items:
            self.bridge.emit("item", item_dict(item), key=f"item:{item.id}")  # solo esa tarjeta
        else:
            self.bridge.emit("queue", self.queue_list)  # cambió la lista entera
        self.bridge.emit("counts", self.counts)

    def _on_history_change(self) -> None:
        self.bridge.emit("history", self.history_list)

    # ------------------------------------------------------------ tareas de fondo

    def _auto_update(self) -> None:
        ok, message = deps.update_ytdlp()
        self.ytdlp_status = {"ok": ok, "message": message}
        self.bridge.emit("ytdlp", self.ytdlp_status)

    def _check_app_update(self) -> None:
        found = updates.check()
        if found:
            version, url = found
            self.app_update = {"version": version, "url": url}
            self.bridge.emit("app_update", self.app_update)

    def _watch_clipboard(self) -> None:
        """Cada segundo y medio mira si se copió un enlace de YouTube."""
        last = ""  # un enlace copiado antes de abrir la app también se ofrece
        while not self.bridge.closing:
            time.sleep(1.5)
            if not self.settings.watch_clipboard:
                continue
            text = clipboard.get_text()
            if text == last:
                continue
            last = text
            if ytdlp.is_youtube_url(text) and text not in self.clip_ignored:
                is_list = ytdlp.is_playlist_url(text) and "v=" not in text
                self.bridge.emit("clip", {"url": text, "playlist": is_list})

    # ------------------------------------------------------------ cierre

    def _on_closing(self) -> None:
        """Al cerrar: detener las descargas y guardarlas para la próxima vez."""
        self.bridge.closing = True
        self.bridge._wake.set()
        if self.queue:
            self.queue.shutdown()
        self.settings.save()


def run() -> None:
    OnituneApp().run()
