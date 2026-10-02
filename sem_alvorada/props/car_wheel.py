"""Roda do carro: pneu com banda de rodagem sulcada e flanco com letras, aro de aço e calota.

O eixo é o X local e a origem, o centro da roda (o runtime gira o objeto em torno de X). Medidas de um
205/70R15: raio externo 0,33 m, aro de 15 polegadas (raio 0,19 m), largura 0,22 m.
"""
import math

from .. import craft
from .kit import MeshBuilder, circle_points

TIRE_RADIUS = 0.33
RIM_RADIUS = 0.19
HALF_WIDTH = 0.11
GROOVE_DEPTH = 0.0075
SEGMENTS = {"low": 32, "medium": 48, "high": 64}

# Flanco, do talão (aro) ao ombro: (raio, deslocamento lateral). O lado externo é o espelho do interno.
SIDEWALL = [(0.196, 0.097), (0.212, 0.108), (0.240, 0.115), (0.272, 0.114), (0.302, 0.106), (0.322, 0.092),
            (0.329, 0.080)]
SHOULDER = SIDEWALL[-1][1]


def _tread_profile():
    """Banda de rodagem de ombro a ombro: coroa levemente abaulada com três sulcos circunferenciais."""
    grooves = (-0.044, 0.0, 0.044)
    steps = 21
    profile = []
    for index in range(steps):
        lateral = -SHOULDER + 2 * SHOULDER * index / (steps - 1)
        radius = TIRE_RADIUS - 0.004 * (lateral / SHOULDER) ** 4
        for centre in grooves:
            reach = abs(lateral - centre)
            if reach < 0.0085:
                radius -= GROOVE_DEPTH * (1.0 - reach / 0.0085)
        profile.append((radius, lateral))
    return profile


def _revolve(m, profile, mat, segments, **options):
    """Gira o perfil [(raio, lateral), ...] em torno do eixo X (o lathe do kit gira em torno de Z)."""
    with m.at(0, 0, 0, ry=90):
        m.lathe(profile, 0, 0, 0, mat, seg=segments, smooth=True, **options)


def _tire(m, segments):
    inboard = [(r, -w) for r, w in SIDEWALL]
    outboard = [(r, w) for r, w in reversed(SIDEWALL)]
    with m.at(0, 0, 0, ry=90):
        for side in (inboard, outboard):
            m.loft([circle_points(0, 0, w, r, segments) for r, w in side], "car_tire", False, False, True,
                   uv_grid=True, orient=False)
    _revolve(m, _tread_profile(), "car_tire_tread", segments, cap_bottom=False, cap_top=False)


def _rim_and_cover(m, segments):
    """Aro de aço (lábio e fundo), disco central e calota estampada na face externa, afundada como um prato."""
    _revolve(m, [(0.180, -0.098), (0.199, -0.096), (0.199, -0.060), (0.180, -0.052), (0.180, 0.060), (0.199, 0.074),
                 (0.201, 0.098), (0.186, 0.100)], "car_rim", segments, cap_bottom=False, cap_top=False)
    _revolve(m, [(0.0, 0.050), (0.180, 0.050), (0.184, 0.058)], "car_rim", segments, cap_bottom=False, cap_top=False)
    _revolve(m, [(0.0, 0.097), (0.040, 0.094), (0.050, 0.080), (0.080, 0.070), (0.125, 0.074), (0.160, 0.086),
                 (0.186, 0.098), (0.192, 0.101)], "car_chrome", segments, cap_bottom=False, cap_top=False)
    with m.at(0, 0, 0, ry=90):
        for index in range(12):
            angle = math.radians(index * 30 + 15)
            m.bar((0.070 * math.cos(angle), 0.070 * math.sin(angle), 0.072), (0.168 * math.cos(angle), 0.168 * math.sin(angle), 0.092),
                  0.011, "car_black_plastic")
        for index in range(5):
            angle = math.radians(index * 72)
            m.cylinder(0.060 * math.cos(angle), 0.060 * math.sin(angle), 0.074, 0.0085, 0.012, "car_chrome", seg=6)
        m.cylinder(0, 0, 0.092, 0.030, 0.012, "car_chrome", seg=12)


def build_wheel_mesh(name, quality="medium"):
    """Malha do pneu + aro + calota, com a origem no centro da roda."""
    m = MeshBuilder(name)
    m.finish = craft.Finish(bevel=0.0015, bevel_segments=1, bevel_angle=40.0, smooth_angle=50.0)
    segments = SEGMENTS.get(quality, SEGMENTS["medium"])
    _tire(m, segments)
    _rim_and_cover(m, segments)
    return m
