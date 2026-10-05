"""Extrai do mocap da CMU os números que o corpo do jogo usa para andar, correr e andar agachado.

    python -m tools.marcha.extrair            # escreve sem_alvorada/gait_data.py e assets/referencia/marcha_ref.json

Entrada: os BVH em `out/referencia/cmu` (baixados sozinhos por `cmu.carregar`).
Saída:
  sem_alvorada/gait_data.py   tabelas por tempo de passada (50 amostras), uma por faixa de velocidade, mais as leis de
                              comprimento do passo. É o que roda no jogo (o jogo não lê BVH).
  assets/referencia/marcha_ref.json
                              as mesmas faixas com os escalares de `metricas.CAMPOS_MARCHA` (média e desvio entre clipes)
                              e as curvas médias por % da passada; é a referência de `tests/test_locomocao.py`.

Os eventos (toque do calcanhar, saída do pé) e os escalares vêm de `tools.movimento_ref.metricas`, as MESMAS funções que
medem o jogo: assim a fase 0 da tabela é o toque do calcanhar que a tabela de comparação enxerga. Todas as tabelas são
MEDIDAS: média de todas as passadas de todos os clipes da faixa, com os dois pés dobrados em um (o pé direito é o esquerdo
deslocado meio ciclo). Comprimentos de pé em unidades de comprimento da perna do sujeito, para valerem para o Daniel (0,845 m).
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.movimento_ref import cmu, metricas, movimento  # noqa: E402

PONTOS = 50                       # amostras por ciclo nas tabelas do jogo
G = 9.81
LEG_DANIEL = 0.845                # coxa 0.43 + canela 0.415 (body/skeleton.py)

# Clipes de caminhada e corrida em linha reta, sujeitos 02 a 39 e 45. A faixa de velocidade decide a que nó cada um vai.
# (Lista explícita: o cache `out/referencia/cmu` é compartilhado e tem clipes de outros usos.)
CLIPES_ANDAR = ("02_01 05_01 06_01 07_01 07_02 07_03 07_04 07_06 07_07 07_08 07_09 07_10 07_11 08_01 08_02 08_03 08_05 08_06 "
                "08_08 08_09 08_10 10_04 12_01 12_02 12_03 16_15 16_16 16_21 16_22 16_31 16_32 16_47 16_58 35_01 35_02 35_03 "
                "35_04 38_01 38_02 39_01 39_02 39_03 39_04 45_01").split()
CLIPES_CORRER = ("09_01 09_02 09_03 09_04 09_05 09_06 09_07 09_08 09_09 09_11 16_35 16_36 16_45 16_46 16_55 16_56 "
                 "35_17 35_18 35_19 35_20 35_21 35_22 35_23 35_24 35_25 35_26 02_03").split()

# faixa -> (modo do jogo, velocidade mínima, máxima, método de eventos)
FAIXAS = {
    "andar_lento": ("walk", 0.85, 1.15, "zeni"),
    "andar": ("walk", 1.20, 1.45, "zeni"),
    "andar_rapido": ("walk", 1.55, 1.80, "zeni"),
    "correr": ("run", 3.00, 4.40, "altura"),
}
AGACHADO = ("136_09", "136_10")

CURVAS_JOGO = ("pe_frente", "pe_lateral", "pe_alt", "pe", "cab_z", "cab_y", "cab_x", "cab_roll", "cab_pitch", "cab_yaw",
               "pelve_yaw", "tronco_yaw", "pelve_roll", "ombro", "cotovelo", "pelvis_z", "pelvis_y", "pelvis_x")
UNIDADE_PERNA = ("pe_frente", "pe_lateral", "pe_alt")
# curvas periódicas travadas na passada, cuja amplitude por passada (pico a pico) a média achata um pouco porque as
# passadas e as pessoas não coincidem em fase: o jogo repete a passada média, então a amplitude é devolvida
RESTAURAR = ("cab_z", "cab_y", "cab_x", "pelvis_z", "pelvis_y", "pelvis_x", "pelve_yaw", "tronco_yaw", "ombro", "cotovelo", "pe_alt")
FATOR_MAX = 1.5
CURVAS_REF = ("quadril", "joelho", "tornozelo", "pelve_rot", "torax_rot", "ombro", "cotovelo", "cabeca_z", "quadril_z",
              "cabeca_x", "tronco_incl")
ESCALARES_REF = tuple(metricas.CAMPOS_MARCHA) + ("perna", "razao_quadril", "velocidade_geral")


# --------------------------------------------------------------------------
# Utilitários
# --------------------------------------------------------------------------
def media_movel(x, n, tendencia=True):
    """Média móvel centrada de `n` amostras. Nas bordas, `tendencia=True` reflete o sinal pelo ponto (2 x[0] - x[k]), o que
    preserva uma reta (a pelve de quem anda avança em linha reta); a reflexão simples, para ângulos e matrizes, a distorceria."""
    n = max(1, int(n) | 1)
    x = np.asarray(x, float)
    if n == 1:
        return x.copy()
    pad = min(n // 2, len(x) - 1)
    if tendencia:
        esquerda = 2 * x[0] - x[pad:0:-1]
        direita = 2 * x[-1] - x[-2:-pad - 2:-1]
    else:
        esquerda, direita = x[pad:0:-1], x[-2:-pad - 2:-1]
    ext = np.concatenate([esquerda, x, direita], axis=0)
    kernel = np.ones(n) / n
    if x.ndim == 1:
        return np.convolve(ext, kernel, mode="valid")[:len(x)]
    return np.stack([np.convolve(ext[:, k], kernel, mode="valid")[:len(x)] for k in range(x.shape[1])], axis=1)


def _angulos_cabeca(rot, frente, janela):
    """Roll (+ = inclina para a esquerda, como a câmera), pitch (+ = olha para cima) e yaw (+ = esquerda), em graus,
    da orientação `rot` [T,3,3] em relação à sua média local (janela de uma passada)."""
    n = len(rot)
    media = media_movel(rot.reshape(n, 9), janela, tendencia=False).reshape(n, 3, 3)
    u, _s, vt = np.linalg.svd(media)
    rel = rot @ np.swapaxes(u @ vt, 1, 2)
    w = 0.5 * np.stack([rel[:, 2, 1] - rel[:, 1, 2], rel[:, 0, 2] - rel[:, 2, 0], rel[:, 1, 0] - rel[:, 0, 1]], axis=1)
    direita = np.stack([frente[:, 1], -frente[:, 0]], axis=1)
    em_torno_da_frente = w[:, 0] * frente[:, 0] + w[:, 1] * frente[:, 1]
    em_torno_da_direita = w[:, 0] * direita[:, 0] + w[:, 1] * direita[:, 1]
    return {"roll": -np.degrees(np.arcsin(np.clip(em_torno_da_frente, -1, 1))),
            "pitch": np.degrees(np.arcsin(np.clip(em_torno_da_direita, -1, 1))),
            "yaw": np.degrees(np.arcsin(np.clip(w[:, 2], -1, 1)))}


def curvas_por_passada(mov, ev, perna, pontos=101):
    """Todas as passadas do clipe, cada uma de um toque do calcanhar ao seguinte do MESMO pé, normalizada para 0..100%:
    {nome: array [passadas, pontos]}. O pé direito entra espelhado (o que o esquerdo faz de 0 a 100% o direito faz de 50 a
    150%); os braços são os OPOSTOS ao pé que toca em 0%. Distâncias da cabeça e da pelve são relativas à média móvel de
    uma passada; as do pé, ao ponto suave da pelve (a raiz Hips), em metros, depois divididas pela perna."""
    _i, frente = metricas.frentes(mov)
    n = mov.quadros
    direita = np.stack([frente[:, 1], -frente[:, 0]], axis=1)
    ang = metricas.angulos(mov)
    toques_e = ev.toque["e"] if len(ev.toque["e"]) >= 2 else ev.toque["d"]
    if len(toques_e) < 2:
        return {}
    janela = int(round(float(np.mean(np.diff(toques_e)))))

    def ao_longo(p):
        return np.stack([(p[:, :2] * frente).sum(axis=1), (p[:, :2] * direita).sum(axis=1), p[:, 2]], axis=1)

    pelve_suave = media_movel(mov.j("quadril"), janela)
    cabeca = mov.cabeca_pos()
    cab_rel = ao_longo(cabeca - media_movel(cabeca, janela))
    pel_rel = ao_longo(mov.j("quadril") - pelve_suave)
    angulos_cabeca = _angulos_cabeca(mov.cabeca_rot, frente, janela) if mov.cabeca_rot is not None else None
    roll_pelve = np.degrees(np.arcsin(np.clip((mov.j("coxa_d")[:, 2] - mov.j("coxa_e")[:, 2])
                                              / np.maximum(np.linalg.norm(mov.j("coxa_d") - mov.j("coxa_e"), axis=1), 1e-6), -1, 1)))
    grade = np.arange(n)
    coletado = {}

    def somar(chave, serie, a, b):
        coletado.setdefault(chave, []).append(np.interp(np.linspace(a, b, pontos), grade, serie))

    for lado, oposto, sinal in (("e", "d", 1.0), ("d", "e", -1.0)):
        tornozelo = ao_longo(mov.j(f"tornozelo_{lado}") - pelve_suave)
        bola = mov.j(f"bola_{lado}") - mov.j(f"tornozelo_{lado}")
        pe = np.degrees(np.arctan2(bola[:, 2], (bola[:, :2] * frente).sum(axis=1)))
        for a, b in zip(ev.toque[lado][:-1], ev.toque[lado][1:]):
            if b - a < 8 or not (0.35 < (b - a) / mov.fps < 2.5):
                continue
            saidas = [s for s in ev.saida[lado] if a < s < b]
            apoio = (saidas[0] - a) / (b - a) if saidas else 0.6
            lo, hi = int(round(0.4 * apoio * (pontos - 1))), max(int(round(0.6 * apoio * (pontos - 1))), int(round(0.4 * apoio * (pontos - 1))) + 2)

            def plano(serie):
                amostra = np.interp(np.linspace(a, b, pontos), grade, serie)
                return serie - amostra[lo:hi].mean()
            somar("pe", plano(pe), a, b)
            somar("pe_alt", plano(tornozelo[:, 2]) / perna, a, b)
            somar("pe_frente", tornozelo[:, 0] / perna, a, b)
            somar("pe_lateral", tornozelo[:, 1] * sinal / perna, a, b)
            somar("ombro", ang[f"ombro_{oposto}"], a, b)
            somar("cotovelo", ang[f"cotovelo_{oposto}"], a, b)
            for chave, serie in (("pelve_yaw", ang["pelve_rot"]), ("tronco_yaw", ang["torax_rot"]), ("pelve_roll", roll_pelve)):
                somar(chave, (serie - np.mean(serie[a:b])) * sinal, a, b)
            somar("cab_z", cab_rel[:, 2], a, b)
            somar("cab_y", cab_rel[:, 1] * sinal, a, b)
            somar("cab_x", cab_rel[:, 0], a, b)
            somar("pelvis_x", pel_rel[:, 0], a, b)
            somar("pelvis_z", pel_rel[:, 2], a, b)
            somar("pelvis_y", pel_rel[:, 1] * sinal, a, b)
            if angulos_cabeca is not None:
                somar("cab_roll", angulos_cabeca["roll"] * sinal, a, b)
                somar("cab_pitch", angulos_cabeca["pitch"], a, b)
                somar("cab_yaw", angulos_cabeca["yaw"] * sinal, a, b)
    return {k: np.array(v) for k, v in coletado.items()}


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


def razao_quadril(mov):
    """Altura média da junta do quadril sobre (coxa + canela + 0,085 m de tornozelo): 1,0 = perna esticada."""
    piso = metricas.altura_do_piso(mov)
    quadril = 0.5 * (mov.j("coxa_e")[:, 2] + mov.j("coxa_d")[:, 2]) - piso
    return float(quadril.mean() / (metricas.comprimento_perna(mov) + movimento.ALTURA_TORNOZELO))


def trecho_andando(mov):
    """Maior trecho contínuo a passo estável (pelve a mais de metade do p90 da velocidade)."""
    sm = metricas.gaussiano(mov.j("quadril")[:, :2], 0.25, mov.fps)
    v = np.linalg.norm(np.gradient(sm, axis=0), axis=1) * mov.fps
    corridas = metricas._corridas(v > 0.5 * np.percentile(v, 90))
    a, b = max(corridas, key=lambda r: r[1] - r[0])
    corte = int(0.4 * mov.fps)
    return mov.trecho((a + corte) / mov.fps, (b - corte) / mov.fps)


# --------------------------------------------------------------------------
# Faixas
# --------------------------------------------------------------------------
def processa(movs, metodo):
    """Pool de passadas e escalares de uma lista [(id, Movimento)]."""
    pools, marchas = [], []
    for cid, mov in movs:
        ev = metricas.eventos_marcha(mov, metodo)
        marcha = metricas.medir_tudo(mov, metodo)
        marcha.v["razao_quadril"] = razao_quadril(mov)
        marcha.v["velocidade_geral"] = float(np.linalg.norm(mov.j("quadril")[-1, :2] - mov.j("quadril")[0, :2]) / mov.duracao)
        marchas.append((cid, marcha))
        perna = marcha.v["perna"]
        curvas = curvas_por_passada(mov, ev, perna)
        if curvas:
            pools.append(curvas)
    return pool_curvas(pools), marchas


def resumo(marchas):
    out = {}
    for chave in ESCALARES_REF:
        a = np.array([m.v.get(chave, np.nan) for _c, m in marchas], float)
        a = a[np.isfinite(a)]
        if len(a):
            out[chave] = {"media": float(a.mean()), "mediana": float(np.median(a)), "dp": float(a.std()), "n": int(len(a)),
                          "min": float(a.min()), "max": float(a.max())}
    return out


def curvas_de_referencia(marchas):
    out = {}
    for chave in CURVAS_REF:
        juntas = [m.curvas[chave] for _c, m in marchas if chave in m.curvas and len(m.curvas[chave].ciclos)]
        if juntas:
            curva = metricas.Curva.juntar(juntas)
            out[chave] = {"media": [round(float(x), 4) for x in curva.media], "dp": [round(float(x), 4) for x in curva.desvio],
                          "n": curva.n}
    return out


def ajuste_passo(marchas, lo, hi):
    """passo/perna = a * Fr^b, com Fr = v / raiz(g perna): mínimos quadrados em log. Devolve (a, b, erro_rms, n)."""
    v, l, st = [], [], []
    for _c, m in marchas:
        x = m.v
        if lo <= x.get("velocidade", 0) <= hi and np.isfinite(x.get("cadencia", np.nan)) and 20 < x["cadencia"] < 220:
            v.append(x["velocidade"]); l.append(x["perna"]); st.append(x["velocidade"] / (x["cadencia"] / 60.0))
    v, l, st = map(np.array, (v, l, st))
    fr = v / np.sqrt(G * l)
    b, a = np.polyfit(np.log(fr), np.log(st / l), 1)
    pred = np.exp(a) * fr ** b
    return float(np.exp(a)), float(b), float(np.sqrt(np.mean((pred - st / l) ** 2))), len(v)


def montar():
    faixas, todos = {}, []
    carregados = {}

    def mov_de(cid):
        if cid not in carregados:
            carregados[cid] = movimento.movimento_de_mocap(cmu.carregar(cid))
        return carregados[cid]

    for nome, (modo, lo, hi, metodo) in FAIXAS.items():
        escolhidos = []
        for cid in CLIPES_ANDAR + CLIPES_CORRER:
            mov = mov_de(cid)
            v = np.linalg.norm(mov.j("quadril")[-1, :2] - mov.j("quadril")[0, :2]) / mov.duracao
            if lo <= v <= hi:
                escolhidos.append((cid, mov))
        curvas, marchas = processa(escolhidos, metodo)
        todos += marchas
        faixas[nome] = {"modo": modo, "metodo": metodo, "clipes": [c for c, _ in escolhidos], "curvas": curvas, "marchas": marchas}
        v = faixas[nome]
        r = resumo(marchas)
        print(f"{nome:14s} n_clipes={len(escolhidos):2d} v={r['velocidade_geral']['media']:.3f}  cadencia(med)={r['cadencia']['mediana']:.1f}"
              f"  apoio(med)={r['apoio_pct']['mediana']:.1f}", flush=True)
    escolhidos = [(cid, trecho_andando(mov_de(cid))) for cid in AGACHADO]
    curvas, marchas = processa(escolhidos, "zeni")
    faixas["agachado"] = {"modo": "crouch", "metodo": "zeni", "clipes": list(AGACHADO), "curvas": curvas, "marchas": marchas}
    r = resumo(marchas)
    print(f"{'agachado':14s} n_clipes={len(escolhidos):2d} v={r['velocidade_geral']['media']:.3f}  cadencia(med)={r['cadencia']['mediana']:.1f}", flush=True)
    fit_walk = ajuste_passo(todos, 0.85, 1.85)
    fit_run = ajuste_passo(todos, 3.0, 4.4)
    print("passo/perna = a Fr^b  andar:", fit_walk, " correr:", fit_run)
    return faixas, fit_walk, fit_run


def escreve_referencia(faixas, fit_walk, fit_run, caminho):
    saida = {"fonte": "CMU Graphics Lab Motion Capture Database (cgspeed BVH). Médias de passadas, pés dobrados; "
                      "escalares e curvas de tools/movimento_ref/metricas.py.",
             "leg_daniel": LEG_DANIEL, "ajuste_passo": {"andar": fit_walk, "correr": fit_run}, "faixas": {}}
    for nome, f in faixas.items():
        saida["faixas"][nome] = {"modo": f["modo"], "metodo": f["metodo"], "clipes": f["clipes"], "resumo": resumo(f["marchas"]),
                                 "curvas": curvas_de_referencia(f["marchas"]),
                                 "fator_amp": {k: round(v[3], 3) for k, v in f["curvas"].items()}}
    with open(caminho, "w", encoding="utf-8") as arq:
        json.dump(saida, arq, ensure_ascii=False, separators=(",", ":"))


def periodico(curva, n=PONTOS):
    """101 amostras de 0 a 100% -> `n` amostras periódicas (descarta a de 100%, que repete a de 0%)."""
    c = np.asarray(curva, float)
    gap = c[-1] - c[0]
    base = c[:-1] - gap * np.linspace(0.0, 1.0, len(c) - 1, endpoint=False)    # reparte o fecho imperfeito ao longo da curva
    x = np.linspace(0.0, 1.0, len(base), endpoint=False)
    xn = np.linspace(0.0, 1.0, n, endpoint=False)
    return np.interp(xn, np.concatenate([x - 1.0, x, x + 1.0]), np.tile(base, 3))


def escreve_modulo(faixas, fit_walk, fit_run, caminho):
    linhas = ['"""Tabelas de marcha MEDIDAS em mocap real (CMU Graphics Lab Motion Capture Database).',
              '',
              'Arquivo GERADO por `python -m tools.marcha.extrair`; não edite à mão. Cada nó é uma faixa de velocidade com a',
              'média das passadas dos clipes da faixa (dois pés dobrados em um): curvas de 50 amostras por ciclo, que começa',
              'no toque do calcanhar do pé de referência (esquerdo, como `tools/movimento_ref/metricas.py` o enxerga).',
              'Comprimentos do pé em unidades de comprimento da perna.',
              '"""',
              '', f'PONTOS = {PONTOS}', f'LEG_DANIEL = {LEG_DANIEL}', '',
              f'PASSO_ANDAR = {tuple(round(x, 5) for x in fit_walk[:2])}      # passo/perna = a * Fr^b, Fr = v / raiz(g perna)',
              f'PASSO_CORRER = {tuple(round(x, 5) for x in fit_run[:2])}', '', 'NOS = {']
    for modo in ("walk", "run", "crouch"):
        linhas.append(f'    "{modo}": [')
        nos = sorted([(resumo(f["marchas"])["velocidade_geral"]["media"], nome, f) for nome, f in faixas.items() if f["modo"] == modo])
        for v, nome, f in nos:
            r = resumo(f["marchas"])
            linhas.append('        {')
            linhas.append(f'            "nome": "{nome}", "v": {v:.4f}, "clipes": {len(f["clipes"])},')
            linhas.append(f'            "cadencia": {r["cadencia"]["mediana"]:.2f}, "apoio": {r["apoio_pct"]["mediana"] / 100.0:.4f},'
                          f' "duplo": {r["duplo_apoio_passo_pct"]["mediana"] / 100.0:.4f},')
            linhas.append(f'            "tronco_incl": {r["tronco_inclinacao"]["mediana"]:.2f},')
            razao = 1.0 if modo == "crouch" else r["razao_quadril"]["mediana"]       # agachado: a altura vem dos olhos
            linhas.append(f'            "razao_quadril": {razao:.4f},')
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
    faixas, fit_walk, fit_run = montar()
    ref = os.path.join(ROOT, "assets", "referencia", "marcha_ref.json")
    escreve_referencia(faixas, fit_walk, fit_run, ref)
    mod = os.path.join(ROOT, "sem_alvorada", "gait_data.py")
    escreve_modulo(faixas, fit_walk, fit_run, mod)
    print("escrito", ref, os.path.getsize(ref) // 1024, "KB;", mod, os.path.getsize(mod) // 1024, "KB")


if __name__ == "__main__":
    main()
