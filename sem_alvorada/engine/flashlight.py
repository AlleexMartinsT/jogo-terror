"""Lanterna: bateria, falhas, troca de pilha e o atraso da luz em relação à câmera.

A lógica (bateria, estado ligado) fica em `GameState`; esta classe cuida do tempo e escreve
o resultado no SPOT `Flashlight` e no `ViewModel_Flashlight`, se existirem.
"""
import math
import random

from .. import conventions as C
from .. import story
from . import angles, texts

# Espaço da câmera: x direita, y cima, z para trás. O SPOT nasce na lente (à frente do corpo da lanterna,
# que assim fica fora do cone e não estoura de tão perto) e recua quando há parede: lanterna colada na parede.
VIEWMODEL_OFFSET = (0.165, -0.125, -0.28)     # a mão aparece no canto sem cobrir a mira
LIGHT_XY = (0.15, -0.10)
LIGHT_FORWARD_MAX = 0.52
LIGHT_FORWARD_MIN = 0.10
WALL_GAP = 0.12                           # a luz fica pelo menos isto antes da superfície à frente
LIGHT_RETRACT_RATE = 18.0
# Perto de uma parede o olho se adapta e a luz parece mais fraca. Sem isso o cone vira um disco branco
# sem detalhe quando se lê uma nota ou se olha uma porta a 1 m.
FULL_POWER_DISTANCE = 4.0
CLOSE_GAIN_EXPONENT = 1.6
CLOSE_GAIN_FLOOR = 0.12
LIGHT_OFFSET = (LIGHT_XY[0], LIGHT_XY[1], -LIGHT_FORWARD_MAX)
SWAP_SECONDS = 1.1
SWAP_DIP = 0.22                           # quanto a lanterna desce na mão durante a troca
BATTERY_FULL_ENOUGH = 0.9
SWAY_FOLLOW = 9.0                         # 1/s: rapidez com que a luz alcança a câmera
MAX_LAG = math.radians(7.0)
IDLE_SWAY = math.radians(0.35)
WARM = (1.0, 0.93, 0.78)
WEAK = (1.0, 0.80, 0.55)


def low_battery_gain(level):
    """Fator de brilho (0.35..1) que cai conforme a bateria passa de BATTERY_LOW para 0."""
    if level >= C.BATTERY_LOW:
        return 1.0
    return 0.35 + 0.65 * (max(level, 0.0) / C.BATTERY_LOW) ** 1.3


class Flashlight:
    def __init__(self, game, light_obj=None, viewmodel_obj=None, seed=7):
        self.game = game
        self.state = game.state
        self.light = light_obj
        self.viewmodel = viewmodel_obj
        self.rng = random.Random(seed)
        self.swap_left = 0.0
        self.intensity = 0.0               # brilho efetivo atual, 0..1
        self._dropout_left = 0.0
        self._dropout_gain = 1.0
        self._strobe_left = 0.0
        self._lag_yaw = 0.0
        self._lag_pitch = 0.0
        self._clock = 0.0
        self.offset = (0.0, 0.0)           # (pitch, yaw) atual da luz em relação à câmera
        self.forward_offset = LIGHT_FORWARD_MAX     # quanto a luz está à frente da câmera (m)
        self.wall_distance = FULL_POWER_DISTANCE

    # ---- comandos ----
    def toggle(self):
        state = self.state
        if not state.has_flashlight or self.swap_left > 0:
            return
        pos = self.game.player.feet
        if state.flashlight_on:
            state.flashlight_on = False
            self.game.make_noise("flash_click", pos, C.NOISE_PLAYER["flash_click"], sound="flash_off")
        elif state.battery <= 0:
            self.game.say(story.FLASHLIGHT_DEAD)
            self.game.sound("flash_off")
        else:
            state.flashlight_on = True
            self.game.make_noise("flash_click", pos, C.NOISE_PLAYER["flash_click"], sound="flash_on")

    def set_on(self, on):
        """Liga ou desliga sem som nem ruído (cutscenes)."""
        if self.state.has_flashlight and (not on or self.state.battery > 0):
            self.state.flashlight_on = on

    def strobe(self, seconds):
        self._strobe_left = max(self._strobe_left, seconds)

    def reload(self):
        state = self.state
        if not state.has_flashlight or self.swap_left > 0:
            return
        if state.spare_batteries <= 0:
            self.game.say(story.NO_SPARE)
            return
        if state.battery > BATTERY_FULL_ENOUGH:
            self.game.say(texts.MSG_BATTERY_GOOD)
            return
        self.swap_left = SWAP_SECONDS
        state.flashlight_on = False
        self.game.make_noise("battery_swap", self.game.player.feet, C.NOISE_PLAYER["battery_swap"],
                             sound="battery_insert")

    # ---- quadro a quadro ----
    def update(self, dt, cam_yaw, cam_pitch, bob=(0.0, 0.0), show_viewmodel=True):
        self._clock += dt
        self._tick_swap(dt)
        self._drain(dt)
        self.intensity = self._effective_intensity(dt)
        self._follow_camera(dt, cam_yaw, cam_pitch)
        self._retract_from_walls(dt)
        self._write_light()
        self._write_viewmodel(bob, show_viewmodel and self.state.has_flashlight)

    def _tick_swap(self, dt):
        if self.swap_left <= 0:
            return
        self.swap_left -= dt
        if self.swap_left <= 0:
            self.swap_left = 0.0
            self.state.battery = C.BATTERY_MAX
            self.state.spare_batteries -= 1
            self.state.flashlight_on = True
            self.game.say(story.BATTERY_SWAPPED)

    def _drain(self, dt):
        state = self.state
        if not state.flashlight_on:
            return
        state.battery = max(0.0, state.battery - C.BATTERY_DRAIN_PER_SEC * dt)
        if state.battery <= 0:
            state.flashlight_on = False
            self.game.say(story.FLASHLIGHT_DEAD)
            self.game.sound("flash_off")

    def _effective_intensity(self, dt):
        state = self.state
        if not state.flashlight_on:
            return 0.0
        gain = low_battery_gain(state.battery) * self._dropout(dt)
        if self._strobe_left > 0:
            self._strobe_left -= dt
            gain *= 0.0 if int(self._clock * 22) % 2 else 1.0
        return gain

    def _dropout(self, dt):
        """Quedas rápidas de luz que ficam mais frequentes e longas quanto menor a bateria."""
        level = self.state.battery
        if level >= C.BATTERY_LOW:
            self._dropout_left = 0.0
            return 1.0
        if self._dropout_left > 0:
            self._dropout_left -= dt
            return self._dropout_gain
        weakness = 1.0 - level / C.BATTERY_LOW
        if self.rng.random() < (0.4 + 5.0 * weakness) * dt:
            longest = 0.18 + 0.35 * (1.0 if level < C.BATTERY_CRITICAL else 0.0)
            self._dropout_left = self.rng.uniform(0.04, longest)
            self._dropout_gain = self.rng.uniform(0.0, 0.3)
            self.game.sound("flash_flicker", None, 0.5)
        return 1.0

    def _follow_camera(self, dt, cam_yaw, cam_pitch):
        follow = 1.0 - math.exp(-SWAY_FOLLOW * dt)
        self._lag_yaw += angles.difference(cam_yaw, self._lag_yaw) * follow
        self._lag_pitch += (cam_pitch - self._lag_pitch) * follow
        yaw_offset = angles.clamp(angles.difference(self._lag_yaw, cam_yaw), -MAX_LAG, MAX_LAG)
        pitch_offset = angles.clamp(self._lag_pitch - cam_pitch, -MAX_LAG, MAX_LAG)
        idle = IDLE_SWAY * math.sin(self._clock * 1.9)
        self.offset = (pitch_offset + idle, yaw_offset + idle * 0.6)

    def _retract_from_walls(self, dt):
        player = self.game.player
        # O mesmo raio serve ao recuo da luz (só importa abaixo de LIGHT_FORWARD_MAX + WALL_GAP)
        # e à adaptação do olho (precisa enxergar até FULL_POWER_DISTANCE).
        wall = self.game.collision.ray_distance(player.eye_pos, player.forward(), FULL_POWER_DISTANCE)
        self.wall_distance = wall
        target = min(LIGHT_FORWARD_MAX, max(LIGHT_FORWARD_MIN, wall - WALL_GAP))
        follow = 1.0 - math.exp(-LIGHT_RETRACT_RATE * dt)
        self.forward_offset += (target - self.forward_offset) * follow

    def snap_to_camera(self, cam_yaw, cam_pitch):
        self._lag_yaw, self._lag_pitch = cam_yaw, cam_pitch
        self.offset = (0.0, 0.0)

    def restore_scene(self):
        """Devolve a lanterna e o viewmodel ao estado do arquivo (ao sair do jogo)."""
        if self.light is not None:
            self.light.data.energy = C.FLASH_ENERGY
            self.light.data.spot_size = math.radians(C.FLASH_SPOT_DEG)
            self.light.data.color = WARM
            self.light.rotation_euler = (0.0, 0.0, 0.0)
        if self.viewmodel is not None:
            self.viewmodel.hide_viewport = self.viewmodel.hide_render = True
            self.viewmodel.location = VIEWMODEL_OFFSET
            self.viewmodel.rotation_euler = (0.0, 0.0, 0.0)

    def _close_range_gain(self):
        ratio = min(1.0, self.wall_distance / FULL_POWER_DISTANCE)
        return max(CLOSE_GAIN_FLOOR, ratio ** CLOSE_GAIN_EXPONENT)

    def _write_light(self):
        light = self.light
        if light is None:
            return
        battery_gain = low_battery_gain(self.state.battery)
        spot = light.data
        spot.energy = C.FLASH_ENERGY * self.intensity * self._close_range_gain()
        spot.spot_size = math.radians(C.FLASH_SPOT_DEG) * (0.8 + 0.2 * battery_gain)
        mix = 1.0 - battery_gain
        spot.color = tuple(w + (k - w) * mix for w, k in zip(WARM, WEAK))
        if hasattr(spot, "use_custom_distance"):
            spot.use_custom_distance = True
            spot.cutoff_distance = 30.0 * (0.45 + 0.55 * battery_gain)
        pitch, yaw = self.offset
        light.location = (LIGHT_XY[0], LIGHT_XY[1], -self.forward_offset)
        light.rotation_euler = (pitch, yaw, 0.0)

    def _write_viewmodel(self, bob, visible):
        model = self.viewmodel
        if model is None:
            return
        model.hide_viewport = model.hide_render = not visible
        if not visible:
            return
        dip = 0.0
        if self.swap_left > 0:
            dip = SWAP_DIP * math.sin(math.pi * (1.0 - self.swap_left / SWAP_SECONDS))
        x, y, z = VIEWMODEL_OFFSET
        model.location = (x + bob[0], y + bob[1] - dip, z)
        pitch, yaw = self.offset
        model.rotation_euler = (pitch * 1.4 + dip * 1.5, yaw * 1.4, 0.0)
