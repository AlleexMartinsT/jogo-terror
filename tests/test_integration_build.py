"""Integração: constrói o jogo inteiro e confere se as costuras do contrato fecham.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_integration_build.py

O que este teste pega e os testes de cada módulo não: um módulo criar `Item_KEY` num
lugar diferente do que o engine espera, uma textura que some ao salvar o .blend, etc.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from sem_alvorada import build, layout  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402

OUT = os.path.join(ROOT, "out", "integration")
BLEND = os.path.join(OUT, "full.blend")


def triangle_count(objs):
    total = 0
    for ob in objs:
        if ob.type == "MESH":
            total += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    return total


def check_scene_contract(scene):
    problems = []
    names = {ob.name for ob in scene.objects}

    def need(name):
        if name not in names:
            problems.append(f"objeto ausente: {name}")

    for col in (C.COL_WORLD, C.COL_PROPS, C.COL_ITEMS, C.COL_ENTITY, C.COL_PLAYER):
        if col not in bpy.data.collections:
            problems.append(f"coleção ausente: {col}")

    for item_id in layout.ITEM_SPOTS:
        need(C.N_ITEM + item_id)
    for door in layout.doors():
        need(C.N_DOOR + door.id)
    for name in layout.ANCHORS:
        need(C.N_ANCHOR + name)
    for op in layout.windows():
        need(C.N_WINDOW + op.id)
    for room, spots in layout.CEILING_LIGHTS.items():
        for n in range(len(spots)):
            need(f"{C.N_LIGHT}{room}_c{n}")
    for name in (C.OBJ_PLAYER_CAM, C.OBJ_FLASHLIGHT, C.OBJ_VIEW_FLASH, C.OBJ_ENTITY, C.OBJ_CUT_CAM,
                 C.OBJ_CAR, C.OBJ_GARAGE_ROLLUP, "Entity_Rig", "Entity_Body", "Entity_Eyes",
                 "Car_DriverEye", "Car_Interact", "Stairs_Main"):
        need(name)

    for door in layout.doors():
        pivot = scene.objects.get(C.N_DOOR + door.id)
        if pivot is None:
            continue
        for prop in (C.P_ID, C.P_INTERACT, C.P_DOOR_CLOSED, C.P_DOOR_OPEN, C.P_LOCK):
            if prop not in pivot:
                problems.append(f"{pivot.name} sem {prop}")
        if pivot.get(C.P_LOCK, "") != door.lock:
            problems.append(f"{pivot.name}: lock {pivot.get(C.P_LOCK)!r} != {door.lock!r}")

    batteries = [ob for ob in scene.objects if ob.get(C.P_ITEM) == C.ITEM_BATTERY]
    if len(batteries) != C.N_BATTERIES_IN_HOUSE:
        problems.append(f"{len(batteries)} pilhas na cena, esperado {C.N_BATTERIES_IN_HOUSE}")
    notes = [ob for ob in scene.objects if ob.get(C.P_ITEM) == C.ITEM_NOTE]
    if len(notes) != C.N_NOTES:
        problems.append(f"{len(notes)} notas, esperado {C.N_NOTES}")

    for item_id, (room, x, y, z, _) in layout.ITEM_SPOTS.items():
        item = scene.objects.get(C.N_ITEM + item_id)
        if item is None:
            continue
        gx, gy, gz = item.matrix_world.translation
        if abs(gx - x) > 1.2 or abs(gy - y) > 1.2:
            problems.append(f"{item.name} a {abs(gx - x):.1f}/{abs(gy - y):.1f} m do ponto previsto")
        found = layout.room_at(gx, gy, gz)
        if found is None or found.id != room:
            problems.append(f"{item.name} caiu fora de {room}: {found.id if found else None}")

    colliders = [ob for ob in scene.objects if ob.get(C.P_COL)]
    if len(colliders) < 10:
        problems.append(f"poucos objetos de colisão: {len(colliders)}")

    for text_name in ("SA_NAV", "SA_AUDIO_MANIFEST"):
        if text_name not in bpy.data.texts:
            problems.append(f"Text ausente: {text_name}")

    visible = [ob for ob in scene.objects if not ob.hide_render]
    tris = triangle_count(visible)
    print(f"[integração] {len(scene.objects)} objetos, {tris} triângulos visíveis, "
          f"{len(bpy.data.images)} imagens, {len(bpy.data.materials)} materiais")
    if tris > 260_000:
        problems.append(f"triângulos demais: {tris}")
    return problems


def check_saved_file():
    """Reabre o .blend num interpretador novo: texturas geradas por código precisam ter sido empacotadas."""
    probe = (
        "import bpy; bpy.ops.wm.open_mainfile(filepath=r'%s'); "
        "bad=[i.name for i in bpy.data.images if i.source in ('GENERATED','FILE') and i.name!='Render Result' "
        "and (i.packed_file is None) and not i.filepath]; "
        "print('IMAGENS_SEM_PACOTE=' + ','.join(bad))" % BLEND
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=300).stdout
    line = next((l for l in out.splitlines() if l.startswith("IMAGENS_SEM_PACOTE=")), "IMAGENS_SEM_PACOTE=?")
    missing = line.split("=", 1)[1]
    return [f"imagens não empacotadas: {missing}"] if missing not in ("", "?") else (
        ["não consegui reabrir o .blend salvo"] if missing == "?" else [])


def main():
    os.makedirs(OUT, exist_ok=True)
    failures = build.run(out=BLEND)
    problems = [f"etapa '{name}' falhou: {err}" for name, err in failures]
    problems += check_scene_contract(bpy.context.scene)
    problems += check_saved_file()
    for line in problems:
        print("FALHA:", line)
    print("integração OK" if not problems else f"{len(problems)} problema(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
