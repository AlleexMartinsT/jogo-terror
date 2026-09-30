"""Validação de sons sem ouvir: métricas numéricas e imagens (forma de onda + espectrograma).

O espectrograma usa eixo de frequência LOGARÍTMICO (30 Hz até Nyquist): nele um drone de
40 Hz, um passo de 200 Hz e um tilintar de 6 kHz ficam todos legíveis.
"""
import numpy as np

from tools import pngwrite

_HEAT_STOPS = (
    (0.00, (4, 4, 12)), (0.20, (40, 12, 90)), (0.45, (150, 30, 90)),
    (0.70, (235, 100, 30)), (0.90, (250, 200, 60)), (1.00, (255, 250, 210)),
)

_FONT = {
    "A": "010101111101101", "B": "110101110101110", "C": "011100100100011", "D": "110101101101110",
    "E": "111100110100111", "F": "111100110100100", "G": "011100101101011", "H": "101101111101101",
    "I": "111010010010111", "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
    "M": "101111111101101", "N": "110101101101101", "O": "010101101101010", "P": "110101110100100",
    "Q": "010101101111011", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010",
    "U": "101101101101111", "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
    "Y": "101101010010010", "Z": "111001010100111",
    "0": "111101101101111", "1": "010110010010111", "2": "110001010100111", "3": "110001010001110",
    "4": "101101111001001", "5": "111100110001110", "6": "011100111101111", "7": "111001010010010",
    "8": "111101111101111", "9": "111101111001110",
    "_": "000000000000111", "-": "000000111000000", ".": "000000000000010", ":": "000010000010000",
    "/": "001001010100100", " ": "000000000000000",
}


# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------
def _rms(x):
    return float(np.sqrt(np.mean(x * x))) if len(x) else 0.0


def spectral_centroid(x, sr):
    spectrum = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    return float(np.sum(freqs * spectrum) / (np.sum(spectrum) + 1e-12))


def attack_ms(x, sr):
    """Tempo entre 10% e 90% do pico absoluto (medido a partir do primeiro cruzamento de 10%)."""
    mag = np.abs(x)
    peak = mag.max()
    if peak <= 0:
        return 0.0
    start = int(np.argmax(mag >= 0.1 * peak))
    top = int(np.argmax(mag >= 0.9 * peak))
    return 1000.0 * max(top - start, 0) / sr


def seam_metrics(x, sr):
    """Continuidade da emenda de um loop.

    jump_ratio: salto entre a última e a primeira amostra, medido em "passos típicos" (p99 de
    |diferença| do sinal). Perto de 1 = emenda invisível; >> 1 = estalo.
    block_diff: diferença de RMS entre os últimos e os primeiros 100 ms, relativa ao RMS total.
    """
    typical = np.percentile(np.abs(np.diff(x)), 99) + 1e-9
    jump_ratio = abs(float(x[0] - x[-1])) / typical
    block = min(int(0.1 * sr), len(x) // 4)
    block_diff = abs(_rms(x[-block:]) - _rms(x[:block])) / (_rms(x) + 1e-9)
    return {"jump_ratio": float(jump_ratio), "block_diff": float(block_diff)}


def describe(x, sr, loop=False):
    """Pico, RMS (dBFS), duração, cruzamentos por zero/s, centroide, ataque e (se loop) emenda."""
    crossings = np.count_nonzero(np.diff(np.signbit(x)))
    stats = {
        "peak": float(np.max(np.abs(x))),
        "rms_db": 20.0 * np.log10(_rms(x) + 1e-9),
        "seconds": len(x) / sr,
        "zcr_per_s": crossings / (len(x) / sr),
        "centroid_hz": spectral_centroid(x, sr),
        "attack_ms": attack_ms(x, sr),
    }
    if loop:
        stats.update(seam_metrics(x, sr))
    return stats


# --------------------------------------------------------------------------
# Imagens
# --------------------------------------------------------------------------
def spectrogram_db(x, sr, n_fft=2048, hop=512):
    """Magnitude em dB (frequências x quadros), janela de Hann. Devolve (freqs, dB)."""
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    window = np.hanning(n_fft)
    starts = np.arange(0, len(x) - n_fft + 1, hop)
    frames = np.stack([x[s:s + n_fft] * window for s in starts], axis=1)
    magnitude = np.abs(np.fft.rfft(frames, axis=0)) / (n_fft / 4.0)
    return np.fft.rfftfreq(n_fft, 1.0 / sr), 20.0 * np.log10(magnitude + 1e-7)


def _heat(values):
    """Mapa de cores 0..1 -> RGB (preto, roxo, laranja, amarelo)."""
    stops = np.array([s for s, _ in _HEAT_STOPS])
    colors = np.array([c for _, c in _HEAT_STOPS], dtype=float)
    v = np.clip(values, 0.0, 1.0)
    return np.stack([np.interp(v, stops, colors[:, k]) for k in range(3)], axis=-1).astype(np.uint8)


def draw_text(image, x, y, text, color=(230, 230, 230), scale=2):
    for index, char in enumerate(text.upper()):
        bits = _FONT.get(char, _FONT[" "])
        for row in range(5):
            for col in range(3):
                if bits[row * 3 + col] == "1":
                    px, py = x + (index * 4 + col) * scale, y + row * scale
                    image[py:py + scale, px:px + scale] = color


def render_panel(x, sr, label, width=640, wave_h=56, spec_h=150, floor_db=-90.0):
    """Um painel: rótulo, forma de onda (em cima) e espectrograma log-frequência (embaixo)."""
    n_fft = 4096 if sr <= 22050 else 2048
    hop = max(len(x) // width // 2, 128)
    freqs, db = spectrogram_db(x, sr, n_fft, hop)
    top = db.max()
    norm = np.clip((db - max(top + floor_db * 0.6, floor_db)) / (top - max(top + floor_db * 0.6, floor_db)), 0, 1)
    log_axis = np.geomspace(30.0, sr / 2.0 - 1.0, spec_h)
    rows = np.searchsorted(freqs, log_axis).clip(0, len(freqs) - 1)
    spec = norm[rows][::-1]
    cols = np.linspace(0, spec.shape[1] - 1, width).astype(int)
    spec_rgb = _heat(spec[:, cols])

    panel = np.zeros((14 + wave_h + spec_h, width, 3), np.uint8)
    panel[:] = (10, 10, 14)
    draw_text(panel, 4, 4, f"{label}  {len(x) / sr:.2f}S {int(sr / 1000)}K", scale=1)
    wave_block = panel[14:14 + wave_h]
    step = max(len(x) // width, 1)
    trimmed = np.abs(x[:step * width]).reshape(-1, step) if len(x) >= step * width else np.abs(x)[None, :]
    envelope = np.interp(np.linspace(0, trimmed.shape[0] - 1, width), np.arange(trimmed.shape[0]), trimmed.max(axis=1))
    peak = max(float(np.max(np.abs(x))), 1e-6)
    half = wave_h // 2
    heights = np.clip((envelope / peak * (half - 1)).astype(int), 0, half - 1)
    for col in range(width):
        wave_block[half - heights[col]:half + heights[col] + 1, col] = (90, 200, 130)
    wave_block[half, :] = np.maximum(wave_block[half, :], (40, 70, 50))
    panel[14 + wave_h:] = spec_rgb
    return panel


def write_panel(path, x, sr, label, **kwargs):
    pngwrite.write_png(path, render_panel(x, sr, label, **kwargs))
    return path


def write_sheet(path, entries, width=640, **kwargs):
    """Empilha painéis. `entries` = [(rótulo, amostras, taxa)]."""
    panels = [render_panel(x, sr, label, width=width, **kwargs) for label, x, sr in entries]
    gap = np.full((3, width, 3), 60, np.uint8)
    stacked = []
    for panel in panels:
        stacked += [panel, gap]
    pngwrite.write_png(path, np.concatenate(stacked, axis=0))
    return path
