"""O cérebro da entidade (o Alto): percepção, estados e movimento sobre a malha de navegação.

Sem bpy. O engine entrega uma `WorldView` (visão, portas, cômodos), o `NoiseSystem` e um
`random.Random`; a cada quadro chama `update(dt, senses)` e aplica o `BrainOutput` no rig.

Estados (conventions.ENTITY_STATES):
  dormant      parado e invisível até `activate`.
  patrol       vai de cômodo em cômodo, para, olha pela porta.
  investigate  vai até onde ouviu um som (com erro de localização maior para sons fracos).
  stalk        jogador perto e quieto: chega devagar e EM SILÊNCIO (drone 0, o silêncio avisa).
  chase        vai ao último ponto conhecido; perdeu por `lose_time` s -> search.
  search       vasculha o último ponto e cômodos vizinhos por `search_time` s -> patrol.
  attack       perto e à vista: breve preparo e `kill=True`.
"""
import math
from dataclasses import dataclass
from typing import Optional

from .. import conventions as C
from .. import layout
from . import nav as nav_module
from .pathfollow import Body, PathFollower
from .perception import (Hearing, awareness_change, entity_head, flashlight_points_at, look_at_player,
                         player_target)
from .tuning import BrainTuning

MAX_CHASE_SPEED = 4.5          # abaixo da corrida do jogador (4.6) mesmo com agressividade máxima
DOOR_BLOCK_SECONDS = 8.0
DOOR_WAIT_GIVE_UP = 6.0
STUCK_STREAK_TO_UNSTICK = 3
LOG_LIMIT = 400


@dataclass
class BrainOutput:
    x: float
    y: float
    z: float
    yaw: float
    speed: float
    state: str
    anim: str                                   # 'idle' | 'stalk' | 'walk' | 'run' | 'attack' | 'stare'
    look_target: Optional[tuple] = None
    kill: bool = False
    drone: float = 0.0                          # volume do zumbido (0 em stalk: o silêncio avisa)
    step_noise: Optional[str] = None            # chave de NOISE_ENTITY para o passo desta marcha
    awareness: float = 0.0


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def _heading_yaw(dx, dy):
    return C.dir_yaw(dx, dy)


def _turn_towards(current, wanted, max_step):
    delta = (wanted - current + math.pi) % (2.0 * math.pi) - math.pi
    return current + max(-max_step, min(max_step, delta))


class EntityBrain:
    def __init__(self, world_view, noise, rng, nav=None, tuning=None):
        self.world = world_view
        self.noise = noise
        self.rng = rng
        self.nav = nav if nav is not None else nav_module.load()
        self.t = tuning or BrainTuning()
        self.follower = PathFollower(world_view, by="entity")
        self.hearing = Hearing(self.t, rng, self._localize)
        self.body = Body(*layout.ENTITY_SPAWN, layer=nav_module.UPPER)
        self.state = "dormant"
        self.aggression = 0
        self.awareness = 0.0
        self.now = 0.0
        self.kill = False
        self.drone = 0.0
        self.goal = None
        self.last_known = None
        self.lost_time = 0.0
        self.state_time = 0.0
        self.pause_left = 0.0
        self.pause_look = None
        self.search_left = 0.0
        self.search_points = []
        self.attack_time = 0.0
        self.blocked = {}
        self.visits = {}
        self.player_audible = False
        self.log = []
        self.stats = {state: 0.0 for state in C.ENTITY_STATES}
        self.counters = {"stuck": 0, "unstick": 0, "replans": 0, "door_gave_up": 0}
        self._alert_pending = False
        self._no_stalk_until = 0.0
        self._planned_goal = None
        self._planned_at = -9.0
        self._force_replan = False
        self._stuck_streak = 0
        self._door_wait = 0.0
        self._presence_timer = 0.0
        self._heading = None
        self._moved_last = 0.0

    # ---- API pública --------------------------------------------------------
    @property
    def position(self):
        return self.body.pos()

    def set_aggression(self, level):
        self.aggression = int(_clamp(level, 0, 2))

    def activate(self, pos, hunt=True):
        """Acorda a entidade em `pos` (ajustado à célula andável mais próxima).

        Com `hunt=True` ela já sabe, aproximadamente, onde o jogador está e vai investigar.
        """
        layer = self.nav.layer_at(*pos)
        cell = self.nav.nearest_walkable(layer, pos[0], pos[1], radius=3.0)
        if cell is None:
            raise ValueError(f"posição {pos} fora da malha de navegação")
        x, y = self.nav.center_of(*cell)
        self.body = Body(x, y, self.nav.height_at(layer, y), layer, self.body.yaw)
        self.kill = False
        self.awareness = 0.0
        self.follower.clear()
        self.blocked.clear()
        self.last_known = None
        self._alert_pending = hunt
        self._enter("patrol", "ativada")

    def deactivate(self):
        self._enter("dormant", "desativada")
        self.follower.clear()

    def update(self, dt, senses):
        """Um quadro de pensamento. Devolve onde a entidade está e o que ela está fazendo."""
        if self.state == "dormant":
            return self._output(0.0, "idle", None, senses, dt)
        self.now += dt
        self.state_time += dt
        self.stats[self.state] += dt
        self._note_room()
        if self._alert_pending:
            self._alert(senses)
        if self.kill:
            return self._output(0.0, "attack", player_target(senses), senses, dt)
        sighting = self._see(dt, senses)
        heard = self._hear()
        self._decide(senses, sighting, heard)
        speed, anim, look = self._act(dt, senses, sighting)
        self._turn(dt, look)
        return self._output(speed, anim, look, senses, dt)

    # ---- percepção -----------------------------------------------------------
    def _alert(self, senses):
        """Recém-ativada: sabe onde o jogador está, com um erro grande, e vai conferir."""
        self._alert_pending = False
        angle = self.rng.uniform(0.0, 2.0 * math.pi)
        x, y, z = senses.player_pos
        self.last_known = (x + 2.5 * math.cos(angle), y + 2.5 * math.sin(angle), z)
        self.awareness = 0.35
        self._start_investigating(self.last_known, "alerta de ativação")

    def _see(self, dt, senses):
        sighting = look_at_player(self.t, self.world, self.body.pos(), self.body.yaw, senses, self.aggression)
        if sighting.visible:
            change = awareness_change(self.t, sighting, self.aggression, self.state == "stalk", dt)
            self.awareness = _clamp(self.awareness + change)
            self.last_known = tuple(senses.player_pos)
            self.lost_time = 0.0
        elif self._senses_presence(senses):
            self.awareness = max(self.awareness, min(self.awareness + self.t.presence_gain * dt, self.t.presence_cap))
            self._refresh_presence_guess(dt, senses)
        else:
            self.awareness = _clamp(self.awareness + awareness_change(self.t, sighting, self.aggression, False, dt))
        return sighting

    def _senses_presence(self, senses):
        """No mesmo cômodo e bem perto ele sente que há alguém, mesmo sem ver: a consciência sobe até o teto."""
        px, py, pz = senses.player_pos
        if abs(pz - self.body.z) >= 1.5 or math.hypot(px - self.body.x, py - self.body.y) > self.t.presence_radius:
            return False
        return self._room_at(px, py, pz) == self._room_at(*self.body.pos())

    def _refresh_presence_guess(self, dt, senses):
        """A cada segundo atualiza um palpite de onde o jogador está (erro de ~1 m)."""
        self._presence_timer -= dt
        if self._presence_timer <= 0.0:
            self._presence_timer = 1.0
            px, py, pz = senses.player_pos
            self.last_known = (px + self.rng.uniform(-1.0, 1.0), py + self.rng.uniform(-1.0, 1.0), pz)

    def _localize(self, target, origin):
        """Mantém o palpite de onde veio o som no mesmo cômodo da origem (ou sobre a escada, se nasceu nela).

        Um erro de 3 m não pode jogar o alvo para dentro da parede, para outro cômodo ou para fora da casa.
        """
        if self.nav.layer_at(*origin) == nav_module.STAIRS:
            st = layout.STAIRS
            return (min(max(target[0], st.x0 + 0.3), st.x1 - 0.2), min(max(target[1], st.y0), st.y1), origin[2])
        room = self._room_at(*origin)
        for share in (1.0, 0.6, 0.3):
            x = origin[0] + (target[0] - origin[0]) * share
            y = origin[1] + (target[1] - origin[1]) * share
            if self._room_at(x, y, origin[2]) == room:
                return (x, y, origin[2])
        return tuple(origin)

    def _hear(self):
        events = self.noise.heard_by_entity(self.body.pos())
        heard = self.hearing.assess(events, self.now, self.aggression)
        self.player_audible = self.hearing.fresh_player_sound(events)
        if heard is not None and heard.source == "player":
            bumped = min(self.awareness + self.hearing.bump_for(heard), self.t.hearing_cap)
            self.awareness = max(self.awareness, bumped)
        return heard

    # ---- transições -------------------------------------------------------------
    def _decide(self, senses, sighting, heard):
        if self.state == "attack":
            return
        if self._can_kill(sighting, senses):
            self._enter("attack", "perto e à vista")
            return
        if self.state == "chase":
            if heard is not None and heard.source == "player":
                self.last_known, self.lost_time = heard.target, 0.0
            return
        if self.awareness >= self.t.chase_awareness:
            self._start_chase(self.last_known or tuple(senses.player_pos), "consciência alta")
        elif heard is not None and heard.strong:
            self._start_chase(heard.target, f"som forte ({heard.kind})")
        elif heard is not None:
            self._react_to_sound(heard)
        elif self.state in ("patrol", "investigate", "search") and self._should_stalk(senses):
            self._enter("stalk", "jogador perto e quieto")
        elif self.state == "stalk":
            self._reconsider_stalk(senses)

    def _can_kill(self, sighting, senses):
        return (sighting.visible and sighting.distance <= C.ENTITY_KILL_DISTANCE
                and abs(senses.player_pos[2] - self.body.z) < 1.6)

    def _player_is_quiet(self, senses):
        return senses.player_level <= self.t.stalk_quiet_level and senses.player_speed <= self.t.stalk_quiet_speed

    def _should_stalk(self, senses):
        """Espreita quem está perto e quieto. Quem a ilumina com a lanterna apontada é visto de longe: perseguição."""
        if (self.awareness < self.t.stalk_awareness or self.last_known is None or self.now < self._no_stalk_until
                or not self._player_is_quiet(senses)):
            return False
        if flashlight_points_at(self.t, senses, entity_head(self.body.pos())):
            return False
        px, py, pz = senses.player_pos
        return math.hypot(px - self.body.x, py - self.body.y) <= self.t.stalk_radius and abs(pz - self.body.z) < 2.0

    def _reconsider_stalk(self, senses):
        if not self._player_is_quiet(senses) and self.awareness >= self.t.stalk_awareness:
            self._start_chase(self.last_known or tuple(senses.player_pos), "jogador fez barulho durante o espreitar")
        elif self.state_time > self.t.stalk_give_up:
            self._start_search("espreitar sem resultado")
        elif math.hypot(senses.player_pos[0] - self.body.x, senses.player_pos[1] - self.body.y) > 1.5 * self.t.stalk_radius:
            self._start_search("o jogador se afastou")

    def _react_to_sound(self, heard):
        if self.state == "stalk":
            return
        current = self.goal if self.state == "investigate" else None
        if current is not None and heard.source == "ambient" and math.dist(current, heard.target) < 2.0:
            return
        self._start_investigating(heard.target, f"ouviu {heard.kind}")

    # ---- entrada nos estados ------------------------------------------------------
    def _enter(self, state, why):
        if len(self.log) < LOG_LIMIT:
            self.log.append((round(self.now, 2), self.state, state, why))
        self.state = state
        self.state_time = 0.0
        self.pause_left = 0.0
        self.pause_look = None
        self.attack_time = 0.0
        self._planned_goal = None
        if state != "investigate":
            self.goal = None

    def _start_investigating(self, target, why):
        self._enter("investigate", why)
        self.goal = target

    def _start_chase(self, target, why):
        self._enter("chase", why)
        self.goal = None
        self.last_known = target
        self.lost_time = 0.0
        self.follower.clear()

    def _start_search(self, why):
        if self.state == "stalk":
            self._no_stalk_until = self.now + self.t.stalk_cooldown
        self._enter("search", why)
        self.search_left = self.t.scaled(self.t.search_time, self.t.search_time_per_level, self.aggression)
        self.search_points = self._pick_search_points()
        self.follower.clear()

    # ---- ação por estado --------------------------------------------------------------
    def _act(self, dt, senses, sighting):
        handler = {
            "patrol": self._act_patrol, "investigate": self._act_investigate, "stalk": self._act_stalk,
            "chase": self._act_chase, "search": self._act_search, "attack": self._act_attack,
        }[self.state]
        return handler(dt, senses, sighting)

    def _patrol_speed(self):
        return self.t.speed_patrol * (1.0 + self.t.patrol_speed_per_level * self.aggression)

    def _act_patrol(self, dt, senses, sighting):
        if self.pause_left > 0.0:
            self.pause_left -= dt
            return 0.0, ("stare" if self.pause_look else "idle"), self.pause_look
        if self.goal is None and not self._choose_patrol_goal(senses):
            self.pause_left = 1.0
            return 0.0, "idle", None
        report = self._travel(self.goal, self._patrol_speed(), dt)
        if report is None:
            self.goal = None
            return 0.0, "idle", None
        if report.arrived:
            self.goal = None
            self.pause_left = self.rng.uniform(*self.t.patrol_pause)
            self.pause_look = self._pick_look_target()
        return self._speed_of(report, dt), "walk", None

    def _act_investigate(self, dt, senses, sighting):
        if self.pause_left > 0.0:
            self.pause_left -= dt
            if self.pause_left <= 0.0:
                self._enter("patrol", "nada encontrado")
            return 0.0, "stare", self.pause_look
        report = self._travel(self.goal, self._patrol_speed() * self.t.speed_investigate_factor, dt)
        if report is None:
            self._enter("patrol", "sem caminho até o som")
            return 0.0, "idle", None
        if report.arrived:
            self.pause_left = self.t.investigate_linger
            self.pause_look = self._pick_look_target()
        return self._speed_of(report, dt), "walk", None

    def _act_stalk(self, dt, senses, sighting):
        goal = self.last_known
        look = player_target(senses) if sighting.visible else None
        if goal is None or math.hypot(goal[0] - self.body.x, goal[1] - self.body.y) < 0.8:
            if not sighting.visible:
                self._start_search("chegou e não havia ninguém")
            return 0.0, "stare", look
        report = self._travel(goal, self.t.speed_stalk, dt, replan_every=1.0)
        if report is None:
            self._start_search("sem caminho no espreitar")
            return 0.0, "idle", None
        return self._speed_of(report, dt), "stalk", look

    def _chase_speed(self):
        return min(MAX_CHASE_SPEED, self.t.speed_chase + self.t.chase_speed_per_level * self.aggression)

    def _act_chase(self, dt, senses, sighting):
        if not sighting.visible and not self.player_audible:
            self.lost_time += dt
            memory = self.t.scaled(self.t.lose_time, self.t.lose_time_per_level, self.aggression)
            if self.lost_time > memory:
                self._start_search("perdeu o jogador")
                return 0.0, "stare", None
        else:
            self.lost_time = 0.0
        look = player_target(senses) if sighting.visible else None
        goal = self.last_known
        arrived = goal is None or math.hypot(goal[0] - self.body.x, goal[1] - self.body.y) < 0.7
        if arrived and not sighting.visible:
            return 0.0, "stare", look
        report = self._travel(goal, self._chase_speed(), dt, replan_every=self.t.replan_seconds if sighting.visible else None)
        if report is None:
            self.lost_time += dt * 2.0
            return 0.0, "stare", look
        return self._speed_of(report, dt), "run", look

    def _act_search(self, dt, senses, sighting):
        self.search_left -= dt
        if self.search_left <= 0.0:
            self.awareness = min(self.awareness, 0.1)
            self._enter("patrol", "busca terminou")
            return 0.0, "idle", None
        if self.pause_left > 0.0:
            self.pause_left -= dt
            return 0.0, "stare", self.pause_look
        if not self.search_points:
            self.search_points = self._pick_search_points()
        report = self._travel(self.search_points[0], self._patrol_speed() * self.t.speed_investigate_factor, dt)
        if report is None or report.arrived:
            self.search_points.pop(0)
            self.pause_left = self.t.search_linger
            self.pause_look = self._pick_look_target()
            return 0.0, "stare", self.pause_look
        return self._speed_of(report, dt), "walk", None

    def _act_attack(self, dt, senses, sighting):
        self.attack_time += dt
        look = player_target(senses)
        distance = math.hypot(senses.player_pos[0] - self.body.x, senses.player_pos[1] - self.body.y)
        if distance > C.ENTITY_KILL_DISTANCE * self.t.attack_cancel_factor:
            self._start_chase(tuple(senses.player_pos), "o jogador escapou do bote")
            return 0.0, "stare", look
        if self.attack_time >= self.t.attack_windup:
            self.kill = True
        return 0.0, "attack", look

    # ---- movimento ---------------------------------------------------------------------
    def _door_cost(self, door_id):
        if self.world.is_locked(door_id) or self.blocked.get(door_id, -1.0) > self.now:
            return None
        return 0.0 if self.world.door_openness(door_id) >= 0.6 else 3.0

    def _needs_plan(self, goal, replan_every):
        if not self.follower.active or self._planned_goal is None or self._force_replan:
            return True
        if math.dist(goal, self._planned_goal) > 0.9:
            return True
        return bool(replan_every) and self.now - self._planned_at >= replan_every

    def _plan(self, goal):
        self._force_replan = False
        self.counters["replans"] += 1
        self._planned_goal, self._planned_at = tuple(goal), self.now
        path = self.nav.find_path(self.body.pos(), goal, self._door_cost, start_layer=self.body.layer)
        if path is None:
            self.follower.clear()
            return False
        self.follower.set_path(path.points, self.body)
        return True

    def _travel(self, goal, speed, dt, replan_every=None):
        """Planeja se preciso e anda um quadro rumo a `goal`. None = sem caminho."""
        if self._needs_plan(goal, replan_every) and not self._plan(goal):
            return None
        before = (self.body.x, self.body.y)
        report = self.follower.step(self.body, speed, dt, self.now)
        self._after_step(before, report, dt)
        return report

    def _after_step(self, before, report, dt):
        dx, dy = self.body.x - before[0], self.body.y - before[1]
        self._moved_last = math.hypot(dx, dy)
        if self._moved_last > 1e-4:
            self._heading = _heading_yaw(dx, dy)
        self._door_wait = self._door_wait + dt if report.waiting_for else 0.0
        if report.blocked_door or self._door_wait > DOOR_WAIT_GIVE_UP:
            door = report.blocked_door or report.waiting_for
            self.blocked[door] = self.now + DOOR_BLOCK_SECONDS
            self.counters["door_gave_up"] += 1
            self._door_wait = 0.0
            self._force_replan = True
        if report.stuck:
            self.counters["stuck"] += 1
            self._force_replan = True
            self._stuck_streak += 1
            if self._stuck_streak >= STUCK_STREAK_TO_UNSTICK:
                self._unstick()
        elif self._moved_last > 0.02:
            self._stuck_streak = 0

    def _unstick(self):
        """Travou várias vezes: volta ao centro da célula andável mais próxima e esquece o alvo atual."""
        self.counters["unstick"] += 1
        self._stuck_streak = 0
        cell = self.nav.nearest_walkable(self.body.layer, self.body.x, self.body.y, radius=2.0)
        if cell is not None:
            self.body.x, self.body.y = self.nav.center_of(*cell)
        self.follower.clear()
        self._planned_goal = None
        if self.state in ("patrol", "investigate"):
            self.goal = None

    @staticmethod
    def _speed_of(report, dt):
        return report.moved / dt if dt > 0 else 0.0

    def _turn(self, dt, look):
        wanted = None
        if look is not None:
            dx, dy = look[0] - self.body.x, look[1] - self.body.y
            if math.hypot(dx, dy) > 1e-3:
                wanted = _heading_yaw(dx, dy)
        elif self._moved_last > 1e-4 and self._heading is not None:
            wanted = self._heading
        if wanted is not None:
            rate = self.t.turn_rate_chase if self.state in ("chase", "attack") else self.t.turn_rate_walk
            self.body.yaw = _turn_towards(self.body.yaw, wanted, rate * dt)

    def _room_at(self, x, y, z):
        """Id do cômodo; aceita que o engine devolva o objeto Room em vez do id."""
        room = self.world.room_at(x, y, z)
        return getattr(room, "id", room)

    # ---- escolhas -------------------------------------------------------------------------
    def _note_room(self):
        room = self._room_at(*self.body.pos())
        if room:
            self.visits[room] = self.now

    def _choose_patrol_goal(self, senses):
        """Sorteia o próximo cômodo (mais tempo sem visita = melhor) e um ponto nele. False se nada é alcançável."""
        here = self._room_at(*self.body.pos())
        rooms = [r for r in layout.ROOMS if r != here and not (r == "garage" and self.world.is_locked("garage_door"))]
        player_room = self._room_at(*senses.player_pos)
        bias = self.t.patrol_player_bias * self.aggression
        scored = []
        for room in rooms:
            stale = min(self.now - self.visits.get(room, -60.0), 90.0)
            hops = len(layout.room_path(here, room) or []) if here else 0
            score = stale + self.rng.uniform(0.0, 25.0) - 4.0 * hops
            if room == player_room and self.rng.random() < bias:
                score += 200.0
            scored.append((score, room))
        for _, room in sorted(scored, reverse=True):
            point = self.nav.random_point_in_room(room, self.rng)
            if point is None:
                continue
            goal = point[:3]
            if self.nav.find_path(self.body.pos(), goal, self._door_cost, start_layer=self.body.layer) is not None:
                self.goal = goal
                return True
        return False

    def _pick_look_target(self):
        """Olha por uma porta do cômodo (60%) ou para uma direção qualquer."""
        here = self._room_at(*self.body.pos())
        links = [link for _, link in layout.neighbors(here)] if here else []
        eye_z = self.body.z + 1.6
        if links and self.rng.random() < 0.6:
            link = self.rng.choice(links)
            return (link.x, link.y, eye_z)
        angle = self.rng.uniform(0.0, 2.0 * math.pi)
        return (self.body.x + 4.0 * math.cos(angle), self.body.y + 4.0 * math.sin(angle), eye_z)

    def _pick_search_points(self):
        """Último ponto conhecido e alguns pontos nos cômodos vizinhos, do mais perto ao mais longe."""
        centre = self.last_known or self.body.pos()
        room_id = self._room_at(*centre) or self._room_at(*self.body.pos())
        rooms = [room_id] if room_id else []
        for neighbour, link in layout.neighbors(room_id) if room_id else []:
            if link.opening and self.world.is_locked(link.opening):
                continue
            rooms.append(neighbour)
        points = [tuple(centre)]
        for room in self.rng.sample(rooms, min(len(rooms), 3)):
            point = self.nav.random_point_in_room(room, self.rng)
            if point is not None:
                points.append(point[:3])
        first, rest = points[0], sorted(points[1:], key=lambda p: math.dist(p, self.body.pos()))
        return [first] + rest

    # ---- saída ---------------------------------------------------------------------------------
    def _output(self, speed, anim, look, senses, dt):
        step_noise = None
        if speed > 0.3:
            step_noise = {"chase": "step_chase", "stalk": "step_stalk"}.get(self.state, "step_patrol")
        return BrainOutput(self.body.x, self.body.y, self.body.z, self.body.yaw, speed, self.state, anim,
                           look_target=tuple(look) if look is not None else None, kill=self.kill,
                           drone=self._drone(senses, dt), step_noise=step_noise, awareness=self.awareness)

    def _drone(self, senses, dt):
        """Zumbido que cresce com a proximidade e some por completo enquanto ela espreita."""
        if self.state in ("dormant", "stalk"):
            self.drone = 0.0
            return 0.0
        px, py, pz = senses.player_pos
        distance = math.hypot(px - self.body.x, py - self.body.y) + 2.0 * abs(pz - self.body.z)
        target = _clamp((self.t.drone_far - distance) / (self.t.drone_far - self.t.drone_near)) ** 1.5
        self.drone += (target - self.drone) * min(1.0, dt * self.t.drone_smoothing)
        return self.drone
