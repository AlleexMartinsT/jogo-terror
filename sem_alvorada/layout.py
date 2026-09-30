"""Planta da casa: fonte única de geometria para modelagem, colisão, IA e som.

Sem dependência de bpy. Tudo em metros. Rua ao sul (y=0), fundos ao norte (y=10).

  Andar 0 (z=0)                           Andar 1 (z=2.8)
  y=10 +------+---+----------+                +------+---+----------+
       | den  |   | cozinha  |                |master|   | escritó- |
       |      | H |          |   +-------+    |      | H | rio      |
   y=6 +--d---+ A |          |   |garagem|    +------+ A +----------+
       | sala | L +---arco---+   |       |    | quarto| L | banheiro |
       |      | L | jantar   |   |       |    | crianç| L |          |
   y=0 +------+---+----------+   +-------+    +------+---+----------+
       x=0    5   8         12  18.5           x=0    5   8         12

A escada sobe para o norte no lado oeste do hall (x 5.08-6.12, y 3.2-7.4).

Este módulo também deriva: paredes com vãos (wall_pieces), retângulos de piso,
grafo de cômodos (para propagação de som) e helpers de porta.
"""
import math
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------
# Medidas estruturais
# --------------------------------------------------------------------------
LEVEL_Z = {0: 0.0, 1: 2.8}      # altura do piso acabado de cada andar
CEIL_Z = {0: 2.6, 1: 5.4}       # altura do forro
SLAB_BOTTOM = 2.6               # laje entre andares: 2.6 .. 2.8
GARAGE_WALL_TOP = 2.9
WALL_T_INT = 0.15
WALL_T_EXT = 0.25
DOOR_H = 2.05
ARCH_H = 2.25
WINDOW_SILL = 0.9
WINDOW_H = 1.2
ROOF = {"eave_z": 5.4, "ridge_z": 7.5, "overhang": 0.55,
        "garage_eave_z": 2.9, "garage_ridge_z": 4.4}   # cumeeira ao longo de X (empena leste/oeste)


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self):
        return self.x1 - self.x0

    @property
    def h(self):
        return self.y1 - self.y0

    @property
    def center(self):
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def contains(self, x, y, margin=0.0):
        return (self.x0 - margin) <= x <= (self.x1 + margin) and (self.y0 - margin) <= y <= (self.y1 + margin)

    def inflate(self, m):
        return Rect(self.x0 - m, self.y0 - m, self.x1 + m, self.y1 + m)

    def overlaps(self, o):
        return self.x0 < o.x1 and o.x0 < self.x1 and self.y0 < o.y1 and o.y0 < self.y1

    def as_tuple(self):
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True)
class Room:
    id: str
    nome: str                # pt-BR
    level: int
    rect: Rect
    surface: str             # conventions.SURFACES (som de passos)
    ambient: float           # ruído de fundo 0..1 (mascara o ruído do jogador)
    floor_mat: str
    wall_mat: str


ROOMS = {r.id: r for r in [
    Room("hall_g", "Hall de entrada", 0, Rect(5, 0, 8, 10), "wood", 0.04, "floor_wood_dark", "wall_wallpaper"),
    Room("living", "Sala de estar", 0, Rect(0, 0, 5, 6), "carpet", 0.06, "floor_carpet", "wall_wallpaper"),
    Room("den", "Escritório", 0, Rect(0, 6, 5, 10), "wood", 0.05, "floor_wood", "wall_paint_dirty"),
    Room("dining", "Sala de jantar", 0, Rect(8, 0, 12, 5), "wood", 0.03, "floor_wood", "wall_wallpaper"),
    Room("kitchen", "Cozinha", 0, Rect(8, 5, 12, 10), "tile", 0.22, "floor_linoleum", "wall_paint_dirty"),
    Room("garage", "Garagem", 0, Rect(12, 0, 18.5, 7), "concrete", 0.12, "floor_concrete", "wall_garage"),
    Room("hall_u", "Corredor do andar de cima", 1, Rect(5, 0, 8, 10), "carpet", 0.03, "floor_carpet", "wall_wallpaper"),
    Room("kids", "Quarto da menina", 1, Rect(0, 0, 5, 5), "carpet", 0.03, "floor_carpet", "wall_paint_dirty"),
    Room("master", "Quarto do casal", 1, Rect(0, 5, 5, 10), "carpet", 0.02, "floor_carpet", "wall_wallpaper"),
    Room("bath", "Banheiro", 1, Rect(8, 0, 12, 5), "tile", 0.10, "floor_tile_bath", "wall_tile_bath"),
    Room("study", "Escritório de cima", 1, Rect(8, 5, 12, 10), "wood", 0.05, "floor_wood", "wall_paint_dirty"),
]}

HOUSE_RECT = Rect(0, 0, 12, 10)   # bloco principal (2 andares)


# --------------------------------------------------------------------------
# Aberturas (portas, arcos, janelas)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Opening:
    id: str
    kind: str        # 'door' | 'arch' | 'window' | 'garage_door'
    level: int
    axis: str        # 'x': parede corre ao longo de X (y constante = pos);  'y': corre ao longo de Y (x = pos)
    pos: float
    a: float         # início do vão ao longo do eixo
    b: float
    sill: float = 0.0
    height: float = DOOR_H
    hinge: str = "a"     # porta: dobradiça em 'a' ou 'b'
    swing: int = 1       # +1: abre para o lado +normal (axis 'x' -> +y ; axis 'y' -> +x); -1: oposto
    rooms: tuple = ()
    lock: str = ""       # '' | 'front' | 'back' | 'garage'  (portas trancadas de início)
    nome: str = ""

    @property
    def width(self):
        return self.b - self.a

    @property
    def mid(self):
        m = (self.a + self.b) / 2
        return (m, self.pos) if self.axis == "x" else (self.pos, m)


def _door(id, level, axis, pos, a, b, hinge, swing, rooms, lock="", nome=""):
    return Opening(id, "door", level, axis, pos, a, b, 0.0, DOOR_H, hinge, swing, rooms, lock, nome)


def _arch(id, level, axis, pos, a, b, rooms):
    return Opening(id, "arch", level, axis, pos, a, b, 0.0, ARCH_H, "a", 1, rooms)


def _win(id, level, axis, pos, a, b, room, sill=WINDOW_SILL, height=WINDOW_H):
    return Opening(id, "window", level, axis, pos, a, b, sill, height, "a", 1, (room,))


OPENINGS = {o.id: o for o in [
    # ---- andar 0 ----
    _door("front", 0, "x", 0.0, 6.05, 6.95, "a", 1, ("hall_g",), lock="front", nome="Porta da frente"),
    _door("back", 0, "x", 10.0, 8.6, 9.5, "a", -1, ("kitchen",), lock="back", nome="Porta dos fundos"),
    _door("living_hall", 0, "y", 5.0, 1.0, 1.9, "a", -1, ("living", "hall_g")),
    _door("den_hall", 0, "y", 5.0, 8.2, 9.1, "b", -1, ("den", "hall_g")),
    _door("den_living", 0, "x", 6.0, 1.5, 2.4, "a", 1, ("living", "den")),
    _arch("dining_hall", 0, "y", 8.0, 0.9, 2.6, ("hall_g", "dining")),
    _door("kitchen_hall", 0, "y", 8.0, 8.0, 8.9, "b", 1, ("hall_g", "kitchen")),
    _arch("dining_kitchen", 0, "x", 5.0, 9.0, 11.0, ("dining", "kitchen")),
    _door("garage_door", 0, "y", 12.0, 5.4, 6.3, "a", 1, ("kitchen", "garage"), lock="garage",
          nome="Porta da garagem"),
    Opening("garage_rollup", "garage_door", 0, "x", 0.0, 13.5, 17.5, 0.0, 2.2, "a", 1, ("garage",),
            nome="Portão da garagem"),
    _win("w_living_s", 0, "x", 0.0, 1.0, 3.0, "living"),
    _win("w_living_w", 0, "y", 0.0, 2.0, 4.0, "living"),
    _win("w_den_w", 0, "y", 0.0, 7.0, 9.0, "den"),
    _win("w_den_n", 0, "x", 10.0, 1.5, 3.5, "den"),
    _win("w_dining_s", 0, "x", 0.0, 9.0, 11.0, "dining"),
    _win("w_kitchen_n", 0, "x", 10.0, 10.0, 11.5, "kitchen"),
    _win("w_kitchen_e", 0, "y", 12.0, 8.0, 9.5, "kitchen"),
    _win("w_hall_g_n", 0, "x", 10.0, 6.0, 7.0, "hall_g"),
    _win("w_garage_e", 0, "y", 18.5, 3.0, 4.5, "garage"),
    # ---- andar 1 (sill/altura relativos ao piso do andar) ----
    _door("master_hall", 1, "y", 5.0, 8.2, 9.1, "b", -1, ("master", "hall_u")),
    _door("kids_hall", 1, "y", 5.0, 1.0, 1.9, "a", -1, ("kids", "hall_u")),
    _door("kids_master", 1, "x", 5.0, 3.6, 4.5, "a", 1, ("kids", "master")),
    _door("bath_hall", 1, "y", 8.0, 1.0, 1.9, "a", 1, ("hall_u", "bath")),
    _door("study_hall", 1, "y", 8.0, 8.2, 9.1, "b", 1, ("hall_u", "study")),
    _door("bath_study", 1, "x", 5.0, 10.5, 11.4, "a", 1, ("bath", "study")),
    _win("w_master_n", 1, "x", 10.0, 1.5, 3.5, "master"),
    _win("w_master_w", 1, "y", 0.0, 6.5, 8.5, "master"),
    _win("w_kids_s", 1, "x", 0.0, 1.5, 3.5, "kids"),
    _win("w_kids_w", 1, "y", 0.0, 1.5, 3.5, "kids"),
    _win("w_bath_s", 1, "x", 0.0, 9.5, 10.5, "bath", sill=1.4, height=0.6),
    _win("w_study_n", 1, "x", 10.0, 9.0, 11.0, "study"),
    _win("w_study_e", 1, "y", 12.0, 6.0, 8.0, "study"),
    _win("w_hall_u_n", 1, "x", 10.0, 6.0, 7.0, "hall_u"),
    _win("w_hall_u_s", 1, "x", 0.0, 6.25, 6.75, "hall_u"),
]}


def doors():
    return [o for o in OPENINGS.values() if o.kind == "door"]


def windows():
    return [o for o in OPENINGS.values() if o.kind == "window"]


# --------------------------------------------------------------------------
# Escada
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Stairs:
    x0: float = 5.08
    x1: float = 6.12
    y0: float = 3.2          # primeira subida (chão)
    y1: float = 7.4          # borda superior: dali pra frente é o piso do andar 1
    risers: int = 15
    z0: float = 0.0
    z1: float = 2.8

    @property
    def rise(self):
        return (self.z1 - self.z0) / self.risers

    @property
    def treads(self):
        return self.risers - 1

    @property
    def tread_depth(self):
        return (self.y1 - self.y0) / self.treads

    @property
    def hole(self):
        """Furo na laje do andar 1 (a escada sobe por ele)."""
        return Rect(5.0, self.y0, self.x1, self.y1)

    def contains(self, x, y):
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def height_at(self, y):
        """Altura do degrau em y (assume x dentro). Degrau i (1..treads) tem topo em i*rise."""
        if y < self.y0:
            return self.z0
        if y >= self.y1:
            return self.z1
        i = int((y - self.y0) / self.tread_depth) + 1
        return self.z0 + min(i, self.treads) * self.rise


STAIRS = Stairs()


def stairs_height(x, y):
    """Altura do piso na escada ou None se (x, y) está fora dela."""
    return STAIRS.height_at(y) if STAIRS.contains(x, y) else None


# --------------------------------------------------------------------------
# Âncoras: posições exatas de peças de cena que cutscenes e gameplay referenciam.
# O módulo props DEVE criar o objeto correspondente e um Empty 'Anchor_<nome>' ali.
# yaw = direção da FRENTE do objeto (convenção do Blender, ver conventions.yaw_dir).
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Anchor:
    name: str
    x: float
    y: float
    z: float
    yaw_deg: float
    note: str

    @property
    def pos(self):
        return (self.x, self.y, self.z)


ANCHORS = {a.name: a for a in [
    Anchor("bed_master", 1.30, 7.50, 2.8, -90, "Cama de casal 2.1x1.6 m, cabeceira na parede oeste (x=0), pés para leste. Lençol bagunçado."),
    Anchor("nightstand_flash", 0.40, 6.20, 2.8, -90, "Criado-mudo 0.5x0.5x0.55 m. A lanterna (Item_FLASHLIGHT) repousa em cima."),
    Anchor("nightstand_clock", 0.40, 8.80, 2.8, -90, "Criado-mudo com despertador digital vermelho (emissivo) marcando 6:47, mais um abajur."),
    Anchor("desk_den", 1.70, 9.35, 0.0, 180, "Escrivaninha 1.6x0.7 m contra a parede norte do escritório, cadeira ao sul. Item_KEY em cima."),
    Anchor("tv_living", 4.70, 3.90, 0.0, 90, "Console + TV de tubo na parede leste da sala, tela para oeste. Chiado branco emissivo."),
    Anchor("sofa_living", 2.10, 3.90, 0.0, -90, "Sofá de três lugares de frente para a TV."),
    Anchor("grandfather_clock", 3.60, 5.55, 0.0, 180, "Relógio de pé (2 m) na parede norte da sala. Parado às 6:12."),
    Anchor("fridge", 11.55, 7.00, 0.0, 90, "Geladeira na parede leste da cozinha (zumbido de fundo)."),
    Anchor("kitchen_counter", 10.20, 9.65, 0.0, 180, "Balcão com pia sob a janela norte da cozinha."),
    Anchor("study_desk", 10.70, 9.30, 2.8, 180, "Escrivaninha do escritório de cima, parede norte. Item_MAP em cima."),
    Anchor("kids_bed", 1.20, 3.90, 2.8, -90, "Caminha da menina (Emma), cabeceira na parede oeste. Coberta intocada."),
    Anchor("bath_sink", 9.10, 4.60, 2.8, 180, "Pia do banheiro com espelho rachado."),
    Anchor("car", 15.50, 3.00, 0.0, 180, "Sedã americano dos anos 90 (4.6x1.9 m), frente voltada para o portão (sul). Porta do motorista a leste."),
    Anchor("car_driver_eye", 15.95, 3.55, 1.20, 180, "Olhos do motorista dentro do carro."),
    Anchor("car_interact", 17.00, 3.60, 0.0, 90, "Ponto onde o jogador entra no carro (ao lado da porta do motorista)."),
    Anchor("workbench", 17.90, 3.20, 0.0, 90, "Bancada de trabalho sob a janela leste da garagem. Bateria e ferramentas."),
]}

# --------------------------------------------------------------------------
# Jogador e entidade
# --------------------------------------------------------------------------
PLAYER_START = (1.9, 5.85, 2.8)     # ao lado da cama, em pé
PLAYER_START_YAW_DEG = -90.0        # olhando para leste (a porta do quarto)
ENTITY_SPAWN = (6.5, 9.3, 2.8)      # fundo do corredor de cima
ENTITY_FIRST_SIGHT = (6.5, 8.9, 2.8)   # onde a cutscene do apagão mostra a entidade
GARAGE_ENTRY = (12.6, 5.85, 0.0)       # logo após a porta da garagem

# --------------------------------------------------------------------------
# Exterior (o mundo lá fora é só escuridão, mas existe: o final atravessa a rua)
# --------------------------------------------------------------------------
ROAD = Rect(-45.0, -14.5, 70.0, -7.5)            # asfalto, corre ao longo de X
SIDEWALK = Rect(-45.0, -7.5, 70.0, -5.5)
DRIVEWAY = Rect(13.5, -7.5, 17.5, 0.0)           # do portão da garagem até a rua
LAWN_FRONT = Rect(-45.0, -5.5, 70.0, 0.0)
YARD_BACK = Rect(-45.0, 10.0, 70.0, 45.0)
NEIGHBOR_LOTS = [Rect(-34, -40, -18, -24), Rect(-6, -40, 10, -24), Rect(24, -40, 42, -24), Rect(50, -40, 66, -24)]
ENTITY_ROAD_POS = (15.5, -11.0, 0.0)             # onde ele espera no final
# Sol que não nasceu: disco preto com uma coroa fina de luz, baixo no horizonte nordeste.
# azimute medido do norte (+Y) para leste (+X).
SUN_RING = {"azimuth_deg": 38.0, "elevation_deg": 9.0, "distance": 140.0, "radius_deg": 3.2}


# --------------------------------------------------------------------------
# Itens: posição APROXIMADA (o objeto Item_* no .blend é a verdade).
# room, x, y, z(superfície onde repousa), dica de móvel
# --------------------------------------------------------------------------
ITEM_SPOTS = {
    "FLASHLIGHT": ("master", 0.40, 6.20, 3.36, "em cima do criado-mudo esquerdo (nightstand_flash)"),
    "KEY": ("den", 1.95, 9.35, 0.79, "em cima da escrivaninha, ao lado da luminária"),
    "MAP": ("study", 10.60, 9.30, 3.58, "em cima da escrivaninha, dobrado sobre um caderno"),
    "BATTERY_1": ("kids", 0.55, 0.60, 3.30, "na prateleira baixa de brinquedos"),
    "BATTERY_2": ("bath", 9.10, 4.55, 3.72, "no balcão da pia"),
    "BATTERY_3": ("living", 4.70, 3.30, 0.55, "na gaveta aberta do console da TV"),
    "BATTERY_4": ("kitchen", 11.10, 9.65, 0.93, "no balcão, perto da pia"),
    "BATTERY_5": ("garage", 17.90, 2.60, 0.95, "na bancada de trabalho"),
    "NOTE_1": ("master", 0.40, 8.80, 3.36, "no criado-mudo direito, sob o despertador"),
    "NOTE_2": ("kids", 1.20, 3.90, 3.40, "sobre a cama da menina"),
    "NOTE_3": ("living", 2.10, 4.60, 0.45, "na mesinha de centro"),
    "NOTE_4": ("den", 0.60, 9.30, 0.80, "colada no quadro de cortiça"),
    "NOTE_5": ("kitchen", 9.00, 6.20, 0.93, "na mesa/geladeira da cozinha"),
    "NOTE_6": ("study", 11.30, 6.20, 3.60, "na estante do escritório de cima"),
    "NOTE_7": ("garage", 14.50, 6.65, 1.00, "na prateleira norte da garagem"),
}

# --------------------------------------------------------------------------
# Luzes de teto: (x, y) por cômodo. Nome: Light_<room>_c<n>
# --------------------------------------------------------------------------
CEILING_LIGHTS = {
    "hall_g": [(6.5, 1.6), (6.5, 8.6)],
    "living": [(2.5, 3.0)],
    "den": [(2.5, 8.0)],
    "dining": [(10.0, 2.5)],
    "kitchen": [(10.0, 7.5)],
    "garage": [(14.2, 3.5), (17.0, 3.5)],
    "hall_u": [(6.6, 1.8), (6.6, 8.8)],
    "kids": [(2.5, 2.5)],
    "master": [(2.5, 7.5)],
    "bath": [(10.0, 2.5)],
    "study": [(10.0, 7.5)],
}

# --------------------------------------------------------------------------
# Zonas que móveis não podem ocupar (folga de portas, escada, início do jogo)
# --------------------------------------------------------------------------
def door_clearance(o, depth=0.95):
    """Retângulo de folga dos dois lados de uma porta/arco."""
    if o.axis == "x":
        return Rect(o.a, o.pos - depth, o.b, o.pos + depth)
    return Rect(o.pos - depth, o.a, o.pos + depth, o.b)


def reserved_zones(level):
    zs = [door_clearance(o) for o in OPENINGS.values()
          if o.level == level and o.kind in ("door", "arch")]
    if level == 0:
        zs.append(Rect(STAIRS.x0 - 0.1, STAIRS.y0 - 0.9, STAIRS.x1 + 0.9, STAIRS.y1 + 0.9))
        zs.append(Rect(13.0, 4.9, 14.8, 7.0))     # passagem da porta da garagem até o carro
    else:
        zs.append(Rect(5.0, STAIRS.y0 - 0.9, 8.0, STAIRS.y1 + 0.9))
        sx, sy, _ = PLAYER_START
        zs.append(Rect(sx - 0.8, sy - 0.8, sx + 0.8, sy + 0.8))
    return zs


# --------------------------------------------------------------------------
# Consultas espaciais
# --------------------------------------------------------------------------
def level_of_z(z):
    return 1 if z >= (LEVEL_Z[1] - 0.5) else 0


def room_at(x, y, z=0.0, margin=0.0):
    """Cômodo em (x, y, z) ou None (fora da casa). Na escada devolve o hall do andar mais próximo."""
    lvl = level_of_z(z)
    for r in ROOMS.values():
        if r.level == lvl and r.rect.contains(x, y, margin):
            return r
    return None


def rooms_on_level(level):
    return [r for r in ROOMS.values() if r.level == level]


def door_mid(o):
    return o.mid


def door_transform(o):
    """Dobradiça e ângulos do pivô de uma porta.

    O pivô (Empty) fica em `hinge` (x, y, z do piso). O leque (mesh) é modelado no
    espaço local do pivô estendendo-se em +X por `width - 0.02`, altura +Z, espessura
    centrada em Y=0. Com rotation_euler.z = closed_yaw a folha fecha o vão; com
    open_yaw ela fica aberta a 90° para o lado `swing`.
    """
    assert o.kind == "door", o.id
    z = LEVEL_Z[o.level]
    if o.axis == "y":       # parede em x = pos, vão ao longo de Y
        hy = o.a if o.hinge == "a" else o.b
        hinge = (o.pos, hy, z)
        closed_dir = (0.0, 1.0) if o.hinge == "a" else (0.0, -1.0)
        open_dir = (float(o.swing), 0.0)
    else:                   # parede em y = pos, vão ao longo de X
        hx = o.a if o.hinge == "a" else o.b
        hinge = (hx, o.pos, z)
        closed_dir = (1.0, 0.0) if o.hinge == "a" else (-1.0, 0.0)
        open_dir = (0.0, float(o.swing))
    # A leaf modelada em +X local aponta para (cos yaw, sin yaw): yaw = atan2(dy, dx)
    closed_yaw = math.atan2(closed_dir[1], closed_dir[0])
    open_yaw = math.atan2(open_dir[1], open_dir[0])
    # escolhe o giro de 90° (nunca o de 270°)
    delta = (open_yaw - closed_yaw + math.pi) % (2 * math.pi) - math.pi
    open_yaw = closed_yaw + delta
    return {"hinge": hinge, "closed_yaw": closed_yaw, "open_yaw": open_yaw, "width": o.width}


# --------------------------------------------------------------------------
# Paredes derivadas
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class WallPiece:
    level: int
    axis: str
    pos: float
    a: float
    b: float
    z0: float
    z1: float
    thickness: float
    exterior: bool
    room_lo: str          # cômodo do lado -normal (vazio se exterior)
    room_hi: str
    kind: str = "full"    # 'full' | 'lintel' | 'sill'
    opening: str = ""     # id da abertura a que pertence (lintel/sill)

    def rect2d(self):
        h = self.thickness / 2
        if self.axis == "x":
            return Rect(self.a, self.pos - h, self.b, self.pos + h)
        return Rect(self.pos - h, self.a, self.pos + h, self.b)


def _room_edges(level):
    for r in rooms_on_level(level):
        rc = r.rect
        yield ("x", rc.y0, rc.x0, rc.x1, "hi", r.id)
        yield ("x", rc.y1, rc.x0, rc.x1, "lo", r.id)
        yield ("y", rc.x0, rc.y0, rc.y1, "hi", r.id)
        yield ("y", rc.x1, rc.y0, rc.y1, "lo", r.id)


def _wall_runs(level):
    """Trechos contínuos de parede: (axis, pos, a, b, room_lo, room_hi, exterior)."""
    groups = {}
    for axis, pos, a, b, side, rid in _room_edges(level):
        groups.setdefault((axis, round(pos, 3)), []).append((a, b, side, rid))
    runs = []
    for (axis, pos), edges in groups.items():
        pts = sorted({p for a, b, _, _ in edges for p in (a, b)})
        elem = []
        for p, q in zip(pts, pts[1:]):
            claims = [(s, rid) for a, b, s, rid in edges if a <= p + 1e-9 and b >= q - 1e-9]
            if not claims:
                continue
            lo = next((rid for s, rid in claims if s == "lo"), "")
            hi = next((rid for s, rid in claims if s == "hi"), "")
            elem.append([p, q, lo, hi])
        merged = []
        for p, q, lo, hi in elem:
            if merged and merged[-1][1] == p and merged[-1][2] == lo and merged[-1][3] == hi:
                merged[-1][1] = q
            else:
                merged.append([p, q, lo, hi])
        for p, q, lo, hi in merged:
            runs.append((axis, pos, p, q, lo, hi, not (lo and hi)))
    return runs


def _wall_top(level, exterior, lo, hi):
    if level == 0 and exterior and "garage" in (lo, hi):
        return GARAGE_WALL_TOP
    if level == 0 and exterior:
        return LEVEL_Z[1]
    return CEIL_Z[level]


def wall_pieces(level):
    """Todas as peças sólidas de parede de um andar, já com os vãos recortados."""
    out = []
    floor = LEVEL_Z[level]
    ops = [o for o in OPENINGS.values() if o.level == level]
    for axis, pos, a, b, lo, hi, ext in _wall_runs(level):
        t = WALL_T_EXT if ext else WALL_T_INT
        top = _wall_top(level, ext, lo, hi)
        here = sorted((o for o in ops if o.axis == axis and abs(o.pos - pos) < 1e-6
                       and o.a >= a - 1e-9 and o.b <= b + 1e-9), key=lambda o: o.a)
        cur = a
        for o in here:
            if o.a > cur + 1e-9:
                out.append(WallPiece(level, axis, pos, cur, o.a, floor, top, t, ext, lo, hi))
            over = floor + o.sill + o.height
            if over < top - 1e-9:
                out.append(WallPiece(level, axis, pos, o.a, o.b, over, top, t, ext, lo, hi, "lintel", o.id))
            if o.sill > 1e-9:
                out.append(WallPiece(level, axis, pos, o.a, o.b, floor, floor + o.sill, t, ext, lo, hi, "sill", o.id))
            cur = o.b
        if b > cur + 1e-9:
            out.append(WallPiece(level, axis, pos, cur, b, floor, top, t, ext, lo, hi))
    return out


def solid_rects(level):
    """Retângulos 2D de parede que bloqueiam o jogador em pé (sem lintel)."""
    return [p.rect2d() for p in wall_pieces(level) if p.kind != "lintel"]


# --------------------------------------------------------------------------
# Pisos e lajes
# --------------------------------------------------------------------------
def subtract_rect(r, hole):
    """r menos hole (hole inteiramente dentro de r ou cortando uma borda) -> lista de Rect."""
    if not r.overlaps(hole):
        return [r]
    out = []
    if hole.y0 > r.y0:
        out.append(Rect(r.x0, r.y0, r.x1, hole.y0))
    if hole.y1 < r.y1:
        out.append(Rect(r.x0, hole.y1, r.x1, r.y1))
    mid0, mid1 = max(r.y0, hole.y0), min(r.y1, hole.y1)
    if hole.x0 > r.x0:
        out.append(Rect(r.x0, mid0, hole.x0, mid1))
    if hole.x1 < r.x1:
        out.append(Rect(hole.x1, mid0, r.x1, mid1))
    return out


def floor_rects(level):
    """(room_id, Rect) do piso de cada cômodo. No andar 1 o furo da escada é subtraído."""
    out = []
    for r in rooms_on_level(level):
        if level == 1 and r.rect.overlaps(STAIRS.hole):
            out += [(r.id, p) for p in subtract_rect(r.rect, STAIRS.hole)]
        else:
            out.append((r.id, r.rect))
    return out


def ceiling_rects(level):
    """Forro de cada cômodo (mesma partição do piso do próprio andar, sem furo no andar 0
    exceto onde a escada passa: o forro do hall_g tem o furo da escada)."""
    out = []
    for r in rooms_on_level(level):
        if level == 0 and r.rect.overlaps(STAIRS.hole):
            out += [(r.id, p) for p in subtract_rect(r.rect, STAIRS.hole)]
        else:
            out.append((r.id, r.rect))
    return out


# --------------------------------------------------------------------------
# Grafo de cômodos (propagação do som e navegação grossa)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Link:
    a: str
    b: str
    kind: str           # 'door' | 'arch' | 'stairs'
    opening: str        # id da abertura ('' na escada)
    x: float
    y: float
    z: float


def links():
    out = []
    for o in OPENINGS.values():
        if o.kind in ("door", "arch") and len(o.rooms) == 2:
            x, y = o.mid
            out.append(Link(o.rooms[0], o.rooms[1], o.kind, o.id, x, y, LEVEL_Z[o.level]))
    out.append(Link("hall_g", "hall_u", "stairs", "", (STAIRS.x0 + STAIRS.x1) / 2,
                    (STAIRS.y0 + STAIRS.y1) / 2, 1.4))
    return out


def neighbors(room_id):
    res = []
    for l in links():
        if l.a == room_id:
            res.append((l.b, l))
        elif l.b == room_id:
            res.append((l.a, l))
    return res


def room_path(src, dst):
    """Menor caminho em número de saltos entre cômodos -> lista de Link (vazia se src==dst)."""
    if src == dst:
        return []
    from collections import deque
    prev = {src: None}
    q = deque([src])
    while q:
        cur = q.popleft()
        for nxt, l in neighbors(cur):
            if nxt not in prev:
                prev[nxt] = (cur, l)
                if nxt == dst:
                    path = []
                    n = dst
                    while prev[n]:
                        n, l2 = prev[n][0], prev[n][1]
                        path.append(l2)
                    return path[::-1]
                q.append(nxt)
    return None


# --------------------------------------------------------------------------
# Validação (rode: python -m sem_alvorada.layout)
# --------------------------------------------------------------------------
def validate():
    errs = []
    # cômodos do mesmo andar não se sobrepõem
    for lvl in (0, 1):
        rs = rooms_on_level(lvl)
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                if a.rect.overlaps(b.rect):
                    errs.append(f"cômodos sobrepostos: {a.id} x {b.id}")
    # cada abertura cai inteira dentro de uma parede existente e não colide com outra
    for lvl in (0, 1):
        runs = _wall_runs(lvl)
        for o in (x for x in OPENINGS.values() if x.level == lvl):
            ok = any(r[0] == o.axis and abs(r[1] - o.pos) < 1e-6 and r[2] - 1e-9 <= o.a and o.b <= r[3] + 1e-9
                     for r in runs)
            if not ok:
                errs.append(f"abertura '{o.id}' não cabe em nenhuma parede")
        ops = [x for x in OPENINGS.values() if x.level == lvl]
        for i, a in enumerate(ops):
            for b in ops[i + 1:]:
                if a.axis == b.axis and abs(a.pos - b.pos) < 1e-6 and a.a < b.b and b.a < a.b:
                    errs.append(f"aberturas sobrepostas: {a.id} x {b.id}")
    # portas/arcos ligam cômodos reais e vizinhos
    for o in OPENINGS.values():
        for rid in o.rooms:
            if rid not in ROOMS:
                errs.append(f"{o.id}: cômodo desconhecido {rid}")
    # nenhuma abertura na parede colada à escada
    for o in OPENINGS.values():
        if o.axis == "y" and abs(o.pos - 5.0) < 1e-6 and o.level == 0 and o.a < STAIRS.y1 and o.b > STAIRS.y0:
            errs.append(f"{o.id} bate na escada")
    # conectividade
    seen, stack = set(), ["master"]
    while stack:
        r = stack.pop()
        if r in seen:
            continue
        seen.add(r)
        stack += [n for n, _ in neighbors(r)]
    for r in ROOMS:
        if r not in seen:
            errs.append(f"cômodo inalcançável: {r}")
    # itens, âncoras e luzes dentro dos cômodos
    for k, (room, x, y, z, _) in ITEM_SPOTS.items():
        if not ROOMS[room].rect.contains(x, y):
            errs.append(f"item {k} fora de {room}")
    for name, rl in CEILING_LIGHTS.items():
        for (x, y) in rl:
            if not ROOMS[name].rect.contains(x, y):
                errs.append(f"luz de {name} fora do cômodo")
    r = room_at(*PLAYER_START[:2], PLAYER_START[2])
    if not r or r.id != "master":
        errs.append("PLAYER_START não está no quarto do casal")
    return errs


# --------------------------------------------------------------------------
# Mapa de depuração (PNG) — python -m sem_alvorada.layout
# --------------------------------------------------------------------------
def render_plan(path, scale=40, level=None):
    import numpy as np
    from tools import pngwrite
    W, H = int(19.5 * scale), int(10.5 * scale)
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = (14, 14, 18)

    def px(x, y):
        return int(round(x * scale)) + 4, H - 4 - int(round(y * scale))

    def fill(rc, col):
        (xa, yb), (xb, ya) = px(rc.x0, rc.y0), px(rc.x1, rc.y1)
        img[max(ya, 0):min(yb, H), max(xa, 0):min(xb, W)] = col

    levels = (0, 1) if level is None else (level,)
    for lvl in levels:
        off = 0
        for r in rooms_on_level(lvl):
            col = {"wood": (70, 52, 36), "carpet": (52, 62, 52), "tile": (70, 74, 80),
                   "concrete": (60, 60, 60)}[r.surface]
            if lvl == 1 and len(levels) == 2:
                col = tuple(int(c * 0.55) for c in col)
            fill(r.rect, col)
        for p in wall_pieces(lvl):
            if p.kind == "lintel":
                continue
            fill(p.rect2d(), (200, 200, 205) if lvl == 0 else (120, 120, 150))
        for o in OPENINGS.values():
            if o.level != lvl:
                continue
            col = {"door": (230, 170, 60), "arch": (110, 200, 110), "window": (80, 160, 255),
                   "garage_door": (220, 90, 90)}[o.kind]
            if o.axis == "x":
                fill(Rect(o.a, o.pos - 0.08, o.b, o.pos + 0.08), col)
            else:
                fill(Rect(o.pos - 0.08, o.a, o.pos + 0.08, o.b), col)
    fill(Rect(STAIRS.x0, STAIRS.y0, STAIRS.x1, STAIRS.y1), (180, 60, 180))
    for a in ANCHORS.values():
        fill(Rect(a.x - 0.12, a.y - 0.12, a.x + 0.12, a.y + 0.12), (255, 255, 0))
    for k, (room, x, y, z, _) in ITEM_SPOTS.items():
        col = (255, 60, 60) if k.startswith("BATTERY") else (60, 255, 255) if k in ("KEY", "MAP", "FLASHLIGHT") else (255, 255, 255)
        fill(Rect(x - 0.1, y - 0.1, x + 0.1, y + 0.1), col)
    sx, sy, _ = PLAYER_START
    fill(Rect(sx - 0.15, sy - 0.15, sx + 0.15, sy + 0.15), (60, 255, 60))
    ex, ey, _ = ENTITY_SPAWN
    fill(Rect(ex - 0.2, ey - 0.2, ex + 0.2, ey + 0.2), (255, 255, 255))
    pngwrite.write_png(path, img)
    return path


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    problems = validate()
    print(f"{len(ROOMS)} cômodos, {len(OPENINGS)} aberturas, "
          f"{len(wall_pieces(0))}+{len(wall_pieces(1))} peças de parede")
    for p in problems:
        print("ERRO:", p)
    if not problems:
        print("planta OK")
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")
    os.makedirs(out, exist_ok=True)
    print(render_plan(os.path.join(out, "planta_andar0.png"), level=0))
    print(render_plan(os.path.join(out, "planta_andar1.png"), level=1))
    sys.exit(1 if problems else 0)
