"""Catálogo de sons do jogo (nomes do contrato, seção 5.6) e registro das receitas de síntese.

Este módulo não importa numpy: o motor de áudio e os testes podem consultar os nomes sem
carregar a síntese. As receitas (recipes_*.py) se registram aqui com os decoradores
`sound` e `sound_family`.
"""
from dataclasses import dataclass
from typing import Callable

SR_FULL = 44100
SR_LOOP = 22050

STEP_SURFACES = ("wood", "carpet", "tile", "concrete", "stairs")
STEP_VARIATIONS = 4


def _numbered(prefix, count):
    return tuple(f"{prefix}_{i}" for i in range(1, count + 1))


REQUIRED_SOUNDS = (
    tuple(n for s in STEP_SURFACES for n in _numbered(f"step_{s}", STEP_VARIATIONS))
    + ("door_open", "door_close", "door_slam", "door_locked", "door_unlock", "door_creak_long")
    + ("pickup", "battery_pickup", "battery_insert", "paper_rustle", "key_jingle", "map_unfold")
    + ("flash_on", "flash_off", "flash_flicker")
    + ("breath_calm", "breath_heavy", "heartbeat", "gasp")
    + ("amb_house", "amb_fridge", "amb_clock_tick", "amb_wind", "amb_tv_static", "amb_garage_hum",
       "amb_music_box", "amb_radio_static")
    + _numbered("creak", 3) + _numbered("thud", 2) + ("phone_ring", "glass_break", "clock_chime")
    + ("ent_drone", "ent_breath") + _numbered("ent_step", 4) + _numbered("ent_step_stalk", 2)
    + ("ent_growl", "ent_scream", "ent_whisper", "ent_door_break", "ent_stinger", "ent_static_burst")
    + ("blackout_thunk", "power_hum", "car_start", "car_idle", "car_door", "garage_rollup",
       "alarm_beep", "death_hit")
)


@dataclass(frozen=True)
class SoundSpec:
    name: str
    build: Callable            # build(rng) -> np.ndarray float64
    sr: int = SR_FULL
    peak: float = 0.85         # pico alvo após normalizar
    loop: bool = False
    group: str = ""


SPECS = {}


def _register(spec):
    assert spec.name not in SPECS, f"som duplicado: {spec.name}"
    SPECS[spec.name] = spec


def sound(name, sr=SR_FULL, peak=0.85, loop=False, group=""):
    """Registra uma receita `fn(rng)` sob `name`."""
    def wrap(fn):
        _register(SoundSpec(name, fn, sr, peak, loop, group))
        return fn
    return wrap


def sound_family(prefix, count, sr=SR_FULL, peak=0.85, group=""):
    """Registra `prefix_1..count` a partir de uma receita `fn(rng, index)` com index 0..count-1."""
    def wrap(fn):
        for index in range(count):
            _register(SoundSpec(f"{prefix}_{index + 1}", lambda rng, i=index: fn(rng, i), sr, peak, False, group))
        return fn
    return wrap


def loop_names():
    return tuple(name for name, spec in SPECS.items() if spec.loop)
