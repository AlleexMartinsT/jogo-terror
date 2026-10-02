"""Texturas do escritório de baixo: o quadro de cortiça com os recortes da Rota 33 e as folhas de papel da mesa.

Tudo em numpy. Cada recorte é desenhado na sua própria imagem pequena e colado girado sobre a cortiça,
com sombra. O RGB é a cor e o ALFA a altura do relevo (ver `tex_sala`). A mesma lista `CORK_CLIPS` serve
à textura e à geometria dos alfinetes, então a linha vermelha passa exatamente pelos papéis.
"""
import math

import numpy as np

from . import tex_sala, textures
from .tex_sala import Raster, blotches, fbm, mix, numpy_generator, smoothstep, worley

BOARD_SIZE = (512, 404)               # altura, largura em pixels (o quadro mede 0,95 x 0,75 m)
BOARD_METERS = (0.75, 0.95)           # largura, altura

# kind, centro u, centro v (0 a 1, origem no canto superior esquerdo), largura e altura em fração, giro em graus
CORK_CLIPS = (
    ("news", 0.20, 0.15, 0.26, 0.20, -5),
    ("map", 0.75, 0.13, 0.30, 0.19, 4),
    ("photo", 0.50, 0.12, 0.16, 0.16, -3),
    ("form", 0.12, 0.45, 0.22, 0.26, 7),
    ("note", 0.86, 0.40, 0.16, 0.16, -9),
    ("news", 0.20, 0.80, 0.28, 0.22, 3),
    ("photo", 0.78, 0.70, 0.18, 0.18, 8),
    ("form", 0.50, 0.86, 0.24, 0.23, -4),
    ("map", 0.90, 0.88, 0.17, 0.17, -12),
    ("note", 0.36, 0.27, 0.13, 0.13, 11),
    ("photo", 0.66, 0.29, 0.13, 0.14, -7),
    ("note", 0.30, 0.66, 0.14, 0.14, -6),
    ("news", 0.89, 0.57, 0.18, 0.15, 6),
)
# pontos (u, v) onde o fio vermelho é preso; pares consecutivos de CORK_YARN formam os trechos de fio
CORK_PINS = {
    "a": (0.20, 0.07), "b": (0.50, 0.05), "c": (0.75, 0.05), "d": (0.12, 0.36), "e": (0.86, 0.32), "f": (0.20, 0.72),
    "g": (0.78, 0.61), "h": (0.50, 0.77), "i": (0.90, 0.80), "j": (0.30, 0.50), "k": (0.86, 0.47),
}
CORK_YARN = (("a", "b"), ("b", "c"), ("c", "e"), ("a", "d"), ("d", "f"), ("e", "g"), ("g", "i"), ("f", "h"), ("h", "i"),
             ("b", "j"), ("j", "d"), ("k", "g"), ("c", "k"))
# a região em volta de (u 0,6; v 0,5) fica livre dos recortes: é onde está o caderno de Daniel (Item_NOTE_4)


def draw_text(image, x, y, text, scale, color):
    """Escreve `text` na fonte 5x7 de `textures` direto num array (muito mais rápido que o Canvas)."""
    for ch in text.upper():
        columns = textures._GLYPHS.get(ch, textures._GLYPHS[" "])
        for column, bits in enumerate(columns):
            for row in range(7):
                if bits >> row & 1:
                    x0, y0 = int(x + column * scale), int(y + row * scale)
                    image[max(y0, 0):max(y0 + scale, 0), max(x0, 0):max(x0 + scale, 0)] = color
        x += 6 * scale


def greek(image, gen, x0, y0, x1, y1, color, line=5, ink_rows=1):
    """Linhas de texto miúdo ilegível: barrinhas escuras com recuos de palavra."""
    y = y0
    while y + line <= y1:
        x = x0
        end = x1 - gen.uniform(0, (x1 - x0) * 0.35)
        while x < end:
            word = int(gen.uniform(5, 18))
            image[int(y):int(y) + ink_rows, int(x):int(min(x + word, end))] = color
            x += word + 3
        y += line


def _clipping(gen, kind, width, height):
    """Imagem RGB e altura de um recorte, no tamanho em pixels dado."""
    rgb = np.zeros((height, width, 3), np.float32)
    ink = np.array([0.10, 0.09, 0.08], np.float32)
    if kind == "news":
        rgb[:] = (0.76, 0.74, 0.65)
        draw_text(rgb, 6, 6, "HARLAN RIDGE", max(1, width // 80), ink)
        rgb[height // 7:height // 7 + 2, 4:width - 4] = ink
        draw_text(rgb, 6, height // 5, "ROTA 33", max(2, width // 36), ink)
        rgb[height // 2:height - 6, 6:width // 2 - 3] = (0.45, 0.45, 0.43)
        greek(rgb, gen, width // 2 + 2, height // 2, width - 6, height - 6, ink)
    elif kind == "map":
        rgb[:] = (0.80, 0.77, 0.63)
        for x in range(8, width, 22):
            rgb[:, x:x + 2] = (0.95, 0.93, 0.86)
        for y in range(10, height, 18):
            rgb[y:y + 2, :] = (0.95, 0.93, 0.86)
        river = slice(height // 3, height // 3 + height // 4)
        rgb[river, :] = rgb[river] * 0.4 + np.array([0.28, 0.40, 0.46]) * 0.6
        steps = np.linspace(0, 1, 40)
        for t in steps:
            px, py = int(t * (width - 4)), int(height * (0.9 - 0.7 * t))
            rgb[py:py + 3, px:px + 3] = (0.72, 0.10, 0.08)
        draw_text(rgb, 4, 3, "ROTA 33", max(1, width // 70), (0.45, 0.05, 0.05))
    elif kind == "photo":
        rgb[:] = (0.86, 0.85, 0.80)
        border = max(3, width // 12)
        rgb[border:height - 3 * border, border:width - border] = (0.18, 0.22, 0.24)
        horizon = height // 2
        rgb[border:horizon, border:width - border] = (0.46, 0.50, 0.52)
        rgb[horizon:height - 3 * border, border:width - border] = (0.12, 0.13, 0.13)
        rgb[horizon + 4:horizon + 8, width // 2 - 2:width // 2 + 2] = (0.8, 0.75, 0.5)
        rgb[horizon - 6:horizon, width // 2 - 14:width // 2 + 14] = (0.07, 0.08, 0.10)
    elif kind == "form":
        rgb[:] = (0.84, 0.84, 0.80)
        rgb[0:height // 7, :] = (0.55, 0.60, 0.70)
        draw_text(rgb, 5, 4, "SEGURO", max(1, width // 60), (0.95, 0.95, 0.95))
        for row in range(5):
            top = height // 4 + row * (height // 8)
            rgb[top:top + height // 11, 5:width - 5] = (0.72, 0.72, 0.68)
            greek(rgb, gen, 8, top + 2, width - 8, top + height // 11, (0.12, 0.13, 0.30), line=4)
        rgb[height - height // 6:height - height // 6 + 2, width // 2:width - 6] = (0.1, 0.1, 0.3)
    else:                                                    # bilhete amarelo escrito à mão
        rgb[:] = (0.92, 0.82, 0.38)
        greek(rgb, gen, 6, 8, width - 6, height - 6, (0.20, 0.12, 0.08), line=7, ink_rows=2)
    grain = (0.94 + 0.12 * gen.random((height, width, 1))).astype(np.float32)
    return np.clip(rgb * grain, 0, 1)


def _paste(rgb, height_map, clip, cx, cy, angle):
    """Cola `clip` girado em (cx, cy) pixels sobre a cortiça: sombra deslocada, papel e relevo."""
    clip_h, clip_w = clip.shape[:2]
    reach = int(math.hypot(clip_w, clip_h) / 2) + 3
    y_lo, y_hi = max(0, cy - reach), min(rgb.shape[0], cy + reach)
    x_lo, x_hi = max(0, cx - reach), min(rgb.shape[1], cx + reach)
    ys, xs = np.mgrid[y_lo:y_hi, x_lo:x_hi]
    cos_a, sin_a = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def inside(shift):
        dx, dy = xs - cx - shift, ys - cy - shift
        u, v = dx * cos_a + dy * sin_a + clip_w / 2, -dx * sin_a + dy * cos_a + clip_h / 2
        return u, v, (u >= 0) & (u < clip_w) & (v >= 0) & (v < clip_h)

    _, _, shadow = inside(3)
    rgb[y_lo:y_hi, x_lo:x_hi][shadow] *= 0.62
    u, v, paper = inside(0)
    region = rgb[y_lo:y_hi, x_lo:x_hi]
    region[paper] = clip[v[paper].astype(int), u[paper].astype(int)]
    height_map[y_lo:y_hi, x_lo:x_hi][paper] = 0.9
    edge = paper & ((u < 2) | (v < 2) | (u > clip_w - 3) | (v > clip_h - 3))
    region[edge] *= 0.78


def cork_board(gen):
    """Quadro de cortiça com recortes, fotos, mapas e formulários, e o centro vazio para o caderno."""
    height, width = BOARD_SIZE
    shape = (height, width)
    f1, f2 = worley(gen, shape, 70)
    cork = mix((0.36, 0.26, 0.16), (0.52, 0.39, 0.25), fbm(gen, shape, 12, 10, 4))
    cork *= (0.82 + 0.3 * smoothstep(0.1, 0.5, f1))[..., None]
    cork *= (1 - 0.35 * blotches(gen, shape, 6, 0.68, 0.86))[..., None]
    rgb = cork.astype(np.float32)
    height_map = (0.35 + 0.25 * smoothstep(0.0, 0.5, f1)).astype(np.float32)
    for kind, u, v, w, h, angle in CORK_CLIPS:
        pixel_w, pixel_h = int(w * width), int(h * height)
        clip = _clipping(gen, kind, pixel_w, pixel_h)
        _paste(rgb, height_map, clip, int(u * width), int(v * height), angle)
    return Raster(rgb, height_map)


def printed_sheet(gen, variant=0, size=(256, 196)):
    """Folha impressa de uma pasta de seguro ou boletim: cabeçalho, campos e parágrafos miúdos."""
    height, width = size
    rgb = np.empty((height, width, 3), np.float32)
    rgb[:] = (0.86, 0.85, 0.79) if variant % 2 == 0 else (0.82, 0.83, 0.86)
    ink = np.array([0.10, 0.10, 0.12], np.float32)
    draw_text(rgb, 12, 10, ("BOLETIM DE OCORRENCIA", "APOLICE DE SEGURO", "LAUDO DO ACIDENTE")[variant % 3], 2, ink)
    rgb[30:32, 10:width - 10] = ink
    for block in range(3):
        top = 42 + block * 52
        greek(rgb, gen, 14, top, width - 14, top + 44, ink * 1.2, line=6)
    rgb[height - 40:height - 38, width // 2:width - 14] = (0.1, 0.1, 0.3)
    stamp = np.hypot(*np.mgrid[0:height, 0:width] - np.array([height - 55, 56])[:, None, None]) < 22
    rgb[stamp] = mix(rgb[stamp], (0.65, 0.12, 0.12), np.full(stamp.sum(), 0.45))
    rgb *= (0.92 + 0.14 * fbm(gen, (height, width), 5, 4, 3))[..., None]
    rgb *= (1 - 0.35 * blotches(gen, (height, width), 4, 0.66, 0.85))[..., None]
    return Raster(rgb, 0.4 + 0.2 * gen.random((height, width)).astype(np.float32))


def newspaper_page(gen, size=(512, 384)):
    """Primeira página do jornal de terça: cabeçalho, manchete sobre a menina, foto e colunas; dobrada ao meio."""
    height, width = size
    rgb = np.empty((height, width, 3), np.float32)
    rgb[:] = (0.76, 0.74, 0.66)
    ink = np.array([0.09, 0.09, 0.09], np.float32)
    draw_text(rgb, 14, 10, "HARLAN RIDGE GAZETTE", 3, ink)
    rgb[44:47, 10:width - 10] = ink
    draw_text(rgb, 12, 56, "MENINA DE 7 ANOS", 3, ink)
    draw_text(rgb, 12, 82, "MORRE NA ROTA 33", 3, ink)
    rgb[112:114, 10:width - 10] = ink
    rgb[124:260, 14:170] = (0.50, 0.50, 0.48)
    rgb[200:252, 24:160] = (0.18, 0.19, 0.20)
    rgb[184:204, 60:120] = (0.12, 0.13, 0.15)
    greek(rgb, gen, 182, 124, width - 14, 262, ink, line=6)
    for column in range(3):
        left = 14 + column * (width - 28) // 3
        greek(rgb, gen, left, 280, left + (width - 40) // 3, height - 12, ink, line=6)
    rgb[height // 2 - 1:height // 2 + 1, :] *= 0.72
    rgb *= (0.90 + 0.16 * fbm(gen, (height, width), 5, 4, 3))[..., None]
    rgb *= (1 - 0.30 * blotches(gen, (height, width), 4, 0.66, 0.85))[..., None]
    rgb *= np.array([1.0, 0.97, 0.90], np.float32)
    return Raster(rgb, 0.4 + 0.2 * gen.random((height, width)).astype(np.float32))


def magazine_cover(gen, variant=0, size=(340, 256)):
    """Capa de revista de viagem de uns anos atrás: título grande, foto de estrada e chamadas miúdas."""
    height, width = size
    palette = ((0.62, 0.12, 0.10), (0.12, 0.30, 0.45), (0.18, 0.40, 0.22))[variant % 3]
    rgb = np.empty((height, width, 3), np.float32)
    rgb[:] = (0.88, 0.86, 0.80)
    rgb[0:56, :] = palette
    draw_text(rgb, 14, 12, ("VIAGEM", "ESTRADA", "CASA")[variant % 3], 5, (0.94, 0.92, 0.86))
    sky = np.linspace(0.75, 0.45, 128)[:, None, None] * np.array([0.8, 0.9, 1.0], np.float32)
    rgb[66:194, 12:width - 12] = sky
    rgb[150:194, 12:width - 12] = (0.2, 0.22, 0.18)
    rgb[170:176, width // 2 - 40:width // 2 + 40] = (0.8, 0.75, 0.4)
    draw_text(rgb, 14, 204, "ROTAS DE VERAO", 3, palette)
    greek(rgb, gen, 14, 232, width - 14, height - 10, (0.1, 0.1, 0.1), line=7)
    rgb *= (0.92 + 0.12 * fbm(gen, (height, width), 4, 4, 3))[..., None]
    rgb *= (1 - 0.25 * blotches(gen, (height, width), 4, 0.66, 0.85))[..., None]
    return Raster(rgb, 0.45 + 0.1 * gen.random((height, width)).astype(np.float32))


textures.TEXTURES.update({
    "sala_cork_board": lambda rng: cork_board(numpy_generator(rng)),
    "sala_newspaper": lambda rng: newspaper_page(numpy_generator(rng)),
    "sala_magazine_a": lambda rng: magazine_cover(numpy_generator(rng), 0),
    "sala_magazine_b": lambda rng: magazine_cover(numpy_generator(rng), 1),
    "sala_magazine_c": lambda rng: magazine_cover(numpy_generator(rng), 2),
    "sala_sheet_a": lambda rng: printed_sheet(numpy_generator(rng), 0),
    "sala_sheet_b": lambda rng: printed_sheet(numpy_generator(rng), 1),
    "sala_sheet_c": lambda rng: printed_sheet(numpy_generator(rng), 2),
})

tex_sala.SURFACES.update({
    "cork_board": tex_sala.Surface("sala_cork_board", 1.0, roughness=0.95, rough_swing=0.05, specular=0.05, bump=1.4,
                                   bump_distance=0.004),
    "newspaper": tex_sala.Surface("sala_newspaper", 1.0, roughness=0.9, specular=0.08, bump=0.3, bump_distance=0.001),
    **{f"magazine_{k}": tex_sala.Surface(f"sala_magazine_{k}", 1.0, roughness=0.5, specular=0.3, bump=0.2,
                                         bump_distance=0.001) for k in "abc"},
    "sheet_a": tex_sala.Surface("sala_sheet_a", 1.0, roughness=0.9, specular=0.1, bump=0.3, bump_distance=0.001),
    "sheet_b": tex_sala.Surface("sala_sheet_b", 1.0, roughness=0.9, specular=0.1, bump=0.3, bump_distance=0.001),
    "sheet_c": tex_sala.Surface("sala_sheet_c", 1.0, roughness=0.9, specular=0.1, bump=0.3, bump_distance=0.001),
})
for _name in ("cork_board", "newspaper", "magazine_a", "magazine_b", "magazine_c", "sheet_a", "sheet_b", "sheet_c"):
    tex_sala.materials.register_builder(_name, lambda n=_name: tex_sala.build_surface(n, tex_sala.SURFACES[n]))
