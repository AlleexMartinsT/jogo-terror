"""Texturas desenhadas do carro (256 a 512 px, filtro linear): trinca do para-brisa, placa, painel de instrumentos,
rádio e flanco do pneu. A tinta, a poeira e a ferrugem não são imagens: são nós procedurais (ver `mat_carro`).

Importar este módulo registra as imagens em `textures.TEXTURES` e os materiais do carro em `materials`.
"""
import math

from . import textures
from .textures import Canvas

CRACK_SIZE = (512, 256)
PLATE_SIZE = (256, 128)
CLUSTER_SIZE = (512, 256)
RADIO_SIZE = (256, 128)
SIDEWALL_SIZE = (1024, 128)

# O impacto que trincou o vidro: (u, v) na imagem. u cresce com +X, então 0,73 cai no lado do passageiro.
CRACK_ORIGIN = (0.73, 0.52)


def _crack_branch(canvas, rng, x, y, angle, length, width, reach):
    """Uma trinca que se ramifica: segmentos tortos, às vezes com um galho lateral."""
    travelled = 0.0
    while travelled < length:
        angle += rng.uniform(-0.28, 0.28)
        step = rng.uniform(6.0, 14.0)
        nx, ny = x + step * math.cos(angle), y + step * math.sin(angle)
        canvas.line(x, y, nx, ny, (0.88, 0.92, 0.94, 0.92), width)
        if reach > 0 and rng.random() < 0.22:
            side = angle + rng.choice((-1, 1)) * rng.uniform(0.5, 1.1)
            _crack_branch(canvas, rng, nx, ny, side, length * 0.35, max(1.0, width - 0.7), reach - 1)
        x, y, travelled = nx, ny, travelled + step


def draw_windshield_crack(rng):
    """Vidro levemente escurecido com uma teia de trincas saindo do ponto de impacto, mais fechada perto dele."""
    width, height = CRACK_SIZE
    canvas = Canvas(width, height, (0.03, 0.05, 0.06, 0.12))
    cx, cy = CRACK_ORIGIN[0] * width, (1.0 - CRACK_ORIGIN[1]) * height
    for index in range(15):
        angle = index * math.tau / 15 + rng.uniform(-0.18, 0.18)
        _crack_branch(canvas, rng, cx, cy, angle, rng.uniform(70, 260), 2.0 if index % 3 == 0 else 1.4, 2)
    for radius in (14, 28, 48, 78):
        for _ in range(int(radius / 4) + 4):
            a0 = rng.uniform(0, math.tau)
            span = rng.uniform(0.15, 0.4)
            canvas.line(cx + radius * math.cos(a0), cy + 0.82 * radius * math.sin(a0),
                        cx + radius * math.cos(a0 + span), cy + 0.82 * radius * math.sin(a0 + span),
                        (0.86, 0.9, 0.93, 0.78), 1.3)
    canvas.ellipse(cx, cy, 7, 6, (0.9, 0.93, 0.95, 0.85))
    canvas.ellipse(cx, cy, 3, 3, (0.2, 0.22, 0.24, 0.9))
    return canvas


def draw_plate(rng):
    """Placa de Ohio: fundo claro, faixa azul com o estado, número em preto, adesivo de validade vencido."""
    width, height = PLATE_SIZE
    canvas = Canvas(width, height, (0.62, 0.60, 0.52, 1.0))
    canvas.rect(0, 0, width, 26, (0.14, 0.2, 0.36, 1.0))
    canvas.rect(0, height - 12, width, height, (0.14, 0.2, 0.36, 1.0))
    canvas.text(width // 2 - canvas.text_width("OHIO", 3) // 2, 4, "OHIO", (0.88, 0.86, 0.75, 1.0), 3)
    canvas.text(width // 2 - canvas.text_width("HGT 6127", 5) // 2, 50, "HGT 6127", (0.10, 0.12, 0.2, 1.0), 5)
    canvas.rect(width - 46, 30, width - 6, 48, (0.52, 0.12, 0.08, 1.0))
    canvas.text(width - 41, 34, "09 98", (0.9, 0.85, 0.7, 1.0), 2)
    canvas.rect(0, 0, 3, height, (0.1, 0.1, 0.1, 0.5))
    canvas.rect(width - 3, 0, width, height, (0.1, 0.1, 0.1, 0.5))
    canvas.grain(rng, 0.05)
    canvas.tint((0.18, 0.15, 0.1), 0.18)
    return canvas


def _dial(canvas, cx, cy, radius, ticks, start_deg, end_deg, label, needle_deg, color):
    """Mostrador analógico: arco, marcas, rótulo e ponteiro."""
    canvas.ellipse(cx, cy, radius, radius, (0.03, 0.03, 0.035, 1.0))
    canvas.ellipse(cx, cy, radius - 3, radius - 3, (0.05, 0.05, 0.055, 1.0))
    for i in range(ticks + 1):
        angle = math.radians(start_deg + (end_deg - start_deg) * i / ticks)
        major = i % 2 == 0
        inner = radius * (0.74 if major else 0.82)
        canvas.line(cx + inner * math.cos(angle), cy - inner * math.sin(angle),
                    cx + radius * 0.92 * math.cos(angle), cy - radius * 0.92 * math.sin(angle),
                    (*color, 1.0), 2.0 if major else 1.0)
    canvas.text(int(cx - canvas.text_width(label, 1) / 2), int(cy + radius * 0.42), label, (*color, 1.0), 1)
    angle = math.radians(needle_deg)
    canvas.line(cx, cy, cx + radius * 0.8 * math.cos(angle), cy - radius * 0.8 * math.sin(angle), (1.0, 0.45, 0.12, 1.0), 2.5)
    canvas.ellipse(cx, cy, 5, 5, (0.12, 0.12, 0.12, 1.0))


def draw_cluster(rng):
    """Painel de instrumentos: velocímetro parado em zero, combustível quase vazio, temperatura fria, luzes de aviso."""
    width, height = CLUSTER_SIZE
    canvas = Canvas(width, height, (0.012, 0.012, 0.014, 1.0))
    green = (0.55, 0.95, 0.62)
    _dial(canvas, 150, 128, 104, 12, 225, -45, "MPH", 225, green)
    canvas.rect(120, 150, 182, 168, (0.0, 0.0, 0.0, 1.0))
    canvas.text(126, 154, "041877", (0.45, 0.9, 0.5, 1.0), 2)
    _dial(canvas, 345, 80, 56, 4, 135, 45, "F  E", 130, green)
    _dial(canvas, 345, 190, 50, 4, 135, 45, "C  H", 132, green)
    for index, (label, color) in enumerate((("BATT", (1.0, 0.25, 0.1)), ("OIL", (1.0, 0.25, 0.1)),
                                            ("CHECK", (1.0, 0.65, 0.12)), ("DOOR", (1.0, 0.25, 0.1)))):
        x = 410 + (index % 2) * 50
        y = 40 + (index // 2) * 60
        canvas.rect(x, y, x + 44, y + 36, (0.04, 0.04, 0.04, 1.0))
        lit = label in ("CHECK", "BATT")
        canvas.text(x + 4, y + 14, label, (*color, 1.0) if lit else (*color, 0.12), 1)
    canvas.grain(rng, 0.04)
    return canvas


def draw_radio(rng):
    """Rádio com toca-fitas: mostrador apagado, botões, fenda da fita e dois knobs."""
    width, height = RADIO_SIZE
    canvas = Canvas(width, height, (0.06, 0.06, 0.065, 1.0))
    canvas.rect(14, 12, 150, 44, (0.02, 0.05, 0.03, 1.0))
    canvas.text(24, 22, "AM 1230", (0.25, 0.55, 0.3, 0.55), 2)
    canvas.rect(14, 56, 190, 70, (0.01, 0.01, 0.01, 1.0))
    for index in range(6):
        canvas.rect(14 + index * 31, 84, 14 + index * 31 + 26, 104, (0.12, 0.12, 0.13, 1.0))
        canvas.text(20 + index * 31, 90, str(index + 1), (0.7, 0.7, 0.66, 1.0), 1)
    for cx in (216, 216):
        canvas.ellipse(cx, 30, 15, 15, (0.14, 0.14, 0.15, 1.0))
        canvas.line(cx, 30, cx + 6, 21, (0.7, 0.7, 0.66, 1.0), 2.0)
    canvas.ellipse(216, 80, 15, 15, (0.14, 0.14, 0.15, 1.0))
    canvas.line(216, 80, 208, 72, (0.7, 0.7, 0.66, 1.0), 2.0)
    canvas.grain(rng, 0.05)
    return canvas


def draw_tire_sidewall(rng):
    """Flanco do pneu, desenrolado: letras em relevo, faixa de desgaste e um aro branco desbotado."""
    width, height = SIDEWALL_SIZE
    canvas = Canvas(width, height, (0.05, 0.05, 0.055, 1.0))
    canvas.rect(0, 14, width, 20, (0.17, 0.17, 0.17, 1.0))
    text, cursor = "RIDGE TRAC RADIAL   P205/70R15 95S   TUBELESS   M+S   ", 0
    while cursor < width:
        canvas.text(cursor, 50, text, (0.34, 0.34, 0.33, 1.0), 3)
        cursor += canvas.text_width(text, 3) + 40
    canvas.rect(0, 104, width, 108, (0.12, 0.12, 0.12, 1.0))
    canvas.grain(rng, 0.12)
    return canvas


textures.TEXTURES.update({
    "car_windshield_crack": draw_windshield_crack,
    "car_plate": draw_plate,
    "car_cluster": draw_cluster,
    "car_radio": draw_radio,
    "car_tire_sidewall": draw_tire_sidewall,
})


def register():
    """Registra os materiais do carro (importação tardia: `mat_carro` precisa do bpy)."""
    from . import mat_carro
    mat_carro.register()



register()
