"""Ayudas para ejecutar programas externos (yt-dlp, ffmpeg) sin abrir consolas."""

import os
import shutil
import subprocess
import sys


def hidden_kwargs() -> dict:
    """Opciones de subprocess para que en Windows no aparezca una ventana negra."""
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    kwargs["env"] = env
    return kwargs


def run(args: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    """Ejecuta un programa, espera a que termine y devuelve su salida como texto."""
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        **hidden_kwargs(),
    )


def open_path(path: str) -> None:
    """Abre un archivo o carpeta con el programa predeterminado del sistema."""
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - es justo lo que queremos
    elif shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", path])
    else:
        # Sin xdg-utils (sistemas mínimos): gio viene con GLib, que GTK ya necesita
        subprocess.Popen(["gio", "open", path])


def show_in_folder(path: str) -> None:
    """Abre la carpeta que contiene el archivo (y lo selecciona en Windows)."""
    if sys.platform == "win32" and os.path.isfile(path):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        open_path(folder)
