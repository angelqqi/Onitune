"""Descarga y actualiza yt-dlp, ffmpeg y Deno dentro de la carpeta de la app.

Así no hace falta instalar nada en el sistema ni tener permisos de administrador.
Cada archivo se compara con la huella SHA256 que publica su proyecto: si no
coincide (descarga dañada o modificada), se borra y no se usa.

Deno es un motor de JavaScript. yt-dlp lo necesita para YouTube desde fines
de 2025: sin él faltan formatos y en cualquier momento puede dejar de funcionar.

Actualizaciones: yt-dlp se actualiza solo (yt-dlp -U). Deno se compara con su
última versión en GitHub. ffmpeg se publica de nuevo cada día, así que solo se
renueva cuando el nuestro tiene más de FFMPEG_MAX_AGE_DAYS días (pesa ~100 MB).
"""

import hashlib
import json
import platform
import re
import shutil
import stat
import tarfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from . import paths, proc, updates
from .i18n import t

# progress(fraccion 0..1 o None si no se sabe, bytes_descargados, bytes_totales)
ProgressFn = Callable[[Optional[float], int, int], None]

YTDLP_BASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
FFMPEG_BASE = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"
DENO_BASE = "https://github.com/denoland/deno/releases/latest/download/"
DENO_API = "https://api.github.com/repos/denoland/deno/releases/latest"

UPDATE_EVERY_DAYS = 7  # cada cuánto se revisan Deno y ffmpeg (yt-dlp: en cada arranque)
FFMPEG_MAX_AGE_DAYS = 30  # ffmpeg se renueva si el nuestro es más viejo que esto

_update_lock = threading.Lock()  # una sola actualización a la vez (la automática o la del botón)


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


def _deno_url() -> str:
    if paths.IS_WINDOWS:
        return DENO_BASE + "deno-x86_64-pc-windows-msvc.zip"
    return DENO_BASE + ("deno-aarch64-unknown-linux-gnu.zip" if _is_arm() else "deno-x86_64-unknown-linux-gnu.zip")


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


def deno_location() -> Optional[str]:
    """Dónde está Deno: la ruta del nuestro, "" si está en el sistema o None si no existe."""
    if paths.deno_path().exists():
        return str(paths.deno_path())
    if shutil.which("deno"):
        return ""
    return None


def js_runtime_args() -> list[str]:
    """Le dice a yt-dlp dónde está nuestro Deno (el del sistema lo encuentra solo)."""
    location = deno_location()
    return ["--js-runtimes", f"deno:{location}"] if location else []


def missing() -> list[str]:
    """Lista de componentes que faltan: "yt-dlp", "ffmpeg" y/o "deno"."""
    result = []
    if not ytdlp_ready():
        result.append("yt-dlp")
    if ffmpeg_location() is None:
        result.append("ffmpeg")
    if deno_location() is None:
        result.append("deno")
    return result


# ---------------------------------------------------------------- descarga


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "Onitune"})
    return urllib.request.urlopen(request, timeout=30)


def _expected_sha256(sums_url: str, filename: str) -> str:
    """Huella SHA256 que publica el proyecto para `filename`.

    Sirve para las listas con una línea por archivo ("huella  nombre") y para
    los archivos con una sola huella (Deno en Windows usa otro formato).
    """
    with _open(sums_url) as response:
        text = response.read().decode("utf-8", "replace")
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == filename and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
    found = re.findall(r"\b[0-9a-fA-F]{64}\b", text)
    if len(found) == 1:
        return found[0].lower()
    raise RuntimeError(t("setup.no_hash", name=filename))


def _download(url: str, dest: Path, progress: ProgressFn, sha256: str) -> None:
    """Descarga un archivo mostrando el progreso y comprueba su huella SHA256.

    Se guarda primero como .part y solo pasa a su nombre final si la huella coincide.
    """
    part = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    try:
        with _open(url) as response, open(part, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                progress(done / total if total else None, done, total)
        if digest.hexdigest() != sha256:
            raise RuntimeError(t("setup.bad_hash", name=dest.name))
        part.replace(dest)
    finally:
        part.unlink(missing_ok=True)  # si falló, no queda basura


def _make_executable(file: Path) -> None:
    if not paths.IS_WINDOWS:
        file.chmod(file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _install(new: Path, dest: Path) -> None:
    """Pone el archivo `new` en lugar de `dest`.

    En Windows no se puede reemplazar un programa abierto (por ejemplo ffmpeg en
    medio de una conversión), pero sí cambiarle el nombre: el viejo queda como
    .old, el que está trabajando sigue sin problemas y se borra la próxima vez.
    """
    try:
        new.replace(dest)
    except PermissionError:
        old = dest.with_name(dest.name + ".old")
        old.unlink(missing_ok=True)
        dest.replace(old)
        new.replace(dest)
    _make_executable(dest)


def _clean_old() -> None:
    """Borra los programas viejos que quedaron como .old (si ya nadie los usa)."""
    for file in paths.bin_dir().glob("*.old"):
        try:
            file.unlink()
        except OSError:
            pass  # sigue abierto: se intenta la próxima vez


def download_ytdlp(progress: ProgressFn) -> None:
    url = _ytdlp_url()
    name = url.rsplit("/", 1)[1]  # "yt-dlp.exe", "yt-dlp_linux"...
    dest = paths.ytdlp_path()
    _download(url, dest, progress, _expected_sha256(YTDLP_BASE + "SHA2-256SUMS", name))
    _make_executable(dest)


def download_ffmpeg(progress: ProgressFn) -> None:
    """Descarga el paquete de ffmpeg y saca solo ffmpeg y ffprobe."""
    url = _ffmpeg_url()
    archive = paths.bin_dir() / url.rsplit("/", 1)[1]
    _download(url, archive, progress, _expected_sha256(FFMPEG_BASE + "checksums.sha256", archive.name))
    wanted = {"ffmpeg", "ffprobe", "ffmpeg.exe", "ffprobe.exe"}
    extracted: list[str] = []  # se sacan como .new y se instalan al final

    def save(name: str, src) -> None:
        with src, open(paths.bin_dir() / (name + ".new"), "wb") as dst:
            shutil.copyfileobj(src, dst)
        extracted.append(name)

    try:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                for member in z.namelist():
                    name = member.rsplit("/", 1)[-1]
                    if name in wanted and "/bin/" in member:
                        save(name, z.open(member))
        else:
            with tarfile.open(archive) as tar:
                for member in tar.getmembers():
                    name = member.name.rsplit("/", 1)[-1]
                    if name in wanted and "/bin/" in member.name and member.isfile():
                        src = tar.extractfile(member)
                        if src:
                            save(name, src)
        if paths.ffmpeg_path().name not in extracted:
            raise RuntimeError(t("setup.no_ffmpeg"))
        for name in extracted:
            _install(paths.bin_dir() / (name + ".new"), paths.bin_dir() / name)
    finally:
        archive.unlink(missing_ok=True)
        for name in wanted:
            (paths.bin_dir() / (name + ".new")).unlink(missing_ok=True)


def download_deno(progress: ProgressFn) -> None:
    """Descarga el .zip de Deno y saca solo el programa (deno.exe o deno)."""
    url = _deno_url()
    archive = paths.bin_dir() / url.rsplit("/", 1)[1]
    _download(url, archive, progress, _expected_sha256(url + ".sha256sum", archive.name))
    dest = paths.deno_path()
    new = dest.with_name(dest.name + ".new")
    try:
        with zipfile.ZipFile(archive) as z, z.open(dest.name) as src, open(new, "wb") as out:
            shutil.copyfileobj(src, out)
        _install(new, dest)
    except KeyError:  # el .zip no trae el programa donde se esperaba
        raise RuntimeError(t("setup.no_deno")) from None
    finally:
        archive.unlink(missing_ok=True)
        new.unlink(missing_ok=True)


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


def deno_version() -> str:
    location = deno_location()
    if location is None:
        return t("ytdlp.not_installed")
    try:
        # "deno 2.5.6 (stable, release, x86_64-pc-windows-msvc)" -> "2.5.6"
        first_line = proc.run([location or "deno", "--version"], timeout=30).stdout.splitlines()[0]
        return first_line.split(" ")[1] if first_line.startswith("deno ") else first_line
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


def _latest_deno() -> str:
    """Última versión de Deno publicada en GitHub: "2.5.6"."""
    request = urllib.request.Request(DENO_API, headers={"User-Agent": "Onitune", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))["tag_name"].lstrip("vV")


def update_deno(progress: ProgressFn) -> tuple[bool, str]:
    """Descarga Deno si hay una versión más nueva. Devuelve (todo_bien, mensaje)."""
    if not paths.deno_path().exists() and deno_location() == "":
        return True, t("deps.system")  # lo instaló el usuario: no lo tocamos
    try:
        if paths.deno_path().exists() and not updates.is_newer(_latest_deno(), deno_version()):
            return True, t("ytdlp.up_to_date")
        download_deno(progress)
    except Exception as exc:
        return False, t("ytdlp.update_error", error=exc)
    return True, t("ytdlp.updated")


def update_ffmpeg(progress: ProgressFn) -> tuple[bool, str]:
    """Renueva ffmpeg si el nuestro tiene más de FFMPEG_MAX_AGE_DAYS días."""
    exe = paths.ffmpeg_path()
    if not exe.exists() and ffmpeg_location() == "":
        return True, t("deps.system")
    if exe.exists() and time.time() - exe.stat().st_mtime < FFMPEG_MAX_AGE_DAYS * 86400:
        return True, t("deps.ffmpeg_fresh")
    try:
        download_ffmpeg(progress)
    except Exception as exc:
        return False, t("ytdlp.update_error", error=exc)
    return True, t("ytdlp.updated")


def update_components(names: list[str], progress_for: Callable[[str], ProgressFn]) -> dict[str, tuple[bool, str]]:
    """Actualiza los componentes pedidos ("ytdlp", "deno", "ffmpeg").

    progress_for(nombre) da la función de progreso de cada descarga.
    Devuelve {nombre: (todo_bien, mensaje)}.
    """
    with _update_lock:
        _clean_old()
        results = {}
        if "ytdlp" in names:
            results["ytdlp"] = update_ytdlp()
        if "deno" in names:
            results["deno"] = update_deno(progress_for("deno"))
        if "ffmpeg" in names:
            results["ffmpeg"] = update_ffmpeg(progress_for("ffmpeg"))
        return results


def versions() -> dict:
    """Versión de cada componente, para Ajustes."""
    # La app descarga su propia copia la primera vez; si no, usa la del sistema
    def where(location) -> str:
        return t("settings.ffmpeg_own") if location else t("settings.ffmpeg_system")

    return {"ytdlp": t("settings.version", version=ytdlp_version()),
            "ffmpeg": f"{ffmpeg_version()} · {where(ffmpeg_location())}",
            "deno": f"{deno_version()} · {where(deno_location())}"}
