"""Corredor de cima: console com retratos da família, vaso de flor seca, cesto, passadeira e teias.

O corredor é o caminho do jogador para todo lugar: nada aqui invade a faixa central (as zonas reservadas do
layout), e a mesinha fica encostada na parede sul, ao pé da janela.
"""
import math

from .. import craft
from . import plush_quartos as plush
from . import small_quartos as small
from . import woodwork_quartos as joinery
from .assembly_quartos import HERO_WOOD, WOOD, Assembly, segments
from .placement import against_wall, place

WALNUT, WALNUT_V = joinery.wood_pair("up_walnut")


def make_console(ctx, room, wall, along, *, width=0.8, depth=0.32, height=0.74):
    """Mesinha de encostar de nogueira: pernas torneadas, gaveta almofadada com puxador, prateleira baixa."""
    x, y, yaw = against_wall(room, wall, along, depth)
    table = Assembly("side_table")
    wood = table.part(HERO_WOOD)
    for sx in (-1, 1):
        for sy in (-1, 1):
            joinery.turned(wood, sx * (width / 2 - 0.04), sy * (depth / 2 - 0.04), 0, joinery.LEG_PROFILE, height - 0.14, WALNUT_V, seg=16)
    wood.box(0, 0, height - 0.035, width, depth, 0.035, WALNUT)
    wood.box(0, 0, height - 0.15, width - 0.08, depth - 0.07, 0.115, WALNUT)
    joinery.framed_panel(wood, 0, depth / 2 - 0.045, height - 0.145, width - 0.14, 0.105, WALNUT, WALNUT, depth=0.02,
                         frame=0.022, frame_mat_v=WALNUT_V)
    joinery.knob(wood, 0, depth / 2 - 0.025, height - 0.095, "brass", 1.1)
    wood.box(0, 0, 0.12, width - 0.1, depth - 0.08, 0.02, WALNUT)
    for sx in (-1, 1):
        wood.box(sx * (width / 2 - 0.04), 0, 0.12, 0.02, depth - 0.08, 0.1, WALNUT)
    return place(ctx, table, room, "side_table", x, y, yaw, name=None)


def make_framed_photo(ctx, room, x, y, z, yaw, art, *, fallen=False, width=0.13, height=0.17, name=None):
    """Porta-retrato de mesa com cavalete; `fallen` o deixa tombado de bruços, só o verso à mostra."""
    frame = Assembly(name or "photo_frame")
    m = frame.part(WOOD)
    rotation = {"rx": -90, "rz": 28} if fallen else {}
    with m.at(0, 0, 0, **rotation):
        small.photo_stand(m, 0, 0, 0.0, art, width=width, height=height, frame="up_walnut")
    if fallen:
        m.drop_to_floor()
    return place(ctx, frame, room, "photo_frame", x, y, yaw, z, mode="decor", name=name)


def make_dry_flowers(ctx, room, x, y, z):
    """Vaso de cerâmica azul-acinzentada com flores secas: hastes curvas, cabeças murchas, folhas que caíram na mesa."""
    vase = Assembly("dry_flowers")
    pot = vase.part(craft.Finish(bevel=0.002, smooth_angle=60.0, bevel_angle=45.0))
    pot.lathe([(0.0, 0.0), (0.045, 0.0), (0.06, 0.04), (0.075, 0.11), (0.05, 0.20), (0.032, 0.25), (0.04, 0.27), (0.034, 0.275)],
              0, 0, 0, "up_ceramic", seg=segments(22), smooth=True, cap_top=False)
    pot.cylinder(0, 0, 0.2, 0.030, 0.004, "up_water", seg=segments(12))
    stems = vase.part(craft.Finish(bevel=0.0, smooth_angle=60.0))
    for index in range(7):
        angle = index * 2.4
        reach = 0.05 + 0.03 * (index % 3)
        top = (reach * math.cos(angle), reach * math.sin(angle), 0.46 + 0.05 * (index % 2))
        mid = (0.45 * top[0], 0.45 * top[1], 0.33)
        stem = craft.tube_along([(0.0, 0.0, 0.22), mid, top], 0.0028, 6, 5, name="stem")
        vase.add_mesh(stem, "up_wood_stem")
        plush.ellipsoid(stems, top[0], top[1], top[2] + 0.012, 0.016, 0.016, 0.022, "up_cloth_beige" if index % 2 else "up_fur_brown",
                        seg=8, rings=5, turn=(index * 15, index * 20, 0))
        with stems.at(top[0] * 0.6, top[1] * 0.6, 0.32 + 0.02 * index, rz=index * 40, rx=-30):
            stems.quad((0, 0, 0), (0.03, 0.0, 0.01), (0.035, 0.05, 0.015), (0.0, 0.07, 0.0), "up_fur_brown")
    for index in range(4):
        with stems.at(0.07 * math.cos(index * 1.7), 0.07 * math.sin(index * 1.7), 0.0, rz=index * 63):
            stems.quad((0, 0, 0.0008), (0.025, 0.0, 0.0008), (0.028, 0.04, 0.0008), (0.0, 0.05, 0.0008), "up_fur_brown")
    return place(ctx, vase, room, "vase", x, y, ctx.rng.uniform(0, math.tau), z, mode="decor")


def make_basket(ctx, room, x, y, *, radius=0.22, height=0.5, z=None):
    """Cesto de vime alto com jornais enrolados e um guarda-chuva fechado."""
    basket = Assembly("basket")
    wicker = basket.part(craft.Finish(bevel=0.0, smooth_angle=60.0))
    wicker.lathe([(radius * 0.82, 0.0), (radius * 0.88, 0.02), (radius * 0.95, height * 0.5), (radius, height)], 0, 0, 0, "up_wicker",
                 seg=segments(28), smooth=True, cap_top=False)
    wicker.torus(0, 0, height, radius, 0.014, "up_wicker", seg=segments(28), seg_minor=6)
    wicker.cylinder(0, 0, 0.0, radius * 0.82, 0.02, "up_wicker", seg=segments(24))
    rolls = basket.part(craft.Finish(bevel=0.0, smooth_angle=60.0))
    for index, (dx, dy, tilt) in enumerate(((-0.07, 0.03, 4), (0.05, -0.02, -6), (0.0, 0.08, 9))):
        rolls.tube((dx, dy, 0.12), (dx + math.sin(math.radians(tilt)) * 0.4, dy, 0.12 + 0.46), 0.033, "up_newsprint", seg=10, smooth=True)
    rolls.tube((0.10, 0.06, 0.10), (0.15, 0.05, 0.62), 0.014, "up_plastic_black", seg=8)
    rolls.tube((0.15, 0.05, 0.62), (0.18, 0.05, 0.70), 0.011, "brass", seg=8)
    return place(ctx, basket, room, "basket", x, y, 0.0, z)
