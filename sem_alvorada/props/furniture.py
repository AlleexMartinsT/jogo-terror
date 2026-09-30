"""Peças genéricas usadas em vários cômodos: cadeiras, quadros, tapetes, marcas, caixas.

Assinatura padrão: `make_<coisa>(ctx, room, x, y, yaw=0.0, *, z=None, ...)` devolve o Object.
`z=None` significa o piso do cômodo. Quadros e decals usam `wall` ('N','S','E','W') + `along`.
"""
import math

from . import parts
from .kit import MeshBuilder
from .placement import against_wall, floor_z, place

WALL_OFFSET = 0.004


def wall_spot(room, wall, along, gap=0.0):
    """(x, y, yaw) sobre a face interna da parede `wall`, com a frente da peça voltada para o cômodo."""
    return against_wall(room, wall, along, gap * 2)


# ---------------------------------------------------------------------------
# Cadeiras
# ---------------------------------------------------------------------------
def _dining_chair(m, cushion_mat, wood_mat="wood_mid"):
    m.box(0, 0, 0.42, 0.44, 0.42, 0.04, wood_mat)
    m.soft_box(0, 0.01, 0.46, 0.40, 0.38, 0.05, cushion_mat, radius=0.03, edge=0.015)
    for cx in (-0.195, 0.195):
        m.box(cx, 0.185, 0, 0.035, 0.035, 0.42, wood_mat)
        m.box(cx, -0.185, 0, 0.035, 0.035, 0.90, wood_mat)
    for z in (0.60, 0.72, 0.84):
        m.box(0, -0.185, z, 0.36, 0.02, 0.07, wood_mat)
    for y in (-0.185, 0.185):
        m.box(0, y, 0.16, 0.36, 0.02, 0.02, wood_mat)


def _office_chair(m, cushion_mat):
    for i in range(5):
        angle = math.radians(72 * i + 18)
        tip = (0.27 * math.cos(angle), 0.27 * math.sin(angle))
        m.bar((0, 0, 0.09), (tip[0], tip[1], 0.06), 0.03, "steel_dark")
        m.cylinder(tip[0], tip[1], 0.0, 0.025, 0.05, "black", seg=6)
    m.cylinder(0, 0, 0.09, 0.025, 0.32, "steel_dark", seg=6)
    m.soft_box(0, 0.02, 0.41, 0.50, 0.48, 0.08, cushion_mat, radius=0.06, edge=0.025)
    with m.at(0, -0.22, 0.52, rx=8):
        m.soft_box(0, 0, 0, 0.46, 0.08, 0.50, cushion_mat, radius=0.05, edge=0.02)
    m.box(0, -0.2, 0.44, 0.06, 0.06, 0.12, "steel_dark")
    for cx in (-0.27, 0.27):
        m.bar((cx, -0.05, 0.47), (cx, -0.05, 0.62), 0.025, "steel_dark")
        m.box(cx, 0.02, 0.62, 0.06, 0.26, 0.03, "black")


def _kid_chair(m, wood_mat):
    m.box(0, 0, 0.26, 0.30, 0.28, 0.03, wood_mat)
    for cx in (-0.13, 0.13):
        m.box(cx, 0.12, 0, 0.025, 0.025, 0.26, wood_mat)
        m.box(cx, -0.12, 0, 0.025, 0.025, 0.55, wood_mat)
    for z in (0.40, 0.49):
        m.box(0, -0.12, z, 0.26, 0.018, 0.06, wood_mat)


def make_chair(ctx, room, x, y, yaw=0.0, *, z=None, style="dining", fallen=False, tucked=False,
               cushion="fabric_gray", name=None):
    """Cadeira; `style`: dining | office | kid. `fallen=True` deixa a peça caída para trás."""
    m = MeshBuilder(name or f"chair_{room}")
    build_style = {"dining": lambda: _dining_chair(m, cushion),
                   "office": lambda: _office_chair(m, cushion),
                   "kid": lambda: _kid_chair(m, "painted_pink")}[style]
    with m.at(0, 0, 0, rx=96 if fallen else 0, rz=12 if fallen else 0):
        build_style()
    if fallen:
        m.drop_to_floor()
    return place(ctx, m, room, f"chair_{style}", x, y, yaw, z, name=name, tucked=tucked)


def make_side_table(ctx, room, wall, along, *, width=0.8, depth=0.34, height=0.74, name=None):
    """Mesinha de encostar com uma gaveta e pernas afiladas."""
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder(name or "side_table")
    m.box(0, 0.0, height - 0.035, width, depth, 0.035, "wood_dark")
    m.box(0, 0.0, height - 0.12, width - 0.06, depth - 0.04, 0.085, "wood_mid")
    parts.knob(m, 0, depth / 2 - 0.02, height - 0.085, "brass")
    for cx in (-width / 2 + 0.04, width / 2 - 0.04):
        for cy in (-depth / 2 + 0.04, depth / 2 - 0.04):
            m.cylinder(cx, cy, 0, 0.022, height - 0.12, "wood_dark", seg=5, r_top=0.014)
    return place(ctx, m, room, "side_table", x, y, yaw, name=name)


def make_photo_frame(ctx, room, x, y, z, yaw, art, *, fallen=False, width=0.13, height=0.17, name=None):
    """Porta-retrato de mesa; `fallen=True` deixa tombado de bruços (só o verso de papelão aparece)."""
    m = MeshBuilder(name or "photo_frame")
    with m.at(0, 0, 0, rx=-90 if fallen else 8, rz=28 if fallen else 0):
        parts.picture(m, 0, 0, height / 2 + 0.01, width, height, art, frame_mat="wood_mid", border=0.014, depth=0.014)
        m.box(0, -0.028, 0.01, 0.03, 0.05, height * 0.6, "wood_mid")
    if fallen:
        m.drop_to_floor()
    return place(ctx, m, room, "photo_frame", x, y, yaw, z, mode="decor", name=name)


def make_basket(ctx, room, x, y, *, radius=0.22, height=0.5, folded_towels=True, z=None):
    """Cesto de vime com toalhas dobradas no topo."""
    m = MeshBuilder("basket")
    parts.wicker_basket(m, 0, 0, 0, radius, height)
    if folded_towels:
        m.soft_box(0, 0, height - 0.12, radius * 1.5, radius * 1.3, 0.10, "linen_dirty", radius=0.04, edge=0.02)
        m.soft_box(0.02, 0.0, height - 0.03, radius * 1.3, radius * 1.1, 0.08, "coat_beige", radius=0.04, edge=0.02)
    return place(ctx, m, room, "basket", x, y, 0.0, z)


# ---------------------------------------------------------------------------
# Quadros, espelhos e marcas na parede
# ---------------------------------------------------------------------------
def make_picture(ctx, room, wall, along, z, width, height, art, *, frame="wood_dark", name=None):
    """Quadro na parede. `z` é a altura do centro acima do piso do cômodo."""
    x, y, yaw = wall_spot(room, wall, along)
    m = MeshBuilder(name or f"picture_{room}")
    parts.picture(m, 0, 0.018, 0, width, height, art, frame_mat=frame)
    return place(ctx, m, room, "picture", x, y, yaw, floor_z(room) + z, mode="wall", name=name)


def make_wall_decal(ctx, room, wall, along, z, width, height, texture, *, name=None):
    """Marca rente à parede (mãos, manchas): um quad com alfa a 4 mm da superfície."""
    x, y, yaw = wall_spot(room, wall, along)
    m = MeshBuilder(name or f"decal_{room}")
    m.panel(0, WALL_OFFSET, 0, width, height, texture, "front")
    return place(ctx, m, room, "decal", x, y, yaw, floor_z(room) + z, mode="wall", name=name)


def make_rug(ctx, room, x, y, yaw, width, depth, texture, *, round_shape=False, tile_along=False, name=None):
    """Tapete rente ao piso (não colide, pode cruzar zonas reservadas). `tile_along` repete o padrão no comprimento."""
    m = MeshBuilder(name or f"rug_{room}")
    thickness = 0.014
    if round_shape:
        angles = [2 * math.pi * i / 20 for i in range(20)]
        low = [(width / 2 * math.cos(a), depth / 2 * math.sin(a), 0.0) for a in angles]
        high = [(px, py, thickness) for px, py, _ in low]
        m.loft([low, high], texture, cap_start=False, cap_end=False)
        m.poly(high, texture, uv=[(0.5 + px / width, 0.5 + py / depth) for px, py, _ in high])
    else:
        repeats = depth / width if tile_along else 1.0
        m.panel(0, 0, thickness, width, depth, texture, "top", uv_rect=(0, 0, 1, repeats))
        m.box(0, 0, 0, width, depth, thickness, texture, skip=("top", "bottom"))
    return place(ctx, m, room, "rug", x, y, yaw, mode="flat", name=name)


def make_floor_decal(ctx, room, x, y, yaw, width, depth, texture, *, lift=0.018, z=None, name=None):
    """Mancha/decal com alfa deitado sobre o piso ou sobre um tapete."""
    m = MeshBuilder(name or f"stain_{room}")
    m.panel(0, 0, 0, width, depth, texture, "top")
    base = floor_z(room) if z is None else z
    return place(ctx, m, room, "decal", x, y, yaw, base + lift, mode="flat", name=name)


# ---------------------------------------------------------------------------
# Caixas de papelão
# ---------------------------------------------------------------------------
def make_box_stack(ctx, room, x, y, yaw, layers, *, texture="cardboard", size=(0.5, 0.4, 0.34), label=None,
                   name=None):
    """Pilha de caixas de papelão; `layers` é uma lista de escalas/deslocamentos por camada."""
    m = MeshBuilder(name or f"boxes_{room}")
    z = 0.0
    for scale, dx, dy, turn in layers:
        w, d, h = size[0] * scale, size[1] * scale, size[2] * scale
        with m.at(dx, dy, z, rz=turn):
            m.box(0, 0, 0, w, d, h, texture, mats={"front": label or texture}, uv=1.6)
        z += h
    return place(ctx, m, room, "boxes", x, y, yaw, name=name)


def make_cup(ctx, room, x, y, z, *, glass=False):
    """Xícara esquecida sobre uma superfície (o café frio do Dan)."""
    m = MeshBuilder("cup")
    parts.mug(m, 0, 0, 0, 0.04, 0.09, "glass_clear" if glass else "ceramic_cream")
    m.cylinder(0, 0, 0.07, 0.035, 0.004, "food_dried", seg=8)
    return place(ctx, m, room, "cup", x, y, ctx.rng.uniform(0, math.tau), z, mode="decor")
