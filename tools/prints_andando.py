"""Folha de contato do que o jogador vê das mãos enquanto se move: andar, correr, agachar ou parado.

    LIBGL_ALWAYS_SOFTWARE=1 python tools/prints_andando.py andar --out out/f5/andar
        [--sem-lanterna] [--quadros 12] [--passo 0.1] [--res 640x360] [--samples 4] [--aquecimento 1.5]

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

DT = 1.0 / 30.0
MODOS = ("andar", "correr", "agachar", "parado")
PITCH_INICIAL = -6.0


def entrada_do_modo(modo):
    entrada = InputState()
    if modo != "parado":
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
    args = parser.parse_args()
    tamanho = tuple(int(v) for v in args.res.lower().split("x"))
    os.makedirs(args.out, exist_ok=True)

    jogo = grava.montar_jogo(palco=False, pista=8.0)
    cena = bpy.context.scene
    jogo.state.flags.add(FLAG_BLACKOUT)
    jogo.lights.set_power(False)
    maos.give(jogo, flashlight=not args.sem_lanterna, on=True)
    if not args.sem_lanterna:
        jogo.hands.equip(C.ITEM_FLASHLIGHT)
    for _ in range(int(0.8 / DT)):
        jogo.tick(DT, InputState())
    jogo.player.pitch = math.radians(PITCH_INICIAL)
    cena.camera = jogo.player_cam
    maos.studio(cena, jogo)
    prender_estudio_a_camera(jogo.player_cam)

    for _ in range(int(args.aquecimento / DT)):
        jogo.tick(DT, entrada_do_modo(args.modo))
    quadros, legendas, relogio = [], [], 0.0
    while len(quadros) < args.quadros:
        jogo.tick(DT, entrada_do_modo(args.modo))
        relogio += DT
        if relogio + 1e-6 >= (len(quadros) + 1) * args.passo:
            caminho = os.path.join(args.out, f"raw_{args.modo}_{len(quadros):02d}.png")
            quadros.append(maos.render_frame(cena, jogo, caminho, tamanho, args.samples))
            legendas.append(f"{args.modo} t={relogio:.2f}s fase={jogo.player.stride_phase / math.pi:.2f}")
    folha = os.path.join(args.out, f"folha_{args.modo}.png")
    maos.contact_sheet(quadros, legendas, args.colunas, folha)
    print(f"[andando] {folha}: {len(quadros)} quadros")


if __name__ == "__main__":
    main()
