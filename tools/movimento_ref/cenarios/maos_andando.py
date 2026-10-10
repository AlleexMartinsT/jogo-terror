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


def gravar_caso(jogo, nome, variante, saida=None, ossos="armadura", inicio=None, extras_lado="R", roteiro=None):
    """Grava o caso `nome` com o modelo `variante`. Devolve (Gravacao, extras): `extras` tem, por quadro, a lente da lanterna
    (espaço da câmera), o apoio e a extensão da mola, o deslocamento e a rotação que a mão recebeu, e o atraso do corpo."""
    from tools.movimento_ref import grava
    from sem_alvorada.engine.inputstate import InputState
    caso = CASOS[nome]
    usar_modelo(jogo, variante)
    jogo.hands.sway.reset()
    x, y, z, yaw = inicio or (0.0, 0.0, 0.0, 0.0)
    jogo.place_player(x, y, z, yaw)
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("acao", choices=("medir", "painel"))
    parser.add_argument("--saida", default=os.path.join(ROOT, "out", "f5_1", "final"))
    parser.add_argument("--casos", default=",".join(CASOS))
    args = parser.parse_args(argv)
    gravacoes = os.path.join(args.saida, "gravacoes")
    if args.acao == "medir":
        jogo = preparar_jogo(palco=True)
        for nome in args.casos.split(","):
            for variante in ("antes", "depois"):
                gravar_caso(jogo, nome, variante, saida=gravacoes)
                print(f"[maos_andando] gravado {nome} {variante}")
    for nome in CASOS_DO_PAINEL:
        if nome in args.casos.split(","):
            print("[maos_andando]", painel_trajetoria(gravacoes, os.path.join(args.saida, f"painel_ego_{nome}.png"), nome))
    return 0


if __name__ == "__main__":
    sys.exit(main())
