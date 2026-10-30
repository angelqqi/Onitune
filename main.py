"""Punto de entrada de Onitune.

Para abrir la app:  python main.py
"""

import flet as ft

from onitune.core.paths import assets_dir
from onitune.ui.app import OnituneApp


def main(page: ft.Page) -> None:
    OnituneApp(page).start()


if __name__ == "__main__":
    ft.run(main, assets_dir=str(assets_dir()))
