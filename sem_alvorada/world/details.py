"""Detalhes de parede e teto: tomadas, interruptores, termostato, grelhas, detectores de fumaça, aquecedores
de rodapé e o quadro de luz da garagem.

Cada peça é modelada num sistema local: X ao longo da parede, Y para fora dela (para dentro do cômodo) e Z
para cima, com a origem no centro da placa sobre a face da parede. `Site.yaw_degrees` leva esse sistema para
a orientação certa de cada parede. Tudo de um andar vira um único objeto `WallDetails_L<n>`.

Alturas de referência (casa americana): tomadas a 30 cm do piso (a 1,1 m em cozinha, garagem e banheiro),
interruptores a 1,22 m, termostato a 1,5 m.
"""
import random

from .. import conventions as C
from .. import layout
from . import wallsites
from .modelkit import FINE, PROFILED, ModelBuilder, build_combined

OUTLET_HEIGHT = 0.30
HIGH_OUTLET_HEIGHT = 1.10
SWITCH_HEIGHT = 1.22
THERMOSTAT_HEIGHT = 1.50
HIGH_OUTLET_ROOMS = ("kitchen", "garage", "bath")
THERMOSTAT_ROOMS = ("hall_g", "hall_u")
SMOKE_ROOMS = {"hall_g": (6.5, 5.0), "hall_u": (6.6, 5.0), "kids": (3.9, 1.2), "master": (3.9, 9.0),
               "kitchen": (11.0, 8.9), "garage": (15.5, 1.3)}
GRILLE_ROOMS = ("hall_g", "hall_u", "living", "master", "kids", "study", "dining")
HEATER_WINDOWS = ("w_living_w", "w_dining_s", "w_den_w", "w_study_e")
PLATE_W, PLATE_H, PLATE_T = 0.070, 0.115, 0.0034


def build(ctx):
    rng = random.Random(f"details:{ctx.seed}")
    for level in (0, 1):
        plates = ModelBuilder(f"_details_plates_L{level}", FINE)
        turned = ModelBuilder(f"_details_turned_L{level}", PROFILED)
        all_sites = wallsites.sites(level)
        _outlets(plates, turned, level, all_sites, rng)
        _switches(plates, turned, level)
        _thermostats(plates, turned, level, all_sites, rng)
        _grilles(plates, level, all_sites, rng)
        _smoke_detectors(turned, level)
        _heaters(plates, level)
        if level == 0:
            _electrical_panel(plates, turned, all_sites)
        else:
            _bath_fan(plates)
        build_combined(ctx, C.COL_WORLD, f"WallDetails_L{level}", [plates, turned])
    ctx.log("detalhes: tomadas, interruptores, termostatos, grelhas, detectores, aquecedores e quadro de luz")


# --------------------------------------------------------------------------
# Posicionamento
# --------------------------------------------------------------------------
def _place(builder, site, u, z, lift=0.0):
    """Contexto que leva o sistema local para (u, z) na face do sítio."""
    return builder.at(*site.point(u, z, lift), rz=site.yaw_degrees)


def _spread(site, rng, taken, spacing=1.0):
    """Posição livre dentro do sítio, longe das já usadas; None se não couber."""
    for _ in range(12):
        u = rng.uniform(site.u0 + 0.1, site.u1 - 0.1)
        if all(abs(u - other) >= spacing for other in taken):
            return u
    return None


def _outlets(plates, turned, level, sites, rng):
    for room_id in sorted({s.room_id for s in sites}):
        room_sites = [s for s in sites if s.room_id == room_id]
        total = sum(s.length for s in room_sites)
        wanted = max(2, round(total / 3.6))
        height = HIGH_OUTLET_HEIGHT if room_id in HIGH_OUTLET_ROOMS else OUTLET_HEIGHT
        taken = {id(s): [] for s in room_sites}
        for _ in range(wanted):
            site = rng.choices(room_sites, weights=[s.length for s in room_sites])[0]
            u = _spread(site, rng, taken[id(site)])
            if u is None:
                continue
            taken[id(site)].append(u)
            with _place(plates, site, u, layout.LEVEL_Z[level] + height):
                _outlet(plates, turned)


def switch_spots(level):
    """(sítio, u, z) de cada interruptor: ao lado do lado da fechadura de cada porta, em cada cômodo que ela serve."""
    spots = []
    for op in layout.doors():
        if op.level != level:
            continue
        for room_id in op.rooms:
            site, u = wallsites.next_to_opening(op, room_id)
            if site is not None:
                spots.append((site, u, layout.LEVEL_Z[level] + SWITCH_HEIGHT))
    return spots


def _switches(plates, turned, level):
    for site, u, z in switch_spots(level):
        with _place(plates, site, u, z):
            _switch(plates, turned)


def _thermostats(plates, turned, level, sites, rng):
    for room_id in THERMOSTAT_ROOMS:
        room_sites = [s for s in sites if s.room_id == room_id and s.length > 1.0]
        if not room_sites:
            continue
        site = max(room_sites, key=lambda s: s.length)
        u = (site.u0 + site.u1) / 2 + rng.uniform(-0.3, 0.3)
        with _place(turned, site, u, layout.LEVEL_Z[level] + THERMOSTAT_HEIGHT):
            _thermostat(turned)


def _grilles(plates, level, sites, rng):
    for room_id in GRILLE_ROOMS:
        room_sites = [s for s in sites if s.room_id == room_id and s.length > 0.9]
        if not room_sites:
            continue
        site = rng.choice(room_sites)
        u = rng.uniform(site.u0 + 0.25, site.u1 - 0.25)
        with _place(plates, site, u, layout.CEIL_Z[level] - 0.32):
            _wall_grille(plates)


def _smoke_detectors(turned, level):
    for room_id, (x, y) in SMOKE_ROOMS.items():
        room = layout.ROOMS[room_id]
        if room.level != level:
            continue
        with turned.at(x, y, layout.CEIL_Z[level], rx=180):
            _smoke_detector(turned)


def _heaters(plates, level):
    for window_id in HEATER_WINDOWS:
        op = layout.OPENINGS[window_id]
        if op.level != level:
            continue
        site = _site_under_window(level, op)
        if site is not None:
            with _place(plates, site, (op.a + op.b) / 2, layout.LEVEL_Z[level]):
                _baseboard_heater(plates, min(1.2, op.width - 0.3))


def _site_under_window(level, op):
    """Sítio (face interna) da parede do vão da janela: usa a peça 'sill' abaixo dela."""
    for piece in layout.wall_pieces(level):
        if piece.opening == op.id and piece.kind == "sill":
            room_id = op.rooms[0]
            side = "lo" if piece.room_lo == room_id else "hi"
            return wallsites.Site(piece, side, room_id, piece.a, piece.b)
    return None


# --------------------------------------------------------------------------
# Peças
# --------------------------------------------------------------------------
def _screw(turned, x, z):
    with turned.at(x, PLATE_T, z, rx=-90):
        turned.lathe([(0.0, 0.0), (0.0042, 0.0), (0.0042, 0.0012), (0.0, 0.0016)], "steel_hardware", 8)


def _plate(plates, rows=1):
    plates.box(-PLATE_W / 2, 0.0, -PLATE_H / 2, PLATE_W / 2, PLATE_T, PLATE_H / 2, "plastic_ivory")


def _outlet(plates, turned):
    """Tomada dupla de 15 A: placa marfim, duas faces de soquete com furos e parafuso central."""
    _plate(plates)
    for z in (-0.0275, 0.0275):
        plates.box(-0.0185, PLATE_T, z - 0.0165, 0.0185, PLATE_T + 0.0009, z + 0.0165, "plastic_ivory")
        for x in (-0.0072, 0.0072):
            plates.box(x - 0.0016, PLATE_T + 0.0009, z + 0.003, x + 0.0016, PLATE_T + 0.0012, z + 0.0115,
                       "plastic_black")
        plates.box(-0.0026, PLATE_T + 0.0009, z - 0.0125, 0.0026, PLATE_T + 0.0012, z - 0.0075, "plastic_black")
    _screw(turned, 0.0, 0.0)


def _switch(plates, turned):
    """Interruptor de alavanca: placa marfim, fenda escura, alavanca e dois parafusos."""
    _plate(plates)
    plates.box(-0.0075, PLATE_T, -0.0145, 0.0075, PLATE_T + 0.0008, 0.0145, "plastic_black")
    plates.box(-0.0042, PLATE_T, 0.0, 0.0042, PLATE_T + 0.0155, 0.0215, "plastic_ivory")
    for z in (-0.0445, 0.0445):
        _screw(turned, 0.0, z)


def _thermostat(turned):
    """Termostato redondo: base, anel graduado e tampa de plástico."""
    with turned.at(0.0, 0.0, 0.0, rx=-90):
        turned.lathe([(0.0, 0.0), (0.055, 0.0), (0.057, 0.004), (0.054, 0.012), (0.046, 0.0185), (0.036, 0.0215),
                      (0.0, 0.0225)], "plastic_white_aged", 20)
        turned.lathe([(0.0, 0.0225), (0.030, 0.0225), (0.030, 0.0235), (0.0, 0.0245)], "plastic_ivory", 16)
        turned.lathe([(0.0, 0.0248), (0.004, 0.0248), (0.004, 0.0275), (0.0, 0.0275)], "brass_worn", 8)


def _wall_grille(plates):
    """Grelha de retorno de ar: moldura com sete lâminas inclinadas."""
    plates.box(-0.22, 0.0, -0.12, 0.22, 0.008, -0.108, "painted_metal")
    plates.box(-0.22, 0.0, 0.108, 0.22, 0.008, 0.12, "painted_metal")
    plates.box(-0.22, 0.0, -0.108, -0.208, 0.008, 0.108, "painted_metal")
    plates.box(0.208, 0.0, -0.108, 0.22, 0.008, 0.108, "painted_metal")
    plates.box(-0.208, 0.0, -0.108, 0.208, 0.0015, 0.108, "iron_black")
    for k in range(7):
        z = -0.09 + k * 0.03
        with plates.at(0.0, 0.0045, z, rx=-38):
            plates.box(-0.205, -0.0012, -0.014, 0.205, 0.0012, 0.014, "painted_metal")


def _smoke_detector(turned):
    """Detector de fumaça preso ao forro (o eixo local aponta para baixo): disco com tampa ventilada e LED."""
    turned.lathe([(0.0, 0.0), (0.072, 0.0), (0.074, 0.005), (0.070, 0.021), (0.052, 0.030), (0.0, 0.031)],
                 "plastic_white_aged", 20)
    turned.lathe([(0.0, 0.0305), (0.030, 0.0305), (0.030, 0.0325), (0.0, 0.0325)], "plastic_ivory", 14)
    with turned.at(0.045, 0.0, 0.0285):
        turned.lathe([(0.0, 0.0), (0.0035, 0.0), (0.0035, 0.002), (0.0, 0.0025)], "led_smoke_red", 6)


def _baseboard_heater(plates, length):
    """Aquecedor de rodapé elétrico: caixa de chapa com friso de aletas no alto e duas tampas."""
    half = length / 2
    plates.box(-half, 0.0, 0.0, half, 0.074, 0.155, "painted_metal")
    plates.box(-half - 0.012, 0.0, 0.0, -half, 0.080, 0.158, "painted_metal")
    plates.box(half, 0.0, 0.0, half + 0.012, 0.080, 0.158, "painted_metal")
    for k in range(5):
        plates.box(-half + 0.02, 0.074, 0.105 + k * 0.009, half - 0.02, 0.0765, 0.1105 + k * 0.009, "iron_black")
    plates.box(-half + 0.01, 0.074, 0.045, half - 0.01, 0.0755, 0.052, "iron_black")


def _electrical_panel(plates, turned, sites):
    """Quadro de luz da garagem: caixa de chapa com porta, trinco, etiqueta e eletroduto até o forro."""
    candidates = [s for s in sites if s.room_id == "garage" and s.piece.axis == "y" and abs(s.piece.pos - 12.0) < 1e-6]
    if not candidates:
        return
    site = max(candidates, key=lambda s: s.length)
    u = site.u0 + min(1.2, site.length * 0.4)
    z = 1.45
    with _place(plates, site, u, z), _place(turned, site, u, z):
        plates.box(-0.18, 0.0, -0.25, 0.18, 0.100, 0.25, "painted_metal")
        plates.box(-0.165, 0.100, -0.235, 0.165, 0.106, 0.235, "painted_metal")
        plates.box(-0.14, 0.106, 0.14, 0.14, 0.1068, 0.205, "plastic_white_aged")
        plates.box(0.1, 0.106, -0.04, 0.14, 0.116, 0.04, "steel_hardware")
        plates.box(-0.165, 0.106, -0.0016, 0.165, 0.1066, 0.0016, "iron_black")
        with turned.at(0.0, 0.05, 0.25):
            turned.tube((0.0, 0.0, 0.0), (0.0, 0.0, layout.CEIL_Z[0] - z - 0.25), 0.0135, "steel_hardware", 8)
            turned.lathe([(0.0, 0.0), (0.021, 0.0), (0.021, 0.03), (0.0, 0.03)], "steel_hardware", 8)


def _bath_fan(plates):
    """Exaustor do banheiro: grade quadrada no forro."""
    x, y, z = 11.0, 3.8, layout.CEIL_Z[1]
    with plates.at(x, y, z, rx=180):
        plates.box(-0.17, -0.17, 0.0, 0.17, 0.17, 0.012, "plastic_white_aged")
        plates.box(-0.14, -0.14, 0.012, 0.14, 0.14, 0.0135, "iron_black")
        for k in range(-3, 4):
            plates.box(-0.14, k * 0.036 - 0.004, 0.0135, 0.14, k * 0.036 + 0.004, 0.0165, "plastic_white_aged")
