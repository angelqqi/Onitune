"""Leer el texto del portapapeles sin librerías extra (Windows y Linux)."""

import ctypes
import shutil
import subprocess
import sys
import threading

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


def _gtk_text() -> str:
    """Lee el portapapeles con GTK, el mismo que usa la ventana en Linux.

    Ubuntu no trae wl-paste, xclip ni xsel, pero GTK sí está (la ventana lo
    necesita). GTK solo se puede usar desde su hilo principal: desde otro hilo
    se le pide con GLib.idle_add y se espera la respuesta.
    """
    if "gi.repository.Gtk" not in sys.modules:
        return ""  # sin ventana GTK abierta (por ejemplo, en los scripts de prueba)
    from gi.repository import Gdk, GLib, Gtk

    def read() -> str:
        return Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() or ""

    if threading.current_thread() is threading.main_thread():
        return read()
    result = {"text": ""}
    done = threading.Event()

    def on_main() -> bool:
        try:
            result["text"] = read()
        finally:
            done.set()
        return False  # no repetir

    GLib.idle_add(on_main)
    done.wait(2)
    return result["text"]


def _linux_text() -> str:
    # Wayland (wl-paste) o X11 (xclip / xsel), lo que esté instalado
    for args in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]):
        if shutil.which(args[0]):
            try:
                return proc.run(args, timeout=2).stdout or ""
            except (OSError, subprocess.SubprocessError):
                return ""
    return _gtk_text()  # ninguno instalado (lo normal en Ubuntu)


def get_text() -> str:
    """Texto copiado ahora mismo ("" si no hay texto o no se pudo leer)."""
    try:
        text = _windows_text() if sys.platform == "win32" else _linux_text()
    except Exception:
        text = ""
    return text.strip()
