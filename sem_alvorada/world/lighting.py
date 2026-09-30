"""Luzes de teto: uma luz POINT sem sombra e uma luminária emissiva por ponto de `layout.CEILING_LIGHTS`.

As luzes de ambiente não projetam sombra (só a lanterna projeta): isso mantém o custo da
viewport baixo. Em troca elas atravessam paredes, então cada uma tem distância de corte
(`cutoff_distance`) para não iluminar cômodos distantes.
"""
import math
from dataclasses import dataclass

import bpy

from .. import conventions as C
from .. import layout
from .meshkit import MeshBuilder

# A luz fica 36 cm abaixo do forro: assim `layout.room_at` a classifica no andar certo
# (o limite do andar de cima é z >= 2,3) e o forro não estoura em branco logo acima dela.
LIGHT_DROP = 0.36
CUTOFF_DISTANCE = 7.5
WARM_BULB = (1.0, 0.72, 0.42)
COLD_TUBE = (0.80, 0.92, 1.0)


@dataclass(frozen=True)
class CeilingLamp:
    kind: str
    color: tuple
    energy: float
    flicker: float


DEFAULT_LAMP = CeilingLamp("ceiling", WARM_BULB, 95.0, 0.03)
LAMPS = {
    "kitchen": CeilingLamp("fluorescent", COLD_TUBE, 150.0, 0.10),
    "garage": CeilingLamp("fluorescent", COLD_TUBE, 180.0, 0.25),
    "hall_u": CeilingLamp("ceiling", WARM_BULB, 85.0, 0.06),
    "bath": CeilingLamp("ceiling", (0.95, 0.9, 0.7), 80.0, 0.04),
}


def build(ctx):
    count = 0
    for room_id, spots in layout.CEILING_LIGHTS.items():
        for index, (x, y) in enumerate(spots):
            _place_lamp(ctx, room_id, index, x, y)
            count += 1
    ctx.log(f"{count} luzes de teto sem sombra")


def _place_lamp(ctx, room_id, index, x, y):
    room = layout.ROOMS[room_id]
    lamp = LAMPS.get(room_id, DEFAULT_LAMP)
    ceiling_z = layout.CEIL_Z[room.level]
    name = f"{room_id}_c{index}"

    fixture = _fixture_mesh(f"Fixture_{name}", lamp.kind, x, y, ceiling_z).build(
        ctx, C.COL_WORLD, origin=(x, y, ceiling_z))
    fixture["sa_glow"] = 1.0
    fixture[C.P_ROOM] = room_id

    data = bpy.data.lights.new(f"{C.N_LIGHT}{name}", "POINT")
    data.energy = lamp.energy
    data.color = lamp.color
    data.shadow_soft_size = 0.15
    data.use_shadow = False
    data.use_custom_distance = True
    data.cutoff_distance = CUTOFF_DISTANCE
    obj = bpy.data.objects.new(f"{C.N_LIGHT}{name}", data)
    obj.location = (x, y, ceiling_z - LIGHT_DROP)
    ctx.link(obj, C.COL_WORLD)
    obj[C.P_ROOM] = room_id
    obj[C.P_LIGHT_ENERGY] = lamp.energy
    obj[C.P_LIGHT_FLICKER] = lamp.flicker
    obj[C.P_LIGHT_KIND] = lamp.kind


def _fixture_mesh(name, kind, x, y, ceiling_z):
    """Luminária colada ao forro: tubo fluorescente na cozinha e garagem, globo nos demais."""
    builder = MeshBuilder(name)
    if kind == "fluorescent":
        builder.box(x - 0.66, y - 0.12, ceiling_z - 0.07, x + 0.66, y + 0.12, ceiling_z, "metal", skip=("+z",))
        builder.box(x - 0.6, y - 0.07, ceiling_z - 0.085, x + 0.6, y + 0.07, ceiling_z - 0.07,
                    "fixture_glow", skip=("+z",))
        return builder
    sides = 10
    builder.cylinder(x, y, ceiling_z - 0.03, ceiling_z, 0.22, "trim_white", sides=sides, caps=False)
    builder.cylinder(x, y, ceiling_z - 0.11, ceiling_z - 0.03, 0.17, "fixture_glow", sides=sides,
                     radius_top=0.2, caps=False)
    disc = [(x + 0.17 * math.cos(2 * math.pi * i / sides), y + 0.17 * math.sin(2 * math.pi * i / sides),
             ceiling_z - 0.11) for i in range(sides)]
    builder.polygon(disc[::-1], "fixture_glow")
    return builder


def apply_power(scene, on):
    """Liga ou desliga em bloco as luzes de teto e o brilho de suas luminárias."""
    for obj in scene.objects:
        if obj.type == "LIGHT" and obj.name.startswith(C.N_LIGHT) and C.P_LIGHT_ENERGY in obj:
            obj.data.energy = obj[C.P_LIGHT_ENERGY] if on else 0.0
        elif obj.name.startswith("Fixture_") and "sa_glow" in obj:
            obj["sa_glow"] = 1.0 if on else 0.0
