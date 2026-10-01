"""Texturas de pisos e degraus: tábuas, carpete, linóleo, azulejo, concreto e a passadeira da escada."""
import numpy as np

from . import texgen as T
from .texgen import Maps
from .tex_interior import _tile_cells


def _wrapped(delta, period):
    """Distância com sinal respeitando a ladrilhagem."""
    return (delta + period / 2) % period - period / 2


def wood_grain(rng, width, height, light, dark, rings=46, knots=3, warp=0.55):
    """Campo de veios de madeira: anéis de crescimento deformados, fibras, poros e nós.

    O eixo X da imagem corre ao longo da fibra. Devolve (cor, anel, fibras) para o chamador compor
    desgaste e verniz por cima.
    """
    u, v = T.unit_grid(width, height)
    drift = T.fbm(rng, width, height, 2, 4, 0.55, cells_y=7)
    t = v * rings + (drift - 0.5) * rings * warp * 0.5
    for _ in range(knots):
        ku, kv, radius = rng.random(), rng.random(), 0.018 + 0.02 * rng.random()
        du, dv = _wrapped(u - ku, 1.0) * (width / height), _wrapped(v - kv, 1.0)
        distance = np.hypot(du * 0.45, dv)
        t = t + 5.5 * np.exp(-(distance / (radius * 3.2)) ** 2) * np.sign(dv + 1e-6)
    ring = 0.5 + 0.5 * np.sin(2 * np.pi * t)
    ring = ring ** 1.6
    fibres = T.value_noise(rng, width, height, 6, height)
    pores = (T.value_noise(rng, width, height, width // 3, height) > 0.80).astype(np.float32)
    tone = 0.80 + 0.38 * T.fbm(rng, width, height, 3, 4, 0.5, cells_y=5)
    image = T.lerp(T.solid(width, height, light), T.solid(width, height, dark), ring * 0.72 + 0.12 * fibres)
    image = T.gain(image, tone * (1 - 0.30 * pores))
    return image, ring, fibres


def wood_planks(rng, width=1024, height=256, light=(0.28, 0.175, 0.10), dark=(0.14, 0.08, 0.045)):
    """Superfície de madeira para tábuas individuais (a geometria faz as emendas): veios, riscos e verniz gasto.

    A imagem cobre 2,0 m ao longo da tábua por 0,5 m de largura; cada tábua sorteia um recorte diferente.
    """
    image, ring, fibres = wood_grain(rng, width, height, light, dark)
    scuffs = T.blur(T.scratches(rng, width, height, 90, 34, (-0.22, 0.22)), 0.7)
    scuffs = np.clip(scuffs * 3.0, 0, 1)
    worn = T.threshold(T.fbm(rng, width, height, 3, 4, 0.5, cells_y=2), 0.6, 0.25)
    image = T.lerp(image, image * 1.55, scuffs * 0.32)
    image = T.lerp(image, T.tint(image, (1.12, 1.07, 1.0)) * 1.12, worn * 0.4)
    stain = T.blobs(rng, width, height, 4, height * 0.16, 0.7)
    image = T.lerp(image, image * np.array((0.50, 0.44, 0.38), np.float32), stain * 0.65)
    height_field = 0.50 + 0.12 * (ring - 0.5) + 0.07 * (fibres - 0.5) - 0.25 * scuffs
    rough = 0.40 + 0.34 * worn + 0.15 * T.fbm(rng, width, height, 5, 3) + 0.3 * scuffs
    return Maps(T.finish(image), T.height_map(height_field), T.rough_map(rough))


def wood_planks_dark(rng):
    return wood_planks(rng, light=(0.16, 0.095, 0.058), dark=(0.075, 0.042, 0.026))


def wood_stairs(rng, width=512, height=512):
    """Degrau de madeira escura envernizada. 1,2 m ao longo do degrau (X) por 0,3 m de profundidade (Y).

    A faixa central é a mais pisada: verniz gasto e madeira clara; o nariz (a borda baixa) lasca mais.
    """
    image, ring, fibres = wood_grain(rng, width, height, (0.17, 0.10, 0.058), (0.085, 0.047, 0.028), rings=26)
    v = T._rows(height) * np.ones((1, width))
    traffic = np.exp(-((v - 0.55) / 0.20) ** 2) * T.threshold(T.fbm(rng, width, height, 3, 4), 0.35, 0.5)
    nose = T.smooth((0.14 - np.minimum(v, 1 - v)) / 0.14)
    scuffs = np.clip(T.blur(T.scratches(rng, width, height, 120, 28, (-0.2, 0.2)), 0.7) * 3, 0, 1)
    image = T.lerp(image, T.tint(image, (1.5, 1.35, 1.15)), traffic * 0.55)
    image = T.lerp(image, image * 1.7, scuffs * 0.3)
    image = T.gain(image, 1 - 0.25 * nose)
    grime = T.threshold(T.fbm(rng, width, height, 6, 3), 0.6, 0.25) * (1 - traffic)
    image = T.gain(image, 1 - 0.3 * grime)
    height_field = 0.5 + 0.10 * (ring - 0.5) + 0.06 * (fibres - 0.5) - 0.28 * scuffs - 0.12 * nose
    rough = 0.38 + 0.4 * traffic + 0.15 * T.fbm(rng, width, height, 5, 3) + 0.2 * scuffs
    return Maps(T.finish(image), T.height_map(height_field), T.rough_map(rough))


def stairs_riser(rng, width=512, height=256):
    """Espelho do degrau pintado de creme, 1,2 m por 0,187 m, com marcas de sapato e tinta lascada."""
    u, v = T.unit_grid(width, height)
    base = np.array((0.40, 0.375, 0.31), np.float32)
    image = T.gain(T.solid(width, height, base), 0.84 + 0.26 * T.fbm(rng, width, height, 4, 4))
    scuff = np.clip(T.blur(T.scratches(rng, width, height, 70, 18, (-0.6, 0.6)), 0.8) * 3.5, 0, 1)
    kicks = T.threshold(T.fbm(rng, width, height, 7, 4), 0.66, 0.1) * T.smooth((0.5 - v) / 0.4)
    image = T.lerp(image, np.array((0.13, 0.12, 0.10), np.float32), np.clip(kicks * 0.55 + scuff * 0.35, 0, 1))
    chips = T.threshold(T.fbm(rng, width, height, 10, 4, 0.6), 0.75, 0.02)
    image = T.lerp(image, T.solid(width, height, (0.12, 0.08, 0.055)), chips)
    height_field = 0.6 - 0.25 * chips - 0.1 * scuff + 0.05 * (rng.random((height, width)) - 0.5)
    return Maps(T.finish(image), T.height_map(height_field), T.rough_map(0.5 + 0.3 * kicks))


def carpet(rng, size=256, base=(0.155, 0.16, 0.125)):
    """Carpete de fio cortado: tufos individuais, sentido do pelo e áreas achatadas. 0,5 m por repetição."""
    near, _, ident = T.cellular(rng, size, size, 96, jitter=1.0)
    tuft_tone = (0.78 + 0.45 * rng.random(96 * 96))[ident]
    tuft = T.smooth(1.0 - near * 1.1)
    nap = T.value_noise(rng, size, size, 5, 3)
    image = T.gain(T.solid(size, size, base), tuft_tone * (0.78 + 0.26 * tuft) * (0.85 + 0.3 * nap))
    flat = T.threshold(T.fbm(rng, size, size, 3, 4), 0.58, 0.25)
    image = T.gain(image, 1 - 0.18 * flat)
    height = 0.25 + 0.6 * tuft * (1 - 0.35 * flat)
    return Maps(T.finish(image), T.height_map(height), T.rough_map(np.full((size, size), 1.0)))


def carpet_runner(rng, width=256, height=1024):
    """Passadeira vinho de estampa persa com borda, gasta no miolo. Mapeada por UV: u = largura, v = comprimento."""
    u, v = T.unit_grid(width, height)
    aspect = height / width
    edge = np.minimum(u, 1 - u)
    wine, navy, cream = np.array((0.20, 0.035, 0.04), np.float32), np.array((0.05, 0.05, 0.10), np.float32), \
        np.array((0.34, 0.28, 0.17), np.float32)
    image = T.solid(width, height, wine)
    border = T.threshold(0.14 - edge, 0.0, 0.01)
    image = T.lerp(image, navy, border)
    rule = T.threshold(0.025 - np.abs(edge - 0.17), 0.0, 0.006) + T.threshold(0.012 - np.abs(edge - 0.045), 0.0, 0.004)
    image = T.lerp(image, cream, np.clip(rule, 0, 1) * 0.8)
    cell_u, cell_v = (u - 0.5) * 2.0, ((v * aspect * 2.4) % 1.0 - 0.5) * 2.0
    lozenge = T.threshold(0.62 - (np.abs(cell_u) / 0.9 + np.abs(cell_v) / 0.9) , 0.0, 0.04) * (1 - border)
    inner = T.threshold(0.30 - (np.abs(cell_u) / 0.9 + np.abs(cell_v) / 0.9), 0.0, 0.05)
    image = T.lerp(image, navy * 1.2, lozenge * 0.8)
    image = T.lerp(image, cream * 0.8, inner * 0.7)
    fibre = T.blur(rng.random((height, width)), 0.6) * 2 - 1
    wear = T.smooth(1 - np.abs(u - 0.5) / 0.28) * T.threshold(T.fbm(rng, width, height, 2, 4, cells_y=6), 0.4, 0.4)
    image = T.lerp(image, image * 0.55 + 0.04, wear * 0.7)
    image = T.gain(image, 0.92 + 0.12 * T.fbm(rng, width, height, 4, 4) + 0.10 * fibre)
    height_field = 0.5 + 0.2 * fibre - 0.22 * wear
    return Maps(T.finish(image), T.height_map(height_field), T.rough_map(np.full((height, width), 1.0)))


def linoleum(rng, size=512, light=(0.30, 0.275, 0.195), dark=(0.20, 0.165, 0.115)):
    """Linóleo xadrez de cozinha (quadrados de 25 cm) com veio marmorizado, riscos, desgaste e cantos lascados."""
    ix, iy, edge, step = _tile_cells(size, 4, 3)
    checker = ((ix + iy) % 2 == 0)[..., None]
    base = np.where(checker, T.solid(size, size, light), T.solid(size, size, dark))
    swirl = T.fbm(rng, size, size, 6, 5, 0.6)
    marble = 0.5 + 0.5 * np.sin(swirl * 14.0 + T.fbm(rng, size, size, 3, 3) * 6.0)
    image = T.gain(base, (0.86 + 0.3 * rng.random((4, 4))[iy, ix]) * (0.88 + 0.16 * marble))
    image = T.gain(image, 0.75 + 0.35 * T.fbm(rng, size, size, 4, 4))
    scuffs = np.clip(T.blur(T.scratches(rng, size, size, 140, 22), 0.7) * 3, 0, 1)
    image = T.lerp(image, image * 1.55, scuffs * 0.3)
    chips = np.clip(T.blur((rng.random((size, size)) < 0.0015).astype(np.float32), 1.2) * 14, 0, 1)
    image = T.gain(image, 1 - 0.55 * chips)
    dirt = T.smooth((1.0 - np.clip(edge / 3.0 + 0.5, 0, 1)))
    image = T.lerp(image, T.solid(size, size, (0.10, 0.085, 0.06)), dirt * 0.8)
    height = np.where(edge < 0, 0.18, 0.66 + 0.12 * marble) - 0.2 * chips - 0.1 * scuffs
    rough = 0.34 + 0.30 * T.fbm(rng, size, size, 5, 3) + 0.4 * scuffs
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))


def bathroom_floor_tile(rng, size=512, base=(0.355, 0.395, 0.395)):
    """Mosaico de azulejo 8x8 (12,5 cm) com peças escuras em xadrez ralo, rejunte encardido e rachaduras."""
    grout_px = 5
    ix, iy, edge, step = _tile_cells(size, 8, grout_px)
    face = T.smooth(edge / 4.0)
    image = T.gain(T.solid(size, size, base), (0.88 + 0.24 * rng.random((8, 8)))[iy, ix])
    accent = ((ix + iy) % 4 == 0)
    image = T.lerp(image, image * np.array((0.55, 0.62, 0.72), np.float32), accent * 0.8)
    image = T.gain(image, 0.78 + 0.32 * T.fbm(rng, size, size, 5, 4))
    big_cracks = T.blur(T.branching_cracks(rng, size, size, 3, 90, 0.5, 0.03), 0.6) * 2.5
    cracked = np.clip(big_cracks, 0, 1)
    image = T.gain(image, 1 - 0.65 * cracked)
    grout = T.solid(size, size, (0.11, 0.115, 0.10)) * (0.65 + 0.7 * T.fbm(rng, size, size, 12, 3))[..., None]
    image = np.where((edge < 0)[..., None], grout, image)
    height = np.where(edge < 0, 0.12, 0.70 + 0.2 * face) - 0.3 * cracked
    rough = np.where(edge < 0, 0.95, 0.20 + 0.35 * T.fbm(rng, size, size, 6, 3))
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))


def concrete(rng, size=512, base=(0.225, 0.225, 0.212), joint=True):
    """Concreto de garagem: mosqueado, poros, trincas ramificadas, riscos de pneu e junta de serra na borda."""
    mottle = T.fbm(rng, size, size, 4, 6, 0.55)
    image = T.gain(T.solid(size, size, base), 0.76 + 0.44 * mottle)
    pores_near, _, _ = T.cellular(rng, size, size, 120)
    pores = T.threshold(0.12 - pores_near, 0.0, 0.05) * (rng.random((size, size)) < 0.5)
    crack = np.clip(T.blur(T.branching_cracks(rng, size, size, 5, 150, 0.35, 0.05), 0.55) * 2.6, 0, 1)
    oil = T.blobs(rng, size, size, 3, size * 0.07, 0.7)
    image = T.gain(image, (1 - 0.45 * pores) * (1 - 0.65 * crack))
    image = T.lerp(image, image * np.array((0.40, 0.38, 0.34), np.float32), oil * 0.6)
    trowel = T.value_noise(rng, size, size, 18, 18)
    image = T.gain(image, 0.95 + 0.1 * trowel)
    edge = np.zeros((size, size))
    if joint:
        px = np.arange(size)
        edge = ((px[None, :] < 3) | (px[:, None] < 3)).astype(np.float32)
        image = T.gain(image, 1 - 0.65 * edge)
    height = 0.62 + 0.15 * (mottle - 0.5) - 0.35 * pores - 0.45 * crack - 0.5 * edge + 0.03 * (trowel - 0.5)
    rough = 0.80 + 0.15 * T.fbm(rng, size, size, 5, 3) - 0.3 * oil
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))
