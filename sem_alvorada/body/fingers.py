"""Dedos: de cinco números (curls) e um de abertura (spread) às rotações das 15 falanges de uma mão.

`curls` vai do polegar ao mindinho, de 0 (dedo esticado) a 1 (totalmente fechado sobre a palma).
Cada dedo reparte o seu `curl` entre as três juntas com a proporção anatômica (nó, meio, ponta).
O polegar tem duas chaves (aberto e fechado sobre a palma) e interpola entre elas.
"""
import math

from mathutils import Quaternion

from . import skeleton as S

IDENTITY = S.IDENTITY

# ângulo máximo (graus) de cada junta quando o dedo está com curl = 1: nó (MCP), meio (PIP), ponta (DIP)
MAX_JOINT = {"Index": (82.0, 100.0, 66.0), "Middle": (86.0, 104.0, 68.0), "Ring": (88.0, 104.0, 68.0),
             "Pinky": (90.0, 106.0, 70.0)}
# abertura lateral de cada dedo (graus) quando spread = 1; positivo vai para o lado do polegar
FAN = {"Index": 12.0, "Middle": 3.0, "Ring": -7.0, "Pinky": -17.0}
THUMB_SPREAD = 38.0
# Polegar relaxado. O osso de repouso aponta quase de lado (abdução de ~65 graus em relação aos dedos) e, com curl pequeno,
# a mão aberta ou em concha ficava com um polegar reto e comprido, perpendicular à palma. Uma mão relaxada tem o polegar a
# ~35 graus do indicador, à frente da palma e um pouco dobrado. Direções dos ossos CMC, MCP e IP nessa pose, nas
# componentes (dedos, lado do polegar, normal da palma). ESTIMADO (proporções de livro-texto, ajustado a olho).
THUMB_RELAXED = ((0.80, 0.45, 0.40), (0.90, 0.25, 0.35), (0.85, 0.15, 0.50))

# polegar: (rotação em torno de F, em torno do eixo de dobra, em torno de p) por osso na chave fechada, graus
THUMB_CLOSED = {0: (-52.4, 1.2, 59.4), 1: (0.0, 32.0, 0.0), 2: (0.0, 64.3, 0.0)}

# presets: (curls do polegar ao mindinho, spread). Usados por quem posiciona as mãos (`PRESETS[nome]`).
PRESETS = {
    "relaxed": ((0.52, 0.22, 0.28, 0.34, 0.40), 0.05),     # polegar quase junto do indicador, não aberto para o lado
    "open": ((0.0, 0.0, 0.0, 0.0, 0.0), 0.55),
    "flat": ((0.18, 0.0, 0.0, 0.0, 0.0), 0.12),
    "grip_cylinder": ((0.57, 0.61, 0.73, 0.75, 0.92), 0.0),
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
        self.thumb_relaxed = self._relaxed_thumb(side, f, p, t)

    @staticmethod
    def _relaxed_thumb(side, f, p, t):
        """Quaternions locais dos três ossos do polegar na pose relaxada (rotação mínima do repouso até a direção alvo)."""
        bones = [S.BONE_MAP[f"Thumb{i}.{side}"] for i in range(3)]
        quats, parent = [], IDENTITY
        for bone, (cf, ct, cp) in zip(bones, THUMB_RELAXED):
            target = (f * cf + t * ct + p * cp).normalized()
            local_target = parent.inverted() @ target
            q = bone.rest_dir.rotation_difference(local_target)
            quats.append(q)
            parent = parent @ q
        return quats


_AXES = {side: HandAxes(side) for side in S.SIDES}


def finger_rotations(side, curls, spread=0.0, joint_curls=None):
    """{osso: Quaternion local} das 15 falanges. Só inclui ossos que se movem (curl ou abertura diferente de zero).

    `joint_curls` (opcional, [5][3]: dedo do polegar ao mindinho, junta da base para a ponta) dá o curl de cada junta
    em separado, para a flexão em cascata de `FingerCascade`; sem ele as três juntas de um dedo usam o mesmo curl."""
    axes = _AXES[side]
    out = {}
    for finger, curl in zip(S.FINGERS, curls[1:]):
        joints = MAX_JOINT[finger]
        fan = math.radians(FAN[finger] * spread)
        bones = S.finger_bones(side, finger)
        row = joint_curls[S.FINGER_NAMES.index(finger)] if joint_curls is not None else (curl, curl, curl)
        for index, bone in enumerate(bones):
            angle = math.radians(joints[index] * _clamp01(row[index]))
            q = Quaternion(axes.curl, angle)
            if index == 0 and fan:
                q = Quaternion(axes.p, -fan if side == "R" else fan) @ q
            out[bone] = q
    bones = S.finger_bones(side, "Thumb")
    row = joint_curls[0] if joint_curls is not None else (curls[0], curls[0], curls[0])
    for index, bone in enumerate(bones):
        about_f, about_curl, about_p = THUMB_CLOSED[index]
        closed = (Quaternion(axes.f, math.radians(about_f)) @ Quaternion(axes.curl, math.radians(about_curl))
                  @ Quaternion(axes.p, math.radians(about_p)))
        q = axes.thumb_relaxed[index].slerp(closed, _clamp01(row[index]))
        if index == 0 and spread:
            q = Quaternion(axes.p, math.radians(-THUMB_SPREAD * spread * (1 if side == "R" else -1))) @ q
        out[bone] = q
    return out


# Flexão em cascata. Ao fechar a mão sobre um objeto os dedos não dobram como um bloco: a junta da base (MCP) sai primeiro,
# a do meio (PIP) acompanha com um atraso e a da ponta (DIP) vem junto com ela (a DIP anda ~2/3 da PIP). Aqui cada junta
# segue a anterior por um filtro de 1ª ordem, em série. As constantes (s) são ESTIMADAS (não há captura de dedos no
# acervo da CMU): ~40 ms na base e ~25 ms por junta seguinte, com o mindinho 10% mais lento a cada dedo a partir do indicador,
# o que dá ~200 ms para uma mão se fechar, a ordem de grandeza de um agarre (150 a 250 ms).
CASCADE_TAU = (0.040, 0.026, 0.026)
CASCADE_FINGER_SLOWING = 0.10


class FingerCascade:
    """Estado dos 5 dedos x 3 juntas e o passo da cascata."""

    def __init__(self, curls):
        self.joint = [[float(c)] * 3 for c in curls]

    def reset(self, curls):
        self.joint = [[float(c)] * 3 for c in curls]

    def step(self, dt, goal):
        """Avança `dt` s rumo a `goal` (5 curls). Devolve True se alguma junta mudou."""
        changed = False
        for finger in range(5):
            slow = 1.0 + CASCADE_FINGER_SLOWING * max(0, finger - 1)
            lead = float(goal[finger])
            for j in range(3):
                value = self.joint[finger][j]
                delta = lead - value
                if abs(delta) > 1e-4:
                    new = value + delta * (1.0 - math.exp(-dt / (CASCADE_TAU[j] * slow)))
                    self.joint[finger][j] = new if abs(lead - new) > 1e-4 else lead
                    changed = True
                lead = self.joint[finger][j]
        return changed
