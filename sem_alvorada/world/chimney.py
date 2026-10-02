"""Chaminé de tijolos individuais na empena oeste, antena de TV, ventilações do telhado.

Cada tijolo é uma peça com recorte de textura sorteado (`ext_brick`); entre eles aparece o miolo de argamassa
(`ext_mortar`). A chaminé sai do chão, alarga na base (a fornalha), estreita num ombro, sobe ao lado do
telhado e termina em coroa de concreto com duas manilhas e uma tampa de chuva enferrujada.
"""
import numpy as np

from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401

BRICK_LENGTH, BRICK_HEIGHT, BRICK_DEPTH, JOINT = 0.215, 0.065, 0.100, 0.010
COURSE = BRICK_HEIGHT + JOINT
WALL_FACE = -layout.WALL_T_EXT / 2          # face externa da parede oeste
SHAFT = {"depth": 0.62, "y0": 4.35, "y1": 5.65}
BASE = {"depth": 0.86, "y0": 4.10, "y1": 5.90}
BASE_TOP, SHOULDER_TOP, SHAFT_TOP, FOOT = 1.25, 1.70, 8.30, -0.45
UV_WINDOW = 0.30


def roof_cutout():
    """Retângulo (x0, y0, x1, y1) onde o telhado não leva telhas: a chaminé e a folga do rufo."""
    return [(-0.86, SHAFT["y0"] - 0.14, 0.0, SHAFT["y1"] + 0.14)]


def _brick(m, rng, x0, y0, z0, x1, y1, z1, faces):
    """Tijolo como caixa sem fundo; `faces` lista quais lados existem ('-x', '+x', '-y', '+y', 'top')."""
    u0, v0 = rng.random() * (1 - UV_WINDOW), rng.random() * (1 - UV_WINDOW)
    uv = [(u0, v0), (u0 + UV_WINDOW, v0), (u0 + UV_WINDOW, v0 + UV_WINDOW), (u0, v0 + UV_WINDOW)]
    quads = {
        "-x": ((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)),
        "+x": ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)),
        "-y": ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
        "+y": ((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)),
        "top": ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
    }
    for name in faces:
        m.quad(*quads[name], "ext_brick", uv=uv)


def _run(rng, length, offset):
    """Cortes de uma fiada: lista de (início, fim) de tijolos ao longo de `length`, com meia-vez no começo."""
    cursor, pieces = -offset, []
    while cursor < length - 0.01:
        end = cursor + BRICK_LENGTH * rng.uniform(0.98, 1.02)
        pieces.append((max(cursor, 0.0), min(end, length)))
        cursor = end + JOINT
    return [(a, b) for a, b in pieces if b - a > 0.04]


def _course(m, rng, z0, box, course_index, inset=0.0):
    """Uma fiada em volta da chaminé (3 faces visíveis; a quarta encosta na parede)."""
    depth, y0, y1 = box["depth"] - inset, box["y0"] + inset, box["y1"] - inset
    x_out = WALL_FACE - depth
    z1 = z0 + BRICK_HEIGHT
    stagger = BRICK_LENGTH / 2 if course_index % 2 else 0.0
    for a, b in _run(rng, y1 - y0, stagger):                 # face oeste, a mais visível
        _brick(m, rng, x_out, y0 + a, z0, x_out + BRICK_DEPTH, y0 + b, z1, ("-x", "top", "-y", "+y"))
    for side, y_face in ((-1, y0), (1, y1)):                 # faces sul e norte, entre os cantos
        for a, b in _run(rng, depth - BRICK_DEPTH - JOINT, BRICK_LENGTH / 2 - stagger * 0.3):
            lo, hi = x_out + BRICK_DEPTH + JOINT + a, x_out + BRICK_DEPTH + JOINT + b
            if side < 0:
                _brick(m, rng, lo, y_face, z0, hi, y_face + BRICK_DEPTH, z1, ("-y", "top", "-x", "+x"))
            else:
                _brick(m, rng, lo, y_face - BRICK_DEPTH, z0, hi, y_face, z1, ("+y", "top", "-x", "+x"))


def _core(m, box, z0, z1, inset=0.012):
    """Miolo de argamassa um pouco menor que a chaminé: aparece nas juntas entre os tijolos."""
    x0, x1 = WALL_FACE - box["depth"] + inset, WALL_FACE + 0.01
    y0, y1 = box["y0"] + inset, box["y1"] - inset
    m.box((x0 + x1) / 2, (y0 + y1) / 2, z0, x1 - x0, y1 - y0, z1 - z0, "ext_mortar")


def _stack(m, rng, box, z_from, z_to, inset=0.0):
    z, index = z_from, 0
    while z < z_to - 0.02:
        _course(m, rng, z, box, index, inset)
        z += COURSE
        index += 1
    return z


def _corbel(m, rng, z, index):
    """Duas fiadas que avançam para sustentar a coroa."""
    for step, grow in enumerate((0.03, 0.06)):
        box = {"depth": SHAFT["depth"] + grow, "y0": SHAFT["y0"] - grow, "y1": SHAFT["y1"] + grow}
        _core(m, box, z + step * COURSE, z + (step + 1) * COURSE)
        _course(m, rng, z + step * COURSE, box, index + step)
    return z + 2 * COURSE


def _crown(m, z):
    """Coroa de concreto, manilhas de barro e tampa de chuva enferrujada."""
    x0, x1 = WALL_FACE - SHAFT["depth"] - 0.08, WALL_FACE + 0.02
    y0, y1 = SHAFT["y0"] - 0.08, SHAFT["y1"] + 0.08
    m.box((x0 + x1) / 2, (y0 + y1) / 2, z, x1 - x0, y1 - y0, 0.10, "concrete")
    m.box((x0 + x1) / 2, (y0 + y1) / 2, z + 0.10, x1 - x0 - 0.06, y1 - y0 - 0.06, 0.03, "concrete")
    x = WALL_FACE - 0.30
    for k, y in enumerate((4.7, 5.3)):
        m.lathe([(0.115, 0.0), (0.11, 0.2), (0.125, 0.22), (0.125, 0.30), (0.112, 0.31), (0.108, 0.40)], x, y, z + 0.13, "ext_brick",
                seg=14, cap_bottom=True, cap_top=False)
    cap_z = z + 0.13 + 0.50
    m.lathe([(0.0, 0.0), (0.16, -0.03), (0.17, -0.06)], x, 5.3, cap_z, "iron_black", seg=14)
    for angle in range(0, 360, 90):
        a = np.radians(angle)
        m.bar((x + 0.10 * np.cos(a), 5.3 + 0.10 * np.sin(a), cap_z - 0.08), (x + 0.12 * np.cos(a), 5.3 + 0.12 * np.sin(a), cap_z - 0.02),
              0.012, "iron_black")


def build_chimney(ctx):
    rng = ext.rng_for(ctx, "chimney")
    m = ext.builder("Roof_Chimney", ext.PROFILED)
    _core(m, BASE, FOOT, BASE_TOP)
    _stack(m, rng, BASE, FOOT, BASE_TOP)
    shoulder_steps = int((SHOULDER_TOP - BASE_TOP) / COURSE)
    for step in range(shoulder_steps):                       # ombro: cada fiada recua um pouco até a largura do duto
        k = (step + 1) / (shoulder_steps + 1)
        box = {"depth": BASE["depth"] + (SHAFT["depth"] - BASE["depth"]) * k,
               "y0": BASE["y0"] + (SHAFT["y0"] - BASE["y0"]) * k, "y1": BASE["y1"] + (SHAFT["y1"] - BASE["y1"]) * k}
        z = BASE_TOP + step * COURSE
        _core(m, box, z, z + COURSE)
        _course(m, rng, z, box, step)
    z = _stack(m, rng, SHAFT, BASE_TOP + shoulder_steps * COURSE, SHAFT_TOP)
    _core(m, SHAFT, BASE_TOP, z)
    z = _corbel(m, rng, z, 3)
    _crown(m, z)
    ext.emit(ctx, m)


# --------------------------------------------------------------------------------------------
# Antena de TV e saídas de ventilação
# --------------------------------------------------------------------------------------------
def build_antenna(ctx, ridge_z):
    """Antena de TV de alumínio dos anos 80, torta, no espigão da empena leste."""
    m = ext.builder("Roof_Antenna", ext.FINE)
    base = np.array((10.6, 5.0, ridge_z + 0.03))
    for sy in (-0.35, 0.35):
        m.bar(tuple(base + (0.0, sy, -0.02)), tuple(base + (0.0, 0.0, 0.55)), 0.02, "metal")
    top = base + (0.18, 0.02, 3.1)
    m.tube(tuple(base + (0, 0, 0.5)), tuple(top), 0.014, "metal", seg=8)
    for boom_z, boom_len, count in ((2.55, 1.3, 7), (3.05, 0.8, 5)):
        center = base + (0.15 + 0.04 * (boom_z - 2.5), 0.0, boom_z)
        m.tube(tuple(center + (0.0, -boom_len / 2, 0.0)), tuple(center + (0.0, boom_len / 2, 0.0)), 0.009, "metal", seg=6)
        for k in range(count):
            y = -boom_len / 2 + boom_len * (k + 0.5) / count
            half = 0.42 * (1.0 - 0.45 * k / count) * (1.0 if k else 1.18)
            tilt = 0.06 if k == 3 else 0.0
            m.tube(tuple(center + (-half, y, tilt)), tuple(center + (half, y, -tilt)), 0.0055, "metal", seg=5)
    wire = [tuple(base + (0.1, 0.1, 0.3)), tuple(base + (0.1, 1.5, -0.4)), tuple(base + (0.1, 3.0, -1.2))]
    ext.sweep_circle(m, wire, 0.004, "black", sides=4)
    ext.emit(ctx, m)


def build_vents(ctx, main_shape):
    """Dois tubos de ventilação do esgoto na água de trás, com a bota de borracha e a tampa."""
    m = ext.builder("Roof_Vents", ext.FINE)
    for x, y in ((3.2, 6.9), (9.0, 7.7)):
        z = main_shape.top_z(y) + 0.01
        m.cylinder(x, y, z, 0.095, 0.05, "rubber", seg=12, r_top=0.045)
        m.cylinder(x, y, z + 0.04, 0.0375, 0.52, "plastic_white_aged", seg=10)
        m.cylinder(x, y, z + 0.56, 0.05, 0.03, "plastic_white_aged", seg=10, r_top=0.03)
    ext.emit(ctx, m)


def build(ctx):
    build_chimney(ctx)
