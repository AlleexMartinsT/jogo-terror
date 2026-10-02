"""Folha de inspeção com cada móvel virado de frente para a câmera, qualquer que seja o seu yaw na casa.

`tools/inspect_object.py` posiciona a câmera pelos eixos do mundo, então um móvel girado na parede (a geladeira
olha para oeste) aparece de lado. Este atalho gira os objetos pedidos para yaw = 180 graus num .blend temporário e chama o
inspetor de sempre:

    python tools/modelagem/inspecionar_de_frente.py --blend out/agente5/x.blend --out out/agente5/insp fridge stove_kitchen
"""
import argparse
import fnmatch
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402

from tools import inspect_object  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("objetos", nargs="+")
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", default="out/agente5/insp")
    parser.add_argument("--views", default="3q,frente,lado")
    parser.add_argument("--res", default="480x480")
    parser.add_argument("--samples", default="24")
    args = parser.parse_args()
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    for obj in bpy.data.objects:
        if any(fnmatch.fnmatch(obj.name, pattern) for pattern in args.objetos):
            obj.rotation_euler.z = math.pi     # a frente do móvel (+Y local) passa a olhar para a câmera, que fica em -Y
    temporary = os.path.join(os.path.dirname(os.path.abspath(args.blend)), "_de_frente.blend")
    bpy.ops.wm.save_as_mainfile(filepath=temporary, copy=True)
    return inspect_object.main(["--blend", temporary, "--out", args.out, "--views", args.views, "--res", args.res,
                                "--samples", args.samples, *args.objetos])


if __name__ == "__main__":
    sys.exit(main())
