"""Cutscenes de SEM ALVORADA (contrato 5.4).

    cutscenes.build(ctx)              cria CutsceneCam e os objetos só de cutscene (coleção SA_Cutscene)
    cutscenes.CutscenePlayer(host)    play / update / active / skip / overlay
    cutscenes.Overlay                 o que o HUD desenha por cima do jogo

O roteiro fica em `scripts.py` (dados), a interpolação e a execução em `player.py`.
"""
from .player import CutscenePlayer, Overlay
from .scripts import NAMES


def build(ctx):
    from . import objects
    objects.create_all(ctx)


__all__ = ["build", "CutscenePlayer", "Overlay", "NAMES"]
