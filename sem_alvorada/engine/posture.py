"""Postura de alcance: o corpo desce, avança e inclina o tronco para chegar ao que está baixo ou longe.

Matemática pura, sem bpy. O `Player` guarda um `ReachPosture` e soma o resultado à câmera (a cabeça desce e avança) e ao
tronco do corpo (`Locomotion` lê `lean`). Quem pede a postura é o `Hands`, quando o gesto de pegar ou de usar a porta
exige mais do que o braço estendido alcança.

Os números vêm de 12 clipes de pegar do chão da CMU, medidos por `tools/movimento_ref/pegar_baixo.py` na escala do Daniel
(olho a 1,65 m): quem se curva (joelhos quase retos, 24 graus) leva o olho 0,78 m para baixo e 0,20 m para a frente, com o
tronco a 73 graus; quem agacha (joelho a 87 graus) leva 0,78 m para baixo e 0,17 m para a frente, com o tronco a 45 graus.
O que está abaixo da profundidade medida é ESTIMADO (proporcional à profundidade).
"""
import math
from dataclasses import dataclass

EYE_STAND = 1.65
DEPTH_MAX = 0.83             # m, MEDIDO: o mergulho mais fundo do olho nos clipes (0,85 m) na escala do Daniel
SHOULDER_DOWN = 0.25         # m, MEDIDO (maos_ego_ref.json): o ombro fica 25 cm abaixo do olho
SHOULDER_BACK = 0.11         # m, MEDIDO: e 11 cm atrás
SHOULDER_SIDE = 0.24         # m, MEDIDO: e 24 cm ao lado
COMFORT_REACH = 0.56         # m, DERIVADO: 85% do alcance do ombro à palma (braço de 0,60 m mais 0,06 m de palma)
EYE_ABOVE_HAND = 0.60        # m, MEDIDO: mediana do olho acima da mão que pega no fundo do gesto (0,55 a 0,78 em 10 clipes)
LUNGE_MAX = 0.25             # m, ESTIMADO: quanto o corpo ainda avança além da técnica (um passo que o jogo não dá)
LUNGE_LEAN = 80.0            # graus de tronco por metro de avanço extra, ESTIMADO
# Cada pessoa escolhe um ponto entre dois extremos, e o que muda ao longo do caminho é o ângulo do tronco: agachar (tronco a
# 24 a 45 graus, joelho a 87 a 137, o quadril cai 0,70 m) e se curvar de pernas retas (tronco a 100 graus, joelho a 7 a 24, o
# quadril cai 0,05 a 0,10 m). Os dois a 0,75 a 0,85 m de profundidade. Por metro de profundidade:
STOOP = {"ahead": 0.35, "lean": 130.0}        # MEDIDO em 69_73 e 69_74 (0,5 m de avanço porque o objeto estava longe: aqui 0,35)
SQUAT = {"ahead": 0.15, "lean": 50.0}         # MEDIDO em 69_70, 69_71 e 69_75 (tronco a 40 graus em 0,8 m)
LEAN_CAP = 115.0             # graus: o mais fundo medido (26_11, 116) tem a cabeça pendente; com avanço extra o tronco passa de 105
LEAN_MAX = 105.0             # graus: acima disso o tronco passaria da horizontal (o mais fundo medido é 116 com a cabeça pendente)
SQUAT_NEAR, SQUAT_FAR = 0.30, 0.80           # m de distância horizontal: até a primeira agacha, a partir da segunda se curva
AHEAD_WALL_MARGIN = 0.22     # m: a câmera para antes da parede (o jogador tem 0,30 m de raio, o plano de corte está a 0,1)


@dataclass(frozen=True)
class Dip:
    """O pico da postura: quanto a cabeça desce (m), avança (m) e quantos graus o tronco se inclina."""
    depth: float = 0.0
    ahead: float = 0.0
    lean: float = 0.0
    down_s: float = 0.0
    up_s: float = 0.0

    @property
    def needed(self):
        return self.depth > 0.04 or self.ahead > 0.04


NONE = Dip()


def descent_seconds(depth):
    """Duração nominal da descida (jerk mínimo). MEDIDO: a descida leva de 0,95 a 1,6 s (mediana 1,1 s, de 4 pontos
    percentuais acima do fundo até 10% dele) em 26_09 a 26_11, 69_70 a 69_75 e 111_17/18, e de 0,5 a 0,7 s nos dois clipes de
    pegar a caixa de ferramentas andando (143_xx). A duração nominal de um jerk mínimo que chega a 90% em 1,1 s é de 1,6 s;
    a do jogo é de 1,35 s a 0,78 m, com o piso de 0,5 s nas profundezas rasas."""
    return min(1.45, max(0.5, 0.45 + 1.15 * depth))


def rise_seconds(depth):
    """Duração nominal da subida. MEDIDO: mediana de 0,93 s (curvar) e 1,3 s (agachar, com um clipe lento de 2,1 s)."""
    return min(1.3, max(0.5, 0.45 + 1.0 * depth))


def technique_mix(horizontal):
    """0 = se curva, 1 = agacha, pela distância horizontal do olho ao alvo: perto agacha, longe se curva."""
    return max(0.0, min(1.0, (SQUAT_FAR - horizontal) / (SQUAT_FAR - SQUAT_NEAR)))


def dip_for_depth(depth, horizontal, wall_distance=None):
    """A postura de profundidade `depth` (m) para um alvo a `horizontal` m de distância."""
    depth = max(0.0, min(DEPTH_MAX, depth))
    mix = technique_mix(horizontal)
    ahead = depth * (STOOP["ahead"] + (SQUAT["ahead"] - STOOP["ahead"]) * mix)
    lean = min(LEAN_MAX, depth * (STOOP["lean"] + (SQUAT["lean"] - STOOP["lean"]) * mix))
    if wall_distance is not None:
        room = max(0.0, wall_distance - AHEAD_WALL_MARGIN)
        if ahead > room and ahead > 1e-6:
            lean *= room / ahead
            ahead = room
    return Dip(depth, ahead, lean, descent_seconds(depth), rise_seconds(depth))


def shoulder_offset(lean):
    """(para trás, para baixo) do ombro em relação ao olho com o tronco inclinado `lean` graus. MEDIDO em pé (0,11 e 0,25 m,
    `assets/referencia/maos_ego_ref.json`) e, curvado, o olho acaba 0,19 m à frente e 0,05 m abaixo do C7 (69_73, 69_74 e
    143_10 a 100 graus): o ombro fica atrás da cabeça. Linear entre os dois."""
    return SHOULDER_BACK + 0.0010 * lean, SHOULDER_DOWN - 0.0025 * lean


def _reaches(dip, forward, lateral, below, shoulder):
    back, down = shoulder_offset(dip.lean)
    gap_forward = forward - dip.ahead + back
    gap_side = lateral - shoulder
    gap_down = below - dip.depth - down
    return math.sqrt(gap_forward ** 2 + gap_side ** 2 + gap_down ** 2) <= COMFORT_REACH


def dip_to_reach(forward, lateral, below, side, wall_distance=None):
    """A menor postura que põe o ponto do alvo ao alcance confortável do braço.

    `forward`, `lateral` e `below` são a distância horizontal à frente do olho, o deslocamento para a direita e quanto o alvo
    está abaixo do olho, todos em metros no referencial do corpo (não da câmera inclinada). `side` é +1 para o braço direito
    e -1 para o esquerdo. A cabeça não desce além de `EYE_ABOVE_HAND` acima do alvo (nos clipes, o olho fica 0,55 a 0,78 m
    acima da mão que pega); se mesmo assim não chega, o corpo avança mais um pouco (`LUNGE_MAX`), e o que faltar é o
    `REACH_LIMIT` do `Hands` (a mão para onde o braço chega)."""
    shoulder = SHOULDER_SIDE * side
    cap = min(DEPTH_MAX, max(0.0, below - EYE_ABOVE_HAND))
    dip = NONE
    for i in range(int(cap / 0.01) + 1):
        dip = dip_for_depth(i * 0.01, forward, wall_distance)
        if _reaches(dip, forward, lateral, below, shoulder):
            return dip
    room = LUNGE_MAX if wall_distance is None else max(0.0, min(LUNGE_MAX, wall_distance - AHEAD_WALL_MARGIN - dip.ahead))
    for i in range(int(room / 0.01) + 1):
        lunge = i * 0.01
        lunged = Dip(dip.depth, dip.ahead + lunge, min(LEAN_CAP, dip.lean + LUNGE_LEAN * lunge), dip.down_s, dip.up_s)
        if _reaches(lunged, forward, lateral, below, shoulder):
            return lunged
    return Dip(dip.depth, dip.ahead + room, min(LEAN_CAP, dip.lean + LUNGE_LEAN * room), dip.down_s, dip.up_s)


class ReachPosture:
    """O estado da postura: uma fração 0..1 que vai de uma a outra em jerk mínimo, com continuidade se mudar no meio."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.amount = 0.0
        self.velocity = 0.0
        self.accel = 0.0
        self.dip = NONE
        self._goal = 0.0
        self._coefficients = None
        self._elapsed = 0.0
        self._seconds = 0.0

    @property
    def active(self):
        return self.amount > 1e-4 or self._coefficients is not None

    @property
    def goal(self):
        return self._goal

    @property
    def depth(self):
        return self.amount * self.dip.depth

    @property
    def ahead(self):
        return self.amount * self.dip.ahead

    @property
    def lean(self):
        return self.amount * self.dip.lean

    def go(self, goal, seconds, dip=None):
        """Vai a `goal` (1 = postura cheia, 0 = em pé) em `seconds`, a partir do estado de agora. `dip` só vale se a
        postura está parada em pé (trocar o formato no meio faria o corpo saltar)."""
        if dip is not None and self.amount < 1e-4:
            self.dip = dip
        self._goal = goal
        if seconds <= 1e-3 or (abs(goal - self.amount) < 1e-5 and abs(self.velocity) < 1e-4):
            self.amount, self.velocity, self.accel = goal, 0.0, 0.0
            self._coefficients = None
            return
        self._coefficients = _quintic(self.amount, self.velocity, self.accel, goal, seconds)
        self._elapsed, self._seconds = 0.0, seconds

    def step(self, dt):
        if self._coefficients is None:
            return
        self._elapsed = min(self._elapsed + dt, self._seconds)
        if self._elapsed >= self._seconds:
            self.amount, self.velocity, self.accel = self._goal, 0.0, 0.0
            self._coefficients = None
            return
        self.amount, self.velocity, self.accel = _quintic_state(self._coefficients, self._elapsed)


def _quintic(x0, v0, a0, goal, seconds):
    """Polinômio de grau 5 de (x0, v0, a0) a `goal` parado, em `seconds` (a mesma curva de jerk mínimo das portas)."""
    d, t = goal - x0, seconds
    c3 = (20 * d - 12 * v0 * t - 3 * a0 * t * t) / (2 * t ** 3)
    c4 = (-30 * d + 16 * v0 * t + 3 * a0 * t * t) / (2 * t ** 4)
    c5 = (12 * d - 6 * v0 * t - a0 * t * t) / (2 * t ** 5)
    return (x0, v0, a0 / 2.0, c3, c4, c5)


def _quintic_state(coefficients, t):
    c0, c1, c2, c3, c4, c5 = coefficients
    x = c0 + t * (c1 + t * (c2 + t * (c3 + t * (c4 + t * c5))))
    v = c1 + t * (2 * c2 + t * (3 * c3 + t * (4 * c4 + t * 5 * c5)))
    a = 2 * c2 + t * (6 * c3 + t * (12 * c4 + t * 20 * c5))
    return x, v, a


def reach_gap(dip, forward, lateral, below, side):
    """Quanto o ponto fica além do alcance confortável do braço (m) com a postura `dip`: 0 se chega."""
    shoulder = SHOULDER_SIDE * side
    back, down = shoulder_offset(dip.lean)
    distance = math.sqrt((forward - dip.ahead + back) ** 2 + (lateral - shoulder) ** 2 + (below - dip.depth - down) ** 2)
    return max(0.0, distance - COMFORT_REACH)
