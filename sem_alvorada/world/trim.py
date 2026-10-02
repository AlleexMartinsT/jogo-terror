"""Rodapés e sancas varridos de perfil, e as cantoneiras da fachada.

O rodapé acompanha cada peça de parede pelas duas faces, parando na guarnição das portas e arcos (que é mais
alta e mais saliente que ele). Sob as janelas ele passa direto. A sanca corre no encontro com o forro, exceto
no banheiro e na garagem.
"""
from .. import conventions as C
from .. import layout
from . import moldings
from .modelkit import PROFILED, ModelBuilder
from .shell_geometry import exterior_corners

NO_CROWN_ROOMS = ("bath", "garage")
CORNER_PROUD = 0.02
FOUNDATION_TOP = 0.12
CASING_END = moldings.CASING_WIDTH + 0.004     # o rodapé para na borda de fora da guarnição


def build_trim(ctx, level):
    builder = ModelBuilder(f"Trim_L{level}", PROFILED)
    door_edges = _door_edges(level)
    for piece in layout.wall_pieces(level):
        if piece.room_lo:
            _wall_side(builder, piece, "lo", piece.room_lo, door_edges)
        if piece.room_hi:
            _wall_side(builder, piece, "hi", piece.room_hi, door_edges)
    for point, (dx, dy, top) in exterior_corners(level).items():
        _corner_post(builder, point, dx, dy, top, level)
    return builder.build(ctx, C.COL_WORLD)


def _door_edges(level):
    """Bordas (eixo, pos, u) de vãos de porta e arco: o rodapé pára antes delas, por causa da guarnição."""
    edges = set()
    for op in layout.OPENINGS.values():
        if op.level == level and op.kind in ("door", "arch"):
            edges.add((op.axis, round(op.pos, 3), round(op.a, 3)))
            edges.add((op.axis, round(op.pos, 3), round(op.b, 3)))
    return edges


def _wall_side(builder, piece, side, room_id, door_edges):
    half = piece.thickness / 2
    face = piece.pos - half if side == "lo" else piece.pos + half
    sign = -1.0 if side == "lo" else 1.0
    if piece.kind in ("full", "sill"):
        for u0, u1 in _spans(piece, side, door_edges):
            moldings.baseboard_run(builder, _point(piece, u0, face, piece.z0), _point(piece, u1, face, piece.z0),
                                   _outward(piece, sign), "trim_white")
    if piece.kind in ("full", "lintel") and room_id not in NO_CROWN_ROOMS:
        z = layout.CEIL_Z[piece.level] - moldings.CROWN_REACH
        moldings.crown_run(builder, _point(piece, piece.a, face, z), _point(piece, piece.b, face, z),
                           _outward(piece, sign), "trim_white")


def _point(piece, u, n, z):
    return (u, n, z) if piece.axis == "x" else (n, u, z)


def _outward(piece, sign):
    return (0.0, sign, 0.0) if piece.axis == "x" else (sign, 0.0, 0.0)


def _spans(piece, side, door_edges):
    """Trechos (u0, u1) do rodapé de uma peça: encurtados nas pontas que encostam em porta ou arco e
    recortados onde a escada do hall térreo encosta na parede (a escada tem rodapé próprio)."""
    start, end = piece.a, piece.b
    if (piece.axis, round(piece.pos, 3), round(piece.a, 3)) in door_edges:
        start += CASING_END
    if (piece.axis, round(piece.pos, 3), round(piece.b, 3)) in door_edges:
        end -= CASING_END
    spans = [(start, end)]
    stairs = layout.STAIRS
    if piece.level == 0 and piece.axis == "y" and abs(piece.pos - stairs.hole.x0) < 1e-6 and side == "hi":
        lo, hi = stairs.y0 - 0.1, stairs.y1 + 0.1
        spans = [(s, e) for s0, e0 in spans for s, e in ((s0, min(e0, lo)), (max(s0, hi), e0))]
    return [(s, e) for s, e in spans if e - s > 0.04]


def _corner_post(builder, point, inward_x, inward_y, top, level):
    half = layout.WALL_T_EXT / 2
    x, y = point
    x0, x1 = (x - half - CORNER_PROUD, x + half) if inward_x > 0 else (x - half, x + half + CORNER_PROUD)
    y0, y1 = (y - half - CORNER_PROUD, y + half) if inward_y > 0 else (y - half, y + half + CORNER_PROUD)
    base = FOUNDATION_TOP if level == 0 else layout.LEVEL_Z[1]
    builder.box(x0, y0, base, x1, y1, top, "trim_white", skip=("-z", "+z"))
