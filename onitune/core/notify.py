"""Notificaciones del sistema (Windows 10/11 y Linux), sin librerías extra."""

import shutil
import subprocess
import sys
import threading

from . import paths, proc

# Windows solo muestra avisos de programas registrados. Onitune se registra a sí
# mismo (en el registro del usuario, sin permisos de administrador) con este
# identificador, su nombre y su icono. Así el aviso dice "Onitune" y no "Windows PowerShell".
WIN_APP_ID = "angelqqi.Onitune"
_WIN_REG_KEY = r"Software\Classes\AppUserModelId" + "\\" + WIN_APP_ID
_registered = False

_WIN_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$texts = $xml.GetElementsByTagName('text')
$texts.Item(0).AppendChild($xml.CreateTextNode($env:ONITUNE_TITLE)) > $null
$texts.Item(1).AppendChild($xml.CreateTextNode($env:ONITUNE_BODY)) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:ONITUNE_APPID).Show($toast)
"""


def _register_windows() -> None:
    """Registra a Onitune como emisor de avisos (una vez por sesión)."""
    global _registered
    if _registered:
        return
    import winreg

    # El icono tiene que ser un archivo que no desaparezca: el .exe de un solo
    # archivo se descomprime en una carpeta temporal, así que se copia a la carpeta de la app.
    icon = paths.bin_dir().parent / "icon.png"
    source = paths.assets_dir() / "icon.png"
    if source.exists() and (not icon.exists() or icon.stat().st_size != source.stat().st_size):
        shutil.copyfile(source, icon)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _WIN_REG_KEY) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Onitune")
        if icon.exists():
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(icon))
    _registered = True


def _send(title: str, message: str) -> None:
    try:
        if sys.platform == "win32":
            _register_windows()
            kwargs = proc.hidden_kwargs()
            # El texto va en variables de entorno para no tener problemas con comillas
            kwargs["env"].update(ONITUNE_TITLE=title, ONITUNE_BODY=message, ONITUNE_APPID=WIN_APP_ID)
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", _WIN_SCRIPT],
                capture_output=True,
                timeout=20,
                **kwargs,
            )
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", "-a", "Onitune", title, message], capture_output=True, timeout=20)
    except Exception:
        pass  # Si el aviso falla no pasa nada: la app sigue funcionando


def notify(title: str, message: str) -> None:
    """Muestra un aviso del sistema sin bloquear la app."""
    threading.Thread(target=_send, args=(title, message), daemon=True).start()
