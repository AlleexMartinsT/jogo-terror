"""Receitas de foley: passos por piso, itens e gestos das mãos, lanterna e sons do corpo do jogador.

As portas estão em `recipes_doors`."""
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


@sound("hand_reach", peak=0.35, group="items")
def hand_reach(rng):
    """Braço estendendo: a manga da camisa de flanela roça no tronco. Quase só ar e tecido."""
    n = D.samples(0.5)
    cloth = _soft_burst(rng, n, 1900, 0.4, 0.12) * D.swell(n, 0.55, 1.4)
    fibres = _crackle(rng, 0.5, 40, 900, 4500) * D.swell(n, 0.6, 1.5)
    return 0.8 * cloth + 0.18 * fibres


@sound("flash_pickup", peak=0.7, group="items")
def flash_pickup(rng):
    """Lanterna de metal pesada erguida da superfície: peso na palma, o tubo vibra e a pilha chacoalha dentro."""
    out = np.zeros(D.samples(0.9))
    D.mix_into(out, D.thump(D.samples(0.2), 210, 120, 0.02, 0.05), 0.0, gain=0.7)                  # peso na mão
    tube = [(rng.uniform(560, 680), 0.07, 0.5), (rng.uniform(1350, 1550), 0.05, 0.35), (rng.uniform(2500, 2800), 0.03, 0.2)]
    D.mix_into(out, D.modal_strike(rng, tube, D.samples(0.5), spread=0.02), 0.01, gain=0.5)        # tubo toca
    D.mix_into(out, _burst(rng, D.samples(0.15), 600, 2800, 0.06, attack=0.01), 0.0, gain=0.35)    # dedos no corpo
    for at, gain in ((0.22, 0.5), (0.31, 0.3)):                                                     # pilha chacoalhando
        D.mix_into(out, _metal_tick(rng, gain, ring=0.01), at)
        D.mix_into(out, D.thump(D.samples(0.08), 330, 190, 0.008, 0.02), at, gain=0.3 * gain)
    D.mix_into(out, _soft_burst(rng, D.samples(0.3), 1400, 0.1, 0.03), 0.4, gain=0.25)            # ajeita na mão
    return D.reverb(rng, out, 0.25, wet=0.1)


@sound("key_pickup", peak=0.6, group="items")
def key_pickup(rng):
    """Chaveiro colhido: chaves tilintam umas nas outras ao sair da superfície e o anel arrasta."""
    out = np.zeros(D.samples(1.0))
    D.mix_into(out, _burst(rng, D.samples(0.12), 1500, 6500, 0.05, attack=0.015), 0.0, gain=0.3)    # anel arrasta
    for start, gain in ((0.05, 0.8), (0.12, 0.65), (0.20, 0.5), (0.31, 0.35), (0.44, 0.2)):
        base = rng.uniform(3000, 4400)
        modes = [(base, 0.12, 0.5), (base * 1.52, 0.09, 0.35), (base * 2.31, 0.06, 0.22), (base * 0.61, 0.15, 0.3)]
        D.mix_into(out, D.modal_strike(rng, modes, D.samples(0.4)), start, gain=gain * rng.uniform(0.7, 1.0))
    D.mix_into(out, D.thump(D.samples(0.1), 260, 150, 0.01, 0.02), 0.06, gain=0.2)
    return D.reverb(rng, out, 0.28, wet=0.12)


@sound("battery_clack", peak=0.8, group="items")
def battery_clack(rng):
    """Pilha D batendo na palma e no metal da lanterna: estalo grave e curto, sem o tilintar de `battery_pickup`."""
    out = np.zeros(D.samples(0.5))
    D.mix_into(out, D.thump(D.samples(0.12), 330, 190, 0.008, 0.022), 0.0, gain=0.9)
    cell = [(rng.uniform(1350, 1550), 0.03, 0.5), (rng.uniform(2800, 3100), 0.02, 0.35), (rng.uniform(4300, 4700), 0.012, 0.2)]
    D.mix_into(out, D.modal_strike(rng, cell, D.samples(0.25), spread=0.015), 0.0, gain=0.7)
    D.mix_into(out, _metal_tick(rng, 0.45, ring=0.006), 0.05)                                       # a mola do contato cede
    D.mix_into(out, _burst(rng, D.samples(0.03), 1800, 7000, 0.007, attack=0.0004), 0.0, gain=0.5)
    return D.reverb(rng, out, 0.22, wet=0.1)


@sound("map_fold", peak=0.6, group="items")
def map_fold(rng):
    """Mapa dobrado de novo: três vincos que estalam e o papel deslizando entre eles."""
    n = D.samples(1.1)
    out = np.zeros(n)
    for start, length in ((0.02, 0.28), (0.38, 0.26), (0.72, 0.3)):
        slide = _burst(rng, D.samples(length), 2200, 8500, 0.2, attack=0.03) * D.swell(D.samples(length), 0.4)
        D.mix_into(out, slide + 0.5 * _crackle(rng, length, 90, 1500, 9000), start, gain=0.4)
        crease = _burst(rng, D.samples(0.05), 1600, 7500, 0.012, attack=0.0008)
        D.mix_into(out, crease, start + length * 0.7, gain=0.8)
    return out


@sound("paper_pick", peak=0.5, group="items")
def paper_pick(rng):
    """Folha tirada de uma superfície: raspa curta, a borda se curva e o papel acomoda na mão."""
    n = D.samples(0.5)
    scrape = _burst(rng, n, 2600, 8000, 0.12, attack=0.03) * D.swell(n, 0.3, 1.5)
    out = 0.5 * scrape + 0.6 * _crackle(rng, 0.5, 70, 1700, 8500) * D.swell(n, 0.35, 1.2)
    D.mix_into(out, _burst(rng, D.samples(0.04), 1400, 6000, 0.01, attack=0.0008), 0.28, gain=0.4)
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


@sound("flash_click_on", peak=0.7, group="flashlight")
def flash_click_on(rng):
    """Botão de borracha da lanterna: a cúpula cede, o contato fecha com um estalo seco e a mola volta."""
    out = np.zeros(D.samples(0.22))
    D.mix_into(out, _soft_burst(rng, D.samples(0.04), 1400, 0.012, 0.004), 0.0, gain=0.5)          # borracha cede
    D.mix_into(out, _burst(rng, D.samples(0.05), 2400, 11000, 0.005, attack=0.0002), 0.012, gain=0.9)
    D.mix_into(out, D.thump(D.samples(0.06), 640, 360, 0.008, 0.016), 0.012, gain=0.5)
    D.mix_into(out, _metal_tick(rng, 0.3, ring=0.007), 0.016)
    D.mix_into(out, _burst(rng, D.samples(0.03), 1800, 6000, 0.006, attack=0.0004), 0.07, gain=0.25)   # a cúpula volta
    return out


@sound("flash_click_off", peak=0.6, group="flashlight")
def flash_click_off(rng):
    """O mesmo botão desligando: um tom mais grave e abafado, sem o estalo de contato fechando."""
    out = np.zeros(D.samples(0.22))
    D.mix_into(out, _soft_burst(rng, D.samples(0.04), 1200, 0.012, 0.004), 0.0, gain=0.5)
    D.mix_into(out, _burst(rng, D.samples(0.05), 1700, 8000, 0.006, attack=0.0003), 0.012, gain=0.7)
    D.mix_into(out, D.thump(D.samples(0.06), 500, 270, 0.009, 0.02), 0.012, gain=0.6)
    D.mix_into(out, _metal_tick(rng, 0.2, ring=0.006), 0.016)
    D.mix_into(out, _burst(rng, D.samples(0.03), 1400, 5000, 0.006, attack=0.0004), 0.075, gain=0.2)
    return out


@sound("flash_flicker_burst", peak=0.7, group="flashlight")
def flash_flicker_burst(rng):
    """Três falhas da luz logo depois de acender: a pilha velha mal fecha o contato e o filamento chia."""
    out = np.zeros(D.samples(0.95))
    for start, length, gain in ((0.0, 0.07, 1.0), (0.17, 0.05, 0.8), (0.32, 0.04, 0.65), (0.50, 0.03, 0.4)):
        n = D.samples(length)
        buzz = D.harmonic_tone(rng.uniform(105, 135), n, [1, 0.6, 0.4, 0.5, 0.3]) * D.attack_decay(n, 0.002, length * 0.4)
        crackle = _burst(rng, n, 1800, 9500, length * 0.3, attack=0.0004)
        D.mix_into(out, 0.45 * buzz + 0.85 * crackle, start, gain=gain)
        D.mix_into(out, _metal_tick(rng, 0.25 * gain, ring=0.005), start)
    D.mix_into(out, _burst(rng, D.samples(0.03), 2200, 9000, 0.006), 0.66, gain=0.5)               # a luz firma
    D.mix_into(out, 0.05 * D.harmonic_tone(120.0, D.samples(0.25), [1, 0.5]) * D.swell(D.samples(0.25), 0.2), 0.66)
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


@sound_family("cloth_rustle", 3, peak=0.34, group="body")
def cloth_rustle(rng, index):
    """Camisa de flanela e calça se mexendo, bem baixo: ruído abafado e granulado, sem ataque nenhum."""
    seconds = (0.55, 0.75, 0.42)[index]
    band = ((420, 3400), (520, 2800), (700, 4200))[index]
    n = D.samples(seconds)
    body = D.band_noise(rng, n, *band)
    grain = 0.55 + 0.45 * np.abs(D.smooth_noise(rng, n, (22, 17, 28)[index]))
    fibres = _crackle(rng, seconds, 55, 1200, 6000)
    return (body * grain + 0.25 * fibres) * D.swell(n, (0.4, 0.5, 0.35)[index], 1.3)
