"""Brinquedos e ferramentas largados no quintal: o triciclo da Emma, a bola murcha, o balanço quebrado, a piscina
de plástico seca, a tabela de basquete, o rastelo encostado e o desenho de giz na entrada de carros.
"""
import math

import numpy as np

from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401

GROUND_Z = -0.12
PINK, STEEL = "painted_pink", "ext_pole_metal"


def tricycle(m, x, y, yaw):
    """Triciclo rosa tombado de lado: roda grande na frente, duas pequenas atrás, guidão com fitas e banco."""
    with m.at(x, y, GROUND_Z + 0.075, rz=yaw, ry=76):
        for sx, radius, z in ((0.0, 0.14, 0.34), (-0.12, 0.07, -0.18), (0.12, 0.07, -0.18)):
            m.torus(sx, 0.0, z, radius, 0.014, "rubber", seg=16, seg_minor=5, rx=90)
            for k in range(6):
                a = k * math.pi / 3
                m.bar((sx, 0, z), (sx, radius * 0.92 * math.sin(a), z + radius * 0.92 * math.cos(a)), 0.006, "steel_hardware")
        m.tube((0.0, 0.0, 0.34), (0.0, 0.0, 0.0), 0.014, PINK, seg=8)
        m.tube((0.0, 0.0, 0.0), (0.0, 0.0, -0.18), 0.016, PINK, seg=8)
        m.tube((-0.12, 0.0, -0.18), (0.12, 0.0, -0.18), 0.012, "steel_hardware", seg=6)
        m.tube((0.0, 0.0, 0.34), (0.0, 0.0, 0.52), 0.013, "steel_hardware", seg=6)
        m.tube((-0.19, 0.0, 0.54), (0.19, 0.0, 0.54), 0.012, PINK, seg=6)
        for side in (-1, 1):
            m.tube((side * 0.19, 0.0, 0.54), (side * 0.20, 0.0, 0.40), 0.004, "toy_yellow", seg=4)
        m.soft_box(0.0, 0.0, -0.06, 0.15, 0.20, 0.035, "coat_dark", radius=0.04, edge=0.012)


def ball(m, x, y):
    m.sphere(x, y, GROUND_Z + 0.075, 0.115, "toy_red", seg=12, rings=8, squash=0.68)
    m.torus(x, y, GROUND_Z + 0.08, 0.10, 0.004, "toy_yellow", seg=16, seg_minor=4)


def swing_set(m, rng, x, y):
    """Balanço de A: duas cavaletes de tubo de aço, viga no topo e dois balanços; uma corrente arrebentou."""
    height, half_width, reach = 2.3, 1.55, 0.95
    top = GROUND_Z + height
    for side in (-1, 1):
        for lean in (-1, 1):
            m.tube((x + side * half_width, y + lean * reach, GROUND_Z), (x + side * half_width * 0.96, y, top), 0.036, STEEL, seg=8)
        m.cylinder(x + side * half_width, y + reach, GROUND_Z - 0.03, 0.08, 0.04, "concrete", seg=8)
        m.cylinder(x + side * half_width, y - reach, GROUND_Z - 0.03, 0.08, 0.04, "concrete", seg=8)
    m.tube((x - half_width * 1.05, y, top), (x + half_width * 1.05, y, top), 0.045, STEEL, seg=10)
    for k, sx in enumerate((-0.55, 0.55)):
        seat_z = GROUND_Z + 0.52
        for dx in (-0.17, 0.17):
            if k == 1 and dx > 0:
                ext.sweep_circle(m, [(x + sx + dx, y, top), (x + sx + dx + 0.05, y + 0.04, top - 0.55), (x + sx + dx + 0.12, y + 0.1, top - 0.95)], 0.006,
                                 "iron_black", sides=4)
                continue
            m.tube((x + sx + dx, y, top - 0.01), (x + sx + dx, y, seat_z + 0.02), 0.006, "iron_black", seg=4)
        if k == 0:
            m.soft_box(x + sx, y, seat_z, 0.45, 0.17, 0.035, "rubber", radius=0.04, edge=0.012)
        else:
            with m.at(x + sx + 0.2, y + 0.6, GROUND_Z + 0.02, rz=-25, rx=6):
                m.soft_box(0, 0, 0, 0.45, 0.17, 0.035, "rubber", radius=0.04, edge=0.012)


def kiddie_pool(m, rng, x, y):
    """Piscina de plástico seca, com folhas mortas e uma poça turva no fundo."""
    m.lathe([(0.78, 0.0), (0.80, 0.02), (0.82, 0.22), (0.78, 0.24), (0.74, 0.22), (0.72, 0.03)], x, y, GROUND_Z, "toy_blue", seg=22,
            cap_bottom=True, cap_top=False)
    m.cylinder(x, y, GROUND_Z + 0.028, 0.70, 0.004, "water_dark", seg=20)
    for _ in range(14):
        a, r = rng.uniform(0, 6.28), rng.uniform(0.0, 0.62)
        with m.at(x + r * math.cos(a), y + r * math.sin(a), GROUND_Z + 0.034, rz=rng.uniform(0, 360)):
            m.box(0, 0, 0, 0.08, 0.05, 0.004, "wood_dark")


def basketball_hoop(m, x, y):
    """Tabela de basquete numa haste de aço na beira da entrada, com aro torto e rede esfiapada."""
    m.tube((x, y, GROUND_Z), (x, y, GROUND_Z + 3.05), 0.055, STEEL, seg=10)
    m.bar((x, y, GROUND_Z + 2.95), (x + 0.65, y, GROUND_Z + 2.95), 0.05, STEEL)
    board = (x + 0.74, y)
    m.box(board[0], board[1], GROUND_Z + 2.88, 0.04, 1.2, 0.8, "paper_white")
    m.box(board[0] + 0.022, board[1], GROUND_Z + 3.0, 0.004, 0.55, 0.40, "ext_hydrant")
    with m.at(board[0] + 0.28, board[1], GROUND_Z + 2.97, ry=-6):
        m.torus(0, 0, 0, 0.23, 0.009, "ext_hydrant", seg=22, seg_minor=5)
        for k in range(14):
            a = k * 2 * math.pi / 14
            m.tube((0.23 * math.cos(a), 0.23 * math.sin(a), -0.01), (0.14 * math.cos(a + 0.4), 0.14 * math.sin(a + 0.4), -0.40), 0.0025,
                   "paper_white", seg=3)


def rake(m, x, y):
    """Rastelo encostado na parede da garagem, de cabeça para baixo."""
    m.tube((x, y - 0.18, GROUND_Z), (x, y - 0.04, GROUND_Z + 1.7), 0.014, "wood_dark", seg=6)
    m.box(x, y - 0.18, GROUND_Z + 0.02, 0.42, 0.04, 0.025, STEEL)
    for k in range(12):
        m.box(x - 0.19 + k * 0.035, y - 0.19, GROUND_Z, 0.004, 0.012, 0.06, STEEL)


def chalk(m, x, y, drive_z):
    """Desenho de giz da Emma colado no concreto da entrada."""
    w, h = 1.35, 2.0
    z = drive_z(y) + 0.003
    m.quad((x - w / 2, y - h / 2, z), (x + w / 2, y - h / 2, z), (x + w / 2, y + h / 2, z), (x - w / 2, y + h / 2, z), "ext_chalk",
           uv=[(0, 0), (1, 0), (1, 1), (0, 1)])


def build(ctx):
    ext.start(ctx)
    rng = ext.rng_for(ctx, "playthings")
    m = ext.builder("Playthings", ext.FINE)
    tricycle(m, 9.0, -3.1, 28)
    ball(m, 11.4, -2.4)
    swing_set(m, rng, 10.2, 13.2)
    kiddie_pool(m, rng, 1.8, 13.6)
    basketball_hoop(m, 12.55, -2.2)
    rake(m, 17.95, -layout.WALL_T_EXT / 2)
    ext.emit(ctx, m)

    decal = ext.builder("Driveway_Chalk", ext.PROFILED)
    raised, wall = -0.06, -layout.WALL_T_EXT / 2
    chalk(decal, 14.6, -2.6, lambda yy: (raised * (wall - yy) / (wall + 5.5)) if yy < wall else 0.0)
    ext.emit(ctx, decal)
