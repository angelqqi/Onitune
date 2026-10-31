"""Descarga y actualiza yt-dlp y ffmpeg dentro de la carpeta de la app.

Así no hace falta instalar nada en el sistema ni tener permisos de administrador.
"""

import platform
import shutil
import stat
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from . import paths, proc
from .i18n import t

# progress(fraccion 0..1 o None si no se sabe, bytes_descargados, bytes_totales)
ProgressFn = Callable[[Optional[float], int, int], None]

YTDLP_BASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
FFMPEG_BASE = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"


def _is_arm() -> bool:
    return platform.machine().lower() in ("aarch64", "arm64")


def _ytdlp_url() -> str:
    if paths.IS_WINDOWS:
        return YTDLP_BASE + "yt-dlp.exe"
    return YTDLP_BASE + ("yt-dlp_linux_aarch64" if _is_arm() else "yt-dlp_linux")


def _ffmpeg_url() -> str:
    if paths.IS_WINDOWS:
        return FFMPEG_BASE + "ffmpeg-master-latest-win64-gpl.zip"
    return FFMPEG_BASE + (
        "ffmpeg-master-latest-linuxarm64-gpl.tar.xz" if _is_arm() else "ffmpeg-master-latest-linux64-gpl.tar.xz"
    )


# ---------------------------------------------------------------- estado


def ytdlp_ready() -> bool:
    return paths.ytdlp_path().exists()


def ffmpeg_location() -> Optional[str]:
    """Dónde está ffmpeg.

    Devuelve la carpeta de la app si lo descargamos nosotros, "" si está
    instalado en el sistema (yt-dlp lo encuentra solo) o None si no existe.
    """
    if paths.ffmpeg_path().exists():
        return str(paths.bin_dir())
    if shutil.which("ffmpeg"):
        return ""
    return None


def missing() -> list[str]:
    """Lista de componentes que faltan: "yt-dlp" y/o "ffmpeg"."""
    result = []
    if not ytdlp_ready():
        result.append("yt-dlp")
    if ffmpeg_location() is None:
        result.append("ffmpeg")
    return result


# ---------------------------------------------------------------- descarga


def _download(url: str, dest: Path, progress: ProgressFn) -> None:
    """Descarga un archivo mostrando el progreso. Se guarda primero como .part."""
    part = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "Onitune"})
    with urllib.request.urlopen(request, timeout=30) as response, open(part, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            progress(done / total if total else None, done, total)
    part.replace(dest)


def _make_executable(file: Path) -> None:
    if not paths.IS_WINDOWS:
        file.chmod(file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def download_ytdlp(progress: ProgressFn) -> None:
    dest = paths.ytdlp_path()
    _download(_ytdlp_url(), dest, progress)
    _make_executable(dest)


def download_ffmpeg(progress: ProgressFn) -> None:
    """Descarga el paquete de ffmpeg y saca solo ffmpeg y ffprobe."""
    url = _ffmpeg_url()
    archive = paths.bin_dir() / url.rsplit("/", 1)[1]
    _download(url, archive, progress)
    wanted = {"ffmpeg", "ffprobe", "ffmpeg.exe", "ffprobe.exe"}
    try:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                for member in z.namelist():
                    name = member.rsplit("/", 1)[-1]
                    if name in wanted and "/bin/" in member:
                        with z.open(member) as src, open(paths.bin_dir() / name, "wb") as dst:
                            shutil.copyfileobj(src, dst)
        else:
            with tarfile.open(archive) as t:
                for member in t.getmembers():
                    name = member.name.rsplit("/", 1)[-1]
                    if name in wanted and "/bin/" in member.name and member.isfile():
                        src = t.extractfile(member)
                        if src:
                            with src, open(paths.bin_dir() / name, "wb") as dst:
                                shutil.copyfileobj(src, dst)
                            _make_executable(paths.bin_dir() / name)
    finally:
        archive.unlink(missing_ok=True)
    if not paths.ffmpeg_path().exists():
        raise RuntimeError(t("setup.no_ffmpeg"))


# ---------------------------------------------------------------- versiones


def ytdlp_version() -> str:
    if not ytdlp_ready():
        return t("ytdlp.not_installed")
    try:
        return proc.run([str(paths.ytdlp_path()), "--version"], timeout=30).stdout.strip() or t("ytdlp.unknown_version")
    except Exception:
        return t("ytdlp.unknown_version")


def ffmpeg_version() -> str:
    location = ffmpeg_location()
    if location is None:
        return t("ytdlp.not_installed")
    exe = str(paths.ffmpeg_path()) if location else "ffmpeg"
    try:
        first_line = proc.run([exe, "-version"], timeout=30).stdout.splitlines()[0]
        # "ffmpeg version N-12345-g... Copyright ..." -> "N-12345-g..."
        return first_line.split(" ")[2] if first_line.startswith("ffmpeg version") else first_line
    except Exception:
        return t("ytdlp.unknown_version")


def update_ytdlp() -> tuple[bool, str]:
    """Actualiza yt-dlp. Devuelve (todo_bien, mensaje_para_el_usuario)."""
    if not ytdlp_ready():
        return False, t("ytdlp.update_missing")
    try:
        result = proc.run([str(paths.ytdlp_path()), "-U"], timeout=300)
    except Exception as exc:
        return False, t("ytdlp.update_error", error=exc)
    text = (result.stdout + result.stderr).lower()
    if "up to date" in text:
        return True, t("ytdlp.up_to_date")
    if "updated yt-dlp" in text:
        return True, t("ytdlp.updated")
    if result.returncode == 0:
        return True, t("ytdlp.checked")
    last = (result.stderr or result.stdout).strip().splitlines()
    return False, last[-1] if last else t("ytdlp.update_failed")
