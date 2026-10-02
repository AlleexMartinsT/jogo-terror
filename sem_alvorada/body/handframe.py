"""Referencial da mão no espaço da câmera, para quem posiciona as mãos (`ArmControl.set_target`).

Com `rotation_deg = (0, 0, 0)` a mão está NEUTRA: dedos apontando para a frente (-Z da câmera), palma para baixo
(-Y), polegar para o centro do corpo (-X na direita, +X na esquerda). `hold(obj)` usa o mesmo referencial:
com rotação zero os eixos do objeto coincidem com os da câmera, com origem no centro da palma.
"""
import math

from mathutils import Matrix, Vector

from . import skeleton as S


def hand_rotation(fingers, palm):
    """Euler XYZ em graus que leva a mão neutra a apontar os dedos para `fingers` e a palma para `palm`.

    Os dois vetores estão no espaço da câmera (X direita, Y cima, -Z frente) e não precisam ser unitários nem
    perpendiculares: `palm` é só uma dica de para onde a palma olha (a parte paralela aos dedos é descartada).
    Ex.: dedos para a frente com a palma para a esquerda: hand_rotation((0, 0, -1), (-1, 0, 0)).
    """
    f = Vector(fingers).normalized()
    p = Vector(palm)
    p = (p - f * p.dot(f)).normalized()
    target = Matrix((f, p, f.cross(p))).transposed()
    euler = (target @ S.NEUTRAL_HAND_CAM.inverted()).to_euler("XYZ")
    return tuple(math.degrees(a) for a in euler)


# --------------------------------------------------------------------------
# Empunhadura de lanterna (cilindro de 3,7 cm), calculada por otimização dos dedos contra o cano (ver README do corpo)
# --------------------------------------------------------------------------
GRIP_RADIUS = 0.0186
GRIP_ANGLE = math.radians(32.3)               # inclinação do cano na palma, a partir do eixo do polegar rumo aos dedos
GRIP_CENTER_API = Vector((0.0, -0.0238, -0.0150))      # eixo do cano em relação ao centro da palma, no referencial da mão


def grip_axis_api(side):
    """Direção do cano (da cauda para a lente) no referencial da mão. A direita e a esquerda são espelhadas em X."""
    sign = 1.0 if side == "R" else -1.0
    return Vector((-sign * math.cos(GRIP_ANGLE), 0.0, -math.sin(GRIP_ANGLE)))


def grip_rotation(side, barrel=(0.0, 0.05, -1.0), toward=None):
    """Euler XYZ (graus) de `set_target` para a mão segurar um cano apontado para `barrel` (espaço da câmera).

    `toward`: para que lado da mão o cano fica (a palma olha para ele). Padrão: para o centro do corpo
    (-X na mão direita, +X na esquerda)."""
    sign = 1.0 if side == "R" else -1.0
    toward = Vector(toward) if toward is not None else Vector((-sign, 0.0, 0.0))
    v1 = Vector(barrel).normalized()
    v2 = (toward - v1 * toward.dot(v1)).normalized()
    u1 = grip_axis_api(side)
    u2 = Vector((0.0, -1.0, 0.0))
    target = Matrix((v1, v2, v1.cross(v2))).transposed()
    source = Matrix((u1, u2, u1.cross(u2))).transposed()
    euler = (target @ source.inverted()).to_euler("XYZ")
    return tuple(math.degrees(a) for a in euler)


def grip_offset(side, local_axis=(0.0, 0.0, -1.0)):
    """Matrix 4x4 de `arm.hold(obj, ...)` para um objeto cujo cano corre ao longo de `local_axis` (lente para onde ele
    aponta) e cuja origem está no meio da pegada: o cano passa a coincidir com o eixo da empunhadura."""
    a = Vector(local_axis).normalized()
    b = grip_axis_api(side)
    rotation = a.rotation_difference(b).to_matrix().to_4x4()
    return Matrix.Translation(GRIP_CENTER_API) @ rotation
