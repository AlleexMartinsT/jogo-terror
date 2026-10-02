"""Carroceria do sedã: loft de seções transversais + booleanas (manifold3d). Saída: assets/models/carro_carroceria.npz

Por que offline: o corpo de um carro tem arcos de roda, frestas de porta, bolsões de farol e uma cabine
oca com colunas finas. Fazer isso com caixas empilhadas dá o aspecto de brinquedo; com booleanas sai chapa
de verdade (espessura nos arcos, frestas que pegam luz). O Blender do jogador não tem trimesh/manifold,
então o resultado é gravado num `.npz` que `craft.load_npz` lê.

A forma (seções, perfis, posição de portas e janelas) vem de `sem_alvorada.props.car_shape`, a mesma que o
construtor do carro usa para encaixar faróis e vidros; este script só faz o sólido e os cortes.

Materiais por face (`material_ids`): 0 tinta, 1 plástico preto (fundo, caixas de roda), 2 forro e painéis
internos, 3 carpete do assoalho, 4 borracha das molduras de vidro, 5 forro do teto.

    python tools/modelagem/carro_carroceria.py
"""
import os
import sys

import numpy as np
import trimesh
from shapely.geometry import Polygon

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sem_alvorada.props import car_shape as shape  # noqa: E402

PAINT, BLACK, TRIM, CARPET, RUBBER, HEADLINER = range(6)
OUTPUT = os.path.join(ROOT, "assets", "models", "carro_carroceria.npz")

CAVITY_FLOOR = 0.34
CAVITY_HALF_WIDTH = 0.82
CABIN_WALL = 0.028
CABIN_Y_RANGE = (-1.9, 1.2)


# --------------------------------------------------------------------------------------------
# Sólidos básicos
# --------------------------------------------------------------------------------------------
def loft_solid(rings):
    """Sólido fechado a partir de anéis (S, M, 3) de mesmo tamanho; as pontas são tampadas em leque."""
    stations, count, _ = rings.shape
    vertices = [rings.reshape(-1, 3)]
    faces = []
    for i in range(stations - 1):
        for j in range(count):
            k = (j + 1) % count
            a, b = i * count + j, i * count + k
            c, d = (i + 1) * count + k, (i + 1) * count + j
            faces += [(a, b, c), (a, c, d)]
    for ring_index in (0, stations - 1):
        centre_id = sum(len(v) for v in vertices)
        vertices.append(rings[ring_index].mean(axis=0)[None, :])
        for j in range(count):
            a, b = ring_index * count + j, ring_index * count + (j + 1) % count
            faces.append((centre_id, a, b))
    solid = trimesh.Trimesh(np.concatenate(vertices), np.array(faces), process=False)
    trimesh.repair.fix_normals(solid)
    if solid.volume < 0:
        solid.invert()
    return solid


def box(x0, x1, y0, y1, z0, z1):
    solid = trimesh.creation.box(extents=(x1 - x0, y1 - y0, z1 - z0))
    solid.apply_translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    return solid


def cylinder_x(radius, x0, x1, y, z, sections=72):
    """Cilindro com eixo em X entre x0 e x1, centrado em (y, z)."""
    solid = trimesh.creation.cylinder(radius=radius, height=abs(x1 - x0), sections=sections)
    solid.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (0, 1, 0)))
    solid.apply_translation(((x0 + x1) / 2, y, z))
    return solid


def prism_x(polygon_yz, x0=-1.5, x1=1.5):
    """Polígono (y, z) extrudado ao longo de X: recortes de silhueta lateral."""
    solid = trimesh.creation.extrude_polygon(Polygon(polygon_yz), height=x1 - x0)
    to_world = np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)
    solid.apply_transform(to_world)
    return solid


def union(parts):
    return trimesh.boolean.union(list(parts), engine="manifold")


def difference(base, cutters):
    return trimesh.boolean.difference([base, union(cutters)], engine="manifold")


def intersection(first, second):
    return trimesh.boolean.intersection([first, second], engine="manifold")


def mirrored_x(solid):
    other = solid.copy()
    other.vertices = other.vertices * np.array([-1.0, 1.0, 1.0])
    other.invert()
    return other


# --------------------------------------------------------------------------------------------
# Corpo inferior
# --------------------------------------------------------------------------------------------
def lower_body():
    return loft_solid(np.array([shape.full_section(y) for y in shape.stations()]))


def wheel_house_cutters():
    """Arco de roda em dois degraus: aro fino de chapa (3 cm) por fora e a caixa de roda, mais larga, por dentro."""
    cutters = []
    for sign in (1, -1):
        for y in (shape.WHEEL_Y, -shape.WHEEL_Y):
            lip = cylinder_x(shape.ARCH_RADIUS, 0.905, 1.3, y, shape.WHEEL_RADIUS)
            well = cylinder_x(shape.ARCH_RADIUS + 0.035, 0.52, 0.92, y, shape.WHEEL_RADIUS)
            cutters += [part if sign > 0 else mirrored_x(part) for part in (lip, well)]
    return cutters


def cavity_cutters():
    """Interior: o vão da cabine, mais estreito sobre as caixas das rodas traseiras (abaixo dos bancos)."""
    return [box(-CAVITY_HALF_WIDTH, CAVITY_HALF_WIDTH, -0.98, 0.96, CAVITY_FLOOR, 1.3),
            box(-0.50, 0.50, -1.50, -0.97, CAVITY_FLOOR, 1.3),
            box(-CAVITY_HALF_WIDTH, CAVITY_HALF_WIDTH, -1.50, -0.97, 0.80, 1.3)]


def in_cavity(points, slack=0.004):
    """True para pontos (N, 3) dentro do vão da cabine (com folga): classifica as faces internas."""
    inside = np.zeros(len(points), bool)
    for cutter in cavity_cutters():
        low, high = cutter.bounds
        inside |= np.all((points >= low - slack) & (points <= np.minimum(high, 1.25) + slack), axis=1)
    return inside


# --------------------------------------------------------------------------------------------
# Frestas (sulcos de 5 mm) varridas ao longo de caminhos sobre a chapa
# --------------------------------------------------------------------------------------------
def rounded_polyline(points, setback, steps=5):
    """Caminho 2D com os cantos internos arredondados (arco quadrático que começa a `setback` do vértice)."""
    points = [np.asarray(p, float) for p in points]
    out = [points[0]]
    for before, corner, after in zip(points, points[1:], points[2:]):
        to_before, to_after = before - corner, after - corner
        start = corner + to_before / np.linalg.norm(to_before) * min(setback, np.linalg.norm(to_before) * 0.45)
        end = corner + to_after / np.linalg.norm(to_after) * min(setback, np.linalg.norm(to_after) * 0.45)
        for t in np.linspace(0.0, 1.0, steps):
            out.append((1 - t) ** 2 * start + 2 * (1 - t) * t * corner + t ** 2 * end)
    out.append(points[-1])
    return np.array(out)


def resample(path, spacing=0.012):
    """Reamostra uma polilinha 2D em passos regulares."""
    lengths = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    samples = np.linspace(0.0, lengths[-1], max(2, int(lengths[-1] / spacing)))
    return np.column_stack([np.interp(samples, lengths, path[:, k]) for k in range(2)])


def sweep_groove(path, surface, outward, width=shape.GROOVE_WIDTH, depth=shape.GROOVE_DEPTH, reach=0.03):
    """Cortador em barra retangular ao longo de `path` (2D), colado à superfície.

    `surface(path)` devolve os pontos 3D sobre a chapa e `outward` é o vetor unitário que sai dela. O corte
    entra `depth` na chapa e sai `reach` para fora, então a fresta acompanha uma curvatura leve.
    """
    path = resample(path)
    base = surface(path)
    tangent2 = np.gradient(path, axis=0)
    tangent2 /= np.linalg.norm(tangent2, axis=1, keepdims=True)
    normal = np.asarray(outward, float)
    axes = [k for k in range(3) if abs(normal[k]) < 0.5]
    tangent = np.zeros((len(path), 3))
    tangent[:, axes[0]], tangent[:, axes[1]] = tangent2[:, 0], tangent2[:, 1]
    across = np.cross(normal[None, :], tangent)
    across /= np.linalg.norm(across, axis=1, keepdims=True)
    half = width / 2
    inner, outer = -depth * normal, reach * normal
    rings = np.stack([base + across * half + inner, base - across * half + inner,
                      base - across * half + outer, base + across * half + outer], axis=1)
    return loft_solid(rings)


def side_surface(sign):
    """Pontos 3D da lateral para um caminho em (y, z)."""
    return lambda p: np.column_stack([sign * shape.side_x(p[:, 0], p[:, 1]), p[:, 0], p[:, 1]])


def top_surface(path):
    """Pontos 3D do capô/porta-malas para um caminho em (x, y)."""
    return np.column_stack([path[:, 0], path[:, 1], shape.hood_surface_z(path[:, 0], path[:, 1])])


def door_groove_paths():
    """Caminhos (y, z) em U de cada porta: borda dianteira, soleira e borda traseira."""
    belt, bottom = shape.BELT_Z - 0.002, shape.DOOR_BOTTOM_Z
    paths = []
    for front, rear in (shape.FRONT_DOOR, shape.REAR_DOOR):
        paths.append(rounded_polyline([(front + 0.035, belt), (front - 0.012, bottom + 0.16), (front - 0.045, bottom),
                                       (rear + 0.045, bottom), (rear - 0.010, bottom + 0.16), (rear + 0.030, belt)], 0.09))
    return paths


def lid_groove_paths():
    """Caminhos (x, y) do capô e da tampa do porta-malas no lado +X (o lado -X é o espelho)."""
    hood_front, hood_rear = 2.185, shape.COWL_Y + 0.015
    trunk_front, trunk_rear = shape.REAR_GLASS_BASE_Y - 0.03, -2.115
    hood = rounded_polyline([(0.0, hood_front), (0.66, hood_front - 0.02), (0.745, hood_front - 0.12),
                             (0.745, hood_rear + 0.06), (0.70, hood_rear), (0.0, hood_rear)], 0.07)
    trunk = rounded_polyline([(0.0, trunk_front), (0.70, trunk_front), (0.75, trunk_front - 0.08),
                              (0.75, trunk_rear + 0.10), (0.70, trunk_rear), (0.0, trunk_rear)], 0.07)
    return [hood, trunk]


def groove_cutters():
    cutters = []
    for sign in (1, -1):
        for path in door_groove_paths():
            cutters.append(sweep_groove(path, side_surface(sign), (sign, 0.0, 0.0)))
        for path in lid_groove_paths():
            cutters.append(sweep_groove(path * np.array([sign, 1.0]), top_surface, (0.0, 0.0, 1.0)))
    return cutters


def pocket_cutters():
    """Bolsões de farol, grade, lanternas, placa e maçanetas."""
    cutters = []
    for sign in (1, -1):
        cutters.append(box(*sorted((sign * 0.43, sign * 0.90)), 2.165, 2.45, 0.53, 0.71))      # farol
        cutters.append(box(*sorted((sign * 0.46, sign * 0.95)), -2.45, -2.185, 0.745, 0.905))   # lanterna
        for handle_y in shape.HANDLE_Y:
            inner_x = float(shape.side_x(handle_y, 0.935)) - 0.034
            cutters.append(box(*sorted((sign * inner_x, sign * 1.1)), handle_y - 0.075, handle_y + 0.075, 0.915, 0.955))
    cutters.append(box(-0.39, 0.39, 2.19, 2.45, 0.545, 0.700))                                 # grade
    cutters.append(box(-0.20, 0.20, -2.45, -2.235, 0.66, 0.78))                                # placa
    return cutters


def classify_lower(mesh):
    """Material de cada face do corpo inferior pela posição e pela normal."""
    centres, normals = mesh.triangles_center, mesh.face_normals
    ids = np.full(len(centres), PAINT)
    ids[(centres[:, 2] < 0.27) & (normals[:, 2] < -0.6)] = BLACK
    for y in (shape.WHEEL_Y, -shape.WHEEL_Y):
        radial = np.hypot(centres[:, 1] - y, centres[:, 2] - shape.WHEEL_RADIUS)
        ax = np.abs(centres[:, 0])
        ids[(radial < shape.ARCH_RADIUS + 0.045) & (ax > 0.45) & (ax < 0.915)] = BLACK
    cavity = in_cavity(centres)
    ids[cavity] = TRIM
    ids[cavity & (centres[:, 2] < CAVITY_FLOOR + 0.05) & (normals[:, 2] > 0.7)] = CARPET
    return ids


# --------------------------------------------------------------------------------------------
# Cabine
# --------------------------------------------------------------------------------------------
def cabin_section(y, wall=0.0):
    """Anel (M, 3) da cabine na estação y; `wall` > 0 encolhe para dentro (miolo a escavar)."""
    taper = float(shape.cabin_taper(y))
    base = 0.88 if wall else 0.975
    sides = [(float(shape.cabin_half_width(z)) * taper - wall, z) for z in np.linspace(base, shape.ROOF_Z - 0.06, 7)]
    roof_edge = sides[-1][0]
    roof = [(roof_edge * (1 - u), shape.ROOF_Z - wall - 0.045 * (roof_edge * (1 - u) / 0.72) ** 2)
            for u in (0.0, 0.12, 0.3, 0.5, 0.7, 0.88, 1.0)]
    right = shape._round_path([(0.0, base)] + sides + roof, {len(sides): 0.09})
    ring = np.concatenate([right, right[-2:0:-1] * np.array([-1.0, 1.0])])
    return np.column_stack([ring[:, 0], np.full(len(ring), float(y)), ring[:, 1]])


def cabin_silhouette(shrink=0.0):
    """Polígono (y, z) da cabine em vista lateral: corta o loft nos planos do para-brisa e do vidro traseiro."""
    z_low, z_high = shape.BELT_Z - 0.06, shape.ROOF_Z + 0.05
    polygon = Polygon([(float(shape.a_pillar_y(z_low)), z_low), (float(shape.a_pillar_y(z_high)), z_high),
                       (float(shape.c_pillar_y(z_high)), z_high), (float(shape.c_pillar_y(z_low)), z_low)])
    return polygon.buffer(-shrink, join_style=2) if shrink else polygon


def window_cutter(corners, thickness=0.30):
    """Prisma que atravessa a chapa: o contorno do vidro extrudado para os dois lados da sua normal."""
    corners = np.asarray(corners, float)
    normal = np.cross(corners[1] - corners[0], corners[3] - corners[0])
    normal /= np.linalg.norm(normal)
    points = np.concatenate([corners + normal * thickness, corners - normal * thickness])
    faces = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
             (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    solid = trimesh.Trimesh(points, np.array(faces), process=False)
    trimesh.repair.fix_normals(solid)
    if solid.volume < 0:
        solid.invert()
    return solid


def cabin_shell():
    """Teto e colunas: casca de 2,8 cm com os vãos dos vidros recortados. Devolve (casca, sólido externo, sólido interno)."""
    ys = np.linspace(*CABIN_Y_RANGE, 44)
    outer = intersection(loft_solid(np.array([cabin_section(y) for y in ys])), _silhouette_prism(cabin_silhouette()))
    inner = intersection(loft_solid(np.array([cabin_section(y, CABIN_WALL) for y in ys])),
                         _silhouette_prism(cabin_silhouette(CABIN_WALL)))
    shell = trimesh.boolean.difference([outer, inner], engine="manifold")
    openings = [window_cutter(corners) for corners in shape.glass_polygons().values()]
    return trimesh.boolean.difference([shell, union(openings)], engine="manifold"), outer, inner


def _silhouette_prism(polygon):
    return prism_x(list(polygon.exterior.coords)[:-1])


def surface_distance(solid, points, samples=400_000):
    """Distância de cada ponto à superfície de `solid`, por vizinho mais próximo numa nuvem densa de amostras."""
    from scipy.spatial import cKDTree
    cloud, _ = trimesh.sample.sample_surface(solid, samples, seed=7)
    return cKDTree(cloud).query(points)[0]


def classify_cabin(mesh, outer, inner, tolerance=0.006):
    """Superfície externa = tinta; superfície interna = forro; paredes cortadas dos vãos de vidro = borracha."""
    centres = mesh.triangles_center
    ids = np.full(len(centres), RUBBER)
    ids[surface_distance(inner, centres) < tolerance] = HEADLINER
    ids[surface_distance(outer, centres) < tolerance] = PAINT
    return ids


# --------------------------------------------------------------------------------------------
def build():
    body = difference(lower_body(), wheel_house_cutters() + cavity_cutters() + groove_cutters() + pocket_cutters())
    cabin, outer, inner = cabin_shell()
    parts = [(body, classify_lower(body)), (cabin, classify_cabin(cabin, outer, inner))]
    vertices, faces, materials, offset = [], [], [], 0
    for mesh, ids in parts:
        vertices.append(mesh.vertices)
        faces.append(mesh.faces + offset)
        materials.append(ids)
        offset += len(mesh.vertices)
    return np.concatenate(vertices), np.concatenate(faces), np.concatenate(materials)


if __name__ == "__main__":
    verts, faces, material_ids = build()
    np.savez_compressed(OUTPUT, verts=verts.astype(np.float32), faces=faces.astype(np.int32),
                        material_ids=material_ids.astype(np.int8))
    print(f"{OUTPUT}: {len(verts)} vértices, {len(faces)} triângulos, {os.path.getsize(OUTPUT) / 1024:.0f} KB")
