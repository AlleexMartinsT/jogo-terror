"""Telhados de duas águas (casa e garagem): estrutura, beiral com forro e fascia, telhas individuais em fiadas,
cumeeira de peças, rufo na parede, empenas com respiro e saídas de ventilação.

A cumeeira corre ao longo de X, então as empenas ficam nas paredes leste e oeste. Cada água é uma laje
(topo de feltro, forro de beiral por baixo) coberta por fiadas de telhas de três abas. A calha, o condutor e a chaminé
estão em `drainage` e `chimney`.
"""
import math
from dataclasses import dataclass

import numpy as np

from .. import conventions as C
from .. import layout
from . import chimney, drainage
from . import ext_common as ext
from . import ext_materials  # noqa: F401  (registra ext_shingle e companhia)

DECK_THICKNESS = 0.14
GABLE_SINK = 0.10          # a base da empena entra no topo da parede
WALL_CLEARANCE = 0.07      # a laje passa este tanto acima do topo da parede, senão a quina da parede fura as telhas
EXPOSURE = 0.145           # parte visível de cada fiada
TAB_WIDTH = 0.333
TAB_GAP = 0.007
TAB_LENGTH = 0.215
TAB_THICKNESS = 0.008
UV_WINDOW = 0.28
SHINGLE = "ext_shingle"
FELT = "rubber"


@dataclass(frozen=True)
class Slope:
    """Uma água do telhado: reta da borda do beiral (`y_edge`, `z_edge`) até a cumeeira, entre x0 e x1."""
    y_edge: float
    z_edge: float
    y_ridge: float
    z_ridge: float
    x0: float
    x1: float

    @property
    def length(self):
        return math.hypot(self.y_ridge - self.y_edge, self.z_ridge - self.z_edge)

    @property
    def direction(self):
        return np.array([0.0, self.y_ridge - self.y_edge, self.z_ridge - self.z_edge]) / self.length

    @property
    def normal(self):
        """Normal para cima, perpendicular à água."""
        d = self.direction
        n = np.cross([1.0, 0.0, 0.0], d)
        return n if n[2] > 0 else -n

    def point(self, x, along):
        return np.array([x, self.y_edge, self.z_edge]) + self.direction * along

    @property
    def run(self):
        return abs(self.y_ridge - self.y_edge)


class RoofShape:
    """Geometria de um telhado de duas águas sobre um retângulo em planta."""

    def __init__(self, x0, x1, y0, y1, eave_z, ridge_z, overhang, deck_x0=None):
        self.x0, self.x1 = x0, x1
        self.wall_y0, self.wall_y1 = y0, y1
        self.eave_z, self.ridge_z = eave_z, ridge_z
        self.overhang = overhang
        self.ridge_y = (y0 + y1) / 2
        self.wall_z = eave_z + WALL_CLEARANCE
        self.slope = (ridge_z - self.wall_z) / (self.ridge_y - y0)
        self.deck_x0 = x0 - overhang if deck_x0 is None else deck_x0
        self.deck_x1 = x1 + overhang

    def top_z(self, y):
        """Altura da face de cima da laje em y (vale também no beiral, abaixo do nível da parede)."""
        distance = min(y - self.wall_y0, self.wall_y1 - y)
        return self.wall_z + self.slope * distance

    def slopes(self):
        o = self.overhang
        front = Slope(self.wall_y0 - o, self.top_z(self.wall_y0 - o), self.ridge_y, self.ridge_z, self.deck_x0, self.deck_x1)
        back = Slope(self.wall_y1 + o, self.top_z(self.wall_y1 + o), self.ridge_y, self.ridge_z, self.deck_x0, self.deck_x1)
        return front, back


def main_shape():
    house = layout.ROOF
    return RoofShape(0.0, 12.0, 0.0, 10.0, house["eave_z"], house["ridge_z"], house["overhang"])


def garage_shape():
    house = layout.ROOF
    rect = layout.ROOMS["garage"].rect
    return RoofShape(rect.x0, rect.x1, rect.y0, rect.y1, house["garage_eave_z"], house["garage_ridge_z"], house["overhang"],
                     deck_x0=rect.x0)


# --------------------------------------------------------------------------------------------
# Laje, fascia, forro
# --------------------------------------------------------------------------------------------
def _deck(m, slope):
    """Laje da água: topo de feltro, forro de beiral por baixo (trim_white) e fascia na borda do beiral."""
    top = [slope.point(slope.x0, 0), slope.point(slope.x1, 0), slope.point(slope.x1, slope.length), slope.point(slope.x0, slope.length)]
    drop = np.array([0.0, 0.0, -DECK_THICKNESS])
    bottom = [p + drop for p in top]
    ext.poly_out(m, top, FELT, slope.normal)
    ext.poly_out(m, bottom, "trim_white", -slope.normal)
    outward = -np.sign(slope.y_ridge - slope.y_edge)
    ext.poly_out(m, [top[0], top[1], bottom[1], bottom[0]], "trim_white", (0, outward, 0))
    for index, side in ((0, -1), (1, 1)):
        far = (3, 2)[index]
        ext.poly_out(m, [top[index], top[far], bottom[far], bottom[index]], "trim_white", (side, 0, 0))


def _fascia(m, slope):
    """Tábua de fascia na frente da borda, com a aba da cantoneira de metal por cima."""
    outward = -float(np.sign(slope.y_ridge - slope.y_edge))
    y = slope.y_edge + outward * 0.014
    z_top = slope.z_edge + 0.03
    m.box((slope.x0 + slope.x1) / 2, y, z_top - 0.20, slope.x1 - slope.x0 + 0.06, 0.028, 0.20, "trim_white")
    m.box((slope.x0 + slope.x1) / 2, slope.y_edge + outward * 0.002, z_top - 0.002, slope.x1 - slope.x0 + 0.06, 0.07, 0.006, "metal")


def _rake(m, slope, deck_x, outward_x):
    """Tábua de empena (rake) ao longo da água, na borda da empena."""
    x = deck_x + outward_x * 0.014
    path = [tuple(slope.point(x, 0.0)), tuple(slope.point(x, slope.length))]
    ext.sweep_profile(m, path, [(-0.014, -0.17), (0.014, -0.17), (0.014, 0.035), (-0.014, 0.035)], "trim_white", up=(0, 0, 1))


def _rafter_tails(m, slope):
    """Pontas de caibro sob o beiral: a única "construção" que aparece de baixo."""
    outward = -float(np.sign(slope.y_ridge - slope.y_edge))
    x = slope.x0 + 0.4
    while x < slope.x1 - 0.2:
        start = slope.point(x, 0.0)
        end = slope.point(x, min(slope.length, 0.62))
        bottom = np.array([0.0, 0.0, -DECK_THICKNESS - 0.07])
        m.bar(tuple(start + bottom), tuple(end + bottom), 0.05, "trim_white")
        x += 0.61


# --------------------------------------------------------------------------------------------
# Telhas
# --------------------------------------------------------------------------------------------
def _footprint_blocked(x, y, width, length, blocked):
    return any(x < bx1 and x + width > bx0 and y - length < by1 and y + length > by0 for bx0, by0, bx1, by1 in blocked)


def _tab(m, rng, slope, x, along, width, length, lift_left, lift_right):
    """Uma telha: face de cima (com recorte de textura sorteado) e a borda grossa da frente."""
    n = slope.normal * TAB_THICKNESS
    left = slope.point(x, along)
    right = slope.point(x + width, along)
    far_left = slope.point(x, min(along + length, slope.length))
    far_right = slope.point(x + width, min(along + length, slope.length))
    lift = np.array([0.0, 0.0, 1.0])
    p0, p1 = left + n + lift * lift_left, right + n + lift * lift_right
    u0, v0 = rng.random() * (1 - UV_WINDOW), rng.random() * (1 - UV_WINDOW)
    uv = [(u0, v0), (u0 + UV_WINDOW, v0), (u0 + UV_WINDOW, v0 + UV_WINDOW), (u0, v0 + UV_WINDOW)]
    m.quad(tuple(p0), tuple(p1), tuple(far_right + n), tuple(far_left + n), SHINGLE, uv=uv)
    m.quad(tuple(left), tuple(right), tuple(p1), tuple(p0), SHINGLE, uv=uv)


def shingle_slope(m, rng, slope, blocked=(), damage=0.012, pitch=1.0):
    """Cobre a água com fiadas de telhas de três abas: fiadas escalonadas, alturas e tortuosidade sorteadas,
    algumas telhas arqueadas e outras faltando (o feltro escuro aparece).

    `pitch` > 1 engrossa as telhas (casas de longe: menos triângulos, mesma leitura)."""
    exposure, tab_pitch, length = EXPOSURE * pitch, TAB_WIDTH * pitch, TAB_LENGTH * pitch
    course, offsets = 0, (0.0, tab_pitch / 3, 2 * tab_pitch / 3)
    while course * exposure < slope.length - 0.02:
        along = max(-0.02 + course * exposure, 0.0)
        x = slope.x0 - offsets[course % 3] - 0.01
        while x < slope.x1:
            tab_x = max(x, slope.x0 - 0.01)
            tab_w = min(x + tab_pitch - TAB_GAP, slope.x1 + 0.01) - tab_x
            point = slope.point(tab_x, along)
            if tab_w > 0.05 and not _footprint_blocked(tab_x, point[1], tab_w, length, blocked) and rng.random() > damage:
                curl = 0.014 if rng.random() < 0.035 else 0.0
                _tab(m, rng, slope, tab_x, along, tab_w, length, curl + rng.random() * 0.003, rng.random() * 0.003)
            x += tab_pitch
        course += 1


def _ridge_cap(m, rng, shape, x0, x1):
    """Cumeeira de peças dobradas, cada uma com folga e leve rotação."""
    profile = [(-0.17, -0.02), (0.0, 0.04), (0.17, -0.02), (0.17, -0.034), (0.0, 0.024), (-0.17, -0.034)]
    x = x0
    while x < x1:
        length = min(0.30, x1 - x)
        dy = rng.uniform(-0.004, 0.004)
        m.extrude([(shape.ridge_y + dy + a, shape.ridge_z + b + rng.random() * 0.002) for a, b in profile], "yz", x, x + length - 0.006,
                  SHINGLE)
        x += 0.30


def _flashing(m, slope, wall_x):
    """Rufo de parede: aba na água do telhado e aba subindo a parede, ao longo da junção do telhado da garagem."""
    path = [tuple(slope.point(wall_x, d)) for d in np.linspace(0.0, slope.length, 8)]
    sign = 1.0
    profile = [(0.0, 0.0), (sign * 0.10, 0.0), (sign * 0.10, 0.012), (0.006, 0.012), (0.006, 0.13), (0.0, 0.13)]
    ext.sweep_profile(m, [(x + 0.0, y, z + 0.01) for x, y, z in path], profile, "metal", up=(0, 0, 1))


# --------------------------------------------------------------------------------------------
# Empenas
# --------------------------------------------------------------------------------------------
def _gable(m, shape, x, thickness):
    """Triângulo de empena em `x`; a ponta termina no forro do telhado."""
    half = thickness / 2
    base = shape.eave_z - GABLE_SINK
    apex = shape.ridge_z - DECK_THICKNESS
    y0, y1 = shape.wall_y0 - half, shape.wall_y1 + half
    m.extrude([(y0, base), (y1, base), (shape.ridge_y, apex)], "yz", x - half, x + half, "wall_siding_ext")


def _gable_vent(m, shape, x, outward):
    """Veneziana da empena: moldura branca e ripas."""
    face = x + outward * layout.WALL_T_EXT / 2
    y, z = shape.ridge_y, shape.eave_z + (shape.ridge_z - shape.eave_z) * 0.42
    m.box(face + outward * 0.02, y, z - 0.22, 0.04, 0.70, 0.44, "trim_white")
    for i in range(6):
        m.box(face + outward * 0.045, y, z - 0.18 + i * 0.07, 0.02, 0.56, 0.032, "black")
        m.box(face + outward * 0.052, y, z - 0.164 + i * 0.07, 0.012, 0.56, 0.006, "trim_white")


def build(ctx):
    ext.start(ctx)
    rng = ext.rng_for(ctx, "roof")
    main, garage = main_shape(), garage_shape()
    blocked = chimney.roof_cutout()

    decks = ext.builder("Roof_Main", ext.PROFILED)
    for slope in main.slopes():
        _deck(decks, slope)
        _fascia(decks, slope)
        _rafter_tails(decks, slope)
    front, back = main.slopes()
    for deck_x, outward in ((main.deck_x0, -1), (main.deck_x1, 1)):
        _rake(decks, front, deck_x, outward)
        _rake(decks, back, deck_x, outward)
    ext.emit(ctx, decks)

    garage_decks = ext.builder("Roof_Garage", ext.PROFILED)
    for slope in garage.slopes():
        _deck(garage_decks, slope)
        _fascia(garage_decks, slope)
        _rafter_tails(garage_decks, slope)
        _rake(garage_decks, slope, garage.deck_x1, 1)
    ext.emit(ctx, garage_decks)

    tiles = ext.builder("Roof_Shingles", ext.PROFILED)
    for slope in (*main.slopes(), *garage.slopes()):
        shingle_slope(tiles, rng, slope, blocked if slope.x0 < 0 else ())
    _ridge_cap(tiles, rng, main, main.deck_x0, main.deck_x1)
    _ridge_cap(tiles, rng, garage, garage.deck_x0, garage.deck_x1)
    for slope in garage.slopes():
        _flashing(tiles, slope, main.x1 + layout.WALL_T_EXT / 2)
    ext.emit(ctx, tiles)

    walls = ext.builder("Roof_Gables", ext.PROFILED)
    for x in (main.x0, main.x1):
        _gable(walls, main, x, layout.WALL_T_EXT)
    _gable_vent(walls, main, main.x0, -1)
    _gable_vent(walls, main, main.x1, 1)
    _gable(walls, garage, garage.x1, layout.WALL_T_EXT)
    ext.emit(ctx, walls)

    chimney.build(ctx)
    chimney.build_antenna(ctx, main.ridge_z)
    chimney.build_vents(ctx, main)
    drainage.build(ctx, main, garage)
    ctx.log("telhados: lajes, telhas individuais, cumeeira, rufo, empenas, calhas e chaminé")
