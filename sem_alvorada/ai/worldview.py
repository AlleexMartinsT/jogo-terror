"""O que o cérebro precisa saber do mundo, e uma implementação só com a planta para testes.

O engine implementa `WorldView` com as malhas e as portas reais (BVH para a linha de visada,
`DoorManager` para as portas). `LayoutWorldView` usa apenas `layout`: paredes de `solid_rects`
e portas como segmentos que bloqueiam a visão enquanto fechadas.
"""
import math
from typing import Optional, Protocol

from .. import layout

DOOR_BLOCKS_SIGHT_BELOW = 0.35     # abertura (0..1) abaixo da qual a folha bloqueia a visão
SLAB_MIDDLE = 2.7                  # entre o forro (2.6) e o piso de cima (2.8): pontos acima estão no andar 1
DOOR_SECONDS = 0.6                 # tempo para abrir por completo


class WorldView(Protocol):
    def line_of_sight(self, a, b) -> bool:
        """Há visão livre entre os pontos a e b (x, y, z de olhos/peito)?"""

    def door_openness(self, door_id) -> float:
        """0 fechada .. 1 aberta."""

    def open_door(self, door_id, by) -> bool:
        """Pede para abrir a porta (por 'entity' ou 'player'). False se trancada."""

    def is_locked(self, door_id) -> bool:
        """A porta está trancada (intransponível)?"""

    def room_at(self, x, y, z) -> Optional[str]:
        """Id do cômodo em (x, y, z), ou None fora da casa."""


def segment_hits_rect(a, b, rect):
    """Liang-Barsky: o segmento a->b atravessa o retângulo?"""
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - rect.x0), (dx, rect.x1 - a[0]), (-dy, a[1] - rect.y0), (dy, rect.y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


class LayoutWorldView:
    """Mundo mínimo: portas que abrem com o tempo, trancas iniciais da planta, visão contra as paredes."""

    def __init__(self, door_seconds=DOOR_SECONDS):
        self._doors = {o.id: o for o in layout.doors()}
        self._openness = {door_id: 0.0 for door_id in self._doors}
        self._target = dict(self._openness)
        self._locked = {door_id: bool(o.lock) for door_id, o in self._doors.items()}
        self._door_seconds = door_seconds
        self._walls = {level: layout.solid_rects(level) for level in (0, 1)}
        self.opened_by = []                 # (porta, quem) de cada pedido, para os testes

    # ---- portas -----------------------------------------------------------
    def update(self, dt):
        """Anima as portas em direção ao alvo (o engine real faz isto no DoorManager)."""
        step = dt / self._door_seconds
        for door_id, target in self._target.items():
            current = self._openness[door_id]
            self._openness[door_id] = min(target, current + step) if target > current else max(target, current - step)

    def door_openness(self, door_id):
        return self._openness.get(door_id, 1.0)

    def open_door(self, door_id, by):
        if self._locked.get(door_id, False) or door_id not in self._doors:
            return False
        self.opened_by.append((door_id, by))
        self._target[door_id] = 1.0
        return True

    def is_locked(self, door_id):
        return self._locked.get(door_id, False)

    def set_openness(self, door_id, value):
        """Força a abertura já (o jogador abrindo/fechando nos testes)."""
        self._openness[door_id] = self._target[door_id] = value

    def close_door(self, door_id):
        self._target[door_id] = 0.0

    def lock(self, door_id):
        self._locked[door_id] = True

    def unlock(self, door_id):
        self._locked[door_id] = False

    # ---- espaço ---------------------------------------------------------------
    def room_at(self, x, y, z):
        room = layout.room_at(x, y, z)
        return room.id if room else None

    def line_of_sight(self, a, b):
        """Os pontos são olhos/peito: o andar sai da altura em relação à laje, não do limiar dos pés."""
        level_a, level_b = int(a[2] >= SLAB_MIDDLE), int(b[2] >= SLAB_MIDDLE)
        if level_a != level_b:
            return False
        p, q = (a[0], a[1]), (b[0], b[1])
        if any(segment_hits_rect(p, q, wall) for wall in self._walls[level_a]):
            return False
        for door_id, door in self._doors.items():
            if door.level == level_a and self._openness[door_id] < DOOR_BLOCKS_SIGHT_BELOW:
                if segment_hits_rect(p, q, _door_rect(door)):
                    return False
        return True


def _door_rect(door):
    if door.axis == "x":
        return layout.Rect(door.a, door.pos - 0.04, door.b, door.pos + 0.04)
    return layout.Rect(door.pos - 0.04, door.a, door.pos + 0.04, door.b)


def horizontal_distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
