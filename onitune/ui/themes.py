"""Temas de color de la app (como el selector de temas de Textual).

Para añadir un tema nuevo basta con agregar un `Palette` a la lista THEMES.
Los colores de cada tema vienen de sus paletas oficiales (créditos en
THIRD_PARTY_LICENSES.md); en algunos claros se oscureció un poco el
verde/amarillo para que el texto se lea bien.

La página (web/style.css) usa cada color como variable CSS (--bg, --card...).
Los colores intermedios (selección suave, bordes) se calculan allí con color-mix().
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Palette:
    id: str
    name: str
    dark: bool
    bg: str  # fondo de la ventana
    rail: str  # fondo del menú lateral
    card: str  # fondo de las tarjetas
    high: str  # campos de texto, elementos resaltados
    border: str  # bordes y separadores
    fg: str  # texto principal
    muted: str  # texto secundario
    primary: str  # color principal (botones, selección)
    on_primary: str  # texto encima del color principal
    secondary: str  # color de acento secundario
    ok: str  # completado
    warn: str  # pausado / avisos
    info: str  # descargando
    error: str  # errores


THEMES: list[Palette] = [
    # ---------------------------------------------------------------- oscuros
    Palette("dracula", "Drácula", True, "#282A36", "#21222C", "#343746", "#424450", "#4D5066",
            "#F8F8F2", "#A9AECB", "#BD93F9", "#282A36", "#FF79C6", "#50FA7B", "#F1FA8C", "#8BE9FD", "#FF5555"),
    Palette("dracula-pink", "Drácula rosa", True, "#282A36", "#21222C", "#343746", "#424450", "#4D5066",
            "#F8F8F2", "#A9AECB", "#FF79C6", "#282A36", "#BD93F9", "#50FA7B", "#F1FA8C", "#8BE9FD", "#FF5555"),
    Palette("tokyo-night", "Tokyo Night", True, "#1A1B26", "#16161E", "#1F2335", "#292E42", "#3B4261",
            "#C0CAF5", "#9AA5CE", "#7AA2F7", "#1A1B26", "#BB9AF7", "#9ECE6A", "#E0AF68", "#7DCFFF", "#F7768E"),
    Palette("catppuccin-mocha", "Catppuccin Mocha", True, "#1E1E2E", "#181825", "#313244", "#45475A", "#585B70",
            "#CDD6F4", "#A6ADC8", "#CBA6F7", "#1E1E2E", "#F5C2E7", "#A6E3A1", "#F9E2AF", "#89B4FA", "#F38BA8"),
    Palette("nord", "Nord", True, "#2E3440", "#292E39", "#3B4252", "#434C5E", "#4C566A",
            "#ECEFF4", "#AEB7C7", "#88C0D0", "#2E3440", "#B48EAD", "#A3BE8C", "#EBCB8B", "#81A1C1", "#BF616A"),
    Palette("gruvbox-dark", "Gruvbox", True, "#282828", "#1D2021", "#32302F", "#3C3836", "#504945",
            "#EBDBB2", "#A89984", "#FE8019", "#282828", "#FABD2F", "#B8BB26", "#FABD2F", "#83A598", "#FB4934"),
    Palette("rose-pine", "Rosé Pine", True, "#191724", "#1F1D2E", "#26233A", "#403D52", "#524F67",
            "#E0DEF4", "#908CAA", "#C4A7E7", "#191724", "#EBBCBA", "#9CCFD8", "#F6C177", "#EBBCBA", "#EB6F92"),
    Palette("monokai", "Monokai", True, "#272822", "#1E1F1C", "#2F302A", "#3E3D32", "#49483E",
            "#F8F8F2", "#A59F85", "#FD971F", "#272822", "#AE81FF", "#A6E22E", "#E6DB74", "#66D9EF", "#F92672"),
    # ---------------------------------------------------------------- claros
    Palette("alucard", "Alucard (Drácula claro)", False, "#FFFBEB", "#F5F0DA", "#FFFEF8", "#EDE7CF", "#DCD5BA",
            "#1F1F1F", "#635D97", "#644AC9", "#FFFFFF", "#A3144D", "#14710A", "#846E15", "#036A96", "#CB3A2A"),
    Palette("catppuccin-latte", "Catppuccin Latte", False, "#EFF1F5", "#E6E9EF", "#F9FAFC", "#DCE0E8", "#CCD0DA",
            "#4C4F69", "#6C6F85", "#8839EF", "#FFFFFF", "#EA76CB", "#2E8A1E", "#B86E0B", "#1E66F5", "#D20F39"),
    Palette("tokyo-night-day", "Tokyo Night Day", False, "#E1E2E7", "#D5D6DB", "#EDEEF2", "#C9CCD9", "#B7BCD0",
            "#3760BF", "#6172B0", "#2E7DE9", "#FFFFFF", "#9854F1", "#587539", "#8C6C3E", "#007197", "#D21F56"),
    Palette("solarized-light", "Solarized Light", False, "#FDF6E3", "#EEE8D5", "#FFFBEF", "#EEE8D5", "#DDD6C1",
            "#073642", "#586E75", "#268BD2", "#FFFFFF", "#D33682", "#6B7A00", "#8A6A00", "#1F7A73", "#DC322F"),
    Palette("gruvbox-light", "Gruvbox claro", False, "#FBF1C7", "#F2E5BC", "#FFF8DC", "#EBDBB2", "#D5C4A1",
            "#3C3836", "#7C6F64", "#AF3A03", "#FFFFFF", "#8F3F71", "#79740E", "#9A6210", "#076678", "#9D0006"),
    Palette("rose-pine-dawn", "Rosé Pine Dawn", False, "#FAF4ED", "#F2E9E1", "#FFFAF3", "#F2E9E1", "#DFDAD9",
            "#575279", "#6E6A86", "#286983", "#FFFFFF", "#907AA9", "#3D7E88", "#B26F12", "#907AA9", "#B4637A"),
]

BY_ID = {t.id: t for t in THEMES}
DEFAULT = "dracula"


def get(theme_id: str) -> Palette:
    # Ajustes de versiones anteriores guardaban "dark", "light" o "system"
    old = {"dark": "dracula", "system": "dracula", "light": "alucard"}
    return BY_ID.get(old.get(theme_id, theme_id), BY_ID[DEFAULT])


def to_dict(p: Palette) -> dict:
    """La paleta como diccionario, para mandarla a la página (web/app.js)."""
    return asdict(p)
