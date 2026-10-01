"""Tampo de laminado com dois recortes de cuba de cantos arredondados (shapely + earcut via trimesh).

Um tampo furado por duas cubas é um polígono com dois buracos: o recorte com cantos de raio 3 cm é trivial
para o `shapely` e impossível de montar bem com caixas. A extrusão já traz as paredes internas do furo.

Saída: assets/models/tampo_pia_dupla.npz
  verts, faces (triângulos), uvs (F, 3, 2) em escala de mundo (1 repetição por metro),
  holes (N, 5) = centro x, centro y, largura, profundidade, raio de cada recorte, em metros.

Sistema de coordenadas: origem no centro do balcão, frente = +Y, base do tampo em z = 0.862 (tampo de 3,8 cm
que termina em 0,90). O game lê `holes` para desenhar o aro e as cubas de aço exatamente sobre os furos.
"""
import os

import numpy as np
import trimesh
from shapely.geometry import Polygon, box

WIDTH, BACK, FRONT = 1.32, -0.30, 0.322
THICKNESS = 0.038
BASE_Z = 0.862
SINK_CENTER_X = -0.12
BOWL_WIDTH, BOWL_DEPTH, BOWL_RADIUS = 0.37, 0.40, 0.035
BOWL_CENTER_Y = -0.03
BOWL_GAP = 0.05
CORNER_STEPS = 8


def rounded_rectangle(cx, cy, width, depth, radius):
    """Polígono de retângulo com cantos em arco (`CORNER_STEPS` pontos por canto)."""
    points = []
    centers = [(cx + width / 2 - radius, cy + depth / 2 - radius, 0), (cx - width / 2 + radius, cy + depth / 2 - radius, 90),
               (cx - width / 2 + radius, cy - depth / 2 + radius, 180), (cx + width / 2 - radius, cy - depth / 2 + radius, 270)]
    for corner_x, corner_y, start in centers:
        for step in range(CORNER_STEPS):
            angle = np.radians(start + 90 * step / (CORNER_STEPS - 1))
            points.append((corner_x + radius * np.cos(angle), corner_y + radius * np.sin(angle)))
    return Polygon(points)


def bowl_holes():
    offset = (BOWL_WIDTH + BOWL_GAP) / 2
    return [(SINK_CENTER_X - offset, BOWL_CENTER_Y), (SINK_CENTER_X + offset, BOWL_CENTER_Y)]


def build():
    outline = box(-WIDTH / 2, BACK, WIDTH / 2, FRONT)
    holes = [rounded_rectangle(cx, cy, BOWL_WIDTH, BOWL_DEPTH, BOWL_RADIUS) for cx, cy in bowl_holes()]
    plate = Polygon(outline.exterior.coords, [hole.exterior.coords for hole in holes])
    mesh = trimesh.creation.extrude_polygon(plate, THICKNESS)
    mesh.apply_translation((0, 0, BASE_Z))
    return mesh


def world_uvs(mesh):
    """UV por face: planta (x, y) para topo e base, (distância ao longo do contorno, z) para as paredes."""
    uvs = np.zeros((len(mesh.faces), 3, 2), np.float32)
    for index, face in enumerate(mesh.faces):
        points = mesh.vertices[face]
        normal = mesh.face_normals[index]
        if abs(normal[2]) > 0.7:
            uvs[index] = points[:, :2]
        elif abs(normal[0]) >= abs(normal[1]):
            uvs[index] = np.stack([points[:, 1], points[:, 2]], axis=1)
        else:
            uvs[index] = np.stack([points[:, 0], points[:, 2]], axis=1)
    return uvs


def main():
    mesh = build()
    holes = np.array([(cx, cy, BOWL_WIDTH, BOWL_DEPTH, BOWL_RADIUS) for cx, cy in bowl_holes()], np.float32)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "models", "tampo_pia_dupla.npz")
    np.savez_compressed(out, verts=np.asarray(mesh.vertices, np.float32), faces=np.asarray(mesh.faces, np.int32),
                        uvs=world_uvs(mesh), holes=holes)
    print(f"{out}: {len(mesh.vertices)} vértices, {len(mesh.faces)} triângulos, {os.path.getsize(out)} bytes")


if __name__ == "__main__":
    main()
