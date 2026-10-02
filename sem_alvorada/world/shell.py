"""Casca da casa: pisos, laje, forros, paredes, rodapés, cantoneiras e fundação.

Tudo deriva de `layout`. As paredes descem para dentro do piso e da laje (e a laje do
andar de cima repousa sobre elas) para que a luz da lanterna, que projeta sombra, não
vaze por frestas de encontro entre peças.
"""
from .. import conventions as C
from .. import layout
from . import floors, trim
from .meshkit import MeshBuilder
from .shell_geometry import exterior_corners

SINK_INTO_FLOOR = {0: 0.12, 1: 0.25}   # o andar 1 desce até o topo das paredes do térreo
FOUNDATION_DEPTH = 0.5
FOUNDATION_TOP = 0.12
FOUNDATION_PROUD = 0.03


def build(ctx):
    build_floors(ctx)
    build_slab_edges(ctx)
    build_ceilings(ctx)
    for level in (0, 1):
        build_walls(ctx, level)
        trim.build_trim(ctx, level)
    build_foundation(ctx)
    ctx.log("casca: pisos, laje, forros, paredes, rodapés e fundação")


# --------------------------------------------------------------------------
# Pisos, laje e forros
# --------------------------------------------------------------------------
def build_floors(ctx):
    """Um objeto por (andar, tipo de piso): o som dos passos lê `sa_surface` do objeto."""
    for level in (0, 1):
        floors.build_level_floors(ctx, level, C.COL_WORLD)


def build_slab_edges(ctx):
    """Cantos da laje ao redor do furo da escada (visíveis de baixo e de cima)."""
    hole = layout.STAIRS.hole
    z0, z1 = layout.SLAB_BOTTOM, layout.LEVEL_Z[1]
    builder = MeshBuilder("Slab_Edges")
    edges = {
        "-x": (hole.x1, hole.y0, hole.x1, hole.y1),
        "+y": (hole.x0, hole.y0, hole.x1, hole.y0),
        "-y": (hole.x0, hole.y1, hole.x1, hole.y1),
    }
    everything = ("-x", "+x", "-y", "+y", "-z", "+z")
    for face, (x0, y0, x1, y1) in edges.items():
        material = "stairs_riser" if face == "-y" else "trim_white"
        builder.box(x0, y0, z0, x1, y1, z1, material, skip=tuple(f for f in everything if f != face))
    builder.build(ctx, C.COL_WORLD, collision=True)


def build_ceilings(ctx):
    """Forros voltados para baixo. Não colidem: o jogador nunca chega neles."""
    for level in (0, 1):
        z = layout.CEIL_Z[level]
        builder = MeshBuilder(f"Ceiling_L{level}")
        for _, rect in layout.ceiling_rects(level):
            builder.quad((rect.x0, rect.y0, z), (rect.x0, rect.y1, z), (rect.x1, rect.y1, z),
                         (rect.x1, rect.y0, z), "ceiling")
        builder.build(ctx, C.COL_WORLD)


# --------------------------------------------------------------------------
# Paredes
# --------------------------------------------------------------------------
def _key(axis, pos, value):
    return (axis, round(pos, 3), round(value, 3))


def _opening_edges(level):
    """Bordas de vãos: peças que terminam nelas mostram a face de batente (reveal)."""
    starts, ends = set(), set()
    for op in layout.OPENINGS.values():
        if op.level == level:
            starts.add(_key(op.axis, op.pos, op.a))
            ends.add(_key(op.axis, op.pos, op.b))
    return starts, ends


def _side_material(room_id):
    return layout.ROOMS[room_id].wall_mat if room_id else "wall_siding_ext"


def _piece_box(piece):
    half = piece.thickness / 2
    if piece.axis == "x":
        return piece.a, piece.pos - half, piece.b, piece.pos + half
    return piece.pos - half, piece.a, piece.pos + half, piece.b


def _add_wall_piece(builder, piece, opening_starts, opening_ends):
    x0, y0, x1, y1 = _piece_box(piece)
    lo_face, hi_face, end_lo, end_hi = ("-y", "+y", "-x", "+x") if piece.axis == "x" else ("-x", "+x", "-y", "+y")
    sinks = piece.kind in ("full", "sill")
    z0 = piece.z0 - (SINK_INTO_FLOOR[piece.level] if sinks else 0.0)
    visible = {lo_face, hi_face}
    if piece.kind == "lintel":
        visible.add("-z")
    if piece.kind == "sill":
        visible.add("+z")
    if _key(piece.axis, piece.pos, piece.b) in opening_starts:
        visible.add(end_hi)
    if _key(piece.axis, piece.pos, piece.a) in opening_ends:
        visible.add(end_lo)
    builder.box(x0, y0, z0, x1, y1, piece.z1, "trim_white",
                skip=tuple(f for f in ("-x", "+x", "-y", "+y", "-z", "+z") if f not in visible),
                face_materials={lo_face: _side_material(piece.room_lo), hi_face: _side_material(piece.room_hi)})


def build_walls(ctx, level):
    starts, ends = _opening_edges(level)
    builder = MeshBuilder(f"Walls_L{level}")
    for piece in layout.wall_pieces(level):
        _add_wall_piece(builder, piece, starts, ends)
    builder.build(ctx, C.COL_WORLD, collision=True)


# --------------------------------------------------------------------------
# Fundação de tijolo aparente
# --------------------------------------------------------------------------
# Face do bloco de fundação que encosta na parede, por (eixo da parede, sentido para fora).
_INNER_FACE = {("x", 1): "-y", ("x", -1): "+y", ("y", 1): "-x", ("y", -1): "+x"}


def build_foundation(ctx):
    corners = exterior_corners(0)
    half = layout.WALL_T_EXT / 2
    reach = half + FOUNDATION_PROUD
    builder = MeshBuilder("Foundation")
    for piece in layout.wall_pieces(0):
        if not piece.exterior or piece.kind not in ("full", "sill"):
            continue
        outward = -1 if not piece.room_lo else 1
        lo_end = _corner_at(corners, piece, piece.a)
        hi_end = _corner_at(corners, piece, piece.b)
        a, b = piece.a - (reach if lo_end else 0.0), piece.b + (reach if hi_end else 0.0)
        near = half if outward > 0 else -half - FOUNDATION_PROUD
        far = near + FOUNDATION_PROUD
        inner_face = _INNER_FACE[(piece.axis, outward)]
        if piece.axis == "x":
            box = (a, piece.pos + near, b, piece.pos + far)
        else:
            box = (piece.pos + near, a, piece.pos + far, b)
        builder.box(box[0], box[1], -FOUNDATION_DEPTH, box[2], box[3], FOUNDATION_TOP, "wall_brick_ext",
                    skip=("-z", inner_face))
    builder.build(ctx, C.COL_WORLD)


def _corner_at(corners, piece, value):
    point = (value, piece.pos) if piece.axis == "x" else (piece.pos, value)
    return (round(point[0], 3), round(point[1], 3)) in corners
