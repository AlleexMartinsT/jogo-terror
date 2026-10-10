"""Pegar do chão como o corpo faz: a descida e a subida do olho, medidas no mocap da CMU.

    python -m tools.movimento_ref.pegar_baixo       # mede os clipes de CLIPES e grava assets/referencia/pegar_baixo_ref.json

Para cada clipe acha o primeiro mergulho do olho (a altura cai pelo menos `PROFUNDIDADE_MINIMA` abaixo da altura em pé) e
mede, com a escala do Daniel (olho a 1,65 m): quanto o olho desce, quanto avança em relação aos pés, a flexão do tronco e do
joelho, o tempo de descida e de subida e a altura da mão mais baixa. Os clipes de "walk up to object" têm marcha antes e
depois: o avanço é medido contra o ponto médio dos tornozelos, não contra o mundo.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from tools.movimento_ref import metricas  # noqa: E402
from tools.movimento_ref.movimento import INDICE  # noqa: E402

ARQUIVO = os.path.join(ROOT, "assets", "referencia", "pegar_baixo_ref.json")
OLHO_DANIEL = 1.65
PROFUNDIDADE_MINIMA = 0.25           # m na escala do Daniel
MARGEM_EM_PE = 0.03                  # m abaixo da altura em pé que conta como "ainda em pé"

# clipe -> (técnica, o que é). Todos têm um objeto no chão ou perto dele. Os 115_xx (caixa, dobrando a cintura ou os joelhos)
# ficaram de fora: o mergulho do olho leva 0,3 s neles, de 3 a 6 vezes mais rápido que nos outros, sinal de outra tarefa (pegar
# uma caixa numa cadência de laboratório) ou de uma taxa de quadros que o arquivo não declara bem.
CLIPES = {
    "26_09": ("curvar", "abaixar e pegar"), "26_10": ("curvar", "abaixar e levantar"), "26_11": ("curvar", "abaixar e levantar"),
    "69_70": ("agachar", "andar, agachar, pegar"), "69_71": ("agachar", "andar, agachar, pegar"),
    "69_75": ("agachar", "andar, agachar, pegar"), "69_73": ("curvar", "andar, inclinar, pegar"),
    "69_74": ("curvar", "andar, inclinar, pegar"),
    "143_10": ("agachar", "andar e pegar caixa de ferramentas"), "143_11": ("agachar", "andar e pegar caixa"),
    "111_17": ("curvar", "pegar"), "111_18": ("curvar", "pegar"),
}


def medir_clipe(clip_id, tecnica):
    from tools.movimento_ref import cmu, movimento
    mov = movimento.movimento_de_mocap(cmu.carregar(clip_id), inicio=0.0)
    return medir_movimento(mov, clip_id, tecnica)


def medir_movimento(mov, nome, tecnica="", olho_do_jogo=OLHO_DANIEL):
    """As medidas de um `Movimento` (mocap ou gravação do jogo) que tem um mergulho do olho; None se não houver."""
    clip_id = nome
    fps = mov.fps
    piso = metricas.altura_do_piso(mov)
    olho = mov.j("olho")
    altura = metricas.gaussiano(olho[:, 2:3], 0.05, fps)[:, 0] - piso
    em_pe = float(np.percentile(altura, 92))
    escala = olho_do_jogo / em_pe
    limite = em_pe - PROFUNDIDADE_MINIMA / escala
    abaixo = np.nonzero(altura < limite)[0]
    if len(abaixo) == 0:
        return None
    fundo = abaixo[0]
    while fundo + 1 < len(altura) and altura[fundo + 1] <= altura[fundo]:
        fundo += 1
    minimo = int(fundo)
    inicio = minimo
    while inicio > 0 and altura[inicio] < em_pe - MARGEM_EM_PE / escala:
        inicio -= 1
    fim = minimo
    while fim + 1 < len(altura) and altura[fim] < em_pe - MARGEM_EM_PE / escala:
        fim += 1
    # a descida acaba e o fundo dura um instante: o "fundo" é onde a altura está a 10% do mínimo
    perto = np.nonzero(altura[inicio:fim + 1] < altura[minimo] + 0.10 * (em_pe - altura[minimo]))[0] + inicio
    chegada, saida = int(perto[0]), int(perto[-1])
    pes = 0.5 * (mov.j("tornozelo_e") + mov.j("tornozelo_d"))
    _inst, frente = metricas.frentes(mov)
    rumo = frente[inicio]
    relativo = (olho[:, :2] - pes[:, :2]) @ rumo
    avanco = (relativo - relativo[inicio]) * escala
    ang = metricas.angulos(mov)
    joelho = 0.5 * (ang["joelho_e"] + ang["joelho_d"])
    quadril = 0.5 * (ang["quadril_e"] + ang["quadril_d"])
    tronco = ang["tronco_incl"]
    alvo = slice(inicio, fim + 1)
    punhos = {lado: mov.j(f"punho_{lado}")[:, 2] - piso for lado in "ed"}
    lado = min(punhos, key=lambda k: punhos[k][alvo].min())
    quadril_z = metricas.gaussiano(mov.j("quadril")[:, 2:3], 0.05, fps)[:, 0] - piso
    quadril_queda = (float(np.percentile(quadril_z, 92)) - float(quadril_z[alvo].min())) * escala
    cabeca = mov.cabeca_rot
    olhar = np.einsum("tij,j->ti", cabeca, np.array([0.0, 0.0, -1.0]))
    arfagem = np.degrees(np.arcsin(np.clip(olhar[:, 2], -1, 1)))
    quadros = np.arange(inicio, fim + 1)
    # curvas normalizadas: 0 = em pé na descida, 1 = fundo; 1 = fundo, 0 = em pé na subida
    def _curva(serie, a, b):
        return np.interp(np.linspace(0, 1, 21), np.linspace(0, 1, b - a + 1), serie[a:b + 1])
    profundidade = (em_pe - altura) * escala
    descida = {"profundidade": _curva(profundidade, inicio, chegada), "avanco": _curva(avanco, inicio, chegada),
               "tronco": _curva(tronco - tronco[inicio], inicio, chegada), "joelho": _curva(joelho - joelho[inicio], inicio, chegada)}
    subida = {"profundidade": _curva(profundidade, saida, fim), "avanco": _curva(avanco, saida, fim),
              "tronco": _curva(tronco - tronco[inicio], saida, fim), "joelho": _curva(joelho - joelho[inicio], saida, fim)}
    # a mão mais baixa chega ao chão antes ou depois do olho chegar ao fundo
    t_mao = int(np.argmin(punhos[lado][alvo])) + inicio
    return {
        "clipe": clip_id, "tecnica": tecnica, "escala": round(float(escala), 4),
        "profundidade_m": round(float(profundidade[minimo]), 3), "avanco_m": round(float(avanco[minimo]), 3),
        "tronco_graus": round(float((tronco - tronco[inicio])[alvo].max()), 1),
        "joelho_graus": round(float((joelho - joelho[inicio])[alvo].max()), 1),
        "quadril_graus": round(float((quadril - quadril[inicio])[alvo].max()), 1), "quadril_queda_m": round(quadril_queda, 3),
        "arfagem_graus": round(float((arfagem - arfagem[inicio])[alvo].min()), 1),
        "descida_s": round((chegada - inicio) / fps, 3), "fundo_s": round((saida - chegada) / fps, 3),
        "subida_s": round((fim - saida) / fps, 3), "total_s": round((fim - inicio) / fps, 3),
        "mao": lado, "mao_altura_m": round(float(punhos[lado][t_mao] * escala), 3),
        "mao_instante_do_fundo": round(float((t_mao - inicio) / max(fim - inicio, 1)), 3),
        "inicio_s": round(inicio / fps, 3), "fim_s": round(fim / fps, 3),
        "descida": {k: np.round(v, 4).tolist() for k, v in descida.items()},
        "subida": {k: np.round(v, 4).tolist() for k, v in subida.items()},
    }


def resumir(medidas):
    resumo = {}
    for tecnica in ("curvar", "agachar"):
        grupo = [m for m in medidas if m["tecnica"] == tecnica]
        if not grupo:
            continue
        item = {"n": len(grupo)}
        for chave in ("profundidade_m", "avanco_m", "tronco_graus", "joelho_graus", "quadril_graus", "arfagem_graus",
                      "descida_s", "fundo_s", "subida_s", "total_s", "mao_altura_m", "quadril_queda_m"):
            valores = np.array([m[chave] for m in grupo])
            item[chave] = {"mediana": round(float(np.median(valores)), 3), "min": round(float(valores.min()), 3),
                           "max": round(float(valores.max()), 3)}
        for fase in ("descida", "subida"):
            item[fase] = {k: np.round(np.median([m[fase][k] for m in grupo], axis=0), 4).tolist()
                          for k in ("profundidade", "avanco", "tronco", "joelho")}
        resumo[tecnica] = item
    return resumo


def main():
    medidas = []
    for clip_id, (tecnica, _descricao) in CLIPES.items():
        try:
            medida = medir_clipe(clip_id, tecnica)
        except Exception as erro:          # clipe que não baixou não derruba os outros
            print(f"{clip_id}: erro {erro}")
            continue
        if medida is None:
            print(f"{clip_id}: sem mergulho do olho de {PROFUNDIDADE_MINIMA} m")
            continue
        medidas.append(medida)
        print(f"{clip_id} {tecnica:8s} desce {medida['profundidade_m']:.2f} m avanca {medida['avanco_m']:+.2f} m "
              f"tronco {medida['tronco_graus']:5.1f} joelho {medida['joelho_graus']:5.1f} arfagem {medida['arfagem_graus']:5.1f} "
              f"descida {medida['descida_s']:.2f}s fundo {medida['fundo_s']:.2f}s subida {medida['subida_s']:.2f}s "
              f"mao {medida['mao_altura_m']:.2f} m quadril cai {medida['quadril_queda_m']:.2f}")
    resumo = resumir(medidas)
    os.makedirs(os.path.dirname(ARQUIVO), exist_ok=True)
    with open(ARQUIVO, "w", encoding="utf-8") as arquivo:
        json.dump({"clipes": medidas, "resumo": resumo}, arquivo, ensure_ascii=False, indent=1)
    for tecnica, item in resumo.items():
        print(f"\n{tecnica} (n={item['n']}):", {k: v["mediana"] for k, v in item.items() if isinstance(v, dict) and "mediana" in v})
    print(f"\ngravado em {os.path.relpath(ARQUIVO, ROOT)}")


if __name__ == "__main__":
    main()
