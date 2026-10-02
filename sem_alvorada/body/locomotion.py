"""Locomoção do corpo: pernas sincronizadas com a passada do jogador, tronco, agachar, correr e respirar.

Matemática pura (mathutils): recebe números do `Player` e devolve uma `PoseSpec` do solver. O corpo
nunca decide para onde anda; segue a câmera. A base do pescoço é presa a um ponto logo atrás e abaixo
dos olhos, e o quadril se desloca para que isso aconteça: agachar, inclinar e olhar para baixo saem
daí sem fórmulas separadas para a altura do quadril.
"""
import math
from dataclasses import dataclass

from mathutils import Matrix, Quaternion, Vector

from . import skeleton as S
from .solver import LegGoal, PoseSpec

AXIS_X, AXIS_Z = Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0))
ROOT_BACK = S.EYE_FROM_C7.y            # a raiz dos pés fica atrás do olho; assim o quadril cai sob a coluna
STAND_EYE, CROUCH_EYE = 1.65, 1.05     # C.PLAYER_EYE_STAND / C.PLAYER_EYE_CROUCH
PITCH_NECK_SHARE = 0.55                # fatia da inclinação do olhar que o pescoço absorve (o resto é do tronco)
MAX_LAG = math.radians(68.0)           # quanto o corpo pode ficar para trás da câmera, em guinada
TOE_OUT = math.radians(5.0)
SOLE_BACK, BALL_FRONT = -0.065, 0.13   # calcanhar e bola do pé em relação ao tornozelo (m)


@dataclass(frozen=True)
class Gait:
    reach: float        # distância total que o pé percorre no apoio (m)
    duty: float         # fração do ciclo com o pé no chão
    lift: float         # altura máxima do pé no balanço (m)
    lean: float         # inclinação do tronco para a frente (graus)
    swing: float        # balanço do braço solto (graus)
    elbow: float        # flexão do cotovelo no balanço (graus)


GAITS = {
    "walk": Gait(reach=0.92, duty=0.50, lift=0.12, lean=3.0, swing=15.0, elbow=14.0),
    "run": Gait(reach=1.12, duty=0.40, lift=0.26, lean=13.0, swing=36.0, elbow=72.0),
    "crouch": Gait(reach=0.58, duty=0.58, lift=0.07, lean=0.0, swing=6.0, elbow=10.0),
}


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def wrap(angle):
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def sole_rise(pitch):
    """Quanto o tornozelo sobe para a sola (do calcanhar à bola do pé), inclinada `pitch`, não entrar no chão."""
    s, c = math.sin(pitch), math.cos(pitch)
    lowest = min(SOLE_BACK * s - S.ANKLE_Z * c, BALL_FRONT * s - S.ANKLE_Z * c)
    return max(0.0, -lowest - S.ANKLE_Z)


def foot_cycle(gait, p):
    """(avanço, altura, inclinação) do pé na fase p (0..1): apoio linear para trás, balanço curvo para a frente."""
    if p < gait.duty:
        s = p / gait.duty
        along = gait.reach * (0.5 - s)
        pitch = math.radians(11.0) * (1.0 - smoothstep(s / 0.22)) - math.radians(32.0) * smoothstep((s - 0.70) / 0.30)
        return along, sole_rise(pitch), pitch
    q = (p - gait.duty) / (1.0 - gait.duty)
    along = gait.reach * (-0.5 + smoothstep(q))
    pitch = -math.radians(32.0) * (1.0 - smoothstep(q / 0.6)) + math.radians(11.0) * smoothstep((q - 0.5) / 0.5)
    return along, gait.lift * math.sin(math.pi * q) ** 0.8 + sole_rise(pitch), pitch


def lerp(a, b, t):
    return a + (b - a) * t


class Frame:
    """Resultado de um quadro de locomoção: onde está a raiz e a pose do corpo sem os braços com alvo."""
    __slots__ = ("root", "yaw", "cam_pos", "cam_basis", "spec", "chest_scale", "phase_cycle", "gait", "body_from_world")


class Locomotion:
    def __init__(self):
        self.reset()

    def reset(self):
        self.body_yaw = None
        self.gain = 0.0
        self.crouch = 0.0
        self.last_pos = None
        self.velocity = Vector((0.0, 0.0))
        self.direction = Vector((0.0, 1.0))
        self.params = dict(reach=GAITS["walk"].reach, duty=GAITS["walk"].duty, lift=GAITS["walk"].lift,
                           lean=GAITS["walk"].lean, swing=GAITS["walk"].swing, elbow=GAITS["walk"].elbow)
        self.clock = 0.0
        self.breath = 0.0
        self.last_phase = 0.0
        self.stair_z = 0.0

    # ------------------------------------------------------------------
    def step(self, dt, player, bob, ground=None):
        """Um quadro. `ground(x, y)` opcional devolve a altura do piso (escadas)."""
        self.clock += dt
        position, euler = player.camera_pose()
        cam_pos = Vector(position)
        cam_basis = Matrix.Rotation(euler[2], 3, "Z") @ Matrix.Rotation(euler[1], 3, "Y") @ Matrix.Rotation(euler[0], 3, "X")
        cam_yaw, pitch = player.yaw, player.pitch
        speed = player.speed

        if self.body_yaw is None:
            self.body_yaw = cam_yaw
        self._follow_yaw(dt, cam_yaw)
        lag = wrap(cam_yaw - self.body_yaw)

        here = Vector((player.x, player.y))
        if self.last_pos is not None and dt > 1e-6:
            self.velocity = (here - self.last_pos) / dt
        self.last_pos = here

        target_gain = max(0.0, min(1.0, speed / 0.45))
        self.gain += (target_gain - self.gain) * (1.0 - math.exp(-10.0 * dt))
        self.crouch += (max(0.0, min(1.0, (STAND_EYE - player.eye) / (STAND_EYE - CROUCH_EYE))) - self.crouch) * (1.0 - math.exp(-14.0 * dt))
        mode = "crouch" if player.crouching else ("run" if player.running and speed > 3.0 else "walk")
        gait = GAITS[mode]
        for key in self.params:
            self.params[key] += (getattr(gait, key) - self.params[key]) * (1.0 - math.exp(-7.0 * dt))

        forward = Vector((-math.sin(self.body_yaw), math.cos(self.body_yaw)))
        root_xy = here - forward * ROOT_BACK
        root = Vector((root_xy.x, root_xy.y, player.z_visual))
        body_from_world = Matrix.Rotation(-self.body_yaw, 3, "Z")

        self._update_direction()
        spec = PoseSpec()
        rot = spec.rot
        lean = self._lean(pitch)
        self._spine(rot, lean, lag, pitch, speed)
        cam_body = body_from_world @ (cam_pos - root)
        eye_offset = Matrix.Rotation(lag, 3, "Z") @ Matrix.Rotation(pitch * PITCH_NECK_SHARE, 3, "X") @ S.EYE_FROM_C7
        neck_target = cam_body - eye_offset
        spec.hips_shift = neck_target - _neck_base(rot)

        phase = player.stride_phase
        cycle = phase / (2.0 * math.pi)
        self._legs(spec, cycle, ground, root)
        self._arms_fk(rot, cycle, speed)

        frame = Frame()
        frame.root, frame.yaw = root, self.body_yaw
        frame.cam_pos, frame.cam_basis = cam_pos, cam_basis
        frame.spec = spec
        frame.chest_scale = self._breath(dt, player)
        frame.phase_cycle = cycle
        frame.gait = mode
        return frame

    # ------------------------------------------------------------------
    def _follow_yaw(self, dt, cam_yaw):
        diff = wrap(cam_yaw - self.body_yaw)
        rate = 6.5 + 9.0 * self.gain
        self.body_yaw += diff * (1.0 - math.exp(-rate * dt))
        diff = wrap(cam_yaw - self.body_yaw)
        if abs(diff) > MAX_LAG:
            self.body_yaw = cam_yaw - math.copysign(MAX_LAG, diff)

    def _update_direction(self):
        """Direção do movimento no espaço do corpo (X direita, Y frente); mantém a última se parado."""
        if self.velocity.length < 0.25:
            return
        c, s = math.cos(self.body_yaw), math.sin(self.body_yaw)
        vx, vy = self.velocity.x, self.velocity.y
        local = Vector((c * vx + s * vy, -s * vx + c * vy)).normalized()
        self.direction = self.direction.lerp(local, 0.35).normalized() if self.direction.length > 1e-6 else local

    def _lean(self, pitch):
        down = max(0.0, -math.degrees(pitch))
        up = max(0.0, math.degrees(pitch))
        return (self.params["lean"] * self.gain + 40.0 * self.crouch + down * 0.26 * (1.0 - PITCH_NECK_SHARE) * 1.6
                - up * 0.08)

    def _spine(self, rot, lean, lag, pitch, speed):
        shares = (("Hips", 0.10), ("Spine1", 0.28), ("Spine2", 0.32), ("Spine3", 0.30))
        for name, share in shares:
            rot[name] = Quaternion(AXIS_X, -math.radians(lean * share))
        twist = lag * 0.55
        for name, share in (("Spine1", 0.25), ("Spine2", 0.35), ("Spine3", 0.40)):
            rot[name] = Quaternion(AXIS_Z, twist * share) @ rot[name]
        breath = math.sin(self.clock * 1.5) * 0.35
        rot["Spine2"] = Quaternion(AXIS_X, math.radians(breath)) @ rot["Spine2"]
        rot["Neck"] = Quaternion(AXIS_X, math.radians(lean * 0.45))

    def _legs(self, spec, cycle, ground, root):
        p = self.params
        gait = Gait(p["reach"], p["duty"], p["lift"], p["lean"], p["swing"], p["elbow"])
        direction = self.direction
        reach_scale = 0.62 + 0.38 * abs(direction.y)
        for side, offset in (("L", 0.0), ("R", 0.5)):
            sx = S.side_sign(side)
            along, lift, pitch = foot_cycle(gait, (cycle + offset) % 1.0)
            along *= reach_scale * self.gain
            lift *= self.gain
            pitch *= self.gain
            neutral_rise = sole_rise(0.0)
            x = sx * S.LEG_X + direction.x * along
            y = direction.y * along
            z = S.ANKLE_Z + lift + neutral_rise * (1.0 - self.gain)
            if ground is not None:
                z += ground(x, y, root, side)
            foot_q = Quaternion(AXIS_Z, -sx * TOE_OUT) @ Quaternion(AXIS_X, pitch)
            pole = Vector((sx * 0.12, 1.0, 0.0))
            spec.legs[side] = LegGoal(Vector((x, y, z)), foot_q, pole)
            spec.rot[f"Toe.{side}"] = Quaternion(AXIS_X, max(0.0, -pitch) * 0.85)

    def _arms_fk(self, rot, cycle, speed):
        """Braço solto: balanço oposto à perna do mesmo lado, mais leve em pé; cotovelos dobram ao correr."""
        p = self.params
        swing, elbow = p["swing"] * self.gain, p["elbow"] * self.gain
        for side, offset in (("L", 0.5), ("R", 0.0)):
            sx = S.side_sign(side)
            wave = math.sin(2.0 * math.pi * (cycle + offset))
            sway = 1.2 * math.sin(self.clock * 0.9 + (0.0 if side == "L" else 1.7)) * (1.0 - self.gain)
            forward = swing * wave + sway
            bend = elbow * (0.45 + 0.55 * max(0.0, wave)) + 9.0 * (1.0 - self.gain)
            rot[f"UpperArm.{side}"] = Quaternion(AXIS_X, math.radians(forward))
            rot[f"Forearm.{side}"] = Quaternion(AXIS_X, math.radians(bend))

    def _breath(self, dt, player):
        hard = getattr(player, "breathing_hard", False)
        rate = 2.4 if hard else 1.5
        amplitude = 0.022 if hard else 0.010
        self.breath += dt * rate * 2.0 * math.pi
        wave = math.sin(self.breath)
        return (1.0 + amplitude * 0.6 * wave, 1.0 + amplitude * wave, 1.0 + amplitude * 0.8 * wave)


def _neck_base(rot):
    """Posição da base do pescoço no espaço do corpo para as rotações de coluna `rot`, com o quadril na origem."""
    world = S.IDENTITY
    head = S.BONE_MAP["Hips"].head.copy()
    previous = S.BONE_MAP["Hips"].head
    for name in ("Hips", "Spine1", "Spine2", "Spine3"):
        bone = S.BONE_MAP[name]
        if name != "Hips":
            head = head + world @ (bone.head - previous)
        world = world @ rot.get(name, S.IDENTITY)
        previous = bone.head
    neck = S.BONE_MAP["Neck"]
    return head + world @ (neck.head - previous)
