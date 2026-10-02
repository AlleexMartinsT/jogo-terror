"""Panos que caem de verdade: a simulação de tecido do Blender (`craft.drape`) assenta o pano sobre o móvel.

O pano nasce plano alguns centímetros acima do ponto de apoio, cai, enrosca na barra e para. O resultado entra na cena
como objeto `wall` (ele pende, não repousa) com a origem no centro da base.
"""
import bpy
from mathutils import Matrix, Vector

from .. import craft
from . import materials
from .kg_shapes import PrebuiltMesh
from .placement import place


def _planar_uv(mesh, origin, size):
    """UV 0..1 pela posição no plano XY do pano plano (os modificadores propagam o UV pela simulação)."""
    layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop in polygon.loop_indices:
            x, y, _ = mesh.vertices[mesh.loops[loop].vertex_index].co
            layer.data[loop].uv = ((x - origin[0]) / size[0], (y - origin[1]) / size[1])


def hang_cloth(ctx, room, name, colliders, origin, size, material, cells=(12, 16), repeat=1.0):
    """Joga um pano de `size` (x, y) metros, com o canto mínimo em `origin`, sobre `colliders` e devolve o objeto."""
    grid = craft.cloth_grid(size[0], size[1], cells[0], cells[1], origin=origin)
    _planar_uv(grid, origin, size)
    grid.materials.append(materials.get(material))
    bpy.context.view_layer.update()
    settled = craft.drape(grid, colliders, frames=50, mass=0.15, stiffness=15.0, bending=3.0, thickness=0.004, subsurf=1,
                          settle_frames=15)
    for loop_uv in settled.uv_layers[0].data:
        loop_uv.uv = (loop_uv.uv[0] * repeat, loop_uv.uv[1] * repeat)
    low = Vector((min(v.co.x for v in settled.vertices), min(v.co.y for v in settled.vertices), min(v.co.z for v in settled.vertices)))
    high = Vector((max(v.co.x for v in settled.vertices), max(v.co.y for v in settled.vertices), 0.0))
    center = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    settled.transform(Matrix.Translation(-center))
    return place(ctx, PrebuiltMesh(settled), room, "cloth", center.x, center.y, 0.0, center.z, mode="wall", name=name)
