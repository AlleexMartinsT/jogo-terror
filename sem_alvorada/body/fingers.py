"""Dedos: de cinco números (curls) e um de abertura (spread) às rotações das 15 falanges de uma mão.

`curls` vai do polegar ao mindinho, de 0 (dedo esticado) a 1 (totalmente fechado sobre a palma).
Cada dedo reparte o seu `curl` entre as três juntas com a proporção anatômica (nó, meio, ponta).
O polegar tem duas chaves (aberto e fechado sobre a palma) e interpola entre elas.
"""
import math

from mathutils import Quaternion

from . import skeleton as S

# ângulo máximo (graus) de cada junta quando o dedo está com curl = 1: nó (MCP), meio (PIP), ponta (DIP)
MAX_JOINT = {"Index": (82.0, 100.0, 66.0), "Middle": (86.0, 104.0, 68.0), "Ring": (88.0, 104.0, 68.0),
             "Pinky": (90.0, 106.0, 70.0)}
# abertura lateral de cada dedo (graus) quando spread = 1; positivo vai para o lado do polegar
FAN = {"Index": 12.0, "Middle": 3.0, "Ring": -7.0, "Pinky": -17.0}
THUMB_SPREAD = 38.0

# polegar: (rotação em torno de F, em torno do eixo de dobra, em torno de p) por osso na chave fechada, graus
THUMB_CLOSED = {0: (-52.4, 1.2, 59.4), 1: (0.0, 32.0, 0.0), 2: (0.0, 64.3, 0.0)}

# presets: (curls do polegar ao mindinho, spread). Usados por quem posiciona as mãos (`PRESETS[nome]`).
PRESETS = {
    "relaxed": ((0.30, 0.22, 0.28, 0.34, 0.40), 0.05),
    "open": ((0.0, 0.0, 0.0, 0.0, 0.0), 0.55),
    "flat": ((0.0, 0.0, 0.0, 0.0, 0.0), 0.12),
    "grip_cylinder": ((0.52, 0.58, 0.64, 0.68, 0.70), 0.0),
    "pinch": ((0.61, 0.57, 0.40, 0.48, 0.56), 0.0),
    "point": ((0.35, 0.0, 0.92, 0.95, 0.97), 0.0),
    "hold_card": ((0.34, 0.36, 0.30, 0.40, 0.46), 0.0),
    "cradle": ((0.18, 0.34, 0.40, 0.46, 0.52), 0.10),
    "hook": ((0.40, 0.55, 0.85, 0.88, 0.90), 0.0),
    "fist": ((0.85, 1.0, 1.0, 1.0, 1.0), 0.0),
}
RELAXED_CURLS, RELAXED_SPREAD = PRESETS["relaxed"]


def preset(name):
    """(curls, spread) do preset `name`."""
    curls, spread = PRESETS[name]
    return tuple(curls), spread


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


class HandAxes:
    """Eixos de uma mão no repouso, para montar rotações de dedo (espaço do corpo)."""

    def __init__(self, side):
        f, p, t = S.hand_frame(side)
        self.f, self.p = f, p
        self.curl = f.cross(p).normalized()          # girar em torno dele fecha o dedo para a palma
        self.side = side


_AXES = {side: HandAxes(side) for side in S.SIDES}


def finger_rotations(side, curls, spread=0.0):
    """{osso: Quaternion local} das 15 falanges. Só inclui ossos que se movem (curl ou abertura diferente de zero)."""
    axes = _AXES[side]
    out = {}
    for finger, curl in zip(S.FINGERS, curls[1:]):
        curl = _clamp01(curl)
        joints = MAX_JOINT[finger]
        fan = math.radians(FAN[finger] * spread)
        bones = S.finger_bones(side, finger)
        for index, bone in enumerate(bones):
            angle = math.radians(joints[index] * curl)
            q = Quaternion(axes.curl, angle)
            if index == 0 and fan:
                q = Quaternion(axes.p, -fan if side == "R" else fan) @ q
            out[bone] = q
    thumb = _clamp01(curls[0])
    bones = S.finger_bones(side, "Thumb")
    for index, bone in enumerate(bones):
        about_f, about_curl, about_p = THUMB_CLOSED[index]
        s = thumb
        q = (Quaternion(axes.f, math.radians(about_f * s)) @ Quaternion(axes.curl, math.radians(about_curl * s))
             @ Quaternion(axes.p, math.radians(about_p * s)))
        if index == 0 and spread:
            q = Quaternion(axes.p, math.radians(-THUMB_SPREAD * spread * (1 if side == "R" else -1))) @ q
        out[bone] = q
    return out
