"""Escada principal: degraus com nariz arredondado, espelhos, longarina fechada, corrimão torneado e passadeira.

A altura do topo de cada degrau é a do layout (`layout.stairs_height`): o degrau i (1..14) tem topo em
`i * rise` entre `y0 + (i-1) * profundidade` e `y0 + i * profundidade`. O nariz sobra 2,5 cm além do espelho
(o espelho fica recuado), de modo que a superfície de pisar não muda um milímetro.

Objetos: `Stairs_Main` (degraus, espelhos, longarina: colide), `Stairs_Trim` (rodapé em degraus e o nariz do
patamar), `Stairs_Railing` (poste, balaústres, corrimão e guarda-corpo do furo) e `Stairs_Runner` (a
passadeira, com varões de latão).
"""
import math

import bpy
from mathutils import Vector

from .. import conventions as C
from .. import craft, layout
from . import materials, moldings
from .meshkit import MeshBuilder
from .modelkit import PROFILED, ModelBuilder, build_combined, detail

WALL_FACE_X = 5.075          # face da parede oeste do hall (parede de 0,15 m em x=5)
SEAL_INTO_WALL = 0.02        # o degrau entra na parede para não deixar fresta
NOSE = 0.025                 # balanço do nariz do degrau sobre o espelho
TREAD_THICK = 0.032
RISER_THICK = 0.019
NOSE_RADIUS = 0.014
STRINGER_THICK = 0.025
RAIL_HEIGHT = 0.9
RAIL_X = 6.095               # eixo do corrimão e dos balaústres da escada (sobre os degraus)
GUARD_X = 6.145              # eixo do guarda-corpo do furo (sobre a laje, fora do furo)
EASE_LENGTH = 0.36           # comprimento da curva de arranque do corrimão
BALUSTER = 0.032
COLLISION_THICKNESS = 0.06
RUNNER_X = (5.24, 5.94)
RUNNER_THICK = 0.010
ROD_RADIUS = 0.0065


def build(ctx):
    _build_steps(ctx)
    _build_trim(ctx)
    _build_railings(ctx)
    _build_runner(ctx)
    _build_rail_colliders(ctx)
    ctx.log(f"escada: {layout.STAIRS.treads} degraus, longarina, corrimão torneado e passadeira")


def _tread_top(stairs, i):
    return stairs.z0 + i * stairs.rise


def _tread_y(stairs, i):
    """y da frente (nariz) do degrau i: o início dele no layout."""
    return stairs.y0 + (i - 1) * stairs.tread_depth


# --------------------------------------------------------------------------
# Degraus, espelhos e longarina
# --------------------------------------------------------------------------
def _tread_profile(depth):
    """Corte transversal do degrau: nariz arredondado na frente, fundo reto, [(y, z)] com z=0 no topo."""
    arc = [(NOSE_RADIUS * (1 - math.cos(a)), -NOSE_RADIUS + NOSE_RADIUS * math.sin(a))
           for a in (math.pi / 2 * k / 5 for k in range(6))]
    return [(0.0, -TREAD_THICK)] + arc + [(depth, 0.0), (depth, -TREAD_THICK)]


def _build_steps(ctx):
    stairs = layout.STAIRS
    x_wall, x_east = WALL_FACE_X - SEAL_INTO_WALL, stairs.x1
    treads = ModelBuilder("Stairs_Main", PROFILED)
    for i in range(1, stairs.treads + 1):
        y, top = _tread_y(stairs, i), _tread_top(stairs, i)
        depth = stairs.tread_depth + (NOSE if i < stairs.treads else 0.0)
        treads.prism(_tread_profile(depth), (x_wall, y, top), (x_east, y, top), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
                     "stairs_wood")
        riser_y = y + NOSE
        treads.box(x_wall, riser_y, _tread_top(stairs, i - 1), x_east, riser_y + RISER_THICK, top - 0.012,
                   "stairs_riser", skip=("-z", "+z"))
    _stringer(treads, stairs)
    obj = treads.build(ctx, C.COL_WORLD, collision=True)
    obj[C.P_SURFACE] = "stairs"


def _stringer_outline(stairs):
    """Contorno (y, z) da longarina fechada: o fundo reto e o topo em degraus, na linha dos narizes."""
    outline = [(stairs.y0, 0.0), (stairs.y1, 0.0), (stairs.y1, _tread_top(stairs, stairs.treads))]
    for i in range(stairs.treads, 0, -1):
        outline.append((_tread_y(stairs, i), _tread_top(stairs, i)))
        if i > 1:
            outline.append((_tread_y(stairs, i), _tread_top(stairs, i - 1)))
    return outline


def _stringer(builder, stairs):
    """Painel fechado do lado leste (a parede do vão sob a escada), no mesmo papel de parede do hall."""
    x0, x1 = stairs.x1, stairs.x1 + STRINGER_THICK
    outline = _stringer_outline(stairs)
    builder.loft([[(x0, y, z) for y, z in outline], [(x1, y, z) for y, z in outline]], "wall_wallpaper")
    moldings.baseboard_run(builder, (x1, stairs.y0, 0.0), (x1, stairs.y1, 0.0), (1.0, 0.0, 0.0), "trim_white")


def _build_trim(ctx):
    """Rodapé em degraus junto à parede e o nariz do patamar no encontro com o piso de cima."""
    stairs = layout.STAIRS
    builder = ModelBuilder("Stairs_Trim", PROFILED)
    for i in range(1, stairs.treads + 1):
        start = _tread_y(stairs, i) + NOSE
        end = _tread_y(stairs, i) + stairs.tread_depth + NOSE
        moldings.baseboard_run(builder, (WALL_FACE_X, start, _tread_top(stairs, i)),
                               (WALL_FACE_X, min(end, stairs.y1), _tread_top(stairs, i)), (1.0, 0.0, 0.0),
                               "trim_white")
    landing = layout.LEVEL_Z[1]
    builder.prism(_tread_profile(NOSE), (WALL_FACE_X, stairs.y1 - NOSE, landing),
                  (stairs.x1, stairs.y1 - NOSE, landing), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), "stairs_wood")
    builder.build(ctx, C.COL_WORLD)


# --------------------------------------------------------------------------
# Corrimão, poste de arranque e guarda-corpo
# --------------------------------------------------------------------------
def _pitch_z(stairs, y):
    """Eixo do corrimão sobre a linha dos narizes, RAIL_HEIGHT acima (a inclinação da escada)."""
    return stairs.rise + RAIL_HEIGHT + stairs.rise / stairs.tread_depth * (y - stairs.y0)


def _newel_y(stairs):
    return stairs.y0 + 0.03


def rail_z(stairs, y):
    """Altura do eixo do corrimão em y: curva de arranque (parábola) até encontrar a linha da escada."""
    slope = stairs.rise / stairs.tread_depth
    y_newel = _newel_y(stairs)
    y_tangent = y_newel + EASE_LENGTH
    if y >= y_tangent:
        return _pitch_z(stairs, y)
    z_newel = _pitch_z(stairs, y_tangent) - slope * EASE_LENGTH / 2
    return z_newel + slope * (y - y_newel) ** 2 / (2 * EASE_LENGTH)


RAIL_PROFILE = [(-0.018, -0.027), (0.018, -0.027), (0.027, -0.018), (0.033, -0.004), (0.031, 0.012),
                (0.024, 0.022), (0.012, 0.028), (-0.012, 0.028), (-0.024, 0.022), (-0.031, 0.012),
                (-0.033, -0.004), (-0.027, -0.018)]
RAIL_HALF_DEPTH = 0.027


def _baluster_profile(length):
    """Perfil (raio, altura) de um balaústre torneado de `length` m: bloco em baixo, vaso, haste e bloco em cima."""
    block = 0.07
    top = length - block
    return [(0.016, 0.0), (0.016, block), (0.0105, block + 0.008), (0.0165, block + 0.045), (0.0095, block + 0.085),
            (0.0095, block + 0.11), (0.0125, block + 0.13), (0.0090, block + 0.15), (0.0090, top - 0.14),
            (0.0160, top - 0.085), (0.0100, top - 0.04), (0.0105, top - 0.01), (0.016, top), (0.016, length)]


NEWEL_CAP = [(0.052, 0.0), (0.056, 0.014), (0.050, 0.03), (0.034, 0.05), (0.028, 0.07), (0.034, 0.095),
             (0.040, 0.12), (0.036, 0.15), (0.022, 0.175), (0.0, 0.185)]


def _newel(builder, x, y, z0, z_rail, sides):
    """Poste torneado: base quadrada, fuste com anéis e tampa em ogiva, que sobe 21 cm acima do eixo do corrimão."""
    shaft_base = z0 + 0.16
    shaft_top = z_rail + 0.03
    shaft = shaft_top - shaft_base
    builder.box(x - 0.058, y - 0.058, z0, x + 0.058, y + 0.058, shaft_base, "wood_dark")
    profile = [(0.046, 0.0), (0.040, 0.045), (0.040, 0.17), (0.050, 0.21), (0.052, 0.26), (0.050, 0.31),
               (0.042, 0.35), (0.038, 0.39), (0.038, shaft - 0.21), (0.046, shaft - 0.17), (0.050, shaft - 0.13),
               (0.050, shaft - 0.06), (0.052, shaft)]
    with builder.at(x, y, shaft_base):
        builder.lathe(profile, "wood_dark", sides, caps=(True, False))
    with builder.at(x, y, shaft_top):
        builder.lathe(NEWEL_CAP, "wood_dark", sides, caps=(False, True))


def _baluster(builder, x, y, z_base, z_top, sides):
    length = z_top - z_base
    with builder.at(x, y, z_base):
        builder.lathe(_baluster_profile(length), "wood_dark", sides)


def _build_railings(ctx):
    stairs = layout.STAIRS
    turned, rails = ModelBuilder("_rail_turned", PROFILED), ModelBuilder("_rail_runs", PROFILED)
    sides = detail(ctx, 8)
    _stair_rail(turned, rails, stairs, sides)
    _guard(turned, rails, stairs, sides)
    build_combined(ctx, C.COL_WORLD, "Stairs_Railing", [turned, rails])


def _stair_rail(turned, rails, stairs, sides):
    y_newel = _newel_y(stairs)
    y_top = stairs.y1 + 0.01
    _newel(turned, RAIL_X, y_newel, 0.0, rail_z(stairs, y_newel) + 0.16, sides)
    for i in range(1, stairs.treads + 1):
        for offset in (0.07, 0.22):
            y = _tread_y(stairs, i) + offset
            if y < y_newel + 0.07 or y > y_top - 0.06:
                continue
            _baluster(turned, RAIL_X, y, _tread_top(stairs, i), rail_z(stairs, y) - RAIL_HALF_DEPTH, sides)
    ys = [y_newel + EASE_LENGTH * k / 6 for k in range(7)] + [y_top]
    points = [(RAIL_X, y, rail_z(stairs, y)) for y in ys]
    depths = []
    for a, b in zip(points, points[1:]):
        direction = Vector(b) - Vector(a)
        direction.normalize()
        depths.append((0.0, -direction.z, direction.y))
    rails.sweep(RAIL_PROFILE, points, [(1.0, 0.0, 0.0)] * (len(points) - 1), depths, "wood_dark")


def _guard(turned, rails, stairs, sides):
    """Guarda-corpo do andar de cima ao redor do furo: lado leste e lado sul, sobre a laje."""
    floor = layout.LEVEL_Z[1]
    top = floor + RAIL_HEIGHT
    y_south, y_north = stairs.y0 - 0.03, stairs.y1 + 0.03
    _newel(turned, GUARD_X, y_north, floor, top + 0.16, sides)
    _newel(turned, GUARD_X, y_south, floor, top + 0.16, sides)
    east = [(GUARD_X, y_north, top), (GUARD_X, y_south, top)]
    rails.sweep(RAIL_PROFILE, east, [(1.0, 0.0, 0.0)], (0.0, 0.0, 1.0), "wood_dark")
    south = [(GUARD_X, y_south, top), (WALL_FACE_X, y_south, top)]
    rails.sweep(RAIL_PROFILE, south, [(0.0, 1.0, 0.0)], (0.0, 0.0, 1.0), "wood_dark")
    for y in _spaced(y_south + 0.07, y_north - 0.07, 0.115):
        _baluster(turned, GUARD_X, y, floor, top - RAIL_HALF_DEPTH, sides)
    for x in _spaced(WALL_FACE_X + 0.04, GUARD_X - 0.07, 0.115):
        _baluster(turned, x, y_south, floor, top - RAIL_HALF_DEPTH, sides)


def _spaced(start, end, step):
    count = max(1, round((end - start) / step))
    return [start + (end - start) * (i + 0.5) / count for i in range(count)]


# --------------------------------------------------------------------------
# Passadeira de carpete com varões de latão
# --------------------------------------------------------------------------
def _runner_path(stairs):
    """Linha (y, z) da superfície da passadeira, de baixo para cima: sobe cada espelho, contorna o nariz e cobre
    o piso. Devolve também os índices dos pontos de dobra (pé de cada espelho), onde ficam os varões."""
    path, creases = [(stairs.y0 - 0.03, 0.0)], []
    for i in range(1, stairs.treads + 1):
        front, top = _tread_y(stairs, i), _tread_top(stairs, i)
        creases.append(len(path))
        path.append((front + NOSE, _tread_top(stairs, i - 1)))
        path.extend(_nose_arc(front, top))
    top_floor = layout.LEVEL_Z[1]
    creases.append(len(path))
    path.append((stairs.y1, _tread_top(stairs, stairs.treads)))
    path.extend(_nose_arc(stairs.y1 - NOSE, top_floor))
    path.append((stairs.y1 + 0.03, top_floor))
    return path, creases


def _nose_arc(front, top):
    """Pontos da passadeira contornando o nariz arredondado que começa em `front`, com topo em `top`."""
    points = [(front - 0.001, top - NOSE_RADIUS)]
    for k in range(1, 5):
        angle = math.pi / 2 * k / 4
        points.append((front + NOSE_RADIUS * (1 - math.cos(angle)), top - NOSE_RADIUS + NOSE_RADIUS * math.sin(angle)))
    return points


def _resample(path, creases, spacing):
    """Reamostra a polilinha a cada `spacing` m mantendo as quinas; devolve também onde as dobras caíram."""
    out, mapped = [path[0]], {}
    for index, (a, b) in enumerate(zip(path, path[1:])):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(1, round(length / spacing))
        out.extend((a[0] + (b[0] - a[0]) * k / steps, a[1] + (b[1] - a[1]) * k / steps) for k in range(1, steps + 1))
        mapped[index + 1] = len(out) - 1
    mapped[0] = 0
    return out, [mapped[i] for i in creases]


def _normals(points):
    """Normal (ny, nz) para cima de cada ponto da linha, pela média dos dois segmentos vizinhos."""
    normals = []
    for index in range(len(points)):
        a = points[max(0, index - 1)]
        b = points[min(len(points) - 1, index + 1)]
        ty, tz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(ty, tz) or 1.0
        normals.append((-tz / length, ty / length))
    return normals


RUNNER_COLUMNS = 14
RUNNER_LIFT = 0.016          # a passadeira começa acima dos degraus e o pano assenta sobre eles


def _build_runner(ctx):
    """Passadeira: pano simulado (`craft.drape`) preso nos varões, que assenta sobre os degraus."""
    stairs = layout.STAIRS
    path, creases = _runner_path(stairs)
    points, pinned_rows = _resample(path, creases, 0.045)
    normals = _normals(points)
    x0, x1 = RUNNER_X
    vertices, uvs, travelled = [], [], 0.0
    for index, ((y, z), (ny, nz)) in enumerate(zip(points, normals)):
        if index:
            travelled += math.hypot(y - points[index - 1][0], z - points[index - 1][1])
        for c in range(RUNNER_COLUMNS + 1):
            x = x0 + (x1 - x0) * c / RUNNER_COLUMNS
            vertices.append((x, y + ny * RUNNER_LIFT, z + nz * RUNNER_LIFT))
            uvs.append((x - x0, travelled))
    stride = RUNNER_COLUMNS + 1
    faces = [(r * stride + c, r * stride + c + 1, (r + 1) * stride + c + 1, (r + 1) * stride + c)
             for r in range(len(points) - 1) for c in range(RUNNER_COLUMNS)]
    mesh = _runner_mesh(vertices, faces, uvs, pinned_rows, stride)
    mesh = _settle_runner(mesh)
    _add_wrinkles(mesh, uvs)
    obj = _object(ctx, "Stairs_Runner", mesh)
    _runner_rods(ctx, stairs)
    return obj


def _runner_mesh(vertices, faces, uvs, pinned_rows, stride):
    mesh = bpy.data.meshes.new("Stairs_Runner")
    mesh.from_pydata(vertices, [], faces)
    layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index, vertex_index in zip(polygon.loop_indices, polygon.vertices):
            layer.data[loop_index].uv = uvs[vertex_index]
    holder = bpy.data.objects.new("_pin_holder", mesh)
    bpy.context.scene.collection.objects.link(holder)
    pins = [row * stride + c for row in pinned_rows for c in range(stride)] + list(range(stride))
    holder.vertex_groups.new(name="pin").add(pins, 1.0, "REPLACE")
    bpy.context.scene.collection.objects.unlink(holder)
    bpy.data.objects.remove(holder)
    return mesh


def _settle_runner(mesh):
    """Deixa o pano cair sobre os degraus e o piso (caixas simples para o piso e o patamar, a escada de verdade)."""
    colliders = [bpy.data.objects["Stairs_Main"], _slab(5.0, 2.0, 6.2, 3.3, -0.1, 0.0),
                 _slab(5.0, layout.STAIRS.y1, 6.2, 8.2, 2.7, layout.LEVEL_Z[1])]
    try:
        settled = craft.drape(mesh, colliders, frames=55, mass=0.5, stiffness=40.0, bending=14.0, pin_group="pin",
                              thickness=RUNNER_THICK, subsurf=0, settle_frames=15)
    finally:
        for proxy in colliders[1:]:
            bpy.data.objects.remove(proxy)
        bpy.data.meshes.remove(mesh)
    settled.materials.append(materials.material_for("carpet_runner"))
    return settled


def _slab(x0, y0, x1, y1, z0, z1):
    corners = [(x, y, z) for z in (z0, z1) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    mesh = bpy.data.meshes.new("_craft_proxy")
    mesh.from_pydata(corners, [], [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
    mesh.update()
    obj = bpy.data.objects.new("_craft_proxy", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _add_wrinkles(mesh, uvs):
    """Uma dobra amassada de través num degrau e ondulação fina: o pano assentado fica bom demais."""
    layer = mesh.uv_layers.active.data
    along = {}
    for polygon in mesh.polygons:
        for loop_index, vertex_index in zip(polygon.loop_indices, polygon.vertices):
            along[vertex_index] = layer[loop_index].uv
    for vertex in mesh.vertices:
        width, travelled = along.get(vertex.index, (0.0, 0.0))
        across = math.sin(math.pi * width / (RUNNER_X[1] - RUNNER_X[0]))
        bunch = 0.014 * math.exp(-((travelled - 2.35) / 0.07) ** 2) * across
        ripple = 0.0025 * math.sin(vertex.co.x * 41.0 + vertex.co.y * 9.0)
        vertex.co += vertex.normal * (bunch + ripple)
    mesh.update()


def _object(ctx, name, mesh):
    obj = bpy.data.objects.new(name, mesh)
    ctx.link(obj, C.COL_WORLD)
    return obj


def _runner_rods(ctx, stairs):
    """Um varão de latão em cada dobra entre espelho e degrau, com ponteiras."""
    builder = ModelBuilder("Stairs_Rods", PROFILED)
    sides = detail(ctx, 8)
    x0, x1 = RUNNER_X
    for i in range(1, stairs.treads + 1):
        y, z = _tread_y(stairs, i) + NOSE + 0.012, _tread_top(stairs, i - 1) + 0.016
        builder.tube((x0 - 0.045, y, z), (x1 + 0.045, y, z), ROD_RADIUS, "brass_worn", sides)
        for x, sign in ((x0 - 0.045, -1), (x1 + 0.045, 1)):
            builder.tube((x, y, z), (x + sign * 0.022, y, z), 0.011, "brass_worn", sides, radius_end=0.0075)
            bracket = x - sign * 0.07
            builder.box(bracket - 0.012, y - 0.01, z - 0.012, bracket + 0.012, y + 0.01, z, "brass_worn")
    builder.build(ctx, C.COL_WORLD)


# --------------------------------------------------------------------------
# Colisão do corrimão
# --------------------------------------------------------------------------
def _build_rail_colliders(ctx):
    """Paredes invisíveis no lugar dos corrimãos (a IA também as lê como obstáculos)."""
    stairs = layout.STAIRS
    east = MeshBuilder("COL_Stairs_RailE")
    east.box(stairs.x1, stairs.y0, 0.0, stairs.x1 + COLLISION_THICKNESS, stairs.y1,
             layout.LEVEL_Z[1] + RAIL_HEIGHT, "black")
    south = MeshBuilder("COL_Stairs_RailS")
    south.box(stairs.hole.x0, stairs.y0 - COLLISION_THICKNESS, layout.LEVEL_Z[1], stairs.x1, stairs.y0,
              layout.LEVEL_Z[1] + RAIL_HEIGHT, "black")
    for builder in (east, south):
        builder.build(ctx, C.COL_COLLISION, collision=True, hide=True)
