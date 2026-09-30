"""Sala de jantar: mesa posta para uma refeição que ninguém terminou, aparador, prato quebrado."""
import math

from . import parts
from .kit import MeshBuilder
from .placement import against_wall, place


def make_dining_table(ctx, room, x, y, yaw=0.0):
    """Mesa de 1,8 x 0,95 m posta para três: dois pratos com comida seca, velas apagadas, flores mortas."""
    width, depth = 1.8, 0.95
    m = MeshBuilder("dining_table")
    m.box(0, 0, 0.72, width, depth, 0.04, "wood_dark", mats={"top": "veneer_dark"})
    m.box(0, 0, 0.64, width - 0.24, depth - 0.24, 0.08, "wood_dark")
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.cylinder(sx * (width / 2 - 0.09), sy * (depth / 2 - 0.09), 0, 0.05, 0.72, "wood_dark", seg=6, r_top=0.035)
    m.box(0, 0, 0.762, 1.5, 0.32, 0.004, "linen_sheet")
    for cx, cy, food in ((-0.55, -0.30, True), (-0.55, 0.30, False), (0.55, 0.30, True), (0.0, -0.32, False)):
        parts.plate(m, cx, cy, 0.766, 0.13, "ceramic_cream", food="food_dried" if food else None)
    for cx in (-0.28, 0.28):
        parts.candle(m, cx, 0.0, 0.766, 0.22)
    m.cylinder(0, 0, 0.766, 0.07, 0.14, "ceramic_cream", seg=8, r_top=0.045)
    for i in range(5):
        angle = math.radians(i * 72)
        m.tube((0, 0, 0.90), (0.11 * math.cos(angle), 0.11 * math.sin(angle), 1.08 - 0.05 * (i % 2)), 0.005, "wood_mid",
               seg=4)
        m.box(0.12 * math.cos(angle), 0.12 * math.sin(angle), 1.06 - 0.05 * (i % 2), 0.04, 0.03, 0.02, "food_dried")
    parts.mug(m, 0.75, -0.25, 0.766, 0.04, 0.09, "glass_clear")
    return place(ctx, m, room, "dining_table", x, y, yaw, name="dining_table")


def make_sideboard(ctx, room, wall, along):
    """Aparador de duas portas e três gavetas, com um retrato, velas e uma travessa."""
    width, depth, height = 1.4, 0.45, 0.85
    x, y, yaw = against_wall(room, wall, along, depth)
    m = MeshBuilder("sideboard")
    parts.four_legs(m, -width / 2, -depth / 2, width / 2, depth / 2, 0.1, 0.05, "wood_dark")
    m.box(0, 0, 0.1, width, depth, height - 0.14, "wood_mid", mats={"front": "veneer_mid"})
    m.box(0, 0, height - 0.04, width + 0.04, depth + 0.02, 0.04, "wood_dark")
    for door_x in (-0.35, 0.35):
        m.box(door_x, depth / 2 + 0.006, 0.14, 0.62, 0.012, height - 0.3, "wood_dark")
        parts.knob(m, door_x + (0.25 if door_x < 0 else -0.25), depth / 2 + 0.016, 0.42, "brass")
    parts.candle(m, -0.5, 0.0, height, 0.2)
    parts.candle(m, -0.38, 0.0, height, 0.14)
    m.cylinder(0.45, 0.0, height, 0.13, 0.03, "ceramic_cream", seg=10, r_top=0.15)
    return place(ctx, m, room, "sideboard", x, y, yaw)


def make_broken_plate(ctx, room, x, y, yaw=0.0):
    """Prato quebrado no chão: meia dúzia de cacos claros espalhados a partir de um ponto de impacto."""
    m = MeshBuilder("broken_plate")
    rng = ctx.rng
    for i in range(7):
        angle = math.radians(i * 51 + rng.uniform(-10, 10))
        reach = rng.uniform(0.04, 0.20)
        cx, cy = reach * math.cos(angle), reach * math.sin(angle)
        spin = rng.uniform(0, 6.28)
        size = rng.uniform(0.035, 0.07)
        shard = [(cx + size * math.cos(spin + k * 2.1 + rng.uniform(-0.3, 0.3)) * (1.0 if k else 0.5),
                  cy + size * math.sin(spin + k * 2.1 + rng.uniform(-0.3, 0.3)), 0.004 + 0.002 * (i % 2)) for k in range(3)]
        m.poly(shard, "ceramic_cream")
        m.poly(list(reversed(shard)), "ceramic_cream")
    m.cylinder(0.02, -0.03, 0.0, 0.05, 0.006, "food_dried", seg=6)
    return place(ctx, m, room, "broken_plate", x, y, yaw, mode="flat")
