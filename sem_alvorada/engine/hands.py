"""As mãos do jogador: pegar, segurar e usar itens, com animação.

Versão mínima que mantém o jogo completável (tudo acontece no mesmo quadro, sem animação) até o agente
de animações de item entregar a definitiva. O contrato completo está em `docs/FASE3.md`.
"""
from .. import conventions as C


class Hands:
    def __init__(self, game):
        self.game = game
        self.held = None             # tipo do item na mão (C.ITEM_*) ou None
        self.busy = False            # uma animação sem interrupção está em curso: não aceita pegar nem trocar
        self.reading = False

    def update(self, dt, bob):
        """Todo quadro de jogo. `bob` é (lateral, vertical) do head bob em metros."""

    def reset(self):
        self.held = None
        self.busy = False
        self.reading = False

    # ---- pegar ----
    def pickup(self, target, on_contact, on_done=None):
        """Estende a mão até o `Interactable`. `on_contact()` roda quando os dedos tocam o item (é ali que o
        inventário muda); `on_done()` roda quando a mão volta ao repouso. Devolve False se não puder começar."""
        if self.busy:
            return False
        on_contact()
        if on_done is not None:
            on_done()
        return True

    # ---- segurar ----
    def equip(self, kind, on_done=None):
        """Coloca `kind` na mão (None abaixa tudo). Devolve False se não puder começar."""
        if self.busy:
            return False
        self.held = kind
        if on_done is not None:
            on_done()
        return True

    # ---- lanterna ----
    def toggle_flashlight(self):
        self.game.flashlight.toggle()

    def reload_flashlight(self):
        self.game.flashlight.reload()

    # ---- leitura ----
    def begin_read(self, note_id, on_open):
        """Levanta o papel até o rosto e então chama `on_open()` (que abre o leitor)."""
        on_open()

    def end_read(self):
        """O leitor fechou: abaixa o papel."""
