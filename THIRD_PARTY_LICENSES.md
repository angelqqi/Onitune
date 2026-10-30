# Licencias de terceros

Onitune tiene licencia MIT (ver [LICENSE](LICENSE)). Usa estos proyectos de otras personas:

| Proyecto | Para qué | Licencia | ¿Va dentro de Onitune? |
|---|---|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Habla con YouTube y descarga | [Unlicense](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE) (dominio público) | No: la app lo descarga de su página oficial en el primer arranque |
| [FFmpeg](https://ffmpeg.org) (compilación de [yt-dlp/FFmpeg-Builds](https://github.com/yt-dlp/FFmpeg-Builds)) | Convierte audio y une video | [GPL v3](https://ffmpeg.org/legal.html) | No: la app lo descarga de su página oficial en el primer arranque, o usa el que ya tengas instalado |
| [Flet](https://flet.dev) | La ventana y los controles | [Apache 2.0](https://github.com/flet-dev/flet/blob/main/LICENSE) | Sí, en el ejecutable |
| [Flutter](https://flutter.dev) (dentro de Flet) | Dibuja la ventana | [BSD 3-Clause](https://github.com/flutter/flutter/blob/master/LICENSE) | Sí, en el ejecutable |
| [Material Icons](https://fonts.google.com/icons) (dentro de Flet) | Iconos de los botones | [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) | Sí, en el ejecutable |
| [Python](https://www.python.org) | El lenguaje | [PSF License](https://docs.python.org/3/license.html) | Sí, en el ejecutable |
| [PyInstaller](https://pyinstaller.org) | Crea el ejecutable | [GPL 2.0 con excepción para programas empaquetados](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt) | Solo su arranque, que esa excepción permite distribuir con cualquier licencia |

## Temas de color

Los temas reproducen los colores (solo los códigos de color, ningún archivo) de estas paletas. Todas tienen licencia MIT, salvo Monokai, la paleta clásica de Wimer Hazenberg, que se usa como referencia de colores:
[Dracula / Alucard](https://draculatheme.com), [Tokyo Night](https://github.com/folke/tokyonight.nvim), [Catppuccin](https://catppuccin.com), [Nord](https://www.nordtheme.com), [Gruvbox](https://github.com/morhetz/gruvbox), [Rosé Pine](https://rosepinetheme.com), [Solarized](https://ethanschoonover.com/solarized/) y Monokai. En algunos temas claros se oscurecieron un poco los colores de estado para que el texto se lea bien.

## Icono

El icono (un onigiri que también es un botón de "play") es un diseño original de este proyecto, dibujado por [tools/make_icon.py](tools/make_icon.py). No usa el logo de YouTube ni el de ninguna serie.
