"""Malha de navegação da entidade: grade de 0,25 m por andar, escada como conector, A* e suavização.

Três camadas de grade (todas com a mesma resolução):
- GROUND (térreo), UPPER (andar de cima) e STAIRS (a escada, uma camada própria).
A escada só se liga ao térreo pela base (y ~ 3.2) e ao andar de cima pelo topo (y ~ 7.4): o
corrimão fecha as laterais. No térreo a área da escada é bloqueada; no andar de cima o furo
da laje é bloqueado.

Uma célula é andável se o centro está dentro de algum cômodo do andar e a pelo menos
`CLEARANCE` metros de qualquer parede (`layout.solid_rects`) ou proxy de colisão `COL_*`.
Portas de 0,9 m passam com folga de 0,2 m. Fora da casa nada é andável: a entidade não sai.

As células que atravessam uma porta (não arco) são "portões": o A* cobra um custo por
atravessá-los fechados (ou os proíbe, se trancados) e o caminho suavizado sempre tem um
ponto exato no centro da porta, onde o cérebro para para abri-la.

Sem bpy: a malha nasce da planta (`from_layout`). `bake_from_scene` só é chamado pelo `ai.build`.
"""
import heapq
import json
import math
import sys
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .. import layout

CELL = 0.25
CLEARANCE = 0.20
GROUND, UPPER, STAIRS = 0, 1, 2
TEXT_NAME = "SA_NAV"
VERSION = 1
GATE_HALF_BAND = 0.2
STAIRS_SLOPE_COST = 1.2
WALL_BIAS = 1.5

_OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
_EXTENT_X, _EXTENT_Y = 18.5, 10.0


@dataclass(frozen=True)
class Waypoint:
    x: float
    y: float
    z: float
    layer: int
    door: Optional[str] = None      # id da porta cujo centro é este ponto (o cérebro abre ao chegar)


@dataclass
class Path:
    points: list
    cost: float


# --------------------------------------------------------------------------
# Rasterização
# --------------------------------------------------------------------------
def _grid_shape(cell):
    return int(math.ceil(_EXTENT_Y / cell)), int(math.ceil(_EXTENT_X / cell))


def _centers(cell):
    rows, cols = _grid_shape(cell)
    xs, ys = (np.arange(cols) + 0.5) * cell, (np.arange(rows) + 0.5) * cell
    return np.meshgrid(xs, ys)


def _rect_gap(grid_x, grid_y, rect):
    """Distância de cada centro de célula ao retângulo (0 dentro)."""
    dx = np.maximum(np.maximum(rect.x0 - grid_x, grid_x - rect.x1), 0.0)
    dy = np.maximum(np.maximum(rect.y0 - grid_y, grid_y - rect.y1), 0.0)
    return np.hypot(dx, dy)


def _polygon_gap(grid_x, grid_y, polygon):
    """Distância de cada centro de célula a um polígono convexo (0 dentro)."""
    points = np.array(polygon, dtype=float)
    count = len(points)
    inside = np.ones(grid_x.shape, bool)
    gap = np.full(grid_x.shape, np.inf)
    signs = _winding(points)
    for k in range(count):
        a, b = points[k], points[(k + 1) % count]
        edge = b - a
        length2 = float(edge @ edge) or 1e-12
        rel_x, rel_y = grid_x - a[0], grid_y - a[1]
        inside &= signs * (edge[0] * rel_y - edge[1] * rel_x) >= 0
        t = np.clip((rel_x * edge[0] + rel_y * edge[1]) / length2, 0.0, 1.0)
        gap = np.minimum(gap, np.hypot(rel_x - t * edge[0], rel_y - t * edge[1]))
    return np.where(inside, 0.0, gap)


def _winding(points):
    area = sum(points[k][0] * points[(k + 1) % len(points)][1] - points[(k + 1) % len(points)][0] * points[k][1]
               for k in range(len(points)))
    return 1.0 if area >= 0 else -1.0


def _clearance_steps(walk, max_steps=4):
    """Para cada célula andável, quantas erosões ela sobrevive (0 = encostada num bloqueio)."""
    steps = np.zeros(walk.shape, np.int8)
    current = walk.copy()
    rows, cols = walk.shape
    for step in range(1, max_steps + 1):
        padded = np.pad(current, 1, constant_values=False)
        eroded = current.copy()
        for dx, dy in _OFFSETS:
            eroded &= padded[1 + dy:1 + dy + rows, 1 + dx:1 + dx + cols]
        steps[eroded] = step
        current = eroded
    return steps


# --------------------------------------------------------------------------
# A malha
# --------------------------------------------------------------------------
class NavGrid:
    def __init__(self, walk, cell=CELL, clearance=CLEARANCE, obstacles=0):
        self.cell = cell
        self.clearance = clearance
        self.obstacles = obstacles
        self.walk = {layer: np.asarray(walk[layer], bool) for layer in (GROUND, UPPER, STAIRS)}
        self.rows, self.cols = self.walk[GROUND].shape
        self._clear = {layer: _clearance_steps(self.walk[layer]) for layer in self.walk}
        self.gates = {}
        self.door_mid = {}
        self._connectors = {}
        self._build_gates()
        self._build_connectors()

    # ---- construção ----------------------------------------------------
    @classmethod
    def from_layout(cls, obstacles=None, clearance=CLEARANCE, cell=CELL):
        """Malha só com a planta, mais `obstacles` opcionais: {andar: [polígono, ...]} (proxies COL_*)."""
        obstacles = obstacles or {}
        grid_x, grid_y = _centers(cell)
        walk = {}
        for level in (0, 1):
            walk[level] = _level_walkable(level, grid_x, grid_y, clearance, obstacles.get(level, []))
        st = layout.STAIRS
        in_stairs = (grid_x >= st.x0) & (grid_x <= st.x1) & (grid_y >= st.y0) & (grid_y <= st.y1)
        walk[GROUND] &= ~in_stairs
        walk[UPPER] &= ~((grid_x >= st.hole.x0) & (grid_x <= st.hole.x1) & (grid_y >= st.hole.y0) & (grid_y <= st.hole.y1))
        walk[STAIRS] = ((grid_x >= st.x0 + clearance) & (grid_x <= st.x1 - 0.15) & (grid_y >= st.y0) & (grid_y <= st.y1))
        count = sum(len(v) for v in obstacles.values())
        return cls(walk, cell, clearance, count)

    def _build_gates(self):
        for opening in layout.OPENINGS.values():
            if opening.kind != "door":
                continue
            layer = opening.level
            mid_x, mid_y = opening.mid
            self.door_mid[opening.id] = (mid_x, mid_y, layer)
            for iy in range(self.rows):
                for ix in range(self.cols):
                    x, y = self.center_of(ix, iy)
                    if opening.axis == "x":
                        hit = opening.a <= x <= opening.b and abs(y - opening.pos) <= GATE_HALF_BAND
                    else:
                        hit = opening.a <= y <= opening.b and abs(x - opening.pos) <= GATE_HALF_BAND
                    if hit and self.walk[layer][iy, ix]:
                        self.gates[(layer, ix, iy)] = opening.id

    def _build_connectors(self):
        rows = np.nonzero(self.walk[STAIRS].any(axis=1))[0]
        if len(rows) == 0:
            return
        bottom, top = int(rows.min()), int(rows.max())
        for ix in np.nonzero(self.walk[STAIRS][bottom])[0]:
            self._link((STAIRS, int(ix), bottom), GROUND, bottom - 1)
        for ix in np.nonzero(self.walk[STAIRS][top])[0]:
            self._link((STAIRS, int(ix), top), UPPER, top + 1)

    def _link(self, stair_node, other_layer, other_row):
        _, ix, _ = stair_node
        for jx in (ix - 1, ix, ix + 1):
            if 0 <= jx < self.cols and 0 <= other_row < self.rows and self.walk[other_layer][other_row, jx]:
                other = (other_layer, jx, other_row)
                cost = self.cell * (1.0 if jx == ix else math.sqrt(2))
                self._connectors.setdefault(stair_node, []).append((other, cost))
                self._connectors.setdefault(other, []).append((stair_node, cost))

    # ---- coordenadas ---------------------------------------------------------
    def cell_of(self, x, y):
        return int(x // self.cell), int(y // self.cell)

    def center_of(self, ix, iy):
        return (ix + 0.5) * self.cell, (iy + 0.5) * self.cell

    def in_bounds(self, ix, iy):
        return 0 <= ix < self.cols and 0 <= iy < self.rows

    def is_walkable(self, layer, ix, iy):
        return self.in_bounds(ix, iy) and bool(self.walk[layer][iy, ix])

    def point_ok(self, layer, x, y):
        """A posição (x, y) cai numa célula andável da camada?"""
        ix, iy = self.cell_of(x, y)
        return self.is_walkable(layer, ix, iy)

    @staticmethod
    def layer_at(x, y, z):
        """Camada de uma posição solta: escada se estiver sobre ela e entre os dois andares."""
        st = layout.STAIRS
        if st.contains(x, y) and 0.15 < z < st.z1 - 0.15:
            return STAIRS
        return layout.level_of_z(z)

    @staticmethod
    def height_at(layer, y):
        st = layout.STAIRS
        if layer == GROUND:
            return layout.LEVEL_Z[0]
        if layer == UPPER:
            return layout.LEVEL_Z[1]
        ramp = (min(max(y, st.y0), st.y1) - st.y0) / (st.y1 - st.y0)
        return st.z0 + ramp * (st.z1 - st.z0)

    def nearest_walkable(self, layer, x, y, radius=2.0):
        """Célula andável mais próxima de (x, y) dentro de `radius` metros, ou None."""
        ix, iy = self.cell_of(x, y)
        if self.is_walkable(layer, ix, iy):
            return ix, iy
        best, best_gap = None, radius ** 2
        reach = int(radius / self.cell) + 1
        for jy in range(iy - reach, iy + reach + 1):
            for jx in range(ix - reach, ix + reach + 1):
                if self.is_walkable(layer, jx, jy):
                    cx, cy = self.center_of(jx, jy)
                    gap = (cx - x) ** 2 + (cy - y) ** 2
                    if gap < best_gap:
                        best, best_gap = (jx, jy), gap
        return best

    def clearance_of(self, layer, ix, iy):
        """Folga aproximada (m) até o obstáculo mais próximo, em passos de uma célula."""
        return (int(self._clear[layer][iy, ix]) + 1) * self.cell

    def random_point_in_room(self, room_id, rng, min_clearance=0.45):
        """Ponto andável sorteado num cômodo, afastado de paredes e portas. (x, y, z, camada) ou None."""
        room = layout.ROOMS[room_id]
        layer = room.level
        rect = room.rect
        choices = []
        for iy in range(int(rect.y0 // self.cell), int(rect.y1 // self.cell) + 1):
            for ix in range(int(rect.x0 // self.cell), int(rect.x1 // self.cell) + 1):
                if (self.is_walkable(layer, ix, iy) and (layer, ix, iy) not in self.gates
                        and rect.contains(*self.center_of(ix, iy)) and self.clearance_of(layer, ix, iy) >= min_clearance):
                    choices.append((ix, iy))
        if not choices:
            return None
        ix, iy = rng.choice(choices)
        x, y = self.center_of(ix, iy)
        return x, y, self.height_at(layer, y), layer

    # ---- vizinhança e A* -------------------------------------------------------
    def _step_cost(self, layer, ix, iy, diagonal):
        base = self.cell * (math.sqrt(2) if diagonal else 1.0)
        closeness = max(0, 2 - int(self._clear[layer][iy, ix])) / 2.0
        scale = (1.0 + WALL_BIAS * closeness) * (STAIRS_SLOPE_COST if layer == STAIRS else 1.0)
        return base * scale

    def neighbours(self, node):
        layer, ix, iy = node
        grid = self.walk[layer]
        for dx, dy in _OFFSETS:
            jx, jy = ix + dx, iy + dy
            if not (0 <= jx < self.cols and 0 <= jy < self.rows) or not grid[jy, jx]:
                continue
            if dx and dy and not (grid[iy, jx] and grid[jy, ix]):
                continue        # não corta quina de parede
            yield (layer, jx, jy), self._step_cost(layer, jx, jy, bool(dx and dy))
        yield from self._connectors.get(node, ())

    def find_path(self, start, goal, door_cost: Optional[Callable] = None, start_layer=None, max_expansions=40000):
        """Caminho suavizado de `start` a `goal` (x, y, z) ou None se não houver.

        `door_cost(door_id)` devolve o custo extra (m) de atravessar aquela porta, ou None se
        ela for intransponível (trancada). `start_layer` evita adivinhar a camada pela altura.
        """
        first = self._snap(start, start_layer)
        last = self._snap(goal)
        if first is None or last is None:
            return None
        cells = self._astar(first, last, door_cost or (lambda _door: 0.0), max_expansions)
        if cells is None:
            return None
        points = self._smooth(cells, start, goal)
        return Path(points, sum(math.hypot(a.x - b.x, a.y - b.y) for a, b in zip(points, points[1:])))

    def _snap(self, position, layer=None):
        x, y, z = position
        layer = self.layer_at(x, y, z) if layer is None else layer
        for candidate in ((layer,) if layer != STAIRS else (STAIRS, GROUND, UPPER)):
            cell = self.nearest_walkable(candidate, x, y, radius=2.0)
            if cell is not None:
                return (candidate, *cell)
        return None

    def _astar(self, first, last, door_cost, max_expansions):
        goal_x, goal_y = last[1], last[2]

        def heuristic(node):
            dx, dy = abs(node[1] - goal_x), abs(node[2] - goal_y)
            return self.cell * (max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy))

        best = {first: 0.0}
        parent = {}
        queue = [(heuristic(first), 0.0, first)]
        door_extra = {}
        expansions = 0
        while queue:
            _, cost, node = heapq.heappop(queue)
            if node == last:
                return self._unwind(parent, node)
            if cost > best.get(node, math.inf):
                continue
            expansions += 1
            if expansions > max_expansions:
                return None
            for neighbour, step in self.neighbours(node):
                door = self.gates.get(neighbour)
                extra = 0.0
                if door is not None:
                    if door not in door_extra:
                        door_extra[door] = door_cost(door)
                    if door_extra[door] is None:
                        continue
                    extra = door_extra[door] / 2.0
                total = cost + step + extra
                if total < best.get(neighbour, math.inf):
                    best[neighbour] = total
                    parent[neighbour] = node
                    heapq.heappush(queue, (total + heuristic(neighbour), total, neighbour))
        return None

    @staticmethod
    def _unwind(parent, node):
        cells = [node]
        while node in parent:
            node = parent[node]
            cells.append(node)
        return cells[::-1]

    # ---- suavização --------------------------------------------------------
    def segment_clear(self, layer, a, b):
        """Todos os pontos amostrados entre a e b caem em células andáveis que não são portões?"""
        length = math.dist(a, b)
        steps = max(int(length / (self.cell / 3.0)), 1)
        for k in range(steps + 1):
            t = k / steps
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            ix, iy = self.cell_of(x, y)
            if not self.is_walkable(layer, ix, iy) or (layer, ix, iy) in self.gates:
                return False
        return True

    def _smooth(self, cells, start, goal):
        """Puxa o fio entre os pontos obrigatórios: início, fim, troca de camada e centro de cada porta."""
        anchors = self._anchors(cells)
        first_layer, last_layer = anchors[0][2], anchors[-1][2]
        anchors[0] = (start[0], start[1], first_layer, None)
        if self.point_ok(last_layer, goal[0], goal[1]):
            anchors[-1] = (goal[0], goal[1], last_layer, None)
        points = []
        i = 0
        while i < len(anchors):
            x, y, layer, door = anchors[i]
            points.append(Waypoint(x, y, self.height_at(layer, y), layer, door))
            j = i + 1
            if door is None and i < len(anchors) - 1:
                while (j + 1 < len(anchors) and anchors[j][3] is None and anchors[j + 1][3] is None
                       and anchors[j + 1][2] == layer and self.segment_clear(layer, (x, y), anchors[j + 1][:2])):
                    j += 1
            i = j
        return points

    def _anchors(self, cells):
        """Células -> pontos (x, y, camada, porta). Os portões de uma travessia viram um só, no centro da porta."""
        anchors = []
        for layer, ix, iy in cells:
            door = self.gates.get((layer, ix, iy))
            if door is None:
                anchors.append((*self.center_of(ix, iy), layer, None))
            elif not anchors or anchors[-1][3] != door:
                mid_x, mid_y, _ = self.door_mid[door]
                anchors.append((mid_x, mid_y, layer, door))
        return anchors

    # ---- serialização ------------------------------------------------------
    def to_json(self):
        layers = {str(layer): ["".join("1" if v else "0" for v in row) for row in self.walk[layer]]
                  for layer in (GROUND, UPPER, STAIRS)}
        return json.dumps({"version": VERSION, "cell": self.cell, "clearance": self.clearance,
                           "obstacles": self.obstacles, "rows": self.rows, "cols": self.cols, "layers": layers})

    @classmethod
    def from_json(cls, text):
        blob = json.loads(text)
        if blob.get("version") != VERSION:
            raise ValueError("versão de malha desconhecida")
        walk = {int(k): np.array([[c == "1" for c in row] for row in rows], bool) for k, rows in blob["layers"].items()}
        return cls(walk, blob["cell"], blob["clearance"], blob.get("obstacles", 0))

    # ---- diagnóstico -------------------------------------------------------
    def reachable_rooms(self, start=None):
        """Cômodos alcançáveis a partir de `start` ((x, y, z), padrão: início do jogador), ignorando trancas."""
        start = start or layout.PLAYER_START
        first = self._snap(start)
        seen, stack = {first}, [first]
        while stack:
            node = stack.pop()
            for neighbour, _ in self.neighbours(node):
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        rooms = set()
        for layer, ix, iy in seen:
            x, y = self.center_of(ix, iy)
            room = layout.room_at(x, y, self.height_at(layer, y))
            if room is not None:
                rooms.add(room.id)
        return rooms


def _level_walkable(level, grid_x, grid_y, clearance, polygons):
    inside = np.zeros(grid_x.shape, bool)
    for room in layout.rooms_on_level(level):
        r = room.rect
        inside |= (grid_x >= r.x0) & (grid_x <= r.x1) & (grid_y >= r.y0) & (grid_y <= r.y1)
    blocked = np.zeros(grid_x.shape, bool)
    for rect in layout.solid_rects(level):
        blocked |= _rect_gap(grid_x, grid_y, rect) < clearance
    for polygon in polygons:
        blocked |= _polygon_gap(grid_x, grid_y, polygon) < clearance
    return inside & ~blocked


# --------------------------------------------------------------------------
# Carregar e assar
# --------------------------------------------------------------------------
def from_layout():
    """Malha construída só da planta (testes, simulações, ou cena sem SA_NAV)."""
    return NavGrid.from_layout()


def load_from_scene(name=TEXT_NAME):
    """Lê o Text `SA_NAV` do .blend aberto. None se não existir ou se o bpy não estiver carregado."""
    bpy = sys.modules.get("bpy")
    if bpy is None:
        return None
    text = bpy.data.texts.get(name)
    if text is None:
        return None
    try:
        return NavGrid.from_json(text.as_string())
    except (ValueError, KeyError):
        return None


def load():
    """A malha do jogo: a assada na cena, ou a da planta."""
    return load_from_scene() or from_layout()


def collision_footprints(objects, min_height=0.3):
    """Pegadas 2D {andar: [polígono]} dos proxies COL_* (objetos bpy): casco convexo dos vértices em mundo."""
    footprints = {0: [], 1: []}
    for obj in objects:
        corners = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        if not corners:
            continue
        z_low, z_high = min(c.z for c in corners), max(c.z for c in corners)
        if z_high - z_low < min_height:
            continue
        hull = _convex_hull([(c.x, c.y) for c in corners])
        if len(hull) >= 3:
            footprints[layout.level_of_z(z_low + 0.05)].append(hull)
    return footprints


def _convex_hull(points):
    points = sorted(set((round(x, 4), round(y, 4)) for x, y in points))
    if len(points) <= 2:
        return points

    def half(sequence):
        chain = []
        for p in sequence:
            while len(chain) >= 2 and (chain[-1][0] - chain[-2][0]) * (p[1] - chain[-2][1]) \
                    - (chain[-1][1] - chain[-2][1]) * (p[0] - chain[-2][0]) <= 0:
                chain.pop()
            chain.append(p)
        return chain[:-1]

    return half(points) + half(points[::-1])


def bake(footprints, log=print):
    """Assa a malha com os proxies e garante que nenhum cômodo ficou isolado.

    Se a folga cheia desconectar algum cômodo (móvel apertando uma porta), tenta folgas menores
    (0,15, 0,10, 0,05 m). Devolve (NavGrid, folga usada).
    """
    every_room = set(layout.ROOMS)
    for clearance in (CLEARANCE, 0.15, 0.10, 0.05):
        grid = NavGrid.from_layout(footprints, clearance=clearance)
        missing = every_room - grid.reachable_rooms()
        if not missing:
            return grid, clearance
        log(f"folga {clearance:.2f} m isola {sorted(missing)}; tentando folga menor")
    log("aviso: usando a planta sem os proxies, eles isolavam cômodos")
    return NavGrid.from_layout(), 0.0
