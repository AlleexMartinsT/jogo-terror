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
