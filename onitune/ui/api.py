"""Funciones de Python que la página puede llamar: `await pywebview.api.nombre(...)`.

pywebview ejecuta cada llamada en un hilo aparte, así que aquí se puede
esperar a yt-dlp sin congelar la ventana. Lo que se devuelve llega a la
página como JSON (dict, list, str, números...).

Ojo: pywebview publica todos los atributos sin "_" de esta clase. Por eso la
app se guarda en `self._app` y las ayudas internas empiezan con "_".
"""

import os
import time
import webbrowser
from dataclasses import asdict, fields
from typing import Optional

import webview

from .. import APP_NAME, APP_VERSION, REPO_URL
from ..core import clipboard, cookies, deps, i18n, paths, proc, ytdlp
from ..core.i18n import t
from ..core.settings import Settings
from . import themes

# Ajustes que la página puede cambiar directamente (el resto tiene su propia función)
EDITABLE = {f.name for f in fields(Settings)} - {"audio_dir", "video_dir", "cookies_file", "max_parallel", "language"}


class Api:
    def __init__(self, app):
        self._app = app

    # ------------------------------------------------------------ arranque

    def init(self) -> dict:
        """La página lo llama al cargar. Devuelve todo lo necesario para dibujarse."""
        app = self._app
        state = {
            "app": {"name": APP_NAME, "version": APP_VERSION, "repo": REPO_URL, "icon": app.icon_data(),
                    "windows": paths.IS_WINDOWS, "debug": bool(os.environ.get("ONITUNE_DEBUG"))},
            "settings": asdict(app.settings),
            # Idioma: los textos ya traducidos, los idiomas que hay y cuál sería el automático
            "lang": i18n.current(),
            "texts": i18n.texts(),
            "languages": i18n.available(),
            "system_lang": i18n.resolve(""),
            "themes": [themes.to_dict(p) for p in themes.THEMES],
            "theme": themes.get(app.settings.theme).id,
            # Navegadores para las cookies: cuáles están instalados y cuáles no se pueden usar
            "browsers": cookies.browsers(),
            "setup": bool(deps.missing()),
            # Lo que falta: con yt-dlp es el primer arranque; si no, una versión nueva que necesita algo más
            "missing": deps.missing(),
        }
        if not state["setup"]:
            app.start_main()
            state.update(
                queue=app.queue_list(),
                history=app.history_list(),
                counts=app.counts(),
                ytdlp=app.ytdlp_status,
                app_update=app.app_update,
            )
        app.bridge.set_ready()
        return state

    def run_setup(self) -> dict:
        """Primer arranque: descarga yt-dlp, ffmpeg y Deno y crea las carpetas.

        También se usa al actualizar desde una versión sin Deno: solo se descarga lo que falta.
        Devuelve la lista de lo descargado, para que la página muestre un resumen
        y espere a que el usuario pulse "Continuar".
        """
        app = self._app
        emit = app.bridge.emit
        downloads = (("yt-dlp", deps.download_ytdlp), ("ffmpeg", deps.download_ffmpeg), ("deno", deps.download_deno))
        if not hasattr(self, "_downloaded"):
            self._downloaded = []  # se conserva si hay que reintentar
        try:
            for name, download in downloads:
                if name not in deps.missing():
                    text = t("setup.verified") if name in self._downloaded else t("setup.already")
                    emit("setup", {"step": name, "state": "done", "text": text}, key=f"setup:{name}")
                    continue
                emit("setup", {"step": name, "state": "running"}, key=f"setup:{name}")

                def progress(fraction, done, total, name=name):
                    text = f"{round(fraction * 100)}%" if fraction is not None else ytdlp.fmt_size(done)
                    emit("setup", {"step": name, "state": "running", "fraction": fraction, "text": text},
                         key=f"setup:{name}")

                download(progress)
                self._downloaded.append(name)
                emit("setup", {"step": name, "state": "done", "text": t("setup.verified")}, key=f"setup:{name}")
            for folder in (app.settings.audio_dir, app.settings.video_dir):
                paths.Path(folder).mkdir(parents=True, exist_ok=True)
            app.settings.save()
            emit("setup", {"step": "folders", "state": "done"}, key="setup:folders")
        except Exception as exc:
            return {"ok": False, "error": t("setup.error", error=exc)}
        time.sleep(0.2)  # que llegue a la página el último paso marcado antes del resumen
        names = {"yt-dlp": "yt-dlp", "ffmpeg": "ffmpeg", "deno": "Deno"}
        return {"ok": True, "downloaded": [names[n] for n in self._downloaded]}

    # ------------------------------------------------------------ ajustes

    def set_setting(self, name: str, value) -> bool:
        if name not in EDITABLE:
            return False
        if name == "cookies_browser" and value not in dict(cookies.BROWSERS):
            return False  # solo navegadores conocidos
        setattr(self._app.settings, name, value)
        self._app.settings.save()
        return True

    def set_language(self, code: str) -> None:
        """Cambia el idioma ("" = automático). Después la página se vuelve a armar."""
        app = self._app
        app.settings.language = code if code in {c for c, _ in i18n.available()} else ""
        app.settings.save()
        i18n.load(app.settings.language)
        app.ytdlp_status["message"] = ""  # estaba en el idioma anterior

    def set_parallel(self, delta: int) -> int:
        app = self._app
        app.queue.set_parallel(app.settings.max_parallel + int(delta))
        return app.settings.max_parallel

    def pick_folder(self, setting: str) -> Optional[str]:
        if setting not in ("audio_dir", "video_dir"):
            return None
        app = self._app
        current = getattr(app.settings, setting)
        result = app.window.create_file_dialog(
            webview.FileDialog.FOLDER, directory=current if os.path.isdir(current) else ""
        )
        if not result:
            return None
        path = result[0] if isinstance(result, (list, tuple)) else result
        setattr(app.settings, setting, path)
        app.settings.save()
        return path

    def pick_cookies(self) -> Optional[str]:
        app = self._app
        result = app.window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=(t("settings.cookies_filter"), t("settings.all_files"))
        )
        if not result:
            return None
        path = result[0] if isinstance(result, (list, tuple)) else result
        app.settings.cookies_file = path
        app.settings.save()
        return path

    def test_cookies(self) -> dict:
        """Botón "Probar" de Ajustes → Cookies: ¿yt-dlp puede usar las cookies elegidas?"""
        return cookies.test(self._app.settings)

    # ------------------------------------------------------------ utilidades

    def get_clipboard(self) -> str:
        return clipboard.get_text()

    def clip_ignore(self, url: str) -> None:
        self._app.clip_ignored.add(url)

    def open_url(self, url: str) -> None:
        # Solo se abren páginas de GitHub (el proyecto y sus Releases)
        if url.startswith("https://github.com/"):
            webbrowser.open(url)

    def describe(self, options: dict) -> str:
        """Texto corto de unas opciones: "MP4 · 1080p · Subt. ES"."""
        try:
            return ytdlp.describe_options(options)
        except (KeyError, AttributeError):
            return ""

    def versions(self) -> dict:
        return deps.versions()

    def update_components(self) -> dict:
        """Botón "Buscar actualizaciones": revisa yt-dlp, Deno y ffmpeg."""
        return self._app.update_components(["ytdlp", "deno", "ffmpeg"])

    # ------------------------------------------------------------ buscar y analizar

    def search(self, query: str) -> dict:
        try:
            results = ytdlp.search(query, self._app.settings)
        except ytdlp.YtdlpError as exc:
            return {"error": str(exc)}
        return {"results": [asdict(r) for r in results]}

    def analyze(self, url: str, kind: str) -> dict:
        """Lee un enlace. Devuelve un video (con sus calidades si kind="video") o una playlist."""
        settings = self._app.settings
        if not ytdlp.is_url(url):
            return {"error": t("video.need_https")}
        url = url.strip()
        try:
            if kind == "video" and not (ytdlp.is_playlist_url(url) and "v=" not in url):
                return {"type": "video", "info": asdict(ytdlp.analyze_video(url, settings))}
            what, info = ytdlp.probe(url, settings)
            if what == "playlist":
                if not info.entries:
                    return {"error": t("playlist.empty")}
                folder = t("nav.audio") if kind == "audio" else t("nav.video")
                if settings.playlist_subfolder:
                    folder += f"/{ytdlp.safe_folder_name(info.title)}"
                note = t("playlist.save_in", folder=folder)
                return {"type": "playlist", "info": asdict(info), "folder_note": note,
                        "music": ytdlp.is_music_url(url)}
            if kind == "video":
                return {"type": "video", "info": asdict(ytdlp.analyze_video(url, settings))}
            return {"type": "video", "info": {**info, "url": url, "music": ytdlp.is_music_url(url)}}
        except ytdlp.YtdlpError as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------ agregar a la cola

    def _audio_options(self, music: bool) -> dict:
        s = self._app.settings
        return {"kind": "audio", "format": s.audio_format, "quality": s.audio_quality,
                "cover": s.audio_cover, "metadata": s.audio_metadata, "music": bool(music)}

    def add(self, kind: str, items: list, options: dict, playlist_title: str = "") -> int:
        """Agrega uno o varios videos ({url, title}) a la cola. Devuelve cuántos."""
        app = self._app
        s = app.settings
        if kind == "audio":
            opts, out_dir = self._audio_options(options.get("music", False)), s.audio_dir
        else:
            opts = {"kind": "video", "res": options.get("res") or None, "container": options.get("container", "mp4"),
                    "subs": bool(options.get("subs")), "music": bool(options.get("music"))}
            if opts["subs"]:
                opts.update(sub_lang=options.get("sub_lang", ""), sub_auto=bool(options.get("sub_auto")),
                            subs_embed=bool(options.get("subs_embed", True)))
            out_dir = s.video_dir
        if playlist_title and s.playlist_subfolder:
            out_dir = os.path.join(out_dir, ytdlp.safe_folder_name(playlist_title))
        # Solo enlaces web: cualquier otra cosa se descarta (ver ytdlp.is_url)
        valid = [i for i in items if isinstance(i, dict) and ytdlp.is_url(i.get("url"))]
        for item in valid:
            app.queue.add(item["url"].strip(), str(item.get("title") or item["url"]), opts, out_dir)
        return len(valid)

    # ------------------------------------------------------------ cola

    def queue_action(self, action: str, item_id: str) -> None:
        q = self._app.queue
        actions = {"pause": q.pause, "resume": q.resume, "retry": q.retry, "cancel": q.cancel}
        if action in actions:
            actions[action](item_id)

    def queue_all(self, action: str) -> None:
        q = self._app.queue
        actions = {"pause": q.pause_all, "resume": q.resume_all, "clear_done": q.clear_done}
        if action in actions:
            actions[action]()

    def open_item(self, where: str, item_id: str, what: str) -> str:
        """Abre el archivo ("file") o su carpeta ("folder"). Devuelve un aviso si falla."""
        if where == "queue":
            item = self._app.queue.find(item_id)
            if not item:
                return ""
            path, folder = item.filepath, item.out_dir
        else:
            entry = next((e for e in self._app.history.entries if e.id == item_id), None)
            if not entry:
                return ""
            path, folder = entry.filepath, os.path.dirname(entry.filepath) if entry.filepath else ""
        if what == "file":
            if path and os.path.exists(path):
                proc.open_path(path)
                return ""
            return t("history.file_gone")
        if path and os.path.exists(path):
            proc.show_in_folder(path)
        elif folder and os.path.isdir(folder):
            proc.open_path(folder)
        else:
            return t("history.folder_gone")
        return ""

    # ------------------------------------------------------------ historial

    def history_again(self, entry_id: str) -> bool:
        app = self._app
        entry = next((e for e in app.history.entries if e.id == entry_id), None)
        if not entry or not ytdlp.is_url(entry.url):
            return False
        folder = os.path.dirname(entry.filepath) if entry.filepath else ""
        if not folder or not os.path.isdir(folder):
            folder = app.settings.audio_dir if entry.kind == "audio" else app.settings.video_dir
        app.queue.add(entry.url, entry.title, entry.options, folder)
        return True

    def history_delete(self, entry_id: str, delete_file: bool) -> None:
        self._app.history.delete(entry_id, delete_file=bool(delete_file))

    def history_clear(self, delete_files: bool) -> int:
        return self._app.history.clear(delete_files=bool(delete_files))
