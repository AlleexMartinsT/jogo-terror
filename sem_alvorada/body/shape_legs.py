"""Calça jeans e cinto de couro: quadril com cós, braguilha, passantes e fivela; pernas com vincos de joelho e barra gasta.

A calça é um casco de quadril mais dois tubos de perna que se sobrepõem a ele (a emenda fica escondida pelo
vinco da virilha). Perna direita construída e espelhada; a esquerda usa a outra metade do atlas do jeans.
"""
import math

import numpy as np

from . import meshkit as K
from . import skeleton as S
from . import tex

DENIM, DENIM_HIP, LEATHER, METAL = "denim", "denim_hip", "leather", "metal"
HIP_SIDES = 40
LEG_SIDES = 26
NEUTRAL = (0.0, 0.0, 0.02, 0.02)          # canto do atlas para peças pequenas

HIP_TABLE = ((0.992, 0.1565, 0.1050, 0.004), (0.985, 0.1570, 0.1055, 0.004), (0.965, 0.1620, 0.1085, 0.003),
             (0.940, 0.1660, 0.1100, 0.002), (0.905, 0.1680, 0.1120, 0.000), (0.865, 0.1660, 0.1110, 0.000),
             (0.830, 0.1610, 0.1080, 0.000), (0.800, 0.1480, 0.1010, 0.000))
HIP_Z = (0.992, 0.985, 0.968, 0.948, 0.925, 0.900, 0.870, 0.840, 0.815, 0.800)
_HRX = K.interp([r[0] for r in reversed(HIP_TABLE)], [r[1] for r in reversed(HIP_TABLE)])
_HRY = K.interp([r[0] for r in reversed(HIP_TABLE)], [r[2] for r in reversed(HIP_TABLE)])
_HCY = K.interp([r[0] for r in reversed(HIP_TABLE)], [r[3] for r in reversed(HIP_TABLE)])
SUPER_N = 2.5


def hip_front_y(z):
    return float(_HCY(z) + _HRY(z))


def _hip_weights(z):
    t = K.ramp(0.935 - z, 0.0, 0.14)

    def per_vertex(thetas):
        out = []
        for theta in thetas:
            right = float(K.smoothstep(math.cos(theta) * 0.15, -0.045, 0.045))
            w = {"Hips": 1.0 - t}
            if t > 0:
                w["Thigh.R"] = t * right
                w["Thigh.L"] = t * (1.0 - right)
            out.append(K.normalize(w))
        return out
    return per_vertex


def _hip_features(z, noise_phase):
    def radial(thetas):
        rx, ry = float(_HRX(z)), float(_HRY(z))
        e = 2.0 / SUPER_N
        c, s = np.cos(thetas), np.sin(thetas)
        x, y = rx * np.sign(c) * np.abs(c) ** e, ry * np.sign(s) * np.abs(s) ** e
        rho = np.maximum(np.hypot(x, y), 0.05)
        front = np.sin(thetas) > 0
        delta = np.zeros_like(thetas)
        band = K.smoothstep(z, 0.943, 0.950)                   # cós: faixa de 4,5 cm um pouco mais grossa
        delta += 0.0030 * band * K.smoothstep(0.9965 - z, 0.0, 0.004)
        delta += 0.0016 * np.exp(-((z - 0.9475) / 0.0018) ** 2)         # pesponto/borda inferior do cós
        zipper = (1.0 - K.smoothstep(np.abs(x), 0.0035, 0.0065)) * front * K.smoothstep(0.945 - z, 0.0, 0.006) \
            * (1.0 - K.smoothstep(0.832 - z, 0.0, 0.010))
        delta += 0.0018 * zipper
        flap = (1.0 - K.smoothstep(np.abs(x - 0.012), 0.0, 0.004)) * front * K.smoothstep(0.945 - z, 0.0, 0.006) \
            * (1.0 - K.smoothstep(0.850 - z, 0.0, 0.010))
        delta += 0.0010 * flap
        # bolsos de trás: leve relevo retangular
        for side in (-1, 1):
            across = 1.0 - K.smoothstep(np.abs(x - 0.062 * side), 0.045, 0.050)
            delta += 0.0012 * across * (np.sin(thetas) < -0.3) * K.smoothstep(z, 0.862, 0.868) * (1.0 - K.smoothstep(z, 0.935, 0.941))
        delta += 0.0020 * np.sin(5.0 * thetas + z * 31.0 + noise_phase) * (1.0 - band * 0.8)
        delta += 0.0014 * np.sin(11.0 * thetas - z * 47.0 + 1.7 * noise_phase)
        return 1.0 + delta / rho
    return radial


def build_hips():
    mesh = K.Mesh()
    rings = []
    for index, z in enumerate(HIP_Z):
        rings.append(K.Ring((0.0, float(_HCY(z)), z), (1, 0, 0), (0, 1, 0), float(_HRX(z)), float(_HRY(z)), n=SUPER_N,
                            radial=_hip_features(z, 0.9 * index), weights=_hip_weights(z)))
    mesh.sweep(rings, HIP_SIDES, DENIM_HIP, phase=0.0, region="jeans_hip", uv0_rect=(0.0, 0.0, 1.0, 1.0),
               uv_tile=tex.DENIM_TILE, closed_end=True)
    return mesh


# --------------------------------------------------------------------------
# Pernas
# --------------------------------------------------------------------------
LEG_TABLE = ((0.905, 0.1005, 0.1070, 0.000), (0.800, 0.0925, 0.0985, 0.002), (0.680, 0.0785, 0.0840, 0.004),
             (0.600, 0.0690, 0.0745, 0.007), (0.500, 0.0635, 0.0700, 0.010), (0.420, 0.0600, 0.0660, 0.007),
             (0.300, 0.0585, 0.0640, 0.003), (0.200, 0.0615, 0.0670, 0.001), (0.105, 0.0690, 0.0765, 0.000))
LEG_Z = (0.905, 0.870, 0.830, 0.790, 0.745, 0.700, 0.655, 0.615, 0.585, 0.560, 0.535, 0.510, 0.485, 0.460, 0.430,
         0.390, 0.340, 0.290, 0.240, 0.200, 0.172, 0.150, 0.130, 0.112, 0.103, 0.100)
_LRX = K.interp([r[0] for r in reversed(LEG_TABLE)], [r[1] for r in reversed(LEG_TABLE)])
_LRY = K.interp([r[0] for r in reversed(LEG_TABLE)], [r[2] for r in reversed(LEG_TABLE)])
_LCY = K.interp([r[0] for r in reversed(LEG_TABLE)], [r[3] for r in reversed(LEG_TABLE)])


def _leg_weights(z):
    return K.blend_chain(["Hips", "Thigh.R", "Shin.R", "Foot.R"], [0.955, S.KNEE_Z, S.ANKLE_Z + 0.02], z, [0.05, 0.055, 0.03])


def _leg_features(z, noise_phase):
    def radial(thetas):
        rx, ry = float(_LRX(z)), float(_LRY(z))
        base = 0.5 * (rx + ry)
        front = np.clip(np.sin(thetas), 0.0, 1.0)
        back = np.clip(-np.sin(thetas), 0.0, 1.0)
        delta = np.zeros_like(thetas)
        # joelho: arcos horizontais na frente, favo atrás
        knee = np.exp(-((z - 0.545) / 0.050) ** 2)
        arcs = 0.5 + 0.5 * np.cos(2.0 * math.pi * (z - 0.50 + 0.012 * np.cos(thetas * 2.0)) / 0.023 + noise_phase * 0.2)
        delta -= 0.0042 * knee * arcs * front ** 0.8
        ham = np.exp(-((z - 0.455) / 0.050) ** 2)
        delta -= 0.0050 * ham * (0.5 + 0.5 * np.cos(2.0 * math.pi * (z - 0.44) / 0.019 + 2.0 * np.sin(thetas * 3.0))) * back ** 0.7
        # coxa: dobras verticais suaves, de peso do tecido
        thigh = float(K.smoothstep(z, 0.55, 0.78)) * (1.0 - float(K.smoothstep(z, 0.88, 0.905)))
        delta += 0.0030 * thigh * np.sin(4.0 * thetas + z * 9.0 + noise_phase)
        # barra: acordeão sobre a bota, mais forte na frente
        hem = float(np.exp(-((z - 0.145) / 0.050) ** 2))
        accordion = 0.5 + 0.5 * np.cos(2.0 * math.pi * (z - 0.10) / 0.030 + 1.3 * np.sin(thetas * 2.0))
        delta += 0.0075 * hem * (accordion - 0.5) * (0.5 + 0.5 * front)
        delta += 0.0030 * hem * np.sin(6.0 * thetas + noise_phase)
        delta += 0.0016 * np.sin(7.0 * thetas - z * 37.0 + 1.3 * noise_phase)
        flare = float(K.smoothstep(z, 0.108, 0.100))
        delta += 0.0045 * flare
        return 1.0 + delta / base
    return radial


def build_leg_right():
    mesh = K.Mesh()
    rings = []
    for index, z in enumerate(LEG_Z):
        rx, ry, cy = float(_LRX(z)), float(_LRY(z)), float(_LCY(z))
        rings.append(K.Ring((S.LEG_X, cy, z), (1, 0, 0), (0, 1, 0), rx, ry, n=2.3, radial=_leg_features(z, 0.8 * index),
                            weights=_leg_weights(z)))
    mesh.sweep(rings, LEG_SIDES, DENIM, phase=0.0, region="jeans_leg", uv0_rect=tex.DENIM_LEG_ATLAS["R"],
               uv_tile=tex.DENIM_TILE)
    return mesh


def mirror_leg(mesh):
    mesh.transform(np.diag([-1.0, 1.0, 1.0]), rename=lambda name: name.replace(".R", ".L"))
    return mesh.shift_uv0(0.5, 0.0, materials=(DENIM,))


# --------------------------------------------------------------------------
# Cinto
# --------------------------------------------------------------------------
BELT_Z0, BELT_Z1 = 0.944, 0.986
BELT_N = 44


def _waist(z, off=0.0):
    return float(_HRX(z)) + off, float(_HRY(z)) + off, float(_HCY(z))


def build_belt():
    """Cinto de couro gasto: faixa com bordas arredondadas, ponta sobreposta, fivela retangular, furos e passantes."""
    mesh = K.Mesh()
    weights = {"Hips": 1.0}
    profile = [(BELT_Z0, -0.0020), (BELT_Z0 + 0.0012, 0.0028), (BELT_Z0 + 0.0035, 0.0043), (0.965, 0.0046),
               (BELT_Z1 - 0.0035, 0.0043), (BELT_Z1 - 0.0012, 0.0028), (BELT_Z1, -0.0020)]
    rings = []
    for z, off in profile:
        rx, ry, cy = _waist(0.965, off)
        rings.append(K.Ring((0.0, cy, z), (1, 0, 0), (0, 1, 0), rx, ry, n=SUPER_N, weights=dict(weights)))
    mesh.sweep(rings, BELT_N, LEATHER, phase=-math.pi / 2, region="belt", uv0_rect=NEUTRAL, uv_tile=0.05)
    mesh.merge(_belt_tail())
    mesh.merge(_buckle())
    for angle in (math.radians(55), math.radians(125), math.radians(8), math.radians(172), math.radians(-90)):
        mesh.merge(_belt_loop(angle))
    return mesh


def _waist_point(theta, z, off):
    rx, ry, cy = _waist(0.965, off)
    e = 2.0 / SUPER_N
    c, s = math.cos(theta), math.sin(theta)
    return np.array([rx * math.copysign(abs(c) ** e, c), cy + ry * math.copysign(abs(s) ** e, s), z])


def _belt_tail():
    """Ponta do cinto: uma segunda camada de couro sobre a faixa, do centro da frente até a esquerda, com a ponta arredondada."""
    mesh = K.Mesh()
    thetas = np.linspace(math.pi / 2 + 0.12, math.pi / 2 + 0.95, 14)
    rings = []
    for index, theta in enumerate(thetas):
        center = _waist_point(theta, 0.965, 0.0074)
        radial = np.array([math.cos(theta), math.sin(theta), 0.0])
        radial[2] = 0.0
        radial /= np.linalg.norm(radial)
        last = len(thetas) - 1
        taper = 1.0 if index < last - 2 else (0.92, 0.7, 0.35)[index - (last - 2)]
        rings.append(K.Ring(center, np.array([0.0, 0.0, 1.0]), radial, 0.0165 * taper, 0.0017, n=4.0, weights={"Hips": 1.0}))
    mesh.sweep(rings, 12, LEATHER, phase=0.0, region="belt_tail", uv0_rect=NEUTRAL, uv_tile=0.05, closed_end=True)
    # furos: pequenos discos escuros pelo cinto (relevo negativo vira disco rebaixado)
    for k in range(5):
        theta = math.pi / 2 + 0.28 + 0.095 * k
        center = _waist_point(theta, 0.965, 0.0093)
        radial = np.array([math.cos(theta), math.sin(theta), 0.0])
        ax = np.cross(radial, [0, 0, 1])
        ring_set = [K.Ring(center + radial * dz, ax, np.array([0.0, 0.0, 1.0]), r, r, weights={"Hips": 1.0})
                    for dz, r in ((0.0, 0.0030), (0.0004, 0.0024))]
        mesh.sweep(ring_set, 10, "sole", phase=0.0, region="belt_hole", uv0_rect=NEUTRAL, uv_tile=0.02, closed_end=True)
    return mesh


def _rounded_rect(width, height, radius, count=40):
    """Pontos (x, z) de um retângulo de cantos arredondados, no sentido anti-horário."""
    pts = []
    corners = ((width / 2 - radius, height / 2 - radius, 0.0), (-(width / 2 - radius), height / 2 - radius, 90.0),
               (-(width / 2 - radius), -(height / 2 - radius), 180.0), (width / 2 - radius, -(height / 2 - radius), 270.0))
    per = count // 4
    for cx, cz, start in corners:
        for k in range(per):
            a = math.radians(start + 90.0 * k / per)
            pts.append((cx + radius * math.cos(a), cz + radius * math.sin(a)))
    return pts


def _buckle():
    """Fivela retangular de aço gasto: moldura de seção arredondada, barra central e lingueta."""
    mesh = K.Mesh()
    z0 = 0.965
    y = _waist(0.965, 0.0)[2] + float(_HRY(0.965)) + 0.0092
    pts = _rounded_rect(0.058, 0.040, 0.007, 40)
    rings = []
    for index, (x, z) in enumerate(pts):
        nx, nz = pts[(index + 1) % len(pts)][0] - pts[index - 1][0], pts[(index + 1) % len(pts)][1] - pts[index - 1][1]
        tangent = np.array([nx, 0.0, nz]) / math.hypot(nx, nz)
        inward = np.array([-nz, 0.0, nx]) / math.hypot(nx, nz)
        rings.append(K.Ring((x, y, z0 + z), inward, np.array([0.0, 1.0, 0.0]), 0.0034, 0.0021, n=2.4, weights={"Hips": 1.0}))
    mesh.sweep(rings, 10, METAL, phase=0.0, region="buckle", uv0_rect=NEUTRAL, uv_tile=0.02, loop=True)
    bar = [K.Ring((x, y + 0.0004, z0), np.array([0.0, 0.0, 1.0]), np.array([0.0, 1.0, 0.0]), 0.0030, 0.0030, weights={"Hips": 1.0})
           for x in np.linspace(-0.027, 0.027, 5)]
    mesh.sweep(bar, 8, METAL, phase=0.0, region="buckle_bar", uv0_rect=NEUTRAL, uv_tile=0.02, closed_start=True, closed_end=True)
    prong = [K.Ring((0.0, y + 0.0012 - 0.0006 * k, z0 + 0.001 - 0.0105 * k), np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]),
                    0.0022 - 0.0004 * k, 0.0012, weights={"Hips": 1.0}) for k in range(4)]
    mesh.sweep(prong, 8, METAL, phase=0.0, region="buckle_prong", uv0_rect=NEUTRAL, uv_tile=0.02, closed_end=True)
    return mesh


def _belt_loop(theta):
    mesh = K.Mesh()
    rings = []
    for z in (0.936, 0.942, 0.956, 0.974, 0.990, 0.998):
        off = 0.0062 if 0.944 < z < 0.988 else 0.0020
        center = _waist_point(theta, z, off)
        radial = np.array([math.cos(theta), math.sin(theta), 0.0])
        radial /= np.linalg.norm(radial)
        tangent = np.cross([0.0, 0.0, 1.0], radial)
        rings.append(K.Ring(center, tangent, radial, 0.0058, 0.0016, n=3.0, weights={"Hips": 1.0}))
    mesh.sweep(rings, 8, DENIM_HIP, phase=0.0, region="belt_loop", uv0_rect=NEUTRAL, uv_tile=0.05)
    return mesh
