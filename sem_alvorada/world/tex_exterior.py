"""Texturas da fachada, do telhado, da rua e dos granulados dos materiais básicos da paleta."""
import numpy as np

from . import texgen as T
from .texgen import Maps


# --------------------------------------------------------------------------
# Fachada e telhado
# --------------------------------------------------------------------------
def brick(rng, size=480, base=(0.225, 0.095, 0.065)):
    """Tijolo aparente em amarração corrente: 12 fiadas de 8 cm e tijolos de 24 cm por 0,96 m."""
    row_h, length = size // 12, size // 4
    xs, ys = T.pixel_grid(size, size)
    row_id = ys // row_h
    shifted = (xs + (row_id % 2) * (length // 2)) % size
    brick_id = shifted // length
    mortar_w = 4
    mortar = ((ys % row_h) < mortar_w) | ((shifted % length) < mortar_w)
    edge_x = np.minimum(shifted % length, length - 1 - shifted % length) - mortar_w / 2
    edge_y = np.minimum(ys % row_h, row_h - 1 - ys % row_h) - mortar_w / 2
    round_off = T.smooth(np.minimum(edge_x, edge_y) / 4.0)
    per_brick = 0.65 + 0.7 * rng.random((12, 4))
    image = T.gain(T.solid(size, size, base), per_brick[row_id, brick_id])
    image = T.tint(image, (1.0, 0.95, 0.92)) * (0.82 + 0.34 * T.fbm(rng, size, size, 6, 4))[..., None]
    image = T.gain(image, 1 + T.speckle(rng, size, size, 0.12))
    pits, _, _ = T.cellular(rng, size, size, 110)
    image = T.gain(image, 1 - 0.4 * T.threshold(0.13 - pits, 0.0, 0.05) * (rng.random((size, size)) < 0.4))
    image = T.gain(image, 0.72 + 0.34 * T.value_noise(rng, size, size, 3, 2))
    efflorescence = T.threshold(T.fbm(rng, size, size, 7, 4), 0.68, 0.08)
    image = T.lerp(image, np.array((0.30, 0.29, 0.26), np.float32), efflorescence * 0.45)
    mortar_color = T.solid(size, size, (0.26, 0.25, 0.22)) * (0.65 + 0.55 * T.fbm(rng, size, size, 14, 3))[..., None]
    image = np.where(mortar[..., None], mortar_color, image)
    height = np.where(mortar, 0.15, 0.62 + 0.25 * round_off) + 0.06 * (T.fbm(rng, size, size, 18, 3) - 0.5)
    rough = np.where(mortar, 0.95, 0.80 + 0.15 * T.fbm(rng, size, size, 6, 3))
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))


def clapboard(rng, size=256, boards=4, base=(0.305, 0.315, 0.275)):
    """Revestimento de tábuas sobrepostas (16 cm de exposição): fio de luz, sombra embaixo, veios, tinta lascada."""
    board = size // boards
    xs, ys = T.pixel_grid(size, size)
    within, board_id = ys % board, ys // board
    t = within / board
    image = T.gain(T.solid(size, size, base), (0.86 + 0.28 * rng.random(boards))[board_id])
    shading = np.where(within >= board - 3, 1.30, np.where(within < 5, 0.50, 0.88 + 0.12 * t))
    image = T.gain(image, shading)
    grain = T.value_noise(rng, size, size, 4, size)
    image = T.gain(image, 0.88 + 0.22 * grain)
    image = T.gain(image, 0.78 + 0.32 * T.value_noise(rng, size, size, 12, 2))
    peel = T.threshold(T.fbm(rng, size, size, 5, 4, 0.6), 0.70, 0.03)
    wood = T.solid(size, size, (0.20, 0.17, 0.13)) * (0.7 + 0.6 * grain)[..., None]
    image = T.lerp(image, wood, peel)
    joints = (xs == (board_id * 23 + 9) % size) & (within > 2)
    image = T.gain(image, np.where(joints, 0.5, 1.0))
    height = 0.3 + 0.55 * t - np.where(within < 5, 0.25, 0.0) + 0.05 * (grain - 0.5) - 0.12 * peel
    rough = 0.78 + 0.15 * grain - 0.1 * (1 - peel)
    return Maps(T.finish(image), T.height_map(height), T.rough_map(rough))


def shingles(rng, size=480, base=(0.075, 0.075, 0.08)):
    """Telha de asfalto em três abas: 8 fiadas de 12 cm, abas de 32 cm com fresta, grânulos, musgo e abas desbotadas."""
    course, tab = size // 8, size // 3
    xs, ys = T.pixel_grid(size, size)
    course_id = ys // course
    shifted = (xs + (course_id * 71) % tab) % size
    tab_id = shifted // tab
    tones = 0.7 + 0.6 * rng.random((8, 3))
    image = T.gain(T.solid(size, size, base), tones[course_id, tab_id])
    within = ys % course
    image = T.gain(image, np.where(within < course * 0.22, 0.55, np.where(within >= course - 3, 1.25, 1.0)))
    slot = (shifted % tab) < 5
    image = T.gain(image, np.where(slot & (within > course * 0.22), 0.30, 1.0))
    image = T.gain(image, 1 + T.speckle(rng, size, size, 0.30))
    moss = T.fbm(rng, size, size, 3, 4)
    moss_color = np.array((0.055, 0.075, 0.05), np.float32) * (0.7 + 0.6 * moss[..., None])
    image = T.lerp(image, moss_color, (moss > 0.72) * 0.55)
    height = (0.35 + 0.5 * (within / course) - 0.3 * slot * (within > course * 0.22)
              + 0.08 * T.speckle(rng, size, size, 1.0))
    return Maps(T.finish(image), T.height_map(height), T.rough_map(np.full((size, size), 0.93)))


def garage_door_paint(rng, size=256, base=(0.30, 0.30, 0.285)):
    """Chapa pintada do portão: amassados suaves e veios de ferrugem escorrendo pela parte baixa."""
    image = T.gain(T.solid(size, size, base), 0.78 + 0.34 * T.fbm(rng, size, size, 3, 4))
    streaks = T.value_noise(rng, size, size, 22, 2) * (1 - T.unit_grid(size, size)[1]) ** 0.8
    rust = np.clip((streaks - 0.45) * 1.6, 0, 0.6)
    image = T.lerp(image, np.array((0.16, 0.085, 0.05), np.float32) * (0.7 + 0.5 * streaks[..., None]), rust * 0.7)
    image = T.gain(image, 1 + T.speckle(rng, size, size, 0.04))
    height = 0.55 + 0.1 * (T.fbm(rng, size, size, 5, 3) - 0.5) - 0.2 * rust
    return Maps(T.finish(image), T.height_map(height), T.rough_map(0.5 + 0.4 * rust))


# --------------------------------------------------------------------------
# Rua e quintal
# --------------------------------------------------------------------------
def asphalt(rng, size=512, base=(0.055, 0.055, 0.06)):
    image = T.gain(T.solid(size, size, base), 0.7 + 0.6 * T.fbm(rng, size, size, 4, 5))
    aggregate = rng.random((size, size))
    image = T.gain(image, np.where(aggregate > 0.93, 1.9, np.where(aggregate < 0.05, 0.5, 1.0)))
    crack = np.clip(T.blur(T.branching_cracks(rng, size, size, 3, 140, 0.3, 0.04), 0.6) * 2.5, 0, 1)
    image = T.gain(image, 1 - 0.65 * crack)
    patch = np.zeros((size, size))
    patch[size // 4:size // 2, size // 6:size * 3 // 4] = 1.0
    image = T.gain(image, 1 - 0.25 * T.blur(patch, 2.0))
    height = 0.5 + 0.25 * (aggregate - 0.5) + 0.1 * (T.fbm(rng, size, size, 8, 3) - 0.5) - 0.4 * crack
    return Maps(T.finish(image), T.height_map(height), T.rough_map(np.full((size, size), 0.93)))


def road_paint(rng, size=256, base=(0.55, 0.47, 0.16)):
    image = T.gain(T.solid(size, size, base), 0.55 + 0.6 * T.fbm(rng, size, size, 3, 4))
    flaked = rng.random((size, size)) < 0.12
    image = T.gain(image, np.where(flaked, 0.3, 1.0))
    return Maps(T.finish(image), T.height_map(0.6 - 0.2 * flaked), None)


def dead_grass(rng, size=256, base=(0.095, 0.09, 0.055)):
    image = T.gain(T.solid(size, size, base), 0.55 + 0.9 * T.fbm(rng, size, size, 5, 5))
    blades = rng.random((size, size))
    image = T.gain(image, np.where(blades > 0.9, 1.6, np.where(blades < 0.12, 0.45, 1.0)))
    height = 0.4 + 0.5 * T.blur(blades, 0.8) * 3 - 0.3
    return Maps(T.finish(image), T.height_map(height), None)


def sidewalk(rng, size=512, base=(0.235, 0.235, 0.22)):
    """Calçada de concreto com juntas de dilatação, trincas e poros."""
    image = T.gain(T.solid(size, size, base), 0.78 + 0.4 * T.fbm(rng, size, size, 4, 5))
    pores = rng.random((size, size)) < 0.025
    crack = np.clip(T.blur(T.branching_cracks(rng, size, size, 3, 120, 0.35, 0.03), 0.55) * 2.5, 0, 1)
    px = np.arange(size)
    edge = ((px[None, :] < 3) | (px[:, None] < 3)).astype(np.float32)
    image = T.gain(image, (1 - 0.4 * pores) * (1 - 0.6 * crack) * (1 - 0.6 * edge))
    height = 0.6 + 0.1 * (T.fbm(rng, size, size, 5, 3) - 0.5) - 0.3 * pores - 0.4 * crack - 0.5 * edge
    return Maps(T.finish(image), T.height_map(height), T.rough_map(np.full((size, size), 0.88)))


def bark(rng, size=256, base=(0.075, 0.055, 0.045)):
    furrows = T.value_noise(rng, size, size, 10, 3)
    image = T.gain(T.solid(size, size, base), 0.35 + 1.1 * furrows)
    image = T.gain(image, 1 + T.speckle(rng, size, size, 0.08))
    return Maps(T.finish(image), T.height_map(furrows), None)


def picket_paint(rng, size=256, base=(0.36, 0.355, 0.32)):
    wood = np.array((0.14, 0.10, 0.07), np.float32)
    image = T.gain(T.solid(size, size, base), 0.8 + 0.3 * T.fbm(rng, size, size, 3, 4))
    worn = T.fbm(rng, size, size, 4, 4)
    grain = T.value_noise(rng, size, size, 3, size // 2)
    image = T.lerp(image, wood * (0.7 + 0.6 * grain)[..., None], T.threshold(worn, 0.6, 0.05) * 0.85)
    return Maps(T.finish(image), T.height_map(0.55 + 0.15 * (grain - 0.5) - 0.2 * T.threshold(worn, 0.6, 0.05)), None)


# --------------------------------------------------------------------------
# Granulado dos materiais básicos da paleta (multiplica a cor lisa)
# --------------------------------------------------------------------------
def grit(rng, size=256):
    """Cinza multiplicativo sutil (média ~0,9) que tira o aspecto de plástico das cores lisas."""
    cloud = T.fbm(rng, size, size, 4, 4)
    fine = T.speckle(rng, size, size, 0.07)
    image = (0.82 + 0.2 * cloud) * (1 + fine)
    height = 0.5 + 0.35 * (cloud - 0.5) + 0.6 * fine
    return Maps(T.finish(np.repeat(image[..., None], 3, axis=2)), T.height_map(height), None)


def wood_grain(rng, size=256):
    """Veio de madeira em tons de cinza para os móveis (multiplica a cor da paleta)."""
    grain = T.value_noise(rng, size, size, 4, size // 2)
    drift = T.fbm(rng, size, size, 2, 3, cells_y=5) * 3
    rings = 0.5 + 0.5 * np.sin(2 * np.pi * (T.unit_grid(size, size)[1] * 14 + drift))
    image = (0.6 + 0.6 * grain) * (0.88 + 0.2 * T.fbm(rng, size, size, 3, 3)) * (0.9 + 0.12 * rings)
    height = 0.5 + 0.2 * (rings - 0.5) + 0.2 * (grain - 0.5)
    return Maps(T.finish(np.repeat(np.clip(image, 0, 1.1)[..., None], 3, axis=2)), T.height_map(height), None)


def fabric_weave(rng, size=256):
    xs, ys = T.pixel_grid(size, size)
    weave = (((xs // 2) + (ys // 2)) % 2)
    fine = T.speckle(rng, size, size, 0.05)
    image = (0.85 + 0.1 * weave + fine) * (0.85 + 0.25 * T.fbm(rng, size, size, 4, 3))
    height = 0.4 + 0.35 * weave + 0.4 * fine
    return Maps(T.finish(np.repeat(np.clip(image, 0, 1)[..., None], 3, axis=2)), T.height_map(height), None)
