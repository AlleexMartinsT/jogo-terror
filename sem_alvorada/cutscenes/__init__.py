"""Cutscenes de SEM ALVORADA (contrato 5.4, ampliado na fase 3).

    cutscenes.build(ctx)              cria CutsceneCam e os objetos só de cutscene (coleção SA_Cutscene)
    cutscenes.CutscenePlayer(host)    play / update / active / skip / overlay
    cutscenes.Overlay                 o que o HUD desenha por cima do jogo

Roteiro: `scripts.py` (registro e plano de batidas) e `scene_*.py` (uma cena por arquivo), só dados.
Câmera: `curves` (splines, curvas, osciladores), `camera` (plano contínuo, mão do operador, pancadas, foco).
Animação de objetos: `anim` (cortinas, poeira, carro, pêndulos, portão, luzes). Corpo e mãos: `body_actor`.
Execução: `player` (relógio, ações, câmera) e `stage` (ponte com o anfitrião e restauração do que foi mexido).
"""
from .player import CutscenePlayer, Overlay
from .scripts import NAMES


def build(ctx):
    from . import objects
    objects.create_all(ctx)


__all__ = ["build", "CutscenePlayer", "Overlay", "NAMES"]
