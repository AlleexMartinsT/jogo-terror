"""Módulo props: mobília, decoração, itens, documentos, carro, viewmodel, âncoras e colisão.

`build(ctx)` é idempotente: apaga o que uma execução anterior criou (objetos dos props, itens,
proxies de colisão, âncoras, luzes de peças) antes de reconstruir.
"""
import random

import bpy

from .. import conventions as C
from . import kit


def _is_props_object(obj):
    name = obj.name
    return (name.startswith((C.N_ANCHOR, C.N_COL, C.N_ITEM, "Car_")) or name in (C.OBJ_CAR, C.OBJ_VIEW_FLASH)
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


def _build_all(ctx):
    from . import anchors, flashlight, items, rooms_lower, rooms_upper
    clear_previous_build()
    rooms_upper.build_master(ctx)
    rooms_upper.build_kids(ctx)
    rooms_upper.build_bath(ctx)
    rooms_upper.build_study(ctx)
    rooms_upper.build_hall_upper(ctx)
    for build_room in (rooms_lower.build_living, rooms_lower.build_den, rooms_lower.build_hall_ground,
                       rooms_lower.build_dining, rooms_lower.build_kitchen, rooms_lower.build_garage):
        build_room(ctx)
    items.make_items(ctx)
    flashlight.make_viewmodel(ctx)
    anchors.make_anchors(ctx)
    ctx.log(f"{sum(1 for o in bpy.data.objects if 'sa_prop_mode' in o)} props, {len(bpy.data.collections[C.COL_ITEMS].objects)} itens")
