"""BodyRig: controle em tempo de execução do corpo do jogador (contrato em docs/FASE3.md, seção "Corpo").

    body = BodyRig(scene)
    body.update(dt, player, bob)         # todo quadro de jogo
    body.arm("R").set_target(...)        # mãos no espaço da câmera

A matemática vem de `locomotion` (pernas, tronco, respiração), `solver` (IK de dois ossos), `fingers`
e `poses`. Aqui só se copia o resultado para os pose bones e se movem os objetos presos às mãos.

Modos: "follow" (segue o `Player`), "placed" (as cutscenes decidem onde fica; `update(dt, None)` anima).
`reset()` volta ao modo "follow".
"""
import math
import time

import bpy  # noqa: F401
from mathutils import Euler, Matrix, Quaternion, Vector

from .. import conventions as C
from . import fingers as F
from . import skeleton as S
from .locomotion import Frame, Locomotion
from .poses import PoseBlend, eye_in_pose, pose_data
from .solver import ArmGoal, PoseSpec, solve

HAND_BLEND_RATE = 24.0         # 1/s: suavização dos dedos entre um preset e outro
EPSILON = 1e-6


def _clamp01(value):
    return max(0.0, min(1.0, value))


def _smooth01(x):
    t = _clamp01(x)
    return t * t * (3.0 - 2.0 * t)


class ArmControl:
    """Braço de um lado. Mesma superfície pública de `engine.fallbacks.NullArm`."""
    ready = True

    def __init__(self, rig, side):
        self._rig = rig
        self.side = side
        self._sx = S.side_sign(side)
        self._target = None
        self._rotation = Matrix.Identity(3)
        self._weight = 0.0
        self._curls = list(F.RELAXED_CURLS)
        self._spread = F.RELAXED_SPREAD
        self._goal_curls = list(F.RELAXED_CURLS)
        self._goal_spread = F.RELAXED_SPREAD
        self._cascade = F.FingerCascade(F.RELAXED_CURLS)
        self._finger_q = {}
        self._finger_dirty = True
        self._held = []                  # [(obj, offset 4x4, estado salvo)]
        self._rest_basis = S.rest_basis(side)
        self._rest_basis_inv = self._rest_basis.inverted()
        self._palm_offset = S.palm_offset(side)
        self._palm_world = None
        self._swivel = 0.0               # giro do cotovelo escolhido no quadro anterior (rad)

    # ------------------------------------------------------------------ contrato
    def set_target(self, position, rotation_deg=(0.0, 0.0, 0.0), weight=1.0):
        """Mão no espaço da câmera (X direita, Y cima, -Z frente, metros), centro da palma.

        `rotation_deg`: Euler XYZ em graus aplicado sobre a mão neutra (dedos para a frente, palma para baixo,
        polegar para o centro do corpo). `weight` 0..1 mistura com a pose solta."""
        self._target = Vector(position)
        self._rotation = Euler([math.radians(a) for a in rotation_deg], "XYZ").to_matrix()
        self._weight = _clamp01(float(weight))

    def set_fingers(self, curls, spread=0.0, blend=1.0):
        """`curls`: cinco valores 0..1 (polegar ao mindinho). `blend` é a fração do caminho até o alvo
        que esta chamada percorre: 1.0 é imediato; chamado todo quadro com 0.2 dá uma transição suave."""
        blend = _clamp01(float(blend))
        for i in range(5):
            self._goal_curls[i] += (_clamp01(curls[i]) - self._goal_curls[i]) * blend
        self._goal_spread += (max(-1.0, min(1.0, float(spread))) - self._goal_spread) * blend
        self._finger_dirty = True

    def release(self, blend=1.0):
        """Volta à pose solta: o peso do alvo cai `blend` do caminho até 0 e os dedos relaxam na mesma fração."""
        blend = _clamp01(float(blend))
        self._weight *= 1.0 - blend
        if self._weight < 1e-4:
            self._weight = 0.0
            self._target = None
        self.set_fingers(F.RELAXED_CURLS, F.RELAXED_SPREAD, blend)

    def hold(self, obj, offset=None):
        """Prende `obj` à mão. `offset`: None, (x, y, z) ou Matrix 4x4, no referencial da mão (o mesmo da câmera
        quando `rotation_deg` é zero: X direita, Y cima, -Z frente), origem no centro da palma."""
        for item in self._held:
            if item[0] is obj:
                self._held.remove(item)
        matrix = Matrix.Identity(4)
        if offset is not None:
            matrix = offset.copy() if isinstance(offset, Matrix) else Matrix.Translation(Vector(offset))
        saved = (obj.parent, obj.matrix_parent_inverse.copy(), obj.location.copy(), obj.rotation_euler.copy(),
                 obj.scale.copy(), obj.parent_type, obj.parent_bone)
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
        self._held.append((obj, matrix, saved))
        self._rig._place_held(self)

    def drop(self, obj=None):
        """Solta `obj` (ou tudo que a mão segura) e devolve a ele o pai e a posição que tinha antes do `hold`."""
        keep = []
        for item in self._held:
            if obj is not None and item[0] is not obj:
                keep.append(item)
                continue
            target, _matrix, saved = item
            parent, inverse, location, rotation, scale, parent_type, parent_bone = saved
            target.parent = parent
            if parent is not None:
                target.parent_type = parent_type
                if parent_type == "BONE":
                    target.parent_bone = parent_bone
                target.matrix_parent_inverse = inverse
            target.location, target.rotation_euler, target.scale = location, rotation, scale
        self._held = keep

    def hand_world_position(self):
        """(x, y, z) do centro da palma no mundo, da última pose calculada."""
        point = self._palm_world if self._palm_world is not None else self._rig._palm_from_rest(self.side)
        return (point.x, point.y, point.z)

    # ------------------------------------------------------------------ interno
    @property
    def _has_target(self):
        return self._target is not None and self._weight > 0.0

    def _advance_fingers(self, dt):
        """Aproxima os dedos mostrados do alvo (em cascata, base -> ponta); devolve os quaternions locais quando algo mudou."""
        changed = self._cascade.step(dt, self._goal_curls)
        for i in range(5):
            self._curls[i] = self._cascade.joint[i][0]
        step = 1.0 - math.exp(-HAND_BLEND_RATE * dt)
        delta = self._goal_spread - self._spread
        if abs(delta) > 1e-4:
            self._spread += delta * step
            changed = True
        if changed or not self._finger_q:
            self._finger_q = F.finger_rotations(self.side, self._curls, self._spread, self._cascade.joint)
            self._finger_dirty = True
        else:
            self._finger_dirty = False
        return self._finger_q

    def _goal(self, frame, view):
        """ArmGoal no espaço do corpo, ou None se o braço está solto."""
        if not self._has_target:
            return None
        cam_pos, cam_basis = view
        body_from_world = frame.body_from_world
        world_rot = cam_basis @ self._rotation @ S.NEUTRAL_HAND_CAM
        hand_body = body_from_world @ world_rot @ self._rest_basis_inv
        hand_q = hand_body.to_quaternion()
        palm_world = cam_pos + cam_basis @ Vector((self._target.x, self._target.y, self._target.z))
        palm_body = body_from_world @ (palm_world - frame.root)
        wrist = palm_body - hand_body @ self._palm_offset
        pole = Vector((self._sx * 0.35, -0.30, -1.0))
        view = (body_from_world @ (cam_pos - frame.root), body_from_world @ (cam_basis @ Vector((0.0, 0.0, -1.0))),
                body_from_world @ (cam_basis @ Vector((1.0, 0.0, 0.0))), body_from_world @ (cam_basis @ Vector((0.0, 1.0, 0.0))))
        return ArmGoal(wrist, hand_q, pole, self._weight, palm=palm_body, palm_offset=self._palm_offset, swivel=self._swivel,
                       view=view)


class BodyRig:
    """Corpo do jogador em primeira pessoa. Mesma superfície pública de `engine.fallbacks.NullBody`."""

    def __init__(self, scene):
        self.scene = scene
        self.armature = self._find(C.OBJ_BODY_RIG)
        self.mesh = self._find(C.OBJ_BODY)
        self._bones = self._cache_bones()
        self._written = {}
        self._visible = not self.mesh.hide_viewport
        self._arms = {"L": ArmControl(self, "L"), "R": ArmControl(self, "R")}
        self._loco = Locomotion()
        self._blend = PoseBlend()
        self._pose_name = "stand"
        self._mode = "follow"
        self._placed = (0.0, 0.0, 0.0, 0.0)
        self._view = None                     # objeto de câmera das cutscenes (None: a câmera do jogador)
        self._solution = None
        self._root = Vector((0.0, 0.0, 0.0))
        self._yaw = 0.0
        self._clock = 0.0
        self._frame_ms = 0.0
        self._last_spec_rot = {}
        self.reset()

    # ------------------------------------------------------------------ montagem
    def _find(self, name):
        obj = self.scene.objects.get(name) or bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f"objeto '{name}' não existe: rode a etapa 'body' do build antes de usar BodyRig")
        return obj

    def _cache_bones(self):
        cached = {}
        for pose_bone in self.armature.pose.bones:
            rest = pose_bone.bone.matrix_local.to_3x3().to_quaternion()
            cached[pose_bone.name] = (pose_bone, rest, rest.inverted())
        missing = set(S.BONE_ORDER) - set(cached)
        if missing:
            raise RuntimeError(f"armadura do corpo sem os ossos {sorted(missing)}")
        return [cached[name] for name in S.BONE_ORDER]

    # ------------------------------------------------------------------ contrato
    @property
    def visible(self):
        return self._visible

    def set_visible(self, visible):
        visible = bool(visible)
        if visible == self._visible:
            return
        self._visible = visible
        self.mesh.hide_viewport = self.mesh.hide_render = not visible

    def arm(self, side):
        return self._arms[side]

    def attach_view(self, camera_obj):
        """Câmera de referência dos alvos dos braços. None volta à câmera do jogador."""
        self._view = camera_obj

    def place(self, x, y, z, yaw):
        """Põe o corpo fora do jogador (cutscenes). Fica assim até `reset()`."""
        self._mode = "placed"
        self._placed = (float(x), float(y), float(z), float(yaw))
        self._refresh_pose_only()

    def pose(self, name, seconds=0.0):
        """Pose de corpo inteiro: "stand", "lying_bed", "sit_bed", "driving". `seconds` > 0 exige `update` por quadro."""
        target = pose_data(name)
        current = self._current_locals()
        self._blend.start(current[0], current[1], target, seconds)
        self._pose_name = name
        if self._mode == "follow" and name != "stand":
            self._mode = "placed"                       # a cutscene assumiu o corpo: fica onde o jogador estava
            self._placed = (self._root.x, self._root.y, self._root.z, self._yaw)
        self._refresh_pose_only()

    def reset(self):
        for arm in self._arms.values():
            arm.drop()
            arm._weight, arm._target = 0.0, None
            arm._swivel = 0.0
            arm._curls[:] = F.RELAXED_CURLS
            arm._goal_curls[:] = F.RELAXED_CURLS
            arm._cascade.reset(F.RELAXED_CURLS)
            arm._spread = arm._goal_spread = F.RELAXED_SPREAD
            arm._finger_q = {}
        self._mode = "follow"
        self._pose_name = "stand"
        self._view = None
        self._loco.reset()
        self._blend = PoseBlend()
        self._blend.start({}, Vector((0.0, 0.0, 0.0)), pose_data("stand"), 0.0)
        self._refresh_pose_only()

    # ------------------------------------------------------------------ quadro a quadro
    def update(self, dt, player, bob=(0.0, 0.0)):
        """Todo quadro. `player=None`: só anima a pose atual (cutscenes)."""
        if dt <= 0.0:
            return
        self._clock += dt
        if not self._visible:
            return
        started = time.perf_counter()
        if self._mode == "follow" and player is not None and self._pose_name == "stand":
            frame = self._loco.step(dt, player, bob)
            self._finish(dt, frame)
        else:
            self._blend.advance(dt)
            frame = self._pose_frame(dt)
            self._finish(dt, frame)
        self._frame_ms += ((time.perf_counter() - started) * 1000.0 - self._frame_ms) * 0.05

    # ------------------------------------------------------------------ pose + cena
    def _current_locals(self):
        if self._solution is None:
            return {}, Vector((0.0, 0.0, 0.0))
        return ({name: self._solution.local[i].copy() for i, name in enumerate(S.BONE_ORDER)},
                self._solution.hips_shift.copy())

    def _refresh_pose_only(self):
        frame = self._pose_frame(0.0)
        self._finish(0.0, frame)

    def _pose_frame(self, dt):
        frame = Frame()
        x, y, z, yaw = self._placed
        frame.root, frame.yaw = Vector((x, y, z)), yaw
        frame.spec = PoseSpec(hips_shift=self._blend.shift.copy(), rot=dict(self._blend.rot))
        breath = math.sin(self._clock * 1.4)
        frame.chest_scale = (1.0 + 0.006 * breath, 1.0 + 0.010 * breath, 1.0 + 0.008 * breath)
        frame.cam_pos, frame.cam_basis = Vector((x, y, z + 1.65)), Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(math.pi / 2, 3, "X")
        frame.phase_cycle, frame.gait = 0.0, "pose"
        return frame

    def _view_of(self, frame):
        """(posição, orientação 3x3) da câmera de referência. Lê a matriz do objeto, então vale para qualquer modo de rotação."""
        camera = self._view
        if camera is None:
            return frame.cam_pos, frame.cam_basis
        # sem pai, `matrix_basis` já reflete location/rotation do objeto neste instante (matrix_world só muda no depsgraph)
        matrix = camera.matrix_basis if camera.parent is None else camera.matrix_world
        return matrix.translation.copy(), matrix.to_3x3().normalized()

    def eye_position(self, pose="stand"):
        """Onde ficam os olhos (x, y, z) na pose `pose`, relativos ao ponto de `place(x, y, z, yaw)` e aos eixos do corpo
        (+Y para onde ele olha). Serve para pôr a câmera de uma cutscene exatamente nos olhos do corpo."""
        return eye_in_pose(pose)

    def _finish(self, dt, frame):
        frame.body_from_world = Matrix.Rotation(-frame.yaw, 3, "Z")
        view = self._view_of(frame)
        spec = frame.spec
        for side in S.SIDES:
            arm = self._arms[side]
            fingers = arm._advance_fingers(dt)
            spec.rot.update(fingers)
            goal = arm._goal(frame, view)
            if goal is not None:
                spec.arms[side] = goal
                spec.rot[f"Clavicle.{side}"] = self._shoulder_for(side, goal)
        solution = solve(spec)
        for side in S.SIDES:
            self._arms[side]._swivel = solution.swivel.get(f"UpperArm.{side}", 0.0)
        self._solution = solution
        self._root, self._yaw = frame.root, frame.yaw
        self._apply(solution, frame)
        for side in S.SIDES:
            self._arms[side]._palm_world = self._palm_world(side, solution)
            self._place_held(self._arms[side])

    @staticmethod
    def _shoulder_for(side, goal):
        """A clavícula avança e sobe um pouco quando a mão vai longe e alto: o alcance cresce e o ombro não fica travado."""
        rest = S.BONE_MAP[f"UpperArm.{side}"].head
        rel = goal.palm - rest
        sx = S.side_sign(side)
        forward = _smooth01((rel.y - 0.10) / 0.40)
        high = _smooth01((rel.z + 0.30) / 0.45)
        protract = math.radians(13.0 * forward) * goal.weight
        lift = math.radians(7.0 * high) * goal.weight
        return Quaternion((0.0, 0.0, 1.0), sx * protract) @ Quaternion((0.0, 1.0, 0.0), -sx * lift)

    # ------------------------------------------------------------------ escrita nos pose bones
    def _apply(self, solution, frame):
        written = self._written
        for i, (pose_bone, rest, rest_inv) in enumerate(self._bones):
            value = rest_inv @ solution.local[i] @ rest
            key = (round(value.w, 6), round(value.x, 6), round(value.y, 6), round(value.z, 6))
            if written.get(i) != key:
                pose_bone.rotation_quaternion = value
                written[i] = key
        hips, _rest, rest_inv = self._bones[0]
        shift = rest_inv @ solution.hips_shift
        key = (round(shift.x, 6), round(shift.y, 6), round(shift.z, 6))
        if written.get("hips") != key:
            hips.location = shift
            written["hips"] = key
        chest = self._bones[S.BONE_INDEX["Chest"]][0]
        scale = tuple(round(v, 5) for v in frame.chest_scale)
        if written.get("chest") != scale:
            chest.scale = frame.chest_scale
            written["chest"] = scale
        self.armature.location = frame.root
        self.armature.rotation_euler = (0.0, 0.0, frame.yaw)

    # ------------------------------------------------------------------ mãos e objetos presos
    def _root_matrix(self):
        return Matrix.Translation(self._root) @ Matrix.Rotation(self._yaw, 4, "Z")

    def _palm_world(self, side, solution):
        offset = self._arms[side]._palm_offset
        hand = f"Hand.{side}"
        point = solution.head[S.BONE_INDEX[hand]] + solution.world[S.BONE_INDEX[hand]] @ offset
        return self._root + Matrix.Rotation(self._yaw, 3, "Z") @ point

    def _palm_from_rest(self, side):
        hand = S.BONE_MAP[f"Hand.{side}"]
        return self._root + Matrix.Rotation(self._yaw, 3, "Z") @ (hand.head + self._arms[side]._palm_offset)

    def _place_held(self, arm):
        if not arm._held or self._solution is None:
            return
        side = arm.side
        index = S.BONE_INDEX[f"Hand.{side}"]
        hand_q = self._solution.world[index]
        rotation = Matrix.Rotation(self._yaw, 3, "Z") @ hand_q.to_matrix() @ arm._rest_basis @ S.NEUTRAL_HAND_CAM.inverted()
        palm = arm._palm_world if arm._palm_world is not None else self._palm_from_rest(side)
        frame_matrix = Matrix.Translation(palm) @ rotation.to_4x4()
        for obj, offset, _saved in arm._held:
            obj.matrix_world = frame_matrix @ offset
