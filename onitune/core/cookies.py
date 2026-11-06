"""Cookies del navegador: qué navegadores hay y si yt-dlp puede leer sus cookies.

Las cookies sirven para videos con restricción de edad, privados o de miembros:
yt-dlp usa la sesión de YouTube del navegador sin pedir la contraseña.
La app nunca guarda las cookies en ningún lado: yt-dlp las lee cada vez.
"""

import os
import re
from pathlib import Path

from . import paths, proc, ytdlp
from .i18n import t
from .settings import Settings

# (nombre para yt-dlp, nombre para mostrar)
BROWSERS = [
    ("firefox", "Firefox"),
    ("chrome", "Chrome"),
    ("edge", "Edge"),
    ("brave", "Brave"),
    ("opera", "Opera"),
    ("vivaldi", "Vivaldi"),
    ("chromium", "Chromium"),
]

# En Windows, Chrome y Edge cifran sus cookies desde 2024 de forma que solo el
# propio navegador puede leerlas (App-Bound Encryption): yt-dlp siempre falla.
BLOCKED_ON_WINDOWS = {"chrome", "edge"}

# "Me at the zoo": video corto y que siempre está disponible
TEST_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def _folders(browser: str) -> list[Path]:
    """Carpetas donde cada navegador guarda sus datos (las mismas que busca yt-dlp)."""
    home = Path.home()
    if paths.IS_WINDOWS:
        local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
        roaming = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
        return {
            "firefox": [roaming / "Mozilla" / "Firefox" / "Profiles"],
            "chrome": [local / "Google" / "Chrome" / "User Data"],
            "edge": [local / "Microsoft" / "Edge" / "User Data"],
            "brave": [local / "BraveSoftware" / "Brave-Browser" / "User Data"],
            "opera": [roaming / "Opera Software" / "Opera Stable"],
            "vivaldi": [local / "Vivaldi" / "User Data"],
            "chromium": [local / "Chromium" / "User Data"],
        }[browser]
    config = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return {
        # Firefox normal, el de Snap (Ubuntu) y el de Flatpak
        "firefox": [home / ".mozilla" / "firefox", config / "mozilla" / "firefox",
                    home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
                    home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox"],
        "chrome": [config / "google-chrome"],
        "edge": [config / "microsoft-edge"],
        "brave": [config / "BraveSoftware" / "Brave-Browser"],
        "opera": [config / "opera"],
        "vivaldi": [config / "vivaldi"],
        "chromium": [config / "chromium"],
    }[browser]


def browsers() -> list[dict]:
    """Los navegadores compatibles, con si están instalados y si se pueden usar."""
    return [
        {
            "id": browser,
            "name": name,
            "installed": any(folder.is_dir() for folder in _folders(browser)),
            "blocked": paths.IS_WINDOWS and browser in BLOCKED_ON_WINDOWS,
        }
        for browser, name in BROWSERS
    ]


def test(settings: Settings) -> dict:
    """Prueba las cookies elegidas en Ajustes. Devuelve {"ok": bool, "message": texto}.

    yt-dlp lee las cookies y simula la descarga de un video corto (no baja nada).
    """
    mode = settings.cookies_mode
    if mode == "none":
        return {"ok": False, "message": t("settings.cookies_test_none")}
    if mode == "file" and not os.path.isfile(settings.cookies_file):
        return {"ok": False, "message": t("settings.cookies_file_missing")}
    if mode == "browser" and paths.IS_WINDOWS and settings.cookies_browser in BLOCKED_ON_WINDOWS:
        return {"ok": False, "message": t("error.cookies_blocked")}

    # Sin --no-warnings: el aviso de cookies caducadas es un "WARNING"
    args = [a for a in ytdlp.base_args(settings) if a != "--no-warnings"]
    args += ["--simulate", "--no-playlist", "--", TEST_URL]
    try:
        result = proc.run(args, timeout=120)
    except Exception as exc:
        return {"ok": False, "message": t("error.run", error=exc)}
    output = result.stdout + "\n" + result.stderr
    if result.returncode != 0:
        return {"ok": False, "message": ytdlp.friendly_error(ytdlp.last_error(result.stderr or result.stdout))}
    if "no longer valid" in output.lower():
        return {"ok": False, "message": t("error.cookies_expired")}
    if mode == "file":
        return {"ok": True, "message": t("settings.cookies_ok_file")}
    found = re.search(r"Extracted (\d+) cookies", output)
    count = int(found.group(1)) if found else 0
    if not count:
        return {"ok": False, "message": t("settings.cookies_empty")}
    name = dict(BROWSERS).get(settings.cookies_browser, settings.cookies_browser)
    return {"ok": True, "message": t("settings.cookies_ok_browser", count=count, browser=name)}
