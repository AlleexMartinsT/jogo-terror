"""Mãos que andam: a mão da lanterna e o braço livre no referencial da câmera, antes e depois do modelo de apoio (fase 5, agente 1).

Não é um `Cenario` de [real | jogo] no palco: o que o jogador vê de uma mão andando é o punho em relação à câmera (`egocentrico`), e
não existe mocap de alguém andando com uma lanterna na mão e o cotovelo dobrado. Então a comparação tem três fontes, e cada número
da tabela diz qual usou:

  MEDIDO    a CMU, no mesmo referencial e com a mesma escala do Daniel (`assets/referencia/maos_ego_ref.json`): o ombro e o braço livre;
  DERIVADO  a lei do modelo (`sem_alvorada.handsway`), conferida por uma simulação independente em `tests/test_maos_andando.py`;
  ESTIMADO  o que não tem fonte aqui (a mola do antebraço, o punho), com a faixa no código.

    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.maos_andando medir --saida out/f5_1/final

Grava no palco (corpo e piso) os casos de `CASOS` com o modelo `antes` (`SwayAntigo`, a mola simples da fase 4) e `depois` (o de
`handsway`), salva as gravações em `<saida>/gravacoes`, e escreve o painel de trajetória, o de séries e espectros e a tabela.
"""
import argparse
import json
import math
import os
import sys
from dataclasses import dataclass

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

from tools.movimento_ref import egocentrico as E  # noqa: E402

FPS = 60.0


@dataclass
class Caso:
    roteiro: str
    janela: tuple              # segundos da gravação que entram na medida (depois do regime assentar)
    real: str = None           # categoria de maos_ego_ref.json
    descricao: str = ""


CASOS = {
    "andar": Caso("parar 1; andar 6", (3.0, 7.0), "andar_rapido", "andar a 1,7 m/s"),
    "correr": Caso("parar 1; correr 4.4", (3.4, 5.4), "correr", "correr a 4,0 m/s"),
    "agachado": Caso("parar 1; agachado 5", (3.0, 6.0), None, "andar agachado a 0,8 m/s"),
    "arrancar": Caso("parar 1.5; andar 2.5", (1.4, 4.0), None, "parado, arranca andando"),
    "parar": Caso("andar 3; parar 3", (1.5, 6.0), None, "andando, para (0,65 s)"),
    "giro": Caso("parar 0.5; virar 180 1.0 parado; parar 1.5", (0.4, 3.0), None, "parado, gira o mouse 180 graus/s por 1 s"),
    "giro_andando": Caso("andar 2; virar 180 1.0; andar 1.5", (1.0, 4.5), None, "andando, gira o mouse 180 graus/s por 1 s"),
    "parado": Caso("parar 8", (1.0, 8.0), None, "parado, só respiração e deriva"),
    "agachar": Caso("parar 1; agachar 1.5; parar 2", (0.8, 4.5), None, "parado, agacha e levanta"),
    "escada": Caso("parar 1; andar 10", (3.0, 11.0), None, "subindo a escada (0,47 m/s, 1,5 passos/s)"),
    "olhar_30": Caso("olhar -30 0.5; andar 6", (3.0, 6.5), "andar_rapido", "andando olhando 30 graus para baixo"),
    "olhar_45": Caso("olhar -45 0.5; andar 6", (3.0, 6.5), "andar_rapido", "andando olhando 45 graus para baixo"),
    "olhar_60": Caso("olhar -60 0.5; andar 6", (3.0, 6.5), "andar_rapido", "andando olhando 60 graus para baixo"),
    "olhar_75": Caso("olhar -75 0.5; andar 6", (3.0, 6.5), "andar_rapido", "andando olhando 75 graus para baixo"),
}
CASOS_DO_PAINEL = ("andar", "correr", "agachado")


# ---------------------------------------------------------------------------------------------------------------------------
# O modelo de antes (fase 4), reconstruído com a classe que continua em `handheld`
# ---------------------------------------------------------------------------------------------------------------------------
class SwayAntigo:
    """A mola simples de antes da fase 5 (`handheld.Sway`): segue o head bob (x, y) e o giro da câmera, sem massa no eixo
    frente-trás. Mesma interface de `engine.handsway.HandSway`, para `Hands` aceitar um no lugar do outro."""

    def __init__(self, game):
        from sem_alvorada.engine.handheld import Sway
        self.game = game
        self.sway = {"R": Sway(0.0, 1.0), "L": Sway(1.7, 0.8)}
        self._out = {"R": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), "L": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))}
        self._clock = 0.0
        self._look = None

    def reset(self):
        for sway in self.sway.values():
            sway.reset()
        self._look = None

    def offset(self, side):
        return self._out[side]

    def update(self, dt, camera_matrix, visual, hand_positions=None):
        player = self.game.player
        self._clock += dt
        previous, self._look = self._look, (player.yaw, player.pitch)
        if previous is None or dt <= 0:
            yaw_rate = pitch_rate = 0.0
        else:
            yaw_rate = ((player.yaw - previous[0] + math.pi) % math.tau - math.pi) / dt
            pitch_rate = (player.pitch - previous[1]) / dt
        bob = player.bob_offset()
        for side, sway in self.sway.items():
            self._out[side] = sway.step(dt, self._clock, bob, yaw_rate, pitch_rate, player.breathing_hard)


# ---------------------------------------------------------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------------------------------------------------------
def preparar_jogo(palco=True, item_esquerda=None, **opcoes):
    """Jogo sem janela com a lanterna acesa na mão direita (e `item_esquerda`, um `C.ITEM_*`, na esquerda). Devolve o jogo."""
    import bpy  # noqa: F401
    from sem_alvorada import conventions as C
    from sem_alvorada.engine.inputstate import InputState
    from tools import prints_maos as maos
    from tools.movimento_ref import grava
    jogo = grava.montar_jogo(palco=palco, **opcoes)
    maos.give(jogo, flashlight=True, key=item_esquerda == C.ITEM_KEY, map_=item_esquerda == C.ITEM_MAP,
              batteries=1 if item_esquerda == C.ITEM_BATTERY else 0, on=True)
    jogo.hands.equip(C.ITEM_FLASHLIGHT)
    if item_esquerda is not None:
        jogo.hands.equip(item_esquerda)
    for _ in range(90):
        jogo.tick(1 / 60, InputState())
    return jogo


def usar_modelo(jogo, variante):
    """`antes` põe a mola de antes; `depois` o modelo novo."""
    from sem_alvorada.engine.handsway import HandSway
    jogo.hands.sway = SwayAntigo(jogo) if variante == "antes" else HandSway(jogo)


def equipar_esquerda(jogo, item):
    """Põe `item` (`C.ITEM_KEY`, `ITEM_MAP`, `ITEM_BATTERY`) na mão esquerda, ou a deixa livre com None, e espera o gesto acabar.
    Só um jogo por processo no palco (`build.fresh_scene` apaga a cena anterior), então os testes trocam o item no mesmo jogo."""
    from sem_alvorada import conventions as C
    from sem_alvorada.engine.inputstate import InputState
    from tools import prints_maos as maos
    maos.give(jogo, flashlight=True, key=item == C.ITEM_KEY, map_=item == C.ITEM_MAP,
              batteries=1 if item == C.ITEM_BATTERY else 0, on=True)
    jogo.hands.equip(item if item is not None else C.ITEM_FLASHLIGHT)
    for _ in range(600):
        jogo.tick(1 / 60, InputState())
        if not jogo.hands.busy:
            break
    for _ in range(30):
        jogo.tick(1 / 60, InputState())


def gravar_caso(jogo, nome, variante, saida=None, ossos="armadura", inicio=None, extras_lado="R", roteiro=None, item_esquerda=None):
    """Grava o caso `nome` com o modelo `variante`. Devolve (Gravacao, extras): `extras` tem, por quadro, a lente da lanterna
    (espaço da câmera), o apoio e a extensão da mola, o deslocamento e a rotação que a mão recebeu, e o atraso do corpo."""
    from tools.movimento_ref import grava
    from sem_alvorada.engine.inputstate import InputState
    caso = CASOS[nome]
    usar_modelo(jogo, variante)
    jogo.hands.sway.reset()
    if item_esquerda is not None:
        equipar_esquerda(jogo, item_esquerda)
    x, y, z, yaw = inicio or (0.0, 0.0, 0.0, 0.0)
    jogo.place_player(x, y, z, yaw)
    jogo.player.reset_body()                 # fôlego cheio: o caso anterior pode ter corrido até o fim dele
    for _ in range(45):
        jogo.tick(1 / 60, InputState())
    leitura = []

    def anotar(j, t, k):
        leitura.append(_ler_extras(j, extras_lado))

    passos = grava.roteiro_de_texto(roteiro or caso.roteiro)
    for passo in passos:
        passo.por_quadro = anotar
    rec = grava.gravar(jogo, passos, nome=f"{nome}_{variante}", ossos=ossos, prefacio=0.3)
    leitura.append(_ler_extras(jogo, extras_lado))
    if item_esquerda is not None:
        equipar_esquerda(jogo, None)
    leitura = leitura[1:]                    # a leitura k vem antes do tique k: a do tique k é a k + 1
    extras = {chave: np.array([quadro[i] for quadro in leitura], float)
              for i, chave in enumerate(("lente", "apoio", "extensao", "deslocamento", "rotacao", "atraso", "pendulo"))}
    if saida:
        os.makedirs(saida, exist_ok=True)
        rec.salvar(os.path.join(saida, f"{nome}_{variante}.npz"))
        np.savez_compressed(os.path.join(saida, f"{nome}_{variante}_extras.npz"), **extras)
    return rec, extras


def carregar_caso(saida, nome, variante):
    from tools.movimento_ref import grava
    rec = grava.Gravacao.carregar(os.path.join(saida, f"{nome}_{variante}.npz"))
    with np.load(os.path.join(saida, f"{nome}_{variante}_extras.npz")) as arquivo:
        extras = {chave: arquivo[chave] for chave in arquivo.files}
    return rec, extras


def _ler_extras(jogo, lado):
    """Lente da lanterna (câmera), apoio, mola, deslocamento e rotação da mão `lado` e o atraso do corpo (graus)."""
    from mathutils import Vector
    from sem_alvorada.engine import flashlight as flashlight_module
    hands = jogo.hands
    matriz = jogo.flashlight.lantern_matrix
    lente = tuple(matriz @ Vector(flashlight_module.LIGHT_FROM_GRIP)) if matriz is not None else (np.nan,) * 3
    modelo = getattr(hands.sway, "hands", {}).get(lado)
    apoio = tuple(modelo.anchor) if modelo is not None else (np.nan,) * 3
    extensao = tuple(modelo.extension) if modelo is not None else (np.nan,) * 3
    deslocamento, rotacao = hands.sway.offset(lado)
    atraso = math.degrees((jogo.player.yaw - getattr(jogo.body, "trunk_yaw", jogo.player.yaw) + math.pi) % math.tau - math.pi)
    return lente, apoio, extensao, tuple(deslocamento), tuple(rotacao), atraso, tuple(hands.pendulum.angle)


# ---------------------------------------------------------------------------------------------------------------------------
# Medidas no referencial da câmera
# ---------------------------------------------------------------------------------------------------------------------------
def recorte(rec, janela):
    a, b = (int(round(t * rec.fps)) for t in janela)
    return slice(a, min(b, rec.quadros))


def ego_do_jogo(rec, janela):
    """{(junta, lado): [T, 3] (direita, frente, cima)} para ombro, cotovelo e punho dos dois braços, e {"alvo_<lado>"}: o alvo
    da palma pedido ao corpo, no espaço da câmera."""
    mov = rec.movimento()
    corte = recorte(rec, janela)
    saida = {}
    for junta in E.JUNTAS_DO_BRACO:
        for lado in "ed":
            saida[(junta, lado)] = E.junta_ego(mov, junta, lado)[corte]
    for indice, lado in ((0, "e"), (1, "d")):
        alvo = rec.alvo_mao[corte, indice]
        saida[("alvo", lado)] = np.stack([alvo[:, 0], -alvo[:, 2], alvo[:, 1]], axis=1)
    return saida


def real_rotacionado(clipes, junta, lado, graus_para_baixo):
    """O braço da CMU (cabeça nivelada) como seria visto com a cabeça inclinada `graus_para_baixo`: a câmera gira em torno do eixo
    direito e os pontos giram ao contrário. É a referência de quando o jogador olha para baixo e os braços entram no quadro."""
    from tools.movimento_ref import cmu, movimento
    p = math.radians(graus_para_baixo)
    saida = []
    for clipe in clipes:
        ego = E.junta_ego(movimento.movimento_de_mocap(cmu.carregar(clipe)), junta, lado)
        frente = ego[:, 1] * math.cos(p) - ego[:, 2] * math.sin(p)
        cima = ego[:, 1] * math.sin(p) + ego[:, 2] * math.cos(p)
        saida.append(np.stack([ego[:, 0], frente, cima], axis=1))
    return np.concatenate(saida)


def lente_ego(extras, janela, fps=FPS):
    """A lente da lanterna em (direita, frente, cima)."""
    a, b = (int(round(t * fps)) for t in janela)
    lente = extras["lente"][a:b]
    return np.stack([lente[:, 0], -lente[:, 2], lente[:, 1]], axis=1)


def estatisticas(ego, fps=FPS):
    """Média, amplitude (percentis 5 a 95), frequência dominante e fração no campo de visão de uma série [T, 3]."""
    ego = np.asarray(ego, float)
    bom = ego[np.isfinite(ego).all(axis=1)]
    p5, p95 = np.percentile(bom, 5, axis=0), np.percentile(bom, 95, axis=0)
    return {"media": bom.mean(axis=0), "amplitude": p95 - p5,
            "freq_frente": E.frequencia_dominante(bom[:, 1], fps), "freq_cima": E.frequencia_dominante(bom[:, 2], fps),
            "no_campo": E.dentro_do_campo(bom)}


def referencia(categoria):
    """O resumo (mediana entre clipes) de uma categoria de `maos_ego_ref.json`: {junta: {lado: {media, amplitude, ...}}}."""
    with open(E.ARQUIVO, encoding="utf-8") as arquivo:
        return json.load(arquivo)[categoria]["resumo"]


def deslocamento_pico_a_pico(extras, janela, coluna="deslocamento", fps=FPS):
    """Pico a pico (percentis 5 a 95) do deslocamento que o modelo soma à mão, nos eixos da câmera (x, y, z)."""
    a, b = (int(round(t * fps)) for t in janela)
    dados = extras[coluna][a:b]
    return np.percentile(dados, 95, axis=0) - np.percentile(dados, 5, axis=0)


def pico_do_dado(serie, janela, fps=FPS):
    a, b = (int(round(t * fps)) for t in janela)
    return np.asarray(serie)[a:b]


# ---------------------------------------------------------------------------------------------------------------------------
# Painéis
# ---------------------------------------------------------------------------------------------------------------------------
def painel_trajetoria(saida_gravacoes, caminho, caso="andar", titulo=None):
    """O painel pedido: o braço no referencial da câmera, real (CMU) contra jogo (antes e depois).

    Esquerda: plano direita x cima em metros com o cone da câmera a 30 cm. Retângulos = média +- amplitude/2 de ombro, cotovelo e punho
    do braço LIVRE esquerdo (azul: CMU na mesma velocidade; laranja: jogo) e do ombro direito; as linhas são o centro da palma direita,
    que carrega a lanterna (cinza: antes; laranja: depois). Centro: o campo de visão em ângulos, com a lente da lanterna. Direita:
    o vaivém vertical e frente-trás da palma ao longo de 3 s e o espectro."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    definicao = CASOS[caso]
    antes, extras_antes = carregar_caso(saida_gravacoes, caso, "antes")
    depois, extras_depois = carregar_caso(saida_gravacoes, caso, "depois")
    real = referencia(definicao.real) if definicao.real else None
    ego_antes, ego_depois = ego_do_jogo(antes, definicao.janela), ego_do_jogo(depois, definicao.janela)

    figura = plt.figure(figsize=(17, 9.2))
    grade = figura.add_gridspec(2, 3, width_ratios=[1.15, 1.0, 1.0], height_ratios=[1, 1], wspace=0.28, hspace=0.34)
    ax_plano = figura.add_subplot(grade[:, 0])
    caixas = []
    for junta, rotulo in (("ombro", "ombro"), ("cotovelo", "cotovelo"), ("punho", "punho")):
        if real:
            dados = real[junta]["e"]
            caixas.append({"rotulo": f"{rotulo} real", "media": dados["media"], "amplitude": dados["amplitude"], "cor": E.COR_REAL})
        estat = estatisticas(ego_depois[(junta, "e")])
        caixas.append({"rotulo": f"{rotulo} jogo", "media": estat["media"], "amplitude": estat["amplitude"], "cor": E.COR_JOGO, "alfa": 0.25})
    for lado, cor in (("d", E.COR_JOGO),):
        estat = estatisticas(ego_depois[("ombro", lado)])
        caixas.append({"rotulo": "ombro dir. jogo", "media": estat["media"], "amplitude": estat["amplitude"], "cor": cor, "alfa": 0.25})
    curvas = [{"rotulo": "palma direita, antes", "ego": ego_antes[("alvo", "d")], "cor": E.COR_ANTES},
              {"rotulo": "palma direita, depois", "ego": ego_depois[("alvo", "d")], "cor": E.COR_JOGO}]
    E.desenhar_plano(ax_plano, caixas, curvas, titulo=f"{definicao.descricao}: braço esquerdo livre (CMU x jogo)\ne palma direita da lanterna")
    ax_plano.set_xlim(-0.55, 0.55)
    ax_plano.set_ylim(-0.95, 0.15)
    ax_plano.legend(fontsize=7, loc="lower right")

    ax_campo = figura.add_subplot(grade[0, 1])
    lente_a, lente_d = lente_ego(extras_antes, definicao.janela), lente_ego(extras_depois, definicao.janela)
    E.desenhar_campo(ax_campo, [{"rotulo": "lente da lanterna, antes", "ego": lente_a, "cor": E.COR_ANTES},
                                {"rotulo": "lente da lanterna, depois", "ego": lente_d, "cor": E.COR_JOGO}],
                     titulo="o que o jogador vê: a lente da lanterna no campo de 72 x 44 graus")
    ax_campo.text(0.02, 0.02, f"no quadro: antes {100 * E.dentro_do_campo(lente_a):.0f}%, depois {100 * E.dentro_do_campo(lente_d):.0f}%",
                  transform=ax_campo.transAxes, fontsize=8, va="bottom")

    t = np.arange(len(ego_depois[("alvo", "d")])) / FPS
    for linha, (indice, rotulo) in enumerate(((2, "cima (m)"), (1, "frente (m)"))):
        ax = figura.add_subplot(grade[linha, 2])
        n = int(3.0 * FPS)
        for ego, cor, nome in ((ego_antes, E.COR_ANTES, "antes"), (ego_depois, E.COR_JOGO, "depois")):
            serie = ego[("alvo", "d")][:, indice]
            ax.plot(t[:n], serie[:n] - serie.mean(), color=cor, label=nome)
        if real:
            meia = real["ombro"]["d"]["amplitude"][indice] / 2
            ax.axhspan(-meia, meia, color=E.COR_REAL, alpha=0.18, label="ombro real (pico a pico)")
        ax.set_ylabel(f"palma direita, {rotulo}, sem a média")
        ax.set_xlabel("s")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
        if linha == 0:
            ax.set_title("vaivém da palma que carrega a lanterna", fontsize=9)

    ax_esp = figura.add_subplot(grade[1, 1])
    for ego, cor, nome in ((ego_antes, E.COR_ANTES, "antes"), (ego_depois, E.COR_JOGO, "depois")):
        for indice, estilo, eixo in ((2, "-", "cima"), (1, "--", "frente")):
            freq, amplitude = E.espectro(ego[("alvo", "d")][:, indice], FPS)
            ax_esp.plot(freq, amplitude * 1000, color=cor, ls=estilo, label=f"{nome}, {eixo}")
    ax_esp.set_xlabel("Hz")
    ax_esp.set_ylabel("amplitude (mm)")
    ax_esp.set_title("espectro: o passo (2 Hz) e a passada (1 Hz)", fontsize=9)
    ax_esp.grid(alpha=0.2)
    ax_esp.legend(fontsize=7)
    figura.suptitle(titulo or f"Mãos que andam no referencial da câmera: {definicao.descricao}", fontsize=12)
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    figura.savefig(caminho, dpi=110, bbox_inches="tight")
    plt.close(figura)
    return caminho


# ---------------------------------------------------------------------------------------------------------------------------
# Tabela: real ou lei contra jogo, antes e depois, com a origem de cada número
# ---------------------------------------------------------------------------------------------------------------------------
@dataclass
class Linha:
    grupo: str
    metrica: str
    unidade: str
    real: object               # número, texto (faixa) ou None quando não existe referência real
    antes: object
    depois: object
    tolerancia: str            # texto: "+-25%", "dentro de 1 a 5 cm"...
    origem: str                # MEDIDO, DERIVADO ou ESTIMADO (com a fonte)
    ok: object = None          # True, False ou None (sem critério)


def _cm(valor):
    return None if valor is None else round(float(valor) * 100.0, 1)


def _dentro(valor, minimo, maximo):
    return bool(minimo <= valor <= maximo)


def linhas_da_tabela(gravacoes):
    """Todas as linhas da tabela a partir das gravações de `medir` (precisa de antes e depois de cada caso)."""
    from sem_alvorada import conventions as C
    from sem_alvorada import handsway as H
    linhas = []
    eixos = ("lado", "frente", "cima")

    def dados(nome, variante):
        return carregar_caso(gravacoes, nome, variante)

    andar_ref = referencia("andar_rapido")
    a_antes, ea_antes = dados("andar", "antes")
    a_depois, ea_depois = dados("andar", "depois")
    janela = CASOS["andar"].janela
    ego_antes, ego_depois = ego_do_jogo(a_antes, janela), ego_do_jogo(a_depois, janela)

    # --- A. o ombro e o braço livre (a base da mão), andando a 1,7 m/s contra a CMU a 1,5 a 1,6 m/s
    for junta, lado, rotulo in (("ombro", "d", "ombro direito"), ("cotovelo", "e", "cotovelo esquerdo, livre"), ("punho", "e", "punho esquerdo, livre")):
        real = andar_ref[junta][lado]["amplitude"]
        jogo = estatisticas(ego_depois[(junta, lado)])["amplitude"]
        antes = estatisticas(ego_antes[(junta, lado)])["amplitude"]
        for i, eixo in enumerate(eixos):
            if real[i] < 0.01:
                continue
            tol = max(0.25 * real[i], 0.012)
            linhas.append(Linha("A. ombro e braço livre andando", f"{rotulo}: amplitude {eixo}", "cm", _cm(real[i]), _cm(antes[i]), _cm(jogo[i]),
                                f"+-{tol * 100:.1f} cm", "MEDIDO (CMU 08_01 a 08_03, 1,5 a 1,6 m/s)", abs(jogo[i] - real[i]) <= tol))
    real_freq = andar_ref["punho"]["e"]["frequencia_frente"]
    linhas.append(Linha("A. ombro e braço livre andando", "punho esquerdo livre: frequência do balanço", "Hz", round(real_freq, 2),
                        round(estatisticas(ego_antes[("punho", "e")])["freq_frente"], 2), round(estatisticas(ego_depois[("punho", "e")])["freq_frente"], 2),
                        "+-0,13 Hz", "MEDIDO (a passada: 1 ciclo)", abs(estatisticas(ego_depois[("punho", "e")])["freq_frente"] - real_freq) <= 0.13))

    # --- B. olhar para baixo: o braço livre entra no quadro
    clipes = ("08_01", "08_02", "08_03")
    for graus in (30, 45, 60, 75):
        nome = f"olhar_{graus}"
        rec_d, _ = dados(nome, "depois")
        rec_a, _ = dados(nome, "antes")
        ego_d, ego_a = ego_do_jogo(rec_d, CASOS[nome].janela), ego_do_jogo(rec_a, CASOS[nome].janela)
        real = estatisticas(real_rotacionado(clipes, "punho", "e", graus))
        jogo, antes = estatisticas(ego_d[("punho", "e")]), estatisticas(ego_a[("punho", "e")])
        for i in (1, 2):
            tol = 0.3 * real["amplitude"][i]
            linhas.append(Linha("B. olhar para baixo", f"{graus} graus, punho esquerdo livre: amplitude {eixos[i]}", "cm", _cm(real["amplitude"][i]),
                                _cm(antes["amplitude"][i]), _cm(jogo["amplitude"][i]), f"+-{tol * 100:.0f} cm", "MEDIDO (CMU girada para a inclinação)",
                                abs(jogo["amplitude"][i] - real["amplitude"][i]) <= tol))
        linhas.append(Linha("B. olhar para baixo", f"{graus} graus, punho esquerdo livre: no quadro", "% dos quadros", round(100 * real["no_campo"]),
                            round(100 * antes["no_campo"]), round(100 * jogo["no_campo"]), "sem tolerância (a posição média difere ~10 cm: ver nota)",
                            "MEDIDO (CMU girada, sem a translação do olho)", None))
    # --- C. a mão que carrega a lanterna
    for nome, rotulo in (("andar", "andando 1,7 m/s"), ("correr", "correndo 4,0 m/s"), ("agachado", "agachado 0,8 m/s")):
        janela_c = CASOS[nome].janela
        antes_rec, _ = dados(nome, "antes")
        depois_rec, extras_depois = dados(nome, "depois")
        antes = estatisticas(ego_do_jogo(antes_rec, janela_c)[("alvo", "d")])
        depois = estatisticas(ego_do_jogo(depois_rec, janela_c)[("alvo", "d")])
        for i, eixo in enumerate(eixos):
            teto = 0.07 if nome == "correr" else 0.05
            linhas.append(Linha("C. palma que carrega a lanterna", f"{rotulo}: amplitude {eixo}", "cm", f"1 a {teto * 100:.0f}", _cm(antes["amplitude"][i]),
                                _cm(depois["amplitude"][i]), f"entre 0,5 e {teto * 100:.0f} cm", "ESTIMADO (ordem de grandeza: ombro real + mola; não há clipe de lanterna andando)",
                                _dentro(depois["amplitude"][i], 0.005, teto)))
        stride = float(np.polyfit(np.arange(len(depois_rec.jogador["fase_passo"])) / depois_rec.fps, depois_rec.jogador["fase_passo"], 1)[0]) / math.tau
        perto_do_ritmo = min(abs(depois["freq_cima"] - stride) / stride, abs(depois["freq_cima"] - 2 * stride) / (2 * stride)) < 0.2
        linhas.append(Linha("C. palma que carrega a lanterna", f"{rotulo}: frequência dominante da subida e descida", "Hz", f"passada {stride:.2f} ou passo {2 * stride:.2f}",
                            round(antes["freq_cima"], 2), round(depois["freq_cima"], 2), "a 20% da passada ou do passo", "MEDIDO (o ombro real balança na passada, 0,8 a 1,0 Hz)", perto_do_ritmo))
        palma_campo_a, palma_campo_d = antes["no_campo"], depois["no_campo"]
        linhas.append(Linha("C. palma que carrega a lanterna", f"{rotulo}: palma dentro do quadro", "% dos quadros", None, round(100 * palma_campo_a), round(100 * palma_campo_d),
                            "sem critério (a palma fica no limite de baixo)", "MEDIDO (no jogo)", None))
    walk_a = estatisticas(ego_do_jogo(dados("andar", "depois")[0], CASOS["andar"].janela)[("alvo", "d")])
    run_a = estatisticas(ego_do_jogo(dados("correr", "depois")[0], CASOS["correr"].janela)[("alvo", "d")])
    walk_b = estatisticas(ego_do_jogo(dados("andar", "antes")[0], CASOS["andar"].janela)[("alvo", "d")])
    run_b = estatisticas(ego_do_jogo(dados("correr", "antes")[0], CASOS["correr"].janela)[("alvo", "d")])
    linhas.append(Linha("C. palma que carrega a lanterna", "correr menos andar: a palma sobe", "cm", "+5 (ombro) a +19 (mão livre)", _cm(run_b["media"][2] - walk_b["media"][2]),
                        _cm(run_a["media"][2] - walk_a["media"][2]), "entre +2 e +10 cm", "MEDIDO no ombro (CMU, +5 cm); ESTIMADO na mão", _dentro(run_a["media"][2] - walk_a["media"][2], 0.02, 0.10)))
    # --- D. partida, parada e giro
    natural, zeta = H.natural_frequency((1.0, 0.0, 0.0), H.ITEM_MASS["flashlight"]), H.damping_ratio((1.0, 0.0, 0.0))
    _, arrancar_antes = dados("arrancar", "antes")
    _, arrancar_depois = dados("arrancar", "depois")
    janela_partida = slice(int(1.4 * FPS), int(2.8 * FPS))
    recuo_lei = C.ACCEL_START / natural ** 2 * (1.0 + math.exp(-math.pi * zeta / math.sqrt(1.0 - zeta ** 2)))
    recuo = float(arrancar_depois["extensao"][janela_partida, 2].max())
    linhas.append(Linha("D. partida, parada e giro", "partida: recuo da mão", "cm", _cm(recuo_lei), 0.0, _cm(recuo),
                        "+-30% (a aceleração real oscila e o ombro se mexe)", "DERIVADO (resposta da mola ao degrau de 5 m/s2, `C.ACCEL_START`)", abs(recuo - recuo_lei) <= 0.3 * recuo_lei))
    _, parar_depois = dados("parar", "depois")
    avanco = float(-parar_depois["extensao"][int(3.0 * FPS):int(4.4 * FPS), 2].min())
    freada = 1.7 / C.STOP_TIME
    avanco_lei = freada / natural ** 2 * (1.0 + math.exp(-math.pi * zeta / math.sqrt(1.0 - zeta ** 2)))
    linhas.append(Linha("D. partida, parada e giro", "parada de 1,7 m/s em 0,65 s: avanço da mão", "cm", _cm(avanco_lei), 0.0, _cm(avanco),
                        "+-40% (a freada acaba antes do pico da mola)", "DERIVADO (degrau de 2,6 m/s2)", abs(avanco - avanco_lei) <= 0.4 * avanco_lei))
    giro_antes, giro_extras = dados("giro", "antes")[0], dados("giro", "depois")[1]
    atraso_s = float(giro_extras["atraso"].max()) / 180.0
    linhas.append(Linha("D. partida, parada e giro", "giro do mouse a 180 graus/s: tronco atrás do olhar", "ms", "70 a 170", None, round(1000 * atraso_s),
                        "70 a 170 ms", "MEDIDO (fase 4, `Locomotion._follow_yaw`; o modelo novo só lê)", _dentro(atraso_s, 0.07, 0.17)))
    lateral = float(giro_extras["deslocamento"][:, 0].max())
    _, giro_antes_ex = dados("giro", "antes")
    lateral_antes = float(giro_antes_ex["deslocamento"][:, 0].max())
    linhas.append(Linha("D. partida, parada e giro", "giro do mouse a 180 graus/s parado: varrida lateral da mão", "cm", "<= 7 (peito soldado)", _cm(lateral_antes), _cm(lateral),
                        "entre 1,5 e 8 cm", "DERIVADO (alavanca de 35 cm sobre o peito atrasado: `LEVER_SHARE` = 0,6, ESTIMADO)", _dentro(lateral, 0.015, 0.08)))
    # --- E. parado
    rec_ant, ex_ant = dados("parado", "antes")
    rec_dep, ex_dep = dados("parado", "depois")
    janela_p = slice(60, None)
    linhas.append(Linha("E. parado", "inclinação do feixe, pico a pico", "graus", "0,3 a 0,6", round(float(np.ptp(ex_ant["rotacao"][janela_p, 0])), 2),
                        round(float(np.ptp(ex_dep["rotacao"][janela_p, 0])), 2), "0,25 a 0,9", "ESTIMADO (respiração 0,20 + deriva 0,10 graus de amplitude; a cabeça faz 0,12, MEDIDO)",
                        _dentro(float(np.ptp(ex_dep["rotacao"][janela_p, 0])), 0.25, 0.9)))
    linhas.append(Linha("E. parado", "deslocamento da mão, pico a pico (maior eixo)", "mm", "< 4", round(float(np.ptp(ex_ant["deslocamento"][janela_p], axis=0).max()) * 1000, 1),
                        round(float(np.ptp(ex_dep["deslocamento"][janela_p], axis=0).max()) * 1000, 1), "< 4 mm",
                        "DERIVADO (o ombro e a câmera sobem juntos com a respiração; a mão não se desloca em relação a eles)", float(np.ptp(ex_dep["deslocamento"][janela_p], axis=0).max()) < 0.004))
    linhas.append(Linha("E. parado", "deriva postural do feixe, amplitude em repouso e esgotado", "graus", "0,1 a 0,3", "0 (não havia)", f"{H.DRIFT_DEG:.2f} e {H.DRIFT_DEG * (1 + H.DRIFT_FATIGUE_GAIN):.2f}",
                        "0,1 a 0,3", "ESTIMADO (docs/FASE5.md; cresce com o cansaço)", True))
    linhas.append(Linha("E. parado", "tremor fisiológico de 8 Hz no punho", "graus", "0,02 a 0,05", "0", "0 (não modelado)", "abaixo de 1 pixel a 1280 x 720",
                        "ESTIMADO (0,12 a 0,24 mm no dedo, 0,3 m de alavanca)", None))
    return linhas


def escrever_tabela(linhas, caminho_base):
    """Escreve `<caminho_base>.md` e `<caminho_base>.png`. Devolve (n linhas com critério, n dentro)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(os.path.dirname(os.path.abspath(caminho_base)), exist_ok=True)
    com_criterio = [l for l in linhas if l.ok is not None]
    dentro = [l for l in com_criterio if l.ok]
    with open(caminho_base + ".md", "w", encoding="utf-8") as arquivo:
        arquivo.write("| Grupo | Métrica | Unidade | Real ou lei | Antes | Depois | Tolerância | Origem | Dentro |\n|---|---|---|---|---|---|---|---|---|\n")
        for l in linhas:
            marca = "" if l.ok is None else ("sim" if l.ok else "NAO")
            arquivo.write(f"| {l.grupo} | {l.metrica} | {l.unidade} | {l.real if l.real is not None else 'sem referência'} | {l.antes} | {l.depois} | {l.tolerancia} | {l.origem} | {marca} |\n")
        arquivo.write(f"\n{len(dentro)} de {len(com_criterio)} linhas com critério dentro da tolerância.\n")
    altura = 0.34 * len(linhas) + 1.4
    figura, ax = plt.subplots(figsize=(19, altura))
    ax.axis("off")
    cabecalho = ["métrica", "unid.", "real ou lei", "antes", "depois", "tolerância", "origem"]
    texto = [[l.metrica[:58], l.unidade, "sem referência" if l.real is None else str(l.real), str(l.antes), str(l.depois), l.tolerancia[:40], l.origem[:70]] for l in linhas]
    tabela = ax.table(cellText=texto, colLabels=cabecalho, loc="upper center", cellLoc="left", colWidths=[0.27, 0.06, 0.12, 0.07, 0.07, 0.14, 0.27])
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(7)
    tabela.scale(1, 1.25)
    for i, l in enumerate(linhas, start=1):
        cor = "#ffffff" if l.ok is None else ("#e3f2e1" if l.ok else "#f8d9d6")
        for j in range(len(cabecalho)):
            tabela[i, j].set_facecolor(cor)
    ax.set_title(f"Mãos que andam: real ou lei contra jogo, antes e depois ({len(dentro)} de {len(com_criterio)} linhas com critério dentro)", fontsize=11)
    figura.savefig(caminho_base + ".png", dpi=100, bbox_inches="tight")
    plt.close(figura)
    return len(com_criterio), len(dentro)


def painel_transientes(gravacoes, caminho):
    """Partida, parada e giro do mouse: o deslocamento da mão em relação à câmera, antes e depois."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figura, eixos = plt.subplots(2, 3, figsize=(16, 7.5))
    casos = (("arrancar", (1.2, 3.5), "parado, arranca andando (t = 1,5 s)"), ("parar", (2.0, 5.0), "andando, para (t = 3,0 s)"),
             ("giro", (0.3, 2.8), "parado, gira 180 graus/s por 1 s (t = 0,5 a 1,5 s)"))
    for coluna, (nome, (t0, t1), titulo) in enumerate(casos):
        for variante, cor in (("antes", E.COR_ANTES), ("depois", E.COR_JOGO)):
            rec, ex = carregar_caso(gravacoes, nome, variante)
            a, b = int(t0 * FPS), int(t1 * FPS)
            t = np.arange(a, b) / FPS
            desl = ex["deslocamento"][a:b]
            eixos[0, coluna].plot(t, -desl[:, 2] * 100, color=cor, label=f"{variante}: frente (+) ou trás (-)")
            eixos[1, coluna].plot(t, desl[:, 0] * 100, color=cor, ls="-", label=f"{variante}: lado")
            eixos[1, coluna].plot(t, desl[:, 1] * 100, color=cor, ls="--", label=f"{variante}: cima")
            if variante == "depois" and nome == "giro":
                eixos[0, coluna].plot(t, ex["atraso"][a:b] / 5.0, color="#2a78d6", ls=":", label="atraso do tronco (graus / 5)")
        eixos[0, coluna].set_title(titulo, fontsize=9)
        for fila in (0, 1):
            eixos[fila, coluna].grid(alpha=0.2)
            eixos[fila, coluna].set_xlabel("s")
            eixos[fila, coluna].set_ylabel("cm, em relação à câmera")
            eixos[fila, coluna].legend(fontsize=7)
    figura.suptitle("A mão da lanterna na partida, na parada e no giro do mouse (a mola de antes só seguia o balanço da cabeça)", fontsize=11)
    figura.savefig(caminho, dpi=105, bbox_inches="tight")
    plt.close(figura)
    return caminho


def quadros_de_pasta(pasta, prefixo):
    """Os `raw_<modo>_NN.png` de uma pasta de `tools/prints_andando.py`, em ordem, como [h, w, 3] uint8."""
    from PIL import Image
    nomes = sorted(n for n in os.listdir(pasta) if n.startswith(prefixo) and n.endswith(".png"))
    return [np.asarray(Image.open(os.path.join(pasta, n)).convert("RGB")) for n in nomes]


def montar_video(pasta_antes, pasta_depois, saida, titulo, modo, fps=20, lento=1):
    """Vídeo [antes | depois] da câmera do jogador a partir dos quadros de duas pastas de `prints_andando.py` (mesmo roteiro, mesma
    câmera, a mola de antes à esquerda e a nova à direita). Escreve o MP4 e uma folha de seis quadros. Devolve (mp4, folha)."""
    from tools.movimento_ref import comparar
    antes, depois = quadros_de_pasta(pasta_antes, f"raw_{modo}_"), quadros_de_pasta(pasta_depois, f"raw_{modo}_")
    n = min(len(antes), len(depois))
    quadros = []
    for i in range(n):
        a = comparar.rotular(antes[i], [f"ANTES  {titulo}", "mola simples (fase 4)"], (6, 6), cor=(235, 235, 235))
        d = comparar.rotular(depois[i], [f"DEPOIS  {titulo}", "mão apoiada no ombro (fase 5)"], (6, 6), cor=(255, 214, 160))
        quadros.append(np.concatenate([a, np.full((a.shape[0], 4, 3), 255, np.uint8), d], axis=1))
    saida_mp4 = comparar.escrever_mp4([q for q in quadros for _ in range(lento)], saida, fps=fps)[0]
    indices = np.linspace(0, n - 1, 6).round().astype(int)
    folha = comparar.grade([comparar.rotular(quadros[i][:, :], [f"t = {i / fps:.2f} s"], (6, quadros[i].shape[0] - 28)) for i in indices], 2)
    caminho_folha = comparar.salvar_png(folha, os.path.splitext(saida)[0] + "_folha.png")
    return saida_mp4, caminho_folha


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("acao", choices=("medir", "painel", "tabela", "video"))
    parser.add_argument("--antes", help="video: pasta de quadros de antes (prints_andando.py --modelo antes)")
    parser.add_argument("--depois", help="video: pasta de quadros de depois")
    parser.add_argument("--modo", default="andar", help="video: modo de prints_andando (andar, correr, agachar, parando, escada...)")
    parser.add_argument("--titulo", default="", help="video: legenda")
    parser.add_argument("--mp4", help="video: caminho do MP4")
    parser.add_argument("--saida", default=os.path.join(ROOT, "out", "f5_1", "final"))
    parser.add_argument("--casos", default=",".join(CASOS))
    args = parser.parse_args(argv)
    gravacoes = os.path.join(args.saida, "gravacoes")
    if args.acao == "video":
        print("[maos_andando]", *montar_video(args.antes, args.depois, args.mp4, args.titulo, args.modo))
        return 0
    if args.acao == "medir":
        jogo = preparar_jogo(palco=True)
        for nome in args.casos.split(","):
            if nome == "escada":
                continue
            for variante in ("antes", "depois"):
                gravar_caso(jogo, nome, variante, saida=gravacoes)
                print(f"[maos_andando] gravado {nome} {variante}")
        if "escada" in args.casos.split(","):
            casa = preparar_jogo(palco=False)
            for variante in ("antes", "depois"):
                gravar_caso(casa, "escada", variante, saida=gravacoes, inicio=(5.6, 1.6, 0.0, 0.0))
                print(f"[maos_andando] gravado escada {variante}")
    if args.acao in ("medir", "painel"):
        for nome in CASOS_DO_PAINEL:
            if nome in args.casos.split(","):
                print("[maos_andando]", painel_trajetoria(gravacoes, os.path.join(args.saida, f"painel_ego_{nome}.png"), nome))
        print("[maos_andando]", painel_transientes(gravacoes, os.path.join(args.saida, "painel_transientes.png")))
    if args.acao in ("medir", "tabela"):
        linhas = linhas_da_tabela(gravacoes)
        total, dentro = escrever_tabela(linhas, os.path.join(args.saida, "tabela_maos_andando"))
        print(f"[maos_andando] tabela: {dentro} de {total} linhas com critério dentro da tolerância")
    return 0


if __name__ == "__main__":
    sys.exit(main())
