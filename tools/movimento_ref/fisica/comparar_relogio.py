"""Relógio de pé: grava o mecanismo do jogo, roda o modelo físico e monta a tabela de métricas.

    python -m tools.movimento_ref.fisica.comparar_relogio
"""
import math
import sys

import numpy as np

from . import grava, medidas, relogio as R

Metrica = medidas.Metrica
GRUPO = "relógio"
HASTE_ANTIGA = 0.54            # m: o pêndulo do modelo antigo (props/clock.py antes da fase 4), parado a 7 graus
ANTES = {"periodo_modelo": R.periodo(R.comprimento_equivalente(HASTE_ANTIGA), math.radians(7.0)), "amplitude": 0.0,
         "atraso": float("nan"), "sincronia": float("nan"), "passo": 0.0, "tiques": 0.0, "periodo": float("nan")}


def cruzamentos(t, theta):
    sinal = np.sign(theta)
    k = np.nonzero(sinal[1:] * sinal[:-1] < 0)[0]
    # interpolação linear do zero
    return t[k] + (0 - theta[k]) * (t[k + 1] - t[k]) / (theta[k + 1] - theta[k])


def metricas(g, haste=None):
    out = []
    add = out.append
    t, theta = g["t"], g["theta"]
    cz = cruzamentos(t, theta)
    periodo_jogo = float(2.0 * np.mean(np.diff(cz)))
    ref_t, ref_theta, ref_tiques = R.simular(60.0, R.comprimento_equivalente(R.comprimento_para_periodo(2.0)))
    ref_cz = cruzamentos(ref_t, ref_theta)
    periodo_ref = float(2.0 * np.mean(np.diff(ref_cz)))
    add(Metrica.igual(GRUPO, "pêndulo: período medido", "s", periodo_ref, periodo_jogo, 0.01, fonte="DERIVADO",
                      nota="pêndulo de segundos: l_eq = 0,994 m, T = 2 s; o modelo temporal dá a referência"))
    if haste is None:
        from sem_alvorada.props import clock
        haste = clock.PENDULUM_LENGTH
    periodo_modelo = R.periodo(R.comprimento_equivalente(haste), g["amplitude"])
    add(Metrica.igual(GRUPO, "modelo 3D: período do pêndulo que a geometria da haste e da lentilha dá", "s", 2.0, periodo_modelo, 0.01,
                      fonte="DERIVADO", nota=f"haste de {haste:.3f} m do pivô ao centro da lentilha; antes: {ANTES['periodo_modelo']:.3f} s"))
    amplitude = math.degrees(float(np.max(np.abs(theta[len(theta) // 2:]))))
    add(Metrica("relógio", "pêndulo: amplitude (cada lado)", "graus", 2.5, amplitude, 2.0, 4.0, fonte="ESTIMADO"))
    # o tique em relação ao centro do arco e ao laço de áudio
    tiques = g["tiques"]
    atrasos = []
    for tq in tiques[2:-1]:
        antes = cz[cz <= tq]
        if antes.size:
            atrasos.append(tq - antes[-1])
    atraso = float(np.median(atrasos))
    add(Metrica("relógio", "tique depois do centro do arco", "s", 0.025, atraso, 0.010, 0.040, fonte="ESTIMADO",
                nota="o dente cai logo depois do impulso"))
    esperados = 0.5 + np.arange(len(tiques))
    esperados = esperados[:len(tiques)]
    erro = np.abs(tiques[2:len(tiques)] - 0.5 - np.round(tiques[2:] - 0.5))
    add(Metrica.limite_max(GRUPO, "tique contra o tique do laço de áudio amb_clock_tick (pior)", "s", 0.030, float(erro.max()),
                           fonte="DERIVADO", nota="o laço tem um tique em 0,5 s + k"))
    add(Metrica.igual(GRUPO, "ponteiro dos segundos: tiques em 60 s", "-", 60.0, float(len(tiques)), 0.02, fonte="DERIVADO"))
    mao = g["mao"]
    degrau = []
    for tq in tiques[2:-3]:
        i_antes = int((tq - 0.05) * g["fps"])
        i_depois = int((tq + 0.45) * g["fps"])
        degrau.append(math.degrees(mao[i_depois] - mao[i_antes]))
    add(Metrica.igual(GRUPO, "ponteiro dos segundos: avanço por tique", "graus", 6.0, float(np.median(degrau)), 0.02, fonte="DERIVADO",
                      nota="60 dentes, um por segundo"))
    sobre = []
    for tq in tiques[2:-3]:
        i0, i1 = int((tq - 0.03) * g["fps"]), int((tq + 0.40) * g["fps"])
        fim = mao[i1]
        sobre.append(math.degrees(np.max(mao[i0:i1]) - fim))
    add(Metrica.limite_max(GRUPO, "ponteiro dos segundos: ultrapassagem depois do salto", "graus", 1.5, float(np.max(sobre)),
                           fonte="ESTIMADO"))
    return out


def tabela_antes(lista):
    """As gravações de antes não existem (o pêndulo não se mexia): os valores de antes vêm do modelo antigo."""
    rotulos = {"pêndulo: período medido": ANTES["periodo"], "pêndulo: amplitude (cada lado)": 0.0,
               "modelo 3D: período do pêndulo que a geometria da haste e da lentilha dá": ANTES["periodo_modelo"],
               "ponteiro dos segundos: tiques em 60 s": 0.0, "ponteiro dos segundos: avanço por tique": 0.0}
    for m in lista:
        if m.nome in rotulos:
            m.antes = rotulos[m.nome]
    return lista


def main(argv=None):
    g = grava.relogio()
    lista = tabela_antes(metricas(g))
    print(medidas.tabela_markdown(lista))
    return lista


if __name__ == "__main__":
    main()
