"""Biblioteca de clipes das mãos: um gesto único para cada tipo de item, escrito como dados.

Espaço da câmera (metros): X direita, Y cima, -Z frente. Quem escreve os clipes dá as rotações em graus, Euler
XYZ, aplicadas a uma mão neutra com a palma para baixo e os dedos para a frente (-Z); o eixo Z da câmera é,
portanto, o eixo dos dedos (rz = rolar a palma para cima ou para baixo). Dentro das trilhas elas viram
quaternions (`QuatTrack`), porque várias garras deixam a mão com os dedos na horizontal, onde o Euler trava.

Trilhas de uma mão (`side` = "R" ou "L"): `pos`, `rot`, `curl` (5 dedos, 0 aberto .. 1 fechado), `w` (peso do
IK: 0 solta o braço) e `attach` (0 o item ainda está no mundo, 1 está preso à mão). Extras `x.*` movem partes
do item: tampa da lanterna (`cap`), dobras do mapa (`fold1`, `fold2`) e o fechar do campo de visão (`zoom`).

Perfil e duração (fase 4). Toda trilha de posição entre duas chaves paradas (`stop`) é um movimento de jerk mínimo, com o
pico de velocidade a 50% da duração (`handtrack`), e as durações seguem a lei medida no mocap real (`move_time`). O alcance
parte da mão solta, onde o braço pende (âncora viva `rest`), e vai em linha reta ao ponto de pegar (âncora viva `grasp`).

Depois do contato o que importa é onde o ITEM aparece na tela (legível no escuro, sem cobrir a mira): essas
chaves são escritas como poses do item e convertidas para a mão pela garra de cada item (`GRIPS`). Antes do
contato a mão é quem lidera e a chave pode ser relativa ao ponto de pegar ao vivo (`space="grasp"`).
"""
import math

import bpy  # noqa: F401 - `mathutils` só existe depois deste import
from mathutils import Euler, Matrix, Vector

from .. import conventions as C
from .handtrack import Clip, Event, Key, QuatTrack, Track, number

SIDE_SIGN = {"R": 1.0, "L": -1.0}
HANG_POS = {"R": (0.263, -0.844, -0.064), "L": (-0.263, -0.842, -0.075)}    # palma do braço solto, olhando em frente
OFF_SCREEN = HANG_POS              # nome antigo: a mão sem peso fica onde o braço pende, abaixo do quadro
REACH_LIMIT = 0.52                 # até onde a palma chega do rosto (m). Com 0,60 o braço ia esticado ao centro da tela
REACH_DROP = -0.08                 # e a palma fica pelo menos 8 cm abaixo da linha do olhar: a 0,52 m o cotovelo cai fora do
                                   # quadro; com a palma na linha do olhar ele ficava a 34 cm do rosto, no meio da tela

# Lei de tempo dos movimentos da mão. MEDIDA em 199 alcances limpos (correlação > 0,9 com o perfil de jerk mínimo, trajetória
# reta) de 20 clipes da CMU (15_06/07, 22_23, 23_23, 69_68..75, 79_36/38, 80_25, 111_17, 115_01, 13_09, 144_22..25), com o
# punho relativo ao quadril e os alcances achados por `tools/movimento_ref/metricas.detectar_alcances` (a duração é onde a
# velocidade passa de 6% do pico):
#     T(6%) = 0,628 + 0,145 * D / L     (s; D = distância reta do punho, L = comprimento ombro-punho do clipe)
# com desvio residual de 0,22 s (a dependência da distância é fraca) e o pico de velocidade em 49 +- 6% da duração. Para D/L
# de 0,3 a 0,6 (18 a 36 cm no Daniel, L = 0,60 m) a média medida é 0,70 s. Uma segmentação mais estreita (de vale a vale,
# 182 alcances) dá 0,464 + 0,193 D/L, uns 0,1 s mais curta: a incerteza do método. Um movimento de jerk mínimo de duração
# nominal T passa de 6% do pico só em 87% de T, então a duração nominal que as chaves usam é T(6%) / 0,869, a mesma que
# `metricas.ajuste_jerk_minimo` devolve. Abaixo de D/L = 0,6 não há dado confiável (o detector pede pico de 0,35 m/s, que
# um movimento curto não tem): a duração desce linearmente até o piso de 0,30 s, ESTIMADO.
MOVE_A, MOVE_B = 0.628 / 0.869, 0.145 / 0.869
ARM_LENGTH = 0.60
MOVE_MIN, MOVE_MAX = 0.30, 1.1
MEASURED_FROM = 0.6                # D/L a partir do qual a lei é medida
GRASP_DWELL = 0.12                 # ESTIMADO: o vale de velocidade entre o alcance e o levantar nos clipes de pegar


def move_time(distance):
    """Duração nominal (s) de um movimento da mão de `distance` metros, pela lei medida."""
    ratio = distance / ARM_LENGTH
    if ratio >= MEASURED_FROM:
        return min(MOVE_MAX, MOVE_A + MOVE_B * ratio)
    floor_to_law = (MOVE_A + MOVE_B * MEASURED_FROM - MOVE_MIN) / MEASURED_FROM
    return MOVE_MIN + floor_to_law * max(0.0, ratio)

# Dedos do polegar ao mindinho (valores na escala de `body.fingers.PRESETS`)
OPEN = (0.35, 0.16, 0.18, 0.22, 0.28)            # mão que alcança: relaxada, o polegar não aponta para fora
RELAX = (0.30, 0.22, 0.28, 0.34, 0.40)
FLASH_FIST = (0.18, 0.62, 0.68, 0.72, 0.74)       # o polegar fica livre sobre o botão
FLASH_CLICK = (0.60, 0.62, 0.68, 0.72, 0.74)
FLASH_GRAB = (0.52, 0.60, 0.66, 0.70, 0.72)
PINCH = (0.46, 0.50, 0.40, 0.48, 0.56)
CUP = (0.18, 0.34, 0.40, 0.46, 0.52)
HOLD_SHEET = (0.34, 0.36, 0.30, 0.40, 0.46)


# ---------------------------------------------------------------------------
# Matemática de poses
# ---------------------------------------------------------------------------
def pose_matrix(pos, rot_deg):
    matrix = Euler(tuple(math.radians(a) for a in rot_deg), "XYZ").to_matrix().to_4x4()
    matrix.translation = Vector(pos)
    return matrix


def euler_quaternion(rot_deg):
    """Euler XYZ em graus -> quaternion (w, x, y, z), a forma das trilhas de rotação."""
    return tuple(Euler(tuple(math.radians(a) for a in rot_deg), "XYZ").to_quaternion())


def pose_parts(matrix):
    """(posição, quaternion) de uma pose em matriz."""
    return tuple(matrix.translation), tuple(matrix.to_quaternion())


# Mão neutra no espaço da câmera: colunas (dedos, normal da palma, lado do polegar). Igual a
# `body.skeleton.NEUTRAL_HAND_CAM` (há teste); copiada aqui para o engine não depender do pacote do corpo.
NEUTRAL_HAND = Matrix(((0.0, 0.0, -1.0), (0.0, -1.0, 0.0), (-1.0, 0.0, 0.0))).transposed()


def hand_rotation(fingers, palm):
    """Euler XYZ (graus) que leva a mão neutra a apontar os dedos para `fingers` e a palma para `palm`."""
    f = Vector(fingers).normalized()
    p = Vector(palm)
    p = (p - f * p.dot(f)).normalized()
    target = Matrix((f, p, f.cross(p))).transposed()
    return tuple(math.degrees(a) for a in (target @ NEUTRAL_HAND.inverted()).to_euler("XYZ"))


class Grip:
    """Onde a palma fica no referencial do item: `mão = item @ garra`. A orientação sai de para onde os dedos
    apontam e para onde a palma olha (a mesma descrição de `body.hand_rotation`)."""

    def __init__(self, pos=(0.0, 0.0, 0.0), fingers=(0.0, 0.0, -1.0), palm=(0.0, -1.0, 0.0)):
        self.matrix = pose_matrix(pos, hand_rotation(fingers, palm))
        self.inverse = self.matrix.inverted()

    def hand_of(self, item_matrix):
        return item_matrix @ self.matrix

    def item_of(self, hand_matrix):
        return hand_matrix @ self.inverse


# Garras no referencial do MODELO de cada item (mão direita para a lanterna, esquerda para o resto). A
# lanterna é um punho em volta do cano vindo da direita e de baixo, polegar sobre o botão e apontando à frente;
# o chaveiro é pinçado pela cabeça com a mão atrás (a palma fica a ~7 cm da ponta dos dedos); o mapa fica preso
# pela borda esquerda, com a mão atrás dele; a pilha repousa na palma virada para cima; a folha é segurada
# pela borda de baixo.
GRIPS = {
    C.ITEM_FLASHLIGHT: Grip((0.025, -0.018, 0.0), (-0.59, -0.81, 0.0), (-0.81, 0.59, 0.0)),
    C.ITEM_KEY: Grip((-0.020, -0.010, 0.065), (0.35, 0.30, -0.89), (0.75, -0.65, 0.0)),
    C.ITEM_MAP: Grip((-0.030, -0.025, -0.035), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
    C.ITEM_BATTERY: Grip((0.0, -0.027, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
    C.ITEM_NOTE: Grip((0.0, -0.040, -0.012), (0.0, 0.8, -0.6), (-0.4, 0.0, -0.9)),
}

# Giro da mão e da lanterna juntas em torno do cano. Com a lanterna na horizontal a mão a segura de lado, o antebraço
# vem de baixo e o cotovelo cai (MEDIDO em 77_05: cotovelo a 121 graus, braço a 59 graus da vertical); sem o giro a palma
# ficava embaixo do cano e o IK jogava o cotovelo para fora, com o braço na horizontal (90 graus) e o punho no limite.
FLASH_ROLL = -62.0


def with_roll(aim_deg, roll_deg=FLASH_ROLL):
    """Euler XYZ (graus) de um item cujo cano aponta como `aim_deg` e que gira `roll_deg` em torno do próprio cano (Z local);
    o cano continua apontando para o mesmo lugar."""
    aim = Euler(tuple(math.radians(a) for a in aim_deg), "XYZ").to_matrix()
    roll = Euler((0.0, 0.0, math.radians(roll_deg)), "XYZ").to_matrix()
    return tuple(math.degrees(a) for a in (aim @ roll).to_euler("XYZ"))


# Item parado na mão (pose do item no espaço da câmera): (posição, rotação)
HOLD_ITEM = {
    ("R", C.ITEM_FLASHLIGHT): ((0.150, -0.100, -0.300), with_roll((8.0, 6.0, -8.0))),
    ("L", C.ITEM_KEY): ((-0.205, -0.015, -0.385), (0.0, 0.0, 0.0)),
    ("L", C.ITEM_MAP): ((-0.290, -0.115, -0.44), (-28.0, 14.0, 6.0)),
    ("L", C.ITEM_BATTERY): ((-0.130, -0.060, -0.33), (-6.0, 0.0, 0.0)),
    ("L", C.ITEM_NOTE): ((-0.185, -0.150, -0.40), (-22.0, 10.0, 4.0)),
}
HOLD_CURL = {C.ITEM_FLASHLIGHT: FLASH_FIST, C.ITEM_KEY: PINCH, C.ITEM_MAP: PINCH, C.ITEM_BATTERY: CUP,
             C.ITEM_NOTE: HOLD_SHEET}
EXTRAS = {"x.cap": 0.0, "x.fold1": 0.0, "x.fold2": 0.0, "x.zoom": 0.0}


FACE_ITEM = {C.ITEM_NOTE: ((-0.040, -0.100, -0.300), (-4.0, 0.0, 0.0))}      # a folha diante do rosto
NEAR_ITEM = {C.ITEM_MAP: ((-0.130, -0.030, -0.300), (-6.0, 6.0, 2.0))}        # o mapa aproximado do rosto
MODE_POSES = {"hold": HOLD_ITEM, "face": {("L", k): v for k, v in FACE_ITEM.items()},
              "near": {("L", k): v for k, v in NEAR_ITEM.items()}}


def hold_hand(side, kind, mode="hold"):
    """Pose da mão (posição, rotação) que segura `kind` parado."""
    item_pos, item_rot = MODE_POSES[mode].get((side, kind), HOLD_ITEM[(side, kind)])
    return pose_parts(GRIPS[kind].hand_of(pose_matrix(item_pos, item_rot)))


def rest_channels(side, kind=None, mode="hold"):
    """Valores de repouso de todos os canais de uma mão: segurando `kind` ou solta, fora do quadro."""
    if kind is None or (side, kind) not in HOLD_ITEM:
        pos, rot, curl, weight, attach = HANG_POS[side], euler_quaternion(HANG_ROT[side]), RELAX, 0.0, 0.0
    else:
        (pos, rot), curl, weight, attach = hold_hand(side, kind, mode), HOLD_CURL[kind], 1.0, 1.0
    return {f"{side}.pos": number(pos), f"{side}.rot": number(rot), f"{side}.curl": number(curl),
            f"{side}.w": number(weight), f"{side}.attach": number(attach)}


def ready_channels(side):
    """A mão esquerda se prepara enquanto a roda de itens está aberta: o antebraço aparece no canto, sem item."""
    sign = SIDE_SIGN[side]
    return {f"{side}.pos": number((0.27 * sign, -0.27, -0.24)), f"{side}.rot": number(euler_quaternion((-12.0, 10.0 * sign, 12.0 * sign))),
            f"{side}.curl": number(RELAX), f"{side}.w": number(0.55), f"{side}.attach": number(0.0)}


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
    C.ITEM_BATTERY: pose_matrix((0.0193, 0.0, 0.0188), (-90.0, 0.0, 0.0)) @ pose_matrix((0, 0, 0), (0.0, -90.0, 0.0)),
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

    def _add(self, name, t, value, stop=False, space="cam"):
        self.channels.setdefault(name, []).append(Key(float(t), number(value), stop, space))

    def hand(self, t, pos, rot, curl=None, w=None, stop=False, space="cam"):
        """Pose da mão. Em `space="grasp"` a posição é somada ao ponto de pegar (a rotação é sempre absoluta)."""
        self._add(f"{self.side}.pos", t, pos, stop, space)
        self._add(f"{self.side}.rot", t, euler_quaternion(rot), stop)
        if curl is not None:
            self._add(f"{self.side}.curl", t, curl, stop)
        if w is not None:
            self._add(f"{self.side}.w", t, w, stop)
        return self

    def rest(self, t, rot, curl=None, w=None, stop=False):
        """Mão solta onde o braço pende: posição na âncora viva "rest" (a palma do braço solto no espaço da câmera),
        com a posição padrão `HANG_POS` quando não há âncora (testes, corpo ausente)."""
        self._add(f"{self.side}.pos", t, HANG_POS[self.side], stop, "rest")
        self._add(f"{self.side}.rot", t, euler_quaternion(rot), stop)
        if curl is not None:
            self._add(f"{self.side}.curl", t, curl, stop)
        if w is not None:
            self._add(f"{self.side}.w", t, w, stop)
        return self

    def item(self, t, pos, rot, curl=None, w=None, stop=False):
        """Pose do item no espaço da câmera; a mão é derivada pela garra."""
        hand_pos, hand_rot = pose_parts(self.grip.hand_of(pose_matrix(pos, rot)))
        self._add(f"{self.side}.pos", t, hand_pos, stop)
        self._add(f"{self.side}.rot", t, hand_rot, stop)
        if curl is not None:
            self._add(f"{self.side}.curl", t, curl, stop)
        if w is not None:
            self._add(f"{self.side}.w", t, w, stop)
        return self

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
        return {name: (QuatTrack if name.endswith(".rot") else Track)(keys) for name, keys in self.channels.items()}


def merge(*paths):
    tracks = {}
    for path in paths:
        tracks.update(path.tracks())
    return tracks


def ev(t, name, arg=None, essential=False):
    return Event(float(t), name, arg, essential)


def _hang_rotation(side):
    """Rotação da mão do braço solto: dedos para baixo (e um pouco à frente), palma voltada para a coxa."""
    sign = SIDE_SIGN[side]
    return hand_rotation((0.04 * sign, -1.0, -0.12), (-sign, 0.0, 0.0))


HANG_ROT = {"R": _hang_rotation("R"), "L": _hang_rotation("L")}
GLIDE = 0.40               # depois do contato o item que a mão não alcançou vem até o punho (a mesa fica abaixo do
                           # alcance do braço: o item sobe do lugar dele até a mão enquanto ela fecha)
CLOSE_TIME = 0.20          # ESTIMADO: tempo que os dedos levam para fechar sobre o item
GRASP_PITCH = 15.0         # graus: dedos um pouco acima da horizontal. A palma pega a ~0,5 m do rosto com o cotovelo baixo
                           # (antebraço quase vertical): com os dedos 46 graus para baixo o pulso dobrava até o limite do
                           # solver (80 graus) e a manga apertava; com +15 o pedido cai a ~58 e o solver ainda comprime
GRASP_NOMINAL = (0.0, -0.08, -0.51)        # onde a palma costuma pegar (o limite do alcance, abaixo da linha do olhar)
NOMINAL_RETURN = 0.60      # distância típica (m) da pose de mostrar até a mão solta
REACH_DEFAULT = move_time(0.65)      # alcance típico: da mão solta ao item sobre uma mesa, 0,65 m


def reach(path, reach_s, grasp, grasp_rot, aperture, closed):
    """O alcance: da mão solta (âncora viva "rest") ao ponto de pegar (âncora viva "grasp"), em linha reta e com perfil
    de jerk mínimo. Os dedos abrem durante o caminho (abertura máxima aos 60%, como nos alcances reais) e só fecham
    ao chegar. O peso do IK sobe nos primeiros 30%, quando a mão ainda está abaixo do quadro."""
    path.rest(0.0, HANG_ROT[path.side], RELAX, w=0.0)
    path.weight(0.30 * reach_s, 1.0)
    path.curl(0.60 * reach_s, aperture)
    path.hand(reach_s, grasp, grasp_rot, aperture, stop=True, space="grasp")
    path.curl(reach_s + 0.02, aperture, stop=True)
    path.curl(reach_s + 0.02 + CLOSE_TIME, closed, stop=True)
    path.hand(reach_s + GRASP_DWELL, grasp, grasp_rot, stop=True, space="grasp")      # a pinça acaba antes de levantar


EXIT_FACTOR = 0.75         # ESTIMADO: a mão que só sai do quadro, sem alvo a acertar, leva 3/4 do tempo de um alcance


def withdraw(path, t0, seconds=None):
    """A mão volta ao braço solto e o IK solta o braço no fim. Sem alvo a acertar, leva `EXIT_FACTOR` da lei do movimento."""
    seconds = EXIT_FACTOR * move_time(NOMINAL_RETURN) if seconds is None else seconds
    path.rest(t0 + seconds, HANG_ROT[path.side], RELAX, stop=True)
    path.weight(t0, 1.0).weight(t0 + seconds * 0.85, 1.0).weight(t0 + seconds, 0.0, stop=True)
    return t0 + seconds


# ---------------------------------------------------------------------------
# Lanterna: primeira vez (mão direita)
# ---------------------------------------------------------------------------
# Rajadas do mau contato (pilha fraca) depois do clique: (início depois do clique, duração total da rajada). Cada
# rajada é uma sequência de aberturas do contato de alguns milissegundos (ver `Flashlight.burst`); os intervalos
# encurtam: a lanterna foi usada antes e a carga já não é a de fábrica.
FLICKER_BURSTS = ((0.22, 0.13), (0.52, 0.11), (0.78, 0.10))


def lantern_first(reach_s=REACH_DEFAULT):
    """Estende a mão, pega a lanterna desligada, traz ao peito, o polegar clica, a luz pisca e a mão assume."""
    path = Path("R", C.ITEM_FLASHLIGHT)
    hold, hold_rot = HOLD_ITEM[("R", C.ITEM_FLASHLIGHT)]
    chest, chest_rot = (0.045, -0.055, -0.330), with_roll((26.0, 10.0, -6.0))
    contact = reach_s + 0.06
    lift = reach_s + GRASP_DWELL
    at_chest = lift + move_time(math.dist(GRASP_NOMINAL, chest))
    click_at = at_chest - 0.04
    leave = click_at + 0.38
    arrive = leave + move_time(math.dist(chest, hold))
    reach(path, reach_s, (0.0, 0.018, 0.0), (GRASP_PITCH, 0.0, -4.0), OPEN, FLASH_GRAB)
    path.item(at_chest, chest, chest_rot, FLASH_FIST, stop=True)
    path.curl(click_at - 0.10, FLASH_FIST)
    path.curl(click_at, FLASH_CLICK, stop=True)
    path.curl(click_at + 0.13, FLASH_FIST, stop=True)
    path.item(leave, chest, chest_rot, stop=True)
    path.item(arrive, hold, hold_rot, FLASH_FIST, stop=True)
    path.attach(contact, 0.0, stop=True).attach(contact + GLIDE, 1.0, stop=True)
    last_burst = max(start + length for start, length in FLICKER_BURSTS)
    duration = max(arrive, click_at + last_burst) + 0.10         # o filamento leva ~60 ms para assentar depois da rajada
    events = [ev(0.05, "sound", "hand_reach"), ev(contact, "contact", essential=True),
              ev(contact, "show", ("R", C.ITEM_FLASHLIGHT), essential=True), ev(click_at, "light_on", essential=True)]
    events += [ev(click_at + start, "burst", index) for index, (start, _) in enumerate(FLICKER_BURSTS)]
    return Clip("lantern_first", duration, path.tracks(), events,
                meta={"side": "R", "kind": C.ITEM_FLASHLIGHT, "grasp": "R", "world_item": True, "rest": True})


# ---------------------------------------------------------------------------
# Pilha: recolher na palma, olhar, guardar (mão esquerda)
# ---------------------------------------------------------------------------
def battery_pickup(reach_s=REACH_DEFAULT):
    path = Path("L", C.ITEM_BATTERY)
    contact = reach_s + 0.06
    lift = reach_s + GRASP_DWELL
    show, show_rot = (-0.100, -0.050, -0.335), (-14.0, -8.0, 4.0)
    at_show = lift + move_time(math.dist(GRASP_NOMINAL, show))
    look = at_show + 0.25                                  # ESTIMADO: o tempo de olhar a pilha na palma
    reach(path, reach_s, (0.0, 0.016, 0.0), (GRASP_PITCH, 2.0, 4.0), OPEN, CUP)
    path.item(at_show, show, show_rot, CUP, stop=True)           # no caminho a mão gira meio giro: palma de lado
    path.item(look, show, show_rot, CUP, stop=True)
    end = withdraw(path, look)
    path.attach(contact, 0.0, stop=True).attach(contact + GLIDE, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(contact, "contact", essential=True),
              ev(contact, "show", ("L", C.ITEM_BATTERY), essential=True),
              ev(look + 0.30, "hide", "L"), ev(end - 0.2, "sound", "cloth_rustle_1")]
    return Clip("battery_pickup", end, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_BATTERY, "grasp": "L", "world_item": True, "rest": True})


# ---------------------------------------------------------------------------
# Chave: erguer o chaveiro e balançar uma vez (mão esquerda)
# ---------------------------------------------------------------------------
def key_pickup(reach_s=REACH_DEFAULT):
    path = Path("L", C.ITEM_KEY)
    contact = reach_s + 0.06
    lift = reach_s + GRASP_DWELL
    hang = HOLD_ITEM[("L", C.ITEM_KEY)][0]
    flick, swing = (-0.150, -0.020, -0.390), (-0.236, -0.030, -0.385)
    at_hang = lift + move_time(math.dist(GRASP_NOMINAL, hang))
    reach(path, reach_s, (0.0, 0.015, 0.0), (GRASP_PITCH, 2.0, 4.0), OPEN, PINCH)
    path.item(at_hang, hang, (0.0, 0.0, 0.0), PINCH, stop=True)
    # o puxão que faz o chaveiro balançar: um meio ciclo de punho de ~4 Hz, sem parar nas pontas
    path.item(at_hang + 0.12, flick, (0.0, 0.0, 0.0), PINCH)
    path.item(at_hang + 0.24, swing, (0.0, 0.0, 0.0), PINCH)
    path.item(at_hang + 0.38, hang, (0.0, 0.0, 0.0), PINCH, stop=True)
    end = withdraw(path, at_hang + 0.40)
    path.attach(contact, 0.0, stop=True).attach(contact + GLIDE, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(contact, "contact", essential=True),
              ev(contact, "show", ("L", C.ITEM_KEY), essential=True),
              ev(at_hang + 0.17, "sound", "key_jingle"), ev(at_hang + 0.40 + 0.30, "hide", "L")]
    return Clip("key_pickup", end, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_KEY, "grasp": "L", "world_item": True, "rest": True})


# ---------------------------------------------------------------------------
# Mapa: pegar dobrado, desdobrar em dois tempos, mostrar aberto (mão esquerda)
# ---------------------------------------------------------------------------
FOLDED = 174.0          # graus em cada dobra do mapa fechado
UNFOLD_TIME = 0.40      # ESTIMADO: cada dobra do mapa abre em ~0,4 s (o painel segue a mola de `Handhelds`)


def map_pickup(reach_s=REACH_DEFAULT):
    path = Path("L", C.ITEM_MAP)
    contact = reach_s + 0.06
    lift = reach_s + GRASP_DWELL
    held, held_rot = (-0.205, -0.075, -0.380), (-18.0, 10.0, 4.0)
    shown, shown_rot = HOLD_ITEM[("L", C.ITEM_MAP)]
    at_held = lift + move_time(math.dist(GRASP_NOMINAL, held))
    at_shown = at_held + move_time(math.dist(held, shown))
    reach(path, reach_s, (0.0, 0.016, 0.0), (GRASP_PITCH, 2.0, 4.0), OPEN, PINCH)
    path.item(at_held, held, held_rot, PINCH, stop=True)
    path.item(at_shown, shown, shown_rot, PINCH, stop=True)
    first = at_held - 0.25                      # a primeira dobra abre ainda subindo
    second = first + 0.32
    path.extra("fold1", 0.0, FOLDED, stop=True).extra("fold2", 0.0, -FOLDED, stop=True)
    path.extra("fold2", first, -FOLDED, stop=True).extra("fold2", first + UNFOLD_TIME, 0.0, stop=True)
    path.extra("fold1", second, FOLDED, stop=True).extra("fold1", second + UNFOLD_TIME, 0.0, stop=True)
    end = withdraw(path, at_shown + 0.15)
    path.attach(contact, 0.0, stop=True).attach(contact + GLIDE, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(contact, "contact", essential=True),
              ev(contact, "show", ("L", C.ITEM_MAP), essential=True),
              ev(first + 0.1, "sound", "map_unfold"), ev(second + 0.1, "sound", "map_unfold"),
              ev(at_shown + 0.15 + 0.30, "hide", "L")]
    return Clip("map_pickup", end, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_MAP, "grasp": "L", "world_item": True, "rest": True})


# ---------------------------------------------------------------------------
# Anotação: folha até o rosto (mão esquerda). A folha no chão sai do lugar; a presa na parede, não.
# ---------------------------------------------------------------------------
def note_pickup(reach_s=REACH_DEFAULT):
    path = Path("L", C.ITEM_NOTE)
    contact = reach_s + 0.06
    lift = reach_s + GRASP_DWELL
    face, face_rot = FACE_ITEM[C.ITEM_NOTE]
    at_face = lift + move_time(math.dist(GRASP_NOMINAL, face))
    reach(path, reach_s, (0.0, 0.012, 0.0), (GRASP_PITCH, 2.0, 4.0), OPEN, HOLD_SHEET)
    path.item(at_face, face, face_rot, HOLD_SHEET, stop=True)
    path.attach(contact, 0.0, stop=True).attach(contact + GLIDE, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(contact, "contact", essential=True),
              ev(contact, "show", ("L", C.ITEM_NOTE), essential=True), ev(contact + 0.02, "sound", "paper_pick"),
              ev(at_face, "open", essential=True)]
    return Clip("note_pickup", at_face, path.tracks(), events,
                meta={"side": "L", "kind": C.ITEM_NOTE, "grasp": "L", "world_item": True, "rest": True})


def note_wall(reach_s=REACH_DEFAULT):
    """Nota presa na parede: a ponta dos dedos toca a folha e o rosto se aproxima (o campo de visão fecha)."""
    path = Path("L", C.ITEM_NOTE)
    touch_curl = (0.2, 0.15, 0.55, 0.6, 0.6)
    path.rest(0.0, HANG_ROT["L"], RELAX, w=0.0)
    path.weight(0.30 * reach_s, 1.0)
    path.curl(0.60 * reach_s, OPEN)
    path.hand(reach_s, (0.0, 0.0, 0.0), (-20.0, 2.0, 0.0), touch_curl, stop=True, space="grasp")
    zoom = move_time(0.15)
    path.extra("zoom", reach_s - 0.12, 0.0, stop=True).extra("zoom", reach_s - 0.12 + zoom, 1.0, stop=True)
    events = [ev(0.04, "sound", "hand_reach"), ev(reach_s + 0.02, "touch", essential=True),
              ev(reach_s + 0.04, "sound", "paper_pick"), ev(reach_s - 0.12 + zoom, "open", essential=True)]
    return Clip("note_wall", reach_s - 0.12 + zoom, path.tracks(), events,
                meta={"side": "L", "kind": None, "grasp": "L", "world_item": False, "rest": True})


def note_putback():
    """O leitor fechou: a folha volta ao lugar onde estava e a mão recua."""
    path = Path("L", C.ITEM_NOTE)
    face, face_rot = FACE_ITEM[C.ITEM_NOTE]
    back = move_time(math.dist(GRASP_NOMINAL, face))
    path.item(0.00, face, face_rot, HOLD_SHEET, stop=True)
    path.hand(back, (0.0, 0.012, 0.0), (-8.0, 2.0, 0.0), HOLD_SHEET, stop=True, space="grasp")
    path.curl(back + 0.06, OPEN, stop=True)
    end = withdraw(path, back + 0.10)
    path.attach(0.00, 1.0, stop=True).attach(back * 0.5, 1.0).attach(back, 0.0, stop=True)
    events = [ev(back, "putback", essential=True), ev(back + 0.02, "sound", "paper_pick")]
    return Clip("note_putback", end, path.tracks(), events, interruptible=True,
                meta={"side": "L", "kind": C.ITEM_NOTE, "grasp": "L", "world_item": True, "rest": True})


def note_retreat():
    """Nota presa na parede: a mão recua e o campo de visão volta ao normal."""
    path = Path("L", C.ITEM_NOTE)
    out = move_time(0.40)
    path.hand(0.00, (0.0, 0.0, 0.0), (-20.0, 2.0, 0.0), w=1.0, stop=True, space="grasp")
    path.rest(out, HANG_ROT["L"], OPEN, stop=True)
    path.curl(out * 0.5, OPEN, stop=True)
    path.weight(out * 0.8, 1.0).weight(out, 0.0, stop=True)
    path.extra("zoom", 0.0, 1.0, stop=True).extra("zoom", out * 0.9, 0.0, stop=True)
    return Clip("note_retreat", out, path.tracks(), [], interruptible=True,
                meta={"side": "L", "kind": None, "grasp": "L", "rest": True})


def note_to_hold():
    """Leitor fechado com a folha vinda da roda: ela volta da frente do rosto para a posição de segurar."""
    path = Path("L", C.ITEM_NOTE)
    pos, rot = HOLD_ITEM[("L", C.ITEM_NOTE)]
    seconds = move_time(math.dist(FACE_ITEM[C.ITEM_NOTE][0], pos))
    path.item(0.00, *FACE_ITEM[C.ITEM_NOTE], HOLD_SHEET, stop=True)
    path.item(seconds, pos, rot, HOLD_SHEET, stop=True)
    return Clip("note_to_hold", seconds, path.tracks(), [ev(0.02, "sound", "paper_pick")],
                meta={"side": "L", "kind": C.ITEM_NOTE})


def note_raise(from_pocket):
    """Anotação do inventário: a folha sobe até o rosto (da posição de segurar, ou de baixo, do bolso)."""
    path = Path("L", C.ITEM_NOTE)
    pos, rot = HOLD_ITEM[("L", C.ITEM_NOTE)]
    face, face_rot = FACE_ITEM[C.ITEM_NOTE]
    if from_pocket:
        below = (pos[0] - 0.06, pos[1] - 0.26, pos[2] + 0.05)
        up = move_time(math.dist(below, face))
        path.item(0.00, below, (rot[0] - 14.0, rot[1], rot[2] - 8.0), HOLD_SHEET, w=0.0)
        path.weight(up * 0.3, 1.0)
        path.item(up, face, face_rot, HOLD_SHEET, stop=True)
        duration = up
    else:
        duration = move_time(math.dist(pos, face))
        path.item(0.00, pos, rot, HOLD_SHEET, stop=True)
        path.item(duration, face, face_rot, HOLD_SHEET, stop=True)
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
    gone = (pos[0] - 0.08, pos[1] - 0.26, pos[2] + 0.06)
    seconds = EXIT_FACTOR * move_time(math.dist(pos, gone))          # só sai do quadro: sem alvo a acertar
    path.item(0.00, pos, rot, HOLD_CURL[kind], stop=True)
    path.item(seconds, gone, (rot[0] - 14.0, rot[1], rot[2] + 8.0), HOLD_CURL[kind], stop=True)
    path.weight(seconds * 0.5, 1.0).weight(seconds, 0.0, stop=True)
    events = [ev(seconds, "hide", "L", essential=True), ev(seconds, "set_left", None, essential=True)]
    return Clip(f"stow_{kind.lower()}", seconds, path.tracks(), events, interruptible=True,
                meta={"side": "L", "kind": kind})


def draw(kind):
    """A mão esquerda traz o item de baixo para a posição de segurar."""
    path = Path("L", kind)
    pos, rot = HOLD_ITEM[("L", kind)]
    below = (pos[0] - 0.06, pos[1] - 0.26, pos[2] + 0.05)
    seconds = move_time(math.dist(pos, below))
    path.item(0.00, below, (rot[0] - 14.0, rot[1], rot[2] - 8.0), HOLD_CURL[kind], w=0.0, stop=True)
    path.weight(seconds * 0.25, 1.0)
    path.item(seconds, pos, rot, HOLD_CURL[kind], stop=True)
    sound = {C.ITEM_KEY: "key_jingle", C.ITEM_MAP: "map_unfold", C.ITEM_NOTE: "paper_pick",
             C.ITEM_BATTERY: "cloth_rustle_2"}[kind]
    events = [ev(0.02, "set_left", kind, essential=True), ev(0.02, "show", ("L", kind), essential=True),
              ev(0.10, "sound", sound, essential=False)]
    return Clip(f"draw_{kind.lower()}", seconds, path.tracks(), events, interruptible=True,
                meta={"side": "L", "kind": kind})


MAP_NEAR = NEAR_ITEM[C.ITEM_MAP]


def map_near():
    """E sem alvo com o mapa na mão: aproxima do rosto."""
    path = Path("L", C.ITEM_MAP)
    pos, rot = HOLD_ITEM[("L", C.ITEM_MAP)]
    seconds = move_time(math.dist(pos, MAP_NEAR[0]))
    path.item(0.00, pos, rot, PINCH, stop=True)
    path.item(seconds, *MAP_NEAR, PINCH, stop=True)
    return Clip("map_near", seconds, path.tracks(), [ev(0.02, "sound", "map_unfold")],
                meta={"side": "L", "kind": C.ITEM_MAP})


def map_back():
    path = Path("L", C.ITEM_MAP)
    pos, rot = HOLD_ITEM[("L", C.ITEM_MAP)]
    seconds = move_time(math.dist(pos, MAP_NEAR[0]))
    path.item(0.00, *MAP_NEAR, PINCH, stop=True)
    path.item(seconds, pos, rot, PINCH, stop=True)
    return Clip("map_back", seconds, path.tracks(), [], meta={"side": "L", "kind": C.ITEM_MAP})


# ---------------------------------------------------------------------------
# Trocar as pilhas (R): as duas mãos
# ---------------------------------------------------------------------------
SWAP_TILT = ((0.045, -0.125, -0.400), with_roll((-58.0, 12.0, -10.0)))     # lanterna com a tampa para cima e para trás
TAIL_OPENING = 0.057                                              # z da boca da lanterna no referencial do viewmodel
CELL_HALF = 0.032


def _cell_on_axis(z):
    """Pose da pilha alinhada ao eixo da lanterna inclinada, com o centro em `z` (referencial do viewmodel)."""
    matrix = pose_matrix(*SWAP_TILT) @ pose_matrix((0.0, 0.0, z), (0.0, 90.0, 0.0))     # o eixo X da pilha segue o cano
    return tuple(matrix.translation), tuple(math.degrees(a) for a in matrix.to_euler("XYZ"))


def swap(left_start, left_end):
    """A direita abaixa e gira a lanterna, a esquerda traz a pilha, a tampa abre e fecha e a luz volta.

    As duas mãos saem juntas (ação bimanual: a que segura posiciona o objeto e a que age chega logo depois):
    a direita termina de inclinar a lanterna antes de a esquerda alinhar a pilha à boca.

    `left_start`: o que a esquerda já segura (a pilha na palma) ou None (a pilha vem do bolso).
    `left_end`: o que a esquerda segura depois (a próxima pilha) ou None."""
    right = Path("R", C.ITEM_FLASHLIGHT)
    left = Path("L", C.ITEM_BATTERY)
    hold, hold_rot = HOLD_ITEM[("R", C.ITEM_FLASHLIGHT)]
    tilted, tilted_rot = SWAP_TILT
    tilt = move_time(math.dist(hold, tilted))                    # a direita inclina a lanterna
    above = TAIL_OPENING + CELL_HALF + 0.05
    lined_up = TAIL_OPENING + CELL_HALF + 0.006
    inside = TAIL_OPENING - CELL_HALF + 0.004
    pos_left = HOLD_ITEM[("L", C.ITEM_BATTERY)][0]
    from_palm = left_start == C.ITEM_BATTERY
    start_left = pos_left if from_palm else (-0.19, -0.30, -0.27)
    arrive = move_time(math.dist(start_left, _cell_on_axis(above + 0.06)[0]))      # a esquerda chega sobre a boca
    cap_open = (max(0.0, tilt - 0.14), tilt + 0.06)              # a tampa abre quando a lanterna acaba de inclinar
    t_lined = arrive + 0.10                                       # alinha com a boca
    t_in = t_lined + 0.30                                         # e desce pelo cano
    cap_close = (t_in + 0.04, t_in + 0.24)
    t_back = t_in + 0.04                                          # a direita volta a segurar quando a esquerda já se afasta
    t_hold = t_back + move_time(math.dist(hold, tilted))
    click = t_hold - 0.02
    right.item(0.00, hold, hold_rot, FLASH_FIST, stop=True)
    right.item(tilt, tilted, tilted_rot, FLASH_FIST, stop=True)
    right.item(t_back, tilted, tilted_rot, FLASH_FIST, stop=True)
    right.item(t_hold, hold, hold_rot, FLASH_FIST, stop=True)
    right.curl(click - 0.12, FLASH_FIST).curl(click, FLASH_CLICK, stop=True).curl(click + 0.09, FLASH_FIST)
    right.extra("cap", 0.0, 0.0, stop=True).extra("cap", cap_open[0], 0.0, stop=True).extra("cap", cap_open[1], 105.0, stop=True)
    right.extra("cap", cap_close[0], 105.0, stop=True).extra("cap", cap_close[1], 0.0, stop=True)
    if from_palm:
        left.item(0.00, pos_left, HOLD_ITEM[("L", C.ITEM_BATTERY)][1], CUP, stop=True)
    else:
        left.item(0.00, start_left, (-20.0, 0.0, 0.0), CUP, w=0.0)
        left.weight(arrive * 0.3, 1.0)
    left.item(arrive, *_cell_on_axis(above + 0.06), CUP, stop=True)
    left.item(t_lined, *_cell_on_axis(lined_up + 0.002), CUP, stop=True)
    left.item(t_in, *_cell_on_axis(inside), CUP, stop=True)
    leave = t_in + 0.06
    if left_end == C.ITEM_BATTERY:                                      # sobrou outra pilha: volta à palma
        pos, rot = HOLD_ITEM[("L", C.ITEM_BATTERY)]
        left.item(leave, *_cell_on_axis(inside), CUP, stop=True)
        left.item(max(t_hold, leave + move_time(0.2)), pos, rot, CUP, stop=True)
        duration = max(t_hold, leave + move_time(0.2))
    else:
        out = (-0.05, -0.20, -0.28)
        left.item(leave, *_cell_on_axis(inside), CUP, stop=True)
        left.item(leave + move_time(0.2), out, (-40.0, 40.0, 0.0), OPEN, stop=True)
        left.weight(leave + 0.10, 1.0).weight(leave + move_time(0.2), 0.0, stop=True)
        duration = max(t_hold, leave + move_time(0.2))
    left.attach(0.0, 1.0, stop=True)
    duration = max(duration, click + 0.10) + 0.04
    events = [ev(0.00, "swap_begin", essential=True), ev(0.02, "sound", "hand_reach"),
              ev(arrive, "sound", "battery_clack"), ev(t_in, "swap_insert", essential=True), ev(t_in + 0.02, "hide", "L"),
              ev(cap_close[1], "sound", "battery_clack"), ev(click - 0.02, "swap_end", essential=True),
              ev(click, "light_on", essential=True)]
    events.append(ev(0.05, "show", ("L", C.ITEM_BATTERY), essential=True))
    if left_end == C.ITEM_BATTERY:
        events.append(ev(t_in + 0.10, "show", ("L", C.ITEM_BATTERY)))
    return Clip("swap", duration, merge(right, left), events,
                meta={"side": "R", "kind": C.ITEM_FLASHLIGHT, "left_end": left_end})


def refuse():
    """Sem pilha reserva ou com a pilha ainda boa: a direita inclina a lanterna para olhar a tampa e volta,
    a esquerda bate no bolso. Curto, sem fala."""
    right = Path("R", C.ITEM_FLASHLIGHT)
    hold, hold_rot = HOLD_ITEM[("R", C.ITEM_FLASHLIGHT)]
    look, look_rot = (0.105, -0.115, -0.300), with_roll((-24.0, 8.0, -4.0))
    right.item(0.00, hold, hold_rot, FLASH_FIST, stop=True)
    right.item(0.22, look, look_rot, FLASH_FIST, stop=True)
    right.item(0.36, look, look_rot, FLASH_FIST, stop=True)
    right.item(0.62, hold, hold_rot, FLASH_FIST, stop=True)
    events = [ev(0.22, "sound", "cloth_rustle_3")]
    return Clip("refuse", 0.66, right.tracks(), events, interruptible=True,
                meta={"side": "R", "kind": C.ITEM_FLASHLIGHT})
