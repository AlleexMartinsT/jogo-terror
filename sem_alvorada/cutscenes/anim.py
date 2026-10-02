"""Biblioteca de animação de objetos das cutscenes.

Cada ator é um `stage.Actor`: `start` guarda o estado original do que vai mexer, `update(stage, dt)` avança e
`stop` devolve tudo (o palco chama `stop` no fim normal e no `skip`). A dinâmica usa osciladores e pêndulos de
`curves` (passos fixos de 1/240 s, estáveis com qualquer `dt`), então a mesma cena roda igual a 30, 60 ou 144 quadros.

Orçamento: tudo aqui é numpy ou aritmética curta; os testes medem o custo por quadro (meta: < 3 ms no conjunto).
"""
import math

import numpy as np

from .. import conventions as C
from . import camera
from .curves import Curve, Pendulum, Spring, clamp, clamp01, ease, hash01, noise, smooth_pulse
from .stage import Actor

GRAVITY = 9.81
WHEEL_RADIUS = 0.33


# --------------------------------------------------------------------------
# Malha deformada por vértice (cortinas, poeira, faíscas)
# --------------------------------------------------------------------------
def _read_vertices(mesh):
    flat = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", flat)
    return flat.reshape(-1, 3)


def _write_vertices(mesh, array):
    mesh.vertices.foreach_set("co", np.ascontiguousarray(array, dtype=np.float32).reshape(-1))
    mesh.update()


class CurtainWind(Actor):
    """Vento nas cortinas: deformação por vértice em numpy, presa na barra e solta na barra de baixo.

    Uma ondulação que percorre a largura, rajadas lentas (`gust`, curva do tempo absoluto da cutscene) e um
    vaivém lateral pequeno. O peso cresce com a distância da barra, então o tecido pesa no alto e voa na bainha.
    """

    def __init__(self, names, strength=1.0, gust=None, seed=0.0, reach=0.20):
        self.names = tuple(names)
        self.strength = strength
        self.gust = gust or Curve.constant(1.0)
        self.seed = seed
        self.reach = reach
        self._cloth = []

    def start(self, stage):
        seen = set()
        for index, name in enumerate(self.names):
            obj = stage.obj(name)
            if obj is None or obj.data in seen:
                continue
            seen.add(obj.data)
            rest = _read_vertices(obj.data)
            z, x, y = rest[:, 2], rest[:, 0], rest[:, 1]
            top, bottom = float(z.max()), float(z.min())
            hang = np.clip((top - z) / max(top - bottom, 1e-3), 0.0, 1.0)
            weight = hang ** 1.4 * np.clip((top - z) / 0.12, 0.0, 1.0)      # a barra de cima não anda
            # a cortina fica entre a parede (y local ~ 0) e o quarto: "para fora" é o sinal de y
            outward = -1.0 if float(y.mean()) < 0.0 else 1.0
            self._cloth.append((obj.data, rest, weight.astype(np.float32), outward, index + self.seed, x))

    def update(self, stage, dt):
        t = stage.t
        gust = self.gust(t) * self.strength
        for mesh, rest, weight, outward, phase, x in self._cloth:
            wave = np.sin(x * 2.3 + t * 1.55 + phase * 1.9) * 0.6 + np.sin(x * 5.1 - t * 2.4 + phase) * 0.4
            billow = 0.55 + 0.45 * math.sin(t * 0.8 + phase)
            push = weight * (0.5 + 0.5 * wave) * (billow * gust * self.reach)
            sway = weight * np.sin(x * 1.1 + t * 0.9 + phase) * (0.35 * gust * self.reach)
            moved = rest.copy()
            moved[:, 1] += outward * push
            moved[:, 0] += sway
            _write_vertices(mesh, moved)

    def stop(self, stage):
        for mesh, rest, *_ in self._cloth:
            _write_vertices(mesh, rest)
        self._cloth.clear()


class DustFall(Actor):
    """Poeira e lascas de reboco caindo do forro a partir de `t0`: balística com arrasto, tudo num objeto só.

    O objeto `Cut_Dust` tem `count` partículas de 4 vértices; aqui cada uma ganha instante de partida, ponto
    no forro, velocidade terminal e tamanho. Partícula fora da vida fica colapsada num ponto (não desenha).
    """

    def __init__(self, center, radius, ceiling_z, floor_z, t0, spread=1.4, seed=1.0, size=1.0, object_name="Cut_Dust"):
        self.center, self.radius = center, radius
        self.ceiling_z, self.floor_z = ceiling_z, floor_z
        self.t0, self.spread = t0, spread
        self.seed, self.size = seed, size
        self.object_name = object_name
        self._obj = None
        self._mesh = None

    def start(self, stage):
        obj = stage.obj(self.object_name)
        if obj is None:
            return
        self._obj = obj
        self._mesh = obj.data
        count = len(self._mesh.vertices) // 4
        k = np.arange(count, dtype=np.float64)
        h = lambda salt: np.abs(np.sin(k * 12.9898 + self.seed * 78.233 + salt) * 43758.5453) % 1.0  # noqa: E731
        self.delay = h(1.0) ** 1.6 * self.spread
        angle, rad = h(2.0) * math.tau, np.sqrt(h(3.0)) * self.radius
        self.x = self.center[0] + np.cos(angle) * rad
        self.y = self.center[1] + np.sin(angle) * rad
        self.terminal = 0.25 + 0.9 * h(4.0) ** 2          # os pedaços grandes caem mais depressa
        self.drift = (h(5.0) - 0.5) * 0.18
        self.grain = (0.0035 + 0.011 * h(6.0) ** 3) * self.size
        self.spin = h(7.0) * math.tau
        base = np.array([[-1, 0, -1], [1, 0, -1], [1, 0, 1], [-1, 0, 1]], dtype=np.float32)
        self._shape = np.tile(base, (count, 1))
        self._count = count

    def update(self, stage, dt):
        if self._mesh is None:
            return
        tau = stage.t - self.t0 - self.delay
        alive = (tau > 0.0) & (self.ceiling_z - self.floor_z > 0.0)
        drag = 2.6
        fall = self.terminal * (tau - (1.0 - np.exp(-drag * np.clip(tau, 0.0, None))) / drag)
        z = self.ceiling_z - 0.02 - fall
        alive &= z > self.floor_z
        size = np.where(alive, self.grain, 0.0)
        c, s = np.cos(self.spin + tau * 2.0), np.sin(self.spin + tau * 2.0)
        corners = self._shape.reshape(self._count, 4, 3)
        px = (self.x + self.drift * np.clip(tau, 0.0, None))[:, None]
        py = self.y[:, None]
        pz = z[:, None]
        verts = np.empty((self._count, 4, 3), dtype=np.float32)
        verts[:, :, 0] = px + corners[:, :, 0] * size[:, None] * c[:, None]
        verts[:, :, 1] = py + corners[:, :, 0] * size[:, None] * s[:, None]
        verts[:, :, 2] = pz + corners[:, :, 2] * size[:, None]
        _write_vertices(self._mesh, verts.reshape(-1, 3))
        self._obj.hide_viewport = self._obj.hide_render = False

    def stop(self, stage):
        if self._obj is not None:
            self._obj.hide_viewport = self._obj.hide_render = True
            if self._mesh is not None:
                _write_vertices(self._mesh, np.zeros((len(self._mesh.vertices), 3), dtype=np.float32))
        self._mesh = None


class SparkBurst(Actor):
    """Faíscas da lâmpada que estoura: partículas balísticas com gravidade, vivem ~0,9 s a partir de `t0`."""

    def __init__(self, origin, t0, speed=2.6, life=0.9, seed=3.0, object_name="Cut_Sparks"):
        self.origin, self.t0, self.speed, self.life, self.seed = origin, t0, speed, life, seed
        self.object_name = object_name
        self._obj = self._mesh = None

    def start(self, stage):
        obj = stage.obj(self.object_name)
        if obj is None:
            return
        self._obj, self._mesh = obj, obj.data
        count = len(self._mesh.vertices) // 4
        k = np.arange(count, dtype=np.float64)
        h = lambda salt: np.abs(np.sin(k * 12.9898 + self.seed * 78.233 + salt) * 43758.5453) % 1.0  # noqa: E731
        az, el = h(1.0) * math.tau, (h(2.0) * 0.9 - 0.2)
        speed = self.speed * (0.35 + 0.65 * h(3.0))
        self.v = np.stack([np.cos(az) * np.cos(el), np.sin(az) * np.cos(el), np.sin(el)], axis=1) * speed[:, None]
        self.life_each = self.life * (0.45 + 0.55 * h(4.0))
        self._count = count
        base = np.array([[-1, 0, 0], [0, 0, -1], [1, 0, 0], [0, 0, 1]], dtype=np.float32)
        self._shape = np.tile(base, (count, 1)).reshape(count, 4, 3)

    def update(self, stage, dt):
        if self._mesh is None:
            return
        tau = np.full(self._count, max(stage.t - self.t0, 0.0))
        alive = (stage.t >= self.t0) & (tau < self.life_each)
        pos = np.array(self.origin)[None, :] + self.v * tau[:, None]
        pos[:, 2] -= 0.5 * GRAVITY * tau ** 2
        size = np.where(alive, 0.010 * (1.0 - tau / self.life_each), 0.0)
        verts = pos[:, None, :] + self._shape * size[:, None, None]
        _write_vertices(self._mesh, verts.reshape(-1, 3))
        self._obj.hide_viewport = self._obj.hide_render = stage.t < self.t0

    def stop(self, stage):
        if self._obj is not None:
            self._obj.hide_viewport = self._obj.hide_render = True
        self._mesh = None


# --------------------------------------------------------------------------
# Emissão (relógio, TV, painel do carro)
# --------------------------------------------------------------------------
class EmissionPulse(Actor):
    """Anima a "Emission Strength" de um material por uma função do tempo e a devolve no fim."""

    def __init__(self, material, level):
        """`level(t)` -> multiplicador sobre a emissão original do material."""
        self.material, self.level = material, level
        self._node = None
        self._base = 0.0

    def start(self, stage):
        import bpy
        mat = bpy.data.materials.get(self.material)
        if mat is None or mat.node_tree is None:
            return
        self._node = next((n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        if self._node is not None:
            self._base = self._node.inputs["Emission Strength"].default_value

    def update(self, stage, dt):
        if self._node is not None:
            self._node.inputs["Emission Strength"].default_value = self._base * max(0.0, self.level(stage.t))

    def stop(self, stage):
        if self._node is not None:
            self._node.inputs["Emission Strength"].default_value = self._base
        self._node = None


def tv_static_level(t, seed=0.0):
    """Chuvisco de TV: brilho que cintila em 24 Hz sem repetir, com quedas curtas de sinal."""
    cell = math.floor(t * 24.0)
    flicker = 0.78 + 0.22 * hash01(cell, seed)
    drop = 0.35 if hash01(math.floor(t * 3.0), seed + 5.0) > 0.86 else 1.0
    return flicker * drop


def clock_level(t, glitches=()):
    """Mostrador do relógio: pulso leve de respiração e falhas rápidas nos instantes de `glitches`."""
    level = 0.92 + 0.08 * math.sin(t * 1.3)
    for g in glitches:
        if g <= t < g + 0.12:
            level *= 0.15 + 0.85 * hash01(math.floor((t - g) * 90.0), g)
    return level


class ClockGlitch(Actor):
    """O despertador (6:47) pisca para 6:12 nos instantes dados: troca com o relógio do final, no mesmo lugar."""

    def __init__(self, times, hold=0.16, real="AlarmClock", ghost="Cut_EndClock"):
        self.times, self.hold, self.real, self.ghost = tuple(times), hold, real, ghost
        self._objs = None
        self._shown = None

    def start(self, stage):
        a, b = stage.obj(self.real), stage.obj(self.ghost)
        if a is not None and b is not None:
            self._objs = (a, b)
            stage.touch(a)

    def update(self, stage, dt):
        if self._objs is None:
            return
        real, ghost = self._objs
        showing_ghost = any(g <= stage.t < g + self.hold for g in self.times)
        if showing_ghost != self._shown:
            self._shown = showing_ghost
            stage.set_hidden(real, showing_ghost)
            stage.set_hidden(ghost, not showing_ghost)

    def stop(self, stage):
        self._objs = None


# --------------------------------------------------------------------------
# O carro
# --------------------------------------------------------------------------
SILL_CROSSINGS = ((1.45, 1.0), (-1.45, -0.8))      # (y do centro do carro quando o eixo passa na soleira, sentido do tranco)


class CarMotion(Actor):
    """O carro sai da garagem: aceleração suave, suspensão, rolagem, motor em marcha lenta e rodas girando.

    O deslocamento é analítico (`smoother`), então a velocidade e a aceleração são contínuas. A suspensão é uma
    mola amortecida alimentada pela aceleração longitudinal (o carro "senta" ao arrancar e "cai" ao frear) e por
    pancadas nas soleiras. Publica `stage.signals["car"]` para o coelhinho, o volante e a câmera presa ao carro.
    """

    def __init__(self, home, stop, move_start, move_end, yaw_deg=180.0, crank_start=None, catch=None, lights_on=None,
                 object_name=C.OBJ_CAR, wander=0.05):
        self.home, self.stop_point = home, stop
        self.t0, self.t1 = move_start, move_end
        self.yaw0 = math.radians(yaw_deg)
        self.crank_start, self.catch = crank_start, catch
        self.lights_on = lights_on
        self.name = object_name
        self.wander = wander
        self._pitch = Spring(1.9, 0.30)
        self._roll = Spring(2.3, 0.28)
        self._heave = Spring(2.6, 0.35)
        self._prev_y = home[1]
        self._crossed = set()
        self._obj = None
        self._wheels = {}

    def start(self, stage):
        self._obj = stage.touch(stage.obj(self.name))
        for wheel in ("FL", "FR", "RL", "RR"):
            obj = stage.touch(stage.obj(f"Car_Wheel_{wheel}"))
            if obj is not None:
                self._wheels[wheel] = obj
        stage.set_mount(self.name, self.home, (0.0, 0.0, self.yaw0))

    # ---- trajetória (analítica: velocidade e aceleração contínuas)
    def _travel(self, t):
        total = self.stop_point[1] - self.home[1]                 # negativo: o carro anda para -Y
        if t <= self.t0:
            return 0.0, 0.0, 0.0
        if t >= self.t1:
            return total, 0.0, 0.0
        span = self.t1 - self.t0
        u = (t - self.t0) / span
        s = total * ease("smoother", u)
        v = total * (30 * u * u - 60 * u ** 3 + 30 * u ** 4) / span
        a = total * (60 * u - 180 * u * u + 120 * u ** 3) / (span * span)
        return s, v, a

    def _engine(self, t):
        """(nível 0..1, girando o motor de arranque). Contínuo: sobe na partida, irregular, firma no "pega"."""
        if self.crank_start is None or t <= self.crank_start:
            return 0.0, False
        crank_level = 0.4 + 0.3 * (0.5 + 0.5 * math.sin((t - self.crank_start) * 21.0)) + 0.1 * noise(t * 9.0, 2.0)
        rise = clamp01((t - self.crank_start) / 0.25)
        if self.catch is None or t < self.catch:
            return crank_level * rise, True
        settle = clamp01((t - self.catch) / 0.35)
        return crank_level * (1.0 - settle) + (1.0 + 0.25 * (1.0 - settle)) * settle, False

    def update(self, stage, dt):
        t = stage.t
        s, v, a_long = self._travel(t)
        total = self.stop_point[1] - self.home[1]
        fade_in = min(1.0, abs(s) / 2.0)
        x = self.home[0] + self.wander * math.sin(2.1 * s) * fade_in               # a mão corrige o volante na rampa
        yaw_extra = math.atan(self.wander * 2.1 * math.cos(2.1 * s) * fade_in) if s else 0.0
        y = self.home[1] + s
        engine, cranking = self._engine(t)
        for index, (threshold, direction) in enumerate(SILL_CROSSINGS):
            if index not in self._crossed and y <= threshold < self._prev_y:
                self._crossed.add(index)
                self._pitch.v += 0.30 * direction
                self._heave.v += 0.20
        self._prev_y = y
        lateral = v * v * yaw_extra
        grade = math.atan(0.054 / abs(total or 1.0)) * clamp01(-s / 2.0)         # a entrada de carros desce até a rua
        pitch = self._pitch.advance(dt, target=0.0105 * a_long)
        roll = self._roll.advance(dt, target=-0.004 * lateral + 0.003 * clamp01(1.0 - abs(t - (self.catch or -9.0)) / 0.3))
        heave = self._heave.advance(dt, target=0.0)
        shudder = engine * (0.0004 * noise(t * 150.0, 1.0) + 0.0003 * math.sin(t * 2 * math.pi * 11.0))
        shudder *= 3.0 if cranking else 1.0
        z = self.home[2] - 0.054 * clamp01(-s / max(abs(total), 1e-3)) + heave * 0.02 + shudder
        pitch_total = pitch - grade + 0.0006 * engine * noise(t * 70.0, 5.0)
        roll_total = roll + 0.0005 * engine * noise(t * 83.0, 6.0)
        euler = (pitch_total, roll_total, self.yaw0 + yaw_extra)
        origin = (x, y, z)
        stage.set_mount(self.name, origin, euler)
        if self._obj is not None:
            self._obj.location = origin
            self._obj.rotation_euler = euler
        spin = -(s / WHEEL_RADIUS)
        steer = clamp(yaw_extra * 2.4, -0.45, 0.45)
        for wheel, obj in self._wheels.items():
            obj.rotation_euler = (spin, 0.0, steer if wheel.startswith("F") else 0.0)
        stage.signals["car"] = {"accel": a_long, "lateral": lateral, "speed": v, "engine": engine,
                                "cranking": cranking, "steer": steer, "pitch": pitch_total, "roll": roll_total,
                                "travel": s}
        self._drive_headlights(stage, t, cranking)

    def _drive_headlights(self, stage, t, cranking):
        """Os faróis oscilam com a bateria enquanto o motor de arranque gira e firmam quando o motor pega."""
        if self.lights_on is None or t < self.lights_on:
            return
        level = 1.0
        if self.catch is not None and t < self.catch + 0.3:
            sag = 0.5 + 0.2 * math.sin((t - self.lights_on) * 26.0)
            settle = clamp01((t - self.catch) / 0.3)
            level = sag * (1.0 - settle) + 1.0 * settle
        stage.headlight_level(level * clamp01((t - self.lights_on) / 0.1))

    def stop(self, stage):
        self._obj = None
        self._wheels.clear()


class PropPath(Actor):
    """Leva um objeto por um caminho no tempo absoluto da cutscene (a chave, a mão que a segura).

    `position`: `Path` com chaves em tempo absoluto (pontos podem depender do palco); `rotation(t, stage)`:
    quaternion (w, x, y, z) ou None para manter a rotação. O objeto só aparece entre `show_from` e `show_to`.
    Publica `stage.signals["prop:<nome>"]` com a aceleração no mundo, que um `CharmPendulum` pode ler.
    """

    def __init__(self, object_name, position, rotation=None, show_from=0.0, show_to=1e9, also=(), mount=""):
        self.object_name, self.position, self.rotation = object_name, position, rotation
        self.mount = mount                      # se houver, posição e rotação estão no espaço desse objeto (o carro)
        self.show_from, self.show_to = show_from, show_to
        self.also = tuple(also)                 # filhos que precisam aparecer e sumir junto (esconder o pai não esconde os filhos)
        self._obj = None
        self._extra = []
        self._history = []

    def start(self, stage):
        self._obj = stage.touch(stage.obj(self.object_name))
        self._extra = [o for o in (stage.obj(n) for n in self.also) if o is not None]
        if self._obj is not None:
            self._obj.rotation_mode = "QUATERNION"
            for obj in [self._obj, *self._extra]:
                stage.set_hidden(obj, True)

    def update(self, stage, dt):
        if self._obj is None:
            return
        t = stage.t
        shown = self.show_from <= t <= self.show_to
        if self._obj.hide_render == shown:
            for obj in [self._obj, *self._extra]:
                stage.set_hidden(obj, not shown)
        point = self.position.at(clamp(t, self.position.times[0], self.position.times[-1]), stage)
        q = self.rotation(t, stage) if self.rotation is not None else None
        if self.mount:
            point = stage.to_world(self.mount, point)
            if q is not None:
                q = camera.qmul(stage.mount_quaternion(self.mount), q)
        self._obj.location = point
        if q is not None:
            self._obj.rotation_quaternion = q
        self._history = (self._history + [(t, point)])[-3:]
        accel = (0.0, 0.0, 0.0)
        if len(self._history) == 3:
            (t0, p0), (t1, p1), (t2, p2) = self._history
            h = (t2 - t0) / 2.0
            if h > 1e-4:
                accel = tuple((p2[i] - 2.0 * p1[i] + p0[i]) / (h * h) for i in range(3))
        stage.signals[f"prop:{self.object_name}"] = accel

    def stop(self, stage):
        self._obj = None


class CharmPendulum(Actor):
    """Coelhinho do retrovisor (ou chaveiro): pêndulo em dois eixos, movido pela aceleração do suporte e pelo motor.

    `source`: "car" lê `stage.signals["car"]`; "prop:<objeto>" lê a aceleração publicada por um `PropPath`.
    """

    def __init__(self, object_name="Cut_Bunny", length=0.22, damping=0.55, source="car", pivot_axis_sign=1.0):
        self.object_name, self.source = object_name, source
        self._x = Pendulum(length, damping)
        self._y = Pendulum(length, damping)
        self._obj = None

    def kick(self, omega_x=0.0, omega_y=0.0):
        self._x.kick(omega_x)
        self._y.kick(omega_y)

    def start(self, stage):
        self._obj = stage.touch(stage.obj(self.object_name))

    def _support(self, stage):
        if self.source == "car":
            car = stage.signals.get("car")
            if not car:
                return 0.0, 0.0, 0.0, 0.0, 0.0
            return car["accel"], car["lateral"], car["engine"], car["pitch"], car["roll"]
        ax, ay, _ = stage.signals.get(self.source, (0.0, 0.0, 0.0))
        return clamp(ay, -12.0, 12.0), clamp(-ax, -12.0, 12.0), 0.0, 0.0, 0.0

    def update(self, stage, dt):
        a_long, a_side, engine, pitch, roll = self._support(stage)
        t = stage.t
        shake = engine * (0.9 * noise(t * 11.0, 7.0) + 0.5 * math.sin(t * 2 * math.pi * 12.5))
        ax = self._x.advance(dt, a_long + 0.25 * shake)
        ay = self._y.advance(dt, -a_side + 0.2 * shake)
        if self._obj is not None:
            self._obj.rotation_euler = (ax - pitch * 0.35, -(ay + roll * 0.35), 0.0)
        stage.signals[f"charm:{self.object_name}"] = (ax, ay)

    def stop(self, stage):
        self._obj = None


class SteeringWheel(Actor):
    """Volante: gira com a direção do carro (relação ~12:1) e treme com o motor, em torno do eixo inclinado da modelagem.

    A malha (`Cut_Wheel`) guarda a inclinação (rx = 65 graus) nos vértices; o giro é um quaternion em torno
    do eixo que essa inclinação deu ao eixo Z do aro.
    """
    AXIS = (0.0, -math.sin(math.radians(65.0)), math.cos(math.radians(65.0)))

    def __init__(self, object_name="Cut_Wheel"):
        self.object_name = object_name
        self._obj = None
        self.angle = 0.0

    def start(self, stage):
        self._obj = stage.touch(stage.obj(self.object_name))
        if self._obj is not None:
            self._obj.rotation_mode = "QUATERNION"

    def set_angle(self, radians):
        self.angle = radians

    def update(self, stage, dt):
        car = stage.signals.get("car")
        engine = car["engine"] if car else 0.0
        steer = car["steer"] if car else 0.0
        spin = self.angle - steer * 9.0 + 0.004 * engine * noise(stage.t * 41.0, 8.0)
        if self._obj is not None:
            s, c = math.sin(spin / 2.0), math.cos(spin / 2.0)
            self._obj.rotation_quaternion = (c, self.AXIS[0] * s, self.AXIS[1] * s, self.AXIS[2] * s)

    def stop(self, stage):
        self._obj = None


class GarageLift(Actor):
    """Portão de enrolar subindo: a mola ruge e o abridor puxa. Parte devagar (folga da corrente), acelera,
    chacoalha nas guias e para com um repique. `sa_open_lift` do objeto manda na altura final.

    O repique usa uma mola (a folha passa um pouco da altura e volta).
    """

    def __init__(self, start, duration, default_lift=2.3, object_name=C.OBJ_GARAGE_ROLLUP):
        self.t0, self.dur, self.default_lift = start, duration, default_lift
        self.name = object_name
        self._obj = None
        self._bounce = Spring(3.4, 0.16)
        self._hit = False
        self.lift = default_lift

    def start(self, stage):
        self._obj = stage.touch(stage.obj(self.name))
        if self._obj is not None:
            self.lift = float(self._obj.get("sa_open_lift", self.default_lift))

    def update(self, stage, dt):
        if self._obj is None:
            return
        t = stage.t
        u = clamp01((t - self.t0) / self.dur)
        # a sacudida do começo (mola tensionando) e a subida em S; o repique vem da mola
        z = self.lift * ease("smoother", u)
        if u >= 1.0 and not self._hit:
            self._hit = True
            self._bounce.v = 0.35
        bounce = self._bounce.advance(dt) * 0.12 if u >= 1.0 else 0.0
        moving = 0.0 < u < 1.0
        rattle = (0.0016 * noise(t * 38.0, 1.0) + 0.0009 * math.sin(t * 90.0)) if moving else 0.0
        jerk = 0.004 * math.exp(-8.0 * max(t - self.t0, 0.0)) * math.sin(60.0 * (t - self.t0)) if t > self.t0 else 0.0
        self._obj.location = (self._obj.location[0], self._obj.location[1], z + bounce + jerk)
        self._obj.rotation_euler = (rattle, rattle * 0.6, 0.0)

    def stop(self, stage):
        self._obj = None


class LightCascade(Actor):
    """Queda de luz em cascata: cada luz da casa pisca e morre no seu instante; a última estoura.

    `plan`: lista de (nome da luz, instante da morte, "die" | "burst"). Antes de morrer a luz tem `lead` s de tremor.
    O ganho é escrito por `stage.house_light`, que passa pelo LightManager do engine.
    """

    def __init__(self, plan, lead=0.6, burst_gain=3.2):
        self.plan = tuple(plan)
        self.lead = lead
        self.burst_gain = burst_gain
        self._last = {}

    def gain(self, t, death, mode):
        if t < death - self.lead:
            return 1.0
        if t >= death:
            if mode == "burst" and t < death + 0.07:
                return self.burst_gain
            return 0.0
        tau = (death - t) / self.lead                          # 1 -> 0
        cell = math.floor(t * 17.0)
        drop = 0.0 if hash01(cell, death) < 0.55 * (1.0 - 0.4 * tau) else 1.0
        return max(0.0, drop * (0.55 + 0.45 * noise(t * 30.0, death)))

    def update(self, stage, dt):
        for name, death, mode in self.plan:
            value = round(self.gain(stage.t, death, mode), 3)
            if self._last.get(name) != value:
                self._last[name] = value
                stage.house_light(name, value)
                if value == 0.0 or value == self.burst_gain:
                    fixture = stage.obj(name.replace("Light_", "Fixture_"))
                    if fixture is not None and value == 0.0:
                        fixture.hide_viewport = fixture.hide_render = True

    def stop(self, stage):
        self._last.clear()
