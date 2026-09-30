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
