"""Louça, panelas, talheres e utensílios da cozinha, desenhados numa `Assembly` (peças torneadas e chapas finas).

Pratos, copos e panelas nascem de um perfil (raio, altura) girado em torno de Z (`lathe`); talheres são
contornos 2D extrudados em 1,8 mm. Cada função recebe a posição do centro da base e devolve nada: acumula
na montagem. Restos de comida usam o material `kg_food_old` (três semanas de mofo).
"""
import math

from .kg_shapes import segments

PLATE_OUTER = [(0.0, 0.002), (0.50, 0.002), (0.52, 0.0), (0.58, 0.0), (0.60, 0.003), (0.88, 0.014), (1.0, 0.022)]
PLATE_INNER = [(0.985, 0.0235), (0.88, 0.0185), (0.62, 0.0075), (0.0, 0.0065)]
FORK = [(-0.006, 0.0), (0.006, 0.0), (0.005, 0.07), (0.016, 0.09), (0.016, 0.135), (0.012, 0.135), (0.012, 0.105),
        (0.0045, 0.105), (0.0045, 0.138), (0.0, 0.138), (-0.0045, 0.138), (-0.0045, 0.105), (-0.012, 0.105),
        (-0.012, 0.135), (-0.016, 0.135), (-0.016, 0.09), (-0.005, 0.07)]
KNIFE = [(-0.007, 0.0), (0.007, 0.0), (0.006, 0.105), (0.009, 0.112), (0.009, 0.20), (0.0, 0.215), (-0.007, 0.115),
         (-0.006, 0.105)]
SPOON_HANDLE = [(-0.006, 0.0), (0.006, 0.0), (0.0045, 0.08), (0.007, 0.10), (-0.007, 0.10), (-0.0045, 0.08)]


def plate(asm, cx, cy, z0, radius=0.12, tilt=(0.0, 0.0), band=True, food=False):
    """Prato raso girado em torno de Z; `tilt` (rx, ry em graus) inclina para empilhar torto."""
    sides = segments(16)
    profile = [(r * radius, z) for r, z in PLATE_OUTER + PLATE_INNER]
    with asm.round.at(cx, cy, z0, rx=tilt[0], ry=tilt[1]):
        asm.round.lathe(profile, 0, 0, 0, "kg_porcelain_band" if band else "kg_porcelain", seg=sides, smooth=True,
                        cap_bottom=False, cap_top=False)
        if food:
            asm.round.sphere(radius * 0.1, radius * 0.05, 0.0105, radius * 0.38, "kg_food_old", seg=8, rings=4, squash=0.13)


def plate_stack(asm, rng, cx, cy, z0, count, radius=0.12, food_every=2):
    """Pilha torta de pratos; a cada `food_every` um tem restos secos."""
    for index in range(count):
        plate(asm, cx + rng.uniform(-0.012, 0.012), cy + rng.uniform(-0.012, 0.012), z0 + index * 0.0125, radius,
              tilt=(rng.uniform(-2.5, 2.5), rng.uniform(-2.5, 2.5)), food=index % food_every == 0)


def bowl(asm, cx, cy, z0, radius=0.075, height=0.06, material="kg_porcelain", food=False):
    """Tigela de cereal com pé baixo; com `food`, o fundo guarda leite coalhado e cereal murcho."""
    outer = [(radius * 0.55, 0.0), (radius * 0.62, 0.006), (radius * 0.95, height * 0.55), (radius, height)]
    asm.round.turned_bowl(cx, cy, z0, outer, 0.004, material, seg=segments(16))
    if food:
        asm.round.lathe([(0.0, 0.0), (radius * 0.55, 0.0), (radius * 0.82, 0.014), (radius * 0.7, 0.015), (0.0, 0.016)],
                        cx, cy, z0 + 0.008, "kg_food_old", seg=segments(12), cap_bottom=False, cap_top=False)


def mug(asm, cx, cy, z0, radius=0.04, height=0.095, material="kg_porcelain", handle_deg=0.0, coffee=False):
    """Caneca com alça de tubo curvo; `coffee` deixa um dedo de café frio com película."""
    sides = segments(14)
    asm.round.turned_bowl(cx, cy, z0, [(radius * 0.9, 0.0), (radius, 0.01), (radius * 1.02, height)], 0.0035, material, seg=sides)
    angle = math.radians(handle_deg)
    ax, ay = math.cos(angle), math.sin(angle)
    reach = radius + 0.03
    points = [(cx + ax * radius, cy + ay * radius, z0 + height * 0.85), (cx + ax * (radius + 0.022), cy + ay * (radius + 0.022), z0 + height * 0.82),
              (cx + ax * reach, cy + ay * reach, z0 + height * 0.5),
              (cx + ax * (radius + 0.02), cy + ay * (radius + 0.02), z0 + height * 0.2),
              (cx + ax * radius, cy + ay * radius, z0 + height * 0.18)]
    asm.round.tube_path(points, 0.0045, material, sides=6, resolution=4)
    if coffee:
        asm.round.cylinder(cx, cy, z0 + height * 0.45, radius * 0.9, 0.002, "water_dark", seg=sides)


def tumbler(asm, cx, cy, z0, radius=0.032, height=0.11, residue=0.0):
    """Copo de vidro; `residue` > 0 deixa um fundo de líquido turvo."""
    sides = segments(14)
    asm.round.turned_bowl(cx, cy, z0, [(radius * 0.85, 0.0), (radius * 0.9, 0.004), (radius, height)], 0.0025,
                          "glass_clear", seg=sides)
    if residue:
        asm.round.cylinder(cx, cy, z0 + 0.004, radius * 0.86, residue, "kg_food_old", seg=sides)


def pot(asm, cx, cy, z0, radius=0.10, height=0.12, lid=False, water=True):
    """Panela de aço com duas alças laterais e, se `water`, a água parada e escura."""
    sides = segments(18)
    asm.round.turned_bowl(cx, cy, z0, [(radius * 0.97, 0.0), (radius, 0.01), (radius, height)], 0.0025, "kg_steel", seg=sides)
    for side in (-1, 1):
        asm.round.tube((cx + side * radius, cy, z0 + height * 0.82), (cx + side * (radius + 0.035), cy, z0 + height * 0.86),
                       0.006, "kg_plastic_dark", seg=6)
    if water:
        asm.round.cylinder(cx, cy, z0 + height * 0.55, radius * 0.97, 0.002, "water_dark", seg=sides)
    if lid:
        asm.round.lathe([(0.0, height + 0.02), (radius * 0.3, height + 0.018), (radius * 1.02, height + 0.002),
                         (radius, height)], cx, cy, z0, "kg_steel", seg=sides, smooth=True, cap_bottom=False, cap_top=False)


def frying_pan(asm, cx, cy, z0, radius=0.12, yaw_deg=0.0):
    """Frigideira de ferro com cabo de madeira; o fundo guarda gordura queimada."""
    sides = segments(18)
    with asm.round.at(cx, cy, z0, rz=yaw_deg):
        asm.round.turned_bowl(0, 0, 0, [(radius * 0.88, 0.0), (radius * 0.95, 0.008), (radius, 0.04)], 0.003, "kg_castiron", seg=sides)
        asm.round.cylinder(0, 0, 0.0035, radius * 0.85, 0.002, "kg_food_old", seg=sides)
        asm.round.tube((radius * 0.95, 0, 0.034), (radius + 0.20, 0, 0.044), 0.009, "kg_pine", seg=8, r_end=0.0075)


def kettle(asm, cx, cy, z0, yaw_deg=0.0):
    """Chaleira de aço de bico curvo, tampa e alça preta."""
    sides = segments(18)
    with asm.round.at(cx, cy, z0, rz=yaw_deg):
        asm.round.lathe([(0.0, 0.0), (0.085, 0.0), (0.098, 0.03), (0.095, 0.12), (0.062, 0.17), (0.04, 0.185), (0.0, 0.19)],
                        0, 0, 0, "kg_steel", seg=sides, smooth=True, cap_bottom=True, cap_top=False)
        asm.round.sphere(0, 0, 0.198, 0.017, "kg_plastic_dark", seg=8, rings=4)
        asm.round.tube_path([(0.085, 0, 0.06), (0.14, 0, 0.11), (0.18, 0, 0.15), (0.19, 0, 0.165)], 0.012, "kg_steel",
                            sides=8, resolution=4, taper=lambda t: 1.0 - 0.5 * t)
        asm.round.tube_path([(-0.075, 0, 0.17), (-0.13, 0, 0.19), (-0.14, 0, 0.12), (-0.098, 0, 0.04)], 0.009,
                            "kg_plastic_dark", sides=6, resolution=5)


def _flat_outline(asm, outline, x, y, z, yaw_deg, material, thickness=0.0018, tilt=(0.0, 0.0)):
    """Contorno 2D extrudado em `thickness` e deitado em (x, y, z), girado em yaw."""
    with asm.crisp.at(x, y, z, rx=tilt[0], ry=tilt[1], rz=yaw_deg):
        asm.crisp.extrude(outline, "xy", 0.0, thickness, material)


def cutlery(asm, kind, x, y, z, yaw_deg=0.0, tilt=(0.0, 0.0)):
    """Garfo, faca ou colher de aço deitados (a ponta do cabo em (x, y)). `kind`: fork | knife | spoon."""
    if kind == "spoon":
        _flat_outline(asm, SPOON_HANDLE, x, y, z, yaw_deg, "kg_steel", tilt=tilt)
        with asm.round.at(x, y, z, rz=yaw_deg):
            asm.round.sphere(0.0, 0.118, 0.001, 0.021, "kg_steel", seg=8, rings=4, squash=0.35)
        return
    _flat_outline(asm, FORK if kind == "fork" else KNIFE, x, y, z, yaw_deg, "kg_steel", tilt=tilt)


def sponge(asm, cx, cy, z0, yaw_deg=0.0):
    """Esponja de louça amarela com a face abrasiva verde, encharcada e torta."""
    with asm.soft.at(cx, cy, z0, rz=yaw_deg):
        asm.soft.soft_box(0, 0, 0.012, 0.09, 0.06, 0.016, "kg_sponge_yellow", radius=0.01, edge=0.005)
        asm.soft.soft_box(0, 0, 0.0, 0.09, 0.06, 0.012, "kg_sponge_green", radius=0.01, edge=0.004)


def detergent_bottle(asm, cx, cy, z0, yaw_deg=0.0, level=0.5):
    """Frasco de detergente verde-claro com bico e rótulo; o líquido é um cilindro mais claro dentro."""
    sides = segments(14)
    with asm.round.at(cx, cy, z0, rz=yaw_deg):
        asm.round.lathe([(0.0, 0.0), (0.03, 0.0), (0.034, 0.02), (0.034, 0.17), (0.026, 0.205), (0.012, 0.215), (0.0, 0.215)],
                        0, 0, 0, "kg_detergent", seg=sides, smooth=True, cap_bottom=False, cap_top=False)
        asm.round.cylinder(0, 0, 0.215, 0.011, 0.02, "kg_plastic_white", seg=8, r_top=0.008)
        asm.round.wrap([(0.0345, 0.05), (0.0345, 0.15)], 0, 0, 0, "kg_label_soap", seg=sides)
        asm.round.tube((0, 0, 0.233), (0.025, 0, 0.243), 0.005, "kg_plastic_white", seg=6)


def kids_cup(asm, cx, cy, z0):
    """Copinho rosa da Emma com tampa, bico e canudo dobrado: lavado e esquecido no escorredor."""
    sides = segments(14)
    asm.round.lathe([(0.0, 0.0), (0.028, 0.0), (0.034, 0.01), (0.038, 0.09), (0.036, 0.1), (0.0, 0.1)], cx, cy, z0, "painted_pink",
                    seg=sides, smooth=True, cap_bottom=False, cap_top=False)
    asm.round.cylinder(cx, cy, z0 + 0.1, 0.037, 0.012, "kg_plastic_white", seg=sides)
    asm.round.tube_path([(cx + 0.008, cy, z0 + 0.1), (cx + 0.008, cy, z0 + 0.16), (cx + 0.03, cy, z0 + 0.175)], 0.004, "toy_blue",
                        sides=6, resolution=4)
