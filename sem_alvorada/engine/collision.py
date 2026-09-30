"""Colisão do jogador (e visada da IA): malhas `sa_col` em BVH ou, sem elas, só a planta.

As duas classes têm a mesma interface, então quem usa não sabe qual recebeu:

    ground(x, y, z)                    altura do piso sob o ponto (None: sem piso)
    push_out(x, y, z, radius, height)  deslocamento (dx, dy) que tira um cilindro das paredes
    headroom(x, y, z, height)          cabe em pé neste ponto?
    line_clear(a, b)                   linha de visada sem geometria estática no caminho

O jogador é um cilindro vertical. Paredes e móveis bloqueiam o que está acima de
`z + STEP`; o que for mais baixo vira degrau e o piso sobe até ali (escada). Quedas maiores
que MAX_DROP contam como parede: é um corrimão invisível que impede cair no vão da escada.
"""
import math

import bpy  # noqa: F401 - no bpy via pip, `mathutils` só existe depois deste import
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .. import conventions as C
from .. import layout

STEP = C.PLAYER_STEP_HEIGHT
MAX_DROP = 0.55
MAX_SUBSTEP = 0.10      # metros por sub-passo: parede fina (0,15 m) não pode ser atravessada num quadro
DOWN = Vector((0.0, 0.0, -1.0))
UP = Vector((0.0, 0.0, 1.0))

# O portão da garagem fica fechado durante todo o jogo; a malha dele pode não ter `sa_col`.
GARAGE_ROLLUP = layout.OPENINGS["garage_rollup"]
_ROLLUP_RECT = (GARAGE_ROLLUP.a, -0.15, GARAGE_ROLLUP.b, 0.15)


# --------------------------------------------------------------------------
# Geometria 2D
# --------------------------------------------------------------------------
def _push_from_rect(x, y, radius, rect):
    """Deslocamento que afasta um círculo de um retângulo (0, 0 se não há contato)."""
    x0, y0, x1, y1 = rect
    cx = min(max(x, x0), x1)
    cy = min(max(y, y0), y1)
    dx, dy = x - cx, y - cy
    dist_sq = dx * dx + dy * dy
    if dist_sq >= radius * radius:
        return 0.0, 0.0
    if dist_sq > 1e-12:
        dist = math.sqrt(dist_sq)
        return dx / dist * (radius - dist), dy / dist * (radius - dist)
    # Centro dentro do retângulo: sai pelo lado mais próximo.
    exits = ((x - x0 + radius, -1.0, 0.0), (x1 - x + radius, 1.0, 0.0),
             (y - y0 + radius, 0.0, -1.0), (y1 - y + radius, 0.0, 1.0))
    depth, nx, ny = min(exits)
    return nx * depth, ny * depth


def closest_on_segment(px, py, x0, y0, x1, y1):
    sx, sy = x1 - x0, y1 - y0
    length_sq = sx * sx + sy * sy
    t = 0.0 if length_sq < 1e-12 else max(0.0, min(1.0, ((px - x0) * sx + (py - y0) * sy) / length_sq))
    return x0 + sx * t, y0 + sy * t


def push_from_segments(x, y, radius, segments):
    """Afasta o círculo de segmentos finos (folhas de porta). Cada segmento: (x0, y0, x1, y1, meia_espessura)."""
    px = py = 0.0
    for x0, y0, x1, y1, half in segments:
        cx, cy = closest_on_segment(x, y, x0, y0, x1, y1)
        dx, dy = x - cx, y - cy
        dist = math.hypot(dx, dy)
        reach = radius + half
        if dist >= reach:
            continue
        if dist < 1e-6:
            dx, dy = -(y1 - y0), (x1 - x0)
            dist = math.hypot(dx, dy) or 1.0
        px += dx / dist * (reach - dist)
        py += dy / dist * (reach - dist)
    return px, py


def segment_crosses(ax, ay, bx, by, x0, y0, x1, y1):
    """Os segmentos AB e (x0,y0)-(x1,y1) se cruzam?"""
    def side(px, py, qx, qy, rx, ry):
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)
    d1 = side(ax, ay, bx, by, x0, y0)
    d2 = side(ax, ay, bx, by, x1, y1)
    d3 = side(x0, y0, x1, y1, ax, ay)
    d4 = side(x0, y0, x1, y1, bx, by)
    return d1 * d2 < 0 and d3 * d4 < 0


def _segment_rect_entry(ax, ay, bx, by, rect):
    """Parâmetro t (0..1) onde o segmento AB entra no retângulo, ou None (Liang-Barsky)."""
    x0, y0, x1, y1 = rect
    t_in, t_out = 0.0, 1.0
    for delta, low, high, start in ((bx - ax, x0, x1, ax), (by - ay, y0, y1, ay)):
        if abs(delta) < 1e-12:
            if start < low or start > high:
                return None
            continue
        t_a, t_b = (low - start) / delta, (high - start) / delta
        if t_a > t_b:
            t_a, t_b = t_b, t_a
        t_in, t_out = max(t_in, t_a), min(t_out, t_b)
        if t_in > t_out:
            return None
    return t_in


# --------------------------------------------------------------------------
# Só a planta
# --------------------------------------------------------------------------
class LayoutCollision:
    """Colisão derivada de `layout`: paredes 2D por andar, escada e pisos."""
    kind = "layout"

    def __init__(self):
        self._walls = {lvl: [r.as_tuple() for r in layout.solid_rects(lvl)] for lvl in (0, 1)}
        self._pieces = {lvl: [(p.rect2d().as_tuple(), p.z0, p.z1) for p in layout.wall_pieces(lvl)]
                        for lvl in (0, 1)}

    def covers(self, x, y, z):
        """(x, y) está sobre algum piso da planta neste andar (ou na escada)?"""
        if layout.stairs_height(x, y) is not None:
            return True
        level = layout.level_of_z(z)
        return any(room.rect.contains(x, y) for room in layout.rooms_on_level(level))

    def ground(self, x, y, z, step=STEP):
        stair = layout.stairs_height(x, y)
        if stair is not None:
            return stair
        if self.covers(x, y, z):
            return layout.LEVEL_Z[layout.level_of_z(z)]
        return None

    def push_out(self, x, y, z, radius, height):
        px = py = 0.0
        rects = list(self._walls[layout.level_of_z(z)])
        if layout.level_of_z(z) == 0:
            rects.append(_ROLLUP_RECT)
        for rect in rects:
            if rect[0] - radius > x or x > rect[2] + radius or rect[1] - radius > y or y > rect[3] + radius:
                continue
            dx, dy = _push_from_rect(x, y, radius, rect)
            px += dx
            py += dy
        return px, py

    def headroom(self, x, y, z, height):
        return True

    def ray_distance(self, origin, direction, max_distance):
        """Distância até a primeira parede na direção dada (max_distance se nada no caminho)."""
        end = tuple(o + d * max_distance for o, d in zip(origin, direction))
        nearest = max_distance
        for rect, z0, z1 in self._pieces[layout.level_of_z(origin[2])]:
            t = _segment_rect_entry(origin[0], origin[1], end[0], end[1], rect)
            if t is not None and z0 - 0.02 <= origin[2] + (end[2] - origin[2]) * t <= z1 + 0.02:
                nearest = min(nearest, t * max_distance)
        return nearest

    def line_clear(self, a, b, through_target_solids=False):
        level_a, level_b = layout.level_of_z(a[2]), layout.level_of_z(b[2])
        if level_a != level_b:
            hole = layout.STAIRS.hole.inflate(0.3)
            return hole.contains(a[0], a[1]) and hole.contains(b[0], b[1])
        for rect, z0, z1 in self._pieces[level_a]:
            t = _segment_rect_entry(a[0], a[1], b[0], b[1], rect)
            if t is None:
                continue
            z_at_hit = a[2] + (b[2] - a[2]) * t
            if z0 - 0.02 <= z_at_hit <= z1 + 0.02:
                return False
        return True


# --------------------------------------------------------------------------
# Malhas do .blend
# --------------------------------------------------------------------------
def world_matrix(obj):
    """Matriz de mundo calculada das propriedades e dos pais.

    `obj.matrix_world` fica desatualizado em objetos ocultos que nunca foram avaliados
    (os proxies COL_* são criados com hide_viewport), então não dá para confiar nele aqui.
    """
    local = obj.matrix_basis
    if obj.parent is None:
        return local.copy()
    return world_matrix(obj.parent) @ obj.matrix_parent_inverse @ local


def object_position(obj):
    return tuple(world_matrix(obj).translation)


def _proxy_box(obj, local_coords, matrix):
    """(mundo->local, mínimo local, máximo local) se `obj` é um proxy COL_* (caixa); senão None.

    Só proxies de móveis podem "envolver" um item; paredes e pisos nunca (uma malha grande de parede
    tem uma caixa que cobre a casa inteira)."""
    if not obj.name.startswith(C.N_COL):
        return None
    coords = local_coords.reshape(-1, 3)
    return np.linalg.inv(matrix), coords.min(axis=0), coords.max(axis=0)


def _world_triangles(scene):
    """Vértices, triângulos, dono de cada triângulo e caixa de cada objeto com sa_col (None se não é proxy)."""
    vertex_chunks, triangle_chunks, owner_chunks, boxes, offset = [], [], [], [], 0
    for obj in scene.objects:
        if obj.type != "MESH" or not obj.get(C.P_COL):
            continue
        mesh = obj.data
        mesh.calc_loop_triangles()
        vertex_count, triangle_count = len(mesh.vertices), len(mesh.loop_triangles)
        if not triangle_count:
            continue
        local = np.empty(vertex_count * 3, np.float64)
        mesh.vertices.foreach_get("co", local)
        indices = np.empty(triangle_count * 3, np.int64)
        mesh.loop_triangles.foreach_get("vertices", indices)
        matrix = np.array(world_matrix(obj), np.float64)
        world_vertices = local.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
        vertex_chunks.append(world_vertices)
        triangle_chunks.append(indices.reshape(-1, 3) + offset)
        owner_chunks.append(np.full(triangle_count, len(boxes), np.int64))
        boxes.append(_proxy_box(obj, local, matrix))
        offset += vertex_count
    if not vertex_chunks:
        return None
    return np.vstack(vertex_chunks), np.vstack(triangle_chunks), np.concatenate(owner_chunks), boxes


class SceneCollision:
    """BVH único com todos os objetos `sa_col` da cena (paredes, pisos, escada, proxies COL_*)."""
    kind = "bvh"

    def __init__(self, vertices, triangles, owners, boxes):
        self._tree = BVHTree.FromPolygons(vertices.tolist(), triangles.tolist(), all_triangles=True)
        self.triangle_count = len(triangles)
        self._owners = owners
        self._boxes = boxes
        self._layout = LayoutCollision()
        self.missing_floor_reports = 0

    @classmethod
    def from_scene(cls, scene):
        built = _world_triangles(scene)
        return None if built is None else cls(*built)

    def covers(self, x, y, z):
        return self._layout.covers(x, y, z)

    def ground(self, x, y, z, step=STEP):
        top = z + step + 0.05
        reach = step + 0.05 + MAX_DROP + 0.10
        origin = Vector((x, y, top))
        for _ in range(4):
            hit, normal, _face, distance = self._tree.ray_cast(origin, DOWN, reach)
            if hit is None:
                break
            if abs(normal.z) > 0.4:         # horizontal, qualquer que seja a orientação da face
                return hit.z
            origin = Vector((x, y, hit.z - 0.01))       # face inclinada demais para pisar: continua descendo
            reach -= distance + 0.01
            if reach <= 0:
                break
        return self._ground_from_plan(x, y, z, step)

    def _ground_from_plan(self, x, y, z, step):
        """Sem piso na malha: usa a planta dentro da casa, para não travar o jogo por um buraco.

        Só vale se o piso da planta está ao alcance dos pés; um vão fundo (escada) continua sendo um vão.
        """
        height = self._layout.ground(x, y, z, step)
        if height is None or height - z > step or z - height > MAX_DROP:
            return None
        if self.missing_floor_reports < 3:
            self.missing_floor_reports += 1
            print(f"[engine] aviso: sem piso sa_col em ({x:.2f}, {y:.2f}, z={z:.2f}); usando a planta", flush=True)
        return height

    def push_out(self, x, y, z, radius, height):
        px = py = 0.0
        for center_z in _sample_heights(z, height, radius):
            center = Vector((x + px, y + py, center_z))
            hit, normal, _face, _distance = self._tree.find_nearest(center, radius)
            if hit is None:
                continue
            dx, dy, dz = center.x - hit.x, center.y - hit.y, center.z - hit.z
            horizontal = math.hypot(dx, dy)
            needed = math.sqrt(max(radius * radius - dz * dz, 0.0))
            if horizontal < 1e-5:
                horizontal_normal = math.hypot(normal.x, normal.y)
                if horizontal_normal < 1e-5:
                    continue
                dx, dy = normal.x / horizontal_normal, normal.y / horizontal_normal
            else:
                dx, dy = dx / horizontal, dy / horizontal
            depth = needed - horizontal
            if depth > 0:
                px += dx * depth
                py += dy * depth
        if layout.level_of_z(z) == 0:
            rx, ry = _push_from_rect(x + px, y + py, radius, _ROLLUP_RECT)
            px, py = px + rx, py + ry
        return px, py

    def headroom(self, x, y, z, height):
        low = z + C.PLAYER_EYE_CROUCH + 0.1
        reach = z + height - low
        for ox, oy in ((0.0, 0.0), (0.2, 0.0), (-0.2, 0.0), (0.0, 0.2), (0.0, -0.2)):
            if self._tree.ray_cast(Vector((x + ox, y + oy, low)), UP, reach)[0] is not None:
                return False
        return True

    def ray_distance(self, origin, direction, max_distance):
        """Distância até a primeira superfície na direção dada (max_distance se nada no caminho)."""
        hit, _normal, _face, distance = self._tree.ray_cast(Vector(origin), Vector(direction), max_distance)
        return max_distance if hit is None else distance

    def line_clear(self, a, b, through_target_solids=False):
        """Visada livre de a até b. Com `through_target_solids`, sólidos que ENVOLVEM b não contam:
        um item dentro da gaveta ou da prateleira fica dentro do proxy do móvel e continua visível."""
        start, end = Vector(a), Vector(b)
        span = end - start
        length = span.length
        if length < 1e-6:
            return True
        direction = span / length
        enclosing = self._enclosing_objects(b) if through_target_solids else ()
        for _ in range(8):
            hit, _normal, face, distance = self._tree.ray_cast(start, direction, length)
            if hit is None:
                return True
            if int(self._owners[face]) not in enclosing:
                return False
            start, length = hit + direction * 0.002, length - distance - 0.002
        return False

    def _enclosing_objects(self, point, margin=0.05):
        """Índices dos proxies COL_* cuja caixa (no espaço local do próprio proxy) contém o ponto."""
        here = np.array([point[0], point[1], point[2], 1.0])
        enclosing = set()
        for index, box in enumerate(self._boxes):
            if box is None:
                continue
            to_local, low, high = box
            local = (to_local @ here)[:3]
            if np.all(local >= low - margin) and np.all(local <= high + margin):
                enclosing.add(index)
        return enclosing


def _sample_heights(z, height, radius):
    """Centros das esferas que representam o cilindro: cobrem de z+STEP até a cabeça sem lacunas."""
    low = z + STEP + radius
    high = max(z + height - radius, low)
    count = max(2, math.ceil((high - low) / (2 * radius * 0.75)) + 1)
    return [low + (high - low) * i / (count - 1) for i in range(count)]


def build_collision(scene):
    """SceneCollision se a cena tem meshes `sa_col`, senão LayoutCollision."""
    return SceneCollision.from_scene(scene) or LayoutCollision()


# --------------------------------------------------------------------------
# Movimento
# --------------------------------------------------------------------------
def _resolve(collision, x, y, z, radius, height, segments):
    for _ in range(4):
        px, py = collision.push_out(x, y, z, radius, height)
        sx, sy = push_from_segments(x + px, y + py, radius, segments)
        px, py = px + sx, py + sy
        if abs(px) + abs(py) < 1e-4:
            break
        x, y = x + px, y + py
    return x, y


EDGE_PROBES = ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0))
EDGE_MARGIN = 0.7        # fração do raio: a borda de um vão fica a esta distância do centro


def near_a_drop(collision, x, y, z, radius, step):
    """Há um vão fundo sob a borda do corpo? Mantém o jogador longe de escadas sem corrimão."""
    reach = radius * EDGE_MARGIN
    for dx, dy in EDGE_PROBES:
        ground = collision.ground(x + dx * reach, y + dy * reach, z, step)
        if ground is None and collision.covers(x + dx * reach, y + dy * reach, z):
            return True
        if ground is not None and z - ground > MAX_DROP:
            return True
    return False


def _try_step(collision, x, y, z, radius, height, segments, step):
    """Posição resolvida e altura do piso ali, ou None se o passo não é permitido."""
    nx, ny = _resolve(collision, x, y, z, radius, height, segments)
    ground = collision.ground(nx, ny, z, step)
    if ground is None or ground - z > step + 1e-3 or z - ground > MAX_DROP:
        return None
    if near_a_drop(collision, nx, ny, ground, radius, step):
        return None
    return nx, ny, ground


def move_and_slide(collision, x, y, z, dx, dy, radius, height, segments=(), step=STEP):
    """Anda (dx, dy) em sub-passos, deslizando nas paredes. Devolve (x, y, z)."""
    parts = max(1, math.ceil(math.hypot(dx, dy) / MAX_SUBSTEP))
    sx, sy = dx / parts, dy / parts
    for _ in range(parts):
        landed = (_try_step(collision, x + sx, y + sy, z, radius, height, segments, step)
                  or _try_step(collision, x + sx, y, z, radius, height, segments, step)
                  or _try_step(collision, x, y + sy, z, radius, height, segments, step))
        if landed is not None:
            x, y, z = landed
    return x, y, z
