"""Extrai do mocap da CMU os números que o corpo do jogo usa para andar, correr e andar agachado.

    python -m tools.marcha.extrair            # escreve sem_alvorada/body/gait_data.py e assets/referencia/marcha_ref.json

Entrada: os BVH em `out/referencia/cmu` (baixados por `python -m tools.movimento_ref.cmu` e pelos IDs de `GRUPOS`).
Saída:
  sem_alvorada/gait_data.py   tabelas por tempo de passada (50 amostras), uma por faixa de velocidade, mais as leis de comprimento
                     do passo. É o que roda no jogo (o jogo não lê BVH).
  marcha_ref.json    as mesmas faixas com média e desvio por % da passada, e os escalares com desvio entre clipes;
                     é a referência que `tests/test_locomocao.py` e os gráficos usam.

Todas as tabelas são MEDIDAS: média de todas as passadas de todos os clipes da faixa, com os dois pés dobrados em um só
(o pé direito é o esquerdo deslocado meio ciclo). Comprimentos de pé em unidades de comprimento da perna (coxa + canela do
sujeito), para valerem para o Daniel (0,845 m).
"""
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.marcha import medir as M  # noqa: E402
from tools.movimento_ref import cmu  # noqa: E402

PONTOS = 50                       # amostras por ciclo nas tabelas do jogo
G = 9.81

# Clipes de caminhada e corrida em linha reta, sujeitos 02 a 39 e 45. A faixa de velocidade decide a que nó cada um vai.
# (Lista explícita: o cache `out/referencia/cmu` é compartilhado e tem clipes de outros usos.)
CLIPES_ANDAR = ("02_01 05_01 06_01 07_01 07_02 07_03 07_04 07_06 07_07 07_08 07_09 07_10 07_11 08_01 08_02 08_03 08_05 08_06 "
                "08_08 08_09 08_10 10_04 12_01 12_02 12_03 16_15 16_16 16_21 16_22 16_31 16_32 16_47 16_58 35_01 35_02 35_03 "
                "35_04 38_01 38_02 39_01 39_02 39_03 39_04 45_01").split()
CLIPES_CORRER = ("09_01 09_02 09_03 09_04 09_05 09_06 09_07 09_08 09_09 09_11 16_35 16_36 16_45 16_46 16_55 16_56 "
                 "35_17 35_18 35_19 35_20 35_21 35_22 35_23 35_24 35_25 35_26 02_03").split()

# faixa -> (modo do jogo, velocidade mínima, máxima). A faixa de agachado vem de trechos a passo contínuo (ver abaixo).
FAIXAS = {
    "andar_lento": ("walk", 0.85, 1.15),
    "andar": ("walk", 1.20, 1.45),
    "andar_rapido": ("walk", 1.55, 1.80),
    "correr": ("run", 3.00, 3.80),
    "correr_rapido": ("run", 3.90, 4.40),
}
AGACHADO = ("136_09", "136_10")

CURVAS_JOGO = ("pe_frente", "pe_lateral", "pe_alt", "pe", "cab_z", "cab_y", "cab_roll", "cab_pitch", "cab_yaw",
               "pelve_yaw", "tronco_yaw", "pelve_roll", "ombro", "cotovelo", "pelvis_z", "pelvis_y")
CURVAS_REF = CURVAS_JOGO + ("quadril", "joelho", "tornozelo", "tronco_incl", "bola_frente", "bola_alt")
UNIDADE_PERNA = ("pe_frente", "pe_lateral", "pe_alt", "bola_frente", "bola_alt")
LEG_DANIEL = 0.845                # coxa 0.43 + canela 0.415 (body/skeleton.py)


def perna(cap):
    return float(np.median(np.linalg.norm(cap.pts["knee_L"] - cap.pts["hip_L"], axis=1))
                 + np.median(np.linalg.norm(cap.pts["ankle_L"] - cap.pts["knee_L"], axis=1)))


def periodico(curva, n=PONTOS):
    """101 amostras de 0 a 100% -> `n` amostras periódicas (descarta a de 100%, que repete a de 0%)."""
    c = np.asarray(curva, float)
    base = c[:-1].copy()
    # o fecho médio das passadas nunca é perfeito: reparte a diferença entre 0% e 100% ao longo da curva
    gap = c[-1] - c[0]
    base = base - gap * np.linspace(0.0, 1.0, len(base), endpoint=False)
    x = np.linspace(0.0, 1.0, len(base), endpoint=False)
    xn = np.linspace(0.0, 1.0, n, endpoint=False)
    ext_x = np.concatenate([x - 1.0, x, x + 1.0])
    ext_y = np.tile(base, 3)
    return np.interp(xn, ext_x, ext_y)


def clipes_da_faixa(lo, hi):
    out = []
    for cid in CLIPES_ANDAR + CLIPES_CORRER:
        cap = M.de_mocap(cmu.carregar(cid))
        v = M.vel_media(cap)
        if lo <= v <= hi:
            out.append((cid, cap))
    return out


def trecho_andando(cap):
    """Maior trecho contínuo a passo estável (pelve a mais de metade do p90 da velocidade)."""
    sm = M.media_movel(cap.pts["pelvis"][:, :2], int(0.5 * cap.fps))
    v = np.linalg.norm(np.gradient(sm, axis=0), axis=1) * cap.fps
    mov = v > 0.5 * np.percentile(v, 90)
    runs = M._runs(mov)
    a, b = max(runs, key=lambda r: r[1] - r[0])
    return cap.cortar(a + int(0.4 * cap.fps), b - int(0.4 * cap.fps))


# curvas periódicas travadas na passada, cuja amplitude por passada (pico a pico) a média achata um pouco porque as
# passadas e as pessoas não coincidem em fase: o jogo repete a passada média, então a amplitude é devolvida
RESTAURAR = ("cab_z", "cab_y", "pelvis_z", "pelvis_y", "pelve_yaw", "tronco_yaw", "ombro", "cotovelo", "pe_alt")
FATOR_MAX = 1.5


def pool_curvas(lista):
    """{nome: (média[101], desvio[101], n, fator)}: `fator` = pico a pico médio por passada / pico a pico da média."""
    pool = {}
    for curvas in lista:
        for k, v in curvas.items():
            pool.setdefault(k, []).append(v)
    out = {}
    for k, v in pool.items():
        A = np.concatenate(v)
        mean = A.mean(axis=0)
        fator = float(np.mean(np.ptp(A, axis=1)) / max(np.ptp(mean), 1e-9))
        out[k] = (mean, A.std(axis=0), len(A), min(fator, FATOR_MAX))
    return out


def processa(clipes):
    """Pool de passadas e escalares de uma lista [(id, Captura)]."""
    pools, escalares = [], []
    for cid, cap in clipes:
        ev = M.eventos(cap)
        m = M.medir(cap, ev)
        m["id"] = cid
        m["perna"] = perna(cap)
        escalares.append(m)
        curvas, _t = M.curvas_por_passada(cap, ev)
        if not curvas:
            continue
        curvas = dict(curvas)
        for k in UNIDADE_PERNA:
            curvas[k] = curvas[k] / m["perna"]
        pools.append(curvas)
    return pool_curvas(pools), escalares


def resumo(escalares):
    out = {}
    chaves = sorted({k for e in escalares for k, v in e.items() if isinstance(v, (int, float, np.floating))})
    for k in chaves:
        a = np.array([e.get(k, np.nan) for e in escalares], float)
        a = a[~np.isnan(a)]
        if len(a):
            out[k] = {"media": float(a.mean()), "dp": float(a.std()), "n": int(len(a)), "min": float(a.min()), "max": float(a.max())}
    return out


def ajuste_passo(todos, lo, hi):
    """passo/perna = a * Fr^b, com Fr = v / raiz(g perna): mínimos quadrados em log. Devolve (a, b, erro_rms_em_perna)."""
    v, l, st = [], [], []
    for e in todos:
        if lo <= e["vel"] <= hi and e.get("cadencia") == e.get("cadencia") and 20 < e["cadencia"] < 200:
            v.append(e["vel"]); l.append(e["perna"]); st.append(e["vel"] / (e["cadencia"] / 60.0))
    v, l, st = map(np.array, (v, l, st))
    fr = v / np.sqrt(G * l)
    b, a = np.polyfit(np.log(fr), np.log(st / l), 1)
    pred = np.exp(a) * fr ** b
    return float(np.exp(a)), float(b), float(np.sqrt(np.mean((pred - st / l) ** 2))), len(v)


def montar():
    faixas, ref, todos = {}, {}, []
    for nome, (modo, lo, hi) in FAIXAS.items():
        clipes = clipes_da_faixa(lo, hi)
        curvas, esc = processa(clipes)
        todos += esc
        resu = resumo(esc)
        faixas[nome] = {"modo": modo, "clipes": [c for c, _ in clipes], "curvas": curvas, "resumo": resu}
        print(f"{nome:14s} n_clipes={len(clipes):2d} v={resu['vel']['media']:.3f}  cadencia={resu.get('cadencia', {}).get('media', float('nan')):.1f}"
              f"  apoio={resu.get('apoio_pct', {}).get('media', float('nan')):.1f}", flush=True)
    # agachado: trecho a passo estável de cada clipe
    clipes = [(cid, trecho_andando(M.de_mocap(cmu.carregar(cid)))) for cid in AGACHADO]
    curvas, esc = processa(clipes)
    resu = resumo(esc)
    faixas["agachado"] = {"modo": "crouch", "clipes": list(AGACHADO), "curvas": curvas, "resumo": resu}
    print(f"{'agachado':14s} n_clipes={len(clipes):2d} v={resu['vel']['media']:.3f}  cadencia={resu['cadencia']['media']:.1f}", flush=True)
    fit_walk = ajuste_passo(todos, 0.85, 1.85)
    fit_run = ajuste_passo(todos, 3.0, 4.4)
    print("passo/perna = a Fr^b  andar:", fit_walk, " correr:", fit_run)
    return faixas, fit_walk, fit_run, todos


def escreve_referencia(faixas, fit_walk, fit_run, caminho):
    saida = {"fonte": "CMU Graphics Lab Motion Capture Database (cgspeed BVH). Médias de passadas, pés dobrados.",
             "leg_daniel": LEG_DANIEL, "ajuste_passo": {"andar": fit_walk, "correr": fit_run}, "faixas": {}}
    for nome, f in faixas.items():
        saida["faixas"][nome] = {
            "modo": f["modo"], "clipes": f["clipes"], "resumo": f["resumo"],
            "curvas": {k: {"media": [round(float(x), 4) for x in v[0]], "dp": [round(float(x), 4) for x in v[1]], "n": int(v[2]),
                           "fator_amp": round(v[3], 3)}
                       for k, v in f["curvas"].items() if k in CURVAS_REF},
        }
    with open(caminho, "w", encoding="utf-8") as arq:
        json.dump(saida, arq, ensure_ascii=False, indent=None, separators=(",", ":"))


def escreve_modulo(faixas, fit_walk, fit_run, caminho):
    linhas = ['"""Tabelas de marcha MEDIDAS em mocap real (CMU Graphics Lab Motion Capture Database).',
              '',
              'Arquivo GERADO por `python -m tools.marcha.extrair`; não edite à mão. Cada nó é uma faixa de velocidade com a',
              'média das passadas dos clipes da faixa (dois pés dobrados em um): curvas de 50 amostras por ciclo, que começa',
              'no toque do calcanhar do pé de referência (esquerdo). Comprimentos do pé em unidades de comprimento da perna.',
              '"""',
              '', f'PONTOS = {PONTOS}', f'LEG_DANIEL = {LEG_DANIEL}', '',
              f'PASSO_ANDAR = {tuple(round(x, 5) for x in fit_walk[:2])}      # passo/perna = a * Fr^b, Fr = v / raiz(g perna)',
              f'PASSO_CORRER = {tuple(round(x, 5) for x in fit_run[:2])}', '', 'NOS = {']
    for modo in ("walk", "run", "crouch"):
        linhas.append(f'    "{modo}": [')
        nos = sorted([(f["resumo"]["vel"]["media"], nome, f) for nome, f in faixas.items() if f["modo"] == modo])
        for v, nome, f in nos:
            r = f["resumo"]
            linhas.append('        {')
            linhas.append(f'            "nome": "{nome}", "v": {v:.4f}, "clipes": {len(f["clipes"])},')
            linhas.append(f'            "cadencia": {r["cadencia"]["media"]:.2f}, "apoio": {r["apoio_pct"]["media"] / 100.0:.4f},'
                          f' "duplo": {r["duplo_apoio_pct"]["media"] / 100.0:.4f},')
            lean = faixas[nome]["curvas"]["tronco_incl"][0].mean() if "tronco_incl" in faixas[nome]["curvas"] else 0.0
            linhas.append(f'            "tronco_incl": {lean:.2f},')
            linhas.append('            "curvas": {')
            for k in CURVAS_JOGO:
                mean = periodico(f["curvas"][k][0])
                if k in RESTAURAR:
                    centro = mean.mean()
                    mean = centro + (mean - centro) * f["curvas"][k][3]
                linhas.append(f'                "{k}": ({", ".join(f"{x:.4f}" for x in mean)}),')
            linhas.append('            },')
            linhas.append('        },')
        linhas.append('    ],')
    linhas.append('}')
    with open(caminho, "w", encoding="utf-8") as arq:
        arq.write("\n".join(linhas) + "\n")


def main():
    faixas, fit_walk, fit_run, _todos = montar()
    ref = os.path.join(ROOT, "assets", "referencia", "marcha_ref.json")
    escreve_referencia(faixas, fit_walk, fit_run, ref)
    mod = os.path.join(ROOT, "sem_alvorada", "gait_data.py")
    escreve_modulo(faixas, fit_walk, fit_run, mod)
    print("escrito", ref, os.path.getsize(ref) // 1024, "KB;", mod, os.path.getsize(mod) // 1024, "KB")


if __name__ == "__main__":
    main()
