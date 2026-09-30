"""Testes do CutscenePlayer com um anfitrião falso que registra tudo o que a cutscene faz.

    python tests/test_cutscenes_player.py

Não precisa do Blender: o player é lógica pura.
"""
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout, story  # noqa: E402
from sem_alvorada.cutscenes import CutscenePlayer, Overlay, NAMES, scripts, timeline  # noqa: E402

REASONS = {"intro": "intro_done", "blackout": "blackout_done", "garage_unlock": "unlock_done",
           "death": "death_done", "ending": "ending_done"}
PLAYER_STATE = (11.1, 5.9, 0.0, math.radians(-90), 1.65)          # cozinha, diante da porta da garagem
HALL_STATE = (5.6, 8.65, 2.8, math.radians(-90), 4.45)              # saindo do quarto do casal


class FakeData:
    def __init__(self, energy=None):
        self.angle = 1.0
        if energy is not None:
            self.energy = energy


class FakeObject:
    def __init__(self, name, light=False):
        self.name = name
        self.location = _Location()
        self.rotation_mode = "XYZ"
        self.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        self.hide_viewport = self.hide_render = light
        self.data = FakeData(0.0 if light else None)
        self.props = {}

    def get(self, key, default=None):
        return self.props.get(key, default)


class _Location(list):
    """Lista com .x .y .z, como o Vector do Blender."""

    def __init__(self):
        super().__init__([0.0, 0.0, 0.0])

    z = property(lambda self: self[2], lambda self, v: self.__setitem__(2, v))


class FakeAudio:
    def __init__(self, fail=False):
        self.played, self.loops, self.stopped, self.fail = [], {}, [], fail

    def play(self, name, pos=None, volume=1.0, pitch=1.0):
        if self.fail:
            raise RuntimeError("sem dispositivo de áudio")
        self.played.append(name)

    def loop(self, key, name, pos=None, volume=1.0, pitch=1.0):
        self.loops[key] = name

    def stop(self, key):
        self.loops.pop(key, None)
        self.stopped.append(key)


class FakeEntity:
    def __init__(self):
        self.visible = False
        self.transform = None
        self.anim = "idle"
        self.eye_level = 0.0
        self.look = "unset"
        self.look_rate = 200.0
        self.head_limit = 2.42
        self.updates = 0
        self.death_amounts = []
        self.history = []

    def set_visible(self, flag):
        self.visible = bool(flag)

    def set_transform(self, x, y, z, yaw):
        self.transform = (x, y, z, yaw)

    def set_anim(self, name):
        self.anim = name
        self.history.append(name)

    def eyes(self, level):
        self.eye_level = level

    def look_at(self, x, y=None, z=None):
        self.look = None if x is None else (x, y, z)

    def update(self, dt, speed=None):
        self.updates += 1

    def head_position(self):
        x, y, z, _ = self.transform or (0, 0, 0, 0)
        return (x, y, z + 2.5)

    def pose_for_death(self, eye, amount=1.0):
        self.death_amounts.append(amount)
        ex, ey, ez = eye
        self.transform = (ex, ey + 0.42, 0.0, math.pi)


class FakeDoors:
    def __init__(self):
        self.snaps = []

    def snap(self, door_id, value):
        self.snaps.append((door_id, value))

    def set_openness(self, door_id, value):
        self.snaps.append((door_id, value))


class FakeHost:
    def __init__(self, state=PLAYER_STATE, missing=(), audio_fails=False):
        self.audio = FakeAudio(audio_fails)
        self.entity = FakeEntity()
        self.doors = FakeDoors()
        self.scene = _FakeScene()
        self.state = state
        self.camera = None
        self.camera_calls = []
        self.finished = []
        self.power_calls, self.flashlight_calls, self.placed = [], [], []
        self.silence_calls, self.brain_calls = [], 0
        self.objects = {}
        for name in ("CutsceneCam", "Car", "GarageRollup", "Car_Headlight_L", "Car_Headlight_R",
                     "Cut_EndClock", "Cut_DawnGlow"):
            if name not in missing:
                self.objects[name] = FakeObject(name, light="Headlight" in name)
        for name in ("CutLight_ClockGlow", "CutLight_Dawn", "CutLight_Road", "CutLight_CorridorRim"):
            self.objects[name] = FakeObject(name, light=True)

    def set_camera(self, obj):
        self.camera_calls.append(obj)
        self.camera = obj

    def get_object(self, name):
        return self.objects.get(name)

    def player_state(self):
        return self.state

    def place_player(self, x, y, z, yaw):
        self.placed.append((x, y, z, yaw))
        self.state = (x, y, z, yaw, z + C.PLAYER_EYE_STAND)

    def set_power(self, on, flicker=0.0):
        self.power_calls.append((on, flicker))

    def flash_light(self, seconds):
        pass

    def set_flashlight(self, on):
        self.flashlight_calls.append(on)

    def noise_silence(self, seconds):
        self.silence_calls.append(seconds)

    def entity_brain_activate(self):
        self.brain_calls += 1

    def finish(self, reason):
        self.finished.append(reason)


class _FakeScene:
    objects = ()


def run_to_end(name, dt_sequence, host=None, on_frame=None, limit=100000):
    """Roda a cutscene até terminar; `dt_sequence` é um iterador de passos. Devolve (host, player, tempo)."""
    host = host or FakeHost()
    player = CutscenePlayer(host)
    done = []
    player.play(name, on_done=lambda: done.append(True))
    elapsed, steps = 0.0, 0
    if on_frame:
        on_frame(player, host, elapsed)
    for dt in dt_sequence:
        if not player.active:
            break
        player.update(dt)
        elapsed += dt
        steps += 1
        if on_frame:
            on_frame(player, host, elapsed)
        assert steps < limit, "a cutscene nunca terminou"
    assert done == [True] or player.active, "on_done não foi chamado"
    return host, player, elapsed


def constant(dt):
    while True:
        yield dt


def jittery(seed=3):
    rng = random.Random(seed)
    while True:
        yield rng.choice([1 / 60, 1 / 30, 1 / 20, 0.1, 0.25, 0.5, 0.0])


def check_overlay(overlay):
    assert isinstance(overlay, Overlay)
    for field in ("fade", "letterbox", "subtitle_alpha", "flash", "shake", "card_alpha"):
        value = getattr(overlay, field)
        assert isinstance(value, float) and math.isfinite(value) and 0.0 <= value <= 1.0, (field, value)
    assert isinstance(overlay.subtitle, str)
    assert overlay.card is None or (isinstance(overlay.card, tuple) and len(overlay.card) == 2)
    if not overlay.subtitle:
        assert overlay.subtitle_alpha == 0.0


def check_camera(host):
    cam = host.objects["CutsceneCam"]
    assert all(math.isfinite(v) for v in cam.location)
    q = cam.rotation_quaternion
    assert abs(math.sqrt(sum(c * c for c in q)) - 1.0) < 1e-6
    fov = math.degrees(cam.data.angle)
    assert 20.0 <= fov <= 100.0, fov


# --------------------------------------------------------------------------
def test_each_cutscene_finishes():
    for name in NAMES:
        for label, dts in (("1/60", constant(1 / 60)), ("1/20", constant(1 / 20)),
                           ("0.5", constant(0.5)), ("misto", jittery())):
            host, player, elapsed = run_to_end(name, dts, on_frame=lambda p, h, t: (
                check_overlay(p.overlay()), check_camera(h)))
            expected = timeline.compile_cutscene(scripts.get(name)).total
            assert host.finished == [REASONS[name]], (name, label, host.finished)
            assert not player.active
            assert host.camera_calls[0] is host.objects["CutsceneCam"] and host.camera_calls[-1] is None
            assert elapsed >= expected - 1e-6 and elapsed < expected + 0.5 + 1e-6, (name, label, elapsed, expected)
            assert player.errors == [], (name, label, player.errors)
            check_overlay(player.overlay())
            assert player.overlay().fade == 0.0 and player.overlay().subtitle == ""
        print(f"  {name}: termina sozinha com dt variados ({expected:.1f} s)")


def test_subtitles_match_story():
    for name in NAMES:
        seen = []

        def on_frame(player, host, elapsed):
            ov = player.overlay()
            if ov.subtitle and (not seen or seen[-1] != ov.subtitle):
                seen.append(ov.subtitle)
        run_to_end(name, constant(1 / 60), on_frame=on_frame)
        wanted = [text for text in story.CUTSCENE_TEXT[name] if text]
        assert seen == wanted, (name, seen, wanted)
        tl = timeline.compile_cutscene(scripts.get(name))
        previous_end = 0.0
        for t0, t1, text in tl.lines:
            assert t1 - t0 >= max(1.0, len(text) / 24.0), f"legenda curta demais: {text!r} ({t1 - t0:.1f}s)"
            assert t0 >= previous_end - 1e-9, f"legendas sobrepostas em {name}"
            previous_end = t1
        print(f"  {name}: {len(wanted)} legendas na ordem do story.py")


def test_subtitle_alpha_fades():
    def probe(player, host, elapsed):
        ov = player.overlay()
        if ov.subtitle:
            samples.append(ov.subtitle_alpha)
    samples = []
    run_to_end("intro", constant(1 / 60), on_frame=probe)
    assert max(samples) == 1.0 and min(samples) < 0.2, "a legenda deve entrar e sair suavemente"


def test_skip():
    for name in NAMES:
        for skip_at in (0.0, 0.7, 5.0, 12.0, 100.0):
            host = FakeHost()
            player = CutscenePlayer(host)
            player.play(name)
            t = 0.0
            while t < skip_at and player.active:
                player.update(1 / 30)
                t += 1 / 30
            if player.active:
                player.skip()
            assert not player.active
            assert host.finished == [REASONS[name]], (name, skip_at, host.finished)
            assert host.camera_calls[-1] is None
            player.skip()                                       # segunda chamada: nada acontece
            player.update(1 / 60)
            assert host.finished == [REASONS[name]]
            assert player.errors == []
    host = FakeHost()
    CutscenePlayer(host).skip()                                 # sem cutscene ativa
    assert host.finished == []
    print("  skip funciona em qualquer instante e é idempotente")


def test_skip_keeps_game_state_consistent():
    host = FakeHost(HALL_STATE)
    player = CutscenePlayer(host)
    player.play("intro")
    player.skip()
    px, py, pz = layout.PLAYER_START
    assert host.placed[-1][:3] == (px, py, pz), host.placed

    host = FakeHost(HALL_STATE)
    player = CutscenePlayer(host)
    player.play("blackout")
    player.skip()
    assert host.power_calls[-1][0] is False
    assert host.brain_calls == 1
    assert host.flashlight_calls[-1] is True
    assert host.entity.visible and host.entity.eye_level == 1.0
    x, y, z = host.placed[-1][:3]
    assert layout.ROOMS["hall_u"].rect.contains(x, y) and math.dist((x, y), layout.ENTITY_FIRST_SIGHT[:2]) > 3.5

    host = FakeHost()
    player = CutscenePlayer(host)
    player.play("garage_unlock")
    player.skip()
    assert host.doors.snaps[-1] == ("garage_door", 1.0)
    assert host.brain_calls == 1

    host = FakeHost()
    player = CutscenePlayer(host)
    player.play("ending")
    player.skip()
    assert host.objects["GarageRollup"].location.z == 2.3
    print("  pular deixa o estado do jogo coerente (posição, luz, portas, cérebro)")


def test_camera_continuity():
    """Sem saltos de câmera dentro de um plano; saltos só nos cortes entre planos."""
    for name in NAMES:
        tl = timeline.compile_cutscene(scripts.get(name))
        boundaries = [t0 for t0, _, _ in tl.shots[1:]]
        host = FakeHost(HALL_STATE if name == "blackout" else PLAYER_STATE)
        player = CutscenePlayer(host)
        player.play(name)
        cam = host.objects["CutsceneCam"]
        last = tuple(cam.location)
        t = 0.0
        worst = 0.0
        while player.active:
            player.update(1 / 60)
            t += 1 / 60
            if not player.active:
                break
            now = tuple(cam.location)
            jump = math.dist(now, last)
            near_cut = any(abs(t - b) < 1.5 / 60 for b in boundaries)
            if not near_cut:
                worst = max(worst, jump)
            last = now
        assert worst < 0.30, f"{name}: a câmera saltou {worst:.2f} m entre quadros"
    print("  câmera sem saltos fora dos cortes")


def test_intro_ends_on_gameplay_view():
    host = FakeHost(HALL_STATE)
    player = CutscenePlayer(host)
    player.play("intro")
    cam = host.objects["CutsceneCam"]
    while player.active:
        player.update(1 / 60)
        if player.time > 36.9:
            break
    px, py, pz = layout.PLAYER_START
    assert math.dist(cam.location, (px, py, pz + C.PLAYER_EYE_STAND)) < 0.05, tuple(cam.location)
    assert abs(math.degrees(cam.data.angle) - C.FOV_DEG) < 1.0
    print("  a intro termina exatamente na vista do jogador")


def test_blackout_beats():
    events = {"fade_black": None, "eyes_on": None, "flashlight_off": None}

    def watch(player, host, elapsed):
        ov = player.overlay()
        if ov.fade > 0.99 and events["fade_black"] is None:
            events["fade_black"] = elapsed
        if host.entity.eye_level >= 1.0 and events["eyes_on"] is None:
            events["eyes_on"] = elapsed
    host, player, _ = run_to_end("blackout", constant(1 / 60), FakeHost(HALL_STATE), on_frame=watch)
    assert events["fade_black"] is not None and events["eyes_on"] is not None
    assert events["eyes_on"] > events["fade_black"] + 2.0, "silêncio e escuridão antes do susto"
    assert host.entity.transform[:3] == layout.ENTITY_FIRST_SIGHT
    assert host.silence_calls, "o silêncio antes do susto precisa pedir noise_silence"
    print(f"  blackout: preto em {events['fade_black']:.1f} s, olhos acendem em {events['eyes_on']:.1f} s")


def test_death_is_a_dry_cut():
    fades = []

    def watch(player, host, elapsed):
        if player.active:
            fades.append(player.overlay().fade)
    host, _, _ = run_to_end("death", constant(1 / 60), FakeHost(HALL_STATE), on_frame=watch)
    jump_at = next(i for i, f in enumerate(fades) if f > 0.9)
    assert fades[jump_at - 1] < 0.05, "o corte para o preto da morte precisa ser seco"
    assert all(f > 0.9 for f in fades[jump_at:]), "depois do corte fica preto até o fim"
    assert host.entity.death_amounts and host.entity.death_amounts[-1] == 1.0
    assert host.entity.death_amounts == sorted(host.entity.death_amounts)
    assert not host.entity.visible, "a entidade some ao terminar"
    print("  morte: corte seco para o preto")


def test_ending_moves_car_and_shows_card():
    seen = {"card": None, "flash": 0.0, "fade_end": 0.0, "lights": 0.0, "stood_tall": False}

    def watch(player, host, elapsed):
        if not player.active:
            return
        seen["stood_tall"] = seen["stood_tall"] or host.entity.head_limit is None
        ov = player.overlay()
        seen["lights"] = max(seen["lights"], host.objects["Car_Headlight_L"].data.energy)
        seen["flash"] = max(seen["flash"], ov.flash)
        if ov.card:
            seen["card"] = ov.card
        seen["fade_end"] = ov.fade
    host, _, _ = run_to_end("ending", constant(1 / 30), on_frame=watch)
    car = host.objects["Car"].location
    stop_y = layout.ENTITY_ROAD_POS[1] + 6.4
    assert abs(car[1] - stop_y) < 1e-6 and abs(car[0] - layout.ANCHORS["car"].x) < 1e-6, tuple(car)
    assert host.objects["GarageRollup"].location.z == 2.3
    assert seen["lights"] > 0, "os faróis precisam acender durante a saída"
    assert seen["flash"] >= 0.99
    assert seen["card"] == story.ENDING_CARD, seen["card"]
    assert seen["fade_end"] > 0.99
    assert host.entity.transform[:3] == layout.ENTITY_ROAD_POS
    assert seen["stood_tall"] and host.entity.head_limit == 2.42, "na estrada ele fica ereto; ao fim volta o limite"
    print("  final: carro sai da garagem, entidade na estrada, flash e cartão")


def test_missing_optional_objects_do_not_break():
    host = FakeHost(missing=("Car", "GarageRollup", "Car_Headlight_L", "Car_Headlight_R", "Cut_EndClock"))
    host, player, _ = run_to_end("ending", constant(1 / 30), host)
    assert host.finished == ["ending_done"] and player.errors == []
    print("  final sem Car/GarageRollup/faróis: segue sem quebrar")


def test_host_errors_are_contained():
    host = FakeHost(audio_fails=True)
    host, player, _ = run_to_end("intro", constant(1 / 30), host)
    assert host.finished == ["intro_done"]
    assert any("audio.play" in e for e in player.errors)
    host = FakeHost(missing=("CutsceneCam",))
    host, player, _ = run_to_end("death", constant(1 / 30), host)
    assert host.finished == ["death_done"] and any("CutsceneCam" in e for e in player.errors)
    print("  falhas do host não derrubam a cutscene e ficam registradas")


def test_cut_lights_are_switched_off_at_the_end():
    for name in ("intro", "blackout", "ending"):
        host, _, _ = run_to_end(name, constant(1 / 30), FakeHost(HALL_STATE))
        for obj_name, obj in host.objects.items():
            if obj_name.startswith("CutLight_"):
                assert obj.data.energy == 0.0 and obj.hide_render, (name, obj_name)
    print("  luzes CutLight_* apagadas ao terminar")


def test_replay_and_unknown_name():
    host = FakeHost()
    player = CutscenePlayer(host)
    player.play("death")
    player.update(0.2)
    player.play("garage_unlock")
    assert player.active and player.name == "garage_unlock" and host.finished == []
    player.skip()
    assert host.finished == ["unlock_done"]
    try:
        player.play("nao_existe")
    except KeyError as exc:
        assert "nao_existe" in str(exc)
    else:
        raise AssertionError("nome desconhecido deveria levantar KeyError")
    print("  play troca de cutscene e nome inválido dá KeyError")


def test_on_done_order():
    order = []
    host = FakeHost()
    host.finish = lambda reason: order.append(("finish", reason))
    player = CutscenePlayer(host)
    player.play("death", on_done=lambda: order.append(("done", player.active)))
    while player.active:
        player.update(0.25)
    assert order == [("finish", "death_done"), ("done", False)], order


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        print(fn.__name__)
        fn()
    print("test_cutscenes_player: OK")


if __name__ == "__main__":
    main()
