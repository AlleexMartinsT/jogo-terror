"""Texturas e materiais dos itens coletáveis: papel de verdade, rótulo de pilha, metal escovado.

Estas texturas são maiores (256 a 512 px) e usam filtro Linear: um bilhete lido a 40 cm tem de ter fibras,
vincos e letra, não blocos. Os desenhos de traço usam um rasterizador local (só o retângulo afetado por
cada segmento), o que torna a letra manuscrita barata mesmo com milhares de traços.
"""
import math

import numpy as np

from .. import compat
from . import materials, textures

INK_BLUE = (0.10, 0.13, 0.30)
INK_PENCIL = (0.24, 0.24, 0.26)
INK_BLACK = (0.07, 0.07, 0.08)


# ---------------------------------------------------------------------------
# Primitivas de desenho (px é um array (H, W, 4); origem no canto superior esquerdo)
# ---------------------------------------------------------------------------
def stroke(px, x0, y0, x1, y1, width, color, alpha=1.0):
    height, wide = px.shape[:2]
    pad = width / 2 + 1.5
    xa, xb = int(max(0, min(x0, x1) - pad)), int(min(wide, max(x0, x1) + pad + 1))
    ya, yb = int(max(0, min(y0, y1) - pad)), int(min(height, max(y0, y1) + pad + 1))
    if xb <= xa or yb <= ya:
        return
    gx, gy = np.meshgrid(np.arange(xa, xb) + 0.5, np.arange(ya, yb) + 0.5)
    dx, dy = x1 - x0, y1 - y0
    span = dx * dx + dy * dy or 1.0
    t = np.clip(((gx - x0) * dx + (gy - y0) * dy) / span, 0, 1)
    distance = np.hypot(gx - (x0 + t * dx), gy - (y0 + t * dy))
    cover = (np.clip(width / 2 + 0.5 - distance, 0, 1) * alpha)[..., None]
    region = px[ya:yb, xa:xb, :3]
    region[:] = region * (1 - cover) + np.array(color[:3], np.float32) * cover


def polyline(px, points, width, color, alpha=1.0):
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        stroke(px, x0, y0, x1, y1, width, color, alpha)


def disc(px, cx, cy, radius, color, alpha=1.0, softness=1.0):
    height, wide = px.shape[:2]
    xa, xb = int(max(0, cx - radius - 2)), int(min(wide, cx + radius + 3))
    ya, yb = int(max(0, cy - radius - 2)), int(min(height, cy + radius + 3))
    gx, gy = np.meshgrid(np.arange(xa, xb) + 0.5, np.arange(ya, yb) + 0.5)
    cover = (np.clip((radius - np.hypot(gx - cx, gy - cy)) / softness + 0.5, 0, 1) * alpha)[..., None]
    region = px[ya:yb, xa:xb, :3]
    region[:] = region * (1 - cover) + np.array(color[:3], np.float32) * cover


def ring(px, cx, cy, radius, thickness, color, alpha=1.0):
    height, wide = px.shape[:2]
    outer = radius + thickness
    xa, xb = int(max(0, cx - outer - 2)), int(min(wide, cx + outer + 3))
    ya, yb = int(max(0, cy - outer - 2)), int(min(height, cy + outer + 3))
    gx, gy = np.meshgrid(np.arange(xa, xb) + 0.5, np.arange(ya, yb) + 0.5)
    distance = np.abs(np.hypot(gx - cx, gy - cy) - radius)
    cover = (np.clip(thickness / 2 + 0.5 - distance, 0, 1) * alpha)[..., None]
    region = px[ya:yb, xa:xb, :3]
    region[:] = region * (1 - cover) + np.array(color[:3], np.float32) * cover


def fill_rect(px, x0, y0, x1, y1, color, alpha=1.0):
    height, wide = px.shape[:2]
    xa, xb, ya, yb = int(max(0, x0)), int(min(wide, x1)), int(max(0, y0)), int(min(height, y1))
    if xb > xa and yb > ya:
        region = px[ya:yb, xa:xb, :3]
        region[:] = region * (1 - alpha) + np.array(color[:3], np.float32) * alpha


def _blotches(height, wide, cells, rng):
    """Ruído suave (interpolação bilinear de uma grade aleatória pequena)."""
    grid = rng.random((cells + 1, cells + 1)).astype(np.float32)
    ys = np.linspace(0, cells, height)
    xs = np.linspace(0, cells, wide)
    rows = np.array([np.interp(xs, np.arange(cells + 1), line) for line in grid])
    return np.array([np.interp(ys, np.arange(cells + 1), rows[:, i]) for i in range(wide)]).T


def canvas_of(px):
    canvas = textures.Canvas(px.shape[1], px.shape[0])
    canvas.px = px
    return canvas


def paper(width, height, color, seed, *, fiber=0.030, blotch=0.07, edge_dark=0.16, age=0.0):
    """Papel com fibras, manchas largas e bordas escurecidas; `age` amarela e suja."""
    rng = np.random.default_rng(seed)
    px = np.empty((height, width, 4), np.float32)
    px[..., :3] = np.array(color, np.float32)
    px[..., 3] = 1.0
    px[..., :3] *= (1 + blotch * (_blotches(height, width, 5, rng) - 0.5) * 2)[..., None]
    px[..., :3] *= (1 + blotch * 0.6 * (_blotches(height, width, 14, rng) - 0.5) * 2)[..., None]
    fibers = rng.normal(0, 1, (height, width)).astype(np.float32)
    fibers = (fibers + np.roll(fibers, 1, 1) + np.roll(fibers, -1, 1)) / 3        # fibras alongadas em X
    px[..., :3] *= (1 + fiber * fibers)[..., None]
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    edge = np.minimum.reduce([xs, width - 1 - xs, ys, height - 1 - ys]) / (0.07 * min(width, height))
    px[..., :3] *= (1 - edge_dark * np.clip(1 - edge, 0, 1) ** 1.5)[..., None]
    if age:
        px[..., :3] = px[..., :3] * (1 - age * 0.35) + np.array((0.62, 0.50, 0.28), np.float32) * (age * 0.35)
    return px


def crease_line(px, x0, y0, x1, y1, strength=0.22):
    """Dobra: sombra fina com um fio claro ao lado, como papel dobrado e aberto."""
    stroke(px, x0, y0, x1, y1, 1.6, (0.0, 0.0, 0.0), strength)
    nx, ny = (y1 - y0), -(x1 - x0)
    length = math.hypot(nx, ny) or 1.0
    stroke(px, x0 + nx / length * 2, y0 + ny / length * 2, x1 + nx / length * 2, y1 + ny / length * 2, 1.4,
           (1.0, 1.0, 0.95), strength * 0.7)


def coffee_ring(px, cx, cy, radius, rng, strength=0.30):
    ring(px, cx, cy, radius, 3.0, (0.30, 0.18, 0.08), strength)
    disc(px, cx, cy, radius, (0.45, 0.30, 0.15), strength * 0.18, softness=radius * 0.5)
    for _ in range(5):
        angle = rng.uniform(0, math.tau)
        disc(px, cx + math.cos(angle) * radius, cy + math.sin(angle) * radius, rng.uniform(1.5, 3.5),
             (0.28, 0.16, 0.07), strength * 0.7)


# ---------------------------------------------------------------------------
# Letra manuscrita
# ---------------------------------------------------------------------------
def _letter(px, rng, x, baseline, size, color, width, slant):
    """Um 'caractere' manuscrito: arco curto, haste com laço ou cauda, em curva suave."""
    kind = rng.random()
    reach = size * rng.uniform(0.28, 0.46)
    points = []
    if kind < 0.22:          # haste alta com laço (l, h, b)
        top = baseline - size * rng.uniform(0.9, 1.15)
        for k in range(9):
            t = k / 8
            points.append((x + slant * (baseline - top) * (1 - t) * 0.4 + math.sin(t * math.pi) * reach * 0.8,
                           baseline + (top - baseline) * math.sin(t * math.pi)))
    elif kind < 0.40:        # cauda (g, y, p)
        bottom = baseline + size * rng.uniform(0.45, 0.75)
        for k in range(9):
            t = k / 8
            points.append((x + math.sin(t * math.pi) * reach * 0.6 - t * reach * 0.2,
                           baseline - size * 0.5 * math.sin(t * math.pi) * (1 - t) + (bottom - baseline) * t * t))
    else:                    # corpo (a, e, o, n, m)
        for k in range(8):
            t = k / 7
            points.append((x + t * reach, baseline - size * 0.5 * abs(math.sin(t * math.pi * rng.choice((1, 1.5, 2))))))
    polyline(px, points, width, color, 0.9)
    return reach


def write_lines(px, rng, x0, y0, x1, y1, color, line_height, width=1.5, slant=0.15, ragged=0.22, lines=None):
    """Preenche a caixa com linhas de letra manuscrita ilegível mas convincente (base oscilando, palavras irregulares)."""
    y = y0 + line_height
    count = 0
    while y <= y1 and (lines is None or count < lines):
        x = x0 + rng.uniform(0, line_height * 0.6)
        end = x1 - rng.uniform(0, (x1 - x0) * ragged)
        drift = rng.uniform(-0.8, 0.8)
        while x < end:
            letters = rng.integers(2, 8)
            for _ in range(int(letters)):
                if x >= end:
                    break
                x += _letter(px, rng, x, y + drift + rng.uniform(-0.7, 0.7), line_height * 0.75, color, width, slant) \
                    + line_height * 0.05
            x += line_height * rng.uniform(0.35, 0.65)
        y += line_height
        count += 1


def ruled(px, y0, y1, step, color=(0.55, 0.65, 0.85), alpha=0.55, margin_x=None, margin_color=(0.85, 0.35, 0.35)):
    y = y0
    while y < y1:
        stroke(px, 0, y, px.shape[1], y, 1.1, color, alpha)
        y += step
    if margin_x is not None:
        stroke(px, margin_x, 0, margin_x, px.shape[0], 1.2, margin_color, alpha)


def type_text(px, x, y, string, color, scale=2, spacing=1, alpha=1.0):
    """Texto com a fonte 5x7 do projeto; para cabeçalhos impressos."""
    glyphs = textures._GLYPHS
    for character in string.upper():
        columns = glyphs.get(character, glyphs[" "])
        for column, bits in enumerate(columns):
            for row in range(7):
                if bits >> row & 1:
                    fill_rect(px, x + column * scale, y + row * scale, x + (column + 1) * scale,
                              y + (row + 1) * scale, color, alpha)
        x += (5 + spacing) * scale
    return x


# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------
def draw_note_letter(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    px = paper(256, 320, (0.86, 0.82, 0.70), seed, age=0.5)
    write_lines(px, gen, 22, 26, 236, 240, INK_BLUE, 17, 1.7)
    write_lines(px, gen, 22, 258, 150, 296, INK_BLUE, 24, 2.4, ragged=0.1, lines=1)      # assinatura grande
    for fold in (107, 214):                                                              # dobras em três
        crease_line(px, 0, fold, 256, fold, 0.28)
    for _ in range(3):                                                                   # marcas de lágrima
        x, y = gen.uniform(30, 220), gen.uniform(40, 220)
        disc(px, x, y, gen.uniform(4, 7), (0.55, 0.50, 0.42), 0.25, softness=3)
    return canvas_of(px)


def draw_envelope(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    px = paper(384, 256, (0.82, 0.76, 0.60), seed, age=0.55)
    write_lines(px, gen, 130, 96, 340, 170, INK_BLUE, 20, 2.0, lines=3, ragged=0.15)
    fill_rect(px, 322, 14, 366, 62, (0.70, 0.22, 0.18), 0.85)
    ring(px, 344, 38, 14, 2, (0.95, 0.90, 0.8), 0.6)
    ring(px, 290, 40, 22, 2.4, (0.22, 0.22, 0.25), 0.45)
    stroke(px, 262, 28, 320, 28, 1.6, (0.22, 0.22, 0.25), 0.4)
    stroke(px, 262, 52, 320, 52, 1.6, (0.22, 0.22, 0.25), 0.4)
    return canvas_of(px)


def draw_crayon_drawing(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    px = paper(320, 448, (0.90, 0.88, 0.80), seed, fiber=0.02, age=0.25)

    def wax(points, width, color):
        for jitter in range(3):                                   # cera: o traço falha e se repete
            shifted = [(x + gen.normal(0, 0.9), y + gen.normal(0, 0.9)) for x, y in points]
            polyline(px, shifted, width, color, 0.55 + 0.15 * jitter)

    wax([(20, 330), (120, 326), (230, 334), (300, 328)], 8, (0.30, 0.55, 0.22))                      # chão
    wax([(80, 330), (80, 236), (210, 236), (210, 330)], 6, (0.15, 0.30, 0.70))                       # casa
    wax([(70, 240), (145, 170), (222, 240), (70, 240)], 6, (0.75, 0.15, 0.12))                       # telhado
    wax([(135, 330), (135, 276), (166, 276), (166, 330)], 5, (0.45, 0.28, 0.12))                     # porta
    for angle in np.linspace(0, math.tau, 14, endpoint=False):                                       # sol enorme
        wax([(255 + math.cos(angle) * 34, 70 + math.sin(angle) * 34),
             (255 + math.cos(angle) * 58, 70 + math.sin(angle) * 58)], 5, (0.95, 0.78, 0.12))
    for r in range(0, 32, 5):
        ring(px, 255, 70, r + 2, 5, (0.96, 0.82, 0.15), 0.85)
    wax([(285, 120), (288, 300)], 11, (0.04, 0.04, 0.05))                                            # o homem alto
    wax([(288, 300), (278, 332)], 8, (0.04, 0.04, 0.05))
    wax([(288, 300), (299, 332)], 8, (0.04, 0.04, 0.05))
    wax([(287, 160), (262, 224)], 7, (0.04, 0.04, 0.05))
    wax([(289, 160), (310, 226)], 7, (0.04, 0.04, 0.05))
    disc(px, 286, 108, 11, (0.04, 0.04, 0.05), 1.0)
    disc(px, 281, 106, 3.2, (1.0, 1.0, 1.0), 1.0)
    disc(px, 292, 106, 3.2, (1.0, 1.0, 1.0), 1.0)
    for cx, h in ((40, 40), (58, 62)):                                                               # a menina e a mãe
        wax([(cx, 330 - h), (cx, 330)], 5, (0.85, 0.30, 0.55))
        disc(px, cx, 330 - h - 8, 7, (0.95, 0.75, 0.60), 0.95)
    write_lines(px, gen, 18, 360, 300, 436, (0.12, 0.12, 0.45), 24, 3.2, slant=0.3, ragged=0.3)       # a frase da Emma
    return canvas_of(px)


def draw_newspaper_clip(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    px = paper(320, 384, (0.72, 0.69, 0.60), seed, fiber=0.045, age=0.75)
    type_text(px, 14, 12, "HARLAN RIDGE GAZETTE", INK_BLACK, 2, alpha=0.85)
    stroke(px, 10, 32, 310, 32, 2.0, INK_BLACK, 0.8)
    type_text(px, 14, 44, "MENINA DE 7 ANOS", INK_BLACK, 3, alpha=0.9)
    type_text(px, 14, 70, "MORRE NA ROTA 33", INK_BLACK, 3, alpha=0.9)
    stroke(px, 10, 96, 310, 96, 1.2, INK_BLACK, 0.6)
    ys, xs = np.mgrid[0:90, 0:140].astype(np.float32)                                              # foto retícula
    photo = 0.35 + 0.35 * _blotches(90, 140, 4, gen)
    dots = (np.sin(xs * 1.6) * np.sin(ys * 1.6) > 0.1).astype(np.float32)
    px[104:194, 14:154, :3] = (0.78 - 0.55 * photo * dots)[..., None] * np.array((1, 0.96, 0.88), np.float32)
    for x0, y_start in ((14, 204), (164, 104)):                    # coluna esquerda abaixo da foto, direita inteira
        y = y_start
        while y < 370:
            stroke(px, x0, y, x0 + gen.uniform(60, 138), y, 2.2, INK_BLACK, 0.55)
            y += 8
    for _ in range(4):
        disc(px, gen.uniform(0, 320), gen.uniform(0, 384), gen.uniform(6, 20), (0.50, 0.42, 0.28), 0.14, softness=8)
    return canvas_of(px)


def draw_notebook_page(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    px = paper(320, 416, (0.90, 0.89, 0.82), seed, age=0.2)
    ruled(px, 54, 416, 24, margin_x=46)
    write_lines(px, gen, 58, 36, 306, 400, INK_PENCIL, 24, 1.5, slant=0.1, ragged=0.28)
    coffee_ring(px, 236, 330, 34, gen, 0.32)
    return canvas_of(px)


def draw_postit(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    px = paper(192, 192, (0.93, 0.82, 0.30), seed, fiber=0.02, blotch=0.05)
    fill_rect(px, 0, 0, 192, 24, (0.78, 0.66, 0.20), 0.55)
    write_lines(px, gen, 16, 40, 176, 176, (0.12, 0.18, 0.50), 30, 3.0, slant=0.2, ragged=0.2, lines=4)
    return canvas_of(px)


def draw_prescription(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    px = paper(256, 320, (0.88, 0.87, 0.80), seed, age=0.55)
    type_text(px, 16, 14, "DR. G. MILLS", INK_BLACK, 2, alpha=0.85)
    type_text(px, 16, 34, "PSIQUIATRIA", INK_BLACK, 1, alpha=0.7)
    stroke(px, 12, 50, 244, 50, 1.4, INK_BLACK, 0.7)
    type_text(px, 18, 62, "RX", INK_BLACK, 4, alpha=0.8)
    write_lines(px, gen, 22, 98, 238, 230, INK_BLUE, 24, 2.0, ragged=0.3, lines=4)
    write_lines(px, gen, 120, 252, 238, 290, INK_BLUE, 30, 2.6, ragged=0.1, lines=1)
    ring(px, 60, 262, 22, 2.4, (0.55, 0.15, 0.15), 0.45)
    return canvas_of(px)


def draw_tow_slip(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    px = paper(320, 400, (0.88, 0.88, 0.84), seed, age=0.35)
    px[200:, :, :3] = px[200:, :, :3] * np.array((1.0, 0.92, 0.45), np.float32)
    type_text(px, 12, 12, "PATIO MUNICIPAL", INK_BLACK, 2, alpha=0.85)
    type_text(px, 12, 32, "LIBERACAO DE VEICULO", INK_BLACK, 1, alpha=0.8)
    for row in range(8):
        y = 56 + row * 18
        stroke(px, 12, y, 308, y, 1.2, INK_BLACK, 0.55)
        stroke(px, 150, y - 14, 150, y, 1.0, INK_BLACK, 0.4)
    write_lines(px, gen, 16, 44, 300, 190, (0.14, 0.22, 0.55), 18, 1.7, ragged=0.4, lines=7)
    write_lines(px, gen, 16, 212, 300, 380, (0.14, 0.22, 0.55), 18, 1.7, ragged=0.4, lines=8)
    stroke(px, 0, 200, 320, 200, 1.4, INK_BLACK, 0.35)
    for x in range(8, 320, 12):                                                     # picote
        disc(px, x, 200, 1.3, (0.1, 0.1, 0.1), 0.5)
    return canvas_of(px)


def draw_paper_back(rng):
    seed = int(rng.random() * 1e9)
    return canvas_of(paper(256, 256, (0.80, 0.77, 0.66), seed, age=0.45))


# ---------------------------------------------------------------------------
# Mapa da cidade
# ---------------------------------------------------------------------------
def draw_city_map(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    size = 512
    px = paper(size, size, (0.82, 0.80, 0.68), seed, fiber=0.025, edge_dark=0.10, age=0.4)
    for x0, y0, x1, y1 in ((60, 70, 150, 160), (330, 300, 440, 390), (380, 90, 450, 150)):     # parques
        fill_rect(px, x0, y0, x1, y1, (0.50, 0.62, 0.38), 0.65)
    river = [(0, 360), (90, 340), (170, 372), (260, 350), (350, 330), (440, 350), (size, 335)]   # rio
    polyline(px, river, 18, (0.52, 0.68, 0.80), 0.85)
    polyline(px, river, 18, (0.30, 0.45, 0.60), 0.18)
    for k in range(9):                                                                              # grade de ruas
        coordinate = 24 + k * 58 + gen.uniform(-4, 4)
        width = 4.5 if k % 4 == 0 else 2.2
        stroke(px, coordinate, 0, coordinate + gen.uniform(-8, 8), size, width, (0.97, 0.95, 0.88), 0.95)
        stroke(px, 0, coordinate, size, coordinate + gen.uniform(-8, 8), width, (0.97, 0.95, 0.88), 0.95)
    stroke(px, 30, 470, 480, 40, 9, (0.88, 0.70, 0.30), 0.95)                                       # rodovia
    stroke(px, 30, 470, 480, 40, 9, (0.30, 0.20, 0.05), 0.20)
    type_text(px, 190, 238, "ROTA 33", (0.55, 0.12, 0.12), 2, alpha=0.9)
    stroke(px, 186, 232, 296, 262, 4, (0.65, 0.08, 0.08), 0.85)                                    # riscada
    stroke(px, 186, 262, 296, 232, 4, (0.65, 0.08, 0.08), 0.85)
    for _ in range(26):
        type_text(px, gen.uniform(10, 440), gen.uniform(10, 490), "".join(gen.choice(list("ABCDEFGHIMNORST"), 5)),
                  (0.30, 0.28, 0.26), 1, alpha=0.6)
    ring(px, 460, 460, 22, 2.2, INK_BLACK, 0.7)                                                     # rosa dos ventos
    stroke(px, 460, 434, 460, 486, 1.6, INK_BLACK, 0.8)
    stroke(px, 434, 460, 486, 460, 1.6, INK_BLACK, 0.8)
    type_text(px, 454, 424, "N", INK_BLACK, 1, alpha=0.9)
    stroke(px, 210, 150, 330, 410, 5, (0.15, 0.25, 0.65), 0.7)                                      # rota a lápis até a saída
    for fold_x in (size // 3, 2 * size // 3):
        crease_line(px, fold_x, 0, fold_x, size, 0.34)
    crease_line(px, 0, size // 2, size, size // 2, 0.30)
    coffee_ring(px, 90, 440, 30, gen, 0.22)
    return canvas_of(px)


# ---------------------------------------------------------------------------
# Pilhas, metal, flanela
# ---------------------------------------------------------------------------
def draw_battery_label(rng):
    seed = int(rng.random() * 1e9)
    gen = np.random.default_rng(seed)
    wide, high = 256, 128                                    # u: volta ao redor (256), v: comprimento (128)
    px = np.empty((high, wide, 4), np.float32)
    px[..., :] = (0.04, 0.04, 0.045, 1.0)
    fill_rect(px, 0, 0, wide, 30, (0.72, 0.40, 0.12), 1.0)                         # faixa de cobre no topo
    fill_rect(px, 0, 30, wide, 34, (0.85, 0.62, 0.20), 1.0)
    fill_rect(px, 0, 96, wide, 100, (0.85, 0.62, 0.20), 1.0)
    type_text(px, 12, 48, "ALKALINE", (0.90, 0.72, 0.28), 3, alpha=0.95)
    type_text(px, 12, 74, "D", (0.95, 0.95, 0.92), 3, alpha=0.95)
    type_text(px, 42, 78, "1.5V", (0.95, 0.95, 0.92), 2, alpha=0.9)
    type_text(px, 140, 48, "ALKALINE", (0.90, 0.72, 0.28), 3, alpha=0.95)
    for _ in range(40):                                                            # riscos e uso
        x, y = gen.uniform(0, wide), gen.uniform(0, high)
        stroke(px, x, y, x + gen.uniform(-14, 14), y + gen.uniform(-3, 3), 1.0, (0.7, 0.7, 0.65), 0.28)
    px[..., :3] *= (1 + 0.05 * gen.normal(0, 1, (high, wide, 1))).astype(np.float32)
    return canvas_of(px)


def draw_brushed_metal(rng):
    gen = np.random.default_rng(int(rng.random() * 1e9))
    streaks = gen.normal(0, 1, (256, 256)).astype(np.float32)
    for _ in range(3):
        streaks = (streaks + np.roll(streaks, 1, 0) + np.roll(streaks, -1, 0)) / 3        # estrias ao longo de Y
    px = np.empty((256, 256, 4), np.float32)
    px[..., :3] = (0.5 + 0.09 * streaks)[..., None]
    px[..., 3] = 1.0
    for _ in range(60):                                                                   # riscos
        x, y = gen.uniform(0, 256), gen.uniform(0, 256)
        stroke(px, x, y, x + gen.uniform(-30, 30), y + gen.uniform(-30, 30), 1.0, (0.75, 0.75, 0.75), 0.35)
    return canvas_of(px)


def draw_knurl(rng):
    """Padrão de moleta (losangos): uso como relevo na pegada da lanterna."""
    size = 64
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    ridge = 0.5 + 0.5 * np.sin((xs + ys) * math.tau / 16) * np.sin((xs - ys) * math.tau / 16)
    px = np.empty((size, size, 4), np.float32)
    px[..., :3] = (0.25 + 0.5 * ridge)[..., None]
    px[..., 3] = 1.0
    return canvas_of(px)


def draw_flannel(rng):
    gen = np.random.default_rng(int(rng.random() * 1e9))
    size = 128
    px = np.empty((size, size, 4), np.float32)
    px[..., :3] = (0.18, 0.07, 0.07)
    px[..., 3] = 1.0
    for band in (14, 78):
        fill_rect(px, band, 0, band + 22, size, (0.08, 0.14, 0.10), 0.7)
        fill_rect(px, 0, band, size, band + 22, (0.08, 0.14, 0.10), 0.7)
    fill_rect(px, 44, 0, 48, size, (0.55, 0.50, 0.40), 0.35)
    fill_rect(px, 0, 44, size, 48, (0.55, 0.50, 0.40), 0.35)
    weave = gen.normal(0, 1, (size, size)).astype(np.float32)
    px[..., :3] *= (1 + 0.10 * weave)[..., None]
    return canvas_of(px)


TEXTURES_NEW = {
    "note_letter": draw_note_letter, "note_envelope": draw_envelope, "note_crayon": draw_crayon_drawing,
    "note_newspaper": draw_newspaper_clip, "note_notebook": draw_notebook_page, "note_postit": draw_postit,
    "note_prescription": draw_prescription, "note_tow": draw_tow_slip, "paper_back": draw_paper_back,
    "city_map": draw_city_map, "battery_label": draw_battery_label, "brushed_metal": draw_brushed_metal,
    "knurl": draw_knurl, "flannel": draw_flannel,
}
textures.TEXTURES.update(TEXTURES_NEW)


# ---------------------------------------------------------------------------
# Materiais
# ---------------------------------------------------------------------------
def _textured(name, texture, *, color=(0.5, 0.5, 0.5), roughness=0.85, metallic=0.0, relief=0.0, relief_distance=0.001,
              emission=0.0, emit_color=None, tile=1.0):
    mat = compat.new_material(name)
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, base_color=color, roughness=roughness, metallic=metallic,
                    specular=0.2 if metallic == 0 else 0.5)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = textures.image(texture)
    image_node.interpolation = "Linear"
    image_node.extension = "REPEAT"
    if tile != 1.0:
        coords = nodes.new("ShaderNodeTexCoord")
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (tile, tile, tile)
        links.new(coords.outputs["UV"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], image_node.inputs["Vector"])
    links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
    if relief:
        compat.add_relief(mat, image_node.outputs["Color"], relief, relief_distance)
    if emission:
        links.new(image_node.outputs["Color"], bsdf.inputs["Emission Color"])
        compat.set_bsdf(bsdf, emission_strength=emission)
    mat.diffuse_color = (*color, 1.0)
    return mat


def _register_materials():
    paper_names = ("note_letter", "note_envelope", "note_crayon", "note_newspaper", "note_notebook",
                   "note_postit", "note_prescription", "note_tow", "city_map")
    for name in paper_names:
        materials.register_builder(name, lambda n=name: _textured(n, n, roughness=0.92, relief=0.35,
                                                                  relief_distance=0.0004))
    materials.register_builder("paper_back", lambda: _textured("paper_back", "paper_back", roughness=0.94, relief=0.3,
                                                              relief_distance=0.0004))
    materials.register_builder("battery_label", lambda: _textured("battery_label", "battery_label", roughness=0.38,
                                                                 metallic=0.35, relief=0.25, relief_distance=0.0005))
    materials.register_builder("flash_aluminum", lambda: _textured(
        "flash_aluminum", "brushed_metal", color=(0.30, 0.33, 0.38), roughness=0.34, metallic=1.0, relief=0.2,
        relief_distance=0.0003))
    materials.register_builder("flash_knurled", lambda: _textured(
        "flash_knurled", "knurl", color=(0.24, 0.26, 0.30), roughness=0.46, metallic=1.0, relief=1.2,
        relief_distance=0.0006))
    materials.register_builder("sleeve_cloth", lambda: _textured("sleeve_cloth", "flannel", roughness=0.97, relief=0.5,
                                                                relief_distance=0.0008))


_register_materials()
