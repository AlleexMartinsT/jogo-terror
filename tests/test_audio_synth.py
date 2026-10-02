"""Testes da síntese sonora: catálogo completo, formato, loops sem estalo, espectros coerentes.

    python tests/test_audio_synth.py      (ou pytest)
"""
import os
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sem_alvorada import AUDIO_DIR  # noqa: E402
from sem_alvorada.audio import analysis, dsp, synth  # noqa: E402
from sem_alvorada.audio.catalog import REQUIRED_SOUNDS, SPECS, STEP_SURFACES, loop_names  # noqa: E402

BUDGET_BYTES = 20 * 1024 * 1024
_cache = {}
synth.load_recipes()


def _sound(name):
    """Lê o WAV do disco (gerando o catálogo na primeira vez, se faltar algo)."""
    if not _cache:
        synth.ensure_all(log=lambda *_: None)
    if name not in _cache:
        _cache[name] = dsp.read_wav(synth.wav_path(name))
    return _cache[name]


def _band_energy(x, sr, low, high):
    spectrum = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    return float(spectrum[(freqs >= low) & (freqs < high)].sum() / (spectrum.sum() + 1e-12))


def _centroid_of(x, sr):
    return analysis.spectral_centroid(x, sr)


def test_catalog_has_every_contract_name():
    synth.selected_names()
    missing = [n for n in REQUIRED_SOUNDS if n not in SPECS]
    assert not missing, f"receitas ausentes: {missing}"
    assert len(REQUIRED_SOUNDS) == 99
    for surface in STEP_SURFACES:
        assert all(f"step_{surface}_{i}" in SPECS for i in range(1, 5))


def test_files_exist_with_correct_format():
    for name in REQUIRED_SOUNDS:
        path = synth.wav_path(name)
        _sound(name)
        with wave.open(path, "rb") as fh:
            assert fh.getnchannels() == 1, f"{name}: não é mono"
            assert fh.getsampwidth() == 2, f"{name}: não é 16 bits"
            assert fh.getframerate() in (44100, 22050), f"{name}: taxa {fh.getframerate()}"
            if name in loop_names() and fh.getframerate() == 44100:
                assert name == "amb_clock_tick", f"{name}: loop longo deveria ser 22,05 kHz"


def test_duration_peak_and_no_clipping():
    for name in REQUIRED_SOUNDS:
        x, sr = _sound(name)
        stats = analysis.describe(x, sr)
        assert not np.isnan(x).any(), f"{name}: NaN"
        assert 0.1 <= stats["seconds"] <= 20.0, f"{name}: duração {stats['seconds']:.2f}s"
        assert 0.3 <= stats["peak"] < 0.9999, f"{name}: pico {stats['peak']:.3f}"
        assert np.count_nonzero(np.abs(x) > 0.9995) < 3, f"{name}: clipando"
        assert stats["rms_db"] > -60.0, f"{name}: quase mudo"
        assert abs(np.mean(x)) < 0.02, f"{name}: DC {np.mean(x):.3f}"


def test_loops_are_seamless():
    assert len(loop_names()) == 15
    for name in loop_names():
        x, sr = _sound(name)
        seam = analysis.seam_metrics(x, sr)
        assert seam["jump_ratio"] < 2.0, f"{name}: estalo na emenda ({seam['jump_ratio']:.2f})"
        assert seam["block_diff"] < 0.6, f"{name}: último e primeiro bloco diferem ({seam['block_diff']:.2f})"
        doubled = np.concatenate([x, x])
        steps = np.abs(np.diff(doubled))
        assert steps[len(x) - 1] < 2.5 * np.percentile(steps, 99.5) + 1e-6, f"{name}: salto ao repetir"


def test_total_size_under_budget():
    total = synth.total_bytes()
    assert total < BUDGET_BYTES, f"{total / 1e6:.1f} MB"


def test_synthesis_is_deterministic():
    for name in ("step_wood_2", "door_slam", "ent_scream", "amb_music_box", "ent_drone"):
        first, _ = synth.render(name)
        second, _ = synth.render(name)
        assert np.array_equal(dsp.to_int16(first), dsp.to_int16(second)), name


def test_seeds_differ_between_variations():
    a, _ = _sound("step_wood_1")
    b, _ = _sound("step_wood_2")
    n = min(len(a), len(b))
    assert not np.allclose(a[:n], b[:n]), "variações idênticas"


def test_steps_have_short_attack_and_distinct_bodies():
    centroids = {}
    for surface in STEP_SURFACES:
        for i in range(1, 5):
            x, sr = _sound(f"step_{surface}_{i}")
            assert analysis.attack_ms(x, sr) < 15.0, f"step_{surface}_{i}: ataque lento"
        x, sr = _sound(f"step_{surface}_1")
        centroids[surface] = _band_energy(x, sr, 0, 400)
    assert centroids["stairs"] > centroids["tile"], "escada deveria ser mais grave que o azulejo"
    assert centroids["carpet"] > centroids["tile"], "carpete deveria ser mais abafado que o azulejo"
    peak_carpet = np.abs(_sound("step_carpet_1")[0]).max()
    peak_wood = np.abs(_sound("step_wood_1")[0]).max()
    assert peak_carpet < peak_wood, "carpete deve ser o mais fraco"
    tile, sr = _sound("step_tile_1")
    concrete, _ = _sound("step_concrete_1")
    assert len(concrete) > len(tile) * 1.5, "concreto deve ecoar mais que azulejo"


def test_entity_drone_is_sub_bass_and_beats():
    x, sr = _sound("ent_drone")
    assert _band_energy(x, sr, 0, 200) > 0.9, "drone precisa ser grave"
    spectrum = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    assert 38.0 <= freqs[np.argmax(spectrum)] <= 60.0
    envelope = np.abs(x).reshape(-1, 441).max(axis=1)
    assert envelope.max() / max(envelope.min(), 1e-6) > 1.15, "sem batimento audível"


def _strongest_partial(x, sr, low=150.0, high=3000.0):
    spectrum = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    band = (freqs >= low) & (freqs <= high)
    return float(freqs[band][np.argmax(spectrum[band])])


def test_scream_rises_in_pitch():
    x, sr = _sound("ent_scream")
    third = len(x) // 3
    early = _strongest_partial(x[:third // 2], sr)
    late = _strongest_partial(x[third:third + third // 2], sr)
    assert late > early * 1.8, f"grito não sobe ({early:.0f} -> {late:.0f} Hz)"


def test_body_and_ambience_frequency_signatures():
    heart, sr = _sound("heartbeat")
    assert _band_energy(heart, sr, 0, 150) > 0.85
    fridge, sr = _sound("amb_fridge")
    spectrum = np.abs(np.fft.rfft(fridge))
    freqs = np.fft.rfftfreq(len(fridge), 1.0 / sr)
    assert abs(freqs[np.argmax(spectrum)] - 60.0) < 2.0, "geladeira deve zumbir em 60 Hz"
    garage, sr = _sound("amb_garage_hum")
    assert _band_energy(garage, sr, 100, 400) > 0.3
    wind, sr = _sound("amb_wind")
    assert _band_energy(wind, sr, 80, 1000) > 0.85


def test_clock_tick_repeats_every_second():
    x, sr = _sound("amb_clock_tick")
    envelope = np.abs(x)
    peaks = [int(np.argmax(envelope[k * sr:(k + 1) * sr])) for k in range(4)]
    assert max(peaks) - min(peaks) < 0.02 * sr, "ticks fora do compasso"
    assert envelope[:int(0.4 * sr)].max() < 0.05 * envelope.max()


def test_heartbeat_has_two_beats_per_cycle():
    x, sr = _sound("heartbeat")
    window = int(0.04 * sr)
    envelope = np.sqrt(np.convolve(x * x, np.ones(window) / window, mode="same"))
    loud = envelope > 0.4 * envelope.max()
    segments = np.count_nonzero(np.diff(loud.astype(int)) == 1) + int(loud[0])
    assert segments == 8, f"esperado 4 lub-dub (8 pulsos), achei {segments}"


def test_stalk_step_is_quiet_and_heavy_step_is_deep():
    heavy, sr = _sound("ent_step_1")
    assert _band_energy(heavy, sr, 0, 250) > 0.5
    assert np.abs(_sound("ent_step_stalk_1")[0]).max() < np.abs(heavy).max() * 0.5


def _strongest_partial_in_windows(x, sr, band, parts=8):
    """Parcial mais forte de `band` em `parts` janelas do trecho ativo do som."""
    active = np.nonzero(np.abs(x) > 0.05 * np.abs(x).max())[0]
    x = x[active[0]:active[-1]]
    size = len(x) // parts
    return [_strongest_partial(x[i * size:(i + 1) * size], sr, *band) for i in range(parts)]


def _band_profile(x, sr, bands=32):
    spectrum = np.abs(np.fft.rfft(x * np.hanning(len(x)), 16384)) ** 2
    freqs = np.fft.rfftfreq(16384, 1.0 / sr)
    edges = np.geomspace(60, 16000, bands + 1)
    energy = np.array([spectrum[(freqs >= lo) & (freqs < hi)].sum() for lo, hi in zip(edges, edges[1:])])
    return 10.0 * np.log10(energy / energy.sum() + 1e-12)


def test_door_creaks_are_different_and_pitch_rises_then_falls():
    names = [f"door_creak_{i}" for i in range(1, 5)]
    profiles = {n: _band_profile(*_sound(n)) for n in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            distance = float(np.sqrt(np.mean((profiles[a] - profiles[b]) ** 2)))
            assert distance > 6.0, f"{a} e {b} soam parecidos ({distance:.1f} dB)"
    for name, band in (("door_creak_2", (600, 3000)), ("door_creak_3", (400, 2000))):
        x, sr = _sound(name)
        contour = _strongest_partial_in_windows(x, sr, band)
        peak = max(contour[2:6])
        assert peak > 1.3 * contour[0] and peak > 1.3 * contour[-1], f"{name}: afinação sem corcova {contour}"
    for name in names:
        x, sr = _sound(name)
        window = int(0.02 * sr)
        rms = np.sqrt(np.mean(x[:len(x) // window * window].reshape(-1, window) ** 2, axis=1))
        active = rms[rms > 0.05 * rms.max()]
        assert active.std() / active.mean() > 0.4, f"{name}: volume constante demais, vira zumbido"
        assert 0.9 <= len(x) / sr <= 2.0


def test_door_motion_sounds_carry_no_creak_and_latch_is_a_click():
    latch, sr = _sound("door_latch")
    assert analysis.attack_ms(latch, sr) < 15.0 and _band_energy(latch, sr, 1500, 9000) > 0.35, "o trinco é um clique de metal"
    handle, sr = _sound("door_handle")
    assert len(handle) / sr < 1.0
    for name in ("door_open", "door_open_soft", "door_close"):
        x, sr = _sound(name)
        assert _band_energy(x, sr, 0, 300) < 0.45, f"{name}: grave demais, parece gemido"
        assert _band_energy(x, sr, 200, 2000) > 0.2, f"{name}: sem a madeira e o ar da folha"
    soft, _ = _sound("door_open_soft")
    normal, _ = _sound("door_open")
    assert np.abs(soft).max() < np.abs(normal).max()


def test_interaction_sounds_have_their_character():
    for name in ("flash_click_on", "flash_click_off", "battery_clack", "ui_wheel_tick"):
        x, sr = _sound(name)
        assert analysis.attack_ms(x, sr) < 15.0, f"{name}: ataque lento"
    for name in ("flash_click_on", "flash_click_off", "ui_wheel_open", "ui_wheel_close"):
        assert len(_sound(name)[0]) / _sound(name)[1] < 0.5
    assert len(_sound("ui_wheel_tick")[0]) / _sound("ui_wheel_tick")[1] < 0.2
    on, sr = _sound("flash_click_on")
    off, _ = _sound("flash_click_off")
    assert analysis.spectral_centroid(on, sr) > analysis.spectral_centroid(off, sr), "ligar tem de soar mais seco que desligar"
    assert _band_energy(_sound("battery_clack")[0], 44100, 0, 400) > 0.1
    for name in ("map_fold", "paper_pick"):
        x, sr = _sound(name)
        assert analysis.spectral_centroid(x, sr) > 3500, f"{name}: papel é agudo e granulado"
    for i in range(1, 4):
        x, sr = _sound(f"cloth_rustle_{i}")
        assert analysis.attack_ms(x, sr) > 20.0 and _band_energy(x, sr, 0, 250) < 0.1, f"cloth_rustle_{i}"
    flicker, sr = _sound("flash_flicker_burst")
    envelope = np.abs(flicker).reshape(-1, 441).max(axis=1)
    assert np.count_nonzero(np.diff((envelope > 0.25 * envelope.max()).astype(int)) == 1) >= 3, "esperava ao menos 3 piscadas"


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} testes passaram")


if __name__ == "__main__":
    main()
