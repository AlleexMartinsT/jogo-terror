"""Arcos de passagem entre cômodos: vão de cantos superiores arredondados com guarnição curva.

O vão do layout é um retângulo (`layout.ARCH_H` de altura). Os cantos de cima são arredondados por um enchimento
(o "pendente") entre o canto e um quarto de círculo, e a guarnição acompanha esse contorno inteiro em uma única
varredura, com o perfil das portas em escala menor.
"""
import math

from mathutils import Vector

from .. import conventions as C
from .. import layout
from . import moldings
from .modelkit import PROFILED, ModelBuilder
from .wallgeom import along, normal, wall_point

CORNER_RADIUS = 0.35
CASING_WIDTH = 0.065
ARC_STEPS = 6


def build(ctx, op, piece):
    builder = ModelBuilder(f"ArchFrame_{op.id}", PROFILED)
    floor = layout.LEVEL_Z[op.level]
    top = floor + op.height
    half = piece.thickness / 2
    for corner_u, direction in ((op.a, 1.0), (op.b, -1.0)):
        _spandrel(builder, op, corner_u, direction, top, half)
    outline = _outline(op, floor, top)
    for side in (-1, 1):
        n = op.pos + side * half
        points = [wall_point(op, u, n, z) for u, z in outline]
        sides = _outward(op, outline)
        scale = CASING_WIDTH / moldings.CASING_WIDTH
        builder.sweep([(u * scale, v) for u, v in moldings.CASING_PROFILE], points, sides, normal(op) * side,
                      "trim_white")
    return builder.build(ctx, C.COL_WORLD)


def _spandrel(builder, op, corner_u, direction, top, half):
    """Enchimento entre o canto do retângulo e o arco: sólido de espessura igual à da parede."""
    centre_u, centre_z = corner_u + direction * CORNER_RADIUS, top - CORNER_RADIUS
    arc = [(centre_u - direction * CORNER_RADIUS * math.sin(t), centre_z + CORNER_RADIUS * math.cos(t))
           for t in (i * (math.pi / 2) / ARC_STEPS for i in range(ARC_STEPS + 1))]
    outline = [(corner_u, top)] + arc
    rings = [[wall_point(op, u, op.pos + n * half, z) for u, z in outline] for n in (-1, 1)]
    builder.loft(rings, "trim_white")


def _outline(op, floor, top):
    """Contorno (u, z) do vão, do piso em um lado ao piso no outro, passando pelos dois cantos arredondados."""
    outline = [(op.a, floor), (op.a, top - CORNER_RADIUS)]
    for i in range(1, ARC_STEPS + 1):
        angle = math.pi - (math.pi / 2) * i / ARC_STEPS
        outline.append(_on_corner(op.a + CORNER_RADIUS, top, angle))
    for i in range(ARC_STEPS + 1):
        angle = math.pi / 2 - (math.pi / 2) * i / ARC_STEPS
        outline.append(_on_corner(op.b - CORNER_RADIUS, top, angle))
    outline.append((op.b, floor))
    return outline


def _on_corner(centre_u, top, angle):
    """Ponto do quarto de círculo de um canto, de centro (centre_u, top - raio)."""
    return (centre_u + CORNER_RADIUS * math.cos(angle), top - CORNER_RADIUS + CORNER_RADIUS * math.sin(angle))


def _outward(op, outline):
    """Para cada trecho do contorno, o vetor unitário (no plano da parede) que aponta para fora do vão."""
    vectors = []
    for (u0, z0), (u1, z1) in zip(outline, outline[1:]):
        du, dz = u1 - u0, z1 - z0
        length = math.hypot(du, dz) or 1.0
        vectors.append(along(op) * (-dz / length) + Vector((0.0, 0.0, 1.0)) * (du / length))
    return vectors
