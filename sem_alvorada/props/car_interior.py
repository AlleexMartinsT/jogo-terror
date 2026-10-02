"""Interior do carro: painel curvo com instrumentos, volante, bancos de veludo com gomos, painéis de porta,
console, banco traseiro com a cadeirinha da Emma, teto com retrovisor e o coelhinho pendurado.

O vão da cabine vem da chapa (`carro_carroceria.npz`): piso em z = 0,34, paredes internas em |x| = 0,82, painel de
fogo em y = 0,96 e porta-pacotes em y = -1,50. Tudo aqui se apoia nessas medidas.
"""
import math

import numpy as np

from .. import craft
from . import car_shape as shape
from . import parts
from .kit import MeshBuilder

VELOUR, TRIM, DASH, PLASTIC, RUBBER, CHROME = "car_velour", "car_door_trim", "car_dash_plastic", "car_black_plastic", \
    "car_rubber", "car_chrome"
WHEEL_HUB = (-0.45, 0.13, 0.90)
SEAT_TILT = 12.0


def interior_builder():
    m = MeshBuilder("Car_Interior")
    m.finish = craft.Finish(bevel=0.0, smooth_angle=72.0)
    return m


# --------------------------------------------------------------------------------------------
# Painel
# --------------------------------------------------------------------------------------------
def _smooth_closed(points, passes=2):
    """Chaikin em polilinha fechada: arredonda os cantos do perfil do painel."""
    pts = np.asarray(points, float)
    for _ in range(passes):
        nxt = np.roll(pts, -1, axis=0)
        pts = np.stack([0.75 * pts + 0.25 * nxt, 0.25 * pts + 0.75 * nxt], axis=1).reshape(-1, 2)
    return pts


def _dash_bumps(x):
    """Quanto o painel avança para trás em x: viseira do quadro de instrumentos (motorista) e nicho do rádio (centro)."""
    visor = math.exp(-(((x + 0.45) / 0.22) ** 4))
    glove = math.exp(-(((x - 0.45) / 0.30) ** 4))
    stack = math.exp(-((x / 0.15) ** 4))
    return visor, glove, stack


def _dash_profile(x):
    visor, glove, stack = _dash_bumps(x)
    face = 0.43 - 0.045 * visor + 0.03 * glove + 0.045 * stack
    top = 0.945 + 0.045 * visor
    lip = face + 0.02
    return [(0.955, 0.992), (0.72, 0.978), (0.54, top), (lip, top - 0.035), (face, 0.82), (face - 0.005, 0.66),
            (face + 0.07, 0.50), (face + 0.18, 0.40), (0.955, 0.36)]


def dashboard(m):
    """Painel de instrumentos: casca extrudada ao longo de X com viseira, nicho de rádio e porta-luvas."""
    xs = np.linspace(-0.80, 0.80, 33)
    rings = []
    for x in xs:
        profile = _smooth_closed(_dash_profile(float(x)), passes=2)
        rings.append([(x, y, z) for y, z in profile])
    m.loft(rings, DASH, True, True, True)
    with m.at(-0.45, 0.396, 0.78, rx=-32):
        m.panel(0, 0, 0, 0.33, 0.15, "car_cluster", "back")
        m.panel(0, -0.003, 0, 0.35, 0.17, "car_glass_clear", "back")
    with m.at(0.0, 0.405, 0.775, rx=-8):
        m.panel(0, 0, 0.0, 0.215, 0.105, "car_radio", "back")
        m.panel(0.0, 0.0, 0.078, 0.095, 0.034, "digits_dash", "back")
        for x in (-0.07, 0.0, 0.07):
            m.cylinder(x, -0.005, -0.12, 0.016, 0.02, CHROME, seg=10)
    for x in (-0.12, 0.12):
        for z in (0.915, 0.93):
            m.box(x, 0.58, z, 0.14, 0.02, 0.006, PLASTIC)
    m.box(0.48, 0.41, 0.585, 0.46, 0.01, 0.20, TRIM)
    m.box(0.48, 0.405, 0.67, 0.04, 0.012, 0.02, CHROME)


def steering_wheel(m):
    """Volante de três raios, com aro envolto e botão de buzina; coluna, alavanca de seta e a fechadura da ignição."""
    hub = WHEEL_HUB
    with m.at(*hub, rx=65):
        m.torus(0, 0, 0, 0.19, 0.0165, PLASTIC, seg=28, seg_minor=8)
        m.soft_box(0, 0, -0.025, 0.115, 0.115, 0.05, PLASTIC, radius=0.03, edge=0.012, corner_points=4)
        for angle in (90, 210, 330):
            end = (0.178 * math.cos(math.radians(angle)), 0.178 * math.sin(math.radians(angle)), 0)
            m.bar((0, 0, 0), end, 0.024, PLASTIC)
        m.cylinder(0, 0, 0.026, 0.034, 0.003, "car_rim", seg=14)
        m.torus(0, 0, 0.0285, 0.028, 0.0025, "car_rim", seg=14, seg_minor=4)
    m.tube((hub[0], hub[1] + 0.02, hub[2] - 0.03), (hub[0], 0.43, 0.70), 0.034, PLASTIC, seg=10)
    m.soft_box(hub[0], 0.31, 0.62, 0.14, 0.12, 0.10, PLASTIC, radius=0.03, edge=0.012)
    m.tube((hub[0] - 0.03, hub[1] + 0.07, hub[2] - 0.07), (hub[0] - 0.14, hub[1] + 0.02, hub[2] - 0.05), 0.0075, PLASTIC, seg=6)
    m.cylinder(hub[0] + 0.07, hub[1] + 0.09, hub[2] - 0.08, 0.012, 0.025, CHROME, seg=8)


def pedals(m):
    for x, width, height in ((-0.50, 0.095, 0.15), (-0.37, 0.07, 0.17)):
        with m.at(x, 0.43, 0.46, rx=-28):
            m.box(0, 0, -height / 2, width, 0.025, height, RUBBER)
            for k in range(4):
                m.box(0, -0.014, -height / 2 + 0.025 + k * height / 4.5, width * 0.9, 0.006, 0.007, PLASTIC)
        m.tube((x, 0.45, 0.50), (x, 0.55, 0.62), 0.008, PLASTIC, seg=5)


# --------------------------------------------------------------------------------------------
# Bancos
# --------------------------------------------------------------------------------------------
def _pleated(m, x, y, z0, width, depth, height, count, mat, gap=0.006, radius=0.035, edge=0.025):
    """Almofada em gomos (costuras entre as tiras) como nos veludos dos anos 90."""
    strip = (width - gap * (count - 1)) / count
    for k in range(count):
        cx = x - width / 2 + strip / 2 + k * (strip + gap)
        m.soft_box(cx, y, z0, strip, depth, height, mat, radius=radius, edge=edge, corner_points=3)


def front_seat(m, x, y=-0.75):
    """Banco dianteiro: assento e encosto em gomos, laterais altas, encosto de cabeça e trilhos."""
    _pleated(m, x, y, 0.37, 0.50, 0.50, 0.12, 3, VELOUR)
    for side in (-1, 1):
        m.soft_box(x + side * 0.285, y, 0.37, 0.075, 0.50, 0.19, VELOUR, radius=0.03, edge=0.022, corner_points=3)
    with m.at(x, y - 0.28, 0.47, rx=SEAT_TILT):
        _pleated(m, 0, 0, 0, 0.46, 0.115, 0.56, 3, VELOUR, radius=0.04)
        for side in (-1, 1):
            m.soft_box(side * 0.27, 0.0, 0.0, 0.085, 0.14, 0.58, VELOUR, radius=0.035, edge=0.022, corner_points=3)
        m.soft_box(0, -0.005, 0.57, 0.22, 0.095, 0.15, VELOUR, radius=0.04, edge=0.025, corner_points=3)
        for post in (-0.06, 0.06):
            m.tube((post, 0, 0.50), (post, 0, 0.60), 0.006, CHROME, seg=6)
    for side in (-0.19, 0.19):
        m.box(x + side, y, 0.30, 0.04, 0.46, 0.07, PLASTIC)
    m.box(x, y + 0.2, 0.32, 0.5, 0.05, 0.05, PLASTIC)


def console(m):
    """Console entre os bancos: tampa acolchoada, porta-copos e a alavanca do câmbio automático."""
    m.soft_box(0.0, -0.66, 0.34, 0.25, 0.60, 0.22, TRIM, radius=0.04, edge=0.02, corner_points=3)
    m.soft_box(0.0, -0.80, 0.56, 0.23, 0.34, 0.045, VELOUR, radius=0.03, edge=0.015, corner_points=3)
    for y in (-0.52, -0.40):
        m.cylinder(0.0, y, 0.555, 0.034, 0.012, PLASTIC, seg=12, r_top=0.04)
    m.tube((0.0, -0.46, 0.57), (0.0, -0.53, 0.70), 0.009, CHROME, seg=6)
    m.soft_box(0.0, -0.545, 0.69, 0.04, 0.05, 0.05, PLASTIC, radius=0.015, edge=0.01)


def rear_seat(m):
    """Banco traseiro corrido em gomos, com porta-pacotes e alto-falantes atrás do encosto."""
    _pleated(m, 0.0, -1.23, 0.38, 1.45, 0.56, 0.14, 5, VELOUR, radius=0.045)
    with m.at(0.0, -1.50, 0.50, rx=9):
        _pleated(m, 0, 0, 0, 1.45, 0.12, 0.50, 5, VELOUR, radius=0.045)
    m.box(0.0, -1.55, 0.985, 1.50, 0.18, 0.025, TRIM)
    for x in (-0.38, 0.38):
        m.cylinder(x, -1.55, 1.008, 0.085, 0.006, PLASTIC, seg=16)
        m.cylinder(x, -1.55, 1.012, 0.05, 0.004, CHROME, seg=12)


def child_seat(m, x=0.32, y=-1.20):
    """Cadeirinha rosa da Emma, presa no banco traseiro: casca, almofada, arnês e fivela."""
    pink = "plush_pink"
    m.soft_box(x, y, 0.52, 0.40, 0.42, 0.11, pink, radius=0.05, edge=0.03, corner_points=3)
    with m.at(x, y - 0.20, 0.55, rx=10):
        m.soft_box(0, 0, 0, 0.40, 0.09, 0.52, pink, radius=0.05, edge=0.03, corner_points=3)
        for side in (-1, 1):
            m.soft_box(side * 0.205, 0.04, 0.12, 0.05, 0.14, 0.40, pink, radius=0.02, edge=0.012)
        m.soft_box(0, 0.052, 0.04, 0.30, 0.03, 0.44, "plush_white", radius=0.03, edge=0.006, corner_points=3)
        for side in (-0.07, 0.07):
            m.bar((side, 0.066, 0.46), (side * 0.9, 0.07, 0.15), 0.028, "coat_dark")
    m.box(x, y + 0.01, 0.635, 0.05, 0.03, 0.012, CHROME)


# --------------------------------------------------------------------------------------------
# Portas e teto
# --------------------------------------------------------------------------------------------
def door_details(m):
    """Apoio de braço, puxador, botões, alto-falante, trava e bolso em cada uma das quatro portas."""
    for side in (-1, 1):
        wall = side * 0.80
        for index, (front, rear) in enumerate((shape.FRONT_DOOR, shape.REAR_DOOR)):
            centre, length = (front + rear) / 2, abs(front - rear)
            m.box(wall, centre, 0.36, 0.024, length - 0.10, 0.17, "car_carpet")
            m.soft_box(side * 0.775, centre - 0.06, 0.74, 0.08, length * 0.52, 0.055, TRIM, radius=0.02, edge=0.012)
            m.tube((wall, centre + length * 0.2, 0.86), (wall, centre - length * 0.1, 0.86), 0.011, CHROME, seg=6)
            with m.at(side * 0.79, centre + length * 0.30, 0.54, ry=90 * side):
                m.cylinder(0, 0, 0, 0.075, 0.012, PLASTIC, seg=18)
                m.cylinder(0, 0, 0.012, 0.045, 0.004, CHROME, seg=14)
            m.cylinder(side * 0.80, centre - length * 0.40, 0.99, 0.0065, 0.04, CHROME, seg=6)
            m.box(wall, centre, 0.47, 0.03, length * 0.36, 0.09, PLASTIC)
            if index == 0 and side < 0:
                m.box(side * 0.775, centre + 0.12, 0.80, 0.05, 0.12, 0.012, PLASTIC)
                for k in range(4):
                    m.box(side * 0.775, centre + 0.08 + 0.03 * k, 0.808, 0.02, 0.018, 0.008, CHROME)
            else:
                m.cylinder(side * 0.78, centre - length * 0.28, 0.84, 0.014, 0.026, CHROME, seg=8)


def headliner_details(m):
    """Luz de cortesia, quebra-sóis, retrovisor interno e o coelhinho pendurado nele."""
    m.cylinder(0.0, -0.50, 1.356, 0.07, 0.01, "car_lens_clear", seg=16)
    m.cylinder(0.0, -0.50, 1.364, 0.075, 0.004, CHROME, seg=16)
    for x in (-0.36, 0.36):
        m.soft_box(x, 0.19, 1.336, 0.34, 0.19, 0.018, "car_headliner", radius=0.02, edge=0.007)
    mirror_y = 0.325
    m.tube((0.0, mirror_y + 0.01, 1.33), (0.0, mirror_y - 0.045, 1.275), 0.007, PLASTIC, seg=6)
    m.soft_box(0.0, mirror_y - 0.05, 1.215, 0.25, 0.03, 0.075, PLASTIC, radius=0.012, edge=0.008)
    m.panel(0.0, mirror_y - 0.0655, 1.2525, 0.225, 0.052, "mirror_plain", "back")
    m.tube((0.08, mirror_y - 0.06, 1.225), (0.08, mirror_y - 0.06, 1.095), 0.0025, "paper_white", seg=3)
    with m.at(0.08, mirror_y - 0.06, 1.01, rx=-4, rz=170):
        parts.rabbit(m, 0, 0, 0, 0.42)


def small_things(m):
    """Coisas que ficaram no carro: óculos escuros no painel, fita cassete, copo vazio, tênis da Emma, livro e giz de cera."""
    m.box(0.62, 0.78, 0.985, 0.13, 0.05, 0.012, "steel_dark")
    m.box(0.55, 0.78, 0.987, 0.05, 0.04, 0.008, "steel_dark")
    m.box(0.20, -0.72, 0.605, 0.11, 0.075, 0.016, "veneer_dark")
    m.cylinder(0.0, -0.40, 0.567, 0.030, 0.085, "paper_white", seg=10, r_top=0.036)
    with m.at(0.27, -0.55, 0.34, rz=25):
        m.soft_box(0, 0, 0, 0.085, 0.20, 0.07, "painted_pink", radius=0.03, edge=0.015)
        m.soft_box(0, -0.06, 0.05, 0.075, 0.09, 0.07, "painted_pink", radius=0.03, edge=0.015)
    with m.at(-0.30, -1.20, 0.52, rz=-14):
        m.box(0, 0, 0, 0.22, 0.28, 0.012, "note_crayon")
        for k in range(3):
            m.tube((0.12 + 0.012 * k, -0.04 + 0.02 * k, 0.02), (0.20 + 0.012 * k, 0.04 + 0.02 * k, 0.02), 0.004,
                   ("toy_red", "toy_blue", "toy_yellow")[k], seg=5)


def floor_mats(m):
    for x in (-0.45, 0.45):
        m.soft_box(x, 0.12, 0.343, 0.50, 0.42, 0.012, RUBBER, radius=0.04, edge=0.004)
    m.soft_box(-0.45, -0.60, 0.343, 0.46, 0.32, 0.01, RUBBER, radius=0.04, edge=0.004)


def seat_belts(m):
    for side in (-1, 1):
        m.bar((side * 0.78, -0.27, 1.15), (side * 0.78, -0.25, 0.80), 0.045, "coat_dark")
        m.box(side * 0.78, -0.26, 0.78, 0.07, 0.03, 0.05, PLASTIC)


def build_interior():
    m = interior_builder()
    dashboard(m)
    steering_wheel(m)
    pedals(m)
    for x in (-0.45, 0.45):
        front_seat(m, x)
    console(m)
    rear_seat(m)
    child_seat(m)
    door_details(m)
    headliner_details(m)
    small_things(m)
    floor_mats(m)
    seat_belts(m)
    return m
