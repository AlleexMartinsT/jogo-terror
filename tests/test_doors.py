"""Testes das portas: movimento suave, trinco, batida, ranger e a reação da entidade ao ranger.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_doors.py      (ou pytest)

O movimento e o jogo usam o `Game` de verdade (mundo mínimo de test_engine_fakes). As estatísticas do
ranger usam um `Game` de mentira só com o que o `DoorManager` consome, para sortear milhares de vezes.
O comportamento da IA usa o `NoiseSystem` e o `EntityBrain` reais, ligados às portas reais do jogo.
"""
import math
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_engine_fakes as fk  # noqa: E402
from test_engine_fakes import DT, make_game, start_playing, teleport  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.ai import EntityBrain  # noqa: E402
from sem_alvorada.audio.noise import NoiseSystem  # noqa: E402
from sem_alvorada.engine import doors as door_module  # noqa: E402
from sem_alvorada.engine.state import GameState  # noqa: E402

FPS = 60.0
FRAME = 1.0 / FPS
ALL_DOORS = [op.id for op in layout.doors()]


# --------------------------------------------------------------------------
# Auxiliares
# --------------------------------------------------------------------------
class AlwaysCreak(random.Random):
    """O sorteio de chance (a primeira chamada de cada par) dá zero: toda dobradiça que pode ranger, range.
    O sorteio da variante (a segunda chamada, dentro de `choices`) é normal, para os quatro rangidos aparecerem."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self._calls = 0

    def random(self):
        self._calls += 1
        return 0.0 if self._calls % 2 == 1 else super().random()


class NeverCreak(random.Random):
    def random(self):
        return 0.999999


class StubGame:
    """O mínimo que o DoorManager lê do Game, com registro do que ele toca e emite."""

    def __init__(self, seed=1, crouching=False, speed=2.6, rng=None):
        self.state = GameState()
        self.rng = rng or random.Random(seed)
        self.clock = 0.0
        self.player = SimpleNamespace(crouching=crouching, speed=speed, x=-50.0, y=-50.0, level=0,
                                      feet=(-50.0, -50.0, 0.0))
        self.sounds, self.noises = [], []
        self.noise = None

    def sound(self, name, pos=None, volume=1.0):
        self.sounds.append(name)

    def make_noise(self, kind, pos, loudness, sound=None, source="player", opening=""):
        self.noises.append((source, kind, loudness, opening))
        if sound:
            self.sounds.append(sound)


def stub_doors(**kwargs):
    game = StubGame(**kwargs)
    return game, door_module.DoorManager(game, None)


def played(game):
    return game.audio.played_names()


def trace_door(game, door_id, seconds, fps=FPS, player=None):
    door = game.doors.get(door_id)
    samples, dt = [], 1.0 / fps
    for k in range(int(round(seconds * fps))):
        game.doors.update(dt, player)
        samples.append(((k + 1) * dt, door.openness, door.velocity))
    return samples


def fresh_game():
    game = start_playing(make_game(world=False))
    game.rng = NeverCreak()
    return game


def unlocked_game():
    game = fresh_game()
    game.state.unlocked |= {"front", "back", "garage"}
    return game


def motion_window(samples, low=1e-4, high=1.0 - 1e-4):
    """(início, fim) em segundos do trecho em que a folha realmente se move entre `low` e `high`."""
    moving = [t for t, x, _ in samples if low < x < high]
    return (moving[0], moving[-1]) if moving else (0.0, 0.0)


# --------------------------------------------------------------------------
# Curva de movimento
# --------------------------------------------------------------------------
def test_quintic_hits_boundary_conditions():
    coefficients = door_module.quintic_coefficients(0.2, 0.7, -1.5, 1.0, 0.9, end_velocity=-0.4)
    x0, v0, a0 = door_module.polynomial_state(coefficients, 0.0)
    x1, v1, a1 = door_module.polynomial_state(coefficients, 0.9)
    assert (x0, v0, a0) == (0.2, 0.7, -1.5)
    assert abs(x1 - 1.0) < 1e-9 and abs(v1 + 0.4) < 1e-9 and abs(a1) < 1e-9


def test_opening_is_smooth_starts_and_ends_at_rest():
    game = fresh_game()
    game.doors.toggle("kids_master")
    samples = trace_door(game, "kids_master", 2.5)
    xs = [x for _, x, _ in samples]
    assert xs[-1] == 1.0 and all(b >= a for a, b in zip(xs, xs[1:])), "abertura tem de ser monótona e chegar a 1"
    steps = [b - a for a, b in zip(xs, xs[1:])]
    assert max(steps) < 0.04, f"salto por quadro a 60 fps: {max(steps):.3f}"
    start, end = motion_window(samples)
    first = [x for t, x, _ in samples if t <= start + 3 * FRAME]
    assert max(first) < 0.006, "a folha tem de sair do repouso devagar (uma porta linear andaria 0,08 nisso)"
    last = [x for t, x, _ in samples if end - 3 * FRAME <= t <= end]
    assert 1.0 - min(last) < 0.006, "e chegar ao fim devagar"
    accel_jumps = [abs((c - b) - (b - a)) / FRAME for a, b, c in zip(xs, xs[1:], xs[2:])]
    assert max(accel_jumps) < 0.2, f"velocidade com salto: {max(accel_jumps):.3f}"


def test_handle_turns_before_the_leaf_moves():
    game = fresh_game()
    door = game.doors.get("kids_master")
    game.doors.toggle("kids_master")
    for _ in range(int(0.1 * FPS)):
        game.doors.update(FRAME)
    assert door.openness == 0.0, "a folha não pode sair antes de a maçaneta girar"
    assert door.turn > 0.5, "a maçaneta tem de estar girando"
    trace_door(game, "kids_master", 2.0)
    assert door.openness == 1.0 and door.turn == 0.0, "a maçaneta volta quando a folha já se foi"


def test_duration_stays_between_0_9_and_1_4_seconds_for_every_door_and_pace():
    for door_id in ALL_DOORS:
        for hurried, crouch, speed in ((True, False, 4.6), (False, False, 2.6), (False, False, 0.0), (False, True, 1.2)):
            game = unlocked_game()
            game.player.crouching, game.player.speed = crouch, speed
            door = game.doors.get(door_id)
            game.doors.toggle(door_id, hurried=hurried)
            seconds = door.glide.seconds
            assert 0.9 <= seconds <= 1.4, f"{door_id} hurried={hurried} crouch={crouch}: {seconds:.2f} s"
            samples = trace_door(game, door_id, 3.0)
            arrival = next(t for t, x, _ in samples if x >= 1.0)
            assert abs(arrival - (door_module.HANDLE_LEAD + seconds)) < 3 * FRAME, f"{door_id}: chegou em {arrival:.2f} s"


def test_pace_changes_speed_in_the_right_direction():
    def seconds_for(hurried=False, crouch=False, speed=2.6):
        game = fresh_game()
        game.player.crouching, game.player.speed = crouch, speed
        game.doors.toggle("master_hall", hurried=hurried)
        return game.doors.get("master_hall").glide.seconds
    hurried, normal = seconds_for(True, speed=4.6), seconds_for()
    still, crouched = seconds_for(speed=0.0), seconds_for(crouch=True, speed=1.2)
    assert hurried < normal < still < crouched, (hurried, normal, still, crouched)


def test_reversing_midway_keeps_position_and_velocity_continuous():
    for stop_at in (0.35, 0.6, 0.9):
        game = fresh_game()
        game.doors.toggle("kids_master")
        trace_door(game, "kids_master", 0.14 + stop_at)
        door = game.doors.get("kids_master")
        x_before, v_before = door.openness, door.velocity
        assert 0.0 < x_before < 1.0
        game.doors.toggle("kids_master")
        assert door.target == 0.0
        after = trace_door(game, "kids_master", 3.0)
        xs = [x_before] + [x for _, x, _ in after]
        steps = [b - a for a, b in zip(xs, xs[1:])]
        assert abs(steps[0] / FRAME - v_before) < 0.4, "a velocidade tem de continuar de onde estava"
        assert max(abs(s) for s in steps) < 0.07, f"salto de posição ao inverter: {max(abs(s) for s in steps):.3f}"
        jumps = [abs((c - b) - (b - a)) / FRAME for a, b, c in zip(xs, xs[1:], xs[2:])]
        assert max(jumps) < 0.6, f"velocidade com salto ao inverter: {max(jumps):.2f}"
        assert max(xs) < 1.0 and min(xs) >= 0.0 and xs[-1] == 0.0
        assert max(xs) - x_before < 0.2, "a inércia leva a folha só um pouco adiante antes de voltar"


def test_closing_ends_with_a_latch_that_settles():
    game = fresh_game()
    game.doors.snap("kids_master", 1.0)
    assert game.doors.toggle("kids_master") == "closed"
    door = game.doors.get("kids_master")
    samples = trace_door(game, "kids_master", 2.5)
    assert "door_close" in played(game) and played(game).count("door_latch") == 1
    arrival = next(t for t, x, _ in samples if x <= 1e-9)
    after = [x for t, x, _ in samples if t > arrival and t < arrival + 0.3]
    assert 0.0 < max(after) <= 0.02, f"acomodação do trinco: {max(after):.4f}"
    assert door.openness == 0.0 and door.settle is None
    assert game.noise_levels()["player"] >= 0.0


def test_door_close_noise_is_logged_when_closing_starts():
    game = fresh_game()
    game.doors.snap("den_hall", 1.0)
    game.doors.toggle("den_hall")
    assert [e for e in game.noise_log if e[1] == "door_close"][-1][2] == C.NOISE_PLAYER["door_close"]


def test_slam_is_fast_and_rebounds_a_little():
    game = fresh_game()
    game.doors.snap("den_hall", 1.0)
    assert game.doors.toggle("den_hall", hurried=True) == "slammed"
    assert "door_slam" in played(game)
    samples = trace_door(game, "den_hall", 0.6)
    arrival = next(t for t, x, _ in samples if x <= 1e-9)
    assert arrival <= 0.25, f"a batida levou {arrival:.2f} s"
    rebound = [x for t, x, _ in samples if t > arrival + FRAME]
    assert 0.003 < max(rebound) < 0.05, f"retorno da folha: {max(rebound):.3f}"
    last_moving = max(t for t, x, _ in samples if x > 0.0)
    assert last_moving < 0.4, f"a folha só assentou em {last_moving:.2f} s"
    assert "door_latch" not in played(game), "a batida tem o próprio estrondo"


def test_locked_door_stays_shut_and_only_rattles():
    game = fresh_game()
    assert game.doors.toggle("front") == "locked"
    assert "door_locked" in played(game)
    samples = trace_door(game, "front", 1.0)
    assert max(x for _, x, _ in samples) < 0.01 and samples[-1][1] == 0.0
    assert game.doors.get("front").target == 0.0


def test_second_press_during_handle_turn_is_ignored():
    game = fresh_game()
    assert game.doors.toggle("kids_master") == "opened"
    for _ in range(3):
        game.doors.update(FRAME)
    assert game.doors.toggle("kids_master") == "opened", "o segundo [E] não pode desfazer a abertura"
    trace_door(game, "kids_master", 2.0)
    assert game.doors.openness("kids_master") == 1.0


def test_would_trap_blocks_closing_on_the_player_during_the_whole_motion():
    game = fresh_game()
    door_id = "den_hall"
    door = game.doors.get(door_id)
    game.doors.snap(door_id, 1.0)
    teleport(game, 5.0, 8.65, 0.0, 0)          # parado no vão
    player = game.player
    assert game.doors._would_trap(door, 0.0, player), "a folha fechada cairia sobre o jogador"
    assert not game.doors._would_trap(door, 1.0, player), "a porta aberta não o atinge"
    game.doors.set_openness(door_id, 0.0)
    samples = trace_door(game, door_id, 2.0, player=player)
    assert door.openness > 0.0, "fechou em cima do jogador"
    stuck = [x for _, x, _ in samples[-30:]]
    assert max(stuck) - min(stuck) < 1e-9, "a folha tem de ficar parada enquanto o jogador está na frente"
    teleport(game, 5.0 - 3.0, 8.65, 0.0, 0)
    trace_door(game, door_id, 3.0, player=game.player)
    assert door.openness == 0.0, "com o caminho livre a porta fecha"


def test_segment_follows_the_leaf_every_frame():
    game = fresh_game()
    door = game.doors.get("kids_hall")
    game.doors.toggle("kids_hall")
    for _ in range(int(2.0 * FPS)):
        game.doors.update(FRAME)
        x0, y0, x1, y1, half = door.segment
        end = door.leaf_point(1.0)
        assert abs(x1 - end[0]) < 1e-9 and abs(y1 - end[1]) < 1e-9
        assert abs(math.hypot(x1 - x0, y1 - y0) - door.length) < 1e-6, "a folha não pode encolher"
        assert (x0, y0) == door.hinge
        assert game.doors.segments(door.level).count(door.segment) == 1
    assert abs(door.yaw - door.open_yaw) < 1e-9


def test_blocks_sight_tracks_the_moving_leaf():
    game = fresh_game()
    door_id = "living_hall"
    center = game.doors.center(door_id)
    a, b = (center[0] - 1.0, center[1], 1.5), (center[0] + 1.0, center[1], 1.5)
    assert game.doors.blocks_sight(a, b)
    game.doors.toggle(door_id)
    trace_door(game, door_id, 2.0)
    assert not game.doors.blocks_sight(a, b)


def test_snap_set_openness_and_reset_keep_working():
    game = fresh_game()
    game.doors.snap("kids_hall", 0.6)
    door = game.doors.get("kids_hall")
    assert door.openness == 0.6 and door.target == 0.6 and door.glide is None and door.velocity == 0.0
    assert not game.doors.is_open("kids_hall") or door.target > door_module.NEAR_OPEN
    game.doors.set_openness("kids_hall", 1.0)
    samples = trace_door(game, "kids_hall", 3.0)
    assert door.openness == 1.0 and samples[0][1] < 0.65, "set_openness anima, não salta"
    game.doors.set_openness("kids_hall", 0.0, speed=2.0)
    assert abs(door.glide.seconds - 0.5) < 1e-9, "speed é a média do trajeto: 1.0 de curso a 2.0/s"
    trace_door(game, "kids_hall", 3.0)
    assert door.openness == 0.0
    game.doors.snap("kids_hall", 1.0)
    game.doors.reset()
    assert all(d.openness == 0.0 and not d.moving for d in game.doors.doors.values())
    assert game.doors.openness("dining_hall") == 1.0, "arcos contam como abertos"


def test_cutscene_style_snap_every_frame_is_stable():
    """As cutscenes chamam snap a cada quadro com um valor interpolado: nada pode lutar contra isso."""
    game = fresh_game()
    for k in range(120):
        game.doors.snap("garage_door", k / 119.0)
        game.doors.update(FRAME)
        assert abs(game.doors.openness("garage_door") - k / 119.0) < 1e-9


def test_bolt_object_follows_the_handle_turn():
    scene = fk.fresh_scene()
    fk.build_minimal_world(scene)
    plan = layout.door_transform(layout.OPENINGS["kids_hall"])
    pivot = fk.bpy.data.objects.new("Door_kids_hall", None)
    bolt = fk.bpy.data.objects.new("DoorBolt_kids_hall", None)
    for obj in (pivot, bolt):
        scene.collection.objects.link(obj)
    pivot[C.P_DOOR_CLOSED], pivot[C.P_DOOR_OPEN], pivot[C.P_LOCK] = plan["closed_yaw"], plan["open_yaw"], ""
    pivot.location = plan["hinge"]
    bolt.parent, bolt.location = pivot, (0.8815, 0.0, 0.95)
    game = start_playing(fk.Game(scene, audio=False, entity=False, cutscenes=False))
    game.rng = NeverCreak()
    game.doors.toggle("kids_hall")
    lows = []
    for _ in range(int(0.4 * FPS)):
        game.doors.update(FRAME)
        lows.append(bolt.location.x)
    assert min(lows) < 0.8815 - 0.008, "a lingueta tem de recolher quase o curso todo"
    trace_door(game, "kids_hall", 2.0)
    assert abs(bolt.location.x - 0.8815) < 1e-4, "e voltar ao soltar a maçaneta"


# --------------------------------------------------------------------------
# Ranger: tabela, ritmo, ferrugem, semente
# --------------------------------------------------------------------------
def test_every_door_has_a_kind_and_chances_are_in_the_documented_table():
    expected = {"master_hall": "quarto", "kids_hall": "quarto", "kids_master": "quarto",
                "bath_hall": "banheiro", "bath_study": "banheiro",
                "den_hall": "escritorio", "den_living": "escritorio", "study_hall": "escritorio",
                "living_hall": "sala", "kitchen_hall": "cozinha_garagem", "garage_door": "cozinha_garagem",
                "front": "exterior", "back": "exterior"}
    assert set(expected) == set(ALL_DOORS)
    _, doors = stub_doors()
    for door_id, kind in expected.items():
        door = doors.get(door_id)
        assert door.kind == kind, door_id
        assert door.creak_chance == door_module.KINDS[kind].creak_chance
        assert 0.1 <= door.creak_chance <= 0.5
    assert doors.get("front").creak_chance > doors.get("living_hall").creak_chance
    gate = layout.Opening("gate", "garage_door", 0, "x", 0.0, 13.5, 17.5, rooms=("garage",))
    assert door_module.classify(gate) == "portao"


def test_probability_orders_by_pace_and_rust():
    game, doors = stub_doors()
    chance = {pace: doors.creak_probability("kids_hall", pace) for pace in door_module.PACE_CREAK}
    assert chance["apressado"] > chance["normal"] > chance["devagar"] > chance["agachado"]
    assert abs(chance["normal"] - 0.30 * 2.2) < 1e-9, "porta de quarto nunca mexida, andando: 66%"
    door = doors.get("kids_hall")
    door.rested_since = game.clock
    recent = doors.creak_probability("kids_hall", "normal")
    assert abs(recent - 0.30) < 1e-9 and recent < chance["normal"]
    game.clock += door_module.RUST_FULL / 2
    assert recent < doors.creak_probability("kids_hall", "normal") < chance["normal"]
    game.clock += door_module.RUST_FULL
    assert abs(doors.creak_probability("kids_hall", "normal") - chance["normal"]) < 1e-9
    assert all(p <= door_module.MAX_CREAK_CHANCE for p in chance.values())


def measured_creak_rate(door_id, trials=4000, seed=7, crouching=False, speed=2.6, hurried=False, rested=False):
    game, doors = stub_doors(seed=seed, crouching=crouching, speed=speed)
    door = doors.get(door_id)
    creaks = 0
    for _ in range(trials):
        if rested:
            door.rested_since = game.clock
        before = len(game.noises)
        door.pace = doors._pace(hurried)
        if doors._roll_creak(door, "player") is not None:
            creaks += 1
        assert len(game.noises) == before
    return creaks / trials


def test_creak_rates_match_the_table_for_each_kind():
    for door_id in ("kids_hall", "bath_hall", "den_hall", "living_hall", "kitchen_hall", "front"):
        _, doors = stub_doors()
        door = doors.get(door_id)
        expected = door.creak_chance * door_module.PACE_CREAK["normal"] * (1 + door_module.RUST_GAIN)
        measured = measured_creak_rate(door_id)
        assert abs(measured - min(expected, 0.9)) < 0.03, f"{door_id}: {measured:.3f} contra {expected:.3f}"


def test_crouched_and_slow_creak_less_and_hurried_creaks_more():
    normal = measured_creak_rate("master_hall", rested=True)
    slow = measured_creak_rate("master_hall", speed=0.0, rested=True)
    crouched = measured_creak_rate("master_hall", crouching=True, speed=1.2, rested=True)
    hurried = measured_creak_rate("master_hall", hurried=True, speed=4.6, rested=True)
    assert hurried > normal * 1.5 > slow * 1.5 > crouched * 1.5, (hurried, normal, slow, crouched)
    assert crouched < 0.2 and hurried > 0.45


def test_first_opening_after_a_long_rest_is_the_likeliest():
    rested = measured_creak_rate("kids_master", rested=True)
    first = measured_creak_rate("kids_master", rested=False)
    assert first > rested * 1.8, (first, rested)


def test_creak_sequence_is_deterministic_per_seed():
    def rolls(seed):
        game, doors = stub_doors(seed=seed)
        out = []
        for index in range(80):
            door = doors.get(ALL_DOORS[index % len(ALL_DOORS)])
            door.pace = ("apressado", "normal", "devagar", "agachado")[index % 4]
            game.clock += 11.0
            out.append(doors._roll_creak(door, "player"))
        return out
    assert rolls(11) == rolls(11) and rolls(11) != rolls(12)

    def played_with(seed):
        game = start_playing(make_game(world=False, seed=seed))
        for door_id in ("kids_hall", "kids_master", "master_hall", "bath_hall", "study_hall", "kitchen_hall") * 3:
            game.clock += 40.0
            game.doors.toggle(door_id)
            trace_door(game, door_id, 2.0)
            game.doors.toggle(door_id)
            trace_door(game, door_id, 2.0)
        return list(game.audio.played_names())
    first, again, other = played_with(5), played_with(5), played_with(6)
    assert first == again and first != other
    assert any(name.startswith("door_creak_") for name in first), "36 aberturas e fechamentos sem um ranger"


def test_creak_picks_all_four_variants_without_repeating_in_a_row():
    game, doors = stub_doors(rng=AlwaysCreak(3))
    names = []
    for door_id in ("kids_hall", "bath_hall", "den_hall", "front", "garage_door"):
        door = doors.get(door_id)
        for _ in range(60):
            door.pace = "normal"
            name = doors._roll_creak(door, "player")
            assert name is not None
            names.append(name)
    assert {f"door_creak_{n}" for n in (1, 2, 3, 4)} == set(names)
    assert all(a != b for a, b in zip(names, names[1:])), "o mesmo rangido duas vezes seguidas"


def test_creak_flavor_follows_door_kind():
    def share(door_id, variant):
        game, doors = stub_doors(rng=AlwaysCreak(3))
        door = doors.get(door_id)
        names = [doors._roll_creak(door, "player") for _ in range(900)]
        return names.count(f"door_creak_{variant}") / len(names)
    assert share("front", 1) > 2 * share("front", 3), "porta da frente pesada: rangido grave"
    assert share("garage_door", 4) > share("garage_door", 1)
    assert share("bath_hall", 2) > 2 * share("bath_hall", 1)


def test_toggle_emits_creak_sound_and_noise_through_the_usual_path():
    game = fresh_game()
    game.rng = AlwaysCreak()
    game.player.speed = 2.6                       # andando: ritmo normal, som de porta normal
    game.doors.toggle("kids_master")
    noise = [e for e in game.noise_log if e[1] == "door_creak"]
    assert noise and noise[-1][0] == "player" and noise[-1][2] == C.NOISE_PLAYER["door_creak"]
    assert game.peak_noise >= C.NOISE_PLAYER["door_creak"]
    trace_door(game, "kids_master", 0.3)
    names = played(game)
    assert any(n.startswith("door_creak_") for n in names)
    assert "door_handle" in names and "door_open" in names
    fk.run_for(game, 0.3)
    assert game.noise_levels()["player"] > 0.45, "o medidor do HUD tem de mostrar o pico do ranger"


def test_slow_opening_uses_the_soft_sound_and_no_creak_without_a_roll():
    game = fresh_game()
    game.player.crouching, game.player.speed = True, 1.2
    game.doors.toggle("kids_master")
    trace_door(game, "kids_master", 0.3)
    assert "door_open_soft" in played(game) and not any(n.startswith("door_creak_") for n in played(game))
    assert not [e for e in game.noise_log if e[1] == "door_creak"]


def test_entity_creaks_only_when_the_player_would_hear_it():
    near = fresh_game()
    near.rng = AlwaysCreak()
    teleport(near, 6.2, 8.65, 0.0, 90)
    assert near.doors.open_door("den_hall", by="entity")
    creaks = [e for e in near.noise_log if e[1] == "door_creak"]
    assert creaks and creaks[-1][0] == "entity" and creaks[-1][2] == C.NOISE_ENTITY["door_creak"]
    assert near.peak_noise == 0.0, "o ranger da entidade não conta como ruído do jogador"
    far = fresh_game()
    far.rng = AlwaysCreak()
    teleport(far, 16.5, 5.0, 0.0, 0)            # garagem, atrás de portas fechadas
    far.doors.open_door("master_hall", by="entity")
    assert not [e for e in far.noise_log if e[1] == "door_creak"]
    assert [e for e in far.noise_log if e[1] == "door_open" and e[0] == "entity"], "o ruído da abertura continua"


# --------------------------------------------------------------------------
# A entidade reage ao ranger (NoiseSystem e EntityBrain de verdade, portas de verdade)
# --------------------------------------------------------------------------
def ai_game(rng, entity_at, player_at, open_doors=()):
    game, _brain, rig, _cut = fk.game_with_fake_entity(hunts=False, world=False)
    start_playing(game)
    game.rng = rng
    brain = EntityBrain(game.world_view, game.noise, random.Random(5))
    game.entity.brain = brain
    game.entity._brain_factory = lambda: brain
    for door_id in open_doors:
        game.doors.snap(door_id, 1.0)
    teleport(game, *player_at, 0.0)
    game.entity.activate(entity_at, hunt=False)
    for _ in range(2):
        fk.step(game)
    return game, brain


def creak_heard_by(game, position):
    return [h for h in game.noise.heard_by_entity(position) if h.kind == "door_creak"]


def run_until_investigating(game, brain, seconds=1.6):
    for _ in range(int(seconds / DT)):
        fk.step(game)
        if brain.state == "investigate":
            return True
    return False


def test_entity_8m_away_in_free_air_investigates_the_creak():
    player_at = (6.0, 8.65, 0.0)              # hall, junto à porta do escritório
    entity_at = (6.8, 0.8, 0.0)               # fundo do mesmo hall: 8 m em linha livre
    game, brain = ai_game(AlwaysCreak(), entity_at, player_at)
    assert brain.state == "patrol" and math.dist(brain.position[:2], entity_at[:2]) < 0.5
    game.doors.toggle("den_hall")
    heard = creak_heard_by(game, brain.position)
    assert heard and heard[0].loudness >= 0.08, "o ranger tem de chegar a 8 m em linha livre"
    assert not [h for h in game.noise.heard_by_entity(brain.position) if h.kind == "door_open"], \
        "o estalo de abrir sozinho (0,30) não chega a 8 m: só o ranger chama"
    assert run_until_investigating(game, brain), f"estado: {brain.state}"
    assert any("door_creak" in why for _, _, _, why in brain.log), brain.log[-3:]
    goal = brain.goal
    assert goal is not None and math.dist(goal[:2], (5.0, 8.65)) < 4.5, goal


def test_same_scene_without_the_creak_does_not_attract_the_entity():
    game, brain = ai_game(NeverCreak(), (6.8, 0.8, 0.0), (6.0, 8.65, 0.0))
    game.doors.toggle("den_hall")
    assert not creak_heard_by(game, brain.position)
    assert not run_until_investigating(game, brain), "a abertura silenciosa a 8 m não chama ninguém"


def test_entity_at_the_far_end_of_the_house_does_not_react():
    # andar de cima: porta do escritório de cima rangendo; entidade no canto do quarto da menina,
    # com as portas do caminho abertas (12 m, o maior trajeto livre da casa no mesmo andar)
    game, brain = ai_game(AlwaysCreak(), (0.8, 0.8, 2.8), (7.0, 8.6, 2.8), open_doors=("kids_hall",))
    game.doors.toggle("study_hall")
    assert game.noise.path_between(game.doors.center("study_hall"), brain.position, opening="study_hall").length > 11.0
    assert not creak_heard_by(game, brain.position)
    assert not run_until_investigating(game, brain)
    # e do térreo, 22 m de caminho pela escada até a garagem
    game2, brain2 = ai_game(AlwaysCreak(), (16.5, 3.0, 0.0), (7.0, 8.6, 2.8))
    game2.doors.toggle("study_hall")
    assert not creak_heard_by(game2, brain2.position)
    assert not run_until_investigating(game2, brain2)


def test_a_closed_door_in_the_way_muffles_the_creak():
    entity_at, player_at = (3.0, 7.0, 0.0), (6.0, 1.5, 0.0)       # escritório; a sala fica entre ele e o hall
    closed, brain_closed = ai_game(AlwaysCreak(), entity_at, player_at)
    closed.doors.toggle("living_hall")
    assert not creak_heard_by(closed, brain_closed.position), "com a porta den_living fechada o ranger some"
    opened, brain_open = ai_game(AlwaysCreak(), entity_at, player_at, open_doors=("den_living",))
    opened.doors.toggle("living_hall")
    assert creak_heard_by(opened, brain_open.position), "com a porta aberta o mesmo ranger chega"


def test_the_creaking_door_does_not_muffle_its_own_creak():
    """Entidade colada do outro lado da porta que está sendo aberta: ouve, mesmo com a folha ainda fechada."""
    game, brain = ai_game(AlwaysCreak(), (2.5, 8.65, 0.0), (6.0, 8.65, 0.0))
    game.doors.toggle("den_hall")
    heard = creak_heard_by(game, brain.position)
    assert heard and heard[0].loudness > 0.3, heard


def test_creak_noise_range_matches_the_design():
    """Alcance em linha livre, num cômodo quieto: entre um passo e uma corrida, bem menos que a casa."""
    def reach(loudness):
        ns = NoiseSystem(door_openness=lambda _door: 1.0)
        event = ns.emit("player", "x", (6.5, 0.2, 1.0), loudness)
        distance = 0.5
        while ns.effective(event, (6.5, 0.2 + distance, 0.0)) >= ns.rules.hear_threshold and distance < 40:
            distance += 0.25
        return distance
    walk, creak, run = (reach(C.NOISE_PLAYER[k]) for k in ("walk", "door_creak", "run"))
    assert walk < creak < run, (walk, creak, run)
    assert 8.0 <= creak <= 10.5, f"o ranger chega a {creak:.1f} m em linha livre"


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} testes passaram")


if __name__ == "__main__":
    main()
