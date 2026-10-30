"""Piezas pequeñas que usan varias pantallas."""

from typing import Callable

import flet as ft

from . import themes

# Colores que cambian solos con el tema (son "roles" del tema de Flet)
ACCENT = ft.Colors.PRIMARY
OK = ft.Colors.TERTIARY  # en themes.build(), tertiary = verde de "completado"
ERR = ft.Colors.ERROR
MUTED = ft.Colors.ON_SURFACE_VARIANT


class _ThemeColors:
    """Colores del tema actual que Flet no tiene como "rol".

    Se leen al construir la pantalla (C.info, C.warn). Al cambiar de tema
    la app vuelve a construir las pestañas, así que siempre están al día.
    """

    palette: themes.Palette = themes.get(themes.DEFAULT)

    @property
    def info(self) -> str:
        return self.palette.info

    @property
    def warn(self) -> str:
        return self.palette.warn


C = _ThemeColors()


def ui_call(page: ft.Page, fn: Callable, *args) -> None:
    """Ejecuta `fn` en el hilo de la interfaz y refresca la pantalla.

    Hay que usarlo siempre que otro hilo (una descarga, una búsqueda...)
    quiera cambiar algo que se ve en pantalla.
    """

    async def _run():
        fn(*args)
        page.update()

    try:
        page.run_task(_run)
    except Exception:
        pass  # la ventana ya se cerró


def toast(page: ft.Page, message: str) -> None:
    """Mensaje corto abajo de la ventana."""
    page.show_dialog(ft.SnackBar(content=ft.Text(message), duration=ft.Duration(milliseconds=2500)))


def header(title: str, subtitle: str | ft.Text) -> ft.Column:
    sub = subtitle if isinstance(subtitle, ft.Text) else ft.Text(subtitle)
    sub.color = MUTED
    sub.size = 13
    return ft.Column(
        spacing=4,
        controls=[ft.Text(title, size=22, weight=ft.FontWeight.BOLD), sub],
    )


def section_label(text: str) -> ft.Text:
    return ft.Text(text.upper(), size=12, weight=ft.FontWeight.W_500, color=MUTED, style=ft.TextStyle(letter_spacing=1))


def card(content: ft.Control, padding: int = 14) -> ft.Container:
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=12,
    )


def kind_icon(kind: str, size: int = 20) -> ft.Container:
    """Cuadradito con el icono de audio o video."""
    return ft.Container(
        content=ft.Icon(ft.Icons.MUSIC_NOTE if kind == "audio" else ft.Icons.MOVIE_OUTLINED, size=size, color=MUTED),
        width=44,
        height=44,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        alignment=ft.Alignment.CENTER,
    )


def thumbnail(src: str, width: int, height: int, duration: str = "") -> ft.Stack:
    """Miniatura de YouTube con la duración en la esquina."""
    placeholder = ft.Container(
        width=width,
        height=height,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_radius=10,
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=MUTED),
    )
    layers: list[ft.Control] = [placeholder]
    if src:
        layers.append(
            ft.Image(src=src, width=width, height=height, fit=ft.BoxFit.COVER, border_radius=10, error_content=placeholder)
        )
    if duration:
        layers.append(
            ft.Container(
                right=6,
                bottom=6,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=6,
                bgcolor="#C8000000",
                content=ft.Text(duration, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
            )
        )
    return ft.Stack(width=width, height=height, controls=layers)


def empty_state(text: str) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=28, horizontal=24),
        alignment=ft.Alignment.CENTER,
        content=ft.Text(text, color=MUTED, text_align=ft.TextAlign.CENTER),
    )


def loading_row(text: str) -> ft.Row:
    return ft.Row(
        spacing=14,
        controls=[ft.ProgressRing(width=20, height=20, stroke_width=2), ft.Text(text, color=MUTED)],
    )


def error_text() -> ft.Text:
    return ft.Text("", color=ERR, visible=False)
