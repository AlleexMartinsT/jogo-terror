"""Primitivas de textura procedural em numpy (ruídos, máscaras, desfoque, conjuntos de mapas).

Convenção: tudo devolve `float32` de forma (altura, largura[, 3]) em cor LINEAR (a conversão para sRGB
acontece quando a imagem é criada, em `materials`). A linha 0 é a de baixo da imagem, como no Blender, então
"topo" significa índices de linha maiores.

Os ruídos são ladrilháveis: as bordas opostas se encontram, para que a repetição no mundo (projeção em
caixa) não deixe emendas.

Cada textura de superfície devolve um `Maps`: cor, altura (vira Bump) e rugosidade. Os módulos
`tex_interior`, `tex_floors`, `tex_doors` e `tex_exterior` usam estas primitivas.
"""
import zlib
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Maps:
    """Conjunto de mapas de uma superfície, todos do mesmo tamanho.

    `color`: (h, w, 3) linear. `height`: (h, w) em [0, 1], o branco é o mais alto (a distância real em
    metros vem da `Surface`). `rough`: (h, w) rugosidade absoluta em [0, 1]. Os dois últimos são opcionais:
    sem altura o relevo sai da luminância da cor; sem rugosidade vale a constante da superfície.
    """
    color: np.ndarray
    height: Optional[np.ndarray] = None
    rough: Optional[np.ndarray] = None


def rng_for(name):
    """Gerador determinístico por nome de textura: o mesmo build gera os mesmos pixels."""
    return np.random.default_rng(zlib.crc32(name.encode("utf-8")))


# --------------------------------------------------------------------------
# Ruídos
# --------------------------------------------------------------------------
def _fade(t):
    return t * t * (3 - 2 * t)


def value_noise(rng, width, height, cells_x, cells_y):
    """Ruído de valor suave e ladrilhável em [0, 1]. Células altas e finas dão fibras."""
    lattice = rng.random((cells_y, cells_x))
    xs = np.arange(width) * cells_x / width
    ys = np.arange(height) * cells_y / height
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    fx, fy = _fade(xs - x0)[None, :], _fade(ys - y0)[:, None]
    x0, y0 = x0 % cells_x, y0 % cells_y
    x1, y1 = (x0 + 1) % cells_x, (y0 + 1) % cells_y
    top = lattice[np.ix_(y0, x0)] * (1 - fx) + lattice[np.ix_(y0, x1)] * fx
    bottom = lattice[np.ix_(y1, x0)] * (1 - fx) + lattice[np.ix_(y1, x1)] * fx
    return top * (1 - fy) + bottom * fy


def fbm(rng, width, height, cells, octaves=4, persistence=0.5, cells_y=None):
    """Soma de oitavas de ruído de valor, normalizada para [0, 1]."""
    total = np.zeros((height, width))
    amplitude, norm = 1.0, 0.0
    for octave in range(octaves):
        scale = 2 ** octave
        total += amplitude * value_noise(rng, width, height, cells * scale, (cells_y or cells) * scale)
        norm += amplitude
        amplitude *= persistence
    return total / norm


def worley(rng, width, height, count):
    """Distâncias (F1, F2) ao ponto mais próximo e ao segundo, ladrilháveis, em pixels."""
    points = rng.random((count, 2)) * (width, height)
    xs, ys = np.meshgrid(np.arange(width) + 0.5, np.arange(height) + 0.5)
    wraps = []
    for ox in (-width, 0, width):
        for oy in (-height, 0, height):
            dx = xs[..., None] - (points[:, 0] + ox)
            dy = ys[..., None] - (points[:, 1] + oy)
            wraps.append(np.sqrt(dx * dx + dy * dy))
    nearest_two = np.partition(np.concatenate(wraps, axis=-1), 1, axis=-1)[..., :2]
    return nearest_two.min(axis=-1), nearest_two.max(axis=-1)


def cellular(rng, width, height, cells_x, cells_y=None, jitter=1.0):
    """Ruído celular por grade com pontos sorteados: (F1, F2, id) em unidades de célula, ladrilhável.

    Mais leve que `worley` para muitas células (só olha as 9 vizinhas) e devolve o `id` da célula mais
    próxima, que serve para dar um tom próprio a cada tijolo, pedra ou grão.
    """
    cells_y = cells_y or cells_x
    points = 0.5 + (rng.random((cells_y, cells_x, 2)) - 0.5) * jitter
    px = (np.arange(width) + 0.5) * cells_x / width
    py = (np.arange(height) + 0.5) * cells_y / height
    cx, cy = np.floor(px).astype(int), np.floor(py).astype(int)
    fx, fy = (px - cx)[None, :], (py - cy)[:, None]
    best1 = np.full((height, width), 9.0)
    best2 = np.full((height, width), 9.0)
    ident = np.zeros((height, width), np.int64)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            ix, iy = (cx + ox) % cells_x, (cy + oy) % cells_y
            gx = points[np.ix_(iy, ix)][..., 0] + ox
            gy = points[np.ix_(iy, ix)][..., 1] + oy
            dist = np.hypot(gx - fx, gy - fy)
            label = (iy[:, None] * cells_x + ix[None, :])
            closer = dist < best1
            best2 = np.where(closer, best1, np.minimum(best2, dist))
            ident = np.where(closer, label, ident)
            best1 = np.where(closer, dist, best1)
    return best1, best2, ident


def speckle(rng, width, height, amount):
    """Ruído por pixel centrado em zero (grão fino)."""
    return (rng.random((height, width)) - 0.5) * 2 * amount


def cracks(rng, width, height, count, steps, wander=0.6):
    """Máscara 0/1 de fissuras: caminhadas aleatórias com direção persistente, ladrilháveis."""
    mask = np.zeros((height, width))
    for _ in range(count):
        x, y = rng.random() * width, rng.random() * height
        angle = rng.random() * 2 * np.pi
        for _ in range(steps):
            angle += (rng.random() - 0.5) * wander
            x, y = x + np.cos(angle), y + np.sin(angle)
            mask[int(y) % height, int(x) % width] = 1.0
    return mask


def branching_cracks(rng, width, height, count, steps, wander=0.45, branch=0.04):
    """Fissuras que se ramificam: cada passo tem uma chance de abrir um galho novo."""
    mask = np.zeros((height, width))
    walkers = [(rng.random() * width, rng.random() * height, rng.random() * 2 * np.pi, steps) for _ in range(count)]
    while walkers:
        x, y, angle, left = walkers.pop()
        for step in range(left):
            angle += (rng.random() - 0.5) * wander
            x, y = x + np.cos(angle), y + np.sin(angle)
            mask[int(y) % height, int(x) % width] = 1.0
            if rng.random() < branch and left - step > 8:
                walkers.append((x, y, angle + (rng.random() - 0.5) * 2.2, (left - step) // 2))
    return mask


def scratches(rng, width, height, count, length, angle_range=(0.0, np.pi)):
    """Riscos retos e curtos em direções aleatórias."""
    mask = np.zeros((height, width))
    for _ in range(count):
        x, y = rng.random() * width, rng.random() * height
        angle = angle_range[0] + rng.random() * (angle_range[1] - angle_range[0])
        for step in range(int(length * (0.4 + rng.random()))):
            mask[int(y + np.sin(angle) * step) % height, int(x + np.cos(angle) * step) % width] = 1.0
    return mask


def blobs(rng, width, height, count, radius, softness=0.35):
    """Manchas de bordas irregulares em [0, 1] (umidade, óleo, sujeira): um envelope
    radial modulado por ruído, cortado num limiar, para não sair círculo perfeito."""
    xs, ys = np.meshgrid(np.arange(width) + 0.5, np.arange(height) + 0.5)
    ragged = fbm(rng, width, height, 6, 4, 0.6)
    field = np.zeros((height, width))
    for _ in range(count):
        cx, cy = rng.random() * width, rng.random() * height
        r = radius * (0.6 + 0.8 * rng.random())
        for ox in (-width, 0, width):
            for oy in (-height, 0, height):
                d2 = ((xs - cx - ox) ** 2 + (ys - cy - oy) ** 2) / (r * r)
                field = np.maximum(field, np.exp(-d2 * 1.6) * (0.35 + 1.1 * ragged))
    return smooth((field - 0.42) / (softness * 0.6))


def smooth(t):
    return _fade(np.clip(t, 0, 1))


def blur(image, sigma):
    """Desfoque gaussiano periódico via FFT (a textura continua ladrilhável). `sigma` em pixels."""
    if sigma <= 0:
        return image
    if image.ndim == 3:
        return np.stack([blur(image[..., c], sigma) for c in range(image.shape[2])], axis=-1)
    rows = np.fft.fftfreq(image.shape[0])[:, None]
    cols = np.fft.fftfreq(image.shape[1])[None, :]
    kernel = np.exp(-2 * (np.pi * sigma) ** 2 * (cols ** 2 + rows ** 2))
    return np.fft.ifft2(np.fft.fft2(image) * kernel).real


def normalize(field):
    """Reescala para [0, 1]."""
    low, high = float(field.min()), float(field.max())
    return (field - low) / (high - low) if high > low else np.zeros_like(field)


def threshold(field, level, softness=0.02):
    """Degrau suave: 0 abaixo de `level`, 1 acima (transição de largura `softness`)."""
    return smooth((field - level) / max(softness, 1e-6) + 0.5)


def pixel_grid(width, height):
    """Índices inteiros de coluna e linha como matrizes (h, w)."""
    return np.arange(width)[None, :].repeat(height, 0), np.arange(height)[:, None].repeat(width, 1)


def unit_grid(width, height):
    """Coordenadas normalizadas [0, 1) de cada pixel: (u, v) como matrizes (h, w)."""
    u = ((np.arange(width) + 0.5) / width)[None, :].repeat(height, 0)
    v = ((np.arange(height) + 0.5) / height)[:, None].repeat(width, 1)
    return u, v


# --------------------------------------------------------------------------
# Utilidades de cor
# --------------------------------------------------------------------------
def solid(width, height, color):
    return np.ones((height, width, 3), np.float32) * np.array(color, np.float32)


def lerp(a, b, t):
    """Mistura a→b com t escalar ou (h, w)."""
    t = np.asarray(t, np.float32)
    if t.ndim == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def gain(image, factor):
    factor = np.asarray(factor, np.float32)
    return image * (factor[..., None] if factor.ndim == 2 else factor)


def tint(image, rgb):
    return image * np.array(rgb, np.float32)


def finish(image):
    return np.clip(image, 0.0, 1.0).astype(np.float32)


def height_map(field):
    return np.clip(field, 0.0, 1.0).astype(np.float32)


def rough_map(field):
    return np.clip(field, 0.05, 1.0).astype(np.float32)


def _rows(height):
    """Coordenada vertical normalizada de cada linha (0 embaixo, 1 no topo)."""
    return ((np.arange(height) + 0.5) / height)[:, None]


def _cols(width):
    return ((np.arange(width) + 0.5) / width)[None, :]
