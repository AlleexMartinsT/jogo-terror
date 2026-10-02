"""Mobiliário urbano: hidrante, poste de luz morto, poste de telefone com fios, placa e bueiro de meio-fio.

Os fios são curvas de catenária varridas por um tubo fino (`ext.sweep_circle`), entre os postes e do poste até o
beiral da casa; é a única coisa na rua que "conecta" as casas apagadas.
"""
import math

import numpy as np

from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401

SIDEWALK_Z = -0.08
GROUND_Z = -0.12
POLE_X = (-1.5, 33.0, -38.0, 68.0)
POLE_Y = -6.3


def hydrant(m, x, y):
    """Hidrante: base, corpo, tampas com correntinha e a tampa de cima, tudo de ferro pintado de vermelho desbotado."""
    z = SIDEWALK_Z
    m.lathe([(0.115, 0.0), (0.115, 0.05), (0.085, 0.07), (0.080, 0.46), (0.098, 0.48), (0.098, 0.52), (0.070, 0.56),
             (0.060, 0.60), (0.0, 0.63)], x, y, z, "ext_hydrant", seg=16, smooth=True)
    m.cylinder(x, y, z + 0.55, 0.012, 0.09, "ext_hydrant", seg=8)
    for angle in (90, 270):
        with m.at(x, y, z + 0.34, rz=angle):
            m.tube((0.0, 0.0, 0.0), (0.11, 0.0, 0.0), 0.046, "ext_hydrant", seg=12)
            m.cylinder(0.12, 0, -0.05, 0.05, 0.10, "ext_hydrant", seg=12)
            m.cylinder(0.12, 0, 0.05, 0.034, 0.025, "iron_black", seg=10)
    with m.at(x, y, z + 0.30, rz=0):
        m.tube((0, 0, 0), (0, -0.12, 0), 0.055, "ext_hydrant", seg=12)
        m.cylinder(0, -0.13, -0.06, 0.062, 0.12, "ext_hydrant", seg=12)
    chain = ext.catenary((x + 0.06, y + 0.08, z + 0.40), (x + 0.15, y + 0.10, z + 0.33), 0.04, 6)
    ext.sweep_circle(m, chain, 0.004, "iron_black", sides=4)


def street_light(m, x, y, arm_toward=1.0):
    """Poste de luz de rua morto: base chumbada, haste afunilada, braço curvo e a luminária 'cabeça de cobra' sem lâmpada."""
    z0 = SIDEWALK_Z
    m.cylinder(x, y, z0, 0.19, 0.12, "iron_black", seg=12, r_top=0.14)
    m.lathe([(0.115, 0.0), (0.105, 1.0), (0.085, 3.5), (0.070, 6.8)], x, y, z0 + 0.12, "ext_pole_metal", seg=12, smooth=True)
    arm = [(x, y, z0 + 6.85), (x, y + arm_toward * 0.35, z0 + 7.30), (x, y + arm_toward * 1.15, z0 + 7.52), (x, y + arm_toward * 2.15, z0 + 7.45)]
    ext.sweep_circle(m, ext_smooth(arm), 0.045, "ext_pole_metal", sides=8)
    head = (x, y + arm_toward * 2.15, z0 + 7.38)
    m.soft_box(head[0], head[1], head[2] - 0.10, 0.28, 0.80, 0.16, "ext_pole_metal", radius=0.12, edge=0.05, corner_points=3)
    m.box(head[0], head[1] + arm_toward * 0.06, head[2] - 0.12, 0.18, 0.60, 0.02, "glass_dark")
    m.cylinder(head[0], head[1] - arm_toward * 0.15, head[2] + 0.06, 0.04, 0.06, "black", seg=8)
    m.box(x + 0.10, y, z0 + 1.2, 0.01, 0.18, 0.30, "ext_pole_metal")           # portinhola de manutenção


def ext_smooth(points, passes=2):
    pts = np.asarray(points, float)
    for _ in range(passes):
        mid = (pts[:-1] + pts[1:]) / 2
        out = np.empty((len(pts) + len(mid), 3))
        out[0::2], out[1::2] = pts, mid
        pts = out
    return [tuple(p) for p in pts]


def telephone_pole(m, x, y, crossarms=(8.0, 7.2), tilt=0.0):
    """Poste de madeira: fuste torto, duas travessas com isoladores de vidro, transformador cinza e estai com âncora."""
    base = GROUND_Z
    top = base + 9.0
    ext.sweep_circle(m, [(x + tilt * t, y, base + 9.0 * t) for t in np.linspace(0, 1, 5)], 0.14, "wood_dark", sides=7,
                     radii=[0.17 - 0.05 * t for t in np.linspace(0, 1, 5)])
    for height in crossarms:
        z = base + height
        px = x + tilt * height / 9.0
        m.box(px, y, z - 0.05, 0.12, 2.1, 0.14, "wood_dark")
        for dy in (-0.85, -0.35, 0.35, 0.85):
            m.cylinder(px, y + dy, z + 0.09, 0.025, 0.07, "ext_bin_gray", seg=6, r_top=0.045)
            m.cylinder(px, y + dy, z + 0.16, 0.045, 0.07, "ext_bin_gray", seg=6, r_top=0.02)
        m.bar((px, y - 0.55, z - 0.12), (px, y - 0.10, z - 0.52), 0.05, "wood_dark", caps=(False, False))
        m.bar((px, y + 0.55, z - 0.12), (px, y + 0.10, z - 0.52), 0.05, "wood_dark", caps=(False, False))
    m.cylinder(x + 0.30, y, base + 6.4, 0.22, 0.62, "ext_bin_gray", seg=14, r_top=0.20)
    m.cylinder(x + 0.30, y, base + 7.0, 0.22, 0.04, "ext_bin_gray", seg=14, r_top=0.12)
    m.box(x + 0.16, y, base + 6.2, 0.10, 0.28, 0.9, "wood_dark")
    for k in range(3):                                                  # degraus de escalada
        m.bar((x + 0.18, y - 0.10, base + 2.4 + 0.7 * k), (x + 0.28, y - 0.10, base + 2.4 + 0.7 * k), 0.018, "iron_black")
    anchor = (x + 2.2, y + 0.4, base)
    ext.sweep_circle(m, [(x + 0.1, y, base + 6.0), (x + 1.2, y + 0.2, base + 3.0), anchor], 0.006, "iron_black", sides=4)
    m.bar((anchor[0], anchor[1], base - 0.1), (anchor[0] + 0.1, anchor[1], base + 0.3), 0.04, "iron_black")


def wires(m, rng):
    """Fios entre os postes (três na travessa de cima, dois na de baixo) e o ramal que desce até a casa."""
    pairs = list(zip(sorted(POLE_X), sorted(POLE_X)[1:]))
    for x0, x1 in pairs:
        if x1 - x0 > 80:
            continue
        for height, offsets in ((8.0, (-0.85, -0.35, 0.35, 0.85)), (7.2, (-0.55, 0.55))):
            for dy in offsets:
                p0 = (x0, POLE_Y + dy, GROUND_Z + height + 0.20)
                p1 = (x1, POLE_Y + dy, GROUND_Z + height + 0.20)
                ext.sweep_circle(m, ext.catenary(p0, p1, 0.55 + 0.25 * rng.random(), 8), 0.007, "black", sides=3)
    drop_from = (-1.5, POLE_Y + 0.35, GROUND_Z + 7.4)
    eave = (3.4, -0.62, 5.0)
    ext.sweep_circle(m, ext.catenary(drop_from, eave, 0.9, 12), 0.011, "black", sides=5)
    ext.sweep_circle(m, ext.catenary((3.4, -0.62, 5.0), (3.4, -0.2, 4.2), 0.05, 4), 0.014, "black", sides=5)


def road_sign(m, x, y):
    """Placa de 'Criança brincando' num poste de aço: losango amarelo desbotado, torto."""
    z0 = GROUND_Z
    m.tube((x, y, z0), (x, y, z0 + 2.4), 0.025, "ext_pole_metal", seg=8)
    with m.at(x, y - 0.03, z0 + 1.95, rz=8, rx=-2):
        m.panel(0, 0, 0, 0.62, 0.62, "ext_sign", "front")
        m.panel(0, 0.004, 0, 0.62, 0.62, "ext_pole_metal", "back")
        m.box(0, 0.002, 0, 0.012, 0.01, 0.70, "ext_pole_metal")


def build(ctx):
    ext.start(ctx)
    rng = ext.rng_for(ctx, "utilities")
    m = ext.builder("StreetFurniture", ext.PROFILED)
    hydrant(m, 20.8, -5.9)
    street_light(m, 10.5, -5.0, arm_toward=-1.0)
    street_light(m, 31.0, -6.2, arm_toward=-1.0)
    street_light(m, -14.0, -6.2, arm_toward=-1.0)
    street_light(m, 14.0, -16.0, arm_toward=1.0)
    for x, tilt in zip(POLE_X, (0.0, 0.18, -0.12, 0.05)):
        telephone_pole(m, x, POLE_Y, tilt=tilt)
    wires(m, rng)
    road_sign(m, 1.0, -5.7)
    ext.emit(ctx, m)
