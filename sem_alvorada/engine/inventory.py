"""Inventário e roda de itens.

Cinco tipos seguráveis, um por setor da roda, em sentido horário a partir do topo: lanterna, pilhas, chave,
mapa e anotações. O jogador segura Q ou Tab, move o mouse na direção do setor e solta; a roda então pede
à `Hands` que ponha aquele item na mão esquerda. O mundo não pausa e o mouse não gira a câmera enquanto a
roda está aberta. O contrato com as mãos e com o HUD está em `docs/FASE3.md`.

A direção vem do vetor do mouse ACUMULADO desde que a roda abriu (e não do movimento de cada quadro), por
isso um movimento lento também escolhe: o que importa é para onde o ponteiro virtual está.
"""
import math

from .. import conventions as C

SLOTS = (C.ITEM_FLASHLIGHT, C.ITEM_BATTERY, C.ITEM_KEY, C.ITEM_MAP, C.ITEM_NOTE)
MAX_SLOTS = len(SLOTS)
SECTOR_WIDTH = math.tau / MAX_SLOTS
DEAD_ZONE = 0.06          # rad de mouse acumulado: dentro disso nenhum setor é escolhido
POINTER_RADIUS = 0.30     # o vetor acumulado não passa daqui; quem foi longe demais volta em poucos pixels
PENDING_SECONDS = 3.2     # quanto tempo um pedido de troca espera a mão ficar livre antes de ser esquecido (a troca de pilhas leva ~2,5 s)


def sector_at(dx, dy):
    """Índice do setor (0 = topo, sentido horário) para o vetor do mouse; None dentro da zona morta.

    `dx` > 0 é o mouse à direita e `dy` > 0 é o mouse para cima, como em `InputState`."""
    if math.hypot(dx, dy) < DEAD_ZONE:
        return None
    angle = math.atan2(dx, dy) % math.tau
    return int((angle + SECTOR_WIDTH / 2) // SECTOR_WIDTH) % MAX_SLOTS


class Inventory:
    def __init__(self, game):
        self.game = game
        self.wheel_open = False
        self.selection = None          # tipo do setor destacado enquanto a roda está aberta
        self._pointer = (0.0, 0.0)     # vetor acumulado do mouse desde a abertura
        self._pending = None           # troca que a mão ocupada recusou; tenta de novo quando liberar
        self._pending_left = 0.0
        self._seen = set()             # tipos que a roda já mostrou ao jogador (para o ponto de novidade)

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
        """Abre e fecha a roda, escolhe o setor e pede à `Hands` que troque o item. Só roda na fase de jogo."""
        self._retry_pending(dt)
        self._put_away_vanished_item()
        if not self.wheel_open and inp.wheel_held:
            if self.owned():
                self._open()
            else:
                # sem nada para escolher a tecla não pode travar a câmera: devolve o mouse ao olhar
                inp.look_dx += inp.wheel_dx
                inp.look_dy += inp.wheel_dy
        if self.wheel_open:
            self._move_pointer(inp.wheel_dx, inp.wheel_dy)
            if not inp.wheel_held:
                self._release()

    def cancel(self):
        """Fecha a roda sem equipar nada (pausa, leitura, cutscene, morte) e esquece pedidos pendentes."""
        self._pending = None
        if self.wheel_open:
            self._close()

    def on_collected(self, kind):
        """Um item entrou no inventário (depois da animação de pegar). Não abre a roda: só deixa o setor
        marcado como novidade até o jogador vê-lo na próxima vez que a abrir."""
        self._seen.discard(kind)

    def reset(self):
        """Novo jogo ou checkpoint: o `GameState` já foi restaurado, então o que há nele não é novidade."""
        self.wheel_open = False
        self.selection = None
        self._pointer = (0.0, 0.0)
        self._pending = None
        self._seen = set(self.owned())

    # ---- roda ----
    def _open(self):
        self.wheel_open = True
        self.selection = None
        self._pointer = (0.0, 0.0)
        self.game.sound("ui_wheel_open")

    def _close(self):
        self.wheel_open = False
        self.selection = None
        self._seen.update(self.owned())
        self.game.sound("ui_wheel_close")

    def _move_pointer(self, dx, dy):
        x, y = self._pointer[0] + dx, self._pointer[1] + dy
        length = math.hypot(x, y)
        if length > POINTER_RADIUS:
            x, y = x * POINTER_RADIUS / length, y * POINTER_RADIUS / length
        self._pointer = (x, y)
        chosen = self._kind_under_pointer()
        if chosen is not None and chosen != self.selection:
            self.game.sound("ui_wheel_tick", None, 0.6)
        self.selection = chosen

    def _kind_under_pointer(self):
        index = sector_at(*self._pointer)
        if index is None or SLOTS[index] not in self.owned():
            return None             # zona morta ou setor apagado: soltar mantém o que está na mão
        return SLOTS[index]

    def _release(self):
        chosen = self.selection
        self._close()
        if chosen is not None and chosen != self.held:
            self._request(chosen)

    # ---- troca de item na mão ----
    def _request(self, kind):
        """A mão ocupada recusa a troca. O pedido mais recente espera até PENDING_SECONDS; os antigos caem."""
        if self.game.hands.equip(kind):
            self._pending = None
        else:
            self._pending, self._pending_left = kind, PENDING_SECONDS

    def _retry_pending(self, dt):
        if self._pending is None:
            return
        self._pending_left -= dt
        if self._pending_left <= 0 or self._pending not in self.owned() or self._pending == self.held:
            self._pending = None
        elif self.game.hands.equip(self._pending):
            self._pending = None

    def _put_away_vanished_item(self):
        """O item na mão acabou (a última pilha foi para a lanterna): a mão volta à lanterna, ou fica vazia."""
        held = self.held
        if held is None or held in self.owned() or self.game.hands.busy:
            return
        self.game.hands.equip(C.ITEM_FLASHLIGHT if self.game.state.has_flashlight else None)

    # ---- HUD ----
    def hud_block(self):
        owned = self.owned()
        held = self.held
        return {"open": self.wheel_open, "selection": self.selection, "owned": owned,
                "held": held if held in owned else None,
                "counts": {kind: self.count(kind) for kind in SLOTS},
                "fresh": tuple(kind for kind in owned if kind not in self._seen),
                "pointer": (self._pointer[0] / POINTER_RADIUS, self._pointer[1] / POINTER_RADIUS),
                "pending": self._pending}
