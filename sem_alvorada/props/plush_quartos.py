"""Bichos de pelúcia e brinquedos modelados do quarto da Emma, montados com elipsoides sobrepostos.

Cada pelúcia é feita de elipsoides lisos (sem chanfro, sem subdivisão: a malha já é redonda) que se atravessam;
as costuras ficam escondidas na sobreposição e o pelo sai do material `up_fur_*`. Olhos de plástico preto e
focinho ficam por cima. As funções desenham no builder em andamento, com a origem na base do bicho sentado.
"""
import math

from .assembly_quartos import segments


def ellipsoid(m, cx, cy, cz, rx, ry, rz, mat, *, seg=14, rings=9, turn=(0.0, 0.0, 0.0)):
    """Elipsoide de semieixos rx, ry, rz centrado em (cx, cy, cz); `turn` = (rx, ry, rz) em graus gira a peça."""
    with m.at(cx, cy, cz, rx=turn[0], ry=turn[1], rz=turn[2]):
        seg = segments(seg)
        rows = [[(0.0, 0.0, -rz)]]
        for row in range(1, rings):
            phi = math.pi * row / rings
            ring = [(rx * math.sin(phi) * math.cos(2 * math.pi * k / seg), ry * math.sin(phi) * math.sin(2 * math.pi * k / seg),
                     -rz * math.cos(phi)) for k in range(seg)]
            rows.append(ring)
        rows.append([(0.0, 0.0, rz)])
        m.loft(rows, mat, False, False, True, uv_grid=True)


def eyes(m, cx, cy, cz, spread, radius, forward=1.0):
    for side in (-1, 1):
        ellipsoid(m, cx + side * spread, cy + forward * radius * 0.2, cz, radius, radius, radius, "up_rubber", seg=8, rings=5)


def rabbit(m, cx, cy, z0, scale=1.0, fur="up_fur_white", inner="up_fur_pink", yaw=0.0):
    """Coelho de pelúcia sentado: corpo, cabeça, orelhas altas com forro rosa, braços, patas, rabo de pompom."""
    s = scale
    with m.at(cx, cy, z0, rz=yaw):
        ellipsoid(m, 0, 0, 0.085 * s, 0.078 * s, 0.070 * s, 0.092 * s, fur)
        ellipsoid(m, 0, 0.012 * s, 0.20 * s, 0.062 * s, 0.056 * s, 0.056 * s, fur)
        for side in (-1, 1):
            ellipsoid(m, side * 0.030 * s, -0.006 * s, 0.30 * s, 0.017 * s, 0.011 * s, 0.085 * s, fur, turn=(0, side * 9, 0),
                      seg=10, rings=7)
            ellipsoid(m, side * 0.030 * s, 0.003 * s, 0.30 * s, 0.009 * s, 0.006 * s, 0.07 * s, inner, turn=(0, side * 9, 0),
                      seg=8, rings=6)
            ellipsoid(m, side * 0.080 * s, 0.026 * s, 0.115 * s, 0.020 * s, 0.022 * s, 0.050 * s, fur, turn=(-14, side * -10, 0),
                      seg=10, rings=6)
            ellipsoid(m, side * 0.046 * s, 0.075 * s, 0.026 * s, 0.026 * s, 0.050 * s, 0.026 * s, fur, seg=10, rings=6)
        ellipsoid(m, 0, -0.072 * s, 0.045 * s, 0.032 * s, 0.032 * s, 0.032 * s, "up_fur_white", seg=10, rings=6)
        ellipsoid(m, 0, 0.066 * s, 0.195 * s, 0.012 * s, 0.009 * s, 0.009 * s, "up_fur_pink", seg=8, rings=5)
        eyes(m, 0, 0.056 * s, 0.215 * s, 0.027 * s, 0.0075 * s)


def teddy(m, cx, cy, z0, scale=1.0, fur="up_fur_brown", yaw=0.0):
    """Urso de pelúcia sentado: corpo gordo, cabeça, orelhas redondas, focinho claro, braços e patas abertas."""
    s = scale
    with m.at(cx, cy, z0, rz=yaw):
        ellipsoid(m, 0, 0, 0.100 * s, 0.092 * s, 0.082 * s, 0.105 * s, fur)
        ellipsoid(m, 0, 0.004 * s, 0.093 * s, 0.056 * s, 0.020 * s, 0.070 * s, "up_fur_yellow", seg=10, rings=6)
        ellipsoid(m, 0, 0.010 * s, 0.245 * s, 0.075 * s, 0.068 * s, 0.066 * s, fur)
        ellipsoid(m, 0, 0.062 * s, 0.230 * s, 0.032 * s, 0.026 * s, 0.024 * s, "up_fur_yellow", seg=10, rings=6)
        ellipsoid(m, 0, 0.086 * s, 0.238 * s, 0.011 * s, 0.008 * s, 0.008 * s, "up_rubber", seg=8, rings=5)
        for side in (-1, 1):
            ellipsoid(m, side * 0.058 * s, -0.004 * s, 0.296 * s, 0.025 * s, 0.018 * s, 0.025 * s, fur, seg=10, rings=6)
            ellipsoid(m, side * 0.108 * s, 0.020 * s, 0.135 * s, 0.028 * s, 0.030 * s, 0.062 * s, fur, turn=(-18, side * -22, 0),
                      seg=10, rings=6)
            ellipsoid(m, side * 0.062 * s, 0.078 * s, 0.030 * s, 0.034 * s, 0.056 * s, 0.032 * s, fur, seg=10, rings=6)
            ellipsoid(m, side * 0.062 * s, 0.108 * s, 0.030 * s, 0.022 * s, 0.020 * s, 0.020 * s, "up_fur_yellow", seg=8, rings=5)
        eyes(m, 0, 0.058 * s, 0.258 * s, 0.030 * s, 0.0085 * s)


def doll(m, cx, cy, z0, scale=1.0, dress="up_cloth_blue", yaw=0.0):
    """Boneca de pano: vestido em sino, cabeça de pano, cabelo de lã, braços abertos e botões no lugar dos olhos."""
    s = scale
    with m.at(cx, cy, z0, rz=yaw):
        m.lathe([(0.0, 0.0), (0.062 * s, 0.0), (0.07 * s, 0.02 * s), (0.045 * s, 0.10 * s), (0.026 * s, 0.17 * s),
                 (0.022 * s, 0.185 * s), (0.0, 0.19 * s)], 0, 0, 0.02 * s, dress, seg=segments(16), smooth=True)
        ellipsoid(m, 0, 0, 0.255 * s, 0.040 * s, 0.038 * s, 0.045 * s, "up_cloth_beige", seg=12, rings=8)
        ellipsoid(m, 0, -0.008 * s, 0.272 * s, 0.045 * s, 0.040 * s, 0.040 * s, "up_fur_yellow", seg=12, rings=7)
        for side in (-1, 1):
            m.tube((side * 0.03 * s, 0, 0.19 * s), (side * 0.11 * s, 0.02 * s, 0.14 * s), 0.011 * s, "up_cloth_beige", seg=8,
                   smooth=True)
            m.tube((side * 0.032 * s, -0.01 * s, 0.26 * s), (side * 0.06 * s, -0.06 * s, 0.14 * s), 0.008 * s, "up_fur_yellow",
                   seg=6, smooth=True)
            ellipsoid(m, side * 0.017 * s, 0.036 * s, 0.258 * s, 0.006 * s, 0.003 * s, 0.006 * s, "up_rubber", seg=6, rings=4)
        ellipsoid(m, 0, 0.038 * s, 0.245 * s, 0.006 * s, 0.003 * s, 0.003 * s, "up_fur_pink", seg=6, rings=4)


def toy_truck(m, cx, cy, z0, yaw=0.0):
    """Caminhãozinho de lata: cabine vermelha, caçamba azul, quatro rodas de borracha com calota amarela."""
    with m.at(cx, cy, z0, rz=yaw):
        m.soft_box(0, 0.075, 0.03, 0.09, 0.09, 0.07, "up_paint_red", radius=0.012, edge=0.006)
        m.soft_box(0, -0.05, 0.03, 0.09, 0.17, 0.045, "up_paint_blue", radius=0.008, edge=0.005)
        m.box(0, 0.115, 0.075, 0.07, 0.004, 0.02, "up_glass")
        for sx in (-0.05, 0.05):
            for wy in (-0.08, 0.075):
                with m.at(sx, wy, 0.022, ry=90):
                    m.cylinder(0, 0, -0.01, 0.022, 0.02, "up_rubber", seg=segments(14))
                    m.cylinder(0, 0, 0.009 if sx > 0 else -0.011, 0.012, 0.002, "up_paint_yellow", seg=segments(10))
