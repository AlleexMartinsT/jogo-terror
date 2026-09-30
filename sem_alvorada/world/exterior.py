"""Exterior: rua, calçada, gramado, entrada de carros, varanda, cerca, árvores secas, poste, caixa
de correio, casas vizinhas apagadas e o horizonte.

O jogador quase nunca sai da casa, mas a janela do quarto olha para fora e o final atravessa a
rua. Por isso o exterior existe inteiro, só que escuro: casas e árvores são silhuetas contra o
brilho fraco do horizonte (ver `sky`).
"""
import math

from .. import conventions as C
from .. import layout
from .meshkit import MeshBuilder

GROUND_Z = -0.12
ROAD_Z = -0.22
SIDEWALK_Z = -0.08
CURB_BOTTOM = -0.4
WORLD_EXTENT = (-170.0, 190.0)      # gramado e horizonte cobrem esta faixa em x e y
HORIZON_RADIUS = 155.0
LOT_EAST_X = 21.5
LOT_WEST_X = -6.0
LOT_BACK_Y = 16.0
FENCE_FRONT_Y = -5.4
SILHOUETTE = "night_silhouette"


def build(ctx):
    _ground(ctx)
    _street(ctx)
    _porch_and_stoop(ctx)
    _fence(ctx)
    _street_furniture(ctx)
    _trees(ctx)
    _neighbors(ctx)
    _horizon(ctx)
    ctx.log("exterior: rua, gramado, varanda, cerca, árvores, vizinhos e horizonte")


def _flat_quad(builder, rect, z, material):
    builder.quad((rect.x0, rect.y0, z), (rect.x1, rect.y0, z), (rect.x1, rect.y1, z), (rect.x0, rect.y1, z), material)


def _ground(ctx):
    low, high = WORLD_EXTENT
    grass = MeshBuilder("Ground_Grass")
    _flat_quad(grass, layout.Rect(low, layout.LAWN_FRONT.y0, high, high), GROUND_Z, "grass_dead")
    across = layout.Rect(low, low, high, layout.ROAD.y0 - 2.0)
    _flat_quad(grass, across, GROUND_Z, "grass_dead")
    grass.build(ctx, C.COL_WORLD)


def _street(ctx):
    road_rect, walk = layout.ROAD, layout.SIDEWALK
    builder = MeshBuilder("Street")
    _flat_quad(builder, road_rect, ROAD_Z, "asphalt")
    far_walk = layout.Rect(walk.x0, road_rect.y0 - 2.0, walk.x1, road_rect.y0)
    for rect in (walk, far_walk):
        builder.box(rect.x0, rect.y0, CURB_BOTTOM, rect.x1, rect.y1, SIDEWALK_Z, "sidewalk", skip=("-z", "-x", "+x"))
    centre = (road_rect.y0 + road_rect.y1) / 2
    x = road_rect.x0 + 2.0
    while x < road_rect.x1 - 3.0:
        builder.quad((x, centre - 0.07, ROAD_Z + 0.004), (x + 3.0, centre - 0.07, ROAD_Z + 0.004),
                     (x + 3.0, centre + 0.07, ROAD_Z + 0.004), (x, centre + 0.07, ROAD_Z + 0.004), "road_paint")
        x += 8.0
    _driveway(builder)
    builder.build(ctx, C.COL_WORLD)


def _ramp(builder, x0, x1, y_from, z_from, y_to, z_to, material):
    """Faixa inclinada entre dois valores de y, com a normal sempre para cima."""
    (y_a, z_a), (y_b, z_b) = sorted(((y_from, z_from), (y_to, z_to)))
    builder.quad((x0, y_a, z_a), (x1, y_a, z_a), (x1, y_b, z_b), (x0, y_b, z_b), material)


def _driveway(builder):
    """Entrada de carros: desce do portão até a calçada, atravessa-a e mergulha na rua."""
    drive, walk = layout.DRIVEWAY, layout.SIDEWALK
    raised = SIDEWALK_Z + 0.02
    _ramp(builder, drive.x0, drive.x1, -layout.WALL_T_EXT / 2, 0.0, walk.y1, raised, "sidewalk")
    _ramp(builder, drive.x0, drive.x1, walk.y1, raised, walk.y0, raised, "sidewalk")
    _ramp(builder, drive.x0, drive.x1, walk.y0, raised, walk.y0 - 0.6, ROAD_Z + 0.01, "sidewalk")


# --------------------------------------------------------------------------
# Varanda da frente e degrau dos fundos
# --------------------------------------------------------------------------
def _porch_and_stoop(ctx):
    front = layout.OPENINGS["front"]
    back = layout.OPENINGS["back"]
    builder = MeshBuilder("Porch")
    wall = layout.WALL_T_EXT / 2
    cx = (front.a + front.b) / 2
    half_width = 1.15
    builder.box(cx - half_width, -1.75, CURB_BOTTOM, cx + half_width, -wall, 0.0, "sidewalk", skip=("-z",))
    builder.box(cx - 0.85, -2.25, CURB_BOTTOM, cx + 0.85, -1.75, -0.06, "sidewalk", skip=("-z",))
    builder.box(cx - 0.5, layout.LAWN_FRONT.y0, GROUND_Z, cx + 0.5, -2.25, GROUND_Z + 0.03, "sidewalk", skip=("-z",))
    for post_x in (cx - half_width + 0.12, cx + half_width - 0.12):
        builder.box(post_x - 0.06, -1.62, 0.0, post_x + 0.06, -1.5, 2.74, "trim_white", skip=("-z",))
    _porch_railing(builder, cx, half_width)
    _porch_roof(builder, cx, half_width)
    builder.build(ctx, C.COL_WORLD)

    stoop = MeshBuilder("Stoop")
    bx = (back.a + back.b) / 2
    stoop.box(bx - 0.8, 10.0 + wall, CURB_BOTTOM, bx + 0.8, 10.95, 0.0, "sidewalk", skip=("-z",))
    stoop.box(bx - 0.6, 10.95, CURB_BOTTOM, bx + 0.6, 11.35, -0.06, "sidewalk", skip=("-z",))
    stoop.build(ctx, C.COL_WORLD)


def _porch_railing(builder, cx, half_width):
    for side in (-1, 1):
        x = cx + side * (half_width - 0.05)
        builder.box(x - 0.03, -1.7, 0.88, x + 0.03, -layout.WALL_T_EXT / 2, 0.94, "trim_white")
        for y in (-1.5, -1.15, -0.8, -0.45):
            builder.box(x - 0.015, y - 0.015, 0.0, x + 0.015, y + 0.015, 0.88, "trim_white", skip=("-z",))


def _porch_roof(builder, cx, half_width):
    """Água única sobre a porta, presa à parede abaixo do peitoril da janela do corredor."""
    left, right = cx - half_width - 0.15, cx + half_width + 0.15
    high, low = 3.1, 2.72
    y_wall, y_front = -layout.WALL_T_EXT / 2, -2.0
    top = [(left, y_wall, high), (right, y_wall, high), (right, y_front, low), (left, y_front, low)]
    thickness = 0.1
    builder.polygon(top[::-1], "roof_shingle")
    bottom = [(x, y, z - thickness) for x, y, z in top]
    builder.polygon(bottom, "trim_white")
    for i in range(4):
        j = (i + 1) % 4
        builder.quad(top[i], top[j], bottom[j], bottom[i], "trim_white")


# --------------------------------------------------------------------------
# Cerca
# --------------------------------------------------------------------------
def _pickets(rng, start, end):
    """Posições e alturas das ripas entre dois pontos; algumas faltam, outras estão quebradas."""
    length = end - start
    count = max(2, int(length / 0.19))
    for i in range(count):
        if rng.random() < 0.07:
            continue
        broken = 0.22 if rng.random() < 0.06 else 0.0
        yield start + length * (i + 0.5) / count, 0.92 + rng.random() * 0.08 - broken


def _fence(ctx):
    rng = ctx.rng
    builder = MeshBuilder("Fence")
    runs = [
        ("x", FENCE_FRONT_Y, LOT_WEST_X, 5.0), ("x", FENCE_FRONT_Y, 8.0, 12.9),
        ("y", LOT_WEST_X, FENCE_FRONT_Y, LOT_BACK_Y), ("x", LOT_BACK_Y, LOT_WEST_X, LOT_EAST_X),
        ("y", LOT_EAST_X, 8.0, LOT_BACK_Y),
    ]
    for axis, fixed, start, end in runs:
        for u, height in _pickets(rng, start, end):
            if axis == "x":
                builder.box(u - 0.045, fixed - 0.012, GROUND_Z, u + 0.045, fixed + 0.012, GROUND_Z + height,
                            "fence_wood", skip=("-z",))
            else:
                builder.box(fixed - 0.012, u - 0.045, GROUND_Z, fixed + 0.012, u + 0.045, GROUND_Z + height,
                            "fence_wood", skip=("-z",))
        for rail_z in (GROUND_Z + 0.25, GROUND_Z + 0.7):
            if axis == "x":
                builder.box(start, fixed + 0.012, rail_z, end, fixed + 0.04, rail_z + 0.06, "fence_wood", skip=("-y",))
            else:
                builder.box(fixed + 0.012, start, rail_z, fixed + 0.04, end, rail_z + 0.06, "fence_wood", skip=("-x",))
    builder.build(ctx, C.COL_WORLD)


# --------------------------------------------------------------------------
# Poste morto e caixa de correio
# --------------------------------------------------------------------------
def _street_furniture(ctx):
    builder = MeshBuilder("StreetFurniture")
    x, y = 10.5, -5.0
    builder.cylinder(x, y, CURB_BOTTOM, 7.3, 0.11, "metal", sides=6, radius_top=0.065)
    builder.beam((x, y, 7.1), (x, y - 2.3, 7.55), 0.07, 0.07, "metal")
    builder.box(x - 0.2, y - 2.9, 7.35, x + 0.2, y - 2.1, 7.5, "black")
    builder.box(x - 0.16, y - 2.8, 7.31, x + 0.16, y - 2.2, 7.35, "glass_dark", skip=("+z",))
    _mailbox(builder, 12.4, -4.7)
    builder.build(ctx, C.COL_WORLD)


def _mailbox(builder, x, y):
    builder.box(x - 0.045, y - 0.045, GROUND_Z, x + 0.045, y + 0.045, 1.08, "wood_dark", skip=("-z",))
    body = [(-0.12, 1.08), (0.12, 1.08), (0.12, 1.2), (0.09, 1.28), (0.0, 1.32), (-0.09, 1.28), (-0.12, 1.2)]
    builder.extrude_profile([(x + u, z) for u, z in body], "x", y - 0.27, y + 0.27, "metal")
    builder.box(x + 0.12, y + 0.05, 1.12, x + 0.15, y + 0.09, 1.34, "blood")


# --------------------------------------------------------------------------
# Árvores secas
# --------------------------------------------------------------------------
TREE_SPOTS = [(-3.2, -3.0), (9.6, -3.4), (19.0, -3.2), (-2.5, 13.0), (6.0, 14.5), (15.5, 12.5), (-9.0, 5.0),
              (24.5, 9.0), (-8.5, -12.0), (26.0, -4.0)]


def _branch(builder, rng, origin, direction, length, width, depth, material):
    """Galho afunilado que se ramifica; direção (dx, dy, dz) normalizada."""
    end = tuple(origin[i] + direction[i] * length for i in range(3))
    builder.beam(origin, end, width, width, material, skip_ends=False)
    if depth == 0:
        return
    for _ in range(2):
        turn = rng.uniform(0.5, 1.1)
        heading = rng.uniform(0, 2 * math.pi)
        new_dir = (direction[0] + math.cos(heading) * turn, direction[1] + math.sin(heading) * turn,
                   direction[2] * 0.6 + 0.25)
        norm = math.sqrt(sum(c * c for c in new_dir))
        new_dir = tuple(c / norm for c in new_dir)
        _branch(builder, rng, end, new_dir, length * 0.62, width * 0.65, depth - 1, material)


def _dead_tree(builder, rng, x, y, height, material, branches, sub_branch_depth):
    builder.cylinder(x, y, GROUND_Z, GROUND_Z + height, 0.22, material, sides=6, radius_top=0.07)
    for _ in range(branches):
        z = GROUND_Z + height * rng.uniform(0.35, 0.95)
        heading = rng.uniform(0, 2 * math.pi)
        direction = (math.cos(heading) * 0.85, math.sin(heading) * 0.85, 0.55)
        norm = math.sqrt(sum(c * c for c in direction))
        direction = tuple(c / norm for c in direction)
        _branch(builder, rng, (x, y, z), direction, height * 0.3 * (1.1 - (z - GROUND_Z) / height * 0.5),
                0.09, sub_branch_depth, material)


def _trees(ctx):
    rng = ctx.rng
    near = MeshBuilder("Trees_Near")
    for x, y in TREE_SPOTS:
        _dead_tree(near, rng, x, y, rng.uniform(4.5, 7.5), "bark", rng.randint(5, 8), 1)
    near.build(ctx, C.COL_WORLD)

    far = MeshBuilder("Trees_Far")
    placed = 0
    while placed < 45:
        angle, radius = rng.uniform(0, 2 * math.pi), rng.uniform(45.0, 120.0)
        x, y = 6.0 + math.cos(angle) * radius, 5.0 + math.sin(angle) * radius
        if layout.ROAD.y0 - 3 < y < layout.ROAD.y1 + 3:
            continue
        _dead_tree(far, rng, x, y, rng.uniform(5.0, 9.0), SILHOUETTE, 4, 0)
        placed += 1
    far.build(ctx, C.COL_WORLD)


# --------------------------------------------------------------------------
# Casas vizinhas apagadas
# --------------------------------------------------------------------------
SIDE_LOTS = [layout.Rect(-34.0, -4.0, -18.0, 14.0), layout.Rect(28.0, -4.0, 44.0, 14.0)]


def _neighbor_house(builder, rng, lot, faces_south):
    """Casa de dois andares em silhueta: corpo, telhado de duas águas, anexo, chaminé e janelas mortas."""
    width, depth, wall_h = rng.uniform(9.0, 11.0), rng.uniform(8.0, 9.5), 5.4
    x0 = lot.x0 + rng.uniform(1.0, 3.0)
    x1 = x0 + width
    front_y = lot.y0 + 3.0 if faces_south else lot.y1 - 3.0
    y0, y1 = (front_y, front_y + depth) if faces_south else (front_y - depth, front_y)
    builder.box(x0, y0, GROUND_Z, x1, y1, wall_h, SILHOUETTE, skip=("-z",))
    ridge_z = wall_h + 2.1
    builder.extrude_profile([(y0 - 0.5, wall_h - 0.2), (y1 + 0.5, wall_h - 0.2), ((y0 + y1) / 2, ridge_z)], "y",
                            x0 - 0.5, x1 + 0.5, SILHOUETTE)
    annex_right = rng.random() < 0.6
    ax0, ax1 = (x1, x1 + 4.0) if annex_right else (x0 - 4.0, x0)
    builder.box(ax0, y0 + 0.5, GROUND_Z, ax1, y1 - 1.5, 3.0, SILHOUETTE, skip=("-z",))
    builder.extrude_profile([(y0 + 0.2, 2.9), (y1 - 1.2, 2.9), ((y0 + y1) / 2 - 0.5, 4.2)], "y", ax0 - 0.3, ax1 + 0.3,
                            SILHOUETTE)
    builder.box(x0 + 1.2, (y0 + y1) / 2 - 0.4, wall_h, x0 + 1.9, (y0 + y1) / 2 + 0.4, ridge_z + 1.0, SILHOUETTE)
    _dead_windows(builder, rng, x0, x1, front_y, -1 if faces_south else 1)


def _dead_windows(builder, rng, x0, x1, front_y, outward):
    """Janelas apagadas: caixas de vidro escuro coladas na fachada, algumas faltando."""
    face_near, face_far = sorted((front_y, front_y + outward * 0.05))
    for row_z in (1.0, 3.6):
        for i in range(int((x1 - x0) // 2.4)):
            if rng.random() < 0.12:
                continue
            cx = x0 + 1.2 + i * 2.4
            builder.box(cx - 0.55, face_near, row_z, cx + 0.55, face_far, row_z + 1.3, "glass_dark")


def _neighbors(ctx):
    rng = ctx.rng
    builder = MeshBuilder("Neighbors")
    for lot in layout.NEIGHBOR_LOTS:
        _neighbor_house(builder, rng, lot, faces_south=False)
    for lot in SIDE_LOTS:
        _neighbor_house(builder, rng, lot, faces_south=True)
    builder.build(ctx, C.COL_WORLD)


# --------------------------------------------------------------------------
# Horizonte
# --------------------------------------------------------------------------
def _horizon(ctx):
    """Anel de colinas e mata baixa ao redor: recorta o céu com uma linha irregular, sempre abaixo do Sol Negro."""
    rng = ctx.rng
    builder = MeshBuilder("Horizon")
    centre_x, centre_y = 6.0, 5.0
    steps = 96
    heights = [rng.uniform(4.0, 9.5) for _ in range(steps)]
    for i in range(steps):
        a0, a1 = 2 * math.pi * i / steps, 2 * math.pi * (i + 1) / steps
        p0 = (centre_x + HORIZON_RADIUS * math.cos(a0), centre_y + HORIZON_RADIUS * math.sin(a0))
        p1 = (centre_x + HORIZON_RADIUS * math.cos(a1), centre_y + HORIZON_RADIUS * math.sin(a1))
        h0, h1 = heights[i], heights[(i + 1) % steps]
        builder.quad((p1[0], p1[1], GROUND_Z), (p0[0], p0[1], GROUND_Z), (p0[0], p0[1], h0), (p1[0], p1[1], h1),
                     SILHOUETTE)
    builder.build(ctx, C.COL_WORLD)
