"""Pestaña Historial: buscar, filtrar, abrir, volver a descargar y borrar."""

import os
import unicodedata
from datetime import datetime, timedelta

import flet as ft

from ..core import proc, ytdlp
from ..core.history import HistoryEntry
from .common import MUTED, card, empty_state, header, kind_icon, toast

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _normalize(text: str) -> str:
    """Minúsculas y sin tildes, para que "cancion" encuentre "Canción"."""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _nice_date(when: datetime) -> str:
    today = datetime.now().date()
    hour = when.strftime("%H:%M")
    if when.date() == today:
        return f"Hoy, {hour}"
    if when.date() == today - timedelta(days=1):
        return f"Ayer, {hour}"
    text = f"{when.day} {MONTHS[when.month - 1]}"
    return text if when.year == today.year else f"{text} {when.year}"


class HistoryView:
    def __init__(self, app):
        self.app = app
        self.kind = "all"
        self.days = "all"

        self.summary = ft.Text("")
        self.search = ft.TextField(dense=True, 
            hint_text="Buscar por título",
            prefix_icon=ft.Icons.SEARCH,
            expand=True,
            border_radius=12,
            on_change=lambda e: self.refresh(),
        )
        self.kind_picker = ft.SegmentedButton(
            selected=["all"],
            show_selected_icon=False,
            segments=[
                ft.Segment(value="all", label="Todo"),
                ft.Segment(value="audio", label="Audio"),
                ft.Segment(value="video", label="Video"),
            ],
            on_change=self._on_kind,
        )
        self.date_picker = ft.Dropdown(dense=True, 
            value="all",
            width=200,
            options=[
                ft.DropdownOption(key="all", text="Cualquier fecha"),
                ft.DropdownOption(key="0", text="Hoy"),
                ft.DropdownOption(key="7", text="Últimos 7 días"),
                ft.DropdownOption(key="30", text="Últimos 30 días"),
            ],
            on_select=self._on_date,
        )
        self.list = ft.Column(spacing=0)

        self.root = ft.Column(
            spacing=12,
            controls=[
                header("Historial", self.summary),
                ft.ResponsiveRow(
                    spacing=10,
                    run_spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(col={"sm": 12, "lg": 6}, content=ft.Row(controls=[self.search])),
                        ft.Row(col={"sm": 12, "lg": 6}, spacing=10, controls=[self.kind_picker, self.date_picker]),
                    ],
                ),
                card(self.list, padding=0),
            ],
        )
        self.refresh()

    def _on_kind(self, e) -> None:
        self.kind = e.control.selected[0]
        self.refresh()

    def _on_date(self, e) -> None:
        self.days = e.control.value or "all"
        self.refresh()

    def _visible_entries(self) -> list[HistoryEntry]:
        query = _normalize((self.search.value or "").strip())
        now = datetime.now()
        result = []
        for entry in self.app.history.entries:
            if self.kind != "all" and entry.kind != self.kind:
                continue
            if self.days != "all":
                limit = now.date() - timedelta(days=int(self.days))
                if entry.when.date() < limit:
                    continue
            if query and query not in _normalize(entry.title):
                continue
            result.append(entry)
        return result

    def refresh(self) -> None:
        total = len(self.app.history.entries)
        self.summary.value = f"{total} descarga{'s' if total != 1 else ''} guardada{'s' if total != 1 else ''}"
        entries = self._visible_entries()
        if entries:
            self.list.controls = [self._row(e) for e in entries[:300]]
        elif total:
            self.list.controls = [empty_state("No hay descargas que coincidan con el filtro.")]
        else:
            self.list.controls = [empty_state("Todavía no hay descargas.")]

    def _row(self, entry: HistoryEntry) -> ft.Control:
        exists = entry.file_exists
        details = [entry.label, ytdlp.fmt_size(entry.size), _nice_date(entry.when)]
        if not exists:
            details.append("archivo movido o borrado")
        return ft.Container(
            padding=ft.Padding.only(left=16, right=8, top=8, bottom=8),
            border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            content=ft.Row(
                spacing=14,
                controls=[
                    kind_icon(entry.kind, size=18),
                    ft.Column(
                        expand=True,
                        spacing=3,
                        controls=[
                            ft.Text(entry.title, weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(" · ".join(d for d in details if d), size=12, color=MUTED),
                        ],
                    ),
                    ft.IconButton(
                        ft.Icons.PLAY_CIRCLE_OUTLINE,
                        tooltip="Abrir archivo" if exists else "El archivo ya no está",
                        disabled=not exists,
                        on_click=lambda e: proc.open_path(entry.filepath),
                    ),
                    ft.IconButton(
                        ft.Icons.FOLDER_OPEN_OUTLINED,
                        tooltip="Abrir carpeta",
                        on_click=lambda e: self._open_folder(entry),
                    ),
                    ft.IconButton(ft.Icons.REFRESH, tooltip="Volver a descargar", on_click=lambda e: self._again(entry)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Borrar del historial", on_click=lambda e: self._ask_delete(entry)),
                ],
            ),
        )

    def _open_folder(self, entry: HistoryEntry) -> None:
        if entry.file_exists:
            proc.show_in_folder(entry.filepath)
        else:
            folder = os.path.dirname(entry.filepath) if entry.filepath else ""
            if folder and os.path.isdir(folder):
                proc.open_path(folder)
            else:
                toast(self.app.page, "La carpeta ya no existe")

    def _again(self, entry: HistoryEntry) -> None:
        s = self.app.settings
        folder = os.path.dirname(entry.filepath) if entry.filepath else ""
        if not folder or not os.path.isdir(folder):
            folder = s.audio_dir if entry.kind == "audio" else s.video_dir
        self.app.queue.add(entry.url, entry.title, entry.options, folder)
        toast(self.app.page, "Agregado de nuevo a descargas")

    def _ask_delete(self, entry: HistoryEntry) -> None:
        also_file = ft.Checkbox(label="Borrar también el archivo del disco", value=False, visible=entry.file_exists)

        def confirm(e):
            self.app.page.pop_dialog()
            self.app.history.delete(entry.id, delete_file=bool(also_file.value))
            toast(self.app.page, "Archivo borrado" if also_file.value else "Quitado del historial")

        self.app.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("¿Quitar del historial?"),
                content=ft.Column(tight=True, spacing=12, controls=[ft.Text(entry.title, color=MUTED), also_file]),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: self.app.page.pop_dialog()),
                    ft.FilledButton("Quitar", on_click=confirm),
                ],
            )
        )
