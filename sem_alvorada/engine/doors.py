"""Portas: abrir/fechar animado, trancas, folha como segmento de colisão e visada.

Os dados vêm de `layout` (dobradiça, ângulos, tranca). Se o pivô `Door_<id>` existir na cena,
as propriedades dele têm a palavra final e a rotação é escrita nele a cada quadro.
"""
import math
from dataclasses import dataclass
from typing import Optional

from .. import conventions as C
from .. import layout
from . import collision

OPEN_SPEED = 1.7          # fração da abertura por segundo
CLOSE_SPEED = 1.4
SLAM_SPEED = 7.0
LEAF_HALF_THICKNESS = 0.03
NEAR_OPEN = 0.5           # acima disso a porta conta como "aberta" para alternar
SIGHT_HEIGHT = layout.DOOR_H


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
    speed: float = OPEN_SPEED
    segment: tuple = (0.0, 0.0, 0.0, 0.0, LEAF_HALF_THICKNESS)

    @property
    def yaw(self):
        return self.closed_yaw + (self.open_yaw - self.closed_yaw) * self.openness

    @property
    def floor_z(self):
        return layout.LEVEL_Z[self.level]

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
    hinge = (plan["hinge"][0], plan["hinge"][1])
    closed_yaw, open_yaw, lock = plan["closed_yaw"], plan["open_yaw"], op.lock
    if pivot is not None:
        origin = collision.object_position(pivot)
        hinge = (origin[0], origin[1])
        closed_yaw = pivot.get(C.P_DOOR_CLOSED, closed_yaw)
        open_yaw = pivot.get(C.P_DOOR_OPEN, open_yaw)
        lock = pivot.get(C.P_LOCK, lock)
    door = Door(op.id, op.level, hinge, closed_yaw, open_yaw, op.width - 0.02, lock or "", pivot)
    door.refresh_segment()
    return door


class DoorManager:
    def __init__(self, game, scene):
        self.game = game
        self.state = game.state
        self.doors = {op.id: _read_door(op, scene) for op in layout.doors()}
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

    # ---- comandos ----
    def set_openness(self, door_id, fraction, speed=OPEN_SPEED):
        """Move a porta até `fraction` animando (usado por cutscenes)."""
        door = self.doors.get(door_id)
        if door is not None:
            door.target = min(max(fraction, 0.0), 1.0)
            door.speed = speed

    def snap(self, door_id, fraction):
        """Coloca a porta em `fraction` agora, sem animar."""
        door = self.doors.get(door_id)
        if door is None:
            return
        door.target = door.openness = min(max(fraction, 0.0), 1.0)
        door.refresh_segment()
        self._write(door)

    def reset(self):
        """Todas fechadas, sem animação (novo jogo e checkpoint)."""
        for door_id in self.doors:
            self.snap(door_id, 0.0)

    def toggle(self, door_id, hurried=False):
        """Alterna a porta pelo jogador. Devolve 'opened' | 'closed' | 'slammed' | 'locked'."""
        door = self.doors[door_id]
        if self.state.is_locked(door.lock):
            self.game.sound("door_locked", self.center(door_id), 0.9)
            self.game.make_noise("flash_click", self.center(door_id), C.NOISE_PLAYER["flash_click"])
            return "locked"
        mid = self.center(door_id)
        if door.target > NEAR_OPEN:
            door.target = 0.0
            if hurried:
                door.speed = SLAM_SPEED
                self.game.make_noise("door_slam", mid, C.NOISE_PLAYER["door_slam"], sound="door_slam")
                return "slammed"
            door.speed = CLOSE_SPEED
            self.game.make_noise("door_close", mid, C.NOISE_PLAYER["door_close"], sound="door_close")
            return "closed"
        door.target, door.speed = 1.0, OPEN_SPEED
        self.game.make_noise("door_open", mid, C.NOISE_PLAYER["door_open"], sound="door_open")
        return "opened"

    def open_door(self, door_id, by="entity"):
        """A IA abre a porta no caminho. Falso se está trancada ou não é uma porta."""
        door = self.doors.get(door_id)
        if door is None or self.state.is_locked(door.lock):
            return False
        if door.target < NEAR_OPEN:
            door.target, door.speed = 1.0, OPEN_SPEED
            mid = self.center(door_id)
            self.game.make_noise("door_open", mid, C.NOISE_ENTITY["door_open"], sound="door_open", source=by)
        return True

    # ---- quadro a quadro ----
    def update(self, dt, player=None):
        for door in self.doors.values():
            if door.openness == door.target:
                continue
            step = door.speed * dt
            new_value = door.openness + max(-step, min(step, door.target - door.openness))
            closing = new_value < door.openness
            if closing and player is not None and self._would_trap(door, new_value, player):
                continue
            door.openness = new_value
            door.refresh_segment()
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
