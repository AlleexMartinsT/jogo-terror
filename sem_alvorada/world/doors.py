"""Portas: folha de almofadas com rebaixos, ferragens de latão, batente com guarnição em esquadria e soleira.

Contrato (docs/CONTRACT.md, seção 4): Empty pivô `Door_<id>` na dobradiça, com a folha `DoorLeaf_<id>`
modelada em +X local e as ferragens em `DoorHandle_<id>`. O batente `DoorFrame_<id>` fica no mundo.
O desenho da folha (onde ficam travessas e almofadas) vem de `doorspec`, o mesmo que a textura lê.

A lingueta da maçaneta é um objeto à parte, `DoorBolt_<id>` (filha do pivô, origem na ponta de dentro da
fechadura, eixo ao longo de +X). O engine a recolhe ao girar a maçaneta e a solta ao fechar. As maçanetas
são peças de revolução: girá-las em torno do próprio eixo não muda nada na imagem, por isso o que se vê
da "maçaneta girando" é a lingueta saindo da borda da folha.
"""
import math
from dataclasses import dataclass

from mathutils import Vector

from .. import conventions as C
from .. import layout
from . import doorspec, moldings
from .meshkit import attach, empty
from .modelkit import FINE, PROFILED, ModelBuilder, build_combined, detail
from .wallgeom import normal, wall_box, wall_point

CLEARANCE_BOTTOM = 0.014      # folga sob a folha (a soleira tem 1,2 cm)
CLEARANCE_TOP = 0.005
THRESHOLD_HEIGHT = 0.012
HALF = doorspec.LEAF_THICKNESS / 2
HINGE_HEIGHT = 0.09
HINGE_ZS = (0.325, 1.07, 1.82)            # 28 cm do piso e 18 cm do topo, como manda a norma
DEADBOLT_HEIGHT = 1.10
LATCH_PLATE_OFFSET = 0.0015     # a face da chapa da fechadura, além da borda livre da folha
BOLT_LENGTH = 0.012

# Relevo de uma almofada, de fora para dentro: (recuo lateral, profundidade abaixo da face), em metros.
# Os dois primeiros pontos são o perfil esculpido na travessa (sticking); depois o fundo do rasgo e o
# chanfro da almofada elevada, que termina 4,5 mm abaixo da face.
PANEL_STEPS = ((0.003, 0.002), (0.007, 0.006), (0.010, 0.009), (0.014, 0.009), (0.036, 0.0045))
LITE_STEPS = ((0.004, 0.003), (0.008, 0.008))
MUNTIN = 0.012


@dataclass(frozen=True)
class DoorStyle:
    kind: str = "six_panel"
    material: str = "door_paint"
    keyed_toward: tuple = ()              # direção (x, y) do lado da chave; vazio = só maçaneta
    threshold: str = "wood_dark"
    kick_plate: bool = False
    peephole: bool = False
    mail_slot: bool = False


DEFAULT_STYLE = DoorStyle()
STYLES = {
    "front": DoorStyle("glazed", "door_front", (0.0, -1.0), "steel_hardware", peephole=True, mail_slot=True),
    "back": DoorStyle("screen", "door_back", (0.0, 1.0), "steel_hardware"),
    "garage_door": DoorStyle("flush", "door_steel", (-1.0, 0.0), "steel_hardware", kick_plate=True),
    "living_hall": DoorStyle(material="door_paint"),
    "den_hall": DoorStyle(material="door_wood"),
    "den_living": DoorStyle(material="door_wood"),
    "kitchen_hall": DoorStyle(material="door_wood"),
    "study_hall": DoorStyle(material="door_wood"),
    "kids_hall": DoorStyle(material="door_kids"),
    "master_hall": DoorStyle(material="door_paint_b"),
    "kids_master": DoorStyle(material="door_paint_b"),
    "bath_study": DoorStyle(material="door_paint_b"),
}


def build(ctx, op, piece):
    style = STYLES.get(op.id, DEFAULT_STYLE)
    placement = layout.door_transform(op)
    _build_frame(ctx, op, piece, style)
    pivot = empty(ctx, f"{C.N_DOOR}{op.id}", C.COL_WORLD, placement["hinge"], placement["closed_yaw"])
    pivot[C.P_ID] = op.id
    pivot[C.P_INTERACT] = "door"
    pivot[C.P_DOOR_CLOSED] = placement["closed_yaw"]
    pivot[C.P_DOOR_OPEN] = placement["open_yaw"]
    pivot[C.P_LOCK] = op.lock
    width, height = op.width - 0.02, op.height - CLEARANCE_TOP
    spec = doorspec.leaf_spec(style.kind, width, height)
    leaf = _leaf(f"DoorLeaf_{op.id}", spec, style).build(ctx, C.COL_WORLD)
    attach(leaf, pivot)
    knob = (width - doorspec.KNOB_INSET, 0.0, doorspec.KNOB_HEIGHT)
    hardware = _hardware(ctx, f"DoorHandle_{op.id}", spec, style, _key_side(placement, style)).build(
        ctx, C.COL_WORLD, knob)
    attach(hardware, pivot, knob)
    bolt_origin = (width + LATCH_PLATE_OFFSET, 0.0, doorspec.KNOB_HEIGHT)
    bolt = _bolt(f"DoorBolt_{op.id}", bolt_origin, detail(ctx, 12)).build(ctx, C.COL_WORLD, bolt_origin)
    attach(bolt, pivot, bolt_origin)
    return pivot


def _key_side(placement, style):
    """+1 se o lado da chave é a face +Y local da folha, -1 se é a -Y, 0 sem fechadura de chave."""
    if not style.keyed_toward:
        return 0
    yaw = placement["closed_yaw"]
    local_y = (-math.sin(yaw), math.cos(yaw))
    return 1 if local_y[0] * style.keyed_toward[0] + local_y[1] * style.keyed_toward[1] > 0 else -1


# --------------------------------------------------------------------------
# Folha
# --------------------------------------------------------------------------
def _oriented(builder, points, toward, material):
    """Polígono voltado para `toward`: inverte a ordem se a normal calculada aponta para o outro lado."""
    a, b, c = (Vector(p) for p in points[:3])
    if (b - a).cross(c - a).dot(Vector(toward)) < 0:
        points = points[::-1]
    builder.poly(points, material)


def _plane(builder, y, x0, z0, x1, z1, facing, material):
    _oriented(builder, [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], (0.0, facing, 0.0), material)


def _band(builder, outer, inner, facing, material):
    """Quatro faixas inclinadas entre dois retângulos concêntricos a profundidades diferentes."""
    (ra, ya), (rb, yb) = outer, inner
    corners_a = [(ra[0], ra[1]), (ra[2], ra[1]), (ra[2], ra[3]), (ra[0], ra[3])]
    corners_b = [(rb[0], rb[1]), (rb[2], rb[1]), (rb[2], rb[3]), (rb[0], rb[3])]
    for i in range(4):
        j = (i + 1) % 4
        quad = [(corners_a[i][0], ya, corners_a[i][1]), (corners_a[j][0], ya, corners_a[j][1]),
                (corners_b[j][0], yb, corners_b[j][1]), (corners_b[i][0], yb, corners_b[i][1])]
        _oriented(builder, quad, (0.0, facing, 0.0), material)


def _inset(rect, amount):
    return (rect[0] + amount, rect[1] + amount, rect[2] - amount, rect[3] - amount)


def _relief(builder, rect, facing, steps, material):
    """Desce da face da folha até o fundo do vão por anéis concêntricos; devolve o retângulo e o plano do fundo."""
    previous = (rect, facing * HALF)
    for inset, depth in steps:
        current = (_inset(rect, inset), facing * (HALF - depth))
        _band(builder, previous, current, facing, material)
        previous = current
    return previous


def _leaf(name, spec, style):
    builder = ModelBuilder(name, PROFILED)
    z_bottom = CLEARANCE_BOTTOM
    for facing in (1, -1):
        _leaf_face(builder, spec, style.material, facing, z_bottom)
    _leaf_edges(builder, spec, style.material, z_bottom)
    for field in spec.fields:
        if field.kind == "panel":
            for facing in (1, -1):
                rect, y = _relief(builder, field.rect, facing, PANEL_STEPS, style.material)
                _plane(builder, y, *rect, facing, style.material)
        else:
            _glazing(builder, field, style.material)
    return builder


def _leaf_face(builder, spec, material, facing, z_bottom):
    """A face plana da folha, em células ao redor dos vãos."""
    xs = sorted({0.0, spec.width, *(v for f in spec.fields for v in (f.x0, f.x1))})
    zs = sorted({z_bottom, spec.height, *(v for f in spec.fields for v in (f.z0, f.z1))})
    for x0, x1 in zip(xs, xs[1:]):
        for z0, z1 in zip(zs, zs[1:]):
            mx, mz = (x0 + x1) / 2, (z0 + z1) / 2
            if not any(f.x0 < mx < f.x1 and f.z0 < mz < f.z1 for f in spec.fields):
                _plane(builder, facing * HALF, x0, z0, x1, z1, facing, material)


def _leaf_edges(builder, spec, material, z_bottom):
    w, h = spec.width, spec.height
    for x, toward in ((0.0, (-1, 0, 0)), (w, (1, 0, 0))):
        _oriented(builder, [(x, -HALF, z_bottom), (x, HALF, z_bottom), (x, HALF, h), (x, -HALF, h)], toward, material)
    for z, toward in ((z_bottom, (0, 0, -1)), (h, (0, 0, 1))):
        _oriented(builder, [(0.0, -HALF, z), (w, -HALF, z), (w, HALF, z), (0.0, HALF, z)], toward, material)


def _glazing(builder, field, material):
    """Vão passante com caixilho: chanfro nas duas faces, paredes do rasgo, muntins e o vidro (ou a tela)."""
    glass = "window_glass" if field.kind == "glass" else "screen_mesh"
    for facing in (1, -1):
        rect, y = _relief(builder, field.rect, facing, LITE_STEPS, material)
    rect = _inset(field.rect, LITE_STEPS[-1][0])
    x0, z0, x1, z1 = rect
    depth = HALF - LITE_STEPS[-1][1]
    for points, toward in (([(x0, -depth, z0), (x1, -depth, z0), (x1, depth, z0), (x0, depth, z0)], (0, 0, 1)),
                           ([(x0, -depth, z1), (x1, -depth, z1), (x1, depth, z1), (x0, depth, z1)], (0, 0, -1)),
                           ([(x0, -depth, z0), (x0, depth, z0), (x0, depth, z1), (x0, -depth, z1)], (1, 0, 0)),
                           ([(x1, -depth, z0), (x1, depth, z0), (x1, depth, z1), (x1, -depth, z1)], (-1, 0, 0))):
        _oriented(builder, points, toward, material)
    builder.poly([(x0, 0.0, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x0, 0.0, z1)], glass)
    if field.kind == "glass":
        columns, rows = 2, 2
        for i in range(1, columns):
            x = x0 + (x1 - x0) * i / columns
            builder.box(x - MUNTIN / 2, -0.009, z0, x + MUNTIN / 2, 0.009, z1, material)
        for j in range(1, rows):
            z = z0 + (z1 - z0) * j / rows
            builder.box(x0, -0.009, z - MUNTIN / 2, x1, 0.009, z + MUNTIN / 2, material)


# --------------------------------------------------------------------------
# Ferragens (origem do objeto na maçaneta; coordenadas da folha)
# --------------------------------------------------------------------------
KNOB_PROFILE = [(0.030, 0.000), (0.0315, 0.002), (0.029, 0.005), (0.0235, 0.0065), (0.0165, 0.0075),
                (0.0105, 0.009), (0.0085, 0.012), (0.0080, 0.030), (0.012, 0.036), (0.021, 0.042),
                (0.026, 0.052), (0.0262, 0.060), (0.0235, 0.070), (0.014, 0.0765), (0.0, 0.0785)]
CYLINDER_PROFILE = [(0.0262, 0.0), (0.0275, 0.002), (0.0255, 0.0045), (0.0180, 0.0055), (0.0165, 0.014),
                    (0.0, 0.0155)]
THUMBTURN_PROFILE = [(0.027, 0.0), (0.0285, 0.002), (0.026, 0.0045), (0.012, 0.0055), (0.0, 0.0056)]


def _hinge_profile():
    """Cano da dobradiça: três nós de 3 cm com um filete entre eles e pontas de pino arredondadas."""
    profile = [(0.0, 0.0), (0.0046, 0.0)]
    for k in range(3):
        z0, z1 = 0.03 * k, 0.03 * (k + 1)
        profile += [(0.0055, z0 + 0.001), (0.0055, z1 - 0.001), (0.0046, z1)]
    return profile + [(0.0046, HINGE_HEIGHT), (0.0, HINGE_HEIGHT)]


HINGE_PROFILE = _hinge_profile()


def _hardware(ctx, name, spec, style, key_side):
    """Ferragens: peças torneadas (sem chanfro, o perfil já é arredondado) e chapas planas (chanfro de 1 mm)."""
    turned, plates = ModelBuilder("_hardware_turned", PROFILED), ModelBuilder("_hardware_plates", FINE)
    sides = detail(ctx, 12)
    knob_x, knob_z = spec.width - doorspec.KNOB_INSET, doorspec.KNOB_HEIGHT
    for side in (1, -1):
        with turned.at(knob_x, side * HALF, knob_z, rx=-90 * side):
            turned.lathe(KNOB_PROFILE, "brass_worn", sides)
    _latch(plates, spec.width, knob_z)
    if key_side:
        for side in (1, -1):
            with turned.at(knob_x, side * HALF, DEADBOLT_HEIGHT, rx=-90 * side):
                turned.lathe(CYLINDER_PROFILE if side == key_side else THUMBTURN_PROFILE, "brass_worn", sides)
                if side != key_side:
                    plates.box(knob_x - 0.014, side * HALF + 0.0056, DEADBOLT_HEIGHT - 0.005, knob_x + 0.014,
                               side * HALF + 0.016, DEADBOLT_HEIGHT + 0.005, "brass_worn")
        _latch(plates, spec.width, DEADBOLT_HEIGHT)
        _bolt_shape(turned, spec.width, DEADBOLT_HEIGHT, sides, 0.022)
    for z in HINGE_ZS:
        _hinge(turned, plates, z, max(6, sides // 2))
    if style.kick_plate:
        for side in (1, -1):
            plates.box(0.03, side * HALF, CLEARANCE_BOTTOM + 0.01, spec.width - 0.03, side * (HALF + 0.002),
                       CLEARANCE_BOTTOM + 0.27, "steel_hardware")
    if style.peephole:
        _peephole(turned, spec.width / 2, 1.565, sides)
    if style.kind == "flush":
        _fire_door_fittings(turned, plates, spec.width, -key_side or 1, max(6, sides // 2))
    if style.mail_slot:
        _mail_slot(plates, spec.width * 0.42, doorspec.KNOB_HEIGHT)
    return HardwareSet(name, turned, plates)


class HardwareSet:
    """Dois construtores de acabamentos diferentes que viram um único objeto."""

    def __init__(self, name, *builders):
        self.builders = builders
        self.name = name

    def build(self, ctx, collection, origin):
        return build_combined(ctx, collection, self.name, self.builders, origin)


def _latch(plates, width, z):
    """Chapa da fechadura na borda livre."""
    plates.box(width - 0.0005, -0.011, z - 0.055, width + LATCH_PLATE_OFFSET, 0.011, z + 0.055, "brass_worn")


def _bolt_shape(builder, width, z, sides, length=BOLT_LENGTH):
    """Lingueta (ou ferrolho): cilindro de ponta arredondada que sai da chapa ao longo de +X."""
    with builder.at(width + LATCH_PLATE_OFFSET, 0.0, z, ry=90):
        builder.lathe([(0.0065, 0.0), (0.0065, length), (0.0045, length + 0.003), (0.0, length + 0.0035)],
                      "brass_worn", max(6, sides // 2))


def _bolt(name, origin, sides):
    """A lingueta da maçaneta como objeto próprio, para o engine recolhê-la quando a maçaneta gira."""
    builder = ModelBuilder(name, PROFILED)
    _bolt_shape(builder, origin[0] - LATCH_PLATE_OFFSET, origin[2], sides)
    return builder


def _hinge(turned, plates, z, sides):
    """Dobradiça de espiga: placa na borda da folha e cano de nós sobre o eixo do pivô."""
    plates.box(-0.0012, -0.0175, z - HINGE_HEIGHT / 2, 0.0, 0.0175, z + HINGE_HEIGHT / 2, "brass_worn")
    with turned.at(0.0, 0.0, z - HINGE_HEIGHT / 2):
        turned.lathe(HINGE_PROFILE, "brass_worn", sides)


def _fire_door_fittings(turned, plates, width, side, sides):
    """Porta corta-fogo: etiqueta de classe na borda do alto e fechamola hidráulica com braço articulado."""
    face = side * HALF
    plates.box(width - 0.11, face, 1.80, width - 0.04, face + side * 0.0012, 1.84, "steel_hardware")
    z = 2.0
    plates.box(0.16, face, z - 0.03, 0.36, face + side * 0.05, z + 0.03, "painted_metal")
    turned.tube((0.36, face + side * 0.03, z), (0.52, face + side * 0.075, z - 0.012), 0.0085, "steel_hardware", sides)
    turned.tube((0.52, face + side * 0.075, z - 0.012), (0.70, face + side * 0.014, z - 0.02), 0.0085,
                "steel_hardware", sides)
    plates.box(0.68, face, z - 0.04, 0.74, face + side * 0.016, z + 0.0, "steel_hardware")


def _mail_slot(plates, x, z):
    """Fresta de correspondência: placa de latão com a abertura escura e a aba (por fora) levemente aberta."""
    for side in (1, -1):
        plates.box(x - 0.15, side * HALF, z - 0.03, x + 0.15, side * (HALF + 0.003), z + 0.03, "brass_worn")
        plates.box(x - 0.115, side * (HALF + 0.003), z - 0.0085, x + 0.115, side * (HALF + 0.0034), z + 0.0085,
                   "iron_black")
    plates.box(x - 0.125, HALF + 0.0034, z + 0.0085, x + 0.125, HALF + 0.0074, z + 0.0185, "brass_worn")


def _peephole(builder, x, z, sides):
    for side in (1, -1):
        with builder.at(x, side * HALF, z, rx=-90 * side):
            builder.lathe([(0.011, 0.0), (0.0115, 0.002), (0.008, 0.004), (0.0045, 0.0045), (0.0, 0.0046)],
                          "brass_worn", max(8, sides))


# --------------------------------------------------------------------------
# Batente: guarnição, batentes de fechamento, soleira e chapa de contra-fechadura
# --------------------------------------------------------------------------
def _build_frame(ctx, op, piece, style):
    half = piece.thickness / 2
    floor = layout.LEVEL_Z[op.level]
    molded, plain = ModelBuilder(f"_frame_molded_{op.id}", PROFILED), ModelBuilder(f"_frame_plain_{op.id}", FINE)
    moldings.casing(molded, op, half, floor, floor + op.height, "trim_white")
    _threshold(molded, op, half, floor, style.threshold)
    _stops(plain, op, floor)
    _strike_plates(plain, op, floor, style)
    return build_combined(ctx, C.COL_WORLD, f"DoorFrame_{op.id}", [molded, plain])


def _threshold(builder, op, half, floor, material):
    """Soleira com chanfros dos dois lados, atravessando a espessura da parede."""
    profile = [(-half, 0.0), (half, 0.0), (half, 0.006), (half - 0.014, THRESHOLD_HEIGHT),
               (-half + 0.014, THRESHOLD_HEIGHT), (-half, 0.006)]
    start = wall_point(op, op.a, op.pos, floor)
    end = wall_point(op, op.b, op.pos, floor)
    builder.sweep(profile, [start, end], [normal(op)], (0.0, 0.0, 1.0), material)


def _stops(builder, op, floor):
    """Batentes de fechamento: tiras finas no lado para o qual a porta NÃO abre, contornando a folha."""
    n0, n1 = sorted((op.pos - op.swing * HALF, op.pos - op.swing * (HALF + 0.012)))
    top = floor + op.height
    reach = 0.035
    wall_box(builder, op, op.a, op.a + reach, n0, n1, floor + THRESHOLD_HEIGHT, top, "trim_white")
    wall_box(builder, op, op.b - reach, op.b, n0, n1, floor + THRESHOLD_HEIGHT, top, "trim_white")
    wall_box(builder, op, op.a + reach, op.b - reach, n0, n1, top - reach, top, "trim_white")


def _strike_plates(builder, op, floor, style):
    """Contra-fechadura de latão na jamba do lado da fechadura, com o rasgo escuro da lingueta."""
    latch_u = op.b if op.hinge == "a" else op.a
    inward = -1 if op.hinge == "a" else 1       # sentido, ao longo da parede, de dentro do vão
    heights = [doorspec.KNOB_HEIGHT] + ([DEADBOLT_HEIGHT] if style.keyed_toward else [])
    for z in heights:
        u0, u1 = sorted((latch_u, latch_u + inward * 0.0016))
        wall_box(builder, op, u0, u1, op.pos - 0.013, op.pos + 0.013, floor + z - 0.06, floor + z + 0.06, "brass_worn")
        u0, u1 = sorted((latch_u + inward * 0.0016, latch_u + inward * 0.0019))
        wall_box(builder, op, u0, u1, op.pos - 0.008, op.pos + 0.008, floor + z - 0.02, floor + z + 0.02, "iron_black")
