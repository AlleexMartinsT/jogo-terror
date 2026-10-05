"""Luzes: lâmpada incandescente (filamento), fluorescente com reator ruim e a luz de uma TV com chuvisco.

Modelo físico independente do jogo (não importa `sem_alvorada`).

Incandescente. O filamento de tungstênio esquenta com a potência elétrica e esfria por radiação:

    C dT/dt = P_el(T) - k (T^4 - T0^4)            k = P_op / T_op^4       (Stefan-Boltzmann, DERIVADO)
    P_el = V^2 / R(T),   R ~ T^1.2                                          (resistividade do tungstênio, ESTIMADO)
    luz visível ~ T^n, n = x / (1 - e^-x), x = h c / (lambda k_B T)         (Planck a 555 nm, DERIVADO: n ~ 9,3 a 2800 K)

Normalizando por T_op: u' = (s u^-1,2 - u^4 + u0^4) / (4 tau), tau = C / (4 k T_op^3). Com o filamento de uma lâmpada de 60 W
(~18 mg de tungstênio, c = 0,16 J/g/K, ESTIMADO) tau ~ 33 ms. Desligar: a luz cai a 10% em ~50 ms; ligar: sobe a 90% em ~100 ms.

Fluorescente com reator ruim (ESTIMADO): o arco falha e reacende em rajadas de 3 a 10 Hz (3 a 8 piscadas), com a lâmpada
apagando de verdade entre elas (profundidade quase total), e longos trechos estáveis entre as rajadas.

TV de tubo com chuvisco: o ruído muda a cada campo (59,94 Hz no NTSC), mas a luz média da sala quase não varia: são
300 mil pixels independentes, flutuação relativa ~1/raiz(N); sobra uma variação lenta de ~2 a 4% (barra de zumbido, CAG).
"""
import math

import numpy as np

# ---- filamento (ESTIMADO salvo o dito)
T_OPERACAO = 2800.0              # K, lâmpada de 60 W
T_AMBIENTE = 300.0               # K
MASSA_FILAMENTO = 18e-6          # kg (17,7 mg de um fio de 0,58 m e 45 micra)
CALOR_ESPECIFICO = 160.0         # J/kg/K a alta temperatura (0,16 J/g/K)
POTENCIA_OPERACAO = 60.0         # W
EXPOENTE_R = 1.2                 # R ~ T^1,2
H_PLANCK, C_LUZ, K_BOLTZMANN = 6.626e-34, 2.998e8, 1.381e-23


def expoente_de_planck(T=T_OPERACAO, comprimento_de_onda=555e-9):
    """DERIVADO: d ln L / d ln T para a radiância espectral de Planck: x e^x / (e^x - 1), com x = hc / (lambda k T)."""
    x = H_PLANCK * C_LUZ / (comprimento_de_onda * K_BOLTZMANN * T)
    return x / (1.0 - math.exp(-x))


def constante_de_tempo():
    """DERIVADO: tau = C / (4 k T_op^3), k = P_op / T_op^4  =>  tau = C T_op / (4 P_op)."""
    calor = MASSA_FILAMENTO * CALOR_ESPECIFICO
    return calor * T_OPERACAO / (4.0 * POTENCIA_OPERACAO)


def potencia_para_luz(luz_relativa, n=None):
    """Potência elétrica relativa (V^2/V_op^2) que mantém, em regime, a luz relativa pedida."""
    n = n or expoente_de_planck()
    u = max(luz_relativa, 0.0) ** (1.0 / n)
    return u ** EXPOENTE_R * (u ** 4 - (T_AMBIENTE / T_OPERACAO) ** 4)


def simular_filamento(t, potencia_relativa, u0=None):
    """Integra u' = (s u^-1,2 - u^4 + u0^4) / (4 tau) (RK4, passo de 0,5 ms). Devolve a luz relativa L = u^n por amostra."""
    n, tau = expoente_de_planck(), constante_de_tempo()
    ambiente = T_AMBIENTE / T_OPERACAO
    u = ambiente if u0 is None else u0
    luz = np.zeros(len(t))

    def f(instante, x):
        s = potencia_relativa(instante)
        return (s * max(x, ambiente) ** -EXPOENTE_R - x ** 4 + ambiente ** 4) / (4.0 * tau)

    luz[0] = u ** n
    for k in range(len(t) - 1):
        passos = max(1, int(math.ceil((t[k + 1] - t[k]) / 0.0005)))
        h = (t[k + 1] - t[k]) / passos
        tk = t[k]
        for _ in range(passos):
            k1 = f(tk, u)
            k2 = f(tk + h / 2, u + h / 2 * k1)
            k3 = f(tk + h / 2, u + h / 2 * k2)
            k4 = f(tk + h, u + h * k3)
            u += h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            tk += h
        luz[k + 1] = u ** n
    return luz


def tempos_de_resposta():
    """(tempo para cair a 10% ao desligar, tempo para subir a 90% ao ligar), em s, do modelo."""
    t = np.arange(0, 1.5, 0.001)
    ligada = simular_filamento(t, lambda x: 1.0, u0=1.0)                           # só confere o regime
    assert abs(ligada[-1] - 1.0) < 1e-3, ligada[-1]
    desliga = simular_filamento(t, lambda x: 0.0, u0=1.0)
    liga = simular_filamento(t, lambda x: 1.0, u0=None)
    return float(t[np.argmax(desliga < 0.10)]), float(t[np.argmax(liga > 0.90)])


# --------------------------------------------------------------------------
# Fluorescente com reator ruim
# --------------------------------------------------------------------------
def estatisticas_de_rajadas(t, ganho, limite_baixo=0.5):
    """Lê um sinal de brilho relativo e devolve as rajadas de piscadas: lista de dicts (inicio, duracao, ciclos,
    frequencia em Hz, profundidade 0..1) e a fração do tempo em rajada.

    Uma piscada é uma queda do brilho abaixo de `limite_baixo`; piscadas separadas por menos de 0,4 s são da mesma rajada.
    """
    baixo = ganho < limite_baixo
    descidas = np.nonzero(baixo[1:] & ~baixo[:-1])[0] + 1
    if descidas.size == 0:
        return [], 0.0
    grupos, atual = [], [descidas[0]]
    for k in descidas[1:]:
        if t[k] - t[atual[-1]] < 0.4:
            atual.append(k)
        else:
            grupos.append(atual)
            atual = [k]
    grupos.append(atual)
    rajadas = []
    for grupo in grupos:
        inicio, fim = t[grupo[0]], t[grupo[-1]]
        ciclos = len(grupo)
        freq = (ciclos - 1) / (fim - inicio) if ciclos > 1 and fim > inicio else float("nan")
        janela = (t >= inicio - 0.05) & (t <= fim + 0.25)
        rajadas.append({"inicio": float(inicio), "duracao": float(fim - inicio), "ciclos": ciclos, "frequencia": float(freq),
                        "profundidade": float(1.0 - np.min(ganho[janela]))})
    em_rajada = sum(r["duracao"] + 0.25 for r in rajadas) / (t[-1] - t[0])
    return rajadas, float(min(em_rajada, 1.0))


# --------------------------------------------------------------------------
# TV
# --------------------------------------------------------------------------
CAMPOS_POR_SEGUNDO = 60.0 / 1.001            # NTSC: 59,94 Hz
PIXELS_ATIVOS = 300_000


def flutuacao_do_ruido():
    """DERIVADO: flutuação relativa da luz média de N pixels de brilho independente (desvio da média / média), ~1/raiz(N)."""
    return 1.0 / math.sqrt(PIXELS_ATIVOS)
