"""Tradução de teclas e mouse em InputState. Não depende de bpy: dá para testar com eventos falsos."""
from .inputstate import InputState

MOUSE_SENSITIVITY = 0.0022        # radianos por pixel

MOVE_KEYS = {"W": (0, 1), "UP_ARROW": (0, 1), "S": (0, -1), "DOWN_ARROW": (0, -1),
             "A": (-1, 0), "LEFT_ARROW": (-1, 0), "D": (1, 0), "RIGHT_ARROW": (1, 0)}
RUN_KEYS = frozenset({"LEFT_SHIFT", "RIGHT_SHIFT"})
CROUCH_KEYS = frozenset({"C", "LEFT_CTRL", "RIGHT_CTRL"})
WHEEL_KEYS = frozenset({"Q", "TAB"})
EDGE_KEYS = {"E": ("interact",), "F": ("flashlight",), "R": ("reload",), "ESC": ("pause", "cancel"),
             "RET": ("confirm",), "NUMPAD_ENTER": ("confirm",), "SPACE": ("skip", "confirm"),
             "LEFTMOUSE": ("interact", "confirm")}
DEBUG_KEYS = {"F1": "give_all", "F2": "to_garage", "F3": "entity_off", "F4": "blackout"}


class Controls:
    def __init__(self, debug=False):
        self.inp = InputState()
        self.debug = debug
        self.debug_requests = []
        self._down = set()

    def reset(self):
        """Solta todas as teclas (pausa, perda de foco): evita o personagem andar sozinho."""
        self._down.clear()
        self._refresh_levels()

    def key(self, key_type, value, is_repeat=False):
        """Um evento de teclado ou botão. Devolve True se a tecla é do jogo (o evento deve ser consumido)."""
        if value == "PRESS" and not is_repeat:
            self._down.add(key_type)
            for name in EDGE_KEYS.get(key_type, ()):
                setattr(self.inp, name, True)
            if self.debug and key_type in DEBUG_KEYS:
                self.debug_requests.append(DEBUG_KEYS[key_type])
        elif value == "RELEASE":
            self._down.discard(key_type)
        self._refresh_levels()
        return (key_type in MOVE_KEYS or key_type in EDGE_KEYS or key_type in RUN_KEYS
                or key_type in CROUCH_KEYS or key_type in WHEEL_KEYS)

    def mouse(self, dx_pixels, dy_pixels):
        # Com a roda de itens aberta o mouse escolhe o setor em vez de girar a câmera.
        if self.inp.wheel_held:
            self.inp.wheel_dx += dx_pixels * MOUSE_SENSITIVITY
            self.inp.wheel_dy += dy_pixels * MOUSE_SENSITIVITY
            return
        self.inp.look_dx += dx_pixels * MOUSE_SENSITIVITY
        self.inp.look_dy += dy_pixels * MOUSE_SENSITIVITY

    def _refresh_levels(self):
        x = sum(vec[0] for key, vec in MOVE_KEYS.items() if key in self._down)
        y = sum(vec[1] for key, vec in MOVE_KEYS.items() if key in self._down)
        self.inp.move_x = max(-1.0, min(1.0, float(x)))
        self.inp.move_y = max(-1.0, min(1.0, float(y)))
        self.inp.run = bool(self._down & RUN_KEYS)
        self.inp.crouch = bool(self._down & CROUCH_KEYS)
        self.inp.wheel_held = bool(self._down & WHEEL_KEYS)

    def take_debug_requests(self):
        requests, self.debug_requests = self.debug_requests, []
        return requests
