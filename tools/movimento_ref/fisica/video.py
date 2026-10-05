"""Vídeos lado a lado [modelo físico | jogo] dos objetos, com a série do sinal principal embaixo (MP4, H.264, 30 quadros/s).

    python -m tools.movimento_ref.fisica.video [porta relogio charm portao carro cortina]

Cada cena é um esquema desenhado com matplotlib (vista de topo, de lado ou de frente, conforme o objeto) a partir de DUAS fontes
independentes: o modelo (código de `fisica/`) à esquerda e a gravação do jogo à direita, no mesmo instante e na mesma escala.
Não há câmera do Blender aqui: o movimento dos objetos é conferido pelas posições, não por pixels de renderização.
"""
import math
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import carro as KC
from . import comparar_carro as CC, cortina as KT, grava, medidas, porta as P, relogio as R
from .paineis import COR_ANTES, COR_JOGO, COR_MODELO, FUNDO, GRADE, TINTA, TINTA_SUAVE

FPS = 30


class Cena:
    """Dois painéis de esquema (modelo, jogo) e um gráfico da série principal com um cursor de tempo."""

    def __init__(self, titulo, t0, t1, serie, ylabel, legenda_tempo="segundos"):
        plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRADE, "text.color": TINTA, "axes.labelcolor": TINTA_SUAVE,
                             "xtick.color": TINTA_SUAVE, "ytick.color": TINTA_SUAVE})
        self.fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=FUNDO)
        grade = self.fig.add_gridspec(2, 2, height_ratios=[1.75, 1.0], left=0.05, right=0.985, top=0.9, bottom=0.09, wspace=0.07, hspace=0.25)
        self.ax_m = self.fig.add_subplot(grade[0, 0])
        self.ax_j = self.fig.add_subplot(grade[0, 1])
        self.ax_s = self.fig.add_subplot(grade[1, :])
        self.fig.text(0.012, 0.955, titulo, fontsize=14, fontweight="bold", va="center", ha="left")
        self.ax_m.set_title("MODELO FÍSICO (código independente)", color=COR_MODELO, loc="left", fontsize=11, fontweight="bold")
        self.ax_j.set_title("JOGO (gravação do código real)", color=COR_JOGO, loc="left", fontsize=11, fontweight="bold")
        for ax in (self.ax_m, self.ax_j):
            ax.set_facecolor(FUNDO)
        self.t0, self.t1 = t0, t1
        for chave, (t, y, cor, est, rot) in serie.items():
            self.ax_s.plot(t, y, color=cor, ls=est, lw=1.7, label=rot)
        self.ax_s.set_xlim(t0, t1)
        self.ax_s.set_ylabel(ylabel)
        self.ax_s.set_xlabel(legenda_tempo)
        self.ax_s.grid(True, color=GRADE, lw=0.7)
        self.ax_s.legend(loc="upper right", frameon=False, fontsize=9, ncol=3)
        for lado in ("top", "right"):
            self.ax_s.spines[lado].set_visible(False)
        self.cursor = self.ax_s.axvline(t0, color=TINTA, lw=1.0)
        self.atualiza = lambda t: None
        self.texto_t = self.fig.text(0.985, 0.955, "", fontsize=12, ha="right", va="center", color=TINTA_SUAVE)

    def quadro(self, t):
        self.cursor.set_xdata([t, t])
        self.texto_t.set_text(f"t = {t:6.2f} s")
        self.atualiza(t)
        self.fig.canvas.draw()
        return np.asarray(self.fig.canvas.buffer_rgba())[:, :, :3].copy()

    def gravar(self, caminho, fps=FPS):
        from tools.movimento_ref import comparar
        n = int((self.t1 - self.t0) * fps)
        arquivo, total = comparar.escrever_mp4((self.quadro(self.t0 + k / fps) for k in range(n)), caminho, fps=fps)
        plt.close(self.fig)
        return arquivo


def _interp(t, ts, ys):
    return float(np.interp(t, ts, ys))


# --------------------------------------------------------------------------
# Porta (vista de cima)
# --------------------------------------------------------------------------
def _sessao_porta(fps=240.0, total=9.5):
    from sem_alvorada.engine import doors as door_module
    jogo = grava.JogoMinimo(False, 2.6)
    jogo.rng = grava.Sempre()
    gerente = door_module.DoorManager(jogo, None)
    porta = gerente.get("kids_master")
    n = int(total * fps)
    dt = 1.0 / fps
    t = np.arange(n) * dt
    theta, turn = np.zeros(n), np.zeros(n)
    for k in range(n):
        agora = k * dt
        if abs(agora - 0.2) < dt / 2:
            gerente.toggle("kids_master")
        if abs(agora - 3.2) < dt / 2:
            gerente.toggle("kids_master")
        if abs(agora - 6.2) < dt / 2:
            gerente.snap("kids_master", 1.0)
        if abs(agora - 6.25) < dt / 2:
            gerente.toggle("kids_master", hurried=True)
        gerente.update(dt, None)
        jogo.clock += dt
        theta[k], turn[k] = porta.openness * P.ABERTURA, porta.turn
    return t, theta, turn


def _modelo_porta(t, duracao_abre=1.1, duracao_fecha=1.1):
    """Ângulo do modelo na mesma sequência: abrir (0,34 s de maçaneta + trajetória de mínima variação de torque), fechar, bater."""
    tm, th, *_ = P.trajetoria_minima_variacao_de_torque(duracao_abre, 25.0)
    sim, t_sim, w, tip = P.golpe_de_porta()
    saida = np.zeros_like(t)
    for k, x in enumerate(t):
        if x < 3.2:
            saida[k] = float(np.interp(x - 0.2 - 0.14, tm, th, left=0.0, right=P.ABERTURA))
        elif x < 6.2:
            saida[k] = float(np.interp(x - 3.2, tm, P.ABERTURA - th, left=P.ABERTURA, right=0.0))
        elif x < 6.25:
            saida[k] = P.ABERTURA
        else:
            tau = x - 6.25
            saida[k] = float(np.interp(tau, sim["t"], sim["theta"])) if tau <= t_sim else 0.0
    return saida


def cena_porta():
    t, theta_jogo, turn = _sessao_porta()
    theta_modelo = _modelo_porta(t)
    serie = {"m": (t, np.degrees(theta_modelo), COR_MODELO, "-", "modelo físico"),
             "j": (t, np.degrees(theta_jogo), COR_JOGO, "-", "jogo (depois)")}
    cena = Cena("Porta (25 kg, 0,88 m): abrir, fechar com trinco e bater", 0.0, 9.5, serie, "ângulo da folha (graus)")
    desenhos = []
    for ax, theta, jogo in ((cena.ax_m, theta_modelo, False), (cena.ax_j, theta_jogo, True)):
        ax.set_xlim(-0.55, 1.35)
        ax.set_ylim(-0.3, 1.3)
        ax.set_aspect("equal")
        ax.axhline(0, xmin=0, xmax=0.28, color=TINTA_SUAVE, lw=7)
        ax.plot([0.92, 1.4], [0, 0], color=TINTA_SUAVE, lw=7, solid_capstyle="butt")
        ax.plot([-0.55, 0.0], [0, 0], color=TINTA_SUAVE, lw=7, solid_capstyle="butt")
        ax.plot([0.0], [0.0], "o", color=TINTA, ms=7)
        folha, = ax.plot([], [], color=COR_JOGO if jogo else COR_MODELO, lw=6, solid_capstyle="butt")
        maca, = ax.plot([], [], "o", color=TINTA, ms=7)
        arco, = ax.plot([], [], color=GRADE, lw=1.5)
        texto = ax.text(-0.5, 1.2, "", fontsize=11)
        ax.axis("off")
        desenhos.append((ax, theta, folha, maca, arco, texto, jogo))

    def atualiza(tempo):
        for ax, theta, folha, maca, arco, texto, jogo in desenhos:
            a = _interp(tempo, t, theta)
            folha.set_data([0, 0.88 * math.cos(a)], [0, 0.88 * math.sin(a)])
            maca.set_data([0.81 * math.cos(a)], [0.81 * math.sin(a)])
            ang = np.linspace(0, a, 30)
            arco.set_data(0.35 * np.cos(ang), 0.35 * np.sin(ang))
            extra = f"   maçaneta {_interp(tempo, t, turn):.0%}" if jogo else ""
            texto.set_text(f"{math.degrees(a):5.1f} graus{extra}")
    cena.atualiza = atualiza
    return cena


# --------------------------------------------------------------------------
# Relógio (frente)
# --------------------------------------------------------------------------
def cena_relogio():
    g = grava.relogio(duracao=14.0, fps=240.0)
    t = g["t"]
    ref_t, ref_theta, ref_tiques = R.simular(14.0, R.comprimento_equivalente(R.comprimento_para_periodo(2.0)), fps=240.0)
    ref_mao = np.radians(R.posicao_do_segundeiro(ref_tiques, ref_t))
    serie = {"m": (ref_t, np.degrees(ref_theta), COR_MODELO, "-", "modelo físico"), "j": (t, np.degrees(g["theta"]), COR_JOGO, "-", "jogo")}
    cena = Cena("Relógio de pé: pêndulo de segundos (T = 2 s) e ponteiro dos segundos", 0.0, 14.0, serie, "pêndulo (graus)")
    L = 1.024
    desenhos = []
    for ax, tt, theta, tiques, mao, cor in ((cena.ax_m, ref_t, ref_theta, ref_tiques, ref_mao, COR_MODELO),
                                            (cena.ax_j, t, g["theta"], g["tiques"], g["mao"], COR_JOGO)):
        ax.set_xlim(-0.26, 0.26)
        ax.set_ylim(0.28, 1.62)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.plot([-0.185, -0.185], [0.33, 1.31], color=TINTA_SUAVE, lw=3)
        ax.plot([0.185, 0.185], [0.33, 1.31], color=TINTA_SUAVE, lw=3)
        ax.plot([0, 0], [1.44, 1.44], "o", color=TINTA, ms=5)
        haste, = ax.plot([], [], color=TINTA, lw=2)
        lentilha, = ax.plot([], [], "o", color=cor, ms=24)
        clarao = ax.text(0.0, 1.5, "", ha="center", fontsize=13, fontweight="bold", color=TINTA)
        ax.text(-0.25, 0.30, "escala horizontal ampliada: o arco real é de +-4,5 cm", fontsize=8, color=TINTA_SUAVE)
        dial = ax.inset_axes([0.60, 0.60, 0.38, 0.38])
        dial.set_aspect("equal")
        dial.set_xlim(-1.15, 1.15)
        dial.set_ylim(-1.15, 1.15)
        dial.axis("off")
        c = np.linspace(0, 2 * np.pi, 100)
        dial.plot(np.cos(c), np.sin(c), color=TINTA_SUAVE, lw=1.5)
        for h in range(12):
            a = h * math.pi / 6
            dial.plot([0.9 * math.sin(a), math.sin(a)], [0.9 * math.cos(a), math.cos(a)], color=TINTA_SUAVE, lw=1)
        for comprimento, graus, largura in ((0.5, 6.2 * 30, 3), (0.8, 72, 2)):         # horas e minutos parados às 6:12
            a = math.radians(graus)
            dial.plot([0, comprimento * math.sin(a)], [0, comprimento * math.cos(a)], color=TINTA, lw=largura)
        segundos, = dial.plot([], [], color=cor, lw=1.5)
        desenhos.append((tt, theta, tiques, mao, haste, lentilha, clarao, segundos))

    def atualiza(tempo):
        for tt, theta, tiques, mao, haste, lentilha, clarao, segundos in desenhos:
            a = _interp(tempo, tt, theta)
            x, z = L * math.sin(a), 1.44 - L * math.cos(a)
            haste.set_data([0, x], [1.44, z])
            lentilha.set_data([x], [z])
            recente = tiques[(tiques <= tempo) & (tiques > tempo - 0.12)]
            clarao.set_text("TIQUE" if recente.size else "")
            m = _interp(tempo, tt, mao)
            segundos.set_data([-0.2 * math.sin(m), 0.95 * math.sin(m)], [-0.2 * math.cos(m), 0.95 * math.cos(m)])
    cena.atualiza = atualiza
    return cena


# --------------------------------------------------------------------------
# Carro e coelhinho (de lado)
# --------------------------------------------------------------------------
def cena_carro(vertical=15.0):
    s = grava.carro()
    ref = CC.referencia_do_carro(s)
    t = s["t"]
    fps = s["fps"]
    v_ref = -np.gradient(ref["y"], 1 / fps)
    spin_ref = -np.cumsum(v_ref) / fps / KC.RAIO_RODA                  # w = v / R, o sentido de rolar para a frente
    spin_jogo = s["roda"][:, 0, 0]
    pitch_jogo, z_jogo = s["euler"][:, 0], s["pos"][:, 2]
    s0 = medidas.carregar_gravacao("carro")
    serie = {"a": (s0["t"], np.degrees(s0["euler"][:, 0]), COR_ANTES, (0, (4, 2)), "jogo antes"),
             "m": (t, np.degrees(ref["theta"]), COR_MODELO, "-", "modelo físico (meio carro)"),
             "j": (t, np.degrees(pitch_jogo), COR_JOGO, "-", "jogo (depois)")}
    cena = Cena(f"Carro saindo da garagem: arfagem, rolagem das rodas e o chão (desvios verticais ampliados {vertical:.0f}x)", 7.5, 17.5,
                serie, "arfagem (graus, nariz para cima +)")
    desenhos = []
    for ax, pitch, zo, spin, cor in ((cena.ax_m, ref["theta"], ref["z_origem"], spin_ref, COR_MODELO),
                                     (cena.ax_j, pitch_jogo, z_jogo, spin_jogo, COR_JOGO)):
        ax.set_xlim(-6.8, 5.6)
        ax.set_ylim(-0.35, 2.3)
        ax.set_aspect("equal")
        ys = np.linspace(-6.8, 5.6, 300)
        solo = vertical * np.array([float(KC.altura_do_chao(y)) for y in ys])
        ax.plot(ys, solo, color=TINTA_SUAVE, lw=2)
        ax.fill_between(ys, solo, -0.35, color=GRADE, alpha=0.5, lw=0)
        ax.plot([0, 0], [2.2 * 0 + 0.0, 2.3], color=TINTA_SUAVE, lw=0.8, ls=":")
        ax.text(0.05, 2.15, "portão", fontsize=8, color=TINTA_SUAVE)
        corpo, = ax.plot([], [], color=cor, lw=2.5)
        rodas = [ax.plot([], [], color=TINTA, lw=2)[0] for _ in range(2)]
        raios = [ax.plot([], [], color=TINTA, lw=1.5)[0] for _ in range(2)]
        info = ax.text(-6.6, 2.05, "", fontsize=10)
        ax.axis("off")
        desenhos.append((ax, pitch, zo, spin, corpo, rodas, raios, info))
    y_pos = s["pos"][:, 1]

    def atualiza(tempo):
        for ax, pitch, zo, spin, corpo, rodas, raios, info in desenhos:
            y = _interp(tempo, t, y_pos)
            th = _interp(tempo, t, pitch)
            z = vertical * (_interp(tempo, t, zo))
            # corpo no plano (y para a esquerda é a frente: o carro anda para -Y); desenhado com a frente à ESQUERDA
            alt = 1.35
            c, sn = math.cos(vertical * th), math.sin(vertical * th)
            pontos = [(-2.42, 0.45), (-2.42, 0.85), (-1.4, 0.95), (-0.9, alt), (1.2, alt), (1.7, 0.95), (2.42, 0.85), (2.42, 0.45), (-2.42, 0.45)]
            xs = [y + (-p[0] * c) + p[1] * (-sn) * 0 for p in pontos]
            xs = [y + (-(p[0]) * c - (p[1] - 0.5) * sn) for p in pontos]
            zs = [z + (-(p[0]) * sn + (p[1] - 0.5) * c) + 0.5 - 0.5 for p in pontos]
            corpo.set_data(xs, zs)
            for k, (lx, rot) in enumerate(((-1.45, 0), (1.45, 1))):
                cx = y + (-lx * c)
                cz = z + (-lx * sn) + KC.RAIO_RODA - 0.0
                ang = np.linspace(0, 2 * np.pi, 40)
                rodas[k].set_data(cx + KC.RAIO_RODA * np.cos(ang), cz + KC.RAIO_RODA * np.sin(ang))
                a = _interp(tempo, t, spin)
                raios[k].set_data([cx, cx + KC.RAIO_RODA * math.cos(a)], [cz, cz + KC.RAIO_RODA * math.sin(a)])
            info.set_text(f"v = {abs(_interp(tempo, t, s['sinais']['speed'])):.2f} m/s   arfagem {math.degrees(th):+.2f} graus")
    cena.atualiza = atualiza
    return cena


def cena_charm():
    s = grava.carro()
    ref = CC.referencia_do_carro(s)
    t = s["t"]
    lb = CC.comprimento_equivalente("Cut_Bunny")
    ref_b = KC.simular_pendulo(t, lb, 0.04, lambda x: float(np.interp(x, t, ref["a_frente"])))
    jogo_b = s["coelho"][:, 0] + s["euler"][:, 0]
    s0 = medidas.carregar_gravacao("carro")
    antes_b = s0["coelho"][:, 0] + 0.35 * s0["euler"][:, 0]
    serie = {"a": (s0["t"], np.degrees(antes_b), COR_ANTES, (0, (4, 2)), "jogo antes"),
             "m": (t, np.degrees(ref_b), COR_MODELO, "-", "modelo (pêndulo composto forçado)"),
             "j": (t, np.degrees(jogo_b), COR_JOGO, "-", "jogo (depois)")}
    cena = Cena(f"Coelhinho do retrovisor: l_eq = {lb:.3f} m (da malha), T = {2 * math.pi * math.sqrt(lb / 9.81):.2f} s; frente do carro à esquerda",
                6.0, 18.0, serie, "ângulo contra a vertical (graus)")
    desenhos = []
    for ax, ang, cor in ((cena.ax_m, ref_b, COR_MODELO), (cena.ax_j, jogo_b, COR_JOGO)):
        ax.set_xlim(-0.55, 0.55)
        ax.set_ylim(-0.32, 0.12)
        ax.set_aspect("equal")
        ax.axvline(0, color=GRADE, lw=1, ls="--")
        ax.plot([-0.5, 0.5], [0.1, 0.1], color=TINTA_SUAVE, lw=5)
        ax.text(-0.52, 0.12, "frente", fontsize=9, color=TINTA_SUAVE)
        ax.plot([0], [0.1], "o", color=TINTA, ms=6)
        fio, = ax.plot([], [], color=TINTA, lw=1.5)
        bicho, = ax.plot([], [], "o", color=cor, ms=34)
        seta = ax.annotate("", xy=(0, 0), xytext=(0, 0), arrowprops={"arrowstyle": "->", "lw": 2, "color": TINTA_SUAVE})
        info = ax.text(-0.52, -0.3, "", fontsize=10)
        ax.axis("off")
        desenhos.append((ang, fio, bicho, seta, info))

    def atualiza(tempo):
        a_frente = _interp(tempo, t, ref["a_frente"])
        for ang, fio, bicho, seta, info in desenhos:
            a = _interp(tempo, t, ang)
            # ângulo positivo = para a frente do carro = para a esquerda da imagem
            x, z = -lb * math.sin(a), 0.1 - lb * math.cos(a)
            fio.set_data([0, x], [0.1, z])
            bicho.set_data([x], [z])
            seta.set_position((0.38, -0.2))
            seta.xy = (0.38 - 0.06 * a_frente, -0.2)
            info.set_text(f"aceleração para a frente {a_frente:+.2f} m/s2   ângulo {math.degrees(a):+.1f} graus")
    cena.atualiza = atualiza
    return cena


def cena_portao():
    s = grava.carro()
    p = grava.portao()
    p0 = medidas.carregar_gravacao("portao")
    t = p["t"]
    t0, T, rampa = p["inicio"], p["duracao"], 1.0
    v = 2.3 / (T - rampa)

    def vel(tau):
        if tau <= 0 or tau >= T:
            return 0.0
        u = min(tau, T - tau, rampa) / rampa
        return v * (3 * u * u - 2 * u ** 3) if min(tau, T - tau) < rampa else v
    ideal = np.cumsum([vel(x - t0) for x in t]) / p["fps"]
    serie = {"a": (p0["t"], p0["z"], COR_ANTES, (0, (4, 2)), "jogo antes (3 s)"), "m": (t, ideal, COR_MODELO, "-", "modelo: abridor de 19 cm/s"),
             "j": (t, p["z"], COR_JOGO, "-", "jogo (depois)")}
    cena = Cena("Portão da garagem e o carro que passa sob ele: altura da folha (m)", 0.0, 14.0, serie, "altura da folha (m)")
    desenhos = []
    for ax, z, cor in ((cena.ax_m, ideal, COR_MODELO), (cena.ax_j, p["z"], COR_JOGO)):
        ax.set_xlim(-5.0, 5.8)
        ax.set_ylim(-0.1, 3.2)
        ax.set_aspect("equal")
        ax.plot([-5, 5.8], [0, 0], color=TINTA_SUAVE, lw=2)
        ax.plot([-0.2, 0.2], [2.3, 2.3], color=TINTA_SUAVE, lw=6)
        folha, = ax.plot([], [], color=cor, lw=7, solid_capstyle="butt")
        carro, = ax.plot([], [], color=TINTA, lw=2)
        info = ax.text(-4.8, 3.0, "", fontsize=10)
        ax.axis("off")
        desenhos.append((z, folha, carro, info))

    def atualiza(tempo):
        for z, folha, carro, info in desenhos:
            h = _interp(tempo, t, z)
            folha.set_data([0, 0], [h, h + 2.19])
            y = _interp(tempo, s["t"], s["pos"][:, 1])
            xs = [y - 2.42, y - 2.42, y - 1.4, y - 0.9, y + 1.2, y + 1.7, y + 2.42, y + 2.42, y - 2.42]
            zs = [0.12, 0.85, 0.95, 1.4, 1.4, 0.95, 0.85, 0.12, 0.12]
            carro.set_data([-x for x in xs], zs)
            info.set_text(f"folha a {h:.2f} m   folga sobre o teto {h - 1.40:+.2f} m   (carro em y = {y:+.1f} m)")
    cena.atualiza = atualiza
    return cena


def cena_cortina():
    c = grava.cortina(duracao=40.0, gust=None)
    H = c["altura"]
    fr = c["fracoes"]
    tm, ym = KT.simular_alturas(H, fr, 40.0, 60.0)
    desloc = c["deslocamento"][:, 0, :, 1]
    desloc = desloc - desloc.mean(axis=0)
    ym = ym * np.std(desloc[:, -1])                    # o modelo vem normalizado: leva ao mesmo RMS da bainha do jogo
    serie = {"m": (tm, ym[:, -1] * 100, COR_MODELO, "-", "modelo (3 modos + vento de von Karman)"),
             "j": (c["t"], desloc[:, -1] * 100, COR_JOGO, "-", "jogo (depois)")}
    cena = Cena(f"Cortina de {H:.2f} m ao vento: oscilação da bainha (modos em 0,40 / 0,92 / 1,44 Hz)", 0.0, 40.0, serie, "bainha (cm)")
    ampl = 8.0
    desenhos = []
    for ax, tt, y, cor in ((cena.ax_m, tm, ym, COR_MODELO), (cena.ax_j, c["t"], desloc, COR_JOGO)):
        ax.set_xlim(-0.6, 0.6)
        ax.set_ylim(-0.1, 1.05)
        ax.plot([-0.5, 0.5], [1.0, 1.0], color=TINTA_SUAVE, lw=6)
        pano, = ax.plot([], [], color=cor, lw=3)
        ax.plot([0, 0], [0, 1.0], color=GRADE, lw=1, ls="--")
        ax.text(-0.58, -0.07, f"deslocamento horizontal ampliado {ampl:.0f}x; barra no alto, bainha embaixo", fontsize=8, color=TINTA_SUAVE)
        ax.set_xticks([])
        ax.set_yticks([])
        desenhos.append((tt, y, pano))

    def atualiza(tempo):
        for tt, y, pano in desenhos:
            xs = [ampl * float(np.interp(tempo, tt, y[:, i])) for i in range(len(fr))]
            alturas = [1.0 - f for f in fr]
            pano.set_data([0.0] + xs, [1.0] + alturas)
    cena.atualiza = atualiza
    return cena


CENAS = {"porta": cena_porta, "relogio": cena_relogio, "carro": cena_carro, "charm": cena_charm, "portao": cena_portao,
         "cortina": cena_cortina}
ARQUIVOS = {"porta": "esquema_porta.mp4", "relogio": "esquema_pendulo_relogio.mp4", "carro": "esquema_carro.mp4", "charm": "esquema_chaveiro.mp4",
            "portao": "esquema_portao.mp4",
            "cortina": "esquema_cortina.mp4"}


def gerar(nome, pasta=None):
    pasta = pasta or medidas.FINAL
    os.makedirs(pasta, exist_ok=True)
    cena = CENAS[nome]()
    return cena.gravar(os.path.join(pasta, ARQUIVOS[nome]))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv) or list(CENAS)
    for nome in argv:
        print(gerar(nome))


if __name__ == "__main__":
    main()
