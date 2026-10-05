"""Porta: grava o jogo, roda o modelo físico, monta a tabela de métricas e os painéis [modelo físico | jogo].

    python -m tools.movimento_ref.fisica.comparar_porta [--antes]      # --antes guarda o jogo de agora como "antes"
"""
import math
import os
import sys

import numpy as np

from . import grava, mao_real, medidas
from . import porta as P

Metrica = medidas.Metrica
GRUPO = "porta"
PORTA_REF = "kids_master"        # tipo "quarto", folha de 25 kg
FOLGA_LINGUETA_RAD = P.FOLGA_LINGUETA / P.RAIO_MACANETA
LIMIAR_GESTO = 0.12              # m/s, o mesmo de mao_real.gestos


# --------------------------------------------------------------------------
# Gravações do jogo
# --------------------------------------------------------------------------
def gravar():
    """Todas as séries do jogo que as métricas e os painéis usam."""
    g = {"abre": {r: grava.porta(PORTA_REF, r) for r in grava.PASSOS},
         "fecha": grava.porta(PORTA_REF, "normal", "aberta"),
         "batida": grava.porta(PORTA_REF, "apressado", "aberta", segundos=2.0),
         "inverte": {f: grava.porta(PORTA_REF, "normal", "fechada", inverte_em=0.14 + f) for f in (0.35, 0.6, 0.9)},
         "portas": {}}
    for porta_id in grava.ids_das_portas():
        g["portas"][porta_id] = {r: grava.porta(porta_id, r, segundos=2.0) for r in ("normal", "apressado")}
    return g


def massa_da_porta(rec):
    return P.MASSAS[rec["kind"]]


def forca_pico(rec):
    """Força (N) na maçaneta que a trajetória GRAVADA do jogo exige da mão, pela dinâmica do modelo físico."""
    dt = rec["t"][1] - rec["t"][0]
    janela = (rec["x"] > 1e-4) & (rec["x"] < 1 - 1e-4)
    tau = P.torque_da_trajetoria(rec["theta"], dt, massa_da_porta(rec))
    return float(np.max(np.abs(tau[janela])) / P.RAIO_MACANETA)


def inicio_da_folha(rec, limite=1e-4):
    return float(rec["t"][np.nonzero(rec["x"] > limite)[0][0]])


def chegada(rec, alvo=0.0, de=1.0):
    """Instante e velocidade (rad/s) em que a folha chega a `alvo` vinda de `de`."""
    if alvo < de:
        idx = np.nonzero(rec["x"] <= alvo + 1e-9)[0]
    else:
        idx = np.nonzero(rec["x"] >= alvo - 1e-9)[0]
    k = int(idx[0])
    return float(rec["t"][k]), float(rec["omega"][max(k - 1, 0)])


def gesto_do_jogo(rec):
    """Duração, fração do pico e razão pico/média da mão que abre a porta, pelo mesmo critério do mocap."""
    v = np.abs(rec["omega"]) * P.RAIO_MACANETA
    ativo = np.nonzero(v > LIMIAR_GESTO)[0]
    a, b = ativo[0], ativo[-1]
    seg = v[a:b + 1]
    dt = rec["t"][1] - rec["t"][0]
    duracao = (b - a + 1) * dt
    trajeto = float(np.sum(seg) * dt)
    return {"duracao": duracao, "fracao_pico": float(np.argmax(seg)) / max(len(seg) - 1, 1),
            "razao": float(np.max(seg) * duracao / trajeto), "trajeto": trajeto, "v_pico": float(np.max(seg))}


def desvio_da_trajetoria(rec, massa):
    """Maior diferença (fração do curso) entre a folha do jogo e a trajetória de mínima variação de torque, mesma duração.

    As curvas são alinhadas pela fase: o início da física é ajustado (±15 ms) para minimizar o erro quadrático.
    """
    from scipy.optimize import minimize_scalar
    duracao = rec["duracao"]
    t_fim = float(rec["t"][np.nonzero(rec["x"] >= 1 - 1e-6)[0][0]])
    t, theta, *_ = P.trajetoria_minima_variacao_de_torque(duracao, massa)
    fisico = theta / P.ABERTURA
    janela = (rec["t"] > t_fim - duracao - 0.05) & (rec["t"] < t_fim + 0.05)

    def curva(t_ini):
        return np.interp(rec["t"][janela] - t_ini, t, fisico, left=0.0, right=1.0)

    def erro(t_ini):
        return float(np.sum((rec["x"][janela] - curva(t_ini)) ** 2))
    melhor = minimize_scalar(erro, bounds=(t_fim - duracao - 0.015, t_fim - duracao + 0.015), method="bounded")
    return float(np.max(np.abs(rec["x"][janela] - curva(melhor.x))))


# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------
def metricas(g):
    out = []
    add = out.append
    abre = g["abre"]["normal"]
    massa = massa_da_porta(abre)
    t_min = P.tempo_minimo(P.F_CONFORTO, massa)

    # ---- abrir: a trajetória
    add(Metrica.igual(GRUPO, "abrir: desvio da trajetória de mínima variação de torque", "fração do curso", 0.0,
                      desvio_da_trajetoria(abre, massa), 0.005, relativa=False,
                      nota="o jogo (quíntica) contra a otimização numérica com inércia, atrito e ar"))
    duracao = abre["duracao"]
    t, theta, omega, alpha, tau = P.trajetoria_minima_variacao_de_torque(duracao, massa)
    janela = (abre["x"] > 1e-4) & (abre["x"] < 1 - 1e-4)
    add(Metrica.igual(GRUPO, "abrir: velocidade angular de pico", "rad/s", float(np.max(omega)),
                      float(np.max(abre["omega"])), 0.03))
    add(Metrica.igual(GRUPO, "abrir: aceleração angular de pico", "rad/s2", float(np.max(np.abs(alpha))),
                      float(np.max(np.abs(abre["alpha"][janela]))), 0.05))
    inicio = inicio_da_folha(abre)
    pico = float(abre["t"][np.argmax(abre["omega"])])
    add(Metrica.igual(GRUPO, "abrir: instante do pico (fração da duração)", "-", float(t[np.argmax(omega)] / duracao),
                      (pico - (inicio + 0.0)) / duracao, 0.05, relativa=False))

    # ---- abrir: o esforço da mão, os ritmos e as 13 portas
    forcas = {r: max(forca_pico(g["portas"][i][r]) for i in g["portas"] if r in g["portas"][i]) for r in ("normal", "apressado")}
    add(Metrica.limite_max(GRUPO, "abrir: força na maçaneta, normal (pior das 13 portas)", "N", P.F_CONFORTO, forcas["normal"],
                           fonte="ESTIMADO", nota="limite de esforço sustentado com uma mão"))
    add(Metrica.limite_max(GRUPO, "abrir: força na maçaneta, apressado (pior das 13 portas)", "N", P.F_CONFORTO, forcas["apressado"],
                           fonte="ESTIMADO", nota="limite de esforço sustentado com uma mão"))
    pior = min(g["abre"][r]["duracao"] / P.tempo_minimo(P.F_CONFORTO, massa) for r in g["abre"])
    add(Metrica.limite_min(GRUPO, "abrir: duração / menor duração que a mão aguenta (pior ritmo)", "-", 1.0, pior,
                           fonte="DERIVADO"))
    add(Metrica.limite_min(GRUPO, "abrir: menor duração de uma abertura, 13 portas e 2 ritmos", "s", 0.8,
                           min(g["portas"][i][r]["duracao"] for i in g["portas"] for r in g["portas"][i]),
                           fonte="ESTIMADO", nota="a mão mais rápida sustentável (150 N, 25 kg) leva 0,7 s"))

    # ---- abrir: a mão do jogo contra mãos reais
    try:
        real = mao_real.resumo(mao_real.gestos_de_erguer("RightHand") + mao_real.gestos_de_erguer("LeftHand")
                               + mao_real.gestos_de_empurrar("RightHand") + mao_real.gestos_de_empurrar("LeftHand"))
    except Exception as erro:                   # noqa: BLE001 - sem rede e sem cache o mocap não está disponível
        print(f"  (mocap indisponível: {erro!r}; as métricas MEDIDAS ficam de fora)")
        real = None
    gesto = gesto_do_jogo(abre)
    for campo, nome, un in (("duracao", "duração do gesto", "s"), ("fracao_pico", "instante do pico (fração)", "-"),
                            ("razao_pico_media", "razão pico/média da velocidade", "-")):
        if real is None:
            break
        media, desvio = real[campo]
        valor = gesto["razao"] if campo == "razao_pico_media" else gesto[campo]
        add(Metrica("mão real", f"abrir: {nome}", un, media, valor, media - desvio, media + desvio, fonte="MEDIDO",
                    nota=f"{real['n']} gestos de empurrar e erguer janela (CMU 56_03..08, 81_05..82_07)"))

    # ---- maçaneta e lingueta em fase
    t_1mm = float(abre["t"][np.nonzero(abre["x"] * P.ABERTURA * P.RAIO_MACANETA > 0.0015)[0][0]])
    giro = float(np.interp(t_1mm, abre["t"], abre["turn"]))
    add(Metrica.limite_min(GRUPO, "abrir: lingueta recolhida quando a folha anda 1,5 mm", "0..1", 0.8, giro, fonte="ESTIMADO",
                           nota="a folha só sai da contra-fechadura com a lingueta recolhida (curso 11 mm)"))

    # ---- fechar com trinco
    fecha = g["fecha"]
    t_ch, w_ch = chegada(fecha)
    add(Metrica.limite_min(GRUPO, "fechar: velocidade da ponta ao chegar ao batente", "m/s", 0.12,
                           abs(w_ch) * P.LARGURA, fonte="ESTIMADO",
                           nota="energia mínima para empurrar a lingueta chanfrada: mola de 3 a 8,5 N em 11 mm"))
    k = int(np.nonzero(fecha["t"] >= t_ch)[0][0])
    giro_na_chegada = float(np.interp(t_ch, fecha["t"], fecha["turn"]))
    add(Metrica.limite_min(GRUPO, "fechar: lingueta recolhida quando a folha encosta", "0..1", 0.8, giro_na_chegada,
                           fonte="DERIVADO", nota="o chanfro empurra a lingueta para dentro antes do encontro"))
    recuo = float(np.max(fecha["x"][k + 1:]) * P.ABERTURA * P.RAIO_MACANETA * 1000.0)
    v_hit = abs(w_ch)
    fisico_recuo = P.rebote_parabolico(v_hit) * P.RAIO_MACANETA * 1000.0
    add(Metrica("porta", "fechar: recuo do trinco na maçaneta", "mm", fisico_recuo, recuo, 0.3, 4.0, fonte="ESTIMADO",
                nota="folga da lingueta de 1 a 5 mm; sai da restituição do batente e da mola"))
    t_latch = next(t for t, nome in fecha["sons"] if nome == "door_latch")
    add(Metrica.igual(GRUPO, "fechar: som do trinco menos o instante da chegada", "s", 0.0, t_latch - t_ch, 0.03,
                      relativa=False))

    # ---- batida
    b = g["batida"]
    sim, t_sim, w_sim, tip = P.golpe_de_porta()
    inicio_b = float(b["t"][np.nonzero(b["x"] < 1 - 1e-4)[0][0]])
    t_hit, w_hit = chegada(b)
    add(Metrica.igual(GRUPO, "batida: tempo da folha do aberto ao batente", "s", t_sim, t_hit - inicio_b, 0.15,
                      fonte="ESTIMADO", nota="golpe de 400 N por 0,15 s a 0,81 m da dobradiça"))
    w_fis = abs(sim["batidas"][0][1])
    add(Metrica.igual(GRUPO, "batida: velocidade angular no impacto", "rad/s", w_fis, abs(w_hit), 0.15, fonte="ESTIMADO"))
    add(Metrica.igual(GRUPO, "batida: velocidade da ponta no impacto", "m/s", w_fis * P.LARGURA, abs(w_hit) * P.LARGURA, 0.15,
                      fonte="ESTIMADO", nota="uma batida forte de mão fica entre 3 e 5 m/s"))
    k = int(np.nonzero(b["t"] >= t_hit)[0][0])
    rebote = float(np.max(b["x"][k + 1:]) * P.ABERTURA * P.RAIO_MACANETA * 1000.0)
    add(Metrica("porta", "batida: rebote máximo na maçaneta", "mm", P.FOLGA_LINGUETA * 1000.0, rebote, 3.0, 8.0,
                fonte="ESTIMADO", nota="o rebote livre seria de dezenas de graus; a lingueta limita à folga de 1 a 5 mm (mais a vedação)"))
    t_bang = next(t for t, nome in b["sons"] if nome == "door_slam") + 0.19
    add(Metrica.igual(GRUPO, "batida: estrondo menos o instante do impacto", "s", 0.0, t_bang - t_hit, 0.03, relativa=False,
                      nota="a receita do som tem o estrondo 0,19 s depois do início"))
    ultimo = float(b["t"][np.nonzero(b["x"] > 1e-6)[0][-1]])
    add(Metrica.limite_max(GRUPO, "batida: tempo até a folha assentar depois do impacto", "s", 0.6, ultimo - t_hit,
                           fonte="ESTIMADO"))

    # ---- inverter no meio
    for fracao, rec in g["inverte"].items():
        k0 = int((0.14 + fracao) * 240)
        x0, w0 = float(rec["x"][k0]), float(rec["omega"][k0])
        avanco = (float(np.max(rec["x"])) - x0) * P.ABERTURA
        minimo = P.reverter(0, w0, massa, 250.0)
        maximo = abs(w0) * 0.10 + P.reverter(0, w0, massa, 100.0)
        add(Metrica("porta", f"inverter aos {fracao:.0%} da abertura: quanto a folha ainda avança", "rad",
                    P.reverter(0, w0, massa, P.F_REVERTER), avanco, minimo, maximo, fonte="DERIVADO",
                    nota="freada com 100 a 250 N (e até 0,1 s de reação) a partir da velocidade que o jogo tinha"))
    return out


def tabela_13_portas(g):
    """Uma linha por porta: tipo, massa, duração planejada e força de pico na maçaneta, em dois ritmos."""
    linhas = []
    for porta_id, ritmos in g["portas"].items():
        n, a = ritmos["normal"], ritmos["apressado"]
        linhas.append({"porta": porta_id, "tipo": n["kind"], "massa_kg": massa_da_porta(n), "dur_normal": n["duracao"],
                       "dur_apressado": a["duracao"], "forca_normal": forca_pico(n), "forca_apressado": forca_pico(a),
                       "t_min_100N": P.tempo_minimo(P.F_CONFORTO, massa_da_porta(n))})
    return linhas


def metricas_com_antes(g):
    lista = metricas(g)
    antes = medidas.carregar_gravacao(GRUPO)
    if antes is not None:
        medidas.completar_antes(lista, metricas(antes))
    return lista


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    g = gravar()
    if "--antes" in argv:
        medidas.salvar_gravacao(GRUPO, g)
        print("antes gravado em", medidas.ANTES)
    lista = metricas_com_antes(g)
    print(medidas.tabela_markdown(lista))
    for linha in tabela_13_portas(g):
        print(linha)
    return lista


if __name__ == "__main__":
    main()
