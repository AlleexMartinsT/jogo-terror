"""Sala de jantar: mesa posta para três (a terceira sem prato), aparador com cristaleira e o prato quebrado no chão.

A mesa mede 1,80 x 0,95 m com tampo a 0,76 m. A toalha cobre só o lado oeste (onde Daniel e Laura se
sentariam) e foi simulada com `craft.drape`; o lado da Emma ficou na madeira nua.
"""
import math

from .. import craft
from . import cloth_sala as cloth
from . import furniture_forms as forms
from . import materials, parts
from . import small_things as things
from .composite import Composite
from .kit import MeshBuilder
from .placement import against_wall, place

materials.SPECS.update({
    "dried_flower_a": materials.Spec(color=(0.30, 0.23, 0.15), roughness=0.95),
    "dried_flower_b": materials.Spec(color=(0.36, 0.26, 0.26), roughness=0.95),
    "dried_leaf": materials.Spec(color=(0.17, 0.14, 0.08), roughness=0.95),
    "wine_glass_bottle": materials.Spec(color=(0.02, 0.07, 0.03), roughness=0.08),
    "toy_cup_yellow": materials.Spec(color=(0.62, 0.52, 0.10), roughness=0.4),
})

TABLE_WIDTH, TABLE_DEPTH, TABLE_TOP = 1.8, 0.95, 0.76
CLOTH_EDGE_X = 0.30                       # a toalha vai da ponta oeste (x = -0,9) até aqui


def _table_frame(wood, round_part):
    """Tampo moldurado, avental, quatro pernas torneadas em balaústre e os blocos de encontro."""
    forms.slab(round_part, 0, 0, TABLE_TOP - 0.04, TABLE_WIDTH, TABLE_DEPTH, forms.OGEE_EDGE, "walnut", radius=0.07)
    apron_z = TABLE_TOP - 0.04 - 0.105
    wood.box(0, TABLE_DEPTH / 2 - 0.085, apron_z, TABLE_WIDTH - 0.24, 0.028, 0.105, "walnut")
    wood.box(0, -TABLE_DEPTH / 2 + 0.085, apron_z, TABLE_WIDTH - 0.24, 0.028, 0.105, "walnut")
    for side in (-1, 1):
        wood.box(side * (TABLE_WIDTH / 2 - 0.085), 0, apron_z, 0.028, TABLE_DEPTH - 0.24, 0.105, "walnut_v")
        for sy in (-1, 1):
            leg_x, leg_y = side * (TABLE_WIDTH / 2 - 0.095), sy * (TABLE_DEPTH / 2 - 0.095)
            forms.turned_leg(round_part, leg_x, leg_y, 0.0, TABLE_TOP - 0.04, 0.052, "walnut_v", "baluster", sides=16)
            wood.box(leg_x, leg_y, apron_z - 0.01, 0.075, 0.075, 0.125, "walnut_v")
        wood.box(side * (TABLE_WIDTH / 2 - 0.15), 0, apron_z - 0.12, 0.012, TABLE_DEPTH - 0.4, 0.012, "walnut_v")


def _table_colliders():
    colliders = cloth.collider_builder("table_colliders")
    colliders.box(0, 0, TABLE_TOP - 0.04, TABLE_WIDTH, TABLE_DEPTH, 0.04, "walnut")
    colliders.box(0, 0, TABLE_TOP - 0.145, TABLE_WIDTH - 0.17, TABLE_DEPTH - 0.17, 0.105, "walnut")
    colliders.box(0, 0, -0.02, 6, 6, 0.02, "walnut")
    return colliders


def _tablecloth(asm):
    """Toalha de linho jogada de ponta a meio da mesa, caindo dos dois lados e caída para fora na ponta oeste."""
    on_top = (-TABLE_WIDTH / 2 + 0.02, -TABLE_DEPTH / 2 + 0.02, CLOTH_EDGE_X + 0.1, TABLE_DEPTH / 2 - 0.02)
    mesh = cloth.drape_over(_table_colliders(), width=1.45, depth=1.3, center=(-0.52, 0.0, TABLE_TOP + 0.008), yaw=0.0,
                            material="tablecloth", cell=0.045, frames=60, mass=0.3, stiffness=15.0, bending=1.5,
                            thickness=0.004, pin_rect=on_top)
    asm.add_mesh(mesh)


def _dried_flowers(m, cx, cy, z0, rng):
    """Vaso de porcelana com flores secas caídas: hastes escuras e cabeças de hortênsia desbotadas."""
    m.lathe([(0.035, 0.0), (0.06, 0.04), (0.075, 0.10), (0.06, 0.17), (0.035, 0.21), (0.045, 0.235), (0.04, 0.24),
             (0.03, 0.235), (0.0, 0.10)], cx, cy, z0, "porcelain_old", seg=forms.seg(18), smooth=True)
    for index in range(11):
        angle = rng.uniform(0, 2 * math.pi)
        lean = rng.uniform(0.04, 0.17)
        length = rng.uniform(0.25, 0.42)
        mid = (cx + lean * 0.4 * math.cos(angle), cy + lean * 0.4 * math.sin(angle), z0 + 0.24 + length * 0.55)
        tip = (cx + lean * math.cos(angle) * 1.4, cy + lean * math.sin(angle) * 1.4, z0 + 0.24 + length - 0.1 * (index % 3))
        start = (cx, cy, z0 + 0.22)
        m.tube(start, mid, 0.0028, "dried_leaf", seg=5)
        m.tube(mid, tip, 0.0025, "dried_leaf", seg=5)
        for blob in range(5):
            m.sphere(tip[0] + rng.uniform(-0.016, 0.016), tip[1] + rng.uniform(-0.016, 0.016), tip[2] + rng.uniform(-0.01, 0.014),
                     rng.uniform(0.011, 0.016), "dried_flower_a" if (index + blob) % 3 else "dried_flower_b", seg=7, rings=4)
        m.box(tip[0] + 0.02, tip[1], tip[2] - 0.05, 0.03, 0.012, 0.045, "dried_leaf")


def _wine_bottle(m, cx, cy, z0, yaw):
    with m.at(cx, cy, z0, rz=yaw):
        parts.bottle(m, 0, 0, 0, 0.038, 0.30, "wine_glass_bottle", cap_mat="gilt")
        m.cylinder(0, 0, 0.0035, 0.0345, 0.095, "wine_dark", seg=forms.seg(16))


def _child_cup(m, cx, cy, z0, yaw):
    """Copo de plástico amarelo da Emma, com canudo dobrado."""
    with m.at(cx, cy, z0, rz=yaw):
        m.lathe([(0.0, 0.0), (0.028, 0.0), (0.036, 0.095), (0.034, 0.10), (0.0, 0.098)], 0, 0, 0, "toy_cup_yellow",
                seg=forms.seg(16), smooth=True)
        m.tube((0.008, 0, 0.02), (0.012, 0, 0.14), 0.0035, "toy_red", seg=6)
        m.tube((0.012, 0, 0.14), (0.03, 0, 0.15), 0.0035, "toy_red", seg=6)


def _napkin(asm, setting_x, setting_y, setting_yaw_deg, surface_z, scale=1.0):
    """Guardanapo de linho caído à esquerda do prato: um pano pequeno simulado sobre o tampo (ou a toalha)."""
    yaw = math.radians(setting_yaw_deg)
    lx, ly = -0.215 * scale, 0.10
    x = setting_x + lx * math.cos(yaw) - ly * math.sin(yaw)
    y = setting_y + lx * math.sin(yaw) + ly * math.cos(yaw)
    support = cloth.collider_builder("napkin_support")
    support.box(x, y, surface_z - 0.03, 0.4, 0.4, 0.03, "walnut")
    mesh = cloth.drape_over(support, width=0.19, depth=0.13, center=(x, y, surface_z + 0.05), yaw=yaw + 0.25,
                            material="tablecloth", cell=0.02, frames=40, mass=0.2, stiffness=10.0, bending=2.0,
                            thickness=0.003)
    asm.add_mesh(mesh)


def _surface_height(x):
    """Altura em que um objeto repousa em x (local da mesa): sobre a toalha ou sobre o tampo."""
    return TABLE_TOP + (0.012 if x < CLOTH_EDGE_X else 0.0)


def _table_things(asm, rng):
    """Os três lugares e o centro da mesa."""
    small = asm.small
    dan = (-0.67, 0.0)
    laura = (-0.50, 0.27)
    emma = (0.53, 0.27)
    things.place_setting(small, dan[0], dan[1], _surface_height(dan[0]), -90, rng, food="food_old")
    things.place_setting(small, laura[0], laura[1], _surface_height(laura[0]), 180, rng, food="food_old")
    things.place_setting(small, emma[0], emma[1], _surface_height(emma[0]), 180, rng, plate=False, child=True)
    _napkin(asm, dan[0], dan[1], -90, _surface_height(dan[0]))
    _napkin(asm, laura[0], laura[1], 180, _surface_height(laura[0]))
    _napkin(asm, emma[0], emma[1], 180, _surface_height(emma[0]), 0.8)
    _child_cup(small, emma[0] + 0.1, emma[1] + 0.2, TABLE_TOP, 20)
    parts.candle(small, -0.24, 0.0, _surface_height(-0.24), 0.24)
    parts.candle(small, 0.30, 0.0, _surface_height(0.30), 0.24)
    _dried_flowers(small, 0.03, 0.01, _surface_height(0.03), rng)
    _wine_bottle(small, 0.56, -0.20, TABLE_TOP, 30)
    things.tumbler(small, 0.66, -0.12, TABLE_TOP, fill=0.0, radius=0.032, height=0.1)
    small.cylinder(-0.09, -0.24, _surface_height(-0.09), 0.014, 0.05, "porcelain_old", seg=forms.seg(10), smooth=True)
    small.cylinder(-0.03, -0.24, _surface_height(-0.03), 0.014, 0.05, "porcelain_old", seg=forms.seg(10), smooth=True)


def make_dining_table(ctx, room, x, y, yaw=0.0):
    """Mesa de nogueira posta para três: dois pratos de comida velha, o lugar da Emma sem prato, velas apagadas."""
    asm = Composite("dining_table", wood=forms.WOOD, round=forms.SMOOTH, small=forms.SMOOTH)
    _table_frame(asm.wood, asm.round)
    _tablecloth(asm)
    _table_things(asm, ctx.rng)
    return place(ctx, asm, room, "dining_table", x, y, yaw, name="dining_table")


# ---------------------------------------------------------------------------
# Aparador com cristaleira
# ---------------------------------------------------------------------------
def _sideboard_base(wood, round_part, trim, width, depth, height):
    """Base de 0,85 m: duas portas almofadadas, três gavetas no meio, tampo moldurado e pés torneados."""
    wood.box(0, 0.0, 0.10, width - 0.04, depth - 0.04, height - 0.14, "walnut_v")
    forms.slab(round_part, 0, 0.015, height - 0.04, width + 0.04, depth + 0.03, forms.OGEE_EDGE, "walnut", radius=0.03)
    forms.slab(round_part, 0, 0, 0.06, width, depth - 0.01, [(0, 0.015), (0.015, 0.0), (0.04, 0.0)], "walnut", radius=0.01)
    for sx in (-1, 1):
        for sy in (-1, 1):
            forms.turned_leg(round_part, sx * (width / 2 - 0.06), sy * (depth / 2 - 0.06), 0.0, 0.08, 0.028, "walnut_v", "bun")
    front = depth / 2 - 0.02
    door_w = width * 0.33
    for side in (-1, 1):
        cx = side * (width / 2 - door_w / 2 - 0.02)
        wood.box(cx, front + 0.008, 0.115, door_w, 0.02, height - 0.205, "walnut")
        with wood.at(cx, front + 0.0185, 0.115 + (height - 0.205) / 2, rx=-90):
            wood.frustum(0, 0, 0, door_w - 0.1, height - 0.31, door_w - 0.12, height - 0.33, 0.007, "walnut_v")
        forms.round_knob(trim, cx - side * (door_w / 2 - 0.05), front + 0.0275, 0.5, 0.014, "brass_aged")
    for row in range(3):
        z = 0.115 + row * (height - 0.205) / 3
        h = (height - 0.205) / 3 - 0.008
        wood.box(0, front + 0.008, z, width - 2 * door_w - 0.09, 0.02, h, "walnut")
        forms.bail_pull(trim, 0, front + 0.0195, z + h / 2 + 0.004, 0.06, "brass_aged")
        forms.escutcheon(trim, 0.0, front + 0.0185, z + h - 0.02, "brass_aged")


def _hutch(wood, round_part, trim, glass, china, x_center, width, depth, base_height):
    """Cristaleira de 0,95 m sobre a base: laterais, prateleiras de vidro, porta envidraçada e louça exposta."""
    z0, z1 = base_height, base_height + 0.95
    hx = width / 2
    for side in (-1, 1):
        wood.box(x_center + side * (hx - 0.01), 0.0, z0, 0.02, depth, z1 - z0, "walnut_v")
    wood.box(x_center, -depth / 2 + 0.01, z0, width, 0.015, z1 - z0, "case_inside")
    wood.box(x_center, 0.0, z1 - 0.02, width, depth, 0.02, "walnut")
    forms.slab(round_part, x_center, 0.0, z1 - 0.005, width, depth - 0.02, forms.CORNICE, "walnut", radius=0.008)
    for level in (0.32, 0.64):
        glass.box(x_center, -0.01, z0 + level, width - 0.04, depth - 0.05, 0.008, "glass_clear")
    front = depth / 2 - 0.01
    wood.box(x_center, front, z0, width, 0.02, 0.05, "walnut")
    for side in (-1, 1):
        wood.box(x_center + side * (hx - 0.035), front, z0 + 0.05, 0.05, 0.02, z1 - z0 - 0.07, "walnut_v")
    wood.box(x_center, front, z1 - 0.07, width - 0.05, 0.02, 0.05, "walnut")
    glass.panel(x_center, front - 0.002, (z0 + z1) / 2 - 0.01, width - 0.1, z1 - z0 - 0.12, "glass_clear", "front")
    forms.round_knob(trim, x_center + hx - 0.06, front + 0.01, z0 + 0.5, 0.012, "brass_aged")
    for index, level in enumerate((0.0, 0.32, 0.64)):
        shelf_z = z0 + level + (0.008 if level else 0.0)
        for plate_x in (-0.17, 0.0, 0.17):
            with china.at(x_center + plate_x, -0.07, shelf_z + 0.004, rx=-78):
                china.lathe([(0.0, 0.0), (0.075, 0.0), (0.082, 0.01), (0.085, 0.012), (0.0, 0.004)], 0, 0, 0, "porcelain_old",
                            seg=forms.seg(18), smooth=True)
        for cup_x in (-0.2, -0.1):
            parts.mug(china, x_center + cup_x, 0.04, shelf_z, 0.028, 0.06, "porcelain_old", handle_dir=1)
        china.cylinder(x_center + 0.16, 0.05, shelf_z, 0.03, 0.12, "cut_crystal", seg=forms.seg(14), r_top=0.036, smooth=True)
        china.cylinder(x_center + 0.24, 0.05, shelf_z, 0.026, 0.1, "cut_crystal", seg=forms.seg(14), r_top=0.032, smooth=True)


def make_sideboard(ctx, room, wall, along):
    """Aparador de 1,4 m com cristaleira na metade de trás e o tampo livre na outra (onde um retrato caiu)."""
    width, depth, height = 1.4, 0.45, 0.85
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Composite("sideboard", wood=forms.WOOD, round=forms.SMOOTH, trim=forms.SMOOTH, glass=craft.RAW, china=forms.SMOOTH)
    _sideboard_base(asm.wood, asm.round, asm.trim, width, depth, height)
    _hutch(asm.wood, asm.round, asm.trim, asm.glass, asm.china, 0.33, 0.7, 0.30, height)
    parts.candle(asm.china, -0.55, 0.0, height, 0.24)
    asm.china.lathe([(0.0, 0.0), (0.09, 0.0), (0.14, 0.05), (0.15, 0.065), (0.12, 0.06), (0.0, 0.035)], -0.22, 0.02, height,
                    "porcelain_old", seg=forms.seg(20), smooth=True)
    return place(ctx, asm, room, "sideboard", x, y, yaw)


# ---------------------------------------------------------------------------
# Prato quebrado
# ---------------------------------------------------------------------------
def make_broken_plate(ctx, room, x, y, yaw=0.0):
    """Prato da Emma quebrado no chão: cacos de porcelana em leque a partir do ponto de impacto, um resto de comida e o garfo."""
    rng = ctx.rng
    m = MeshBuilder("broken_plate")
    m.finish = forms.SMOOTH
    pieces = 7
    for index in range(pieces):
        a0 = 2 * math.pi * index / pieces + rng.uniform(-0.12, 0.12)
        a1 = 2 * math.pi * (index + 1) / pieces + rng.uniform(-0.12, 0.12)
        r_in, r_out = rng.uniform(0.0, 0.03), rng.uniform(0.10, 0.125)
        outline = [(r_in * math.cos(a0), r_in * math.sin(a0)), (r_out * math.cos(a0), r_out * math.sin(a0)),
                   (r_out * 1.02 * math.cos((a0 + a1) / 2), r_out * 1.02 * math.sin((a0 + a1) / 2)),
                   (r_out * math.cos(a1), r_out * math.sin(a1)), (r_in * math.cos(a1), r_in * math.sin(a1))]
        push = rng.uniform(0.02, 0.10)
        mid = (a0 + a1) / 2
        with m.at(push * math.cos(mid), push * math.sin(mid), 0.0018, rz=rng.uniform(-14, 14),
                  rx=rng.uniform(-6, 6), ry=rng.uniform(-6, 6)):
            m.extrude(outline, "xy", 0.0, 0.0032, "porcelain_old")
    m.cylinder(0.03, -0.05, 0.0, 0.055, 0.004, "food_old", seg=forms.seg(10))
    things.fork(m, 0.1, 0.08, 0.0, 70, 0.8)
    return place(ctx, m, room, "broken_plate", x, y, yaw, mode="flat")
