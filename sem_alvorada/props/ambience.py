"""Peças pequenas de ambientação do térreo: o que Daniel, Laura e Emma deixaram pela casa.

Cada função cria um objeto de enfeite (`decor`, apoiado numa superfície ou no chão) ou rente ao piso (`flat`)
e conta uma coisa: o jornal sobre o sofá, as pantufas ao lado, os blocos da Emma, a mochila rosa jogada, a
garrafa vazia e o remédio sobre a mesa do escritório.
"""
import math

from .. import craft
from . import furniture_forms as forms
from . import materials, parts, tex_den  # noqa: F401  (registra o jornal e as folhas impressas)
from . import small_things as things
from .kit import MeshBuilder
from .placement import place

materials.SPECS.update({
    "slipper_fleece": materials.Spec(color=(0.20, 0.20, 0.22), roughness=1.0),
    "backpack_pink": materials.Spec(color=(0.52, 0.22, 0.34), roughness=0.8),
    "strap_dark": materials.Spec(color=(0.05, 0.05, 0.06), roughness=0.9),
    "amber_glass": materials.Spec(color=(0.18, 0.08, 0.02), roughness=0.1),
    "whisky": materials.Spec(color=(0.30, 0.13, 0.03), roughness=0.08),
    "wire_basket": materials.Spec(color=(0.05, 0.05, 0.055), roughness=0.5, metallic=0.8),
    "pen_blue": materials.Spec(color=(0.05, 0.10, 0.42), roughness=0.4),
    "folder_manila": materials.Spec(color=(0.46, 0.38, 0.22), roughness=0.85),
})


def _builder(name, finish=forms.SMOOTH):
    builder = MeshBuilder(name)
    builder.finish = finish
    return builder


def make_slippers(ctx, room, x, y, yaw, z=0.0):
    """Pantufas de lã cinzentas do Dan, uma virada para o lado como quem as tirou de qualquer jeito."""
    m = _builder("slippers")
    for side, turn in ((-1, 0), (1, 38)):
        with m.at(side * 0.065, 0.0, 0.0, rz=turn):
            m.soft_box(0, 0, 0.0, 0.095, 0.29, 0.02, "rubber", radius=0.04, edge=0.008, corner_points=4)
            m.soft_box(0, 0.05, 0.016, 0.092, 0.17, 0.05, "slipper_fleece", radius=0.04, edge=0.02, corner_points=4)
            m.soft_box(0, -0.08, 0.016, 0.082, 0.07, 0.025, "slipper_fleece", radius=0.03, edge=0.01, corner_points=4)
    return place(ctx, m, room, "slippers", x, y, yaw, z, mode="decor")


def _letter_block(m, texture, size=0.052):
    """Cubo com a letra impressa em cada face (UV de 0 a 1 por face, para a letra caber)."""
    half = size / 2
    for facing, offset in (("front", (0, half, half)), ("back", (0, -half, half)), ("right", (half, 0, half)),
                           ("left", (-half, 0, half))):
        m.panel(offset[0], offset[1], offset[2], size, size, texture, facing)
    m.panel(0, 0, size, size, size, texture, "top")


def make_toy_blocks(ctx, room, x, y, z=0.0):
    """Quatro blocos de letras que soletram E-M-M-A numa fileira torta e um quinto caído longe."""
    m = _builder("toy_blocks", craft.STANDARD)
    letters = ("block_e", "block_m", "block_m", "block_a")
    for index, texture in enumerate(letters):
        with m.at(index * 0.062, 0.006 * (-1) ** index, 0.0, rz=ctx.rng.uniform(-18, 18)):
            _letter_block(m, texture)
    with m.at(0.32, 0.12, 0.0, rz=40):
        _letter_block(m, "block_a")
    return place(ctx, m, room, "toy_blocks", x, y, ctx.rng.uniform(0, 6.28), z, mode="decor")


def make_newspaper(ctx, room, x, y, z, yaw):
    """Jornal de terça dobrado ao meio, aberto na página da manchete, caído onde Daniel o largou."""
    m = _builder("newspaper", craft.RAW)
    m.box(0, 0, 0, 0.30, 0.40, 0.007, "paper_white", skip=("top",))
    m.panel(0, 0, 0.0071, 0.30, 0.40, "sheet_b", "top")
    with m.at(0.015, -0.02, 0.0072, rz=-5):
        m.box(0, 0, 0, 0.30, 0.40, 0.004, "paper_white", skip=("top",))
        m.panel(0, 0, 0.0041, 0.30, 0.40, "newspaper", "top")
    return place(ctx, m, room, "newspaper", x, y, yaw, z, mode="decor")


def make_pen_cup(ctx, room, x, y, z):
    """Copo de arame preto com canetas e um lápis em ângulos diferentes."""
    m = _builder("pen_cup")
    m.lathe([(0.0, 0.0), (0.038, 0.0), (0.041, 0.095), (0.0, 0.092)], 0, 0, 0, "wire_basket", seg=forms.seg(14), smooth=True)
    for lean, turn, color, length in ((10, 0, "pen_blue", 0.17), (-12, 70, "toy_red", 0.16), (6, 140, "pen_blue", 0.15),
                                      (-8, 220, "toy_yellow", 0.19)):
        with m.at(0, 0, 0.02, rz=turn, ry=lean):
            m.tube((0, 0.0, 0.0), (0.0, 0.0, length), 0.0042, color, seg=6)
    return place(ctx, m, room, "pen_cup", x, y, 0.0, z, mode="decor")


def make_pill_and_glass(ctx, room, x, y, z):
    """Frasco de remédio aberto e um copo de água pela metade ao lado: a dose que ele não toma."""
    m = _builder("pills")
    things.pill_bottle(m, 0.0, 0.0, 0.0, yaw=0.0)
    things.pill_bottle(m, 0.06, -0.025, 0.0, lying=True, yaw=70)
    things.tumbler(m, -0.07, 0.03, 0.0, fill=0.45, radius=0.033, height=0.1, liquid="glass_clear")
    return place(ctx, m, room, "pills", x, y, 0.0, z, mode="decor")


def make_wastebasket(ctx, room, x, y):
    """Lixeira de arame com bolas de papel amassado, algumas caídas em volta."""
    m = _builder("wastebasket")
    rng = ctx.rng
    m.lathe([(0.0, 0.0), (0.12, 0.0), (0.135, 0.01), (0.17, 0.3), (0.0, 0.29)], 0, 0, 0, "wire_basket",
            seg=forms.seg(18), smooth=True)
    m.torus(0, 0, 0.3, 0.17, 0.004, "wire_basket", seg=forms.seg(18), seg_minor=4)
    for index in range(9):
        spill = index > 5
        angle = rng.uniform(0, 6.28)
        reach = rng.uniform(0.2, 0.3) if spill else rng.uniform(0.0, 0.09)
        radius = rng.uniform(0.03, 0.045)
        m.sphere(reach * math.cos(angle), reach * math.sin(angle), radius * 0.9 if spill else 0.3, radius, "paper_white", seg=7,
                 rings=4, squash=0.9)
    return place(ctx, m, room, "wastebasket", x, y, 0.0, mode="decor")


def make_backpack(ctx, room, x, y, yaw):
    """Mochila rosa da escola da Emma, tombada de lado onde foi largada na última manhã."""
    m = _builder("backpack", forms.PADDING)           # soft_box + subdivisão: o corpo fica macio
    with m.at(0, 0, 0.0, rx=78, ry=8):
        m.soft_box(0, 0, 0.0, 0.30, 0.14, 0.38, "backpack_pink", radius=0.045, edge=0.03)
        m.soft_box(0, 0.085, 0.02, 0.24, 0.05, 0.22, "backpack_pink", radius=0.025, edge=0.015)
        m.soft_box(0.0, 0.0, 0.375, 0.1, 0.03, 0.03, "strap_dark", radius=0.01, edge=0.006)
        for side in (-1, 1):
            m.tube((side * 0.1, -0.07, 0.34), (side * 0.11, -0.12, 0.12), 0.012, "strap_dark", seg=6)
    m.drop_to_floor()
    return place(ctx, m, room, "backpack", x, y, yaw, 0.0, mode="decor")


def make_whisky_set(ctx, room, x, y, z):
    """Garrafa de uísque quase vazia e um copo com um dedo de bebida."""
    m = _builder("whisky")
    parts.bottle(m, 0.0, 0.0, 0.0, 0.04, 0.27, "amber_glass", cap_mat="gilt")
    m.cylinder(0.0, 0.0, 0.0035, 0.0365, 0.045, "whisky", seg=forms.seg(16))
    m.cylinder(0.0, 0.0, 0.09, 0.0403, 0.085, "paper_white", seg=forms.seg(16), smooth=True)
    things.tumbler(m, 0.12, 0.03, 0.0, fill=0.3, radius=0.034, height=0.095, liquid="whisky")
    return place(ctx, m, room, "whisky", x, y, 0.0, z, mode="decor")


def make_folder_stack(ctx, room, x, y, z):
    """Pasta de seguro e de boletim empilhadas, a de cima aberta."""
    m = _builder("folders", craft.RAW)
    rng = ctx.rng
    cursor = 0.0
    for index in range(4):
        with m.at(rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01), cursor, rz=rng.uniform(-8, 8)):
            m.box(0, 0, 0, 0.24, 0.32, 0.006, "folder_manila")
            m.box(-0.1, 0, 0.006, 0.02, 0.32, 0.002, "folder_manila")
        cursor += 0.0075
    with m.at(0.0, 0.0, cursor, rz=6):
        m.box(0, 0, 0, 0.23, 0.31, 0.001, "paper_white", skip=("top",))
        m.panel(0, 0, 0.0011, 0.23, 0.31, "sheet_a", "top")
    return place(ctx, m, room, "folders", x, y, 0.0, z, mode="decor")
