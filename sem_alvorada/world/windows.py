"""Janelas de guilhotina (duas folhas), com caixilhos, vidros sujos, travas, peitoril e avental.

Cada janela é um objeto `Window_<id>` com origem no centro do vão, `sa_interact = 'look'`. Janelas largas
viram duas ou mais unidades lado a lado (montante no meio): uma guilhotina de 2 m nunca existiu. As
cortinas e persianas são objetos filhos (`dressings`); as venezianas externas ficam na mesma malha.

Medidas de referência: caixilho de 4,5 cm, travessa de encontro de 4 cm, bastão de 1,6 cm, peitoril (stool)
de 2,8 cm de espessura projetando 5,5 cm além da guarnição.
"""
import math
from dataclasses import dataclass

from .. import conventions as C
from .. import layout
from . import moldings
from .meshkit import attach
from .modelkit import PROFILED, ModelBuilder, build_combined, detail
from .wallgeom import inward_sign, normal, wall_box, wall_point

LINER = 0.028                 # forro da jamba (jamb liner) dentro do vão
STILE = 0.046
RAIL = 0.044
MEETING = 0.040
SASH_DEPTH = 0.034
MUNTIN_W = 0.017
MUNTIN_D = 0.022
UNIT_WIDTH = 1.05             # largura máxima de uma unidade de guilhotina
STOOL_THICK = 0.028
SHUTTER_WIDTH = 0.34
SHUTTER_WALL_Y = 0.0          # venezianas nas janelas largas do térreo voltadas para a rua


@dataclass(frozen=True)
class WindowStyle:
    """O que cobre a janela: `none`, `curtain_open`, `curtain_closed` ou `blinds`."""
    covering: str = "none"
    length: str = "long"          # 'long' (até o piso) ou 'short' (cortina de café)
    glass: str = "window_glass"
    torn: bool = False
    stack: str = "both"           # 'both' (abre para os dois lados) ou 'low' (recolhe só no lado de menor u)
    cracked: bool = False         # um vidro trincado, remendado com fita
    blinds_drop: float = 1.0      # fração do vão coberta pela persiana
    crooked: float = 0.0          # inclinação da barra da persiana (m)


STYLES = {
    "w_living_s": WindowStyle("curtain_open"), "w_living_w": WindowStyle("curtain_open"),
    "w_dining_s": WindowStyle("curtain_closed"),
    "w_den_w": WindowStyle("curtain_open", stack="low"),     # o quadro de cortiça ocupa a parede ao norte da janela
    "w_den_n": WindowStyle("blinds", blinds_drop=0.55),
    "w_kitchen_n": WindowStyle("curtain_open", "short"),
    "w_kitchen_e": WindowStyle("blinds", blinds_drop=1.0),
    "w_master_n": WindowStyle("curtain_open"), "w_master_w": WindowStyle("curtain_closed", torn=True),
    "w_kids_s": WindowStyle("curtain_closed"), "w_kids_w": WindowStyle("curtain_closed"),
    "w_bath_s": WindowStyle(glass="frosted_glass"),
    "w_study_n": WindowStyle("blinds", blinds_drop=0.35), "w_hall_u_n": WindowStyle(cracked=True),
    "w_study_e": WindowStyle("blinds", blinds_drop=0.8, crooked=0.05),
}


class WindowFrame:
    """Coordenadas da janela: u ao longo da parede, s para FORA da casa (negativo = para dentro), z."""

    def __init__(self, op, piece):
        self.op = op
        self.piece = piece
        self.half = piece.thickness / 2
        self.inward = inward_sign(piece)
        self.outward = -self.inward
        self.z0 = layout.LEVEL_Z[op.level] + op.sill
        self.z1 = self.z0 + op.height

    def n(self, s):
        return self.op.pos + self.outward * s

    def box(self, builder, u0, u1, s0, s1, z0, z1, material, skip=()):
        n0, n1 = sorted((self.n(s0), self.n(s1)))
        wall_box(builder, self.op, u0, u1, n0, n1, z0, z1, material, skip)

    def point(self, u, s, z):
        return wall_point(self.op, u, self.n(s), z)

    @property
    def center(self):
        return wall_point(self.op, (self.op.a + self.op.b) / 2, self.op.pos, (self.z0 + self.z1) / 2)


def build(ctx, op, piece):
    from . import dressings
    style = STYLES.get(op.id, WindowStyle())
    frame = WindowFrame(op, piece)
    molded = ModelBuilder(f"_win_molded_{op.id}", PROFILED)
    plain = ModelBuilder(f"_win_plain_{op.id}", PROFILED)
    _liners(plain, frame)
    _sashes(ctx, plain, frame, style)
    _interior_trim(molded, frame)
    _exterior_trim(plain, molded, frame)
    if op.axis == "x" and op.pos == SHUTTER_WALL_Y and op.width >= 1.0 and op.level == 0:
        _shutters(plain, frame)
    window = build_combined(ctx, C.COL_WORLD, f"{C.N_WINDOW}{op.id}", [molded, plain], origin=frame.center)
    _blocker(ctx, frame)
    window[C.P_ID] = op.id
    window[C.P_INTERACT] = "look"
    window[C.P_PROMPT] = "[E] Olhar"
    window[C.P_ROOM] = op.rooms[0]
    covering = dressings.build(ctx, frame, style)
    if covering is not None:
        attach(covering, window)
    return window


def _blocker(ctx, frame):
    """Proxy invisível que fecha o vão da janela para a colisão (o jogador não sai por ela)."""
    op = frame.op
    blocker = ModelBuilder(f"COL_Window_{op.id}", None)
    wall_box(blocker, op, op.a, op.b, op.pos - frame.half, op.pos + frame.half, frame.z0, frame.z1, "black")
    blocker.build(ctx, C.COL_COLLISION, collision=True, hide=True)


# --------------------------------------------------------------------------
# Caixa da janela e folhas
# --------------------------------------------------------------------------
def _liners(builder, frame):
    """Forro de madeira que reveste o vão por dentro, em toda a espessura da parede."""
    op, half = frame.op, frame.half
    frame.box(builder, op.a, op.a + LINER, -half, half, frame.z0, frame.z1, "trim_white")
    frame.box(builder, op.b - LINER, op.b, -half, half, frame.z0, frame.z1, "trim_white")
    frame.box(builder, op.a + LINER, op.b - LINER, -half, half, frame.z1 - LINER, frame.z1, "trim_white")


def _units(frame):
    """Intervalos (u0, u1) de cada unidade de guilhotina entre as jambas e os montantes."""
    op = frame.op
    inner = op.width - 2 * LINER
    count = max(1, math.ceil(inner / UNIT_WIDTH))
    post = 0.05
    width = (inner - (count - 1) * post) / count
    start = op.a + LINER
    return [(start + i * (width + post), start + i * (width + post) + width) for i in range(count)], post


def _sashes(ctx, builder, frame, style):
    units, post = _units(frame)
    for u0, u1 in units[1:]:
        frame.box(builder, u0 - post, u0, -0.04, 0.04, frame.z0, frame.z1 - LINER, "trim_white")
    z_floor, z_head = frame.z0 + 0.012, frame.z1 - LINER
    z_meet = (z_floor + z_head) / 2
    tall = frame.op.height >= 0.9
    for u0, u1 in units:
        lower = (u0, u1, z_floor, z_meet + MEETING / 2)
        upper = (u0, u1, z_meet - MEETING / 2, z_head)
        _sash(builder, frame, lower, (-SASH_DEPTH - 0.003, -0.003), True, style.glass, tall)
        if style.cracked and (u0, u1) == units[0]:
            _taped_crack(builder, frame, lower, tall)
        _sash(builder, frame, upper, (0.003, SASH_DEPTH + 0.003), False, style.glass, tall)
        _hardware(ctx, builder, frame, (u0 + u1) / 2, z_floor, z_meet)


def _sash(builder, frame, rect, depth, is_lower, glass, tall):
    """Folha de guilhotina: duas longarinas, duas travessas, bastões e o vidro."""
    u0, u1, z0, z1 = rect
    s0, s1 = depth
    bottom_rail = RAIL + 0.015 if is_lower else MEETING
    top_rail = MEETING if is_lower else RAIL
    frame.box(builder, u0, u0 + STILE, s0, s1, z0, z1, "trim_white")
    frame.box(builder, u1 - STILE, u1, s0, s1, z0, z1, "trim_white")
    frame.box(builder, u0 + STILE, u1 - STILE, s0, s1, z0, z0 + bottom_rail, "trim_white")
    frame.box(builder, u0 + STILE, u1 - STILE, s0, s1, z1 - top_rail, z1, "trim_white")
    inner = (u0 + STILE, u1 - STILE, z0 + bottom_rail, z1 - top_rail)
    columns = 3 if (u1 - u0) >= 0.6 else 2
    rows = 2 if tall else 1
    _muntins(builder, frame, inner, (s0 + s1) / 2, columns, rows)
    middle = (s0 + s1) / 2
    ia, ib, iz0, iz1 = inner
    builder.poly([frame.point(ia, middle, iz0), frame.point(ib, middle, iz0), frame.point(ib, middle, iz1),
                  frame.point(ia, middle, iz1)], glass)


def _taped_crack(builder, frame, lower_rect, tall):
    """Trinca num vidro da folha de baixo, remendada com duas tiras de fita em X. Só em paredes ao longo de X."""
    u0, u1, z0, z1 = lower_rect
    columns = 3 if (u1 - u0) >= 0.6 else 2
    rows = 2 if tall else 1
    inner_u0, inner_u1 = u0 + STILE, u1 - STILE
    inner_z0, inner_z1 = z0 + RAIL + 0.015, z1 - MEETING
    pane_w, pane_h = (inner_u1 - inner_u0) / columns, (inner_z1 - inner_z0) / rows
    centre_u = inner_u0 + pane_w * (columns // 2 + 0.5 * (columns % 2 == 0))
    centre_z = inner_z0 + pane_h * 0.5
    s = -(SASH_DEPTH + 0.003) / 2 - 0.0012
    size = max(pane_w, pane_h)
    corners = [frame.point(centre_u + dx * size / 2, s, centre_z + dz * size / 2)
               for dx, dz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    builder.facing(corners, tuple(-frame.outward * normal(frame.op)), "decal_crack",
                   [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
    for angle in (38, -38):
        with builder.at(*frame.point(centre_u, s - 0.0004, centre_z), ry=angle):
            builder.box(-size * 0.62, -0.0004, -0.009, size * 0.62, 0.0004, 0.009, "tape_gray")


def _muntins(builder, frame, inner, middle, columns, rows):
    u0, u1, z0, z1 = inner
    half_depth = MUNTIN_D / 2
    for i in range(1, columns):
        u = u0 + (u1 - u0) * i / columns
        frame.box(builder, u - MUNTIN_W / 2, u + MUNTIN_W / 2, middle - half_depth, middle + half_depth, z0, z1,
                  "trim_white")
    for j in range(1, rows):
        z = z0 + (z1 - z0) * j / rows
        frame.box(builder, u0, u1, middle - half_depth, middle + half_depth, z - MUNTIN_W / 2, z + MUNTIN_W / 2,
                  "trim_white")


def _hardware(ctx, builder, frame, u, z_floor, z_meet):
    """Trava de encontro (fecho de came) e dois puxadores de latão na travessa de baixo."""
    sides = detail(ctx, 10)
    s_face = -SASH_DEPTH - 0.003
    frame.box(builder, u - 0.032, u + 0.032, s_face - 0.006, s_face, z_meet + MEETING / 2 - 0.016,
              z_meet + MEETING / 2 - 0.006, "brass_worn")
    knob = [(0.011, 0.0), (0.011, 0.004), (0.006, 0.0075), (0.0, 0.008)]
    _lathe_toward(builder, frame, u, s_face - 0.006, z_meet + MEETING / 2 - 0.011, knob, sides)
    frame.box(builder, u + 0.002, u + 0.036, s_face - 0.020, s_face - 0.012, z_meet + MEETING / 2 - 0.014,
              z_meet + MEETING / 2 - 0.008, "brass_worn")
    for offset in (-0.14, 0.14):
        frame.box(builder, u + offset - 0.022, u + offset + 0.022, s_face - 0.012, s_face - 0.0, z_floor + 0.020,
                  z_floor + 0.026, "brass_worn")
        frame.box(builder, u + offset - 0.022, u + offset - 0.014, s_face - 0.014, s_face, z_floor + 0.020,
                  z_floor + 0.040, "brass_worn")
        frame.box(builder, u + offset + 0.014, u + offset + 0.022, s_face - 0.014, s_face, z_floor + 0.020,
                  z_floor + 0.040, "brass_worn")


def _lathe_toward(builder, frame, u, s, z, profile, sides):
    """Torneado de latão cujo eixo aponta para dentro da casa, partindo de (u, s, z)."""
    point = frame.point(u, s, z)
    turn = {"rx": -90 * frame.inward} if frame.op.axis == "x" else {"ry": 90 * frame.inward}
    with builder.at(*point, **turn):
        builder.lathe(profile, "brass_worn", sides)


# --------------------------------------------------------------------------
# Acabamento interno e externo
# --------------------------------------------------------------------------
def _interior_trim(builder, frame):
    """Guarnição de três lados, peitoril (stool) com chifres e avental sob ele."""
    op, half = frame.op, frame.half
    inward = frame.inward
    moldings.casing(builder, op, half, frame.z0 + STOOL_THICK, frame.z1, "trim_white", sides=(inward,))
    reach = moldings.CASING_WIDTH + 0.04
    start = wall_point(op, op.a - reach, op.pos + inward * half, frame.z0)
    end = wall_point(op, op.b + reach, op.pos + inward * half, frame.z0)
    stool = [(-half, 0.0), (0.060, 0.0), (0.060, 0.016), (0.054, 0.025), (0.044, STOOL_THICK), (-half, STOOL_THICK)]
    builder.sweep(stool, [start, end], [normal(op) * inward], (0.0, 0.0, 1.0), "trim_white")
    apron_start = wall_point(op, op.a - reach + 0.02, op.pos + inward * half, frame.z0 - 0.075)
    apron_end = wall_point(op, op.b + reach - 0.02, op.pos + inward * half, frame.z0 - 0.075)
    apron = [(0.0, 0.0), (0.0, 0.075), (0.012, 0.075), (0.020, 0.069), (0.020, 0.012), (0.012, 0.0)]
    builder.sweep(apron, [apron_start, apron_end], [normal(op) * inward], (0.0, 0.0, 1.0), "trim_white")


def _exterior_trim(plain, molded, frame):
    """Guarnição lisa de tábua, pingadeira sobre a verga e peitoril inclinado com pingo."""
    op, half = frame.op, frame.half
    outward = frame.outward
    s0, s1 = half, half + 0.026
    width = 0.09
    frame.box(plain, op.a - width, op.a, s0, s1, frame.z0, frame.z1 + width, "trim_white")
    frame.box(plain, op.b, op.b + width, s0, s1, frame.z0, frame.z1 + width, "trim_white")
    frame.box(plain, op.a, op.b, s0, s1, frame.z1, frame.z1 + width, "trim_white")
    frame.box(plain, op.a - width - 0.02, op.b + width + 0.02, s0 - 0.004, s1 + 0.024, frame.z1 + width,
              frame.z1 + width + 0.022, "trim_white")
    start = wall_point(op, op.a - width - 0.02, op.pos + outward * half, frame.z0)
    end = wall_point(op, op.b + width + 0.02, op.pos + outward * half, frame.z0)
    sill = [(-half, 0.0), (0.075, -0.022), (0.075, -0.012), (0.055, 0.004), (-half, 0.030)]
    molded.sweep(sill, [start, end], [normal(op) * outward], (0.0, 0.0, 1.0), "trim_white")


def _shutters(builder, frame):
    """Venezianas fixas de réguas inclinadas na face externa, um par ao lado de cada janela larga."""
    op = frame.op
    margin = 0.09 + 0.02
    s0, s1 = frame.half, frame.half + 0.036
    z0, z1 = frame.z0 - 0.03, frame.z1 + 0.09
    for u0, u1 in ((op.a - margin - SHUTTER_WIDTH, op.a - margin), (op.b + margin, op.b + margin + SHUTTER_WIDTH)):
        frame.box(builder, u0, u0 + 0.04, s0, s1, z0, z1, "wall_green")
        frame.box(builder, u1 - 0.04, u1, s0, s1, z0, z1, "wall_green")
        frame.box(builder, u0 + 0.04, u1 - 0.04, s0, s1, z0, z0 + 0.05, "wall_green")
        frame.box(builder, u0 + 0.04, u1 - 0.04, s0, s1, z1 - 0.05, z1, "wall_green")
        slats = int((z1 - z0 - 0.1) / 0.055)
        for k in range(slats):
            z = z0 + 0.05 + (k + 0.5) * (z1 - z0 - 0.1) / slats
            _slat(builder, frame, u0 + 0.04, u1 - 0.04, (s0 + s1) / 2, z)


def _slat(builder, frame, u0, u1, s, z):
    """Régua de veneziana: prisma fino, com a aresta externa mais baixa para escorrer a chuva."""
    section = [(s - 0.012, z - 0.003), (s + 0.012, z - 0.019), (s + 0.012, z - 0.013), (s - 0.012, z + 0.003)]
    builder.loft([[frame.point(u0, ss, zz) for ss, zz in section], [frame.point(u1, ss, zz) for ss, zz in section]],
                 "wall_green")
