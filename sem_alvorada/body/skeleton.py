"""Esqueleto do corpo do jogador (Daniel Harper, 1,80 m): ossos, repouso e geometria das mãos.

Matemática pura (só `mathutils`). A pose de repouso é a de modelagem: em pé, braços soltos
ao lado do corpo com os cotovelos levemente dobrados e as palmas voltadas para as coxas.

Convenção das rotações (a mesma do Alto, `entity/skeleton.py`): cada osso guarda uma rotação
`Q` RELATIVA AO PAI, escrita nos eixos do repouso do pai (X = direita, Y = frente, Z = cima, girados
junto com o pai). Quem escreve a pose nunca se preocupa com o "roll" dos ossos do Blender: o
`BodyRig` converte `Q` para a rotação local do pose bone por conjugação, `B = R^-1 Q R`.

Espaço do corpo: origem no chão, sob o quadril; X direita, Y frente, Z cima.
"""
from dataclasses import dataclass

import bpy  # noqa: F401  (no pacote pip, importar bpy é o que torna `mathutils` importável)
from mathutils import Matrix, Quaternion, Vector

IDENTITY = Quaternion((1.0, 0.0, 0.0, 0.0))

# --------------------------------------------------------------------------
# Medidas (m). Referência: homem de 1,80 m, magro. Olho a 1,65 m (C.PLAYER_EYE_STAND).
# --------------------------------------------------------------------------
HEIGHT = 1.80
EYE_Z = 1.65
ANKLE_Z = 0.085
KNEE_Z = 0.50
HIP_Z = 0.93
LEG_X = 0.088
PELVIS_Z = 0.955
C7_Z = 1.45
SHOULDER = Vector((0.172, 0.005, 1.42))
CLAVICLE_HEAD = Vector((0.025, 0.035, 1.46))
UPPER_ARM_LEN = 0.335
FOREARM_LEN = 0.265
HAND_LEN = 0.098                 # do punho à linha dos nós dos dedos
PALM_SURFACE = 0.012             # do plano médio da mão até a superfície da palma
PALM_CENTER_F = 0.055            # do punho ao centro da palma, ao longo dos dedos
# o olho fica à frente do eixo da coluna e acima da base do pescoço; 6,5 cm (e não os 9 cm de uma cabeça real)
# deixam o peito 4 a 5 cm à frente do olho, e assim olhar para baixo mostra camisa, barriga e cinto
EYE_FROM_C7 = Vector((0.0, 0.065, EYE_Z - C7_Z))

FINGERS = ("Index", "Middle", "Ring", "Pinky")
PHALANX = {"Index": (0.044, 0.025, 0.021), "Middle": (0.048, 0.028, 0.022),
           "Ring": (0.045, 0.026, 0.021), "Pinky": (0.036, 0.019, 0.018)}
MCP_FORWARD = {"Index": 0.093, "Middle": 0.096, "Ring": 0.091, "Pinky": 0.081}      # punho -> nó, ao longo dos dedos
MCP_LATERAL = {"Index": 0.0305, "Middle": 0.0105, "Ring": -0.0105, "Pinky": -0.0295}  # + = lado do polegar
THUMB_LEN = (0.048, 0.034, 0.028)         # metacarpo, falange proximal, falange distal
SIDES = ("L", "R")


def side_sign(side):
    """R fica em +X: o corpo olha para +Y, então a direita dele é +X."""
    return 1.0 if side == "R" else -1.0


@dataclass(frozen=True)
class BoneDef:
    name: str
    parent: str | None
    head: Vector
    tail: Vector
    deform: bool = True

    @property
    def length(self):
        return (self.tail - self.head).length

    @property
    def rest_dir(self):
        return (self.tail - self.head).normalized()


def mirror_x(vector):
    return Vector((-vector.x, vector.y, vector.z))


# --------------------------------------------------------------------------
# Braço e mão no repouso (lado direito; o esquerdo é o espelho)
# --------------------------------------------------------------------------
def _right_arm():
    upper_dir = Vector((0.22, -0.02, -0.975)).normalized()
    elbow = SHOULDER + upper_dir * UPPER_ARM_LEN
    fore_dir = Vector((0.10, 0.28, -0.955)).normalized()
    wrist = elbow + fore_dir * FOREARM_LEN
    middle = elbow + fore_dir * (FOREARM_LEN * 0.5)
    return elbow, middle, wrist


def _hand_basis(wrist_dir, palm_hint):
    """(F, p, T): dedos, normal da palma (para fora dela) e lado do polegar."""
    f = wrist_dir.normalized()
    p = (palm_hint - f * palm_hint.dot(f)).normalized()
    t = f.cross(p).normalized()
    return f, p, t


_ELBOW_R, _MIDDLE_R, _WRIST_R = _right_arm()
_HAND_DIR_R = Vector((0.05, 0.28, -0.958)).normalized()
# a palma do lado direito olha para o corpo (-X)
_F_R, _P_R, _T_R = _hand_basis(_HAND_DIR_R, Vector((-1.0, 0.0, 0.0)))


def hand_frame(side):
    """(F, p, T) do repouso da mão do lado `side`, em espaço do corpo. O esquerdo é o espelho do direito."""
    if side == "R":
        return _F_R.copy(), _P_R.copy(), _T_R.copy()
    return mirror_x(_F_R), mirror_x(_P_R), mirror_x(_T_R)


def rest_basis(side):
    """Matriz cujas colunas são (F, p, F x p): leva o referencial da mão (dedos, palma, resto) ao espaço do corpo."""
    f, p, _t = hand_frame(side)
    return Matrix((f, p, f.cross(p))).transposed()


def palm_offset(side):
    """Do punho ao centro da superfície da palma, no repouso (espaço do corpo)."""
    f, p, _t = hand_frame(side)
    return f * PALM_CENTER_F + p * PALM_SURFACE


# Orientação neutra da mão no espaço da câmera (X direita, Y cima, -Z frente): dedos para a frente,
# palma para baixo, polegar para o centro do corpo. Mesma para as duas mãos.
NEUTRAL_HAND_CAM = Matrix((Vector((0.0, 0.0, -1.0)), Vector((0.0, -1.0, 0.0)), Vector((-1.0, 0.0, 0.0)))).transposed()


def _build_bones():
    bones = []

    def add(name, parent, head, tail, deform=True):
        bones.append(BoneDef(name, parent, Vector(head), Vector(tail), deform))

    add("Hips", None, (0.0, -0.01, PELVIS_Z), (0.0, -0.01, PELVIS_Z + 0.07))
    add("Spine1", "Hips", (0.0, -0.01, 1.025), (0.0, 0.0, 1.16))
    add("Spine2", "Spine1", (0.0, 0.0, 1.16), (0.0, 0.005, 1.30))
    add("Spine3", "Spine2", (0.0, 0.005, 1.30), (0.0, 0.01, C7_Z))
    add("Chest", "Spine2", (0.0, 0.0, 1.32), (0.0, 0.12, 1.32))        # folha: respiração
    add("Neck", "Spine3", (0.0, 0.01, C7_Z), (0.0, 0.025, 1.58))

    for side in SIDES:
        sx = side_sign(side)
        mirror = (lambda v: v) if side == "R" else mirror_x

        add(f"Clavicle.{side}", "Spine3", mirror(CLAVICLE_HEAD), mirror(SHOULDER + Vector((-0.012, 0.0, 0.0))))
        add(f"UpperArm.{side}", f"Clavicle.{side}", mirror(SHOULDER), mirror(_ELBOW_R))
        add(f"Forearm.{side}", f"UpperArm.{side}", mirror(_ELBOW_R), mirror(_MIDDLE_R))
        add(f"ForearmRoll.{side}", f"Forearm.{side}", mirror(_MIDDLE_R), mirror(_WRIST_R))
        wrist = mirror(_WRIST_R)
        f, p, t = hand_frame(side)
        add(f"Hand.{side}", f"ForearmRoll.{side}", wrist, wrist + f * HAND_LEN)

        for finger in FINGERS:
            knuckle = wrist + f * MCP_FORWARD[finger] + t * MCP_LATERAL[finger]
            parent = f"Hand.{side}"
            head = knuckle
            for index, length in enumerate(PHALANX[finger], start=1):
                tail = head + f * length
                add(f"{finger}{index}.{side}", parent, head, tail)
                parent, head = f"{finger}{index}.{side}", tail

        cmc = wrist + f * 0.022 + t * 0.020 + p * 0.002
        directions = (_thumb_dir(f, p, t, 0), _thumb_dir(f, p, t, 1), _thumb_dir(f, p, t, 2))
        parent, head = f"Hand.{side}", cmc
        for index, (direction, length) in enumerate(zip(directions, THUMB_LEN)):
            tail = head + direction * length
            add(f"Thumb{index}.{side}", parent, head, tail)
            parent, head = f"Thumb{index}.{side}", tail

        leg_x = sx * LEG_X
        add(f"Thigh.{side}", "Hips", (leg_x, 0.0, HIP_Z), (leg_x, 0.01, KNEE_Z))
        add(f"Shin.{side}", f"Thigh.{side}", (leg_x, 0.01, KNEE_Z), (leg_x, 0.0, ANKLE_Z))
        add(f"Foot.{side}", f"Shin.{side}", (leg_x, 0.0, ANKLE_Z), (leg_x, 0.160, 0.040))
        add(f"Toe.{side}", f"Foot.{side}", (leg_x, 0.160, 0.040), (leg_x, 0.265, 0.035))
    return bones


def _thumb_dir(f, p, t, index):
    """Direção de cada osso do polegar relaxado: sai do lado da palma, avança e se aproxima dos outros dedos."""
    mix = ((0.38, 0.88, 0.22), (0.62, 0.70, 0.30), (0.74, 0.55, 0.38))[index]
    return (f * mix[0] + t * mix[1] + p * mix[2]).normalized()


BONES = _build_bones()                      # pais sempre antes dos filhos
BONE_MAP = {b.name: b for b in BONES}
BONE_ORDER = [b.name for b in BONES]
BONE_INDEX = {name: i for i, name in enumerate(BONE_ORDER)}
PARENT_INDEX = [BONE_INDEX[b.parent] if b.parent else -1 for b in BONES]
CHILD_OFFSET = [b.head - (BONES[PARENT_INDEX[i]].head if PARENT_INDEX[i] >= 0 else Vector()) for i, b in enumerate(BONES)]


def finger_bones(side, finger):
    """Nomes das falanges de um dedo (polegar: metacarpo e duas falanges)."""
    if finger == "Thumb":
        return [f"Thumb{i}.{side}" for i in range(3)]
    return [f"{finger}{i}.{side}" for i in range(1, 4)]


FINGER_NAMES = ("Thumb",) + FINGERS      # polegar ao mindinho: a ordem de `curls`

def hinge_axis(chord, bend):
    """Normal do plano de um membro dobrado: o eixo do cotovelo ou joelho."""
    return chord.cross(bend).normalized()


def frame_matrix(direction, hinge):
    """Referencial de um osso: Y ao longo do osso, X na dobradiça, Z completando."""
    y = direction.normalized()
    x = (hinge - y * hinge.dot(y)).normalized()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


# Cadeias de dois ossos resolvidas por IK: osso de cima -> (osso de baixo, osso cuja cabeça é o fim da cadeia)
IK_CHAINS = {}
for _side in SIDES:
    IK_CHAINS[f"UpperArm.{_side}"] = (f"Forearm.{_side}", f"Hand.{_side}")
    IK_CHAINS[f"Thigh.{_side}"] = (f"Shin.{_side}", f"Foot.{_side}")


def rest_hinge(upper_name):
    """Eixo da dobradiça (cotovelo/joelho) no repouso, no espaço do corpo."""
    lower_name, end_name = IK_CHAINS[upper_name]
    shoulder, elbow, wrist = BONE_MAP[upper_name].head, BONE_MAP[lower_name].head, BONE_MAP[end_name].head
    chord = wrist - shoulder
    unit = chord.normalized()
    bend = (elbow - shoulder) - unit * (elbow - shoulder).dot(unit)
    return hinge_axis(unit, bend.normalized())


HINGE_REST = {name: rest_hinge(name) for name in IK_CHAINS}
