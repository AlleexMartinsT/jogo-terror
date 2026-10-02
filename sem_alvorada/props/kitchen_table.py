"""Mesinha do café da manhã, as duas cadeiras de tubo, a lixeira de pedal e o que sobrou na mesa.

Referências: mesa de 0,80 m com tampo a 0,75 m; assento de cadeira a 0,45 m; lixeira de pedal de 30 cm.
"""
import math

from . import kit, kitchen_ware as ware
from .kg_shapes import segments

TABLE_SIZE = 0.80
TABLE_TOP = 0.75


def build_table(asm, rng):
    """Tampo de laminado com cinta cromada, quatro pernas de tubo levemente abertas e a mesa posta para um só."""
    size = TABLE_SIZE
    asm.hard.soft_box(0, 0, TABLE_TOP - 0.036, size, size, 0.036, "kg_laminate", radius=0.04, edge=0.004, corner_points=5)
    outer = kit.rounded_rect(size + 0.006, size + 0.006, 0.043, 5)
    inner = kit.rounded_rect(size, size, 0.04, 5)
    asm.crisp.annulus(outer, inner, TABLE_TOP - 0.04, TABLE_TOP - 0.004, "kg_chrome")
    asm.hard.box(0, 0, TABLE_TOP - 0.075, size - 0.12, size - 0.12, 0.04, "kg_toe")
    for sx in (-1, 1):
        for sy in (-1, 1):
            asm.round.tube((sx * 0.355, sy * 0.355, TABLE_TOP - 0.04), (sx * 0.375, sy * 0.375, 0.0), 0.0135, "kg_chrome",
                           seg=segments(10, 6))
            asm.round.cylinder(sx * 0.375, sy * 0.375, 0.0, 0.017, 0.012, "kg_rubber", seg=8)
    top = TABLE_TOP
    ware.bowl(asm, -0.2, 0.2, top, 0.075, 0.06, food=True)
    ware.bowl(asm, 0.17, -0.22, top, 0.075, 0.06, food=True)
    ware.mug(asm, 0.25, 0.22, top, 0.04, 0.095, handle_deg=-20.0, coffee=True)
    cereal_box(asm, -0.22, -0.2, top)
    newspaper(asm, 0.0, 0.0, top)
    pill_bottle(asm, 0.02, 0.28, top)


def cereal_box(asm, x, y, z):
    """Caixa de cereal amarela e vermelha, mais aberta que fechada."""
    with asm.hard.at(x, y, z, rz=12):
        asm.hard.box(0, 0, 0, 0.17, 0.065, 0.27, "toy_yellow")
        asm.hard.box(0, 0.0335, 0.1, 0.12, 0.002, 0.1, "toy_red")
        asm.hard.box(0, 0.0, 0.27, 0.17, 0.065, 0.004, "toy_yellow")
        with asm.hard.at(0, -0.03, 0.272, rx=-55):
            asm.hard.box(0, 0.0, 0.0, 0.17, 0.06, 0.003, "toy_yellow")


def newspaper(asm, x, y, z):
    """O jornal de ontem aberto na mesa, com a dobra do meio."""
    with asm.round.at(x, y, z + 0.0004, rz=-14):
        for side in (-1, 1):
            with asm.round.at(side * 0.1, 0.0, 0.0, ry=side * 1.5):
                asm.round.box(0, 0, 0, 0.2, 0.3, 0.0016, "paper_white")
                asm.round.panel(0, 0, 0.0018, 0.2, 0.3, "note_newspaper", "top")


def pill_bottle(asm, x, y, z):
    """Vidro de remédio âmbar com tampa branca, e um copo d'água pela metade ao lado."""
    sides = segments(14)
    asm.round.lathe([(0.0, 0.0), (0.0185, 0.0), (0.02, 0.004), (0.02, 0.07), (0.0185, 0.074), (0.0, 0.074)], x, y, z,
                    "kg_amber_glass", seg=sides, smooth=True, cap_bottom=False, cap_top=False)
    asm.round.cylinder(x, y, z + 0.074, 0.021, 0.018, "kg_plastic_white", seg=sides)
    ware.tumbler(asm, x + 0.09, y - 0.03, z, 0.034, 0.1, residue=0.05)


def build_chair(asm, rng, seat_material="kg_vinyl_red"):
    """Cadeira de cozinha de tubo cromado com assento e encosto estofados em vinil vermelho já trincado."""
    tube = 0.0115
    sides = segments(10, 6)
    seat_h = 0.45
    for sx in (-1, 1):
        asm.round.tube_path([(sx * 0.19, 0.18, 0.0), (sx * 0.19, 0.18, seat_h - 0.02)], tube, "kg_chrome", sides=sides)
        asm.round.tube_path([(sx * 0.19, -0.19, 0.0), (sx * 0.19, -0.19, seat_h - 0.02), (sx * 0.19, -0.2, seat_h + 0.18),
                             (sx * 0.19, -0.215, 0.86)], tube, "kg_chrome", sides=sides, resolution=8)
        asm.round.cylinder(sx * 0.19, 0.18, 0.0, 0.016, 0.012, "kg_rubber", seg=8)
        asm.round.cylinder(sx * 0.19, -0.19, 0.0, 0.016, 0.012, "kg_rubber", seg=8)
    for z in (0.22,):
        asm.round.tube((-0.19, 0.18, z), (0.19, 0.18, z), 0.008, "kg_chrome", seg=8)
        asm.round.tube((-0.19, -0.19, z), (0.19, -0.19, z), 0.008, "kg_chrome", seg=8)
    asm.round.tube((-0.19, -0.19, 0.2), (-0.19, 0.18, 0.2), 0.008, "kg_chrome", seg=8)
    asm.round.tube((0.19, -0.19, 0.2), (0.19, 0.18, 0.2), 0.008, "kg_chrome", seg=8)
    asm.soft.soft_box(0, 0.0, seat_h - 0.02, 0.42, 0.40, 0.055, seat_material, radius=0.05, edge=0.018, corner_points=5)
    with asm.soft.at(0, -0.205, 0.0, rx=-6):
        asm.soft.soft_box(0, 0, 0.62, 0.40, 0.045, 0.2, seat_material, radius=0.03, edge=0.015, corner_points=4)


def build_trash_bin(asm, rng):
    """Lixeira de pedal de aço pintado: tampa entreaberta, saco estufado com lixo de três semanas, pedal na frente."""
    radius, height = 0.17, 0.52
    sides = segments(22)
    asm.round.lathe([(0.0, 0.0), (radius * 0.9, 0.0), (radius * 0.97, 0.02), (radius, 0.06), (radius, height - 0.02),
                     (radius * 0.97, height)], 0, 0, 0, "kg_plastic_white", seg=sides, smooth=True, cap_bottom=False,
                    cap_top=False)
    asm.soft.sphere(0.0, 0.01, height + 0.02, radius * 0.92, "kg_trash_bag", seg=segments(12), rings=7, squash=0.75)
    lumps = (("paper_white", 0.0), ("kg_food_old", 40.0), ("kg_box_plain", 75.0), ("paper_white", 130.0), ("kg_food_old", 160.0))
    for index, (material, turn) in enumerate(lumps):
        angle = index * 1.25
        with asm.soft.at(0.08 * math.cos(angle), 0.08 * math.sin(angle) + 0.01, height + 0.07 + 0.015 * index, rx=turn * 0.4,
                         ry=turn * 0.3, rz=turn):
            asm.soft.soft_box(0, 0, 0, 0.09, 0.07, 0.06, material, radius=0.02, edge=0.015, corner_points=3)
    with asm.round.at(0.05, 0.02, height + 0.1, rx=14, rz=25):
        asm.round.box(0, 0, 0, 0.2, 0.012, 0.16, "kg_box_plain")
    with asm.round.at(0, -radius * 0.98, height + 0.03, rx=26):
        asm.round.lathe([(0.0, 0.055), (radius * 0.9, 0.05), (radius, 0.03), (radius * 0.98, 0.0), (0.0, 0.0)], 0, radius * 0.98,
                        0.0, "kg_plastic_white", seg=sides, smooth=True, cap_bottom=False, cap_top=False)
        asm.round.sphere(0, radius * 0.98, 0.062, 0.018, "kg_plastic_dark", seg=8, rings=4)
    asm.crisp.box(0, radius + 0.045, 0.012, 0.075, 0.1, 0.012, "kg_plastic_dark")
    asm.round.tube((0, radius + 0.0, 0.03), (0, radius * 0.7, 0.04), 0.006, "kg_chrome", seg=6)
