"""Biblioteca de clipes das mãos: um gesto único para cada tipo de item, escrito como dados.

Espaço da câmera (metros): X direita, Y cima, -Z frente. Rotações em graus, Euler XYZ, aplicadas a uma mão
neutra com a palma para baixo e os dedos para a frente (-Z); o eixo Z da câmera é, portanto, o eixo dos dedos
(rz = rolar a palma para cima ou para baixo).

Trilhas de uma mão (`side` = "R" ou "L"): `pos`, `rot`, `curl` (5 dedos, 0 aberto .. 1 fechado), `w` (peso do
IK: 0 solta o braço) e `attach` (0 o item ainda está no mundo, 1 está preso à mão). Extras `x.*` movem partes
do item: tampa da lanterna, pilha entrando, dobras do mapa.

Depois do contato o que importa é onde o ITEM aparece na tela (legível no escuro, sem cobrir a mira): essas
chaves são escritas como poses do item e convertidas para a mão pela garra de cada item (`GRIPS`). Antes do
contato a mão é quem lidera e a chave pode ser relativa ao ponto de pegar ao vivo (`space="grasp"`).
"""
import math

import bpy  # noqa: F401 - `mathutils` só existe depois deste import
from mathutils import Euler, Matrix, Vector

from .. import conventions as C
from .handtrack import Clip, Event, Key, Track, number

SIDE_SIGN = {"R": 1.0, "L": -1.0}
OFF_SCREEN = {"R": (0.36, -0.42, -0.14), "L": (-0.36, -0.42, -0.14)}
REACH_LIMIT = 0.60                 # até onde a palma chega à frente do rosto (m)

# Dedos do polegar ao mindinho
OPEN = (0.10, 0.08, 0.08, 0.10, 0.12)
RELAX = (0.30, 0.28, 0.30, 0.34, 0.38)
FLASH_FIST = (0.30, 0.82, 0.88, 0.90, 0.88)       # o polegar fica livre sobre o botão
FLASH_CLICK = (0.62, 0.82, 0.88, 0.90, 0.88)
FLASH_GRAB = (0.62, 0.75, 0.78, 0.80, 0.78)
PINCH = (0.58, 0.62, 0.28, 0.34, 0.40)
CUP = (0.34, 0.40, 0.44, 0.48, 0.52)
HOLD_SHEET = (0.55, 0.58, 0.20, 0.24, 0.30)


# ---------------------------------------------------------------------------
# Matemática de poses
# ---------------------------------------------------------------------------
def pose_matrix(pos, rot_deg):
    matrix = Euler(tuple(math.radians(a) for a in rot_deg), "XYZ").to_matrix().to_4x4()
    matrix.translation = Vector(pos)
    return matrix


def pose_parts(matrix, previous=None):
    euler = matrix.to_euler("XYZ", previous) if previous is not None else matrix.to_euler("XYZ")
    return tuple(matrix.translation), tuple(math.degrees(a) for a in euler), euler


class Grip:
    """Onde a palma fica no referencial do item: `mão = item @ garra`."""

    def __init__(self, pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0)):
        self.matrix = pose_matrix(pos, rot)
        self.inverse = self.matrix.inverted()

    def hand_of(self, item_matrix):
        return item_matrix @ self.matrix

    def item_of(self, hand_matrix):
        return hand_matrix @ self.inverse


# Garras provisórias: palma logo abaixo do item. Afinadas contra a mão do corpo quando ele existe.
GRIPS = {
    C.ITEM_FLASHLIGHT: Grip((0.0, -0.034, 0.012), (0.0, 0.0, 0.0)),
    C.ITEM_KEY: Grip((0.0, 0.010, 0.012), (0.0, 0.0, 0.0)),
    C.ITEM_MAP: Grip((0.030, -0.010, 0.014), (0.0, 0.0, 0.0)),
    C.ITEM_BATTERY: Grip((0.0, -0.022, 0.0), (0.0, 0.0, 180.0)),
    C.ITEM_NOTE: Grip((0.0, -0.040, 0.010), (0.0, 0.0, 0.0)),
}

# Item parado na mão (pose do item no espaço da câmera): (posição, rotação)
HOLD_ITEM = {
    ("R", C.ITEM_FLASHLIGHT): ((0.165, -0.125, -0.28), (0.0, 0.0, 0.0)),
    ("L", C.ITEM_KEY): ((-0.215, -0.085, -0.40), (0.0, 0.0, 0.0)),
    ("L", C.ITEM_MAP): ((-0.290, -0.115, -0.44), (-28.0, 14.0, 6.0)),
    ("L", C.ITEM_BATTERY): ((-0.150, -0.130, -0.34), (-6.0, 90.0, 0.0)),
    ("L", C.ITEM_NOTE): ((-0.170, -0.095, -0.40), (-22.0, 10.0, 4.0)),
}
HOLD_CURL = {C.ITEM_FLASHLIGHT: FLASH_FIST, C.ITEM_KEY: PINCH, C.ITEM_MAP: PINCH, C.ITEM_BATTERY: CUP,
             C.ITEM_NOTE: HOLD_SHEET}
EXTRAS = {"x.cap": 0.0, "x.fold1": 0.0, "x.fold2": 0.0, "x.zoom": 0.0}


FACE_ITEM = {C.ITEM_NOTE: ((-0.010, -0.015, -0.255), (-4.0, 0.0, 0.0))}      # a folha diante do rosto
NEAR_ITEM = {C.ITEM_MAP: ((-0.150, -0.012, -0.255), (-6.0, 6.0, 2.0))}        # o mapa aproximado do rosto
MODE_POSES = {"hold": HOLD_ITEM, "face": {("L", k): v for k, v in FACE_ITEM.items()},
              "near": {("L", k): v for k, v in NEAR_ITEM.items()}}


def hold_hand(side, kind, mode="hold"):
    """Pose da mão (posição, rotação) que segura `kind` parado."""
    item_pos, item_rot = MODE_POSES[mode].get((side, kind), HOLD_ITEM[(side, kind)])
    pos, rot, _ = pose_parts(GRIPS[kind].hand_of(pose_matrix(item_pos, item_rot)))
    return pos, rot


def rest_channels(side, kind=None, mode="hold"):
    """Valores de repouso de todos os canais de uma mão: segurando `kind` ou solta, fora do quadro."""
    if kind is None or (side, kind) not in HOLD_ITEM:
        pos, rot, curl, weight, attach = OFF_SCREEN[side], (0.0, 0.0, 0.0), RELAX, 0.0, 0.0
    else:
        (pos, rot), curl, weight, attach = hold_hand(side, kind, mode), HOLD_CURL[kind], 1.0, 1.0
    return {f"{side}.pos": number(pos), f"{side}.rot": number(rot), f"{side}.curl": number(curl),
            f"{side}.w": number(weight), f"{side}.attach": number(attach)}


# Do referencial do modelo na mão para o do item de mesa (o objeto `Item_*`), para o item aparecer na mão
# exatamente onde estava no mundo. Valores de props/flashlight.py, item_models.py e handheld_*.py (há teste).
def _flashlight_to_model():
    head_end, head_radius, body_radius, grip = 0.2068, 0.0292, 0.0194, 0.073
    lean = math.degrees(math.asin((head_radius - body_radius) / head_end))
    return (pose_matrix((0.0, -head_end / 2, head_radius), (lean, 0.0, 0.0)) @ pose_matrix((0, 0, 0), (-90.0, 0, 0))
            @ pose_matrix((0.0, 0.0, grip), (180.0, 0.0, 0.0)))


KEY_PIVOT = (0.0, 0.0345 * 1.3, 0.0105 * 1.3 / 2)     # no referencial do Item_KEY: o centro da cabeça de borracha
KEY_HAND_SCALE = 0.75
ITEM_TO_MODEL = {
    C.ITEM_FLASHLIGHT: _flashlight_to_model(),
    C.ITEM_KEY: pose_matrix(KEY_PIVOT, (0.0, 0.0, 180.0)),
    C.ITEM_MAP: pose_matrix((-0.177, 0.0, 0.0), (0.0, 0.0, 0.0)),
    C.ITEM_BATTERY: pose_matrix((0.0193, 0.0, 0.0188), (-90.0, 0.0, 0.0)),
    C.ITEM_NOTE: pose_matrix((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
}
WORLD_SCALE = {C.ITEM_KEY: 1.0 / KEY_HAND_SCALE}      # o chaveiro de mesa é maior que o da mão (para ser mirado)


# ---------------------------------------------------------------------------
# Construtor de trilhas de uma mão
# ---------------------------------------------------------------------------
class Path:
    def __init__(self, side, kind):
        self.side, self.kind = side, kind
        self.grip = GRIPS[kind]
        self.channels = {}
        self._euler = None

    def _add(self, name, t, value, stop=False, space="cam"):
        self.channels.setdefault(name, []).append(Key(float(t), number(value), stop, space))

    def hand(self, t, pos, rot, curl=None, w=None, stop=False, space="cam"):
        """Pose da mão. Em `space="grasp"` a posição é somada ao ponto de pegar (a rotação é sempre absoluta)."""
        self._add(f"{self.side}.pos", t, pos, stop, space)
        self._add(f"{self.side}.rot", t, rot, stop)
        if curl is not None:
            self._add(f"{self.side}.curl", t, curl, stop)
        if w is not None:
            self._add(f"{self.side}.w", t, w, stop)
        return self

    def item(self, t, pos, rot, curl=None, w=None, stop=False):
        """Pose do item no espaço da câmera; a mão é derivada pela garra."""
        hand_pos, hand_rot, self._euler = pose_parts(self.grip.hand_of(pose_matrix(pos, rot)), self._euler)
        return self.hand(t, hand_pos, hand_rot, curl, w, stop)

    def curl(self, t, values, stop=False):
        self._add(f"{self.side}.curl", t, values, stop)
        return self

    def weight(self, t, value, stop=False):
        self._add(f"{self.side}.w", t, value, stop)
        return self

    def attach(self, t, value, stop=False):
        self._add(f"{self.side}.attach", t, value, stop)
        return self

    def extra(self, name, t, value, stop=False):
        self._add(f"x.{name}", t, value, stop)
        return self

    def tracks(self):
        return {name: Track(keys) for name, keys in self.channels.items()}


def merge(*paths):
    tracks = {}
    for path in paths:
        tracks.update(path.tracks())
    return tracks


def ev(t, name, arg=None, essential=False):
    return Event(float(t), name, arg, essential)


REACH_PRE = 0.40           # a mão chega acima do item
REACH_GRASP = 0.58         # e desce até ele: é o instante do contato


def reach(path, entry_rot, pre, pre_rot, grasp, grasp_rot, curl, pre_lead=0.0, side_sign=1.0):
    """Mão entrando pelo canto até o ponto de pegar ao vivo (`space="grasp"`): peso do IK sobe nos primeiros
    quadros, a chegada é um arco único sem parada no meio e a descida final é lenta."""
    path.hand(0.00, OFF_SCREEN[path.side], entry_rot, curl, w=0.0)
    path.weight(0.16, 1.0)
    path.hand(REACH_PRE + pre_lead, pre, pre_rot, curl, space="grasp")
    path.hand(REACH_GRASP, grasp, grasp_rot, curl, stop=True, space="grasp")


# ---------------------------------------------------------------------------
# Lanterna: primeira vez (mão direita)
# ---------------------------------------------------------------------------
# Intensidade da luz em cada rajada: (início depois do clique, duração). Três rajadas de queda e retorno,
# com intervalos que encurtam: a lanterna foi usada antes e a carga já não é a de fábrica.
FLICKER_BURSTS = ((0.26, 0.11), (0.66, 0.10), (0.94, 0.09))


def lantern_first():
    """Estende a mão, pega a lanterna desligada, traz ao peito, o polegar clica, a luz pisca e a mão assume."""
    path = Path("R", C.ITEM_FLASHLIGHT)
    hold, hold_rot = HOLD_ITEM[("R", C.ITEM_FLASHLIGHT)]
    chest, chest_rot = (0.075, -0.105, -0.345), (32.0, 11.0, -6.0)
    lift, lift_rot = (0.145, -0.150, -0.370), (14.0, 4.0, 0.0)
    g = REACH_GRASP
    click_at = g + 0.90
    reach(path, (8.0, -12.0, -6.0), (0.0, 0.07, 0.05), (-4.0, 0.0, 0.0), (0.0, 0.018, 0.0), (-14.0, 0.0, 0.0), OPEN)
    path.curl(g + 0.10, FLASH_GRAB)
    path.item(g + 0.38, lift, lift_rot, FLASH_FIST)
    path.item(g + 0.70, chest, chest_rot, FLASH_FIST, stop=True)
    path.curl(click_at - 0.10, FLASH_FIST)
    path.curl(click_at, FLASH_CLICK, stop=True)
    path.curl(click_at + 0.13, FLASH_FIST)
    path.item(click_at - 0.02, chest, chest_rot, stop=True)
    path.item(click_at + 0.05, (chest[0], chest[1] - 0.006, chest[2]), chest_rot)
    path.item(click_at + 0.22, chest, chest_rot, stop=True)
    path.item(click_at + 1.00, chest, chest_rot, stop=True)
    path.item(click_at + 1.50, hold, hold_rot, FLASH_FIST, stop=True)
    path.attach(g, 0.0, stop=True).attach(g + 0.40, 1.0, stop=True)
    events = [ev(0.05, "sound", "hand_reach"), ev(g, "contact", essential=True),
              ev(g, "show", ("R", C.ITEM_FLASHLIGHT), essential=True),
              ev(g + 0.02, "sound", "flash_pickup"), ev(click_at, "light_on", essential=True)]
    events += [ev(click_at + start, "burst", index) for index, (start, _) in enumerate(FLICKER_BURSTS)]
    return Clip("lantern_first", click_at + 1.55, path.tracks(), events,
                meta={"side": "R", "kind": C.ITEM_FLASHLIGHT, "grasp": "R", "world_item": True})


# ---------------------------------------------------------------------------
# Pilha: recolher na palma, olhar, guardar (mão esquerda)
# ---------------------------------------------------------------------------
def battery_pickup():
    path = Path("L", C.ITEM_BATTERY)
    g = REACH_GRASP
    show, show_rot = (-0.105, -0.095, -0.315), (-14.0, 80.0, 4.0)
    near, near_rot = (-0.115, -0.085, -0.290), (-20.0, 76.0, 8.0)
    reach(path, (6.0, 14.0, 8.0), (0.0, 0.06, 0.04), (-6.0, 4.0, 2.0), (0.0, 0.016, 0.0), (-14.0, 2.0, 0.0), OPEN)
    path.curl(g + 0.10, CUP)
    path.item(g + 0.34, (-0.140, -0.125, -0.335), (-10.0, 88.0, 0.0), CUP)
    path.item(g + 0.54, show, show_rot, CUP, stop=True)
    path.item(g + 0.76, near, near_rot, CUP, stop=True)
    path.item(g + 0.96, (-0.190, -0.300, -0.250), (-20.0, 80.0, 10.0), CUP)
    path.weight(g + 0.82, 1.0).weight(g + 1.12, 0.0, stop=True)
    path.attach(g, 0.0, stop=True).attach(g + 0.22, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(g + 0.02, "contact", essential=True),
              ev(g + 0.02, "show", ("L", C.ITEM_BATTERY), essential=True),
              ev(g + 0.92, "hide", "L"), ev(g + 1.08, "sound", "cloth_rustle_1")]
    return Clip("battery_pickup", g + 1.17, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_BATTERY, "grasp": "L", "world_item": True})


# ---------------------------------------------------------------------------
# Chave: erguer o chaveiro e balançar uma vez (mão esquerda)
# ---------------------------------------------------------------------------
def key_pickup():
    path = Path("L", C.ITEM_KEY)
    g = REACH_GRASP
    reach(path, (6.0, 14.0, 8.0), (0.0, 0.06, 0.04), (-6.0, 4.0, 2.0), (0.0, 0.015, 0.0), (-16.0, 2.0, 0.0), OPEN)
    path.curl(g + 0.08, PINCH)
    path.item(g + 0.36, (-0.200, -0.060, -0.360), (0.0, 0.0, 0.0), PINCH)
    path.item(g + 0.54, (-0.150, -0.050, -0.375), (0.0, 0.0, 0.0), PINCH)        # o puxão que faz o chaveiro balançar
    path.item(g + 0.64, (-0.236, -0.062, -0.370), (0.0, 0.0, 0.0), PINCH, stop=True)
    path.item(g + 0.84, (-0.210, -0.075, -0.375), (0.0, 0.0, 0.0), PINCH, stop=True)
    path.item(g + 1.24, (-0.300, -0.330, -0.250), (0.0, 0.0, 0.0), PINCH)
    path.weight(g + 1.12, 1.0).weight(g + 1.42, 0.0, stop=True)
    path.attach(g, 0.0, stop=True).attach(g + 0.20, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(g + 0.02, "contact", essential=True),
              ev(g + 0.02, "show", ("L", C.ITEM_KEY), essential=True), ev(g + 0.04, "sound", "key_pickup"),
              ev(g + 0.61, "sound", "key_jingle"), ev(g + 1.22, "hide", "L")]
    return Clip("key_pickup", g + 1.47, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_KEY, "grasp": "L", "world_item": True})


# ---------------------------------------------------------------------------
# Mapa: pegar dobrado, desdobrar em dois tempos, mostrar aberto (mão esquerda)
# ---------------------------------------------------------------------------
FOLDED = 174.0          # graus em cada dobra do mapa fechado


def map_pickup():
    path = Path("L", C.ITEM_MAP)
    g = REACH_GRASP
    held, held_rot = (-0.205, -0.075, -0.380), (-18.0, 10.0, 4.0)
    shown, shown_rot = HOLD_ITEM[("L", C.ITEM_MAP)]
    reach(path, (6.0, 14.0, 8.0), (0.0, 0.06, 0.04), (-6.0, 4.0, 2.0), (0.0, 0.016, 0.0), (-14.0, 2.0, 0.0), OPEN)
    path.curl(g + 0.10, PINCH)
    path.item(g + 0.42, held, held_rot, PINCH, stop=True)
    path.item(g + 0.72, (held[0] + 0.012, held[1] + 0.006, held[2] + 0.010), (held_rot[0] - 4.0, 16.0, 8.0), PINCH)
    path.item(g + 1.14, (shown[0] + 0.020, shown[1] + 0.014, shown[2] + 0.020), (shown_rot[0] + 4.0, 18.0, 8.0), PINCH)
    path.item(g + 1.50, shown, shown_rot, PINCH, stop=True)
    path.item(g + 1.90, (-0.300, -0.330, -0.300), (-30.0, 20.0, 10.0), PINCH)
    path.weight(g + 1.70, 1.0).weight(g + 2.02, 0.0, stop=True)
    path.attach(g, 0.0, stop=True).attach(g + 0.24, 1.0, stop=True)
    path.extra("fold1", 0.0, FOLDED, stop=True).extra("fold2", 0.0, -FOLDED, stop=True)
    path.extra("fold2", g + 0.44, -FOLDED, stop=True).extra("fold2", g + 0.80, 0.0, stop=True)
    path.extra("fold1", g + 0.82, FOLDED, stop=True).extra("fold1", g + 1.18, 0.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(g + 0.02, "contact", essential=True),
              ev(g + 0.02, "show", ("L", C.ITEM_MAP), essential=True), ev(g + 0.04, "sound", "map_fold"),
              ev(g + 0.52, "sound", "map_unfold"), ev(g + 0.90, "sound", "map_unfold"), ev(g + 1.86, "hide", "L")]
    return Clip("map_pickup", g + 2.05, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_MAP, "grasp": "L", "world_item": True})


# ---------------------------------------------------------------------------
# Anotação: folha até o rosto (mão esquerda). A folha no chão sai do lugar; a presa na parede, não.
# ---------------------------------------------------------------------------
def note_pickup():
    path = Path("L", C.ITEM_NOTE)
    g = REACH_GRASP
    face, face_rot = FACE_ITEM[C.ITEM_NOTE]
    reach(path, (6.0, 14.0, 8.0), (0.0, 0.05, 0.04), (-4.0, 4.0, 2.0), (0.0, 0.012, 0.0), (-8.0, 2.0, 0.0), OPEN)
    path.curl(g + 0.08, HOLD_SHEET)
    path.item(g + 0.30, (-0.120, -0.090, -0.340), (-14.0, 8.0, 2.0), HOLD_SHEET)
    path.item(g + 0.58, face, face_rot, HOLD_SHEET, stop=True)
    path.attach(g, 0.0, stop=True).attach(g + 0.20, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(g + 0.02, "contact", essential=True),
              ev(g + 0.02, "show", ("L", C.ITEM_NOTE), essential=True), ev(g + 0.04, "sound", "paper_pick"),
              ev(g + 0.58, "open", essential=True)]
    return Clip("note_pickup", g + 0.58, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_NOTE, "grasp": "L", "world_item": True})


def note_wall():
    """Nota presa na parede: a ponta dos dedos toca a folha e o rosto se aproxima (o campo de visão fecha)."""
    path = Path("L", C.ITEM_NOTE)
    g = REACH_GRASP
    path.hand(0.00, OFF_SCREEN["L"], (6.0, 14.0, 8.0), OPEN, w=0.0)
    path.weight(0.16, 1.0)
    path.hand(REACH_PRE, (0.02, 0.03, 0.02), (-12.0, 4.0, 0.0), OPEN, space="grasp")
    path.hand(g, (0.0, 0.0, 0.0), (-20.0, 2.0, 0.0), (0.2, 0.15, 0.55, 0.6, 0.6), stop=True, space="grasp")
    path.extra("zoom", g - 0.12, 0.0, stop=True).extra("zoom", g + 0.34, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(g + 0.02, "touch", essential=True),
              ev(g + 0.04, "sound", "paper_pick"), ev(g + 0.34, "open", essential=True)]
    return Clip("note_wall", g + 0.34, path.tracks(), events,
                meta={"side": "L", "kind": None, "grasp": "L", "world_item": False})


def note_putback():
    """O leitor fechou: a folha volta ao lugar onde estava e a mão recua."""
    path = Path("L", C.ITEM_NOTE)
    face, face_rot = FACE_ITEM[C.ITEM_NOTE]
    path.item(0.00, face, face_rot, HOLD_SHEET, stop=True)
    path.hand(0.34, (0.0, 0.050, 0.030), (-8.0, 2.0, 0.0), HOLD_SHEET, space="grasp")
    path.hand(0.46, (0.0, 0.012, 0.0), (-8.0, 2.0, 0.0), HOLD_SHEET, stop=True, space="grasp")
    path.curl(0.52, OPEN)
    path.hand(0.82, (-0.30, -0.30, -0.26), (6.0, 14.0, 8.0), OPEN, w=1.0)
    path.weight(0.64, 1.0).weight(0.90, 0.0, stop=True)
    path.attach(0.00, 1.0, stop=True).attach(0.20, 1.0).attach(0.46, 0.0, stop=True)
    events = [ev(0.46, "putback", essential=True), ev(0.48, "sound", "paper_pick")]
    return Clip("note_putback", 0.95, path.tracks(), events, interruptible=True,
                meta={"side": "L", "kind": C.ITEM_NOTE, "grasp": "L", "world_item": True})


def note_retreat():
    """Nota presa na parede: a mão recua e o campo de visão volta ao normal."""
    path = Path("L", C.ITEM_NOTE)
    path.hand(0.00, (0.0, 0.0, 0.0), (-20.0, 2.0, 0.0), w=1.0, stop=True, space="grasp")
    path.hand(0.36, (-0.10, -0.18, 0.06), (0.0, 8.0, 4.0), OPEN, space="grasp")
    path.weight(0.22, 1.0).weight(0.48, 0.0, stop=True)
    path.extra("zoom", 0.0, 1.0, stop=True).extra("zoom", 0.45, 0.0, stop=True)
    return Clip("note_retreat", 0.50, path.tracks(), [], interruptible=True, meta={"side": "L", "kind": None, "grasp": "L"})


def note_to_hold():
    """Leitor fechado com a folha vinda da roda: ela volta da frente do rosto para a posição de segurar."""
    path = Path("L", C.ITEM_NOTE)
    pos, rot = HOLD_ITEM[("L", C.ITEM_NOTE)]
    path.item(0.00, *FACE_ITEM[C.ITEM_NOTE], HOLD_SHEET, stop=True)
    path.item(0.40, pos, rot, HOLD_SHEET, stop=True)
    return Clip("note_to_hold", 0.40, path.tracks(), [ev(0.02, "sound", "paper_pick")],
                meta={"side": "L", "kind": C.ITEM_NOTE})


def note_raise(from_pocket):
    """Anotação do inventário: a folha sobe até o rosto (da posição de segurar, ou de baixo, do bolso)."""
    path = Path("L", C.ITEM_NOTE)
    pos, rot = HOLD_ITEM[("L", C.ITEM_NOTE)]
    face, face_rot = FACE_ITEM[C.ITEM_NOTE]
    if from_pocket:
        path.item(0.00, (pos[0] - 0.06, pos[1] - 0.26, pos[2] + 0.05), (rot[0] - 14.0, rot[1], rot[2] - 8.0),
                  HOLD_SHEET, w=0.0)
        path.weight(0.10, 1.0)
        path.item(0.30, pos, rot, HOLD_SHEET)
    else:
        path.item(0.00, pos, rot, HOLD_SHEET, stop=True)
    path.item(0.58 if from_pocket else 0.40, face, face_rot, HOLD_SHEET, stop=True)
    duration = 0.58 if from_pocket else 0.40
    events = [ev(0.02, "show", ("L", C.ITEM_NOTE), essential=True), ev(0.06, "sound", "paper_pick"),
              ev(duration, "open", essential=True)]
    return Clip("note_raise", duration, path.tracks(), events, meta={"side": "L", "kind": C.ITEM_NOTE})


# ---------------------------------------------------------------------------
# Trocar de item na mão esquerda
# ---------------------------------------------------------------------------
def stow(kind):
    """A mão esquerda guarda o item: desce e sai do quadro."""
    path = Path("L", kind)
    pos, rot = HOLD_ITEM[("L", kind)]
    path.item(0.00, pos, rot, HOLD_CURL[kind], stop=True)
    path.item(0.26, (pos[0] - 0.08, pos[1] - 0.26, pos[2] + 0.06), (rot[0] - 14.0, rot[1], rot[2] + 8.0),
              HOLD_CURL[kind])
    path.weight(0.12, 1.0).weight(0.30, 0.0, stop=True)
    events = [ev(0.28, "hide", "L", essential=True), ev(0.28, "set_left", None, essential=True)]
    return Clip(f"stow_{kind.lower()}", 0.32, path.tracks(), events, interruptible=True,
                meta={"side": "L", "kind": kind})


def draw(kind):
    """A mão esquerda traz o item de baixo para a posição de segurar."""
    path = Path("L", kind)
    pos, rot = HOLD_ITEM[("L", kind)]
    path.item(0.00, (pos[0] - 0.06, pos[1] - 0.26, pos[2] + 0.05), (rot[0] - 14.0, rot[1], rot[2] - 8.0),
              HOLD_CURL[kind], w=0.0)
    path.weight(0.10, 1.0)
    path.item(0.38, pos, rot, HOLD_CURL[kind], stop=True)
    sound = {C.ITEM_KEY: "key_jingle", C.ITEM_MAP: "map_unfold", C.ITEM_NOTE: "paper_pick",
             C.ITEM_BATTERY: "cloth_rustle_2"}[kind]
    events = [ev(0.02, "set_left", kind, essential=True), ev(0.02, "show", ("L", kind), essential=True),
              ev(0.10, "sound", sound, essential=False)]
    return Clip(f"draw_{kind.lower()}", 0.46, path.tracks(), events, interruptible=True,
                meta={"side": "L", "kind": kind})


MAP_NEAR = NEAR_ITEM[C.ITEM_MAP]


def map_near():
    """E sem alvo com o mapa na mão: aproxima do rosto."""
    path = Path("L", C.ITEM_MAP)
    pos, rot = HOLD_ITEM[("L", C.ITEM_MAP)]
    path.item(0.00, pos, rot, PINCH, stop=True)
    path.item(0.42, *MAP_NEAR, PINCH, stop=True)
    return Clip("map_near", 0.42, path.tracks(), [ev(0.02, "sound", "map_unfold")],
                meta={"side": "L", "kind": C.ITEM_MAP})


def map_back():
    path = Path("L", C.ITEM_MAP)
    pos, rot = HOLD_ITEM[("L", C.ITEM_MAP)]
    path.item(0.00, *MAP_NEAR, PINCH, stop=True)
    path.item(0.40, pos, rot, PINCH, stop=True)
    return Clip("map_back", 0.40, path.tracks(), [], meta={"side": "L", "kind": C.ITEM_MAP})


# ---------------------------------------------------------------------------
# Trocar as pilhas (R): as duas mãos
# ---------------------------------------------------------------------------
SWAP_TILT = ((0.060, -0.140, -0.330), (-62.0, 12.0, -10.0))     # lanterna com a tampa para cima e para trás
TAIL_OPENING = 0.057                                              # z da boca da lanterna no referencial do viewmodel
CELL_HALF = 0.032


def _cell_on_axis(z):
    """Pose da pilha alinhada ao eixo da lanterna inclinada, com o centro em `z` (referencial do viewmodel)."""
    matrix = pose_matrix(*SWAP_TILT) @ pose_matrix((0.0, 0.0, z), (0.0, 0.0, 0.0))
    pos, rot, _ = pose_parts(matrix)
    return pos, rot


def swap(left_start, left_end):
    """A direita abaixa e gira a lanterna, a esquerda traz a pilha, a tampa abre e fecha e a luz volta.

    `left_start`: o que a esquerda já segura (a pilha na palma) ou None (a pilha vem do bolso).
    `left_end`: o que a esquerda segura depois (a próxima pilha) ou None."""
    right = Path("R", C.ITEM_FLASHLIGHT)
    left = Path("L", C.ITEM_BATTERY)
    hold, hold_rot = HOLD_ITEM[("R", C.ITEM_FLASHLIGHT)]
    tilted, tilted_rot = SWAP_TILT
    right.item(0.00, hold, hold_rot, FLASH_FIST, stop=True)
    right.item(0.34, tilted, tilted_rot, FLASH_FIST, stop=True)
    right.item(0.94, tilted, tilted_rot, FLASH_FIST, stop=True)
    right.item(1.34, hold, hold_rot, FLASH_FIST, stop=True)
    right.curl(1.28, FLASH_FIST).curl(1.39, FLASH_CLICK, stop=True).curl(1.47, FLASH_FIST)
    right.extra("cap", 0.0, 0.0, stop=True).extra("cap", 0.40, 0.0, stop=True).extra("cap", 0.56, 105.0, stop=True)
    right.extra("cap", 0.92, 105.0, stop=True).extra("cap", 1.06, 0.0, stop=True)
    # a pilha chega à esquerda, para sobre a tampa aberta e desce pelo cano
    above = TAIL_OPENING + CELL_HALF + 0.05
    lined_up = TAIL_OPENING + CELL_HALF + 0.006
    inside = TAIL_OPENING - CELL_HALF + 0.004
    if left_start == C.ITEM_BATTERY:
        pos, rot = HOLD_ITEM[("L", C.ITEM_BATTERY)]
        left.item(0.00, pos, rot, CUP, stop=True)
    else:
        left.item(0.00, (-0.19, -0.30, -0.27), (-20.0, 90.0, 0.0), CUP, w=0.0)
        left.weight(0.12, 1.0)
    left.item(0.52, *_cell_on_axis(above + 0.06), CUP, stop=True)
    left.item(0.64, *_cell_on_axis(lined_up + 0.002), CUP, stop=True)
    left.item(0.88, *_cell_on_axis(inside), CUP, stop=True)
    if left_end == C.ITEM_BATTERY:                                      # sobrou outra pilha: volta à palma
        pos, rot = HOLD_ITEM[("L", C.ITEM_BATTERY)]
        left.item(1.34, pos, rot, CUP, stop=True)
    else:
        left.item(1.10, (-0.05, -0.20, -0.28), (-40.0, 40.0, 0.0), OPEN)
        left.weight(0.96, 1.0).weight(1.18, 0.0, stop=True)
    left.attach(0.0, 1.0, stop=True)
    events = [ev(0.00, "swap_begin", essential=True), ev(0.02, "sound", "hand_reach"),
              ev(0.54, "sound", "battery_clack"), ev(0.88, "swap_insert", essential=True), ev(0.90, "hide", "L"),
              ev(1.06, "sound", "battery_clack"), ev(1.38, "swap_end", essential=True),
              ev(1.40, "light_on", essential=True)]
    events.append(ev(0.05, "show", ("L", C.ITEM_BATTERY), essential=True))
    if left_end == C.ITEM_BATTERY:
        events.append(ev(1.00, "show", ("L", C.ITEM_BATTERY)))
    return Clip("swap", 1.48, merge(right, left), events,
                meta={"side": "R", "kind": C.ITEM_FLASHLIGHT, "left_end": left_end})


def refuse():
    """Sem pilha reserva ou com a pilha ainda boa: a direita inclina a lanterna para olhar a tampa e volta,
    a esquerda bate no bolso. Curto, sem fala."""
    right = Path("R", C.ITEM_FLASHLIGHT)
    hold, hold_rot = HOLD_ITEM[("R", C.ITEM_FLASHLIGHT)]
    look, look_rot = (0.105, -0.115, -0.300), (-24.0, 8.0, -4.0)
    right.item(0.00, hold, hold_rot, FLASH_FIST, stop=True)
    right.item(0.22, look, look_rot, FLASH_FIST, stop=True)
    right.item(0.36, look, look_rot, FLASH_FIST, stop=True)
    right.item(0.62, hold, hold_rot, FLASH_FIST, stop=True)
    events = [ev(0.22, "sound", "cloth_rustle_3")]
    return Clip("refuse", 0.66, right.tracks(), events, interruptible=True,
                meta={"side": "R", "kind": C.ITEM_FLASHLIGHT})
