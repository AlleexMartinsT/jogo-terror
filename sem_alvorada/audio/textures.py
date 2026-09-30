"""Blocos sonoros reaproveitados pelas receitas: rajadas de ruído, metal, rangido, estalidos."""
import numpy as np

from . import dsp as D


def burst(rng, n, low, high, tau, attack=0.0004, sr=D.SR):
    """Ruído de banda `low..high` com ataque rápido e queda exponencial."""
    return D.band_noise(rng, n, low, high, sr) * D.attack_decay(n, attack, tau, sr)


def soft_burst(rng, n, cutoff, tau, attack, sr=D.SR):
    """Ruído passa-baixa (abafado) com ataque suave: pé no tecido, carpete."""
    return D.unit_rms(D.lowpass(D.white(rng, n), cutoff, sr)) * D.attack_decay(n, attack, tau, sr)


def metal_tick(rng, gain=1.0, ring=0.02):
    """Toque seco de metal (trinco, chave, mola): três modos agudos que morrem rápido."""
    n = D.samples(0.12)
    modes = [(rng.uniform(1700, 2100), ring, 0.6), (rng.uniform(3000, 3500), ring * 0.7, 0.45),
             (rng.uniform(5200, 6200), ring * 0.5, 0.3)]
    return gain * D.modal_strike(rng, modes, n)


def creak_texture(rng, seconds, groan_hz, squeal_hz=None, squeal_gain=0.5, sr=D.SR):
    """Rangido de atrito (stick-slip): trem de pulsos irregulares por formantes de madeira.

    O atrito só "pega" por trechos (`slip`), e o tom desliza de `groan_hz[0]` a `groan_hz[1]`.
    Com `squeal_hz` soma o guincho agudo de uma dobradiça.
    """
    n = D.samples(seconds, sr)
    slip = D.gate_from(D.smooth_noise(rng, n, 9, sr), threshold=-0.45, softness=0.4)
    pitch = D.sweep(*groan_hz, n) * (1.0 + 0.10 * D.smooth_noise(rng, n, 7, sr))
    pulses = D.pulse_train(rng, pitch, n, sr, jitter=0.12, amp_jitter=0.45)
    groan = D.unit_rms(D.formants(pulses, [(230, 130, 1.0), (540, 260, 0.8), (1150, 500, 0.35)], sr))
    out = groan * slip
    if squeal_hz:
        tone_hz = D.sweep(*squeal_hz, n) * (1.0 + 0.04 * D.smooth_noise(rng, n, 6, sr))
        squeal = D.unit_rms(D.harmonic_tone(tone_hz, n, D.sawtooth_weights(6, 1.3), sr))
        out = out + squeal_gain * squeal * D.gate_from(D.smooth_noise(rng, n, 5, sr), 0.1, 0.3)
    return np.tanh(out / 2.0) * 2.0 * D.swell(n, 0.5, 0.8)       # limita os picos dos pulsos


def crackle(rng, seconds, per_second, low, high, sr=D.SR):
    """Estalidos de papel/plástico: impulsos aleatórios de alturas variadas, filtrados."""
    n = D.samples(seconds, sr)
    hits = (rng.random(n) < per_second / sr) * rng.exponential(1.0, n)
    return D.unit_rms(D.bandpass(hits, low, high, sr))


def breath_cycles(rng, seconds, cycle_seconds, inhale_share, band, rasp_hz=0.0, wheeze_hz=0.0, depth=1.0):
    """Respiração periódica: `seconds` é múltiplo de `cycle_seconds`, então o loop emenda."""
    sr = D.SR_LOOP
    n = D.samples(seconds, sr)
    voice = D.formants(D.white(rng, n), [(500, 400, 1.0), (1500, 900, 0.6), (3000, 1300, 0.25)], sr, floor=0.08)
    voice = D.unit_rms(D.bandpass(voice, *band, sr))
    if rasp_hz:
        voice *= 0.55 + 0.45 * D.smooth_noise(rng, n, rasp_hz, sr) ** 2 * 2.0
    envelope = np.zeros(n)
    cycle_n = D.samples(cycle_seconds, sr)
    inhale_n, exhale_n = int(cycle_n * inhale_share), int(cycle_n * (0.92 - inhale_share))
    for cycle in range(int(round(seconds / cycle_seconds))):
        start = cycle * cycle_n
        vary = 1.0 + 0.15 * rng.uniform(-1, 1)
        envelope[start:start + inhale_n] = depth * vary * D.swell(inhale_n, 0.7, 1.5)
        envelope[start + inhale_n + int(0.04 * cycle_n):][:exhale_n] = 0.8 * depth * vary * D.swell(exhale_n, 0.3, 1.5)
    out = voice * envelope
    if wheeze_hz:
        out += 0.12 * D.sine(wheeze_hz * (1 + 0.02 * D.smooth_noise(rng, n, 3, sr)), n, sr) * envelope
    return out
