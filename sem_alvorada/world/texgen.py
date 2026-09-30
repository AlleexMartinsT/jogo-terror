"""Geradores de textura procedural em numpy.

Convenção: todas as funções devolvem `float32` de forma (altura, largura, 3) em cor LINEAR
(a conversão para sRGB acontece quando a imagem é criada, em `materials`). A linha 0 é a de
baixo da imagem, como no Blender, então "topo" significa índices de linha maiores.

Os ruídos são ladrilháveis: as bordas opostas se encontram, para que a repetição no
mundo (projeção em caixa) não deixe emendas.
"""
import zlib

import numpy as np


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
        total += amplitude * value_noise(rng, width, height, cells * scale,
                                         (cells_y or cells) * scale)
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


def scratches(rng, width, height, count, length):
    """Riscos retos e curtos em direções aleatórias."""
    mask = np.zeros((height, width))
    for _ in range(count):
        x, y = rng.random() * width, rng.random() * height
        angle = rng.random() * np.pi
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
    return _smooth((field - 0.42) / (softness * 0.6))


def _smooth(t):
    return _fade(np.clip(t, 0, 1))


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


def _rows(height):
    """Coordenada vertical normalizada de cada linha (0 embaixo, 1 no topo)."""
    return ((np.arange(height) + 0.5) / height)[:, None]


def _cols(width):
    return ((np.arange(width) + 0.5) / width)[None, :]


# --------------------------------------------------------------------------
# Paredes
# --------------------------------------------------------------------------
def wallpaper(rng, size=128, base=(0.27, 0.245, 0.195)):
    """Papel de parede listrado e desbotado, com um rosetão pequeno em cada faixa clara."""
    xs = np.arange(size)[None, :].repeat(size, 0)
    ys = np.arange(size)[:, None].repeat(size, 1)
    band = (xs % 16) < 8
    edge = ((xs % 16) == 0) | ((xs % 16) == 8)
    image = solid(size, size, base)
    image = gain(image, np.where(band, 1.0, 0.78))
    image = gain(image, np.where(edge, 0.66, 1.0))
    motif_x, motif_y = (xs % 16) - 4, (ys % 32) - 16
    rosette = (np.abs(motif_x) + np.abs(motif_y) * 0.55 < 3.2) & band
    image = lerp(image, tint(image, (0.62, 0.78, 0.70)), rosette * 0.85)
    image = gain(image, 0.9 + 0.2 * fbm(rng, size, size, 4, 3))
    image = gain(image, 1 + speckle(rng, size, size, 0.05))
    return finish(image)


def paint_dirty(rng, size=128, base=(0.215, 0.245, 0.205), plaster=(0.36, 0.34, 0.29)):
    """Tinta lascada: manchas fosco/brilho, fissuras e placas soltas mostrando o reboco."""
    image = gain(solid(size, size, base), 0.82 + 0.36 * fbm(rng, size, size, 3, 4))
    peel = fbm(rng, size, size, 4, 3)
    peeled = peel > 0.72
    rim = (peel > 0.69) & ~peeled
    image = np.where(peeled[..., None], plaster * (0.6 + 0.4 * peel[..., None]), image)
    image = gain(image, np.where(rim, 0.55, 1.0))
    edges, second = worley(rng, size, size, 9)
    crack_lines = ((second - edges) < 0.9) & (rng.random((size, size)) < 0.5) & (peel > 0.45)
    image = gain(image, np.where(crack_lines, 0.45, 1.0))
    image = gain(image, 1 + speckle(rng, size, size, 0.06))
    return finish(image)


def _tile_grid(size, count, grout):
    """Índices de ladrilho (ix, iy), posição interna (fx, fy) em px e máscara de rejunte."""
    step = size // count
    pos = np.arange(size)
    ix, iy = (pos // step)[None, :].repeat(size, 0), (pos // step)[:, None].repeat(size, 1)
    fx, fy = (pos % step)[None, :].repeat(size, 0), (pos % step)[:, None].repeat(size, 1)
    is_grout = (fx < grout) | (fy < grout)
    return ix, iy, fx, fy, is_grout, step


def bathroom_wall_tile(rng, size=128, count=8, base=(0.40, 0.44, 0.415)):
    """Azulejo com bisel, rejunte escuro, rachaduras, azulejos manchados e escorridos de água."""
    ix, iy, fx, fy, grout, step = _tile_grid(size, count, 2)
    per_tile = 0.9 + 0.2 * rng.random((count, count))
    image = gain(solid(size, size, base), per_tile[iy, ix])
    bevel = np.where(fy >= step - 2, 1.25, np.where(fy < 4, 0.8, 1.0)) * np.where(fx >= step - 2, 0.85, 1.0)
    image = gain(image, bevel)
    stained = rng.random((count, count)) < 0.12
    image = lerp(image, tint(image, (0.75, 0.62, 0.45)), (stained[iy, ix] * 0.55).astype(np.float32))
    slash = (rng.random((count, count)) < 0.10)[iy, ix] & (np.abs(fx - fy) < 1)
    image = gain(image, np.where(slash, 0.4, 1.0))
    streaks = value_noise(rng, size, size, 24, 2)
    image = gain(image, 0.84 + 0.2 * streaks)
    image = np.where(grout[..., None], solid(size, size, (0.20, 0.21, 0.185)) * (0.75 + 0.4 * rng.random((size, size, 1))), image)
    return finish(image)


def garage_block(rng, size=128, base=(0.20, 0.21, 0.205)):
    """Bloco de concreto pintado: 8 fiadas de 0,2 m, blocos de 0,4 m, tinta descascando."""
    rows, block = 8, 32
    row_height = size // rows
    ys = np.arange(size)[:, None].repeat(size, 1)
    xs = np.arange(size)[None, :].repeat(size, 0)
    row_id = ys // row_height
    shifted = (xs + (row_id % 2) * (block // 2)) % size
    block_id = shifted // block
    mortar = ((ys % row_height) < 1) | ((shifted % block) < 1)
    per_block = 0.85 + 0.3 * rng.random((rows, size // block))
    image = gain(solid(size, size, base), per_block[row_id, block_id])
    peel = fbm(rng, size, size, 4, 3)
    image = np.where((peel > 0.70)[..., None], solid(size, size, (0.27, 0.265, 0.245)) * (0.7 + 0.4 * peel[..., None]), image)
    image = gain(image, 0.85 + 0.25 * fbm(rng, size, size, 8, 3))
    image = gain(image, 1 + speckle(rng, size, size, 0.07))
    image = np.where(mortar[..., None], solid(size, size, (0.09, 0.09, 0.085)), image)
    return finish(image)


def brick(rng, size=96, base=(0.225, 0.095, 0.065)):
    """Tijolo aparente em amarração corrente: fiadas de 8 px e tijolos de 24 px."""
    row_height, length = 8, 24
    ys = np.arange(size)[:, None].repeat(size, 1)
    xs = np.arange(size)[None, :].repeat(size, 0)
    row_id = ys // row_height
    shifted = (xs + (row_id % 2) * (length // 2)) % size
    brick_id = shifted // length
    mortar = ((ys % row_height) == 0) | ((shifted % length) == 0)
    per_brick = 0.65 + 0.7 * rng.random((size // row_height, size // length))
    image = gain(solid(size, size, base), per_brick[row_id, brick_id])
    image = tint(image, (1.0, 0.95, 0.92)) * (0.85 + 0.3 * fbm(rng, size, size, 6, 3))[..., None]
    image = gain(image, 1 + speckle(rng, size, size, 0.12))
    soot = value_noise(rng, size, size, 3, 2)
    image = gain(image, 0.75 + 0.3 * soot)
    image = np.where(mortar[..., None], solid(size, size, (0.26, 0.25, 0.22)) * (0.7 + 0.5 * rng.random((size, size, 1))), image)
    return finish(image)


def clapboard(rng, size=64, boards=4, base=(0.305, 0.315, 0.275)):
    """Revestimento de tábuas sobrepostas: fio de luz em cima, sombra embaixo, veios e fuligem."""
    board = size // boards
    ys = np.arange(size)[:, None].repeat(size, 1)
    within = ys % board
    board_id = ys // board
    image = solid(size, size, base)
    image = gain(image, (0.86 + 0.28 * rng.random(boards))[board_id])
    shading = np.where(within >= board - 2, 1.28, np.where(within < 3, 0.55, 0.9 + 0.1 * within / board))
    image = gain(image, shading)
    grain = value_noise(rng, size, size, 4, size)
    image = gain(image, 0.9 + 0.2 * grain)
    grime = value_noise(rng, size, size, 12, 2)
    image = gain(image, 0.8 + 0.3 * grime)
    joints = (np.arange(size)[None, :] == (board_id * 23 + 9) % size) & (within > 1)
    image = gain(image, np.where(joints, 0.5, 1.0))
    return finish(image)


# --------------------------------------------------------------------------
# Pisos
# --------------------------------------------------------------------------
def wood_planks(rng, size=128, base=(0.27, 0.17, 0.095), planks=8, vertical=False):
    """Tábuas corridas: cada tábua com tom próprio, uma emenda, veios e riscos de uso."""
    plank = size // planks
    ys = np.arange(size)[:, None].repeat(size, 1)
    xs = np.arange(size)[None, :].repeat(size, 0)
    plank_id = ys // plank
    joint = (rng.random(planks) * 0.6 + 0.2) * size
    side = (xs > joint[plank_id]).astype(int)
    tones = 0.75 + 0.5 * rng.random((planks, 2))
    image = gain(solid(size, size, base), tones[plank_id, side])
    grain = value_noise(rng, size, size, 3, size // 2)
    image = gain(image, 0.78 + 0.4 * grain)
    image = tint(image, (1.0, 0.97, 0.93))
    seam = ((ys % plank) == 0) | (xs == joint[plank_id].astype(int))
    image = gain(image, np.where(seam, 0.4, 1.0))
    image = gain(image, np.where((ys % plank) == plank - 1, 1.15, 1.0))
    image = gain(image, 0.85 + 0.2 * fbm(rng, size, size, 3, 3))
    image = lerp(image, image * 1.6, scratches(rng, size, size, 14, 12) * 0.35)
    image = gain(image, 1 + speckle(rng, size, size, 0.03))
    return finish(image.transpose(1, 0, 2) if vertical else image)


def carpet(rng, size=64, base=(0.155, 0.16, 0.125)):
    """Carpete gasto: fibra por pixel, trama diagonal e áreas achatadas."""
    xs = np.arange(size)[None, :].repeat(size, 0)
    ys = np.arange(size)[:, None].repeat(size, 1)
    image = solid(size, size, base)
    image = gain(image, 1 + speckle(rng, size, size, 0.16))
    image = gain(image, 1 + 0.05 * np.sin((xs + ys) * np.pi / 2))
    image = gain(image, 0.82 + 0.3 * fbm(rng, size, size, 3, 3))
    return finish(image)


def linoleum(rng, size=128, light=(0.30, 0.275, 0.195), dark=(0.20, 0.165, 0.115)):
    """Linóleo xadrez de cozinha, com riscos, desgaste e cantos lascados."""
    ix, iy, fx, fy, grout, step = _tile_grid(size, 4, 1)
    checker = ((ix + iy) % 2 == 0)[..., None]
    image = np.where(checker, solid(size, size, light), solid(size, size, dark))
    image = gain(image, 0.85 + 0.3 * rng.random((4, 4))[iy, ix])
    image = gain(image, 0.75 + 0.35 * fbm(rng, size, size, 4, 4))
    image = lerp(image, image * 1.5, scratches(rng, size, size, 22, 10) * 0.3)
    chips = (rng.random((size, size)) < 0.004) * 0.6
    image = gain(image, 1 - chips)
    image = gain(image, np.where(grout, 0.55, 1.0))
    return finish(image)


def bathroom_floor_tile(rng, size=128, base=(0.355, 0.395, 0.395)):
    """Mosaico de azulejo 8x8 com peças escuras em xadrez ralo e rejunte encardido."""
    ix, iy, fx, fy, grout, step = _tile_grid(size, 8, 2)
    image = gain(solid(size, size, base), (0.88 + 0.24 * rng.random((8, 8)))[iy, ix])
    accent = (ix + iy) % 4 == 0
    image = lerp(image, image * np.array((0.55, 0.62, 0.72), np.float32), accent * 0.8)
    image = gain(image, 0.8 + 0.3 * fbm(rng, size, size, 4, 4))
    image = gain(image, np.where(cracks(rng, size, size, 3, 22), 0.4, 1.0))
    image = np.where(grout[..., None], solid(size, size, (0.11, 0.115, 0.10)) * (0.7 + 0.6 * rng.random((size, size, 1))), image)
    return finish(image)


def concrete(rng, size=128, base=(0.225, 0.225, 0.212), joint=True):
    """Concreto: mosqueado, poros escuros, fissuras e uma junta de dilatação na borda."""
    image = gain(solid(size, size, base), 0.78 + 0.4 * fbm(rng, size, size, 4, 5))
    pores = rng.random((size, size)) < 0.025
    image = gain(image, np.where(pores, 0.5, 1.0))
    image = gain(image, np.where(cracks(rng, size, size, 4, 60, 0.35), 0.4, 1.0))
    image = gain(image, 1 + speckle(rng, size, size, 0.05))
    if joint:
        edge = (np.arange(size)[None, :] == 0) | (np.arange(size)[:, None] == 0)
        image = gain(image, np.where(edge, 0.35, 1.0))
    return finish(image)


def ceiling_plaster(rng, size=64, base=(0.46, 0.45, 0.405)):
    """Forro de gesso com textura de spray e pontinhos de mofo."""
    image = gain(solid(size, size, base), 0.9 + 0.16 * fbm(rng, size, size, 4, 3))
    image = gain(image, 1 + speckle(rng, size, size, 0.05))
    mold = rng.random((size, size)) < 0.004
    image = gain(image, np.where(mold, 0.7, 1.0))
    return finish(image)


def shingles(rng, size=96, base=(0.075, 0.075, 0.08)):
    """Telha de asfalto em três abas: fiadas de 12 px, abas de 32 px, musgo e abas desbotadas."""
    course, tab = 12, 32
    ys = np.arange(size)[:, None].repeat(size, 1)
    xs = np.arange(size)[None, :].repeat(size, 0)
    course_id = ys // course
    shifted = (xs + (course_id * 11) % tab) % size
    tab_id = shifted // tab
    tones = 0.7 + 0.6 * rng.random((size // course, size // tab))
    image = gain(solid(size, size, base), tones[course_id, tab_id])
    within = ys % course
    image = gain(image, np.where(within < 3, 0.55, np.where(within >= course - 2, 1.2, 1.0)))
    image = gain(image, np.where((shifted % tab) == 0, 0.35, 1.0))
    granules = 1 + speckle(rng, size, size, 0.28)
    image = gain(image, granules)
    moss = fbm(rng, size, size, 3, 3)
    image = lerp(image, np.array((0.055, 0.075, 0.05), np.float32) * (0.7 + 0.6 * moss[..., None]), (moss > 0.74) * 0.5)
    return finish(image)


def wood_stairs(rng, size=128, base=(0.15, 0.09, 0.05)):
    """Degrau de madeira escura: veios ao longo de X, pontos claros de uso nas bordas."""
    image = gain(solid(size, size, base), 0.7 + 0.5 * value_noise(rng, size, size, 3, size // 2))
    image = gain(image, 0.8 + 0.3 * fbm(rng, size, size, 3, 3))
    image = lerp(image, image * 1.7, scratches(rng, size, size, 16, 16) * 0.3)
    return finish(gain(image, 1 + speckle(rng, size, size, 0.04)))


# --------------------------------------------------------------------------
# Portas, madeiras e acabamentos
# --------------------------------------------------------------------------
def door_wood(rng, width=128, height=256, base=(0.14, 0.08, 0.05)):
    """Folha de porta (uma repetição por folha de 0,9 x 2,05 m): veio vertical, sujeira no puxador
    e a parte de baixo riscada pelos pés."""
    image = gain(solid(width, height, base), 0.68 + 0.6 * value_noise(rng, width, height, width // 5, 3))
    image = gain(image, 0.85 + 0.3 * fbm(rng, width, height, 3, 3, 0.5, cells_y=5))
    v, u = _rows(height), _cols(width)
    smudge = np.exp(-(((u - 0.9) / 0.10) ** 2 + ((v - 0.49) / 0.06) ** 2))
    image = gain(image, 1 - 0.35 * smudge)
    kick = np.clip((0.16 - v) / 0.16, 0, 1) * np.ones_like(u)
    image = lerp(image, image * 1.5, kick * scratches(rng, width, height, 40, 14) * 0.5)
    image = gain(image, 1 - 0.3 * kick)
    return finish(gain(image, 1 + speckle(rng, width, height, 0.03)))


def trim_paint(rng, size=64, base=(0.47, 0.45, 0.395)):
    """Tinta branca envelhecida de rodapés e batentes, amarelada com lascas de madeira."""
    image = gain(solid(size, size, base), 0.82 + 0.26 * fbm(rng, size, size, 3, 3))
    image = tint(image, (1.0, 0.98, 0.9))
    image = gain(image, 0.95 + 0.1 * value_noise(rng, size, size, 2, size // 2))
    chips = rng.random((size, size)) < 0.012
    image = np.where(chips[..., None], solid(size, size, (0.12, 0.08, 0.05)), image)
    return finish(gain(image, 1 + speckle(rng, size, size, 0.03)))


def curtain_fabric(rng, size=64, base=(0.165, 0.125, 0.105)):
    """Tecido de cortina desbotado pelo sol: trama de fios e faixas de mofo na barra."""
    xs = np.arange(size)[None, :].repeat(size, 0)
    ys = np.arange(size)[:, None].repeat(size, 1)
    weave = 0.92 + 0.08 * (((xs // 2) + (ys // 2)) % 2)
    image = gain(solid(size, size, base), weave)
    image = gain(image, 0.75 + 0.4 * fbm(rng, size, size, 2, 3))
    fade = value_noise(rng, size, size, 2, 2)
    image = lerp(image, tint(image, (1.25, 1.2, 1.1)), fade * 0.35)
    mildew = value_noise(rng, size, size, 8, 3) * (1 - _rows(size)) ** 1.5
    return finish(gain(image, 1 - 0.35 * np.clip(mildew * 1.6 - 0.3, 0, 1)))


def garage_door_paint(rng, size=64, base=(0.30, 0.30, 0.285)):
    """Chapa pintada do portão: amassados suaves e veios de ferrugem escorrendo pela parte baixa."""
    image = gain(solid(size, size, base), 0.78 + 0.34 * fbm(rng, size, size, 3, 3))
    streaks = value_noise(rng, size, size, 14, 2) * (1 - _rows(size)) ** 0.8
    rust = np.clip((streaks - 0.42) * 3.0, 0, 1)
    image = lerp(image, np.array((0.16, 0.085, 0.05), np.float32) * (0.7 + 0.5 * streaks[..., None]), rust * 0.7)
    return finish(gain(image, 1 + speckle(rng, size, size, 0.04)))


# --------------------------------------------------------------------------
# Exterior
# --------------------------------------------------------------------------
def asphalt(rng, size=128, base=(0.055, 0.055, 0.06)):
    image = gain(solid(size, size, base), 0.7 + 0.6 * fbm(rng, size, size, 4, 4))
    aggregate = rng.random((size, size))
    image = gain(image, np.where(aggregate > 0.93, 1.9, np.where(aggregate < 0.05, 0.5, 1.0)))
    image = gain(image, np.where(cracks(rng, size, size, 3, 70, 0.3), 0.35, 1.0))
    patch = np.zeros((size, size))
    patch[30:62, 20:100] = 1.0
    image = gain(image, 1 - 0.25 * patch)
    return finish(image)


def road_paint(rng, size=64, base=(0.55, 0.47, 0.16)):
    image = gain(solid(size, size, base), 0.55 + 0.6 * fbm(rng, size, size, 3, 3))
    return finish(gain(image, np.where(rng.random((size, size)) < 0.12, 0.3, 1.0)))


def dead_grass(rng, size=64, base=(0.095, 0.09, 0.055)):
    image = gain(solid(size, size, base), 0.55 + 0.9 * fbm(rng, size, size, 5, 4))
    blades = rng.random((size, size))
    image = gain(image, np.where(blades > 0.9, 1.6, np.where(blades < 0.12, 0.45, 1.0)))
    return finish(image)


def sidewalk(rng, size=128, base=(0.235, 0.235, 0.22)):
    image = concrete(rng, size, base, joint=True)
    image = gain(image, 0.85 + 0.2 * fbm(rng, size, size, 3, 3))
    return finish(image)


def bark(rng, size=64, base=(0.075, 0.055, 0.045)):
    furrows = value_noise(rng, size, size, 10, 3)
    image = gain(solid(size, size, base), 0.35 + 1.1 * furrows)
    return finish(gain(image, 1 + speckle(rng, size, size, 0.08)))


def picket_paint(rng, size=64, base=(0.36, 0.355, 0.32)):
    wood = np.array((0.14, 0.10, 0.07), np.float32)
    image = gain(solid(size, size, base), 0.8 + 0.3 * fbm(rng, size, size, 3, 3))
    worn = fbm(rng, size, size, 4, 3)
    image = lerp(image, wood * (0.7 + 0.6 * value_noise(rng, size, size, 3, size // 2))[..., None], (worn > 0.6) * 0.85)
    return finish(image)


# --------------------------------------------------------------------------
# Camadas de sujeira multiplicativas (aplicadas sobre qualquer material da casa)
# --------------------------------------------------------------------------
def wall_grime_overlay(rng, width=256, height=128):
    """8 m x 2,8 m: sujeira rente ao piso, fumaça no teto, manchas de infiltração e escorridos."""
    v, u = _rows(height), _cols(width)
    ramp_floor = 0.5 + 0.5 * _smooth(v / 0.3)
    ramp_ceiling = 1 - 0.22 * _smooth((v - 0.8) / 0.2)
    haze = 0.86 + 0.24 * fbm(rng, width, height, 4, 3)
    result = ramp_floor * ramp_ceiling * haze
    damp = blobs(rng, width, height, 7, 30, 0.6) * _smooth((v - 0.55) / 0.25)
    core = _smooth((damp - 0.35) / 0.3)
    rim = np.clip(1 - np.abs(damp - 0.42) / 0.06, 0, 1)
    drips = value_noise(rng, width, height, 90, 2) > 0.62
    drip_fade = _smooth(damp * 3) * _smooth((0.75 - v) / 0.25 + 0.3)
    result = result * (1 - 0.32 * core) * (1 - 0.25 * rim) * (1 - 0.3 * drips * drip_fade)
    stain_rgb = np.array((1.0, 0.96, 0.88), np.float32)
    image = result[..., None] * (1 - core[..., None] * (1 - stain_rgb))
    return finish(image)


def floor_grime_overlay(rng, size=128):
    """8 m x 8 m: sujeira de trânsito, poças secas e manchas escuras."""
    image = 0.8 + 0.28 * fbm(rng, size, size, 3, 4)
    wet = blobs(rng, size, size, 5, 16, 0.6)
    dark = blobs(rng, size, size, 3, 8, 0.5)
    image = image * (1 - 0.2 * wet) * (1 - 0.28 * dark)
    return finish(np.repeat(image[..., None], 3, axis=2) * np.array((1.0, 0.98, 0.94), np.float32))


# --------------------------------------------------------------------------
# Granulado genérico para os materiais básicos da paleta
# --------------------------------------------------------------------------
def grit(rng, size=64):
    """Cinza multiplicativo sutil (média ~0,9) que tira o aspecto de plástico das cores lisas."""
    image = 0.82 + 0.2 * fbm(rng, size, size, 4, 3)
    image = image * (1 + speckle(rng, size, size, 0.07))
    return finish(np.repeat(image[..., None], 3, axis=2))


def wood_grain(rng, size=64):
    """Veio de madeira em tons de cinza para os móveis (multiplica a cor da paleta)."""
    image = 0.6 + 0.6 * value_noise(rng, size, size, 4, size // 2)
    image = image * (0.88 + 0.2 * fbm(rng, size, size, 3, 3))
    return finish(np.repeat(np.clip(image, 0, 1.1)[..., None], 3, axis=2))


def fabric_weave(rng, size=64):
    xs = np.arange(size)[None, :].repeat(size, 0)
    ys = np.arange(size)[:, None].repeat(size, 1)
    image = 0.85 + 0.1 * (((xs // 2) + (ys // 2)) % 2) + speckle(rng, size, size, 0.05)
    image = image * (0.85 + 0.25 * fbm(rng, size, size, 4, 3))
    return finish(np.repeat(np.clip(image, 0, 1)[..., None], 3, axis=2))
