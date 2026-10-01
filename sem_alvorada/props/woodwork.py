"""Marcenaria dos cômodos de cima: gavetas e portas almofadadas, puxadores, pernas e pés torneados, molduras.

Todas desenham num `MeshBuilder` já em andamento, nas coordenadas locais do móvel (frente = +Y, base em Z=0).
O veio da madeira corre ao longo do eixo U do material; peças verticais usam a variante `_v` (veio girado).
"""
import math

from .assembly import segments

FINE = 0.004


def wood_pair(kind):
    """(material com veio horizontal, material com veio vertical) de uma madeira ou tinta, ex.: 'up_walnut'."""
    return kind, f"{kind}_v"


def _profile(points, height, base_radius=1.0):
    """Perfil de torneado dado em frações: (raio relativo, altura relativa) -> (raio, z) em metros."""
    return [(radius * base_radius, z * height) for radius, z in points]


# perfis (raio em metros, altura relativa 0..1) de peças torneadas
POST_PROFILE = [(0.036, 0.0), (0.036, 0.05), (0.026, 0.07), (0.026, 0.09), (0.040, 0.12), (0.040, 0.16), (0.028, 0.19),
                (0.026, 0.62), (0.036, 0.65), (0.036, 0.69), (0.026, 0.72), (0.030, 0.76), (0.040, 0.82), (0.040, 0.88),
                (0.030, 0.94), (0.016, 0.98), (0.0, 1.0)]
LEG_PROFILE = [(0.030, 0.0), (0.026, 0.03), (0.030, 0.07), (0.021, 0.12), (0.021, 0.52), (0.027, 0.56), (0.027, 0.62),
               (0.020, 0.66), (0.022, 1.0)]
TURNED_FOOT = [(0.034, 0.0), (0.034, 0.15), (0.024, 0.30), (0.030, 0.45), (0.026, 0.70), (0.034, 1.0)]
BALL_FINIAL = [(0.0, 0.0), (0.020, 0.10), (0.026, 0.35), (0.022, 0.62), (0.012, 0.85), (0.0, 1.0)]
KNOB_PROFILE = [(0.0, 0.0), (0.010, 0.0), (0.0075, 0.004), (0.007, 0.012), (0.014, 0.018), (0.016, 0.026), (0.012, 0.034),
                (0.0, 0.036)]


def turned(m, x, y, z0, profile, height, mat, seg=18, radius_scale=1.0):
    """Peça torneada (pé de cama, perna de mesa) revolucionada em Z; `profile` em frações da altura."""
    m.lathe(_profile(profile, height, radius_scale), x, y, z0, mat, seg=segments(seg), smooth=True)


def knob(m, cx, y, cz, mat="brass", scale=1.0):
    """Puxador de bola apontando para +Y, saindo de uma frente em `y`."""
    with m.at(cx, y, cz, rx=-90):
        m.lathe([(r * scale, z * scale) for r, z in KNOB_PROFILE], 0, 0, 0, mat, seg=segments(12), smooth=True)


def pull(m, cx, y, cz, length, mat="brass", vertical=False):
    """Puxador de barra com dois suportes, saindo para +Y."""
    half = length / 2
    with m.at(cx, y, cz, ry=90 if vertical else 0):
        for sign in (-1, 1):
            with m.at(sign * (half - 0.012), 0, 0, rx=-90):
                m.cylinder(0, 0, 0, 0.0045, 0.022, mat, seg=segments(8))
        m.tube((-half, 0.022, 0), (half, 0.022, 0), 0.0055, mat, seg=segments(10), smooth=True)


def framed_panel(m, cx, y, z0, width, height, frame_mat, panel_mat, *, depth=0.022, frame=0.034, recess=0.008,
                 frame_mat_v=None, raised=False):
    """Frente almofadada: moldura de quatro barras com um painel afundado (ou saliente, `raised`).

    `y` é o plano de trás da frente; ela avança `depth` para +Y. Gavetas, portas e painéis de cabeceira.
    """
    frame_mat_v = frame_mat_v or frame_mat
    inner_w, inner_h = width - 2 * frame, height - 2 * frame
    m.box(cx, y + depth / 2, z0, width, depth, frame, frame_mat)
    m.box(cx, y + depth / 2, z0 + height - frame, width, depth, frame, frame_mat)
    for sign in (-1, 1):
        m.box(cx + sign * (width - frame) / 2, y + depth / 2, z0 + frame, frame, depth, inner_h, frame_mat_v)
    back = y + 0.004
    front = y + depth + (recess if raised else -recess)
    m.box(cx, (back + front) / 2, z0 + frame - 0.002, inner_w + 0.004, front - back, inner_h + 0.004, panel_mat)


def molding(m, x0, x1, y, z, mat, *, drop=0.03, out=0.025):
    """Moldura de coroamento corrida em X: perfil em ogiva (sai da parede e volta). Frente em +Y."""
    profile = [(y, z - drop), (y + out * 0.35, z - drop * 0.75), (y + out, z - drop * 0.30), (y + out, z), (y, z)]
    m.extrude(profile, "yz", x0, x1, mat)


def plinth(m, cx, cy, width, depth, height, mat):
    """Rodapé recuado sob um móvel: caixa um pouco menor que o corpo."""
    m.box(cx, cy, 0, width, depth, height, mat)


def hanging_ring(m, cx, cy, z, radius, mat="brass"):
    m.torus(cx, cy, z, radius, 0.0025, mat, seg=segments(14), seg_minor=5, rx=90)
