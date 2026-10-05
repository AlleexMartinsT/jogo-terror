"""Portas: abrir/fechar animado, trancas, ranger, folha como segmento de colisão e visada.

Os dados vêm de `layout` (dobradiça, ângulos, tranca). Se o pivô `Door_<id>` existir na cena,
as propriedades dele têm a palavra final e a rotação é escrita nele a cada quadro. Se existir a lingueta
`DoorBolt_<id>` (filha do pivô), ela recolhe quando a maçaneta gira e volta ao soltar.

Movimento
---------
A folha é um corpo rígido numa dobradiça (I = m L^2 / 3, atrito seco e viscoso, arrasto do ar) empurrado por uma mão. Quem
abre, fecha ou inverte a porta com a mão em contato leva a folha por uma curva de grau 5 (jerk mínimo) entre o estado atual
(posição, velocidade, aceleração) e o destino em repouso: é a trajetória que o corpo humano escolhe (Flash e Hogan, 1985) e,
com a dinâmica da folha, também a de mínima variação de torque, diferente dela em menos de 0,03% do curso. Por isso:
  - sai do repouso sem salto de aceleração e chega ao batente em tempo exato (o trinco precisa de um instante de chegada);
  - mudar de ideia no meio parte do estado atual, então posição e velocidade continuam contínuas e a folha ainda segue um
    pouco para onde ia (inércia) antes de voltar;
  - a duração não é arbitrária: nenhuma abertura é mais rápida do que a mão aguenta. A força de pico na maçaneta que a
    curva exige da massa da porta (FORCE_COMFORT, FORCE_REVERSE) limita o tempo (`_hand_limited_seconds`), e os 0,9 a 1,4 s
    ficam, assim, entre 40 e 100 N.
Fechar chega ao batente com a velocidade que empurra a lingueta chanfrada por cima da contra-fechadura (LATCH_TIP_SPEED); a
lingueta recolhe durante os últimos 11 mm e estala para fora na chegada. A batida não é guiada pela mão: é um golpe curto e forte
(FORCE_SLAM por SLAM_PULSE s) e a folha solta corre sozinha até o batente (`Slam`, integração do corpo rígido), onde bate
com a velocidade que a física dá (~4 m/s na ponta). O rebote no batente é balístico (restituição, e a folga da lingueta
limita o retorno): arcos parabólicos cada vez menores (`Settle`). Números e conferência com um modelo independente:
tools/movimento_ref/fisica/porta.py e comparar_porta.py.

Ranger
------
Cada abrir e cada fechar sorteia, com `game.rng`, se a dobradiça range:

    chance = creak_chance da porta  x  ritmo  x  ferrugem          (no máximo 0,9)

    tipo da porta            portas                                   creak_chance  folha (s)
    quarto                   master_hall, kids_hall, kids_master          0.30         1.10
    banheiro                 bath_hall, bath_study                        0.24         1.10
    escritório               den_hall, den_living, study_hall             0.20         1.12
    sala                     living_hall                                  0.18         1.12
    cozinha e garagem        kitchen_hall, garage_door                    0.24         1.22
    frente e fundos          front, back                                  0.36         1.22
    portão                   qualquer abertura `garage_door` do layout    0.42         1.22

    ritmo (jogador)          apressado 1.8  |  normal 1.0  |  devagar 0.65  |  agachado 0.40
                             apressado = correndo ou mais de 1,3x o passo; devagar = parado ou abaixo de 1,3 m/s
    ferrugem                 1 + 1,2 x (tempo parada / 150 s), no máximo 2,2: a primeira abertura de uma
                             porta que ficou muito tempo fechada é a mais provável

Exemplo: porta de quarto aberta andando, nunca antes mexida: 0.30 x 1.0 x 2.2 = 66%. Fechá-la logo depois,
agachado: 0.30 x 0.40 x 1.0 = 12%. A entidade abre com ritmo 1.3.

Quando range, toca `door_creak_N` (N sorteado sem repetir o anterior, com preferência por tipo) e emite o
ruído `door_creak` (NOISE_PLAYER 0.55). Com o decaimento do NoiseSystem isso é ouvido a uns 9 m em linha livre
de um cômodo de fundo silencioso (um cômodo e meio), um pouco menos num cômodo com ruído de fundo, e quase
nada atravessa uma porta fechada. A porta que está rangendo não abafa o próprio ranger (`opening=` na emissão).
"""
import math
from dataclasses import dataclass
from typing import Optional

from .. import conventions as C
from .. import layout
from . import collision

NEAR_OPEN = 0.5           # acima disso a porta conta como "aberta" para alternar
LEAF_HALF_THICKNESS = 0.03
SIGHT_HEIGHT = layout.DOOR_H

# ---- movimento ----
MAX_STEP_SECONDS = 0.1    # nunca integra mais que isto de uma vez (o jogo já limita o quadro)
HANDLE_LEAD = 0.14        # a maçaneta gira este tempo antes de a folha se mexer
HANDLE_HOLD = 0.12        # e fica girada este tempo depois de a folha sair
HANDLE_FOLLOW = 16.0      # 1/s: a maçaneta gira seguindo a mão
HANDLE_RELEASE = 45.0     # 1/s: e volta empurrada pela mola de retorno (~25 ms)
BOLT_STROKE = 0.011       # curso da lingueta (m): fechadura residencial
PARTIAL_BASE = 0.3        # duração de um trajeto parcial: seconds x (PARTIAL_BASE + (1 - PARTIAL_BASE) x distância)
MIN_SECONDS = 0.45
PACE_SECONDS = {"apressado": 0.84, "normal": 1.0, "devagar": 1.06, "agachado": 1.14, "entidade": 0.95}

# ---- física da folha (DERIVADO = lei; ESTIMADO = engenharia lembrada, com a faixa) ----
LEAF_ARC = math.pi / 2           # a folha abre 90 graus
KNOB_INSET = 0.07                # m: a maçaneta fica a 7 cm da borda livre (world/doorspec.py)
LEAF_HEIGHT = 2.03               # m
GRAVITY = 9.81
HINGE_MU, HINGE_RADIUS = 0.20, 0.007     # ESTIMADO (0,15 a 0,35; 5 a 9 mm): atrito seco = mu m g r nas arruelas de empuxo
HINGE_VISCOUS = 0.4              # N m s/rad, ESTIMADO (0,1 a 1,0): graxa velha
AIR_DRAG = 0.125 * 1.2 * 1.2 * LEAF_HEIGHT       # 1/8 rho Cd h; vezes L^4 dá o torque k w|w| (DERIVADO, Cd 1,2 ESTIMADO)
FORCE_COMFORT = 100.0            # N na maçaneta, esforço sustentado com uma mão (ESTIMADO 60 a 150)
FORCE_REVERSE = 150.0            # N, frear a folha e voltar: esforço curto (ESTIMADO 100 a 250)
FORCE_SLAM = 400.0               # N, golpe explosivo (ESTIMADO 300 a 500)
SLAM_PULSE = 0.15                # s, duração do golpe (ESTIMADO 0,15 a 0,5)
LATCH_TIP_SPEED = 0.30           # m/s na ponta ao chegar: empurra a lingueta chanfrada (mola de 3 a 8,5 N em 11 mm, ESTIMADO)
RESTITUTION = 0.25               # batente de madeira com vedação (ESTIMADO 0,1 a 0,35)
LATCH_PLAY = 0.003               # m, folga da lingueta na contra-fechadura (ESTIMADO 1 a 5 mm)
SLAM_PLAY = 0.005                # m, o retorno de uma batida forte (folga + vedação comprimida)
RETURN_PULL = 2.0                # rad/s2: mola da lingueta e vedação devolvendo a folha ao batente (ESTIMADO 1 a 4)
SLAM_SOUND_LEAD = 0.19           # s do início de audio/recipes_doors.py:door_slam até o estrondo
RATTLE_BOUNCE = (0.05, 0.004, 3)         # porta trancada sacudida: (duração de cada vaivém s, amplitude, quantidade)

# ---- ranger ----
SLOW_SPEED = 1.3
PACE_CREAK = {"apressado": 1.8, "normal": 1.0, "devagar": 0.65, "agachado": 0.40, "entidade": 1.3}
RUST_FULL = 150.0
RUST_GAIN = 1.2
MAX_CREAK_CHANCE = 0.9
ENTITY_AUDIBLE_FLOOR = 0.03   # a entidade só range se o jogador ouviria pelo menos isto


@dataclass(frozen=True)
class DoorKind:
    creak_chance: float
    seconds: float             # duração de uma abertura completa em ritmo normal
    creak_weights: tuple       # preferência por door_creak_1..4 (madeira grave, metal, madeira e pino, carraca seca)
    mass: float = 25.0         # kg da folha (ESTIMADO: madeira maciça com almofadas 20 a 30; porta de entrada isolada 35 a 50)


KINDS = {
    "quarto": DoorKind(0.30, 1.10, (3, 1, 3, 2)),
    "banheiro": DoorKind(0.24, 1.10, (1, 3, 2, 2)),
    "escritorio": DoorKind(0.20, 1.12, (2, 1, 3, 3)),
    "sala": DoorKind(0.18, 1.12, (2, 1, 3, 2)),
    "cozinha_garagem": DoorKind(0.24, 1.22, (1, 2, 2, 3), 32.0),
    "exterior": DoorKind(0.36, 1.22, (4, 2, 1, 1), 40.0),
    "portao": DoorKind(0.42, 1.22, (1, 4, 1, 2), 32.0),
}
CREAK_VARIANTS = 4


def classify(op):
    """Tipo da porta, lido dos cômodos que ela liga na planta."""
    rooms = set(op.rooms)
    if op.kind == "garage_door":
        return "portao"
    if op.id in ("front", "back"):
        return "exterior"
    if "bath" in rooms:
        return "banheiro"
    if rooms & {"kids", "master"}:
        return "quarto"
    if rooms & {"kitchen", "garage"}:
        return "cozinha_garagem"
    if rooms & {"den", "study"}:
        return "escritorio"
    return "sala"


# --------------------------------------------------------------------------
# Trajetórias (matemática pura, sem estado do jogo)
# --------------------------------------------------------------------------
def quintic_coefficients(x0, v0, a0, goal, seconds, end_velocity=0.0):
    """Polinômio de grau 5 de (x0, v0, a0) até `goal` em `seconds`, chegando com `end_velocity` e aceleração 0."""
    d, T = goal - x0, seconds
    c3 = (20 * d - (8 * end_velocity + 12 * v0) * T - 3 * a0 * T * T) / (2 * T ** 3)
    c4 = (-30 * d + (14 * end_velocity + 16 * v0) * T + 3 * a0 * T * T) / (2 * T ** 4)
    c5 = (12 * d - 6 * (end_velocity + v0) * T - a0 * T * T) / (2 * T ** 5)
    return (x0, v0, a0 / 2.0, c3, c4, c5)


def polynomial_state(coefficients, t):
    """(posição, velocidade, aceleração) do polinômio em `t`."""
    c0, c1, c2, c3, c4, c5 = coefficients
    x = c0 + t * (c1 + t * (c2 + t * (c3 + t * (c4 + t * c5))))
    v = c1 + t * (2 * c2 + t * (3 * c3 + t * (4 * c4 + t * 5 * c5)))
    a = 2 * c2 + t * (6 * c3 + t * (12 * c4 + t * 20 * c5))
    return x, v, a


@dataclass
class Glide:
    """Um trajeto da folha: o polinômio, quanto dura e há quanto tempo anda."""
    coefficients: tuple
    seconds: float
    goal: float
    end_velocity: float = 0.0
    elapsed: float = 0.0

    def advance(self, dt):
        self.elapsed = min(self.elapsed + dt, self.seconds)
        if self.elapsed >= self.seconds:
            return self.goal, self.end_velocity, 0.0
        return polynomial_state(self.coefficients, self.elapsed)

    @property
    def done(self):
        return self.elapsed >= self.seconds


class Settle:
    """A folha batendo no batente e voltando: arcos parabólicos cada vez menores.

    Sai com `restitution` x a velocidade de impacto e uma mola (lingueta, vedação) a puxa de volta com aceleração `pull`,
    então cada rebote é uma parábola. O primeiro não passa da folga da lingueta (`play`); a folga encolhe com e^2 a cada
    rebote. Tudo em unidades de abertura (0..1) e segundos.
    """

    def __init__(self, hit, restitution=RESTITUTION, play=0.0024, pull=RETURN_PULL * 2.0 / math.pi):
        self.arcs = []                    # (duração, altura) de cada rebote
        speed, cap = restitution * abs(hit), play
        while True:
            height = min(speed * speed / (2.0 * pull), cap)
            if height < 2e-5:
                break
            self.arcs.append((2.0 * math.sqrt(2.0 * height / pull), height))
            speed *= restitution
            cap *= restitution ** 2
        self.elapsed = 0.0

    @property
    def seconds(self):
        return sum(duration for duration, _ in self.arcs)

    def advance(self, dt):
        self.elapsed = min(self.elapsed + dt, self.seconds)
        t = self.elapsed
        for duration, height in self.arcs:
            if t < duration:
                u = t / duration
                return 4.0 * height * u * (1.0 - u)
            t -= duration
        return 0.0

    @property
    def done(self):
        return self.elapsed >= self.seconds


@dataclass
class Rattle:
    """Porta trancada sacudida: a folha vibra na folga do ferrolho, `bounces` vaivéns de `period` s que se apagam."""
    period: float
    amplitude: float
    bounces: int
    elapsed: float = 0.0

    @property
    def seconds(self):
        return self.period * self.bounces

    def advance(self, dt):
        self.elapsed = min(self.elapsed + dt, self.seconds)
        if self.elapsed >= self.seconds:
            return 0.0
        decay = math.exp(-self.elapsed / (1.2 * self.period))
        return self.amplitude * decay * abs(math.sin(math.pi * self.elapsed / self.period))

    @property
    def done(self):
        return self.elapsed >= self.seconds


class Slam:
    """Batida: um golpe forte e curto da mão e a folha solta correndo até o batente. Integra o corpo rígido (mesmas
    equações do modelo em tools/movimento_ref/fisica/porta.py) numa tabela e a percorre; fala a língua de `Glide`.

        I w' = -F r sin(pi t / T) - atrito seco - viscoso - arrasto do ar          (0 <= t <= T, depois só a resistência)
    """
    STEP = 1.0 / 960.0

    def __init__(self, x0, v0, mass, length):
        arc = LEAF_ARC
        radius = max(length - KNOB_INSET, 0.5 * length)
        inertia = mass * length ** 2 / 3.0
        dry = HINGE_MU * mass * GRAVITY * HINGE_RADIUS
        air = AIR_DRAG * length ** 4
        theta, omega, t = x0 * arc, v0 * arc, 0.0
        xs, vs, accels = [x0], [v0], [0.0]
        while theta > 0.0 and t < 3.0:
            push = -FORCE_SLAM * radius * math.sin(math.pi * t / SLAM_PULSE) if t < SLAM_PULSE else 0.0
            resist = (math.copysign(dry, omega) if omega else 0.0) + HINGE_VISCOUS * omega + air * omega * abs(omega)
            alpha = (push - resist) / inertia
            omega += alpha * self.STEP
            theta += omega * self.STEP
            t += self.STEP
            xs.append(max(theta, 0.0) / arc)
            vs.append(omega / arc)
            accels.append(alpha / arc)
        self._x, self._v, self._a = xs, vs, accels
        self.seconds = (len(xs) - 1) * self.STEP
        self.goal = 0.0
        self.end_velocity = vs[-1]                    # velocidade de impacto, negativa (abertura/s)
        self.coefficients = None
        self.elapsed = 0.0

    def advance(self, dt):
        self.elapsed = min(self.elapsed + dt, self.seconds)
        if self.elapsed >= self.seconds:
            return self.goal, self.end_velocity, 0.0
        position = self.elapsed / self.STEP
        k = int(position)
        f = position - k
        lerp = lambda arr: arr[k] + (arr[k + 1] - arr[k]) * f      # noqa: E731
        return lerp(self._x), lerp(self._v), lerp(self._a)

    @property
    def done(self):
        return self.elapsed >= self.seconds


@dataclass
class Door:
    id: str
    level: int
    hinge: tuple
    closed_yaw: float
    open_yaw: float
    length: float
    lock: str
    pivot: Optional[object] = None
    openness: float = 0.0
    target: float = 0.0
    segment: tuple = (0.0, 0.0, 0.0, 0.0, LEAF_HALF_THICKNESS)
    kind: str = "sala"
    creak_chance: float = 0.0
    seconds: float = 1.1
    creak_weights: tuple = (1, 1, 1, 1)
    bolt: Optional[object] = None
    bolt_rest: float = 0.0
    pace: str = "normal"
    velocity: float = 0.0
    accel: float = 0.0
    glide: Optional[Glide] = None
    settle: Optional[Settle] = None
    wait: float = 0.0             # segundos até a folha sair (a maçaneta gira antes)
    turn: float = 0.0             # 0..1: maçaneta girada, lingueta recolhida
    turn_hold: float = 0.0        # segundos que a maçaneta ainda fica girada
    rested_since: Optional[float] = None      # None: nunca mexida (ou zerada), a ferrugem é máxima
    slam: bool = False
    mass: float = 25.0            # kg
    hit: float = 0.0              # velocidade (abertura/s) com que a folha chegou ao batente fechando

    @property
    def yaw(self):
        return self.closed_yaw + (self.open_yaw - self.closed_yaw) * self.openness

    @property
    def floor_z(self):
        return layout.LEVEL_Z[self.level]

    @property
    def moving(self):
        return self.glide is not None or self.settle is not None or self.wait > 0.0

    def leaf_point(self, fraction):
        """Ponto (x, y) da folha, `fraction` do comprimento a partir da dobradiça."""
        yaw = self.yaw
        return (self.hinge[0] + math.cos(yaw) * self.length * fraction,
                self.hinge[1] + math.sin(yaw) * self.length * fraction)

    def refresh_segment(self):
        end_x, end_y = self.leaf_point(1.0)
        self.segment = (self.hinge[0], self.hinge[1], end_x, end_y, LEAF_HALF_THICKNESS)


def _read_door(op, scene):
    plan = layout.door_transform(op)
    pivot = scene.objects.get(C.N_DOOR + op.id) if scene is not None else None
    bolt = scene.objects.get(f"DoorBolt_{op.id}") if scene is not None else None
    hinge = (plan["hinge"][0], plan["hinge"][1])
    closed_yaw, open_yaw, lock = plan["closed_yaw"], plan["open_yaw"], op.lock
    if pivot is not None:
        origin = collision.object_position(pivot)
        hinge = (origin[0], origin[1])
        closed_yaw = pivot.get(C.P_DOOR_CLOSED, closed_yaw)
        open_yaw = pivot.get(C.P_DOOR_OPEN, open_yaw)
        lock = pivot.get(C.P_LOCK, lock)
    kind = classify(op)
    spec = KINDS[kind]
    door = Door(op.id, op.level, hinge, closed_yaw, open_yaw, op.width - 0.02, lock or "", pivot,
                kind=kind, creak_chance=spec.creak_chance, seconds=spec.seconds, creak_weights=spec.creak_weights,
                mass=spec.mass)
    if bolt is not None:
        door.bolt, door.bolt_rest = bolt, bolt.location.x
    door.refresh_segment()
    return door


class DoorManager:
    def __init__(self, game, scene):
        self.game = game
        self.state = game.state
        self.doors = {op.id: _read_door(op, scene) for op in layout.doors()}
        self._last_creak = None
        self._later = []          # [segundos, porta, nome, posição, volume]: sons que esperam a maçaneta girar
        self._apply_to_objects()

    # ---- consultas ----
    def get(self, door_id):
        return self.doors.get(door_id)

    def openness(self, door_id):
        """0 fechada .. 1 aberta. Ids que não são portas (arcos) contam como abertos."""
        door = self.doors.get(door_id)
        return 1.0 if door is None else door.openness

    def is_locked(self, door_id):
        door = self.doors.get(door_id)
        return door is not None and self.state.is_locked(door.lock)

    def is_open(self, door_id):
        return self.doors[door_id].target > NEAR_OPEN

    def segments(self, level):
        return [door.segment for door in self.doors.values() if door.level == level]

    def center(self, door_id):
        """Ponto de mira da porta: meio da folha, à altura da mão."""
        door = self.doors[door_id]
        x, y = door.leaf_point(0.6)
        return (x, y, door.floor_z + 1.0)

    def blocks_sight(self, a, b, ignore=None):
        """Alguma folha de porta cruza a linha a-b (a altura conta: a folha vai até DOOR_H)?"""
        level = layout.level_of_z(min(a[2], b[2]))
        for door in self.doors.values():
            if door.level != level or door.id == ignore:
                continue
            top = door.floor_z + SIGHT_HEIGHT
            if max(a[2], b[2]) < door.floor_z or min(a[2], b[2]) > top:
                continue
            x0, y0, x1, y1, _ = door.segment
            if collision.segment_crosses(a[0], a[1], b[0], b[1], x0, y0, x1, y1):
                return True
        return False

    def creak_probability(self, door_id, pace="normal"):
        """Chance de ranger agora ao abrir ou fechar a porta com esse ritmo (a tabela do topo do arquivo)."""
        door = self.doors[door_id]
        return min(MAX_CREAK_CHANCE, door.creak_chance * PACE_CREAK[pace] * self._rust(door))

    # ---- comandos ----
    def set_openness(self, door_id, fraction, speed=None):
        """Move a porta até `fraction` animando, sem som (usado por cutscenes).

        `speed` (fração da abertura por segundo, média do trajeto) força a duração; sem ele vale a da porta.
        """
        door = self.doors.get(door_id)
        if door is None:
            return
        goal = min(max(fraction, 0.0), 1.0)
        door.pace = "normal"
        seconds = None if not speed else abs(goal - door.openness) / speed
        self._retarget(door, goal, lead=0.0, seconds=seconds)

    def snap(self, door_id, fraction):
        """Coloca a porta em `fraction` agora, sem animar."""
        door = self.doors.get(door_id)
        if door is None:
            return
        door.target = door.openness = min(max(fraction, 0.0), 1.0)
        self._halt(door)
        door.turn = door.turn_hold = 0.0
        door.rested_since = self.game.clock
        self._later = [entry for entry in self._later if entry[1] != door_id]
        door.refresh_segment()
        self._write(door)

    def reset(self):
        """Todas fechadas, sem animação (novo jogo e checkpoint). A ferrugem volta."""
        for door_id, door in self.doors.items():
            self.snap(door_id, 0.0)
            door.rested_since = None
        self._last_creak = None

    def toggle(self, door_id, hurried=False):
        """Alterna a porta pelo jogador. Devolve 'opened' | 'closed' | 'slammed' | 'locked'."""
        door = self.doors[door_id]
        mid = self.center(door_id)
        if self.state.is_locked(door.lock):
            self.game.sound("door_locked", mid, 0.9)
            self.game.make_noise("flash_click", mid, C.NOISE_PLAYER["flash_click"])
            self._rattle(door)
            return "locked"
        if door.wait > 0.0:         # a maçaneta ainda está girando: um segundo [E] não desfaz o que começou
            return "opened" if door.target > NEAR_OPEN else "closed"
        door.pace = self._pace(hurried)
        if door.target > NEAR_OPEN:
            return self._begin_closing(door, mid, hurried)
        self._begin_opening(door, mid, C.NOISE_PLAYER, "player")
        return "opened"

    def open_door(self, door_id, by="entity"):
        """A IA abre a porta no caminho. Falso se está trancada ou não é uma porta."""
        door = self.doors.get(door_id)
        if door is None or self.state.is_locked(door.lock):
            return False
        if door.target < NEAR_OPEN:
            door.pace = "entidade"
            self._begin_opening(door, self.center(door_id), C.NOISE_ENTITY, by)
        return True

    # ---- início dos movimentos ----
    def _begin_opening(self, door, mid, noise_table, source):
        from_rest = not door.moving and door.openness < 0.02
        lead = HANDLE_LEAD if from_rest else 0.0
        creak = self._roll_creak(door, source)
        slow = door.pace in ("devagar", "agachado")
        self.game.make_noise("door_open", mid, noise_table["door_open"], source=source, opening=door.id)
        if lead:
            self._pull_handle(door, lead + HANDLE_HOLD)
            self.game.sound("door_handle", mid, 0.7 if source == "player" else 0.5)
        self._play(door, lead, "door_open_soft" if slow else "door_open", mid, 0.25 + 0.75 * noise_table["door_open"])
        if creak is not None:
            loud = noise_table["door_creak"]
            self.game.make_noise("door_creak", mid, loud, source=source, opening=door.id)
            self._play(door, lead, creak, mid, 0.25 + 0.75 * loud)
        self._retarget(door, 1.0, lead=lead)

    def _begin_closing(self, door, mid, hurried):
        creak = self._roll_creak(door, "player")
        if hurried:
            self.game.make_noise("door_slam", mid, C.NOISE_PLAYER["door_slam"], opening=door.id)
            result = "slammed"
        else:
            self.game.make_noise("door_close", mid, C.NOISE_PLAYER["door_close"], sound="door_close", opening=door.id)
            result = "closed"
        if creak is not None:
            self.game.make_noise("door_creak", mid, C.NOISE_PLAYER["door_creak"], sound=creak, opening=door.id)
        door.slam = hurried
        self._retarget(door, 0.0, lead=0.0)
        if hurried:         # o estrondo da receita vem SLAM_SOUND_LEAD s depois do início: tem de cair no impacto
            arrival = door.glide.seconds if door.glide is not None else 0.0
            self._play(door, max(0.0, arrival - SLAM_SOUND_LEAD), "door_slam", mid, 1.0)
        return result

    def _rattle(self, door):
        """Porta trancada: a folha sacode um fio na moldura. Nada de maçaneta girando."""
        if door.moving or door.openness > 0.0:
            return
        period, amplitude, bounces = RATTLE_BOUNCE
        door.settle = Rattle(period, amplitude, bounces)

    def _retarget(self, door, goal, lead, seconds=None):
        """Novo destino: parte do estado atual (posição, velocidade, aceleração) para o repouso em `goal`."""
        door.target = goal
        door.settle = None
        door.wait = lead
        x, v, a = door.openness, door.velocity, door.accel
        distance = abs(goal - x)
        if distance < 1e-4 and abs(v) < 1e-3:
            door.glide = None
            self._move_to(door, goal)
            return
        if door.slam and goal == 0.0 and seconds is None:
            door.glide = Slam(x, v, door.mass, door.length)
            return
        reversing = v * (goal - x) < 0.0 and abs(v) > 0.05
        forced = seconds is not None
        if seconds is None:
            seconds = self._duration(door, distance, reversing)
        end_velocity = 0.0
        if goal == 0.0 and not forced:       # fecha com a velocidade que vence a lingueta, não parando na frente dela
            end_velocity = -min(LATCH_TIP_SPEED / (door.length * LEAF_ARC), 1.2 * distance / seconds)
        if not forced:
            seconds = self._hand_limited_seconds(door, x, v, a, goal, seconds, end_velocity,
                                                 FORCE_REVERSE if reversing else FORCE_COMFORT)
        coefficients = quintic_coefficients(x, v, a, goal, seconds, end_velocity)
        door.glide = Glide(coefficients, seconds, goal, end_velocity)

    def _duration(self, door, distance, reversing):
        """Duração desejada pelo ritmo; ao inverter no meio a mão freia e volta o mais rápido que o esforço curto deixa."""
        if reversing:
            return MIN_SECONDS
        seconds = door.seconds * PACE_SECONDS[door.pace] * (PARTIAL_BASE + (1.0 - PARTIAL_BASE) * min(distance, 1.0))
        return max(MIN_SECONDS, seconds)

    def hand_force(self, door, coefficients, seconds, samples=24):
        """Força de pico (N) na maçaneta que a curva `coefficients` exige da mão: I alpha + atrito + arrasto, sobre o raio."""
        radius = max(door.length - KNOB_INSET, 0.5 * door.length)
        inertia = door.mass * door.length ** 2 / 3.0
        dry = HINGE_MU * door.mass * GRAVITY * HINGE_RADIUS
        air = AIR_DRAG * door.length ** 4
        peak = 0.0
        for i in range(samples + 1):
            _, v, a = polynomial_state(coefficients, seconds * i / samples)
            w = v * LEAF_ARC
            torque = inertia * a * LEAF_ARC + (math.copysign(dry, w) if w else 0.0) + HINGE_VISCOUS * w + air * w * abs(w)
            peak = max(peak, abs(torque) / radius)
        return peak

    def _hand_limited_seconds(self, door, x, v, a, goal, seconds, end_velocity, limit):
        """Menor duração >= `seconds` cuja curva a mão faz com no máximo `limit` N na maçaneta (bisseção)."""
        limit *= 0.995              # margem: a curva é amostrada, o pico verdadeiro cai entre duas amostras

        def peak(duration):
            return self.hand_force(door, quintic_coefficients(x, v, a, goal, duration, end_velocity), duration)
        if peak(seconds) <= limit:
            return seconds
        low, high = seconds, seconds * 4.0
        for _ in range(14):
            mid = 0.5 * (low + high)
            if peak(mid) > limit:
                low = mid
            else:
                high = mid
        return high

    def _halt(self, door):
        door.glide = door.settle = None
        door.wait = 0.0
        door.velocity = door.accel = 0.0
        door.slam = False

    def _pull_handle(self, door, hold):
        door.turn_hold = max(door.turn_hold, hold)

    def _pace(self, hurried):
        if hurried:
            return "apressado"
        player = getattr(self.game, "player", None)
        if player is None:
            return "normal"
        if player.crouching:
            return "agachado"
        return "devagar" if player.speed < SLOW_SPEED else "normal"

    # ---- ranger ----
    def _rust(self, door):
        if door.rested_since is None:
            return 1.0 + RUST_GAIN
        idle = max(0.0, self.game.clock - door.rested_since)
        return 1.0 + RUST_GAIN * min(1.0, idle / RUST_FULL)

    def _roll_creak(self, door, source):
        """Nome do `door_creak_N` sorteado, ou None. O sorteio sempre consome o RNG, para a semente ser estável."""
        roll = self.game.rng.random()
        if roll >= self.creak_probability(door.id, door.pace):
            return None
        if source != "player" and not self._player_would_hear(door):
            return None
        weights = [0.0 if index + 1 == self._last_creak else w for index, w in enumerate(door.creak_weights)]
        choice = self.game.rng.choices(range(1, CREAK_VARIANTS + 1), weights=weights)[0]
        self._last_creak = choice
        return f"door_creak_{choice}"

    def _player_would_hear(self, door):
        """O jogador ouviria o ranger da entidade? Estimativa pelo caminho do som (cômodos e portas)."""
        player = getattr(self.game, "player", None)
        if player is None:
            return False
        loud = C.NOISE_ENTITY["door_creak"]
        mid = self.center(door.id)
        path_between = getattr(self.game.noise, "path_between", None)
        if path_between is None:
            return loud * (1.0 - C.NOISE_DECAY_PER_M * math.dist(mid, player.feet)) > ENTITY_AUDIBLE_FLOOR
        path = path_between(mid, player.feet, opening=door.id)
        heard = (loud * (1.0 - C.NOISE_DECAY_PER_M * path.length) - C.NOISE_DOOR_CLOSED_LOSS * path.closed_doors
                 - C.NOISE_FLOOR_LOSS * path.floors)
        return heard > ENTITY_AUDIBLE_FLOOR

    def _play(self, door, delay, name, pos, volume):
        if delay <= 0.0:
            self.game.sound(name, pos, volume)
        else:
            self._later.append([delay, door.id, name, pos, volume])

    # ---- quadro a quadro ----
    def update(self, dt, player=None):
        dt = min(max(dt, 0.0), MAX_STEP_SECONDS)
        self._play_due(dt)
        for door in self.doors.values():
            self._step_handle(door, dt)
            if door.wait > 0.0:
                door.wait = max(0.0, door.wait - dt)
                continue
            if door.settle is not None:
                self._step_settle(door, dt)
            elif door.glide is not None or door.openness != door.target:
                self._step_glide(door, dt, player)

    def _play_due(self, dt):
        if not self._later:
            return
        due, waiting = [], []
        for entry in self._later:
            entry[0] -= dt
            (due if entry[0] <= 0.0 else waiting).append(entry)
        self._later = waiting
        for _, _, name, pos, volume in due:
            self.game.sound(name, pos, volume)

    def _step_glide(self, door, dt, player):
        if door.glide is None:      # esperava o jogador sair da frente: tenta de novo a partir do repouso
            door.velocity = door.accel = 0.0
            self._retarget(door, door.target, lead=0.0)
            if door.glide is None:
                return
        glide = door.glide
        x, v, a = glide.advance(dt)
        x = min(max(x, 0.0), 1.0)
        if x < door.openness and player is not None and self._would_trap(door, x, player):
            door.glide = None
            door.velocity = door.accel = 0.0
            return
        self._move_to(door, x)
        door.velocity, door.accel = v, a
        if door.target == 0.0 and x < self._ramp(door):
            # a lingueta chanfrada é empurrada para dentro pela contra-fechadura nos últimos 11 mm: a maçaneta gira junto
            door.turn = max(door.turn, 1.0 - x / self._ramp(door))
            self._write(door)
        if glide.done:
            door.glide = None
            door.hit = abs(glide.end_velocity)
            door.velocity = door.accel = 0.0
            self._arrive(door)

    def _ramp(self, door):
        """Quanto da abertura (0..1) a lingueta leva para sair da contra-fechadura: curso / (raio da maçaneta x 90 graus)."""
        return BOLT_STROKE / (max(door.length - KNOB_INSET, 0.5 * door.length) * LEAF_ARC)

    def _step_settle(self, door, dt):
        settle = door.settle
        previous = door.openness
        x = settle.advance(dt)
        self._move_to(door, x)
        door.velocity = (x - previous) / dt if dt > 0 else 0.0
        if settle.done:
            door.settle = None
            door.velocity = 0.0
            door.rested_since = self.game.clock

    def _arrive(self, door):
        """A folha parou. Chegando ao batente: a lingueta estala para fora (trinco) ou a batida já tocou, e a folha rebate."""
        door.openness = door.target
        door.rested_since = self.game.clock
        if door.target != 0.0:
            door.slam = False
            self._move_to(door, door.target)
            return
        slam, door.slam = door.slam, False
        play = (SLAM_PLAY if slam else LATCH_PLAY) / (max(door.length - KNOB_INSET, 0.5 * door.length) * LEAF_ARC)
        self._move_to(door, 0.0)
        door.settle = Settle(door.hit, RESTITUTION, play)
        if not slam:
            self.game.sound("door_latch", self.center(door.id), 0.75)

    def _move_to(self, door, x):
        if x != door.openness:
            door.openness = x
            door.refresh_segment()
        self._write(door)

    def _step_handle(self, door, dt):
        goal = 1.0 if door.turn_hold > 0.0 else 0.0
        door.turn_hold = max(0.0, door.turn_hold - dt)
        if door.turn != goal:
            rate = HANDLE_FOLLOW if goal > door.turn else HANDLE_RELEASE
            door.turn += (goal - door.turn) * (1.0 - math.exp(-rate * dt))
            if abs(door.turn - goal) < 1e-3:
                door.turn = goal
            self._write(door)

    def _would_trap(self, door, new_value, player):
        """Não fecha a porta em cima do jogador."""
        old = door.openness
        door.openness = new_value
        door.refresh_segment()
        x0, y0, x1, y1, half = door.segment
        cx, cy = collision.closest_on_segment(player.x, player.y, x0, y0, x1, y1)
        trapped = (door.level == player.level
                   and math.hypot(player.x - cx, player.y - cy) < C.PLAYER_RADIUS + half + 0.05)
        door.openness = old
        door.refresh_segment()
        return trapped

    def _apply_to_objects(self):
        for door in self.doors.values():
            self._write(door)

    def _write(self, door):
        if door.pivot is not None and abs(door.pivot.rotation_euler.z - door.yaw) > 1e-5:
            door.pivot.rotation_euler.z = door.yaw
        if door.bolt is not None:
            x = door.bolt_rest - BOLT_STROKE * door.turn
            if abs(door.bolt.location.x - x) > 1e-6:
                door.bolt.location.x = x
