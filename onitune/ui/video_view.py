"""Pestaña Video: analizar un enlace y elegir resolución, formato y subtítulos."""

from typing import Optional

import flet as ft

from ..core import ytdlp
from .common import MUTED, OK, card, empty_state, error_text, header, loading_row, section_label, thumbnail, toast, ui_call
from .playlist_dialog import PlaylistDialog

CONTAINERS = {
    "mp4": "Se reproduce en todo: Windows, celulares, televisores.",
    "mkv": "Guarda la calidad original sin convertir. Algunos televisores y celulares no lo abren.",
}

# Para playlists no analizamos cada video: ofrecemos calidades típicas
GENERIC_RES = [(0, "Mejor disponible"), (2160, "2160p 4K"), (1440, "1440p"), (1080, "1080p"), (720, "720p"), (480, "480p"), (360, "360p")]


class VideoView:
    def __init__(self, app):
        self.app = app
        self.info: Optional[ytdlp.VideoInfo] = None
        self.res: int = 0  # 0 = la mejor
        self.res_chips: list[ft.Chip] = []

        self.url = ft.TextField(dense=True, 
            hint_text="https://www.youtube.com/watch?v=…",
            prefix_icon=ft.Icons.LINK,
            expand=True,
            border_radius=12,
            on_submit=self._analyze,
        )
        self.analyze_button = ft.FilledButton("Analizar", icon=ft.Icons.SEARCH, on_click=self._analyze, height=40)
        paste_button = ft.OutlinedButton("Pegar", icon=ft.Icons.CONTENT_PASTE, on_click=self._paste, height=40)

        self.status = ft.Container(visible=False)
        self.error = error_text()
        self.details = ft.Column(spacing=24, visible=False)
        self.empty = card(empty_state("Las calidades disponibles aparecerán aquí después de analizar un enlace."))

        self.root = ft.Column(
            spacing=24,
            controls=[
                header("Descargar video", "Al analizar un enlace se muestran las calidades disponibles del video."),
                ft.Row(spacing=10, controls=[self.url, paste_button, self.analyze_button]),
                self.status,
                self.error,
                self.empty,
                self.details,
            ],
        )

    # ------------------------------------------------------------ entrada

    async def _paste(self, e) -> None:
        text = await self.app.clipboard.get()
        if text:
            self.url.value = text.strip()
            self.app.page.update()

    def use_url(self, url: str) -> None:
        """Lo usa el aviso del portapapeles."""
        self.url.value = url
        self._analyze()

    def _set_busy(self, text: Optional[str]) -> None:
        self.status.visible = bool(text)
        self.status.content = loading_row(text) if text else None
        self.analyze_button.disabled = bool(text)

    def _analyze(self, e=None) -> None:
        url = (self.url.value or "").strip()
        self.error.visible = False
        if not ytdlp.is_url(url):
            self.error.value, self.error.visible = "El enlace debe empezar por https://", True
            return
        self.details.visible = False
        self.empty.visible = False
        if ytdlp.is_playlist_url(url) and "v=" not in url:
            self._set_busy("Leyendo la playlist…")
            self.app.page.run_thread(self._playlist_worker, url)
        else:
            self._set_busy("Leyendo los formatos del video…")
            self.app.page.run_thread(self._analyze_worker, url)

    # ------------------------------------------------------------ hilos

    def _analyze_worker(self, url: str) -> None:
        try:
            info = ytdlp.analyze_video(url, self.app.settings)
        except ytdlp.YtdlpError as exc:
            ui_call(self.app.page, self._after_error, str(exc))
            return
        ui_call(self.app.page, self._show_info, info)

    def _playlist_worker(self, url: str) -> None:
        try:
            kind, info = ytdlp.probe(url, self.app.settings)
        except ytdlp.YtdlpError as exc:
            ui_call(self.app.page, self._after_error, str(exc))
            return
        if kind != "playlist":
            self._analyze_worker(url)
            return
        ui_call(self.app.page, self._show_playlist, url, info)

    def _after_error(self, message: str) -> None:
        self._set_busy(None)
        self.error.value, self.error.visible = message, True
        self.empty.visible = True

    # ------------------------------------------------------------ playlist

    def _show_playlist(self, url: str, info: ytdlp.PlaylistInfo) -> None:
        self._set_busy(None)
        self.empty.visible = True
        if not info.entries:
            self.error.value, self.error.visible = "La playlist está vacía o es privada", True
            return
        s = self.app.settings
        res_pick = ft.Dropdown(dense=True, 
            label="Calidad máxima",
            value="0",
            width=220,
            options=[ft.DropdownOption(key=str(r), text=t) for r, t in GENERIC_RES],
        )
        container_pick = ft.SegmentedButton(
            selected=[s.video_container],
            segments=[ft.Segment(value="mp4", label="MP4"), ft.Segment(value="mkv", label="MKV")],
            show_selected_icon=False,
        )

        def options() -> dict:
            return {
                "kind": "video",
                "res": int(res_pick.value or 0) or None,
                "container": container_pick.selected[0],
                "subs": False,
                "music": ytdlp.is_music_url(url),  # para recortar la portada
            }

        extra = ft.Row(spacing=16, controls=[res_pick, container_pick])
        PlaylistDialog(self.app, info, url, "video", options, s.video_dir, extra=extra).open()

    # ------------------------------------------------------------ un video

    def _show_info(self, info: ytdlp.VideoInfo) -> None:
        self._set_busy(None)
        self.info = info
        s = self.app.settings

        # Resolución: "Mejor" + las que tiene el video
        self.res = 0
        self.res_chips = []
        best_detail = info.resolutions[0].label if info.resolutions else ""
        choices = [(0, "Mejor", f"{best_detail} · la más alta" if best_detail else "la más alta")]
        choices += [(r.res, r.label, r.detail) for r in info.resolutions]
        for value, label, detail in choices:
            chip = ft.Chip(
                label=ft.Column(
                    spacing=0,
                    tight=True,
                    controls=[ft.Text(label, weight=ft.FontWeight.BOLD), ft.Text(detail or " ", size=11, color=MUTED)],
                ),
                selected=value == 0,
                show_checkmark=False,
                data=value,
                on_select=self._on_res,
            )
            self.res_chips.append(chip)

        # Formato
        self.container = ft.SegmentedButton(
            selected=[s.video_container],
            segments=[ft.Segment(value="mp4", label="MP4"), ft.Segment(value="mkv", label="MKV")],
            show_selected_icon=False,
            on_change=self._on_container,
        )
        self.container_desc = ft.Text(CONTAINERS[s.video_container], size=13, color=MUTED)

        # Subtítulos
        has_subs = bool(info.subtitles)
        self.subs = ft.Switch(label="Descargar subtítulos", value=s.video_subs and has_subs, disabled=not has_subs, on_change=self._on_subs)
        default_sub = next((x for x in info.subtitles if x.code.startswith("es") and not x.auto), None) or (
            info.subtitles[0] if has_subs else None
        )
        self.sub_lang = ft.Dropdown(dense=True, 
            label="Idioma",
            width=320,
            value=f"{default_sub.code}|{int(default_sub.auto)}" if default_sub else None,
            options=[ft.DropdownOption(key=f"{x.code}|{int(x.auto)}", text=x.label) for x in info.subtitles],
            on_select=self._update_summary,
        )
        self.sub_mode = ft.RadioGroup(
            value="embed" if s.video_subs_embed else "file",
            on_change=self._on_sub_mode,
            content=ft.Row(
                controls=[
                    ft.Radio(value="embed", label="Incrustar en el video"),
                    ft.Radio(value="file", label="Archivo .srt aparte"),
                ]
            ),
        )
        self.sub_box = ft.Column(spacing=8, visible=self.subs.value, controls=[self.sub_lang, self.sub_mode])
        subs_section = [section_label("Subtítulos"), self.subs, self.sub_box]
        if not has_subs:
            subs_section.append(ft.Text("Este video no tiene subtítulos.", size=13, color=MUTED))

        self.summary = ft.Text("", weight=ft.FontWeight.W_500)
        found = f"{len(info.resolutions)} calidades encontradas"
        if has_subs:
            found += f" · subtítulos en {len(info.subtitles)} idioma{'s' if len(info.subtitles) != 1 else ''}"

        self.details.controls = [
            card(
                ft.Row(
                    spacing=12,
                    controls=[
                        thumbnail(info.thumbnail, 224, 126, info.duration),
                        ft.Column(
                            expand=True,
                            spacing=6,
                            controls=[
                                ft.Text(info.title, size=18, weight=ft.FontWeight.W_500),
                                ft.Text(" · ".join(x for x in (info.channel, info.duration) if x), size=14, color=MUTED),
                                ft.Row(spacing=6, controls=[ft.Icon(ft.Icons.CHECK, size=16, color=OK), ft.Text(found, size=13, color=OK)]),
                            ],
                        ),
                    ],
                ),
                padding=16,
            ),
            card(
                ft.Column(
                    spacing=24,
                    controls=[
                        ft.Column(
                            spacing=10,
                            controls=[
                                section_label("Resolución"),
                                ft.Row(wrap=True, spacing=8, run_spacing=8, controls=self.res_chips),
                                ft.Text(
                                    "Solo aparecen las calidades que este video tiene de verdad. Los tamaños son aproximados.",
                                    size=13,
                                    color=MUTED,
                                ),
                            ],
                        ),
                        ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                        ft.ResponsiveRow(
                            spacing=40,
                            run_spacing=24,
                            controls=[
                                ft.Column(col={"sm": 12, "md": 5}, spacing=10, controls=[section_label("Formato"), self.container, self.container_desc]),
                                ft.Column(col={"sm": 12, "md": 7}, spacing=10, controls=subs_section),
                            ],
                        ),
                    ],
                )
            ),
            card(
                ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Column(
                            expand=True,
                            spacing=4,
                            controls=[self.summary, ft.Text(f"Se guardará en: {s.video_dir}", size=12, color=MUTED)],
                        ),
                        ft.FilledButton("Descargar", icon=ft.Icons.DOWNLOAD, on_click=self._add, height=40),
                    ],
                ),
                padding=16,
            ),
        ]
        self.details.visible = True
        self._update_summary()

    # ------------------------------------------------------------ cambios

    def _on_res(self, e) -> None:
        self.res = e.control.data
        for chip in self.res_chips:
            chip.selected = chip.data == self.res
        self._update_summary()

    def _on_container(self, e) -> None:
        self.app.settings.video_container = e.control.selected[0]
        self.container_desc.value = CONTAINERS[self.app.settings.video_container]
        self.app.settings.save()
        self._update_summary()

    def _on_subs(self, e) -> None:
        self.app.settings.video_subs = self.subs.value
        self.sub_box.visible = self.subs.value
        self.app.settings.save()
        self._update_summary()

    def _on_sub_mode(self, e) -> None:
        self.app.settings.video_subs_embed = self.sub_mode.value == "embed"
        self.app.settings.save()

    def options(self) -> dict:
        s = self.app.settings
        opts = {"kind": "video", "res": self.res or None, "container": s.video_container, "subs": False,
                "music": self.info.music if self.info else False}
        if self.subs.value and self.sub_lang.value:
            code, auto = self.sub_lang.value.split("|")
            opts.update(subs=True, sub_lang=code, sub_auto=auto == "1", subs_embed=self.sub_mode.value == "embed")
        return opts

    def _update_summary(self, e=None) -> None:
        self.summary.value = ytdlp.describe_options(self.options())

    def _add(self, e) -> None:
        if not self.info:
            return
        self.app.queue.add(self.info.url, self.info.title, self.options(), self.app.settings.video_dir)
        toast(self.app.page, "Agregado a descargas")
