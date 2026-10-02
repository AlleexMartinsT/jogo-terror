"""Ferramentas de mão modeladas a partir das silhuetas de `kg_silhouettes`.

Cada função desenha a ferramenta pendurada: no plano XZ, com o furo de pendurar na origem, a espessura crescendo
em +Y a partir do plano. Para deitá-la numa bancada, entre em `with asm.at(x, y, z, rx=90)`: o comprimento passa
a correr em +Y e a espessura sobe em Z.
"""
from . import kg_silhouettes as shapes
from .kg_shapes import segments

THICKNESS = 0.03


def _seen(polygon):
    """Espelha o contorno em u: o X local do móvel cresce para a esquerda de quem olha de frente, e as silhuetas
    em `kg_silhouettes` (as do contorno à caneta) foram desenhadas com u para a direita de quem olha."""
    return [(-u, v) for u, v in reversed(polygon)]


def hammer(asm):
    """Martelo de unha: cabo de madeira de seção afilada e cabeça de aço com a unha curva."""
    middle = THICKNESS / 2
    asm.round.tube((0, middle, -0.30), (0, middle, -0.11), 0.0125, "kg_oak", seg=segments(10), r_end=0.0105, smooth=True)
    asm.round.sphere(0, middle, -0.30, 0.0128, "kg_oak", seg=8, rings=4, squash=0.6)
    asm.hard.extrude(_seen(shapes.HAMMER_HEAD), "xz", 0.0, THICKNESS, "kg_tool_steel")
    asm.round.cylinder(-0.05, middle, -0.12, 0.0145, 0.002, "kg_chrome", seg=10)


def wrench(asm):
    """Chave inglesa de boca aberta, aço forjado."""
    asm.hard.extrude(_seen(shapes.WRENCH), "xz", 0.004, 0.016, "kg_tool_steel")
    asm.round.tube((0.0, 0.01, -0.04), (0.0, 0.01, -0.12), 0.0035, "kg_chrome", seg=6)


def pliers(asm):
    """Alicate universal: corpo de aço, pino do eixo e cabos emborrachados vermelhos."""
    asm.hard.extrude(_seen(shapes.PLIERS_OUTLINE), "xz", 0.004, 0.016, "kg_tool_steel")
    with asm.round.at(0.0, 0.01, -0.07, rx=-90):
        asm.round.cylinder(0, 0, -0.01, 0.007, 0.022, "kg_chrome", seg=8)
    for side in (-1, 1):
        asm.round.tube((side * 0.029, 0.01, -0.2), (side * 0.0185, 0.01, -0.1), 0.0105, "toy_red", seg=segments(8), r_end=0.0095)


def saw(asm):
    """Serrote: lâmina fina de dentes, cabo de madeira escura com três rebites."""
    asm.round.extrude(_seen(shapes.SAW_BLADE), "xz", 0.012, 0.0135, "kg_tool_steel")
    asm.hard.extrude(_seen(shapes.SAW_HANDLE), "xz", 0.004, 0.024, "kg_oak")
    for point in ((0.02, -0.075), (0.0, -0.02), (-0.03, -0.075)):
        with asm.round.at(point[0], 0.0245, point[1], rx=-90):
            asm.round.cylinder(0, 0, 0, 0.004, 0.002, "kg_chrome", seg=6)
    with asm.round.at(-0.005, 0.0242, -0.05, rx=-90):
        asm.round.cylinder(0, 0, 0, 0.013, 0.0004, "kg_gasket", seg=10)


def screwdriver(asm, handle_material="toy_yellow", phillips=False):
    """Chave de fenda (ou Phillips): cabo torneado e haste cromada."""
    middle = 0.012
    asm.round.lathe([(0.0, -0.1), (0.011, -0.1), (0.0165, -0.075), (0.0175, -0.035), (0.0135, -0.006), (0.0, 0.0)],
                    0, middle, 0.0, handle_material, seg=segments(12), smooth=True, cap_bottom=False, cap_top=False)
    asm.round.tube((0, middle, -0.1), (0, middle, -0.255), 0.0033, "kg_chrome", seg=6)
    asm.crisp.box(0, middle, -0.265, 0.007 if not phillips else 0.0065, 0.0012 if not phillips else 0.0065, 0.012, "kg_tool_steel")


def tape_measure(asm):
    """Trena amarela de caixa arredondada com o gancho da fita."""
    asm.hard.soft_box(0, 0.02, -0.075, 0.075, 0.04, 0.075, "toy_yellow", radius=0.014, edge=0.006, corner_points=4)
    asm.round.box(0.0, 0.0405, -0.045, 0.04, 0.001, 0.025, "kg_gasket")
    asm.crisp.box(-0.045, 0.02, -0.07, 0.012, 0.004, 0.012, "kg_chrome")


def peg(asm, u, v, length=0.045):
    """Gancho de arame no furo do painel."""
    asm.round.tube((u, 0.0, v), (u, length, v), 0.0025, "kg_chrome", seg=5)
    asm.round.tube((u, length, v), (u, length, v + 0.012), 0.0025, "kg_chrome", seg=5)
