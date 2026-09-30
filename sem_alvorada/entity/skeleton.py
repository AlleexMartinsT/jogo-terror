"""Esqueleto do Alto: ossos, hierarquia, cinemática direta e IK de dois ossos.

Este módulo é matemática pura (só `mathutils`, nada de cena). O mesmo cálculo alimenta
a animação, `head_position()`, a pose de morte e os testes de limites.

Convenção das rotações
----------------------
A entidade fica de pé no espaço da armadura com X = direita dela, Y = frente e Z = cima.
Cada osso guarda uma rotação `Q` RELATIVA AO PAI, escrita nesses eixos fixos (e não nos
eixos locais do osso, que dependem do "roll" escolhido ao criar a armadura). Assim
"inclinar o tronco 20 graus para a frente" é sempre uma rotação em X, seja qual for o osso.

Para o Blender, a rig converte `Q` em rotação local do pose bone por conjugação:
`B = R^-1 @ Q @ R`, onde `R` é a orientação de repouso do osso (`bone.matrix_local`).
"""
import math
from dataclasses import dataclass, field

import bpy  # noqa: F401  (no pacote pip, importar bpy é o que torna `mathutils` importável)
from mathutils import Quaternion, Vector

IDENTITY = Quaternion((1.0, 0.0, 0.0, 0.0))
DOWN = Vector((0.0, 0.0, -1.0))

# Alturas de referência (m). O modelo e o esqueleto derivam destes números.
HIP_Z = 1.24
KNEE_Z = 0.64
ANKLE_Z = 0.09
SHOULDER_Z = 2.10
ELBOW_Z = 1.42
WRIST_Z = 0.74
HAND_END_Z = 0.56
NECK_BASE_Z = 2.14
HEAD_BASE_Z = 2.40
HEAD_TOP_Z = 2.65
LEG_SPREAD = 0.10           # afastamento lateral do quadril
FINGER_NAMES = ("Index", "Middle", "Ring", "Pinky")
FINGER_LENGTH = {"Index": 0.21, "Middle": 0.23, "Ring": 0.21, "Pinky": 0.17}
# com a mão pendurada e a palma para a coxa, os dedos ficam lado a lado no eixo Y (polegar na frente)
FINGER_Y = {"Index": 0.030, "Middle": 0.010, "Ring": -0.010, "Pinky": -0.030}
ARM_SPREAD = {"shoulder": 0.21, "elbow": 0.25, "wrist": 0.29}
MAX_FORCED_BEND = 0.39 * 3.141592653589793      # ~70 graus: quanto um osso com orientação imposta (pé) pode dobrar


@dataclass(frozen=True)
class BoneDef:
    name: str
    parent: str | None
    head: Vector
    tail: Vector

    @property
    def length(self):
        return (self.tail - self.head).length

    @property
    def rest_dir(self):
        return (self.tail - self.head).normalized()


def side_sign(side):
    """R fica em +X (a entidade olha para +Y, então a direita dela é +X)."""
    return 1.0 if side == "R" else -1.0


def _build_bones():
    bones = []

    def add(name, parent, head, tail):
        bones.append(BoneDef(name, parent, Vector(head), Vector(tail)))

    add("Hips", None, (0, 0, HIP_Z), (0, 0, 1.36))
    add("Spine1", "Hips", (0, 0, 1.36), (0, 0, 1.62))
    add("Spine2", "Spine1", (0, 0, 1.62), (0, 0, 1.88))
    add("Spine3", "Spine2", (0, 0, 1.88), (0, 0, NECK_BASE_Z))
    add("Neck", "Spine3", (0, 0, NECK_BASE_Z), (0, 0, HEAD_BASE_Z))
    add("Head", "Neck", (0, 0, HEAD_BASE_Z), (0, 0, HEAD_TOP_Z))

    for side in ("L", "R"):
        sx = side_sign(side)
        add(f"Shoulder.{side}", "Spine3", (sx * 0.04, 0, SHOULDER_Z), (sx * 0.20, 0, SHOULDER_Z))
        add(f"UpperArm.{side}", f"Shoulder.{side}", (sx * ARM_SPREAD["shoulder"], 0, SHOULDER_Z),
            (sx * ARM_SPREAD["elbow"], 0, ELBOW_Z))
        add(f"Forearm.{side}", f"UpperArm.{side}", (sx * ARM_SPREAD["elbow"], 0, ELBOW_Z),
            (sx * ARM_SPREAD["wrist"], 0, WRIST_Z))
        hand_x = sx * ARM_SPREAD["wrist"]
        add(f"Hand.{side}", f"Forearm.{side}", (hand_x, 0, WRIST_Z), (hand_x, 0, HAND_END_Z))
        for finger in FINGER_NAMES:
            length = FINGER_LENGTH[finger]
            y = FINGER_Y[finger]
            knuckle = HAND_END_Z - length * 0.5
            add(f"{finger}A.{side}", f"Hand.{side}", (hand_x, y, HAND_END_Z), (hand_x, y, knuckle))
            add(f"{finger}B.{side}", f"{finger}A.{side}", (hand_x, y, knuckle),
                (hand_x, y, HAND_END_Z - length))
        add(f"Thumb.{side}", f"Hand.{side}", (hand_x, 0.05, WRIST_Z - 0.06),
            (hand_x, 0.08, WRIST_Z - 0.22))

        leg_x = sx * LEG_SPREAD
        add(f"Thigh.{side}", "Hips", (leg_x, 0, HIP_Z), (leg_x, 0, KNEE_Z))
        add(f"Shin.{side}", f"Thigh.{side}", (leg_x, 0, KNEE_Z), (leg_x, 0, ANKLE_Z))
        add(f"Foot.{side}", f"Shin.{side}", (leg_x, 0, ANKLE_Z), (leg_x, 0.26, 0.03))

        # abas da parte de baixo do sobretudo: balançam com o passo
        add(f"CoatFront.{side}", "Hips", (sx * 0.11, 0.10, 1.10), (sx * 0.11, 0.13, 0.52))
        add(f"CoatBack.{side}", "Hips", (sx * 0.11, -0.10, 1.10), (sx * 0.11, -0.14, 0.34))
    return bones


BONES = _build_bones()                      # pais sempre antes dos filhos
BONE_MAP = {b.name: b for b in BONES}
BONE_ORDER = [b.name for b in BONES]

# osso de cima -> (osso de baixo, direção do joelho/cotovelo na entidade parada)
IK_CHAINS = {}
for _side in ("L", "R"):
    _sx = side_sign(_side)
    IK_CHAINS[f"Thigh.{_side}"] = (f"Shin.{_side}", Vector((0.0, 1.0, 0.0)))
    IK_CHAINS[f"UpperArm.{_side}"] = (f"Forearm.{_side}", Vector((_sx * 0.5, -1.0, -0.2)))


def bone(name):
    return BONE_MAP[name]


# pontos da sola do pé relativos ao tornozelo (calcanhar e ponta dos dedos), iguais aos do modelo
SOLE_POINTS = (Vector((0.0, -0.065, -ANKLE_Z)), Vector((0.0, 0.30, -ANKLE_Z)))


def sole_rise(pitch_degrees):
    """Quanto o tornozelo precisa subir para a sola, inclinada `pitch_degrees`, não entrar no chão."""
    p = math.radians(pitch_degrees)
    lowest = min(pt.y * math.sin(p) + pt.z * math.cos(p) for pt in SOLE_POINTS)
    return max(0.0, -lowest - ANKLE_Z)


def sole_height(solution, foot_name):
    """Altura do ponto mais baixo da sola do pé `foot_name` numa pose resolvida."""
    origin, orientation = solution.head[foot_name], solution.world[foot_name]
    return min((origin + orientation @ pt).z for pt in SOLE_POINTS)


def foot_bones():
    return ("Foot.L", "Foot.R")


def finger_bones(side):
    """Ossos dos quatro dedos longos de uma mão, na ordem A, B por dedo."""
    return [(f"{finger}A.{side}", f"{finger}B.{side}") for finger in FINGER_NAMES]


# --------------------------------------------------------------------------
# Especificação de pose e solução
# --------------------------------------------------------------------------
@dataclass
class IKGoal:
    """Onde o fim da cadeia (tornozelo/pulso) deve chegar, no espaço da entidade."""
    target: Vector
    pole: Vector | None = None


@dataclass
class PoseSpec:
    """O que uma animação pede ao solver, antes de virar rotações de osso."""
    rot: dict = field(default_factory=dict)          # osso -> Quaternion local (FK)
    hips_shift: Vector = field(default_factory=Vector)
    ik: dict = field(default_factory=dict)           # osso de cima -> IKGoal
    world_rot: dict = field(default_factory=dict)    # osso -> orientação absoluta (pés no chão)


@dataclass
class Solution:
    """Pose resolvida: rotações locais, orientações absolutas e posições das cabeças dos ossos."""
    local: dict
    world: dict
    head: dict
    hips_shift: Vector

    def tail(self, name):
        b = BONE_MAP[name]
        return self.head[name] + self.world[name] @ (b.tail - b.head)

    def midpoint(self, name):
        return (self.head[name] + self.tail(name)) * 0.5


def two_bone_joint(origin, target, upper_len, lower_len, pole):
    """Posição do cotovelo/joelho e do fim da cadeia para um alvo (limitado ao alcance dos ossos)."""
    reach = target - origin
    dist = reach.length
    if dist < 1e-6:
        reach, dist = Vector((0.0, 0.0, -1.0)), 1.0
    forward = reach / dist
    dist = min(max(dist, abs(upper_len - lower_len) + 1e-3), upper_len + lower_len - 1e-3)
    along = (upper_len ** 2 - lower_len ** 2 + dist ** 2) / (2.0 * dist)
    height = max(upper_len ** 2 - along ** 2, 0.0) ** 0.5
    bend = pole - forward * pole.dot(forward)
    if bend.length < 1e-6:
        bend = Vector((0.0, 1.0, 0.0)) - forward * forward.y
    bend.normalize()
    return origin + forward * along + bend * height, origin + forward * dist


def _solve_chain(origin, goal, upper, lower):
    """Rotações absolutas dos dois ossos de uma cadeia com IK."""
    pole = goal.pole if goal.pole is not None else IK_CHAINS[upper.name][1]
    joint, end = two_bone_joint(origin, goal.target, upper.length, lower.length, pole)
    upper_world = upper.rest_dir.rotation_difference((joint - origin).normalized())
    lower_world = lower.rest_dir.rotation_difference((end - joint).normalized())
    return upper_world, lower_world


def _limit_bend(relative):
    """Limita a dobra de uma orientação imposta em relação ao pai (o tornozelo não vira 100 graus)."""
    angle = relative.angle
    if angle <= MAX_FORCED_BEND:
        return relative
    return IDENTITY.slerp(relative, MAX_FORCED_BEND / angle)


def solve(spec):
    """Resolve a `PoseSpec` inteira: FK do tronco, IK das cadeias pedidas, FK do resto."""
    local, world, head = {}, {}, {}
    forced = {}
    for b in BONES:
        name = b.name
        if b.parent is None:
            parent_world, origin = IDENTITY, b.head + spec.hips_shift
        else:
            parent_world = world[b.parent]
            parent = BONE_MAP[b.parent]
            origin = head[b.parent] + parent_world @ (b.head - parent.head)
        head[name] = origin

        if name in forced:
            absolute = forced[name]
        elif name in spec.world_rot:
            absolute = parent_world @ _limit_bend(parent_world.inverted() @ spec.world_rot[name])
        elif name in spec.ik:
            lower_name = IK_CHAINS[name][0]
            absolute, forced[lower_name] = _solve_chain(origin, spec.ik[name], b, BONE_MAP[lower_name])
        else:
            absolute = parent_world @ spec.rot.get(name, IDENTITY)
        world[name] = absolute
        local[name] = parent_world.inverted() @ absolute
    return Solution(local, world, head, spec.hips_shift.copy())


def forward(local, hips_shift):
    """Cinemática direta a partir de rotações locais já prontas (usada ao misturar poses)."""
    return solve(PoseSpec(rot=local, hips_shift=hips_shift))


def blend_local(a, b, weight):
    """Mistura duas poses locais (slerp por osso)."""
    if weight <= 0.0:
        return {k: v.copy() for k, v in a.items()}
    if weight >= 1.0:
        return {k: v.copy() for k, v in b.items()}
    return {name: a[name].slerp(b[name], weight) for name in a}
