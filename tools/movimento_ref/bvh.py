"""Leitor de BVH (captura de movimento real) com cinemática direta.

Convenções deste projeto, valem para qualquer coisa que use `Mocap`:
    mundo   X direita, Y frente, Z cima, em metros (o mesmo do jogo)
    arquivo CMU em unidades de 1/0.45 polegada (0,05644 m), eixo Y para cima, Z em profundidade

`Mocap.world()` já devolve posições e rotações no mundo do jogo, com o esqueleto virado para +Y no primeiro
quadro. Nada aqui importa `bpy`: roda com numpy puro, em qualquer Python.
"""
import re
from dataclasses import dataclass

import numpy as np

CMU_UNIT_M = 0.0254 / 0.45
YUP_TO_ZUP = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])      # (x, y, z) -> (x, -z, y)


@dataclass
class Mocap:
    name: str
    fps: float
    joints: list            # nomes na ordem do arquivo
    parent: list            # índice do pai (-1 na raiz)
    offset: np.ndarray      # [J, 3] metros, nos eixos do arquivo
    channels: list          # por junta: lista de nomes ("Xposition", "Zrotation"...)
    data: np.ndarray        # [T, canais] graus e unidades do arquivo (sem converter)
    unit: float = CMU_UNIT_M

    @property
    def frames(self):
        return self.data.shape[0]

    @property
    def duration(self):
        return self.frames / self.fps

    def index(self, joint):
        return self.joints.index(joint)

    # ---- cinemática direta ----
    def _local_rotations(self):
        """[T, J, 3, 3] rotação de cada junta no espaço do pai, ainda nos eixos do arquivo (Y para cima)."""
        total = self.frames
        rotations = np.tile(np.eye(3), (total, len(self.joints), 1, 1))
        cursor = 0
        for j, names in enumerate(self.channels):
            angles = {}
            for name in names:
                column = self.data[:, cursor]
                cursor += 1
                if name.endswith("rotation"):
                    angles[name[0]] = np.radians(column)
            if angles:
                order = [name[0] for name in names if name.endswith("rotation")]
                matrix = np.tile(np.eye(3), (total, 1, 1))
                for axis in order:                        # a ordem listada é a ordem de composição, da esquerda p/ direita
                    matrix = matrix @ _axis(axis, angles[axis])
                rotations[:, j] = matrix
        return rotations

    def _root_translation(self):
        cursor = 0
        for j, names in enumerate(self.channels):
            if j == 0:
                columns = {n[0]: self.data[:, cursor + k] for k, n in enumerate(names) if n.endswith("position")}
                return np.stack([columns["X"], columns["Y"], columns["Z"]], axis=1) * self.unit
            cursor += len(names)
        raise ValueError("raiz sem translação")

    def world(self, face_forward=True):
        """(posições [T, J, 3], rotações [T, J, 3, 3]) no mundo do jogo. `face_forward` vira o esqueleto do
        primeiro quadro para +Y (a direção que o quadril aponta)."""
        local = self._local_rotations()
        offsets = self.offset
        total, joints = self.frames, len(self.joints)
        positions = np.zeros((total, joints, 3))
        rotations = np.zeros((total, joints, 3, 3))
        root = self._root_translation()
        for j in range(joints):
            p = self.parent[j]
            if p < 0:
                rotations[:, j] = local[:, j]
                positions[:, j] = root
            else:
                rotations[:, j] = rotations[:, p] @ local[:, j]
                positions[:, j] = positions[:, p] + np.einsum("tij,j->ti", rotations[:, p], offsets[j])
        # eixos do arquivo -> mundo do jogo
        positions = positions @ YUP_TO_ZUP.T
        rotations = YUP_TO_ZUP @ rotations @ YUP_TO_ZUP.T
        if face_forward:
            turn = _yaw_to_forward(self, positions)
            positions = positions @ turn.T
            rotations = turn @ rotations
        return positions, rotations


def _axis(axis, radians):
    c, s = np.cos(radians), np.sin(radians)
    one, zero = np.ones_like(c), np.zeros_like(c)
    if axis == "X":
        rows = [[one, zero, zero], [zero, c, -s], [zero, s, c]]
    elif axis == "Y":
        rows = [[c, zero, s], [zero, one, zero], [-s, zero, c]]
    else:
        rows = [[c, -s, zero], [s, c, zero], [zero, zero, one]]
    return np.stack([np.stack(r, axis=-1) for r in rows], axis=-2)


def _yaw_to_forward(mocap, positions):
    """Rotação em torno de Z que faz o quadril do primeiro quadro olhar para +Y (frente = cima x direita)."""
    left, right = mocap.index("LeftUpLeg"), mocap.index("RightUpLeg")
    across = positions[0, right] - positions[0, left]
    forward = np.cross([0.0, 0.0, 1.0], across)
    angle = np.arctan2(forward[1], forward[0])             # ângulo atual da frente
    delta = np.pi / 2 - angle
    c, s = np.cos(delta), np.sin(delta)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def parse(text, name="clip"):
    """Lê o texto de um BVH."""
    header, _, motion = text.partition("MOTION")
    joints, parent, offsets, channels = [], [], [], []
    stack = []
    current = None
    for raw in header.splitlines():
        line = raw.strip()
        if line.startswith(("ROOT", "JOINT")):
            joints.append(line.split()[1])
            parent.append(stack[-1] if stack else -1)
            offsets.append([0.0, 0.0, 0.0])
            channels.append([])
            current = len(joints) - 1
        elif line.startswith("End Site"):
            current = None
        elif line == "{":
            stack.append(current)
        elif line == "}":
            stack.pop()
            current = stack[-1] if stack else None
        elif line.startswith("OFFSET") and current is not None:
            offsets[current] = [float(v) for v in line.split()[1:4]]
        elif line.startswith("CHANNELS"):
            parts = line.split()
            channels[current] = parts[2:2 + int(parts[1])]
    lines = motion.strip().splitlines()
    count = int(re.search(r"Frames:\s*(\d+)", lines[0]).group(1))
    frame_time = float(re.search(r"Frame Time:\s*([0-9.eE+-]+)", lines[1]).group(1))
    data = np.array([[float(v) for v in row.split()] for row in lines[2:2 + count]])
    offset = np.array(offsets) * CMU_UNIT_M                          # metros, ainda nos eixos do arquivo (a FK roda assim)
    return Mocap(name, 1.0 / frame_time, joints, parent, offset, channels, data)
