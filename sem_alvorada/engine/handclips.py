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
EXTRAS = {"x.cap": 0.0, "x.cell": 0.0, "x.fold1": 0.0, "x.fold2": 0.0}


def hold_hand(side, kind):
    """Pose da mão (posição, rotação) que segura `kind` parado."""
    item_pos, item_rot = HOLD_ITEM[(side, kind)]
    pos, rot, _ = pose_parts(GRIPS[kind].hand_of(pose_matrix(item_pos, item_rot)))
    return pos, rot


def rest_channels(side, kind=None):
    """Valores de repouso de todos os canais de uma mão: segurando `kind` ou solta, fora do quadro."""
    if kind is None or (side, kind) not in HOLD_ITEM:
        pos, rot, curl, weight, attach = OFF_SCREEN[side], (0.0, 0.0, 0.0), RELAX, 0.0, 0.0
    else:
        (pos, rot), curl, weight, attach = hold_hand(side, kind), HOLD_CURL[kind], 1.0, 1.0
    return {f"{side}.pos": number(pos), f"{side}.rot": number(rot), f"{side}.curl": number(curl),
            f"{side}.w": number(weight), f"{side}.attach": number(attach)}


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

    def item(self, t, pos, rot, curl=None, w=1.0, stop=False):
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
    off = OFF_SCREEN["R"]
    click_at = 1.38
    path.hand(0.00, off, (8.0, -12.0, -6.0), OPEN, w=0.0)
    path.hand(0.14, (0.30, -0.28, -0.26), (2.0, -6.0, -4.0), OPEN, w=1.0)
    path.hand(0.34, (0.0, 0.07, 0.05), (-4.0, 0.0, 0.0), OPEN, space="grasp")
    path.hand(0.50, (0.0, 0.018, 0.0), (-14.0, 0.0, 0.0), OPEN, stop=True, space="grasp")
    path.curl(0.62, FLASH_GRAB)
    path.item(0.88, lift, lift_rot, FLASH_FIST)
    path.item(1.20, chest, chest_rot, FLASH_FIST, stop=True)
    path.curl(click_at - 0.10, FLASH_FIST)
    path.curl(click_at, FLASH_CLICK, stop=True)
    path.curl(click_at + 0.13, FLASH_FIST)
    path.item(click_at - 0.02, chest, chest_rot, stop=True)
    path.item(click_at + 0.05, (chest[0], chest[1] - 0.006, chest[2]), chest_rot)
    path.item(click_at + 0.22, chest, chest_rot, stop=True)
    path.item(2.40, chest, chest_rot, stop=True)
    path.item(2.90, hold, hold_rot, FLASH_FIST, stop=True)
    path.attach(0.52, 0.0, stop=True).attach(0.92, 1.0, stop=True)
    events = [ev(0.05, "sound", "hand_reach"), ev(0.52, "contact", essential=True),
              ev(0.52, "show", ("R", C.ITEM_FLASHLIGHT), essential=True),
              ev(0.54, "sound", "flash_pickup"), ev(click_at, "light_on", essential=True)]
    events += [ev(click_at + start, "burst", index, essential=False) for index, (start, _) in enumerate(FLICKER_BURSTS)]
    return Clip("lantern_first", 2.95, path.tracks(), events,
                meta={"side": "R", "kind": C.ITEM_FLASHLIGHT, "grasp": "R", "world_item": True})


# ---------------------------------------------------------------------------
# Pilha: recolher na palma, olhar, guardar (mão esquerda)
# ---------------------------------------------------------------------------
def battery_pickup():
    path = Path("L", C.ITEM_BATTERY)
    off = OFF_SCREEN["L"]
    show, show_rot = (-0.105, -0.095, -0.315), (-14.0, 80.0, 4.0)
    near, near_rot = (-0.115, -0.085, -0.290), (-20.0, 76.0, 8.0)
    path.hand(0.00, off, (6.0, 14.0, 8.0), OPEN, w=0.0)
    path.hand(0.12, (-0.28, -0.28, -0.26), (0.0, 8.0, 4.0), OPEN, w=1.0)
    path.hand(0.26, (0.0, 0.06, 0.04), (-6.0, 4.0, 2.0), OPEN, space="grasp")
    path.hand(0.38, (0.0, 0.016, 0.0), (-14.0, 2.0, 0.0), OPEN, stop=True, space="grasp")
    path.curl(0.50, CUP)
    path.item(0.72, (-0.140, -0.125, -0.335), (-10.0, 88.0, 0.0), CUP)
    path.item(0.92, show, show_rot, CUP, stop=True)
    path.item(1.14, near, near_rot, CUP, stop=True)
    path.item(1.34, (-0.190, -0.300, -0.250), (-20.0, 80.0, 10.0), CUP)
    path.weight(1.20, 1.0).weight(1.50, 0.0, stop=True)
    path.attach(0.38, 0.0, stop=True).attach(0.60, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(0.40, "contact", essential=True),
              ev(0.40, "show", ("L", C.ITEM_BATTERY), essential=True),
              ev(1.30, "hide", "L"), ev(1.46, "sound", "cloth_rustle_1")]
    return Clip("battery_pickup", 1.55, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_BATTERY, "grasp": "L", "world_item": True})


# ---------------------------------------------------------------------------
# Chave: erguer o chaveiro e balançar uma vez (mão esquerda)
# ---------------------------------------------------------------------------
def key_pickup():
    path = Path("L", C.ITEM_KEY)
    off = OFF_SCREEN["L"]
    path.hand(0.00, off, (6.0, 14.0, 8.0), OPEN, w=0.0)
    path.hand(0.12, (-0.28, -0.28, -0.26), (0.0, 8.0, 4.0), OPEN, w=1.0)
    path.hand(0.26, (0.0, 0.06, 0.04), (-6.0, 4.0, 2.0), OPEN, space="grasp")
    path.hand(0.38, (0.0, 0.015, 0.0), (-16.0, 2.0, 0.0), OPEN, stop=True, space="grasp")
    path.curl(0.48, PINCH)
    path.item(0.74, (-0.200, -0.060, -0.360), (0.0, 0.0, 0.0), PINCH)
    path.item(0.92, (-0.150, -0.050, -0.375), (0.0, 0.0, 0.0), PINCH)        # o puxão que faz o chaveiro balançar
    path.item(1.02, (-0.236, -0.062, -0.370), (0.0, 0.0, 0.0), PINCH, stop=True)
    path.item(1.22, (-0.210, -0.075, -0.375), (0.0, 0.0, 0.0), PINCH, stop=True)
    path.item(1.62, (-0.300, -0.330, -0.250), (0.0, 0.0, 0.0), PINCH)
    path.weight(1.50, 1.0).weight(1.80, 0.0, stop=True)
    path.attach(0.38, 0.0, stop=True).attach(0.58, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(0.40, "contact", essential=True),
              ev(0.40, "show", ("L", C.ITEM_KEY), essential=True), ev(0.42, "sound", "key_pickup"),
              ev(0.99, "sound", "key_jingle"), ev(1.60, "hide", "L")]
    return Clip("key_pickup", 1.85, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_KEY, "grasp": "L", "world_item": True})


# ---------------------------------------------------------------------------
# Mapa: pegar dobrado, desdobrar em dois tempos, mostrar aberto (mão esquerda)
# ---------------------------------------------------------------------------
FOLDED = 174.0          # graus em cada dobra do mapa fechado


def map_pickup():
    path = Path("L", C.ITEM_MAP)
    off = OFF_SCREEN["L"]
    held, held_rot = (-0.205, -0.075, -0.380), (-18.0, 10.0, 4.0)
    shown, shown_rot = HOLD_ITEM[("L", C.ITEM_MAP)]
    path.hand(0.00, off, (6.0, 14.0, 8.0), OPEN, w=0.0)
    path.hand(0.12, (-0.28, -0.28, -0.26), (0.0, 8.0, 4.0), OPEN, w=1.0)
    path.hand(0.28, (0.0, 0.06, 0.04), (-6.0, 4.0, 2.0), OPEN, space="grasp")
    path.hand(0.40, (0.0, 0.016, 0.0), (-14.0, 2.0, 0.0), OPEN, stop=True, space="grasp")
    path.curl(0.50, PINCH)
    path.item(0.82, held, held_rot, PINCH, stop=True)
    path.item(1.12, (held[0] + 0.012, held[1] + 0.006, held[2] + 0.010), (held_rot[0] - 4.0, 16.0, 8.0), PINCH)
    path.item(1.52, (shown[0] + 0.020, shown[1] + 0.014, shown[2] + 0.020), (shown_rot[0] + 4.0, 18.0, 8.0), PINCH)
    path.item(2.00, shown, shown_rot, PINCH, stop=True)
    path.item(2.50, (-0.300, -0.330, -0.300), (-30.0, 20.0, 10.0), PINCH)
    path.weight(2.30, 1.0).weight(2.62, 0.0, stop=True)
    path.attach(0.40, 0.0, stop=True).attach(0.62, 1.0, stop=True)
    path.extra("fold1", 0.0, FOLDED, stop=True).extra("fold2", 0.0, -FOLDED, stop=True)
    path.extra("fold2", 0.84, -FOLDED, stop=True).extra("fold2", 1.20, 0.0, stop=True)
    path.extra("fold1", 1.22, FOLDED, stop=True).extra("fold1", 1.60, 0.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(0.42, "contact", essential=True),
              ev(0.42, "show", ("L", C.ITEM_MAP), essential=True), ev(0.44, "sound", "map_fold"),
              ev(0.92, "sound", "map_unfold"), ev(1.30, "sound", "map_unfold"), ev(2.46, "hide", "L")]
    return Clip("map_pickup", 2.65, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_MAP, "grasp": "L", "world_item": True})


# ---------------------------------------------------------------------------
# Anotação: folha até o rosto (mão esquerda). A folha no chão sai do lugar; a presa na parede, não.
# ---------------------------------------------------------------------------
def note_pickup():
    path = Path("L", C.ITEM_NOTE)
    off = OFF_SCREEN["L"]
    face, face_rot = (-0.010, -0.015, -0.255), (-4.0, 0.0, 0.0)
    path.hand(0.00, off, (6.0, 14.0, 8.0), OPEN, w=0.0)
    path.hand(0.12, (-0.26, -0.28, -0.26), (0.0, 8.0, 4.0), OPEN, w=1.0)
    path.hand(0.26, (0.0, 0.05, 0.04), (-4.0, 4.0, 2.0), OPEN, space="grasp")
    path.hand(0.38, (0.0, 0.012, 0.0), (-8.0, 2.0, 0.0), OPEN, stop=True, space="grasp")
    path.curl(0.46, HOLD_SHEET)
    path.item(0.70, (-0.120, -0.090, -0.340), (-14.0, 8.0, 2.0), HOLD_SHEET)
    path.item(0.96, face, face_rot, HOLD_SHEET, stop=True)
    path.attach(0.38, 0.0, stop=True).attach(0.58, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(0.40, "contact", essential=True),
              ev(0.40, "show", ("L", C.ITEM_NOTE), essential=True), ev(0.42, "sound", "paper_pick"),
              ev(0.96, "open", essential=True)]
    return Clip("note_pickup", 1.20, path.tracks(), events, hold=(0.96, 8.0),
                meta={"side": "L", "kind": C.ITEM_NOTE, "grasp": "L", "world_item": True})


def note_wall():
    """Nota presa na parede: a ponta dos dedos toca a folha e o rosto se aproxima (o campo de visão fecha)."""
    path = Path("L", C.ITEM_NOTE)
    off = OFF_SCREEN["L"]
    path.hand(0.00, off, (6.0, 14.0, 8.0), OPEN, w=0.0)
    path.hand(0.12, (-0.22, -0.26, -0.26), (0.0, 8.0, 4.0), OPEN, w=1.0)
    path.hand(0.34, (0.02, 0.03, 0.02), (-12.0, 4.0, 0.0), OPEN, space="grasp")
    path.hand(0.52, (0.0, 0.0, 0.0), (-20.0, 2.0, 0.0), (0.2, 0.15, 0.55, 0.6, 0.6), stop=True, space="grasp")
    path.extra("zoom", 0.30, 0.0, stop=True).extra("zoom", 0.80, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(0.54, "touch", essential=True), ev(0.56, "sound", "paper_pick"),
              ev(0.80, "open", essential=True)]
    return Clip("note_wall", 0.90, path.tracks(), events, hold=(0.80, 8.0),
                meta={"side": "L", "kind": None, "grasp": "L", "world_item": False})


def read_lower(wall):
    """O leitor fechou: a folha desce (ou a mão recua da parede e o campo de visão volta)."""
    path = Path("L", C.ITEM_NOTE)
    off = OFF_SCREEN["L"]
    if wall:
        path.hand(0.00, (0.0, 0.0, 0.0), (-20.0, 2.0, 0.0), w=1.0, stop=True, space="grasp")
        path.hand(0.34, (-0.10, -0.18, 0.06), (0.0, 8.0, 4.0), OPEN, space="grasp")
        path.weight(0.20, 1.0).weight(0.46, 0.0, stop=True)
        path.extra("zoom", 0.0, 1.0, stop=True).extra("zoom", 0.45, 0.0, stop=True)
        return Clip("read_lower_wall", 0.50, path.tracks(), [], meta={"side": "L", "kind": None})
    path.item(0.00, (-0.010, -0.015, -0.255), (-4.0, 0.0, 0.0), HOLD_SHEET, stop=True)
    path.item(0.40, (-0.20, -0.30, -0.290), (-22.0, 12.0, 6.0), HOLD_SHEET)
    path.weight(0.26, 1.0).weight(0.50, 0.0, stop=True)
    events = [ev(0.46, "hide", "L")]
    return Clip("read_lower", 0.55, path.tracks(), events, meta={"side": "L", "kind": C.ITEM_NOTE})


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
    events = [ev(0.28, "hide", "L"), ev(0.28, "set_left", None)]
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


def map_inspect():
    """E sem alvo com o mapa na mão: aproxima do rosto, espera, e volta."""
    path = Path("L", C.ITEM_MAP)
    pos, rot = HOLD_ITEM[("L", C.ITEM_MAP)]
    near, near_rot = (-0.165, -0.010, -0.250), (-6.0, 6.0, 2.0)
    path.item(0.00, pos, rot, PINCH, stop=True)
    path.item(0.42, near, near_rot, PINCH, stop=True)
    path.item(0.46, near, near_rot, PINCH, stop=True)
    path.item(0.86, pos, rot, PINCH, stop=True)
    events = [ev(0.02, "sound", "map_unfold")]
    return Clip("map_inspect", 0.90, path.tracks(), events, hold=(0.46, 1.6), meta={"side": "L", "kind": C.ITEM_MAP})


# ---------------------------------------------------------------------------
# Trocar as pilhas (R): as duas mãos
# ---------------------------------------------------------------------------
def swap(left_end):
    """A direita abaixa e gira a lanterna, a esquerda traz a pilha, a tampa abre e fecha e a luz volta.

    `left_end`: o item que a mão esquerda segura depois (a próxima pilha, por exemplo) ou None."""
    right = Path("R", C.ITEM_FLASHLIGHT)
    left = Path("L", C.ITEM_BATTERY)
    hold, hold_rot = HOLD_ITEM[("R", C.ITEM_FLASHLIGHT)]
    tilted, tilted_rot = (0.060, -0.140, -0.330), (-62.0, 12.0, -10.0)        # tampa para cima e para trás
    right.item(0.00, hold, hold_rot, FLASH_FIST, stop=True)
    right.item(0.34, tilted, tilted_rot, FLASH_FIST, stop=True)
    right.item(0.94, tilted, tilted_rot, FLASH_FIST, stop=True)
    right.item(1.34, hold, hold_rot, FLASH_FIST, stop=True)
    right.curl(1.30, FLASH_FIST).curl(1.40, FLASH_CLICK, stop=True).curl(1.52, FLASH_FIST)
    right.extra("cap", 0.0, 0.0, stop=True).extra("cap", 0.40, 0.0, stop=True).extra("cap", 0.56, 105.0, stop=True)
    right.extra("cap", 0.92, 105.0, stop=True).extra("cap", 1.06, 0.0, stop=True)
    right.extra("cell", 0.0, 0.0, stop=True).extra("cell", 0.60, 0.0, stop=True).extra("cell", 0.90, 1.0, stop=True)
    # a pilha chega de baixo à esquerda, para sobre a tampa aberta e desce pelo cano
    cell_start = (-0.19, -0.30, -0.27)
    left.item(0.00, cell_start, (-20.0, 90.0, 0.0), CUP, w=0.0)
    left.weight(0.12, 1.0)
    left.item(0.52, (0.040, -0.040, -0.300), (-62.0, 12.0, -10.0), CUP, stop=True)
    left.item(0.62, (0.040, -0.040, -0.300), (-62.0, 12.0, -10.0), CUP, stop=True)
    left.item(0.90, (0.055, -0.085, -0.315), (-62.0, 12.0, -10.0), CUP, stop=True)
    left.item(1.10, (-0.05, -0.20, -0.28), (-40.0, 40.0, 0.0), OPEN)
    left.weight(0.96, 1.0).weight(1.18, 0.0, stop=True)
    left.attach(0.0, 1.0, stop=True)
    events = [ev(0.00, "swap_begin", essential=True), ev(0.02, "sound", "hand_reach"),
              ev(0.54, "sound", "battery_clack"), ev(0.62, "show", ("L", C.ITEM_BATTERY)),
              ev(0.88, "swap_insert", essential=True), ev(0.90, "hide", "L"),
              ev(1.06, "sound", "battery_clack"), ev(1.40, "light_on", essential=True),
              ev(1.46, "swap_end", essential=True)]
    events.insert(0, ev(0.00, "show", ("L", C.ITEM_BATTERY)))
    return Clip("swap", 1.48, merge(right, left), events, meta={"side": "R", "kind": C.ITEM_FLASHLIGHT, "left_end": left_end})


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
