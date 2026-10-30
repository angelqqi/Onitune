@echo off
:: Abre Onitune (versión con ventana). Doble clic y listo.
cd /d "%~dp0"
title Onitune

:: 1. Buscar actualizaciones del programa (si tienes git instalado)
where git >nul 2>nul && git pull --quiet

:: 2. La primera vez: crear el entorno de Python
if not exist ".venv\Scripts\python.exe" (
    echo Preparando Onitune por primera vez, espera un momento...
    rem Se recomienda Python 3.13; si no esta, se usa el Python que haya
    py -3.13 -m venv .venv 2>nul || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo No se encontro Python. Instala Python 3.13 desde https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

:: 3. Instalar o actualizar lo que necesita la app (es rapido si ya esta)
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo No se pudieron instalar las dependencias. Revisa tu conexion a internet.
    pause
    exit /b 1
)

:: 4. Abrir la app sin dejar la consola abierta
start "" ".venv\Scripts\pythonw.exe" main.py
