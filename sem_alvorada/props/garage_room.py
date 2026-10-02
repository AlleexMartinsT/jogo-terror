"""Arranjo da garagem: bancada, painel de ferramentas, estante, freezer, bicicleta e o que sobrou do Dan."""
import math

from .. import layout
from . import garage


def _anchor_yaw(name):
    return math.radians(layout.ANCHORS[name].yaw_deg)


def build(ctx):
    room = "garage"
    a = layout.ANCHORS["workbench"]
    garage.make_workbench(ctx, room, a.x, a.y, _anchor_yaw("workbench"), anchor="workbench", z=a.z)
    garage.make_tool_panel(ctx, room, "E", 1.95, 1.65)
    garage.make_garage_shelves(ctx, room, "N", 16.15)
    garage.make_chest_freezer(ctx, room, "W", 1.6)
    garage.make_kids_bicycle(ctx, room, 12.4, 3.25, 0.0)
    garage.make_water_heater(ctx, room, 18.05, 6.5)
    garage.make_lawn_mower(ctx, room, 17.85, 1.3, math.radians(10))
    garage.make_box_pile(ctx, room, 12.55, 0.6, 0.0, [(1.0, 0, 0, 0), (0.9, 0.0, 0.0, 8), (0.8, 0.03, 0.0, -6)], "kg_box_emma",
                         name="boxes_garage")
    garage.make_box_pile(ctx, room, 12.5, 4.3, 0.0, [(0.9, 0, 0, 0), (0.7, 0.0, 0.0, 14)], "kg_box_toys", name="boxes_garage_2")
    garage.make_ambience(ctx, room)
