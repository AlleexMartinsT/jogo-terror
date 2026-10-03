"""Marcha do protagonista: leis de comprimento do passo e tabelas de ciclo, tudo MEDIDO em mocap real.

Matemática pura (sem bpy): o `Player` (cadência, câmera, passos) e o `Locomotion` (pernas, tronco, braços) leem as
mesmas tabelas na mesma fase, e é isso que mantém a câmera dos olhos, o corpo e o som dos passos em fase.

Fonte dos números: `gait_data.py`, gerado por `python -m tools.marcha.extrair` a partir da base de captura da CMU
(Carnegie Mellon University Graphics Lab Motion Capture Database). Cada nó é uma faixa de velocidade (andar lento,
andar, andar rápido, correr, correr rápido, agachado) com a passada média de todos os clipes da faixa, em 50 amostras
por ciclo. O ciclo `c` (0 a 1) começa no toque do calcanhar do pé esquerdo; o pé direito é o esquerdo em `c + 0,5`.
`Player.stride_phase` = `2 pi c`: cada pi é um passo.

Nada aqui inventa movimento: o que o jogo ajusta são a velocidade (entre nós, por interpolação linear) e a escala do
alcance do pé, para o pé em apoio andar para trás exatamente na velocidade do corpo (sem deslizar).
"""
import math

from . import gait_data as D

N = D.PONTOS
LEG = D.LEG_DANIEL                  # coxa + canela do Daniel (m); as tabelas de pé vêm em unidades de perna
G = 9.81
STAND_LEAN = 1.0                    # graus: inclinação do tronco parado (77_02, 111_28, 113_21, 16_33)
RUN_FROM, RUN_TO = 2.1, 3.1         # m/s: a corrida entra aos 2,1 e é plena aos 3,1 (transição humana perto de 2 m/s)
MIN_SPEED = 0.30                    # m/s: abaixo disto o corpo não dá passos
FULL_SPEED = 0.45                   # m/s: a partir daqui as amplitudes do passo são plenas
STEP_EXPONENT = {"walk": D.PASSO_ANDAR[1], "run": D.PASSO_CORRER[1], "crouch": D.PASSO_ANDAR[1]}
START_CYCLE = 0.28                  # onde o ciclo recomeça ao arrancar: pé esquerdo no apoio médio, direito em balanço
FOOT_KEYS = ("pe_frente", "pe_lateral", "pe_alt", "pe")
HEAD_KEYS = ("cab_z", "cab_y", "cab_roll", "cab_pitch", "cab_yaw")
TORSO_KEYS = ("pelve_yaw", "tronco_yaw", "pelve_roll")
ARM_KEYS = ("ombro", "cotovelo")
CENTERED = ("pe_lateral", "cab_z", "cab_y", "cab_roll", "cab_pitch", "cab_yaw", "pelve_yaw", "tronco_yaw", "pelve_roll")


def smoothstep(x):
    x = 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
    return x * x * (3.0 - 2.0 * x)


class Node:
    """Uma faixa de velocidade: curvas do ciclo e os escalares que o jogo usa (passo, apoio, alcance)."""
    __slots__ = ("name", "v", "cadence", "step", "duty", "double", "lean", "curves", "reach")

    def __init__(self, raw):
        self.name = raw["nome"]
        self.v = raw["v"]
        self.cadence = raw["cadencia"]
        self.step = self.v / (self.cadence / 60.0)          # m por passo (um pé ao outro)
        self.duty = raw["apoio"]
        self.double = raw["duplo"]
        self.lean = raw["tronco_incl"] - STAND_LEAN
        self.curves = {k: tuple(v) for k, v in raw["curvas"].items()}
        for k in CENTERED:            # só a oscilação conta: a média é a postura de repouso do Daniel, não a do sujeito
            mean = sum(self.curves[k]) / N
            self.curves[k] = tuple(x - mean for x in self.curves[k])
        front = self.curves["pe_frente"]
        self.reach = (front[0] - front[int(round(self.duty * N)) % N]) * LEG          # quanto o pé anda no apoio (m)


NODES = {mode: sorted((Node(raw) for raw in raws), key=lambda n: n.v) for mode, raws in D.NOS.items()}
MODES = tuple(NODES)


def node_pair(mode, v):
    """(nó a, nó b, peso de b): interpolação linear da velocidade; fora da faixa, o nó da ponta."""
    nodes = NODES[mode]
    if v <= nodes[0].v or len(nodes) == 1:
        return nodes[0], nodes[0], 0.0
    if v >= nodes[-1].v:
        return nodes[-1], nodes[-1], 0.0
    for a, b in zip(nodes, nodes[1:]):
        if v <= b.v:
            return a, b, (v - a.v) / (b.v - a.v)
    return nodes[-1], nodes[-1], 0.0


def mode_weights(speed, crouch):
    """(andar, correr, agachado): quanto cada família de passada vale agora. `crouch` é a fração 0..1 do agachado."""
    crouch = 0.0 if crouch < 0.0 else 1.0 if crouch > 1.0 else crouch
    run = smoothstep((speed - RUN_FROM) / (RUN_TO - RUN_FROM))
    return (1.0 - crouch) * (1.0 - run), (1.0 - crouch) * run, crouch


def mode_step(mode, v):
    """Comprimento do passo (m) da família `mode` a `v` m/s: interpolado entre os nós, lei de potência fora deles
    (passo ~ v^b, com b ajustado no mocap)."""
    nodes = NODES[mode]
    v = max(v, 0.05)
    if v <= nodes[0].v:
        return nodes[0].step * (v / nodes[0].v) ** STEP_EXPONENT[mode]
    if v >= nodes[-1].v:
        return nodes[-1].step * (v / nodes[-1].v) ** STEP_EXPONENT[mode]
    a, b, w = node_pair(mode, v)
    return a.step + (b.step - a.step) * w


def step_length(speed, weights):
    """Passo (m) a `speed` m/s com as famílias nos pesos `weights` (de `mode_weights`)."""
    return sum(w * mode_step(mode, speed) for mode, w in zip(MODES, weights) if w > 1e-6)


def cadence(speed, weights):
    """Passos por minuto."""
    return 60.0 * speed / max(step_length(speed, weights), 1e-6)


def amplitude(speed):
    """0..1: o passo vai de parado a pleno entre MIN_SPEED e FULL_SPEED (os pés não 'marcham' no lugar)."""
    return smoothstep((speed - 0.12) / (FULL_SPEED - 0.12))


def _cubic_weights(c):
    """Índices e pesos de Catmull-Rom periódico para a fração de ciclo `c` (0..1)."""
    x = (c % 1.0) * N
    i = int(x)
    t = x - i
    t2, t3 = t * t, t * t * t
    return (((i - 1) % N, (i % N), ((i + 1) % N), ((i + 2) % N)),
            (-0.5 * t3 + t2 - 0.5 * t, 1.5 * t3 - 2.5 * t2 + 1.0, -1.5 * t3 + 2.0 * t2 + 0.5 * t, 0.5 * t3 - 0.5 * t2))


def sample(table, c):
    """Valor da tabela periódica `table` (N amostras) na fração de ciclo `c`."""
    (i0, i1, i2, i3), (w0, w1, w2, w3) = _cubic_weights(c)
    return table[i0] * w0 + table[i1] * w1 + table[i2] * w2 + table[i3] * w3


class Sampled:
    """Curvas amostradas num instante: valores do pé de referência (esquerdo, em `c`) e do outro pé (em `c + 0,5`)."""
    __slots__ = ("c", "speed", "weights", "step", "duty", "reach", "lean", "lean_crouch", "values", "other")


def evaluate(c, speed, crouch=0.0, keys=None):
    """Amostra as curvas medidas em `c` para `speed` m/s e `crouch` (0..1).

    `values[k]` é a curva k em `c`; `other[k]`, em `c + 0,5` (o pé direito, o braço esquerdo). Alcance, passo, apoio
    e inclinação do tronco vêm interpolados entre os nós."""
    weights = mode_weights(speed, crouch)
    out = Sampled()
    out.c, out.speed, out.weights = c, speed, weights
    keys = keys or tuple(D.NOS["walk"][0]["curvas"])
    here, there = _cubic_weights(c), _cubic_weights(c + 0.5)
    values = dict.fromkeys(keys, 0.0)
    other = dict.fromkeys(keys, 0.0)
    duty = reach = lean = lean_crouch = 0.0
    for mode, wm in zip(MODES, weights):
        if wm <= 1e-6:
            continue
        a, b, wb = node_pair(mode, speed)
        for node, wn in ((a, 1.0 - wb), (b, wb)):
            if wn <= 1e-6:
                continue
            w = wm * wn
            for k in keys:
                table = node.curves[k]
                (i0, i1, i2, i3), (w0, w1, w2, w3) = here
                values[k] += w * (table[i0] * w0 + table[i1] * w1 + table[i2] * w2 + table[i3] * w3)
                (i0, i1, i2, i3), (w0, w1, w2, w3) = there
                other[k] += w * (table[i0] * w0 + table[i1] * w1 + table[i2] * w2 + table[i3] * w3)
            duty += w * node.duty
            reach += w * node.reach
            if mode == "crouch":
                lean_crouch += w * node.lean
            else:
                lean += w * node.lean
    out.values, out.other = values, other
    out.duty, out.reach, out.lean, out.lean_crouch = duty, reach, lean, lean_crouch
    out.step = step_length(speed, weights)
    return out


def foot_scale(sampled):
    """Escala do avanço do pé: o passo da lei (extrapolado fora dos nós) sobre o passo que as tabelas medidas têm
    naquela velocidade. Dentro da faixa medida vale 1 (a trajetória do tornozelo é a do mocap, que já inclui o rolar
    do pé sobre o chão); fora dela o pé anda mais ou menos na proporção do passo."""
    ref = sum(w * _clamped_step(mode, sampled.speed) for mode, w in zip(MODES, sampled.weights) if w > 1e-6)
    return max(0.4, min(1.8, sampled.step / max(ref, 1e-6)))


def _clamped_step(mode, v):
    nodes = NODES[mode]
    return mode_step(mode, min(max(v, nodes[0].v), nodes[-1].v))


# ---- ângulos da câmera ----
def camera_euler(yaw, pitch, roll):
    """Euler XYZ do Blender (rx, ry, rz) de uma câmera que olha `yaw`/`pitch` com `roll` em torno do eixo de visão.

    R = Rz(yaw) Rx(pi/2 + pitch) Rz(roll): o roll é em torno do eixo óptico (-Z da câmera). A conversão é a de
    `R = Rz(c) Ry(b) Rx(a)`."""
    cy, sy = math.cos(yaw), math.sin(yaw)
    px = math.pi / 2.0 + pitch
    cp, sp = math.cos(px), math.sin(px)
    cr, sr = math.cos(roll), math.sin(roll)
    # Rx(px) Rz(roll)
    m = [[cr, -sr, 0.0], [cp * sr, cp * cr, -sp], [sp * sr, sp * cr, cp]]
    # Rz(yaw) @ m
    r = [[cy * m[0][j] - sy * m[1][j] for j in range(3)],
         [sy * m[0][j] + cy * m[1][j] for j in range(3)],
         [m[2][j] for j in range(3)]]
    b = -math.asin(max(-1.0, min(1.0, r[2][0])))
    if abs(r[2][0]) < 0.99999:
        a = math.atan2(r[2][1], r[2][2])
        c = math.atan2(r[1][0], r[0][0])
    else:
        a = math.atan2(-r[1][2], r[1][1])
        c = 0.0
    return (a, b, c)
