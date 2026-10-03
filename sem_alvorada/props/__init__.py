"""Módulo props: mobília, decoração, itens, documentos, carro, viewmodel, âncoras e colisão.

`build(ctx)` é idempotente: apaga o que uma execução anterior criou (objetos dos props, itens,
proxies de colisão, âncoras, luzes de peças) antes de reconstruir.
"""
import os
import random

import bpy

from .. import conventions as C
from . import kit


def _is_props_object(obj):
    name = obj.name
    return (name.startswith((C.N_ANCHOR, C.N_COL, C.N_ITEM, "Car_", "ViewModel_")) or name in (C.OBJ_CAR, "HandFill")
            or "sa_prop_mode" in obj or (name.startswith(C.N_LIGHT) and "_p" in name))


def clear_previous_build():
    """Remove objetos e malhas órfãs de uma construção anterior de props."""
    for obj in [o for o in bpy.data.objects if _is_props_object(o)]:
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(mesh)


def build(ctx):
    """Mobília, itens, carro, viewmodel e âncoras.

    A bagunça usa um gerador próprio derivado da semente: o resultado não depende do que as outras
    etapas sortearam antes, e reconstruir na mesma `ctx` devolve exatamente a mesma cena.
    """
    kit.set_quality(ctx.quality)
    shared_rng, ctx.rng = ctx.rng, random.Random(f"props:{ctx.seed}")
    try:
        _build_all(ctx)
    finally:
        ctx.rng = shared_rng


def _room_builders():
    from . import rooms_lower, rooms_upper
    return {
        "master": rooms_upper.build_master, "kids": rooms_upper.build_kids, "bath": rooms_upper.build_bath,
        "study": rooms_upper.build_study, "hall_u": rooms_upper.build_hall_upper,
        "living": rooms_lower.build_living, "den": rooms_lower.build_den, "hall_g": rooms_lower.build_hall_ground,
        "dining": rooms_lower.build_dining, "kitchen": rooms_lower.build_kitchen, "garage": rooms_lower.build_garage,
    }


def _selected(all_names):
    """`SA_ROOMS=kitchen,garage` constrói só esses cômodos (mais 'items', 'viewmodel', 'anchors' se listados).

    Serve para iterar num território sem depender do código em andamento de quem mexe nos outros.
    Sem a variável, constrói tudo.
    """
    raw = os.environ.get("SA_ROOMS", "").strip()
    if not raw:
        return set(all_names)
    wanted = {name.strip() for name in raw.split(",") if name.strip()}
    unknown = wanted - set(all_names)
    if unknown:
        raise ValueError(f"SA_ROOMS desconhecido: {sorted(unknown)}; válidos: {sorted(all_names)}")
    return wanted


def _build_all(ctx):
    from . import anchors, flashlight, items
    clear_previous_build()
    rooms = _room_builders()
    chosen = _selected([*rooms, "items", "viewmodel", "anchors"])
    for room_id, build_room in rooms.items():
        if room_id in chosen:
            build_room(ctx)
    if "items" in chosen:
        items.make_items(ctx)
    if "viewmodel" in chosen:
        flashlight.make_viewmodel(ctx)
    if "anchors" in chosen:
        anchors.make_anchors(ctx)
    ctx.log(f"{sum(1 for o in bpy.data.objects if 'sa_prop_mode' in o)} props, {len(getattr(bpy.data.collections.get(C.COL_ITEMS), 'objects', ()))} itens")
