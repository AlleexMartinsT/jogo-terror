"""Escritório de cima: onde Dan pesquisa a rota. Escrivaninha, cadeira giratória caída, estante de livros, arquivo.

A escrivaninha mantém o tampo a 0,76 m e o caderno de 2,2 cm sob o mapa (Item_MAP); o arquivo de aço mantém o
topo a 0,78 m, onde fica a receita (Item_NOTE_6). Tudo o mais é acumulação: papéis do seguro e da polícia, café
frio, caixas de arquivo, recortes e um mapa na parede.
"""
import math

from .. import craft
from . import small_quartos as small
from . import woodwork_quartos as joinery
from .assembly_quartos import CLOTH, HERO_WOOD, METAL, WOOD, Assembly, segments
from .decor_quartos import wall_spot
from .placement import against_wall, flush_center, floor_z, place

OAK, OAK_V = joinery.wood_pair("up_oak")
DESK_TOP = 0.76
BOOK_FINISH = craft.Finish(bevel=0.0, smooth_angle=40.0)     # 140 livros: sem chanfro, a quina já é pequena


# ---------------------------------------------------------------------------
# Escrivaninha
# ---------------------------------------------------------------------------
def make_desk(ctx, room, x, y, yaw, *, width=1.4, depth=0.65, anchor=None, name=None, z=None):
    """Escrivaninha de carvalho com gavetas à direita, painel frontal e tampo de 4 cm com a borda gasta."""
    cy = flush_center(room, x, y, yaw, depth)
    desk = Assembly(name or "study_desk")
    wood = desk.part(HERO_WOOD)
    pedestal = 0.46
    with wood.at(0, cy, 0):
        wood.box(0, 0.01, 0.72, width + 0.05, depth + 0.03, 0.04, OAK)
        wood.box(width / 2 - pedestal / 2 - 0.01, 0, 0.0, pedestal, depth - 0.04, 0.72, OAK_V)
        for index, z0 in enumerate((0.50, 0.28, 0.04)):
            joinery.framed_panel(wood, width / 2 - pedestal / 2 - 0.01, depth / 2 - 0.04, z0, pedestal - 0.04, 0.2, OAK, OAK,
                                 depth=0.022, frame=0.026, frame_mat_v=OAK_V)
            joinery.pull(wood, width / 2 - pedestal / 2 - 0.01, depth / 2 - 0.018, z0 + 0.1, 0.11, "brass")
        wood.box(-width / 2 + 0.03, 0, 0.0, 0.05, depth - 0.04, 0.72, OAK_V)
        wood.box(-0.12, -depth / 2 + 0.04, 0.22, width - pedestal - 0.1, 0.02, 0.50, OAK)
        wood.box(-0.12, -0.05, 0.62, width - pedestal - 0.1, depth - 0.12, 0.03, OAK)
        for sx in (-width / 2 + 0.03, width / 2 - 0.03):
            wood.box(sx, 0, 0.0, 0.06, depth - 0.02, 0.05, OAK)
    return place(ctx, desk, room, "desk", x, y, yaw, z, name=name, anchor=anchor)


def make_notebook(ctx, room, x, y, z, yaw=0.0):
    """Caderno espiral grosso, capa azul, pautado e riscado; a espessura (2,2 cm) sustenta o mapa dobrado."""
    book = Assembly("notebook")
    m = book.part(craft.Finish(bevel=0.002, bevel_segments=1, smooth_angle=45.0, bevel_angle=45.0), builder_class=small.UvBuilder)
    m.soft_box(0, 0, 0, 0.23, 0.31, 0.02, "up_cloth_blue", radius=0.01, edge=0.004)
    m.box(0.004, 0, 0.02, 0.21, 0.29, 0.002, "up_paper_notes")
    m.panel(0.004, 0, 0.0221, 0.21, 0.29, "up_paper_notes", "top")
    for index in range(9):
        m.torus(-0.115, -0.125 + index * 0.031, 0.0105, 0.009, 0.0014, "chrome", seg=10, seg_minor=4, rx=0, ry=90)
    return place(ctx, book, room, "notebook", x, y, yaw, z, mode="decor")


def make_papers(ctx, room, x, y, z, count=6, spread=0.22, *, textures=("up_paper_policy", "up_paper_report", "up_paper_notes"),
                name=None):
    """Folhas soltas e em pilha torta (apólice, boletim, anotações), cada uma girada e com borda levemente curva."""
    pile = Assembly(name or "papers")
    m = pile.part(CLOTH)
    for index in range(count):
        offset = (ctx.rng.uniform(-spread, spread), ctx.rng.uniform(-spread, spread) * 0.7)
        with m.at(offset[0], offset[1], index * 0.0024, rz=math.degrees(ctx.rng.uniform(0, math.pi))):
            m.box(0, 0, 0, 0.21, 0.297, 0.0016, "up_paper_blank", skip=("top",))
            m.panel(0, 0, 0.0016, 0.21, 0.297, textures[index % len(textures)], "top")
    return place(ctx, pile, room, "papers", x, y, 0.0, z, mode="decor")


def make_cold_coffee(ctx, room, x, y, z):
    """Caneca esmaltada com café frio e película, e o anel marrom que ela deixou no tampo."""
    cup = Assembly("coffee_cup")
    m = cup.part(craft.Finish(bevel=0.002, smooth_angle=55.0, bevel_angle=45.0))
    m.lathe([(0.032, 0.0), (0.038, 0.004), (0.043, 0.09), (0.045, 0.098)], 0, 0, 0.0, "up_ceramic", seg=segments(22), smooth=True, cap_top=False)
    m.cylinder(0, 0, 0.0, 0.032, 0.003, "up_ceramic", seg=segments(16))
    m.cylinder(0, 0, 0.074, 0.041, 0.002, "up_water", seg=segments(20))
    m.torus(0.052, 0, 0.05, 0.026, 0.0045, "up_ceramic", seg=segments(14), seg_minor=5, rx=90)
    m.panel(0.052, 0.0, 0.0006, 0.16, 0.16, "up_stain_ring", "top")
    return place(ctx, cup, room, "cup", x, y, ctx.rng.uniform(0, math.tau), z, mode="decor")


def make_desk_lamp(ctx, room, x, y, z, yaw=0.0, *, lit=True):
    """Luminária articulada de metal: base redonda, dois braços com mola e cúpula cônica de lâmina."""
    lamp = Assembly("desk_lamp")
    m = lamp.part(METAL)
    m.lathe([(0.0, 0.0), (0.09, 0.0), (0.09, 0.012), (0.045, 0.026), (0.02, 0.04)], 0, 0, 0, "up_steel", seg=segments(24), smooth=True)
    for p0, p1 in (((0, 0, 0.04), (0.05, 0.03, 0.30)), ((0.05, 0.03, 0.30), (-0.05, 0.16, 0.38))):
        m.tube(p0, p1, 0.007, "up_steel", seg=segments(10), smooth=True)
    m.tube((0.0, 0.0, 0.08), (0.05, 0.03, 0.27), 0.002, "chrome", seg=5)
    for joint in ((0, 0, 0.04), (0.05, 0.03, 0.30), (-0.05, 0.16, 0.38)):
        m.sphere(*joint, 0.012, "up_steel", seg=10, rings=6)
    with m.at(-0.06, 0.17, 0.36, rx=-28):
        m.lathe([(0.03, 0.0), (0.05, -0.04), (0.10, -0.10), (0.103, -0.104)], 0, 0, 0.0, "lampshade_lit" if lit else "up_steel",
                seg=segments(24), smooth=True, cap_bottom=False, cap_top=False)
        m.sphere(0, 0, -0.06, 0.022, "lens_glow", seg=10, rings=6)
    return place(ctx, lamp, room, "desk_lamp", x, y, yaw, z, mode="decor")


# ---------------------------------------------------------------------------
# Cadeira giratória (caída)
# ---------------------------------------------------------------------------
def _swivel_chair(m, leather):
    for index in range(5):
        angle = math.radians(72 * index + 18)
        tip = (0.30 * math.cos(angle), 0.30 * math.sin(angle))
        m.tube((0, 0, 0.115), (tip[0], tip[1], 0.06), 0.021, "up_plastic_black", seg=segments(10), r_end=0.015, smooth=True)
        m.cylinder(tip[0], tip[1], 0.0, 0.022, 0.05, "up_plastic_black", seg=segments(10))
        with m.at(tip[0], tip[1], 0.025, rz=math.degrees(angle) + 90, ry=90):
            m.cylinder(0, 0, -0.018, 0.024, 0.012, "up_rubber", seg=segments(12))
            m.cylinder(0, 0, 0.006, 0.024, 0.012, "up_rubber", seg=segments(12))
    m.cylinder(0, 0, 0.10, 0.034, 0.28, "up_plastic_black", seg=segments(14))
    m.cylinder(0, 0, 0.36, 0.02, 0.07, "chrome", seg=segments(12))
    m.soft_box(0, 0, 0.42, 0.20, 0.20, 0.03, "up_plastic_black", radius=0.03, edge=0.01)
    m.soft_box(0, 0.02, 0.45, 0.52, 0.50, 0.08, leather, radius=0.07, edge=0.03, corner_points=4)
    with m.at(0, -0.22, 0.50, rx=10):
        m.soft_box(0, 0, 0, 0.48, 0.10, 0.54, leather, radius=0.06, edge=0.03, corner_points=4)
        m.soft_box(0, 0.05, 0.12, 0.30, 0.04, 0.16, leather, radius=0.02, edge=0.014)
    m.box(0, -0.2, 0.46, 0.08, 0.06, 0.14, "up_plastic_black")
    for side in (-1, 1):
        m.tube((side * 0.2, -0.12, 0.50), (side * 0.27, -0.10, 0.64), 0.012, "up_plastic_black", seg=8)
        m.tube((side * 0.27, -0.10, 0.64), (side * 0.27, 0.05, 0.66), 0.012, "up_plastic_black", seg=8)
        m.soft_box(side * 0.27, -0.02, 0.655, 0.07, 0.26, 0.032, "up_plastic_black", radius=0.02, edge=0.01)


def make_swivel_chair(ctx, room, x, y, yaw, *, fallen=True, leather="up_leather", name=None):
    """Cadeira de escritório de cinco pés com rodízios, assento e encosto de couro, braços; caída de lado."""
    chair = Assembly(name or "chair_office")
    body = chair.part(craft.Finish(bevel=0.003, bevel_segments=2, smooth_angle=50.0, bevel_angle=45.0))
    with body.at(0, 0, 0, rx=96 if fallen else 0, rz=12 if fallen else 0):
        _swivel_chair(body, leather)
    lowest = chair.bounds()[0][2]
    return place(ctx, chair, room, "chair_office", x, y, yaw, floor_z(room) - lowest if fallen else None, name=name)


# ---------------------------------------------------------------------------
# Estante com livros individuais
# ---------------------------------------------------------------------------
def _fill_shelf(books, rng, x0, x1, z0, depth, height, fill):
    """Enche uma prateleira com livros de espessuras e alturas variadas, alguns inclinados, uma pilha deitada."""
    cursor = x0
    while cursor < x1 - 0.05:
        if rng.random() > fill:
            cursor += rng.uniform(0.06, 0.18)
            continue
        if rng.random() < 0.10 and x1 - cursor > 0.3:
            for level in range(rng.randint(2, 4)):
                small.book_flat(books, cursor + 0.14, -0.01, z0 + level * 0.034, rng.uniform(0.024, 0.04), depth - 0.06,
                                rng.uniform(0.18, 0.26), rng.randrange(8), yaw=rng.uniform(-9, 9))
            cursor += 0.30
            continue
        thickness, tall = rng.uniform(0.018, 0.05), height * rng.uniform(0.62, 0.94)
        style = rng.randrange(8)
        lean = rng.uniform(5, 14) if rng.random() < 0.07 else 0.0
        with books.at(cursor + thickness / 2, 0.0, z0, ry=-lean):
            small.book(books, 0.0, -0.01, 0.0, thickness, depth - 0.06, tall, style)
        cursor += thickness + (0.04 if lean else 0.0) + 0.001


def make_bookcase(ctx, room, wall, along, *, width=1.5, height=1.9, depth=0.32, shelves=5, fill=0.88, z=None, name=None):
    """Estante de nogueira com cinco prateleiras de livros individuais, uma pilha deitada, caixas e um relógio de mesa parado."""
    x, y, yaw = against_wall(room, wall, along, depth)
    case = Assembly(name or "bookcase")
    wood = case.part(HERO_WOOD)
    walnut, walnut_v = joinery.wood_pair("up_walnut")
    for sx in (-1, 1):
        wood.box(sx * (width / 2 - 0.02), 0, 0.05, 0.04, depth, height - 0.05, walnut_v)
    wood.box(0, 0, 0.0, width, depth, 0.06, walnut)
    wood.box(0, -depth / 2 + 0.01, 0.06, width - 0.04, 0.02, height - 0.06, "up_paint_white")
    wood.box(0, 0.01, height, width + 0.04, depth + 0.03, 0.035, walnut)
    wood.box(0, 0.0, height - 0.04, width - 0.04, 0.03, 0.04, walnut)
    gap = (height - 0.08) / shelves
    books = case.part(BOOK_FINISH, builder_class=small.UvBuilder)
    for level in range(shelves):
        shelf_z = 0.06 + level * gap
        if level:
            wood.box(0, 0, shelf_z - 0.012, width - 0.08, depth - 0.02, 0.024, walnut)
        _fill_shelf(books, ctx.rng, -width / 2 + 0.06, width / 2 - 0.06, shelf_z + 0.012, depth, gap - 0.05, fill)
    boxes = case.part(WOOD)
    boxes.box(-width / 4, 0, height + 0.035, 0.38, 0.24, 0.24, "cardboard")
    return place(ctx, case, room, "bookcase", x, y, yaw, z, name=name)


# ---------------------------------------------------------------------------
# Arquivo de aço
# ---------------------------------------------------------------------------
def make_filing_cabinet(ctx, room, wall, along, *, height=0.78, z=None):
    """Arquivo de aço cinza-esverdeado de duas gavetas: frente dobrada, puxador de chapa, porta-etiqueta e fechadura."""
    width, depth = 0.46, 0.6
    x, y, yaw = against_wall(room, wall, along, depth)
    cabinet = Assembly("filing_cabinet")
    steel = cabinet.part(craft.Finish(bevel=0.004, bevel_segments=2, bevel_angle=45.0, smooth_angle=45.0))
    steel.box(0, 0, 0.03, width, depth, height - 0.03, "up_steel")
    steel.box(0, 0, 0.0, width - 0.04, depth - 0.04, 0.03, "up_steel")
    drawer_h = (height - 0.1) / 2
    for row in range(2):
        z0 = 0.045 + row * (drawer_h + 0.012)
        steel.box(0, depth / 2 + 0.008, z0, width - 0.03, 0.016, drawer_h, "up_steel")
        steel.box(0, depth / 2 + 0.024, z0 + drawer_h * 0.62, 0.18, 0.024, 0.022, "up_steel")
        steel.box(0, depth / 2 + 0.025, z0 + drawer_h * 0.62 - 0.001, 0.15, 0.02, 0.014, "up_plastic_black")
        steel.box(0, depth / 2 + 0.017, z0 + drawer_h * 0.84, 0.11, 0.004, 0.042, "up_paper_blank")
    steel.cylinder(width / 2 - 0.05, depth / 2 + 0.017, height - 0.05, 0.007, 0.004, "chrome", seg=10)
    return place(ctx, cabinet, room, "filing_cabinet", x, y, yaw, z)


def make_archive_boxes(ctx, room, x, y, yaw):
    """Duas caixas de arquivo empilhadas, a de cima com a tampa torta e papéis saindo; etiquetas SEGURO e POLICIA."""
    stack = Assembly("archive_boxes")
    m = stack.part(craft.Finish(bevel=0.003, bevel_segments=2, smooth_angle=45.0, bevel_angle=45.0), builder_class=small.UvBuilder)
    for level, (label, turn) in enumerate((("up_paper_policy", 0), ("up_paper_report", 14))):
        with m.at(0.0, 0.0, level * 0.26, rz=turn):
            m.box(0, 0, 0.0, 0.40, 0.33, 0.26, "cardboard")
            m.panel(0, 0.1655, 0.13, 0.20, 0.12, label, "front")
            m.box(0, 0.168, 0.20, 0.12, 0.004, 0.07, "up_plastic_black")
    with m.at(0.02, 0.0, 0.52, rz=-10, rx=6):
        m.box(0, 0, 0.0, 0.42, 0.35, 0.03, "cardboard")
    for index in range(3):
        with m.at(0.0, 0.0, 0.50 + index * 0.003, rz=index * 25 - 20):
            m.box(0.02, 0.03, 0.0, 0.21, 0.297, 0.0016, "up_paper_blank")
    return place(ctx, stack, room, "boxes", x, y, yaw)


# ---------------------------------------------------------------------------
# Globo
# ---------------------------------------------------------------------------
def make_globe(ctx, room, x, y, *, z=None):
    """Globo em pedestal torneado, meridiano de latão e o eixo inclinado em 23 graus como sempre."""
    globe = Assembly("globe")
    wood = globe.part(WOOD)
    walnut, walnut_v = joinery.wood_pair("up_walnut")
    wood.lathe([(0.0, 0.0), (0.17, 0.0), (0.17, 0.02), (0.12, 0.04), (0.04, 0.10), (0.03, 0.40), (0.05, 0.44), (0.03, 0.47),
                (0.0, 0.47)], 0, 0, 0, walnut_v, seg=segments(22), smooth=True)
    wood.tube((0, 0, 0.46), (0, 0, 0.61), 0.009, "brass", seg=8)
    sphere = globe.part(craft.Finish(bevel=0.0, smooth_angle=180.0))
    with sphere.at(0, 0, 0.82, rx=-23):
        sphere.sphere(0, 0, 0, 0.20, "up_globe", seg=segments(32), rings=18)
        sphere.torus(0, 0, 0, 0.212, 0.0045, "brass", seg=segments(32), seg_minor=6, rx=90)
        sphere.tube((0, 0, -0.235), (0, 0, 0.235), 0.006, "brass", seg=8)
    return place(ctx, globe, room, "globe", x, y, 0.0, z)


# ---------------------------------------------------------------------------
# Mapa na parede, com alfinetes, fio vermelho e recortes
# ---------------------------------------------------------------------------
def make_wall_map(ctx, room, wall, along, z, width=1.1):
    """Mapa da cidade na parede: moldura fina, alfinetes vermelhos nos pontos riscados, fio ligando os recortes presos em volta."""
    x, y, yaw = wall_spot(room, wall, along)
    height = width * 0.75
    unit = Assembly("wall_map")
    wood = unit.part(WOOD, builder_class=small.UvBuilder)
    wood.panel(0, 0.006, 0, width, height, "up_wall_map", "front")
    for sign in (-1, 1):
        wood.box(sign * (width + 0.02) / 2, 0.008, -height / 2 - 0.01, 0.02, 0.016, height + 0.02, "up_plastic_black")
        wood.box(0, 0.008, sign * (height + 0.02) / 2 - 0.01, width, 0.016, 0.02, "up_plastic_black")
    pins = [(-0.18, -0.10), (0.06, -0.01), (0.22, 0.14), (-0.30, 0.17)]
    for px, pz in pins:
        wood.sphere(px, 0.016, pz, 0.008, "up_paint_red", seg=8, rings=5)
    clippings = [(-0.70, 0.22, 8), (0.72, 0.12, -6), (-0.66, -0.20, -4), (0.70, -0.24, 10)]
    for cx, cz, tilt in clippings:
        with wood.at(cx, 0.004, cz, ry=tilt):
            wood.panel(0, 0, 0, 0.17, 0.17, "up_newsprint", "front")
            wood.sphere(0, 0.004, 0.07, 0.007, "up_paint_red", seg=6, rings=4)
    string = unit.part(METAL)
    chain = [(clippings[0][0], 0.07 + clippings[0][1]), *[(px, pz) for px, pz in pins], (clippings[1][0], 0.07 + clippings[1][1])]
    for (ax, az), (bx, bz) in zip(chain, chain[1:]):
        string.tube((ax, 0.02, az), (bx, 0.02, bz), 0.0012, "up_paint_red", seg=4)
    return place(ctx, unit, room, "picture", x, y, yaw, floor_z(room) + z, mode="wall", name="wall_map_study")
