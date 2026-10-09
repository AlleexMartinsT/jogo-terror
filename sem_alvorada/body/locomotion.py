"""Locomoção do corpo: pernas, pelve, tronco e braços na fase da passada medida em mocap real, agachar e respirar.

Matemática pura (mathutils): recebe números do `Player` e devolve uma `PoseSpec` do solver. O corpo
nunca decide para onde anda; segue a câmera. A base do pescoço é presa a um ponto logo atrás e abaixo
dos olhos, e o quadril se desloca para que isso aconteça: agachar, inclinar e olhar para baixo saem
daí sem fórmulas separadas para a altura do quadril.

Os movimentos do ciclo (pé: avanço, lado, altura e inclinação; giro da pelve e do tórax; balanço do ombro e flexão do
cotovelo) são as médias de passadas reais da base de captura da CMU, em `gait` / `gait_data`, lidas na MESMA fase
`player.stride_phase` que dá a altura e o lado da cabeça da câmera: por isso corpo e câmera andam juntos.
"""
import math

from mathutils import Matrix, Quaternion, Vector

from .. import gait, layout
from . import skeleton as S
from .solver import LegGoal, PoseSpec

AXIS_X, AXIS_Y, AXIS_Z = Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0))
ROOT_BACK = S.EYE_FROM_C7.y            # a raiz dos pés fica atrás do olho; assim o quadril cai sob a coluna
STAND_EYE, CROUCH_EYE = 1.65, 1.30     # C.PLAYER_EYE_STAND / C.PLAYER_EYE_CROUCH
PITCH_NECK_SHARE = 0.35                # fatia da inclinação do olhar que o pescoço absorve (o resto é do tronco)
LEAN_PER_PITCH = 0.06                  # graus de tronco inclinado por grau de olhar para baixo
MAX_LAG = math.radians(68.0)           # quanto o corpo pode ficar para trás da câmera, em guinada
TOE_OUT = math.radians(5.0)
SOLE_BACK, BALL_FRONT = -0.065, 0.16   # calcanhar e articulação da bola do pé em relação ao tornozelo (m)
LEAN_GAIN = 0.95                       # graus de coluna por grau de inclinação lombar->C7 (a coluna toda gira 0,85 do que o segmento mede)
CROUCH_LEAN_MAX = 45.0                 # graus de coluna: agachado de olho a 1,05 m, mais que isso o tronco deitaria sobre as coxas
TOE_UP_MAX = math.radians(50.0)        # dedos dobrados para cima no fim do apoio (o pé rola sobre a bola)
GROUND_FOLLOW = 30.0                   # 1/s: o pé acompanha o degrau sob a sola
HIP_AHEAD_CORRECTION = {"walk": 0.09, "run": -0.05, "crouch": 0.09}      # calibrada contra a curva do quadril; ver docs/FASE4.md
# antiga:          # m: a junta do quadril do mocap fica 3,76 cm à frente da raiz Hips; a do Daniel, 1 cm (3,76 - 1,0)
TOE_HINGE, TOE_LENGTH = 0.16, 0.105    # articulação dos dedos (bola) e comprimento do dedão ao tornozelo (m), de skeleton.py
TOE_TIP = TOE_HINGE + TOE_LENGTH       # ponta do dedão em relação ao tornozelo, no plano
TOE_RELAX = 0.15                       # fração do ciclo que os dedos levam para relaxar depois de o pé sair do chão
TRUNK_TURN_LEAN = 0.75                 # tronco / câmera ao inclinar para dentro da curva (1,4 / 1,9 graus em 16_17)
SWING_MARGIN = 0.015                   # m: folga entre a ponta do pé e o chão no balanço
RUN_ROCKER_OFF = 1.0                   # 1: na corrida vale só a trajetória medida do pé (o pé não rola como no passo)
RAMP_FRACTION = 0.15
STANCE_RAMP = 0.12                     # fração do ciclo que o apoio rolante leva para entrar e sair
PELVIS_FOLLOW = 0.5                    # s: o "ponto suave da pelve" (referência das tabelas do pé) é o quadril filtrado
STEP_HALF_WIDTH = 0.0425               # m: metade da largura do passo ao andar (0,085 m nos 10 clipes de andar rápido; em pé é LEG_X)


def _rest_arm_angles():
    """Ângulos de repouso do braço do Daniel: (ombro, cotovelo) em graus, definidos como nas tabelas medidas
    (braço com a vertical no plano sagital, + = à frente; flexão do cotovelo)."""
    upper = S.BONE_MAP["UpperArm.R"].rest_dir
    fore = S.BONE_MAP["Forearm.R"].rest_dir
    return math.degrees(math.atan2(upper.y, -upper.z)), math.degrees(math.acos(max(-1.0, min(1.0, upper.dot(fore)))))


REST_SHOULDER, REST_ELBOW = _rest_arm_angles()


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def wrap(angle):
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def sole_rise(pitch, toe=0.0):
    """Quanto o tornozelo sobe para a sola (calcanhar, bola e ponta dos dedos), inclinada `pitch` e com os dedos
    dobrados `toe` para cima em relação ao pé, não entrar no chão."""
    s, c = math.sin(pitch), math.cos(pitch)
    points = ((SOLE_BACK, -S.ANKLE_Z), (BALL_FRONT, -S.ANKLE_Z), (TOE_HINGE, -S.ANKLE_Z),
              (TOE_HINGE + TOE_LENGTH * math.cos(toe), -S.ANKLE_Z + TOE_LENGTH * math.sin(toe)))
    lowest = min(y * s + z * c for y, z in points)
    return max(0.0, -lowest - S.ANKLE_Z)


def lerp(a, b, t):
    return a + (b - a) * t


class Frame:
    """Resultado de um quadro de locomoção: onde está a raiz e a pose do corpo sem os braços com alvo."""
    __slots__ = ("root", "yaw", "cam_pos", "cam_basis", "spec", "chest_scale", "phase_cycle", "gait", "body_from_world")


class Locomotion:
    def __init__(self):
        self.reset()

    def reset(self):
        self.body_yaw = None
        self.gain = 0.0
        self.crouch = 0.0
        self.last_pos = None
        self.velocity = Vector((0.0, 0.0))
        self.direction = Vector((0.0, 1.0))
        self.clock = 0.0
        self.speed_filtered = 0.0
        self.breath = 0.0
        self.last_phase = 0.0
        self.ground_z = {"L": 0.0, "R": 0.0}      # altura do piso sob cada pé, relativa à raiz, suavizada
        self.pelvis_y = 0.0                       # y suavizado do quadril no espaço do corpo (deslocamento do tronco inclinado)

    # ------------------------------------------------------------------
    def step(self, dt, player, bob):
        """Um quadro de locomoção a partir do `Player` (posição, olhar, passada, agachar)."""
        self.clock += dt
        position, euler = player.camera_pose()
        cam_pos = Vector(position)
        cam_basis = Matrix.Rotation(euler[2], 3, "Z") @ Matrix.Rotation(euler[1], 3, "Y") @ Matrix.Rotation(euler[0], 3, "X")
        cam_yaw, pitch = player.yaw, player.pitch
        speed = getattr(player, "gait_speed", None)
        if speed is None:                       # jogador de mentira (testes, cutscenes): filtra aqui
            self.speed_filtered += (player.speed - self.speed_filtered) * (1.0 - math.exp(-dt / 0.08))
            speed = self.speed_filtered

        if self.body_yaw is None:
            self.body_yaw = cam_yaw
        self._follow_yaw(dt, cam_yaw)
        lag = wrap(cam_yaw - self.body_yaw)

        here = Vector((player.x, player.y))
        if self.last_pos is not None and dt > 1e-6:
            self.velocity = (here - self.last_pos) / dt
        self.last_pos = here

        crouch = getattr(player, "crouch_fraction", None)
        if crouch is None:
            crouch = max(0.0, min(1.0, (STAND_EYE - player.eye) / (STAND_EYE - CROUCH_EYE)))
        self.crouch = crouch
        self.gain = gait.amplitude(speed)
        cycle = player.stride_phase / (2.0 * math.pi)
        sampled = gait.evaluate(cycle, max(speed, 0.05), crouch)
        step_length = getattr(player, "step_length", 0.0)
        if step_length > 0.0:
            sampled.step = step_length
        scale = gait.foot_scale(sampled)

        forward = Vector((-math.sin(self.body_yaw), math.cos(self.body_yaw)))
        root_xy = here - forward * ROOT_BACK
        root = Vector((root_xy.x, root_xy.y, player.z_visual))
        body_from_world = Matrix.Rotation(-self.body_yaw, 3, "Z")

        self._update_direction()
        spec = PoseSpec()
        rot = spec.rot
        lean = self._lean(pitch, sampled)
        self._spine(rot, lean, lag, sampled, player)
        cam_body = body_from_world @ (cam_pos - root)
        eye_offset = Matrix.Rotation(lag, 3, "Z") @ Matrix.Rotation(pitch * PITCH_NECK_SHARE, 3, "X") @ S.EYE_FROM_C7
        neck_target = cam_body - eye_offset
        spec.hips_shift = neck_target - _neck_base(rot)

        self.pelvis_y += (spec.hips_shift.y - self.pelvis_y) * (1.0 - math.exp(-dt / PELVIS_FOLLOW))
        self._legs(spec, sampled, scale, root, dt)
        self._arms_fk(rot, sampled)

        frame = Frame()
        frame.root, frame.yaw = root, self.body_yaw
        frame.cam_pos, frame.cam_basis = cam_pos, cam_basis
        frame.spec = spec
        frame.chest_scale = self._breath(dt, player)
        frame.phase_cycle = cycle
        w_walk, w_run, w_crouch = sampled.weights
        frame.gait = "crouch" if w_crouch > 0.5 else ("run" if w_run > 0.5 else "walk")
        return frame

    # ------------------------------------------------------------------
    def _follow_yaw(self, dt, cam_yaw):
        diff = wrap(cam_yaw - self.body_yaw)
        rate = 6.5 + 9.0 * self.gain
        self.body_yaw += diff * (1.0 - math.exp(-rate * dt))
        diff = wrap(cam_yaw - self.body_yaw)
        if abs(diff) > MAX_LAG:
            self.body_yaw = cam_yaw - math.copysign(MAX_LAG, diff)

    def _update_direction(self):
        """Direção do movimento no espaço do corpo (X direita, Y frente); mantém a última se parado."""
        if self.velocity.length < 0.25:
            return
        c, s = math.cos(self.body_yaw), math.sin(self.body_yaw)
        vx, vy = self.velocity.x, self.velocity.y
        local = Vector((c * vx + s * vy, -s * vx + c * vy)).normalized()
        self.direction = self.direction.lerp(local, 0.35).normalized() if self.direction.length > 1e-6 else local

    def _lean(self, pitch, sampled):
        """Graus de tronco inclinado: o do andar/correr (medido, apagado quando parado) e o do agachado, mais o olhar."""
        down = max(0.0, -math.degrees(pitch))
        up = max(0.0, math.degrees(pitch))
        lean = (sampled.lean * self.gain + sampled.lean_crouch) * LEAN_GAIN
        if sampled.lean_crouch > 0.0:
            lean = min(lean, CROUCH_LEAN_MAX)
        return lean + down * LEAN_PER_PITCH - up * 0.08

    def _spine(self, rot, lean, lag, sampled, player):
        shares = (("Hips", 0.10), ("Spine1", 0.28), ("Spine2", 0.32), ("Spine3", 0.30))
        tilt = TRUNK_TURN_LEAN * getattr(player, "turn_lean", 0.0)
        for name, share in shares:
            rot[name] = Quaternion(AXIS_X, -math.radians(lean * share)) @ Quaternion(AXIS_Y, -tilt * share)
        # a pelve gira e se inclina com a passada; a coluna torce o tórax no sentido oposto (tronco_yaw - pelve_yaw)
        v = sampled.values
        amp = self.gain
        pelvis_yaw = math.radians(v["pelve_yaw"]) * amp
        chest_twist = math.radians(v["tronco_yaw"] - v["pelve_yaw"]) * amp
        pelvis_roll = math.radians(v["pelve_roll"]) * amp
        rot["Hips"] = Quaternion(AXIS_Z, pelvis_yaw) @ Quaternion(AXIS_Y, -pelvis_roll) @ rot["Hips"]
        twist = lag * 0.55 + chest_twist
        for name, share in (("Spine1", 0.25), ("Spine2", 0.35), ("Spine3", 0.40)):
            rot[name] = Quaternion(AXIS_Z, twist * share) @ rot[name]
        breath = math.sin(getattr(player, "breath_phase", self.clock * 1.5)) * (0.35 + 0.5 * getattr(player, "breath_mix", 0.0))
        rot["Spine2"] = Quaternion(AXIS_X, math.radians(breath)) @ rot["Spine2"]
        rot["Neck"] = Quaternion(AXIS_X, math.radians(lean * 0.45))

    def _legs(self, spec, sampled, scale, root, dt):
        amp = self.gain
        direction = self.direction
        reach_scale = 0.62 + 0.38 * abs(direction.y)
        perp = Vector((direction.y, -direction.x))             # direita do movimento
        # as tabelas medem o pé em relação ao ponto suave da pelve (a raiz Hips do mocap); no Daniel esse ponto é o quadril filtrado
        correction = sum(w * c for w, c in zip(sampled.weights, (HIP_AHEAD_CORRECTION["walk"], HIP_AHEAD_CORRECTION["run"], HIP_AHEAD_CORRECTION["crouch"])))
        bias = S.BONE_MAP["Hips"].head.y + self.pelvis_y - correction
        for side, table, mirror, cycle in (("L", sampled.values, 1.0, sampled.c), ("R", sampled.other, -1.0, sampled.c + 0.5)):
            sx = S.side_sign(side)
            pitch = math.radians(table["pe"])
            phase, weight, relax = self._foot_phase(cycle, sampled.roll)
            toe = min(TOE_UP_MAX, max(0.0, -pitch)) * relax          # dedos dobrados enquanto o pé rola sobre a bola
            along_table = table["pe_frente"] * gait.LEG * scale * reach_scale
            z_table = max(table["pe_alt"] * gait.LEG, sole_rise(pitch, toe) + SWING_MARGIN * (1.0 - weight))
            along, z = along_table, z_table
            weight *= 1.0 - sampled.weights[1] * RUN_ROCKER_OFF
            if weight > 1e-4:
                model_along, model_z = self._stance_model(phase, sampled, scale * reach_scale, pitch)
                along, z = lerp(along_table, model_along, weight), lerp(z_table, model_z, weight)
            lateral = table["pe_lateral"] * gait.LEG * mirror
            half = sx * (S.LEG_X + (STEP_HALF_WIDTH - S.LEG_X) * amp)
            x = half + (direction.x * along + perp.x * lateral) * amp
            y = (direction.y * along + perp.y * lateral + bias) * amp
            z = S.ANKLE_Z + z * amp
            z += self._ground_under(side, x, y, root, dt)
            foot_q = Quaternion(AXIS_Z, -sx * TOE_OUT) @ Quaternion(AXIS_X, pitch * amp)
            pole = Vector((sx * 0.12, 1.0, 0.0))
            spec.legs[side] = LegGoal(Vector((x, y, z)), foot_q, pole)
            spec.rot[f"Toe.{side}"] = Quaternion(AXIS_X, toe * amp)

    @staticmethod
    def _foot_phase(cycle, roll):
        """(fase do pé com o toque do calcanhar em 0, peso do apoio rolante, relaxamento dos dedos).

        O peso sobe do toque do calcanhar até `STANCE_RAMP` e cai até o fim do rolamento: nas pontas do apoio a trajetória
        medida do tornozelo (que inclui o rolar do pé do sujeito do mocap) manda; no meio, o pé fica preso ao chão."""
        phase = cycle % 1.0
        if phase > roll + 0.5 * (1.0 - roll):
            phase -= 1.0
        ramp = min(STANCE_RAMP, RAMP_FRACTION * roll)
        weight = smoothstep(phase / ramp) * (1.0 - smoothstep((phase - roll + ramp) / ramp)) if 0.0 <= phase <= roll else 0.0
        if phase < 0.0:
            relax = 0.0
        else:
            relax = 1.0 - smoothstep((phase - roll) / TOE_RELAX)
        return phase, weight, relax

    @staticmethod
    def _stance_model(phase, sampled, scale, pitch):
        """(avanço, altura do tornozelo sobre o repouso) de um pé em apoio rolante.

        O pé rola sobre o chão sem deslizar: calcanhar parado até o pé ficar plano, depois a bola. O tornozelo sai da
        geometria do pé do Daniel (sola de `SOLE_BACK` a `BALL_FRONT` do tornozelo) e da inclinação MEDIDA, e o chão
        anda para trás na velocidade do corpo. Fora do apoio vale a trajetória medida, e nas trocas as duas se
        misturam; assim o pé fica parado no chão mesmo com o pé do Daniel mais comprido que o do sujeito do mocap."""
        travel = (phase - sampled.flat_phase) * 2.0 * sampled.step
        flat_ankle = sampled.flat_front * gait.LEG * scale
        s, c = math.sin(pitch), math.cos(pitch)
        if pitch >= 0.0:
            pivot = flat_ankle + SOLE_BACK - travel
            rel_y, rel_z = SOLE_BACK * c + S.ANKLE_Z * s, SOLE_BACK * s - S.ANKLE_Z * c
        else:
            pivot = flat_ankle + BALL_FRONT - travel
            rel_y, rel_z = BALL_FRONT * c + S.ANKLE_Z * s, BALL_FRONT * s - S.ANKLE_Z * c
        return pivot - rel_y, -rel_z - S.ANKLE_Z

    def _ground_under(self, side, x, y, root, dt):
        """Quanto o piso sob o pé está acima da raiz (degraus da escada), suavizado para o pé não saltar na quina.

        A sola inteira conta: o pé apoia no degrau mais alto que algum ponto dela (calcanhar, tornozelo, bola, ponta do
        dedão) toca, então o pé sobe antes de a ponta passar do espelho do degrau, e não atravessa a quina."""
        c, s = math.cos(self.body_yaw), math.sin(self.body_yaw)
        want = None
        for reach in (SOLE_BACK, 0.0, BALL_FRONT, TOE_TIP):
            fy = y + reach
            wx, wy = root.x + c * x - s * fy, root.y + s * x + c * fy
            height = layout.stairs_height(wx, wy)
            level = 0.0 if height is None else height - root.z
            want = level if want is None else max(want, level)
        self.ground_z[side] += (want - self.ground_z[side]) * (1.0 - math.exp(-GROUND_FOLLOW * dt))
        return self.ground_z[side]

    def _arms_fk(self, rot, sampled):
        """Braço solto: balanço medido, oposto à perna do mesmo lado; parado, o repouso com uma leve oscilação."""
        amp = self.gain
        for side, table in (("R", sampled.values), ("L", sampled.other)):
            sway = 1.2 * math.sin(self.clock * 0.9 + (0.0 if side == "L" else 1.7)) * (1.0 - amp)
            shoulder = (table["ombro"] - REST_SHOULDER) * amp + sway
            elbow = (table["cotovelo"] - REST_ELBOW) * amp + 9.0 * (1.0 - amp)
            rot[f"UpperArm.{side}"] = Quaternion(AXIS_X, math.radians(shoulder))
            rot[f"Forearm.{side}"] = Quaternion(AXIS_X, math.radians(elbow))

    def _breath(self, dt, player):
        phase = getattr(player, "breath_phase", None)
        if phase is None:
            hard = getattr(player, "breathing_hard", False)
            self.breath += dt * (0.65 if hard else 0.25) * 2.0 * math.pi
            phase, mix = self.breath, 1.0 if hard else 0.0
        else:
            mix = getattr(player, "breath_mix", 0.0)
        amplitude = 0.010 + 0.012 * mix
        wave = math.sin(phase)
        return (1.0 + amplitude * 0.6 * wave, 1.0 + amplitude * wave, 1.0 + amplitude * 0.8 * wave)


def _neck_base(rot):
    """Posição da base do pescoço no espaço do corpo para as rotações de coluna `rot`, com o quadril na origem."""
    world = S.IDENTITY
    head = S.BONE_MAP["Hips"].head.copy()
    previous = S.BONE_MAP["Hips"].head
    for name in ("Hips", "Spine1", "Spine2", "Spine3"):
        bone = S.BONE_MAP[name]
        if name != "Hips":
            head = head + world @ (bone.head - previous)
        world = world @ rot.get(name, S.IDENTITY)
        previous = bone.head
    neck = S.BONE_MAP["Neck"]
    return head + world @ (neck.head - previous)
