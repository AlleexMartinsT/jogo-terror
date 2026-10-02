"""Geometria de parede compartilhada pelas peças que se apoiam nos vãos (portas, janelas, arcos, trilhos).

Um vão (`layout.Opening`) corre ao longo de um eixo ('x' ou 'y') da parede. Aqui moram as conversões entre o
sistema da parede (u ao longo dela, n na normal, z) e o de mundo.
"""
from mathutils import Vector

from .. import layout


def wall_point(op, u, n, z):
    """(u ao longo da parede, n na normal, z) -> ponto de mundo."""
    return (u, n, z) if op.axis == "x" else (n, u, z)


def along(op):
    """Vetor unitário ao longo da parede."""
    return Vector((1.0, 0.0, 0.0)) if op.axis == "x" else Vector((0.0, 1.0, 0.0))


def normal(op):
    """Vetor unitário da normal da parede (+n)."""
    return Vector((0.0, 1.0, 0.0)) if op.axis == "x" else Vector((1.0, 0.0, 0.0))


def inward_sign(piece):
    """Sinal da normal que aponta para dentro da casa (parede exterior: o lado que tem cômodo)."""
    return 1 if not piece.room_lo else -1


def opening_pieces():
    """Uma peça de verga por abertura: dela saem a espessura da parede e o lado exterior."""
    found = {}
    for level in (0, 1):
        for piece in layout.wall_pieces(level):
            if piece.opening:
                found[piece.opening] = piece
    return found


def wall_box(builder, op, u0, u1, n0, n1, z0, z1, material, skip=()):
    """Caixa em coordenadas da parede (u, n, z) sobre qualquer construtor com `box` em eixos de mundo."""
    if op.axis == "x":
        builder.box(u0, n0, z0, u1, n1, z1, material, skip=skip)
    else:
        builder.box(n0, u0, z0, n1, u1, z1, material, skip=skip)
