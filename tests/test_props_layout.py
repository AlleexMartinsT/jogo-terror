"""Teste do módulo props: constrói a mobília, os itens, o carro e confere as costuras do contrato.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_props_layout.py

Cobre: itens (propriedades, cômodo, distância do ponto previsto, apoiados numa superfície), âncoras,
pegadas dos móveis (dentro do cômodo, fora das zonas reservadas, sem atravessar outros móveis),
proxies de colisão, orçamento de triângulos, materiais, nomes únicos, luzes, carro, viewmodel e
idempotência do build.
"""
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import build, layout, props, story  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.props import placement  # noqa: E402

MAX_PROP_TRIS = 1500
MAX_CAR_TRIS = 6000
MAX_TOTAL_TRIS = 80_000
MAX_PART_LIGHTS = 13
ITEM_DISTANCE_LIMIT = 1.2
REST_TOLERANCE = 0.03


def build_scene():
    scene = build.fresh_scene()
    ctx = BuildContext(scene)
    ctx.stage = "props"
    props.build(ctx)
    bpy.context.view_layer.update()
    return scene, ctx


def triangles(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def prop_meshes(scene):
    """Malhas visíveis criadas por props (exclui proxies de colisão, que são ocultos)."""
    return [o for o in scene.objects if o.type == "MESH" and not o.hide_render]


# ---------------------------------------------------------------------------
# Itens
# ---------------------------------------------------------------------------
def check_items(scene):
    problems = []
    expected = ["FLASHLIGHT", "KEY", "MAP"] + [f"BATTERY_{i}" for i in range(1, 6)] + [f"NOTE_{i}" for i in range(1, 8)]
    assert sorted(expected) == sorted(layout.ITEM_SPOTS), "lista de itens do teste difere do layout"
    for item_id in expected:
        obj = scene.objects.get(C.N_ITEM + item_id)
        if obj is None:
            problems.append(f"item ausente: Item_{item_id}")
            continue
        kind = item_id.split("_")[0]
        room, sx, sy, _, _ = layout.ITEM_SPOTS[item_id]
        wanted = {C.P_ID: item_id, C.P_ITEM: kind, C.P_INTERACT: "note" if kind == "NOTE" else "item", C.P_ROOM: room}
        for key, value in wanted.items():
            if obj.get(key) != value:
                problems.append(f"{obj.name}: {key}={obj.get(key)!r}, esperado {value!r}")
        prompt = obj.get(C.P_PROMPT, "")
        if not prompt.startswith(story.ITEM_PROMPTS[kind]):
            problems.append(f"{obj.name}: prompt {prompt!r}")
        if kind == "NOTE" and story.NOTES[item_id][0] not in prompt:
            problems.append(f"{obj.name}: prompt sem o título da nota")
        if C.COL_ITEMS not in [c.name for c in obj.users_collection]:
            problems.append(f"{obj.name}: fora de {C.COL_ITEMS}")
        gx, gy, gz = obj.matrix_world.translation
        if math.hypot(gx - sx, gy - sy) > ITEM_DISTANCE_LIMIT:
            problems.append(f"{obj.name}: a {math.hypot(gx - sx, gy - sy):.2f} m do ponto previsto")
        found = layout.room_at(gx, gy, gz)
        if found is None or found.id != room:
            problems.append(f"{obj.name}: está em {found.id if found else None}, esperado {room}")
        if obj.get("sa_mount") == "rest" and not rests_on_surface(scene, obj):
            problems.append(f"{obj.name}: flutuando (nada a até {REST_TOLERANCE} m abaixo)")
        if any(m is None for m in obj.data.materials):
            problems.append(f"{obj.name}: material ausente")
    return problems


def rests_on_surface(scene, obj):
    """Raio para baixo a partir do ponto mais baixo do item, com o próprio item escondido do raio."""
    lowest = min((obj.matrix_world @ Vector(v.co)).z for v in obj.data.vertices)
    x, y, _ = obj.matrix_world.translation
    obj.hide_viewport = True
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    hit = scene.ray_cast(depsgraph, Vector((x, y, lowest + 0.002)), Vector((0, 0, -1)), distance=REST_TOLERANCE)[0]
    obj.hide_viewport = False
    bpy.context.view_layer.update()
    return hit


# ---------------------------------------------------------------------------
# Âncoras, móveis, colisão
# ---------------------------------------------------------------------------
def check_anchors(scene):
    problems = []
    for name, anchor in layout.ANCHORS.items():
        marker = scene.objects.get(C.N_ANCHOR + name)
        if marker is None or marker.type != "EMPTY":
            problems.append(f"Anchor_{name} ausente ou não é Empty")
            continue
        if (Vector(marker.location) - Vector(anchor.pos)).length > 1e-4:
            problems.append(f"Anchor_{name} fora da posição")
        if abs(marker.rotation_euler.z - math.radians(anchor.yaw_deg)) > 1e-4:
            problems.append(f"Anchor_{name} com yaw errado")
        owners = [o for o in scene.objects if o.get(placement.P_ANCHOR) == name and o is not marker]
        if not owners:
            problems.append(f"âncora {name} sem móvel")
        for owner in owners:
            if owner.type == "MESH" and (Vector(owner.location) - Vector(anchor.pos)).length > 1e-4:
                problems.append(f"{owner.name}: não está exatamente na âncora {name}")
    return problems


def check_collision(scene):
    problems = []
    proxies = [o for o in scene.objects if o.name.startswith(C.N_COL)]
    for proxy in proxies:
        if len(proxy.data.vertices) != 8:
            problems.append(f"{proxy.name}: {len(proxy.data.vertices)} vértices")
        if abs(proxy.rotation_euler.x) > 1e-6 or abs(proxy.rotation_euler.y) > 1e-6:
            problems.append(f"{proxy.name}: pitch/roll")
        if not (proxy.get(C.P_COL) and proxy.hide_render and proxy.hide_viewport):
            problems.append(f"{proxy.name}: flags de proxy incorretas")
        if [c.name for c in proxy.users_collection] != [C.COL_COLLISION]:
            problems.append(f"{proxy.name}: coleção {[c.name for c in proxy.users_collection]}")
    for name in layout.ANCHORS:
        if name in ("car_driver_eye", "car_interact"):
            continue
        if not any(p.name.startswith(f"{C.N_COL}{name}") for p in proxies):
            problems.append(f"âncora {name} sem proxy COL_")
    large = [o for o in placement.prop_objects(scene) if o[placement.P_MODE] == "furniture" and o.get("sa_height", 0) >= 0.3]
    covered = {re.sub(r"_\d+$", "", p.name[len(C.N_COL):]) for p in proxies}
    for obj in large:
        anchor_or_name = obj.get(placement.P_ANCHOR) or obj.name
        if not any(c == anchor_or_name or c.startswith(anchor_or_name) for c in covered) and \
                not any(p.name.startswith(C.N_COL + anchor_or_name) for p in proxies):
            problems.append(f"{obj.name}: móvel grande sem proxy")
    return problems


def check_budget(scene):
    problems = []
    total = 0
    for obj in prop_meshes(scene):
        count = triangles(obj)
        if obj.name.startswith(C.N_COL):
            continue
        total += count
        limit = MAX_CAR_TRIS if obj.name.startswith("Car_Body") else MAX_PROP_TRIS
        if count > limit:
            problems.append(f"{obj.name}: {count} triângulos (limite {limit})")
    print(f"[props] triângulos visíveis: {total}")
    if total > MAX_TOTAL_TRIS:
        problems.append(f"props somam {total} triângulos (limite {MAX_TOTAL_TRIS})")
    car_total = sum(triangles(o) for o in scene.objects if o.name.startswith("Car_") and o.type == "MESH")
    if car_total > MAX_CAR_TRIS:
        problems.append(f"carro soma {car_total} triângulos (limite {MAX_CAR_TRIS})")
    return problems


def check_materials_and_names(scene):
    problems = []
    for obj in scene.objects:
        if obj.type != "MESH" or obj.name.startswith(C.N_COL):      # proxies de colisão não são renderizados
            continue
        slots = obj.data.materials
        if not len(slots) or any(m is None for m in slots):
            problems.append(f"{obj.name}: material ausente")
            continue
        if any(p.material_index >= len(slots) for p in obj.data.polygons):
            problems.append(f"{obj.name}: índice de material fora dos slots")
    for material in bpy.data.materials:
        if material.users and material.node_tree:
            for node in material.node_tree.nodes:
                if node.bl_idname == "ShaderNodeTexImage" and node.image and node.image.packed_file is None:
                    problems.append(f"{material.name}: imagem {node.image.name} não empacotada")
                if node.bl_idname == "ShaderNodeTexImage" and node.interpolation != "Closest":
                    problems.append(f"{material.name}: interpolação {node.interpolation}")
    names = [o.name for o in scene.objects]
    if len(names) != len(set(names)):
        problems.append("nomes de objeto repetidos")
    for name in names:
        if re.search(r"\.\d{3}$", name):
            problems.append(f"{name}: sufixo automático do Blender")
    return problems


def check_lights(scene):
    problems = []
    lights = [o for o in scene.objects if o.type == "LIGHT" and re.match(r"Light_.+_p\d+$", o.name)]
    if not 5 <= len(lights) <= MAX_PART_LIGHTS:
        problems.append(f"{len(lights)} luzes de peças")
    for light in lights:
        for key in (C.P_ROOM, C.P_LIGHT_ENERGY, C.P_LIGHT_FLICKER, C.P_LIGHT_KIND):
            if key not in light:
                problems.append(f"{light.name}: sem {key}")
        if light.data.use_shadow:
            problems.append(f"{light.name}: com sombra")
        room = layout.room_at(*light.matrix_world.translation)
        if room is None or room.id != light.get(C.P_ROOM):
            problems.append(f"{light.name}: fora do cômodo declarado")
    for required in ("Light_living_p1", "Light_master_p1", "Light_kids_p1", "Light_garage_p1"):
        if required not in scene.objects:
            problems.append(f"{required} ausente")
    return problems


def check_car_and_viewmodel(scene):
    problems = []
    car = scene.objects.get(C.OBJ_CAR)
    if car is None or car.type != "EMPTY":
        return ["Car ausente"]
    anchor = layout.ANCHORS["car"]
    if (Vector(car.location) - Vector(anchor.pos)).length > 1e-4:
        problems.append("Car fora da âncora")
    for wheel in ("FL", "FR", "RL", "RR"):
        obj = scene.objects.get(f"Car_Wheel_{wheel}")
        if obj is None or obj.parent is not car:
            problems.append(f"Car_Wheel_{wheel} ausente ou sem pai")
    for side in ("L", "R"):
        lamp = scene.objects.get(f"Car_Headlight_{side}")
        if lamp is None or lamp.type != "LIGHT" or lamp.data.type != "SPOT" or lamp.data.energy != 0:
            problems.append(f"Car_Headlight_{side} deve ser SPOT desligado")
    eye = scene.objects.get("Car_DriverEye")
    if eye is None or (eye.matrix_world.translation - Vector(layout.ANCHORS["car_driver_eye"].pos)).length > 1e-3:
        problems.append("Car_DriverEye fora da âncora")
    interact = scene.objects.get("Car_Interact")
    if interact is None or interact.get(C.P_INTERACT) != "car" or interact.get(C.P_PROMPT) != story.PROMPT_CAR:
        problems.append("Car_Interact sem sa_interact/sa_prompt")
    elif math.hypot(interact.matrix_world.translation.x - layout.ANCHORS["car_interact"].x,
                    interact.matrix_world.translation.y - layout.ANCHORS["car_interact"].y) > 1e-3:
        problems.append("Car_Interact fora da âncora em XY")
    viewmodel = scene.objects.get(C.OBJ_VIEW_FLASH)
    if viewmodel is None:
        problems.append("ViewModel_Flashlight ausente")
    else:
        zs = [v.co.z for v in viewmodel.data.vertices]
        if not (viewmodel.hide_viewport and viewmodel.hide_render):
            problems.append("ViewModel_Flashlight deve estar oculto")
        if min(zs) > -0.15 or max(zs) < 0.03:
            problems.append(f"ViewModel_Flashlight: cano deveria apontar para -Z (z de {min(zs):.2f} a {max(zs):.2f})")
    return problems


def check_idempotent(scene, ctx):
    before = sorted(o.name for o in scene.objects)
    props.build(ctx)
    after = sorted(o.name for o in scene.objects)
    return [] if before == after else [f"build não idempotente: {len(before)} -> {len(after)} objetos"]


def main():
    scene, ctx = build_scene()
    problems = []
    problems += check_items(scene)
    problems += check_anchors(scene)
    problems += [f"planta: {p}" for p in placement.validate_layout(scene)]
    problems += check_collision(scene)
    problems += check_budget(scene)
    problems += check_materials_and_names(scene)
    problems += check_lights(scene)
    problems += check_car_and_viewmodel(scene)
    problems += check_idempotent(scene, ctx)
    for line in problems:
        print("FALHA:", line)
    print("props OK" if not problems else f"{len(problems)} problema(s)")
    return 1 if problems else 0


def test_props_layout():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
