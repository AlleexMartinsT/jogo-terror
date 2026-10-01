"""Palco: a ponte entre as ações das cutscenes e o anfitrião (`host`) do engine.

Toda chamada ao host passa por aqui. Erros em chamadas cosméticas (um som que falta, um objeto que
não existe) são registrados em `errors` e NÃO derrubam a cutscene: o jogo continua e o teste pega.
"""
from dataclasses import dataclass

from .. import conventions as C

# Objetos que só existem para cutscenes (criados por `cutscenes.build`)
HEADLIGHT_ENERGY = 3500.0


@dataclass(frozen=True)
class PlayerSnapshot:
    """Onde o jogador estava quando a cutscene começou."""
    x: float
    y: float
    z: float
    yaw: float
    eye_z: float

    @property
    def eye(self):
        return (self.x, self.y, self.eye_z)

    def ahead(self, distance, height=None):
        """Ponto à frente do jogador, na altura dos olhos (ou `height`)."""
        dx, dy = C.yaw_dir(self.yaw)
        return (self.x + dx * distance, self.y + dy * distance, self.eye_z if height is None else height)


class Stage:
    def __init__(self, host):
        self.host = host
        self.errors = []
        self.player = self._snapshot()
        self.moved = {}                   # objeto -> deslocamento (dx, dy, dz) aplicado pelas Tracks
        self._loops = set()
        self._lit = set()                 # luzes CutLight_* que esta cutscene acendeu
        self._head_limit = None           # (valor original) se a entidade foi erguida por esta cutscene
        self._dawn_used = False
        self._visibility = {}             # objeto -> (hide_viewport, hide_render) originais, devolvidos no fim

    def _snapshot(self):
        try:
            x, y, z, yaw, eye_z = self.host.player_state()
        except Exception as exc:          # noqa: BLE001 - um host sem jogador ainda deixa a cutscene rodar
            self.errors.append(f"player_state: {exc}")
            x, y, z, yaw, eye_z = 0.0, 0.0, 0.0, 0.0, C.PLAYER_EYE_STAND
        return PlayerSnapshot(x, y, z, yaw, eye_z)

    def safe(self, label, fn, *args, **kwargs):
        """Chama o host; se falhar, anota e segue."""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:          # noqa: BLE001
            self.errors.append(f"{label}: {exc!r}")
            return None

    def resolve(self, value):
        return value(self) if callable(value) else value

    # ---------------------------------------------------------------- objetos
    def obj(self, name):
        return self.safe(f"get_object({name})", self.host.get_object, name)

    def offset(self, name):
        return self.moved.get(name, (0.0, 0.0, 0.0))

    # ---------------------------------------------------------------- som
    def sound(self, name, pos=None, volume=1.0, pitch=1.0):
        self.safe(f"audio.play({name})", self.host.audio.play, name, pos=pos, volume=volume, pitch=pitch)

    def loop(self, key, name, volume=1.0, pos=None):
        audio = self.host.audio
        if hasattr(audio, "loop"):
            self.safe(f"audio.loop({name})", audio.loop, key, name, pos=pos, volume=volume)
            self._loops.add(key)
        else:
            self.sound(name, pos=pos, volume=volume)

    def stop_loop(self, key):
        if key in self._loops and hasattr(self.host.audio, "stop"):
            self.safe(f"audio.stop({key})", self.host.audio.stop, key)
        self._loops.discard(key)

    def stop_all_loops(self):
        for key in list(self._loops):
            self.stop_loop(key)

    # ---------------------------------------------------------------- luzes só de cutscene
    def set_light(self, name, energy):
        """Liga/desliga uma luz `CutLight_*` (desligada = oculta, para não pesar no orçamento de luzes)."""
        obj = self.obj(name)
        if obj is None:
            return
        on = energy > 0.0
        obj.hide_viewport = obj.hide_render = not on
        obj.data.energy = max(0.0, energy)
        (self._lit.add if on else self._lit.discard)(name)

    def headlights(self, on):
        """Liga/desliga os faróis do carro (módulo props). Ligados usam `sa_base_energy` se existir."""
        for name in ("Car_Headlight_L", "Car_Headlight_R"):
            obj = self.obj(name)
            if obj is None or not hasattr(getattr(obj, "data", None), "energy"):
                continue
            obj.hide_viewport = obj.hide_render = not on
            obj.data.energy = float(obj.get("sa_base_energy", HEADLIGHT_ENERGY)) if on else 0.0

    def set_visible(self, name, visible):
        obj = self.obj(name)
        if obj is not None:
            self.set_hidden(obj, not visible)

    def set_hidden(self, obj, hidden):
        """Mostra/esconde `obj` lembrando como ele estava, para devolver ao terminar a cutscene."""
        self._visibility.setdefault(obj, (obj.hide_viewport, obj.hide_render))
        obj.hide_viewport = obj.hide_render = hidden

    # ---------------------------------------------------------------- entidade
    @property
    def entity(self):
        return self.host.entity

    def set_dawn(self, amount):
        """Clareia o céu (halo do Sol Negro e horizonte) via `world.sky.set_dawn`; ignora se não houver mundo."""
        if getattr(self.host.scene, "world", None) is None:
            return
        from ..world import sky
        self.safe("sky.set_dawn", sky.set_dawn, self.host.scene, amount)
        self._dawn_used = amount > 0.0

    def stand_tall(self, entity):
        """Tira o limite de altura da cabeça (a rig curva a entidade sob o forro); `finish_up` devolve."""
        if hasattr(entity, "head_limit") and self._head_limit is None:
            self._head_limit = (entity.head_limit,)
            entity.head_limit = None

    def entity_head(self):
        return tuple(self.entity.head_position())

    def finish_up(self):
        """Ao terminar (ou pular): solta os loops e apaga as luzes de cutscene. A câmera volta em `player.py`."""
        self.stop_all_loops()
        for name in list(self._lit):
            self.set_light(name, 0.0)
        for obj, (hide_viewport, hide_render) in self._visibility.items():
            obj.hide_viewport, obj.hide_render = hide_viewport, hide_render
        self._visibility.clear()
        if self._dawn_used:
            self.set_dawn(0.0)
        if self._head_limit is not None:
            self.entity.head_limit = self._head_limit[0]
            self._head_limit = None
