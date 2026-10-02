"""Roda de itens: mapeamento ângulo -> setor, zona morta, setores apagados, soltar sem mexer, casos de borda
(mudança de fase, mão ocupada, item que some) e a integração com Controls e com o Game.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_inventory.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_engine_fakes as fk  # noqa: E402
from test_engine_fakes import DT, InputState, make_game, start_playing, step  # noqa: E402

from sem_alvorada.engine import controls, inventory  # noqa: E402
from sem_alvorada.engine.controls import Controls  # noqa: E402
from sem_alvorada.engine.inventory import DEAD_ZONE, POINTER_RADIUS, SLOTS, sector_at  # noqa: E402

FLASHLIGHT, BATTERY, KEY, MAP, NOTE = SLOTS


class FakeHands:
    """Mãos de mentira: guardam o que lhes pediram e recusam a troca enquanto `busy`."""

    def __init__(self):
        self.held = None
        self.busy = False
        self.equips = []

    def equip(self, kind, on_done=None):
        if self.busy:
            return False
        self.held = kind
        self.equips.append(kind)
        return True

    def reset(self):
        self.held = None
        self.busy = False

    def suspend(self):
        pass

    def update(self, dt, bob):
        pass

    def toggle_flashlight(self):
        pass

    def reload_flashlight(self):
        pass

    def end_read(self):
        pass


def vector(sector_angle_deg, length=0.2):
    """Vetor de mouse (dx, dy) apontando `sector_angle_deg` graus em sentido horário a partir do topo."""
    angle = math.radians(sector_angle_deg)
    return length * math.sin(angle), length * math.cos(angle)


def wheel_game(owned=SLOTS, held=FLASHLIGHT):
    """Partida em jogo com mãos falsas e os tipos de `owned` no inventário."""
    game = start_playing(make_game(world=True))
    game.hands = FakeHands()
    game.hands.held = held
    state = game.state
    state.has_flashlight = FLASHLIGHT in owned
    state.spare_batteries = 2 if BATTERY in owned else 0
    state.has_key = KEY in owned
    state.has_map = MAP in owned
    state.notes_read = {"NOTE_1"} if NOTE in owned else set()
    game.inventory.reset()
    return game


def hold(game, dx=0.0, dy=0.0):
    return step(game, InputState(wheel_held=True, wheel_dx=dx, wheel_dy=dy))


def release(game):
    return step(game, InputState(wheel_held=False))


def sounds(game):
    return [name for name in game.audio.played_names() if name.startswith("ui_wheel")]


# --------------------------------------------------------------------------
# Ângulo -> setor
# --------------------------------------------------------------------------
def test_sector_mapping_is_clockwise_from_the_top_for_all_five_sectors():
    for index in range(5):
        assert sector_at(*vector(index * 72)) == index, index
    assert sector_at(0.0, 0.2) == 0 and sector_at(0.2, 0.0) == 1 and sector_at(-0.2, 0.0) == 4
    assert sector_at(0.01, -0.2) == 2 and sector_at(-0.01, -0.2) == 3, "para baixo é a divisa entre chave e mapa"


def test_sector_boundaries_sit_halfway_between_sector_centers():
    for index in range(5):
        edge = index * 72 + 36
        assert sector_at(*vector(edge - 0.01)) == index, (index, "logo antes da divisa")
        assert sector_at(*vector(edge + 0.01)) == (index + 1) % 5, (index, "logo depois da divisa")
    assert sector_at(*vector(-0.01)) == 0 and sector_at(*vector(0.01)) == 0, "a volta completa fecha no topo"
    assert sector_at(*vector(359.99)) == 0 and sector_at(*vector(324 + 0.01)) == 0


def test_dead_zone_selects_nothing():
    assert sector_at(0.0, 0.0) is None
    assert sector_at(0.0, DEAD_ZONE * 0.98) is None and sector_at(DEAD_ZONE * 0.7, DEAD_ZONE * 0.7) is None
    assert sector_at(0.0, DEAD_ZONE * 1.02) == 0
    assert abs(DEAD_ZONE - 0.06) < 1e-9, "contrato de docs/FASE3.md"


# --------------------------------------------------------------------------
# Abrir, escolher, soltar
# --------------------------------------------------------------------------
def test_holding_the_key_opens_the_wheel_and_a_sector_is_picked_by_the_accumulated_vector():
    game = wheel_game()
    hold(game)
    assert game.inventory.wheel_open and game.inventory.selection is None
    hold(game, *vector(144, 0.03))                      # devagar: cada quadro fica dentro da zona morta
    assert game.inventory.selection is None
    hold(game, *vector(144, 0.03))
    assert game.inventory.selection == KEY, "o vetor acumulado passou da zona morta"
    assert sounds(game) == ["ui_wheel_open", "ui_wheel_tick"]
    hold(game, *vector(216, 0.4))
    assert game.inventory.selection == MAP, "o ponteiro acumulado atravessa o centro até o setor vizinho"
    assert sounds(game) == ["ui_wheel_open", "ui_wheel_tick", "ui_wheel_tick"], "um tique por mudança de setor"


def test_release_equips_the_selected_sector_and_plays_the_close_sound():
    game = wheel_game()
    hold(game)
    hold(game, *vector(72, 0.2))
    assert game.inventory.selection == BATTERY
    release(game)
    assert not game.inventory.wheel_open and game.hands.equips == [BATTERY] and game.hands.held == BATTERY
    assert sounds(game)[0] == "ui_wheel_open" and sounds(game)[-1] == "ui_wheel_close"
    assert game.inventory.held == BATTERY


def test_the_last_mouse_movement_before_the_release_still_counts():
    game = wheel_game()
    hold(game)
    step(game, InputState(wheel_held=False, wheel_dx=vector(144, 0.2)[0], wheel_dy=vector(144, 0.2)[1]))
    assert game.hands.equips == [KEY], "o movimento e o soltar chegaram no mesmo quadro"


def test_release_without_moving_keeps_what_is_in_the_hand():
    game = wheel_game(held=KEY)
    hold(game)
    hold(game, 0.02, 0.02)
    release(game)
    assert game.hands.equips == [] and game.hands.held == KEY
    game = wheel_game(held=KEY)
    hold(game)
    hold(game, *vector(144, 0.2))                         # a chave já está na mão: escolher a mesma coisa não troca
    release(game)
    assert game.hands.equips == []


def test_returning_to_the_dead_zone_cancels_the_choice():
    game = wheel_game()
    hold(game)
    hold(game, *vector(72, 0.2))
    assert game.inventory.selection == BATTERY
    hold(game, *vector(252, 0.2))                         # volta ao centro
    assert game.inventory.selection is None
    release(game)
    assert game.hands.equips == []


def test_unavailable_sector_is_not_selectable_and_is_shown_dim():
    game = wheel_game(owned=(FLASHLIGHT, KEY))
    hold(game)
    hold(game, *vector(216, 0.2))                         # setor do mapa, que o jogador não tem
    assert game.inventory.selection is None
    release(game)
    assert game.hands.equips == []
    hold(game)
    slots = {slot["kind"]: slot for slot in game.hud_model()["wheel"]["slots"]}
    assert [kind for kind, slot in slots.items() if slot["owned"]] == [FLASHLIGHT, KEY]
    hold(game, *vector(144, 0.2))
    assert game.inventory.selection == KEY


def test_notes_enter_the_wheel_only_after_the_first_one_is_read():
    game = wheel_game(owned=(FLASHLIGHT,))
    assert NOTE not in game.inventory.owned() and game.inventory.count(NOTE) == 0
    game.state.notes_read.update({"NOTE_1", "NOTE_4"})
    assert NOTE in game.inventory.owned() and game.inventory.count(NOTE) == 2
    assert game.inventory.owned() == (FLASHLIGHT, NOTE), "a ordem dos setores é fixa"


def test_counts_follow_the_state():
    game = wheel_game(owned=SLOTS)
    inv = game.inventory
    assert inv.count(BATTERY) == 2 and inv.count(KEY) == 1 and inv.count(MAP) == 1 and inv.count(FLASHLIGHT) == 1
    game.state.spare_batteries = 0
    assert inv.count(BATTERY) == 0 and BATTERY not in inv.owned()


def test_pointer_is_clamped_so_a_wild_swing_comes_back_quickly():
    game = wheel_game()
    hold(game)
    hold(game, 3.0, 0.0)                                  # pulou para a direita, muito além do raio
    assert game.inventory.selection == BATTERY
    hold(game, -(POINTER_RADIUS * 2 + 0.02), 0.0)         # basta atravessar o raio para ir ao lado oposto
    assert game.inventory.selection == NOTE
    assert math.hypot(*game.inventory.hud_block()["pointer"]) <= 1.0 + 1e-9


def test_a_new_item_marks_its_sector_but_does_not_open_the_wheel():
    game = wheel_game(owned=(FLASHLIGHT,))
    game.state.has_key = True
    game.inventory.on_collected(KEY)
    assert not game.inventory.wheel_open and sounds(game) == []
    assert game.inventory.hud_block()["fresh"] == (KEY,)
    hold(game)
    assert game.hud_model()["wheel"]["slots"][2]["fresh"]
    release(game)
    hold(game)
    assert game.inventory.hud_block()["fresh"] == (), "depois de ver a roda, a novidade some"


# --------------------------------------------------------------------------
# Casos de borda
# --------------------------------------------------------------------------
def test_wheel_closes_without_equipping_when_the_game_leaves_play():
    for phase in ("paused", "reading", "cutscene", "dead"):
        game = wheel_game()
        hold(game)
        hold(game, *vector(144, 0.2))
        assert game.inventory.selection == KEY
        game.phase = phase
        game.tick(DT, InputState(wheel_held=True))
        assert not game.inventory.wheel_open and game.hands.equips == [], phase
        assert sounds(game)[-1] == "ui_wheel_close", phase
        game.phase = "play"
        game.tick(DT, InputState(wheel_held=False))
        assert game.hands.equips == [], f"{phase}: soltar a tecla depois não equipa nada"


def test_pausing_with_the_key_held_closes_the_wheel():
    game = wheel_game()
    hold(game)
    hold(game, *vector(72, 0.2))
    step(game, InputState(wheel_held=True, pause=True))
    assert game.phase == "paused" and not game.inventory.wheel_open and game.hands.equips == []


def test_busy_hands_keep_the_latest_request_and_apply_it_when_free():
    game = wheel_game()
    game.hands.busy = True
    hold(game)
    hold(game, *vector(72, 0.2))
    release(game)
    assert game.hands.equips == [] and game.inventory.hud_block()["pending"] == BATTERY
    hold(game)
    hold(game, *vector(144, 0.2))                         # um pedido mais novo substitui o antigo
    release(game)
    assert game.inventory.hud_block()["pending"] == KEY
    for _ in range(5):
        step(game)
    assert game.hands.equips == []
    game.hands.busy = False
    step(game)
    assert game.hands.equips == [KEY] and game.inventory.hud_block()["pending"] is None
    step(game)
    assert game.hands.equips == [KEY], "o pedido só vale uma vez"


def test_a_request_the_hands_never_accept_is_dropped_after_two_seconds():
    game = wheel_game()
    game.hands.busy = True
    hold(game)
    hold(game, *vector(72, 0.2))
    release(game)
    fk.run_for(game, inventory.PENDING_SECONDS + 0.5)
    assert game.inventory.hud_block()["pending"] is None
    game.hands.busy = False
    step(game)
    assert game.hands.equips == [], "um pedido velho não pode pegar o jogador de surpresa"


def test_a_pending_request_is_dropped_if_the_item_disappears():
    game = wheel_game()
    game.hands.busy = True
    hold(game)
    hold(game, *vector(72, 0.2))
    release(game)
    game.state.spare_batteries = 0
    game.hands.busy = False
    step(game)
    assert game.hands.equips == [] and game.inventory.hud_block()["pending"] is None


def test_an_item_that_vanishes_with_the_wheel_open_cannot_be_chosen():
    game = wheel_game()
    hold(game)
    hold(game, *vector(72, 0.2))
    assert game.inventory.selection == BATTERY
    game.state.spare_batteries = 0                        # a troca de pilhas consumiu a última
    hold(game)
    assert game.inventory.selection is None
    release(game)
    assert game.hands.equips == []


def test_the_hand_puts_away_an_item_that_ran_out():
    game = wheel_game(held=BATTERY)
    game.state.spare_batteries = 0
    step(game)
    assert game.hands.held == FLASHLIGHT and game.hands.equips == [FLASHLIGHT]
    game = wheel_game(held=BATTERY)
    game.state.spare_batteries = 0
    game.hands.busy = True
    step(game)
    assert game.hands.equips == [], "enquanto a mão anima, o item não é recolhido à força"
    game.hands.busy = False
    step(game)
    assert game.hands.equips == [FLASHLIGHT]


def test_new_game_and_checkpoint_reset_the_wheel():
    game = wheel_game()
    hold(game)
    hold(game, *vector(144, 0.2))
    game.hands.busy = True
    release(game)
    hold(game)
    assert game.inventory.wheel_open
    game.save_checkpoint()
    game.restart_from_checkpoint()
    inv = game.inventory
    assert not inv.wheel_open and inv.selection is None and inv.hud_block()["pending"] is None
    assert inv.hud_block()["fresh"] == (), "o que já era do jogador no checkpoint não é novidade"
    game.new_game(skip_intro=True)
    assert inv.owned() == () and inv.hud_block()["fresh"] == ()


def test_with_nothing_to_choose_the_key_does_not_trap_the_camera():
    game = start_playing(make_game(world=True))
    assert game.inventory.owned() == ()
    ctl = Controls()
    ctl.key("Q", "PRESS")
    ctl.mouse(100, 0)
    yaw = game.player.yaw
    game.tick(DT, ctl.inp)
    assert not game.inventory.wheel_open and sounds(game) == []
    assert abs((yaw - game.player.yaw) - 100 * controls.MOUSE_SENSITIVITY) < 1e-6, "o mouse continuou girando a câmera"


# --------------------------------------------------------------------------
# Controls e Game
# --------------------------------------------------------------------------
def test_controls_route_the_mouse_to_the_wheel_while_q_or_tab_is_held():
    for key in ("Q", "TAB"):
        ctl = Controls()
        assert ctl.key(key, "PRESS") is True and ctl.inp.wheel_held
        ctl.mouse(100, 40)
        assert abs(ctl.inp.wheel_dx - 100 * controls.MOUSE_SENSITIVITY) < 1e-9
        assert abs(ctl.inp.wheel_dy - 40 * controls.MOUSE_SENSITIVITY) < 1e-9
        assert ctl.inp.look_dx == 0.0 and ctl.inp.look_dy == 0.0
        ctl.key(key, "RELEASE")
        assert not ctl.inp.wheel_held
        ctl.mouse(10, 10)
        assert ctl.inp.look_dx > 0 and ctl.inp.look_dy > 0, "solta a tecla: o mouse volta a olhar"
    both = Controls()
    both.key("Q", "PRESS")
    both.key("TAB", "PRESS")
    both.key("Q", "RELEASE")
    assert both.inp.wheel_held, "enquanto uma das duas teclas estiver apertada a roda continua"
    both.reset()
    assert not both.inp.wheel_held


def test_wheel_does_not_react_to_key_repeat_or_pause_the_world():
    ctl = Controls()
    ctl.key("Q", "PRESS")
    ctl.key("Q", "PRESS", is_repeat=True)
    ctl.key("W", "PRESS")
    game = wheel_game()
    start = game.player.feet
    for _ in range(30):
        game.tick(DT, ctl.inp)
        ctl.inp.clear_edges()
    assert game.inventory.wheel_open and game.player.feet != start, "o mundo e o jogador continuam"
    assert game.phase == "play"


def test_game_freezes_the_camera_while_the_wheel_is_open_and_selects_through_controls():
    game = wheel_game()
    ctl = Controls()
    ctl.key("Q", "PRESS")
    game.tick(DT, ctl.inp)
    ctl.inp.clear_edges()
    yaw, pitch = game.player.yaw, game.player.pitch
    ctl.mouse(0, 100)                                     # para cima: setor do topo (lanterna), a que já está na mão
    ctl.mouse(100, 0)                                     # mais à direita: o ponteiro acumulado vai para as pilhas
    ctl.mouse(100, 0)
    game.tick(DT, ctl.inp)
    ctl.inp.clear_edges()
    assert game.player.yaw == yaw and game.player.pitch == pitch
    assert game.inventory.selection == BATTERY
    ctl.key("Q", "RELEASE")
    game.tick(DT, ctl.inp)
    ctl.inp.clear_edges()
    assert game.hands.equips == [BATTERY]
    ctl.mouse(100, 0)
    game.tick(DT, ctl.inp)
    assert game.player.yaw != yaw, "a câmera volta a girar depois da roda"


def test_wheel_drives_the_real_hands_and_a_busy_swap_defers_the_choice():
    game = start_playing(make_game(world=True))
    state = game.state
    state.has_flashlight, state.has_key, state.has_map, state.spare_batteries = True, True, True, 1
    state.battery = 0.2
    game.inventory.reset()
    assert game.inventory.held == FLASHLIGHT, "lanterna na direita, esquerda livre"
    hold(game)
    hold(game, *vector(144, 0.2))
    release(game)
    fk.run_for(game, 3.0)
    assert game.hands.held == KEY and not game.hands.busy
    step(game, InputState(reload=True))                   # a troca de pilha ocupa as duas mãos
    fk.run_for(game, 0.4)
    assert game.hands.busy
    hold(game)
    hold(game, *vector(216, 0.2))
    release(game)
    assert game.inventory.hud_block()["pending"] == MAP and game.hands.held != MAP
    fk.run_for(game, 4.0)
    assert game.hands.held == MAP and game.inventory.hud_block()["pending"] is None
    assert state.spare_batteries == 0 and state.battery > 0.9, "a troca terminou antes do mapa chegar à mão"


def test_hud_block_is_stable_without_the_wheel():
    game = wheel_game(owned=(FLASHLIGHT, KEY), held=KEY)
    block = game.inventory.hud_block()
    assert not block["open"] and block["selection"] is None and block["owned"] == (FLASHLIGHT, KEY)
    assert block["held"] == KEY and block["counts"][KEY] == 1 and block["pointer"] == (0.0, 0.0)
    game.hands.held = MAP                                 # segurando algo que o jogador não tem: não aparece como na mão
    assert game.inventory.hud_block()["held"] is None


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok      {name}", flush=True)
        except Exception as error:      # noqa: BLE001
            import traceback
            failures += 1
            print(f"FALHOU  {name}: {error!r}", flush=True)
            traceback.print_exc()
    print(f"{len(tests) - failures}/{len(tests)} testes de inventário passaram")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
