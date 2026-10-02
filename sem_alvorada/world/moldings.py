"""Molduras da casa: guarnições (casings), rodapés, sancas e peitoris, todos varridos de um perfil.

Cada perfil é uma lista fechada de pontos (u, v): `u` corre para longe da borda de onde a moldura parte
(para a guarnição, a partir da borda do vão; para o rodapé, a altura) e `v` sai da superfície da parede.
Os perfis são grosseiros de propósito: poucos pontos bem escolhidos já pegam a luz rasante da lanterna.
"""
import math

from mathutils import Vector

from .wallgeom import along, normal, wall_point

CASING_WIDTH = 0.080
CASING_PROFILE = [
    (0.000, 0.000), (0.000, 0.0235), (0.004, 0.0275), (0.012, 0.0285), (0.021, 0.0270), (0.029, 0.0235),
    (0.036, 0.0225), (0.046, 0.0240), (0.057, 0.0260), (0.067, 0.0255), (0.074, 0.0225), (0.080, 0.0140),
    (0.080, 0.000),
]
BASEBOARD_HEIGHT = 0.125
BASEBOARD_PROFILE = [
    (0.000, 0.000), (0.000, 0.0170), (0.012, 0.0185), (0.088, 0.0185), (0.094, 0.0205), (0.102, 0.0235),
    (0.110, 0.0245), (0.117, 0.0225), (0.125, 0.0150), (0.125, 0.000),
]
CROWN_REACH = 0.075


def crown_profile(reach=CROWN_REACH, steps=6):
    """Sanca côncava: um quarto de círculo centrado na quina entre parede e forro."""
    arc = [(reach - reach * math.cos(math.pi / 2 * i / steps), reach * math.sin(math.pi / 2 * i / steps))
           for i in range(steps + 1)]
    return arc + [(reach, 0.0)]


STOOL_PROFILE = [(0.0, 0.0), (0.0, 0.026), (0.020, 0.028), (0.030, 0.0275), (0.034, 0.0245), (0.036, 0.020),
                 (0.036, 0.0)]


def casing(builder, op, wall_half, z_bottom, z_top, material, sides=(-1, 1), width=CASING_WIDTH):
    """Guarnição de três lados (duas jambas e a verga) com quinas em meia-esquadria, nas faces escolhidas.

    `z_bottom`..`z_top` é a altura livre do vão; a verga assenta sobre `z_top`. O perfil sai da superfície
    da parede (`wall_half` é metade da espessura) e cresce para fora dela.
    """
    scale = width / CASING_WIDTH
    profile = [(u * scale, v) for u, v in CASING_PROFILE]
    a, b = op.a, op.b
    for side in sides:
        n = op.pos + side * wall_half
        corners = [wall_point(op, a, n, z_bottom), wall_point(op, a, n, z_top),
                   wall_point(op, b, n, z_top), wall_point(op, b, n, z_bottom)]
        directions = [-along(op), Vector((0.0, 0.0, 1.0)), along(op)]
        builder.sweep(profile, corners, directions, normal(op) * side, material)


def baseboard_run(builder, start, end, outward, material):
    """Rodapé reto entre dois pontos do piso. `outward` é a normal da parede, voltada para o cômodo."""
    builder.prism(BASEBOARD_PROFILE, start, end, (0.0, 0.0, 1.0), outward, material)


def crown_run(builder, start, end, outward, material, reach=CROWN_REACH):
    """Sanca reta; `start`/`end` na altura em que a moldura encosta na parede (forro menos `reach`)."""
    builder.prism(crown_profile(reach), start, end, (0.0, 0.0, 1.0), outward, material)
