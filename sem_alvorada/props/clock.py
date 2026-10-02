"""Relógio de pé de nogueira, 1,98 m, parado às 6:12, com o pêndulo imóvel e os pesos atrás do vidro.

Medidas de um relógio de salão americano: base de 0,46 m, corpo de 0,37 m, capelo de 0,47 m. Tem
`depth` de 0,36 m, o mesmo da peça anterior, para encostar na parede sem invadir a passagem.
"""
import math

from .. import craft
from . import furniture_forms as forms
from . import materials
from .composite import Composite
from .placement import flush_center, place

DEPTH = 0.36
HOUR_ANGLE = (6 + 12 / 60) * 30           # graus no sentido horário a partir das 12
MINUTE_ANGLE = 12 * 6
DIAL_CENTER_Z = 1.55

materials.SPECS.update({"case_inside": materials.Spec(color=(0.035, 0.024, 0.016), roughness=0.9),
                        "blued_steel": materials.Spec(color=(0.03, 0.04, 0.07), roughness=0.35, metallic=0.9)})

FINIAL_PROFILE = [(0.012, 0.0), (0.016, 0.010), (0.010, 0.020), (0.021, 0.040), (0.023, 0.055), (0.013, 0.070),
                  (0.007, 0.080), (0.012, 0.086), (0.0, 0.097)]


def _plinth(wood, round_part):
    forms.slab(round_part, 0, 0, 0, 0.50, DEPTH, [(0, 0.014), (0.008, 0.0), (0.070, 0.0), (0.082, 0.012)], "walnut", radius=0.012)
    wood.box(0, 0, 0.082, 0.43, 0.30, 0.22, "walnut_v")
    with wood.at(0, 0.15, 0.19, rx=-90):
        wood.frustum(0, 0, 0, 0.30, 0.16, 0.25, 0.115, 0.013, "walnut")
    forms.slab(round_part, 0, 0, 0.302, 0.47, 0.33, [(0, 0.0), (0.012, 0.0), (0.018, 0.012), (0.030, 0.045)], "walnut",
               radius=0.01)


def _trunk(wood, round_part, trim, glass):
    """Corpo: laterais, fundo escuro, moldura da porta e vidro; quatro quartos de coluna nos cantos."""
    z0, z1 = 0.335, 1.31
    height = z1 - z0
    for side in (-1, 1):
        wood.box(side * 0.1775, 0, z0, 0.015, 0.30, height, "walnut_v")
    wood.box(0, -0.145, z0, 0.34, 0.012, height, "case_inside")
    for side in (-1, 1):
        wood.box(side * 0.145, 0.138, z0, 0.05, 0.022, height, "walnut_v")
    wood.box(0, 0.138, z0, 0.24, 0.022, 0.165, "walnut")                           # travessa de baixo
    wood.box(0, 0.138, 1.175, 0.24, 0.022, z1 - 1.175, "walnut")                  # travessa de cima
    glass.panel(0, 0.131, 0.835, 0.24, 0.675, "glass_clear", "front")
    for side in (-1, 1):                                                           # frisos de latão da porta
        trim.box(side * 0.121, 0.151, 0.50, 0.004, 0.003, 0.675, "brass_aged")
    trim.box(0, 0.151, 0.50, 0.24, 0.003, 0.004, "brass_aged")
    trim.box(0, 0.151, 1.171, 0.24, 0.003, 0.004, "brass_aged")
    forms.escutcheon(trim, 0.108, 0.151, 0.84, "brass_aged")
    for side in (-1, 1):
        forms.turned_leg(round_part, side * 0.178, 0.142, z0 + 0.04, height - 0.08, 0.016, "walnut_v", "spindle")


def _hood(wood, round_part, trim, glass, hands):
    """Capelo com o mostrador atrás do vidro, colunas, cornija, frontão e três vasos de latão."""
    forms.slab(round_part, 0, 0, 1.31, 0.47, 0.34, [(0, 0.045), (0.012, 0.030), (0.022, 0.012), (0.034, 0.0)], "walnut",
               radius=0.01)
    z0, z1 = 1.344, 1.745
    for side in (-1, 1):
        wood.box(side * 0.2175, 0, z0, 0.015, 0.30, z1 - z0, "walnut_v")
    wood.box(0, -0.145, z0, 0.42, 0.012, z1 - z0, "case_inside")
    wood.box(0, 0, z0, 0.42, 0.30, 0.012, "walnut")
    wood.box(0, 0, z1 - 0.012, 0.42, 0.30, 0.012, "walnut")
    for side in (-1, 1):
        wood.box(side * 0.1925, 0.138, z0, 0.04, 0.022, z1 - z0, "walnut_v")
    wood.box(0, 0.138, z0, 0.345, 0.022, 0.036, "walnut")
    wood.box(0, 0.138, 1.724, 0.345, 0.022, z1 - 1.724, "walnut")
    glass.panel(0, 0.129, DIAL_CENTER_Z, 0.345, 0.345, "glass_clear", "front")
    trim.panel(0, 0.10, DIAL_CENTER_Z, 0.345, 0.345, "clock_dial", "front")
    _hands(hands, trim)
    for side in (-1, 1):
        forms.turned_leg(round_part, side * 0.2, 0.145, z0 + 0.01, z1 - z0 - 0.02, 0.019, "walnut_v", "baluster")
        trim.cylinder(side * 0.2, 0.145, z1 - 0.022, 0.022, 0.012, "brass_aged", seg=forms.seg(14), smooth=True)
    forms.slab(round_part, 0, 0, z1, 0.46, 0.32, [(0, 0.0), (0.010, 0.0), (0.016, -0.006), (0.026, -0.011), (0.034, -0.013),
                                           (0.039, -0.012)], "walnut", radius=0.008)
    top = z1 + 0.039
    profile = [(-0.236, top), (0.236, top), (0.236, top + 0.02), (0.20, top + 0.055), (0.13, top + 0.08),
               (0.06, top + 0.094), (0.0, top + 0.098), (-0.06, top + 0.094), (-0.13, top + 0.08), (-0.20, top + 0.055),
               (-0.236, top + 0.02)]
    round_part.extrude(profile, "xz", -0.12, 0.13, "walnut")
    with trim.at(0, 0.131, top + 0.052, rx=-90):
        trim.lathe([(0.0, 0.0), (0.034, 0.0), (0.036, 0.003), (0.03, 0.007), (0.012, 0.010), (0.0, 0.010)], 0, 0, 0,
                   "brass_aged", seg=forms.seg(18), smooth=True)
    for x, base, scale in ((0.0, top + 0.098, 1.0), (-0.2, top, 0.62), (0.2, top, 0.62)):
        profile_scaled = [(r * scale, h * scale) for r, h in FINIAL_PROFILE]
        trim.lathe(profile_scaled, x, -0.005, base, "brass_aged", seg=forms.seg(14), smooth=True)


def _hands(hands, trim):
    """Ponteiros de aço azulado parados às 6:12, no plano do mostrador (frente = +Y)."""
    spade = [(-0.0035, -0.02), (0.0035, -0.02), (0.0045, 0.03), (0.014, 0.055), (0.0, 0.098), (-0.014, 0.055), (-0.0045, 0.03)]
    needle = [(-0.0028, -0.025), (0.0028, -0.025), (0.0020, 0.09), (0.0, 0.140), (-0.0020, 0.09)]
    with hands.at(0, 0.102, DIAL_CENTER_Z, ry=-HOUR_ANGLE):
        hands.extrude(spade, "xz", 0.0, 0.0022, "blued_steel")
    with hands.at(0, 0.1045, DIAL_CENTER_Z, ry=-MINUTE_ANGLE):
        hands.extrude(needle, "xz", 0.0, 0.0022, "blued_steel")
    with trim.at(0, 0.1045, DIAL_CENTER_Z, rx=-90):
        trim.cylinder(0, 0, 0, 0.008, 0.007, "brass_aged", seg=forms.seg(12), smooth=True)


def _pendulum_and_weights(trim, wood):
    """Pêndulo parado a 7 graus do prumo e dois pesos de latão pendurados em correntes finas."""
    pivot = (0.0, 0.0, 1.16)
    angle = math.radians(7)
    bob = (pivot[0] + 0.54 * math.sin(angle), 0.0, pivot[2] - 0.54 * math.cos(angle))
    trim.tube(pivot, bob, 0.0030, "brass_aged", seg=8, smooth=True)
    with trim.at(*bob, rx=-90):
        trim.lathe([(0.0, 0.0), (0.050, 0.0), (0.058, 0.004), (0.060, 0.009), (0.054, 0.014), (0.0, 0.0155)],
                   0, 0, -0.0075, "brass_aged", seg=forms.seg(20), smooth=True)
        trim.torus(0, 0, 0.008, 0.035, 0.0025, "brass_aged", seg=forms.seg(18), seg_minor=5)
    for x, bottom, link_top in ((-0.075, 0.54, 1.16), (0.075, 0.63, 1.16)):
        trim.lathe([(0.0, 0.0), (0.030, 0.0), (0.034, 0.012), (0.034, 0.17), (0.030, 0.182), (0.0, 0.182)], x, -0.03, bottom,
                   "brass_aged", seg=forms.seg(16), smooth=True)
        trim.sphere(x, -0.03, bottom + 0.19, 0.008, "brass_aged", seg=8, rings=5)
        links = 22
        for i in range(links):
            z_a = bottom + 0.19 + (link_top - bottom - 0.19) * i / links
            z_b = bottom + 0.19 + (link_top - bottom - 0.19) * (i + 1) / links
            trim.tube((x + 0.0012 * (-1) ** i, -0.03, z_a), (x - 0.0012 * (-1) ** i, -0.03, z_b), 0.0014, "brass_aged",
                      seg=4)
    wood.box(0, -0.10, 0.52, 0.33, 0.02, 0.012, "case_inside")


def make_grandfather_clock(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Relógio de pé encostado na parede, parado às 6:12."""
    cy = flush_center(room, x, y, yaw, DEPTH)
    asm = Composite("grandfather_clock", wood=forms.WOOD, round=forms.SMOOTH, trim=forms.SMOOTH, glass=craft.RAW,
                    hands=craft.RAW)
    with asm.at(0, cy, 0):
        _plinth(asm.wood, asm.round)
        _trunk(asm.wood, asm.round, asm.trim, asm.glass)
        _hood(asm.wood, asm.round, asm.trim, asm.glass, asm.hands)
        _pendulum_and_weights(asm.trim, asm.wood)
    return place(ctx, asm, room, "grandfather_clock", x, y, yaw, z, name="grandfather_clock", anchor=anchor)
