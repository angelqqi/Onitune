"""Aviso de versiones nuevas de Onitune.

Pregunta a GitHub cuál es la última Release publicada y la compara con la
versión de la app. Solo avisa: no descarga ni instala nada.
"""

import json
import re
import urllib.request
from typing import Optional

from .. import APP_VERSION, REPO_URL

# REPO_URL = "https://github.com/usuario/Onitune" -> API de su última Release
API_URL = REPO_URL.replace("https://github.com/", "https://api.github.com/repos/") + "/releases/latest"


def _parts(version: str) -> tuple[int, ...]:
    """"v1.2.10" -> (1, 2, 10). Así 1.2.10 es mayor que 1.2.9 (como texto no lo sería)."""
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3])


def is_newer(latest: str, current: str = APP_VERSION) -> bool:
    try:
        return _parts(latest) > _parts(current)
    except ValueError:
        return False


def check() -> Optional[tuple[str, str]]:
    """Devuelve (versión, enlace de descarga) si hay una versión nueva, o None.

    Cualquier problema (sin internet, repo sin Releases, GitHub no responde)
    devuelve None: no vale la pena molestar con un error por esto.
    """
    request = urllib.request.Request(
        API_URL, headers={"User-Agent": "Onitune", "Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    tag = data.get("tag_name") or ""
    if tag and is_newer(tag):
        return tag.lstrip("vV"), data.get("html_url") or f"{REPO_URL}/releases/latest"
    return None
