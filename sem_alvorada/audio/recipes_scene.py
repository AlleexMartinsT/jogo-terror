"""Receitas de cutscenes e gameplay especial: apagão, energia, carro, garagem, alarme, morte."""
import numpy as np

from . import dsp as D
from .catalog import SR_LOOP, sound
from .textures import burst, crackle, metal_tick, soft_burst


@sound("blackout_thunk", peak=0.95, group="scene")
def blackout_thunk(rng):
    """Disjuntor desarmando: baque no quadro de força, faísca e o gemido da energia descendo."""
    n = D.samples(1.5)
    out = 1.0 * D.thump(n, 82, 36, 0.04, 0.32)
    out += 0.7 * burst(rng, n, 1200, 9000, 0.02, attack=0.0003) + 0.4 * crackle(rng, 1.5, 60, 1500, 8000) * D.decay(n, 0.15)
    whine_n = D.samples(0.8)
    fall = D.sine(D.sweep(2600.0, 55.0, whine_n), whine_n) * D.decay(whine_n, 0.25)
    D.mix_into(out, fall, 0.02, gain=0.4)
    D.mix_into(out, metal_tick(rng, 0.9, ring=0.03), 0.0)
    return D.reverb(rng, out, 0.8, wet=0.25)


@sound("power_hum", sr=SR_LOOP, peak=0.5, loop=True, group="scene")
def power_hum(rng):
    """Transformador/rede elétrica: 60 Hz com harmônicos ímpares e um apito fino de 1,2 kHz."""
    sr, n = SR_LOOP, D.samples(4.0, SR_LOOP)
    mains = D.harmonic_tone(60.0, n, [1.0, 0.35, 0.7, 0.15, 0.4, 0.1, 0.2], sr)
    whine = 0.08 * D.sine(1200.0, n, sr) * (0.7 + 0.3 * D.sine(0.5, n, sr))
    return mains + whine + 0.25 * D.unit_rms(D.lowpass(D.white(rng, n), 300, sr))


_ENGINE_WEIGHTS = [1.0, 0.8, 0.7, 0.55, 0.45, 0.35, 0.3, 0.22, 0.18, 0.15, 0.1, 0.08]


def _engine(rng, rate_curve, seconds, roughness=0.15, sr=D.SR):
    """Motor de 4 cilindros: harmônicos da taxa de explosão (`rate_curve` Hz) com irregularidade lenta."""
    n = D.samples(seconds, sr)
    body = D.harmonic_tone(rate_curve, n, _ENGINE_WEIGHTS, sr)
    body *= 1.0 + roughness * D.smooth_noise(rng, n, 9, sr)
    mechanical = 0.10 * D.band_noise(rng, n, 250, 2800, sr)
    return D.unit_rms(body) + mechanical


@sound("car_start", peak=0.9, group="scene")
def car_start(rng):
    """Partida: motor de arranque em compressões lentas, o motor pega, sobe de giro e assenta no ralenti."""
    seconds = 4.6
    n = D.samples(seconds)
    t = D.time_axis(n)
    crank_end, catch_end = 1.6, 2.4
    starter_hz = 7.0 - 1.0 * (t / crank_end).clip(0, 1)
    starter = D.lowpass(D.pulse_train(rng, starter_hz, n, jitter=0.02, amp_jitter=0.3), 420) * (t < crank_end + 0.1)
    whine = 0.35 * D.sine(220.0 + 20.0 * np.sin(2 * np.pi * 7 * t), n) * (t < crank_end)
    rpm_hz = np.where(t < crank_end, 3.0, np.where(t < catch_end, 3.0 + 27.0 * ((t - crank_end) / (catch_end - crank_end)).clip(0, 1) ** 0.6, 30.0))
    throttle = 0.6 + 0.4 * ((t >= crank_end) & (t < catch_end + 0.4))
    motor = _engine(rng, rpm_hz, seconds) * (t >= crank_end - 0.05) * throttle
    return D.reverb(rng, D.unit_rms(starter) * 0.9 + whine + motor * 1.2, 0.5, wet=0.15)


@sound("car_idle", sr=SR_LOOP, peak=0.7, loop=True, group="scene")
def car_idle(rng):
    """Ralenti de 30 Hz (900 rpm): frequência constante e ruído periódico, então a emenda é contínua."""
    sr, seconds = SR_LOOP, 4.0
    return _engine(rng, D.as_curve(30.0, D.samples(seconds, sr)), seconds, sr=sr)


@sound("car_door", peak=0.9, group="scene")
def car_door(rng):
    n = D.samples(1.2)
    out = 1.0 * D.thump(n, 105, 55, 0.03, 0.12) + 0.8 * soft_burst(rng, n, 900, 0.05, 0.001)
    out += 0.4 * D.modal_strike(rng, [(140, 0.3, 0.6), (235, 0.22, 0.4), (410, 0.12, 0.25)], n)
    D.mix_into(out, metal_tick(rng, 1.0, ring=0.03), 0.045)
    D.mix_into(out, metal_tick(rng, 0.6, ring=0.02), 0.11)
    return D.reverb(rng, out, 0.28, wet=0.3)


@sound("garage_rollup", peak=0.9, group="scene")
def garage_rollup(rng):
    """Portão de enrolar: rumor do trilho, painéis batendo nos roletes, motor e o encontro no batente."""
    seconds = 5.0
    n = D.samples(seconds)
    rail = D.unit_rms(D.lowpass(D.pink(rng, n), 650)) * D.swell(n, 0.5, 0.5) * 0.7
    motor = 0.25 * D.harmonic_tone(D.sweep(170.0, 215.0, n), n, [1.0, 0.5, 0.3]) * D.swell(n, 0.5, 0.4)
    out = rail + motor
    clock = 0.15
    while clock < seconds - 0.9:        # cada junta de painel passa por um rolete
        modes = [(rng.uniform(500, 700), 0.04, 0.7), (rng.uniform(1300, 1600), 0.03, 0.5), (rng.uniform(2700, 3100), 0.02, 0.3)]
        clank = D.modal_strike(rng, modes, D.samples(0.2)) + 0.5 * burst(rng, D.samples(0.2), 1000, 6000, 0.02)
        D.mix_into(out, clank, clock, gain=rng.uniform(0.3, 1.0) * float(D.swell(100, 0.5, 0.5)[50]))
        clock += 1.0 / 7.0 * rng.uniform(0.8, 1.2)
    stop = D.modal_strike(rng, [(400, 0.4, 0.8), (900, 0.3, 0.6), (1900, 0.2, 0.4), (3600, 0.12, 0.3)], D.samples(1.2))
    D.mix_into(out, stop + 1.0 * D.thump(D.samples(1.2), 90, 45, 0.03, 0.2), seconds - 1.0, gain=1.2)
    return D.reverb(rng, out, 1.3, wet=0.3)


@sound("alarm_beep", peak=0.7, group="scene")
def alarm_beep(rng):
    """Três bipes eletrônicos secos (onda quadrada de 1,5 kHz)."""
    out = np.zeros(D.samples(1.0))
    for k in range(3):
        n = D.samples(0.14)
        beep = D.harmonic_tone(1500.0, n, [1.0, 0.0, 0.33, 0.0, 0.2, 0.0, 0.14]) * D.fade_edges(np.ones(n), 0.004, 0.006)
        D.mix_into(out, beep, 0.02 + 0.28 * k)
    return D.reverb(rng, out, 0.3, wet=0.1)


@sound("death_hit", peak=0.98, group="scene")
def death_hit(rng):
    """Impacto final: boom subgrave, colapso de ruído e um guincho; corta seco e sobra um zumbido no ouvido."""
    n = D.samples(2.6)
    cut = D.samples(0.95)
    hit = 1.2 * D.thump(n, 95, 26, 0.09, 0.5) + 0.9 * burst(rng, n, 80, 7000, 0.22, attack=0.001)
    screech = D.harmonic_tone(D.sweep(2600.0, 900.0, D.samples(0.6)), D.samples(0.6), D.sawtooth_weights(8, 1.0))
    D.mix_into(hit, screech * D.attack_decay(D.samples(0.6), 0.005, 0.2), 0.0, gain=0.5)
    hit[cut:] = 0.0                                   # corte seco
    hit[:cut] *= np.concatenate([np.ones(cut - D.samples(0.01)), np.linspace(1.0, 0.0, D.samples(0.01))])
    ring_envelope = np.zeros(n)
    ring_envelope[cut:] = D.attack_decay(n - cut, 0.05, 0.8)
    return D.reverb(rng, hit, 1.0, wet=0.2)[:n] + 0.09 * D.sine(4200.0, n) * ring_envelope
