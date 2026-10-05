"""Mecanismo do relógio de pé da sala: o pêndulo de segundos que balança e o ponteiro dos segundos que dá passos.

O pêndulo é um pêndulo composto de comprimento equivalente 0,994 m (T = 2 s, veja `props/clock.py`), amortecido pelo ar
(Q ~ 200) e mantido pelo escape: a cada passagem pelo centro a âncora dá o impulso que repõe a energia perdida e, ~25 ms
depois, o dente cai na palheta (o "tique"). São dois tiques por ciclo, um por segundo. O ponteiro dos segundos avança 6 graus
por tique, com uma pequena oscilação de acomodação. As horas ficam paradas às 6:12 (é a história); só o mecanismo anda.

O `amb_clock_tick` é um laço de 4 s com um tique por segundo a partir de 0,5 s. Quando o laço (re)começa, `sync` ajusta a
fase do pêndulo para que o centro caia 25 ms antes de cada tique: o que se vê e o que se ouve ficam juntos. A badalada
(`clock_chime`) também espera o próximo tique, porque a corrente do sino é solta pelo mecanismo e começa numa batida.

Modelo físico independente e conferência: tools/movimento_ref/fisica/relogio.py.
"""
import math

CLOCK_RUNS = True               # falso deixa o relógio inteiro parado, como a modelagem original
PENDULUM = "grandfather_clock_pendulum"
SECOND_HAND = "grandfather_clock_seconds"
EQUIVALENT_LENGTH = 0.9937      # m (DERIVADO da haste e da lentilha)
AMPLITUDE = math.radians(2.5)   # ESTIMADO: 2 a 3 graus de cada lado num relógio de caixa alta
QUALITY = 200.0                 # ESTIMADO: fator de qualidade no ar (100 a 400)
TICK_DELAY = 0.025              # s depois do centro (ESTIMADO 10 a 40 ms)
LOOP_FIRST_TICK = 0.5           # s do início do laço `amb_clock_tick` até o primeiro tique
HAND_STEP = math.radians(6.0)   # 60 dentes, 1 tique por segundo
HAND_HZ, HAND_ZETA = 18.0, 0.35 # acomodação do ponteiro depois do salto (ESTIMADO)
GRAVITY = 9.81
SUBSTEP = 1.0 / 480.0


class ClockWork:
    def __init__(self, scene=None):
        objects = getattr(scene, "objects", None)
        self.pendulum = objects.get(PENDULUM) if objects is not None and CLOCK_RUNS else None
        self.second_hand = objects.get(SECOND_HAND) if objects is not None and CLOCK_RUNS else None
        self.omega0 = math.sqrt(GRAVITY / EQUIVALENT_LENGTH)
        self.reset()

    def reset(self):
        self.time = 0.0
        self.theta = 0.0
        self.omega = self.omega0 * AMPLITUDE
        self.ticks = 0
        self.tick_times = []          # instantes dos tiques ainda por acontecer (s)
        self.hand = 0.0               # posição do dente (rad)
        self._hand_pos = 0.0
        self._hand_vel = 0.0
        self.last_tick = None

    # ---- física
    def _step(self, dt):
        w2 = self.omega0 ** 2
        crossed = False
        while dt > 1e-9:
            h = min(dt, SUBSTEP)
            previous = self.theta
            accel = -w2 * math.sin(self.theta) - (self.omega0 / QUALITY) * self.omega
            self.omega += accel * h
            self.theta += self.omega * h
            self.time += h
            dt -= h
            if previous * self.theta < 0.0:                       # passou pelo centro
                target = math.copysign(self.omega0 * AMPLITUDE, self.omega)
                if abs(self.omega) < abs(target):
                    self.omega = 0.5 * (self.omega + target)       # o impulso da âncora repõe a energia
                self.tick_times.append(self.time + TICK_DELAY)
                crossed = True
        return crossed

    def update(self, dt):
        if not CLOCK_RUNS or dt <= 0.0:
            return
        self._step(dt)
        while self.tick_times and self.tick_times[0] <= self.time:
            self.last_tick = self.tick_times.pop(0)
            self.ticks += 1
            self.hand = self.ticks * HAND_STEP
        k = 2.0 * math.pi * HAND_HZ
        remaining = dt
        while remaining > 1e-9:                                     # o ponteiro segue o dente com uma mola amortecida
            h = min(remaining, SUBSTEP)
            self._hand_vel += (-k * k * (self._hand_pos - self.hand) - 2.0 * HAND_ZETA * k * self._hand_vel) * h
            self._hand_pos += self._hand_vel * h
            remaining -= h
        self._write()

    def _write(self):
        if self.pendulum is not None:
            self.pendulum.rotation_euler = (0.0, self.theta, 0.0)
        if self.second_hand is not None:
            self.second_hand.rotation_euler = (0.0, -self._hand_pos, 0.0)

    # ---- sincronia com o som
    def sync(self):
        """O laço do tique acabou de (re)começar agora: põe um centro do arco 25 ms antes de cada tique do laço.

        theta = a sin(phi + w t) e omega / w = a cos(phi + w t): escolhe, entre as fases que alinham, a mais próxima da atual
        (o salto máximo é meio segundo de arco, ~5 graus na lentilha)."""
        amplitude = math.hypot(self.theta, self.omega / self.omega0)
        phase_now = math.atan2(self.theta, self.omega / self.omega0)
        wanted = -self.omega0 * (LOOP_FIRST_TICK - TICK_DELAY)        # phi + w c = n pi para o centro c = 0,475 s adiante
        phase = phase_now + ((wanted - phase_now + math.pi / 2) % math.pi - math.pi / 2)
        self.theta = amplitude * math.sin(phase)
        self.omega = self.omega0 * amplitude * math.cos(phase)
        self.tick_times = []

    def next_tick_in(self):
        """Segundos até o próximo tique (a badalada começa nele)."""
        if self.tick_times:
            return max(self.tick_times[0] - self.time, 0.0)
        return 0.0
