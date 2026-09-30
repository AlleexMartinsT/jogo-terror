"""Luzes de ambiente: só as do cômodo do jogador e dos vizinhos ficam acesas (EEVEE leve).

Cada luz `Light_<sala>_<x>` traz `sa_room`, `sa_base_energy`, `sa_flicker` e `sa_kind`.
No apagão as luzes de teto morrem; abajures ficam fracos e a TV segue chiando.
"""
import math
import re
from dataclasses import dataclass

from .. import conventions as C
from .. import layout

# Fração da energia que sobra quando a energia elétrica cai, por tipo de luz.
POWER_OFF_KEEP = {"ceiling": 0.0, "fluorescent": 0.0, "lamp": 0.45, "tv": 1.0, "window": 1.0}
_CEILING_NAME = re.compile(r"_c\d+$")


@dataclass
class ManagedLight:
    obj: object
    room: str
    base_energy: float
    flicker: float
    kind: str
    seed: float
    visible: bool = True


def flicker_gain(clock, amount, seed):
    """Brilho relativo (0..1) de uma luz que pisca: tremor contínuo mais quedas bruscas."""
    if amount <= 0:
        return 1.0
    wobble = 0.5 + 0.5 * math.sin(clock * 23.0 + seed) * math.sin(clock * 7.3 + seed * 1.7)
    cell = math.floor(clock * 11.0 + seed * 3.0)
    noise = (math.sin(cell * 12.9898 + seed * 78.233) * 43758.5453) % 1.0
    dropout = 1.0 if noise < amount * 0.3 else 0.0
    return max(0.0, 1.0 - amount * (0.4 * wobble + 0.6 * dropout))


def _room_of(obj):
    room = obj.get(C.P_ROOM)
    if room:
        return room
    stem = obj.name[len(C.N_LIGHT):]
    return stem.rsplit("_", 1)[0]


def _kind_of(obj):
    kind = obj.get(C.P_LIGHT_KIND)
    if kind:
        return kind
    return "ceiling" if _CEILING_NAME.search(obj.name) else "lamp"


class LightManager:
    def __init__(self, scene):
        self.lights = []
        for index, obj in enumerate(sorted(scene.objects, key=lambda o: o.name)):
            if obj.type == "LIGHT" and obj.name.startswith(C.N_LIGHT):
                energy = float(obj.get(C.P_LIGHT_ENERGY, obj.data.energy))
                self.lights.append(ManagedLight(obj, _room_of(obj), energy,
                                                float(obj.get(C.P_LIGHT_FLICKER, 0.0)),
                                                _kind_of(obj), 1.7 * index + 0.3))
        self.fixtures = [o for o in scene.objects if o.name.startswith("Fixture_")]
        self.power_on = True
        self.power_flicker = 0.0
        self.active_rooms = set()
        self.clock = 0.0

    def set_power(self, on, flicker=0.0):
        """Liga/desliga a energia da casa. `flicker` (0..1) acrescenta tremor a todas as luzes."""
        self.power_on = on
        self.power_flicker = flicker
        for fixture in self.fixtures:
            fixture.hide_viewport = fixture.hide_render = not on

    def rooms_near(self, room_id):
        if room_id is None:
            return set()
        return {room_id} | {other for other, _ in layout.neighbors(room_id)}

    def update(self, dt, room_id):
        self.clock += dt
        self.active_rooms = self.rooms_near(room_id)
        for light in self.lights:
            self._show(light, light.room in self.active_rooms)
            if light.visible:
                self._set_energy(light)

    def energy_target(self, light):
        keep = 1.0 if self.power_on else POWER_OFF_KEEP.get(light.kind, 0.0)
        amount = min(1.0, light.flicker + self.power_flicker)
        return light.base_energy * keep * flicker_gain(self.clock, amount, light.seed)

    def _show(self, light, visible):
        if light.visible == visible:
            return
        light.visible = visible
        light.obj.hide_viewport = light.obj.hide_render = not visible
        if not visible:
            light.obj.data.energy = 0.0

    def _set_energy(self, light):
        energy = self.energy_target(light)
        data = light.obj.data
        if abs(data.energy - energy) > 0.002 * max(light.base_energy, 1.0):
            data.energy = energy

    def restore_all(self):
        """Todas as luzes visíveis e com a energia do arquivo (ao sair do jogo)."""
        for light in self.lights:
            light.visible = True
            light.obj.hide_viewport = light.obj.hide_render = False
            light.obj.data.energy = light.base_energy
        self.set_power(True, 0.0)

    def lit_count(self):
        return sum(1 for light in self.lights if light.visible)
