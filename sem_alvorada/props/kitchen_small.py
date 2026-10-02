"""Eletrodomésticos pequenos e utensílios de bancada: micro-ondas, cafeteira, torradeira, tábua com pão, fruteira,
bloco de facas, temperos e rolo de papel-toalha. Origem no centro da base, frente em +Y.
"""
import math

from . import kitchen_ware as ware
from .kg_shapes import segments


def build_microwave(asm, rng):
    """Micro-ondas bege amarelado: porta com visor, painel com display 6:12 e botões, pés de borracha."""
    w, d, h = 0.46, 0.34, 0.27
    front = d / 2
    hard = asm.hard
    hard.soft_box(0, 0, 0.014, w, d, h - 0.014, "kg_plastic_beige", radius=0.02, edge=0.01, corner_points=4)
    for sx in (-1, 1):
        for sy in (-1, 1):
            asm.round.cylinder(sx * 0.19, sy * 0.13, 0.0, 0.013, 0.014, "kg_rubber", seg=8)
    door_front = front + 0.012
    hard.soft_box(-0.06, front - 0.003, 0.034, 0.31, 0.03, 0.215, "kg_plastic_beige", radius=0.012, edge=0.006, corner_points=3)
    asm.round.panel(-0.06, door_front + 0.0006, 0.14, 0.255, 0.165, "kg_plastic_dark", "front")
    asm.round.panel(-0.06, door_front + 0.0012, 0.14, 0.24, 0.15, "glass_dark", "front")
    for z in (0.065, 0.215):
        asm.round.tube((0.087, door_front, z), (0.087, door_front + 0.022, z), 0.005, "kg_plastic_white", seg=6)
    asm.round.tube((0.087, door_front + 0.022, 0.065), (0.087, door_front + 0.022, 0.215), 0.007, "kg_plastic_white", seg=8)
    asm.round.panel(0.158, front + 0.0006, 0.135, 0.12, 0.23, "kg_plastic_dark", "front")
    asm.round.panel(0.158, front + 0.0012, 0.222, 0.09, 0.035, "digits_dash", "front")
    for row in range(4):
        for column in range(2):
            asm.crisp.box(0.133 + column * 0.05, front + 0.003, 0.15 - row * 0.027, 0.036, 0.006, 0.018, "kg_plastic_white")
    asm.crisp.box(0.158, front + 0.003, 0.035, 0.09, 0.006, 0.022, "kg_plastic_white")
    asm.round.panel(0.158, front + 0.0065, 0.035, 0.07, 0.012, "led_red", "front")


def build_coffee_maker(asm, rng):
    """Cafeteira de filtro: coluna, cabeça com porta-filtro, placa aquecedora e a jarra com o café frio de ontem."""
    hard = asm.hard
    hard.soft_box(0, 0, 0.0, 0.21, 0.23, 0.032, "kg_plastic_dark", radius=0.02, edge=0.008, corner_points=4)
    asm.round.cylinder(0.0, 0.02, 0.032, 0.085, 0.004, "kg_steel", seg=segments(20))
    hard.soft_box(0, -0.085, 0.032, 0.21, 0.058, 0.30, "kg_plastic_dark", radius=0.015, edge=0.008, corner_points=3)
    hard.soft_box(0, -0.035, 0.30, 0.21, 0.17, 0.052, "kg_plastic_dark", radius=0.02, edge=0.008, corner_points=4)
    asm.round.lathe([(0.0, 0.0), (0.055, 0.0), (0.075, 0.028), (0.0, 0.028)], 0, 0.02, 0.272, "kg_plastic_white",
                    seg=segments(16), cap_bottom=False, cap_top=False)
    asm.round.lathe([(0.0, 0.0), (0.056, 0.0), (0.066, 0.045), (0.07, 0.12), (0.06, 0.16), (0.03, 0.175), (0.0, 0.175)], 0, 0.02, 0.036,
                    "glass_clear", seg=segments(18), cap_bottom=False, cap_top=False)
    asm.round.cylinder(0, 0.02, 0.04, 0.056, 0.07, "kg_coffee", seg=segments(16), r_top=0.066)
    asm.round.cylinder(0, 0.02, 0.109, 0.066, 0.002, "kg_coffee", seg=segments(16))
    asm.round.cylinder(0, 0.02, 0.208, 0.034, 0.012, "kg_plastic_dark", seg=segments(12))
    asm.round.tube_path([(0.068, 0.02, 0.185), (0.105, 0.02, 0.18), (0.112, 0.02, 0.12), (0.07, 0.02, 0.07)], 0.007,
                        "kg_plastic_dark", sides=8, resolution=5)
    asm.crisp.box(0.07, 0.116, 0.014, 0.022, 0.006, 0.012, "kg_plastic_white")
    asm.round.panel(0.07, 0.1195, 0.02, 0.008, 0.008, "led_red", "front")


def build_toaster(asm, rng):
    """Torradeira de duas fatias: corpo de aço, topo e laterais pretos, alavanca, botão de tostagem e migalhas."""
    w, d, h = 0.27, 0.15, 0.185
    asm.hard.soft_box(0, 0, 0.012, w, d, h - 0.012, "kg_steel", radius=0.03, edge=0.012, corner_points=5)
    asm.hard.soft_box(0, 0, h - 0.002, w - 0.012, d - 0.012, 0.014, "kg_plastic_dark", radius=0.026, edge=0.005,
                      corner_points=4)
    for slot_x in (-0.055, 0.055):
        asm.round.box(slot_x, 0.0, h + 0.0121, 0.13, 0.012, 0.0006, "kg_gasket")
    for sx in (-1, 1):
        asm.round.cylinder(sx * 0.1, 0.0, 0.0, 0.016, 0.014, "kg_rubber", seg=8)
    asm.crisp.box(w / 2 + 0.006, 0.0, 0.07, 0.012, 0.03, 0.01, "kg_plastic_dark")
    asm.round.tube((w / 2 + 0.008, 0.0, 0.075), (w / 2 + 0.03, 0.0, 0.075), 0.007, "kg_plastic_dark", seg=8)
    asm.round.cylinder(-w / 2 + 0.03, d / 2, 0.15, 0.014, 0.012, "kg_plastic_dark", seg=10)
    for _ in range(14):
        asm.round.box(rng.uniform(-0.1, 0.1), rng.uniform(-0.07, 0.07) + 0.0, h + 0.0121, 0.004, 0.004, 0.001,
                      "kg_food_old")


def build_bread_board(asm, rng):
    """Tábua de pinho com um pão de forma mofado, uma fatia caída e a faca que cortou a última."""
    asm.hard.soft_box(0, 0, 0.0, 0.40, 0.26, 0.02, "kg_pine", radius=0.04, edge=0.006, corner_points=5)
    asm.round.rounded_loft([(0.02, 0.22, 0.1, 0.04, -0.02, 0.0), (0.05, 0.225, 0.103, 0.045, -0.02, 0.0),
                            (0.085, 0.215, 0.1, 0.045, -0.02, 0.0), (0.11, 0.18, 0.08, 0.04, -0.02, 0.0),
                            (0.12, 0.12, 0.05, 0.022, -0.02, 0.0)], "kg_food_old", corner_points=5)
    asm.soft.soft_box(0.13, -0.045, 0.02, 0.1, 0.1, 0.014, "kg_food_old", radius=0.025, edge=0.005, corner_points=3)
    ware.cutlery(asm, "knife", 0.07, 0.09, 0.0215, 25.0)
    asm.round.tube((0.15, 0.13, 0.028), (0.19, 0.13, 0.032), 0.012, "kg_plastic_dark", seg=8)


def build_fruit_bowl(asm, rng):
    """Fruteira de madeira com fruta de três semanas: maçãs escuras, laranja mofada e uma banana preta."""
    sides = segments(18)
    asm.round.turned_bowl(0, 0, 0.0, [(0.08, 0.0), (0.12, 0.04), (0.17, 0.085), (0.18, 0.09)], 0.008, "kg_pine", seg=sides)
    for dx, dy, dz, size, tilt in ((-0.05, 0.02, 0.05, 0.043, 0.0), (0.06, 0.04, 0.052, 0.04, 0.0), (0.0, -0.06, 0.055, 0.042, 0.0)):
        asm.round.sphere(dx, dy, dz + size * 0.9, size, "kg_rotten_fruit", seg=segments(10), rings=6, squash=0.92)
    asm.round.sphere(0.01, 0.06, 0.10, 0.037, "kg_mold_orange", seg=segments(10), rings=6)
    asm.round.sphere(0.02, 0.07, 0.133, 0.017, "kg_food_old", seg=8, rings=4, squash=0.5)
    asm.round.tube_path([(-0.1, -0.02, 0.1), (-0.04, -0.075, 0.14), (0.05, -0.085, 0.145), (0.12, -0.04, 0.12)], 0.016,
                        "kg_banana_black", sides=6, resolution=5, taper=lambda t: 0.45 + 1.1 * math.sin(math.pi * t))


def build_knife_block(asm, rng):
    """Bloco de facas de madeira inclinado, com cinco cabos pretos de tamanhos diferentes."""
    asm.hard.box(0, 0, 0.0, 0.12, 0.2, 0.2, "kg_pine")
    asm.hard.wedge(0, 0, 0.2, 0.12, 0.2, 0.04, "kg_pine", high="back")
    for index in range(5):
        y = -0.07 + index * 0.035
        length = 0.07 + 0.015 * (index % 3)
        asm.round.box(0.0, y, 0.236, 0.016, 0.013, length, "kg_plastic_dark")


def build_spice_rack(asm, rng):
    """Prateleirinha de bancada com seis potes de tempero de tampas coloridas, cada um com um resto diferente."""
    asm.hard.box(0, 0, 0.0, 0.34, 0.11, 0.012, "kg_pine")
    asm.hard.box(0, -0.052, 0.012, 0.34, 0.006, 0.02, "kg_pine")
    colors = ("toy_red", "toy_yellow", "toy_green", "kg_brass", "toy_red", "kg_plastic_dark")
    for index, lid in enumerate(colors):
        x = -0.14 + index * 0.056
        asm.round.cylinder(x, 0.0, 0.012, 0.022, 0.08, "glass_clear", seg=segments(10))
        asm.round.cylinder(x, 0.0, 0.012, 0.0205, 0.03 + 0.02 * ((index * 3) % 3) * 0.5, "kg_spice", seg=segments(10))
        asm.round.cylinder(x, 0.0, 0.092, 0.023, 0.014, lid, seg=segments(10))


def build_paper_towel(asm, rng):
    """Suporte de rolo de papel-toalha com o rolo pela metade e uma tira solta pendurada."""
    asm.round.cylinder(0, 0, 0.0, 0.07, 0.012, "kg_plastic_dark", seg=segments(16), r_top=0.065)
    asm.round.cylinder(0, 0, 0.012, 0.006, 0.28, "kg_chrome", seg=8)
    asm.round.sphere(0, 0, 0.296, 0.012, "kg_chrome", seg=8, rings=4)
    asm.round.lathe([(0.026, 0.0), (0.062, 0.0), (0.066, 0.01), (0.066, 0.24), (0.062, 0.25), (0.026, 0.25)], 0, 0, 0.016,
                    "paper_white", seg=segments(20), cap_bottom=False, cap_top=False)
    asm.round.lathe([(0.026, 0.0), (0.026, 0.25)], 0, 0, 0.016, "kg_cardboard_tube", seg=segments(12), cap_bottom=False,
                    cap_top=False)
    asm.round.tube_path([(0.066, 0.0, 0.2), (0.075, 0.0, 0.17), (0.072, 0.003, 0.1), (0.08, 0.0, 0.03)], 0.0012, "paper_white",
                        sides=4, resolution=4, taper=lambda t: 1.0 + 12 * t)
