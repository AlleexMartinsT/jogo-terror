"""Porta: corpo rígido numa dobradiça, empurrado por uma mão. Modelo físico independente do jogo.

Não importa nada de `sem_alvorada`. Convenção: theta em radianos, 0 = fechada (no batente), pi/2 = aberta (o jogo
abre sempre 90 graus). Torques em N m, forças na mão em N.

    I theta'' = tau_mao - tau_seco sgn(theta') - b theta' - k_ar theta'|theta'| + tau_batente

Origem de cada número (veja `docs/FASE4.md`):
    DERIVADO   I = m L^2 / 3 (placa fina girando pela aresta); arrasto do ar = 1/8 rho Cd h L^4 w|w| (integral do
               arrasto de placa ao longo da largura); tempo mínimo a partir do limite de força (jerk mínimo);
               curva do trajeto = mínima variação de torque (Uno, Kawato e Suzuki, 1989), resolvida aqui numericamente
    ESTIMADO   massa da folha, atrito da dobradiça (mu e raio de contato), Cd da placa, limites de força da mão,
               restituição do batente, folga da lingueta. Faixas ao lado de cada constante.
"""
import math

import numpy as np

G = 9.81
RHO_AR = 1.2                     # kg/m3, ar a ~20 C (DERIVADO: gás ideal)

# ---- a folha (largura e altura vêm da planta e de props/doorspec: 36 x 80 pol menos a folga de 2 cm)
LARGURA = 0.88                   # m
ALTURA = 2.03                    # m
RAIO_MACANETA = 0.81             # m, centro da maçaneta (LARGURA - 0,07)
ABERTURA = math.pi / 2           # rad

# ---- massa por tipo de porta (ESTIMADO: madeira maciça com almofadas 20 a 30 kg; porta de entrada isolada 35 a 50 kg)
MASSAS = {"quarto": 25.0, "banheiro": 25.0, "escritorio": 25.0, "sala": 25.0, "cozinha_garagem": 32.0,
          "exterior": 40.0, "portao": 32.0}

# ---- dobradiça (ESTIMADO): 3 dobradiças de latão ou aço com arruelas de empuxo, peso apoiado no joelho de baixo
MU_DOBRADICA = 0.20              # faixa 0,15 a 0,35 (metal sobre metal pouco lubrificado)
RAIO_ATRITO = 0.007              # m, raio médio da arruela de empuxo (faixa 5 a 9 mm)
VISCOSO = 0.4                    # N m s/rad, graxa velha (faixa 0,1 a 1,0)
CD_PLACA = 1.2                   # placa plana normal ao escoamento (faixa 1,1 a 1,3)

# ---- a mão (ESTIMADO): força de empurrar com uma mão, em pé, ~1 m do chão
F_CONFORTO = 100.0               # N, esforço sustentado sem sentir peso (faixa 60 a 150)
F_PICO = 400.0                   # N, golpe explosivo (faixa 300 a 500)
F_REVERTER = 150.0               # N, frear a folha e voltar (esforço curto, faixa 100 a 250)
# ---- batente e trinco (ESTIMADO)
RESTITUICAO = 0.25               # madeira contra vedação de borracha (faixa 0,1 a 0,35)
FOLGA_LINGUETA = 0.003           # m, folga da lingueta na contra-fechadura (faixa 1 a 5 mm)
CURSO_LINGUETA = 0.011           # m, curso da lingueta (fechadura residencial: 11 mm)
PASSO_RK = 0.0005                # s


def inercia(massa=25.0, largura=LARGURA):
    """DERIVADO: momento de inércia de uma placa fina em torno da dobradiça (aresta), I = m L^2 / 3."""
    return massa * largura ** 2 / 3.0


def atrito_seco(massa=25.0):
    """DERIVADO do peso: torque de Coulomb = mu N r, com N = m g na arruela de empuxo."""
    return MU_DOBRADICA * massa * G * RAIO_ATRITO


def coeficiente_ar(largura=LARGURA, altura=ALTURA):
    """DERIVADO: torque do arrasto quadrático = k w|w|, k = (1/8) rho Cd h L^4."""
    return RHO_AR * CD_PLACA * altura * largura ** 4 / 8.0


def torque_resistente(omega, massa=25.0):
    """Atrito seco + viscoso + arrasto do ar, sempre contra o movimento."""
    return (atrito_seco(massa) * math.copysign(1.0, omega) if omega else 0.0) + VISCOSO * omega \
        + coeficiente_ar() * omega * abs(omega)


# --------------------------------------------------------------------------
# Trajetórias guiadas pela mão: quanta força a mão precisa fazer
# --------------------------------------------------------------------------
def jerk_minimo(u):
    """Posição normalizada (0..1) de um movimento de mínima sacudida em u = t/T, e suas derivadas em u."""
    u = np.asarray(u, dtype=float)
    x = 10 * u ** 3 - 15 * u ** 4 + 6 * u ** 5
    v = 30 * u ** 2 - 60 * u ** 3 + 30 * u ** 4
    a = 60 * u - 180 * u ** 2 + 120 * u ** 3
    return x, v, a


def torque_da_trajetoria(theta_t, dt, massa=25.0):
    """Torque que a mão precisa aplicar para a folha seguir `theta_t` (amostrada a cada `dt`)."""
    omega = np.gradient(theta_t, dt)
    alpha = np.gradient(omega, dt)
    resistente = np.array([torque_resistente(w, massa) if abs(w) > 1e-6 else 0.0 for w in omega])
    return inercia(massa) * alpha + resistente


def forca_pico_jerk_minimo(duracao, massa=25.0, dtheta=ABERTURA, raio=RAIO_MACANETA):
    """Maior força na maçaneta (N) para abrir `dtheta` em `duracao` s com a trajetória de jerk mínimo."""
    t = np.linspace(0.0, duracao, 801)
    x, _, _ = jerk_minimo(t / duracao)
    torque = torque_da_trajetoria(dtheta * x, t[1] - t[0], massa)
    return float(np.max(np.abs(torque)) / raio)


def tempo_minimo(forca_max, massa=25.0, dtheta=ABERTURA, raio=RAIO_MACANETA):
    """DERIVADO: menor duração que uma mão com `forca_max` consegue. Sem atrito, F r = 5,77 I dtheta / T^2."""
    i = inercia(massa)
    chute = math.sqrt(5.7735 * dtheta * i / (raio * forca_max))
    baixo, alto = chute * 0.8, chute * 1.5               # o atrito e o ar encarecem um pouco: bisseção
    for _ in range(40):
        meio = 0.5 * (baixo + alto)
        if forca_pico_jerk_minimo(meio, massa, dtheta, raio) > forca_max:
            baixo = meio
        else:
            alto = meio
    return alto


def trajetoria_minima_variacao_de_torque(duracao, massa=25.0, dtheta=ABERTURA, amostras=401):
    """Trajetória que minimiza a integral de (d tau/dt)^2 com a dinâmica da folha (inércia, atrito, ar).

    Um polinômio de grau 9 em u = t/T com posição, velocidade e aceleração fixadas nas duas pontas
    (repouso a repouso); os 4 coeficientes livres são achados por otimização. Sem atrito dá o jerk mínimo.
    Devolve (t, theta, omega, alpha, tau).
    """
    from scipy.optimize import minimize
    t = np.linspace(0.0, duracao, amostras)
    u = t / duracao
    i = inercia(massa)
    k_ar, seco = coeficiente_ar(), atrito_seco(massa)

    def base(grau, derivada):
        out = np.zeros_like(u)
        if derivada == 0:
            return u ** grau
        coef = np.prod([grau - k for k in range(derivada)])
        return coef * u ** (grau - derivada) if grau >= derivada else out

    def coeficientes(livres):
        c = np.zeros(10)
        c[6:10] = livres
        # c0=c1=c2=0 (repouso no início); c3,c4,c5 saem das 3 condições do fim (posição 1, v 0, a 0)
        ponta = np.array([[1, 1, 1], [3, 4, 5], [6, 12, 20]], dtype=float)
        resto = np.array([1.0, 0.0, 0.0]) - np.array(
            [[sum(c[g] * np.prod([g - k for k in range(d)]) for g in range(6, 10))] for d in range(3)]).ravel()
        c[3:6] = np.linalg.solve(ponta, resto)
        return c

    def serie(c):
        theta = sum(c[g] * base(g, 0) for g in range(10)) * dtheta
        omega = sum(c[g] * base(g, 1) for g in range(10)) * dtheta / duracao
        alpha = sum(c[g] * base(g, 2) for g in range(10)) * dtheta / duracao ** 2
        tau = i * alpha + seco * np.sign(omega) + VISCOSO * omega + k_ar * omega * np.abs(omega)
        return theta, omega, alpha, tau

    def custo(livres):
        tau = serie(coeficientes(livres))[3]
        return float(np.sum(np.diff(tau) ** 2) / (t[1] - t[0]))

    inicial = np.zeros(4)
    resultado = minimize(custo, inicial, method="Nelder-Mead", options={"xatol": 1e-9, "fatol": 1e-12, "maxiter": 4000})
    theta, omega, alpha, tau = serie(coeficientes(resultado.x))
    return t, theta, omega, alpha, tau


# --------------------------------------------------------------------------
# Empurrão curto e a folha solta: integração numérica
# --------------------------------------------------------------------------
def pulso_de_mao(forca, duracao, raio=RAIO_MACANETA, inicio=0.0):
    """Torque de um empurrão em meia-senoide de `duracao` s e pico `forca` N, aplicado a `raio` m da dobradiça."""
    def tau(t):
        if t < inicio or t > inicio + duracao:
            return 0.0
        return forca * raio * math.sin(math.pi * (t - inicio) / duracao)
    return tau


def simular(tau_mao, theta0, omega0, t_fim, massa=25.0, restituicao=RESTITUICAO, passo=PASSO_RK, batentes=(0.0, ABERTURA),
            torque_extra=None):
    """Integra a folha (RK4) com contato nos batentes. `tau_mao(t)` em N m. Devolve dict de séries.

    O contato é instantâneo: no batente a velocidade vira -e v. `torque_extra(theta, omega)` soma uma mola de fecho.
    """
    i = inercia(massa)

    def derivada(t, theta, omega):
        extra = torque_extra(theta, omega) if torque_extra else 0.0
        resist = torque_resistente(omega, massa)
        if omega == 0.0:                    # parado: o atrito seco só segura se o resto não o vence
            motriz = tau_mao(t) + extra
            resist = math.copysign(min(abs(motriz), atrito_seco(massa)), motriz) if motriz else 0.0
        return omega, (tau_mao(t) + extra - resist) / i

    n = int(round(t_fim / passo))
    t = np.arange(n + 1) * passo
    theta = np.empty(n + 1)
    omega = np.empty(n + 1)
    x, v = theta0, omega0
    batidas = []                              # (instante, velocidade de impacto, batente)
    for k in range(n + 1):
        theta[k], omega[k] = x, v
        if k == n:
            break
        tk = t[k]
        k1 = derivada(tk, x, v)
        k2 = derivada(tk + passo / 2, x + passo / 2 * k1[0], v + passo / 2 * k1[1])
        k3 = derivada(tk + passo / 2, x + passo / 2 * k2[0], v + passo / 2 * k2[1])
        k4 = derivada(tk + passo, x + passo * k3[0], v + passo * k3[1])
        x += passo / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        v += passo / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        for lado, batente in enumerate(batentes):
            dentro = x < batente if lado == 0 else x > batente
            if dentro:
                batidas.append((tk + passo, v, lado))
                x = batente
                v = -restituicao * v
                if abs(v) < 0.02:             # rebote sem energia: encosta e fica
                    v = 0.0
    return {"t": t, "theta": theta, "omega": omega, "batidas": batidas}


def chegada(serie, alvo, saindo_de):
    """Primeiro instante em que a folha chega a `alvo` (rad) vindo de `saindo_de`, e a velocidade nesse instante."""
    sinal = 1.0 if alvo > saindo_de else -1.0
    passou = sinal * (serie["theta"] - alvo) >= -1e-9
    indices = np.nonzero(passou)[0]
    if indices.size == 0:
        return None, None
    return float(serie["t"][indices[0]]), float(serie["omega"][indices[0]])


def golpe_de_porta(forca=F_PICO, duracao=0.15, massa=25.0, partida=ABERTURA):
    """Bater a porta: um empurrão forte e curto, a folha solta corre até o batente e quica.

    Devolve a série e (tempo de chegada ao batente em s, velocidade de impacto em rad/s, velocidade na ponta em m/s).
    """
    # o empurrão fecha: torque negativo
    pulso = pulso_de_mao(forca, duracao)
    serie = simular(lambda t: -pulso(t), partida, 0.0, 1.2, massa)
    t_chegada, _ = chegada(serie, 0.0, partida)
    w = abs(serie["batidas"][0][1])             # velocidade ANTES do rebote
    return serie, t_chegada, w, w * LARGURA


def reverter(theta, omega, massa=25.0, forca=F_REVERTER, raio=RAIO_MACANETA):
    """DERIVADO: quanto a folha ainda anda (rad) até a mão frear, a uma velocidade `omega` (rad/s).

    Freando com torque constante `forca * raio` a favor da resistência: d = w^2 / (2 alpha). Só frear, antes de voltar.
    """
    alpha = (forca * raio + torque_resistente(abs(omega), massa)) / inercia(massa)
    return omega ** 2 / (2.0 * alpha)


def rebote_parabolico(v_impacto, restituicao=RESTITUICAO, folga=FOLGA_LINGUETA, raio=RAIO_MACANETA):
    """Rebote da folha no batente com a lingueta limitando o retorno.

    DERIVADO: sai com e*v; sem a lingueta subiria v'^2 / (2 g_eff); com ela, o retorno máximo é a folga (em rad).
    Devolve a altura do primeiro rebote em rad.
    """
    folga_rad = folga / raio
    v_sai = restituicao * v_impacto
    # a mola da lingueta e a vedação puxam de volta com ~2 rad/s2 (faixa 1 a 4): sem folga o retorno seria v^2 / 4
    livre = v_sai ** 2 / (2.0 * 2.0)
    return min(livre, folga_rad)
