"""Colocação dos itens coletáveis e das sete notas na casa.

Os modelos (chave, pilhas, mapa, notas, lanterna) ficam em `item_models.py` e `flashlight.py`.

Cada item nasce com a origem no centro visual e é apoiado na superfície informada (`rest_z`) pelo
ponto mais baixo da malha. As notas presas na parede (caderno na cortiça, post-it no frigobar)
são construídas de pé, com a frente em +Y, e giradas para o cômodo.
"""
import math

import bpy

from .. import conventions as C
from .. import layout, story
from . import kitchen
from .flashlight import build_item_mesh
from .item_models import (build_battery_pair, build_key, build_map, build_note_clipping, build_note_drawing,
                          build_note_letter, build_note_notebook, build_note_postit, build_note_prescription,
                          build_note_tow_slip)

REST_CLEARANCE = 0.012      # folga sob o item: o raio da interação não pode nascer dentro de uma malha


# ---------------------------------------------------------------------------
# Colocação
# ---------------------------------------------------------------------------
# id -> (construtor, x, y, z da superfície, yaw em graus, modo). z é a superfície onde o item repousa;
# no modo 'wall' é o centro do item, já na altura em que fica preso.
def _placements():
    fridge_x, fridge_y, fridge_z = kitchen.mini_fridge_front()
    return {
        "FLASHLIGHT": (build_item_mesh, 0.40, 6.08, 2.8 + 0.55, 0.0, "rest"),
        "KEY": (build_key, 2.00, 9.32, 0.76, 70.0, "rest"),
        "MAP": (build_map, 10.60, 9.42, 2.8 + 0.76 + 0.021, 8.0, "rest"),
        "BATTERY_1": (build_battery_pair, 0.62, 0.30, 0.5 + 2.8, 15.0, "rest"),
        "BATTERY_2": (build_battery_pair, 9.32, 4.70, 2.8 + 0.90, 100.0, "rest"),
        "BATTERY_3": (build_battery_pair, 4.285, 3.50, 0.30, 35.0, "rest"),
        "BATTERY_4": (build_battery_pair, 11.02, 9.55, kitchen.COUNTER_HEIGHT, 80.0, "rest"),
        "BATTERY_5": (build_battery_pair, 18.05, 2.66, 0.90, 10.0, "rest"),
        "NOTE_1": (build_note_letter, 0.56, 8.86, 2.8 + 0.55, 90.0, "rest"),
        "NOTE_2": (build_note_drawing, 1.35, 3.90, 2.8 + 0.44, -90.0 + 6.0, "rest"),
        "NOTE_3": (build_note_clipping, 3.05, 4.15, 0.422, 35.0, "rest"),
        "NOTE_4": (build_note_notebook, 0.1795, 9.42, 1.5, -90.0, "wall"),     # na frente da cortiça (face em x=0.173)
        "NOTE_5": (build_note_postit, fridge_x + 0.004, fridge_y + 0.05, fridge_z + 0.12, -90.0, "wall"),
        "NOTE_6": (build_note_prescription, 11.62, 6.72, 2.8 + 0.78, 20.0, "rest"),
        "NOTE_7": (build_note_tow_slip, 15.2, 6.68, 1.005, 12.0, "rest"),
    }


def _prompt(item_id, kind):
    if kind == C.ITEM_NOTE:
        return f"{story.ITEM_PROMPTS[kind]}: {story.NOTES[item_id][0]}"
    return story.ITEM_PROMPTS[kind]


def _create_item(ctx, item_id, builder, x, y, z, yaw_deg, mode):
    kind = item_id.split("_")[0]
    mesh_builder = builder()
    mesh_builder.name = C.N_ITEM + item_id
    if mode == "rest":
        z += REST_CLEARANCE - mesh_builder.bounds()[0][2]
    obj = bpy.data.objects.new(C.N_ITEM + item_id, mesh_builder.to_mesh(C.N_ITEM + item_id))
    obj.location = (x, y, z)
    obj.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    obj[C.P_INTERACT] = "note" if kind == C.ITEM_NOTE else "item"
    obj[C.P_ITEM] = kind
    obj[C.P_ID] = item_id
    obj[C.P_PROMPT] = _prompt(item_id, kind)
    obj[C.P_ROOM] = layout.ITEM_SPOTS[item_id][0]
    obj["sa_mount"] = mode
    if kind == C.ITEM_NOTE:
        obj["sa_title"] = story.NOTES[item_id][0]
    ctx.link(obj, C.COL_ITEMS)
    return obj


def make_items(ctx):
    """Cria os 15 itens (lanterna, chave, mapa, 5 pilhas, 7 notas) e devolve os objetos."""
    return [_create_item(ctx, item_id, *spec) for item_id, spec in _placements().items()]
