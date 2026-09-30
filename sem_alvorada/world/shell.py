"""Casca da casa: pisos, laje, forros, paredes, rodapés, cantoneiras e fundação.

Tudo deriva de `layout`. As paredes descem para dentro do piso e da laje (e a laje do
andar de cima repousa sobre elas) para que a luz da lanterna, que projeta sombra, não
vaze por frestas de encontro entre peças.
"""
from collections import defaultdict

from .. import conventions as C
from .. import layout
from .meshkit import MeshBuilder

SINK_INTO_FLOOR = {0: 0.12, 1: 0.25}   # o andar 1 desce até o topo das paredes do térreo
BASEBOARD_HEIGHT = 0.11
BASEBOARD_DEPTH = 0.022
CROWN_HEIGHT = 0.07
CROWN_DEPTH = 0.045
CORNER_PROUD = 0.02
FOUNDATION_DEPTH = 0.5
FOUNDATION_TOP = 0.12
FOUNDATION_PROUD = 0.03
STAIR_CLEARANCE = 0.1

NO_CROWN_ROOMS = ("bath", "garage")


def build(ctx):
    build_floors(ctx)
    build_slab_edges(ctx)
    build_ceilings(ctx)
    for level in (0, 1):
        build_walls(ctx, level)
        build_trim(ctx, level)
    build_foundation(ctx)
    ctx.log("casca: pisos, laje, forros, paredes, rodapés e fundação")


# --------------------------------------------------------------------------
# Pisos, laje e forros
# --------------------------------------------------------------------------
def build_floors(ctx):
    """Um objeto por (andar, tipo de piso): o som dos passos lê `sa_surface` do objeto."""
    for level in (0, 1):
        z = layout.LEVEL_Z[level]
        builders = {}
        for room_id, rect in layout.floor_rects(level):
            room = layout.ROOMS[room_id]
            builder = builders.setdefault(room.surface, MeshBuilder(f"Floor_L{level}_{room.surface}"))
            builder.quad((rect.x0, rect.y0, z), (rect.x1, rect.y0, z), (rect.x1, rect.y1, z),
                         (rect.x0, rect.y1, z), room.floor_mat)
        for surface, builder in builders.items():
            obj = builder.build(ctx, C.COL_WORLD, collision=True)
            obj[C.P_SURFACE] = surface


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
        builder.box(x0, y0, z0, x1, y1, z1, "trim_white", skip=tuple(f for f in everything if f != face))
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
# Rodapés, sancas e cantoneiras
# --------------------------------------------------------------------------
def _strip(piece, side, depth):
    """Retângulo 2D de uma faixa colada à face `side` ('lo'|'hi') da peça."""
    half = piece.thickness / 2
    near, far = (-half - depth, -half) if side == "lo" else (half, half + depth)
    if piece.axis == "x":
        return piece.a, piece.pos + near, piece.b, piece.pos + far
    return piece.pos + near, piece.a, piece.pos + far, piece.b


def _stairs_exclusion(piece, side):
    """Faixa de y em que o rodapé do hall térreo colide com a escada encostada na parede."""
    if piece.level == 0 and piece.axis == "y" and abs(piece.pos - layout.STAIRS.hole.x0) < 1e-6 and side == "hi":
        return layout.STAIRS.y0 - STAIR_CLEARANCE, layout.STAIRS.y1 + STAIR_CLEARANCE
    return None


def _clipped(piece, rect, exclusion):
    """Recorta a faixa retirando o trecho `exclusion` ao longo do eixo da parede."""
    x0, y0, x1, y1 = rect
    if exclusion is None:
        return [rect]
    lo, hi = exclusion
    a, b = (x0, x1) if piece.axis == "x" else (y0, y1)
    spans = [(a, min(b, lo)), (max(a, hi), b)]
    spans = [(s, e) for s, e in spans if e - s > 0.02]
    if piece.axis == "x":
        return [(s, y0, e, y1) for s, e in spans]
    return [(x0, s, x1, e) for s, e in spans]


def _add_trim_strips(builder, piece, side, room_id):
    if piece.kind in ("full", "sill"):
        for x0, y0, x1, y1 in _clipped(piece, _strip(piece, side, BASEBOARD_DEPTH), _stairs_exclusion(piece, side)):
            builder.box(x0, y0, piece.z0, x1, y1, piece.z0 + BASEBOARD_HEIGHT, "trim_white", skip=("-z",))
    if piece.kind in ("full", "lintel") and room_id not in NO_CROWN_ROOMS:
        top = layout.CEIL_Z[piece.level]
        x0, y0, x1, y1 = _strip(piece, side, CROWN_DEPTH)
        builder.box(x0, y0, top - CROWN_HEIGHT, x1, y1, top, "trim_white", skip=("+z",))


def exterior_corners(level):
    """Cantos convexos da fachada: {(x, y): (dx, dy, topo)}, (dx, dy) aponta para dentro."""
    ends = defaultdict(lambda: {"x": set(), "y": set(), "top": 0.0})
    for piece in layout.wall_pieces(level):
        if not piece.exterior:
            continue
        for value, direction in ((piece.a, 1), (piece.b, -1)):
            point = (value, piece.pos) if piece.axis == "x" else (piece.pos, value)
            record = ends[(round(point[0], 3), round(point[1], 3))]
            record[piece.axis].add(direction)
            record["top"] = max(record["top"], piece.z1)
    corners = {}
    for (x, y), record in ends.items():
        if len(record["x"]) != 1 or len(record["y"]) != 1:
            continue
        dx, dy = next(iter(record["x"])), next(iter(record["y"]))
        outside = layout.room_at(x - dx * 0.5, y - dy * 0.5, layout.LEVEL_Z[level] + 0.1)
        if outside is None:
            corners[(x, y)] = (dx, dy, record["top"])
    return corners


def _add_corner_post(builder, point, inward_x, inward_y, top, level):
    half = layout.WALL_T_EXT / 2
    x, y = point
    x0, x1 = (x - half - CORNER_PROUD, x + half) if inward_x > 0 else (x - half, x + half + CORNER_PROUD)
    y0, y1 = (y - half - CORNER_PROUD, y + half) if inward_y > 0 else (y - half, y + half + CORNER_PROUD)
    base = FOUNDATION_TOP if level == 0 else layout.LEVEL_Z[1]
    builder.box(x0, y0, base, x1, y1, top, "trim_white", skip=("-z", "+z"))


def build_trim(ctx, level):
    builder = MeshBuilder(f"Trim_L{level}")
    for piece in layout.wall_pieces(level):
        if piece.room_lo:
            _add_trim_strips(builder, piece, "lo", piece.room_lo)
        if piece.room_hi:
            _add_trim_strips(builder, piece, "hi", piece.room_hi)
    for point, (dx, dy, top) in exterior_corners(level).items():
        _add_corner_post(builder, point, dx, dy, top, level)
    builder.build(ctx, C.COL_WORLD)


# --------------------------------------------------------------------------
# Fundação de tijolo aparente
# --------------------------------------------------------------------------
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
        inner_face = "-y" if piece.axis == "x" and outward > 0 else "+y" if piece.axis == "x" else \
                     "-x" if outward > 0 else "+x"
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
