"""Ruído tileável em numpy: matéria-prima das texturas procedurais de 256 a 512 px dos quartos.

Todas as funções devolvem arrays `(altura, largura)` de float32 que repetem sem emenda nas bordas, então
o material pode ladrilhar a textura por metro sem que a costura apareça. As imagens usam o eixo X (colunas)
como direção do veio ou do fio: para esticar o ruído ao longo de X, use poucas células em X e muitas em Y.
"""
import numpy as np


def generator(rng):
    """Gerador numpy derivado do `random.Random` do build, para a textura ser reprodutível."""
    return np.random.default_rng(rng.getrandbits(64))


def _smooth(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def value_noise(height, width, cells_y, cells_x, gen):
    """Ruído de valor 0..1 numa grade de `cells_y` x `cells_x` células, interpolada e tileável."""
    grid = gen.random((cells_y, cells_x)).astype(np.float32)
    ys = np.arange(height, dtype=np.float32) * cells_y / height
    xs = np.arange(width, dtype=np.float32) * cells_x / width
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    fy = _smooth(ys - y0)[:, None]
    fx = _smooth(xs - x0)[None, :]
    y0, x0 = y0 % cells_y, x0 % cells_x
    y1, x1 = (y0 + 1) % cells_y, (x0 + 1) % cells_x
    top = grid[np.ix_(y0, x0)] * (1 - fx) + grid[np.ix_(y0, x1)] * fx
    bottom = grid[np.ix_(y1, x0)] * (1 - fx) + grid[np.ix_(y1, x1)] * fx
    return top * (1 - fy) + bottom * fy


def fbm(height, width, cells_y, cells_x, gen, octaves=4, persistence=0.5):
    """Soma de oitavas de `value_noise` (cada uma com o dobro de células), normalizada em 0..1."""
    total = np.zeros((height, width), np.float32)
    amplitude, norm = 1.0, 0.0
    for octave in range(octaves):
        scale = 2 ** octave
        total += amplitude * value_noise(height, width, cells_y * scale, cells_x * scale, gen)
        norm += amplitude
        amplitude *= persistence
    return total / norm


def stretched(height, width, gen, along_x=True, long_cells=3, short_cells=64, octaves=3):
    """Ruído esticado em uma direção: fibras de madeira (along_x) ou de tecido."""
    cells_y, cells_x = (short_cells, long_cells) if along_x else (long_cells, short_cells)
    return fbm(height, width, cells_y, cells_x, gen, octaves)


def blend(low, high, amount):
    """Mistura linear de duas cores RGB por uma máscara `amount` (altura, largura) de 0 a 1."""
    low, high = np.asarray(low, np.float32), np.asarray(high, np.float32)
    amount = np.clip(amount, 0.0, 1.0)[..., None]
    return low * (1 - amount) + high * amount


def smoothstep(edge0, edge1, values):
    """Rampa suave de 0 (em `edge0`) a 1 (em `edge1`); com os limites invertidos a rampa desce."""
    span = np.asarray(edge1 - edge0, np.float32)
    span = np.where(np.abs(span) < 1e-6, 1e-6, span)
    t = np.clip((values - edge0) / span, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def grime(color, gen, amount=0.25, tone=(0.10, 0.09, 0.07), cells=6):
    """Sujeira de baixa frequência: escurece e esfria o albedo em manchas (poeira, gordura, mofo)."""
    height, width = color.shape[:2]
    mask = smoothstep(0.35, 0.85, fbm(height, width, cells, cells, gen, 4)) * amount
    return color * (1 - mask[..., None]) + np.asarray(tone, np.float32) * mask[..., None]


def speckle(height, width, gen, density=0.01):
    """Pontos isolados (0 ou 1): poros, respingos, farelo."""
    return (gen.random((height, width)) < density).astype(np.float32)


def scratches(height, width, gen, count=40, length=(20, 90), angle_jitter=0.35):
    """Riscos finos quase horizontais (0..1) desenhados por amostragem ao longo de segmentos."""
    mask = np.zeros((height, width), np.float32)
    for _ in range(count):
        x0, y0 = gen.uniform(0, width), gen.uniform(0, height)
        size = gen.uniform(*length)
        angle = gen.normal(0.0, angle_jitter)
        steps = np.arange(int(size))
        xs = ((x0 + steps * np.cos(angle)) % width).astype(int)
        ys = ((y0 + steps * np.sin(angle)) % height).astype(int)
        mask[ys, xs] = np.maximum(mask[ys, xs], gen.uniform(0.4, 1.0))
    return mask
