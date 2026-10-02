"""Palco: a ponte entre as ações das cutscenes e o anfitrião (`host`) do engine.

Toda chamada ao host passa por aqui. Erros em chamadas cosméticas (um som que falta, um objeto que
não existe) são registrados em `errors` e NÃO derrubam a cutscene: o jogo continua e o teste pega.

O palco também lembra tudo o que a cutscene mexeu (transformações, visibilidade, luzes, braços do corpo,
atores) para devolver no fim, tanto no fim normal quanto num `skip`.
"""
import math
from dataclasses import dataclass

from .. import conventions as C
from . import camera

# Objetos que só existem para cutscenes (criados por `cutscenes.build`)
HEADLIGHT_ENERGY = 3500.0
EXPECTED_EYE = C.PLAYER_EYE_STAND


@dataclass(frozen=True)
class PlayerSnapshot:
    """Onde o jogador estava quando a cutscene começou."""
    x: float
    y: float
    z: float
    yaw: float
    eye_z: float
    pitch: float = 0.0

    @property
    def eye(self):
        return (self.x, self.y, self.eye_z)

    def ahead(self, distance, height=None):
        """Ponto à frente do jogador, na altura dos olhos (ou `height`)."""
        dx, dy = C.yaw_dir(self.yaw)
        return (self.x + dx * distance, self.y + dy * distance, self.eye_z if height is None else height)

    def gaze(self, distance=6.0):
        """Ponto para onde o jogador olhava (com a inclinação da cabeça): a primeira vista da cutscene é a do jogo."""
        dx, dy = C.yaw_dir(self.yaw)
        flat = math.cos(self.pitch)
        return (self.x + dx * flat * distance, self.y + dy * flat * distance,
                self.eye_z + math.sin(self.pitch) * distance)


class Actor:
    """Algo que vive por vários quadros (vento, pêndulo, carro). Subclasses restauram o que mexeram em `stop`.

    `late = True`: roda depois que a câmera do quadro foi posicionada (o corpo e as mãos dependem dela).
    """
    late = False

    def start(self, stage):
        pass

    def update(self, stage, dt):
        pass

    def stop(self, stage):
        pass


class Stage:
    def __init__(self, host):
        self.host = host
        self.errors = []
        self.player = self._snapshot()
        self.t = 0.0                      # tempo absoluto da cutscene
        self.dt = 0.0
        self.signals = {}                 # um ator publica (ex.: aceleração do carro), outro lê (o coelhinho)
        self.poses = {}                   # nome do objeto carregador -> (origem, (rx, ry, rz)); a câmera `mount` lê daqui
        self.actors = {}
        self.entity_speed = 0.0           # m/s que a rig da entidade usa para o passo
        self.flash_aim = (0.0, 0.0)       # graus (guinada, inclinação) da lanterna em relação à câmera: a luz não precisa cair onde o olhar cai
        self.camera_pose = None           # (posição, quaternion) da câmera neste quadro; os atores `late` leem
        self.flash_hand = 0.0             # 0..1: tremor da lanterna na mão (a lanterna do jogo segue a câmera da cutscene)
        self.flashlight_follows = False
        self._memo = {}
        self._headlights_used = False
        self.skipping = False             # True durante o skip: ações essenciais vão direto ao estado final
        self._loops = set()
        self._lit = set()                 # luzes CutLight_* que esta cutscene acendeu
        self._gains = set()               # luzes da casa que a cutscene escureceu/realçou
        self._head_limit = None           # (valor original) se a entidade foi erguida por esta cutscene
        self._dawn_used = False
        self._visibility = {}             # objeto -> (hide_viewport, hide_render) originais, devolvidos no fim
        self._touched = {}                # objeto -> transformação original
        self._arms = set()
        self._body_shown = False
        self._camera_q = None

    def _snapshot(self):
        try:
            x, y, z, yaw, eye_z = self.host.player_state()
        except Exception as exc:          # noqa: BLE001 - um host sem jogador ainda deixa a cutscene rodar
            self.errors.append(f"player_state: {exc}")
            x, y, z, yaw, eye_z = 0.0, 0.0, 0.0, 0.0, C.PLAYER_EYE_STAND
        pitch = 0.0
        getter = getattr(self.host, "player_pitch", None)
        if getter is not None:
            try:
                pitch = float(getter())
            except Exception as exc:      # noqa: BLE001
                self.errors.append(f"player_pitch: {exc}")
        return PlayerSnapshot(x, y, z, yaw, eye_z, pitch)

    def safe(self, label, fn, *args, **kwargs):
        """Chama o host; se falhar, anota e segue."""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:          # noqa: BLE001
            self.errors.append(f"{label}: {exc!r}")
            return None

    def resolve(self, value):
        return value(self) if callable(value) else value

    def memo(self, key, compute):
        """Calcula `compute(stage)` na primeira vez e guarda: posições que a cutscene precisa fixar quando ela começa."""
        if key not in self._memo:
            self._memo[key] = compute(self)
        return self._memo[key]

    # ---------------------------------------------------------------- objetos
    def obj(self, name):
        return self.safe(f"get_object({name})", self.host.get_object, name)

    def touch(self, obj):
        """Guarda a transformação original de `obj` (uma vez) para devolver ao terminar."""
        if obj is None or obj in self._touched:
            return obj
        saved = {}
        for attr in ("location", "rotation_euler", "scale"):
            value = getattr(obj, attr, None)
            if value is not None:
                saved[attr] = tuple(value)
        saved["rotation_mode"] = getattr(obj, "rotation_mode", None)
        saved["rotation_quaternion"] = tuple(getattr(obj, "rotation_quaternion", ())) or None
        self._touched[obj] = saved
        return obj

    def _restore_transforms(self):
        for obj, saved in self._touched.items():
            for attr in ("location", "rotation_euler", "scale"):
                if attr in saved:
                    setattr(obj, attr, saved[attr])
            if saved["rotation_mode"] is not None:
                obj.rotation_mode = saved["rotation_mode"]
            if saved["rotation_quaternion"] is not None:
                obj.rotation_quaternion = saved["rotation_quaternion"]
        self._touched.clear()

    # ---------------------------------------------------------------- carregadores (o carro)
    def set_mount(self, name, origin, euler):
        self.poses[name] = (tuple(origin), tuple(euler))

    def mount_quaternion(self, name):
        return camera.euler_xyz_quaternion(*self.poses[name][1])

    def mount_transform(self, name):
        """(origem, quaternion) do objeto que carrega a câmera; sem ator que o mova, vale a pose do objeto na cena."""
        if name not in self.poses:
            obj = self.obj(name)
            location = tuple(getattr(obj, "location", (0.0, 0.0, 0.0))) if obj is not None else (0.0, 0.0, 0.0)
            euler = tuple(getattr(obj, "rotation_euler", (0.0, 0.0, 0.0))) if obj is not None else (0.0, 0.0, 0.0)
            self.poses[name] = (location, euler)
        return self.poses[name][0], self.mount_quaternion(name)

    def to_world(self, mount, local_point):
        origin, q = self.mount_transform(mount)
        r = camera.rotate(q, local_point)
        return (origin[0] + r[0], origin[1] + r[1], origin[2] + r[2])

    def to_local(self, mount, world_point):
        """O inverso de `to_world`: um ponto do mundo no espaço do carregador (para a câmera presa ao carro olhar algo fora dele)."""
        origin, q = self.mount_transform(mount)
        w, x, y, z = q
        r = camera.rotate((w, -x, -y, -z), (world_point[0] - origin[0], world_point[1] - origin[1], world_point[2] - origin[2]))
        return r

    # ---------------------------------------------------------------- atores
    def start_actor(self, key, actor):
        self.stop_actor(key)
        self.actors[key] = actor
        self.safe(f"actor.start({key})", actor.start, self)
        if self.errors and self.errors[-1].startswith(f"actor.start({key})"):
            self.actors.pop(key, None)                  # não deu partida: não roda a cada quadro para falhar de novo

    def stop_actor(self, key):
        actor = self.actors.pop(key, None)
        if actor is not None:
            self.safe(f"actor.stop({key})", actor.stop, self)

    def update_actors(self, dt, late=False):
        for key, actor in list(self.actors.items()):
            if actor.late == late:
                self.safe(f"actor.update({key})", actor.update, self, dt)

    # ---------------------------------------------------------------- som
    def sound(self, name, pos=None, volume=1.0, pitch=1.0):
        self.safe(f"audio.play({name})", self.host.audio.play, name, pos=pos, volume=volume, pitch=pitch)

    def loop(self, key, name, volume=1.0, pos=None):
        audio = self.host.audio
        if hasattr(audio, "loop"):
            self.safe(f"audio.loop({name})", audio.loop, key, name, pos=pos, volume=volume)
            self._loops.add(key)
        else:
            self.sound(name, pos=pos, volume=volume)

    def stop_loop(self, key):
        if key in self._loops and hasattr(self.host.audio, "stop"):
            self.safe(f"audio.stop({key})", self.host.audio.stop, key)
        self._loops.discard(key)

    def stop_all_loops(self):
        for key in list(self._loops):
            self.stop_loop(key)

    # ---------------------------------------------------------------- luzes
    def set_light(self, name, energy):
        """Liga/desliga uma luz `CutLight_*` (desligada = oculta, para não pesar no orçamento de luzes)."""
        obj = self.obj(name)
        if obj is None:
            return
        on = energy > 0.0
        obj.hide_viewport = obj.hide_render = not on
        obj.data.energy = max(0.0, energy)
        (self._lit.add if on else self._lit.discard)(name)

    def house_light(self, name, gain):
        """Escurece ou realça uma luz da casa (`Light_<sala>_cN`) sem brigar com o LightManager do engine."""
        setter = getattr(self.host, "set_light_gain", None)
        if setter is not None:
            self.safe(f"set_light_gain({name})", setter, name, gain)
            (self._gains.add if abs(gain - 1.0) > 1e-6 else self._gains.discard)(name)

    def headlights(self, on):
        """Liga/desliga os faróis do carro (módulo props). Ligados usam `sa_base_energy` se existir."""
        for name in ("Car_Headlight_L", "Car_Headlight_R"):
            obj = self.obj(name)
            if obj is None or not hasattr(getattr(obj, "data", None), "energy"):
                continue
            obj.hide_viewport = obj.hide_render = not on
            obj.data.energy = float(obj.get("sa_base_energy", HEADLIGHT_ENERGY)) if on else 0.0
        self._headlights_used = self._headlights_used or on

    def headlight_level(self, level):
        """Intensidade 0..1 dos faróis (a partida do motor faz a luz oscilar)."""
        for name in ("Car_Headlight_L", "Car_Headlight_R"):
            obj = self.obj(name)
            if obj is None or not hasattr(getattr(obj, "data", None), "energy"):
                continue
            base = float(obj.get("sa_base_energy", HEADLIGHT_ENERGY))
            obj.hide_viewport = obj.hide_render = level <= 0.001
            obj.data.energy = base * max(0.0, level)
            self._headlights_used = self._headlights_used or level > 0.001

    def set_visible(self, name, visible):
        obj = self.obj(name)
        if obj is not None:
            self.set_hidden(obj, not visible)

    def set_hidden(self, obj, hidden):
        """Mostra/esconde `obj` lembrando como ele estava, para devolver ao terminar a cutscene."""
        self._visibility.setdefault(obj, (obj.hide_viewport, obj.hide_render))
        obj.hide_viewport = obj.hide_render = hidden

    # ---------------------------------------------------------------- entidade
    @property
    def entity(self):
        return self.host.entity

    def set_dawn(self, amount):
        """Clareia o céu (halo do Sol Negro e horizonte) via `world.sky.set_dawn`; ignora se não houver mundo."""
        if getattr(self.host.scene, "world", None) is None:
            return
        from ..world import sky
        self.safe("sky.set_dawn", sky.set_dawn, self.host.scene, amount)
        self._dawn_used = amount > 0.0

    def stand_tall(self, entity):
        """Tira o limite de altura da cabeça (a rig curva a entidade sob o forro); `finish_up` devolve."""
        if hasattr(entity, "head_limit") and self._head_limit is None:
            self._head_limit = (entity.head_limit,)
            entity.head_limit = None

    def entity_head(self):
        return tuple(self.entity.head_position())

    # ---------------------------------------------------------------- corpo do jogador
    @property
    def body(self):
        return getattr(self.host, "body", None)

    def show_body(self, visible):
        """Liga o corpo na cutscene (câmera dos olhos do Daniel). Sem corpo no jogo, não faz nada."""
        shower = getattr(self.host, "show_body", None)
        if shower is not None:
            self.safe("show_body", shower, visible)
        self._body_shown = visible

    def body_call(self, method, *args, **kwargs):
        body = self.body
        fn = getattr(body, method, None) if body is not None else None
        if fn is None:
            return None
        return self.safe(f"body.{method}", fn, *args, **kwargs)

    def arm(self, side):
        body = self.body
        if body is None:
            return None
        arm = self.safe(f"body.arm({side})", body.arm, side)
        if arm is not None:
            self._arms.add(side)
        return arm

    # ---------------------------------------------------------------- fim
    def finish_up(self):
        """Ao terminar (ou pular): para atores e loops, apaga as luzes de cutscene, devolve tudo o que foi mexido."""
        for key in list(self.actors):
            self.stop_actor(key)
        self.stop_all_loops()
        if self._headlights_used:
            self.headlights(False)
        for name in list(self._lit):
            self.set_light(name, 0.0)
        for name in list(self._gains):
            self.house_light(name, 1.0)
        for side in list(self._arms):
            arm = self.safe(f"body.arm({side})", self.body.arm, side) if self.body is not None else None
            if arm is not None:
                self.safe("arm.release", arm.release, 1.0)
        self._arms.clear()
        if self._body_shown:
            self.show_body(False)
            attach = getattr(self.body, "attach_view", None)
            if attach is not None:
                self.safe("body.attach_view(None)", attach, None)
        self._restore_transforms()
        for obj, (hide_viewport, hide_render) in self._visibility.items():
            obj.hide_viewport, obj.hide_render = hide_viewport, hide_render
        self._visibility.clear()
        if self._dawn_used:
            self.set_dawn(0.0)
        if self._head_limit is not None:
            self.entity.head_limit = self._head_limit[0]
            self._head_limit = None
