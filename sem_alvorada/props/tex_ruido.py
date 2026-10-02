"""Ruídos, máscaras e utilitários de desenho das texturas procedurais da cozinha e da garagem (numpy puro).

Tudo é ladrilhável (periódico), para a projeção em caixa em escala de mundo não deixar emendas, e determinístico por
nome de textura. As funções devolvem arrays (altura, largura) com valores 0..1, e `canvas_from` empacota cor e relevo
num `Canvas` RGBA em que o alfa é a altura.
"""
import zlib

import numpy as np

from . import textures
from .textures import Canvas


def generator(name):
    """Gerador determinístico por nome de textura."""
    return np.random.default_rng(zlib.crc32(f"kg:{name}".encode("utf-8")))


def _fade(t):
    return t * t * (3 - 2 * t)


def value_noise(rng, size, cells_x, cells_y):
    """Ruído de valor suave e periódico em [0, 1]; células finas e altas dão fibras e escovado."""
    lattice = rng.random((cells_y, cells_x))
    xs, ys = np.arange(size) * cells_x / size, np.arange(size) * cells_y / size
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    fx, fy = _fade(xs - x0)[None, :], _fade(ys - y0)[:, None]
    x0, y0 = x0 % cells_x, y0 % cells_y
    x1, y1 = (x0 + 1) % cells_x, (y0 + 1) % cells_y
    top = lattice[np.ix_(y0, x0)] * (1 - fx) + lattice[np.ix_(y0, x1)] * fx
    bottom = lattice[np.ix_(y1, x0)] * (1 - fx) + lattice[np.ix_(y1, x1)] * fx
    return top * (1 - fy) + bottom * fy


def fbm(rng, size, cells_x, cells_y=None, octaves=4, gain=0.5):
    """Soma de oitavas de `value_noise`, normalizada para [0, 1]."""
    cells_y = cells_y or cells_x
    total, amplitude, norm = np.zeros((size, size)), 1.0, 0.0
    for octave in range(octaves):
        total += amplitude * value_noise(rng, size, cells_x * 2 ** octave, cells_y * 2 ** octave)
        norm += amplitude
        amplitude *= gain
    return total / norm


def smooth(values, low, high):
    """Degrau suave: 0 abaixo de `low`, 1 acima de `high`."""
    return _fade(np.clip((values - low) / (high - low), 0.0, 1.0))


def blur(values, passes=1):
    for _ in range(passes):
        values = (values * 4 + np.roll(values, 1, 0) + np.roll(values, -1, 0)
                  + np.roll(values, 1, 1) + np.roll(values, -1, 1)) / 8
    return values


def scratches(rng, size, count, length=(0.05, 0.25), angle_deg=(-8.0, 8.0), strength=(0.3, 1.0)):
    """Riscos finos (máscara 0..1) com ângulo quase constante, periódicos."""
    mask = np.zeros((size, size))
    for _ in range(count):
        x0, y0 = rng.uniform(0, size, 2)
        angle = np.radians(rng.uniform(*angle_deg))
        steps = int(rng.uniform(*length) * size * 2)
        t = np.arange(steps) / 2.0
        xs = ((x0 + t * np.cos(angle)) % size).astype(int)
        ys = ((y0 + t * np.sin(angle)) % size).astype(int)
        np.maximum.at(mask, (ys, xs), rng.uniform(*strength))
    return mask


def spots(rng, size, count, radius=(2.0, 6.0), strength=(0.5, 1.0)):
    """Manchas redondas e suaves (respingos, ferrugem, mofo) como máscara 0..1, periódicas.

    Cada mancha só mexe na janela quadrada ao redor dela (índices tomados módulo `size` para a textura ladrilhar).
    """
    mask = np.zeros((size, size))
    for _ in range(count):
        cx, cy = rng.uniform(0, size, 2)
        r = rng.uniform(*radius)
        weight = rng.uniform(*strength)
        reach = int(np.ceil(r)) + 1
        xs = np.arange(int(cx) - reach, int(cx) + reach + 1)
        ys = np.arange(int(cy) - reach, int(cy) + reach + 1)
        falloff = weight * np.clip(1.0 - np.hypot(xs[None, :] - cx, ys[:, None] - cy) / r, 0.0, 1.0)
        window = np.ix_(ys % size, xs % size)
        mask[window] = np.maximum(mask[window], falloff)
    return mask


def ring_mark(size, cx, cy, radius, width):
    """Marca de fundo de copo: um aro fino e suave."""
    yy, xx = np.mgrid[0:size, 0:size]
    return np.clip(1.0 - np.abs(np.hypot(xx - cx, yy - cy) - radius) / width, 0.0, 1.0)


def mix(color_a, color_b, amount):
    """Mistura duas cores (r, g, b) por uma máscara (h, w)."""
    a, b = np.array(color_a), np.array(color_b)
    return a + (b - a) * amount[..., None]


def stamp_text(canvas, x, y, string, color, scale=1, spacing=1):
    """Escreve `string` na fonte 5x7 do projeto por fatias de array (o `Canvas.text` pinta a imagem inteira a cada pixel)."""
    rgb = np.array(color[:3], np.float32)
    for char in string.upper():
        for column, bits in enumerate(textures._GLYPHS.get(char, textures._GLYPHS[" "])):
            for row in range(7):
                if bits >> row & 1:
                    x0, y0 = int(x + column * scale), int(y + row * scale)
                    canvas.px[max(y0, 0):max(y0 + scale, 0), max(x0, 0):max(x0 + scale, 0), :3] = rgb
        x += (5 + spacing) * scale


def canvas_from(color, height):
    """Empacota cor (h, w, 3) e altura (h, w) num Canvas RGBA."""
    rows, columns = height.shape
    canvas = Canvas(columns, rows)
    canvas.px[..., :3] = np.clip(color, 0.0, 1.0)
    canvas.px[..., 3] = np.clip(height, 0.0, 1.0)
    return canvas


# ---------------------------------------------------------------------------
# Decals: o alfa da imagem é a transparência (e não a altura)
# ---------------------------------------------------------------------------
def decal_canvas(color, alpha):
    """Canvas para decal: o alfa da imagem é a transparência (e não a altura, como nas demais)."""
    rows, columns = alpha.shape
    canvas = Canvas(columns, rows)
    canvas.px[..., :3] = np.broadcast_to(np.array(color, np.float32), (rows, columns, 3))
    canvas.px[..., 3] = np.clip(alpha, 0.0, 1.0)
    return canvas


def radial_falloff(size, power=1.6):
    yy, xx = np.mgrid[0:size, 0:size]
    distance = np.hypot(xx - size / 2 + 0.5, yy - size / 2 + 0.5) / (size / 2)
    return np.clip(1.0 - distance, 0.0, 1.0) ** power
