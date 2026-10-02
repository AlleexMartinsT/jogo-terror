"""Objetos pequenos de uma casa habitada: controle remoto, copos, cartas, óculos, remédios, talheres, guardanapos.

Todos desenham num `MeshBuilder` já em andamento, apoiados em `z0` e centrados em (cx, cy), com giro `yaw`
em graus. Servem de ambientação: ficam sobre móveis e contam o que Daniel fez nas últimas semanas.
"""
from . import furniture_forms as forms
from . import parts


def remote_control(m, cx, cy, z0, yaw=0.0):
    """Controle remoto de TV: corpo preto abaulado, janela de infravermelho, teclado e botão vermelho."""
    with m.at(cx, cy, z0, rz=yaw):
        m.soft_box(0, 0, 0, 0.050, 0.195, 0.022, "tv_black", radius=0.016, edge=0.008, corner_points=3, smooth=True)
        m.box(0, 0.094, 0.0155, 0.026, 0.006, 0.004, "led_red")
        m.box(0.012, 0.075, 0.0221, 0.012, 0.012, 0.001, "led_red")
        for row in range(5):
            for col in range(3):
                m.box(-0.014 + col * 0.014, 0.045 - row * 0.021, 0.0221, 0.01, 0.014, 0.0012, "plastic_gray")
        m.box(0, -0.075, 0.0221, 0.034, 0.012, 0.001, "plastic_beige")


def tumbler(m, cx, cy, z0, fill=0.0, radius=0.036, height=0.095, liquid="coffee_cold"):
    """Copo baixo de vidro grosso; `fill` (0 a 1) deixa líquido escuro até aquela fração da altura."""
    r, h = radius, height
    m.lathe([(0.0, 0.0), (0.82 * r, 0.0), (0.9 * r, 0.004), (r, h * 0.96), (r * 1.01, h), (r * 0.93, h), (r * 0.86, h * 0.14),
             (0.0, h * 0.16)], cx, cy, z0, "glass_clear", seg=forms.seg(18), smooth=True)
    if fill > 0:
        m.cylinder(cx, cy, z0 + h * 0.16, r * 0.88, h * fill, liquid, seg=forms.seg(16))


def envelope_pile(m, cx, cy, z0, rng, count=4):
    """Correspondência fechada que ninguém abriu: envelopes pardos em leque, o de cima com selo vermelho."""
    z = z0
    for index in range(count):
        turn = rng.uniform(-28, 28)
        with m.at(cx + rng.uniform(-0.012, 0.012), cy + rng.uniform(-0.012, 0.012), z, rz=turn):
            m.box(0, 0, 0, 0.225, 0.115, 0.0016, "paper_white", skip=("top",))
            m.panel(0, 0, 0.0017, 0.225, 0.115, "envelope" if index == count - 1 else "paper_white", "top")
        z += 0.0018


def reading_glasses(m, cx, cy, z0, yaw=0.0):
    """Óculos de armação fina dobrado sobre uma superfície: duas lentes redondas, ponte e hastes recolhidas."""
    with m.at(cx, cy, z0, rz=yaw):
        for side in (-1, 1):
            m.torus(side * 0.034, 0, 0.0035, 0.0235, 0.0012, "brass_aged", seg=forms.seg(18), seg_minor=4)
            m.cylinder(side * 0.034, 0, 0.0028, 0.0225, 0.0007, "glass_clear", seg=forms.seg(18))
            m.tube((side * 0.057, 0.0, 0.0035), (side * 0.054, -0.052, 0.0035), 0.0011, "brass_aged", seg=4)
        m.tube((-0.011, 0, 0.0035), (0.011, 0, 0.0035), 0.0011, "brass_aged", seg=4)


def pill_bottle(m, cx, cy, z0, yaw=0.0, lying=False):
    """Frasco alaranjado de remédio com tampa branca; deitado ou em pé."""
    with m.at(cx, cy, z0 + (0.0185 if lying else 0.0), ry=90 if lying else 0, rz=yaw):
        m.lathe([(0.0, 0.0), (0.0165, 0.0), (0.018, 0.003), (0.018, 0.062), (0.0165, 0.07), (0.0, 0.07)], 0, 0, 0,
                "pill_orange", seg=forms.seg(14), smooth=True)
        m.cylinder(0, 0, 0.07, 0.0185, 0.014, "paper_white", seg=forms.seg(14), smooth=True)
        m.cylinder(0, 0, 0.014, 0.0184, 0.04, "paper_white", seg=forms.seg(14), smooth=True)


def fork(m, cx, cy, z0, yaw=0.0, scale=1.0):
    """Garfo de mesa deitado, 19 cm, com quatro dentes."""
    with m.at(cx, cy, z0, rz=yaw):
        s = scale
        m.box(0, -0.045 * s, 0, 0.018 * s, 0.1 * s, 0.0016, "chrome")
        m.box(0, -0.09 * s, 0.0, 0.009 * s, 0.045 * s, 0.0022, "chrome")
        m.box(0, 0.0 * s, 0.0, 0.026 * s, 0.03 * s, 0.0016, "chrome")
        for i in range(4):
            m.box((i - 1.5) * 0.0072 * s, 0.043 * s, 0.0, 0.0028 * s, 0.056 * s, 0.0016, "chrome")


def knife(m, cx, cy, z0, yaw=0.0, scale=1.0):
    """Faca de mesa deitada: cabo e lâmina."""
    with m.at(cx, cy, z0, rz=yaw):
        s = scale
        m.box(0, -0.06 * s, 0, 0.016 * s, 0.075 * s, 0.0035, "chrome")
        m.extrude([(-0.0085 * s, -0.02 * s), (0.0085 * s, -0.02 * s), (0.0085 * s, 0.07 * s), (0.0035 * s, 0.1 * s),
                   (-0.0085 * s, 0.075 * s)], "xy", 0.0, 0.0017, "chrome")


def spoon(m, cx, cy, z0, yaw=0.0, scale=1.0):
    """Colher de sopa: haste e concha oval."""
    with m.at(cx, cy, z0, rz=yaw):
        s = scale
        m.box(0, -0.055 * s, 0, 0.012 * s, 0.1 * s, 0.0018, "chrome")
        m.lathe([(0.0, 0.0), (0.011 * s, 0.0005), (0.0155 * s, 0.003), (0.0, 0.0038)], 0, 0.05 * s, 0.0, "chrome",
                seg=forms.seg(12), smooth=True)


def place_setting(m, cx, cy, z0, yaw, rng, *, plate_mat="porcelain_old", food=None, child=False, plate=True):
    """Lugar posto: prato raso, garfo à esquerda, faca e colher à direita e um copo. Voltado para -Y."""
    scale = 0.8 if child else 1.0
    with m.at(cx, cy, z0, rz=yaw):
        if plate:
            parts.plate(m, 0, 0.02, 0.0, 0.125 * scale, plate_mat, food=food)
        fork(m, -0.165 * scale, 0.0, 0.0, rng.uniform(-3, 3), scale)
        knife(m, 0.155 * scale, 0.0, 0.0, rng.uniform(-3, 3), scale)
        spoon(m, 0.185 * scale, 0.0, 0.0, rng.uniform(-3, 3), scale)
        tumbler(m, 0.12, 0.2, 0.0, fill=0.0 if not food else 0.25, radius=0.032 * scale, height=0.1 * scale, liquid="wine_dark")


