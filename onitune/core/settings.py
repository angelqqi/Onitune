"""Ajustes del usuario, guardados en settings.json."""

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

    # Idioma: "" = automático (el del sistema, por defecto), o un código: "es", "en", "pt"... (ver core/i18n.py)
    language: str = ""

    # Tema de colores (ver onitune/ui/themes.py)
    theme: str = "dracula"

    # Avisos
    notify_queue_done: bool = True
    notify_each: bool = False
    watch_clipboard: bool = True

    # Actualizar los componentes solos: yt-dlp al abrir la app, Deno y ffmpeg una vez
    # por semana (se mantiene el nombre viejo para no perder lo que eligió el usuario)
    auto_update_ytdlp: bool = True
    last_deps_check: float = 0.0  # cuándo se revisaron Deno y ffmpeg por última vez (segundos)

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
        paths.write_json(paths.data_dir() / "settings.json", asdict(self), indent=2)

    @classmethod
    def load(cls) -> "Settings":
        data = paths.read_json(paths.data_dir() / "settings.json", {})
        if not isinstance(data, dict):
            data = {}
        # Solo usamos las claves que conocemos (por si el archivo es de otra versión)
        known = {f.name for f in fields(cls)}
        settings = cls(**{k: v for k, v in data.items() if k in known})
        if not settings.audio_dir:
            settings.audio_dir = str(paths.default_audio_dir())
        if not settings.video_dir:
            settings.video_dir = str(paths.default_video_dir())
        return settings
