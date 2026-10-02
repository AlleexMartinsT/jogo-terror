"""Árvores e arbustos mortos: tronco torto com raízes aparentes e galhos que se ramificam recursivamente.

`grow` gera cada galho como um tubo afunilado de poucos pontos (uma leve curva) e sorteia os filhos a partir
dele; a profundidade e o comprimento caem a cada geração, então dezenas de galhos saem de uma chamada só.
As árvores de longe (a mata do horizonte) usam a mesma função com profundidade menor e material de silhueta.
"""
import math

import numpy as np

from .. import layout
from . import ext_common as ext

GROUND_Z = -0.12
TREE_SPOTS = [(-3.2, -3.0), (9.6, -3.4), (19.0, -3.2), (-2.5, 13.0), (6.0, 14.5), (15.5, 12.5), (-9.0, 5.0),
              (24.5, 9.0), (-8.5, -12.0), (26.0, -4.0)]
SILHOUETTE = "night_silhouette"


def _unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-9)


def _bent_path(rng, start, direction, length, sag=0.12, points=4):
    """Pontos de um galho que se curva suavemente para baixo e de lado enquanto cresce."""
    direction = _unit(direction)
    side = _unit(np.cross(direction, (0.0, 0.0, 1.0)) + 1e-6)
    drift = rng.uniform(-0.18, 0.18)
    path = [np.asarray(start, float)]
    for k in range(1, points):
        t = k / (points - 1)
        offset = side * drift * length * t * t - np.array([0.0, 0.0, 1.0]) * sag * length * t * t
        path.append(start + direction * length * t + offset)
    return path


def grow(m, rng, start, direction, length, radius, depth, mat, sides=5, children=(2, 3), up_bias=0.22, spread=0.62):
    """Galho que se ramifica `depth` vezes. Devolve a ponta, para quem quiser pendurar algo nela."""
    path = _bent_path(rng, start, direction, length, points=4 if depth > 1 else 3)
    radii = [radius * (1.0 - 0.55 * t) for t in np.linspace(0, 1, len(path))]
    ext.sweep_circle(m, [tuple(p) for p in path], radius, mat, sides=sides, radii=radii, caps="end")
    if depth == 0:
        return path[-1]
    for _ in range(rng.randint(*children)):
        t = rng.uniform(0.35, 0.95)
        index = min(int(t * (len(path) - 1)), len(path) - 2)
        origin = path[index] + (path[index + 1] - path[index]) * (t * (len(path) - 1) - index)
        heading = rng.uniform(0, 2 * math.pi)
        turned = _unit(_unit(direction) + np.array([math.cos(heading), math.sin(heading), 0.0]) * spread + np.array([0, 0, up_bias]))
        grow(m, rng, origin, turned, length * rng.uniform(0.55, 0.78), radius * 0.6, depth - 1, mat, max(3, sides - 1), children,
             up_bias, spread)
    return path[-1]


def _trunk(m, rng, x, y, height, mat, sides=10):
    """Tronco ligeiramente torto, mais grosso embaixo, com quatro raízes aparentes."""
    top = (x + rng.uniform(-0.35, 0.35), y + rng.uniform(-0.35, 0.35))
    path = [(x + (top[0] - x) * t ** 1.5 + 0.06 * math.sin(7 * t), y + (top[1] - y) * t ** 1.5 + 0.05 * math.cos(5 * t), GROUND_Z - 0.05 + height * t)
            for t in np.linspace(0, 1, 9)]
    radii = [0.30 * (1 - t) ** 0.8 + 0.08 for t in np.linspace(0, 1, 9)]
    ext.sweep_circle(m, path, 0.3, mat, sides=sides, radii=radii, caps=True)
    for k in range(4):
        a = rng.uniform(0, 2 * math.pi) + k * math.pi / 2
        root = [(x + 0.1 * math.cos(a), y + 0.1 * math.sin(a), GROUND_Z + 0.55), (x + 0.45 * math.cos(a), y + 0.45 * math.sin(a), GROUND_Z + 0.12),
                (x + 0.95 * math.cos(a), y + 0.95 * math.sin(a), GROUND_Z - 0.04)]
        ext.sweep_circle(m, root, 0.11, mat, sides=5, radii=[0.12, 0.08, 0.025], caps=False)
    return path


def dead_tree(m, rng, x, y, height, mat="bark", limbs=(5, 7), depth=2, sides=8, children=(2, 2)):
    """Árvore morta completa: tronco e galhos maiores saindo do terço de cima, cada um com sua ramificação."""
    trunk = _trunk(m, rng, x, y, height, mat, sides)
    for _ in range(rng.randint(*limbs)):
        t = rng.uniform(0.38, 0.97)
        base = np.array(trunk[min(int(t * (len(trunk) - 1)), len(trunk) - 1)])
        heading = rng.uniform(0, 2 * math.pi)
        direction = (math.cos(heading) * 0.9, math.sin(heading) * 0.9, rng.uniform(0.35, 0.9))
        grow(m, rng, base, direction, height * rng.uniform(0.20, 0.34) * (1.2 - t * 0.5), 0.085 * (1.2 - t * 0.4), depth, mat, sides=5,
             children=children)
    grow(m, rng, np.array(trunk[-1]), (0.1, 0.1, 1.0), height * 0.22, 0.07, max(depth - 1, 0), mat, sides=5, children=children)


def dead_shrub(m, rng, x, y, size, mat="bark"):
    """Arbusto seco: dezenas de varetas partindo do chão em leque, com ramificação fina."""
    for _ in range(rng.randint(6, 9)):
        heading = rng.uniform(0, 2 * math.pi)
        direction = (math.cos(heading) * rng.uniform(0.3, 0.8), math.sin(heading) * rng.uniform(0.3, 0.8), 1.0)
        grow(m, rng, np.array((x + 0.05 * math.cos(heading), y + 0.05 * math.sin(heading), GROUND_Z)), direction, size * rng.uniform(0.5, 0.9),
             0.011, 1, mat, sides=3, children=(2, 2), up_bias=0.1, spread=0.7)


def build(ctx):
    ext.start(ctx)
    rng = ext.rng_for(ctx, "trees")
    near = ext.builder("Trees_Near", ext.PROFILED)
    for x, y in TREE_SPOTS:
        dead_tree(near, rng, x, y, rng.uniform(5.0, 7.8), children=(2, 3))
    ext.emit(ctx, near)

    far = ext.builder("Trees_Far", ext.PROFILED)
    placed = 0
    while placed < ext.scaled(ctx, 46):
        angle, radius = rng.uniform(0, 2 * math.pi), rng.uniform(40.0, 120.0)
        x, y = 6.0 + math.cos(angle) * radius, 5.0 + math.sin(angle) * radius
        if layout.ROAD.y0 - 3 < y < layout.ROAD.y1 + 3:
            continue
        dead_tree(far, rng, x, y, rng.uniform(6.0, 10.0), SILHOUETTE, limbs=(4, 5), depth=0, sides=4)
        placed += 1
    ext.emit(ctx, far)
