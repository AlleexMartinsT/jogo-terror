"""Tabela das métricas MEDIDAS nos clipes reais de referência (cmu.REFERENCIAS): o que o jogo tem de alcançar.

    python -m tools.movimento_ref.referencias                       # escreve out/movimento/referencias_medidas.md
    python -m tools.movimento_ref.referencias --saida docs/movimento/referencias_medidas.md

Clipes de marcha entram com ritmo, passo, apoio, oscilações e picos articulares; clipes de gesto (pegar, alcançar, empurrar,
lanterna) entram com o perfil de velocidade da mão. Tudo sai das mesmas funções de `metricas.py` que medem o jogo. Cada
linha diz o método de eventos usado e quantas passadas completas o clipe tem: com 1 ou 2, trate o valor como indicativo.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from tools.movimento_ref import cmu, metricas  # noqa: E402
from tools.movimento_ref.movimento import movimento_de_mocap  # noqa: E402

MARCHA = ("andar", "andar_2", "andar_devagar", "andar_parar", "correr", "curva", "furtivo", "rastejar", "agachado", "escada",
          "degraus", "cuidado")
GESTOS = ("pegar_chao", "alcancar", "empurrar", "lanterna", "pegar_chaves", "levantar", "sentar_levantar")
COLUNAS_MARCHA = (("velocidade", "v (m/s)", 2), ("cadencia", "cad. (passos/min)", 0), ("passada", "passada (m)", 2),
                  ("passo", "passo (m)", 2), ("apoio_pct", "apoio (%)", 0), ("duplo_apoio_passo_pct", "2x apoio (%)", 0),
                  ("voo_pct", "voo (%)", 0), ("quadril_altura", "quadril (m)", 2), ("cabeca_osc_vert", "cabeça vert. (cm)", 1),
                  ("cabeca_osc_lat", "cabeça lat. (cm)", 1), ("joelho_apoio_max", "joelho apoio (°)", 0),
                  ("joelho_balanco_max", "joelho balanço (°)", 0), ("tronco_inclinacao", "tronco (°)", 0))
CENTIMETROS = {"cabeca_osc_vert", "cabeca_osc_lat"}


def _formatar(valor, casas, chave):
    if valor is None or not np.isfinite(valor):
        return "--"
    return f"{valor * (100 if chave in CENTIMETROS else 1):.{casas}f}"


def medir_marcha_clipe(clip_id, metodo="auto"):
    mov = movimento_de_mocap(cmu.carregar(clip_id))
    marcha = metricas.medir_tudo(mov, metodo)
    passadas = sum(max(0, len(marcha.eventos.toque[l]) - 1) for l in "ed")
    return mov, marcha, passadas


def medir_gesto_clipe(clip_id):
    """Melhor alcance da mão (o de maior pico de velocidade) entre as duas mãos."""
    mov = movimento_de_mocap(cmu.carregar(clip_id))
    melhor = None
    for lado in "ed":
        velocidade = metricas.perfil_mao(mov, lado)
        for a, b in metricas.detectar_alcances(velocidade, mov.fps, vel_minima=0.4):
            ajuste = metricas.ajuste_jerk_minimo(velocidade, a, b, mov.fps)
            if ajuste and (melhor is None or ajuste["velocidade_pico"] > melhor[1]["velocidade_pico"]):
                melhor = (lado, ajuste, a / mov.fps)
    return mov, melhor


def gerar(saida):
    linhas = ["# Métricas medidas nos clipes reais de referência (CMU)", "",
              "Medido com `tools/movimento_ref/metricas.py` (MEDIDO, não estimado). Passadas = passadas completas observadas "
              "(pés esquerdo e direito somados); com menos de 3 trate como indicativo. Velocidade é a do quadril.", "",
              "## Marcha", ""]
    cabecalho = ["clipe", "gesto", "método", "passadas"] + [c[1] for c in COLUNAS_MARCHA]
    linhas.append("| " + " | ".join(cabecalho) + " |")
    linhas.append("|" + "|".join("---" for _ in cabecalho) + "|")
    for nome in MARCHA:
        clip_id, motivo = cmu.REFERENCIAS[nome]
        try:
            mov, marcha, passadas = medir_marcha_clipe(clip_id)
        except Exception as erro:       # noqa: BLE001
            linhas.append(f"| {clip_id} | {nome} | -- | -- |" + " -- |" * len(COLUNAS_MARCHA) + f" erro: {erro}")
            continue
        velocidade = marcha.v.get("velocidade", float("nan"))
        metodo = "altura" if (np.isfinite(velocidade) and velocidade ** 2 / (9.81 * metricas.comprimento_perna(mov)) > metricas.FROUDE_CORRIDA) else "zeni"
        celulas = [clip_id, nome, metodo, str(passadas)] + [_formatar(marcha.v.get(c, float("nan")), casas, c) for c, _, casas in COLUNAS_MARCHA]
        linhas.append("| " + " | ".join(celulas) + " |")
    linhas += ["", "## Gestos da mão (perfil de velocidade do melhor alcance)", "",
               "| clipe | gesto | mão | início (s) | duração (s) | distância (m) | pico (m/s) | pico em % da duração | pico/média | R² jerk mínimo |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for nome in GESTOS:
        clip_id, motivo = cmu.REFERENCIAS[nome]
        try:
            _mov, melhor = medir_gesto_clipe(clip_id)
        except Exception as erro:       # noqa: BLE001
            linhas.append(f"| {clip_id} | {nome} | erro: {erro} |")
            continue
        if melhor is None:
            linhas.append(f"| {clip_id} | {nome} | -- | -- | -- | -- | -- | -- | -- | -- |")
            continue
        lado, a, inicio = melhor
        linhas.append(f"| {clip_id} | {nome} | {'esq.' if lado == 'e' else 'dir.'} | {inicio:.2f} | {a['duracao']:.2f} | {a['distancia']:.2f} | "
                      f"{a['velocidade_pico']:.2f} | {100 * a['pico_fracao']:.0f} | {a['pico_razao']:.2f} | {a['r2_jerk_minimo']:.2f} |")
    linhas += ["", "Jerk mínimo teórico: pico em 50% da duração, pico/média = 1,875, R² = 1.", ""]
    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas))
    return "\n".join(linhas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saida", default=os.path.join(ROOT, "out", "movimento", "referencias_medidas.md"))
    args = ap.parse_args(argv)
    print(gerar(args.saida))
    return 0


if __name__ == "__main__":
    sys.exit(main())
