"""Balcão da pia: tampo recortado, cubas de aço, torneira, escorredor e a louça por lavar.

O tampo vem de `assets/models/tampo_pia_dupla.npz` (gerado por `tools/modelagem/tampo_pia_dupla.py`, com os
dois recortes de cantos arredondados). O mesmo arquivo guarda a posição de cada recorte, então o aro e as
cubas de aço são desenhados exatamente sobre os furos, sem repetir números aqui.
"""
import os

import numpy as np

from .. import ASSETS_DIR, craft
from . import kit, kitchen_cabinets as cabinets, kitchen_ware as ware
from .kg_shapes import segments

TOP_NPZ = os.path.join(ASSETS_DIR, "models", "tampo_pia_dupla.npz")
WIDTH, DEPTH = 1.30, 0.60
RIM_RAISE = 0.004
BOWL_DEPTH = 0.20
FAUCET_Y = -0.265


def load_holes():
    """Recortes do tampo: lista de (cx, cy, largura, profundidade, raio)."""
    with np.load(TOP_NPZ) as arrays:
        return [tuple(float(v) for v in row) for row in arrays["holes"]]


def _outline(cx, cy, width, depth, radius, corner_points=6):
    return [(cx + x, cy + y) for x, y in kit.rounded_rect(width, depth, radius, corner_points)]


def hollow_base(asm):
    """Caixa sem tampo e sem fundo de cima: a cuba precisa de espaço para descer."""
    thick = 0.018
    m = asm.hard
    m.box(0, -0.03, 0.0, WIDTH - 0.004, DEPTH - 0.07, cabinets.TOE_H, "kg_toe")
    for side in (-1, 1):
        m.box(side * (WIDTH / 2 - thick / 2), 0, cabinets.TOE_H, thick, DEPTH, cabinets.BODY_TOP - cabinets.TOE_H, "kg_oak_v")
    m.box(0, -DEPTH / 2 + 0.006, cabinets.TOE_H, WIDTH, 0.012, cabinets.BODY_TOP - cabinets.TOE_H, "kg_toe")
    m.box(0, 0, cabinets.TOE_H, WIDTH, DEPTH, 0.018, "kg_pine")


def doors_and_drawer(asm):
    y_front = DEPTH / 2 + cabinets.DOOR_T
    z_top = cabinets.BODY_TOP - cabinets.GAP
    cabinets.drawer_front(asm, -WIDTH / 2 + cabinets.GAP, WIDTH / 2 - cabinets.GAP, z_top - cabinets.DRAWER_H, z_top, y_front)
    z1 = z_top - cabinets.DRAWER_H - cabinets.GAP
    for index, (x0, x1) in enumerate(cabinets.door_openings(WIDTH, 2)):
        hinge_x, free_x = (x0, x1) if index == 0 else (x1, x0)
        cabinets.hinged_door(asm, hinge_x, free_x, cabinets.TOE_H + cabinets.GAP, z1, y_front)
        handle_x = free_x + (-0.05 if free_x > hinge_x else 0.05)
        cabinets.grease_mark(asm, handle_x, z1 - 0.1, y_front)
        cabinets.bar_pull(asm, handle_x, z1 - 0.1, y_front, 0.1, vertical=True)


def steel_bowl(asm, hole):
    """Cuba de aço: aro elevado sobre o laminado e o fundo arredondado que desce BOWL_DEPTH."""
    cx, cy, width, depth, radius = hole
    margin = 0.025
    asm.crisp.annulus(_outline(cx, cy, width + 2 * margin, depth + 2 * margin, radius + margin),
                      _outline(cx, cy, width, depth, radius), cabinets.TOP_Z, cabinets.TOP_Z + RIM_RAISE, "kg_steel")
    top = cabinets.TOP_Z + RIM_RAISE
    sections = [(top, 0.0, radius), (top - 0.008, 0.002, radius), (top - 0.13, 0.008, radius + 0.01),
                (top - BOWL_DEPTH + 0.02, 0.026, radius + 0.025), (top - BOWL_DEPTH, 0.04, radius + 0.04)]
    rings = [[(x, y, z) for x, y in _outline(cx, cy, width - 2 * inset, depth - 2 * inset, r)] for z, inset, r in sections]
    asm.crisp.loft(rings, "kg_steel", cap_start=False, cap_end=True, smooth=True)
    drain_z = top - BOWL_DEPTH + 0.002
    asm.round.cylinder(cx, cy, drain_z, 0.04, 0.004, "kg_chrome", seg=segments(16))
    asm.round.cylinder(cx, cy, drain_z + 0.004, 0.012, 0.003, "kg_steel", seg=8)


def faucet(asm, x):
    """Torneira de pescoço alto com alavanca única e arejador; tudo cromado."""
    y = FAUCET_Y
    asm.round.cylinder(x, y, cabinets.TOP_Z, 0.03, 0.012, "kg_chrome", seg=segments(16))
    neck = [(x, y, 0.91), (x, y, 0.99), (x, y + 0.012, 1.05), (x, y + 0.06, 1.095), (x, y + 0.13, 1.095),
            (x, y + 0.19, 1.05), (x, y + 0.21, 0.995)]
    asm.round.tube_path(neck, 0.0115, "kg_chrome", sides=10, resolution=8)
    asm.round.cylinder(x, y + 0.21, 0.965, 0.0145, 0.04, "kg_chrome", seg=10)
    asm.round.cylinder(x + 0.026, y, 0.912, 0.011, 0.034, "kg_chrome", seg=8)
    asm.round.tube_path([(x + 0.026, y, 0.946), (x + 0.07, y, 0.962), (x + 0.108, y, 0.974)], 0.006, "kg_chrome", sides=6,
                        resolution=3)


def dish_rack(asm, cx, cy):
    """Escorredor de arame sobre uma bandeja de plástico, com quatro pratos limpos em pé e dois copos."""
    z = cabinets.TOP_Z
    length, width = 0.40, 0.32
    asm.crisp.box(cx, cy, z, length, width, 0.012, "kg_plastic_white")
    for edge in (-1, 1):
        asm.crisp.box(cx, cy + edge * (width / 2 - 0.004), z, length, 0.008, 0.026, "kg_plastic_white")
    wire = 0.0016
    for index in range(9):
        x = cx - length / 2 + 0.03 + index * (length - 0.06) / 8
        asm.round.tube((x, cy - width / 2 + 0.02, z + 0.02), (x, cy + width / 2 - 0.02, z + 0.02), wire, "kg_steel", seg=4)
    for index in range(6):
        y = cy - width / 2 + 0.03 + index * (width - 0.06) / 5
        asm.round.tube((cx - length / 2 + 0.02, y, z + 0.02), (cx + length / 2 - 0.02, y, z + 0.02), wire, "kg_steel", seg=4)
    slots_y = [cy + 0.05 + 0.03 * i for i in range(4)]
    for y in slots_y:
        for side in (-1, 1):
            asm.round.tube((cx + side * 0.17, y, z + 0.02), (cx + side * 0.17, y, z + 0.15), wire, "kg_steel", seg=4)
        ware.plate(asm, cx - 0.12, y, z + 0.02 + 0.108, 0.11, tilt=(80.0, 0.0), band=True)
    ware.kids_cup(asm, cx + 0.12, cy - 0.1, z + 0.026)
    ware.tumbler(asm, cx + 0.04, cy - 0.1, z + 0.026, 0.03, 0.1)


def dirty_dishes(asm, rng, hole):
    """Pia da esquerda: o monte de pratos, tigelas e canecas da última semana sobre uma panela grande."""
    cx, cy = hole[0], hole[1]
    floor = cabinets.TOP_Z + RIM_RAISE - BOWL_DEPTH + 0.004
    ware.pot(asm, cx - 0.02, cy + 0.03, floor, 0.105, 0.17, water=False)
    ware.plate_stack(asm, rng, cx - 0.02, cy + 0.03, floor + 0.17, 4, 0.115)
    ware.bowl(asm, cx + 0.08, cy - 0.09, floor + 0.0, 0.075, 0.06, food=True)
    ware.bowl(asm, cx - 0.10, cy - 0.07, floor + 0.0, 0.075, 0.06, food=True)
    ware.mug(asm, cx + 0.1, cy + 0.09, floor, 0.04, 0.095, handle_deg=40.0, coffee=True)
    ware.tumbler(asm, cx - 0.115, cy + 0.11, floor, 0.032, 0.11, residue=0.012)
    for index, (kind, yaw) in enumerate((("fork", 80.0), ("knife", 100.0), ("spoon", 260.0), ("fork", 285.0))):
        ware.cutlery(asm, kind, cx - 0.1 + index * 0.06, cy + 0.0, floor + 0.05 + index * 0.012, yaw,
                     tilt=(rng.uniform(-8, 8), rng.uniform(-10, 10)))


def soaking_pot(asm, hole):
    """Pia da direita: uma panela de molho com a água parada e escura, a esponja na borda."""
    cx, cy = hole[0], hole[1]
    floor = cabinets.TOP_Z + RIM_RAISE - BOWL_DEPTH + 0.004
    ware.pot(asm, cx + 0.01, cy + 0.01, floor, 0.12, 0.14, water=True)
    ware.sponge(asm, cx + 0.12, cy + 0.19, cabinets.TOP_Z + RIM_RAISE, 12.0)


def build_sink_unit(asm, rng):
    """Desenha o balcão da pia na montagem `asm` (frente em +Y, origem no centro da base)."""
    holes = load_holes()
    hollow_base(asm)
    doors_and_drawer(asm)
    asm.hard.add_mesh(craft.load_npz(TOP_NPZ, name="sink_top"), "kg_laminate")
    asm.hard.extrude([(-DEPTH / 2, cabinets.TOP_Z), (-DEPTH / 2 + 0.016, cabinets.TOP_Z),
                      (-DEPTH / 2 + 0.016, cabinets.TOP_Z + 0.09), (-DEPTH / 2, cabinets.TOP_Z + 0.09)],
                     "yz", -WIDTH / 2, WIDTH / 2, "kg_laminate")
    for hole in holes:
        steel_bowl(asm, hole)
    faucet(asm, (holes[0][0] + holes[1][0]) / 2)
    dirty_dishes(asm, rng, holes[0])
    soaking_pot(asm, holes[1])
    dish_rack(asm, 0.47, 0.0)
    ware.detergent_bottle(asm, -0.585, -0.2, cabinets.TOP_Z, 20.0)
