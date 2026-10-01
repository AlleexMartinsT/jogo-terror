"""Armários da cozinha: carcaça, portas de almofada rebaixada, gavetas, puxadores, dobradiças e tampo.

Tudo é desenhado numa `Assembly` com a origem no centro da base do módulo e a frente em +Y (convenção dos
móveis). Medidas de referência de uma cozinha americana: rodapé de armário 10 cm, caixa de 76 cm, tampo de
3,8 cm que fecha em 0,90 m, armário alto a 1,50 m com 34 cm de profundidade.
"""
import math

from . import kg_shapes
from .kg_shapes import arc_points, segments

TOE_H = 0.10
TOP_Z = 0.90
SLAB_T = 0.038
BODY_TOP = TOP_Z - SLAB_T
DOOR_T = 0.02
GAP = 0.003
STILE = 0.055
RAIL = 0.06
DRAWER_H = 0.14
PANEL_SETBACK = 0.008


# ---------------------------------------------------------------------------
# Ferragens
# ---------------------------------------------------------------------------
def bar_pull(asm, cx, z, y_front, length=0.128, vertical=False):
    """Puxador de barra de latão: dois pés e a barra, sobre uma rosácea escura de gordura acumulada."""
    posts = length / 2 - 0.012
    sides = segments(8, 6)
    if vertical:
        ends = [(cx, y_front, z - posts), (cx, y_front, z + posts)]
        bar = [(cx, y_front + 0.03, z - posts), (cx, y_front + 0.03, z + posts)]
    else:
        ends = [(cx - posts, y_front, z), (cx + posts, y_front, z)]
        bar = [(cx - posts, y_front + 0.03, z), (cx + posts, y_front + 0.03, z)]
    for foot, top in zip(ends, bar):
        asm.round.tube(foot, top, 0.0045, "kg_brass", seg=sides)
    asm.round.tube(bar[0], bar[1], 0.0058, "kg_brass", seg=sides)


def face_hinge(asm, x, z, y_front, height=0.05):
    """Dobradiça de superfície: folha na porta, folha no quadro e o pino cilíndrico no meio."""
    asm.crisp.box(x - 0.011, y_front + 0.0015, z, 0.016, 0.003, height, "kg_brass")
    asm.crisp.box(x + 0.011, y_front + 0.0015, z, 0.016, 0.003, height, "kg_brass")
    asm.round.cylinder(x, y_front + 0.004, z, 0.0042, height, "kg_brass", seg=segments(8, 6))


def grease_mark(asm, cx, cz, y_front, size=0.14):
    """Mancha de gordura escura onde a mão pega: um quad com alfa 1 mm à frente da porta."""
    asm.hard.panel(cx, y_front + 0.0012, cz, size, size, "kg_grease", "front")


# ---------------------------------------------------------------------------
# Portas e gavetas
# ---------------------------------------------------------------------------
def cabinet_door(asm, x0, x1, z0, z1, y_front, stile=STILE, rail=RAIL):
    """Porta de almofada rebaixada: painel recuado 8 mm dentro de um quadro de duas colunas e dois travessões."""
    width, height = x1 - x0, z1 - z0
    cx = (x0 + x1) / 2
    back = y_front - DOOR_T
    m = asm.hard
    m.box(cx, (back + y_front - PANEL_SETBACK) / 2, z0, width, DOOR_T - PANEL_SETBACK, height, "kg_oak_v")
    depth_bar = DOOR_T
    for x in (x0 + stile / 2, x1 - stile / 2):
        m.box(x, back + depth_bar / 2, z0, stile, depth_bar, height, "kg_oak_v")
    for z in (z0, z1 - rail):
        m.box(cx, back + depth_bar / 2, z, width - 2 * stile, depth_bar, rail, "kg_oak")


def hinged_door(asm, x_hinge, x_free, z0, z1, y_front, open_deg=0.0):
    """Porta com dobradiças no lado `x_hinge`, que pode estar entreaberta em `open_deg` graus."""
    direction = 1.0 if x_free > x_hinge else -1.0
    width = abs(x_free - x_hinge)
    pivot_y = y_front - DOOR_T
    with asm.at(x_hinge, pivot_y, 0.0, rz=direction * open_deg):
        x0, x1 = (0.0, width) if direction > 0 else (-width, 0.0)
        cabinet_door(asm, x0, x1, z0, z1, DOOR_T)
        for z in (z0 + 0.07, z1 - 0.12):
            face_hinge(asm, direction * 0.012, z, DOOR_T)


def drawer_front(asm, x0, x1, z0, z1, y_front):
    """Frente de gaveta rasa com o mesmo desenho das portas, em escala menor, e puxador central."""
    cabinet_door(asm, x0, x1, z0, z1, y_front, stile=0.04, rail=0.035)
    bar_pull(asm, (x0 + x1) / 2, (z0 + z1) / 2, y_front)


# ---------------------------------------------------------------------------
# Tampo de laminado com borda arredondada e rodabanca
# ---------------------------------------------------------------------------
def counter_profile(depth, overhang=0.022, splash=0.09, thickness=SLAB_T):
    """Seção (y, z) do tampo: borda frontal arredondada, base chanfrada e rodabanca com concordância."""
    z_bot, z_top = TOP_Z - thickness, TOP_Z
    y_back, y_front = -depth / 2, depth / 2 + overhang
    bullnose, cove, lip = 0.014, 0.018, 0.016
    points = [(y_back, z_bot), (y_front - 0.004, z_bot), (y_front, z_bot + 0.004)]
    points += arc_points(y_front - bullnose, z_top - bullnose, bullnose, 0, 90, 5)
    points += arc_points(y_back + lip + cove, z_top + cove, cove, -90, -180, 5)
    points += [(y_back + lip, z_top + splash - 0.004), (y_back + lip - 0.004, z_top + splash), (y_back, z_top + splash)]
    return points


def laminate_top(asm, x0, x1, depth, overhang=0.022, splash=0.09):
    """Tampo extrudido entre x0 e x1 (a seção vem de `counter_profile`)."""
    asm.hard.extrude(counter_profile(depth, overhang, splash), "yz", x0, x1, "kg_laminate")


# ---------------------------------------------------------------------------
# Módulos
# ---------------------------------------------------------------------------
def base_carcass(asm, width, depth):
    """Rodapé recuado e caixa; a frente da caixa é escura para as frestas entre portas parecerem fundas."""
    asm.hard.box(0, -0.03, 0.0, width - 0.004, depth - 0.07, TOE_H, "kg_toe")
    asm.hard.box(0, 0, TOE_H, width, depth, BODY_TOP - TOE_H, "kg_oak_v", mats={"front": "kg_toe"})


def door_openings(width, count):
    """Pares (x0, x1) de cada porta lado a lado, com frestas de GAP entre elas e nas pontas."""
    each = (width - GAP * (count + 1)) / count
    return [(-width / 2 + GAP + i * (each + GAP), -width / 2 + GAP + i * (each + GAP) + each) for i in range(count)]


def base_cabinet(asm, width, depth, doors=2, drawer=False, open_door=None, open_deg=0.0):
    """Módulo de balcão completo com tampo. `open_door` é o índice da porta entreaberta, se houver."""
    base_carcass(asm, width, depth)
    z0, z1 = TOE_H + GAP, BODY_TOP - GAP
    y_front = depth / 2 + DOOR_T
    if drawer:
        drawer_front(asm, -width / 2 + GAP, width / 2 - GAP, z1 - DRAWER_H, z1, y_front)
        z1 -= DRAWER_H + GAP
    for index, (x0, x1) in enumerate(door_openings(width, doors)):
        hinge_left = index < doors / 2 if doors > 1 else True
        hinge_x, free_x = (x0, x1) if hinge_left else (x1, x0)
        angle = open_deg if index == open_door else 0.0
        hinged_door(asm, hinge_x, free_x, z0, z1, y_front, angle)
        handle_x = free_x - math.copysign(0.05, free_x - hinge_x)
        handle_z = z1 - 0.1
        if angle == 0.0:
            grease_mark(asm, handle_x, handle_z, y_front)
            bar_pull(asm, handle_x, handle_z, y_front, 0.1, vertical=True)
    laminate_top(asm, -width / 2 - 0.0, width / 2, depth)


def wall_cabinet(asm, width, depth, z0, height, open_door=None, open_deg=0.0, stock=None):
    """Armário alto pendurado: caixa oca (laterais, tampo, fundo, prateleira) e portas; `stock(asm, z, x0, x1)`
    desenha o que fica na prateleira, visível pela porta entreaberta."""
    thick = 0.018
    z1 = z0 + height
    m = asm.hard
    m.box(-width / 2 + thick / 2, 0, z0, thick, depth, height, "kg_pine")
    m.box(width / 2 - thick / 2, 0, z0, thick, depth, height, "kg_pine")
    m.box(0, 0, z1 - thick, width, depth, thick, "kg_pine")
    m.box(0, 0, z0, width, depth, thick, "kg_pine")
    m.box(0, -depth / 2 + 0.004, z0, width, 0.008, height, "kg_toe")
    shelf_z = z0 + height * 0.48
    m.box(0, -0.01, shelf_z, width - 2 * thick, depth - 0.03, 0.016, "kg_pine")
    if stock:
        stock(asm, shelf_z + 0.016, -width / 2 + thick, width / 2 - thick)
    count = max(2, round(width / 0.5))
    y_front = depth / 2 + DOOR_T
    for index, (x0, x1) in enumerate(door_openings(width, count)):
        hinge_left = index < count / 2
        hinge_x, free_x = (x0, x1) if hinge_left else (x1, x0)
        angle = open_deg if index == open_door else 0.0
        hinged_door(asm, hinge_x, free_x, z0 + GAP, z1 - GAP, y_front, angle)
        if angle == 0.0:
            bar_pull(asm, free_x - math.copysign(0.045, free_x - hinge_x), z0 + 0.14, y_front, 0.1, vertical=True)
    asm.hard.box(0, depth / 2 + 0.002, z1, width + 0.03, depth + 0.036, 0.03, "kg_oak")        # cornija
