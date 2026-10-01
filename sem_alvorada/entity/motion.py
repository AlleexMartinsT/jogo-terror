"""Animação procedural do Alto: cada quadro é calculado por senos, ruído e IK, sem actions.

O runtime roda dentro de um operador modal, então nada aqui depende de `scene.frame_set`.
Entrada: nome da animação, relógio e velocidade. Saída: uma `skeleton.Solution` (rotações
locais de cada osso, posições das juntas). A `rig.EntityRig` só copia isso para a cena.

Convenção dos ângulos (graus, eixos fixos da armadura, ver skeleton.py):
    X positivo  balança um osso que aponta para baixo PARA A FRENTE; num osso que aponta para cima
                inclina o topo PARA TRÁS (olhar para cima). Inclinar o tronco para a frente é X negativo.
    Y positivo  inclina o topo de um osso vertical para a direita da entidade (+X).
    Z positivo  gira para a esquerda da entidade (guinada).
"""
import math
from dataclasses import dataclass

import bpy  # noqa: F401
from mathutils import Quaternion, Vector

from . import skeleton as S

AXIS_X, AXIS_Y, AXIS_Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))

ANIMATIONS = ("idle", "stalk", "walk", "run", "attack", "stare", "twitch", "appear")
APPEAR_DURATION = 2.8
APPEAR_FPS = 8.0                         # a entrada "aos trancos", como quadros perdidos
BLEND_SECONDS = {"attack": 0.12, "twitch": 0.05, "appear": 0.0, "stare": 0.45}
DEFAULT_BLEND = 0.30
LOOK_LIMIT_YAW = 80.0
LOOK_LIMIT_PITCH_UP = 40.0
LOOK_LIMIT_PITCH_DOWN = 35.0
INDOOR_HEAD_LIMIT = 2.42            # topo da cabeça sob o forro (pé-direito 2,6 m): ele anda encurvado dentro da casa


# --------------------------------------------------------------------------
# Utilidades numéricas
# --------------------------------------------------------------------------
def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(value, low=0.0, high=1.0):
    t = clamp((value - low) / (high - low), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def rotation(x=0.0, y=0.0, z=0.0):
    """Quaternion de ângulos em graus: guinada (Z), depois inclinação (X), depois giro (Y)."""
    return (Quaternion(AXIS_Z, math.radians(z)) @ Quaternion(AXIS_X, math.radians(x))
            @ Quaternion(AXIS_Y, math.radians(y)))


def wobble(t, seed, rate=1.0):
    """Ruído suave em [-1, 1]: três senos de frequências incomensuráveis."""
    s = seed * 12.9898
    return (math.sin(t * rate + s) + 0.6 * math.sin(t * rate * 2.31 + s * 1.7)
            + 0.3 * math.sin(t * rate * 4.77 + s * 2.3)) / 1.9


def hash01(n, seed):
    """Número pseudo-aleatório determinístico em [0, 1) para o inteiro `n`."""
    return (math.sin(n * 127.1 + seed * 311.7) * 43758.5453) % 1.0


def spasm(t, seed, rate, decay=5.0, chance=0.6):
    """Espasmos: a cada 1/rate segundos, com probabilidade `chance`, o valor salta e decai."""
    slot = math.floor(t * rate)
    if hash01(slot, seed) > chance:
        return 0.0
    amplitude = hash01(slot, seed + 17.0) * 2.0 - 1.0
    age = t - slot / rate
    return amplitude * math.exp(-age * decay)


# --------------------------------------------------------------------------
# Construtor de poses
# --------------------------------------------------------------------------
class Pose:
    """Acumula ângulos (graus) por osso e metas de IK; converte para `PoseSpec` no fim."""

    def __init__(self):
        self.angles = {}
        self.hips = Vector((0.0, 0.0, 0.0))
        self.goals = {}
        self.world = {}

    def add(self, bone, x=0.0, y=0.0, z=0.0):
        entry = self.angles.setdefault(bone, [0.0, 0.0, 0.0])
        entry[0] += x
        entry[1] += y
        entry[2] += z

    def foot(self, side, x, y, z=0.0, pitch=0.0, toe_out=6.0):
        """Coloca o tornozelo em (x, y, z + altura do tornozelo) e o pé com inclinação `pitch`."""
        upper = f"Thigh.{side}"
        self.goals[upper] = S.IKGoal(Vector((x, y, S.ANKLE_Z + z)))
        outward = toe_out if side == "L" else -toe_out
        self.world[f"Foot.{side}"] = rotation(x=pitch, z=outward)

    def to_spec(self):
        rot = {bone: rotation(*angles) for bone, angles in self.angles.items()}
        return S.PoseSpec(rot=rot, hips_shift=self.hips.copy(), ik=dict(self.goals),
                          world_rot=dict(self.world))


def lean(pose, degrees):
    """Inclina o tronco para a frente `degrees`, repartido pelas três vértebras."""
    for name, share in (("Spine1", 0.30), ("Spine2", 0.35), ("Spine3", 0.35)):
        pose.add(name, x=-degrees * share)


def twist_torso(pose, yaw, roll=0.0):
    for name, share in (("Spine1", 0.3), ("Spine2", 0.35), ("Spine3", 0.35)):
        pose.add(name, y=roll * share, z=yaw * share)


def arm(pose, side, pitch=0.0, abduct=0.0, elbow=0.0, twist=0.0, wrist=0.0):
    """Braço em FK: `pitch` para a frente, `abduct` para fora, `elbow` dobra o antebraço para a frente."""
    sx = S.side_sign(side)
    pose.add(f"UpperArm.{side}", x=pitch, y=-sx * abduct, z=twist)
    pose.add(f"Forearm.{side}", x=elbow)
    pose.add(f"Hand.{side}", x=wrist)


def hand(pose, side, curl_a, curl_b, spread=0.0, thumb=None, jitter=0.0, t=0.0, seed=0):
    """Dedos: `curl_a/curl_b` fecham as falanges em direção à palma; `jitter` desencontra os dedos."""
    sx = S.side_sign(side)
    for index, finger in enumerate(S.FINGER_NAMES):
        noise = jitter * wobble(t, seed + index * 3.1, 2.3)
        pose.add(f"{finger}A.{side}", x=math.copysign(spread, S.FINGER_Y[finger]), y=sx * (curl_a + noise))
        pose.add(f"{finger}B.{side}", y=sx * (curl_b + noise * 1.3))
    pose.add(f"Thumb.{side}", y=sx * (curl_a * 0.7 if thumb is None else thumb))


def coat_sway(pose, front, back):
    for side in ("L", "R"):
        pose.add(f"CoatFront.{side}", x=front[side])
        pose.add(f"CoatBack.{side}", x=back[side])


def apply_look(pose, yaw, pitch, weight):
    """Olhar para um ponto: a cabeça e o pescoço giram; um pouco do tronco acompanha."""
    if weight <= 0.0:
        return
    pose.add("Spine3", z=yaw * 0.10 * weight)
    pose.add("Neck", x=pitch * 0.40 * weight, z=yaw * 0.38 * weight)
    pose.add("Head", x=pitch * 0.60 * weight, z=yaw * 0.52 * weight)


# --------------------------------------------------------------------------
# Marcha
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Gait:
    stride: float        # quanto o pé anda para trás, em relação ao quadril, durante o apoio (m)
    duty: float          # fração do ciclo com o pé no chão
    lift: float          # altura máxima do pé no balanço (m)
    hip_drop: float      # quadril abaixado (m)
    bob: float           # sobe e desce do quadril (m)
    sway: float          # deslocamento lateral do quadril (m)
    lean: float          # tronco inclinado para a frente (graus)
    nominal_speed: float


GAITS = {
    "walk": Gait(stride=0.95, duty=0.62, lift=0.15, hip_drop=0.06, bob=0.035, sway=0.040, lean=7.0,
                 nominal_speed=1.5),
    "run": Gait(stride=1.10, duty=0.30, lift=0.32, hip_drop=0.24, bob=0.11, sway=0.030, lean=27.0,
                nominal_speed=4.1),
    "stalk": Gait(stride=0.72, duty=0.78, lift=0.20, hip_drop=0.36, bob=0.020, sway=0.030, lean=30.0,
                  nominal_speed=0.9),
}


def cadence(name, speed):
    """Ciclos de passada por segundo para andar `speed` m/s sem escorregar os pés."""
    gait = GAITS[name]
    return clamp(speed * gait.duty / gait.stride, 0.30, 2.8)


def foot_cycle(gait, p, irregular):
    """(y, z, pitch) do tornozelo para a fase `p` (0..1) do pé: apoio linear para trás, balanço curvo."""
    if p < gait.duty:
        s = p / gait.duty
        y = gait.stride * (0.5 - s)
        pitch = 9.0 * (1.0 - smoothstep(s, 0.0, 0.25)) - 34.0 * smoothstep(s, 0.72, 1.0)
        return y, S.sole_rise(pitch), pitch
    q = (p - gait.duty) / (1.0 - gait.duty)
    y = gait.stride * (-0.5 + smoothstep(q))
    pitch = lerp(-34.0, 9.0, smoothstep(q))
    return y, gait.lift * irregular * math.sin(math.pi * q) ** 0.8 + S.sole_rise(pitch), pitch


def locomotion(pose, motion, name, weight):
    """Pernas, quadril e tronco de uma animação de marcha; `weight` (0..1) funde com o repouso."""
    gait = GAITS[name]
    t, phase = motion.time, motion.phase
    warp = 0.045 * math.sin(2 * math.pi * phase * 2.0 + 1.3) + 0.03 * math.sin(2 * math.pi * phase + 0.4)
    cycle = phase + warp
    irregular = 1.0 + 0.30 * wobble(t, 4.0, 1.1)
    if name == "walk":
        irregular += 0.25 * math.sin(2 * math.pi * cycle)        # um pé sobe mais que o outro

    drop = gait.hip_drop * weight + 0.035 * (1.0 - weight)
    bob = gait.bob * weight * (0.5 + 0.5 * math.cos(4 * math.pi * cycle))
    sway = gait.sway * weight * math.sin(2 * math.pi * cycle)
    pose.hips += Vector((sway, 0.0, -drop + bob))

    coat_front, coat_back = {}, {}
    for side, offset in (("R", 0.0), ("L", 0.5)):
        y, z, pitch = foot_cycle(gait, (cycle + offset) % 1.0, irregular)
        x = S.side_sign(side) * S.LEG_SPREAD * 1.12
        standing = (x, 0.0, 0.0, 0.0)
        moving = (x, y, z, pitch)
        pose.foot(side, *[lerp(a, b, weight) for a, b in zip(standing, moving)])
        coat_front[side] = 22.0 * weight * (y / gait.stride)
        coat_back[side] = -10.0 * weight * (y / gait.stride)
    run_wind = -30.0 * (gait.lean / 27.0) * weight if name == "run" else -6.0 * weight
    for side in ("L", "R"):
        coat_back[side] += run_wind + 5.0 * wobble(t, 8.0 + (side == "L"), 2.4)
        coat_front[side] += (-8.0 * weight if name == "run" else 0.0)
    coat_sway(pose, coat_front, coat_back)

    lean(pose, gait.lean * weight)
    return cycle


# --------------------------------------------------------------------------
# Animações
# --------------------------------------------------------------------------
def _shoulders(pose, droop, shrug=0.0):
    for side in ("L", "R"):
        pose.add(f"Shoulder.{side}", y=S.side_sign(side) * (droop - shrug))


def _idle_pose(pose, motion, t, stillness=0.0):
    """Base de pé, em repouso. `stillness` (0..1) congela a respiração e o balanço (usado em `stare`)."""
    live = 1.0 - stillness
    breath = math.sin(2 * math.pi * t / 4.6) * live
    pose.hips += Vector((0.0, 0.0, -0.035))
    pose.foot("R", S.LEG_SPREAD * 1.15, 0.02)
    pose.foot("L", -S.LEG_SPREAD * 1.15, -0.02)
    lean(pose, 4.0)
    pose.add("Spine2", x=0.8 * breath)
    pose.add("Spine3", x=0.9 * breath, y=1.2 * wobble(t, 1.0, 0.35) * live)
    _shoulders(pose, 5.0, 0.9 * breath)
    drift = 1.0 - motion.look_weight
    pose.add("Neck", x=-4.0, y=5.0)
    pose.add("Head", x=-5.0, y=8.0 + 2.5 * wobble(t, 2.0, 0.5) * live, z=7.0 * wobble(t, 3.0, 0.16) * live * drift)
    for side in ("L", "R"):
        arm(pose, side, pitch=1.5 + 1.0 * wobble(t, 5.0, 0.4) * live, abduct=3.5, elbow=7.0, wrist=3.0)
        pulse = 26.0 * smoothstep(math.sin(2 * math.pi * t / 7.3 + (side == "L") * 2.0), 0.85, 1.0) * live
        hand(pose, side, 14.0, 25.0 + pulse, spread=2.0, jitter=6.0 * live, t=t, seed=(side == "L") * 7.0)
    coat_sway(pose, {"L": 0.0, "R": 0.0}, {"L": 1.2 * breath, "R": 1.2 * breath})


def anim_idle(pose, motion):
    _idle_pose(pose, motion, motion.time)


def anim_stare(pose, motion):
    _idle_pose(pose, motion, motion.time, stillness=0.85)
    pose.add("Head", y=1.5)                      # a inclinação torta fica um pouco pior
    clench = smoothstep(math.sin(2 * math.pi * motion.time / 5.0), 0.95, 1.0)
    for side in ("L", "R"):
        hand(pose, side, 8.0 * clench, 14.0 * clench, thumb=0.0)


def _walk_arms(pose, motion, cycle, amplitude, elbow_base, elbow_swing, abduct, lag=0.10):
    t = motion.time
    for side, offset in (("R", 0.5), ("L", 0.0)):                 # braço oposto à perna
        swing = math.sin(2 * math.pi * (cycle + offset - lag))
        noise = wobble(t, 11.0 + (side == "L"), 1.7)
        arm(pose, side, pitch=amplitude * swing + 6.0 * noise, abduct=abduct + 5.0 * noise,
            elbow=elbow_base + elbow_swing * (0.5 + 0.5 * swing), wrist=10.0 * swing, twist=8.0 * noise)


def anim_walk(pose, motion):
    t = motion.time
    cycle = locomotion(pose, motion, "walk", motion.move_w)
    w = motion.move_w
    twist_torso(pose, 10.0 * math.sin(2 * math.pi * cycle) * w, 6.0 * math.sin(2 * math.pi * cycle + 0.8) * w)
    _shoulders(pose, 6.0, 2.0 * math.sin(2 * math.pi * cycle * 2))
    _walk_arms(pose, motion, cycle, amplitude=24.0 * w, elbow_base=14.0, elbow_swing=16.0, abduct=6.0)
    drift = 1.0 - motion.look_weight
    pose.add("Neck", x=-8.0, y=7.0 + 4.0 * math.sin(2 * math.pi * cycle * 2 + 1.0) * w)
    pose.add("Head", x=-4.0, y=10.0 + 5.0 * wobble(t, 6.0, 1.4), z=(10.0 * wobble(t, 12.0, 0.5) - 8.0 * math.sin(2 * math.pi * cycle) * w) * drift)
    for side in ("L", "R"):
        hand(pose, side, 18.0, 30.0, spread=3.0, jitter=9.0, t=t, seed=(side == "L") * 5.0)


def anim_run(pose, motion):
    t = motion.time
    w = motion.move_w
    cycle = locomotion(pose, motion, "run", w)
    flail = 1.0 + 0.35 * wobble(t, 21.0, 2.2)
    twist_torso(pose, 16.0 * math.sin(2 * math.pi * cycle) * w, 9.0 * math.sin(2 * math.pi * cycle + 0.6) * w)
    _shoulders(pose, 4.0, 4.0 * math.sin(2 * math.pi * cycle * 2))
    for side, offset in (("R", 0.5), ("L", 0.0)):
        swing = math.sin(2 * math.pi * (cycle + offset - 0.12))
        noise = wobble(t, 31.0 + (side == "L"), 2.9)
        arm(pose, side, pitch=(58.0 * swing + 8.0) * w * flail, abduct=14.0 + 18.0 * noise,
            elbow=55.0 + 40.0 * (0.5 + 0.5 * swing) + 12.0 * noise, wrist=25.0 * swing, twist=14.0 * noise)
        hand(pose, side, 6.0, 10.0, spread=10.0, jitter=14.0, t=t, seed=(side == "L") * 4.0)
    drift = 1.0 - motion.look_weight
    pose.add("Neck", x=-16.0, y=12.0 * wobble(t, 41.0, 2.0))
    pose.add("Head", x=12.0, y=14.0 * wobble(t, 42.0, 1.6), z=12.0 * wobble(t, 43.0, 1.1) * drift)


def anim_stalk(pose, motion):
    t = motion.time
    w = motion.move_w
    cycle = locomotion(pose, motion, "stalk", w)
    twist_torso(pose, 5.0 * math.sin(2 * math.pi * cycle) * w, 3.0 * math.sin(2 * math.pi * cycle) * w)
    _shoulders(pose, 8.0)
    for side, offset in (("R", 0.5), ("L", 0.0)):
        swing = math.sin(2 * math.pi * (cycle + offset - 0.1))
        arm(pose, side, pitch=10.0 + 7.0 * swing * w, abduct=12.0, elbow=28.0, wrist=8.0)
        hand(pose, side, 32.0, 48.0, spread=2.0, jitter=8.0, t=t, seed=(side == "L") * 6.0)
    drift = 1.0 - motion.look_weight
    pose.add("Neck", x=-26.0, y=8.0)
    pose.add("Head", x=14.0, y=10.0 + 4.0 * wobble(t, 51.0, 0.8), z=14.0 * math.sin(t * 0.7) * drift)


def anim_attack(pose, motion):
    u = motion.clock
    windup, strike = smoothstep(u, 0.0, 0.20), smoothstep(u, 0.20, 0.42)
    reach = strike
    tremor = math.sin(u * 2 * math.pi * 13.0) * smoothstep(u, 0.5, 0.8)
    pose.hips += Vector((0.0, 0.10 * reach - 0.06 * windup * (1 - strike), -0.34 * reach - 0.05 * windup))
    pose.foot("R", S.LEG_SPREAD * 1.6, 0.32 * reach + 0.02)
    pose.foot("L", -S.LEG_SPREAD * 1.6, -0.24 * reach)
    lean(pose, 4.0 - 10.0 * windup * (1 - strike) + 46.0 * reach)
    twist_torso(pose, 0.0, 6.0 * math.sin(u * 5.0) * reach)
    _shoulders(pose, 4.0, 6.0 * reach)
    for side in ("L", "R"):
        sx = S.side_sign(side)
        arm(pose, side, pitch=-38.0 * windup * (1 - strike) + 112.0 * reach + 2.5 * tremor,
            abduct=4.0 - 4.0 * reach, elbow=6.0 * reach + 2.0 * tremor, wrist=-10.0 * reach, twist=sx * 9.0 * reach)
        hand(pose, side, 24.0 * (1 - reach) - 6.0 * reach + 6.0 * tremor, 40.0 * (1 - reach) - 10.0 * reach,
             spread=14.0 * reach, thumb=-10.0 * reach)
    pose.add("Neck", x=-6.0 - 10.0 * reach, y=6.0)
    pose.add("Head", x=6.0 + 12.0 * reach, y=6.0 * (1 - reach))
    coat_sway(pose, {"L": 12.0 * reach, "R": 12.0 * reach}, {"L": -14.0 * reach, "R": -14.0 * reach})


def anim_twitch(pose, motion):
    t = motion.time
    _idle_pose(pose, motion, t, stillness=1.0)
    pose.hips += Vector((0.05 * spasm(t, 61.0, 7.0), 0.0, -0.03 - 0.05 * abs(spasm(t, 62.0, 9.0))))
    pose.add("Head", x=22.0 * spasm(t, 63.0, 11.0, 7.0, 0.7), y=30.0 * spasm(t, 64.0, 9.0, 6.0, 0.7),
             z=48.0 * spasm(t, 65.0, 8.0, 5.0, 0.7))
    pose.add("Neck", x=16.0 * spasm(t, 66.0, 10.0, 8.0), y=14.0 * spasm(t, 67.0, 12.0), z=22.0 * spasm(t, 68.0, 7.0))
    twist_torso(pose, 22.0 * spasm(t, 69.0, 8.0, 5.0, 0.7), 14.0 * spasm(t, 70.0, 9.0))
    lean(pose, 10.0 * abs(spasm(t, 71.0, 6.0)))
    for side in ("L", "R"):
        seed = 80.0 + (side == "L") * 9.0
        arm(pose, side, pitch=38.0 * spasm(t, seed, 9.0, 6.0, 0.7), abduct=24.0 * abs(spasm(t, seed + 1, 8.0)),
            elbow=55.0 * abs(spasm(t, seed + 2, 10.0)), twist=40.0 * spasm(t, seed + 3, 7.0))
        hand(pose, side, 12.0 + 50.0 * abs(spasm(t, seed + 4, 12.0, 6.0)), 20.0 + 60.0 * abs(spasm(t, seed + 4, 12.0, 6.0)),
             spread=16.0 * abs(spasm(t, seed + 5, 9.0)))
    _shoulders(pose, 5.0, 12.0 * abs(spasm(t, 90.0, 8.0)))
    pose.add("Head", y=1.5 * math.sin(t * 2 * math.pi * 19.0))     # tremor de fundo


def _crooked(pose, k):
    """Postura torta e dobrada da chegada; `k` vai de 1 (torto) a 0 (ereto)."""
    pose.hips += Vector((0.0, 0.10 * k, -0.62 * k))
    pose.foot("R", S.LEG_SPREAD * 1.15 + 0.14 * k, 0.40 * k)
    pose.foot("L", -S.LEG_SPREAD * 1.15 - 0.10 * k, -0.32 * k)
    lean(pose, 58.0 * k)
    pose.add("Spine1", y=-26.0 * k, z=18.0 * k)
    pose.add("Spine2", y=34.0 * k, z=-22.0 * k)
    pose.add("Spine3", y=-14.0 * k)
    pose.add("Neck", x=-30.0 * k, y=40.0 * k)
    pose.add("Head", x=26.0 * k, y=-38.0 * k, z=24.0 * k)
    _shoulders(pose, 0.0, 16.0 * k)
    arm(pose, "R", pitch=118.0 * k, abduct=30.0 * k, elbow=105.0 * k, twist=-40.0 * k)
    arm(pose, "L", pitch=-46.0 * k, abduct=10.0 * k, elbow=20.0 * k)
    for side in ("L", "R"):
        hand(pose, side, 55.0 * k, 75.0 * k, spread=4.0 * k)


def anim_appear(pose, motion):
    stepped = math.floor(motion.clock * APPEAR_FPS) / APPEAR_FPS
    progress = clamp(stepped / APPEAR_DURATION, 0.0, 1.0)
    k = 1.0 - smoothstep(progress)
    _idle_pose(pose, motion, motion.time, stillness=0.6 * k)
    _crooked(pose, k)


BUILDERS = {
    "idle": anim_idle, "stare": anim_stare, "walk": anim_walk, "run": anim_run,
    "stalk": anim_stalk, "attack": anim_attack, "twitch": anim_twitch, "appear": anim_appear,
}


# --------------------------------------------------------------------------
# Pose de morte: a entidade agarra o rosto do jogador
# --------------------------------------------------------------------------
FACE_DISTANCE = 0.42        # da cabeça da entidade aos olhos do jogador (m)
GRAB_LEAN = 52.0


def _grab_spec(eye_z, drop):
    pose = Pose()
    pose.hips += Vector((0.0, 0.12, -drop))
    pose.foot("R", S.LEG_SPREAD * 1.5, 0.12)
    pose.foot("L", -S.LEG_SPREAD * 1.5, -0.08)
    lean(pose, GRAB_LEAN)
    pose.add("Neck", x=-18.0, y=6.0)
    pose.add("Head", x=GRAB_LEAN + 8.0, y=-10.0)
    _shoulders(pose, 2.0, 12.0)
    return pose


def grab_solution(eye_z):
    """Pose de agarrar: devolve (Solution, y da cabeça). A entidade se abaixa até o rosto ficar na altura dos olhos."""
    low, high = 0.0, 0.85
    for _ in range(24):
        mid = (low + high) / 2
        solution = S.solve(_grab_spec(eye_z, mid).to_spec())
        if solution.midpoint("Head").z > eye_z + 0.01:
            low = mid
        else:
            high = mid
    drop = (low + high) / 2
    pose = _grab_spec(eye_z, drop)
    face_y = S.solve(pose.to_spec()).midpoint("Head").y
    distance = face_y + FACE_DISTANCE
    for side in ("L", "R"):
        sx = S.side_sign(side)
        pose.goals[f"UpperArm.{side}"] = S.IKGoal(
            Vector((sx * 0.34, distance - 0.16, eye_z - 0.10)), Vector((sx * 0.8, -0.3, -0.6)))
        hand(pose, side, -6.0, -10.0, spread=16.0, thumb=-12.0)
    return S.solve(pose.to_spec()), distance


# --------------------------------------------------------------------------
# Controlador de animação
# --------------------------------------------------------------------------
class Motion:
    """Relógio, fase da passada, transições e olhar. Não conhece a cena do Blender."""

    def __init__(self):
        self.anim = "idle"
        self.time = 0.0                 # relógio global (ruído contínuo)
        self.clock = 0.0                # tempo desde `set_anim`
        self.phase = 0.0
        self.move_w = 0.0
        self.look_yaw = self.look_pitch = self.look_weight = 0.0
        self.head_limit = INDOOR_HEAD_LIMIT      # None: ereto, com os 2,65 m inteiros (estrada, no final)
        self._from = None
        self._blend_t = self._blend_dur = 0.0
        self.last = self._pose_for("idle")

    def set_anim(self, name):
        if name not in BUILDERS:
            raise ValueError(f"animação desconhecida: {name!r}; use uma de {ANIMATIONS}")
        if name == self.anim:
            return
        self._from = (self.last.local, self.last.hips_shift.copy())
        self._blend_dur = BLEND_SECONDS.get(name, DEFAULT_BLEND)
        self._blend_t = 0.0
        self.anim = name
        self.clock = 0.0

    def nominal_speed(self):
        return GAITS[self.anim].nominal_speed if self.anim in GAITS else 0.0

    def _pose_for(self, name):
        pose = Pose()
        BUILDERS[name](pose, self)
        apply_look(pose, self.look_yaw, self.look_pitch, self.look_weight)
        solution = S.solve(pose.to_spec())
        if self.head_limit is not None:
            solution = self._stoop(pose, solution)
        return solution

    def _stoop(self, pose, solution):
        """Se a cabeça passaria do forro, curva o tronco e dobra os joelhos até caber."""
        excess = solution.tail("Head").z - self.head_limit
        if excess <= 0.0:
            return solution
        lean(pose, min(28.0, 75.0 * excess))
        pose.hips.z -= 0.3 * excess
        solution = S.solve(pose.to_spec())
        excess = solution.tail("Head").z - self.head_limit
        if excess > 0.0:
            pose.hips.z -= excess
            solution = S.solve(pose.to_spec())
        return solution

    def update(self, dt, speed=None):
        self.time += dt
        self.clock += dt
        if self.anim in GAITS:
            gait_speed = GAITS[self.anim].nominal_speed if speed is None else speed
            moving = 1.0 if gait_speed > 0.05 else 0.0
            self.move_w += clamp(moving - self.move_w, -6.0 * dt, 6.0 * dt)
            if moving:
                self.phase = (self.phase + cadence(self.anim, gait_speed) * dt) % 1.0
        else:
            self.move_w += clamp(0.0 - self.move_w, -6.0 * dt, 6.0 * dt)

        solution = self._pose_for(self.anim)
        if self._from is not None:
            self._blend_t += dt
            weight = 1.0 if self._blend_dur <= 0 else smoothstep(self._blend_t / self._blend_dur)
            if weight < 1.0:
                local = S.blend_local(self._from[0], solution.local, weight)
                hips = self._from[1].lerp(solution.hips_shift, weight)
                solution = S.forward(local, hips)
            else:
                self._from = None
        solution = self._ground_clamp(solution)
        self.last = solution
        return solution

    @staticmethod
    def _ground_clamp(solution):
        """Se algum pé afundou no chão (mistura de poses), sobe o quadril o suficiente."""
        lowest = min(S.sole_height(solution, f) for f in S.foot_bones())
        if lowest >= -1e-4:
            return solution
        hips = solution.hips_shift + Vector((0.0, 0.0, -lowest))
        return S.forward(solution.local, hips)
