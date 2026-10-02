"""Peças pequenas reutilizadas pelos móveis: molduras, abajures, louça, livros, pelúcias.

Todas desenham dentro de um `MeshBuilder` já em andamento, nas coordenadas locais do móvel
(ou do bloco `with builder.at(...)` em que forem chamadas).
"""
import math
import random

from . import bookcase
from . import furniture_forms as forms


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


FRAME_PROFILE = ((0.0, 0.0), (0.0, 0.34), (0.22, 0.46), (0.30, 1.0), (0.72, 1.0), (0.84, 0.72), (1.0, 0.55), (1.0, 0.0))


def picture(m, cx, cy, cz, width, height, art_mat, facing="front", frame_mat="wood_dark", border=0.035, depth=0.03):
    """Quadro pendurado: arte atrás de uma moldura de perfil em degraus, com esquadria a 45 graus.

    (cx, cy, cz) é o centro no plano da parede; `depth` é a espessura total; `facing` para onde a frente aponta.
    """
    turn = {"front": 0, "right": -90, "back": 180, "left": 90}[facing]
    with m.at(cx, cy, cz, rz=turn):
        m.panel(0, -depth / 2 + depth * 0.30, 0, width, height, art_mat, "front")
        profile = [(border * u, -depth / 2 + depth * v) for u, v in FRAME_PROFILE]
        forms.mitred_frame(m, 0, 0, 0, width, height, profile, frame_mat)
        m.panel(0, -depth / 2 + 0.001, 0, width + 2 * border, height + 2 * border, "wood_dark", "back")


def table_lamp(m, cx, cy, z0, height, shade_mat="lampshade_lit", base_mat="brass", shade=0.32):
    """Abajur de mesa: pé torneado em balaústre, soquete e cúpula plissada em tronco de cone."""
    scale = height / 0.45
    m.lathe([(0.07, 0.0), (0.072, 0.012), (0.045, 0.03), (0.032, 0.06), (0.058, 0.12 * scale), (0.066, 0.16 * scale),
             (0.05, 0.21 * scale), (0.022, 0.26 * scale), (0.020, 0.31 * scale), (0.028, 0.325 * scale),
             (0.012, 0.335 * scale)], cx, cy, z0, base_mat, seg=forms.seg(16), smooth=True)
    bottom, top, shade_h = shade / 2, shade * 0.31, height * 0.46
    z_bottom = z0 + height * 0.54
    pleats = 36
    rings = []
    for z, radius in ((z_bottom, bottom), (z_bottom + shade_h, top)):
        rings.append([(cx + (radius * (1 + 0.025 * (-1) ** i)) * math.cos(2 * math.pi * i / pleats),
                       cy + (radius * (1 + 0.025 * (-1) ** i)) * math.sin(2 * math.pi * i / pleats), z) for i in range(pleats)])
    m.loft(rings, shade_mat, False, False, True, orient=False)
    m.cylinder(cx, cy, z_bottom + shade_h - 0.002, 0.012, 0.014, base_mat, seg=forms.seg(10), smooth=True)


def book_row(m, x0, x1, y, z0, depth, height, spine_mat="book_spines"):
    """Fileira de livros individuais de x0 a x1 sobre uma prateleira em z0 (a altura é o vão disponível)."""
    rng = random.Random(f"book_row:{x0:.3f}:{x1:.3f}:{z0:.3f}")
    bookcase.fill_shelf(m, rng, x0, x1, y, z0, height, depth, density=1.0)


def lean_book(m, cx, cy, z0, width, height, depth, mat, lean_deg=14):
    """Livro em pé inclinado, para quebrar a linha reta das prateleiras."""
    rng = random.Random(f"lean_book:{cx:.3f}:{z0:.3f}")
    bookcase.book(m, cx, cy, z0, width, depth, height, rng, lean=lean_deg)


def plate(m, cx, cy, z0, radius=0.12, mat="ceramic_cream", food=None):
    """Prato raso torneado: pé, fundo plano, aba larga com borda enrolada; `food` acrescenta restos secos."""
    r = radius
    m.lathe([(0.0, 0.0), (0.56 * r, 0.0), (0.60 * r, 0.004), (0.92 * r, 0.014), (r, 0.0185), (0.985 * r, 0.0205),
             (0.93 * r, 0.0185), (0.80 * r, 0.0115), (0.58 * r, 0.0062), (0.0, 0.0062)], cx, cy, z0, mat,
            seg=forms.seg(24), smooth=True)
    if food:
        m.lathe([(0.0, 0.0), (0.42 * r, 0.0), (0.40 * r, 0.006), (0.25 * r, 0.011), (0.0, 0.012)], cx, cy, z0 + 0.0062, food,
                seg=forms.seg(12), smooth=True)


def mug(m, cx, cy, z0, radius=0.04, height=0.09, mat="ceramic_cream", handle_dir=1, coffee=False):
    """Caneca oca com borda enrolada e alça em C; `coffee=True` deixa um café frio, com película, até o meio."""
    r, h = radius, height
    m.lathe([(0.0, 0.0), (0.82 * r, 0.0), (0.88 * r, 0.004), (r, 0.12 * h), (r * 1.03, 0.95 * h), (r * 1.04, h),
             (r * 0.93, h), (r * 0.90, 0.96 * h), (r * 0.88, 0.12 * h), (0.0, 0.10 * h)], cx, cy, z0, mat,
            seg=forms.seg(18), smooth=True)
    for point_a, point_b in _handle_segments(cx, cy, z0, r, h, handle_dir):
        m.tube(point_a, point_b, 0.0055, mat, seg=6, smooth=True)
    if coffee:
        m.cylinder(cx, cy, z0 + h * 0.62, r * 0.89, 0.002, "coffee_cold", seg=forms.seg(18))


def _handle_segments(cx, cy, z0, r, h, direction):
    """Alça em C: cinco trechos de arco entre o corpo e o lado."""
    points = []
    for step in range(6):
        angle = math.radians(-70 + 140 * step / 5)
        points.append((cx + direction * (r * 0.98 + 0.026 * math.cos(angle)), cy, z0 + h * 0.52 + 0.30 * h * math.sin(angle)))
    return list(zip(points, points[1:]))


def bottle(m, cx, cy, z0, radius, height, mat, cap_mat="black"):
    """Garrafa de vidro: base chanfrada, corpo, ombro, gargalo com lábio e tampa."""
    r, h = radius, height
    m.lathe([(0.0, 0.0), (0.84 * r, 0.0), (r, 0.02 * h), (r, 0.52 * h), (0.86 * r, 0.64 * h), (0.40 * r, 0.76 * h),
             (0.30 * r, 0.80 * h), (0.30 * r, 0.93 * h), (0.38 * r, 0.945 * h), (0.38 * r, 0.965 * h),
             (0.0, 0.965 * h)], cx, cy, z0, mat, seg=forms.seg(16), smooth=True)
    m.cylinder(cx, cy, z0 + 0.945 * h, 0.40 * r, 0.06 * h, cap_mat, seg=forms.seg(12), smooth=True)


def candle(m, cx, cy, z0, height=0.2):
    """Castiçal de latão com vela de cera apagada: pavio queimado e pingos secos."""
    m.lathe([(0.0, 0.0), (0.05, 0.0), (0.05, 0.008), (0.02, 0.016), (0.014, 0.03), (0.02, 0.036), (0.028, 0.045),
             (0.0, 0.045)], cx, cy, z0, "brass_aged", seg=forms.seg(14), smooth=True)
    m.cylinder(cx, cy, z0 + 0.045, 0.0165, height, "candle", seg=forms.seg(12), r_top=0.0155, smooth=True)
    m.cylinder(cx, cy, z0 + 0.045 + height, 0.0016, 0.014, "black", seg=5)
    m.sphere(cx + 0.015, cy, z0 + 0.045 + height * 0.85, 0.0045, "candle", seg=6, rings=4)


def paper_sheet(m, cx, cy, z0, width, depth, mat, yaw=0.0, thickness=0.002):
    """Folha solta sobre uma superfície, com giro em Z."""
    with m.at(cx, cy, z0, rz=math.degrees(yaw)):
        m.box(0, 0, 0, width, depth, thickness, mat)


def handle_bar(m, cx, cy, z, width, mat="brass", outward=1.0):
    """Puxador horizontal simples numa porta ou gaveta voltada para +Y (outward=1) ou -Y."""
    m.box(cx, cy + outward * 0.015, z, width, 0.02, 0.014, mat)


def knob(m, cx, cy, z, mat="brass", outward=1.0):
    forms.round_knob(m, cx, cy, z, 0.016, mat, outward)


def drawer_stack(m, cx, front_y, z0, width, height, rows, mat, handle_mat="brass", gap=0.012, outward=1.0):
    """Frentes de gaveta empilhadas, cada uma com almofada em relevo e puxador de alça."""
    row_h = (height - gap * (rows + 1)) / rows
    for row in range(rows):
        z = z0 + gap + row * (row_h + gap)
        m.box(cx, front_y, z, width - 2 * gap, 0.018, row_h, mat)
        with m.at(cx, front_y + outward * 0.009, z + row_h / 2, rx=-90 * outward):
            m.frustum(0, 0, 0, width - 0.09, row_h - 0.05, width - 0.11, row_h - 0.07, 0.005, mat)
        forms.bail_pull(m, cx, front_y + outward * 0.014, z + row_h / 2 + 0.006, min(0.09, width * 0.28), handle_mat,
                        facing=outward)


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
