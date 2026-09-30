"""Móveis de escritório: escrivaninhas, estantes, arquivo, globo, luminária, computador, papéis."""
import math

from . import parts
from .kit import MeshBuilder
from .placement import against_wall, flush_center, place


def make_desk(ctx, room, x, y, yaw, *, width, depth, anchor=None, z=None, name=None, pedestal="right",
              wood="wood_dark"):
    """Escrivaninha com gavetas de um lado; a frente (+Y) é onde a cadeira fica. Tampo a 0,76 m."""
    cy = flush_center(room, x, y, yaw, depth)
    m = MeshBuilder(name or "desk")
    sign = 1 if pedestal == "right" else -1
    with m.at(0, cy, 0):
        m.box(0, 0.01, 0.72, width + 0.04, depth + 0.02, 0.04, wood, mats={"top": "veneer_dark"})
        ped_w = 0.46
        m.box(sign * (width / 2 - ped_w / 2 - 0.01), 0, 0, ped_w, depth - 0.04, 0.72, wood)
        parts.drawer_stack(m, sign * (width / 2 - ped_w / 2 - 0.01), depth / 2 - 0.02, 0.02, ped_w, 0.68, 3, "wood_mid")
        m.box(-sign * (width / 2 - 0.03), 0, 0, 0.04, depth - 0.06, 0.72, wood)
        m.box(0, -depth / 2 + 0.04, 0.25, width - 0.06, 0.02, 0.47, wood)
    return place(ctx, m, room, "desk", x, y, yaw, z, name=name, anchor=anchor)


def make_desk_lamp(ctx, room, x, y, z, yaw=0.0, *, lit=True):
    """Luminária articulada de mesa com cúpula cônica voltada para o tampo."""
    m = MeshBuilder("desk_lamp")
    m.cylinder(0, 0, 0, 0.09, 0.025, "steel_dark", seg=8)
    m.bar((0, 0, 0.02), (0.05, 0.03, 0.30), 0.014, "steel_dark")
    m.bar((0.05, 0.03, 0.30), (-0.05, 0.16, 0.36), 0.012, "steel_dark")
    with m.at(-0.06, 0.17, 0.34, rx=-25):
        m.cylinder(0, 0, -0.02, 0.10, 0.11, "lampshade_lit" if lit else "lampshade_off", seg=8, r_top=0.03)
        m.cylinder(0, 0, -0.02, 0.10, 0.008, "steel_dark", seg=8)
    return place(ctx, m, room, "desk_lamp", x, y, yaw, z, mode="decor")


def make_notebook(ctx, room, x, y, z, yaw=0.0, *, cover="fabric_blue"):
    m = MeshBuilder("notebook")
    m.box(0, 0, 0, 0.23, 0.31, 0.02, cover)
    m.box(0.004, 0, 0.02, 0.21, 0.29, 0.002, "paper_white")
    m.box(-0.115, 0, 0.0, 0.012, 0.31, 0.022, "steel_dark")
    return place(ctx, m, room, "notebook", x, y, yaw, z, mode="decor")


def make_papers(ctx, room, x, y, z, count=6, spread=0.22, *, mat="paper_white"):
    """Folhas espalhadas sobre uma superfície, giradas ao acaso (bagunça determinística)."""
    m = MeshBuilder("papers")
    for i in range(count):
        parts.paper_sheet(m, ctx.rng.uniform(-spread, spread), ctx.rng.uniform(-spread, spread) * 0.7,
                          i * 0.0022, 0.21, 0.29, mat, ctx.rng.uniform(0, math.pi))
    return place(ctx, m, room, "papers", x, y, 0.0, z, mode="decor")


def make_crt_computer(ctx, room, x, y, z, yaw):
    """Micro dos anos 90: monitor de tubo, teclado e mouse bege, tela apagada."""
    m = MeshBuilder("crt_computer")
    m.box(0, 0.0, 0.0, 0.42, 0.40, 0.06, "plastic_beige")
    m.soft_box(0, 0.02, 0.06, 0.40, 0.32, 0.34, "plastic_beige", radius=0.03, edge=0.015)
    m.frustum(0, -0.22, 0.09, 0.30, 0.20, 0.16, 0.10, 0.26, "plastic_beige")
    m.panel(0, 0.182, 0.24, 0.31, 0.26, "mirror_plain", "front")
    m.soft_box(0, 0.30, 0.0, 0.46, 0.16, 0.03, "plastic_beige", radius=0.01, edge=0.008)
    m.box(0, 0.30, 0.03, 0.42, 0.13, 0.006, "plastic_gray")
    m.soft_box(0.30, 0.30, 0.0, 0.06, 0.10, 0.03, "plastic_beige", radius=0.02, edge=0.01)
    return place(ctx, m, room, "computer", x, y, yaw, z, mode="decor")


def make_bookcase(ctx, room, wall, along, *, width=1.5, height=1.9, depth=0.32, shelves=5, fill=0.8,
                  z=None, name=None):
    """Estante de livros: os livros são blocos com textura de lombadas, alguns inclinados, e há caixas no topo."""
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder(name or "bookcase")
    m.box(0, 0.0, 0, width, depth, 0.05, "wood_dark")
    m.box(-width / 2 + 0.02, 0, 0.05, 0.04, depth, height - 0.05, "wood_mid")
    m.box(width / 2 - 0.02, 0, 0.05, 0.04, depth, height - 0.05, "wood_mid")
    m.box(0, -depth / 2 + 0.01, 0.05, width, 0.02, height - 0.05, "wood_dark")
    m.box(0, 0.005, height, width + 0.03, depth + 0.02, 0.03, "wood_dark")
    gap = (height - 0.08) / shelves
    for level in range(shelves):
        shelf_z = 0.05 + level * gap
        if level:
            m.box(0, 0, shelf_z, width - 0.08, depth - 0.03, 0.025, "wood_mid")
        cursor = -width / 2 + 0.06
        book_h = gap - 0.09
        while cursor < width / 2 - 0.1:
            run = min(ctx.rng.uniform(0.18, 0.45), width / 2 - 0.06 - cursor)
            if ctx.rng.random() < fill and run > 0.05:
                parts.book_row(m, cursor, cursor + run, -0.02, shelf_z + 0.025, depth - 0.1,
                               book_h * ctx.rng.uniform(0.75, 1.0))
            elif run > 0.1:
                parts.lean_book(m, cursor + 0.04, -0.03, shelf_z + 0.025, 0.04, book_h * 0.9, 0.2, "fabric_red", 12)
            cursor += run + ctx.rng.uniform(0.02, 0.1)
    m.box(-width / 4, 0, height + 0.03, 0.38, 0.24, 0.24, "cardboard")
    return place(ctx, m, room, "bookcase", x, y, yaw, z, name=name)


def make_filing_cabinet(ctx, room, wall, along, *, height=0.78, z=None):
    """Arquivo de aço de duas gavetas."""
    width, depth = 0.46, 0.6
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("filing_cabinet")
    m.box(0, 0, 0, width, depth, height, "steel_dark", mats={"front": "metal"})
    for row in range(2):
        drawer_z = 0.04 + row * (height - 0.06) / 2
        m.box(0, depth / 2 + 0.006, drawer_z, width - 0.04, 0.014, (height - 0.1) / 2, "metal")
        m.box(0, depth / 2 + 0.02, drawer_z + (height - 0.1) / 4 - 0.01, 0.16, 0.02, 0.02, "steel_dark")
        m.box(0, depth / 2 + 0.016, drawer_z + (height - 0.1) / 2 - 0.05, 0.10, 0.004, 0.035, "paper_white")
    return place(ctx, m, room, "filing_cabinet", x, y, yaw, z)


def make_globe(ctx, room, x, y, *, z=None):
    """Globo terrestre em pedestal, com o eixo inclinado como sempre."""
    m = MeshBuilder("globe")
    m.cylinder(0, 0, 0, 0.16, 0.03, "wood_dark", seg=8, r_top=0.12)
    m.cylinder(0, 0, 0.03, 0.022, 0.55, "wood_dark", seg=6)
    m.cylinder(0, 0, 0.58, 0.07, 0.02, "brass", seg=8)
    with m.at(0, 0, 0.78, rx=-23):
        m.sphere(0, 0, 0, 0.17, "globe", seg=12, rings=8)
        m.tube((0, 0, -0.2), (0, 0, 0.2), 0.008, "brass", seg=4)
    return place(ctx, m, room, "globe", x, y, 0.0, z)
