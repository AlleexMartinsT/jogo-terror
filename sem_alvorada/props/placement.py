"""Colocação de props na cena: cria o objeto, mede a pegada, gera o proxy de colisão.

Modos de colocação (`mode`):
- "furniture": apoiado no chão; precisa caber no cômodo e fora das zonas reservadas;
  ganha proxy de colisão em caixa.
- "flat":  tapetes e manchas rente ao chão; podem cruzar zonas reservadas, não colidem.
- "wall":  quadros, espelhos, armários suspensos, cortina pendurada na vara; não colidem.
- "decor": objetos pequenos sobre um móvel; não colidem.
"""
import functools
import math

import bpy
from mathutils import Euler, Matrix, Vector

from .. import conventions as C
from .. import layout

MODES = ("furniture", "flat", "wall", "decor")
EDGE_TOLERANCE = 0.01

P_MODE = "sa_prop_mode"
P_KIND = "sa_kind_prop"
P_ANCHOR = "sa_anchor"
P_FOOTPRINT = "sa_footprint"
P_TUCKED = "sa_tucked"


# ---------------------------------------------------------------------------
# Geometria da planta
# ---------------------------------------------------------------------------
def _wall_half_thickness(level, axis, pos, span_lo, span_hi):
    thickness = 0.0
    for piece in layout.wall_pieces(level):
        if piece.axis == axis and abs(piece.pos - pos) < 1e-6 and piece.a < span_hi and piece.b > span_lo:
            thickness = max(thickness, piece.thickness)
    return thickness / 2


@functools.lru_cache(maxsize=None)
def room_bounds(room_id):
    """Retângulo livre de um cômodo: a planta menos meia espessura de parede em cada lado (a planta é estática)."""
    room = layout.ROOMS[room_id]
    rc, level = room.rect, room.level
    return layout.Rect(
        rc.x0 + _wall_half_thickness(level, "y", rc.x0, rc.y0, rc.y1),
        rc.y0 + _wall_half_thickness(level, "x", rc.y0, rc.x0, rc.x1),
        rc.x1 - _wall_half_thickness(level, "y", rc.x1, rc.y0, rc.y1),
        rc.y1 - _wall_half_thickness(level, "x", rc.y1, rc.x0, rc.x1))


def floor_z(room_id):
    return layout.LEVEL_Z[layout.ROOMS[room_id].level]


def back_gap(room_id, x, y, yaw):
    """Distância de (x, y) até a parede que fica atrás de uma peça voltada para `yaw`."""
    bounds = room_bounds(room_id)
    fx, fy = C.yaw_dir(yaw)
    bx, by = -fx, -fy
    distances = []
    if bx > 0.5:
        distances.append((bounds.x1 - x) / bx)
    elif bx < -0.5:
        distances.append((bounds.x0 - x) / bx)
    if by > 0.5:
        distances.append((bounds.y1 - y) / by)
    elif by < -0.5:
        distances.append((bounds.y0 - y) / by)
    return min(distances) if distances else 0.0


def flush_center(room_id, x, y, yaw, depth):
    """Deslocamento local em Y do centro da malha para que o fundo encoste na parede."""
    return -(back_gap(room_id, x, y, yaw) - depth / 2)


def against_wall(room_id, wall, along, depth):
    """(x, y, yaw) de uma peça de `depth` encostada na parede `wall` ('N','S','E','W'), centrada em `along`."""
    b = room_bounds(room_id)
    if wall == "N":
        return along, b.y1 - depth / 2, math.pi
    if wall == "S":
        return along, b.y0 + depth / 2, 0.0
    if wall == "E":
        return b.x1 - depth / 2, along, math.pi / 2
    return b.x0 + depth / 2, along, -math.pi / 2


def world_footprint(lo, hi, x, y, yaw):
    """Caixa planar (Rect) no mundo de uma caixa local (lo, hi) girada por `yaw` em (x, y)."""
    cos_a, sin_a = math.cos(yaw), math.sin(yaw)
    xs, ys = [], []
    for px in (lo[0], hi[0]):
        for py in (lo[1], hi[1]):
            xs.append(x + px * cos_a - py * sin_a)
            ys.append(y + px * sin_a + py * cos_a)
    return layout.Rect(min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
# Criação de objetos
# ---------------------------------------------------------------------------
def unique_name(base):
    if base not in bpy.data.objects:
        return base
    index = 2
    while f"{base}_{index}" in bpy.data.objects:
        index += 1
    return f"{base}_{index}"


def make_collision_box(ctx, name, x, y, z, yaw, lo, hi):
    """Proxy `COL_<name>`: cubo de 8 vértices, só yaw, oculto, na coleção SA_Collision."""
    corners = [(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
               (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(C.N_COL + name)
    mesh.from_pydata(corners, [], faces)
    mesh.update()
    proxy = bpy.data.objects.new(unique_name(C.N_COL + name), mesh)
    proxy.location = (x, y, z)
    proxy.rotation_euler = (0.0, 0.0, yaw)
    # Objetos com hide_viewport não entram no depsgraph e ficariam com matrix_world = identidade;
    # gravar a matriz aqui deixa o proxy correto para quem ler matrix_world (BVH de colisão, IA).
    proxy.matrix_world = Matrix.Translation(Vector((x, y, z))) @ Euler((0.0, 0.0, yaw)).to_matrix().to_4x4()
    proxy[C.P_COL] = 1
    proxy.hide_render = True
    proxy.hide_viewport = True
    ctx.link(proxy, C.COL_COLLISION)
    return proxy


def place(ctx, builder, room, kind, x, y, yaw=0.0, z=None, *, mode="furniture", name=None,
          anchor=None, collision="bbox", collision_top=None, tucked=False, props=None):
    """Transforma o builder em objeto de `SA_Props` e devolve o objeto.

    - `collision`: "bbox" (caixa da malha inteira), None, ou lista de caixas locais
      `(x0, y0, z0, x1, y1, z1)` para peças em L ou com balanço que não deve bloquear.
    - `collision_top`: com "bbox", corta a caixa nesta altura. Móveis com enfeites em cima e um item
      coletável sobre o tampo precisam disso: o item não pode ficar dentro do volume do proxy, ou a
      linha de visada da interação bate no proxy antes de chegar nele.
    - `tucked`: cadeira enfiada sob a mesa (a pegada pode sobrepor a da mesa).
    """
    assert mode in MODES, mode
    obj_name = unique_name(name or f"{kind}_{room}")
    obj = bpy.data.objects.new(obj_name, builder.to_mesh(obj_name))
    base_z = floor_z(room) if z is None else z
    obj.location = (x, y, base_z)
    obj.rotation_euler = (0.0, 0.0, yaw)
    lo, hi = builder.bounds()
    footprint = world_footprint(lo, hi, x, y, yaw)
    obj[C.P_ROOM] = room
    obj[P_MODE] = mode
    obj[P_KIND] = kind
    obj[P_FOOTPRINT] = [footprint.x0, footprint.y0, footprint.x1, footprint.y1]
    obj["sa_height"] = hi[2]
    if anchor:
        obj[P_ANCHOR] = anchor
    if tucked:
        obj[P_TUCKED] = 1
    for key, value in (props or {}).items():
        obj[key] = value
    ctx.link(obj, C.COL_PROPS)
    if mode == "furniture" and collision:
        top = hi[2] if collision_top is None else collision_top
        boxes = [(lo[0], lo[1], lo[2], hi[0], hi[1], top)] if collision == "bbox" else collision
        for index, (x0, y0, z0, x1, y1, z1) in enumerate(boxes):
            suffix = "" if len(boxes) == 1 else f"_{index + 1}"
            make_collision_box(ctx, (anchor or obj_name) + suffix, x, y, base_z, yaw,
                               (x0, y0, z0), (x1, y1, z1))
    return obj


def prop_objects(scene):
    """Objetos de mobília/decoração já colocados (têm o modo gravado)."""
    return [ob for ob in scene.objects if P_MODE in ob]


# ---------------------------------------------------------------------------
# Validação da planta (usada pelo build de desenvolvimento e pelos testes)
# ---------------------------------------------------------------------------
def _footprint_of(obj):
    return layout.Rect(*obj[P_FOOTPRINT])


def validate_layout(scene, overlap_tolerance=0.03):
    """Lista de problemas: fora do cômodo, dentro de zona reservada, móveis que se atravessam."""
    problems = []
    furniture = []
    for obj in prop_objects(scene):
        room = layout.ROOMS[obj[C.P_ROOM]]
        footprint = _footprint_of(obj)
        bounds = room_bounds(room.id)
        if obj[P_MODE] != "wall":
            inflated = bounds.inflate(EDGE_TOLERANCE)
            if not (inflated.x0 <= footprint.x0 and footprint.x1 <= inflated.x1
                    and inflated.y0 <= footprint.y0 and footprint.y1 <= inflated.y1):
                problems.append(f"{obj.name}: sai de {room.id} {tuple(round(v, 2) for v in obj[P_FOOTPRINT])}")
        if obj[P_MODE] == "furniture":
            shrunk = footprint.inflate(-0.01)
            for zone in layout.reserved_zones(room.level):
                if shrunk.overlaps(zone):
                    problems.append(f"{obj.name}: invade zona reservada {zone.as_tuple()}")
                    break
            furniture.append(obj)
    for i, first in enumerate(furniture):
        for second in furniture[i + 1:]:
            if first[C.P_ROOM] != second[C.P_ROOM] or first.get(P_TUCKED) or second.get(P_TUCKED):
                continue
            if _footprint_of(first).inflate(-overlap_tolerance).overlaps(_footprint_of(second)):
                problems.append(f"{first.name} atravessa {second.name}")
    return problems
