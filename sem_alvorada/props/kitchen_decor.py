"""Enfeites presos em portas e paredes: folhas de papel, ímãs, relógio e calendário.

Tudo acumula numa `Assembly` e olha para +Y; o chamador escolhe o plano (`y`) da superfície. Folhas e ímãs
usam a malha sem chanfro (`round`): uma lâmina de 1,4 mm não aguenta um chanfro de 3 mm.
"""
import math

from .kg_shapes import segments

SHEET_THICKNESS = 0.0014


def paper_sheet(asm, cx, cz, y, width, height, material, tilt_deg=0.0):
    """Folha presa na superfície: verso claro, face com a arte, levemente girada."""
    with asm.round.at(cx, y, cz, ry=tilt_deg):
        asm.round.box(0, SHEET_THICKNESS / 2, -height / 2, width, SHEET_THICKNESS, height, "paper_white")
        asm.round.panel(0, SHEET_THICKNESS + 0.0002, 0, width, height, material, "front")


def round_magnet(asm, cx, cz, y, color, radius=0.013):
    """Ímã redondo de cor, com uma cúpula baixa."""
    with asm.round.at(cx, y, cz, rx=-90):
        asm.round.cylinder(0, 0, 0, radius, 0.006, color, seg=segments(10), r_top=radius * 0.85)


def letter_magnet(asm, cx, cz, y, letter_material, body_color, tilt_deg=0.0):
    """Ímã de letra: um pastilha colorida com a letra pintada na frente."""
    with asm.round.at(cx, y, cz, ry=tilt_deg):
        asm.round.box(0, 0.004, -0.019, 0.034, 0.008, 0.038, body_color)
        asm.round.panel(0, 0.0082, 0, 0.03, 0.034, letter_material, "front")


def wall_clock(asm, cx, cz, y, radius=0.15, hour_deg=186.0, minute_deg=72.0):
    """Relógio de parede redondo parado em 6:12: aro, mostrador, vidro e dois ponteiros (ângulos horários)."""
    sides = segments(28)
    with asm.round.at(cx, y, cz, rx=-90):
        asm.round.cylinder(0, 0, 0, radius, 0.035, "kg_plastic_dark", seg=sides, r_top=radius * 0.97)
    asm.round.dial(cx, y + 0.0352, cz, radius * 0.9, "kg_clock_face", sides)
    asm.round.dial(cx, y + 0.0385, cz, radius * 0.9, "glass_clear", sides)
    for angle, length, width, lift in ((hour_deg, radius * 0.5, 0.009, 0.0405), (minute_deg, radius * 0.75, 0.006, 0.043)):
        rad = math.radians(angle)
        tip = (cx - length * math.sin(rad), y + lift, cz + length * math.cos(rad))   # a direita de quem olha é -X
        asm.round.tube((cx, y + lift, cz), tip, width / 2, "kg_plastic_dark", seg=4)
    asm.round.cylinder(cx, y + 0.0405, cz, 0.009, 0.004, "kg_plastic_dark", seg=8)
