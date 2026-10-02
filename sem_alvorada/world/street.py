"""A rua em frente à casa: asfalto com rachaduras, remendos e buraco, meio-fio, calçadas em lajes com juntas,
a entrada de carros, bueiro, tampa de inspeção, hidrante, poste de luz morto e poste de telefone com fios.

Tudo vem de `layout` (ROAD, SIDEWALK, DRIVEWAY): a rua corre ao longo de X, ao sul da casa.
"""
import math

import numpy as np

from .. import conventions as C
from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401

ROAD_Z = -0.22
SIDEWALK_Z = -0.08
GROUND_Z = -0.12
CURB_WIDTH = 0.16
NEAR_CURB_Y = layout.ROAD.y1
FAR_CURB_Y = layout.ROAD.y0
SLAB_LENGTH = 1.5
POTHOLE = (19.6, -9.6, 0.42)         # x, y, raio


# --------------------------------------------------------------------------------------------
# Asfalto
# --------------------------------------------------------------------------------------------
def _flat(m, x0, y0, x1, y1, z, mat, scale=3.0):
    m.quad((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), mat, uv=[(x0 / scale, y0 / scale), (x1 / scale, y0 / scale),
                                                                       (x1 / scale, y1 / scale), (x0 / scale, y1 / scale)])


def _road_surface(m):
    """A pista inteira, menos o buraco: cinco retângulos em volta dele."""
    road = layout.ROAD
    px, py, pr = POTHOLE
    hole = (px - pr, py - pr, px + pr, py + pr)
    z = ROAD_Z
    _flat(m, road.x0, road.y0, road.x1, hole[1], z, "asphalt")
    _flat(m, road.x0, hole[3], road.x1, road.y1, z, "asphalt")
    _flat(m, road.x0, hole[1], hole[0], hole[3], z, "asphalt")
    _flat(m, hole[2], hole[1], road.x1, hole[3], z, "asphalt")


def _pothole(m, rng):
    """Buraco: borda irregular que desce em degraus até uma poça escura."""
    px, py, pr = POTHOLE
    count = 18
    angles = [2 * math.pi * i / count for i in range(count)]
    rim = [(px + pr * math.cos(a), py + pr * math.sin(a), ROAD_Z) for a in angles]
    mid = [(px + pr * 0.78 * (1 + 0.15 * (rng.random() - 0.5)) * math.cos(a), py + pr * 0.78 * math.sin(a), ROAD_Z - 0.035 - 0.015 * rng.random())
           for a in angles]
    floor = [(px + pr * 0.45 * math.cos(a), py + pr * 0.45 * math.sin(a), ROAD_Z - 0.075 - 0.01 * rng.random()) for a in angles]
    m.loft([rim, mid, floor], "asphalt", False, True, False)
    m.cylinder(px, py, ROAD_Z - 0.071, pr * 0.40, 0.003, "water_dark", seg=14)


def _crack(m, rng, start, heading, length, z, width=0.008):
    """Fissura: caminho tortuoso e fita fina de piche escuro em cima do asfalto."""
    x, y = start
    path, angle = [], heading
    for _ in range(max(3, int(length / 0.35))):
        path.append((x, y, z))
        angle += rng.uniform(-0.45, 0.45)
        x, y = x + 0.35 * math.cos(angle), y + 0.35 * math.sin(angle)
        if rng.random() < 0.10:                                         # ramificação curta
            bx, by, ba = x, y, angle + rng.choice((-1, 1)) * 0.8
            branch = []
            for _ in range(rng.randint(2, 5)):
                branch.append((bx, by, z))
                bx, by, ba = bx + 0.3 * math.cos(ba), by + 0.3 * math.sin(ba), ba + rng.uniform(-0.4, 0.4)
            if len(branch) > 2:
                ext.sweep_profile(m, branch, [(-width / 2, 0.0), (width / 2, 0.0), (width / 2, 0.002), (-width / 2, 0.002)], "black", caps=False)
    if len(path) > 2:
        w = width * rng.uniform(0.6, 1.8)
        ext.sweep_profile(m, path, [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, 0.002), (-w / 2, 0.002)], "black", caps=False)


def _patch(m, x0, y0, x1, y1, rng):
    """Remendo de asfalto: placa um pouco mais alta, de borda chanfrada, com piche de vedação em volta."""
    z = ROAD_Z + 0.007
    m.box((x0 + x1) / 2, (y0 + y1) / 2, ROAD_Z, x1 - x0, y1 - y0, 0.007, "asphalt")
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        ext.sweep_profile(m, [(ax, ay, z + 0.0005), (bx, by, z + 0.0005)], [(-0.012, 0.0), (0.012, 0.0), (0.012, 0.0015), (-0.012, 0.0015)],
                          "rubber", caps=False)
    for _ in range(3):
        _crack(m, rng, (x0 + (x1 - x0) * rng.random(), y0 + (y1 - y0) * rng.random()), rng.uniform(0, 6.28), rng.uniform(0.6, 1.4), z + 0.001, 0.005)


def _manhole(m, x, y):
    """Tampa de ferro com anéis em relevo e o aro de concreto em volta."""
    m.cylinder(x, y, ROAD_Z - 0.01, 0.40, 0.03, "concrete", seg=24)
    m.cylinder(x, y, ROAD_Z + 0.015, 0.33, 0.008, "iron_black", seg=24)
    for radius in (0.28, 0.20, 0.12):
        m.torus(x, y, ROAD_Z + 0.026, radius, 0.007, "iron_black", seg=24, seg_minor=5)
    for k in range(8):
        a = k * math.pi / 4
        m.bar((x + 0.04 * math.cos(a), y + 0.04 * math.sin(a), ROAD_Z + 0.024), (x + 0.30 * math.cos(a), y + 0.30 * math.sin(a), ROAD_Z + 0.024),
              0.012, "iron_black")


def _road_paint(m):
    road = layout.ROAD
    centre = (road.y0 + road.y1) / 2
    x = road.x0 + 2.0
    while x < road.x1 - 3.0:
        for dy in (-0.09, 0.09):
            _flat(m, x, centre + dy - 0.05, x + 3.0, centre + dy + 0.05, ROAD_Z + 0.004, "road_paint", scale=0.64)
        x += 9.0


def road(ctx):
    rng = ext.rng_for(ctx, "road")
    m = ext.builder("Street", ext.PROFILED)
    _road_surface(m)
    _pothole(m, rng)
    _road_paint(m)
    for _ in range(26):
        _crack(m, rng, (rng.uniform(-20, 45), rng.uniform(-14.2, -7.8)), rng.uniform(-0.3, 0.3) + rng.choice((0, math.pi)),
               rng.uniform(2.0, 9.0), ROAD_Z + 0.001)
    for _ in range(6):
        _crack(m, rng, (rng.uniform(-8, 35), rng.uniform(-13, -9)), rng.uniform(1.2, 1.9), rng.uniform(2.0, 4.0), ROAD_Z + 0.001, 0.012)
    for box in ((5.0, -9.4, 7.4, -8.6), (22.5, -13.2, 25.5, -12.2), (10.0, -12.4, 11.3, -11.8), (-9.0, -10.0, -6.6, -9.0), (30.0, -9.6, 31.5, -8.9)):
        _patch(m, *box, rng)
    _manhole(m, 8.0, -11.0)
    _manhole(m, 24.5, -10.4)
    ext.emit(ctx, m)


# --------------------------------------------------------------------------------------------
# Meio-fio, calçada, entrada de carros
# --------------------------------------------------------------------------------------------
def _slab(m, rng, x0, y0, x1, y1, z, mat="sidewalk", lift=0.006):
    """Laje de concreto com juntas de dilatação: cantos em alturas ligeiramente diferentes e bordas quebradas."""
    heights = [z + rng.uniform(-lift, lift) for _ in range(4)]
    corners = [(x0 + 0.004, y0 + 0.004, heights[0]), (x1 - 0.004, y0 + 0.004, heights[1]), (x1 - 0.004, y1 - 0.004, heights[2]),
               (x0 + 0.004, y1 - 0.004, heights[3])]
    scale = 1.5
    m.quad(*corners, mat, uv=[(c[0] / scale, c[1] / scale) for c in corners])
    base = [(cx, cy, -0.45) for cx, cy, _ in corners]
    for i in range(4):
        j = (i + 1) % 4
        m.quad(corners[i], corners[j], base[j], base[i], mat)


def _curb(m, rng, y_face, side, x0, x1):
    """Meio-fio: peças de 2 a 3 m com junta e um canto lascado de vez em quando."""
    x = x0
    while x < x1:
        length = rng.uniform(2.0, 3.0)
        end = min(x + length, x1)
        face_y, back_y = y_face, y_face + side * CURB_WIDTH
        r = 0.025
        profile = [(face_y, ROAD_Z - 0.04), (face_y, SIDEWALK_Z - r), (face_y + side * r * 0.3, SIDEWALK_Z - r * 0.2),
                   (face_y + side * r, SIDEWALK_Z), (back_y, SIDEWALK_Z), (back_y, ROAD_Z - 0.04)]
        m.extrude(profile, "yz", x, end - 0.006, "sidewalk")
        if rng.random() < 0.18:
            cx = x + rng.uniform(0.2, length - 0.2)
            m.box(cx, face_y + side * 0.04, SIDEWALK_Z - 0.03, rng.uniform(0.08, 0.18), 0.05, 0.04, "black")
        x = end


def _sidewalk(m, rng, y_curb, side, y_inner, x0, x1):
    y_a, y_b = sorted((y_curb + side * CURB_WIDTH, y_inner))
    x = x0
    while x < x1:
        end = min(x + SLAB_LENGTH, x1)
        _slab(m, rng, x, y_a, end, y_b, SIDEWALK_Z)
        if rng.random() < 0.35:                                         # rachadura de ponta a ponta
            xs = x + rng.uniform(0.3, SLAB_LENGTH - 0.3)
            path = [(xs, y_a + 0.05, SIDEWALK_Z + 0.001), (xs + rng.uniform(-0.15, 0.15), (y_a + y_b) / 2, SIDEWALK_Z + 0.001),
                    (xs + rng.uniform(-0.2, 0.2), y_b - 0.05, SIDEWALK_Z + 0.001)]
            ext.sweep_profile(m, path, [(-0.004, 0.0), (0.004, 0.0), (0.004, 0.0015), (-0.004, 0.0015)], "black", caps=False)
        x = end


def _driveway(m, rng):
    """Entrada de carros: lajes inclinadas do portão até a rua, atravessando a calçada rebaixada."""
    drive, walk = layout.DRIVEWAY, layout.SIDEWALK
    raised = SIDEWALK_Z + 0.02
    wall = -layout.WALL_T_EXT / 2
    knots = [(wall, 0.0), (walk.y1, raised), (walk.y0 + CURB_WIDTH, raised), (walk.y0 - 0.5, ROAD_Z + 0.012)]
    y = wall
    for (ya, za), (yb, zb) in zip(knots, knots[1:]):
        steps = max(1, int(abs(yb - ya) / 1.6))
        for k in range(steps):
            y0 = ya + (yb - ya) * k / steps
            y1 = ya + (yb - ya) * (k + 1) / steps
            z0 = za + (zb - za) * k / steps
            z1 = za + (zb - za) * (k + 1) / steps
            xa, xb = drive.x0, drive.x1
            corners = [(xa, y0, z0), (xb, y0, z0), (xb, y1, z1), (xa, y1, z1)]
            if y1 < y0:
                corners = [(xa, y1, z1), (xb, y1, z1), (xb, y0, z0), (xa, y0, z0)]
            m.quad(*corners, "sidewalk", uv=[(c[0] / 1.5, c[1] / 1.5) for c in corners])
    for yj in (-1.6, -3.4, -5.4):                                       # juntas
        m.box((drive.x0 + drive.x1) / 2, yj, SIDEWALK_Z * 0.3 + 0.0005, drive.x1 - drive.x0, 0.012, 0.002, "black")
    for side_x in (drive.x0, drive.x1):                                 # faixa de grama rente à laje: borda quebrada
        m.box(side_x, -3.8, -0.30, 0.1, 7.2, 0.28, "sidewalk")


def curbs_and_walks(ctx):
    rng = ext.rng_for(ctx, "walks")
    m = ext.builder("Sidewalks", ext.FINE)
    road_x0, road_x1 = layout.ROAD.x0, layout.ROAD.x1
    drive = layout.DRIVEWAY
    _curb(m, rng, NEAR_CURB_Y, 1.0, road_x0, drive.x0)
    _curb(m, rng, NEAR_CURB_Y, 1.0, drive.x1, road_x1)
    _curb(m, rng, FAR_CURB_Y, -1.0, road_x0, road_x1)
    inner_near = layout.SIDEWALK.y1
    _sidewalk(m, rng, NEAR_CURB_Y, 1.0, inner_near, road_x0, drive.x0)
    _sidewalk(m, rng, NEAR_CURB_Y, 1.0, inner_near, drive.x1, road_x1)
    _sidewalk(m, rng, FAR_CURB_Y, -1.0, FAR_CURB_Y - 2.0, road_x0, road_x1)
    _driveway(m, rng)
    ext.emit(ctx, m)


def build(ctx):
    ext.start(ctx)
    road(ctx)
    curbs_and_walks(ctx)
