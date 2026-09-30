"""Segue um caminho da malha: anda, para diante de porta fechada, pede para abri-la e nota quando trava."""
import math
from dataclasses import dataclass
from typing import Optional

OPEN_REQUEST_DISTANCE = 1.6     # a que distância da porta pede para abri-la
DOOR_STOP_DISTANCE = 0.8        # fica parado aqui até a folha abrir o bastante
DOOR_OPEN_ENOUGH = 0.6
DOOR_WAIT_LIMIT = 3.5           # esperando a porta além disto: desiste dela
STUCK_WINDOW = 1.0
STUCK_FRACTION = 0.25           # andou menos que isto da distância esperada = travado


@dataclass
class Body:
    x: float
    y: float
    z: float
    layer: int
    yaw: float = 0.0

    def pos(self):
        return (self.x, self.y, self.z)


@dataclass
class StepReport:
    moved: float = 0.0
    arrived: bool = False
    waiting_for: Optional[str] = None       # porta fechada diante do corpo
    blocked_door: Optional[str] = None      # porta trancada ou que não abriu: precisa de outro caminho
    stuck: bool = False


class PathFollower:
    def __init__(self, world, by="entity"):
        self.world = world
        self.by = by
        self.path = []
        self.index = 0
        self._segment_start = None
        self._door_wait = 0.0
        self._last_request = -9.0
        self._window_time = 0.0
        self._window_origin = None

    @property
    def active(self):
        return self.index < len(self.path)

    @property
    def goal(self):
        return self.path[-1] if self.path else None

    def set_path(self, waypoints, body):
        self.path, self.index = list(waypoints), 0
        self._segment_start = (body.x, body.y, body.z)
        self._door_wait = 0.0
        self._reset_window()

    def clear(self):
        self.path, self.index = [], 0
        self._reset_window()

    def remaining(self, body):
        """Metros que faltam até o fim do caminho."""
        if not self.active:
            return 0.0
        total, x, y = 0.0, body.x, body.y
        for waypoint in self.path[self.index:]:
            total += math.hypot(waypoint.x - x, waypoint.y - y)
            x, y = waypoint.x, waypoint.y
        return total

    def step(self, body, speed, dt, now):
        """Anda `speed * dt` metros ao longo do caminho, respeitando portas."""
        report = StepReport()
        budget = speed * dt
        while budget > 1e-9 and self.active:
            target = self.path[self.index]
            gap = math.hypot(target.x - body.x, target.y - body.y)
            allowed = gap
            if target.door and self.world.door_openness(target.door) < DOOR_OPEN_ENOUGH:
                allowed = max(0.0, gap - DOOR_STOP_DISTANCE)
                self._deal_with_door(target, gap, now, dt, report)
            travel = min(budget, allowed, gap)
            self._advance(body, target, travel, gap)
            report.moved += travel
            budget -= travel
            if travel >= gap - 1e-9:
                self._arrive(body, target)
            else:
                break
        report.arrived = not self.active
        self._watch_progress(body, speed, dt, report)
        return report

    def _deal_with_door(self, target, gap, now, dt, report):
        if gap > OPEN_REQUEST_DISTANCE:
            self._door_wait = 0.0
            return
        if now - self._last_request >= 1.0:
            self._last_request = now
            if not self.world.open_door(target.door, self.by):
                report.blocked_door = target.door
                return
        if gap <= DOOR_STOP_DISTANCE + 0.05:
            self._door_wait += dt
            report.waiting_for = target.door
            if self._door_wait > DOOR_WAIT_LIMIT:
                report.blocked_door = target.door

    def _advance(self, body, target, travel, gap):
        if travel <= 0.0 or gap <= 1e-9:
            return
        start_x, start_y, start_z = self._segment_start
        body.x += (target.x - body.x) / gap * travel
        body.y += (target.y - body.y) / gap * travel
        span = math.hypot(target.x - start_x, target.y - start_y)
        done = 1.0 if span < 1e-9 else min(1.0, math.hypot(body.x - start_x, body.y - start_y) / span)
        body.z = start_z + (target.z - start_z) * done

    def _arrive(self, body, target):
        body.x, body.y, body.z, body.layer = target.x, target.y, target.z, target.layer
        self._segment_start = (target.x, target.y, target.z)
        self._door_wait = 0.0
        self.index += 1

    def _reset_window(self):
        self._window_time = 0.0
        self._window_origin = None

    def _watch_progress(self, body, speed, dt, report):
        if speed <= 0.05 or not self.active or report.waiting_for is not None:
            self._reset_window()
            return
        if self._window_origin is None:
            self._window_origin = (body.x, body.y)
        self._window_time += dt
        if self._window_time >= STUCK_WINDOW:
            moved = math.hypot(body.x - self._window_origin[0], body.y - self._window_origin[1])
            report.stuck = moved < STUCK_FRACTION * speed * STUCK_WINDOW
            self._reset_window()
