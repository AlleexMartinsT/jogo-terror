"""Telas cheias e overlays: título, pausa, leitor de notas, fim de jogo, créditos e cutscenes.

`draw_frame` decide o que desenhar a partir de `model["phase"]`. Nada aqui altera o jogo.
"""
from . import hud, texts
from .canvas import INK, PAPER, PAPER_DIM, SHADE, WARNING, with_alpha, wrap_text

PAPER_SHEET = (0.80, 0.74, 0.56, 1.0)
PAPER_EDGE = (0.36, 0.29, 0.18, 1.0)
LETTERBOX_FRACTION = 0.12


def draw_frame(canvas, model):
    """Um quadro completo do HUD/telas para o `hud_model()` dado."""
    {"title": draw_title, "cutscene": draw_cutscene, "play": draw_playing, "reading": draw_reading,
     "paused": draw_paused, "dead": draw_dead, "credits": draw_credits}[model["phase"]](canvas, model)
    hud.draw_debug(canvas, model)
    hud.draw_error(canvas, model)


def draw_playing(canvas, model):
    hud.draw_gameplay(canvas, model)
    if model["fade_in"] > 0:         # voltou de uma morte: a tela clareia em vez de aparecer de repente
        canvas.rect(0, 0, canvas.width, canvas.height, with_alpha(SHADE, model["fade_in"]))


# --------------------------------------------------------------------------
# Cutscene
# --------------------------------------------------------------------------
def draw_cutscene(canvas, model):
    overlay = model["overlay"]
    u = canvas.scale
    bar = overlay["letterbox"] * canvas.height * LETTERBOX_FRACTION
    canvas.rect(0, 0, canvas.width, bar, SHADE)
    canvas.rect(0, canvas.height - bar, canvas.width, bar, SHADE)
    canvas.rect(0, 0, canvas.width, canvas.height, with_alpha(SHADE, overlay["fade"]))
    if overlay["subtitle"] and overlay["subtitle_alpha"] > 0:
        _draw_subtitle(canvas, overlay["subtitle"], overlay["subtitle_alpha"], bar + 26 * u)
    if overlay["card"]:
        _draw_card(canvas, overlay["card"], max(overlay["fade"], 0.0))
    canvas.rect(0, 0, canvas.width, canvas.height, (1.0, 1.0, 1.0, overlay["flash"]))


def _draw_subtitle(canvas, subtitle, alpha, base_y):
    u = canvas.scale
    size = 19 * u
    lines = wrap_text(canvas, subtitle, size, canvas.width * 0.7)
    height = len(lines) * size * 1.35
    widest = max(canvas.text_width(line, size) for line in lines)
    canvas.rect((canvas.width - widest) / 2 - 16 * u, base_y - 10 * u, widest + 32 * u, height + 12 * u,
                with_alpha(SHADE, 0.5 * alpha))
    for index, line in enumerate(lines):
        y = base_y + (len(lines) - 1 - index) * size * 1.35
        canvas.text(canvas.width / 2, y, line, size, with_alpha(PAPER, alpha), "center")


def _draw_card(canvas, card, backdrop):
    u = canvas.scale
    title, subtitle = card
    cx, cy = canvas.width / 2, canvas.height / 2
    canvas.rect(0, 0, canvas.width, canvas.height, with_alpha(SHADE, max(0.0, 0.9 - backdrop)))
    canvas.text(cx, cy + 6 * u, title, 38 * u, PAPER, "center")
    canvas.rect(cx - 110 * u, cy - 8 * u, 220 * u, u, with_alpha(PAPER, 0.4))
    canvas.wrapped(cx, cy - 32 * u, subtitle, 17 * u, PAPER_DIM, canvas.width * 0.6, align="center")


# --------------------------------------------------------------------------
# Leitor de notas
# --------------------------------------------------------------------------
def draw_reading(canvas, model):
    hud.draw_reader_dim(canvas)
    draw_note(canvas, model["note"])


def draw_note(canvas, note):
    u = canvas.scale
    body_size, title_size, leading = 15 * u, 22 * u, 1.4
    lines = note["body"].split("\n")
    height = (60 + 44) * u + title_size + len(lines) * body_size * leading + 18 * u
    width = 520 * u
    x, y = (canvas.width - width) / 2, (canvas.height - height) / 2
    canvas.rect(x - 3 * u, y - 3 * u, width + 6 * u, height + 6 * u, PAPER_EDGE)
    canvas.rect(x, y, width, height, PAPER_SHEET)
    canvas.rect(x + 30 * u, y + height - 74 * u, width - 60 * u, 1.5 * u, with_alpha(INK, 0.55))
    canvas.text(x + 30 * u, y + height - 52 * u, note["title"], title_size, INK)
    top = y + height - 100 * u
    for index, line in enumerate(lines):
        canvas.text(x + 30 * u, top - index * body_size * leading, line, body_size, with_alpha(INK, 0.92))
    canvas.text(x + width - 30 * u, y + 22 * u, texts.READER_CLOSE, 12 * u, with_alpha(INK, 0.6), "right")


# --------------------------------------------------------------------------
# Título, pausa, morte, créditos
# --------------------------------------------------------------------------
def spaced_text(canvas, cx, y, string, size, color, tracking):
    """Título com espaçamento entre letras (o blf não tem tracking)."""
    widths = [canvas.text_width(ch, size) + tracking for ch in string]
    x = cx - (sum(widths) - tracking) / 2
    for ch, advance in zip(string, widths):
        canvas.text(x, y, ch, size, color)
        x += advance


def draw_controls(canvas, controls, cx, top):
    u = canvas.scale
    for index, (keys, action) in enumerate(controls):
        y = top - index * 24 * u
        canvas.text(cx - 18 * u, y, keys, 14 * u, PAPER, "right")
        canvas.text(cx + 18 * u, y, action, 14 * u, PAPER_DIM)


def draw_title(canvas, model):
    u = canvas.scale
    info = model["title"]
    cx, cy = canvas.width / 2, canvas.height / 2
    canvas.rect(0, 0, canvas.width, canvas.height, with_alpha(SHADE, 0.95))
    spaced_text(canvas, cx, cy + 130 * u, info["name"], 64 * u, PAPER, 10 * u)
    canvas.text(cx, cy + 92 * u, info["subtitle"], 17 * u, PAPER_DIM, "center")
    canvas.rect(cx - 130 * u, cy + 70 * u, 260 * u, u, with_alpha(PAPER, 0.3))
    draw_controls(canvas, info["controls"], cx, cy + 34 * u)
    canvas.text(cx, cy - 200 * u, texts.TITLE_START, 16 * u, PAPER, "center")
    canvas.wrapped(cx, cy - 238 * u, info["tip"], 13 * u, with_alpha(PAPER_DIM, 0.85), canvas.width * 0.6, align="center")


def draw_paused(canvas, model):
    """O único lugar do jogo com objetivo, lista de coleta, medidor completo e controles."""
    u = canvas.scale
    canvas.rect(0, 0, canvas.width, canvas.height, with_alpha(SHADE, 0.84))
    cx, cy = canvas.width / 2, canvas.height / 2
    canvas.text(cx, cy + 250 * u, texts.PAUSE_TITLE, 36 * u, PAPER, "center")
    canvas.rect(cx - 130 * u, cy + 232 * u, 260 * u, u, with_alpha(PAPER, 0.3))
    left, y = cx - 400 * u, cy + 190 * u
    canvas.text(left, y, texts.PAUSE_OBJECTIVE, 11 * u, PAPER_DIM)
    used = canvas.wrapped(left, y - 26 * u, model["objective"], 19 * u, PAPER, 360 * u)
    y -= 26 * u + used + 28 * u
    canvas.text(left, y, texts.PAUSE_COLLECT, 11 * u, PAPER_DIM)
    for index, row in enumerate(model["collect"]):
        _draw_collect_row(canvas, left, y - 26 * u - index * 24 * u, row)
    y -= 26 * u + len(model["collect"]) * 24 * u + 14 * u
    _draw_pause_meter(canvas, model["noise"], left, y)
    canvas.text(cx + 180 * u, cy + 190 * u, texts.PAUSE_CONTROLS, 11 * u, PAPER_DIM, "center")
    draw_controls(canvas, model["title"]["controls"], cx + 180 * u, cy + 164 * u)
    canvas.text(cx, cy - 190 * u, texts.PAUSE_HELP, 16 * u, PAPER, "center")


def _draw_collect_row(canvas, x, y, row):
    u = canvas.scale
    box = 10 * u
    canvas.outline(x, y, box, box, max(1.0, u), with_alpha(PAPER, 0.8))
    if row["done"]:
        canvas.rect(x + 2.5 * u, y + 2.5 * u, box - 5 * u, box - 5 * u, PAPER)
    label = row["label"] if row["need"] == 1 else f"{row['label']} {row['have']}/{row['need']}"
    canvas.text(x + 19 * u, y - 0.5 * u, label, 14 * u, PAPER if row["done"] else PAPER_DIM)


def _draw_pause_meter(canvas, noise, x, y):
    u = canvas.scale
    canvas.text(x, y, texts.METER_TITLE, 11 * u, PAPER_DIM)
    for index, key in enumerate(("player", "ambient", "entity")):
        hud.draw_meter_row(canvas, x, y - 28 * u - index * 26 * u, noise, key)
    hud.draw_threshold_legend(canvas, x, y - 28 * u - 3 * 26 * u - 2 * u)


def draw_dead(canvas, model):
    u = canvas.scale
    info = model["death"]
    cx, cy = canvas.width / 2, canvas.height / 2
    canvas.rect(0, 0, canvas.width, canvas.height, with_alpha(SHADE, 0.9))
    canvas.wrapped(cx, cy + 20 * u, info["card"], 30 * u, WARNING, canvas.width * 0.75, align="center")
    canvas.text(cx, cy - 60 * u, info["retry"], 16 * u, PAPER_DIM, "center")


def draw_credits(canvas, model):
    u = canvas.scale
    title, subtitle = model["ending"]["card"]
    cx, cy = canvas.width / 2, canvas.height / 2
    canvas.rect(0, 0, canvas.width, canvas.height, SHADE)
    canvas.text(cx, cy + 60 * u, title, 38 * u, PAPER, "center")
    canvas.wrapped(cx, cy + 20 * u, subtitle, 17 * u, PAPER_DIM, canvas.width * 0.6, align="center")
    for index, line in enumerate(model["ending"]["credits"]):
        canvas.text(cx, cy - 90 * u - index * 22 * u, line, 13 * u if index else 15 * u,
                    PAPER if index == 0 else with_alpha(PAPER_DIM, 0.9), "center")
    canvas.text(cx, cy - 190 * u, texts.CREDITS_BACK, 14 * u, PAPER_DIM, "center")
