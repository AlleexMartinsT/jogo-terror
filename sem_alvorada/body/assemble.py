"""Monta o corpo na cena: armadura, malha única com grupos de vértices e o modificador Armature.

    PlayerBody_Rig (armadura)  >  PlayerBody (malha, filha, sem transformação própria)

Os dois ficam na coleção do jogador, sem prefixo `COL_` e sem `sa_interact`: nada aqui vira colisão nem alvo.
"""
import bpy

from .. import conventions as C
from .. import craft
from . import materials as M
from . import shape_cloth as cloth
from . import shape_skin as skin
from . import skeleton as S
from .meshkit import Mesh

# ossos que não deformam malha no marco 1 (continuam existindo como referência)
NON_DEFORM = ()


def create_armature(ctx):
    armature = bpy.data.armatures.new(C.OBJ_BODY_RIG)
    armature.display_type = "STICK"
    obj = bpy.data.objects.new(C.OBJ_BODY_RIG, armature)
    ctx.link(obj, C.COL_PLAYER)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        edit_bones = {}
        for b in S.BONES:
            edit = armature.edit_bones.new(b.name)
            edit.head, edit.tail = b.head, b.tail
            edit.parent = edit_bones.get(b.parent)
            edit.use_connect = False
            edit.use_deform = b.deform
            edit_bones[b.name] = edit
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    for pose_bone in obj.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
    obj.select_set(False)
    return obj


def build_mesh_data():
    """Todas as peças do corpo, já com pesos, em uma `Mesh` só."""
    mesh = Mesh()
    mesh.merge(cloth.build_shirt_torso())
    sleeve = cloth.build_sleeve_right()
    mesh.merge(sleeve.copy())
    mesh.merge(cloth.mirror(sleeve))
    arm = skin.build_hand_skin("R")
    mesh.merge(arm.copy())
    mesh.merge(skin.mirror_arm(arm))
    mesh.merge(cloth.build_pants())
    boot = cloth.build_boot_right()
    mesh.merge(boot.copy())
    mesh.merge(cloth.mirror(boot))
    return mesh


def mesh_to_blender(data, name):
    slots = M.SLOT_ORDER
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(data.verts, [], data.faces)
    for material in M.slot_materials():
        mesh.materials.append(material)
    mesh.polygons.foreach_set("material_index", [M.slot_index(m) for m in data.material])
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    uv_main = mesh.uv_layers.new(name="UVMap")
    uv_main.data.foreach_set("uv", [c for face in data.uv0 for pair in face for c in pair])
    uv_tile = mesh.uv_layers.new(name="UVTile")
    uv_tile.data.foreach_set("uv", [c for face in data.uv1 for pair in face for c in pair])
    mesh.update()
    mesh.validate()
    craft.shade_by_angle(mesh, 70.0)
    return mesh


def apply_weights(obj, data):
    groups = {name: obj.vertex_groups.new(name=name) for name in S.BONE_ORDER}
    by_bone = {}
    for index, weights in enumerate(data.weights):
        for bone, weight in weights.items():
            if weight > 0.001:
                by_bone.setdefault((bone, round(weight, 3)), []).append(index)
    for (bone, weight), indices in by_bone.items():
        groups[bone].add(indices, weight, "REPLACE")


def triangle_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def create_body(ctx):
    rig = create_armature(ctx)
    data = build_mesh_data()
    mesh = mesh_to_blender(data, C.OBJ_BODY)
    body = bpy.data.objects.new(C.OBJ_BODY, mesh)
    ctx.link(body, C.COL_PLAYER)
    body.parent = rig
    apply_weights(body, data)
    modifier = body.modifiers.new("Armature", "ARMATURE")
    modifier.object = rig
    modifier.use_vertex_groups = True
    modifier.use_bone_envelopes = False
    if hasattr(body, "visible_shadow"):
        body.visible_shadow = False          # a lanterna fica colada ao corpo: sem sombra projetada pelas próprias mãos
    body.hide_viewport = body.hide_render = True
    return rig, body, data
