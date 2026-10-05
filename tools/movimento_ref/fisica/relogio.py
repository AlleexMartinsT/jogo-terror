"""Relógio de pé: pêndulo de segundos com escape. Modelo físico independente do jogo (não importa `sem_alvorada`).

Pêndulo composto. Haste fina de latão (massa por comprimento, ESTIMADO 0,24 kg/m para r = 3 mm) e lentilha de latão
(r = 0,06 m, 1,2 kg, ESTIMADO) que balançam em torno do pivô; o eixo de giro é o eixo da própria lentilha:

    I = m_h L^2 / 3 + m_b (L^2 + r^2 / 2),   d_cm = (m_h L / 2 + m_b L) / (m_h + m_b),   l_eq = I / (M d_cm)
    T = 2 pi sqrt(l_eq / g) * (1 + theta0^2 / 16 + ...)                                     (DERIVADO)

Um pêndulo "de segundos" bate 1 s por meio ciclo: T = 2 s, l_eq = g T^2 / (4 pi^2) = 0,994 m. O escape (âncora) dá o impulso
perto do centro do arco e solta o dente logo depois (o "tique"), duas vezes por ciclo, e o ponteiro dos segundos avança um
dente por tique: 6 graus (60 dentes por volta com 1 tique por segundo). Amplitude de um relógio de caixa alta: 2 a 3 graus de
cada lado (ESTIMADO); fator de qualidade Q ~ 200 no ar (ESTIMADO 100 a 400).
"""
import math

import numpy as np

G = 9.81
R_HASTE_KG_M = 0.24
M_LENTILHA = 1.2
R_LENTILHA = 0.06
AMPLITUDE = math.radians(2.5)
Q_AR = 200.0
ATRASO_DO_TIQUE = 0.025          # s depois do centro (ESTIMADO 10 a 40 ms): o dente cai no fim da face de impulso
PASSO_DO_SEGUNDEIRO = 6.0        # graus por tique (DERIVADO: 360 / 60)


def comprimento_equivalente(L, m_haste_por_m=R_HASTE_KG_M, m_lentilha=M_LENTILHA, r=R_LENTILHA):
    """l_eq (m) de uma haste de comprimento L (pivô até o centro da lentilha) mais a lentilha."""
    m_h = m_haste_por_m * L
    inercia = m_h * L ** 2 / 3.0 + m_lentilha * (L ** 2 + r ** 2 / 2.0)
    d_cm = (m_h * L / 2.0 + m_lentilha * L) / (m_h + m_lentilha)
    return inercia / ((m_h + m_lentilha) * d_cm)


def periodo(l_eq, amplitude=AMPLITUDE):
    """DERIVADO: período (s) com a correção de amplitude finita."""
    return 2.0 * math.pi * math.sqrt(l_eq / G) * (1.0 + amplitude ** 2 / 16.0)


def comprimento_para_periodo(alvo=2.0, amplitude=AMPLITUDE):
    """Comprimento da haste (pivô até o centro da lentilha) que dá o período `alvo`, por bisseção."""
    baixo, alto = 0.3, 1.5
    for _ in range(60):
        meio = 0.5 * (baixo + alto)
        if periodo(comprimento_equivalente(meio), amplitude) < alvo:
            baixo = meio
        else:
            alto = meio
    return 0.5 * (baixo + alto)


def simular(duracao, l_eq, fps=240.0, amplitude=AMPLITUDE, q=Q_AR, com_escape=True, theta0=None):
    """Integra theta'' = -(g/l) sin(theta) - (w/Q) theta' (RK4). O escape repõe a energia perdida por meio ciclo com um
    impulso na passagem pelo centro. Devolve (t, theta, instantes dos tiques)."""
    w = math.sqrt(G / l_eq)
    n = int(duracao * fps)
    t = np.arange(n) / fps
    theta = np.zeros(n)
    x = amplitude if theta0 is None else theta0
    v = 0.0
    h = 1.0 / fps / 4.0
    tiques = []
    pendente = []
    for k in range(n):
        theta[k] = x
        for _ in range(4):
            anterior = x
            a1 = -(w * w) * math.sin(x) - (w / q) * v
            v_mid = v + 0.5 * h * a1
            x_mid = x + 0.5 * h * v
            a2 = -(w * w) * math.sin(x_mid) - (w / q) * v_mid
            v += h * a2
            x += h * v_mid
            if com_escape and anterior * x < 0.0:                      # passou pelo centro
                alvo_v = math.copysign(w * amplitude, v)
                v = 0.5 * (v + alvo_v) if abs(v) < abs(alvo_v) else v   # impulso que repõe a energia
                pendente.append(t[k] + ATRASO_DO_TIQUE)
        tiques.extend(pendente)
        pendente = []
    return t, theta, np.array(tiques)


def posicao_do_segundeiro(tiques, t, passo=PASSO_DO_SEGUNDEIRO):
    """Ângulo ideal (graus) do ponteiro dos segundos: degraus de `passo` a cada tique."""
    return passo * np.searchsorted(tiques, t, side="right")
