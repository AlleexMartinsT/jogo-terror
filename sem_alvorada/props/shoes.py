"""Calçados modelados: sapato social, sapatilha, tênis infantil e bota de chuva.

Cada sapato é uma sola recortada no formato do pé (extrusão) mais o cabedal, um `loft` de seções que
crescem do calcanhar ao peito do pé e afinam na biqueira. O pé aponta para +Y; `scale` converte o
adulto (1,0) em criança (0,62). A boca do sapato é uma mancha escura no topo, onde o pé entra.
"""
import math

from .kit import rounded_rect

# (y, meia largura, altura do cabedal acima da sola) do calcanhar à biqueira, para um pé de 0,29 m
OXFORD = ((-0.145, 0.029, 0.062), (-0.12, 0.035, 0.080), (-0.08, 0.038, 0.082), (-0.03, 0.040, 0.060), (0.02, 0.044, 0.058),
          (0.07, 0.046, 0.050), (0.115, 0.040, 0.038), (0.145, 0.024, 0.028))
FLAT = ((-0.145, 0.027, 0.032), (-0.12, 0.033, 0.036), (-0.06, 0.036, 0.030), (0.0, 0.040, 0.026), (0.07, 0.044, 0.024),
        (0.12, 0.038, 0.022), (0.145, 0.022, 0.018))
SNEAKER = ((-0.145, 0.030, 0.062), (-0.12, 0.036, 0.078), (-0.08, 0.040, 0.082), (-0.03, 0.042, 0.064), (0.02, 0.045, 0.062),
           (0.07, 0.047, 0.056), (0.115, 0.043, 0.046), (0.145, 0.028, 0.040))


def _outline(stations, sole_pad):
    """Contorno (x, y) da sola: a meia largura de cada estação mais uma folga, dos dois lados."""
    right = [(half + sole_pad, y) for y, half, _ in stations]
    left = [(-half - sole_pad, y) for y, half, _ in reversed(stations)]
    return right + left


def shoe(m, cx, cy, z0, scale, upper_mat, sole_mat="rubber", kind="oxford", yaw=0.0, mirror=1):
    """Um sapato apoiado em z0, com o calcanhar em (cx, cy); `mirror` = -1 desenha o pé esquerdo."""
    stations = {"oxford": OXFORD, "flat": FLAT, "sneaker": SNEAKER}[kind]
    sole_height = 0.020 if kind != "flat" else 0.008
    s = scale
    with m.at(cx, cy, z0, rz=yaw):
        outline = [(mirror * x * s, (y + 0.145) * s) for x, y in _outline(stations, 0.004)]
        if mirror < 0:
            outline.reverse()
        m.extrude(outline, "xy", 0.0, sole_height * s, sole_mat)
        if kind == "oxford":
            m.box(mirror * 0.0, 0.03 * s, 0.0, 0.07 * s, 0.05 * s, 0.032 * s, sole_mat)       # salto
        rings = []
        for y, half, top in stations:
            width, height = 2 * half * s, top * s
            section = rounded_rect(width, height, min(width, height) * 0.38, 4)
            spring = 0.010 * s * max(0.0, (y - 0.06) / 0.085)
            rings.append([(mirror * px, (y + 0.145) * s, sole_height * s + height / 2 + pz + spring) for px, pz in section])
        m.loft(rings, upper_mat, True, True, True)
        mouth_y = (-0.075 + 0.145) * s
        m.panel(0, mouth_y, (sole_height + 0.074) * s, 0.056 * s, 0.07 * s, "tv_black", "top")
        if kind in ("oxford", "sneaker"):
            for lace in range(4):
                y = (-0.025 + 0.026 * lace + 0.145) * s
                z_lace = (sole_height + 0.075 - 0.007 * lace) * s
                m.tube((-0.03 * s, y, z_lace), (0.03 * s, y, z_lace),
                       0.0016 * s, "paper_white" if kind == "sneaker" else "leather_black", seg=5)


def rain_boot(m, cx, cy, z0, scale, mat, yaw=0.0):
    """Bota de chuva de borracha: pé curto e cano que sobe com leve alargamento no topo."""
    s = scale
    with m.at(cx, cy, z0, rz=yaw):
        outline = [(x * s, (y + 0.145) * s) for x, y in _outline(FLAT, 0.004)]
        m.extrude(outline, "xy", 0.0, 0.016 * s, "rubber")
        foot = []
        for y, half, top in ((-0.145, 0.029, 0.07), (-0.10, 0.036, 0.085), (-0.03, 0.040, 0.075), (0.05, 0.044, 0.05),
                             (0.11, 0.038, 0.04), (0.145, 0.022, 0.032)):
            width, height = 2 * half * s, top * s
            section = rounded_rect(width, height, height * 0.38, 4)
            foot.append([(px, (y + 0.145) * s, 0.016 * s + height / 2 + pz) for px, pz in section])
        m.loft(foot, mat, True, True, True)
        shaft = []
        for z, rx, ry in ((0.06, 0.036, 0.034), (0.10, 0.034, 0.033), (0.17, 0.038, 0.036), (0.26, 0.044, 0.040),
                          (0.275, 0.046, 0.042)):
            shaft.append([(rx * s * math.cos(2 * math.pi * i / 16), (0.02 + ry * math.sin(2 * math.pi * i / 16)) * s, z * s)
                          for i in range(16)])
        m.loft(shaft, mat, False, False, True, orient=False)
        rim = [(0.043 * s * math.cos(2 * math.pi * i / 16), (0.02 + 0.039 * math.sin(2 * math.pi * i / 16)) * s, 0.2755 * s)
               for i in range(16)]
        m.poly(rim, "tv_black")
