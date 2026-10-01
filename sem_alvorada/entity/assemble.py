"""Monta a hierarquia do Alto na cena: Entity > Entity_Rig, Entity_Body, Entity_Eyes, Entity_EyeLight."""
import bpy
from mathutils import Vector

from .. import conventions as C
from .. import layout
from . import materials as M
from . import model
from . import skeleton as S

RIG_NAME = "Entity_Rig"
BODY_NAME = "Entity_Body"
EYES_NAME = "Entity_Eyes"
LIGHT_NAME = "Entity_EyeLight"

EYE_LIGHT_ENERGY = 14.0          # W com os olhos no máximo
EYE_LIGHT_COLOR = (0.86, 0.93, 1.0)
EYE_LIGHT_OFFSET = Vector((0.0, 0.16, 2.535))


def _create_armature_object(ctx):
    """Cria a armadura com todos os ossos de `skeleton.BONES`."""
    armature = bpy.data.armatures.new(RIG_NAME)
    armature.display_type = "STICK"
    obj = bpy.data.objects.new(RIG_NAME, armature)
    ctx.link(obj, C.COL_ENTITY)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        edit_bones = {}
        for b in S.BONES:
            edit = armature.edit_bones.new(b.name)
            edit.head, edit.tail = b.head, b.tail
            edit.parent = edit_bones.get(b.parent)
            edit.use_deform = True
            edit_bones[b.name] = edit
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    for pose_bone in obj.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
    return obj


def _skin_to_rig(mesh_obj, rig_obj):
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = rig_obj
    mod.use_vertex_groups = True
    mod.use_bone_envelopes = False


def _create_eye_light():
    light = bpy.data.lights.new(LIGHT_NAME, "POINT")
    light.color = EYE_LIGHT_COLOR
    light.energy = 0.0
    light.shadow_soft_size = 0.06
    light.use_shadow = False
    obj = bpy.data.objects.new(LIGHT_NAME, light)
    obj.location = EYE_LIGHT_OFFSET
    obj[C.P_LIGHT_ENERGY] = EYE_LIGHT_ENERGY
    return obj


def hide_entity(objects, hidden=True):
    """Oculta/mostra malha, olhos e luz. A armadura continua avaliada para deformar a malha."""
    for obj in objects:
        obj.hide_viewport = hidden
        obj.hide_render = hidden


def create_entity(ctx):
    """Constrói o Alto inteiro e devolve o Empty raiz. Chamado por `entity.build`."""
    materials = M.build_all(ctx.rng)

    root = bpy.data.objects.new(C.OBJ_ENTITY, None)
    root.empty_display_type = "ARROWS"
    root.empty_display_size = 0.4
    root["sa_height"] = C.ENTITY_HEIGHT
    ctx.link(root, C.COL_ENTITY)

    rig = _create_armature_object(ctx)
    body = model.create_body_object(materials)
    eyes = model.create_eyes_object(materials)
    light = _create_eye_light()
    for obj in (body, eyes, light):
        ctx.link(obj, C.COL_ENTITY)
    for obj in (rig, body, eyes, light):
        obj.parent = root
    _skin_to_rig(body, rig)
    _skin_to_rig(eyes, rig)

    sx, sy, sz = layout.ENTITY_SPAWN
    root.location = (sx, sy, sz)
    root.rotation_euler = (0.0, 0.0, C.dir_yaw(0.0, -1.0))     # de frente para o corredor
    hide_entity((body, eyes, light))
    ctx.log(f"Alto: {model.triangle_count(body) + model.triangle_count(eyes)} triângulos, "
            f"{len(S.BONES)} ossos")
    return root
