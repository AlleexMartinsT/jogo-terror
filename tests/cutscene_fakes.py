"""Anfitrião falso para os testes das cutscenes: registra tudo o que elas fazem, sem Blender.

Usado por `test_cutscenes_player.py` e `test_cutscenes_fluency.py`.
"""
import math

import numpy as np

from sem_alvorada import conventions as C
from sem_alvorada import layout

PLAYER_STATE = (11.1, 5.9, 0.0, math.radians(-90), 1.65)          # cozinha, diante da porta da garagem
HALL_STATE = (5.6, 3.6, 2.8, math.radians(0), 4.45)                 # no corredor de cima, olhando para o norte
START_STATES = {"intro": (*layout.PLAYER_START, 0.0, 4.45), "blackout": HALL_STATE, "garage_unlock": PLAYER_STATE,
                "death": (6.6, 5.2, 2.8, 0.0, 4.45), "ending": (16.5, 3.6, 0.0, math.radians(90), 1.65)}

LIGHT_NAMES = ("CutLight_ClockGlow", "CutLight_BedLamp", "CutLight_Dawn", "CutLight_Road", "CutLight_CorridorRim",
               "CutLight_Driveway", "CutLight_CarCabin")
OBJECT_NAMES = ("CutsceneCam", "Car", "GarageRollup", "Car_Headlight_L", "Car_Headlight_R", "Cut_EndClock", "PlayerCam",
                "Car_Wheel_FL", "Car_Wheel_FR", "Car_Wheel_RL", "Car_Wheel_RR", "Cut_Bunny", "Cut_Wheel", "Cut_Key",
                "Cut_KeyCharm", "Cut_Dust", "Cut_Sparks", "Cut_LidTop", "Cut_LidBottom", "AlarmClock",
                "Curtain_w_master_n", "Curtain_w_master_w")


class FakeDof:
    def __init__(self):
        self.use_dof = False
        self.focus_distance = 10.0
        self.aperture_fstop = 2.8


class FakeDatablock:
    def __init__(self, energy=None):
        self.angle = 1.0
        self.dof = FakeDof()
        if energy is not None:
            self.energy = energy


class FakeVertices:
    def __init__(self, coords):
        self.coords = np.asarray(coords, np.float32).reshape(-1, 3)

    def __len__(self):
        return len(self.coords)

    def foreach_get(self, attr, buffer):
        buffer[:] = self.coords.reshape(-1)

    def foreach_set(self, attr, values):
        self.coords = np.asarray(values, np.float32).reshape(-1, 3).copy()


class FakeMesh:
    """Malha com vértices em numpy: o suficiente para os atores de deformação."""

    def __init__(self, coords):
        self.vertices = FakeVertices(coords)
        self.updates = 0

    def update(self):
        self.updates += 1


def curtain_grid(columns=48, rows=60, width=3.0, top=0.8, bottom=-1.46, depth=-0.2):
    xs = np.linspace(-width / 2, width / 2, columns)
    zs = np.linspace(bottom, top, rows)
    grid = np.array([(x, depth + 0.05 * math.sin(x * 9.0), z) for z in zs for x in xs], np.float32)
    return grid


class _Location(list):
    """Lista com .x .y .z, como o Vector do Blender."""

    def __init__(self):
        super().__init__([0.0, 0.0, 0.0])

    z = property(lambda self: self[2], lambda self, v: self.__setitem__(2, v))


class FakeObject:
    def __init__(self, name, light=False, mesh=None):
        self.name = name
        self.location = _Location()
        self.rotation_mode = "XYZ"
        self.rotation_euler = (0.0, 0.0, 0.0)
        self.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        self.scale = (1.0, 1.0, 1.0)
        self.hide_viewport = self.hide_render = light
        self.data = mesh if mesh is not None else FakeDatablock(0.0 if light else None)
        self.props = {}

    def get(self, key, default=None):
        return self.props.get(key, default)


class FakeAudio:
    def __init__(self, fail=False):
        self.played, self.loops, self.stopped, self.fail = [], {}, [], fail

    def play(self, name, pos=None, volume=1.0, pitch=1.0):
        if self.fail:
            raise RuntimeError("sem dispositivo de áudio")
        self.played.append(name)

    def loop(self, key, name, pos=None, volume=1.0, pitch=1.0):
        self.loops[key] = name

    def stop(self, key):
        self.loops.pop(key, None)
        self.stopped.append(key)


class FakeEntity:
    def __init__(self):
        self.visible = False
        self.transform = None
        self.anim = "idle"
        self.eye_level = 0.0
        self.look = "unset"
        self.look_rate = 200.0
        self.head_limit = 2.42
        self.updates = 0
        self.speeds = []
        self.death_amounts = []
        self.history = []
        self._grab_start = None

    def set_visible(self, flag):
        self.visible = bool(flag)

    def set_transform(self, x, y, z, yaw):
        self.transform = (x, y, z, yaw)

    def set_anim(self, name):
        self.anim = name
        self.history.append(name)

    def eyes(self, level):
        self.eye_level = level

    def look_at(self, x, y=None, z=None):
        self.look = None if x is None else (x, y, z)

    def update(self, dt, speed=None):
        self.updates += 1
        self.speeds.append(speed)

    def head_position(self):
        x, y, z, _ = self.transform or (0, 0, 0, 0)
        return (x, y, z + 2.5)

    def pose_for_death(self, eye, amount=1.0):
        """Como a rig real: sai de onde está e chega, em `amount`, a 0,62 m dos olhos, de frente para eles."""
        self.death_amounts.append(amount)
        ex, ey, ez = eye
        if self._grab_start is None:
            self._grab_start = self.transform
        sx, sy, sz, syaw = self._grab_start
        length = math.hypot(sx - ex, sy - ey) or 1.0
        fx, fy = ex + (sx - ex) / length * 0.62, ey + (sy - ey) / length * 0.62
        self.transform = (sx + (fx - sx) * amount, sy + (fy - sy) * amount, sz, syaw)


class FakeDoors:
    def __init__(self):
        self.snaps = []
        self.glides = []

    def snap(self, door_id, value):
        self.snaps.append((door_id, value))

    def set_openness(self, door_id, value, speed=None):
        self.glides.append((door_id, value, speed))

    def final(self, door_id):
        events = [(v) for d, v in self.snaps if d == door_id] + [v for d, v, _ in self.glides if d == door_id]
        return events[-1] if events else None


class FakeArm:
    ready = True

    def __init__(self, calls, side):
        self.calls, self.side = calls, side

    def set_target(self, position, rotation_deg=(0, 0, 0), weight=1.0):
        self.calls.append(("target", self.side, tuple(position), tuple(rotation_deg), weight))

    def set_fingers(self, curls, spread=0.0, blend=1.0):
        self.calls.append(("fingers", self.side, tuple(curls), spread))

    def release(self, blend=1.0):
        self.calls.append(("release", self.side))

    def hold(self, obj, offset=None):
        self.calls.append(("hold", self.side))

    def drop(self, obj=None):
        self.calls.append(("drop", self.side))

    def hand_world_position(self):
        return (0.0, 0.0, 0.0)


class RecordingBody:
    """Corpo de mentira com a interface de `engine/fallbacks.NullBody` mais `attach_view`: guarda as chamadas."""
    visible = False

    def __init__(self):
        self.calls = []
        self._arms = {"L": FakeArm(self.calls, "L"), "R": FakeArm(self.calls, "R")}

    def set_visible(self, visible):
        self.visible = visible

    def update(self, dt, player, bob=(0.0, 0.0)):
        self.calls.append(("update",))

    def arm(self, side):
        return self._arms[side]

    def place(self, x, y, z, yaw):
        self.calls.append(("place", x, y, z, yaw))

    def pose(self, name, seconds=0.0):
        self.calls.append(("pose", name, seconds))

    def attach_view(self, camera_obj):
        self.calls.append(("attach_view", camera_obj.name if camera_obj is not None else None))

    def reset(self):
        self.calls.append(("reset",))

    def poses(self):
        return [c[1] for c in self.calls if c[0] == "pose"]


class _FakeScene:
    objects = ()


class FakeHost:
    def __init__(self, state=PLAYER_STATE, missing=(), audio_fails=False, pitch=0.0, body=None, meshes=True):
        self.audio = FakeAudio(audio_fails)
        self.entity = FakeEntity()
        self.doors = FakeDoors()
        self.scene = _FakeScene()
        self.state = state
        self.pitch = pitch
        self.body = body
        self.body_shown = []
        self.gains = {}
        self.camera = None
        self.camera_calls = []
        self.finished = []
        self.power_calls, self.flashlight_calls, self.placed = [], [], []
        self.silence_calls, self.brain_calls, self.brain_pos = [], 0, None
        self.objects = {}
        for name in OBJECT_NAMES:
            if name in missing:
                continue
            mesh = None
            if meshes and name == "Cut_Dust":
                mesh = FakeMesh(np.zeros((140 * 4, 3)))
            elif meshes and name == "Cut_Sparks":
                mesh = FakeMesh(np.zeros((28 * 4, 3)))
            elif meshes and name.startswith("Curtain_"):
                mesh = FakeMesh(curtain_grid())
            self.objects[name] = FakeObject(name, light="Headlight" in name, mesh=mesh)
        for name in ("Cut_EndClock", "Cut_Dust", "Cut_Sparks", "Cut_LidTop", "Cut_LidBottom", "Cut_Key", "Cut_KeyCharm"):
            if name in self.objects:
                self.objects[name].hide_viewport = self.objects[name].hide_render = True
        for name in LIGHT_NAMES:
            self.objects[name] = FakeObject(name, light=True)

    # ---- o contrato do host (seção 5.4 + extensões da fase 3)
    def set_camera(self, obj):
        self.camera_calls.append(obj)
        self.camera = obj

    def get_object(self, name):
        return self.objects.get(name)

    def player_state(self):
        return self.state

    def player_pitch(self):
        return self.pitch

    def place_player(self, x, y, z, yaw):
        self.placed.append((x, y, z, yaw))
        self.state = (x, y, z, yaw, z + C.PLAYER_EYE_STAND)

    def set_power(self, on, flicker=0.0):
        self.power_calls.append((on, flicker))

    def set_light_gain(self, name, gain):
        self.gains[name] = gain

    def flash_light(self, seconds):
        pass

    def set_flashlight(self, on):
        self.flashlight_calls.append(on)

    def noise_silence(self, seconds):
        self.silence_calls.append(seconds)

    def entity_brain_activate(self, pos=None):
        self.brain_calls += 1
        self.brain_pos = pos

    def show_body(self, visible):
        self.body_shown.append(bool(visible))

    def finish(self, reason):
        self.finished.append(reason)


def place_entity_near_player(host, distance=1.1):
    """No jogo a entidade já está colada no jogador quando ele morre."""
    x, y, z, yaw, _ = host.state
    dx, dy = C.yaw_dir(yaw)
    host.entity.set_transform(x + dx * distance, y + dy * distance, z, yaw + math.pi)
    host.entity.set_visible(True)


def host_for(name, **kwargs):
    host = FakeHost(START_STATES[name], **kwargs)
    if name == "death":
        place_entity_near_player(host)
    return host


def settle_state(host):
    """Resumo do que a cutscene deixou no jogo (para comparar execução completa e skip)."""
    entity = host.entity
    objects = {}
    for name, obj in sorted(host.objects.items()):
        if name == "CutsceneCam":
            continue
        energy = getattr(obj.data, "energy", None)
        objects[name] = (tuple(round(v, 6) for v in obj.location), tuple(round(v, 6) for v in obj.rotation_euler),
                         obj.rotation_mode, obj.hide_viewport, obj.hide_render,
                         None if energy is None else round(energy, 6))
    return {
        "placed": [tuple(round(v, 6) for v in host.placed[-1])] if host.placed else [],
        "power": host.power_calls[-1] if host.power_calls else None,
        "flashlight": host.flashlight_calls[-1] if host.flashlight_calls else None,
        "brain": (host.brain_calls, None if host.brain_pos is None else tuple(round(v, 6) for v in host.brain_pos)),
        "entity": (entity.visible, None if entity.transform is None else tuple(round(v, 6) for v in entity.transform),
                   entity.anim, round(entity.eye_level, 6), entity.head_limit),
        "door": host.doors.final("garage_door"),
        "gains": {k: v for k, v in host.gains.items() if abs(v - 1.0) > 1e-9},
        "loops": dict(host.audio.loops),
        "body_shown": host.body_shown[-1] if host.body_shown else False,
        "objects": objects,
        "finished": list(host.finished),
    }
