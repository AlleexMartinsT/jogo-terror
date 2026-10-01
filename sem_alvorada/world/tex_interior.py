"""Texturas das paredes, forros, rodapés e camadas de sujeira da casa (cor, relevo e rugosidade).

Cada função devolve um `texgen.Maps`. O envelhecimento segue a história: uma casa de vinte anos com
infiltração no teto, tinta que lasca, papel desbotado e rejunte encardido.
"""
import numpy as np

from . import texgen as T
from .texgen import Maps


def _rim(mask, width):
    """Faixa em volta de uma máscara suave: o relevo de borda de tinta lascada."""
    return np.clip(T.blur(mask, width) * 2.2 - mask * 1.2, 0, 1)


# --------------------------------------------------------------------------
# Paredes
# --------------------------------------------------------------------------
def wallpaper(rng, size=512, base=(0.275, 0.25, 0.20)):
    """Papel de parede listrado de dois rolos de 0,53 m (1,06 m de tela), desbotado e amarelado.

    Quatro repetições do motivo por tela: faixa larga clara com losango e folhas, filetes verdes, emenda
    levemente aberta no meio e na borda. Relevo: o estampado em relevo do vinil.
    """
    u, v = T.unit_grid(size, size)
    repeat = 4
    ux, uy = (u * repeat) % 1.0, (v * repeat) % 1.0
    d, dy = np.abs(ux - 0.5), np.abs(uy - 0.5)
    wide = T.threshold(0.30 - d, 0.0, 0.012)
    pins = np.maximum(np.exp(-((d - 0.37) / 0.014) ** 2), 0.7 * np.exp(-((d - 0.44) / 0.007) ** 2))
    diamond = T.threshold(1.0 - (d / 0.13 + dy / 0.22), 0.0, 0.06)
    leaf_a = T.threshold(1.0 - (np.hypot((d - 0.20) / 0.07, (dy - 0.02) / 0.16)), 0.0, 0.08)
    motif = np.clip(diamond + leaf_a * (1 - diamond), 0, 1)
    cream, sage, olive = np.array(base, np.float32) * 1.18, np.array(base, np.float32) * (0.80, 0.86, 0.80), \
        np.array((0.165, 0.19, 0.135), np.float32)
    image = T.lerp(np.broadcast_to(sage, (size, size, 3)).copy(), np.broadcast_to(cream, (size, size, 3)).copy(), wide)
    image = T.lerp(image, np.array((0.20, 0.25, 0.19), np.float32), motif * wide * 0.8)
    image = T.lerp(image, olive, pins * 0.85)
    seam = np.exp(-((((u * 2) % 1.0) - 0.0) * size / 2.2) ** 2) + np.exp(-((((u * 2) % 1.0) - 1.0) * size / 2.2) ** 2)
    sun = T.fbm(rng, size, size, 3, 4)
    image = T.gain(image, 0.86 + 0.28 * sun)
    image = T.lerp(image, T.tint(image, (1.12, 1.0, 0.72)), T.threshold(T.fbm(rng, size, size, 4, 3), 0.55, 0.3) * 0.6)
    fibre = T.blur(rng.random((size, size)), 0.7) * 2 - 1
    image = T.gain(image, 1 + fibre * 0.10)
    image = T.gain(image, 1 - 0.20 * np.clip(seam, 0, 1))
    height = 0.50 + 0.14 * motif * wide + 0.06 * wide - 0.12 * pins - 0.22 * np.clip(seam, 0, 1) + 0.05 * fibre
    rough = 0.62 + 0.28 * (1 - wide) + 0.10 * T.fbm(rng, size, size, 5, 3)
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))


def paint_dirty(rng, size=512, base=(0.215, 0.245, 0.205), plaster=(0.36, 0.34, 0.29)):
    """Tinta de parede lascada: casca de laranja do rolo, placas soltas mostrando o reboco, fissuras."""
    roller = T.blur(rng.random((size, size)), 0.9) * 2 - 1
    tone = 0.82 + 0.36 * T.fbm(rng, size, size, 3, 4)
    paint = T.gain(T.solid(size, size, base), tone * (1 + roller * 0.10))
    field = T.fbm(rng, size, size, 4, 6, 0.58)
    peeled = T.threshold(field, 0.69, 0.018)
    rim = np.clip(T.threshold(field, 0.655, 0.018) - peeled, 0, 1)
    bare = T.gain(T.solid(size, size, plaster), 0.62 + 0.55 * T.fbm(rng, size, size, 8, 4))
    edges, second, _ = T.cellular(rng, size, size, 7)
    crack = T.threshold(0.045 - (second - edges), 0.0, 0.025) * T.threshold(field, 0.42, 0.2)
    crack = np.maximum(crack, T.blur(T.branching_cracks(rng, size, size, 5, 120), 0.6) * 2.2)
    crack = np.clip(crack, 0, 1)
    image = T.lerp(paint, bare, peeled)
    image = T.gain(image, 1 - 0.40 * rim)
    image = T.gain(image, 1 - 0.55 * crack)
    stains = T.blobs(rng, size, size, 4, size * 0.09, 0.8)
    image = T.lerp(image, T.tint(image, (0.82, 0.78, 0.60)), stains * 0.5)
    height = 0.60 + 0.05 * roller - 0.24 * peeled + 0.10 * rim - 0.22 * crack + 0.05 * (peeled * roller)
    rough = 0.50 + 0.18 * T.fbm(rng, size, size, 5, 3) + 0.34 * peeled + 0.1 * rim
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))


def _tile_cells(size, count, grout):
    """Posição interna (fx, fy) em pixels, ladrilho (ix, iy) e distância à borda do ladrilho."""
    step = size // count
    pos = np.arange(size)
    ix, iy = (pos // step)[None, :].repeat(size, 0), (pos // step)[:, None].repeat(size, 1)
    fx, fy = (pos % step)[None, :].repeat(size, 0), (pos % step)[:, None].repeat(size, 1)
    edge = np.minimum(np.minimum(fx, fy), np.minimum(step - 1 - fx, step - 1 - fy)) - grout / 2.0
    return ix, iy, edge, step


def bathroom_wall_tile(rng, size=512, count=8, base=(0.40, 0.44, 0.415)):
    """Azulejo 15 cm com bisel, craquelê no esmalte, rejunte encardido, azulejos manchados e uma peça rachada."""
    grout_px = 5
    ix, iy, edge, step = _tile_cells(size, count, grout_px)
    face = T.smooth(edge / 4.0)
    per_tile = 0.9 + 0.2 * rng.random((count, count))
    image = T.gain(T.solid(size, size, base), per_tile[iy, ix])
    bevel_light = np.clip(1.0 - np.abs(edge - 1.5) / 2.0, 0, 1) * 0.25
    image = T.gain(image, 1 + bevel_light - 0.30 * (edge < 0.5))
    craze, craze2, _ = T.cellular(rng, size, size, 40)
    crazed = (rng.random((count, count)) < 0.5)[iy, ix] * T.threshold(0.07 - (craze2 - craze), 0.0, 0.03)
    image = T.gain(image, 1 - 0.28 * crazed)
    stained = (rng.random((count, count)) < 0.14)[iy, ix]
    image = T.lerp(image, T.tint(image, (0.78, 0.64, 0.46)), stained * 0.55)
    streaks = T.value_noise(rng, size, size, 36, 3)
    image = T.gain(image, 0.80 + 0.28 * streaks)
    slash_tile = (rng.random((count, count)) < 0.09)[iy, ix]
    fx = np.arange(size)[None, :] % step
    fy = np.arange(size)[:, None] % step
    slash = slash_tile & (np.abs((fx - fy) - step * 0.1) < 1.6)
    image = T.gain(image, np.where(slash, 0.35, 1.0))
    grout_color = T.solid(size, size, (0.20, 0.205, 0.18)) * (0.65 + 0.5 * T.fbm(rng, size, size, 12, 3))[..., None]
    image = np.where((edge < 0)[..., None], grout_color, image)
    height = np.where(edge < 0, 0.12 + 0.03 * rng.random((size, size)), 0.72 + 0.18 * face)
    height = height - 0.25 * slash
    rough = np.where(edge < 0, 0.92, 0.24 + 0.30 * T.fbm(rng, size, size, 6, 3)) + 0.2 * stained
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))


def garage_block(rng, size=512, base=(0.20, 0.21, 0.205)):
    """Bloco de concreto pintado: 8 fiadas de 20 cm, blocos de 40 cm, poros, tinta descascando e eflorescência."""
    rows, block = 8, size // 4
    row_h = size // rows
    xs, ys = T.pixel_grid(size, size)
    row_id = ys // row_h
    shifted = (xs + (row_id % 2) * (block // 2)) % size
    block_id = shifted // block
    joint = 4
    mortar = ((ys % row_h) < joint) | ((shifted % block) < joint)
    per_block = 0.84 + 0.30 * rng.random((rows, 4))
    image = T.gain(T.solid(size, size, base), per_block[row_id, block_id])
    pores_f1, _, _ = T.cellular(rng, size, size, 70)
    pores = T.threshold(0.16 - pores_f1, 0.0, 0.05) * (rng.random((size, size)) < 0.55)
    peel_field = T.fbm(rng, size, size, 4, 6, 0.58)
    peeled = T.threshold(peel_field, 0.68, 0.02)
    raw = T.gain(T.solid(size, size, (0.27, 0.265, 0.245)), 0.7 + 0.5 * T.fbm(rng, size, size, 10, 3))
    image = T.lerp(image, raw, peeled)
    image = T.gain(image, 0.85 + 0.25 * T.fbm(rng, size, size, 8, 3))
    image = T.gain(image, 1 - 0.55 * pores)
    white = T.threshold(T.fbm(rng, size, size, 6, 4), 0.66, 0.08) * (ys % row_h < row_h * 0.3)
    image = T.lerp(image, np.array((0.34, 0.34, 0.31), np.float32), white * 0.5)
    image = np.where(mortar[..., None], T.solid(size, size, (0.09, 0.09, 0.085)) * (0.7 + 0.5 * rng.random((size, size, 1))), image)
    height = np.where(mortar, 0.14, 0.72 - 0.10 * peeled) - 0.22 * pores + 0.05 * (rng.random((size, size)) - 0.5)
    rough = np.where(mortar, 0.95, 0.70 + 0.2 * peeled + 0.1 * rng.random((size, size)))
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))


def ceiling_plaster(rng, size=256, base=(0.46, 0.45, 0.405)):
    """Forro de gesso com textura de spray (pipoca): gotículas em relevo e pontos de mofo."""
    near, _, _ = T.cellular(rng, size, size, 46, jitter=1.0)
    bumps = T.smooth(1.0 - near * 1.15)
    clump = T.fbm(rng, size, size, 5, 3)
    image = T.gain(T.solid(size, size, base), 0.88 + 0.16 * clump + 0.10 * bumps)
    mold = T.threshold(T.fbm(rng, size, size, 12, 3), 0.72, 0.05) * (rng.random((size, size)) < 0.4)
    image = T.gain(image, 1 - 0.35 * mold)
    height = 0.35 + 0.55 * bumps * (0.75 + 0.25 * clump)
    return Maps(T.finish(image), T.height_map(height), T.rough_map(np.full((size, size), 0.97)))


def trim_paint(rng, size=256, base=(0.47, 0.45, 0.395)):
    """Tinta branca envelhecida de rodapés e batentes: pincelada, amarelado, lascas mostrando a madeira."""
    strokes = T.value_noise(rng, size, size, 3, size // 2)
    image = T.gain(T.solid(size, size, base), 0.82 + 0.26 * T.fbm(rng, size, size, 3, 3))
    image = T.tint(image, (1.0, 0.98, 0.9))
    image = T.gain(image, 0.94 + 0.12 * strokes)
    chip_field = T.fbm(rng, size, size, 9, 4, 0.6)
    chips = T.threshold(chip_field, 0.74, 0.02)
    wood = T.solid(size, size, (0.13, 0.085, 0.055)) * (0.7 + 0.6 * T.value_noise(rng, size, size, 3, size // 3))[..., None]
    image = T.lerp(image, wood, chips)
    grime = T.threshold(T.fbm(rng, size, size, 5, 3), 0.62, 0.3)
    image = T.lerp(image, T.tint(image, (0.78, 0.74, 0.62)), grime * 0.5)
    height = 0.6 + 0.07 * (strokes - 0.5) - 0.24 * chips + 0.03 * (rng.random((size, size)) - 0.5)
    rough = 0.42 + 0.18 * T.fbm(rng, size, size, 4, 3) + 0.4 * chips
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))


def curtain_fabric(rng, size=256, base=(0.165, 0.125, 0.105)):
    """Tecido de cortina desbotado: trama de fios, listras desbotadas pelo sol, manchas de mofo."""
    xs, ys = T.pixel_grid(size, size)
    warp = 0.5 + 0.5 * np.sin(xs * np.pi * 0.5)
    weft = 0.5 + 0.5 * np.sin(ys * np.pi * 0.5)
    weave = np.where(((xs // 2) + (ys // 2)) % 2 == 0, warp, weft)
    image = T.gain(T.solid(size, size, base), 0.88 + 0.12 * weave)
    image = T.gain(image, 0.74 + 0.4 * T.fbm(rng, size, size, 2, 3))
    fade = T.value_noise(rng, size, size, 3, 2)
    image = T.lerp(image, T.tint(image, (1.3, 1.22, 1.1)), fade * 0.4)
    stripes = 0.5 + 0.5 * np.sin(xs / size * 2 * np.pi * 8)
    image = T.gain(image, 0.92 + 0.12 * T.threshold(stripes, 0.7, 0.2))
    mildew = T.threshold(T.fbm(rng, size, size, 8, 4), 0.66, 0.08)
    image = T.gain(image, 1 - 0.35 * mildew)
    height = 0.45 + 0.30 * weave + 0.05 * (rng.random((size, size)) - 0.5)
    return Maps(T.finish(image), T.height_map(height), T.rough_map(np.full((size, size), 0.98)))


# --------------------------------------------------------------------------
# Camadas de sujeira multiplicativas (aplicadas sobre qualquer material da casa)
# --------------------------------------------------------------------------
def wall_grime_overlay(rng, width=1024, height=256):
    """8 m x 2,8 m: sujeira rente ao piso, fumaça no teto, manchas de infiltração com borda marrom e escorridos."""
    v, u = T._rows(height), T._cols(width)
    ramp_floor = 0.5 + 0.5 * T.smooth(v / 0.3)
    ramp_ceiling = 1 - 0.22 * T.smooth((v - 0.8) / 0.2)
    haze = 0.84 + 0.26 * T.fbm(rng, width, height, 5, 4)
    result = ramp_floor * ramp_ceiling * haze
    damp = T.blobs(rng, width, height, 9, 40, 0.6) * T.smooth((v - 0.50) / 0.25)
    core = T.smooth((damp - 0.35) / 0.3)
    rim = np.clip(1 - np.abs(damp - 0.42) / 0.06, 0, 1)
    drips = T.value_noise(rng, width, height, 140, 3) > 0.64
    drip_fade = T.smooth(damp * 3) * T.smooth((0.75 - v) / 0.25 + 0.3)
    result = result * (1 - 0.30 * core) * (1 - 0.30 * rim) * (1 - 0.32 * drips * drip_fade)
    scuffs = T.threshold(T.blur(T.scratches(rng, width, height, 120, 22, (-0.3, 0.3)), 0.8) * 4, 0.3, 0.3)
    result = result * (1 - 0.14 * scuffs * T.smooth((0.45 - v) / 0.2))
    stain_rgb = np.array((1.0, 0.93, 0.80), np.float32)
    image = result[..., None] * (1 - core[..., None] * (1 - stain_rgb))
    image = image * (1 - rim[..., None] * (1 - np.array((0.95, 0.80, 0.55), np.float32)) * 0.7)
    return T.finish(image)


def floor_grime_overlay(rng, size=512):
    """8 m x 8 m: sujeira de trânsito, poças secas e manchas escuras."""
    image = 0.8 + 0.28 * T.fbm(rng, size, size, 3, 5)
    wet = T.blobs(rng, size, size, 6, size * 0.12, 0.6)
    dark = T.blobs(rng, size, size, 4, size * 0.06, 0.5)
    image = image * (1 - 0.2 * wet) * (1 - 0.28 * dark)
    return T.finish(np.repeat(image[..., None], 3, axis=2) * np.array((1.0, 0.98, 0.94), np.float32))


def ceiling_grime_overlay(rng, size=512):
    """8 m x 8 m: manchas de infiltração com anel marrom (marca d'água) e fumaça nos cantos."""
    base = 0.88 + 0.14 * T.fbm(rng, size, size, 4, 4)
    spots = T.blobs(rng, size, size, 5, size * 0.11, 0.5)
    core = T.smooth((spots - 0.3) / 0.4)
    ring = np.clip(1 - np.abs(spots - 0.42) / 0.05, 0, 1)
    image = base[..., None] * (1 - core[..., None] * (1 - np.array((0.96, 0.88, 0.70), np.float32)) * 0.8)
    image = image * (1 - ring[..., None] * (1 - np.array((0.85, 0.66, 0.40), np.float32)) * 0.8)
    return T.finish(image)
