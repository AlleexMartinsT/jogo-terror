"""Pegadas por contato: os dedos fecham sobre a malha do item, junta por junta, e param quando tocam.

O corpo tem cinco curls por mão (`fingers`), e uma curva fixa de curls não sabe onde o item está: um dedo atravessava o
cano ou ficava no ar (medido: 9 a 12 mm de penetração e até 21 mm de folga na lanterna). Aqui a posição do item na mão
e a malha dele (BVH) decidem os ângulos:

  * `HandSkin` leva os vértices de pele de cada osso da mão (a mesma malha do corpo, no repouso) junto com as falanges,
    então o teste de contato é feito na pele e não num cilindro de mentira;
  * `close_finger`: cada dedo fecha da pré-forma aberta até o padrão de uma pegada real, as três juntas juntas, na
    proporção do padrão (MCP, PIP, DIP). A falange que tocar a malha trava a junta que a move e todas as de trás dela;
    as juntas da frente continuam até tocar também (o dedo se enrola no cano). O contato é achado por bisseção, então a
    folga final é de centésimos de milímetro e nenhuma falange entra no item;
  * `reach_goal`: o polegar vai a uma folga dada de uma malha (pairando sobre o interruptor, ou tocando uma face);
  * `fit_grip`: ajusta onde a mão fica em relação ao item (seis graus de liberdade, perto do ponto de partida) para a
    palma encostar sem atravessar e os dedos fecharem com contato; roda offline (`pegadas gerar`) e grava
    `sem_alvorada/grasp_data.py`, que o jogo só lê;
  * `measure_skin` mede o resultado na malha de pele de verdade (a malha do corpo já deformada pelo esqueleto), parte
    por parte: a penetração máxima e a folga mínima, em milímetros.

Nada aqui escreve na cena; só o que mede lê a malha avaliada.
"""
import math
from dataclasses import dataclass, field

import bpy  # noqa: F401 - `mathutils` só existe depois deste import
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import fingers as F
from . import skeleton as S

BISECTIONS = 14
CLOSE_STEPS = 36

# Padrão de uma pegada de força num cilindro fino (curls das juntas MCP, PIP, DIP, fração do máximo da junta). A
# tomografia de Shimawaki et al. (2019) mede, num cilindro de 60 mm, MCP 40, PIP 48 e DIP 35 graus no indicador e 46, 48 e
# 35 no médio, com mais flexão quanto mais fino o cilindro (a lanterna tem 37 mm). O padrão aqui é o FIM do curso: o
# contato para antes. ESTIMADO: de 60 para 37 mm, +20% de flexão.
POWER_TARGET = {"Index": (0.70, 0.82, 0.66), "Middle": (0.72, 0.82, 0.66), "Ring": (0.72, 0.82, 0.66), "Pinky": (0.74, 0.84, 0.66)}
PINCH_TARGET = {"Index": (0.55, 0.62, 0.50), "Middle": (0.58, 0.64, 0.52), "Ring": (0.60, 0.66, 0.54), "Pinky": (0.60, 0.66, 0.54)}
CUP_TARGET = {"Index": (0.50, 0.58, 0.44), "Middle": (0.54, 0.60, 0.46), "Ring": (0.56, 0.62, 0.48), "Pinky": (0.58, 0.64, 0.50)}
PREFORM = (0.10, 0.12, 0.10)         # dedo quase esticado: de onde a mão parte para fechar
THUMB_PREFORM = (0.30, 0.25, 0.25)
SKIN_POINTS = {"Hand": 100000, "Finger": 100000, "Thumb": 100000}      # todos os vértices: com amostra rala o dedo "entrava" onde nenhum ponto olhava


@dataclass
class Grasp:
    """O resultado de uma pegada: curls por junta (polegar ao mindinho, base à ponta) de uma mão que segura `kind`."""
    kind: str
    side: str
    closed: list                       # [5][3]: fechada no item, sem penetração
    preform: list                      # [5][3]: aberta antes de fechar (nenhuma falange toca o item)
    pressed: list = None               # [3]: só o polegar da lanterna, com o interruptor apertado
    touches: dict = field(default_factory=dict)      # dedo -> (falange que parou, folga em mm)

    def blend(self, closure):
        """[5][3] com cada dedo entre a pré-forma e a pegada fechada (`closure`: cinco valores de 0 a 1)."""
        return [[a + (b - a) * min(1.0, max(0.0, u)) for a, b in zip(row_open, row_closed)]
                for row_open, row_closed, u in zip(self.preform, self.closed, closure)]


# ---------------------------------------------------------------------------
# A pele da mão e a cinemática dos dedos
# ---------------------------------------------------------------------------
class HandSkin:
    """Vértices de pele da mão de um lado, no repouso. `palm`: pontos relativos ao punho (palma e dorso); `bones[nome]`:
    pontos relativos à cabeça do osso (falanges e polegar). Cada vértice vai para o osso de maior peso (acima de 0,5)."""

    def __init__(self, body_obj, side):
        self.side = side
        wrist = Vector(S.BONE_MAP[f"Hand.{side}"].head)
        valid = {f"Hand.{side}"} | {bone for finger in S.FINGER_NAMES for bone in S.finger_bones(side, finger)}
        names = {g.index: g.name for g in body_obj.vertex_groups}
        grouped = {}
        for vertex in body_obj.data.vertices:
            best = max(vertex.groups, key=lambda g: g.weight, default=None)
            if best is None or best.weight <= 0.5 or names.get(best.group) not in valid:
                continue
            grouped.setdefault(names[best.group], []).append(vertex.co.copy())
        self.palm = _thin(grouped.get(f"Hand.{side}", []), SKIN_POINTS["Hand"], wrist)
        self.bones = {}
        for finger in S.FINGER_NAMES:
            for bone in S.finger_bones(side, finger):
                count = SKIN_POINTS["Thumb" if finger == "Thumb" else "Finger"]
                self.bones[bone] = _thin(grouped.get(bone, []), count, Vector(S.BONE_MAP[bone].head))


def _thin(points, count, origin):
    if len(points) > count:
        stride = len(points) / count
        points = [points[int(i * stride)] for i in range(count)]
    return [p - origin for p in points]


class HandKinematics:
    """Falanges e pele de uma mão no referencial do punho em repouso (espaço do corpo, origem no punho)."""

    def __init__(self, side, skin=None):
        self.side = side
        self.skin = skin
        self.wrist = Vector(S.BONE_MAP[f"Hand.{side}"].head)
        self.bones = {name: S.finger_bones(side, name) for name in S.FINGER_NAMES}
        self.rest_basis_inverse = S.rest_basis(side).inverted()
        self.palm_offset = S.palm_offset(side)

    def frames(self, finger, row):
        """[(cabeça, rotação 3x3)] das três falanges de `finger` com `row` = curls das três juntas."""
        quats = F.thumb_quaternions(self.side, row) if finger == "Thumb" else F.finger_quaternions(self.side, finger, row)
        world, head, previous, out = None, None, None, []
        for name, q in zip(self.bones[finger], quats):
            bone = S.BONE_MAP[name]
            if head is None:
                head, world = bone.head - self.wrist, q.to_matrix()
            else:
                head = head + world @ (bone.head - previous.head)
                world = world @ q.to_matrix()
            out.append((head.copy(), world.copy()))
            previous = bone
        return out

    def chain(self, finger, row):
        """[(cabeça, ponta)] das falanges (sem a pele), no referencial do punho."""
        return [(head, head + world @ (S.BONE_MAP[name].tail - S.BONE_MAP[name].head))
                for (head, world), name in zip(self.frames(finger, row), self.bones[finger])]

    def skin_points(self, finger, row, to_item):
        """Pele de cada falange (uma lista de pontos por falange) no referencial do item."""
        return [[to_item @ (head + world @ p) for p in self.skin.bones[name]]
                for (head, world), name in zip(self.frames(finger, row), self.bones[finger])]

    def palm_points(self, to_item):
        return [to_item @ p for p in self.skin.palm]

    def to_item(self, grip_matrix):
        """Matriz que leva um ponto relativo ao punho (repouso) ao referencial do item, para a mão em `grip_matrix`."""
        rotation = grip_matrix.to_3x3() @ S.NEUTRAL_HAND_CAM @ self.rest_basis_inverse
        return Matrix.Translation(grip_matrix.translation) @ rotation.to_4x4() @ Matrix.Translation(-self.palm_offset)


# ---------------------------------------------------------------------------
# A malha do item
# ---------------------------------------------------------------------------
class ItemShape:
    """BVH de um item (um ou mais objetos) no referencial `frame` (padrão: o mundo). `sheet`: folha fina, vista dos dois
    lados. `materials`: só os polígonos desses materiais entram (as peças internas e duplicadas de um modelo, como o
    refletor da lanterna, dão sinal errado de dentro e fora)."""
    INSIDE_LIMIT = 0.012             # m: mais longe que isto da superfície, o sinal da normal não vale como "dentro"

    def __init__(self, objects, frame=None, sheet=False, materials=None):
        self.sheet = sheet
        vertices, polygons = [], []
        for obj in objects:
            matrix = obj.matrix_world if frame is None else frame @ obj.matrix_world
            names = [m.name if m else "" for m in obj.data.materials]
            base = len(vertices)
            vertices += [matrix @ v.co for v in obj.data.vertices]
            for p in obj.data.polygons:
                if materials is None or (p.material_index < len(names) and names[p.material_index] in materials):
                    polygons.append(tuple(base + i for i in p.vertices))
        self.tree = BVHTree.FromPolygons(vertices, polygons)

    def signed_distance(self, point):
        """Distância assinada do ponto à malha (negativa dentro). Numa folha o sinal é o lado: positivo à frente."""
        location, normal, _index, distance = self.tree.find_nearest(point)
        if location is None:
            return 1.0
        offset = point - location
        along = offset.dot(normal)
        if self.sheet:
            return along if (offset - normal * along).length < 2e-3 else distance
        return distance if along >= 0.0 or distance > self.INSIDE_LIMIT else -distance

    def clearance(self, points, side=1.0):
        """Menor distância assinada de uma lista de pontos (numa folha, `side` escolhe o lado: 1 à frente, -1 atrás)."""
        if not points:
            return 1.0
        if self.sheet:
            return min(side * self.signed_distance(p) for p in points)
        return min(self.signed_distance(p) for p in points)


# ---------------------------------------------------------------------------
# Fechar um dedo até o contato
# ---------------------------------------------------------------------------
def close_finger(kinematics, finger, to_item, shape, start, target, side=1.0, steps=CLOSE_STEPS):
    """Fecha `finger` da pré-forma `start` rumo ao padrão `target` (curls das três juntas), parando no contato.

    Devolve (juntas, [folga de cada falange em m], índice da falange que parou ou None)."""
    frozen = [None, None, None]
    stopped = None

    def config(u):
        return [frozen[j] if frozen[j] is not None else start[j] + u * (target[j] - start[j]) for j in range(3)]

    def clearances(row):
        return [shape.clearance(points, side) for points in kinematics.skin_points(finger, row, to_item)]

    u = 0.0
    while u < 1.0 and any(f is None for f in frozen):
        ahead = min(1.0, u + 1.0 / steps)
        if min(clearances(config(ahead))) >= 0.0:
            u = ahead
            continue
        low, high = u, ahead
        for _ in range(BISECTIONS):
            middle = 0.5 * (low + high)
            if min(clearances(config(middle))) >= 0.0:
                low = middle
            else:
                high = middle
        row_high = clearances(config(high))
        touching = [k for k in range(3) if row_high[k] < 0.0 and frozen[k] is None]
        k = max(touching) if touching else 2
        row_low = config(low)
        for j in range(k + 1):
            if frozen[j] is None:
                frozen[j] = row_low[j]
        stopped = k
        u = low
    final = config(min(u, 1.0))
    return final, clearances(final), stopped


def reach_goal(kinematics, finger, to_item, shape, goal_shape, hover, start, side=1.0, goal_side=1.0):
    """Ajuste de três ângulos para a pele da falange de ponta chegar a `hover` m da malha `goal_shape` (negativo = dentro),
    sem atravessar `shape`. Busca por coordenadas com passo que encolhe. Devolve (juntas, erro em m, penetração em m)."""

    def cost(row):
        parts = kinematics.skin_points(finger, row, to_item)
        near = [shape.clearance(points, side) for points in parts]
        goal = goal_shape.clearance(parts[2], goal_side)
        penalty = sum(max(0.0, -c) for c in near) * 60.0
        keep = sum((a - b) ** 2 for a, b in zip(row, start)) * 0.0006
        return abs(goal - hover) + penalty + keep

    row = list(start)
    best = cost(row)
    step = 0.30
    for _ in range(20):
        improved = False
        for j in range(3):
            for sign in (1.0, -1.0):
                trial = list(row)
                trial[j] = min(1.0, max(0.0, trial[j] + sign * step))
                value = cost(trial)
                if value < best - 1e-8:
                    row, best, improved = trial, value, True
        if not improved:
            step *= 0.55
    parts = kinematics.skin_points(finger, row, to_item)
    penetration = max(0.0, -min(shape.clearance(points, side) for points in parts))
    return row, abs(goal_shape.clearance(parts[2], goal_side) - hover), penetration


# ---------------------------------------------------------------------------
# A pegada de cada item
# ---------------------------------------------------------------------------
@dataclass
class Role:
    """O que cada dedo faz numa pegada. `power`, `pinch` e `cup` fecham por contato rumo ao padrão de força, de pinça ou de
    concha; `free` fica relaxado (abre se atravessar o item). `thumb`: "contact" (o polegar toca o item), "hover" (paira
    sobre `thumb_goal`) ou "free". Numa folha (`sheet`) o polegar toca a face da frente e os dedos a de trás."""
    power: tuple = ()
    pinch: tuple = ()
    cup: tuple = ()
    free: dict = field(default_factory=dict)
    thumb: str = "contact"
    thumb_hover: float = 0.0
    thumb_free: tuple = (0.34, 0.30, 0.30)
    sheet: bool = False
    palm_gap: float = None               # m: alvo da folga da palma ao item (None: só não pode atravessar)


def free_row(curl):
    """Dedo relaxado: as três juntas dobradas por `curl`, a ponta um pouco menos."""
    return [curl, curl * 1.05, curl * 0.85]


def solve(kind, side, grip_matrix, shape, role, skin, goal_shape=None, press_shape=None, press_depth=0.0010):
    """Calcula a `Grasp` de `kind`: `shape` é o item no mesmo referencial de `grip_matrix` (a mão no item)."""
    kinematics = HandKinematics(side, skin)
    to_item = kinematics.to_item(grip_matrix)
    closed = [[0.0] * 3 for _ in range(5)]
    preform = [list(PREFORM) for _ in range(5)]
    touches = {}
    behind = -1.0 if role.sheet else 1.0
    for index, finger in enumerate(S.FINGER_NAMES):
        if finger == "Thumb":
            continue
        mode = POWER_TARGET if finger in role.power else PINCH_TARGET if finger in role.pinch else CUP_TARGET if finger in role.cup else None
        if mode is not None:
            row, clear, stopped = close_finger(kinematics, finger, to_item, shape, PREFORM, mode[finger], side=behind)
            closed[index] = row
            touches[finger] = (stopped, max(0.0, min(clear)) * 1000.0, max(0.0, -min(clear)) * 1000.0)
        else:
            row = list(role.free.get(finger, free_row(0.40)))
            while max(row) > 0.0 and any(shape.clearance(points, behind) < 0.0
                                         for points in kinematics.skin_points(finger, row, to_item)):
                row = [max(0.0, v - 0.03) for v in row]
            closed[index] = row
    pressed = None
    if role.thumb == "free":
        closed[0] = list(role.thumb_free)
    else:
        target_shape = goal_shape or shape
        closed[0], error, penetration = reach_goal(kinematics, "Thumb", to_item, shape, target_shape, role.thumb_hover, THUMB_PREFORM)
        touches["Thumb"] = (2, error * 1000.0, penetration * 1000.0)
        if role.thumb == "hover" and press_depth is not None:
            pressed = reach_goal(kinematics, "Thumb", to_item, press_shape or shape, target_shape, -press_depth, closed[0])[0]
    preform[0] = list(THUMB_PREFORM)
    return Grasp(kind, side, closed, preform, pressed, touches)


def grip_from_matrix(matrix):
    """(posição, direção dos dedos, direção da palma) de uma mão em `matrix` (a forma que `handclips.Grip` recebe)."""
    target = matrix.to_3x3() @ S.NEUTRAL_HAND_CAM
    return tuple(matrix.translation), tuple(target.col[0]), tuple(target.col[1])


def matrix_from_grip(position, fingers, palm):
    f = Vector(fingers).normalized()
    p = Vector(palm)
    p = (p - f * p.dot(f)).normalized()
    rotation = Matrix((f, p, f.cross(p))).transposed() @ S.NEUTRAL_HAND_CAM.inverted()
    matrix = rotation.to_4x4()
    matrix.translation = Vector(position)
    return matrix


def fit_grip(kind, side, start_matrix, shape, role, skin, goal_shape=None, rounds=9, move=0.012, turn=18.0, scan=None,
             press_shape=None, extra=None, candidates=3):
    """Mexe a mão em volta de `start_matrix` (no referencial do item) até a palma encostar sem entrar e os dedos fecharem
    com contato. Busca por coordenadas, seis parâmetros, passo que encolhe; um prior pequeno segura a mão perto do ponto de
    partida. `scan` = (eixo, graus...) gira antes a mão em torno de um eixo que passa pela origem do item (o cano da
    lanterna): os `candidates` melhores giros seguem para o ajuste fino e vence o de menor custo. `extra(matriz)` soma uma
    penalidade de fora (o braço precisa alcançar a mão: `pegadas.verificador_de_braco`).
    Devolve (matriz, Grasp, custo, giro do scan em graus)."""
    kinematics = HandKinematics(side, skin)
    palm_side = -1.0 if role.sheet else 1.0

    def evaluate(matrix, final=False):
        clearance = shape.clearance(kinematics.palm_points(kinematics.to_item(matrix)), palm_side)
        total = 0.0
        if clearance < 0.0:
            total += 800.0 * clearance * clearance
        elif role.palm_gap is not None:
            total += 4000.0 * (clearance - role.palm_gap) ** 2
        grasp = solve(kind, side, matrix, shape, role, skin, goal_shape, press_shape, 0.0010 if final else None)
        for finger, (stopped, gap_mm, pen_mm) in grasp.touches.items():
            wanted = finger in role.power or finger in role.pinch or finger in role.cup or finger == "Thumb"
            if pen_mm > 0.01:                           # entra no item (na pré-forma, ou o polegar sem saída)
                total += (pen_mm / 1000.0) ** 2 * 8000.0
            if wanted and (stopped is None or finger == "Thumb"):
                total += (gap_mm / 1000.0) ** 2 * (2000.0 if finger == "Thumb" else 1200.0)
        if extra is not None:
            total += extra(matrix)
        return total, grasp

    def local(origin):
        rotation0, position0 = origin.to_3x3(), origin.translation.copy()

        def build(params):
            matrix = (Euler(tuple(math.radians(a) for a in params[3:]), "XYZ").to_matrix() @ rotation0).to_4x4()
            matrix.translation = position0 + Vector(params[:3])
            return matrix

        def cost(params):
            value, grasp = evaluate(build(params))
            return value + 60.0 * sum(v * v for v in params[:3]) + 1.5e-5 * sum(v * v for v in params[3:]), grasp

        params, steps = [0.0] * 6, [move] * 3 + [turn] * 3
        best, _ = cost(params)
        for _ in range(rounds):
            improved = False
            for i in range(6):
                for sign in (1.0, -1.0):
                    trial = list(params)
                    trial[i] += sign * steps[i]
                    value, _ = cost(trial)
                    if value < best - 1e-9:
                        best, params, improved = value, trial, True
            if not improved:
                steps = [v * 0.5 for v in steps]
        matrix = build(params)
        value, grasp = evaluate(matrix, final=True)
        return matrix, grasp, value + 60.0 * sum(v * v for v in params[:3]) + 1.5e-5 * sum(v * v for v in params[3:])

    if scan is None:
        return (*local(start_matrix), 0.0)
    axis, *angles = scan
    ranked = sorted(((evaluate(Matrix.Rotation(math.radians(a), 4, axis) @ start_matrix)[0], a) for a in angles))
    best = None
    for _score, degrees in ranked[:candidates]:
        matrix, grasp, value = local(Matrix.Rotation(math.radians(degrees), 4, axis) @ start_matrix)
        if best is None or value < best[2]:
            best = (matrix, grasp, value, float(degrees))
    return best


# ---------------------------------------------------------------------------
# Medir na pele de verdade
# ---------------------------------------------------------------------------
PARTS = ("Thumb", "Index", "Middle", "Ring", "Pinky", "Palm")
_PART_OF_GROUP = {}


def _part_of_group(name):
    """"Index2.R" -> ("Index", "R"); "Hand.L" -> ("Palm", "L"); o resto -> None."""
    if name in _PART_OF_GROUP:
        return _PART_OF_GROUP[name]
    result = None
    stem, _, side = name.rpartition(".")
    if side in ("L", "R"):
        if stem == "Hand":
            result = ("Palm", side)
        else:
            for part in PARTS[:5]:
                if stem.startswith(part) and stem[len(part):].isdigit():
                    result = (part, side)
    _PART_OF_GROUP[name] = result
    return result


def skin_parts(body_obj, side):
    """{parte: [índices de vértice]} da malha do corpo, cada vértice na parte do osso de maior peso do lado `side`."""
    groups = {g.index: _part_of_group(g.name) for g in body_obj.vertex_groups}
    parts = {part: [] for part in PARTS}
    for vertex in body_obj.data.vertices:
        best = max(vertex.groups, key=lambda g: g.weight, default=None)
        if best is None:
            continue
        info = groups.get(best.group)
        if info is not None and info[1] == side and best.weight > 0.5:
            parts[info[0]].append(vertex.index)
    return parts


def measure_skin(body_obj, shape, side, skin_vertices=None):
    """Penetração e folga da pele de cada parte da mão contra `shape` (já no mundo), em milímetros.

    {parte: {"pen": penetração máxima, "gap": menor distância (0 se há penetração), "touch": vértices a menos de 1 mm}}.
    Numa folha a penetração é a profundidade do dedo que atravessa para o outro lado."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = body_obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    matrix = evaluated.matrix_world
    skin_vertices = skin_vertices or skin_parts(body_obj, side)
    out = {}
    try:
        for part, indices in skin_vertices.items():
            front, back, nearest, touch = 0.0, 0.0, 1.0, 0
            for index in indices:
                signed = shape.signed_distance(matrix @ mesh.vertices[index].co)
                nearest = min(nearest, abs(signed))
                if abs(signed) < 1e-3:
                    touch += 1
                if shape.sheet:
                    if signed > 0.0:
                        front = max(front, signed if signed < 0.012 else 0.0)
                    else:
                        back = max(back, -signed if -signed < 0.012 else 0.0)
                elif signed < 0.0:
                    front = max(front, -signed)
            depth = min(front, back) if shape.sheet else front
            out[part] = {"pen": depth * 1000.0, "gap": 0.0 if depth > 0.0 else nearest * 1000.0, "touch": touch}
    finally:
        evaluated.to_mesh_clear()
    return out
