"""Etapa de build do engine: câmera do jogador, lanterna, viewmodel e textos embutidos no .blend."""
import math

import bmesh
import bpy

from .. import ROOT_DIR
from .. import conventions as C
from .. import layout, matapi
from . import texts
from .flashlight import LIGHT_OFFSET, VIEWMODEL_OFFSET, WARM

PLAYER_FAR_CLIP = 200.0

JOGAR_SCRIPT = '''"""Inicia SEM ALVORADA: rode este texto no editor de texto do Blender (Alt+P)."""
import os
import sys

import bpy

BUILD_ROOT = r"{root}"

for root in (os.path.dirname(bpy.data.filepath), BUILD_ROOT):
    if root and os.path.isdir(os.path.join(root, "sem_alvorada")):
        if root not in sys.path:
            sys.path.insert(0, root)
        break
else:
    raise RuntimeError("Pasta do projeto não encontrada: abra o .blend de dentro da pasta do jogo.")

from sem_alvorada.engine import launcher

launcher.start()
'''


def _new_object(name, datablock):
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, datablock)
    return obj


def make_player_camera(ctx):
    camera_data = bpy.data.cameras.get(C.OBJ_PLAYER_CAM) or bpy.data.cameras.new(C.OBJ_PLAYER_CAM)
    camera_data.sensor_fit = "HORIZONTAL"
    camera_data.lens_unit = "FOV"
    camera_data.angle = math.radians(C.FOV_DEG)
    camera_data.clip_start = 0.05
    camera_data.clip_end = PLAYER_FAR_CLIP
    camera_data.show_passepartout = False
    cam = _new_object(C.OBJ_PLAYER_CAM, camera_data)
    x, y, z = layout.PLAYER_START
    cam.location = (x, y, z + C.PLAYER_EYE_STAND)
    cam.rotation_euler = (math.pi / 2, 0.0, math.radians(layout.PLAYER_START_YAW_DEG))
    ctx.link(cam, C.COL_PLAYER)
    return cam


def make_flashlight(ctx, cam):
    spot_data = bpy.data.lights.get(C.OBJ_FLASHLIGHT) or bpy.data.lights.new(C.OBJ_FLASHLIGHT, "SPOT")
    spot_data.energy = C.FLASH_ENERGY
    spot_data.spot_size = math.radians(C.FLASH_SPOT_DEG)
    spot_data.spot_blend = 0.25
    spot_data.color = WARM
    spot_data.use_shadow = True
    spot_data.shadow_soft_size = 0.03
    light = _new_object(C.OBJ_FLASHLIGHT, spot_data)
    light.parent = cam
    light.location = LIGHT_OFFSET
    light.rotation_euler = (0.0, 0.0, 0.0)
    ctx.link(light, C.COL_PLAYER)
    return light


def _fallback_viewmodel():
    """Lanterna simples (corpo + cabeça) caso o módulo props não tenha criado a dela."""
    mesh = bpy.data.meshes.new(C.OBJ_VIEW_FLASH)
    builder = bmesh.new()
    for radius, depth, offset in ((0.026, 0.16, 0.08), (0.038, 0.06, 0.19)):
        shift = bmesh.ops.create_cone(builder, cap_ends=True, segments=8, radius1=radius, radius2=radius, depth=depth)
        bmesh.ops.translate(builder, verts=shift["verts"], vec=(0.0, 0.0, -offset))
    builder.to_mesh(mesh)
    builder.free()
    obj = bpy.data.objects.new(C.OBJ_VIEW_FLASH, mesh)
    matapi.assign(obj, "metal")
    return obj


def hang_viewmodel(ctx, cam):
    obj = bpy.data.objects.get(C.OBJ_VIEW_FLASH)
    if obj is None:
        ctx.log("ViewModel_Flashlight ausente: criando uma lanterna simples")
        obj = _fallback_viewmodel()
    obj.parent = cam
    obj.location = VIEWMODEL_OFFSET
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.hide_viewport = obj.hide_render = True
    if hasattr(obj, "visible_shadow"):
        obj.visible_shadow = False
    ctx.link(obj, C.COL_PLAYER)
    return obj


def write_text(name, content):
    block = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    block.clear()
    block.write(content)
    block.use_fake_user = True
    return block


def write_texts():
    write_text("LEIA-ME", "\n".join(texts.README_LINES) + "\n")
    write_text("jogar.py", JOGAR_SCRIPT.format(root=ROOT_DIR))


def build(ctx):
    scene = ctx.scene
    cam = make_player_camera(ctx)
    make_flashlight(ctx, cam)
    hang_viewmodel(ctx, cam)
    write_texts()
    scene.camera = cam
    scene.frame_start, scene.frame_end = 1, 250
    scene["sa_engine"] = "1"
    ctx.log("PlayerCam, Flashlight, ViewModel_Flashlight, LEIA-ME e jogar.py criados")
