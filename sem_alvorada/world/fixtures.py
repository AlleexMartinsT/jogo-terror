"""Luminárias de teto: plafon de vidro leitoso, luminária de corredor, calha fluorescente (com gaiola na
garagem) e um lustre de cinco braços na sala de jantar.

Cada luminária vira DOIS objetos, porque o engine esconde todo `Fixture_*` quando falta energia:

* `Fixture_<sala>_c<n>`: só o que brilha (vidro leitoso, tubos, lâmpadas), com `sa_glow` lido pelo material;
* `FixtureBase_<sala>_c<n>`: ferragem e o vidro apagado, sempre visíveis. O vidro apagado fica 1,5 mm por baixo
  do que brilha, então na queda de energia sobra a peça escura no teto em vez de um buraco.
"""
import math

from .. import conventions as C
from .modelkit import PROFILED, ModelBuilder, detail

SHELL_LIFT = 1.012            # o vidro que brilha é 1,2% maior que o apagado

# Perfis de baixo para cima: assim as normais do torneado saem para fora.
DOME_PROFILE = [(0.0, -0.111), (0.060, -0.109), (0.116, -0.099), (0.151, -0.081), (0.169, -0.056), (0.173, -0.030),
                (0.166, -0.014)]
BASE_PLATE = [(0.0, -0.013), (0.168, -0.013), (0.192, -0.011), (0.197, -0.004), (0.195, 0.0), (0.0, 0.0)]


def build(ctx, room_id, index, x, y, ceiling_z, kind):
    """Cria o par de objetos da luminária e devolve o `Fixture_` (o que brilha)."""
    name = f"{room_id}_c{index}"
    glow, base = ModelBuilder(f"Fixture_{name}", PROFILED), ModelBuilder(f"FixtureBase_{name}", PROFILED)
    sides = detail(ctx, 14)
    if kind == "fluorescent":
        _strip(glow, base, x, y, ceiling_z, cage=room_id == "garage")
    elif room_id == "dining":
        _chandelier(glow, base, x, y, ceiling_z, sides)
    elif room_id.startswith("hall"):
        _hall_light(glow, base, x, y, ceiling_z)
    else:
        _dome(glow, base, x, y, ceiling_z, sides)
    origin = (x, y, ceiling_z)
    base.build(ctx, C.COL_WORLD, origin=origin)
    fixture = glow.build(ctx, C.COL_WORLD, origin=origin)
    fixture["sa_glow"] = 1.0
    fixture[C.P_ROOM] = room_id
    return fixture


# --------------------------------------------------------------------------
# Plafon redondo de vidro leitoso
# --------------------------------------------------------------------------
def _dome(glow, base, x, y, z, sides):
    with base.at(x, y, z):
        base.lathe(BASE_PLATE, "fixture_metal", sides)
        base.lathe(DOME_PROFILE, "milk_glass_dead", sides, caps=(False, False))
        base.lathe([(0.0, -0.123), (0.012, -0.122), (0.016, -0.114), (0.012, -0.108), (0.0, -0.108)], "brass_worn", 8)
        for k in range(3):
            angle = math.tau * (k + 0.25) / 3
            with base.at(0.186 * math.cos(angle), 0.186 * math.sin(angle), -0.012):
                base.lathe([(0.0, -0.005), (0.006, -0.004), (0.0075, 0.0), (0.0, 0.0)], "brass_worn", 8)
    with glow.at(x, y, z):
        glow.lathe([(r * SHELL_LIFT, h * SHELL_LIFT) for r, h in DOME_PROFILE], "fixture_milk_glass", sides,
                   caps=(False, False))


# --------------------------------------------------------------------------
# Luminária de corredor: moldura retangular com difusor
# --------------------------------------------------------------------------
def _hall_light(glow, base, x, y, z):
    half_x, half_y = 0.11, 0.27
    base.box(x - 0.125, y - 0.285, z - 0.026, x + 0.125, y + 0.285, z, "fixture_metal", skip=("+z",))
    base.box(x - half_x, y - half_y, z - 0.058, x + half_x, y + half_y, z - 0.026, "milk_glass_dead", skip=("+z",))
    for sx in (-1, 1):
        for sy in (-1, 1):
            with base.at(x + sx * 0.108, y + sy * 0.262, z - 0.026):
                base.lathe([(0.0, -0.006), (0.0075, -0.005), (0.009, 0.0), (0.0, 0.0)], "brass_worn", 8)
    lift = 0.0015
    glow.box(x - half_x - lift, y - half_y - lift, z - 0.058 - lift, x + half_x + lift, y + half_y + lift, z - 0.026,
             "fixture_milk_glass", skip=("+z",))


# --------------------------------------------------------------------------
# Calha fluorescente
# --------------------------------------------------------------------------
def _strip(glow, base, x, y, z, cage):
    """Calha de 1,2 m com dois tubos. Na garagem pende por correntes e leva uma gaiola de arame."""
    drop = 0.12 if cage else 0.0
    top = z - drop
    base.box(x - 0.62, y - 0.13, top - 0.065, x + 0.62, y + 0.13, top - 0.03, "fixture_metal")
    base.box(x - 0.62, y - 0.13, top - 0.065, x + 0.62, y - 0.118, top - 0.012, "fixture_metal")
    base.box(x - 0.62, y + 0.118, top - 0.065, x + 0.62, y + 0.13, top - 0.012, "fixture_metal")
    for dy in (-0.045, 0.045):
        glow.tube((x - 0.585, y + dy, top - 0.078), (x + 0.585, y + dy, top - 0.078), 0.0125, "fixture_tube", 8)
        base.tube((x - 0.6, y + dy, top - 0.078), (x - 0.585, y + dy, top - 0.078), 0.012, "iron_black", 8)
        base.tube((x + 0.585, y + dy, top - 0.078), (x + 0.6, y + dy, top - 0.078), 0.012, "iron_black", 8)
    if cage:
        for sx in (-0.5, 0.5):
            for sy in (-0.1, 0.1):
                base.tube((x + sx, y + sy, z), (x + sx, y + sy, top - 0.03), 0.0025, "iron_black", 5)
        _cage(base, x, y, top - 0.062)


def _cage(base, x, y, z):
    """Gaiola de proteção: duas longarinas, sete aros transversais, tudo de arame fino."""
    for dy in (-0.115, 0.115):
        base.tube((x - 0.64, y + dy, z), (x + 0.64, y + dy, z), 0.0028, "iron_black", 5)
    for k in range(8):
        px = x - 0.6 + 1.2 * k / 7
        base.tube((px, y - 0.115, z), (px, y, z - 0.055), 0.0028, "iron_black", 5)
        base.tube((px, y, z - 0.055), (px, y + 0.115, z), 0.0028, "iron_black", 5)
    base.tube((x - 0.6, y, z - 0.055), (x + 0.6, y, z - 0.055), 0.0028, "iron_black", 5)


# --------------------------------------------------------------------------
# Lustre de cinco braços (sala de jantar)
# --------------------------------------------------------------------------
def _chandelier(glow, base, x, y, z, sides):
    """Lustre simples de latão: canopla, corrente, coluna torneada e cinco braços com velas elétricas."""
    with base.at(x, y, z):
        base.lathe([(0.0, 0.0), (0.075, 0.0), (0.072, -0.012), (0.045, -0.026), (0.02, -0.034), (0.0, -0.034)],
                   "brass_worn", sides, caps=(False, False))
    for k in range(6):
        link_z = z - 0.05 - k * 0.048
        with base.at(x, y, link_z, rx=90 if k % 2 else 0, ry=0 if k % 2 else 90):
            base.torus(0.012, 0.0028, "brass_worn", 10, 5)
    column_top = z - 0.34
    with base.at(x, y, column_top):
        base.lathe([(0.0, 0.0), (0.012, 0.0), (0.020, -0.03), (0.038, -0.07), (0.044, -0.11), (0.030, -0.15),
                    (0.016, -0.18), (0.020, -0.215), (0.0, -0.235)], "brass_worn", sides, caps=(False, False))
    arm_z = column_top - 0.10
    for k in range(5):
        angle = math.tau * k / 5
        _arm(glow, base, x, y, arm_z, angle, sides)


def _arm(glow, base, x, y, z, angle, sides):
    """Um braço em S: sai da coluna, abre e sobe até o copo da vela."""
    ca, sa = math.cos(angle), math.sin(angle)
    path = [(0.03, 0.0), (0.11, -0.03), (0.19, -0.01), (0.235, 0.07)]
    points = [(x + r * ca, y + r * sa, z + h) for r, h in path]
    for a, b in zip(points, points[1:]):
        base.tube(a, b, 0.0075, "brass_worn", max(5, sides // 2))
    end = points[-1]
    with base.at(*end):
        base.lathe([(0.0, 0.0), (0.024, 0.0), (0.026, 0.012), (0.018, 0.02), (0.012, 0.028), (0.012, 0.062)],
                   "brass_worn", max(6, sides // 2), caps=(False, False))
    with glow.at(*end):
        glow.lathe([(0.0, 0.058), (0.010, 0.066), (0.012, 0.085), (0.0075, 0.108), (0.0, 0.124)], "fixture_glow",
                   max(6, sides // 2), caps=(False, False))
