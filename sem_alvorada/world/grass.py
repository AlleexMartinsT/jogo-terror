"""Capim morto: tufos de lâminas finas e tortas espalhados pelo gramado, mais altos junto da cerca e da casa.

Cada lâmina é um quadrilátero e um triângulo (dobrados no meio), com UV que guarda o tom sorteado (u) e a
altura relativa (v) para o material pintar do pé escuro à ponta de palha.
"""
import math

from .. import layout
from . import ext_common as ext
from . import ext_materials  # noqa: F401

GROUND_Z = -0.12
# Regiões de gramado: (x0, y0, x1, y1). A frente e os fundos são largos; as laterais, estreitas.
LAWNS = [(-6.0, -5.4, 13.2, -0.2), (17.8, -5.4, 21.5, -0.2), (-6.0, -0.2, -0.2, 16.0), (-0.2, 10.2, 21.5, 16.0),
         (12.2, 7.2, 21.5, 10.2), (18.8, -0.2, 21.5, 7.2)]
KEEP_OUT = [(5.2, -5.4, 7.8, 0.0), (0.7, -1.15, 5.2, -0.30), (8.1, -1.15, 11.7, -0.30), (3.6, 10.2, 5.0, 11.6)]


def _blocked(x, y):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in KEEP_OUT)


def _blade(m, rng, x, y, height, lean):
    width = rng.uniform(0.007, 0.013)
    tone = rng.random()
    dx, dy = math.cos(lean), math.sin(lean)
    px, py = -dy * width, dx * width
    base_l, base_r = (x - px, y - py, GROUND_Z), (x + px, y + py, GROUND_Z)
    reach = height * rng.uniform(0.25, 0.55)
    mid = (x + dx * reach * 0.4, y + dy * reach * 0.4, GROUND_Z + height * 0.55)
    tip = (x + dx * reach, y + dy * reach, GROUND_Z + height - 0.03 * rng.random())
    mid_l, mid_r = (mid[0] - px * 0.7, mid[1] - py * 0.7, mid[2]), (mid[0] + px * 0.7, mid[1] + py * 0.7, mid[2])
    m.quad(base_l, base_r, mid_r, mid_l, "ext_grass", uv=[(tone, 0.0), (tone, 0.0), (tone, 0.5), (tone, 0.5)])
    m.poly([mid_l, mid_r, tip], "ext_grass", uv=[(tone, 0.5), (tone, 0.5), (tone, 1.0)])


def _tuft(m, rng, x, y, tall):
    for _ in range(rng.randint(5, 9)):
        r, a = rng.uniform(0.0, 0.07), rng.uniform(0, 2 * math.pi)
        height = rng.uniform(0.10, 0.28) * (2.2 if tall and rng.random() < 0.5 else 1.0)
        _blade(m, rng, x + r * math.cos(a), y + r * math.sin(a), height, rng.uniform(0, 2 * math.pi))


def build(ctx):
    ext.start(ctx)
    rng = ext.rng_for(ctx, "grass")
    m = ext.builder("Grass_Tufts", ext.PROFILED)
    density = 2.0 * {"low": 0.5, "medium": 1.0, "high": 1.4}.get(ctx.quality, 1.0)
    for x0, y0, x1, y1 in LAWNS:
        for _ in range(int((x1 - x0) * (y1 - y0) * density)):
            x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
            if _blocked(x, y):
                continue
            near_edge = min(x - x0, x1 - x, y - y0, y1 - y) < 0.6
            _tuft(m, rng, x, y, near_edge)
    ext.emit(ctx, m)
