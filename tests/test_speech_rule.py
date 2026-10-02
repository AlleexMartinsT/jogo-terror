"""A regra de fala do personagem (docs/FASE3.md): `Game.say` só ao começar a partida e ao pegar um item principal
(mais "tenho tudo" quando o último chega). Porta trancada, lanterna sem carga, sem pilha, janela, carro trancado,
respawn e dicas de controle são estado visual, nunca fala.

Duas provas: uma partida simulada que intercepta `Game.say` e uma auditoria do código-fonte que lista toda
chamada de `.say(` e rejeita as que não sejam as três permitidas.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_speech_rule.py
"""
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_engine_fakes as fk  # noqa: E402
from test_engine_fakes import InputState, game_with_fake_entity, run_for, step, teleport  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout, story  # noqa: E402
from sem_alvorada.engine.interact import Interactable  # noqa: E402
from sem_alvorada.engine.state import FLAG_BLACKOUT  # noqa: E402

PACKAGE = os.path.join(fk.ROOT, "sem_alvorada")
ALLOWED_TEXTS = {story.OPENING_LINE, story.COLLECT_DONE, *story.PICKED.values()}
# As únicas expressões aceitas como primeiro argumento de `.say(`, por arquivo.
ALLOWED_SAY_ARGUMENTS = {
    "engine/director.py": {"story.OPENING_LINE", "story.COLLECT_DONE"},
    "engine/interact.py": {"story.PICKED[item]"},
}


def record_speech(game):
    spoken = []
    original = game.say

    def recorder(text, seconds=3.5):
        spoken.append(text)
        original(text, seconds)

    game.say = recorder
    return spoken


def take(game, ref):
    """Pega o item `ref` pelo caminho normal (interact -> mãos -> coleta) e espera as mãos terminarem."""
    target = next(t for t in game.interact.targets if t.ref == ref)
    game.interact.use(target)
    for _ in range(int(4.0 / fk.DT)):
        if ref in game.state.collected and not game.hands.busy:
            return
        step(game)
    raise AssertionError(f"{ref} não foi coletado")


def start_story_game():
    game, brain, rig, cutscenes = game_with_fake_entity(hunts=False, items=True)
    spoken = record_speech(game)
    step(game)
    step(game, InputState(confirm=True))
    assert game.phase == "cutscene"
    run_for(game, 1.5)
    assert game.phase == "play"
    return game, brain, spoken


def test_the_character_speaks_when_the_game_starts_and_when_picking_main_items_only():
    game, brain, spoken = start_story_game()
    assert spoken == [story.OPENING_LINE]

    # sem lanterna: teclas de lanterna, hall escuro, janela e carro trancado não falam
    step(game, InputState(flashlight=True))
    step(game, InputState(reload=True))
    hall = layout.ROOMS["hall_u"].rect.center
    teleport(game, hall[0], hall[1], 2.8, 0)
    run_for(game, 0.5)
    game.interact.use(Interactable("look", "window_x", position=(0.0, 0.0, 1.5)))
    game.interact.use(next(t for t in game.interact.targets if t.kind == "car"))
    for door_id, door in game.doors.doors.items():
        if door.lock:
            game.interact.use(Interactable("door", door_id))
    run_for(game, 0.5)
    assert spoken == [story.OPENING_LINE], spoken

    # itens principais: uma fala cada, e "tenho tudo" quando o último chega
    take(game, "FLASHLIGHT")
    assert spoken[-1] == story.PICKED[C.ITEM_FLASHLIGHT]
    take(game, "KEY")
    take(game, "MAP")
    assert spoken[-1] == story.PICKED[C.ITEM_MAP]
    take(game, "BATTERY_1")
    take(game, "BATTERY_2")
    assert spoken[-1] == story.PICKED[C.ITEM_BATTERY]
    before = len(spoken)
    take(game, "BATTERY_3")
    assert spoken[before:] == [story.PICKED[C.ITEM_BATTERY], story.COLLECT_DONE]
    assert game.message_text == story.COLLECT_DONE, "a última fala é a que o jogador lê"
    take(game, "BATTERY_4")
    assert spoken[-1] == story.PICKED[C.ITEM_BATTERY], "cada pilha reserva tem a sua fala"
    quiet = len(spoken)

    # a partir daqui tudo é estado visual
    game.state.flags.add(FLAG_BLACKOUT)
    state = game.state
    state.battery, state.flashlight_on = 0.003, True                  # a lanterna morre sozinha
    run_for(game, 2.0)
    assert not state.flashlight_on and state.battery == 0.0
    step(game, InputState(flashlight=True))                           # F sem carga
    state.spare_batteries = 0
    step(game, InputState(reload=True))                               # R sem pilha reserva
    run_for(game, 1.6)                                                # a mão termina o gesto de recusa
    state.spare_batteries, state.battery = 2, 0.95
    step(game, InputState(reload=True))                               # R com a pilha ainda boa
    run_for(game, 1.6)
    state.battery = 0.1
    step(game, InputState(reload=True))                               # R de verdade: troca
    run_for(game, 4.0)
    assert state.battery > 0.95 and state.flashlight_on and state.spare_batteries == 1
    game.interact.use(Interactable("look", "window_x", position=(0.0, 0.0, 1.5)))
    for door_id, door in game.doors.doors.items():
        if door.lock == "front":
            game.interact.use(Interactable("door", door_id))
    for note in ("NOTE_1", "NOTE_2"):
        game.interact.use(next(t for t in game.interact.targets if t.ref == note))
        run_for(game, 1.5)
        assert game.phase == "reading"
        step(game, InputState(interact=True))
        run_for(game, 0.5)
    game.debug_cheat("give_all")
    run_for(game, 0.5)
    assert spoken[quiet:] == [], spoken[quiet:]

    # destrancar a garagem, entrar no carro, morrer e voltar: nada de fala
    game.director.unlock_garage()
    run_for(game, 1.5)
    game.interact.use(next(t for t in game.interact.targets if t.kind == "car"))
    run_for(game, 1.5)
    assert game.phase == "credits"
    assert spoken[quiet:] == [], spoken[quiet:]
    assert set(spoken) <= ALLOWED_TEXTS


def test_respawn_after_death_is_silent():
    game, brain, spoken = start_story_game()
    take(game, "FLASHLIGHT")
    game.state.flags.add(FLAG_BLACKOUT)
    teleport(game, 2.5, 8.0, 0.0, 0)
    game.save_checkpoint()
    count = len(spoken)
    game.phase = "dead"
    game.state.deaths = 1
    step(game)                                  # a tela de morte fica um tempo; o HUD só vê a volta depois dela
    step(game, InputState(confirm=True))
    assert game.phase == "play" and game.hud_model()["fade_in"] > 0.9
    run_for(game, 1.0)
    assert len(spoken) == count and game.message_text in ("", story.PICKED[C.ITEM_FLASHLIGHT])
    assert game.message_text != story.OPENING_LINE


def test_every_say_call_in_the_source_is_one_of_the_allowed_three():
    found = []
    for folder, _dirs, files in os.walk(PACKAGE):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            relative = os.path.relpath(path, PACKAGE).replace(os.sep, "/")
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "say":
                    argument = ast.unparse(node.args[0]) if node.args else ""
                    found.append((relative, node.lineno, argument))
    assert found, "a auditoria não achou nenhuma chamada: o filtro quebrou"
    for relative, line, argument in found:
        allowed = ALLOWED_SAY_ARGUMENTS.get(relative, set())
        assert argument in allowed, f"{relative}:{line} fala {argument!r}; o personagem só fala ao começar e ao pegar item principal"
    files_with_say = {relative for relative, _line, _argument in found}
    assert files_with_say == set(ALLOWED_SAY_ARGUMENTS), files_with_say


def test_texts_of_old_spoken_states_became_prompts():
    for lock in ("front", "back", "garage"):
        assert story.PROMPT_LOCKED[lock] and story.PROMPT_LOCKED[lock] != story.PROMPT_OPEN
    assert story.PROMPT_CAR_LOCKED and story.PROMPT_LOOK
    for name in ("LOCKED_MSGS", "NOTHING_OUTSIDE", "GARAGE_UNLOCKED"):
        assert not hasattr(story, name), f"story.{name} voltou: era fala e virou dica de interação"


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
    print(f"{len(tests) - failures}/{len(tests)} testes da regra de fala passaram")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
