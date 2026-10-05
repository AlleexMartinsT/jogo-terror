"""Testes das mãos: executor de clipes, pegar cada item, lanterna (primeira vez, F, R), leitura, roda e reset.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_hands.py

O corpo é um `BodyFalso` que só registra o que a mão pediu (alvo, dedos, soltar), então nada aqui depende da
malha do corpo. Os deslocamentos por quadro são medidos nos alvos que a mão recebeu.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_engine_fakes as fk  # noqa: E402
from test_engine_fakes import InputState, aim_at, kinds_logged, make_game, start_playing, teleport  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.engine import handclips, handtrack  # noqa: E402
from sem_alvorada.engine.flashlight import burst_curve  # noqa: E402

FRAME = 1.0 / 60.0
DT_IDLE = 1.0 / 30.0
MAX_STEP = 0.07             # m por quadro a 60 Hz (4,2 m/s): acima disso a mão "teletransportou"
MAX_TURN = 14.0             # graus por quadro a 60 Hz
STAND_OFFSETS = ((0.0, -1.1), (1.1, 0.0), (0.0, 1.1), (-1.1, 0.0), (0.8, -0.8), (-0.8, -0.8))


# --------------------------------------------------------------------------
# Corpo falso e ajudantes
# --------------------------------------------------------------------------
class FakeArm:
    ready = True

    def __init__(self):
        self.targets = []
        self.fingers = []
        self.releases = 0

    def set_target(self, position, rotation_deg=(0.0, 0.0, 0.0), weight=1.0):
        self.targets.append((tuple(position), tuple(rotation_deg), weight))

    def set_fingers(self, curls, spread=0.0, blend=1.0):
        assert len(curls) == 5 and all(0.0 <= c <= 1.0 for c in curls), curls
        self.fingers.append(tuple(curls))

    def release(self, blend=1.0):
        self.releases += 1

    def hold(self, obj, offset=None):
        pass

    def drop(self, obj=None):
        pass

    def hand_world_position(self):
        return None


class FakeBody:
    visible = False

    def __init__(self):
        self.arms = {"L": FakeArm(), "R": FakeArm()}

    def set_visible(self, visible):
        self.visible = visible

    def update(self, dt, player, bob=(0.0, 0.0)):
        pass

    def arm(self, side):
        return self.arms[side]

    def place(self, x, y, z, yaw):
        pass

    def pose(self, name, seconds=0.0):
        pass

    def reset(self):
        pass


def new_game(**kwargs):
    game = start_playing(make_game(world=True, items=True, **kwargs))
    game.body = FakeBody()
    return game


def tick(game, seconds, inp=None, dt=FRAME, watch=None):
    """Roda `seconds` em quadros de `dt`; `watch(game)` é chamado depois de cada quadro."""
    for _ in range(int(round(seconds / dt))):
        game.tick(dt, inp or InputState())
        if inp is not None:
            inp.clear_edges()
        if watch is not None:
            watch(game)


def press(game, **flags):
    game.tick(FRAME, InputState(**flags))


def stand_before(game, ref):
    """Põe o jogador diante do item `ref` com ele na mira; devolve o alvo."""
    room, x, y, z, _ = layout.ITEM_SPOTS[ref]
    level_z = layout.LEVEL_Z[layout.ROOMS[room].level]
    for dx, dy in STAND_OFFSETS:
        teleport(game, x + dx, y + dy, level_z, 0)
        aim_at(game, (x, y, z + 0.05))
        game.tick(FRAME, InputState())
        current = game.interact.current
        if current is not None and current.ref == ref:
            return current
    raise AssertionError(f"não achei onde ficar para mirar {ref}")


def turn_between(rot_a, rot_b):
    """Ângulo (graus) entre duas orientações dadas em Euler XYZ (graus)."""
    from mathutils import Euler
    a, b = (Euler([math.radians(x) for x in rot], "XYZ").to_quaternion() for rot in (rot_a, rot_b))
    return math.degrees(a.rotation_difference(b).angle)


class Recorder:
    """Acompanha o que as mãos entregaram ao corpo quadro a quadro."""

    def __init__(self, game):
        self.game = game
        self.last = {}
        self.worst_move = {"L": 0.0, "R": 0.0}
        self.worst_turn = {"L": 0.0, "R": 0.0}
        self.busy_log = []

    def __call__(self, game):
        self.busy_log.append(game.hands.busy)
        for side, arm in game.body.arms.items():
            if not arm.targets:
                continue
            pos, rot, weight = arm.targets[-1]
            if weight < 0.02:
                self.last.pop(side, None)
                continue
            if side in self.last and len(arm.targets) > self.last[side][2]:
                old_pos, old_rot, _ = self.last[side]
                self.worst_move[side] = max(self.worst_move[side], math.dist(pos, old_pos))
                self.worst_turn[side] = max(self.worst_turn[side], turn_between(rot, old_rot))
            self.last[side] = (pos, rot, len(arm.targets))

    def assert_smooth(self):
        for side in "LR":
            assert self.worst_move[side] < MAX_STEP, (side, "a mão pulou", self.worst_move[side])
            assert self.worst_turn[side] < MAX_TURN, (side, "a mão girou de repente", self.worst_turn[side])


def run_pickup(game, ref, extra_seconds=0.4, recorder=None):
    """Mira o item, aperta E e deixa o gesto terminar. Devolve (ordem dos eventos, recorder)."""
    order = []
    target = stand_before(game, ref)
    recorder = recorder or Recorder(game)
    real_collect = game.interact._collect

    def collect(tgt):
        order.append(("contact", game.hands.busy))
        real_collect(tgt)

    game.interact._collect = collect
    press(game, interact=True)
    assert game.hands.busy, f"{ref}: a mão devia estar ocupada logo depois do E"
    assert ref not in game.state.collected, f"{ref}: o inventário mudou antes do contato"
    for _ in range(int(6.0 / FRAME)):
        game.tick(FRAME, InputState())
        recorder(game)
        if order and not game.hands.busy:
            break
    tick(game, extra_seconds, watch=recorder)
    game.interact._collect = real_collect
    return order, recorder, target


# --------------------------------------------------------------------------
# Executor de clipes (sem jogo)
# --------------------------------------------------------------------------
def test_track_passes_through_keys_without_overshoot():
    curve = handtrack.track((0.0, 0.0, "stop"), (0.5, 1.0), (1.0, 1.0, "stop"), (1.5, 0.0, "stop"))
    samples = [curve.sample(i / 100.0)[0] for i in range(151)]
    assert min(samples) >= -1e-9 and max(samples) <= 1.0 + 1e-9, (min(samples), max(samples))
    assert abs(curve.sample(0.5)[0] - 1.0) < 1e-9 and abs(curve.sample(1.0)[0] - 1.0) < 1e-9


def test_runner_fires_events_in_order_even_with_a_long_frame():
    clip = handtrack.Clip("t", 1.0, {"a": handtrack.track((0, 0), (1, 1))},
                          [handtrack.Event(0.9, "late"), handtrack.Event(0.2, "early"),
                           handtrack.Event(0.5, "mid", essential=True)])
    runner = handtrack.ClipPlayer()
    seen = []
    runner.start(clip)
    runner.update(0.6, lambda: {"a": (0.0,)}, None, lambda e: seen.append(e.name))
    assert seen == ["early", "mid"], seen
    runner.update(0.6, lambda: {"a": (0.0,)}, None, lambda e: seen.append(e.name))
    assert seen == ["early", "mid", "late", "done"] and not runner.active, seen


def test_runner_abort_runs_only_essential_events():
    clip = handtrack.Clip("t", 1.0, {}, [handtrack.Event(0.3, "cosmetic"), handtrack.Event(0.6, "state", essential=True)])
    runner = handtrack.ClipPlayer()
    seen = []
    runner.start(clip)
    runner.update(0.1, dict, None, lambda e: seen.append(e.name))
    runner.abort(lambda e: seen.append(e.name))
    assert seen == ["state", "done"] and not runner.active, seen


def test_runner_never_jumps_when_the_source_changes():
    base_a, base_b = {"a": (0.0, 0.0, 0.0)}, {"a": (1.0, 1.0, 1.0)}
    clip = handtrack.Clip("t", 0.6, {"a": handtrack.track((0, (0.5, 0.5, 0.5), "stop"), (0.6, (0.9, 0.2, 0.0), "stop"))})
    runner = handtrack.ClipPlayer()
    previous, worst = None, 0.0
    sequence = [(base_a, 30), (None, 60), (base_b, 60), (None, 40)]
    for base, frames in sequence:
        if base is None:
            runner.start(clip)
            base = base_b
        else:
            runner.rebase()
        for _ in range(frames):
            out = runner.update(FRAME, lambda base=base: base, None, lambda e: None)["a"]
            if previous is not None:
                worst = max(worst, math.dist(out, previous))
            previous = out
    assert worst < 0.12, f"salto de {worst:.4f} por quadro ao trocar de fonte"


# --------------------------------------------------------------------------
# Biblioteca de clipes
# --------------------------------------------------------------------------
def all_clips():
    clips = [handclips.lantern_first(), handclips.battery_pickup(), handclips.key_pickup(), handclips.map_pickup(),
             handclips.note_pickup(), handclips.note_wall(), handclips.note_putback(), handclips.note_retreat(),
             handclips.note_to_hold(), handclips.note_raise(False), handclips.note_raise(True),
             handclips.map_near(), handclips.map_back(), handclips.refuse(), handclips.swap(None, None),
             handclips.swap(C.ITEM_BATTERY, C.ITEM_BATTERY)]
    clips += [handclips.stow(k) for k in (C.ITEM_KEY, C.ITEM_MAP, C.ITEM_BATTERY, C.ITEM_NOTE)]
    clips += [handclips.draw(k) for k in (C.ITEM_KEY, C.ITEM_MAP, C.ITEM_BATTERY, C.ITEM_NOTE)]
    return clips


def test_clips_are_well_formed_and_smooth():
    for clip in all_clips():
        times = [event.t for event in clip.events]
        assert times == sorted(times) and clip.events[-1].name == "done", clip.name
        assert all(0.0 <= t <= clip.duration + 1e-9 for t in times), clip.name
        for name, curve in clip.tracks.items():
            assert curve.end <= clip.duration + 1e-9, (clip.name, name)
        anchors = {"R.pos": (0.0, -0.1, -0.5), "L.pos": (0.0, -0.1, -0.5)}
        for name, curve in clip.tracks.items():
            if name.endswith(".rot"):
                previous = curve.sample(0.0)
                for i in range(1, int(clip.duration / FRAME) + 1):
                    value = curve.sample(i * FRAME)
                    turn = math.degrees(2.0 * math.acos(min(1.0, abs(sum(a * b for a, b in zip(value, previous))))))
                    assert turn < MAX_TURN, (clip.name, name, round(i * FRAME, 3), round(turn, 1))
                    previous = value
            if not name.endswith(".pos"):
                continue
            previous = curve.sample(0.0, {"grasp": anchors[name]})
            for i in range(1, int(clip.duration / FRAME) + 1):
                value = curve.sample(i * FRAME, {"grasp": anchors[name]})
                assert math.dist(value, previous) < MAX_STEP, (clip.name, name, i * FRAME, math.dist(value, previous))
                previous = value
    assert 1.4 <= handclips.swap(None, None).duration <= 2.2      # ESTIMADO: a troca real leva alguns segundos; aqui é comprimida


def test_every_pickup_clip_makes_contact_before_it_ends():
    for clip in (handclips.lantern_first(), handclips.battery_pickup(), handclips.key_pickup(), handclips.map_pickup()):
        names = [e.name for e in clip.events]
        assert names.index("contact") < names.index("done"), clip.name
        contact = next(e for e in clip.events if e.name == "contact")
        assert contact.essential and 0.4 < contact.t < 1.0, (clip.name, contact.t)


def test_flicker_pattern_is_two_to_four_dips_with_shrinking_gaps():
    bursts = handclips.FLICKER_BURSTS
    assert 2 <= len(bursts) <= 4
    starts = [start for start, _ in bursts]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(g2 < g1 for g1, g2 in zip(gaps, gaps[1:])), gaps
    curve = [burst_curve(i / 100.0) for i in range(101)]
    assert curve[0] == 1.0 and abs(curve[-1] - 1.0) < 1e-9 and min(curve) == 0.0 and max(curve) > 1.05
    # a corrente de uma rajada abre o contato por milissegundos: nenhuma abertura passa de 60 ms
    from sem_alvorada.engine import flashlight as fl
    longest = max(b - a for a, b in fl.CHATTER) * max(length for _, length in bursts)
    assert longest < 0.060, longest
    # e o filamento sobe e desce em dezenas de ms (ESTIMADO 20 a 80 ms de 10 a 90%)
    assert 0.020 <= math.log(9.0) * fl.FILAMENT_TAU_UP <= 0.080 and 0.020 <= math.log(9.0) * fl.FILAMENT_TAU_DOWN <= 0.080


# --------------------------------------------------------------------------
# Lanterna
# --------------------------------------------------------------------------
def test_first_flashlight_pickup_ends_lit_after_two_to_four_blinks():
    game = new_game()
    state = game.state
    recorder = Recorder(game)
    stand_before(game, "FLASHLIGHT")
    levels = []
    seen = {"contact": None, "has": []}
    real_collect = game.interact._collect

    def collect(tgt):
        seen["contact"] = (game.hands.busy, state.battery)
        real_collect(tgt)

    game.interact._collect = collect
    press(game, interact=True)
    assert game.hands.busy and not state.has_flashlight and game.hands.held is None
    for _ in range(int(5.0 / FRAME)):
        game.tick(FRAME, InputState())
        recorder(game)
        levels.append(game.flashlight.intensity)
        if seen["contact"] and not game.hands.busy:
            break
    assert seen["contact"] is not None, "o contato nunca aconteceu"
    assert state.has_flashlight and "FLASHLIGHT" in state.collected
    assert abs(state.battery - C.FLASHLIGHT_FOUND_CHARGE) < 0.01, state.battery
    assert state.flashlight_on and levels[-1] > 0.99, "a primeira vez termina com a luz acesa"
    assert game.hands.held == C.ITEM_FLASHLIGHT and not game.hands.busy
    # cada piscada é uma rajada de mau contato (várias aberturas de ms que o filamento alisa): quedas a menos de
    # 0,2 s uma da outra contam como a mesma piscada
    drops = [i for i, (a, b) in enumerate(zip(levels, levels[1:])) if a >= 0.5 > b]
    blinks = sum(1 for k, i in enumerate(drops) if k == 0 or (i - drops[k - 1]) * FRAME > 0.2)
    assert 2 <= blinks <= 4, f"{blinks} piscadas"
    assert levels.index(max(levels)) > 0 and min(l for l in levels if l > 0) < 0.35, "a piscada devia ir ao fundo"
    recorder.assert_smooth()
    assert kinds_logged(game, "flash_click"), "o clique do polegar é ruído"
    sounds = game.audio.played_names()
    assert sounds.count("flash_flicker_burst") == len(handclips.FLICKER_BURSTS) and "flash_click_on" in sounds
    assert game.player_cam.data.angle > 0


def test_flashlight_f_is_only_the_thumb_click_afterwards():
    game = new_game()
    game.state.has_flashlight = True
    tick(game, 0.3)
    thumb_before = len(game.body.arm("R").fingers)
    press(game, flashlight=True)
    assert game.state.flashlight_on and not game.hands.busy
    tick(game, 0.2)
    press(game, flashlight=True)
    assert not game.state.flashlight_on
    sounds = game.audio.played_names()
    assert "flash_click_on" in sounds and "flash_click_off" in sounds
    thumbs = [f[0] for f in game.body.arm("R").fingers[thumb_before:]]
    assert max(thumbs) > min(thumbs) + 0.2, "o polegar devia ter se mexido no clique"


def test_battery_swap_effects_duration_and_refusals():
    game = new_game()
    state = game.state
    state.has_flashlight, state.flashlight_on = True, True
    state.battery, state.spare_batteries = 0.2, 0
    tick(game, 0.2)
    press(game, reload=True)                                    # sem reserva: só um gesto de recusa
    assert abs(state.battery - 0.2) < 0.01 and state.spare_batteries == 0 and state.flashlight_on
    assert game.flashlight.swap_left == 0
    tick(game, 1.0)
    assert not game.hands.busy
    state.spare_batteries, state.battery = 1, 0.95
    press(game, reload=True)                                    # carga ainda boa
    assert state.spare_batteries == 1 and state.flashlight_on and game.flashlight.swap_left == 0
    tick(game, 1.0)
    state.battery = 0.2
    press(game, reload=True)
    assert game.flashlight.swap_left > 0 and not state.flashlight_on, "a luz se apaga durante a troca"
    assert kinds_logged(game, "battery_swap")[-1][2] == C.NOISE_PLAYER["battery_swap"]
    started = game.clock
    while game.hands.busy and game.clock - started < 3.0:
        game.tick(FRAME, InputState())
        if game.flashlight.swap_left > 0:
            assert not state.flashlight_on
    took = game.clock - started
    assert 1.4 <= took + FRAME <= 2.2, f"a troca durou {took:.2f} s"
    assert state.battery > 0.99 and state.spare_batteries == 0 and state.flashlight_on
    assert game.flashlight.swap_left == 0
    names = game.audio.played_names()
    assert "battery_clack" in names and "battery_insert" in names


def test_swap_with_a_battery_in_the_palm_uses_it_and_keeps_the_next_one():
    game = new_game()
    state = game.state
    state.has_flashlight, state.battery, state.spare_batteries = True, 0.1, 2
    tick(game, 0.1)
    assert game.hands.equip(C.ITEM_BATTERY)
    tick(game, 1.0)
    assert game.hands.held == C.ITEM_BATTERY and C.ITEM_BATTERY in game.hands.visible_kinds()
    press(game, reload=True)
    tick(game, 2.0)
    assert state.spare_batteries == 1 and state.battery > 0.99
    assert game.hands.held == C.ITEM_BATTERY and C.ITEM_BATTERY in game.hands.visible_kinds(), "outra pilha na palma"
    state.battery = 0.1
    press(game, reload=True)
    tick(game, 2.0)
    assert state.spare_batteries == 0 and game.hands.held == C.ITEM_FLASHLIGHT
    assert C.ITEM_BATTERY not in game.hands.visible_kinds()


def test_swap_puts_away_a_key_first_and_still_finishes():
    game = new_game()
    state = game.state
    state.has_flashlight, state.has_key, state.battery, state.spare_batteries = True, True, 0.1, 1
    tick(game, 0.1)
    game.hands.equip(C.ITEM_KEY)
    tick(game, 1.0)
    press(game, reload=True)
    tick(game, 3.0)
    assert state.battery > 0.99 and state.spare_batteries == 0 and state.flashlight_on
    assert game.hands.held == C.ITEM_FLASHLIGHT and not game.hands.busy


# --------------------------------------------------------------------------
# Pegar cada item
# --------------------------------------------------------------------------
def check_pickup(ref, expect):
    game = new_game()
    game.state.has_flashlight = True
    tick(game, 0.3)
    order, recorder, _ = run_pickup(game, ref)
    assert [name for name, _ in order] == ["contact"], (ref, order)
    assert order[0][1], f"{ref}: o contato tem de acontecer com a mão ocupada"
    assert expect(game.state), ref
    assert not game.hands.busy, f"{ref}: a mão devia ter terminado"
    assert game.hands.held == C.ITEM_FLASHLIGHT and not game.hands.visible_kinds() - {C.ITEM_FLASHLIGHT}, ref
    recorder.assert_smooth()
    assert game.body.arm("L").releases > 0, "a esquerda devia voltar à pose solta"
    return game


def test_pickup_battery_key_and_map():
    check_pickup("BATTERY_4", lambda s: s.spare_batteries == 1 and s.batteries_found == 1)
    check_pickup("KEY", lambda s: s.has_key)
    check_pickup("MAP", lambda s: s.has_map)


def test_pickup_key_swings_once_and_jingles():
    game = new_game()
    game.state.has_flashlight = True
    swings = []
    run_pickup(game, "KEY", extra_seconds=0.0)
    game = new_game()
    game.state.has_flashlight = True
    stand_before(game, "KEY")
    press(game, interact=True)
    peak = 0.0
    for _ in range(int(3.0 / FRAME)):
        game.tick(FRAME, InputState())
        peak = max(peak, abs(game.hands.pendulum.angle[0]))
        swings.append(game.hands.pendulum.angle[0])
    assert math.degrees(peak) > 12.0, f"o chaveiro balançou só {math.degrees(peak):.1f} graus"
    assert abs(swings[-1]) < math.radians(2.0), "o balanço devia amortecer até parar"
    assert game.audio.played_names().count("key_jingle") >= 1 and "key_pickup" in game.audio.played_names()   # o do contato vem do Interact


def test_held_key_jingles_on_running_steps_with_noise():
    game = new_game()
    game.state.has_flashlight = game.state.has_key = True
    game.hands.equip(C.ITEM_KEY)
    tick(game, 1.0)
    teleport(game, 6.5, 1.0, 0.0, 0)
    before = len(kinds_logged(game, "key_jingle"))
    tick(game, 2.5, InputState(move_y=1.0, run=True))
    jingles = kinds_logged(game, "key_jingle")[before:]
    assert len(jingles) >= 3 and all(j[2] == C.NOISE_PLAYER["key_jingle"] for j in jingles), jingles
    assert abs(game.hands.pendulum.angle[0]) + abs(game.hands.pendulum.angle[1]) > 0.0
    before = len(kinds_logged(game, "key_jingle"))
    teleport(game, 6.5, 1.0, 0.0, 0)
    tick(game, 2.0, InputState(move_y=1.0))                      # andando, sem correr: balança mas não tilinta
    assert len(kinds_logged(game, "key_jingle")) == before


def test_pickup_battery_while_holding_a_key_stows_it_first():
    game = new_game()
    game.state.has_flashlight = game.state.has_key = True
    game.hands.equip(C.ITEM_KEY)
    tick(game, 1.0)
    assert game.hands.held == C.ITEM_KEY
    order, recorder, _ = run_pickup(game, "BATTERY_4", extra_seconds=0.6)
    assert game.state.spare_batteries == 1 and game.hands.held == C.ITEM_FLASHLIGHT
    recorder.assert_smooth()


def test_read_floor_note_lifts_opens_reader_and_puts_it_back():
    game = new_game()
    game.state.has_flashlight = True
    target = stand_before(game, "NOTE_1")
    obj = target.obj
    press(game, interact=True)
    assert game.hands.busy and game.phase == "play" and not obj.hide_viewport
    recorder = Recorder(game)
    opened = None
    for _ in range(int(3.0 / FRAME)):
        game.tick(FRAME, InputState())
        recorder(game)
        if game.phase == "reading":
            opened = game.clock
            break
    assert opened is not None and game.reader_note == "NOTE_1"
    assert obj.hide_viewport and C.ITEM_NOTE in game.hands.visible_kinds(), "a folha saiu do lugar com a mão"
    game.tick(FRAME, InputState(interact=True))                    # fecha o leitor
    assert game.phase == "play"
    tick(game, 1.4, watch=recorder)
    assert not obj.hide_viewport, "a folha devia voltar ao lugar"
    assert not game.hands.busy and C.ITEM_NOTE not in game.hands.visible_kinds()
    recorder.assert_smooth()


def test_read_wall_note_touches_without_taking_it_and_zooms_back():
    game = new_game()
    game.state.has_flashlight = True
    stand_before(game, "NOTE_4")
    base_angle = game.player_cam.data.angle
    press(game, interact=True)
    recorder = Recorder(game)
    for _ in range(int(3.0 / FRAME)):
        game.tick(FRAME, InputState())
        recorder(game)
        if game.phase == "reading":
            break
    assert game.phase == "reading" and C.ITEM_NOTE not in game.hands.visible_kinds()
    assert game.player_cam.data.angle < base_angle * 0.9, "o rosto devia se aproximar da nota"
    game.tick(FRAME, InputState(interact=True))
    tick(game, 1.2, watch=recorder)
    assert abs(game.player_cam.data.angle - base_angle) < 1e-3 and not game.hands.busy
    recorder.assert_smooth()


def test_held_note_from_the_wheel_reopens_the_reader_and_returns_to_the_hand():
    game = new_game()
    game.state.has_flashlight = True
    game.state.notes_read.add("NOTE_1")
    game.hands.begin_read("NOTE_1", lambda: game.open_note("NOTE_1"))
    tick(game, 2.0)
    assert game.phase == "reading"
    game.tick(FRAME, InputState(interact=True))
    tick(game, 1.0)
    assert game.hands.equip(C.ITEM_NOTE)
    tick(game, 1.0)
    assert game.hands.held == C.ITEM_NOTE and C.ITEM_NOTE in game.hands.visible_kinds()
    assert game.hands.use_held() and not game.hands.busy is False
    tick(game, 2.0)
    assert game.phase == "reading" and game.reader_note == "NOTE_1"
    game.tick(FRAME, InputState(interact=True))
    tick(game, 1.0)
    assert game.hands.held == C.ITEM_NOTE and C.ITEM_NOTE in game.hands.visible_kinds()


def test_held_map_comes_to_the_face_and_goes_back():
    game = new_game()
    game.state.has_flashlight = game.state.has_map = True
    game.hands.equip(C.ITEM_MAP)
    tick(game, 1.0)
    rest = game.body.arm("L").targets[-1][0]
    assert game.hands.use_held()
    tick(game, 0.8)
    near = game.body.arm("L").targets[-1][0]
    assert near[2] > rest[2] + 0.05 or math.dist(near, rest) > 0.08, "o mapa devia se aproximar do rosto"
    assert game.hands.use_held(), "E de novo devolve o mapa"
    tick(game, 1.0)
    assert math.dist(game.body.arm("L").targets[-1][0], rest) < 0.03
    assert game.hands.use_held() and True
    tick(game, 3.0)
    assert math.dist(game.body.arm("L").targets[-1][0], rest) < 0.03, "sem apertar nada o mapa volta sozinho"


# --------------------------------------------------------------------------
# Roda (equip), interrupção e reset
# --------------------------------------------------------------------------
def test_equip_switches_items_without_invalid_states():
    game = new_game()
    state = game.state
    state.has_flashlight, state.has_key, state.has_map, state.spare_batteries = True, True, True, 2
    assert game.hands.held == C.ITEM_FLASHLIGHT
    seen = []
    for kind in (C.ITEM_KEY, C.ITEM_MAP, C.ITEM_BATTERY, C.ITEM_FLASHLIGHT, C.ITEM_KEY):
        assert game.hands.equip(kind)
        assert game.hands.held == kind or (kind == C.ITEM_FLASHLIGHT and game.hands.held == C.ITEM_FLASHLIGHT)
        for _ in range(int(0.3 / FRAME)):
            game.tick(FRAME, InputState())
            seen.append(sorted(game.hands.visible_kinds()))
            assert len(game.hands.visible_kinds() - {C.ITEM_FLASHLIGHT}) <= 1, "dois itens na mão esquerda"
        tick(game, 0.9)
        wanted = {C.ITEM_FLASHLIGHT} | ({kind} if kind != C.ITEM_FLASHLIGHT else set())
        assert game.hands.visible_kinds() == wanted, (kind, game.hands.visible_kinds())
    assert game.hands.equip(C.ITEM_KEY)                               # interrompe a troca em curso
    tick(game, 0.1)
    assert game.hands.equip(C.ITEM_MAP)
    tick(game, 1.5)
    assert game.hands.held == C.ITEM_MAP and game.hands.visible_kinds() == {C.ITEM_FLASHLIGHT, C.ITEM_MAP}
    assert game.hands.equip(None) and game.hands.held == C.ITEM_FLASHLIGHT
    tick(game, 1.0)
    assert game.hands.visible_kinds() == {C.ITEM_FLASHLIGHT}


def test_equip_is_refused_while_a_pickup_is_in_progress():
    game = new_game()
    game.state.has_flashlight, game.state.has_key = True, True
    stand_before(game, "BATTERY_4")
    press(game, interact=True)
    assert game.hands.busy and not game.hands.equip(C.ITEM_KEY)
    tick(game, 3.0)
    assert not game.hands.busy and game.hands.equip(C.ITEM_KEY)


def test_a_new_pickup_interrupts_the_note_being_put_back():
    game = new_game()
    game.state.has_flashlight = True
    target = stand_before(game, "NOTE_1")
    press(game, interact=True)
    tick(game, 3.0)
    assert game.phase == "reading"
    game.tick(FRAME, InputState(interact=True))
    tick(game, 0.1)
    assert game.hands.runner.active and target.obj.hide_viewport
    assert not game.hands.busy, "guardar a folha de volta pode ser interrompido"
    assert game.hands.begin_read("NOTE_1", lambda: None)
    tick(game, 0.05)
    assert not target.obj.hide_viewport or game.hands.runner.active


def test_reset_in_the_middle_leaves_nothing_behind():
    game = new_game()
    state = game.state
    state.has_flashlight = True
    stand_before(game, "KEY")
    press(game, interact=True)
    tick(game, 0.3)
    game.hands.reset()
    assert not game.hands.busy and not game.hands.visible_kinds() - {C.ITEM_FLASHLIGHT}
    tick(game, 3.0)
    assert not state.has_key and "KEY" not in state.collected, "o contato não pode acontecer depois do reset"
    assert game.hands.held == C.ITEM_FLASHLIGHT and not game.hands.busy
    assert game.hands.runner.clip is None and game.hands._after is None


def game_with_cutscene():
    game, _brain, _rig, _player = fk.game_with_fake_entity(hunts=False, cutscene_seconds=1.0, world=True, items=True)
    start_playing(game)
    game.body = FakeBody()
    return game


def test_cutscene_in_the_middle_finishes_the_state_and_hides_the_hands():
    game = game_with_cutscene()
    state = game.state
    state.has_flashlight, state.battery, state.spare_batteries, state.flashlight_on = True, 0.2, 1, True
    tick(game, 0.1)
    press(game, reload=True)
    tick(game, 0.4)
    assert game.flashlight.swap_left > 0
    game.play_cutscene("blackout")
    tick(game, 0.3)
    assert state.battery > 0.99 and state.spare_batteries == 0, "a troca termina no estado"
    assert game.flashlight.swap_left == 0 and not game.hands.busy
    assert not game.hands.visible_kinds()
    assert all(obj is None or obj.hide_viewport for obj in game.hands.models.objects.values())
    assert game.body.arm("L").releases > 0 and game.body.arm("R").releases > 0


def test_first_flashlight_pickup_cut_by_a_cutscene_is_never_half_done():
    game = game_with_cutscene()
    stand_before(game, "FLASHLIGHT")
    press(game, interact=True)
    tick(game, 0.2)
    game.play_cutscene("intro")
    tick(game, 0.3)
    state = game.state
    assert state.has_flashlight == ("FLASHLIGHT" in state.collected), "o item ou foi pego inteiro ou ficou no mundo"
    assert not state.has_flashlight or state.battery <= C.FLASHLIGHT_FOUND_CHARGE + 1e-6
    assert not game.hands.busy and game.flashlight.lantern_matrix is None and not game.hands.visible_kinds()


def test_hands_pull_back_and_lower_near_a_wall():
    game = new_game()
    game.state.has_flashlight = True
    teleport(game, 6.5, 2.0, 0.0, 0)                           # hall comprido à frente
    tick(game, 0.8)
    open_space = game.hands.last["R"][0]
    teleport(game, 7.5, 9.575, 0.0, 0)                         # encostado na parede norte
    tick(game, 0.8)
    near_wall = game.hands.last["R"][0]
    assert near_wall[2] > open_space[2] + 0.04 and near_wall[1] < open_space[1] - 0.03, (open_space, near_wall)
    teleport(game, 6.5, 2.0, 0.0, 0)
    tick(game, 0.8)
    assert math.dist(game.hands.last["R"][0], open_space) < 0.01, "a mão devia voltar quando a parede some"


def test_left_hand_gets_ready_while_the_wheel_is_open():
    game = new_game()
    game.state.has_flashlight = True
    tick(game, 0.5)
    assert game.body.arm("L").targets == [] or game.body.arm("L").targets[-1][2] < 0.02
    held = InputState(wheel_held=True)
    tick(game, 0.6, held)                                  # a roda abre enquanto a tecla está apertada
    assert game.inventory.wheel_open
    pos, _rot, weight = game.body.arm("L").targets[-1]
    assert 0.3 < weight < 0.8 and pos[0] < -0.2, (pos, weight)
    tick(game, 1.0)
    assert game.body.arm("L").releases > 0 and not game.hands.visible_kinds() - {C.ITEM_FLASHLIGHT}


def build_models():
    """Cena de teste com os modelos da mão construídos pela etapa props (como no build de verdade)."""
    from sem_alvorada.buildctx import BuildContext
    from sem_alvorada.props import flashlight as props_flashlight
    from sem_alvorada.props import kit
    scene = fk.fresh_scene()
    fallback = scene.objects.get(C.OBJ_VIEW_FLASH)               # a etapa engine cria uma lanterna simples se faltar
    if fallback is not None:
        fk.bpy.data.objects.remove(fallback, do_unlink=True)
    kit.set_quality("medium")
    props_flashlight.make_viewmodel(BuildContext(scene, verbose=False))
    return scene


def test_handheld_models_exist_fit_the_budget_and_chain_correctly():
    from sem_alvorada.engine.handheld import MODEL_NAMES
    scene = build_models()
    names = [*MODEL_NAMES.values(), "ViewModel_Flashlight_Cap", "ViewModel_Map_P2", "ViewModel_Map_P3"]
    total = 0
    for name in names:
        obj = scene.objects[name]
        assert obj.hide_viewport and obj.hide_render, f"{name} devia nascer oculto"
        obj.data.calc_loop_triangles()
        total += len(obj.data.loop_triangles)
    assert total <= 6000, f"{total} triângulos nas mãos (teto 6000)"
    objects = scene.objects
    assert objects["ViewModel_Flashlight_Cap"].parent is objects["ViewModel_Flashlight"]
    assert objects["ViewModel_Map_P2"].parent is objects["ViewModel_Map"]
    assert objects["ViewModel_Map_P3"].parent is objects["ViewModel_Map_P2"]
    assert abs(objects["ViewModel_Map_P2"].location.x - 0.118) < 1e-6
    fill = objects["HandFill"]
    assert fill.type == "LIGHT" and fill.data.type == "POINT" and not fill.data.use_shadow and fill.data.energy < 3.0
    assert fill.hide_viewport and fill.hide_render, "a luz das mãos só acende com algo na mão"
    for name in ("ViewModel_Flashlight", "ViewModel_Key", "ViewModel_Map", "ViewModel_Battery", "ViewModel_Paper"):
        for material in objects[name].data.materials:
            image = next((n.image for n in material.node_tree.nodes if n.type == "TEX_IMAGE"), None) if material.node_tree else None
            assert image is None or max(image.size) <= 512, (name, material.name, tuple(image.size))


def test_flashlight_viewmodel_has_no_hand_or_sleeve_and_the_cap_opens_at_the_tail():
    scene = build_models()
    body = scene.objects["ViewModel_Flashlight"]
    assert not any(m.name in ("skin_hand", "sleeve_cloth") for m in body.data.materials), "a mão é do corpo agora"
    cap = scene.objects["ViewModel_Flashlight_Cap"]
    cap_low = min(v.co.z for v in cap.data.vertices) + cap.location.z
    body_high = max(v.co.z for v in body.data.vertices)
    assert abs(cap.location.z - 0.0574) < 1e-3, cap.location
    assert cap_low > 0.05 and body_high < 0.06, "a tampa fica atrás do cano, na cauda (+Z do viewmodel)"
    assert max(v.co.x for v in cap.data.vertices) <= 0.002 and min(v.co.x for v in cap.data.vertices) > -0.042


def test_handheld_objects_hang_from_the_player_camera_and_hide_when_the_world_is_idle():
    game = new_game()
    game.state.has_flashlight = game.state.has_key = True
    game.hands.equip(C.ITEM_KEY)
    tick(game, 1.0)
    flash = game.scene.objects[C.OBJ_VIEW_FLASH]
    assert flash.parent is game.player_cam and not flash.hide_viewport
    game.flashlight.update(DT_IDLE, 0.0, 0.0, show_viewmodel=False)       # o que o mundo ocioso (cutscene) faz
    assert flash.hide_viewport and not game.hands.visible_kinds()
    assert game.hands.models.fill is None or game.hands.models.fill.hide_render


def test_neutral_hand_matches_the_body_package():
    from sem_alvorada.body import skeleton
    assert all(abs(a - b) < 1e-9 for ra, rb in zip(handclips.NEUTRAL_HAND, skeleton.NEUTRAL_HAND_CAM)
               for a, b in zip(ra, rb))
    from sem_alvorada.body import handframe
    for fingers, palm in (((0, 0, -1), (-1, 0, 0)), ((-0.59, -0.81, 0), (-0.81, 0.59, 0)), ((0.35, 0.3, -0.89), (0.75, -0.65, 0))):
        mine, theirs = handclips.hand_rotation(fingers, palm), handframe.hand_rotation(fingers, palm)
        assert all(abs(a - b) < 1e-6 for a, b in zip(mine, theirs)), (mine, theirs)


def test_battery_budget_and_constants_match_the_models():
    from sem_alvorada.props import flashlight as props_flashlight
    head_end, head_radius, grip = props_flashlight.HEAD_END, props_flashlight.HEAD_RADIUS, props_flashlight.GRIP_CENTER
    assert (head_end, head_radius, grip) == (0.2068, 0.0292, 0.073), "handclips._flashlight_to_model está desatualizado"


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
    print(f"{len(tests) - failures}/{len(tests)} testes das mãos passaram")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
