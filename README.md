<p align="center"><img src="assets/icon.png" width="128" alt="Icono de Onitune: un onigiri con forma de botón de play"></p>

# Onitune

App de escritorio para descargar **audio y video de YouTube**, hecha en Python con [Flet](https://flet.dev) y [yt-dlp](https://github.com/yt-dlp/yt-dlp). Funciona en Windows y Linux.

- **Audio:** MP3, M4A, OPUS, FLAC o WAV, con portada y metadatos. Se puede pegar un enlace o buscar por nombre y elegir entre los resultados.
- **Búsqueda en YouTube Music:** al buscar por nombre, busca canciones en YouTube Music para que el archivo quede con artista y álbum correctos. Se puede apagar en Ajustes.
- **Portada cuadrada:** recorta la miniatura de YouTube para que la portada quede cuadrada, como en YouTube Music. Se elige en Ajustes si se aplica a canciones de YouTube Music, a todo el audio, al video o a nada.
- **Video:** analiza el enlace y muestra solo las resoluciones que ese video tiene. MP4 o MKV, con subtítulos incrustados o en un archivo aparte.
- **Playlists:** muestra la lista para seleccionar qué videos descargar.
- **Descargas:** varias a la vez, con pausa, reanudación, cancelación y reintento. Las pendientes se guardan al cerrar la app.
- **Historial:** buscar, filtrar, abrir el archivo o la carpeta, volver a descargar y borrar.
- **Temas:** 14 temas de color (Drácula, Alucard, Tokyo Night, Catppuccin, Nord, Gruvbox, Rosé Pine, Solarized…) que se eligen en Ajustes.
- **Extras:** detecta enlaces de YouTube copiados, usa cookies del navegador (para videos con restricción de edad), muestra avisos del sistema y avisa cuando hay una versión nueva de Onitune.

## Créditos

- **Idea, diseño y dirección:** [angelqqi](https://github.com/angelqqi).
- **Código:** escrito con ayuda de inteligencia artificial ([Claude](https://claude.com), de Anthropic), siguiendo las indicaciones y decisiones de angelqqi.

## Licencia y aviso legal

- El código de Onitune tiene licencia **MIT** (ver [LICENSE](LICENSE)): se puede usar, modificar y compartir libremente, manteniendo el aviso de copyright.
- Los programas de terceros que usa (yt-dlp, FFmpeg, Flet…) y sus licencias están en [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). yt-dlp y FFmpeg **no** van incluidos: la app los descarga de sus páginas oficiales.
- Onitune **no está afiliado** a YouTube ni a Google. "YouTube" es una marca de Google LLC y se menciona solo para describir para qué sirve la app.
- Descargar contenido puede ir contra los términos de YouTube o los derechos de autor de quien lo creó. **La app debe usarse solo con contenido que se tenga derecho a guardar** (por ejemplo, videos propios o contenido con licencia libre). Cada persona es responsable de cómo la usa.

## Descargar

En la [última versión (Releases)](https://github.com/angelqqi/Onitune/releases/latest) hay tres formas para Windows. Ninguna necesita Python ni permisos de administrador:

| Archivo | Para qué |
|---|---|
| `Onitune-Setup-X.Y.Z.exe` | **Instalador** (recomendado): crea el acceso en el Menú Inicio y se desinstala desde la configuración de Windows. |
| `Onitune-X.Y.Z-windows.zip` | **Portable**: se descomprime la carpeta y se abre `Onitune.exe`. Es la que abre más rápido. |
| `Onitune.exe` | **Un solo archivo**: se abre directamente, sin instalar. Tarda un poco más en abrir porque se descomprime cada vez. |

> Windows puede mostrar el aviso "Windows protegió su PC" porque el programa no está firmado. Para abrirlo: **Más información → Ejecutar de todas formas**.
>
> Las huellas SHA256 de todos los archivos están en `SHA256SUMS.txt` y en las notas de cada Release.
>
> **Linux:** el ejecutable para Linux llegará pronto. Mientras tanto, se puede usar con Python (ver abajo).

## Cómo abrirla

| | Windows | Linux |
|---|---|---|
| Con Python 3.13 | Doble clic en `Onitune.bat` | `./Onitune.sh` |
| Sin Python | [`Onitune.exe`](https://github.com/angelqqi/Onitune/releases/latest) | Próximamente |

La primera vez, la app descarga sola **yt-dlp** y **ffmpeg** a su carpeta. No hay que instalar nada ni pedir permisos de administrador.

Los lanzadores (`Onitune.bat` / `Onitune.sh`) hacen esto:
1. `git pull` para traer la última versión del programa.
2. Crean un entorno de Python (`.venv`) la primera vez, con Python 3.13 si está instalado.
3. Instalan lo que hay en `requirements.txt`.
4. Abren la app.

> **¿Por qué Python 3.13?** Las versiones más nuevas (3.15) todavía no tienen todas las librerías listas; por ejemplo, la herramienta `flet-cli` no se instala. En Windows se puede tener 3.13 al lado de otra versión: `py install 3.13`.
>
> En Linux, Flet puede necesitar algunas librerías del sistema. Si la ventana no abre, la [guía de Flet para Linux](https://flet.dev/docs/publish/linux) explica cuáles instalar.

## Crear el ejecutable

```bash
.venv\Scripts\python -m pip install -r requirements-build.txt   # Windows
winget install JRSoftware.InnoSetup                              # solo para el instalador
python build.py
```

El resultado queda en `dist/`: el instalador, el `.zip` portable, el `.exe` de un solo archivo y `SHA256SUMS.txt`. Nada de eso necesita Python. yt-dlp **no** va dentro a propósito: así se actualiza solo y no hay que volver a crear el ejecutable cada vez que YouTube cambia algo.

## Dónde guarda las cosas

| Qué | Windows | Linux |
|---|---|---|
| Ajustes, descargas pendientes, historial, yt-dlp y ffmpeg | `%LOCALAPPDATA%\Onitune` | `~/.local/share/onitune` |
| Archivos descargados (por defecto) | `Música\Onitune\Audio` y `Videos\Onitune\Video` | `~/Music/Onitune/...` y `~/Videos/Onitune/...` |

Las carpetas de descarga se pueden cambiar en **Ajustes**.

## Cómo está organizado el código

```
main.py                 Punto de entrada: abre la ventana
onitune/
  core/                 La lógica, sin nada de interfaz
    paths.py            Dónde se guarda cada cosa
    settings.py         Ajustes (settings.json)
    deps.py             Descarga y actualiza yt-dlp y ffmpeg
    ytdlp.py            Habla con yt-dlp: buscar, analizar y armar el comando de descarga
    queue.py            La cola de descargas: lanza yt-dlp, lee el progreso, pausa y cancela
    history.py          Historial (history.json)
    updates.py          Revisa en GitHub si hay una versión nueva de Onitune
    notify.py           Avisos de Windows/Linux
    proc.py             Ejecutar programas sin abrir consolas, abrir archivos y carpetas
  ui/                   La interfaz (Flet)
    app.py              Ventana principal, menú lateral, temas, avisos (portapapeles y versión nueva)
    themes.py           Los temas de color (para agregar uno, se suma a la lista)
    audio_view.py       Pestaña Audio
    video_view.py       Pestaña Video
    queue_view.py       Pestaña Descargas
    history_view.py     Pestaña Historial
    settings_view.py    Pestaña Ajustes (incluye el selector de temas y "Acerca de")
    setup_view.py       Pantalla del primer arranque
    playlist_dialog.py  Ventana para elegir videos de una playlist
    common.py           Piezas compartidas (tarjetas, miniaturas, colores)
tools/make_icon.py      Dibuja el icono (assets/icon.png, assets/icon.ico)
build.py                Crea el ejecutable
```

**Idea clave:** `core/` no sabe nada de la interfaz y `ui/` no habla directamente con yt-dlp. Si YouTube cambia algo, normalmente basta con actualizar yt-dlp (botón en Ajustes). Para cambiar cómo se ve algo, basta con tocar `ui/`.

**Hilos:** las búsquedas y descargas corren en otros hilos para que la ventana no se congele. Cuando uno de esos hilos quiere cambiar algo en pantalla, usa `ui_call(page, funcion)` (en `ui/common.py`), que pasa el cambio al hilo de la interfaz.
