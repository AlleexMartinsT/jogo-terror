"""Tampo de bancada de cozinha com cuba recortada (booleana via manifold3d).

Recortar uma cuba num tampo com caixas empilhadas exigiria montar a borda à mão; a booleana faz o
buraco já com a parede interna e o fundo. Saída: assets/models/tampo_com_cuba.npz
(unidades em metros; origem no canto frontal esquerdo da face de baixo; frente = -Y).
"""
import os

import numpy as np
import trimesh


def build(width=1.80, depth=0.62, thickness=0.04, sink_w=0.52, sink_d=0.40, sink_h=0.20, offset_x=0.55):
    top = trimesh.creation.box(extents=(width, depth, thickness))
    top.apply_translation((width / 2, depth / 2, thickness / 2))
    basin = trimesh.creation.box(extents=(sink_w, sink_d, sink_h * 2))
    basin.apply_translation((offset_x + sink_w / 2, depth / 2, thickness))
    cut = trimesh.boolean.difference([top, basin], engine="manifold")
    return cut


if __name__ == "__main__":
    mesh = build()
    triangles = np.asarray(mesh.faces, dtype=np.int32)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "models", "tampo_com_cuba.npz")
    np.savez_compressed(out, verts=np.asarray(mesh.vertices, dtype=np.float32), faces=triangles)
    print(f"{out}: {len(mesh.vertices)} vértices, {len(triangles)} triângulos")
