"""Texturas e materiais da sala, do escritório de baixo, do hall e da sala de jantar.

Madeira de nogueira e carvalho com veio e poros, tecidos de estofado, couro, lã xadrez, tapetes, lombadas
de livros e porcelana. Tudo numpy puro (nada de bibliotecas fora do Blender), 256 a 512 px, ladrilhável,
lido com filtro Linear e com relevo ligado ao Bump.

Convenção das imagens: o RGB guarda a cor (sRGB, como o olho a vê) e o ALFA guarda a ALTURA do relevo
(0,3 a 1,0). Assim cada material precisa de uma só imagem para cor, relevo e rugosidade (a rugosidade
sai da luminância: sujeira escurece e deixa áspero, desgaste clareia e lustra).

O veio da madeira corre ao longo de U. Peças verticais (pernas, montantes) usam a variante `_v` do
material, que gira o mapeamento em 90 graus.
"""
import math
import random
from dataclasses import dataclass

import numpy as np

from .. import compat
from . import materials, textures


# ---------------------------------------------------------------------------
# Ruído ladrilhável
# ---------------------------------------------------------------------------
def numpy_generator(rng):
    """Gerador numpy derivado do `random.Random` do build: a mesma semente gera os mesmos pixels."""
    return np.random.default_rng(rng.getrandbits(63))


def _fade(t):
    return t * t * (3 - 2 * t)


def value_noise(gen, shape, cells_y, cells_x=None):
    """Ruído de valor 0..1 que repete nas bordas. Poucas células em X e muitas em Y dão fibras ao longo de X."""
    height, width = shape
    cells_x = cells_x or cells_y
    grid = gen.random((cells_y, cells_x)).astype(np.float32)
    ys, xs = np.arange(height) * cells_y / height, np.arange(width) * cells_x / width
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    fy, fx = _fade(ys - y0)[:, None], _fade(xs - x0)[None, :]
    y0, x0 = y0 % cells_y, x0 % cells_x
    y1, x1 = (y0 + 1) % cells_y, (x0 + 1) % cells_x
    top = grid[np.ix_(y0, x0)] * (1 - fx) + grid[np.ix_(y0, x1)] * fx
    bottom = grid[np.ix_(y1, x0)] * (1 - fx) + grid[np.ix_(y1, x1)] * fx
    return top * (1 - fy) + bottom * fy


def fbm(gen, shape, cells_y, cells_x=None, octaves=4, gain=0.5):
    """Soma de oitavas de `value_noise`, normalizada em 0..1."""
    cells_x = cells_x or cells_y
    total = np.zeros(shape, np.float32)
    amplitude, norm = 1.0, 0.0
    for octave in range(octaves):
        total += amplitude * value_noise(gen, shape, cells_y * 2 ** octave, cells_x * 2 ** octave)
        norm += amplitude
        amplitude *= gain
    return total / norm


def worley(gen, shape, cells):
    """Distâncias ao ponto mais próximo (F1) e ao segundo (F2), em células, numa grade que repete nas bordas."""
    height, width = shape
    points = gen.random((cells, cells, 2)).astype(np.float32)
    ys, xs = (np.arange(height) + 0.5) * cells / height, (np.arange(width) + 0.5) * cells / width
    cell_y, cell_x = np.floor(ys).astype(int), np.floor(xs).astype(int)
    first = np.full(shape, 9.0, np.float32)
    second = np.full(shape, 9.0, np.float32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ny, nx = (cell_y + dy) % cells, (cell_x + dx) % cells
            px = (cell_x + dx)[None, :] + points[np.ix_(ny, nx)][..., 0]
            py = (cell_y + dy)[:, None] + points[np.ix_(ny, nx)][..., 1]
            distance = np.hypot(xs[None, :] - px, ys[:, None] - py)
            second = np.minimum(second, np.maximum(first, distance))
            first = np.minimum(first, distance)
    return first, second


def smoothstep(edge0, edge1, values):
    t = np.clip((values - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def mix(low, high, amount):
    """Mistura linear de duas cores por uma máscara (altura, largura)."""
    amount = np.clip(amount, 0.0, 1.0)[..., None]
    return np.asarray(low, np.float32) * (1 - amount) + np.asarray(high, np.float32) * amount


def scratch_mask(gen, shape, count, length=(0.05, 0.3), tilt=0.25):
    """Riscos finos quase paralelos ao eixo X (0..1), com emenda nas bordas."""
    height, width = shape
    mask = np.zeros(shape, np.float32)
    for _ in range(count):
        x0, y0 = gen.uniform(0, width), gen.uniform(0, height)
        steps = int(gen.uniform(*length) * width)
        angle = gen.normal(0.0, tilt)
        ts = np.arange(steps)
        mask[((y0 + ts * math.sin(angle)) % height).astype(int),
             ((x0 + ts * math.cos(angle)) % width).astype(int)] = gen.uniform(0.4, 1.0)
    return mask


def blotches(gen, shape, cells, low, high):
    """Manchas grandes de baixa frequência, 0 onde não há mancha (sujeira, gordura, mofo)."""
    return smoothstep(low, high, fbm(gen, shape, cells, cells, 4))


class Raster:
    """Imagem RGBA com a interface que `textures.image` espera de um Canvas."""

    def __init__(self, rgb, height_map=None):
        self.height, self.width = rgb.shape[:2]
        alpha = np.ones((self.height, self.width), np.float32) if height_map is None \
            else 0.3 + 0.7 * np.clip(height_map, 0, 1)
        self.px = np.dstack([np.clip(rgb, 0, 1), alpha]).astype(np.float32)

    def pixels(self):
        return np.ascontiguousarray(self.px[::-1]).ravel()


def _grid(shape):
    """Coordenadas normalizadas: v para baixo, u para a direita, ambas em 0..1."""
    height, width = shape
    return np.arange(height, dtype=np.float32)[:, None] / height, np.arange(width, dtype=np.float32)[None, :] / width


# ---------------------------------------------------------------------------
# Madeira
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WoodLook:
    dark: tuple
    light: tuple
    rings: int            # anéis de crescimento por repetição da textura
    wander: float         # quanto o veio ondula (catedral)
    pores: float          # profundidade dos poros


WALNUT = WoodLook(dark=(0.12, 0.065, 0.036), light=(0.33, 0.19, 0.105), rings=46, wander=7.0, pores=0.7)
OAK = WoodLook(dark=(0.26, 0.16, 0.085), light=(0.60, 0.43, 0.25), rings=34, wander=6.0, pores=0.9)


def wood_veneer(gen, look, size=512):
    """Tábua com anéis ondulados (catedral), poros esticados no sentido do veio, riscos e manchas de uso."""
    shape = (size, size)
    v, u = _grid(shape)
    drift = fbm(gen, shape, 2, 2, 3) - 0.5
    arch = fbm(gen, shape, 1, 2, 2) - 0.5
    phase = v * look.rings + drift * look.wander + 0.6 * look.wander * arch * np.sin(2 * np.pi * u * 1)
    ring = phase % 1.0
    late_wood = smoothstep(0.35, 0.9, ring) * (1 - smoothstep(0.9, 1.0, ring))
    fibre = fbm(gen, shape, size // 4, 2, 3)
    pore = smoothstep(0.58, 0.85, fbm(gen, shape, size // 2, 4, 2)) * look.pores
    tone = np.clip(0.30 + 0.40 * late_wood + 0.50 * (fibre - 0.5), 0, 1)
    color = mix(look.light, look.dark, tone) * (1 - 0.40 * pore)[..., None]
    color *= (0.90 + 0.20 * fbm(gen, shape, 3, 2, 3))[..., None]          # uma tábua mais clara que a vizinha
    scratches = scratch_mask(gen, shape, 34)
    color = color * (1 - 0.15 * scratches[..., None]) + 0.04 * scratches[..., None]
    stain = blotches(gen, shape, 5, 0.66, 0.9) * 0.35
    color *= (1 - stain)[..., None]
    height = 0.62 + 0.12 * late_wood - 0.5 * pore - 0.3 * scratches
    return Raster(color, height)


# ---------------------------------------------------------------------------
# Tecidos e couro
# ---------------------------------------------------------------------------
def _weave_height(shape, threads, twill=False):
    """Trama de fios que passam por cima e por baixo; devolve altura 0..1 e a luminância dos fios."""
    v, u = _grid(shape)
    x, y = u * threads, v * threads
    ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - ix, y - iy
    over_warp = ((ix - iy) % 4 < 2) if twill else ((ix + iy) % 2 == 0)
    warp = np.sin(np.pi * fx) ** 0.8 * (0.65 + 0.35 * np.sin(np.pi * fy))
    weft = np.sin(np.pi * fy) ** 0.8 * (0.65 + 0.35 * np.sin(np.pi * fx))
    return np.where(over_warp, warp, weft).astype(np.float32)


def upholstery_cloth(gen, size=512):
    """Estofado de tecido grosso: trama, fios soltos, desgaste lustroso nas áreas de apoio e manchas."""
    shape = (size, size)
    weave = _weave_height(shape, 128, twill=False)
    fuzz = fbm(gen, shape, size // 2, size // 2, 1)
    worn = smoothstep(0.58, 0.82, fbm(gen, shape, 3, 3, 4))
    weave_strength = 0.30 * (1 - 0.7 * worn)
    luminance = 0.72 - weave_strength / 2 + weave_strength * weave + 0.10 * (fuzz - 0.5) + 0.10 * worn
    luminance *= 0.92 + 0.16 * fbm(gen, shape, 5, 5, 3)
    stain = blotches(gen, shape, 6, 0.70, 0.88)
    rgb = mix(np.ones(3), (0.55, 0.47, 0.38), stain * 0.55) * luminance[..., None]
    return Raster(rgb, 0.25 + 0.55 * weave * (1 - 0.6 * worn))


def velvet_cloth(gen, size=512):
    """Veludo: pelo deitado em sentidos diferentes (áreas mais claras e mais escuras) e marcas de uso."""
    shape = (size, size)
    nap = fbm(gen, shape, 4, 4, 3)
    brushed = fbm(gen, shape, size // 3, size // 8, 3)
    luminance = 0.55 + 0.50 * (nap - 0.5) + 0.20 * (brushed - 0.5)
    pressed = smoothstep(0.62, 0.82, fbm(gen, shape, 3, 3, 3))
    luminance = luminance * (1 - 0.25 * pressed) + 0.10 * pressed
    stain = blotches(gen, shape, 5, 0.72, 0.9)
    rgb = mix(np.ones(3), (0.5, 0.42, 0.36), stain * 0.5) * luminance[..., None]
    return Raster(rgb, 0.45 + 0.4 * brushed)


def aged_leather(gen, size=512):
    """Couro com grão de seixos, dobras suaves onde se senta e desgaste claro nas áreas de apoio."""
    shape = (size, size)
    f1, f2 = worley(gen, shape, 96)
    grain = smoothstep(0.0, 0.35, f2 - f1)                       # 0 nas juntas entre seixos
    folds = np.abs(fbm(gen, shape, 3, 6, 3) - 0.5) * 2           # vales longos e rasos
    crease = 1 - smoothstep(0.0, 0.18, folds)
    worn = smoothstep(0.55, 0.8, fbm(gen, shape, 3, 3, 4))
    luminance = 0.66 + 0.10 * grain - 0.07 * crease + 0.12 * worn + 0.07 * (fbm(gen, shape, 5, 5, 3) - 0.5)
    greasy = blotches(gen, shape, 5, 0.68, 0.88)
    rgb = mix(np.ones(3), (0.66, 0.58, 0.50), greasy * 0.30) * np.clip(luminance, 0, 1)[..., None]
    return Raster(rgb, 0.55 + 0.25 * grain - 0.25 * crease)


def plaid_wool(gen, size=256):
    """Manta de lã xadrez: vinho, verde-garrafa e fios cremes, em sarja, puída."""
    shape = (size, size)
    v, u = _grid(shape)
    wine, green, cream, navy = (0.40, 0.09, 0.09), (0.09, 0.20, 0.14), (0.62, 0.56, 0.42), (0.07, 0.08, 0.15)

    def band(t):
        t = t % 1.0
        wide = smoothstep(0.10, 0.12, t) * (1 - smoothstep(0.38, 0.40, t))
        thin = smoothstep(0.58, 0.59, t) * (1 - smoothstep(0.62, 0.63, t))
        dark = smoothstep(0.78, 0.80, t) * (1 - smoothstep(0.92, 0.94, t))
        return wide, thin, dark

    vw, vt, vd = band(v)
    uw, ut, ud = band(u)
    color = np.broadcast_to(np.asarray(wine, np.float32), shape + (3,)).copy()
    color = mix(color, green, np.maximum(vw, uw) * 0.85)
    color = mix(color, navy, np.minimum(vd + ud, 1) * 0.8)
    color = mix(color, cream, np.maximum(vt, ut) * 0.9)
    twill = _weave_height(shape, 64, twill=True)
    color *= (0.78 + 0.30 * twill)[..., None] * (0.9 + 0.2 * fbm(gen, shape, size // 2, size // 2, 1))[..., None]
    color *= (1 - 0.35 * blotches(gen, shape, 4, 0.68, 0.85))[..., None]
    return Raster(color, 0.3 + 0.6 * twill)


# ---------------------------------------------------------------------------
# Tapetes
# ---------------------------------------------------------------------------
# tamanho (largura em X, profundidade em Y) em metros de cada tapete com padrão desenhado
RUG_SIZES = {"rug_living": (2.5, 2.3), "rug_den": (2.0, 1.5), "rug_dining": (2.7, 1.9)}


def rug_shape(width, depth, long_side=512):
    """(altura, largura) em pixels de uma imagem com a proporção do tapete."""
    scale = long_side / max(width, depth)
    return int(depth * scale), int(width * scale)


def persian_rug(gen, shape=(512, 384), palette=None, medallion=True):
    """Tapete de padrão persa simplificado: barras de borda, campo em losangos e medalhão central, desbotado."""
    ground, accent, cream, navy = palette or ((0.36, 0.09, 0.08), (0.62, 0.45, 0.20), (0.62, 0.56, 0.42), (0.08, 0.10, 0.20))
    height, width = shape
    v, u = _grid(shape)
    y, x = v * height / width, u            # unidades de largura do tapete
    aspect = height / width
    edge = np.minimum(np.minimum(x, 1 - x), np.minimum(y, aspect - y))
    along = np.where(np.minimum(x, 1 - x) < np.minimum(y, aspect - y), y, x)
    color = np.broadcast_to(np.asarray(ground, np.float32), shape + (3,)).copy()
    in_range = lambda lo, hi: ((edge >= lo) & (edge < hi)).astype(np.float32)           # noqa: E731
    color = mix(color, navy, in_range(0.0, 0.035))
    color = mix(color, cream, in_range(0.035, 0.05))
    border_motif = (np.sin(along * 2 * np.pi * 20) > 0).astype(np.float32) * in_range(0.07, 0.15)
    color = mix(color, accent, border_motif * 0.9)
    color = mix(color, navy, in_range(0.05, 0.07) + in_range(0.15, 0.17))
    color = mix(color, cream, in_range(0.17, 0.185))
    lattice = (np.abs((x * 9) % 1 - 0.5) + np.abs((y * 9) % 1 - 0.5)) < 0.22
    color = mix(color, accent, lattice.astype(np.float32) * (edge >= 0.185) * 0.55)
    if medallion:
        cx, cy = 0.5, aspect / 2
        lozenge = np.abs(x - cx) / 0.30 + np.abs(y - cy) / (0.30 * aspect * 1.05)
        color = mix(color, navy, (lozenge < 1.0).astype(np.float32))
        color = mix(color, cream, ((lozenge > 0.72) & (lozenge < 0.80)).astype(np.float32))
        color = mix(color, ground, (lozenge < 0.55).astype(np.float32))
        color = mix(color, accent, (lozenge < 0.22).astype(np.float32))
    yarn = fbm(gen, shape, height // 2, width // 2, 1)
    worn = smoothstep(0.55, 0.8, fbm(gen, shape, 3, 3, 4))
    luminance = (0.80 + 0.30 * (yarn - 0.5)) * (1 - 0.28 * worn)
    color = mix(color * luminance[..., None], (0.35, 0.32, 0.28), worn * 0.35)
    color *= (1 - 0.4 * blotches(gen, shape, 3, 0.7, 0.86))[..., None]
    return Raster(color, 0.5 + 0.3 * (yarn - 0.5))


def pile_texture(gen, size=256):
    """Pelo curto de tapete: grãozinho de lã que se mistura à cor do tapete e dá o relevo."""
    shape = (size, size)
    tuft = fbm(gen, shape, size // 3, size // 3, 2)
    fine = gen.random(shape).astype(np.float32)
    luminance = 0.82 + 0.35 * (tuft - 0.5) + 0.10 * (fine - 0.5)
    return Raster(np.repeat(luminance[..., None], 3, axis=2), 0.3 + 0.7 * tuft)


# ---------------------------------------------------------------------------
# Livros, papel, louça
# ---------------------------------------------------------------------------
BOOK_CLOTHS = ((0.30, 0.09, 0.08), (0.08, 0.14, 0.26), (0.10, 0.22, 0.14), (0.45, 0.33, 0.14), (0.22, 0.14, 0.09),
               (0.38, 0.38, 0.34), (0.09, 0.09, 0.10), (0.42, 0.20, 0.10), (0.20, 0.10, 0.22), (0.50, 0.46, 0.36))
SPINE_W, SPINE_H = 48, 192
ATLAS_SIZE = 512


def book_atlas_cell(kind, index):
    """Retângulo (u0, v0, u1, v1) de uma célula do atlas, no espaço UV (origem embaixo à esquerda).

    `kind`: 'spine' (10 colunas x 2 linhas de 48 x 192 px), 'cover' (4 de 64 x 128) ou 'pages' (4 de 64 x 128).
    """
    if kind == "spine":
        col, row = index % 10, (index // 10) % 2
        x0, y0, x1, y1 = col * SPINE_W, row * SPINE_H, (col + 1) * SPINE_W, (row + 1) * SPINE_H
    else:
        col = index % 4 + (4 if kind == "pages" else 0)
        x0, y0, x1, y1 = col * 64, 2 * SPINE_H, (col + 1) * 64, 2 * SPINE_H + 128
    return x0 / ATLAS_SIZE, 1 - y1 / ATLAS_SIZE, x1 / ATLAS_SIZE, 1 - y0 / ATLAS_SIZE


def book_atlas(gen, size=ATLAS_SIZE):
    """Atlas de lombadas (20), capas lisas (4) e blocos de páginas (4) de livros de uma casa de 20 anos."""
    rgb = np.full((size, size, 3), 0.1, np.float32)
    height = np.full((size, size), 0.5, np.float32)

    def paint(x0, y0, x1, y1, color, h=None):
        rgb[y0:y1, x0:x1] = color
        if h is not None:
            height[y0:y1, x0:x1] = h

    gilt, label = (0.62, 0.50, 0.24), (0.72, 0.66, 0.50)
    for index in range(20):
        col, row = index % 10, index // 10
        x0, y0 = col * SPINE_W, row * SPINE_H
        cloth = BOOK_CLOTHS[(index * 3 + row) % len(BOOK_CLOTHS)]
        paint(x0, y0, x0 + SPINE_W, y0 + SPINE_H, cloth, 0.5)
        sheen = 0.78 + 0.35 * np.linspace(0, 1, SPINE_W)[None, :] * np.linspace(1, 0, SPINE_W)[None, :] * 4
        rgb[y0:y0 + SPINE_H, x0:x0 + SPINE_W] *= sheen[..., None]
        for stripe in (10, 14, SPINE_H - 14, SPINE_H - 10):
            paint(x0 + 3, y0 + stripe, x0 + SPINE_W - 3, y0 + stripe + 2, gilt, 0.8)
        if index % 3:
            top = y0 + 30 + (index % 4) * 8
            paint(x0 + 7, top, x0 + SPINE_W - 7, top + 52, label, 0.62)
            for line in range(5):
                rgb[top + 8 + line * 8: top + 10 + line * 8, x0 + 11:x0 + SPINE_W - 11] = (0.14, 0.11, 0.08)
                height[top + 8 + line * 8: top + 10 + line * 8, x0 + 11:x0 + SPINE_W - 11] = 0.25
        else:
            for line in range(3):
                paint(x0 + 8, y0 + 50 + line * 30, x0 + SPINE_W - 8, y0 + 53 + line * 30, gilt, 0.8)
    cover_y = 2 * SPINE_H
    for index in range(4):
        x0 = index * 64
        paint(x0, cover_y, x0 + 64, cover_y + 128, BOOK_CLOTHS[(index * 2 + 1) % len(BOOK_CLOTHS)], 0.5)
        paint(x0 + 8, cover_y + 8, x0 + 56, cover_y + 12, gilt, 0.7)
        paint(x0 + 8, cover_y + 116, x0 + 56, cover_y + 120, gilt, 0.7)
    for index in range(4):
        x0 = (4 + index) * 64
        paint(x0, cover_y, x0 + 64, cover_y + 128, (0.72, 0.66, 0.50), 0.55)
        for line in range(0, 128, 3):
            rgb[cover_y + line, x0 + 6:x0 + 58] *= 0.86
        rgb[cover_y:cover_y + 128, x0:x0 + 5] = BOOK_CLOTHS[index * 2]
        rgb[cover_y:cover_y + 128, x0 + 59:x0 + 64] = BOOK_CLOTHS[index * 2]
    rgb *= (0.92 + 0.12 * fbm(gen, (size, size), 20, 20, 3))[..., None]
    rgb *= (1 - 0.25 * blotches(gen, (size, size), 7, 0.65, 0.85))[..., None]
    return Raster(rgb, height)


def table_linen(gen, size=512):
    """Linho de toalha de mesa: trama fina cor de creme, bordado em listra, anel de copo e uma queimadura."""
    shape = (size, size)
    weave = _weave_height(shape, 170)
    v, u = _grid(shape)
    luminance = 0.80 + 0.10 * weave + 0.06 * (fbm(gen, shape, size // 2, size // 2, 1) - 0.5)
    stripe = ((np.abs(((v * 4) % 1.0) - 0.5) < 0.012) | (np.abs(((v * 4) % 1.0) - 0.42) < 0.004)).astype(np.float32)
    rgb = np.repeat(luminance[..., None], 3, axis=2) * np.array([1.0, 0.97, 0.88], np.float32)
    rgb = mix(rgb, (0.46, 0.40, 0.30), stripe * 0.65)
    ring = np.abs(np.hypot(u - 0.3, v - 0.62) - 0.07)
    rgb *= (1 - 0.16 * (1 - smoothstep(0.0, 0.010, ring)))[..., None] * np.array([1.0, 0.97, 0.92], np.float32)
    rgb *= (1 - 0.16 * blotches(gen, shape, 5, 0.70, 0.88))[..., None]
    return Raster(rgb, 0.25 + 0.55 * weave)


def china_porcelain(gen, size=256):
    """Louça de casa de família: branco encardido, filete dourado desbotado e rachaduras finas de esmalte."""
    shape = (size, size)
    v, u = _grid(shape)
    first, second = worley(gen, shape, 18)
    crazing = 1 - smoothstep(0.0, 0.06, second - first)
    base = 0.78 + 0.10 * (fbm(gen, shape, 6, 6, 3) - 0.5)
    rgb = np.repeat(base[..., None], 3, axis=2) * np.array([1.0, 0.97, 0.88], np.float32)
    rim = (np.abs(v - 0.5) < 0.02).astype(np.float32)
    rgb = mix(rgb, (0.60, 0.46, 0.20), rim * 0.9)
    rgb *= (1 - 0.18 * crazing)[..., None]
    rgb *= (1 - 0.4 * blotches(gen, shape, 5, 0.7, 0.88))[..., None]
    return Raster(rgb, 0.7 - 0.1 * crazing)


def envelope_front(gen, width=256, height=160):
    """Envelope pardo fechado, com selo, carimbo e o endereço manuscrito."""
    canvas = textures.Canvas(width, height, (0.74, 0.70, 0.56, 1.0))
    canvas.grain(random.Random(int(gen.integers(1 << 30))), 0.04)
    canvas.rect(width - 52, 10, width - 12, 56, (0.60, 0.20, 0.18, 1.0))
    canvas.rect(width - 48, 14, width - 16, 52, (0.76, 0.62, 0.34, 1.0))
    canvas.ellipse(width - 70, 40, 18, 18, (0.20, 0.18, 0.16, 0.35))
    pen = random.Random(int(gen.integers(1 << 30)))
    canvas.scribbles(pen, 40, 80, width - 70, 130, (0.12, 0.12, 0.30, 1.0), 14, 2.0)
    canvas.rect(0, height - 14, width, height, (0.60, 0.18, 0.16, 0.9))
    canvas.text(12, height - 11, "URGENTE", (0.9, 0.85, 0.7, 1.0))
    return canvas


def coir_doormat(gen, shape=(340, 512)):
    """Capacho de fibra de coco: fios de cor parda, moldura mais escura e a palavra de boas-vindas gasta."""
    height, width = shape
    fibre = fbm(gen, shape, height // 2, width // 12, 3)
    rgb = mix((0.20, 0.13, 0.08), (0.42, 0.30, 0.17), fibre)
    v, u = _grid(shape)
    edge = np.minimum(np.minimum(u, 1 - u), np.minimum(v * height / width, (1 - v) * height / width))
    frame = (edge < 0.045).astype(np.float32)
    rgb = mix(rgb, (0.08, 0.06, 0.05), frame * 0.85)
    canvas = textures.Canvas(width, height, (0, 0, 0, 0))
    text = "BEM-VINDO"
    canvas.text((width - canvas.text_width(text, 7)) // 2, height // 2 - 24, text, (1, 1, 1, 1), 7)
    letters = canvas.px[..., 3] > 0.5
    rgb = mix(rgb, (0.55, 0.50, 0.38), letters.astype(np.float32) * 0.75 * (0.6 + 0.4 * fibre))
    rgb *= (1 - 0.5 * blotches(gen, shape, 4, 0.62, 0.84))[..., None]
    return Raster(rgb, 0.3 + 0.6 * fibre)


# traços (x, y) de 0 a 1, com y para baixo, de cada algarismo romano numa caixa de 0,6 x 1
_ROMAN_STROKES = {
    "I": (((0.3, 0.0), (0.3, 1.0)),),
    "V": (((0.0, 0.0), (0.3, 1.0)), ((0.6, 0.0), (0.3, 1.0))),
    "X": (((0.0, 0.0), (0.6, 1.0)), ((0.6, 0.0), (0.0, 1.0))),
}


def clock_dial(gen, size=512):
    """Mostrador de relógio de pé: marfim envelhecido, algarismos romanos, trilho dos minutos e florões nos cantos."""
    canvas = textures.Canvas(size, size, (0.70, 0.64, 0.46, 1.0))
    ink, gilt = (0.09, 0.07, 0.05, 1.0), (0.55, 0.42, 0.16, 1.0)
    center = size / 2
    canvas.rect(0, 0, size, 14, gilt)
    canvas.rect(0, size - 14, size, size, gilt)
    canvas.rect(0, 0, 14, size, gilt)
    canvas.rect(size - 14, 0, size, size, gilt)
    for corner_x, corner_y in ((0, 0), (size, 0), (0, size), (size, size)):
        canvas.ellipse(corner_x, corner_y, size * 0.17, size * 0.17, gilt)
        canvas.ellipse(corner_x, corner_y, size * 0.13, size * 0.13, (0.66, 0.60, 0.44, 1.0))
    canvas.ellipse(center, center, center * 0.80, center * 0.80, ink)
    canvas.ellipse(center, center, center * 0.795, center * 0.795, (0.74, 0.68, 0.50, 1.0))
    canvas.ellipse(center, center, center * 0.60, center * 0.60, ink)
    canvas.ellipse(center, center, center * 0.595, center * 0.595, (0.74, 0.68, 0.50, 1.0))
    for minute in range(60):
        angle = math.radians(minute * 6)
        long = minute % 5 == 0
        inner, outer = (0.72 if long else 0.75) * center, 0.79 * center
        canvas.line(center + inner * math.sin(angle), center - inner * math.cos(angle),
                    center + outer * math.sin(angle), center - outer * math.cos(angle), ink, 4.5 if long else 2.2)
    numerals = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    for hour, text in enumerate(numerals):
        angle = math.radians(hour * 30)
        cx, cy = center + 0.66 * center * math.sin(angle), center - 0.66 * center * math.cos(angle)
        glyph_h = 0.088 * size
        glyph_w = 0.6 * glyph_h
        for index, glyph in enumerate(text):
            offset_x = (index - (len(text) - 1) / 2) * glyph_w * 1.45
            for (x0, y0), (x1, y1) in _ROMAN_STROKES[glyph]:
                local = [((x0 - 0.3) * glyph_h + offset_x, (y0 - 0.5) * glyph_h),
                         ((x1 - 0.3) * glyph_h + offset_x, (y1 - 0.5) * glyph_h)]
                rotated = [(cx + px * math.cos(angle) - py * math.sin(angle), cy + px * math.sin(angle) + py * math.cos(angle))
                           for px, py in local]
                canvas.line(*rotated[0], *rotated[1], ink, 5.5 if glyph == "I" else 4.2)
    canvas.px[..., :3] *= (0.92 + 0.14 * fbm(gen, (size, size), 5, 5, 3))[..., None]
    canvas.px[..., :3] *= (1 - 0.35 * blotches(gen, (size, size), 4, 0.62, 0.85))[..., None]
    height = 0.6 + 0.0 * canvas.px[..., 0]
    return Raster(canvas.px[..., :3], height)


def hires_art(small, gen, factor=4):
    """Foto ou quadro do kit (64 x 48 px) ampliado e suavizado: papel desbotado sob o vidro, sem degraus de pixel."""
    pixels = np.repeat(np.repeat(small.px, factor, axis=0), factor, axis=1)
    canvas = textures.Canvas(pixels.shape[1], pixels.shape[0])
    canvas.px = pixels.copy()
    canvas.blur(factor // 2 + 1)
    rgb = canvas.px[..., :3] * (0.94 + 0.10 * gen.random(canvas.px.shape[:2]))[..., None]
    height, width = rgb.shape[:2]
    streak = np.clip(1 - np.abs((np.arange(width)[None, :] / width) * 1.2 - (np.arange(height)[:, None] / height) - 0.25) * 9, 0, 1)
    rgb = rgb + 0.05 * streak[..., None]                                   # reflexo do vidro
    return Raster(rgb)


ART_SOURCES = {"photo_trio": ("photo", "trio"), "photo_mother_child": ("photo", "mother_child"),
               "photo_father_child": ("photo", "father_child"), "photo_portrait": ("photo", "portrait"),
               "painting_lake": ("painting", "lake"), "painting_barn": ("painting", "barn"),
               "painting_still": ("painting", "still")}


def _hires(name):
    kind, variant = ART_SOURCES[name]
    draw = textures.draw_family_photo if kind == "photo" else textures.draw_painting
    return lambda rng: hires_art(draw(rng, variant), numpy_generator(rng))


# ---------------------------------------------------------------------------
# Registro de texturas
# ---------------------------------------------------------------------------
def _seeded(function, *args, **kwargs):
    return lambda rng: function(numpy_generator(rng), *args, **kwargs)


textures.TEXTURES.update({
    "sala_walnut": _seeded(wood_veneer, WALNUT),
    "sala_oak": _seeded(wood_veneer, OAK),
    "sala_upholstery": _seeded(upholstery_cloth),
    "sala_velvet": _seeded(velvet_cloth),
    "sala_leather": _seeded(aged_leather),
    "sala_plaid": _seeded(plaid_wool),
    "sala_rug_living": _seeded(persian_rug, rug_shape(*RUG_SIZES["rug_living"])),
    "sala_rug_den": _seeded(persian_rug, rug_shape(*RUG_SIZES["rug_den"]),
                            ((0.10, 0.16, 0.26), (0.55, 0.42, 0.22), (0.58, 0.54, 0.42), (0.05, 0.07, 0.10))),
    "sala_rug_dining": _seeded(persian_rug, rug_shape(*RUG_SIZES["rug_dining"]),
                               ((0.18, 0.20, 0.22), (0.50, 0.42, 0.26), (0.60, 0.56, 0.44), (0.06, 0.09, 0.14))),
    "sala_doormat": _seeded(coir_doormat),
    "sala_rug_pile": _seeded(pile_texture),
    "sala_book_atlas": _seeded(book_atlas),
    "sala_porcelain": _seeded(china_porcelain),
    "sala_linen": _seeded(table_linen),
    "sala_envelope": _seeded(envelope_front),
    "sala_clock_dial": _seeded(clock_dial),
    **{f"art_{name}": _hires(name) for name in ART_SOURCES},
})


# ---------------------------------------------------------------------------
# Materiais
# ---------------------------------------------------------------------------
PILE_TILE = 0.35        # metros por repetição do pelo do tapete


@dataclass(frozen=True)
class Surface:
    """Como um material de superfície é montado a partir de uma imagem de cor + relevo."""
    texture: str
    tile: float = 0.6                 # metros por repetição da textura
    tint: tuple = (1.0, 1.0, 1.0)     # multiplica a imagem (a mesma trama serve a vários tecidos)
    roughness: float = 0.6
    rough_swing: float = 0.25         # quanto a rugosidade varia com a luminância
    specular: float = 0.35
    metallic: float = 0.0
    bump: float = 0.5
    bump_distance: float = 0.003
    coat: float = 0.0                 # verniz sobre a madeira
    sheen: float = 0.0                # penugem do veludo
    rotate: bool = False              # veio na vertical
    box: bool = False                 # projeção em caixa pelas coordenadas do objeto (peças orgânicas, sem UV útil)
    dust: float = 0.0                 # quanto de poeira clara assenta nas faces voltadas para cima (0 a 1)


def _input(bsdf, names):
    return next((bsdf.inputs[n] for n in names if n in bsdf.inputs), None)


def _add_dust(tree, color, roughness, coords, amount):
    """Poeira: nas faces voltadas para cima (normal do mundo) e em manchas, clareia a cor e deixa a superfície áspera."""
    links = tree.links
    normal = tree.nodes.new("ShaderNodeNewGeometry")
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    links.new(normal.outputs["Normal"], split.inputs["Vector"])
    upward = tree.nodes.new("ShaderNodeMapRange")
    upward.inputs["From Min"].default_value, upward.inputs["From Max"].default_value = 0.78, 0.98
    links.new(split.outputs["Z"], upward.inputs["Value"])
    patches = tree.nodes.new("ShaderNodeTexNoise")
    patches.inputs["Scale"].default_value, patches.inputs["Detail"].default_value = 14.0, 5.0
    links.new(coords.outputs["Object"], patches.inputs["Vector"])
    patchy = tree.nodes.new("ShaderNodeMapRange")
    patchy.inputs["From Min"].default_value, patchy.inputs["From Max"].default_value = 0.35, 0.65
    patchy.inputs["To Min"].default_value = 0.35
    links.new(patches.outputs["Fac"], patchy.inputs["Value"])
    mask = tree.nodes.new("ShaderNodeMath")
    mask.operation = "MULTIPLY"
    links.new(upward.outputs["Result"], mask.inputs[0])
    links.new(patchy.outputs["Result"], mask.inputs[1])
    strength = tree.nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    strength.inputs[1].default_value = amount
    links.new(mask.outputs["Value"], strength.inputs[0])
    dusty = tree.nodes.new("ShaderNodeMix")
    dusty.data_type = "RGBA"
    dusty.inputs[7].default_value = (0.40, 0.38, 0.34, 1.0)
    links.new(strength.outputs["Value"], dusty.inputs[0])
    links.new(color, dusty.inputs[6])
    rough = tree.nodes.new("ShaderNodeMath")
    rough.operation = "MULTIPLY_ADD"
    rough.use_clamp = True
    rough.inputs[1].default_value = 0.35
    links.new(strength.outputs["Value"], rough.inputs[0])
    links.new(roughness, rough.inputs[2])
    return dusty.outputs[2], rough.outputs["Value"]


def build_surface(name, spec):
    """Material com imagem Linear, gradiente de rugosidade pela luminância e Bump pelo alfa."""
    mat = compat.new_material(name)
    tree, links = mat.node_tree, mat.node_tree.links
    bsdf = compat.bsdf_of(mat)
    coords = tree.nodes.new("ShaderNodeTexCoord")
    mapping = tree.nodes.new("ShaderNodeMapping")
    scale = 1 / spec.tile
    mapping.inputs["Scale"].default_value = (scale, scale, scale if spec.box else 1.0)
    if spec.rotate:
        mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(90))
    links.new(coords.outputs["Object" if spec.box else "UV"], mapping.inputs["Vector"])
    image = tree.nodes.new("ShaderNodeTexImage")
    image.image = textures.image(spec.texture)
    image.interpolation = "Linear"
    image.extension = "REPEAT"
    if spec.box:
        image.projection, image.projection_blend = "BOX", 0.25
    links.new(mapping.outputs["Vector"], image.inputs["Vector"])

    color = image.outputs["Color"]
    if tuple(spec.tint) != (1.0, 1.0, 1.0):
        tinted = tree.nodes.new("ShaderNodeMix")
        tinted.data_type, tinted.blend_type = "RGBA", "MULTIPLY"
        tinted.inputs[0].default_value = 1.0
        links.new(color, tinted.inputs[6])
        tinted.inputs[7].default_value = (*spec.tint, 1.0)
        color = tinted.outputs[2]
    gray = tree.nodes.new("ShaderNodeRGBToBW")
    links.new(image.outputs["Color"], gray.inputs["Color"])
    ranged = tree.nodes.new("ShaderNodeMapRange")
    ranged.inputs["From Min"].default_value, ranged.inputs["From Max"].default_value = 0.05, 0.75
    ranged.inputs["To Min"].default_value = min(1.0, spec.roughness + spec.rough_swing)
    ranged.inputs["To Max"].default_value = max(0.05, spec.roughness - spec.rough_swing)
    links.new(gray.outputs["Val"], ranged.inputs["Value"])
    roughness = ranged.outputs["Result"]
    if spec.dust:
        color, roughness = _add_dust(tree, color, roughness, coords, spec.dust)
    links.new(color, bsdf.inputs["Base Color"])
    links.new(roughness, bsdf.inputs["Roughness"])

    compat.set_bsdf(bsdf, specular=spec.specular, metallic=spec.metallic)
    coat = _input(bsdf, ("Coat Weight", "Clearcoat"))
    if coat is not None and spec.coat:
        coat.default_value = spec.coat
        rough = _input(bsdf, ("Coat Roughness", "Clearcoat Roughness"))
        if rough is not None:
            rough.default_value = 0.25
    sheen = _input(bsdf, ("Sheen Weight", "Sheen"))
    if sheen is not None and spec.sheen:
        sheen.default_value = spec.sheen
    compat.add_relief(mat, image.outputs["Alpha"], spec.bump, spec.bump_distance)
    mat.diffuse_color = (*(0.5 * c for c in spec.tint), 1.0)
    return mat


def build_rug(name, pattern, size):
    """Tapete: padrão desenhado (uma imagem por tapete, sem repetição) multiplicado pelo pelo curto ladrilhado.

    O UV do tapete vai de 0 a 1 em toda a peça; `size` (m) converte isso em repetições do pelo.
    """
    mat = compat.new_material(name)
    tree, links = mat.node_tree, mat.node_tree.links
    bsdf = compat.bsdf_of(mat)
    coords = tree.nodes.new("ShaderNodeTexCoord")
    pattern_node = tree.nodes.new("ShaderNodeTexImage")
    pattern_node.image = textures.image(pattern)
    pattern_node.interpolation, pattern_node.extension = "Linear", "EXTEND"
    links.new(coords.outputs["UV"], pattern_node.inputs["Vector"])
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (size[0] / PILE_TILE, size[1] / PILE_TILE, 1.0)
    links.new(coords.outputs["UV"], mapping.inputs["Vector"])
    pile = tree.nodes.new("ShaderNodeTexImage")
    pile.image = textures.image("sala_rug_pile")
    pile.interpolation, pile.extension = "Linear", "REPEAT"
    links.new(mapping.outputs["Vector"], pile.inputs["Vector"])
    product = tree.nodes.new("ShaderNodeMix")
    product.data_type, product.blend_type = "RGBA", "MULTIPLY"
    product.inputs[0].default_value = 1.0
    links.new(pattern_node.outputs["Color"], product.inputs[6])
    links.new(pile.outputs["Color"], product.inputs[7])
    links.new(product.outputs[2], bsdf.inputs["Base Color"])
    compat.set_bsdf(bsdf, roughness=0.97, specular=0.05)
    sheen = _input(bsdf, ("Sheen Weight", "Sheen"))
    if sheen is not None:
        sheen.default_value = 0.4
    compat.add_relief(mat, pile.outputs["Alpha"], 0.9, 0.006)
    mat.diffuse_color = (0.25, 0.1, 0.08, 1.0)
    return mat


def build_scuffed_metal(name, color, roughness, metallic=1.0, scale=70.0, bump=0.12):
    """Metal riscado sem imagem: ruído fino no relevo e na rugosidade, para o brilho não ser uma cor chapada."""
    mat = compat.new_material(name)
    tree, links = mat.node_tree, mat.node_tree.links
    bsdf = compat.bsdf_of(mat)
    coords = tree.nodes.new("ShaderNodeTexCoord")
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.7
    links.new(coords.outputs["Object"], noise.inputs["Vector"])
    ranged = tree.nodes.new("ShaderNodeMapRange")
    ranged.inputs["To Min"].default_value, ranged.inputs["To Max"].default_value = roughness + 0.18, max(0.05, roughness - 0.12)
    links.new(noise.outputs["Fac"], ranged.inputs["Value"])
    links.new(ranged.outputs["Result"], bsdf.inputs["Roughness"])
    bump_node = tree.nodes.new("ShaderNodeBump")
    bump_node.inputs["Strength"].default_value, bump_node.inputs["Distance"].default_value = bump, 0.0006
    links.new(noise.outputs["Fac"], bump_node.inputs["Height"])
    links.new(bump_node.outputs["Normal"], bsdf.inputs["Normal"])
    compat.set_bsdf(bsdf, base_color=color, metallic=metallic, specular=0.5)
    mat.diffuse_color = (*color, 1.0)
    return mat


SURFACES = {
    "walnut": Surface("sala_walnut", 0.6, roughness=0.42, specular=0.45, bump=0.45, coat=0.25, dust=0.2),
    "walnut_v": Surface("sala_walnut", 0.6, roughness=0.42, specular=0.45, bump=0.45, coat=0.25, rotate=True, dust=0.2),
    "oak": Surface("sala_oak", 0.6, roughness=0.5, specular=0.4, bump=0.5, coat=0.18, dust=0.2),
    "oak_v": Surface("sala_oak", 0.6, roughness=0.5, specular=0.4, bump=0.5, coat=0.18, rotate=True, dust=0.2),
    "sofa_fabric": Surface("sala_upholstery", 0.45, tint=(0.34, 0.42, 0.56), roughness=0.9, rough_swing=0.12,
                           specular=0.12, bump=0.7, bump_distance=0.002, sheen=0.35, box=True, dust=0.12),
    "armchair_fabric": Surface("sala_upholstery", 0.45, tint=(0.38, 0.41, 0.30), roughness=0.9, rough_swing=0.12,
                               specular=0.12, bump=0.7, bump_distance=0.002, sheen=0.3, box=True, dust=0.12),
    "velvet_burgundy": Surface("sala_velvet", 0.4, tint=(0.28, 0.03, 0.05), roughness=0.9, rough_swing=0.1,
                               specular=0.15, bump=0.5, sheen=0.25, box=True),
    "velvet_pink": Surface("sala_velvet", 0.4, tint=(0.55, 0.30, 0.36), roughness=0.9, rough_swing=0.1,
                           specular=0.15, bump=0.5, sheen=0.25, box=True),
    "leather_aged": Surface("sala_leather", 0.5, tint=(0.52, 0.30, 0.18), roughness=0.5, rough_swing=0.25,
                            specular=0.4, bump=0.9, bump_distance=0.002, coat=0.15, box=True, dust=0.12),
    "leather_black": Surface("sala_leather", 0.5, tint=(0.16, 0.15, 0.15), roughness=0.45, rough_swing=0.25,
                             specular=0.45, bump=0.9, bump_distance=0.002, coat=0.2, box=True),
    "wool_plaid": Surface("sala_plaid", 0.32, roughness=0.95, rough_swing=0.05, specular=0.05, bump=1.0,
                          bump_distance=0.003, sheen=0.5, box=True),
    "book_atlas": Surface("sala_book_atlas", 1.0, roughness=0.6, rough_swing=0.2, specular=0.3, bump=0.8,
                          bump_distance=0.0015),
    "tablecloth": Surface("sala_linen", 0.5, roughness=0.95, rough_swing=0.05, specular=0.05, bump=0.8, bump_distance=0.002,
                          box=True),
    "porcelain_old": Surface("sala_porcelain", 0.45, roughness=0.2, rough_swing=0.1, specular=0.6, bump=0.15,
                             bump_distance=0.0005, coat=0.4),
    "envelope": Surface("sala_envelope", 1.0, roughness=0.85, specular=0.1, bump=0.0),
    **{f"art_{name}": Surface(f"art_{name}", 1.0, roughness=0.3, rough_swing=0.0, specular=0.6, bump=0.0) for name in ART_SOURCES},
    "clock_dial": Surface("sala_clock_dial", 1.0, roughness=0.55, specular=0.3, bump=0.0),
}

materials.SPECS.update({
    "dust_cloth": materials.Spec(color=(0.015, 0.014, 0.013), roughness=0.95),
    "lampshade_pleated": materials.Spec(color=(0.52, 0.42, 0.26), roughness=0.9, emission=1.4,
                                        emit_color=(1.0, 0.70, 0.36)),
    "glass_green": materials.Spec(color=(0.01, 0.07, 0.03), roughness=0.08, emission=0.10, emit_color=(0.20, 0.8, 0.35)),
    "wine_dark": materials.Spec(color=(0.025, 0.004, 0.008), roughness=0.1),
    "cut_crystal": materials.Spec(color=(0.62, 0.66, 0.68), roughness=0.04, alpha=0.3),
    "napkin_cloth": materials.Spec(color=(0.55, 0.50, 0.40), roughness=0.95),
    "rug_fringe": materials.Spec(color=(0.45, 0.40, 0.30), roughness=0.95),
    "food_old": materials.Spec(color=(0.085, 0.06, 0.03), roughness=0.85),
    "coffee_cold": materials.Spec(color=(0.045, 0.022, 0.010), roughness=0.22),
})

for _name, _color, _roughness in (("brass_aged", (0.42, 0.30, 0.11), 0.38), ("gilt", (0.58, 0.44, 0.17), 0.3),
                                  ("steel_filing", (0.17, 0.19, 0.17), 0.5)):
    materials.register_builder(_name, lambda n=_name, c=_color, r=_roughness: build_scuffed_metal(
        n, c, r, metallic=0.7 if n == "steel_filing" else 1.0))
for _name, _spec in SURFACES.items():
    materials.register_builder(_name, lambda n=_name, s=_spec: build_surface(n, s))
for _name, _pattern in (("rug_living", "sala_rug_living"), ("rug_den", "sala_rug_den"), ("rug_dining", "sala_rug_dining")):
    materials.register_builder(_name, lambda n=_name, p=_pattern: build_rug(n, p, RUG_SIZES[n]))
materials.register_builder("doormat", lambda: build_rug("doormat", "sala_doormat", (0.9, 0.6)))
