"""Receitas de ambiente: loops de fundo da casa e eventos pontuais (rangidos, baques, telefone...)."""
import numpy as np

from . import dsp as D
from .catalog import SR_LOOP, sound, sound_family
from .textures import burst, creak_texture, metal_tick, soft_burst


def _slow_depth(rng, n, rate_hz, depth, sr):
    """Modulação lenta periódica entre (1 - depth) e 1, para dar vida a um loop sem quebrá-lo."""
    return 1.0 - depth * (0.5 - 0.5 * np.clip(D.smooth_noise(rng, n, rate_hz, sr) * 1.6, -1.0, 1.0))


# --------------------------------------------------------------------------
# Loops
# --------------------------------------------------------------------------
@sound("amb_house", sr=SR_LOOP, peak=0.5, loop=True, group="ambience")
def amb_house(rng):
    sr, n = SR_LOOP, D.samples(10.0, SR_LOOP)
    room = D.unit_rms(D.lowpass(D.pink(rng, n, sr), 260, sr))
    air = D.band_noise(rng, n, 400, 1300, sr) * 0.22 * _slow_depth(rng, n, 0.35, 0.8, sr)
    mains = 0.10 * D.sine(60.0, n, sr) + 0.04 * D.sine(120.0, n, sr)
    return room + air + mains


@sound("amb_fridge", sr=SR_LOOP, peak=0.55, loop=True, group="ambience")
def amb_fridge(rng):
    sr, n = SR_LOOP, D.samples(6.0, SR_LOOP)
    motor = D.harmonic_tone(60.0, n, [1.0, 0.5, 0.35, 0.2, 0.1, 0.08], sr)
    beat = 0.6 * D.harmonic_tone(60.5, n, [1.0, 0.3], sr)            # 3 batimentos em 6 s
    rumble = D.unit_rms(D.lowpass(D.white(rng, n), 170, sr)) * (0.6 + 0.4 * D.sine(30.0, n, sr))
    rattle = 0.05 * D.band_noise(rng, n, 500, 1800, sr) * (0.5 + 0.5 * D.sine(30.0, n, sr))
    return motor + beat + 0.8 * rumble + rattle


def _tick(rng, body_hz, gain):
    """Um "tic" de relógio: estalo agudo seco mais um toque de madeira embaixo."""
    n = D.samples(0.12)
    click = burst(rng, n, 2500, 11000, 0.004, attack=0.0002)
    wood = D.modal_strike(rng, [(body_hz, 0.014, 0.6), (body_hz * 1.7, 0.010, 0.3)], n)
    return gain * (click + 0.8 * wood)


@sound("amb_clock_tick", peak=0.6, loop=True, group="ambience")
def amb_clock_tick(rng):
    out = np.zeros(D.samples(4.0))
    for second in range(4):     # tic-toc: o "toc" é mais grave e um pouco mais fraco
        D.mix_into(out, _tick(rng, 900 if second % 2 == 0 else 640, 1.0 if second % 2 == 0 else 0.8), 0.5 + second)
    return out


@sound("amb_wind", sr=SR_LOOP, peak=0.55, loop=True, group="ambience")
def amb_wind(rng):
    sr, n = SR_LOOP, D.samples(12.0, SR_LOOP)
    body = D.band_noise(rng, n, 110, 720, sr) * _slow_depth(rng, n, 0.3, 0.85, sr)
    howl = np.zeros(n)
    for centre in (330.0, 470.0, 610.0):        # frestas: bandas estreitas que aparecem e somem
        narrow = D.unit_rms(D.bandpass(D.white(rng, n), centre * 0.94, centre * 1.06, sr, order=3))
        howl += narrow * _slow_depth(rng, n, 0.22, 1.0, sr) ** 2
    return body + 0.35 * howl


@sound("amb_tv_static", sr=SR_LOOP, peak=0.5, loop=True, group="ambience")
def amb_tv_static(rng):
    sr, n = SR_LOOP, D.samples(4.0, SR_LOOP)
    snow = D.unit_rms(D.highpass(D.white(rng, n), 150, sr)) * (0.85 + 0.15 * D.smooth_noise(rng, n, 14, sr))
    sparks = (rng.random(n) < 40.0 / sr) * rng.exponential(2.0, n) * rng.choice([-1.0, 1.0], n)
    hum = 0.07 * D.sine(60.0, n, sr) + 0.04 * D.sine(120.0, n, sr)
    return snow + 0.5 * D.highpass(sparks, 1500, sr) + hum


@sound("amb_garage_hum", sr=SR_LOOP, peak=0.5, loop=True, group="ambience")
def amb_garage_hum(rng):
    """Lâmpada fluorescente: 120 Hz com muitos harmônicos, e falhas curtas do reator."""
    sr, n = SR_LOOP, D.samples(6.0, SR_LOOP)
    buzz = D.harmonic_tone(120.0, n, [0.7] + [0.9 / (k ** 0.7) for k in range(2, 24)], sr)
    buzz *= 0.75 + 0.25 * D.sine(60.0, n, sr)
    flutter = D.gate_from(D.smooth_noise(rng, n, 0.9, sr), -0.9, 0.2)      # raramente desliga
    rumble = D.unit_rms(D.lowpass(D.pink(rng, n, sr), 200, sr))
    return buzz * (0.6 + 0.4 * flutter) * 0.5 + 0.35 * rumble


# Caixa de música: (semitons a partir de mi5, tempos). Termina em pausa para a cauda cair no início.
_MUSIC_BOX_PHRASE = [
    (None, 1), (0, 1), (3, 1), (7, 2), (5, 1), (3, 1), (0, 2), (-2, 1), (0, 1), (3, 2),
    (0, 1), (-2, 1), (-5, 2), (-2, 1), (0, 1), (3, 1), (7, 1), (10, 2), (7, 1),
    (5, 1), (3, 2), (5, 1), (3, 1), (0, 1), (-2, 1), (0, 4), (None, 2),
]


def _music_box_note(rng, freq):
    """Lâmina de pente metálico: parciais inarmônicos, os graves duram mais que os agudos."""
    n = D.samples(2.4, SR_LOOP)
    life = float(np.clip(700.0 / freq, 0.35, 1.4))
    partials = [(1.0, 1.0 * life, 1.0), (2.32, 0.5 * life, 0.35), (4.25, 0.25 * life, 0.15), (6.63, 0.12 * life, 0.07)]
    modes = [(freq * ratio, tau, amp) for ratio, tau, amp in partials if freq * ratio < 0.45 * SR_LOOP]
    pluck = burst(rng, D.samples(0.02, SR_LOOP), 3000, 9500, 0.003, sr=SR_LOOP)
    tine = D.modal_strike(rng, modes, n, sr=SR_LOOP)
    return D.stack(tine, 0.25 * pluck)


@sound("amb_music_box", sr=SR_LOOP, peak=0.55, loop=True, group="ambience")
def amb_music_box(rng):
    """Melodia lenta e levemente desafinada; a cauda da última nota dá a volta ao início."""
    sr, seconds_per_beat = SR_LOOP, 0.5
    total = sum(beats for _, beats in _MUSIC_BOX_PHRASE) * seconds_per_beat
    out = np.zeros(D.samples(total + 3.0, sr))
    clock = 0.0
    for semitones, beats in _MUSIC_BOX_PHRASE:
        if semitones is not None:
            cents = rng.choice([0.0, 0.0, 0.0, -28.0, 22.0])         # algumas lâminas desafinadas
            freq = 659.25 * 2 ** ((semitones + cents / 100.0) / 12.0)
            D.mix_into(out, _music_box_note(rng, freq), clock + rng.uniform(0.0, 0.012), sr,
                       gain=rng.uniform(0.75, 1.0))
        clock += beats * seconds_per_beat
    mechanism = D.band_noise(rng, len(out), 1800, 4200, sr) * 0.012 * (0.6 + 0.4 * D.sine(9.0, len(out), sr))
    return D.wrap_tail(out + mechanism, D.samples(total, sr))


@sound("amb_radio_static", sr=SR_LOOP, peak=0.5, loop=True, group="ambience")
def amb_radio_static(rng):
    """Rádio fora de estação: chiado AM, estalos, um assobio à deriva e balbucio de voz distante."""
    sr, seconds = SR_LOOP, 6.0
    n = D.samples(seconds, sr)
    hiss = D.band_noise(rng, n, 300, 3600, sr) * (0.8 + 0.2 * D.smooth_noise(rng, n, 8, sr))
    pops = D.bandpass((rng.random(n) < 12.0 / sr) * rng.exponential(3.0, n), 500, 4000, sr)
    drift = 1150.0 + 160.0 * D.sine(1.0 / seconds, n, sr)
    whistle = 0.18 * D.sine(drift, n, sr) * D.gate_from(D.smooth_noise(rng, n, 0.5, sr), 0.35, 0.2)
    glottal = D.pulse_train(rng, 118.0 + 14.0 * D.smooth_noise(rng, n, 1.5, sr), n, sr, jitter=0.05, amp_jitter=0.2)
    syllables = [rng.choice(list(D.VOWELS)) for _ in range(28)]

    def peaks_at(t):
        index = int(t / seconds * len(syllables)) % len(syllables)
        blend = (t / seconds * len(syllables)) % 1.0
        return D.vowel_peaks(syllables[index], syllables[(index + 1) % len(syllables)], blend)

    murmur = D.unit_rms(D.formant_glide(glottal + 0.4 * D.white(rng, n) * 0.2, peaks_at, sr))
    rhythm = np.clip(0.5 + 0.5 * D.smooth_noise(rng, n, 3.5, sr) * 2.0, 0.0, 1.0) ** 2
    murmur = D.bandpass(murmur, 300, 3400, sr) * rhythm * _slow_depth(rng, n, 0.4, 0.9, sr)
    return hiss + 0.5 * pops + whistle + 0.55 * murmur


# --------------------------------------------------------------------------
# Eventos pontuais
# --------------------------------------------------------------------------
def _distant(rng, x, rt60=0.7, wet=0.3, cutoff=3500):
    """Faz um som parecer vindo de outro cômodo: menos agudos e mais sala."""
    return D.reverb(rng, D.lowpass(x, cutoff, order=1), rt60, wet=wet, damping=0.7)


@sound_family("creak", 3, peak=0.7, group="events")
def creak(rng, index):
    recipes = [
        dict(seconds=0.95, groan_hz=(60, 135), squeal_hz=(700, 1000), squeal_gain=0.3),    # tábua do assoalho
        dict(seconds=2.3, groan_hz=(52, 30), squeal_hz=None, squeal_gain=0.0),             # madeiramento assentando
        dict(seconds=1.7, groan_hz=(85, 58), squeal_hz=(520, 430), squeal_gain=0.45),      # parede/porta ao longe
    ][index]
    return _distant(rng, creak_texture(rng, **recipes), rt60=0.6, wet=0.25)


@sound_family("thud", 2, peak=0.85, group="events")
def thud(rng, index):
    n = D.samples(1.0)
    bump = D.thump(n, 88, 44, 0.04, 0.16) + 0.6 * soft_burst(rng, n, 320, 0.07, 0.003)
    if index == 1:      # segundo baque menor e algo rolando
        D.mix_into(bump, D.thump(D.samples(0.4), 76, 42, 0.04, 0.10), 0.27, gain=0.55)
        rolling = D.unit_rms(D.band_noise(rng, D.samples(0.6), 150, 600)) * D.decay(D.samples(0.6), 0.25)
        D.mix_into(bump, rolling * D.smooth_noise(rng, D.samples(0.6), 14).clip(0, 1), 0.35, gain=0.25)
    return _distant(rng, bump, rt60=0.9, wet=0.35, cutoff=1400)


@sound("phone_ring", peak=0.75, group="events")
def phone_ring(rng):
    """Telefone de mesa antigo: martelo batendo alternadamente em dois sinos (~40 batidas/s)."""
    out = np.zeros(D.samples(3.6))
    for burst_start in (0.05, 1.35):
        for strike in range(int(0.9 / 0.025)):
            bell = 1410.0 if strike % 2 == 0 else 1740.0
            modes = [(bell, 0.05, 0.6), (bell * 1.5, 0.035, 0.3), (bell * 2.4, 0.02, 0.2)]
            D.mix_into(out, D.modal_strike(rng, modes, D.samples(0.18)), burst_start + strike * 0.025, gain=0.35)
    out += 0.05 * soft_burst(rng, len(out), 500, 5.0, 0.01)
    return D.reverb(rng, out, 0.6, wet=0.2)


@sound("glass_break", peak=0.9, group="events")
def glass_break(rng):
    n = D.samples(2.0)
    out = 1.0 * burst(rng, n, 2500, 16000, 0.03, attack=0.0002)
    out += 0.5 * D.thump(n, 420, 210, 0.02, 0.05)
    for _ in range(90):     # cacos: milhares de tinidos curtos, cada vez mais espaçados
        when = float(rng.exponential(0.35)) + 0.01
        freq = rng.uniform(2200, 9500)
        shard = D.modal_strike(rng, [(freq, rng.uniform(0.01, 0.06), 1.0), (freq * 1.6, 0.02, 0.4)], D.samples(0.15))
        D.mix_into(out, shard, when, gain=rng.uniform(0.05, 0.3) * np.exp(-when / 0.5))
    return D.reverb(rng, out, 0.6, wet=0.2, damping=0.3)


@sound("clock_chime", peak=0.8, group="events")
def clock_chime(rng):
    """Relógio de pé: sino grave com parciais inarmônicos que batem lentamente."""
    n = D.samples(5.5)
    hum = 196.0
    modes = [(hum * 0.5, 3.6, 0.5), (hum, 3.2, 1.0), (hum * 1.19, 2.4, 0.55), (hum * 1.5, 2.0, 0.45),
             (hum * 2.0, 1.6, 0.4), (hum * 2.55, 1.0, 0.22), (hum * 3.4, 0.6, 0.15), (hum * 1.003, 3.0, 0.5)]
    strike = burst(rng, D.samples(0.06), 500, 4000, 0.01, attack=0.0005)
    bell = D.modal_strike(rng, modes, n, spread=0.002)
    return D.reverb(rng, D.stack(bell, 0.4 * strike), 0.9, wet=0.15)
