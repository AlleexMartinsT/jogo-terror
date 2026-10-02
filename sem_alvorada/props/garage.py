"""Garagem: peças públicas (`make_*`) que montam e colocam bancada, painel, estante, freezer, bicicleta e o resto.

O desenho de cada peça fica nos módulos `garage_*`. Alturas lidas por outros módulos: o tampo da bancada (0,90 m,
pilha 5) e a tábua do degrau de 1 m da estante (guia do reboque, nota 7).
"""
import math

from . import garage_bench as bench
from . import garage_bicycle as bicycle
from . import garage_clutter as clutter
from . import garage_machines as machines
from . import garage_storage as storage
from .kg_shapes import Assembly, front_limited_box
from .placement import against_wall, flush_center, floor_z, place

BENCH_TOP = bench.TOP
SHELF_TIERS = storage.SHELF_TIERS
NOTE_TIER = storage.NOTE_TIER
NOTE_TIER_LIMIT = storage.NOTE_TIER_LIMIT


def make_workbench(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Bancada de tábuas grossas sob a janela leste, com gavetas, morsa e o que ficou em cima quando o Dan parou."""
    cy = flush_center(room, x, y, yaw, bench.DEPTH)
    asm = Assembly("workbench", wear={"grime_height": 0.6, "seed": 43})
    with asm.at(0, cy, 0):
        bench.build_bench(asm, ctx.rng)
    low, high = asm.bounds()
    body = [(low[0], cy - bench.DEPTH / 2, 0.0, high[0], cy + bench.DEPTH / 2, BENCH_TOP)]
    return place(ctx, asm, room, "workbench", x, y, yaw, z, name="workbench", anchor=anchor, collision=body)


def make_tool_panel(ctx, room, wall, along, z_center, *, width=1.7, height=0.9):
    """Painel perfurado com as ferramentas penduradas; o contorno do martelo ficou vazio."""
    x, y, yaw = against_wall(room, wall, along, 0.0)
    asm = Assembly("tool_panel")
    storage.build_tool_panel(asm, ctx.rng, width, height)
    return place(ctx, asm, room, "tool_panel", x, y, yaw, floor_z(room) + z_center + height / 2, mode="wall")


def make_garage_shelves(ctx, room, wall, along, *, width=2.5, depth=0.4, height=1.85):
    """Estante de aço com caixas, latas e potes; o degrau de 1 m fica livre no trecho do guia do reboque."""
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Assembly("garage_shelves", wear={"grime_height": 0.9, "seed": 47})
    storage.build_shelves(asm, ctx.rng, width, depth, height)
    # proxy só no fundo da estante: o jogador para na beira dela e o guia do reboque fica fora do volume
    back_only = [(-width / 2, -depth / 2, 0.0, width / 2, -depth / 2 + 0.12, height)]
    return place(ctx, asm, room, "garage_shelves", x, y, yaw, collision=back_only)


def make_chest_freezer(ctx, room, wall, along):
    """Freezer horizontal velho e amarelado, com a tampa riscada e um cadeado."""
    x, y, yaw = against_wall(room, wall, along, machines.FREEZER_D)
    asm = Assembly("chest_freezer", wear={"grime_height": 0.6, "seed": 53})
    machines.build_freezer(asm, ctx.rng)
    return place(ctx, asm, room, "chest_freezer", x, y, yaw, collision=front_limited_box(asm, machines.FREEZER_D / 2 + 0.01))


def make_water_heater(ctx, room, x, y):
    """Aquecedor de água com canos de cobre, válvula de alívio, exaustão até o forro e a poça de ferrugem."""
    asm = Assembly("water_heater", wear={"grime_height": 0.9, "seed": 59})
    machines.build_heater(asm, ctx.rng)
    r = machines.HEATER_RADIUS
    return place(ctx, asm, room, "water_heater", x, y, math.pi,
                 collision=[(-r - 0.02, -r - 0.02, 0.0, r + 0.02, r + 0.02, machines.HEATER_HEIGHT)])


def make_lawn_mower(ctx, room, x, y, yaw):
    """Cortador de grama a gasolina de empurrar, com o saco de grama e o guidão dobrado."""
    asm = Assembly("lawn_mower", wear={"grime_height": 0.4, "seed": 61})
    machines.build_mower(asm, ctx.rng)
    return place(ctx, asm, room, "lawn_mower", x, y, yaw)


def make_kids_bicycle(ctx, room, x, y, yaw):
    """Bicicleta rosa da Emma, com rodinhas, cestinha, fitas no guidão e o capacete."""
    asm = Assembly("kids_bicycle", wear={"grime_height": 0.5, "seed": 67})
    bicycle.build_bicycle(asm, ctx.rng)
    return place(ctx, asm, room, "kids_bicycle", x, y, yaw)


def make_box_pile(ctx, room, x, y, yaw, layers, label, name=None):
    """Pilha de caixas de papelão fechadas com fita e rótulo à caneta."""
    asm = Assembly(name or "boxes")
    storage.box_pile(asm, ctx.rng, layers, label)
    return place(ctx, asm, room, "boxes", x, y, yaw, name=name)


def _decor(ctx, room, kind, build, x, y, z, yaw, mode="decor", name=None, wear=None):
    asm = Assembly(name or kind, wear=wear)
    build(asm, ctx.rng)
    return place(ctx, asm, room, kind, x, y, yaw, z, mode=mode, name=name)


def make_floor_stain(ctx, room, x, y, yaw, width, depth, name):
    """Mancha de óleo no concreto: um quad com alfa 6 mm acima do piso."""
    asm = Assembly(name)
    asm.round.panel(0, 0, 0, width, depth, "kg_oil_stain", "top")
    return place(ctx, asm, room, "decal", x, y, yaw, floor_z(room) + 0.006, mode="flat", name=name)


def make_cobweb(ctx, room, wall, along, z_top, size, name):
    """Teia de aranha na quina de uma parede com o forro: um quad com alfa, o vértice do leque no canto de cima."""
    x, y, yaw = against_wall(room, wall, along, 0.0)
    asm = Assembly(name)
    asm.round.panel(size / 2 * (1 if along >= 0 else -1), 0.004, -size / 2, size, size, "kg_cobweb", "front")
    return place(ctx, asm, room, "cobweb", x, y, yaw, floor_z(room) + z_top, mode="wall", name=name)


def make_ambience(ctx, room):
    """Tralhas e marcas de uso: a casa guardou o que o Dan deixou onde parou."""
    _decor(ctx, room, "ladder", clutter.build_ladder, 13.45, 6.57, floor_z(room), math.pi)
    _decor(ctx, room, "yard_tools", clutter.build_tool_leaners, 12.5, 6.58, floor_z(room), math.pi)
    _decor(ctx, room, "toolbox", clutter.build_toolbox, 17.35, 4.75, floor_z(room), math.radians(-70))
    _decor(ctx, room, "jerrycan", clutter.build_jerrycan, 18.12, 0.42, floor_z(room), math.radians(90))
    _decor(ctx, room, "spare_tires", clutter.build_tires, 12.62, 5.0, floor_z(room), 0.0)
    for index, (x, y, tone) in enumerate(((17.6, 6.55, "toy_blue"), (17.62, 6.25, "toy_green"))):
        _decor(ctx, room, "paint_can", lambda asm, rng, c=tone: storage.paint_can(asm, 0.0, 0.0, 0.0, c, True), x, y,
               floor_z(room), 0.0, name=f"paint_can_floor_{index + 1}")
    _decor(ctx, room, "hose", clutter.build_hose, 18.34, 5.2, floor_z(room) + 1.45, -math.pi / 2, mode="wall")
    _decor(ctx, room, "extension_cord", clutter.build_cord_coil, 12.42, 1.35, 0.907, 0.4)
    _decor(ctx, room, "bare_bulb", clutter.build_bare_bulb, 17.2, 3.2, floor_z(room) + 2.15, 0.0, mode="wall")
    make_floor_stain(ctx, room, 17.2, 0.75, 0.6, 0.6, 0.45, "stain_mower_garage")
    make_floor_stain(ctx, room, 15.9, 5.2, -0.5, 0.5, 0.35, "stain_door_garage")
    make_cobweb(ctx, room, "N", 13.3, 2.6, 0.55, "cobweb_garage_nw")
    make_cobweb(ctx, room, "W", 6.7, 2.6, 0.5, "cobweb_garage_w")
    make_cobweb(ctx, room, "N", 18.2, 2.6, 0.5, "cobweb_garage_ne")
