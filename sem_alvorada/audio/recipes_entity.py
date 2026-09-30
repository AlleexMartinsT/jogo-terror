"""Receitas da entidade (o Alto): zumbido grave, respiração, passos, rosnado, grito, sussurro."""
import numpy as np

from . import dsp as D
from .catalog import SR_LOOP, sound, sound_family
from .textures import breath_cycles, burst, creak_texture, crackle, soft_burst


def _slow_depth(rng, n, rate_hz, depth, sr):
    return 1.0 - depth * (0.5 - 0.5 * np.clip(D.smooth_noise(rng, n, rate_hz, sr) * 1.6, -1.0, 1.0))


@sound("ent_drone", sr=SR_LOOP, peak=0.85, loop=True, group="entity")
def ent_drone(rng):
    """Subgrave com dois tons quase iguais (batem a 1,1 Hz) e um trítono dissonante.

    Todas as frequências são múltiplos de 1/8 Hz: cabem em número inteiro de ciclos nos 8 s,
    então o loop emenda sem estalo. A saturação cria harmônicos audíveis em alto-falantes pequenos.
    """
    sr, n = SR_LOOP, D.samples(8.0, SR_LOOP)
    sub = (D.sine(41.0, n, sr) + 0.9 * D.sine(42.125, n, sr) + 0.5 * D.sine(58.0, n, sr)
           + 0.25 * D.sine(123.0, n, sr) + 0.22 * D.sine(130.125, n, sr))
    sub *= 1.0 - 0.25 * D.sine(0.125, n, sr) + 0.04 * D.sine(5.5, n, sr)
    dark = D.unit_rms(D.lowpass(D.pink(rng, n, sr), 140, sr)) * 0.35 * _slow_depth(rng, n, 0.3, 0.7, sr)
    whine = 0.02 * D.sine(1650.0, n, sr) * D.gate_from(D.sine(0.25, n, sr), 0.5, 0.3)
    return D.saturate(sub / 3.0, 2.2) * 3.0 + dark + whine


@sound("ent_breath", sr=SR_LOOP, peak=0.8, loop=True, group="entity")
def ent_breath(rng):
    """Respiração rouca e lenta (2 ciclos de 3 s) com um ronco de voz por baixo."""
    sr, n = SR_LOOP, D.samples(6.0, SR_LOOP)
    air = breath_cycles(rng, 6.0, 3.0, 0.45, (120, 2400), rasp_hz=30, wheeze_hz=0.0, depth=1.0)
    exhale_gate = D.gate_from(D.sine(1.0 / 3.0, n, sr, start=0.6), 0.3, 0.3)
    growl = D.unit_rms(D.formants(D.harmonic_tone(68.0, n, D.sawtooth_weights(14, 1.0), sr),
                                  [(500, 200, 1.0), (900, 300, 0.7)], sr))
    wet = D.unit_rms(D.lowpass(D.white(rng, n), 90, sr)) * (0.5 + 0.5 * D.sine(1.0 / 3.0, n, sr))
    return D.unit_rms(air) + 0.35 * growl * exhale_gate + 0.2 * wet


@sound_family("ent_step", 4, peak=0.95, group="entity")
def ent_step(rng, index):
    """Pé enorme: baque subgrave, sola molhada e um arrasto; a sala devolve o eco."""
    n = D.samples(0.9)
    out = 1.0 * D.thump(n, rng.uniform(58, 68), 30, 0.05, 0.22)
    out += 0.6 * soft_burst(rng, n, 520, 0.08, 0.004)
    out += 0.25 * D.unit_rms(D.lowpass(D.pink(rng, n), 130)) * D.decay(n, 0.3)
    drag = burst(rng, D.samples(0.22), 200, 1400, 0.1, attack=0.05)
    D.mix_into(out, drag, rng.uniform(0.10, 0.18), gain=0.22)
    if index % 2 == 1:      # uma tábua geme sob o peso
        D.mix_into(out, creak_texture(rng, 0.5, (45, 70), (330, 420), 0.2), 0.03, gain=0.2)
    return D.reverb(rng, out, 0.9, wet=0.3, damping=0.6)


@sound_family("ent_step_stalk", 2, peak=0.35, group="entity")
def ent_step_stalk(rng, index):
    """Passo de quem não quer ser ouvido: só o tecido e um roçar, quase sem grave."""
    n = D.samples(0.45)
    out = 0.5 * D.thump(n, 92, 58, 0.03, 0.05) + soft_burst(rng, n, 330, 0.06, 0.012)
    out += 0.2 * burst(rng, n, 600, 1800, 0.08, attack=0.02)
    return D.reverb(rng, out, 0.4, wet=0.12)


@sound("ent_growl", peak=0.9, group="entity")
def ent_growl(rng):
    """Rosnado: pulsos glotais graves e irregulares por formantes de "o/a", com tremor rouco."""
    n = D.samples(1.9)
    t = D.time_axis(n)
    f0 = 56.0 * (1.0 + 0.18 * D.smooth_noise(rng, n, 9)) * (1.0 - 0.18 * np.sin(np.pi * t / t[-1]))
    voice = D.pulse_train(rng, f0, n, jitter=0.25, amp_jitter=0.35)
    voice = D.unit_rms(D.formants(voice, [(480, 160, 1.0), (880, 260, 0.8), (2400, 700, 0.25)]))
    rasp = D.band_noise(rng, n, 300, 3000) * (0.5 + 0.5 * np.sin(2 * np.pi * 26 * t)) ** 2
    growl = D.saturate((voice + 0.5 * rasp) / 3.0, 2.0) * 3.0
    return D.reverb(rng, growl * D.swell(n, 0.35, 0.8), 0.6, wet=0.2)


def _scream_peaks(progress):
    """Formantes de um grito: a boca abre e o trato vocal encurta, então F1..F3 sobem com o tom."""
    u = min(max(progress, 0.0), 1.0)
    return [(700.0 + 900.0 * u, 350.0, 1.0), (1300.0 + 1500.0 * u, 450.0, 0.6), (2800.0 + 1000.0 * u, 600.0, 0.3)]


@sound("ent_scream", peak=0.95, group="entity")
def ent_scream(rng):
    """Grito que sobe: f0 de 280 a 1350 Hz com vibrato, formantes acompanhando, saturado e áspero."""
    seconds = 2.5
    n = D.samples(seconds)
    t = D.time_axis(n)
    rise = D.sweep(280.0, 1350.0, n) * (1.0 + 0.03 * np.sin(2 * np.pi * 6.5 * t) + 0.02 * D.smooth_noise(rng, n, 25))
    voice = D.harmonic_tone(rise, n, D.sawtooth_weights(28, 0.9))
    voice = D.formant_glide(voice, lambda s: _scream_peaks(s / seconds), floor=0.08)
    breath = D.highpass(D.white(rng, n), 1800) * 0.25
    scream = D.saturate((D.unit_rms(voice) + breath) / 3.0, 3.0) * 3.0
    return D.reverb(rng, scream * D.swell(n, 0.5, 0.6), 1.3, wet=0.3)


@sound("ent_whisper", peak=0.6, group="entity")
def ent_whisper(rng):
    """Sussurro ininteligível: ruído por formantes que trocam de vogal a cada sílaba, em três vozes."""
    seconds = 2.8
    n = D.samples(seconds)
    voices = np.zeros(n)
    for layer in range(3):
        syllables = [rng.choice(list(D.VOWELS)) for _ in range(14)]
        offset = layer * 0.09

        def peaks_at(t, syllables=syllables, offset=offset):
            position = ((t + offset) / seconds * len(syllables)) % len(syllables)
            index = int(position)
            return D.vowel_peaks(syllables[index], syllables[(index + 1) % len(syllables)], position - index)

        air = D.highpass(D.white(rng, n), 400)
        breath = D.formant_glide(air, peaks_at, floor=0.1)
        rhythm = np.abs(np.sin(np.pi * (D.time_axis(n) + offset) / seconds * len(syllables))) ** 3
        voices += D.unit_rms(breath) * rhythm * rng.uniform(0.6, 1.0)
    return D.reverb(rng, voices * D.swell(n, 0.5, 0.35), 0.7, wet=0.25)


@sound("ent_door_break", peak=0.95, group="entity")
def ent_door_break(rng):
    n = D.samples(2.4)
    out = 1.0 * burst(rng, n, 300, 9000, 0.04, attack=0.0002) + 0.9 * D.thump(n, 120, 45, 0.06, 0.3)
    for _ in range(60):     # lascas de madeira
        D.mix_into(out, burst(rng, D.samples(0.06), 1000, 7000, 0.01), float(rng.exponential(0.25)),
                   gain=rng.uniform(0.1, 0.5))
    D.mix_into(out, creak_texture(rng, 0.5, (120, 260), (300, 1200), 0.6), 0.03, gain=0.5)
    D.mix_into(out, crackle(rng, 1.4, 50, 800, 5000) * D.decay(D.samples(1.4), 0.5), 0.3, gain=0.3)
    return D.reverb(rng, out, 1.0, wet=0.3)


@sound("ent_stinger", peak=0.95, group="entity")
def ent_stinger(rng):
    """Susto: aglomerado de semitons com ataque instantâneo, boom grave e um guincho que cai."""
    n = D.samples(2.7)
    cluster = np.zeros(n)
    for freq in (196.0, 207.7, 220.0, 293.7, 311.1, 466.2):
        cluster += D.harmonic_tone(freq * rng.uniform(0.997, 1.003), n, D.sawtooth_weights(12, 0.9))
    cluster = D.unit_rms(cluster) * D.attack_decay(n, 0.004, 0.7)
    boom = 1.3 * D.thump(n, 90, 30, 0.08, 0.35)
    screech = D.sine(D.sweep(4200.0, 2100.0, D.samples(0.9)), D.samples(0.9)) * D.attack_decay(D.samples(0.9), 0.003, 0.25)
    out = cluster + boom
    D.mix_into(out, screech + 0.5 * burst(rng, D.samples(0.9), 2000, 9000, 0.2), 0.0, gain=0.5)
    return D.reverb(rng, out, 1.6, wet=0.3)


@sound("ent_static_burst", peak=0.8, group="entity")
def ent_static_burst(rng):
    n = D.samples(0.9)
    chatter = D.gate_from(D.smooth_noise(rng, n, 40), -0.2, 0.3)
    out = D.band_noise(rng, n, 200, 9000) * chatter * D.attack_decay(n, 0.004, 0.45)
    for _ in range(4):      # blips tonais como sinal roubado
        blip_n = D.samples(rng.uniform(0.02, 0.05))
        D.mix_into(out, D.sine(rng.uniform(700, 2600), blip_n) * D.swell(blip_n), rng.uniform(0.02, 0.5), gain=0.35)
    return out
