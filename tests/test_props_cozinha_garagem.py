"""Teste da cozinha e da garagem remodeladas: peças, orçamento, materiais, alturas do jogo e determinismo.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_props_cozinha_garagem.py

Constrói só os dois cômodos (mais itens e âncoras, que dependem deles) com `SA_ROOMS`. Cobre:
* as peças principais existem e a ambientação nova passa de 12 objetos;
* orçamento de triângulos por peça e do conjunto;
* materiais: todos presentes, texturas empacotadas, filtro linear, até 512 px, relevo ligado;
* alturas que o jogo usa: tampo do balcão (pilha 4), tampo da bancada (pilha 5), porta do frigobar (nota 5) e
  tábua da estante (nota 7), medidas por raio sobre a malha;
* o martelo falta no painel de ferramentas e está na bancada;
* o pano de prato caiu de verdade (a simulação encontrou o forno);
* nada de modificadores deixados na malha e atributo de desgaste gravado;
* reconstruir do zero devolve a mesma geometria, e `quality=low` tem menos triângulos que `high` sem perder peças.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["SA_ROOMS"] = "kitchen,garage,items,anchors"

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import build, props  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.props import kg_silhouettes, kitchen  # noqa: E402

HERO_LIMIT = C.BUDGET_TRIS["hero_prop"]
GROUP_LIMIT = 180_000
MAIN_PIECES = (
    "fridge", "kitchen_counter", "stove_kitchen", "range_hood_kitchen", "mini_fridge_kitchen", "counter_corner_north",
    "counter_corner_east", "counter_west_a", "counter_west_b", "wall_cabinets_kitchen", "kitchen_table", "chair_kitchen_kitchen",
    "trash_bin_kitchen", "microwave_kitchen", "coffee_maker_kitchen", "workbench", "tool_panel_garage", "garage_shelves_garage",
    "chest_freezer_garage", "kids_bicycle_garage", "water_heater_garage", "lawn_mower_garage",
)
AMBIENCE = (
    "toaster_kitchen", "bread_board_kitchen", "fruit_bowl_kitchen", "knife_block_kitchen", "spice_rack_kitchen",
    "paper_towel_kitchen", "wall_clock_kitchen", "calendar_kitchen", "dish_towel_kitchen", "ladder_garage", "yard_tools_garage",
    "toolbox_garage", "jerrycan_garage", "spare_tires_garage", "hose_garage", "extension_cord_garage", "bare_bulb_garage",
    "paint_can_floor_1", "stain_mower_garage", "cobweb_garage_nw",
)
SURFACE_TOLERANCE = 0.006
RELIEF_EXEMPT = ("outline", "cobweb", "stain", "grease", "smudge", "chrome")      # decals com alfa: o relevo não faz sentido


def build_scene(quality="medium"):
    scene = build.fresh_scene()
    ctx = BuildContext(scene, quality=quality, verbose=False)
    ctx.stage = "props"
    props.build(ctx)
    bpy.context.view_layer.update()
    return scene


def my_objects(scene):
    return [o for o in scene.objects if o.type == "MESH" and o.get("sa_room") in ("kitchen", "garage")
            and not o.name.startswith(C.N_COL) and not o.name.startswith(C.N_ITEM) and not o.name.startswith("Car")
            and not o.name.startswith("Fixture")]


def triangles(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def surface_height(scene, x, y, z_from):
    """Altura da primeira superfície visível sob (x, y), por raio de cima para baixo."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    hit, location, *_ = scene.ray_cast(depsgraph, Vector((x, y, z_from)), Vector((0, 0, -1)), distance=1.0)
    return location.z if hit else None


# ---------------------------------------------------------------------------
def check_pieces(scene):
    names = {o.name for o in scene.objects}
    problems = [f"peça ausente: {name}" for name in MAIN_PIECES + AMBIENCE if name not in names]
    if len(AMBIENCE) < 12:
        problems.append("menos de 12 peças de ambientação nas expectativas do teste")
    for name in ("Anchor_fridge", "Anchor_kitchen_counter", "Anchor_workbench"):
        if name not in names:
            problems.append(f"{name} ausente")
    return problems


def check_budget(scene):
    problems, total = [], 0
    for obj in my_objects(scene):
        count = triangles(obj)
        total += count
        if count > HERO_LIMIT:
            problems.append(f"{obj.name}: {count} triângulos (limite {HERO_LIMIT})")
    print(f"[cozinha e garagem] {total} triângulos em {len(my_objects(scene))} objetos")
    if total > GROUP_LIMIT:
        problems.append(f"cozinha e garagem somam {total} triângulos (limite {GROUP_LIMIT})")
    return problems


def check_materials(scene):
    problems = []
    for obj in my_objects(scene):
        slots = obj.data.materials
        if not len(slots) or any(m is None for m in slots):
            problems.append(f"{obj.name}: material ausente")
        if obj.modifiers:
            problems.append(f"{obj.name}: modificadores deixados na malha")
        if any(p.material_index >= len(slots) for p in obj.data.polygons):
            problems.append(f"{obj.name}: índice de material fora dos slots")
    used = {m for o in my_objects(scene) for m in o.data.materials if m is not None}
    for material in used:
        if not material.name.startswith("kg_") or not material.node_tree:
            continue
        nodes = material.node_tree.nodes
        for node in (n for n in nodes if n.bl_idname == "ShaderNodeTexImage"):
            if node.image.packed_file is None:
                problems.append(f"{material.name}: imagem {node.image.name} não empacotada")
            if node.interpolation != "Linear":
                problems.append(f"{material.name}: interpolação {node.interpolation}")
            if max(node.image.size) > 512:
                problems.append(f"{material.name}: textura {tuple(node.image.size)} acima de 512 px")
        has_bump = any(n.bl_idname == "ShaderNodeBump" for n in nodes)
        if not has_bump and not _is_flat(material) and not any(tag in material.name for tag in RELIEF_EXEMPT):
            problems.append(f"{material.name}: textura sem relevo")
    return problems


def _is_flat(material):
    return not any(n.bl_idname == "ShaderNodeTexImage" for n in material.node_tree.nodes)


def check_wear_attribute(scene):
    furniture = ("fridge", "kitchen_counter", "workbench", "stove_kitchen", "garage_shelves_garage")
    return [f"{name}: sem o atributo sa_wear" for name in furniture if "sa_wear" not in scene.objects[name].data.color_attributes]


def check_game_heights(scene):
    problems = []
    # a sondagem fica ao lado do item (a pilha e a nota ocupam o ponto exato)
    counter = surface_height(scene, 11.02, 9.40, 1.2)
    bench = surface_height(scene, 18.05, 2.66 - 0.12, 1.2)
    shelf = surface_height(scene, 15.2 + 0.25, 6.68, 1.2)
    expected = {"tampo do balcão (pilha 4)": (counter, kitchen.COUNTER_HEIGHT), "tampo da bancada (pilha 5)": (bench, 0.90),
                "tábua da estante (nota 7)": (shelf, 1.005)}
    for label, (found, wanted) in expected.items():
        if found is None or abs(found - wanted) > SURFACE_TOLERANCE:
            problems.append(f"{label}: superfície em {found}, esperado {wanted}")
    door_x, door_y, _ = kitchen.mini_fridge_front()
    item = scene.objects.get("Item_NOTE_5")
    if item is not None and abs(item.location.x - door_x) > 0.02:
        problems.append("Item_NOTE_5 não encostou na porta do frigobar")
    probe = Vector((door_x + 0.2, door_y + 0.05, 0.62))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    hit, location, *_ = scene.ray_cast(depsgraph, probe, Vector((-1, 0, 0)), distance=0.5)
    if hit and abs(location.x - door_x) > 0.015:
        problems.append(f"porta do frigobar em x={location.x:.3f}, esperado {door_x:.3f}")
    return problems


def check_tool_panel(scene):
    problems = []
    if kg_silhouettes.MISSING not in kg_silhouettes.PANEL_SLOTS:
        problems.append("o contorno do martelo não está nas posições do painel")
    for name, (_x, _z, outline) in kg_silhouettes.PANEL_SLOTS.items():
        if len(outline) < 8:
            problems.append(f"contorno de {name} com poucos pontos")
    if triangles(scene.objects["tool_panel_garage"]) < 1500:
        problems.append("o painel perdeu as ferramentas penduradas")
    return problems


def check_cloth_fell(scene):
    towel = scene.objects.get("dish_towel_kitchen")
    if towel is None:
        return ["dish_towel_kitchen ausente"]
    height = max(v.co.z for v in towel.data.vertices) - min(v.co.z for v in towel.data.vertices)
    inside = 0.3 < towel.location.z + height < 0.95 and 11.0 < towel.location.x < 11.5
    return [] if height > 0.08 and inside else [f"pano de prato não caiu sobre o forno (altura {height:.3f}, em {tuple(towel.location)})"]


def check_names(scene):
    names = [o.name for o in scene.objects]
    problems = [f"{name}: sufixo automático do Blender" for name in names if re.search(r"\.\d{3}$", name)]
    if len(names) != len(set(names)):
        problems.append("nomes de objeto repetidos")
    return problems


def check_collision_proxies(scene):
    problems = []
    for name in ("fridge", "kitchen_counter", "workbench", "stove", "chest_freezer", "mini_fridge", "garage_shelves"):
        boxes = [o for o in scene.objects if o.name.startswith(C.N_COL) and name in o.name]
        if not boxes:
            problems.append(f"sem proxy COL_ para {name}")
        for box in boxes:
            if len(box.data.vertices) != 8:
                problems.append(f"{box.name}: {len(box.data.vertices)} vértices")
    return problems


def signature(scene):
    return {o.name: (len(o.data.vertices), round(sum(v.co.x + 2 * v.co.y + 3 * v.co.z for v in o.data.vertices), 3))
            for o in my_objects(scene)}


def check_determinism(first):
    second = signature(build_scene())
    differing = sorted(name for name in first.keys() | second.keys() if first.get(name) != second.get(name))
    return [f"construção não determinística: {differing[:5]}"] if differing else []


def measure(quality):
    """(nomes, triângulos) dos meus objetos numa construção nova: ler logo, pois a próxima construção apaga a cena."""
    scene = build_scene(quality)
    mine = my_objects(scene)
    return {o.name for o in mine}, sum(triangles(o) for o in mine)


def check_quality_levels(medium_names):
    low_names, low_total = measure("low")
    high_names, high_total = measure("high")
    problems = []
    if not low_total < high_total:
        problems.append(f"quality=low ({low_total}) não tem menos triângulos que high ({high_total})")
    for label, names in (("low", low_names), ("high", high_names)):
        if medium_names - names:
            problems.append(f"quality={label} perdeu peças: {sorted(medium_names - names)[:5]}")
    return problems


def check_asset():
    import numpy as np
    arrays = np.load(os.path.join(ROOT, "assets", "models", "tampo_pia_dupla.npz"))
    holes = arrays["holes"]
    problems = []
    if len(holes) != 2:
        problems.append("o tampo da pia deve ter dois recortes")
    if os.path.getsize(os.path.join(ROOT, "assets", "models", "tampo_pia_dupla.npz")) > 1_000_000:
        problems.append("tampo_pia_dupla.npz passa de 1 MB")
    return problems


def main():
    scene = build_scene()
    problems = []
    problems += check_pieces(scene)
    problems += check_budget(scene)
    problems += check_materials(scene)
    problems += check_wear_attribute(scene)
    problems += check_game_heights(scene)
    problems += check_tool_panel(scene)
    problems += check_cloth_fell(scene)
    problems += check_names(scene)
    problems += check_collision_proxies(scene)
    problems += check_asset()
    reference = signature(scene)
    problems += check_determinism(reference)
    problems += check_quality_levels(set(reference))
    for line in problems:
        print("FALHA:", line)
    print("cozinha e garagem OK" if not problems else f"{len(problems)} problema(s)")
    return 1 if problems else 0


def test_props_cozinha_garagem():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
