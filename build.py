"""Crea lo que se publica de Onitune con `flet pack`.

Uso:   python build.py
Resultado en dist/:
  - Onitune.exe                  un solo archivo (Linux: Onitune)
  - Onitune-X.Y.Z-windows.zip    versión en carpeta (abre más rápido)
  - Onitune-Setup-X.Y.Z.exe      instalador (necesita Inno Setup)
  - SHA256SUMS.txt               huellas de todo lo anterior

Necesita:  pip install -r requirements-build.txt  (con Python 3.13; en 3.15 flet-cli no se instala)
           winget install JRSoftware.InnoSetup  (solo para el instalador)

`flet pack` usa PyInstaller por dentro, mete la ventana de Flet en el
ejecutable y le pone nuestro nombre e icono (también en la barra de tareas).
yt-dlp y ffmpeg NO van dentro: la app los descarga sola la primera vez, así
yt-dlp se puede actualizar sin volver a crear el ejecutable.
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from onitune import APP_NAME, APP_VERSION

ROOT = Path(__file__).resolve().parent
IS_WINDOWS = sys.platform == "win32"

# Módulos que están instalados para desarrollar pero la app no usa al ejecutarse.
# Sin esto el ejecutable pesaba más del doble.
EXCLUDE = ["PIL", "yaml", "flet.testing", "flet_cli"]


DIST = ROOT / "dist"
FOLDER_DIST = ROOT / "build" / "carpeta"  # aquí queda la versión "en carpeta"

# Inno Setup (crea el instalador). winget lo instala en la carpeta del usuario.
ISCC_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
]


def pack(onedir: bool, distpath: Path) -> None:
    """Empaqueta la app con `flet pack`: un solo archivo o una carpeta (onedir)."""
    flet = Path(sys.executable).parent / ("flet.exe" if IS_WINDOWS else "flet")
    args = [
        str(flet), "pack", "main.py",
        "--distpath", str(distpath),
        "--name", APP_NAME,
        "--icon", "assets/icon.ico" if IS_WINDOWS else "assets/icon.png",
        "--product-name", APP_NAME,
        "--file-description", f"{APP_NAME} - descarga audio y video de YouTube",
        "--product-version", APP_VERSION,
        "--file-version", f"{APP_VERSION}.0",
        "--company-name", "angelqqi",
        "--copyright", "Copyright (c) 2026 angelqqi - Licencia MIT",
        "--add-data", "assets:assets", "LICENSE:.", "THIRD_PARTY_LICENSES.md:.",
        "-y",
    ]
    if onedir:
        args.append("--onedir")
    args.append("--")  # lo que sigue va directo a PyInstaller
    for module in EXCLUDE:
        args += ["--exclude-module", module]
    print(" ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def make_installer() -> None:
    """Crea el instalador con Inno Setup a partir de la versión en carpeta."""
    iscc = next((p for p in ISCC_PATHS if p.is_file()), None)
    if not iscc:
        print("\nAVISO: no se encontró Inno Setup; no se crea el instalador.")
        print("       Instálalo con:  winget install JRSoftware.InnoSetup")
        return
    subprocess.run(
        [
            str(iscc), "/Q",
            f"/DAppVersion={APP_VERSION}",
            f"/DSourceDir={FOLDER_DIST / APP_NAME}",
            f"/DOutputDir={DIST}",
            str(ROOT / "installer" / "onitune.iss"),
        ],
        check=True,
    )


def clean(folder: Path) -> None:
    """Borra la carpeta de un build anterior.

    Si un archivo está bloqueado (app abierta o antivirus revisándolo) se
    detiene: así no se cuelan archivos viejos en SHA256SUMS.txt ni en la Release.
    """
    if not folder.exists():
        return
    try:
        shutil.rmtree(folder)
    except OSError as error:
        sys.exit(
            f"\nERROR: no se pudo borrar {folder}\n  {error}\n"
            "Cierra Onitune (o espera a que el antivirus termine) y vuelve a intentarlo."
        )


def main() -> None:
    clean(DIST)

    # 1. Un solo archivo: Onitune.exe (se descomprime solo cada vez que se abre)
    pack(onedir=False, distpath=DIST)

    if IS_WINDOWS:
        # 2. Versión en carpeta (abre más rápido) → se reparte en un .zip
        clean(FOLDER_DIST)
        pack(onedir=True, distpath=FOLDER_DIST)
        zip_name = DIST / f"{APP_NAME}-{APP_VERSION}-windows"
        shutil.make_archive(str(zip_name), "zip", root_dir=FOLDER_DIST, base_dir=APP_NAME)

        # 3. Instalador hecho con la versión en carpeta
        make_installer()

    # Huellas SHA256 de todo lo que se publica: sirven para comprobar
    # que un archivo descargado no fue modificado.
    lines = []
    print("\nListo:")
    for file in sorted(p for p in DIST.iterdir() if p.is_file()):
        # file_digest lee el archivo por partes: no carga 55 MB en memoria de golpe
        with open(file, "rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        lines.append(f"{digest}  {file.name}")
        print(f"  {file.name}  ({file.stat().st_size / 1024 / 1024:.0f} MB)")

    # El mismo texto va al archivo y a la consola (se pega en las notas de la Release)
    sums = "\n".join(lines) + "\n"
    # newline="\n": saltos de línea de Linux, como espera `sha256sum -c` (en Windows saldría \r\n)
    (DIST / "SHA256SUMS.txt").write_text(sums, encoding="utf-8", newline="\n")
    print("\n" + sums)


if __name__ == "__main__":
    main()
