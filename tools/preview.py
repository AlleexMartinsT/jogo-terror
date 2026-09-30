"""Renderiza vistas de um .blend em modo headless, para conferir o que foi construído.

Uso na linha de comando:
    python tools/preview.py --blend out/parcial.blend --out out/prev \
        --view "sala:2.5,3,1.65,-90,0" --view "quarto:1.9,5.85,4.45,-90,-5" \
        --engine cycles --res 640x360 --samples 24 --fill 0.15

Uso como biblioteca (dentro de um script bpy já com a cena montada):
    from tools import preview
    preview.render_views(scene, [("nome", (x, y, z), yaw_deg, pitch_deg)], "out/prev")

Cada vista: "nome:x,y,z,yaw_deg,pitch_deg". yaw 0 olha para +Y (norte), -90 olha para +X;
pitch positivo olha para cima. z é a altura do olho em metros no mundo.

Motores:
    workbench  ~0,3 s   só formas; cores = cor de viewport do material (diffuse_color)
    cycles     ~5-40 s  CPU; mostra materiais/luzes de verdade (bom para checar texturas)
    eevee      ~30 s+   é o motor do jogo; em software (llvmpipe) é lento

--fill N   acende o mundo com luz branca de força N (0 = escuro real). Útil p/ ver geometria.
--exposure E   compensa renders escuros (stops).
--hide GLOB    oculta objetos cujo nome bate (fnmatch), ex.: --hide "Roof*" --hide "Ceiling*"
"""
import argparse
import fnmatch
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")


def _camera(scene, fov_deg):
    cam = scene.objects.get("_PreviewCam")
    if cam is None:
        data = bpy.data.cameras.new("_PreviewCam")
        cam = bpy.data.objects.new("_PreviewCam", data)
        scene.collection.objects.link(cam)
    cam.data.angle = math.radians(fov_deg)
    cam.data.clip_start = 0.05
    cam.data.clip_end = 300
    scene.camera = cam
    return cam


def _apply_fill(scene, strength):
    world = scene.world or bpy.data.worlds.new("_PreviewWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is None:
        bg = world.node_tree.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = strength


def set_engine(scene, engine, samples):
    engine = engine.lower()
    if engine == "workbench":
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"
    elif engine == "cycles":
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = False
    else:
        from sem_alvorada import compat
        compat.use_eevee(scene)


def render_views(scene, views, out_prefix, engine="cycles", res=(640, 360), samples=24,
                 fill=0.0, exposure=0.0, fov=72.0, hide=()):
    """Renderiza cada vista para <out_prefix>_<nome>.png e devolve a lista de caminhos."""
    os.makedirs(os.path.dirname(os.path.abspath(out_prefix)) or ".", exist_ok=True)
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    set_engine(scene, engine, samples)
    scene.view_settings.exposure = exposure
    if fill > 0:
        _apply_fill(scene, fill)
    hidden = []
    for pat in hide:
        for ob in scene.objects:
            if fnmatch.fnmatch(ob.name, pat) and not ob.hide_render:
                ob.hide_render = True
                hidden.append(ob)
    cam = _camera(scene, fov)
    paths = []
    for name, (x, y, z), yaw_deg, pitch_deg in views:
        cam.location = (x, y, z)
        cam.rotation_euler = (math.radians(90 + pitch_deg), 0, math.radians(yaw_deg))
        path = f"{out_prefix}_{name}.png"
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        paths.append(path)
        print(f"[preview] {path}", flush=True)
    for ob in hidden:
        ob.hide_render = False
    return paths


def parse_view(text):
    name, _, vals = text.partition(":")
    x, y, z, yaw, pitch = [float(v) for v in vals.split(",")]
    return (name, (x, y, z), yaw, pitch)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blend", help=".blend a abrir (padrão: cena vazia)")
    ap.add_argument("--out", default="out/prev")
    ap.add_argument("--view", action="append", default=[], help="nome:x,y,z,yaw,pitch")
    ap.add_argument("--engine", default="cycles", choices=["workbench", "cycles", "eevee"])
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--fill", type=float, default=0.0)
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--fov", type=float, default=72.0)
    ap.add_argument("--hide", action="append", default=[])
    a = ap.parse_args(argv)
    if a.blend:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    res = tuple(int(v) for v in a.res.lower().split("x"))
    views = [parse_view(v) for v in a.view]
    if not views:
        views = [("padrao", (6.5, 1.0, 1.65), 0.0, 0.0)]
    render_views(bpy.context.scene, views, a.out, a.engine, res, a.samples, a.fill,
                 a.exposure, a.fov, a.hide)


if __name__ == "__main__":
    main()
