"""Texturas procedurais dos props (numpy puro, 32-256 px, estilo GoldSrc).

Cada `draw_*` devolve um `Canvas` pronto; `image(name)` converte para
`bpy.types.Image` empacotada, com cache por nome. Nada é baixado: tudo é
desenhado com retângulos, elipses, linhas, polígonos e uma fonte de 5x7 pixels.

O Canvas usa origem no canto superior esquerdo (y para baixo), como uma imagem
comum; a inversão vertical que o Blender exige acontece só em `Canvas.pixels`.
"""
import math

import numpy as np

# Fonte 5x7 clássica: 5 colunas por glifo, o bit 0 de cada coluna é a linha de cima.
_GLYPHS = {
    "0": (0x3E, 0x51, 0x49, 0x45, 0x3E), "1": (0x00, 0x42, 0x7F, 0x40, 0x00),
    "2": (0x42, 0x61, 0x51, 0x49, 0x46), "3": (0x21, 0x41, 0x45, 0x4B, 0x31),
    "4": (0x18, 0x14, 0x12, 0x7F, 0x10), "5": (0x27, 0x45, 0x45, 0x45, 0x39),
    "6": (0x3C, 0x4A, 0x49, 0x49, 0x30), "7": (0x01, 0x71, 0x09, 0x05, 0x03),
    "8": (0x36, 0x49, 0x49, 0x49, 0x36), "9": (0x06, 0x49, 0x49, 0x29, 0x1E),
    ":": (0x00, 0x36, 0x36, 0x00, 0x00), "-": (0x08, 0x08, 0x08, 0x08, 0x08),
    ".": (0x00, 0x60, 0x60, 0x00, 0x00), "!": (0x00, 0x00, 0x5F, 0x00, 0x00),
    "?": (0x02, 0x01, 0x51, 0x09, 0x06), " ": (0x00, 0x00, 0x00, 0x00, 0x00),
    "A": (0x7E, 0x11, 0x11, 0x11, 0x7E), "B": (0x7F, 0x49, 0x49, 0x49, 0x36),
    "C": (0x3E, 0x41, 0x41, 0x41, 0x22), "D": (0x7F, 0x41, 0x41, 0x22, 0x1C),
    "E": (0x7F, 0x49, 0x49, 0x49, 0x41), "F": (0x7F, 0x09, 0x09, 0x09, 0x01),
    "G": (0x3E, 0x41, 0x49, 0x49, 0x7A), "H": (0x7F, 0x08, 0x08, 0x08, 0x7F),
    "I": (0x00, 0x41, 0x7F, 0x41, 0x00), "J": (0x20, 0x40, 0x41, 0x3F, 0x01),
    "K": (0x7F, 0x08, 0x14, 0x22, 0x41), "L": (0x7F, 0x40, 0x40, 0x40, 0x40),
    "M": (0x7F, 0x02, 0x0C, 0x02, 0x7F), "N": (0x7F, 0x04, 0x08, 0x10, 0x7F),
    "O": (0x3E, 0x41, 0x41, 0x41, 0x3E), "P": (0x7F, 0x09, 0x09, 0x09, 0x06),
    "Q": (0x3E, 0x41, 0x51, 0x21, 0x5E), "R": (0x7F, 0x09, 0x19, 0x29, 0x46),
    "S": (0x46, 0x49, 0x49, 0x49, 0x31), "T": (0x01, 0x01, 0x7F, 0x01, 0x01),
    "U": (0x3F, 0x40, 0x40, 0x40, 0x3F), "V": (0x1F, 0x20, 0x40, 0x20, 0x1F),
    "W": (0x3F, 0x40, 0x38, 0x40, 0x3F), "X": (0x63, 0x14, 0x08, 0x14, 0x63),
    "Y": (0x07, 0x08, 0x70, 0x08, 0x07), "Z": (0x61, 0x51, 0x49, 0x45, 0x43),
}

# Segmentos de um display de sete segmentos: a topo, b/c direita, d base, e/f esquerda, g meio.
_SEGMENTS_OF_DIGIT = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abfgcd", " ": "",
}


def rgb(value):
    """Aceita (r, g, b) ou (r, g, b, a) e devolve sempre 4 componentes."""
    return tuple(value) if len(value) == 4 else (*value, 1.0)


class Canvas:
    """Imagem RGBA float com primitivas de desenho vetorizadas."""

    def __init__(self, width, height, color=(1.0, 1.0, 1.0, 1.0)):
        self.width, self.height = width, height
        self.px = np.empty((height, width, 4), np.float32)
        self.px[:] = rgb(color)
        self._grid_x, self._grid_y = np.meshgrid(np.arange(width) + 0.5, np.arange(height) + 0.5)

    # -- composição ------------------------------------------------------
    def paint(self, mask, color):
        r, g, b, a = rgb(color)
        under = self.px[mask]
        self.px[mask, :3] = under[:, :3] * (1 - a) + np.array([r, g, b], np.float32) * a
        self.px[mask, 3] = np.maximum(under[:, 3], a)

    def rect(self, x0, y0, x1, y1, color):
        self.paint((self._grid_x >= x0) & (self._grid_x < x1) & (self._grid_y >= y0) & (self._grid_y < y1), color)

    def ellipse(self, cx, cy, rx, ry, color):
        self.paint(((self._grid_x - cx) / rx) ** 2 + ((self._grid_y - cy) / ry) ** 2 <= 1.0, color)

    def line(self, x0, y0, x1, y1, color, width=1.0):
        dx, dy = x1 - x0, y1 - y0
        length_sq = dx * dx + dy * dy or 1e-9
        t = np.clip(((self._grid_x - x0) * dx + (self._grid_y - y0) * dy) / length_sq, 0, 1)
        dist = np.hypot(self._grid_x - (x0 + t * dx), self._grid_y - (y0 + t * dy))
        self.paint(dist <= width / 2, color)

    def polygon(self, points, color):
        """Preenche um polígono (regra par-ímpar), só na caixa que o contém."""
        xs, ys = zip(*points)
        x_lo, x_hi = max(int(min(xs)) - 1, 0), min(int(max(xs)) + 2, self.width)
        y_lo, y_hi = max(int(min(ys)) - 1, 0), min(int(max(ys)) + 2, self.height)
        if x_lo >= x_hi or y_lo >= y_hi:
            return
        gx, gy = self._grid_x[y_lo:y_hi, x_lo:x_hi], self._grid_y[y_lo:y_hi, x_lo:x_hi]
        inside = np.zeros(gx.shape, bool)
        for i in range(len(points)):
            (ax, ay), (bx, by) = points[i], points[(i + 1) % len(points)]
            crosses = (ay > gy) != (by > gy)
            slope_x = (bx - ax) * (gy - ay) / ((by - ay) or 1e-9) + ax
            inside ^= crosses & (gx < slope_x)
        mask = np.zeros((self.height, self.width), bool)
        mask[y_lo:y_hi, x_lo:x_hi] = inside
        self.paint(mask, color)

    def text(self, x, y, string, color, scale=1, spacing=1):
        for ch in string.upper():
            columns = _GLYPHS.get(ch, _GLYPHS[" "])
            for cx, bits in enumerate(columns):
                for row in range(7):
                    if bits >> row & 1:
                        self.rect(x + cx * scale, y + row * scale, x + (cx + 1) * scale, y + (row + 1) * scale, color)
            x += (5 + spacing) * scale

    def text_width(self, string, scale=1, spacing=1):
        return len(string) * (5 + spacing) * scale - spacing * scale

    # -- efeitos ---------------------------------------------------------
    def grain(self, rng, amount):
        """Ruído de luminância por pixel (papel, tecido, cortiça)."""
        noise = np.array([rng.gauss(0, 1) for _ in range(self.width * self.height)], np.float32)
        self.px[..., :3] *= 1 + amount * noise.reshape(self.height, self.width, 1)

    def tint(self, color, amount):
        self.px[..., :3] = self.px[..., :3] * (1 - amount) + np.array(color[:3], np.float32) * amount

    def vignette(self, strength):
        nx = (self._grid_x / self.width - 0.5) * 2
        ny = (self._grid_y / self.height - 0.5) * 2
        falloff = 1 - strength * np.clip(nx ** 2 + ny ** 2, 0, 2) / 2
        self.px[..., :3] *= falloff[..., None]

    def fade(self, amount, toward=(0.62, 0.58, 0.48)):
        """Desbota a imagem: menos contraste e saturação, tom quente de foto antiga."""
        grey = self.px[..., :3].mean(axis=2, keepdims=True)
        washed = grey * 0.55 + self.px[..., :3] * 0.45
        self.px[..., :3] = washed * (1 - amount) + np.array(toward, np.float32) * amount

    def blur(self, passes=1):
        for _ in range(passes):
            p = self.px
            self.px = (p + np.roll(p, 1, 0) + np.roll(p, -1, 0) + np.roll(p, 1, 1) + np.roll(p, -1, 1)) / 5

    def pixels(self):
        """Lista plana RGBA na ordem que o Blender espera (linha de baixo primeiro)."""
        return np.clip(self.px[::-1], 0, 1).astype(np.float32).ravel()

    def scribbles(self, rng, x0, y0, x1, y1, color, line_height, width=1.0, ragged=0.25):
        """Linhas que imitam letra manuscrita: zigue-zague miúdo com espaços entre palavras."""
        y = y0
        while y + line_height <= y1:
            x = x0
            end = x1 - rng.uniform(0, (x1 - x0) * ragged)
            while x < end:
                word = rng.uniform(4, 16)
                px_prev = (x, y)
                steps = int(word / 2)
                for _ in range(max(steps, 1)):
                    nxt = (min(px_prev[0] + rng.uniform(1.5, 3.0), end), y + rng.uniform(-1.2, 1.2) * line_height / 3)
                    self.line(*px_prev, *nxt, color, width)
                    px_prev = nxt
                x = px_prev[0] + rng.uniform(3, 5)
            y += line_height


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def _paper(width, height, base, rng, grain=0.03):
    canvas = Canvas(width, height, base)
    canvas.grain(rng, grain)
    return canvas


def _crease(canvas, x0, y0, x1, y1, strength=0.10):
    canvas.line(x0, y0, x1, y1, (0.0, 0.0, 0.0, strength), 1.0)


# ---------------------------------------------------------------------------
# Despertador, relógio de pé, TV
# ---------------------------------------------------------------------------
def draw_digits(text, width=128, height=64, lit=(1.0, 0.08, 0.05), dim=0.06):
    """Display de sete segmentos (ex.: ' 6:47') sobre fundo escuro, com segmentos apagados visíveis."""
    canvas = Canvas(width, height, (0.015, 0.0, 0.0, 1.0))
    cell = width / 4.6
    thick = max(2.0, cell * 0.16)
    for index, ch in enumerate(text.replace(":", "")):
        x0 = 4 + index * cell + (cell * 0.35 if index >= 2 else 0)
        y0, y1 = 8.0, height - 8.0
        w = cell * 0.78
        mid = (y0 + y1) / 2
        boxes = {"a": (x0 + thick, y0, x0 + w - thick, y0 + thick), "d": (x0 + thick, y1 - thick, x0 + w - thick, y1),
                 "g": (x0 + thick, mid - thick / 2, x0 + w - thick, mid + thick / 2),
                 "f": (x0, y0 + thick, x0 + thick, mid - thick / 2), "b": (x0 + w - thick, y0 + thick, x0 + w, mid - thick / 2),
                 "e": (x0, mid + thick / 2, x0 + thick, y1 - thick), "c": (x0 + w - thick, mid + thick / 2, x0 + w, y1 - thick)}
        for seg, box in boxes.items():
            on = seg in _SEGMENTS_OF_DIGIT.get(ch, "")
            canvas.rect(*box, (*lit, 1.0) if on else (*lit, dim))
    colon_x = 4 + 2 * cell + cell * 0.12
    for cy in (height * 0.36, height * 0.66):
        canvas.rect(colon_x, cy - thick / 2, colon_x + thick, cy + thick / 2, (*lit, 1.0))
    return canvas


def draw_grandfather_face(hour=6, minute=12, size=128):
    """Mostrador de relógio de pé: marfim envelhecido, algarismos em traços, ponteiros parados."""
    canvas = Canvas(size, size, (0.10, 0.07, 0.04, 1.0))
    c = size / 2
    canvas.ellipse(c, c, c * 0.92, c * 0.92, (0.62, 0.58, 0.44, 1.0))
    canvas.ellipse(c, c, c * 0.82, c * 0.82, (0.72, 0.68, 0.52, 1.0))
    for i in range(12):
        angle = math.radians(i * 30)
        inner = 0.60 if i % 3 else 0.52
        canvas.line(c + c * inner * math.sin(angle), c - c * inner * math.cos(angle),
                    c + c * 0.75 * math.sin(angle), c - c * 0.75 * math.cos(angle), (0.12, 0.09, 0.06, 1.0), 2.0 if i % 3 == 0 else 1.0)
    hour_angle = math.radians((hour % 12) * 30 + minute * 0.5)
    minute_angle = math.radians(minute * 6)
    canvas.line(c, c, c + c * 0.40 * math.sin(hour_angle), c - c * 0.40 * math.cos(hour_angle), (0.05, 0.04, 0.03, 1.0), 3.0)
    canvas.line(c, c, c + c * 0.66 * math.sin(minute_angle), c - c * 0.66 * math.cos(minute_angle), (0.05, 0.04, 0.03, 1.0), 2.0)
    canvas.ellipse(c, c, 3, 3, (0.30, 0.22, 0.10, 1.0))
    canvas.tint((0.30, 0.22, 0.10), 0.10)
    return canvas


def draw_tv_static(rng, size=128):
    """Chiado: ruído branco com linhas de varredura e um tom azulado."""
    canvas = Canvas(size, size, (0.5, 0.5, 0.5, 1.0))
    noise = np.array([rng.random() for _ in range(size * size)], np.float32).reshape(size, size)
    scan = 0.75 + 0.25 * (np.arange(size) % 2)[:, None]
    level = np.clip(noise * scan, 0, 1)
    canvas.px[..., 0] = level * 0.80
    canvas.px[..., 1] = level * 0.90
    canvas.px[..., 2] = level * 1.00
    band = rng.randrange(size // 4, size * 3 // 4)
    canvas.px[band:band + 6, :, :3] *= 0.45
    return canvas


# ---------------------------------------------------------------------------
# Mapa da cidade
# ---------------------------------------------------------------------------
def draw_city_map(rng, size=256):
    """Mapa dobrável de Harlan Ridge: grade de ruas, rio, parque e a Rota 33 riscada em vermelho."""
    canvas = _paper(size, size, (0.80, 0.76, 0.62, 1.0), rng, 0.025)
    canvas.rect(0, 0, size, 14, (0.55, 0.50, 0.38, 1.0))
    canvas.text(6, 4, "HARLAN RIDGE - OHIO", (0.12, 0.10, 0.08, 1.0))
    river = [(-10, 70), (60, 90), (110, 120), (150, 160), (210, 175), (270, 230), (270, 250), (200, 200), (140, 190),
             (95, 150), (50, 115), (-10, 92)]
    canvas.polygon(river, (0.48, 0.58, 0.62, 1.0))
    canvas.polygon([(170, 30), (230, 34), (236, 80), (176, 84)], (0.55, 0.64, 0.45, 1.0))
    canvas.polygon([(20, 170), (70, 175), (66, 225), (16, 220)], (0.55, 0.64, 0.45, 1.0))
    street = (0.93, 0.91, 0.84, 1.0)
    for x in range(16, size, 30):
        canvas.line(x + rng.uniform(-1, 1), 16, x + rng.uniform(-1, 1), size, street, 2.0)
    for y in range(34, size, 28):
        canvas.line(0, y + rng.uniform(-1, 1), size, y + rng.uniform(-1, 1), street, 2.0)
    for _ in range(90):
        bx, by = rng.uniform(4, size - 10), rng.uniform(18, size - 10)
        canvas.rect(bx, by, bx + rng.uniform(4, 9), by + rng.uniform(3, 7), (0.66, 0.60, 0.50, 0.55))
    canvas.line(0, 200, 90, 168, (0.95, 0.90, 0.60, 1.0), 4.0)
    canvas.line(90, 168, size, 30, (0.95, 0.90, 0.60, 1.0), 4.0)
    canvas.line(0, 200, 90, 168, (0.75, 0.10, 0.08, 1.0), 2.0)      # Rota 33
    canvas.line(90, 168, size, 30, (0.75, 0.10, 0.08, 1.0), 2.0)
    canvas.text(24, 176, "ROTA 33", (0.6, 0.05, 0.05, 1.0), 1)
    canvas.line(40, 150, 200, 200, (0.55, 0.04, 0.04, 0.9), 3.0)     # riscada com caneta
    canvas.line(40, 200, 200, 150, (0.55, 0.04, 0.04, 0.9), 3.0)
    canvas.ellipse(132, 128, 26, 20, (0.55, 0.04, 0.04, 0.0))
    canvas.text(196, 236, "1 MI", (0.2, 0.18, 0.14, 1.0))
    canvas.line(196, 232, 226, 232, (0.2, 0.18, 0.14, 1.0), 1.0)
    for x in (size // 3, 2 * size // 3):
        _crease(canvas, x, 0, x, size, 0.18)
    _crease(canvas, 0, size // 2, size, size // 2, 0.12)
    canvas.vignette(0.35)
    return canvas


# ---------------------------------------------------------------------------
# Fotos e quadros
# ---------------------------------------------------------------------------
def draw_family_photo(rng, kind, width=64, height=48):
    """Foto de família desbotada. `kind`: trio, mother_child, father_child, portrait."""
    backdrop = {"trio": (0.35, 0.45, 0.42), "mother_child": (0.42, 0.40, 0.30),
                "father_child": (0.40, 0.52, 0.62), "portrait": (0.30, 0.40, 0.58)}[kind]
    canvas = Canvas(width, height, (*backdrop, 1.0))
    if kind == "father_child":
        canvas.rect(0, height * 0.62, width, height, (0.72, 0.66, 0.48, 1.0))
    if kind == "portrait":
        for _ in range(60):
            cx, cy = rng.uniform(0, width), rng.uniform(0, height)
            canvas.ellipse(cx, cy, 4, 3, (0.25, 0.35, 0.60, 0.35))

    def person(cx, head_y, scale, cloth, hair, skin=(0.78, 0.62, 0.52)):
        canvas.polygon([(cx - 9 * scale, height), (cx - 6 * scale, head_y + 9 * scale),
                        (cx + 6 * scale, head_y + 9 * scale), (cx + 9 * scale, height)], (*cloth, 1.0))
        canvas.ellipse(cx, head_y, 4.5 * scale, 5.5 * scale, (*skin, 1.0))
        canvas.ellipse(cx, head_y - 3 * scale, 5 * scale, 3.5 * scale, (*hair, 1.0))

    if kind == "trio":
        person(width * 0.30, height * 0.28, 1.15, (0.18, 0.20, 0.30), (0.18, 0.12, 0.08))
        person(width * 0.70, height * 0.32, 1.05, (0.55, 0.20, 0.22), (0.30, 0.20, 0.10))
        person(width * 0.50, height * 0.55, 0.75, (0.80, 0.70, 0.20), (0.55, 0.40, 0.15))
    elif kind == "mother_child":
        person(width * 0.38, height * 0.30, 1.15, (0.55, 0.20, 0.22), (0.30, 0.20, 0.10))
        person(width * 0.65, height * 0.55, 0.75, (0.80, 0.70, 0.20), (0.55, 0.40, 0.15))
    elif kind == "father_child":
        person(width * 0.36, height * 0.30, 1.2, (0.18, 0.20, 0.30), (0.18, 0.12, 0.08))
        person(width * 0.66, height * 0.52, 0.75, (0.80, 0.70, 0.20), (0.55, 0.40, 0.15))
    else:
        person(width * 0.5, height * 0.40, 1.5, (0.80, 0.70, 0.20), (0.55, 0.40, 0.15))
    canvas.grain(rng, 0.06)
    canvas.vignette(0.5)
    canvas.fade(0.42)
    _crease(canvas, 0, height * 0.3, width, height * 0.72, 0.12)
    return canvas


def draw_painting(rng, kind, width=64, height=48):
    """Quadros de parede genéricos de casa de subúrbio, escurecidos pelo tempo."""
    canvas = Canvas(width, height, (0.35, 0.40, 0.45, 1.0))
    if kind == "lake":
        canvas.rect(0, 0, width, height * 0.5, (0.62, 0.66, 0.68, 1.0))
        canvas.rect(0, height * 0.5, width, height, (0.22, 0.32, 0.38, 1.0))
        canvas.polygon([(0, height * 0.5), (width * 0.3, height * 0.28), (width * 0.55, height * 0.5)], (0.22, 0.28, 0.24, 1.0))
        for x in range(4, width, 9):
            canvas.polygon([(x, height * 0.55), (x + 4, height * 0.25 + rng.uniform(-4, 4)), (x + 8, height * 0.55)], (0.10, 0.20, 0.14, 1.0))
    elif kind == "barn":
        canvas.rect(0, 0, width, height * 0.6, (0.70, 0.66, 0.50, 1.0))
        canvas.rect(0, height * 0.6, width, height, (0.36, 0.42, 0.26, 1.0))
        canvas.rect(width * 0.3, height * 0.35, width * 0.7, height * 0.72, (0.45, 0.14, 0.10, 1.0))
        canvas.polygon([(width * 0.27, height * 0.36), (width * 0.5, height * 0.15), (width * 0.73, height * 0.36)], (0.22, 0.14, 0.12, 1.0))
        canvas.line(width * 0.5, height, width * 0.5, height * 0.72, (0.6, 0.55, 0.4, 1.0), 4.0)
    else:
        canvas.rect(0, 0, width, height, (0.58, 0.52, 0.40, 1.0))
        canvas.rect(width * 0.3, height * 0.55, width * 0.7, height, (0.30, 0.18, 0.10, 1.0))
        canvas.ellipse(width * 0.5, height * 0.55, 9, 12, (0.22, 0.34, 0.42, 1.0))
        for i in range(5):
            canvas.ellipse(width * (0.32 + 0.09 * i), height * (0.28 + 0.05 * (i % 2)), 5, 6, (0.62, 0.20, 0.20, 1.0))
    canvas.grain(rng, 0.05)
    canvas.fade(0.30)
    return canvas


def draw_cracked_mirror(rng, size=128):
    """Espelho de banheiro rachado: vidro azul-escuro com reflexo fraco e trincas em estrela."""
    canvas = Canvas(size, size, (0.06, 0.08, 0.10, 1.0))
    for y in range(size):
        canvas.px[y, :, :3] += 0.10 * (1 - y / size)
    canvas.px[..., :3] *= 0.9 + 0.1 * np.array([[rng.random() for _ in range(size)] for _ in range(4)]).repeat(size // 4, 0)[..., None]
    center = (size * 0.62, size * 0.38)
    for _ in range(11):
        angle = rng.uniform(0, 2 * math.pi)
        length = rng.uniform(size * 0.25, size * 0.9)
        x, y = center
        for _ in range(5):
            step = length / 5
            angle += rng.uniform(-0.35, 0.35)
            nx, ny = x + step * math.cos(angle), y + step * math.sin(angle)
            canvas.line(x, y, nx, ny, (0.78, 0.82, 0.86, 0.85), 1.0)
            x, y = nx, ny
    canvas.ellipse(*center, 3, 3, (0.85, 0.88, 0.92, 0.9))
    return canvas


def draw_plain_mirror(rng, size=64):
    canvas = Canvas(size, size, (0.09, 0.11, 0.13, 1.0))
    for y in range(size):
        canvas.px[y, :, :3] += 0.07 * (1 - y / size)
    canvas.line(size * 0.15, size * 0.9, size * 0.6, size * 0.05, (0.35, 0.40, 0.45, 0.25), 6.0)
    canvas.grain(rng, 0.03)
    return canvas


# ---------------------------------------------------------------------------
# Papéis (as sete notas e o mapa)
# ---------------------------------------------------------------------------
def draw_note_letter(rng, width=64, height=80):
    """Bilhete da Laura: papel creme pautado com letra a caneta azul."""
    canvas = _paper(width, height, (0.86, 0.82, 0.68, 1.0), rng)
    canvas.text(6, 6, "DAN,", (0.12, 0.16, 0.42, 1.0))
    canvas.scribbles(rng, 6, 20, width - 6, height - 14, (0.14, 0.18, 0.44, 1.0), 6)
    canvas.text(6, height - 11, "L.", (0.12, 0.16, 0.42, 1.0))
    _crease(canvas, 0, height / 2, width, height / 2, 0.10)
    return canvas


def draw_envelope(rng, width=64, height=44):
    canvas = _paper(width, height, (0.80, 0.76, 0.62, 1.0), rng, 0.03)
    canvas.line(0, 0, width / 2, height * 0.58, (0.30, 0.26, 0.18, 0.55), 1.0)
    canvas.line(width, 0, width / 2, height * 0.58, (0.30, 0.26, 0.18, 0.55), 1.0)
    canvas.rect(width - 14, 5, width - 5, 15, (0.55, 0.20, 0.18, 0.85))
    canvas.text(8, height - 14, "DAN", (0.14, 0.18, 0.44, 1.0), 1)
    return canvas


def draw_crayon_drawing(rng, width=112, height=144):
    """Desenho da Emma: a casa, um sol amarelo enorme e o moço alto, todo preto, de olhos brancos."""
    canvas = _paper(width, height, (0.90, 0.88, 0.80, 1.0), rng, 0.02)
    canvas.ellipse(width * 0.72, height * 0.26, 30, 30, (0.98, 0.82, 0.10, 1.0))
    for i in range(14):
        angle = i * math.tau / 14
        canvas.line(width * 0.72 + 32 * math.cos(angle), height * 0.26 + 32 * math.sin(angle),
                    width * 0.72 + 46 * math.cos(angle), height * 0.26 + 46 * math.sin(angle), (0.98, 0.78, 0.10, 1.0), 2.5)
    canvas.rect(4, height * 0.72, width - 4, height - 6, (0.35, 0.65, 0.25, 1.0))
    canvas.rect(10, height * 0.50, 44, height * 0.76, (0.80, 0.22, 0.18, 1.0))
    canvas.polygon([(6, height * 0.51), (27, height * 0.34), (48, height * 0.51)], (0.55, 0.30, 0.20, 1.0))
    canvas.rect(21, height * 0.62, 32, height * 0.76, (0.30, 0.20, 0.14, 1.0))
    black = (0.04, 0.04, 0.05, 1.0)
    fx = width * 0.70
    canvas.ellipse(fx, height * 0.43, 6, 7, black)
    canvas.rect(fx - 4, height * 0.47, fx + 4, height * 0.72, black)
    canvas.polygon([(fx - 10, height * 0.50), (fx + 10, height * 0.50), (fx + 5, height * 0.78), (fx - 5, height * 0.78)], black)
    canvas.line(fx - 7, height * 0.52, fx - 22, height * 0.68, black, 3.0)
    canvas.line(fx + 7, height * 0.52, fx + 24, height * 0.70, black, 3.0)
    canvas.ellipse(fx - 2.5, height * 0.42, 2.0, 2.4, (1, 1, 1, 1))
    canvas.ellipse(fx + 2.5, height * 0.42, 2.0, 2.4, (1, 1, 1, 1))
    canvas.text(8, height - 14, "EMMA", (0.75, 0.20, 0.55, 1.0), 1)
    canvas.grain(rng, 0.05)
    for _ in range(60):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        canvas.rect(x, y, x + 1, y + 1, (0.9, 0.88, 0.80, 0.5))
    return canvas


def draw_newspaper_clip(rng, width=96, height=112):
    """Recorte de jornal: cabeçalho, manchete grande e colunas de texto miúdo."""
    canvas = _paper(width, height, (0.74, 0.72, 0.64, 1.0), rng, 0.05)
    canvas.text(6, 4, "GAZETTE", (0.10, 0.10, 0.10, 1.0), 2)
    canvas.rect(4, 20, width - 4, 21, (0.1, 0.1, 0.1, 1.0))
    canvas.text(6, 26, "MENINA DE 7", (0.05, 0.05, 0.05, 1.0), 1)
    canvas.text(6, 36, "ANOS MORRE", (0.05, 0.05, 0.05, 1.0), 1)
    canvas.text(6, 46, "NA ROTA 33", (0.05, 0.05, 0.05, 1.0), 1)
    canvas.rect(6, 58, 40, 90, (0.42, 0.42, 0.40, 1.0))
    canvas.polygon([(8, 88), (20, 70), (30, 80), (38, 66), (38, 88)], (0.30, 0.30, 0.30, 1.0))
    for column in range(2):
        x0 = 44 if column == 0 else 44
        canvas.scribbles(rng, x0, 58 + column * 0, width - 5, 92, (0.25, 0.25, 0.25, 0.8), 3)
    canvas.scribbles(rng, 6, 94, width - 5, height - 3, (0.25, 0.25, 0.25, 0.8), 3)
    canvas.tint((0.35, 0.28, 0.15), 0.10)
    return canvas


def draw_notebook_page(rng, width=80, height=104):
    """Folha de caderno espiral: pautas azuis, margem vermelha, furos e anotações do Dan."""
    canvas = _paper(width, height, (0.86, 0.85, 0.78, 1.0), rng, 0.02)
    for y in range(14, height - 4, 6):
        canvas.line(0, y, width, y, (0.42, 0.52, 0.72, 0.55), 1.0)
    canvas.line(14, 0, 14, height, (0.72, 0.25, 0.25, 0.7), 1.0)
    for y in range(12, height - 8, 22):
        canvas.ellipse(6, y, 2.5, 2.5, (0.25, 0.22, 0.20, 1.0))
    canvas.text(18, 3, "DIA 19", (0.10, 0.12, 0.35, 1.0))
    canvas.scribbles(rng, 18, 16, width - 4, height - 6, (0.10, 0.12, 0.35, 1.0), 6)
    return canvas


def draw_postit(rng, size=64):
    canvas = _paper(size, size, (0.98, 0.90, 0.35, 1.0), rng, 0.03)
    canvas.text(4, 6, "SERTRALINA", (0.12, 0.10, 0.08, 1.0))
    canvas.text(4, 18, "50 MG", (0.12, 0.10, 0.08, 1.0))
    canvas.text(4, 30, "DE MANHA?", (0.12, 0.10, 0.08, 1.0))
    canvas.scribbles(rng, 4, 44, size - 6, size - 6, (0.12, 0.10, 0.08, 1.0), 6)
    canvas.rect(0, 0, size, 3, (1.0, 0.95, 0.55, 0.6))
    return canvas


def draw_prescription(rng, width=72, height=96):
    canvas = _paper(width, height, (0.90, 0.90, 0.88, 1.0), rng, 0.02)
    canvas.rect(0, 0, width, 16, (0.20, 0.32, 0.55, 1.0))
    canvas.text(5, 4, "DR MILLS", (0.92, 0.92, 0.95, 1.0))
    canvas.text(6, 24, "RX", (0.20, 0.32, 0.55, 1.0), 2)
    canvas.scribbles(rng, 6, 44, width - 6, 76, (0.10, 0.12, 0.35, 1.0), 6)
    canvas.line(width * 0.45, height - 12, width - 6, height - 16, (0.10, 0.12, 0.35, 1.0), 1.5)
    canvas.text(6, height - 9, "SESSAO 4", (0.30, 0.30, 0.34, 1.0))
    return canvas


def draw_tow_slip(rng, width=96, height=120):
    """Guia do pátio municipal: formulário em três vias (branca, rosa, amarela)."""
    canvas = _paper(width, height, (0.86, 0.86, 0.82, 1.0), rng, 0.03)
    canvas.rect(0, 0, width, 18, (0.75, 0.35, 0.40, 1.0))
    canvas.text(4, 3, "PATIO MUNICIPAL", (0.12, 0.05, 0.06, 1.0))
    canvas.text(4, 11, "LIBERACAO DE VEICULO", (0.12, 0.05, 0.06, 1.0))
    for y in range(26, 82, 12):
        canvas.rect(4, y, width - 4, y + 9, (0.70, 0.70, 0.66, 1.0))
        canvas.rect(5, y + 1, width - 5, y + 8, (0.90, 0.90, 0.86, 1.0))
        canvas.scribbles(rng, 8, y + 2, width - 10, y + 8, (0.12, 0.12, 0.30, 1.0), 4)
    canvas.rect(0, 92, width, height, (0.92, 0.82, 0.42, 1.0))
    canvas.text(4, 96, "VIA DO TITULAR", (0.20, 0.16, 0.05, 1.0))
    canvas.rect(60, 104, 90, 116, (0.55, 0.1, 0.1, 0.0))
    canvas.line(64, 112, 90, 108, (0.10, 0.10, 0.30, 1.0), 1.5)
    return canvas


def draw_cork(rng, size=64):
    canvas = Canvas(size, size, (0.52, 0.38, 0.22, 1.0))
    canvas.grain(rng, 0.18)
    for _ in range(80):
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        canvas.ellipse(x, y, rng.uniform(0.8, 2.0), rng.uniform(0.8, 1.6), (0.32, 0.22, 0.12, 0.8))
    for _ in range(50):
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        canvas.ellipse(x, y, rng.uniform(0.8, 1.6), rng.uniform(0.8, 1.6), (0.68, 0.52, 0.32, 0.8))
    return canvas


def draw_clippings(rng, width=96, height=112):
    """Placa de cortiça do escritório: recortes, fotos e linha vermelha ligando tudo."""
    canvas = draw_cork(rng, 64)
    board = Canvas(width, height, (0.5, 0.36, 0.2, 1.0))
    for ty in range(0, height, 64):
        for tx in range(0, width, 64):
            board.px[ty:ty + 64, tx:tx + 64] = canvas.px[:min(64, height - ty), :min(64, width - tx)]
    anchors = []
    for _ in range(9):
        cx, cy = rng.uniform(12, width - 12), rng.uniform(12, height - 12)
        w, h = rng.uniform(12, 22), rng.uniform(10, 24)
        tone = rng.choice([(0.78, 0.76, 0.66), (0.66, 0.64, 0.56), (0.86, 0.84, 0.74)])
        board.rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, (*tone, 1.0))
        board.scribbles(rng, cx - w / 2 + 2, cy - h / 2 + 2, cx + w / 2 - 2, cy + h / 2 - 2, (0.2, 0.2, 0.2, 0.9), 3)
        board.ellipse(cx, cy - h / 2 + 2, 1.5, 1.5, (0.8, 0.1, 0.1, 1.0))
        anchors.append((cx, cy - h / 2 + 2))
    for a, b in zip(anchors, anchors[3:] + anchors[:3]):
        board.line(*a, *b, (0.70, 0.08, 0.08, 0.9), 1.0)
    return board


def draw_book_spines(rng, width=128, height=32):
    """Faixa de lombadas coloridas e desbotadas; repete na horizontal."""
    canvas = Canvas(width, height, (0.10, 0.08, 0.06, 1.0))
    palette = [(0.42, 0.16, 0.14), (0.16, 0.24, 0.36), (0.22, 0.34, 0.24), (0.55, 0.45, 0.25),
               (0.30, 0.22, 0.34), (0.60, 0.58, 0.50), (0.20, 0.20, 0.22), (0.50, 0.30, 0.18)]
    x = 0.0
    while x < width:
        w = rng.uniform(3, 7)
        top = rng.uniform(0, 5)
        color = rng.choice(palette)
        canvas.rect(x, top, x + w - 0.6, height, (*color, 1.0))
        canvas.rect(x, top + height * 0.25, x + w - 0.6, top + height * 0.32, (0.85, 0.80, 0.60, 0.7))
        x += w
    canvas.grain(rng, 0.06)
    return canvas


def draw_rug(rng, size=128, base=(0.32, 0.12, 0.10), accent=(0.70, 0.60, 0.38)):
    """Tapete de padrão losango com bordas."""
    canvas = Canvas(size, size, (*base, 1.0))
    canvas.rect(0, 0, size, 8, (*accent, 1.0))
    canvas.rect(0, size - 8, size, size, (*accent, 1.0))
    canvas.rect(0, 0, 8, size, (*accent, 1.0))
    canvas.rect(size - 8, 0, size, size, (*accent, 1.0))
    canvas.rect(12, 12, size - 12, size - 12, (*base, 1.0))
    c = size / 2
    for radius, color in ((44, accent), (34, base), (22, (0.18, 0.20, 0.30)), (10, accent)):
        canvas.polygon([(c, c - radius), (c + radius, c), (c, c + radius), (c - radius, c)], (*color, 1.0))
    canvas.grain(rng, 0.08)
    canvas.fade(0.20, (0.35, 0.30, 0.25))
    return canvas


def draw_plaid(rng, size=64, base=(0.30, 0.16, 0.14), stripe=(0.55, 0.50, 0.38)):
    canvas = Canvas(size, size, (*base, 1.0))
    for i in range(0, size, 16):
        canvas.rect(i, 0, i + 5, size, (*stripe, 0.55))
        canvas.rect(0, i, size, i + 5, (*stripe, 0.55))
    canvas.grain(rng, 0.07)
    return canvas


def draw_stars_comforter(rng, size=64):
    """Coberta infantil lilás com estrelinhas amarelas desbotadas."""
    canvas = Canvas(size, size, (0.50, 0.38, 0.58, 1.0))
    for cx, cy in ((10, 10), (42, 18), (24, 40), (54, 50), (8, 54)):
        pts = []
        for i in range(10):
            radius = 6 if i % 2 == 0 else 2.6
            angle = -math.pi / 2 + i * math.pi / 5
            pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        canvas.polygon(pts, (0.88, 0.78, 0.35, 1.0))
    canvas.grain(rng, 0.05)
    canvas.fade(0.15, (0.45, 0.40, 0.45))
    return canvas


def draw_linen(rng, size=64, base=(0.66, 0.64, 0.58)):
    canvas = Canvas(size, size, (*base, 1.0))
    canvas.grain(rng, 0.04)
    for _ in range(8):
        y = rng.uniform(0, size)
        canvas.line(0, y, size, y + rng.uniform(-6, 6), (0, 0, 0, 0.07), 2.0)
    return canvas


def draw_shower_curtain(rng, size=64):
    canvas = Canvas(size, size, (0.62, 0.70, 0.66, 1.0))
    for _ in range(26):
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        canvas.ellipse(x, y, 3, 3, (0.78, 0.84, 0.80, 1.0))
    for _ in range(22):
        x, y = rng.uniform(0, size), rng.uniform(size * 0.6, size)
        canvas.ellipse(x, y, rng.uniform(2, 4), rng.uniform(2, 4), (0.20, 0.26, 0.18, 0.35))
    canvas.grain(rng, 0.04)
    return canvas


def draw_cardboard(rng, label=None, size=64):
    canvas = Canvas(size, size, (0.50, 0.38, 0.24, 1.0))
    canvas.grain(rng, 0.08)
    canvas.rect(0, size * 0.44, size, size * 0.56, (0.78, 0.72, 0.55, 0.85))      # fita adesiva
    if label:
        canvas.text(max(4, (size - canvas.text_width(label, 2)) // 2), 8, label, (0.06, 0.05, 0.05, 1.0), 2)
    return canvas


def draw_can_labels(rng, width=64, height=24):
    canvas = Canvas(width, height, (0.7, 0.7, 0.66, 1.0))
    for i in range(0, width, 16):
        color = rng.choice([(0.72, 0.16, 0.12), (0.18, 0.34, 0.60), (0.20, 0.50, 0.28), (0.85, 0.75, 0.20)])
        canvas.rect(i, 0, i + 16, height, (*color, 1.0))
        canvas.rect(i, height * 0.4, i + 16, height * 0.65, (0.92, 0.90, 0.80, 1.0))
    canvas.grain(rng, 0.05)
    return canvas


def draw_calendar(rng, width=48, height=64):
    """Calendário de parede parado em junho: quase todos os dias riscados."""
    canvas = _paper(width, height, (0.86, 0.84, 0.76, 1.0), rng, 0.02)
    canvas.rect(0, 0, width, 14, (0.55, 0.20, 0.18, 1.0))
    canvas.text(6, 4, "JUNHO", (0.95, 0.92, 0.85, 1.0))
    for row in range(5):
        for col in range(7):
            x, y = 3 + col * 6, 20 + row * 8
            canvas.rect(x, y, x + 4, y + 4, (0.25, 0.25, 0.25, 0.75))
            if row * 7 + col < 24:
                canvas.line(x - 1, y - 1, x + 5, y + 5, (0.6, 0.05, 0.05, 0.9), 1.0)
    return canvas


def draw_fridge_front(rng, width=96, height=192):
    """Porta da geladeira: creme encardido, desenhos infantis e ímãs de letras que formam EMMA."""
    canvas = Canvas(width, height, (0.62, 0.60, 0.53, 1.0))
    canvas.grain(rng, 0.03)
    canvas.rect(0, height * 0.31, width, height * 0.31 + 2, (0.20, 0.19, 0.17, 1.0))
    for _ in range(9):
        x = rng.uniform(4, width - 10)
        canvas.rect(x, height * 0.28, x + 3, height, (0.35, 0.33, 0.28, 0.06))
    canvas.rect(10, height * 0.40, 46, height * 0.56, (0.90, 0.88, 0.80, 1.0))
    canvas.ellipse(28, height * 0.46, 8, 8, (0.98, 0.80, 0.10, 1.0))
    canvas.rect(16, height * 0.50, 26, height * 0.55, (0.78, 0.22, 0.18, 1.0))
    canvas.rect(52, height * 0.62, 88, height * 0.78, (0.92, 0.90, 0.84, 1.0))
    canvas.scribbles(rng, 55, height * 0.65, 85, height * 0.77, (0.55, 0.25, 0.60, 1.0), 6, 1.5)
    for i, letter in enumerate("EMMA"):
        color = [(0.75, 0.20, 0.20), (0.20, 0.35, 0.70), (0.85, 0.70, 0.15), (0.25, 0.55, 0.30)][i]
        canvas.rect(8 + i * 11, height * 0.83, 8 + i * 11 + 9, height * 0.83 + 9, (*color, 1.0))
        canvas.text(9 + i * 11, height * 0.83 + 1, letter, (1, 1, 1, 1.0))
    return canvas


def draw_letter_block(letter, base=(0.75, 0.20, 0.20), size=32):
    canvas = Canvas(size, size, (*base, 1.0))
    canvas.rect(2, 2, size - 2, size - 2, (0.90, 0.85, 0.70, 1.0))
    canvas.text(size // 2 - 8, size // 2 - 10, letter, (*base, 1.0), 3)
    return canvas


def draw_stain(rng, size=64, color=(0.16, 0.04, 0.03)):
    """Mancha irregular com alfa (decal sobre tapete ou piso)."""
    canvas = Canvas(size, size, (*color, 0.0))
    c = size / 2
    canvas.ellipse(c, c, size * 0.33, size * 0.27, (*color, 0.85))
    for _ in range(9):
        angle = rng.uniform(0, math.tau)
        dist = rng.uniform(size * 0.15, size * 0.32)
        canvas.ellipse(c + dist * math.cos(angle), c + dist * math.sin(angle),
                       rng.uniform(4, 11), rng.uniform(4, 9), (*color, 0.7))
    for _ in range(6):
        angle = rng.uniform(0, math.tau)
        canvas.ellipse(c + size * 0.42 * math.cos(angle), c + size * 0.42 * math.sin(angle), 2, 2, (*color, 0.7))
    canvas.blur(1)
    canvas.px[..., 3] *= 0.9
    return canvas


def draw_handprints(rng, size=64):
    """Duas marcas de mão pequenas, escuras, como se arrastadas na parede (decal com alfa)."""
    canvas = Canvas(size, size, (0.14, 0.03, 0.03, 0.0))
    for cx, cy, tilt in ((size * 0.30, size * 0.55, -0.15), (size * 0.68, size * 0.42, 0.2)):
        canvas.ellipse(cx, cy + 4, 7, 8, (0.14, 0.03, 0.03, 0.85))
        for i in range(5):
            angle = tilt + (-0.85 + i * 0.4) + math.pi
            canvas.line(cx + 5 * math.sin(-angle + math.pi), cy - 2, cx + 9 * math.sin(-angle + math.pi) * 1.1,
                        cy - 14 + abs(i - 2) * 2.5, (0.14, 0.03, 0.03, 0.85), 2.4)
        canvas.line(cx, cy + 10, cx + 3, cy + 24, (0.14, 0.03, 0.03, 0.5), 3.0)
    canvas.blur(1)
    return canvas


def draw_oil_stain(rng, size=64):
    return draw_stain(rng, size, (0.03, 0.03, 0.035))


def draw_step_marks(size=32):
    canvas = Canvas(size, size, (0.7, 0.7, 0.7, 1.0))
    return canvas


def draw_appliance_panel(rng, size=64, base=(0.60, 0.58, 0.52)):
    canvas = Canvas(size, size, (*base, 1.0))
    canvas.grain(rng, 0.03)
    for _ in range(6):
        x = rng.uniform(0, size)
        canvas.rect(x, 0, x + 2, size, (0.25, 0.22, 0.15, 0.07))
    return canvas


def draw_laminate(rng, size=64):
    """Bancada de laminado cinza-esverdeado salpicado."""
    canvas = Canvas(size, size, (0.36, 0.38, 0.34, 1.0))
    for _ in range(120):
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        tone = rng.choice([(0.26, 0.28, 0.24), (0.46, 0.48, 0.42)])
        canvas.rect(x, y, x + 1.5, y + 1.5, (*tone, 0.9))
    canvas.grain(rng, 0.04)
    return canvas


def draw_wood_veneer(rng, size=64, base=(0.30, 0.19, 0.11)):
    canvas = Canvas(size, size, (*base, 1.0))
    for y in range(size):
        wobble = 0.06 * math.sin(y * 0.6 + rng.uniform(0, 0.4)) + rng.uniform(-0.03, 0.03)
        canvas.px[y, :, :3] *= 1 + wobble
    canvas.grain(rng, 0.03)
    return canvas


# ---------------------------------------------------------------------------
# Registro: nome -> função (e argumentos) que gera o Canvas
# ---------------------------------------------------------------------------
TEXTURES = {
    "digits_647": lambda rng: draw_digits(" 6:47"),
    "digits_612": lambda rng: draw_digits(" 6:12"),
    "digits_dash": lambda rng: draw_digits(" 6:12", 96, 48, (0.35, 1.0, 0.45)),
    "clock_face": lambda rng: draw_grandfather_face(6, 12),
    "tv_static": draw_tv_static,
    "city_map": draw_city_map,
    "photo_trio": lambda rng: draw_family_photo(rng, "trio"),
    "photo_mother_child": lambda rng: draw_family_photo(rng, "mother_child"),
    "photo_father_child": lambda rng: draw_family_photo(rng, "father_child"),
    "photo_portrait": lambda rng: draw_family_photo(rng, "portrait"),
    "painting_lake": lambda rng: draw_painting(rng, "lake"),
    "painting_barn": lambda rng: draw_painting(rng, "barn"),
    "painting_still": lambda rng: draw_painting(rng, "still"),
    "mirror_cracked": draw_cracked_mirror,
    "mirror_plain": draw_plain_mirror,
    "note_letter": draw_note_letter,
    "note_envelope": draw_envelope,
    "note_crayon": draw_crayon_drawing,
    "note_newspaper": draw_newspaper_clip,
    "note_notebook": draw_notebook_page,
    "note_postit": draw_postit,
    "note_prescription": draw_prescription,
    "note_tow": draw_tow_slip,
    "cork_clippings": draw_clippings,
    "book_spines": draw_book_spines,
    "rug_red": lambda rng: draw_rug(rng),
    "rug_blue": lambda rng: draw_rug(rng, 128, (0.14, 0.18, 0.28), (0.62, 0.55, 0.40)),
    "rug_runner": lambda rng: draw_rug(rng, 64, (0.22, 0.26, 0.20), (0.55, 0.48, 0.34)),
    "plaid_blanket": draw_plaid,
    "comforter_stars": draw_stars_comforter,
    "linen_sheet": draw_linen,
    "linen_dirty": lambda rng: draw_linen(rng, 64, (0.50, 0.48, 0.42)),
    "shower_curtain": draw_shower_curtain,
    "cardboard": draw_cardboard,
    "cardboard_emma": lambda rng: draw_cardboard(rng, "EMMA"),
    "cardboard_toys": lambda rng: draw_cardboard(rng, "BRINQ."),
    "can_labels": draw_can_labels,
    "calendar": draw_calendar,
    "fridge_front": draw_fridge_front,
    "block_e": lambda rng: draw_letter_block("E", (0.75, 0.20, 0.20)),
    "block_m": lambda rng: draw_letter_block("M", (0.20, 0.35, 0.70)),
    "block_a": lambda rng: draw_letter_block("A", (0.25, 0.55, 0.30)),
    "stain_dark": draw_stain,
    "handprints": draw_handprints,
    "stain_oil": draw_oil_stain,
    "appliance_panel": draw_appliance_panel,
    "laminate": draw_laminate,
    "veneer_dark": lambda rng: draw_wood_veneer(rng, 64, (0.24, 0.15, 0.09)),
    "veneer_mid": lambda rng: draw_wood_veneer(rng, 64, (0.36, 0.23, 0.13)),
}


def canvas_for(name, seed=90210):
    """Gera o Canvas da textura `name`; a semente depende do nome, então é reprodutível."""
    import random
    rng = random.Random(f"{seed}:{name}")
    return TEXTURES[name](rng)


def image(name):
    """`bpy.types.Image` empacotada da textura `name` (cache por nome no .blend)."""
    import bpy
    existing = bpy.data.images.get(name)
    if existing is not None:
        return existing
    canvas = canvas_for(name)
    img = bpy.data.images.new(name, canvas.width, canvas.height, alpha=True)
    img.pixels.foreach_set(canvas.pixels())
    img.pack()
    img.update()
    return img
