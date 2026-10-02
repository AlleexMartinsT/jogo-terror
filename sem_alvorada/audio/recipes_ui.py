"""Sons de interface: a roda do inventário. Discretos, de madeira e papel, nada de bipe eletrônico."""
import numpy as np

from . import dsp as D
from .catalog import sound
from .textures import burst as _burst
from .textures import soft_burst as _soft_burst


def _sweep_air(rng, seconds, low_band, high_band, rising):
    """Sopro que cruza de uma faixa para outra: o ouvido lê como abrir ou fechar."""
    n = D.samples(seconds)
    low = D.band_noise(rng, n, *low_band)
    high = D.band_noise(rng, n, *high_band)
    u = np.linspace(0.0, 1.0, n)
    mix = u if rising else 1.0 - u
    return (low * (1.0 - mix) + high * mix) * D.swell(n, 0.55 if rising else 0.4, 1.4)


@sound("ui_wheel_open", peak=0.4, group="ui")
def ui_wheel_open(rng):
    out = np.zeros(D.samples(0.3))
    D.mix_into(out, _sweep_air(rng, 0.22, (500, 1300), (1800, 4200), True), 0.0, gain=0.5)
    D.mix_into(out, D.thump(D.samples(0.1), 230, 140, 0.012, 0.03), 0.0, gain=0.4)
    D.mix_into(out, _burst(rng, D.samples(0.04), 1500, 6500, 0.01, attack=0.001), 0.17, gain=0.35)
    return out


@sound("ui_wheel_tick", peak=0.34, group="ui")
def ui_wheel_tick(rng):
    """Troca de setor: um estalo seco e baixo, como a lingueta de uma catraca de madeira."""
    out = np.zeros(D.samples(0.1))
    modes = [(rng.uniform(1650, 1850), 0.008, 0.6), (rng.uniform(3300, 3700), 0.005, 0.3)]
    D.mix_into(out, D.modal_strike(rng, modes, D.samples(0.08), spread=0.01), 0.0)
    D.mix_into(out, _soft_burst(rng, D.samples(0.04), 2500, 0.008, 0.0008), 0.0, gain=0.5)
    D.mix_into(out, D.thump(D.samples(0.04), 380, 220, 0.006, 0.01), 0.0, gain=0.35)
    return out


@sound("ui_wheel_close", peak=0.35, group="ui")
def ui_wheel_close(rng):
    out = np.zeros(D.samples(0.26))
    D.mix_into(out, _sweep_air(rng, 0.18, (500, 1300), (1800, 4200), False), 0.0, gain=0.45)
    D.mix_into(out, _burst(rng, D.samples(0.05), 1100, 5000, 0.012, attack=0.001), 0.14, gain=0.35)
    D.mix_into(out, D.thump(D.samples(0.1), 200, 120, 0.012, 0.03), 0.14, gain=0.4)
    return out
