"""Cortinas, poeira e luzes: grava o jogo, roda os modelos físicos e monta a tabela de métricas.

    python -m tools.movimento_ref.fisica.comparar_ambiente [--antes]
"""
import math
import sys

import numpy as np

from . import cortina as KC
from . import grava, luz as KL, medidas

Metrica = medidas.Metrica
G = 9.81


def gravar(antes=False):
    out = {"cortina": grava.cortina(antes=antes), "poeira": grava.poeira(duracao=12.0, antes=antes)}
    if not antes:                      # as luzes de antes foram gravadas antes de mexer em engine/lights.py
        out["luzes"] = grava.luzes()
    return out


# --------------------------------------------------------------------------
# Cortina
# --------------------------------------------------------------------------
def perfil_de_amplitude(c):
    """RMS da oscilação (sem a média) em cada altura, dividido pelo da bainha, numa coluna do meio da cortina."""
    desloc = c["deslocamento"][:, 0, :, 1]
    rms = np.std(desloc - desloc.mean(axis=0), axis=0)
    return c["fracoes"], rms / rms[-1]


def fatia_de_energia(t, y, banda=(0.3, 1.0), minimo=0.1):
    freq, pot = KC.espectro(t, y, minimo)
    dentro = (freq >= banda[0]) & (freq <= banda[1])
    return float(pot[dentro].sum() / pot.sum())


def fator_de_crista(y):
    d = y - np.mean(y)
    return float(np.max(np.abs(d)) / np.std(d))


def metricas_cortina(c):
    out = []
    t = c["t"]
    hem = c["deslocamento"][:, 0, -1, 1]
    f1 = float(KC.frequencias_dos_modos(c["altura"])[0])
    ts, yb, _ = KC.simular(c["altura"], duracao=600.0)
    pico = KC.pico_do_espectro(t, hem)
    out.append(Metrica.igual("cortina", "frequência dominante da bainha", "Hz", f1, pico, 0.25,
                             nota=f"1o modo da corrente pendurada, H = {c['altura']:.2f} m (modelo temporal: {KC.pico_do_espectro(ts, yb):.2f} Hz)"))
    fatia_fisica = fatia_de_energia(ts, yb)
    out.append(Metrica("cortina", "energia entre 0,3 e 1 Hz (acima de 0,1 Hz)", "fração", fatia_fisica,
                       fatia_de_energia(t, hem), 0.5 * fatia_fisica, min(1.0, 1.3 * fatia_fisica), fonte="ESTIMADO",
                       nota="o vento de von Karman excita os modos; o pano filtra"))
    fracoes, perfil_jogo = perfil_de_amplitude(c)
    alturas_ref, rms_ref = _perfil_fisico(c["altura"])
    perfil_fis = rms_ref / rms_ref[-1]
    out.append(Metrica.igual("cortina", "perfil de amplitude cima-baixo (maior diferença)", "fração da bainha", 0.0,
                             float(np.max(np.abs(perfil_jogo - perfil_fis))), 0.15, relativa=False,
                             nota="RMS da oscilação a 10 alturas, contra os 3 modos integrados no tempo"))
    cr = fator_de_crista(hem)
    cr_fis = fator_de_crista(yb)
    out.append(Metrica("cortina", "fator de crista do deslocamento (rajadas)", "-", cr_fis, cr, 0.7 * cr_fis, 1.4 * cr_fis,
                       fonte="ESTIMADO", nota="processo aleatório gaussiano: pico/RMS ~ 3 em minutos"))
    return out


def _perfil_fisico(altura, duracao=600.0, fps=60.0):
    rng = np.random.default_rng(0)
    n = int(duracao * fps)
    freq = np.fft.rfftfreq(n, 1.0 / fps)
    amp = np.sqrt(KC.espectro_do_vento(freq))
    ruido = np.fft.irfft(amp * (rng.normal(size=len(freq)) + 1j * rng.normal(size=len(freq))), n)
    ruido /= np.std(ruido)
    alturas = np.linspace(0.1, 1.0, 10)
    f = KC.frequencias_dos_modos(altura, 3)
    resposta = np.zeros((n, len(alturas)))
    w1 = 2.0 * math.pi * f[0]
    for k in range(3):
        w = 2.0 * math.pi * f[k]
        q, v, h = 0.0, 0.0, 1.0 / fps
        gama = KC.participacao(k + 1)
        formas = KC.forma_do_modo(alturas, k + 1)
        serie = np.zeros(n)
        for i in range(n):
            for _ in range(4):
                a = gama * ruido[i] * w1 * w1 - 2.0 * KC.ZETA_PANO * w * v - w * w * q
                v += a * h / 4
                q += v * h / 4
            serie[i] = q
        resposta += serie[:, None] * formas[None, :]
    return alturas, np.std(resposta, axis=0)


# --------------------------------------------------------------------------
# Poeira
# --------------------------------------------------------------------------
def velocidades_terminais_do_jogo(p):
    """Velocidade terminal de cada partícula (m/s), pela inclinação do fim da vida dela, e o tempo de relaxação medido."""
    t, z, tam = p["t"], p["z"], p["tamanho"]
    fps = p["fps"]
    v_term, tau = [], []
    for j in range(z.shape[1]):
        vivo = np.nonzero(tam[:, j] > 0)[0]
        if len(vivo) < 8:
            continue
        zz = z[vivo, j]
        vel = -np.gradient(zz, 1.0 / fps)
        final = vel[-max(4, len(vel) // 4):]
        vt = float(np.median(final))
        v_term.append(vt)
        alcanca = np.nonzero(vel >= 0.632 * vt)[0]
        tau.append(float(alcanca[0] / fps) if alcanca.size and vt > 0.4 else np.nan)
    return np.array(v_term), np.array(tau)


def ks(a, b):
    """Estatística de Kolmogorov-Smirnov de duas amostras."""
    todos = np.sort(np.concatenate([a, b]))
    cdf = lambda x: np.searchsorted(np.sort(x), todos, side="right") / len(x)      # noqa: E731
    return float(np.max(np.abs(cdf(a) - cdf(b))))


def amostra_fisica(n=20000, semente=1):
    rng = np.random.default_rng(semente)
    classes = KC.classes_de_poeira()
    v = []
    for _ in range(n):
        u = rng.random()
        if u < classes[0][2]:
            d = classes[0][1][0] * (classes[0][1][1] / classes[0][1][0]) ** rng.random()
            v.append(float(KC.velocidade_terminal(d)))
        elif u < classes[0][2] + classes[1][2]:
            d = classes[1][1][0] * (classes[1][1][1] / classes[1][1][0]) ** rng.random()
            v.append(float(KC.velocidade_terminal(d)))
        else:
            lado, esp = 0.004 + 0.006 * rng.random(), 0.001 + 0.001 * rng.random()
            massa = KC.RHO_REBOCO * lado * lado * esp
            v.append(math.sqrt(2 * massa * G / (KC.RHO_AR * 1.3 * lado * lado)))
    return np.array(v)


def metricas_poeira(p):
    out = []
    vt, tau = velocidades_terminais_do_jogo(p)
    fisica = amostra_fisica()
    fina = vt[vt < 0.15]
    out.append(Metrica("poeira", "velocidade terminal da poeira fina (mediana)", "m/s", float(np.median(fisica[fisica < 0.15])),
                       float(np.median(fina)) if fina.size else float(np.median(vt)), 0.02, 0.10, fonte="DERIVADO",
                       nota="poeira de 20 a 45 micra, Schiller-Naumann: poucos cm/s"))
    out.append(Metrica("poeira", "fração de partículas de poeira fina (< 15 cm/s)", "fração", float(np.mean(fisica < 0.15)),
                       float(np.mean(vt < 0.15)), 0.5, 0.8, fonte="ESTIMADO"))
    out.append(Metrica.limite_max("poeira", "distância KS da distribuição de log v contra a física", "-", 0.2,
                                  ks(np.log10(vt), np.log10(fisica)), fonte="DERIVADO"))
    rapidas = vt > 0.4
    if rapidas.any():
        # física: tau = v_t / g para cada partícula rápida
        esperado = vt[rapidas] / G
        medido = tau[rapidas]
        bons = ~np.isnan(medido)
        razao = float(np.median(medido[bons] / esperado[bons])) if bons.any() else float("nan")
        out.append(Metrica.igual("poeira", "tempo de relaxação medido / (v_t / g) nas partículas rápidas", "-", 1.0, razao, 0.4))
    return out


# --------------------------------------------------------------------------
# Luzes
# --------------------------------------------------------------------------
def tempo_para(t, sinal, nivel, subindo, a_partir_de):
    k0 = int(np.searchsorted(t, a_partir_de))
    s = sinal[k0:]
    ok = np.nonzero(s >= nivel)[0] if subindo else np.nonzero(s <= nivel)[0]
    return float(t[k0 + ok[0]] - a_partir_de) if ok.size else float("inf")


def metricas_luzes(l):
    out = []
    off_fis, on_fis = KL.tempos_de_resposta()
    liga = l["liga_desliga"]["ceiling"]
    t, e, base = liga["t"], liga["energia"], liga["base"]
    t_desliga = tempo_para(t, e, 0.10 * base, False, 0.5)
    t_liga = tempo_para(t, e, 0.90 * base, True, 1.5)
    out.append(Metrica.igual("luz", "incandescente: tempo para cair a 10% ao desligar", "s", off_fis, max(t_desliga, 1e-4), 0.4,
                             fonte="DERIVADO", nota="filamento de 60 W: tau = 34 ms, luz ~ T^9,3"))
    out.append(Metrica.igual("luz", "incandescente: tempo para subir a 90% ao ligar", "s", on_fis, max(t_liga, 1e-4), 0.4,
                             fonte="DERIVADO"))
    fl = l["liga_desliga"]["fluorescent"]
    out.append(Metrica.limite_max("luz", "fluorescente: tempo para cair a 10% ao desligar", "s", 0.02,
                                  tempo_para(fl["t"], fl["energia"], 0.10 * fl["base"], False, 0.5), fonte="ESTIMADO",
                                  nota="o arco se apaga na hora; o fósforo persiste alguns ms"))
    for nome, quantidade in (("garagem", "fluorescente_garagem"), ("cozinha", "fluorescente_cozinha")):
        s = l["pisca"][quantidade]
        rajadas, fracao = KL.estatisticas_de_rajadas(s["t"], s["ganho"])
        freq = float(np.median([r["frequencia"] for r in rajadas if not math.isnan(r["frequencia"])])) if any(
            not math.isnan(r["frequencia"]) for r in rajadas) else 0.0
        profundidade = float(np.median([r["profundidade"] for r in rajadas])) if rajadas else float(1.0 - s["ganho"].min())
        out.append(Metrica("luz", f"fluorescente ({nome}): frequência das piscadas dentro de uma rajada", "Hz", 6.0, freq, 3.0, 10.0,
                           fonte="ESTIMADO", nota="reator ruim: 3 a 10 Hz"))
        out.append(Metrica.limite_min("luz", f"fluorescente ({nome}): profundidade da piscada", "0..1", 0.8, profundidade,
                                      fonte="ESTIMADO", nota="o arco apaga de verdade"))
        out.append(Metrica.limite_max("luz", f"fluorescente ({nome}): fração do tempo em rajada", "fração", 0.45, fracao,
                                      fonte="ESTIMADO", nota="longos trechos estáveis entre as rajadas"))
    tv = l["pisca"]["tv"]["ganho"]
    out.append(Metrica.limite_max("luz", "TV de chuvisco: variação RMS da luz da sala", "fração", 0.04, float(np.std(tv) / np.mean(tv)),
                                  fonte="ESTIMADO", nota=f"o ruído por si só varia ~{KL.flutuacao_do_ruido():.1e} (1/raiz N)"))
    return out


# --------------------------------------------------------------------------
def metricas(g):
    return metricas_cortina(g["cortina"]) + metricas_poeira(g["poeira"]) + metricas_luzes(g["luzes"])


def metricas_com_antes(g):
    lista = metricas(g)
    antes = {nome: medidas.carregar_gravacao(nome) for nome in ("cortina", "poeira", "luzes")}
    if all(v is not None for v in antes.values()):
        medidas.completar_antes(lista, metricas(antes))
    return lista


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--antes" in argv:
        for nome, valor in gravar(antes=True).items():
            medidas.salvar_gravacao(nome, valor)
    g = gravar()
    for nome in ("cortina", "poeira", "luzes"):
        medidas.salvar_gravacao(nome, g[nome], pasta=medidas.DEPOIS)
    lista = metricas_com_antes(g)
    print(medidas.tabela_markdown(lista))
    return lista


if __name__ == "__main__":
    main()
