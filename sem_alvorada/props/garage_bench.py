"""Bancada de trabalho do Dan: tampo de tábuas grossas, gavetas, morsa, e o que ficou em cima quando ele parou.

Referências: bancada de 2,0 x 0,65 m com tampo a 0,90 m (tábuas de 4 cm, as de pinho mais o tempo). O espaço
em torno de x = -0,54 (a pilha 5, `Item_BATTERY_5`) fica livre.
"""
from . import garage_storage as storage
from . import garage_tools as tools
from . import kitchen_ware as ware
from .kg_shapes import segments

LENGTH, DEPTH, TOP = 2.0, 0.65, 0.90
TOP_T = 0.055
BOARDS = 5
LEG = 0.075


def frame(asm):
    """Pernas, travessas, prateleira de baixo e mão-francesa de trás."""
    half_x, half_y = LENGTH / 2 - 0.045, DEPTH / 2 - 0.045
    for sx in (-1, 1):
        for sy in (-1, 1):
            asm.hard.box(sx * half_x, sy * half_y, 0.0, LEG, LEG, TOP - TOP_T, "kg_pine")
    for z0, height in ((TOP - TOP_T - 0.1, 0.1), (0.2, 0.07)):
        for sy in (-1, 1):
            asm.hard.box(0, sy * half_y, z0, LENGTH - 0.09, 0.04, height, "kg_pine")
        for sx in (-1, 1):
            asm.hard.box(sx * half_x, 0, z0, 0.04, DEPTH - 0.09, height, "kg_pine")
    board_w = (DEPTH - 0.1) / 3
    for index in range(3):
        asm.hard.box(0, -DEPTH / 2 + 0.05 + board_w * (index + 0.5), 0.27, LENGTH - 0.09, board_w - 0.004, 0.022, "kg_pine")
    for sign in (-1, 1):
        asm.hard.bar((sign * 0.8, -half_y + 0.025, 0.26), (-sign * 0.8, -half_y + 0.025, 0.76), 0.03, "kg_pine")


def top(asm, rng):
    """Cinco tábuas com frestas e altura levemente diferente (a do meio cobre o eixo), mais o rodapé de trás."""
    width = DEPTH / BOARDS
    for index in range(BOARDS):
        lift = rng.uniform(-0.0008, 0.0008)
        asm.hard.box(0, -DEPTH / 2 + width * (index + 0.5), TOP - TOP_T + lift, LENGTH, width - 0.003, TOP_T, "kg_bench_wood")
    asm.hard.box(0, -DEPTH / 2 + 0.022, TOP, LENGTH, 0.04, 0.12, "kg_pine")


def drawers(asm, rng):
    """Bloco de três gavetas sob a ponta esquerda; a do meio ficou aberta, com parafusos e fita dentro."""
    x0, x1 = -0.97, -0.5
    cx, width = (x0 + x1) / 2, x1 - x0
    z_base, height = 0.3, TOP - TOP_T - 0.3 - 0.1
    asm.hard.box(cx, -0.02, z_base, width, DEPTH - 0.13, height, "kg_pine")
    row = height / 3
    front = DEPTH / 2 - 0.055
    for index in range(3):
        z0 = z_base + index * row + 0.004
        out = 0.0
        if index == 1:
            out = 0.1
            drawer_box(asm, cx, front + out - 0.011 - 0.15, z0, width - 0.04, 0.3, row - 0.012, rng)
        asm.hard.box(cx, front + out, z0, width - 0.012, 0.022, row - 0.008, "kg_oak")
        asm.round.tube((cx - 0.07, front + out + 0.011, z0 + row / 2), (cx + 0.07, front + out + 0.011, z0 + row / 2), 0.006,
                       "kg_tool_steel", seg=8)
        for dx in (-0.07, 0.07):
            asm.round.tube((cx + dx, front + out + 0.011, z0 + row / 2), (cx + dx, front + out + 0.03, z0 + row / 2), 0.004,
                           "kg_tool_steel", seg=6)


def drawer_box(asm, cx, cy, z0, width, depth, height, rng):
    """Caixa da gaveta aberta: laterais, fundo e o que ela guarda."""
    wall = 0.012
    asm.hard.box(cx, cy, z0, width, depth, wall, "kg_pine")
    for side in (-1, 1):
        asm.hard.box(cx + side * (width / 2 - wall / 2), cy, z0, wall, depth, height, "kg_pine")
    asm.hard.box(cx, cy - depth / 2 + wall / 2, z0, width, wall, height, "kg_pine")
    for _ in range(26):
        asm.round.cylinder(cx + rng.uniform(-0.17, 0.17), cy + rng.uniform(-0.1, 0.1), z0 + wall, 0.0025, rng.uniform(0.02, 0.04),
                           "kg_tool_steel", seg=5)
    asm.round.lathe([(0.026, 0.0), (0.03, 0.01), (0.03, 0.03), (0.026, 0.04)], cx + 0.05, cy - 0.08, z0 + wall, "toy_yellow",
                    seg=segments(10), cap_bottom=False, cap_top=False)


def vise(asm, x, y):
    """Morsa de ferro fundido presa na quina da frente: mandíbulas, guias, fuso e a barra com bolas nas pontas."""
    z = TOP
    asm.hard.box(x, y - 0.035, z, 0.22, 0.13, 0.03, "kg_tool_steel")
    asm.hard.box(x, y - 0.02, z + 0.03, 0.2, 0.05, 0.075, "kg_tool_steel")
    asm.hard.box(x, y + 0.062, z + 0.032, 0.2, 0.04, 0.073, "kg_tool_steel")
    for dx in (-0.075, 0.075):
        asm.round.tube((x + dx, y, z + 0.06), (x + dx, y + 0.17, z + 0.06), 0.008, "kg_chrome", seg=8)
    asm.round.tube((x, y + 0.08, z + 0.065), (x, y + 0.24, z + 0.065), 0.01, "kg_tool_steel", seg=10)
    asm.round.tube((x - 0.1, y + 0.24, z + 0.065), (x + 0.1, y + 0.24, z + 0.065), 0.006, "kg_chrome", seg=8)
    for side in (-1, 1):
        asm.round.sphere(x + side * 0.1, y + 0.24, z + 0.065, 0.012, "kg_chrome", seg=8, rings=5)
    asm.crisp.box(x, y + 0.04, z + 0.105, 0.14, 0.02, 0.004, "kg_chrome")


def radio(asm, x, y, yaw_deg):
    """Rádio de pilha com antena, alça e fita no deck, parado desde que acabou a bateria."""
    with asm.hard.at(x, y, TOP, rz=yaw_deg):
        asm.hard.soft_box(0, 0, 0.0, 0.32, 0.12, 0.17, "kg_plastic_dark", radius=0.015, edge=0.007, corner_points=3)
    with asm.round.at(x, y, TOP, rz=yaw_deg):
        asm.round.panel(0, 0.0605, 0.085, 0.12, 0.05, "glass_dark", "front")
        for side in (-1, 1):
            asm.round.dial(side * 0.1, 0.0605, 0.085, 0.045, "kg_speaker", 18)
        asm.round.tube((0.13, -0.04, 0.17), (0.04, -0.08, 0.5), 0.0025, "kg_chrome", seg=5)
        asm.round.tube_path([(-0.1, 0.0, 0.17), (-0.1, 0.0, 0.215), (0.1, 0.0, 0.215), (0.1, 0.0, 0.17)], 0.007, "kg_plastic_dark",
                            sides=6, resolution=4)


def clutter(asm, rng):
    """O que sobrou em cima: martelo, frascos de parafusos, caneca de café velho, caixa de pregos e panos."""
    with asm.at(0.46, 0.08, TOP, rx=90, rz=24):
        tools.hammer(asm)
    for index, (x, y) in enumerate(((-0.30, -0.22), (-0.2, -0.2))):
        asm.round.turned_bowl(x, y, TOP, [(0.04, 0.0), (0.045, 0.01), (0.045, 0.12), (0.04, 0.125)], 0.003, "glass_clear",
                              seg=segments(12))
        asm.round.cylinder(x, y, TOP + 0.003, 0.038, 0.05 + 0.02 * index, "kg_tool_steel", seg=segments(10))
        asm.round.cylinder(x, y, TOP + 0.125, 0.044, 0.014, "kg_tin", seg=segments(12))
    ware.mug(asm, 0.18, 0.18, TOP, 0.04, 0.095, "kg_porcelain", handle_deg=30.0, coffee=True)
    with asm.hard.at(0.0, -0.1, TOP, rz=-18):
        asm.hard.box(0, 0, 0, 0.12, 0.08, 0.03, "kg_box_plain")
    for _ in range(18):
        asm.round.tube((rng.uniform(-0.08, 0.1), rng.uniform(-0.14, 0.0), TOP + 0.002), (rng.uniform(-0.08, 0.1) + 0.02, rng.uniform(-0.14, 0.0), TOP + 0.002),
                       0.0016, "kg_tool_steel", seg=4)
    asm.soft.soft_box(0.66, -0.15, TOP, 0.2, 0.14, 0.03, "coat_dark", radius=0.04, edge=0.012, corner_points=4)
    asm.soft.soft_box(0.69, -0.14, TOP + 0.03, 0.14, 0.1, 0.02, "kg_plastic_dark", radius=0.03, edge=0.01, corner_points=4)
    with asm.at(0.2, -0.05, TOP, rx=90, rz=-100):
        tools.tape_measure(asm)
    asm.round.lathe([(0.0, 0.0), (0.035, 0.0), (0.04, 0.02), (0.038, 0.07), (0.015, 0.09), (0.0, 0.09)], -0.12, 0.2, TOP,
                    "kg_tin", seg=segments(12), cap_bottom=False, cap_top=False)
    asm.round.tube((-0.12, 0.2, TOP + 0.085), (-0.04, 0.2, TOP + 0.12), 0.004, "kg_tin", seg=6)


def underneath(asm, rng):
    """Prateleira de baixo: uma caixa de papelão aberta com trapos, o balde vermelho e duas latas de tinta."""
    z = 0.292
    with asm.hard.at(-0.12, 0.0, z):
        storage.open_box(asm, 0.44, 0.34, 0.26, "kg_box_plain")
    asm.soft.soft_box(-0.1, 0.0, z + 0.2, 0.3, 0.22, 0.09, "coat_beige", radius=0.05, edge=0.02, corner_points=4)
    sides = segments(16)
    asm.round.lathe([(0.0, 0.0), (0.12, 0.0), (0.145, 0.27), (0.14, 0.28), (0.0, 0.28)], 0.45, 0.0, z, "kg_toolbox_red", seg=sides,
                    smooth=True, cap_bottom=False, cap_top=False)
    asm.round.tube_path([(0.31, 0.0, z + 0.27), (0.45, 0.0, z + 0.42), (0.59, 0.0, z + 0.27)], 0.004, "kg_chrome", sides=6,
                        resolution=6)
    for x in (0.76, 0.9):
        storage.paint_can(asm, x, 0.0, z, "toy_blue" if x < 0.8 else "toy_green")


def build_bench(asm, rng):
    frame(asm)
    top(asm, rng)
    drawers(asm, rng)
    vise(asm, 0.84, DEPTH / 2 - 0.1)
    radio(asm, -0.84, -0.02, 12.0)
    clutter(asm, rng)
    underneath(asm, rng)
