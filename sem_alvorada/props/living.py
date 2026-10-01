"""Sala de estar: sofá, poltrona, mesa de centro e abajur de chão, além de miudezas de quem mora ali.

A TV com o console fica em `tv.py` e o relógio de pé em `clock.py`. Os estofados são montados com uma
`Assembly` (madeira firme + estofado macio): ver `assembly.py` e `shapes.py`.
"""
import math

from .. import craft
from . import parts, shapes, tex_sala  # noqa: F401  (tex_sala registra texturas e materiais da sala)
from .assembly import Assembly
from .placement import place

LIFT = 0.12                    # altura dos pés do estofado


def _upholstered_seat(asm, width, depth, fabric, seats, *, arm_half=0.085, back_top=0.9, cushion_skew=0.0):
    """Estofado com `seats` lugares: pés torneados, base, braços enrolados, encosto e almofadas soltas.

    Medidas de sofá de três lugares americano: assento a 0,46 m, braço a 0,64 m, encosto a 0,9 m,
    profundidade 0,9 m. Devolve o contorno interno dos braços (x_min, x_max) onde as almofadas ficam.
    """
    wood, soft = asm.wood, asm.soft
    roll_radius = arm_half / math.cos(math.radians(35))
    arm_x = width / 2 - roll_radius
    inner = arm_x - arm_half
    span = 2 * inner
    # base de madeira: pés torneados e travessas aparentes sob o estofado
    for sx in (-1, 1):
        for sy in (-1, 1):
            shapes.turned_leg(wood, sx * (width / 2 - 0.085), sy * (depth / 2 - 0.085), 0.0, LIFT + 0.02, 0.036,
                              "walnut_v", "baluster")
    wood.box(0, depth / 2 - 0.085, 0.04, width - 0.2, 0.035, 0.08, "walnut")
    wood.box(0, -depth / 2 + 0.085, 0.04, width - 0.2, 0.035, 0.08, "walnut")
    for sx in (-1, 1):
        wood.box(sx * (width / 2 - 0.085), 0, 0.04, 0.035, depth - 0.2, 0.08, "walnut")
    # corpo estofado: assento corrido, encosto fixo e braços
    soft.soft_box(0, 0, LIFT, width, depth, 0.17, fabric, radius=0.06, edge=0.025)
    soft.soft_box(0, -depth / 2 + 0.105, LIFT + 0.05, span + 0.05, 0.21, 0.52, fabric, radius=0.07, edge=0.04)
    for sx in (-1, 1):
        shapes.rolled_arm(soft, sx * arm_x, -depth / 2 + 0.01, depth / 2 - 0.015, LIFT, arm_half, 0.545, fabric)
        shapes.scroll_face(soft, sx * arm_x, depth / 2 - 0.015, 0.545, roll_radius * 0.97, fabric)
    # almofadas soltas de assento e de encosto
    seat_w = span / seats - 0.006
    seat_z = LIFT + 0.17
    for index in range(seats):
        cx = (index - (seats - 1) / 2) * (span / seats)
        rows = shapes.cushion(soft, cx, 0.14, seat_z, seat_w, 0.64, 0.17, fabric, squareness=3.4, corner=0.22,
                              crown=0.018, wrinkle=0.0025, phase=index * 1.9)
        shapes.piping_at(soft, rows, 0.82, 0.0045, fabric)
        shapes.piping_at(soft, rows, -0.82, 0.0045, fabric)
        with soft.at(cx, -0.17, seat_z + 0.16, rx=-76):
            rows = shapes.cushion(soft, 0, 0, -0.095, seat_w, 0.50, 0.19, fabric, squareness=3.0, corner=0.22,
                                  crown=0.02, dimple=0.028, wrinkle=0.0025, phase=index * 2.3 + 1)
            shapes.piping_at(soft, rows, 0.82, 0.0045, fabric)
            shapes.button(soft, 0, 0, 0.088, fabric)
    return span


def make_sofa(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Sofá de três lugares de frente para a TV, com uma almofada de quem dormiu ali."""
    asm = Assembly("sofa_living", wood=craft.FURNITURE, soft=craft.RAW)
    asm.soft.finish = craft.Finish(bevel=0.010, bevel_segments=3, smooth_angle=70, subsurf=1)
    span = _upholstered_seat(asm, 2.1, 0.9, "sofa_fabric", 3)
    with asm.at(0.0, 0.0, 0.0):
        throw_cushion(asm.soft, 0.62, 0.0, 0.46, tilt=-24, turn=18, fabric="velvet_burgundy")
    return place(ctx, asm, room, "sofa", x, y, yaw, z, name="sofa_living", anchor=anchor)


def throw_cushion(soft, x, y, z, *, tilt=-20, turn=0, fabric="velvet_burgundy", size=0.42):
    """Almofada de enfeite apoiada no braço: elipsoide achatado levemente amassado."""
    with soft.at(x, y, z, rx=tilt, rz=turn):
        shapes.cushion(soft, 0, 0, 0, size, size, 0.13, fabric, squareness=2.3, corner=0.45, crown=0.012,
                       wrinkle=0.006, phase=turn)


def make_armchair(ctx, room, x, y, yaw, *, fabric="fabric_gray", worn=False, z=None):
    """Poltrona de braços enrolados. `worn=True` troca o tecido por couro gasto (a poltrona velha do escritório)."""
    asm = Assembly("armchair", wood=craft.FURNITURE, soft=craft.RAW)
    asm.soft.finish = craft.Finish(bevel=0.010, bevel_segments=3, smooth_angle=70, subsurf=1)
    cover = "leather_aged" if worn else "armchair_fabric"
    _upholstered_seat(asm, 0.9, 0.88, cover, 1, arm_half=0.07)
    return place(ctx, asm, room, "armchair", x, y, yaw, z)


# --- legado: ainda não refeito (será substituído) ---
from .kit import MeshBuilder  # noqa: E402
from .placement import flush_center  # noqa: E402


def make_coffee_table(ctx, room, x, y, yaw, *, z=None):
    """Mesa de centro baixa com prateleira inferior e uma xícara fria, o controle e um recorte de jornal por cima."""
    m = MeshBuilder("coffee_table")
    m.box(0, 0, 0.38, 1.0, 0.5, 0.04, "wood_dark")
    m.box(0, 0, 0.12, 0.9, 0.42, 0.025, "wood_mid")
    parts.four_legs(m, -0.5, -0.25, 0.5, 0.25, 0.38, 0.05, "wood_dark")
    parts.mug(m, -0.32, 0.08, 0.42, 0.04, 0.09, "ceramic_cream", handle_dir=1)
    m.box(0.15, -0.09, 0.42, 0.05, 0.16, 0.02, "plastic_gray")
    parts.paper_sheet(m, -0.05, 0.04, 0.42, 0.26, 0.36, "linen_dirty", 0.5)
    return place(ctx, m, room, "coffee_table", x, y, yaw, z, collision_top=0.42)


def make_tv_console(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Console de madeira com TV de tubo em cima; a gaveta da esquerda está aberta e o chiado ilumina a sala."""
    depth = 0.5
    cy = flush_center(room, x, y, yaw, depth)
    m = MeshBuilder("tv_living")
    with m.at(0, cy, 0):
        m.box(0, 0, 0.0, 1.2, depth, 0.04, "wood_dark")
        m.box(0, 0, 0.51, 1.24, depth + 0.02, 0.04, "wood_dark")
        for sx in (-0.59, -0.2, 0.2, 0.59):
            m.box(sx, 0, 0.04, 0.02, depth - 0.02, 0.47, "wood_mid")
        m.box(0, -depth / 2 + 0.01, 0.04, 1.2, 0.02, 0.47, "black")
        m.box(0.4, depth / 2 - 0.005, 0.06, 0.38, 0.012, 0.43, "wood_mid", mats={"front": "veneer_mid"})
        parts.knob(m, 0.4, depth / 2 + 0.005, 0.28, "brass")
        m.box(0, 0.0, 0.10, 0.36, 0.26, 0.07, "plastic_gray")
        m.box(0.12, 0.132, 0.125, 0.012, 0.004, 0.012, "led_red")
        # gaveta da esquerda puxada: frente + caixa aberta em cima
        pulled = 0.28
        m.box(-0.4, depth / 2 + pulled, 0.30, 0.38, 0.02, 0.18, "wood_mid", mats={"front": "veneer_mid"})
        parts.knob(m, -0.4, depth / 2 + pulled + 0.01, 0.39, "brass")
        m.box(-0.4, depth / 2 + pulled / 2, 0.30, 0.34, pulled, 0.14, "wood_dark", skip=("top",))
        _crt_television(m, 0.55)
    # o proxy cobre o console e a TV, mas não a gaveta puxada (onde repousa a pilha)
    body = (-0.62, cy - depth / 2, 0.0, 0.62, cy + depth / 2, 0.55)
    television = (-0.34, cy - 0.24, 0.55, 0.26, cy + 0.20, 1.03)
    return place(ctx, m, room, "tv_console", x, y, yaw, z, name="tv_living", anchor=anchor,
                 collision=[body, television])


def _crt_television(m, z0):
    """TV de tubo de 20 polegadas: caixa frontal, fundo afunilado, tela com o chiado e antena."""
    half_w, half_h = 0.30, 0.24
    front_y, mid_y, back_y = 0.18, -0.02, -0.22
    rings = [[(-half_w, front_y, z0), (half_w, front_y, z0), (half_w, front_y, z0 + 2 * half_h), (-half_w, front_y, z0 + 2 * half_h)],
             [(-half_w, mid_y, z0), (half_w, mid_y, z0), (half_w, mid_y, z0 + 2 * half_h), (-half_w, mid_y, z0 + 2 * half_h)],
             [(-0.17, back_y, z0 + 0.06), (0.17, back_y, z0 + 0.06), (0.17, back_y, z0 + 0.38), (-0.17, back_y, z0 + 0.38)]]
    m.loft(rings, "veneer_dark", True, True)
    m.panel(-0.045, front_y + 0.002, z0 + half_h, 0.44, 0.34, "tv_static", "front")
    m.box(-0.045, front_y - 0.004, z0 + half_h - 0.19, 0.48, 0.008, 0.38, "black", skip=("front", "bottom"))
    for dz in (0.34, 0.24):
        with m.at(0.245, front_y, z0 + dz, rx=-90):
            m.cylinder(0, 0, 0, 0.022, 0.02, "plastic_gray", seg=6)
    for i in range(6):
        m.box(0.245, front_y + 0.001, z0 + 0.06 + i * 0.012, 0.09, 0.004, 0.005, "black")
    for side in (-1, 1):
        m.bar((0, -0.1, z0 + 2 * half_h), (side * 0.22, -0.12, z0 + 2 * half_h + 0.34), 0.008, "steel_dark")


def make_floor_lamp(ctx, room, x, y, *, z=None):
    """Abajur de chão: base pesada, haste e cúpula clara."""
    m = MeshBuilder("floor_lamp")
    m.cylinder(0, 0, 0, 0.14, 0.03, "steel_dark", seg=8, r_top=0.12)
    m.tube((0, 0, 0.03), (0, 0, 1.35), 0.014, "brass", seg=5)
    m.frustum(0, 0, 1.28, 0.42, 0.42, 0.28, 0.28, 0.30, "lampshade_lit")
    return place(ctx, m, room, "floor_lamp", x, y, 0.0, z)


def make_grandfather_clock(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Relógio de pé de dois metros parado às 6:12, com o pêndulo visível e imóvel atrás do vidro."""
    depth = 0.34
    cy = flush_center(room, x, y, yaw, depth)
    m = MeshBuilder("grandfather_clock")
    with m.at(0, cy, 0):
        m.box(0, 0, 0, 0.46, depth, 0.28, "wood_dark")
        m.box(0, 0, 0.28, 0.36, depth - 0.06, 1.12, "wood_mid")
        m.box(0, depth / 2 - 0.03, 0.42, 0.24, 0.01, 0.84, "glass_clear")
        m.box(0, depth / 2 - 0.035, 0.42, 0.28, 0.006, 0.88, "black")
        m.bar((0.01, 0.0, 1.30), (0.03, 0.0, 0.62), 0.008, "brass")
        m.cylinder(0.03, 0.0, 0.54, 0.055, 0.012, "brass", seg=8)
        m.box(0, 0, 1.40, 0.44, depth - 0.02, 0.42, "wood_dark")
        m.extrude([(-0.20, 1.82), (0.20, 1.82), (0.14, 1.92), (0.0, 1.98), (-0.14, 1.92)], "xz", -depth / 2 + 0.01,
                  depth / 2 - 0.03, "wood_dark")
        m.panel(0, depth / 2 - 0.015, 1.62, 0.33, 0.33, "clock_face", "front")
        m.box(0, depth / 2 - 0.021, 1.62, 0.37, 0.012, 0.37, "brass", skip=("front",))
        m.box(0, 0, 1.36, 0.48, depth + 0.02, 0.05, "wood_mid")
    return place(ctx, m, room, "grandfather_clock", x, y, yaw, z, name="grandfather_clock", anchor=anchor)


def make_telephone(ctx, room, x, y, z, yaw):
    """Telefone fixo bege com secretária eletrônica ao lado (a luz vermelha piscando é só um LED aceso)."""
    m = MeshBuilder("telephone")
    m.soft_box(0, 0, 0, 0.22, 0.20, 0.07, "plastic_beige", radius=0.02, edge=0.012)
    with m.at(0, -0.02, 0.07, rx=-4):
        m.soft_box(0, 0, 0, 0.19, 0.055, 0.035, "plastic_beige", radius=0.02, edge=0.012)
        m.box(-0.085, 0, 0.0, 0.03, 0.06, 0.05, "plastic_beige")
        m.box(0.085, 0, 0.0, 0.03, 0.06, 0.05, "plastic_beige")
    m.panel(0, 0.03, 0.072, 0.09, 0.07, "black", "top")
    m.soft_box(0.26, 0, 0, 0.20, 0.16, 0.06, "plastic_gray", radius=0.02, edge=0.01)
    m.box(0.30, 0.081, 0.03, 0.016, 0.004, 0.012, "led_red")
    return place(ctx, m, room, "telephone", x, y, yaw, z, mode="decor")
