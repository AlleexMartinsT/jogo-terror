"""Banheiro: banheira de louça com água parada, vaso, pia com cuba, armário de remédios, cortina de box, toalhas.

Louça em casca (anéis ligados por `loft`: parede de fora, borda, parede de dentro), cromados em tubos e torneados.
A pia mantém o tampo a 0,90 m e uma faixa livre à esquerda, onde repousa a pilha (Item_BATTERY_2).
"""
import math

from .. import craft
from . import cloth_quartos as fabric
from . import plush_quartos as plush
from . import small_quartos as small
from . import woodwork_quartos as joinery
from .assembly_quartos import CLOTH, METAL, PAINTED, WOOD, Assembly, segments
from .decor_quartos import wall_spot
from .kit import MeshBuilder
from .placement import against_wall, flush_center, floor_z, place
from .shapes_quartos import WeldedBuilder, annulus, ellipse_outline, oval_ring, rect_ring

PORCELAIN = "up_porcelain"
CERAMIC_FINISH = craft.Finish(bevel=0.004, bevel_segments=2, bevel_angle=34.0, smooth_angle=62.0)
PAINT_WHITE, PAINT_WHITE_V = joinery.wood_pair("up_paint_white")


# ---------------------------------------------------------------------------
# Banheira
# ---------------------------------------------------------------------------
TUB_LENGTH, TUB_WIDTH, TUB_CORNER = 1.70, 0.75, 0.20
# (recuo em relação ao contorno externo, altura): base, pé, parede, borda arredondada, parede de dentro, fundo
TUB_SECTIONS = ((0.06, 0.07), (0.0, 0.14), (0.0, 0.42), (0.012, 0.552), (0.024, 0.575), (0.050, 0.578), (0.064, 0.553),
                (0.078, 0.45), (0.104, 0.30), (0.150, 0.19), (0.172, 0.150))
WATER_LEVEL = 0.40


def _tub_rings():
    return [rect_ring(TUB_LENGTH, TUB_WIDTH, TUB_CORNER, z, inset=inset) for inset, z in TUB_SECTIONS]


def _tub_fixtures(m, assembly):
    """Registros de cruzeta, bica curva, chuveiro com haste na parede do fundo e pés de bola."""
    back = -TUB_WIDTH / 2
    x = -0.55
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.sphere(sx * (TUB_LENGTH / 2 - 0.2), sy * (TUB_WIDTH / 2 - 0.12), 0.034, 0.034, "chrome", seg=10, rings=6)
    for handle_x in (x - 0.17, x + 0.17):
        with m.at(handle_x, back, 0.74, rx=-90):
            m.cylinder(0, 0, 0, 0.034, 0.008, "chrome", seg=segments(16))
            m.lathe([(0.011, 0.0), (0.011, 0.026), (0.016, 0.03), (0.016, 0.036), (0.0, 0.038)], 0, 0, 0.008, "chrome", seg=segments(12))
            m.box(0, 0, 0.040, 0.05, 0.012, 0.012, "chrome")
            m.box(0, 0, 0.040, 0.012, 0.05, 0.012, "chrome")
            m.sphere(0, 0, 0.040, 0.011, "chrome", seg=8, rings=5)
    with m.at(x, back, 0.76, rx=-90):
        m.cylinder(0, 0, 0, 0.036, 0.008, "chrome", seg=segments(16))
    spout = craft.tube_along([(x, back + 0.01, 0.76), (x, back + 0.10, 0.775), (x, back + 0.19, 0.755), (x, back + 0.205, 0.715)],
                             0.0135, 10, 8, name="tub_spout")
    assembly.add_mesh(spout, "chrome")
    riser = craft.tube_along([(x, back + 0.012, 0.80), (x, back + 0.012, 1.55), (x, back + 0.012, 1.88), (x, back + 0.07, 1.93),
                              (x, back + 0.20, 1.91)], 0.010, 8, 6, name="shower_riser")
    assembly.add_mesh(riser, "chrome")
    with m.at(x, back + 0.20, 1.91, rx=-40):
        m.cylinder(0, 0, 0.0, 0.016, 0.018, "chrome", seg=segments(12), r_top=0.06)
        m.cylinder(0, 0, 0.018, 0.06, 0.006, "up_plastic_gray", seg=segments(16))
    with m.at(0.5, 0, WATER_LEVEL - 0.25):
        m.cylinder(0.0, 0, 0.0, 0.032, 0.006, "chrome", seg=segments(14))


def _tub_water(m):
    inset = 0.083
    ring = rect_ring(TUB_LENGTH, TUB_WIDTH, TUB_CORNER, WATER_LEVEL, inset=inset)
    m.poly(ring, "up_water", uv=[(px * 0.5, py * 0.5) for px, py, _ in ring])


def _rubber_duck(m, cx, cy, z, yaw):
    """Patinho de borracha boiando: corpo, cabeça, bico laranja e dois olhos."""
    with m.at(cx, cy, z, rz=yaw):
        plush.ellipsoid(m, 0, 0, 0.012, 0.034, 0.046, 0.026, "rubber_duck", seg=12, rings=7)
        plush.ellipsoid(m, 0, -0.04, 0.026, 0.020, 0.018, 0.020, "rubber_duck", seg=10, rings=6, turn=(-20, 0, 0))
        plush.ellipsoid(m, 0, 0.035, 0.040, 0.020, 0.024, 0.024, "rubber_duck", seg=12, rings=7)
        plush.ellipsoid(m, 0, 0.060, 0.036, 0.013, 0.020, 0.005, "up_paint_red", seg=8, rings=5)
        for side in (-1, 1):
            plush.ellipsoid(m, side * 0.012, 0.050, 0.050, 0.004, 0.004, 0.004, "up_rubber", seg=6, rings=4)


def make_bathtub(ctx, room, wall, along):
    """Banheira de louça com a borda arredondada, cheia de água escura e parada, o patinho da Emma boiando."""
    x, y, yaw = against_wall(room, wall, along, TUB_WIDTH)
    tub = Assembly("bathtub")
    shell = tub.part(CERAMIC_FINISH)
    shell.loft(_tub_rings(), PORCELAIN, True, True, True)
    fittings = tub.part(METAL)
    _tub_fixtures(fittings, tub)
    water = tub.part(None)
    _tub_water(water)
    _rubber_duck(water, 0.22, 0.06, WATER_LEVEL, 0.5)
    return place(ctx, tub, room, "bathtub", x, y, yaw)


# ---------------------------------------------------------------------------
# Vaso sanitário
# ---------------------------------------------------------------------------
# (meia-largura, meia-profundidade à frente, atrás, centro y, altura): bacia por fora, borda, bacia por dentro
BOWL_SECTIONS = ((0.11, 0.14, 0.10, -0.06, 0.05), (0.14, 0.20, 0.12, -0.04, 0.16), (0.175, 0.26, 0.14, -0.02, 0.28),
                 (0.188, 0.295, 0.15, 0.0, 0.38), (0.195, 0.31, 0.155, 0.0, 0.405), (0.186, 0.298, 0.147, 0.0, 0.414),
                 (0.150, 0.262, 0.118, 0.0, 0.410), (0.128, 0.222, 0.092, 0.0, 0.300), (0.085, 0.150, 0.062, 0.0, 0.205),
                 (0.052, 0.095, 0.040, 0.0, 0.165))


def _bowl_rings():
    return [oval_ring(a, b, z, cy=cy, back_half_y=bb, points=28) for a, b, bb, cy, z in BOWL_SECTIONS]


def make_toilet(ctx, room, wall, along):
    """Vaso de louça de forma orgânica (casca por anéis), caixa acoplada, assento e tampa erguida contra a caixa."""
    depth = 0.68
    x, y, yaw = against_wall(room, wall, along, depth)
    unit = Assembly("toilet")
    bowl = unit.part(CERAMIC_FINISH)
    bowl.loft(_bowl_rings(), PORCELAIN, True, True, True)
    bowl.lathe([(0.10, 0.0), (0.125, 0.01), (0.115, 0.08), (0.10, 0.17)], 0, -0.05, 0.0, PORCELAIN, seg=segments(20), smooth=True)
    bowl.soft_box(0, -depth / 2 + 0.09, 0.30, 0.40, 0.17, 0.48, PORCELAIN, radius=0.04, edge=0.02)
    bowl.soft_box(0, -depth / 2 + 0.095, 0.78, 0.43, 0.20, 0.03, PORCELAIN, radius=0.04, edge=0.012)
    water = unit.part(None)
    ring = oval_ring(0.080, 0.145, 0.215, cy=0.0, back_half_y=0.058, points=28)
    water.poly(ring, "up_water", uv=[(px * 3, py * 3) for px, py, _ in ring])
    seat = unit.part(craft.Finish(bevel=0.004, bevel_segments=2, smooth_angle=60.0, bevel_angle=45.0), builder_class=WeldedBuilder)
    outer = [(px, py) for px, py, _ in oval_ring(0.188, 0.302, 0.0, back_half_y=0.150, points=28)]
    inner = [(px, py) for px, py, _ in oval_ring(0.134, 0.242, 0.0, back_half_y=0.098, points=28)]
    annulus(seat, outer, inner, "up_plastic_white", thickness=0.02, z_top=0.436)
    with seat.at(0, -0.145, 0.446, rx=92):
        lid = [(px, py + 0.150) for px, py, _ in oval_ring(0.188, 0.302, 0.0, back_half_y=0.150, points=28)]
        seat.extrude([(px, py) for px, py in lid], "xy", 0.0, 0.018, "up_plastic_white")
    metal = unit.part(METAL)
    for side in (-1, 1):
        metal.cylinder(side * 0.1, -0.145, 0.44, 0.011, 0.02, "chrome", seg=10)
    metal.cylinder(0.11, -depth / 2 + 0.095, 0.81, 0.026, 0.012, "chrome", seg=segments(14))
    metal.tube((-0.17, -depth / 2 + 0.005, 0.12), (-0.17, -depth / 2 + 0.005, 0.30), 0.008, "chrome", seg=8)
    return place(ctx, unit, room, "toilet", x, y, yaw)


# ---------------------------------------------------------------------------
# Pia com gabinete
# ---------------------------------------------------------------------------
VANITY_WIDTH, VANITY_DEPTH, VANITY_TOP = 1.2, 0.5, 0.90
BASIN_X, BASIN_Y, BASIN_HALF = 0.2, 0.02, (0.19, 0.14)


def _ray_to_rect(origin, angle, x0, x1, y0, y1):
    """Ponto em que um raio saindo de `origin` com `angle` cruza o retângulo [x0,x1] x [y0,y1]."""
    dx, dy = math.cos(angle), math.sin(angle)
    distances = []
    if abs(dx) > 1e-9:
        distances.append(((x1 if dx > 0 else x0) - origin[0]) / dx)
    if abs(dy) > 1e-9:
        distances.append(((y1 if dy > 0 else y0) - origin[1]) / dy)
    distance = min(distances)
    return origin[0] + dx * distance, origin[1] + dy * distance


def _countertop(m):
    """Tampo de louça de 4 cm com furo elíptico para a cuba, contorno e furo com a mesma contagem de pontos."""
    points = 36
    hole = ellipse_outline(BASIN_HALF[0], BASIN_HALF[1], BASIN_X, BASIN_Y, points)
    half_w = VANITY_WIDTH / 2 + 0.02
    outer = [_ray_to_rect((BASIN_X, BASIN_Y), 2 * math.pi * k / points, -half_w, half_w, -VANITY_DEPTH / 2, VANITY_DEPTH / 2 + 0.02)
             for k in range(points)]
    annulus(m, outer, hole, PORCELAIN, thickness=0.04, z_top=VANITY_TOP)


def _basin(m):
    rings = []
    for scale, z in ((1.0, 0.86), (0.97, 0.835), (0.82, 0.79), (0.60, 0.755), (0.40, 0.742)):
        rings.append(oval_ring(BASIN_HALF[0] * scale, BASIN_HALF[1] * scale, z, cx=BASIN_X, cy=BASIN_Y, points=36))
    m.loft(rings, PORCELAIN, False, True, True)
    m.cylinder(BASIN_X, BASIN_Y, 0.742, 0.026, 0.004, "chrome", seg=segments(14))


def _faucet(m, assembly):
    x, y = BASIN_X, -VANITY_DEPTH / 2 + 0.07
    m.lathe([(0.03, 0.0), (0.03, 0.01), (0.02, 0.02), (0.016, 0.06)], x, y, VANITY_TOP, "chrome", seg=segments(16), smooth=True)
    spout = craft.tube_along([(x, y, VANITY_TOP + 0.05), (x, y + 0.06, VANITY_TOP + 0.075), (x, y + 0.12, VANITY_TOP + 0.06),
                              (x, y + 0.135, VANITY_TOP + 0.03)], 0.0105, 10, 6, name="sink_spout")
    assembly.add_mesh(spout, "chrome")
    m.box(x + 0.035, y, VANITY_TOP + 0.045, 0.06, 0.012, 0.012, "chrome")


def _cabinet(m):
    for sx in (-1, 1):
        m.box(sx * (VANITY_WIDTH / 2 - 0.02), 0, 0.08, 0.04, VANITY_DEPTH - 0.02, 0.78, PAINT_WHITE_V)
    m.box(0, 0, 0.08, VANITY_WIDTH - 0.04, VANITY_DEPTH - 0.02, 0.03, PAINT_WHITE)
    m.box(0, -VANITY_DEPTH / 2 + 0.01, 0.10, VANITY_WIDTH - 0.04, 0.02, 0.76, PAINT_WHITE)
    m.box(0, 0, 0.0, VANITY_WIDTH - 0.08, VANITY_DEPTH - 0.08, 0.08, "up_paint_white")
    front = VANITY_DEPTH / 2 - 0.035
    for sign in (-1, 1):
        cx = sign * (VANITY_WIDTH / 4 - 0.005)
        joinery.framed_panel(m, cx, front, 0.12, VANITY_WIDTH / 2 - 0.035, 0.70, PAINT_WHITE, PAINT_WHITE, depth=0.022, frame=0.045,
                             frame_mat_v=PAINT_WHITE_V)
        joinery.knob(m, cx - sign * (VANITY_WIDTH / 4 - 0.1), front + 0.022, 0.62, "chrome", 1.2)


def make_vanity(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Pia com gabinete branco de portas almofadadas, tampo e cuba de louça, misturador cromado e copo de escovas."""
    cy = flush_center(room, x, y, yaw, VANITY_DEPTH)
    unit = Assembly("bath_sink")
    cabinet = unit.part(PAINTED)
    top = unit.part(CERAMIC_FINISH, builder_class=WeldedBuilder)
    fittings = unit.part(METAL)
    with cabinet.at(0, cy, 0):
        _cabinet(cabinet)
    with top.at(0, cy, 0):
        _countertop(top)
        top.box(0, -VANITY_DEPTH / 2 + 0.01, VANITY_TOP, VANITY_WIDTH + 0.04, 0.02, 0.09, PORCELAIN)
    with fittings.at(0, cy, 0):
        _basin(fittings)
        _faucet(fittings, unit)
    things = unit.part(WOOD, builder_class=small.UvBuilder)
    with things.at(0, cy, VANITY_TOP):
        small.glass_tumbler(things, 0.52, -0.12, 0.0, 0.032, 0.095, water=0.0)
        for index, tint in enumerate(("up_paint_blue", "up_paint_red")):
            things.tube((0.52 + 0.012 * (index * 2 - 1), -0.12, 0.012), (0.52 + 0.03 * (index * 2 - 1), -0.12, 0.17), 0.0055, tint, seg=6)
        things.cylinder(-0.50, -0.14, 0.0, 0.05, 0.016, "up_paint_white", seg=segments(16))
        things.soft_box(-0.50, -0.14, 0.016, 0.07, 0.045, 0.022, "up_paint_cream", radius=0.012, edge=0.006)
    return place(ctx, unit, room, "vanity", x, y, yaw, z, name="bath_sink", anchor=anchor, collision_top=VANITY_TOP)


# ---------------------------------------------------------------------------
# Armário de remédios com o espelho rachado
# ---------------------------------------------------------------------------
def make_medicine_cabinet(ctx, room, wall, along, z_bottom, *, door_open_deg=28):
    """Armário de embutir branco, porta-espelho rachada meio aberta, prateleiras com frascos e uma cartela de comprimidos."""
    width, height, depth = 0.56, 0.72, 0.14
    x, y, yaw = wall_spot(room, wall, along)
    unit = Assembly("medicine_cabinet")
    box = unit.part(PAINTED)
    box.box(0, depth / 2, 0, width, depth, 0.02, PAINT_WHITE)
    box.box(0, depth / 2, height - 0.02, width, depth, 0.02, PAINT_WHITE)
    for sx in (-1, 1):
        box.box(sx * (width / 2 - 0.01), depth / 2, 0, 0.02, depth, height, PAINT_WHITE_V)
    box.box(0, 0.008, 0, width, 0.016, height, "up_paint_white")
    for level in (0.26, 0.49):
        box.box(0, depth / 2, level, width - 0.04, depth - 0.02, 0.014, PAINT_WHITE)
    bottles = unit.part(METAL, builder_class=small.UvBuilder)
    for cx, tall in ((-0.18, 0.08), (-0.10, 0.065), (0.04, 0.075), (0.15, 0.06)):
        small.pill_bottle(bottles, cx, depth / 2, 0.504, 0.018, tall)
    bottles.box(0.12, depth / 2, 0.274, 0.10, 0.06, 0.07, "up_paint_cream")
    bottles.box(-0.12, depth / 2, 0.274, 0.06, 0.07, 0.10, "up_plastic_white")
    for strip in range(3):
        bottles.box(-0.01 + strip * 0.012, depth / 2 + 0.01, 0.274, 0.01, 0.05, 0.002, "chrome")
    door = unit.part(WOOD)
    with door.at(-width / 2, depth, 0, rz=door_open_deg):
        door.box(width / 2, 0.01, 0, width, 0.02, height, PAINT_WHITE)
        door.panel(width / 2, 0.0205, height / 2, width - 0.06, height - 0.06, "up_mirror_cracked", "front")
        door.box(width / 2, 0.0, -0.02, width + 0.02, 0.012, 0.02, PAINT_WHITE)
    return place(ctx, unit, room, "medicine_cabinet", x, y, yaw, floor_z(room) + z_bottom, mode="wall")


# ---------------------------------------------------------------------------
# Toalheiro com toalhas, cortina de box
# ---------------------------------------------------------------------------
def make_towel_bar(ctx, room, wall, along, z):
    """Barra cromada com suportes e duas toalhas (verde e rosa) caídas por cima, simuladas."""
    x, y, yaw = wall_spot(room, wall, along)
    bar_y = 0.075
    unit = Assembly("towel_bar")
    metal = unit.part(METAL)
    metal.tube((-0.34, bar_y, 0), (0.34, bar_y, 0), 0.0115, "chrome", seg=segments(12), smooth=True)
    for sx in (-0.33, 0.33):
        metal.box(sx, bar_y / 2, -0.014, 0.024, bar_y, 0.028, "chrome")
        metal.box(sx, 0.006, -0.025, 0.04, 0.012, 0.05, "chrome")
    hold = MeshBuilder("towel_hold")
    hold.finish = None
    hold.box(0, bar_y, -0.0115, 0.68, 0.023, 0.023, "chrome")
    hold.box(0, -0.01, -1.4, 2.0, 0.02, 2.0, "chrome")
    big = fabric.settle_cloth(0.52, 1.20, (-0.02, bar_y + 0.10), 0.026, [hold], "up_towel_green", cell=0.045, wrinkles=0.012,
                              seed=ctx.seed + 51, uv_scale=1.0, thickness=0.01, subsurf=0, frames=60, fold=(None, None, bar_y - 0.012, bar_y + 0.012))
    small_towel = fabric.settle_cloth(0.28, 0.60, (0.25, bar_y + 0.07), 0.027, [hold, big], "up_towel_pink", cell=0.04,
                                      wrinkles=0.01, seed=ctx.seed + 52, uv_scale=1.0, thickness=0.008, subsurf=0, frames=60,
                                      fold=(None, None, bar_y - 0.02, bar_y + 0.026))
    unit.add_mesh(big, "up_towel_green")
    unit.add_mesh(small_towel, "up_towel_pink")
    return place(ctx, unit, room, "towel_bar", x, y, yaw, floor_z(room) + z, mode="wall")


def make_shower_curtain(ctx, room, x, rod_y0, rod_y1, hang_length, *, rod_z=1.85, drop=1.3):
    """Cortina de box de vinil puxada só até a metade da vara, com pregas fundas, argolas e a barra manchada de bolor."""
    unit = Assembly("shower_curtain")
    metal = unit.part(METAL)
    metal.tube((0, rod_y0, rod_z), (0, rod_y1, rod_z), 0.012, "chrome", seg=segments(12), smooth=True)
    for end in (rod_y0, rod_y1):
        metal.cylinder(0, end, rod_z - 0.04, 0.02, 0.08, "chrome", seg=segments(10))
    count = int(hang_length / 0.095)
    for index in range(count):
        ring_y = rod_y1 - 0.05 - index * (hang_length - 0.08) / max(1, count - 1)
        metal.torus(0, ring_y, rod_z, 0.0205, 0.0022, "chrome", seg=segments(14), seg_minor=5, ry=90)
    vinyl = unit.part(CLOTH)

    def fn(u, v):
        y = rod_y1 - hang_length + u * hang_length
        pleat = (0.055 + 0.030 * v) * math.sin(u * math.tau * count * 0.5 + 0.4) + 0.012 * math.sin(u * 37 + v * 3)
        hem = drop * (1.0 + 0.025 * math.sin(u * math.tau * count * 0.5 + 1.1))
        return pleat, y, rod_z - 0.035 - v * hem

    vinyl.surface(fn, count * 10, 8, "up_curtain_vinyl", uv_size=(hang_length, drop), smooth=True)
    return place(ctx, unit, room, "shower_curtain", x, 0.0, 0.0, mode="wall")       # pendurada na vara, não apoiada


# ---------------------------------------------------------------------------
# Lixeira
# ---------------------------------------------------------------------------
def make_trash_bin(ctx, room, x, y, *, z=None, height=0.32, radius=0.14, mat="plastic_gray", overflowing=False):
    """Lixeira de plástico com pedal e papéis amassados; `overflowing` enche até transbordar (cozinha usa)."""
    material = {"plastic_gray": "up_plastic_gray"}.get(mat, mat)
    unit = Assembly("trash_bin")
    body = unit.part(craft.Finish(bevel=0.003, bevel_segments=2, smooth_angle=55.0, bevel_angle=45.0))
    body.lathe([(radius * 0.80, 0.0), (radius * 0.86, 0.01), (radius * 0.95, height * 0.6), (radius, height)], 0, 0, 0, material,
               seg=segments(24), smooth=True, cap_top=False)
    body.torus(0, 0, height, radius, 0.007, material, seg=segments(24), seg_minor=5)
    body.box(0, radius * 0.9, 0.0, 0.07, 0.04, 0.025, "up_plastic_black")
    trash = unit.part(craft.Finish(bevel=0.0, smooth_angle=60.0))
    count = 7 if overflowing else 3
    for index in range(count):
        angle = index * 2.1
        spread = radius * (0.35 if overflowing else 0.28)
        plush.ellipsoid(trash, spread * math.cos(angle), spread * math.sin(angle),
                        height - 0.03 + (0.05 + 0.02 * index if overflowing else 0.0), 0.05, 0.045, 0.045, "up_paper_blank",
                        seg=8, rings=5, turn=(index * 20, index * 33, index * 41))
    return place(ctx, unit, room, "trash_bin", x, y, 0.0, z)
