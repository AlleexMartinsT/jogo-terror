"""Inicia o jogo na GUI. Como o script pode rodar antes de a janela existir, a partida é agendada por timer."""
import functools
import traceback

import bpy

from . import operator as play_operator
from .windowing import find_view3d

FIRST_DELAY = 0.8
RETRY_DELAY = 0.5
MAX_ATTEMPTS = 40


def _try_launch(options, attempts):
    """Chamado pelo timer: acha um editor 3D e inicia `sa.play`; tenta de novo enquanto a janela não existe."""
    found = find_view3d(bpy.context.window_manager)
    if found is None:
        attempts[0] += 1
        if attempts[0] >= MAX_ATTEMPTS:
            print("[engine] nenhum editor 3D encontrado; abra um e rode `bpy.ops.sa.play()`", flush=True)
            return None
        return RETRY_DELAY
    window, area, region = found
    try:
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.sa.play("INVOKE_DEFAULT", **options)
    except Exception:      # noqa: BLE001 - o timer não pode morrer com traceback mudo
        traceback.print_exc()
    return None


def start(quality="medium", skip_intro=False, debug=False):
    """Registra o operador e agenda a partida. Devolve False em modo background (sem janela)."""
    play_operator.register()
    if bpy.app.background:
        print("[engine] modo background: não há janela para jogar (use tests/sim_playthrough.py)", flush=True)
        return False
    options = {"quality": quality, "skip_intro": skip_intro, "debug": debug}
    bpy.app.timers.register(functools.partial(_try_launch, options, [0]), first_interval=FIRST_DELAY,
                            persistent=True)
    return True
