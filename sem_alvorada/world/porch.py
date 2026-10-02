"""Varanda da porta da frente: laje de concreto lascada, dois degraus, colunas torneadas, guarda-corpo com balaústres
torneados, cobertura de uma água com telhas e forro de réguas, lampião, campainha, placa com o número da casa
e as coisas que ficaram na entrada (jornais, vaso seco, capacho).

Também faz o degrau dos fundos, na porta da cozinha.
"""
import math

import numpy as np

from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401
from . import roof

GROUND_Z = -0.12
SLAB_HALF_WIDTH = 1.20
SLAB_DEPTH = 1.75
COLUMN_TOP = 2.70
CANOPY_HIGH, CANOPY_LOW = 3.10, 2.72
HOUSE_NUMBER = "412"


def _front_x():
    door = layout.OPENINGS["front"]
    return (door.a + door.b) / 2


def _slab(m, cx):
    """Laje e dois degraus, com cantos quebrados e rachaduras."""
    wall = layout.WALL_T_EXT / 2
    m.box(cx, -(wall + SLAB_DEPTH) / 2 + 0.0, -0.5, 2 * SLAB_HALF_WIDTH, SLAB_DEPTH - wall, 0.5, "sidewalk")
    m.box(cx, -SLAB_DEPTH - 0.25, -0.5, 1.72, 0.50, 0.435, "sidewalk")
    m.box(cx, -SLAB_DEPTH - 0.80, GROUND_Z, 1.0, 0.62, 0.05, "sidewalk")
    for dx, length in ((-0.55, 0.9), (0.6, 0.6)):                      # fissuras da laje
        m.box(cx + dx, -1.1, -0.0005, 0.006, length, 0.002, "black")
    m.box(cx + 0.9, -SLAB_DEPTH + 0.02, -0.001, 0.30, 0.08, 0.004, "ext_mortar")


def _column(m, x, y, z0, height):
    """Coluna torneada: plinto, base em toro, fuste com leve entasis, colar e capitel."""
    profile = [(0.115, 0.0), (0.115, 0.07), (0.088, 0.08), (0.092, 0.11), (0.074, 0.13), (0.066, 0.20),
               (0.063, height * 0.5), (0.060, height - 0.22), (0.068, height - 0.19), (0.062, height - 0.15),
               (0.078, height - 0.12), (0.112, height - 0.06), (0.112, height)]
    m.lathe(profile, x, y, z0, "trim_white", seg=16, smooth=True, cap_bottom=True, cap_top=True)
    m.box(x, y, z0 + height, 0.28, 0.28, 0.07, "trim_white")


def _baluster(m, x, y, z0, height):
    profile = [(0.026, 0.0), (0.026, 0.03), (0.016, 0.05), (0.016, 0.12), (0.028, height * 0.33), (0.018, height * 0.45),
               (0.018, height * 0.55), (0.03, height * 0.66), (0.016, height * 0.8), (0.026, height - 0.04), (0.026, height)]
    m.lathe(profile, x, y, z0, "trim_white", seg=8, smooth=True)


def _railing(m, cx):
    """Guarda-corpo dos dois lados, ao longo de Y: corrimão, travessa, balaústres; faltam dois e um está torto."""
    for side in (-1, 1):
        x = cx + side * (SLAB_HALF_WIDTH - 0.07)
        y0, y1 = -SLAB_DEPTH + 0.1, -layout.WALL_T_EXT / 2 - 0.05
        m.box(x, (y0 + y1) / 2, 0.88, 0.075, y1 - y0 + 0.16, 0.045, "trim_white")
        m.box(x, (y0 + y1) / 2, 0.88 - 0.015, 0.05, y1 - y0, 0.02, "trim_white")
        m.box(x, (y0 + y1) / 2, 0.095, 0.06, y1 - y0 + 0.1, 0.05, "trim_white")
        y = y0 + 0.08
        index = 0
        while y < y1 - 0.04:
            if not (side < 0 and index in (4, 9)):
                tilt = 6.0 if (side > 0 and index == 6) else 0.0
                with m.at(x, y, 0.145, ry=tilt):
                    _baluster(m, 0, 0, 0, 0.74)
            y += 0.115
            index += 1


def _canopy(ctx, cx):
    """Cobertura de uma água sobre a porta: laje, fascia, forro de réguas e telhas."""
    x0, x1 = cx - SLAB_HALF_WIDTH - 0.18, cx + SLAB_HALF_WIDTH + 0.18
    wall = -layout.WALL_T_EXT / 2
    slope = roof.Slope(-2.05, CANOPY_LOW, wall, CANOPY_HIGH, x0, x1)
    deck = ext.builder("Porch_Roof", ext.PROFILED)
    roof._deck(deck, slope)
    roof._fascia(deck, slope)
    for sign, x in ((-1, x0), (1, x1)):
        roof._rake(deck, slope, x, sign)
    for k in range(int((x1 - x0) / 0.09)):                                   # frestas entre as réguas do forro
        deck.box(x0 + 0.045 + k * 0.09, (wall - 2.05) / 2, CANOPY_LOW - roof.DECK_THICKNESS - 0.006, 0.006, 2.05 + wall, 0.004,
                 "black")
    ext.emit(ctx, deck)
    tiles = ext.builder("Porch_Shingles", ext.PROFILED)
    roof.shingle_slope(tiles, ext.rng_for(ctx, "porch_roof"), slope, damage=0.02)
    ext.emit(ctx, tiles)


def _lantern(m, x, y):
    """Lampião de parede: suporte, caixa de vidro apagado, teto e argola."""
    m.box(x, y - 0.015, 1.70, 0.07, 0.03, 0.19, "iron_black")
    m.box(x, y - 0.085, 1.74, 0.12, 0.12, 0.24, "glass_dark")
    for dx in (-0.06, 0.06):
        for dy in (-0.06, 0.06):
            m.box(x + dx, y - 0.085 + dy, 1.74, 0.014, 0.014, 0.24, "iron_black")
    m.frustum(x, y - 0.085, 1.98, 0.16, 0.16, 0.05, 0.05, 0.07, "iron_black")
    m.box(x, y - 0.085, 1.72, 0.14, 0.14, 0.02, "iron_black")


def _doorbell_and_number(m, cx):
    wall = -layout.WALL_T_EXT / 2
    m.box(cx + 0.74, wall - 0.012, 1.18, 0.05, 0.024, 0.09, "plastic_ivory")
    m.cylinder(cx + 0.74, wall - 0.026, 1.205, 0.012, 0.01, "brass_worn", seg=10)
    m.panel(cx - 0.72, wall - 0.016, 1.62, 0.20, 0.10, "ext_plaque", "front")
    m.box(cx - 0.72, wall - 0.01, 1.57, 0.22, 0.02, 0.10, "wood_dark")


def _things_left_behind(m, cx):
    """Jornais enrolados em saco plástico, um vaso com a planta morta e o capacho."""
    wall = layout.WALL_T_EXT / 2
    for k, (dx, dy, angle) in enumerate(((0.80, -0.75, 20), (0.60, -0.90, 80), (0.88, -1.05, 150))):
        with m.at(cx + dx, dy, 0.045, rz=angle):
            m.tube((-0.18, 0, 0), (0.18, 0, 0), 0.045, "paper_white", seg=10)
            m.tube((0.1, 0, 0.0), (0.2, 0, 0.0), 0.047, "plastic_white_aged", seg=10)
    m.lathe([(0.10, 0.0), (0.14, 0.04), (0.17, 0.26), (0.19, 0.31), (0.17, 0.32)], cx - 0.82, -0.55, 0.0, "ceramic_cream",
            seg=14, cap_top=False)
    m.cylinder(cx - 0.82, -0.55, 0.28, 0.16, 0.02, "carpet_stain", seg=12)
    for k in range(7):
        a = k * 0.9
        m.tube((cx - 0.82, -0.55, 0.29), (cx - 0.82 + 0.12 * math.cos(a), -0.55 + 0.12 * math.sin(a), 0.62 + 0.04 * k), 0.004,
               "wood_dark", seg=4)
    m.box(cx, -0.55, 0.0005, 0.74, 0.46, 0.014, "carpet_brown")
    m.box(cx, -0.55, 0.0145, 0.64, 0.36, 0.002, "carpet_stain")


def build_front(ctx):
    cx = _front_x()
    m = ext.builder("Porch", ext.FINE)
    _slab(m, cx)
    for side in (-1, 1):
        _column(m, cx + side * (SLAB_HALF_WIDTH - 0.07), -SLAB_DEPTH + 0.14, 0.0, COLUMN_TOP)
    _railing(m, cx)
    _lantern(m, cx + 0.95, -layout.WALL_T_EXT / 2)
    _doorbell_and_number(m, cx)
    _things_left_behind(m, cx)
    ext.emit(ctx, m)
    _canopy(ctx, cx)


def build_back(ctx):
    """Degrau de concreto dos fundos e a luminária da porta da cozinha."""
    back = layout.OPENINGS["back"]
    bx = (back.a + back.b) / 2
    wall = layout.WALL_T_EXT / 2
    m = ext.builder("Stoop", ext.FINE)
    m.box(bx, 10.0 + wall + 0.45, -0.5, 1.6, 0.9 - 0.0, 0.5, "sidewalk")
    m.box(bx, 10.0 + wall + 1.15, -0.5, 1.2, 0.5, 0.44, "sidewalk")
    m.box(bx + 0.9, 10.0 + wall + 0.4, 0.0, 0.5, 0.5, 0.05, "black")
    ext.emit(ctx, m)


def build(ctx):
    ext.start(ctx)
    build_front(ctx)
    build_back(ctx)
