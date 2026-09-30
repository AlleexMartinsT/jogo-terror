"""Telhados de duas águas (casa e garagem), empenas, chaminé e calhas.

A cumeeira corre ao longo de X, então as empenas ficam nas paredes leste e oeste. As duas
águas são lajes de 16 cm de espessura vertical: a face de cima é telha, a de baixo é forro
de beiral (trim_white). As empenas são triângulos que terminam dentro da espessura do telhado.
"""
from .. import conventions as C
from .. import layout
from .meshkit import MeshBuilder

DECK_THICKNESS = 0.16
GABLE_SINK = 0.10          # a base da empena entra no topo da parede
RIDGE_CAP_HALF = 0.16
GUTTER_DEPTH = 0.10
DOWNSPOUT = 0.07
BRICK = "wall_brick_ext"


class RoofShape:
    """Geometria de um telhado de duas águas sobre um retângulo em planta."""

    def __init__(self, x0, x1, y0, y1, eave_z, ridge_z, overhang):
        self.x0, self.x1 = x0, x1
        self.wall_y0, self.wall_y1 = y0, y1
        self.eave_z, self.ridge_z = eave_z, ridge_z
        self.overhang = overhang
        self.ridge_y = (y0 + y1) / 2
        self.slope = (ridge_z - eave_z) / (self.ridge_y - y0)

    def top_z(self, y):
        """Altura da face de cima da telha em y (vale também no beiral, abaixo do nível da parede)."""
        distance = min(y - self.wall_y0, self.wall_y1 - y)
        return self.eave_z + self.slope * distance


def _slab(builder, top_points, thickness):
    """Água de telhado: face de cima em telha, face de baixo e bordas em trim_white."""
    ax, ay, az = (top_points[1][i] - top_points[0][i] for i in range(3))
    bx, by, bz = (top_points[3][i] - top_points[0][i] for i in range(3))
    if ax * by - ay * bx < 0:
        top_points = top_points[::-1]
    bottom = [(x, y, z - thickness) for x, y, z in top_points]
    builder.polygon(top_points, "roof_shingle")
    builder.polygon(bottom[::-1], "trim_white")
    for i in range(4):
        j = (i + 1) % 4
        builder.quad(top_points[j], top_points[i], bottom[i], bottom[j], "trim_white")


def _deck(builder, shape, x0, x1):
    o = shape.overhang
    y_lo, y_hi = shape.wall_y0 - o, shape.wall_y1 + o
    ridge = shape.ridge_y
    for edge_y in (y_lo, y_hi):
        top_edge = shape.top_z(edge_y)
        _slab(builder, [(x0, edge_y, top_edge), (x1, edge_y, top_edge),
                        (x1, ridge, shape.ridge_z), (x0, ridge, shape.ridge_z)], DECK_THICKNESS)
    cap = [(ridge - RIDGE_CAP_HALF, shape.ridge_z - 0.07), (ridge, shape.ridge_z + 0.05),
           (ridge + RIDGE_CAP_HALF, shape.ridge_z - 0.07)]
    builder.extrude_profile(cap, "y", x0, x1, "roof_shingle")


def _gable(builder, shape, x, thickness):
    """Triângulo de empena em `x`; a ponta termina no forro do telhado."""
    half = thickness / 2
    base = shape.eave_z - GABLE_SINK
    apex = shape.ridge_z - DECK_THICKNESS
    y0, y1 = shape.wall_y0 - half, shape.wall_y1 + half
    builder.extrude_profile([(y0, base), (y1, base), (shape.ridge_y, apex)], "y", x - half, x + half,
                            "wall_siding_ext")


def _gable_vent(builder, shape, x, outward):
    """Veneziana da empena: moldura branca e frestas escuras."""
    face = x + outward * layout.WALL_T_EXT / 2
    n0, n1 = sorted((face, face + outward * 0.03))
    y, z = shape.ridge_y, shape.eave_z + (shape.ridge_z - shape.eave_z) * 0.42
    builder.box(n0, y - 0.32, z - 0.22, n1, y + 0.32, z + 0.22, "trim_white", skip=("-x" if outward > 0 else "+x",))
    n0, n1 = sorted((face + outward * 0.03, face + outward * 0.045))
    for i in range(4):
        zi = z - 0.16 + i * 0.105
        builder.box(n0, y - 0.26, zi, n1, y + 0.26, zi + 0.045, "black")


def _gutter_run(builder, x0, x1, y, outward, z_top):
    """Calha encostada na face do beiral: caixa de metal com o fundo mais escuro."""
    n0, n1 = sorted((y, y + outward * GUTTER_DEPTH))
    builder.box(x0, n0, z_top - 0.13, x1, n1, z_top - 0.03, "metal")


def _downspout(builder, x, y_gutter, outward, gutter_bottom, wall_y):
    """Tubo vertical, cotovelo inclinado até a parede e descida rente à parede."""
    y_pipe = y_gutter + outward * GUTTER_DEPTH / 2
    elbow = gutter_bottom - 0.5
    builder.box(x - DOWNSPOUT / 2, y_pipe - DOWNSPOUT / 2, elbow, x + DOWNSPOUT / 2, y_pipe + DOWNSPOUT / 2,
                gutter_bottom, "metal")
    wall_side = wall_y + outward * (layout.WALL_T_EXT / 2 + DOWNSPOUT / 2)
    builder.beam((x, y_pipe, elbow), (x, wall_side, elbow - 0.4), DOWNSPOUT, DOWNSPOUT, "metal")
    builder.box(x - DOWNSPOUT / 2, wall_side - DOWNSPOUT / 2, -0.1, x + DOWNSPOUT / 2, wall_side + DOWNSPOUT / 2,
                elbow - 0.4, "metal")


def _chimney(builder):
    """Chaminé de tijolo aparente na empena oeste, entre as janelas de baixo e de cima."""
    y0, y1 = 4.35, 5.65
    yc = (y0 + y1) / 2
    face = -layout.WALL_T_EXT / 2
    builder.box(face - 0.68, y0 - 0.05, -0.5, face + 0.02, y1 + 0.05, 3.2, BRICK, skip=("-z", "+x"))
    builder.box(face - 0.58, y0 + 0.08, 3.2, face + 0.02, y1 - 0.08, 3.5, BRICK, skip=("+x",))
    builder.box(face - 0.5, y0 + 0.15, 3.5, face + 0.02, y1 - 0.15, 8.35, BRICK, skip=("+x", "-z"))
    builder.box(face - 0.6, y0 + 0.07, 8.35, face + 0.06, y1 - 0.07, 8.5, "concrete", skip=("-z",))
    for offset in (-0.28, 0.28):
        builder.cylinder(face - 0.27, yc + offset, 8.5, 8.85, 0.11, "metal", sides=6)


def build(ctx):
    house = layout.ROOF
    main = RoofShape(0.0, 12.0, 0.0, 10.0, house["eave_z"], house["ridge_z"], house["overhang"])
    garage_rect = layout.ROOMS["garage"].rect
    garage = RoofShape(garage_rect.x0, garage_rect.x1, garage_rect.y0, garage_rect.y1,
                       house["garage_eave_z"], house["garage_ridge_z"], house["overhang"])
    decks = MeshBuilder("Roof_Main")
    _deck(decks, main, main.x0 - main.overhang, main.x1 + main.overhang)
    decks.build(ctx, C.COL_WORLD)

    garage_deck = MeshBuilder("Roof_Garage")
    _deck(garage_deck, garage, garage.x0, garage.x1 + garage.overhang)
    garage_deck.build(ctx, C.COL_WORLD)

    walls = MeshBuilder("Roof_Gables")
    for x, outward in ((main.x0, -1), (main.x1, 1)):
        _gable(walls, main, x, layout.WALL_T_EXT)
    _gable_vent(walls, main, main.x0, -1)
    _gable(walls, garage, garage.x1, layout.WALL_T_EXT)
    walls.build(ctx, C.COL_WORLD)

    chimney = MeshBuilder("Roof_Chimney")
    _chimney(chimney)
    chimney.build(ctx, C.COL_WORLD)

    gutters = MeshBuilder("Roof_Gutters")
    for shape, span in ((main, (main.x0 - main.overhang, main.x1 + main.overhang)),
                        (garage, (garage.x0, garage.x1 + garage.overhang))):
        for wall_y, outward in ((shape.wall_y0, -1), (shape.wall_y1, 1)):
            eave_y = wall_y + outward * shape.overhang
            top = shape.top_z(eave_y)
            _gutter_run(gutters, span[0], span[1], eave_y, outward, top - DECK_THICKNESS + 0.12)
        _downspout(gutters, span[1] - 0.35, shape.wall_y0 - shape.overhang, -1,
                   shape.top_z(shape.wall_y0 - shape.overhang) - DECK_THICKNESS - 0.02, shape.wall_y0)
    _downspout(gutters, main.x0 + 0.35, main.wall_y1 + main.overhang, 1,
               main.top_z(main.wall_y1 + main.overhang) - DECK_THICKNESS - 0.02, main.wall_y1)
    gutters.build(ctx, C.COL_WORLD)
    ctx.log("telhados, empenas, chaminé e calhas")
