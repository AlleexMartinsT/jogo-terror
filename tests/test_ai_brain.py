"""Testes do cérebro da entidade: percepção (números), contrato da API e cenários simulados.

    python tests/test_ai_brain.py      (ou pytest)

Os cenários vêm de tests/sim_ai.py (LayoutWorldView + NavGrid.from_layout + NoiseSystem, sem bpy).
"""
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import sim_ai  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.ai import BrainTuning, EntityBrain, LayoutWorldView, Senses  # noqa: E402
from sem_alvorada.ai import perception as P  # noqa: E402
from sem_alvorada.audio.noise import HeardEvent, NoiseSystem  # noqa: E402

T = BrainTuning()
WORLD = LayoutWorldView()
ANIMS = {"idle", "stalk", "walk", "run", "attack", "stare"}


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def beam_to(player_pos, target):
    v = (target[0] - player_pos[0], target[1] - (player_pos[1]), target[2] - (player_pos[2] + 1.35))
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


# ---- visão: números --------------------------------------------------------
def test_vision_range_table():
    entity = (6.9, 9.0, 0.0)
    head = P.entity_head(entity)
    player = (6.9, 2.0, 0.0)
    aimed = beam_to(player, head)
    away = (0.0, -1.0, 0.0)

    def reach(speed=2.6, crouch=False, light=False, beam=None, aggression=0):
        return P.vision_range(T, Senses(player, 0.0, 0.0, speed, crouch, light, beam), head, aggression)

    assert approx(reach(), C.DARK_VISION_RANGE)
    assert approx(reach(speed=1.2, crouch=True), C.DARK_VISION_RANGE * 0.6)
    assert approx(reach(speed=0.0), C.DARK_VISION_RANGE * 0.7)
    assert approx(reach(speed=0.0, crouch=True), C.DARK_VISION_RANGE * 0.6 * 0.7)
    assert approx(reach(speed=4.6), C.DARK_VISION_RANGE * 1.25)
    assert approx(reach(light=True, beam=aimed), C.FLASH_RANGE_VISION)
    assert approx(reach(light=True, beam=aimed, speed=0.0), C.FLASH_RANGE_VISION * 0.7)
    assert approx(reach(light=True, beam=away), C.DARK_VISION_RANGE * 1.4)
    assert approx(reach(aggression=2), C.DARK_VISION_RANGE * 1.2)
    assert reach(light=True, beam=aimed) > 3 * reach()


def test_cone_line_of_sight_and_touch_range():
    entity, yaw = (6.9, 5.0, 0.0), 0.0                      # olhando para o norte (+Y)

    def sees(player, speed=2.6):
        senses = Senses(player, 0.0, 0.0, speed, False, False, None)
        return P.look_at_player(T, WORLD, entity, yaw, senses, 0).visible

    assert sees((6.9, 8.0, 0.0)), "de frente, 3 m"
    assert not sees((6.9, 2.0, 0.0)), "de costas, 3 m"
    assert sees((6.9, 4.0, 0.0)), "de costas mas colado (1 m)"
    assert sees((6.9 - 1.6 * math.sin(math.radians(50)), 5.0 + 1.6 * math.cos(math.radians(50)), 0.0)), "50 graus fora do eixo"
    assert not sees((6.9 - 1.6 * math.sin(math.radians(65)), 5.0 + 1.6 * math.cos(math.radians(65)), 0.0)), "65 graus fora do eixo"
    behind_wall = Senses((3.0, 8.0, 0.0), 0.0, 0.0, 2.6, False, False, None)        # escritório
    assert not P.look_at_player(T, WORLD, (3.0, 4.5, 0.0), 0.0, behind_wall, 0).visible, "parede entre os dois"
    assert not P.look_at_player(T, WORLD, (6.9, 5.0, 0.0), 0.0, Senses((6.9, 5.0, 2.8), 0.0, 0.0, 2.6, False, False, None), 0).visible


def test_awareness_grows_gradually_and_decays_slowly():
    def seconds_to_chase(distance, speed=2.6, crouch=False):
        senses = Senses((0, 0, 0), 0.0, 0.0, speed, crouch, False, None)
        reach = P.vision_range(T, senses, (0, distance, 2.3), 0)
        sighting = P.Sighting(True, distance, reach)
        awareness, steps = 0.0, 0
        while awareness < T.chase_awareness and steps < 3000:
            awareness += P.awareness_change(T, sighting, 0, False, 1 / 30)
            steps += 1
        return steps / 30

    close, far = seconds_to_chase(2.0), seconds_to_chase(5.0)
    assert 0.3 < close < 1.3 and 1.0 < far < 3.0 and close < far
    hidden = seconds_to_chase(2.0, speed=0.0, crouch=True)
    assert hidden > close * 0.9, "agachado e parado não o denuncia mais depressa"
    unseen = P.Sighting(False, 10.0, 5.5)
    assert approx(P.awareness_change(T, unseen, 0, False, 10.0), -1.2)
    assert P.awareness_change(T, unseen, 2, False, 10.0) > -1.2, "agressividade aumenta a memória"


# ---- audição -----------------------------------------------------------------
def heard(uid, loudness, kind="run", source="player", pos=(3.0, 8.0, 0.0), age=0.0):
    return HeardEvent(uid, source, kind, pos, loudness, age, "den")


def test_hearing_error_shrinks_with_volume():
    rng = random.Random(1)
    hearing = P.Hearing(T, rng)
    offsets = {}
    for loudness in (0.12, 0.4, 0.9):
        samples = []
        for uid in range(300):
            result = hearing.assess([heard(uid + 1000 * int(loudness * 100), loudness)], uid * 10.0, 0)
            samples.append(math.dist(result.target[:2], (3.0, 8.0)))
        radius = max(0.3, T.error_radius_max * (1 - loudness))
        assert max(samples) <= radius + 1e-9
        offsets[loudness] = sum(samples) / len(samples)
    assert offsets[0.12] > offsets[0.4] > offsets[0.9]
    assert offsets[0.9] < 0.4 and offsets[0.12] > 1.5


def test_loud_or_repeated_sounds_are_strong():
    hearing = P.Hearing(T, random.Random(2))
    assert not hearing.assess([heard(1, 0.30)], 0.0, 0).strong
    assert hearing.assess([heard(2, 0.60)], 1.0, 0).strong
    quiet = P.Hearing(T, random.Random(3))
    flags = [quiet.assess([heard(uid, 0.2)], uid * 1.0, 0).strong for uid in range(1, 5)]
    assert flags == [False, False, True, True], "três sons fracos em 4 s viram perseguição"
    spaced = P.Hearing(T, random.Random(3))
    assert not any(spaced.assess([heard(uid, 0.2)], uid * 5.0, 0).strong for uid in range(1, 6)), "espaçados não contam"
    assert not P.Hearing(T, random.Random(4)).assess([heard(9, 0.5)], 0.0, 0).strong
    assert P.Hearing(T, random.Random(4)).assess([heard(9, 0.5)], 0.0, 2).strong, "agressividade baixa o limiar"


def test_same_event_is_handled_once_and_ambient_distracts_only_if_strong_enough():
    hearing = P.Hearing(T, random.Random(5))
    event = heard(1, 0.3)
    assert hearing.assess([event], 0.0, 0) is not None
    assert hearing.assess([event], 0.1, 0) is None
    phone = heard(2, 0.5, "phone", "ambient", (10.0, 7.5, 0.9))
    result = hearing.assess([phone], 0.2, 0)
    assert result is not None and result.target == (10.0, 7.5, 0.9) and not result.strong
    assert hearing.assess([heard(3, 0.3, "creak", "ambient")], 0.3, 0) is None, "rangido fraco não distrai"
    assert hearing.assess([heard(4, 0.3, "glass", "ambient")], 0.4, 0) is not None


# ---- contrato da API ------------------------------------------------------------
def make_brain(seed=1, nav=None):
    world = LayoutWorldView()
    return EntityBrain(world, NoiseSystem(world.door_openness), random.Random(seed), nav=nav or sim_ai.shared_nav()), world


def test_dormant_until_activated_and_positions_snap_into_the_house():
    brain, _ = make_brain()
    senses = Senses((1.0, 1.0, 0.0))
    out = brain.update(1 / 30, senses)
    assert out.state == "dormant" and out.anim == "idle" and out.speed == 0.0 and out.drone == 0.0 and not out.kill
    brain.activate((-0.6, 3.0, 0.0), hunt=False)              # fora da parede: vai para a célula andável mais próxima
    assert brain.state == "patrol" and layout.room_at(brain.body.x, brain.body.y, brain.body.z) is not None
    try:
        brain.activate((60.0, 60.0, 0.0))
        raise AssertionError("deveria recusar posição longe da casa")
    except ValueError:
        pass
    brain.deactivate()
    assert brain.update(1 / 30, senses).state == "dormant"


def test_aggression_is_clamped_and_output_contract_holds():
    brain, _ = make_brain()
    brain.set_aggression(7)
    assert brain.aggression == 2
    brain.set_aggression(-3)
    assert brain.aggression == 0
    sim = sim_ai.scenario_wander(seed=12, seconds=60.0)
    for _, x, y, z, state, speed, drone, _layer in sim.trace:
        assert state in C.ENTITY_STATES and 0.0 <= drone <= 1.0 and speed >= 0.0
        assert all(math.isfinite(v) for v in (x, y, z))
    out = sim.out
    assert out.anim in ANIMS and isinstance(out.kill, bool)
    assert out.look_target is None or len(out.look_target) == 3


# ---- cenários ---------------------------------------------------------------------
def assert_clean_run(sim, still_limit=10.0):
    assert sim_ai.wall_violations(sim.trace) == [], sim_ai.wall_violations(sim.trace)[:5]
    assert sim_ai.outside_house(sim.trace) == []
    assert sim_ai.longest_stillness(sim.trace) <= still_limit, f"parada de {sim_ai.longest_stillness(sim.trace):.1f}s"
    assert sim.brain.counters["unstick"] <= 1, sim.brain.counters


def transitions_per_second(log, window=1.0):
    """Trocas de estado por janela; reavisos no mesmo estado (novo som durante investigate) não contam: com os passos no
    compasso da animação o jogador faz um som a cada ~0.5 s e cada um fica no log."""
    times = [t for t, old, new, *_ in log if old != new]
    return max((sum(1 for u in times if t <= u < t + window) for t in times), default=0)


def test_patrol_visits_many_rooms_in_three_minutes():
    sim = sim_ai.scenario_patrol(seed=1, seconds=180.0)
    sim_ai.describe("patrulha", sim)
    assert len(sim.rooms_visited()) >= 7 and "garage" not in sim.rooms_visited()
    levels = {round(t[3]) for t in sim.trace}
    assert {0, 3} <= levels, "patrulha os dois andares (z 0 e 2.8)"
    assert set(sim.states_visited()) == {"patrol"}
    moving = [t[5] for t in sim.trace if t[5] > 0.3]
    assert approx(sum(moving) / len(moving), C.ENTITY_SPEED_PATROL, 0.05)
    assert_clean_run(sim, 6.0)


def test_investigates_a_noise_made_by_a_fake_player_elsewhere():
    sim = sim_ai.scenario_investigate()
    assert sim.states_visited()[:2] == ["investigate", "patrol"]
    closest = min(math.hypot(x - sim.noise_origin[0], y - sim.noise_origin[1]) for _, x, y, *_ in sim.trace)
    assert closest < 3.0, f"chegou a {closest:.1f} m da origem do som"
    assert not sim.brain.kill and "chase" not in sim.states_visited()
    assert_clean_run(sim)


def test_ambient_phone_distracts_the_patrolling_entity():
    sim = sim_ai.scenario_ambient_distraction()
    assert sim.states_visited()[0] == "investigate"
    closest = min(math.hypot(x - sim.noise_origin[0], y - sim.noise_origin[1]) for _, x, y, *_ in sim.trace)
    assert closest < 1.5 and "chase" not in sim.states_visited()
    why = next(reason for _, _, new, reason in sim.brain.log if new == "investigate")
    assert why.startswith("ouviu phone"), why


def test_chases_through_doors_and_up_the_stairs_then_kills():
    sim = sim_ai.scenario_chase_across_floors()
    sim_ai.describe("perseguicao", sim)
    assert sim.out.kill and "chase" in sim.states_visited()
    assert any(t[7] == 2 for t in sim.trace), "passou pela camada da escada"
    assert max(t[3] for t in sim.trace) >= 2.7 and sim.trace[0][3] == 0.0
    assert any(who == "entity" for _door, who in sim.world.opened_by), "abriu portas pelo world view"
    assert max(t[5] for t in sim.trace) <= C.ENTITY_SPEED_CHASE + 1e-6
    assert_clean_run(sim)


def test_kills_a_player_standing_still_in_view():
    lit = sim_ai.scenario_kill_standing(flashlight=True)
    assert lit.out.kill and lit.time < 6.0 and lit.states_visited()[-1] == "attack"
    dark_far = sim_ai.Sim(5, player_at=(6.9, 2.0, 0.0), entity_at=(6.9, 9.0, 0.0), entity_yaw=C.dir_yaw(0, -1), entity_pause=30.0)
    awareness = []
    dark_far.run(20.0, on_step=lambda s, out: awareness.append(out.awareness))
    assert dark_far.states_visited() == ["patrol"] and max(awareness) < 0.1, "parado no escuro a 7 m ele não enxerga"
    near = sim_ai.Sim(9, player_at=(6.9, 6.0, 0.0), entity_at=(6.9, 9.0, 0.0), entity_yaw=C.dir_yaw(0, -1), entity_pause=30.0)
    near.run(20.0, until=lambda s, out: out.kill)
    assert near.out.kill, "parado no escuro a 3 m, de frente, ele enxerga (alcance 3.85 m)"
    assert {"chase", "attack"} <= set(near.states_visited())


def test_loses_a_player_hidden_behind_a_closed_door_and_searches():
    sim = sim_ai.scenario_hide_behind_door()
    sim_ai.describe("esconder", sim)
    states = sim.states_visited()
    assert states[:3] == ["patrol", "chase", "search"] and "patrol" in states[3:], states
    assert not sim.brain.kill and ("kids_hall", "entity") in sim.world.opened_by
    chase_end = next(t for t, s in sim.state_log if s == "search")
    chase_start = next(t for t, s in sim.state_log if s == "chase")
    assert chase_end - chase_start >= T.lose_time, "espera a memória de 4 s antes de desistir"
    search_end = next(t for t, s in sim.state_log if s == "patrol" and t > chase_end)
    assert approx(search_end - chase_end, T.search_time, 0.3), f"busca durou {search_end - chase_end:.1f}s"
    assert_clean_run(sim)


def test_locked_door_stops_the_chase():
    sim = sim_ai.scenario_hide_behind_door(lock_after_close=True)
    inside = [t for t in sim.trace if layout.room_at(t[1], t[2], t[3]) and layout.room_at(t[1], t[2], t[3]).id == "kids"]
    assert inside == [], "porta trancada é intransponível"
    assert not sim.brain.kill and "search" in sim.states_visited()
    assert_clean_run(sim)


def test_stalk_is_silent_slow_and_ends_in_the_attack():
    sim = sim_ai.scenario_stalk()
    stalk = [t for t in sim.trace if t[4] == "stalk"]
    assert len(stalk) >= 30, f"espreitou só {len(stalk) / 30:.1f}s"
    assert all(t[6] == 0.0 for t in stalk), "drone tem que ser 0 durante stalk"
    assert max(t[5] for t in stalk) <= C.ENTITY_SPEED_STALK + 1e-6
    before = [t for t in sim.trace if t[4] == "patrol"]
    assert max(t[6] for t in before) > 0.5, "antes do stalk o zumbido cresce com a proximidade"
    assert sim.out.kill
    assert sim.states_visited()[-2:] == ["chase", "attack"] or sim.states_visited()[-1] == "attack"


def test_drone_grows_with_proximity_and_is_bounded():
    sim = sim_ai.scenario_chase_across_floors()
    drones = [t[6] for t in sim.trace]
    assert max(drones) > 0.7 and min(drones) >= 0.0 and max(drones) <= 1.0
    patrol = sim_ai.scenario_patrol(seed=2, seconds=150.0)
    px, py, _ = sim_ai.GARAGE_HIDEOUT
    for _, x, y, z, _state, _speed, drone, _layer in patrol.trace:
        distance = math.hypot(x - px, y - py) + 2.0 * abs(z)
        if distance > 19.0:
            assert drone < 0.05, f"zumbido a {distance:.0f} m"
        if distance < 7.0:
            assert drone > 0.25, f"silêncio a {distance:.0f} m"


def test_never_crosses_walls_never_leaves_the_house_never_sticks():
    for seed, aggression in ((8, 0), (9, 1), (10, 2), (11, 2)):
        sim = sim_ai.scenario_wander(seed=seed, seconds=200.0, aggression=aggression)
        assert_clean_run(sim)
        assert transitions_per_second(sim.brain.log) <= 6, (seed, aggression)
        assert sim.kills >= 1, "o jogador imortal foi morto pelo menos uma vez"


def test_locked_garage_is_never_entered_until_unlocked():
    locked = sim_ai.scenario_wander(seed=13, seconds=400.0, aggression=2)
    assert "garage" not in locked.rooms_visited()
    opened = sim_ai.scenario_wander(seed=13, seconds=400.0, aggression=2, unlock_garage=True)
    assert "garage" in opened.rooms_visited()
    assert_clean_run(opened)


def test_aggression_makes_patrol_and_chase_faster_but_not_faster_than_running():
    calm = sim_ai.scenario_patrol(seed=3, seconds=60.0, aggression=0)
    fierce = sim_ai.scenario_patrol(seed=3, seconds=60.0, aggression=2)
    top = lambda sim, state: max(t[5] for t in sim.trace if t[4] == state)            # noqa: E731
    assert approx(top(fierce, "patrol") / top(calm, "patrol"), 1.3, 0.01)
    chase_calm = sim_ai.scenario_kill_standing()
    chase_fierce = sim_ai.Sim(5, 2, player_at=(6.9, 2.0, 0.0), entity_at=(6.9, 9.0, 0.0), entity_yaw=C.dir_yaw(0, -1), entity_pause=30.0)
    chase_fierce.player.flashlight, chase_fierce.player.aim = True, (6.9, 9.0, 2.2)
    chase_fierce.run(10.0, until=lambda s, out: out.kill)
    assert top(chase_fierce, "chase") > top(chase_calm, "chase")
    assert top(chase_fierce, "chase") < C.SPEED_RUN


def test_simulation_is_deterministic():
    def fingerprint(seed):
        sim = sim_ai.scenario_wander(seed=seed, seconds=60.0)
        return [(round(t[1], 4), round(t[2], 4), t[4]) for t in sim.trace]

    assert fingerprint(21) == fingerprint(21)
    assert fingerprint(21) != fingerprint(22)


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} testes passaram")


if __name__ == "__main__":
    main()
