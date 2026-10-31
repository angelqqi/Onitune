"""Textos de la app en varios idiomas.

Cada idioma es un archivo JSON en onitune/idiomas/ (es.json, en.json, pt.json...).
Para agregar un idioma basta con copiar es.json con el código nuevo (por
ejemplo fr.json) y traducir los textos. No hace falta tocar código.

- Las claves (a la izquierda) no se traducen.
- {nombre} se reemplaza por un dato: "Resultados para “{text}”".
- Un texto con plural es un objeto: {"one": "1 video", "other": "{n} videos"}.
- Si a un idioma le falta un texto, se usa el de español.

La página recibe todos los textos al abrir (ver ui/api.py) y usa su propia
función t() con las mismas reglas (ver web/app.js).
"""

import json
import locale
import os
import sys
from pathlib import Path
from typing import Optional

FOLDER = Path(__file__).resolve().parents[1] / "idiomas"
BASE = "es"  # el idioma completo, que se usa de respaldo

_texts: dict = {}
_current = BASE


def available() -> list[tuple[str, str]]:
    """Idiomas que hay en la carpeta: [("en", "English"), ("es", "Español"), ...]."""
    result = []
    for file in sorted(FOLDER.glob("*.json")):
        try:
            name = json.loads(file.read_text(encoding="utf-8")).get("_name") or file.stem
        except (OSError, ValueError):
            continue  # archivo roto: se ignora
        result.append((file.stem, name))
    return result


def system_language() -> str:
    """Código del idioma del sistema ("es", "en", "pt"...), o "" si no se sabe."""
    name = ""
    try:
        if sys.platform == "win32":
            import ctypes

            # Idioma de la interfaz de Windows (el de los menús), p. ej. 0x340A -> "es_CL"
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            name = locale.windows_locale.get(lang_id, "")
        else:
            # Linux: las variables de siempre, en orden de prioridad ("es_CL.UTF-8")
            for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
                if os.environ.get(var):
                    name = os.environ[var].split(":")[0]
                    break
    except Exception:
        return ""
    return name.split(".")[0].replace("-", "_").split("_")[0].lower()


def resolve(choice: str = "") -> str:
    """Idioma que se usará: el elegido o, si es "" (automático), el del sistema.

    Si no hay archivo para ese idioma, se usa español.
    """
    codes = {code for code, _ in available()}
    for code in (choice, system_language()):
        if code and code in codes:
            return code
    return BASE


def _read(code: str) -> dict:
    try:
        return json.loads((FOLDER / f"{code}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load(choice: str = "") -> str:
    """Carga los textos de un idioma ("" = automático). Devuelve el código usado."""
    global _texts, _current
    _current = resolve(choice)
    texts = _read(BASE)
    if _current != BASE:
        # Encima de español: lo que falte en la traducción queda en español
        texts.update({k: v for k, v in _read(_current).items() if v})
    _texts = texts
    return _current


def current() -> str:
    if not _texts:
        load()
    return _current


def texts() -> dict:
    """Todos los textos del idioma actual (para mandarlos a la página)."""
    if not _texts:
        load()
    return _texts


def t(key: str, n: Optional[int] = None, default: Optional[str] = None, **values) -> str:
    """Texto traducido. `n` elige el plural y se puede usar como {n}.

    t("rail.running", n=2) -> "2 descargando ahora"
    t("error.run", error="...") -> "No se pudo ejecutar yt-dlp: ..."
    """
    text = texts().get(key)
    if text is None:
        return default if default is not None else key
    if isinstance(text, dict):  # plural
        text = text.get("one" if n == 1 else "other") or text.get("other") or key
    if n is not None:
        values["n"] = n
    if not values:
        return text
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text  # traducción con un {dato} mal escrito: se muestra tal cual
