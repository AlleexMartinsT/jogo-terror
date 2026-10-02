"""Receitas das portas: movimento, trinco, batida, tranca e os quatro rangidos de dobradiça.

O ranger é um som À PARTE do movimento. `door_open`/`door_close` são só o ar e a madeira da folha
(sem gemido nenhum); quando o jogo sorteia o ranger, toca `door_creak_N` por cima. Assim uma porta
que não range de fato não range, e o trinco (`door_latch`) toca quando a folha chega ao batente,
não num instante fixo do arquivo.
"""
import numpy as np

from . import dsp as D
from .catalog import sound, sound_family
from .textures import burst as _burst
from .textures import creak_texture as _creak
from .textures import metal_tick as _metal_tick
from .textures import soft_burst as _soft_burst


def _latch(rng, gain=1.0):
    """Lingueta do trinco: toque metálico com um baque de madeira embaixo."""
    n = D.samples(0.15)
    return gain * D.stack(_metal_tick(rng, 0.7), 0.5 * D.thump(n, 240, 130, 0.01, 0.025))


def _wood_stop(rng, gain=1.0):
    """Folha encostando no batente: baque surdo curto."""
    n = D.samples(0.3)
    return gain * (D.thump(n, 105, 55, 0.03, 0.07) + 0.4 * _soft_burst(rng, n, 700, 0.04, 0.002))


def _wood_pops(rng, canvas, start, end, count, gain):
    """Estalinhos de madeira trabalhando: o que sobra de uma porta sem gemido."""
    for _ in range(count):
        at = rng.uniform(start, end)
        pop = _burst(rng, D.samples(0.05), rng.uniform(350, 900), rng.uniform(1400, 2600), rng.uniform(0.008, 0.02), attack=0.001)
        D.mix_into(canvas, pop, at, gain=gain * rng.uniform(0.4, 1.0))


def _leaf_air(rng, seconds, cutoff, peak_at, power=1.5):
    """Ar empurrado pela folha e atrito leve nas vedações: ruído abafado que sobe e desce."""
    n = D.samples(seconds)
    air = D.unit_rms(D.bandpass(D.white(rng, n), 140, cutoff))
    return air * D.swell(n, peak_at, power)


# --------------------------------------------------------------------------
# Movimento e trinco
# --------------------------------------------------------------------------
@sound("door_open", peak=0.7, group="doors")
def door_open(rng):
    out = np.zeros(D.samples(1.3))
    D.mix_into(out, _metal_tick(rng, 0.5, ring=0.012), 0.0)
    D.mix_into(out, D.thump(D.samples(0.12), 230, 130, 0.01, 0.025), 0.0, gain=0.3)
    D.mix_into(out, _leaf_air(rng, 1.0, 900, 0.45), 0.10, gain=0.22)
    _wood_pops(rng, out, 0.12, 0.95, 4, 0.18)
    return D.reverb(rng, out, 0.3, wet=0.14)


@sound("door_open_soft", peak=0.45, group="doors")
def door_open_soft(rng):
    """Porta aberta com cuidado: o trinco solta e a folha corre quase sem ruído."""
    out = np.zeros(D.samples(1.2))
    D.mix_into(out, _metal_tick(rng, 0.22, ring=0.008), 0.0)
    D.mix_into(out, _leaf_air(rng, 1.0, 520, 0.5, 2.0), 0.08, gain=0.2)
    _wood_pops(rng, out, 0.2, 0.9, 2, 0.07)
    return D.reverb(rng, out, 0.3, wet=0.12)


@sound("door_close", peak=0.7, group="doors")
def door_close(rng):
    """A folha corre até o batente. O encontro e o trinco são `door_latch`, tocado na chegada."""
    out = np.zeros(D.samples(1.2))
    D.mix_into(out, _leaf_air(rng, 1.0, 1000, 0.5), 0.0, gain=0.25)
    _wood_pops(rng, out, 0.05, 0.8, 3, 0.15)
    D.mix_into(out, _soft_burst(rng, D.samples(0.18), 600, 0.06, 0.04), 0.82, gain=0.2)   # ar comprimido no fim
    return D.reverb(rng, out, 0.3, wet=0.14)


@sound("door_handle", peak=0.6, group="doors")
def door_handle(rng):
    """Maçaneta girando: atrito do latão, a lingueta recolhe e a mola a devolve."""
    out = np.zeros(D.samples(0.7))
    D.mix_into(out, _burst(rng, D.samples(0.12), 1600, 6500, 0.05, attack=0.02), 0.0, gain=0.22)    # latão no mecanismo
    D.mix_into(out, _metal_tick(rng, 0.8, ring=0.012), 0.075)                                       # lingueta recolhe
    D.mix_into(out, D.thump(D.samples(0.1), 280, 160, 0.008, 0.02), 0.075, gain=0.25)
    D.mix_into(out, _burst(rng, D.samples(0.08), 2500, 9000, 0.02, attack=0.004), 0.30, gain=0.16)   # solta o botão
    D.mix_into(out, _metal_tick(rng, 0.38, ring=0.008), 0.37)                                       # mola devolve a lingueta
    return D.reverb(rng, out, 0.2, wet=0.1)


@sound("door_latch", peak=0.85, group="doors")
def door_latch(rng):
    """Trinco: a lingueta chanfrada raspa na contra-fechadura, estala no lugar e a folha assenta."""
    out = np.zeros(D.samples(0.45))
    D.mix_into(out, _burst(rng, D.samples(0.03), 2200, 9000, 0.008, attack=0.003), 0.0, gain=0.3)
    D.mix_into(out, _metal_tick(rng, 1.0, ring=0.014), 0.014)
    D.mix_into(out, _metal_tick(rng, 0.6, ring=0.02), 0.017)
    D.mix_into(out, D.thump(D.samples(0.15), 240, 130, 0.01, 0.025), 0.014, gain=0.22)
    D.mix_into(out, _wood_stop(rng, 0.16), 0.016)
    D.mix_into(out, _metal_tick(rng, 0.3, ring=0.008), 0.095)       # a folha volta um fio e assenta
    D.mix_into(out, _burst(rng, D.samples(0.04), 500, 2200, 0.01), 0.095, gain=0.18)
    return D.reverb(rng, out, 0.28, wet=0.13)


@sound("door_slam", peak=0.95, group="doors")
def door_slam(rng):
    """Batida. A folha leva ~0,2 s do ar ao batente, então o estrondo vem depois do assobio."""
    lead = 0.19
    out = np.zeros(D.samples(2.4))
    D.mix_into(out, _leaf_air(rng, lead, 3200, 0.9, 1.0), 0.0, gain=0.5)
    n = D.samples(2.2)
    core = np.zeros(n)
    boom = D.thump(n, 75, 32, 0.05, 0.25)
    slab = _soft_burst(rng, n, 1500, 0.08, 0.001)
    wood = D.modal_strike(rng, [(110, 0.25, 0.6), (190, 0.18, 0.5), (340, 0.14, 0.35), (520, 0.10, 0.25)], n, spread=0.02)
    crack = _burst(rng, n, 1500, 12000, 0.012, attack=0.0002)
    core += 1.0 * boom + 0.8 * slab + 0.6 * wood + 0.6 * crack
    D.mix_into(core, _latch(rng, 0.9), 0.008)
    for k in range(6):      # o batente e a folha vibram depois do impacto
        D.mix_into(core, _burst(rng, D.samples(0.05), 800, 3000, 0.01), 0.06 + 0.045 * k, gain=0.35 * 0.7 ** k)
    D.mix_into(out, core, lead)
    return D.reverb(rng, out, 0.9, wet=0.28, predelay=0.02)[:D.samples(2.4)]


@sound("door_locked", peak=0.8, group="doors")
def door_locked(rng):
    out = np.zeros(D.samples(1.3))
    for start, gain in ((0.02, 1.0), (0.42, 0.85), (0.78, 0.55)):
        for k in range(3):      # a maçaneta sacoleja: três batidas metálicas seguidas
            D.mix_into(out, _metal_tick(rng, gain * (1.0 - 0.25 * k), ring=0.03), start + 0.03 * k)
        D.mix_into(out, D.thump(D.samples(0.2), 210, 120, 0.01, 0.04), start, gain=0.5 * gain)
    D.mix_into(out, _wood_stop(rng, 0.3), 0.03)
    return D.reverb(rng, out, 0.3, wet=0.12)


@sound("door_unlock", peak=0.75, group="doors")
def door_unlock(rng):
    out = np.zeros(D.samples(1.5))
    for start in (0.03, 0.10):       # chave entrando: raspado agudo em dois tempos
        D.mix_into(out, _burst(rng, D.samples(0.06), 3500, 9500, 0.03, attack=0.004), start, gain=0.35)
    for k, start in enumerate((0.30, 0.38, 0.45)):    # pinos do cilindro
        D.mix_into(out, _metal_tick(rng, 0.6 + 0.1 * k, ring=0.012), start)
    D.mix_into(out, _latch(rng, 1.2), 0.62)
    D.mix_into(out, D.thump(D.samples(0.25), 160, 85, 0.02, 0.06), 0.62, gain=0.5)
    D.mix_into(out, _burst(rng, D.samples(0.1), 3000, 9000, 0.05, attack=0.01), 1.05, gain=0.25)
    return D.reverb(rng, out, 0.3, wet=0.12)


# --------------------------------------------------------------------------
# Ranger
# --------------------------------------------------------------------------
# Um rangido de dobradiça é atrito que pega e solta (stick-slip). A taxa dos "pega e solta" segue a
# velocidade da folha: sobe quando ela acelera e cai quando ela assenta. Por isso todo rangido aqui tem
# uma corcova de afinação (repouso -> pico -> repouso) que acompanha a curva de movimento da porta.
def _pitch_hump(n, rest_hz, peak_hz, end_hz, peak_at):
    """Afinação que sobe de `rest_hz` ao pico (em `peak_at`, 0..1) e desce até `end_hz`."""
    u = np.linspace(0.0, 1.0, n)
    rise = np.sin(0.5 * np.pi * np.clip(u / peak_at, 0.0, 1.0)) ** 2
    fall = np.sin(0.5 * np.pi * np.clip((u - peak_at) / (1.0 - peak_at), 0.0, 1.0)) ** 2
    return np.where(u < peak_at, rest_hz + (peak_hz - rest_hz) * rise, peak_hz + (end_hz - peak_hz) * fall)


def _grip(rng, n, rate_hz, threshold, softness, floor=0.0):
    """Quando o atrito pega: porta suave 0..1 que corta o tom em trechos de dezenas de milissegundos."""
    return floor + (1.0 - floor) * D.gate_from(D.smooth_noise(rng, n, rate_hz), threshold, softness)


def _groan(rng, n, pitch, formant_peaks, jitter=0.14, amp_jitter=0.5):
    """Gemido da madeira: pulsos de atrito irregulares passados pelos formantes da folha e do batente."""
    pulses = D.pulse_train(rng, pitch * (1.0 + 0.08 * D.smooth_noise(rng, n, 8)), n, jitter=jitter, amp_jitter=amp_jitter)
    return D.unit_rms(D.formants(pulses, formant_peaks, floor=0.02))


def _squeal(rng, n, pitch, weights, resonance, wobble=0.03, tremble=0.012):
    """Guincho de metal: tom com harmônicos que escorrega no pino seco; a ressonância dá o timbre."""
    bend = pitch * (1.0 + wobble * D.smooth_noise(rng, n, 6)) * (1.0 + tremble * D.smooth_noise(rng, n, 90))
    tone = D.harmonic_tone(bend, n, weights)
    return D.unit_rms(D.formants(tone, resonance, floor=0.05))


def _creak_body(n, peak_at, floor=0.18):
    """Contorno de volume: arranca firme (o atrito vence a inércia), sobe com a velocidade e assenta."""
    t = np.arange(n) / D.SR
    return np.minimum(t / 0.02, 1.0) * (floor + (1.0 - floor) * D.swell(n, peak_at, 0.8))


def _finish_creak(rng, x):
    x = np.tanh(x / 3.5) * 3.5
    return D.reverb(rng, D.lowpass(x, 9500), 0.32, wet=0.12)


@sound_family("door_creak", 4, peak=0.8, group="doors")
def door_creak(rng, index):
    return (_creak_old_wood, _creak_metal, _creak_wood_and_pin, _creak_dry_ratchet)[index](rng)


def _creak_old_wood(rng):
    """1: madeira velha, grave e áspera. Gemido de 50 a 115 Hz com um fio de guincho por cima."""
    n = D.samples(1.3)
    peak_at = 0.48
    groan = _groan(rng, n, _pitch_hump(n, 46, 150, 58, peak_at),
                   [(170, 100, 1.0), (360, 180, 0.9), (820, 380, 0.45), (1500, 600, 0.15)])
    pin = _squeal(rng, n, _pitch_hump(n, 360, 760, 420, peak_at), D.sawtooth_weights(7, 1.6),
                  [(900, 500, 1.0), (1700, 800, 0.4)])
    out = groan * _grip(rng, n, 5, -0.2, 0.4, 0.04) * (1.0 + 0.5 * D.smooth_noise(rng, n, 24)) \
        + 0.5 * pin * _grip(rng, n, 4, 0.0, 0.35, 0.0)
    return _finish_creak(rng, out * _creak_body(n, peak_at))


def _creak_metal(rng):
    """2: guincho de metal, agudo e curto, em duas sílabas (o pino pega, cede e pega de novo)."""
    n = D.samples(0.95)
    peak_at = 0.42
    squeal = _squeal(rng, n, _pitch_hump(n, 820, 2050, 1350, peak_at), D.sawtooth_weights(9, 1.25),
                     [(2400, 1000, 1.0), (1300, 600, 0.5), (4200, 1500, 0.18)], wobble=0.035, tremble=0.02)
    groan = _groan(rng, n, _pitch_hump(n, 80, 135, 90, peak_at), [(260, 160, 1.0), (700, 300, 0.4)])
    u = np.linspace(0.0, 1.0, n)
    two_syllables = 1.0 - 0.8 * np.exp(-(((u - 0.55) / 0.035) ** 2))        # o respiro entre o "ii" e o "iik"
    out = squeal * _grip(rng, n, 19, -0.1, 0.35, 0.1) + 0.14 * groan
    return _finish_creak(rng, out * _creak_body(n, peak_at, 0.1) * two_syllables)


def _creak_wood_and_pin(rng):
    """3: rangido médio, madeira e pino ao mesmo tempo. O mais parecido com uma porta de casa."""
    n = D.samples(1.15)
    peak_at = 0.5
    groan = _groan(rng, n, _pitch_hump(n, 120, 360, 170, peak_at), [(300, 150, 1.0), (900, 400, 0.8), (1900, 700, 0.35)],
                   jitter=0.1, amp_jitter=0.4)
    pin = _squeal(rng, n, _pitch_hump(n, 480, 1500, 650, peak_at), D.sawtooth_weights(8, 1.35),
                  [(1500, 700, 1.0), (2800, 1100, 0.4)])
    out = groan * _grip(rng, n, 7, -0.3, 0.4, 0.1) + 0.8 * pin * _grip(rng, n, 5, 0.1, 0.3)
    return _finish_creak(rng, out * _creak_body(n, peak_at))


def _creak_dry_ratchet(rng):
    """4: dobradiça seca, uma carraca de estalos de atrito (tr-tr-trrr-tr) sem tom sustentado."""
    n = D.samples(1.0)
    peak_at = 0.45
    rate = _pitch_hump(n, 7, 27, 12, peak_at)
    phase = np.cumsum(rate) / D.SR
    hits = np.nonzero(np.diff(np.floor(phase), prepend=np.floor(phase[0])) > 0)[0]
    out = np.zeros(n)
    lift = _pitch_hump(n, 1.0, 1.35, 1.05, peak_at)
    for at in hits:
        at = int(np.clip(at + rng.normal(0.0, 0.0012 * D.SR), 0, n - 1))
        base = rng.uniform(560, 760) * lift[at]
        modes = [(base, 0.011, 0.8), (base * 2.1, 0.007, 0.5), (base * 3.7, 0.004, 0.3)]
        ring = D.modal_strike(rng, modes, D.samples(0.08), spread=0.04)
        ring = ring + 0.5 * _burst(rng, D.samples(0.08), 1200, 5000, 0.006, attack=0.0005)
        D.mix_into(out, ring, at / D.SR, gain=abs(rng.normal(0.7, 0.3)) + 0.15)
        if rng.random() < 0.3:      # a madeira da folha responde com um toque grave
            D.mix_into(out, D.thump(D.samples(0.05), 150, 90, 0.01, 0.015), at / D.SR, gain=0.4)
    return _finish_creak(rng, out * _creak_body(n, peak_at, 0.3))


@sound("door_creak_long", peak=0.8, group="doors")
def door_creak_long(rng):
    seconds = 4.6
    groan = _creak(rng, seconds, (42, 118), (480, 940), 0.55)
    n = len(groan)
    air = _soft_burst(rng, n, 380, 3.0, 0.6) * D.swell(n)
    return D.reverb(rng, groan + 0.06 * air, 0.5, wet=0.15)
