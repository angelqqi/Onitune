"""Pestaña Cola: progreso de cada descarga y botones para controlarlas."""

import os
from typing import Optional

import flet as ft

from ..core import proc
from ..core.queue import DONE, DOWNLOADING, ERROR, PAUSED, PROCESSING, WAITING, DownloadItem
from .common import ERR, MUTED, OK, C, card, empty_state, header, kind_icon


def status_text(status: str) -> tuple[str, str]:
    """Texto y color de cada estado (el color depende del tema)."""
    return {
        WAITING: ("En espera", MUTED),
        DOWNLOADING: ("Descargando", C.info),
        PROCESSING: ("Procesando…", C.info),
        PAUSED: ("Pausado", C.warn),
        ERROR: ("Error", ERR),
        DONE: ("Completado", OK),
    }.get(status, ("", MUTED))


class QueueCard:
    """La tarjeta de una descarga. Se actualiza sin redibujar toda la lista."""

    def __init__(self, view: "QueueView", item: DownloadItem):
        self.view = view
        self.item_id = item.id
        self.title = ft.Text(weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)
        self.status = ft.Text(size=13, weight=ft.FontWeight.W_500)
        self.bar = ft.ProgressBar(bar_height=6, border_radius=3)
        self.detail = ft.Text(size=12, color=MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        self.actions = ft.Row(spacing=0)
        self.shown_status = ""
        self.root = card(
            ft.Row(
                spacing=16,
                controls=[
                    kind_icon(item.kind),
                    ft.Column(
                        expand=True,
                        spacing=6,
                        controls=[ft.Row(controls=[self.title, self.status]), self.bar, self.detail],
                    ),
                    self.actions,
                ],
            ),
            padding=10,
        )
        self.refresh(item)

    def refresh(self, item: DownloadItem) -> None:
        label, color = status_text(item.status)
        pct = f" · {round((item.fraction or 0) * 100)}%" if item.status in (DOWNLOADING, PAUSED) and item.fraction else ""
        self.title.value = item.title
        self.status.value, self.status.color = label + pct, color

        self.bar.visible = item.status in (DOWNLOADING, PROCESSING, PAUSED)
        self.bar.color = C.warn if item.status == PAUSED else None
        # Barra "infinita" mientras procesa o si aún no se sabe el tamaño
        self.bar.value = None if item.status == PROCESSING or item.fraction is None else item.fraction

        parts = [item.label]
        if item.status == DOWNLOADING:
            parts += [x for x in (item.speed, f"quedan {item.eta}" if item.eta else "") if x]
        elif item.status == WAITING:
            parts.append("Esperando turno")
        elif item.status == ERROR:
            parts.append(item.error)
        elif item.status == DONE and item.filepath:
            parts.append(os.path.basename(item.filepath))
        self.detail.value = " · ".join(parts)
        self.detail.color = ERR if item.status == ERROR else MUTED

        if item.status != self.shown_status:  # los botones solo cambian con el estado
            self.shown_status = item.status
            self.actions.controls = self._buttons(item)

    def _buttons(self, item: DownloadItem) -> list[ft.Control]:
        q = self.view.app.queue
        i = item.id
        b = []
        if item.status in (DOWNLOADING, PROCESSING, WAITING):
            b.append(ft.IconButton(ft.Icons.PAUSE, tooltip="Pausar", on_click=lambda e: q.pause(i)))
        if item.status == PAUSED:
            b.append(ft.IconButton(ft.Icons.PLAY_ARROW, tooltip="Reanudar", on_click=lambda e: q.resume(i)))
        if item.status == ERROR:
            b.append(ft.IconButton(ft.Icons.REFRESH, tooltip="Reintentar", on_click=lambda e: q.retry(i)))
        if item.status == DONE:
            path = item.filepath
            b.append(ft.IconButton(ft.Icons.PLAY_CIRCLE_OUTLINE, tooltip="Abrir archivo", on_click=lambda e: path and proc.open_path(path)))
            b.append(
                ft.IconButton(
                    ft.Icons.FOLDER_OPEN_OUTLINED,
                    tooltip="Abrir carpeta",
                    on_click=lambda e: proc.show_in_folder(path or item.out_dir),
                )
            )
        else:
            b.append(ft.IconButton(ft.Icons.CLOSE, tooltip="Cancelar", on_click=lambda e: q.cancel(i)))
        return b


class QueueView:
    def __init__(self, app):
        self.app = app
        self.cards: dict[str, QueueCard] = {}

        self.summary = ft.Text("")
        self.parallel = ft.Text(str(app.settings.max_parallel), weight=ft.FontWeight.W_500, width=20, text_align=ft.TextAlign.CENTER)
        self.pause_all = ft.OutlinedButton("Pausar todo", icon=ft.Icons.PAUSE, on_click=self._toggle_all)
        self.list = ft.Column(spacing=10)

        self.root = ft.Column(
            spacing=12,
            controls=[
                header("Descargas", self.summary),
                ft.Row(
                    wrap=True,
                    spacing=10,
                    run_spacing=10,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.only(left=16, right=4),
                            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=24,
                            content=ft.Row(
                                spacing=2,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text("Descargas a la vez"),
                                    ft.IconButton(ft.Icons.REMOVE, tooltip="Menos", on_click=lambda e: self._parallel(-1)),
                                    self.parallel,
                                    ft.IconButton(ft.Icons.ADD, tooltip="Más", on_click=lambda e: self._parallel(+1)),
                                ],
                            ),
                        ),
                        ft.Row(
                            spacing=10,
                            tight=True,
                            controls=[
                                self.pause_all,
                                ft.OutlinedButton("Quitar completadas", icon=ft.Icons.DONE_ALL, on_click=lambda e: app.queue.clear_done()),
                            ],
                        ),
                    ],
                ),
                self.list,
                ft.Text(
                    "Las descargas pendientes se guardan: continúan al volver a abrir la app.",
                    size=13,
                    color=MUTED,
                ),
            ],
        )
        self.rebuild()

    def _parallel(self, delta: int) -> None:
        self.app.queue.set_parallel(self.app.settings.max_parallel + delta)
        self.parallel.value = str(self.app.settings.max_parallel)

    def _toggle_all(self, e) -> None:
        q = self.app.queue
        if q.count(WAITING, DOWNLOADING, PROCESSING):
            q.pause_all()
        else:
            q.resume_all()

    def on_queue_change(self, item: Optional[DownloadItem]) -> None:
        """La cola cambió (se llama en el hilo de la interfaz)."""
        card_ = self.cards.get(item.id) if item else None
        if card_ is not None and item in self.app.queue.items:
            card_.refresh(item)  # solo cambió una descarga: actualizamos su tarjeta
        else:
            self.rebuild()
        self._update_header()

    def rebuild(self) -> None:
        items = list(self.app.queue.items)
        cards = {}
        for item in items:
            c = self.cards.get(item.id) or QueueCard(self, item)
            c.refresh(item)
            cards[item.id] = c
        self.cards = cards
        self.list.controls = [cards[i.id].root for i in items] or [card(empty_state("No hay descargas. Se pueden agregar desde Audio o Video."))]
        self._update_header()

    def _update_header(self) -> None:
        q = self.app.queue
        parts = []
        for status, word in ((DOWNLOADING, "descargando"), (PROCESSING, "procesando"), (WAITING, "en espera"), (PAUSED, "en pausa")):
            n = q.count(status)
            if n:
                parts.append(f"{n} {word}")
        errors = q.count(ERROR)
        if errors:
            parts.append(f"{errors} con error{'es' if errors != 1 else ''}")
        self.summary.value = " · ".join(parts) or "No hay descargas pendientes"
        active = q.count(WAITING, DOWNLOADING, PROCESSING)
        paused = q.count(PAUSED)
        self.pause_all.content = "Pausar todo" if active or not paused else "Reanudar todo"
        self.pause_all.icon = ft.Icons.PAUSE if active or not paused else ft.Icons.PLAY_ARROW
        self.pause_all.disabled = not active and not paused
