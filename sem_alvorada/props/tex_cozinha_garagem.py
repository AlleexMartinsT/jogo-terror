"""Texturas procedurais da cozinha e da garagem (numpy puro, 256 a 512 px, ladrilháveis).

Cada função devolve um `Canvas` (RGBA) em que **RGB é a cor e o canal alfa é o relevo** (altura 0..1).
Guardar os dois na mesma imagem corta o tamanho do .blend pela metade; o material lê a altura pela saída
Alpha do nó de imagem e nunca a liga ao canal alfa do shader (ver `mat_cozinha_garagem`).

Convenção de cor do pacote `props`: os valores são sRGB de tela (como as demais texturas de `textures.py`).
Ruídos são ladrilháveis para a projeção em caixa em escala de mundo não deixar emendas.
"""
import numpy as np

from . import kg_silhouettes, textures
from .tex_ruido import (blur, canvas_from, decal_canvas, fbm, generator, mix, radial_falloff, ring_mark, scratches, smooth,
                        spots, stamp_text)
from .textures import Canvas


# ---------------------------------------------------------------------------
# Madeira (carvalho de armário, pinho de prateleira, tábua de bancada)
# ---------------------------------------------------------------------------
def wood(name, size=512, dark=(0.20, 0.12, 0.07), light=(0.40, 0.27, 0.15), rings=9, knots=1, grime=0.5,
         vertical=False, planks=0, stain=None):
    """Madeira com veios ao longo de X (gire com `vertical`). `planks` > 0 emenda tábuas lado a lado."""
    rng = generator(name)
    yy = np.arange(size)[:, None] / size
    warp = fbm(rng, size, 2, 3, 3)
    fibers = fbm(rng, size, 3, size // 3, 3)
    ring_wave = 0.5 + 0.5 * np.sin((yy * rings + warp * 2.2) * 2 * np.pi)
    tone = 0.45 * fibers + 0.40 * ring_wave + 0.15 * rng.random((size, size)) * (fibers > 0.5)
    height = 0.55 * fibers + 0.30 * ring_wave
    for _ in range(knots):
        knot = spots(rng, size, 1, (10, 16), (0.9, 1.0))
        tone = tone * (1 - 0.7 * knot) + 0.1 * knot
        height -= 0.25 * knot
    if planks:
        for index in range(planks):
            row = int(index * size / planks)
            tone[row:row + 3, :] *= 0.25
            height[row:row + 3, :] -= 0.5
            shift = rng.uniform(-0.12, 0.12)
            tone[row + 3:int((index + 1) * size / planks), :] += shift
    color = np.array(dark) + (np.array(light) - np.array(dark)) * tone[..., None]
    dirt = smooth(fbm(rng, size, 3, 3, 4), 0.5, 0.85) * grime
    color *= (1.0 - 0.5 * dirt)[..., None]
    if stain is not None:
        color = mix(color, stain, spots(rng, size, 4, (25, 55), (0.5, 0.9)) * 0.7)
    cuts = scratches(rng, size, 40, (0.03, 0.12), (-12, 12), (0.2, 0.6))
    color *= (1.0 - 0.25 * cuts)[..., None]
    height -= 0.2 * cuts
    if vertical:
        color, height = color.transpose(1, 0, 2), height.T
    return canvas_from(color, height)


# ---------------------------------------------------------------------------
# Laminado de bancada
# ---------------------------------------------------------------------------
def laminate(name="kg_laminate", size=512, base=(0.40, 0.42, 0.37)):
    """Laminado cinza-esverdeado salpicado, com riscos de faca, marcas de copo e uma queimadura."""
    rng = generator(name)
    noise = rng.random((size, size))
    speckle = blur((noise > 0.93).astype(float) - (noise < 0.05).astype(float), 1)
    mottling = fbm(rng, size, 4, 4, 4) - 0.5
    luminance = 1.0 + 0.5 * speckle + 0.25 * mottling
    color = np.array(base) * luminance[..., None]
    cut = blur(scratches(rng, size, 90, (0.04, 0.2), (-90, 90), (0.2, 0.7)), 1)
    color = color * (1.0 - 0.18 * cut)[..., None] + 0.05 * cut[..., None]
    for cx, cy, radius in ((120, 340, 34), (300, 130, 29), (395, 410, 31)):
        ring = ring_mark(size, cx, cy, radius, 3.2)
        color = mix(color, (0.28, 0.25, 0.19), ring * 0.55)
    burn = spots(rng, size, 1, (22, 28), (0.95, 1.0))
    color = mix(color, (0.16, 0.10, 0.06), burn * 0.8)
    grime = smooth(fbm(rng, size, 3, 3, 4), 0.5, 0.9)
    color *= (1.0 - 0.3 * grime)[..., None]
    height = 0.55 + 0.2 * speckle - 0.35 * cut - 0.25 * burn
    return canvas_from(color, height)


# ---------------------------------------------------------------------------
# Esmalte de eletrodoméstico, aço escovado, ferro fundido
# ---------------------------------------------------------------------------
def enamel(name, size=512, base=(0.66, 0.64, 0.56), yellow=0.5, rust=0.25, streaks=1.0):
    """Esmalte branco-creme envelhecido: casca de laranja, escorridos, amarelado e pintas de ferrugem."""
    rng = generator(name)
    peel = fbm(rng, size, 64, 64, 2)
    drips = fbm(rng, size, 30, 2, 3)
    blotch = fbm(rng, size, 3, 3, 4)
    luminance = 1.0 + 0.05 * (peel - 0.5) - 0.10 * streaks * smooth(drips, 0.55, 0.9) - 0.04 * blotch
    color = np.array(base) * luminance[..., None]
    color = mix(color, (0.62, 0.52, 0.28), smooth(blotch, 0.45, 0.9) * yellow * 0.6)
    grime = smooth(fbm(rng, size, 7, 7, 4), 0.58, 0.95)
    color *= (1.0 - 0.16 * grime)[..., None]
    chips = spots(rng, size, int(40 * rust) + 4, (1.2, 3.2), (0.7, 1.0))
    color = mix(color, (0.34, 0.17, 0.08), smooth(chips, 0.35, 0.7) * 0.8)
    wipe = blur(scratches(rng, size, 30, (0.08, 0.3), (-4, 4), (0.1, 0.35)), 1)
    color *= (1.0 - 0.12 * wipe)[..., None]
    height = 0.5 + 0.2 * (peel - 0.5) - 0.4 * chips
    return canvas_from(color, height)


def brushed_steel(name="kg_steel", size=512, base=(0.55, 0.56, 0.57), smudge=0.5):
    """Aço escovado: linhas finas em X, marcas de dedo, manchas de água e riscos longos."""
    rng = generator(name)
    lines = fbm(rng, size, 3, size // 2, 3)
    fine = blur(rng.random((size, size)) * 0.5 + 0.5, 0)
    streak = 0.6 * lines + 0.4 * fbm(rng, size, 2, size // 3, 2)
    luminance = 0.82 + 0.3 * (streak - 0.5) + 0.04 * (fine - 0.5)
    color = np.array(base) * luminance[..., None]
    smudges = smooth(fbm(rng, size, 5, 5, 4), 0.55, 0.9) * smudge
    color = mix(color, (0.34, 0.33, 0.30), smudges * 0.6)
    water = spots(rng, size, 70, (1.5, 4.0), (0.3, 0.8))
    color = mix(color, (0.72, 0.72, 0.70), smooth(water, 0.2, 0.6) * 0.5)
    long_scratches = scratches(rng, size, 24, (0.15, 0.5), (-3, 3), (0.2, 0.55))
    color *= (1.0 - 0.18 * long_scratches)[..., None]
    height = 0.4 + 0.55 * streak - 0.2 * long_scratches
    return canvas_from(color, height)


def cast_iron(name="kg_castiron", size=256):
    """Ferro fundido da grelha do fogão: poros, gordura queimada e pintas de ferrugem."""
    rng = generator(name)
    pits = smooth(fbm(rng, size, 48, 48, 2), 0.6, 0.8)
    rough = fbm(rng, size, 6, 6, 3)
    color = np.array((0.11, 0.105, 0.10)) * (0.8 + 0.4 * rough)[..., None]
    color = mix(color, (0.04, 0.035, 0.03), smooth(fbm(rng, size, 4, 4, 3), 0.5, 0.8) * 0.8)
    rust = spots(rng, size, 16, (2.0, 5.0), (0.4, 0.9))
    color = mix(color, (0.35, 0.17, 0.07), rust * 0.6)
    return canvas_from(color, 0.6 - 0.35 * pits + 0.1 * rough)


def porcelain(name="kg_porcelain", size=256, base=(0.74, 0.72, 0.64), band=None):
    """Louça creme: esmalte com microporos, riscos de talher e, no prato, o fio azul perto da borda."""
    rng = generator(name)
    luminance = 1.0 + 0.08 * (fbm(rng, size, 4, 4, 3) - 0.5)
    color = np.array(base) * luminance[..., None]
    knife = scratches(rng, size, 40, (0.03, 0.12), (-90, 90), (0.1, 0.4))
    color *= (1.0 - 0.14 * knife)[..., None]
    pits = rng.random((size, size)) > 0.995
    color = mix(color, (0.35, 0.3, 0.22), pits.astype(float) * 0.6)
    if band:
        rows = np.arange(size)[:, None] / size
        stripe = ((rows > band[0]) & (rows < band[1])).astype(float) * np.ones((1, size))
        color = mix(color, (0.22, 0.30, 0.50), blur(stripe, 1) * 0.85)
    return canvas_from(color, 0.55 + 0.15 * fbm(rng, size, 20, 20, 2) - 0.2 * knife)


# ---------------------------------------------------------------------------
# Metal pintado (estante, bicicleta, cortador), plástico, borracha
# ---------------------------------------------------------------------------
def painted_metal(name, base, size=512, rust=0.5, chips=0.6, dust=0.4, streak=0.4):
    """Tinta sobre aço: riscos, lascas que mostram o ferro, ferrugem escorrida e poeira."""
    rng = generator(name)
    luminance = 1.0 + 0.2 * (fbm(rng, size, 5, 5, 4) - 0.5)
    color = np.array(base) * luminance[..., None]
    cut = blur(scratches(rng, size, int(80 * chips) + 5, (0.04, 0.2), (-80, 80), (0.3, 0.8)), 1)
    chip = spots(rng, size, int(70 * chips) + 3, (1.5, 4.0), (0.6, 1.0))
    iron = smooth(chip, 0.3, 0.6)
    color = mix(color, (0.19, 0.17, 0.16), iron * 0.9)
    rust_mask = smooth(fbm(rng, size, 6, 3, 4), 0.55, 0.9) * rust * smooth(fbm(rng, size, 2, 12, 3), 0.4, 0.8)
    rust_mask = np.maximum(rust_mask, iron * rust * 0.8)
    color = mix(color, (0.36, 0.17, 0.07), np.clip(rust_mask, 0, 1) * 0.85)
    color *= (1.0 - 0.25 * cut)[..., None]
    drip = smooth(fbm(rng, size, 24, 2, 3), 0.5, 0.85) * streak
    color *= (1.0 - 0.3 * drip)[..., None]
    dust_layer = smooth(fbm(rng, size, 4, 4, 5), 0.45, 0.9) * dust
    color = mix(color, (0.45, 0.43, 0.40), dust_layer * 0.35)
    height = 0.6 - 0.3 * iron - 0.25 * cut + 0.25 * rust_mask
    return canvas_from(color, height)


def plastic(name, base, size=256, scuffs=0.5, yellow=0.3):
    """Plástico ABS: granulado fino, arranhões e amarelado pelo tempo."""
    rng = generator(name)
    grain = rng.random((size, size))
    luminance = 1.0 + 0.06 * (blur(grain, 1) - 0.5) + 0.12 * (fbm(rng, size, 4, 4, 3) - 0.5)
    color = np.array(base) * luminance[..., None]
    color = mix(color, (0.55, 0.47, 0.25), smooth(fbm(rng, size, 3, 3, 3), 0.4, 0.8) * yellow)
    scuff = blur(scratches(rng, size, int(60 * scuffs) + 3, (0.03, 0.2), (-60, 60), (0.2, 0.7)), 1)
    color = color * (1.0 - 0.18 * scuff)[..., None] + 0.04 * scuff[..., None]
    grime = smooth(fbm(rng, size, 5, 5, 4), 0.55, 0.9)
    color *= (1.0 - 0.3 * grime)[..., None]
    return canvas_from(color, 0.55 + 0.08 * (grain - 0.5) - 0.2 * scuff)


def rubber(name="kg_rubber", size=256, tread=False):
    """Borracha: preta, com poeira cinza; `tread` desenha o espinhaço do pneu (chevrons ao longo de V)."""
    rng = generator(name)
    noise = fbm(rng, size, 32, 32, 2)
    color = np.array((0.045, 0.045, 0.05)) * (0.8 + 0.5 * noise)[..., None]
    color = mix(color, (0.25, 0.24, 0.22), smooth(fbm(rng, size, 4, 4, 4), 0.55, 0.9) * 0.5)
    height = 0.5 + 0.15 * noise
    if tread:
        uu, vv = np.meshgrid(np.arange(size) / size, np.arange(size) / size)
        wave = np.abs(((uu * 8 + np.abs(vv - 0.5) * 3.0) % 1.0) - 0.5)
        lug = smooth(wave, 0.12, 0.2) * smooth(np.abs(vv - 0.5), 0.0, 0.05)
        height = 0.25 + 0.7 * lug
        color *= (0.7 + 0.4 * lug)[..., None]
    return canvas_from(color, height)


# ---------------------------------------------------------------------------
# Tecidos, comida velha, papelão
# ---------------------------------------------------------------------------
def vinyl(name, base, size=256):
    """Vinil de estofado de cadeira: grão fino, trincas no uso, ombros clareados e sujeira de dedo."""
    rng = generator(name)
    grain = fbm(rng, size, 48, 48, 2)
    cracks = 1.0 - smooth(np.abs(fbm(rng, size, 14, 14, 4) - 0.5) * 2.0, 0.0, 0.035)
    luminance = 0.9 + 0.2 * grain
    color = np.array(base) * luminance[..., None]
    color = mix(color, tuple(np.array(base) * 0.35), cracks * 0.8)
    color = mix(color, tuple(np.minimum(np.array(base) * 1.5, 1.0)), smooth(fbm(rng, size, 3, 3, 3), 0.6, 0.9) * 0.4)
    grime = smooth(fbm(rng, size, 5, 5, 4), 0.55, 0.9)
    color *= (1.0 - 0.3 * grime)[..., None]
    return canvas_from(color, 0.55 + 0.25 * grain - 0.4 * cracks)


def pegboard(name="kg_pegboard", size=256):
    """Chapa de fibra perfurada (furos de 6 mm a cada 25 mm; o ladrilho cobre 25,4 cm a 1 px por milímetro)."""
    rng = generator(name)
    spacing = size // 10
    yy, xx = np.mgrid[0:size, 0:size]
    centre_x = (xx % spacing) - spacing / 2 + 0.5
    centre_y = (yy % spacing) - spacing / 2 + 0.5
    hole = np.clip(3.4 - np.hypot(centre_x, centre_y), 0.0, 1.0)
    fibre = fbm(rng, size, 48, 48, 2)
    color = np.array((0.50, 0.38, 0.25)) * (0.85 + 0.3 * fibre)[..., None]
    color = mix(color, (0.30, 0.22, 0.14), smooth(fbm(rng, size, 3, 3, 4), 0.55, 0.9) * 0.6)
    color = mix(color, (0.04, 0.03, 0.025), hole)
    return canvas_from(color, 0.62 - 0.6 * hole + 0.1 * fibre)


def tool_outlines(columns=512, rows=272, board=(1.7, 0.9)):
    """Contorno à caneta de cada ferramenta do painel (decal). A do martelo continua lá, sem o martelo."""
    rng = generator("kg_outline")
    canvas = Canvas(columns, rows)
    canvas.px[..., :3] = np.array((0.03, 0.03, 0.04), np.float32)
    canvas.px[..., 3] = 0.0
    px_per_m = columns / board[0]
    for name, (hang_x, hang_z, outline) in kg_silhouettes.PANEL_SLOTS.items():
        points = [((hang_x + u) * px_per_m + rng.normal(0, 0.4), (board[1] - (hang_z + v)) * px_per_m + rng.normal(0, 0.4))
                  for u, v in outline]
        for start, end in zip(points, points[1:] + points[:1]):
            canvas.line(*start, *end, (0.03, 0.03, 0.04, 0.92), 3.2)
    return canvas


def towel(name="kg_towel", size=256, checks=6, color_a=(0.58, 0.14, 0.12), color_b=(0.72, 0.70, 0.62)):
    """Pano de prato xadrez, gasto e manchado, com trama visível."""
    rng = generator(name)
    cell = (np.arange(size) * checks // size) % 2
    check = (cell[:, None] ^ cell[None, :]).astype(float)
    stripe = (cell[:, None] | cell[None, :]).astype(float)
    base = mix(color_b, color_a, 0.55 * stripe + 0.45 * check)
    weave = 0.5 + 0.5 * np.sin(np.arange(size)[None, :] * 2 * np.pi / 4) * np.sin(np.arange(size)[:, None] * 2 * np.pi / 4)
    color = base * (0.92 + 0.12 * weave + 0.1 * (fbm(rng, size, 6, 6, 3) - 0.5))[..., None]
    stain = spots(rng, size, 6, (18, 40), (0.4, 0.8))
    color = mix(color, (0.30, 0.22, 0.12), stain * 0.5)
    return canvas_from(color, 0.4 + 0.4 * weave)


def old_food(name="kg_food_old", size=256):
    """Comida de três semanas: marrom ressecado com mofo cinza-esverdeado."""
    rng = generator(name)
    lumps = fbm(rng, size, 10, 10, 4)
    color = mix((0.30, 0.20, 0.10), (0.18, 0.12, 0.07), lumps)
    mold = spots(rng, size, 36, (4.0, 14.0), (0.5, 1.0)) * smooth(fbm(rng, size, 6, 6, 3), 0.35, 0.65)
    color = mix(color, (0.50, 0.55, 0.46), smooth(mold, 0.25, 0.6) * 0.85)
    color = mix(color, (0.28, 0.38, 0.30), smooth(mold, 0.55, 0.95) * 0.5)
    return canvas_from(color, 0.3 + 0.4 * lumps + 0.3 * mold)


def cardboard(name, size=256, label=None, lines=None):
    """Papelão ondulado com fita e, se houver, o texto à caneta (a fonte do projeto só tem maiúsculas)."""
    rng = generator(name)
    corrugation = 0.5 + 0.5 * np.sin(np.arange(size)[None, :] * 2 * np.pi / 6 + 3 * fbm(rng, size, 2, 2, 2))
    color = np.array((0.50, 0.38, 0.24)) * (0.9 + 0.08 * corrugation + 0.1 * (fbm(rng, size, 5, 5, 4) - 0.5))[..., None]
    color = mix(color, (0.30, 0.22, 0.13), smooth(fbm(rng, size, 3, 3, 4), 0.55, 0.9) * 0.6)
    tape_top, tape_bottom = int(size * 0.44), int(size * 0.56)
    color[tape_top:tape_bottom] = color[tape_top:tape_bottom] * 0.35 + np.array((0.72, 0.66, 0.46)) * 0.65
    height = 0.45 + 0.25 * corrugation
    height[tape_top:tape_bottom] = 0.7
    canvas = canvas_from(color, height)
    if label:
        scale = max(2, min(5, int(size * 0.85 / canvas.text_width(label, 1))))
        x = (size - canvas.text_width(label, scale)) // 2
        stamp_text(canvas, x, int(size * 0.14), label, (0.07, 0.06, 0.05, 1.0), scale)
    for index, line in enumerate(lines or ()):
        stamp_text(canvas, int(size * 0.08), int(size * 0.64) + index * 18, line, (0.1, 0.09, 0.08, 1.0), 2)
    return canvas


# ---------------------------------------------------------------------------
# Marcas com alfa de verdade (decals): gordura, óleo, teia
# ---------------------------------------------------------------------------
def grease_mark(size=128):
    """Mancha de gordura de mão: marrom-escura, mais forte no centro, com bordas irregulares."""
    rng = generator("kg_grease")
    alpha = radial_falloff(size, 1.2) * (0.55 + 0.9 * fbm(rng, size, 4, 4, 4))
    return decal_canvas((0.07, 0.045, 0.02), smooth(alpha, 0.2, 0.9) * 0.55)


def smudges(size=256):
    """Marcas de mãozinhas de criança na porta: manchas acinzentadas em fileiras de dedos, bem suaves."""
    rng = generator("kg_smudge")
    alpha = np.zeros((size, size))
    for palm_x, palm_y, tilt in ((0.34, 0.62, -0.2), (0.62, 0.42, 0.25)):
        cx, cy = palm_x * size, palm_y * size
        yy, xx = np.mgrid[0:size, 0:size]
        palm = np.clip(1.0 - np.hypot(xx - cx, (yy - cy) * 1.15) / (size * 0.075), 0.0, 1.0)
        alpha = np.maximum(alpha, palm * 0.5)
        for finger in range(4):
            angle = tilt + (finger - 1.5) * 0.28
            fx, fy = cx + np.sin(angle) * size * 0.115, cy - np.cos(angle) * size * 0.115
            reach = np.clip(1.0 - np.hypot(xx - fx, (yy - fy) * 0.8) / (size * 0.032), 0.0, 1.0)
            alpha = np.maximum(alpha, reach * 0.45)
    alpha *= 0.55 + 0.6 * fbm(rng, size, 6, 6, 3)
    return decal_canvas((0.18, 0.16, 0.13), smooth(alpha, 0.08, 0.55) * 0.45)


def oil_stain(size=256):
    """Poça de óleo de motor: núcleo escuro, borda fina com reflexo arroxeado."""
    rng = generator("kg_oil_stain")
    base = radial_falloff(size, 0.7) * (0.5 + 1.0 * fbm(rng, size, 3, 3, 5))
    core = smooth(base, 0.45, 0.62)
    rim = smooth(base, 0.28, 0.45) * (1.0 - core)
    color = mix((0.02, 0.018, 0.015), (0.18, 0.12, 0.22), rim)
    return decal_canvas(color, np.clip(core * 0.9 + rim * 0.35, 0.0, 1.0))


def cobweb(size=256):
    """Teia de canto: um leque de fios a partir do canto superior esquerdo, ligados por arcos frouxos."""
    alpha = np.zeros((size, size))
    yy, xx = np.mgrid[0:size, 0:size].astype(float)
    angle = np.arctan2(yy, xx)
    radius = np.hypot(xx, yy) / size
    spokes = 7
    for index in range(spokes):
        direction = (index + 0.5) / spokes * (np.pi / 2)
        alpha = np.maximum(alpha, np.clip(1.0 - np.abs(angle - direction) * radius * size / 1.4, 0.0, 1.0) * 0.8)
    for ring in np.linspace(0.18, 0.95, 7):
        sag = ring * (1.0 - 0.12 * np.sin(angle * 2 * spokes / 1.0) ** 2)
        alpha = np.maximum(alpha, np.clip(1.0 - np.abs(radius - sag) * size / 1.6, 0.0, 1.0) * 0.55)
    alpha *= (radius < 1.0)
    return decal_canvas((0.82, 0.82, 0.78), alpha * 0.55)


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------
TEXTURES = {
    "kg_oak": lambda rng: wood("kg_oak", rings=8, knots=0, grime=0.6),
    "kg_oak_v": lambda rng: wood("kg_oak_v", rings=8, knots=0, grime=0.6, vertical=True),
    "kg_pine": lambda rng: wood("kg_pine", dark=(0.36, 0.27, 0.17), light=(0.58, 0.45, 0.28), rings=6, knots=3, grime=0.7),
    "kg_bench_wood": lambda rng: wood("kg_bench_wood", dark=(0.30, 0.20, 0.11), light=(0.50, 0.36, 0.20), rings=7,
                                      knots=2, grime=0.9, planks=5, stain=(0.10, 0.08, 0.06)),
    "kg_laminate": lambda rng: laminate(),
    "kg_enamel": lambda rng: enamel("kg_enamel"),
    "kg_enamel_black": lambda rng: enamel("kg_enamel_black", base=(0.13, 0.13, 0.14), yellow=0.0, rust=0.12, streaks=0.5),
    "kg_enamel_yellow": lambda rng: enamel("kg_enamel_yellow", base=(0.66, 0.62, 0.50), yellow=0.45, rust=0.5),
    "kg_steel": lambda rng: brushed_steel(),
    "kg_castiron": lambda rng: cast_iron(),
    "kg_porcelain": lambda rng: porcelain(),
    "kg_porcelain_band": lambda rng: porcelain("kg_porcelain_band", band=(0.88, 0.905)),
    "kg_shelf_paint": lambda rng: painted_metal("kg_shelf_paint", (0.33, 0.37, 0.36), rust=0.7),
    "kg_bike_pink": lambda rng: painted_metal("kg_bike_pink", (0.82, 0.38, 0.52), rust=0.25, chips=0.8, dust=0.25),
    "kg_bike_tube": lambda rng: painted_metal("kg_bike_tube", (0.82, 0.38, 0.52), rust=0.08, chips=0.1, dust=0.08, streak=0.05),
    "kg_mower_red": lambda rng: painted_metal("kg_mower_red", (0.55, 0.12, 0.09), rust=0.35, chips=0.7, dust=0.9),
    "kg_plastic_beige": lambda rng: plastic("kg_plastic_beige", (0.64, 0.59, 0.46), yellow=0.5),
    "kg_plastic_dark": lambda rng: plastic("kg_plastic_dark", (0.17, 0.17, 0.18), yellow=0.0),
    "kg_plastic_white": lambda rng: plastic("kg_plastic_white", (0.70, 0.69, 0.64), yellow=0.6),
    "kg_rubber": lambda rng: rubber(),
    "kg_tire": lambda rng: rubber("kg_tire", tread=True),
    "kg_vinyl_red": lambda rng: vinyl("kg_vinyl_red", (0.40, 0.08, 0.07)),
    "kg_towel": lambda rng: towel(),
    "kg_food_old": lambda rng: old_food(),
    "kg_box_plain": lambda rng: cardboard("kg_box_plain"),
    "kg_box_emma": lambda rng: cardboard("kg_box_emma", label="EMMA", lines=("QUARTO", "NAO MEXER")),
    "kg_box_toys": lambda rng: cardboard("kg_box_toys", label="BRINQ."),
    "kg_box_xmas": lambda rng: cardboard("kg_box_xmas", label="NATAL"),
    "kg_box_docs": lambda rng: cardboard("kg_box_docs", label="IMPOSTOS", lines=("2018 - 2022",)),
    "kg_box_kitchen": lambda rng: cardboard("kg_box_kitchen", label="COZINHA"),
    "kg_grease": lambda rng: grease_mark(),
    "kg_smudge": lambda rng: smudges(),
    "kg_oil_stain": lambda rng: oil_stain(),
    "kg_cobweb": lambda rng: cobweb(),
    "kg_pegboard": lambda rng: pegboard(),
    "kg_outline": lambda rng: tool_outlines(),
    "kg_aluminum": lambda rng: brushed_steel("kg_aluminum", base=(0.62, 0.63, 0.64), smudge=0.9),
    "kg_tool_steel": lambda rng: painted_metal("kg_tool_steel", (0.30, 0.30, 0.32), rust=0.9, chips=0.2, dust=0.5, streak=0.2),
    "kg_toolbox_red": lambda rng: painted_metal("kg_toolbox_red", (0.52, 0.10, 0.07), rust=0.6, chips=0.8, dust=0.8),
    "kg_tin": lambda rng: painted_metal("kg_tin", (0.52, 0.52, 0.50), rust=0.8, chips=0.2, dust=0.4, streak=0.5),
    "kg_heater": lambda rng: enamel("kg_heater", base=(0.62, 0.60, 0.54), yellow=0.25, rust=0.6, streaks=1.4),
}


def register():
    """Coloca as texturas no registro de `props.textures` (idempotente)."""
    textures.TEXTURES.update(TEXTURES)
