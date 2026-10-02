"""Cozinha: peças públicas (`make_*`) que montam e colocam os móveis; o desenho fica nos módulos `kitchen_*`.

Altura do tampo (0,90 m) e posição do frigobar são lidas por `items.py` (pilha 4 no balcão, nota 5 no frigobar).
"""
import math

from . import kitchen_appliances as appliances
from . import kitchen_cabinets as cabinets
from . import kitchen_decor as decor
from . import kitchen_cloth, kitchen_sink, kitchen_small as small, kitchen_table as dining
from . import kitchen_ware as ware
from .kg_shapes import Assembly, front_limited_box
from .placement import against_wall, flush_center, floor_z, place, room_bounds

COUNTER_HEIGHT = cabinets.TOP_Z
MINI_FRIDGE_DEPTH = appliances.MINI_DEPTH
MINI_FRIDGE_ALONG = 6.40        # posição do frigobar ao longo da parede oeste (y)
MINI_FRIDGE_FRONT_PLATE = appliances.MINI_PLATE
TOP_OVERHANG = 0.022


def mini_fridge_front():
    """(x, y, z) da superfície da porta do frigobar, onde o post-it da Laura fica colado."""
    bounds = room_bounds("kitchen")
    return (bounds.x0 + MINI_FRIDGE_DEPTH + MINI_FRIDGE_FRONT_PLATE, MINI_FRIDGE_ALONG, 0.50)


def make_base_cabinet(ctx, room, wall, along, length, *, depth=0.6, doors=2, drawer=False, name=None):
    """Módulo de balcão com `length` metros ao longo da parede `wall`."""
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Assembly(name or "base_cabinet", wear={"grime_height": 0.4, "seed": 11})
    cabinets.base_cabinet(asm, length, depth, doors=doors, drawer=drawer)
    return place(ctx, asm, room, "counter", x, y, yaw, name=name,
                 collision=front_limited_box(asm, depth / 2 + TOP_OVERHANG, COUNTER_HEIGHT))


def make_sink_unit(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Balcão com pia dupla de aço sob a janela norte; louça suja empilhada, torneira alta e escorredor."""
    cy = flush_center(room, x, y, yaw, kitchen_sink.DEPTH)
    asm = Assembly("kitchen_counter", wear={"grime_height": 0.4, "seed": 7})
    with asm.at(0, cy, 0):
        kitchen_sink.build_sink_unit(asm, ctx.rng)
    return place(ctx, asm, room, "kitchen_counter", x, y, yaw, z, name="kitchen_counter", anchor=anchor,
                 collision=front_limited_box(asm, cy + kitchen_sink.DEPTH / 2 + TOP_OVERHANG, COUNTER_HEIGHT))


def make_corner_counter(ctx, room, x0, y0, x1, y1, *, name="counter_corner"):
    """Balcão em L do canto nordeste: uma perna ao longo do norte (frente para sul) e outra ao longo do leste.

    A perna norte tem só um módulo com porta no trecho visível; o resto é o canto cego atrás da perna leste.
    """
    depth = 0.6
    north_len = x1 - x0
    nx, ny, _ = against_wall(room, "N", (x0 + x1) / 2, depth)
    north = Assembly(name + "_north", wear={"grime_height": 0.4, "seed": 13})
    visible = 0.425
    with north.at(north_len / 2 - visible / 2, 0, 0):
        cabinets.base_cabinet(north, visible, depth, doors=1, top=False)
    cabinets.blind_filler(north, -north_len / 2, north_len / 2 - visible, depth)
    cabinets.laminate_top(north, -north_len / 2, north_len / 2, depth)
    north_obj = place(ctx, north, room, "counter", nx, ny, math.pi, name=name + "_north",
                      collision=front_limited_box(north, depth / 2 + TOP_OVERHANG, COUNTER_HEIGHT))
    east_len = (y1 - y0) - depth - TOP_OVERHANG - 0.012
    ex, ey, yaw_east = against_wall(room, "E", y0 + east_len / 2, depth)
    east = Assembly(name + "_east", wear={"grime_height": 0.4, "seed": 17})
    cabinets.base_cabinet(east, east_len, depth, doors=2)
    east_obj = place(ctx, east, room, "counter", ex, ey, yaw_east, name=name + "_east",
                     collision=front_limited_box(east, depth / 2 + TOP_OVERHANG, COUNTER_HEIGHT))
    return north_obj, east_obj


def make_fridge(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Geladeira de freezer em cima, cantos arredondados, ímãs, desenhos da Emma e recados."""
    cy = flush_center(room, x, y, yaw, appliances.FRIDGE_D)
    asm = Assembly("fridge", wear={"grime_height": 0.55, "seed": 3})
    with asm.at(0, cy, 0):
        appliances.build_fridge(asm, ctx.rng)
    return place(ctx, asm, room, "fridge", x, y, yaw, z, name="fridge", anchor=anchor,
                 collision=front_limited_box(asm, cy + appliances.FRIDGE_D / 2))


def make_mini_fridge(ctx, room, wall, along, *, width=appliances.MINI_W, depth=MINI_FRIDGE_DEPTH):
    """Frigobar embutido no balcão da parede oeste."""
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Assembly("mini_fridge", wear={"grime_height": 0.5, "seed": 5})
    appliances.build_mini_fridge(asm, ctx.rng)
    front = depth / 2 + MINI_FRIDGE_FRONT_PLATE       # o puxador fica de fora: o post-it não pode cair dentro
    return place(ctx, asm, room, "mini_fridge", x, y, yaw,
                 collision=[(-width / 2, -depth / 2, 0.0, width / 2, front, 0.90)])


def make_stove(ctx, room, wall, along):
    """Fogão de quatro bocas com a chaleira, a frigideira e uma panela frios sobre as bocas."""
    x, y, yaw = against_wall(room, wall, along, appliances.STOVE_D)
    asm = Assembly("stove", wear={"grime_height": 0.5, "seed": 19})
    appliances.build_stove(asm, ctx.rng)
    return place(ctx, asm, room, "stove", x, y, yaw, collision=front_limited_box(asm, appliances.STOVE_D / 2))


def make_oven_towel(ctx, room, stove):
    """Pano de prato xadrez jogado sobre a barra do forno: metade pende para a sala, metade fica colada na porta."""
    bar_x = stove.location.x - (appliances.STOVE_D / 2 + 0.012 + 0.045)
    bar_y, bar_z = stove.location.y + 0.06, 0.675
    size = (0.42, 0.30)
    return kitchen_cloth.hang_cloth(ctx, room, "dish_towel_kitchen", [stove], (bar_x - size[0] / 2, bar_y - size[1] / 2, bar_z + 0.07),
                                    size, "kg_towel", repeat=2.0)


def make_range_hood(ctx, room, wall, along):
    """Coifa de aço sobre o fogão, da copa ao forro."""
    depth = 0.46
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Assembly("range_hood", wear={"grime_height": 2.6, "seed": 23})
    with asm.at(0, -depth / 2, 0):
        appliances.build_hood(asm, ctx.rng)
    return place(ctx, asm, room, "range_hood", x, y, yaw, mode="wall")


def make_wall_cabinets(ctx, room, wall, along, length, *, z0=1.5, height=0.7, depth=0.34, ajar=True):
    """Armários altos pendurados na parede, com uma porta entreaberta mostrando a louça."""
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Assembly("wall_cabinets", wear={"grime_height": 3.0, "seed": 29})

    def stock(builder, shelf_z, x_left, x_right):
        count = max(2, round(length / 0.5))
        door_x0, door_x1 = cabinets.door_openings(length, count)[1]
        cx = (door_x0 + door_x1) / 2
        ware.plate_stack(builder, ctx.rng, cx - 0.05, 0.0, shelf_z, 6, 0.1)
        ware.mug(builder, cx + 0.13, 0.03, shelf_z, 0.038, 0.09, handle_deg=20.0)

    cabinets.wall_cabinet(asm, length, depth, z0, height, open_door=1 if ajar else None, open_deg=30.0,
                          stock=stock if ajar else None)
    return place(ctx, asm, room, "wall_cabinets", x, y, yaw, mode="wall")


def make_microwave(ctx, room, x, y, z, yaw):
    """Micro-ondas na bancada leste, com o display parado em 6:12."""
    return _decor(ctx, room, "microwave", small.build_microwave, x, y, z, yaw)


def make_coffee_maker(ctx, room, x, y, z, yaw):
    """Cafeteira com a jarra ainda cheia de café frio de ontem."""
    return _decor(ctx, room, "coffee_maker", small.build_coffee_maker, x, y, z, yaw)


def make_kitchen_table(ctx, room, x, y):
    """Mesinha do café da manhã: tigelas de cereal secas, a caixa de cereal, o jornal de ontem e o remédio."""
    asm = Assembly("kitchen_table", wear={"grime_height": 0.8, "seed": 31})
    dining.build_table(asm, ctx.rng)
    half = dining.TABLE_SIZE / 2
    return place(ctx, asm, room, "kitchen_table", x, y, 0.0, name="kitchen_table",
                 collision=[(-half, -half, 0.0, half, half, dining.TABLE_TOP)])


def make_kitchen_chair(ctx, room, x, y, yaw, *, tucked=True):
    """Cadeira de tubo cromado com vinil vermelho; `tucked` a deixa enfiada sob a mesa."""
    asm = Assembly("kitchen_chair", wear={"grime_height": 0.5, "seed": 37})
    dining.build_chair(asm, ctx.rng)
    return place(ctx, asm, room, "chair_kitchen", x, y, yaw, tucked=tucked)


def make_trash_bin(ctx, room, x, y):
    """Lixeira de pedal transbordando, na entrada da cozinha."""
    asm = Assembly("trash_bin", wear={"grime_height": 0.4, "seed": 41})
    dining.build_trash_bin(asm, ctx.rng)
    return place(ctx, asm, room, "trash_bin", x, y, -math.pi / 2, name="trash_bin_kitchen",
                 collision=[(-0.175, -0.175, 0.0, 0.175, 0.175, 0.62)])


def _decor(ctx, room, kind, build, x, y, z, yaw, wear=None, name=None):
    """Peça pequena apoiada em `z` (sem colisão)."""
    asm = Assembly(name or kind, wear=wear)
    build(asm, ctx.rng)
    return place(ctx, asm, room, kind, x, y, yaw, z, mode="decor", name=name)


def make_ambience(ctx, room):
    """Bancadas e paredes: o que a casa guardou do dia em que ela parou."""
    top = COUNTER_HEIGHT
    _decor(ctx, room, "toaster", small.build_toaster, 8.36, 5.45, top, -math.pi / 2)
    _decor(ctx, room, "bread_board", small.build_bread_board, 8.36, 5.82, top, -math.pi / 2 + 0.2)
    _decor(ctx, room, "fruit_bowl", small.build_fruit_bowl, 8.37, 6.40, top, 0.0)
    _decor(ctx, room, "knife_block", small.build_knife_block, 8.30, 6.88, top, -math.pi / 2)
    _decor(ctx, room, "spice_rack", small.build_spice_rack, 8.17, 7.22, top, -math.pi / 2)
    _decor(ctx, room, "paper_towel", small.build_paper_towel, 8.30, 7.50, top, 0.0)
    asm = Assembly("wall_clock_kitchen")
    decor.wall_clock(asm, 0.0, 0.0, 0.0)
    x, y, yaw = against_wall(room, "S", 8.55, 0.0)
    place(ctx, asm, room, "wall_clock", x, y, yaw, floor_z(room) + 2.05, mode="wall", name="wall_clock_kitchen")
    asm = Assembly("calendar_kitchen")
    decor.paper_sheet(asm, 0.0, 0.0, 0.004, 0.30, 0.41, "kg_calendar", 0.0)
    asm.round.cylinder(0.0, 0.0, 0.2, 0.004, 0.004, "toy_red", seg=6)
    x, y, yaw = against_wall(room, "S", 8.55, 0.0)
    place(ctx, asm, room, "calendar", x, y, yaw, floor_z(room) + 1.5, mode="wall", name="calendar_kitchen")
