"""Peças pequenas reutilizadas pelos móveis: molduras, abajures, louça, livros, pelúcias.

Todas desenham dentro de um `MeshBuilder` já em andamento, nas coordenadas locais do móvel
(ou do bloco `with builder.at(...)` em que forem chamadas).
"""
import math



def four_legs(m, x0, y0, x1, y1, height, thickness, mat, z0=0.0):
    """Quatro pernas quadradas nos cantos do retângulo (x0, y0)-(x1, y1)."""
    half = thickness / 2
    for cx in (x0 + half, x1 - half):
        for cy in (y0 + half, y1 - half):
            m.box(cx, cy, z0, thickness, thickness, height, mat)


def frame_bars(m, cx, cy, cz, width, height, border, depth, mat, facing="front"):
    """Moldura de quatro barras em torno de um vazio width x height, no plano de `facing`."""
    sx = 1 if facing in ("front", "back") else 0
    sy = 1 - sx

    def bar(ox, oz, w, h):
        px, py = cx + (ox if sx else 0.0), cy + (ox if sy else 0.0)
        m.box(px, py, cz + oz - h / 2, w if sx else depth, depth if sx else w, h, mat, skip=("bottom",))

    bar(0, height / 2 + border / 2, width + 2 * border, border)
    bar(0, -height / 2 - border / 2, width + 2 * border, border)
    bar(-width / 2 - border / 2, 0, border, height)
    bar(width / 2 + border / 2, 0, border, height)


def picture(m, cx, cy, cz, width, height, art_mat, facing="front", frame_mat="wood_dark", border=0.035, depth=0.03):
    """Quadro pendurado: arte dentro de moldura. (cx, cy, cz) é o centro no plano da parede."""
    offset = {"front": (0, depth / 2 - 0.004), "back": (0, -(depth / 2 - 0.004)),
              "right": (depth / 2 - 0.004, 0), "left": (-(depth / 2 - 0.004), 0)}[facing]
    m.panel(cx + offset[0], cy + offset[1], cz, width, height, art_mat, facing)
    frame_bars(m, cx, cy, cz, width, height, border, depth, frame_mat, facing)
    back_offset = (-offset[0], -offset[1])
    m.panel(cx + back_offset[0], cy + back_offset[1], cz, width + 2 * border, height + 2 * border,
            "wood_dark", {"front": "back", "back": "front", "right": "left", "left": "right"}[facing])


def table_lamp(m, cx, cy, z0, height, shade_mat="lampshade_lit", base_mat="brass", shade=0.32):
    """Abajur de mesa: pé torneado e cúpula em tronco."""
    m.lathe([(0.07, 0), (0.06, 0.01), (0.035, 0.06), (0.05, 0.13 * height / 0.45), (0.018, 0.3 * height / 0.45),
             (0.014, 0.42 * height / 0.45)], cx, cy, z0, base_mat, seg=8, smooth=False)
    m.frustum(cx, cy, z0 + height * 0.55, shade, shade, shade * 0.62, shade * 0.62, height * 0.45, shade_mat)


def book_row(m, x0, x1, y, z0, depth, height, spine_mat="book_spines"):
    """Fileira de livros como um bloco com a textura de lombadas na frente (barato e legível)."""
    m.box((x0 + x1) / 2, y, z0, x1 - x0, depth, height, "wood_dark", mats={"front": spine_mat}, uv=1.0)


def lean_book(m, cx, cy, z0, width, height, depth, mat, lean_deg=14):
    """Livro em pé inclinado, para quebrar a linha reta das prateleiras."""
    with m.at(cx, cy, z0, ry=lean_deg):
        m.box(0, 0, 0, width, depth, height, mat)


def plate(m, cx, cy, z0, radius=0.12, mat="ceramic_cream", food=None):
    """Prato raso; `food` acrescenta restos secos no centro."""
    m.cylinder(cx, cy, z0, radius * 0.62, 0.012, mat, seg=10, r_top=radius)
    if food:
        m.cylinder(cx, cy, z0 + 0.012, radius * 0.45, 0.006, food, seg=7, r_top=radius * 0.3)


def mug(m, cx, cy, z0, radius=0.04, height=0.09, mat="ceramic_cream", handle_dir=1):
    m.cylinder(cx, cy, z0, radius, height, mat, seg=8)
    m.box(cx + handle_dir * (radius + 0.012), cy, z0 + height * 0.25, 0.024, 0.014, height * 0.5, mat)


def bottle(m, cx, cy, z0, radius, height, mat, cap_mat="black"):
    m.lathe([(radius, 0), (radius, height * 0.55), (radius * 0.4, height * 0.8), (radius * 0.35, height)],
            cx, cy, z0, mat, seg=8, smooth=False)
    m.cylinder(cx, cy, z0 + height, radius * 0.4, height * 0.08, cap_mat, seg=6)


def candle(m, cx, cy, z0, height=0.2):
    m.cylinder(cx, cy, z0, 0.05, 0.02, "brass", seg=8, r_top=0.03)
    m.cylinder(cx, cy, z0 + 0.02, 0.018, height, "candle", seg=6)
    m.cylinder(cx, cy, z0 + 0.02 + height, 0.002, 0.012, "black", seg=3)


def paper_sheet(m, cx, cy, z0, width, depth, mat, yaw=0.0, thickness=0.002):
    """Folha solta sobre uma superfície, com giro em Z."""
    with m.at(cx, cy, z0, rz=math.degrees(yaw)):
        m.box(0, 0, 0, width, depth, thickness, mat)


def handle_bar(m, cx, cy, z, width, mat="brass", outward=1.0):
    """Puxador horizontal simples numa porta ou gaveta voltada para +Y (outward=1) ou -Y."""
    m.box(cx, cy + outward * 0.015, z, width, 0.02, 0.014, mat)


def knob(m, cx, cy, z, mat="brass", outward=1.0):
    with m.at(cx, cy, z, rx=-90 * outward):
        m.cylinder(0, 0, 0, 0.013, 0.022, mat, seg=6)


def drawer_stack(m, cx, front_y, z0, width, height, rows, mat, handle_mat="brass", gap=0.012, outward=1.0):
    """Frentes de gaveta empilhadas (uma caixa fina por gaveta) com puxador central."""
    row_h = (height - gap * (rows + 1)) / rows
    for row in range(rows):
        z = z0 + gap + row * (row_h + gap)
        m.box(cx, front_y, z, width - 2 * gap, 0.018, row_h, mat)
        handle_bar(m, cx, front_y + outward * 0.009, z + row_h / 2 - 0.007, min(0.12, width * 0.25), handle_mat, outward)


def soft_toy_body(m, cx, cy, z0, radius, mat, seg=8):
    """Corpo de pelúcia: pera achatada."""
    m.lathe([(0, 0), (radius * 0.75, radius * 0.15), (radius, radius * 0.7), (radius * 0.9, radius * 1.3),
             (radius * 0.55, radius * 1.75), (0, radius * 1.8)], cx, cy, z0, mat, seg=seg, smooth=True,
            cap_bottom=False, cap_top=False)


def rabbit(m, cx, cy, z0, scale=1.0, mat="plush_white", inner="plush_pink", sitting_yaw=0.0):
    """Coelho de pelúcia sentado (o coelhinho da Emma), com orelhas longas."""
    with m.at(cx, cy, z0, rz=math.degrees(sitting_yaw)):
        s = scale
        soft_toy_body(m, 0, 0, 0, 0.09 * s, mat)
        m.lathe([(0, 0), (0.06 * s, 0.03 * s), (0.065 * s, 0.075 * s), (0.04 * s, 0.12 * s), (0, 0.13 * s)],
                0, 0.02 * s, 0.14 * s, mat, seg=8, cap_bottom=False, cap_top=False)
        for side in (-1, 1):
            with m.at(side * 0.03 * s, 0.02 * s, 0.25 * s, rx=0, ry=side * 8):
                m.extrude([(-0.018 * s, 0), (0.018 * s, 0), (0.024 * s, 0.09 * s), (0.0, 0.16 * s), (-0.024 * s, 0.09 * s)],
                          "xz", -0.008 * s, 0.008 * s, mat)
                m.panel(0, 0.0085 * s, 0.08 * s, 0.024 * s, 0.11 * s, inner, "front")
        for side in (-1, 1):
            m.box(side * 0.024 * s, 0.075 * s, 0.205 * s, 0.014 * s, 0.01 * s, 0.014 * s, "black")
        m.cylinder(0, -0.09 * s, 0.05 * s, 0.03 * s, 0.05 * s, mat, seg=6)


def teddy(m, cx, cy, z0, scale=1.0, mat="plush_brown", yaw=0.0):
    """Urso de pelúcia sentado, com orelhas redondas e focinho."""
    with m.at(cx, cy, z0, rz=math.degrees(yaw)):
        s = scale
        soft_toy_body(m, 0, 0, 0, 0.11 * s, mat)
        m.lathe([(0, 0), (0.075 * s, 0.03 * s), (0.08 * s, 0.08 * s), (0.05 * s, 0.14 * s), (0, 0.15 * s)],
                0, 0.01 * s, 0.17 * s, mat, seg=8, cap_bottom=False, cap_top=False)
        for side in (-1, 1):
            m.cylinder(side * 0.06 * s, 0.0, 0.29 * s, 0.03 * s, 0.02 * s, mat, seg=6)
            m.box(side * 0.14 * s, 0.03 * s, 0.09 * s, 0.05 * s, 0.05 * s, 0.13 * s, mat)
            m.box(side * 0.08 * s, 0.05 * s, 0.0, 0.06 * s, 0.09 * s, 0.05 * s, mat)
        m.box(0, 0.075 * s, 0.215 * s, 0.05 * s, 0.03 * s, 0.035 * s, "plush_white")
        m.box(0, 0.09 * s, 0.225 * s, 0.014 * s, 0.01 * s, 0.01 * s, "black")


def clothes_heap(m, cx, cy, z0, rng, radius=0.2, height=0.14, palette=("coat_dark", "coat_beige", "plush_blue", "fabric_gray")):
    """Monte de roupa amassada: poucas caixas achatadas giradas ao acaso."""
    for _ in range(4):
        with m.at(cx + rng.uniform(-radius, radius) * 0.5, cy + rng.uniform(-radius, radius) * 0.5,
                  z0 + rng.uniform(0, height), rz=rng.uniform(0, 180)):
            m.soft_box(0, 0, 0, rng.uniform(0.2, 0.32), rng.uniform(0.16, 0.24), rng.uniform(0.05, 0.08),
                       rng.choice(palette), radius=0.04, edge=0.02)


def wicker_basket(m, cx, cy, z0, radius, height, mat="wood_mid"):
    """Cesto de vime: tronco com aro e fundo."""
    m.cylinder(cx, cy, z0, radius * 0.85, height, mat, seg=10, r_top=radius, caps=(True, False))
    m.torus(cx, cy, z0 + height, radius, 0.012, mat, seg=10, seg_minor=4)


def counter_top_with_basin(m, x0, x1, y0, y1, z, thickness, basin_cx, basin_cy, basin_w, basin_d, basin_depth,
                           top_mat, basin_mat="porcelain", bottom_mat=None):
    """Tampo de bancada com furo retangular: quatro lajes ao redor e a cuba (paredes e fundo) abaixo dele."""
    hx0, hx1 = basin_cx - basin_w / 2, basin_cx + basin_w / 2
    hy0, hy1 = basin_cy - basin_d / 2, basin_cy + basin_d / 2
    mid_y = (y0 + y1) / 2
    m.box((x0 + hx0) / 2, mid_y, z, hx0 - x0, y1 - y0, thickness, top_mat)
    m.box((hx1 + x1) / 2, mid_y, z, x1 - hx1, y1 - y0, thickness, top_mat)
    m.box(basin_cx, (y0 + hy0) / 2, z, basin_w, hy0 - y0, thickness, top_mat)
    m.box(basin_cx, (hy1 + y1) / 2, z, basin_w, y1 - hy1, thickness, top_mat)
    floor_z = z + thickness - basin_depth
    m.box(basin_cx, basin_cy, floor_z, basin_w, basin_d, basin_depth, basin_mat, skip=("top", "bottom"))
    m.panel(basin_cx, basin_cy, floor_z + 0.003, basin_w, basin_d, bottom_mat or basin_mat, "top")


def shoe_pair(m, cx, cy, z0, scale, mat, yaw=0.0, tall=False):
    """Par de sapatos lado a lado (cano alto se `tall`, como bota de chuva), virados para +Y."""
    s = scale
    with m.at(cx, cy, z0, rz=math.degrees(yaw)):
        for side in (-1, 1):
            with m.at(side * 0.065 * s, 0, 0, rz=side * 5):
                m.soft_box(0, 0, 0, 0.085 * s, 0.24 * s, 0.07 * s, mat, radius=0.03 * s, edge=0.015 * s)
                m.soft_box(0, -0.06 * s, 0.05 * s, 0.08 * s, 0.11 * s, (0.30 if tall else 0.09) * s, mat,
                           radius=0.03 * s, edge=0.012 * s)
                m.box(0, 0.0, 0.0, 0.09 * s, 0.25 * s, 0.012 * s, "rubber")


def dirty_dishes(m, rng, cx, cy, z0, count=4, radius=0.11):
    """Pilha torta de pratos com restos secos e um copo ao lado."""
    for i in range(count):
        plate(m, cx + rng.uniform(-0.02, 0.02), cy + rng.uniform(-0.02, 0.02), z0 + i * 0.016, radius,
              "ceramic_cream", food="food_dried" if i % 2 == 0 else None)
    mug(m, cx + radius + 0.06, cy - 0.03, z0, 0.035, 0.085, "ceramic_cream", handle_dir=1)
