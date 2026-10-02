"""Hall de entrada: sapateira com os calçados de toda a família, cabideiro com casacos, espelho, porta-guarda-chuva,
a planta que secou, a chave pendurada e a correspondência que passou por baixo da porta.

Os casacos são panos simulados com `craft.drape`, presos por um trecho no alto (a argola do cabide) e soltos
no resto: pendem em dobras, em vez de serem blocos.
"""
import math

from .. import craft, layout
from . import cloth_sala as cloth
from . import furniture_forms as forms
from . import materials, shoes, tex_sala
from . import small_things as things
from .composite import Composite
from .furniture import wall_spot
from .kit import MeshBuilder
from .placement import against_wall, floor_z, place

materials.SPECS.update({
    "mirror_glass": materials.Spec(color=(0.30, 0.32, 0.33), roughness=0.03, metallic=1.0),
    "shoe_leather": materials.Spec(color=(0.07, 0.04, 0.025), roughness=0.4),
    "shoe_leather_tan": materials.Spec(color=(0.30, 0.18, 0.10), roughness=0.4),
    "shoe_fabric": materials.Spec(color=(0.30, 0.30, 0.34), roughness=0.9),
    "boot_rubber_yellow": materials.Spec(color=(0.62, 0.50, 0.05), roughness=0.3),
    "plant_dead": materials.Spec(color=(0.17, 0.12, 0.06), roughness=0.95),
    "plant_soil": materials.Spec(color=(0.05, 0.035, 0.02), roughness=1.0),
    "umbrella_navy": materials.Spec(color=(0.03, 0.04, 0.10), roughness=0.5),
    "umbrella_pink": materials.Spec(color=(0.45, 0.20, 0.30), roughness=0.5),
})
for _name, _tint, _tile in (("coat_wool_dark", (0.06, 0.07, 0.09), 0.3), ("coat_wool_beige", (0.34, 0.28, 0.19), 0.3),
                            ("coat_raincoat", (0.66, 0.52, 0.06), 0.35), ("scarf_wool", (0.36, 0.05, 0.05), 0.2)):
    tex_sala.SURFACES[_name] = tex_sala.Surface("sala_upholstery", _tile, tint=_tint, roughness=0.9, rough_swing=0.1,
                                                specular=0.1, bump=0.9, bump_distance=0.002, sheen=0.3, box=True)
    materials.register_builder(_name, lambda n=_name: tex_sala.build_surface(n, tex_sala.SURFACES[n]))


# ---------------------------------------------------------------------------
# Sapateira
# ---------------------------------------------------------------------------
def make_shoe_rack(ctx, room, wall, along):
    """Sapateira de carvalho com três prateleiras de ripas: sapatos do Dan, sapatilhas da Laura, tênis e galochas da Emma."""
    width, depth, height = 0.62, 0.28, 0.56
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Composite("shoe_rack", wood=forms.WOOD, shoes=forms.SMOOTH)
    wood, shoe_part = asm.wood, asm.shoes
    for side in (-1, 1):
        wood.extrude([(-depth / 2, 0.05), (-depth / 2 + 0.03, 0.0), (-depth / 2 + 0.06, 0.05), (-0.04, 0.05), (-0.03, 0.0),
                      (0.0, 0.05), (depth / 2 - 0.06, 0.05), (depth / 2 - 0.03, 0.0), (depth / 2, 0.05), (depth / 2, height),
                      (-depth / 2, height)], "yz", side * (width / 2 - 0.009) - 0.009, side * (width / 2 - 0.009) + 0.009, "oak_v")
    shelf_zs = (0.07, 0.25, 0.43)
    for shelf_z in shelf_zs:
        for slat in range(5):
            wood.box(0, -depth / 2 + 0.028 + slat * (depth - 0.056) / 4, shelf_z, width - 0.036, 0.042, 0.014, "oak")
    for z in (0.12, 0.30):
        wood.box(0, -depth / 2 + 0.008, z, width - 0.036, 0.012, 0.03, "oak")
    wood.box(0, depth / 2 - 0.008, height - 0.03, width - 0.036, 0.014, 0.03, "oak")
    top = 0.014
    shoes.shoe(shoe_part, -0.215, -0.14, shelf_zs[0] + top, 1.0, "shoe_leather", kind="oxford", yaw=4, mirror=1)
    shoes.shoe(shoe_part, -0.10, -0.14, shelf_zs[0] + top, 1.0, "shoe_leather", kind="oxford", yaw=-6, mirror=-1)
    shoes.shoe(shoe_part, 0.10, -0.12, shelf_zs[0] + top, 0.9, "shoe_leather_tan", kind="flat", yaw=20, mirror=1)
    shoes.shoe(shoe_part, 0.215, -0.11, shelf_zs[0] + top, 0.9, "shoe_leather_tan", kind="flat", yaw=-8, mirror=-1)
    shoes.shoe(shoe_part, -0.2, -0.1, shelf_zs[1] + top, 0.62, "shoe_fabric", kind="sneaker", yaw=-4, mirror=1)
    shoes.shoe(shoe_part, -0.12, -0.1, shelf_zs[1] + top, 0.62, "shoe_fabric", kind="sneaker", yaw=8, mirror=-1)
    shoes.rain_boot(shoe_part, 0.1, -0.1, shelf_zs[1] + top, 0.62, "boot_rubber_yellow", yaw=-3)
    shoes.rain_boot(shoe_part, 0.2, -0.1, shelf_zs[1] + top, 0.62, "boot_rubber_yellow", yaw=6)
    shoes.shoe(shoe_part, -0.14, -0.14, shelf_zs[2] + top, 1.0, "shoe_leather", kind="sneaker", yaw=-3, mirror=1)
    return place(ctx, asm, room, "shoe_rack", x, y, yaw)


# ---------------------------------------------------------------------------
# Cabideiro e casacos
# ---------------------------------------------------------------------------
HOOK_ARM = 0.19
UPPER_HOOK_Z, LOWER_HOOK_Z = 1.84, 1.28


def _hook_positions():
    """(ângulo em graus, altura) de cada gancho."""
    return [(45, UPPER_HOOK_Z), (135, UPPER_HOOK_Z), (225, UPPER_HOOK_Z), (315, UPPER_HOOK_Z), (180, LOWER_HOOK_Z),
            (0, LOWER_HOOK_Z)]


def _rack_frame(wood, metal):
    wood.lathe([(0.0, 0.0), (0.22, 0.0), (0.23, 0.012), (0.2, 0.03), (0.12, 0.05), (0.05, 0.075), (0.026, 0.1), (0.0, 0.1)],
               0, 0, 0, "walnut", seg=forms.seg(24), smooth=True)
    wood.lathe([(0.026, 0.1), (0.030, 0.14), (0.022, 0.18), (0.022, 1.7), (0.03, 1.74), (0.024, 1.78), (0.022, 1.82),
                (0.034, 1.86), (0.03, 1.9), (0.012, 1.93), (0.0, 1.93)], 0, 0, 0, "walnut_v", seg=forms.seg(16), smooth=True)
    for angle, z in _hook_positions():
        direction = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
        base = (direction[0] * 0.02, direction[1] * 0.02, z)
        tip = (direction[0] * HOOK_ARM, direction[1] * HOOK_ARM, z + 0.014)
        metal.tube(base, tip, 0.0095, "brass_aged", seg=8, r_end=0.0075, smooth=True)
        metal.sphere(tip[0], tip[1], tip[2] + 0.01, 0.013, "brass_aged", seg=10, rings=6)


def _hanger(wood, metal, angle, bar_z, span):
    """Cabide de madeira pendurado no gancho do `angle`: barra dos ombros na tangente e gancho de arame no braço."""
    direction = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
    tangent = (-direction[1], direction[0])
    reach = HOOK_ARM * 0.92
    center = (direction[0] * reach, direction[1] * reach)
    left = (center[0] - tangent[0] * span / 2, center[1] - tangent[1] * span / 2, bar_z)
    right = (center[0] + tangent[0] * span / 2, center[1] + tangent[1] * span / 2, bar_z)
    peak = (center[0], center[1], bar_z + 0.035)
    wood.tube(left, peak, 0.008, "walnut", seg=6, smooth=True)
    wood.tube(peak, right, 0.008, "walnut", seg=6, smooth=True)
    metal.tube(peak, (center[0], center[1], bar_z + 0.085), 0.0016, "chrome", seg=4)
    return left, peak, right


def _hang(asm, angle, bar_z, span, width, drop, material, *, thickness=0.012, hanger=True):
    """Casaco no cabide: o pano cai sobre a barra dos ombros e pende dos dois lados, preso em cima para não escorregar."""
    direction = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
    reach = HOOK_ARM * 0.92
    colliders = cloth.collider_builder("rack_colliders")
    if hanger:
        left, peak, right = _hanger(asm.wood, asm.metal, angle, bar_z, span)
        colliders.tube(left, peak, 0.012, "walnut", seg=6)
        colliders.tube(peak, right, 0.012, "walnut", seg=6)
    else:
        base = (direction[0] * 0.02, direction[1] * 0.02, bar_z)
        tip = (direction[0] * HOOK_ARM, direction[1] * HOOK_ARM, bar_z + 0.014)
        colliders.tube(base, tip, 0.011, "walnut", seg=6)
    colliders.cylinder(0, 0, 0, 0.022, 1.9, "walnut", seg=10)
    top = bar_z + (0.04 if hanger else 0.03)
    center = (direction[0] * reach, direction[1] * reach, top)
    tangent = (-direction[1], direction[0])

    def pinned(x, y, z):
        along = (x - center[0]) * tangent[0] + (y - center[1]) * tangent[1]
        across = (x - center[0]) * direction[0] + (y - center[1]) * direction[1]
        return abs(across) < 0.035 and abs(along) < (span / 2 if hanger else width / 2)

    mesh = cloth.drape_over(colliders, width=width, depth=drop * 2, center=center, yaw=math.radians(angle + 90),
                            material=material, cell=0.05, frames=70, mass=0.5, stiffness=30.0, bending=10.0,
                            thickness=thickness, pin=pinned, ripple=None)
    asm.add_mesh(mesh)


def make_coat_rack(ctx, room, x, y):
    """Cabideiro de pé: casaco do Dan, o trench que a Laura esqueceu, um cachecol e a capa de chuva amarela da Emma."""
    asm = Composite("coat_rack", wood=forms.SMOOTH, metal=forms.SMOOTH)
    _rack_frame(asm.wood, asm.metal)
    _hang(asm, 45, UPPER_HOOK_Z - 0.115, 0.44, 0.62, 0.62, "coat_wool_dark")
    _hang(asm, 225, UPPER_HOOK_Z - 0.115, 0.42, 0.58, 0.72, "coat_wool_beige")
    _hang(asm, 135, UPPER_HOOK_Z, 0.0, 0.14, 0.42, "scarf_wool", thickness=0.01, hanger=False)
    _hang(asm, 180, LOWER_HOOK_Z - 0.10, 0.30, 0.38, 0.30, "coat_raincoat", thickness=0.008)
    return place(ctx, asm, room, "coat_rack", x, y, 0.0, collision=[(-0.25, -0.25, 0.0, 0.25, 0.25, 1.95)])


# ---------------------------------------------------------------------------
# Porta-guarda-chuva
# ---------------------------------------------------------------------------
def _folded_umbrella(m, x, y, base_z, lean, mat, length=0.85, handle_mat="shoe_leather"):
    """Guarda-chuva fechado em pé, inclinado: haste, pano enrolado em pregas e cabo em gancho."""
    top = (x + math.tan(math.radians(lean)) * length, y, base_z + length)
    m.tube((x, y, base_z), top, 0.005, "steel_dark", seg=6)
    pleats = 10
    rings = [[(x + (top[0] - x) * 0.30, y, base_z + length * 0.30)]]
    for fraction, radius in ((0.40, 0.020), (0.62, 0.034), (0.80, 0.026), (0.95, 0.008)):
        px, pz = x + (top[0] - x) * fraction, base_z + length * fraction
        rings.append([(px + (radius * (1 + 0.25 * (-1) ** i)) * math.cos(2 * math.pi * i / pleats),
                       y + (radius * (1 + 0.25 * (-1) ** i)) * math.sin(2 * math.pi * i / pleats), pz) for i in range(pleats)])
    m.loft(rings, mat, False, False, True, orient=False)
    m.tube(top, (top[0] + 0.035, y, top[2] + 0.03), 0.011, handle_mat, seg=8, smooth=True)
    m.tube((top[0] + 0.035, y, top[2] + 0.03), (top[0] + 0.07, y, top[2] - 0.01), 0.011, handle_mat, seg=8, smooth=True)


def make_umbrella_stand(ctx, room, x, y):
    """Porta-guarda-chuva de cerâmica com dois guarda-chuvas de adulto e o rosa da Emma."""
    asm = Composite("umbrella_stand", pot=forms.SMOOTH, umbrellas=forms.SMOOTH)
    asm.pot.lathe([(0.0, 0.0), (0.085, 0.0), (0.095, 0.02), (0.10, 0.2), (0.115, 0.4), (0.12, 0.44), (0.105, 0.445),
                   (0.098, 0.40), (0.088, 0.04), (0.0, 0.03)], 0, 0, 0, "porcelain_old", seg=forms.seg(20), smooth=True)
    _folded_umbrella(asm.umbrellas, -0.03, 0.02, 0.05, -3, "shoe_leather", 0.88)
    _folded_umbrella(asm.umbrellas, 0.035, -0.03, 0.05, 5, "umbrella_navy", 0.84)
    _folded_umbrella(asm.umbrellas, 0.01, 0.045, 0.05, 2, "umbrella_pink", 0.6, "umbrella_pink")
    return place(ctx, asm, room, "umbrella_stand", x, y, 0.0)


# ---------------------------------------------------------------------------
# Planta seca
# ---------------------------------------------------------------------------
def make_dead_plant(ctx, room, x, y, z, *, height=0.5):
    """Vaso de cerâmica com uma planta que secou: terra rachada, hastes arqueadas para o lado e folhas murchas e enroladas."""
    rng = ctx.rng
    asm = Composite("dead_plant", pot=forms.SMOOTH, leaves=craft.RAW)
    pot, leaves = asm.pot, asm.leaves
    pot.lathe([(0.0, 0.0), (0.075, 0.0), (0.095, 0.03), (0.11, 0.16), (0.125, 0.175), (0.118, 0.18), (0.10, 0.172),
               (0.0, 0.125)], 0, 0, 0, "porcelain_old", seg=forms.seg(20), smooth=True)
    pot.cylinder(0, 0, 0.12, 0.103, 0.04, "plant_soil", seg=forms.seg(16))
    for index in range(8):
        angle = rng.uniform(0, 2 * math.pi)
        reach = rng.uniform(0.09, 0.17)
        peak = 0.16 + height * rng.uniform(0.5, 0.85)
        mid = (reach * 0.35 * math.cos(angle), reach * 0.35 * math.sin(angle), 0.16 + (peak - 0.16) * 0.8)
        top = (reach * math.cos(angle), reach * math.sin(angle), peak - rng.uniform(0.04, 0.12))
        leaves.tube((0, 0, 0.15), mid, 0.0035, "plant_dead", seg=5)
        leaves.tube(mid, top, 0.003, "plant_dead", seg=5, r_end=0.002)
        for leaf in range(4):
            u = rng.uniform(0.2, 1.0)
            anchor = tuple(mid[i] + (top[i] - mid[i]) * u for i in range(3))
            outline = [(0.0, 0.0), (0.012, 0.025), (0.008, 0.055), (0.0, 0.08), (-0.008, 0.055), (-0.012, 0.025)]
            with leaves.at(*anchor, rz=math.degrees(angle) + rng.uniform(-70, 70) + 90, rx=rng.uniform(100, 150)):
                leaves.extrude(outline, "xy", 0.0, 0.0012, "plant_dead")
    return place(ctx, asm, room, "dead_plant", x, y, 0.0, z, mode="decor")


# ---------------------------------------------------------------------------
# Espelho, chaveiro, correspondência
# ---------------------------------------------------------------------------
def make_hall_mirror(ctx, room, wall, along, z, width, height):
    """Espelho de parede com moldura dourada envelhecida de perfil entalhado; vidro escuro e levemente manchado."""
    x, y, yaw = wall_spot(room, wall, along)
    asm = Composite("hall_mirror", frame=forms.SMOOTH, glass=craft.RAW)
    depth = 0.035
    profile = [(0.0, 0.004), (0.0, depth * 0.55), (0.012, depth * 0.7), (0.022, depth), (0.04, depth), (0.05, depth * 0.78),
               (0.065, depth * 0.6), (0.065, 0.004)]
    forms.mitred_frame(asm.frame, 0, 0.0, 0, width, height, profile, "gilt")
    asm.glass.panel(0, 0.01, 0, width + 0.004, height + 0.004, "mirror_glass", "front")
    for corner_x in (-1, 1):
        for corner_z in (-1, 1):
            asm.frame.sphere(corner_x * (width / 2 + 0.05), depth * 0.9, corner_z * (height / 2 + 0.05), 0.012, "gilt",
                             seg=8, rings=5)
    return place(ctx, asm, room, "mirror", x, y, yaw, floor_z(room) + z, mode="wall", name=f"mirror_{room}")


def make_key_rack(ctx, room, wall, along, z):
    """Chaveiro de parede de madeira com quatro ganchos: chave da casa, as de Laura (levou só uma) e o chaveiro da Emma."""
    x, y, yaw = wall_spot(room, wall, along)
    asm = Composite("key_rack", wood=forms.WOOD, metal=forms.SMOOTH)
    asm.wood.box(0, 0.011, -0.04, 0.34, 0.022, 0.08, "walnut")
    for index in range(4):
        hook_x = (index - 1.5) * 0.075
        asm.metal.tube((hook_x, 0.022, 0.0), (hook_x, 0.05, 0.0), 0.0035, "brass_aged", seg=6)
        asm.metal.sphere(hook_x, 0.052, 0.0, 0.006, "brass_aged", seg=6, rings=4)
    for hook_x, tone in ((-0.1125, "brass_aged"), (0.1125, "chrome")):
        asm.metal.torus(hook_x, 0.052, -0.012, 0.011, 0.0015, "chrome", seg=12, seg_minor=4, rx=90)
        asm.metal.box(hook_x, 0.052, -0.05, 0.012, 0.002, 0.052, tone)
    asm.metal.sphere(0.0375, 0.052, -0.03, 0.02, "plush_pink", seg=8, rings=5)
    return place(ctx, asm, room, "key_rack", x, y, yaw, floor_z(room) + z, mode="wall", name=f"key_rack_{room}")


def make_floor_mail(ctx, room, x, y):
    """Cartas e um folheto que passaram por baixo da porta e ficaram no chão: ninguém as recolhe há semanas."""
    m = MeshBuilder("floor_mail")
    m.finish = craft.RAW
    things.envelope_pile(m, 0.0, 0.0, 0.0, ctx.rng, count=5)
    with m.at(0.18, -0.05, 0.0, rz=35):
        m.box(0, 0, 0, 0.21, 0.27, 0.0015, "paper_white", skip=("top",))
        m.panel(0, 0, 0.0016, 0.21, 0.27, "sheet_b", "top")
    return place(ctx, m, room, "mail", x, y, ctx.rng.uniform(0, 6.28), mode="flat", name=f"mail_{room}")


def stair_photo_slots(count=7):
    """Posições (y, altura acima do piso do térreo) dos quadros seguindo a subida da escada."""
    stairs = layout.STAIRS
    span = stairs.y1 - stairs.y0 - 0.9
    slots = []
    for i in range(count):
        y = stairs.y0 + 0.5 + span * i / (count - 1)
        slots.append((y, layout.stairs_height(stairs.x0 + 0.1, y) + 1.55))
    return slots
