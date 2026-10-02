"""Texturas de folhas de porta, vidros e telas.

As folhas são mapeadas pelas coordenadas do objeto (origem na dobradiça), uma repetição de 0,9 x 2,05 m
por folha, e a pintura conhece o desenho da porta (`doorspec`): racha nas juntas, a fibra corre ao longo
da travessa ou da longarina, a gordura se acumula em volta da maçaneta.
"""
import numpy as np

from . import doorspec
from . import texgen as T
from .texgen import Maps

TILE_X, TILE_Z = 0.9, 2.05
LEAF_W, LEAF_H = 0.88, 2.045


def _meters(width, height):
    """Coordenadas (x, z) em metros de cada pixel da textura de uma folha."""
    u, v = T.unit_grid(width, height)
    return u * TILE_X, v * TILE_Z


def _rect_sdf(x, z, rect):
    x0, z0, x1, z1 = rect
    dx = np.maximum(x0 - x, x - x1)
    dz = np.maximum(z0 - z, z - z1)
    return np.hypot(np.maximum(dx, 0), np.maximum(dz, 0)) + np.minimum(np.maximum(dx, dz), 0)


def _field_distance(spec, x, z):
    """Distância com sinal ao vão mais próximo (negativa dentro): para juntas e cantos de almofada."""
    if not spec.fields:
        return np.full(x.shape, 1.0)
    return np.min([_rect_sdf(x, z, f.rect) for f in spec.fields], axis=0)


def _horizontal_mask(spec, z):
    """1 nas faixas de travessa (fibra horizontal), 0 nas longarinas e almofadas (fibra vertical)."""
    mask = np.zeros(z.shape)
    for z0, z1 in doorspec.rail_bands(spec):
        mask = np.maximum(mask, ((z >= z0) & (z <= z1)).astype(float))
    return mask


def _wood_fibres(rng, width, height, spec, z):
    """Fibra de madeira: vertical nas longarinas e almofadas, horizontal nas travessas."""
    vertical = T.value_noise(rng, width, height, width // 5, 3)
    ridges = T.value_noise(rng, width, height, 12, 4)
    horizontal = T.value_noise(rng, width, height, 3, height // 4)
    blend = T.blur(_horizontal_mask(spec, z), 1.5)
    return vertical * (1 - blend) + horizontal * blend, ridges


def _hand_grime(x, z, knob=(doorspec.KNOB_INSET, doorspec.KNOB_HEIGHT)):
    """Gordura de mão em volta da maçaneta (a maçaneta fica a KNOB_INSET da borda livre)."""
    kx = LEAF_W - knob[0]
    smudge = np.exp(-(((x - kx) / 0.11) ** 2 + ((z - knob[1]) / 0.13) ** 2))
    lower = np.exp(-(((x - kx + 0.05) / 0.16) ** 2 + ((z - 0.72) / 0.18) ** 2))
    return np.clip(smudge * 0.9 + lower * 0.4, 0, 1)


def _stamp_hand(x, z, cx, cz, scale, angle):
    """Máscara de uma mão espalmada (palma e quatro dedos mais o polegar) centrada em (cx, cz)."""
    c, s = np.cos(angle), np.sin(angle)
    dx, dz = (x - cx) / scale, (z - cz) / scale
    u, v = dx * c + dz * s, -dx * s + dz * c
    palm = np.exp(-((u / 0.046) ** 2 + ((v + 0.01) / 0.052) ** 2) ** 1.4)
    fingers = np.zeros_like(u)
    for fx, length in ((-0.034, 0.062), (-0.0115, 0.080), (0.0115, 0.086), (0.034, 0.070)):
        reach = ((u - fx) / 0.0115) ** 2 + ((v - 0.05 - length / 2) / (length * 0.55)) ** 2
        fingers = np.maximum(fingers, np.exp(-reach ** 1.6))
    thumb = np.exp(-((((u - 0.062) / 0.013) ** 2 + ((v - 0.005) / 0.034) ** 2)) ** 1.6)
    return np.clip(palm + fingers + thumb, 0, 1)


def _joint_cracks(rng, width, height, distance_m):
    """Fissuras da tinta ao longo das juntas entre travessa e almofada."""
    near = np.exp(-(distance_m / 0.0025) ** 2)
    broken = T.threshold(T.fbm(rng, width, height, 30, 3, 0.6), 0.5, 0.2)
    return near * broken


def _star_mask(x, z, cx, cz, radius, rotation):
    """Estrela de cinco pontas centrada em (cx, cz): máscara 0/1 suave."""
    angle = np.arctan2(z - cz, x - cx) - rotation
    r = np.hypot(x - cx, z - cz)
    sector = (angle % (2 * np.pi / 5)) / (2 * np.pi / 5)
    edge = radius * (0.42 + 0.58 * np.abs(1.0 - 2.0 * sector))
    return T.threshold(edge - r, 0.0, 0.0035)


def _heart_mask(x, z, cx, cz, size):
    u, v = (x - cx) / size, (z - cz) / size + 0.15
    return T.threshold(1.0 - ((u * u + v * v - 0.5) ** 3 - 0.9 * u * u * v ** 3) * 4.0, 0.0, 0.05) * (np.abs(u) < 0.8)


def _stickers(image, x, z, rng):
    """Adesivos de estrela e coração na altura de uma criança, em cores gastas pelo sol."""
    palette = ((0.62, 0.48, 0.08), (0.55, 0.20, 0.30), (0.16, 0.28, 0.50), (0.20, 0.45, 0.22))
    spots = ((0.30, 1.12, 0.055), (0.52, 0.98, 0.045), (0.21, 0.86, 0.05), (0.43, 1.28, 0.04), (0.63, 1.16, 0.05),
             (0.34, 0.70, 0.04))
    for index, (cx, cz, radius) in enumerate(spots):
        color = np.array(palette[index % len(palette)], np.float32)
        if index == 2:
            mask = _heart_mask(x, z, cx, cz, radius * 1.1)
        else:
            mask = _star_mask(x, z, cx, cz, radius, rng.uniform(0, 1.2))
        shine = 0.8 + 0.4 * np.clip((x - cx) / radius + (z - cz) / radius, -1, 1) * 0.5
        image = T.lerp(image, color * shine[..., None], mask * 0.92)
    return image


def door_painted(rng, size=(512, 1024), base=(0.42, 0.395, 0.325), kind="six_panel", prints=False, stickers=False):
    """Folha de porta pintada de creme: pincelada, tinta craquelada nas juntas, gordura na maçaneta, lascas."""
    width, height = size
    spec = doorspec.leaf_spec(kind, LEAF_W, LEAF_H)
    x, z = _meters(width, height)
    fibre, ridges = _wood_fibres(rng, width, height, spec, z)
    distance = _field_distance(spec, x, z)
    tone = 0.84 + 0.30 * T.fbm(rng, width, height, 3, 4)
    image = T.gain(T.solid(width, height, base), tone * (0.95 + 0.10 * fibre))
    image = T.tint(image, (1.0, 0.985, 0.93))
    yellow = T.threshold(T.fbm(rng, width, height, 4, 3), 0.55, 0.3)
    image = T.lerp(image, T.tint(image, (1.1, 1.0, 0.76)), yellow * 0.5)
    cracked = _joint_cracks(rng, width, height, distance)
    image = T.gain(image, 1 - 0.55 * cracked)
    chip_field = T.fbm(rng, width, height, 9, 4, 0.6)
    edge_bias = (np.exp(-(np.minimum(x, LEAF_W - x) / 0.05) ** 2) + np.exp(-(z / 0.12) ** 2)
                 + np.exp(-((LEAF_H - z) / 0.06) ** 2))
    chips = T.threshold(chip_field + 0.13 * np.clip(edge_bias, 0, 1), 0.85, 0.02)
    wood = T.solid(width, height, (0.20, 0.13, 0.08)) * (0.7 + 0.6 * ridges)[..., None]
    image = T.lerp(image, wood, chips)
    grime = _hand_grime(x, z)
    image = T.lerp(image, image * np.array((0.50, 0.44, 0.36), np.float32), grime * 0.7)
    kick = T.smooth((0.32 - z) / 0.32)
    scuffs = np.clip(T.blur(T.scratches(rng, width, height, 120, 26, (-0.5, 0.5)), 0.8) * 3, 0, 1)
    image = T.lerp(image, image * 0.45, kick * T.threshold(T.fbm(rng, width, height, 8, 3), 0.45, 0.3) * 0.7)
    image = T.lerp(image, image * 1.4, scuffs * kick * 0.4)
    if stickers:
        image = _stickers(image, x, z, rng)
    if prints:
        for cx, cz, scale, angle in ((0.62, 0.62, 0.55, 0.25), (0.70, 0.74, 0.5, -0.15), (0.24, 0.50, 0.55, 0.5)):
            hand = _stamp_hand(x, z, cx, cz, scale, angle)
            image = T.lerp(image, image * np.array((0.45, 0.40, 0.34), np.float32), hand * 0.5)
    height_field = (0.62 + 0.04 * (fibre - 0.5) - 0.28 * chips - 0.25 * cracked
                    + 0.02 * T.speckle(rng, width, height, 1.0))
    rough = 0.40 + 0.22 * T.fbm(rng, width, height, 5, 3) + 0.4 * chips + 0.2 * grime
    return Maps(T.finish(image), T.height_map(height_field), T.rough_map(rough))


def door_stained(rng, size=(512, 1024), light=(0.20, 0.115, 0.062), dark=(0.095, 0.052, 0.03), kind="six_panel",
                 gloss=0.34):
    """Folha de carvalho tingido e envernizado: fibra ao longo de cada peça, verniz gasto na maçaneta e embaixo."""
    width, height = size
    spec = doorspec.leaf_spec(kind, LEAF_W, LEAF_H)
    x, z = _meters(width, height)
    fibre, ridges = _wood_fibres(rng, width, height, spec, z)
    distance = _field_distance(spec, x, z)
    rings = 0.5 + 0.5 * np.sin(2 * np.pi * (x * 70 + T.fbm(rng, width, height, 2, 4, 0.5, cells_y=6) * 8))
    vertical_rings = rings ** 1.4
    shade = 0.15 + 0.55 * (0.5 * ridges + 0.5 * vertical_rings) * (1 - 0.3 * fibre)
    image = T.lerp(T.solid(width, height, light), T.solid(width, height, dark), shade)
    image = T.gain(image, 0.80 + 0.36 * T.fbm(rng, width, height, 3, 4))
    joint = np.exp(-(distance / 0.0022) ** 2)
    image = T.gain(image, 1 - 0.55 * joint)
    pool = np.exp(-(np.clip(distance, 0, 1) / 0.03))
    image = T.gain(image, 1 - 0.22 * pool * (distance > 0))
    grime = _hand_grime(x, z)
    worn = T.threshold(grime + 0.35 * T.fbm(rng, width, height, 6, 3), 0.55, 0.3)
    image = T.lerp(image, T.tint(image, (1.9, 1.7, 1.4)), worn * 0.55)
    kick = T.smooth((0.30 - z) / 0.30)
    scuffs = np.clip(T.blur(T.scratches(rng, width, height, 150, 24, (-0.5, 0.5)), 0.8) * 3, 0, 1)
    image = T.lerp(image, image * 1.7, scuffs * 0.28)
    image = T.gain(image, 1 - 0.35 * kick * T.threshold(T.fbm(rng, width, height, 7, 3), 0.4, 0.3))
    height_field = 0.55 + 0.10 * (vertical_rings - 0.5) + 0.06 * (fibre - 0.5) - 0.3 * joint - 0.15 * scuffs
    rough = gloss + 0.30 * worn + 0.15 * T.fbm(rng, width, height, 5, 3) + 0.25 * scuffs
    return Maps(T.finish(image), T.height_map(height_field), T.rough_map(rough))


def door_steel(rng, size=(512, 1024), base=(0.30, 0.30, 0.265)):
    """Porta corta-fogo de aço pintada: amassados, riscos, ferrugem na base e gordura de mão."""
    width, height = size
    x, z = _meters(width, height)
    image = T.gain(T.solid(width, height, base), 0.80 + 0.32 * T.fbm(rng, width, height, 3, 4))
    dents = T.fbm(rng, width, height, 5, 3)
    rust_streak = T.value_noise(rng, width, height, 26, 2) * np.clip((0.55 - z) / 0.55, 0, 1) ** 0.9
    foot = 0.8 * np.exp(-(z / 0.06) ** 2) * T.fbm(rng, width, height, 12, 3)
    rust = np.clip((rust_streak - 0.40) * 1.8, 0, 0.8) + foot
    rust = np.clip(rust, 0, 0.85)
    rust_color = np.array((0.20, 0.10, 0.055), np.float32) * (0.7 + 0.6 * T.fbm(rng, width, height, 14, 3)[..., None])
    image = T.lerp(image, rust_color, rust)
    scratches = np.clip(T.blur(T.scratches(rng, width, height, 100, 40), 0.7) * 3, 0, 1)
    image = T.lerp(image, np.array((0.40, 0.38, 0.34), np.float32), scratches * 0.35)
    grime = _hand_grime(x, z)
    image = T.lerp(image, image * 0.5, grime * 0.6)
    seam = np.exp(-((x - 0.0) / 0.003) ** 2) + np.exp(-((x - LEAF_W) / 0.003) ** 2)
    height_field = 0.55 + 0.12 * (dents - 0.5) - 0.25 * rust + 0.05 * scratches - 0.15 * np.clip(seam, 0, 1)
    rough = 0.42 + 0.3 * rust + 0.2 * T.fbm(rng, width, height, 5, 3)
    return Maps(T.finish(image), T.height_map(height_field), T.rough_map(rough))


def door_painted_cream_a(rng):
    return door_painted(rng, prints=False)


def door_painted_cream_b(rng):
    return door_painted(rng, base=(0.40, 0.385, 0.34), prints=True)


def door_kids_painted(rng):
    """Porta do quarto da Emma: pintura clara e cuidada, adesivos de estrela e mãozinhas pequenas na altura dela."""
    return door_painted(rng, base=(0.46, 0.42, 0.38), prints=True, stickers=True)


def door_back_painted(rng):
    return door_painted(rng, base=(0.36, 0.37, 0.34), kind="screen")


def door_front_stained(rng):
    return door_stained(rng, light=(0.135, 0.065, 0.04), dark=(0.055, 0.026, 0.018), kind="glazed", gloss=0.26)


# --------------------------------------------------------------------------
# Vidro e tela
# --------------------------------------------------------------------------
def window_glass(rng, size=256):
    """Vidro velho e sujo: quase transparente, com poeira, marcas de dedo e escorridos de condensação."""
    cloud = T.fbm(rng, size, size, 4, 4)
    dust = T.threshold(cloud, 0.55, 0.35)
    streak = T.value_noise(rng, size, size, 40, 3) * T.threshold(cloud, 0.45, 0.3)
    smears = np.clip(T.blur(T.scratches(rng, size, size, 40, 40), 1.2) * 3, 0, 1)
    opacity = 0.06 + 0.22 * dust + 0.16 * streak + 0.18 * smears
    grime = np.clip(dust * 0.6 + smears * 0.4, 0, 1)
    image = T.lerp(T.solid(size, size, (0.020, 0.028, 0.035)), T.solid(size, size, (0.16, 0.15, 0.12)), grime)
    return Maps(T.finish(image), T.height_map(0.5 + 0.2 * dust), T.rough_map(0.08 + 0.5 * dust + 0.3 * smears),
                T.height_map(opacity))


def frosted_glass(rng, size=256):
    """Vidro fosco do banheiro: leitoso e granulado."""
    grain = T.blur(rng.random((size, size)), 0.8)
    image = T.solid(size, size, (0.30, 0.34, 0.33)) * (0.85 + 0.3 * grain)[..., None]
    dirt = T.threshold(T.fbm(rng, size, size, 4, 4), 0.6, 0.3)
    image = T.lerp(image, image * 0.6, dirt * 0.5)
    return Maps(T.finish(image), T.height_map(0.5 + 0.5 * (grain - 0.5)), T.rough_map(0.55 + 0.2 * grain),
                T.height_map(0.55 + 0.25 * dirt))


def screen_mesh(rng, size=256, wires=14):
    """Tela de arame em trama simples. Uma repetição de 4 cm tem `wires` fios (passo de ~3 mm)."""
    xs, ys = T.pixel_grid(size, size)
    pitch = size / wires
    wire_x = np.abs(((xs % pitch) / pitch) - 0.5) > 0.34
    wire_y = np.abs(((ys % pitch) / pitch) - 0.5) > 0.34
    wire = (wire_x | wire_y).astype(np.float32)
    wire = T.blur(wire, 0.6)
    rust = T.threshold(T.fbm(rng, size, size, 3, 3), 0.55, 0.3)
    image = T.lerp(T.solid(size, size, (0.08, 0.08, 0.075)), T.solid(size, size, (0.15, 0.09, 0.05)), rust * 0.7)
    return Maps(T.finish(image), T.height_map(wire), T.rough_map(np.full((size, size), 0.6)),
                T.height_map(np.clip(wire * 1.3, 0, 1)))
