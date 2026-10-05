"""Figuras padronizadas de matplotlib para comparar movimento real com o jogo.

    from tools.movimento_ref import graficos
    graficos.painel_curvas(reais, jogo, "out/x/curvas.png", titulo="Andar: 07_01 x jogo")
    graficos.painel_tabela(linhas, "out/x/tabela.png", titulo=...)
    graficos.diagrama_apoios(mov_real, mov_jogo, "out/x/apoios.png")
    graficos.painel_alcance(perfil_real, perfil_jogo, "out/x/alcance.png")

Padrão visual (o mesmo em todas): real em azul, com faixa de +-1 desvio entre os ciclos observados; jogo em laranja
(também com faixa quando há mais de um ciclo); eixo x em % do ciclo (de um toque do calcanhar ao seguinte do mesmo pé) ou
em segundos normalizados; a legenda sempre aparece, e o texto nunca usa a cor das séries. As cores são as duas primeiras
do conjunto categórico validado para daltonismo (azul #2a78d6 e laranja #eb6834).
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .metricas import CICLO_PONTOS, Curva, tabela_texto  # noqa: E402,F401

COR_REAL = "#2a78d6"
COR_JOGO = "#eb6834"
TINTA = "#0b0b0b"
TINTA_SUAVE = "#52514e"
FUNDO = "#fcfcfb"
GRADE = "#e4e3de"
CICLO_X = np.linspace(0, 100, CICLO_PONTOS)

ROTULOS_CURVAS = {
    "quadril": ("Quadril (flexão +)", "graus"), "joelho": ("Joelho (flexão)", "graus"),
    "tornozelo": ("Tornozelo (dorsiflexão +)", "graus"), "pelve_rot": ("Rotação da pelve", "graus"),
    "torax_rot": ("Rotação do tórax", "graus"), "tronco_incl": ("Inclinação do tronco (frente +)", "graus"),
    "ombro": ("Ombro (braço à frente +)", "graus"), "cotovelo": ("Cotovelo (flexão)", "graus"),
    "cabeca_z": ("Cabeça, vertical", "m"), "quadril_z": ("Quadril, vertical", "m"),
    "cabeca_x": ("Cabeça, lateral", "m"),
}
ORDEM_CURVAS = ("quadril", "joelho", "tornozelo", "pelve_rot", "torax_rot", "tronco_incl",
                "ombro", "cotovelo", "cabeca_z", "quadril_z", "cabeca_x")


def _estilo():
    plt.rcParams.update({
        "figure.facecolor": FUNDO, "axes.facecolor": FUNDO, "savefig.facecolor": FUNDO,
        "axes.edgecolor": GRADE, "axes.labelcolor": TINTA_SUAVE, "axes.titlecolor": TINTA,
        "axes.titlesize": 10, "axes.labelsize": 8.5, "xtick.color": TINTA_SUAVE, "ytick.color": TINTA_SUAVE,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "text.color": TINTA, "axes.grid": True, "grid.color": GRADE,
        "grid.linewidth": 0.7, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
        "legend.fontsize": 9, "font.size": 9, "lines.solid_capstyle": "round",
    })


def _lista(valor):
    if valor is None:
        return []
    return list(valor) if isinstance(valor, (list, tuple)) else [valor]


def curva_de(marchas, chave):
    """Junta a curva `chave` de uma ou várias `Marcha` (varias pessoas/clipes reais viram uma só faixa)."""
    curvas = [m.curvas[chave] for m in _lista(marchas) if chave in m.curvas]
    return Curva.juntar(curvas) if curvas else None


def _desenhar(ax, curva, cor, rotulo, faixa=True, escala=1.0):
    if curva is None or not curva.n:
        return
    media, desvio = curva.media * escala, curva.desvio * escala
    if faixa and curva.n > 1:
        ax.fill_between(CICLO_X, media - desvio, media + desvio, color=cor, alpha=0.20, linewidth=0)
    ax.plot(CICLO_X, media, color=cor, linewidth=2.0, label=f"{rotulo} (n={curva.n})")


def _eixos_ciclo(ax, unidade):
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_ylabel(unidade)


def _salvar(figura, caminho):
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    figura.savefig(caminho, dpi=130)
    plt.close(figura)
    return caminho


def curva_unica(real, jogo, chave, caminho, titulo=None, rotulo_real="real", rotulo_jogo="jogo"):
    """Uma grandeza ao longo do ciclo, real contra jogo."""
    _estilo()
    figura, ax = plt.subplots(figsize=(5.6, 3.4))
    nome, unidade = ROTULOS_CURVAS.get(chave, (chave, ""))
    escala = 100.0 if unidade == "m" else 1.0
    _desenhar(ax, curva_de(real, chave), COR_REAL, rotulo_real, escala=escala)
    _desenhar(ax, curva_de(jogo, chave), COR_JOGO, rotulo_jogo, escala=escala)
    ax.set_title(titulo or nome, loc="left")
    ax.set_xlabel("% do ciclo (toque do calcanhar a toque do calcanhar)")
    _eixos_ciclo(ax, "cm" if unidade == "m" else unidade)
    ax.legend(loc="best")
    figura.tight_layout()
    return _salvar(figura, caminho)


def painel_curvas(real, jogo, caminho, titulo="", chaves=None, rotulo_real="real (CMU)", rotulo_jogo="jogo", colunas=4):
    """Grade de curvas por % do ciclo. `real` e `jogo` são `Marcha` ou listas delas."""
    _estilo()
    chaves = [c for c in (chaves or ORDEM_CURVAS) if curva_de(real, c) is not None or curva_de(jogo, c) is not None]
    linhas = int(np.ceil(len(chaves) / colunas))
    figura, eixos = plt.subplots(linhas, colunas, figsize=(3.3 * colunas, 2.45 * linhas + 0.8), squeeze=False)
    for ax in eixos.flat:
        ax.set_visible(False)
    for ax, chave in zip(eixos.flat, chaves):
        ax.set_visible(True)
        nome, unidade = ROTULOS_CURVAS.get(chave, (chave, ""))
        escala = 100.0 if unidade == "m" else 1.0
        _desenhar(ax, curva_de(real, chave), COR_REAL, rotulo_real, escala=escala)
        _desenhar(ax, curva_de(jogo, chave), COR_JOGO, rotulo_jogo, escala=escala)
        ax.set_title(nome, loc="left", fontsize=9.5)
        _eixos_ciclo(ax, "cm" if unidade == "m" else unidade)
        ax.set_xlabel("% do ciclo", fontsize=8)
    pegadas = [plt.Line2D([0], [0], color=COR_REAL, linewidth=2.2), plt.Line2D([0], [0], color=COR_JOGO, linewidth=2.2)]
    ns = [(curva_de(real, chaves[0]), curva_de(jogo, chaves[0]))] if chaves else [(None, None)]
    nr = ns[0][0].n if ns[0][0] is not None else 0
    nj = ns[0][1].n if ns[0][1] is not None else 0
    figura.legend(pegadas, [f"{rotulo_real} (média +-1 desvio, {nr} ciclos)", f"{rotulo_jogo} ({nj} ciclos)"],
                  loc="upper right", ncol=2, bbox_to_anchor=(0.99, 0.995))
    figura.suptitle(titulo, x=0.01, ha="left", fontsize=12, fontweight="bold", y=0.995)
    figura.tight_layout(rect=(0, 0, 1, 0.95))
    return _salvar(figura, caminho)


def painel_tabela(linhas, caminho, titulo="", rotulo_real="real", rotulo_jogo="jogo"):
    """A tabela de `comparar_metricas` como figura. Estado em palavras ("dentro"/"fora"), nunca só em cor."""
    _estilo()
    n = len(linhas)
    figura, ax = plt.subplots(figsize=(10.5, 0.34 * n + 1.3))
    ax.axis("off")
    com_desvio = any(np.isfinite(linha.desvio_real) for linha in linhas)
    cabecalho = ["métrica", "unidade", rotulo_real] + (["+-1 desvio"] if com_desvio else []) + [rotulo_jogo, "dif.", "tolerância", "estado"]
    celulas, cores = [], []
    for linha in linhas:
        def fmt(x):
            return "--" if not np.isfinite(x) else f"{x:.{linha.casas}f}"
        estado = "sem dado" if linha.ok is None else ("dentro" if linha.ok else "fora")
        celulas.append([linha.rotulo, linha.unidade, fmt(linha.real)] + ([fmt(linha.desvio_real)] if com_desvio else [])
                       + [fmt(linha.jogo), ("" if not np.isfinite(linha.diferenca) or linha.diferenca < 0 else "+") + fmt(linha.diferenca),
                          "+-" + fmt(linha.tolerancia), estado])
        cores.append("#f6d9d3" if linha.ok is False else FUNDO)
    tabela = ax.table(cellText=celulas, colLabels=cabecalho, loc="upper left", cellLoc="right",
                      colWidths=[0.36, 0.09, 0.09] + ([0.09] if com_desvio else []) + [0.09, 0.09, 0.11, 0.09])
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(8.6)
    tabela.scale(1.0, 1.35)
    for (linha, coluna), celula in tabela.get_celld().items():
        celula.set_edgecolor(GRADE)
        celula.set_linewidth(0.6)
        if coluna == 0:
            celula._loc = "left"
            celula.get_text().set_ha("left")
        if linha == 0:
            celula.set_facecolor("#ecebe6")
            celula.get_text().set_fontweight("bold")
        else:
            celula.set_facecolor(cores[linha - 1])
            if coluna == len(cabecalho) - 1 and celulas[linha - 1][-1] == "fora":
                celula.get_text().set_fontweight("bold")
    ax.set_title(titulo, loc="left", fontsize=11.5, fontweight="bold")
    figura.tight_layout()
    return _salvar(figura, caminho)


def diagrama_apoios(mov_real, mov_jogo, caminho, titulo="Apoios dos pés", janela=None, metodo="auto"):
    """Quando cada pé toca o chão, real em cima, jogo embaixo. Barras = pé em contato (veja `metricas.eventos_marcha`)."""
    from . import metricas
    _estilo()
    figura, eixos = plt.subplots(2, 1, figsize=(9.0, 3.6), sharex=False)
    for ax, mov, cor, nome in ((eixos[0], mov_real, COR_REAL, "real"), (eixos[1], mov_jogo, COR_JOGO, "jogo")):
        eventos = metricas.eventos_marcha(mov, metodo)
        for fila, (lado, rotulo) in enumerate((("e", "pé esquerdo"), ("d", "pé direito"))):
            for a, b in metricas._corridas(eventos.contato[lado]):
                ax.barh(fila, (b - a) / mov.fps, left=a / mov.fps, height=0.62, color=cor, alpha=0.85 if lado == "e" else 0.55)
            for i in eventos.toque[lado]:
                ax.plot([i / mov.fps] * 2, [fila - 0.40, fila + 0.40], color=TINTA, linewidth=1.1)
        ax.set_yticks([0, 1], ["esquerdo", "direito"])
        ax.set_ylim(-0.6, 1.6)
        ax.set_ylabel(nome)
        ax.grid(axis="y", visible=False)
        if janela:
            ax.set_xlim(*janela)
    eixos[1].set_xlabel("segundos (traço preto = toque do calcanhar)")
    eixos[0].set_title(titulo, loc="left")
    figura.tight_layout()
    return _salvar(figura, caminho)


def painel_alcance(perfis, caminho, titulo="Perfil de velocidade da mão", modelo=None):
    """Perfis de velocidade de alcances sobre tempo normalizado. `perfis`: [(rótulo, velocidade_m_s [n], fps, cor)];
    `modelo`: opcional (distância, duração) para sobrepor o jerk mínimo."""
    from . import metricas
    _estilo()
    figura, ax = plt.subplots(figsize=(6.2, 3.8))
    for rotulo, velocidade, fps, cor in perfis:
        tau = (np.arange(len(velocidade)) + 0.5) / len(velocidade)
        ax.plot(tau * 100, velocidade, color=cor, linewidth=2.0, label=rotulo)
    if modelo is not None:
        dist, dur = modelo
        v = metricas.jerk_minimo(dist, dur, 200.0)
        ax.plot((np.arange(len(v)) + 0.5) / len(v) * 100, v, color=TINTA_SUAVE, linewidth=1.4, linestyle=(0, (4, 3)),
                label="jerk mínimo (modelo)")
    ax.set_xlabel("% da duração do alcance")
    ax.set_ylabel("m/s")
    ax.set_xlim(0, 100)
    ax.set_title(titulo, loc="left")
    ax.legend(loc="upper right")
    figura.tight_layout()
    return _salvar(figura, caminho)


def serie_temporal(series, caminho, titulo="", unidade="", eventos=None):
    """Várias séries no tempo. `series`: [(rótulo, t, y, cor)]. `eventos`: [(t, rótulo)] como traços verticais."""
    _estilo()
    figura, ax = plt.subplots(figsize=(8.0, 3.2))
    for rotulo, t, y, cor in series:
        ax.plot(t, y, color=cor, linewidth=1.8, label=rotulo)
    for t, rotulo in eventos or []:
        ax.axvline(t, color=TINTA_SUAVE, linewidth=0.8, alpha=0.6)
    ax.set_xlabel("segundos")
    ax.set_ylabel(unidade)
    ax.set_title(titulo, loc="left")
    ax.legend(loc="best")
    figura.tight_layout()
    return _salvar(figura, caminho)
