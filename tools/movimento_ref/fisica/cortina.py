"""Cortina ao vento e poeira caindo. Modelos físicos independentes do jogo (não importam `sem_alvorada`).

Cortina. Um pano pendurado numa barra é a corrente de Bernoulli: a tração cresce com o peso que há abaixo, T(s) = mu g s
(s medido a partir da barra de baixo, a bainha). Para pequenos deslocamentos laterais y(s, t):

    mu y_tt = d/ds ( mu g s y_s ) + p(t)            modos y_n = J0(2 w_n sqrt(s/g)),  J0(2 w_n sqrt(H/g)) = 0
    w_n = j_{0,n} sqrt(g / H) / 2                   (DERIVADO; f_n = w_n / 2 pi)

Para H = 2,26 m (a cortina do quarto): f1 = 0,40 Hz, f2 = 0,92 Hz, f3 = 1,41 Hz. A forma do 1o modo, vista de cima para baixo
(h = 0 na barra, h = 1 na bainha), é J0(j_{0,1} sqrt(1 - h)): 0 na barra e 1 na bainha, crescendo mais devagar no alto.
O vento é turbulência de baixa frequência (espectro de von Karman, escala de tempo T ~ 5 s, ESTIMADO) que excita esses modos;
o amortecimento do ar em tecido leve é zeta ~ 0,15 (ESTIMADO 0,08 a 0,3).

Poeira. A velocidade terminal vem de m g = 1/2 rho_ar Cd(Re) A v^2 com Cd = 24/Re (1 + 0,15 Re^0,687) (Schiller-Naumann);
densidade de reboco ~1800 kg/m3 (ESTIMADO). Poeira fina de 20 a 60 micra cai a 2 a 15 cm/s; grãos de 0,15 a 0,4 mm a
~1 a 3 m/s; lascas de milímetros, a ~4 a 7 m/s. O tempo de relaxação é tau = v_t / g (arrasto linear, vale para a fina).
"""
import math

import numpy as np
from scipy.special import j0, j1, jn_zeros

G = 9.81
RHO_AR = 1.2
MU_AR = 1.81e-5                  # Pa s
RHO_REBOCO = 1800.0              # kg/m3 (ESTIMADO 1500 a 2100)
ZETA_PANO = 0.15


def frequencias_dos_modos(altura, n=3):
    """DERIVADO: f_n = j_{0,n} sqrt(g/H) / (4 pi), em Hz."""
    return jn_zeros(0, n) * math.sqrt(G / altura) / (4.0 * math.pi)


def forma_do_modo(h, n=1):
    """Forma do modo n em h = distância à barra / altura (0 = barra, 1 = bainha), normalizada para 1 na bainha."""
    zero = jn_zeros(0, n)[n - 1]
    return j0(zero * np.sqrt(np.clip(1.0 - np.asarray(h, dtype=float), 0.0, 1.0)))


def participacao(n=1):
    """Projeção de uma pressão uniforme no modo n: 2 / (j_n J1(j_n))."""
    zero = jn_zeros(0, n)[n - 1]
    return 2.0 / (zero * j1(zero))


def espectro_do_vento(frequencia, escala=5.0):
    """Densidade espectral (von Karman) da velocidade do vento, normalizada: S(f) = 4 T / (1 + 70,8 (f T)^2)^(5/6)."""
    f = np.asarray(frequencia, dtype=float)
    return 4.0 * escala / (1.0 + 70.8 * (f * escala) ** 2) ** (5.0 / 6.0)


def simular(altura, duracao=600.0, fps=60.0, semente=0, zeta=ZETA_PANO, modos=3):
    """Resposta temporal da bainha (e de uma altura intermediária) ao vento turbulento, por integração dos modos.

    A pressão do vento é p ~ U^2, com U = média + flutuação; aqui a flutuação de pressão é um ruído filtrado pelo espectro
    de von Karman. Devolve (t, y_bainha[t], y_meio[t]) normalizados (desvio padrão 1 da bainha).
    """
    rng = np.random.default_rng(semente)
    n = int(duracao * fps)
    t = np.arange(n) / fps
    # ruído com o espectro de von Karman (pela FFT)
    frequencias = np.fft.rfftfreq(n, 1.0 / fps)
    amplitude = np.sqrt(espectro_do_vento(frequencias))
    ruido = np.fft.irfft(amplitude * (rng.normal(size=len(frequencias)) + 1j * rng.normal(size=len(frequencias))), n)
    ruido /= np.std(ruido)
    f = frequencias_dos_modos(altura, modos)
    y_bainha = np.zeros(n)
    y_meio = np.zeros(n)
    w1 = 2.0 * math.pi * f[0]                        # escala comum da pressão (a compliância estática de cada modo é 1/w_n^2)
    for k in range(modos):
        w = 2.0 * math.pi * f[k]
        gama = participacao(k + 1)
        q, v = 0.0, 0.0
        h = 1.0 / fps
        passos = 4
        for i in range(n):
            for _ in range(passos):                # integração simplética em subpassos
                a = gama * ruido[i] * w1 * w1 - 2.0 * zeta * w * v - w * w * q          # força modal = participação x pressão
                v += a * h / passos
                q += v * h / passos
            y_bainha[i] += q * float(forma_do_modo(1.0, k + 1))
            y_meio[i] += q * float(forma_do_modo(0.5, k + 1))
    escala = np.std(y_bainha)
    return t, y_bainha / escala, y_meio / escala


def espectro(t, y, minimo=0.1):
    """(frequências, potência) do sinal depois de tirar a média e as frequências abaixo de `minimo` Hz."""
    y = y - np.mean(y)
    fps = 1.0 / (t[1] - t[0])
    janela = np.hanning(len(y))
    potencia = np.abs(np.fft.rfft(y * janela)) ** 2
    freq = np.fft.rfftfreq(len(y), 1.0 / fps)
    mascara = freq >= minimo
    return freq[mascara], potencia[mascara]


def pico_do_espectro(t, y, banda=(0.1, 3.0)):
    freq, pot = espectro(t, y, banda[0])
    mascara = freq <= banda[1]
    return float(freq[mascara][np.argmax(pot[mascara])])


# --------------------------------------------------------------------------
# Poeira
# --------------------------------------------------------------------------
def velocidade_terminal(diametro, densidade=RHO_REBOCO):
    """DERIVADO: velocidade terminal (m/s) de uma esfera de `diametro` m no ar, arrasto de Schiller-Naumann (iterado)."""
    d = np.asarray(diametro, dtype=float)
    massa_efetiva = (densidade - RHO_AR) * G * math.pi * d ** 3 / 6.0
    area = math.pi * d ** 2 / 4.0
    v = massa_efetiva / (3.0 * math.pi * MU_AR * d)              # Stokes como chute
    for _ in range(60):
        re = np.maximum(RHO_AR * v * d / MU_AR, 1e-9)
        cd = 24.0 / re * (1.0 + 0.15 * re ** 0.687)
        v = np.sqrt(2.0 * massa_efetiva / (RHO_AR * cd * area))
    return v


def classes_de_poeira():
    """(nome, faixa de diâmetro em m, fração das partículas): o que cai do forro depois de um abalo (ESTIMADO)."""
    return (("poeira fina", (20e-6, 60e-6), 0.65), ("grãos", (150e-6, 400e-6), 0.25), ("lascas", (1.5e-3, 6e-3), 0.10))


def tempo_de_relaxacao(v_terminal):
    """DERIVADO: com arrasto linear, v(t) = v_t (1 - e^(-t/tau)) e tau = v_t / g."""
    return np.asarray(v_terminal) / G
