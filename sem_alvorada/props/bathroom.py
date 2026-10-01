"""Mobília do banheiro: banheira com água parada, vaso, pia com bancada, armário de remédios, cortina."""
import math

from . import parts
from .furniture import wall_spot
from .kit import MeshBuilder
from .placement import against_wall, flush_center, floor_z, place


def make_bathtub(ctx, room, wall, along):
    """Banheira cheia de água escura e parada, com o patinho de borracha da Emma boiando."""
    length, width, height = 1.7, 0.75, 0.56
    x, y, yaw = against_wall(room, wall, along, width)
    m = MeshBuilder("bathtub")
    for cx in (-length / 2 + 0.12, length / 2 - 0.12):
        for cy in (-width / 2 + 0.1, width / 2 - 0.1):
            m.cylinder(cx, cy, 0, 0.03, 0.06, "chrome", seg=6)
    m.box(0, 0, 0.06, length, width, 0.05, "porcelain")
    for sign in (-1, 1):
        m.soft_box(0, sign * (width / 2 - 0.045), 0.06, length, 0.09, height - 0.06, "porcelain", radius=0.03, edge=0.015)
        m.soft_box(sign * (length / 2 - 0.045), 0, 0.06, 0.09, width - 0.16, height - 0.06, "porcelain", radius=0.02, edge=0.015)
    m.panel(0, 0, 0.40, length - 0.16, width - 0.16, "water_dark", "top")
    m.tube((-length / 2 + 0.06, -0.15, 0.62), (-length / 2 + 0.06, -0.15, 0.68), 0.025, "chrome")
    m.tube((-length / 2 + 0.06, -0.15, 0.68), (-length / 2 + 0.06, 0.03, 0.68), 0.016, "chrome", seg=5)
    for side in (-1, 1):
        m.cylinder(-length / 2 + 0.06, -0.15 + side * 0.11, 0.56, 0.02, 0.05, "chrome", seg=6)
    with m.at(0.25, 0.08, 0.40, rz=25):
        m.lathe([(0, 0), (0.035, 0.01), (0.04, 0.03), (0.03, 0.055), (0, 0.06)], 0, 0, 0, "rubber_duck", seg=7,
                cap_bottom=False, cap_top=False)
        m.sphere(0.03, 0, 0.07, 0.024, "rubber_duck", seg=7, rings=4)
        m.box(0.06, 0, 0.065, 0.02, 0.022, 0.01, "toy_red")
    return place(ctx, m, room, "bathtub", x, y, yaw)


def make_shower_curtain(ctx, room, x, rod_y0, rod_y1, hang_length, *, rod_z=1.85, drop=1.3):
    """Cortina de box puxada só até a metade da vara, com dobras verticais, presa ao lado da banheira."""
    m = MeshBuilder("shower_curtain")
    m.tube((0, rod_y0, rod_z), (0, rod_y1, rod_z), 0.012, "chrome", seg=5)

    def fn(u, v):
        return (0.035 * math.sin(u * 20 + v * 0.6), rod_y1 - hang_length + u * hang_length, rod_z - 0.03 - v * drop)

    m.surface(fn, 16, 3, "shower_curtain", uv_size=(hang_length, drop))
    return place(ctx, m, room, "shower_curtain", x, 0.0, 0.0, mode="decor")


def make_toilet(ctx, room, wall, along):
    depth = 0.68
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("toilet")
    m.cylinder(0, 0.02, 0, 0.13, 0.2, "porcelain", seg=8, r_top=0.11)
    m.soft_box(0, 0.03, 0.2, 0.38, 0.5, 0.2, "porcelain", radius=0.14, edge=0.03, corner_points=4)
    m.soft_box(0, 0.05, 0.4, 0.40, 0.48, 0.025, "plastic_beige", radius=0.15, edge=0.008, corner_points=4)
    with m.at(0, -0.19, 0.425, rx=-6):
        m.soft_box(0, 0.09, 0, 0.36, 0.42, 0.02, "plastic_beige", radius=0.14, edge=0.008, corner_points=4)
    m.soft_box(0, -depth / 2 + 0.09, 0.38, 0.40, 0.17, 0.40, "porcelain", radius=0.03, edge=0.02)
    m.cylinder(0.1, -depth / 2 + 0.09, 0.78, 0.018, 0.02, "chrome", seg=6)
    return place(ctx, m, room, "toilet", x, y, yaw)


def make_vanity(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Pia com bancada 1,2 x 0,5 m: gabinete, cuba à esquerda (visto de frente), torneira, copo de escovas."""
    cy = flush_center(room, x, y, yaw, 0.5)
    basin_x, basin_w, basin_d = 0.2, 0.36, 0.30
    m = MeshBuilder("bath_sink")
    with m.at(0, cy, 0):
        m.box(0, 0, 0.0, 1.2, 0.5, 0.86, "wood_mid", mats={"front": "veneer_mid"})
        for door_x in (-0.3, 0.3):
            m.box(door_x, 0.255, 0.08, 0.54, 0.012, 0.72, "wood_dark")
            parts.knob(m, door_x + (0.22 if door_x < 0 else -0.22), 0.265, 0.42, "chrome")
        parts.counter_top_with_basin(m, -0.62, 0.62, -0.25, 0.29, 0.86, 0.04, basin_x, 0.02, basin_w, basin_d, 0.12,
                                     "porcelain", bottom_mat="water_dark")
        m.cylinder(basin_x, -0.20, 0.90, 0.014, 0.05, "chrome", seg=6)
        m.tube((basin_x, -0.20, 0.95), (basin_x, -0.08, 0.95), 0.011, "chrome", seg=5)
        parts.mug(m, -0.36, -0.12, 0.90, 0.03, 0.09, "glass_clear")
        for i, color in enumerate(("toy_blue", "toy_red")):
            m.bar((-0.36, -0.12, 0.92), (-0.36 + 0.02 * (i * 2 - 1), -0.12, 1.02), 0.008, color)
        m.cylinder(-0.14, 0.05, 0.90, 0.04, 0.02, "painted_white", seg=6)
    return place(ctx, m, room, "vanity", x, y, yaw, z, name="bath_sink", anchor=anchor)


def make_medicine_cabinet(ctx, room, wall, along, z_bottom, *, door_open_deg=28):
    """Armário de remédios com a porta-espelho rachada meio aberta e frascos nas prateleiras."""
    width, height, depth = 0.56, 0.72, 0.14
    x, y, yaw = wall_spot(room, wall, along)
    m = MeshBuilder("medicine_cabinet")
    m.box(0, depth / 2, 0, width, depth, height, "painted_white", skip=("front",))
    m.box(0, 0.01, 0, width - 0.02, 0.02, height, "painted_white")
    for level in (0.26, 0.50):
        m.box(0, depth / 2, level, width - 0.04, depth - 0.02, 0.012, "painted_white")
    for cx, color in ((-0.17, "pill_orange"), (-0.05, "glass_clear"), (0.12, "pill_orange")):
        m.cylinder(cx, depth / 2, 0.512, 0.024, 0.08, color, seg=7)
    m.box(0.13, depth / 2, 0.272, 0.1, 0.06, 0.07, "paper_white")
    with m.at(-width / 2, depth, 0, rz=door_open_deg):
        m.box(width / 2, 0.006, 0, width, 0.012, height, "painted_white", mats={"front": "mirror_cracked"})
    return place(ctx, m, room, "medicine_cabinet", x, y, yaw, floor_z(room) + z_bottom, mode="wall")


def make_towel_bar(ctx, room, wall, along, z):
    x, y, yaw = wall_spot(room, wall, along)
    m = MeshBuilder("towel_bar")
    m.tube((-0.32, 0.08, 0), (0.32, 0.08, 0), 0.01, "chrome", seg=5)
    for sx in (-0.3, 0.3):
        m.box(sx, 0.04, -0.02, 0.02, 0.08, 0.04, "chrome")

    def fold(u, v):
        return (-0.2 + 0.4 * u + 0.01 * math.sin(v * 6), 0.09 + 0.03 * v - 0.015 * math.sin(u * 9), -0.6 * v + 0.02)

    m.surface(fold, 4, 4, "linen_dirty", uv_size=(0.4, 0.6))
    return place(ctx, m, room, "towel_bar", x, y, yaw, floor_z(room) + z, mode="wall")


def make_trash_bin(ctx, room, x, y, *, z=None, height=0.32, radius=0.14, mat="plastic_gray", overflowing=False):
    m = MeshBuilder("trash_bin")
    m.cylinder(0, 0, 0, radius * 0.85, height, mat, seg=8, r_top=radius, caps=(True, False))
    m.torus(0, 0, height, radius, 0.008, mat, seg=8, seg_minor=4)
    if overflowing:
        m.cylinder(0, 0, height - 0.05, radius * 0.9, 0.12, "linen_dirty", seg=6, r_top=radius * 0.5)
        m.box(0.05, 0.02, height + 0.02, 0.09, 0.06, 0.05, "paper_white")
    return place(ctx, m, room, "trash_bin", x, y, 0.0, z)
