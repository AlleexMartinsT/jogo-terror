"""Telefone fixo bege dos anos 90: carcaça em cunha, teclado, fone sobre o gancho e fio espiral.

O fio do fone é uma hélice seguida por `craft.tube_along`; o que sai do aparelho para a tomada é uma curva
suave. Serve ao hall (aparador) e ao escritório (escrivaninha).
"""
import math

from .. import craft
from . import furniture_forms as forms
from . import materials
from .composite import Composite
from .placement import place

materials.SPECS.update({"phone_plastic": materials.Spec(color=(0.46, 0.41, 0.31), roughness=0.38),
                        "phone_key": materials.Spec(color=(0.58, 0.54, 0.44), roughness=0.4)})


def _helix(start, end, turns, radius, points_per_turn=6, sag=0.04):
    """Pontos de uma espiral de `turns` voltas ao longo da reta start-end, com a barriga caída pelo peso."""
    count = int(turns * points_per_turn)
    result = []
    for i in range(count + 1):
        t = i / count
        axis = [start[k] + (end[k] - start[k]) * t for k in range(3)]
        angle = 2 * math.pi * turns * t
        result.append((axis[0] + radius * math.cos(angle) * 0.4, axis[1] + radius * math.cos(angle),
                       axis[2] + radius * math.sin(angle) - sag * math.sin(math.pi * t)))
    return result


def build_phone(asm, *, handset_on_cradle=True):
    """Desenha o telefone na Composite: base em cunha, teclado 3x4, ganchos, fone e fios."""
    body, trim = asm.body, asm.trim
    profile = [(-0.115, 0.0), (0.115, 0.0), (0.105, 0.045), (0.02, 0.092), (-0.115, 0.092)]       # (y, z) lateral
    body.extrude(profile, "yz", -0.105, 0.105, "phone_plastic")
    slope = math.degrees(math.atan2(0.092 - 0.045, 0.105 - 0.02))
    with trim.at(0, 0.0625, 0.0685, rx=-slope):                                  # teclado na face inclinada
        for row in range(4):
            for col in range(3):
                trim.box((col - 1) * 0.026, (1.5 - row) * 0.022, 0.0, 0.018, 0.016, 0.006, "phone_key")
    for side in (-1, 1):
        trim.box(side * 0.045, -0.085, 0.092, 0.012, 0.03, 0.022, "phone_plastic")             # ganchos do fone
    trim.box(0, 0.115, 0.012, 0.18, 0.004, 0.015, "tv_black")
    cord = craft.tube_along([(0.06, 0.115, 0.012), (0.13, 0.2, 0.004), (0.30, 0.22, 0.0), (0.55, 0.12, 0.0)], 0.0022,
                            segments=6, resolution=3, name="cabo_fone")
    cord.materials.append(materials.get("phone_plastic"))
    asm.add_mesh(cord)
    # fone: duas conchas e a haste curva, deitado nos ganchos
    handset_z = 0.116
    for side in (-1, 1):
        body.soft_box(side * 0.085, -0.08, handset_z, 0.062, 0.05, 0.036, "phone_plastic", radius=0.015, edge=0.008)
    body.soft_box(0, -0.08, handset_z + 0.006, 0.12, 0.028, 0.026, "phone_plastic", radius=0.012, edge=0.006)
    for side in (-1, 1):
        for hole in range(5):
            trim.box(side * 0.085 + (hole - 2) * 0.008, -0.08, handset_z + 0.0362, 0.004, 0.004, 0.0008, "tv_black")
    coil = craft.tube_along(_helix((0.0, -0.095, handset_z + 0.004), (0.02, 0.115, 0.04), 16, 0.012), 0.0013, segments=6,
                            resolution=2, name="espiral")
    coil.materials.append(materials.get("phone_plastic"))
    asm.add_mesh(coil)


def make_telephone(ctx, room, x, y, z, yaw):
    """Telefone fixo bege sobre um móvel (objeto de enfeite); a frente do aparelho é +Y."""
    asm = Composite("telephone", body=forms.SMOOTH, trim=craft.RAW)
    build_phone(asm)
    return place(ctx, asm, room, "telephone", x, y, yaw, z, mode="decor")
