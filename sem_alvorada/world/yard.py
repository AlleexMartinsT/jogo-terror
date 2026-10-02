"""Quintal e frente: caixa de correio em poste, lixeiras (uma tombada), canteiros de plantas secas, arbustos mortos,
condensador do ar-condicionado, mangueira enrolada e as coisas da Emma largadas no gramado.
"""
import math

import numpy as np

from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401
from . import trees

GROUND_Z = -0.12
WALL = layout.WALL_T_EXT / 2


# --------------------------------------------------------------------------------------------
# Caixa de correio
# --------------------------------------------------------------------------------------------
def mailbox(m, rng, x, y):
    """Caixa de correio em poste de madeira inclinado: corpo em arco, porta aberta com cartas saindo, bandeira erguida."""
    with m.at(x, y, GROUND_Z, rx=-2.0, ry=3.0):
        m.box(0, 0, 0, 0.095, 0.095, 1.08, "wood_dark")
        m.bar((0.0, 0.0, 0.95), (0.0, -0.20, 1.07), 0.05, "wood_dark")
    with m.at(x, y - 0.12, GROUND_Z + 1.10, rz=-3):
        arch = [(-0.095 * math.cos(math.pi * k / 10), 0.095 + 0.105 * math.sin(math.pi * k / 10)) for k in range(11)]
        m.extrude([(-0.105, 0.0), (0.105, 0.0)] + [(a, b) for a, b in reversed(arch)], "xz", -0.27, 0.27, "ext_mailbox")
        m.extrude([(-0.105, -0.01), (0.105, -0.01), (0.105, 0.0), (-0.105, 0.0)], "xz", -0.28, 0.28, "ext_mailbox")
        with m.at(0, -0.27, 0.0, rx=-64):                               # porta aberta, pendurada para baixo
            m.extrude([(-0.1, 0.0), (0.1, 0.0)] + [(0.1 * math.cos(math.pi * k / 8), 0.19 * math.sin(math.pi * k / 8)) for k in range(9)],
                      "xz", -0.006, 0.006, "ext_mailbox")
        for dx, dz, angle in ((-0.03, 0.04, 8), (0.02, 0.05, -12), (0.05, 0.03, 30)):          # cartas
            with m.at(dx, -0.30, dz, rz=angle, rx=-8):
                m.box(0, 0, 0, 0.16, 0.012, 0.09, "paper_white")
        m.box(0.12, 0.05, 0.04, 0.012, 0.012, 0.18, "iron_black")
        m.box(0.125, 0.05, 0.19, 0.012, 0.075, 0.05, "ext_hydrant")                             # bandeira levantada
        m.panel(0.0, 0.11, 0.12, 0.085, 0.03, "ext_plaque", "back")
    m.box(x + 0.16, y - 0.05, GROUND_Z + 0.42, 0.09, 0.3, 0.07, "toy_blue")                    # jornal em tubo azul esquecido no chão


# --------------------------------------------------------------------------------------------
# Lixeiras
# --------------------------------------------------------------------------------------------
def bin_standing(m, x, y, yaw, mat, lid_open=22.0):
    """Lixeira de rodas: corpo afunilado, alça traseira, rodas, tampa articulada entreaberta."""
    with m.at(x, y, GROUND_Z, rz=yaw):
        m.frustum(0, 0, 0.06, 0.50, 0.60, 0.58, 0.72, 0.92, mat)
        m.box(0, 0.30, 0.90, 0.56, 0.04, 0.05, mat)
        m.tube((-0.28, 0.40, 0.55), (0.28, 0.40, 0.55), 0.012, "iron_black", seg=6)
        m.tube((-0.26, 0.38, 0.06), (0.26, 0.38, 0.06), 0.012, "iron_black", seg=6)
        for sx in (-0.26, 0.26):
            with m.at(sx, 0.40, 0.09, ry=90):
                m.cylinder(0, 0, -0.02, 0.085, 0.04, "rubber", seg=12)
        with m.at(0, 0.36, 0.99, rx=lid_open):
            m.soft_box(0, -0.36, 0.0, 0.62, 0.74, 0.045, mat, radius=0.04, edge=0.012)


def bin_fallen(m, rng, x, y):
    """Lixeira tombada com o lixo espalhado: sacos, latas, garrafas e uma caixa de pizza."""
    with m.at(x, y, GROUND_Z + 0.36, rz=-48, rx=84):
        m.frustum(0, 0, 0, 0.50, 0.60, 0.58, 0.72, 0.92, "ext_bin_gray")
        m.tube((-0.28, 0.40, 0.35), (0.28, 0.40, 0.35), 0.012, "iron_black", seg=6)
    with m.at(x + 0.55, y + 0.30, GROUND_Z, rz=-48):
        with m.at(0.1, 0.0, 0.0, rz=-30, rx=-90):
            m.soft_box(0, 0, 0, 0.74, 0.62, 0.045, "ext_bin_gray", radius=0.04, edge=0.012)
    for _ in range(4):
        px, py = x + rng.uniform(0.3, 1.6), y + rng.uniform(-0.6, 0.9)
        m.sphere(px, py, GROUND_Z + 0.14, 0.2, "black", seg=8, rings=5, squash=0.7)
        m.tube((px - 0.05, py, GROUND_Z + 0.31), (px + 0.05, py + 0.04, GROUND_Z + 0.34), 0.02, "black", seg=5)
    for k in range(5):
        px, py = x + rng.uniform(0.4, 2.0), y + rng.uniform(-0.8, 1.0)
        with m.at(px, py, GROUND_Z + 0.032, rz=rng.uniform(0, 360), ry=90):
            m.cylinder(0, 0, -0.06, 0.032, 0.12, "steel_hardware", seg=8)
    with m.at(x + 1.1, y - 0.5, GROUND_Z + 0.004, rz=35):
        m.box(0, 0, 0, 0.36, 0.36, 0.035, "cardboard")


# --------------------------------------------------------------------------------------------
# Canteiros e arbustos
# --------------------------------------------------------------------------------------------
def dead_stem(m, rng, x, y, height, lean):
    """Haste seca de flor com uma cabeça de sementes."""
    top = (x + math.cos(lean) * height * 0.18, y + math.sin(lean) * height * 0.18, GROUND_Z + height)
    path = [(x, y, GROUND_Z + 0.02), (x + (top[0] - x) * 0.4, y + (top[1] - y) * 0.4, GROUND_Z + height * 0.5), top]
    ext.sweep_circle(m, path, 0.0045, "wood_dark", sides=3, radii=[0.0055, 0.0042, 0.003], caps=False)
    m.cylinder(top[0], top[1], top[2] - 0.01, 0.014, 0.03, "wood_dark", seg=5, r_top=0.004)


def hosta(m, rng, x, y):
    """Roseta de folhas de hosta secas e caídas: cada folha é uma pá achatada e dobrada."""
    for k in range(9):
        a = k * 2 * math.pi / 9 + rng.uniform(-0.2, 0.2)
        length = rng.uniform(0.22, 0.34)
        pts = []
        for t in (0.0, 0.5, 1.0):
            r = 0.04 + length * t
            pts.append((x + r * math.cos(a), y + r * math.sin(a), GROUND_Z + 0.03 + 0.12 * math.sin(t * math.pi * 0.8) - 0.1 * t * t))
        left = [(px + 0.05 * math.sin(a) * (0.4 + w), py - 0.05 * math.cos(a) * (0.4 + w), pz) for (px, py, pz), w in zip(pts, (0.0, 0.5, 0.1))]
        right = [(px - 0.05 * math.sin(a) * (0.4 + w), py + 0.05 * math.cos(a) * (0.4 + w), pz) for (px, py, pz), w in zip(pts, (0.0, 0.5, 0.1))]
        m.quad(left[0], left[1], right[1], right[0], "ext_grass", uv=[(0.3, 0), (0.3, 0.5), (0.3, 0.5), (0.3, 0)])
        m.quad(left[1], left[2], right[2], right[1], "ext_grass", uv=[(0.3, 0.5), (0.3, 1.0), (0.3, 1.0), (0.3, 0.5)])


def flower_bed(m, rng, x0, x1, y0, y1):
    """Canteiro com cobertura de lascas, pedras na borda, hastes secas, hostas e um rosal morto."""
    m.box((x0 + x1) / 2, (y0 + y1) / 2, GROUND_Z, x1 - x0, y1 - y0, 0.045, "bark")
    for side_y in (y0, y1):
        x = x0
        while x < x1:
            length = rng.uniform(0.22, 0.34)
            m.box(x + length / 2, side_y, GROUND_Z, length - 0.02, 0.17, 0.10, "concrete")
            x += length
    for _ in range(int((x1 - x0) * 3.5)):
        dead_stem(m, rng, rng.uniform(x0 + 0.1, x1 - 0.1), rng.uniform(y0 + 0.15, y1 - 0.15), rng.uniform(0.28, 0.62), rng.uniform(0, 6.28))
    for _ in range(max(2, int((x1 - x0) * 0.8))):
        hosta(m, rng, rng.uniform(x0 + 0.3, x1 - 0.3), rng.uniform(y0 + 0.2, y1 - 0.2))
    trees.dead_shrub(m, rng, (x0 + x1) / 2 + rng.uniform(-0.5, 0.5), (y0 + y1) / 2, 0.6, "wood_dark")


# --------------------------------------------------------------------------------------------
# Fundos da casa
# --------------------------------------------------------------------------------------------
def condenser(m, x, y):
    """Condensador do ar-condicionado: gabinete de aço com aletas, grade do ventilador, linhas de gás isoladas."""
    m.box(x, y, GROUND_Z, 0.95, 0.95, 0.08, "concrete")
    m.box(x, y, GROUND_Z + 0.08, 0.76, 0.76, 0.78, "painted_metal")
    for side in (-1, 1):
        for k in range(13):
            m.box(x + side * 0.382, y, GROUND_Z + 0.13 + k * 0.054, 0.012, 0.66, 0.02, "steel_hardware")
            m.box(x, y + side * 0.382, GROUND_Z + 0.13 + k * 0.054, 0.66, 0.012, 0.02, "steel_hardware")
    top = GROUND_Z + 0.86
    m.cylinder(x, y, top, 0.37, 0.018, "painted_metal", seg=24)
    for radius in (0.12, 0.22, 0.32):
        m.torus(x, y, top + 0.012, radius, 0.0055, "iron_black", seg=24, seg_minor=4)
    for k in range(10):
        a = k * math.pi / 5
        m.bar((x, y, top + 0.012), (x + 0.34 * math.cos(a), y + 0.34 * math.sin(a), top + 0.012), 0.008, "iron_black")
    m.cylinder(x, y, top + 0.02, 0.04, 0.03, "iron_black", seg=10)
    pipe = [(x + 0.2, y - 0.38, GROUND_Z + 0.3), (x + 0.2, y - 0.6, GROUND_Z + 0.25), (x + 0.2, y - 0.8, GROUND_Z + 0.8), (x + 0.2, 10.0 + WALL + 0.04, 0.75)]
    ext.sweep_circle(m, pipe, 0.022, "rubber", sides=6)
    ext.sweep_circle(m, [(px + 0.06, py, pz) for px, py, pz in pipe], 0.011, "brass_worn", sides=5)


def hose_and_bib(m, x, wall_y):
    """Torneira de jardim na face de fora da parede norte e a mangueira enrolada no chão em espiral achatada."""
    face = wall_y + WALL
    m.box(x, face + 0.03, 0.55, 0.07, 0.04, 0.07, "brass_worn")
    m.tube((x, face + 0.04, 0.55), (x + 0.07, face + 0.12, 0.54), 0.012, "brass_worn", seg=6)
    coils = []
    for k in range(70):
        t = k / 69
        r = 0.34 - 0.23 * t
        coils.append((x + 0.55 + r * math.cos(t * 6 * math.pi), face + 0.95 + r * math.sin(t * 6 * math.pi), GROUND_Z + 0.022 + 0.018 * t))
    ext.sweep_circle(m, coils, 0.0125, "ext_bin_green", sides=6, caps=True)
    ext.sweep_circle(m, [coils[-1], (x + 0.3, face + 0.6, GROUND_Z + 0.03), (x + 0.12, face + 0.1, 0.5)], 0.0125, "ext_bin_green", sides=6)


def electric_meter(m, x, y):
    """Caixa do medidor de luz na parede da garagem e o eletroduto que sobe até o ramal."""
    m.box(x, y - 0.04, 1.35, 0.30, 0.08, 0.40, "painted_metal")
    m.cylinder(x, y - 0.11, 1.45, 0.095, 0.06, "glass_dark", seg=16)
    m.cylinder(x, y - 0.13, 1.45, 0.085, 0.005, "paper_white", seg=16)
    m.tube((x + 0.08, y - 0.04, 1.55), (x + 0.08, y - 0.04, 3.4), 0.018, "steel_hardware", seg=8)


def build(ctx):
    ext.start(ctx)
    rng = ext.rng_for(ctx, "yard")
    m = ext.builder("Yard", ext.FINE)
    mailbox(m, rng, 12.4, -4.7)
    bin_standing(m, 19.2, -0.95, 8, "ext_bin_green")
    bin_standing(m, 20.1, -1.05, -4, "ext_bin_gray", lid_open=0.0)
    bin_fallen(m, rng, 19.4, -3.4)
    flower_bed(m, rng, 0.7, 5.2, -1.15, -0.30)
    flower_bed(m, rng, 8.1, 11.7, -1.15, -0.30)
    for x in (-0.6, 0.4, 11.9, 12.2):
        trees.dead_shrub(m, rng, x, -0.55, 0.9, "wood_dark")
    condenser(m, 4.3, 10.9)
    hose_and_bib(m, 9.3, 10.0)
    electric_meter(m, 17.9, -WALL)
    ext.emit(ctx, m)
