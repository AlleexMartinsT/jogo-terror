"""Inventário e roda de itens.

Cinco tipos seguráveis, um por setor da roda: lanterna, pilhas, chave, mapa e anotações. O jogador
segura a tecla da roda (Q ou Tab), move o mouse na direção do setor e solta. O que está em jogo vale
`docs/FASE3.md`; esta é a versão mínima que mantém o jogo completável até o agente de HUD e
inventário entregar a definitiva.
"""
from .. import conventions as C

SLOTS = (C.ITEM_FLASHLIGHT, C.ITEM_BATTERY, C.ITEM_KEY, C.ITEM_MAP, C.ITEM_NOTE)
MAX_SLOTS = len(SLOTS)


class Inventory:
    def __init__(self, game):
        self.game = game
        self.wheel_open = False
        self.selection = None          # tipo do setor destacado enquanto a roda está aberta

    # ---- consultas ----
    def owned(self):
        """Tipos que o jogador possui agora, na ordem de SLOTS."""
        state = self.game.state
        have = {C.ITEM_FLASHLIGHT: state.has_flashlight, C.ITEM_BATTERY: state.spare_batteries > 0,
                C.ITEM_KEY: state.has_key, C.ITEM_MAP: state.has_map, C.ITEM_NOTE: bool(state.notes_read)}
        return tuple(kind for kind in SLOTS if have[kind])

    def count(self, kind):
        state = self.game.state
        return {C.ITEM_BATTERY: state.spare_batteries, C.ITEM_NOTE: len(state.notes_read)}.get(
            kind, int(kind in self.owned()))

    @property
    def held(self):
        return self.game.hands.held

    # ---- quadro a quadro ----
    def update(self, dt, inp):
        """Abre e fecha a roda, escolhe o setor e pede à `Hands` que troque o item. Versão mínima: não faz nada."""

    def on_collected(self, kind):
        """Chamado quando um item entra no inventário (depois da animação de pegar)."""

    def reset(self):
        self.wheel_open = False
        self.selection = None

    def hud_block(self):
        return {"open": self.wheel_open, "selection": self.selection, "owned": self.owned(), "held": self.held}
