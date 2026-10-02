"""Peças pequenas de ambientação do andar de cima: o que a casa guarda do dia em que ela morreu.

Cada função cria um objeto `decor` ou `wall` pequeno, apoiado, encostado ou caído com lógica, nunca no caminho do
jogador nem na visada dos itens coletáveis.
"""
import math

from .. import craft
from . import plush_quartos as plush
from . import small_quartos as small
from .assembly_quartos import METAL, PLUSH, WOOD, Assembly, segments
from .decor_quartos import wall_spot
from .placement import floor_z, place


# ---------------------------------------------------------------------------
# Quarto do casal
# ---------------------------------------------------------------------------
def make_dresser_top(ctx, room, x, y, z, yaw):
    """Tampo da cômoda: paninho de renda, caixa de joias aberta com um colar, escova, perfume, relógio e o retrato do casamento."""
    top = Assembly("dresser_top")
    m = top.part(WOOD, builder_class=small.UvBuilder)
    m.cylinder(0.0, 0.03, 0.0, 0.20, 0.002, "up_cloth_white", seg=segments(24))
    m.box(-0.46, 0.02, 0.0, 0.22, 0.14, 0.07, "up_walnut")
    with m.at(-0.46, -0.05, 0.07, rx=105):
        m.box(0, 0.07, 0, 0.22, 0.14, 0.012, "up_walnut")
        m.panel(0, 0.07, 0.0065, 0.20, 0.12, "up_cloth_red", "top")
    m.box(-0.46, 0.02, 0.066, 0.20, 0.12, 0.003, "up_cloth_red")
    pearls = craft.tube_along([(-0.52, 0.02, 0.07), (-0.46, 0.08, 0.075), (-0.40, 0.03, 0.073), (-0.34, 0.09, 0.0), (-0.30, 0.11, 0.0)],
                              0.0035, 6, 6, name="necklace")
    top.add_mesh(pearls, "up_plastic_white")
    with m.at(0.02, 0.0, 0.0, rz=18):
        plush.ellipsoid(m, 0, 0, 0.012, 0.045, 0.058, 0.012, "up_walnut", seg=12, rings=6)
        m.tube((0, -0.05, 0.012), (0, -0.16, 0.012), 0.009, "up_walnut", seg=8, smooth=True)
        for row in range(4):
            m.box(-0.015 + row * 0.01, 0.0, 0.022, 0.003, 0.07, 0.006, "up_paint_cream")
    m.lathe([(0.0, 0.0), (0.03, 0.0), (0.035, 0.012), (0.034, 0.075), (0.012, 0.09), (0.011, 0.105)], 0.30, 0.02, 0.0, "up_glass_amber",
            seg=segments(14), smooth=True)
    m.sphere(0.30, 0.02, 0.118, 0.016, "brass", seg=10, rings=6)
    with m.at(-0.12, -0.12, 0.002, rz=-25):
        m.torus(0, 0, 0.003, 0.016, 0.0035, "up_leather", seg=14, seg_minor=5)
        m.cylinder(0, 0.0, 0.0, 0.016, 0.006, "brass", seg=12)
    small.photo_stand(m, 0.52, -0.1, 0.0, "up_photo_mother_child", width=0.14, height=0.18, frame="brass")
    return place(ctx, top, room, "dresser_top", x, y, yaw, z, mode="decor")


def make_fallen_hangers(ctx, room, x, y):
    """Três cabides de arame no chão, largados de quando as roupas de Laura foram levadas pela metade."""
    pile = Assembly("hangers")
    wire = pile.part(METAL)
    for index, (dx, dy, turn) in enumerate(((0.0, 0.0, 10), (0.06, 0.05, 80), (-0.05, 0.08, 150))):
        with wire.at(dx, dy, 0.0035 + index * 0.0035, rz=turn):
            loop = craft.tube_along([(0.0, 0.0, 0.0), (0.0, 0.05, 0.0), (0.0, 0.07, 0.0)], 0.0013, 5, 4, name="hook")
            pile.add_mesh(loop, "chrome")
            wire.tube((0.0, 0.0, 0.0), (-0.2, -0.1, 0.0), 0.0013, "chrome", seg=5)
            wire.tube((0.0, 0.0, 0.0), (0.2, -0.1, 0.0), 0.0013, "chrome", seg=5)
            wire.tube((-0.2, -0.1, 0.0), (0.2, -0.1, 0.0), 0.0013, "chrome", seg=5)
    return place(ctx, pile, room, "hangers", x, y, ctx.rng.uniform(0, math.tau), floor_z(room), mode="decor")


# ---------------------------------------------------------------------------
# Quarto da Emma
# ---------------------------------------------------------------------------
def make_tea_set(ctx, room, x, y):
    """Chá das bonecas no tapete: bule, duas xícaras com pires, e o urso e o coelho sentados esperando que ela volte."""
    tea = Assembly("tea_set")
    porcelain = tea.part(craft.Finish(bevel=0.0, smooth_angle=60.0))
    porcelain.lathe([(0.0, 0.0), (0.035, 0.0), (0.05, 0.03), (0.052, 0.06), (0.04, 0.085), (0.02, 0.092), (0.0, 0.093)], 0, 0, 0,
                    "up_paint_pink", seg=segments(16), smooth=True)
    porcelain.sphere(0, 0, 0.098, 0.011, "up_paint_cream", seg=8, rings=5)
    porcelain.tube((0.045, 0, 0.07), (0.078, 0, 0.055), 0.006, "up_paint_pink", seg=6)
    porcelain.tube((-0.04, 0, 0.055), (-0.085, 0, 0.075), 0.005, "up_paint_pink", seg=6)
    for cup_x in (0.18, -0.16):
        with porcelain.at(cup_x, 0.14 if cup_x > 0 else -0.12, 0.0):
            porcelain.cylinder(0, 0, 0.0, 0.036, 0.004, "up_paint_cream", seg=segments(14), r_top=0.045)
            porcelain.lathe([(0.012, 0.0), (0.022, 0.006), (0.03, 0.04), (0.032, 0.042)], 0, 0, 0.004, "up_paint_cream",
                            seg=segments(14), smooth=True, cap_top=False)
    toys = tea.part(PLUSH)
    plush.teddy(toys, 0.0, 0.34, 0.0, 0.55, "up_fur_brown", yaw=math.radians(180))
    plush.rabbit(toys, 0.30, -0.10, 0.0, 0.5, "up_fur_white", yaw=math.radians(120))
    return place(ctx, tea, room, "tea_set", x, y, 0.0, floor_z(room) + 0.014, mode="decor")


# ---------------------------------------------------------------------------
# Corredor
# ---------------------------------------------------------------------------
def make_rain_boots(ctx, room, x, y, yaw):
    """Galochas amarelas da Emma, um pé tombado, abandonadas junto ao rodapé."""
    pair = Assembly("rain_boots")
    m = pair.part(craft.Finish(bevel=0.0, smooth_angle=70.0))
    for side, (dx, dy, turn, tilt) in enumerate(((-0.06, 0.0, 3, 0), (0.13, 0.03, -62, 0))):
        with m.at(dx, dy, 0.0, rz=turn):
            small.shoe(m, 0, 0, 0.0, "up_rubber_yellow", scale=0.55, sole="up_rubber")
            m.cylinder(0, -0.045, 0.02, 0.035, 0.17, "up_rubber_yellow", seg=segments(14), r_top=0.039)
            m.torus(0, -0.045, 0.19, 0.039, 0.004, "up_rubber_yellow", seg=segments(14), seg_minor=5)
    return place(ctx, pair, room, "boots", x, y, yaw, floor_z(room), mode="decor")


# ---------------------------------------------------------------------------
# Banheiro
# ---------------------------------------------------------------------------
def make_toilet_roll(ctx, room, wall, along, z):
    """Porta-papel cromado na parede com o rolo pela metade e a ponta da folha pendurada."""
    x, y, yaw = wall_spot(room, wall, along)
    holder = Assembly("toilet_roll")
    m = holder.part(METAL)
    m.box(0, 0.007, 0, 0.02, 0.014, 0.12, "chrome")
    m.tube((0, 0.01, 0.05), (0.14, 0.04, 0.05), 0.005, "chrome", seg=8)
    with m.at(0.07, 0.04, 0.05, ry=90):
        m.cylinder(0, 0, -0.055, 0.05, 0.11, "up_paper_blank", seg=segments(18))
        m.cylinder(0, 0, -0.056, 0.019, 0.112, "up_paper_blank", seg=segments(10))
    m.quad((0.12, 0.092, 0.05), (0.095, 0.092, 0.05), (0.095, 0.10, -0.06), (0.12, 0.10, -0.06), "up_paper_blank", uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    return place(ctx, holder, room, "toilet_roll", x, y, yaw, floor_z(room) + z, mode="wall")


def make_bath_shelf(ctx, room, wall, along, z):
    """Prateleira de vidro sobre a banheira: xampu infantil, sabonete na saboneteira, esponja e um barquinho de brinquedo."""
    x, y, yaw = wall_spot(room, wall, along)
    shelf = Assembly("bath_shelf")
    m = shelf.part(METAL, builder_class=small.UvBuilder)
    m.box(0, 0.075, 0, 0.62, 0.15, 0.012, "up_glass")
    for sx in (-0.27, 0.27):
        m.box(sx, 0.006, -0.05, 0.016, 0.012, 0.06, "chrome")
        m.box(sx, 0.07, -0.014, 0.012, 0.13, 0.014, "chrome")
    for cx, tall, material in ((-0.22, 0.17, "up_paint_pink"), (-0.14, 0.15, "up_paint_blue")):
        m.lathe([(0.024, 0.0), (0.03, 0.01), (0.03, tall * 0.8), (0.015, tall * 0.92), (0.011, tall)], cx, 0.07, 0.012, material,
                seg=segments(14), smooth=True)
        m.cylinder(cx, 0.07, 0.012 + tall, 0.012, 0.02, "up_plastic_white", seg=segments(8))
    m.box(0.0, 0.075, 0.012, 0.095, 0.065, 0.014, "up_paint_white")
    m.soft_box(0.0, 0.075, 0.026, 0.075, 0.048, 0.024, "up_paint_cream", radius=0.012, edge=0.008)
    m.soft_box(0.12, 0.07, 0.012, 0.075, 0.05, 0.03, "up_paint_yellow", radius=0.014, edge=0.008)
    with m.at(0.22, 0.07, 0.012):
        m.soft_box(0, 0, 0, 0.09, 0.04, 0.02, "up_paint_red", radius=0.015, edge=0.006)
        m.box(0, 0, 0.02, 0.003, 0.003, 0.07, "up_wood_stem")
        m.poly([(0.0, 0.0, 0.085), (0.0, 0.0, 0.03), (0.045, 0.0, 0.03)], "up_cloth_white", uv=[(0, 1), (0, 0), (1, 0)])
    return place(ctx, shelf, room, "bath_shelf", x, y, yaw, floor_z(room) + z, mode="wall")


# ---------------------------------------------------------------------------
# Escritório
# ---------------------------------------------------------------------------
def make_newspaper_stack(ctx, room, x, y, yaw):
    """Pilha de jornais no chão ao lado da mesa, com a manchete do acidente para cima e as dobras desencontradas."""
    stack = Assembly("newspapers")
    m = stack.part(WOOD, builder_class=small.UvBuilder)
    for level in range(9):
        offset = (ctx.rng.uniform(-0.02, 0.02), ctx.rng.uniform(-0.02, 0.02))
        with m.at(offset[0], offset[1], level * 0.0075, rz=ctx.rng.uniform(-6, 6)):
            m.box(0, 0, 0, 0.36, 0.28, 0.0072, "up_paper_blank")
            m.panel(0, 0, 0.0073, 0.36, 0.28, "up_newsprint", "top")
    return place(ctx, stack, room, "newspapers", x, y, yaw, floor_z(room), mode="decor")


def make_desk_tools(ctx, room, x, y, z, yaw):
    """Fita adesiva no suporte, tesoura de cabo preto e caixinha de alfinetes: o material do mapa na parede."""
    tools = Assembly("desk_tools")
    m = tools.part(METAL)
    m.soft_box(0, 0, 0, 0.12, 0.06, 0.05, "up_plastic_black", radius=0.015, edge=0.006)
    with m.at(0, 0, 0.07, rx=90):
        m.torus(0, 0, 0, 0.032, 0.012, "up_plastic_white", seg=segments(16), seg_minor=6)
    with m.at(0.17, 0.0, 0.0, rz=30):
        m.box(0, 0.0, 0.0, 0.012, 0.15, 0.004, "chrome")
        for side in (-1, 1):
            m.torus(side * 0.014, -0.085, 0.003, 0.014, 0.003, "up_plastic_black", seg=12, seg_minor=5)
    m.box(-0.14, 0.0, 0.0, 0.07, 0.045, 0.02, "up_paint_red")
    for pin in range(4):
        m.sphere(-0.15 + pin * 0.02, 0.07, 0.006, 0.006, "up_paint_red", seg=6, rings=4)
    return place(ctx, tools, room, "desk_tools", x, y, yaw, z, mode="decor")
