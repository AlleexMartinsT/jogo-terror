"""O que liga `handsway` (matemática pura da mão que carrega) ao jogo: câmera, ombro do corpo, passada e fôlego.

`Hands.update` chama `update` uma vez por quadro e `_pose_hand` lê `offset(side)`. O ombro vem do corpo do jogador
(`ArmControl.shoulder_world_position`); sem corpo (testes, cutscenes), é um ponto fixo na câmera, e a mão fica só com a
mola e a deriva.
"""
import math

from .. import conventions as C
from .. import gait, handsway as H

to_camera_vector = H.to_camera

SIDES = {"R": (1.0, 0), "L": (-1.0, 1)}
SHOULDER_IN_CAMERA = {"R": (0.20, -0.21, 0.05), "L": (-0.20, -0.21, 0.05)}       # sem corpo: (direita, cima, atrás) em m
MASS_OF = {C.ITEM_FLASHLIGHT: H.ITEM_MASS["flashlight"], C.ITEM_KEY: H.ITEM_MASS["key"], C.ITEM_MAP: H.ITEM_MASS["map"],
           C.ITEM_BATTERY: H.ITEM_MASS["battery"], C.ITEM_NOTE: H.ITEM_MASS["note"]}
FATIGUE_FOLLOW_S = 2.0               # s: a fadiga que alarga a deriva sobe e desce devagar, como o fôlego
STEP_WRAP = 128                      # `Player` volta a fase em 64 ciclos (128 toques) para manter o número pequeno


class HandSway:
    def __init__(self, game):
        self.game = game
        self.hands = {side: H.CarryHand(sign, index) for side, (sign, index) in SIDES.items()}
        self._offsets = {side: ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)) for side in SIDES}
        self._clock = 0.0
        self._fatigue = 0.0
        self._last_step = None
        self._axes_before = None

    def reset(self):
        for hand in self.hands.values():
            hand.reset()
        self._offsets = {side: ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)) for side in SIDES}
        self._fatigue = 0.0
        self._last_step = None
        self._axes_before = None

    def offset(self, side):
        """(deslocamento (x, y, z) em m nos eixos da câmera, rotação (rx, ry, rz) em graus) a somar à pose do gesto."""
        return self._offsets[side]

    def update(self, dt, camera_matrix, visual, hand_positions=None):
        """`camera_matrix`: Matrix 4x4 da câmera no mundo; `visual`: o que cada mão mostra agora ({"R": tipo ou None, "L": ...});
        `hand_positions`: a pose pedida pelo gesto para cada mão, nos eixos da câmera."""
        if dt <= 0.0:
            return
        self._clock += dt
        player = self.game.player
        rotation = camera_matrix.to_3x3()
        axes = tuple(tuple(rotation.col[i]) for i in range(3))
        origin = tuple(camera_matrix.translation)
        speed = getattr(player, "gait_speed", 0.0)
        weights = gait.mode_weights(speed, getattr(player, "crouch_fraction", 0.0))
        self._heel_strike(player, weights)
        stamina = getattr(player, "stamina", C.STAMINA_MAX)
        target = 1.0 if getattr(player, "exhausted", False) else max(0.0, min(1.0, (C.STAMINA_MAX - stamina) / C.STAMINA_MAX))
        self._fatigue += (target - self._fatigue) * (1.0 - math.exp(-dt / FATIGUE_FOLLOW_S))
        pitch, roll = player.head_wobble() if hasattr(player, "head_wobble") else (0.0, 0.0)
        breath_phase = getattr(player, "breath_phase", self._clock * math.tau * 0.25)
        breath_mix = getattr(player, "breath_mix", 0.0)
        shoulders = {side: self._shoulder(side, axes, origin) for side in self.hands}
        chest = self._chest_yaw(shoulders, self._axes_before or axes)       # o corpo é o do quadro anterior: a câmera também
        for side, hand in self.hands.items():
            mass = MASS_OF.get(visual.get(side), 0.0)
            wanted = None if hand_positions is None else hand_positions.get(side)
            move = hand.step(dt, axes, origin, shoulders[side], weights, mass, chest, wanted)
            turn = hand.rotation(self._clock, pitch, roll, weights, breath_phase, breath_mix, self._fatigue)
            self._offsets[side] = ((move[0], move[1], move[2]), turn)
        self._axes_before = axes

    @staticmethod
    def _chest_yaw(shoulders, axes):
        """Guinada da linha dos ombros em relação à câmera (rad, + esquerda): o peito virado para a esquerda da câmera adianta o
        ombro direito. Zero com os ombros alinhados (parado, olhando em frente)."""
        right = to_camera_vector(axes, shoulders["R"])
        left = to_camera_vector(axes, shoulders["L"])
        return math.atan2(-(right[2] - left[2]), right[0] - left[0])

    def _shoulder(self, side, axes, origin):
        arm = self.game.body.arm(side)
        point = arm.shoulder_world_position() if hasattr(arm, "shoulder_world_position") else None
        if point is not None:
            return point
        local = SHOULDER_IN_CAMERA[side]
        world = H.from_camera(axes, local)
        return tuple(o + w for o, w in zip(origin, world))

    def _heel_strike(self, player, weights):
        """Cada pi da fase da passada é um toque de calcanhar; a mão leva o impulso do modo (andar, correr, agachado)."""
        phase = getattr(player, "stride_phase", None)
        if phase is None:
            return
        index = int(phase // math.pi)
        previous, self._last_step = self._last_step, index
        if previous is None or getattr(player, "speed", 0.0) < gait.MIN_SPEED:
            return
        if (index - previous) % STEP_WRAP != 1:
            return
        amplitude = gait.amplitude(player.gait_speed)
        walk, run, crouch = weights
        strength = (walk * H.HEEL_KICK["walk"] + run * H.HEEL_KICK["run"] + crouch * H.HEEL_KICK["crouch"]) * amplitude
        for hand in self.hands.values():
            hand.heel_strike(strength)
