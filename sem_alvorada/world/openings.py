"""Vãos da casa: despacha portas (`doors`) e janelas (`windows`), e monta os arcos e o portão da garagem.

As conversões de coordenadas de parede e a guarnição simples usadas pelo portão ficam aqui.
"""
from .. import layout
from . import arches, doors, garage_door, windows

CASING_WIDTH = 0.075
CASING_PROUD = 0.03


def build(ctx):
    pieces = _opening_pieces()
    for op in layout.OPENINGS.values():
        piece = pieces[op.id]
        if op.kind == "door":
            doors.build(ctx, op, piece)
        elif op.kind == "arch":
            arches.build(ctx, op, piece)
        elif op.kind == "window":
            windows.build(ctx, op, piece)
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
# Portão da garagem
# --------------------------------------------------------------------------
def build_rollup(ctx, op, piece):
    """Portão seccional da garagem: ver `garage_door`."""
    garage_door.build(ctx, op, piece)
