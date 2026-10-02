"""Poses de corpo inteiro para as cutscenes: parado, deitado na cama, sentado na beira da cama, dirigindo.

Cada pose é FK pura (rotações locais em graus e um deslocamento do quadril). Convenção de `place(x, y, z, yaw)`:
em "stand" `z` é o chão; nas outras poses `z` é o plano onde o quadril apoia (colchão ou assento) e
o corpo olha para onde o `yaw` aponta (deitado: a cabeça fica atrás, em -Y local).
"""
import math

from mathutils import Quaternion, Vector

from . import skeleton as S

AXIS_X, AXIS_Y, AXIS_Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
PELVIS_ABOVE_SEAT = 0.10                   # centro da pelve acima do plano de apoio quando sentado ou deitado


def _x(degrees):
    return Quaternion(AXIS_X, math.radians(degrees))


def _spec(shift, **angles):
    """angles: osso com '_' no lugar de '.' -> graus em X, ou (x, y, z) em graus."""
    rot = {}
    for key, value in angles.items():
        name = key.replace("__", ".")
        if isinstance(value, (int, float)):
            rot[name] = _x(value)
        else:
            x, y, z = value
            rot[name] = Quaternion(AXIS_Z, math.radians(z)) @ Quaternion(AXIS_X, math.radians(x)) @ Quaternion(AXIS_Y, math.radians(y))
    return {"rot": rot, "shift": Vector(shift)}


def _both(**angles):
    out = {}
    for key, value in angles.items():
        out[key + "__L"] = value
        out[key + "__R"] = value
    return out


def _pose_stand():
    return _spec((0.0, 0.0, 0.0))


def _pose_sit_bed():
    pelvis = S.BONE_MAP["Hips"].head
    shift = (0.0, -0.02, PELVIS_ABOVE_SEAT - pelvis.z)
    return _spec(shift, **_both(Thigh=88.0, Shin=-92.0, Foot=4.0, UpperArm=24.0, Forearm=58.0),
                 Spine1=-4.0, Spine2=-5.0, Spine3=-3.0, Neck=8.0)


def _pose_lying_bed():
    pelvis = S.BONE_MAP["Hips"].head
    shift = (0.0, 0.0, PELVIS_ABOVE_SEAT - pelvis.z)
    return _spec(shift, Hips=90.0, **_both(Thigh=10.0, Shin=-18.0, UpperArm=-4.0, Forearm=6.0), Spine1=2.0, Neck=-6.0)


def _pose_driving():
    pelvis = S.BONE_MAP["Hips"].head
    shift = (0.0, -0.03, PELVIS_ABOVE_SEAT - pelvis.z)
    return _spec(shift, Hips=-3.0, Thigh__R=72.0, Shin__R=-48.0, Foot__R=-14.0, Thigh__L=78.0, Shin__L=-70.0,
                 **_both(UpperArm=38.0, Forearm=68.0), Spine1=-3.0, Spine2=-2.0)


POSE_BUILDERS = {"stand": _pose_stand, "sit_bed": _pose_sit_bed, "lying_bed": _pose_lying_bed, "driving": _pose_driving}
POSE_NAMES = tuple(POSE_BUILDERS)


def pose_data(name):
    """{'rot': {osso: Quaternion}, 'shift': Vector} da pose `name`."""
    if name not in POSE_BUILDERS:
        raise KeyError(f"pose desconhecida: {name!r} (use {', '.join(POSE_NAMES)})")
    return POSE_BUILDERS[name]()


class PoseBlend:
    """Transição suave entre a pose atual (qualquer dict de locais) e uma pose alvo."""

    def __init__(self):
        self.rot = {}
        self.shift = Vector((0.0, 0.0, 0.0))
        self._from_rot, self._from_shift = {}, Vector((0.0, 0.0, 0.0))
        self._to_rot, self._to_shift = {}, Vector((0.0, 0.0, 0.0))
        self._duration = 0.0
        self._elapsed = 0.0
        self.active = False

    def start(self, current_rot, current_shift, target, seconds):
        self._from_rot, self._from_shift = dict(current_rot), Vector(current_shift)
        self._to_rot, self._to_shift = target["rot"], target["shift"]
        self._duration, self._elapsed = max(0.0, seconds), 0.0
        self.active = True
        self._evaluate(0.0 if seconds > 0 else 1.0)
        if seconds <= 0:
            self.active = False

    def advance(self, dt):
        if not self.active:
            return
        self._elapsed += dt
        t = self._elapsed / self._duration if self._duration > 0 else 1.0
        if t >= 1.0:
            self.active = False
        self._evaluate(min(t, 1.0))

    def _evaluate(self, t):
        eased = t * t * (3.0 - 2.0 * t)
        names = set(self._from_rot) | set(self._to_rot)
        self.rot = {n: self._from_rot.get(n, S.IDENTITY).slerp(self._to_rot.get(n, S.IDENTITY), eased) for n in names}
        self.shift = self._from_shift.lerp(self._to_shift, eased)
