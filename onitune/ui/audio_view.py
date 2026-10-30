"""Pestaña Audio: buscar o pegar un enlace y elegir formato y calidad."""

import flet as ft

from ..core import ytdlp
from .common import MUTED, OK, card, empty_state, error_text, header, loading_row, section_label, thumbnail, toast, ui_call
from .playlist_dialog import PlaylistDialog

FORMATS = {
    "mp3": "El más compatible: funciona en cualquier reproductor, auto o celular.",
    "m4a": "Muy compatible y con mejor calidad que MP3 al mismo tamaño. YouTube ya lo entrega así, sin reconvertir.",
    "opus": "El audio original de YouTube: la mejor calidad por tamaño. Algunos reproductores antiguos no lo abren.",
    "flac": "Sin pérdida al guardar, pero YouTube no tiene audio sin pérdida: no suena mejor, solo ocupa más.",
    "wav": "Sin compresión, útil para editar audio. Los archivos son muy grandes.",
}
LOSSLESS = ("flac", "wav")


class AudioView:
    def __init__(self, app):
        self.app = app
        s = app.settings

        # --- Campo de búsqueda / enlace
        self.query = ft.TextField(dense=True, 
            hint_text="Enlace de YouTube o nombre de una canción",
            prefix_icon=ft.Icons.SEARCH,
            expand=True,
            border_radius=12,
            on_change=self._on_query_change,
            on_submit=self._go,
        )
        self.go_button = ft.FilledButton("Buscar", icon=ft.Icons.SEARCH, on_click=self._go, height=40)
        paste_button = ft.OutlinedButton("Pegar", icon=ft.Icons.CONTENT_PASTE, on_click=self._paste, height=40)

        # --- Opciones
        self.format_picker = ft.SegmentedButton(
            selected=[s.audio_format],
            segments=[ft.Segment(value=k, label=k.upper()) for k in FORMATS],
            on_change=self._on_format,
            show_selected_icon=False,
        )
        self.format_desc = ft.Text(FORMATS[s.audio_format], size=13, color=MUTED)
        self.quality = ft.Dropdown(dense=True, 
            label="Calidad",
            value=s.audio_quality,
            width=220,
            options=[
                ft.DropdownOption(key="best", text="Mejor disponible"),
                ft.DropdownOption(key="320", text="320 kbps"),
                ft.DropdownOption(key="256", text="256 kbps"),
                ft.DropdownOption(key="192", text="192 kbps"),
                ft.DropdownOption(key="128", text="128 kbps"),
            ],
            on_select=self._on_quality,
        )
        self.quality_note = ft.Text("No aplica a formatos sin pérdida.", size=13, color=MUTED, visible=False)
        self.cover = ft.Switch(label="Incrustar portada", value=s.audio_cover, on_change=self._on_switch)
        self.metadata = ft.Switch(label="Agregar metadatos (título, artista, álbum)", value=s.audio_metadata, on_change=self._on_switch)

        options_card = card(
            ft.Column(
                spacing=16,
                controls=[
                    ft.ResponsiveRow(
                        spacing=24,
                        run_spacing=16,
                        controls=[
                            ft.Column(
                                col={"sm": 12, "md": 8},
                                spacing=10,
                                controls=[section_label("Formato"), self.format_picker, self.format_desc],
                            ),
                            ft.Column(
                                col={"sm": 12, "md": 4},
                                spacing=10,
                                controls=[section_label("Calidad"), self.quality, self.quality_note],
                            ),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                    ft.Row(wrap=True, spacing=32, controls=[self.cover, self.metadata]),
                ],
            )
        )

        # --- Resultados
        self.status = ft.Container(visible=False)
        self.error = error_text()
        self.results_title = ft.Text("", size=18, weight=ft.FontWeight.W_500)
        self.results_list = ft.Column(spacing=0)
        self.results = ft.Column(
            visible=False,
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[self.results_title],
                ),
                card(self.results_list, padding=0),
            ],
        )

        self.root = ft.Column(
            spacing=24,
            controls=[
                header("Descargar audio", "Enlace de YouTube o nombre de una canción para buscar."),
                ft.Row(spacing=10, controls=[self.query, paste_button, self.go_button]),
                options_card,
                self.status,
                self.error,
                self.results,
            ],
        )
        self._apply_format_rules()

    # ------------------------------------------------------------ opciones

    def options(self, music: bool = False) -> dict:
        """music=True: la canción viene de YouTube Music (sirve para recortar la portada)."""
        s = self.app.settings
        return {
            "kind": "audio",
            "format": s.audio_format,
            "quality": s.audio_quality,
            "cover": s.audio_cover,
            "metadata": s.audio_metadata,
            "music": music,
        }

    def _apply_format_rules(self) -> None:
        lossless = self.app.settings.audio_format in LOSSLESS
        self.quality.disabled = lossless
        self.quality_note.visible = lossless
        self.cover.disabled = self.app.settings.audio_format == "wav"  # WAV no admite portada

    def _on_format(self, e) -> None:
        self.app.settings.audio_format = e.control.selected[0]
        self.format_desc.value = FORMATS[self.app.settings.audio_format]
        self._apply_format_rules()
        self.app.settings.save()

    def _on_quality(self, e) -> None:
        self.app.settings.audio_quality = e.control.value or "best"
        self.app.settings.save()

    def _on_switch(self, e) -> None:
        self.app.settings.audio_cover = self.cover.value
        self.app.settings.audio_metadata = self.metadata.value
        self.app.settings.save()

    # ------------------------------------------------------------ búsqueda / enlace

    def _on_query_change(self, e=None) -> None:
        if ytdlp.is_url(self.query.value or ""):
            self.go_button.content, self.go_button.icon = "Descargar", ft.Icons.DOWNLOAD
        else:
            self.go_button.content, self.go_button.icon = "Buscar", ft.Icons.SEARCH

    async def _paste(self, e) -> None:
        text = await self.app.clipboard.get()
        if text:
            self.query.value = text.strip()
            self._on_query_change()
            self.app.page.update()

    def use_url(self, url: str) -> None:
        """Lo usa el aviso del portapapeles: rellena el campo y lo procesa."""
        self.query.value = url
        self._on_query_change()
        self._go()

    def _set_busy(self, text: str | None) -> None:
        self.status.visible = bool(text)
        self.status.content = loading_row(text) if text else None
        self.go_button.disabled = bool(text)

    def _show_error(self, message: str) -> None:
        self.error.value = message
        self.error.visible = bool(message)

    def _go(self, e=None) -> None:
        text = (self.query.value or "").strip()
        if not text:
            return
        self._show_error("")
        if ytdlp.is_url(text):
            self._set_busy("Analizando el enlace…")
            self.app.page.run_thread(self._probe_worker, text)
        else:
            self.results.visible = False
            where = " en YouTube Music" if self.app.settings.music_search else ""
            self._set_busy(f"Buscando “{text}”{where}…")
            self.app.page.run_thread(self._search_worker, text)

    # Lo que sigue corre en otro hilo (para que la ventana no se congele)

    def _probe_worker(self, url: str) -> None:
        try:
            kind, info = ytdlp.probe(url, self.app.settings)
        except ytdlp.YtdlpError as exc:
            ui_call(self.app.page, self._after_error, str(exc))
            return
        ui_call(self.app.page, self._after_probe, url, kind, info)

    def _search_worker(self, query: str) -> None:
        try:
            results = ytdlp.search(query, self.app.settings)
        except ytdlp.YtdlpError as exc:
            ui_call(self.app.page, self._after_error, str(exc))
            return
        ui_call(self.app.page, self._after_search, query, results)

    # Y esto vuelve al hilo de la interfaz

    def _after_error(self, message: str) -> None:
        self._set_busy(None)
        self._show_error(message)

    def _after_probe(self, url: str, kind: str, info) -> None:
        self._set_busy(None)
        music = ytdlp.is_music_url(url)
        if kind == "playlist":
            if not info.entries:
                self._show_error("La playlist está vacía o es privada")
                return
            PlaylistDialog(self.app, info, url, "audio", lambda: self.options(music), self.app.settings.audio_dir).open()
        else:
            self.app.queue.add(url, info, self.options(music), self.app.settings.audio_dir)
            self.query.value = ""
            self._on_query_change()
            toast(self.app.page, "Agregado a descargas")

    def _after_search(self, query: str, results: list[ytdlp.SearchResult]) -> None:
        self._set_busy(None)
        self.results_title.value = f"Resultados para “{query}”"
        self.results_list.controls = [self._result_row(r) for r in results] or [empty_state("No se encontró nada.")]
        self.results.visible = True

    def _result_row(self, r: ytdlp.SearchResult) -> ft.Control:
        if r.live:
            action: ft.Control = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12),
                content=ft.Text("En vivo", color=MUTED),
                tooltip="Las transmisiones en vivo no se pueden descargar",
            )
        else:
            action = ft.OutlinedButton("Descargar", icon=ft.Icons.DOWNLOAD)

            def add(e, r=r):
                self.app.queue.add(r.url, r.title, self.options(r.music), self.app.settings.audio_dir)
                row.controls[-1] = ft.Row(
                    spacing=6,
                    controls=[ft.Icon(ft.Icons.CHECK, color=OK, size=18), ft.Text("En descargas", color=OK, weight=ft.FontWeight.W_500)],
                )
                toast(self.app.page, "Agregado a descargas")

            action.on_click = add

        row = ft.Row(
            spacing=16,
            controls=[
                thumbnail(r.thumbnail, 104, 58, "EN VIVO" if r.live else r.duration),
                ft.Column(
                    expand=True,
                    spacing=4,
                    controls=[
                        ft.Text(r.title, weight=ft.FontWeight.W_500, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(r.channel, size=13, color=MUTED),
                    ],
                ),
                action,
            ],
        )
        return ft.Container(
            content=row,
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )
