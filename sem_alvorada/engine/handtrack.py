"""Animação das mãos em dados: chaves, trilhas e o executor que toca um clipe por vez.

Um clipe é uma tabela de canais (`"R.pos"`, `"L.curl"`, `"x.cap"`...) com chaves no tempo, mais uma lista de
eventos nomeados (`contact`, `click`, `done`...). O executor garante:

* um clipe por vez (`start` troca o anterior);
* eventos em ordem, mesmo quando um quadro longo atravessa vários;
* nenhuma descontinuidade: ao trocar de fonte (base -> clipe, clipe -> base, clipe -> clipe) a diferença
  entre o que estava na tela e o que a nova fonte pede vira um deslocamento que decai por amortecimento
  crítico, com a velocidade também emendada. A mão nunca teletransporta, nem quando o clipe é interrompido.

Os valores são sempre tuplas de floats (escalares viram tuplas de um item). As rotações (canais `*.rot`) são
quaternions (w, x, y, z): interpolar ângulos de Euler passa por orientações absurdas perto de um eixo
vertical ("gimbal"), e várias garras da mão ficam exatamente ali.
"""
import math
from bisect import bisect_right
from dataclasses import dataclass, field

import bpy  # noqa: F401 - `mathutils` só existe depois deste import
from mathutils import Quaternion

FOLLOW_RATE = 13.0          # 1/s: quão depressa uma emenda é absorvida (~0,35 s para sumir)
VELOCITY_PROBE = 1.0 / 240.0


@dataclass(frozen=True)
class Key:
    t: float
    value: tuple
    stop: bool = False       # a velocidade zera nesta chave: parada deliberada (contato, clique)
    space: str = "cam"       # "cam" = absoluto; outro nome = somado ao âncora de mesmo nome (ex.: "grasp")


@dataclass(frozen=True)
class Event:
    t: float
    name: str
    arg: object = None
    essential: bool = False  # muda estado de jogo: roda mesmo que o clipe seja interrompido


@dataclass
class Clip:
    name: str
    duration: float
    tracks: dict                                  # canal -> Track
    events: list = field(default_factory=list)    # [Event] (o executor soma o `done` final)
    interruptible: bool = False                   # pode ser substituído por outro sem terminar
    meta: dict = field(default_factory=dict)      # o que o dono do clipe precisa saber (item, mão, âncora)

    def __post_init__(self):
        done = Event(self.duration, "done", essential=True)
        self.events = sorted([*self.events, done], key=lambda e: e.t)


def number(value):
    return tuple(float(x) for x in (value if isinstance(value, (tuple, list)) else (value,)))


def track(*keys):
    """`track((t, valor), (t, valor, "stop"), (t, valor, "stop", "grasp"))` -> Track."""
    built = []
    for item in keys:
        t, value, *flags = item
        built.append(Key(float(t), number(value), stop="stop" in flags,
                         space=next((f for f in flags if f != "stop"), "cam")))
    return Track(built)


class Track:
    """Curva de um canal: Hermite cúbico monótono (não passa de uma chave a outra para além delas)."""

    def __init__(self, keys):
        self.keys = sorted(keys, key=lambda k: k.t)
        self.times = [k.t for k in self.keys]
        self.size = len(self.keys[0].value)

    @property
    def end(self):
        return self.keys[-1].t

    def _resolved(self, index, anchors):
        key = self.keys[index]
        if key.space == "cam" or not anchors or key.space not in anchors:
            return key.value
        return tuple(a + b for a, b in zip(key.value, anchors[key.space]))

    def _tangent(self, index, anchors):
        last = len(self.keys) - 1
        key = self.keys[index]
        if index == 0 or index == last or key.stop:
            return (0.0,) * self.size
        before, here, after = (self._resolved(index + d, anchors) for d in (-1, 0, 1))
        h0 = key.t - self.keys[index - 1].t
        h1 = self.keys[index + 1].t - key.t
        tangent = []
        for b, c, a in zip(before, here, after):
            d0, d1 = (c - b) / h0, (a - c) / h1
            if d0 * d1 <= 0.0:
                tangent.append(0.0)                    # extremo local: sem sobressalto entre as chaves
            else:
                m = (h1 * d0 + h0 * d1) / (h0 + h1)    # média ponderada pelo tempo
                limit = 3.0 * min(abs(d0), abs(d1))
                tangent.append(math.copysign(min(abs(m), limit), m))
        return tuple(tangent)

    def sample(self, t, anchors=None):
        if t <= self.times[0]:
            return self._resolved(0, anchors)
        if t >= self.times[-1]:
            return self._resolved(len(self.keys) - 1, anchors)
        i = bisect_right(self.times, t) - 1
        h = self.times[i + 1] - self.times[i]
        s = (t - self.times[i]) / h
        p0, p1 = self._resolved(i, anchors), self._resolved(i + 1, anchors)
        m0, m1 = self._tangent(i, anchors), self._tangent(i + 1, anchors)
        s2, s3 = s * s, s * s * s
        h00, h10, h01, h11 = 2 * s3 - 3 * s2 + 1, s3 - 2 * s2 + s, -2 * s3 + 3 * s2, s3 - s2
        return tuple(h00 * a + h10 * h * ma + h01 * b + h11 * h * mb
                     for a, b, ma, mb in zip(p0, p1, m0, m1))


def _align(q, reference):
    """O mesmo quaternion, no hemisfério de `reference` (q e -q são a mesma rotação)."""
    return tuple(-x for x in q) if sum(a * b for a, b in zip(q, reference)) < 0.0 else tuple(q)


def _normalize(q):
    length = math.sqrt(sum(x * x for x in q)) or 1.0
    return tuple(x / length for x in q)


def _quaternion(values):
    return Quaternion(values)


def _log(q):
    """Vetor de rotação (eixo * metade do ângulo) de um quaternion unitário."""
    vector = q.axis * (q.angle / 2.0) if q.angle > 1e-9 else q.axis * 0.0
    return vector


def _exp(vector):
    angle = vector.length
    if angle < 1e-9:
        return Quaternion((1.0, 0.0, 0.0, 0.0))
    return Quaternion(vector / angle, 2.0 * angle)


class QuatTrack(Track):
    """Curva de uma rotação: SQUAD entre quaternions (sem saltos de eixo, sem sobressalto entre as chaves)."""

    def __init__(self, keys):
        super().__init__(keys)
        aligned = []
        previous = None
        for key in self.keys:
            value = _normalize(key.value) if previous is None else _align(_normalize(key.value), previous)
            aligned.append(Key(key.t, value, key.stop, key.space))
            previous = value
        self.keys = aligned
        self._quats = [_quaternion(k.value) for k in self.keys]
        self._control = [self._control_point(i) for i in range(len(self.keys))]

    def _control_point(self, index):
        keys, quats = self.keys, self._quats
        if index == 0 or index == len(keys) - 1 or keys[index].stop:
            return quats[index]
        here = quats[index]
        toward_next = _log(here.inverted() @ quats[index + 1])
        toward_previous = _log(here.inverted() @ quats[index - 1])
        return here @ _exp((toward_next + toward_previous) * -0.25)

    def sample(self, t, anchors=None):
        if t <= self.times[0]:
            return tuple(self.keys[0].value)
        if t >= self.times[-1]:
            return tuple(self.keys[-1].value)
        i = bisect_right(self.times, t) - 1
        u = (t - self.times[i]) / (self.times[i + 1] - self.times[i])
        a, b = self._quats[i], self._quats[i + 1]
        edge = a.slerp(b, u)
        inner = self._control[i].slerp(self._control[i + 1], u)
        result = edge.slerp(inner, 2.0 * u * (1.0 - u))
        return _align(tuple(result), self.keys[i].value)


class _Channel:
    __slots__ = ("out", "vel", "off", "offv", "kind")

    def __init__(self, value, kind):
        zero = (0.0,) * len(value)
        self.out, self.vel, self.off, self.offv, self.kind = value, zero, zero, zero, kind


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


class ClipPlayer:
    """Toca um `Clip` por vez sobre uma base (a pose de repouso de cada canal).

    `update(dt, base_fn, anchors, fire)`: `base_fn()` devolve {canal: valor} da pose de repouso (chamada depois
    dos eventos, porque eles podem mudar o estado); `anchors` é {"grasp": {canal: valor}} para chaves com `space`;
    `fire(evento)` recebe cada evento na ordem. Devolve {canal: valor} de todos os canais da base e do clipe.
    """

    def __init__(self, follow_rate=FOLLOW_RATE):
        self.follow = follow_rate
        self.clip = None
        self.time = 0.0
        self.serial = 0
        self._channels = {}
        self._next_event = 0

    # ---- controle ----
    @property
    def active(self):
        return self.clip is not None

    def start(self, clip):
        self.serial += 1
        self.clip = clip
        self.time = 0.0
        self._next_event = 0

    def rebase(self):
        """A base mudou de repente (outro item na mão): o próximo quadro emenda em vez de pular."""
        for channel in self._channels.values():
            channel.kind = None

    def abort(self, fire):
        """Interrompe: os eventos essenciais que faltam rodam na hora, os demais se perdem."""
        clip = self.clip
        if clip is None:
            return []
        self.clip = None                    # antes dos eventos: um deles pode começar outro clipe
        pending = [event for event in clip.events[self._next_event:] if event.essential]
        for event in pending:
            fire(event)
        return pending

    # ---- quadro a quadro ----
    def update(self, dt, base_fn, anchors, fire):
        if self.clip is not None and dt > 0:
            self._advance(dt, fire)
        base = base_fn()
        clip, time = self.clip, self.time
        names = set(base) | (set(clip.tracks) if clip is not None else set())
        out = {}
        for name in names:
            if clip is not None and name in clip.tracks:
                curve = clip.tracks[name]
                grasp = anchors.get(name) if anchors else None
                here = curve.sample(time, {"grasp": grasp} if grasp is not None else None)
                ahead = curve.sample(time + VELOCITY_PROBE, {"grasp": grasp} if grasp is not None else None)
                source = (here, tuple((b - a) / VELOCITY_PROBE for a, b in zip(here, ahead)), f"clip{self.serial}")
            else:
                value = base[name]
                source = (value, (0.0,) * len(value), "base")
            out[name] = self._settle(name, source, dt)
        return out

    def _advance(self, dt, fire):
        clip = self.clip
        target = self.time + dt
        finishing = target >= clip.duration
        if finishing:
            self.clip = None                # os eventos finais já rodam com o clipe encerrado
        self.time = min(target, clip.duration)
        events = clip.events
        while self._next_event < len(events) and events[self._next_event].t <= target + 1e-9:
            event = events[self._next_event]
            self._next_event += 1
            fire(event)
            if self.clip is not (None if finishing else clip):
                return                      # um evento começou outro clipe: ele cuida do resto

    def _settle(self, name, source, dt):
        value, source_velocity, kind = source
        rotation = name.endswith(".rot")
        channel = self._channels.get(name)
        if channel is None:
            channel = self._channels[name] = _Channel(value, kind)
            return channel.out
        if channel.kind != kind:
            if rotation and sum(a * b for a, b in zip(channel.out, value)) < 0.0:
                channel.out = tuple(-x for x in channel.out)             # a mesma rotação, no hemisfério da fonte nova
                channel.vel = tuple(-x for x in channel.vel)
            channel.off = _sub(channel.out, value)
            channel.offv = _sub(channel.vel, source_velocity)
            channel.kind = kind
        if dt > 0:
            decay = math.exp(-self.follow * dt)
            new_off, new_offv = [], []
            for x, v in zip(channel.off, channel.offv):
                push = v + self.follow * x
                new_off.append((x + push * dt) * decay)
                new_offv.append((v - self.follow * push * dt) * decay)
            channel.off, channel.offv = tuple(new_off), tuple(new_offv)
            previous = channel.out
            channel.out = _add(value, channel.off)
            if rotation:
                channel.out = _normalize(channel.out)
            channel.vel = tuple((a - b) / dt for a, b in zip(channel.out, previous))
        else:
            channel.out = _add(value, channel.off)
            if rotation:
                channel.out = _normalize(channel.out)
        return channel.out

    def current(self, name):
        channel = self._channels.get(name)
        return None if channel is None else channel.out
