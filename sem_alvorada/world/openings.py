"""Vãos da casa: batentes, portas (pivô + folha + maçaneta), arcos, janelas, cortinas e o portão.

Cada porta segue o contrato: um Empty pivô na dobradiça, com a folha modelada em +X local.
"""
import math

from .. import conventions as C
from .. import layout
from .meshkit import MeshBuilder, attach, empty

CASING_WIDTH = 0.075
CASING_PROUD = 0.03
THRESHOLD_HEIGHT = 0.012
LEAF_THICKNESS = 0.04
LEAF_CLEARANCE = 0.005
PANEL_RELIEF = 0.007
ROLLUP_PANELS = 7

# Cortinas por janela: (estilo, comprimento). "closed" fecha o vão, "open" recolhe nas laterais.
CURTAINS = {
    "w_living_s": ("open", "long"), "w_living_w": ("open", "long"),
    "w_dining_s": ("closed", "long"), "w_den_w": ("open", "long"),
    "w_kitchen_n": ("open", "short"),
    "w_master_n": ("open", "long"), "w_master_w": ("closed", "long"),
    "w_kids_s": ("closed", "long"), "w_kids_w": ("closed", "long"),
}
SHUTTER_WALL_Y = 0.0   # venezianas nas janelas largas do térreo voltadas para a rua


def build(ctx):
    pieces = _opening_pieces()
    for op in layout.OPENINGS.values():
        piece = pieces[op.id]
        if op.kind == "door":
            build_door(ctx, op, piece)
        elif op.kind == "arch":
            build_arch(ctx, op, piece)
        elif op.kind == "window":
            build_window(ctx, op, piece)
        elif op.kind == "garage_door":
            build_rollup(ctx, op, piece)
    ctx.log("vãos: portas, arcos, janelas, cortinas e portão")


def _opening_pieces():
    """Uma peça de verga por abertura: dela saem a espessura da parede e o lado exterior."""
    found = {}
    for level in (0, 1):
        for piece in layout.wall_pieces(level):
            if piece.opening:
                found[piece.opening] = piece
    return found


def _wall_point(op, u, n, z):
    """(u ao longo da parede, n na normal, z) -> ponto de mundo."""
    return (u, n, z) if op.axis == "x" else (n, u, z)


def _wall_box(builder, op, u0, u1, n0, n1, z0, z1, material, skip=()):
    if op.axis == "x":
        builder.box(u0, n0, z0, u1, n1, z1, material, skip=skip)
    else:
        builder.box(n0, u0, z0, n1, u1, z1, material, skip=skip)


def _inward_sign(piece):
    """Sinal da normal que aponta para dentro da casa (parede exterior: o lado que tem cômodo)."""
    return 1 if not piece.room_lo else -1


def _casing(builder, op, piece, height, width=CASING_WIDTH, sides=(-1, 1)):
    """Guarnição (testeiras) nas duas faces da parede, contornando o vão."""
    floor = layout.LEVEL_Z[op.level] + op.sill
    half = piece.thickness / 2
    for side in sides:
        n0, n1 = sorted((op.pos + side * half, op.pos + side * (half + CASING_PROUD)))
        _wall_box(builder, op, op.a - width, op.a, n0, n1, floor, floor + height + width, "trim_white", skip=("-z",))
        _wall_box(builder, op, op.b, op.b + width, n0, n1, floor, floor + height + width, "trim_white", skip=("-z",))
        _wall_box(builder, op, op.a, op.b, n0, n1, floor + height, floor + height + width, "trim_white", skip=("+z",))


# --------------------------------------------------------------------------
# Portas
# --------------------------------------------------------------------------
def build_door(ctx, op, piece):
    frame = MeshBuilder(f"DoorFrame_{op.id}")
    _casing(frame, op, piece, op.height)
    half = piece.thickness / 2
    floor = layout.LEVEL_Z[op.level]
    _wall_box(frame, op, op.a, op.b, op.pos - half, op.pos + half, floor, floor + THRESHOLD_HEIGHT,
              "wood_dark", skip=("-z",))
    frame.build(ctx, C.COL_WORLD)

    placement = layout.door_transform(op)
    pivot = empty(ctx, f"{C.N_DOOR}{op.id}", C.COL_WORLD, placement["hinge"], placement["closed_yaw"])
    pivot[C.P_ID] = op.id
    pivot[C.P_INTERACT] = "door"
    pivot[C.P_DOOR_CLOSED] = placement["closed_yaw"]
    pivot[C.P_DOOR_OPEN] = placement["open_yaw"]
    pivot[C.P_LOCK] = op.lock
    width = op.width - 0.02
    leaf = _door_leaf(f"DoorLeaf_{op.id}", width, op.height - LEAF_CLEARANCE).build(ctx, C.COL_WORLD)
    attach(leaf, pivot)
    knobs = _door_handles(f"DoorHandle_{op.id}").build(ctx, C.COL_WORLD)
    attach(knobs, pivot, (width - 0.07, 0.0, 1.0))


def _door_leaf(name, width, height):
    """Folha em +X local: placa lisa mais quatro almofadas em relevo por face."""
    builder = MeshBuilder(name)
    half = LEAF_THICKNESS / 2
    builder.box(0.0, -half, 0.01, width, half, height, "door_wood")
    stile, top_rail, bottom_rail, mid_rail = 0.14, 0.14, 0.20, 0.12
    columns = (width - 2 * stile - mid_rail) / 2
    spans_x = [(stile, stile + columns), (stile + columns + mid_rail, width - stile)]
    free = height - top_rail - bottom_rail - mid_rail
    lower = free * 0.45
    spans_z = [(bottom_rail, bottom_rail + lower), (bottom_rail + lower + mid_rail, height - top_rail)]
    for x0, x1 in spans_x:
        for z0, z1 in spans_z:
            builder.box(x0, half, z0, x1, half + PANEL_RELIEF, z1, "door_wood", skip=("-y",))
            builder.box(x0, -half - PANEL_RELIEF, z0, x1, -half, z1, "door_wood", skip=("+y",))
    return builder


def _door_handles(name):
    """Puxador dos dois lados, centrado na origem do objeto (que fica no ponto da maçaneta)."""
    builder = MeshBuilder(name)
    for side in (-1, 1):
        base = side * LEAF_THICKNESS / 2
        builder.cylinder(0.0, 0.0, min(base, base + side * 0.008), max(base, base + side * 0.008),
                         0.038, "metal", sides=8, axis="y")
        builder.cylinder(0.0, 0.0, min(base, base + side * 0.05), max(base, base + side * 0.05),
                         0.011, "metal", sides=6, axis="y")
        builder.cylinder(0.0, 0.0, min(base + side * 0.05, base + side * 0.09), max(base + side * 0.05, base + side * 0.09),
                         0.026, "metal", sides=8, radius_top=0.02, axis="y")
    return builder


# --------------------------------------------------------------------------
# Arcos
# --------------------------------------------------------------------------
def build_arch(ctx, op, piece):
    """Guarnição lateral e cantos arredondados (enchimento entre o canto e um arco de 1/4 de círculo)."""
    builder = MeshBuilder(f"ArchFrame_{op.id}")
    floor = layout.LEVEL_Z[op.level]
    top = floor + op.height
    half = piece.thickness / 2
    radius = 0.35
    for corner_u, direction in ((op.a, 1), (op.b, -1)):
        centre = (corner_u + direction * radius, top - radius)
        arc = [(centre[0] - direction * radius * math.sin(t), centre[1] + radius * math.cos(t))
               for t in [i * (math.pi / 2) / 6 for i in range(7)]]
        builder.extrude_profile([(corner_u, top)] + arc, op.axis, op.pos - half, op.pos + half, "trim_white")
    _casing(builder, op, piece, op.height, width=0.06)
    builder.build(ctx, C.COL_WORLD)


# --------------------------------------------------------------------------
# Janelas
# --------------------------------------------------------------------------
def build_window(ctx, op, piece):
    inward = _inward_sign(piece)
    floor = layout.LEVEL_Z[op.level]
    z_bottom, z_top = floor + op.sill, floor + op.sill + op.height
    centre = _wall_point(op, (op.a + op.b) / 2, op.pos, (z_bottom + z_top) / 2)
    builder = MeshBuilder(f"Window_{op.id}")
    _sash(builder, op, z_bottom, z_top)
    _window_trim(builder, op, piece, inward, z_bottom, z_top)
    if op.axis == "x" and op.pos == SHUTTER_WALL_Y and op.width >= 1.0 and op.level == 0:
        _shutters(builder, op, piece, z_bottom, z_top)
    window = builder.build(ctx, C.COL_WORLD, origin=centre)
    _window_blocker(ctx, op, piece, z_bottom, z_top)
    window[C.P_ID] = op.id
    window[C.P_INTERACT] = "look"
    window[C.P_PROMPT] = "[E] Olhar"
    window[C.P_ROOM] = op.rooms[0]
    if op.id in CURTAINS:
        curtain = _curtains(op, piece, inward, z_bottom, z_top).build(ctx, C.COL_WORLD, origin=centre)
        attach(curtain, window)
    return window


def _window_blocker(ctx, op, piece, z_bottom, z_top):
    """Proxy invisível que fecha o vão da janela para a colisão (o jogador não sai por ela)."""
    half = piece.thickness / 2
    blocker = MeshBuilder(f"COL_Window_{op.id}")
    _wall_box(blocker, op, op.a, op.b, op.pos - half, op.pos + half, z_bottom, z_top, "black")
    blocker.build(ctx, C.COL_COLLISION, collision=True, hide=True)


def _sash(builder, op, z_bottom, z_top):
    """Caixilho no meio da espessura da parede, com montantes e travessa (sem vidro)."""
    bar, depth = 0.055, 0.035
    n0, n1 = op.pos - depth, op.pos + depth
    for u0, u1 in ((op.a, op.a + bar), (op.b - bar, op.b)):
        _wall_box(builder, op, u0, u1, n0, n1, z_bottom, z_top, "trim_white")
    for z0, z1 in ((z_bottom, z_bottom + bar), (z_top - bar, z_top)):
        _wall_box(builder, op, op.a + bar, op.b - bar, n0, n1, z0, z1, "trim_white")
    panes = max(1, round(op.width / 0.7))
    for i in range(1, panes):
        u = op.a + op.width * i / panes
        _wall_box(builder, op, u - 0.014, u + 0.014, op.pos - 0.02, op.pos + 0.02,
                  z_bottom + bar, z_top - bar, "trim_white")
    if op.height >= 0.8:
        z = (z_bottom + z_top) / 2
        _wall_box(builder, op, op.a + bar, op.b - bar, op.pos - 0.02, op.pos + 0.02, z - 0.014, z + 0.014, "trim_white")


def _window_trim(builder, op, piece, inward, z_bottom, z_top):
    """Guarnições, peitoril (interno) e pingadeira (externa)."""
    half = piece.thickness / 2
    for side in (-1, 1):
        n0, n1 = sorted((op.pos + side * half, op.pos + side * (half + CASING_PROUD)))
        _wall_box(builder, op, op.a - CASING_WIDTH, op.a, n0, n1, z_bottom, z_top + CASING_WIDTH, "trim_white", skip=("-z",))
        _wall_box(builder, op, op.b, op.b + CASING_WIDTH, n0, n1, z_bottom, z_top + CASING_WIDTH, "trim_white", skip=("-z",))
        _wall_box(builder, op, op.a, op.b, n0, n1, z_top, z_top + CASING_WIDTH, "trim_white", skip=("+z",))
        projection = 0.09 if side == inward else 0.07
        s0, s1 = sorted((op.pos + side * half, op.pos + side * (half + projection)))
        _wall_box(builder, op, op.a - CASING_WIDTH - 0.03, op.b + CASING_WIDTH + 0.03, s0, s1,
                  z_bottom - 0.03, z_bottom + 0.012, "trim_white")


def _shutters(builder, op, piece, z_bottom, z_top):
    """Venezianas fixas na face externa, um par ao lado de cada janela larga da fachada."""
    half = piece.thickness / 2
    outward = -_inward_sign(piece)
    n0, n1 = sorted((op.pos + outward * half, op.pos + outward * (half + 0.035)))
    width = 0.32
    for u0, u1 in ((op.a - CASING_WIDTH - 0.03 - width, op.a - CASING_WIDTH - 0.03),
                   (op.b + CASING_WIDTH + 0.03, op.b + CASING_WIDTH + 0.03 + width)):
        _wall_box(builder, op, u0, u1, n0, n1, z_bottom - 0.03, z_top + CASING_WIDTH, "wall_green", skip=("-z",))


def _curtains(op, piece, inward, z_bottom, z_top):
    style, length = CURTAINS[op.id]
    builder = MeshBuilder(f"Curtain_{op.id}")
    half = piece.thickness / 2
    n_plane = op.pos + inward * (half + 0.13)
    if length == "short":
        top, bottom = z_bottom + op.height * 0.55, z_bottom - 0.05
        rod_z = top + 0.03
    else:
        rod_z = z_top + 0.16
        top, bottom = rod_z - 0.03, layout.LEVEL_Z[op.level] + 0.04
    _wall_box(builder, op, op.a - 0.3, op.b + 0.3, n_plane - 0.015, n_plane + 0.015, rod_z - 0.015,
              rod_z + 0.015, "wood_dark")
    if style == "closed":
        panels = [(op.a - 0.12, (op.a + op.b) / 2 + 0.06), ((op.a + op.b) / 2 - 0.06, op.b + 0.12)]
    else:
        panels = [(op.a - 0.3, op.a + 0.4), (op.b - 0.4, op.b + 0.3)]
    for u0, u1 in panels:
        _curtain_panel(builder, op, u0, u1, top, bottom, n_plane, inward)
    return builder


def _curtain_panel(builder, op, u0, u1, top, bottom, n_plane, inward):
    """Faixa pregueada de cortina: colunas alternando fundo/frente, dupla face, barra irregular."""
    folds = max(4, round((u1 - u0) / 0.09))
    columns = []
    for i in range(folds + 1):
        u = u0 + (u1 - u0) * i / folds
        n = n_plane + inward * (0.055 if i % 2 else 0.0)
        hem = bottom + 0.03 * math.sin(i * 2.3)
        columns.append(((u, n, top), (u, n, hem)))
    for (top_a, low_a), (top_b, low_b) in zip(columns, columns[1:]):
        corners = [_wall_point(op, *low_a), _wall_point(op, *low_b), _wall_point(op, *top_b), _wall_point(op, *top_a)]
        builder.polygon(corners, "curtain")
        builder.polygon(corners[::-1], "curtain")


# --------------------------------------------------------------------------
# Portão da garagem
# --------------------------------------------------------------------------
def build_rollup(ctx, op, piece):
    """Portão de enrolar: Empty raiz e painéis horizontais. Abrir = subir `location.z` em `sa_open_lift`."""
    root = empty(ctx, C.OBJ_GARAGE_ROLLUP, C.COL_WORLD, (op.mid[0], op.pos, layout.LEVEL_Z[op.level]))
    root["sa_open_lift"] = 2.3
    root[C.P_ID] = op.id
    root[C.P_ROOM] = "garage"
    frame = MeshBuilder("GarageFrame")
    _casing(frame, op, piece, op.height, width=0.12)
    frame.build(ctx, C.COL_WORLD)
    panels = MeshBuilder("GarageRollup_Panels")
    width = op.width - 0.06
    gap = 0.012
    height = op.height / ROLLUP_PANELS
    for i in range(ROLLUP_PANELS):
        z0 = i * height + gap / 2
        panels.box(-width / 2, -0.02, z0, width / 2, 0.02, (i + 1) * height - gap / 2, "door_garage_metal")
    body = panels.build(ctx, C.COL_WORLD)
    attach(body, root)
    blocker = MeshBuilder("COL_GarageRollup")
    blocker.box(op.a, op.pos - 0.05, layout.LEVEL_Z[op.level], op.b, op.pos + 0.05, layout.LEVEL_Z[op.level] + op.height,
                "black")
    blocker.build(ctx, C.COL_COLLISION, collision=True, hide=True)
