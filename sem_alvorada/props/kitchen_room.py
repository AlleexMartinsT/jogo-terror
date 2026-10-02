"""Arranjo da cozinha: o que fica onde, na ordem em que o jogador a vê."""
import math

from .. import layout
from . import kitchen


def _anchor_yaw(name):
    return math.radians(layout.ANCHORS[name].yaw_deg)


def build(ctx):
    room = "kitchen"
    a = layout.ANCHORS
    kitchen.make_fridge(ctx, room, a["fridge"].x, a["fridge"].y, _anchor_yaw("fridge"), anchor="fridge", z=a["fridge"].z)
    kitchen.make_sink_unit(ctx, room, a["kitchen_counter"].x, a["kitchen_counter"].y, _anchor_yaw("kitchen_counter"),
                           anchor="kitchen_counter", z=a["kitchen_counter"].z)
    stove = kitchen.make_stove(ctx, room, "E", 7.8)
    kitchen.make_oven_towel(ctx, room, stove)
    kitchen.make_range_hood(ctx, room, "E", 7.8)
    kitchen.make_corner_counter(ctx, room, 10.85, 8.32, 11.875, 9.875)
    top = kitchen.COUNTER_HEIGHT
    kitchen.make_microwave(ctx, room, 11.58, 8.8, top, math.pi / 2)
    kitchen.make_coffee_maker(ctx, room, 11.63, 9.62, top, math.pi)
    kitchen.make_base_cabinet(ctx, room, "W", 5.62, 0.9, depth=0.55, name="counter_west_a")
    kitchen.make_mini_fridge(ctx, room, "W", kitchen.MINI_FRIDGE_ALONG)
    kitchen.make_base_cabinet(ctx, room, "W", 7.16, 0.88, depth=0.55, name="counter_west_b", drawer=True)
    kitchen.make_wall_cabinets(ctx, room, "W", 6.4, 2.4)
    kitchen.make_wall_cabinets(ctx, room, "N", 9.78, 0.44, ajar=False)
    kitchen.make_kitchen_table(ctx, room, 9.95, 6.9)
    kitchen.make_kitchen_chair(ctx, room, 9.95, 7.55, math.pi)
    kitchen.make_kitchen_chair(ctx, room, 9.95, 6.25, 0.0)
    kitchen.make_trash_bin(ctx, room, 8.4, 7.8)
    kitchen.make_ambience(ctx, room)
