"""Ajustes del usuario, guardados en settings.json."""

import json
from dataclasses import asdict, dataclass, fields

from . import paths


@dataclass
class Settings:
    # Carpetas
    audio_dir: str = ""
    video_dir: str = ""
    playlist_subfolder: bool = True

    # Cola
    max_parallel: int = 2

    # Cookies: "none", "browser" o "file"
    cookies_mode: str = "none"
    cookies_browser: str = "firefox"
    cookies_file: str = ""

    # Tema de colores (ver onitune/ui/themes.py)
    theme: str = "dracula"

    # Avisos
    notify_queue_done: bool = True
    notify_each: bool = False
    watch_clipboard: bool = True

    # yt-dlp
    auto_update_ytdlp: bool = True

    # Avisar si hay una versión nueva de Onitune en GitHub (solo avisa, no instala)
    check_app_updates: bool = True

    # Búsqueda de audio: True = buscar canciones en YouTube Music (mejores metadatos)
    music_search: bool = True

    # Recortar la portada en cuadrado: "none", "music" (solo canciones de
    # YouTube Music), "audio", "video" o "both" (audio y video)
    cover_crop: str = "music"

    # Últimas opciones elegidas (para que la app las recuerde)
    audio_format: str = "mp3"
    audio_quality: str = "best"
    audio_cover: bool = True
    audio_metadata: bool = True
    video_container: str = "mp4"
    video_subs: bool = False
    video_subs_embed: bool = True

    def save(self) -> None:
        file = paths.data_dir() / "settings.json"
        file.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        file = paths.data_dir() / "settings.json"
        data = {}
        if file.exists():
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
        # Solo usamos las claves que conocemos (por si el archivo es de otra versión)
        known = {f.name for f in fields(cls)}
        settings = cls(**{k: v for k, v in data.items() if k in known})
        if not settings.audio_dir:
            settings.audio_dir = str(paths.default_audio_dir())
        if not settings.video_dir:
            settings.video_dir = str(paths.default_video_dir())
        return settings
