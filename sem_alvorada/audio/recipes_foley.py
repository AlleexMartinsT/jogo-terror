"""Receitas de foley: passos por piso, portas, itens, lanterna e sons do corpo do jogador."""
import numpy as np

from . import dsp as D
from .catalog import SR_LOOP, sound, sound_family
from .textures import breath_cycles
from .textures import burst as _burst
from .textures import creak_texture as _creak
from .textures import crackle as _crackle
from .textures import metal_tick as _metal_tick
from .textures import soft_burst as _soft_burst


def _two_contacts(rng, contact, toe_gain, delay_range):
    """Passo = calcanhar + ponta do pé (mesmo tipo de contato, mais fraco, um instante depois)."""
    heel, toe = contact(rng, 1.0), contact(rng, toe_gain)
    out = np.zeros(max(len(heel), len(toe)) + D.samples(delay_range[1]))
    D.mix_into(out, heel, 0.0)
    D.mix_into(out, toe, rng.uniform(*delay_range))
    return out


# --------------------------------------------------------------------------
# Passos: madeira, carpete, azulejo, concreto, escada
# --------------------------------------------------------------------------
def _wood_contact(rng, scale):
    n = D.samples(0.4)
    base = rng.uniform(165, 235)
    boards = D.modal_strike(rng, [(base, 0.16, 0.5), (base * 1.71, 0.11, 0.3), (base * 2.63, 0.08, 0.2),
                                  (base * 4.1, 0.05, 0.1)], n, spread=0.03)
    knock = _burst(rng, n, 250, 1800, 0.03)
    click = _burst(rng, n, 2500, 9000, 0.004)
    body = D.thump(n, base * 0.85, base * 0.42, 0.02, 0.07)
    return scale * (0.7 * body + 0.6 * knock + 0.3 * click + 0.6 * boards)


@sound_family("step_wood", 4, peak=0.78, group="steps")
def step_wood(rng, index):
    out = _two_contacts(rng, _wood_contact, 0.45, (0.085, 0.13))
    if index in (1, 3):     # tábua que estala sob o peso
        plank = _creak(rng, rng.uniform(0.14, 0.24), (70, 115), (520, 700), 0.25)
        D.mix_into(out, plank, rng.uniform(0.02, 0.06), gain=0.12)
    return D.reverb(rng, out, 0.18, wet=0.12)


def _carpet_contact(rng, scale):
    n = D.samples(0.3)
    thud = D.thump(n, 95, 52, 0.03, 0.05)
    fluff = _soft_burst(rng, n, rng.uniform(500, 800), 0.05, 0.006)
    rustle = _burst(rng, n, 1000, 2800, 0.04, attack=0.005)
    return scale * (0.6 * thud + 0.75 * fluff + 0.08 * rustle)


@sound_family("step_carpet", 4, peak=0.5, group="steps")
def step_carpet(rng, index):
    return _two_contacts(rng, _carpet_contact, 0.4, (0.10, 0.14))


def _tile_contact(rng, scale):
    n = D.samples(0.3)
    tap = _burst(rng, n, 1500, 12000, 0.006, attack=0.0003)
    ring = D.modal_strike(rng, [(rng.uniform(2200, 2500), 0.02, 0.4), (3700, 0.012, 0.25), (5200, 0.008, 0.15)], n)
    body = D.thump(n, 190, 110, 0.01, 0.03)
    return scale * (tap + ring + 0.35 * body)


@sound_family("step_tile", 4, peak=0.8, group="steps")
def step_tile(rng, index):
    out = _two_contacts(rng, _tile_contact, 0.5, (0.075, 0.10))
    return D.reverb(rng, out, 0.35, wet=0.18, damping=0.2)


def _concrete_contact(rng, scale):
    n = D.samples(0.35)
    grit = D.unit_rms(D.bandpass(D.white(rng, n), 600, 4500)) * (rng.random(n) ** 3 * 3.0)
    scuff = grit * D.attack_decay(n, 0.002, 0.05)
    thump = D.thump(n, 110, 65, 0.04, 0.06)
    click = _burst(rng, n, 3000, 12000, 0.006)
    return scale * (0.55 * scuff + 0.7 * thump + 0.3 * click)


@sound_family("step_concrete", 4, peak=0.8, group="steps")
def step_concrete(rng, index):
    dry = _two_contacts(rng, _concrete_contact, 0.5, (0.09, 0.12))
    slap = D.delayed_echoes(dry, [rng.uniform(0.08, 0.10), rng.uniform(0.17, 0.20)], [0.25, 0.12])
    return D.reverb(rng, slap, 1.1, wet=0.35, predelay=0.025, damping=0.5)


def _stairs_contact(rng, scale):
    n = D.samples(0.6)
    cavity = rng.uniform(115, 150)
    boom = D.modal_strike(rng, [(cavity, 0.22, 1.0), (cavity * 2.03, 0.14, 0.45)], n, spread=0.02)
    knock = D.hollow(_burst(rng, D.samples(0.15), 300, 900, 0.03), rng.uniform(0.006, 0.009), 0.55)
    out = np.zeros(n)
    out[:min(n, len(knock))] += 0.55 * knock[:n]
    return scale * (out + boom)


@sound_family("step_stairs", 4, peak=0.88, group="steps")
def step_stairs(rng, index):
    out = _two_contacts(rng, _stairs_contact, 0.6, (0.11, 0.15))
    return D.reverb(rng, out, 0.3, wet=0.15)


# --------------------------------------------------------------------------
# Portas
# --------------------------------------------------------------------------
def _latch(rng, gain=1.0):
    """Lingueta do trinco: toque metálico com um baque de madeira embaixo."""
    n = D.samples(0.15)
    return gain * D.stack(_metal_tick(rng, 0.7), 0.5 * D.thump(n, 240, 130, 0.01, 0.025))


def _wood_stop(rng, gain=1.0):
    """Folha encostando no batente: baque surdo curto."""
    n = D.samples(0.3)
    return gain * (D.thump(n, 105, 55, 0.03, 0.07) + 0.4 * _soft_burst(rng, n, 700, 0.04, 0.002))


@sound("door_open", peak=0.8, group="doors")
def door_open(rng):
    out = np.zeros(D.samples(1.6))
    D.mix_into(out, _latch(rng), 0.02)
    D.mix_into(out, _creak(rng, 1.0, (52, 96), (620, 860), 0.4), 0.14, gain=0.85)
    D.mix_into(out, _soft_burst(rng, D.samples(1.0), 450, 0.5, 0.3) * D.swell(D.samples(1.0)), 0.14, gain=0.05)
    D.mix_into(out, _wood_stop(rng, 0.35), 1.2)
    return D.reverb(rng, out, 0.35, wet=0.15)


@sound("door_close", peak=0.8, group="doors")
def door_close(rng):
    out = np.zeros(D.samples(1.4))
    D.mix_into(out, _creak(rng, 0.85, (96, 55), (840, 610), 0.35), 0.02, gain=0.8)
    D.mix_into(out, _soft_burst(rng, D.samples(0.8), 450, 0.4, 0.3) * D.swell(D.samples(0.8)), 0.02, gain=0.05)
    D.mix_into(out, _wood_stop(rng, 0.8), 0.86)
    D.mix_into(out, _latch(rng, 1.1), 0.88)
    return D.reverb(rng, out, 0.35, wet=0.15)


@sound("door_slam", peak=0.95, group="doors")
def door_slam(rng):
    n = D.samples(2.2)
    out = np.zeros(n)
    boom = D.thump(n, 75, 32, 0.05, 0.25)
    slab = _soft_burst(rng, n, 1500, 0.08, 0.001)
    wood = D.modal_strike(rng, [(110, 0.25, 0.6), (190, 0.18, 0.5), (340, 0.14, 0.35), (520, 0.10, 0.25)], n, spread=0.02)
    crack = _burst(rng, n, 1500, 12000, 0.012, attack=0.0002)
    out += 1.0 * boom + 0.8 * slab + 0.6 * wood + 0.6 * crack
    D.mix_into(out, _latch(rng, 0.9), 0.008)
    for k in range(6):      # o batente e a folha vibram depois do impacto
        D.mix_into(out, _burst(rng, D.samples(0.05), 800, 3000, 0.01), 0.06 + 0.045 * k, gain=0.35 * 0.7 ** k)
    return D.reverb(rng, out, 0.9, wet=0.28, predelay=0.02)[:D.samples(2.2)]


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


@sound("door_creak_long", peak=0.8, group="doors")
def door_creak_long(rng):
    seconds = 4.6
    groan = _creak(rng, seconds, (42, 118), (480, 940), 0.55)
    n = len(groan)
    air = _soft_burst(rng, n, 380, 3.0, 0.6) * D.swell(n)
    return D.reverb(rng, groan + 0.06 * air, 0.5, wet=0.15)


# --------------------------------------------------------------------------
# Itens
# --------------------------------------------------------------------------
@sound("pickup", peak=0.6, group="items")
def pickup(rng):
    n = D.samples(0.38)
    out = 0.6 * _burst(rng, n, 700, 3000, 0.05, attack=0.004)
    D.mix_into(out, _burst(rng, D.samples(0.15), 1500, 5000, 0.03, attack=0.002), 0.09, gain=0.5)
    D.mix_into(out, D.thump(D.samples(0.12), 190, 100, 0.02, 0.03), 0.16, gain=0.6)
    return D.reverb(rng, out, 0.2, wet=0.1)


@sound("battery_pickup", peak=0.75, group="items")
def battery_pickup(rng):
    n = D.samples(0.7)
    modes = [(2050, 0.13, 0.5), (3350, 0.09, 0.4), (5100, 0.06, 0.25), (6800, 0.04, 0.12)]
    clink = D.modal_strike(rng, modes, n, spread=0.01)
    out = clink + 0.35 * _burst(rng, n, 800, 3500, 0.04, attack=0.003)
    D.mix_into(out, D.modal_strike(rng, modes, D.samples(0.4), spread=0.02), 0.14, gain=0.35)
    return D.reverb(rng, out, 0.25, wet=0.12)


@sound("battery_insert", peak=0.8, group="items")
def battery_insert(rng):
    out = np.zeros(D.samples(0.95))
    D.mix_into(out, _burst(rng, D.samples(0.18), 1800, 6000, 0.08, attack=0.05), 0.0, gain=0.3)   # deslizando
    D.mix_into(out, _metal_tick(rng, 1.0, ring=0.03), 0.20)
    spring = D.modal_strike(rng, [(880, 0.12, 0.5), (1350, 0.07, 0.3)], D.samples(0.3))
    D.mix_into(out, spring, 0.20, gain=0.5)
    D.mix_into(out, _burst(rng, D.samples(0.08), 900, 4000, 0.01), 0.42, gain=0.6)      # tampa
    D.mix_into(out, D.thump(D.samples(0.15), 260, 150, 0.01, 0.03), 0.42, gain=0.7)
    D.mix_into(out, _metal_tick(rng, 0.6, ring=0.015), 0.50)
    return D.reverb(rng, out, 0.25, wet=0.1)


@sound("paper_rustle", peak=0.6, group="items")
def paper_rustle(rng):
    n = D.samples(0.95)
    body = _burst(rng, n, 2500, 8500, 0.5, attack=0.02) * D.swell(n, 0.35)
    crackles = _crackle(rng, 0.95, 90, 1800, 9000) * D.swell(n, 0.4, 1.0)
    return 0.5 * body + 0.7 * crackles


@sound("key_jingle", peak=0.7, group="items")
def key_jingle(rng):
    out = np.zeros(D.samples(1.5))
    for start, gain in ((0.0, 1.0), (0.09, 0.8), (0.17, 0.6), (0.30, 0.7), (0.38, 0.5), (0.52, 0.35)):
        base = rng.uniform(3200, 4600)
        modes = [(base, 0.22, 0.5), (base * 1.52, 0.16, 0.35), (base * 2.31, 0.10, 0.22), (base * 0.61, 0.28, 0.3)]
        D.mix_into(out, D.modal_strike(rng, modes, D.samples(0.6)), start, gain=gain * rng.uniform(0.6, 1.0))
    return D.reverb(rng, out, 0.3, wet=0.12)


@sound("map_unfold", peak=0.6, group="items")
def map_unfold(rng):
    n = D.samples(1.6)
    out = np.zeros(n)
    for start, length in ((0.02, 0.45), (0.5, 0.35), (0.9, 0.5)):     # cada dobra que se abre
        fold = _burst(rng, D.samples(length), 2000, 8000, 0.3, attack=0.05) * D.swell(D.samples(length), 0.5)
        D.mix_into(out, fold + 0.6 * _crackle(rng, length, 80, 1500, 9000), start, gain=0.5)
    D.mix_into(out, _burst(rng, D.samples(0.3), 500, 3500, 0.06, attack=0.005), 1.35, gain=0.6)   # estala reto
    return out


# --------------------------------------------------------------------------
# Lanterna
# --------------------------------------------------------------------------
@sound("flash_on", peak=0.7, group="flashlight")
def flash_on(rng):
    n = D.samples(0.18)
    out = _burst(rng, n, 2500, 12000, 0.004, attack=0.0002) + 0.6 * D.thump(n, 700, 380, 0.008, 0.018)
    D.mix_into(out, _metal_tick(rng, 0.35, ring=0.008), 0.004)
    return out


@sound("flash_off", peak=0.6, group="flashlight")
def flash_off(rng):
    n = D.samples(0.18)
    out = 0.7 * _burst(rng, n, 1800, 9000, 0.005, attack=0.0003) + 0.7 * D.thump(n, 520, 280, 0.01, 0.022)
    D.mix_into(out, _metal_tick(rng, 0.25, ring=0.008), 0.006)
    return out


@sound("flash_flicker", peak=0.7, group="flashlight")
def flash_flicker(rng):
    out = np.zeros(D.samples(0.75))
    for start in (0.0, 0.11, 0.19, 0.33, 0.41, 0.55):
        length = rng.uniform(0.03, 0.07)
        buzz = D.harmonic_tone(120.0, D.samples(length), [1, 0.6, 0.4, 0.5, 0.3]) * D.attack_decay(D.samples(length), 0.002, 0.03)
        crackle = _burst(rng, D.samples(length), 2000, 9000, 0.015, attack=0.0005)
        D.mix_into(out, 0.5 * buzz + 0.8 * crackle, start, gain=rng.uniform(0.5, 1.0))
    D.mix_into(out, _burst(rng, D.samples(0.02), 2500, 12000, 0.004), 0.68, gain=0.8)
    return out


# --------------------------------------------------------------------------
# Corpo do jogador
# --------------------------------------------------------------------------
@sound("breath_calm", sr=SR_LOOP, peak=0.5, loop=True, group="body")
def breath_calm(rng):
    return breath_cycles(rng, 8.0, 4.0, 0.42, (280, 3200), depth=0.8)


@sound("breath_heavy", sr=SR_LOOP, peak=0.7, loop=True, group="body")
def breath_heavy(rng):
    return breath_cycles(rng, 4.0, 1.0, 0.45, (200, 4500), rasp_hz=40, wheeze_hz=640)


@sound("heartbeat", sr=SR_LOOP, peak=0.85, loop=True, group="body")
def heartbeat(rng):
    sr, period, beats = SR_LOOP, 0.86, 4
    n = D.samples(period * beats, sr)
    out = np.zeros(n)
    lub = D.thump(D.samples(0.35, sr), 74, 46, 0.035, 0.10, sr) + 0.3 * _soft_burst(rng, D.samples(0.35, sr), 130, 0.05, 0.004, sr)
    dub = D.thump(D.samples(0.30, sr), 64, 42, 0.03, 0.085, sr)
    for beat in range(beats):
        D.mix_into(out, lub, 0.30 + beat * period, sr)
        D.mix_into(out, dub, 0.30 + beat * period + 0.29, sr, gain=0.65)
    return out


@sound("gasp", peak=0.7, group="body")
def gasp(rng):
    n = D.samples(0.8)
    air = D.unit_rms(D.formants(D.white(rng, n), [(700, 500, 1.0), (1800, 1000, 0.6), (3200, 1400, 0.3)], floor=0.05))
    air = air * D.attack_decay(n, 0.05, 0.16)
    pitch = D.sweep(170, 240, n) * (1 + 0.01 * np.sin(2 * np.pi * 6 * D.time_axis(n)))
    voice = D.formants(D.harmonic_tone(pitch, n, D.sawtooth_weights(10, 1.0)), [(750, 200, 1.0), (1250, 250, 0.6)])
    voice = D.unit_rms(voice) * D.attack_decay(n, 0.06, 0.12)
    return air + 0.25 * voice
