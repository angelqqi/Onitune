"""Pestaña Ajustes."""

import flet as ft

from .. import APP_NAME, APP_VERSION, REPO_URL
from ..core import deps
from . import themes
from .common import ERR, MUTED, OK, card, header, section_label, ui_call

BROWSERS = [("firefox", "Firefox"), ("chrome", "Chrome"), ("edge", "Edge"), ("brave", "Brave"), ("opera", "Opera"), ("vivaldi", "Vivaldi")]


def _title(text: str) -> ft.Text:
    return ft.Text(text, size=16, weight=ft.FontWeight.W_500)


class SettingsView:
    def __init__(self, app):
        self.app = app
        s = app.settings

        # --- Carpetas
        self.audio_dir = ft.Text(s.audio_dir, size=13, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, selectable=True)
        self.video_dir = ft.Text(s.video_dir, size=13, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, selectable=True)
        folders = card(
            ft.Column(
                spacing=12,
                controls=[
                    _title("Carpetas de descarga"),
                    self._folder_row("Audio", self.audio_dir, "audio_dir"),
                    self._folder_row("Video", self.video_dir, "video_dir"),
                    ft.Switch(
                        label="Guardar cada playlist en su propia subcarpeta",
                        value=s.playlist_subfolder,
                        on_change=lambda e: self._set("playlist_subfolder", e.control.value),
                    ),
                ],
            )
        )

        # --- Cookies
        self.browser = ft.Dropdown(dense=True, 
            value=s.cookies_browser,
            width=180,
            options=[ft.DropdownOption(key=k, text=t) for k, t in BROWSERS],
            on_select=lambda e: self._set("cookies_browser", e.control.value),
        )
        self.cookies_file = ft.Text(s.cookies_file or "Ningún archivo elegido", size=13, color=MUTED, expand=True)
        self.cookies_file_button = ft.OutlinedButton("Elegir archivo…", on_click=self._pick_cookies)
        self.cookies_mode = ft.RadioGroup(
            value=s.cookies_mode,
            on_change=self._on_cookies_mode,
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Radio(value="none", label="No usar cookies"),
                    ft.Row(controls=[ft.Radio(value="browser", label="Usar las del navegador"), self.browser]),
                    ft.Row(controls=[ft.Radio(value="file", label="Usar un archivo cookies.txt"), self.cookies_file_button, self.cookies_file]),
                ],
            ),
        )
        cookies = card(
            ft.Column(
                spacing=10,
                controls=[
                    _title("Cookies"),
                    ft.Text(
                        "Sirven para videos con restricción de edad, privados o de miembros. La app usa la sesión "
                        "de YouTube del navegador, sin pedir la contraseña. Con Chrome o Edge puede fallar si el navegador está abierto.",
                        size=13,
                        color=MUTED,
                    ),
                    self.cookies_mode,
                ],
            )
        )
        self._apply_cookie_rules()

        # --- Tema y avisos
        appearance = card(
            ft.Column(
                spacing=12,
                controls=[
                    _title("Tema"),
                    ft.Text("Colores de la app.", size=13, color=MUTED),
                    section_label("Oscuros"),
                    ft.Row(wrap=True, spacing=10, run_spacing=10, controls=[self._theme_tile(p) for p in themes.THEMES if p.dark]),
                    section_label("Claros"),
                    ft.Row(wrap=True, spacing=10, run_spacing=10, controls=[self._theme_tile(p) for p in themes.THEMES if not p.dark]),
                ],
            )
        )
        notices = card(
            ft.Column(
                spacing=4,
                controls=[
                    _title("Avisos"),
                    ft.Switch(label="Notificar cuando terminen todas las descargas", value=s.notify_queue_done,
                              on_change=lambda e: self._set("notify_queue_done", e.control.value)),
                    ft.Switch(label="Notificar cada descarga terminada", value=s.notify_each,
                              on_change=lambda e: self._set("notify_each", e.control.value)),
                    ft.Switch(label="Detectar enlaces de YouTube copiados", value=s.watch_clipboard,
                              on_change=lambda e: self._set("watch_clipboard", e.control.value)),
                ],
            )
        )

        # --- Búsqueda
        searching = card(
            ft.Column(
                spacing=10,
                controls=[
                    _title("Búsqueda"),
                    ft.Text(
                        "Al buscar en la pestaña Audio, busca solo canciones en YouTube Music. Traen artista, "
                        "álbum y portada bien puestos, pero la búsqueda tarda unos segundos más. "
                        "Apagado, busca en YouTube normal (incluye videos musicales, en vivo, con letra…).",
                        size=13,
                        color=MUTED,
                    ),
                    ft.Switch(
                        label="Buscar canciones en YouTube Music",
                        value=s.music_search,
                        on_change=lambda e: self._set("music_search", e.control.value),
                    ),
                ],
            )
        )

        # --- Portadas
        covers = card(
            ft.Column(
                spacing=10,
                controls=[
                    _title("Portada cuadrada"),
                    ft.Text(
                        "YouTube guarda las miniaturas en formato rectangular y rellena los lados de las portadas "
                        "de álbum. Recortar deja solo el cuadrado del centro, como en YouTube Music. "
                        "En videos con una imagen rectangular de verdad se pierden los lados.",
                        size=13,
                        color=MUTED,
                    ),
                    ft.RadioGroup(
                        value=s.cover_crop,
                        on_change=lambda e: self._set("cover_crop", e.control.value),
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Radio(value="music", label="Solo canciones de YouTube Music (búsqueda o enlaces music.youtube.com)"),
                                ft.Radio(value="audio", label="Todas las descargas de audio"),
                                ft.Radio(value="video", label="Todas las descargas de video"),
                                ft.Radio(value="both", label="Audio y video"),
                                ft.Radio(value="none", label="Nunca (dejar la miniatura como viene)"),
                            ],
                        ),
                    ),
                ],
            )
        )

        # --- Componentes
        self.ytdlp_version = ft.Text("…", size=12, color=MUTED)
        self.ffmpeg_version = ft.Text("…", size=12, color=MUTED)
        self.update_status = ft.Text("", size=13, weight=ft.FontWeight.W_500)
        self.update_button = ft.OutlinedButton("Buscar actualización", icon=ft.Icons.REFRESH, on_click=self._update_ytdlp)
        components = card(
            ft.Column(
                spacing=14,
                controls=[
                    _title("Componentes"),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(expand=True, spacing=2, controls=[ft.Text("yt-dlp", weight=ft.FontWeight.W_500), self.ytdlp_version]),
                            self.update_status,
                            self.update_button,
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                    ft.Column(spacing=2, controls=[ft.Text("ffmpeg", weight=ft.FontWeight.W_500), self.ffmpeg_version]),
                    ft.Switch(
                        label="Buscar actualizaciones de yt-dlp al abrir la app",
                        value=s.auto_update_ytdlp,
                        on_change=lambda e: self._set("auto_update_ytdlp", e.control.value),
                    ),
                    ft.Switch(
                        label="Avisar cuando haya una versión nueva de Onitune",
                        value=s.check_app_updates,
                        on_change=lambda e: self._set("check_app_updates", e.control.value),
                    ),
                ],
            )
        )

        self.root = ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # todas las tarjetas a lo ancho
            controls=[
                header("Ajustes", "Los cambios se guardan automáticamente."),
                folders,
                cookies,
                appearance,
                notices,
                searching,
                covers,
                components,
                self._about(),
            ],
        )
        app.page.run_thread(self._load_versions)

    # ------------------------------------------------------------ ayudas

    def _set(self, name: str, value) -> None:
        setattr(self.app.settings, name, value)
        self.app.settings.save()

    def _folder_row(self, label: str, text: ft.Text, setting: str) -> ft.Row:
        async def pick(e):
            path = await self.app.file_picker.get_directory_path(
                dialog_title=f"Carpeta para {label.lower()}", initial_directory=getattr(self.app.settings, setting)
            )
            if path:
                text.value = path
                self._set(setting, path)
                self.app.page.update()

        return ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(label, width=60),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    border_radius=12,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    content=ft.Row(controls=[text]),
                ),
                ft.OutlinedButton("Cambiar", icon=ft.Icons.FOLDER_OPEN_OUTLINED, on_click=pick),
            ],
        )

    # ------------------------------------------------------------ cookies

    def _apply_cookie_rules(self) -> None:
        mode = self.app.settings.cookies_mode
        self.browser.disabled = mode != "browser"
        self.cookies_file_button.disabled = mode != "file"

    def _on_cookies_mode(self, e) -> None:
        self._set("cookies_mode", self.cookies_mode.value)
        self._apply_cookie_rules()

    async def _pick_cookies(self, e) -> None:
        files = await self.app.file_picker.pick_files(
            dialog_title="Seleccionar archivo cookies.txt", allowed_extensions=["txt"], file_type=ft.FilePickerFileType.CUSTOM
        )
        if files and files[0].path:
            self.cookies_file.value = files[0].path
            self._set("cookies_file", files[0].path)
            self.app.page.update()

    # ------------------------------------------------------------ tema

    def _theme_tile(self, p: themes.Palette) -> ft.Container:
        """Tarjetita de muestra de un tema, pintada con sus propios colores."""
        selected = themes.get(self.app.settings.theme).id == p.id
        swatches = [
            ft.Container(width=14, height=14, border_radius=7, bgcolor=color)
            for color in (p.primary, p.secondary, p.ok, p.warn, p.info, p.error)
        ]
        return ft.Container(
            width=184,
            padding=12,
            border_radius=12,
            bgcolor=p.bg,
            border=ft.Border.all(2 if selected else 1, p.primary if selected else p.border),
            ink=True,
            on_click=lambda e: self._pick_theme(p.id),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(p.name, color=p.fg, size=13, weight=ft.FontWeight.W_500, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Icon(ft.Icons.CHECK_CIRCLE, color=p.primary, size=18, visible=selected),
                        ]
                    ),
                    ft.Container(
                        height=24,
                        border_radius=6,
                        bgcolor=p.card,
                        padding=ft.Padding.symmetric(horizontal=8),
                        alignment=ft.Alignment.CENTER_LEFT,
                        content=ft.Text("Texto de ejemplo", color=p.muted, size=11),
                    ),
                    ft.Row(spacing=5, controls=swatches),
                ],
            ),
        )

    def _pick_theme(self, theme_id: str) -> None:
        self._set("theme", theme_id)
        self.app.apply_theme()

    # ------------------------------------------------------------ acerca de

    def _about(self) -> ft.Container:
        return card(
            ft.Column(
                spacing=8,
                controls=[
                    _title(f"Acerca de {APP_NAME} {APP_VERSION}"),
                    ft.Text("Idea, diseño y dirección: angelqqi."),
                    ft.Text("El código se escribió con ayuda de inteligencia artificial (Claude, de Anthropic).", color=MUTED, size=13),
                    ft.Text(
                        "Software libre con licencia MIT. Usa yt-dlp, FFmpeg y Flet; sus licencias están en "
                        "THIRD_PARTY_LICENSES.md.",
                        color=MUTED,
                        size=13,
                    ),
                    ft.Text(
                        f"{APP_NAME} no está afiliado a YouTube ni a Google. Solo se debe descargar contenido "
                        "que se tenga derecho a guardar.",
                        color=MUTED,
                        size=13,
                    ),
                    ft.Row(controls=[ft.TextButton("Ver el proyecto en GitHub", icon=ft.Icons.OPEN_IN_NEW, url=REPO_URL)]),
                ],
            )
        )

    # ------------------------------------------------------------ componentes

    def _load_versions(self) -> None:
        yt, ff = deps.ytdlp_version(), deps.ffmpeg_version()
        # La app descarga su propia copia la primera vez; si no, usa la del sistema
        where = "descargado por Onitune" if deps.ffmpeg_location() else "instalado en el sistema"

        def show():
            self.ytdlp_version.value = f"versión {yt}"
            self.ffmpeg_version.value = f"{ff} · {where}"

        ui_call(self.app.page, show)

    def _update_ytdlp(self, e=None) -> None:
        self.update_button.disabled = True
        self.update_status.value, self.update_status.color = "Buscando…", MUTED
        self.app.page.run_thread(self._update_worker)

    def _update_worker(self) -> None:
        ok, message = deps.update_ytdlp()
        version = deps.ytdlp_version()

        def show():
            self.update_button.disabled = False
            self.update_status.value, self.update_status.color = message, OK if ok else ERR
            self.ytdlp_version.value = f"versión {version}"

        ui_call(self.app.page, show)

    def show_auto_update_result(self, ok: bool, message: str) -> None:
        """La app llama a esto tras la búsqueda automática al abrir."""
        self.update_status.value, self.update_status.color = message, OK if ok else ERR
        self.app.page.run_thread(self._load_versions)
