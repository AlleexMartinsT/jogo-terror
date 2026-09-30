"""Cozinha: geladeira, fogão, balcões, pia, frigobar, armários altos, mesinha e a louça por lavar."""
import math

from . import parts
from .kit import MeshBuilder
from .placement import against_wall, flush_center, place

COUNTER_HEIGHT = 0.90
# frente do frigobar (onde o post-it da Laura fica colado): x, y, z (altura acima do piso)
MINI_FRIDGE_FRONT = (8.66, 6.40, 0.50)


def _cabinet_body(m, width, depth, top_mat="laminate", doors=2, body="wood_mid", front="veneer_mid"):
    """Módulo de balcão: caixa, rodapé recuado, portas com puxador e tampo que avança na frente."""
    m.box(0, 0.02, 0.0, width, depth - 0.04, 0.08, "black")
    m.box(0, 0, 0.08, width, depth, 0.78, body, mats={"front": front})
    door_w = (width - 0.03 * (doors + 1)) / doors
    for i in range(doors):
        cx = -width / 2 + 0.03 + door_w / 2 + i * (door_w + 0.03)
        m.box(cx, depth / 2 + 0.006, 0.11, door_w, 0.014, 0.72, "wood_dark")
        parts.knob(m, cx + (door_w / 2 - 0.05 if i % 2 == 0 else -door_w / 2 + 0.05), depth / 2 + 0.018, 0.75, "chrome")
    m.box(0, 0.02, 0.86, width + 0.02, depth + 0.02, 0.04, top_mat)


def make_base_cabinet(ctx, room, wall, along, length, *, depth=0.6, doors=2, name=None):
    """Módulo de balcão com `length` metros ao longo da parede `wall`."""
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder(name or "base_cabinet")
    with m.at(0, 0, 0):
        _cabinet_body(m, length, depth, doors=doors)
    return place(ctx, m, room, "counter", x, y, yaw, name=name)


def make_sink_unit(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Balcão com pia dupla de aço sob a janela norte; louça suja empilhada e a torneira giratória."""
    width, depth = 1.3, 0.6
    cy = flush_center(room, x, y, yaw, depth)
    m = MeshBuilder("kitchen_counter")
    with m.at(0, cy, 0):
        m.box(0, 0.02, 0.0, width, depth - 0.04, 0.08, "black")
        m.box(0, 0, 0.08, width, depth, 0.78, "wood_mid", mats={"front": "veneer_mid"})
        for i, cx in enumerate((-0.32, 0.32)):
            m.box(cx, depth / 2 + 0.006, 0.11, 0.58, 0.014, 0.72, "wood_dark")
            parts.knob(m, cx + (0.22 if i == 0 else -0.22), depth / 2 + 0.018, 0.75, "chrome")
        parts.counter_top_with_basin(m, -width / 2 - 0.01, width / 2 + 0.01, -depth / 2, depth / 2 + 0.02, 0.86, 0.04,
                                     -0.08, 0.0, 0.72, 0.42, 0.16, "laminate", "metal", "steel_dark")
        m.box(-0.08, -0.06, 0.86, 0.02, 0.44, 0.02, "metal")
        m.tube((0.0, -0.22, 0.90), (0.0, -0.22, 1.10), 0.014, "chrome", seg=6)
        m.tube((0.0, -0.22, 1.10), (0.0, -0.06, 1.14), 0.012, "chrome", seg=5)
        parts.dirty_dishes(m, ctx.rng, -0.28, 0.0, 0.73, count=5, radius=0.11)
        m.box(0.55, 0.05, 0.90, 0.15, 0.25, 0.012, "steel_dark")
        for i in range(5):
            m.box(0.49 + i * 0.03, 0.05, 0.912, 0.008, 0.2, 0.09, "ceramic_cream")
    return place(ctx, m, room, "kitchen_counter", x, y, yaw, z, name="kitchen_counter", anchor=anchor)


def make_corner_counter(ctx, room, x0, y0, x1, y1, *, name="counter_corner"):
    """Balcão em L do canto nordeste: uma perna ao longo do norte (frente para sul) e outra ao longo do leste."""
    depth = 0.6
    yaw_north = math.pi
    north_len = x1 - x0
    nx, ny, _ = against_wall(room, "N", (x0 + x1) / 2, depth)
    m = MeshBuilder(name)
    with m.at(0, 0, 0):
        _cabinet_body(m, north_len, depth, doors=2)
    north = place(ctx, m, room, "counter", nx, ny, yaw_north, name=name + "_north")
    east_len = (y1 - y0) - depth
    ex, ey, yaw_east = against_wall(room, "E", y0 + east_len / 2, depth)
    east_mesh = MeshBuilder(name + "_east")
    _cabinet_body(east_mesh, east_len, depth, doors=2)
    east = place(ctx, east_mesh, room, "counter", ex, ey, yaw_east, name=name + "_east")
    return north, east


def make_fridge(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Geladeira com freezer em cima, ímãs de letra, desenhos da Emma e o calendário parado."""
    width, depth, height = 0.74, 0.70, 1.78
    cy = flush_center(room, x, y, yaw, depth)
    m = MeshBuilder("fridge")
    with m.at(0, cy, 0):
        m.soft_box(0, 0, 0.03, width, depth, height - 0.03, "appliance_panel", radius=0.04, edge=0.02)
        m.panel(0, depth / 2 + 0.003, 0.03 + (height - 0.03) / 2, width - 0.02, height - 0.06, "fridge_front", "front")
        m.box(0, 0, 0.0, width - 0.06, depth - 0.06, 0.04, "black")
        for z_handle, tall in ((height * 0.74, 0.30), (height * 0.5, 0.42)):
            m.box(width / 2 - 0.07, depth / 2 + 0.03, z_handle - tall / 2, 0.03, 0.03, tall, "chrome")
        m.box(0.0, depth / 2 + 0.008, 0.03 + 0.18, 0.16, 0.01, 0.05, "paper_white")
    return place(ctx, m, room, "fridge", x, y, yaw, z, name="fridge", anchor=anchor)


def make_mini_fridge(ctx, room, wall, along, *, width=0.62, depth=0.58):
    """Frigobar embutido no balcão da parede oeste."""
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("mini_fridge")
    m.box(0, 0, 0.0, width, depth, 0.86, "appliance_panel")
    m.box(0, depth / 2 + 0.006, 0.04, width - 0.04, 0.012, 0.78, "plastic_beige")
    m.box(width / 2 - 0.07, depth / 2 + 0.03, 0.42, 0.025, 0.03, 0.26, "chrome")
    m.box(0, 0.02, 0.86, width + 0.02, depth + 0.02, 0.04, "laminate")
    return place(ctx, m, room, "mini_fridge", x, y, yaw)


def make_stove(ctx, room, wall, along):
    """Fogão de quatro bocas com uma panela e a chaleira frias sobre as bocas."""
    width, depth, height = 0.76, 0.65, 0.90
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("stove")
    m.box(0, 0, 0.0, width, depth, height, "appliance_panel", mats={"front": "plastic_beige"})
    m.panel(0, depth / 2 + 0.002, 0.40, width - 0.1, 0.42, "black", "front")
    m.panel(0, depth / 2 + 0.004, 0.44, width - 0.24, 0.26, "glass_dark", "front")
    m.box(0, depth / 2 + 0.03, 0.66, width - 0.12, 0.024, 0.024, "chrome")
    m.box(0, -depth / 2 + 0.04, height, width, 0.08, 0.24, "plastic_beige")
    m.box(0, 0, height, width, depth, 0.02, "black")
    for i, (bx, by) in enumerate(((-0.19, -0.14), (0.19, -0.14), (-0.19, 0.14), (0.19, 0.14))):
        m.cylinder(bx, by, height + 0.02, 0.085, 0.012, "steel_dark", seg=8)
        m.cylinder(bx, by, height + 0.032, 0.055, 0.006, "black", seg=8)
        with m.at(-0.27 + i * 0.18, depth / 2 - 0.005, 0.78, rx=-90):
            m.cylinder(0, 0, 0, 0.022, 0.03, "black", seg=6)
    m.lathe([(0.11, 0), (0.12, 0.16), (0.12, 0.2)], -0.19, -0.14, height + 0.03, "steel_dark", seg=8, smooth=False)
    m.cylinder(-0.19, -0.14, height + 0.23, 0.12, 0.012, "steel_dark", seg=8)
    m.cylinder(0.19, 0.14, height + 0.03, 0.09, 0.14, "brass", seg=8, r_top=0.06)
    return place(ctx, m, room, "stove", x, y, yaw)


def make_wall_cabinets(ctx, room, wall, along, length, *, z0=1.5, height=0.7, depth=0.34, ajar=True):
    """Armários altos pendurados na parede, com uma porta entreaberta."""
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("wall_cabinets")
    m.box(0, 0, z0, length, depth, height, "wood_mid")
    doors = max(2, int(length / 0.5))
    door_w = length / doors
    for i in range(doors):
        cx = -length / 2 + door_w / 2 + i * door_w
        if ajar and i == 1:
            with m.at(cx - door_w / 2 + 0.01, depth / 2, z0 + 0.02, rz=-22):
                m.box(door_w / 2, 0.008, 0, door_w - 0.02, 0.016, height - 0.04, "wood_dark")
            m.box(cx, depth / 2 - 0.05, z0 + 0.02, door_w - 0.06, 0.02, height - 0.04, "black")
            plate_z = z0 + height / 2
            m.box(cx, depth / 2 - 0.12, plate_z, door_w - 0.1, 0.12, 0.012, "wood_dark")
            parts.plate(m, cx, depth / 2 - 0.12, plate_z + 0.012, 0.09, "ceramic_cream")
        else:
            m.box(cx, depth / 2 + 0.006, z0 + 0.02, door_w - 0.02, 0.016, height - 0.04, "wood_dark")
            parts.knob(m, cx + (door_w / 2 - 0.05 if i % 2 == 0 else -door_w / 2 + 0.05), depth / 2 + 0.02, z0 + 0.08, "chrome")
    return place(ctx, m, room, "wall_cabinets", x, y, yaw, mode="wall")


def make_microwave(ctx, room, x, y, z, yaw):
    m = MeshBuilder("microwave")
    m.soft_box(0, 0, 0, 0.46, 0.34, 0.27, "plastic_beige", radius=0.02, edge=0.012)
    m.panel(-0.06, 0.171, 0.135, 0.28, 0.20, "glass_dark", "front")
    m.box(0.17, 0.171, 0.06, 0.08, 0.006, 0.20, "plastic_gray")
    m.box(0.17, 0.176, 0.20, 0.06, 0.004, 0.03, "led_red")
    return place(ctx, m, room, "microwave", x, y, yaw, z, mode="decor")


def make_coffee_maker(ctx, room, x, y, z, yaw):
    """Cafeteira com a jarra ainda cheia de café frio de ontem."""
    m = MeshBuilder("coffee_maker")
    m.soft_box(0, -0.06, 0, 0.20, 0.20, 0.06, "plastic_gray", radius=0.02, edge=0.01)
    m.box(0, -0.13, 0.06, 0.18, 0.08, 0.28, "plastic_gray")
    m.box(0, -0.06, 0.32, 0.20, 0.20, 0.03, "plastic_gray")
    m.cylinder(0, 0.0, 0.06, 0.07, 0.14, "glass_clear", seg=8, r_top=0.08)
    m.cylinder(0, 0.0, 0.06, 0.065, 0.06, "water_dark", seg=8, r_top=0.075)
    return place(ctx, m, room, "coffee_maker", x, y, yaw, z, mode="decor")


def make_kitchen_table(ctx, room, x, y):
    """Mesinha do café da manhã, com duas tigelas de cereal secas, a caixa de cereal e o jornal de ontem."""
    m = MeshBuilder("kitchen_table")
    m.box(0, 0, 0.71, 0.80, 0.80, 0.04, "laminate")
    m.box(0, 0, 0.68, 0.74, 0.74, 0.03, "wood_mid")
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.tube((sx * 0.34, sy * 0.34, 0), (sx * 0.36, sy * 0.36, 0.69), 0.02, "chrome", seg=5)
    parts.plate(m, -0.20, 0.22, 0.75, 0.10, "ceramic_cream", food="food_dried")
    parts.plate(m, 0.16, -0.24, 0.75, 0.10, "ceramic_cream", food="food_dried")
    parts.mug(m, 0.24, 0.22, 0.75, 0.04, 0.09, "ceramic_cream")
    m.box(-0.20, -0.20, 0.75, 0.16, 0.06, 0.26, "toy_yellow")
    m.box(-0.20, -0.17, 0.90, 0.10, 0.02, 0.06, "toy_red")
    parts.paper_sheet(m, 0.02, 0.0, 0.751, 0.28, 0.20, "linen_dirty", 0.3)
    return place(ctx, m, room, "kitchen_table", x, y, 0.0, name="kitchen_table")
