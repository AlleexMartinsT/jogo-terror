"""Cortinas e persianas das janelas.

As cortinas são tecido simulado pelo próprio Blender (`craft.drape`): a linha de cima é presa ao varão
em posições mais juntas que as do tecido em repouso (o "franzido"), o resto cai por gravidade e se enruga
em pregas. Nenhuma prega é modelada à mão: o que está na tela é o pano assentado contra a parede, o
peitoril e o piso. As persianas, em compensação, são réguas modeladas uma a uma (não há física a ganhar).

Tudo de uma janela vai num único objeto `Curtain_<id>`, filho de `Window_<id>`.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from .. import conventions as C
from .. import craft
from .. import layout
from .modelkit import PROFILED, ModelBuilder, detail

FULLNESS = 2.0               # tecido em repouso = 2x a largura franzida no varão
CELL = 0.065                 # lado da célula da malha de tecido (m)
ROD_OFFSET = 0.105           # distância do varão à face da parede
ROD_RISE = 0.17              # varão acima da verga
ROD_RADIUS = 0.0125
PLEAT_PERIOD = 0.11          # largura de uma prega, medida no varão
PLEAT_DEPTH = 0.045
CURTAIN_MATERIALS = {"w_kids_s": "curtain_kids", "w_kids_w": "curtain_kids", "w_master_n": "curtain_green",
                     "w_master_w": "curtain_green", "w_dining_s": "curtain_green"}


def build(ctx, frame, style):
    """Cortina ou persiana da janela, como objeto filho. Devolve None se a janela fica nua."""
    if style.covering == "none":
        return None
    builder = ModelBuilder(f"Curtain_{frame.op.id}", PROFILED)
    rng = random.Random(f"dressing:{frame.op.id}")
    cloth = []
    if style.covering == "blinds":
        _blinds(builder, frame, style, rng)
    else:
        _rod(ctx, builder, frame, style, rng)
        cloth = _panels(ctx, frame, style, rng)
    mesh = builder.build_mesh(frame.center, ctx.quality) if builder._polygons else None
    meshes = [m for m in [mesh] + cloth if m is not None]
    joined = craft.join_meshes(meshes, f"Curtain_{frame.op.id}")
    for part in meshes:
        if part.users == 0 and part is not joined:
            bpy.data.meshes.remove(part)
    obj = bpy.data.objects.new(f"Curtain_{frame.op.id}", joined)
    obj.location = frame.center
    ctx.link(obj, C.COL_WORLD)
    return obj


# --------------------------------------------------------------------------
# Varão, suportes e argolas
# --------------------------------------------------------------------------
def _rod_geometry(frame, style):
    """(u0, u1, s, z) do varão. Cortina curta (café): dentro do vão, na altura do meio. Longa: sobre a verga."""
    op = frame.op
    if style.length == "short":
        return op.a + 0.01, op.b - 0.01, -(frame.half - 0.03), frame.z0 + op.height * 0.58
    reach = 0.34 if style.covering == "curtain_open" else 0.20
    return op.a - reach, op.b + reach, -(frame.half + ROD_OFFSET), frame.z1 + ROD_RISE


def _rod(ctx, builder, frame, style, rng):
    u0, u1, s, z = _rod_geometry(frame, style)
    material = "brass_worn" if rng.random() < 0.5 else "wood_dark"
    sides = detail(ctx, 10)
    start, end = frame.point(u0, s, z), frame.point(u1, s, z)
    builder.tube(start, end, ROD_RADIUS, material, sides)
    for u, sign in ((u0, -1), (u1, 1)):
        _finial(builder, frame, u, s, z, sign, material, sides)
        _bracket(builder, frame, u + sign * -0.07, s, z, material, sides)
    if style.length == "long":
        for span_start, span_end in _panel_spans(frame, style):
            _rings(builder, frame, span_start, span_end, s, z, material)


def _rings(builder, frame, u0, u1, s, z, material):
    """Argolas ao longo do trecho do varão que um painel ocupa; o tecido pende delas."""
    count = max(3, round((u1 - u0) / 0.095))
    turn = {"ry": 90} if frame.op.axis == "x" else {"rx": -90}
    for k in range(count):
        u = u0 + (k + 0.5) * (u1 - u0) / count
        with builder.at(*frame.point(u, s, z), **turn):
            builder.torus(0.0215, 0.0032, material, 10, 4)


def _finial(builder, frame, u, s, z, sign, material, sides):
    profile = [(0.0, 0.0), (0.0155, 0.0), (0.011, 0.012), (0.016, 0.022), (0.027, 0.035), (0.028, 0.048),
               (0.021, 0.060), (0.0, 0.0635)]
    turn = {"ry": 90 * sign} if frame.op.axis == "x" else {"rx": -90 * sign}
    with builder.at(*frame.point(u, s, z), **turn):
        builder.lathe(profile, material, sides)


def _bracket(builder, frame, u, s, z, material, sides):
    """Suporte em L: haste até a parede e rosácea."""
    wall_s = -frame.half
    builder.tube(frame.point(u, wall_s, z), frame.point(u, s, z), 0.008, material, sides)
    builder.tube(frame.point(u, wall_s - 0.004, z), frame.point(u, wall_s + 0.012, z), 0.026, material, sides)


# --------------------------------------------------------------------------
# Cortinas: tecido simulado
# --------------------------------------------------------------------------
def _panel_spans(frame, style):
    """Faixas (u0, u1) de varão que cada painel ocupa, de fora para dentro."""
    op = frame.op
    if style.length == "short":
        return [(op.a + 0.02, op.b - 0.02)]
    if style.covering == "curtain_closed":
        mid = (op.a + op.b) / 2
        return [(op.a - 0.14, mid + 0.07), (mid - 0.07, op.b + 0.14)]
    return [(op.a - 0.34, op.a + 0.26), (op.b - 0.26, op.b + 0.34)]


_PANEL_CACHE = {"owner": None, "panels": {}}


def _panels(ctx, frame, style, rng):
    """Os painéis da janela. A simulação é cara, então painéis de janelas de mesmo tamanho e tipo reaproveitam
    o mesmo pano (guardado em coordenadas da janela); duas variantes por forma quebram a repetição."""
    if _PANEL_CACHE["owner"] is not ctx:
        _PANEL_CACHE.update(owner=ctx, panels={})
    meshes = []
    material = CURTAIN_MATERIALS.get(frame.op.id, "curtain")
    variant = sum(map(ord, frame.op.id)) % 2
    for side, (u0, u1) in enumerate(_panel_spans(frame, style)):
        key = (style.covering, style.length, round(frame.op.width, 3), round(frame.op.height, 3), side, variant)
        if key not in _PANEL_CACHE["panels"]:
            _PANEL_CACHE["panels"][key] = _to_local(frame, _simulate(frame, style, u0, u1, random.Random(str(key))))
        mesh = _from_local(frame, _PANEL_CACHE["panels"][key], material)
        if style.torn and side == 0:
            mesh = _tear(mesh, frame, u0, u1)
        meshes.append(mesh)
    return meshes


def _panel_extent(frame, style):
    """(s do varão, z do alto do tecido, z da barra)."""
    _, _, s, z_rod = _rod_geometry(frame, style)
    bottom = frame.z0 - 0.03 if style.length == "short" else layout.LEVEL_Z[frame.op.level] + 0.045
    return s, z_rod - 0.025, bottom


def _simulate(frame, style, u0, u1, rng):
    """Malha plana pré-franzida e pinada no varão, que o Blender deixa cair e se enrugar. Devolve a malha em mundo."""
    s_rod, top, bottom = _panel_extent(frame, style)
    gathered = u1 - u0
    rest = gathered * FULLNESS
    columns = max(8, round(rest / CELL))
    rows = max(6, round((top - bottom) / CELL))
    mesh = craft.cloth_grid(rest, top - bottom, columns, rows)
    phases = [rng.random() * math.tau for _ in range(3)]
    for vertex in mesh.vertices:
        i, j = round(vertex.co.x / rest * columns), round(vertex.co.y / (top - bottom) * rows)
        t = j / rows
        spread = _smoothstep(0.0, 0.55, t)
        gathered_u = u0 + gathered * i / columns
        flared_u = (u0 + u1) / 2 + (i / columns - 0.5) * gathered * (1.0 + 0.55 * spread)
        u = gathered_u * (1 - spread) + flared_u * spread
        x = gathered * i / columns
        wave = (0.7 * math.sin(math.tau * x / PLEAT_PERIOD + phases[0])
                + 0.3 * math.sin(math.tau * x / (PLEAT_PERIOD * 1.9) + phases[1]))
        wave *= 1.0 + 0.35 * math.sin(x * 13.0 + phases[2])
        vertex.co = Vector(frame.point(u, s_rod - PLEAT_DEPTH * (1.0 - 0.45 * t) * wave, top - t * (top - bottom)))
    _pin_top_row(mesh, columns)
    colliders = _colliders(frame)
    try:
        return craft.drape(mesh, colliders, frames=52, mass=0.3, stiffness=18.0, bending=3.5, pin_group="pin",
                           thickness=0.014, subsurf=0, settle_frames=12)
    finally:
        for proxy in colliders:
            bpy.data.objects.remove(proxy)


def _to_local(frame, mesh):
    """Guarda o pano em coordenadas da janela (u relativo ao centro, s, z relativo ao piso) para reaproveitá-lo."""
    op = frame.op
    centre_u = (op.a + op.b) / 2
    floor = layout.LEVEL_Z[op.level]
    points = []
    for vertex in mesh.vertices:
        u, n = (vertex.co.x, vertex.co.y) if op.axis == "x" else (vertex.co.y, vertex.co.x)
        points.append((u - centre_u, (n - op.pos) * frame.outward, vertex.co.z - floor))
    polygons = [tuple(p.vertices) for p in mesh.polygons]
    bpy.data.meshes.remove(mesh)
    return points, polygons


def _from_local(frame, stored, material):
    op = frame.op
    centre_u = (op.a + op.b) / 2
    floor = layout.LEVEL_Z[op.level]
    centre = Vector(frame.center)
    points, polygons = stored
    mesh = bpy.data.meshes.new(f"cloth_{op.id}")
    mesh.from_pydata([tuple(Vector(frame.point(centre_u + du, s, floor + dz)) - centre) for du, s, dz in points],
                     [], polygons)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    mesh.update()
    mesh.materials.append(_cloth_material(material))
    return mesh


def _smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _pin_top_row(mesh, columns):
    """Grupo de vértices `pin` com a linha de cima (os primeiros vértices da grade) presa ao varão."""
    holder = bpy.data.objects.new("_pin_holder", mesh)
    bpy.context.scene.collection.objects.link(holder)
    holder.vertex_groups.new(name="pin").add(list(range(columns + 1)), 1.0, "REPLACE")
    bpy.context.scene.collection.objects.unlink(holder)
    bpy.data.objects.remove(holder)


def _colliders(frame):
    """Caixas temporárias onde o pano pode encostar: parede ao redor do vão, folhas, peitoril, avental e piso."""
    op, half = frame.op, frame.half
    floor = layout.LEVEL_Z[op.level]
    reach = 1.2
    boxes = [
        (op.a - reach, op.a, -half, half, floor - 0.2, floor + 3.4),              # parede à esquerda
        (op.b, op.b + reach, -half, half, floor - 0.2, floor + 3.4),              # à direita
        (op.a, op.b, -half, half, frame.z1, floor + 3.4),                         # acima do vão
        (op.a, op.b, -half, half, floor - 0.2, frame.z0),                         # abaixo do vão
        (op.a, op.b, -0.045, 0.045, frame.z0, frame.z1),                          # folhas de vidro
        (op.a - 0.12, op.b + 0.12, -half - 0.06, -half, frame.z0, frame.z0 + 0.03),   # peitoril
        (op.a - 0.10, op.b + 0.10, -half - 0.02, -half, frame.z0 - 0.075, frame.z0),  # avental
        (op.a - reach, op.b + reach, -2.0, 2.0, floor - 0.2, floor),              # piso
    ]
    return [_box_object([frame.point(u, s, z) for z in (z0, z1) for u, s in ((u0, s0), (u1, s0), (u1, s1), (u0, s1))])
            for u0, u1, s0, s1, z0, z1 in boxes]


def _box_object(corners):
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new("_craft_proxy")
    mesh.from_pydata(corners, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("_craft_proxy", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _cloth_material(name):
    from . import materials
    return materials.material_for(name)


def _tear(mesh, frame, u0, u1):
    """Rasga o painel: um triângulo irregular de faces some, com o vértice no alto e a base na barra."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    centre = Vector(frame.center)
    low = min(v.co.z for v in bm.verts)
    high = max(v.co.z for v in bm.verts)
    axis = 0 if frame.op.axis == "x" else 1
    doomed = []
    for face in bm.faces:
        centroid = face.calc_center_median()
        across = (centroid[axis] + centre[axis] - u0) / (u1 - u0)
        height = (centroid.z - low) / (high - low)
        reach = 0.62 * (1.0 - abs(across - 0.68) / 0.17) + 0.06 * math.sin(centroid.z * 37.0 + across * 11.0)
        if abs(across - 0.68) < 0.17 and height < reach:
            doomed.append(face)
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


# --------------------------------------------------------------------------
# Persianas
# --------------------------------------------------------------------------
def _blinds(builder, frame, style, rng):
    """Persiana veneziana de réguas: cabeçote, réguas, fitas e barra inferior, com uma ou outra régua torta."""
    op = frame.op
    s_front = -(frame.half + 0.055)
    u0, u1 = op.a - 0.05, op.b + 0.05
    top = frame.z1 + 0.115
    bottom = frame.z1 - (frame.z1 - frame.z0) * style.blinds_drop + 0.0
    bottom = max(bottom, frame.z0 - 0.04)
    frame.box(builder, u0, u1, s_front - 0.03, s_front + 0.03, top - 0.045, top, "blinds_plastic")
    count = max(4, int((top - 0.045 - bottom) / 0.028))
    step = (top - 0.045 - bottom) / count
    for k in range(count):
        z = top - 0.05 - k * step
        droop = style.crooked * (k / count)
        broken = rng.random() < 0.05 and k > count * 0.3
        _blind_slat(builder, frame, u0 + 0.01, u1 - 0.01, s_front, z, droop, 0.012 if broken else 0.0)
    droop = style.crooked
    frame.box(builder, u0, u1, s_front - 0.012, s_front + 0.012, bottom - 0.014 - droop, bottom - droop * 0.2,
              "blinds_plastic")
    for u in (u0 + 0.12, u1 - 0.12):
        frame.box(builder, u - 0.0025, u + 0.0025, s_front - 0.003, s_front + 0.003, bottom, top - 0.045, "rope_cotton")


def _blind_slat(builder, frame, u0, u1, s, z, droop, sag):
    """Régua curva (arco de 2,5 cm) levemente inclinada; `droop` abaixa a ponta de dentro, `sag` uma régua quebrada."""
    section = [(s - 0.0125, z), (s, z + 0.003), (s + 0.0125, z - 0.003), (s + 0.0125, z - 0.0035),
               (s, z - 0.0005), (s - 0.0125, z - 0.0005)]
    left = [frame.point(u0, ss, zz - droop - sag) for ss, zz in section]
    right = [frame.point(u1, ss, zz - droop * 0.1) for ss, zz in section]
    builder.loft([left, right], "blinds_plastic")
