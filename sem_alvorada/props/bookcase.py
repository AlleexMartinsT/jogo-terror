"""Estantes com livros individuais e bibelôs.

Cada livro é uma caixa de 10 triângulos cuja lombada, capa e páginas vêm de células do atlas `book_atlas`
(ver `tex_sala`): variam a cor, a altura, a espessura e a inclinação, e nenhum dois lados se repetem em
fila. A estante é de carvalho, com rodapé, cornija e fundo.
"""
import math

from .. import craft
from . import furniture_forms as forms
from . import tex_sala
from .composite import Composite
from .placement import against_wall, place

BOOK_MATERIAL = "book_atlas"
BOOK_FINISH = craft.Finish(bevel=0.0, smooth_angle=60)


def book(m, x, y, z0, thickness, depth, height, rng, *, lean=0.0, turn=0.0, lying=False):
    """Livro em pé (lombada para +Y) ou deitado, apoiado em z0; `lean` em graus inclina o topo para o lado."""
    spine = tex_sala.book_atlas_cell("spine", rng.randrange(20))
    cover = tex_sala.book_atlas_cell("cover", rng.randrange(4))
    pages = tex_sala.book_atlas_cell("pages", rng.randrange(4))
    with m.at(x, y, z0, ry=lean, rz=turn, rx=-90 if lying else 0):
        _book_box(m, thickness, depth, height, spine, cover, pages)


def _uv_rect(cell, flip=False):
    u0, v0, u1, v1 = cell
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)] if not flip else [(u1, v0), (u0, v0), (u0, v1), (u1, v1)]


def _book_box(m, thickness, depth, height, spine, cover, pages):
    x0, x1, y0, y1 = -thickness / 2, thickness / 2, -depth / 2, depth / 2
    m.quad((x1, y1, 0), (x0, y1, 0), (x0, y1, height), (x1, y1, height), BOOK_MATERIAL, uv=_uv_rect(spine))
    m.quad((x0, y0, height), (x1, y0, height), (x1, y1, height), (x0, y1, height), BOOK_MATERIAL, uv=_uv_rect(pages))
    m.quad((x0, y0, 0), (x1, y0, 0), (x1, y0, height), (x0, y0, height), BOOK_MATERIAL, uv=_uv_rect(pages))
    m.quad((x1, y0, 0), (x1, y1, 0), (x1, y1, height), (x1, y0, height), BOOK_MATERIAL, uv=_uv_rect(cover))
    m.quad((x0, y1, 0), (x0, y0, 0), (x0, y0, height), (x0, y1, height), BOOK_MATERIAL, uv=_uv_rect(cover, True))


def fill_shelf(m, rng, x0, x1, y, shelf_top, clearance, depth, *, density=0.85, decor=None):
    """Enche uma prateleira de `x0` a `x1` com livros em pé, tombados e pilhas deitadas; `decor` reserva um vão."""
    if decor is None:
        _fill_run(m, rng, x0, x1, y, shelf_top, clearance, depth, density)
        return
    split = rng.uniform(x0 + 0.25, x1 - 0.45)
    _fill_run(m, rng, x0, split, y, shelf_top, clearance, depth, density)
    decor(m, split + 0.05, y, shelf_top, rng)
    _fill_run(m, rng, split + 0.22, x1, y, shelf_top, clearance, depth, density)


def _fill_run(m, rng, x0, x1, y, shelf_top, clearance, depth, density):
    cursor = x0
    while cursor < x1 - 0.03:
        roll = rng.random()
        if roll > density:
            cursor += rng.uniform(0.04, 0.12)
            continue
        if roll > density - 0.07 and x1 - cursor > 0.3:
            cursor = _lying_stack(m, rng, cursor, y, shelf_top, depth, clearance)
            continue
        run = rng.randrange(3, 9)
        lean_end = rng.random() < 0.22
        for index in range(run):
            thick = rng.uniform(0.016, 0.05)
            if cursor + thick > x1 - 0.015:
                break
            height = rng.uniform(0.66, 0.97) * clearance
            book_depth = depth * rng.uniform(0.72, 0.94)
            lean = 0.0
            shift = 0.0
            if lean_end and index == run - 1:
                lean = rng.uniform(5, 14)
                shift = math.sin(math.radians(lean)) * height / 2
            book(m, cursor + thick / 2 + shift, y - (depth - book_depth) / 2 + 0.01, shelf_top, thick, book_depth, height,
                 rng, lean=lean)
            cursor += thick + rng.uniform(0.0005, 0.004) + abs(shift) * 1.2
        cursor += rng.uniform(0.0, 0.01)


def _lying_stack(m, rng, cursor, y, shelf_top, depth, clearance):
    """Pilha de livros deitados (a lombada para a frente) e devolve onde a prateleira continua."""
    width = rng.uniform(0.20, 0.27)
    z = shelf_top
    for _ in range(rng.randrange(2, 5)):
        thick = rng.uniform(0.022, 0.045)
        if z + thick > shelf_top + clearance * 0.8:
            break
        with m.at(cursor + width / 2 + rng.uniform(-0.01, 0.01), y, z, rz=rng.uniform(-6, 6)):
            spine = tex_sala.book_atlas_cell("spine", rng.randrange(20))
            cover = tex_sala.book_atlas_cell("cover", rng.randrange(4))
            pages = tex_sala.book_atlas_cell("pages", rng.randrange(4))
            _lying_book(m, width, depth * rng.uniform(0.72, 0.9), thick, spine, cover, pages)
        z += thick
    return cursor + width + 0.02


def _lying_book(m, width, depth, thick, spine, cover, pages):
    x0, x1, y0, y1 = -width / 2, width / 2, -depth / 2, depth / 2
    # capa de cima e de baixo (texto das lombadas fica na frente, +Y)
    m.quad((x0, y0, thick), (x1, y0, thick), (x1, y1, thick), (x0, y1, thick), BOOK_MATERIAL, uv=_uv_rect(cover))
    m.quad((x1, y1, 0), (x0, y1, 0), (x0, y1, thick), (x1, y1, thick), BOOK_MATERIAL, uv=_uv_rect(spine))
    m.quad((x0, y0, 0), (x1, y0, 0), (x1, y0, thick), (x0, y0, thick), BOOK_MATERIAL, uv=_uv_rect(pages))
    m.quad((x1, y0, 0), (x1, y1, 0), (x1, y1, thick), (x1, y0, thick), BOOK_MATERIAL, uv=_uv_rect(pages))
    m.quad((x0, y1, 0), (x0, y0, 0), (x0, y0, thick), (x0, y1, thick), BOOK_MATERIAL, uv=_uv_rect(pages))


# ---------------------------------------------------------------------------
# Bibelôs
# ---------------------------------------------------------------------------
def vase_ornament(m, x, y, z, rng):
    """Vaso de cerâmica com a boca estreita (sem flores)."""
    radius = rng.uniform(0.035, 0.05)
    m.lathe([(0.55 * radius, 0.0), (radius, 0.03), (radius * 1.05, 0.08), (radius * 0.7, 0.14), (radius * 0.4, 0.17),
             (radius * 0.5, 0.19)], x, y, z, "porcelain_old", seg=forms.seg(14), smooth=True)


def candlestick_ornament(m, x, y, z, rng):
    m.lathe([(0.04, 0.0), (0.04, 0.008), (0.012, 0.02), (0.018, 0.06), (0.012, 0.10), (0.022, 0.115), (0.008, 0.12)],
            x, y, z, "brass_aged", seg=forms.seg(12), smooth=True)
    m.cylinder(x, y, z + 0.12, 0.011, 0.11, "candle", seg=8)


def frame_ornament(m, x, y, z, rng):
    art = rng.choice(("photo_trio", "photo_mother_child", "photo_father_child"))
    with m.at(x + 0.05, y, z, rz=rng.uniform(-10, 10)):
        m.panel(0, 0.012, 0.085, 0.09, 0.12, art, "front")
        m.box(0, 0.0, 0.0, 0.11, 0.02, 0.01, "oak")
        forms.mitred_frame(m, 0, 0.014, 0.085, 0.09, 0.12, ((0.0, 0.0), (0.005, 0.004), (0.014, 0.004), (0.016, 0.0)), "oak")


def clock_ornament(m, x, y, z, rng):
    """Despertador de mesa parado, de plástico bege."""
    m.soft_box(x + 0.05, y, z, 0.1, 0.05, 0.09, "plastic_beige", radius=0.015, edge=0.008)
    m.panel(x + 0.05, y + 0.0255, z + 0.05, 0.07, 0.07, "clock_face", "front")


ORNAMENTS = (vase_ornament, candlestick_ornament, frame_ornament, clock_ornament)


# ---------------------------------------------------------------------------
# Estante
# ---------------------------------------------------------------------------
def make_bookcase(ctx, room, wall, along, *, width=1.5, height=1.9, depth=0.32, shelves=5, fill=0.85,
                  z=None, name=None):
    """Estante de carvalho encostada em `wall`: rodapé, cornija, fundo e prateleiras cheias de livros individuais."""
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Composite(name or "bookcase", wood=forms.WOOD, round=forms.SMOOTH, books=BOOK_FINISH)
    _carcass(asm.wood, asm.round, width, height, depth)
    gap = (height - 0.20) / shelves
    for level in range(shelves):
        board_z = 0.11 + level * gap
        if level:
            asm.wood.box(0, 0.005, board_z, width - 0.07, depth - 0.03, 0.018, "oak")
        decor = ctx.rng.choice(ORNAMENTS) if level in (1, shelves - 2) else None
        fill_shelf(asm.books, ctx.rng, -width / 2 + 0.05, width / 2 - 0.05, -0.01, board_z + 0.018, gap - 0.03,
                   depth - 0.07, density=fill, decor=decor)
    return place(ctx, asm, room, "bookcase", x, y, yaw, z, name=name)


def _carcass(wood, round_part, width, height, depth):
    wood.box(0, 0.008, 0.0, width - 0.04, depth - 0.03, 0.09, "oak")                       # rodapé recuado
    forms.slab(round_part, 0, 0.0, 0.09, width, depth, [(0, 0.015), (0.010, 0.006), (0.020, 0.0)], "oak", radius=0.006)
    for side in (-1, 1):
        wood.box(side * (width / 2 - 0.0175), 0, 0.11, 0.035, depth, height - 0.14, "oak_v")
        wood.box(side * (width / 2 - 0.0175), depth / 2 - 0.008, 0.11, 0.04, 0.012, height - 0.14, "oak_v")
    wood.box(0, -depth / 2 + 0.01, 0.11, width - 0.07, 0.012, height - 0.14, "case_inside")
    wood.box(0, 0.0, 0.11, width - 0.07, depth - 0.03, 0.018, "oak")                       # fundo
    wood.box(0, depth / 2 - 0.01, height - 0.09, width - 0.07, 0.02, 0.07, "oak")           # testeira
    forms.slab(round_part, 0, 0.015, height - 0.03, width - 0.02, depth + 0.004, forms.CORNICE, "oak", radius=0.008)
