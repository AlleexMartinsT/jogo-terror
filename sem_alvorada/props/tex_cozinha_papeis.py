"""Papéis da cozinha: desenhos da Emma na geladeira, post-its, calendário parado e mostrador do relógio.

Desenhados com o `Canvas` do pacote (retângulos, elipses, linhas) em resolução maior que a das primeiras
texturas (128 a 192 px), para o traço de giz de cera aparecer de perto. A fonte só tem maiúsculas e sem acento.
"""
import math

import numpy as np

from . import textures
from .textures import Canvas
from .tex_ruido import stamp_text

PAPER = (0.86, 0.84, 0.76)
BLACK_INK = (0.07, 0.07, 0.09, 1.0)
BLUE_INK = (0.14, 0.18, 0.50, 1.0)


def _rng_for(name):
    import zlib
    return np.random.default_rng(zlib.crc32(f"kgp:{name}".encode("utf-8")))


def _paper(width, height, color, name, fiber=0.025):
    """Folha com fibras: ruído de luminância por pixel feito em numpy (o `grain` do Canvas usa laço Python)."""
    canvas = Canvas(width, height, (*color, 1.0))
    noise = _rng_for(name).normal(0.0, 1.0, (height, width, 1)).astype(np.float32)
    canvas.px[..., :3] *= 1 + fiber * noise
    return canvas


def _crayon(canvas, rng, points, color, width=2.6):
    """Traço de giz: poligonal com tremor, para não parecer régua."""
    wobble = [(x + rng.normal(0, 0.7), y + rng.normal(0, 0.7)) for x, y in points]
    for a, b in zip(wobble, wobble[1:]):
        canvas.line(*a, *b, (*color, 0.92), width)


def _hatch(canvas, rng, x0, y0, x1, y1, color, spacing=2.6, width=2.0):
    """Preenchimento por hachuras diagonais irregulares (giz pressionado), recortadas ao retângulo."""
    reach = y1 - y0
    x = x0 - reach
    while x < x1:
        start_x, start_y = x, y0
        if start_x < x0:
            start_y += x0 - start_x
            start_x = x0
        end_x, end_y = x + reach, y1
        if end_x > x1:
            end_y -= end_x - x1
            end_x = x1
        if end_y > start_y:
            canvas.line(start_x, start_y, end_x, end_y + rng.uniform(-0.6, 0.6), (*color, 0.85), width)
        x += spacing


def _smile(canvas, rng, cx, cy, radius, color=BLACK_INK[:3]):
    points = [(cx + radius * math.cos(math.radians(a)), cy + radius * 0.6 * math.sin(math.radians(a)))
              for a in range(20, 161, 20)]
    _crayon(canvas, rng, points, color, 1.6)


def _stick_figure(canvas, rng, x, y, height, color, skirt=False):
    """Boneco palito de criança: cabeça redonda com sorriso, tronco, braços abertos e pernas."""
    head = height * 0.16
    canvas.ellipse(x, y + head, head, head, (0.95, 0.80, 0.65, 1.0))
    _smile(canvas, rng, x, y + head * 1.05, head * 0.55)
    body_top, body_bottom = y + head * 2, y + height * 0.62
    if skirt:
        canvas.polygon([(x, body_top), (x - head * 1.5, body_bottom), (x + head * 1.5, body_bottom)], (*color, 0.9))
    else:
        _crayon(canvas, rng, [(x, body_top), (x, body_bottom)], color, 3.0)
    _crayon(canvas, rng, [(x - head * 2.2, body_top + height * 0.14), (x, body_top + 2), (x + head * 2.2, body_top + height * 0.14)],
            color, 2.2)
    _crayon(canvas, rng, [(x - head * 1.1, y + height), (x, body_bottom), (x + head * 1.1, y + height)], color, 2.4)


def drawing_house(width=128, height=160):
    """Casa vermelha, sol de raios compridos, árvore, um gato laranja e a menina de mãos dadas com o gato."""
    rng = np.random.default_rng(11)
    canvas = _paper(width, height, PAPER, "house")
    canvas.ellipse(width * 0.2, height * 0.16, 17, 17, (0.98, 0.80, 0.10, 1.0))
    for index in range(12):
        angle = index * math.tau / 12
        _crayon(canvas, rng, [(width * 0.2 + 20 * math.cos(angle), height * 0.16 + 20 * math.sin(angle)),
                              (width * 0.2 + 33 * math.cos(angle), height * 0.16 + 33 * math.sin(angle))], (0.98, 0.75, 0.08), 2.4)
    _hatch(canvas, rng, 4, height * 0.78, width - 4, height - 8, (0.35, 0.65, 0.25), 2.8)
    _hatch(canvas, rng, 30, height * 0.42, 92, height * 0.78, (0.78, 0.20, 0.16), 2.6)
    canvas.polygon([(24, height * 0.43), (61, height * 0.24), (98, height * 0.43)], (0.52, 0.28, 0.18, 1.0))
    canvas.rect(52, height * 0.58, 70, height * 0.78, (0.30, 0.20, 0.14, 1.0))
    for wx in (36, 78):
        canvas.rect(wx, height * 0.48, wx + 14, height * 0.55, (0.60, 0.80, 0.95, 1.0))
    canvas.rect(104, height * 0.52, 108, height * 0.78, (0.40, 0.25, 0.12, 1.0))
    canvas.ellipse(106, height * 0.46, 15, 17, (0.20, 0.55, 0.22, 1.0))
    canvas.ellipse(112, height * 0.84, 9, 6, (0.95, 0.50, 0.12, 1.0))
    canvas.polygon([(105, height * 0.80), (108, height * 0.77), (110, height * 0.80)], (0.95, 0.50, 0.12, 1.0))
    stamp_text(canvas, 10, height - 14, "EMMA 7", (0.72, 0.18, 0.55, 1.0), 1)
    return canvas


def drawing_family(width=128, height=160):
    """A família de mãos dadas: pai alto, mãe e a Emma pequena no meio, sob um sol sorridente."""
    rng = np.random.default_rng(23)
    canvas = _paper(width, height, (0.90, 0.88, 0.80), "family")
    canvas.ellipse(width * 0.5, height * 0.14, 15, 15, (0.98, 0.80, 0.10, 1.0))
    _smile(canvas, rng, width * 0.5, height * 0.15, 8)
    _hatch(canvas, rng, 4, height * 0.80, width - 4, height - 6, (0.35, 0.62, 0.25), 2.8)
    _stick_figure(canvas, rng, 24, height * 0.30, height * 0.50, (0.15, 0.25, 0.65))
    _stick_figure(canvas, rng, 64, height * 0.45, height * 0.36, (0.80, 0.20, 0.55), skirt=True)
    _stick_figure(canvas, rng, 104, height * 0.27, height * 0.53, (0.80, 0.30, 0.12), skirt=True)
    stamp_text(canvas, 18, height - 18, "NOS 3", (0.75, 0.20, 0.20, 1.0), 2)
    return canvas


def _postit(name, color, lines, ink):
    canvas = _paper(112, 112, color, name, 0.02)
    canvas.rect(0, 0, 112, 5, (*(min(1.0, c + 0.06) for c in color), 0.7))
    for index, (text, scale) in enumerate(lines):
        stamp_text(canvas, 7, 12 + index * 20, text, ink, scale, spacing=1)
    return canvas


def postit_remedio():
    return _postit("remedio", (0.97, 0.88, 0.34), [("TOMA O", 2), ("REMEDIO", 2), ("L.", 2)], BLUE_INK)


def postit_doutor():
    return _postit("doutor", (0.95, 0.55, 0.62), [("DR MILLS", 2), ("QUINTA", 2), ("15H", 2)], BLACK_INK)


def calendar_stopped(width=128, height=176):
    """Calendário de brinde da farmácia: setembro riscado até o dia 8 e o dia 9 circulado em vermelho. Depois, nada."""
    canvas = _paper(width, height, (0.88, 0.86, 0.78), "calendar", 0.02)
    canvas.rect(0, 0, width, 70, (0.30, 0.38, 0.22, 1.0))
    canvas.polygon([(0, 70), (width * 0.3, 40), (width * 0.55, 56), (width * 0.8, 30), (width, 50), (width, 70)],
                   (0.55, 0.45, 0.20, 1.0))
    canvas.ellipse(width * 0.78, 22, 11, 11, (0.9, 0.55, 0.15, 1.0))
    canvas.rect(0, 70, width, 86, (0.62, 0.20, 0.16, 1.0))
    stamp_text(canvas, int((width - canvas.text_width("SETEMBRO", 1)) / 2), 74, "SETEMBRO", (0.95, 0.92, 0.85, 1.0), 1)
    cell_w, top = width / 7, 94
    for index, letter in enumerate("DSTQQSS"):
        stamp_text(canvas, int(index * cell_w + cell_w / 2 - 2), top, letter, (0.55, 0.15, 0.12, 1.0), 1)
    day = 1
    for row in range(5):
        for column in range(7):
            if row == 0 and column < 1 or day > 30:
                continue
            cx, cy = column * cell_w + cell_w / 2, top + 20 + row * 14
            stamp_text(canvas, int(cx - 3 * (1 + (day >= 10))), int(cy - 3), str(day), (0.12, 0.12, 0.14, 1.0), 1)
            if day <= 8:
                canvas.line(cx - 7, cy - 6, cx + 7, cy + 6, (0.5, 0.05, 0.05, 0.9), 1.2)
                canvas.line(cx - 7, cy + 6, cx + 7, cy - 6, (0.5, 0.05, 0.05, 0.9), 1.2)
            if day == 9:
                for angle in range(0, 360, 20):
                    a, b = math.radians(angle), math.radians(angle + 22)
                    canvas.line(cx + 9 * math.cos(a), cy + 8 * math.sin(a), cx + 9 * math.cos(b), cy + 8 * math.sin(b),
                                (0.75, 0.06, 0.06, 1.0), 1.6)
            day += 1
    return canvas


def clock_face(size=128):
    """Mostrador de relógio de parede: branco amarelado, algarismos e marcas, sem ponteiros (são geometria)."""
    canvas = _paper(size, size, (0.80, 0.78, 0.68), "clock", 0.02)
    centre = size / 2
    canvas.ellipse(centre, centre, centre - 2, centre - 2, (0.84, 0.82, 0.72, 1.0))
    for mark in range(60):
        angle = math.radians(mark * 6 - 90)
        inner = centre * (0.84 if mark % 5 == 0 else 0.90)
        canvas.line(centre + inner * math.cos(angle), centre + inner * math.sin(angle),
                    centre + centre * 0.95 * math.cos(angle), centre + centre * 0.95 * math.sin(angle),
                    (0.1, 0.1, 0.1, 1.0), 2.0 if mark % 5 == 0 else 1.0)
    for number, label in ((12, "12"), (3, "3"), (6, "6"), (9, "9")):
        angle = math.radians(number * 30 - 90)
        x, y = centre + centre * 0.66 * math.cos(angle), centre + centre * 0.66 * math.sin(angle)
        stamp_text(canvas, int(x - canvas.text_width(label, 2) / 2), int(y - 7), label, (0.1, 0.1, 0.1, 1.0), 2)
    return canvas


def label(name, band, title, subtitle, width=256, height=96):
    """Rótulo de lata ou frasco que dá a volta: faixa colorida em cima e embaixo, nome do produto e letras miúdas."""
    canvas = _paper(width, height, (0.84, 0.82, 0.74), name, 0.03)
    canvas.rect(0, 0, width, height * 0.22, (*band, 1.0))
    canvas.rect(0, height * 0.82, width, height, (*band, 1.0))
    for repeat in range(2):
        x = repeat * width / 2 + width / 4 - canvas.text_width(title, 2) / 2
        stamp_text(canvas, int(x), int(height * 0.36), title, (0.08, 0.08, 0.10, 1.0), 2)
        sub_x = repeat * width / 2 + width / 4 - canvas.text_width(subtitle, 1) / 2
        stamp_text(canvas, int(sub_x), int(height * 0.64), subtitle, (0.2, 0.2, 0.22, 1.0), 1)
    rng = _rng_for(name)
    for _ in range(40):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        canvas.rect(x, y, x + rng.uniform(1, 3), y + rng.uniform(1, 4), (0.25, 0.22, 0.18, 0.35))
    return canvas


TEXTURES = {
    "kg_label_blue": lambda rng: label("kg_label_blue", (0.15, 0.30, 0.62), "TINTA", "ACRILICA FOSCA 3.6L"),
    "kg_label_green": lambda rng: label("kg_label_green", (0.18, 0.45, 0.25), "VERNIZ", "BRILHANTE 3.6L"),
    "kg_label_red": lambda rng: label("kg_label_red", (0.62, 0.15, 0.12), "ESMALTE", "SINTETICO 3.6L"),
    "kg_label_oil": lambda rng: label("kg_label_oil", (0.10, 0.10, 0.12), "OLEO 10W40", "MOTOR 1L"),
    "kg_label_soap": lambda rng: label("kg_label_soap", (0.20, 0.55, 0.28), "DETERGENTE", "NEUTRO 500ML"),
    "kg_drawing_house": lambda rng: drawing_house(),
    "kg_drawing_family": lambda rng: drawing_family(),
    "kg_postit_remedio": lambda rng: postit_remedio(),
    "kg_postit_doutor": lambda rng: postit_doutor(),
    "kg_calendar": lambda rng: calendar_stopped(),
    "kg_clock_face": lambda rng: clock_face(),
}


def register():
    textures.TEXTURES.update(TEXTURES)
