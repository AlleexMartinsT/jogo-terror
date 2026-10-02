"""O amassado da frente: o carro bateu num poste do lado do passageiro.

Uma única função de peso (gaussiana em torno do ponto de impacto) vale para tudo: a chapa é deformada vértice
a vértice (`crush_mesh`) e as peças rígidas (farol, grade, para-choque) recebem o deslocamento do seu centro
(`part_offset`), então nada fica no lugar original enquanto a chapa afunda ao redor.
"""
import numpy as np

IMPACT = np.array([0.66, 2.24, 0.68])
REACH = np.array([0.42, 0.62, 0.56])         # alcance do amassado em x, y, z
PUSH_BACK = 0.30                             # quanto a ponta do para-choque recuou, no centro


def weight(points):
    """Peso 0..1 do amassado em cada ponto (N, 3): 1 no centro do impacto, cai suave até 0."""
    scaled = (np.asarray(points, float) - IMPACT) / REACH
    return np.exp(-np.sum(scaled * scaled, axis=-1))


def _wrinkles(points, strength):
    """Rugas diagonais da chapa que dobrou: seno ao longo de uma diagonal do capô, mais forte perto do centro."""
    phase = points[:, 1] * 24.0 - points[:, 0] * 11.0
    return strength * np.sin(phase) * np.cos(points[:, 0] * 17.0 + 1.3)


def displacement(points):
    """Deslocamento (N, 3) de cada ponto da carroceria."""
    points = np.asarray(points, float)
    w = weight(points)
    top = np.clip((points[:, 2] - 0.62) / 0.2, 0.0, 1.0)          # 0 no para-choque, 1 no capô
    out = np.zeros_like(points)
    out[:, 1] = -PUSH_BACK * w ** 1.2 * (0.55 + 0.45 * (1.0 - top))
    out[:, 0] = -0.05 * w * np.clip((points[:, 0] - 0.35) / 0.4, 0.0, 1.0)
    out[:, 2] = -0.07 * w * top + _wrinkles(points, 0.024) * w ** 1.3 * top - 0.020 * w * (1.0 - top)
    out[:, 1] += _wrinkles(points[:, [1, 0, 2]], 0.016) * w ** 1.5
    return out


def crush_mesh(mesh):
    """Aplica o amassado aos vértices de `mesh` (bpy.types.Mesh) no lugar."""
    coords = np.empty(len(mesh.vertices) * 3, np.float64)
    mesh.vertices.foreach_get("co", coords)
    points = coords.reshape(-1, 3)
    mesh.vertices.foreach_set("co", (points + displacement(points)).ravel())
    mesh.update()


def part_offset(x, y, z):
    """Deslocamento (dx, dy, dz) rígido de uma peça cujo centro está em (x, y, z)."""
    return tuple(float(v) for v in displacement(np.array([[x, y, z]]))[0])


def tilt(x, y, z):
    """Inclinação (graus) em torno de Z de uma peça no ponto: a ponta do para-choque girou para dentro."""
    return float(-24.0 * weight(np.array([[x, y, z]]))[0])
