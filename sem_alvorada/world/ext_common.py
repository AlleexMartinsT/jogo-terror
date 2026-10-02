"""Ferramentas comuns do exterior e do portão da garagem.

Os construtores de geometria vêm do kit de props (`MeshBuilder`: caixas, torneados, lofts, varreduras), que
já entrega malhas conexas com normais por ângulo. Este módulo acrescenta o que só o mundo precisa: criar o
objeto na coleção certa, varrer perfis ao longo de curvas (calhas, trilhos, fios, galhos), catenárias e uma
amostragem determinística para espalhar coisas (grama, telhas, tijolos) sem depender da ordem do build.
"""
import math

import bpy
import numpy as np

from .. import conventions as C
from .. import craft
from ..props import kit
from . import materials as world_materials

# Sem chanfro, para o que é repetido aos milhares (telhas, tijolos, capim) ou já tem o contorno no perfil.
PROFILED = craft.Finish(bevel=0.0, smooth_angle=44.0)
SMOOTH = craft.Finish(bevel=0.0, smooth_angle=62.0)
FINE = craft.Finish(bevel=0.0015, bevel_segments=1, bevel_angle=35.0, smooth_angle=48.0)
TRIM = craft.Finish(bevel=0.004, bevel_segments=2, bevel_angle=32.0, smooth_angle=48.0)


def builder(name, finish=craft.STANDARD):
    """MeshBuilder do kit com a receita de acabamento escolhida."""
    m = kit.MeshBuilder(name)
    m.finish = finish
    return m


def emit(ctx, m, name=None, collection=C.COL_WORLD, collision=False, parent=None, location=(0.0, 0.0, 0.0), hide=False):
    """Cria o objeto de malha de `m` (se tiver geometria) na coleção e devolve-o."""
    if not m.tri_count:
        return None
    name = name or m.name
    obj = bpy.data.objects.new(name, m.to_mesh(name))
    obj.location = location
    ctx.link(obj, collection)
    if parent is not None:
        obj.parent = parent
    if collision:
        obj[C.P_COL] = 1
    if hide:
        obj.hide_render = obj.hide_viewport = True
    return obj


def start(ctx):
    """Alinha o kit com a qualidade do build (menos segmentos em 'low')."""
    kit.set_quality(ctx.quality)


def scaled(ctx, count, minimum=1):
    """Quantidade de elementos repetidos conforme a qualidade: 'low' corta pela metade, 'high' ganha 30%."""
    factor = {"low": 0.5, "medium": 1.0, "high": 1.3}.get(ctx.quality, 1.0)
    return max(minimum, int(count * factor))


def rng_for(ctx, label):
    """Gerador determinístico por rótulo: o resultado de uma peça não depende de quanto as outras sortearam."""
    import random
    return random.Random(f"{ctx.seed}:{label}")


def poly_out(m, points, mat, direction, uv=None):
    """Polígono com a normal virada para `direction` (o kit não corrige a ordem dos vértices de `poly`)."""
    pts = [np.asarray(p, float) for p in points]
    normal = np.cross(pts[1] - pts[0], pts[2] - pts[0])
    flip = np.dot(normal, direction) < 0
    pts = pts[::-1] if flip else pts
    if uv is not None and flip:
        uv = uv[::-1]
    m.poly([tuple(p) for p in pts], mat, uv=uv)


def register_material(name, build):
    """Registra um material de nós próprio no registro de `world.materials` (o kit o encontra por `matapi`)."""
    world_materials.register_builder(name, build)


# --------------------------------------------------------------------------------------------
# Varreduras
# --------------------------------------------------------------------------------------------
def _frames(path):
    """Tangentes e um par de vetores ortogonais por ponto (transporte paralelo, sem torção)."""
    path = np.asarray(path, float)
    tangent = np.gradient(path, axis=0)
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
    seed = np.array([0.0, 0.0, 1.0]) if abs(tangent[0, 2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    normal = np.cross(tangent[0], seed)
    normal /= np.linalg.norm(normal)
    normals, binormals = [], []
    for t in tangent:
        normal = normal - t * np.dot(normal, t)
        normal /= max(np.linalg.norm(normal), 1e-9)
        normals.append(normal.copy())
        binormals.append(np.cross(t, normal))
    return path, np.array(normals), np.array(binormals)


def sweep_circle(m, path, radius, mat, sides=6, radii=None, caps=True, smooth=True):
    """Tubo de seção circular ao longo de `path` [(x, y, z), ...]; `radii` (um por ponto) afunila.

    `caps`: True fecha as duas pontas, False deixa abertas e "end" fecha só a última (galho que nasce de outro)."""
    path, normals, binormals = _frames(path)
    rings = []
    for index, point in enumerate(path):
        r = radius if radii is None else radii[index]
        ring = []
        for k in range(sides):
            angle = 2 * math.pi * k / sides
            ring.append(tuple(point + r * (math.cos(angle) * normals[index] + math.sin(angle) * binormals[index])))
        rings.append(ring)
    m.loft(rings, mat, caps is True, bool(caps), smooth)


def sweep_profile(m, path, profile, mat, up=(0.0, 0.0, 1.0), caps=True, smooth=False):
    """Perfil 2D [(a, b), ...] varrido ao longo de `path`: `a` ao longo de `up` x tangente (lado) e `b` ao longo de `up`
    projetado (para cima). Serve para calhas, trilhos, beirais e molduras."""
    path = np.asarray(path, float)
    tangent = np.gradient(path, axis=0)
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
    up = np.asarray(up, float)
    rings = []
    for point, t in zip(path, tangent):
        side = np.cross(t, up)
        side /= max(np.linalg.norm(side), 1e-9)
        lift = np.cross(side, t)
        rings.append([tuple(point + side * a + lift * b) for a, b in profile])
    m.loft(rings, mat, caps, caps, smooth)


def arc(center, radius, start_deg, end_deg, plane="yz", steps=8):
    """Pontos de um arco de círculo no plano ('xy', 'yz' ou 'xz') ao redor de `center`."""
    points = []
    for k in range(steps + 1):
        angle = math.radians(start_deg + (end_deg - start_deg) * k / steps)
        a, b = radius * math.cos(angle), radius * math.sin(angle)
        offsets = {"xy": (a, b, 0.0), "yz": (0.0, a, b), "xz": (a, 0.0, b)}[plane]
        points.append(tuple(c + o for c, o in zip(center, offsets)))
    return points


def catenary(start, end, sag, steps=12):
    """Curva de fio frouxo entre dois pontos: parábola com flecha `sag` no meio."""
    start, end = np.asarray(start, float), np.asarray(end, float)
    points = []
    for k in range(steps + 1):
        t = k / steps
        point = start + (end - start) * t
        point[2] -= sag * 4.0 * t * (1.0 - t)
        points.append(tuple(point))
    return points


def helix(center, axis_from, axis_to, radius, turns, steps_per_turn=8):
    """Pontos de uma hélice ao longo do eixo X (mola de torção): de `axis_from` a `axis_to`."""
    count = int(turns * steps_per_turn)
    cy, cz = center
    return [(axis_from + (axis_to - axis_from) * k / count, cy + radius * math.cos(2 * math.pi * k / steps_per_turn),
             cz + radius * math.sin(2 * math.pi * k / steps_per_turn)) for k in range(count + 1)]
