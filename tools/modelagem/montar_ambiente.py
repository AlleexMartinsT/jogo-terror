"""Monta a cozinha e a garagem NOVAS dentro do mundo antigo (out/base_antes.blend), sem depender da etapa `world`.

Outros agentes estão reescrevendo o mundo: para ver as minhas peças em contexto, com paredes, piso e janelas
estáveis, abro o .blend da fase anterior, deixo o `props.build` apagar a mobília velha e recriar só os cômodos
pedidos em SA_ROOMS (itens e âncoras incluídos).

    SA_ROOMS=kitchen,garage,items,anchors python tools/modelagem/montar_ambiente.py --out out/agente5/ambiente.blend
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
os.environ.setdefault("SA_ROOMS", "kitchen,garage,items,anchors")

import bpy  # noqa: E402

from sem_alvorada import props  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.path.join(ROOT, "out", "base_antes.blend"))
    parser.add_argument("--out", default=os.path.join(ROOT, "out", "agente5", "ambiente.blend"))
    args = parser.parse_args()
    bpy.ops.wm.open_mainfile(filepath=args.base)
    ctx = BuildContext(bpy.context.scene, verbose=False)
    ctx.stage = "props"
    props.build(ctx)
    for image in bpy.data.images:
        if image.source == "GENERATED" and image.packed_file is None and image.users:
            image.pack()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.out, compress=True)
    print(f"[ambiente] {args.out}", flush=True)


if __name__ == "__main__":
    main()
