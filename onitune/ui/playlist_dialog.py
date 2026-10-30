"""Ventana para elegir qué videos de una playlist añadir a la cola."""

import os
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

import flet as ft

from ..core import ytdlp
from .common import MUTED, toast


def _video_id_in(url: str) -> Optional[str]:
    """Si el enlace es watch?v=XXX&list=YYY, devuelve XXX."""
    try:
        return parse_qs(urlparse(url).query).get("v", [None])[0]
    except ValueError:
        return None


class PlaylistDialog:
    def __init__(
        self,
        app,
        info: ytdlp.PlaylistInfo,
        source_url: str,
        kind: str,
        get_options: Callable[[], dict],
        base_dir: str,
        extra: Optional[ft.Control] = None,
    ):
        self.app = app
        self.info = info
        self.kind = kind
        self.get_options = get_options
        self.base_dir = base_dir

        # Si el enlace venía de un video concreto dentro de la playlist,
        # marcamos solo ese; si no, marcamos todos.
        only = _video_id_in(source_url)
        if only and not any(e.id == only for e in info.entries):
            only = None

        self.checks: list[tuple[ft.Checkbox, ytdlp.PlaylistEntry]] = []
        rows = []
        for n, entry in enumerate(info.entries, start=1):
            check = ft.Checkbox(value=(entry.id == only) if only else True, on_change=self._refresh)
            self.checks.append((check, entry))
            rows.append(
                ft.Row(
                    spacing=12,
                    controls=[
                        check,
                        ft.Text(str(n), size=12, color=MUTED, width=24),
                        ft.Text(entry.title, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(entry.duration, size=12, color=MUTED),
                    ],
                )
            )

        self.add_button = ft.FilledButton(on_click=self._add)
        where = "Audio" if kind == "audio" else "Video"
        folder_note = f"Se guardará en {where}/{ytdlp.safe_folder_name(info.title)}" if app.settings.playlist_subfolder else f"Se guardará en {where}"

        content_controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.TextButton("Seleccionar todo", on_click=lambda e: self._set_all(True)),
                    ft.TextButton("Ninguno", on_click=lambda e: self._set_all(False)),
                ]
            ),
            ft.Container(
                height=360,
                border=ft.Border(
                    top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                ),
                content=ft.ListView(controls=rows, spacing=2, padding=ft.Padding.symmetric(vertical=6)),
            ),
        ]
        if extra:
            content_controls.append(extra)
        content_controls.append(ft.Text(folder_note, size=13, color=MUTED))

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Column(
                spacing=2,
                tight=True,
                controls=[
                    ft.Text(info.title, size=20, weight=ft.FontWeight.W_500),
                    ft.Text(f"Playlist · {len(info.entries)} videos", size=13, color=MUTED),
                ],
            ),
            content=ft.Column(width=600, tight=True, spacing=10, controls=content_controls),
            actions=[ft.TextButton("Cancelar", on_click=lambda e: self.app.page.pop_dialog()), self.add_button],
        )
        self._refresh()

    def open(self) -> None:
        self.app.page.show_dialog(self.dialog)

    def _selected(self) -> list[ytdlp.PlaylistEntry]:
        return [entry for check, entry in self.checks if check.value]

    def _refresh(self, e=None) -> None:
        n = len(self._selected())
        self.add_button.content = f"Descargar {n} video{'s' if n != 1 else ''}"
        self.add_button.disabled = n == 0

    def _set_all(self, value: bool) -> None:
        for check, _ in self.checks:
            check.value = value
        self._refresh()

    def _add(self, e) -> None:
        entries = self._selected()
        options = self.get_options()
        out_dir = self.base_dir
        if self.app.settings.playlist_subfolder:
            out_dir = os.path.join(out_dir, ytdlp.safe_folder_name(self.info.title))
        for entry in entries:
            self.app.queue.add(entry.url, entry.title, options, out_dir)
        self.app.page.pop_dialog()
        toast(self.app.page, f"{len(entries)} video{'s' if len(entries) != 1 else ''} agregado{'s' if len(entries) != 1 else ''} a descargas")
