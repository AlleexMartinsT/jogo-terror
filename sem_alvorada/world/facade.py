"""Fachada de tábuas sobrepostas (clapboard): cada tábua é uma peça em cunha, com sombra na junta de baixo.

As tábuas cobrem a face externa de todas as paredes de fora (inclusive as empenas), em fiadas contínuas do
alicerce ao beiral. Elas param no caixilho das janelas e portas (a guarnição é mais saliente que a tábua) e
antes das cantoneiras. Cada tábua tem comprimento sorteado (2,4 a 3,8 m): a emenda vertical aparece, sempre
em lugares diferentes de uma fiada para a seguinte.
"""
import numpy as np

from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401
from . import roof
from .shell_geometry import exterior_corners

BOARD_HEIGHT = 0.145
LIP = 0.026                 # espessura da borda de baixo
THIN = 0.007                # espessura da borda de cima
Z_BASE = 0.11               # topo do alicerce de tijolo
CORNER_SETBACK = 0.150
MATERIAL = "ext_board"
UV_PER_METER = 0.5          # a imagem cobre 2 m de tábua


def _outward(piece):
    """+1 se a face de fora da parede aponta para +normal, -1 se para -normal."""
    return 1.0 if piece.room_lo else -1.0


def _end_margin(piece, value, corners):
    point = (value, piece.pos) if piece.axis == "x" else (piece.pos, value)
    return CORNER_SETBACK if (round(point[0], 3), round(point[1], 3)) in corners else 0.0


def _point(axis, along, pos, z):
    return (along, pos, z) if axis == "x" else (pos, along, z)


def _board(m, rng, axis, pos, outward, a, b, z0, z1, h0):
    """Uma tábua entre `a` e `b` ao longo da parede, com a cunha dos dois lados já cortada em z0..z1.

    `h0` é a altura do pé da tábua inteira; se a tábua foi cortada pela verga/peitoril, z0 > h0."""
    def depth(z):
        return LIP + (THIN - LIP) * (z - h0) / BOARD_HEIGHT

    p = lambda s, n, z: _point(axis, s, pos + outward * n, z)           # noqa: E731
    u_start = rng.random() + a * UV_PER_METER
    u_end = u_start + (b - a) * UV_PER_METER
    v0, v1 = (z0 - h0) / BOARD_HEIGHT, (z1 - h0) / BOARD_HEIGHT
    front = [p(a, depth(z0), z0), p(b, depth(z0), z0), p(b, depth(z1), z1), p(a, depth(z1), z1)]
    direction = _point(axis, 0.0, outward, 0.0)
    ext.poly_out(m, front, MATERIAL, (direction[0], direction[1], 0.3), uv=[(u_start, v0), (u_end, v0), (u_end, v1), (u_start, v1)])
    if z0 <= h0 + 1e-6:
        under = [p(a, 0.0, z0), p(b, 0.0, z0), p(b, depth(z0), z0), p(a, depth(z0), z0)]
        ext.poly_out(m, under, MATERIAL, (0, 0, -1), uv=[(u_start, 0.0), (u_end, 0.0), (u_end, 0.04), (u_start, 0.04)])
    for s in (a, b):
        cap = [p(s, 0.0, z0), p(s, depth(z0), z0), p(s, depth(z1), z1), p(s, 0.0, z1)]
        ext.poly_out(m, cap, MATERIAL, _point(axis, 1.0 if s == b else -1.0, 0.0, 0.0), uv=[(0.1, 0.0), (0.12, 0.0), (0.12, 0.1), (0.1, 0.1)])


def _course_segments(rng, start, end):
    """Divide o trecho [start, end] em tábuas de 2,4 a 3,8 m, com uma folga fina entre elas."""
    cursor, pieces = start, []
    while cursor < end - 0.02:
        length = rng.uniform(2.4, 3.8)
        stop = min(cursor + length, end)
        if end - stop < 0.35:
            stop = end
        pieces.append((cursor, stop - 0.003))
        cursor = stop
    return pieces


def _cover_piece(m, rng, piece, corners):
    """Tábuas de um trecho de parede: todas as fiadas que cruzam [z0, z1] da peça."""
    outward = _outward(piece)
    a = piece.a + _end_margin(piece, piece.a, corners)
    b = piece.b - _end_margin(piece, piece.b, corners)
    if b - a < 0.05:
        return
    pos = piece.pos + outward * piece.thickness / 2
    z_floor = max(piece.z0, Z_BASE)
    first = int((z_floor - Z_BASE) // BOARD_HEIGHT)
    k = first
    while Z_BASE + k * BOARD_HEIGHT < piece.z1 - 0.01:
        h0 = Z_BASE + k * BOARD_HEIGHT
        z0, z1 = max(h0, piece.z0), min(h0 + BOARD_HEIGHT, piece.z1)
        if z1 - z0 > 0.012:
            for s0, s1 in _course_segments(rng, a, b):
                _board(m, rng, piece.axis, pos, outward, s0, s1, z0, z1, h0)
        k += 1


def _cover_gable(m, rng, shape, x, outward_x):
    """Tábuas da empena: cada fiada tem o comprimento do triângulo àquela altura."""
    half = layout.WALL_T_EXT / 2
    base, apex = shape.eave_z - roof.GABLE_SINK, shape.ridge_z - roof.DECK_THICKNESS
    y_mid = shape.ridge_y
    half_width = (shape.wall_y1 - shape.wall_y0) / 2 + half
    pos = x + outward_x * half
    k = int((base - Z_BASE) // BOARD_HEIGHT)
    while Z_BASE + k * BOARD_HEIGHT < apex - 0.03:
        h0 = Z_BASE + k * BOARD_HEIGHT
        z0, z1 = max(h0, base), min(h0 + BOARD_HEIGHT, apex)
        reach = half_width * max(0.0, (apex - z0) / (apex - base)) - 0.03
        if z1 - z0 > 0.012 and reach > 0.1:
            for s0, s1 in _course_segments(rng, y_mid - reach, y_mid + reach):
                _board(m, rng, "y", pos, outward_x, s0, s1, z0, z1, h0)
        k += 1


def build(ctx):
    ext.start(ctx)
    rng = ext.rng_for(ctx, "facade")
    m = ext.builder("Facade_Clapboard", ext.PROFILED)
    for level in (0, 1):
        corners = exterior_corners(level)
        for piece in layout.wall_pieces(level):
            if piece.exterior:
                _cover_piece(m, rng, piece, corners)
    main, garage = roof.main_shape(), roof.garage_shape()
    for x, outward in ((main.x0, -1.0), (main.x1, 1.0)):
        _cover_gable(m, rng, main, x, outward)
    _cover_gable(m, rng, garage, garage.x1, 1.0)
    ext.emit(ctx, m)
    ctx.log(f"fachada: {m.tri_count} triângulos de tábuas")
