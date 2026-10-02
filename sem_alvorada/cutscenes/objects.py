"""Objetos que só existem para as cutscenes: câmera, luzes de apoio, relógio 6:12 e brilho da aurora.

Tudo nasce oculto/apagado; as ações do roteiro ligam quando precisam (`CutLight_*` com energia 0
ficam ocultas para não gastar o orçamento de luzes da cena).
"""
import math

import bpy
from mathutils import Vector

from .. import compat
from .. import conventions as C
from .. import layout
from ..props import bedroom_master as bedroom
from ..props import textures
from . import scripts as sc

CAMERA_FOV_DEG = 60.0


def _place(obj, ctx, hidden=False):
    ctx.link(obj, C.COL_CUTSCENE)
    obj.hide_viewport = obj.hide_render = hidden
    return obj


def create_camera(ctx):
    camera_data = bpy.data.cameras.new(C.OBJ_CUT_CAM)
    camera_data.sensor_fit = "HORIZONTAL"    # `angle` é o FOV horizontal, como o do jogador
    camera_data.angle = math.radians(CAMERA_FOV_DEG)
    camera_data.clip_start = 0.03
    camera_data.clip_end = 400.0
    cam = bpy.data.objects.new(C.OBJ_CUT_CAM, camera_data)
    first_eye = sc.anchor("nightstand_clock", 0.28, -1.1, 0.75)
    cam.location = first_eye
    cam.rotation_mode = "QUATERNION"
    return _place(cam, ctx)


def _light(ctx, name, kind, color, location, target=None, size=0.05, area=None):
    light_data = bpy.data.lights.new(name, kind)
    light_data.color = color
    light_data.energy = 0.0
    light_data.use_shadow = False
    if kind == "AREA":
        light_data.shape = "RECTANGLE"
        light_data.size, light_data.size_y = area
    else:
        light_data.shadow_soft_size = size
    obj = bpy.data.objects.new(name, light_data)
    obj.location = location
    if target is not None:
        obj.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    return _place(obj, ctx, hidden=True)


def parent_to_car(obj, ctx):
    """Se o módulo props já criou o `Car`, a luz anda com ele (mantendo a posição de mundo atual)."""
    car_obj = bpy.data.objects.get(C.OBJ_CAR)
    if car_obj is not None:
        bpy.context.view_layer.update()      # sem isso matrix_world do carro ainda é a identidade
        obj.parent = car_obj
        obj.matrix_parent_inverse = car_obj.matrix_world.inverted()


def create_lights(ctx):
    car = layout.ANCHORS["car"]
    clock = layout.ANCHORS["nightstand_clock"]
    _light(ctx, sc.CLOCK_GLOW, "POINT", (1.0, 0.12, 0.07), (clock.x + 0.16, clock.y, clock.z + 0.72))
    _light(ctx, sc.BED_LAMP, "POINT", (1.0, 0.72, 0.42), (clock.x + 0.05, clock.y + 0.12, clock.z + 1.05), size=0.12)
    window = sc.window_center("w_master_n")
    _light(ctx, sc.DAWN_LIGHT, "AREA", (0.55, 0.68, 0.95), (window[0], window[1] + 0.9, window[2]),
           target=(window[0], window[1] - 3.0, window[2] - 0.6), area=(2.6, 1.6))
    _light(ctx, sc.DRIVEWAY_LIGHT, "SPOT", (0.62, 0.72, 1.0), (10.5, -6.5, 4.8), target=(car.x, -2.0, 0.8), size=0.5)
    cabin = _light(ctx, sc.CAR_CABIN, "POINT", (0.75, 0.82, 1.0), (car.x + 0.45, car.y + 1.10, 1.35), size=0.1)
    parent_to_car(cabin, ctx)
    road = layout.ENTITY_ROAD_POS
    _light(ctx, sc.ROAD_LIGHT, "SPOT", (0.85, 0.9, 1.0), (road[0], road[1] + 6.0, 3.4),
           target=(road[0], road[1], 1.4), size=0.4)
    sight = layout.ENTITY_FIRST_SIGHT
    _light(ctx, sc.CORRIDOR_RIM, "POINT", (0.55, 0.68, 1.0), (sight[0], sight[1] + 0.9, sight[2] + 2.3), size=0.2)


def _display_material(name="cut_clock_digits", strength=7.0):
    """Mostrador 6:12 do relógio final: a mesma imagem do despertador, emissiva e mais forte (é o foco do plano)."""
    mat = compat.new_material(name)
    bsdf = compat.bsdf_of(mat)
    image = mat.node_tree.nodes.new("ShaderNodeTexImage")
    image.image = textures.image("digits_612")
    image.interpolation = "Closest"           # mostrador digital: pixel de propósito
    mat.node_tree.links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
    mat.node_tree.links.new(image.outputs["Color"], bsdf.inputs["Emission Color"])
    compat.set_bsdf(bsdf, base_color=(0, 0, 0), roughness=0.4, emission_strength=strength)
    return mat


def create_end_clock(ctx):
    """Despertador marcando 6:12, no lugar exato do da cabeceira (que o roteiro esconde), para o plano final."""
    anchor = layout.ANCHORS["nightstand_clock"]
    x, y, yaw = bedroom.ALARM_CLOCK_POSE
    top = 0.55
    _display_material()
    mesh = bedroom.alarm_clock_assembly("cut_clock_digits", sc.END_CLOCK).to_mesh(sc.END_CLOCK)
    obj = bpy.data.objects.new(sc.END_CLOCK, mesh)
    obj.location = (x, y, anchor.z + top + 0.001)
    obj.rotation_euler = (0.0, 0.0, yaw)
    return _place(obj, ctx, hidden=True)


def create_all(ctx):
    create_camera(ctx)
    create_lights(ctx)
    create_end_clock(ctx)
