"""Sala, escritório de baixo, hall e sala de jantar: confere o que o jogo e a história usam desses cômodos.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_props_sala.py

Constrói só esses quatro cômodos (mais itens e âncoras) e checa: planta (dentro do cômodo, fora das zonas
reservadas), superfícies que sustentam os itens (gaveta, escrivaninha, mesinha, cortiça), âncoras exatas,
a TV com o nó `StaticMapping` e a luz de chiado, orçamento de triângulos, apoio dos enfeites e determinismo.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ["SA_ROOMS"] = "living,den,hall_g,dining,items"

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import test_props_layout as layout_checks  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.props import placement  # noqa: E402

ROOMS = {"living", "den", "hall_g", "dining"}
BUDGET_ROOMS_TOTAL = 260_000
SURFACE_TOLERANCE = 0.012           # o item repousa a 1,2 cm acima da superfície que o sustenta


def mine(scene):
    """Objetos de mobília e enfeite dos quatro cômodos."""
    return [o for o in placement.prop_objects(scene) if o.get(C.P_ROOM) in ROOMS]


def top_z_under(scene, point, ignore):
    """Altura da superfície logo abaixo de `point` (raio para baixo ignorando o próprio objeto)."""
    ignore.hide_viewport = True
    bpy.context.view_layer.update()
    hit = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), point + Vector((0, 0, 0.05)), Vector((0, 0, -1)), distance=0.5)
    ignore.hide_viewport = False
    bpy.context.view_layer.update()
    return hit[1].z if hit[0] else None


def check_item_surfaces(scene):
    """As quatro superfícies do jogo mantêm a altura: gaveta 0,30, escrivaninha 0,76, mesinha 0,42, cortiça perto da parede."""
    expected = {"BATTERY_3": 0.30, "KEY": 0.76, "NOTE_3": 0.42}
    problems = []
    for item_id, height in expected.items():
        item = scene.objects[C.N_ITEM + item_id]
        under = top_z_under(scene, item.matrix_world.translation, item)
        if under is None or abs(under - height) > 0.02:
            problems.append(f"{item.name}: superfície em {under} (esperado {height})")
        low = min((item.matrix_world @ Vector(v.co)).z for v in item.data.vertices)
        if under is not None and not 0.0 <= low - under <= SURFACE_TOLERANCE + 0.02:
            problems.append(f"{item.name}: a {low - under:.3f} m da superfície")
    note = scene.objects[C.N_ITEM + "NOTE_4"]
    board = scene.objects.get("cork_board_den")
    if board is None:
        problems.append("quadro de cortiça ausente")
    elif abs(note.matrix_world.translation.y - board.location.y) > 0.4 or abs(note.matrix_world.translation.z - 1.5) > 0.3:
        problems.append("NOTE_4 fora do quadro de cortiça")
    return problems


def check_anchors_exact(scene):
    problems = []
    for name in ("tv_living", "sofa_living", "grandfather_clock", "desk_den"):
        anchor = layout.ANCHORS[name]
        owners = [o for o in scene.objects if o.get(placement.P_ANCHOR) == name]
        if not owners:
            problems.append(f"âncora {name} sem móvel")
        for owner in owners:
            if (Vector(owner.location) - Vector(anchor.pos)).length > 1e-4:
                problems.append(f"{owner.name}: fora da âncora")
            if abs(owner.rotation_euler.z - math.radians(anchor.yaw_deg)) > 1e-4:
                problems.append(f"{owner.name}: yaw diferente da âncora")
    return problems


def check_tv(scene):
    problems = []
    screens = [m for m in bpy.data.materials if m.node_tree and m.node_tree.nodes.get("StaticMapping")]
    if not screens:
        problems.append("nenhum material com StaticMapping (o engine anima o chiado por ele)")
    light = scene.objects.get("Light_living_p1")
    if light is None:
        problems.append("Light_living_p1 ausente")
    elif (light.location - Vector((4.15, 3.9, 0.85))).length > 0.01:
        problems.append("Light_living_p1 mudou de lugar")
    tv = scene.objects.get("tv_living")
    if tv is None or not any(m and m.name == "tv_screen" for m in tv.data.materials):
        problems.append("a tela da TV não usa o material tv_screen")
    return problems


def check_room_budget(scene):
    problems = []
    total = 0
    for obj in mine(scene):
        if obj.type != "MESH" or obj.hide_render:
            continue
        count = layout_checks.triangles(obj)
        total += count
        if count > C.BUDGET_TRIS["hero_prop"]:
            problems.append(f"{obj.name}: {count} triângulos")
    print(f"[sala] triângulos dos quatro cômodos: {total}")
    if total > BUDGET_ROOMS_TOTAL:
        problems.append(f"quatro cômodos somam {total} triângulos (limite {BUDGET_ROOMS_TOTAL})")
    return problems


def check_decor_in_rooms(scene):
    problems = []
    for obj in mine(scene):
        if obj[placement.P_MODE] == "decor" and not layout_checks.rests_on_surface(scene, obj):
            problems.append(f"{obj.name}: flutuando em {tuple(round(c, 2) for c in obj.location)}")
    return problems


def check_minimum_ambience(scene):
    """Pelo menos 12 peças pequenas de ambientação (enfeites) nos quatro cômodos."""
    count = sum(1 for o in mine(scene) if o[placement.P_MODE] == "decor")
    return [] if count >= 12 else [f"só {count} peças de ambientação"]


def main():
    scene, ctx = layout_checks.build_scene()
    signature = layout_checks.scene_signature(scene)
    problems = []
    names = {o.name for o in mine(scene)}
    problems += [f"planta: {p}" for p in placement.validate_layout(scene) if p.split(":")[0].split(" ")[0] in names]
    problems += check_item_surfaces(scene)
    problems += layout_checks.check_items_clear_of_collision(scene)
    problems += check_anchors_exact(scene)
    problems += check_tv(scene)
    problems += check_room_budget(scene)
    problems += check_decor_in_rooms(scene)
    problems += check_minimum_ambience(scene)
    problems += layout_checks.check_deterministic(signature)
    for line in problems:
        print("FALHA:", line)
    print("sala OK" if not problems else f"{len(problems)} problema(s)")
    return 1 if problems else 0


def test_props_sala():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
