"""Leer el texto del portapapeles sin librerías extra (Windows y Linux)."""

import ctypes
import shutil
import subprocess
import sys

from . import proc

CF_UNICODETEXT = 13


def _windows_text() -> str:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return ""
    if not user32.OpenClipboard(None):
        return ""  # otro programa lo tiene abierto: se intenta en la próxima vuelta
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _linux_text() -> str:
    # Wayland (wl-paste) o X11 (xclip / xsel), lo que esté instalado
    for args in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]):
        if shutil.which(args[0]):
            try:
                return proc.run(args, timeout=2).stdout or ""
            except (OSError, subprocess.SubprocessError):
                return ""
    return ""


def get_text() -> str:
    """Texto copiado ahora mismo ("" si no hay texto o no se pudo leer)."""
    try:
        text = _windows_text() if sys.platform == "win32" else _linux_text()
    except Exception:
        text = ""
    return text.strip()
