"""Pantalla de primer arranque: descarga yt-dlp y ffmpeg."""

import time
from typing import Callable

import flet as ft

from ..core import deps, paths, ytdlp
from .common import ACCENT, ERR, MUTED, OK, C, ui_call


class Step:
    def __init__(self, title: str, description: str):
        self.icon = ft.Container(
            width=28,
            height=28,
            border_radius=14,
            border=ft.Border.all(2, ft.Colors.OUTLINE_VARIANT),
            alignment=ft.Alignment.CENTER,
        )
        self.title = ft.Text(title, weight=ft.FontWeight.W_500, color=MUTED)
        self.percent = ft.Text("", size=13, color=C.info)
        self.bar = ft.ProgressBar(value=0, bar_height=6, border_radius=3, color=ACCENT, visible=False)
        self.description = ft.Text(description, size=13, color=MUTED)
        self.root = ft.Row(
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                self.icon,
                ft.Column(
                    expand=True,
                    spacing=8,
                    controls=[
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[self.title, self.percent]),
                        self.bar,
                        self.description,
                    ],
                ),
            ],
        )

    def running(self) -> None:
        self.title.color = None
        self.icon.border = None
        self.icon.bgcolor = ft.Colors.with_opacity(0.16, C.info)
        self.icon.content = ft.Icon(ft.Icons.DOWNLOAD, size=16, color=C.info)
        self.bar.visible = True

    def progress(self, fraction, done: int, total: int) -> None:
        self.bar.value = fraction
        self.percent.value = f"{round(fraction * 100)}%" if fraction is not None else ytdlp.fmt_size(done)

    def finished(self) -> None:
        self.title.color = None
        self.icon.border = None
        self.icon.bgcolor = ft.Colors.with_opacity(0.16, OK)
        self.icon.content = ft.Icon(ft.Icons.CHECK, size=16, color=OK)
        self.bar.visible = False
        self.percent.value = ""

    def failed(self) -> None:
        self.icon.border = None
        self.icon.bgcolor = ft.Colors.with_opacity(0.16, ERR)
        self.icon.content = ft.Icon(ft.Icons.CLOSE, size=16, color=ERR)
        self.bar.visible = False


class SetupView:
    def __init__(self, app, on_done: Callable[[], None]):
        self.app = app
        self.on_done = on_done
        self.steps = {
            "yt-dlp": Step("Descargar yt-dlp", "El programa que habla con YouTube."),
            "ffmpeg": Step("Descargar ffmpeg", "Convierte el audio y une el video con el sonido."),
            "folders": Step("Crear carpetas Audio y Video", "Donde se guardarán las descargas."),
        }
        self.error = ft.Text("", color=ERR, visible=False)
        self.retry = ft.FilledButton("Reintentar", icon=ft.Icons.REFRESH, visible=False, on_click=lambda e: self.start())
        where = r"%LOCALAPPDATA%\Onitune" if paths.IS_WINDOWS else "~/.local/share/onitune"

        box = ft.Container(
            width=560,
            padding=36,
            border_radius=20,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            content=ft.Column(
                tight=True,
                spacing=28,
                controls=[
                    ft.Row(
                        spacing=14,
                        controls=[
                            ft.Image(src="/icon.png", width=56, height=56),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text("Preparando Onitune", size=24, weight=ft.FontWeight.BOLD),
                                    ft.Text("Primera configuración de la app. Solo ocurre una vez.", size=14, color=MUTED),
                                ],
                            ),
                        ],
                    ),
                    ft.Column(spacing=18, controls=[s.root for s in self.steps.values()]),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                        border_radius=12,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        content=ft.Text(
                            f"Se guardan dentro de la carpeta de la app ({where}). "
                            "No hace falta instalar nada ni permisos de administrador.",
                            size=13,
                            color=MUTED,
                        ),
                    ),
                    self.error,
                    ft.Row(alignment=ft.MainAxisAlignment.END, controls=[self.retry]),
                ],
            ),
        )
        self.root = ft.Container(expand=True, alignment=ft.Alignment.CENTER, padding=16, content=box)

    def start(self) -> None:
        self.error.visible = False
        self.retry.visible = False
        self.app.page.run_thread(self._worker)

    def _worker(self) -> None:
        page = self.app.page
        try:
            for name, download in (("yt-dlp", deps.download_ytdlp), ("ffmpeg", deps.download_ffmpeg)):
                step = self.steps[name]
                if name not in deps.missing():
                    ui_call(page, step.finished)
                    continue
                ui_call(page, step.running)
                last = [0.0]

                def progress(fraction, done, total, step=step):
                    now = time.monotonic()
                    if now - last[0] > 0.25 or fraction == 1:
                        last[0] = now
                        ui_call(page, step.progress, fraction, done, total)

                download(progress)
                ui_call(page, step.finished)

            folders = self.steps["folders"]
            for folder in (self.app.settings.audio_dir, self.app.settings.video_dir):
                paths.Path(folder).mkdir(parents=True, exist_ok=True)
            self.app.settings.save()
            ui_call(page, folders.finished)
        except Exception as exc:
            def fail():
                for step in self.steps.values():
                    if step.bar.visible:
                        step.failed()
                self.error.value = f"No se pudo completar: {exc}. Revisar la conexión a internet."
                self.error.visible = True
                self.retry.visible = True

            ui_call(page, fail)
            return
        time.sleep(0.6)
        ui_call(page, self.on_done)
