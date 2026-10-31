#!/usr/bin/env bash
# Abre Onitune en Linux:  ./Onitune.sh
cd "$(dirname "$0")" || exit 1

# 1. Buscar actualizaciones del programa (si tienes git instalado)
command -v git >/dev/null && git pull --quiet

# 2. La primera vez: crear el entorno de Python
if [ ! -x .venv/bin/python ]; then
    echo "Preparando Onitune por primera vez, espera un momento..."
    PY=$(command -v python3.13 || command -v python3)  # se recomienda Python 3.13
    # --system-site-packages: así la ventana puede usar GTK/WebKit instalados en el sistema
    if ! "$PY" -m venv --system-site-packages .venv; then
        echo "Necesitas Python 3 con venv. En Ubuntu/Debian: sudo apt install python3-venv python3-gi gir1.2-webkit2-4.1"
        exit 1
    fi
fi

# 3. Instalar o actualizar lo que necesita la app
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt || {
    echo "No se pudieron instalar las dependencias. Revisa tu conexión a internet."
    exit 1
}

# 4. Abrir la app
exec .venv/bin/python main.py
