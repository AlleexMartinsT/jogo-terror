"""Quarto da Emma: caminha de cabeceira recortada, estante de brinquedos, baú, casa de bonecas, escrivaninha.

Tudo arrumado e pequeno demais para o silêncio. Madeira pintada de creme e rosa, pelúcias de elipsoides,
brinquedos de pano e lata. A cama mantém a altura da coberta (0,44 m) onde repousa o desenho (Item_NOTE_2) e a
estante mantém o topo a 0,50 m, onde ficam as pilhas (Item_BATTERY_1).
"""
import math

from mathutils import Matrix

from .. import craft
from . import cloth_quartos as fabric
from . import plush_quartos as plush
from . import small_quartos as small
from . import woodwork_quartos as joinery
from .assembly_quartos import METAL, PAINTED, PLUSH, UPHOLSTERY, Assembly, segments
from .kit import MeshBuilder
from .placement import against_wall, flush_center, floor_z, place

CREAM, CREAM_V = joinery.wood_pair("up_paint_cream")
PINK, PINK_V = joinery.wood_pair("up_paint_pink")
KID_HEAD_Y, KID_FOOT_Y = -0.815, 0.83
MATTRESS_Z, MATTRESS_TOP = 0.28, 0.42     # a coberta assenta ~1,8 cm acima: 0,44 m, onde repousa o desenho (NOTE_2)


# ---------------------------------------------------------------------------
# Caminha
# ---------------------------------------------------------------------------
def _scalloped_profile(half_width, base_z, arches=3, rise=0.09, points=36):
    """Perfil (x, z) de uma cabeceira com o topo em ondas (três arcos), fundo reto."""
    top = []
    for i in range(points + 1):
        x = half_width - 2 * half_width * i / points
        phase = (half_width - x) / (2 * half_width) * arches
        top.append((x, base_z + 0.40 + rise * abs(math.sin(math.pi * phase))))
    return [(-half_width, base_z), (half_width, base_z)] + top


def _star(cx, cz, radius, points=5):
    return [(cx + (radius if k % 2 == 0 else radius * 0.45) * math.cos(-math.pi / 2 + k * math.pi / points),
             cz + (radius if k % 2 == 0 else radius * 0.45) * math.sin(-math.pi / 2 + k * math.pi / points))
            for k in range(2 * points)]


def _kid_bed_frame(m):
    for side in (-1, 1):
        m.box(side * 0.40, KID_HEAD_Y, 0, 0.05, 0.05, 0.64, CREAM_V)
        m.sphere(side * 0.40, KID_HEAD_Y, 0.67, 0.027, PINK, seg=12, rings=7)
        m.box(side * 0.40, KID_FOOT_Y, 0, 0.05, 0.05, 0.46, CREAM_V)
        m.sphere(side * 0.40, KID_FOOT_Y, 0.49, 0.026, PINK, seg=12, rings=7)
        m.box(side * 0.36, 0, 0.16, 0.04, KID_FOOT_Y - KID_HEAD_Y, 0.12, CREAM)
    m.extrude(_scalloped_profile(0.375, 0.20), "xz", KID_HEAD_Y - 0.016, KID_HEAD_Y + 0.016, CREAM)
    m.extrude(_star(0, 0.52, 0.11), "xz", KID_HEAD_Y + 0.016, KID_HEAD_Y + 0.024, PINK)
    m.box(0, KID_FOOT_Y, 0.16, 0.76, 0.04, 0.08, CREAM)
    m.box(0, KID_FOOT_Y, 0.42, 0.78, 0.045, 0.04, PINK)
    for index in range(9):
        m.cylinder(-0.32 + index * 0.08, KID_FOOT_Y, 0.24, 0.011, 0.18, CREAM_V, seg=segments(8))
    for index in range(max(1, int((KID_FOOT_Y - KID_HEAD_Y) / 0.12))):
        m.box(0, KID_HEAD_Y + 0.06 + index * 0.12, 0.26, 0.76, 0.07, 0.014, CREAM_V)
    guard = 0.435
    m.box(guard, 0.25, 0.50, 0.03, 0.90, 0.03, PINK)
    m.box(guard, 0.25, 0.30, 0.03, 0.90, 0.04, CREAM)
    for index in range(10):
        m.cylinder(guard, -0.17 + index * 0.093, 0.34, 0.010, 0.17, CREAM_V, seg=segments(8))
    for end in (-0.20, 0.70):
        m.box(guard, end, 0.28, 0.035, 0.035, 0.27, CREAM_V)


def _kid_bed_hold():
    hold = MeshBuilder("kid_bed_hold")
    hold.finish = None
    hold.box(0, 0, MATTRESS_Z, 0.80, 1.58, MATTRESS_TOP - MATTRESS_Z, "up_paint_cream")
    return hold


def make_kids_bed(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Caminha feita: coberta lisa de estrelas, travesseiro rosa e o coelho de pelúcia sentado nele."""
    cy = flush_center(room, x, y, yaw, 2 * 0.845)
    bed = Assembly("kids_bed")
    frame = bed.part(PAINTED)
    with frame.at(0, cy, 0):
        _kid_bed_frame(frame)
    mattress = bed.part(UPHOLSTERY)
    mattress.soft_box(0, cy, MATTRESS_Z, 0.80, 1.58, MATTRESS_TOP - MATTRESS_Z, "up_cloth_white", radius=0.04, edge=0.035)
    shift = Matrix.Translation((0, cy, 0))
    cover = fabric.settle_cloth(1.10, 1.06, (0.0, 0.25), MATTRESS_TOP + 0.08, [_kid_bed_hold()], "up_comforter", cell=0.045,
                                seed=ctx.seed + 41, thickness=0.012, subsurf=0, frames=45, floor=0.0,
                                fold=(-0.40, 0.40, None, None), limits=(-0.435, 0.435, None, None),
                                mass=0.3, stiffness=25.0, bending=30.0)
    bed.add_mesh(cover, "up_comforter", matrix=shift)
    pillow = fabric.pillow(0.50, 0.32, 0.10, "up_pillowcase", dent=0.018, lean=0.05, seed=ctx.seed + 42, uv_scale=1.6)
    bed.add_mesh(pillow, "up_pillowcase", matrix=shift @ Matrix.Translation((0.0, -0.58, MATTRESS_TOP + 0.002)))
    toys = bed.part(PLUSH)
    with toys.at(0, cy, 0):
        plush.rabbit(toys, 0.02, -0.60, 0.472, 1.0, yaw=math.radians(8))
    return place(ctx, bed, room, "kids_bed", x, y, yaw, z, name="kids_bed", anchor=anchor,
                 collision=[(-0.44, cy - 0.84, 0, 0.44, cy + 0.84, 0.40)])


# ---------------------------------------------------------------------------
# Estante baixa de brinquedos
# ---------------------------------------------------------------------------
def _toy_bin(m, cx, z0, material, width=0.34, depth=0.26, height=0.17):
    """Caixote de madeira pintada com os cantos reforçados e uma alça recortada."""
    m.box(cx, 0, z0, width, depth, 0.012, material)
    for sx in (-1, 1):
        m.box(cx + sx * (width / 2 - 0.006), 0, z0, 0.012, depth, height, material)
    for sy in (-1, 1):
        m.box(cx, sy * (depth / 2 - 0.006), z0, width, 0.012, height, material)
    m.box(cx, depth / 2 + 0.003, z0 + height * 0.5, 0.10, 0.006, 0.02, "up_paint_cream")


def make_toy_shelf(ctx, room, wall, along, *, width=1.05, depth=0.34, height=0.5):
    """Estante baixa de brinquedos: caixotes, pelúcias, boneca, caminhão e livros; o tampo (0,50 m) fica livre."""
    x, y, yaw = against_wall(room, wall, along, depth)
    shelf = Assembly("toy_shelf")
    body = shelf.part(PAINTED)
    body.box(0, 0, 0, width, depth, 0.03, CREAM)
    for sx in (-width / 2 + 0.015, width / 2 - 0.015, 0.0):
        body.box(sx, 0, 0.03, 0.03, depth, height - 0.03, CREAM_V)
    body.box(0, -depth / 2 + 0.01, 0.03, width, 0.02, height - 0.03, "up_paint_white")
    body.box(0, 0, 0.24, width, depth, 0.025, CREAM)
    body.box(0, 0.015, height - 0.025, width + 0.03, depth + 0.03, 0.025, PINK)
    body.box(0, depth / 2 - 0.004, 0.03, width - 0.06, 0.008, 0.012, PINK)
    _toy_bin(body, -0.25, 0.03, "up_paint_red")
    _toy_bin(body, 0.26, 0.03, "up_paint_blue")
    toys = shelf.part(PLUSH)
    plush.teddy(toys, -0.36, 0.0, 0.265, 0.62, "up_fur_yellow", yaw=math.radians(6))
    plush.toy_truck(toys, -0.14, 0.04, 0.265, yaw=math.radians(-20))
    plush.doll(toys, 0.10, 0.03, 0.265, 0.9, "up_cloth_blue", yaw=math.radians(-8))
    plush.rabbit(toys, 0.26, 0.02, 0.265, 0.62, "up_fur_gray", yaw=math.radians(-12))
    books = shelf.part(PAINTED, builder_class=small.UvBuilder)
    for index, (style, thickness, tall) in enumerate(((2, 0.022, 0.20), (5, 0.018, 0.18), (0, 0.025, 0.21), (7, 0.016, 0.17))):
        small.book(books, 0.37 + index * 0.027, 0.0, 0.265, thickness, 0.17, tall, style)
    return place(ctx, shelf, room, "toy_shelf", x, y, yaw, collision_top=height)


# ---------------------------------------------------------------------------
# Baú de brinquedos
# ---------------------------------------------------------------------------
def make_toy_chest(ctx, room, wall, along, *, z=None):
    """Baú rosa de tampa abaulada com cantoneiras de latão, alças de corda e a orelha de um urso presa na tampa."""
    width, depth, body_h = 0.76, 0.40, 0.30
    x, y, yaw = against_wall(room, wall, along, depth)
    chest = Assembly("toy_chest")
    wood = chest.part(PAINTED)
    wood.box(0, 0, 0.0, width, depth, 0.05, CREAM)
    wood.box(0, 0, 0.05, width - 0.02, depth - 0.02, body_h - 0.05, PINK)
    for sx in (-1, 1):
        wood.box(sx * (width / 2 - 0.045), depth / 2 - 0.004, 0.05, 0.09, 0.012, body_h - 0.05, CREAM_V)
    lid_profile = [(depth / 2 * math.cos(math.pi * i / 12), 0.075 * math.sin(math.pi * i / 12)) for i in range(13)]
    with wood.at(0, 0, body_h):
        wood.extrude(lid_profile, "yz", -width / 2 - 0.01, width / 2 + 0.01, PINK)
    metal = chest.part(METAL)
    for sx in (-1, 1):
        for sy in (-1, 1):
            metal.box(sx * (width / 2 - 0.012), sy * (depth / 2 - 0.012), body_h - 0.04, 0.026, 0.026, 0.05, "brass")
        metal.tube((sx * width / 2, -0.06, 0.20), (sx * (width / 2 + 0.022), 0.0, 0.17), 0.007, "up_cloth_beige", seg=6)
        metal.tube((sx * (width / 2 + 0.022), 0.0, 0.17), (sx * width / 2, 0.06, 0.20), 0.007, "up_cloth_beige", seg=6)
    metal.box(0, depth / 2 + 0.004, body_h - 0.03, 0.05, 0.012, 0.05, "brass")
    toys = chest.part(PLUSH)
    plush.teddy(toys, -0.17, 0.0, body_h + 0.04, 0.9, "up_fur_brown", yaw=math.radians(25))
    plush.ellipsoid(toys, 0.17, depth / 2 - 0.02, body_h + 0.01, 0.025, 0.018, 0.04, "up_fur_pink", turn=(20, 0, 10), seg=10,
                    rings=6)
    return place(ctx, chest, room, "toy_chest", x, y, yaw, z)


# ---------------------------------------------------------------------------
# Casa de bonecas
# ---------------------------------------------------------------------------
def _doll_house_rooms(m, width, depth):
    for level, z0 in enumerate((0.04, 0.30)):
        m.box(0, 0, z0 - 0.02, width - 0.04, depth - 0.02, 0.02, "up_oak")
        m.box(-width / 2 + 0.02 + (width - 0.04) * 0.55, 0, z0, 0.016, depth - 0.04, 0.24, CREAM)
    paper = ("up_paint_yellow", "up_paint_green", "up_paint_blue", "up_paint_red")
    for index, material in enumerate(paper):
        column, level = index % 2, index // 2
        cx = (-0.2 if column == 0 else 0.25)
        m.box(cx, -depth / 2 + 0.03, 0.04 + 0.26 * level, 0.36 if column == 0 else 0.34, 0.006, 0.24, material)


def _doll_house_furniture(m):
    m.soft_box(0.30, 0.02, 0.04, 0.17, 0.12, 0.05, "up_paint_pink", radius=0.01, edge=0.006)      # sofá
    m.box(-0.26, 0.04, 0.04, 0.12, 0.08, 0.05, "up_oak")                                           # mesa
    m.box(-0.12, 0.05, 0.04, 0.035, 0.035, 0.06, "up_oak")
    m.box(0.20, 0.04, 0.30, 0.18, 0.12, 0.035, "up_cloth_white")                                    # cama
    m.box(0.20, -0.02, 0.335, 0.16, 0.05, 0.02, "up_paint_pink")
    m.box(-0.22, 0.02, 0.30, 0.07, 0.07, 0.07, "up_paint_cream")
    for x_pos, material in ((-0.30, "up_cloth_red"), (-0.08, "up_cloth_blue")):
        m.cylinder(x_pos, 0.01, 0.04, 0.012, 0.045, material, seg=8, r_top=0.004)
        m.sphere(x_pos, 0.01, 0.10, 0.012, "up_cloth_beige", seg=8, rings=5)
    with m.at(0.02, 0.06, 0.04, rz=75):
        m.cylinder(0, 0, 0.0, 0.011, 0.04, "up_cloth_blue", seg=8, r_top=0.004)
        m.sphere(0, 0, 0.056, 0.011, "up_cloth_beige", seg=8, rings=5)


def make_doll_house(ctx, room, wall, along, *, z=None):
    """Casa de bonecas de dois andares, aberta na frente: papéis de parede, móveis, bonecos, telhado de telhas, chaminé."""
    width, depth = 0.9, 0.42
    x, y, yaw = against_wall(room, wall, along, depth)
    house = Assembly("doll_house")
    wood = house.part(PAINTED)
    wood.box(0, 0, 0, width, depth, 0.04, "up_oak")
    wood.box(0, -depth / 2 + 0.01, 0.04, width - 0.04, 0.02, 0.52, CREAM)
    for side in (-1, 1):
        wood.box(side * (width / 2 - 0.01), 0, 0.04, 0.02, depth, 0.52, PINK_V)
    wood.box(0, 0.0, 0.54, width, depth, 0.02, CREAM)
    _doll_house_rooms(wood, width, depth)
    gable = [(-width / 2 - 0.03, 0.56), (width / 2 + 0.03, 0.56), (0, 0.72)]
    wood.extrude([(x_, z_ - 0.02) for x_, z_ in gable], "xz", -depth / 2, -depth / 2 + 0.02, CREAM)
    for side in (-1, 1):
        with wood.at(side * 0.23, 0.02, 0.64, ry=side * 36):
            wood.box(0, 0, 0, 0.56, depth + 0.04, 0.022, "up_paint_red")
            for row in range(7):
                wood.box(0, 0, 0.012, 0.56, depth + 0.045, 0.0015, "up_paint_red")
    wood.box(0, 0.025, 0.715, 0.05, depth + 0.05, 0.03, "up_paint_red")
    wood.box(0.28, -0.1, 0.62, 0.07, 0.07, 0.14, "up_paint_cream")
    wood.box(0.28, -0.1, 0.76, 0.085, 0.085, 0.015, "up_paint_red")
    with wood.at(width / 2 + 0.005, depth / 2, 0.04, rz=70):
        wood.box(-0.16, 0, 0, 0.32, 0.015, 0.50, CREAM)
        wood.box(-0.16, 0.009, 0.25, 0.14, 0.004, 0.18, "up_glass")
    furniture = house.part(PAINTED)
    _doll_house_furniture(furniture)
    return place(ctx, house, room, "doll_house", x, y, yaw, z)


# ---------------------------------------------------------------------------
# Escrivaninha, cadeira e caixa de música
# ---------------------------------------------------------------------------
def _crayon(m, cx, cy, z0, tip, bend):
    m.tube((cx, cy, z0), (cx + bend, cy + 0.01, z0 + 0.075), 0.0045, tip, seg=6)
    m.tube((cx + bend, cy + 0.01, z0 + 0.075), (cx + bend * 1.2, cy + 0.011, z0 + 0.088), 0.0045, tip, seg=6, r_end=0.0008)


def _music_box(m, cx, cy, z0):
    """Caixa de música com a tampa aberta, o pente de aço e uma bailarina de tule em cima de uma mola."""
    m.box(cx, cy, z0, 0.17, 0.12, 0.065, "up_walnut")
    m.box(cx, cy, z0 + 0.065, 0.15, 0.10, 0.004, "brass")
    m.box(cx + 0.03, cy + 0.01, z0 + 0.069, 0.07, 0.016, 0.004, "up_steel")
    with m.at(cx, cy - 0.06, z0 + 0.065, rx=100):
        m.box(0, 0.06, 0, 0.17, 0.12, 0.012, "up_walnut")
        m.panel(0, 0.06, 0.0075, 0.14, 0.09, "up_paint_pink", "top")
    m.tube((cx - 0.02, cy, z0 + 0.069), (cx - 0.02, cy, z0 + 0.115), 0.0025, "chrome", seg=5)
    m.cylinder(cx - 0.02, cy, z0 + 0.105, 0.030, 0.014, "up_cloth_white", seg=12, r_top=0.008)
    m.cylinder(cx - 0.02, cy, z0 + 0.118, 0.010, 0.026, "up_paint_pink", seg=8, r_top=0.008)
    m.sphere(cx - 0.02, cy, z0 + 0.158, 0.010, "up_cloth_beige", seg=8, rings=5)


def make_kid_desk(ctx, room, wall, along, *, z=None):
    """Escrivaninha infantil: gavetas, copo de giz de cera, folhas com desenhos, livro de histórias e a caixa de música."""
    width, depth = 1.05, 0.5
    x, y, yaw = against_wall(room, wall, along, depth)
    desk = Assembly("kid_desk")
    wood = desk.part(PAINTED, builder_class=small.UvBuilder)
    wood.box(0, 0, 0.51, width, depth, 0.04, "up_oak")
    for sy in (-depth / 2 + 0.04, depth / 2 - 0.04):
        wood.frustum(-width / 2 + 0.04, sy, 0, 0.05, 0.05, 0.036, 0.036, 0.51, PINK_V)
    wood.box(0.25, 0, 0.0, 0.46, depth - 0.04, 0.51, CREAM)
    for row, z0 in enumerate((0.27, 0.03)):
        joinery.framed_panel(wood, 0.25, depth / 2 - 0.04, z0, 0.42, 0.21, CREAM, CREAM, depth=0.02, frame=0.024, frame_mat_v=CREAM_V)
        joinery.knob(wood, 0.25, depth / 2 - 0.02, z0 + 0.105, "brass", 1.1)
    wood.box(-0.26, -depth / 2 + 0.03, 0.04, 0.5, 0.02, 0.47, CREAM)
    top = 0.55
    wood.box(0.0, 0.03, top, 0.62, 0.40, 0.0015, "up_paper_blank")
    for index, (art, cx, cy, turn) in enumerate((("up_crayon_house", -0.28, 0.06, 12), ("up_crayon_family", -0.05, 0.12, -7))):
        with wood.at(cx, cy, top + 0.002 * (index + 1), rz=turn):
            wood.box(0, 0, 0, 0.20, 0.27, 0.0012, "up_paper_blank")
            wood.panel(0, 0, 0.00125, 0.20, 0.27, art, "top")
    small.book_flat(wood, 0.04, -0.14, top, 0.018, 0.17, 0.22, 3, yaw=4)
    _music_box(wood, 0.25, -0.05, top)
    wood.cylinder(-0.42, -0.13, top, 0.036, 0.09, "up_paint_yellow", seg=segments(14))
    for index, (tip, bend) in enumerate((("up_paint_red", -0.012), ("up_paint_blue", 0.0), ("up_paint_green", 0.014), ("up_paint_pink", 0.026))):
        _crayon(wood, -0.42 + (index - 1.5) * 0.008, -0.13, top + 0.035, tip, bend)
    with wood.at(-0.34, 0.14, top, rz=35):
        _crayon(wood, 0, 0, 0.0, "up_paint_yellow", 0.0)
    return place(ctx, desk, room, "kid_desk", x, y, yaw, z)


def make_kid_chair(ctx, room, x, y, yaw, *, tucked=True):
    """Cadeirinha de madeira rosa com um coração no encosto, para sentar à escrivaninha."""
    chair = Assembly("chair_kid")
    wood = chair.part(PAINTED)
    wood.box(0, 0, 0.27, 0.32, 0.30, 0.03, PINK)
    for sx in (-0.13, 0.13):
        wood.frustum(sx, 0.12, 0, 0.035, 0.035, 0.026, 0.026, 0.27, CREAM_V)
        wood.frustum(sx, -0.12, 0, 0.035, 0.035, 0.026, 0.026, 0.27, CREAM_V)
        wood.box(sx, -0.12, 0.27, 0.025, 0.025, 0.30, CREAM_V)
    wood.box(0, -0.12, 0.50, 0.30, 0.025, 0.07, PINK)
    wood.box(0, -0.12, 0.34, 0.30, 0.02, 0.05, CREAM)
    heart = [(0.0, 0.405), (0.05, 0.45), (0.062, 0.48), (0.04, 0.505), (0.0, 0.485), (-0.04, 0.505), (-0.062, 0.48), (-0.05, 0.45)]
    wood.extrude(heart, "xz", -0.1315, -0.1235, "up_paint_red")
    return place(ctx, chair, room, "chair_kid", x, y, yaw, tucked=tucked)


# ---------------------------------------------------------------------------
# Luz noturna, cubos, sapatinhos, móbile
# ---------------------------------------------------------------------------
def make_night_light(ctx, room, wall, along, z):
    """Luz noturna de tomada: base de plástico branco e um domo de lua que brilha (o único brilho do quarto)."""
    from .decor_quartos import wall_spot
    x, y, yaw = wall_spot(room, wall, along)
    light = Assembly("night_light")
    plug = light.part(METAL)
    plug.soft_box(0, 0.016, -0.05, 0.075, 0.032, 0.10, "up_plastic_white", radius=0.012, edge=0.006)
    dome = light.part(craft.Finish(bevel=0.0, smooth_angle=180.0))
    dome.lathe([(0.001, 0.0), (0.034, 0.004), (0.036, 0.016), (0.028, 0.030), (0.012, 0.040), (0.001, 0.044)], 0, 0.032, 0.0,
               "night_light", seg=segments(20), smooth=True, cap_bottom=False, cap_top=False)
    return place(ctx, light, room, "night_light", x, y, yaw, floor_z(room) + z, mode="wall")


def make_letter_blocks(ctx, room, x, y):
    """Quatro cubos de alfabeto (E, M, M, A) no tapete; o último tombado de lado."""
    size = 0.075
    blocks = Assembly("letter_blocks")
    m = blocks.part(PAINTED)
    for material, dx, dy, turn in (("up_block_e", 0.0, 0.0, 6), ("up_block_m", 0.09, 0.005, -4), ("up_block_m", 0.19, -0.01, 10),
                                   ("up_block_a", 0.30, 0.06, 55)):
        with m.at(dx, dy, 0, rz=turn):
            m.box(0, 0, 0, size, size, size, material, uv=1 / size)
    return place(ctx, blocks, room, "letter_blocks", x, y, 0.0, floor_z(room) + 0.014, mode="decor")


def make_small_shoes(ctx, room, x, y, yaw, *, z=None):
    """Sapatilhas rosa lado a lado ao pé da cama, as pontas ainda voltadas para o lugar onde ela se sentava."""
    pair = Assembly("small_shoes")
    m = pair.part(UPHOLSTERY)
    small.shoe(m, -0.05, 0.0, 0.0, "up_fur_pink", yaw=4, scale=0.52, sole="up_cloth_white")
    small.shoe(m, 0.05, 0.0, 0.0, "up_fur_pink", yaw=-3, scale=0.52, sole="up_cloth_white")
    return place(ctx, pair, room, "shoes", x, y, yaw, z, mode="decor")


def _crescent(radius):
    outer = [(radius * math.cos(a), radius * math.sin(a)) for a in (math.pi * (0.2 + 1.6 * i / 14) for i in range(15))]
    inner = [(radius * 0.55 * math.cos(a) + radius * 0.45, radius * 0.55 * math.sin(a)) for a in
             (math.pi * (1.75 - 1.5 * i / 14) for i in range(15))]
    return outer + inner


def make_mobile(ctx, room, x, y):
    """Móbile de papel pendurado no forro: estrela, lua, nuvem e coração em linhas de pesca, braços cruzados."""
    mobile = Assembly("mobile")
    metal = mobile.part(METAL)
    metal.tube((0, 0, 0), (0, 0, -0.30), 0.0012, "chrome", seg=5)
    metal.tube((-0.24, 0, -0.30), (0.24, 0, -0.30), 0.003, "brass", seg=6)
    metal.tube((0, -0.24, -0.30), (0, 0.24, -0.30), 0.003, "brass", seg=6)
    paper = mobile.part(PAINTED)
    shapes = ((0.24, 0.0, 0.26, _star(0, 0, 0.05), "up_paint_yellow"), (-0.24, 0.0, 0.34, _crescent(0.045), "up_paint_cream"),
              (0.0, 0.24, 0.40, [(0.05 * math.cos(a), 0.035 * math.sin(a)) for a in (2 * math.pi * k / 14 for k in range(14))], "up_paint_white"),
              (0.0, -0.24, 0.30, [(0.0, -0.05), (0.05, 0.0), (0.03, 0.04), (0.0, 0.02), (-0.03, 0.04), (-0.05, 0.0)], "up_paint_pink"))
    for sx, sy, drop, outline, material in shapes:
        metal.tube((sx, sy, -0.30), (sx, sy, -0.30 - drop), 0.0008, "chrome", seg=4)
        with paper.at(sx, sy, -0.30 - drop - 0.05, rz=sx * 90 + sy * 40):
            paper.extrude(outline, "xz", -0.004, 0.004, material)
    return place(ctx, mobile, room, "mobile", x, y, 0.0, floor_z(room) + 2.6, mode="wall")
