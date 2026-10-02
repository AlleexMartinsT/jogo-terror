"""Bicicleta rosa da Emma (aro 16): quadro de tubos, rodas com raios, rodinhas de apoio, cestinha e fitas no guidão.

Referências de bicicleta infantil aro 16: rodas de 40 cm de diâmetro, distância entre eixos de 72 cm, guidão a 70 cm.
O quadro fica no plano x = 0 e a bicicleta aponta para +Y.
"""
import math

from .kg_shapes import segments

WHEEL_R = 0.20
WHEELBASE = 0.72
REAR_HUB = (0.0, -WHEELBASE / 2, WHEEL_R)
FRONT_HUB = (0.0, WHEELBASE / 2, WHEEL_R)
BOTTOM_BRACKET = (0.0, -0.04, 0.17)
SEAT_TOP = (0.0, -0.17, 0.56)
HEAD_BOTTOM = (0.0, 0.265, 0.44)
HEAD_TOP = (0.0, 0.285, 0.58)
TUBE = 0.0135


def _tube(asm, a, b, radius=TUBE):
    asm.round.tube(a, b, radius, "kg_bike_tube", seg=segments(10, 6), smooth=True)


def frame(asm):
    """Quadro com tubo de descida, canos do selim, garfo curvo e as soldas nas juntas."""
    seat_mid = (0.0, -0.12, 0.42)
    for a, b in ((REAR_HUB, BOTTOM_BRACKET), (BOTTOM_BRACKET, HEAD_BOTTOM), (REAR_HUB, seat_mid), (BOTTOM_BRACKET, SEAT_TOP),
                 (seat_mid, (0.0, 0.272, 0.52)), (HEAD_BOTTOM, HEAD_TOP)):
        _tube(asm, a, b)
    for point in (BOTTOM_BRACKET, seat_mid, HEAD_BOTTOM, (0.0, 0.272, 0.52)):
        asm.round.sphere(*point, TUBE * 1.25, "kg_bike_tube", seg=8, rings=5)
    for side in (-1, 1):
        asm.round.tube_path([(side * 0.032, 0.27, 0.43), (side * 0.034, 0.30, 0.34), (side * 0.03, 0.34, 0.24),
                             (side * 0.025, 0.36, 0.2)], 0.0095, "kg_bike_tube", sides=segments(8, 6), resolution=6)
    asm.round.tube((-0.034, 0.27, 0.43), (0.034, 0.27, 0.43), 0.012, "kg_bike_tube", seg=8)
    asm.round.tube(SEAT_TOP, (0.0, -0.185, 0.62), 0.009, "kg_chrome", seg=8)
    asm.soft.soft_box(0.0, -0.19, 0.62, 0.13, 0.22, 0.045, "kg_vinyl_black", radius=0.05, edge=0.016, corner_points=5)
    asm.round.tube(HEAD_TOP, (0.0, 0.27, 0.70), 0.0105, "kg_chrome", seg=8)


def handlebar(asm, rng):
    """Guidão cromado com manoplas rosa, campainha e dois feixes de fitas de cetim."""
    asm.round.tube_path([(-0.2, 0.25, 0.77), (-0.19, 0.26, 0.72), (-0.1, 0.27, 0.70), (0.1, 0.27, 0.70), (0.19, 0.26, 0.72),
                         (0.2, 0.25, 0.77)], 0.0095, "kg_chrome", sides=8, resolution=6)
    for side in (-1, 1):
        asm.round.tube((side * 0.2, 0.25, 0.77), (side * 0.2, 0.25, 0.82), 0.0125, "plush_pink", seg=8)
        asm.round.sphere(side * 0.2, 0.25, 0.826, 0.0125, "plush_pink", seg=8, rings=4)
        for index in range(5):
            sway = 0.012 * math.sin(index * 1.7 + side)
            color = "plush_pink" if index % 2 else "plush_white"
            asm.round.surface(lambda u, v, s=side, sw=sway, c=index: (
                s * (0.2 + 0.006 * c) + sw * v, 0.25 + 0.01 * c * v + 0.012 * u, 0.79 - 0.2 * v), 1, 5, color, uv_size=(0.012, 0.2), flip=side > 0)
    asm.round.cylinder(0.12, 0.27, 0.708, 0.017, 0.016, "kg_chrome", seg=10, r_top=0.014)


def basket(asm, rng):
    """Cestinha de arame branco presa ao guidão, com margaridas de adesivo no fundo."""
    cx, cy, cz = 0.0, 0.31, 0.72
    radius, height = 0.11, 0.1
    sides = segments(18)
    for ring_z, ring_r in ((cz + height, radius), (cz + 0.01, radius * 0.92)):
        points = [(cx + ring_r * math.cos(2 * math.pi * i / sides), cy + ring_r * math.sin(2 * math.pi * i / sides), ring_z)
                  for i in range(sides + 1)]
        asm.round.tube_path(points, 0.0028, "kg_plastic_white", sides=5, resolution=1)
    for index in range(sides):
        angle = 2 * math.pi * index / sides
        top = (cx + radius * math.cos(angle), cy + radius * math.sin(angle), cz + height)
        bottom = (cx + radius * 0.92 * math.cos(angle), cy + radius * 0.92 * math.sin(angle), cz + 0.01)
        asm.round.tube(bottom, top, 0.0022, "kg_plastic_white", seg=4)
    asm.round.cylinder(cx, cy, cz + 0.005, radius * 0.92, 0.003, "kg_plastic_white", seg=sides)
    for dx in (-0.06, 0.06):
        asm.round.tube((dx, 0.27, 0.70), (dx * 1.3, cy - radius * 0.7, cz + 0.01), 0.003, "kg_plastic_white", seg=5)


def wheel(asm, y):
    """Roda com pneu de banda, aro cromado, cubo e 20 raios cruzados."""
    sides = segments(28)
    with asm.round.at(0.0, y, WHEEL_R, ry=90):
        major, minor = 0.172, 0.028
        tire = [(major + minor * math.cos(math.radians(a)), minor * math.sin(math.radians(a))) for a in range(-90, 271, 30)]
        asm.round.lathe(tire, 0, 0, 0, "kg_tire", seg=sides, smooth=True, cap_bottom=False, cap_top=False, uv=2.5)
        asm.round.lathe([(0.15, -0.012), (0.158, -0.014), (0.168, -0.012), (0.168, 0.012), (0.158, 0.014), (0.15, 0.012)], 0, 0, 0,
                        "kg_chrome", seg=sides, smooth=True, cap_bottom=False, cap_top=False)
        asm.round.cylinder(0, 0, -0.035, 0.016, 0.07, "kg_chrome", seg=10)
        asm.round.cylinder(0, 0, -0.012, 0.02, 0.024, "kg_chrome", seg=10)
    for index in range(20):
        angle = 2 * math.pi * index / 20
        side = 1 if index % 2 else -1
        hub = (side * 0.012, y + 0.02 * math.cos(angle), WHEEL_R + 0.02 * math.sin(angle))
        rim = (0.0, y + 0.152 * math.cos(angle + side * 0.45), WHEEL_R + 0.152 * math.sin(angle + side * 0.45))
        asm.round.tube(hub, rim, 0.0007, "kg_chrome", seg=3)


def training_wheels(asm):
    """Rodinhas de apoio: braço dobrado e roda de plástico, uma de cada lado do eixo traseiro."""
    for side in (-1, 1):
        asm.round.tube_path([(side * 0.03, REAR_HUB[1], WHEEL_R), (side * 0.1, REAR_HUB[1], 0.15), (side * 0.14, REAR_HUB[1], 0.09)],
                            0.005, "kg_tool_steel", sides=6, resolution=4)
        with asm.round.at(side * 0.15, REAR_HUB[1], 0.06, ry=90):
            asm.round.lathe([(0.0, -0.013), (0.055, -0.013), (0.06, -0.007), (0.06, 0.007), (0.055, 0.013), (0.0, 0.013)], 0, 0, 0,
                            "kg_plastic_dark", seg=segments(14), smooth=True, cap_bottom=False, cap_top=False)
            asm.round.cylinder(0, 0, side * 0.012, 0.016, 0.008, "toy_yellow", seg=8)


def drivetrain(asm):
    """Pedivela, coroa, pedais com a borracha desgastada e a corrente por baixo do protetor rosa."""
    x_side = 0.045
    with asm.round.at(x_side, BOTTOM_BRACKET[1], BOTTOM_BRACKET[2], ry=90):
        asm.round.lathe([(0.0, 0.0), (0.045, 0.0), (0.05, 0.004), (0.045, 0.008), (0.0, 0.008)], 0, 0, 0, "kg_chrome",
                        seg=segments(20), smooth=True, cap_bottom=False, cap_top=False)
    asm.round.tube((-0.05, BOTTOM_BRACKET[1], BOTTOM_BRACKET[2]), (0.06, BOTTOM_BRACKET[1], BOTTOM_BRACKET[2]), 0.01, "kg_chrome", seg=8)
    for side, drop in ((1, 1), (-1, -1)):
        end = (side * 0.07, BOTTOM_BRACKET[1] + drop * 0.02, BOTTOM_BRACKET[2] - drop * 0.085)
        asm.round.tube((side * 0.055, BOTTOM_BRACKET[1], BOTTOM_BRACKET[2]), end, 0.007, "kg_chrome", seg=6)
        asm.crisp.box(end[0] + side * 0.03, end[1], end[2], 0.07, 0.035, 0.014, "kg_plastic_dark")
    asm.round.tube_path([(0.04, BOTTOM_BRACKET[1], 0.215), (0.04, -0.2, 0.225), (0.04, -0.34, 0.22), (0.04, -0.34, 0.18),
                         (0.04, -0.2, 0.132), (0.04, BOTTOM_BRACKET[1], 0.125)], 0.003, "kg_tool_steel", sides=4, resolution=3)
    asm.round.surface(lambda u, v: (0.056, -0.34 + 0.32 * u, 0.22 - 0.07 * v + 0.02 * u), 4, 1, "kg_bike_pink", uv_size=(0.32, 0.07))


def fenders(asm):
    """Para-lamas rosa curvos sobre as duas rodas."""
    for y in (-WHEELBASE / 2, WHEELBASE / 2):
        asm.round.surface(lambda u, v, yc=y: (-0.03 + 0.06 * v, yc + 0.215 * math.sin(math.radians(-40 + 130 * u)),
                                              WHEEL_R + 0.215 * math.cos(math.radians(-40 + 130 * u))), 12, 1, "kg_bike_pink",
                          uv_size=(0.5, 0.06), flip=True)


def helmet(asm):
    """Capacete rosa pendurado no guidão, com a tira solta."""
    with asm.soft.at(0.0, -0.19, 0.69, rx=-12):
        asm.soft.sphere(0, 0, 0.0, 0.095, "plush_pink", seg=segments(14), rings=8, squash=0.72)
    asm.round.tube_path([(0.05, -0.12, 0.665), (0.07, -0.08, 0.62), (0.04, -0.1, 0.6)], 0.005, "kg_gasket", sides=4, resolution=4)


def build_bicycle(asm, rng):
    frame(asm)
    handlebar(asm, rng)
    basket(asm, rng)
    wheel(asm, REAR_HUB[1])
    wheel(asm, FRONT_HUB[1])
    training_wheels(asm)
    drivetrain(asm)
    fenders(asm)
    helmet(asm)
