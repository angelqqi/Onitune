#!/usr/bin/env bash
# Crea el paquete .deb de Onitune (Ubuntu, Debian, Linux Mint, Kali...).
#
# Uso, en Linux, desde la raíz del repo:   bash installer/linux/build_deb.sh
# Resultado: dist/onitune_X.Y.Z_all.deb
#
# Para crearlo hace falta python3 con venv (sudo apt install python3-venv).
# Qué hace el paquete al instalarse:
# - Copia la app a /usr/lib/onitune (con pywebview dentro, en vendor/).
# - Crea el comando "onitune" y el acceso en el menú de aplicaciones.
# - apt instala solo GTK y WebKit (las dependencias de la ventana).
# yt-dlp y ffmpeg no van dentro: la app los descarga al primer arranque, igual que en Windows.
set -euo pipefail
cd "$(dirname "$0")/../.."

VERSION=$(python3 -c "import onitune; print(onitune.APP_VERSION)")
NAME="onitune_${VERSION}_all"
WORK="build/deb"
PKG="$WORK/$NAME"
APP="$PKG/usr/lib/onitune"

echo "Creando $NAME.deb..."
rm -rf "$WORK"
mkdir -p "$APP" "$PKG/DEBIAN" "$PKG/usr/bin" "$PKG/usr/share/applications" \
         "$PKG/usr/share/icons/hicolor/512x512/apps" "$PKG/usr/share/doc/onitune" dist

# 1. La app: código, página, iconos y licencias
cp -r main.py onitune assets LICENSE THIRD_PARTY_LICENSES.md "$APP/"
rm -f "$APP/assets/icon.ico"  # el .ico solo sirve en Windows
find "$APP" -name "__pycache__" -type d -prune -exec rm -rf {} +

# 2. pywebview y lo que necesita, dentro de vendor/ (versión fija de requirements.txt)
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/python" -m pip install --quiet --disable-pip-version-check \
    --no-compile --target "$APP/vendor" -r requirements.txt
rm -rf "$APP/vendor/bin"
rm -rf "$APP/vendor/webview/lib"  # piezas de WebView2 para Windows: en Linux no se usan
find "$APP/vendor" -name "__pycache__" -type d -prune -exec rm -rf {} +

# 3. El comando "onitune" (usa el Python del sistema, que trae GTK con python3-gi)
cat > "$PKG/usr/bin/onitune" <<'EOF'
#!/bin/sh
# Abre Onitune instalado con el paquete .deb
export PYTHONPATH="/usr/lib/onitune/vendor${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3 /usr/lib/onitune/main.py "$@"
EOF

# 4. Acceso en el menú de aplicaciones e icono
cat > "$PKG/usr/share/applications/onitune.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Onitune
GenericName=YouTube Downloader
GenericName[es]=Descargador de YouTube
Comment=Download music and video from YouTube
Comment[es]=Descarga música y video de YouTube
Exec=onitune
Icon=onitune
Terminal=false
Categories=AudioVideo;Audio;Video;Network;
Keywords=youtube;mp3;music;video;download;música;descargar;
StartupWMClass=onitune
EOF
cp assets/icon.png "$PKG/usr/share/icons/hicolor/512x512/apps/onitune.png"
cp LICENSE "$PKG/usr/share/doc/onitune/copyright"

# 5. Datos del paquete para apt/dpkg
SIZE=$(du -sk "$PKG" | cut -f1)
cat > "$PKG/DEBIAN/control" <<EOF
Package: onitune
Version: $VERSION
Architecture: all
Maintainer: angelqqi <350423338+angelqqi@users.noreply.github.com>
Installed-Size: $SIZE
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
Recommends: libnotify-bin, xdg-utils
Section: sound
Priority: optional
Homepage: https://github.com/angelqqi/Onitune
Description: Download music and video from YouTube
 Onitune is a simple and free desktop app to download audio (MP3, M4A,
 OPUS, FLAC, WAV) with cover art and tags, and video up to 4K, from YouTube
 and YouTube Music. It uses yt-dlp and ffmpeg, which it downloads by itself
 on first launch.
EOF

# Al instalar: precompilar el código (abre más rápido). Al desinstalar: borrar esa caché.
cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
python3 -m compileall -q /usr/lib/onitune >/dev/null 2>&1 || true
EOF
cat > "$PKG/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
find /usr/lib/onitune -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
EOF

# 6. Permisos: carpetas 755, archivos 644, ejecutables 755
find "$PKG" -type d -exec chmod 755 {} +
find "$PKG" -type f -exec chmod 644 {} +
chmod 755 "$PKG/usr/bin/onitune" "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/prerm"

dpkg-deb --build --root-owner-group "$PKG" "dist/$NAME.deb" >/dev/null
echo "Listo: dist/$NAME.deb ($(du -h "dist/$NAME.deb" | cut -f1))"
