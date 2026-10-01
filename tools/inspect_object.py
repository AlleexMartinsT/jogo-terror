"""Folha de inspeção: renderiza um objeto isolado, com luz de estúdio, em vários ângulos.

    python tools/inspect_object.py --blend out/x.blend --out out/meu_modulo/inspecao Car "bed_*" Item_KEY

Cada argumento posicional é um nome de objeto ou padrão fnmatch; o objeto e seus filhos entram
juntos. Gera <out>/<nome>.png com os ângulos pedidos lado a lado (padrão: 3q, frente, lado).

Serve para julgar o acabamento de PERTO, longe do escuro da casa: silhueta, chanfros, proporção,
detalhes. Se o objeto só funciona no escuro, ele não está pronto.

Ângulos: 3q (três quartos), frente, lado, costas, topo, detalhe (câmera bem próxima, 3q).
"""
import argparse
import fnmatch
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from tools import pngwrite  # noqa: E402

VIEWS = {
    "3q": (35.0, 22.0, 1.0),
    "frente": (0.0, 6.0, 1.0),
    "lado": (90.0, 6.0, 1.0),
    "costas": (180.0, 10.0, 1.0),
    "topo": (0.0, 80.0, 1.0),
    "detalhe": (30.0, 18.0, 0.55),
}


def family(obj):
    yield obj
    for child in obj.children_recursive:
        yield child


def world_bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    found = False
    for obj in objs:
        if obj.type != "MESH" or not obj.data.vertices:
            continue
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            lo = Vector((min(lo[i], point[i]) for i in range(3)))
            hi = Vector((max(hi[i], point[i]) for i in range(3)))
            found = True
    return (lo, hi) if found else (None, None)


def set_look(camera, target, yaw_deg, pitch_deg, distance):
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    # a frente do objeto é +Y local; a câmera olha de -Y (yaw 0) para a frente dele
    offset = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch))) * distance
    camera.location = target + offset
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def build_stage(scene, lo, hi):
    """Chão neutro e luz de três pontos ao redor do objeto."""
    center = (lo + hi) / 2
    size = max((hi - lo).length, 0.3)
    world = bpy.data.worlds.new("_inspect_world")
    world.use_nodes = True
    background = world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (0.20, 0.21, 0.23, 1)
    background.inputs["Strength"].default_value = 0.35
    scene.world = world
    bpy.ops.mesh.primitive_plane_add(size=size * 6, location=(center.x, center.y, lo.z - 0.002))
    floor = bpy.context.object
    floor.name = "_inspect_floor"
    material = bpy.data.materials.new("_inspect_floor_mat")
    material.use_nodes = True
    bsdf = material.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.16, 0.16, 0.17, 1)
    bsdf.inputs["Roughness"].default_value = 0.9
    floor.data.materials.append(material)
    for name, where, energy in (("key", (1.6, -2.2, 2.4), 150), ("fill", (-2.4, -1.4, 1.2), 50), ("rim", (0.4, 2.6, 2.2), 110)):
        data = bpy.data.lights.new(f"_inspect_{name}", "AREA")
        data.energy = energy * size * size
        data.size = size * 1.2
        light = bpy.data.objects.new(f"_inspect_{name}", data)
        light.location = center + Vector(where) * size * 0.8
        direction = center - light.location
        light.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(light)


def render_sheet(scene, label, targets, views, res, samples, out_dir):
    lo, hi = world_bounds(targets)
    if lo is None:
        print(f"[inspecionar] {label}: sem malha", flush=True)
        return None
    center = (lo + hi) / 2
    diag = (hi - lo).length
    camera = scene.camera
    fov = camera.data.angle
    base = (diag / 2) / math.tan(fov / 2) * 0.95
    frames = []
    for view in views:
        yaw, pitch, zoom = VIEWS[view]
        set_look(camera, center, yaw, pitch, base * zoom)
        path = os.path.join(out_dir, f"_frame_{view}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(path)
        pixels = np.empty(res[0] * res[1] * 4, np.float32)
        image.pixels.foreach_get(pixels)
        bpy.data.images.remove(image)
        frames.append(pixels.reshape(res[1], res[0], 4)[..., :3])
        os.remove(path)
    sheet = np.concatenate(frames, axis=1)
    out = (np.clip(np.flipud(sheet), 0, 1) * 255).astype(np.uint8)
    safe = label.replace("/", "_").replace(" ", "_")
    path = os.path.join(out_dir, f"{safe}.png")
    pngwrite.write_png(path, out)
    print(f"[inspecionar] {path}", flush=True)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("objetos", nargs="+")
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", default="out/inspecao")
    parser.add_argument("--views", default="3q,frente,lado")
    parser.add_argument("--res", default="480x480")
    parser.add_argument("--samples", type=int, default=32)
    args = parser.parse_args(argv)

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    scene = bpy.context.scene
    res = tuple(int(v) for v in args.res.lower().split("x"))
    views = [v.strip() for v in args.views.split(",")]
    os.makedirs(args.out, exist_ok=True)

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"

    selected = []
    for pattern in args.objetos:
        selected += [o for o in scene.objects if fnmatch.fnmatch(o.name, pattern) and o.parent is None] or \
                    [o for o in scene.objects if fnmatch.fnmatch(o.name, pattern)]
    if not selected:
        print("[inspecionar] nenhum objeto casou com", args.objetos, flush=True)
        return 1

    camera_data = bpy.data.cameras.new("_inspect_cam")
    camera_data.lens = 50
    camera = bpy.data.objects.new("_inspect_cam", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.clip_start, camera_data.clip_end = 0.02, 200

    hidden = []
    for obj in scene.objects:
        if obj.type == "LIGHT" or obj.name.startswith("_inspect"):
            continue
        obj.hide_render = True
        hidden.append(obj)
    for light in [o for o in scene.objects if o.type == "LIGHT"]:
        light.hide_render = True

    done = set()
    for obj in selected:
        if obj.name in done:
            continue
        group = list(family(obj))
        done.update(o.name for o in group)
        for member in group:
            member.hide_render = False
        lo, hi = world_bounds(group)
        if lo is None:
            continue
        # palco novo para cada objeto (centrado nele)
        for stale in [o for o in scene.objects if o.name.startswith("_inspect_") and o.name != "_inspect_cam"]:
            bpy.data.objects.remove(stale, do_unlink=True)
        build_stage(scene, lo, hi)
        render_sheet(scene, obj.name, group, views, res, args.samples, args.out)
        for member in group:
            member.hide_render = True
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None))
