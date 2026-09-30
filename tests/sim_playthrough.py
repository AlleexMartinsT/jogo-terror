"""Simula uma partida completa por `Game.tick`, com um robô que joga (sem GUI).

    LIBGL_ALWAYS_SOFTWARE=1 python tests/sim_playthrough.py                  # constrói e joga
    python tests/sim_playthrough.py --blend out/engine/x.blend --skip-cutscenes
    python tests/sim_playthrough.py --minutes 5 --stages world,props,engine

Fase 1 (história): entidade DESATIVADA. O robô anda pela planta com A* sobre a MESMA colisão do
jogo, abre portas com [E], pega lanterna, chave, mapa e 3 pilhas, lê notas, destranca a garagem,
entra no carro e chega ao `ending`.
Fase 2 (caçada, se o módulo `ai` existir): entidade LIGADA; o robô continua jogando por N minutos
simulados e o teste só exige que nada lance exceção (a morte e o retry contam como jogo normal).
"""
import argparse
import heapq
import math
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_engine_fakes as fk  # noqa: E402
from test_engine_fakes import DT, InputState  # noqa: E402

import bpy  # noqa: E402

from sem_alvorada import build as build_module  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout, story  # noqa: E402
from sem_alvorada.engine import collision  # noqa: E402
from sem_alvorada.engine.game import Game  # noqa: E402
from sem_alvorada.engine.player import STAND_HEIGHT  # noqa: E402

OUT_BLEND = os.path.join(fk.ROOT, "out", "engine", "sim.blend")
GRID = 0.25
STAIRS_X = (layout.STAIRS.x0 + layout.STAIRS.x1) / 2
STAIRS_BOTTOM = (STAIRS_X, layout.STAIRS.y0 - 0.5, 0)
STAIRS_TOP = (STAIRS_X, layout.STAIRS.y1 + 0.5, 1)
NEIGHBOURS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
GOAL_SECONDS = 150.0


# --------------------------------------------------------------------------
# Navegação
# --------------------------------------------------------------------------
class NavGrid:
    """Grade de 0,25 m por andar; célula livre = o cilindro do jogador cabe ali, no piso do andar."""

    def __init__(self, game):
        self.game = game
        self.nx = int(19.0 / GRID)
        self.ny = int(10.5 / GRID)
        self.free = {level: self._scan(level) for level in (0, 1)}
        self.locked_cells = set()
        self.leaf_cells = set()
        self.reachable = set()
        self.refresh_locks()

    def cell_center(self, ix, iy):
        return (ix + 0.5) * GRID, (iy + 0.5) * GRID

    def cell_of(self, x, y):
        return int(x / GRID), int(y / GRID)

    def _scan(self, level):
        z = layout.LEVEL_Z[level]
        col = self.game.collision
        grid = [[False] * self.ny for _ in range(self.nx)]
        for ix in range(self.nx):
            for iy in range(self.ny):
                x, y = self.cell_center(ix, iy)
                ground = col.ground(x, y, z)
                if ground is None or abs(ground - z) > 0.03 or not layout_floor(x, y, level):
                    continue
                px, py = col.push_out(x, y, z, C.PLAYER_RADIUS, STAND_HEIGHT)
                if abs(px) + abs(py) < 0.02 and not collision.near_a_drop(col, x, y, z, C.PLAYER_RADIUS,
                                                                          C.PLAYER_STEP_HEIGHT):
                    grid[ix][iy] = True
        return grid

    def refresh_locks(self):
        """Portas trancadas contam como parede para o planejamento; recalcula o que é alcançável."""
        self.locked_cells = set()
        for door in self.game.doors.doors.values():
            if not self.game.doors.is_locked(door.id):
                continue
            op = layout.OPENINGS[door.id]
            for ix in range(self.nx):
                for iy in range(self.ny):
                    x, y = self.cell_center(ix, iy)
                    near_axis = abs((y if op.axis == "x" else x) - op.pos) < 0.6
                    along = op.a - 0.3 <= (x if op.axis == "x" else y) <= op.b + 0.3
                    if near_axis and along and door.level == 0:
                        self.locked_cells.add((ix, iy))
        player = self.game.player
        self._flood((player.x, player.y))

    def is_free(self, level, ix, iy):
        """Célula livre E alcançável desde o início (a colisão deixa células "livres" dentro de móveis)."""
        return (0 <= ix < self.nx and 0 <= iy < self.ny and self.free[level][ix][iy]
                and not (level == 0 and (ix, iy) in self.locked_cells)
                and (level, ix, iy) not in self.leaf_cells
                and (not self.reachable or (level, ix, iy) in self.reachable))

    def refresh_leaves(self):
        """Folhas de porta abertas são paredes finas: bloqueiam as células coladas nelas."""
        self.leaf_cells = set()
        reach = C.PLAYER_RADIUS + 0.04
        for door in self.game.doors.doors.values():
            if door.openness < 0.3:
                continue
            x0, y0, x1, y1, _ = door.segment
            for ix in range(int((min(x0, x1) - reach) / GRID), int((max(x0, x1) + reach) / GRID) + 1):
                for iy in range(int((min(y0, y1) - reach) / GRID), int((max(y0, y1) + reach) / GRID) + 1):
                    cx, cy = self.cell_center(ix, iy)
                    nearest = collision.closest_on_segment(cx, cy, x0, y0, x1, y1)
                    if math.hypot(cx - nearest[0], cy - nearest[1]) < reach:
                        self.leaf_cells.add((door.level, ix, iy))

    def _flood(self, start_xy):
        """Todas as células alcançáveis a partir de start_xy (andar do jogador), inclusive pela escada."""
        self.reachable = set()
        first = self.nearest_free(self.game.player.level, *start_xy)
        seen, stack = set(), [(self.game.player.level, *first)]
        bottom, top = self._stairs_ends()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            level, ix, iy = node
            for dx, dy in NEIGHBOURS:
                if self.is_free(level, ix + dx, iy + dy) and (not (dx and dy) or (
                        self.is_free(level, ix + dx, iy) and self.is_free(level, ix, iy + dy))):
                    stack.append((level, ix + dx, iy + dy))
            if node == bottom:
                stack.append(top)
            elif node == top:
                stack.append(bottom)
        self.reachable = seen

    def nearest_free(self, level, x, y, radius=1.0):
        ix, iy = self.cell_of(x, y)
        span = int(radius / GRID) + 1
        best = None
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                if self.is_free(level, ix + dx, iy + dy):
                    cx, cy = self.cell_center(ix + dx, iy + dy)
                    dist = math.hypot(cx - x, cy - y)
                    if best is None or dist < best[0]:
                        best = (dist, ix + dx, iy + dy)
        return None if best is None else (best[1], best[2])

    def path(self, start, goal):
        """Lista de (x, y, level) do ponto `start` ao `goal` (ambos (x, y, level)), ou None."""
        s = self.nearest_free(start[2], start[0], start[1])
        g = self.nearest_free(goal[2], goal[0], goal[1])
        if s is None or g is None:
            return None
        nodes = self._search((start[2], *s), (goal[2], *g))
        if nodes is None:
            return None
        return self._to_waypoints(nodes)

    def _stairs_ends(self):
        bottom = self.nearest_free(0, STAIRS_BOTTOM[0], STAIRS_BOTTOM[1], 0.6)
        top = self.nearest_free(1, STAIRS_TOP[0], STAIRS_TOP[1], 0.6)
        return (0, *bottom), (1, *top)

    def _search(self, start, goal):
        bottom, top = self._stairs_ends()
        links = {bottom: (top, 14.0), top: (bottom, 14.0)}
        frontier = [(0.0, start)]
        cost, parent = {start: 0.0}, {start: None}
        while frontier:
            _, node = heapq.heappop(frontier)
            if node == goal:
                break
            level, ix, iy = node
            options = []
            for dx, dy in NEIGHBOURS:
                if not self.is_free(level, ix + dx, iy + dy):
                    continue
                if dx and dy and not (self.is_free(level, ix + dx, iy) and self.is_free(level, ix, iy + dy)):
                    continue
                options.append(((level, ix + dx, iy + dy), math.hypot(dx, dy)))
            if node in links:
                options.append(links[node])
            for nxt, step in options:
                new_cost = cost[node] + step
                if new_cost < cost.get(nxt, 1e9):
                    cost[nxt], parent[nxt] = new_cost, node
                    remaining = math.hypot(nxt[1] - goal[1], nxt[2] - goal[2]) * (1.0 if nxt[0] == goal[0] else 0.5)
                    heapq.heappush(frontier, (new_cost + remaining, nxt))
        if goal not in parent:
            return None
        chain = []
        node = goal
        while node is not None:
            chain.append(node)
            node = parent[node]
        return chain[::-1]

    def _to_waypoints(self, nodes):
        points = [(*self.cell_center(ix, iy), level) for level, ix, iy in nodes]
        points = self._string_pull(points)
        return self._center_on_doors(points)

    def _walkable_line(self, a, b):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        for i in range(int(length / (GRID / 2)) + 1):
            t = i * (GRID / 2) / max(length, 1e-6)
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            ix, iy = self.cell_of(x, y)
            if not self.is_free(a[2], ix, iy):
                return False
        return True

    def _string_pull(self, points):
        """Remove pontos intermediários quando a linha reta entre vizinhos é caminhável (mesmo andar)."""
        out = [points[0]]
        anchor = 0
        for i in range(1, len(points)):
            same_level = points[i][2] == points[anchor][2]
            if i + 1 < len(points) and same_level and points[i + 1][2] == points[anchor][2] \
                    and self._walkable_line(points[anchor], points[i + 1]):
                continue
            out.append(points[i])
            anchor = i
        return out

    def _center_on_doors(self, points):
        """Faz o caminho cruzar cada porta pelo centro, perpendicular ao vão."""
        path_points = []
        for index, point in enumerate(points):
            path_points.append(point)
            if index + 1 >= len(points) or points[index + 1][2] != point[2]:
                continue
            nxt = points[index + 1]
            for op in layout.doors():
                if op.level != point[2]:
                    continue
                crossing = _crossing(point, nxt, op)
                if crossing is not None:
                    path_points.extend(crossing)
        return path_points


def layout_floor(x, y, level):
    return any(room.rect.contains(x, y) for room in layout.rooms_on_level(level))


def _crossing(a, b, op):
    """Pontos (antes, meio, depois) da porta `op` se o segmento a-b a cruza; senão None."""
    mid_x, mid_y = op.mid
    if op.axis == "y":
        side_a, side_b = a[0] - op.pos, b[0] - op.pos
        cross_at = a[1] + (b[1] - a[1]) * (op.pos - a[0]) / (b[0] - a[0]) if b[0] != a[0] else None
        if side_a * side_b >= 0 or not (op.a - 0.2 <= cross_at <= op.b + 0.2):
            return None
        sign = 1 if side_b > 0 else -1
        return [(op.pos - sign * 0.6, mid_y, a[2]), (op.pos, mid_y, a[2]), (op.pos + sign * 0.6, mid_y, a[2])]
    side_a, side_b = a[1] - op.pos, b[1] - op.pos
    cross_at = a[0] + (b[0] - a[0]) * (op.pos - a[1]) / (b[1] - a[1]) if b[1] != a[1] else None
    if side_a * side_b >= 0 or not (op.a - 0.2 <= cross_at <= op.b + 0.2):
        return None
    sign = 1 if side_b > 0 else -1
    return [(mid_x, op.pos - sign * 0.6, a[2]), (mid_x, op.pos, a[2]), (mid_x, op.pos + sign * 0.6, a[2])]


# --------------------------------------------------------------------------
# O robô
# --------------------------------------------------------------------------
class Bot:
    """Joga pelo InputState, como uma pessoa: anda, vira, abre portas, mira e aperta [E]."""

    def __init__(self, game, nav, skip_cutscenes=False, run=False):
        self.game = game
        self.nav = nav
        self.inp = InputState()
        self.skip_cutscenes = skip_cutscenes
        self.run = run
        self.path = []
        self.door_wait = 0.0
        self.log = []
        self.stuck_clock = 0.0
        self.last_probe = (game.player.x, game.player.y, game.clock)
        self.detour = 0.0
        self.stuck = False
        self.goals_failed = []

    # ---- controle de baixo nível ----
    def tick(self):
        game = self.game
        game.tick(DT, self.inp)
        self.inp.clear_edges()
        self.inp.move_x = self.inp.move_y = 0.0
        self.inp.run = False

    def turn_toward(self, yaw, pitch=None, rate=0.35):
        player = self.game.player
        error = math.remainder(yaw - player.yaw, math.tau)
        self.inp.look_dx = -max(-rate, min(rate, error))
        if pitch is not None:
            self.inp.look_dy = max(-rate, min(rate, pitch - player.pitch))
        return abs(error) < 0.03 and (pitch is None or abs(pitch - player.pitch) < 0.03)

    def face_point(self, target):
        px, py, pz = self.game.player.eye_pos
        dx, dy, dz = target[0] - px, target[1] - py, target[2] - pz
        return self.turn_toward(math.atan2(-dx, dy), math.atan2(dz, math.hypot(dx, dy)))

    def press(self, **edges):
        for name, value in edges.items():
            setattr(self.inp, name, value)

    # ---- cutscene, menus, leitor ----
    def handle_meta_phase(self):
        """True se a fase atual não é de jogo e o robô já agiu."""
        game = self.game
        phase = game.phase
        if phase == "title":
            self.press(confirm=True)
        elif phase == "cutscene":
            if self.skip_cutscenes:
                self.press(skip=True)
        elif phase == "reading":
            self.reading_clock = getattr(self, "reading_clock", 0.0) + DT
            if self.reading_clock > 0.6:
                self.press(interact=True)
                self.reading_clock = 0.0
        elif phase == "dead":
            self.press(confirm=True)
            self.path = []
        elif phase == "paused":
            self.press(confirm=True)
        elif phase == "credits":
            return True
        else:
            return False
        self.tick()
        return True

    # ---- movimento ----
    def plan(self, goal):
        player = self.game.player
        self.nav.refresh_leaves()
        self.path = self.nav.path((player.x, player.y, player.level), goal) or []
        self.last_probe = (player.x, player.y, self.game.clock)
        return bool(self.path)

    def follow_path(self, hurry=False):
        """Um passo em direção ao próximo ponto. Devolve True quando o caminho acabou."""
        player = self.game.player
        while self.path and math.hypot(self.path[0][0] - player.x, self.path[0][1] - player.y) < 0.28:
            self.path.pop(0)
        if not self.path:
            return True
        if self._door_in_the_way():
            return False
        target = self.path[0]
        aimed = self.turn_toward(math.atan2(-(target[0] - player.x), target[1] - player.y))
        if self.detour > 0:
            self.detour -= DT
            self.inp.move_x = 1.0
        if aimed or abs(math.remainder(math.atan2(-(target[0] - player.x), target[1] - player.y) - player.yaw, math.tau)) < 0.6:
            self.inp.move_y = 1.0
            self.inp.run = hurry and player.stamina > 0.3
        self._watch_progress()
        return False

    def _watch_progress(self):
        player = self.game.player
        x0, y0, t0 = self.last_probe
        if self.game.clock - t0 < 3.0 or self.game.phase != "play":
            return
        moved = math.hypot(player.x - x0, player.y - y0)
        self.last_probe = (player.x, player.y, self.game.clock)
        if moved < 0.3 and self.game.phase == "play":
            self.detour = 0.6
            self.stuck = True
            self.log.append(f"t={self.game.clock:.0f}s preso perto de ({player.x:.1f},{player.y:.1f}); tentando desviar")

    def _door_in_the_way(self):
        """Se há porta fechada logo à frente no caminho, para, mira e abre. True enquanto trata a porta."""
        game, player = self.game, self.game.player
        for door_id, door in game.doors.doors.items():
            if door.level != player.level or game.doors.openness(door_id) > 0.85 or game.doors.is_locked(door_id):
                continue
            center = game.doors.center(door_id)
            if math.hypot(center[0] - player.x, center[1] - player.y) > 1.6 or not self._path_crosses(door_id):
                continue
            if game.doors.get(door_id).target > 0.5:            # já abrindo: espera terminar
                return True
            if self.face_point(center):
                self.press(interact=True)
            return True
        return False

    def _path_crosses(self, door_id):
        op = layout.OPENINGS[door_id]
        mid_x, mid_y = op.mid
        return any(math.hypot(p[0] - mid_x, p[1] - mid_y) < 0.7 for p in self.path[:4])

    # ---- objetivos ----
    def standing_spot(self, target):
        """Célula livre a ≤1,3 m do alvo, com visada livre até ele; a mais próxima do robô."""
        game = self.game
        tx, ty, tz = target
        level = layout.level_of_z(tz)
        z = layout.LEVEL_Z[level]
        best = None
        ix0, iy0 = self.nav.cell_of(tx, ty)
        span = int(1.6 / GRID)
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                if not self.nav.is_free(level, ix0 + dx, iy0 + dy):
                    continue
                x, y = self.nav.cell_center(ix0 + dx, iy0 + dy)
                dist = math.hypot(x - tx, y - ty)
                eye = (x, y, z + C.PLAYER_EYE_STAND)
                if 0.5 <= dist <= 1.8 and math.dist(eye, target) <= C.INTERACT_RANGE - 0.1 and self._sees(eye, target):
                    score = dist
                    if best is None or score < best[0]:
                        best = (score, x, y)
        return None if best is None else (best[1], best[2], level)

    def _sees(self, eye, target):
        """A mesma regra de visada do jogo (Interact.can_see)."""
        return self.game.interact.can_see(eye, target)

    def go_and_use(self, target, done, label):
        """Anda até perto de `target` (x, y, z), mira e aperta [E] até `done()` ficar verdadeiro."""
        game = self.game
        spot = self.standing_spot(target)
        if spot is None:
            self.log.append(f"{label}: nenhum ponto de mira livre")
            return False
        deadline = game.clock + GOAL_SECONDS
        self.plan(spot)
        aim_ticks = 0
        while game.clock < deadline and not done():
            if self.handle_meta_phase():
                if game.phase == "credits":
                    return done()
                continue
            if self.stuck:
                self.stuck = False
                self.plan(spot)
            if self.path and not self.follow_path(hurry=self.run):
                self.tick()
                continue
            if self.face_point(target):
                aim_ticks += 1
                if aim_ticks > 3:
                    self.press(interact=True)
                    aim_ticks = 0
            self.tick()
            if not self.path and game.interact.current is None and aim_ticks == 0 and self._far_from(spot):
                self.plan(spot)
        return done()

    def _far_from(self, spot):
        player = self.game.player
        return math.hypot(player.x - spot[0], player.y - spot[1]) > 0.5


def item_position(game, ref):
    for target in game.interact.targets:
        if target.ref == ref and target.kind in ("item", "note"):
            return game.interact.position(target)
    raise KeyError(ref)


def path_length(bot, ref):
    player = bot.game.player
    target = item_position(bot.game, ref)
    spot = bot.standing_spot(target)
    if spot is None:
        return math.inf
    path = bot.nav.path((player.x, player.y, player.level), spot)
    if not path:
        return math.inf
    pts = [(player.x, player.y)] + [(p[0], p[1]) for p in path]
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])) + (12 if player.level != path[-1][2] else 0)


# --------------------------------------------------------------------------
# Partidas
# --------------------------------------------------------------------------
def collect_item(bot, ref, label=None):
    game = bot.game
    target = item_position(game, ref)
    ok = bot.go_and_use(target, lambda: ref in game.state.collected or game.phase == "reading"
                        and game.reader_note == ref, label or ref)
    if game.phase == "reading":
        for _ in range(int(1.0 / DT)):
            bot.handle_meta_phase()
    if ref.startswith("NOTE"):
        ok = ref in game.state.notes_read
    if not ok:
        bot.goals_failed.append(ref)
    return ok


def after_pickup(bot, ref):
    game = bot.game
    if ref == "FLASHLIGHT":
        bot.press(flashlight=True)
        bot.tick()
        assert game.state.flashlight_on, "não conseguiu ligar a lanterna"
    while game.phase == "cutscene":
        bot.handle_meta_phase()
        if not bot.skip_cutscenes:
            bot.tick()


def play_story(game, skip_cutscenes, notes=2):
    """Título -> lanterna -> coleta -> garagem -> carro -> ending. Devolve o Bot."""
    nav = NavGrid(game)
    bot = Bot(game, nav, skip_cutscenes=skip_cutscenes)
    game.skip_intro = False
    while game.phase in ("title", "cutscene"):
        bot.handle_meta_phase()
    assert game.phase == "play", f"a abertura não terminou: {game.phase}"
    print(f"  jogo começou em {game.clock:.1f}s; objetivo: {game.state.objective}", flush=True)
    collect_item(bot, "FLASHLIGHT")
    after_pickup(bot, "FLASHLIGHT")
    wanted = ["KEY", "MAP"]
    batteries = ["BATTERY_1", "BATTERY_2", "BATTERY_3", "BATTERY_4"]
    read = ["NOTE_1", "NOTE_4", "NOTE_5"][:notes]
    remaining = wanted + read + batteries
    picked_batteries = 0
    while remaining and (picked_batteries < 3 or any(r in wanted + read for r in remaining)):
        ref = min(remaining, key=lambda r: path_length(bot, r))
        remaining.remove(ref)
        if ref.startswith("BATTERY") and picked_batteries >= 3:
            continue
        ok = collect_item(bot, ref)
        after_pickup(bot, ref)
        picked_batteries += int(ok and ref.startswith("BATTERY"))
        print(f"  {ref:10s} {'ok' if ok else 'FALHOU'}  t={game.clock:6.1f}s  objetivo: {game.state.objective}", flush=True)
    assert game.state.collect_complete(), f"coleta incompleta: {game.state.missing_labels()}"
    bot.nav.refresh_locks()
    unlock_garage(bot)
    enter_car(bot)
    return bot


def unlock_garage(bot):
    game = bot.game
    door = game.doors.center("garage_door")
    ok = bot.go_and_use(door, lambda: "garage" in game.state.unlocked, "garage_door")
    assert ok, "não destrancou a porta da garagem"
    while game.phase == "cutscene":
        bot.handle_meta_phase()
    assert game.phase == "play", game.phase
    bot.nav.refresh_locks()
    print(f"  garagem destrancada em t={game.clock:.1f}s; objetivo: {game.state.objective}", flush=True)


def enter_car(bot):
    game = bot.game
    car = next(t for t in game.interact.targets if t.kind == "car")
    target = game.interact.position(car)
    bot.go_and_use(target, lambda: game.phase in ("cutscene", "credits"), "carro")
    assert game.phase in ("cutscene", "credits"), f"não entrou no carro: fase {game.phase}"
    while game.phase != "credits":
        bot.handle_meta_phase()
        if game.phase == "cutscene" and not bot.skip_cutscenes:
            bot.tick()
        if game.clock > 1e5:
            break
    print(f"  final alcançado em t={game.clock:.1f}s", flush=True)


def play_hunt(game, minutes, skip_cutscenes=True):
    """Entidade ligada: o robô joga (e morre, e tenta de novo) por `minutes` minutos simulados."""
    nav = NavGrid(game)
    bot = Bot(game, nav, skip_cutscenes=skip_cutscenes, run=True)
    start_clock = game.clock
    ticks = 0
    limit = minutes * 60.0
    started = time.time()
    while game.clock - start_clock < limit and game.phase != "credits":
        ticks += 1
        if ticks > limit / DT * 4:
            break
        if bot.handle_meta_phase():
            continue
        state = game.state
        if not state.has_flashlight:
            collect_item(bot, "FLASHLIGHT")
            after_pickup(bot, "FLASHLIGHT")
        elif not state.has_key:
            collect_item(bot, "KEY")
        elif not state.has_map:
            collect_item(bot, "MAP")
        elif state.batteries_found < 3:
            ref = min((r for r in ("BATTERY_1", "BATTERY_2", "BATTERY_3", "BATTERY_4") if r not in state.collected),
                      key=lambda r: path_length(bot, r))
            collect_item(bot, ref)
        else:
            bot.tick()
    print(f"  caçada: {game.clock - start_clock:.0f}s simulados em {time.time() - started:.1f}s reais", flush=True)
    return bot


# --------------------------------------------------------------------------
# Cena, resumo e main
# --------------------------------------------------------------------------
def build_scene(stages, rebuild):
    if rebuild or not os.path.exists(OUT_BLEND):
        os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
        failures = build_module.run(stages, OUT_BLEND)
        for name, error in failures:
            print(f"  aviso: etapa '{name}' falhou no build: {error}")
    bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
    return bpy.context.scene


def summarize(title, game, bot, wall_seconds):
    state = game.state
    print(f"--- {title}")
    print(f"  tempo simulado : {game.clock:.1f} s   (tempo real {wall_seconds:.1f} s, {game.clock / max(wall_seconds, 1e-6):.0f}x)")
    print(f"  itens          : lanterna={state.has_flashlight} chave={state.has_key} mapa={state.has_map} "
          f"pilhas encontradas={state.batteries_found} (reserva {state.spare_batteries}) notas lidas={len(state.notes_read)}")
    print(f"  ruído máximo   : {game.peak_noise:.2f}   eventos de ruído do jogador: "
          f"{sum(1 for e in game.noise_log if e[0] == 'player')}   mortes: {state.deaths}")
    seen = Counter(game.cutscene_history)
    print(f"  cutscenes vistas: {', '.join(f'{name} x{count}' if count > 1 else name for name, count in seen.items()) or '-'}")
    print(f"  colisão        : {game.collision.kind}   entidade: {'ligada' if game.entity.enabled else 'desligada'}   "
          f"cutscenes: {'reais' if game.cutscenes is not None else 'ausentes'}")
    if game.interact.missing_from_scene:
        print(f"  ausentes na cena (alvos virtuais): {', '.join(game.interact.missing_from_scene[:12])}"
              f"{'...' if len(game.interact.missing_from_scene) > 12 else ''}")
    if hasattr(game.audio, "played"):
        print(f"  sons pedidos   : {len(game.audio.played)} (últimos: {', '.join(game.audio.played_names()[-6:])})")
    for line in bot.log[:6]:
        print("  robô:", line)
    if bot.goals_failed:
        print("  objetivos que falharam:", ", ".join(bot.goals_failed))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stages", default=",".join(build_module.STAGES))
    parser.add_argument("--rebuild", action="store_true", help="reconstrói o .blend mesmo que já exista")
    parser.add_argument("--blend", help="usa este .blend em vez de construir")
    parser.add_argument("--minutes", type=float, default=5.0, help="duração da fase com a entidade ligada")
    parser.add_argument("--skip-cutscenes", action="store_true", help="o robô pula as cutscenes (mais rápido)")
    parser.add_argument("--no-hunt", action="store_true", help="não roda a fase com a entidade")
    parser.add_argument("--audio", action="store_true", help="usa o AudioEngine real (sem dispositivo vira no-op)")
    args = parser.parse_args(argv)

    global OUT_BLEND
    if args.blend:
        OUT_BLEND = args.blend
    started = time.time()
    scene = build_scene(args.stages.split(","), args.rebuild and not args.blend)
    print(f"cena pronta em {time.time() - started:.1f}s: {len(scene.objects)} objetos", flush=True)

    print("== Fase 1: história, entidade desativada", flush=True)
    game = Game(scene, audio=args.audio, entity=False, cutscenes=True)
    t0 = time.time()
    bot = play_story(game, args.skip_cutscenes)
    summarize("história completa", game, bot, time.time() - t0)
    assert game.phase == "credits" and state_flag_ending(game), "a história não chegou ao ending"
    game.leave_scene()
    game.shutdown()

    hunt_ok = True
    if not args.no_hunt and can_hunt():
        print(f"== Fase 2: caçada, entidade ligada, {args.minutes:g} min simulados", flush=True)
        scene = build_scene(args.stages.split(","), False)
        hunt = Game(scene, audio=args.audio, entity=True, cutscenes=True)
        if not hunt.entity.enabled:
            print("  entidade indisponível (rig ou cérebro falharam): fase pulada")
            hunt_ok = False
        else:
            t0 = time.time()
            bot = play_hunt(hunt, args.minutes, skip_cutscenes=True)
            summarize("caçada", hunt, bot, time.time() - t0)
    elif not args.no_hunt:
        print("== Fase 2 pulada: módulo `ai.brain` ainda não existe")
    print("sim_playthrough OK" if hunt_ok else "sim_playthrough OK (sem a fase da entidade)")
    return 0


def state_flag_ending(game):
    from sem_alvorada.engine.state import FLAG_ENDING
    return FLAG_ENDING in game.state.flags


def can_hunt():
    try:
        import importlib
        importlib.import_module("sem_alvorada.ai.brain")
        importlib.import_module("sem_alvorada.entity.rig")
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    sys.exit(main())
