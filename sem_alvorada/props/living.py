"""Sala de estar: sofá, poltrona, mesa de centro, TV de tubo com console, relógio de pé, abajur de chão."""
from . import parts
from .kit import MeshBuilder
from .placement import flush_center, place


def _upholstered_seat(m, width, depth, fabric, seats, arm=0.17, leg_mat="wood_dark"):
    """Estofado em U com `seats` assentos: base, encosto, braços, almofadas de assento e de encosto."""
    seat_w = (width - 2 * arm) / seats
    parts.four_legs(m, -width / 2 + 0.04, -depth / 2 + 0.04, width / 2 - 0.04, depth / 2 - 0.04, 0.10, 0.06, leg_mat)
    m.soft_box(0, 0, 0.10, width, depth, 0.18, fabric, radius=0.06, edge=0.03)
    m.soft_box(0, -depth / 2 + 0.10, 0.28, width, 0.20, 0.52, fabric, radius=0.06, edge=0.04)
    for side in (-1, 1):
        m.soft_box(side * (width / 2 - arm / 2), 0, 0.10, arm, depth, 0.50, fabric, radius=0.06, edge=0.035)
    for i in range(seats):
        cx = (i - (seats - 1) / 2) * seat_w
        m.soft_box(cx, 0.09, 0.28, seat_w - 0.01, depth - 0.24, 0.14, fabric, radius=0.05, edge=0.035)
        with m.at(cx, -depth / 2 + 0.22, 0.42, rx=12):
            m.soft_box(0, 0, 0, seat_w - 0.03, 0.17, 0.38, fabric, radius=0.05, edge=0.035)


def make_sofa(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Sofá de três lugares de frente para a TV, com uma manta jogada e um travesseiro de quem dormiu ali."""
    m = MeshBuilder("sofa_living")
    _upholstered_seat(m, 2.1, 0.9, "fabric_blue", 3)
    with m.at(-0.55, 0.12, 0.43, rz=14, rx=-4):
        m.soft_box(0, 0, 0, 0.7, 0.5, 0.08, "plaid_blanket", radius=0.05, edge=0.03, uv=1.3)
    with m.at(-0.62, 0.36, 0.30, rz=-30):
        m.soft_box(0, 0, 0, 0.5, 0.3, 0.10, "plaid_blanket", radius=0.04, edge=0.04, uv=1.3)
    with m.at(0.72, -0.05, 0.43, rx=-12, rz=20):
        m.soft_box(0, 0, 0, 0.46, 0.30, 0.13, "linen_dirty", radius=0.08, edge=0.05, corner_points=3)
    return place(ctx, m, room, "sofa", x, y, yaw, z, name="sofa_living", anchor=anchor)


def make_armchair(ctx, room, x, y, yaw, *, fabric="fabric_gray", worn=False, z=None):
    m = MeshBuilder("armchair")
    _upholstered_seat(m, 0.86, 0.86, fabric, 1, arm=0.16)
    if worn:
        with m.at(0.0, 0.1, 0.28, rx=-3):
            m.soft_box(0, 0, 0, 0.5, 0.55, 0.16, "leather_brown", radius=0.06, edge=0.04)
    return place(ctx, m, room, "armchair", x, y, yaw, z)


def make_coffee_table(ctx, room, x, y, yaw, *, z=None):
    """Mesa de centro baixa com prateleira inferior e uma xícara fria, o controle e um recorte de jornal por cima."""
    m = MeshBuilder("coffee_table")
    m.box(0, 0, 0.38, 1.0, 0.5, 0.04, "wood_dark")
    m.box(0, 0, 0.12, 0.9, 0.42, 0.025, "wood_mid")
    parts.four_legs(m, -0.5, -0.25, 0.5, 0.25, 0.38, 0.05, "wood_dark")
    parts.mug(m, -0.32, 0.08, 0.42, 0.04, 0.09, "ceramic_cream", handle_dir=1)
    m.box(0.15, -0.09, 0.42, 0.05, 0.16, 0.02, "plastic_gray")
    parts.paper_sheet(m, -0.05, 0.04, 0.42, 0.26, 0.36, "linen_dirty", 0.5)
    return place(ctx, m, room, "coffee_table", x, y, yaw, z)


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
    return place(ctx, m, room, "tv_console", x, y, yaw, z, name="tv_living", anchor=anchor)


def _crt_television(m, z0):
    """TV de tubo de 20 polegadas: caixa frontal, fundo afunilado, tela com o chiado e antena."""
    half_w, half_h = 0.30, 0.24
    front_y, mid_y, back_y = 0.16, -0.06, -0.36
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
