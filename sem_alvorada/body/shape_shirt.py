"""Camisa de flanela de manga comprida: tronco com carcela e bolsos, mangas com cotovelo amassado e punho dobrado,
gola, botões. Lado direito construído e espelhado (`mirror`); o tronco é simétrico.

Medidas: homem magro de 1,80 m. Peito 0,31 m de largura por 0,20 de profundidade, cintura 0,28; a camisa tem
folga de cerca de 1,2 cm. A barra fica por dentro da calça, com um franzido por cima do cinto.
"""
import math

import numpy as np

from . import meshkit as K
from . import skeleton as S
from . import tex
from .shape_skin import forearm_weights

FLANNEL, BUTTON, SKIN = "flannel", "button", "skin"
TORSO_SIDES = 40
SLEEVE_SIDES = 24
TORSO_PHASE = -math.pi / 2                    # u = 0 atrás, 0,25 direita, 0,5 frente, 0,75 esquerda

# z, semi-largura (x), semi-profundidade (y), deslocamento do centro em y
TORSO_TABLE = (
    (0.955, 0.158, 0.108, 0.000), (0.990, 0.152, 0.103, 0.003), (1.040, 0.142, 0.097, 0.004),
    (1.090, 0.140, 0.096, 0.005), (1.150, 0.145, 0.098, 0.007), (1.220, 0.153, 0.101, 0.009),
    (1.290, 0.159, 0.104, 0.010), (1.350, 0.165, 0.104, 0.010), (1.385, 0.172, 0.100, 0.008),
    (1.412, 0.168, 0.093, 0.009), (1.436, 0.146, 0.084, 0.012), (1.456, 0.104, 0.074, 0.016), (1.478, 0.068, 0.063, 0.020),
)
TORSO_Z = (0.955, 0.975, 0.995, 1.015, 1.040, 1.070, 1.100, 1.135, 1.170, 1.205, 1.240, 1.275, 1.310, 1.345, 1.372,
           1.395, 1.414, 1.432, 1.448, 1.462, 1.478)
_RX = K.interp([r[0] for r in TORSO_TABLE], [r[1] for r in TORSO_TABLE])
_RY = K.interp([r[0] for r in TORSO_TABLE], [r[2] for r in TORSO_TABLE])
_CY = K.interp([r[0] for r in TORSO_TABLE], [r[3] for r in TORSO_TABLE])
SUPER_N = 2.5
BUTTON_ZS = (1.405, 1.340, 1.275, 1.210, 1.145, 1.080, 1.020)


def _ease(x, edge):
    return K.smoothstep(x, 0.0, edge)


def _section_xy(z, thetas):
    """(x, y) da superelipse do tronco em z (sem deslocamento) para cada ângulo."""
    rx, ry = float(_RX(z)), float(_RY(z))
    e = 2.0 / SUPER_N
    c, s = np.cos(thetas), np.sin(thetas)
    return rx * np.sign(c) * np.abs(c) ** e, ry * np.sign(s) * np.abs(s) ** e


def torso_features(z, noise_phase):
    """Fator radial por ângulo: carcela, bolsos, dobras da barriga, franzido sobre o cinto, costuras e ruído de tecido."""
    def radial(thetas):
        x, y = _section_xy(z, thetas)
        rho = np.maximum(np.hypot(x, y), 0.05)
        front = np.clip(np.sin(thetas), 0.0, 1.0)
        delta = np.zeros_like(thetas)
        # carcela: faixa dupla de 3,4 cm na frente, do colarinho ao cinto
        along = K.smoothstep(z, 1.000, 1.020) * (1.0 - K.smoothstep(z, 1.440, 1.460))
        plank = (1.0 - K.smoothstep(np.abs(x), 0.0150, 0.0185)) * (np.sin(thetas) > 0)
        delta += 0.0038 * along * plank
        delta -= 0.0013 * along * np.exp(-((np.abs(x) - 0.0205) / 0.0032) ** 2) * (np.sin(thetas) > 0)    # vinco ao lado
        # bolsos de peito com aba
        for side in (-1, 1):
            cx = 0.078 * side
            across = 1.0 - K.smoothstep(np.abs(x - cx), 0.052, 0.058)
            body = across * K.smoothstep(z, 1.268, 1.274) * (1.0 - K.smoothstep(z, 1.383, 1.389))
            flap = across * K.smoothstep(z, 1.322, 1.328) * (1.0 - K.smoothstep(z, 1.383, 1.389))
            delta += (0.0026 * body + 0.0017 * flap) * (np.sin(thetas) > 0.2)
        # dobras da barriga: arcos que descem para os lados
        zone = K.smoothstep(z, 0.990, 1.020) * (1.0 - K.smoothstep(z, 1.150, 1.180))
        fold = 0.5 + 0.5 * np.cos(2.0 * math.pi * (z + 0.22 * x * x / 0.02 * 0.12 - 1.0) / 0.036 + noise_phase)
        delta -= 0.0030 * zone * fold * front ** 0.6
        # franzido sobre o cinto
        blouse = np.exp(-((z - 1.012) / 0.020) ** 2)
        delta += blouse * (0.0065 + 0.0030 * np.sin(thetas * 13.0 + noise_phase))
        # costura do ombro e dos ombros caídos
        delta += 0.0016 * np.exp(-((z - 1.410) / 0.006) ** 2) * (np.abs(np.cos(thetas)) > 0.5)
        # tecido: ondas baixas, mais fortes nas costas e embaixo
        wave = (0.50 * np.sin(5.0 * thetas + z * 19.0 + noise_phase) + 0.32 * np.sin(9.0 * thetas - z * 27.0 + 1.3 * noise_phase)
                + 0.18 * np.sin(14.0 * thetas + z * 41.0))
        delta += 0.0017 * wave * (0.6 + 0.4 * (1.0 - front))
        return 1.0 + delta / rho
    return radial


def _torso_weights(z):
    base = K.blend_chain(["Hips", "Spine1", "Spine2", "Spine3"], [1.025, 1.16, 1.30], z, 0.050)

    def per_vertex(thetas):
        out = []
        for theta in thetas:
            weights = dict(base)
            lateral = abs(math.cos(theta))
            front = max(0.0, math.sin(theta))
            top = K.ramp(z, 1.36, 1.44)
            if top > 0.0:
                share = top * lateral * 0.60
                side = "R" if math.cos(theta) > 0 else "L"
                weights = {k: v * (1.0 - share) for k, v in weights.items()}
                weights[f"Clavicle.{side}"] = share
            chest = K.ramp(z, 1.14, 1.26) * (1.0 - K.ramp(z, 1.38, 1.44)) * front * 0.5
            if chest > 0.0:
                weights = {k: v * (1.0 - chest) for k, v in weights.items()}
                weights["Chest"] = chest
            neck = K.ramp(z, 1.455, 1.48)
            if neck > 0.0:
                weights = {k: v * (1.0 - neck) for k, v in weights.items()}
                weights["Neck"] = neck * 0.5
                weights["Spine3"] = weights.get("Spine3", 0.0) + neck * 0.5
            out.append(K.normalize(weights))
        return out
    return per_vertex


def torso_front_y(z):
    return float(_CY(z) + _RY(z))


def build_torso():
    mesh = K.Mesh()
    rings = []
    for index, z in enumerate(TORSO_Z):
        rings.append(K.Ring((0.0, float(_CY(z)), z), (1, 0, 0), (0, 1, 0), float(_RX(z)), float(_RY(z)), n=SUPER_N,
                            radial=torso_features(z, 0.7 * index), weights=_torso_weights(z)))
    mesh.sweep(rings, TORSO_SIDES, FLANNEL, phase=TORSO_PHASE, region="shirt", uv0_rect=tex.FLANNEL_ATLAS["torso"],
               uv_tile=tex.FLANNEL_TILE, closed_start=True, closed_end=True)
    return mesh


def build_collar():
    """Gola de camisa: faixa em pé que cai para fora, e o pescoço de pele que sobe por dentro dela."""
    mesh = K.Mesh()
    weights = {"Neck": 0.55, "Spine3": 0.45}
    profile = [(1.456, 0.0685, 0.0645), (1.470, 0.0678, 0.0638), (1.486, 0.0665, 0.0625), (1.497, 0.0675, 0.0640),
               (1.502, 0.0715, 0.0680), (1.500, 0.0775, 0.0740), (1.493, 0.0835, 0.0800), (1.483, 0.0875, 0.0840),
               (1.478, 0.0880, 0.0845)]
    rings = [K.Ring((0.0, 0.020, z), (1, 0, 0), (0, 1, 0), rx, ry, n=2.2, weights=dict(weights)) for z, rx, ry in profile]
    mesh.sweep(rings, 32, FLANNEL, phase=TORSO_PHASE, region="collar", uv0_rect=tex.FLANNEL_SMALL, uv_tile=tex.FLANNEL_TILE)
    # abertura em V na frente: o colarinho de camisa aberta mostra o pescoço
    mesh.drop_faces(lambda c: c[1] > 0.03 and abs(c[0]) < 0.026 + (c[1] - 0.03) * 0.9 and c[2] > 1.462)
    neck = [(1.468, 0.054, 0.052), (1.50, 0.052, 0.050), (1.532, 0.050, 0.048), (1.546, 0.045, 0.043)]
    rings = [K.Ring((0.0, 0.022, z), (1, 0, 0), (0, 1, 0), rx, ry, n=2.1, weights={"Neck": 1.0}) for z, rx, ry in neck]
    mesh.sweep(rings, 20, SKIN, phase=TORSO_PHASE, region="neck", uv0_rect=(0.0, 0.0, 0.02, 0.02), closed_end=True)
    return mesh


def build_buttons():
    """Sete botões na carcela: disco com borda, concavidade e quatro furos pintados."""
    mesh = K.Mesh()
    for z in BUTTON_ZS:
        y = torso_front_y(z) + 0.0038
        w = K.normalize(_torso_weights(z)(np.array([math.pi / 2]))[0])
        rings = [K.Ring((0.0, y + dy, z), (1, 0, 0), (0, 0, 1), r, r, n=2.0, weights=dict(w)) for dy, r in
                 [(0.0, 0.0058), (0.0008, 0.0060), (0.0021, 0.0054), (0.0026, 0.0040), (0.0022, 0.0030)]]
        mesh.sweep(rings, 14, BUTTON, phase=0.0, region="button", uv0_rect=(0.0, 0.0, 0.1, 0.1), uv_tile=0.02,
                   closed_end=True)
    return mesh


# --------------------------------------------------------------------------
# Manga
# --------------------------------------------------------------------------
CUFF_START, CUFF_END = 0.118, 0.170             # início e fim do punho dobrado, medidos a partir do cotovelo (rente ao pulso: aparece mais manga)
UPPER_LEN = S.UPPER_ARM_LEN


def _sleeve_path():
    shoulder = np.array(S.BONE_MAP["UpperArm.R"].head)
    elbow = np.array(S.BONE_MAP["Forearm.R"].head)
    wrist = np.array(S.BONE_MAP["Hand.R"].head)
    fore = (wrist - elbow) / np.linalg.norm(wrist - elbow)
    top = shoulder + np.array([-0.036, 0.0, 0.020])
    end = elbow + fore * (CUFF_END + 0.02)
    along = [elbow + fore * d for d in (0.04, 0.09, 0.14)]
    return K.polyline_curve([top, shoulder, shoulder + (elbow - shoulder) * 0.5, elbow] + along + [end]), top, shoulder, elbow, fore


# (distância s a partir do ombro, raio lateral, raio frontal); depois do cotovelo o raio depende do punho
SLEEVE_TABLE = ((-0.041, 0.010, 0.010), (-0.036, 0.030, 0.029), (-0.027, 0.046, 0.044), (-0.014, 0.0560, 0.0535), (-0.003, 0.0585, 0.0555),
                (0.020, 0.0585, 0.0555), (0.080, 0.0545, 0.0520), (0.160, 0.0505, 0.0495), (0.250, 0.0480, 0.0480),
                (0.320, 0.0480, 0.0480), (0.335, 0.0480, 0.0480), (0.380, 0.0465, 0.0460), (0.420, 0.0450, 0.0445))
_SR = K.interp([r[0] for r in SLEEVE_TABLE], [r[1] for r in SLEEVE_TABLE])
_SF = K.interp([r[0] for r in SLEEVE_TABLE], [r[2] for r in SLEEVE_TABLE])


def _cuff_radius(e):
    """Raio extra do punho dobrado a `e` m do cotovelo: degrau arredondado na dobra e lábio na ponta."""
    rise = float(K.smoothstep(e, CUFF_START - 0.004, CUFF_START + 0.008))
    lip = float(K.smoothstep(e, CUFF_END - 0.010, CUFF_END + 0.002))
    return 0.0068 * rise - 0.0105 * lip


def _sleeve_weights(s):
    if s > UPPER_LEN - 0.045:
        e = s - UPPER_LEN
        if e > 0.04:
            return forearm_weights(e - S.FOREARM_LEN, "R")
        w = K.blend_chain(["UpperArm.R", "Forearm.R"], [UPPER_LEN], s, 0.04)
        return w
    w = {"UpperArm.R": 1.0}
    if s < 0.065:
        share = 1.0 - K.ramp(s, -0.045, 0.065)
        w = {"UpperArm.R": 1.0 - 0.55 * share, "Clavicle.R": 0.38 * share, "Spine3": 0.17 * share}
    return w


def _sleeve_features(s, phase):
    elbow_zone = float(np.exp(-((s - UPPER_LEN) / 0.055) ** 2))

    def radial(thetas):
        # no anel da manga, ax é o lado (+ para fora) e ay a frente do braço; theta = pi/2 é a frente (dentro do cotovelo)
        front = np.clip(np.sin(thetas), 0.0, 1.0)
        back = np.clip(-np.sin(thetas), 0.0, 1.0)
        base = 0.0495
        delta = np.zeros_like(thetas)
        crease = 0.5 + 0.5 * np.cos(2.0 * math.pi * (s - UPPER_LEN) / 0.0185 + 0.6 * np.sin(thetas * 2.0))
        delta -= 0.0034 * elbow_zone * crease * front ** 0.7                                  # dentro do cotovelo
        delta += 0.0020 * elbow_zone * (0.5 + 0.5 * np.cos(2.0 * math.pi * (s - UPPER_LEN) / 0.030 + 1.7)) * back
        delta += 0.0016 * np.sin(3.0 * thetas + 15.0 * s + phase) * (0.4 + 0.6 * float(K.smoothstep(s, 0.0, 0.18)))
        delta += 0.0012 * np.sin(7.0 * thetas - 31.0 * s + 1.7 * phase)
        delta += 0.0016 * np.exp(-((s + 0.020) / 0.006) ** 2)                                  # costura da cava
        return 1.0 + delta / base
    return radial


def build_sleeve():
    mesh = K.Mesh()
    curve, top, shoulder, elbow, fore = _sleeve_path()
    total = curve.length
    to_shoulder = float(np.linalg.norm(shoulder - top))
    samples = [-0.041, -0.038, -0.032, -0.024, -0.014, -0.003, 0.012, 0.032, 0.060, 0.110, 0.170, 0.230, 0.290, 0.325,
               UPPER_LEN, UPPER_LEN + 0.020, UPPER_LEN + 0.045, UPPER_LEN + CUFF_START - 0.012, UPPER_LEN + CUFF_START - 0.004,
               UPPER_LEN + CUFF_START + 0.004, UPPER_LEN + CUFF_START + 0.014, UPPER_LEN + 0.5 * (CUFF_START + CUFF_END), UPPER_LEN + CUFF_END - 0.012,
               UPPER_LEN + CUFF_END - 0.004, UPPER_LEN + CUFF_END + 0.001]
    rings = []
    for index, s in enumerate(samples):
        pos, tan = curve(min(max((s + to_shoulder) / total, 0.0), 1.0))
        front_hint = np.array([0.0, 1.0, 0.0])
        ay, _ = K.perpendicular_frame(tan, front_hint)
        ax = np.cross(ay, tan)
        e = s - UPPER_LEN
        extra = _cuff_radius(e) if e > 0 else 0.0
        if s > UPPER_LEN:
            skin_r = 0.0445 - 0.00055 * (e * 100.0)
            rx = float(_SR(min(s, 0.42))) + extra if e < CUFF_START - 0.02 else skin_r + 0.0048 + extra
            ry = float(_SF(min(s, 0.42))) + extra if e < CUFF_START - 0.02 else skin_r + 0.0036 + extra
        else:
            rx, ry = float(_SR(s)), float(_SF(s))
        rings.append(K.Ring(pos, ax, ay, rx, ry, n=2.2, radial=_sleeve_features(s, 0.9 * index),
                            weights=_sleeve_weights(s)))
    mesh.sweep(rings, SLEEVE_SIDES, FLANNEL, phase=0.0, region="sleeve", uv0_rect=tex.FLANNEL_ATLAS["sleeve_R"],
               uv_tile=tex.FLANNEL_TILE, closed_start=True)
    return mesh


def mirror(mesh):
    """Direita -> esquerda: espelha e usa a metade esquerda do atlas da flanela."""
    mesh.transform(np.diag([-1.0, 1.0, 1.0]), rename=lambda name: name.replace(".R", ".L"))
    shift = tex.FLANNEL_ATLAS["sleeve_L"][0] - tex.FLANNEL_ATLAS["sleeve_R"][0]
    for i, face in enumerate(mesh.uv0):
        if mesh.region[mesh.faces[i][0]] == "sleeve":
            mesh.uv0[i] = tuple((u + shift, v) for u, v in face)
    return mesh
