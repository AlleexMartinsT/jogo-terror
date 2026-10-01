"""Texturas de tecido dos quartos: trama de linho, xadrez, estampa infantil, felpa, toalha e tapetes.

A trama e a felpa saem em tons de cinza e recebem a cor do material (multiplicação), assim uma imagem serve
para lençol, roupa, cortina e pelúcia. Estampas (xadrez, estrelas, tapetes) já nascem coloridas.
"""
import math

import numpy as np

from . import tex_noise as noise
from . import textures

Canvas = textures.Canvas


def _canvas(color):
    height, width = color.shape[:2]
    canvas = Canvas(width, height)
    canvas.px[..., :3] = np.clip(color, 0.0, 1.0)
    canvas.px[..., 3] = 1.0
    return canvas


def _weave_shading(size, period, gen):
    """Brilho 0..1 de uma trama simples: fios de urdidura e de trama se alternando por cima, com variação por fio."""
    index = np.arange(size)
    half = max(period // 2, 1)
    over = ((index[:, None] // half) + (index[None, :] // half)) % 2 == 0
    across = 0.5 + 0.5 * np.cos(2 * np.pi * index[None, :] / period)
    along = 0.5 + 0.5 * np.cos(2 * np.pi * index[:, None] / period)
    height = np.where(over, across, along)
    per_column = gen.random(size).astype(np.float32)[None, :]
    per_row = gen.random(size).astype(np.float32)[:, None]
    slub = noise.fbm(size, size, 24, 24, gen, 2)
    return 0.62 + 0.24 * height + 0.07 * per_column + 0.07 * per_row + 0.10 * (slub - 0.5)


def draw_weave(rng, size=256, period=4):
    """Trama cinza de pano (lençol, roupa, cortina): receberá a cor do material."""
    gen = noise.generator(rng)
    shade = np.clip(_weave_shading(size, period, gen), 0, 1.2)
    return _canvas(np.repeat(shade[..., None], 3, axis=2))


def draw_twill(rng, size=256):
    """Sarja diagonal cinza (jeans, brim): fios que correm a 45 graus."""
    gen = noise.generator(rng)
    index = np.arange(size)
    diagonal = 0.5 + 0.5 * np.cos(2 * np.pi * (index[:, None] + index[None, :]) / 6)
    shade = 0.66 + 0.26 * diagonal + 0.10 * (noise.fbm(size, size, 20, 20, gen, 2) - 0.5)
    return _canvas(np.repeat(shade[..., None], 3, axis=2))


def draw_terry(rng, size=256):
    """Toalha felpuda: laçadas minúsculas em relevo, em cinza."""
    gen = noise.generator(rng)
    loops = noise.fbm(size, size, 110, 110, gen, 2)
    soft = noise.fbm(size, size, 8, 8, gen, 2)
    shade = 0.55 + 0.45 * loops * (0.8 + 0.2 * soft)
    return _canvas(np.repeat(shade[..., None], 3, axis=2))


def draw_fur(rng, size=256):
    """Pelo curto de pelúcia: tufos finos com direção, em cinza."""
    gen = noise.generator(rng)
    tufts = noise.fbm(size, size, 120, 90, gen, 3, 0.55)
    clumps = noise.fbm(size, size, 14, 14, gen, 2)
    shade = 0.50 + 0.38 * tufts + 0.20 * (clumps - 0.5)
    return _canvas(np.repeat(shade[..., None], 3, axis=2))


# ---------------------------------------------------------------------------
# Estampas
# ---------------------------------------------------------------------------
def draw_tartan(rng, size=256, ground=(0.27, 0.075, 0.075), stripes=((0.075, 0.14, 0.10), (0.52, 0.46, 0.33))):
    """Xadrez escocês desbotado de edredom: listras de urdidura e de trama se cruzando sobre a trama do fio."""
    gen = noise.generator(rng)
    band_pattern = np.zeros(size, np.int8)         # 0 fundo, 1 verde, 2 creme fino, 3 preto
    for start, width, kind in ((12, 44, 1), (74, 6, 2), (92, 14, 3), (132, 44, 1), (194, 6, 2), (212, 14, 3)):
        band_pattern[start:start + width] = kind
    palette = np.array([ground, stripes[0], stripes[1], (0.025, 0.025, 0.03)], np.float32)
    warp = palette[band_pattern][None, :, :]
    weft = palette[band_pattern][:, None, :]
    color = 0.5 * (warp + weft)
    both = ((band_pattern[None, :] > 0) & (band_pattern[:, None] > 0))[..., None]
    color = np.where(both, color * 1.15, color)
    shade = _weave_shading(size, 4, gen)[..., None]
    return _canvas(color * shade * 1.2)


def draw_stars_fabric(rng, size=256):
    """Coberta infantil: fundo lilás-acinzentado, estrelas amareladas e luas, pontos de costura de colcha."""
    gen = noise.generator(rng)
    canvas = Canvas(size, size, (0.43, 0.37, 0.50, 1.0))
    for cx, cy in ((46, 40), (170, 70), (96, 150), (214, 206), (30, 214), (130, 12), (232, 124)):
        points = []
        for i in range(10):
            radius = 26 if i % 2 == 0 else 11
            angle = -math.pi / 2 + i * math.pi / 5
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        canvas.polygon(points, (0.78, 0.68, 0.36, 1.0))
    canvas.ellipse(190, 160, 14, 14, (0.74, 0.70, 0.52, 1.0))
    canvas.ellipse(196, 156, 12, 12, (0.43, 0.37, 0.50, 1.0))
    quilt = np.zeros((size, size), np.float32)
    index = np.arange(size)
    quilt[(index % 64 < 2)[:, None] | (index % 64 < 2)[None, :]] = 1.0
    shade = _weave_shading(size, 4, gen)[..., None]
    color = canvas.px[..., :3] * shade * 1.25 * (1 - 0.35 * quilt[..., None])
    return _canvas(color)


# ---------------------------------------------------------------------------
# Tapetes (peça única: a textura cobre o tapete inteiro, de 0 a 1)
# ---------------------------------------------------------------------------
def _pile(canvas, gen, wear=0.5):
    """Felpa e desgaste de tapete: grão de fio e um caminho gasto, mais claro, no meio."""
    size_y, size_x = canvas.px.shape[:2]
    pile = noise.fbm(size_y, size_x, 100, 100, gen, 2)
    path = np.exp(-(((np.arange(size_x)[None, :] / size_x - 0.5) / 0.22) ** 2)) * noise.fbm(size_y, size_x, 5, 3, gen, 3)
    canvas.px[..., :3] *= (0.78 + 0.34 * pile)[..., None] * (1.0 - 0.18 * wear * path[..., None])
    canvas.px[..., :3] = noise.grime(canvas.px[..., :3], gen, 0.22, (0.07, 0.065, 0.055))
    return canvas


def draw_rug_persian(rng, size=512):
    """Tapete de sala em bordô e azul-marinho: moldura de três faixas, medalhão em losangos e cantos."""
    gen = noise.generator(rng)
    burgundy, navy, cream, olive = (0.20, 0.060, 0.065), (0.060, 0.075, 0.140), (0.46, 0.40, 0.28), (0.15, 0.17, 0.09)
    canvas = Canvas(size, size, (*burgundy, 1.0))
    margin = size * 0.05
    for inset, color in ((0, navy), (margin * 0.9, cream), (margin * 1.2, navy), (margin * 2.4, burgundy), (margin * 2.8, cream),
                         (margin * 3.0, burgundy)):
        canvas.rect(inset, inset, size - inset, size - inset, (*color, 1.0))
    c = size / 2
    for radius, color in ((size * 0.30, navy), (size * 0.25, burgundy), (size * 0.19, cream), (size * 0.15, olive), (size * 0.07, burgundy)):
        canvas.polygon([(c, c - radius), (c + radius * 0.72, c), (c, c + radius), (c - radius * 0.72, c)], (*color, 1.0))
    for corner_x, corner_y in ((0.2, 0.2), (0.8, 0.2), (0.2, 0.8), (0.8, 0.8)):
        px, py = size * corner_x, size * corner_y
        canvas.polygon([(px, py - 26), (px + 20, py), (px, py + 26), (px - 20, py)], (*navy, 1.0))
        canvas.ellipse(px, py, 8, 8, (*cream, 1.0))
    for i in range(14):
        x = size * (0.16 + 0.68 * i / 13)
        canvas.polygon([(x, margin * 1.45), (x + 7, margin * 1.45 + 9), (x, margin * 1.45 + 18), (x - 7, margin * 1.45 + 9)],
                       (*cream, 0.9))
        canvas.polygon([(x, size - margin * 1.45 - 18), (x + 7, size - margin * 1.45 - 9), (x, size - margin * 1.45),
                        (x - 7, size - margin * 1.45 - 9)], (*cream, 0.9))
    return _pile(canvas, gen)


def draw_rug_kids(rng, size=256):
    """Tapete redondo azul de quarto infantil: anéis creme e rosa e estrelas pequenas."""
    gen = noise.generator(rng)
    canvas = Canvas(size, size, (0.11, 0.15, 0.25, 1.0))
    c = size / 2
    for radius, color in ((0.47, (0.44, 0.40, 0.30)), (0.43, (0.11, 0.15, 0.25)), (0.36, (0.45, 0.28, 0.32)),
                          (0.32, (0.11, 0.15, 0.25))):
        canvas.ellipse(c, c, size * radius, size * radius, (*color, 1.0))
    for i in range(8):
        angle = i * math.pi / 4
        cx, cy = c + size * 0.215 * math.cos(angle), c + size * 0.215 * math.sin(angle)
        points = [(cx + (14 if k % 2 == 0 else 6) * math.cos(-math.pi / 2 + k * math.pi / 5),
                   cy + (14 if k % 2 == 0 else 6) * math.sin(-math.pi / 2 + k * math.pi / 5)) for k in range(10)]
        canvas.polygon(points, (0.62, 0.55, 0.30, 1.0))
    canvas.ellipse(c, c, size * 0.10, size * 0.10, (0.45, 0.28, 0.32, 1.0))
    return _pile(canvas, gen, 0.3)


def draw_rug_runner(rng, size=256):
    """Passadeira do corredor: faixa verde-musgo com bordas e losangos que repetem na vertical."""
    gen = noise.generator(rng)
    moss, brown, cream = (0.12, 0.16, 0.10), (0.20, 0.10, 0.07), (0.42, 0.37, 0.25)
    canvas = Canvas(size, size, (*moss, 1.0))
    for x0, x1, color in ((0, 22, brown), (22, 30, cream), (30, 44, brown), (size - 22, size, brown),
                          (size - 30, size - 22, cream), (size - 44, size - 30, brown)):
        canvas.rect(x0, 0, x1, size, (*color, 1.0))
    for y in (size * 0.25, size * 0.75):
        canvas.polygon([(size / 2, y - 52), (size / 2 + 48, y), (size / 2, y + 52), (size / 2 - 48, y)], (*brown, 1.0))
        canvas.polygon([(size / 2, y - 32), (size / 2 + 30, y), (size / 2, y + 32), (size / 2 - 30, y)], (*cream, 1.0))
        canvas.polygon([(size / 2, y - 16), (size / 2 + 16, y), (size / 2, y + 16), (size / 2 - 16, y)], (*moss, 1.0))
    canvas.px[..., :3] *= (0.76 + 0.34 * noise.fbm(size, size, 90, 90, gen, 2))[..., None]
    canvas.px[..., :3] = noise.grime(canvas.px[..., :3], gen, 0.25, (0.07, 0.065, 0.055))
    return canvas


def draw_rug_cotton(rng, size=128):
    """Tapete de banheiro de algodão felpudo, azul-acinzentado com faixas."""
    gen = noise.generator(rng)
    canvas = Canvas(size, size, (0.32, 0.38, 0.40, 1.0))
    canvas.rect(0, size * 0.12, size, size * 0.2, (0.46, 0.48, 0.45, 1.0))
    canvas.rect(0, size * 0.80, size, size * 0.88, (0.46, 0.48, 0.45, 1.0))
    canvas.px[..., :3] *= (0.55 + 0.6 * noise.fbm(size, size, 64, 64, gen, 2))[..., None]
    canvas.px[..., :3] = noise.grime(canvas.px[..., :3], gen, 0.3, (0.10, 0.09, 0.06))
    return canvas


TEXTURES = {
    "up_weave": draw_weave,
    "up_twill": draw_twill,
    "up_terry": draw_terry,
    "up_fur": draw_fur,
    "up_tartan": draw_tartan,
    "up_stars_fabric": draw_stars_fabric,
    "up_rug_persian": draw_rug_persian,
    "up_rug_kids": draw_rug_kids,
    "up_rug_runner": draw_rug_runner,
    "up_rug_cotton": draw_rug_cotton,
}
textures.TEXTURES.update(TEXTURES)
