"""Tralhas da garagem: escada de alumínio, mangueira, extensão, caixa de ferramentas, galão, enxada, lâmpada nua, pneus.

Cada função desenha uma peça numa `Assembly` com a origem no centro da base e a frente em +Y.
"""
import math

from . import garage_tools as tools
from .kg_shapes import segments


def build_ladder(asm, rng):
    """Escada de alumínio de 6 degraus, fechada e encostada na parede (inclinada para a parede, rx = 7 graus)."""
    height, width = 1.78, 0.44
    with asm.at(0, 0, 0, rx=7):
        for side in (-1, 1):
            asm.hard.box(side * width / 2, 0.0, 0.0, 0.04, 0.025, height, "kg_aluminum")
            asm.hard.box(side * (width / 2 - 0.012), 0.0, 0.0, 0.016, 0.05, height, "kg_aluminum")
            asm.hard.box(side * width / 2, -0.07, 0.0, 0.04, 0.025, height, "kg_aluminum")
            asm.round.cylinder(side * width / 2, 0.0, -0.01, 0.022, 0.03, "kg_rubber", seg=8)
        for step in range(6):
            z = 0.28 + step * 0.26
            asm.hard.box(0, 0.015, z, width, 0.085, 0.016, "kg_aluminum")
            for rib in (-0.025, 0.0, 0.025):
                asm.round.box(0, 0.015 + rib, z + 0.0165, width - 0.04, 0.004, 0.0015, "kg_aluminum")
        asm.hard.box(0, -0.03, height - 0.02, width + 0.06, 0.1, 0.03, "kg_plastic_dark")
        asm.round.box(0.0, 0.0, 0.5, 0.2, 0.001, 0.12, "toy_yellow")
        for spot in range(5):
            asm.round.box(rng.uniform(-0.18, 0.18), 0.02, rng.uniform(0.3, 1.5), 0.02, 0.0015, 0.012, "toy_blue")


def build_hose(asm, rng):
    """Mangueira de jardim enrolada num suporte de parede (espiral no plano XZ), com o esguicho de latão pendurado."""
    asm.hard.box(0, 0.01, -0.06, 0.12, 0.02, 0.2, "kg_tin")
    asm.round.tube((0, 0.02, -0.02), (0, 0.2, -0.02), 0.012, "kg_tin", seg=8)
    asm.round.tube((0, 0.2, -0.02), (0, 0.2, 0.03), 0.012, "kg_tin", seg=8)
    turns, steps, centre = 6, 18, -0.24
    points = []
    for index in range(turns * steps + 1):
        angle = 2 * math.pi * index / steps
        turn = index / steps
        radius = 0.17 - 0.003 * turn
        points.append((radius * math.sin(angle), 0.04 + 0.027 * turn, centre + radius * math.cos(angle)))
    asm.round.tube_path(points, 0.0095, "kg_hose", sides=segments(8, 6), resolution=2)
    end = points[-1]
    asm.round.tube_path([end, (end[0] + 0.03, end[1] + 0.01, end[2] - 0.12), (end[0] + 0.05, end[1], end[2] - 0.25)], 0.0095, "kg_hose",
                        sides=segments(8, 6), resolution=4)
    asm.round.cylinder(end[0] + 0.05, end[1], end[2] - 0.31, 0.016, 0.07, "kg_brass", seg=10)


def build_cord_coil(asm, rng):
    """Extensão laranja em rolo frouxo, com a tomada múltipla e o plugue pendurados no fim."""
    points = []
    turns, steps = 4, 16
    for index in range(turns * steps + 1):
        angle = 2 * math.pi * index / steps
        radius = 0.11 - 0.004 * (index / steps)
        points.append((radius * math.cos(angle), radius * math.sin(angle), 0.008 + 0.018 * (index / steps)))
    asm.round.tube_path(points, 0.0045, "kg_cord_orange", sides=6, resolution=2)
    end = points[-1]
    asm.round.tube_path([end, (end[0] + 0.08, end[1] + 0.05, 0.01), (end[0] + 0.16, end[1] + 0.02, 0.01)], 0.0045, "kg_cord_orange", sides=6, resolution=4)
    asm.hard.soft_box(end[0] + 0.2, end[1] + 0.02, 0.0, 0.1, 0.045, 0.03, "kg_cord_orange", radius=0.008, edge=0.005, corner_points=3)
    for slot in range(3):
        asm.round.box(end[0] + 0.17 + slot * 0.03, end[1] + 0.02, 0.0303, 0.014, 0.01, 0.0008, "kg_gasket")


def build_toolbox(asm, rng):
    """Caixa de ferramentas de aço vermelho aberta: tampa levantada, alça, trincos e as ferramentas na bandeja."""
    width, depth, height = 0.46, 0.2, 0.17
    asm.hard.box(0, 0, 0.0, width, depth, height, "kg_toolbox_red")
    asm.round.box(0, 0, height + 0.0005, width - 0.03, depth - 0.03, 0.001, "kg_tool_steel")
    with asm.hard.at(0, -depth / 2, height, rx=10):
        asm.hard.box(0, 0, 0.0, width, 0.012, depth, "kg_toolbox_red")
    asm.round.tube_path([(-0.18, 0.0, height), (-0.18, 0.0, height + 0.07), (0.18, 0.0, height + 0.07), (0.18, 0.0, height)], 0.006,
                        "kg_chrome", sides=6, resolution=5)
    for x in (-0.12, 0.0, 0.12):
        asm.round.box(x, 0.0, height + 0.001, 0.1, 0.12, 0.016, "kg_tool_steel")
    with asm.at(-0.1, -0.02, height + 0.018, rx=90, rz=20):
        tools.pliers(asm)
    asm.crisp.box(0, depth / 2 + 0.004, height - 0.05, 0.05, 0.01, 0.03, "kg_chrome")


def build_jerrycan(asm, rng):
    """Galão de gasolina vermelho de 5 L: corpo vincado, bico com tampa e a alça de transporte."""
    asm.hard.soft_box(0, 0, 0.0, 0.34, 0.14, 0.36, "kg_mower_red", radius=0.03, edge=0.015, corner_points=4)
    for sign in (-1, 1):
        asm.round.box(0, sign * 0.0712, 0.18, 0.3, 0.003, 0.0035, "kg_mower_red")
        asm.round.tube((-0.14, sign * 0.07, 0.04), (0.14, sign * 0.07, 0.32), 0.0035, "kg_mower_red", seg=4)
        asm.round.tube((0.14, sign * 0.07, 0.04), (-0.14, sign * 0.07, 0.32), 0.0035, "kg_mower_red", seg=4)
    asm.hard.box(-0.06, 0.0, 0.36, 0.14, 0.05, 0.02, "kg_mower_red")
    asm.round.tube_path([(-0.1, 0.0, 0.36), (-0.1, 0.0, 0.42), (0.06, 0.0, 0.42), (0.1, 0.0, 0.37)], 0.012, "kg_mower_red", sides=8,
                        resolution=4)
    asm.round.cylinder(0.11, 0.0, 0.36, 0.022, 0.04, "kg_plastic_dark", seg=12)
    asm.round.cylinder(0.11, 0.0, 0.4, 0.026, 0.012, "kg_brass", seg=12)


def build_tool_leaners(asm, rng):
    """Rastelo, pá e vassoura encostados no canto, inclinados para a parede (rx = 8 graus)."""
    def lean(x, build):
        with asm.at(x, 0.0, 0.0, rx=8):
            build()

    def rake():
        asm.round.tube((0, 0, 0.0), (0, 0, 1.5), 0.0125, "kg_oak", seg=8)
        asm.hard.box(0, 0, 1.45, 0.4, 0.015, 0.025, "kg_tool_steel")
        for tine in range(11):
            asm.round.tube((-0.18 + tine * 0.036, 0, 1.45), (-0.18 + tine * 0.036, 0.0, 1.35), 0.0022, "kg_tool_steel", seg=4)

    def shovel():
        asm.round.tube((0, 0, 0.3), (0, 0, 1.45), 0.0135, "kg_oak", seg=8)
        asm.round.tube((-0.05, 0, 1.45), (0.05, 0, 1.45), 0.012, "kg_oak", seg=8)
        asm.hard.extrude([(-0.1, 0.35), (0.1, 0.35), (0.12, 0.2), (0.07, 0.03), (0.0, 0.0), (-0.07, 0.03), (-0.12, 0.2)], "xz", -0.0015, 0.0015,
                         "kg_tool_steel")
        asm.round.tube((0, 0, 0.3), (0, 0, 0.4), 0.018, "kg_tool_steel", seg=8)

    def broom():
        asm.round.tube((0, 0, 0.2), (0, 0, 1.45), 0.0115, "kg_pine", seg=8)
        asm.soft.soft_box(0, 0, 0.0, 0.3, 0.05, 0.22, "kg_bread_crust", radius=0.012, edge=0.01, corner_points=3)
        asm.hard.box(0, 0, 0.2, 0.31, 0.06, 0.04, "kg_pine")

    lean(-0.2, rake)
    lean(0.0, shovel)
    lean(0.22, broom)


def build_bare_bulb(asm, rng):
    """Lâmpada nua pendurada por um fio no soquete de porcelana; queimada, com o filamento partido."""
    asm.round.tube_path([(0, 0, 0.45), (0.01, 0, 0.3), (0, 0, 0.12)], 0.0035, "kg_gasket", sides=5, resolution=4)
    asm.round.cylinder(0, 0, 0.1, 0.02, 0.05, "kg_porcelain", seg=10)
    asm.round.lathe([(0.0, 0.0), (0.013, 0.0), (0.03, 0.04), (0.03, 0.07), (0.013, 0.1), (0.0, 0.105)], 0, 0, -0.02, "glass_clear",
                    seg=segments(14), smooth=True, cap_bottom=False, cap_top=False)
    asm.round.tube((0.0, 0, 0.02), (0.0, 0, 0.055), 0.0006, "kg_tool_steel", seg=3)


def build_tires(asm, rng):
    """Dois pneus velhos empilhados, com a banda gasta e poeira."""
    sides = segments(20)
    for index in range(2):
        z = index * 0.2
        tire = [(0.225 + 0.09 * math.cos(math.radians(a)), z + 0.1 + 0.1 * math.sin(math.radians(a))) for a in range(-90, 271, 30)]
        asm.round.lathe([(r, zz) for r, zz in tire], 0, 0, 0, "kg_tire", seg=sides, smooth=True, cap_bottom=False, cap_top=False, uv=1.4)
