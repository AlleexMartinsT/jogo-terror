"""Testes do núcleo do engine (sem GUI): colisão, escada, fôlego, ruído, lanterna, portas,
interação, portão, checkpoint, história com fakes, world view da IA, luzes e hud_model.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_engine_core.py
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_engine_fakes as fk  # noqa: E402
from test_engine_fakes import (DT, InputState, aim_at, game_with_fake_entity, kinds_logged, make_game,  # noqa: E402
                               run_for, start_playing, step, teleport, walk)

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout, story  # noqa: E402
from sem_alvorada.engine import lights, state, texts  # noqa: E402
from sem_alvorada.engine.interact import Interactable  # noqa: E402

MODES = {"bvh": dict(world=True), "planta": dict(world=False)}


def each_mode():
    for name, options in MODES.items():
        game = start_playing(make_game(**options))
        assert game.collision.kind == ("bvh" if options["world"] else "layout"), game.collision.kind
        yield name, game


# --------------------------------------------------------------------------
# Colisão e escada
# --------------------------------------------------------------------------
def test_collision_stops_at_walls_and_slides():
    for mode, game in each_mode():
        teleport(game, 1.9, 5.85, 2.8, 0)
        walk(game, 4.0)
        assert game.player.y < 10.0 - 0.125 - C.PLAYER_RADIUS + 0.02, (mode, game.player.feet)
        assert game.player.y > 9.4, (mode, game.player.feet)
        teleport(game, 3.0, 6.0, 2.8, -45)
        walk(game, 3.0)
        assert game.player.x <= 5.0 - 0.075 - C.PLAYER_RADIUS + 0.02, (mode, game.player.feet)
        assert game.player.y > 6.6, f"não deslizou ao longo da parede ({mode}): {game.player.feet}"


def test_collision_blocks_furniture_proxy():
    game = start_playing(make_game(world=True))
    teleport(game, 2.1, 1.5, 0.0, 0)
    walk(game, 3.0)
    limit = 3.9 - 1.0 - C.PLAYER_RADIUS
    assert abs(game.player.y - limit) < 0.03, game.player.feet
    teleport(game, 2.1 + 0.9, 1.5, 0.0, 0)      # ao lado do sofá: passa livre
    walk(game, 1.0)
    assert game.player.y > 2.4


def test_no_tunneling_at_low_frame_rate():
    for mode, game in each_mode():
        teleport(game, 6.5, 2.0, 0.0, 90)        # de frente para a parede oeste do hall
        inp = InputState(move_y=1.0, run=True)
        for _ in range(60):
            game.tick(0.1, inp)                   # 10 fps, correndo
        assert game.player.x > 5.0, (mode, game.player.feet)


def test_stairs_up_and_down_match_layout():
    for mode, game in each_mode():
        teleport(game, 5.6, 2.4, 0.0, 0)
        for _ in range(400):
            walk(game, DT, yaw_deg=0)
            player = game.player
            expected = layout.stairs_height(player.x, player.y)
            if expected is not None:
                assert abs(player.z - expected) < 1e-3, (mode, player.feet, expected)
            if player.y > 7.8:
                break
        assert abs(game.player.z - layout.LEVEL_Z[1]) < 1e-3, (mode, game.player.feet)
        assert game.player.room_id == "hall_u"
        for _ in range(400):
            walk(game, DT, yaw_deg=180)
            if game.player.y < 2.6:
                break
        assert abs(game.player.z) < 1e-3, (mode, game.player.feet)
        assert game.player.room_id == "hall_g"


def test_no_falling_into_stairwell():
    for mode, game in each_mode():
        teleport(game, 7.0, 5.0, 2.8, 90)         # andar de cima, apontando para o vão da escada
        walk(game, 2.0)
        assert game.player.x >= layout.STAIRS.x1 + 0.2, (mode, game.player.feet)
        assert abs(game.player.z - 2.8) < 1e-3


def test_crouch_lowers_eyes_and_respects_headroom():
    game = start_playing(make_game(world=True))
    teleport(game, 6.5, 2.0, 0.0, 0)
    run_for(game, 1.0, InputState(crouch=True))
    assert game.player.crouching and abs(game.player.eye - C.PLAYER_EYE_CROUCH) < 0.02
    fk.add_box(game.scene, "LowBeam", 5.0, 0.0, 1.5, 8.0, 10.0, 1.6)
    game.collision = type(game.collision).from_scene(game.scene)
    game.player.collision = game.collision
    run_for(game, 1.0, InputState(crouch=False))
    assert game.player.crouching, "levantou dentro de uma viga baixa"
    teleport(game, 1.0, 2.0, 0.0, 0)
    run_for(game, 1.0, InputState(crouch=False))
    assert not game.player.crouching and abs(game.player.eye - C.PLAYER_EYE_STAND) < 0.02


# --------------------------------------------------------------------------
# Fôlego e ruído
# --------------------------------------------------------------------------
def run_with_resets(game, seconds):
    """Corre sem parar mesmo sendo a casa pequena: devolve o jogador ao início do hall a cada segundo."""
    inp = InputState(move_y=1.0, run=True)
    for second in range(int(seconds)):
        teleport(game, 6.5, 1.0, 0.0, 0)
        run_for(game, 1.0, inp)


def test_stamina_drains_exhausts_and_recovers():
    game = start_playing(make_game(world=True))
    run_with_resets(game, 3)
    expected = C.STAMINA_MAX - C.STAMINA_DRAIN * 3.0
    assert abs(game.player.stamina - expected) < 0.06, game.player.stamina
    run_with_resets(game, 2)
    assert game.player.exhausted and game.player.stamina < 0.15
    teleport(game, 6.5, 1.0, 0.0, 0)
    run_for(game, 0.4, InputState(move_y=1.0, run=True))
    assert game.player.speed < C.SPEED_WALK * 1.1, "correu sem fôlego"
    assert kinds_logged(game, "breath_heavy"), "sem ruído de respiração ofegante"
    run_for(game, 1.5, InputState())
    assert not game.player.exhausted and game.player.stamina >= C.REACH_MIN_STAMINA_TO_RUN
    run_for(game, 0.6, InputState(move_y=1.0, run=True))
    assert game.player.running


def steps_of(game, kind):
    return [entry[2] for entry in kinds_logged(game, kind)]


def test_footstep_noise_by_action_and_surface():
    cases = [("carpet", (2.5, 3.0, 0.0, 90), "walk"), ("wood", (2.5, 8.0, 0.0, 90), "walk"),
             ("tile", (10.0, 7.5, 0.0, 0), "walk")]
    for surface, (x, y, z, yaw), kind in cases:
        game = start_playing(make_game(world=True))
        teleport(game, x, y, z, yaw)
        walk(game, 2.0)
        heard = steps_of(game, kind)
        assert heard, surface
        assert all(abs(v - round(C.NOISE_PLAYER[kind] * C.SURFACE_NOISE_MULT[surface], 3)) < 1e-3 for v in heard), (surface, heard)
    game = start_playing(make_game(world=True))
    teleport(game, 6.5, 1.0, 0.0, 0)
    walk(game, 1.5, run=True)
    assert steps_of(game, "run") and abs(steps_of(game, "run")[0] - C.NOISE_PLAYER["run"]) < 1e-3
    game = start_playing(make_game(world=True))
    teleport(game, 6.5, 1.0, 0.0, 0)
    walk(game, 2.5, crouch=True)
    assert steps_of(game, "crouch_walk") and abs(steps_of(game, "crouch_walk")[0] - 0.08) < 1e-3
    assert not steps_of(game, "walk")
    game = start_playing(make_game(world=True))
    teleport(game, 5.6, 2.6, 0.0, 0)
    walk(game, 2.0)
    assert any(abs(v - round(0.30 * 1.35, 3)) < 1e-3 for v in steps_of(game, "walk")), steps_of(game, "walk")
    assert game.noise.level_at(game.player.feet, "player") > 0.0


def test_standing_still_makes_no_noise_and_running_is_louder():
    game = start_playing(make_game(world=True))
    run_for(game, 3.0)
    assert not kinds_logged(game, "walk") and not kinds_logged(game, "run")
    assert C.NOISE_PLAYER["run"] > C.NOISE_PLAYER["walk"] > C.NOISE_PLAYER["crouch_walk"] > C.NOISE_PLAYER["idle"]


def test_noise_kinds_used_by_engine_exist_in_conventions():
    tables = {**C.NOISE_PLAYER, **C.NOISE_ENTITY, **C.NOISE_AMBIENT_EVENTS}
    package = os.path.join(fk.ROOT, "sem_alvorada", "engine")
    found = set()
    for name in os.listdir(package):
        if name.endswith(".py"):
            with open(os.path.join(package, name), encoding="utf-8") as source:
                found |= set(re.findall(r'make_noise\(\s*"([a-z_]+)"', source.read()))
                source.seek(0)
                found |= set(re.findall(r'NOISE_(?:PLAYER|ENTITY)\["([a-z_]+)"\]', source.read()))
    assert found, "nenhum tipo de ruído encontrado no código"
    unknown = found - set(tables)
    assert not unknown, f"tipos de ruído sem entrada em conventions: {unknown}"


# --------------------------------------------------------------------------
# Lanterna
# --------------------------------------------------------------------------
def tick_seconds(game, seconds, inp=None):
    inp = inp or InputState()
    for _ in range(int(seconds / 0.1)):
        game.tick(0.1, inp)
        inp.clear_edges()


def test_flashlight_toggle_drain_flicker_and_death():
    game = start_playing(make_game(world=True))
    step(game, InputState(flashlight=True))
    assert not game.state.flashlight_on, "ligou sem ter a lanterna"
    game.state.has_flashlight = True
    step(game, InputState(flashlight=True))
    assert game.state.flashlight_on
    assert kinds_logged(game, "flash_click")[-1][2] == C.NOISE_PLAYER["flash_click"]
    beam = game.scene.objects[C.OBJ_FLASHLIGHT].data
    assert abs(beam.energy - C.FLASH_ENERGY) < 1.0 and abs(math.degrees(beam.spot_size) - C.FLASH_SPOT_DEG) < 0.1
    tick_seconds(game, 100)
    assert abs(game.state.battery - (1.0 - 100 * C.BATTERY_DRAIN_PER_SEC)) < 0.02, game.state.battery
    step(game, InputState(flashlight=True))
    before = game.state.battery
    tick_seconds(game, 10)
    assert game.state.battery == before, "drenou desligada"
    step(game, InputState(flashlight=True))
    game.state.battery = 0.5
    samples = []
    for _ in range(30):
        game.tick(0.1, InputState())
        samples.append(game.flashlight.intensity)
    assert min(samples) == max(samples) == 1.0, "piscou com bateria boa"
    game.state.battery = 0.1
    samples = []
    for _ in range(120):
        game.tick(0.1, InputState())
        samples.append(game.flashlight.intensity)
        game.state.battery = 0.1
    assert min(samples) < 0.4 and max(samples) > 0.35, (min(samples), max(samples))
    assert max(samples) < 1.0, "sem perda de brilho com bateria baixa"
    game.state.battery = 0.004
    tick_seconds(game, 2)
    assert not game.state.flashlight_on and game.state.battery == 0.0
    assert game.message_text == story.FLASHLIGHT_DEAD
    assert beam.energy == 0.0


def test_flashlight_battery_swap():
    game = start_playing(make_game(world=True))
    game.state.has_flashlight = True
    step(game, InputState(reload=True))
    assert game.message_text == story.NO_SPARE
    game.state.spare_batteries = 1
    game.state.battery = 0.95
    step(game, InputState(reload=True))
    assert game.message_text == texts.MSG_BATTERY_GOOD and game.state.spare_batteries == 1
    game.state.battery = 0.2
    step(game, InputState(reload=True))
    assert kinds_logged(game, "battery_swap")[-1][2] == C.NOISE_PLAYER["battery_swap"]
    assert game.flashlight.swap_left > 0
    tick_seconds(game, 1.5)
    assert game.state.battery > 0.99 and game.state.spare_batteries == 0
    assert game.state.flashlight_on and game.message_text == story.BATTERY_SWAPPED
    game.state.battery = 0.0
    game.state.flashlight_on = False
    game.state.spare_batteries = 1
    step(game, InputState(reload=True))
    tick_seconds(game, 1.5)
    assert game.state.flashlight_on and game.state.battery > 0.99, "lanterna morta não voltou a acender"


def test_flashlight_lags_behind_camera_and_viewmodel_follows_pickup():
    game = start_playing(make_game(world=True))
    game.state.has_flashlight = True
    step(game)
    viewmodel = game.scene.objects[C.OBJ_VIEW_FLASH]
    assert not viewmodel.hide_viewport
    game.state.has_flashlight = False
    step(game)
    assert viewmodel.hide_viewport
    game.state.has_flashlight = True
    step(game, InputState(look_dx=math.radians(20)))
    offset_yaw = game.flashlight.offset[1]
    assert abs(offset_yaw) > math.radians(1), "a luz não ficou para trás ao girar"
    run_for(game, 1.0)
    assert abs(game.flashlight.offset[1]) < abs(offset_yaw) * 0.2, "a luz não alcançou a câmera"


# --------------------------------------------------------------------------
# Portas
# --------------------------------------------------------------------------
def settle(game, seconds=1.5):
    run_for(game, seconds)


def test_door_blocks_then_opens_by_interaction():
    game = start_playing(make_game(world=True))
    teleport(game, 6.2, 1.45, 0.0, 90)
    walk(game, 2.0)
    assert game.player.x > 5.3, f"atravessou a porta fechada: {game.player.feet}"
    aim_at(game, game.doors.center("living_hall"))
    step(game)
    assert game.interact.current is not None and game.interact.current.ref == "living_hall"
    assert game.interact.prompt_for(game.interact.current) == story.PROMPT_OPEN
    step(game, InputState(interact=True))
    assert kinds_logged(game, "door_open")[-1][2] == C.NOISE_PLAYER["door_open"]
    settle(game)
    assert game.doors.openness("living_hall") > 0.99
    teleport(game, 6.2, 1.45, 0.0, 90)
    walk(game, 2.0)
    assert game.player.x < 4.5, f"não passou pela porta aberta: {game.player.feet}"


def test_door_close_slam_and_locks():
    game = start_playing(make_game(world=True))
    game.doors.snap("den_hall", 1.0)
    assert game.doors.toggle("den_hall") == "closed"
    assert kinds_logged(game, "door_close")[-1][2] == C.NOISE_PLAYER["door_close"]
    settle(game)
    assert game.doors.openness("den_hall") == 0.0
    game.doors.snap("den_hall", 1.0)
    assert game.doors.toggle("den_hall", hurried=True) == "slammed"
    assert kinds_logged(game, "door_slam")[-1][2] == C.NOISE_PLAYER["door_slam"]
    run_for(game, 0.4)
    assert game.doors.openness("den_hall") == 0.0, "a batida devia fechar a porta em menos de 0,4 s"
    assert game.doors.toggle("front") == "locked" and game.doors.openness("front") == 0.0
    assert game.doors.is_locked("garage_door") and game.doors.is_locked("back")
    assert not game.doors.is_locked("living_hall")
    assert not game.doors.open_door("garage_door", "entity")
    assert game.doors.openness("dining_hall") == 1.0, "arcos contam como abertos"


def test_door_drives_pivot_object_and_does_not_close_on_player():
    scene = fk.fresh_scene()
    fk.build_minimal_world(scene)
    plan = layout.door_transform(layout.OPENINGS["kids_hall"])
    pivot = fk.bpy.data.objects.new("Door_kids_hall", None)
    scene.collection.objects.link(pivot)
    pivot[C.P_DOOR_CLOSED], pivot[C.P_DOOR_OPEN], pivot[C.P_LOCK] = plan["closed_yaw"], plan["open_yaw"], ""
    pivot.location = plan["hinge"]
    game = start_playing(fk.Game(scene, audio=False, entity=False, cutscenes=False))
    game.doors.snap("kids_hall", 1.0)
    assert abs(pivot.rotation_euler.z - plan["open_yaw"]) < 1e-4
    game.doors.set_openness("kids_hall", 0.0)
    run_for(game, 2.0)
    assert abs(pivot.rotation_euler.z - plan["closed_yaw"]) < 1e-4
    trapped = start_playing(make_game(world=True))
    door = layout.OPENINGS["den_hall"]
    trapped.doors.snap("den_hall", 1.0)
    teleport(trapped, door.pos, (door.a + door.b) / 2, 0.0, 0)
    trapped.doors.set_openness("den_hall", 0.0)
    run_for(trapped, 2.0, InputState())
    assert trapped.doors.openness("den_hall") > 0.0, "fechou a porta em cima do jogador"


def test_entity_opens_doors_with_noise():
    game = start_playing(make_game(world=True))
    assert game.doors.open_door("kitchen_hall", by="entity")
    assert kinds_logged(game, "door_open", "entity")[-1][2] == C.NOISE_ENTITY["door_open"]
    settle(game)
    assert game.world_view.door_openness("kitchen_hall") > 0.99


# --------------------------------------------------------------------------
# Interação e inventário
# --------------------------------------------------------------------------
def test_pickup_item_inventory_and_prompt():
    game = start_playing(make_game(world=True))
    key = layout.ITEM_SPOTS["KEY"]
    target = (key[1], key[2], key[3] + 0.05)
    teleport(game, key[1], key[2] - 1.2, 0.0, 0)
    aim_at(game, target)
    step(game)
    assert game.interact.current is not None and game.interact.current.ref == "KEY"
    assert game.hud_model()["prompt"] == story.ITEM_PROMPTS["KEY"]
    step(game, InputState(interact=True))
    assert game.state.has_key and "KEY" in game.state.collected
    assert game.message_text == story.PICKED["KEY"]
    assert kinds_logged(game, "pickup")[-1][2] == C.NOISE_PLAYER["pickup"]
    step(game)
    assert game.interact.current is None or game.interact.current.ref != "KEY"
    teleport(game, key[1] + 1.9, key[2] - 1.5, 0.0, 0)
    aim_at(game, target)
    step(game)
    assert game.interact.current is None, "selecionou fora do alcance"


def test_interaction_needs_line_of_sight_and_center_of_view():
    game = start_playing(make_game(world=True))
    probe = Interactable("note", "NOTE_PROBE", "NOTE", None, (2.0, 5.4, 1.2))     # sala, junto à porta den_living
    game.interact.targets.append(probe)
    teleport(game, 2.0, 6.6, 0.0, 0)                                              # escritório
    aim_at(game, probe.position)
    step(game)
    assert game.interact.current is not probe, "selecionou através de uma porta fechada"
    game.doors.snap("den_living", 1.0)
    step(game)
    assert game.interact.current is probe
    game.player.yaw += math.radians(40)                 # olhando para o lado
    step(game)
    assert game.interact.current is not probe
    aim_at(game, (0.5, 5.4, 1.2))                       # olhando para a parede ao lado do alvo
    step(game)
    assert game.interact.current is not probe


def test_item_inside_furniture_proxy_stays_interactable_but_walls_still_block():
    """Uma pilha na gaveta fica dentro do proxy do móvel: o móvel que envolve o alvo não pode bloqueá-lo."""
    game = start_playing(make_game(world=True))
    shelf = fk.add_box(game.scene, "COL_shelf", 2.0, 3.0, 0.0, 3.0, 3.6, 0.9, hidden=True)
    game.collision = type(game.collision).from_scene(game.scene)
    game.player.collision = game.collision
    inside = Interactable("item", "BATTERY_IN_DRAWER", "BATTERY", None, (2.5, 3.3, 0.5))
    game.interact.targets.append(inside)
    teleport(game, 2.5, 2.0, 0.0, 0)
    aim_at(game, inside.position)
    step(game)
    assert game.interact.current is inside, "item dentro do proxy deveria ser selecionável"
    assert not game.collision.line_clear(game.player.eye_pos, inside.position), "sem a exceção o proxy bloquearia"
    fk.add_box(game.scene, "COL_screen", 2.0, 2.4, 0.0, 3.0, 2.5, 2.2, hidden=True)      # um biombo no meio
    game.collision = type(game.collision).from_scene(game.scene)
    game.player.collision = game.collision
    step(game)
    assert game.interact.current is not inside, "outro móvel entre o jogador e o item deve bloquear"


def test_big_wall_mesh_never_counts_as_enclosing_the_target():
    """Uma única malha de parede cobre a casa toda: não pode virar exceção de visada."""
    game = start_playing(make_game(world=True))
    fk.add_box(game.scene, "AllWalls", 0.0, 0.0, 0.0, 12.0, 10.0, 5.0)        # caixa que envolve tudo, sem prefixo COL_
    wall = fk.add_box(game.scene, "Partition", 1.0, 5.0, 0.0, 4.0, 5.2, 2.5)
    game.collision = type(game.collision).from_scene(game.scene)
    assert not game.collision.line_clear((2.0, 3.0, 1.6), (2.0, 7.0, 1.0), through_target_solids=True)
    rotated = fk.add_box(game.scene, "COL_turned", -0.5, -0.3, 0.0, 0.5, 0.3, 0.8, hidden=True)
    rotated.rotation_euler.z = math.radians(45)
    rotated.location = (8.0, 8.0, 0.0)
    game.collision = type(game.collision).from_scene(game.scene)
    assert game.collision._enclosing_objects((8.2, 8.2, 0.3)), "proxy girado: o ponto dentro da caixa deve contar"
    assert not game.collision._enclosing_objects((8.5, 7.5, 0.3)), "canto do AABB do proxy girado está fora da caixa"


def test_door_sight_line_opens_with_door():
    game = start_playing(make_game(world=True))
    a, b = (2.0, 6.6, 1.5), (2.0, 5.4, 1.5)
    assert not game.world_view.line_of_sight(a, b), "porta fechada devia bloquear a visada"
    game.doors.snap("den_living", 1.0)
    assert game.world_view.line_of_sight(a, b)
    assert not game.world_view.line_of_sight((0.5, 6.6, 1.5), (0.5, 5.4, 1.5)), "parede devia bloquear"
    assert not game.world_view.line_of_sight((6.5, 5.0, 1.5), (6.5, 5.0, 4.3)), "laje devia bloquear"
    assert game.world_view.line_of_sight((6.5, 1.0, 1.5), (6.5, 9.0, 1.5))
    assert game.world_view.room_at(6.5, 5.0, 0.0) == "hall_g" and game.world_view.room_at(-5.0, 5.0, 0.0) is None


def test_notes_pause_the_world_and_are_read_once():
    game = start_playing(make_game(world=True))
    note = layout.ITEM_SPOTS["NOTE_2"]
    teleport(game, note[1], note[2] - 1.3, 2.8, 0)
    aim_at(game, (note[1], note[2], note[3] + 0.05))
    step(game)
    step(game, InputState(interact=True))
    assert game.phase == "reading" and game.reader_note == "NOTE_2"
    model = game.hud_model()
    assert model["note"]["title"] == story.NOTES["NOTE_2"][0] and model["note"]["body"]
    clock = game.clock
    game.state.flashlight_on, game.state.has_flashlight = True, True
    battery = game.state.battery
    run_for(game, 3.0, InputState(move_y=1.0))
    assert game.clock == clock and game.state.battery == battery and game.player.y < note[2] - 1.2, "o mundo não pausou"
    step(game, InputState(interact=True))
    assert game.phase == "play" and "NOTE_2" in game.state.notes_read
    assert game.checkpoint is not None


def test_item_objects_hide_on_pickup_and_reappear_on_restore():
    game = start_playing(make_game(world=True, items=True))
    assert not game.interact.missing_from_scene or "Item_KEY" not in game.interact.missing_from_scene
    key_obj = game.scene.objects["Item_KEY"]
    key = layout.ITEM_SPOTS["KEY"]
    teleport(game, key[1], key[2] - 1.2, 0.0, 0)
    aim_at(game, tuple(key_obj.location))
    step(game)
    step(game, InputState(interact=True))
    assert key_obj.hide_viewport and key_obj.hide_render
    saved = game.checkpoint["state"]
    game.state.restore(state.GameState().snapshot())
    game.interact.sync_scene()
    assert not key_obj.hide_viewport
    game.state.restore(saved)
    game.interact.sync_scene()
    assert key_obj.hide_viewport


# --------------------------------------------------------------------------
# Portão da garagem, checkpoint, história
# --------------------------------------------------------------------------
def test_gate_requires_key_map_and_three_found_batteries():
    game, brain, rig, cutscenes = game_with_fake_entity(hunts=False)
    start_playing(game)
    st = game.state
    st.has_key = st.has_map = True
    st.batteries_found = 2
    assert not st.collect_complete() and st.missing_labels() == [story.LABEL_BATTERIES]
    teleport(game, 13.6, 5.85, 0.0, 90)
    aim_at(game, game.doors.center("garage_door"))
    step(game)
    assert game.interact.current.ref == "garage_door"
    assert game.interact.prompt_for(game.interact.current) == story.PROMPT_OPEN
    step(game, InputState(interact=True))
    assert game.doors.is_locked("garage_door") and game.phase == "play"
    assert story.LOCKED_MSGS["garage"] in game.message_text and story.LABEL_BATTERIES in game.message_text
    st.batteries_found, st.spare_batteries = 3, 0            # usar pilhas não descontaria do que foi encontrado
    assert st.collect_complete()
    step(game)
    assert game.interact.prompt_for(game.interact.current) == story.PROMPT_UNLOCK_GARAGE
    step(game, InputState(interact=True))
    assert not game.doors.is_locked("garage_door") and "garage" in st.unlocked
    assert game.phase == "cutscene" and cutscenes.played[-1] == "garage_unlock"
    run_for(game, 2.0)
    assert game.phase == "play" and game.doors.openness("garage_door") > 0.99
    assert st.objective == story.OBJ_CAR and brain.aggression == 2


def test_checkpoint_snapshot_and_restore():
    game = start_playing(make_game(world=True))
    st = game.state
    st.has_flashlight = st.has_key = True
    st.batteries_found = st.spare_batteries = 2
    st.collected |= {"FLASHLIGHT", "KEY", "BATTERY_1", "BATTERY_2"}
    st.notes_read.add("NOTE_1")
    st.battery = 0.6
    teleport(game, 3.0, 8.0, 0.0, 30)
    game.save_checkpoint()
    snapshot = st.snapshot()
    st.has_key = False
    st.spare_batteries = 0
    st.collected.clear()
    st.battery = 0.1
    st.flags.add(state.FLAG_BLACKOUT)
    teleport(game, 9.0, 9.0, 2.8, 0)
    game.restart_from_checkpoint()
    assert st.snapshot() == snapshot
    assert game.phase == "play" and abs(game.player.x - 3.0) < 1e-6 and abs(game.player.yaw - math.radians(30)) < 1e-6
    assert game.player.stamina == C.STAMINA_MAX and game.lights.power_on


def test_story_flow_intro_blackout_collect_unlock_ending():
    game, brain, rig, cutscenes = game_with_fake_entity(hunts=False)
    step(game)
    assert game.phase == "title" and game.hud_model()["title"]["name"] == story.TITLE
    step(game, InputState(confirm=True))
    assert game.phase == "cutscene" and cutscenes.played == ["intro"]
    assert game.hud_model()["overlay"]["letterbox"] == 1.0
    run_for(game, 1.5)
    assert game.phase == "play" and game.state.objective == story.OBJ_TAKE_FLASHLIGHT
    assert game.checkpoint is not None
    hall = layout.ROOMS["hall_u"].rect.center
    teleport(game, hall[0], hall[1], 2.8, 0)
    run_for(game, 0.3)
    assert game.phase == "play" and "blackout" not in cutscenes.played, "blackout sem lanterna"
    assert game.message_text == texts.MSG_NEED_FLASHLIGHT
    game.state.has_flashlight = True
    assert game.state.objective == story.OBJ_LEAVE_ROOM
    run_for(game, 0.3)
    assert game.phase == "cutscene" and cutscenes.played[-1] == "blackout"
    run_for(game, 1.5)
    assert game.phase == "play" and state.FLAG_BLACKOUT in game.state.flags
    assert state.FLAG_BLACKOUT in game.checkpoint["state"]["flags"]
    assert abs(game.checkpoint["pos"][0] - layout.PLAYER_START[0]) < 0.01, "o checkpoint do apagão deve manter a posição segura"
    assert not game.lights.power_on and game.entity.active and brain.activated_at is not None and rig.visible
    assert game.state.objective == story.OBJ_COLLECT and brain.aggression == 0
    game.state.has_key = game.state.has_map = True
    game.state.batteries_found = 3
    game.director.on_item_taken(None)
    assert game.state.objective == story.OBJ_GARAGE and brain.aggression == 1
    assert game.message_text == story.COLLECT_DONE
    game.director.unlock_garage()
    run_for(game, 1.5)
    assert game.state.objective == story.OBJ_CAR
    car = layout.ANCHORS["car_interact"]
    teleport(game, car.x + 1.0, car.y, 0.0, 90)
    aim_at(game, (car.x, car.y, car.z + 1.0))
    step(game)
    assert game.interact.current.kind == "car"
    step(game, InputState(interact=True))
    assert game.phase == "cutscene" and cutscenes.played[-1] == "ending"
    run_for(game, 1.5)
    assert game.phase == "credits" and game.hud_model()["ending"]["card"] == story.ENDING_CARD
    step(game, InputState(confirm=True))
    assert game.phase == "title"


def test_car_refuses_until_garage_unlocked():
    game = start_playing(make_game(world=True))
    car = layout.ANCHORS["car_interact"]
    teleport(game, car.x + 1.0, car.y, 0.0, 90)
    aim_at(game, (car.x, car.y, car.z + 1.0))
    step(game)
    step(game, InputState(interact=True))
    assert game.phase == "play" and game.message_text == texts.MSG_CAR_LOCKED


def farness(a, b):
    """Distância usada no respawn: andar diferente conta como mais longe."""
    penalty = 6.0 if layout.level_of_z(a[2]) != layout.level_of_z(b[2]) else 0.0
    return math.hypot(a[0] - b[0], a[1] - b[1]) + penalty


def test_death_shows_card_and_retries_from_checkpoint_far_from_entity():
    game, brain, rig, cutscenes = game_with_fake_entity(hunts=True)
    start_playing(game)
    game.state.has_flashlight = True
    game.state.flags.add(state.FLAG_BLACKOUT)
    teleport(game, 2.5, 8.0, 0.0, 0)
    game.save_checkpoint()
    game.entity.activate((4.5, 8.0, 0.0))
    run_for(game, 3.0)
    assert cutscenes.played[-1] == "death" or game.phase == "dead"
    run_for(game, 1.5)
    assert game.phase == "dead" and game.state.deaths == 1
    assert game.hud_model()["death"]["card"] == story.DEATH_CARD
    step(game, InputState(confirm=True))
    assert game.phase == "play" and abs(game.player.x - 2.5) < 1e-6
    assert game.entity.active and farness(brain.activated_at, (2.5, 8.0, 0.0)) >= 8.0, brain.activated_at
    assert brain.hunt is False, "no retry a entidade não pode nascer sabendo onde o jogador está"


def test_pause_and_quit_flow():
    game = start_playing(make_game(world=True))
    step(game, InputState(pause=True))
    assert game.phase == "paused"
    clock = game.clock
    run_for(game, 1.0, InputState(move_y=1.0))
    assert game.clock == clock
    step(game, InputState(confirm=True))
    assert game.phase == "play"
    step(game, InputState(pause=True))
    step(game, InputState(pause=True, cancel=True))
    assert game.quit_requested


# --------------------------------------------------------------------------
# Luzes, câmera, hud_model
# --------------------------------------------------------------------------
def test_lights_only_near_player_and_blackout():
    game = start_playing(make_game(world=True, lights=True))
    game.tick(DT, InputState())
    visible_rooms = {light.room for light in game.lights.lights if light.visible}
    expected = {"master"} | {other for other, _ in layout.neighbors("master")}
    assert visible_rooms == expected, visible_rooms
    assert game.lights.lit_count() < len(game.lights.lights)
    energies = [light.obj.data.energy for light in game.lights.lights if light.visible]
    assert all(0.0 <= e <= 60.0 for e in energies) and max(energies) > 30.0
    game.lights.set_power(False, 0.0)
    run_for(game, 0.5)
    assert all(light.obj.data.energy == 0.0 for light in game.lights.lights if light.kind == "ceiling")
    teleport(game, 10.0, 7.5, 0.0, 0)
    run_for(game, 0.2)
    assert {light.room for light in game.lights.lights if light.visible} == {"kitchen"} | {
        other for other, _ in layout.neighbors("kitchen")}
    for clock in (0.0, 0.37, 1.9, 5.5):
        assert 0.0 <= lights.flicker_gain(clock, 0.6, 3.3) <= 1.0
    assert lights.flicker_gain(1.0, 0.0, 1.0) == 1.0


def test_player_camera_follows_player_with_bob():
    game = start_playing(make_game(world=True))
    cam = game.scene.objects[C.OBJ_PLAYER_CAM]
    assert abs(cam.data.angle - math.radians(72)) < 1e-4 and abs(cam.data.clip_start - 0.05) < 1e-6
    step(game)
    assert abs(cam.location.z - (2.8 + C.PLAYER_EYE_STAND)) < 0.05
    assert abs(cam.rotation_euler.z - game.player.yaw) < 1e-6
    teleport(game, 6.5, 1.0, 0.0, 0)
    heights = []
    inp = InputState(move_y=1.0)
    for _ in range(45):
        game.tick(DT, inp)
        heights.append(cam.location.z)
    assert max(heights) - min(heights) > 0.02, "sem head bob"
    assert max(heights) - min(heights) < 0.12, "head bob exagerado"
    step(game, InputState(look_dy=math.radians(120)))
    assert game.player.pitch <= math.radians(85) + 1e-6


def test_hud_model_is_complete_in_every_phase():
    game, brain, rig, cutscenes = game_with_fake_entity(hunts=False, debug=True)
    required = {"phase", "battery", "collect", "objective", "prompt", "message", "message_alpha", "noise", "stamina",
                "exhausted", "crouching", "overlay", "note", "title", "death", "ending", "debug", "error"}
    seen = set()
    for phase in ("title", "cutscene", "play", "reading", "paused", "dead", "credits"):
        game.phase = phase
        game.reader_note = "NOTE_1" if phase == "reading" else None
        model = game.hud_model()
        assert required <= set(model), (phase, required - set(model))
        seen.add(model["phase"])
    assert len(seen) == 7
    model = game.hud_model()
    assert {"levels", "peaks", "hear_threshold", "labels"} <= set(model["noise"])
    assert set(model["noise"]["levels"]) == {"player", "ambient", "entity"}
    assert 0.0 < model["noise"]["hear_threshold"] < 0.5
    assert [row["label"] for row in model["collect"]] == [story.LABEL_KEY, story.LABEL_MAP, story.LABEL_BATTERIES]
    assert model["collect"][2]["need"] == 3
    assert model["battery"]["level"] == 1.0 and model["debug"]
    game.phase = "play"
    game.say("teste", 2.0)
    run_for(game, 0.5)
    assert game.hud_model()["message"] == "teste" and game.hud_model()["message_alpha"] > 0.5
    walk(game, 1.5, yaw_deg=90)
    walk(game, 1.0, run=True, yaw_deg=90)
    assert game.hud_model()["noise"]["levels"]["player"] > 0.0
    assert game.hud_model()["noise"]["peaks"]["player"] >= game.hud_model()["noise"]["levels"]["player"]


def test_cutscene_host_contract():
    game, brain, rig, cutscenes = game_with_fake_entity(hunts=False)
    host = game.host
    assert host.scene is game.scene and host.audio is game.audio and host.entity is rig
    assert host.doors.set_openness and host.doors.snap
    host.place_player(3.0, 8.0, 0.0, math.radians(45))
    x, y, z, yaw, eye_z = host.player_state()
    assert (x, y, z) == (3.0, 8.0, 0.0) and abs(yaw - math.radians(45)) < 1e-9 and abs(eye_z - C.PLAYER_EYE_STAND) < 0.05
    assert host.get_object(C.OBJ_PLAYER_CAM) is game.player_cam and host.get_object("nao_existe") is None
    fake_camera = fk.bpy.data.objects.new(C.OBJ_CUT_CAM, fk.bpy.data.cameras.new("cam"))
    game.scene.collection.objects.link(fake_camera)
    host.set_camera(fake_camera)
    assert game.scene.camera is fake_camera
    host.set_camera(None)
    assert game.scene.camera is game.player_cam
    game.state.has_flashlight = True
    host.set_flashlight(True)
    assert game.state.flashlight_on
    host.flash_light(0.5)
    host.set_power(False, 0.5)
    assert not game.lights.power_on and game.lights.power_flicker == 0.5
    host.noise_silence(1.0)
    game.make_noise("walk", (1, 1, 0), 0.3)
    assert not kinds_logged(game, "walk"), "ruído durante o silêncio pedido pela cutscene"
    host.entity_brain_activate()
    assert game.entity.active
    host.doors.snap("kids_hall", 1.0)
    assert game.doors.openness("kids_hall") == 1.0


def test_missing_modules_degrade_gracefully():
    game = start_playing(make_game(world=False, entity=False, cutscenes=False))
    assert not game.entity.enabled and game.cutscenes is None
    game.state.has_flashlight = True
    teleport(game, 6.5, 5.0, 2.8, 0)
    run_for(game, 0.3)
    assert state.FLAG_BLACKOUT in game.state.flags and not game.lights.power_on, "blackout sem cutscenes"
    assert game.phase == "play"
    assert game.interact.missing_from_scene, "sem props: os alvos deveriam ser virtuais"
    game.debug_cheat("give_all")
    assert game.state.collect_complete()


def main():
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok      {name}", flush=True)
        except Exception as error:      # noqa: BLE001 - queremos ver todas as falhas de uma vez
            failures += 1
            import traceback
            print(f"FALHOU  {name}: {error!r}", flush=True)
            traceback.print_exc()
    print(f"{len(tests) - failures}/{len(tests)} testes do engine passaram")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
