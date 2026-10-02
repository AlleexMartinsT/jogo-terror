"""Cadeiras: de jantar (encosto de balaústres e travessa entalhada), giratória de couro e a infantil.

Todas desenham numa `Composite` com as partes `wood` (marcenaria), `soft` (estofado) e `metal`. A frente
é +Y e a origem fica no centro da base, como no resto dos móveis.
"""
import math

from .. import craft
from . import furniture_forms as forms
from .composite import Composite


# nomes de tecido usados pelos chamadores (rooms_*) -> material estofado desta fase
SEAT_COVERS = {"fabric_red": "velvet_burgundy", "plush_pink": "velvet_pink", "fabric_gray": "armchair_fabric",
               "leather_brown": "leather_aged", "fabric_blue": "sofa_fabric"}


def new_chair(name):
    return Composite(name, wood=forms.WOOD, round=forms.SMOOTH, soft=forms.PADDING, pillows=craft.RAW, metal=forms.SMOOTH)


# ---------------------------------------------------------------------------
# Cadeira de jantar
# ---------------------------------------------------------------------------
SPLAT = [(-0.030, 0.0), (0.030, 0.0), (0.034, 0.05), (0.052, 0.10), (0.058, 0.16), (0.040, 0.22), (0.020, 0.25),
         (-0.020, 0.25), (-0.040, 0.22), (-0.058, 0.16), (-0.052, 0.10), (-0.034, 0.05)]


def dining_chair(asm, cover, wood="walnut", booster=None):
    """Cadeira de jantar de nogueira: pernas dianteiras torneadas, traseiras em curva, encosto de balaústres e crista."""
    timber, vertical = wood, wood + "_v"
    w = asm.wood
    seat_z = 0.43
    for side in (-1, 1):
        forms.turned_leg(asm.round, side * 0.205, 0.188, 0.0, seat_z, 0.029, vertical, "tapered")
        w.bar((side * 0.205, -0.175, 0.0), (side * 0.205, -0.197, seat_z), 0.034, vertical)
        w.bar((side * 0.205, -0.197, seat_z), (side * 0.192, -0.238, 0.955), 0.030, vertical)
    rail_z = seat_z - 0.065
    w.box(0, 0.188, rail_z, 0.385, 0.03, 0.065, timber)
    w.box(0, -0.195, rail_z, 0.385, 0.03, 0.065, timber)
    for side in (-1, 1):
        w.box(side * 0.205, 0, rail_z, 0.03, 0.39, 0.065, vertical)
    for y in (0.188, -0.187):
        w.bar((-0.205, y, 0.17), (0.205, y, 0.17), 0.016, timber)                     # travessas baixas
    w.bar((-0.205, 0.0, 0.17), (0.205, 0.0, 0.17), 0.016, timber)
    # encosto: travessa baixa, cinco balaústres e a crista entalhada

    def back_y(z):
        """Posição em Y do montante traseiro na altura z (ele se inclina para trás)."""
        return -0.197 - 0.041 * (z - seat_z) / (0.955 - seat_z)

    w.box(0, back_y(0.6), 0.58, 0.38, 0.026, 0.05, timber)
    for x in (-0.12, -0.06, 0.0, 0.06, 0.12):
        forms.turned_leg(asm.round, x, back_y(0.75), 0.625, 0.255, 0.0105, vertical, "spindle", sides=10)
    with w.at(0, back_y(0.9) - 0.011, 0.0, rx=-5):
        w.extrude([(-0.195, 0.865), (0.195, 0.865), (0.195, 0.915), (0.13, 0.925), (0.07, 0.96), (0.0, 0.985),
                   (-0.07, 0.96), (-0.13, 0.925), (-0.195, 0.915)], "xz", 0.0, 0.026, timber)
    # assento estofado
    soft = asm.soft
    soft.soft_box(0, 0.0, seat_z, 0.42, 0.41, 0.05, cover, radius=0.035, edge=0.02)
    if booster:
        soft.soft_box(0, 0.0, seat_z + 0.05, 0.36, 0.34, 0.07, booster, radius=0.04, edge=0.03)


# ---------------------------------------------------------------------------
# Cadeira giratória de escritório
# ---------------------------------------------------------------------------
def office_chair(asm, cover):
    """Giratória de couro: base de cinco pés com rodízios, pistão telescópico, assento e encosto acolchoados e braços."""
    metal, soft = asm.metal, asm.soft
    for index in range(5):
        angle = math.radians(72 * index + 18)
        tip = (0.30 * math.cos(angle), 0.30 * math.sin(angle))
        metal.tube((0, 0, 0.115), (tip[0], tip[1], 0.07), 0.017, "steel_dark", seg=8, r_end=0.012, smooth=True)
        metal.cylinder(tip[0], tip[1], 0.05, 0.011, 0.04, "steel_dark", seg=8, smooth=True)
        with metal.at(tip[0], tip[1], 0.03, rz=math.degrees(angle) + 90):
            metal.box(0, 0, 0.0, 0.034, 0.014, 0.025, "steel_dark")
            for side in (-1, 1):
                with metal.at(side * 0.010, 0, 0.0, ry=90):
                    metal.cylinder(0, 0, 0, 0.026, 0.008, "rubber", seg=forms.seg(14), smooth=True)
    metal.lathe([(0.055, 0.09), (0.060, 0.12), (0.032, 0.14), (0.032, 0.24), (0.026, 0.25), (0.026, 0.37), (0.04, 0.38)],
                0, 0, 0.0, "steel_dark", seg=forms.seg(16), smooth=True)
    metal.box(0, 0.0, 0.375, 0.2, 0.2, 0.014, "steel_dark")
    pillows = asm.pillows
    rows = forms.cushion(pillows, 0, 0.03, 0.39, 0.54, 0.52, 0.10, cover, squareness=3.0, corner=0.3, crown=0.012,
                         wrinkle=0.002)
    forms.piping_at(pillows, rows, 0.82, 0.004, cover)
    metal.bar((0, -0.18, 0.40), (0, -0.25, 0.60), 0.035, "steel_dark")
    with pillows.at(0, -0.255, 0.86, rx=-80):
        rows = forms.cushion(pillows, 0, 0, -0.045, 0.50, 0.56, 0.095, cover, squareness=3.0, corner=0.30, crown=0.015,
                             dimple=0.02, dimple_at=(0.0, 0.18), wrinkle=0.002, phase=1.0)
        forms.piping_at(pillows, rows, 0.82, 0.004, cover)
        forms.button(pillows, 0, 0.18 * 0.56, 0.05, cover)
    for side in (-1, 1):
        metal.bar((side * 0.27, -0.02, 0.43), (side * 0.27, -0.02, 0.63), 0.022, "steel_dark")
        metal.bar((side * 0.27, -0.02, 0.63), (side * 0.27, 0.10, 0.63), 0.022, "steel_dark")
        soft.soft_box(side * 0.27, 0.0, 0.63, 0.07, 0.30, 0.04, cover, radius=0.03, edge=0.016)


# ---------------------------------------------------------------------------
# Cadeirinha infantil (quartos)
# ---------------------------------------------------------------------------
def kid_chair(asm, wood_mat):
    """Cadeirinha de criança pintada: assento de bordas arredondadas, pernas afiladas e um coração aplicado no encosto."""
    forms.slab(asm.round, 0, 0, 0.245, 0.31, 0.29, [(0.0, 0.012), (0.006, 0.003), (0.012, 0.0), (0.024, 0.0), (0.03, 0.006)],
               wood_mat, radius=0.03)
    for side in (-1, 1):
        forms.turned_leg(asm.round, side * 0.125, 0.115, 0.0, 0.25, 0.017, wood_mat, "tapered", sides=10)
        asm.wood.bar((side * 0.125, -0.115, 0.0), (side * 0.125, -0.125, 0.56), 0.026, wood_mat)
    asm.wood.box(0, -0.125, 0.36, 0.25, 0.018, 0.045, wood_mat)
    asm.wood.box(0, -0.125, 0.47, 0.25, 0.018, 0.09, wood_mat)
    heart = [(0.0, -0.032), (0.036, 0.004), (0.04, 0.026), (0.022, 0.042), (0.0, 0.028), (-0.022, 0.042), (-0.04, 0.026),
             (-0.036, 0.004)]
    asm.wood.extrude([(x, z + 0.515) for x, z in heart], "xz", -0.1175, -0.1145, "plush_pink")
