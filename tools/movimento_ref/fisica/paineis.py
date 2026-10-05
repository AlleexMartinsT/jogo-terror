"""Painéis [modelo físico | jogo | antes e depois sobrepostos] dos objetos, em out/f4_4/final/.

    python -m tools.movimento_ref.fisica.paineis [porta carro relogio ambiente ...]

Cores: modelo físico em azul (o "real" dos painéis do corpo), jogo depois em laranja, jogo antes em cinza tracejado (a identidade
nunca depende só da cor: o antes é tracejado). O texto usa tinta, nunca a cor da série.
"""
import math
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import carro as KC
from . import comparar_ambiente as CA, comparar_carro as CC, comparar_porta as CP, comparar_relogio as CR
from . import cortina as KT, grava, luz as KL, mao_real, medidas, porta as P, relogio as R

COR_MODELO, COR_JOGO, COR_ANTES = "#2a78d6", "#eb6834", "#8a8984"
TINTA, TINTA_SUAVE, FUNDO, GRADE = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3de"
SAIDA = medidas.FINAL


def _estilo():
    plt.rcParams.update({
        "figure.facecolor": FUNDO, "axes.facecolor": FUNDO, "savefig.facecolor": FUNDO, "axes.edgecolor": GRADE,
        "axes.labelcolor": TINTA_SUAVE, "axes.titlecolor": TINTA, "axes.titlesize": 10, "axes.labelsize": 8.5,
        "xtick.color": TINTA_SUAVE, "ytick.color": TINTA_SUAVE, "xtick.labelsize": 8, "ytick.labelsize": 8, "text.color": TINTA,
        "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.7, "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "legend.fontsize": 8.5, "font.size": 9, "lines.solid_capstyle": "round",
        "figure.constrained_layout.use": True})


def _salvar(fig, nome):
    os.makedirs(SAIDA, exist_ok=True)
    caminho = os.path.join(SAIDA, nome)
    fig.savefig(caminho, dpi=110)
    plt.close(fig)
    return caminho


def _colunas(titulo, linhas, rotulos_y, largura=13.0, altura_linha=2.15):
    """Figura de `linhas` x 3: modelo | jogo | sobreposto. Devolve (fig, eixos[linhas][3])."""
    _estilo()
    fig, eixos = plt.subplots(linhas, 3, figsize=(largura, altura_linha * linhas + 0.9), sharex="col", squeeze=False)
    fig.suptitle(titulo, x=0.01, ha="left", fontsize=11.5, fontweight="bold")
    for c, nome in enumerate(("Modelo físico", "Jogo (depois)", "Sobrepostos")):
        eixos[0][c].set_title(nome, loc="left")
    for r, rotulo in enumerate(rotulos_y):
        eixos[r][0].set_ylabel(rotulo)
        for c in range(1, 3):
            eixos[r][c].sharey(eixos[r][0])
            plt.setp(eixos[r][c].get_yticklabels(), visible=False)
    return fig, eixos


def _tres(eixos_linha, t_modelo, y_modelo, t_jogo, y_jogo, t_antes=None, y_antes=None, cortes=None):
    a, b, c = eixos_linha
    a.plot(t_modelo, y_modelo, color=COR_MODELO, lw=1.8)
    b.plot(t_jogo, y_jogo, color=COR_JOGO, lw=1.8)
    if t_antes is not None:
        c.plot(t_antes, y_antes, color=COR_ANTES, lw=1.6, ls=(0, (4, 2)), label="jogo antes")
    c.plot(t_modelo, y_modelo, color=COR_MODELO, lw=1.8, label="modelo")
    c.plot(t_jogo, y_jogo, color=COR_JOGO, lw=1.4, ls=":", label="jogo depois")


# --------------------------------------------------------------------------
# Porta
# --------------------------------------------------------------------------
def painel_porta_abrir(g, antes):
    rec, rec0 = g["abre"]["normal"], antes["abre"]["normal"]
    dur = rec["duracao"]
    massa = CP.massa_da_porta(rec)
    t, theta, omega, alpha, tau = P.trajetoria_minima_variacao_de_torque(dur, massa)
    t_fim = float(rec["t"][np.nonzero(rec["x"] >= 1 - 1e-6)[0][0]])
    t0 = t_fim - dur
    tj = rec["t"] - t0
    dt = rec["t"][1] - rec["t"][0]
    forca_jogo = P.torque_da_trajetoria(rec["theta"], dt, massa) / P.RAIO_MACANETA
    fig, ax = _colunas(f"Porta, abrir andando (folha de {massa:.0f} kg, {dur:.2f} s): a quíntica do jogo é a trajetória de mínima variação de torque",
                       4, ["ângulo (graus)", "velocidade (rad/s)", "aceleração (rad/s2)", "força na maçaneta (N)"])
    janela = (tj > -0.1) & (tj < dur + 0.15)
    _tres(ax[0], t, np.degrees(theta), tj[janela], np.degrees(rec["theta"][janela]), rec0["t"] - t0, np.degrees(rec0["theta"]))
    _tres(ax[1], t, omega, tj[janela], rec["omega"][janela], rec0["t"] - t0, rec0["omega"])
    _tres(ax[2], t, alpha, tj[janela], rec["alpha"][janela], rec0["t"] - t0, rec0["alpha"])
    _tres(ax[3], t, tau / P.RAIO_MACANETA, tj[janela], forca_jogo[janela])
    for c in range(3):
        ax[3][c].axhline(P.F_CONFORTO, color=TINTA_SUAVE, lw=0.9, ls="--")
    ax[3][0].text(0.02, P.F_CONFORTO + 3, "limite de esforço sustentado (100 N, ESTIMADO)", fontsize=8, color=TINTA_SUAVE)
    for c in range(3):
        ax[3][c].set_xlabel("segundos desde a folha sair do repouso")
        ax[0][c].set_xlim(-0.1, dur + 0.15)
    ax[0][2].legend(loc="lower right")
    return _salvar(fig, "porta_abrir.png")


def painel_porta_empurrao():
    """Por que a abertura é guiada pela mão: um empurrão solto (impulso 0,35 s) chega ao batente a 1,4 rad/s."""
    _estilo()
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    fig.suptitle("Porta: empurrão curto e a folha solta contra a folha guiada pela mão (25 kg, 90 graus)", x=0.01, ha="left",
                 fontsize=11.5, fontweight="bold")
    solto = P.simular(P.pulso_de_mao(51.0, 0.35), 0.0, 0.0, 2.0, 25.0, restituicao=P.RESTITUICAO)
    t, theta, omega, *_ = P.trajetoria_minima_variacao_de_torque(1.1, 25.0)
    ax[0].plot(solto["t"], np.degrees(solto["theta"]), color=COR_MODELO, lw=1.8, label="empurrão de 51 N por 0,35 s, solta")
    ax[0].plot(t, np.degrees(theta), color=COR_MODELO, lw=1.6, ls=(0, (4, 2)), label="guiada pela mão, 1,1 s")
    ax[0].set_ylabel("ângulo (graus)")
    ax[1].plot(solto["t"], solto["omega"], color=COR_MODELO, lw=1.8)
    ax[1].plot(t, omega, color=COR_MODELO, lw=1.6, ls=(0, (4, 2)))
    ax[1].set_ylabel("velocidade angular (rad/s)")
    for a in ax[:2]:
        a.set_xlim(0, 2.0)
        a.set_xlabel("segundos")
    ax[0].legend(loc="lower right")
    v_chegada = float(np.max(np.abs([b[1] for b in solto["batidas"][:1]]))) if solto["batidas"] else 0.0
    ax[1].annotate(f"chega ao batente a {v_chegada:.2f} rad/s\n({v_chegada * P.LARGURA:.1f} m/s na ponta)", (solto["batidas"][0][0], v_chegada),
                   (0.7, 1.9), fontsize=8.5, arrowprops={"arrowstyle": "-", "color": TINTA_SUAVE})
    # esforço: a força necessária para cada duração
    duracoes = np.linspace(0.5, 1.8, 40)
    ax[2].plot(duracoes, [P.forca_pico_jerk_minimo(d, 25.0) for d in duracoes], color=COR_MODELO, lw=1.8, label="25 kg")
    ax[2].plot(duracoes, [P.forca_pico_jerk_minimo(d, 40.0) for d in duracoes], color=COR_MODELO, lw=1.6, ls=(0, (4, 2)), label="40 kg (porta de entrada)")
    ax[2].axhline(P.F_CONFORTO, color=TINTA_SUAVE, lw=0.9, ls="--")
    ax[2].axvspan(0.9, 1.4, color=COR_JOGO, alpha=0.12, lw=0)
    ax[2].text(0.92, 150, "faixa do jogo\n0,9 a 1,4 s", fontsize=8.5)
    ax[2].set_xlabel("duração da abertura de 90 graus (s)")
    ax[2].set_ylabel("força de pico na maçaneta (N)")
    ax[2].set_ylim(0, 260)
    ax[2].legend()
    return _salvar(fig, "porta_empurrao_e_esforco.png")


def painel_porta_fecha_batida(g, antes):
    fecha, fecha0, bat, bat0 = g["fecha"], antes["fecha"], g["batida"], antes["batida"]
    _estilo()
    fig, ax = plt.subplots(2, 3, figsize=(13, 5.6))
    fig.suptitle("Porta: fechar com trinco e bater (folha de 25 kg, ponta a 0,81 m da dobradiça)", x=0.01, ha="left",
                 fontsize=11.5, fontweight="bold")
    # fechar: os últimos 0,35 s, folga na maçaneta em mm e a lingueta
    mm = P.RAIO_MACANETA * P.ABERTURA * 1000.0
    t_ch, _ = CP.chegada(fecha)
    t_ch0, _ = CP.chegada(fecha0)
    for rec, tc, cor, est, rot in ((fecha0, t_ch0, COR_ANTES, (0, (4, 2)), "antes"), (fecha, t_ch, COR_JOGO, "-", "depois")):
        j = (rec["t"] > tc - 0.3) & (rec["t"] < tc + 0.35)
        ax[0][0].plot(rec["t"][j] - tc, rec["x"][j] * mm, color=cor, lw=1.7, ls=est, label=f"jogo {rot}")
        ax[1][0].plot(rec["t"][j] - tc, rec["turn"][j], color=cor, lw=1.7, ls=est)
    ax[0][0].set_ylabel("posição na maçaneta (mm do batente)")
    ax[1][0].set_ylabel("lingueta recolhida (0..1)")
    ax[0][0].set_title("Fechar: chegada ao batente", loc="left")
    ax[1][0].set_xlabel("segundos desde a chegada")
    ax[0][0].axvline(0, color=TINTA_SUAVE, lw=0.8, ls="--")
    ax[1][0].axvline(0, color=TINTA_SUAVE, lw=0.8, ls="--")
    ax[0][0].legend()
    ax[0][0].text(0.05, ax[0][0].get_ylim()[1] * 0.55, "física: a lingueta recolhe nos\núltimos 11 mm e estala na chegada;\nrecuo de 1 a 3 mm", fontsize=8, color=TINTA_SUAVE)
    # batida
    sim, t_sim, w_sim, tip = P.golpe_de_porta()
    ate = sim["t"] <= t_sim + 0.02            # depois do impacto o modelo seria um rebote livre; a lingueta o limita a milímetros
    sim = {"t": sim["t"][ate], "theta": sim["theta"][ate], "omega": sim["omega"][ate]}
    ax[0][1].plot(sim["t"], np.degrees(sim["theta"]), color=COR_MODELO, lw=1.8)
    ax[1][1].plot(sim["t"], sim["omega"], color=COR_MODELO, lw=1.8)
    ax[0][1].text(0.43, 40, f"impacto a {w_sim:.1f} rad/s\n({tip:.1f} m/s na ponta);\nsem lingueta o rebote seria livre,\ncom ela fica em ~5 mm", fontsize=8, color=TINTA_SUAVE)
    ax[0][1].set_title("Batida: modelo (golpe de 400 N por 0,15 s)", loc="left")
    for rec, cor, est, rot in ((bat0, COR_ANTES, (0, (4, 2)), "antes"), (bat, COR_JOGO, "-", "depois")):
        t_in = float(rec["t"][np.nonzero(rec["x"] < 1 - 1e-4)[0][0]])
        ax[0][2].plot(rec["t"] - t_in, np.degrees(rec["theta"]), color=cor, lw=1.7, ls=est, label=f"jogo {rot}")
        ax[1][2].plot(rec["t"] - t_in, rec["omega"], color=cor, lw=1.7, ls=est)
    ax[0][2].plot(sim["t"], np.degrees(sim["theta"]), color=COR_MODELO, lw=1.4, label="modelo")
    ax[1][2].plot(sim["t"], sim["omega"], color=COR_MODELO, lw=1.4)
    ax[0][2].set_title("Batida: jogo contra modelo", loc="left")
    ax[0][2].legend()
    for a in (ax[0][1], ax[0][2]):
        a.set_ylabel("ângulo (graus)")
        a.set_xlim(-0.02, 0.8)
    for a in (ax[1][1], ax[1][2]):
        a.set_ylabel("velocidade (rad/s)")
        a.set_xlabel("segundos desde o golpe")
        a.set_xlim(-0.02, 0.8)
    return _salvar(fig, "porta_fecha_e_batida.png")


def painel_porta_inverte(g, antes):
    _estilo()
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.7), sharey=True)
    fig.suptitle("Porta: mudar de ideia no meio (a folha ainda anda um pouco: inércia e esforço curto de 100 a 250 N)", x=0.01,
                 ha="left", fontsize=11.5, fontweight="bold")
    for a, (fracao, rec) in zip(ax, g["inverte"].items()):
        rec0 = antes["inverte"][fracao]
        k0 = int((0.14 + fracao) * 240)
        w0 = float(rec["omega"][k0])
        x0 = float(rec["x"][k0])
        massa = CP.massa_da_porta(rec)
        lo = P.reverter(0, w0, massa, 250.0) / P.ABERTURA
        hi = (abs(w0) * 0.10 + P.reverter(0, w0, massa, 100.0)) / P.ABERTURA
        a.axhspan(x0 + lo, x0 + hi, color=COR_MODELO, alpha=0.18, lw=0, label="avanço permitido pela física")
        a.plot(rec0["t"], rec0["x"], color=COR_ANTES, lw=1.6, ls=(0, (4, 2)), label="jogo antes")
        a.plot(rec["t"], rec["x"], color=COR_JOGO, lw=1.8, label="jogo depois")
        a.axvline(0.14 + fracao, color=TINTA_SUAVE, lw=0.8, ls="--")
        a.set_title(f"apertar E aos {fracao:.0%} da abertura", loc="left")
        a.set_xlabel("segundos")
        a.set_xlim(0, 2.4)
    ax[0].set_ylabel("abertura (0 fechada, 1 aberta)")
    ax[0].legend(loc="upper right")
    return _salvar(fig, "porta_inverte.png")


def painel_porta_13(g, antes):
    _estilo()
    linhas, linhas0 = CP.tabela_13_portas(g), CP.tabela_13_portas(antes)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
    fig.suptitle("As 13 portas: esforço da mão e duração (cada tipo com a sua massa, ESTIMADA)", x=0.01, ha="left", fontsize=11.5,
                 fontweight="bold")
    nomes = [l["porta"] for l in linhas]
    y = np.arange(len(nomes))
    ax[0].scatter([l["forca_normal"] for l in linhas], y, color=COR_JOGO, s=34, zorder=3, label="normal (depois)")
    ax[0].scatter([l["forca_apressado"] for l in linhas], y, color=COR_JOGO, s=34, marker="s", zorder=3, label="apressado (depois)")
    ax[0].scatter([l["forca_apressado"] for l in linhas0], y, color=COR_ANTES, s=30, marker="x", zorder=3, label="apressado (antes)")
    ax[0].axvline(P.F_CONFORTO, color=TINTA_SUAVE, lw=0.9, ls="--")
    ax[0].set_yticks(y)
    ax[0].set_yticklabels([f"{l['porta']} ({l['massa_kg']:.0f} kg)" for l in linhas], fontsize=8)
    ax[0].set_xlabel("força de pico na maçaneta (N); linha = 100 N")
    ax[0].legend(loc="lower right")
    ax[1].scatter([l["dur_normal"] for l in linhas], y, color=COR_JOGO, s=34, zorder=3, label="normal")
    ax[1].scatter([l["dur_apressado"] for l in linhas], y, color=COR_JOGO, s=34, marker="s", zorder=3, label="apressado (depois)")
    ax[1].scatter([l["dur_apressado"] for l in linhas0], y, color=COR_ANTES, s=30, marker="x", zorder=3, label="apressado (antes)")
    ax[1].scatter([l["t_min_100N"] for l in linhas], y, color=COR_MODELO, s=36, marker="|", linewidths=2, zorder=2, label="menor duração a 100 N")
    ax[1].set_yticks(y)
    ax[1].set_yticklabels([])
    ax[1].set_xlabel("duração da abertura (s)")
    ax[1].legend(loc="lower right")
    return _salvar(fig, "porta_13_portas.png")


def painel_mao_real(g):
    _estilo()
    fig, ax = plt.subplots(1, 2, figsize=(13, 3.9))
    fig.suptitle("A mão que abre a porta contra mãos reais empurrando e erguendo janela (mocap CMU, MEDIDO)", x=0.01, ha="left",
                 fontsize=11.5, fontweight="bold")
    try:
        erguer = mao_real.gestos_de_erguer("RightHand") + mao_real.gestos_de_erguer("LeftHand")
        empurrar = mao_real.gestos_de_empurrar("RightHand") + mao_real.gestos_de_empurrar("LeftHand")
    except Exception as erro:       # noqa: BLE001
        print("mocap indisponível:", erro)
        return None
    u = np.linspace(0, 1, 50)
    for lista, nome, cor in ((erguer, f"erguer janela ({len(erguer)} gestos)", COR_MODELO), (empurrar, f"empurrar ({len(empurrar)} gestos)", "#3f9e6b")):
        perfis = np.array([gm["perfil"] for gm in lista])
        media, dp = perfis.mean(axis=0), perfis.std(axis=0)
        ax[0].plot(u, media, color=cor, lw=1.8, label=nome)
        ax[0].fill_between(u, media - dp, media + dp, color=cor, alpha=0.15, lw=0)
    rec = g["abre"]["normal"]
    v = np.abs(rec["omega"]) * P.RAIO_MACANETA
    ativo = np.nonzero(v > CP.LIMIAR_GESTO)[0]
    seg = v[ativo[0]:ativo[-1] + 1]
    ax[0].plot(np.linspace(0, 1, len(seg)), seg / seg.max(), color=COR_JOGO, lw=2.0, label="porta do jogo (maçaneta)")
    ax[0].set_xlabel("fração do gesto")
    ax[0].set_ylabel("velocidade da mão / pico")
    ax[0].legend(loc="upper right")
    # dispersão duração x trajeto
    ax[1].scatter([gm["trajeto"] for gm in erguer], [gm["duracao"] for gm in erguer], color=COR_MODELO, s=22, label="erguer janela")
    ax[1].scatter([gm["trajeto"] for gm in empurrar], [gm["duracao"] for gm in empurrar], color="#3f9e6b", marker="s", s=22, label="empurrar")
    gj = CP.gesto_do_jogo(rec)
    ax[1].scatter([gj["trajeto"]], [gj["duracao"]], color=COR_JOGO, marker="D", s=70, zorder=4, label="porta do jogo")
    ax[1].set_xlabel("trajeto da mão (m)")
    ax[1].set_ylabel("duração (s)")
    ax[1].legend(loc="upper left")
    return _salvar(fig, "porta_mao_real.png")


# --------------------------------------------------------------------------
# Relógio
# --------------------------------------------------------------------------
def painel_relogio(r):
    t, theta, mao, tiques = r["t"], r["theta"], r["mao"], r["tiques"]
    ref_t, ref_theta, ref_tiques = R.simular(20.0, R.comprimento_equivalente(R.comprimento_para_periodo(2.0)))
    _estilo()
    fig, ax = plt.subplots(3, 2, figsize=(13, 7.4), gridspec_kw={"height_ratios": [1.1, 1.1, 1.0]})
    fig.suptitle("Relógio de pé: pêndulo de segundos (T = 2 s, l_eq = 0,994 m), tique depois do centro e ponteiro dos segundos",
                 x=0.01, ha="left", fontsize=11.5, fontweight="bold")
    ax[0][0].plot(ref_t, np.degrees(ref_theta), color=COR_MODELO, lw=1.8)
    ax[0][0].set_title("Modelo físico (RK4 com escape)", loc="left")
    j = t <= 20
    ax[0][1].plot(t[j], np.degrees(theta[j]), color=COR_JOGO, lw=1.8)
    ax[0][1].set_title("Jogo (engine/clockwork.py)", loc="left")
    for a, tq in ((ax[0][0], ref_tiques[ref_tiques < 20]), (ax[0][1], tiques[tiques < 20])):
        a.vlines(tq, -3.4, -3.0, color=TINTA, lw=1.0)
        a.set_ylabel("pêndulo (graus)")
        a.set_ylim(-3.6, 3.2)
    ax[0][1].text(0.2, 2.6, "riscos: tiques (1 por segundo)", fontsize=8, color=TINTA_SUAVE)
    # zoom em dois tiques
    for a, (tt, th, tq, cor) in zip(ax[1], ((ref_t, ref_theta, ref_tiques, COR_MODELO), (t, theta, tiques, COR_JOGO))):
        k = (tt > 10.2) & (tt < 12.8)
        a.plot(tt[k], np.degrees(th[k]), color=cor, lw=1.8)
        a.axhline(0, color=GRADE, lw=1)
        for q in tq[(tq > 10.2) & (tq < 12.8)]:
            a.axvline(q, color=TINTA, lw=0.9, ls="--")
        a.set_ylabel("pêndulo (graus)")
        a.set_title("Zoom: o tique cai ~25 ms depois do centro do arco", loc="left")
    # ponteiro dos segundos
    ref_mao = R.posicao_do_segundeiro(ref_tiques, ref_t)
    ax[2][0].plot(ref_t[ref_t < 8], ref_mao[ref_t < 8], color=COR_MODELO, lw=1.8)
    j = t < 8
    ax[2][1].plot(t[j], np.degrees(mao[j]), color=COR_JOGO, lw=1.8)
    for a in ax[2]:
        a.set_ylabel("ponteiro dos segundos (graus)")
        a.set_xlabel("segundos")
    ax[2][0].set_title("Degraus de 6 graus a cada tique (60 dentes)", loc="left")
    ax[2][1].set_title("Jogo: salto com acomodação de mola (18 Hz, zeta 0,35)", loc="left")
    return _salvar(fig, "relogio_pendulo.png")


# --------------------------------------------------------------------------
# Carro
# --------------------------------------------------------------------------
def painel_carro_suspensao(s, s0):
    ref = CC.referencia_do_carro(s)
    t = s["t"]
    j = (t > 7.5) & (t < 17.5)
    fig, ax = _colunas("Carro: arfagem da carroceria (nariz para cima = positivo) na saída da garagem",
                       3, ["velocidade para a frente (m/s)", "aceleração para a frente (m/s2)", "arfagem (graus)"])
    v_ref = -np.gradient(ref["y"], 1 / s["fps"])
    ax[0][0].plot(t[j], v_ref[j], color=COR_MODELO, lw=1.8)
    ax[0][1].plot(t[j], s["sinais"]["speed"][j], color=COR_JOGO, lw=1.8)
    ax[0][2].plot(t[j], v_ref[j], color=COR_MODELO, lw=1.8)
    ax[0][2].plot(t[j], s["sinais"]["speed"][j], color=COR_JOGO, lw=1.4, ls=":")
    ax[1][0].plot(t[j], ref["a_frente"][j], color=COR_MODELO, lw=1.8)
    ax[1][1].plot(t[j], s["sinais"]["accel"][j], color=COR_JOGO, lw=1.8)
    ax[1][2].plot(t[j], ref["a_frente"][j], color=COR_MODELO, lw=1.8)
    ax[1][2].plot(t[j], s["sinais"]["accel"][j], color=COR_JOGO, lw=1.4, ls=":")
    ax[1][2].plot(s0["t"][j], -s0["sinais"]["accel"][j], color=COR_ANTES, lw=1.4, ls=(0, (4, 2)))
    _tres(ax[2], t[j], np.degrees(ref["theta"][j]), t[j], np.degrees(s["euler"][j, 0]), s0["t"][j], np.degrees(s0["euler"][j, 0]))
    ax[2][2].legend(loc="lower left")
    ax[2][0].text(12.6, 0.15, "meio carro: massa sobre 2 molas\n(1,15 e 1,30 Hz, zeta 0,3),\nchão lido do mundo 3D", fontsize=8, color=TINTA_SUAVE)
    for c in range(3):
        ax[2][c].set_xlabel("segundos (a cena)")
    ax[2][2].text(12.6, 0.12, "antes: arfagem invertida\n(usava a aceleração do eixo Y\ndo mundo, não a da frente do carro)", fontsize=7.5, color=TINTA_SUAVE)
    return _salvar(fig, "carro_arfagem.png")


def painel_carro_rodas(s, s0):
    _estilo()
    fig, ax = plt.subplots(2, 3, figsize=(13, 6.0))
    fig.suptitle("Carro: rodas rolando sem deslizar, esterçamento de Ackermann e o volante", x=0.01, ha="left", fontsize=11.5,
                 fontweight="bold")
    for rec, cor, est, rot in ((s0, COR_ANTES, (0, (4, 2)), "antes"), (s, COR_JOGO, "-", "depois")):
        fps = rec["fps"]
        t = rec["t"]
        giro = np.unwrap(rec["roda"][:, 0, 0])
        w = np.gradient(giro, 1 / fps)
        v = rec["sinais"]["speed"]
        mover = np.abs(v) > 0.3
        ax[0][0].plot(t[mover], (-w * KC.RAIO_RODA)[mover], color=cor, lw=1.7, ls=est, label=f"jogo {rot}")
        ax[0][1].plot(t[mover], (np.degrees(rec["sinais"]["steer"]))[mover], color=cor, lw=1.7, ls=est, label=f"jogo {rot}")
        ax[0][2].plot(t[mover], np.degrees(rec["euler"][:, 1])[mover], color=cor, lw=1.7, ls=est)
    v = s["sinais"]["speed"]
    mover = np.abs(v) > 0.3
    ax[0][0].plot(s["t"][mover], v[mover], color=COR_MODELO, lw=1.6, label="modelo: w R = v")
    ax[0][0].set_ylabel("w R, velocidade do centro (m/s)")
    ax[0][0].set_title("Rotação da roda x velocidade", loc="left")
    ax[0][0].legend()
    kappa = CC.curvatura_do_caminho(s)
    ax[0][1].plot(s["t"][mover], np.degrees(np.arctan(KC.ENTRE_EIXOS * kappa))[mover], color=COR_MODELO, lw=1.6, label="Ackermann: atan(L kappa)")
    ax[0][1].set_ylabel("esterçamento das rodas (graus)")
    ax[0][1].set_title("Esterçamento", loc="left")
    ax[0][1].legend()
    ax[0][2].set_ylabel("rolagem da carroceria (graus)")
    ax[0][2].set_title("Rolagem (a aceleração lateral é pequena)", loc="left")
    # deslizamento do ponto de contato
    for rec, cor, est, rot in ((s0, COR_ANTES, (0, (4, 2)), "antes"), (s, COR_JOGO, "-", "depois")):
        valor = CC.deslizamento_das_rodas(rec)
        ax[1][0].bar([rot], [valor], color=cor, width=0.55)
        ax[1][0].text(rot, valor + 0.04, f"{valor:.3f}", ha="center", fontsize=9)
    ax[1][0].axhline(0.05, color=TINTA_SUAVE, lw=0.9, ls="--")
    ax[1][0].set_ylabel("v do contato / v do centro")
    ax[1][0].set_title("Deslizamento do pneu (0 = rola; 2 = gira ao contrário)", loc="left")
    ax[1][0].text(0.6, 0.12, "limite 0,05", fontsize=8, color=TINTA_SUAVE)
    # volante
    for rec, cor, est, rot in ((s0, COR_ANTES, (0, (4, 2)), "antes"), (s, COR_JOGO, "-", "depois")):
        q = rec["volante"]
        eixo = np.array([0.0, -math.sin(math.radians(65.0)), math.cos(math.radians(65.0))])
        ang = np.degrees(2.0 * np.arctan2(q[:, 1:] @ eixo, q[:, 0]))
        m = np.abs(rec["sinais"]["speed"]) > 0.3
        ax[1][1].plot(rec["t"][m], ang[m], color=cor, lw=1.7, ls=est, label=f"jogo {rot}")
    steer = np.degrees(np.arctan(KC.ENTRE_EIXOS * kappa))
    ax[1][1].plot(s["t"][mover], KC.RELACAO_DIRECAO * steer[mover], color=COR_MODELO, lw=1.6, label="modelo: 15 x esterçamento")
    ax[1][1].set_ylabel("volante (graus)")
    ax[1][1].set_xlabel("segundos")
    ax[1][1].set_title("Volante (relação 15:1, esquerda = positivo)", loc="left")
    ax[1][1].legend()
    # trajetória em planta
    for rec, cor, est, rot in ((s0, COR_ANTES, (0, (4, 2)), "antes"), (s, COR_JOGO, "-", "depois")):
        ax[1][2].plot((rec["pos"][:, 0] - 15.5) * 100, rec["pos"][:, 1], color=cor, lw=1.7, ls=est, label=f"jogo {rot}")
    ax[1][2].set_xlabel("desvio lateral (cm)")
    ax[1][2].set_ylabel("y (m)")
    ax[1][2].set_title("Caminho (a correção de volante precisa ser possível)", loc="left")
    ax[1][2].legend()
    for a in (ax[0][0], ax[0][1], ax[0][2]):
        a.set_xlabel("segundos")
    return _salvar(fig, "carro_rodas_direcao.png")


def painel_charm(s, s0):
    ref = CC.referencia_do_carro(s)
    t = s["t"]
    lb = CC.comprimento_equivalente("Cut_Bunny")
    lk = CC.comprimento_equivalente("Cut_KeyCharm")
    ref_b = np.degrees(KC.simular_pendulo(t, lb, 0.04, lambda x: float(np.interp(x, t, ref["a_frente"]))))
    ref_k = np.degrees(KC.simular_pendulo(t, lk, 0.04, lambda x: float(np.interp(x, t, ref["a_frente"]))))
    j = (t > 6.0) & (t < 18.0)
    fig, ax = _colunas(f"Coelhinho do retrovisor e chaveiro: pêndulo composto (l_eq {lb:.3f} m e {lk:.3f} m, calculados da malha) forçado pelo carro",
                       2, ["coelhinho: ângulo contra a vertical (graus)", "chaveiro: ângulo (graus)"])
    mundo = np.degrees(s["coelho"][:, 0] + s["euler"][:, 0])
    mundo0 = np.degrees(s0["coelho"][:, 0] + 0.35 * s0["euler"][:, 0])
    _tres(ax[0], t[j], ref_b[j], t[j], mundo[j], s0["t"][j], mundo0[j])
    mk = np.degrees(s["chaveiro"][:, 0] + s["euler"][:, 0])
    mk0 = np.degrees(s0["chaveiro"][:, 0] + 0.35 * s0["euler"][:, 0])
    _tres(ax[1], t[j], ref_k[j], t[j], mk[j], s0["t"][j], mk0[j])
    ax[0][2].legend(loc="lower left")
    for c in range(3):
        ax[1][c].set_xlabel("segundos")
    ax[1][0].text(6.3, -9.0, "ângulo positivo = para a frente do carro: acelerar joga o pêndulo para trás, frear para a frente", fontsize=8, color=TINTA_SUAVE)
    return _salvar(fig, "charm_pendulos.png")


def painel_portao(p, p0, s, s0):
    _estilo()
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))
    fig.suptitle("Portão da garagem: abridor residencial a ~19 cm/s com partida e parada suaves (2,3 m em ~12 s)", x=0.01, ha="left",
                 fontsize=11.5, fontweight="bold")
    t = p["t"]
    ideal = np.zeros_like(t)
    t0, T, rampa, v = p["inicio"], p["duracao"], 1.0, 2.3 / (p["duracao"] - 1.0)
    # modelo: velocidade em rampa suave, cruzeiro, rampa suave (a mesma lei de um motor com partida suave, escrita à parte)
    def vel(tau):
        if tau <= 0 or tau >= T:
            return 0.0
        if tau < rampa:
            u = tau / rampa
            return v * (3 * u * u - 2 * u ** 3)
        if tau > T - rampa:
            u = (T - tau) / rampa
            return v * (3 * u * u - 2 * u ** 3)
        return v
    ideal = np.cumsum([vel(x - t0) for x in t]) / p["fps"]
    ax[0].plot(t, ideal, color=COR_MODELO, lw=1.8, label="modelo: 19 cm/s, rampa de 1 s")
    ax[0].plot(p0["t"], p0["z"], color=COR_ANTES, lw=1.6, ls=(0, (4, 2)), label="jogo antes (2,3 m em 3 s)")
    ax[0].plot(t, p["z"], color=COR_JOGO, lw=1.8, ls=":", label="jogo depois")
    ax[0].set_xlabel("segundos (a cena)")
    ax[0].set_ylabel("altura da folha (m)")
    ax[0].legend(loc="lower right")
    for rec, cor, est, rot in ((p0, COR_ANTES, (0, (4, 2)), "antes"), (p, COR_JOGO, "-", "depois")):
        janela = max(3, int(rec["fps"] // 2))
        zs = np.convolve(rec["z"], np.ones(janela) / janela, mode="same")
        ax[1].plot(rec["t"], np.gradient(zs, 1 / rec["fps"]), color=cor, lw=1.7, ls=est, label=f"jogo {rot}")
    ax[1].axhspan(0.15, 0.20, color=COR_MODELO, alpha=0.2, lw=0, label="abridor residencial 15 a 20 cm/s")
    ax[1].set_ylim(0, 1.6)
    ax[1].set_xlabel("segundos")
    ax[1].set_ylabel("velocidade da folha (m/s)")
    ax[1].legend(loc="upper right")
    # folga do teto do carro
    for rec_p, rec_s, cor, est, rot in ((p0, s0, COR_ANTES, (0, (4, 2)), "antes"), (p, s, COR_JOGO, "-", "depois")):
        tt = rec_s["t"]
        y_frente, y_tras = rec_s["pos"][:, 1] - 2.42, rec_s["pos"][:, 1] + 2.42
        folga = np.interp(tt, rec_p["t"], rec_p["z"]) - (rec_s["pos"][:, 2] + KC.TETO)
        sob = (y_frente < 0.158) & (y_tras > -0.064)
        ax[2].plot(tt, np.where(sob, folga, np.nan), color=cor, lw=2.0, ls=est, label=f"jogo {rot}")
    ax[2].axhline(0.10, color=TINTA_SUAVE, lw=0.9, ls="--")
    ax[2].set_xlabel("segundos")
    ax[2].set_ylabel("folga teto do carro - folha (m)")
    ax[2].set_title("enquanto o carro passa sob a folha", loc="left")
    ax[2].legend()
    return _salvar(fig, "portao_garagem.png")


# --------------------------------------------------------------------------
# Cortina, poeira, luzes
# --------------------------------------------------------------------------
def painel_cortina(c, c0):
    _estilo()
    fig, ax = plt.subplots(2, 2, figsize=(13, 6.4))
    fig.suptitle("Cortina ao vento: modos de um pano pendurado (corrente de Bernoulli) excitados por vento turbulento", x=0.01,
                 ha="left", fontsize=11.5, fontweight="bold")
    f_modos = KT.frequencias_dos_modos(c["altura"])
    ts, yb, _ = KT.simular(c["altura"], duracao=600.0)
    for a, (t, y, cor, titulo) in zip((ax[0][0], ax[0][1]), ((ts, yb, COR_MODELO, "Modelo: bainha, integração dos modos (normalizada)"),
                                                           (c["t"], c["deslocamento"][:, 0, -1, 1], COR_JOGO, "Jogo (depois): bainha, deslocamento em metros"))):
        k = t < 60
        a.plot(t[k], y[k] - np.mean(y), color=cor, lw=1.3)
        a.set_title(titulo, loc="left")
        a.set_xlabel("segundos")
    for tt, yy, cor, est, rot in ((c0["t"], c0["deslocamento"][:, 0, -1, 1], COR_ANTES, (0, (4, 2)), "jogo antes"),
                                  (c["t"], c["deslocamento"][:, 0, -1, 1], COR_JOGO, "-", "jogo depois"), (ts, yb, COR_MODELO, "-", "modelo")):
        f, p = KT.espectro(tt, yy, 0.05)
        largura = max(3, int(round(0.05 / (f[1] - f[0]))))          # média numa janela de 0,05 Hz: tira o ruído da estimativa
        p = np.convolve(p, np.ones(largura) / largura, mode="same")
        m = f < 2.5
        ax[1][0].plot(f[m], p[m] / p[m].max(), color=cor, lw=1.6, ls=est, label=rot)
    for n, fn in enumerate(f_modos, 1):
        ax[1][0].axvline(fn, color=TINTA_SUAVE, lw=0.8, ls="--")
        ax[1][0].text(fn + 0.02, 0.92, f"modo {n}\n{fn:.2f} Hz", fontsize=8, color=TINTA_SUAVE, va="top")
    ax[1][0].axvspan(0.3, 1.0, color=COR_MODELO, alpha=0.08, lw=0)
    ax[1][0].set_xlabel("frequência (Hz)")
    ax[1][0].set_ylabel("potência (relativa ao pico)")
    ax[1][0].set_title("Espectro da bainha", loc="left")
    ax[1][0].legend(loc="upper right")
    fr, pj = CA.perfil_de_amplitude(c)
    _, pj0 = CA.perfil_de_amplitude(c0)
    alturas, rms = CA._perfil_fisico(c["altura"])
    ax[1][1].plot(rms / rms[-1], alturas, color=COR_MODELO, lw=1.8, label="modelo (3 modos)")
    ax[1][1].plot(KT.forma_do_modo(alturas, 1), alturas, color=COR_MODELO, lw=1.2, ls=(0, (1, 2)), label="só o 1o modo: J0(2,40 raiz(1-h))")
    ax[1][1].plot(pj0, fr, color=COR_ANTES, lw=1.6, ls=(0, (4, 2)), label="jogo antes")
    ax[1][1].plot(pj, fr, color=COR_JOGO, lw=1.8, ls=":", label="jogo depois")
    ax[1][1].invert_yaxis()
    ax[1][1].set_xlabel("RMS da oscilação / RMS na bainha")
    ax[1][1].set_ylabel("distância à barra / altura")
    ax[1][1].set_title("Amplitude cresce de cima para baixo", loc="left")
    ax[1][1].legend(loc="lower left", fontsize=8)
    return _salvar(fig, "cortina_modos.png")


def painel_poeira(p, p0):
    _estilo()
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))
    fig.suptitle("Poeira do forro: velocidade terminal pela lei de arrasto (poeira fina cai a poucos cm/s)", x=0.01, ha="left",
                 fontsize=11.5, fontweight="bold")
    fisica = CA.amostra_fisica()
    vt, tau = CA.velocidades_terminais_do_jogo(p)
    vt0, tau0 = CA.velocidades_terminais_do_jogo(p0)
    for x, cor, est, rot in ((fisica, COR_MODELO, "-", "modelo (Schiller-Naumann)"), (vt0, COR_ANTES, (0, (4, 2)), "jogo antes"), (vt, COR_JOGO, "-", "jogo depois")):
        s = np.sort(x)
        ax[0].step(s, np.arange(1, len(s) + 1) / len(s), color=cor, lw=1.7, ls=est, label=rot, where="post")
    ax[0].set_xscale("log")
    ax[0].set_xlabel("velocidade terminal (m/s)")
    ax[0].set_ylabel("fração das partículas")
    ax[0].legend(loc="lower right")
    d = np.logspace(math.log10(10e-6), math.log10(1e-3), 60)
    ax[1].loglog(d * 1e6, KT.velocidade_terminal(d), color=COR_MODELO, lw=1.8)
    for nome, (lo, hi), fracao in KT.classes_de_poeira()[:2]:
        ax[1].axvspan(lo * 1e6, hi * 1e6, color=COR_JOGO, alpha=0.15, lw=0)
        ax[1].text(lo * 1e6, 0.012, nome, fontsize=8)
    ax[1].set_xlabel("diâmetro (micra)")
    ax[1].set_ylabel("velocidade terminal (m/s)")
    ax[1].set_title("Esferas de reboco (1800 kg/m3)", loc="left")
    for rec, cor, est in ((p0, COR_ANTES, (0, (4, 2))), (p, COR_JOGO, "-")):
        for j in range(0, rec["z"].shape[1], 7):
            vivo = rec["tamanho"][:, j] > 0
            ax[2].plot(rec["t"][vivo] - rec["inicio"], rec["z"][vivo, j], color=cor, lw=0.9, ls=est, alpha=0.8)
    ax[2].plot([], [], color=COR_ANTES, ls=(0, (4, 2)), label="jogo antes")
    ax[2].plot([], [], color=COR_JOGO, label="jogo depois")
    ax[2].legend()
    ax[2].set_xlabel("segundos depois do abalo")
    ax[2].set_ylabel("altura (m)")
    ax[2].set_title("Quedas (1 em cada 7 partículas)", loc="left")
    return _salvar(fig, "poeira_queda.png")


def painel_luz(l, l0):
    _estilo()
    fig, ax = plt.subplots(2, 3, figsize=(13, 6.0))
    fig.suptitle("Luzes: filamento incandescente (dezenas de ms), fluorescente com reator ruim (rajadas de 3 a 10 Hz) e TV com chuvisco",
                 x=0.01, ha="left", fontsize=11.5, fontweight="bold")
    t = np.arange(0, 0.5, 0.001)
    modelo_off = KL.simular_filamento(t, lambda x: 0.0, u0=1.0)
    ax[0][0].plot(t * 1000, modelo_off, color=COR_MODELO, lw=1.8, label="modelo")
    for rec, cor, est, rot in ((l0["liga_desliga"]["ceiling"], COR_ANTES, (0, (4, 2)), "jogo antes"), (l["liga_desliga"]["ceiling"], COR_JOGO, "-", "jogo depois")):
        k = (rec["t"] > 0.5) & (rec["t"] < 1.0)
        ax[0][0].plot((rec["t"][k] - 0.5) * 1000, rec["energia"][k] / rec["base"], color=cor, lw=1.7, ls=est, label=rot)
    ax[0][0].set_xlim(0, 300)
    ax[0][0].set_xlabel("ms depois de a energia cair")
    ax[0][0].set_ylabel("luz relativa")
    ax[0][0].set_title("Incandescente desligando", loc="left")
    ax[0][0].legend()
    t2 = np.arange(0, 0.5, 0.001)
    modelo_on = KL.simular_filamento(t2, lambda x: 1.0)
    ax[0][1].plot(t2 * 1000, modelo_on, color=COR_MODELO, lw=1.8, label="modelo")
    for rec, cor, est, rot in ((l0["liga_desliga"]["ceiling"], COR_ANTES, (0, (4, 2)), "jogo antes"), (l["liga_desliga"]["ceiling"], COR_JOGO, "-", "jogo depois")):
        k = (rec["t"] > 1.5) & (rec["t"] < 2.0)
        ax[0][1].plot((rec["t"][k] - 1.5) * 1000, rec["energia"][k] / rec["base"], color=cor, lw=1.7, ls=est)
    ax[0][1].set_xlim(0, 300)
    ax[0][1].set_xlabel("ms depois de a energia voltar")
    ax[0][1].set_title("Incandescente ligando (partida a frio)", loc="left")
    for a, (nome, chave) in zip((ax[1][0], ax[1][1]), (("Fluorescente da garagem (flicker 0,25)", "fluorescente_garagem"), ("Fluorescente da cozinha (flicker 0,10)", "fluorescente_cozinha"))):
        pass
    r = l["pisca"]["fluorescente_garagem"]
    r0 = l0["pisca"]["fluorescente_garagem"]
    k = r["t"] < 40
    ax[1][0].plot(r0["t"][k], r0["ganho"][k], color=COR_ANTES, lw=1.0, ls=(0, (4, 2)), label="antes")
    ax[1][0].plot(r["t"][k], r["ganho"][k], color=COR_JOGO, lw=1.0, label="depois")
    ax[1][0].set_title("Garagem, 40 s: rajadas e trechos estáveis", loc="left")
    ax[1][0].set_xlabel("segundos")
    ax[1][0].set_ylabel("luz relativa")
    ax[1][0].legend(loc="lower right")
    rajadas, _ = KL.estatisticas_de_rajadas(r["t"], r["ganho"])
    maior = max(rajadas, key=lambda x: x["ciclos"])
    k2 = (r["t"] > maior["inicio"] - 0.3) & (r["t"] < maior["inicio"] + maior["duracao"] + 0.6)
    ax[1][1].plot(r["t"][k2] - maior["inicio"], r["ganho"][k2], color=COR_JOGO, lw=1.6)
    ax[1][1].set_title(f"Uma rajada: {maior['ciclos']} piscadas a {maior['frequencia']:.1f} Hz", loc="left")
    ax[1][1].set_xlabel("segundos")
    tv, tv0 = l["pisca"]["tv"], l0["pisca"]["tv"]
    k = tv["t"] < 20
    ax[1][2].plot(tv0["t"][k], tv0["ganho"][k], color=COR_ANTES, lw=1.0, ls=(0, (4, 2)), label="antes (flicker 0,7)")
    ax[1][2].plot(tv["t"][k], tv["ganho"][k], color=COR_JOGO, lw=1.4, label="depois")
    ax[1][2].axhspan(1 - 0.04, 1.0, color=COR_MODELO, alpha=0.18, lw=0, label="física: variação de até 4%")
    ax[1][2].set_ylim(0, 1.05)
    ax[1][2].set_title("Luz da TV de chuvisco na sala", loc="left")
    ax[1][2].set_xlabel("segundos")
    ax[1][2].legend(loc="lower right")
    ax[0][2].axis("off")
    ax[0][2].text(0.0, 0.95, "Origem dos números", fontsize=10, fontweight="bold", va="top")
    off, on = KL.tempos_de_resposta()
    ax[0][2].text(0.0, 0.85, f"DERIVADO: expoente de Planck n = {KL.expoente_de_planck():.2f} (luz ~ T^n a 2800 K)\n"
                  f"DERIVADO: tau = C T_op / (4 P_op) = {KL.constante_de_tempo() * 1000:.0f} ms\n"
                  f"ESTIMADO: 18 mg de tungstênio, 0,16 J/g/K, R ~ T^1,2\n"
                  f"modelo: 10% da luz em {off * 1000:.0f} ms (desligar), 90% em {on * 1000:.0f} ms (ligar)\n\n"
                  f"ESTIMADO: fluorescente com reator ruim, 3 a 10 Hz,\n3 a 8 piscadas por rajada\n\n"
                  f"DERIVADO: o ruído de 300 mil pixels varia {KL.flutuacao_do_ruido() * 100:.2f}% a luz média\n"
                  f"ESTIMADO: sobra uma variação lenta de 2 a 4%", fontsize=8.5, va="top", color=TINTA)
    return _salvar(fig, "luz_incandescente_fluorescente_tv.png")


# --------------------------------------------------------------------------
def tabela_markdown(todas, caminho):
    linhas = ["# Objetos e física: valor físico contra o jogo, antes e depois", "",
              "ESTIMADO = engenharia lembrada de memória (faixa na nota); DERIVADO = lei física sobre medidas do modelo 3D; "
              "MEDIDO = mocap da CMU. Não existe vídeo real de portas, carros ou relógios neste ambiente.", "",
              medidas.tabela_markdown(todas)]
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas) + "\n")
    return caminho


def todas_as_metricas():
    g, g0 = CP.gravar(), medidas.carregar_gravacao("porta")
    s, p = CC.gravar()
    s0, p0 = medidas.carregar_gravacao("carro"), medidas.carregar_gravacao("portao")
    amb = CA.gravar()
    amb0 = {n: medidas.carregar_gravacao(n) for n in ("cortina", "poeira", "luzes")}
    r = grava.relogio()
    lista = CP.metricas_com_antes(g) + CC.metricas_com_antes(s, p) + CA.metricas_com_antes(amb) + CR.tabela_antes(CR.metricas(r))
    return lista, (g, g0, s, s0, p, p0, amb, amb0, r)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    lista, (g, g0, s, s0, p, p0, amb, amb0, r) = todas_as_metricas()
    saidas = []
    quer = lambda nome: not argv or nome in argv        # noqa: E731
    if quer("porta"):
        saidas += [painel_porta_abrir(g, g0), painel_porta_empurrao(), painel_porta_fecha_batida(g, g0), painel_porta_inverte(g, g0),
                   painel_porta_13(g, g0), painel_mao_real(g)]
    if quer("relogio"):
        saidas.append(painel_relogio(r))
    if quer("carro"):
        saidas += [painel_carro_suspensao(s, s0), painel_carro_rodas(s, s0), painel_charm(s, s0), painel_portao(p, p0, s, s0)]
    if quer("ambiente"):
        saidas += [painel_cortina(amb["cortina"], amb0["cortina"]), painel_poeira(amb["poeira"], amb0["poeira"]),
                   painel_luz(amb["luzes"], amb0["luzes"])]
    os.makedirs(SAIDA, exist_ok=True)
    saidas.append(tabela_markdown(lista, os.path.join(SAIDA, "tabela_fisica_objetos.md")))
    medidas.salvar_json(lista, "metricas_objetos")
    for caminho in saidas:
        print(caminho)
    return saidas


if __name__ == "__main__":
    main()
