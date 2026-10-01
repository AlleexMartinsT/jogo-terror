"""Mobília dos quartos: casal (Dan e Laura) e da menina (Emma)."""
import math

from . import materials, parts
from .furniture import wall_spot
from .kit import MeshBuilder
from .placement import against_wall, flush_center, floor_z, place

BED_LENGTH = 2.1
BED_WIDTH = 1.6
BED_BACK_EXTENT = 1.12      # do centro da malha até o topo da cabeceira


# ---------------------------------------------------------------------------
# Cama de casal
# ---------------------------------------------------------------------------
def _messy_cover(m, rng, head_y, foot_y, top_z, half_width):
    """Edredom jogado: cobre do pé até o meio, escorre pelos lados e forma dobras no meio."""
    phase = [rng.uniform(0, 6.28) for _ in range(3)]
    hang = (0.20, 0.30)          # lado da Laura (esquerda) quase arrumado; lado do Dan escorrendo

    def fn(u, v):
        y = foot_y + (head_y - foot_y) * u
        t = v * 8
        edge = int(min(t, 7))
        f = t - edge
        base = [(-1.0, -1), (-1.02, -0.5), (-0.96, 0.02), (-0.5, 0.025), (0.0, 0.03), (0.5, 0.02), (0.96, 0.0),
                (1.02, -0.6), (1.0, -1)]
        (ax, az), (bx, bz) = base[edge], base[edge + 1]
        px, pz = ax + (bx - ax) * f, az + (bz - az) * f
        side_hang = hang[0] if px < 0 else hang[1]
        z = top_z + (pz * side_hang if pz < 0 else pz)
        ripple = 0.018 * math.sin(y * 9 + phase[0]) + 0.014 * math.sin(px * 7 + y * 4 + phase[1])
        if abs(pz) < 0.1:
            z += ripple + 0.05 * max(0.0, u - 0.82) / 0.18 + 0.03 * math.exp(-((y - 0.15) ** 2) * 18)
        return (px * half_width, y, z)

    m.surface(fn, 9, 8, "plaid_blanket", uv_size=(1.3, 1.6), flip=True)


def make_double_bed(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Cama de casal desarrumada: cabeceira baixa (abaixo do peitoril), edredom jogado, travesseiros amassados."""
    rng = ctx.rng
    cy = flush_center(room, x, y, yaw, 2 * BED_BACK_EXTENT)
    m = MeshBuilder("bed_master")
    with m.at(0, cy, 0):
        m.box(0, 0.0, 0.16, BED_WIDTH, BED_LENGTH, 0.18, "wood_dark")
        for cx in (-0.76, 0.76):
            for cyl in (-1.0, 1.0):
                m.box(cx, cyl, 0, 0.07, 0.07, 0.16, "wood_dark")
        m.box(0, -BED_LENGTH / 2 - 0.02, 0.15, BED_WIDTH + 0.06, 0.06, 0.75, "wood_dark")
        m.box(0, -BED_LENGTH / 2 - 0.02, 0.86, BED_WIDTH + 0.10, 0.09, 0.05, "wood_mid")
        m.box(0, BED_LENGTH / 2 + 0.02, 0.15, BED_WIDTH + 0.06, 0.05, 0.27, "wood_dark")
        m.soft_box(0, 0, 0.34, 1.54, 2.02, 0.20, "linen_sheet", radius=0.05, edge=0.03)
        _messy_cover(m, rng, head_y=-0.15, foot_y=1.03, top_z=0.545, half_width=0.79)
        with m.at(0.36, -0.78, 0.55, rz=4):
            m.soft_box(0, 0, 0, 0.66, 0.42, 0.13, "linen_sheet", radius=0.08, edge=0.05, corner_points=3)
        with m.at(-0.36, -0.74, 0.55, rz=-9, rx=-6):
            m.soft_box(0, 0, 0, 0.62, 0.40, 0.11, "linen_dirty", radius=0.08, edge=0.05, corner_points=3)
            m.soft_box(0.0, 0.0, 0.0, 0.5, 0.3, 0.02, "linen_dirty")
    return place(ctx, m, room, "bed", x, y, yaw, z, name="bed_master", anchor=anchor,
                 collision=[(-0.82, cy - 1.13, 0, 0.82, cy + 1.08, 0.62)])


# ---------------------------------------------------------------------------
# Criados-mudos e acessórios de mesa de cabeceira
# ---------------------------------------------------------------------------
def make_nightstand(ctx, room, x, y, yaw, *, anchor=None, z=None, name=None):
    """Criado-mudo 0.5 x 0.5 x 0.55 com gaveta e prateleira aberta; encostado na parede de trás."""
    cy = flush_center(room, x, y, yaw, 0.5)
    m = MeshBuilder(name or "nightstand")
    with m.at(0, cy, 0):
        m.box(0, 0, 0.0, 0.5, 0.5, 0.05, "wood_dark")
        for sx in (-0.235, 0.235):
            m.box(sx, 0, 0.05, 0.03, 0.48, 0.44, "wood_mid")
        m.box(0, -0.235, 0.05, 0.44, 0.03, 0.44, "wood_mid")
        m.box(0, 0, 0.16, 0.44, 0.46, 0.02, "wood_mid")
        m.box(0, 0.02, 0.32, 0.44, 0.44, 0.12, "wood_mid", mats={"front": "veneer_mid"})
        parts.knob(m, 0, 0.245, 0.38, outward=1.0)
        m.box(0, 0.01, 0.52, 0.52, 0.52, 0.03, "wood_dark")
        m.box(0, 0.25, 0.10, 0.44, 0.02, 0.02, "wood_mid")
    return place(ctx, m, room, "nightstand", x, y, yaw, z, name=name, anchor=anchor)


def make_table_lamp(ctx, room, x, y, z, yaw=0.0, *, height=0.4, shade=0.28, lit=True, name=None):
    m = MeshBuilder(name or "lamp")
    parts.table_lamp(m, 0, 0, 0, height, "lampshade_lit" if lit else "lampshade_off", shade=shade)
    return place(ctx, m, room, "lamp", x, y, yaw, z, mode="decor", name=name)


def make_alarm_clock(ctx, room, x, y, z, yaw):
    """Despertador-rádio: dígitos emissivos 6:47. Para o final, troque o material do mostrador por `digits_612`."""
    m = MeshBuilder("AlarmClock")
    m.soft_box(0, 0, 0, 0.19, 0.09, 0.09, "plastic_gray", radius=0.015, edge=0.008)
    m.panel(-0.02, 0.0455, 0.048, 0.10, 0.05, "digits_647", "front")
    for i in range(5):
        m.box(0.055, 0.0455, 0.062 - i * 0.012, 0.03, 0.004, 0.006, "black")
    for i in range(3):
        m.box(0.003 + i * 0.014 - 0.05, 0.046, 0.012, 0.010, 0.004, 0.010, "steel_dark")
    m.box(0, -0.02, 0.09, 0.1, 0.03, 0.008, "steel_dark")
    materials.get("digits_612")       # precisa existir no .blend para a cutscene final trocar o mostrador
    return place(ctx, m, room, "alarm_clock", x, y, yaw, z, mode="decor", name="AlarmClock",
                 props={"sa_alt_material": "digits_612", "sa_time": "6:47"})


def make_bedside_clutter(ctx, room, x, y, z, yaw, kind):
    """Objetos de cabeceira: 'pills' (frasco e copo d'água) ou 'book' (livro com marcador e porta-retrato)."""
    m = MeshBuilder(f"bedside_{kind}")
    if kind == "pills":
        m.cylinder(0, 0, 0, 0.022, 0.07, "pill_orange", seg=8)
        m.cylinder(0, 0, 0.07, 0.024, 0.012, "painted_white", seg=8)
        m.cylinder(0.11, 0.02, 0, 0.035, 0.09, "glass_clear", seg=8, r_top=0.04)
        m.cylinder(0.11, 0.02, 0.0, 0.03, 0.02, "water_dark", seg=8)
    else:
        m.box(0, 0, 0, 0.22, 0.16, 0.035, "fabric_blue")
        m.box(0.003, 0.0, 0.035, 0.20, 0.15, 0.004, "paper_white")
        m.box(-0.09, 0.09, 0.02, 0.012, 0.06, 0.004, "toy_red")
        with m.at(0.19, 0.03, 0.0, rz=-12):
            parts.picture(m, 0, 0.0, 0.085, 0.10, 0.08, "photo_mother_child", frame_mat="brass", border=0.012, depth=0.012)
    return place(ctx, m, room, "bedside", x, y, yaw, z, mode="decor")


# ---------------------------------------------------------------------------
# Cômoda, guarda-roupa, espelho, cesto
# ---------------------------------------------------------------------------
def make_dresser(ctx, room, x, y, yaw, *, z=None):
    cy = flush_center(room, x, y, yaw, 0.5)
    m = MeshBuilder("dresser")
    with m.at(0, cy, 0):
        m.box(0, 0, 0.06, 1.4, 0.5, 0.74, "wood_mid")
        m.box(0, 0.02, 0.80, 1.46, 0.54, 0.035, "wood_dark")
        parts.four_legs(m, -0.68, -0.22, 0.68, 0.22, 0.06, 0.06, "wood_dark")
        parts.drawer_stack(m, 0, 0.25, 0.08, 1.4, 0.70, 3, "wood_dark")
        m.box(0, 0.02, 0.835, 1.0, 0.3, 0.004, "linen_sheet")       # tapete de renda no tampo
    return place(ctx, m, room, "dresser", x, y, yaw, z)


def make_wardrobe(ctx, room, x, y, yaw, *, z=None, width=1.3, depth=0.6):
    """Guarda-roupa de duas portas com uma entreaberta (dez graus), mostrando roupas escuras."""
    cy = flush_center(room, x, y, yaw, depth)
    m = MeshBuilder("wardrobe")
    height = 1.95
    with m.at(0, cy, 0):
        m.box(0, 0.01, 0, width, depth, 0.08, "wood_dark")
        m.box(-width / 2 + 0.02, 0, 0.08, 0.04, depth, height - 0.08, "wood_mid")
        m.box(width / 2 - 0.02, 0, 0.08, 0.04, depth, height - 0.08, "wood_mid")
        m.box(0, depth / 2 - 0.01, 0.08, width - 0.08, 0.02, height - 0.08, "black")
        m.box(0, 0.02, height, width + 0.06, depth + 0.04, 0.05, "wood_dark")
        m.box(0, -depth / 2 + 0.02, 0.08, width - 0.08, 0.03, height - 0.08, "wood_mid")
        m.box(0, -0.05, 1.55, width - 0.08, 0.02, 0.02, "steel_dark")
        for cx, color in ((-0.42, "coat_dark"), (-0.30, "coat_beige"), (-0.18, "coat_dark"), (0.32, "coat_dark")):
            m.box(cx, -0.05, 0.75, 0.1, 0.28, 0.8, color)
            m.box(cx, -0.05, 1.55, 0.006, 0.05, 0.02, "steel_dark")
        door_w = (width - 0.06) / 2
        m.box(-width / 4 - 0.005, depth / 2 + 0.01, 0.10, door_w, 0.025, height - 0.14, "wood_mid", mats={"front": "veneer_mid"})
        with m.at(width / 2 - 0.03, depth / 2 + 0.01, 0.10, rz=-10):
            m.box(-door_w / 2, 0.0, 0.0, door_w, 0.025, height - 0.14, "wood_mid", mats={"front": "veneer_mid"})
            m.box(-door_w + 0.08, 0.02, 0.9, 0.02, 0.02, 0.14, "brass")
        m.box(-0.06, depth / 2 + 0.03, 0.95, 0.02, 0.02, 0.14, "brass")
    return place(ctx, m, room, "wardrobe", x, y, yaw, z)


def make_wall_mirror(ctx, room, wall, along, z, width, height, *, draped=False, art="mirror_plain"):
    """Espelho de parede; `draped` cobre metade com um lençol (luto), deixando uma faixa do vidro à mostra."""
    x, y, yaw = wall_spot(room, wall, along)
    m = MeshBuilder("mirror")
    parts.picture(m, 0, 0.02, 0, width, height, art, frame_mat="wood_dark", border=0.05, depth=0.035)
    if draped:
        drop = height * 0.72

        def fn(u, v):
            wobble = 0.012 * math.sin(u * 14) + 0.008 * math.sin(u * 27 + v * 3)
            return (-(width + 0.16) / 2 + u * (width + 0.16), 0.056 + wobble * (0.4 + v),
                    height / 2 + 0.08 - v * (drop + 0.06 * math.sin(u * 9)))

        m.surface(fn, 10, 4, "linen_dirty", uv_size=(width, drop), flip=False)
        m.box(0, 0.04, height / 2 + 0.05, width + 0.2, 0.04, 0.05, "linen_dirty")
    return place(ctx, m, room, "mirror", x, y, yaw, floor_z(room) + z, mode="wall")


def make_laundry_basket(ctx, room, x, y, *, z=None):
    m = MeshBuilder("laundry_basket")
    parts.wicker_basket(m, 0, 0, 0, 0.22, 0.52)
    parts.clothes_heap(m, 0, 0, 0.44, ctx.rng, 0.16, 0.18)
    m.box(0.18, 0.12, 0.62, 0.05, 0.3, 0.02, "coat_dark")
    return place(ctx, m, room, "laundry_basket", x, y, 0.0, z)


# ---------------------------------------------------------------------------
# Quarto da Emma
# ---------------------------------------------------------------------------
def make_kids_bed(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Caminha intocada: coberta esticada com estrelas, travesseiro e o coelho de pelúcia."""
    length, width = 1.6, 0.85
    cy = flush_center(room, x, y, yaw, 2 * 0.845)
    m = MeshBuilder("kids_bed")
    with m.at(0, cy, 0):
        m.box(0, 0, 0.14, width, length, 0.12, "painted_cream")
        parts.four_legs(m, -width / 2, -length / 2, width / 2, length / 2, 0.14, 0.05, "painted_cream")
        m.extrude([(-0.45, 0.12), (0.45, 0.12), (0.45, 0.66), (0.30, 0.78), (-0.30, 0.78), (-0.45, 0.66)],
                  "xz", -length / 2 - 0.045, -length / 2 + 0.01, "painted_pink")
        m.box(0, length / 2 + 0.02, 0.12, width + 0.04, 0.04, 0.32, "painted_pink")
        m.soft_box(0, 0, 0.26, 0.78, 1.52, 0.14, "linen_sheet", radius=0.04, edge=0.02)
        m.soft_box(0, 0.14, 0.38, 0.82, 1.14, 0.06, "comforter_stars", radius=0.04, edge=0.025, uv=1.6)
        m.soft_box(0, -0.42, 0.395, 0.80, 0.20, 0.05, "linen_sheet", radius=0.03, edge=0.02)
        m.soft_box(0, -0.60, 0.40, 0.50, 0.30, 0.10, "linen_sheet", radius=0.06, edge=0.04, corner_points=3)
        parts.rabbit(m, 0.03, -0.6, 0.50, 0.9, sitting_yaw=math.radians(8))
    return place(ctx, m, room, "kids_bed", x, y, yaw, z, name="kids_bed", anchor=anchor,
                 collision=[(-0.44, cy - 0.84, 0, 0.44, cy + 0.84, 0.46)])


def make_toy_shelf(ctx, room, wall, along, *, width=1.05, depth=0.34, height=0.5):
    """Estante baixa de brinquedos, com nichos, caixas coloridas e uma boneca. O topo fica livre para a pilha."""
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("toy_shelf")
    m.box(0, 0, 0, width, depth, 0.03, "painted_cream")
    for sx in (-width / 2 + 0.015, width / 2 - 0.015, 0.0):
        m.box(sx, 0, 0.03, 0.03, depth, height - 0.03, "painted_cream")
    m.box(0, -depth / 2 + 0.01, 0.03, width, 0.02, height - 0.03, "painted_white")
    m.box(0, 0, 0.24, width, depth, 0.025, "painted_cream")
    m.box(0, 0.015, height - 0.025, width + 0.03, depth + 0.03, 0.025, "painted_pink")
    m.box(-0.25, 0.0, 0.03, 0.34, 0.24, 0.20, "toy_red")
    m.box(0.26, 0.0, 0.03, 0.34, 0.24, 0.20, "toy_blue")
    parts.teddy(m, -0.25, 0.0, 0.265, 0.55, "plush_yellow")
    m.box(0.26, 0.0, 0.265, 0.3, 0.2, 0.09, "toy_green")
    parts.rabbit(m, 0.25, 0.04, 0.355, 0.6)
    return place(ctx, m, room, "toy_shelf", x, y, yaw)


def make_toy_chest(ctx, room, wall, along, *, z=None):
    x, y, yaw = against_wall(room, wall, along, 0.4)
    m = MeshBuilder("toy_chest")
    m.box(0, 0, 0.0, 0.76, 0.4, 0.06, "wood_dark")
    m.box(0, 0, 0.06, 0.72, 0.38, 0.30, "painted_pink")
    m.box(0, 0.0, 0.36, 0.76, 0.42, 0.06, "painted_cream")
    m.cylinder(0, 0, 0.42, 0.13, 0.02, "painted_pink", seg=8)
    parts.teddy(m, -0.16, 0.0, 0.44, 0.9, "plush_brown", yaw=0.4)
    return place(ctx, m, room, "toy_chest", x, y, yaw, z)


def make_doll_house(ctx, room, wall, along, *, z=None):
    """Casa de bonecas de dois andares, aberta na frente, com quatro móveis de brinquedo."""
    width, depth, height = 0.9, 0.42, 0.72
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("doll_house")
    m.box(0, 0, 0, width, depth, 0.03, "wood_dark")
    m.box(0, -depth / 2 + 0.01, 0.03, width, 0.02, height - 0.2, "painted_pink")
    for sx in (-width / 2 + 0.01, width / 2 - 0.01, 0.0):
        m.box(sx, 0, 0.03, 0.02, depth, height - 0.2, "painted_pink")
    m.box(0, 0, 0.36, width, depth, 0.02, "painted_cream")
    m.box(0, 0.01, height - 0.17, width + 0.04, depth + 0.02, 0.02, "painted_cream")
    m.extrude([(-width / 2 - 0.03, height - 0.15), (width / 2 + 0.03, height - 0.15), (0, height + 0.08)],
              "xz", -depth / 2, depth / 2 + 0.04, "toy_red")
    m.box(-0.28, 0.04, 0.05, 0.2, 0.12, 0.09, "toy_blue")
    m.box(0.22, 0.03, 0.05, 0.16, 0.16, 0.12, "toy_yellow")
    m.box(-0.1, 0.05, 0.38, 0.22, 0.14, 0.07, "toy_green")
    m.box(0.28, 0.02, 0.38, 0.12, 0.12, 0.16, "plush_pink")
    with m.at(width / 2 + 0.005, depth / 2, 0.03, rz=70):
        m.box(-0.16, 0, 0, 0.32, 0.015, height - 0.2, "painted_cream")
    return place(ctx, m, room, "doll_house", x, y, yaw, z)


def make_kid_desk(ctx, room, wall, along, *, z=None):
    """Escrivaninha pequena: crayons num copo, folhas soltas, papel em branco e a caixa de música."""
    width, depth = 1.05, 0.5
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("kid_desk")
    m.box(0, 0, 0.53, width, depth, 0.04, "wood_mid")
    parts.four_legs(m, -width / 2 + 0.02, -depth / 2 + 0.02, width / 2 - 0.02, depth / 2 - 0.02, 0.53, 0.05, "painted_pink")
    m.box(0.25, 0.0, 0.34, 0.4, depth - 0.06, 0.19, "painted_cream")
    parts.knob(m, 0.25, depth / 2 - 0.03, 0.43, "brass")
    m.box(0, 0.02, 0.57, 0.62, 0.02, 0.002, "paper_white")
    parts.paper_sheet(m, -0.28, 0.06, 0.573, 0.21, 0.29, "note_crayon", 0.2)
    m.cylinder(-0.4, -0.12, 0.57, 0.035, 0.09, "toy_yellow", seg=8)
    for i, color in enumerate(("toy_red", "toy_blue", "toy_green")):
        m.bar((-0.4, -0.12, 0.64), (-0.4 + 0.02 * (i - 1), -0.12 + 0.01, 0.72), 0.012, color)
    _music_box(m, 0.28, -0.05, 0.57)
    return place(ctx, m, room, "kid_desk", x, y, yaw, z)


def _music_box(m, cx, cy, z0):
    """Caixa de música com tampa aberta e uma bailarina de pé no centro."""
    m.box(cx, cy, z0, 0.16, 0.12, 0.07, "wood_dark", mats={"top": "brass"})
    with m.at(cx, cy - 0.06, z0 + 0.07, rx=-105):
        m.box(0, 0.06, 0, 0.16, 0.12, 0.012, "wood_dark")
    m.cylinder(cx, cy, z0 + 0.07, 0.006, 0.05, "plush_pink", seg=5)
    m.cylinder(cx, cy, z0 + 0.09, 0.03, 0.02, "plush_white", seg=8, r_top=0.008)
    m.cylinder(cx, cy, z0 + 0.12, 0.008, 0.02, "skin_hand", seg=5)


def make_night_light(ctx, room, wall, along, z):
    """Luz noturna de tomada, em forma de meia-lua: o domo emissivo é o que brilha."""
    x, y, yaw = wall_spot(room, wall, along)
    m = MeshBuilder("night_light")
    m.box(0, 0.015, 0, 0.07, 0.03, 0.10, "painted_white")
    m.lathe([(0.001, 0), (0.038, 0.004), (0.036, 0.02), (0.022, 0.034), (0.001, 0.04)], 0, 0.03, 0.05,
            "night_light", seg=8, smooth=False, cap_bottom=False, cap_top=False)
    return place(ctx, m, room, "night_light", x, y, yaw, floor_z(room) + z, mode="wall")


def make_letter_blocks(ctx, room, x, y):
    """Quatro cubos de alfabeto (E, M, M, A) no tapete; um deles tombado."""
    size = 0.075
    m = MeshBuilder("letter_blocks")
    layout_of_blocks = (("block_e", 0.0, 0.0, 6), ("block_m", 0.09, 0.005, -4), ("block_m", 0.19, -0.01, 10),
                        ("block_a", 0.30, 0.06, 55))
    for material, dx, dy, turn in layout_of_blocks:
        with m.at(dx, dy, 0, rz=turn):
            with m.at(-size / 2, -size / 2, 0):
                m.box(size / 2, size / 2, 0, size, size, size, material, uv=1 / size)
    return place(ctx, m, room, "letter_blocks", x, y, 0.0, floor_z(room) + 0.014, mode="decor")


def make_small_shoes(ctx, room, x, y, yaw, *, z=None):
    """Par de sapatinhos rosa, lado a lado, ao pé da cama."""
    m = MeshBuilder("small_shoes")
    for side in (-1, 1):
        with m.at(side * 0.06, 0, 0, rz=side * 6):
            m.soft_box(0, 0, 0, 0.07, 0.17, 0.035, "plush_pink", radius=0.03, edge=0.012)
            m.soft_box(0, -0.035, 0.03, 0.065, 0.09, 0.03, "plush_pink", radius=0.025, edge=0.01)
            m.box(0, 0.0, 0.0, 0.07, 0.17, 0.008, "black")
    return place(ctx, m, room, "shoes", x, y, yaw, z, mode="decor")
