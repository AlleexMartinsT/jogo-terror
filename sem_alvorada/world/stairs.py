"""Escada principal: degraus maciços, rodapé em degraus, corrimãos, balaústres e guarda-corpo do furo.

As alturas vêm de `layout.STAIRS`: o topo do degrau i (1..14) fica em i * rise, idêntico a
`layout.stairs_height`, que é o que o jogador e a IA usam para subir.
"""
from .. import conventions as C
from .. import layout
from .meshkit import MeshBuilder

WALL_FACE_X = 5.075          # face da parede oeste do hall (parede de 0,15 m em x=5)
SEAL_INTO_WALL = 0.02        # o degrau entra na parede para não deixar fresta
RAIL_HEIGHT = 0.9
RAIL_X = 6.09
BALUSTER = 0.035
NEWEL = 0.09
GUARD_HEIGHT = 0.9
COLLISION_THICKNESS = 0.06


def build(ctx):
    _build_steps(ctx)
    _build_railings(ctx)
    _build_rail_colliders(ctx)
    ctx.log(f"escada: {layout.STAIRS.treads} degraus, corrimão e guarda-corpo")


def _tread_top(stairs, i):
    return stairs.z0 + i * stairs.rise


def _build_steps(ctx):
    stairs = layout.STAIRS
    depth = stairs.tread_depth
    builder = MeshBuilder("Stairs_Main")
    x0 = WALL_FACE_X - SEAL_INTO_WALL
    for i in range(1, stairs.treads + 1):
        y0 = stairs.y0 + (i - 1) * depth
        top = _tread_top(stairs, i)
        skip = ["-z", "-x"]
        if i < stairs.treads:
            skip.append("+y")
        builder.box(x0, y0, stairs.z0, stairs.x1, y0 + depth, top, "stairs_wood",
                    skip=tuple(skip), face_materials={"+x": "trim_white"})
        builder.box(WALL_FACE_X, y0, top, WALL_FACE_X + 0.02, y0 + depth, top + 0.11, "trim_white", skip=("-x", "-z"))
    stairs_obj = builder.build(ctx, C.COL_WORLD, collision=True)
    stairs_obj[C.P_SURFACE] = "stairs"


def _rail_z(stairs, y):
    """Altura do corrimão inclinado: paralelo à linha dos bocais, RAIL_HEIGHT acima."""
    slope = stairs.rise / stairs.tread_depth
    return stairs.rise + RAIL_HEIGHT + slope * (y - stairs.y0)


def _build_railings(ctx):
    stairs = layout.STAIRS
    builder = MeshBuilder("Stairs_Railing")
    _sloped_rails(builder, stairs)
    _flat_guard(builder, stairs)
    builder.build(ctx, C.COL_WORLD)


def _sloped_rails(builder, stairs):
    for x in (RAIL_X, WALL_FACE_X + 0.04):
        builder.beam((x, stairs.y0, _rail_z(stairs, stairs.y0)), (x, stairs.y1, _rail_z(stairs, stairs.y1)),
                     0.055, 0.05, "wood_dark")
    for i in range(1, stairs.treads + 1):
        y = stairs.y0 + (i - 0.5) * stairs.tread_depth
        builder.box(RAIL_X - BALUSTER / 2, y - BALUSTER / 2, _tread_top(stairs, i),
                    RAIL_X + BALUSTER / 2, y + BALUSTER / 2, _rail_z(stairs, y) - 0.025, "wood_dark", skip=("-z",))
    builder.box(RAIL_X - NEWEL / 2, stairs.y0 - NEWEL / 2, 0.0, RAIL_X + NEWEL / 2, stairs.y0 + NEWEL / 2,
                _rail_z(stairs, stairs.y0) + 0.12, "wood_dark", skip=("-z",))


def _flat_guard(builder, stairs):
    """Guarda-corpo do andar de cima ao redor do furo: lado leste e lado sul."""
    floor = layout.LEVEL_Z[1]
    top = floor + GUARD_HEIGHT
    y_south, y_north = stairs.y0 + 0.04, stairs.y1 - 0.04
    builder.beam((RAIL_X, y_south, top), (RAIL_X, y_north, top), 0.06, 0.05, "wood_dark")
    builder.beam((WALL_FACE_X, y_south, top), (RAIL_X, y_south, top), 0.06, 0.05, "wood_dark")
    for y in _spaced(y_south, y_north, 0.14):
        builder.box(RAIL_X - BALUSTER / 2, y - BALUSTER / 2, floor, RAIL_X + BALUSTER / 2, y + BALUSTER / 2,
                    top - 0.025, "wood_dark", skip=("-z",))
    for x in _spaced(WALL_FACE_X + 0.05, RAIL_X, 0.14):
        builder.box(x - BALUSTER / 2, y_south - BALUSTER / 2, floor, x + BALUSTER / 2, y_south + BALUSTER / 2,
                    top - 0.025, "wood_dark", skip=("-z",))
    for y in (y_south, y_north):
        builder.box(RAIL_X - NEWEL / 2, y - NEWEL / 2, floor, RAIL_X + NEWEL / 2, y + NEWEL / 2,
                    top + 0.1, "wood_dark", skip=("-z",))


def _spaced(start, end, step):
    count = max(1, round((end - start) / step))
    return [start + (end - start) * (i + 0.5) / count for i in range(count)]


def _build_rail_colliders(ctx):
    """Paredes invisíveis no lugar dos corrimãos (a IA também as lê como obstáculos)."""
    stairs = layout.STAIRS
    east = MeshBuilder("COL_Stairs_RailE")
    east.box(stairs.x1, stairs.y0, 0.0, stairs.x1 + COLLISION_THICKNESS, stairs.y1,
             layout.LEVEL_Z[1] + GUARD_HEIGHT, "black")
    south = MeshBuilder("COL_Stairs_RailS")
    south.box(stairs.hole.x0, stairs.y0 - COLLISION_THICKNESS, layout.LEVEL_Z[1], stairs.x1, stairs.y0,
              layout.LEVEL_Z[1] + GUARD_HEIGHT, "black")
    for builder in (east, south):
        builder.build(ctx, C.COL_COLLISION, collision=True, hide=True)
