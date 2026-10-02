"""Marcas da decadência nas paredes e no forro: papel de parede descolando (com o reboco à mostra), rachaduras,
mofo, manchas de infiltração e teias nos cantos altos.

Os decalques de mancha são quadriláteros a 2 mm da superfície, com textura de alfa mapeada por UV. O papel
descolado é geometria de verdade: uma fita que se afasta da parede e se enrola na ponta de baixo, no material
`wall_peel` (a mesma estampa da parede, com o avesso claro). Cada cômodo conta uma coisa diferente: o quarto da
menina fica limpo, o banheiro mofado, a garagem rachada.
"""
import math
import random

from mathutils import Vector

from .. import conventions as C
from .. import layout
from . import details, moldings, wallgeom, wallsites
from .modelkit import PROFILED, ModelBuilder

LIFT = 0.002

# (peel, crack, mold, damp, webs) por cômodo
PLAN = {
    "hall_g": (3, 1, 0, 2, 3), "living": (2, 0, 0, 1, 3), "den": (0, 2, 1, 1, 3), "dining": (2, 1, 0, 1, 3),
    "kitchen": (0, 2, 2, 2, 2), "garage": (0, 3, 2, 2, 5), "hall_u": (2, 1, 1, 2, 3), "kids": (0, 0, 0, 0, 0),
    "master": (2, 0, 1, 1, 2), "bath": (0, 1, 4, 2, 2), "study": (0, 2, 0, 1, 3),
}
WALLPAPER_ROOMS = ("hall_g", "living", "dining", "hall_u", "master")
GHOST_ROOMS = ("living", "master", "hall_u")         # quadros que alguém levou
MOUSE_ROOMS = ("hall_g", "garage")
BASEBOARD_FRONT = 0.0198


def build(ctx):
    rng = random.Random(f"decals:{ctx.seed}")
    for level in (0, 1):
        stains = ModelBuilder(f"Decals_L{level}", None)
        webs = ModelBuilder(f"Webs_L{level}", None)
        strips = ModelBuilder(f"Peeling_L{level}", PROFILED)
        sites = wallsites.sites(level)
        for room_id in sorted({s.room_id for s in sites}):
            room_sites = [s for s in sites if s.room_id == room_id and s.length > 0.7]
            peel, cracks, mold, damp, cobwebs = PLAN.get(room_id, (0, 0, 0, 0, 0))
            if not room_sites:
                continue
            for _ in range(peel):
                _peeling_strip(strips, stains, rng.choice(room_sites), level, rng)
            for _ in range(cracks):
                _wall_decal(stains, rng.choice(room_sites), level, rng, "decal_crack", (0.9, 1.5), (1.1, 2.0), True)
            for _ in range(mold):
                _mold(stains, rng.choice(room_sites), level, rng)
            for _ in range(damp):
                _ceiling_stain(stains, layout.ROOMS[room_id], level, rng)
            for _ in range(cobwebs):
                _cobweb(webs, layout.ROOMS[room_id], level, rng)
        _small_stories(stains, strips, level, sites, rng)
        for builder in (stains, webs):
            obj = builder.build(ctx, C.COL_WORLD)
            if obj is not None:
                obj.visible_shadow = False
        strips.build(ctx, C.COL_WORLD)
    ctx.log("decalques: papel descolando, rachaduras, mofo, infiltração e teias")


# --------------------------------------------------------------------------
# Decalques de parede
# --------------------------------------------------------------------------
def _uv_corners(rng, rotate=True):
    """UV de um quadrilátero, girado/espelhado ao acaso para a textura não se repetir igual."""
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    if rotate:
        turns = rng.randrange(4)
        uvs = uvs[turns:] + uvs[:turns]
        if rng.random() < 0.5:
            uvs = [uvs[0], uvs[3], uvs[2], uvs[1]]
    return uvs


def _wall_quad(builder, site, u, z, width, height, material, rng, rotate=True, lift=LIFT):
    corners = [site.point(u + dx * width / 2, z + dz * height / 2, lift)
               for dx, dz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    builder.facing(corners, tuple(site.out), material, _uv_corners(rng, rotate))


def _wall_decal(builder, site, level, rng, material, size_range, z_range, rotate):
    size = rng.uniform(*size_range)
    u = rng.uniform(site.u0 + size * 0.2, max(site.u0 + size * 0.2 + 0.01, site.u1 - size * 0.2))
    z = layout.LEVEL_Z[level] + rng.uniform(*z_range)
    _wall_quad(builder, site, u, z, size, size, material, rng, rotate)


def _mold(builder, site, level, rng):
    """Mofo no alto, junto ao forro, ou rente ao piso (atrás de onde ficam os móveis)."""
    high = rng.random() < 0.6
    size = rng.uniform(0.55, 0.95)
    z = layout.CEIL_Z[level] - size * 0.35 if high else layout.LEVEL_Z[level] + size * 0.3
    u = site.u0 + 0.1 if rng.random() < 0.5 else site.u1 - 0.1
    _wall_quad(builder, site, u, z, size, size, "decal_mold", rng)


def _peeling_strip(strips, stains, site, level, rng):
    """Fita de papel de parede que se soltou do alto da parede e se enrola, com o reboco à mostra atrás."""
    width = rng.uniform(0.38, 0.53)
    length = rng.uniform(0.7, 1.25)
    u = rng.uniform(site.u0 + width / 2, max(site.u0 + width / 2 + 0.01, site.u1 - width / 2))
    top = layout.CEIL_Z[level] - 0.13
    curl = rng.uniform(0.07, 0.16)
    skew = rng.choice((-1.0, 1.0)) * rng.uniform(0.03, 0.09)
    columns, rows = 6, 12
    lengths = [length * rng.uniform(0.82, 1.12) for _ in range(columns + 1)]
    grid = []
    for r in range(rows + 1):
        t = r / rows
        row = []
        for c in range(columns + 1):
            across = c / columns - 0.5
            out = LIFT + 0.001 + curl * t ** 2.4 * (1.0 + 0.5 * across * skew * 6)
            shift = skew * t ** 2 + 0.01 * math.sin(c * 2.0 + t * 5.0)
            point = Vector(site.point(u + across * width + shift, top - t * lengths[c], out))
            row.append(tuple(point))
        grid.append(row)
    for r in range(rows):
        for c in range(columns):
            quad = [grid[r][c], grid[r][c + 1], grid[r + 1][c + 1], grid[r + 1][c]]
            strips.facing(quad, tuple(site.out), "wall_peel")
    patch_height = length * 0.85
    _wall_quad(stains, site, u, top - patch_height / 2, width * 1.05, patch_height, "decal_plaster", rng, False,
               LIFT * 0.6)


# --------------------------------------------------------------------------
# Forro e cantos
# --------------------------------------------------------------------------
def _ceiling_stain(builder, room, level, rng):
    """Mancha de infiltração no forro, perto de uma das paredes."""
    rect = room.rect
    size = rng.uniform(0.7, 1.4)
    x = rng.uniform(rect.x0 + 0.4, rect.x1 - 0.4)
    y = rng.uniform(rect.y0 + 0.4, rect.y1 - 0.4)
    z = layout.CEIL_Z[level] - LIFT
    h = size / 2
    corners = [(x - h, y - h, z), (x + h, y - h, z), (x + h, y + h, z), (x - h, y + h, z)]
    builder.facing(corners, (0.0, 0.0, -1.0), "decal_damp", _uv_corners(rng))


def _cobweb(builder, room, level, rng):
    """Teia num canto do forro, esticada sobre uma das duas paredes que formam o canto."""
    rect = room.rect
    cx, cy = rng.choice([(rect.x0, rect.y0), (rect.x1, rect.y0), (rect.x1, rect.y1), (rect.x0, rect.y1)])
    sx, sy = (1.0 if cx == rect.x0 else -1.0), (1.0 if cy == rect.y0 else -1.0)
    half_x, half_y = _wall_half(level, "y", cx, cy), _wall_half(level, "x", cy, cx)
    size = rng.uniform(0.28, 0.5)
    z = layout.CEIL_Z[level] - 0.004
    if rng.random() < 0.5:
        face_x = cx + sx * half_x
        y0 = cy + sy * half_y
        points = [(face_x + sx * LIFT, y0, z), (face_x + sx * LIFT, y0 + sy * size, z),
                  (face_x + sx * LIFT, y0 + sy * size, z - size), (face_x + sx * LIFT, y0, z - size)]
        toward = (sx, 0.0, 0.0)
    else:
        face_y = cy + sy * half_y
        x0 = cx + sx * half_x
        points = [(x0, face_y + sy * LIFT, z), (x0 + sx * size, face_y + sy * LIFT, z),
                  (x0 + sx * size, face_y + sy * LIFT, z - size), (x0, face_y + sy * LIFT, z - size)]
        toward = (0.0, sy, 0.0)
    builder.facing(points, toward, "decal_cobweb", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])


def _wall_half(level, axis, pos, along):
    """Metade da espessura da parede em `axis`=pos que passa por `along`."""
    for piece in layout.wall_pieces(level):
        if piece.axis == axis and abs(piece.pos - pos) < 1e-6 and piece.a - 1e-6 <= along <= piece.b + 1e-6:
            return piece.thickness / 2
    return layout.WALL_T_INT / 2


# --------------------------------------------------------------------------
# Pequenas histórias: o que a casa guardou
# --------------------------------------------------------------------------
def _small_stories(stains, solids, level, sites, rng):
    """Peças pequenas de ambientação: quadros levados, marcas de altura da Emma, buraco de rato,
    escorridos sob as janelas, fumaça em volta das luminárias e dedos nos interruptores."""
    for room_id in GHOST_ROOMS:
        room_sites = [s for s in sites if s.room_id == room_id and s.length > 1.3]
        if room_sites:
            _picture_ghost(stains, solids, rng.choice(room_sites), level, rng)
    for room_id in MOUSE_ROOMS:
        room_sites = [s for s in sites if s.room_id == room_id and s.length > 1.0]
        if room_sites:
            _mouse_hole(stains, rng.choice(room_sites), level, rng)
    if level == 1:
        _height_marks(stains)
    for op in layout.windows():
        if op.level == level and op.sill >= 0.8:
            _drips(stains, op, level)
    for room_id, spots in layout.CEILING_LIGHTS.items():
        if layout.ROOMS[room_id].level == level:
            for x, y in spots:
                _soot(stains, x, y, layout.CEIL_Z[level])
    for site, u, z in details.switch_spots(level):
        _wall_quad(stains, site, u, z, 0.2, 0.2, "decal_dirt", rng, False, 0.0016)


def _picture_ghost(stains, solids, site, level, rng):
    width, height = rng.uniform(0.45, 0.72), rng.uniform(0.55, 0.85)
    u = rng.uniform(site.u0 + width / 2, max(site.u0 + width / 2 + 0.01, site.u1 - width / 2))
    z = layout.LEVEL_Z[level] + rng.uniform(1.45, 1.75)
    _wall_quad(stains, site, u, z, width, height, "decal_ghost", rng, False, 0.0015)
    nail_z = z + height / 2 - 0.07
    solids.tube(site.point(u, nail_z, 0.0), site.point(u, nail_z, 0.012), 0.0016, "steel_hardware", 6)
    solids.tube(site.point(u, nail_z, 0.012), site.point(u, nail_z, 0.0135), 0.0042, "steel_hardware", 8)


def _mouse_hole(stains, site, level, rng):
    u = rng.uniform(site.u0 + 0.2, site.u1 - 0.2)
    _wall_quad(stains, site, u, layout.LEVEL_Z[level] + 0.055, 0.1, 0.1, "decal_mouse", rng, False, BASEBOARD_FRONT)


def _height_marks(stains):
    """Riscos de lápis na guarnição da porta do quarto da Emma, do lado de dentro, na altura de uma criança."""
    op = layout.OPENINGS["kids_hall"]
    piece = wallgeom.opening_pieces()[op.id]
    side = "lo" if piece.room_lo == "kids" else "hi"
    sign = -1.0 if side == "lo" else 1.0
    n = op.pos + sign * (piece.thickness / 2 + 0.0287)
    u = op.a - moldings.CASING_WIDTH * 0.5
    z0 = layout.LEVEL_Z[op.level]
    half_w = 0.036
    corners = [wallgeom.wall_point(op, u + dx * half_w, n, z0 + z)
               for dx, z in ((-1, 0.38), (1, 0.38), (1, 1.42), (-1, 1.42))]
    out = tuple(wallgeom.normal(op) * sign)
    stains.facing(corners, out, "decal_height", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])


def _drips(stains, op, level):
    """Dois escorridos, um sob cada canto do peitoril, na face de dentro da parede."""
    piece = next(p for p in layout.wall_pieces(level) if p.opening == op.id and p.kind == "sill")
    room_id = op.rooms[0]
    side = "lo" if piece.room_lo == room_id else "hi"
    site = wallsites.Site(piece, side, room_id, piece.a, piece.b)
    top = layout.LEVEL_Z[level] + op.sill - 0.075
    for u in (op.a - 0.02, op.b + 0.02):
        corners = [site.point(u + dx * 0.14, top - dz, 0.0014) for dx, dz in ((-1, 0.8), (1, 0.8), (1, 0.0), (-1, 0.0))]
        stains.facing(corners, tuple(site.out), "decal_drip", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])


def _soot(stains, x, y, z):
    half = 0.45
    corners = [(x - half, y - half, z - 0.0016), (x + half, y - half, z - 0.0016), (x + half, y + half, z - 0.0016),
               (x - half, y + half, z - 0.0016)]
    stains.facing(corners, (0.0, 0.0, -1.0), "decal_soot", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
