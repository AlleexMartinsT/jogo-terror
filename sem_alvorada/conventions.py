"""Vocabulário comum entre os módulos (nomes de objetos, propriedades, constantes).

Nada aqui importa bpy: pode ser lido por qualquer módulo e pelos testes.

Sistema de coordenadas: metros, Z para cima. A rua fica ao sul (y=0) e os fundos
ao norte (y=10). O sol deveria nascer a nordeste.

Yaw: é o rotation_euler.z do Blender. yaw=0 olha para +Y (norte), yaw=+90° olha
para -X (oeste), yaw=-90° olha para +X (leste). Direção = (-sin(yaw), cos(yaw)).
"""
import math

# --------------------------------------------------------------------------
# Coleções da cena
# --------------------------------------------------------------------------
COL_WORLD = "SA_World"        # casa, chão, teto, telhado, luzes fixas
COL_PROPS = "SA_Props"        # móveis e decoração
COL_ITEMS = "SA_Items"        # itens coletáveis e documentos
COL_ENTITY = "SA_Entity"      # a entidade
COL_CUTSCENE = "SA_Cutscene"  # câmeras e objetos que só existem em cutscenes
COL_PLAYER = "SA_Player"      # câmera do jogador, lanterna e viewmodel
COL_COLLISION = "SA_Collision"  # proxies de colisão (ocultos)

# --------------------------------------------------------------------------
# Propriedades customizadas (obj["sa_..."]) lidas pelo runtime
# --------------------------------------------------------------------------
P_COL = "sa_col"                # truthy => entra na colisão do jogador e da IA
P_INTERACT = "sa_interact"      # 'item' | 'door' | 'note' | 'car' | 'switch' | 'look'
P_ID = "sa_id"                  # id lógico (ex.: 'KEY', 'garage', 'NOTE_3')
P_PROMPT = "sa_prompt"          # texto curto da dica de interação (pt-BR)
P_ITEM = "sa_item"              # tipo de item: 'FLASHLIGHT' | 'KEY' | 'MAP' | 'BATTERY' | 'NOTE'
P_ROOM = "sa_room"              # id do cômodo (layout.ROOMS)
P_LIGHT_ENERGY = "sa_base_energy"   # energia base da luz (W); o runtime escala/pisca
P_LIGHT_FLICKER = "sa_flicker"      # 0..1, quanto a luz pisca
P_LIGHT_KIND = "sa_kind"            # 'ceiling' | 'lamp' | 'tv' | 'fluorescent' | 'window'
P_DOOR_CLOSED = "sa_closed_yaw"     # rotation_euler.z do pivô da porta fechada
P_DOOR_OPEN = "sa_open_yaw"         # idem, aberta
P_LOCK = "sa_lock"                  # '' | 'front' | 'back' | 'garage'
P_SURFACE = "sa_surface"            # material de piso (som de passos): ver SURFACES

# Prefixos de nome de objeto
N_DOOR = "Door_"          # Door_<id>  (Empty pivô na dobradiça)
N_WINDOW = "Window_"
N_LIGHT = "Light_"        # Light_<room>_<n>
N_ITEM = "Item_"          # Item_KEY, Item_BATTERY_1, Item_NOTE_3 ...
N_COL = "COL_"            # proxies de colisão
N_ANCHOR = "Anchor_"      # Anchor_<nome> (layout.ANCHORS)

# Objetos únicos, criados por módulos específicos
OBJ_PLAYER_CAM = "PlayerCam"
OBJ_FLASHLIGHT = "Flashlight"          # SPOT filho da câmera
OBJ_VIEW_FLASH = "ViewModel_Flashlight"  # mesh da lanterna na mão (props.viewmodel)
OBJ_ENTITY = "Entity"                  # Empty raiz da entidade (pés na origem, frente = +Y local)
OBJ_CUT_CAM = "CutsceneCam"
OBJ_CAR = "Car"
OBJ_GARAGE_ROLLUP = "GarageRollup"
OBJ_BODY = "PlayerBody"               # malha do corpo do jogador (primeira pessoa), na coleção do jogador
OBJ_BODY_RIG = "PlayerBody_Rig"        # armadura do corpo

# --------------------------------------------------------------------------
# Itens e objetivo
# --------------------------------------------------------------------------
ITEM_FLASHLIGHT = "FLASHLIGHT"
ITEM_KEY = "KEY"
ITEM_MAP = "MAP"
ITEM_BATTERY = "BATTERY"
ITEM_NOTE = "NOTE"

N_BATTERIES_IN_HOUSE = 5
# Para destrancar a porta da garagem (a entidade continua perseguindo):
GATE_REQUIRES = {ITEM_KEY: 1, ITEM_MAP: 1, ITEM_BATTERY: 3}   # baterias já ENCONTRADAS

N_NOTES = 7

# --------------------------------------------------------------------------
# Jogador
# --------------------------------------------------------------------------
PLAYER_EYE_STAND = 1.65
PLAYER_EYE_CROUCH = 1.05
PLAYER_RADIUS = 0.30
PLAYER_STEP_HEIGHT = 0.35
# Velocidades de uma pessoa de verdade (fase 4). Medidas em mocap da CMU (docs/FASE4.md): andar 0,93 a 1,75 m/s nas
# caminhadas em linha reta (1,3 normal, 1,67 rápido), correr 3,0 a 4,15 m/s, andar agachado 0,8 m/s (136_09, 136_10).
# Antes: 1,2 / 2,6 / 4,6 m/s; 2,6 é um trote (o passo de 1,15 m ficava curto e o pé deslizava) e 4,6 é de velocista.
SPEED_CROUCH = 0.8
SPEED_WALK = 1.7
SPEED_RUN = 4.0
ACCEL_START = 5.0         # m/s2, partida: ~70% do que 143_03 mede (7,2 m/s2 até 4,9 m/s em 0,68 s)
ACCEL_BRAKE = 6.0         # m/s2, teto da parada: 143_02 (corrida) freia a 7,8; 16_08 e 16_57 (corrida, parada suave) a 1,9 a 2,4
# Parar leva o mesmo tempo qualquer que seja a velocidade: 16_33 para de 0,9 m/s em 0,7 s (1,3 m/s2) e 143_02 de 5 m/s em
# 0,7 s (7,8 m/s2). A freada é a velocidade sobre este tempo, entre ACCEL_BRAKE_MIN e ACCEL_BRAKE.
STOP_TIME = 0.65
ACCEL_BRAKE_MIN = 1.2
# Escada: o ritmo é dos degraus. Medido em 83_27 a 83_35 (8 clipes, degraus de 12 a 16 cm): um degrau a cada 0,79 a 0,90 s
# (1,17 passo/s). Usamos 1,5 passo/s andando (ESTIMADO, 1,5 a 1,8 na literatura para subida confortável), 2,4 correndo e
# 1,1 agachado, vezes a profundidade do degrau do jogo (0,3 m): 0,45 / 0,72 / 0,33 m/s.
STAIRS_STEPS_PER_SECOND = {"walk": 1.5, "run": 2.5, "crouch": 1.1}
STAIRS_RATIO_WALK = 0.45 / 1.7        # velocidade na escada / velocidade no plano, andando e correndo (0,75 / 4,0)
STAIRS_RATIO_RUN = 0.75 / 4.0


def stairs_speed(speed):
    """Velocidade na escada de quem andaria a `speed` m/s no plano: a razão vai de andar (1,7) a correr (4,0). A entidade
    usa isto para manter na escada as mesmas razões que tem com o jogador no plano."""
    t = max(0.0, min(1.0, (speed - SPEED_WALK) / (SPEED_RUN - SPEED_WALK)))
    return speed * (STAIRS_RATIO_WALK + (STAIRS_RATIO_RUN - STAIRS_RATIO_WALK) * t)
STAMINA_MAX = 1.0
STAMINA_DRAIN = 0.22      # por segundo correndo
STAMINA_REGEN = 0.15      # por segundo
INTERACT_RANGE = 2.0
FOV_DEG = 72.0
REACH_MIN_STAMINA_TO_RUN = 0.15

# --------------------------------------------------------------------------
# Lanterna
# --------------------------------------------------------------------------
BATTERY_MAX = 1.0
FLASHLIGHT_FOUND_CHARGE = 0.78        # a lanterna do criado-mudo já foi usada: ao pegá-la a carga cai para isto
BATTERY_DRAIN_PER_SEC = 1.0 / 210.0   # ~3,5 min de luz por pilha
BATTERY_LOW = 0.25                    # abaixo disso a luz começa a falhar
BATTERY_CRITICAL = 0.08
START_SPARE_BATTERIES = 0
FLASH_SPOT_DEG = 48.0
FLASH_ENERGY = 900.0                  # W (spot do Blender); acima disso o cone estoura em branco nas paredes próximas
FLASH_RANGE_VISION = 18.0             # alcance em que a entidade "vê" a luz
DARK_VISION_RANGE = 5.5               # alcance de visão da entidade sem lanterna

# --------------------------------------------------------------------------
# RUÍDO (0..1 na fonte). Foco do jogo: ver docs/CONTRACT.md seção "Som e ruído".
# --------------------------------------------------------------------------
# Emitido pelo jogador, por ação:
NOISE_PLAYER = {
    "idle": 0.00,
    "breath_heavy": 0.06,      # sem fôlego
    "crouch_walk": 0.08,
    "walk": 0.30,
    "run": 0.75,
    "door_open": 0.30,
    "door_close": 0.35,
    "door_slam": 0.90,
    "door_creak": 0.55,        # dobradiça que range: atravessa um cômodo e meio, não a casa (ver engine/doors.py)
    "pickup": 0.15,
    "flash_click": 0.10,
    "battery_swap": 0.18,
    "key_jingle": 0.20,        # chaveiro na mão tilintando a cada passo de corrida
    "stairs_creak": 0.55,      # degrau que range
    "knock_over": 0.85,
}
# Multiplicador por tipo de piso (SURFACES) aplicado a passos:
SURFACES = ("wood", "carpet", "tile", "concrete", "stairs")
SURFACE_NOISE_MULT = {"wood": 1.0, "carpet": 0.55, "tile": 1.15, "concrete": 1.0, "stairs": 1.35}

# Emitido pela entidade (o que o JOGADOR ouve; a entidade também "vaza" presença):
NOISE_ENTITY = {
    "drone": 0.30,        # zumbido grave contínuo quando perto (some ao espreitar)
    "step_stalk": 0.10,
    "step_patrol": 0.35,
    "step_chase": 0.85,
    "breath": 0.12,
    "growl": 0.70,
    "scream": 1.00,
    "door_open": 0.40,
    "door_creak": 0.50,
    "door_break": 0.95,
}

# Ambiente: cada cômodo tem um ruído base (ver layout.ROOMS[..].ambient), que
# MASCARA o ruído do jogador. Eventos ambientais pontuais:
NOISE_AMBIENT_EVENTS = {
    "creak": 0.20,
    "thud": 0.40,
    "phone": 0.60,
    "tv_burst": 0.70,
    "clock_chime": 0.45,
    "glass": 0.65,
}

# Propagação
NOISE_DECAY_PER_M = 0.085         # atenuação linear por metro de caminho
NOISE_DOOR_CLOSED_LOSS = 0.35     # perda extra por porta fechada no caminho
NOISE_FLOOR_LOSS = 0.30           # perda ao mudar de andar
NOISE_MASK_FACTOR = 0.9           # o ruído ambiente do cômodo do ouvinte é subtraído com este peso

# --------------------------------------------------------------------------
# Entidade
# --------------------------------------------------------------------------
ENTITY_HEIGHT = 2.65
ENTITY_RADIUS = 0.38
# Mesmas razões de antes em relação ao modo equivalente do jogador (espreita/agachar 0,75, patrulha/andar 0,577,
# perseguição/correr 0,891), aplicadas às velocidades novas do jogador.
ENTITY_SPEED_STALK = 0.60
ENTITY_SPEED_PATROL = 0.98
ENTITY_SPEED_CHASE = 3.57         # 89% da corrida do jogador: dá pra fugir se houver fôlego
ENTITY_KILL_DISTANCE = 1.15
ENTITY_STATES = ("dormant", "patrol", "investigate", "stalk", "chase", "search", "attack")

# --------------------------------------------------------------------------
# Câmera / render
# --------------------------------------------------------------------------
RES_X, RES_Y = 1280, 720
TEX_SIZE_DEFAULT = 128        # texturas geradas: baixa resolução, estilo GoldSrc / Cry of Fear
TEX_SIZE_HI = 256

# Paleta base: fria, suja e dessaturada (Cry of Fear)
PALETTE = {
    "wall_beige": (0.34, 0.30, 0.24),
    "wall_green": (0.20, 0.24, 0.20),
    "wall_gray": (0.24, 0.24, 0.25),
    "wood_dark": (0.16, 0.10, 0.06),
    "wood_mid": (0.28, 0.18, 0.10),
    "carpet_brown": (0.20, 0.14, 0.10),
    "carpet_green": (0.12, 0.17, 0.13),
    "tile_white": (0.45, 0.46, 0.44),
    "tile_kitchen": (0.30, 0.28, 0.20),
    "concrete": (0.22, 0.22, 0.21),
    "metal": (0.30, 0.31, 0.33),
    "fabric_red": (0.28, 0.06, 0.05),
    "fabric_blue": (0.09, 0.12, 0.22),
    "fabric_gray": (0.18, 0.18, 0.19),
    "paper": (0.65, 0.62, 0.50),
    "black": (0.02, 0.02, 0.02),
    "rubber": (0.05, 0.05, 0.05),
    "blood": (0.22, 0.02, 0.02),
    "glass_dark": (0.02, 0.03, 0.04),
    "plaster_white": (0.55, 0.53, 0.47),
    "car_paint": (0.10, 0.16, 0.22),
    "skin_grey": (0.42, 0.40, 0.38),
    "emit_white": (1.0, 1.0, 1.0),
}

# Nomes canônicos de materiais que qualquer módulo pode pedir a matapi.get_material()
MATERIAL_NAMES = tuple(PALETTE.keys()) + (
    "wall_wallpaper", "wall_paint_dirty", "wall_tile_bath", "wall_garage", "wall_brick_ext",
    "floor_wood", "floor_wood_dark", "floor_carpet", "floor_linoleum", "floor_tile_bath",
    "floor_concrete", "ceiling", "roof_shingle", "door_wood", "trim_white", "stairs_wood",
    "glass_night", "curtain",
)

# --------------------------------------------------------------------------
# Orçamento de geometria (triângulos). Roda em EEVEE ao vivo; a lanterna projeta sombra, então a cena
# é desenhada duas vezes por quadro. Detalhe vale a pena, desperdício não.
# --------------------------------------------------------------------------
BUDGET_TRIS = {
    "prop": 25_000,          # móvel ou objeto comum
    "hero_prop": 60_000,     # peça que aparece de perto e de frente: cama, sofá, geladeira, escrivaninha
    "car": 90_000,
    "props_total": 650_000,
    "world_total": 450_000,  # casca, esquadrias, escada, telhado, exterior
    "scene_total": 1_200_000,
}

# --------------------------------------------------------------------------
# Helpers de direção
# --------------------------------------------------------------------------
def yaw_dir(yaw):
    """Vetor (x, y) para onde aponta um yaw do Blender."""
    return (-math.sin(yaw), math.cos(yaw))


def dir_yaw(dx, dy):
    """Yaw do Blender que faz um objeto olhar na direção (dx, dy)."""
    return math.atan2(-dx, dy)
