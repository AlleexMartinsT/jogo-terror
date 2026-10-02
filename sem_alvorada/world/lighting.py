"""Luzes de teto: uma luz POINT sem sombra e uma luminária emissiva por ponto de `layout.CEILING_LIGHTS`.

As luzes de ambiente não projetam sombra (só a lanterna projeta): isso mantém o custo da
viewport baixo. Em troca elas atravessam paredes, então cada uma tem distância de corte
(`cutoff_distance`) para não iluminar cômodos distantes.
"""
from dataclasses import dataclass

import bpy

from .. import conventions as C
from .. import layout
from . import fixtures

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
    fixtures.build(ctx, room_id, index, x, y, ceiling_z, lamp.kind)

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


def apply_power(scene, on):
    """Liga ou desliga em bloco as luzes de teto e o brilho de suas luminárias."""
    for obj in scene.objects:
        if obj.type == "LIGHT" and obj.name.startswith(C.N_LIGHT) and C.P_LIGHT_ENERGY in obj:
            obj.data.energy = obj[C.P_LIGHT_ENERGY] if on else 0.0
        elif obj.name.startswith("Fixture_") and "sa_glow" in obj:
            obj["sa_glow"] = 1.0 if on else 0.0
