"""Folha de contato do que o jogador vê das mãos enquanto se move: andar, correr, agachar ou parado.

    LIBGL_ALWAYS_SOFTWARE=1 python tools/prints_andando.py andar --out out/f5/andar
        [--sem-lanterna] [--quadros 12] [--passo 0.1] [--res 640x360] [--samples 4] [--aquecimento 1.5]
        [--modelo antes|depois] [--esteira] [--item-esquerda KEY|MAP|BATTERY] [--olhar -45]

O jogador anda numa pista livre da casa (`grava.achar_pista`, 8 m). O fundo do estúdio é preso à câmera para
acompanhar a caminhada (o de `prints_maos.studio` fica parado no mundo). `--aquecimento` deixa o corpo chegar
ao regime antes do primeiro quadro; quadros e passo são em segundos de jogo.
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.engine.game import InputState  # noqa: E402
from sem_alvorada.engine.state import FLAG_BLACKOUT  # noqa: E402
from tools import prints_maos as maos  # noqa: E402
from tools.movimento_ref import grava  # noqa: E402

DT = 1.0 / 60.0               # o passo do jogo é o de jogar (60 Hz); os quadros saem a cada `--passo` segundos
MODOS = ("andar", "correr", "agachar", "parado", "parando", "arrancando", "escada")
PITCH_INICIAL = -6.0


def entrada_do_modo(modo, t=0.0, parar_em=None, arrancar_em=None):
    """`parando` anda até `parar_em` s e solta o teclado; `arrancando` fica parado até `arrancar_em` s e anda. `t` conta desde o começo."""
    entrada = InputState()
    anda = modo not in ("parado",)
    if modo == "parando" and parar_em is not None and t >= parar_em:
        anda = False
    if modo == "arrancando" and arrancar_em is not None and t < arrancar_em:
        anda = False
    if anda:
        entrada.move_y = 1.0
    entrada.run = modo == "correr"
    entrada.crouch = modo == "agachar"
    return entrada


def prender_estudio_a_camera(camera):
    """O fundo e as luzes do estúdio andam junto com a câmera, senão o jogador atravessa a parede de fundo."""
    for objeto in bpy.data.objects:
        if objeto.name.startswith("estudio_"):
            objeto.parent = camera
            objeto.matrix_parent_inverse = camera.matrix_world.inverted()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("modo", choices=MODOS)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sem-lanterna", action="store_true")
    parser.add_argument("--quadros", type=int, default=12)
    parser.add_argument("--passo", type=float, default=0.1)
    parser.add_argument("--aquecimento", type=float, default=1.5)
    parser.add_argument("--res", default="640x360")
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--colunas", type=int, default=4)
    parser.add_argument("--modelo", choices=("antes", "depois"), default="depois",
                        help="antes = a mola simples da fase 4 (cenarios/maos_andando.SwayAntigo)")
    parser.add_argument("--esteira", action="store_true",
                        help="a pista tem 8 m: devolve o jogador ao começo antes de chegar ao fim, sem tocar na velocidade nem na passada")
    parser.add_argument("--item-esquerda", choices=("KEY", "MAP", "BATTERY"), default=None)
    parser.add_argument("--casa", action="store_true", help="a casa escura, só a lanterna ilumina (sem o fundo do estúdio)")
    parser.add_argument("--parar-em", type=float, default=None, help="modo parando: segundo em que o jogador solta o teclado")
    parser.add_argument("--arrancar-em", type=float, default=None, help="modo arrancando: segundo em que o jogador começa a andar")
    parser.add_argument("--olhar", type=float, default=PITCH_INICIAL, help="inclinação do olhar em graus (negativo = para baixo)")
    args = parser.parse_args()
    tamanho = tuple(int(v) for v in args.res.lower().split("x"))
    os.makedirs(args.out, exist_ok=True)

    jogo = grava.montar_jogo(palco=False, pista=8.0)
    cena = bpy.context.scene
    jogo.state.flags.add(FLAG_BLACKOUT)
    jogo.lights.set_power(False)
    esquerda = {"KEY": C.ITEM_KEY, "MAP": C.ITEM_MAP, "BATTERY": C.ITEM_BATTERY}.get(args.item_esquerda)
    maos.give(jogo, flashlight=not args.sem_lanterna, key=esquerda == C.ITEM_KEY, map_=esquerda == C.ITEM_MAP,
              batteries=1 if esquerda == C.ITEM_BATTERY else 0, on=True)
    if not args.sem_lanterna:
        jogo.hands.equip(C.ITEM_FLASHLIGHT)
    if esquerda is not None:
        jogo.hands.equip(esquerda)
    if args.modelo == "antes":
        from tools.movimento_ref.cenarios.maos_andando import SwayAntigo
        jogo.hands.sway = SwayAntigo(jogo)
    for _ in range(int(0.8 / DT)):
        jogo.tick(DT, InputState())
    jogo.player.pitch = math.radians(args.olhar)
    cena.camera = jogo.player_cam
    if args.modo == "escada":
        args.casa = True
        jogo.place_player(5.6, 1.2, 0.0, 0.0)
        jogo.player.pitch = math.radians(args.olhar)
    if not args.casa:
        maos.studio(cena, jogo)
        prender_estudio_a_camera(jogo.player_cam)

    direcao = (-math.sin(jogo.player.yaw), math.cos(jogo.player.yaw))
    if args.esteira:           # o começo da pista vê um brilho forte (o fundo do corredor): a esteira roda mais adiante, a 2,6 m do começo
        jogo.place_player(jogo.player.x + direcao[0] * 2.6, jogo.player.y + direcao[1] * 2.6, jogo.player.z, jogo.player.yaw)
        jogo.player.pitch = math.radians(args.olhar)
        for _ in range(int(0.5 / DT)):
            jogo.tick(DT, InputState())
    inicio = (jogo.player.x, jogo.player.y)

    relogio_do_modo = [0.0]

    def passo_do_jogo():
        jogo.tick(DT, entrada_do_modo(args.modo, relogio_do_modo[0], args.parar_em, args.arrancar_em))
        relogio_do_modo[0] += DT
        if args.esteira:
            andado = (jogo.player.x - inicio[0]) * direcao[0] + (jogo.player.y - inicio[1]) * direcao[1]
            if andado > 4.0:
                jogo.player.x -= direcao[0] * 3.5
                jogo.player.y -= direcao[1] * 3.5

    for _ in range(int(args.aquecimento / DT)):
        passo_do_jogo()
    quadros, legendas, relogio = [], [], 0.0
    while len(quadros) < args.quadros:
        passo_do_jogo()
        relogio += DT
        if relogio + 1e-6 >= (len(quadros) + 1) * args.passo:
            caminho = os.path.join(args.out, f"raw_{args.modo}_{len(quadros):02d}.png")
            quadros.append(maos.render_frame(cena, jogo, caminho, tamanho, args.samples))
            legendas.append(f"{args.modo} t={relogio:.2f}s fase={jogo.player.stride_phase / math.pi:.2f}")
    if len(quadros) <= 24:
        folha = os.path.join(args.out, f"folha_{args.modo}.png")
        maos.contact_sheet(quadros, legendas, args.colunas, folha)
        print(f"[andando] {folha}: {len(quadros)} quadros")
    else:
        print(f"[andando] {args.out}: {len(quadros)} quadros")


if __name__ == "__main__":
    main()
