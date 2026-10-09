"""Percepção da entidade: o que ela vê (cone, luz, linha de visada) e o que ela ouve (ruído)."""
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

ENTITY_EYE_HEIGHT = 2.3
PLAYER_CHEST = 1.35
PLAYER_CHEST_CROUCHED = 1.00


@dataclass
class Senses:
    """O que o engine informa a cada quadro. `player_level` é o ruído que o jogador emite agora (0..1)."""
    player_pos: tuple
    player_yaw: float = 0.0
    player_level: float = 0.0
    player_speed: float = 0.0
    player_crouching: bool = False
    flashlight_on: bool = False
    flashlight_dir: Optional[tuple] = None       # vetor unitário (x, y, z); None = para onde o jogador olha


@dataclass
class Sighting:
    visible: bool
    distance: float
    reach: float          # alcance de visão calculado neste quadro


@dataclass
class Heard:
    """Som escolhido pela entidade como o mais interessante neste quadro."""
    target: tuple         # onde ela acha que foi (origem mais o erro de localização)
    loudness: float
    kind: str
    source: str
    strong: bool          # forte ou repetido: vai direto à perseguição
    uid: int


def player_target(senses):
    z_offset = PLAYER_CHEST_CROUCHED if senses.player_crouching else PLAYER_CHEST
    x, y, z = senses.player_pos
    return (x, y, z + z_offset)


def entity_head(pos):
    return (pos[0], pos[1], pos[2] + ENTITY_EYE_HEIGHT)


def angle_between(a, b):
    """Ângulo (rad) entre dois vetores 2D."""
    na, nb = math.hypot(*a), math.hypot(*b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return math.acos(max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) / (na * nb))))


def flashlight_points_at(tuning, senses, head):
    """A lanterna do jogador está acesa e o cone dela pega a cabeça da entidade?"""
    if not senses.flashlight_on:
        return False
    x, y, z = player_target(senses)
    to_head = (head[0] - x, head[1] - y, head[2] - z)
    beam = senses.flashlight_dir or (-math.sin(senses.player_yaw), math.cos(senses.player_yaw), 0.0)
    norm = math.sqrt(sum(v * v for v in to_head)) * math.sqrt(sum(v * v for v in beam))
    if norm < 1e-9:
        return True
    cosine = sum(a * b for a, b in zip(to_head, beam)) / norm
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine)))) <= tuning.flash_aim_deg


def vision_range(tuning, senses, head, aggression):
    """Até onde ela enxerga o jogador neste quadro (m)."""
    if flashlight_points_at(tuning, senses, head):
        reach = tuning.flash_range
    elif senses.flashlight_on:
        reach = tuning.dark_range * tuning.glow_range_factor
    else:
        reach = tuning.dark_range
    if senses.player_crouching:
        reach *= tuning.crouch_vision
    if senses.player_speed < tuning.still_speed:
        reach *= tuning.still_vision
    elif senses.player_speed > tuning.run_speed:
        reach *= tuning.run_vision
    return reach * (1.0 + 0.1 * aggression)


def look_at_player(tuning, world, position, yaw, senses, aggression):
    """Vê o jogador? Precisa estar no alcance, dentro do cone (ou colado) e com linha de visada livre."""
    head = entity_head(position)
    target = player_target(senses)
    distance = math.hypot(target[0] - position[0], target[1] - position[1])
    reach = vision_range(tuning, senses, head, aggression)
    sighting = Sighting(False, distance, reach)
    if abs(target[2] - head[2]) > 3.2 or distance > reach:
        return sighting
    facing = (-math.sin(yaw), math.cos(yaw))
    off_axis = angle_between(facing, (target[0] - position[0], target[1] - position[1]))
    if distance > tuning.touch_range and math.degrees(off_axis) > tuning.fov_deg / 2.0:
        return sighting
    sighting.visible = bool(world.line_of_sight(head, target))
    return sighting


def awareness_change(tuning, sighting, aggression, stalking, dt):
    """Variação da consciência neste quadro: sobe com a proximidade, desce devagar quando não vê."""
    if not sighting.visible:
        return -tuning.decay_per_s * dt * (1.0 - 0.25 * aggression)
    closeness = max(0.0, 1.0 - sighting.distance / max(sighting.reach, 1e-6))
    rate = tuning.gain_far + tuning.gain_near * closeness
    rate *= 1.0 + 0.25 * aggression
    if stalking and sighting.distance > 1.6:
        rate *= tuning.stalk_gain_factor
    return rate * dt


class Hearing:
    """Escolhe, entre os sons que chegaram, o que merece reação; lembra dos recentes para detectar repetição."""

    def __init__(self, tuning, rng, keep_on_layer=None):
        self.tuning = tuning
        self.rng = rng
        self._keep_on_layer = keep_on_layer or (lambda target, origin: target)
        self._recent = deque()          # (instante, uid) de sons do jogador acima do mínimo de repetição
        self._handled = {}              # uid -> instante em que já reagimos

    def assess(self, heard_events, now, aggression):
        """Devolve o `Heard` mais interessante ainda não tratado (ou None)."""
        t = self.tuning
        self._forget(now)
        best, best_interest = None, 0.0
        for event in heard_events:
            if event.source == "player" and event.loudness >= t.repeat_min_loudness:
                if all(uid != event.uid for _, uid in self._recent):
                    self._recent.append((now, event.uid))
            if event.uid in self._handled:
                continue
            interest = self._interest(event)
            if interest > best_interest:
                best, best_interest = event, interest
        if best is None:
            return None
        self._handled[best.uid] = now
        return self._describe(best, aggression)

    def fresh_player_sound(self, heard_events):
        """Há som do jogador acima do limiar neste quadro (mesmo já tratado)? Mantém a perseguição viva."""
        return any(event.source == "player" for event in heard_events)

    def _forget(self, now):
        while self._recent and now - self._recent[0][0] > self.tuning.repeat_window:
            self._recent.popleft()
        for uid in [u for u, t in self._handled.items() if now - t > 8.0]:
            del self._handled[uid]

    def _interest(self, event):
        if event.source == "player":
            return event.loudness
        weight = self.tuning.ambient_weight.get(event.kind, 0.5)
        score = event.loudness * weight
        return score if score >= self.tuning.distract_min_loudness else 0.0

    def _describe(self, event, aggression):
        t = self.tuning
        threshold = t.chase_loudness + t.chase_loudness_per_level * aggression
        repeated = len(self._recent) >= t.repeat_count
        strong = event.source == "player" and (event.loudness >= threshold or repeated)
        if event.source == "ambient":
            target = event.pos_source
        else:
            radius = max(0.3, t.error_radius_max * (1.0 - min(event.loudness, 1.0)) * (1.0 - 0.2 * aggression))
            angle, spread = self.rng.uniform(0.0, 2.0 * math.pi), radius * math.sqrt(self.rng.random())
            x, y, z = event.pos_source
            target = self._keep_on_layer((x + spread * math.cos(angle), y + spread * math.sin(angle), z), event.pos_source)
        return Heard(target, event.loudness, event.kind, event.source, strong, event.uid)

    def bump_for(self, heard):
        """Quanto um som do jogador soma à consciência (limitado por `hearing_cap` pelo chamador)."""
        return self.tuning.hearing_bump * heard.loudness if heard.source == "player" else 0.0
