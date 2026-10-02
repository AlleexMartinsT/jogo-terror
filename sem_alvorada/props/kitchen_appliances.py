"""Eletrodomésticos grandes da cozinha: geladeira, frigobar, fogão e coifa.

Medidas de referência: geladeira de freezer em cima 0,74 x 0,70 x 1,78 m; fogão de quatro bocas 0,76 m de
largura com tampo a 0,90 m; boca de 19 cm. Origem no centro da base, frente em +Y, como todo móvel.
"""
from . import kitchen_cabinets as cabinets
from . import kitchen_decor as decor
from . import kitchen_ware as ware
from .kg_shapes import segments

FRIDGE_W, FRIDGE_D, FRIDGE_H = 0.74, 0.70, 1.78
DOOR_T = 0.045
MINI_W = 0.62
MINI_DEPTH = 0.58
MINI_PLATE = 0.012
STOVE_W, STOVE_D, STOVE_H = 0.76, 0.65, 0.90


def vertical_handle(asm, x, y, z_center, length, material="kg_chrome", standoff=0.036, radius=0.0115):
    """Puxador de barra vertical com dois pés, como o da porta de geladeira."""
    half = length / 2 - 0.02
    for z in (z_center - half, z_center + half):
        asm.round.tube((x, y, z), (x, y + standoff, z), radius * 0.8, material, seg=segments(8, 6))
    asm.round.tube((x, y + standoff, z_center - half), (x, y + standoff, z_center + half), radius, material,
                   seg=segments(10, 6))


# ---------------------------------------------------------------------------
# Geladeira
# ---------------------------------------------------------------------------
def build_fridge(asm, rng):
    """Geladeira de duas portas de cantos arredondados, vedação à vista, vincos, ímãs e desenhos da Emma."""
    w, d, h = FRIDGE_W, FRIDGE_D, FRIDGE_H
    front = d / 2
    body_depth = d - DOOR_T
    hard = asm.hard
    hard.soft_box(0, -d / 2 + body_depth / 2, 0.045, w, body_depth, h - 0.045, "kg_enamel", radius=0.035, edge=0.012,
                  corner_points=5)
    hard.box(0, -d / 2 + body_depth / 2 - 0.02, 0.0, w - 0.09, body_depth - 0.12, 0.05, "kg_toe")
    for index in range(4):
        asm.crisp.box(0, front - DOOR_T - 0.036, 0.008 + index * 0.012, w - 0.12, 0.006, 0.006, "kg_plastic_dark")
    for side in (-1, 1):
        asm.round.cylinder(side * (w / 2 - 0.05), front - DOOR_T - 0.04, 0.0, 0.022, 0.05, "kg_plastic_dark", seg=8)
    gasket_z = 1.255
    hard.box(0, front - DOOR_T + 0.004, gasket_z, w - 0.03, 0.012, 0.04, "kg_gasket")
    for z0, z1 in ((0.075, 1.255), (1.29, 1.76)):
        hard.soft_box(0, front - DOOR_T / 2, z0, w - 0.006, DOOR_T, z1 - z0, "kg_enamel", radius=0.03, edge=0.011,
                      corner_points=5)
    asm.round.box(0.0, front + 0.0005, 1.74, 0.34, 0.0014, 0.012, "kg_gasket")       # reentrância de dedo da porta de cima
    asm.round.box(0.0, front + 0.0005, 1.235, 0.34, 0.0014, 0.012, "kg_gasket")
    handle_x = -w / 2 + 0.06
    vertical_handle(asm, handle_x, front, 0.82, 0.56)
    vertical_handle(asm, handle_x, front, 1.53, 0.26)
    for z in (0.12, 1.27, 1.72):
        asm.round.cylinder(w / 2 - 0.022, front - 0.02, z, 0.015, 0.03, "kg_plastic_dark", seg=8)
    asm.crisp.box(0.12, front + 0.002, 1.70, 0.1, 0.004, 0.02, "kg_chrome")
    decorate_fridge_door(asm, rng, front)


def decorate_fridge_door(asm, rng, y):
    """Marcas de uma casa com criança: mãos baixas na porta, desenhos e fotos presos por ímãs, recados da Laura."""
    asm.hard.panel(0.06, y + 0.0008, 0.46, 0.34, 0.34, "kg_smudge", "front")
    asm.hard.panel(-0.30, y + 0.0009, 0.78, 0.16, 0.16, "kg_grease", "front")
    asm.hard.panel(-0.30, y + 0.0009, 1.50, 0.15, 0.15, "kg_grease", "front")
    letters = (("block_e", "toy_red"), ("block_m", "toy_blue"), ("block_m", "toy_blue"), ("block_a", "toy_green"))
    for index, (letter, color) in enumerate(letters):
        decor.letter_magnet(asm, 0.105 - index * 0.04, 0.985 + rng.uniform(-0.004, 0.004), y, letter, color,
                            rng.uniform(-9, 9))
    decor.paper_sheet(asm, 0.07, 1.16, y, 0.22, 0.27, "kg_drawing_house", 3.5)
    decor.round_magnet(asm, 0.07 - 0.07, 1.16 + 0.115, y + 0.003, "toy_yellow")
    decor.round_magnet(asm, 0.07 + 0.07, 1.16 + 0.115, y + 0.003, "toy_red")
    decor.paper_sheet(asm, -0.13, 0.66, y, 0.2, 0.25, "kg_drawing_family", -5.0)
    decor.round_magnet(asm, -0.13, 0.66 + 0.105, y + 0.003, "toy_blue")
    decor.paper_sheet(asm, 0.17, 0.74, y, 0.1, 0.075, "photo_mother_child", 6.0)
    decor.round_magnet(asm, 0.17, 0.74 + 0.03, y + 0.003, "toy_green", 0.011)
    decor.paper_sheet(asm, 0.22, 1.30, y, 0.075, 0.075, "kg_postit_remedio", -4.0)
    decor.paper_sheet(asm, -0.12, 1.55, y, 0.075, 0.075, "kg_postit_doutor", 7.0)


# ---------------------------------------------------------------------------
# Frigobar
# ---------------------------------------------------------------------------
def build_mini_fridge(asm, rng):
    """Frigobar embutido no balcão: caixa, porta principal e portinha do congelador, puxador no lado direito, tampo."""
    w, d = MINI_W, MINI_DEPTH
    front = d / 2 + MINI_PLATE
    hard = asm.hard
    hard.soft_box(0, 0, 0.0, w, d, 0.86, "kg_enamel", radius=0.02, edge=0.008, corner_points=3)
    hard.soft_box(0, front - 0.016, 0.03, w - 0.03, 0.032, 0.655, "kg_enamel", radius=0.02, edge=0.008, corner_points=4)
    hard.soft_box(0, front - 0.016, 0.69, w - 0.03, 0.032, 0.14, "kg_enamel", radius=0.02, edge=0.008, corner_points=4)
    hard.box(0, front - 0.012, 0.683, w - 0.05, 0.02, 0.01, "kg_gasket")
    vertical_handle(asm, w / 2 - 0.075, front, 0.40, 0.26, standoff=0.03, radius=0.0095)
    asm.crisp.box(w / 2 - 0.075, front + 0.006, 0.76, 0.016, 0.012, 0.05, "kg_chrome")
    asm.hard.panel(0.0, front + 0.0008, 0.22, 0.30, 0.30, "kg_grease", "front")
    asm.crisp.box(-0.2, front + 0.001, 0.80, 0.06, 0.003, 0.012, "kg_chrome")
    cabinets.laminate_top(asm, -w / 2, w / 2, d)


# ---------------------------------------------------------------------------
# Fogão
# ---------------------------------------------------------------------------
def _burner(asm, cx, cy, top):
    """Boca: prato de aço, anel e tampa de ferro, e a mancha de gordura queimada ao redor."""
    sides = segments(20)
    asm.round.lathe([(0.0, 0.0), (0.078, 0.0), (0.097, 0.009), (0.103, 0.009), (0.103, 0.004)], cx, cy, top, "kg_steel",
                    seg=sides, smooth=True, cap_bottom=False, cap_top=False)
    asm.round.lathe([(0.0, 0.0), (0.056, 0.0), (0.056, 0.014), (0.0, 0.014)], cx, cy, top + 0.006, "kg_castiron", seg=sides,
                    cap_bottom=False, cap_top=False)
    asm.round.cylinder(cx, cy, top + 0.02, 0.034, 0.008, "kg_castiron", seg=segments(14), r_top=0.03)


def _grate(asm, cx, top):
    """Grelha de ferro fundido sobre duas bocas: moldura, travessas e dedos para apoiar a panela."""
    z = top + 0.034
    half_x, half_y = 0.175, 0.26
    sides = segments(8, 6)
    rails = [((cx - half_x, -half_y, z), (cx - half_x, half_y, z)), ((cx + half_x, -half_y, z), (cx + half_x, half_y, z)),
             ((cx - half_x, -half_y, z), (cx + half_x, -half_y, z)), ((cx - half_x, half_y, z), (cx + half_x, half_y, z)),
             ((cx - half_x, 0.0, z), (cx + half_x, 0.0, z))]
    rails += [((cx + offset, -half_y, z), (cx + offset, half_y, z)) for offset in (-0.075, 0.0, 0.075)]
    for start, end in rails:
        asm.round.tube(start, end, 0.0065, "kg_castiron", seg=sides)
    for sx in (-1, 1):
        for sy in (-1, 1):
            asm.round.tube((cx + sx * half_x, sy * half_y, top), (cx + sx * half_x, sy * half_y, z), 0.008, "kg_castiron", seg=sides)


def _knob(asm, x, y, z):
    sides = segments(14)
    with asm.round.at(x, y, z, rx=-90):
        asm.round.lathe([(0.0, 0.0), (0.021, 0.0), (0.025, 0.01), (0.022, 0.026), (0.0, 0.027)], 0, 0, 0, "kg_plastic_dark",
                        seg=sides, smooth=True, cap_bottom=False, cap_top=False)
    asm.crisp.box(x, y + 0.0275, z + 0.012, 0.003, 0.004, 0.014, "paper_white")


def build_stove(asm, rng):
    """Fogão de quatro bocas: tampo preto, grelhas, forno com visor, gaveta, relógio parado e panelas frias."""
    w, d, h = STOVE_W, STOVE_D, STOVE_H
    front = d / 2
    top = h
    hard = asm.hard
    hard.soft_box(0, 0, 0.0, w, d, h - 0.04, "kg_enamel", radius=0.012, edge=0.008, corner_points=3)
    hard.box(0, 0, h - 0.04, w, d, 0.04, "kg_enamel_black")
    hard.box(0, -d / 2 + 0.05, h, w, 0.10, 0.2, "kg_enamel")
    hard.panel(0.17, -d / 2 + 0.1005, h + 0.1, 0.13, 0.065, "digits_612", "front")
    asm.crisp.box(0.17, -d / 2 + 0.1002, h + 0.1 - 0.0375, 0.15, 0.002, 0.075, "kg_gasket")
    hard.soft_box(0, front - 0.02 + 0.006, 0.14, w - 0.04, 0.052, 0.54, "kg_enamel", radius=0.012, edge=0.008, corner_points=3)
    door_front = front + 0.012
    asm.round.panel(0, door_front + 0.0006, 0.41, 0.48, 0.30, "kg_gasket", "front")
    asm.round.panel(0, door_front + 0.0012, 0.41, 0.44, 0.26, "glass_dark", "front")
    hard.soft_box(0, front - 0.016 + 0.006, 0.02, w - 0.06, 0.044, 0.105, "kg_enamel", radius=0.01, edge=0.006, corner_points=3)
    for sx in (-1, 1):
        asm.round.tube((sx * 0.27, door_front, 0.675), (sx * 0.27, door_front + 0.045, 0.675), 0.009, "kg_chrome", seg=8)
    asm.round.tube((-0.27, door_front + 0.045, 0.675), (0.27, door_front + 0.045, 0.675), 0.0125, "kg_chrome",
                   seg=segments(10, 6))
    asm.crisp.box(0, door_front - 0.004 + 0.002, 0.075, 0.2, 0.012, 0.014, "kg_chrome")
    hard.box(0, front - 0.012, 0.715, w - 0.04, 0.026, 0.145, "kg_enamel_black")
    for index, x in enumerate((-0.285, -0.15, 0.0, 0.15, 0.285)):
        _knob(asm, x, front + 0.001, 0.79 if index != 2 else 0.775)
    burners = [(-0.19, 0.13), (-0.19, -0.13), (0.19, 0.13), (0.19, -0.13)]
    for cx, cy in burners:
        _burner(asm, cx, cy, top)
    for cx in (-0.19, 0.19):
        _grate(asm, cx, top)
    hard.panel(0.12, 0.05, top + 0.0006, 0.30, 0.30, "kg_grease", "top")
    hard.panel(-0.2, -0.05, top + 0.0007, 0.22, 0.22, "kg_grease", "top")
    ware.kettle(asm, -0.19, -0.13, top + 0.034, 15.0)
    ware.frying_pan(asm, 0.19, 0.13, top + 0.034, yaw_deg=160.0)
    ware.pot(asm, 0.19, -0.13, top + 0.034, 0.1, 0.11, lid=True, water=False)


def build_hood(asm, rng):
    """Coifa de aço: copa em tronco, chaminé até o forro, filtro e botões. Frente em +Y, origem no fundo da peça."""
    depth, width = 0.46, 0.62
    z0, z1, ceiling = 1.48, 1.74, 2.6
    asm.crisp.rounded_loft([(z0, width, depth, 0.01, 0, depth / 2), (z1, 0.30, 0.22, 0.006, 0, 0.11)], "kg_steel", corner_points=2)
    asm.crisp.rounded_loft([(z1, 0.30, 0.22, 0.006, 0, 0.11), (ceiling, 0.30, 0.22, 0.006, 0, 0.11)], "kg_steel",
                           corner_points=2, caps=(False, False))
    asm.hard.box(0, depth / 2 + 0.002, z0 - 0.006, width - 0.1, depth - 0.1, 0.006, "kg_castiron")
    for x in (-0.07, 0.0, 0.07):
        asm.round.cylinder(x, depth - 0.004, z0 + 0.04, 0.014, 0.01, "kg_plastic_dark", seg=8)
    asm.hard.panel(0.0, depth * 0.78, z0 - 0.0063, width - 0.14, 0.04, "kg_grease", "bottom")
