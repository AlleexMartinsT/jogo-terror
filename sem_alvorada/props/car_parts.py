"""Peças soltas da parte externa do carro: para-choques, grade, faróis, lanternas, maçanetas, espelhos,
molduras, limpadores, antena e o fundo (escapamento, eixos).

Tudo é desenhado sem amassado, sobre a chapa lida do `.npz`; `car.py` aplica o amassado depois em tudo junto,
então a ponta do para-choque, a grade e o farol do lado do passageiro entortam com a carroceria.
As medidas vêm de `car_shape`, a mesma fonte do script que fez a chapa.
"""
import math

import numpy as np

from . import car_shape as shape
from .kit import MeshBuilder

CHROME, RUBBER, PLASTIC = "car_chrome", "car_rubber", "car_black_plastic"
BUMPER_Z = 0.385


def exterior_builder():
    """MeshBuilder com chanfro fino: as peças têm poucos milímetros e o padrão (4 mm) as engoliria."""
    from .. import craft
    m = MeshBuilder("Car_Exterior")
    m.finish = craft.Finish(bevel=0.0018, bevel_segments=1, bevel_angle=35.0, smooth_angle=48.0)
    return m


# --------------------------------------------------------------------------------------------
# Varredura de um perfil ao longo de uma curva (para-choques, molduras)
# --------------------------------------------------------------------------------------------
def sweep_xy(m, path, profile, mat, outward=1.0, closed=True):
    """Perfil [(n, z), ...] varrido ao longo de `path` [(x, y, z), ...].

    `n` é a distância ao longo da normal horizontal da curva (para fora, se `outward` = +1; para o outro lado se -1)
    e `z` o deslocamento vertical. O loft fecha as pontas e orienta as faces sozinho.
    """
    path = np.asarray(path, float)
    tangent = np.gradient(path[:, :2], axis=0)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    normal = outward * np.column_stack([-tangent[:, 1], tangent[:, 0]])
    rings = [[(p[0] + n_vec[0] * n, p[1] + n_vec[1] * n, p[2] + dz) for n, dz in profile] for p, n_vec in zip(path, normal)]
    m.loft(rings, mat, closed, closed, True)


def _bumper_path(sign, reach=0.90, wrap=0.38, steps=33, z=BUMPER_Z, y_center=2.342):
    xs = np.linspace(-reach, reach, steps)
    ys = sign * (y_center - wrap * (np.abs(xs) / reach) ** 3)
    return np.column_stack([xs, ys, np.full(steps, z)])


BUMPER_PROFILE = [(-0.012, -0.070), (0.030, -0.076), (0.058, -0.062), (0.068, -0.030), (0.068, 0.030), (0.058, 0.062),
                  (0.030, 0.076), (-0.012, 0.070)]
STRIP_PROFILE = [(0.064, -0.020), (0.078, -0.018), (0.081, 0.0), (0.078, 0.018), (0.064, 0.020)]


def bumper(m, sign):
    """Para-choque cromado com tira de borracha, suportes de amortecedor e saia plástica por baixo."""
    path = _bumper_path(sign)
    outward = sign
    sweep_xy(m, path, BUMPER_PROFILE, CHROME, outward)
    sweep_xy(m, _bumper_path(sign, reach=0.80, wrap=0.26, steps=25), STRIP_PROFILE, RUBBER, outward, closed=True)
    sweep_xy(m, _bumper_path(sign, reach=0.90, wrap=0.34, steps=25, z=0.255, y_center=2.265),
             [(-0.02, -0.055), (0.035, -0.055), (0.050, 0.0), (0.035, 0.055), (-0.02, 0.055)], PLASTIC, outward)
    for x in (-0.46, 0.46):
        m.tube((x, sign * 2.20, BUMPER_Z), (x, sign * 2.335, BUMPER_Z), 0.028, PLASTIC, seg=8)
        m.tube((x, sign * 2.28, BUMPER_Z), (x, sign * 2.332, BUMPER_Z), 0.036, CHROME, seg=8)


def license_plate(m, sign):
    """Placa: na frente, parafusada no para-choque; atrás, no vão da tampa do porta-malas."""
    if sign > 0:
        m.panel(0.0, 2.425, BUMPER_Z, 0.30, 0.15, "car_plate", "front")
        for x in (-0.12, 0.12):
            m.cylinder(x, 2.424, BUMPER_Z + 0.062, 0.008, 0.004, CHROME, seg=6)
    else:
        m.panel(0.0, -2.245, 0.72, 0.30, 0.15, "car_plate", "back")


# --------------------------------------------------------------------------------------------
# Frente: grade e faróis
# --------------------------------------------------------------------------------------------
def grille(m):
    """Grade de barras horizontais cromadas num bolsão preto, com moldura e emblema redondo."""
    m.box(0.0, 2.196, 0.548, 0.78, 0.008, 0.150, PLASTIC)
    for i in range(6):
        m.box(0.0, 2.224, 0.558 + i * 0.0245, 0.76, 0.012, 0.0095, CHROME)
    for x in (-0.19, 0.0, 0.19):
        m.box(x, 2.226, 0.552, 0.012, 0.016, 0.142, CHROME)
    m.box(0.0, 2.256, 0.545, 0.80, 0.012, 0.014, CHROME)
    m.box(0.0, 2.256, 0.686, 0.80, 0.012, 0.014, CHROME)
    for x in (-0.395, 0.395):
        m.box(x, 2.256, 0.545, 0.014, 0.012, 0.155, CHROME)
    with m.at(0.0, 2.238, 0.625, rx=-90):
        m.cylinder(0, 0, 0, 0.034, 0.012, CHROME, seg=16)
        m.cylinder(0, 0, 0.012, 0.022, 0.004, "car_rim", seg=16)


def _end_surface(x_lo, x_hi, z_lo, z_hi, sign, setback):
    """Superfície paramétrica que acompanha o canto arredondado da frente (sign=+1) ou da traseira (-1)."""
    def fn(u, v):
        x = x_lo + (x_hi - x_lo) * u
        return (x, sign * (float(shape.nose_y(x)) - setback), z_lo + (z_hi - z_lo) * v)
    return fn


def _lamp_surface(m, side, x_lo, x_hi, z_lo, z_hi, front, setback, mat, keep=None, cells=(10, 3)):
    """Uma lente curva que acompanha o canto, para o lado `side` (+1 passageiro, -1 motorista).

    `keep(i, j)` decide quais células existem: a lente do farol batido tem pedaços que faltam.
    """
    sign = 1.0 if front else -1.0
    base = _end_surface(x_lo, x_hi, z_lo, z_hi, sign, setback)
    nu, nv = cells

    def point(u, v):
        x, y, z = base(u, v)
        return (side * x, y, z)

    for i in range(nu):
        for j in range(nv):
            if keep is not None and not keep(i, j):
                continue
            quad = [point(i / nu, j / nv), point((i + 1) / nu, j / nv), point((i + 1) / nu, (j + 1) / nv), point(i / nu, (j + 1) / nv)]
            if side * sign < 0:
                quad = quad[::-1]
            m.quad(*quad, mat, uv=[(0, 0), (1, 0), (1, 1), (0, 1)])


def _broken_lens(i, j):
    """Lente do farol do passageiro: faltam os cacos do lado de fora e do alto, onde bateu."""
    return not ((i >= 6 and j >= 1) or (i == 4 and j == 2) or (i >= 8))


def headlight(m, side):
    """Farol retangular: placa preta, dois refletores cromados com lâmpada, lente de policarbonato nervurada
    e um pisca âmbar no canto."""
    x_lo, x_hi, z_lo, z_hi = 0.455, 0.870, 0.545, 0.695
    _lamp_surface(m, side, x_lo, x_hi, z_lo - 0.008, z_hi + 0.008, True, 0.052, PLASTIC)
    for x in (0.555, 0.690):
        y = float(shape.nose_y(x)) - 0.060
        with m.at(side * x, y, 0.620, rx=-90):
            m.lathe([(0.0, 0.0), (0.018, 0.006), (0.040, 0.020), (0.058, 0.042), (0.064, 0.050)], 0, 0, 0, CHROME, seg=20,
                    cap_bottom=False, cap_top=False)
            m.sphere(0, 0, 0.016, 0.013, "car_lens_glow", seg=8, rings=4)
    _lamp_surface(m, side, 0.775, x_hi, z_lo + 0.004, z_hi - 0.004, True, 0.030, "car_tail_amber")
    _lamp_surface(m, side, x_lo, x_hi, z_lo, z_hi, True, 0.014, "car_lens_clear", keep=_broken_lens if side > 0 else None)
    for z in (z_lo - 0.006, z_hi + 0.006):
        m.tube((side * x_lo, float(shape.nose_y(x_lo)) - 0.012, z), (side * 0.74, float(shape.nose_y(0.74)) - 0.012, z),
               0.0045, CHROME, seg=5)


def taillight(m, side):
    """Lanterna traseira: faixa vermelha larga em cima; embaixo âmbar (seta) e branco (ré)."""
    x_lo, x_hi = 0.485, 0.925
    _lamp_surface(m, side, x_lo, x_hi, 0.752, 0.898, False, 0.060, PLASTIC)
    _lamp_surface(m, side, x_lo, x_hi, 0.822, 0.896, False, 0.016, "car_tail_red")
    _lamp_surface(m, side, x_lo, 0.70, 0.754, 0.816, False, 0.016, "car_lens_clear")
    _lamp_surface(m, side, 0.70, x_hi, 0.754, 0.816, False, 0.016, "car_tail_amber")
    for z in (0.750, 0.819, 0.900):
        m.tube((side * x_lo, -(float(shape.nose_y(x_lo)) - 0.012), z), (side * 0.88, -(float(shape.nose_y(0.88)) - 0.012), z),
               0.0045, CHROME, seg=5)


# --------------------------------------------------------------------------------------------
# Laterais: maçanetas, espelhos, molduras, marcadores
# --------------------------------------------------------------------------------------------
def door_handles(m):
    for side in (-1, 1):
        for y in shape.HANDLE_Y:
            x = float(shape.side_x(y, 0.935)) - 0.022
            m.box(side * x, y, 0.926, 0.016, 0.108, 0.022, CHROME)
            m.cylinder(side * (x + 0.006), y - 0.062, 0.929, 0.0075, 0.016, CHROME, seg=6)
        lock_x = float(shape.side_x(shape.HANDLE_Y[0] + 0.14, 0.93))
        with m.at(side * lock_x, shape.HANDLE_Y[0] + 0.14, 0.93, ry=90 * side):
            m.cylinder(0, 0, 0, 0.011, 0.005, CHROME, seg=10)
            m.box(0, 0, 0.003, 0.002, 0.012, 0.003, PLASTIC)


def mirror(m, side, broken):
    """Espelho externo: haste cromada, carcaça preta e vidro. O do passageiro está rachado e dobrado para a frente."""
    base = np.array([side * 0.905, 0.80, 1.015])
    swing = -22.0 * side if broken else 0.0
    with m.at(*base, rz=swing):
        m.tube((0, 0, 0), (side * 0.085, 0.03, 0.050), 0.011, CHROME, seg=6)
        with m.at(side * 0.115, 0.04, 0.062):
            m.soft_box(0, 0, -0.055, 0.075, 0.17, 0.11, PLASTIC, radius=0.035, edge=0.02, corner_points=4)
            m.panel(0, -0.0865, 0.0, 0.15, 0.092, "mirror_cracked" if broken else "mirror_plain", "back")


def rub_strip(m):
    """Friso lateral preto com filete cromado, entre os arcos de roda."""
    ys = np.linspace(1.00, -1.00, 21)
    profile = [(-0.003, -0.036), (0.008, -0.034), (0.0135, -0.022), (0.0135, 0.022), (0.008, 0.034), (-0.003, 0.036)]
    for side in (-1, 1):
        rings = [[(side * (float(shape.side_x(y, 0.575)) + n), y, 0.575 + dz) for n, dz in profile] for y in ys]
        m.loft(rings, RUBBER, True, True, True)
        rings = [[(side * (float(shape.side_x(y, 0.575)) + n), y, 0.575 + dz) for n, dz in
                  [(0.012, -0.004), (0.0155, -0.0035), (0.0155, 0.0035), (0.012, 0.004)]] for y in ys]
        m.loft(rings, CHROME, True, True, False)


def belt_molding(m):
    """Filete cromado onde a cabine encontra a porta."""
    ys = np.linspace(0.84, -1.50, 24)
    for side in (-1, 1):
        rings = []
        for y in ys:
            x = float(shape.cabin_half_width(1.0) * shape.cabin_taper(y)) + 0.002
            rings.append([(side * (x + n), y, 0.998 + dz) for n, dz in [(0, -0.006), (0.010, -0.005), (0.010, 0.012), (0, 0.012)]])
        m.loft(rings, CHROME, True, True, False)


def window_trim(m):
    """Borracha em volta de cada vidro e cromado na soleira dos laterais."""
    for name, corners in shape.glass_polygons().items():
        corners = [np.asarray(c, float) for c in corners]
        centre = sum(corners) / 4.0
        normal = np.cross(corners[1] - corners[0], corners[3] - corners[0])
        normal /= np.linalg.norm(normal)
        if np.dot(normal, centre - np.array([0.0, centre[1], 1.1])) < 0:
            normal = -normal
        lifted = [c + normal * 0.020 for c in corners]
        for index in range(4):
            a, b = lifted[index], lifted[(index + 1) % 4]
            sill = name.startswith("side") and index == 0
            m.bar(tuple(a), tuple(b), 0.016 if not sill else 0.012, CHROME if sill else RUBBER)


def wipers(m):
    """Limpadores recolhidos na base do para-brisa: braço fino e palheta de borracha deitados sobre o vidro."""
    low_left, low_right, top_right, top_left = (np.asarray(c, float) for c in shape.glass_polygons()["windshield"])
    up = (top_left - low_left) / np.linalg.norm(top_left - low_left)
    normal = np.cross(low_right - low_left, up)
    normal /= np.linalg.norm(normal)
    if normal[2] < 0:
        normal = -normal

    def at(u, v):
        point = low_left + (low_right - low_left) * (u + 1) / 2 + up * v
        return tuple(point + normal * 0.014)

    for pivot_u, tip_u in ((-0.52, 0.02), (0.18, 0.74)):
        m.bar(at(pivot_u, 0.02), at(tip_u, 0.09), 0.010, PLASTIC)
        m.bar(at(pivot_u + 0.10, 0.075), at(tip_u + 0.02, 0.085), 0.008, RUBBER)
        m.cylinder(*at(pivot_u, 0.02)[:2], at(pivot_u, 0.02)[2] - 0.01, 0.016, 0.02, CHROME, seg=8)


def antenna(m):
    """Antena de mastro no para-lama traseiro, levemente inclinada para trás."""
    base = (0.80, -1.78, float(shape.hood_surface_z(0.80, -1.78)) - 0.018)
    m.cylinder(base[0], base[1], base[2], 0.020, 0.025, CHROME, seg=10, r_top=0.014)
    m.tube((base[0], base[1], base[2] + 0.02), (base[0], base[1] - 0.10, base[2] + 0.95), 0.0042, CHROME, seg=5, r_end=0.0022)
    m.sphere(base[0], base[1] - 0.10, base[2] + 0.955, 0.007, CHROME, seg=6, rings=4)


def markers(m):
    """Luzes de posição nos para-lamas (âmbar na frente, vermelha atrás) e a tampa do tanque."""
    for side in (-1, 1):
        for y, mat in ((1.98, "car_tail_amber"), (-2.00, "car_tail_red")):
            x = float(shape.side_x(y, 0.62))
            m.box(side * (x + 0.002), y, 0.595, 0.012, 0.075, 0.034, mat)
    x = float(shape.side_x(-1.80, 0.84))
    with m.at(-x, -1.80, 0.84, ry=-90):
        m.cylinder(0, 0, 0, 0.046, 0.006, CHROME, seg=16)
        m.cylinder(0, 0, 0.006, 0.030, 0.004, "car_rim", seg=12)


# --------------------------------------------------------------------------------------------
# Fundo
# --------------------------------------------------------------------------------------------
def exhaust_meshes():
    """Escapamento (cano até o silencioso e o rabicho que sai atrás do para-choque), já com material."""
    from .. import craft
    from . import materials
    pieces = [craft.tube_along([(-0.28, 1.15, 0.17), (-0.28, 0.2, 0.15), (-0.28, -0.8, 0.14), (-0.30, -1.55, 0.14)], 0.032),
              craft.tube_along([(-0.30, -2.05, 0.15), (-0.33, -2.25, 0.20), (-0.35, -2.37, 0.27)], 0.030)]
    for piece in pieces:
        piece.materials.append(materials.get("car_rim"))
    return pieces


def underbody(m):
    """Eixo de transmissão, eixo traseiro com diferencial, tanque, silencioso e braços da suspensão dianteira."""
    m.tube((0.0, 0.7, 0.19), (0.0, -1.35, 0.19), 0.038, PLASTIC, seg=8)
    m.tube((-0.60, -1.45, 0.33), (0.60, -1.45, 0.33), 0.045, PLASTIC, seg=8)
    m.sphere(0.0, -1.45, 0.32, 0.12, PLASTIC, seg=10, rings=6)
    m.soft_box(0.0, -1.75, 0.10, 0.80, 0.55, 0.14, PLASTIC, radius=0.05, edge=0.02)
    m.cylinder(-0.30, -1.80, 0.07, 0.085, 0.14, "car_rim", seg=12)
    for side in (-1, 1):
        m.bar((side * 0.40, 1.05, 0.24), (side * 0.72, 1.20, 0.30), 0.035, PLASTIC)
        m.bar((side * 0.40, 1.60, 0.24), (side * 0.72, 1.55, 0.30), 0.035, PLASTIC)


def build_exterior():
    """Todas as peças externas num MeshBuilder."""
    m = exterior_builder()
    for sign in (1, -1):
        bumper(m, sign)
        license_plate(m, sign)
    grille(m)
    for side in (-1, 1):
        headlight(m, side)
        taillight(m, side)
        mirror(m, side, broken=side > 0)
    door_handles(m)
    rub_strip(m)
    belt_molding(m)
    window_trim(m)
    wipers(m)
    antenna(m)
    markers(m)
    underbody(m)
    return m
