"""A entidade em tempo de execução: cérebro (ai) + corpo (entity) + o som que ela faz.

Se `ai.brain` ou `entity.rig` não existirem (ou falharem ao iniciar), a entidade fica
dormente e o resto do jogo funciona.
"""
import importlib
import math
import random
from dataclasses import dataclass

from .. import conventions as C
from .. import layout

EYE_LEVEL = {"dormant": 0.0, "patrol": 0.55, "investigate": 0.7, "stalk": 0.85,
             "chase": 1.0, "search": 0.7, "attack": 1.0}
STRIDE_BY_STATE = {"chase": 1.6, "attack": 1.6, "stalk": 0.9}
STRIDE_DEFAULT = 1.1
STEP_KIND_BY_STATE = {"chase": "step_chase", "attack": "step_chase", "stalk": "step_stalk"}
GROWL_COOLDOWN = 5.0
BREATH_RANGE = 7.0
DANGER_RANGE = 14.0
RESPAWN_MIN_DISTANCE = 8.0
RESPAWN_POINTS = [layout.ENTITY_SPAWN, (10.0, 7.5, 0.0), (10.0, 2.5, 0.0), (2.5, 8.0, 0.0),
                  (2.5, 7.5, 2.8), (10.0, 7.5, 2.8), (6.5, 1.6, 0.0)]


def _load(module_name, class_name):
    try:
        module = importlib.import_module(f"{__package__.rsplit('.', 1)[0]}.{module_name}")
        return getattr(module, class_name)
    except (ImportError, AttributeError) as error:
        print(f"[engine] {module_name}.{class_name} indisponível ({error}); entidade dormente", flush=True)
        return None


def _senses_class():
    """O `Senses` do módulo ai, se existir; senão um equivalente com os mesmos campos."""
    try:
        return importlib.import_module(f"{__package__.rsplit('.', 1)[0]}.ai.perception").Senses
    except (ImportError, AttributeError):
        return _FallbackSenses


@dataclass
class _FallbackSenses:
    """Campos do contrato (5.8): `player_level` é o ruído que o jogador emite agora (0..1)."""
    player_pos: tuple
    player_yaw: float = 0.0
    player_level: float = 0.0
    player_speed: float = 0.0
    player_crouching: bool = False
    flashlight_on: bool = False
    flashlight_dir: tuple = None


class EntityRuntime:
    def __init__(self, game, enabled=True, parts=None):
        """`parts=(rig, brain_factory)` injeta peças de teste; senão importa entity e ai."""
        self.game = game
        self.rig = None
        self.brain = None
        self._brain_factory = None
        self.active = False
        self.output = None
        self._anim = None
        self._last_pos = None
        self._stride_left = STRIDE_DEFAULT
        self._growl_cooldown = 0.0
        self._last_state = "dormant"
        self.senses_class = _senses_class()
        if parts is not None:
            self.rig, self._brain_factory = parts
        elif enabled:
            self._load_default_parts()
        if self._brain_factory is not None:
            self.brain = self._brain_factory()
        if self.rig is not None:
            self.rig.set_visible(False)

    def _load_default_parts(self):
        rig_class = _load("entity.rig", "EntityRig")
        brain_class = _load("ai.brain", "EntityBrain")
        if rig_class is None or brain_class is None:
            return
        game = self.game
        try:
            self.rig = rig_class(game.scene)
        except Exception as error:      # noqa: BLE001 - qualquer falha deixa a entidade dormente
            print(f"[engine] EntityRig falhou ({error}); entidade dormente", flush=True)
            return
        self._brain_factory = lambda: brain_class(game.world_view, game.noise, random.Random(game.seed + 99))

    @property
    def enabled(self):
        return self.rig is not None and self.brain is not None

    def activate(self, pos=None):
        """Começa a caçada. `pos` padrão: o fundo do corredor de cima."""
        if not self.enabled:
            return
        pos = pos or layout.ENTITY_SPAWN
        self.brain.activate(pos)
        self.rig.set_transform(pos[0], pos[1], pos[2], 0.0)
        self.rig.set_visible(True)
        self.active = True
        self._last_pos = pos

    def set_aggression(self, level):
        if self.enabled:
            self.brain.set_aggression(level)

    def reset(self):
        """Volta ao estado dormente (novo jogo, morte)."""
        if self._brain_factory is not None:
            self.brain = self._brain_factory()
        if self.rig is not None:
            self.rig.set_visible(False)
            self.rig.set_anim("idle")
            self.rig.eyes(0.0)
        for key in ("ent_drone", "ent_breath"):
            self.game.audio.stop(key)
        self.active = False
        self.output = None
        self._anim = None
        self._last_state = "dormant"

    def respawn_point(self, player_pos):
        """O ponto de partida mais longe do jogador (andar diferente conta como mais longe)."""
        def distance(point):
            level_penalty = 6.0 if layout.level_of_z(point[2]) != layout.level_of_z(player_pos[2]) else 0.0
            return math.hypot(point[0] - player_pos[0], point[1] - player_pos[1]) + level_penalty
        far_enough = [p for p in RESPAWN_POINTS if distance(p) >= RESPAWN_MIN_DISTANCE]
        return max(far_enough or RESPAWN_POINTS, key=distance)

    def distance_to(self, pos):
        if self.output is None:
            return math.inf
        out = self.output
        return math.sqrt((out.x - pos[0]) ** 2 + (out.y - pos[1]) ** 2 + ((out.z - pos[2]) * 2) ** 2)

    def danger(self, player_pos):
        """0..1: quanto o jogador deve temer agora (alimenta o batimento cardíaco)."""
        if not self.active or self.output is None:
            return 0.0
        proximity = max(0.0, 1.0 - self.distance_to(player_pos) / DANGER_RANGE)
        boost = {"chase": 0.85, "attack": 1.0, "stalk": 0.65}.get(self.output.state, 0.25)
        return min(1.0, proximity * boost * 1.4)

    def update(self, dt, senses):
        """Um passo do cérebro; devolve o BrainOutput (ou None se dormente)."""
        if not (self.enabled and self.active):
            return None
        out = self.brain.update(dt, senses)
        self.output = out
        self.rig.set_transform(out.x, out.y, out.z, out.yaw)
        if out.anim != self._anim:
            self.rig.set_anim(out.anim)
            self._anim = out.anim
        self.rig.update(dt, out.speed)
        if out.look_target is not None:
            self.rig.look_at(*out.look_target)
        self.rig.eyes(EYE_LEVEL.get(out.state, 0.6))
        self._make_sounds(dt, out)
        return out

    def _make_sounds(self, dt, out):
        game = self.game
        body = (out.x, out.y, out.z + 1.3)
        game.audio.loop("ent_drone", "ent_drone", body, max(0.0, min(1.0, out.drone)))
        distance = self.distance_to(game.player.feet)
        breath = max(0.0, 1.0 - distance / BREATH_RANGE) * 0.6
        game.audio.loop("ent_breath", "ent_breath", body, breath)
        self._footsteps(out)
        self._growl(dt, out, body)
        self._last_state = out.state

    def _footsteps(self, out):
        pos = (out.x, out.y, out.z)
        if self._last_pos is not None and out.speed > 0.2:
            self._stride_left -= math.hypot(pos[0] - self._last_pos[0], pos[1] - self._last_pos[1])
        self._last_pos = pos
        if self._stride_left > 0:
            return
        self._stride_left = STRIDE_BY_STATE.get(out.state, STRIDE_DEFAULT)
        kind = STEP_KIND_BY_STATE.get(out.state, "step_patrol")
        rng = self.game.rng
        sound = f"ent_step_stalk_{rng.randint(1, 2)}" if kind == "step_stalk" else f"ent_step_{rng.randint(1, 4)}"
        self.game.make_noise(kind, pos, C.NOISE_ENTITY[kind], sound=sound, source="entity")

    def _growl(self, dt, out, body):
        self._growl_cooldown = max(0.0, self._growl_cooldown - dt)
        if out.state == "chase" and self._last_state != "chase" and self._growl_cooldown <= 0:
            self._growl_cooldown = GROWL_COOLDOWN
            self.game.make_noise("growl", body, C.NOISE_ENTITY["growl"], sound="ent_growl", source="entity")
