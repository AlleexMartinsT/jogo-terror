"""Carroceria do sedã: loft de seções transversais + booleanas (manifold3d). Saída: assets/models/carro_carroceria.npz

Por que offline: o corpo de um carro tem arcos de roda, frestas de porta, bolsões de farol e uma cabine
oca com colunas finas. Fazer isso com caixas empilhadas dá o aspecto de brinquedo; fazer com booleanas
dá chapa de verdade (espessura nos arcos, frestas que pegam luz). O Blender do jogador não tem
trimesh/manifold, então o resultado é gravado em um `.npz` que `craft.load_npz` lê.

A forma (seções, perfis, posição de portas e janelas) vem de `sem_alvorada.props.car_shape`, a mesma que
o construtor do carro usa para encaixar faróis e vidros; este script só faz a geometria sólida e os cortes.

Materiais por face (`material_ids`): 0 tinta, 1 plástico preto (fundo, caixas de roda), 2 forro e painéis
internos, 3 carpete do assoalho, 4 borracha das molduras de vidro.

    python tools/modelagem/carro_carroceria.py
"""
import os
import sys

import numpy as np
import trimesh

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sem_alvorada.props import car_shape as shape  # noqa: E402

PAINT, BLACK, TRIM, CARPET, RUBBER = range(5)
OUTPUT = os.path.join(ROOT, "assets", "models", "carro_carroceria.npz")

CAVITY_FLOOR = 0.34
CAVITY_HALF_WIDTH = 0.82
CABIN_WALL = 0.028


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
    for ring_index, flip in ((0, True), (stations - 1, False)):
        centre = rings[ring_index].mean(axis=0)
        centre_id = sum(len(v) for v in vertices)
        vertices.append(centre[None, :])
        for j in range(count):
            a, b = ring_index * count + j, ring_index * count + (j + 1) % count
            faces.append((centre_id, b, a) if flip else (centre_id, a, b))
    solid = trimesh.Trimesh(np.concatenate(vertices), np.array(faces), process=False)
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


def union(parts):
    return trimesh.boolean.union(list(parts), engine="manifold")


def difference(base, cutters):
    return trimesh.boolean.difference([base, union(cutters)], engine="manifold")


def mirror_x(solid):
    other = solid.copy()
    other.vertices = other.vertices * np.array([-1.0, 1.0, 1.0])
    other.invert()
    return other


# --------------------------------------------------------------------------------------------
# Corpo inferior
# --------------------------------------------------------------------------------------------
def lower_body():
    rings = np.array([shape.full_section(y) for y in shape.stations()])
    return loft_solid(rings)


def wheel_house_cutters():
    """Arco de roda em dois degraus: aro fino na chapa (3 cm) e caixa de roda mais larga por dentro."""
    cutters = []
    for side in (1, -1):
        for y in (shape.WHEEL_Y, -shape.WHEEL_Y):
            lip = cylinder_x(shape.ARCH_RADIUS, 0.905, 1.3, y, shape.WHEEL_RADIUS)
            well = cylinder_x(shape.ARCH_RADIUS + 0.035, 0.52, 0.92, y, shape.WHEEL_RADIUS)
            for part in (lip, well):
                if side < 0:
                    part = mirror_x(part)
                cutters.append(part)
    return cutters


def cavity_cutters():
    """Interior: o vão da cabine, mais estreito sobre as caixas das rodas traseiras (abaixo do banco)."""
    return [box(-CAVITY_HALF_WIDTH, CAVITY_HALF_WIDTH, -0.98, 0.96, CAVITY_FLOOR, 1.3),
            box(-0.50, 0.50, -1.50, -0.97, CAVITY_FLOOR, 1.3),
            box(-CAVITY_HALF_WIDTH, CAVITY_HALF_WIDTH, -1.50, -0.97, 0.80, 1.3)]


def in_cavity(points, slack=0.004):
    """True para pontos (N, 3) dentro do vão da cabine (com folga), para classificar faces internas."""
    inside = np.zeros(len(points), bool)
    for cutter in cavity_cutters():
        lo, hi = cutter.bounds
        inside |= np.all((points >= lo - slack) & (points <= hi + slack), axis=1) & (points[:, 2] < 1.25)
    return inside


# --------------------------------------------------------------------------------------------
# Frestas (sulcos de 5 mm) varridas ao longo de caminhos sobre a chapa
# --------------------------------------------------------------------------------------------
def rounded_polyline(points, radius, steps=5):
    """Caminho 2D com os cantos internos arredondados (raio aproximado por recuo `radius`)."""
    points = [np.asarray(p, float) for p in points]
    out = [points[0]]
    for before, corner, after in zip(points, points[1:], points[2:]):
        to_before, to_after = before - corner, after - corner
        start = corner + to_before / np.linalg.norm(to_before) * min(radius, np.linalg.norm(to_before) * 0.45)
        end = corner + to_after / np.linalg.norm(to_after) * min(radius, np.linalg.norm(to_after) * 0.45)
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
    entra `depth` na chapa e sai `reach` para fora, então a fresta acompanha qualquer curvatura leve.
    """
    path = resample(path)
    base = surface(path)
    tangent = np.gradient(path, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    # direção de largura: perpendicular ao caminho dentro do plano da superfície
    plane_normal = np.asarray(outward, float)
    across = np.cross(plane_normal[None, :], np.column_stack([tangent, np.zeros(len(tangent))]) if False else
                      _tangent3(tangent, outward))
    across /= np.linalg.norm(across, axis=1, keepdims=True)
    half = width / 2
    inner, outer = -depth * plane_normal, reach * plane_normal
    rings = np.stack([base + across * half + inner, base - across * half + inner,
                      base - across * half + outer, base + across * half + outer], axis=1)
    return loft_solid(rings)


def _tangent3(tangent2, outward):
    """Leva a tangente 2D do caminho para 3D, nos dois eixos que não são `outward`."""
    axes = [k for k in range(3) if abs(outward[k]) < 0.5]
    out = np.zeros((len(tangent2), 3))
    out[:, axes[0]], out[:, axes[1]] = tangent2[:, 0], tangent2[:, 1]
    return out


def side_surface(sign):
    """Pontos 3D da lateral (caminho em (y, z))."""
    return lambda p: np.column_stack([sign * shape.side_x(p[:, 0], p[:, 1]), p[:, 0], p[:, 1]])


def top_surface(path):
    """Pontos 3D do capô/porta-malas (caminho em (x, y))."""
    return np.column_stack([path[:, 0], path[:, 1], shape.hood_surface_z(path[:, 0], path[:, 1])])


def door_groove_paths():
    """Caminhos (y, z) em U de cada porta: borda dianteira, soleira e borda traseira."""
    belt = shape.BELT_Z - 0.002
    bottom = shape.DOOR_BOTTOM_Z
    paths = []
    for front, rear in (shape.FRONT_DOOR, shape.REAR_DOOR):
        paths.append(rounded_polyline([(front + 0.035, belt), (front - 0.012, bottom + 0.16), (front - 0.045, bottom),
                                       (rear + 0.045, bottom), (rear - 0.010, bottom + 0.16), (rear + 0.030, belt)], 0.09))
    return paths


def lid_groove_paths():
    """Caminhos (x, y) do capô e da tampa do porta-malas, em coordenadas do lado +X (espelhar para -X)."""
    hood_front, hood_rear = 2.185, shape.COWL_Y + 0.015
    trunk_front, trunk_rear = shape.REAR_GLASS_BASE_Y - 0.03, -2.115
    hood = rounded_polyline([(0.0, hood_front), (0.70, hood_front - 0.03), (0.745, hood_front - 0.12),
                             (0.745, hood_rear + 0.06), (0.70, hood_rear), (0.0, hood_rear)], 0.07)
    trunk = rounded_polyline([(0.0, trunk_front), (0.72, trunk_front), (0.75, trunk_front - 0.08),
                              (0.75, trunk_rear + 0.10), (0.70, trunk_rear), (0.0, trunk_rear)], 0.07)
    return [hood, trunk]


def groove_cutters():
    cutters = []
    for sign in (1, -1):
        outward = (sign, 0.0, 0.0)
        for path in door_groove_paths():
            cutters.append(sweep_groove(path, side_surface(sign), outward))
        for path in lid_groove_paths():
            mirrored = path * np.array([sign, 1.0])
            cutters.append(sweep_groove(mirrored, top_surface, (0.0, 0.0, 1.0)))
    return cutters


def pocket_cutters():
    """Bolsões de farol, grade, lanternas, placa e maçanetas."""
    cutters = []
    for sign in (1, -1):
        lo, hi = sorted((sign * 0.43, sign * 0.90))
        cutters.append(box(lo, hi, 2.165, 2.45, 0.53, 0.71))                       # farol
        lo, hi = sorted((sign * 0.46, sign * 0.95))
        cutters.append(box(lo, hi, -2.45, -2.185, 0.745, 0.905))                   # lanterna
        for handle_y in (-0.10, -0.92):
            z0, z1 = 0.915, 0.955
            lo_x = float(shape.side_x(handle_y, 0.935)) - 0.034
            lo, hi = sorted((sign * lo_x, sign * 1.1))
            cutters.append(box(lo, hi, handle_y - 0.075, handle_y + 0.075, z0, z1))
    cutters.append(box(-0.39, 0.39, 2.19, 2.45, 0.545, 0.700))                    # grade
    cutters.append(box(-0.20, 0.20, -2.45, -2.235, 0.66, 0.78))                    # placa
    return cutters


# --------------------------------------------------------------------------------------------
# Cabine
# --------------------------------------------------------------------------------------------
def cabin_section(y, wall=0.0):
    """Anel (M, 3) da cabine na estação y; `wall` > 0 encolhe para dentro (para escavar o miolo)."""
    taper = 1.0 - 0.07 * shape.smoothstep(-0.9, -1.7, y) - 0.03 * shape.smoothstep(0.45, 1.05, y)
    base = 0.90 if wall else 0.97
    zs = np.linspace(base, shape.ROOF_Z - 0.06, 7)
    half = [(float(shape.cabin_half_width(z)) * taper - wall, z) for z in zs]
    roof_edge = half[-1][0]
    roof = [(roof_edge * (1 - u), shape.ROOF_Z - wall - 0.030 * ((roof_edge * (1 - u)) / 0.72) ** 2)
            for u in (0.0, 0.12, 0.3, 0.5, 0.7, 0.88, 1.0)]
    points = [(0.0, base)] + half + [roof[0]] + roof[1:][::-1][::-1][:0]
    right = [(0.0, base)] + half + [(x, z) for x, z in roof]
    right = shape._round_path(right, {len(half): 0.05})
    left = right[-2:0:-1].copy()
    left[:, 0] *= -1.0
    ring = np.concatenate([right, left])
    del points
    return np.column_stack([ring[:, 0], np.full(len(ring), float(y)), ring[:, 1]])


def glass_polygons_3d():
    """Contornos 3D (N, 3) de cada vidro: para-brisa, vidro traseiro e quatro laterais."""
    (wy0, wz0), (wy1, wz1) = shape.WINDSHIELD_BASE, shape.WINDSHIELD_TOP
    inset = 0.075
    windshield = [(-(shape.cabin_half_width(wz0) - inset), wy0, wz0), ((shape.cabin_half_width(wz0) - inset), wy0, wz0),
                  ((shape.cabin_half_width(wz1) - inset - 0.01), wy1 + 0.04, wz1 - 0.07),
                  (-(shape.cabin_half_width(wz1) - inset - 0.01), wy1 + 0.04, wz1 - 0.07)]
    (ry0, rz0), (ry1, rz1) = shape.REAR_GLASS_TOP, shape.REAR_GLASS_BASE
    rear_inset = 0.11
    rear = [(-(shape.cabin_half_width(rz1) - rear_inset), ry1 - 0.0 + (ry1 - ry0) * 0.0, rz1),
            ((shape.cabin_half_width(rz1) - rear_inset), ry1, rz1),
            ((shape.cabin_half_width(rz0 - 0.06) - rear_inset), ry0 - 0.03, rz0 - 0.06),
            (-(shape.cabin_half_width(rz0 - 0.06) - rear_inset), ry0 - 0.03, rz0 - 0.06)]
    glass = {"windshield": np.array(windshield, float), "rear": np.array(rear, float)}
    for name, polygon in shape.side_window_polygons().items():
        for sign in (1, -1):
            glass[f"side_{name}_{'p' if sign > 0 else 'd'}"] = np.array(
                [(sign * float(shape.side_window_surface_x(z)), y, z) for y, z in polygon], float)
    return glass


def window_cutter(corners, thickness=0.30):
    """Prisma que atravessa a chapa: o polígono do vidro extrudado para os dois lados da sua normal."""
    corners = np.asarray(corners, float)
    normal = np.cross(corners[1] - corners[0], corners[3] - corners[0])
    normal /= np.linalg.norm(normal)
    slab = np.stack([corners + normal * thickness, corners - normal * thickness])
    faces = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
             (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    solid = trimesh.Trimesh(slab.reshape(-1, 3), np.array(faces), process=False)
    if solid.volume < 0:
        solid.invert()
    return solid


def cabin_shell():
    """Teto e colunas: casca de 2,8 cm com os vãos dos vidros recortados."""
    ys = np.linspace(-1.85, 1.15, 40)
    outer = loft_solid(np.array([cabin_section(y) for y in ys]))
    inner = loft_solid(np.array([cabin_section(y, CABIN_WALL) for y in np.linspace(-1.9, 1.2, 40)]))
    profile = [(shape.COWL_Y + 0.06, shape.BELT_Z - 0.05), shape.WINDSHIELD_TOP, shape.REAR_GLASS_TOP,
               (shape.REAR_GLASS_BASE[0] - 0.05, shape.BELT_Z - 0.05)]
    side_cut = trimesh.creation.extrude_polygon(_polygon([(y, z) for y, z in profile]), height=3.0)
    side_cut.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, (0, 1, 0)) @
                             trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0)) if False else np.eye(4))
    del side_cut
    return outer, inner


def _polygon(points):
    from shapely.geometry import Polygon
    return Polygon(points)


if __name__ == "__main__":
    body = lower_body()
    print(len(body.vertices), len(body.faces), body.is_watertight, body.volume)
