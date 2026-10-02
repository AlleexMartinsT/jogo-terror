"""Casas vizinhas apagadas: fachada, telhado de telhas, varanda com colunas, janelas com caixilho e veneziana,
chaminé de tijolo e garagem anexa. Ficam a mais de 20 m da janela, então as telhas são mais grossas e as tábuas
vêm da textura; o que importa é a silhueta, a profundidade dos vãos e o telhado recortando o céu.
"""
import math

import numpy as np

from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401
from . import roof, trees

GROUND_Z = -0.12
SIDE_LOTS = [layout.Rect(-34.0, -4.0, -18.0, 14.0), layout.Rect(28.0, -4.0, 44.0, 14.0)]
SIDING = "wall_siding_ext"
WALL_HEIGHT = 5.4


def _window(m, x, z, width, height, y_front, shutters, lit_off=True):
    """Janela de guilhotina vista de fora: guarnição, vidro fundo escuro, travessa de encontro e (às vezes) venezianas."""
    m.box(x, y_front - 0.02, z - 0.07, width + 0.16, 0.05, height + 0.2, "trim_white")
    m.box(x, y_front + 0.005, z, width, 0.04, height, "glass_dark")
    for k in range(1, 3):
        m.box(x - width / 2 + width * k / 3, y_front - 0.012, z, 0.035, 0.03, height, "trim_white")
    m.box(x, y_front - 0.012, z + height / 2, width, 0.03, 0.05, "trim_white")
    m.box(x, y_front - 0.06, z - 0.09, width + 0.3, 0.12, 0.05, "trim_white")
    if shutters:
        for side in (-1, 1):
            m.box(x + side * (width / 2 + 0.28), y_front - 0.03, z - 0.03, 0.34, 0.035, height + 0.06, "wall_green")


def _porch(m, rng, door_x, y_front):
    """Varanda de entrada: laje, duas colunas torneadas, viga e uma cobertura de uma água com telhas grossas."""
    m.box(door_x, y_front - 0.9, GROUND_Z, 2.6, 1.8, 0.15, "sidewalk")
    for side in (-1, 1):
        m.lathe([(0.08, 0.0), (0.06, 0.2), (0.055, 2.2), (0.075, 2.3)], door_x + side * 1.15, y_front - 1.55, 0.0, "trim_white", seg=10)
    m.box(door_x, y_front - 0.85, 2.30, 2.9, 1.7, 0.12, "trim_white")
    slope = roof.Slope(y_front - 1.95, 2.52, y_front, 3.0, door_x - 1.45, door_x + 1.45)
    roof._deck(m, slope)
    roof.shingle_slope(m, rng, slope, damage=0.03, pitch=3.0)


def _door(m, x, y_front):
    m.box(x, y_front - 0.03, 0.0, 1.1, 0.07, 2.2, "trim_white")
    m.box(x, y_front, 0.0, 0.9, 0.05, 2.05, "door_paint")
    m.cylinder(x + 0.33, y_front - 0.04, 1.0, 0.025, 0.03, "brass_worn", seg=8)


RIDGE_CAP = [(-0.17, -0.02), (0.0, 0.04), (0.17, -0.02), (0.17, -0.034), (0.0, 0.024), (-0.17, -0.034)]


def _roof_gable(m, rng, width, depth, eave_z, rise, overhang=0.5, coarse=3.0):
    """Telhado de duas águas com a cumeeira ao longo de X, em coordenadas locais da casa."""
    slope = rise / (depth / 2)
    for side in (-1, 1):
        y_edge = side * (depth / 2 + overhang)
        z_edge = eave_z - slope * overhang
        sl = roof.Slope(y_edge, z_edge, 0.0, eave_z + rise, -width / 2 - overhang, width / 2 + overhang)
        roof._deck(m, sl)
        roof._fascia(m, sl)
        roof.shingle_slope(m, rng, sl, damage=0.03, pitch=coarse)
    for x in (-width / 2, width / 2):
        m.extrude([(-depth / 2, eave_z), (depth / 2, eave_z), (0.0, eave_z + rise - roof.DECK_THICKNESS)], "yz", x - 0.12, x + 0.12, SIDING)
    x = -width / 2 - overhang
    while x < width / 2 + overhang:
        m.extrude([(a, eave_z + rise + b) for a, b in RIDGE_CAP], "yz", x, x + 0.32, roof.SHINGLE)
        x += 0.33


def house(m, rng, cx, cy, yaw, width, depth, floors):
    """Uma casa de frente para -y local, girada por `yaw` e centrada em (cx, cy)."""
    height = WALL_HEIGHT if floors == 2 else 2.9
    with m.at(cx, cy, GROUND_Z, rz=yaw):
        m.box(0, 0, 0, width, depth, height, SIDING)
        m.box(0, 0, 0, width + 0.06, depth + 0.06, 0.5, "wall_brick_ext")
        y_front = -depth / 2
        door_x = rng.choice((-1, 1)) * width * 0.18
        _door(m, door_x, y_front)
        _porch(m, rng, door_x, y_front)
        columns = max(2, int(width // 2.7))
        for level in range(floors):
            for k in range(columns):
                x = -width / 2 + (k + 0.5) * width / columns
                if level == 0 and abs(x - door_x) < 1.5:
                    continue
                _window(m, x, 1.0 + level * 2.8, 1.0, 1.25, y_front, shutters=(level == 0 and rng.random() < 0.7))
        for side in (-1, 1):
            for level in range(floors):
                with m.at(side * width / 2, 0, 0, rz=90 * side):
                    _window(m, 0, 1.0 + level * 2.8, 0.9, 1.25, 0.0, False)
        _roof_gable(m, rng, width, depth, height + 0.12, 2.2 if floors == 2 else 1.7)
        m.box(-width * 0.3, 0.0, height, 0.8, 0.8, 2.4, "wall_brick_ext")
        m.box(-width * 0.3, 0.0, height + 2.4, 0.95, 0.95, 0.08, "concrete")
        annex = width / 2 + 2.2
        m.box(annex, 0.4, 0, 4.4, depth - 0.8, 2.7, SIDING)
        m.box(annex, 0.4 - (depth - 0.8) / 2 - 0.01, 0.0, 3.4, 0.06, 2.2, "door_garage_metal")
        m.box(annex, 0.4, 2.7, 4.8, depth - 0.4, 0.25, "trim_white")


def build(ctx):
    ext.start(ctx)
    rng = ext.rng_for(ctx, "neighbors")
    m = ext.builder("Neighbors", ext.PROFILED)
    for lot in layout.NEIGHBOR_LOTS:
        width, depth = rng.uniform(9.0, 11.0), rng.uniform(8.0, 9.5)
        x = lot.x0 + rng.uniform(1.0, 3.0) + width / 2
        house(m, rng, x, lot.y1 - 3.0 - depth / 2, 180, width, depth, 2)
    for lot in SIDE_LOTS:
        width, depth = rng.uniform(9.0, 11.0), rng.uniform(8.0, 9.5)
        x = lot.x0 + rng.uniform(1.0, 3.0) + width / 2
        house(m, rng, x, lot.y0 + 3.0 + depth / 2, 0, width, depth, 2)
    ext.emit(ctx, m)

    extra = ext.builder("Neighbors_Trees", ext.PROFILED)
    for lot in (*layout.NEIGHBOR_LOTS, *SIDE_LOTS):
        for _ in range(2):
            trees.dead_tree(extra, rng, rng.uniform(lot.x0 + 1, lot.x1 - 1), rng.uniform(lot.y0 + 1, lot.y1 - 1), rng.uniform(4.5, 7.0),
                            limbs=(5, 7), depth=2, sides=8)
    ext.emit(ctx, extra)
