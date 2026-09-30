"""Hall de entrada: sapateira, cabideiro com casacos, porta-guarda-chuva, planta seca, fotos na escada."""
import math

from .. import layout
from . import parts
from .kit import MeshBuilder
from .placement import against_wall, place


def make_shoe_rack(ctx, room, wall, along):
    """Sapateira de três prateleiras: botas do Dan, sapatilhas da Laura e as galochas amarelas da Emma."""
    width, depth, height = 0.62, 0.28, 0.56
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("shoe_rack")
    for side in (-1, 1):
        m.box(side * (width / 2 - 0.015), 0, 0, 0.03, depth, height, "wood_mid")
    m.box(0, -depth / 2 + 0.01, 0, width, 0.02, height, "wood_dark")
    for level in range(4):
        m.box(0, 0, level * (height - 0.03) / 3, width - 0.02, depth - 0.02, 0.03, "wood_mid")
    z_first = 0.03
    parts.shoe_pair(m, -0.16, 0.01, z_first, 1.0, "leather_brown", 0.1)
    parts.shoe_pair(m, 0.16, 0.01, z_first, 1.0, "coat_dark", -0.15)
    parts.shoe_pair(m, -0.12, 0.01, z_first + 0.18, 0.85, "coat_beige", 0.05)
    parts.shoe_pair(m, 0.16, 0.0, z_first + 0.18, 0.62, "boot_yellow", 0.0, tall=True)
    parts.shoe_pair(m, 0.0, 0.01, z_first + 0.36, 0.95, "fabric_gray", 0.2)
    return place(ctx, m, room, "shoe_rack", x, y, yaw)


def make_coat_rack(ctx, room, x, y):
    """Cabideiro de pé com o casaco do Dan, um cachecol e a capa de chuva amarela pendurada no gancho baixo."""
    m = MeshBuilder("coat_rack")
    m.cylinder(0, 0, 0, 0.22, 0.03, "wood_dark", seg=8, r_top=0.14)
    m.tube((0, 0, 0.03), (0, 0, 1.85), 0.022, "wood_dark", seg=6)
    for i in range(4):
        angle = math.radians(90 * i + 45)
        tip = (0.16 * math.cos(angle), 0.16 * math.sin(angle), 1.90)
        m.tube((0, 0, 1.82), tip, 0.012, "brass", seg=5)
    for angle_deg, height in ((0, 1.28), (180, 1.28)):
        angle = math.radians(angle_deg)
        m.tube((0, 0, height), (0.12 * math.cos(angle), 0.12 * math.sin(angle), height + 0.05), 0.010, "brass", seg=5)
    with m.at(0.17, 0.10, 1.86):                                   # casaco longo do Dan
        m.frustum(0, 0, -0.98, 0.50, 0.16, 0.36, 0.12, 0.98, "coat_dark")
        m.box(0, 0.08, -0.6, 0.06, 0.02, 0.34, "coat_beige")
    with m.at(-0.12, -0.12, 1.83, rz=40):                          # cachecol
        m.frustum(0, 0, -0.55, 0.09, 0.04, 0.10, 0.05, 0.55, "fabric_red")
    with m.at(0.13, 0.0, 1.30):                                    # capa amarela, na altura de uma criança
        m.frustum(0, 0, -0.55, 0.30, 0.09, 0.22, 0.07, 0.55, "coat_yellow")
        m.box(0.0, 0.05, -0.45, 0.20, 0.03, 0.18, "coat_yellow")
    return place(ctx, m, room, "coat_rack", x, y, 0.0, collision=[(-0.22, -0.22, 0.0, 0.22, 0.22, 1.9)])


def make_umbrella_stand(ctx, room, x, y):
    m = MeshBuilder("umbrella_stand")
    m.cylinder(0, 0, 0, 0.09, 0.45, "ceramic_cream", seg=8, r_top=0.11, caps=(True, False))
    for i, (dx, dy, lean) in enumerate(((-0.04, 0.02, -4), (0.03, -0.03, 6), (0.04, 0.04, 2))):
        tip = (dx + math.tan(math.radians(lean)) * 0.75, dy, 0.85)
        m.tube((dx, dy, 0.05), tip, 0.011, "coat_dark" if i < 2 else "plush_pink", seg=5)
        m.tube(tip, (tip[0] + 0.06, tip[1], tip[2] + 0.03), 0.011, "steel_dark", seg=5)
    return place(ctx, m, room, "umbrella_stand", x, y, 0.0)


def make_dead_plant(ctx, room, x, y, z, *, height=0.5):
    """Vaso com uma planta que secou: hastes finas caídas."""
    m = MeshBuilder("dead_plant")
    m.cylinder(0, 0, 0, 0.09, 0.16, "ceramic_cream", seg=8, r_top=0.12)
    m.cylinder(0, 0, 0.14, 0.11, 0.02, "food_dried", seg=8)
    for i in range(7):
        angle = math.radians(i * 51)
        tip = (0.16 * math.cos(angle), 0.16 * math.sin(angle), 0.16 + height * (0.55 + 0.1 * (i % 3)))
        m.tube((0, 0, 0.15), tip, 0.006, "wood_mid", seg=4, r_end=0.002)
        m.box(tip[0], tip[1], tip[2] - 0.05, 0.05, 0.02, 0.05, "food_dried")
    return place(ctx, m, room, "dead_plant", x, y, 0.0, z, mode="decor")


def stair_photo_slots(count=7):
    """Posições (y, altura acima do piso do térreo) dos quadros seguindo a subida da escada."""
    stairs = layout.STAIRS
    span = stairs.y1 - stairs.y0 - 0.9
    slots = []
    for i in range(count):
        y = stairs.y0 + 0.5 + span * i / (count - 1)
        slots.append((y, layout.stairs_height(stairs.x0 + 0.1, y) + 1.55))
    return slots
