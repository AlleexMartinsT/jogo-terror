"""Testes numéricos do sistema de ruído (sem bpy, sem aud).

    python tests/test_audio_noise.py      (ou pytest)
"""
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.audio.noise import HEAR_THRESHOLD, NoiseRules, NoiseSystem, room_id_at, step_loudness  # noqa: E402


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def system(open_doors=(), openness=1.0):
    """NoiseSystem cujas portas em `open_doors` têm abertura `openness` e as demais estão fechadas."""
    return NoiseSystem(door_openness=lambda door_id: openness if door_id in open_doors else 0.0)


def expected(loudness, metres, ambient_of_listener_room, doors=0, floors=0):
    value = (loudness * (1 - C.NOISE_DECAY_PER_M * metres) - C.NOISE_DOOR_CLOSED_LOSS * doors
             - C.NOISE_FLOOR_LOSS * floors - C.NOISE_MASK_FACTOR * ambient_of_listener_room)
    return min(max(value, 0.0), 1.0)


# ---- passos por piso, agachado e correndo -----------------------------------
def test_step_loudness_by_surface_and_gait():
    walk = {s: step_loudness("walk", s) for s in C.SURFACES}
    assert approx(walk["carpet"], 0.30 * 0.55) and approx(walk["wood"], 0.30)
    assert approx(walk["tile"], 0.30 * 1.15) and approx(walk["stairs"], 0.30 * 1.35)
    assert walk["carpet"] < walk["wood"] < walk["tile"] < walk["stairs"]
    assert step_loudness("crouch_walk", "wood") == 0.08
    assert step_loudness("run", "tile") <= 1.0 and step_loudness("run", "wood") == 0.75


def test_same_room_matches_formula_and_falls_with_distance():
    ns = system()
    event = ns.emit("player", "walk", (0.6, 8.0, 0.0), 0.30)         # escritório (den, ambiente 0.05)
    ambient = layout.ROOMS["den"].ambient
    previous = 2.0
    for metres in (0.5, 1.0, 2.0, 3.0, 4.0):
        value = ns.effective(event, (0.6 + metres, 8.0, 0.0))
        assert approx(value, expected(0.30, metres, ambient)), (metres, value)
        assert value <= previous
        previous = value


def test_carpet_wood_tile_audibility_at_three_metres():
    rooms = {"carpet": (1.0, 3.0, 0.0), "wood": (1.0, 8.0, 0.0), "tile": (8.5, 2.0, 2.8)}   # sala, escritório, banheiro
    heard = {}
    for surface, source in rooms.items():
        ns = system()
        ns.emit("player", "walk", source, step_loudness("walk", surface))
        listener = (source[0] + 3.0, source[1], source[2])
        heard[surface] = bool(ns.heard_by_entity(listener)), ns.level_at(listener)
    assert heard["carpet"][0] is False, "andar no carpete a 3 m passa despercebido"
    assert heard["wood"][0] and heard["tile"][0]
    assert heard["carpet"][1] < heard["wood"][1] and heard["carpet"][1] < heard["tile"][1]


def test_crouch_walk_is_inaudible_but_run_is_heard_across_the_room():
    ns = system()
    ns.emit("player", "crouch_walk", (0.8, 9.0, 0.0), step_loudness("crouch_walk", "wood"))
    assert ns.heard_by_entity((1.8, 9.0, 0.0)) == [], "agachado, nem a 1 m"
    ns.clear()
    ns.emit("player", "run", (0.8, 9.0, 0.0), step_loudness("run", "wood"))
    assert ns.heard_by_entity((4.5, 6.5, 0.0)), "correndo, o outro canto do escritório ouve"


def test_run_on_tile_echoes_through_open_house():
    ns = system(open_doors=("kitchen_hall", "living_hall"))
    ns.emit("player", "run", (10.0, 7.5, 0.0), step_loudness("run", "tile"))
    in_hall = ns.heard_by_entity((6.5, 8.45, 0.0))           # hall_g, do outro lado da porta aberta
    assert in_hall and in_hall[0].kind == "run"
    closed = system()
    closed.emit("player", "run", (10.0, 7.5, 0.0), step_loudness("run", "tile"))
    assert closed.level_at((6.5, 8.45, 0.0)) < ns.level_at((6.5, 8.45, 0.0))


# ---- portas, andares e cômodos vizinhos ---------------------------------------
def test_door_open_vs_closed_between_rooms():
    source, listener = (3.5, 1.45, 0.0), (6.5, 1.45, 0.0)         # sala -> hall, pela porta living_hall
    closed, opened = system(), system(open_doors=("living_hall",))
    for ns in (closed, opened):
        ns.emit("player", "run", source, 0.75)
    hall_ambient = layout.ROOMS["hall_g"].ambient
    assert approx(closed.level_at(listener), expected(0.75, 3.0, hall_ambient, doors=1), 1e-9)
    assert approx(opened.level_at(listener), expected(0.75, 3.0, hall_ambient), 1e-9)
    assert opened.level_at(listener) > closed.level_at(listener) + 0.3


def test_walking_behind_closed_door_is_silent_but_audible_when_open():
    source, listener = (3.5, 1.45, 0.0), (6.5, 1.45, 0.0)
    closed, opened = system(), system(open_doors=("living_hall",))
    closed.emit("player", "walk", source, 0.30)
    opened.emit("player", "walk", source, 0.30)
    assert closed.heard_by_entity(listener) == []
    assert opened.heard_by_entity(listener)


def test_half_open_door_scales_the_loss():
    ns_half = NoiseSystem(door_openness=lambda d: 0.25 if d == "living_hall" else 0.0)
    ns_shut = system()
    ns_full = system(open_doors=("living_hall",))
    for ns in (ns_half, ns_shut, ns_full):
        ns.emit("player", "run", (3.5, 1.45, 0.0), 0.75)
    pos = (6.5, 1.45, 0.0)
    shut, half, full = (ns.level_at(pos) for ns in (ns_shut, ns_half, ns_full))
    assert shut < half < full
    assert approx(full - half, 0.5 * C.NOISE_DOOR_CLOSED_LOSS, 1e-9)
    ns_wide = NoiseSystem(door_openness=lambda d: 0.6 if d == "living_hall" else 0.0)
    ns_wide.emit("player", "run", (3.5, 1.45, 0.0), 0.75)
    assert approx(ns_wide.level_at(pos), full, 1e-9), "acima de 0.5 a porta já não bloqueia"


def test_other_floor_pays_floor_loss_and_extra_path():
    ns = system()
    event = ns.emit("player", "door_slam", (5.6, 3.5, 0.0), 0.90)         # pé da escada
    upstairs = (5.6, 8.0, 2.8)                                              # topo da escada, andar de cima
    detail = ns.explain(event, upstairs)
    assert detail["floors"] == 1 and detail["closed_doors"] == 0
    assert approx(detail["floor_loss"], C.NOISE_FLOOR_LOSS)
    assert detail["path_length"] > 5.3, "o caminho inclui a escada, não a linha reta"
    same_floor = ns.effective(event, (5.6, 3.5 + 6.0, 0.0))
    assert ns.effective(event, upstairs) < same_floor + 0.3
    assert ns.effective(event, upstairs) > 0.0, "batida de porta no pé da escada chega lá em cima"


def test_directly_above_is_not_a_shortcut():
    ns = system()
    event = ns.emit("player", "run", (2.5, 3.0, 0.0), 0.75)               # sala, térreo
    assert ns.level_at((2.5, 2.5, 2.8)) == 0.0, "o som não atravessa a laje em linha reta"


def test_kitchen_masks_the_player():
    kitchen, hall = system(), system()
    kitchen.emit("player", "walk", (10.0, 8.0, 0.0), 0.30)
    hall.emit("player", "walk", (6.5, 8.0, 0.0), 0.30)
    assert kitchen.heard_by_entity((10.0, 5.5, 0.0)) == [], "geladeira (0.22) esconde passos a 2.5 m"
    assert hall.heard_by_entity((6.5, 5.5, 0.0)), "mesma distância no hall é ouvida"
    assert layout.ROOMS["kitchen"].ambient == 0.22


# ---- ambiente -------------------------------------------------------------
def test_ambient_level_base_events_and_expiry():
    ns = system()
    for room in layout.ROOMS.values():
        assert approx(ns.ambient_level(room.id), room.ambient)
    event = ns.emit("ambient", "phone", (10.0, 7.5, 0.9), C.NOISE_AMBIENT_EVENTS["phone"], ttl=2.0)
    assert ns.ambient_level("kitchen") > 0.6
    assert approx(ns.ambient_level("master"), layout.ROOMS["master"].ambient), "outro andar, porta fechada: nada"
    ns.update(2.1)
    assert event not in ns.events
    assert approx(ns.ambient_level("kitchen"), layout.ROOMS["kitchen"].ambient)


def test_ambient_event_attracts_the_entity_and_masks_the_player():
    ns = system()
    phone = ns.emit("ambient", "phone", (10.0, 7.5, 0.9), 0.60, ttl=4.0)
    heard = ns.heard_by_entity((10.0, 9.0, 0.0))
    assert heard and heard[0].source == "ambient" and heard[0].kind == "phone" and heard[0].uid == phone.uid
    assert heard[0].pos_source == phone.pos
    ns.emit("player", "walk", (9.0, 6.0, 0.0), 0.30)
    kinds = [h.kind for h in ns.heard_by_entity((10.0, 9.0, 0.0))]
    assert "walk" not in kinds, "o telefone toca alto demais para ouvir passos"


def test_ambient_event_does_not_mask_itself():
    ns = system()
    event = ns.emit("ambient", "thud", (2.5, 8.0, 1.0), 0.40)
    listener = (2.5, 6.5, 0.0)
    metres = math.hypot(event.pos[0] - listener[0], event.pos[1] - listener[1])
    value = ns.effective(event, listener)
    assert approx(value, expected(0.40, metres, layout.ROOMS["den"].ambient), 1e-9)
    assert value > 0.2


def test_level_at_source_filter_and_soft_sum():
    ns = system()
    ns.emit("player", "run", (2.5, 8.0, 0.0), 0.75)
    ns.emit("entity", "growl", (2.5, 8.0, 0.0), 0.70)
    pos = (3.0, 8.0, 0.0)
    only_player, only_entity, both = ns.level_at(pos, "player"), ns.level_at(pos, "entity"), ns.level_at(pos)
    assert both > max(only_player, only_entity) and both < 1.0
    assert approx(both, 1 - (1 - only_player) * (1 - only_entity))
    assert ns.level_at(pos, ("player", "entity")) == both
    assert ns.heard_by_entity(pos) and all(h.source != "entity" for h in ns.heard_by_entity(pos))


# ---- vida dos eventos e medidores ---------------------------------------------
def test_events_expire_and_fade():
    ns = system()
    ns.emit("player", "walk", (2.5, 8.0, 0.0), 0.30, ttl=1.5)
    fresh = ns.level_at((3.0, 8.0, 0.0))
    ns.update(0.4)
    assert approx(ns.level_at((3.0, 8.0, 0.0)), fresh), "primeira parte do ttl é força total"
    ns.update(0.8)
    assert 0.0 < ns.level_at((3.0, 8.0, 0.0)) < fresh, "fim do ttl esmaece"
    ns.update(0.4)
    assert ns.events == () and ns.level_at((3.0, 8.0, 0.0)) == 0.0


def test_continuous_emission_merges_into_one_event():
    ns = system()
    for _ in range(30):
        ns.emit("entity", "drone", (6.5, 8.0, 0.0), 0.30, ttl=0.3)
        ns.update(1 / 60)
    assert len(ns.events) == 1
    ns.emit("player", "walk", (2.0, 8.0, 0.0), 0.3)
    ns.update(0.5)
    ns.emit("player", "walk", (3.0, 8.0, 0.0), 0.3)
    assert len([e for e in ns.events if e.kind == "walk"]) == 2, "passos separados no tempo são eventos separados"


def test_hud_rises_fast_and_falls_slowly():
    ns = system()
    ns.set_listener((2.5, 8.0, 0.0))
    ns.emit("player", "run", (2.5, 8.0, 0.0), 0.75, ttl=1.0)
    ns.update(0.05)
    assert ns.hud_levels()["player"] > 0.4, "sobe rápido"
    ns.update(0.15)
    assert ns.hud_levels()["player"] > 0.65
    ns.update(1.0)                                    # o evento expirou; o medidor ainda guarda a memória
    after_expiry = ns.hud_levels()["player"]
    assert 0.3 < after_expiry < 0.75
    readings = []
    for _ in range(10):
        ns.update(0.2)
        readings.append(ns.hud_levels()["player"])
    assert all(a > b for a, b in zip([after_expiry] + readings, readings)), "cai monotonicamente"
    assert readings[4] > 0.1, "ainda não zerou depois de 1 s"
    assert ns.hud_levels()["ambient"] > 0.0 and ns.hud_levels()["entity"] == 0.0


def test_hud_entity_bar_follows_the_listener():
    ns = system()
    ns.set_listener((6.5, 5.0, 0.0))
    ns.emit("entity", "step_chase", (6.5, 8.0, 0.0), C.NOISE_ENTITY["step_chase"], ttl=1.0)
    for _ in range(6):
        ns.update(0.05)
    near = ns.hud_levels()["entity"]
    assert near > 0.4
    ns.set_listener((2.5, 8.0, 2.8))                  # jogador em outro andar
    for _ in range(40):
        ns.update(0.05)
    assert ns.hud_levels()["entity"] < near


def test_silence_blocks_and_clears():
    ns = system()
    ns.emit("player", "run", (2.5, 8.0, 0.0), 0.75)
    ns.silence(2.0)
    assert ns.events == () and ns.emit("player", "run", (2.5, 8.0, 0.0), 0.75) is None
    ns.update(2.1)
    assert ns.emit("player", "run", (2.5, 8.0, 0.0), 0.75) is not None


# ---- robustez -------------------------------------------------------------
def test_no_nan_and_bounded_under_random_stress():
    rng = random.Random(7)
    ns = NoiseSystem(door_openness=lambda d: rng.random())
    for step in range(400):
        pos = (rng.uniform(-5, 22), rng.uniform(-5, 15), rng.choice([0.0, 1.4, 2.8, 3.5]))
        ns.emit(rng.choice(["player", "entity", "ambient"]), "walk", pos, rng.choice([0.0, 0.05, 0.5, 1.0, 1.7]),
                ttl=rng.uniform(0.1, 3.0))
        ns.set_listener((rng.uniform(0, 12), rng.uniform(0, 10), rng.choice([0.0, 2.8])))
        ns.update(rng.uniform(0.0, 0.3))
        probe = (rng.uniform(-3, 20), rng.uniform(-3, 13), rng.choice([0.0, 2.8]))
        for value in (ns.level_at(probe), ns.level_at(probe, "player"), *ns.hud_levels().values()):
            assert math.isfinite(value) and 0.0 <= value <= 1.0
        for heard in ns.heard_by_entity(probe):
            assert math.isfinite(heard.loudness) and heard.loudness >= HEAR_THRESHOLD
    assert room_id_at((-4.0, 3.0, 0.0)) == "living"


def test_rules_are_tunable():
    louder_doors = NoiseSystem(rules=NoiseRules(door_closed_loss=0.0))
    louder_doors.emit("player", "walk", (3.5, 1.45, 0.0), 0.30)
    assert louder_doors.heard_by_entity((6.5, 1.45, 0.0)), "sem perda de porta, o passo passa"


# ---- eventos ambientais aleatórios ---------------------------------------------
def _simulate_ambient(seed, seconds=900.0, dt=0.1, room="master", rate=1.0):
    ns, rng, log = system(), random.Random(seed), []
    ns.ambient_rate = rate
    clock = 0.0
    while clock < seconds:
        for event in ns.schedule_ambient_events(dt, rng, room):
            log.append((clock, event))
        ns.update(dt)
        clock += dt
    return log


def test_ambient_events_are_moderate_varied_and_avoid_the_player_room():
    log = _simulate_ambient(3)
    assert 20 <= len(log) <= 80, f"{len(log)} eventos em 15 min"
    assert all(event.room != "master" for _, event in log)
    assert len({event.kind for _, event in log}) >= 4
    times = [clock for clock, _ in log]
    assert all(b - a >= NoiseRules().ambient_min_interval - 0.2 for a, b in zip(times, times[1:]))
    for _, event in log:
        assert event.kind in C.NOISE_AMBIENT_EVENTS and event.source == "ambient"
        assert layout.ROOMS[event.room].rect.contains(event.pos[0], event.pos[1])


def test_ambient_events_deterministic_and_controllable():
    a = [(round(t, 1), e.kind, e.room) for t, e in _simulate_ambient(11)]
    b = [(round(t, 1), e.kind, e.room) for t, e in _simulate_ambient(11)]
    c = [(round(t, 1), e.kind, e.room) for t, e in _simulate_ambient(12)]
    assert a == b and a != c
    assert len(_simulate_ambient(5, rate=3.0)) > 1.8 * len(_simulate_ambient(5, rate=1.0))
    ns = system()
    ns.ambient_enabled = False
    assert ns.schedule_ambient_events(1000.0, random.Random(1), "kids") == []


def test_ambient_events_route_to_the_right_sound():
    from sem_alvorada.audio.noise import sound_for_event
    from sem_alvorada.audio.catalog import REQUIRED_SOUNDS
    rng = random.Random(2)
    for _, event in _simulate_ambient(4):
        assert sound_for_event(event, rng) in REQUIRED_SOUNDS


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} testes passaram")


if __name__ == "__main__":
    main()
