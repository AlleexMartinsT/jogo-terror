"""Peças planas e de parede dos cômodos de cima: tapetes macios, quadros emoldurados, decals e teias.

Mesma convenção de `furniture.py` (`wall` = 'N','S','E','W', `along` ao longo da parede, `z` do centro), mas com
molduras de verdade, tapetes com felpa e franja, e materiais `up_*` de textura linear.
"""
import math

import bmesh
import bpy

from .assembly_quartos import CLOTH, WOOD, Assembly
from .kit import MeshBuilder
from .placement import against_wall, floor_z, place

WALL_GAP = 0.004


def wall_spot(room, wall, along):
    """(x, y, yaw) de um ponto da face interna da parede `wall`, com a frente da peça voltada para o cômodo."""
    return against_wall(room, wall, along, 0.0)


# ---------------------------------------------------------------------------
# Tapetes
# ---------------------------------------------------------------------------
def _rug_mesh(width, depth, round_shape, thickness, curl, seed):
    """Malha do tapete: grade com felpa irregular, borda arredondada e um canto levantado opcional."""
    import random
    rng = random.Random(seed)
    nx, ny = max(10, int(width * 12)), max(10, int(depth * 12))
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    phase = [rng.uniform(0, math.tau) for _ in range(4)]
    verts = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            x, y = _disc_map(u, v, width, depth) if round_shape else ((u - 0.5) * width, (v - 0.5) * depth)
            lump = 0.0025 * math.sin(x * 11 + phase[0]) * math.sin(y * 9 + phase[1])
            edge = min(u, 1 - u, v, 1 - v)
            z = thickness + lump
            if edge < 0.012:
                z *= 0.55 + 0.45 * edge / 0.012
            if curl:
                dist = math.hypot(u - 1.0, v - 1.0)
                z += curl * max(0.0, 1 - dist / 0.16) ** 1.6
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)
    for j in range(ny):
        for i in range(nx):
            corners = [verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]]
            face = bm.faces.new(corners)
            for loop, (du, dv) in zip(face.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                loop[uv_layer].uv = ((i + du) / nx, (j + dv) / ny)
    mesh = bpy.data.meshes.new("rug_top")
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return mesh


def _disc_map(u, v, width, depth):
    """Leva o quadrado unitário ao disco (mapeamento que preserva a grade), em metros."""
    a, b = 2 * u - 1, 2 * v - 1
    x = a * math.sqrt(max(0.0, 1 - b * b / 2))
    y = b * math.sqrt(max(0.0, 1 - a * a / 2))
    return x * width / 2, y * depth / 2


def make_rug(ctx, room, x, y, yaw, width, depth, material, *, round_shape=False, curl=0.0, fringe=True, name=None,
             z=None, tile_along=False):
    """Tapete rente ao piso (não colide). Espessura média 1,4 cm; `curl` levanta um canto; `fringe` põe franja nas pontas."""
    rug = Assembly(name or f"rug_{room}")
    thickness = 0.014
    top = _rug_mesh(width, depth, round_shape, thickness, curl, ctx.seed + int(x * 7 + y * 13))
    if tile_along:
        _tile_uv(top, depth / width)
    rug.add_mesh(top, material)
    border = rug.part(CLOTH)
    if round_shape:
        rim = [(math.cos(2 * math.pi * k / 40) * width / 2, math.sin(2 * math.pi * k / 40) * depth / 2) for k in range(40)]
        border.loft([[(px, py, 0.0) for px, py in rim], [(px, py, thickness * 0.8) for px, py in rim]], material,
                    cap_start=False, cap_end=False, smooth=True, uv=1.0)
    else:
        border.box(0, 0, 0, width, depth, thickness * 0.8, material, skip=("top", "bottom"))
    if fringe and not round_shape:
        _fringe(border, width, depth, material)
    return place(ctx, rug, room, "rug", x, y, yaw, floor_z(room) if z is None else z, mode="flat", name=name)


def _tile_uv(mesh, repeats):
    layer = mesh.uv_layers.active
    for loop in mesh.loops:
        u, v = layer.data[loop.index].uv
        layer.data[loop.index].uv = (u, v * repeats)


def _fringe(m, width, depth, material):
    """Franja de fios soltos nas duas pontas curtas do tapete (quads finos, ligeiramente desencontrados)."""
    count = max(12, int(min(width, depth) * 30))
    for end, sign in ((depth / 2, 1), (-depth / 2, -1)):
        for index in range(count):
            x = -width / 2 + (index + 0.5) * width / count
            wobble = 0.012 * math.sin(index * 2.1 + end * 3) + 0.01
            m.quad((x - 0.0035, end, 0.001), (x + 0.0035, end, 0.001), (x + 0.0035 + wobble / 2, end + sign * 0.045, 0.0008),
                   (x - 0.0035 + wobble / 2, end + sign * 0.045, 0.0008), "up_cloth_beige")


# ---------------------------------------------------------------------------
# Decals
# ---------------------------------------------------------------------------
def make_floor_decal(ctx, room, x, y, yaw, width, depth, material, *, lift=0.018, z=None, name=None):
    """Mancha deitada no piso ou sobre um tapete (um quad com alfa)."""
    decal = MeshBuilder(name or f"stain_{room}")
    decal.finish = None
    decal.panel(0, 0, 0, width, depth, material, "top")
    base = floor_z(room) if z is None else z
    return place(ctx, decal, room, "decal", x, y, yaw, base + lift, mode="flat", name=name)


def make_wall_decal(ctx, room, wall, along, z, width, height, material, *, flip_u=False, name=None):
    """Marca rente à parede (mãos, adesivos, teias): um quad com alfa a 4 mm da superfície."""
    x, y, yaw = wall_spot(room, wall, along)
    decal = MeshBuilder(name or f"decal_{room}")
    decal.finish = None
    decal.panel(0, WALL_GAP, 0, width, height, material, "front", uv_rect=(1, 0, 0, 1) if flip_u else (0, 0, 1, 1))
    return place(ctx, decal, room, "decal", x, y, yaw, floor_z(room) + z, mode="wall", name=name)


def make_cobweb(ctx, room, wall, along, ceiling_z, size=0.36, *, flip_u=False):
    """Teia no canto alto, com o centro no canto entre parede e forro.

    `along` é o canto na parede; sem `flip_u` o canto fica à esquerda de quem olha a parede (a teia se abre para a direita).
    """
    x, y, yaw = wall_spot(room, wall, along)
    web = MeshBuilder(f"cobweb_{room}")
    web.finish = None
    web.panel(size * (0.5 if flip_u else -0.5), WALL_GAP * 2, -size / 2, size, size, "up_cobweb", "front",
              uv_rect=(1, 0, 0, 1) if flip_u else (0, 0, 1, 1))
    return place(ctx, web, room, "decal", x, y, yaw, floor_z(room) + ceiling_z, mode="wall", name=f"cobweb_{room}")


# ---------------------------------------------------------------------------
# Quadros
# ---------------------------------------------------------------------------
def _frame_bars(m, width, height, border, depth, mat):
    """Moldura em quatro barras com degrau interno (lábio) e chanfros."""
    outer_h = height + 2 * border
    for sign in (-1, 1):
        m.box(sign * (width + border) / 2, 0, -outer_h / 2, border, depth, outer_h, mat)
        m.box(0, 0, sign * (height + border) / 2 - border / 2, width, depth, border, mat)
    lip = border * 0.35
    for sign in (-1, 1):
        m.box(sign * (width / 2 - lip / 2), depth * 0.35, -height / 2, lip, depth * 0.5, height, mat)
        m.box(0, depth * 0.35, sign * (height / 2 - lip / 2) - lip / 2, width - 2 * lip, depth * 0.5, lip, mat)


def make_framed(ctx, room, wall, along, z, width, height, art, *, frame="up_walnut", border=0.035, tilt=0.0,
                depth=0.028, name=None):
    """Quadro de parede: moldura de madeira, passe-partout creme e a arte; `tilt` (graus) o deixa torto."""
    x, y, yaw = wall_spot(room, wall, along)
    picture = Assembly(name or f"picture_{room}")
    wood = picture.part(WOOD)
    with wood.at(0, depth / 2 + 0.002, 0, ry=tilt):
        _frame_bars(wood, width, height, border, depth, frame)
        wood.panel(0, -depth / 2 + 0.002, 0, width + 2 * border, height + 2 * border, "up_paint_cream", "back")
        mat_size = 0.03
        wood.panel(0, depth * 0.18, 0, width, height, "up_paint_cream", "front")
        wood.panel(0, depth * 0.18 + 0.001, 0, width - 2 * mat_size, height - 2 * mat_size, art, "front")
    return place(ctx, picture, room, "picture", x, y, yaw, floor_z(room) + z, mode="wall", name=name)


def make_pinned_sheet(ctx, room, wall, along, z, width, height, art, *, tilt=0.0, name=None):
    """Folha de papel presa na parede com dois pedaços de fita crepe nos cantos de cima; `tilt` em graus."""
    x, y, yaw = wall_spot(room, wall, along)
    sheet = MeshBuilder(name or f"sheet_{room}")
    sheet.finish = None
    with sheet.at(0, 0, 0, ry=tilt):
        sheet.panel(0, WALL_GAP * 2, 0, width, height, art, "front")
        for side in (-1, 1):
            sheet.quad((side * width / 2 - 0.02, WALL_GAP * 3, height / 2 - 0.012), (side * width / 2 + 0.02, WALL_GAP * 3, height / 2 - 0.012),
                       (side * width / 2 + 0.02, WALL_GAP * 3, height / 2 + 0.012), (side * width / 2 - 0.02, WALL_GAP * 3, height / 2 + 0.012),
                       "up_cloth_beige", uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    return place(ctx, sheet, room, "decal", x, y, yaw, floor_z(room) + z, mode="wall", name=name)
