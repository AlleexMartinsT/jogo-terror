"""EntityRig: controle em tempo de execução do Alto (sem UI). API do contrato, seção 5.3.

    rig = EntityRig(scene)
    rig.set_transform(x, y, z, yaw); rig.set_anim("stalk"); rig.look_at(px, py, pz)
    rig.update(dt, speed)          # todo quadro

A animação vem de `motion.Motion` (puro Python + mathutils); aqui só copiamos o resultado para
os pose bones, a luz dos olhos e os materiais.
"""
import math

import bpy  # noqa: F401
from mathutils import Vector

from .. import conventions as C
from . import assemble
from . import materials
from . import motion as mo
from . import skeleton as S

LOOK_TURN_RATE = 220.0          # graus/s com que a cabeça acompanha o alvo
LOOK_FADE_RATE = 4.0            # 1/s para ligar e desligar o olhar
LOOK_HOLD = 0.5                 # s que um look_at vale sem ser renovado
EYE_LIGHT_FORWARD = 0.38       # longe do rosto: perto demais estoura a pele em branco


def _wrap_degrees(angle):
    return (angle + 180.0) % 360.0 - 180.0


class EntityRig:
    def __init__(self, scene):
        self.scene = scene
        self.root = self._find(C.OBJ_ENTITY)
        self.armature = self._find(assemble.RIG_NAME)
        self.body = self._find(assemble.BODY_NAME)
        self.eyes_obj = self._find(assemble.EYES_NAME)
        self.eye_light = self._find(assemble.LIGHT_NAME)
        self._bones = self._cache_bones()
        self.motion = mo.Motion()
        self._shown = self.motion.last          # última pose aplicada à malha
        self.position = Vector(self.root.location)
        self.yaw = self.root.rotation_euler.z
        self.look_rate = LOOK_TURN_RATE
        self._look_target = None
        self._look_until = 0.0
        self._eye_level = 0.0
        self._death = None
        self.eyes(0.0)

    # ------------------------------------------------------------------ montagem
    def _find(self, name):
        obj = self.scene.objects.get(name) or bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f"objeto '{name}' não existe: rode a etapa 'entity' do build antes de usar EntityRig")
        return obj

    def _cache_bones(self):
        """Para cada osso: pose bone e a rotação de repouso R usada na conjugação B = R^-1 Q R."""
        cached = {}
        for pose_bone in self.armature.pose.bones:
            rest = pose_bone.bone.matrix_local.to_3x3().to_quaternion()
            cached[pose_bone.name] = (pose_bone, rest, rest.inverted())
        missing = set(S.BONE_ORDER) - set(cached)
        if missing:
            raise RuntimeError(f"armadura sem os ossos {sorted(missing)}")
        return cached

    # ------------------------------------------------------------------ contrato
    @property
    def visible(self):
        return not self.body.hide_viewport

    def set_visible(self, flag):
        assemble.hide_entity((self.body, self.eyes_obj, self.eye_light), hidden=not flag)
        self._apply_eye_light()

    def set_transform(self, x, y, z, yaw):
        self.position = Vector((x, y, z))
        self.yaw = yaw
        self.root.location = self.position
        self.root.rotation_euler = (0.0, 0.0, yaw)

    def set_anim(self, name):
        self._death = None
        self.motion.set_anim(name)

    @property
    def anim(self):
        return self.motion.anim

    @property
    def head_limit(self):
        """Altura máxima do topo da cabeça (m): dentro da casa ele se curva para caber sob o forro."""
        return self.motion.head_limit

    @head_limit.setter
    def head_limit(self, value):
        self.motion.head_limit = value

    def look_at(self, x, y=None, z=None, hold=LOOK_HOLD):
        """A cabeça segue o ponto (limitada a +-80 graus de guinada) por `hold` segundos.

        Quem quer manter o olhar chama todo quadro (o cérebro e as cutscenes fazem assim); se ninguém
        renovar, o olhar se solta sozinho e a cabeça volta ao repouso. `look_at(None)` solta na hora.
        """
        if x is None:
            self._look_target = None
            return
        self._look_target = Vector(x) if y is None else Vector((x, y, z))
        self._look_until = self.motion.time + hold

    def clear_look(self):
        self._look_target = None

    @property
    def look_angles(self):
        """(guinada, inclinação) em graus que a cabeça está usando agora em relação ao corpo."""
        return self.motion.look_yaw, self.motion.look_pitch

    def eyes(self, level):
        """Brilho dos olhos de 0 a 1: emissão do material e luz `Entity_EyeLight`."""
        self._eye_level = max(0.0, min(1.0, float(level)))
        materials.set_eye_strength(self._eye_level)
        self._apply_eye_light()

    @property
    def eye_level(self):
        return self._eye_level

    def _apply_eye_light(self):
        base = self.eye_light.get(C.P_LIGHT_ENERGY, assemble.EYE_LIGHT_ENERGY)
        self.eye_light.data.energy = base * self._eye_level if self.visible else 0.0

    def head_position(self):
        """Centro da cabeça no mundo, calculado pela cinemática (não depende de avaliar a cena)."""
        return tuple(self._to_world(self._shown.midpoint("Head")))

    def _to_world(self, local):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return self.position + Vector((c * local.x - s * local.y, s * local.x + c * local.y, local.z))

    def joint_world(self, bone_name):
        """Posição no mundo do início de um osso (útil para testes e cutscenes)."""
        return self._to_world(self._shown.head[bone_name])

    def pose_for_death(self, player_eye_pos, amount=1.0):
        """Pose de agarrar o rosto do jogador. `amount` 0..1 leva da posição atual até o agarrão."""
        eye = Vector(player_eye_pos)
        amount = max(0.0, min(1.0, amount))
        if self._death is None:
            self.motion.set_anim("attack")
            attack_pose = self._shown
            start_dir = Vector((eye.x - self.position.x, eye.y - self.position.y))
            grab, distance = mo.grab_solution(eye.z - self.position.z)
            self._death = {"start": self.position.copy(), "start_yaw": self.yaw, "grab": grab,
                           "distance": distance, "dir": start_dir, "attack": attack_pose}
        death = self._death
        heading = death["dir"]
        if heading.length < 1e-3:
            heading = Vector((-math.sin(death["start_yaw"]), math.cos(death["start_yaw"])))
        heading = heading.normalized()
        final_xy = Vector((eye.x, eye.y)) - heading * death["distance"]
        final_yaw = C.dir_yaw(heading.x, heading.y)
        start = death["start"]
        x = start.x + (final_xy.x - start.x) * amount
        y = start.y + (final_xy.y - start.y) * amount
        turn = _wrap_degrees(math.degrees(final_yaw - death["start_yaw"]))
        yaw = death["start_yaw"] + math.radians(turn) * min(1.0, amount * 2.0)
        self.set_transform(x, y, start.z, yaw)
        death["amount"] = amount
        self._apply_solution(self._death_solution())

    # ------------------------------------------------------------------ quadro a quadro
    def update(self, dt, speed=None):
        """Avança a animação `dt` segundos. `speed` (m/s) ajusta a cadência das animações de marcha."""
        self._update_look(dt)
        if not self.visible:
            self.motion.time += dt
            self.motion.clock += dt
            return
        if self._death is not None:
            self._death["attack"] = self.motion.update(dt, 0.0)
            self._apply_solution(self._death_solution())
        else:
            self._apply_solution(self.motion.update(dt, speed))

    def _death_solution(self):
        attack = self._death["attack"]
        grab = self._death["grab"]
        amount = self._death["amount"]
        local = S.blend_local(attack.local, grab.local, amount)
        hips = attack.hips_shift.lerp(grab.hips_shift, amount)
        return S.forward(local, hips)

    def _update_look(self, dt):
        motion = self.motion
        if self._look_target is not None and motion.time > self._look_until:
            self._look_target = None
        if self._look_target is None:
            motion.look_weight = max(0.0, motion.look_weight - LOOK_FADE_RATE * dt)
            return
        head = Vector(self.head_position())
        delta = self._look_target - head
        want_yaw = _wrap_degrees(math.degrees(C.dir_yaw(delta.x, delta.y) - self.yaw))
        want_pitch = math.degrees(math.atan2(delta.z, math.hypot(delta.x, delta.y)))
        want_yaw = mo.clamp(want_yaw, -mo.LOOK_LIMIT_YAW, mo.LOOK_LIMIT_YAW)
        want_pitch = mo.clamp(want_pitch, -mo.LOOK_LIMIT_PITCH_DOWN, mo.LOOK_LIMIT_PITCH_UP)
        step = self.look_rate * dt
        motion.look_yaw += mo.clamp(want_yaw - motion.look_yaw, -step, step)
        motion.look_pitch += mo.clamp(want_pitch - motion.look_pitch, -step, step)
        motion.look_weight = min(1.0, motion.look_weight + LOOK_FADE_RATE * dt)

    def _apply_solution(self, solution):
        for name, q_local in solution.local.items():
            pose_bone, rest, rest_inv = self._bones[name]
            pose_bone.rotation_quaternion = rest_inv @ q_local @ rest
        hips_bone, _rest, rest_inv = self._bones["Hips"]
        hips_bone.location = rest_inv @ solution.hips_shift
        self._place_eye_light(solution)

    def _place_eye_light(self, solution):
        forward = solution.world["Head"] @ Vector((0.0, 1.0, 0.0))
        self.eye_light.location = solution.midpoint("Head") + forward * EYE_LIGHT_FORWARD
        self._shown = solution
