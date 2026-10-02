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
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import build, layout, props, story  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.props import placement  # noqa: E402

MAX_PROP_TRIS = C.BUDGET_TRIS["hero_prop"]
MAX_CAR_TRIS = C.BUDGET_TRIS["car"]
MAX_TOTAL_TRIS = C.BUDGET_TRIS["props_total"]
MAX_PART_LIGHTS = 13
ITEM_DISTANCE_LIMIT = 1.2
REST_TOLERANCE = 0.03       # distância máxima entre o ponto mais baixo de um item/enfeite e a superfície


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
    """Apoiado: há superfície dentro de REST_TOLERANCE do ponto mais baixo (ou ele está no piso do andar)."""
    lowest = min((obj.matrix_world @ Vector(v.co)).z for v in obj.data.vertices)
    if min(abs(lowest - z) for z in layout.LEVEL_Z.values()) < REST_TOLERANCE:
        return True
    x, y, _ = obj.matrix_world.translation
    obj.hide_viewport = True
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    # o raio nasce um pouco acima do ponto mais baixo: enfeites que afundam 4 mm no tampo também contam
    hit = scene.ray_cast(depsgraph, Vector((x, y, lowest + 0.02)), Vector((0, 0, -1)), distance=0.02 + REST_TOLERANCE)[0]
    obj.hide_viewport = False
    bpy.context.view_layer.update()
    return hit


def segment_hits_box(start, end, lo, hi):
    """Interseção segmento x caixa alinhada aos eixos (método das lajes), em coordenadas locais da caixa."""
    t_near, t_far = 0.0, 1.0
    for axis in range(3):
        delta = end[axis] - start[axis]
        if abs(delta) < 1e-9:
            if not lo[axis] <= start[axis] <= hi[axis]:
                return False
            continue
        t0, t1 = (lo[axis] - start[axis]) / delta, (hi[axis] - start[axis]) / delta
        t_near, t_far = max(t_near, min(t0, t1)), min(t_far, max(t0, t1))
        if t_near > t_far:
            return False
    return True


def check_items_clear_of_collision(scene):
    """Nenhum item pode ficar dentro de um proxy COL_ nem ter o proxy entre ele e quem olha a 0,8 m."""
    problems = []
    proxies = [o for o in scene.objects if o.name.startswith(C.N_COL)]
    boxes = []
    for proxy in proxies:
        xs, ys, zs = zip(*(v.co for v in proxy.data.vertices))
        boxes.append((proxy, proxy.matrix_world.inverted(), (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))))
    for obj in scene.objects:
        if not obj.name.startswith(C.N_ITEM):
            continue
        center = obj.matrix_world.translation
        room = layout.ROOMS[obj[C.P_ROOM]]
        to_center = Vector((room.rect.center[0] - center.x, room.rect.center[1] - center.y, 0.0))
        to_center = to_center.normalized() if to_center.length > 0.01 else Vector((0.0, -1.0, 0.0))
        eye = center + to_center * 0.8
        eye.z = layout.LEVEL_Z[room.level] + C.PLAYER_EYE_STAND
        for proxy, to_local, lo, hi in boxes:
            local_center, local_eye = to_local @ center, to_local @ eye
            if all(lo[i] <= local_center[i] <= hi[i] for i in range(3)):
                problems.append(f"{obj.name}: dentro do volume de {proxy.name}")
            elif segment_hits_box(local_eye, local_center, lo, hi):
                problems.append(f"{obj.name}: {proxy.name} bloqueia a linha de visada a 0,8 m")
    return problems


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
        if (proxy.matrix_world.translation - proxy.location).length > 1e-4:
            problems.append(f"{proxy.name}: matrix_world desatualizada (objeto oculto não é avaliado)")
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


def check_decor_supported(scene):
    """Todo enfeite pequeno (xícara, abajur, telefone, porta-retrato) precisa ter superfície logo abaixo."""
    problems = []
    for obj in placement.prop_objects(scene):
        if obj[placement.P_MODE] != "decor":
            continue
        if not rests_on_surface(scene, obj):
            problems.append(f"{obj.name}: flutuando em {tuple(round(c, 2) for c in obj.location)}")
    return problems


GRID_STEP = 0.1
GRID_W, GRID_H = int(19.0 / GRID_STEP), int(10.0 / GRID_STEP)
STAIR_LINK = ((5.6, 2.8), (5.6, 7.9))       # sopé da escada (térreo) e patamar de cima (andar 1)


def walkable_grid(scene, level):
    """Grade booleana (True = o centro do jogador cabe) com paredes e proxies de colisão inflados pelo raio."""
    xs = (np.arange(GRID_W) + 0.5) * GRID_STEP
    ys = (np.arange(GRID_H) + 0.5) * GRID_STEP
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    free = np.zeros(gx.shape, bool)
    for room in layout.rooms_on_level(level):
        rc = room.rect
        free |= (gx >= rc.x0) & (gx <= rc.x1) & (gy >= rc.y0) & (gy <= rc.y1)
    radius = C.PLAYER_RADIUS
    for wall in layout.solid_rects(level):
        near_x = np.maximum(np.maximum(wall.x0 - gx, gx - wall.x1), 0.0)
        near_y = np.maximum(np.maximum(wall.y0 - gy, gy - wall.y1), 0.0)
        free &= np.hypot(near_x, near_y) >= radius
    if level == 1:
        hole = layout.STAIRS.hole
        near_x = np.maximum(np.maximum(hole.x0 - gx, gx - hole.x1), 0.0)
        near_y = np.maximum(np.maximum(hole.y0 - gy, gy - hole.y1), 0.0)
        free &= np.hypot(near_x, near_y) >= 0.05
    floor = layout.LEVEL_Z[level]
    for proxy in (o for o in scene.objects if o.name.startswith(C.N_COL)):
        if layout.level_of_z(proxy.location.z + 0.01) != level or proxy.location.z < floor - 0.1:
            continue
        xs_local, ys_local, _ = zip(*(v.co for v in proxy.data.vertices))
        cos_a, sin_a = math.cos(proxy.rotation_euler.z), math.sin(proxy.rotation_euler.z)
        dx, dy = gx - proxy.location.x, gy - proxy.location.y
        local_x, local_y = dx * cos_a + dy * sin_a, -dx * sin_a + dy * cos_a
        near_x = np.maximum(np.maximum(min(xs_local) - local_x, local_x - max(xs_local)), 0.0)
        near_y = np.maximum(np.maximum(min(ys_local) - local_y, local_y - max(ys_local)), 0.0)
        free &= np.hypot(near_x, near_y) >= radius
    return free


def reachable_cells(grids, start):
    """Flood fill em (andar, ix, iy); a escada liga o sopé ao patamar."""
    def cell(level, xy):
        return level, int(xy[0] / GRID_STEP), int(xy[1] / GRID_STEP)

    link_a, link_b = cell(0, STAIR_LINK[0]), cell(1, STAIR_LINK[1])
    seen, queue = {start}, deque([start])
    while queue:
        level, ix, iy = queue.popleft()
        steps = [(level, ix + dx, iy + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        if (level, ix, iy) == link_a:
            steps.append(link_b)
        elif (level, ix, iy) == link_b:
            steps.append(link_a)
        for nxt in steps:
            lv, nx, ny = nxt
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H and nxt not in seen and grids[lv][nx, ny]:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def check_reachability(scene):
    """Com a mobília no lugar o jogador ainda chega a todos os cômodos, portas, à escada e a cada item."""
    problems = []
    grids = {level: walkable_grid(scene, level) for level in (0, 1)}
    sx, sy, sz = layout.PLAYER_START
    start = (layout.level_of_z(sz), int(sx / GRID_STEP), int(sy / GRID_STEP))
    if not grids[start[0]][start[1], start[2]]:
        return ["PLAYER_START bloqueado pela mobília"]
    seen = reachable_cells(grids, start)
    for link_xy, level in ((STAIR_LINK[0], 0), (STAIR_LINK[1], 1)):
        if (level, int(link_xy[0] / GRID_STEP), int(link_xy[1] / GRID_STEP)) not in seen:
            problems.append(f"escada inalcançável em {link_xy}")
    for room in layout.ROOMS.values():
        if not any(c[0] == room.level and room.rect.contains((c[1] + 0.5) * GRID_STEP, (c[2] + 0.5) * GRID_STEP, -0.3)
                   for c in seen):
            problems.append(f"cômodo inalcançável: {room.id}")
    for opening in layout.doors():
        mx, my = opening.mid
        if not any(c[0] == opening.level and math.hypot((c[1] + 0.5) * GRID_STEP - mx, (c[2] + 0.5) * GRID_STEP - my) < 0.5
                   for c in seen):
            problems.append(f"porta bloqueada: {opening.id}")
    reach = C.INTERACT_RANGE - 0.4
    for obj in scene.objects:
        if not obj.name.startswith(C.N_ITEM):
            continue
        x, y, z = obj.matrix_world.translation
        level = layout.level_of_z(z)
        if not any(c[0] == level and math.hypot((c[1] + 0.5) * GRID_STEP - x, (c[2] + 0.5) * GRID_STEP - y) <= reach
                   for c in seen):
            problems.append(f"{obj.name}: nenhum ponto alcançável a menos de {reach:.1f} m")
    car = layout.ANCHORS["car_interact"]
    if not any(c[0] == 0 and math.hypot((c[1] + 0.5) * GRID_STEP - car.x, (c[2] + 0.5) * GRID_STEP - car.y) < 0.4 for c in seen):
        problems.append("ponto de interação do carro inalcançável")
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
                if node.bl_idname == "ShaderNodeTexImage" and node.interpolation not in ("Linear", "Closest"):
                    problems.append(f"{material.name}: interpolação {node.interpolation}")
                if node.bl_idname == "ShaderNodeTexImage" and node.image and \
                        node.image.size[0] * node.image.size[1] > 512 * 512:
                    problems.append(f"{material.name}: textura {tuple(node.image.size)} acima de 512x512 px em área")
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
        if min(zs) > -0.12 or max(zs) < 0.03:        # cano de pelo menos 12 cm à frente do punho; antebraço atrás
            problems.append(f"ViewModel_Flashlight: cano deveria apontar para -Z (z de {min(zs):.2f} a {max(zs):.2f})")
    return problems


def check_idempotent(scene, ctx, reference):
    """Reconstruir na mesma cena não duplica nada e devolve exatamente a mesma geometria."""
    props.build(ctx)
    bpy.context.view_layer.update()
    again = scene_signature(scene)
    differing = sorted(name for name in reference.keys() | again.keys() if reference.get(name) != again.get(name))
    return [f"build não idempotente: {differing[:5]}"] if differing else []


def scene_signature(scene):
    """Contagem de vértices, soma ponderada das coordenadas e posição de cada objeto."""
    signature = {}
    for obj in scene.objects:
        if obj.type == "MESH":
            signature[obj.name] = (len(obj.data.vertices),
                                   round(sum(v.co.x + 2 * v.co.y + 3 * v.co.z for v in obj.data.vertices), 4))
        signature[obj.name + ":local"] = tuple(round(c, 4) for c in obj.location)
    return signature


def check_deterministic(first):
    """Duas construções do zero com a mesma semente têm de produzir exatamente a mesma cena."""
    second_scene, _ = build_scene()
    second = scene_signature(second_scene)
    differing = sorted(name for name in first.keys() | second.keys() if first.get(name) != second.get(name))
    return [f"construção não determinística: {differing[:5]}"] if differing else []


def main():
    scene, ctx = build_scene()
    reference = scene_signature(scene)
    problems = []
    problems += check_items(scene)
    problems += check_items_clear_of_collision(scene)
    problems += check_anchors(scene)
    problems += [f"planta: {p}" for p in placement.validate_layout(scene)]
    problems += check_collision(scene)
    problems += check_reachability(scene)
    problems += check_decor_supported(scene)
    problems += check_budget(scene)
    problems += check_materials_and_names(scene)
    problems += check_lights(scene)
    problems += check_car_and_viewmodel(scene)
    problems += check_idempotent(scene, ctx, reference)
    problems += check_deterministic(reference)        # por último: reconstruir do zero invalida a cena atual
    for line in problems:
        print("FALHA:", line)
    print("props OK" if not problems else f"{len(problems)} problema(s)")
    return 1 if problems else 0


def test_props_layout():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
