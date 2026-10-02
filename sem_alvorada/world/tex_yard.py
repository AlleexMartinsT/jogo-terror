"""Texturas do exterior que Agent 1 não cobre: telha individual, tijolo individual, tábua de fachada, calha e grama.

Diferença para `tex_exterior`: aquelas cobrem uma superfície grande e repetem por metro (projeção em caixa).
Estas aqui são lidas por UV, uma peça por vez: cada telha, tijolo ou tábua sorteia um recorte diferente da
imagem, e a variação de tom entre peças vizinhas vem daí. Registradas em `materials.SURFACES` ao importar.
"""
import numpy as np

from . import texgen as T
from .texgen import Maps


def shingle_tab(rng, size=256):
    """Granulado de telha asfáltica envelhecida: cinza-carvão com grânulos, manchas de mofo e descoloração."""
    base = np.array((0.060, 0.062, 0.068), np.float32)
    image = T.gain(T.solid(size, size, base), 0.55 + 0.9 * T.fbm(rng, size, size, 4, 4))
    image = T.gain(image, 0.78 + 0.5 * T.speckle(rng, size, size, 0.35))
    image = T.gain(image, 0.85 + 0.3 * T.value_noise(rng, size, size, 64, 64))
    moss = T.threshold(T.fbm(rng, size, size, 3, 4), 0.62, 0.1)
    image = T.lerp(image, np.array((0.045, 0.062, 0.040), np.float32) * (0.7 + 0.6 * T.fbm(rng, size, size, 9, 3))[..., None],
                   moss * 0.6)
    bleach = T.threshold(T.fbm(rng, size, size, 2, 3), 0.7, 0.12)
    image = T.lerp(image, np.array((0.12, 0.115, 0.11), np.float32), bleach * 0.5)
    height = 0.45 + 0.4 * T.value_noise(rng, size, size, 96, 96) + 0.1 * T.fbm(rng, size, size, 8, 3)
    return Maps(T.finish(image), T.height_map(height), T.rough_map(np.full((size, size), 0.93)))


def brick_unit(rng, size=256):
    """Face de um tijolo: vermelho queimado com poros, fuligem e eflorescência."""
    base = np.array((0.215, 0.085, 0.060), np.float32)
    image = T.gain(T.solid(size, size, base), 0.6 + 0.8 * T.fbm(rng, size, size, 3, 4))
    image = T.gain(image, 0.8 + 0.4 * T.value_noise(rng, size, size, 48, 48))
    pits, _, _ = T.cellular(rng, size, size, 60)
    image = T.gain(image, 1 - 0.45 * T.threshold(0.10 - pits, 0.0, 0.04))
    soot = T.threshold(T.fbm(rng, size, size, 2, 4), 0.55, 0.2)
    image = T.lerp(image, np.array((0.04, 0.035, 0.035), np.float32), soot * 0.55)
    salt = T.threshold(T.fbm(rng, size, size, 5, 4), 0.72, 0.08)
    image = T.lerp(image, np.array((0.30, 0.29, 0.26), np.float32), salt * 0.4)
    height = 0.5 + 0.3 * T.value_noise(rng, size, size, 64, 64) - 0.3 * T.threshold(0.10 - pits, 0.0, 0.04)
    return Maps(T.finish(image), T.height_map(height), T.rough_map(np.full((size, size), 0.9)))


def mortar(rng, size=128):
    image = T.gain(T.solid(size, size, (0.21, 0.205, 0.185)), 0.6 + 0.8 * T.fbm(rng, size, size, 8, 4))
    image = T.gain(image, 1 + 0.4 * T.speckle(rng, size, size, 0.25))
    return Maps(T.finish(image), T.height_map(T.value_noise(rng, size, size, 40, 40)),
                T.rough_map(np.full((size, size), 0.97)))


def board_paint(rng, width=512, height=64):
    """Uma tábua de fachada vista de frente: tinta verde-acinzentada lascada, veio, sujeira que escorre.

    O eixo X da imagem corre ao longo da tábua; o recorte por tábua vem da UV sorteada."""
    base = np.array((0.215, 0.225, 0.190), np.float32)
    grain = T.value_noise(rng, width, height, 6, 96)
    image = T.gain(T.solid(width, height, base), 0.72 + 0.5 * T.fbm(rng, width, height, 5, 3))
    image = T.gain(image, 0.86 + 0.22 * grain)
    peel = T.threshold(T.fbm(rng, width, height, 6, 4, 0.6), 0.66, 0.04)
    wood = T.solid(width, height, (0.17, 0.145, 0.11)) * (0.65 + 0.7 * grain)[..., None]
    image = T.lerp(image, wood, peel)
    streak = T.value_noise(rng, width, height, 40, 3)
    image = T.gain(image, 1 - 0.30 * T.threshold(streak, 0.55, 0.25))
    mold = T.threshold(T.fbm(rng, width, height, 3, 4), 0.7, 0.1)
    image = T.lerp(image, np.array((0.07, 0.085, 0.06), np.float32), mold * 0.5)
    shade = np.linspace(1.12, 0.62, height, dtype=np.float32)[:, None]      # linha 0 = pé da tábua; o topo fica na sombra da de cima
    image = T.gain(image, shade)
    rough = 0.80 + 0.14 * grain - 0.12 * (1 - peel)
    return Maps(T.finish(image), T.height_map(0.35 + 0.4 * grain - 0.25 * peel), T.rough_map(rough))


def gutter_paint(rng, size=256):
    """Alumínio pintado de creme, com listras pretas de água suja e manchas de ferrugem."""
    image = T.gain(T.solid(size, size, (0.30, 0.285, 0.24)), 0.62 + 0.6 * T.fbm(rng, size, size, 4, 4))
    streak = T.value_noise(rng, size, size, 48, 3)
    image = T.gain(image, 1 - 0.55 * T.threshold(streak, 0.52, 0.25))
    rust = T.threshold(T.fbm(rng, size, size, 6, 4), 0.7, 0.06)
    image = T.lerp(image, np.array((0.13, 0.055, 0.03), np.float32), rust * 0.7)
    return Maps(T.finish(image), T.height_map(0.5 + 0.3 * T.fbm(rng, size, size, 12, 3)),
                T.rough_map(0.5 + 0.4 * rust))


def house_number(rng, text="412", size=(256, 128)):
    """Placa de madeira escura com os números de latão: fundo envernizado, numerais em segmentos, oxidação."""
    from ..props.textures import Canvas
    width, height = size
    canvas = Canvas(width, height, (0.065, 0.040, 0.025, 1.0))
    canvas.grain(rng_py(rng), 0.10)
    cell = width / (len(text) + 1)
    for index, ch in enumerate(text):
        canvas.text(int(cell * (index + 0.5)), 30, ch, (0.55, 0.40, 0.14, 1.0), 9, 2)
    canvas.rect(0, 0, width, 5, (0.02, 0.012, 0.008, 1.0))
    canvas.rect(0, height - 5, width, height, (0.02, 0.012, 0.008, 1.0))
    canvas.tint((0.12, 0.10, 0.05), 0.12)
    colour = np.clip(canvas.px[::-1, :, :3], 0, 1).astype(np.float32)
    return Maps(colour, T.height_map(1.0 - colour.mean(axis=2)), T.rough_map(np.full((height, width), 0.6)))


def rng_py(np_rng):
    """`random.Random` derivado de um gerador numpy (o Canvas dos props usa a biblioteca padrão)."""
    import random
    return random.Random(int(np_rng.integers(1 << 31)))


def children_sign(rng, size=256):
    """Placa 'Criança brincando': losango amarelo desbotado com borda preta, letras e dois bonequinhos."""
    from ..props.textures import Canvas
    canvas = Canvas(size, size, (0.0, 0.0, 0.0, 0.0))
    c = size / 2
    canvas.polygon([(c, 4), (size - 4, c), (c, size - 4), (4, c)], (0.42, 0.34, 0.04, 1.0))
    canvas.polygon([(c, 16), (size - 16, c), (c, size - 16), (16, c)], (0.020, 0.020, 0.020, 1.0))
    canvas.polygon([(c, 24), (size - 24, c), (c, size - 24), (24, c)], (0.42, 0.34, 0.04, 1.0))
    for text, y in (("SLOW", 66), ("CHILDREN", 160), ("AT PLAY", 188)):
        scale = 4 if text == "SLOW" else 2
        canvas.text(int(c - canvas.text_width(text, scale) / 2), y, text, (0.02, 0.02, 0.02, 1.0), scale)
    for x in (c - 30, c + 30):
        canvas.ellipse(x, 108, 7, 7, (0.02, 0.02, 0.02, 1.0))
        canvas.line(x, 114, x, 142, (0.02, 0.02, 0.02, 1.0), 5)
        canvas.line(x - 14, 126, x + 14, 126, (0.02, 0.02, 0.02, 1.0), 4)
    canvas.grain(rng_py(rng), 0.12)
    colour = np.clip(canvas.px[::-1, :, :3], 0, 1).astype(np.float32)
    dirt = T.fbm(rng, size, size, 4, 4)
    colour = T.gain(colour, 0.65 + 0.5 * dirt)
    alpha = canvas.px[::-1, :, 3].astype(np.float32)
    return Maps(T.finish(colour), T.height_map(1.0 - colour.mean(axis=2)), T.rough_map(np.full((size, size), 0.4)), alpha)


def chalk_drawing(rng, size=(256, 384)):
    """Desenho de giz da Emma na entrada de carros: amarelinha numerada, o nome dela e um sol, tudo desbotado."""
    from ..props.textures import Canvas
    width, height = size
    canvas = Canvas(width, height, (0.0, 0.0, 0.0, 0.0))
    pink, blue, yellow, white = (0.80, 0.40, 0.55), (0.38, 0.55, 0.85), (0.90, 0.80, 0.35), (0.85, 0.85, 0.82)
    cell = 54
    # amarelinha: casas 1-2 em fila, 3 sozinha, 4-5 em fila, 6 sozinha, 7-8 em fila (de baixo para cima)
    layout_rows = [(0,), (0,), (-0.5, 0.5), (0,), (-0.5, 0.5), (0,), (-0.5, 0.5)]
    number = 1
    for row, columns in enumerate(layout_rows):
        y = height - 58 - row * cell
        for column in columns:
            x = 70 + column * cell
            color = (pink, blue, yellow)[number % 3]
            for edge in ((x, y, x + cell, y), (x + cell, y, x + cell, y + cell), (x + cell, y + cell, x, y + cell), (x, y + cell, x, y)):
                canvas.line(*edge, (*color, 0.9), 4.0)
            canvas.text(int(x + cell / 2 - 7), int(y + cell / 2 - 10), str(number), (*white, 0.9), 3)
            number += 1
    canvas.text(150, 60, "EMMA", (*pink, 0.9), 5)
    cx, cy = 200, 180
    canvas.ellipse(cx, cy, 22, 22, (*yellow, 0.9))
    for k in range(10):
        a = k * 0.628
        canvas.line(cx + 30 * np.cos(a), cy + 30 * np.sin(a), cx + 48 * np.cos(a), cy + 48 * np.sin(a), (*yellow, 0.85), 4.0)
    for eye in (-8, 8):
        canvas.line(cx + eye, cy - 5, cx + eye, cy + 1, (0.2, 0.2, 0.2, 0.9), 3.0)
    canvas.line(cx - 10, cy + 8, cx, cy + 13, (0.2, 0.2, 0.2, 0.9), 3.0)
    canvas.line(cx, cy + 13, cx + 10, cy + 8, (0.2, 0.2, 0.2, 0.9), 3.0)
    smear = T.fbm(rng, width, height, 4, 4)
    colour = np.clip(canvas.px[::-1, :, :3], 0, 1).astype(np.float32)
    alpha = canvas.px[::-1, :, 3].astype(np.float32) * (0.25 + 0.65 * T.threshold(smear, 0.28, 0.4))
    return Maps(T.finish(colour), None, T.rough_map(np.full((height, width), 0.95)), alpha)
