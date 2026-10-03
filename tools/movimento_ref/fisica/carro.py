"""Carro: sedã americano dos anos 90. Modelo físico independente do jogo (não importa `sem_alvorada`).

    arrancada     0 a 100 km/h calibrado para ~10 s (ESTIMADO), com limite de tração e de potência
    suspensão     meio carro (arfagem + vertical) massa-mola-amortecedor, excitado pela aceleração e pelo chão
    rodas         rolam sem deslizar: w = v / R, sentido pelo eixo X local da roda
    direção       Ackermann: delta = atan(L kappa); relação de direção ~15:1
    rolagem       gradiente de 4 a 8 graus por g (carros macios)
    motor         vibração de marcha lenta pela frequência de ignição
    pêndulo       coelhinho do retrovisor e chaveiro: pêndulo composto forçado pela aceleração

DERIVADO = lei física a partir de medidas do modelo 3D; ESTIMADO = engenharia lembrada de memória (faixa ao lado).
Convenção do carro: +Y para a frente, +X para a direita, +Z para cima. Arfagem positiva = nariz para cima.
"""
import math

import numpy as np

G = 9.81

# ---- medidas do modelo 3D (props/car_shape.py): DERIVADO
ENTRE_EIXOS = 2.90               # m
BITOLA = 1.60                    # m (WHEEL_X = 0,80)
RAIO_RODA = 0.33                 # m; pneu 205/70R15 = 381 mm de aro + 2 x 143,5 mm de flanco -> D = 0,668 m
TETO = 1.40                      # m

# ---- massa e geometria (ESTIMADO)
MASSA = 1500.0                   # kg, faixa 1400 a 1700
ALTURA_CG = 0.55                 # m, faixa 0,50 a 0,60
FRACAO_PESO_FRENTE = 0.55        # sedã de motor dianteiro: 55 a 60% na frente
RAIO_DE_GIRO = 1.2               # m, I = m k^2 (faixa 1,1 a 1,3)
# ---- suspensão (ESTIMADO): frequências de passeio de um sedã macio e amortecimento
F_PASSEIO_FRENTE = 1.15          # Hz, faixa 1,0 a 1,5
F_PASSEIO_TRAS = 1.30            # Hz (traseira um pouco mais dura: regra da "marcha plana")
ZETA = 0.30                      # faixa 0,2 a 0,4
GRADIENTE_ROLAGEM = math.radians(6.0) / G      # rad por m/s2 (faixa 4 a 8 graus por g)
F_ROLAGEM = 1.3                  # Hz, faixa 1,0 a 1,6
# ---- tração e potência (ESTIMADO)
CDA = 0.33 * 2.1                 # m2, Cd x área frontal
CRR = 0.012                      # coeficiente de rolamento
A_PRIMEIRA = 4.0                 # m/s2, limite de tração e relação da 1a marcha
T_TROCA = 0.5                    # s perdidos por troca (2 trocas até 100 km/h)
# ---- direção (ESTIMADO)
RELACAO_DIRECAO = 15.0           # volante / roda, faixa 14 a 18 (direção hidráulica americana)
DELTA_MAX = math.radians(35.0)   # esterçamento máximo das rodas
# ---- motor de marcha lenta (ESTIMADO): V6 de 3,8 L, 700 rpm
RPM_MARCHA_LENTA = 700.0
CILINDROS = 6
ACEL_MARCHA_LENTA_RMS = (0.05, 0.40)    # m/s2 de aceleração vertical no assoalho (faixa)

# perfil do chão sob o carro: altura z do terreno em função de y (m), lido do mundo 3D por raios verticais
# (x = 15,5): piso da garagem até a soleira, soleira de 8 mm em y = -0,2 e a entrada de carros descendo até a rua.
CHAO = ((1.0, 0.0), (0.2, 0.0), (0.0, 0.0), (-0.2, 0.008), (-0.5, -0.004), (-1.0, -0.010), (-2.0, -0.021),
        (-3.0, -0.032), (-4.0, -0.043), (-5.0, -0.054), (-6.0, -0.060), (-12.0, -0.060))


def pesos_por_eixo():
    """DERIVADO: com o CG a `a` do eixo dianteiro e `b` do traseiro, a frente leva m b / L."""
    b = FRACAO_PESO_FRENTE * ENTRE_EIXOS
    a = ENTRE_EIXOS - b
    return a, b, MASSA * b / ENTRE_EIXOS, MASSA * a / ENTRE_EIXOS


def rigidez_e_amortecimento():
    """DERIVADO: k = m_eixo (2 pi f)^2 e c = 2 zeta sqrt(k m_eixo), por eixo (os dois lados juntos)."""
    a, b, m_f, m_r = pesos_por_eixo()
    k_f = m_f * (2 * math.pi * F_PASSEIO_FRENTE) ** 2
    k_r = m_r * (2 * math.pi * F_PASSEIO_TRAS) ** 2
    return k_f, k_r, 2 * ZETA * math.sqrt(k_f * m_f), 2 * ZETA * math.sqrt(k_r * m_r)


def inercia_arfagem():
    return MASSA * RAIO_DE_GIRO ** 2


def frequencias_proprias():
    """DERIVADO: frequências do meio carro (vertical e arfagem), com o acoplamento do CG fora do meio."""
    a, b, *_ = pesos_por_eixo()
    k_f, k_r, *_ = rigidez_e_amortecimento()
    k_zz = k_f + k_r
    k_zt = a * k_f - b * k_r
    k_tt = a * a * k_f + b * b * k_r
    m, i = MASSA, inercia_arfagem()
    traco = k_zz / m + k_tt / i
    det = (k_zz / m) * (k_tt / i) - (k_zt ** 2) / (m * i)
    disc = math.sqrt(max(traco ** 2 / 4 - det, 0.0))
    w1, w2 = math.sqrt(traco / 2 - disc), math.sqrt(traco / 2 + disc)
    return w1 / (2 * math.pi), w2 / (2 * math.pi)


def gradiente_de_arfagem():
    """DERIVADO: ângulo estático de arfagem por aceleração longitudinal (rad por m/s2) = m h / K_theta."""
    a, b, *_ = pesos_por_eixo()
    k_f, k_r, *_ = rigidez_e_amortecimento()
    return MASSA * ALTURA_CG / (a * a * k_f + b * b * k_r)


# --------------------------------------------------------------------------
# Longitudinal
# --------------------------------------------------------------------------
def aceleracao_a_fundo(v, potencia):
    """Aceleração (m/s2) com o acelerador a fundo: min(tração da 1a, potência / (m v)) menos resistências."""
    arrasto = 0.5 * 1.2 * CDA * v * v / MASSA
    rolamento = CRR * G
    motriz = min(A_PRIMEIRA, potencia / (MASSA * max(v, 1.0)))
    return motriz - arrasto - rolamento


def tempo_0_a_100(potencia):
    """Tempo (s) de 0 a 100 km/h a fundo com `potencia` (W efetivos) e 2 trocas de marcha."""
    v, t, dt = 0.0, 0.0, 0.002
    alvo = 100.0 / 3.6
    trocas = [(10.0, False), (19.0, False)]               # m/s em que o motorista troca
    while v < alvo and t < 60.0:
        for k, (limite, feita) in enumerate(trocas):
            if not feita and v >= limite:
                trocas[k] = (limite, True)
                t += T_TROCA
                v -= 0.02 * v                              # perde um pouco de velocidade na troca
        v += aceleracao_a_fundo(v, potencia) * dt
        t += dt
    return t


def potencia_para_10s(alvo=10.0):
    """Calibra a potência efetiva (W) para chegar a 100 km/h em `alvo` s (bisseção)."""
    baixo, alto = 20e3, 250e3
    for _ in range(40):
        meio = 0.5 * (baixo + alto)
        if tempo_0_a_100(meio) > alvo:
            baixo = meio
        else:
            alto = meio
    return alto


# --------------------------------------------------------------------------
# Trajetória e chão
# --------------------------------------------------------------------------
def percurso_jerk_minimo(t, t0, t1, total):
    """Deslocamento, velocidade e aceleração de um percurso de mínima sacudida (`total` com sinal)."""
    t = np.asarray(t, dtype=float)
    u = np.clip((t - t0) / (t1 - t0), 0.0, 1.0)
    span = t1 - t0
    s = total * (10 * u ** 3 - 15 * u ** 4 + 6 * u ** 5)
    dentro = (t > t0) & (t < t1)
    v = np.where(dentro, total * (30 * u ** 2 - 60 * u ** 3 + 30 * u ** 4) / span, 0.0)
    a = np.where(dentro, total * (60 * u - 180 * u ** 2 + 120 * u ** 3) / span ** 2, 0.0)
    return s, v, a


def altura_do_chao(y, janela=0.15):
    """Altura do terreno em y, suavizada pela mancha de contato do pneu (média numa janela de `janela` m)."""
    ys = np.array([p[0] for p in CHAO])[::-1]
    zs = np.array([p[1] for p in CHAO])[::-1]
    y = np.asarray(y, dtype=float)
    saidas = [np.interp(y + d, ys, zs) for d in np.linspace(-janela / 2, janela / 2, 7)]
    return np.mean(saidas, axis=0)


def suspensao(t, y_carro, a_longitudinal):
    """Resposta do meio carro (vertical + arfagem) ao chão e à aceleração. `y_carro(t)` é a posição do centro do
    carro (m, mundo), com o carro andando para -Y; `a_longitudinal(t)` a aceleração PARA A FRENTE (m/s2).

    Devolve (z, theta, z_origem): vertical do CG, arfagem (rad, nariz para cima) e altura do centro da base.
    """
    from scipy.integrate import solve_ivp
    a, b, *_ = pesos_por_eixo()
    k_f, k_r, c_f, c_r = rigidez_e_amortecimento()
    inercia = inercia_arfagem()

    def chao_nos_eixos(instante):
        y = y_carro(instante)
        return altura_do_chao(y - ENTRE_EIXOS / 2), altura_do_chao(y + ENTRE_EIXOS / 2)     # frente (-Y), trás (+Y)

    def derivada(instante, estado):
        z, vz, th, vth = estado
        r_f, r_r = chao_nos_eixos(instante)
        dt = 1e-3
        r_f2, r_r2 = chao_nos_eixos(instante + dt)
        v_f, v_r = (r_f2 - r_f) / dt, (r_r2 - r_r) / dt
        f_f = k_f * (z + a * th - r_f) + c_f * (vz + a * vth - v_f)
        f_r = k_r * (z - b * th - r_r) + c_r * (vz - b * vth - v_r)
        acel_z = -(f_f + f_r) / MASSA
        acel_th = (-a * f_f + b * f_r + MASSA * ALTURA_CG * a_longitudinal(instante)) / inercia
        return [vz, acel_z, vth, acel_th]

    r_f0, r_r0 = chao_nos_eixos(t[0])
    z0 = (b * r_f0 + a * r_r0) / ENTRE_EIXOS
    th0 = (r_f0 - r_r0) / ENTRE_EIXOS
    solucao = solve_ivp(derivada, (t[0], t[-1]), [z0, 0.0, th0, 0.0], t_eval=t, max_step=0.004, rtol=1e-7, atol=1e-9)
    z, th = solucao.y[0], solucao.y[2]
    # altura do centro da base (meio do entre-eixos) = z do CG deslocado ao longo do corpo inclinado
    z_origem = z + ((a - b) / 2.0) * th
    return z, th, z_origem


# --------------------------------------------------------------------------
# Rodas, direção, rolagem, motor
# --------------------------------------------------------------------------
def velocidade_angular_da_roda(v_frente):
    """DERIVADO: rolamento sem deslizar, w = v / R. Em torno do eixo +X local o sinal é negativo para andar para a frente."""
    return -v_frente / RAIO_RODA


def deslizamento_do_contato(matrizes_roda, centro, fps):
    """Velocidade horizontal do ponto mais baixo do pneu (m/s): zero se a roda rola sem deslizar."""
    raio = np.array([0.0, 0.0, -RAIO_RODA])
    contato = np.array([c + m @ raio for c, m in zip(centro, matrizes_roda)])
    return np.gradient(contato, 1.0 / fps, axis=0)[:, :2]


def esterco_ackermann(curvatura):
    """DERIVADO: ângulo das rodas para seguir uma curva de curvatura `kappa` a baixa velocidade."""
    return np.arctan(ENTRE_EIXOS * np.asarray(curvatura))


def curvatura_maxima():
    return math.tan(DELTA_MAX) / ENTRE_EIXOS


def angulo_de_rolagem(a_lateral):
    """Rolagem (rad, positiva = teto para +X) para uma aceleração lateral `a_lateral` (positiva para +X): o corpo
    se inclina para o lado contrário da aceleração."""
    return -GRADIENTE_ROLAGEM * np.asarray(a_lateral)


def vibracao_marcha_lenta():
    """DERIVADO: frequências do motor em marcha lenta (Hz): 1a ordem = rpm/60 e a ordem de ignição = n_cil/2 x 1a."""
    primeira = RPM_MARCHA_LENTA / 60.0
    return primeira, primeira * CILINDROS / 2.0


def amplitude_da_vibracao(a_rms, frequencia):
    """DERIVADO: deslocamento de pico (m) de uma senoide com aceleração RMS `a_rms` na frequência dada."""
    return a_rms * math.sqrt(2.0) / (2 * math.pi * frequencia) ** 2


# --------------------------------------------------------------------------
# Pêndulo pendurado no retrovisor
# --------------------------------------------------------------------------
def pendulo_composto(inercia_sobre_volume, volume, d_cm):
    """DERIVADO: comprimento equivalente l = I / (m d) de um corpo rígido que balança em torno de um pivô.
    Densidade uniforme (massa e volume se cancelam). `inercia_sobre_volume` em m5 (I por unidade de densidade)."""
    return inercia_sobre_volume / (volume * d_cm)


def simular_pendulo(t, comprimento, zeta, aceleracao_suporte, theta0=0.0):
    """Integra theta'' = -(g/l) sin(theta) - 2 zeta w theta' - (a_s/l) cos(theta), RK4. `a_s` na direção do ângulo positivo."""
    w = math.sqrt(G / comprimento)
    theta = np.zeros(len(t))
    omega = 0.0
    x = theta0
    sub = 8
    for k in range(len(t) - 1):
        h = (t[k + 1] - t[k]) / sub
        tk = t[k]
        for j in range(sub):
            def f(tt, x_, v_):
                return v_, -(G / comprimento) * math.sin(x_) - 2 * zeta * w * v_ - aceleracao_suporte(tt) / comprimento * math.cos(x_)
            k1 = f(tk, x, omega)
            k2 = f(tk + h / 2, x + h / 2 * k1[0], omega + h / 2 * k1[1])
            k3 = f(tk + h / 2, x + h / 2 * k2[0], omega + h / 2 * k2[1])
            k4 = f(tk + h, x + h * k3[0], omega + h * k3[1])
            x += h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
            omega += h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
            tk += h
        theta[k + 1] = x
    return theta
