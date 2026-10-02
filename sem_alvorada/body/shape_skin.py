"""Pele de Daniel: antebraço descoberto, palma, dorso, cinco dedos com falanges e unhas.

Tudo é construído para o lado DIREITO no espaço do corpo e espelhado para o esquerdo (`mirror_arm`).
O antebraço e a mão são uma única varredura contínua do punho do punho dobrado (sob o punho da manga)
até a linha dos nós dos dedos, então não há emenda no pulso. Os dedos saem dos nós como varreduras
separadas que se sobrepõem à palma na base (a membrana entre os dedos aparece de graça).
"""
import math

import numpy as np

from . import meshkit as K
from . import skeleton as S

SKIN, NAIL = "skin", "nail"
MAX_SIDES = 20            # lados da seção do antebraço e da palma
FINGER_SIDES = 12


def _g(x, center, width):
    return np.exp(-((x - center) / width) ** 2)


def _angle_gap(theta, center):
    """Diferença angular mínima, em radianos, com sinal ignorado."""
    return np.abs((theta - center + math.pi) % (2.0 * math.pi) - math.pi)


# --------------------------------------------------------------------------
# Antebraço + mão (varredura contínua)
# --------------------------------------------------------------------------
# distância ao punho (m, negativa rumo ao cotovelo) -> semi-eixo lateral e de espessura
_ARM_PROFILE = (
    (-0.200, 0.0395, 0.0340), (-0.140, 0.0360, 0.0305), (-0.080, 0.0320, 0.0255), (-0.040, 0.0290, 0.0215),
    (-0.010, 0.0282, 0.0195), (0.000, 0.0300, 0.0195), (0.018, 0.0380, 0.0172), (0.045, 0.0425, 0.0152),
    (0.070, 0.0432, 0.0142), (0.088, 0.0428, 0.0132), (0.098, 0.0412, 0.0118),
)
_ARM_D = [row[0] for row in _ARM_PROFILE]
_RX = K.interp(_ARM_D, [row[1] for row in _ARM_PROFILE])
_RY = K.interp(_ARM_D, [row[2] for row in _ARM_PROFILE])
SAMPLES_D = (-0.200, -0.170, -0.140, -0.110, -0.085, -0.062, -0.040, -0.022, -0.008, 0.004, 0.018, 0.034, 0.050,
             0.066, 0.080, 0.090, 0.098)


def arm_path():
    """(curva, comprimento do antebraço): do cotovelo ao nó dos dedos, a curva por comprimento."""
    elbow = np.array(S.BONE_MAP["Forearm.R"].head)
    middle = np.array(S.BONE_MAP["ForearmRoll.R"].head)
    wrist = np.array(S.BONE_MAP["Hand.R"].head)
    f, _p, _t = S.hand_frame("R")
    end = wrist + np.array(f) * S.HAND_LEN
    return K.polyline_curve([elbow, middle, wrist, end]), float(np.linalg.norm(wrist - elbow))


def forearm_weights(d, side="R"):
    """Pesos de um ponto do antebraço/mão à distância d do punho (negativa para o cotovelo)."""
    bones = [f"Forearm.{side}", f"ForearmRoll.{side}", f"Hand.{side}"]
    return K.blend_chain(bones, [-0.1325, 0.0], d, [0.052, 0.034])


def _arm_features(d, rx, ry):
    """Fator radial por ângulo (0 = lado do polegar, pi/2 = palma, pi = lado do mindinho, 3pi/2 = dorso)."""
    tendon_t = [3 * math.pi / 2 + S.MCP_LATERAL[f] / max(rx, 0.02) for f in S.FINGERS]

    def radial(theta):
        fac = np.ones_like(theta)
        fac += 0.30 * _g(d, 0.030, 0.022) * np.exp(-(_angle_gap(theta, 0.95) / 0.60) ** 2)            # tênar
        fac += 0.12 * _g(d, 0.048, 0.026) * np.exp(-(_angle_gap(theta, 2.20) / 0.55) ** 2)            # hipotênar
        window = K.smoothstep(d, 0.012, 0.040) * (1.0 - K.smoothstep(d, 0.090, 0.100))
        for angle, finger in zip(tendon_t, S.FINGERS):
            fac += 0.075 * window * np.exp(-(_angle_gap(theta, angle) / 0.13) ** 2)                    # tendões
            fac += 0.20 * _g(d, S.MCP_FORWARD[finger], 0.010) * np.exp(-(_angle_gap(theta, angle) / 0.20) ** 2)   # nós
        fac += 0.11 * _g(d, -0.006, 0.009) * np.exp(-(_angle_gap(theta, 3.90) / 0.30) ** 2)          # estiloide da ulna
        fac += 0.05 * _g(d, -0.105, 0.045) * np.exp(-(_angle_gap(theta, 0.45) / 0.6) ** 2)            # braquiorradial
        fac -= 0.06 * _g(d, 0.060, 0.030) * np.exp(-(_angle_gap(theta, math.pi / 2) / 0.35) ** 2)     # concavidade da palma
        return fac
    return radial


def build_arm_skin(side="R", material=SKIN, uv_rect=(0.0, 0.0, 0.3, 1.0), tile=0.12):
    mesh = K.Mesh()
    curve, fore_len = arm_path()
    f, p, _t = S.hand_frame("R")
    palm = np.array(p)
    rings = []
    for d in SAMPLES_D:
        pos, tan = curve((d + fore_len) / curve.length)
        normal, _ = K.perpendicular_frame(tan, palm)          # eixo da palma
        lateral = np.cross(tan, normal)                       # lado do polegar
        rx, ry = float(_RX(d)), float(_RY(d))
        shift = (0.0019 * float(K.smoothstep(d, 0.0, 0.03)), 0.0)
        rings.append(K.Ring(pos, lateral, normal, rx, ry, n=2.5, radial=_arm_features(d, rx, ry),
                            weights=forearm_weights(d, "R"), shift=shift))
    mesh.sweep(rings, MAX_SIDES, material, phase=0.0, region="skin_arm", uv0_rect=uv_rect, uv_tile=tile,
               closed_end=True)
    return mesh


# --------------------------------------------------------------------------
# Dedos
# --------------------------------------------------------------------------
_FINGER_R = {"Index": 0.0092, "Middle": 0.0095, "Ring": 0.0090, "Pinky": 0.0079}


def finger_profile(finger):
    """[(distância b ao nó, fator de raio, fator de espessura)], b em metros ao longo do dedo."""
    l1, l2, l3 = S.PHALANX[finger]
    b1, b2, b3 = l1, l1 + l2, l1 + l2 + l3
    return [
        (-0.012, 1.18, 1.00), (0.000, 1.12, 0.98), (0.30 * l1, 1.03, 0.94), (0.70 * l1, 0.98, 0.90),
        (b1 - 0.005, 0.95, 0.86), (b1, 1.02, 0.92), (b1 + 0.005, 0.94, 0.86),
        (b1 + 0.55 * l2, 0.90, 0.84), (b2 - 0.004, 0.88, 0.82), (b2, 0.93, 0.88), (b2 + 0.005, 0.88, 0.82),
        (b2 + 0.55 * l3, 0.82, 0.80), (b3 - 0.004, 0.72, 0.76), (b3 - 0.0012, 0.52, 0.60),
    ]


def build_finger(finger, side="R", material=SKIN, uv_rect=(0.3, 0.0, 0.34, 0.45), tile=0.12):
    mesh = K.Mesh()
    f, p, t = (np.array(v) for v in S.hand_frame("R"))
    wrist = np.array(S.BONE_MAP["Hand.R"].head)
    knuckle = wrist + f * S.MCP_FORWARD[finger] + t * S.MCP_LATERAL[finger]
    bones = [f"{finger}{i}.{side}" for i in (1, 2, 3)]
    l1, l2, l3 = S.PHALANX[finger]
    radius = _FINGER_R[finger]
    rings = []
    for b, k_r, k_t in finger_profile(finger):
        center = knuckle + f * b
        if b > l1 + l2:
            center = center + p * (0.0006 * (b - l1 - l2) / l3)          # a polpa do dedo cai para o lado da palma
        w = K.blend_chain(bones, [l1, l1 + l2], b, 0.0045)
        if b < 0.012:                                                    # base: mistura com a palma
            share = K.ramp(b, -0.012, 0.012)
            w = K.normalize({**{k: v * share for k, v in w.items()}, f"Hand.{side}": 1.0 - share})
        rx, ry = radius * k_r, radius * k_t * 0.94

        def flesh(theta, b=b, ry=ry):
            return 1.0 + 0.0 * theta
        rings.append(K.Ring(center, t, p, rx, ry, n=2.4, weights=w))
    rings.append(_apex_ring(knuckle + f * (l1 + l2 + l3 + 0.0006), t, p, radius * 0.22, radius * 0.18, bones[2]))
    mesh.sweep(rings, FINGER_SIDES, material, phase=0.0, region=f"finger_{finger}", uv0_rect=uv_rect, uv_tile=tile,
               closed_end=True)
    return mesh


def _apex_ring(center, ax, ay, rx, ry, bone):
    return K.Ring(center, ax, ay, rx, ry, n=2.0, weights={bone: 1.0})


def thumb_path():
    """Pontos do polegar: CMC, MCP, IP, ponta (espaço do corpo, lado direito)."""
    f, p, t = S.hand_frame("R")
    pts = [np.array(S.BONE_MAP[f"Thumb{i}.R"].head) for i in range(3)] + [np.array(S.BONE_MAP["Thumb2.R"].tail)]
    return pts


def build_thumb(side="R", material=SKIN, uv_rect=(0.34, 0.0, 0.38, 0.45), tile=0.12):
    mesh = K.Mesh()
    f, p, _t = (np.array(v) for v in S.hand_frame("R"))
    pts = thumb_path()
    bones = [f"Thumb{i}.{side}" for i in range(3)]
    lengths = [float(np.linalg.norm(pts[i + 1] - pts[i])) for i in range(3)]
    curve = K.polyline_curve(pts)
    total = curve.length
    edges = np.cumsum([0.0] + lengths)
    # (distância ao CMC, raio lateral, espessura): o polegar é mais largo que um dedo e achatado
    profile = [(-0.006, 0.0150, 0.0125), (0.000, 0.0148, 0.0122), (0.020, 0.0132, 0.0112), (0.044, 0.0124, 0.0108),
               (edges[1] - 0.006, 0.0118, 0.0103), (edges[1], 0.0124, 0.0108), (edges[1] + 0.006, 0.0116, 0.0101),
               (edges[1] + 0.020, 0.0111, 0.0097), (edges[2] - 0.005, 0.0108, 0.0094), (edges[2], 0.0114, 0.0099),
               (edges[2] + 0.005, 0.0107, 0.0092), (edges[2] + 0.018, 0.0100, 0.0087), (total - 0.004, 0.0084, 0.0076),
               (total - 0.0012, 0.0060, 0.0056)]
    rings = []
    for d, rx, ry in profile:
        pos, tan = curve(max(d, 0.0) / total) if d >= 0 else (curve(0.0)[0] + curve(0.0)[1] * d, curve(0.0)[1])
        normal, _ = K.perpendicular_frame(tan, p)
        lateral = np.cross(tan, normal)
        w = K.blend_chain(bones, [edges[1], edges[2]], d, 0.006)
        if d < 0.012:
            share = K.ramp(d, -0.006, 0.012)
            w = K.normalize({**{k: v * share for k, v in w.items()}, f"Hand.{side}": 1.0 - share})
        rings.append(K.Ring(pos, lateral, normal, rx, ry, n=2.4, weights=w))
    pos_end, tan_end = curve(1.0)
    normal, _ = K.perpendicular_frame(tan_end, p)
    rings.append(_apex_ring(pos_end + tan_end * 0.0006, np.cross(tan_end, normal), normal, 0.0020, 0.0016, bones[2]))
    mesh.sweep(rings, FINGER_SIDES, material, phase=0.0, region="thumb", uv0_rect=uv_rect, uv_tile=tile, closed_end=True)
    return mesh


# --------------------------------------------------------------------------
# Unhas
# --------------------------------------------------------------------------
def build_nail(finger, side="R", material=NAIL):
    """Unha de um dedo: grade curva sobre o dorso da última falange, 0,4 mm acima da pele."""
    f, p, t = (np.array(v) for v in S.hand_frame("R"))
    wrist = np.array(S.BONE_MAP["Hand.R"].head)
    mesh = K.Mesh()
    if finger == "Thumb":
        return _thumb_nail(side, material)
    l1, l2, l3 = S.PHALANX[finger]
    knuckle = wrist + f * S.MCP_FORWARD[finger] + t * S.MCP_LATERAL[finger]
    radius = _FINGER_R[finger]
    b_start, b_end = l1 + l2 + 0.28 * l3, l1 + l2 + l3 - 0.0012
    cols, rows = 5, 5
    points = np.zeros((rows, cols, 3))
    for r in range(rows):
        v = r / (rows - 1)
        b = b_start + (b_end - b_start) * v
        k_r = float(np.interp(b, [row[0] for row in finger_profile(finger)], [row[1] for row in finger_profile(finger)]))
        k_t = float(np.interp(b, [row[0] for row in finger_profile(finger)], [row[2] for row in finger_profile(finger)]))
        rx, ry = radius * k_r, radius * k_t * 0.94
        half = rx * 0.72 * (1.0 - 0.18 * v ** 2)
        for c in range(cols):
            u = -1.0 + 2.0 * c / (cols - 1)
            a = half * u
            x_norm = min(abs(a) / rx, 0.98)
            dorsal = -ry * (1.0 - x_norm ** 2.4) ** (1.0 / 2.4) * 1.0
            points[r, c] = knuckle + f * b + t * a + p * (dorsal - 0.0004)
    bone = f"{finger}3.{side}"
    mesh.grid(points, material, {bone: 1.0}, region=f"nail_{finger}", uv0_rect=(0.0, 0.0, 1.0, 1.0), flip=True)
    return mesh


def _thumb_nail(side, material):
    f, p, _t = (np.array(v) for v in S.hand_frame("R"))
    pts = thumb_path()
    curve = K.polyline_curve(pts)
    total = curve.length
    mesh = K.Mesh()
    rows, cols = 5, 5
    points = np.zeros((rows, cols, 3))
    for r in range(rows):
        v = r / (rows - 1)
        d = total - 0.020 + 0.0185 * v
        pos, tan = curve(d / total)
        normal, _ = K.perpendicular_frame(tan, p)
        lateral = np.cross(tan, normal)
        rx, ry = 0.0102 * (1 - 0.15 * v), 0.0090 * (1 - 0.1 * v)
        half = rx * 0.74
        for c in range(cols):
            a = half * (-1.0 + 2.0 * c / (cols - 1))
            x_norm = min(abs(a) / rx, 0.98)
            points[r, c] = pos + lateral * a - normal * (ry * (1.0 - x_norm ** 2.4) ** (1.0 / 2.4) + 0.0004)
    mesh.grid(points, material, {f"Thumb2.{side}": 1.0}, region="nail_Thumb", flip=True)
    return mesh


def build_hand_skin(side="R"):
    """Antebraço + palma + dedos + unhas do lado direito (peças separadas, mesclar depois)."""
    mesh = build_arm_skin(side)
    for finger in S.FINGERS:
        mesh.merge(build_finger(finger, side))
    mesh.merge(build_thumb(side))
    for finger in S.FINGER_NAMES:
        mesh.merge(build_nail(finger, side))
    return mesh


def mirror_arm(mesh):
    """Do lado direito para o esquerdo: espelha em X e troca os sufixos dos ossos."""
    return mesh.transform(np.diag([-1.0, 1.0, 1.0]), rename=lambda name: name.replace(".R", ".L"))
