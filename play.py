"""Inicia SEM ALVORADA dentro do Blender.

    blender SemAlvorada.blend --python play.py -- --quality medium
    blender --python play.py -- --quality low --skip-intro --debug

Opções depois de '--':  --quality low|medium|high   --skip-intro   --debug
Pelo editor de texto do Blender, rode o texto `jogar.py` que vai dentro do .blend.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from sem_alvorada import BLEND_PATH  # noqa: E402


def parse_options(argv):
    """Lê só o que vem depois de '--' (o resto é do Blender)."""
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser(prog="play.py", description="Joga SEM ALVORADA")
    parser.add_argument("--quality", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--skip-intro", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args(tail)


def ensure_game_file_open():
    """Abre SemAlvorada.blend se nenhum arquivo está carregado. Devolve False se ele não existe."""
    if bpy.data.filepath:
        return True
    if not os.path.exists(BLEND_PATH):
        print(f"[play] {BLEND_PATH} não existe. Gere com: python -m sem_alvorada.build", flush=True)
        return False
    bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
    return True


def main():
    options = parse_options(sys.argv)
    if not ensure_game_file_open():
        return
    from sem_alvorada.engine import launcher
    launcher.start(quality=options.quality, skip_intro=options.skip_intro, debug=options.debug)


main()
