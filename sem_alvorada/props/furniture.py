"""Peças genéricas usadas em vários cômodos: cadeiras, quadros, tapetes, marcas, caixas.

Assinatura padrão: `make_<coisa>(ctx, room, x, y, yaw=0.0, *, z=None, ...)` devolve o Object.
`z=None` significa o piso do cômodo. Quadros e decals usam `wall` ('N','S','E','W') + `along`.
"""
import math

from .. import craft
from . import chairs, parts, tex_sala
from . import furniture_forms as forms
from .composite import Composite
from .kit import MeshBuilder
from .placement import against_wall, floor_z, place

WALL_OFFSET = 0.004


def art_for(name):
    """Versão ampliada e suave da foto ou do quadro do kit (`art_<nome>`), se existir; senão o próprio material."""
    return f"art_{name}" if name in tex_sala.ART_SOURCES else name


def wall_spot(room, wall, along, gap=0.0):
    """(x, y, yaw) sobre a face interna da parede `wall`, com a frente da peça voltada para o cômodo."""
    return against_wall(room, wall, along, gap * 2)


# ---------------------------------------------------------------------------
# Cadeiras
# ---------------------------------------------------------------------------
def make_chair(ctx, room, x, y, yaw=0.0, *, z=None, style="dining", fallen=False, tucked=False,
               cushion="fabric_gray", name=None, booster=None):
    """Cadeira; `style`: dining | office | kid. `fallen=True` deixa a peça caída para trás.

    `booster` (material) acrescenta uma almofada alta no assento, como a da cadeira da Emma.
    """
    asm = chairs.new_chair(name or f"chair_{room}")
    cover = chairs.SEAT_COVERS.get(cushion, cushion)
    with asm.at(0, 0, 0, rx=96 if fallen else 0, rz=12 if fallen else 0):
        if style == "dining":
            chairs.dining_chair(asm, cover, booster=chairs.SEAT_COVERS.get(booster, booster))
        elif style == "office":
            chairs.office_chair(asm, cover)
        else:
            chairs.kid_chair(asm, "painted_pink")
    if fallen:
        asm.drop_to_floor()
    return place(ctx, asm, room, f"chair_{style}", x, y, yaw, z, name=name, tucked=tucked)


def make_side_table(ctx, room, wall, along, *, width=0.8, depth=0.34, height=0.74, name=None):
    """Mesinha de encostar: tampo moldurado, friso com gaveta de puxador de alça e pernas torneadas afinadas."""
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Composite(name or "side_table", wood=forms.WOOD, round=forms.SMOOTH)
    wood = asm.wood
    top = 0.035
    forms.slab(asm.round, 0, 0, height - top, width, depth, forms.THIN_EDGE, "walnut", radius=0.03)
    apron_h = 0.10
    wood.box(0, 0, height - top - apron_h, width - 0.07, depth - 0.07, apron_h, "walnut")
    drawer_w = min(0.42, width - 0.22)
    wood.box(0, depth / 2 - 0.036, height - top - apron_h + 0.012, drawer_w, 0.012, apron_h - 0.024, "oak")
    forms.bail_pull(wood, 0, depth / 2 - 0.026, height - top - apron_h / 2 + 0.004, 0.07, "brass_aged")
    for sx in (-1, 1):
        for sy in (-1, 1):
            forms.turned_leg(asm.round, sx * (width / 2 - 0.04), sy * (depth / 2 - 0.04), 0.0, height - top - 0.002, 0.024,
                             "walnut_v", "tapered")
    return place(ctx, asm, room, "side_table", x, y, yaw, name=name)


def make_photo_frame(ctx, room, x, y, z, yaw, art, *, fallen=False, width=0.13, height=0.17, name=None):
    """Porta-retrato de mesa com pé de apoio; `fallen=True` deixa tombado de bruços (só o verso de papelão aparece)."""
    m = MeshBuilder(name or "photo_frame")
    with m.at(0, 0, 0, rx=-90 if fallen else 8, rz=28 if fallen else 0):
        parts.picture(m, 0, 0, height / 2 + 0.01, width, height, art_for(art), frame_mat="walnut", border=0.014, depth=0.014)
        with m.at(0, -0.07, 0.01, rx=-24):
            m.box(0, 0, 0, 0.03, 0.004, height * 0.62, "oak")
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
    parts.picture(m, 0, 0.018, 0, width, height, art_for(art), frame_mat=frame)
    return place(ctx, m, room, "picture", x, y, yaw, floor_z(room) + z, mode="wall", name=name)


def make_wall_decal(ctx, room, wall, along, z, width, height, texture, *, name=None):
    """Marca rente à parede (mãos, manchas): um quad com alfa a 4 mm da superfície."""
    x, y, yaw = wall_spot(room, wall, along)
    m = MeshBuilder(name or f"decal_{room}")
    m.panel(0, WALL_OFFSET, 0, width, height, texture, "front")
    return place(ctx, m, room, "decal", x, y, yaw, floor_z(room) + z, mode="wall", name=name)


# ---------------------------------------------------------------------------
# Tapetes
# ---------------------------------------------------------------------------
SOFT_RUGS = {"rug_living", "rug_den", "rug_dining", "doormat"}


def _soft_rug(m, rng, width, depth, texture, curl_corner):
    """Tapete macio: superfície ondulada com a borda enrolada para baixo, franjas nas pontas e um canto levantado."""
    thickness = 0.017
    nu, nv = max(8, int(width * 14)), max(8, int(depth * 14))
    phase = rng.uniform(0, 6.28)

    def height_at(u, v):
        x, y = (u - 0.5) * width, (v - 0.5) * depth
        edge = min(u * width, (1 - u) * width, v * depth, (1 - v) * depth)
        roll = math.sqrt(forms.smooth01(edge / 0.05))
        z = 0.003 + (thickness - 0.003) * roll
        z += 0.0035 * math.sin(2 * math.pi * 2.3 * u + phase) * math.sin(2 * math.pi * 1.9 * v + 0.6 * phase)
        if curl_corner:
            cx, cy = curl_corner[0] * width / 2, curl_corner[1] * depth / 2
            z += 0.04 * math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / 0.018)
        return (x, y, z)

    m.surface(height_at, nu, nv, texture, uv_size=(1.0, 1.0), smooth=True)
    strands = int(width * 55)
    for side in (-1, 1):
        for index in range(strands):
            x = (index + 0.5) / strands * width - width / 2
            reach = rng.uniform(0.05, 0.075)
            with m.at(x, side * depth / 2, 0.0, rz=rng.uniform(-6, 6)):
                m.box(0, side * reach / 2, 0.0, 0.0065, reach, 0.0022, "rug_fringe")


def make_rug(ctx, room, x, y, yaw, width, depth, texture, *, round_shape=False, tile_along=False, name=None):
    """Tapete rente ao piso (não colide, pode cruzar zonas reservadas). `tile_along` repete o padrão no comprimento."""
    m = MeshBuilder(name or f"rug_{room}")
    if texture in SOFT_RUGS:
        m.finish = craft.RAW
        _soft_rug(m, ctx.rng, width, depth, texture, curl_corner=(1, -1) if texture == "rug_living" else None)
        return place(ctx, m, room, "rug", x, y, yaw, mode="flat", name=name)
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
    """Pilha de caixas de papelão com abas dobradas e fita; `layers` é uma lista de escalas/deslocamentos por camada."""
    m = MeshBuilder(name or f"boxes_{room}")
    z = 0.0
    for scale, dx, dy, turn in layers:
        w, d, h = size[0] * scale, size[1] * scale, size[2] * scale
        with m.at(dx, dy, z, rz=turn):
            m.box(0, 0, 0, w, d, h, texture, mats={"front": label or texture}, uv=1.6)
            m.box(0, 0, h, w * 0.5, d, 0.004, texture, uv=1.6)
            m.box(0, 0, h, w * 0.02, d, 0.003, "tape_silver")
            for side in (-1, 1):
                with m.at(side * w / 4, 0, h + 0.002, ry=-side * 11):
                    m.box(side * w * 0.02, 0, 0, w * 0.5, d - 0.004, 0.004, texture, uv=1.6)
        z += h
    return place(ctx, m, room, "boxes", x, y, yaw, name=name)


def make_cup(ctx, room, x, y, z, *, glass=False):
    """Xícara esquecida sobre uma superfície (o café frio do Dan)."""
    m = MeshBuilder("cup")
    if glass:
        parts.mug(m, 0, 0, 0, 0.04, 0.09, "glass_clear")
    else:
        parts.mug(m, 0, 0, 0, 0.04, 0.09, "ceramic_cream", coffee=True)
    return place(ctx, m, room, "cup", x, y, ctx.rng.uniform(0, math.tau), z, mode="decor")
