"""Módulo engine: jogador, lanterna, interação, portas, luzes, HUD e o operador modal.

O núcleo (`game.Game`) roda sem janela. A interface fica em `hud`, `screens`, `operator` e `launcher`,
que só são importados quando o jogo é iniciado na GUI.
"""


def build(ctx):
    """Etapa de build: câmera do jogador, lanterna, viewmodel, LEIA-ME e jogar.py."""
    from . import builder
    builder.build(ctx)
