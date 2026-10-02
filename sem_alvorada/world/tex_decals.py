"""Texturas de decalques com alfa: reboco à mostra, mofo, rachaduras, manchas de infiltração, teias.

Cada uma devolve um `texgen.Maps` com `alpha`. São mapeadas por UV (0..1 sobre o quadrilátero do decalque)
e cobrem pouca área: o que vale é o contorno irregular e as bordas macias, não a resolução.
"""
import numpy as np

from . import texgen as T
from .texgen import Maps


def _ragged_disc(rng, size, radius, ragged=0.35):
    """Máscara 0..1 de um disco de borda rasgada, centrado."""
    u, v = T.unit_grid(size, size)
    distance = np.hypot(u - 0.5, v - 0.5) / radius
    noise = T.fbm(rng, size, size, 4, 5, 0.6)
    return distance + (noise - 0.5) * ragged * 2


def plaster_patch(rng, size=256):
    """Placa de reboco exposta por onde o papel caiu: cinza-claro, resíduo de cola marrom e borda de papel rasgado."""
    field = _ragged_disc(rng, size, 0.46, 0.55)
    shape = T.threshold(1.0 - field, 0.0, 0.05)
    plaster = T.gain(T.solid(size, size, (0.40, 0.385, 0.34)), 0.8 + 0.4 * T.fbm(rng, size, size, 8, 4))
    glue = T.threshold(T.fbm(rng, size, size, 5, 4), 0.55, 0.2)
    stain = np.array((0.19, 0.12, 0.07), np.float32) * np.ones((size, size, 1), np.float32)
    image = T.lerp(plaster, stain, glue * 0.55)
    rim = np.clip(1.0 - np.abs(field - 0.92) / 0.08, 0, 1)
    image = T.lerp(image, np.array((0.60, 0.57, 0.46), np.float32) * np.ones((size, size, 1), np.float32), rim * 0.7)
    height = 0.45 + 0.2 * rim + 0.1 * (T.fbm(rng, size, size, 10, 3) - 0.5)
    return Maps(T.finish(image), T.height_map(height), T.rough_map(np.full((size, size), 0.95)), T.height_map(shape))


def mold_blotch(rng, size=256):
    """Mofo: manchas escuras verde-enegrecidas de contorno macio, mais densas no centro."""
    cloud = T.fbm(rng, size, size, 4, 6, 0.62)
    u, v = T.unit_grid(size, size)
    falloff = np.clip(1.0 - np.hypot(u - 0.5, v - 0.5) / 0.5, 0, 1)
    density = T.smooth((cloud * 1.2 + falloff * 0.9 - 0.75) * 2.2)
    dots = T.threshold(T.fbm(rng, size, size, 22, 3), 0.62, 0.1) * falloff
    alpha = np.clip(density * 0.85 + dots * 0.5, 0, 0.92)
    color = T.lerp(T.solid(size, size, (0.025, 0.035, 0.022)), T.solid(size, size, (0.07, 0.085, 0.05)), cloud)
    return Maps(T.finish(color), None, T.rough_map(np.full((size, size), 0.9)), T.height_map(alpha))


def _crack_walk(rng, mask, x, y, angle, steps, wander, weight, branch_chance, depth=0):
    """Risca `mask` com uma fissura: direção quase reta (`wander` pequeno), de vez em quando um galho mais curto."""
    size = mask.shape[0]
    for step in range(steps):
        angle += rng.normal(0.0, wander)
        x, y = x + np.cos(angle), y + np.sin(angle)
        if not (0 <= x < size and 0 <= y < size):
            return
        mask[int(y), int(x)] = max(mask[int(y), int(x)], weight)
        if depth < 2 and rng.random() < branch_chance:
            side = rng.choice((-1.0, 1.0)) * rng.uniform(0.5, 1.0)
            _crack_walk(rng, mask, x, y, angle + side, int(steps * rng.uniform(0.1, 0.3)), wander * 1.4,
                        weight * 0.7, branch_chance * 0.5, depth + 1)


def wall_crack(rng, size=256):
    """Rachadura de parede: uma fissura fina que atravessa o decalque quase em linha reta, com poucos galhos."""
    mask = np.zeros((size, size))
    y0 = size * rng.uniform(0.25, 0.75)
    _crack_walk(rng, mask, 0.0, y0, rng.normal(0.0, 0.25), int(size * 1.4), 0.07, 1.0, 0.014)
    line = np.clip(T.blur(mask, 0.7) * 3.4, 0, 1)
    halo = np.clip(T.blur(mask, 2.4) * 5.0, 0, 1) * 0.35
    alpha = np.clip(line * 0.85 + halo, 0, 0.9)
    color = T.solid(size, size, (0.05, 0.043, 0.036))
    return Maps(T.finish(color), T.height_map(0.55 - 0.45 * line), T.rough_map(np.full((size, size), 0.95)),
                T.height_map(alpha))


def damp_stain(rng, size=256):
    """Mancha de infiltração: miolo amarelado e anel marrom escuro na borda (marca da água que secou)."""
    field = _ragged_disc(rng, size, 0.44, 0.45)
    inside = T.threshold(1.0 - field, 0.0, 0.04)
    ring = np.clip(1.0 - np.abs(field - 0.9) / 0.1, 0, 1) * inside
    core = T.smooth((0.9 - field) / 0.9) * inside
    alpha = np.clip(core * 0.40 + ring * 0.60, 0, 0.8)
    color = T.lerp(T.solid(size, size, (0.30, 0.20, 0.08)), T.solid(size, size, (0.12, 0.07, 0.03)), ring)
    return Maps(T.finish(color), None, T.rough_map(np.full((size, size), 0.9)), T.height_map(alpha))


def cobweb(rng, size=256):
    """Teia de canto: raios a partir de um vértice e fios em arcos entre eles. (0, 0) é o canto."""
    u, v = T.unit_grid(size, size)
    radius = np.hypot(u, v)
    angle = np.arctan2(v, u)
    spokes = 7
    jitter = (np.array([rng.random() for _ in range(spokes)]) - 0.5) * 0.08
    spoke_pos = np.linspace(0.04, np.pi / 2 - 0.04, spokes) + jitter
    web = np.zeros((size, size))
    for theta in spoke_pos:
        web = np.maximum(web, np.exp(-((np.sin(angle - theta) * radius) / 0.004) ** 2) * (radius < 0.95))
    rings = np.zeros((size, size))
    for ring in np.linspace(0.12, 0.9, 9):
        sag = 0.012 * np.sin(angle * 9)
        rings = np.maximum(rings, np.exp(-((radius - ring - sag) / 0.0035) ** 2) * (angle > spoke_pos[0] - 0.02) *
                           (angle < spoke_pos[-1] + 0.02))
    thin = np.clip(web * 0.8 + rings * 0.55, 0, 1)
    holes = T.threshold(T.fbm(rng, size, size, 6, 3), 0.72, 0.1)
    thin = thin * (1 - 0.8 * holes)
    return Maps(T.finish(T.solid(size, size, (0.55, 0.55, 0.52))), None, T.rough_map(np.full((size, size), 0.8)),
                T.height_map(thin * 0.75))


def picture_ghost(rng, size=256):
    """Retângulo onde um quadro ficou anos pendurado: o papel de parede ali não desbotou, e a poeira marcou o alto."""
    u, v = T.unit_grid(size, size)
    inside = (T.threshold(0.5 - np.abs(u - 0.5) * 1.02, 0.0, 0.006)
              * T.threshold(0.5 - np.abs(v - 0.5) * 1.02, 0.0, 0.006))
    soft = T.blur(inside, 1.4)
    dust_top = np.exp(-((v - 0.985) / 0.012) ** 2) * inside
    fresh = T.solid(size, size, (0.36, 0.33, 0.25)) * (0.9 + 0.2 * T.fbm(rng, size, size, 5, 3))[..., None]
    image = T.lerp(fresh, T.solid(size, size, (0.10, 0.09, 0.07)), np.clip(dust_top * 1.2, 0, 1))
    alpha = np.clip(soft * 0.5 + dust_top * 0.4, 0, 0.7)
    return Maps(T.finish(image), None, T.rough_map(np.full((size, size), 0.9)), T.height_map(alpha))


def height_marks(rng, size=256):
    """Marcas de altura a lápis numa ombreira: riscos curtos de tamanhos diferentes, de baixo para cima."""
    u, v = T.unit_grid(size, size)
    marks = np.zeros((size, size))
    for k in range(9):
        y = 0.07 + k * 0.105 + rng.uniform(-0.01, 0.01)
        reach = rng.uniform(0.35, 0.8)
        wobble = rng.uniform(-0.01, 0.01)
        line = np.exp(-((v - (y + wobble * (u - 0.5))) / 0.0045) ** 2) * (u < reach) * (u > 0.1)
        marks = np.maximum(marks, line)
        if k % 2 == 0:
            tick = np.exp(-((u - reach - 0.02) / 0.06) ** 2) * np.exp(-((v - (y + 0.018)) / 0.008) ** 2)
            marks = np.maximum(marks, tick * 0.7)
    alpha = np.clip(T.blur(marks, 0.6) * 1.6, 0, 0.75)
    return Maps(T.finish(T.solid(size, size, (0.12, 0.115, 0.11))), None, T.rough_map(np.full((size, size), 0.8)),
                T.height_map(alpha))


def mouse_hole(rng, size=128):
    """Buraco de rato no rodapé: arco escuro de borda roída, com algumas bolinhas escuras embaixo."""
    u, v = T.unit_grid(size, size)
    radius = np.hypot((u - 0.5) / 0.30, (v - 0.40) / 0.36)
    gnaw = T.fbm(rng, size, size, 8, 3)
    hole = T.threshold(1.0 - radius + (gnaw - 0.5) * 0.35, 0.0, 0.05) * (v > 0.12)
    rim = np.clip(1.0 - np.abs(radius - 1.12) / 0.14, 0, 1) * (1 - hole)
    droppings = np.zeros((size, size))
    for _ in range(6):
        cx, cy = rng.uniform(0.15, 0.85), rng.uniform(0.02, 0.1)
        droppings = np.maximum(droppings, np.exp(-(((u - cx) / 0.03) ** 2 + ((v - cy) / 0.014) ** 2)))
    dark = np.clip(hole + droppings, 0, 1)
    color = T.lerp(T.solid(size, size, (0.30, 0.22, 0.13)), T.solid(size, size, (0.01, 0.01, 0.01)), dark)
    alpha = np.clip(hole * 0.98 + rim * 0.55 + droppings * 0.9, 0, 1)
    return Maps(T.finish(color), None, T.rough_map(np.full((size, size), 0.9)), T.height_map(alpha))


def drip_streaks(rng, size=256):
    """Escorrido de sujeira sob o peitoril da janela: riscos verticais escuros que somem com a descida."""
    u, v = T.unit_grid(size, size)
    streaks = np.zeros((size, size))
    for _ in range(5):
        x = rng.uniform(0.15, 0.85)
        width = rng.uniform(0.012, 0.035)
        length = rng.uniform(0.45, 0.95)
        fade = np.clip((v - (1.0 - length)) / length, 0, 1) ** 1.3
        streaks = np.maximum(streaks, np.exp(-((u - x - 0.02 * np.sin(v * 9 + x * 20)) / width) ** 2) * fade)
    streaks *= 0.75 + 0.25 * T.value_noise(rng, size, size, 4, 24)
    alpha = np.clip(streaks * 0.55, 0, 0.55)
    return Maps(T.finish(T.solid(size, size, (0.11, 0.09, 0.06))), None, T.rough_map(np.full((size, size), 0.9)),
                T.height_map(alpha))


def soot_halo(rng, size=256):
    """Anel de fumaça e poeira ao redor de uma luminária de teto: cinza-escuro, mais forte na borda do plafon."""
    u, v = T.unit_grid(size, size)
    radius = np.hypot(u - 0.5, v - 0.5) / 0.5
    ring = np.exp(-((radius - 0.45) / 0.28) ** 2) * (radius < 1.0)
    streaks = 0.7 + 0.3 * T.fbm(rng, size, size, 7, 4)
    alpha = np.clip(ring * streaks * 0.45, 0, 0.5) * T.smooth((1.0 - radius) / 0.3)
    return Maps(T.finish(T.solid(size, size, (0.07, 0.06, 0.05))), None, T.rough_map(np.full((size, size), 0.95)),
                T.height_map(alpha))


def dirt_halo(rng, size=128):
    """Mancha de dedos em volta de um interruptor: halo suave, mais escuro nos lados da placa."""
    u, v = T.unit_grid(size, size)
    radius = np.hypot((u - 0.5) / 0.5, (v - 0.5) / 0.5)
    alpha = np.clip(T.smooth((1.0 - radius) / 0.7) * (0.55 + 0.45 * T.fbm(rng, size, size, 6, 3)) * 0.42, 0, 0.45)
    return Maps(T.finish(T.solid(size, size, (0.09, 0.075, 0.05))), None, T.rough_map(np.full((size, size), 0.9)),
                T.height_map(alpha))
