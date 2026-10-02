"""Texturas procedurais do corpo: pele, flanela, jeans, couro, unha. Só numpy.

Cada função devolve um array (H, W, 4) float32: RGB em sRGB e ALFA = ALTURA para o relevo (0,5 é o nível da
superfície; o material usa o alfa como altura do Bump, nunca como transparência). A origem é embaixo à esquerda
(v para cima), a mesma do Blender, então o array já é gravado sem inverter.

Duas famílias, como as UVs da malha pedem:
* `tile_*`: repetem em escala de mundo (UVTile). Trama, xadrez, couro, poros.
* `atlas_*`: não repetem (UVMap). Costuras, desgaste, sujeira, veias, rugas, marcas de uso.
"""
import math

import numpy as np

SIZE = 512
TWO_PI = 2.0 * math.pi


# --------------------------------------------------------------------------
# Ruído
# --------------------------------------------------------------------------
def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def value_noise(height, width, cells_y, cells_x, rng, wrap=True):
    """Ruído de valor suave em [0,1], com `cells` células por eixo (ladrilhável se `wrap`)."""
    grid = rng.random((cells_y + 1, cells_x + 1)).astype(np.float32)
    if wrap:
        grid[-1, :], grid[:, -1] = grid[0, :], grid[:, 0]
    ys = np.arange(height, dtype=np.float32) * cells_y / height
    xs = np.arange(width, dtype=np.float32) * cells_x / width
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = _smooth(ys - y0)[:, None], _smooth(xs - x0)[None, :]
    a, b = grid[y0][:, x0], grid[y0][:, x0 + 1]
    c, d = grid[y0 + 1][:, x0], grid[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(height, width, rng, octaves=5, cells=4, gain=0.5, wrap=True):
    """Soma de oitavas de ruído de valor, normalizada para [0,1]."""
    total = np.zeros((height, width), np.float32)
    amplitude, norm = 1.0, 0.0
    for octave in range(octaves):
        n = cells * (2 ** octave)
        total += amplitude * value_noise(height, width, n, n, rng, wrap)
        norm += amplitude
        amplitude *= gain
    return total / norm


def gaussian(x, sigma):
    return np.exp(-(x / sigma) ** 2)


def wrap_angle(a):
    return (a + math.pi) % TWO_PI - math.pi


def mix(base, color, amount):
    """base (H,W,3) misturado com `color` por `amount` (H,W) em [0,1]."""
    amount = np.clip(amount, 0.0, 1.0)[..., None]
    return base * (1.0 - amount) + np.asarray(color, np.float32) * amount


def new_layer(height, width, color):
    px = np.empty((height, width, 4), np.float32)
    px[..., :3] = color
    px[..., 3] = 0.5
    return px


def stroke_into(layer, x0, y0, x1, y1, width, color, alpha=1.0, height_delta=0.0):
    """Traço com bordas suaves num array (H,W,4); só toca o retângulo do segmento."""
    h, w = layer.shape[:2]
    pad = width / 2.0 + 1.5
    xa, xb = int(max(0, min(x0, x1) - pad)), int(min(w, max(x0, x1) + pad + 1))
    ya, yb = int(max(0, min(y0, y1) - pad)), int(min(h, max(y0, y1) + pad + 1))
    if xb <= xa or yb <= ya:
        return
    gx, gy = np.meshgrid(np.arange(xa, xb) + 0.5, np.arange(ya, yb) + 0.5)
    dx, dy = x1 - x0, y1 - y0
    span = dx * dx + dy * dy or 1e-9
    t = np.clip(((gx - x0) * dx + (gy - y0) * dy) / span, 0, 1)
    distance = np.hypot(gx - (x0 + t * dx), gy - (y0 + t * dy))
    cover = np.clip(width / 2.0 + 0.5 - distance, 0, 1) * alpha
    region = layer[ya:yb, xa:xb]
    region[..., :3] = region[..., :3] * (1 - cover[..., None]) + np.asarray(color, np.float32) * cover[..., None]
    region[..., 3] += height_delta * cover


# --------------------------------------------------------------------------
# Pele
# --------------------------------------------------------------------------
SKIN_BASE = np.array((0.70, 0.55, 0.47), np.float32)
SKIN_RED = np.array((0.74, 0.40, 0.36), np.float32)
SKIN_VEIN = np.array((0.46, 0.51, 0.60), np.float32)
SKIN_DIRT = np.array((0.29, 0.23, 0.18), np.float32)
SKIN_HAIR = np.array((0.20, 0.14, 0.10), np.float32)
ARM_D0, ARM_D1 = -0.200, 0.098          # alcance do antebraço+mão (m) mapeado em v = 0..1
ARM_ATLAS = {"R": (0.00, 0.00, 0.28, 1.0), "L": (0.50, 0.00, 0.78, 1.0)}
FINGER_COLUMN = 0.036
FINGER_ROWS = 0.46


def finger_rect(side, index):
    """Retângulo (u0, v0, u1, v1) do atlas da pele para o dedo `index` (0 indicador ... 3 mindinho, 4 polegar)."""
    base = 0.28 if side == "R" else 0.78
    return (base + index * FINGER_COLUMN, 0.0, base + (index + 1) * FINGER_COLUMN, FINGER_ROWS)


def _region_grid(size, rect):
    """Coordenadas em pixels da região `rect` do atlas, u e v em [0,1] dentro dela."""
    x0, y0, x1, y1 = (int(round(r * size)) for r in rect)
    u = (np.arange(x0, x1) + 0.5 - x0) / (x1 - x0)
    v = (np.arange(y0, y1) + 0.5 - y0) / (y1 - y0)
    return (x0, y0, x1, y1), np.broadcast_to(u[None, :], (y1 - y0, x1 - x0)), np.broadcast_to(v[:, None], (y1 - y0, x1 - x0))


def _paint_arm(layer, side, rng):
    size = layer.shape[0]
    (x0, y0, x1, y1), u, v = _region_grid(size, ARM_ATLAS[side])
    theta = math.pi + TWO_PI * u               # seção do anel: 0 = lado do polegar, pi/2 = palma, 3pi/2 = dorso
    d = ARM_D0 + (ARM_D1 - ARM_D0) * v
    h, w = u.shape
    rgb = np.empty((h, w, 3), np.float32)
    rgb[:] = SKIN_BASE
    mottle = fbm(h, w, rng, 5, 3, 0.55, wrap=False)
    rgb *= (0.92 + 0.16 * mottle)[..., None]
    rgb[..., 0] += 0.04 * (fbm(h, w, rng, 4, 2, 0.5, wrap=False) - 0.5)
    height = np.full((h, w), 0.5, np.float32)
    dorsal = np.exp(-(wrap_angle(theta - 1.5 * math.pi) / 1.25) ** 2)
    palm = np.exp(-(wrap_angle(theta - 0.5 * math.pi) / 1.1) ** 2)
    # palma mais rosada, dorso mais pálido; antebraço mais claro perto do cotovelo
    rgb = mix(rgb, (0.74, 0.46, 0.42), 0.45 * palm * np.clip((d + 0.01) / 0.05, 0, 1))
    rgb = mix(rgb, (0.78, 0.66, 0.58), 0.25 * dorsal * (d < 0.0))
    # nós dos dedos e cristas dos tendões ficam avermelhados
    for finger, lateral in (("Index", 0.0305), ("Middle", 0.0105), ("Ring", -0.0105), ("Pinky", -0.0295)):
        angle = 1.5 * math.pi + lateral / 0.042
        knuckle = gaussian(d - {"Index": 0.093, "Middle": 0.096, "Ring": 0.091, "Pinky": 0.081}[finger], 0.008) \
            * gaussian(wrap_angle(theta - angle), 0.35)
        rgb = mix(rgb, SKIN_RED, 0.55 * knuckle)
        height -= 0.10 * knuckle * (fbm(h, w, rng, 3, 24, 0.5, wrap=False) > 0.5)
        for k in range(4):                                         # rugas transversais no nó
            offset = (k - 1.5) * 0.0035
            height -= 0.06 * gaussian(d - (0.093 + offset), 0.0007) * gaussian(wrap_angle(theta - angle), 0.28)
    # veias no dorso da mão e do punho
    for index, base_angle in enumerate((-0.45, -0.10, 0.22, 0.55)):
        path = 1.5 * math.pi + base_angle + 0.12 * np.sin(d * (24 + 6 * index) + index * 1.7) * np.clip((d + 0.1) / 0.1, 0, 1)
        vein = gaussian(wrap_angle(theta - path), 0.045 - 0.006 * (d < 0)) * np.clip((0.085 - d) / 0.03, 0, 1) \
            * np.clip((d + 0.17) / 0.06, 0, 1)
        vein *= 0.6 + 0.4 * fbm(h, w, rng, 3, 6, 0.5, wrap=False)
        rgb = mix(rgb, SKIN_VEIN, 0.34 * vein * dorsal)
        height += 0.10 * vein * dorsal
    # rugas do punho e vincos da palma
    for offset in (-0.010, -0.002):
        height -= 0.22 * gaussian(d - offset, 0.0009) * palm
        rgb = mix(rgb, SKIN_DIRT, 0.20 * gaussian(d - offset, 0.0010) * palm)
    for center, tilt, depth in ((0.074, 0.0, 0.22), (0.056, 0.012, 0.20), (0.034, -0.01, 0.16)):
        arc = center + tilt * np.cos(wrap_angle(theta - 0.5 * math.pi) * 2.2)
        line = gaussian(d - arc, 0.0009) * gaussian(wrap_angle(theta - (0.5 * math.pi + 0.15)), 0.55)
        height -= depth * line
        rgb = mix(rgb, SKIN_DIRT, 0.30 * line)
    thenar = gaussian(d - 0.050, 0.020) * gaussian(wrap_angle(theta - 0.80), 0.40)         # linha da vida em torno do tênar
    arc = 0.026 + 0.028 * np.sin(np.clip(wrap_angle(theta - 0.15) / 1.0, -1.6, 1.6))       # linha da vida: curva em volta do tênar
    life = gaussian(d - arc, 0.0010) * gaussian(wrap_angle(theta - 0.55), 0.62) * (d > 0.015)
    height -= 0.18 * life
    rgb = mix(rgb, SKIN_DIRT, 0.22 * life)
    # sujeira em manchas, sempre mais forte perto dos vincos e do punho
    grime = np.clip((fbm(h, w, rng, 5, 5, 0.55, wrap=False) - 0.52) * 3.2, 0, 1)
    rgb = mix(rgb, SKIN_DIRT, 0.55 * grime * (0.5 + 0.5 * gaussian(d + 0.01, 0.12)))
    smear = np.clip((fbm(h, w, rng, 4, 3, 0.5, wrap=False) - 0.62) * 4.0, 0, 1)
    rgb = mix(rgb, (0.18, 0.15, 0.13), 0.40 * smear)
    # poros finos e pelos
    height += 0.035 * (rng.random((h, w)).astype(np.float32) - 0.5)
    layer[y0:y1, x0:x1, :3] = rgb
    layer[y0:y1, x0:x1, 3] = height
    _hairs(layer, (x0, y0, x1, y1), d, theta, rng, side)
    _marks(layer, (x0, y0, x1, y1), side, rng)


def _hairs(layer, box, d, theta, rng, side):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for _ in range(360):
        u = rng.uniform(0.08, 0.42)                       # metade dorsal: u de 0,08 a 0,42 (theta de 3pi/2 +-)
        v = rng.uniform(0.0, 0.80)
        if rng.random() < 0.3:
            v = rng.uniform(0.0, 0.5)
        length = rng.uniform(3.0, 7.0)
        angle = rng.normal(math.pi / 2, 0.5)
        x, y = x0 + u * w, y0 + v * h
        stroke_into(layer, x, y, x + math.cos(angle) * length * 0.35, y + math.sin(angle) * length, 0.7,
                    (0.36, 0.27, 0.21), 0.20 * (1.0 - v * 0.7))


def _marks(layer, box, side, rng):
    """Marcas de cada mão: arranhões nas costas da mão direita, cicatriz fina na esquerda, manchas de óleo."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if side == "R":
        for _ in range(3):
            x = x0 + rng.uniform(0.15, 0.40) * w
            y = y0 + rng.uniform(0.70, 0.90) * h
            stroke_into(layer, x, y, x + rng.uniform(-6, 6), y + rng.uniform(14, 30), 1.1, (0.55, 0.28, 0.26), 0.7, -0.10)
        stroke_into(layer, x0 + 0.62 * w, y0 + 0.62 * h, x0 + 0.70 * w, y0 + 0.74 * h, 2.0, (0.60, 0.46, 0.42), 0.6, 0.05)
    else:
        stroke_into(layer, x0 + 0.20 * w, y0 + 0.40 * h, x0 + 0.34 * w, y0 + 0.54 * h, 2.6, (0.80, 0.68, 0.62), 0.75, 0.10)
        for k in range(5):
            xx = x0 + (0.22 + 0.025 * k) * w
            stroke_into(layer, xx - 3, y0 + (0.455 + 0.02 * k) * h, xx + 3, y0 + (0.462 + 0.02 * k) * h, 1.0,
                        (0.70, 0.55, 0.50), 0.5, 0.04)


def _paint_finger(layer, side, index, finger, rng):
    size = layer.shape[0]
    rect = finger_rect(side, index)
    (x0, y0, x1, y1), u, v = _region_grid(size, rect)
    h, w = u.shape
    from . import skeleton as S
    if finger == "Thumb":
        lengths = (0.048, 0.034, 0.028)
        total = sum(lengths) + 0.006
        edges = (0.0, lengths[0], lengths[0] + lengths[1])
        start = -0.006
        b = start + v * (total - start + 0.002)
    else:
        l1, l2, l3 = S.PHALANX[finger]
        total = l1 + l2 + l3
        edges = (l1, l1 + l2)
        b = -0.012 + v * (total + 0.012)
    theta = math.pi + TWO_PI * u                 # 3pi/2 = dorso (unha), pi/2 = polpa
    rgb = np.empty((h, w, 3), np.float32)
    rgb[:] = SKIN_BASE
    mottle = fbm(h, w, rng, 4, 2, 0.5, wrap=False)
    rgb *= (0.93 + 0.14 * mottle)[..., None]
    height = np.full((h, w), 0.5, np.float32)
    dorsal = np.exp(-(wrap_angle(theta - 1.5 * math.pi) / 1.3) ** 2)
    palmar = np.exp(-(wrap_angle(theta - 0.5 * math.pi) / 1.1) ** 2)
    rgb = mix(rgb, (0.76, 0.46, 0.42), 0.40 * palmar)
    for edge in edges:                                  # vincos palmares e rugas dorsais das juntas
        height -= 0.24 * gaussian(b - edge, 0.0009) * palmar
        rgb = mix(rgb, SKIN_DIRT, 0.30 * gaussian(b - edge, 0.0014) * palmar)
        for k in range(3):
            off = (k - 1) * 0.0032
            height -= 0.16 * gaussian(b - (edge + off), 0.0008) * dorsal
        rgb = mix(rgb, SKIN_RED, 0.40 * gaussian(b - edge, 0.0045) * dorsal)
    tip = np.clip((b - (total - 0.011)) / 0.011, 0, 1)
    rgb = mix(rgb, (0.78, 0.50, 0.46), 0.45 * tip * palmar)
    rgb = mix(rgb, SKIN_DIRT, 0.60 * np.clip(tip - 0.35, 0, 1) * dorsal * 0.3)            # sujeira ao redor da unha
    grime = np.clip((fbm(h, w, rng, 4, 4, 0.55, wrap=False) - 0.5) * 3.0, 0, 1)
    rgb = mix(rgb, SKIN_DIRT, 0.50 * grime)
    height += 0.035 * (rng.random((h, w)).astype(np.float32) - 0.5)
    layer[y0:y1, x0:x1, :3] = rgb
    layer[y0:y1, x0:x1, 3] = height


def atlas_skin(seed=7):
    rng = np.random.default_rng(seed)
    layer = new_layer(SIZE, SIZE, SKIN_BASE)
    for side in ("R", "L"):
        _paint_arm(layer, side, rng)
        for index, finger in enumerate(("Index", "Middle", "Ring", "Pinky", "Thumb")):
            _paint_finger(layer, side, index, finger, rng)
    return layer


def atlas_nail(seed=11):
    """Unha 64x64: placa rosada, lúnula pálida na base, borda livre branca suja."""
    rng = np.random.default_rng(seed)
    size = 64
    px = new_layer(size, size, (0.86, 0.68, 0.66))
    v = (np.arange(size) + 0.5)[:, None] / size * np.ones((1, size), np.float32)
    u = np.ones((size, 1), np.float32) * ((np.arange(size) + 0.5)[None, :] / size)
    rgb = px[..., :3]
    rgb[:] = mix(rgb, (0.93, 0.88, 0.84), 0.65 * gaussian(v - 0.08, 0.12))              # lúnula
    rgb[:] = mix(rgb, (0.72, 0.55, 0.52), 0.25 * (1.0 - gaussian(u - 0.5, 0.6)))
    free = np.clip((v - 0.86) / 0.14, 0, 1)
    rgb[:] = mix(rgb, (0.64, 0.58, 0.50), 0.8 * free)                                    # borda livre com sujeira
    rgb[:] = mix(rgb, SKIN_DIRT, 0.55 * np.clip((v - 0.93) / 0.07, 0, 1))
    px[..., 3] = 0.5 + 0.06 * np.sin(u * math.pi * 14.0) * 0.4 + 0.02 * (rng.random((size, size)) - 0.5)
    return px
