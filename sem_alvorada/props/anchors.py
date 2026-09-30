"""Empties `Anchor_<nome>` para cada entrada de `layout.ANCHORS`, exatamente na posição e no yaw do layout."""
import math

import bpy

from .. import conventions as C
from .. import layout
from .placement import P_ANCHOR

CAR_PARTS = {"car": C.OBJ_CAR, "car_driver_eye": "Car_DriverEye", "car_interact": "Car_Interact"}


def make_anchors(ctx):
    """Cria os Empties e marca o objeto correspondente com `sa_anchor` (os do carro já existem)."""
    for name, anchor in layout.ANCHORS.items():
        marker = bpy.data.objects.new(C.N_ANCHOR + name, None)
        marker.empty_display_type = "ARROWS"
        marker.empty_display_size = 0.25
        marker.location = anchor.pos
        marker.rotation_euler = (0.0, 0.0, math.radians(anchor.yaw_deg))
        marker["sa_note"] = anchor.note
        marker[P_ANCHOR] = name
        ctx.link(marker, C.COL_PROPS)
        if name in CAR_PARTS:
            bpy.data.objects[CAR_PARTS[name]][P_ANCHOR] = name
