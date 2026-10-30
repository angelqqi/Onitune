"""Dónde guarda la app sus archivos, en Windows y en Linux."""

import os
import shutil
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


def _app_dir() -> Path:
    """Carpeta normal de la app: %LOCALAPPDATA%\\Onitune o ~/.local/share/onitune."""
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        folder = base / "Onitune"
        old = base / "YTMP3"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        folder = base / "onitune"
        old = base / "ytmp3"
    # La app antes se llamaba YTMP3: si existe su carpeta, se mueve a la nueva
    # para conservar ajustes, historial, yt-dlp y ffmpeg.
    if old.is_dir() and not folder.exists():
        try:
            shutil.move(str(old), str(folder))
        except OSError:
            pass  # si falla (archivo en uso), se empieza con una carpeta nueva
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def data_dir() -> Path:
    """Carpeta de ajustes, cola, historial y temporales.

    Si existe la variable ONITUNE_DATA_DIR se usa esa carpeta: así las pruebas
    no tocan el historial real. yt-dlp y ffmpeg siguen en la carpeta normal.
    """
    custom = os.environ.get("ONITUNE_DATA_DIR")
    folder = Path(custom) if custom else _app_dir()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def bin_dir() -> Path:
    """Carpeta donde viven yt-dlp y ffmpeg descargados por la app."""
    folder = _app_dir() / "bin"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def temp_dir() -> Path:
    """Carpeta para archivos a medio descargar (uno por descarga)."""
    folder = data_dir() / "tmp"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def ytdlp_path() -> Path:
    return bin_dir() / ("yt-dlp.exe" if IS_WINDOWS else "yt-dlp")


def ffmpeg_path() -> Path:
    return bin_dir() / ("ffmpeg.exe" if IS_WINDOWS else "ffmpeg")


def _first_existing(*candidates: Path) -> Path:
    for c in candidates:
        if c.exists():
            return c
    return candidates[-1]


def default_audio_dir() -> Path:
    music = _first_existing(Path.home() / "Music", Path.home() / "Música", Path.home())
    return music / "Onitune" / "Audio"


def default_video_dir() -> Path:
    videos = _first_existing(Path.home() / "Videos", Path.home() / "Vídeos", Path.home())
    return videos / "Onitune" / "Video"


def assets_dir() -> Path:
    """Carpeta assets/ (funciona también dentro del .exe empaquetado)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "assets"
    return Path(__file__).resolve().parents[2] / "assets"
