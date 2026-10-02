"""Sistema de ruído: quem faz barulho, por onde ele viaja e quem consegue ouvir.

É o coração do jogo (contrato, seção 5.7). Não usa bpy nem aud: roda em testes e simulações.

Como o valor EFETIVO de um som é calculado
------------------------------------------
Um evento nasce com `loudness` L (0..1, já multiplicada pelo piso pelo chamador) e viaja pelo
grafo de cômodos (`RoomGraph`), não em linha reta. Para um ouvinte em outro ponto:

    efetivo = L * (1 - decay_per_m * comprimento_do_caminho)
              - door_closed_loss * (portas fechadas no caminho)
              - floor_loss       * (mudanças de andar)
              - mask_factor      * ambient_level(cômodo do ouvinte)
    e o resultado é limitado a [0, 1].

Portas parcialmente abertas contam como `1 - abertura/door_open_transparent` de uma porta
fechada (a partir de metade aberta a porta deixa de bloquear). O caminho escolhido é o que MENOS
enfraquece o som, então uma porta aberta mais longe pode vencer uma fechada mais perto.

Exemplo numérico: passo no carpete, L = 0.30 * 0.55 = 0.165, ouvinte na mesma sala a 2 m,
sala com ambiente 0.06:
    0.165 * (1 - 0.085 * 2) - 0.9 * 0.06 = 0.137 - 0.054 = 0.083   (acima do limiar 0.08: ouvido)
A 3 m: 0.165 * 0.745 - 0.054 = 0.069 (abaixo do limiar: passa despercebido).
Correr no azulejo (L = 0.75 * 1.15 = 0.86) a 6 m de caminho, com uma porta fechada no meio:
    0.86 * (1 - 0.51) - 0.35 - 0.9 * 0.03 = 0.42 - 0.35 - 0.027 = 0.046 (a porta salva o jogador).

Eventos simultâneos se combinam por "ou probabilístico" (1 - prod(1 - e_i)): dois sons de 0.5
dão 0.75, nunca passam de 1 e o mais forte domina.
Ao avaliar um evento AMBIENTAL, o próprio evento não mascara a si mesmo.

Este módulo também sorteia eventos ambientais (`schedule_ambient_events`) para que o silêncio
da casa não seja previsível.
"""
import heapq
import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from .. import conventions as C
from .. import layout

HEAR_THRESHOLD = 0.08

SOURCES = ("player", "entity", "ambient")


@dataclass(frozen=True)
class NoiseRules:
    """Todos os números que governam o ruído. Troque-os aqui (ou passe outra instância)."""
    decay_per_m: float = C.NOISE_DECAY_PER_M
    door_closed_loss: float = C.NOISE_DOOR_CLOSED_LOSS
    floor_loss: float = C.NOISE_FLOOR_LOSS
    mask_factor: float = C.NOISE_MASK_FACTOR
    hear_threshold: float = HEAR_THRESHOLD
    door_open_transparent: float = 0.5     # abertura (0..1) a partir da qual a porta não bloqueia mais
    hold_fraction: float = 0.35            # fração do ttl em força total; depois cai linearmente a 0
    hear_window: float = 0.35              # a entidade só percebe um som pontual enquanto ele é novo (s)
    sustained_ttl: float = 2.0             # eventos com ttl a partir disto (telefone tocando) valem a vida toda
    merge_distance: float = 0.35           # emissões contínuas iguais e próximas viram um evento só
    merge_window: float = 0.15
    max_events: int = 96
    hud_rise_tau: float = 0.06             # medidor: sobe rápido...
    hud_fall_tau: float = 1.2              # ...e cai devagar
    ambient_mean_interval: float = 24.0    # segundos entre eventos ambientais (média)
    ambient_min_interval: float = 8.0


# --------------------------------------------------------------------------
# Eventos
# --------------------------------------------------------------------------
@dataclass
class NoiseEvent:
    uid: int
    source: str
    kind: str
    pos: tuple
    room: str
    loudness: float
    ttl: float
    age: float = 0.0
    opening: str = ""       # porta que é a origem do som (ranger, batida): ela mesma não o abafa
    _reach_cache: dict = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class HeardEvent:
    """O que a entidade ouviu: onde foi, quão forte chegou (efetivo) e há quanto tempo."""
    uid: int
    source: str
    kind: str
    pos_source: tuple
    loudness: float
    age: float
    room: str


@dataclass(frozen=True)
class PathInfo:
    """Caminho do som entre dois pontos: metros, portas fechadas (equivalentes) e andares."""
    length: float
    closed_doors: float
    floors: int


def step_loudness(mode, surface):
    """Ruído de um passo: `mode` em NOISE_PLAYER (walk, crouch_walk, run) x multiplicador do piso."""
    return min(1.0, C.NOISE_PLAYER[mode] * C.SURFACE_NOISE_MULT.get(surface, 1.0))


# --------------------------------------------------------------------------
# Grafo de cômodos
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Waypoint:
    index: int
    x: float
    y: float
    z: float
    opening: str        # id da porta/arco ('' na escada)
    kind: str           # 'door' | 'arch' | 'stairs_bottom' | 'stairs_top'
    rooms: tuple

    @property
    def pos(self):
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class Reach:
    """Melhor jeito de o som chegar a um ponto de passagem."""
    weakening: float     # quanto o som perdeu até aqui (em unidades de loudness)
    length: float        # metros percorridos
    door_share: float    # portas fechadas equivalentes no caminho
    floors: int


def _dist(a, b):
    """Distância horizontal: a altura das fontes (pé, peito) não deve alongar o caminho."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _slope_length(a, b):
    """Comprimento real da escada, que sobe 2,8 m ao longo dos ~4,6 m de percurso."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


class RoomGraph:
    """Pontos de passagem (portas, arcos, pé e topo da escada) ligando os cômodos.

    Dentro de um cômodo dois pontos quaisquer se enxergam em linha reta (cômodos são retângulos).
    """

    def __init__(self):
        self.waypoints = []
        st = layout.STAIRS
        for link in layout.links():
            if link.kind == "stairs":
                mid_x = (st.x0 + st.x1) / 2
                self._add(mid_x, st.y0 - 0.2, st.z0, "", "stairs_bottom", (link.a,))
                self._add(mid_x, st.y1 + 0.2, st.z1, "", "stairs_top", (link.b,))
            else:
                self._add(link.x, link.y, link.z, link.opening, link.kind, (link.a, link.b))
        self.stairs_pair = tuple(w.index for w in self.waypoints if w.kind.startswith("stairs"))
        self.by_room = {}
        for waypoint in self.waypoints:
            for room in waypoint.rooms:
                self.by_room.setdefault(room, []).append(waypoint)
        self.door_ids = tuple(w.opening for w in self.waypoints if w.kind == "door")

    def _add(self, x, y, z, opening, kind, rooms):
        self.waypoints.append(Waypoint(len(self.waypoints), x, y, z, opening, kind, rooms))

    def neighbours(self, waypoint):
        """Pontos que compartilham um cômodo com `waypoint`, mais o outro lado da escada."""
        seen = set()
        for room in waypoint.rooms:
            for other in self.by_room[room]:
                if other.index != waypoint.index and other.index not in seen:
                    seen.add(other.index)
                    yield other
        if waypoint.kind.startswith("stairs"):
            for index in self.stairs_pair:
                if index != waypoint.index and index not in seen:
                    yield self.waypoints[index]


_GRAPH = None


def room_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = RoomGraph()
    return _GRAPH


def room_id_at(pos):
    """Cômodo que contém `pos`; fora da casa devolve o mais próximo do mesmo andar."""
    x, y, z = pos
    room = layout.room_at(x, y, z)
    if room is not None:
        return room.id
    level = layout.level_of_z(z)
    best, best_gap = None, float("inf")
    for candidate in layout.rooms_on_level(level):
        rect = candidate.rect
        gap = math.hypot(max(rect.x0 - x, 0.0, x - rect.x1), max(rect.y0 - y, 0.0, y - rect.y1))
        if gap < best_gap:
            best, best_gap = candidate.id, gap
    return best


# --------------------------------------------------------------------------
# Eventos ambientais aleatórios
# --------------------------------------------------------------------------
# kind -> (peso do sorteio, cômodos possíveis ou None = qualquer, ttl)
_AMBIENT_TABLE = {
    "creak": (0.40, None, 1.5),
    "thud": (0.25, None, 1.5),
    "phone": (0.07, ("kitchen", "den", "master", "hall_g"), 4.0),
    "tv_burst": (0.06, ("living",), 1.5),
    "clock_chime": (0.10, ("living", "hall_g"), 3.0),
    "glass": (0.04, ("kitchen", "dining", "living", "bath", "study"), 2.0),
}
_AMBIENT_SPOTS = {"tv_burst": "tv_living", "clock_chime": "grandfather_clock"}
_AMBIENT_SOUNDS = {
    "creak": ("creak_1", "creak_2", "creak_3"), "thud": ("thud_1", "thud_2"), "phone": ("phone_ring",),
    "tv_burst": ("ent_static_burst",), "clock_chime": ("clock_chime",), "glass": ("glass_break",),
}


def sound_for_event(event, rng):
    """Nome do WAV que combina com um evento ambiental (o engine toca junto com o ruído)."""
    return rng.choice(_AMBIENT_SOUNDS[event.kind]) if event.kind in _AMBIENT_SOUNDS else None


# --------------------------------------------------------------------------
# Sistema
# --------------------------------------------------------------------------
class NoiseSystem:
    def __init__(self, door_openness: Optional[Callable] = None, rules: Optional[NoiseRules] = None):
        self.rules = rules or NoiseRules()
        self._door_openness = door_openness or (lambda _door_id: 0.0)
        self._graph = room_graph()
        self._events = []
        self._next_uid = 1
        self._listener = None
        self._last_player_pos = None
        self._hud = {"player": 0.0, "ambient": 0.0, "entity": 0.0}
        self._silence_left = 0.0
        self._ambient_countdown = None
        self.ambient_enabled = True
        self.ambient_rate = 1.0           # multiplicador da frequência dos eventos ambientais

    # ---- emissão e vida dos eventos -----------------------------------
    def emit(self, source, kind, pos, loudness, ttl=1.5, opening=""):
        """Registra um som. Emissões iguais e coladas (zumbido contínuo) renovam o mesmo evento.

        `opening` é o id da porta que faz o som: o ranger de uma porta fechada que está sendo aberta não pode
        ser abafado por ela mesma, senão a entidade colada do outro lado não o ouviria nos primeiros instantes."""
        if self._silence_left > 0.0 or loudness <= 0.0:
            return None
        loudness = min(max(float(loudness), 0.0), 1.0)
        pos = (float(pos[0]), float(pos[1]), float(pos[2]))
        rules = self.rules
        for event in self._events:
            if (event.source == source and event.kind == kind and event.age <= rules.merge_window
                    and _dist(event.pos, pos) <= rules.merge_distance):
                event.age, event.loudness, event.ttl, event.pos = 0.0, max(event.loudness, loudness), max(event.ttl, ttl), pos
                event.opening = opening or event.opening
                event.room = room_id_at(pos)
                event._reach_cache.clear()
                return event
        event = NoiseEvent(self._next_uid, source, kind, pos, room_id_at(pos), loudness, float(ttl), opening=opening)
        self._next_uid += 1
        self._events.append(event)
        if len(self._events) > rules.max_events:
            self._events.pop(0)
        if source == "player":
            self._last_player_pos = pos
        return event

    def update(self, dt):
        """Envelhece e descarta eventos; atualiza os medidores suavizados do HUD."""
        self._silence_left = max(0.0, self._silence_left - dt)
        for event in self._events:
            event.age += dt
        self._events = [e for e in self._events if e.age < e.ttl]
        self._update_hud(dt)

    def silence(self, seconds):
        """Apaga tudo e ignora novas emissões por `seconds` (cutscenes)."""
        self._events.clear()
        self._silence_left = seconds

    def clear(self):
        self._events.clear()
        self._silence_left = 0.0
        self._hud = {key: 0.0 for key in self._hud}

    def set_listener(self, pos):
        """Posição do jogador: base do medidor de ambiente/entidade. O engine chama a cada quadro."""
        self._listener = (float(pos[0]), float(pos[1]), float(pos[2]))

    @property
    def events(self):
        return tuple(self._events)

    def _age_gain(self, event):
        hold = self.rules.hold_fraction * event.ttl
        if event.age <= hold:
            return 1.0
        return max(0.0, 1.0 - (event.age - hold) / max(event.ttl - hold, 1e-6))

    # ---- propagação -----------------------------------------------------
    def _door_losses(self):
        """Perda de cada porta agora: 0 (aberta) até `door_closed_loss` (fechada). Arcos nunca perdem."""
        rules = self.rules
        losses = {}
        for door_id in self._graph.door_ids:
            try:
                openness = float(self._door_openness(door_id))
            except Exception:       # a porta pode não existir ainda no runtime; conta como fechada
                openness = 0.0
            share = 1.0 - min(1.0, max(openness, 0.0) / rules.door_open_transparent)
            losses[door_id] = round(share, 2)
        return losses

    def _reach_map(self, event, door_share):
        """Dijkstra do ponto de origem até cada ponto de passagem, minimizando o enfraquecimento."""
        if event.opening:
            door_share = {**door_share, event.opening: 0.0}
        key = tuple(sorted(door_share.items()))
        cached = event._reach_cache.get(key)
        if cached is not None:
            return cached
        graph = self._graph
        per_metre = event.loudness * self.rules.decay_per_m
        best, queue = {}, []
        for waypoint in graph.by_room.get(event.room, []):
            self._settle(best, queue, waypoint, per_metre, door_share, _dist(event.pos, waypoint.pos), 0.0, 0)
        while queue:
            weakening, index = heapq.heappop(queue)
            here = best[index]
            if weakening > here.weakening + 1e-12:
                continue
            waypoint = graph.waypoints[index]
            for other in graph.neighbours(waypoint):
                changes_floor = waypoint.kind.startswith("stairs") and other.kind.startswith("stairs")
                step = _slope_length(waypoint.pos, other.pos) if changes_floor else _dist(waypoint.pos, other.pos)
                self._settle(best, queue, other, per_metre, door_share, here.length + step,
                             here.door_share, here.floors + int(changes_floor))
        event._reach_cache[key] = best
        return best

    def _settle(self, best, queue, waypoint, per_metre, door_share, length, doors_before, floors):
        """Registra a chegada a `waypoint` se for o caminho mais fraco-perdendo até agora."""
        rules = self.rules
        share = door_share.get(waypoint.opening, 0.0) if waypoint.kind == "door" else 0.0
        doors = doors_before + share
        weakening = per_metre * length + rules.door_closed_loss * doors + rules.floor_loss * floors
        known = best.get(waypoint.index)
        if known is None or weakening < known.weakening - 1e-12:
            best[waypoint.index] = Reach(weakening, length, doors, floors)
            heapq.heappush(queue, (weakening, waypoint.index))

    def _route(self, event, pos, door_share):
        """(enfraquecimento, comprimento, portas, andares) do melhor caminho até `pos`."""
        listener_room = room_id_at(pos)
        per_metre = event.loudness * self.rules.decay_per_m
        if listener_room == event.room:
            length = _dist(event.pos, pos)
            return per_metre * length, length, 0.0, 0
        reach = self._reach_map(event, door_share)
        best = None
        for waypoint in self._graph.by_room.get(listener_room, []):
            arrived = reach.get(waypoint.index)
            if arrived is None:
                continue
            last = _dist(waypoint.pos, pos)
            length = arrived.length + last
            weakening = (per_metre * length + self.rules.door_closed_loss * arrived.door_share
                         + self.rules.floor_loss * arrived.floors)
            if best is None or weakening < best[0]:
                best = (weakening, length, arrived.door_share, arrived.floors)
        return best or (float("inf"), float("inf"), 0.0, 0)

    def set_door_openness(self, door_openness):
        self._door_openness = door_openness or (lambda _door_id: 0.0)

    def path_between(self, source_pos, listener_pos, opening=""):
        """Caminho de menor perda entre dois pontos (o motor de áudio usa isto para a oclusão).

        `opening` é uma porta que não conta como obstáculo (a que está fazendo o som)."""
        probe = NoiseEvent(0, "ambient", "probe", tuple(source_pos), room_id_at(source_pos), 1.0, 1.0, opening=opening)
        _, length, doors, floors = self._route(probe, tuple(listener_pos), self._door_losses())
        return PathInfo(length, doors, floors)

    def _masking(self, room, exclude_uid=None):
        return self.rules.mask_factor * self._ambient_level(room, exclude_uid)

    def _effective(self, event, pos, door_share, mask_cache):
        weakening, _, _, _ = self._route(event, pos, door_share)
        if not math.isfinite(weakening):
            return 0.0
        room = room_id_at(pos)
        if event.source == "ambient":
            mask = self._masking(room, event.uid)
        else:
            if room not in mask_cache:
                mask_cache[room] = self._masking(room)
            mask = mask_cache[room]
        value = event.loudness * self._age_gain(event) - weakening - mask
        return min(max(value, 0.0), 1.0)

    def effective(self, event, pos):
        """Valor efetivo de UM evento para um ouvinte em `pos` (0..1)."""
        return self._effective(event, pos, self._door_losses(), {})

    def explain(self, event, pos):
        """Decomposição do cálculo (para depurar e para os testes)."""
        door_share = self._door_losses()
        weakening, length, doors, floors = self._route(event, pos, door_share)
        rules = self.rules
        return {
            "path_length": length, "closed_doors": doors, "floors": floors,
            "distance_loss": event.loudness * rules.decay_per_m * length,
            "door_loss": rules.door_closed_loss * doors, "floor_loss": rules.floor_loss * floors,
            "mask": self._masking(room_id_at(pos), event.uid if event.source == "ambient" else None),
            "effective": self._effective(event, pos, door_share, {}),
        }

    # ---- consultas -------------------------------------------------------
    def level_at(self, pos, source=None):
        """Quanto um ouvinte em `pos` percebe agora (0..1), somando eventos ativos (ou só os de `source`)."""
        wanted = {source} if isinstance(source, str) else (set(source) if source else None)
        door_share, mask_cache, quiet = self._door_losses(), {}, 1.0
        for event in self._events:
            if wanted is not None and event.source not in wanted:
                continue
            quiet *= 1.0 - self._effective(event, pos, door_share, mask_cache)
        return 1.0 - quiet

    def heard_by_entity(self, pos):
        """Eventos do jogador e do ambiente que a entidade em `pos` consegue ouvir, do mais forte ao mais fraco."""
        door_share, mask_cache, heard = self._door_losses(), {}, []
        for event in self._events:
            if event.source == "entity" or not self._is_fresh(event):
                continue
            value = self._effective(event, pos, door_share, mask_cache)
            if value >= self.rules.hear_threshold:
                heard.append(HeardEvent(event.uid, event.source, event.kind, event.pos, value, event.age, event.room))
        heard.sort(key=lambda h: -h.loudness)
        return heard

    def _is_fresh(self, event):
        """Um estalo já aconteceu e passou; uma campainha insistente continua chamando por toda a duração.

        Sem isto, abrir uma porta um segundo depois "revelaria" o passo dado atrás dela.
        """
        rules = self.rules
        return event.age <= rules.hear_window or event.ttl >= rules.sustained_ttl

    def _ambient_level(self, room_id, exclude_uid=None):
        room = layout.ROOMS.get(room_id)
        if room is None:
            return 0.0
        centre = room.rect.center
        centre_pos = (centre[0], centre[1], layout.LEVEL_Z[room.level] + 1.0)
        door_share, quiet = self._door_losses(), 1.0 - room.ambient
        for event in self._events:
            if event.source != "ambient" or event.uid == exclude_uid:
                continue
            weakening, _, _, _ = self._route(event, centre_pos, door_share)
            if math.isfinite(weakening):
                contribution = max(event.loudness * self._age_gain(event) - weakening, 0.0)
                quiet *= 1.0 - min(contribution, 1.0)
        return 1.0 - quiet

    def ambient_level(self, room_id):
        """Ruído de fundo do cômodo: `layout.ROOMS[..].ambient` combinado com os eventos ambientais ativos."""
        return self._ambient_level(room_id)

    # ---- medidores do HUD -------------------------------------------------
    def _listener_pos(self):
        return self._listener or self._last_player_pos

    def _hud_targets(self):
        targets = {"player": 0.0, "ambient": 0.0, "entity": 0.0}
        for event in self._events:
            if event.source == "player":
                targets["player"] = max(targets["player"], event.loudness * self._age_gain(event))
        listener = self._listener_pos()
        if listener is not None:
            targets["ambient"] = self._ambient_level(room_id_at(listener))
            targets["entity"] = self.level_at(listener, "entity")
        return targets

    def _update_hud(self, dt):
        for key, target in self._hud_targets().items():
            current = self._hud[key]
            tau = self.rules.hud_rise_tau if target > current else self.rules.hud_fall_tau
            self._hud[key] = current + (target - current) * (1.0 - math.exp(-dt / tau))

    def hud_levels(self):
        """Medidor de som suavizado (sobe rápido, cai devagar): dict(player=, ambient=, entity=)."""
        return dict(self._hud)

    # ---- eventos ambientais aleatórios --------------------------------------
    def schedule_ambient_events(self, dt, rng, player_room=None):
        """Sorteia rangidos, baques, telefone etc. em cômodos onde o jogador NÃO está.

        Devolve os eventos criados neste quadro (normalmente nenhum). O engine toca
        `sound_for_event(evento, rng)` junto. Intervalo médio `ambient_mean_interval`, nunca
        abaixo de `ambient_min_interval`; `ambient_rate` e `ambient_enabled` controlam a frequência.
        """
        if not self.ambient_enabled or self._silence_left > 0.0:
            return []
        player_room = getattr(player_room, "id", player_room)
        if self._ambient_countdown is None:
            self._ambient_countdown = self._next_interval(rng)
        self._ambient_countdown -= dt * self.ambient_rate
        created = []
        while self._ambient_countdown <= 0.0:
            event = self._spawn_ambient(rng, player_room)
            if event is not None:
                created.append(event)
            self._ambient_countdown += self._next_interval(rng)
        return created

    def _next_interval(self, rng):
        rules = self.rules
        spread = max(rules.ambient_mean_interval - rules.ambient_min_interval, 1.0)
        return rules.ambient_min_interval + rng.expovariate(1.0 / spread)

    def _spawn_ambient(self, rng, player_room):
        kinds = list(_AMBIENT_TABLE)
        kind = rng.choices(kinds, weights=[_AMBIENT_TABLE[k][0] for k in kinds])[0]
        _, allowed, ttl = _AMBIENT_TABLE[kind]
        rooms = [r for r in (allowed or tuple(layout.ROOMS)) if r != player_room and r in layout.ROOMS]
        if not rooms:
            return None
        room = layout.ROOMS[rng.choice(rooms)]
        loudness = C.NOISE_AMBIENT_EVENTS[kind] * rng.uniform(0.85, 1.15)
        return self.emit("ambient", kind, self._spot_for(kind, room, rng), loudness, ttl)

    @staticmethod
    def _spot_for(kind, room, rng):
        anchor = layout.ANCHORS.get(_AMBIENT_SPOTS.get(kind, ""))
        if anchor is not None and layout.room_at(anchor.x, anchor.y, anchor.z).id == room.id:
            return (anchor.x, anchor.y, anchor.z + 1.0)
        rect = room.rect
        x = rng.uniform(rect.x0 + 0.6, rect.x1 - 0.6)
        y = rng.uniform(rect.y0 + 0.6, rect.y1 - 0.6)
        return (x, y, layout.LEVEL_Z[room.level] + 1.0)
