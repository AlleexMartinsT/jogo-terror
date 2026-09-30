"""Texturas procedurais do Alto (numpy), baixa resolução para o visual GoldSrc.

Cada função devolve um array float32 (altura, largura, 3) em sRGB, 0..1. Nada aqui toca
o Blender: `materials.py` cuida de virar imagem empacotada.

A textura de pele é um atlas:
    quadrante superior esquerdo  (u 0..0.5, v 0.5..1)  cabeça, com as órbitas escurecidas
    metade direita               (u 0.5..1)            membros, pescoço, mãos e pés
    quadrante inferior esquerdo  (u 0..0.5, v 0..0.5)  peito, com costelas aparentes
"""
import numpy as np

SKIN_SIZE = 128
CLOTH_SIZE = 128

SKIN_BASE = np.array([0.43, 0.44, 0.42], np.float32)
SKIN_SHADE = np.array([0.27, 0.29, 0.30], np.float32)
VEIN_COLOR = np.array([0.10, 0.12, 0.17], np.float32)
CLOTH_BASE = np.array([0.105, 0.098, 0.092], np.float32)

# onde ficam as órbitas dos olhos no quadrante da cabeça (u, v em 0..1 do atlas)
HEAD_ATLAS = (0.0, 0.5, 0.5, 1.0)          # u0, v0, u1, v1
EYE_SOCKET_UV = ((0.215, 0.755), (0.285, 0.755))


def value_noise(size, cells, rng):
    """Ruído de valor periódico (sem emendas) com `cells` células por lado."""
    grid = rng.random((cells, cells)).astype(np.float32)
    coords = np.linspace(0, cells, size, endpoint=False)
    i0 = np.floor(coords).astype(int) % cells
    i1 = (i0 + 1) % cells
    frac = (coords - np.floor(coords)).astype(np.float32)
    frac = frac * frac * (3 - 2 * frac)
    top = grid[np.ix_(i0, i0)] * (1 - frac)[None, :] + grid[np.ix_(i0, i1)] * frac[None, :]
    bottom = grid[np.ix_(i1, i0)] * (1 - frac)[None, :] + grid[np.ix_(i1, i1)] * frac[None, :]
    return top * (1 - frac)[:, None] + bottom * frac[:, None]


def fractal_noise(size, rng, octaves=4, base_cells=4):
    total = np.zeros((size, size), np.float32)
    weight, norm = 1.0, 0.0
    for octave in range(octaves):
        total += weight * value_noise(size, base_cells * 2 ** octave, rng)
        norm += weight
        weight *= 0.5
    return total / norm


def _draw_vein(mask, rng, start, steps, thickness):
    """Passeio aleatório com tendência de direção; deixa um traço fino (toroidal)."""
    size = mask.shape[0]
    x, y = start
    angle = rng.uniform(0, 2 * np.pi)
    for _ in range(steps):
        angle += rng.normal(0, 0.35)
        x = (x + np.cos(angle)) % size
        y = (y + np.sin(angle)) % size
        mask[int(y), int(x)] = 1.0
        if thickness > 1:
            mask[int(y), int(x + 1) % size] = 0.6
        if rng.random() < 0.06:
            _draw_vein(mask, rng, (x, y), steps // 3, 1)


def _vein_mask(size, rng, count=26):
    mask = np.zeros((size, size), np.float32)
    for _ in range(count):
        start = (rng.integers(0, size), rng.integers(0, size))
        _draw_vein(mask, rng, start, int(rng.integers(30, 80)), 1)
    return mask


def _paint_soft_disc(image, center_uv, radius_px, color, strength):
    size_y, size_x = image.shape[:2]
    cx, cy = center_uv[0] * size_x, (1.0 - center_uv[1]) * size_y      # v cresce para cima
    ys, xs = np.mgrid[0:size_y, 0:size_x]
    falloff = np.clip(1.0 - np.hypot(xs - cx, ys - cy) / radius_px, 0.0, 1.0)
    image[:] = image * (1 - strength * falloff[..., None]) + color * strength * falloff[..., None]


def skin_texture(rng, size=SKIN_SIZE):
    """Pele cinza cadavérica com manchas arroxeadas e veias escuras."""
    mottling = fractal_noise(size, rng, octaves=4, base_cells=3)
    fine = value_noise(size, size // 2, rng)
    image = SKIN_BASE + (mottling[..., None] - 0.5) * 0.22 + (fine[..., None] - 0.5) * 0.05
    livid = np.clip((fractal_noise(size, rng, 3, 2) - 0.55) * 4.0, 0.0, 1.0)
    image = image * (1 - 0.55 * livid[..., None]) + SKIN_SHADE * 0.55 * livid[..., None]

    veins = _vein_mask(size, rng)
    image = image * (1 - 0.75 * veins[..., None]) + VEIN_COLOR * 0.75 * veins[..., None]

    _paint_ribs(image, size)
    for socket in EYE_SOCKET_UV:
        _paint_soft_disc(image, socket, radius_px=size * 0.038, color=np.array([0.03, 0.03, 0.04]),
                         strength=0.9)
    return np.clip(image, 0.0, 1.0).astype(np.float32)


def _paint_ribs(image, size):
    """Costelas no quadrante inferior esquerdo: faixas escuras curvas em cima de pele mais fina."""
    half = size // 2
    ys, xs = np.mgrid[0:half, 0:half]
    curve = np.sin((ys + 0.35 * np.abs(xs - half / 2)) * 0.9)
    ribs = np.clip((curve - 0.55) * 3.0, 0.0, 1.0)
    quadrant = image[half:, :half]           # linhas de baixo da imagem = v baixo
    quadrant[:] = quadrant * (1 - 0.6 * ribs[..., None]) + VEIN_COLOR * 0.6 * ribs[..., None]


def cloth_texture(rng, size=CLOTH_SIZE):
    """Sobretudo escuro e velho: trama, manchas, remendos claros e rasgos."""
    ys, xs = np.mgrid[0:size, 0:size]
    weave = 0.5 + 0.5 * np.sin(xs * 1.9) * np.sin(ys * 1.9)
    grime = fractal_noise(size, rng, octaves=5, base_cells=4)
    image = CLOTH_BASE + (grime[..., None] - 0.5) * 0.09 + (weave[..., None] - 0.5) * 0.025

    worn = np.clip((fractal_noise(size, rng, 3, 3) - 0.6) * 5.0, 0.0, 1.0)
    image = image * (1 - worn[..., None]) + np.array([0.15, 0.135, 0.12]) * worn[..., None]

    tears = np.clip((fractal_noise(size, rng, 2, 5) - 0.72) * 9.0, 0.0, 1.0)
    image = image * (1 - tears[..., None]) + np.array([0.012, 0.012, 0.014]) * tears[..., None]

    for _ in range(4):                       # costuras: linhas claras retas e finas
        row = int(rng.integers(0, size))
        image[row, :, :] = image[row, :, :] * 0.6 + np.array([0.16, 0.15, 0.13]) * 0.4
    return np.clip(image, 0.0, 1.0).astype(np.float32)
