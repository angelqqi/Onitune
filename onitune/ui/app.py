"""La ventana principal: menú lateral, pestañas, temas, aviso del portapapeles y cierre."""

import asyncio
from typing import Optional

import flet as ft

from .. import APP_NAME, APP_VERSION
from ..core import deps, paths, updates, ytdlp
from ..core.history import History
from ..core.queue import DOWNLOADING, PROCESSING, DownloadItem, DownloadQueue
from ..core.settings import Settings
from . import themes
from .audio_view import AudioView
from .common import ACCENT, MUTED, OK, C, ui_call
from .history_view import HistoryView
from .queue_view import QueueView
from .settings_view import SettingsView
from .setup_view import SetupView
from .video_view import VideoView

ORDER = ["audio", "video", "queue", "history", "settings"]
SCROLL_GAP = 16  # espacio a la derecha para la barra de desplazamiento


class OnituneApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.settings = Settings.load()
        self.history = History()
        self.queue: Optional[DownloadQueue] = None

        # Servicios de Flet: portapapeles y selector de carpetas/archivos
        self.clipboard = ft.Clipboard()
        self.file_picker = ft.FilePicker()

        self.views: dict = {}
        self.current = "audio"
        self.ytdlp_ok = True  # resultado de la actualización automática
        self._clip_last = ""
        self._clip_shown = ""  # enlace que muestra el aviso ahora mismo
        self._clip_ignored: set[str] = set()
        self.app_update: Optional[tuple[str, str]] = None  # (versión nueva, enlace) si hay
        self.closing = False  # al cerrar, los bucles en segundo plano se detienen

    # ------------------------------------------------------------ arranque

    def start(self) -> None:
        page = self.page
        page.title = APP_NAME
        page.padding = 0
        page.window.width, page.window.height = 1200, 820
        page.window.min_width, page.window.min_height = 760, 560
        icon = paths.assets_dir() / "icon.ico"
        if icon.exists():
            page.window.icon = str(icon)
        self.apply_theme(update=False)

        # Al cerrar: guardar la cola antes de salir
        page.window.prevent_close = True
        page.window.on_event = self._on_window_event

        if deps.missing():
            setup = SetupView(self, on_done=self.show_main)
            page.add(setup.root)
            page.update()
            setup.start()
        else:
            self.show_main()

    def apply_theme(self, update: bool = True) -> None:
        """Aplica el tema elegido en Ajustes y redibuja la ventana."""
        palette = themes.get(self.settings.theme)
        C.palette = palette
        page = self.page
        page.theme = page.dark_theme = themes.build(palette)
        page.theme_mode = ft.ThemeMode.DARK if palette.dark else ft.ThemeMode.LIGHT
        page.bgcolor = palette.bg
        if self.views:
            # Algunas piezas leen el color al crearse: las volvemos a crear.
            # Las descargas no se tocan.
            self._build_ui()
        elif update:
            page.update()

    def show_main(self) -> None:
        page = self.page
        self.queue = DownloadQueue(self.settings, self.history)
        self.queue.listeners.append(lambda item: ui_call(page, self._on_queue_change, item))
        self.history.listeners.append(lambda: ui_call(page, self._on_history_change))

        self._build_ui()

        self.queue.start()
        if self.settings.auto_update_ytdlp:
            page.run_thread(self._auto_update)
        if self.settings.check_app_updates:
            page.run_thread(self._check_app_update)
        page.run_task(self._watch_clipboard)

    def _build_ui(self) -> None:
        self.views = {
            "audio": AudioView(self),
            "video": VideoView(self),
            "queue": QueueView(self),
            "history": HistoryView(self),
            "settings": SettingsView(self),
        }

        # --- Menú lateral
        self.queue_icon = ft.Icon(ft.Icons.DOWNLOAD_OUTLINED)
        self.queue_icon_selected = ft.Icon(ft.Icons.DOWNLOAD)
        self.status_ytdlp = self._status_line(OK, "")
        self.status_ffmpeg = self._status_line(OK, "ffmpeg listo")
        self.status_queue = self._status_line(C.info, "")
        self.rail = ft.NavigationRail(
            selected_index=ORDER.index(self.current),
            extended=True,
            min_extended_width=200,
            bgcolor=ft.Colors.SURFACE_DIM,  # en themes.build(), surface_dim = color del menú
            leading=ft.Container(
                padding=ft.Padding.only(left=8, right=8, top=12, bottom=20),
                content=ft.Row(
                    spacing=12,
                    controls=[
                        ft.Image(src="/icon.png", width=36, height=36),
                        ft.Column(
                            spacing=0,
                            controls=[
                                ft.Text(APP_NAME, size=18, weight=ft.FontWeight.BOLD),
                                ft.Text("Audio y video de YouTube", size=12, color=MUTED),
                            ],
                        ),
                    ],
                ),
            ),
            trailing=ft.Container(
                margin=ft.Margin.only(left=12, right=12, bottom=16),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border_radius=12,
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                width=176,
                content=ft.Column(spacing=8, controls=[self.status_ytdlp, self.status_ffmpeg, self.status_queue]),
            ),
            pin_trailing_to_bottom=True,
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.MUSIC_NOTE_OUTLINED, selected_icon=ft.Icons.MUSIC_NOTE, label="Audio"),
                ft.NavigationRailDestination(icon=ft.Icons.MOVIE_OUTLINED, selected_icon=ft.Icons.MOVIE, label="Video"),
                ft.NavigationRailDestination(icon=self.queue_icon, selected_icon=self.queue_icon_selected, label="Descargas"),
                ft.NavigationRailDestination(icon=ft.Icons.HISTORY, label="Historial"),
                ft.NavigationRailDestination(icon=ft.Icons.TUNE, label="Ajustes"),
            ],
            on_change=lambda e: self.go(ORDER[e.control.selected_index]),
        )

        # --- Aviso de enlace copiado
        self.clip_text = ft.Text(weight=ft.FontWeight.W_500)
        self.clip_url = ft.Text(size=13, color=MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.clip_banner = ft.Container(
            visible=False,
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=12,
            border=ft.Border.all(1, ACCENT),
            bgcolor=ft.Colors.with_opacity(0.08, ACCENT),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.CONTENT_PASTE, color=ACCENT),
                    ft.Column(expand=True, spacing=2, controls=[self.clip_text, self.clip_url]),
                    ft.TextButton("Ignorar", on_click=self._clip_dismiss),
                    ft.OutlinedButton("Video", icon=ft.Icons.MOVIE_OUTLINED, on_click=lambda e: self._clip_use("video")),
                    ft.FilledButton("Audio", icon=ft.Icons.MUSIC_NOTE, on_click=lambda e: self._clip_use("audio")),
                ],
            ),
        )
        if self._clip_shown:
            self._show_clip(self._clip_shown)

        # --- Aviso de versión nueva de Onitune
        self.update_text = ft.Text(weight=ft.FontWeight.W_500)
        self.update_button = ft.FilledButton("Descargar", icon=ft.Icons.OPEN_IN_NEW)
        self.update_banner = ft.Container(
            visible=False,
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=12,
            border=ft.Border.all(1, ACCENT),
            bgcolor=ft.Colors.with_opacity(0.08, ACCENT),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.NEW_RELEASES_OUTLINED, color=ACCENT),
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[self.update_text, ft.Text(f"Versión instalada: {APP_VERSION}", size=13, color=MUTED)],
                    ),
                    ft.TextButton("Ahora no", on_click=self._update_dismiss),
                    self.update_button,
                ],
            ),
        )
        if self.app_update:
            self._show_app_update()

        # Los avisos dejan libre a la derecha el mismo carril que la barra de desplazamiento
        self.update_banner.margin = self.clip_banner.margin = ft.Margin.only(right=SCROLL_GAP)
        self.body = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, controls=[self._page_box(self.current)])
        content = ft.Container(
            expand=True,
            bgcolor=ft.Colors.SURFACE,
            padding=ft.Padding.only(left=24, right=8, top=18, bottom=8),
            content=ft.Column(expand=True, spacing=10, controls=[self.update_banner, self.clip_banner, self.body]),
        )

        self.page.controls.clear()
        self.page.add(ft.Row(expand=True, spacing=0, controls=[self.rail, ft.VerticalDivider(width=1), content]))
        self._show_ytdlp_status()
        self._update_status()
        self.page.update()

    def _status_line(self, color: str, text: str) -> ft.Row:
        return ft.Row(
            spacing=8,
            controls=[
                ft.Container(width=8, height=8, border_radius=4, bgcolor=color),
                ft.Text(text, size=13),
            ],
        )

    # ------------------------------------------------------------ navegación

    def _page_box(self, name: str) -> ft.Container:
        """La pestaña con un margen derecho: ahí va la barra de desplazamiento sin tapar nada."""
        return ft.Container(padding=ft.Padding.only(right=SCROLL_GAP), content=self.views[name].root)

    def go(self, name: str) -> None:
        self.current = name
        self.rail.selected_index = ORDER.index(name)
        self.body.controls = [self._page_box(name)]
        if name == "history":
            self.views["history"].refresh()
        self.page.update()

    # ------------------------------------------------------------ cambios de la cola

    def _on_queue_change(self, item: Optional[DownloadItem]) -> None:
        self.views["queue"].on_queue_change(item)
        self._update_status()

    def _on_history_change(self) -> None:
        self.views["history"].refresh()

    def _update_status(self) -> None:
        pending = self.queue.pending if self.queue else 0
        badge = str(pending) if pending else None
        self.queue_icon.badge = badge
        self.queue_icon_selected.badge = badge
        running = self.queue.count(DOWNLOADING, PROCESSING) if self.queue else 0
        self.status_queue.controls[1].value = f"{running} descargando ahora" if running else "Sin descargas activas"
        self.status_queue.controls[1].color = None if running else MUTED

    # ------------------------------------------------------------ actualización automática

    def _show_ytdlp_status(self) -> None:
        self.status_ytdlp.controls[0].bgcolor = OK if self.ytdlp_ok else C.warn
        self.status_ytdlp.controls[1].value = "yt-dlp listo" if self.ytdlp_ok else "yt-dlp sin actualizar"

    def _auto_update(self) -> None:
        ok, message = deps.update_ytdlp()

        def show():
            self.ytdlp_ok = ok
            self._show_ytdlp_status()
            self.views["settings"].show_auto_update_result(ok, message)

        ui_call(self.page, show)

    # ------------------------------------------------------------ versión nueva de Onitune

    def _check_app_update(self) -> None:
        """Corre en otro hilo: pregunta a GitHub si hay una versión nueva."""
        found = updates.check()
        if found:
            def show():
                self.app_update = found
                self._show_app_update()

            ui_call(self.page, show)

    def _show_app_update(self) -> None:
        version, url = self.app_update
        self.update_text.value = f"Hay una versión nueva de {APP_NAME}: {version}"
        self.update_button.url = url  # el botón abre la página de descarga en el navegador
        self.update_banner.visible = True

    def _update_dismiss(self, e=None) -> None:
        # Se oculta hasta la próxima vez que se abra la app
        self.app_update = None
        self.update_banner.visible = False

    # ------------------------------------------------------------ portapapeles

    async def _watch_clipboard(self) -> None:
        """Cada segundo y medio mira si copiaste un enlace de YouTube."""
        while not self.closing:
            await asyncio.sleep(1.5)
            if self.closing or not self.settings.watch_clipboard:
                continue
            try:
                text = (await self.clipboard.get() or "").strip()
            except Exception:
                continue  # la ventana se está cerrando o el portapapeles no tiene texto
            if text == self._clip_last:
                continue
            self._clip_last = text
            if ytdlp.is_youtube_url(text) and text not in self._clip_ignored:
                self._show_clip(text)
                self.page.update()

    def _show_clip(self, url: str) -> None:
        is_list = ytdlp.is_playlist_url(url) and "v=" not in url
        self._clip_shown = url
        self.clip_text.value = "Enlace de playlist copiado" if is_list else "Enlace de YouTube copiado"
        self.clip_url.value = url
        self.clip_banner.visible = True

    def _clip_dismiss(self, e=None) -> None:
        self._clip_ignored.add(self._clip_shown)
        self._clip_shown = ""
        self.clip_banner.visible = False

    def _clip_use(self, where: str) -> None:
        url = self._clip_shown
        self._clip_dismiss()
        self.go(where)
        self.views[where].use_url(url)

    # ------------------------------------------------------------ cierre

    async def _on_window_event(self, e) -> None:
        if e.type == ft.WindowEventType.CLOSE:
            self.closing = True
            if self.queue:
                self.queue.shutdown()
            self.settings.save()
            await self.page.window.destroy()
