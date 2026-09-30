"""Ferramentas de síntese sonora (só numpy): ruído, filtros, envelopes, osciladores, reverb e WAV.

Convenções:
- todo sinal é um `np.ndarray` float64 mono, amplitude nominal em [-1, 1];
- filtros atuam no domínio da frequência (FFT), com fase zero e de forma circular. Por isso um
  ruído filtrado com `n` amostras já "emenda" consigo mesmo: é a base dos loops sem estalo;
- os envelopes são aplicados DEPOIS de filtrar (ruído, filtro, envelope), assim o filtro não
  espalha o ataque para antes do início do som.
"""
import wave

import numpy as np

SR = 44100
SR_LOOP = 22050

_TINY = 1e-12


# --------------------------------------------------------------------------
# Tempo e ruído
# --------------------------------------------------------------------------
def samples(seconds, sr=SR):
    return int(round(seconds * sr))


def time_axis(n, sr=SR):
    return np.arange(n) / sr


def white(rng, n):
    return rng.standard_normal(n)


def unit_rms(x):
    return x / (np.sqrt(np.mean(x * x)) + _TINY)


def peak_of(x):
    return float(np.max(np.abs(x))) if len(x) else 0.0


# --------------------------------------------------------------------------
# Filtros por resposta em frequência
# --------------------------------------------------------------------------
def shape(x, gain_of_hz, sr=SR):
    """Multiplica o espectro de `x` por `gain_of_hz(freqs)` (fase zero, circular)."""
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    return np.fft.irfft(np.fft.rfft(x) * gain_of_hz(freqs), n=len(x))


def lowpass(x, cutoff, sr=SR, order=2):
    return shape(x, lambda f: 1.0 / np.sqrt(1.0 + (f / cutoff) ** (2 * order)), sr)


def highpass(x, cutoff, sr=SR, order=2):
    def gain(f):
        safe = np.maximum(f, 1e-3)
        return 1.0 / np.sqrt(1.0 + (cutoff / safe) ** (2 * order))
    return shape(x, gain, sr)


def bandpass(x, low, high, sr=SR, order=2):
    return highpass(lowpass(x, high, sr, order), low, sr, order)


def resonance_gain(freqs, center, q):
    """Módulo de um passa-faixa de 2a ordem: 1 no `center`, cai com Q alto para os lados."""
    safe = np.maximum(freqs, 1e-3)
    return 1.0 / np.sqrt(1.0 + (q * (safe / center - center / safe)) ** 2)


def formants(x, peaks, sr=SR, floor=0.03):
    """Filtro de formantes: `peaks` = [(freq, largura_de_banda, ganho)], mais um piso de ruído."""
    def gain(f):
        total = np.full_like(f, floor)
        for center, bandwidth, height in peaks:
            total += height / (1.0 + ((f - center) / (bandwidth / 2.0)) ** 2)
        return total
    return shape(x, gain, sr)


def pink(rng, n, sr=SR, low=20.0):
    """Ruído rosa (1/f em potência) periódico em `n` amostras."""
    return unit_rms(shape(white(rng, n), lambda f: 1.0 / np.sqrt(np.maximum(f, low)), sr))


def tilt(x, db_per_octave, sr=SR, pivot=1000.0):
    """Inclinação espectral em dB por oitava em torno de `pivot`."""
    return shape(x, lambda f: (np.maximum(f, 20.0) / pivot) ** (db_per_octave / 6.02), sr)


def band_noise(rng, n, low, high, sr=SR, order=2):
    return unit_rms(bandpass(white(rng, n), low, high, sr, order))


# --------------------------------------------------------------------------
# Envelopes
# --------------------------------------------------------------------------
def decay(n, tau, sr=SR):
    """Decaimento exponencial: cai a 37% em `tau` segundos."""
    return np.exp(-time_axis(n, sr) / tau)


def attack_decay(n, attack, tau, sr=SR):
    """Subida linear em `attack` s e decaimento exponencial de constante `tau`."""
    t = time_axis(n, sr)
    rise = np.minimum(t / max(attack, 1.0 / sr), 1.0)
    return rise * np.exp(-np.maximum(t - attack, 0.0) / tau)


def swell(n, peak_at=0.5, power=2.0):
    """Sobe e desce suavemente; `peak_at` (0..1) é onde fica o máximo."""
    u = np.linspace(0.0, 1.0, n)
    up = np.sin(0.5 * np.pi * np.clip(u / peak_at, 0, 1)) ** power
    down = np.cos(0.5 * np.pi * np.clip((u - peak_at) / (1.0 - peak_at), 0, 1)) ** power
    return np.where(u < peak_at, up, down)


def smooth_noise(rng, n, rate_hz, sr=SR):
    """Ruído lento em [-1, 1] com variações a ~`rate_hz`; periódico em `n` amostras."""
    slow = unit_rms(lowpass(white(rng, n), rate_hz, sr, order=3))
    return np.clip(slow / 2.5, -1.0, 1.0)


def gate_from(slow_signal, threshold=0.0, softness=0.25):
    """Transforma um sinal lento em porta suave 0..1 (ligado acima de `threshold`)."""
    return 1.0 / (1.0 + np.exp(-(slow_signal - threshold) / max(softness, 1e-3) * 4.0))


def fade_edges(x, fade_in=0.002, fade_out=0.008, sr=SR):
    y = x.copy()
    a, b = min(samples(fade_in, sr), len(y) // 2), min(samples(fade_out, sr), len(y) // 2)
    if a:
        y[:a] *= np.linspace(0.0, 1.0, a)
    if b:
        y[-b:] *= np.linspace(1.0, 0.0, b)
    return y


# --------------------------------------------------------------------------
# Osciladores
# --------------------------------------------------------------------------
def as_curve(value, n):
    """Aceita número ou curva de n amostras e devolve sempre a curva."""
    arr = np.asarray(value, dtype=float)
    return np.full(n, float(arr)) if arr.ndim == 0 else arr


def sweep(f_start, f_end, n, log=True):
    """Curva de frequência de f_start até f_end (exponencial por padrão, soa como afinação)."""
    if log:
        return np.geomspace(f_start, f_end, n)
    return np.linspace(f_start, f_end, n)


def phase_of(freq, sr=SR, start=0.0):
    return 2.0 * np.pi * (np.cumsum(as_curve(freq, len(freq))) / sr) + start


def sine(freq, n, sr=SR, start=0.0):
    return np.sin(phase_of(as_curve(freq, n), sr, start))


def harmonic_tone(freq, n, weights, sr=SR, start=0.0):
    """Soma aditiva de harmônicos (peso `weights[k]` no harmônico k+1), limitada abaixo de Nyquist."""
    curve = as_curve(freq, n)
    phase = phase_of(curve, sr, start)
    total = np.zeros(n)
    for k, weight in enumerate(weights, start=1):
        audible = (curve * k) < 0.45 * sr
        total += weight * np.sin(k * phase) * audible
    return total


def sawtooth_weights(count, rolloff=1.0):
    return [1.0 / (k ** rolloff) for k in range(1, count + 1)]


def thump(n, f_start, f_end, tau_pitch, tau_amp, sr=SR):
    """Batida grave: seno cuja frequência despenca de f_start a f_end, com decaimento de amplitude."""
    t = time_axis(n, sr)
    freq = f_end + (f_start - f_end) * np.exp(-t / tau_pitch)
    return sine(freq, n, sr) * np.exp(-t / tau_amp)


def modal_strike(rng, modes, n, sr=SR, spread=0.0):
    """Percussão por modos: `modes` = [(freq, tau, amp)] somam senos decaindo. `spread` desafina um pouco."""
    t = time_axis(n, sr)
    total = np.zeros(n)
    for freq, tau, amp in modes:
        detune = 1.0 + spread * rng.uniform(-1.0, 1.0)
        total += amp * np.sin(2 * np.pi * freq * detune * t + rng.uniform(0, 6.28)) * np.exp(-t / tau)
    return total


def pulse_train(rng, freq, n, sr=SR, jitter=0.0, amp_jitter=0.0):
    """Trem de impulsos na taxa `freq` (Hz, número ou curva), com variação de altura por impulso."""
    phase = np.cumsum(as_curve(freq, n)) / sr
    hits = np.nonzero(np.diff(np.floor(phase), prepend=np.floor(phase[0])) > 0)[0]
    heights = np.abs(1.0 + amp_jitter * rng.standard_normal(len(hits)))
    if jitter and len(hits):
        hits = np.clip(hits + (jitter * sr / np.maximum(as_curve(freq, n)[hits], 1.0)
                               * rng.standard_normal(len(hits))).astype(int), 0, n - 1)
    train = np.zeros(n)
    np.add.at(train, hits, heights)
    return train


def saturate(x, drive):
    """Distorção suave (tanh), normalizada para o mesmo pico de entrada."""
    return np.tanh(drive * x) / np.tanh(drive)


# --------------------------------------------------------------------------
# Composição
# --------------------------------------------------------------------------
def silence(seconds, sr=SR):
    return np.zeros(samples(seconds, sr))


def mix_into(canvas, x, at, sr=SR, gain=1.0):
    """Soma `x` em `canvas` a partir de `at` segundos (corta o que passar do fim)."""
    start = samples(at, sr)
    if start >= len(canvas):
        return canvas
    end = min(len(canvas), start + len(x))
    canvas[start:end] += gain * x[:end - start]
    return canvas


def stack(*signals):
    """Soma sinais de comprimentos diferentes alinhados no início (o resultado tem o maior)."""
    out = np.zeros(max(len(s) for s in signals))
    for s in signals:
        out[:len(s)] += s
    return out


def delayed_echoes(x, delays, gains, sr=SR):
    """Cópias atrasadas de `x` (eco seco). Devolve sinal mais longo, com a cauda dos ecos."""
    tail = samples(max(delays), sr)
    out = np.zeros(len(x) + tail)
    out[:len(x)] += x
    for delay, gain in zip(delays, gains):
        out[samples(delay, sr):samples(delay, sr) + len(x)] += gain * x
    return out


def hollow(x, delay, feedback, taps=8, sr=SR):
    """Ressonância de caixa oca: soma cópias atrasadas de `delay` s que decaem por `feedback`."""
    step = samples(delay, sr)
    out = np.zeros(len(x) + taps * step)
    for k in range(taps + 1):
        out[k * step:k * step + len(x)] += (feedback ** k) * x
    return out


# --------------------------------------------------------------------------
# Reverb de sala (convolução com resposta ao impulso sintética)
# --------------------------------------------------------------------------
def room_impulse(rng, rt60, sr=SR, predelay=0.0, damping=0.6):
    """Resposta de sala: ruído em 3 bandas cujos agudos morrem mais rápido (`damping` 0..1)."""
    n = samples(rt60 + predelay + 0.05, sr)
    t = time_axis(n, sr)
    bands = ((20.0, 500.0, 1.0), (500.0, 2000.0, 1.0 - 0.45 * damping), (2000.0, 9000.0, 1.0 - 0.75 * damping))
    response = np.zeros(n)
    for low, high, life in bands:
        tone = band_noise(rng, n, low, high, sr, order=1)
        response += tone * np.exp(-6.9 * t / max(rt60 * life, 0.02))
    response[:samples(predelay, sr)] = 0.0
    return response / (np.sqrt(np.sum(response ** 2)) + _TINY)


def _fft_convolve(x, kernel):
    size = 1 << int(np.ceil(np.log2(len(x) + len(kernel))))
    return np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(kernel, size), size)[:len(x) + len(kernel) - 1]


def reverb(rng, x, rt60, wet=0.25, sr=SR, predelay=0.012, damping=0.6):
    """Mistura o som seco com sua versão reverberada. O resultado é mais longo (cauda da sala)."""
    kernel = room_impulse(rng, rt60, sr, predelay, damping)
    wet_signal = _fft_convolve(x, kernel)
    dry = np.zeros_like(wet_signal)
    dry[:len(x)] = x
    gain = wet * np.sqrt(np.sum(x ** 2) / (np.sum(wet_signal ** 2) + _TINY))
    return (1.0 - wet) * dry + gain * wet_signal


def reverb_circular(rng, x, rt60, wet=0.25, sr=SR, damping=0.6):
    """Reverb que preserva o comprimento: a cauda dá a volta ao início (mantém loops emendados)."""
    kernel = room_impulse(rng, rt60, sr, 0.0, damping)
    folded = np.zeros(len(x))
    for start in range(0, len(kernel), len(x)):
        chunk = kernel[start:start + len(x)]
        folded[:len(chunk)] += chunk
    wet_signal = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(folded), len(x))
    gain = wet * np.sqrt(np.sum(x ** 2) / (np.sum(wet_signal ** 2) + _TINY))
    return (1.0 - wet) * x + gain * wet_signal


# --------------------------------------------------------------------------
# Loops e acabamento
# --------------------------------------------------------------------------
def make_loop(x, length, crossfade):
    """Recorta um loop de `length` amostras cuja emenda é um crossfade de potência constante.

    `x` precisa ter ao menos `length + crossfade` amostras: a sobra do final é misturada
    com o começo, então o último bloco continua naturalmente no primeiro.
    """
    assert len(x) >= length + crossfade, "sinal curto demais para o crossfade"
    out = x[:length].copy()
    ramp = np.linspace(0.0, 1.0, crossfade)
    out[:crossfade] = x[:crossfade] * np.sin(0.5 * np.pi * ramp) + x[length:length + crossfade] * np.cos(0.5 * np.pi * ramp)
    return out


def wrap_tail(x, length):
    """Dobra o excedente além de `length` amostras sobre o início (cauda de reverb ou de nota)."""
    out = x[:length].copy()
    for start in range(length, len(x), length):
        chunk = x[start:start + length]
        out[:len(chunk)] += chunk
    return out


def finalize(x, peak=0.85, fade_in=0.002, fade_out=0.010, sr=SR, remove_dc=True):
    """Acabamento de um som pontual: tira DC, aplica fades curtos e normaliza o pico (sem clipar)."""
    y = x - np.mean(x) if remove_dc else x.copy()
    y = fade_edges(y, fade_in, fade_out, sr)
    return y * (peak / (peak_of(y) + _TINY))


def finalize_loop(x, peak=0.6, remove_dc=True):
    """Acabamento de um loop: sem fades (a emenda já é contínua), só DC e pico."""
    y = x - np.mean(x) if remove_dc else x.copy()
    return y * (peak / (peak_of(y) + _TINY))


# --------------------------------------------------------------------------
# WAV 16 bits mono
# --------------------------------------------------------------------------
def to_int16(x):
    return np.clip(np.round(np.asarray(x) * 32767.0), -32768, 32767).astype("<i2")


def write_wav(path, x, sr):
    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(int(sr))
        fh.writeframes(to_int16(x).tobytes())


def read_wav(path):
    """Lê um WAV 16 bits mono -> (amostras float64 em [-1, 1], taxa)."""
    with wave.open(path, "rb") as fh:
        assert fh.getnchannels() == 1 and fh.getsampwidth() == 2, f"{path}: esperado mono 16 bits"
        rate = fh.getframerate()
        raw = fh.readframes(fh.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0, rate
