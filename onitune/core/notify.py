"""Notificaciones del sistema (Windows 10/11 y Linux), sin librerías extra."""

import shutil
import subprocess
import sys
import threading

from . import proc

# Windows solo muestra avisos de programas "registrados". Usamos el
# identificador de PowerShell, que siempre existe.
_WIN_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_WIN_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$texts = $xml.GetElementsByTagName('text')
$texts.Item(0).AppendChild($xml.CreateTextNode($env:ONITUNE_TITLE)) > $null
$texts.Item(1).AppendChild($xml.CreateTextNode($env:ONITUNE_BODY)) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:ONITUNE_APPID).Show($toast)
"""


def _send(title: str, message: str) -> None:
    try:
        if sys.platform == "win32":
            kwargs = proc.hidden_kwargs()
            # El texto va en variables de entorno para no tener problemas con comillas
            kwargs["env"].update(ONITUNE_TITLE=title, ONITUNE_BODY=message, ONITUNE_APPID=_WIN_APP_ID)
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
