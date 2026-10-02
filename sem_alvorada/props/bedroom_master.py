"""Cama de casal do quarto de Dan e Laura: nogueira torneada, colchão, lençol e edredom simulados, travesseiros.

Coordenadas locais da cama: X atravessa (X+ é o lado de Dan, onde fica a lanterna; X- é o lado de Laura),
Y vai da cabeceira (Y-) ao pé (Y+). A cama real mede 1,60 x 2,10 m (queen); a cabeceira fica abaixo do
peitoril da janela oeste (0,90 m) para não tapar o vidro.
"""
import math

from mathutils import Matrix

from .. import craft
from . import cloth_quartos as fabric
from . import materials
from . import small_quartos as small
from . import woodwork_quartos as joinery
from .assembly_quartos import CLOTH, HERO_WOOD, METAL, UPHOLSTERY, Assembly, segments
from .kit import MeshBuilder
from .placement import flush_center, place

BED_BACK_EXTENT = 1.12        # do centro da malha até a face de trás da cabeceira
POST_X = 0.775                # eixo dos pilares, a partir do centro
HEAD_Y, FOOT_Y = -1.08, 1.04
MATTRESS = (1.50, 2.02, 0.24)
MATTRESS_Z = 0.30
WALNUT, WALNUT_V = joinery.wood_pair("up_walnut")


def _arch_profile(half_width, base_z, rise, points=17):
    """Perfil (x, z) da travessa curva do topo da cabeceira: fundo reto e topo em arco."""
    top = [(half_width * (1 - 2 * i / (points - 1)), base_z + 0.05 + rise * math.sin(math.pi * i / (points - 1)) ** 0.8)
           for i in range(points)]
    return [(-half_width, base_z), (half_width, base_z)] + top


def _headboard(m):
    for side in (-1, 1):
        joinery.turned(m, side * POST_X, HEAD_Y, 0, joinery.POST_PROFILE, 0.90, WALNUT_V, seg=16)
    inner = POST_X - 0.04
    m.box(0, HEAD_Y - 0.01, 0.30, 2 * inner, 0.04, 0.44, WALNUT)
    m.box(0, HEAD_Y, 0.20, 2 * inner, 0.06, 0.11, WALNUT)
    for cx, width in ((-0.535, 0.40), (0.0, 0.62), (0.535, 0.40)):
        joinery.framed_panel(m, cx, HEAD_Y + 0.01, 0.40, width, 0.34, WALNUT, WALNUT, frame_mat_v=WALNUT_V,
                             depth=0.02, frame=0.03)
    m.extrude(_arch_profile(inner, 0.74, 0.07), "xz", HEAD_Y - 0.03, HEAD_Y + 0.03, WALNUT)
    m.box(0, HEAD_Y + 0.035, 0.73, 2 * inner, 0.025, 0.025, WALNUT)


def _footboard(m):
    for side in (-1, 1):
        joinery.turned(m, side * POST_X, FOOT_Y, 0, joinery.POST_PROFILE, 0.54, WALNUT_V, seg=20, radius_scale=0.9)
    inner = POST_X - 0.04
    m.box(0, FOOT_Y, 0.14, 2 * inner, 0.05, 0.10, WALNUT)
    m.box(0, FOOT_Y - 0.01, 0.24, 2 * inner, 0.03, 0.22, WALNUT)
    joinery.framed_panel(m, 0, FOOT_Y, 0.24, 2 * inner - 0.06, 0.22, WALNUT, WALNUT, frame_mat_v=WALNUT_V,
                         depth=0.022, frame=0.03)
    m.box(0, FOOT_Y, 0.46, 2 * inner, 0.05, 0.03, WALNUT)


def _rails_and_slats(m):
    for side in (-1, 1):
        m.box(side * POST_X, (HEAD_Y + FOOT_Y) / 2, 0.12, 0.05, FOOT_Y - HEAD_Y, 0.19, WALNUT)
        m.box(side * (POST_X - 0.04), 0.0, 0.22, 0.03, 2.0, 0.04, WALNUT)
    count = 17
    for index in range(count):
        y = -0.92 + index * (1.84 / (count - 1))
        m.box(0, y, 0.28, 1.50, 0.075, 0.02, WALNUT_V)
    m.box(0, 0.0, 0.18, 0.10, 2.0, 0.08, WALNUT)


def _bed_skirt(m):
    """Saia plissada nos lados norte (de Laura) e do pé; o lado de Dan fica aberto, mostrando a longarina."""
    half = MATTRESS[0] / 2 + 0.01
    side_length, foot_length = 1.94, 2 * half
    total = side_length + foot_length

    def fn(u, v):
        arc = u * total
        pleat = 0.014 * math.sin(arc * 55)
        if arc < side_length:
            x, y = -half - pleat, -0.92 + arc
        else:
            x, y = -half + (arc - side_length), 1.02 + pleat
        return x, y, MATTRESS_Z - 0.23 * v + 0.004 * math.sin(arc * 31)

    m.surface(fn, 190, 3, "up_cloth_beige", uv_size=(total, 0.23), smooth=True)


def _collision_set():
    """Caixas simplificadas da cama para o pano apoiar: colchão, longarinas, cabeceira e pé."""
    hold = MeshBuilder("bed_hold")
    hold.finish = None
    hold.box(0, 0, MATTRESS_Z, MATTRESS[0], MATTRESS[1], MATTRESS[2], "up_walnut")
    for side in (-1, 1):
        hold.box(side * POST_X, 0, 0.12, 0.05, 2.12, 0.19, "up_walnut")
    hold.box(0, HEAD_Y, 0.0, 1.56, 0.08, 0.9, "up_walnut")
    hold.box(0, FOOT_Y - 0.005, 0.0, 1.56, 0.06, 0.5, "up_walnut")
    return hold


# o pano não pode pender para fora da pegada da cama (proxy de colisão e zonas reservadas do layout)
CLOTH_FOLD = (-0.805, 0.805, None, 1.07)
CLOTH_LIMITS = (-0.835, 0.835, None, 1.095)


def _linens(rng_seed):
    """Lençol e edredom simulados sobre a cama: o edredom escorre para o lado de Dan e para o pé."""
    hold = _collision_set()
    sheet = fabric.settle_cloth(1.62, 2.08, (0.0, 0.03), 0.575, [hold], "up_sheet", cell=0.06, wrinkles=0.03,
                                seed=rng_seed, subsurf=0, frames=45, floor=0.0, fold=CLOTH_FOLD, limits=CLOTH_LIMITS)
    duvet = fabric.settle_cloth(1.70, 1.55, (0.30, 0.58), 0.605, [hold, sheet], "up_duvet", cell=0.06, wrinkles=0.03,
                                seed=rng_seed + 1, thickness=0.014, subsurf=0, frames=55, floor=0.0, fold=CLOTH_FOLD,
                                limits=CLOTH_LIMITS, mass=0.40, stiffness=14.0, bending=8.0)
    return sheet, duvet


def _pillows(rng_seed):
    """Travesseiro de Laura (arrumado, no lado X-) e de Dan (amassado pela cabeça, torto, no lado X+)."""
    neat = fabric.pillow(0.70, 0.46, 0.15, "up_pillowcase", dent=0.015, lean=0.10, seed=rng_seed, uv_scale=1.4)
    slept = fabric.pillow(0.72, 0.48, 0.15, "up_pillowcase", dent=0.075, dent_at=(0.05, 0.1), lean=0.07,
                          seed=rng_seed + 3, uv_scale=1.4)
    return (neat, Matrix.Translation((-0.38, -0.70, 0.572)) @ Matrix.Rotation(0.03, 4, "Z")), \
           (slept, Matrix.Translation((0.36, -0.69, 0.572)) @ Matrix.Rotation(-0.16, 4, "Z"))


def make_double_bed(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Cama de casal desarrumada: nogueira torneada, colchão, lençol e edredom caídos, travesseiros amassados."""
    cy = flush_center(room, x, y, yaw, 2 * BED_BACK_EXTENT)
    bed = Assembly("bed_master")
    wood = bed.part(HERO_WOOD)
    with wood.at(0, cy, 0):
        _headboard(wood)
        _footboard(wood)
        _rails_and_slats(wood)
    mattress = bed.part(UPHOLSTERY)
    mattress.soft_box(0, cy, MATTRESS_Z, MATTRESS[0], MATTRESS[1], MATTRESS[2], "up_cloth_white", radius=0.05, edge=0.045,
                      corner_points=3)
    skirt = bed.part(CLOTH)
    with skirt.at(0, cy, 0):
        _bed_skirt(skirt)
    shift = Matrix.Translation((0, cy, 0))
    sheet, duvet = _linens(ctx.seed)
    bed.add_mesh(sheet, "up_sheet", matrix=shift)
    bed.add_mesh(duvet, "up_duvet", matrix=shift)
    for mesh, transform in _pillows(ctx.seed):
        bed.add_mesh(mesh, "up_pillowcase", matrix=shift @ transform)
    return place(ctx, bed, room, "bed", x, y, yaw, z, name="bed_master", anchor=anchor,
                 collision=[(-0.82, cy - 1.13, 0, 0.82, cy + 1.08, 0.62)])


# ---------------------------------------------------------------------------
# Criado-mudo
# ---------------------------------------------------------------------------
def _drawer(m, front_y, shift):
    """Gaveta com frente almofadada e puxador de bola; `shift` a puxa para fora e mostra a caixa."""
    joinery.framed_panel(m, 0, front_y + shift, 0.372, 0.40, 0.142, WALNUT, WALNUT, frame_mat_v=WALNUT_V, depth=0.02,
                         frame=0.026)
    joinery.knob(m, 0, front_y + shift + 0.02, 0.443, "brass", 1.1)
    if shift > 0:
        m.box(0, front_y + shift - 0.19, 0.372, 0.376, 0.38, 0.012, WALNUT)
        for side in (-1, 1):
            m.box(side * 0.182, front_y + shift - 0.19, 0.372, 0.012, 0.38, 0.085, WALNUT)
        m.box(0, front_y + shift - 0.375, 0.372, 0.376, 0.012, 0.085, WALNUT)


def _nightstand_body(m, drawer_shift):
    for sx in (-0.205, 0.205):
        for sy in (-0.205, 0.205):
            joinery.turned(m, sx, sy, 0, joinery.LEG_PROFILE, 0.52, WALNUT_V, seg=16)
    m.box(0, 0, 0.52, 0.50, 0.50, 0.03, WALNUT)
    m.box(0, -0.205, 0.12, 0.40, 0.02, 0.40, WALNUT)
    for side in (-1, 1):
        m.box(side * 0.205, 0, 0.12, 0.02, 0.41, 0.40, WALNUT)
    m.box(0, 0, 0.12, 0.40, 0.41, 0.02, WALNUT)
    m.box(0, 0, 0.35, 0.40, 0.41, 0.02, WALNUT)
    _drawer(m, 0.205, drawer_shift)
    m.box(0, 0.215, 0.14, 0.40, 0.02, 0.025, WALNUT)         # testeira do nicho aberto


def _nightstand_niche(m):
    """Dentro do nicho aberto: dois livros deitados e uma caixa de lenços."""
    with m.at(-0.02, 0.02, 0.14, ry=90):
        small.book(m, 0, 0, 0, 0.04, 0.24, 0.17, 1)
    with m.at(-0.01, 0.03, 0.18, ry=90):
        small.book(m, 0, 0, 0, 0.032, 0.22, 0.16, 3)
    m.box(0.12, 0.0, 0.14, 0.12, 0.10, 0.07, "up_paper_blank")


def make_nightstand(ctx, room, x, y, yaw, *, anchor=None, z=None, name=None, drawer_open=0.0):
    """Criado-mudo de nogueira 0,5 x 0,5 x 0,55 m: pernas torneadas, gaveta almofadada e nicho aberto."""
    cy = flush_center(room, x, y, yaw, 0.5)
    stand = Assembly(name or "nightstand")
    wood = stand.part(HERO_WOOD)
    with wood.at(0, cy, 0):
        _nightstand_body(wood, drawer_open)
    niche = stand.part(HERO_WOOD, builder_class=small.UvBuilder)
    with niche.at(0, cy, 0):
        _nightstand_niche(niche)
    return place(ctx, stand, room, "nightstand", x, y, yaw, z, name=name, anchor=anchor)


# ---------------------------------------------------------------------------
# Abajur e despertador
# ---------------------------------------------------------------------------
LAMP_BASE = [(0.0, 0.0), (0.060, 0.0), (0.066, 0.008), (0.082, 0.045), (0.088, 0.09), (0.074, 0.14), (0.040, 0.18),
             (0.022, 0.205), (0.020, 0.222)]


def make_table_lamp(ctx, room, x, y, z, yaw=0.0, *, height=0.4, shade=0.28, lit=True, name=None):
    """Abajur: base de cerâmica torneada, pescoço e soquete de latão, cúpula de pano que acende (ou não)."""
    k = height / 0.42
    lamp = Assembly(name or "lamp")
    base = lamp.part(craft.STANDARD)
    base.lathe([(r * k, z0 * k) for r, z0 in LAMP_BASE], 0, 0, 0, "up_ceramic", seg=segments(24), smooth=True)
    base.cylinder(0, 0, 0.222 * k, 0.010 * k, 0.07 * k, "brass", seg=segments(10))
    base.cylinder(0, 0, 0.262 * k, 0.020 * k, 0.034 * k, "brass", seg=segments(12))
    base.cylinder(0, 0, 0.292 * k, 0.015 * k, 0.012 * k, "up_plastic_white", seg=segments(12))
    cloth = lamp.part(CLOTH)
    shade_mat = "up_lampshade_lit" if lit else "up_lampshade_off"
    rings = [circle(0, 0, 0.215 * k, shade / 2, segments(28)), circle(0, 0, 0.42 * k, shade * 0.32, segments(28))]
    cloth.loft(rings, shade_mat, cap_start=False, cap_end=False, smooth=True)
    base.torus(0, 0, 0.215 * k, shade / 2, 0.0025, "brass", seg=segments(28), seg_minor=5)
    base.torus(0, 0, 0.42 * k, shade * 0.32, 0.0025, "brass", seg=segments(24), seg_minor=5)
    base.sphere(0, 0, 0.33 * k, 0.026 * k, "lens_glow", seg=segments(12), rings=7)
    return place(ctx, lamp, room, "lamp", x, y, yaw, z, mode="decor", name=name)


def _clock_front(m, display):
    """Frente do despertador (visto de frente, +Y): janela do mostrador à direita, alto-falante à esquerda."""
    face = 0.0425
    m.box(-0.025, face - 0.001, 0.027, 0.112, 0.004, 0.056, "up_plastic_black")
    m.panel(-0.025, face + 0.001, 0.048, 0.100, 0.044, display, "front")
    m.box(0.062, face - 0.001, 0.024, 0.062, 0.003, 0.050, "up_plastic_gray")
    for column in range(6):
        m.box(0.040 + column * 0.009, face + 0.0005, 0.032, 0.0035, 0.002, 0.034, "up_plastic_black")
    for knob_x in (0.040, 0.062):
        m.cylinder(knob_x, face, 0.012, 0.0075, 0.007, "up_plastic_gray", seg=12, caps=(False, True))
    m.box(-0.07, face - 0.002, 0.014, 0.020, 0.003, 0.007, "up_plastic_gray")


ALARM_CLOCK_POSE = (0.47, 8.70, -math.pi / 2)      # x, y, yaw na cabeceira de Laura; o relógio 6:12 do final usa o mesmo lugar


def alarm_clock_assembly(display="digits_647", name="AlarmClock"):
    """Despertador-rádio: carcaça preta, janela de dígitos (`display` é o material), grade de alto-falante, botões e cabo."""
    clock = Assembly(name)
    body = clock.part(METAL)
    body.soft_box(0, 0, 0.005, 0.20, 0.09, 0.077, "up_plastic_black", radius=0.014, edge=0.008, corner_points=3)
    for foot_x in (-0.085, 0.085):
        for foot_y in (-0.032, 0.032):
            body.cylinder(foot_x, foot_y, 0.0, 0.007, 0.005, "up_rubber", seg=8)
    _clock_front(body, display)
    body.box(0, 0.008, 0.082, 0.10, 0.040, 0.008, "up_plastic_gray")           # barra de soneca
    for button_x in (-0.07, -0.05, 0.07):
        body.cylinder(button_x, -0.022, 0.082, 0.007, 0.006, "up_plastic_gray", seg=12)
    cord = craft.tube_along([(0.06, -0.045, 0.02), (0.07, -0.09, 0.006), (0.03, -0.17, 0.004), (0.05, -0.26, 0.004),
                             (0.04, -0.3, 0.004)], 0.0022, 6, 6, name="clock_cord")
    clock.add_mesh(cord, "up_rubber")
    return clock


def make_alarm_clock(ctx, room, x, y, z, yaw):
    """Despertador marcando 6:47 na cabeceira de Laura; a cutscene final o esconde e mostra o 6:12 no mesmo lugar."""
    materials.get("digits_612")     # precisa existir no .blend: o roteiro de cutscene troca o mostrador por ele
    return place(ctx, alarm_clock_assembly(), room, "alarm_clock", x, y, yaw, z, mode="decor", name="AlarmClock",
                 props={"sa_alt_material": "digits_612", "sa_time": "6:47"})


def circle(cx, cy, z, radius, count):
    return [(cx + radius * math.cos(2 * math.pi * i / count), cy + radius * math.sin(2 * math.pi * i / count), z)
            for i in range(count)]


# ---------------------------------------------------------------------------
# Objetos de cabeceira
# ---------------------------------------------------------------------------
def make_bedside_clutter(ctx, room, x, y, z, yaw, kind):
    """Cabeceira de Laura ('pills': remédio, comprimidos e copo velho) ou de Dan ('book': livro e retrato de Emma)."""
    items = Assembly(f"bedside_{kind}")
    m = items.part(craft.STANDARD, builder_class=small.UvBuilder)
    if kind == "pills":
        small.pill_bottle(m, 0.0, 0.0, 0.0)
        small.tablets(m, 0.045, -0.03, 0.0)
        small.glass_tumbler(m, 0.12, 0.03, 0.0)
        m.panel(0.12, 0.03, 0.0006, 0.085, 0.085, "up_stain_ring", "top")
    else:
        small.book_flat(m, 0.0, 0.0, 0.0, 0.032, 0.15, 0.22, 4, yaw=8)
        small.book_flat(m, 0.01, 0.0, 0.032, 0.022, 0.14, 0.20, 0, yaw=-16)
        small.photo_stand(m, 0.23, 0.0, 0.0, "up_photo_portrait", frame="brass")
    return place(ctx, items, room, "bedside", x, y, yaw, z, mode="decor")
