"""Ajuste numérico dos dedos do corpo (scipy, só para autoria): polegar fechado e empunhadura de lanterna.

    python tools/modelagem/corpo_dedos.py pinca       # polegar e indicador se tocam (preset "pinch", chave do polegar)
    python tools/modelagem/corpo_dedos.py lanterna    # curls e eixo do cano para segurar um cilindro de 3,7 cm

Imprime os números que foram colados em `sem_alvorada/body/fingers.py` (THUMB_CLOSED, PRESETS["pinch"] e
PRESETS["grip_cylinder"]) e em `sem_alvorada/body/handframe.py` (GRIP_ANGLE, GRIP_CENTER_API). Nada aqui é importado
pelo jogo: o corpo só lê os números.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402,F401
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from scipy.optimize import differential_evolution, minimize  # noqa: E402

from sem_alvorada.body import fingers as F  # noqa: E402
from sem_alvorada.body import skeleton as S  # noqa: E402
from sem_alvorada.body import solver as V  # noqa: E402

SIDE = "R"
R_CYL = 0.0186
f, p, t = (np.array(v) for v in S.hand_frame(SIDE))
WRIST = np.array(S.BONE_MAP["Hand.R"].head)
PALM = WRIST + f * S.PALM_CENTER_F + p * S.PALM_SURFACE
PAD = {"Index": 0.0085, "Middle": 0.0088, "Ring": 0.0083, "Pinky": 0.0072}


def pose(curls):
    return V.solve(V.PoseSpec(rot=F.finger_rotations(SIDE, list(curls), 0.0)))


def tune_pinch():
    init = np.array([F.THUMB_CLOSED[i][j] for i in range(3) for j in range(3)] + [0.62, 0.50])

    def cost(x):
        for i in range(3):
            F.THUMB_CLOSED[i] = tuple(x[i * 3:(i + 1) * 3])
        pinch = pose((x[9], x[10], 0.40, 0.48, 0.56))
        fist = pose((1.0, 1, 1, 1, 1))
        grip = pose((0.75, 0.58, 0.64, 0.68, 0.70))
        gap = (pinch.tail("Thumb2.R") - pinch.tail("Index3.R")).length
        fist_d = (fist.tail("Thumb2.R") - fist.point_on("Hand.R", PALM)).length
        grip_d = (grip.tail("Thumb2.R") - grip.tail("Middle3.R")).length
        reg = np.sum(((x[:9] - init[:9]) / 30.0) ** 2) * 0.01
        pen = max(0, x[9] - 1) ** 2 + max(0, 0.15 - x[9]) ** 2 + max(0, x[10] - 0.9) ** 2
        return gap ** 2 * 400 + max(0, fist_d - 0.045) ** 2 * 60 + max(0, grip_d - 0.03) ** 2 * 30 + reg + pen

    best = minimize(cost, init, method="Nelder-Mead", options=dict(maxiter=4000, xatol=0.3, fatol=1e-8)).x
    print("THUMB_CLOSED =", {i: tuple(round(v, 1) for v in best[i * 3:(i + 1) * 3]) for i in range(3)})
    print("pinch: curl do polegar", round(best[9], 2), "curl do indicador", round(best[10], 2))


def tune_grip():
    def contacts(sol):
        out = []
        for finger in S.FINGERS:
            for i in (1, 2, 3):
                name = f"{finger}{i}.R"
                idx = S.BONE_INDEX[name]
                mid = (sol.head[idx] + sol.tail(name)) * 0.5
                out.append((finger, i, np.array(mid + (sol.world[idx] @ Vector(p)) * PAD[finger] * 0.9)))
        for i in (1, 2):
            name = f"Thumb{i}.R"
            idx = S.BONE_INDEX[name]
            mid = (sol.head[idx] + sol.tail(name)) * 0.5
            out.append(("Thumb", i, np.array(mid + (sol.world[idx] @ Vector(p)) * 0.011)))
        return out

    def cost(x):
        curls, phi, bc, cc = x[:5], x[5], x[6], x[7]
        axis = math.cos(phi) * t + math.sin(phi) * f
        center = WRIST + f * bc + p * cc
        total = 0.0
        for finger, i, point in contacts(pose(curls)):
            d = point - center
            gap = np.linalg.norm(d - axis * (d @ axis)) - R_CYL
            weight = 2.0 if finger == "Thumb" else (0.7 if i == 1 else 1.0)
            total += weight * gap ** 2 * (6.0 if gap < 0 else 1.0)
        d = PALM - center
        palm_gap = np.linalg.norm(d - axis * (d @ axis)) - R_CYL
        total += 2.0 * palm_gap ** 2 * (6.0 if palm_gap < 0 else 1.0)
        return total * 1e4 + sum((c - 0.68) ** 2 for c in curls[1:]) * 0.05 * 200

    bounds = [(0.3, 1.0)] + [(0.5, 1.0)] * 4 + [(-0.3, 1.2), (0.035, 0.070), (0.012, 0.05)]
    x = differential_evolution(cost, bounds, maxiter=120, popsize=24, tol=1e-8, seed=3, polish=True).x
    print("grip_cylinder curls (polegar..mindinho):", [round(v, 2) for v in x[:5]])
    print("GRIP_ANGLE (graus):", round(math.degrees(x[5]), 1), " eixo do cano: b =", round(x[6], 4), " c =", round(x[7], 4))


if __name__ == "__main__":
    {"pinca": tune_pinch, "lanterna": tune_grip}[sys.argv[1] if len(sys.argv) > 1 else "lanterna"]()
