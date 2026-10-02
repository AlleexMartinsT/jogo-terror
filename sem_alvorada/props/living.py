"""Sala de estar: sofá com a manta, poltrona, mesa de centro e abajur de chão.

A TV com o console fica em `tv.py` e o relógio de pé em `clock.py`. Os estofados são montados com um
`Composite` (madeira firme + estofado macio): ver `composite.py` e `furniture_forms.py`.
"""
import math

from .. import craft
from . import cloth_sala as cloth
from . import furniture_forms as shapes
from . import materials, parts, small_things as things, tex_den  # noqa: F401  (registra as capas de revista)
from .composite import Composite
from .placement import place

LIFT = 0.12                    # altura dos pés do estofado


def new_upholstered(name):
    """Composite de estofado: madeira, torneados, base acolchoada (subdividida) e almofadas/vivos (malha direta)."""
    return Composite(name, wood=shapes.WOOD, round=shapes.SMOOTH, soft=shapes.PADDING, pillows=craft.RAW)


def _upholstered_seat(asm, width, depth, fabric, seats, *, arm_half=0.085):
    """Estofado com `seats` lugares: pés torneados, base, braços enrolados, encosto e almofadas soltas.

    Medidas de sofá de três lugares americano: assento a 0,46 m, braço a 0,64 m, encosto a 0,9 m,
    profundidade 0,9 m. As almofadas dividem igualmente o vão entre os braços.
    """
    wood, soft, pillows = asm.wood, asm.soft, asm.pillows
    roll_radius = arm_half / math.cos(math.radians(35))
    arm_x = width / 2 - roll_radius
    span = 2 * (arm_x - arm_half)
    # base de madeira: pés torneados e travessas aparentes sob o estofado
    for sx in (-1, 1):
        for sy in (-1, 1):
            shapes.turned_leg(asm.round, sx * (width / 2 - 0.085), sy * (depth / 2 - 0.085), 0.0, LIFT + 0.02, 0.036,
                              "walnut_v", "baluster")
    wood.box(0, depth / 2 - 0.085, 0.04, width - 0.2, 0.035, 0.08, "walnut")
    wood.box(0, -depth / 2 + 0.085, 0.04, width - 0.2, 0.035, 0.08, "walnut")
    for sx in (-1, 1):
        wood.box(sx * (width / 2 - 0.085), 0, 0.04, 0.035, depth - 0.2, 0.08, "walnut")
    # corpo estofado: assento corrido, encosto fixo e braços
    soft.soft_box(0, 0, LIFT, width, depth, 0.17, fabric, radius=0.06, edge=0.025)
    soft.soft_box(0, -depth / 2 + 0.105, LIFT + 0.05, span + 0.05, 0.21, 0.52, fabric, radius=0.07, edge=0.04)
    for sx in (-1, 1):
        shapes.rolled_arm(soft, sx * arm_x, -depth / 2 + 0.01, depth / 2 - 0.015, LIFT, arm_half, 0.545, fabric)
        shapes.scroll_face(soft, sx * arm_x, depth / 2 - 0.015, 0.545, roll_radius * 0.97, fabric)
    for z_edge in (LIFT + 0.168, LIFT + 0.012):                       # vivos da base, em cima e embaixo
        pillows.tube((-span / 2 - 0.02, depth / 2 - 0.004, z_edge), (span / 2 + 0.02, depth / 2 - 0.004, z_edge), 0.0045,
                     fabric, seg=5, smooth=True)
    # almofadas soltas de assento e de encosto
    seat_w = span / seats - 0.006
    seat_z = LIFT + 0.17
    for index in range(seats):
        cx = (index - (seats - 1) / 2) * (span / seats)
        rows = shapes.cushion(pillows, cx, 0.14, seat_z, seat_w, 0.64, 0.17, fabric, squareness=3.4, corner=0.22,
                              crown=0.018, wrinkle=0.0025, phase=index * 1.9)
        shapes.piping_at(pillows, rows, 0.82, 0.0045, fabric)
        shapes.piping_at(pillows, rows, -0.82, 0.0045, fabric)
        with pillows.at(cx, -0.215, seat_z + 0.215, rx=-76):
            rows = shapes.cushion(pillows, 0, 0, -0.095, seat_w, 0.50, 0.19, fabric, squareness=3.0, corner=0.22,
                                  crown=0.02, dimple=0.04, wrinkle=0.0025, phase=index * 2.3 + 1)
            shapes.piping_at(pillows, rows, 0.82, 0.0045, fabric)
            shapes.button(pillows, 0, 0, 0.088, fabric)


def throw_cushion(soft, x, y, z, *, tilt=-20, turn=0, fabric="velvet_burgundy", size=0.40):
    """Almofada de enfeite encostada no encosto: quadrada, macia, levemente amassada."""
    with soft.at(x, y, z, rx=tilt, rz=turn):
        shapes.cushion(soft, 0, 0, -0.05, size, size, 0.10, fabric, squareness=2.6, corner=0.30, crown=0.012,
                       wrinkle=0.005, phase=turn)


def make_armchair(ctx, room, x, y, yaw, *, fabric="fabric_gray", worn=False, z=None):
    """Poltrona de braços enrolados. `worn=True` troca o tecido por couro gasto (a poltrona velha do escritório)."""
    asm = new_upholstered("armchair")
    cover = "leather_aged" if worn else "armchair_fabric"
    _upholstered_seat(asm, 0.86, 0.86, cover, 1, arm_half=0.07)
    return place(ctx, asm, room, "armchair", x, y, yaw, z)


def _sofa_colliders(width, depth, seats, arm_half=0.085):
    """Formas simples do sofá (almofadas, braço, encosto) para o pano cair em cima, no mesmo referencial."""
    colliders = cloth.collider_builder("sofa_colliders")
    roll_radius = arm_half / math.cos(math.radians(35))
    arm_x = width / 2 - roll_radius
    span = 2 * (arm_x - arm_half)
    colliders.soft_box(0, 0, LIFT, width, depth, 0.17, "walnut", radius=0.05, edge=0.02)
    for index in range(seats):
        cx = (index - (seats - 1) / 2) * (span / seats)
        colliders.soft_box(cx, 0.14, LIFT + 0.17, span / seats - 0.006, 0.64, 0.18, "walnut", radius=0.06, edge=0.05)
        with colliders.at(cx, -0.215, LIFT + 0.17 + 0.215, rx=-76):
            colliders.soft_box(0, 0, -0.095, span / seats - 0.006, 0.50, 0.19, "walnut", radius=0.06, edge=0.05)
    for side in (-1, 1):
        shapes.rolled_arm(colliders, side * arm_x, -depth / 2 + 0.01, depth / 2 - 0.015, LIFT, arm_half, 0.545, "walnut")
    return colliders


def blanket_on_sofa(asm, width, depth, seats):
    """Manta xadrez jogada sobre o assento da esquerda e o braço, escorrendo pela frente."""
    colliders = _sofa_colliders(width, depth, seats)
    colliders.box(0, 0, -0.02, 6, 6, 0.02, "walnut")                    # chão: se escorregar, para nele
    mesh = cloth.drape_over(colliders, width=1.1, depth=0.7, center=(0.62, 0.05, 0.85), yaw=math.radians(-12),
                            material="wool_plaid", cell=0.04, frames=80, mass=0.4, stiffness=16.0, bending=7.0, thickness=0.007)
    asm.add_mesh(mesh)


def make_sofa(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Sofá de três lugares de frente para a TV, com uma almofada de quem dormiu ali e a manta da Laura."""
    asm = new_upholstered("sofa_living")
    _upholstered_seat(asm, 2.1, 0.9, "sofa_fabric", 3)
    throw_cushion(asm.pillows, -0.62, -0.02, 0.60, tilt=-62, turn=-14)
    blanket_on_sofa(asm, 2.1, 0.9, 3)
    return place(ctx, asm, room, "sofa", x, y, yaw, z, name="sofa_living", anchor=anchor)


def make_coffee_table(ctx, room, x, y, yaw, *, z=None):
    """Mesa de centro de nogueira (1,0 x 0,5 m, tampo a 0,42 m) com prateleira inferior e as coisas de quem senta ali.

    O centro do tampo fica livre: é onde repousa `Item_NOTE_3`.
    """
    rng = ctx.rng
    asm = Composite("coffee_table", wood=shapes.WOOD, round=shapes.SMOOTH, small=shapes.SMOOTH)
    wood, small = asm.wood, asm.small
    shapes.slab(asm.round, 0, 0, 0.38, 1.0, 0.5, shapes.OGEE_EDGE, "walnut", radius=0.045)
    for sign in (-1, 1):
        wood.box(0, sign * 0.2, 0.325, 0.86, 0.022, 0.055, "walnut")
        wood.box(sign * 0.425, 0, 0.325, 0.022, 0.38, 0.055, "walnut_v")
        for leg_y in (-1, 1):
            shapes.turned_leg(asm.round, sign * 0.43, leg_y * 0.19, 0.0, 0.385, 0.033, "walnut_v", "tapered")
    wood.box(0, 0, 0.115, 0.84, 0.36, 0.02, "oak")
    for sign in (-1, 1):
        wood.box(0, sign * 0.185, 0.095, 0.84, 0.02, 0.04, "oak")
    # sobre o tampo
    small.cylinder(-0.32, 0.08, 0.4195, 0.052, 0.003, "leather_black", seg=shapes.seg(16), smooth=True)
    parts.mug(small, -0.32, 0.08, 0.4225, 0.04, 0.09, "ceramic_cream", handle_dir=1, coffee=True)
    things.remote_control(small, 0.20, -0.13, 0.42, yaw=28)
    things.envelope_pile(small, 0.34, 0.11, 0.42, rng, count=4)
    things.reading_glasses(small, -0.12, -0.15, 0.42, yaw=-14)
    # na prateleira de baixo: revistas e um álbum de fotos
    for index, (turn, shift) in enumerate(((4, 0.0), (-9, 0.02), (14, -0.01))):
        with small.at(-0.18 + shift, 0.0, 0.135 + index * 0.006, rz=turn):
            small.box(0, 0, 0, 0.22, 0.29, 0.005, "paper_white", skip=("top",))
            small.panel(0, 0, 0.0051, 0.22, 0.29, "magazine_" + "abc"[index], "top")
    return place(ctx, asm, room, "coffee_table", x, y, yaw, z, collision_top=0.42)


def make_floor_lamp(ctx, room, x, y, *, z=None):
    """Abajur de chão: base de ferro, haste torneada de latão, cúpula plissada que acende em âmbar."""
    asm = Composite("floor_lamp", metal=shapes.SMOOTH, shade=craft.RAW)
    metal, shade = asm.metal, asm.shade
    metal.lathe([(0.0, 0.0), (0.16, 0.0), (0.165, 0.008), (0.15, 0.022), (0.07, 0.034), (0.03, 0.05), (0.0, 0.05)], 0, 0, 0,
                "steel_dark", seg=shapes.seg(24), smooth=True)
    metal.lathe([(0.026, 0.05), (0.03, 0.08), (0.016, 0.12), (0.014, 0.4), (0.024, 0.43), (0.014, 0.46), (0.012, 0.9),
                 (0.026, 0.93), (0.014, 0.96), (0.011, 1.25), (0.02, 1.27), (0.011, 1.29)], 0, 0, 0, "brass_aged",
                seg=shapes.seg(16), smooth=True)
    metal.lathe([(0.02, 1.27), (0.026, 1.285), (0.02, 1.31), (0.0, 1.31)], 0, 0, 0, "brass_aged", seg=shapes.seg(14))
    for side in (-1, 1):                                                 # garras que seguram a cúpula
        metal.tube((0.0, 0.0, 1.29), (side * 0.15, 0.0, 1.33), 0.0025, "brass_aged", seg=4)
    pleats = 48
    rings = []
    for z_ring, radius in ((1.30, 0.215), (1.60, 0.150)):
        rings.append([((radius * (1 + 0.03 * (-1) ** i)) * math.cos(2 * math.pi * i / pleats),
                       (radius * (1 + 0.03 * (-1) ** i)) * math.sin(2 * math.pi * i / pleats), z_ring) for i in range(pleats)])
    shade.loft(rings, "lampshade_pleated", False, False, True, orient=False)
    metal.sphere(0, 0, 1.4, 0.032, "glass_clear", seg=10, rings=6)
    metal.sphere(0, 0, 1.4, 0.012, "emit_white", seg=6, rings=4)
    cord = craft.tube_along([(0.0, -0.02, 0.01), (-0.08, -0.1, 0.004), (-0.16, -0.12, 0.004), (-0.2, -0.17, 0.004)],
                            0.0035, segments=8, name="cabo_abajur")
    cord.materials.append(materials.get("rubber"))
    asm.add_mesh(cord)
    return place(ctx, asm, room, "floor_lamp", x, y, 0.0, z)
