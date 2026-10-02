"""Panos da sala e do jantar (manta, toalha de mesa, guardanapos, casacos) simulados com `craft.drape`.

O pano nasce plano acima dos objetos que vão segurá-lo e cai na simulação do Blender. Os colliders são
formas simples que o chamador desenha num `MeshBuilder` nas mesmas coordenadas locais do pano, então o
resultado entra direto no móvel (`Composite.add_mesh`) sem passar por nenhuma transformação.
"""
import math

import bpy
from mathutils import Matrix

from .. import craft
from . import kit, materials

QUALITY_CELL = {"low": 1.6, "medium": 1.0, "high": 0.75}
QUALITY_FRAMES = {"low": 0.7, "medium": 1.0, "high": 1.2}


def collider_builder(name="collider"):
    """Construtor de formas de apoio: sem chanfro, sem material (o pano só precisa da geometria)."""
    builder = kit.MeshBuilder(name)
    builder.finish = craft.RAW
    return builder


def drape_over(colliders, *, width, depth, center, material, yaw=0.0, cell=0.04, frames=70, mass=0.3,
               stiffness=15.0, bending=8.0, thickness=0.006, pressure=None, subsurf=1, pin_rect=None, pin=None,
               vertical=False, ripple=None):
    """Pano de `width` x `depth` m que cai de `center` (x, y, z) sobre `colliders` (um `MeshBuilder` ou vários).

    `pin_rect` (x0, y0, x1, y1), em coordenadas locais finais: o pano começa deitado na altura `center[2]` e
    os vértices dentro do retângulo ficam presos nela; só o que passa da borda cai. É o modo da toalha de
    mesa, que sem isso escorrega para um lado. `pin` é a versão geral: uma função (x, y, z) -> bool.
    `vertical=True` levanta o pano no plano XZ (um casaco pendurado); `ripple=(amplitude, comprimento)` ondula o
    pano plano antes da queda, o que semeia as dobras. Devolve a malha assentada, com espessura de `thickness` m.
    """
    scene = bpy.context.scene
    builders = colliders if isinstance(colliders, (list, tuple)) else [colliders]
    objects = []
    try:
        for index, builder in enumerate(builders):
            holder = bpy.data.objects.new(f"_cloth_collider_{index}", builder.to_mesh(f"_collider_{index}"))
            scene.collection.objects.link(holder)
            _make_grippy(holder)
            objects.append(holder)
        cell = cell * QUALITY_CELL.get(kit.QUALITY, 1.0)
        nx, ny = max(5, round(width / cell)), max(5, round(depth / cell))
        grid = craft.cloth_grid(width, depth, nx, ny, origin=(-width / 2, -depth / 2, 0.0))
        if ripple:
            for vertex in grid.vertices:
                vertex.co.z += ripple[0] * math.sin(2 * math.pi * vertex.co.x / ripple[1] + 1.7 * math.sin(vertex.co.y * 3.1))
        lift = Matrix.Rotation(math.pi / 2, 4, "X") if vertical else Matrix.Identity(4)
        grid.transform(Matrix.Translation(center) @ Matrix.Rotation(yaw, 4, "Z") @ lift)
        if pin_rect:
            x0, y0, x1, y1 = pin_rect
            pin = lambda x, y, z: x0 <= x <= x1 and y0 <= y <= y1          # noqa: E731
        pin_group = _pin_where(grid, pin) if pin else None
        frame_count = max(40, int(frames * QUALITY_FRAMES.get(kit.QUALITY, 1.0)))
        settled = craft.drape(grid, objects, frames=frame_count, mass=mass, stiffness=stiffness, bending=bending,
                              thickness=0.012, pressure=pressure, subsurf=subsurf, pin_group=pin_group)
    finally:
        for holder in objects:
            mesh = holder.data
            scene.collection.objects.unlink(holder)
            bpy.data.objects.remove(holder)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
    if thickness:
        settled = craft.bake_mesh(settled, lambda holder: _solidify(holder, thickness))
        for polygon in settled.polygons:
            polygon.use_smooth = True
    settled.materials.append(materials.get(material))
    return settled


def _pin_where(mesh, predicate):
    """Grupo de vértices "pin": peso 1 (preso, como no painel Pinning do Blender) onde `predicate(x, y, z)`, 0 fora."""
    holder = bpy.data.objects.new("_cloth_pin", mesh)
    bpy.context.scene.collection.objects.link(holder)
    try:
        group = holder.vertex_groups.new(name="pin")
        for vertex in mesh.vertices:
            group.add([vertex.index], 1.0 if predicate(*vertex.co) else 0.0, "REPLACE")
    finally:
        bpy.context.scene.collection.objects.unlink(holder)
        bpy.data.objects.remove(holder)
    return "pin"


def _make_grippy(holder):
    """Colisão com muito atrito: sem isso a manta escorrega da almofada em vez de ficar onde caiu."""
    modifier = holder.modifiers.new("craft_collision", "COLLISION")
    modifier.settings.thickness_outer = 0.004
    modifier.settings.use_culling = False
    modifier.settings.cloth_friction = 30.0
    modifier.settings.damping = 0.2


def _solidify(holder, thickness):
    modifier = holder.modifiers.new("craft_solidify", "SOLIDIFY")
    modifier.thickness = thickness
    modifier.offset = 0.0
