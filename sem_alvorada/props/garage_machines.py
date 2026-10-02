"""Máquinas da garagem: freezer horizontal, aquecedor de água e cortador de grama. Origem no centro da base, frente em +Y."""
from .kg_shapes import segments

FREEZER_W, FREEZER_D, FREEZER_H = 1.1, 0.7, 0.9
HEATER_RADIUS, HEATER_HEIGHT = 0.27, 1.52


# ---------------------------------------------------------------------------
# Freezer
# ---------------------------------------------------------------------------
def build_freezer(asm, rng):
    """Freezer horizontal amarelado: corpo de cantos arredondados, tampa com vedação, dobradiças e cadeado."""
    w, d = FREEZER_W, FREEZER_D
    asm.hard.soft_box(0, 0, 0.06, w, d, 0.78, "kg_enamel_yellow", radius=0.035, edge=0.012, corner_points=5)
    asm.hard.box(0, 0, 0.0, w - 0.1, d - 0.1, 0.06, "kg_toe")
    for sx in (-1, 1):
        for sy in (-1, 1):
            asm.round.cylinder(sx * (w / 2 - 0.07), sy * (d / 2 - 0.07), 0.0, 0.025, 0.02, "kg_rubber", seg=8)
    for y, thick in ((d / 2 - 0.008, 0.012), (-d / 2 + 0.008, 0.012)):
        asm.hard.box(0, y, 0.832, w - 0.03, thick, 0.014, "kg_gasket")
    for x in (-w / 2 + 0.008, w / 2 - 0.008):
        asm.hard.box(x, 0, 0.832, 0.012, d - 0.03, 0.014, "kg_gasket")
    asm.hard.soft_box(0, 0.006, 0.845, w + 0.012, d + 0.012, 0.062, "kg_enamel_yellow", radius=0.04, edge=0.015, corner_points=5)
    for x in (-0.38, 0.38):
        asm.crisp.box(x, -d / 2 + 0.012, 0.83, 0.08, 0.02, 0.06, "kg_chrome")
        with asm.round.at(x, -d / 2 + 0.012, 0.88, ry=90):
            asm.round.cylinder(0, 0, -0.04, 0.012, 0.08, "kg_chrome", seg=8)
    for sx in (-1, 1):
        asm.round.tube((sx * 0.15, d / 2 + 0.006, 0.872), (sx * 0.15, d / 2 + 0.04, 0.872), 0.008, "kg_chrome", seg=8)
    asm.round.tube((-0.15, d / 2 + 0.04, 0.872), (0.15, d / 2 + 0.04, 0.872), 0.012, "kg_chrome", seg=segments(10, 6))
    asm.crisp.box(0.0, d / 2 + 0.012, 0.8, 0.06, 0.01, 0.08, "kg_chrome")
    asm.crisp.soft_box(0.0, d / 2 + 0.05, 0.742, 0.045, 0.02, 0.05, "kg_brass", radius=0.008, edge=0.004, corner_points=3)
    asm.round.tube_path([(-0.012, d / 2 + 0.05, 0.79), (-0.014, d / 2 + 0.05, 0.815), (0.0, d / 2 + 0.05, 0.832), (0.014, d / 2 + 0.05, 0.815),
                         (0.012, d / 2 + 0.05, 0.79)], 0.0035, "kg_chrome", sides=6, resolution=5)
    asm.hard.panel(0.1, 0.0, 0.9078, 0.5, 0.38, "kg_smudge", "top")
    asm.crisp.box(-0.38, d / 2 + 0.004, 0.874, 0.1, 0.004, 0.026, "kg_chrome")


# ---------------------------------------------------------------------------
# Aquecedor de água
# ---------------------------------------------------------------------------
def _pipe(asm, points, radius, material="kg_copper"):
    asm.round.tube_path(points, radius, material, sides=segments(8, 6), resolution=6)


def build_heater(asm, rng):
    """Aquecedor de água de 100 L: tanque encapado, painel do termostato, válvula de alívio e canos de cobre."""
    radius, height = HEATER_RADIUS, HEATER_HEIGHT
    sides = segments(28)
    asm.round.lathe([(0.0, 0.0), (radius * 0.9, 0.0), (radius * 0.94, 0.03), (radius * 0.98, 0.07), (radius, 0.12),
                     (radius, height - 0.14), (radius * 0.97, height - 0.07), (radius * 0.8, height - 0.015), (radius * 0.4, height),
                     (0.0, height)], 0, 0, 0, "kg_heater", seg=sides, smooth=True, cap_bottom=False, cap_top=False)
    asm.round.cylinder(0, 0, 0.0, radius * 0.96, 0.05, "kg_tin", seg=sides)
    asm.round.lathe([(radius * 1.001, 0.62), (radius * 1.001, 0.66)], 0, 0, 0, "kg_tin", seg=sides, cap_bottom=False, cap_top=False)
    asm.hard.soft_box(0, radius * 0.96, 0.22, 0.2, 0.05, 0.2, "kg_plastic_dark", radius=0.012, edge=0.006, corner_points=3)
    with asm.round.at(0.0, radius * 0.96 + 0.025, 0.35, rx=-90):
        asm.round.lathe([(0.0, 0.0), (0.03, 0.0), (0.034, 0.012), (0.03, 0.026), (0.0, 0.028)], 0, 0, 0, "kg_plastic_white",
                        seg=segments(14), smooth=True, cap_bottom=False, cap_top=False)
    asm.round.panel(0.0, radius * 0.96 + 0.0255, 0.265, 0.17, 0.06, "paper_white", "front")
    asm.round.dial(0.1, radius * 0.99, 1.05, 0.04, "kg_gauge", 20)
    asm.round.panel(-0.07, radius * 0.99 + 0.001, 0.55, 0.08, 0.1, "toy_yellow", "front")
    for side, color in ((-0.09, "toy_blue"), (0.09, "toy_red")):
        _pipe(asm, [(side, 0.0, height - 0.02), (side, 0.0, height + 0.18), (side, 0.07, height + 0.3), (side, 0.18, height + 0.34),
                    (side, 0.32, height + 0.34)], 0.0125)
        asm.round.cylinder(side, 0.0, height + 0.1, 0.02, 0.06, "kg_brass", seg=8)
        asm.round.tube((side - 0.03, 0.0, height + 0.13), (side + 0.03, 0.0, height + 0.13), 0.005, color, seg=6)
    asm.round.tube((radius - 0.01, 0.0, 1.2), (radius + 0.06, 0.0, 1.2), 0.012, "kg_brass", seg=8)
    _pipe(asm, [(radius + 0.06, 0.0, 1.2), (radius + 0.09, 0.0, 1.0), (radius + 0.09, 0.0, 0.4), (radius + 0.06, 0.0, 0.05)], 0.008)
    asm.round.lathe([(0.0, 0.0), (0.09, 0.0), (0.08, 0.06), (0.05, 0.12), (0.045, 0.2), (0.0, 0.2)], 0, 0, height, "kg_tin", seg=segments(16),
                    smooth=True, cap_bottom=False, cap_top=False)
    asm.round.tube((0.0, 0.0, height + 0.18), (0.0, 0.0, 1.1 + height), 0.05, "kg_tin", seg=segments(14))
    asm.hard.panel(0.0, 0.0, 0.0006, 0.5, 0.5, "kg_oil_stain", "top")


# ---------------------------------------------------------------------------
# Cortador de grama
# ---------------------------------------------------------------------------
def _wheel(asm, x, y, radius, width, hub_side):
    """Roda de cortador: pneu de banda, aro e calota; o eixo corre em X."""
    sides = segments(18)
    half = width / 2
    with asm.round.at(x, y, radius, ry=90):
        asm.round.lathe([(radius * 0.55, -half), (radius * 0.85, -half), (radius, -half * 0.75), (radius, half * 0.75),
                         (radius * 0.85, half), (radius * 0.55, half)], 0, 0, 0, "kg_tire", seg=sides, smooth=True,
                        cap_bottom=False, cap_top=False, uv=3.0)
        asm.round.lathe([(0.0, half * 0.9), (radius * 0.5, half * 0.9), (radius * 0.55, half * 0.5), (radius * 0.55, -half * 0.5)],
                        0, 0, 0, "kg_plastic_dark", seg=sides, smooth=True, cap_bottom=False, cap_top=False)
        asm.round.cylinder(0, 0, hub_side * half * 0.5, radius * 0.12, 0.02, "kg_chrome", seg=8)


def build_mower(asm, rng):
    """Cortador a gasolina de empurrar: carenagem, motor com puxador, rodas, guidão dobrado e saco de grama."""
    asm.round.rounded_loft([(0.11, 0.50, 0.56, 0.07, 0, 0.0), (0.2, 0.46, 0.5, 0.1, 0, 0.0), (0.27, 0.40, 0.42, 0.13, 0, 0.0)],
                           "kg_mower_red", corner_points=5, caps=(False, True))
    asm.round.rounded_loft([(0.108, 0.50, 0.56, 0.07, 0, 0.0), (0.113, 0.49, 0.55, 0.07, 0, 0.0)], "kg_plastic_dark", corner_points=5,
                           caps=(False, False))
    asm.hard.soft_box(0.0, 0.0, 0.27, 0.26, 0.26, 0.09, "kg_plastic_dark", radius=0.08, edge=0.025, corner_points=5)
    asm.round.cylinder(0.0, 0.0, 0.36, 0.1, 0.012, "kg_plastic_dark", seg=segments(14))
    asm.round.cylinder(0.06, 0.07, 0.372, 0.026, 0.018, "kg_plastic_dark", seg=10)
    asm.round.tube_path([(-0.1, -0.1, 0.372), (-0.15, -0.15, 0.38), (-0.2, -0.17, 0.33), (-0.22, -0.17, 0.2)], 0.003, "kg_plastic_white",
                        sides=4, resolution=4)
    asm.hard.box(0.0, 0.23, 0.14, 0.34, 0.06, 0.1, "kg_plastic_dark")
    for sx in (-1, 1):
        _wheel(asm, sx * 0.27, 0.2, 0.075, 0.045, sx)
        _wheel(asm, sx * 0.27, -0.2, 0.1, 0.05, sx)
    for sx in (-1, 1):
        bottom = (sx * 0.2, -0.27, 0.22)
        asm.round.tube_path([bottom, (sx * 0.19, -0.4, 0.5), (sx * 0.17, -0.5, 0.85), (sx * 0.16, -0.54, 1.0)], 0.0125, "kg_tin",
                            sides=segments(8, 6), resolution=6)
    asm.round.tube((-0.16, -0.54, 1.0), (0.16, -0.54, 1.0), 0.0135, "kg_rubber", seg=segments(10, 6))
    asm.round.tube_path([(-0.17, -0.5, 0.88), (-0.1, -0.5, 0.9), (0.1, -0.5, 0.9), (0.17, -0.5, 0.88)], 0.008, "kg_chrome", sides=6,
                        resolution=4)
    asm.round.tube_path([(0.16, -0.5, 0.9), (0.14, -0.4, 0.7), (0.06, -0.12, 0.4), (0.04, -0.05, 0.37)], 0.0025, "kg_gasket", sides=4,
                        resolution=6)
    asm.hard.soft_box(0.0, -0.4, 0.07, 0.38, 0.16, 0.22, "kg_tarp", radius=0.04, edge=0.012, corner_points=4)
    asm.round.panel(-0.12, 0.2801, 0.2, 0.08, 0.08, "toy_yellow", "front")
    for _ in range(14):
        asm.round.box(rng.uniform(-0.2, 0.2), rng.uniform(-0.22, 0.25), 0.114, 0.012, 0.004, 0.003, "kg_food_old")
