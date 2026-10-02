"""Teste dos cômodos de cima (quartos, banheiro, escritório e corredor) isolados do resto da casa.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_props_quartos.py

Constrói só `master, kids, bath, study, hall_u` mais os itens e confere o que importa para o jogo: os itens
coletáveis ficam em cima de superfícies reais e fora dos proxies; as âncoras do quarto, da pia e do escritório
continuam no lugar; a mobília cabe nos cômodos, não invade zonas reservadas e deixa tudo alcançável; o
orçamento de triângulos fecha; os materiais têm textura linear e empacotada; e a construção é determinística
(pano simulado inclusive).
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ["SA_ROOMS"] = "master,kids,bath,study,hall_u,items"

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import test_props_layout as shared  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.props import placement  # noqa: E402

ROOMS = ("master", "kids", "bath", "study", "hall_u")
MY_ITEMS = ("FLASHLIGHT", "MAP", "BATTERY_1", "BATTERY_2", "NOTE_1", "NOTE_2", "NOTE_6")
MY_ANCHORS = ("bed_master", "nightstand_flash", "nightstand_clock", "kids_bed", "bath_sink", "study_desk")
ROOMS_BUDGET = 190_000          # soma dos cinco cômodos, com itens fora da conta
MIN_SMALL_PIECES = 12


def my_objects(scene):
    return [o for o in scene.objects if o.type == "MESH" and o.get(C.P_ROOM) in ROOMS and not o.name.startswith((C.N_COL, C.N_ITEM))]


def check_items(scene):
    problems = []
    for item_id in MY_ITEMS:
        obj = scene.objects.get(C.N_ITEM + item_id)
        if obj is None:
            problems.append(f"item ausente: {item_id}")
            continue
        if not shared.rests_on_surface(scene, obj):
            problems.append(f"{obj.name}: flutuando")
    mine = {name for name in (C.N_ITEM + i for i in MY_ITEMS)}
    problems += [p for p in shared.check_items_clear_of_collision(scene) if p.split(":")[0] in mine]
    return problems


def check_anchors(scene):
    """Cada âncora do território tem um móvel exatamente na posição e no yaw do layout (os Empties vêm de outra etapa)."""
    problems = []
    for name in MY_ANCHORS:
        anchor = layout.ANCHORS[name]
        owners = [o for o in scene.objects if o.get(placement.P_ANCHOR) == name and o.type == "MESH"]
        if not owners:
            problems.append(f"âncora {name} sem móvel")
        for owner in owners:
            if (owner.location - Vector(anchor.pos)).length > 1e-4 or abs(owner.rotation_euler.z - math.radians(anchor.yaw_deg)) > 1e-4:
                problems.append(f"{owner.name}: fora da âncora {name}")
    return problems


def check_layout(scene):
    problems = []
    for problem in placement.validate_layout(scene):
        obj = scene.objects.get(problem.split(":")[0].split(" ")[0])
        if obj is not None and obj.get(C.P_ROOM) in ROOMS:
            problems.append(f"planta: {problem}")
    return problems


def check_collision(scene):
    """As verificações compartilhadas, ignorando âncoras de outros territórios (o carro, a cozinha...)."""
    foreign = [name for name in layout.ANCHORS if name not in MY_ANCHORS]
    return [p for p in shared.check_collision(scene) if not any(f"âncora {name} " in p for name in foreign)]


def check_reachability(scene):
    return [p for p in shared.check_reachability(scene) if "carro" not in p]


def check_budget(scene):
    problems = []
    total = 0
    for obj in my_objects(scene):
        count = shared.triangles(obj)
        total += count
        limit = C.BUDGET_TRIS["hero_prop"] if obj.name in ("bed_master", "wardrobe_master") else C.BUDGET_TRIS["prop"]
        if count > limit:
            problems.append(f"{obj.name}: {count} triângulos (limite {limit})")
    print(f"[quartos] triângulos dos cinco cômodos: {total}")
    if total > ROOMS_BUDGET:
        problems.append(f"cômodos de cima somam {total} triângulos (limite {ROOMS_BUDGET})")
    return problems


def check_small_pieces(scene):
    small = [o for o in my_objects(scene) if o.get(placement.P_MODE) in ("decor", "wall") and o.get("sa_height", 1.0) < 0.5]
    print(f"[quartos] peças pequenas de ambientação: {len(small)}")
    return [] if len(small) >= MIN_SMALL_PIECES else [f"só {len(small)} peças pequenas (mínimo {MIN_SMALL_PIECES})"]


def check_materials(scene):
    problems = []
    for material in bpy.data.materials:
        if not (material.users and material.node_tree and material.name.startswith("up_")):
            continue
        for node in material.node_tree.nodes:
            if node.bl_idname != "ShaderNodeTexImage":
                continue
            if node.image is None or node.image.packed_file is None and node.image.source != "GENERATED":
                problems.append(f"{material.name}: imagem sem pacote")
            if node.interpolation != "Linear":
                problems.append(f"{material.name}: interpolação {node.interpolation} (esperado Linear)")
            if min(node.image.size) < 128:
                problems.append(f"{material.name}: textura de {tuple(node.image.size)} px")
    for obj in my_objects(scene):
        if not len(obj.data.materials) or any(m is None for m in obj.data.materials):
            problems.append(f"{obj.name}: material ausente")
    return problems


def check_lights_in_rooms(scene):
    problems = []
    for light in (o for o in scene.objects if o.type == "LIGHT" and "_p" in o.name):
        room = layout.room_at(*light.matrix_world.translation)
        if room is None or room.id != light.get(C.P_ROOM):
            problems.append(f"{light.name}: fora do cômodo declarado")
    return problems


def main():
    scene, ctx = shared.build_scene()
    reference = shared.scene_signature(scene)
    problems = []
    problems += check_items(scene)
    problems += check_anchors(scene)
    problems += check_layout(scene)
    problems += check_collision(scene)
    problems += shared.check_decor_supported(scene)
    problems += check_reachability(scene)
    problems += check_budget(scene)
    problems += check_small_pieces(scene)
    problems += check_materials(scene)
    problems += check_lights_in_rooms(scene)
    problems += shared.check_idempotent(scene, ctx, reference)
    problems += shared.check_deterministic(reference)
    for line in problems:
        print("FALHA:", line)
    print("quartos OK" if not problems else f"{len(problems)} problema(s)")
    return 1 if problems else 0


def test_props_quartos():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
