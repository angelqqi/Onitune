"""Dibuja el icono de Onitune: un onigiri que también es un botón de "play".

El onigiri (bola de arroz) es triangular: girado hacia la derecha parece el
botón de reproducir. El alga nori lleva una flecha de descarga y el arroz una
carita kawaii. Diseño original (no usa el logo de YouTube).

Uso:   python tools/make_icon.py
Crea:  assets/icon.png (512 px), assets/icon-1024.png y assets/icon.ico
Necesita Pillow:  pip install pillow
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
S = 2048  # dibujamos grande y luego reducimos: así los bordes quedan suaves

# Colores (paleta Drácula)
PINK = (255, 121, 198)
PURPLE = (189, 147, 249)
RICE = (248, 248, 242)
NORI = (33, 34, 44)
EYES = (40, 42, 54)
BLUSH = (255, 121, 198, 150)


def px(v: float) -> int:
    return round(v * S)


def rounded_triangle(draw: ImageDraw.ImageDraw, pts, radius: float, fill) -> None:
    """Triángulo con esquinas redondeadas (unión de círculos y polígonos)."""
    (ax, ay), (bx, by), (cx, cy) = pts
    a = math.dist((bx, by), (cx, cy))
    b = math.dist((ax, ay), (cx, cy))
    c = math.dist((ax, ay), (bx, by))
    per = a + b + c
    ix, iy = (a * ax + b * bx + c * cx) / per, (a * ay + b * by + c * cy) / per  # incentro
    s = per / 2
    area = math.sqrt(s * (s - a) * (s - b) * (s - c))
    inradius = area / s
    k = (inradius - radius) / inradius
    inner = [(ix + (x - ix) * k, iy + (y - iy) * k) for x, y in pts]
    draw.polygon([(px(x), px(y)) for x, y in inner], fill=fill)
    for i in range(3):
        x1, y1 = inner[i]
        x2, y2 = inner[(i + 1) % 3]
        # normal hacia fuera del lado
        nx, ny = y2 - y1, -(x2 - x1)
        length = math.hypot(nx, ny)
        nx, ny = nx / length * radius, ny / length * radius
        if (x1 + nx - ix) ** 2 + (y1 + ny - iy) ** 2 < (x1 - ix) ** 2 + (y1 - iy) ** 2:
            nx, ny = -nx, -ny
        draw.polygon(
            [(px(x1), px(y1)), (px(x2), px(y2)), (px(x2 + nx), px(y2 + ny)), (px(x1 + nx), px(y1 + ny))],
            fill=fill,
        )
        draw.ellipse([px(x1 - radius), px(y1 - radius), px(x1 + radius), px(y1 + radius)], fill=fill)


def make() -> Image.Image:
    # Fondo: cuadrado redondeado con degradado rosa → morado
    gradient = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(gradient)
    for i in range(S * 2):
        t = i / (S * 2)
        color = tuple(round(p + (q - p) * t) for p, q in zip(PINK, PURPLE))
        gd.line([(i, 0), (0, i)], fill=color + (255,), width=2)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=px(0.23), fill=255)
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    icon.paste(gradient, (0, 0), mask)

    # Onigiri girado: apunta a la derecha como un botón de play
    tri = [(0.29, 0.165), (0.29, 0.835), (0.875, 0.50)]
    corner = 0.095

    # Sombra suave
    shadow = Image.new("L", (S, S), 0)
    rounded_triangle(ImageDraw.Draw(shadow), [(x, y + 0.025) for x, y in tri], corner, 110)
    shadow = shadow.filter(ImageFilter.GaussianBlur(px(0.025)))
    icon.paste((60, 20, 90, 255), (0, 0), shadow)

    # Arroz
    rice_mask = Image.new("L", (S, S), 0)
    rounded_triangle(ImageDraw.Draw(rice_mask), tri, corner, 255)
    icon.paste(RICE + (255,), (0, 0), rice_mask)

    # Nori (solo dentro del arroz) en el lado izquierdo
    nori_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(nori_mask).rectangle([0, px(0.335), px(0.475), px(0.665)], fill=255)
    combined = Image.new("L", (S, S), 0)
    combined.paste(nori_mask, (0, 0), rice_mask)
    icon.paste(NORI + (255,), (0, 0), combined)

    d = ImageDraw.Draw(icon)

    # Flecha de descarga sobre el nori
    ax = 0.383
    d.rounded_rectangle([px(ax - 0.024), px(0.39), px(ax + 0.024), px(0.53)], radius=px(0.012), fill=PINK)
    d.polygon([(px(ax - 0.066), px(0.505)), (px(ax + 0.066), px(0.505)), (px(ax), px(0.59))], fill=PINK)
    d.rounded_rectangle([px(ax - 0.06), px(0.605), px(ax + 0.06), px(0.627)], radius=px(0.01), fill=PINK)

    # Carita kawaii en el arroz
    for ex in (0.565, 0.665):
        d.ellipse([px(ex - 0.022), px(0.445), px(ex + 0.022), px(0.495)], fill=EYES)
        d.ellipse([px(ex - 0.006), px(0.452), px(ex + 0.006), px(0.465)], fill=RICE)  # brillo
    d.arc([px(0.595), px(0.505), px(0.635), px(0.542)], start=20, end=160, fill=EYES, width=px(0.009))

    blush = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blush)
    for bx in (0.532, 0.700):
        bd.ellipse([px(bx - 0.026), px(0.512), px(bx + 0.026), px(0.538)], fill=BLUSH)
    icon = Image.alpha_composite(icon, blush)
    return icon


def main() -> None:
    big = make()
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    big.resize((512, 512), Image.LANCZOS).save(assets / "icon.png")
    big.resize((1024, 1024), Image.LANCZOS).save(assets / "icon-1024.png")
    ico = big.resize((256, 256), Image.LANCZOS)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico.save(assets / "icon.ico", sizes=sizes)
    print("Listo: assets/icon.png, assets/icon-1024.png y assets/icon.ico")


if __name__ == "__main__":
    main()
