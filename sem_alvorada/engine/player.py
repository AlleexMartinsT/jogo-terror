"""Jogador: movimento, colisão, fôlego, agachar, passos com ruído e head bob."""
import math

from .. import conventions as C
from .. import layout
from . import angles, collision

STAND_HEIGHT = 1.80
CROUCH_HEIGHT = 1.20
PITCH_LIMIT = math.radians(85.0)
ACCELERATION = 14.0            # 1/s: quão rápido a velocidade alcança a desejada (leve inércia)
BACKWARD_FACTOR = 0.8
EYE_FOLLOW = 9.0
Z_FOLLOW = 18.0                # suaviza os degraus da escada na câmera
STRIDE_METERS = {"crouch": 0.9, "walk": 1.15, "run": 1.6}
STEP_KIND = {"crouch": "crouch_walk", "walk": "walk", "run": "run"}
BOB_AMPLITUDE = {"crouch": 0.010, "walk": 0.020, "run": 0.034}
BREATH_STAMINA = 0.30
BREATH_NOISE_INTERVAL = 1.0
STAIRS_CREAK_CHANCE = 0.10
MIN_STEP_SPEED = 0.3


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
        self.eye = C.PLAYER_EYE_STAND
        self.z_visual = self.z
        self.room_id = None
        self._vx = self._vy = 0.0
        self._stride_left = STRIDE_METERS["walk"]
        self._bob_phase = 0.0
        self._bob_gain = 0.0
        self._bob_mode = "walk"
        self._breath_clock = 0.0
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

    def forward(self):
        """Direção da mira (vetor unitário 3D)."""
        flat = math.cos(self.pitch)
        return (-math.sin(self.yaw) * flat, math.cos(self.yaw) * flat, math.sin(self.pitch))

    def surface(self):
        if layout.STAIRS.contains(self.x, self.y) and 0.05 < self.z < layout.LEVEL_Z[1] - 0.05:
            return "stairs"
        room = layout.room_at(self.x, self.y, self.z)
        return room.surface if room else "concrete"

    def bob_offset(self):
        """(lateral, vertical) do head bob em metros, para a câmera e o viewmodel."""
        amplitude = BOB_AMPLITUDE[self._bob_mode] * self._bob_gain
        return (0.6 * amplitude * math.sin(self._bob_phase), amplitude * math.sin(2 * self._bob_phase))

    def camera_pose(self):
        """Posição e rotação (euler XYZ) da câmera, já com head bob."""
        lateral, vertical = self.bob_offset()
        right_x, right_y = math.cos(self.yaw), math.sin(self.yaw)
        position = (self.x + right_x * lateral, self.y + right_y * lateral, self.z_visual + self.eye + vertical)
        return position, (math.pi / 2 + self.pitch, lateral * 0.35, self.yaw)

    # ---- comandos ----
    def place(self, x, y, z, yaw, pitch=0.0):
        self.x, self.y, self.z, self.yaw, self.pitch = x, y, z, yaw, pitch
        self.z_visual = z
        self._vx = self._vy = 0.0
        self.speed = 0.0
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
        self._footsteps()
        self._breathe(dt)
        self._follow_height(dt)
        self._advance_bob()
        self._refresh_room()

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
            return C.SPEED_CROUCH
        return C.SPEED_RUN if can_run else C.SPEED_WALK

    def _move(self, dt, inp):
        wx, wy, forward = self._wish(inp)
        wish_length = math.hypot(wx, wy)
        target = self._target_speed(inp, wish_length)
        follow = 1.0 - math.exp(-ACCELERATION * dt)
        self._vx += (wx * target - self._vx) * follow
        self._vy += (wy * target - self._vy) * follow
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

    def _footsteps(self):
        if self.speed < MIN_STEP_SPEED:
            return
        mode = self._step_mode()
        self._stride_left -= self._travelled
        if self._stride_left > 0:
            return
        self._stride_left = STRIDE_METERS[mode]
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
        self.z_visual += (self.z - self.z_visual) * (1.0 - math.exp(-Z_FOLLOW * dt))

    def _advance_bob(self):
        mode = self._step_mode()
        moving = self.speed >= MIN_STEP_SPEED
        self._bob_mode = mode
        self._bob_gain += ((1.0 if moving else 0.0) - self._bob_gain) * min(1.0, 8.0 * self._dt)
        if moving:
            self._bob_phase += self._travelled / STRIDE_METERS[mode] * math.pi

    def _refresh_room(self):
        room = layout.room_at(self.x, self.y, self.z)
        self.room_id = room.id if room else None
