"""A mão que carrega algo enquanto o corpo anda: um braço dobrado, apoiado num ombro quase parado, que absorve o passo.

Matemática pura (sem bpy), na linha de `gait.py`. `engine/handsway.py` liga isto ao `Hands`. Todas as grandezas vivem nos eixos
da câmera (x direita, y cima, z atrás; a frente é -z), em metros, graus ou segundos.

O modelo, em uma frase: a mão é uma massa presa ao ombro por uma mola com amortecedor (o antebraço), e o ombro é o do corpo do
jogador, que anda com a cabeça mas não é a cabeça. O que o jogador vê é a soma de duas coisas:

  1. o deslocamento do ombro em relação à câmera (a cabeça gira e balança sobre o tronco; o tronco fica atrás do olhar ao
     girar o mouse), sem a parte lenta, que já está na pose do gesto;
  2. a extensão da mola, que responde à ACELERAÇÃO do ombro no mundo (arrancar, parar, o balanço vertical do passo, o toque
     do calcanhar), não à posição: se o ombro anda a velocidade constante, a mão anda junto sem atraso nenhum.

    x'' + 2 zeta w x' + w^2 x = -a_ombro                 (x = extensão da mola, a_ombro = aceleração do ombro no mundo)

Rótulos de origem de cada número (a convenção da fase 4):
  MEDIDO   tirado de captura de movimento humano (CMU) ou da física do jogo, medido pelo mesmo código nos dois lados;
  DERIVADO consequência de uma lei escrita à parte (a transmissibilidade de um sistema de segunda ordem está em
           `relative_transmissibility` e é conferida contra a simulação em tests/test_maos_andando.py);
  ESTIMADO número de engenharia sem fonte medida aqui, com a faixa declarada.

Não existe clipe de mocap de alguém andando com uma lanterna na mão e o cotovelo dobrado: os clipes de lanterna da CMU (77_05)
são uma pessoa parada olhando em volta, e os de carregar (70_xx, 111_36, 113_26) são mala com o braço esticado e caixa com as duas
mãos. O que existe como medida é (a) o ombro em relação à cabeça andando e correndo (maos_ego_ref.json, 12 + 3 clipes), que é a
base em que o braço se apoia, e (b) a latência do tronco atrás da cabeça (fase 4). O resto é ESTIMADO e comparado com as leis
acima e com a ordem de grandeza da pesquisa (docs/MAOS.md).
"""
import math

# --- a mola do antebraço (ESTIMADO: 3 a 5 Hz e 0,4 a 0,7 de amortecimento, docs/FASE5.md) ---------------------------------
# O limite superior real é mais alto: ombro e antebraço têm ressonâncias de 6 a 12 Hz em vibração de mão e braço (ISO 5349),
# mas são ressonâncias do tecido com a mão APERTADA numa ferramenta. Aqui a mão apoia um objeto leve num cotovelo dobrado e a
# faixa pedida é a do controle postural do braço. O ponto de partida é o extremo macio (3 Hz): os 2 Hz do passo ficam abaixo da
# ressonância (razão 0,67), o suficiente para o passo e a partida aparecerem em centímetros e não em milímetros.
FREQUENCY_HZ = {"walk": 3.8, "run": 4.4, "crouch": 4.0}        # corre mais rígido: o cotovelo fecha (~90 graus) e o braço trava
DAMPING_RATIO = {"walk": 0.45, "run": 0.60, "crouch": 0.55}
EFFECTIVE_ARM_MASS = 1.5                      # kg: antebraço e mão que a mola move (ESTIMADO: 1,3 a 1,8 kg num adulto)
ITEM_MASS = {"flashlight": 0.30, "battery": 0.045, "key": 0.030, "map": 0.050, "note": 0.005}     # kg, ESTIMADO
SUBSTEP = 1.0 / 240.0
TELEPORT = 1.0                                # m: um ombro que anda mais que isto num quadro foi posto em outro lugar

# --- a parte lenta sai: a pose do gesto já a tem ---------------------------------------------------------------------------
# Olhar para baixo ou para cima desloca o ombro em relação à câmera por muitos centímetros, e a pose do gesto está escrita na
# câmera (a lanterna fica no quadro). O filtro passa-alta separa o que muda em menos de ~1 s (balanço do passo, giro de mouse
# rápido) do que é postura. 1,2 s corta em 0,13 Hz; o passo (1 Hz) passa com 99% da amplitude.
ANCHOR_HIGHPASS_S = 1.2
ANCHOR_JUMP = 0.25                             # m: o ombro mudou mais que isto de um quadro para o outro na câmera: corpo ou câmera foram postos em outro lugar
ANCHOR_LIMIT = (0.070, 0.050, 0.060)           # m (x, y, z): teto suave do deslocamento do apoio; o medido fica abaixo de 4 cm
# O ombro do corpo do jogo contra o real, na MESMA velocidade (08_01 a 08_03, 1,5 a 1,6 m/s; o jogo anda a 1,7): amplitude pico a pico
# (percentis 5 a 95) em (direita, frente, cima) CMU (0,012, 0,026, 0,032) m contra o jogo (0,011, 0,036, 0,034). A razão real/jogo
# (n = 3 clipes, MEDIDO nos dois lados) fica como ganho do apoio, para a mão seguir o ombro REAL e não o excesso do corpo na frente e
# atrás; (x, y, z) = (lado, cima, frente). A mediana dos 12 clipes de andar (0,010, 0,0275, 0,0196) é menor porque mistura passos
# lentos de 1,2 a 1,4 m/s, onde o ombro balança menos. Na vertical o antebraço ainda compensa uma parte (ESTIMADO: 15%, quem anda com
# algo que olha ou que ilumina o chão segura-o mais firme em relação à cabeça): 0,95 * 0,85.
ANCHOR_GAIN = (1.0, 0.80, 0.75)
# O tronco gira sobre os quadris mais devagar que a cabeça ao virar o mouse (atraso MEDIDO de 0,07 a 0,17 s, `Locomotion._follow_yaw`:
# 1/(6,5 + 9 g) s, g = ganho da passada) e, andando, o peito torce 5 a 10 graus a cada passada. Um ponto do ombro quase não sai do
# lugar com isso (o eixo passa pelo pescoço, entre os dois ombros: só 3,6 cm para trás num atraso de 26 graus), mas uma mão 35 cm à
# frente do ombro varre de lado: 35 cm * sen(12 graus) = 7 cm. A mão acompanha esta parte do braço de alavanca; o resto o antebraço
# e o ombro compensam (ESTIMADO: 0,6, faixa 0,4 a 0,8; 1 seria a mão soldada ao peito, 0 a mão soldada à câmera).
LEVER_SHARE = 0.6

# --- toque do calcanhar (ESTIMADO) -----------------------------------------------------------------------------------------
# A curva média da cabeça não tem o transiente do toque. Na caminhada o crânio recebe cerca de 0,5 g de pico e a tíbia 5 g
# (calcanhar duro); na corrida o impacto chega ao tronco e à cabeça atenuado. A mão, solta na mola, continua descendo um pouco
# enquanto o ombro freia: a velocidade inicial da extensão é ~ a velocidade vertical de aterrissagem do tronco, que é
# ~0,1 a 0,2 m/s andando e g * t_voo / 2 = 0,5 m/s correndo (voo de 0,10 s a 4 m/s, 35% do ciclo medido).
HEEL_KICK = {"walk": 0.10, "run": 0.45, "crouch": 0.03}      # m/s
HEEL_KICK_FORWARD = 0.30                                      # fração do impulso na direção da marcha (a mão segue em frente)

# --- diferença entre andar e correr (MEDIDO no ombro, ESTIMADO na mão) -----------------------------------------------------
# CMU, mediana de 12 clipes de andar e 3 de correr (maos_ego_ref.json), ombro direito em (direita, frente, cima): andando
# (+0,24, -0,11, -0,25), correndo (+0,20, -0,14, -0,20): 4 cm para dentro, 3 cm para trás, 5 cm para cima. A mão livre sobe 19 cm
# (o cotovelo fecha de 20 para ~90 graus). Uma mão que carrega, com o cotovelo já dobrado, acompanha o ombro e metade do
# fechamento a mais: o subir de 0,05 m é o do ombro (MEDIDO) e o resto é a parte ESTIMADA, pequena de propósito.
RUN_OFFSET = (-0.015, 0.045, 0.025)           # (x para dentro do lado direito, y cima, z atrás), m, no regime de corrida
MODE_FOLLOW_S = 0.25                          # s: o cotovelo leva este tempo para fechar ao começar a correr

# --- o aperto do punho: o feixe fica mais firme que a cabeça --------------------------------------------------------------
# O braço usa controle antecipado para dissipar o movimento do tronco e da cabeça (Pontzer 2009, Collins 2009): a orientação do
# que se carrega varia menos que a da cabeça. O punho cancela esta fração da inclinação e do rolar que a cabeça faz por
# passada. ESTIMADO (0 = rígido na câmera, 1 = firme no tronco); a guinada fica de fora de propósito: quem a acompanha, com a
# latência medida de 77 ms, é o feixe (`Flashlight`).
WRIST_STABILIZE = {"walk": 0.5, "run": 0.4, "crouch": 0.5}

# --- respiração e deriva postural da mão e do feixe -------------------------------------------------------------------------
# A respiração move o peito e, com ele, o ombro; aqui só o que sobra no punho: a inclinação do feixe com a fase do peito do corpo
# (a mesma fase de `Player.breath_phase`). A cabeça faz 0,12 graus parada e 0,40 sem fôlego (MEDIDO, player.py); o punho
# apoiado no peito inclina um pouco mais que a cabeça, ESTIMADO em 1,7 vezes.
BREATH_PITCH_DEG = (0.20, 0.55)                # (em repouso, sem fôlego), amplitude
# Deriva: o punho não fica parado nem em repouso. Três senos incomensuráveis por eixo entre 0,19 e 0,97 Hz, soma limitada pela
# amplitude. ESTIMADO: 0,1 a 0,3 grau (docs/FASE5.md); o dado de pesquisa é que o balanço postural de baixa frequência (0 a 2 Hz,
# eixo frente-trás) cresce com a fadiga. Com o fôlego esgotado a amplitude triplica.
DRIFT_DEG = 0.10
DRIFT_FATIGUE_GAIN = 2.0                       # amplitude = DRIFT_DEG * (1 + DRIFT_FATIGUE_GAIN * fadiga)
DRIFT_FREQUENCIES = (((0.21, 0.37, 0.83), (0.27, 0.53, 0.97), (0.19, 0.43, 0.71)),       # mão direita: (pitch, yaw, roll)
                     ((0.23, 0.41, 0.79), (0.31, 0.47, 1.00), (0.17, 0.39, 0.89)))       # mão esquerda
DRIFT_WEIGHTS = (0.50, 0.30, 0.20)
# Tremor fisiológico: 8 Hz, 0,12 a 0,24 mm no dedo parado (ESTIMADO da pesquisa). A 0,3 m do pulso isto é 0,02 a 0,05 grau no
# punho, menos de um pixel a 1280 x 720 (17,8 pixels por grau), então não é modelado. Quando houver estudo de que cresça com o
# cansaço em mais de 10 vezes, entra aqui.


def smoothstep(x):
    x = 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
    return x * x * (3.0 - 2.0 * x)


def soft_limit(value, limit):
    """Satura `value` em +-`limit` sem quina: igual ao valor perto do zero (tanh)."""
    return limit * math.tanh(value / limit)


def natural_frequency(weights, item_mass=0.0):
    """Frequência natural (rad/s) da mola para os pesos (andar, correr, agachado) e a massa do item na mão.

    w = w_braço * raiz(M / (M + m)): carregar uma lanterna de 0,3 kg desce o braço de 3,0 para 2,7 Hz."""
    walk, run, crouch = weights
    hertz = walk * FREQUENCY_HZ["walk"] + run * FREQUENCY_HZ["run"] + crouch * FREQUENCY_HZ["crouch"]
    return 2.0 * math.pi * hertz * math.sqrt(EFFECTIVE_ARM_MASS / (EFFECTIVE_ARM_MASS + item_mass))


def damping_ratio(weights):
    walk, run, crouch = weights
    return walk * DAMPING_RATIO["walk"] + run * DAMPING_RATIO["run"] + crouch * DAMPING_RATIO["crouch"]


def relative_transmissibility(frequency, natural, zeta):
    """Razão entre a amplitude da extensão (mão em relação ao ombro) e a do deslocamento do ombro, num ombro que
    oscila senoidalmente em `frequency` Hz: r^2 / raiz((1 - r^2)^2 + (2 zeta r)^2), r = frequency / natural.
    DERIVADO da equação da mola; é o que o teste confere contra a simulação."""
    r = frequency / natural
    return r * r / math.sqrt((1.0 - r * r) ** 2 + (2.0 * zeta * r) ** 2)


# ---------------------------------------------------------------------------------------------------------------------------
# Álgebra mínima (matrizes 3x3 como três linhas; `axes[i][j]` = componente j do eixo i da câmera, no mundo)
# ---------------------------------------------------------------------------------------------------------------------------
def to_camera(axes, vector):
    """Componentes de `vector` (mundo) nos eixos da câmera: (x direita, y cima, z atrás)."""
    return tuple(sum(axes[i][j] * vector[j] for j in range(3)) for i in range(3))


def from_camera(axes, vector):
    return tuple(sum(axes[i][j] * vector[i] for i in range(3)) for j in range(3))


def carry_over(old_axes, new_axes, vector):
    """Um vetor fixo no mundo, escrito nos eixos antigos da câmera, reescrito nos eixos novos."""
    return to_camera(new_axes, from_camera(old_axes, vector))


class HighPass:
    """Passa-alta de primeira ordem: devolve o sinal menos a sua média lenta (constante de tempo `tau`)."""

    def __init__(self, tau, size=3):
        self.tau, self.size = tau, size
        self.reset()

    def reset(self):
        self.slow = None

    def step(self, dt, value):
        if self.slow is None:
            self.slow = list(value)
        mix = 1.0 - math.exp(-dt / self.tau)
        self.slow = [s + (v - s) * mix for s, v in zip(self.slow, value)]
        return tuple(v - s for v, s in zip(value, self.slow))


class CarryHand:
    """Uma mão que carrega, num dos lados (`side` +1 direita, -1 esquerda).

    `step(...)` recebe a pose da câmera, a posição do ombro no mundo e o modo da marcha; devolve o deslocamento (x, y, z) a somar
    à pose do gesto, nos eixos da câmera, e `rotation` devolve a rotação do punho em graus."""

    def __init__(self, side=1.0, hand_index=0):
        self.side = side
        self.hand_index = hand_index
        self.anchor_filter = HighPass(ANCHOR_HIGHPASS_S)
        self.chest_filter = HighPass(ANCHOR_HIGHPASS_S, 1)
        self.reset()

    def reset(self):
        self.extension = [0.0, 0.0, 0.0]
        self.speed = [0.0, 0.0, 0.0]
        self.anchor = (0.0, 0.0, 0.0)
        self.mode_offset = [0.0, 0.0, 0.0]
        self.anchor_filter.reset()
        self.chest_filter.reset()
        self._axes = None
        self._camera_before = None
        self._relative_before = None
        self._shoulder = None
        self._shoulder_speed = None
        self._shoulder_accel = [0.0, 0.0, 0.0]
        self.fatigue = 0.0

    # ---- quadro a quadro ----
    def step(self, dt, camera_axes, camera_position, shoulder_world, weights, item_mass=0.0, chest_yaw=0.0, hand_position=None):
        """Avança `dt` s. `camera_axes`: três linhas (direita, cima, atrás da câmera) no mundo. `chest_yaw`: guinada do peito em
        relação à câmera (rad, + para a esquerda) e `hand_position`: a pose pedida pelo gesto, nos eixos da câmera; com os dois, a
        mão acompanha o giro do peito pelo braço de alavanca. Devolve (x, y, z)."""
        if dt <= 0.0:
            return self.offset()
        acceleration = self._shoulder_acceleration(dt, shoulder_world)
        previous = self._axes
        self._axes = camera_axes
        if previous is not None:        # a extensão é um vetor do mundo: gira junto com os eixos da câmera ao virar o mouse
            self.extension = list(carry_over(previous, camera_axes, self.extension))
            self.speed = list(carry_over(previous, camera_axes, self.speed))
        excitation = to_camera(camera_axes, acceleration)
        omega, zeta = natural_frequency(weights, item_mass), damping_ratio(weights)
        steps = max(1, int(math.ceil(dt / SUBSTEP)))
        h = dt / steps
        for _ in range(steps):
            for i in range(3):
                self.speed[i] += (-omega * omega * self.extension[i] - 2.0 * zeta * omega * self.speed[i] - excitation[i]) * h
                self.extension[i] += self.speed[i] * h
        # o corpo se atualiza DEPOIS das mãos no quadro: o ombro que se lê é o do quadro anterior e a câmera de então é a certa para ele
        reference_position, reference_axes = self._camera_before or (camera_position, camera_axes)
        self._camera_before = (camera_position, camera_axes)
        relative = to_camera(reference_axes, tuple(s - c for s, c in zip(shoulder_world, reference_position)))
        if self._relative_before is not None and math.dist(relative, self._relative_before) > ANCHOR_JUMP:
            self.anchor_filter.reset()        # um salto de corpo ou de câmera não é balanço: começa de novo, sem ficar anos saturado
            self.chest_filter.reset()
        self._relative_before = relative
        slow_out = self.anchor_filter.step(dt, relative)
        chest_dynamic = self.chest_filter.step(dt, (chest_yaw,))[0]
        if hand_position is not None and chest_dynamic != 0.0:
            slow_out = tuple(a + b for a, b in zip(slow_out, lever_shift(chest_dynamic, hand_position, relative)))
        self.anchor = tuple(soft_limit(v * gain, limit) for v, gain, limit in zip(slow_out, ANCHOR_GAIN, ANCHOR_LIMIT))
        self._follow_mode(dt, weights)
        return self.offset()

    def _shoulder_acceleration(self, dt, shoulder_world):
        """Aceleração do ombro no mundo (m/s2): segunda diferença com um filtro curto e teto de 30 m/s2.
        Um salto de posição (teletransporte, esteira de teste, fim de cena) não vira um impulso."""
        position = tuple(shoulder_world)
        if self._shoulder is None:
            self._shoulder, self._shoulder_speed = position, None
            return tuple(self._shoulder_accel)
        if math.dist(position, self._shoulder) > TELEPORT:      # o corpo foi posto em outro lugar: a velocidade continua, o salto não
            if self._shoulder_speed is None:
                self._shoulder = position
                return tuple(self._shoulder_accel)
            self._shoulder = tuple(p - v * dt for p, v in zip(position, self._shoulder_speed))
        velocity = tuple((a - b) / dt for a, b in zip(position, self._shoulder))
        self._shoulder = position
        if self._shoulder_speed is not None:
            mix = 1.0 - math.exp(-dt / 0.010)
            raw = tuple((v1 - v0) / dt for v0, v1 in zip(self._shoulder_speed, velocity))
            self._shoulder_accel = [max(-30.0, min(30.0, old + (new - old) * mix)) for old, new in zip(self._shoulder_accel, raw)]
        self._shoulder_speed = velocity
        return tuple(self._shoulder_accel)

    def _follow_mode(self, dt, weights):
        """O afastamento médio da corrida (o cotovelo fecha) vem aos poucos, pelo peso de correr."""
        run = weights[1]
        wanted = (RUN_OFFSET[0] * self.side * run, RUN_OFFSET[1] * run, RUN_OFFSET[2] * run)
        mix = 1.0 - math.exp(-dt / MODE_FOLLOW_S)
        self.mode_offset = [m + (w - m) * mix for m, w in zip(self.mode_offset, wanted)]

    def offset(self):
        """Deslocamento da mão nos eixos da câmera: apoio + mola + modo."""
        return tuple(a + e + m for a, e, m in zip(self.anchor, self.extension, self.mode_offset))

    def heel_strike(self, strength, forward=HEEL_KICK_FORWARD):
        """Toque do calcanhar: a mão continua descendo (e um pouco para a frente) com `strength` m/s."""
        self.speed[1] -= strength
        self.speed[2] -= strength * forward

    # ---- rotação do punho ----
    def rotation(self, clock, head_pitch, head_roll, weights, breath_phase, breath_mix, fatigue):
        """(pitch, yaw, roll) em graus, em torno dos eixos da câmera. `head_pitch` e `head_roll` são o que a cabeça faz a mais que
        o olhar (rad, de `Player.head_wobble`): o punho cancela `WRIST_STABILIZE` disto e soma respiração e deriva."""
        walk, run, crouch = weights
        stabilize = walk * WRIST_STABILIZE["walk"] + run * WRIST_STABILIZE["run"] + crouch * WRIST_STABILIZE["crouch"]
        breath = (BREATH_PITCH_DEG[0] + (BREATH_PITCH_DEG[1] - BREATH_PITCH_DEG[0]) * breath_mix) * math.sin(breath_phase + 0.6 * self.side)
        drift = drift_angles(clock, self.hand_index, fatigue)
        return (-stabilize * math.degrees(head_pitch) + breath + drift[0], drift[1], -stabilize * math.degrees(head_roll) + drift[2])


def lever_shift(chest_yaw, hand_position, shoulder):
    """Quanto a mão sai do lugar, nos eixos da câmera, se o peito girar `chest_yaw` (rad, + esquerda) em torno do ombro: o vetor
    ombro-mão (no plano horizontal da câmera) gira e `LEVER_SHARE` da diferença vale."""
    lx, lz = hand_position[0] - shoulder[0], hand_position[2] - shoulder[2]
    sine, cosine = math.sin(chest_yaw), math.cos(chest_yaw)
    return (LEVER_SHARE * (lx * (cosine - 1.0) + lz * sine), 0.0, LEVER_SHARE * (-lx * sine + lz * (cosine - 1.0)))


def drift_angles(clock, hand_index, fatigue):
    """Deriva postural (pitch, yaw, roll) em graus: senos incomensuráveis, amplitude de pico `DRIFT_DEG` (x3 esgotado)."""
    amplitude = DRIFT_DEG * (1.0 + DRIFT_FATIGUE_GAIN * max(0.0, min(1.0, fatigue)))
    out = []
    for axis, frequencies in enumerate(DRIFT_FREQUENCIES[hand_index]):
        total = sum(w * math.sin(math.tau * f * clock + 1.7 * axis + 0.9 * hand_index + 0.6 * k)
                    for k, (w, f) in enumerate(zip(DRIFT_WEIGHTS, frequencies)))
        out.append(amplitude * total)
    return tuple(out)
