"""Gestos de interação das mãos que pedem o corpo inteiro: pegar baixo, a mão na porta e a leitura com as duas mãos.

`Hands` guarda um `HandActions` e o consulta nos pontos em que um gesto depende do mundo (onde está o item, onde está a
maçaneta). O que fica aqui:

  * Pegar baixo. O braço sozinho não chega a um item abaixo da cintura: a cabeça desce e avança, o tronco se inclina e os
    joelhos dobram (`posture.ReachPosture`, no `Player`; `body.locomotion` lê a inclinação). Este módulo decide quanto, em
    cima da geometria (`posture.dip_to_reach`), liga a descida ao começo do gesto da mão e a subida ao fim do fechamento
    dos dedos. A mão sai um pouco depois do tronco, como nos clipes de pegar do chão da CMU.
  * (as seções de porta e de leitura entram nas próximas versões deste arquivo)

Nada aqui conhece o `Interact`: quem chama passa o alvo e o lado da mão.
"""
import math
from dataclasses import dataclass

from mathutils import Matrix, Quaternion, Vector

from .. import conventions as C
from . import collision
from . import doors as D
from . import handclips as K
from . import posture as P
from .handtrack import Clip, Event, Key, QuatTrack, Track, min_jerk

HAND_LAG = 0.25                # fração da descida em que a mão começa a sair (o tronco vai primeiro). ESTIMADO: nos clipes
                               # da CMU a mão só passa de 10% da distância depois do tronco já ter descido uns 20%
RISE_AFTER_CLOSE = 0.0         # s depois do contato que o corpo começa a subir (o dedo já fechou, a mão levanta o item)
STAND_DISTANCE = 0.50          # m, ESTIMADO: distância horizontal do olho ao item em que a pessoa para para se curvar. Nos clipes
                               # 69_70 a 69_75 o olho acaba sobre o objeto, 0,0 a 0,25 m dele; o ombro fica uns 0,2 m atrás
STEP_TRIGGER = 0.70            # m: além disto o corpo anda até o item
STEP_MAX = 0.70                # m: o passo não passa disto (mais longe, o braço e o `REACH_LIMIT` resolvem o resto)
EYE_FLOOR = 0.80               # m: a câmera não desce abaixo disto (o olho de um agachado fundo mede 1,26 m no mocap; 0,8 é
                               # o limite de antes de entrar no chão com a malha do corpo)
ARM_REACH = 0.62               # m: ombro até o centro da palma com o braço quase esticado (braço de 0,60 m + 0,06 m de palma, menos a folga do IK)


def shifted(clip, delay):
    """O mesmo clipe começando `delay` s depois: a mão espera onde está (a primeira chave de cada trilha se repete em 0)."""
    if delay <= 1e-4:
        return clip
    tracks = {}
    for name, track in clip.tracks.items():
        first = track.keys[0]
        keys = [Key(0.0, first.value, True, first.space)]
        keys += [Key(k.t + delay, k.value, k.stop, k.space) for k in track.keys]
        tracks[name] = (QuatTrack if name.endswith(".rot") else Track)(keys)
    events = [Event(e.t + delay, e.name, e.arg, e.essential) for e in clip.events if e.name != "done"]
    return Clip(clip.name, clip.duration + delay, tracks, events, clip.interruptible, dict(clip.meta))


class HandActions:
    def __init__(self, hands):
        self.hands = hands
        self.game = hands.game
        self.dip = P.NONE
        self.dip_clip = None            # o clipe que está usando a postura (quem o termina manda o corpo subir)
        self._ready = None              # (id da porta, clipe, DoorHand) da mão preparada diante da maçaneta
        self._dwell = 0.0               # s olhando a mesma porta de perto
        self._lost = 0.0

    # ---- ciclo de vida ----
    def reset(self):
        self.dip, self.dip_clip = P.NONE, None
        self._ready, self._dwell, self._lost = None, 0.0, 0.0
        self.game.player.reach.reset()

    def update(self, dt):
        """Guarda: se o clipe que pediu a postura acabou sem mandar subir (interrompido, trocado), o corpo sobe."""
        self._watch_door(dt)
        reach = self.game.player.reach
        if self.dip_clip is None:
            return
        running = self.hands.runner.clip
        if running is not self.dip_clip and reach.goal > 0.0:
            reach.go(0.0, self.dip.up_s)
        if running is not self.dip_clip and not reach.active:
            self.dip_clip = None

    # ---- postura de alcance ----
    def _eye_frame(self):
        player = self.game.player
        yaw = player.yaw
        return (player.eye_pos, (-math.sin(yaw), math.cos(yaw)), (math.cos(yaw), math.sin(yaw)))

    def _item_point(self, target):
        return Vector(collision.object_position(target.obj) if target.obj is not None else target.position)

    def plan_pickup(self, target, side):
        """Para pegar o item de `target` com a mão `side` ("R"/"L"): (postura, passo em metros, direção do passo).

        Quem pega algo que está longe anda até ele antes de se curvar (os clipes 69_70 a 69_75 da CMU começam com "andar até o
        objeto"). O jogo faz o mesmo em passo lento, no máximo `STEP_MAX`, até o item ficar a `STAND_DISTANCE` do olho; o que
        sobrar de distância é o `REACH_LIMIT` do `Hands` (a mão para onde o braço chega)."""
        player = self.game.player
        eye, forward, right = self._eye_frame()
        point = self._item_point(target)
        dx, dy, dz = point.x - eye[0], point.y - eye[1], point.z - eye[2]
        horizontal = math.hypot(dx, dy)
        step = min(STEP_MAX, horizontal - STAND_DISTANCE) if horizontal > STEP_TRIGGER else 0.0
        left = max(0.0, horizontal - step) / horizontal if horizontal > 1e-6 else 1.0
        ahead = max(0.0, (dx * forward[0] + dy * forward[1]) * left)
        lateral = (dx * right[0] + dy * right[1]) * left
        wall = self.game.collision.ray_distance(eye, (forward[0], forward[1], 0.0), 1.2 + step)
        dip = P.dip_to_reach(ahead, lateral, -dz, 1.0 if side == "R" else -1.0, wall_distance=max(0.0, wall - step))
        cap = max(0.0, (eye[2] - player.z) - EYE_FLOOR)        # agachado já está perto do chão
        if dip.depth > cap:
            dip = P.dip_for_depth(cap, ahead, wall)
        direction = (dx / horizontal, dy / horizontal) if horizontal > 1e-6 else (forward[0], forward[1])
        return dip, step, direction

    def start_dip(self, dip, clip):
        if not dip.needed:
            return
        self.dip, self.dip_clip = dip, clip
        self.game.player.reach.go(1.0, dip.down_s, dip)

    def pickup_clip(self, factory, target, side):
        """O clipe de pegar `target` com o passo e a postura que ele pede: devolve o clipe e a postura (que já começaram)."""
        hands = self.hands
        dip, step, direction = self.plan_pickup(target, side)
        if not dip.needed and step < 0.02:
            return factory(K.move_time((hands._reach_point(target) - hands._rest[side]).length)), P.NONE
        rest_world = hands._cam[0] @ hands._rest[side] + Vector((direction[0] * step, direction[1] * step, 0.0))
        reach_s = K.move_time((self._item_point(target) - rest_world).length)       # a mão percorre o caminho no mundo
        clip = factory(reach_s)
        if step >= 0.02:
            self.game.player.assist_walk(direction[0], direction[1], step)
        if not dip.needed:
            return clip, P.NONE
        clip = shifted(clip, HAND_LAG * dip.down_s)
        contact = next(e.t for e in clip.events if e.name == "contact")
        clip.events.append(Event(contact + RISE_AFTER_CLOSE, "rise", None, True))
        clip.events.sort(key=lambda e: e.t)
        clip.meta["posture"] = True
        self.start_dip(dip, clip)
        return clip, dip

    # ---- porta ----
    def _door_side(self):
        """A mão que abre a porta: a esquerda, que a lanterna deixa livre; sem lanterna, a direita. None se a mão está ocupada."""
        hands, state = self.hands, self.game.state
        clip = hands.runner.clip
        waiting = clip is not None and clip.name == "door_ready"
        if hands.busy or hands._after is not None or (clip is not None and not waiting):
            return None
        if hands._job is not None and not waiting:
            return None
        if state.has_flashlight:
            return "L" if hands._persist_left is None and hands._held is None and hands._goal is None else None
        return "R"

    def plan_door(self, door_id, hurried=False, ready=False, origin=None):
        """O gesto que a porta pede agora, ou None (sem gesto: a mão está ocupada, a maçaneta está longe, alguém já girou).
        `ready`: só a mão preparada diante da maçaneta; `origin` (posição, rotação no espaço da câmera): a mão já está a caminho."""
        game, hands = self.game, self.hands
        door = game.doors.get(door_id)
        side = self._door_side()
        if door is None or side is None or door.moving or hurried:       # com pressa não há tempo de esperar a mão
            return None
        locked = game.state.is_locked(door.lock)
        closing = door.target > D.NEAR_OPEN
        kind = "locked" if locked else ("close" if closing else "open")
        player = game.player
        eye, forward, right = self._eye_frame()
        yaw = door.yaw
        base = Vector((door.hinge[0] + math.cos(yaw) * (door.length - D.KNOB_INSET),
                       door.hinge[1] + math.sin(yaw) * (door.length - D.KNOB_INSET), door.floor_z + KNOB_HEIGHT))
        normal = Vector((-math.sin(yaw), math.cos(yaw), 0.0))
        if (Vector(eye) - base).dot(normal) < 0.0:
            normal = -normal
        grasp = base + normal * KNOB_CENTER + Vector((0.0, 0.0, PALM_OVER))
        dx, dy, dz = grasp.x - eye[0], grasp.y - eye[1], grasp.z - eye[2]
        horizontal = math.hypot(dx, dy)
        pushing = kind == "open" and self._swings_away(door, eye)
        step = min(STEP_MAX, horizontal - STAND_DISTANCE) if pushing and not ready and horizontal > STEP_TRIGGER else 0.0
        left = max(0.0, horizontal - step) / horizontal if horizontal > 1e-6 else 1.0
        ahead, lateral = (dx * forward[0] + dy * forward[1]) * left, (dx * right[0] + dy * right[1]) * left
        sign = 1.0 if side == "R" else -1.0
        wall = game.collision.ray_distance(eye, (forward[0], forward[1], 0.0), 1.2 + step)
        dip = P.dip_to_reach(max(0.0, ahead), lateral, -dz, sign, wall_distance=max(0.0, wall - step))
        if P.reach_gap(dip, max(0.0, ahead), lateral, -dz, sign) > DOOR_REACH_SLACK:
            return None
        direction = (dx / horizontal, dy / horizontal) if horizontal > 1e-6 else (forward[0], forward[1])
        rest_world = hands._cam[0] @ hands._rest[side] + Vector((direction[0] * step, direction[1] * step, 0.0))
        pre = grasp + normal * PRE_GRASP
        if origin is not None:
            distance = (pre - hands._cam[0] @ origin[0]).length
            reach_s = 0.0 if distance < 0.02 else min(K.move_time(distance), 0.15 + 2.0 * distance)
        elif ready:
            reach_s = K.move_time((pre - rest_world).length)
        else:
            reach_s = max(COLD_REACH_MIN, K.move_time((pre - rest_world).length) - COLD_REACH_FASTER)
        timing = DoorHand.timing(kind, reach_s)
        return DoorPlan(door_id, kind, side, normal, reach_s, timing, dip, step, direction, horizontal)

    @staticmethod
    def _swings_away(door, eye):
        """A folha que abre se afasta do jogador (empurrar) ou vem para cima dele (puxar)?"""
        yaw_open = door.open_yaw
        side_of_eye = (eye[0] - door.hinge[0]) * -math.sin(door.closed_yaw) + (eye[1] - door.hinge[1]) * math.cos(door.closed_yaw)
        swing = math.cos(yaw_open) * -math.sin(door.closed_yaw) + math.sin(yaw_open) * math.cos(door.closed_yaw)
        return side_of_eye * swing < 0.0

    def use_door(self, door_id, hurried=False):
        """O [E] numa porta: a mão vai à maçaneta (ou já está nela) e, quando fecha os dedos, a porta se move. Devolve o que o
        `DoorManager` devolve."""
        doors, hands = self.game.doors, self.hands
        origin = None
        if self._ready is not None and self._ready[1] is hands.runner.clip and self._ready[0] == door_id:
            side = self._ready[2].plan.side
            origin = (Vector(hands.runner.current(f"{side}.pos")), Quaternion(hands.runner.current(f"{side}.rot")))
        plan = self.plan_door(door_id, hurried, origin=origin)
        result = doors.toggle(door_id, hurried=hurried, delay=plan.delay if plan is not None else 0.0)
        if plan is not None:
            self.play_door(plan, doors.get(door_id), origin)
        else:
            self._cancel_ready()
        return result

    def play_door(self, plan, door, origin=None):
        from .hands import _Job
        hands = self.hands
        glide = door.glide.seconds if door.glide is not None else 0.0
        hand = DoorHand(self, plan, door, glide, origin=origin)
        events = [Event(0.04, "sound", "hand_reach")] if origin is None else []
        meta = {"side": plan.side, "kind": None, "grasp": plan.side, "rest": True, "door": door.id}
        if plan.dip.needed:
            events.append(Event(hand.release_at + 0.05, "rise", None, True))
            meta["posture"] = True
        clip = Clip(f"door_{plan.kind}", hand.duration, hand.tracks(), events, interruptible=True, meta=meta)
        if plan.step >= 0.02:
            self.game.player.assist_walk(plan.direction[0], plan.direction[1], plan.step)
        self._ready = None
        hands._start(clip, _Job("door", item=None))
        self.start_dip(plan.dip, clip)

    # ---- a mão que se prepara ----
    def _watch_door(self, dt):
        """Olhando uma porta de perto e devagar, a mão sai sozinha até a maçaneta e espera: o [E] só fecha os dedos. Sem isso a
        porta esperaria a mão sair de baixo do quadro (0,6 s) em cada abertura."""
        game, hands = self.game, self.hands
        if self._ready is not None and hands.runner.clip is not self._ready[1]:
            self._ready = None
        current = game.interact.current if game.phase == "play" else None
        door_id = current.ref if current is not None and current.kind == "door" else None
        ok = False
        if door_id is not None and game.player.speed < PRIME_SPEED and not game.player.assisting:
            plan = self.plan_door(door_id, False, ready=True)
            ok = plan is not None and plan.horizontal <= PRIME_DISTANCE
        if ok:
            self._lost = 0.0
            if self._ready is None:
                self._dwell += dt
                if self._dwell >= PRIME_DWELL:
                    self._start_ready(door_id, plan)
            elif self._ready[0] != door_id:
                self._cancel_ready()
            return
        if self._ready is None:
            self._dwell = 0.0
            return
        self._lost += dt
        if self._lost > PRIME_LOSE:
            self._cancel_ready()

    def _start_ready(self, door_id, plan):
        from .hands import _Job
        hands = self.hands
        door = self.game.doors.get(door_id)
        hand = DoorHand(self, plan, door, 0.0, ready=True)
        clip = Clip("door_ready", READY_SECONDS, hand.tracks(), [Event(0.04, "sound", "hand_reach")], interruptible=True,
                    meta={"side": plan.side, "kind": None, "grasp": plan.side, "rest": True, "door": door_id})
        hands._start(clip, _Job("ready", item=None))
        self._ready = (door_id, clip, hand)
        if plan.dip.needed:
            clip.meta["posture"] = True
            self.start_dip(plan.dip, clip)

    def _cancel_ready(self):
        ready, self._ready, self._dwell, self._lost = self._ready, None, 0.0, 0.0
        if ready is not None and self.hands.runner.clip is ready[1]:
            self.hands._interrupt()

    def _on_rise(self, _):
        self.game.player.reach.go(0.0, self.dip.up_s)

    # ---- eventos que o Hands não conhece ----
    def handler(self, name):
        return getattr(self, f"_on_{name}", None)

    def clamp_to_arm(self, point, side):
        """`point` (espaço da câmera) limitado à esfera que o braço alcança a partir do ombro de verdade, enquanto o corpo está
        no gesto de pegar baixo; None quando não há postura em curso (vale o limite de sempre, medido do olho)."""
        if side is None or self.dip_clip is None or self.dip_clip is not self.hands.runner.clip or not self.dip.needed:
            return None
        shoulder = self.game.body.arm(side).shoulder_world_position()
        if shoulder is None:
            return None
        anchor = self.hands._cam[1] @ Vector(shoulder)
        offset = Vector(point) - anchor
        if offset.length > ARM_REACH:
            offset *= ARM_REACH / offset.length
        return anchor + offset


# ---------------------------------------------------------------------------
# A mão na porta
# ---------------------------------------------------------------------------
# A maçaneta redonda (world/doors.py): cabeça de latão de 5,2 cm a 7 cm da borda livre e 0,95 m do piso, o centro da cabeça a
# 7,5 cm do plano médio da folha. A mão esquerda (a direita segura a lanterna) a alcança, abre os dedos antes de tocar, fecha,
# gira o punho (a lingueta recolhe: `doors.HANDLE_LEAD`), acompanha a maçaneta pelo arco da folha enquanto o braço alcança, solta
# e volta. O tempo de chegar e de fechar os dedos é o `delay` que o `DoorManager` espera antes de girar a maçaneta e soltar a
# folha: a duração do movimento da folha não muda.
KNOB_HEIGHT = 0.95                # world/doorspec.KNOB_HEIGHT (há teste)
KNOB_CENTER = 0.075               # m, do plano médio da folha ao centro da cabeça
PALM_OVER = 0.042                 # m: a palma pousa sobre a cabeça (raio 2,6 cm mais a pele)
PRE_GRASP = 0.075                 # m: a mão para aqui, aberta, antes do último avanço
FOREARM_DOWN = 28.0               # graus: os dedos apontam para a maçaneta e para baixo (ela fica 45 cm abaixo do ombro)
PRE_ROLL = 38.0                   # graus de supinação ao chegar (a mão não vai com a palma para baixo: meio caminho da apertada de mão)
TURN_ROLL = 42.0                  # graus de supinação do giro. ESTIMADO: a faixa funcional do antebraço é de 50 graus de pronação a 50 de
                                  # supinação (Kapandji, via Sage OT 2023) e a lingueta de uma maçaneta recolhe com 30 a 45 graus
APPROACH = 0.12                   # s do pré-contato ao contato (o último avanço)
CLOSE = 0.20                      # s para os dedos fecharem sobre a maçaneta (o mesmo CLOSE_TIME do alcance)
UNCLASP = 0.10                    # s com os dedos abrindo antes de a mão sair
WITHDRAW = 0.50                   # s da mão voltando ao braço solto. ESTIMADO: sem alvo a acertar (EXIT_FACTOR), mais depressa que a lei
RELEASE_OPEN = 0.60               # fração do movimento da folha em que a mão solta ao abrir (depois do pico de velocidade)
RELEASE_CLOSE = 0.92              # ... e ao fechar (solta junto com a lingueta)
COLD_REACH_FASTER = 0.22          # s: sem a mão já a caminho a pessoa alcança a maçaneta 1 desvio (0,22 s) mais depressa que a lei
COLD_REACH_MIN = 0.50             # s: ... e não menos que isto (ESTIMADO)
PRIME_DWELL = 0.30                # s olhando a porta de perto antes de a mão sair sozinha (ESTIMADO)
PRIME_DISTANCE = 0.95             # m (horizontal, olho até a maçaneta): mais perto que isto, e ao alcance do braço, a mão já se prepara
PRIME_SPEED = 1.0                 # m/s: andando mais depressa, a pessoa está só passando
PRIME_LOSE = 0.30                 # s sem as condições antes de a mão desistir
DOOR_REACH_SLACK = 0.06           # m: além do alcance confortável o IK ainda estica o braço, mas não passa disto
READY_SECONDS = 60.0              # a mão preparada espera por quanto tempo for preciso; quem a tira de lá é `HandActions.update`
KNOB_GRIP = (0.52, 0.56, 0.62, 0.66, 0.68)      # dedos em torno de uma esfera de 5 cm
ARM_MIN_REACH = 0.28              # m: com a maçaneta tão perto do ombro o cotovelo não dobra mais (puxar a folha para si): solta
LOCK_TWIST = 26.0                 # graus que o punho gira antes de a tranca segurar
LOCK_JIGGLE = (3.0, 3, 0.05)      # graus, vaivéns e período (s) do punho sacudindo a maçaneta travada: o mesmo do vaivém da folha
                                  # (`doors.RATTLE_BOUNCE`: três de 0,05 s)


def hand_quaternion(fingers, palm):
    """Rotação da mão (o mesmo da `handclips.hand_rotation`, sem passar por ângulos de Euler)."""
    f = Vector(fingers).normalized()
    p = Vector(palm)
    p = (p - f * p.dot(f)).normalized()
    return (Matrix((f, p, f.cross(p))).transposed() @ K.NEUTRAL_HAND.inverted()).to_quaternion()


def roll_about(vector, axis, degrees):
    return Quaternion(axis.normalized(), math.radians(degrees)) @ Vector(vector)


class LiveTrack:
    """Uma trilha que se calcula a cada amostra, em vez de interpolar chaves: a mão da porta segue a maçaneta de verdade.
    Fala a língua de `Track` para o `ClipPlayer` (que só chama `sample`)."""

    def __init__(self, function, size):
        self.function, self.size = function, size
        self.keys = [Key(0.0, (0.0,) * size)]
        self.times = [0.0]

    @property
    def end(self):
        return 1e9

    def sample(self, t, anchors=None):
        return self.function(t, anchors)

    def phase(self, t):
        return 0.0


@dataclass
class DoorPlan:
    door_id: str
    kind: str                      # open | close | slam | locked
    side: str
    normal: Vector                 # do plano da folha para o lado do jogador (mundo)
    reach_s: float
    delay: float                   # s até os dedos fecharem na maçaneta: o que o `DoorManager` espera
    dip: object
    step: float = 0.0
    direction: tuple = (0.0, 0.0)
    horizontal: float = 0.0        # m, do olho à maçaneta


class DoorHand:
    """A mão numa maçaneta: tudo o que a pose precisa saber da porta, calculado ao vivo, e a linha do tempo do gesto."""

    @staticmethod
    def timing(kind, reach_s):
        """Segundos até a maçaneta poder girar (o que o `DoorManager` espera): chegar, o último avanço e, na tranca, o giro até ela."""
        grasp = reach_s + APPROACH
        return grasp + 0.14 if kind == "locked" else grasp

    def __init__(self, actions, plan, door, glide_seconds, ready=False, origin=None):
        self.actions, self.plan, self.door = actions, plan, door
        self.ready, self.origin = ready, origin       # ready: só se aproxima e espera; origin: (posição, rotação) de onde a mão parte
        self.hands = actions.hands
        self.sign = -1.0 if plan.side == "L" else 1.0          # sentido da supinação em torno do eixo dos dedos
        self.reach = plan.reach_s
        self.grasp_at = plan.reach_s + APPROACH                # a palma toca a maçaneta
        kind = plan.kind
        if kind == "locked":
            self.turn_at = self.grasp_at
            self.stop_at = self.turn_at + 0.14                 # o punho chega à tranca
            self.release_at = self.stop_at + LOCK_JIGGLE[1] * LOCK_JIGGLE[2] + 0.12
        elif kind == "slam":
            self.turn_at = self.grasp_at
            self.stop_at = self.grasp_at
            self.release_at = self.grasp_at + D.SLAM_PULSE
        else:
            self.turn_at = self.grasp_at
            self.stop_at = self.grasp_at + D.HANDLE_LEAD       # a folha sai quando a maçaneta acaba de girar
            fraction = RELEASE_OPEN if kind == "open" else RELEASE_CLOSE
            self.release_at = self.stop_at + fraction * glide_seconds
        self.duration = READY_SECONDS if ready else self.release_at + UNCLASP + WITHDRAW
        self.released = None           # (instante, posição, rotação, dedos) no espaço da câmera
        self._cache = {}

    # ---- a porta ao vivo ----
    def knob_world(self):
        door = self.door
        yaw = door.yaw
        along = door.length - D.KNOB_INSET
        base = Vector((door.hinge[0] + math.cos(yaw) * along, door.hinge[1] + math.sin(yaw) * along, door.floor_z + KNOB_HEIGHT))
        normal = Vector((-math.sin(yaw), math.cos(yaw), 0.0))
        if normal.dot(self.plan.normal) < 0.0:
            normal = -normal
        return base + normal * KNOB_CENTER, normal

    def _pose_world(self):
        """(centro da cabeça, normal para o jogador, dedos, palma) no mundo, com a mão virada para a maçaneta."""
        center, normal = self.knob_world()
        up = Vector((0.0, 0.0, 1.0))
        fingers = (-normal * math.cos(math.radians(FOREARM_DOWN)) - up * math.sin(math.radians(FOREARM_DOWN))).normalized()
        palm = (-up - fingers * (-up).dot(fingers)).normalized()
        return center, normal, fingers, palm

    def _to_camera(self, point, fingers, palm):
        cam = self.hands._cam
        return cam[1] @ point, cam[1].to_3x3() @ fingers, cam[1].to_3x3() @ palm

    def _hand(self, roll, back):
        """Pose da mão (posição, rotação) no espaço da câmera, `back` m recuada da maçaneta e com `roll` graus de supinação."""
        center, normal, fingers, palm = self._pose_world()
        position = center + Vector((0.0, 0.0, PALM_OVER)) + normal * back
        palm = roll_about(palm, fingers, self.sign * roll)
        point, f, p = self._to_camera(position, fingers, palm)
        return Vector(point), hand_quaternion(f, p)

    # ---- a linha do tempo ----
    def twist(self, t):
        """Graus de supinação no instante `t` (antes de soltar): chega com PRE_ROLL, gira, segura e, na tranca, sacode."""
        kind = self.plan.kind
        roll = PRE_ROLL
        if kind == "locked":
            roll += LOCK_TWIST * min_jerk((t - self.turn_at) / max(self.stop_at - self.turn_at, 1e-3))
            after = t - self.stop_at
            amplitude, count, period = LOCK_JIGGLE
            if 0.0 < after < count * period:
                roll += amplitude * math.sin(2.0 * math.pi * after / period)
        elif kind != "slam":
            roll += TURN_ROLL * min_jerk((t - self.turn_at) / max(self.stop_at - self.turn_at, 1e-3))
        return roll

    def _should_release(self, t, position):
        if t >= self.release_at:
            return True
        if t < self.stop_at:
            return False
        shoulder = self.hands.game.body.arm(self.plan.side).shoulder_world_position()
        if shoulder is None:
            return False
        world = self.hands._cam[0] @ position
        distance = (world - Vector(shoulder)).length
        return distance > ARM_REACH or distance < ARM_MIN_REACH

    def pose(self, t, anchors):
        """(posição, rotação, dedos) no instante `t`; o resultado de cada `t` fica guardado (o executor pergunta duas vezes)."""
        key = round(t, 6)
        if key in self._cache:
            return self._cache[key]
        rest = Vector(self.hands._rest_at_start)
        rest_q = Quaternion(K.euler_quaternion(K.HANG_ROT[self.plan.side]))
        start, start_q = (self.origin if self.origin is not None else (rest, rest_q))
        if self.released is not None and t >= self.released[0]:
            result = self._after_release(t, rest, rest_q)
        elif self.ready and t >= self.reach:
            position, rotation = self._hand(PRE_ROLL, PRE_GRASP)
            result = (position, rotation, self._open(t))
        elif t < self.reach:
            u = min_jerk(t / self.reach)
            end, end_q = self._hand(PRE_ROLL, PRE_GRASP)
            result = (start.lerp(end, u), start_q.slerp(end_q, u), self._open(t))
        elif t < self.grasp_at:
            v = min_jerk((t - self.reach) / APPROACH)
            a, qa = self._hand(PRE_ROLL, PRE_GRASP)
            b, qb = self._hand(PRE_ROLL, 0.0)
            result = (a.lerp(b, v), qa.slerp(qb, v), self._open(t))
        else:
            position, rotation = self._hand(self.twist(t), 0.0)
            if self._should_release(t, position):
                self.released = (t, position, rotation, self._grip(t))
                result = self._after_release(t, rest, rest_q)
            else:
                result = (position, rotation, self._grip(t))
        if len(self._cache) > 16:
            self._cache.clear()
        self._cache[key] = result
        return result

    def _open(self, t):
        """Os dedos abrem durante o alcance (a abertura máxima aos 60%, como nos alcances medidos) e ficam abertos até tocar."""
        if self.reach < 1e-3 or self.origin is not None:
            return K.OPEN
        u = min_jerk(max(0.0, min(1.0, t / (0.60 * self.reach))))
        return tuple(a + (b - a) * u for a, b in zip(K.RELAX, K.OPEN))

    def _grip(self, t):
        if self.plan.kind == "slam":
            return K.OPEN
        u = min_jerk((t - (self.grasp_at - 0.04)) / CLOSE)
        return tuple(a + (b - a) * u for a, b in zip(K.OPEN, KNOB_GRIP))

    def _after_release(self, t, rest, rest_q):
        moment, position, rotation, grip = self.released
        since = t - moment
        if since < UNCLASP:
            u = min_jerk(since / UNCLASP)
            return position, rotation, tuple(a + (b - a) * u for a, b in zip(grip, K.OPEN))
        u = min_jerk((since - UNCLASP) / WITHDRAW)
        curl = tuple(a + (b - a) * u for a, b in zip(K.OPEN, K.RELAX))
        return position.lerp(rest, u), rotation.slerp(rest_q, u), curl

    # ---- as trilhas do clipe ----
    def tracks(self):
        side = self.plan.side
        previous = {"rot": None}

        def position(t, anchors):
            return tuple(self.pose(t, anchors)[0])

        def rotation(t, anchors):
            q = self.pose(t, anchors)[1]
            if previous["rot"] is not None and sum(a * b for a, b in zip(q, previous["rot"])) < 0.0:
                q = Quaternion((-q.w, -q.x, -q.y, -q.z))
            previous["rot"] = tuple(q)
            return tuple(q)

        def fingers(t, anchors):
            return tuple(self.pose(t, anchors)[2])

        weight = Track([Key(0.0, (0.0,), True), Key(0.30 * self.reach, (1.0,)), Key(self.duration - 0.10, (1.0,)),
                        Key(self.duration, (0.0,), True)])
        return {f"{side}.pos": LiveTrack(position, 3), f"{side}.rot": LiveTrack(rotation, 4),
                f"{side}.curl": LiveTrack(fingers, 5), f"{side}.w": weight}
