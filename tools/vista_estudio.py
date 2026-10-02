"""Vista de estúdio do exterior: Cycles com céu uniforme e um sol de apoio, sem as luzes do jogo.

No jogo o lado de fora é quase preto de propósito (o sol sumiu), então ele não serve para julgar forma e
material. Aqui o mundo é neutro. Não representa o que o jogador vê; representa o modelo.

    python tools/vista_estudio.py --blend out/estado.blend --out out/estudio/rua \
        --view "fachada:6,-16,2,0,5" --sky 0.6 --sun 2.5 --samples 16 --res 640x360

Cada --view é nome:x,y,z,yaw,pitch (yaw 0 olha para +Y; yaw negativo gira para +X).
"""
import argparse
import fnmatch
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
import bpy  # noqa: E402


def neutral_world(scene, strength, tint):
    world = bpy.data.worlds.new("_lit_world")
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()
    bg = tree.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (*tint, 1.0)
    bg.inputs["Strength"].default_value = strength
    out = tree.nodes.new("ShaderNodeOutputWorld")
    tree.links.new(bg.outputs["Background"], out.inputs["Surface"])
    scene.world = world


def add_sun(scene, energy, yaw, pitch):
    data = bpy.data.lights.new("_lit_sun", "SUN")
    data.energy = energy
    data.angle = math.radians(8)
    sun = bpy.data.objects.new("_lit_sun", data)
    sun.rotation_euler = (math.radians(pitch), 0, math.radians(yaw))
    scene.collection.objects.link(sun)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--view", action="append", default=[])
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--sky", type=float, default=0.5)
    ap.add_argument("--sun", type=float, default=2.0)
    ap.add_argument("--sun-yaw", type=float, default=35)
    ap.add_argument("--sun-pitch", type=float, default=55)
    ap.add_argument("--fov", type=float, default=60)
    ap.add_argument("--hide", action="append", default=[])
    ap.add_argument("--keep-lights", action="store_true")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    scene = bpy.context.scene
    res = tuple(int(v) for v in a.res.lower().split("x"))
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = a.samples
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    neutral_world(scene, a.sky, (0.75, 0.80, 0.9))
    add_sun(scene, a.sun, a.sun_yaw, a.sun_pitch)
    for ob in scene.objects:
        if ob.type == "LIGHT" and not ob.name.startswith("_lit") and not a.keep_lights:
            ob.hide_render = True
        if any(fnmatch.fnmatch(ob.name, p) for p in a.hide):
            ob.hide_render = True
    for name in ("FogBox_House", "FogBox_Garage"):
        if name in scene.objects:
            scene.objects[name].hide_render = True
    cam_data = bpy.data.cameras.new("_lit_cam")
    cam = bpy.data.objects.new("_lit_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.angle = math.radians(a.fov)
    cam_data.clip_start, cam_data.clip_end = 0.05, 400
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    for text in a.view:
        name, _, vals = text.partition(":")
        x, y, z, yaw, pitch = [float(v) for v in vals.split(",")]
        cam.location = (x, y, z)
        cam.rotation_euler = (math.radians(90 + pitch), 0, math.radians(yaw))
        scene.render.filepath = f"{a.out}_{name}.png"
        bpy.ops.render.render(write_still=True)
        print("[lit]", scene.render.filepath, flush=True)


if __name__ == "__main__":
    main()
