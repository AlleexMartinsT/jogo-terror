"""Matemática das cutscenes: curvas de aceleração, chaves com tangentes contínuas, ruído e osciladores.

Nada aqui conhece o Blender nem o engine, então tudo roda (e é testado) em Python puro.

Escolhas que importam para a fluidez:
    * `Curve` e `Path` interpolam por Hermite cúbico com tangentes calculadas dos vizinhos. A velocidade é
      contínua nas chaves (sem o tranco de "A para B, depois B para C"); uma chave `hold` zera a velocidade
      ali (parada de verdade), e as pontas do trecho começam e terminam em repouso, a menos que se peça o contrário.
    * `Curve` (escalar) usa tangentes que nunca ultrapassam as chaves vizinhas (PCHIP): o FOV, o roll e o foco
      não "passam" do valor pedido.
    * `Path` (3D) usa Catmull-Rom com tempos desiguais: a câmera passa exatamente pelos pontos.
"""
import bisect
import math

TWO_PI = 2.0 * math.pi


def clamp(value, low, high):
    return low if value < low else high if value > high else value


def clamp01(value):
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def lerp(a, b, f):
    return a + (b - a) * f


def lerp3(a, b, f):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f)


def add3(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub3(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale3(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def norm3(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def dist3(a, b):
    return norm3(sub3(a, b))


def wrap_pi(angle):
    """Leva um ângulo para (-pi, pi]."""
    return (angle + math.pi) % TWO_PI - math.pi


def unwrap(previous, angle):
    """`angle` somado de voltas inteiras até ficar o mais perto possível de `previous` (sem salto de 2 pi)."""
    return angle + TWO_PI * round((previous - angle) / TWO_PI)


# --------------------------------------------------------------------------
# Curvas de aceleração 0..1 -> 0..1
# --------------------------------------------------------------------------
def _ease_in_out_back(u):
    c = 1.2
    if u < 0.5:
        return (2 * u) ** 2 * ((c + 1) * 2 * u - c) / 2
    return ((2 * u - 2) ** 2 * ((c + 1) * (2 * u - 2) + c) + 2) / 2


EASES = {
    "linear": lambda u: u,
    "in": lambda u: u * u,
    "out": lambda u: 1.0 - (1.0 - u) ** 2,
    "smooth": lambda u: u * u * (3.0 - 2.0 * u),
    "smoother": lambda u: u * u * u * (u * (u * 6.0 - 15.0) + 10.0),
    "cubic_in": lambda u: u * u * u,
    "cubic_out": lambda u: 1.0 - (1.0 - u) ** 3,
    "back": _ease_in_out_back,
}


def ease(name, u):
    """Curvas de aceleração de 0..1 para 0..1."""
    u = clamp01(u)
    try:
        return EASES[name](u)
    except KeyError:
        raise ValueError(f"curva desconhecida: {name!r}") from None


# --------------------------------------------------------------------------
# Chaves
# --------------------------------------------------------------------------
class Key:
    """Ponto de um caminho ou de uma curva: instante `t` (s, relativo ao plano), valor e se a velocidade zera ali."""
    __slots__ = ("t", "value", "hold")

    def __init__(self, t, value, hold=False):
        self.t = float(t)
        self.value = value
        self.hold = hold

    def __repr__(self):
        return f"Key({self.t}, {self.value!r}{', hold' if self.hold else ''})"


def _as_keys(keys):
    out = [k if isinstance(k, Key) else Key(*k) for k in keys]
    for a, b in zip(out, out[1:]):
        if b.t <= a.t:
            raise ValueError(f"chaves fora de ordem ou repetidas: t={a.t} -> t={b.t}")
    if len(out) < 1:
        raise ValueError("uma curva precisa de pelo menos uma chave")
    return out


def _pchip_slopes(times, values, holds, rest_ends):
    n = len(times)
    if n == 1:
        return [0.0]
    h = [times[i + 1] - times[i] for i in range(n - 1)]
    delta = [(values[i + 1] - values[i]) / h[i] for i in range(n - 1)]
    slopes = [0.0] * n
    for i in range(1, n - 1):
        if holds[i] or delta[i - 1] * delta[i] <= 0.0:
            slopes[i] = 0.0
        else:
            w1, w2 = 2.0 * h[i] + h[i - 1], h[i] + 2.0 * h[i - 1]
            slopes[i] = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])
    if rest_ends:
        slopes[0] = slopes[-1] = 0.0
    else:
        slopes[0] = 0.0 if holds[0] else delta[0]
        slopes[-1] = 0.0 if holds[-1] else delta[-1]
    return slopes


def _hermite(p0, p1, m0, m1, h, u):
    u2, u3 = u * u, u * u * u
    return ((2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * h * m0
            + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * h * m1)


class Curve:
    """Escalar no tempo: chaves `(t, valor)` ou `(t, valor, hold)`. Fora do intervalo mantém o valor da ponta."""

    def __init__(self, keys, rest_ends=True):
        self.keys = _as_keys(keys)
        self.times = [k.t for k in self.keys]
        values = [float(k.value) for k in self.keys]
        self.values = values
        self.slopes = _pchip_slopes(self.times, values, [k.hold for k in self.keys], rest_ends)

    @classmethod
    def constant(cls, value):
        return cls([(0.0, value)])

    def __call__(self, t):
        times = self.times
        if t <= times[0]:
            return self.values[0]
        if t >= times[-1]:
            return self.values[-1]
        i = bisect.bisect_right(times, t) - 1
        h = times[i + 1] - times[i]
        return _hermite(self.values[i], self.values[i + 1], self.slopes[i], self.slopes[i + 1], h, (t - times[i]) / h)


def as_curve(value):
    """Número -> curva constante; curva -> ela mesma; lista de chaves -> `Curve`."""
    if isinstance(value, Curve):
        return value
    if isinstance(value, (int, float)):
        return Curve.constant(value)
    return Curve(value)


class Path:
    """Caminho 3D por Catmull-Rom com tempos desiguais; os pontos podem ser `stage -> (x, y, z)`.

    A velocidade é contínua em cada chave, então um plano com cinco chaves é um movimento só. Para o
    câmera parar de verdade num ponto, a chave leva `hold`.
    """

    def __init__(self, keys, rest_ends=True, tension=1.0):
        self.keys = _as_keys(keys)
        self.rest_ends = rest_ends
        self.tension = tension
        self.times = [k.t for k in self.keys]
        self.dynamic = any(callable(k.value) for k in self.keys)
        self._cached = None if self.dynamic else self._tangents([k.value for k in self.keys])
        self._points = None if self.dynamic else [tuple(k.value) for k in self.keys]

    @classmethod
    def still(cls, point):
        return cls([(0.0, point)])

    def _tangents(self, points):
        n, times = len(points), self.times
        if n == 1:
            return [(0.0, 0.0, 0.0)]
        out = []
        for i in range(n):
            if (i in (0, n - 1) and self.rest_ends) or self.keys[i].hold:
                out.append((0.0, 0.0, 0.0))
                continue
            lo, hi = max(i - 1, 0), min(i + 1, n - 1)
            span = times[hi] - times[lo]
            out.append(tuple(self.tension * (points[hi][c] - points[lo][c]) / span for c in range(3)))
        return out

    def resolve(self, stage):
        """(pontos, tangentes) deste instante: só recalcula quando algum ponto depende do palco."""
        if not self.dynamic:
            return self._points, self._cached
        points = [tuple(k.value(stage)) if callable(k.value) else tuple(k.value) for k in self.keys]
        return points, self._tangents(points)

    def at(self, t, stage=None, resolved=None):
        points, tangents = resolved or self.resolve(stage)
        times = self.times
        if t <= times[0]:
            return points[0]
        if t >= times[-1]:
            return points[-1]
        i = bisect.bisect_right(times, t) - 1
        h = times[i + 1] - times[i]
        u = (t - times[i]) / h
        return tuple(_hermite(points[i][c], points[i + 1][c], tangents[i][c], tangents[i + 1][c], h, u)
                     for c in range(3))

    def velocity(self, t, stage=None, step=1e-3):
        resolved = self.resolve(stage)
        a, b = self.at(t - step, stage, resolved), self.at(t + step, stage, resolved)
        return scale3(sub3(b, a), 0.5 / step)

    def length(self, stage=None, samples=96):
        """Comprimento aproximado do caminho (m) e tabela de distância acumulada por amostra."""
        resolved = self.resolve(stage)
        t0, t1 = self.times[0], self.times[-1]
        prev = self.at(t0, stage, resolved)
        table, total = [(t0, 0.0)], 0.0
        for k in range(1, samples + 1):
            t = t0 + (t1 - t0) * k / samples
            point = self.at(t, stage, resolved)
            total += dist3(prev, point)
            table.append((t, total))
            prev = point
        return total, table


def as_path(value):
    if isinstance(value, Path):
        return value
    if callable(value) or (isinstance(value, tuple) and len(value) == 3 and not isinstance(value[0], (tuple, list, Key))):
        return Path.still(value)
    return Path(value)


def walk_keys(points, duration, hold_ends=True):
    """Chaves de um caminho percorrido em passo constante: o tempo de cada ponto é proporcional à distância.

    Dá a cadência de quem anda sem parar em cada ponto (sem o "stop and go" de tempos uniformes).
    """
    pts = [tuple(p) for p in points]
    legs = [dist3(a, b) for a, b in zip(pts, pts[1:])]
    total = sum(legs) or 1.0
    t, keys = 0.0, [Key(0.0, pts[0], hold=hold_ends)]
    for leg, point in zip(legs, pts[1:]):
        t += duration * leg / total
        keys.append(Key(t, point))
    keys[-1].hold = hold_ends
    return keys


# --------------------------------------------------------------------------
# Ruído suave e determinístico
# --------------------------------------------------------------------------
_PARTIALS = ((1.0, 0.0, 1.0), (2.17, 1.3, 0.5), (4.63, 2.9, 0.25), (9.11, 4.1, 0.12))


def noise(t, seed=0.0, octaves=3):
    """Ruído contínuo em torno de [-1, 1]: senos de frequências incomensuráveis, mais forte nas baixas."""
    total, weight = 0.0, 0.0
    s = seed * 12.9898
    for k in range(min(octaves, len(_PARTIALS))):
        freq, phase, amp = _PARTIALS[k]
        total += amp * math.sin(t * freq + phase + s * (1.0 + 0.37 * k))
        weight += amp
    return total / weight


def hash01(n, seed=0.0):
    return (math.sin(n * 127.1 + seed * 311.7) * 43758.5453) % 1.0


# --------------------------------------------------------------------------
# Osciladores
# --------------------------------------------------------------------------
def damped_impulse(tau, freq_hz, damping):
    """Resposta de um oscilador amortecido a uma pancada em tau=0: zero no início, depois balança e some."""
    if tau <= 0.0:
        return 0.0
    return math.exp(-damping * tau) * math.sin(TWO_PI * freq_hz * tau)


class Spring:
    """Mola amortecida de uma dimensão, integrada em passos fixos (estável para qualquer `dt` de quadro).

    `x'' = -k (x - alvo) - c x'` com k = (2 pi f)^2 e c = 2 zeta (2 pi f).
    """
    STEP = 1.0 / 240.0

    def __init__(self, freq_hz, damping_ratio, x=0.0, v=0.0):
        self.k = (TWO_PI * freq_hz) ** 2
        self.c = 2.0 * damping_ratio * TWO_PI * freq_hz
        self.x, self.v = x, v

    def advance(self, dt, target=0.0, force=0.0):
        remaining = dt
        while remaining > 1e-9:
            h = min(self.STEP, remaining)
            accel = -self.k * (self.x - target) - self.c * self.v + force
            self.v += accel * h
            self.x += self.v * h
            remaining -= h
        return self.x


class Pendulum:
    """Pêndulo amortecido que balança com uma aceleração do suporte (o coelhinho do retrovisor, o chaveiro).

    `theta` é o ângulo em relação à vertical; `support_accel` é a aceleração horizontal do ponto de fixação
    no plano do balanço (m/s2): quando o carro acelera para a frente, o pêndulo vai para trás.
    """
    STEP = 1.0 / 240.0

    def __init__(self, length, damping=0.9, theta=0.0, omega=0.0, limit=1.3):
        self.length = length
        self.damping = damping
        self.theta, self.omega = theta, omega
        self.limit = limit

    def advance(self, dt, support_accel=0.0, g=9.81):
        remaining = dt
        while remaining > 1e-9:
            h = min(self.STEP, remaining)
            alpha = (-(g / self.length) * math.sin(self.theta) - self.damping * self.omega
                     - (support_accel / self.length) * math.cos(self.theta))
            self.omega += alpha * h
            self.theta = clamp(self.theta + self.omega * h, -self.limit, self.limit)
            remaining -= h
        return self.theta

    def kick(self, omega):
        self.omega += omega


def smooth_pulse(t, start, rise, hold, fall):
    """Pulso 0 -> 1 -> 0: sobe em `rise`, fica `hold`, desce em `fall` (todos suaves)."""
    if t <= start or t >= start + rise + hold + fall:
        return 0.0
    if t < start + rise:
        return ease("smooth", (t - start) / rise)
    if t < start + rise + hold:
        return 1.0
    return 1.0 - ease("smooth", (t - start - rise - hold) / fall)
