"""Entrada do jogador em um quadro, já traduzida das teclas e do mouse."""
from dataclasses import dataclass


@dataclass
class InputState:
    """`move_*` e `run`/`crouch` são níveis (enquanto a tecla está apertada).

    `look_*` são radianos acumulados desde o último tick (dx>0: mouse à direita,
    dy>0: mouse para cima). Os demais são *edges*: valem por um único tick.
    """
    move_x: float = 0.0
    move_y: float = 0.0
    look_dx: float = 0.0
    look_dy: float = 0.0
    run: bool = False
    crouch: bool = False
    interact: bool = False
    flashlight: bool = False
    reload: bool = False
    pause: bool = False
    confirm: bool = False
    skip: bool = False
    cancel: bool = False

    def clear_edges(self):
        """Zera o que só vale por um quadro; o operador chama depois de cada tick."""
        self.look_dx = self.look_dy = 0.0
        self.interact = self.flashlight = self.reload = False
        self.pause = self.confirm = self.skip = self.cancel = False
