"""A câmera das cutscenes: caminho dos olhos, caminho do olhar, lente, foco, mão que respira e pancadas.

Um `Rig` descreve UM plano contínuo (o "steadicam"): os olhos e o alvo seguem `Path` com velocidade contínua,
o FOV, o roll e o foco são `Curve`. Em cima disso entram a mão do operador (`Hand`, com amplitude ligada ao que
o personagem está fazendo) e as pancadas (`Impact`, um oscilador amortecido que começa em zero: nunca há salto
de posição, só uma sacudida que decai).

Tudo é função do tempo do plano e do palco; o player só avalia e escreve na `CutsceneCam`.
"""
import bisect
import math
import os
from dataclasses import dataclass, field

from .. import conventions as C
from . import curves
from .curves import Curve, Key, Path, as_curve, as_path, damped_impulse, noise

DEPTH_OF_FIELD = os.environ.get("SA_CUTSCENE_DOF", "1") != "0"      # desligável sem mexer em roteiro
HEAD_SCALE = 1.0


# --------------------------------------------------------------------------
# Quaternions (w, x, y, z) e a convenção da câmera do Blender
# --------------------------------------------------------------------------
def qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


def axis_rotation(axis, radians):
    s, c = math.sin(radians / 2.0), math.cos(radians / 2.0)
    return (c, s if axis == "x" else 0.0, s if axis == "y" else 0.0, s if axis == "z" else 0.0)


def camera_quaternion(yaw, pitch, roll):
    """Quaternion (w, x, y, z) de uma câmera do Blender que olha na direção de `yaw`/`pitch` com `roll`.

    A câmera olha para -Z local: girar 90 graus em X deita o eixo de visão no plano do chão (olhando +Y).
    """
    q = axis_rotation("z", yaw)
    q = qmul(q, axis_rotation("x", math.pi / 2.0 + pitch))
    return qmul(q, axis_rotation("z", roll))


def euler_xyz_quaternion(rx, ry, rz):
    """Quaternion de um Euler XYZ do Blender (aplica X, depois Y, depois Z, em eixos fixos)."""
    return qmul(axis_rotation("z", rz), qmul(axis_rotation("y", ry), axis_rotation("x", rx)))


def rotate(q, v):
    """Gira o vetor `v` pelo quaternion unitário `q`."""
    w, x, y, z = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


def quaternion_to_euler_xyz(q):
    """Euler XYZ do Blender (a, b, c) em radianos de um quaternion unitário: R = Rz(c) Ry(b) Rx(a)."""
    w, x, y, z = q
    r20 = 2.0 * (x * z - w * y)
    r21 = 2.0 * (y * z + w * x)
    r22 = 1.0 - 2.0 * (x * x + y * y)
    r10 = 2.0 * (x * y + w * z)
    r00 = 1.0 - 2.0 * (y * y + z * z)
    return (math.atan2(r21, r22), -math.asin(max(-1.0, min(1.0, r20))), math.atan2(r10, r00))


def keep_hemisphere(q, previous):
    """q e -q são a mesma rotação; escolhe o que fica no mesmo hemisfério do quadro anterior (sem dupla cobertura)."""
    if previous is not None and sum(a * b for a, b in zip(q, previous)) < 0.0:
        return tuple(-c for c in q)
    return q


def look_angles(eye, target):
    """(yaw, pitch) em radianos para olhar de `eye` a `target`."""
    dx, dy, dz = (t - e for e, t in zip(eye, target))
    return C.dir_yaw(dx, dy), math.atan2(dz, math.hypot(dx, dy))


def angle_between(qa, qb):
    """Ângulo (radianos) da menor rotação que leva `qa` a `qb`."""
    dot = abs(sum(a * b for a, b in zip(qa, qb)))
    return 2.0 * math.acos(min(1.0, dot))


# --------------------------------------------------------------------------
# A mão do operador
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Style:
    """Quanto cada movimento natural vale com amplitude 1 (metros e graus)."""
    drift_pos: float = 0.004
    drift_rot: float = 0.20
    drift_hz: float = 0.55
    breath_pos: float = 0.004
    breath_rot: float = 0.22
    breath_hz: float = 0.27
    pulse_pos: float = 0.0
    pulse_hz: float = 1.2
    step_bob: float = 0.0           # sobe e desce a cada passo
    step_sway: float = 0.0          # balanço lateral (um ciclo a cada dois passos)
    step_roll: float = 0.0
    step_pitch: float = 0.0
    step_length: float = 0.72       # metros por passo (liga o balanço à distância percorrida)


STYLES = {
    "tripod": Style(0.0004, 0.015, 0.4, 0.0, 0.0),
    "lying": Style(0.0035, 0.18, 0.45, 0.0055, 0.30, 0.19, 0.0009, 1.15),
    "sitting": Style(0.0045, 0.22, 0.50, 0.0050, 0.28, 0.24),
    "stand": Style(0.0040, 0.20, 0.55, 0.0040, 0.22, 0.27),
    "walk": Style(0.0045, 0.22, 0.60, 0.0025, 0.12, 0.27, 0.0, 1.2, 0.024, 0.016, 0.55, 0.45),
    "drive": Style(0.0030, 0.12, 0.50, 0.0020, 0.08, 0.25),
    "panic": Style(0.012, 0.80, 1.10, 0.008, 0.60, 0.60, 0.002, 1.8),
}


@dataclass(frozen=True)
class Hand:
    """Como a câmera treme: `style` diz que corpo é (deitado, andando, no carro), `amount` é a energia
    (número ou `Curve` do tempo do plano) e liga a amplitude à ação: parada em 0, correndo em 1 ou mais."""
    style: str = "stand"
    amount: object = 1.0
    seed: float = 0.0


@dataclass(frozen=True)
class Impact:
    """Pancada em `at` segundos: a câmera é jogada e balança de volta, amortecendo (nunca salta)."""
    at: float
    strength: float = 1.0
    freq: float = 6.5
    damping: float = 5.0
    seed: float = 0.0
    sign: float = 1.0


def _hand_offsets(hand, t, stress, step_phase, speed_gain):
    """(direita, cima, frente) em metros e (guinada, inclinação, giro) em radianos da mão do operador."""
    style = STYLES[hand.style]
    amount = as_curve(hand.amount)(t) * HEAD_SCALE
    s = hand.seed
    drift_w = 2 * math.pi * style.drift_hz
    breath = math.sin(2 * math.pi * style.breath_hz * t + s)
    pulse = math.sin(2 * math.pi * style.pulse_hz * t + 1.7 * s)
    right = style.drift_pos * noise(t * drift_w, 1.0 + s) + 0.003 * stress * noise(t * 34.0, 11.0 + s)
    up = (style.drift_pos * noise(t * drift_w * 0.9, 2.0 + s) + style.breath_pos * breath
          + style.pulse_pos * pulse + 0.003 * stress * noise(t * 31.0, 12.0 + s))
    forward = style.drift_pos * 0.6 * noise(t * drift_w * 1.1, 3.0 + s) + 0.004 * stress * noise(t * 38.0, 13.0 + s)
    yaw = style.drift_rot * noise(t * drift_w * 0.8, 4.0 + s) + 0.9 * stress * noise(t * 33.0, 14.0 + s)
    pitch = (style.drift_rot * noise(t * drift_w * 0.7, 5.0 + s) + style.breath_rot * breath
             + 0.7 * stress * noise(t * 37.0, 15.0 + s))
    roll = style.drift_rot * 0.8 * noise(t * drift_w * 0.6, 6.0 + s) + 1.1 * stress * noise(t * 30.0, 16.0 + s)
    if style.step_bob and step_phase is not None:
        g = speed_gain
        up += -style.step_bob * g * math.cos(2 * math.pi * step_phase)
        right += style.step_sway * g * math.sin(math.pi * step_phase)
        roll += style.step_roll * g * math.sin(math.pi * step_phase)
        pitch += style.step_pitch * g * math.cos(2 * math.pi * step_phase + 0.4)
    k = amount
    return ((right * k, forward * k, up * k),
            tuple(math.radians(v * k) for v in (yaw, pitch, roll)))


HAND_CROSSFADE = 0.9           # s para trocar de um estilo de mão para outro (deitado -> sentado -> andando)


def _hand_blend(hand, t, stress, step_phase, speed_gain):
    """`hand` é uma `Hand` ou uma sequência `((t0, Hand), (t1, Hand), ...)`: na troca os estilos se misturam em vez de saltar."""
    if isinstance(hand, Hand):
        return _hand_offsets(hand, t, stress, step_phase, speed_gain)
    index = 0
    for k, (start, _) in enumerate(hand):
        if t >= start:
            index = k
    current = _hand_offsets(hand[index][1], t, stress, step_phase, speed_gain)
    since = t - hand[index][0]
    if index == 0 or since >= HAND_CROSSFADE:
        return current
    before = _hand_offsets(hand[index - 1][1], t, stress, step_phase, speed_gain)
    w = curves.ease("smooth", since / HAND_CROSSFADE)
    return (tuple(a + (b - a) * w for a, b in zip(before[0], current[0])),
            tuple(a + (b - a) * w for a, b in zip(before[1], current[1])))


def _impact_offsets(impacts, t):
    """Soma das pancadas ativas: (direita, frente, cima) em metros e (guinada, inclinação, giro) em radianos."""
    pos = [0.0, 0.0, 0.0]
    rot = [0.0, 0.0, 0.0]
    for hit in impacts:
        tau = t - hit.at
        if tau <= 0.0 or tau > 4.0 / hit.damping:
            continue
        wave = damped_impulse(tau, hit.freq, hit.damping) * hit.strength * hit.sign
        wave2 = damped_impulse(tau, hit.freq * 1.37, hit.damping * 1.1) * hit.strength
        a = math.sin(hit.seed * 5.3 + 0.7)
        b = math.cos(hit.seed * 3.1 + 1.9)
        pos[0] += 0.016 * a * wave
        pos[1] += 0.022 * wave2
        pos[2] += 0.032 * wave * (0.6 + 0.4 * b)
        rot[0] += math.radians(1.1) * b * wave
        rot[1] += math.radians(1.9) * wave
        rot[2] += math.radians(1.4) * a * wave2
    return pos, rot


# --------------------------------------------------------------------------
# O plano
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Aim:
    """Olhar por ÂNGULOS (graus, yaw do Blender e inclinação) em vez de por um ponto-alvo.

    Um alvo que passa perto dos olhos faz a câmera girar de um lado ao outro num instante; ângulos não têm esse
    problema, então viradas de corpo (olhar a janela e dar meia-volta) usam `Aim`. `toward` converte alvos em
    ângulos nos instantes das chaves, olhando de onde os olhos estão naquele momento.
    """
    yaw: Curve
    pitch: Curve
    distance: float = 3.0                   # para o foco automático

    @classmethod
    def toward(cls, eye, targets, distance=3.0):
        """`eye`: `Path` estático; `targets`: lista de `(t, ponto)` ou `(t, ponto, hold)`."""
        yaws, pitches, last = [], [], None
        for key in targets:
            t, point, hold = (key[0], key[1], key[2] if len(key) > 2 else False)
            yaw, pitch = look_angles(eye.at(t), point)
            yaw = yaw if last is None else curves.unwrap(last, yaw)
            last = yaw
            yaws.append(Key(t, math.degrees(yaw), hold))
            pitches.append(Key(t, math.degrees(pitch), hold))
        return cls(Curve(yaws), Curve(pitches), distance)

    @property
    def times(self):
        return self.yaw.times


class Look:
    """Alvo do olhar por CHAVES de ponto, interpolado em ÂNGULOS a partir dos olhos de cada instante.

    Interpolar o ponto-alvo em linha reta faz a câmera girar de um lado ao outro quando o caminho passa perto
    dos olhos (alvo no teto sobre a cabeça, rosto da entidade colado). Aqui cada chave vira (yaw, pitch) vistos
    de onde os olhos estão agora, e os ângulos (desenrolados, sem salto de 2 pi) seguem curvas suaves. Chaves
    iguais seguidas são parada. Os pontos podem depender do palco (jogador, entidade, carro).
    """

    def __init__(self, keys, distance=None):
        self.keys = curves._as_keys(keys)
        self.times = [k.t for k in self.keys]
        self.holds = [k.hold for k in self.keys]
        self.distance = distance

    def angles(self, t, stage, eye):
        """(yaw, pitch, distância ao alvo) no instante `t` de olhos em `eye`."""
        keys, times = self.keys, self.times
        targets = [tuple(k.value(stage)) if callable(k.value) else tuple(k.value) for k in keys]
        if len(keys) == 1:
            yaw, pitch = look_angles(eye, targets[0])
            return yaw, pitch, curves.dist3(eye, targets[0])
        yaws, pitches, dists, last = [], [], [], None
        for target in targets:
            yaw, pitch = look_angles(eye, target)
            yaw = yaw if last is None else curves.unwrap(last, yaw)
            last = yaw
            yaws.append(yaw)
            pitches.append(pitch)
            dists.append(curves.dist3(eye, target))
        if t <= times[0]:
            return yaws[0], pitches[0], dists[0]
        if t >= times[-1]:
            return yaws[-1], pitches[-1], dists[-1]
        i = bisect.bisect_right(times, t) - 1
        h = times[i + 1] - times[i]
        u = (t - times[i]) / h
        out = []
        for values in (yaws, pitches, dists):
            slopes = curves._pchip_slopes(times, values, self.holds, True)
            out.append(curves._hermite(values[i], values[i + 1], slopes[i], slopes[i + 1], h, u))
        return tuple(out)


@dataclass(frozen=True)
class Rig:
    """Um plano contínuo de câmera. Os pontos de `eye` e o alvo `look` (ou ângulos, `Aim`) são mundo, ou espaço do `mount`."""
    eye: Path
    look: object                      # Look (chaves de ponto, em ângulos), Path de pontos-alvo ou Aim
    fov: Curve = field(default_factory=lambda: Curve.constant(62.0))
    roll: Curve = field(default_factory=lambda: Curve.constant(0.0))
    hand: Hand = field(default_factory=Hand)
    impacts: tuple = ()
    focus: object = None              # Curve (metros), "auto" (distância ao alvo) ou None (sem profundidade de campo)
    fstop: object = None              # número ou Curve; ignorado sem foco
    mount: str = ""                   # objeto que carrega a câmera (o carro): pontos em espaço local dele
    walk: bool = False                # o balanço dos passos acompanha a distância percorrida pelos olhos

    def __post_init__(self):
        object.__setattr__(self, "_travel", self._travel_table())

    def _travel_table(self):
        if not self.walk or self.eye.dynamic:
            return None
        return self.eye.length()[1]

    def step_phase(self, t, stage):
        """Fase de passos (cada 1.0 é um passo) e fator de velocidade (0 parado .. 1 passo normal)."""
        style = STYLES["walk"] if not isinstance(self.hand, Hand) else STYLES[self.hand.style]
        if not isinstance(self.hand, Hand):
            style = next((STYLES[h.style] for _, h in self.hand if STYLES[h.style].step_bob), style)
        if not style.step_bob:
            return None, 1.0
        if self._travel is None:
            return t / (style.step_length / 1.2), 1.0
        table = self._travel
        times = [row[0] for row in table]
        i = min(max(bisect.bisect_right(times, t) - 1, 0), len(table) - 2)
        (ta, da), (tb, db) = table[i], table[i + 1]
        u = 0.0 if tb == ta else (t - ta) / (tb - ta)
        distance = da + (db - da) * min(max(u, 0.0), 1.0)
        vx, vy, _ = self.eye.velocity(t)                  # a velocidade vem da derivada do caminho: sem degraus no balanço
        gain = curves.clamp(math.hypot(vx, vy) / 1.2, 0.0, 1.3)
        return distance / style.step_length, gain

    @property
    def length(self):
        return max(self.eye.times[-1], self.look.times[-1])


@dataclass
class CameraState:
    """Pose da câmera num instante, no espaço do `mount` (ou do mundo, sem mount)."""
    eye: tuple
    yaw: float
    pitch: float
    roll: float
    fov: float
    focus: float | None
    fstop: float | None
    distance: float                   # olhos -> alvo (para o foco automático)
    mount: str = ""


def evaluate(rig, t, stage, stress=0.0, dof=None):
    """Estado da câmera de `rig` no instante `t` do plano (segundos desde o começo dele).

    `dof`: liga/desliga a profundidade de campo (None: o padrão do módulo, `DEPTH_OF_FIELD`).
    """
    eye = rig.eye.at(t, stage)
    if isinstance(rig.look, Aim):
        yaw, pitch = math.radians(rig.look.yaw(t)), math.radians(rig.look.pitch(t))
        distance = rig.look.distance
    elif isinstance(rig.look, Look):
        yaw, pitch, distance = rig.look.angles(t, stage, eye)
    else:
        look = rig.look.at(t, stage)
        yaw, pitch = look_angles(eye, look)
        distance = curves.dist3(eye, look)
    phase, gain = rig.step_phase(t, stage)
    (right, forward, up), (dyaw, dpitch, droll) = _hand_blend(rig.hand, t, stress, phase, gain)
    (ir, if_, iu), (iyaw, ipitch, iroll) = _impact_offsets(rig.impacts, t)
    right, forward, up = right + ir, forward + if_, up + iu
    cy, sy = math.cos(yaw), math.sin(yaw)
    fx, fy = -sy, cy
    position = (eye[0] + right * cy + forward * fx, eye[1] + right * sy + forward * fy, eye[2] + up)
    fov = rig.fov(t)
    roll = math.radians(rig.roll(t)) + droll + iroll
    focus = None
    fstop = None
    if (DEPTH_OF_FIELD if dof is None else dof) and rig.focus is not None:
        focus = distance if rig.focus == "auto" else as_curve(rig.focus)(t)
        fstop = as_curve(rig.fstop if rig.fstop is not None else 2.8)(t)
    return CameraState(position, yaw + dyaw + iyaw, pitch + dpitch + ipitch, roll, fov, focus, fstop, distance,
                       rig.mount)


def rig_from_views(a, b=None, duration=1.0, hand=None, **extra):
    """Rig simples A -> B (a partir de dois `View`): para planos curtos que não pedem spline. Para e parte em repouso."""
    if b is None:
        return Rig(as_path(a.eye), as_path(a.target), Curve.constant(a.fov), Curve.constant(a.roll),
                   hand or Hand(), **extra)
    eye = Path([Key(0.0, a.eye, True), Key(duration, b.eye, True)])
    look = Path([Key(0.0, a.target, True), Key(duration, b.target, True)])
    return Rig(eye, look, Curve([(0.0, a.fov), (duration, b.fov)]), Curve([(0.0, a.roll), (duration, b.roll)]),
               hand or Hand(), **extra)


def apply_lens(cam, state):
    """Escreve FOV e profundidade de campo na câmera. Compatível com o Blender 4.2 e 5.0 (o objeto `dof` é o mesmo)."""
    data = cam.data
    data.angle = math.radians(state.fov)
    dof = getattr(data, "dof", None)
    if dof is None:
        return
    wanted = state.focus is not None
    if dof.use_dof != wanted:
        dof.use_dof = wanted
    if wanted:
        dof.focus_distance = max(0.05, state.focus)
        dof.aperture_fstop = max(0.8, state.fstop)
