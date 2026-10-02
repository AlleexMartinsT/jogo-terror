"""Cerca de ripas do terreno: mourões de 2,4 em 2,4 m com capuz, duas travessas por dentro, ripas de ponta bicuda
uma a uma (algumas faltam, outras estão quebradas ou tortas) e o portão duplo da frente, aberto e caído.
"""
import math

from . import ext_common as ext
from . import ext_materials  # noqa: F401

GROUND_Z = -0.12
LOT_WEST_X, LOT_EAST_X, LOT_BACK_Y, FRONT_Y = -6.0, 21.5, 16.0, -5.4
GATE_LEFT, GATE_RIGHT = 5.0, 8.0
RUNS = [("x", FRONT_Y, LOT_WEST_X, GATE_LEFT), ("x", FRONT_Y, GATE_RIGHT, 12.9), ("y", LOT_WEST_X, FRONT_Y, LOT_BACK_Y),
        ("x", LOT_BACK_Y, LOT_WEST_X, LOT_EAST_X), ("y", LOT_EAST_X, 8.0, LOT_BACK_Y)]
INNER = {("x", FRONT_Y): 1.0, ("x", LOT_BACK_Y): -1.0, ("y", LOT_WEST_X): 1.0, ("y", LOT_EAST_X): -1.0}
PICKET_WIDTH, PICKET_PITCH, PICKET_THICK = 0.09, 0.135, 0.02
POST_SPACING = 2.4
MAT = "fence_wood"


def _profile(height):
    """Contorno da ripa de frente: topo em ponta com ombros."""
    shoulder = height - 0.06
    return [(-PICKET_WIDTH / 2, 0.0), (PICKET_WIDTH / 2, 0.0), (PICKET_WIDTH / 2, shoulder), (0.0, height), (-PICKET_WIDTH / 2, shoulder)]


def _picket(m, axis, fixed, u, height, lean=0.0, broken=False):
    """Uma ripa em `u` ao longo da cerca, no plano `fixed`. `lean` (graus) a inclina no plano da cerca."""
    x, y = (u, fixed) if axis == "x" else (fixed, u)
    plane = "xz" if axis == "x" else "yz"
    tilt = {"ry": lean} if axis == "x" else {"rx": lean}
    with m.at(x, y, GROUND_Z, **tilt):
        if broken:
            m.extrude([(-PICKET_WIDTH / 2, 0.0), (PICKET_WIDTH / 2, 0.0), (PICKET_WIDTH / 2, height * 0.45), (-0.01, height * 0.52),
                       (-PICKET_WIDTH / 2, height * 0.4)], plane, -PICKET_THICK / 2, PICKET_THICK / 2, MAT)
        else:
            m.extrude(_profile(height), plane, -PICKET_THICK / 2, PICKET_THICK / 2, MAT)


def _post(m, axis, fixed, u, height=1.18):
    x, y = (u, fixed) if axis == "x" else (fixed, u)
    m.box(x, y, GROUND_Z, 0.11, 0.11, height, MAT)
    m.frustum(x, y, GROUND_Z + height, 0.13, 0.13, 0.04, 0.04, 0.06, MAT)


def _rails(m, axis, fixed, a, b, inner):
    side = fixed + inner * (PICKET_THICK / 2 + 0.022)
    for z in (GROUND_Z + 0.26, GROUND_Z + 0.72):
        if axis == "x":
            m.box((a + b) / 2, side, z, b - a, 0.045, 0.085, MAT)
        else:
            m.box(side, (a + b) / 2, z, 0.045, b - a, 0.085, MAT)


def _run(m, rng, axis, fixed, a, b):
    inner = INNER[(axis, fixed)]
    count = max(2, round((b - a) / POST_SPACING))
    for k in range(count + 1):
        _post(m, axis, fixed, a + (b - a) * k / count)
    _rails(m, axis, fixed, a, b, inner)
    u = a + PICKET_PITCH / 2
    while u < b:
        roll = rng.random()
        if roll < 0.06:
            pass                                                         # ripa que caiu
        else:
            height = 0.98 + rng.random() * 0.06
            if roll < 0.12:
                _picket(m, axis, fixed, u, height, broken=True)
            else:
                lean = rng.uniform(-9, 9) if roll < 0.20 else rng.uniform(-1.2, 1.2)
                _picket(m, axis, fixed, u + rng.uniform(-0.01, 0.01), height, lean)
        u += PICKET_PITCH


def _leaf(m, rng, length, sag):
    """Folha do portão em coordenadas locais (dobradiça na origem, abre para +X): moldura, ripas e a mão-francesa."""
    height = 1.0
    m.box(length / 2, 0.0, GROUND_Z + 0.12, length, 0.04, 0.08, MAT)
    m.box(length / 2, 0.0, GROUND_Z + height - 0.2, length, 0.04, 0.08, MAT)
    for x in (0.05, length - 0.05):
        m.box(x, 0.0, GROUND_Z + 0.04, 0.09, 0.05, height, MAT)
    m.bar((0.1, 0.0, GROUND_Z + 0.2), (length - 0.1, 0.0, GROUND_Z + height - 0.25), 0.07, MAT)
    u = 0.14
    while u < length - 0.1:
        if rng.random() > 0.08:
            with m.at(u, 0.03, GROUND_Z + 0.04):
                m.extrude(_profile(height - 0.04 + rng.uniform(-0.02, 0.03)), "xz", -PICKET_THICK / 2, PICKET_THICK / 2, MAT)
        u += PICKET_PITCH
    for z in (GROUND_Z + 0.16, GROUND_Z + height - 0.16):
        m.box(0.05, -0.04, z, 0.06, 0.03, 0.02, "iron_black")


def _gate(m, rng):
    """Dois mourões altos e duas folhas: a da esquerda aberta, a da direita com a dobradiça de baixo solta."""
    for x in (GATE_LEFT, GATE_RIGHT):
        m.box(x, FRONT_Y, GROUND_Z, 0.15, 0.15, 1.35, MAT)
        m.frustum(x, FRONT_Y, GROUND_Z + 1.35, 0.18, 0.18, 0.06, 0.06, 0.08, MAT)
    half = (GATE_RIGHT - GATE_LEFT) / 2 - 0.1
    with m.at(GATE_LEFT + 0.09, FRONT_Y, 0.0, rz=34):
        _leaf(m, rng, half, 0.0)
    with m.at(GATE_RIGHT - 0.09, FRONT_Y, 0.0, rz=-7, rx=3.5):
        with m.at(0, 0, 0, rz=180):
            _leaf(m, rng, half, 0.0)
    m.box((GATE_LEFT + GATE_RIGHT) / 2, FRONT_Y + 0.4, GROUND_Z, 0.05, 0.05, 0.02, "iron_black")


def build(ctx):
    ext.start(ctx)
    rng = ext.rng_for(ctx, "fence")
    m = ext.builder("Fence", ext.PROFILED)
    for axis, fixed, a, b in RUNS:
        _run(m, rng, axis, fixed, a, b)
    _gate(m, rng)
    ext.emit(ctx, m)
