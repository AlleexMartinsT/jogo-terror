"""O carro da família: sedã americano de 4,8 m, batido na frente do lado do passageiro (guia do reboque).

Origem no centro da base, frente = +Y local, motorista à esquerda (-X local). A carroceria (chapa, arcos,
frestas, cabine oca) vem de um `.npz` desenhado por `tools/modelagem/carro_carroceria.py`; aqui ela é
amassada, recebe as peças soltas (para-choques, faróis, grade, espelhos, interior) e os vidros.
"""
import math
import os

import bpy

from .. import ASSETS_DIR, craft
from .. import conventions as C
from .. import layout, story
from . import car_damage, car_interior, car_parts, car_wheel, kit, materials, tex_carro  # noqa: F401  (tex_carro registra os materiais)
from .car_shape import WHEEL_RADIUS, WHEEL_X, WHEEL_Y, ROOF_Z
from .lights import keep_world_position, make_point_light
from .placement import make_collision_box

HALF_WIDTH = 0.95
MODEL_PATH = os.path.join(ASSETS_DIR, "models", "carro_carroceria.npz")
SHELL_MATERIALS = ("car_body_paint", "car_black_plastic", "car_door_trim", "car_carpet", "car_rubber", "car_headliner")
SHELL_FINISH = craft.Finish(bevel=0.0, smooth_angle=38.0)


def _ensure_uv(mesh):
    """Camada UV (planta x-z) para a carroceria poder se juntar às peças do kit, que sempre têm UV."""
    layer = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        point = mesh.vertices[loop.vertex_index].co
        layer.data[loop.index].uv = (point.x, point.z)


def build_shell_mesh():
    """Chapa da carroceria lida do `.npz`, com as normais por ângulo (o amassado vem depois, em tudo junto)."""
    mesh = craft.load_npz(MODEL_PATH, [materials.get(name) for name in SHELL_MATERIALS], "car_shell")
    _ensure_uv(mesh)
    return craft.finish_mesh(mesh, SHELL_FINISH)


def build_body_mesh():
    """Tudo o que é opaco na carroceria, numa malha só e amassada de uma vez (peças soltas entortam com a chapa)."""
    parts = [build_shell_mesh(), car_parts.build_exterior().to_mesh("car_exterior"), *car_parts.exhaust_meshes(),
             car_interior.build_interior().to_mesh("car_interior")]
    body = craft.join_meshes(parts, "Car_Body")
    car_damage.crush_mesh(body)
    return body


def build_glass_mesh():
    from .car_shape import glass_polygons
    m = kit.MeshBuilder("Car_Glass")
    m.finish = craft.RAW
    corners = glass_polygons()
    for name, quad in corners.items():
        mat = "car_windshield" if name == "windshield" else "car_glass_clear"
        m.quad(*[tuple(p) for p in quad], mat, uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    return m


def build_wheel_mesh(name):
    return car_wheel.build_wheel_mesh(name, kit.QUALITY)


def _new_object(ctx, name, mesh, parent, location):
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.parent = parent
    ctx.link(obj, C.COL_PROPS)
    return obj


def _marker(ctx, name, world_position, parent, display="PLAIN_AXES", size=0.2):
    marker = bpy.data.objects.new(name, None)
    marker.empty_display_type = display
    marker.empty_display_size = size
    marker.location = world_position
    ctx.link(marker, C.COL_PROPS)
    keep_world_position(marker, parent)
    return marker


def _headlight(ctx, name, x, parent):
    lamp_data = bpy.data.lights.new(name, "SPOT")
    lamp_data.energy = 0.0
    lamp_data.spot_size = math.radians(62)
    lamp_data.spot_blend = 0.45
    lamp_data.use_shadow = False
    lamp_data.color = (1.0, 0.94, 0.78)
    lamp = bpy.data.objects.new(name, lamp_data)
    lamp.location = (x, 2.30, 0.61)
    lamp.rotation_euler = (math.radians(86), 0.0, 0.0)
    lamp.parent = parent
    lamp["sa_base_energy"] = 900.0
    lamp["sa_kind"] = "headlight"
    lamp["sa_on"] = 0
    lamp[C.P_ROOM] = "garage"
    ctx.link(lamp, C.COL_PROPS)
    return lamp


def make_car(ctx):
    """Cria `Car` (raiz), corpo, vidros, rodas, faróis desligados, olhos do motorista e ponto de interação."""
    anchor = layout.ANCHORS["car"]
    root = bpy.data.objects.new(C.OBJ_CAR, None)
    root.empty_display_type = "ARROWS"
    root.empty_display_size = 0.6
    root.location = anchor.pos
    root.rotation_euler = (0.0, 0.0, math.radians(anchor.yaw_deg))
    root[C.P_ID] = "car"
    root[C.P_ROOM] = "garage"
    ctx.link(root, C.COL_PROPS)
    body = _new_object(ctx, "Car_Body", build_body_mesh(), root, (0, 0, 0))
    body["sa_tris"] = sum(len(p.vertices) - 2 for p in body.data.polygons)
    body["sa_glow"] = 0.0          # as lâmpadas dos faróis leem esta propriedade (material car_lens_glow); a cutscene a liga com os faróis
    _new_object(ctx, "Car_Glass", build_glass_mesh().to_mesh("Car_Glass"), root, (0, 0, 0))
    for suffix, x, y in (("FL", -WHEEL_X, WHEEL_Y), ("FR", WHEEL_X, WHEEL_Y), ("RL", -WHEEL_X, -WHEEL_Y),
                         ("RR", WHEEL_X, -WHEEL_Y)):
        name = f"Car_Wheel_{suffix}"
        wheel = _new_object(ctx, name, build_wheel_mesh(name).to_mesh(name), root, (x, y, WHEEL_RADIUS))
        wheel["sa_side"] = 1 if x > 0 else -1
    _headlight(ctx, "Car_Headlight_L", -0.62, root)
    _headlight(ctx, "Car_Headlight_R", 0.62, root)
    bpy.context.view_layer.update()          # matrix_world do root precisa estar atual antes de parentear os marcadores
    eye = layout.ANCHORS["car_driver_eye"]
    _marker(ctx, "Car_DriverEye", eye.pos, root, "SPHERE", 0.1)
    door_point = layout.ANCHORS["car_interact"]
    interact = _marker(ctx, "Car_Interact", (door_point.x, door_point.y, 0.95), root, "CUBE", 0.35)
    interact[C.P_INTERACT] = "car"
    interact[C.P_ID] = "car"
    interact[C.P_PROMPT] = story.PROMPT_CAR
    make_collision_box(ctx, "car", *anchor.pos, math.radians(anchor.yaw_deg),
                       (-HALF_WIDTH - 0.02, -2.42, 0.30), (HALF_WIDTH + 0.02, 2.42, ROOF_Z + 0.05))
    make_point_light(ctx, "garage", 1, (anchor.x + 0.45, anchor.y - 0.30, 0.95), 0.6, (0.4, 1.0, 0.55), "lamp",
                     parent=root)
    return root
