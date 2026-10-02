"""Calhas e condutores: calha K de alumínio com ganchos, condutor retangular com cotovelos e bloco de respingo.

A calha cai de leve para o lado do condutor (3 cm em 10 m), tem pontas tampadas e uma boca no lugar do tubo.
"""
import math

import numpy as np

from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401

GUTTER = "ext_gutter"
FALL = 0.035


def _thick(path, thickness):
    """Contorno fechado de uma chapa fina: a polilinha `path` engrossada de `thickness` para os dois lados."""
    pts = np.asarray(path, float)
    tangent = np.gradient(pts, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    normal = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    left = pts + normal * thickness
    right = pts - normal * thickness
    return [tuple(p) for p in np.concatenate([left, right[::-1]])]


# Linha média da calha K, em (para fora da fascia, altura a partir do topo da calha); o topo de trás fica na fascia.
K_STYLE = [(0.0, 0.0), (0.0, -0.092), (0.008, -0.102), (0.075, -0.102), (0.092, -0.094), (0.094, -0.062), (0.078, -0.054),
           (0.090, -0.034), (0.104, -0.014), (0.110, 0.0)]


def gutter_run(m, x0, x1, y_fascia, outward, z_top, down_to_x1=True):
    """Calha ao longo de X na fascia que está em `y_fascia`, com `outward` = -1 (frente) ou +1 (fundos)."""
    profile = _thick(K_STYLE, 0.0012)
    xs = np.linspace(x0, x1, 14)
    drop = FALL * (xs - x0) / (x1 - x0) if down_to_x1 else FALL * (x1 - xs) / (x1 - x0)
    path = [(x, y_fascia + outward * 0.02, z_top - d) for x, d in zip(xs, drop)]
    # o lado do perfil (tangente x Z) aponta para -Y: na frente isso já é "para fora"
    ext.sweep_profile(m, path, [(-outward * a, b) for a, b in profile], GUTTER, up=(0, 0, 1))
    for x in np.arange(x0 + 0.4, x1 - 0.2, 0.62):                       # ganchos
        t = (x - x0) / (x1 - x0)
        z = z_top - FALL * (t if down_to_x1 else 1.0 - t)
        m.bar((x, y_fascia + outward * 0.115, z - 0.002), (x, y_fascia + outward * 0.006, z - 0.045), 0.012, GUTTER)


def downspout(m, x, y_gutter, outward, z_outlet, wall_y, ground=0.0):
    """Condutor: desce da boca da calha, vai até a parede num cotovelo duplo, desce rente a ela e solta no chão."""
    face = wall_y + outward * (layout.WALL_T_EXT / 2 + 0.045)
    start_y = y_gutter + outward * 0.06
    path = [(x, start_y, z_outlet), (x, start_y, z_outlet - 0.25)]
    mid = z_outlet - 0.25 - abs(start_y - face) * 0.9
    path += [(x, (start_y + face) / 2, (z_outlet - 0.25 + mid) / 2), (x, face, mid), (x, face, ground + 0.55),
             (x, face + outward * 0.04, ground + 0.30), (x, face + outward * 0.22, ground + 0.16)]
    profile = [(-0.0325, -0.0425), (0.0325, -0.0425), (0.0325, 0.0425), (-0.0325, 0.0425)]
    smooth_path = _smooth(path)
    ext.sweep_profile(m, smooth_path, [(a, b) for a, b in profile], GUTTER, up=(1, 0, 0))
    for z in (ground + 1.4, ground + 3.0):
        if z < z_outlet - 0.6:
            m.box(x, face - outward * 0.02, z, 0.085, 0.04, 0.03, "metal")
    m.box(x, face + outward * 0.36, ground - 0.02, 0.28, 0.4, 0.07, "concrete")           # bloco de respingo


def _smooth(path, passes=2):
    pts = np.asarray(path, float)
    for _ in range(passes):
        mid = (pts[:-1] + pts[1:]) / 2
        interleaved = np.empty((len(pts) + len(mid), 3))
        interleaved[0::2], interleaved[1::2] = pts, mid
        pts = interleaved
    return [tuple(p) for p in pts]


def build(ctx, main, garage):
    ext.start(ctx)
    m = ext.builder("Roof_Gutters", ext.FINE)
    for shape, spans in ((main, (main.deck_x0, main.deck_x1)), (garage, (garage.deck_x0, garage.deck_x1))):
        o = shape.overhang
        for wall_y, outward in ((shape.wall_y0, -1), (shape.wall_y1, 1)):
            edge_y = wall_y + outward * o
            z_top = shape.top_z(edge_y) + 0.03 - 0.02
            gutter_run(m, spans[0], spans[1], edge_y + outward * 0.014, outward, z_top, down_to_x1=shape is garage)
    front, back = main.overhang, main.overhang
    z_main = main.top_z(-front) + 0.01 - 0.10
    downspout(m, main.deck_x0 + 0.35, -main.overhang, -1, z_main, 0.0)
    downspout(m, main.deck_x1 - 0.30, main.wall_y1 + main.overhang, 1, main.top_z(main.wall_y1 + main.overhang) - 0.10 - FALL, 10.0)
    z_garage = garage.top_z(-garage.overhang) - 0.10 - FALL
    downspout(m, garage.deck_x1 - 0.3, -garage.overhang, -1, z_garage, 0.0)
    downspout(m, garage.deck_x1 - 0.3, garage.wall_y1 + garage.overhang, 1, z_garage, garage.wall_y1)
    ext.emit(ctx, m)
