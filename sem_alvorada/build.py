"""Constrói SemAlvorada.blend inteiro por código (sem assets externos).

    python -m sem_alvorada.build                       # tudo
    python -m sem_alvorada.build --stages world,props --out out/parcial.blend
    python -m sem_alvorada.build --strict              # aborta na primeira falha

Cada etapa é um pacote `sem_alvorada.<nome>` com `build(ctx)`.
"""
import argparse
import importlib
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from sem_alvorada import BLEND_PATH, compat  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402

# ordem importa: world -> props -> entity -> cutscenes -> ai (lê colisões) -> audio -> engine
STAGES = ["world", "props", "entity", "cutscenes", "ai", "audio", "engine"]


def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "SemAlvorada"
    scene.unit_settings.system = "METRIC"
    scene.render.resolution_x, scene.render.resolution_y = C.RES_X, C.RES_Y
    scene.render.fps = 30
    compat.use_eevee(scene)
    return scene


def run(stages=None, out=None, strict=False, quality="medium", keep_open=False):
    stages = stages or STAGES
    out = out or BLEND_PATH
    scene = fresh_scene()
    ctx = BuildContext(scene, quality=quality)
    failures = []
    t_all = time.time()
    for name in stages:
        ctx.stage = name
        t0 = time.time()
        try:
            mod = importlib.import_module(f"sem_alvorada.{name}")
            mod.build(ctx)
            print(f"[build] {name}: ok ({time.time() - t0:.1f}s)", flush=True)
        except Exception as exc:     # noqa: BLE001 - queremos seguir para as outras etapas
            failures.append((name, exc))
            print(f"[build] {name}: FALHOU: {exc}", flush=True)
            traceback.print_exc()
            if strict:
                raise
    # Texturas geradas por código só sobrevivem ao salvar se forem empacotadas no .blend.
    for img in bpy.data.images:
        if img.source == "GENERATED" and img.packed_file is None and img.users:
            img.pack()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True)
    print(f"[build] salvo em {out} ({os.path.getsize(out) / 1e6:.1f} MB) em {time.time() - t_all:.1f}s", flush=True)
    if failures:
        print("[build] etapas com falha:", ", ".join(n for n, _ in failures), flush=True)
    return failures


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default=",".join(STAGES))
    ap.add_argument("--out", default=BLEND_PATH)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--quality", default="medium", choices=["low", "medium", "high"])
    args = ap.parse_args(argv)
    failures = run(args.stages.split(","), args.out, args.strict, args.quality)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
