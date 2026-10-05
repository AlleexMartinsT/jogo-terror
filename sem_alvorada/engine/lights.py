"""Luzes de ambiente: só as do cômodo do jogador e dos vizinhos ficam acesas (EEVEE leve).

Cada luz `Light_<sala>_<x>` traz `sa_room`, `sa_base_energy`, `sa_flicker` e `sa_kind`.
No apagão as luzes de teto morrem; abajures ficam fracos e a TV segue chiando.

Cada tipo de luz tem a sua física (derivações e conferência: tools/movimento_ref/fisica/luz.py):
  - teto e abajur são incandescentes: o filamento esquenta e esfria (constante de ~34 ms, luz ~ T^9,3), então
    a luz cai a 10% em ~50 ms ao desligar e sobe a 90% em ~120 ms ao ligar; quedas curtas de tensão são alisadas;
  - fluorescente com reator ruim pisca em rajadas de 3 a 10 Hz (o arco apaga de verdade) com longos trechos estáveis;
  - a TV de chuvisco mantém a luz média da sala quase constante (300 mil pixels independentes se anulam).
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
    heat: float = 1.0            # temperatura relativa do filamento (1 = regime), só nas incandescentes


def flicker_gain(clock, amount, seed):
    """Brilho relativo (0..1) de uma luz que pisca: tremor contínuo mais quedas bruscas."""
    if amount <= 0:
        return 1.0
    wobble = 0.5 + 0.5 * math.sin(clock * 23.0 + seed) * math.sin(clock * 7.3 + seed * 1.7)
    cell = math.floor(clock * 11.0 + seed * 3.0)
    noise = (math.sin(cell * 12.9898 + seed * 78.233) * 43758.5453) % 1.0
    dropout = 1.0 if noise < amount * 0.3 else 0.0
    return max(0.0, 1.0 - amount * (0.4 * wobble + 0.6 * dropout))


# ---- filamento incandescente: u' = (s u^-1,2 - u^4 + u0^4) / (4 tau), luz = u^n ----
FILAMENT_KINDS = ("ceiling", "lamp")
FILAMENT_TAU = 0.0336            # s: C T_op / (4 P_op), filamento de 60 W (DERIVADO de uma massa ESTIMADA)
FILAMENT_N = 9.26                # expoente de Planck da luz visível a 2800 K (DERIVADO)
FILAMENT_AMBIENT = 300.0 / 2800.0
FILAMENT_STEP = 0.002            # s: passo de integração (a partida a frio é rápida)


def filament_power(light_fraction):
    """Potência elétrica relativa que mantém, em regime, a fração de luz pedida."""
    u = max(light_fraction, 0.0) ** (1.0 / FILAMENT_N)
    return u ** 1.2 * (u ** 4 - FILAMENT_AMBIENT ** 4)


def filament_advance(u, light_fraction, dt):
    """Avança a temperatura relativa `u` do filamento por `dt` s com a luz pedida `light_fraction`; devolve o novo `u`."""
    power = filament_power(light_fraction)
    while dt > 1e-9:
        h = min(dt, FILAMENT_STEP)
        u += h * (power * max(u, FILAMENT_AMBIENT) ** -1.2 - u ** 4 + FILAMENT_AMBIENT ** 4) / (4.0 * FILAMENT_TAU)
        dt -= h
    return max(u, FILAMENT_AMBIENT)


def burst_flicker_gain(clock, amount, seed):
    """Fluorescente com reator ruim: rajadas de piscadas (3 a 10 Hz, 3 a 8 ciclos) em épocas de 4 s, com a lâmpada apagando
    de verdade entre as piscadas e estável fora delas. `amount` (0..1) sobe a chance de haver rajada na época."""
    if amount <= 0:
        return 1.0
    epoch = math.floor(clock / 4.0)
    chance = min(0.9, amount * 2.4)
    if _hash(epoch, seed) >= chance:
        return 1.0
    frequency = 3.0 + 7.0 * _hash(epoch, seed + 1.0)
    cycles = 3 + int(_hash(epoch, seed + 2.0) * 6.0)
    start = epoch * 4.0 + _hash(epoch, seed + 3.0) * (4.0 - cycles / frequency - 0.2)
    elapsed = clock - start
    if elapsed < 0.0 or elapsed > cycles / frequency:
        return 1.0
    phase = (elapsed * frequency) % 1.0
    edge = 0.006 * frequency                       # o arco apaga e reacende em ~6 ms (fração do ciclo)
    low = 0.03 + 0.1 * _hash(epoch, seed + 4.0)    # sobra um brilho de fósforo
    if phase < edge:
        level = 1.0 - phase / edge
    elif phase < 0.5:
        level = 0.0
    elif phase < 0.5 + edge:
        level = (phase - 0.5) / edge
    else:
        level = 1.0
    return low + (1.0 - low) * level


def tv_gain(clock, amount, seed):
    """TV de tubo com chuvisco: a luz média quase não varia (flutuação de 2 a 4% lenta, a barra de zumbido e o CAG)."""
    if amount <= 0:
        return 1.0
    wobble = 0.5 + 0.5 * math.sin(clock * 4.4 + seed) * math.sin(clock * 0.7 + seed * 1.3)
    return 1.0 - 0.05 * amount * wobble


def _hash(n, seed):
    return (math.sin(n * 127.1 + seed * 311.7) * 43758.5453) % 1.0


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
                if obj.data.users > 1:
                    obj.data = obj.data.copy()       # energia por luz: dados compartilhados piscariam juntos
                energy = float(obj.get(C.P_LIGHT_ENERGY, obj.data.energy))
                self.lights.append(ManagedLight(obj, _room_of(obj), energy,
                                                float(obj.get(C.P_LIGHT_FLICKER, 0.0)),
                                                _kind_of(obj), 1.7 * index + 0.3))
        self.fixtures = [o for o in scene.objects if o.name.startswith("Fixture_")]
        self.power_on = True
        self.power_flicker = 0.0
        self.active_rooms = set()
        self.clock = 0.0
        self.gains = {}                      # nome da luz -> multiplicador (cutscenes: queda em cascata, lâmpada que estoura)

    def set_gain(self, name, gain):
        """Multiplica a energia de uma luz por `gain` (1 volta ao normal). Só as cutscenes usam."""
        if abs(gain - 1.0) < 1e-6:
            self.gains.pop(name, None)
        else:
            self.gains[name] = max(0.0, gain)

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
                self._set_energy(light, dt)

    def energy_target(self, light):
        """Energia que a luz PEDE agora (queda de energia, ganho da cutscene, tremor). O filamento ainda tem de acompanhar."""
        keep = 1.0 if self.power_on else POWER_OFF_KEEP.get(light.kind, 0.0)
        amount = min(1.0, light.flicker + self.power_flicker)
        gain = self.gains.get(light.obj.name, 1.0) if self.gains else 1.0
        if light.kind == "fluorescent":
            shimmer = burst_flicker_gain(self.clock, amount, light.seed)
        elif light.kind == "tv":
            shimmer = tv_gain(self.clock, amount, light.seed)
        else:
            shimmer = flicker_gain(self.clock, amount, light.seed)
        return light.base_energy * keep * gain * shimmer

    def _show(self, light, visible):
        if light.visible == visible:
            return
        light.visible = visible
        light.obj.hide_viewport = light.obj.hide_render = not visible
        if not visible:
            light.obj.data.energy = 0.0

    def _set_energy(self, light, dt=0.0):
        energy = self.energy_target(light)
        if light.kind in FILAMENT_KINDS and light.base_energy > 0.0 and dt > 0.0:
            light.heat = filament_advance(light.heat, energy / light.base_energy, dt)
            energy = light.base_energy * light.heat ** FILAMENT_N
            if energy < 0.002 * light.base_energy:        # abaixo de 0,2% da luz o filamento já é um fio escuro
                energy = 0.0
        lamp = light.obj.data
        if abs(lamp.energy - energy) > 0.002 * max(light.base_energy, 1.0):
            lamp.energy = energy

    def restore_all(self):
        """Todas as luzes visíveis e com a energia do arquivo (ao sair do jogo)."""
        for light in self.lights:
            light.visible = True
            light.heat = 1.0
            light.obj.hide_viewport = light.obj.hide_render = False
            light.obj.data.energy = light.base_energy
        self.set_power(True, 0.0)

    def lit_count(self):
        return sum(1 for light in self.lights if light.visible)
