"""Armazenamento da garagem: painel de ferramentas, estante de aço, caixas de papelão, latas e potes.

Estante de 2,5 x 0,4 x 1,85 m com cinco prateleiras; o degrau de 1 m deixa livre o trecho onde repousa o guia do
reboque (`Item_NOTE_7`), e a tábua dessa prateleira tem o topo a 1,005 m.
"""
import math

from . import garage_tools as tools
from . import kg_silhouettes as shapes
from .kg_shapes import segments

SHELF_TIERS = (0.30, 0.65, 1.00, 1.35, 1.70)
NOTE_TIER = 1.00
NOTE_TIER_LIMIT = 0.55
LABELS = {"toy_blue": "kg_label_blue", "toy_green": "kg_label_green", "toy_red": "kg_label_red", "toy_yellow": "kg_label_red"}
BOX_LABELS = ("kg_box_plain", "kg_box_toys", "kg_box_xmas", "kg_box_docs", "kg_box_kitchen", "kg_box_plain")


# ---------------------------------------------------------------------------
# Painel de ferramentas
# ---------------------------------------------------------------------------
def build_tool_panel(asm, rng, width=1.7, height=0.9):
    """Painel de chapa perfurada com as ferramentas penduradas; o contorno do martelo ficou só no painel.

    A origem fica no topo do painel (ele pende para baixo) e a frente em +Y.
    """
    asm.hard.box(0, 0.012, -height, width, 0.024, height, "kg_pegboard", uv=1 / 0.254)
    asm.hard.box(0, 0.026, -0.02, width + 0.02, 0.02, 0.04, "kg_pine")
    asm.hard.box(0, 0.026, -height + 0.02, width + 0.02, 0.02, 0.04, "kg_pine")
    for side in (-1, 1):
        asm.hard.box(side * (width / 2 + 0.002), 0.026, -height, 0.04, 0.02, height, "kg_pine")
    asm.round.panel(0, 0.0245, -height / 2, width, height, "kg_outline", "front")
    builders = {"wrench": tools.wrench, "pliers": tools.pliers, "saw": tools.saw,
                "driver_flat": lambda a: tools.screwdriver(a, "toy_yellow"),
                "driver_cross": lambda a: tools.screwdriver(a, "toy_red", phillips=True)}
    for name, (hang_x, hang_z, _outline) in shapes.PANEL_SLOTS.items():
        x, z = width / 2 - hang_x, hang_z - height      # X local cresce para a esquerda de quem olha
        with asm.at(x, 0.024, z):
            tools.peg(asm, 0.0, 0.0)
            if name != shapes.MISSING:
                builders[name](asm)
    with asm.at(0.62, 0.024, -0.1):
        tools.peg(asm, 0.0, 0.0)
        asm.round.tube_path([(0.0, 0.05, 0.0), (0.0, 0.07, -0.1), (0.0, 0.09, -0.2), (0.0, 0.07, -0.26), (0.0, 0.05, -0.2)], 0.012,
                            "kg_cord_orange", sides=8, resolution=6)


# ---------------------------------------------------------------------------
# Estante de aço
# ---------------------------------------------------------------------------
def build_shelves(asm, rng, width=2.5, depth=0.4, height=1.85):
    """Montantes de aço, tábuas apoiadas em travessas, contraventamento atrás e as caixas, latas e potes."""
    for x in (-width / 2 + 0.03, 0.0, width / 2 - 0.03):
        for y in (-depth / 2 + 0.02, depth / 2 - 0.02):
            asm.hard.box(x, y, 0.0, 0.04, 0.04, height, "kg_shelf_paint")
    for tier in SHELF_TIERS:
        asm.hard.box(0, 0, tier - 0.017, width - 0.08, depth - 0.02, 0.022, "kg_pine")
        for y in (-depth / 2 + 0.02, depth / 2 - 0.02):
            asm.hard.box(0, y, tier - 0.047, width - 0.04, 0.02, 0.03, "kg_shelf_paint")
    asm.hard.bar((-width / 2 + 0.05, -depth / 2 + 0.012, 0.32), (0.0 - 0.04, -depth / 2 + 0.012, 1.0), 0.016, "kg_shelf_paint")
    asm.hard.bar((0.04, -depth / 2 + 0.012, 0.32), (0.0 - 0.04 + 1.2, -depth / 2 + 0.012, 1.0), 0.016, "kg_shelf_paint")
    for tier in SHELF_TIERS:
        limit = NOTE_TIER_LIMIT if tier == NOTE_TIER else width / 2 - 0.08
        stock_tier(asm, rng, tier + 0.005, -width / 2 + 0.1, limit, depth)


def stock_tier(asm, rng, top, first, limit, depth):
    """Enche uma prateleira de `first` a `limit` com caixas, latas e potes escolhidos ao acaso, sem passar do fim."""
    cursor = first
    while cursor < limit - 0.14:
        kind = rng.random()
        if kind < 0.40:
            span = min(rng.uniform(0.2, 0.4), limit - cursor)
            closed_box(asm, cursor + span / 2, 0.0, top, span, depth - 0.1, rng.uniform(0.14, 0.27), rng.choice(BOX_LABELS), rng,
                       rng.uniform(-6, 6))
        elif kind < 0.65:
            count = rng.randint(1, 3)
            span = count * 0.16
            for index in range(count):
                paint_can(asm, cursor + 0.08 + index * 0.16, 0.0, top, rng.choice(("toy_blue", "toy_green", "toy_red", "toy_yellow")),
                          rng.random() < 0.4)
            if rng.random() < 0.5:
                paint_can(asm, cursor + 0.08, 0.0, top + 0.175, "toy_blue", False)
        elif kind < 0.85:
            count = rng.randint(2, 3)
            span = count * 0.115
            for index in range(count):
                glass_jar(asm, cursor + 0.0575 + index * 0.115, rng.uniform(-0.04, 0.04), top, rng)
        else:
            span = 0.16
            oil_bottle(asm, cursor + 0.08, 0.0, top)
        cursor += span + rng.uniform(0.02, 0.07)


def closed_box(asm, cx, cy, z0, width, depth, height, label, rng, yaw_deg=0.0):
    """Caixa de papelão fechada com fita, rótulo à caneta, aba levemente levantada e quinas amassadas pelo uso."""
    with asm.at(cx, cy, z0, rz=yaw_deg):
        asm.hard.box(0, 0, 0, width, depth, height, "kg_box_plain", uv=1.6)
        asm.round.panel(0, depth / 2 + 0.0006, height / 2, width - 0.012, height - 0.012, label, "front")
        asm.round.box(0, 0, height, width * 0.5, 0.004, 0.0012, "kg_gasket")
        if rng.random() < 0.35:
            with asm.hard.at(0, depth / 2, height, rx=14):
                asm.hard.box(0, depth / 4, 0, width - 0.004, depth / 2, 0.003, "kg_box_plain")


def open_box(asm, width, depth, height, material):
    """Caixa de papelão sem tampa: fundo, quatro paredes e as abas viradas para fora."""
    wall = 0.003
    asm.hard.box(0, 0, 0, width, depth, wall, material)
    asm.hard.box(0, depth / 2 - wall / 2, 0, width, wall, height, material)
    asm.hard.box(0, -depth / 2 + wall / 2, 0, width, wall, height, material)
    for side in (-1, 1):
        asm.hard.box(side * (width / 2 - wall / 2), 0, 0, wall, depth, height, material)
    for side in (-1, 1):
        with asm.hard.at(0, side * depth / 2, height, rx=side * 55):
            asm.hard.box(0, side * depth / 4, 0, width - 0.004, depth / 2, wall, material)


def paint_can(asm, cx, cy, z0, color, dripped=False):
    """Lata de tinta de um galão: corpo de lata, rótulo, tampa e, às vezes, tinta seca escorrida pela borda."""
    sides = segments(16)
    asm.round.lathe([(0.0, 0.0), (0.07, 0.0), (0.075, 0.005), (0.075, 0.17), (0.07, 0.175), (0.0, 0.175)], cx, cy, z0, "kg_tin",
                    seg=sides, smooth=True, cap_bottom=False, cap_top=False)
    asm.round.wrap([(0.0757, 0.04), (0.0757, 0.13)], cx, cy, z0, LABELS[color], seg=sides)
    asm.round.lathe([(0.066, 0.1745), (0.071, 0.178), (0.0, 0.178)], cx, cy, z0, color, seg=sides, cap_bottom=False, cap_top=False)
    if dripped:
        for angle in (0.4, 2.2, 4.4):
            asm.round.tube((cx + 0.0765 * math.cos(angle), cy + 0.0765 * math.sin(angle), z0 + 0.17),
                           (cx + 0.0765 * math.cos(angle), cy + 0.0765 * math.sin(angle), z0 + 0.1), 0.004, color, seg=5,
                           r_end=0.0025)


def glass_jar(asm, cx, cy, z0, rng):
    """Pote de vidro de geleia com tampa metálica, cheio de parafusos, pregos ou botões."""
    sides = segments(12)
    fill = rng.choice(("kg_tool_steel", "kg_brass", "kg_tool_steel", "toy_red"))
    asm.round.turned_bowl(cx, cy, z0, [(0.034, 0.0), (0.04, 0.008), (0.04, 0.13), (0.034, 0.14)], 0.003, "glass_clear", seg=sides)
    asm.round.cylinder(cx, cy, z0 + 0.004, 0.035, rng.uniform(0.05, 0.11), fill, seg=sides)
    asm.round.cylinder(cx, cy, z0 + 0.138, 0.037, 0.016, "kg_tin", seg=sides)


def oil_bottle(asm, cx, cy, z0):
    """Garrafa de óleo de motor, amarela, com a tampa preta e uma etiqueta."""
    sides = segments(12)
    asm.round.lathe([(0.0, 0.0), (0.05, 0.0), (0.055, 0.02), (0.055, 0.16), (0.03, 0.2), (0.022, 0.24), (0.0, 0.24)], cx, cy, z0,
                    "kg_oil_yellow", seg=sides, smooth=True, cap_bottom=False, cap_top=False)
    asm.round.cylinder(cx, cy, z0 + 0.24, 0.026, 0.02, "kg_plastic_dark", seg=sides)
    asm.round.wrap([(0.0558, 0.05), (0.0558, 0.14)], cx, cy, z0, "kg_label_oil", seg=sides)


def box_pile(asm, rng, layers, label):
    """Pilha de caixas: cada camada é (escala, dx, dy, giro em graus), como em `furniture.make_box_stack`."""
    z = 0.0
    size = (0.5, 0.4, 0.34)
    for scale, dx, dy, turn in layers:
        width, depth, height = size[0] * scale, size[1] * scale, size[2] * scale
        closed_box(asm, dx, dy, z, width, depth, height, label, rng, turn)
        z += height
