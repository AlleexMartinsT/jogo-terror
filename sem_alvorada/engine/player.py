"""Jogador: movimento, colisão, fôlego, agachar, passos com ruído e a cabeça que acompanha a passada.

A passada vem de `gait` (tabelas medidas em mocap real): `stride_phase` avança com a distância andada, o passo é
mais longo quanto mais rápido se anda, e a cabeça (altura, lado, giros) é a da tabela na MESMA fase que as pernas do
corpo usam. O som de cada passo sai quando a fase cruza um toque de calcanhar (cada pi), não por distância.
"""
import math

from .. import conventions as C
from .. import gait, layout
from . import angles, collision

STAND_HEIGHT = 1.80
CROUCH_HEIGHT = 1.20
PITCH_LIMIT = math.radians(85.0)
ACCELERATION = 14.0            # 1/s: perto da velocidade desejada a aproximação é exponencial (acabamento suave)
BACKWARD_FACTOR = 0.8
EYE_FOLLOW = 6.5               # 1/s: agachar leva 0,35 s de 10% a 90% da descida em 136_09 (taxa exponencial equivalente 6,3)
Z_FOLLOW = 18.0                # suaviza o piso sob os pés (desníveis pequenos)
# Na escada o corpo sobe de degrau em degrau e a cabeça sobe quase em rampa: a oscilação vertical da cabeça sem a subida é de
# 6,0 a 8,6 cm pico a pico em 83_27 a 83_35 (x1,11 pelo tamanho do Daniel = 6,7 a 9,5); com 3/s o jogo dá 7,6 cm (6/s dava 10,2)
Z_FOLLOW_STAIRS = 3.0
SPEED_FILTER = 0.08            # s: constante do filtro da velocidade que alimenta a passada
STEP_KIND = {"crouch": "crouch_walk", "walk": "walk", "run": "run"}
BREATH_STAMINA = 0.30
BREATH_NOISE_INTERVAL = 1.0
STAIRS_CREAK_CHANCE = 0.10
MIN_STEP_SPEED = gait.MIN_SPEED
RESTART_AMPLITUDE = 0.15       # ao arrancar com a passada já apagada, o ciclo recomeça no apoio médio do pé esquerdo
# Respiração e postura da cabeça parada. Vertical e lateral MEDIDOS nas janelas mais quietas de 77_02, 111_28,
# 113_21, 140_06, 140_07 e 82_08 (cabeça: 1,4 mm rms na vertical, 5 a 7 mm rms de lado); frequências e a respiração
# ofegante são ESTIMADOS (12 a 16 respirações/min em repouso, 35 a 45 depois de esforço).
IDLE_BREATH_HZ, HARD_BREATH_HZ = 0.25, 0.65
IDLE_BREATH_Z, HARD_BREATH_Z = 0.0020, 0.0055          # amplitude da subida da cabeça (m)
IDLE_BREATH_PITCH, HARD_BREATH_PITCH = math.radians(0.12), math.radians(0.40)
IDLE_SWAY = 0.0065                                       # m, deslocamento lateral lento
# A passada média achata o balanço da cabeça: a velocidade angular RMS da cabeça de pessoas reais (25,6 graus/s em 10
# clipes de andar rápido) é 1,5 vez a da curva média (16,7), porque cada passada tem sua trepidação. Devolvemos 1,4.
# Arfagem e rolagem pedem mais na corrida e agachado (RMS real 22,9 e 9,8 graus/s contra 12,6 e 3,9 da curva média x 1,4),
# onde a trepidação por passada pesa mais que a oscilação regular; a guinada da corrida já passa com 1,4.
HEAD_ROTATION_GAIN = 1.4
HEAD_TILT_GAIN = {"walk": 1.4, "run": 1.8, "crouch": 2.0}
# Inclinar para dentro da curva. Em 16_17 (andar a 0,7 m/s e virar a 140 graus/s) a cabeça rola 1,9 e o tronco 1,4 graus
# para o lado da curva, 0,2 e 0,15 do ângulo que a força centrípeta pediria (atan(v w / g) = 9,4 graus). Vale a mesma fração
# para o giro do mouse; o teto evita que um giro rápido deite a câmera.
TURN_RATE_SMOOTH = 0.10               # s, filtro da velocidade de giro (o mouse chega aos trancos)
TURN_LEAN_GAIN = 0.22
TURN_LEAN_MAX = math.radians(5.0)
TURN_LEAN_FOLLOW = 0.15               # s


class Player:
    def __init__(self, game, walk_collision):
        self.game = game
        self.collision = walk_collision
        self.x, self.y, self.z = layout.PLAYER_START
        self.yaw = math.radians(layout.PLAYER_START_YAW_DEG)
        self.pitch = 0.0
        self.crouching = False
        self.stamina = C.STAMINA_MAX
        self.exhausted = False
        self.running = False
        self.speed = 0.0
        self.gait_speed = 0.0      # velocidade filtrada: o que a passada, o corpo e os pés leem
        self.step_length = 0.0     # m, passo atual (um pé ao outro)
        self.on_stairs = False
        self.eye = C.PLAYER_EYE_STAND
        self.z_visual = self.z
        self.room_id = None
        self._vx = self._vy = 0.0
        self._brake_from = 0.0                   # m/s, velocidade em que a parada em curso começou
        self._turn_rate = 0.0                    # rad/s, giro suavizado (+ para a esquerda)
        self.turn_lean = 0.0                     # rad, inclinação para dentro da curva (+ esquerda): câmera e tronco
        self._cycle = gait.START_CYCLE          # fração do ciclo: 0 = toque do calcanhar esquerdo
        self._amp = 0.0                          # 0..1: amplitude da passada (apaga ao parar)
        self._was_moving = False
        self._last_step = int(self._cycle * 2.0)   # índice do último toque de calcanhar (meio ciclo cada)
        self._head = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)   # lateral (m), vertical (m), roll, pitch, yaw (rad) da cabeça e avanço (m)
        self._breath_clock = 0.0                 # cronômetro do ruído de respiração
        self._breath_phase = 0.0
        self._breath_mix = 0.0                   # 0 repouso .. 1 ofegante
        self._sway_clock = 0.0
        self._travelled = 0.0      # metros andados no último tick
        self._dt = 1.0 / 60.0
        self._refresh_room()

    # ---- consultas ----
    @property
    def feet(self):
        return (self.x, self.y, self.z)

    @property
    def eye_pos(self):
        return (self.x, self.y, self.z + self.eye)

    @property
    def level(self):
        return layout.level_of_z(self.z)

    @property
    def height(self):
        return CROUCH_HEIGHT if self.crouching else STAND_HEIGHT

    @property
    def breathing_hard(self):
        return self.exhausted or self.stamina < BREATH_STAMINA

    @property
    def crouch_fraction(self):
        """0 em pé .. 1 agachado, pela altura dos olhos (suave, como o corpo a vê)."""
        span = C.PLAYER_EYE_STAND - C.PLAYER_EYE_CROUCH
        return max(0.0, min(1.0, (C.PLAYER_EYE_STAND - self.eye) / span))

    @property
    def breath_phase(self):
        """Fase da respiração (rad): o peito do corpo e a cabeça da câmera sobem e descem juntos."""
        return self._breath_phase

    @property
    def breath_mix(self):
        """0 respiração de repouso .. 1 ofegante."""
        return self._breath_mix

    def forward(self):
        """Direção da mira (vetor unitário 3D)."""
        flat = math.cos(self.pitch)
        return (-math.sin(self.yaw) * flat, math.cos(self.yaw) * flat, math.sin(self.pitch))

    def surface(self):
        if self._on_stairs_now():
            return "stairs"
        room = layout.room_at(self.x, self.y, self.z)
        return room.surface if room else "concrete"

    def _on_stairs_now(self):
        return layout.STAIRS.contains(self.x, self.y) and 0.05 < self.z < layout.LEVEL_Z[1] - 0.05

    @property
    def stride_phase(self):
        """Fase da passada em radianos: cada pi é um passo (um toque de calcanhar), 2 pi é o ciclo completo.

        0 = toque do calcanhar esquerdo, pi = o do direito. É a fase das pernas do corpo e da cabeça da câmera."""
        return self._cycle * 2.0 * math.pi

    def bob_offset(self):
        """(lateral, vertical) da cabeça em metros em relação ao ponto de repouso, para a câmera e as mãos."""
        return (self._head[0], self._head[1])

    def camera_pose(self):
        """Posição e rotação (euler XYZ) da câmera: olhos, passada medida, respiração e giros da cabeça."""
        lateral, vertical, roll, pitch, yaw, ahead = self._head
        right_x, right_y = math.cos(self.yaw), math.sin(self.yaw)
        position = (self.x + right_x * lateral - math.sin(self.yaw) * ahead, self.y + right_y * lateral + math.cos(self.yaw) * ahead,
                    self.z_visual + self.eye + vertical)
        return position, gait.camera_euler(self.yaw + yaw, self.pitch + pitch, roll)

    # ---- comandos ----
    def place(self, x, y, z, yaw, pitch=0.0):
        self.x, self.y, self.z, self.yaw, self.pitch = x, y, z, yaw, pitch
        self.z_visual = z
        self._vx = self._vy = 0.0
        self.speed = self.gait_speed = 0.0
        self._amp = 0.0
        self._cycle = gait.START_CYCLE
        self._last_step = int(self._cycle * 2.0)
        self._was_moving = False
        self._head = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._turn_rate = self.turn_lean = 0.0
        self._refresh_room()

    def reset_body(self):
        """Fôlego cheio e em pé (novo jogo, checkpoint)."""
        self.stamina, self.exhausted, self.crouching = C.STAMINA_MAX, False, False
        self.eye = C.PLAYER_EYE_STAND

    # ---- quadro a quadro ----
    def update(self, dt, inp):
        self._look(inp)
        self._crouch(inp)
        self._move(dt, inp)
        self._recover_stamina(dt)
        self._advance_gait(dt)
        self._breathe(dt)
        self._follow_height(dt)
        self._lean_into_turn(dt, inp)
        self._update_head(dt)
        self._refresh_room()

    def _lean_into_turn(self, dt, inp):
        rate = -inp.look_dx / dt if dt > 1e-6 else 0.0
        self._turn_rate += (rate - self._turn_rate) * (1.0 - math.exp(-dt / TURN_RATE_SMOOTH))
        centripetal = self.gait_speed * self._turn_rate
        target = TURN_LEAN_GAIN * math.atan(centripetal / gait.G) * self._amp
        target = max(-TURN_LEAN_MAX, min(TURN_LEAN_MAX, target))
        self.turn_lean += (target - self.turn_lean) * (1.0 - math.exp(-dt / TURN_LEAN_FOLLOW))

    def _look(self, inp):
        self.yaw = angles.wrap(self.yaw - inp.look_dx)
        self.pitch = angles.clamp(self.pitch + inp.look_dy, -PITCH_LIMIT, PITCH_LIMIT)

    def _crouch(self, inp):
        if inp.crouch:
            self.crouching = True
        elif self.crouching and self.collision.headroom(self.x, self.y, self.z, STAND_HEIGHT):
            self.crouching = False

    def _wish(self, inp):
        """Vetor de desejo (x, y) no mundo, comprimento 0..1."""
        forward, side = inp.move_y, inp.move_x
        length = math.hypot(forward, side)
        if length < 1e-6:
            return 0.0, 0.0, 0.0
        if length > 1.0:
            forward, side = forward / length, side / length
        if forward < 0:
            forward *= BACKWARD_FACTOR
        fx, fy = -math.sin(self.yaw), math.cos(self.yaw)
        rx, ry = math.cos(self.yaw), math.sin(self.yaw)
        return fx * forward + rx * side, fy * forward + ry * side, forward

    def _target_speed(self, inp, wish_length):
        can_run = (inp.run and not self.crouching and not self.exhausted
                   and self.stamina >= (0.0 if self.running else C.REACH_MIN_STAMINA_TO_RUN)
                   and wish_length > 0.1)
        self.running = can_run
        if self.crouching:
            target, mode = C.SPEED_CROUCH, "crouch"
        elif can_run:
            target, mode = C.SPEED_RUN, "run"
        else:
            target, mode = C.SPEED_WALK, "walk"
        if self.on_stairs:
            # na escada o ritmo é o dos degraus (passos por segundo x profundidade do degrau), não o do corredor
            target = min(target, C.STAIRS_STEPS_PER_SECOND[mode] * layout.STAIRS.tread_depth)
        return target

    def _move(self, dt, inp):
        self.on_stairs = self._on_stairs_now()
        wx, wy, forward = self._wish(inp)
        wish_length = math.hypot(wx, wy)
        target = self._target_speed(inp, wish_length)
        goal_x, goal_y = wx * target, wy * target
        # aceleração limitada pelo que uma pessoa faz (partida 7 m/s2 em 143_03, parada até 8 m/s2 em 143_02),
        # com acabamento exponencial perto da velocidade desejada
        delta_x, delta_y = goal_x - self._vx, goal_y - self._vy
        delta = math.hypot(delta_x, delta_y)
        current = math.hypot(self._vx, self._vy)
        if delta > 1e-9:
            speeding_up = math.hypot(goal_x, goal_y) > current
            if speeding_up:
                limit = C.ACCEL_START
                self._brake_from = current
            else:       # a freada vem da velocidade em que a parada começou, senão ela viraria uma cauda exponencial
                limit = max(C.ACCEL_BRAKE_MIN, min(C.ACCEL_BRAKE, self._brake_from / C.STOP_TIME))
            change = delta if delta < 1e-4 else min(delta, limit * dt, delta * ACCELERATION * dt)
            self._vx += delta_x / delta * change
            self._vy += delta_y / delta * change
        else:
            self._brake_from = current
        old_x, old_y = self.x, self.y
        segments = self.game.doors.segments(self.level)
        self.x, self.y, self.z = collision.move_and_slide(
            self.collision, self.x, self.y, self.z, self._vx * dt, self._vy * dt,
            C.PLAYER_RADIUS, self.height, segments)
        moved = math.hypot(self.x - old_x, self.y - old_y)
        self.speed = moved / dt if dt > 0 else 0.0
        if dt > 0 and moved < math.hypot(self._vx, self._vy) * dt * 0.98:
            self._vx, self._vy = (self.x - old_x) / dt, (self.y - old_y) / dt
        self._travelled = moved
        if self.running:
            self.stamina = max(0.0, self.stamina - C.STAMINA_DRAIN * dt)
            if self.stamina <= 0.0:
                self.exhausted = True
                self.running = False
        self._dt = dt

    def _recover_stamina(self, dt):
        if self.running:
            return
        self.stamina = min(C.STAMINA_MAX, self.stamina + C.STAMINA_REGEN * dt)
        if self.exhausted and self.stamina >= C.REACH_MIN_STAMINA_TO_RUN:
            self.exhausted = False

    def _step_mode(self):
        if self.crouching:
            return "crouch"
        return "run" if self.running and self.speed > C.SPEED_WALK * 1.1 else "walk"

    # ---- passada, passos e cabeça ----
    def _advance_gait(self, dt):
        """Avança o ciclo com a distância andada, conta os toques de calcanhar e faz o som de cada um."""
        smooth = 1.0 - math.exp(-dt / SPEED_FILTER) if dt > 0 else 1.0
        self.gait_speed += (self.speed - self.gait_speed) * smooth
        self._amp = gait.amplitude(self.gait_speed)
        moving = self.speed >= MIN_STEP_SPEED
        if moving and not self._was_moving and self._amp < RESTART_AMPLITUDE:
            self._cycle = gait.START_CYCLE
            self._last_step = int(self._cycle * 2.0)
        self._was_moving = moving
        weights = gait.mode_weights(self.gait_speed, self.crouch_fraction)
        step = gait.step_length(max(self.gait_speed, self.speed), weights)
        if self.on_stairs:
            step = min(step, layout.STAIRS.tread_depth)         # um pé por degrau
        self.step_length = step
        if not moving:
            return
        self._cycle += self._travelled / (2.0 * step)
        index = int(math.floor(self._cycle * 2.0))
        while self._last_step < index:
            self._last_step += 1
            self._footstep(self._last_step % 2)
        if self._cycle > 64.0:                       # mantém o número pequeno sem mexer na fase
            self._cycle -= 64.0
            self._last_step -= 128

    def _footstep(self, foot):
        """Toque de calcanhar: `foot` 0 = esquerdo, 1 = direito. O som sai neste instante da animação."""
        mode = self._step_mode()
        surface = self.surface()
        kind = STEP_KIND[mode]
        loudness = C.NOISE_PLAYER[kind] * C.SURFACE_NOISE_MULT[surface]
        self.game.make_noise(kind, self.feet, loudness, sound=("footstep", surface))
        if surface == "stairs" and self.game.rng.random() < STAIRS_CREAK_CHANCE:
            self.game.make_noise("stairs_creak", self.feet, C.NOISE_PLAYER["stairs_creak"],
                                 sound=f"creak_{self.game.rng.randint(1, 3)}")

    def _breathe(self, dt):
        if not self.breathing_hard:
            self._breath_clock = BREATH_NOISE_INTERVAL
            return
        self._breath_clock += dt
        if self._breath_clock >= BREATH_NOISE_INTERVAL:
            self._breath_clock = 0.0
            self.game.make_noise("breath_heavy", self.feet, C.NOISE_PLAYER["breath_heavy"])

    def _follow_height(self, dt):
        target_eye = C.PLAYER_EYE_CROUCH if self.crouching else C.PLAYER_EYE_STAND
        self.eye += (target_eye - self.eye) * (1.0 - math.exp(-EYE_FOLLOW * dt))
        if abs(self.z - self.z_visual) > 0.6:
            self.z_visual = self.z
        rate = Z_FOLLOW_STAIRS if self.on_stairs or abs(self.z - self.z_visual) > 0.03 else Z_FOLLOW
        self.z_visual += (self.z - self.z_visual) * (1.0 - math.exp(-rate * dt))

    def _update_head(self, dt):
        """Cabeça = passada medida (na fase do corpo) + respiração + balanço lento de quem está parado."""
        hard = 1.0 if self.breathing_hard else 0.0
        self._breath_mix += (hard - self._breath_mix) * (1.0 - math.exp(-1.5 * dt))
        mix = self._breath_mix
        self._breath_phase += dt * 2.0 * math.pi * (IDLE_BREATH_HZ + (HARD_BREATH_HZ - IDLE_BREATH_HZ) * mix)
        self._sway_clock += dt
        breath = math.sin(self._breath_phase)
        still = 1.0 - self._amp
        breath_z = (IDLE_BREATH_Z + (HARD_BREATH_Z - IDLE_BREATH_Z) * mix) * breath
        breath_pitch = (IDLE_BREATH_PITCH + (HARD_BREATH_PITCH - IDLE_BREATH_PITCH) * mix) * breath
        sway = IDLE_SWAY * (0.6 * math.sin(self._sway_clock * 2.0 * math.pi * 0.17)
                            + 0.4 * math.sin(self._sway_clock * 2.0 * math.pi * 0.29 + 1.3)) * still
        lateral = sway
        vertical = breath_z
        roll = self.turn_lean
        pitch = breath_pitch
        yaw = 0.0
        ahead = 0.0
        if self._amp > 1e-3:
            s = gait.evaluate(self._cycle, max(self.gait_speed, 0.05), self.crouch_fraction, gait.HEAD_KEYS)
            v = s.values
            amp = self._amp
            lateral += v["cab_y"] * amp
            ahead += v["cab_x"] * amp
            vertical += (v["cab_z"] - s.drop) * amp          # s.drop: o quadril anda mais baixo que com a perna esticada
            tilt_gain = sum(w * g for w, g in zip(s.weights, (HEAD_TILT_GAIN["walk"], HEAD_TILT_GAIN["run"], HEAD_TILT_GAIN["crouch"])))
            roll += math.radians(v["cab_roll"]) * amp * tilt_gain
            pitch += math.radians(v["cab_pitch"]) * amp * tilt_gain
            yaw += math.radians(v["cab_yaw"]) * amp * HEAD_ROTATION_GAIN
        self._head = (lateral, vertical, roll, pitch, yaw, ahead)

    def _refresh_room(self):
        room = layout.room_at(self.x, self.y, self.z)
        self.room_id = room.id if room else None
