"""Garagem: bancada, painel de ferramentas, prateleiras, freezer, bicicleta da Emma, cortador de grama."""
import math

from . import parts
from .kit import MeshBuilder
from .placement import against_wall, flush_center, floor_z, place

BENCH_TOP = 0.90
SHELF_TIERS = (0.30, 0.65, 1.00, 1.35, 1.70)
NOTE_TIER = 1.00                                   # o degrau de 1 m recebe o guia do reboque
NOTE_TIER_LIMIT = 0.55


def make_workbench(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Bancada de madeira grossa sob a janela leste, com morsa, ferramentas, latas e a prateleira de baixo cheia."""
    length, depth = 2.0, 0.65
    cy = flush_center(room, x, y, yaw, depth)
    m = MeshBuilder("workbench")
    with m.at(0, cy, 0):
        m.box(0, 0, BENCH_TOP - 0.07, length, depth, 0.07, "wood_mid")
        m.box(0, -depth / 2 + 0.03, BENCH_TOP, length, 0.03, 0.10, "wood_dark")
        parts.four_legs(m, -length / 2 + 0.04, -depth / 2 + 0.04, length / 2 - 0.04, depth / 2 - 0.04, BENCH_TOP - 0.07, 0.08,
                        "wood_dark")
        m.box(0, 0, 0.28, length - 0.16, depth - 0.1, 0.04, "wood_dark")
        m.box(-0.5, 0.0, 0.32, 0.5, 0.36, 0.28, "cardboard")
        m.cylinder(0.3, 0.0, 0.32, 0.1, 0.22, "toy_red", seg=8)
        m.cylinder(0.6, 0.05, 0.32, 0.08, 0.16, "steel_dark", seg=8)
        m.box(0.86, 0.1, BENCH_TOP, 0.18, 0.14, 0.16, "steel_dark")             # morsa
        m.box(0.86, 0.22, BENCH_TOP + 0.09, 0.14, 0.05, 0.05, "steel_dark")
        m.tube((0.86, 0.3, BENCH_TOP + 0.11), (0.86, 0.42, BENCH_TOP + 0.11), 0.01, "chrome", seg=5)
        m.bar((0.35, 0.12, BENCH_TOP), (0.55, 0.05, BENCH_TOP), 0.03, "steel_dark")   # martelo
        m.box(0.58, 0.04, BENCH_TOP, 0.05, 0.05, 0.05, "coat_dark")
        m.bar((0.2, 0.05, BENCH_TOP + 0.01), (0.34, 0.16, BENCH_TOP + 0.01), 0.016, "toy_yellow")
        m.cylinder(-0.35, -0.05, BENCH_TOP, 0.05, 0.12, "glass_clear", seg=8)
        m.cylinder(-0.35, -0.05, BENCH_TOP, 0.04, 0.05, "steel_dark", seg=8)
        m.soft_box(-0.85, 0.0, BENCH_TOP, 0.26, 0.15, 0.16, "plastic_gray", radius=0.02, edge=0.01)     # rádio
        m.box(-0.85, 0.076, BENCH_TOP + 0.08, 0.14, 0.004, 0.06, "black")
        parts.paper_sheet(m, 0.05, 0.16, BENCH_TOP, 0.30, 0.10, "coat_dark", 0.4, 0.02)                 # pano de graxa
    return place(ctx, m, room, "workbench", x, y, yaw, z, name="workbench", anchor=anchor, collision_top=BENCH_TOP)


def make_tool_panel(ctx, room, wall, along, z_center, *, width=1.7, height=0.9):
    """Painel perfurado com as silhuetas das ferramentas; uma ferramenta falta, deixando só o contorno."""
    x, y, yaw = against_wall(room, wall, along, 0.0)
    m = MeshBuilder("tool_panel")
    m.box(0, 0.012, -height / 2, width, 0.024, height, "wood_mid")
    for i in range(6):
        tx = -width / 2 + 0.2 + i * (width - 0.4) / 5
        if i == 3:
            m.box(tx, 0.026, -0.62, 0.05, 0.004, 0.32, "black")               # contorno de uma ferramenta que sumiu
            continue
        m.bar((tx, 0.05, -0.2), (tx, 0.05, -0.6 - 0.05 * (i % 3)), 0.03, "steel_dark")
        m.box(tx, 0.05, -0.16, 0.06, 0.04, 0.08, "toy_red" if i % 2 else "toy_yellow")
    m.tube((-width / 2 + 0.15, 0.06, -0.72), (width / 2 - 0.2, 0.06, -0.78), 0.012, "coat_dark", seg=4)
    return place(ctx, m, room, "tool_panel", x, y, yaw, floor_z(room) + z_center + height / 2, mode="wall")


def _stock_shelf(m, rng, tier, first, limit, depth):
    """Enche uma prateleira de `first` a `limit` (coordenadas locais) com caixas, latas e potes, sem passar do fim."""
    cursor = first
    while cursor < limit - 0.12:
        span = min(rng.uniform(0.18, 0.4), limit - cursor)
        kind = rng.random()
        if kind < 0.4:
            m.box(cursor + span / 2, 0.0, tier + 0.005, span, depth - 0.08, rng.uniform(0.16, 0.28), "cardboard",
                  mats={"front": "cardboard_toys" if rng.random() < 0.3 else "cardboard"}, uv=1.6)
        elif kind < 0.75:
            for k in range(max(1, int((span - 0.06) / 0.13))):
                m.cylinder(cursor + 0.07 + k * 0.13, 0.0, tier + 0.005, 0.06, rng.uniform(0.14, 0.2), "can_labels", seg=8)
        else:
            m.cylinder(cursor + span / 2, 0.0, tier + 0.005, 0.07, 0.2, "glass_clear", seg=8)
        cursor += span + rng.uniform(0.02, 0.08)


def make_garage_shelves(ctx, room, wall, along, *, width=2.5, depth=0.4, height=1.85):
    """Estante de aço com caixas, latas de tinta e potes; o degrau de 1 m fica livre para o guia do reboque."""
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("garage_shelves")
    for sx in (-width / 2 + 0.03, width / 2 - 0.03, 0.0):
        for sy in (-depth / 2 + 0.02, depth / 2 - 0.02):
            m.box(sx, sy, 0, 0.04, 0.04, height, "steel_dark")
    for tier in SHELF_TIERS:
        m.box(0, 0, tier - 0.02, width, depth, 0.025, "wood_mid")
    for tier in SHELF_TIERS:
        # a estante gira 180 graus: o trecho onde o guia repousa (x ~ 15.2) fica no lado +X local
        limit = NOTE_TIER_LIMIT if tier == NOTE_TIER else width / 2 - 0.08
        _stock_shelf(m, ctx.rng, tier, -width / 2 + 0.1, limit, depth)
    # proxy só no fundo da estante: o jogador para na beira dela e o guia do reboque fica fora do volume
    back_only = [(-width / 2, -depth / 2, 0.0, width / 2, -depth / 2 + 0.12, height)]
    return place(ctx, m, room, "garage_shelves", x, y, yaw, collision=back_only)


def make_chest_freezer(ctx, room, wall, along):
    """Freezer horizontal velho, amarelado, com a tampa cheia de riscos e um cadeado."""
    width, depth, height = 1.1, 0.7, 0.9
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("chest_freezer")
    m.soft_box(0, 0, 0.06, width, depth, height - 0.1, "appliance_panel", radius=0.03, edge=0.02)
    m.box(0, 0.016, height - 0.06, width + 0.03, depth + 0.03, 0.06, "plastic_beige")
    m.box(0, depth / 2 + 0.02, height - 0.05, 0.3, 0.03, 0.03, "chrome")
    m.box(0, depth / 2 + 0.005, height - 0.16, 0.05, 0.02, 0.06, "steel_dark")
    for fx in (-0.45, 0.45):
        m.box(fx, 0, 0, 0.08, depth - 0.1, 0.06, "black")
    return place(ctx, m, room, "chest_freezer", x, y, yaw)


def make_water_heater(ctx, room, x, y):
    m = MeshBuilder("water_heater")
    m.cylinder(0, 0, 0.0, 0.27, 1.45, "plastic_beige", seg=10, caps=(True, True))
    m.cylinder(0, 0, 1.45, 0.27, 0.05, "plastic_beige", seg=10, r_top=0.2)
    for sx in (-0.08, 0.08):
        m.tube((sx, 0, 1.5), (sx, 0, 1.85), 0.022, "brass", seg=6)
    m.box(0.0, -0.28, 0.35, 0.16, 0.02, 0.22, "black")
    m.box(0.0, -0.291, 0.4, 0.10, 0.004, 0.06, "paper_white")
    return place(ctx, m, room, "water_heater", x, y, 0.0)


def make_lawn_mower(ctx, room, x, y, yaw):
    """Cortador de grama a gasolina, de lado, com o cabo dobrado."""
    m = MeshBuilder("lawn_mower")
    m.soft_box(0, 0, 0.12, 0.5, 0.6, 0.16, "toy_red", radius=0.06, edge=0.03)
    m.cylinder(0.0, -0.05, 0.28, 0.1, 0.09, "steel_dark", seg=8)
    m.box(0, 0.14, 0.14, 0.5, 0.06, 0.06, "black")
    for sx in (-0.27, 0.27):
        for sy, radius in ((0.22, 0.07), (-0.22, 0.10)):
            with m.at(sx, sy, radius, ry=90):
                m.cylinder(0, 0, -0.025, radius, 0.05, "tire_rubber", seg=8)
    for sx in (-0.2, 0.2):
        m.bar((sx, -0.28, 0.24), (sx * 0.9, -0.55, 0.95), 0.025, "steel_dark")
    m.bar((-0.18, -0.55, 0.95), (0.18, -0.55, 0.95), 0.03, "black")
    m.cylinder(0.14, 0.2, 0.28, 0.035, 0.05, "toy_yellow", seg=6)
    return place(ctx, m, room, "lawn_mower", x, y, yaw)


def make_kids_bicycle(ctx, room, x, y, yaw):
    """Bicicleta rosa da Emma com rodinhas de apoio, cestinha e fitas no guidão, encostada na parede."""
    m = MeshBuilder("kids_bicycle")
    wheel_r, wheelbase = 0.20, 0.72
    for wy in (-wheelbase / 2, wheelbase / 2):
        m.torus(0, wy, wheel_r, wheel_r, 0.018, "tire_rubber", seg=12, seg_minor=4, ry=90)
        for spoke in range(4):
            angle = spoke * math.pi / 4
            m.bar((0, wy - wheel_r * 0.95 * math.sin(angle), wheel_r - wheel_r * 0.95 * math.cos(angle)),
                  (0, wy + wheel_r * 0.95 * math.sin(angle), wheel_r + wheel_r * 0.95 * math.cos(angle)), 0.006, "chrome")
    rear_hub, front_hub = (0, -wheelbase / 2, wheel_r), (0, wheelbase / 2, wheel_r)
    seat_post, head = (0, -0.16, 0.55), (0, 0.26, 0.60)
    for a, b in ((rear_hub, (0, -0.02, 0.30)), ((0, -0.02, 0.30), front_hub), (seat_post, (0, -0.02, 0.30)),
                 (seat_post, head), ((0, -0.02, 0.30), head), (head, front_hub), (rear_hub, seat_post)):
        m.tube(a, b, 0.014, "painted_pink", seg=5)
    m.box(0, -0.2, 0.55, 0.11, 0.2, 0.04, "coat_dark")
    m.tube((-0.15, 0.24, 0.70), (0.15, 0.24, 0.70), 0.011, "chrome", seg=5)
    m.tube(head, (0, 0.24, 0.70), 0.012, "chrome", seg=5)
    for side in (-1, 1):
        m.bar((side * 0.15, 0.24, 0.70), (side * 0.16, 0.24, 0.52), 0.006, "fabric_red")
        m.tube((side * 0.03, -wheelbase / 2, wheel_r), (side * 0.13, -wheelbase / 2, 0.08), 0.008, "steel_dark", seg=4)
        m.cylinder(side * 0.13, -wheelbase / 2, 0.0, 0.055, 0.03, "tire_rubber", seg=6)
    m.box(0, 0.30, 0.62, 0.20, 0.13, 0.11, "linen_sheet")
    return place(ctx, m, room, "kids_bicycle", x, y, yaw)
