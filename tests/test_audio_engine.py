"""Testes do AudioEngine: com dispositivo falso 3D/2D, sem dispositivo, sem aud e com o aud real.

    python tests/test_audio_engine.py      (ou pytest)

O `aud` do Blender pip não tem backend de saída neste ambiente, então a lógica 3D é validada
com `audio.fakes.FakeAud`; o carregamento dos WAV, o cache e o filtro lowpass usam o aud REAL.
"""
import logging
import os
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sem_alvorada import AUDIO_DIR  # noqa: E402
from sem_alvorada.audio import engine as engine_module  # noqa: E402
from sem_alvorada.audio import synth  # noqa: E402
from sem_alvorada.audio.catalog import REQUIRED_SOUNDS  # noqa: E402
from sem_alvorada.audio.engine import AudioEngine, forward_of, listener_quaternion, occlusion_tier  # noqa: E402
from sem_alvorada.audio.fakes import FakeAud  # noqa: E402
from sem_alvorada.audio.noise import PathInfo  # noqa: E402

synth.ensure_all(log=lambda *_: None)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def warnings(self):
        return [r for r in self.records if r.levelno >= logging.WARNING]


def capture_logs():
    handler = LogCapture()
    engine_module.LOG.addHandler(handler)
    engine_module.LOG.setLevel(logging.DEBUG)
    return handler


def spatial_engine(door_open=(), **kwargs):
    aud = FakeAud()
    clock = Clock()
    engine = AudioEngine(aud_module=aud, door_openness=lambda d: 1.0 if d in door_open else 0.0, clock=clock, **kwargs)
    return engine, aud.devices[0], clock


# ---- sem dispositivo, sem aud, desligado ------------------------------------
def test_disabled_engine_is_a_silent_noop():
    engine = AudioEngine(enabled=False)
    assert not engine.available
    engine.update_listener((1, 2, 0), 0.5)
    assert engine.play("door_open") is None and engine.loop("k", "amb_house") is None
    assert engine.footstep("wood", 0.5) in {f"step_wood_{i}" for i in range(1, 5)}
    engine.stop("k")
    engine.set_master(0.3)
    engine.shutdown()


def test_no_output_device_logs_once_and_never_raises():
    handler = capture_logs()
    engine = AudioEngine(aud_module=FakeAud(has_device=False))
    assert not engine.available
    for _ in range(50):
        engine.update_listener((1, 2, 0), 0.2)
        assert engine.play("pickup", (2, 2, 0)) is None
        engine.loop("amb", "amb_house", (1, 1, 0), 0.4)
        engine.footstep("tile", 1.0, (3, 3, 0))
    engine.stop()
    engine.shutdown()
    assert len(handler.warnings()) == 1, [r.getMessage() for r in handler.warnings()]
    engine_module.LOG.removeHandler(handler)


def test_missing_aud_module_is_a_noop():
    import bpy  # noqa: F401 - registra o aud antes de simularmos a ausência
    handler = capture_logs()
    saved = sys.modules.get("aud")
    sys.modules["aud"] = None
    try:
        engine = AudioEngine()
        assert not engine.available and engine.play("gasp") is None
        engine.update_listener((0, 0, 0), 0.0)
        engine.shutdown()
    finally:
        if saved is not None:
            sys.modules["aud"] = saved
    assert len(handler.warnings()) == 1
    engine_module.LOG.removeHandler(handler)


def test_device_failure_during_play_disables_instead_of_raising():
    handler = capture_logs()
    engine, device, _ = spatial_engine()

    def broken_play(sound, keep=False):
        raise RuntimeError("placa de som desapareceu")

    device.play = broken_play
    assert engine.play("door_close") is None
    assert not engine.available
    assert engine.play("door_close") is None and engine.footstep("wood", 1.0)
    assert len(handler.warnings()) == 1
    engine_module.LOG.removeHandler(handler)


def test_shutdown_stops_everything_and_turns_into_noop():
    engine, device, _ = spatial_engine()
    engine.update_listener((0, 0, 0), 0.0)
    engine.loop("drone", "ent_drone", (5, 5, 0), 0.5)
    engine.play("door_open", (3, 3, 0))
    engine.shutdown()
    assert device.alive() == [] and device.stop_all_calls == 1
    assert not engine.available and engine.play("door_open") is None
    engine.shutdown()


# ---- 3D ------------------------------------------------------------------
def test_listener_orientation_matches_game_yaw():
    for yaw, expected in ((0.0, (0.0, 1.0)), (-np.pi / 2, (1.0, 0.0)), (np.pi / 2, (-1.0, 0.0)), (np.pi, (0.0, -1.0))):
        x, y, z = forward_of(listener_quaternion(yaw))
        assert abs(x - expected[0]) < 1e-6 and abs(y - expected[1]) < 1e-6 and abs(z) < 1e-6, (yaw, (x, y, z))
    engine, device, _ = spatial_engine()
    engine.update_listener((4.0, 5.0, 1.65), -np.pi / 2)
    assert device.listener_location == (4.0, 5.0, 1.65)
    assert forward_of(device.listener_orientation)[0] > 0.99


def test_positional_play_sets_location_reference_distance_and_volume():
    engine, device, _ = spatial_engine()
    engine.update_listener((6.5, 5.0, 0.0), 0.0)
    handle = engine.play("ent_scream", (6.5, 9.0, 0.0), volume=0.8, pitch=1.1)
    assert handle.location == (6.5, 9.0, 0.0) and handle.relative is False
    assert handle.distance_reference == 7.0 and handle.attenuation == 1.0
    assert abs(handle.volume - 0.8) < 1e-9 and abs(handle.pitch - 1.1) < 1e-9
    assert device.lock_depth == 0, "todo lock precisa de unlock"
    ui = engine.play("pickup")
    assert ui.relative is True and ui.location == (0.0, 0.0, 0.0)


def test_closed_door_uses_muffled_version_and_lower_volume():
    listener = (6.5, 1.45, 0.0)
    source = (3.5, 1.45, 0.0)                    # sala, porta living_hall entre os dois
    closed, closed_device, _ = spatial_engine()
    opened, opened_device, _ = spatial_engine(door_open=("living_hall",))
    for engine in (closed, opened):
        engine.update_listener(listener, 0.0)
    shut_handle = closed.play("door_slam", source)
    open_handle = opened.play("door_slam", source)
    assert shut_handle.sound.cutoff == 1600.0 and open_handle.sound.cutoff is None
    assert abs(shut_handle.volume - 0.6) < 1e-9 and abs(open_handle.volume - 1.0) < 1e-9


def test_other_floor_is_muffled_hardest():
    engine, _, _ = spatial_engine()
    engine.update_listener((2.0, 4.0, 2.8), 0.0)
    handle = engine.play("thud_1", (3.5, 1.45, 0.0))
    assert handle.sound.cutoff == 650.0 and abs(handle.volume - 0.3) < 1e-9
    assert occlusion_tier(PathInfo(3.0, 0.0, 0)) == 0
    assert occlusion_tier(PathInfo(3.0, 1.0, 0)) == 1
    assert occlusion_tier(PathInfo(3.0, 2.0, 0)) == 2
    assert occlusion_tier(PathInfo(3.0, 0.0, 1)) == 2


def test_loop_lifecycle_update_replace_and_stop():
    engine, device, clock = spatial_engine()
    engine.update_listener((6.5, 5.0, 0.0), 0.0)
    engine.loop("amb", "amb_fridge", (11.0, 7.0, 0.0), 0.4)
    assert len(device.plays) == 1 and device.plays[0].loop_count == -1
    engine.loop("amb", "amb_fridge", (11.0, 7.0, 0.0), 0.7, pitch=0.9)
    assert len(device.plays) == 1 and abs(device.plays[0].volume - 0.7) < 1e-9, "atualiza sem recriar (a cozinha chega ao hall pelos arcos da sala de jantar)"
    engine.loop("amb", "amb_house", None, 0.5)
    clock.t += 1.0
    engine.update_listener((6.5, 5.0, 0.0), 0.0)
    assert len(device.plays) == 2 and device.plays[0].stopped, "trocar o som para o loop antigo (com fade)"
    engine.stop("amb")
    clock.t += 1.0
    engine.update_listener((6.5, 5.0, 0.0), 0.0)
    assert device.alive() == []
    engine.stop("nao-existe")


def test_loop_crossfades_when_a_door_closes():
    door = {"living_hall": 1.0}
    aud = FakeAud()
    clock = Clock()
    engine = AudioEngine(aud_module=aud, door_openness=lambda d: door.get(d, 0.0), clock=clock)
    device = aud.devices[0]
    engine.update_listener((6.5, 1.45, 0.0), 0.0)
    engine.loop("tv", "amb_tv_static", (3.5, 1.45, 0.0), 1.0)
    assert device.plays[0].sound.cutoff is None
    door["living_hall"] = 0.0
    engine.update_listener((6.5, 1.45, 0.0), 0.0)
    assert len(device.plays) == 2 and device.plays[1].sound.cutoff == 1600.0
    clock.t += 0.15
    engine.update_listener((6.5, 1.45, 0.0), 0.0)
    old, new = device.plays
    assert abs(new.volume - 0.3) < 1e-9 and abs(old.volume - 0.5) < 1e-9, "meio do crossfade: 50% de cada volume-alvo"
    clock.t += 0.3
    engine.update_listener((6.5, 1.45, 0.0), 0.0)
    assert old.stopped and abs(new.volume - 0.6) < 1e-9


def test_footstep_never_repeats_and_uses_all_variations():
    engine, device, _ = spatial_engine()
    engine.update_listener((0, 0, 0), 0.0)
    names = [engine.footstep("carpet", 0.5) for _ in range(300)]
    assert all(a != b for a, b in zip(names, names[1:]))
    assert set(names) == {f"step_carpet_{i}" for i in range(1, 5)}
    assert engine.footstep("lava", 1.0).startswith("step_wood_"), "piso desconhecido cai na madeira"
    soft, hard = engine.footstep("tile", 0.1, (1, 1, 0)), engine.footstep("tile", 1.0, (1, 1, 0))
    assert device.plays[-2].volume < device.plays[-1].volume and soft and hard
    for surface in ("wood", "carpet", "tile", "concrete", "stairs"):
        assert engine.footstep(surface, 0.5).startswith(f"step_{surface}_")


def test_master_volume_and_pitch_variation():
    engine, device, _ = spatial_engine()
    engine.set_master(0.4)
    assert device.volume == 0.4 and engine.master == 0.4
    pitches = {round(engine.play("step_wood_1", None, 1.0, 1.0).pitch, 3) for _ in range(3)}
    assert pitches == {1.0}
    engine.footstep("wood", 1.0)
    assert 0.94 <= device.plays[-1].pitch <= 1.06


def test_flat_stereo_device_falls_back_to_distance_volume():
    aud = FakeAud(spatial=False)
    engine = AudioEngine(aud_module=aud, clock=Clock())
    device = aud.devices[0]
    assert engine.available and not engine.spatial
    engine.update_listener((0.0, 0.0, 0.0), 0.0)
    near = engine.play("thud_1", (2.0, 0.0, 0.0))
    far = engine.play("thud_1", (2.0, 12.0, 0.0))
    assert near is not None and far is not None and 0.0 < far.volume < near.volume <= 1.0
    engine.loop("x", "amb_house", (1.0, 1.0, 0.0), 0.5)
    engine.shutdown()
    assert device.alive() == []


def test_play_variant_for_events():
    engine, _, _ = spatial_engine()
    engine.update_listener((0, 0, 0), 0.0)
    names = [engine.play_variant("creak", 3, (2.0, 2.0, 0.0)) for _ in range(60)]
    assert set(names) == {"creak_1", "creak_2", "creak_3"} and all(a != b for a, b in zip(names, names[1:]))


# ---- aud real ----------------------------------------------------------------
def test_real_aud_loads_every_sound_and_matches_the_wav_files():
    engine = AudioEngine(audio_dir=AUDIO_DIR, enabled=True)
    if engine._bank is None:
        return      # aud realmente ausente: o teste de no-op acima já cobre
    assert engine.preload(REQUIRED_SOUNDS) == [], "todos os 77 sons devem carregar pelo aud"
    for name in REQUIRED_SOUNDS:
        sound = engine.sound(name)
        with wave.open(os.path.join(AUDIO_DIR, name + ".wav"), "rb") as fh:
            frames, rate = fh.getnframes(), fh.getframerate()
        assert sound.length == frames, name
        assert sound.specs == (float(rate), 1), (name, sound.specs)
    for call in (lambda: engine.play("door_open", (1, 1, 0)), lambda: engine.loop("k", "amb_wind", None),
                 lambda: engine.footstep("stairs", 1.0), lambda: engine.stop("k"), engine.shutdown):
        call()      # com ou sem placa de som: nunca lança


def test_real_aud_lowpass_versions_really_remove_treble():
    engine = AudioEngine(audio_dir=AUDIO_DIR, enabled=True)
    if engine._bank is None:
        return
    clear = engine.sound("door_slam", 0).data().ravel()
    for tier, ceiling in ((1, 0.6), (2, 0.25)):
        muffled = engine.sound("door_slam", tier).data().ravel()
        n = min(len(clear), len(muffled))
        treble = lambda x: np.sum(np.abs(np.fft.rfft(x[:n])[int(n * 2500 / 22050):]) ** 2)   # noqa: E731
        ratio = treble(muffled) / treble(clear)
        assert ratio < ceiling ** 2, f"tier {tier}: agudos só caíram para {ratio:.3f}"


def test_real_aud_missing_file_is_reported_not_raised():
    handler = capture_logs()
    engine = AudioEngine(audio_dir=AUDIO_DIR, enabled=True)
    if engine._bank is None:
        engine_module.LOG.removeHandler(handler)
        return
    assert engine.preload(["arquivo_que_nao_existe"]) == ["arquivo_que_nao_existe"]
    assert engine.sound("arquivo_que_nao_existe") is None
    engine_module.LOG.removeHandler(handler)


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} testes passaram")


if __name__ == "__main__":
    main()
