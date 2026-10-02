"""Resolve uma pose do corpo: cinemática direta do tronco, IK de dois ossos nos braços e nas pernas.

Matemática pura (mathutils). Reaproveita `two_bone_joint` do esqueleto do Alto. A diferença para o Alto
é o cuidado com a torção: o osso de cima e o de baixo usam o MESMO eixo de dobradiça (a normal do plano
do membro), então o cotovelo e o joelho dobram como dobradiças e o tecido não torce. A torção do
antebraço entre o cotovelo e a mão é repartida entre `Forearm`, `ForearmRoll` e `Hand`.
"""
import math

from mathutils import Quaternion, Vector

from ..entity.skeleton import two_bone_joint
from . import skeleton as S

IDENTITY = S.IDENTITY
MAX_WRIST_SWING = math.radians(72.0)       # quanto a mão dobra em relação ao antebraço (flexão e desvio)
MAX_ANKLE_BEND = math.radians(70.0)
ROLL_SHARE = 0.62                          # fatia da torção que o osso do meio do antebraço assume

_N = len(S.BONES)
_NAME_OF = S.BONE_ORDER
_INDEX = S.BONE_INDEX
_PARENT = S.PARENT_INDEX
_OFFSET = S.CHILD_OFFSET
_REST_DIR = [b.rest_dir for b in S.BONES]
_LENGTH = [b.length for b in S.BONES]


class ArmGoal:
    """Onde o pulso deve chegar (espaço do corpo), a orientação absoluta da mão e o polo do cotovelo."""
    __slots__ = ("wrist", "hand_q", "pole", "weight", "palm", "palm_offset")

    def __init__(self, wrist, hand_q, pole, weight=1.0, palm=None, palm_offset=None):
        self.wrist, self.hand_q, self.pole, self.weight = wrist, hand_q, pole, weight
        # com `palm` (alvo do centro da palma) o solver corrige o pulso quando o limite de flexão muda a orientação
        self.palm, self.palm_offset = palm, palm_offset


class LegGoal:
    """Onde o tornozelo deve chegar e a orientação absoluta do pé (None: segue o repouso)."""
    __slots__ = ("ankle", "foot_q", "pole", "weight")

    def __init__(self, ankle, foot_q=None, pole=None, weight=1.0):
        self.ankle, self.foot_q, self.weight = ankle, foot_q, weight
        self.pole = pole if pole is not None else Vector((0.0, 1.0, 0.0))


class PoseSpec:
    """O que uma animação pede ao solver."""
    __slots__ = ("hips_shift", "rot", "arms", "legs")

    def __init__(self, hips_shift=None, rot=None, arms=None, legs=None):
        self.hips_shift = hips_shift if hips_shift is not None else Vector((0.0, 0.0, 0.0))
        self.rot = rot if rot is not None else {}
        self.arms = arms if arms is not None else {}
        self.legs = legs if legs is not None else {}


class Solution:
    """Pose resolvida: rotações locais, orientações absolutas e cabeças dos ossos (espaço do corpo)."""
    __slots__ = ("local", "world", "head", "hips_shift", "reach_error")

    def __init__(self, local, world, head, hips_shift):
        self.local, self.world, self.head, self.hips_shift = local, world, head, hips_shift
        self.reach_error = {}

    def tail(self, name):
        index = _INDEX[name]
        return self.head[index] + self.world[index] @ (S.BONES[index].tail - S.BONES[index].head)

    def point_on(self, name, rest_point):
        """Posição atual de um ponto fixo ao osso `name`, dado onde ele fica no repouso."""
        index = _INDEX[name]
        return self.head[index] + self.world[index] @ (Vector(rest_point) - S.BONES[index].head)


def _twist_swing(q, axis):
    """q = twist @ swing, com `twist` em torno de `axis` (a torção é aplicada por último)."""
    inverse = q.inverted()
    v = Vector((inverse.x, inverse.y, inverse.z))
    projected = axis * v.dot(axis)
    twist_inv = Quaternion((inverse.w, projected.x, projected.y, projected.z))
    if twist_inv.magnitude < 1e-9:
        return IDENTITY.copy(), q.copy()
    twist_inv.normalize()
    swing_inv = inverse @ twist_inv.inverted()
    return twist_inv.inverted(), swing_inv.inverted()


def _limit(q, max_angle):
    angle = q.angle
    if angle <= max_angle or angle < 1e-9:
        return q
    return IDENTITY.slerp(q, max_angle / angle)


def _chain_frames(upper_name, origin, joint, end):
    """Rotações absolutas (em relação ao repouso) do osso de cima e do de baixo, com dobradiça comum."""
    lower_name, _end_name = S.IK_CHAINS[upper_name]
    chord = (end - origin)
    unit = chord.normalized()
    bend = (joint - origin) - unit * (joint - origin).dot(unit)
    if bend.length < 1e-6:
        bend = Vector((0.0, 1.0, 0.0)) - unit * unit.y
    hinge = S.hinge_axis(unit, bend.normalized())
    rest = S.HINGE_REST[upper_name]
    upper_rest = S.frame_matrix(_REST_DIR[_INDEX[upper_name]], rest)
    lower_rest = S.frame_matrix(_REST_DIR[_INDEX[lower_name]], rest)
    upper = (S.frame_matrix(joint - origin, hinge) @ upper_rest.inverted()).to_quaternion()
    lower = (S.frame_matrix(end - joint, hinge) @ lower_rest.inverted()).to_quaternion()
    return upper, lower


def _blend_local(fk, ik, weight):
    if weight >= 1.0:
        return ik
    if weight <= 0.0:
        return fk
    return fk.slerp(ik, weight)


def _solve_leg(upper_name, origin, parent_world, goal, rot):
    """Locais das pernas: coxa, canela, pé (a ponta do pé segue o FK de `rot`)."""
    lower_name, end_name = S.IK_CHAINS[upper_name]
    thigh, shin = _INDEX[upper_name], _INDEX[lower_name]
    joint, end = two_bone_joint(origin, goal.ankle, _LENGTH[thigh], _LENGTH[shin], goal.pole)
    thigh_q, shin_q = _chain_frames(upper_name, origin, joint, end)
    local = {upper_name: _blend_local(rot.get(upper_name, IDENTITY), parent_world.inverted() @ thigh_q, goal.weight),
             lower_name: _blend_local(rot.get(lower_name, IDENTITY), thigh_q.inverted() @ shin_q, goal.weight)}
    if goal.foot_q is not None:
        foot_local = _limit(shin_q.inverted() @ goal.foot_q, MAX_ANKLE_BEND)
        local[end_name] = _blend_local(rot.get(end_name, IDENTITY), foot_local, goal.weight)
    return local, (end - goal.ankle).length


def _solve_arm(upper_name, origin, parent_world, goal, rot):
    """Locais do braço: braço, antebraço, meio do antebraço (torção) e mão."""
    lower_name, hand_name = S.IK_CHAINS[upper_name]
    roll_name = lower_name.replace("Forearm", "ForearmRoll")
    upper_i, lower_i = _INDEX[upper_name], _INDEX[lower_name]
    arm_len = _LENGTH[upper_i]
    fore_len = _LENGTH[lower_i] + _LENGTH[_INDEX[roll_name]]
    fore_axis = _REST_DIR[_INDEX[lower_name]]
    wrist = goal.wrist
    for _attempt in range(3):
        joint, end = two_bone_joint(origin, wrist, arm_len, fore_len, goal.pole)
        upper_q, fore_q = _chain_frames(upper_name, origin, joint, end)
        rel = fore_q.inverted() @ goal.hand_q
        twist, swing = _twist_swing(rel, fore_axis)
        swing = _limit(swing, MAX_WRIST_SWING)
        hand_q = fore_q @ twist @ swing
        if goal.palm is None:
            break
        corrected = goal.palm - hand_q @ goal.palm_offset
        if (corrected - wrist).length < 2e-4:
            break
        wrist = corrected
    signed = 2.0 * math.atan2(twist.x * fore_axis.x + twist.y * fore_axis.y + twist.z * fore_axis.z, twist.w)
    if signed > math.pi:
        signed -= 2.0 * math.pi
    elif signed < -math.pi:
        signed += 2.0 * math.pi
    roll_q = fore_q @ Quaternion(fore_axis, signed * ROLL_SHARE)

    local = {
        upper_name: _blend_local(rot.get(upper_name, IDENTITY), parent_world.inverted() @ upper_q, goal.weight),
        lower_name: _blend_local(rot.get(lower_name, IDENTITY), upper_q.inverted() @ fore_q, goal.weight),
        roll_name: _blend_local(rot.get(roll_name, IDENTITY), fore_q.inverted() @ roll_q, goal.weight),
        hand_name: _blend_local(rot.get(hand_name, IDENTITY), roll_q.inverted() @ hand_q, goal.weight),
    }
    if goal.palm is not None:
        return local, (end + hand_q @ goal.palm_offset - goal.palm).length
    return local, (end - goal.wrist).length


def solve(spec):
    """Resolve a `PoseSpec`: FK de tudo, trocando os locais dos braços e pernas pelos de IK onde há alvo."""
    local = [IDENTITY] * _N
    world = [IDENTITY] * _N
    head = [None] * _N
    forced = {}
    errors = {}
    rot = spec.rot
    for i in range(_N):
        name = _NAME_OF[i]
        parent = _PARENT[i]
        if parent < 0:
            parent_world = IDENTITY
            head[i] = S.BONES[i].head + spec.hips_shift
        else:
            parent_world = world[parent]
            head[i] = head[parent] + parent_world @ _OFFSET[i]
        q = forced.get(name)
        if q is None:
            q = rot.get(name, IDENTITY)
            if name in S.IK_CHAINS:
                side = name.rsplit(".", 1)[1]
                if name.startswith("UpperArm"):
                    goal = spec.arms.get(side)
                    if goal is not None and goal.weight > 0.0:
                        forced, errors[name] = _merge(forced, _solve_arm(name, head[i], parent_world, goal, rot))
                        q = forced[name]
                elif name.startswith("Thigh"):
                    goal = spec.legs.get(side)
                    if goal is not None and goal.weight > 0.0:
                        forced, errors[name] = _merge(forced, _solve_leg(name, head[i], parent_world, goal, rot))
                        q = forced[name]
        local[i] = q
        world[i] = parent_world @ q
    solution = Solution(local, world, head, spec.hips_shift)
    solution.reach_error = errors
    return solution


def _merge(forced, result):
    locals_, error = result
    forced.update(locals_)
    return forced, error
