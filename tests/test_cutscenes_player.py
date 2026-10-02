"""Testes do CutscenePlayer com um anfitrião falso que registra tudo o que a cutscene faz.

    python tests/test_cutscenes_player.py

Não precisa do Blender: o player é lógica pura (os atores de malha rodam sobre malhas de numpy).
A fluidez da câmera (saltos, velocidade, aceleração, cortes declarados) está em `test_cutscenes_fluency.py`.
"""
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from cutscene_fakes import (HALL_STATE, START_STATES, FakeHost, RecordingBody, host_for,  # noqa: E402
                            settle_state)
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout, story  # noqa: E402
from sem_alvorada.cutscenes import NAMES, CutscenePlayer, Overlay, scripts, timeline  # noqa: E402
from sem_alvorada.cutscenes import camera  # noqa: E402
from sem_alvorada.engine.fallbacks import NullBody  # noqa: E402

REASONS = {"intro": "intro_done", "blackout": "blackout_done", "garage_unlock": "unlock_done",
           "death": "death_done", "ending": "ending_done"}


def run_to_end(name, dt_sequence, host=None, on_frame=None, limit=100000):
    """Roda a cutscene até terminar; `dt_sequence` é um iterador de passos. Devolve (host, player, tempo)."""
    host = host or host_for(name)
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
    dof = cam.data.dof
    assert math.isfinite(dof.focus_distance) and dof.focus_distance > 0 and 0.8 <= dof.aperture_fstop <= 32


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
            host = host_for(name)
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
            assert player.errors == [], (name, skip_at, player.errors)
    host = FakeHost()
    CutscenePlayer(host).skip()                                 # sem cutscene ativa
    assert host.finished == []
    print("  skip funciona em qualquer instante e é idempotente")


def test_skip_leaves_the_same_game_state_as_the_full_run():
    """O estado que o jogo vê depois (posição do jogador, luz, porta, cérebro, entidade, objetos) não depende de pular."""
    for name in NAMES:
        full_host = host_for(name)
        run_to_end(name, constant(1 / 30), full_host)
        reference = settle_state(full_host)
        for skip_at in (0.0, 1.0, 3.3, 7.0, 12.5, 20.0):
            host = host_for(name)
            player = CutscenePlayer(host)
            player.play(name)
            t = 0.0
            while t < skip_at and player.active:
                player.update(1 / 30)
                t += 1 / 30
            if player.active:
                player.skip()
            state = settle_state(host)
            if state != reference:
                diff = {k: (state[k], reference[k]) for k in state if state[k] != reference[k] and k != "objects"}
                diff.update({n: (state["objects"][n], reference["objects"][n]) for n in state["objects"]
                             if state["objects"][n] != reference["objects"][n]})
                raise AssertionError(f"{name} pulada em {skip_at}: {diff}")
    print("  pular em qualquer instante deixa o mesmo estado final da execução completa")


def test_skip_keeps_game_state_consistent():
    host = FakeHost(HALL_STATE)
    player = CutscenePlayer(host)
    player.play("intro")
    player.skip()
    px, py, pz = layout.PLAYER_START
    assert host.placed[-1][:3] == (px, py, pz), host.placed
    assert host.power_calls[-1] == (True, 0.0), "a casa começa o jogo com a luz acesa"

    host = host_for("blackout")
    player = CutscenePlayer(host)
    player.play("blackout")
    player.skip()
    assert host.power_calls[-1][0] is False
    assert host.brain_calls == 1
    assert host.flashlight_calls[-1] is True
    assert host.entity.visible and host.entity.eye_level == 1.0 and host.entity.anim == "stare"
    x, y, z = host.placed[-1][:3]
    assert layout.ROOMS["hall_u"].rect.contains(x, y) and math.dist((x, y), layout.ENTITY_FIRST_SIGHT[:2]) > 3.5
    assert math.dist(host.brain_pos[:2], (x, y)) > 3.0, "o cérebro acorda longe do jogador"
    assert all(abs(g - 1.0) < 1e-9 for g in host.gains.values()), "os ganhos de luz da cascata voltam ao normal"

    host = host_for("garage_unlock")
    player = CutscenePlayer(host)
    player.play("garage_unlock")
    player.skip()
    assert host.doors.snaps[-1] == ("garage_door", 1.0)
    assert host.brain_calls == 1

    host = host_for("ending")
    player = CutscenePlayer(host)
    player.play("ending")
    player.skip()
    assert host.objects["GarageRollup"].location[2] == 0.0 and tuple(host.objects["Car"].location) == (0.0, 0.0, 0.0), \
        "o portão e o carro voltam ao lugar (o final não deixa a cena bagunçada para um novo jogo)"
    print("  pular deixa o estado do jogo coerente (posição, luz, portas, cérebro)")


def test_intro_ends_on_gameplay_view():
    """A passagem para o jogador não tem salto: posição, yaw e FOV do último quadro são os da câmera do jogo."""
    host = host_for("intro")
    player = CutscenePlayer(host)
    player.play("intro")
    cam = host.objects["CutsceneCam"]
    total = timeline.compile_cutscene(scripts.get("intro")).total
    while player.active and player.time < total - 0.03:
        player.update(1 / 60)
    px, py, pz = layout.PLAYER_START
    assert math.dist(cam.location, (px, py, pz + C.PLAYER_EYE_STAND)) < 0.005, tuple(cam.location)
    assert abs(math.degrees(cam.data.angle) - C.FOV_DEG) < 0.05
    want = camera.camera_quaternion(math.radians(layout.PLAYER_START_YAW_DEG), 0.0, 0.0)
    assert math.degrees(camera.angle_between(tuple(cam.rotation_quaternion), want)) < 0.05
    print("  a intro termina exatamente na vista do jogador (posição, yaw e FOV)")


def test_cutscenes_start_on_the_players_view():
    """Garagem e morte começam na vista exata do jogador (sem corte na entrada)."""
    for name, pitch in (("garage_unlock", math.radians(-12)), ("blackout", 0.0), ("death", math.radians(5))):
        host = host_for(name, pitch=pitch)
        player = CutscenePlayer(host)
        player.play(name)
        cam = host.objects["CutsceneCam"]
        x, y, z, yaw, eye_z = host.state
        assert math.dist(cam.location, (x, y, eye_z)) < 0.03, (name, tuple(cam.location))
        want = camera.camera_quaternion(yaw, pitch, 0.0)
        assert math.degrees(camera.angle_between(tuple(cam.rotation_quaternion), want)) < 1.5, name
        assert abs(math.degrees(cam.data.angle) - C.FOV_DEG) < 0.2, name
    print("  garagem, apagão e morte começam na vista do jogador (posição, yaw, inclinação e FOV)")


def test_blackout_beats():
    seen = {"fade_black": None, "eyes_on": None, "first_sight": None, "walk": []}

    def watch(player, host, elapsed):
        ov = player.overlay()
        if ov.fade > 0.99 and seen["fade_black"] is None:
            seen["fade_black"] = elapsed
        if host.entity.eye_level >= 1.0 and seen["eyes_on"] is None:
            seen["eyes_on"] = elapsed
        if host.entity.transform and seen["first_sight"] is None:
            seen["first_sight"] = host.entity.transform[:3]
        seen["walk"].append(host.entity.speeds[-1] if host.entity.speeds else 0.0)
    host, player, _ = run_to_end("blackout", constant(1 / 60), host_for("blackout"), on_frame=watch)
    assert seen["fade_black"] is not None and seen["eyes_on"] is not None
    assert seen["eyes_on"] > seen["fade_black"] + 2.0, "silêncio e escuridão antes do susto"
    assert seen["first_sight"] == layout.ENTITY_FIRST_SIGHT
    assert host.silence_calls, "o silêncio antes do susto precisa pedir noise_silence"
    assert max(s or 0.0 for s in seen["walk"]) > 0.2, "a passada lenta em direção à câmera anima o passo da entidade"
    assert host.entity.speeds[-1] == 0.0
    sight = layout.ENTITY_FIRST_SIGHT
    assert abs(host.entity.transform[1] - (sight[1] - 1.0)) < 1e-6, "ele deu um metro de passo"
    assert host.brain_pos == tuple(host.entity.transform[:3]), "o cérebro acorda de onde a cutscene o deixou"
    assert host.power_calls[-1][0] is False
    print(f"  blackout: luz estoura em {seen['fade_black']:.1f} s, olhos acendem em {seen['eyes_on']:.1f} s")


def test_light_cascade_dies_in_order_and_the_last_bursts():
    gains = []

    def watch(player, host, elapsed):
        gains.append((elapsed, dict(host.gains)))
    host, _, _ = run_to_end("blackout", constant(1 / 60), host_for("blackout"), on_frame=watch)
    death = {}
    for elapsed, snapshot in gains:
        for name, gain in snapshot.items():
            if gain == 0.0 and name not in death:
                death[name] = elapsed
    assert len(death) >= 4, death
    order = sorted(death, key=death.get)
    assert order[-1].startswith("Light_hall_u"), "a última a morrer é a do corredor, sobre o jogador"
    peak = max(g for _, snap in gains for g in snap.values())
    assert peak > 2.0, "a lâmpada estoura: antes de apagar ela dá um clarão"
    spread = death[order[-1]] - death[order[0]]
    assert 0.8 < spread < 2.6, spread
    print(f"  cascata: {len(death)} luzes morrem em {spread:.1f} s, a do corredor por último e com clarão")


def test_death_is_a_dry_cut():
    fades = []

    def watch(player, host, elapsed):
        if player.active:
            fades.append(player.overlay().fade)
    host, _, elapsed = run_to_end("death", constant(1 / 60), host_for("death"), on_frame=watch)
    jump_at = next(i for i, f in enumerate(fades) if f > 0.9)
    assert fades[jump_at - 1] < 0.05, "o corte para o preto da morte precisa ser seco"
    assert all(f > 0.9 for f in fades[jump_at:]), "depois do corte fica preto até o fim"
    assert host.entity.death_amounts and host.entity.death_amounts[-1] == 1.0
    assert host.entity.death_amounts == sorted(host.entity.death_amounts)
    assert not host.entity.visible, "a entidade some ao terminar"
    assert elapsed < 4.0, "a morte é rápida: sem congelar o tempo"
    print(f"  morte: corte seco para o preto, {elapsed:.1f} s no total")


def test_ending_moves_car_and_shows_card():
    seen = {"card": None, "flash": 0.0, "fade_end": 0.0, "lights": 0.0, "stood_tall": False, "car_y": [],
            "rollup": 0.0, "wheel_spin": 0.0, "bunny": 0.0, "engine": False}

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
        seen["car_y"].append(host.objects["Car"].location[1])
        seen["rollup"] = max(seen["rollup"], host.objects["GarageRollup"].location[2])
        seen["wheel_spin"] = max(seen["wheel_spin"], abs(host.objects["Car_Wheel_FL"].rotation_euler[0]))
        seen["bunny"] = max(seen["bunny"], abs(host.objects["Cut_Bunny"].rotation_euler[0]))
        seen["engine"] = seen["engine"] or "engine" in host.audio.loops
    host, _, _ = run_to_end("ending", constant(1 / 30), host_for("ending"), on_frame=watch)
    car = layout.ANCHORS["car"]
    stop_y = layout.ENTITY_ROAD_POS[1] + 6.0
    assert abs(min(seen["car_y"]) - stop_y) < 0.05, (min(seen["car_y"]), stop_y)
    assert abs(seen["car_y"][1] - car.y) < 0.01, "o carro começa parado na garagem"
    assert abs(seen["rollup"] - 2.3) < 0.2, seen["rollup"]
    assert seen["lights"] > 0, "os faróis precisam acender durante a saída"
    assert seen["wheel_spin"] > 3.0, "as rodas giram"
    assert seen["bunny"] > 0.05, "o coelhinho balança com o carro"
    assert seen["engine"], "o motor toca em marcha lenta"
    assert seen["flash"] >= 0.99
    assert seen["card"] == story.ENDING_CARD, seen["card"]
    assert seen["fade_end"] > 0.99
    assert host.entity.transform[:3] == layout.ENTITY_ROAD_POS
    assert seen["stood_tall"] and host.entity.head_limit == 2.42, "na estrada ele fica ereto; ao fim volta o limite"
    assert host.objects["Cut_EndClock"].hide_render, "objetos mostrados pela cutscene voltam a ficar ocultos"
    assert not host.objects["AlarmClock"].hide_render, "o despertador escondido volta"
    print("  final: portão sobe, carro sai com rodas e coelhinho, entidade na estrada, flash e cartão")


def test_missing_optional_objects_do_not_break():
    host = FakeHost(START_STATES["ending"], missing=("Car", "GarageRollup", "Car_Headlight_L", "Car_Headlight_R",
                                                      "Cut_EndClock", "Cut_Bunny", "Cut_Wheel", "Cut_Key", "Cut_Dust",
                                                      "Cut_Sparks", "Cut_LidTop", "Cut_LidBottom", "PlayerCam",
                                                      "Curtain_w_master_n", "Curtain_w_master_w", "AlarmClock"))
    host, player, _ = run_to_end("ending", constant(1 / 30), host)
    assert host.finished == ["ending_done"] and player.errors == []
    for name in ("intro", "blackout", "garage_unlock", "death"):
        host = host_for(name, missing=("Cut_Dust", "Cut_Sparks", "Cut_Key", "Cut_LidTop", "PlayerCam", "Curtain_w_master_n"))
        host, player, _ = run_to_end(name, constant(1 / 30), host)
        assert host.finished == [REASONS[name]] and player.errors == [], (name, player.errors)
    print("  sem Car/GarageRollup/faróis/poeira/pálpebras/cortinas: segue sem quebrar")


def test_host_errors_are_contained():
    host = host_for("intro", audio_fails=True)
    host, player, _ = run_to_end("intro", constant(1 / 30), host)
    assert host.finished == ["intro_done"]
    assert any("audio.play" in e for e in player.errors)
    host = host_for("death", missing=("CutsceneCam",))
    host, player, _ = run_to_end("death", constant(1 / 30), host)
    assert host.finished == ["death_done"] and any("CutsceneCam" in e for e in player.errors)
    print("  falhas do host não derrubam a cutscene e ficam registradas")


def test_cut_lights_are_switched_off_at_the_end():
    for name in ("intro", "blackout", "ending"):
        host, _, _ = run_to_end(name, constant(1 / 30), host_for(name))
        for obj_name, obj in host.objects.items():
            if obj_name.startswith("CutLight_"):
                assert obj.data.energy == 0.0 and obj.hide_render, (name, obj_name)
    print("  luzes CutLight_* apagadas ao terminar")


def test_actors_restore_the_scene():
    """Cortinas, poeira, faíscas, carro, rodas, coelhinho, portão e chave voltam ao que eram."""
    for name in NAMES:
        host = host_for(name)
        before = settle_state(host)
        meshes = {n: o.data.vertices.coords.copy() for n, o in host.objects.items() if hasattr(o.data, "vertices")}
        run_to_end(name, constant(1 / 30), host)
        for n, coords in meshes.items():
            assert (host.objects[n].data.vertices.coords == coords).all() or n in ("Cut_Dust", "Cut_Sparks"), (name, n)
        after = settle_state(host)
        for n in ("Car", "GarageRollup", "Car_Wheel_FL", "Cut_Bunny", "Cut_Wheel", "PlayerCam"):
            assert after["objects"][n] == before["objects"][n], (name, n, before["objects"][n], after["objects"][n])
    print("  atores devolvem malhas, transformações e visibilidade")


def test_curtains_move_and_stay_inside_their_budget():
    host = host_for("intro")
    original = host.objects["Curtain_w_master_n"].data.vertices.coords.copy()
    seen = []

    def watch(player, h, elapsed):
        if 20.0 < elapsed < 21.0:
            seen.append(abs(h.objects["Curtain_w_master_n"].data.vertices.coords - original).max())
    run_to_end("intro", constant(1 / 60), host, on_frame=watch)
    assert max(seen) > 0.02, "a cortina balança"
    assert max(seen) < 0.5, "mas não atravessa o quarto"
    print(f"  cortina: deslocamento máximo {max(seen) * 100:.0f} cm")


def test_dust_falls_from_the_ceiling():
    host = host_for("garage_unlock")
    heights = []

    def watch(player, h, elapsed):
        if elapsed > 7.0:
            z = h.objects["Cut_Dust"].data.vertices.coords[:, 2]
            visible = z[(h.objects["Cut_Dust"].data.vertices.coords != 0).any(axis=1)]
            if len(visible):
                heights.append((elapsed, float(visible.max()), float(visible.min())))
    run_to_end("garage_unlock", constant(1 / 30), host, on_frame=watch)
    assert heights and heights[0][1] > 2.4, "a poeira nasce no forro"
    assert min(h[2] for h in heights) < 2.0, "e desce"
    print("  poeira nasce no forro (2,6 m) e desce")


def test_body_integration_with_a_recording_body():
    """Com corpo: poses, braços e a referência da câmera; sem corpo (NullBody ou ausente): nada quebra."""
    for name in NAMES:
        body = RecordingBody()
        host = host_for(name, body=body)
        host, player, _ = run_to_end(name, constant(1 / 30), host)
        assert player.errors == [], (name, player.errors)
        if name in ("intro", "garage_unlock", "ending"):
            assert host.body_shown[0] is True and host.body_shown[-1] is False, (name, host.body_shown)
            assert ("attach_view", "CutsceneCam") in body.calls, name
            last_reset = max(i for i, c in enumerate(body.calls) if c == ("reset",))
            assert not any(c[0] in ("place", "pose") for c in body.calls[last_reset:]), \
                f"{name}: o corpo volta ao jogo (reset) no fim e nenhuma pose vem depois"
        if name == "intro":
            assert body.poses()[:3] == ["lying_bed", "sit_bed", "stand"], body.poses()
        null_host = host_for(name, body=NullBody())
        _, null_player, _ = run_to_end(name, constant(1 / 30), null_host)
        assert null_player.errors == [], (name, null_player.errors)
        assert null_host.finished == [REASONS[name]]
    print("  corpo: poses e referência da câmera; com NullBody tudo segue")


def test_dof_can_be_turned_off():
    host = host_for("intro")
    player = CutscenePlayer(host, dof=False)
    player.play("intro")
    for _ in range(300):
        player.update(1 / 30)
    assert host.objects["CutsceneCam"].data.dof.use_dof is False
    host = host_for("intro")
    player = CutscenePlayer(host, dof=True)
    player.play("intro")
    assert host.objects["CutsceneCam"].data.dof.use_dof is True
    print("  profundidade de campo liga e desliga")


def test_replay_and_unknown_name():
    host = host_for("death")
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
    host = host_for("death")
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
