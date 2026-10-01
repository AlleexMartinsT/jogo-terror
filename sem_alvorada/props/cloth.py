"""Panos dos quartos: lençol, edredom, cortina, toalha e roupa, simulados com `craft.drape`; travesseiros inflados.

O pano nasce plano alguns centímetros acima dos objetos que vão segurá-lo e cai na simulação do Blender.
Os colliders são montados a partir dos builders do móvel, nas mesmas coordenadas locais do pano.
"""
import math
from contextlib import contextmanager

import bmesh
import bpy
from mathutils import Matrix

from .. import craft
from . import kit, materials

COLLIDER_NAME = "_cloth_collider"


def grid_density(cell):
    """Tamanho de célula da grade do pano conforme a qualidade do build (maior no `low`)."""
    return cell * {"low": 1.5, "medium": 1.0, "high": 0.8}.get(kit.QUALITY, 1.0)


@contextmanager
def colliders(*sources, floor=None):
    """Objetos temporários na cena para o pano colidir: builders do móvel, malhas prontas e (opcional) o piso.

    `floor` é a altura do piso no sistema local do móvel; cria uma laje larga ali.
    """
    scene = bpy.context.scene
    created = []
    try:
        for source in sources:
            if hasattr(source, "to_mesh"):
                saved = source.finish
                source.finish = None
                mesh = source.to_mesh(COLLIDER_NAME)
                source.finish = saved
            else:
                mesh = source.copy()
            holder = bpy.data.objects.new(COLLIDER_NAME, mesh)
            scene.collection.objects.link(holder)
            created.append(holder)
        if floor is not None:
            plane = bpy.data.meshes.new(COLLIDER_NAME)
            half = 3.0
            plane.from_pydata([(-half, -half, floor), (half, -half, floor), (half, half, floor), (-half, half, floor)],
                              [], [(0, 1, 2, 3)])
            holder = bpy.data.objects.new(COLLIDER_NAME, plane)
            scene.collection.objects.link(holder)
            created.append(holder)
        yield created
    finally:
        for holder in created:
            mesh = holder.data
            scene.collection.objects.unlink(holder)
            bpy.data.objects.remove(holder)
            bpy.data.meshes.remove(mesh)


def _assign_flat_uv(mesh, origin, uv_scale):
    """UV do pano em repouso: metros a partir da quina, para a trama não esticar nas dobras."""
    layer = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        layer.data[loop.index].uv = ((co.x - origin[0]) * uv_scale, (co.y - origin[1]) * uv_scale)


def settle_cloth(width, depth, center, z, hold, material, *, cell=0.06, wrinkles=0.0, seed=0, uv_scale=1.0,
                 thickness=0.0, subsurf=1, frames=60, floor=None, **physics):
    """Pano de `width` x `depth` m centrado em `center` (x, y), solto de altura `z` sobre `hold` (lista de fontes).

    `wrinkles` (m) ondula a malha de partida: o pano assenta mantendo dobras, em vez de cair liso.
    `thickness` > 0 dá espessura ao pano (edredom, toalha grossa). Devolve a malha em coordenadas locais.
    """
    nx = max(4, int(round(width / grid_density(cell))))
    ny = max(4, int(round(depth / grid_density(cell))))
    origin = (center[0] - width / 2, center[1] - depth / 2, z)
    mesh = craft.cloth_grid(width, depth, nx, ny, origin)
    if wrinkles:
        _ripple(mesh, wrinkles, seed)
    _assign_flat_uv(mesh, origin, uv_scale)
    with colliders(*hold, floor=floor) as holders:
        settled = craft.drape(mesh, holders, frames=frames, subsurf=subsurf, **physics)
    if thickness:
        settled = craft.bake_mesh(settled, lambda holder: _solidify(holder, thickness))
        for polygon in settled.polygons:
            polygon.use_smooth = True
    settled.materials.clear()
    settled.materials.append(materials.get(material))
    return settled


def _ripple(mesh, amplitude, seed):
    """Ondulação de baixa frequência na malha de partida (soma de senos de fase sorteada)."""
    import random
    rng = random.Random(seed)
    waves = [(rng.uniform(4, 9), rng.uniform(4, 9), rng.uniform(0, math.tau), rng.uniform(0, math.tau)) for _ in range(3)]
    for vertex in mesh.vertices:
        offset = sum(math.sin(vertex.co.x * ax + px) * math.sin(vertex.co.y * ay + py) for ax, ay, px, py in waves)
        vertex.co.z += amplitude * offset / 3.0
    mesh.update()


def _solidify(holder, thickness):
    modifier = holder.modifiers.new("craft_solidify", "SOLIDIFY")
    modifier.thickness = thickness
    modifier.offset = 0.0


# ---------------------------------------------------------------------------
# Travesseiro: forma inflada calculada (a simulação com pressão do Blender fica instável e custa 30 s por peça)
# ---------------------------------------------------------------------------
def pillow(width, depth, height, material, *, dent=0.0, dent_at=(0.0, 0.0), lean=0.0, seed=0, uv_scale=1.0,
           cells=14):
    """Travesseiro de duas faces costuradas na borda, com cantos em orelha e uma depressão opcional (cabeça).

    A face de cima sobe `height` no centro; a de baixo é mais achatada, apoiada na cama. `lean` (rad) inclina
    o conjunto em torno do eixo X. Origem na base, centro do travesseiro.
    """
    import random
    rng = random.Random(seed)
    phase = [rng.uniform(0, math.tau) for _ in range(4)]
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    top, bottom = [], []

    def thickness_at(u, v):
        edge = (1 - abs(u) ** 2.3) ** 0.55 * (1 - abs(v) ** 2.3) ** 0.55
        return max(edge, 0.0)

    for side, grid in ((1, top), (-1, bottom)):
        for j in range(cells + 1):
            row = []
            for i in range(cells + 1):
                u, v = -1 + 2 * i / cells, -1 + 2 * j / cells
                body = thickness_at(u, v)
                z = height * body * (1.0 if side > 0 else 0.35)
                if side > 0 and dent:
                    d2 = ((u - dent_at[0]) ** 2 + (v - dent_at[1]) ** 2) / 0.16
                    z -= dent * math.exp(-d2) * body
                    z += 0.006 * math.sin(u * 9 + phase[0]) * math.sin(v * 7 + phase[1]) * body
                row.append(bm.verts.new((u * width / 2, v * depth / 2, z * side)))
            grid.append(row)
    for grid, flip in ((top, False), (bottom, True)):
        for j in range(cells):
            for i in range(cells):
                corners = [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
                face = bm.faces.new(corners[::-1] if flip else corners)
                for loop, corner in zip(face.loops, corners[::-1] if flip else corners):
                    loop[uv_layer].uv = (corner.co.x * uv_scale, corner.co.y * uv_scale)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    mesh = bpy.data.meshes.new("pillow")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(materials.get(material))
    lowest = min(v.co.z for v in mesh.vertices)
    mesh.transform(Matrix.Translation((0, 0, -lowest)))
    if lean:
        mesh.transform(Matrix.Rotation(lean, 4, "X"))
    mesh.update()
    return craft.finish_mesh(mesh, craft.Finish(bevel=0.0, subsurf=1, smooth_angle=180.0), kit.QUALITY)
