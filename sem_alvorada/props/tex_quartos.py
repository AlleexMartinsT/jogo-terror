"""Texturas de superfícies duras dos cômodos de cima: madeira, tinta, porcelana, aço, couro.

São imagens quadradas e tileáveis (256 ou 512 px) em tons sujos e dessaturados, feitas só com numpy.
O veio e as fibras correm no eixo X da imagem; o material gira a textura 90 graus quando o veio precisa
subir (pernas, montantes). Cada função recebe o `random.Random` do nome da textura e devolve um `Canvas`.
"""
import numpy as np

from . import tex_noise as noise
from . import textures

Canvas = textures.Canvas


def _canvas(color):
    """Canvas opaco a partir de um array (altura, largura, 3)."""
    height, width = color.shape[:2]
    canvas = Canvas(width, height)
    canvas.px[..., :3] = np.clip(color, 0.0, 1.0)
    canvas.px[..., 3] = 1.0
    return canvas


def _tone(pattern, gain=1.0):
    """Mapeia um padrão 0..1 para um fator de brilho em torno de 1 (usado para modular um albedo)."""
    return (1.0 + (pattern - 0.5) * 2.0 * gain)[..., None]


# ---------------------------------------------------------------------------
# Madeira
# ---------------------------------------------------------------------------
def draw_wood(rng, size=512, dark=(0.085, 0.050, 0.030), light=(0.250, 0.150, 0.082), rings=9, wear=0.30):
    """Madeira com anéis ondulados, fibras finas, poros escuros e sujeira acumulada."""
    gen = noise.generator(rng)
    warp = noise.fbm(size, size, 2, 2, gen, 3)
    y = np.arange(size, dtype=np.float32)[:, None] / size
    ring = 0.5 + 0.5 * np.sin((y * rings + warp * 1.7) * 2 * np.pi)
    fibre = noise.stretched(size, size, gen, True, 2, 128, 3)
    pattern = 0.40 * ring + 0.60 * fibre
    color = noise.blend(dark, light, noise.smoothstep(0.15, 0.85, pattern))
    pores = noise.stretched(size, size, gen, True, 24, 320, 1) > 0.78
    color = color * (1 - 0.40 * pores[..., None])
    return _canvas(noise.grime(color, gen, wear))


def draw_paint(rng, size=256, wear=0.35):
    """Tinta clara sobre madeira, em tons de cinza para receber a cor do material: pincelada e lascas escuras."""
    gen = noise.generator(rng)
    strokes = noise.stretched(size, size, gen, True, 3, 40, 3)
    shade = 0.80 + 0.20 * strokes
    chipped = noise.smoothstep(0.78, 0.86, noise.fbm(size, size, 14, 14, gen, 3))
    shade = shade * (1 - 0.62 * chipped)
    color = np.repeat(shade[..., None], 3, axis=2)
    return _canvas(noise.grime(color, gen, wear, tone=(0.20, 0.18, 0.14)))


# ---------------------------------------------------------------------------
# Cerâmica, metal, couro
# ---------------------------------------------------------------------------
def draw_porcelain(rng, size=256):
    """Louça encardida: tom marfim, craquelê fino, manchas de ferrugem escorrendo."""
    gen = noise.generator(rng)
    base = noise.blend((0.50, 0.50, 0.46), (0.58, 0.57, 0.52), noise.fbm(size, size, 3, 3, gen, 3))
    level = noise.fbm(size, size, 10, 10, gen, 3)
    crazing = noise.smoothstep(0.010, 0.0, np.abs(level - 0.5)) * 0.55
    color = base * (1 - crazing[..., None])
    streaks = noise.smoothstep(0.62, 0.9, noise.stretched(size, size, gen, False, 2, 40, 2))
    color = noise.blend(color, (0.30, 0.20, 0.10), streaks * 0.45)
    return _canvas(noise.grime(color, gen, 0.18, (0.16, 0.15, 0.11)))


def draw_steel_paint(rng, size=256, paint=(0.20, 0.23, 0.20)):
    """Chapa pintada de arquivo de aço: risco claro, mossa, ferrugem em pontos e poeira."""
    gen = noise.generator(rng)
    brushed = noise.stretched(size, size, gen, True, 2, 180, 2)
    color = np.asarray(paint, np.float32) * _tone(brushed, 0.10)
    scratch = noise.scratches(size, size, gen, count=70)
    color = noise.blend(color, (0.52, 0.52, 0.48), scratch * 0.55)
    rust = noise.smoothstep(0.80, 0.9, noise.fbm(size, size, 12, 12, gen, 3)) * noise.speckle(size, size, gen, 0.35)
    color = noise.blend(color, (0.34, 0.15, 0.06), rust * 0.9)
    return _canvas(noise.grime(color, gen, 0.30, (0.12, 0.11, 0.09)))


def draw_leather(rng, size=256, base=(0.16, 0.085, 0.05)):
    """Couro gasto: granulado de poros, vincos onde dobra e brilho de uso nas áreas altas."""
    gen = noise.generator(rng)
    pebble = noise.fbm(size, size, 64, 64, gen, 2)
    level = noise.fbm(size, size, 5, 5, gen, 3)
    creases = noise.smoothstep(0.018, 0.0, np.abs(level - 0.5))
    color = np.asarray(base, np.float32) * _tone(pebble, 0.22)
    color = color * (1 - 0.55 * creases[..., None])
    polished = noise.smoothstep(0.55, 0.9, noise.fbm(size, size, 3, 3, gen, 2))
    color = noise.blend(color, np.asarray(base) * 1.9, polished * 0.28)
    return _canvas(color)


def draw_plastic(rng, size=128):
    """Plástico fosco levemente granulado (carcaça de rádio-relógio, caixas de brinquedo)."""
    gen = noise.generator(rng)
    grain = noise.fbm(size, size, 32, 32, gen, 2)
    color = np.repeat((0.80 + 0.20 * grain)[..., None], 3, axis=2)
    return _canvas(noise.grime(color, gen, 0.12, (0.2, 0.18, 0.14)))


TEXTURES = {
    "up_wood_dark": lambda rng: draw_wood(rng, 512, (0.075, 0.042, 0.026), (0.215, 0.128, 0.070), 9),
    "up_wood_mid": lambda rng: draw_wood(rng, 512, (0.150, 0.092, 0.050), (0.360, 0.232, 0.125), 6),
    "up_paint": draw_paint,
    "up_porcelain": draw_porcelain,
    "up_steel": draw_steel_paint,
    "up_leather": draw_leather,
    "up_plastic": draw_plastic,
}
textures.TEXTURES.update(TEXTURES)
