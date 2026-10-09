"""O corpo do Daniel nas cutscenes: deitado, sentado, de pé, dirigindo, andando atrás da câmera, e as mãos no quadro.

`BodyDriver` escolhe, a cada instante, entre posar o corpo num ponto fixo (cama, assento do carro) e deixá-lo
seguir a câmera como no jogo (pernas andando no ritmo da câmera). `HandActor` leva uma mão por pontos que podem
estar no mundo ou no espaço do carro; a cada quadro eles viram o espaço da câmera, que é o que `ArmControl` pede.

Sem corpo (NullBody, ou o jogo sem a etapa `body`) tudo isto não faz nada, e nunca derruba a cutscene.
"""
import math
from dataclasses import dataclass

from . import camera
from .curves import Curve, Key, Path, clamp, clamp01
from .stage import Actor

# Onde ficam os olhos em cada pose, relativos ao `place(x, y, z, yaw)` (eixos do corpo: +Y para onde ele olha).
# Vêm de `body.solver` sobre `body.poses`; um teste (test_cutscenes_build) confere que ainda batem.
EYE_LOCAL = {"stand": (0.0, 0.075, 1.65), "sit_bed": (0.0, 0.131, 0.782), "lying_bed": (0.0, -0.700, 0.184),
             "driving": (0.0, 0.130, 0.778)}
STEP_LENGTH = 0.69                 # m por passo: cada pi de `stride_phase` é um passo, como no Player
PLAYER_EYE = 1.65


def root_for(pose, eye, yaw):
    """Ponto de `body.place` que leva os olhos da pose `pose` até `eye` quando o corpo olha para `yaw` (radianos)."""
    ex, ey, ez = EYE_LOCAL[pose]
    c, s = math.cos(yaw), math.sin(yaw)
    return (eye[0] - (c * ex - s * ey), eye[1] - (s * ex + c * ey), eye[2] - ez)


@dataclass(frozen=True)
class BodyPose:
    """A partir de `t`, o corpo faz a pose `pose` (transição de `seconds`), com a raiz em `root` e olhando para `yaw`.

    `root`: ponto, `Path` (tempos absolutos) ou função do palco; `yaw`: radianos ou `Curve` (tempos absolutos).
    Com `mount`, ambos estão no espaço desse objeto (o carro) e o corpo anda com ele."""
    t: float
    pose: str
    seconds: float = 0.0
    root: object = (0.0, 0.0, 0.0)
    yaw: object = 0.0
    mount: str = ""


@dataclass(frozen=True)
class BodyFollow:
    """A partir de `t`, o corpo segue a câmera como segue o jogador (pernas andando, tronco acompanhando o olhar)."""
    t: float


class _CameraAsPlayer:
    """O que `Locomotion.step` lê do jogador, montado a partir da câmera da cutscene."""
    crouching = False
    running = False
    eye = PLAYER_EYE

    def __init__(self, position, yaw, pitch, roll, speed, stride_phase):
        self.x, self.y = position[0], position[1]
        self.z_visual = position[2] - PLAYER_EYE
        self.yaw, self.pitch, self.speed, self.stride_phase = yaw, pitch, speed, stride_phase
        self._pose = (position, (math.pi / 2 + pitch, roll, yaw))

    def camera_pose(self):
        return self._pose


class BodyDriver(Actor):
    late = True                        # roda depois que a câmera do quadro foi posicionada

    def __init__(self, segments, camera_name="CutsceneCam"):
        self.segments = sorted(segments, key=lambda s: s.t)
        self.camera_name = camera_name
        self._current = None
        self._camera_obj = None
        self._last_xy = None
        self._speed = 0.0
        self._phase = 0.0
        self._last_place = None

    def start(self, stage):
        self._camera_obj = stage.obj(self.camera_name)

    def _segment(self, t):
        current = None
        for segment in self.segments:
            if segment.t <= t + 1e-9:
                current = segment
        return current

    def _enter(self, stage, segment):
        first = self._current is None
        previous = self._current
        self._current = segment
        if isinstance(segment, BodyFollow) or first:
            stage.body_call("reset")
            stage.body_call("attach_view", self._camera_obj)
            self._last_xy, self._speed, self._phase = None, 0.0, 0.0
        if isinstance(segment, BodyPose):
            stage.body_call("pose", segment.pose, segment.seconds)
            self._last_place = None
        elif isinstance(previous, BodyPose):
            self._last_place = None

    def update(self, stage, dt):
        if stage.body is None:
            return
        segment = self._segment(stage.t)
        if segment is None:
            return
        if segment is not self._current:
            self._enter(stage, segment)
        if isinstance(segment, BodyFollow):
            self._follow(stage, dt)
        else:
            self._placed(stage, segment, dt)

    def stop(self, stage):
        """Devolve o corpo ao jogo: de pé, seguindo o jogador (senão ele ficaria na pose da cutscene)."""
        if self._current is not None:
            stage.body_call("reset")
        self._current = None

    # ---- pose fixa
    def _placed(self, stage, segment, dt):
        t = stage.t
        root = segment.root
        if isinstance(root, Path):
            root = root.at(clamp(t, root.times[0], root.times[-1]), stage)
        elif callable(root):
            root = root(stage)
        yaw = segment.yaw
        if isinstance(yaw, Curve):
            yaw = yaw(t)
        elif callable(yaw):
            yaw = yaw(stage)
        if segment.mount:
            root = stage.to_world(segment.mount, root)
            yaw += stage.poses[segment.mount][1][2]
        placement = (*root, yaw)
        if self._last_place is None or max(abs(a - b) for a, b in zip(placement, self._last_place)) > 1e-5:
            stage.body_call("place", *placement)
            self._last_place = placement
        stage.body_call("update", dt, None)

    # ---- o corpo como se fosse o jogador
    def _follow(self, stage, dt):
        pose = getattr(stage, "camera_pose", None)
        if pose is None:
            return
        position, q = pose
        forward = camera.rotate(q, (0.0, 0.0, -1.0))
        yaw, pitch = math.atan2(-forward[0], forward[1]), math.asin(clamp(forward[2], -1.0, 1.0))
        up = camera.rotate(q, (0.0, 1.0, 0.0))
        roll = 0.0 if abs(forward[2]) > 0.98 else math.atan2(up[0] * math.cos(yaw) + up[1] * math.sin(yaw), up[2])
        if self._last_xy is not None and dt > 1e-6:
            distance = math.hypot(position[0] - self._last_xy[0], position[1] - self._last_xy[1])
            target = distance / dt
            self._speed += (target - self._speed) * (1.0 - math.exp(-12.0 * dt))
            self._phase += math.pi * distance / STEP_LENGTH
        self._last_xy = (position[0], position[1])
        proxy = _CameraAsPlayer(position, yaw, pitch, roll, self._speed, self._phase)
        stage.body_call("update", dt, proxy, (0.0, 0.0))


@dataclass(frozen=True)
class HandKey:
    """Uma chave da mão. `pos` no `space` do HandActor; `fingers` e `palm` são direções no mesmo espaço (opcionais:
    sem elas vale `rot`, o Euler em graus do espaço da câmera de `ArmControl.set_target`)."""
    t: float
    pos: tuple
    fingers: tuple | None = None
    palm: tuple | None = None
    rot: tuple = (0.0, 0.0, 0.0)
    weight: float = 1.0
    grip: object = "relaxed"           # nome de preset de `body.fingers.PRESETS` ou (curls, spread)


def _grip_values(grip):
    if isinstance(grip, str):
        try:
            from ..body import fingers
            return fingers.PRESETS[grip]
        except Exception:                                   # noqa: BLE001 - sem o módulo do corpo, dedos meio fechados
            return ((0.3,) * 5, 0.0)
    return grip


class HandActor(Actor):
    """Leva a mão `side` pelas chaves e a solta depois da última. Atua só entre a primeira e a última chave.

    `space`: "camera" (X direita, Y cima, -Z frente), "world" ou o nome de um carregador ("Car").
    """
    late = True

    def __init__(self, side, keys, space="camera", fade=0.35):
        keys = sorted(keys, key=lambda k: k.t)
        self.side, self.space, self.fade = side, space, fade
        self.t0, self.t1 = keys[0].t, keys[-1].t
        self.pos = Path([Key(k.t, k.pos) for k in keys], rest_ends=True)
        self.weight = Curve([(k.t, k.weight) for k in keys])
        self.has_aim = all(k.fingers is not None and k.palm is not None for k in keys)
        if self.has_aim:
            self.fingers = Path([Key(k.t, k.fingers) for k in keys], rest_ends=False)
            self.palm = Path([Key(k.t, k.palm) for k in keys], rest_ends=False)
        else:
            self.rot = Path([Key(k.t, k.rot) for k in keys], rest_ends=False)
        grips = [_grip_values(k.grip) for k in keys]
        self.curls = [Curve([(k.t, g[0][i]) for k, g in zip(keys, grips)]) for i in range(5)]
        self.spread = Curve([(k.t, g[1]) for k, g in zip(keys, grips)])
        self._released = True

    def start(self, stage):
        self._released = True

    # ---- espaços
    def _camera_point(self, stage, point):
        if self.space == "camera":
            return point
        world = point if self.space == "world" else stage.to_world(self.space, point)
        position, q = stage.camera_pose
        return camera.rotate((q[0], -q[1], -q[2], -q[3]), tuple(world[i] - position[i] for i in range(3)))

    def _camera_vector(self, stage, vector):
        if self.space == "camera":
            return vector
        world = vector if self.space == "world" else camera.rotate(stage.mount_quaternion(self.space), vector)
        q = stage.camera_pose[1]
        return camera.rotate((q[0], -q[1], -q[2], -q[3]), world)

    def update(self, stage, dt):
        t = stage.t
        arm = stage.arm(self.side)
        if arm is None or getattr(stage, "camera_pose", None) is None:
            return
        if t < self.t0 or t > self.t1 + self.fade:
            if not self._released:
                stage.safe("arm.release", arm.release, 1.0)
                self._released = True
            return
        tt = clamp(t, self.t0, self.t1)
        weight = clamp01(self.weight(tt))
        if t > self.t1:
            weight *= clamp01(1.0 - (t - self.t1) / self.fade)
        position = self._camera_point(stage, self.pos.at(tt))
        if self.has_aim:
            rotation = self._rotation(stage, self._camera_vector(stage, self.fingers.at(tt)),
                                      self._camera_vector(stage, self.palm.at(tt)))
        else:
            rotation = self.rot.at(tt)
        stage.safe("arm.set_target", arm.set_target, position, rotation, weight)
        stage.safe("arm.set_fingers", arm.set_fingers, [clamp01(c(tt)) for c in self.curls], self.spread(tt), 0.35)
        self._released = False

    @staticmethod
    def _rotation(stage, fingers, palm):
        try:
            from ..body.handframe import hand_rotation
            return hand_rotation(fingers, palm)
        except Exception:                                   # noqa: BLE001
            return (0.0, 0.0, 0.0)

    def stop(self, stage):
        arm = stage.arm(self.side)
        if arm is not None and not self._released:
            stage.safe("arm.release", arm.release, 1.0)
