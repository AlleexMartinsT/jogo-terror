"""Móveis de guardar do quarto do casal: guarda-roupa com roupas penduradas, cômoda, banco e cesto de roupa suja."""
import math

from . import woodwork_quartos as joinery
from .assembly_quartos import HERO_WOOD, METAL, PLUSH, UPHOLSTERY, Assembly
from .placement import flush_center, place

WALNUT, WALNUT_V = joinery.wood_pair("up_walnut")


# ---------------------------------------------------------------------------
# Roupas
# ---------------------------------------------------------------------------
GARMENT_LOOKS = {         # (largura dos ombros, comprimento, espessura, perfil (t, meia-largura, meia-profundidade))
    "coat": (0.46, 0.94, 0.05, [(0.0, 0.225, 0.05), (0.18, 0.215, 0.055), (0.48, 0.19, 0.05), (0.78, 0.215, 0.055),
                                (0.92, 0.235, 0.06), (0.985, 0.19, 0.045), (1.0, 0.05, 0.02)]),
    "shirt": (0.42, 0.72, 0.035, [(0.0, 0.20, 0.035), (0.35, 0.185, 0.04), (0.8, 0.205, 0.045), (0.95, 0.215, 0.04),
                                  (1.0, 0.05, 0.02)]),
    "dress": (0.36, 0.98, 0.03, [(0.0, 0.26, 0.045), (0.3, 0.19, 0.04), (0.6, 0.15, 0.04), (0.82, 0.17, 0.045),
                                 (0.95, 0.19, 0.04), (1.0, 0.05, 0.02)]),
}


def garment(m, cx, cy, top_z, kind, material, *, facing=90.0):
    """Peça pendurada num cabide de arame, com os ombros virados para o fundo do armário (`facing` em graus)."""
    shoulder, length, thickness, profile = GARMENT_LOOKS[kind]
    with m.at(cx, cy, 0, rz=facing):
        rings = []
        for t, half_width, half_depth in profile:
            z = top_z - length * (1 - t)
            rings.append([(half_width * math.cos(a), half_depth * math.sin(a), z)
                          for a in (2 * math.pi * k / 12 for k in range(12))])
        m.loft(rings, material, cap_start=True, cap_end=True, smooth=True)
        for side in (-1, 1):
            m.tube((side * shoulder * 0.46, 0.0, top_z - 0.04), (side * shoulder * 0.52, -0.02, top_z - length * 0.55), 0.038,
                   material, seg=10, r_end=0.028, smooth=True)
        m.tube((0, 0, top_z + 0.02), (0, 0, top_z + 0.09), 0.0018, "chrome", seg=5)
        m.tube((0, 0, top_z + 0.04), (-shoulder * 0.5, 0, top_z - 0.03), 0.0018, "chrome", seg=5)
        m.tube((0, 0, top_z + 0.04), (shoulder * 0.5, 0, top_z - 0.03), 0.0018, "chrome", seg=5)


# ---------------------------------------------------------------------------
# Guarda-roupa
# ---------------------------------------------------------------------------
def _carcass(m, width, depth, height):
    for sx in (-1, 1):
        joinery.turned(m, sx * (width / 2 - 0.05), depth / 2 - 0.06, 0, joinery.TURNED_FOOT, 0.10, WALNUT_V, seg=16)
        joinery.turned(m, sx * (width / 2 - 0.05), -depth / 2 + 0.06, 0, joinery.TURNED_FOOT, 0.10, WALNUT_V, seg=16)
        m.box(sx * (width / 2 - 0.0125), 0, 0.10, 0.025, depth, height - 0.15, WALNUT_V)
    m.box(0, 0, 0.10, width, depth, 0.03, WALNUT)
    m.box(0, 0, 0.0, width - 0.08, depth - 0.10, 0.10, WALNUT)
    m.box(0, 0, height - 0.05, width, depth, 0.03, WALNUT)
    m.box(0, 0.02, height - 0.025, width + 0.05, depth + 0.04, 0.05, WALNUT)
    m.box(0, 0.01, height + 0.025, width + 0.02, depth + 0.02, 0.025, WALNUT)
    m.box(0, -depth / 2 + 0.01, 0.13, width - 0.05, 0.016, height - 0.2, "up_paint_white")
    m.box(0, 0, 0.13, 0.02, depth - 0.04, height - 0.2, WALNUT_V)               # divisória central
    m.box(0.33, 0, height - 0.22, width / 2 - 0.05, depth - 0.04, 0.02, WALNUT)    # prateleira do chapéu


def _door(m, hinge_x, front_y, width, height, mirror=False, knob_side=1):
    """Folha da porta com origem na dobradiça (a folha corre para -X se `knob_side` > 0, senão para +X)."""
    sign = -knob_side
    center = sign * width / 2
    if mirror:
        joinery.framed_panel(m, center, front_y, 0.12, width, height, WALNUT, "up_mirror_plain", depth=0.026, frame=0.075,
                             frame_mat_v=WALNUT_V, recess=0.012)
    else:
        split = 0.62
        joinery.framed_panel(m, center, front_y, 0.12 + split, width, height - split, WALNUT, WALNUT, depth=0.026,
                             frame=0.06, frame_mat_v=WALNUT_V, raised=True)
        joinery.framed_panel(m, center, front_y, 0.12, width, split + 0.02, WALNUT, WALNUT, depth=0.026, frame=0.06,
                             frame_mat_v=WALNUT_V, raised=True)
    joinery.knob(m, sign * (width - 0.06), front_y + 0.026, 0.12 + height * 0.48, "brass", 1.4)
    for hinge_z in (0.30, height * 0.5, height - 0.12):
        m.box(0, front_y + 0.026, hinge_z, 0.03, 0.004, 0.07, "brass")


def make_wardrobe(ctx, room, x, y, yaw, *, z=None, width=1.3, depth=0.6):
    """Guarda-roupa de nogueira: porta com espelho, porta almofadada entreaberta e roupas penduradas no escuro."""
    height = 1.95
    cy = flush_center(room, x, y, yaw, depth)
    unit = Assembly("wardrobe")
    wood = unit.part(HERO_WOOD)
    door_w = (width - 0.05) / 2
    front = depth / 2 - 0.01
    with wood.at(0, cy, 0):
        _carcass(wood, width, depth, height)
        with wood.at(-width / 2 + 0.02, 0, 0):
            _door(wood, 0, front, door_w, height - 0.26, mirror=True, knob_side=-1)
        with wood.at(width / 2 - 0.02, 0, 0, rz=-13):
            _door(wood, 0, front, door_w, height - 0.26, knob_side=1)
    hardware = unit.part(METAL)
    with hardware.at(0, cy, 0):
        hardware.tube((0.035, 0.0, height - 0.28), (width / 2 - 0.035, 0.0, height - 0.28), 0.011, "chrome", seg=10)
    clothes = unit.part(PLUSH)
    looks = [("coat", "up_cloth_dark"), ("shirt", "up_cloth_white"), ("dress", "up_cloth_red"), ("coat", "up_cloth_beige"),
             ("shirt", "up_cloth_blue"), ("coat", "up_cloth_dark"), ("shirt", "up_cloth_gray")]
    for index, (kind, material) in enumerate(looks):
        garment(clothes, 0.085 + index * 0.086, cy + 0.0, height - 0.30, kind, material, facing=90.0 + (index % 2) * 4)
    return place(ctx, unit, room, "wardrobe", x, y, yaw, z)


# ---------------------------------------------------------------------------
# Cômoda
# ---------------------------------------------------------------------------
DRESSER_ROWS = ((0.60, 0.17), (0.43, 0.17), (0.255, 0.17), (0.09, 0.16))
OPEN_ROW, OPEN_SHIFT = 1, 0.10


def _dresser_drawers(m, width, front):
    for row_index, (z0, height) in enumerate(DRESSER_ROWS):
        splits = 2 if row_index == 0 else 1
        drawer_w = (width - 0.1 - 0.02 * (splits - 1)) / splits
        for column in range(splits):
            cx = -((splits - 1) / 2 - column) * (drawer_w + 0.02)
            is_open = row_index == OPEN_ROW
            shift = OPEN_SHIFT if is_open else 0.0
            joinery.framed_panel(m, cx, front + shift, z0, drawer_w, height, WALNUT, WALNUT, depth=0.022, frame=0.028,
                                 frame_mat_v=WALNUT_V)
            joinery.pull(m, cx, front + shift + 0.022, z0 + height / 2, min(0.12, drawer_w * 0.3), "brass")
            if is_open:
                _drawer_tray(m, cx, front + shift, z0, drawer_w, height)


def _drawer_tray(m, cx, front_y, z0, width, height):
    """Caixa da gaveta puxada: fundo, laterais e fundo traseiro, dentro do corpo da cômoda."""
    m.box(cx, front_y - 0.2, z0 + 0.012, width - 0.04, 0.40, 0.012, WALNUT)
    for side in (-1, 1):
        m.box(cx + side * (width - 0.05) / 2, front_y - 0.2, z0 + 0.012, 0.012, 0.40, height * 0.62, WALNUT)
    m.box(cx, front_y - 0.40, z0 + 0.012, width - 0.04, 0.012, height * 0.62, WALNUT)


def make_dresser(ctx, room, x, y, yaw, *, z=None):
    """Cômoda de nogueira 1,40 x 0,50: cinco gavetas almofadadas com puxadores de barra, uma puxada com meias."""
    width, depth, body_top = 1.40, 0.50, 0.80
    cy = flush_center(room, x, y, yaw, depth)
    unit = Assembly("dresser")
    wood = unit.part(HERO_WOOD)
    front = depth / 2 - 0.02
    with wood.at(0, cy, 0):
        for sx in (-1, 1):
            for sy in (-1, 1):
                joinery.turned(wood, sx * (width / 2 - 0.06), sy * (depth / 2 - 0.07), 0, joinery.TURNED_FOOT, 0.09, WALNUT_V,
                               seg=16)
        wood.box(0, 0, 0.09, width - 0.04, depth - 0.04, body_top - 0.09, WALNUT_V)
        wood.box(0, 0.02, body_top, width + 0.05, depth + 0.04, 0.04, WALNUT)
        _dresser_drawers(wood, width, front)
    socks = unit.part(UPHOLSTERY)
    z_tray = DRESSER_ROWS[OPEN_ROW][0] + 0.024
    with socks.at(0, cy, 0):
        for index, (dx, dy, turn, material) in enumerate(((-0.28, -0.14, 20, "up_cloth_gray"), (-0.12, -0.18, -35, "up_cloth_dark"),
                                                          (0.04, -0.12, 10, "up_cloth_beige"), (-0.2, -0.28, 80, "up_cloth_blue"))):
            with socks.at(dx, front + OPEN_SHIFT + dy, z_tray, rz=turn):
                socks.soft_box(0, 0, 0, 0.17, 0.09, 0.05, material, radius=0.03, edge=0.02)
        socks.tube((-0.22, front + OPEN_SHIFT + 0.01, z_tray + 0.04), (-0.22, front + OPEN_SHIFT + 0.07, z_tray - 0.05), 0.022,
                   "up_cloth_gray", seg=10, r_end=0.016, smooth=True)
    return place(ctx, unit, room, "dresser", x, y, yaw, z)
