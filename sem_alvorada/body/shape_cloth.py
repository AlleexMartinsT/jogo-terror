"""Roupa e calçado de Daniel: camisa de flanela, calça jeans, cinto, botas.

Versão do marco 1: formas corretas em proporção, sem os detalhes finos (dobras, costuras, botões).
Lado direito construído e espelhado (`shape_skin.mirror_arm`); o tronco e a calça são simétricos.
"""
import math

import numpy as np

from . import meshkit as K
from . import skeleton as S
from .shape_skin import forearm_weights

FLANNEL, DENIM, LEATHER, SOLE = "flannel", "denim", "leather", "sole"
TORSO_SIDES = 28


def _ring_z(z, rx, ry, cy, weights, n=2.4, radial=None):
    return K.Ring((0.0, cy, z), (1, 0, 0), (0, 1, 0), rx, ry, n=n, weights=weights, radial=radial)


def torso_weights(z, thetas=None):
    base = K.blend_chain(["Hips", "Spine1", "Spine2", "Spine3"], [1.025, 1.16, 1.30], z, 0.045)
    return base


def shoulder_weights(z):
    """Pesos de um anel do tronco por ângulo: o topo acompanha também as clavículas."""
    base = torso_weights(z)

    def per_vertex(thetas):
        out = []
        for theta in thetas:
            w = dict(base)
            lateral = abs(math.cos(theta))
            front = max(0.0, math.sin(theta))
            top = K.ramp(z, 1.36, 1.44)
            if top > 0.0:
                share = top * lateral * 0.55
                side = "R" if math.cos(theta) > 0 else "L"
                w = {k: v * (1.0 - share) for k, v in w.items()}
                w[f"Clavicle.{side}"] = share
            chest = K.ramp(z, 1.20, 1.28) * (1.0 - K.ramp(z, 1.40, 1.46)) * front * 0.55
            if chest > 0.0:
                w = {k: v * (1.0 - chest) for k, v in w.items()}
                w["Chest"] = chest
            out.append(K.normalize(w))
        return out
    return per_vertex


def build_shirt_torso():
    mesh = K.Mesh()
    table = [  # z, rx, ry, deslocamento y
        (0.925, 0.158, 0.108, 0.000), (0.985, 0.152, 0.104, 0.004), (1.050, 0.143, 0.098, 0.004),
        (1.120, 0.145, 0.098, 0.006), (1.200, 0.152, 0.102, 0.008), (1.280, 0.160, 0.106, 0.010),
        (1.350, 0.168, 0.106, 0.010), (1.400, 0.170, 0.100, 0.008), (1.435, 0.148, 0.086, 0.010),
        (1.462, 0.088, 0.072, 0.016), (1.486, 0.064, 0.060, 0.022),
    ]
    rings = [_ring_z(z, rx, ry, cy, shoulder_weights(z)) for z, rx, ry, cy in table]
    mesh.sweep(rings, TORSO_SIDES, FLANNEL, phase=-math.pi / 2 + math.pi / TORSO_SIDES * 0.0, region="shirt",
               uv_tile=0.12, closed_start=True, closed_end=True)
    return mesh


def _arm_chain_points():
    shoulder = np.array(S.BONE_MAP["UpperArm.R"].head)
    elbow = np.array(S.BONE_MAP["Forearm.R"].head)
    wrist = np.array(S.BONE_MAP["Hand.R"].head)
    return shoulder, elbow, wrist


CUFF_FROM_ELBOW = 0.12            # onde termina a manga dobrada, medido a partir do cotovelo


def build_sleeve_right():
    """Manga direita: da cúpula do ombro até o punho dobrado no antebraço."""
    mesh = K.Mesh()
    shoulder, elbow, wrist = _arm_chain_points()
    fore_dir = (wrist - elbow) / np.linalg.norm(wrist - elbow)
    cuff = elbow + fore_dir * CUFF_FROM_ELBOW
    top = shoulder + np.array([-0.012, 0.0, 0.052])
    curve = K.polyline_curve([top, shoulder, shoulder + (elbow - shoulder) * 0.5, elbow, cuff])
    upper_len = float(np.linalg.norm(elbow - shoulder))
    total = curve.length
    # (distância ao longo da manga a partir da cúpula, raio lateral, raio frontal)
    table = [(0.000, 0.020, 0.020), (0.012, 0.045, 0.044), (0.030, 0.060, 0.057), (0.052, 0.063, 0.059),
             (0.110, 0.058, 0.055), (0.200, 0.050, 0.049), (0.300, 0.046, 0.046), (0.052 + upper_len - 0.01, 0.0455, 0.0455),
             (0.052 + upper_len + 0.045, 0.043, 0.042), (total, 0.0445, 0.0430)]
    ds = [row[0] for row in table]
    rx_f, ry_f = K.interp(ds, [r[1] for r in table]), K.interp(ds, [r[2] for r in table])
    samples = [0.0, 0.012, 0.030, 0.052, 0.080, 0.130, 0.200, 0.270, 0.052 + upper_len - 0.02,
               0.052 + upper_len + 0.015, 0.052 + upper_len + 0.060, total]
    rings = []
    for d in samples:
        pos, tan = curve(min(d / total, 1.0))
        ay, _ = K.perpendicular_frame(tan, np.array([0.0, 1.0, 0.0]))
        ax = np.cross(ay, tan)
        rings.append(K.Ring(pos, ax, ay, float(rx_f(d)), float(ry_f(d)), n=2.2, weights=_sleeve_weights(d, upper_len)))
    mesh.sweep(rings, 20, FLANNEL, region="sleeve", uv_tile=0.12, closed_start=True)
    return mesh


def _sleeve_weights(d, upper_len):
    along_arm = d - 0.052
    if along_arm < upper_len + 0.03:
        w = {"UpperArm.R": 1.0}
        if along_arm < 0.07:
            share = 1.0 - K.ramp(along_arm, -0.04, 0.07)
            w = {"UpperArm.R": 1.0 - 0.55 * share, "Clavicle.R": 0.40 * share, "Spine3": 0.15 * share}
        if along_arm > upper_len - 0.05:
            return K.blend_chain(["UpperArm.R", "Forearm.R"], [upper_len], along_arm, 0.045)
        return w
    return _forearm_part(along_arm - upper_len)


def _forearm_part(e):
    """Pesos na manga a `e` metros do cotovelo."""
    return forearm_weights(e - S.FOREARM_LEN, "R")


def build_pants():
    mesh = K.Mesh()
    waist = [(0.985, 0.156, 0.104, 0.003), (0.940, 0.164, 0.110, 0.002), (0.880, 0.166, 0.112, 0.000),
             (0.820, 0.160, 0.108, 0.000), (0.775, 0.130, 0.100, 0.000)]
    rings = [_ring_z(z, rx, ry, cy, {"Hips": 1.0}, n=2.5) for z, rx, ry, cy in waist]
    mesh.sweep(rings, TORSO_SIDES, DENIM, region="jeans_hip", uv_tile=0.12, closed_start=True, closed_end=True)
    mesh.merge(_leg_right())
    left = _leg_right()
    mesh.merge(left.transform(np.diag([-1.0, 1.0, 1.0]), rename=lambda n: n.replace(".R", ".L")))
    return mesh


def _leg_right():
    mesh = K.Mesh()
    x = S.LEG_X
    table = [  # z, rx, ry, cy
        (0.905, 0.092, 0.104, 0.000), (0.800, 0.088, 0.096, 0.002), (0.680, 0.074, 0.082, 0.004),
        (0.560, 0.063, 0.070, 0.008), (0.500, 0.060, 0.068, 0.010), (0.420, 0.057, 0.063, 0.006),
        (0.300, 0.055, 0.062, 0.002), (0.190, 0.057, 0.064, 0.000), (0.105, 0.063, 0.070, 0.000),
    ]
    rings = []
    for z, rx, ry, cy in table:
        w = K.blend_chain(["Hips", "Thigh.R", "Shin.R"], [0.95, S.KNEE_Z + 0.0], z, [0.04, 0.05])
        rings.append(K.Ring((x, cy, z), (1, 0, 0), (0, 1, 0), rx, ry, n=2.3, weights=w))
    mesh.sweep(rings, 20, DENIM, region="jeans_leg", uv_tile=0.12, closed_end=False)
    return mesh


def build_boot_right():
    """Bota de couro: casco único do calcanhar à ponta, mais o cano em volta do tornozelo."""
    mesh = K.Mesh()
    x = S.LEG_X
    table = [  # y, meia-largura, meia-altura, z do centro
        (-0.068, 0.030, 0.050, 0.060), (-0.050, 0.037, 0.075, 0.078), (-0.010, 0.040, 0.092, 0.092),
        (0.040, 0.043, 0.060, 0.062), (0.090, 0.047, 0.040, 0.042), (0.140, 0.047, 0.030, 0.032),
        (0.200, 0.042, 0.027, 0.029), (0.245, 0.030, 0.022, 0.025), (0.262, 0.012, 0.014, 0.017),
    ]
    rings = []
    for y, hw, hh, zc in table:
        w = {f"Foot.R": 1.0}
        if y > 0.12:
            w = K.blend_chain(["Foot.R", "Toe.R"], [0.13], y, 0.03)
        rings.append(K.Ring((x, y, zc), (1, 0, 0), (0, 0, 1), hw, hh, n=2.6, weights=w))
    mesh.sweep(rings, 18, LEATHER, region="boot", uv_tile=0.12, closed_start=True, closed_end=True)
    return mesh


def mirror(mesh):
    return mesh.transform(np.diag([-1.0, 1.0, 1.0]), rename=lambda n: n.replace(".R", ".L"))
