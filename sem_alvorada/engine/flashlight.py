"""Lanterna: bateria, falhas, troca de pilha e o atraso da luz em relação à câmera.

A lógica (bateria, estado ligado) fica em `GameState`; esta classe cuida do tempo e escreve o resultado no
SPOT `Flashlight`. Quem posiciona a lanterna na mão é `Hands`: ela entrega a pose do viewmodel em
`lantern_matrix` e a luz sai da lente onde a mão a pôs. Nenhuma falha aqui vira fala: a dica de interação
e o ícone da bateria dizem o estado (ver `hudmodel`).
"""
import math
import random

import bpy  # noqa: F401 - `mathutils` só existe depois deste import
from mathutils import Euler, Matrix, Vector

from .. import conventions as C
from . import angles

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
LIGHT_FROM_GRIP = (LIGHT_XY[0] - VIEWMODEL_OFFSET[0], LIGHT_XY[1] - VIEWMODEL_OFFSET[1],
                   -LIGHT_FORWARD_MAX - VIEWMODEL_OFFSET[2])     # onde a luz nasce, a partir do punho da lanterna
HOLD_MATRIX = Matrix.Translation(VIEWMODEL_OFFSET)
BATTERY_FULL_ENOUGH = 0.9
BURST_SURGE = 1.10                        # corrente logo depois da última abertura: o contato fecha com um tranco
BURST_SURGE_TIME = 0.010                  # e o tranco dura 10 ms
# Mau contato da pilha: a corrente abre e fecha em milissegundos. Aberturas do contato como fração da rajada
# (início, fim); a rajada típica dura 0,10 a 0,15 s, então a maior abertura tem ~50 ms e a menor ~13 ms.
CHATTER = ((0.06, 0.42), (0.52, 0.72), (0.82, 0.92))
# Lâmpada incandescente: a luz segue a corrente com a inércia térmica do filamento. ESTIMADO (lembrado de memória, faixa
# de 20 a 80 ms para a subida de 10 a 90%): constantes de 14 ms na subida (31 ms de 10 a 90%) e 24 ms na descida (53 ms),
# o filamento esfria mais devagar do que esquenta com a corrente toda.
FILAMENT_TAU_UP = 0.014
FILAMENT_TAU_DOWN = 0.024
# Atraso da luz em relação ao olhar. MEDIDO no mocap 77_05 (olhar em volta com lanterna na mão direita): o antebraço
# segue a guinada da cabeça com constante de 54 a 86 ms (correlação cruzada: 50 ms; ajuste de 1ª ordem: 54 a 70 ms), então
# a luz alcança a câmera a 1/0,075 s = 13 por segundo (era 9). O limite angular é decisão de jogo: no mocap a mão chega a
# 20 graus da cabeça (desvio-padrão), mas a luz tem de continuar dentro do campo que o jogador vê.
SWAY_FOLLOW = 13.0                        # 1/s: rapidez com que a luz alcança a câmera
MAX_LAG = math.radians(10.0)
IDLE_SWAY = math.radians(0.35)
WARM = (1.0, 0.93, 0.78)
WEAK = (1.0, 0.80, 0.55)


def burst_curve(u, length=0.13):
    """Corrente (1 = contato fechado) em uma rajada de mau contato, `u` de 0 a 1 ao longo de `length` s: fecha, abre
    três vezes em tempos cada vez menores e volta com um tranco."""
    for a, b in CHATTER:
        if a <= u < b:
            return 0.0
    surge_from = CHATTER[-1][1]
    if surge_from <= u < surge_from + BURST_SURGE_TIME / length:
        return BURST_SURGE
    return 1.0


def burst_average(t0, t1, length):
    """Média da corrente da rajada no intervalo [t0, t1] (s desde o início dela): as aberturas de alguns milissegundos
    são mais curtas que um quadro, então o quadro enxerga a média, que o filamento então alisa."""
    t0, t1 = max(0.0, t0), min(length, t1)
    if t1 <= t0:
        return 1.0
    total = 1.0 * (t1 - t0)
    for a, b in CHATTER:
        total -= max(0.0, min(t1, b * length) - max(t0, a * length))
    surge = CHATTER[-1][1] * length
    total += (BURST_SURGE - 1.0) * max(0.0, min(t1, surge + BURST_SURGE_TIME) - max(t0, surge))
    return total / (t1 - t0)


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
        self._strobe_left = 0.0
        self._bursts = []                  # [[tempo desde o início, duração]] de rajadas de mau contato em curso
        self._filament = 0.0               # brilho do filamento (inércia térmica): 0 frio .. 1 incandescente
        self.lantern_matrix = None         # pose do viewmodel no espaço da câmera, entregue pelas mãos
        self._lag_yaw = 0.0
        self._lag_pitch = 0.0
        self._clock = 0.0
        self.offset = (0.0, 0.0)           # (pitch, yaw) atual da luz em relação à câmera
        self.forward_offset = LIGHT_FORWARD_MAX     # quanto a luz está à frente da câmera (m)
        self.wall_distance = FULL_POWER_DISTANCE

    # ---- comandos ----
    def switch(self, on):
        """Liga ou desliga com som e ruído. Devolve True se o estado mudou. Sem carga a lanterna só estala."""
        state = self.state
        if not state.has_flashlight or self.swap_left > 0 or on == state.flashlight_on:
            return False
        pos = self.game.player.feet
        if not on:
            state.flashlight_on = False
            self.game.make_noise("flash_click", pos, C.NOISE_PLAYER["flash_click"], sound="flash_click_off")
            return True
        if state.battery <= 0:
            self.game.sound("flash_click_off", None, 0.5)
            return False
        state.flashlight_on = True
        self.game.make_noise("flash_click", pos, C.NOISE_PLAYER["flash_click"], sound="flash_click_on")
        return True

    def toggle(self):
        return self.switch(not self.state.flashlight_on)

    def set_on(self, on):
        """Liga ou desliga sem som nem ruído (cutscenes)."""
        if self.state.has_flashlight and (not on or self.state.battery > 0):
            self.state.flashlight_on = on

    def strobe(self, seconds):
        self._strobe_left = max(self._strobe_left, seconds)

    def burst(self, seconds):
        """Uma rajada de mau contato de `seconds` s: três aberturas de alguns ms, cada vez menores, e um tranco."""
        self._bursts.append([0.0, seconds])

    def reload_blocker(self):
        """Por que a troca de pilha não pode acontecer agora: 'no_spare', 'still_good' ou None (pode)."""
        state = self.state
        if not state.has_flashlight or self.swap_left > 0:
            return "busy"
        if state.spare_batteries <= 0:
            return "no_spare"
        if state.battery > BATTERY_FULL_ENOUGH:
            return "still_good"
        return None

    def begin_swap(self, seconds):
        """A mão abriu a lanterna: a luz se apaga até a troca terminar."""
        self.swap_left = seconds
        self.state.flashlight_on = False
        self._bursts.clear()
        self.game.make_noise("battery_swap", self.game.player.feet, C.NOISE_PLAYER["battery_swap"],
                             sound="battery_clack")

    def finish_swap(self):
        """A pilha nova entrou: carga cheia, uma reserva a menos."""
        self.state.battery = C.BATTERY_MAX
        self.state.spare_batteries -= 1

    def end_swap(self):
        self.swap_left = 0.0

    # ---- quadro a quadro ----
    def update(self, dt, cam_yaw, cam_pitch, bob=(0.0, 0.0), show_viewmodel=True):
        """`bob` fica na assinatura por compatibilidade: o balanço do viewmodel agora é das mãos."""
        self._clock += dt
        self._drain(dt)
        self.intensity = self._effective_intensity(dt)
        self._follow_camera(dt, cam_yaw, cam_pitch)
        self._retract_from_walls(dt)
        self._write_light()
        if not show_viewmodel:
            self.game.hands.suspend()

    def _drain(self, dt):
        state = self.state
        if not state.flashlight_on:
            return
        state.battery = max(0.0, state.battery - C.BATTERY_DRAIN_PER_SEC * dt)
        if state.battery <= 0:
            state.flashlight_on = False
            self.game.sound("flash_off")

    def _effective_intensity(self, dt):
        """Brilho do filamento: a corrente (pilha, mau contato, strobe) passa pela inércia térmica da lâmpada."""
        state = self.state
        drive = 0.0
        if state.flashlight_on:
            drive = low_battery_gain(state.battery) * self._dropout(dt)
            if self._strobe_left > 0:
                self._strobe_left -= dt
                drive *= 0.0 if int(self._clock * 22) % 2 else 1.0
            drive *= self._burst_gain(dt)
        else:
            self._bursts.clear()
        tau = FILAMENT_TAU_UP if drive > self._filament else FILAMENT_TAU_DOWN
        self._filament += (drive - self._filament) * (1.0 - math.exp(-dt / tau))
        if abs(drive - self._filament) < 1e-3:
            self._filament = drive
        return self._filament

    def _burst_gain(self, dt):
        gain = 1.0
        for burst in self._bursts:
            gain = min(gain, burst_average(burst[0], burst[0] + dt, burst[1]))
            burst[0] += dt
        self._bursts = [b for b in self._bursts if b[0] < b[1] + BURST_SURGE_TIME]
        return gain

    def _dropout(self, dt):
        """Com a pilha fraca o contato falha em rajadas, mais frequentes e mais longas quanto menor a carga."""
        level = self.state.battery
        if level >= C.BATTERY_LOW:
            return 1.0
        weakness = 1.0 - level / C.BATTERY_LOW
        if not self._bursts and self.rng.random() < (0.4 + 5.0 * weakness) * dt:
            longest = 0.16 + 0.24 * (1.0 if level < C.BATTERY_CRITICAL else 0.0)
            self.burst(self.rng.uniform(0.06, longest))
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
        """Devolve a lanterna e as mãos ao estado do arquivo (ao sair do jogo)."""
        self.lantern_matrix = None
        if self.light is not None:
            self.light.data.energy = C.FLASH_ENERGY
            self.light.data.spot_size = math.radians(C.FLASH_SPOT_DEG)
            self.light.data.color = WARM
            self.light.rotation_euler = (0.0, 0.0, 0.0)
        if self.viewmodel is not None:
            self.viewmodel.hide_viewport = self.viewmodel.hide_render = True
            self.viewmodel.location = VIEWMODEL_OFFSET
            self.viewmodel.rotation_euler = (0.0, 0.0, 0.0)
        self.game.hands.restore_scene()

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
        grip = self.lantern_matrix if self.lantern_matrix is not None else HOLD_MATRIX
        slide = LIGHT_FORWARD_MAX - self.forward_offset                 # recuo perto da parede, ao longo do cano
        light.location = grip @ Vector((LIGHT_FROM_GRIP[0], LIGHT_FROM_GRIP[1], LIGHT_FROM_GRIP[2] + slide))
        # o atraso gira o cano em torno dos eixos da CÂMERA (a lanterna na mão está rolada, os eixos do Euler dela não servem)
        aim = Euler((pitch, yaw, 0.0), "XYZ").to_matrix() @ grip.to_3x3()
        light.rotation_euler = aim.to_euler("XYZ")
