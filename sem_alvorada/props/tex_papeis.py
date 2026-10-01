"""Texturas de papel, livros, quadros, espelhos e decals dos cômodos de cima.

Fotos e pinturas reaproveitam os desenhos de 64x48 de `textures.py`, ampliados e suavizados como uma foto
antiga fora de foco. Livros ficam num atlas único (lombadas, cores de capa e corte das folhas), assim a
estante inteira usa um só material. Decals (manchas, marcas de mão, teias) têm canal alfa.
"""
import math

import numpy as np

from . import tex_noise as noise
from . import textures

Canvas = textures.Canvas

SPINE_W, SPINE_H, PATCH_H = 64, 256, 32
BOOK_COLORS = ((0.24, 0.07, 0.07), (0.07, 0.09, 0.17), (0.08, 0.15, 0.10), (0.38, 0.28, 0.10),
               (0.20, 0.11, 0.06), (0.20, 0.21, 0.23), (0.04, 0.04, 0.045), (0.50, 0.46, 0.36))
BOOK_ATLAS_SIZE = (len(BOOK_COLORS) * SPINE_W, SPINE_H + 2 * PATCH_H)


def _upscale(canvas, factor, blur=2):
    """Amplia um Canvas pequeno repetindo pixels e suavizando: a imagem fica macia, como fora de foco."""
    big = Canvas(canvas.width * factor, canvas.height * factor)
    big.px = np.repeat(np.repeat(canvas.px, factor, axis=0), factor, axis=1).copy()
    big.blur(blur)
    return big


def _fill(canvas, x0, y0, x1, y1, color):
    """Retângulo por fatia de array (muito mais rápido que `Canvas.rect`, que varre a imagem inteira)."""
    xs, xe = max(int(x0), 0), min(int(math.ceil(x1)), canvas.width)
    ys, ye = max(int(y0), 0), min(int(math.ceil(y1)), canvas.height)
    if xs >= xe or ys >= ye:
        return
    r, g, b, a = textures.rgb(color)
    region = canvas.px[ys:ye, xs:xe]
    region[..., :3] = region[..., :3] * (1 - a) + np.array([r, g, b], np.float32) * a
    region[..., 3] = np.maximum(region[..., 3], a)


def _text(canvas, x, y, string, color, scale=1):
    """Texto na fonte 5x7 do projeto, pixel a pixel por fatias."""
    for character in string.upper():
        columns = textures._GLYPHS.get(character, textures._GLYPHS[" "])
        for offset, bits in enumerate(columns):
            for row in range(7):
                if bits >> row & 1:
                    _fill(canvas, x + offset * scale, y + row * scale, x + (offset + 1) * scale, y + (row + 1) * scale, color)
        x += 6 * scale


def _opaque(canvas):
    canvas.px[..., 3] = 1.0
    return canvas


# ---------------------------------------------------------------------------
# Livros
# ---------------------------------------------------------------------------
def draw_books_atlas(rng):
    """Atlas de livros: 8 lombadas (linhas 0..255), cor de capa de cada uma (256..287) e corte das folhas (288..319)."""
    width, height = BOOK_ATLAS_SIZE
    canvas = Canvas(width, height, (0.10, 0.09, 0.07, 1.0))
    gen = noise.generator(rng)
    cylinder = 0.78 + 0.22 * np.sin(np.pi * (np.arange(SPINE_W) + 0.5) / SPINE_W)
    for column, base in enumerate(BOOK_COLORS):
        x0 = column * SPINE_W
        canvas.rect(x0, 0, x0 + SPINE_W, SPINE_H, (*base, 1.0))
        gilt = (0.62, 0.52, 0.26, 1.0) if column % 3 != 2 else (0.74, 0.72, 0.62, 1.0)
        for y in (14, 20, SPINE_H - 22, SPINE_H - 16):
            canvas.rect(x0 + 4, y, x0 + SPINE_W - 4, y + 2.5, gilt)
        canvas.rect(x0 + 9, 44, x0 + SPINE_W - 9, 150, (*[min(c * 1.6 + 0.05, 0.9) for c in base], 1.0))
        for line in range(5):
            y = 54 + line * 18
            canvas.rect(x0 + 13, y, x0 + 13 + rng.uniform(16, 36), y + 5, (*base, 0.9))
        canvas.ellipse(x0 + SPINE_W / 2, SPINE_H - 52, 9, 9, gilt)
        canvas.ellipse(x0 + SPINE_W / 2, SPINE_H - 52, 5, 5, (*base, 1.0))
        canvas.px[:SPINE_H, x0:x0 + SPINE_W, :3] *= cylinder[None, :, None]
        canvas.rect(x0, SPINE_H, x0 + SPINE_W, SPINE_H + PATCH_H, (*base, 1.0))
    cover_cloth = 0.80 + 0.30 * noise.fbm(PATCH_H, width, 8, 64, gen, 3)
    canvas.px[SPINE_H:SPINE_H + PATCH_H, :, :3] *= cover_cloth[..., None]
    canvas.px[:SPINE_H, :, :3] *= (0.85 + 0.25 * noise.fbm(SPINE_H, width, 24, 24, gen, 3))[..., None]
    pages = canvas.px[SPINE_H + PATCH_H:, :, :3]
    pages[:] = (0.60, 0.55, 0.42)
    pages *= (0.92 + 0.10 * np.sin(np.arange(PATCH_H)[:, None, None] * 2.4))
    canvas.px[SPINE_H + PATCH_H:, :, :3] = noise.grime(pages, gen, 0.35, (0.18, 0.14, 0.08), cells=4)
    return canvas


# ---------------------------------------------------------------------------
# Papéis datilografados e manuscritos
# ---------------------------------------------------------------------------
def _typed_lines(canvas, x0, y0, x1, y1, rng, ink, spacing=7):
    y = y0
    while y + 5 < y1:
        end = x1 - rng.uniform(0, (x1 - x0) * 0.3)
        x = x0
        while x < end:
            word = rng.uniform(10, 34)
            _fill(canvas, x, y, min(x + word, end), y + 3, (*ink, 0.55))
            x += word + 5
        y += spacing


def draw_paper_policy(rng, width=256, height=362):
    """Apólice de seguro: cabeçalho, tabela de campos e um carimbo vermelho de NEGADO inclinado."""
    gen = noise.generator(rng)
    canvas = Canvas(width, height, (0.78, 0.75, 0.64, 1.0))
    ink = (0.10, 0.10, 0.12)
    _text(canvas, 18, 16, "HARLAN MUTUAL", (*ink, 1.0), 2)
    _text(canvas, 18, 34, "SEGURO DE VEICULO", (*ink, 1.0), 1)
    canvas.rect(18, 46, width - 18, 48, (*ink, 0.8))
    for row in range(6):
        y = 60 + row * 22
        _text(canvas, 20, y, ("APOLICE", "TITULAR", "SINISTRO", "DATA", "VALOR", "PARECER")[row], (*ink, 0.9), 1)
        canvas.rect(100, y + 8, width - 24, y + 9, (*ink, 0.5))
    _text(canvas, 104, 60, "33-1947-HR", (0.12, 0.12, 0.35, 1.0), 1)
    _text(canvas, 104, 82, "D. HARPER", (0.12, 0.12, 0.35, 1.0), 1)
    _typed_lines(canvas, 20, 206, width - 20, height - 30, rng, ink)
    stamp = (0.62, 0.08, 0.06)
    canvas.polygon([(34, 250), (210, 226), (216, 266), (40, 292)], (*stamp, 0.18))
    _text(canvas, 60, 252, "NEGADO", (*stamp, 0.85), 4)
    canvas.px[..., :3] = noise.grime(canvas.px[..., :3], gen, 0.30, (0.30, 0.22, 0.10), 5)
    return _opaque(canvas)


def draw_paper_report(rng, width=256, height=362):
    """Boletim de ocorrência: brasão, campos e anotações a caneta nas margens."""
    gen = noise.generator(rng)
    canvas = Canvas(width, height, (0.74, 0.72, 0.64, 1.0))
    ink = (0.08, 0.08, 0.10)
    canvas.ellipse(width / 2, 34, 18, 18, (*ink, 0.7))
    canvas.ellipse(width / 2, 34, 13, 13, (0.74, 0.72, 0.64, 1.0))
    _text(canvas, 34, 62, "DEPTO DE POLICIA", (*ink, 1.0), 2)
    _text(canvas, 54, 82, "HARLAN RIDGE", (*ink, 1.0), 2)
    canvas.rect(20, 102, width - 20, 104, (*ink, 0.8))
    _text(canvas, 24, 114, "OCORRENCIA ROTA 33 - 06:12", (*ink, 0.9), 1)
    _typed_lines(canvas, 24, 134, width - 24, height - 80, rng, ink)
    canvas.scribbles(rng, 30, height - 70, width - 40, height - 30, (0.12, 0.12, 0.38, 0.9), 12, 1.3)
    canvas.px[..., :3] = noise.grime(canvas.px[..., :3], gen, 0.28, (0.28, 0.2, 0.1), 5)
    return _opaque(canvas)


def draw_paper_notes(rng, width=256, height=362):
    """Folha pautada com anotações a caneta: trajetos riscados e horários."""
    gen = noise.generator(rng)
    canvas = Canvas(width, height, (0.80, 0.78, 0.68, 1.0))
    for y in range(40, height, 15):
        canvas.rect(0, y, width, y + 1, (0.35, 0.45, 0.62, 0.45))
    canvas.rect(34, 0, 35, height, (0.70, 0.20, 0.20, 0.5))
    canvas.scribbles(rng, 42, 44, width - 20, height - 30, (0.10, 0.10, 0.30, 0.9), 15, 1.4, 0.2)
    canvas.line(60, 120, 200, 190, (0.60, 0.05, 0.05, 0.9), 2.0)
    canvas.line(60, 190, 200, 120, (0.60, 0.05, 0.05, 0.9), 2.0)
    canvas.px[..., :3] = noise.grime(canvas.px[..., :3], gen, 0.25, (0.25, 0.18, 0.1), 5)
    return _opaque(canvas)


def draw_newsprint(rng, size=256):
    """Recorte de jornal: manchete grande e colunas de texto cinza."""
    gen = noise.generator(rng)
    canvas = Canvas(size, size, (0.70, 0.67, 0.56, 1.0))
    ink = (0.10, 0.10, 0.11)
    _text(canvas, 10, 12, "HARLAN RIDGE", (*ink, 1.0), 3)
    _text(canvas, 10, 40, "GAZETTE", (*ink, 1.0), 2)
    canvas.rect(8, 60, size - 8, 62, (*ink, 0.9))
    for column in range(3):
        x0 = 10 + column * 80
        _typed_lines(canvas, x0, 72, x0 + 70, size - 16, rng, ink, spacing=6)
    canvas.rect(14, 150, 96, 220, (0.30, 0.30, 0.32, 1.0))
    canvas.px[..., :3] = noise.grime(canvas.px[..., :3], gen, 0.30, (0.30, 0.22, 0.10), 5)
    return _opaque(canvas)


# ---------------------------------------------------------------------------
# Fotos, quadros, mapa
# ---------------------------------------------------------------------------
def _soft_photo(rng, kind):
    canvas = _upscale(textures.draw_family_photo(rng, kind), 4, 3)
    gen = noise.generator(rng)
    canvas.px[..., :3] *= (0.90 + 0.20 * noise.fbm(canvas.height, canvas.width, 48, 64, gen, 2))[..., None]
    canvas.vignette(0.45)
    return _opaque(canvas)


def _soft_painting(rng, kind):
    canvas = _upscale(textures.draw_painting(rng, kind), 4, 2)
    gen = noise.generator(rng)
    weave = 0.93 + 0.07 * np.sin(np.arange(canvas.width) * 1.6)[None, :] * np.sin(np.arange(canvas.height) * 1.6)[:, None]
    canvas.px[..., :3] *= (weave * (0.92 + 0.16 * noise.fbm(canvas.height, canvas.width, 32, 48, gen, 3)))[..., None]
    return _opaque(canvas)


def draw_wall_map(rng, width=512, height=384):
    """Mapa de parede do escritório: a cidade, a Rota 33 em círculos vermelhos e alfinetes nos pontos visitados."""
    base = _upscale(textures.draw_city_map(rng, 256), 2, 1)
    canvas = Canvas(width, height, (0.72, 0.69, 0.56, 1.0))
    canvas.px[:] = base.px[:height, :width]
    for cx, cy in ((196, 252), (270, 210), (320, 150), (150, 120)):
        canvas.ellipse(cx, cy, 20, 20, (0.70, 0.06, 0.05, 0.28))
        canvas.ellipse(cx, cy, 5, 5, (0.80, 0.08, 0.06, 1.0))
        canvas.ellipse(cx - 1, cy - 1, 2, 2, (0.95, 0.60, 0.55, 1.0))
    canvas.line(196, 252, 270, 210, (0.65, 0.05, 0.05, 0.9), 2.0)
    canvas.line(270, 210, 320, 150, (0.65, 0.05, 0.05, 0.9), 2.0)
    _text(canvas, 212, 232, "6:12", (0.55, 0.04, 0.04, 1.0), 2)
    canvas.scribbles(rng, 24, height - 54, 190, height - 14, (0.10, 0.10, 0.30, 0.9), 12, 1.4)
    return _opaque(canvas)


def draw_calendar(rng, width=192, height=256):
    """Calendário de parede parado: as semanas riscadas e um dia circulado em vermelho."""
    gen = noise.generator(rng)
    canvas = Canvas(width, height, (0.82, 0.80, 0.70, 1.0))
    canvas.rect(0, 0, width, 64, (0.46, 0.16, 0.14, 1.0))
    _text(canvas, 20, 22, "SETEMBRO", (0.90, 0.86, 0.76, 1.0), 3)
    for row in range(5):
        for col in range(7):
            x, y = 12 + col * 24, 82 + row * 32
            _text(canvas, x, y, f"{row * 7 + col + 1:02d}" if row * 7 + col < 30 else "", (0.2, 0.2, 0.2, 0.8), 1)
            if row * 7 + col < 19:
                canvas.line(x - 2, y - 3, x + 14, y + 11, (0.55, 0.05, 0.05, 0.85), 1.5)
    canvas.ellipse(12 + 4 * 24 + 6, 82 + 2 * 32 + 3, 14, 12, (0.65, 0.06, 0.06, 0.28))
    canvas.px[..., :3] = noise.grime(canvas.px[..., :3], gen, 0.22, (0.25, 0.2, 0.1), 5)
    return _opaque(canvas)


def draw_mirror_cracked(rng, size=256):
    """Espelho de banheiro: prata comida pela umidade nas bordas e trincas que saem de um ponto de impacto."""
    gen = noise.generator(rng)
    canvas = Canvas(size, size)
    gradient = np.linspace(0.20, 0.05, size, dtype=np.float32)[:, None, None]
    canvas.px[..., :3] = np.array([0.55, 0.62, 0.68], np.float32) * gradient * 0.9
    canvas.px[..., 3] = 1.0
    edge = np.minimum(np.arange(size), size - 1 - np.arange(size))
    rim = np.minimum(edge[None, :], edge[:, None]) / size
    foxing = noise.smoothstep(0.55, 0.95, noise.fbm(size, size, 7, 7, gen, 4)) * noise.smoothstep(0.30, 0.04, rim)
    canvas.px[..., :3] = noise.blend(canvas.px[..., :3], (0.025, 0.02, 0.015), foxing)
    cx, cy = size * 0.62, size * 0.38
    for _ in range(13):
        angle = rng.uniform(0, math.tau)
        x, y = cx, cy
        for _ in range(7):
            angle += rng.uniform(-0.3, 0.3)
            step = rng.uniform(size * 0.05, size * 0.14)
            nx, ny = x + step * math.cos(angle), y + step * math.sin(angle)
            canvas.line(x, y, nx, ny, (0.80, 0.84, 0.88, 0.85), 1.0)
            if rng.random() < 0.3:
                branch = angle + rng.choice((-1, 1)) * rng.uniform(0.5, 1.0)
                canvas.line(nx, ny, nx + 22 * math.cos(branch), ny + 22 * math.sin(branch), (0.8, 0.84, 0.88, 0.6), 1.0)
            x, y = nx, ny
    for radius in (14, 28, 46):
        a0 = rng.uniform(0, math.tau)
        for k in range(0, 9):
            a = a0 + k * 0.55
            canvas.line(cx + radius * math.cos(a), cy + radius * math.sin(a), cx + radius * math.cos(a + 0.4),
                        cy + radius * math.sin(a + 0.4), (0.78, 0.82, 0.86, 0.5), 1.0)
    canvas.ellipse(cx, cy, 3.5, 3.5, (0.92, 0.94, 0.96, 0.95))
    canvas.blur(1)
    return canvas


def draw_mirror_plain(rng, size=128):
    """Espelho empoeirado: reflexo escuro, faixa de luz oblíqua, marcas de dedo e poeira."""
    gen = noise.generator(rng)
    canvas = Canvas(size, size)
    canvas.px[..., :3] = (np.array([0.09, 0.11, 0.13], np.float32) *
                          (1.0 + 0.9 * np.linspace(1, 0, size, dtype=np.float32)[:, None, None]))
    canvas.px[..., 3] = 1.0
    canvas.line(size * 0.2, size * 0.95, size * 0.62, size * 0.02, (0.55, 0.60, 0.65, 0.14), size * 0.12)
    dust = noise.smoothstep(0.45, 0.9, noise.fbm(size, size, 8, 8, gen, 4))
    canvas.px[..., :3] = noise.blend(canvas.px[..., :3], (0.32, 0.31, 0.28), dust * 0.35)
    return canvas


# ---------------------------------------------------------------------------
# Desenhos de criança
# ---------------------------------------------------------------------------
def _crayon_line(canvas, rng, points, color, width=3.0):
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        canvas.line(x0 + rng.uniform(-1, 1), y0 + rng.uniform(-1, 1), x1 + rng.uniform(-1, 1), y1 + rng.uniform(-1, 1),
                    (*color, 0.92), width)


def _stick_figure(canvas, rng, x, y, scale, dress):
    canvas.ellipse(x, y, 9 * scale, 9 * scale, (0.88, 0.70, 0.55, 1.0))
    canvas.polygon([(x, y + 9 * scale), (x + 15 * scale, y + 46 * scale), (x - 15 * scale, y + 46 * scale)], (*dress, 1.0))
    _crayon_line(canvas, rng, [(x - 13 * scale, y + 22 * scale), (x - 28 * scale, y + 34 * scale)], (0.2, 0.15, 0.12), 3)
    _crayon_line(canvas, rng, [(x + 13 * scale, y + 22 * scale), (x + 28 * scale, y + 34 * scale)], (0.2, 0.15, 0.12), 3)
    _crayon_line(canvas, rng, [(x - 6 * scale, y + 46 * scale), (x - 6 * scale, y + 66 * scale)], (0.2, 0.15, 0.12), 3)
    _crayon_line(canvas, rng, [(x + 6 * scale, y + 46 * scale), (x + 6 * scale, y + 66 * scale)], (0.2, 0.15, 0.12), 3)


def draw_crayon(rng, kind, width=192, height=256):
    """Desenho de giz de cera numa folha: `house` (casa com sol), `family` (três bonecos), `rabbit`."""
    gen = noise.generator(rng)
    canvas = Canvas(width, height, (0.82, 0.80, 0.70, 1.0))
    if kind == "rabbit":
        canvas.ellipse(96, 170, 44, 52, (0.80, 0.50, 0.58, 1.0))
        canvas.ellipse(96, 100, 30, 30, (0.82, 0.54, 0.60, 1.0))
        for side in (-1, 1):
            canvas.ellipse(96 + side * 16, 46, 9, 34, (0.82, 0.54, 0.60, 1.0))
            canvas.ellipse(96 + side * 16, 46, 4, 26, (0.92, 0.72, 0.74, 1.0))
            canvas.ellipse(96 + side * 11, 96, 3.5, 3.5, (0.10, 0.08, 0.10, 1.0))
        canvas.ellipse(96, 110, 4, 3, (0.40, 0.15, 0.2, 1.0))
        _text(canvas, 60, 232, "COELHINHO", (0.25, 0.30, 0.65, 0.95), 2)
    else:
        canvas.ellipse(150, 38, 22, 22, (0.92, 0.78, 0.18, 1.0))
        for k in range(10):
            a = k * math.tau / 10
            _crayon_line(canvas, rng, [(150 + 26 * math.cos(a), 38 + 26 * math.sin(a)),
                                       (150 + 38 * math.cos(a), 38 + 38 * math.sin(a))], (0.92, 0.78, 0.18), 3)
        canvas.rect(0, 190, width, height, (0.35, 0.55, 0.28, 0.8))
        if kind == "house":
            canvas.rect(30, 100, 110, 190, (0.62, 0.34, 0.22, 1.0))
            canvas.polygon([(22, 102), (70, 56), (118, 102)], (0.70, 0.16, 0.14, 1.0))
            canvas.rect(60, 140, 82, 190, (0.30, 0.20, 0.15, 1.0))
            canvas.rect(38, 112, 52, 126, (0.60, 0.70, 0.80, 1.0))
            canvas.rect(92, 112, 106, 126, (0.60, 0.70, 0.80, 1.0))
            _text(canvas, 30, 224, "NOSSA CASA", (0.25, 0.30, 0.65, 0.95), 2)
        else:
            _stick_figure(canvas, rng, 54, 100, 1.1, (0.18, 0.28, 0.60))
            _stick_figure(canvas, rng, 108, 98, 1.1, (0.70, 0.22, 0.30))
            _stick_figure(canvas, rng, 82, 136, 0.7, (0.92, 0.78, 0.20))
            _text(canvas, 24, 224, "EU MAMAE PAPAI", (0.25, 0.30, 0.65, 0.95), 1)
    canvas.grain(rng, 0.10)
    canvas.px[..., :3] *= (0.90 + 0.14 * noise.fbm(height, width, 40, 30, gen, 2))[..., None]
    return _opaque(canvas)


# ---------------------------------------------------------------------------
# Decals e vinil
# ---------------------------------------------------------------------------
def draw_stain(rng, size=256, color=(0.10, 0.025, 0.02)):
    """Mancha escura irregular com alfa: contorno por ruído em torno do centro e gotas satélites."""
    gen = noise.generator(rng)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dx, dy = (xx - size / 2) / size, (yy - size / 2) / size
    radius, angle = np.hypot(dx, dy), np.arctan2(dy, dx)
    boundary = 0.22 + 0.05 * np.sin(3 * angle + rng.uniform(0, 6)) + 0.03 * np.sin(7 * angle + rng.uniform(0, 6))
    boundary = boundary + 0.06 * (noise.fbm(size, size, 6, 6, gen, 3) - 0.5)
    alpha = noise.smoothstep(boundary + 0.02, boundary - 0.03, radius)
    drops = noise.smoothstep(0.80, 0.88, noise.fbm(size, size, 16, 16, gen, 2)) * noise.smoothstep(0.48, 0.24, radius) * 0.7
    canvas = Canvas(size, size, (*color, 0.0))
    canvas.px[..., :3] = np.array(color, np.float32)
    canvas.px[..., 3] = np.clip(np.maximum(alpha * 0.92, drops), 0, 1)
    return canvas


def draw_handprints(rng, size=256):
    """Duas mãos pequenas, escuras e borradas, arrastadas na parede: palma, cinco dedos e um rastro."""
    canvas = Canvas(size, size, (0.09, 0.025, 0.02, 0.0))
    ink = (0.09, 0.025, 0.02)
    for cx, cy, tilt in ((size * 0.30, size * 0.62, -0.18), (size * 0.68, size * 0.45, 0.22)):
        canvas.ellipse(cx, cy + 14, 26, 30, (*ink, 0.85))
        for finger in range(5):
            spread = (finger - 2) * 0.33 + tilt
            length = (34, 44, 48, 44, 32)[finger]
            base_x, base_y = cx + 17 * math.sin(spread), cy - 10
            canvas.line(base_x, base_y, base_x + length * math.sin(spread), base_y - length * math.cos(spread), (*ink, 0.85), 9.0)
        canvas.line(cx - 4, cy + 36, cx - 8, cy + 92, (*ink, 0.42), 12.0)
    canvas.blur(2)
    canvas.px[..., 3] = np.clip(canvas.px[..., 3] * 1.1, 0, 0.9)
    return canvas


def draw_ring_stain(rng, size=128):
    """Marca de fundo de copo: um anel de líquido seco, mais forte de um lado."""
    canvas = Canvas(size, size, (0.12, 0.08, 0.04, 0.0))
    radius = np.hypot(canvas._grid_x - size / 2, canvas._grid_y - size / 2) / size
    ring = noise.smoothstep(0.34, 0.39, radius) * noise.smoothstep(0.45, 0.40, radius)
    side = 0.55 + 0.45 * np.cos(np.arctan2(canvas._grid_y - size / 2, canvas._grid_x - size / 2) - 0.8)
    canvas.px[..., 3] = ring * side * 0.55
    return canvas


def draw_cobweb(rng, size=256):
    """Teia de canto (um quarto de círculo): raios e arcos frouxos em cinza-claro com alfa."""
    canvas = Canvas(size, size, (0.78, 0.78, 0.74, 0.0))
    spokes = [rng.uniform(0.05, 1.5) for _ in range(7)] + [0.0, math.pi / 2]
    for angle in spokes:
        canvas.line(0, 0, size * 1.1 * math.cos(angle), size * 1.1 * math.sin(angle), (0.78, 0.78, 0.74, 0.55), 1.2)
    ordered = sorted(spokes)
    for ring in range(1, 9):
        radius = ring * size * 0.11
        for a, b in zip(ordered, ordered[1:]):
            mid = (a + b) / 2
            sag = radius * (0.86 + 0.06 * rng.random())
            canvas.line(radius * math.cos(a), radius * math.sin(a), sag * math.cos(mid), sag * math.sin(mid), (0.78, 0.78, 0.74, 0.40), 1.0)
            canvas.line(sag * math.cos(mid), sag * math.sin(mid), radius * math.cos(b), radius * math.sin(b), (0.78, 0.78, 0.74, 0.40), 1.0)
    canvas.blur(1)
    canvas.px[..., 3] = np.clip(canvas.px[..., 3] * 1.4, 0, 0.7)
    return canvas


def draw_glow_stars(rng, size=256):
    """Adesivos de estrelas e uma lua que brilham no escuro, em verde-amarelado pálido."""
    canvas = Canvas(size, size, (0.70, 0.78, 0.42, 0.0))
    color = (0.74, 0.82, 0.46, 0.95)
    for cx, cy, radius in ((48, 52, 26), (150, 40, 16), (96, 130, 20), (200, 120, 28), (60, 210, 14), (170, 210, 18)):
        points = [(cx + (radius if k % 2 == 0 else radius * 0.42) * math.cos(-math.pi / 2 + k * math.pi / 5),
                   cy + (radius if k % 2 == 0 else radius * 0.42) * math.sin(-math.pi / 2 + k * math.pi / 5)) for k in range(10)]
        canvas.polygon(points, color)
    canvas.blur(1)
    return canvas


def draw_curtain_vinyl(rng, size=256):
    """Cortina de box de vinil verde-água com bolhas brancas e bolor subindo da barra."""
    gen = noise.generator(rng)
    canvas = Canvas(size, size, (0.56, 0.68, 0.62, 1.0))
    for _ in range(36):
        x, y, r = rng.uniform(0, size), rng.uniform(0, size), rng.uniform(6, 15)
        for ox in (-size, 0, size):
            canvas.ellipse(x + ox, y, r, r, (0.78, 0.86, 0.80, 0.9))
            canvas.ellipse(x + ox, y, r * 0.7, r * 0.7, (0.56, 0.68, 0.62, 0.9))
    mold = noise.smoothstep(0.35, 0.8, np.linspace(0.0, 1.0, size)[:, None] + 0.45 * noise.fbm(size, size, 10, 10, gen, 4) - 0.55)
    canvas.px[..., :3] = noise.blend(canvas.px[..., :3], (0.07, 0.10, 0.06), mold * 0.75)
    return _opaque(canvas)


TEXTURES = {
    "up_books": draw_books_atlas,
    "up_paper_policy": draw_paper_policy,
    "up_paper_report": draw_paper_report,
    "up_paper_notes": draw_paper_notes,
    "up_newsprint": draw_newsprint,
    "up_photo_trio": lambda rng: _soft_photo(rng, "trio"),
    "up_photo_mother_child": lambda rng: _soft_photo(rng, "mother_child"),
    "up_photo_father_child": lambda rng: _soft_photo(rng, "father_child"),
    "up_photo_portrait": lambda rng: _soft_photo(rng, "portrait"),
    "up_painting_lake": lambda rng: _soft_painting(rng, "lake"),
    "up_painting_barn": lambda rng: _soft_painting(rng, "barn"),
    "up_painting_still": lambda rng: _soft_painting(rng, "still"),
    "up_wall_map": draw_wall_map,
    "up_calendar": draw_calendar,
    "up_mirror_cracked": draw_mirror_cracked,
    "up_mirror_plain": draw_mirror_plain,
    "up_crayon_house": lambda rng: draw_crayon(rng, "house"),
    "up_crayon_family": lambda rng: draw_crayon(rng, "family"),
    "up_crayon_rabbit": lambda rng: draw_crayon(rng, "rabbit"),
    "up_stain": draw_stain,
    "up_stain_ring": draw_ring_stain,
    "up_handprints": draw_handprints,
    "up_cobweb": draw_cobweb,
    "up_glow_stars": draw_glow_stars,
    "up_curtain_vinyl": draw_curtain_vinyl,
}
textures.TEXTURES.update(TEXTURES)
