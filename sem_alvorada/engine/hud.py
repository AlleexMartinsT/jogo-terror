"""HUD de jogo: quase vazio de propósito, cor de papel envelhecido.

Cada função recebe um `Canvas` e o `hud_model()`; nenhuma toca a lógica do jogo. Em jogo só existe:

    centro              mira em ponto e, havendo alvo, a dica de interação (ou o estado: "Trancada")
    inferior esquerdo   barra VOCÊ do medidor de som (e ENTIDADE enquanto ela é audível)
    inferior direito    bateria da lanterna, só depois de um gesto ou quando está acabando
    inferior central    fôlego, só quando está acabando
    centro (segurando Q ou Tab)   a roda de itens
    mais abaixo         a fala do personagem, nas poucas vezes em que ele fala

Objetivo, lista de coleta, medidor completo e controles ficam no menu de pausa (`screens.py`).
"""
import math

from .. import conventions as C
from . import texts
from .canvas import INK, PAPER, PAPER_DIM, SHADE, WARNING, with_alpha

WARNING_BRIGHT = (0.80, 0.30, 0.22, 1.0)       # o vermelho dos avisos, claro o bastante para aparecer sobre parede iluminada

MARGIN = 28
METER_LABEL_W = 84
METER_BAR_W = 176
METER_BAR_H = 6
METER_ROW = 24
BATTERY_BARS = 10
DISPLAY_CURVE = 0.6          # níveis pequenos precisam ser visíveis: exibe level ** 0.6

WHEEL_RADIUS = 158           # distância do centro ao centro de cada setor, em unidades de 720p
WHEEL_TILE = 88
WHEEL_RING = 44              # raio do anel central onde o ponteiro anda
WHEEL_GROUND = (0.035, 0.033, 0.028, 1.0)       # cor de fundo dos setores, para vazar detalhes dos ícones
ICON_SCALE = 1.3


def display_level(level):
    """Curva do medidor: 0.08 (limiar de audição) ocupa 22% da barra em vez de 8%."""
    return max(0.0, min(1.0, level)) ** DISPLAY_CURVE


def draw_gameplay(canvas, model):
    if model["wheel"]["open"]:
        draw_wheel(canvas, model["wheel"])
    else:
        draw_crosshair(canvas, model)
    draw_noise_meter(canvas, model["noise"])
    draw_flashlight(canvas, model)
    draw_stamina(canvas, model)
    draw_message(canvas, model)


# --------------------------------------------------------------------------
# Medidor de som
# --------------------------------------------------------------------------
def draw_noise_meter(canvas, noise):
    """Em jogo: só a barra VOCÊ, quase transparente em silêncio, e ENTIDADE quando dá para ouvi-la."""
    u = canvas.scale
    alpha = noise["alpha"]
    x0, y0 = MARGIN * u, MARGIN * u
    rows = ["player"] + (["entity"] if noise["entity_audible"] else [])
    for row, key in enumerate(rows):
        y = y0 + row * METER_ROW * u
        canvas.rect(x0 - 8 * u, y - 7 * u, (METER_LABEL_W + METER_BAR_W + 16) * u, 22 * u,
                    with_alpha(SHADE, 0.32 * alpha))
        draw_meter_row(canvas, x0, y, noise, key, alpha)


def draw_meter_row(canvas, x, y, noise, key, alpha=1.0):
    """Uma barra do medidor; a marca do limiar de audição só existe na linha do jogador."""
    u = canvas.scale
    level, peak = noise["levels"][key], noise["peaks"][key]
    threshold = noise["hear_threshold"] if key == "player" else None
    bar_x, bar_w, bar_h = x + METER_LABEL_W * u, METER_BAR_W * u, METER_BAR_H * u
    canvas.text(x, y, noise["labels"][key], 11 * u, with_alpha(PAPER_DIM, alpha))
    canvas.rect(bar_x, y, bar_w, bar_h, with_alpha(PAPER, 0.13 * alpha))
    audible = threshold is not None and level >= threshold
    canvas.rect(bar_x, y, bar_w * display_level(level), bar_h, with_alpha(WARNING if audible else PAPER, 0.92 * alpha))
    if peak > level + 0.01:
        peak_x = bar_x + bar_w * display_level(peak)
        canvas.rect(peak_x - u, y - 2 * u, 2 * u, bar_h + 4 * u, with_alpha(PAPER, 0.85 * alpha))
    if threshold is not None:
        mark_x = bar_x + bar_w * display_level(threshold)
        canvas.rect(mark_x - 0.75 * u, y - 4 * u, 1.5 * u, bar_h + 8 * u, with_alpha(WARNING, alpha))


def draw_threshold_legend(canvas, x, y):
    u = canvas.scale
    canvas.rect(x, y - 1 * u, 1.5 * u, 7 * u, WARNING)
    canvas.text(x + 7 * u, y, texts.METER_THRESHOLD_HINT, 10 * u, with_alpha(PAPER_DIM, 0.9))


# --------------------------------------------------------------------------
# Lanterna e fôlego
# --------------------------------------------------------------------------
def draw_flashlight(canvas, model):
    battery = model["battery"]
    if not battery["has"] or battery["alpha"] <= 0:
        return
    u = canvas.scale
    right, y = canvas.width - MARGIN * u, MARGIN * u
    alpha = battery["alpha"]
    _draw_battery_bars(canvas, right, y, battery, model["time"], alpha)
    canvas.text(right, y + 22 * u, texts.HUD_FLASHLIGHT, 10 * u, with_alpha(PAPER_DIM, alpha), "right")
    if battery["dead"]:
        _draw_dead_hint(canvas, right, y + 58 * u, battery, model["time"])


def _draw_battery_bars(canvas, right, y, battery, clock, alpha):
    u = canvas.scale
    bar_w, bar_h, gap = 8 * u, 13 * u, 3 * u
    filled = math.ceil(battery["level"] * BATTERY_BARS - 1e-6) if battery["level"] > 0 else 0
    blink = battery["critical"] and int(clock * 3) % 2 == 0
    color = WARNING if battery["low"] else PAPER
    for index in range(BATTERY_BARS):
        x = right - (BATTERY_BARS - index) * (bar_w + gap) + gap
        if index >= filled or battery["swapping"]:
            level = 0.14
        elif not battery["on"]:
            level = 0.38            # desligada: mostra a carga, mas apagada
        else:
            level = 0.14 if blink else 0.92
        canvas.rect(x, y, bar_w, bar_h, with_alpha(color, level * alpha))


def _draw_dead_hint(canvas, right, y, battery, clock):
    """Lanterna sem carga: o aviso é visual e fica enquanto durar, no lugar da antiga fala."""
    u = canvas.scale
    pulse = 0.65 + 0.35 * math.sin(clock * 5.0) if not battery["swapping"] else 0.4
    canvas.text(right, y, texts.HUD_NO_CHARGE, 12 * u, with_alpha(WARNING, pulse), "right")
    if battery["can_swap"] and not battery["swapping"]:
        canvas.text(right, y - 16 * u, texts.HUD_SWAP_HINT, 10 * u, with_alpha(PAPER_DIM, 0.9), "right")


def draw_stamina(canvas, model):
    alpha = model["stamina_alpha"]
    if alpha <= 0:
        return
    u = canvas.scale
    width = 150 * u
    x, y = (canvas.width - width) / 2, MARGIN * u
    tired = model["exhausted"]
    canvas.text(canvas.width / 2, y + 10 * u, texts.HUD_STAMINA, 9 * u,
                with_alpha(WARNING if tired else PAPER_DIM, alpha), "center")
    canvas.rect(x, y, width, 3 * u, with_alpha(PAPER, 0.13 * alpha))
    canvas.rect(x, y, width * model["stamina"], 3 * u, with_alpha(WARNING if tired else PAPER, 0.85 * alpha))


# --------------------------------------------------------------------------
# Centro da tela
# --------------------------------------------------------------------------
def draw_crosshair(canvas, model):
    u = canvas.scale
    cx, cy = canvas.width / 2, canvas.height / 2
    prompt = model["prompt"]
    canvas.disc(cx, cy, 3.6 * u, with_alpha(SHADE, 0.4), 14)          # halo escuro: a mira não some sobre parede iluminada
    if prompt is None:
        canvas.disc(cx, cy, 1.7 * u, with_alpha(PAPER, 0.55), 12)
        return
    canvas.disc(cx, cy, 2.5 * u, with_alpha(PAPER, 0.92), 12)
    canvas.ring(cx, cy, 8 * u, max(1.0, 0.9 * u), with_alpha(PAPER, 0.45), 28)
    _draw_prompt(canvas, cx, cy - 42 * u, prompt, model["prompt_blocked"])


def _draw_prompt(canvas, cx, y, prompt, blocked):
    """Dica de interação. Quando é estado e não ação (porta trancada) vai em tom apagado com uma marca de aviso."""
    u = canvas.scale
    width = canvas.text_width(prompt, 16 * u)
    lead = 14 * u if blocked else 0.0
    left = cx - (width + lead) / 2
    canvas.rect(left - 12 * u, y - 6 * u, width + lead + 24 * u, 26 * u, with_alpha(SHADE, 0.78))
    if blocked:
        canvas.rect(left, y - 2 * u, 3 * u, 17 * u, WARNING_BRIGHT)
    canvas.text(left + lead, y, prompt, 16 * u, with_alpha(PAPER, 0.74) if blocked else PAPER)


def draw_message(canvas, model):
    """A fala do personagem. Aparece na largada e ao pegar um item principal, e só."""
    if not model["message"] or model["message_alpha"] <= 0:
        return
    u = canvas.scale
    alpha = model["message_alpha"]
    lines_top = canvas.height * 0.22
    canvas.wrapped(canvas.width / 2, lines_top, model["message"], 16 * u, with_alpha(PAPER, alpha),
                   canvas.width * 0.6, align="center")


# --------------------------------------------------------------------------
# Roda de itens
# --------------------------------------------------------------------------
def wheel_center(cx, cy, index, count, radius):
    """Centro do setor `index`: sentido horário a partir do topo."""
    angle = math.tau * index / count
    return cx + radius * math.sin(angle), cy + radius * math.cos(angle)


def draw_wheel(canvas, wheel):
    u = canvas.scale
    cx, cy = canvas.width / 2, canvas.height / 2
    count = len(wheel["slots"])
    centers = [wheel_center(cx, cy, index, count, WHEEL_RADIUS * u) for index in range(count)]
    for layer in range(20):           # sombra que some nas bordas: camadas finas empilhadas em vez de um disco chapado
        canvas.disc(cx, cy, (285 - layer * 11) * u, with_alpha(SHADE, 0.075), 56)
    for slot, (tx, ty) in zip(wheel["slots"], centers):
        bright = slot["selected"]
        canvas.line(cx, cy, tx, ty, (2.0 if bright else 1.2) * u, with_alpha(PAPER, 0.6 if bright else 0.10))
    canvas.ring(cx, cy, WHEEL_RING * u, max(1.0, 1.4 * u), with_alpha(PAPER, 0.3))
    px, py = wheel["pointer"]
    canvas.disc(cx + px * (WHEEL_RING - 6) * u, cy + py * (WHEEL_RING - 6) * u, 3.2 * u, with_alpha(PAPER, 0.95), 14)
    for slot, (tx, ty) in zip(wheel["slots"], centers):
        _draw_wheel_tile(canvas, slot, tx, ty)
    caption_y = cy - 58 * u
    canvas.text(cx, caption_y, wheel["caption"], 11 * u, with_alpha(PAPER, 0.8), "center")
    canvas.text(cx, caption_y - 20 * u, wheel["name"], 17 * u, PAPER, "center")


def _draw_wheel_tile(canvas, slot, cx, cy):
    u = canvas.scale
    size = WHEEL_TILE * u
    x, y = cx - size / 2, cy - size / 2
    stroke = max(1.0, u)
    if not slot["owned"]:
        canvas.rect(x, y, size, size, with_alpha(SHADE, 0.3))
        canvas.outline(x, y, size, size, stroke, with_alpha(PAPER, 0.10))
        WHEEL_ICONS[slot["kind"]](canvas, cx, cy, with_alpha(PAPER_DIM, 0.2), WHEEL_GROUND)
        return
    if slot["selected"]:
        canvas.rect(x, y, size, size, with_alpha(PAPER, 0.93))
        canvas.outline(x - 4 * u, y - 4 * u, size + 8 * u, size + 8 * u, 1.5 * u, with_alpha(PAPER, 0.7))
        ink, ground = INK, PAPER
    else:
        canvas.rect(x, y, size, size, with_alpha(SHADE, 0.66))
        canvas.outline(x, y, size, size, stroke, with_alpha(PAPER, 0.55 if slot["held"] else 0.28))
        ink, ground = with_alpha(PAPER, 0.9 if slot["held"] else 0.62), WHEEL_GROUND
    WHEEL_ICONS[slot["kind"]](canvas, cx, cy, ink, ground)
    if slot["count"] is not None:
        canvas.text(x + size - 6 * u, y + 6 * u, f"x{slot['count']}", 14 * u, INK if slot["selected"] else PAPER, "right")
    if slot["fresh"]:
        canvas.disc(x + size - 9 * u, y + size - 9 * u, 3.6 * u, INK if slot["selected"] else PAPER, 12)
    if slot["held"]:
        canvas.rect(cx - 15 * u, y - 11 * u, 30 * u, 2.5 * u, with_alpha(PAPER, 0.9))


def _placer(canvas, cx, cy, dy=0.0):
    """Coordenadas locais do ícone (unidades de 720p, y para cima, origem no centro do setor) em pixels."""
    u = canvas.scale * ICON_SCALE
    return lambda x, y: (cx + x * u, cy + (y + dy) * u)


# Ícones: formas simples em um quadrado de ~60 unidades. `ink` desenha, `ground` vaza o detalhe por dentro.
def _icon_flashlight(canvas, cx, cy, ink, ground):
    u = canvas.scale * ICON_SCALE
    at = _placer(canvas, cx, cy, -4)
    canvas.poly([at(-8, 2), at(8, 2), at(13, 16), at(-13, 16)], ink)
    canvas.poly([at(-13, 16), at(13, 16), at(13, 19.5), at(-13, 19.5)], with_alpha(ink, 0.55))
    canvas.poly([at(-6, -20), at(6, -20), at(6, 2), at(-6, 2)], ink)
    canvas.poly([at(-2, -9), at(2, -9), at(2, -3), at(-2, -3)], ground)
    for (x0, y0), (x1, y1) in (((0, 23), (0, 29)), ((-10, 22), (-15, 27)), ((10, 22), (15, 27))):
        canvas.line(*at(x0, y0), *at(x1, y1), 2 * u, with_alpha(ink, 0.6))


def _icon_battery(canvas, cx, cy, ink, ground):
    u = canvas.scale * ICON_SCALE
    at = _placer(canvas, cx, cy, 1)
    canvas.poly([at(-10, -20), at(10, -20), at(10, 12), at(-10, 12)], ink)
    canvas.poly([at(-4, 12), at(4, 12), at(4, 17), at(-4, 17)], ink)
    canvas.poly([at(-10, -8), at(10, -8), at(10, -2), at(-10, -2)], ground)
    canvas.poly([at(-1.2, -19), at(1.2, -19), at(1.2, -11), at(-1.2, -11)], ground)


def _icon_key(canvas, cx, cy, ink, ground):
    u = canvas.scale * ICON_SCALE
    at = _placer(canvas, cx, cy, -1)
    bow_x, bow_y = at(0, 14)
    canvas.disc(bow_x, bow_y, 10 * u, ink, 20)
    canvas.disc(bow_x, bow_y, 4.2 * u, ground, 14)
    canvas.poly([at(-2.5, -22), at(2.5, -22), at(2.5, 5), at(-2.5, 5)], ink)
    canvas.poly([at(2.5, -22), at(9, -22), at(9, -17), at(2.5, -17)], ink)
    canvas.poly([at(2.5, -13), at(8, -13), at(8, -9), at(2.5, -9)], ink)


def _icon_map(canvas, cx, cy, ink, ground):
    u = canvas.scale * ICON_SCALE
    at = _placer(canvas, cx, cy)
    canvas.poly([at(-25, -14), at(-8, -19), at(-8, 17), at(-25, 22)], ink)
    canvas.poly([at(-8, -19), at(8, -14), at(8, 22), at(-8, 17)], with_alpha(ink, 0.62))
    canvas.poly([at(8, -14), at(25, -19), at(25, 17), at(8, 22)], ink)
    for x, y in ((-17, 6), (-14, -2), (14, 2), (18, 9)):
        canvas.disc(*at(x, y), 1.8 * u, ground, 8)
    canvas.line(*at(-14, -2), *at(-17, 6), 1.2 * u, ground)
    canvas.line(*at(14, 2), *at(18, 9), 1.2 * u, ground)


def _icon_note(canvas, cx, cy, ink, ground):
    u = canvas.scale * ICON_SCALE
    at = _placer(canvas, cx, cy)
    canvas.poly([at(-14, -21), at(14, -21), at(14, 10), at(4, 21), at(-14, 21)], ink)
    canvas.poly([at(4, 21), at(14, 10), at(4, 10)], with_alpha(ink, 0.55))
    for row in range(4):
        y = 3 - row * 7
        canvas.poly([at(-9, y), at(9 if row else 0, y), at(9 if row else 0, y - 2), at(-9, y - 2)], ground)


WHEEL_ICONS = {C.ITEM_FLASHLIGHT: _icon_flashlight, C.ITEM_BATTERY: _icon_battery, C.ITEM_KEY: _icon_key,
               C.ITEM_MAP: _icon_map, C.ITEM_NOTE: _icon_note}


# --------------------------------------------------------------------------
# Sobreposições gerais
# --------------------------------------------------------------------------
def draw_debug(canvas, model):
    if model["debug"]:
        u = canvas.scale
        canvas.text(canvas.width - MARGIN * u, canvas.height - 24 * u, model["debug"], 11 * u,
                    with_alpha(PAPER_DIM, 0.9), "right")


def draw_error(canvas, model):
    if model["error"]:
        u = canvas.scale
        text = texts.ERROR_BANNER.format(message=model["error"])
        width = min(canvas.width - 40 * u, canvas.text_width(text, 13 * u) + 24 * u)
        canvas.rect((canvas.width - width) / 2, canvas.height - 44 * u, width, 26 * u, with_alpha(WARNING, 0.85))
        canvas.text(canvas.width / 2, canvas.height - 36 * u, text, 13 * u, INK, "center")


def draw_reader_dim(canvas):
    canvas.rect(0, 0, canvas.width, canvas.height, with_alpha(SHADE, 0.8))
