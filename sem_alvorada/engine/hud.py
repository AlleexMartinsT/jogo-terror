"""HUD de jogo: canto a canto, discreto, cor de papel envelhecido.

Cada função recebe um `Canvas` e o `hud_model()`; nenhuma toca a lógica do jogo.

    inferior esquerdo   medidor de som (VOCÊ / AMBIENTE / ENTIDADE)
    superior esquerdo   objetivo e lista de coleta
    inferior direito    lanterna (barras), pilhas reserva e fôlego
    centro              mira, dica de interação e mensagens
"""
import math

from . import texts
from .canvas import INK, PAPER, PAPER_DIM, SHADE, WARNING, with_alpha

MARGIN = 28
METER_LABEL_W = 84
METER_BAR_W = 176
METER_BAR_H = 6
METER_ROW = 24
BATTERY_BARS = 10
DISPLAY_CURVE = 0.6          # níveis pequenos precisam ser visíveis: exibe level ** 0.6


def display_level(level):
    """Curva do medidor: 0.08 (limiar de audição) ocupa 22% da barra em vez de 8%."""
    return max(0.0, min(1.0, level)) ** DISPLAY_CURVE


def draw_gameplay(canvas, model):
    draw_crosshair(canvas, model)
    draw_noise_meter(canvas, model["noise"])
    draw_objective(canvas, model)
    draw_flashlight(canvas, model)
    draw_message(canvas, model)


# --------------------------------------------------------------------------
# Medidor de som
# --------------------------------------------------------------------------
def draw_noise_meter(canvas, noise):
    u = canvas.scale
    x0, y0 = MARGIN * u, MARGIN * u
    rows_base = y0 + 20 * u                       # linha de base da última barra (ENTIDADE)
    panel_x, panel_y = x0 - 10 * u, y0 - 10 * u
    panel_w = (METER_LABEL_W + METER_BAR_W + 22) * u
    panel_h = (METER_ROW * 3 + 54) * u
    canvas.rect(panel_x, panel_y, panel_w, panel_h, with_alpha(SHADE, 0.42))
    canvas.outline(panel_x, panel_y, panel_w, panel_h, max(1.0, u), with_alpha(PAPER, 0.16))
    canvas.text(x0, rows_base + (METER_ROW * 3 + 4) * u, texts.METER_TITLE, 10 * u, PAPER_DIM)
    for row, key in enumerate(("player", "ambient", "entity")):
        y = rows_base + (2 - row) * METER_ROW * u
        _draw_meter_row(canvas, x0, y, noise["labels"][key], noise["levels"][key], noise["peaks"][key],
                        noise["hear_threshold"] if key == "player" else None)
    _draw_threshold_legend(canvas, x0, y0)


def _draw_meter_row(canvas, x, y, label, level, peak, threshold):
    u = canvas.scale
    bar_x, bar_w, bar_h = x + METER_LABEL_W * u, METER_BAR_W * u, METER_BAR_H * u
    canvas.text(x, y, label, 11 * u, PAPER_DIM)
    canvas.rect(bar_x, y, bar_w, bar_h, with_alpha(PAPER, 0.13))
    shown = display_level(level)
    audible = threshold is not None and level >= threshold
    canvas.rect(bar_x, y, bar_w * shown, bar_h, WARNING if audible else with_alpha(PAPER, 0.92))
    if peak > level + 0.01:
        peak_x = bar_x + bar_w * display_level(peak)
        canvas.rect(peak_x - u, y - 2 * u, 2 * u, bar_h + 4 * u, with_alpha(PAPER, 0.85))
    if threshold is not None:
        mark_x = bar_x + bar_w * display_level(threshold)
        canvas.rect(mark_x - 0.75 * u, y - 4 * u, 1.5 * u, bar_h + 8 * u, WARNING)


def _draw_threshold_legend(canvas, x, y):
    u = canvas.scale
    canvas.rect(x, y - 1 * u, 1.5 * u, 7 * u, WARNING)
    canvas.text(x + 7 * u, y, texts.METER_THRESHOLD_HINT, 9 * u, with_alpha(PAPER_DIM, 0.85))


# --------------------------------------------------------------------------
# Objetivo e coleta
# --------------------------------------------------------------------------
def draw_objective(canvas, model):
    u = canvas.scale
    x, y = MARGIN * u, canvas.height - MARGIN * u - 10 * u
    canvas.text(x, y, texts.HUD_OBJECTIVE, 10 * u, PAPER_DIM)
    y -= 20 * u
    used = canvas.wrapped(x, y, model["objective"], 15 * u, PAPER, 380 * u)
    y -= used + 10 * u
    for row in model["collect"]:
        _draw_collect_row(canvas, x, y, row)
        y -= 19 * u


def _draw_collect_row(canvas, x, y, row):
    u = canvas.scale
    box = 9 * u
    canvas.outline(x, y, box, box, max(1.0, u), with_alpha(PAPER, 0.8))
    if row["done"]:
        canvas.rect(x + 2 * u, y + 2 * u, box - 4 * u, box - 4 * u, PAPER)
    label = row["label"] if row["need"] == 1 else f"{row['label']} {row['have']}/{row['need']}"
    canvas.text(x + 17 * u, y - 0.5 * u, label, 13 * u, PAPER if row["done"] else PAPER_DIM)


# --------------------------------------------------------------------------
# Lanterna
# --------------------------------------------------------------------------
def draw_flashlight(canvas, model):
    u = canvas.scale
    right = canvas.width - MARGIN * u
    battery = model["battery"]
    y = MARGIN * u
    if model["stamina"] < 0.995:
        _draw_stamina(canvas, right, y, model)
    if not battery["has"]:
        return
    y += 26 * u
    _draw_spares(canvas, right, y, battery["spare"])
    y += 26 * u
    _draw_battery_bars(canvas, right, y, battery, model["time"])
    canvas.text(right, y + 22 * u, texts.HUD_FLASHLIGHT, 10 * u, PAPER_DIM, "right")


def _draw_battery_bars(canvas, right, y, battery, clock):
    u = canvas.scale
    bar_w, bar_h, gap = 9 * u, 15 * u, 3 * u
    filled = math.ceil(battery["level"] * BATTERY_BARS - 1e-6) if battery["level"] > 0 else 0
    blink = battery["critical"] and int(clock * 3) % 2 == 0
    color = WARNING if battery["low"] else PAPER
    for index in range(BATTERY_BARS):
        x = right - (BATTERY_BARS - index) * (bar_w + gap) + gap
        if index >= filled or battery["swapping"]:
            alpha = 0.14
        elif not battery["on"]:
            alpha = 0.38            # desligada: mostra a carga, mas apagada
        else:
            alpha = 0.14 if blink else 0.92
        canvas.rect(x, y, bar_w, bar_h, with_alpha(color, alpha))


def _draw_spares(canvas, right, y, spare):
    u = canvas.scale
    label = f"{texts.HUD_SPARE}  x{spare}"
    canvas.text(right, y + 2 * u, label, 11 * u, PAPER_DIM if spare else with_alpha(WARNING, 0.9), "right")
    icons_right = right - canvas.text_width(label, 11 * u) - 10 * u
    for index in range(min(spare, 6)):
        x = icons_right - (index + 1) * 12 * u
        canvas.rect(x, y, 8 * u, 13 * u, with_alpha(PAPER, 0.85))
        canvas.rect(x + 2.5 * u, y + 13 * u, 3 * u, 2 * u, with_alpha(PAPER, 0.85))


def _draw_stamina(canvas, right, y, model):
    u = canvas.scale
    width = 130 * u
    tired = model["exhausted"]
    canvas.text(right, y + 7 * u, texts.HUD_STAMINA, 9 * u, WARNING if tired else PAPER_DIM, "right")
    canvas.rect(right - width, y, width, 3 * u, with_alpha(PAPER, 0.13))
    canvas.rect(right - width, y, width * model["stamina"], 3 * u, WARNING if tired else with_alpha(PAPER, 0.8))


# --------------------------------------------------------------------------
# Centro da tela
# --------------------------------------------------------------------------
def draw_crosshair(canvas, model):
    u = canvas.scale
    cx, cy = canvas.width / 2, canvas.height / 2
    active = model["prompt"] is not None
    canvas.rect(cx - 1.5 * u, cy - 1.5 * u, 3 * u, 3 * u, with_alpha(PAPER, 0.85 if active else 0.4))
    if not active:
        return
    tick = with_alpha(PAPER, 0.75)
    canvas.rect(cx - 10 * u, cy - 0.75 * u, 4 * u, 1.5 * u, tick)
    canvas.rect(cx + 6 * u, cy - 0.75 * u, 4 * u, 1.5 * u, tick)
    canvas.rect(cx - 0.75 * u, cy - 10 * u, 1.5 * u, 4 * u, tick)
    canvas.rect(cx - 0.75 * u, cy + 6 * u, 1.5 * u, 4 * u, tick)
    width = canvas.text_width(model["prompt"], 16 * u)
    canvas.rect(cx - width / 2 - 12 * u, cy - 48 * u, width + 24 * u, 26 * u, with_alpha(SHADE, 0.4))
    canvas.text(cx, cy - 42 * u, model["prompt"], 16 * u, PAPER, "center")


def draw_message(canvas, model):
    if not model["message"] or model["message_alpha"] <= 0:
        return
    u = canvas.scale
    alpha = model["message_alpha"]
    lines_top = canvas.height * 0.22
    canvas.wrapped(canvas.width / 2, lines_top, model["message"], 16 * u, with_alpha(PAPER, alpha),
                   canvas.width * 0.6, align="center")


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
