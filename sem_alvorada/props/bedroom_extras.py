"""Complementos do quarto do casal: cadeira com a roupa de Dan, espelho coberto, cesto de roupa suja, banco, sapatos."""
import math

from .. import craft
from . import cloth_quartos as fabric
from . import small_quartos as small
from . import woodwork_quartos as joinery
from .assembly_quartos import CLOTH, HERO_WOOD, UPHOLSTERY, WOOD, Assembly, segments
from .decor_quartos import wall_spot
from .kit import MeshBuilder
from .placement import floor_z, place

WALNUT, WALNUT_V = joinery.wood_pair("up_walnut")
OAK, OAK_V = joinery.wood_pair("up_oak")


# ---------------------------------------------------------------------------
# Cadeira de quarto com a roupa do dia
# ---------------------------------------------------------------------------
def _chair_frame(m, seat_mat):
    for sx in (-0.195, 0.195):
        joinery.turned(m, sx, 0.185, 0, joinery.LEG_PROFILE, 0.45, OAK_V, seg=14)
        m.box(sx, -0.185, 0, 0.034, 0.034, 0.92, OAK_V)
    m.box(0, 0, 0.42, 0.44, 0.42, 0.035, OAK)
    for y in (-0.185, 0.185):
        m.box(0, y, 0.16, 0.36, 0.02, 0.025, OAK)
    for sx in (-0.195, 0.195):
        m.box(sx, 0, 0.17, 0.02, 0.36, 0.025, OAK)
    m.box(0, -0.185, 0.80, 0.40, 0.03, 0.09, OAK)
    for slat_x in (-0.12, 0.0, 0.12):
        m.box(slat_x, -0.185, 0.50, 0.04, 0.016, 0.30, OAK_V)
    m.box(0, -0.185, 0.46, 0.38, 0.03, 0.04, OAK)


def _chair_collider():
    hold = MeshBuilder("chair_hold")
    hold.finish = None
    hold.box(0, 0, 0.42, 0.44, 0.42, 0.07, "up_oak")
    hold.box(0, -0.185, 0.46, 0.42, 0.04, 0.48, "up_oak")
    return hold


def _trousers(chair):
    """Calça jeans largada: duas pernas que saem do assento, passam pela frente e caem até perto do chão."""
    for side in (-1, 1):
        path = [(side * 0.07, -0.10, 0.60), (side * 0.085, 0.02, 0.52), (side * 0.095, 0.22, 0.50), (side * 0.10, 0.32, 0.42),
                (side * 0.115, 0.35, 0.22), (side * 0.13, 0.30, 0.06)]
        leg = craft.tube_along(path, 0.064, 10, 7, taper=lambda t: 1.0 - 0.28 * t, name="trouser_leg")
        chair.add_mesh(leg, "up_denim")


def make_bedroom_chair(ctx, room, x, y, yaw, *, seat="up_cloth_red", clothes=True, name=None):
    """Cadeira de madeira com assento estofado e, por cima, a camisa e a calça de Dan, largadas como caíram."""
    chair = Assembly(name or f"chair_{room}")
    frame = chair.part(WOOD)
    _chair_frame(frame, seat)
    cushion = chair.part(UPHOLSTERY)
    cushion.soft_box(0, 0.01, 0.455, 0.40, 0.38, 0.05, seat, radius=0.04, edge=0.02)
    if clothes:
        hold = _chair_collider()
        _trousers(chair)
        shirt = fabric.settle_cloth(0.5, 0.7, (0.0, -0.12), 1.12, [hold], "up_cloth_white", cell=0.05,
                                    wrinkles=0.03, seed=ctx.seed + 12, thickness=0.004, subsurf=0, frames=50, floor=0.0)
        chair.add_mesh(shirt, "up_cloth_white")
    return place(ctx, chair, room, "chair_bedroom", x, y, yaw, name=name)


# ---------------------------------------------------------------------------
# Espelho de parede (a casa de Laura cobriu o do quarto com um lençol)
# ---------------------------------------------------------------------------
def make_wall_mirror(ctx, room, wall, along, z, width, height, *, draped=False, art="up_mirror_plain"):
    """Espelho de parede com moldura de madeira; `draped` o cobre da testa até quase o fim com um lençol (luto)."""
    x, y, yaw = wall_spot(room, wall, along)
    mirror = Assembly("mirror")
    wood = mirror.part(WOOD)
    depth, border = 0.034, 0.05
    with wood.at(0, depth / 2, 0):
        for sign in (-1, 1):
            wood.box(sign * (width + border) / 2, 0, -(height + 2 * border) / 2, border, depth, height + 2 * border, WALNUT_V)
            wood.box(0, 0, sign * (height + border) / 2 - border / 2, width, depth, border, WALNUT)
        wood.panel(0, depth / 2 - 0.006, 0, width, height, art, "front")
        wood.box(0, 0, height / 2 + border, width + 2 * border + 0.04, depth + 0.012, 0.03, WALNUT)
    if draped:
        sheet = mirror.part(CLOTH)
        _mirror_sheet(sheet, width + 0.18, height, border, depth)
    return place(ctx, mirror, room, "mirror", x, y, yaw, floor_z(room) + z, mode="wall")


def _mirror_sheet(m, sheet_width, height, border, depth):
    """Lençol pendurado na testa da moldura: pregas que crescem para baixo e uma barra repuxada de um lado."""
    top = height / 2 + border + 0.03
    drop = height * 0.80

    def fn(u, v):
        hem = drop * (1.0 - 0.30 * u ** 2 + 0.06 * math.sin(u * 19))
        pleat = (0.012 * math.sin(u * 41) + 0.008 * math.sin(u * 17 + 1.3)) * (0.25 + 0.75 * v)
        return (u - 0.5) * sheet_width, depth + 0.012 + pleat + 0.02 * v * v, top - v * hem

    m.surface(fn, 70, 10, "up_cloth_white", uv_size=(sheet_width, drop), uv=2.0, smooth=True)
    m.box(0, depth / 2, top - 0.012, sheet_width * 0.94, depth + 0.03, 0.02, "up_cloth_white")


# ---------------------------------------------------------------------------
# Cesto de roupa suja
# ---------------------------------------------------------------------------
def make_laundry_basket(ctx, room, x, y, *, z=None):
    """Cesto de vime com roupa amontoada, uma manga caída por cima da borda."""
    basket = Assembly("laundry_basket")
    wicker = basket.part(craft.Finish(bevel=0.0, smooth_angle=60.0))
    height, radius = 0.52, 0.22
    wicker.lathe([(radius * 0.80, 0.0), (radius * 0.86, 0.02), (radius * 0.94, height * 0.5), (radius, height)], 0, 0, 0,
                 "up_wicker", seg=segments(28), smooth=True, cap_top=False)
    wicker.torus(0, 0, height, radius, 0.014, "up_wicker", seg=segments(28), seg_minor=6)
    for side in (-1, 1):
        wicker.tube((side * radius, 0, height - 0.06), (side * (radius + 0.03), 0, height + 0.05), 0.012, "up_wicker", seg=6)
    hold = MeshBuilder("basket_hold")
    hold.finish = None
    hold.lathe([(radius * 0.78, 0.01), (radius * 0.86, 0.02), (radius * 0.94, height * 0.5), (radius * 0.99, height)], 0, 0, 0,
               "up_wicker", seg=20, smooth=False, cap_top=False)
    for index, (material, size) in enumerate((("up_cloth_gray", 0.36), ("up_cloth_white", 0.34), ("up_cloth_red", 0.32))):
        cloth_piece = fabric.settle_cloth(size, size, (0.03 * index - 0.03, 0.02 * index), height + 0.30 + 0.12 * index,
                                          [hold], material, cell=0.04, wrinkles=0.05, seed=ctx.seed + 31 + index,
                                          uv_scale=2.0, subsurf=0, frames=60, floor=0.0)
        basket.add_mesh(cloth_piece, material)
    sleeve = fabric.settle_cloth(0.16, 0.56, (radius * 0.55, 0.0), height + 0.04, [hold], "up_cloth_blue", cell=0.035,
                                 wrinkles=0.01, seed=ctx.seed + 39, uv_scale=2.0, subsurf=0, frames=55, floor=0.0)
    basket.add_mesh(sleeve, "up_cloth_blue")
    return place(ctx, basket, room, "laundry_basket", x, y, 0.0, z)


# ---------------------------------------------------------------------------
# Banco do pé da cama
# ---------------------------------------------------------------------------
def make_bench(ctx, room, x, y, yaw, *, z=None):
    """Banco estofado em couro com pés torneados e botões, para sentar e calçar os sapatos."""
    bench = Assembly("bench")
    wood = bench.part(HERO_WOOD)
    width, depth = 1.10, 0.40
    for sx in (-1, 1):
        for sy in (-1, 1):
            joinery.turned(wood, sx * (width / 2 - 0.05), sy * (depth / 2 - 0.05), 0, joinery.LEG_PROFILE, 0.36, WALNUT_V, seg=16)
    wood.box(0, 0, 0.30, width - 0.04, depth - 0.04, 0.06, WALNUT)
    upholstery = bench.part(UPHOLSTERY)
    upholstery.soft_box(0, 0, 0.35, width, depth, 0.10, "up_leather", radius=0.06, edge=0.04, corner_points=4)
    for bx in (-0.36, -0.12, 0.12, 0.36):
        upholstery.sphere(bx, 0, 0.455, 0.012, "up_leather", seg=8, rings=4)
    return place(ctx, bench, room, "bench", x, y, yaw, z)


# ---------------------------------------------------------------------------
# Sapatos
# ---------------------------------------------------------------------------
def make_shoes(ctx, room, x, y, yaw, kind, *, z=None):
    """'dan': sapatos sociais pretos, um tombado; 'laura': chinelos de pelúcia rosa, lado a lado e intocados."""
    pair = Assembly(f"shoes_{kind}")
    m = pair.part(UPHOLSTERY if kind == "laura" else WOOD)
    if kind == "dan":
        small.shoe(m, -0.07, 0.0, 0.0, "up_leather", yaw=8)
        small.shoe(m, 0.16, 0.05, 0.0, "up_leather", yaw=-70, tilt=0)
    else:
        small.shoe(m, -0.06, 0.0, 0.0, "up_fur_pink", yaw=2, scale=0.85, sole="up_cloth_white")
        small.shoe(m, 0.06, 0.0, 0.0, "up_fur_pink", yaw=-2, scale=0.85, sole="up_cloth_white")
    return place(ctx, pair, room, "shoes", x, y, yaw, z, mode="decor")
