"""Substitutos simples para módulos que podem não existir (áudio e sistema de ruído).

Servem a duas coisas: o jogo continua rodando se `audio` falhar ao importar, e os testes
podem inspecionar o que foi tocado (`NullAudio.played`) sem depender de dispositivo de som.
"""
from collections import deque
from dataclasses import dataclass

from .. import conventions as C
from .. import layout

HEAR_THRESHOLD = 0.08


class NullAudio:
    """Mesma interface do AudioEngine, sem tocar nada. Guarda o histórico para os testes."""

    def __init__(self):
        self.played = deque(maxlen=400)       # (nome, pos, volume)
        self.loops = {}                       # chave -> (nome, pos, volume)
        self.footsteps = deque(maxlen=200)    # (superfície, intensidade)
        self.listener = ((0.0, 0.0, 0.0), 0.0)

    def update_listener(self, pos, yaw):
        self.listener = (pos, yaw)

    def play(self, name, pos=None, volume=1.0, pitch=1.0):
        self.played.append((name, pos, volume))

    def loop(self, key, name, pos=None, volume=1.0, pitch=1.0):
        self.loops[key] = (name, pos, volume)

    def stop(self, key):
        self.loops.pop(key, None)

    def footstep(self, surface, intensity, pos=None):
        self.footsteps.append((surface, intensity))

    def set_master(self, value):
        pass

    def shutdown(self):
        self.loops.clear()

    def played_names(self):
        return [entry[0] for entry in self.played]


@dataclass
class HeardEvent:
    pos_source: tuple
    loudness: float
    kind: str
    age: float


@dataclass
class _Event:
    source: str
    kind: str
    pos: tuple
    loudness: float
    ttl: float
    age: float = 0.0


class FallbackNoise:
    """Sistema de ruído mínimo (distância em linha reta, sem portas) com a interface de audio.noise."""

    def __init__(self, door_openness=None):
        self.events = []
        self._smooth = {"player": 0.0, "ambient": 0.0, "entity": 0.0}
        self._listener = (0.0, 0.0, 0.0)
        self._room = None

    def emit(self, source, kind, pos, loudness, ttl=1.5, opening=""):
        self.events.append(_Event(source, kind, tuple(pos), loudness, ttl))

    def update(self, dt):
        for event in self.events:
            event.age += dt
        self.events = [e for e in self.events if e.age < e.ttl]
        self._decay(dt)

    def set_listener(self, pos):
        room = layout.room_at(*pos)
        self._listener, self._room = pos, room.id if room else None

    def silence(self, seconds):
        self.events.clear()

    def schedule_ambient_events(self, dt, rng, player_room=None):
        return []

    @staticmethod
    def _heard_from(event, pos):
        dist = sum((a - b) ** 2 for a, b in zip(pos, event.pos)) ** 0.5
        return event.loudness * max(0.0, 1.0 - C.NOISE_DECAY_PER_M * dist)

    def level_at(self, pos, source=None):
        return max((self._heard_from(e, pos) for e in self.events
                    if source is None or e.source == source), default=0.0)

    def heard_by_entity(self, pos):
        heard = []
        for event in self.events:
            effective = self._heard_from(event, pos)
            if event.source != "entity" and effective >= HEAR_THRESHOLD:
                heard.append(HeardEvent(event.pos, effective, event.kind, event.age))
        return heard

    def ambient_level(self, room_id):
        room = layout.ROOMS.get(room_id)
        return room.ambient if room else 0.0

    def _decay(self, dt):
        targets = {"player": self.level_at(self._listener, "player"),
                   "ambient": self.ambient_level(self._room),
                   "entity": self.level_at(self._listener, "entity")}
        for key, target in targets.items():
            rate = 12.0 if target > self._smooth[key] else 1.6
            self._smooth[key] += (target - self._smooth[key]) * min(1.0, rate * dt)

    def hud_levels(self):
        return dict(self._smooth)


class NullArm:
    """Braço de mentira: aceita os comandos do contrato do corpo (docs/FASE3.md) e não faz nada."""
    ready = False

    def set_target(self, position, rotation_deg=(0.0, 0.0, 0.0), weight=1.0):
        pass

    def set_fingers(self, curls, spread=0.0, blend=1.0):
        pass

    def release(self, blend=1.0):
        pass

    def hold(self, obj, offset=None):
        pass

    def drop(self, obj=None):
        pass

    def hand_world_position(self):
        return None


class NullBody:
    """Ocupa o lugar do BodyRig quando o módulo `body` não existe (ou não foi construído no .blend)."""
    visible = False

    def __init__(self):
        self._arms = {"L": NullArm(), "R": NullArm()}

    def set_visible(self, visible):
        self.visible = False

    def update(self, dt, player, bob=(0.0, 0.0)):
        pass

    def arm(self, side):
        return self._arms[side]

    def place(self, x, y, z, yaw):
        pass

    def attach_view(self, camera_obj):
        pass

    def pose(self, name, seconds=0.0):
        pass

    def eye_position(self, pose="stand"):
        """Sem corpo, os olhos ficam na altura do jogador em pé, no ponto de `place`."""
        return (0.0, 0.0, 1.65)

    def reset(self):
        pass
