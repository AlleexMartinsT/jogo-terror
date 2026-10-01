"""Ferramenta de desenvolvimento: estúdio de renderização e folhas de contato do Alto.

    python -m sem_alvorada.entity.sheet views      # frente, perfil e close do rosto
    python -m sem_alvorada.entity.sheet anims      # uma faixa de poses por animação

Não é usada no jogo. Escreve em out/entity/.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

OUT_DIR = os.path.join(ROOT, "out", "entity")
DOOR_HEIGHT = 2.05


def _new_object(name, datablock, scene):
    obj = bpy.data.objects.new(name, datablock)
    scene.collection.objects.link(obj)
    return obj


def _box(scene, name, size, location, color):
    mesh = bpy.data.meshes.new(name)
    sx, sy, sz = (v / 2 for v in size)
    verts = [(x, y, z) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh.from_pydata(verts, [], faces)
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*color, 1.0)
    mesh.materials.append(mat)
    obj = _new_object(name, mesh, scene)
    obj.location = location
    return obj


def _light(scene, name, kind, energy, location, target, color=(1, 1, 1), size=None):
    light = bpy.data.lights.new(name, kind)
    light.energy = energy
    light.color = color
    if kind == "SPOT":
        light.spot_size = math.radians(70)
        light.spot_blend = 0.6
    if size is not None:
        light.shadow_soft_size = size
    obj = _new_object(name, light, scene)
    obj.location = location
    direction = Vector(target) - Vector(location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


def build_studio(scene, with_door=True):
    """Chão escuro, uma porta de 2,05 m como régua, luz fria de lado e contraluz."""
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = False
    world = bpy.data.worlds.new("Studio") if scene.world is None else scene.world
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.005, 0.007, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    _box(scene, "StudioFloor", (12, 12, 0.05), (0, 0, -0.025), (0.06, 0.06, 0.065))
    _box(scene, "StudioWall", (12, 0.1, 5), (0, -2.6, 2.5), (0.07, 0.065, 0.06))
    if with_door:
        _box(scene, "DoorRuler", (0.9, 0.06, DOOR_HEIGHT), (-1.3, 0.3, DOOR_HEIGHT / 2), (0.25, 0.2, 0.14))
    _light(scene, "Key", "SPOT", 1500, (-2.2, 3.6, 3.4), (0, 0, 1.4), (0.75, 0.85, 1.0), 0.3)
    _light(scene, "Rim", "SPOT", 1200, (1.8, -2.0, 3.2), (0, 0, 1.6), (1.0, 0.9, 0.8), 0.2)
    _light(scene, "Fill", "POINT", 90, (2.2, 2.6, 1.0), (0, 0, 1.0), (0.6, 0.7, 1.0), 0.5)
    _light(scene, "SideKey", "SPOT", 1300, (4.2, 1.2, 3.2), (0, 0, 1.4), (0.8, 0.85, 1.0), 0.3)
    camera_data = bpy.data.cameras.new("StudioCam")
    camera_data.sensor_fit = "HORIZONTAL"
    camera_data.clip_start = 0.02
    cam = _new_object("StudioCam", camera_data, scene)
    scene.camera = cam
    return cam


def aim_camera(cam, position, target, fov_deg=40.0):
    cam.location = position
    cam.data.angle = math.radians(fov_deg)
    cam.rotation_euler = (Vector(target) - Vector(position)).to_track_quat("-Z", "Y").to_euler()


def render(scene, path, res=(320, 480), samples=12):
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.cycles.samples = samples
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def load_pixels(path):
    image = bpy.data.images.load(path)
    width, height = image.size
    pixels = np.empty(width * height * 4, np.float32)
    image.pixels.foreach_get(pixels)
    bpy.data.images.remove(image)
    return pixels.reshape(height, width, 4)[::-1, :, :3]        # linha 0 = topo


def save_png(path, rgb_float):
    from tools import pngwrite
    srgb = np.clip(rgb_float, 0, 1)
    pngwrite.write_png(path, (srgb * 255).astype(np.uint8))


_GLYPHS = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01111 10000 10000 10000 10000 10000 01111", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01111 10000 10000 10011 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "J": "00111 00010 00010 00010 00010 10010 01100", "Q": "01110 10001 10001 10001 10101 10010 01101",
    ",": "00000 00000 00000 00000 01100 00100 01000", "?": "01110 10001 00001 00110 00100 00000 00100",
    "!": "00100 00100 00100 00100 00100 00000 00100", "(": "00010 00100 01000 01000 01000 00100 00010",
    ")": "01000 00100 00010 00010 00010 00100 01000", "'": "00100 00100 01000 00000 00000 00000 00000",
    "I": "11111 00100 00100 00100 00100 00100 11111", "K": "10001 10010 10100 11000 10100 10010 10001",
    "L": "10000 10000 10000 10000 10000 10000 11111", "M": "10001 11011 10101 10101 10001 10001 10001",
    "N": "10001 11001 10101 10011 10001 10001 10001", "O": "01110 10001 10001 10001 10001 10001 01110",
    "P": "11110 10001 10001 11110 10000 10000 10000", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 11011 10001", "X": "10001 01010 00100 00100 00100 01010 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10011 10101 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00110 01000 10000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "01110 10000 11110 10001 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00001 01110",
    ".": "00000 00000 00000 00000 00000 01100 01100", "=": "00000 00000 11111 00000 11111 00000 00000",
    "-": "00000 00000 00000 11111 00000 00000 00000", " ": "00000 00000 00000 00000 00000 00000 00000",
    "_": "00000 00000 00000 00000 00000 00000 11111", ":": "00000 01100 01100 00000 01100 01100 00000",
}


def draw_text(image, text, x, y, scale=2, color=(1, 1, 0.6)):
    """Escreve `text` (maiúsculas, dígitos e pontuação básica) com uma fonte 5x7 embutida."""
    cursor = x
    for char in text.upper():
        glyph = _GLYPHS.get(char, _GLYPHS[" "]).split()
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    y0, x0 = y + row * scale, cursor + col * scale
                    image[y0:y0 + scale, x0:x0 + scale] = color
        cursor += 6 * scale


def contact_sheet(tiles, columns, labels=None, pad=4):
    """Junta imagens (h, w, 3) do mesmo tamanho numa grade; `labels` são escritos no canto de cada uma."""
    height, width = tiles[0].shape[:2]
    rows = math.ceil(len(tiles) / columns)
    sheet = np.zeros((rows * (height + pad) + pad, columns * (width + pad) + pad, 3), np.float32)
    for index, tile in enumerate(tiles):
        r, c = divmod(index, columns)
        y, x = pad + r * (height + pad), pad + c * (width + pad)
        sheet[y:y + height, x:x + width] = tile
        if labels:
            draw_text(sheet, labels[index], x + 4, y + 4, scale=2)
    return sheet


def fresh_studio_scene():
    from sem_alvorada import build
    scene = build.fresh_scene()
    build_studio(scene)
    return scene


def build_entity_in(scene):
    from sem_alvorada.buildctx import BuildContext
    from sem_alvorada import entity
    ctx = BuildContext(scene, verbose=False)
    entity.build(ctx)
    return scene


def demo_views():
    """Frente, perfil, três-quartos e close do rosto (pose de repouso ou a pose atual da rig)."""
    scene = fresh_studio_scene()
    build_entity_in(scene)
    from sem_alvorada.entity.rig import EntityRig
    rig = EntityRig(scene)
    rig.set_transform(0.0, 0.0, 0.0, 0.0)
    rig.set_visible(True)
    rig.set_anim("idle")
    for _ in range(90):
        rig.update(1 / 60, 0.0)
    rig.eyes(1.0)
    cam = scene.camera
    views = {
        "front": ((0.0, 6.2, 1.5), (0, 0, 1.3), 34),
        "side": ((6.2, 0.0, 1.5), (0, 0, 1.3), 34),
        "threeq": ((-3.6, 4.6, 1.8), (0, 0, 1.3), 34),
        "face": (None, None, 30),
    }
    tiles, labels = [], []
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, (pos, target, fov) in views.items():
        if pos is None:                                   # close do rosto: segue a cabeça da rig
            head = Vector(rig.head_position())
            pos, target = (head.x, head.y + 1.05, head.z + 0.03), tuple(head)
        aim_camera(cam, pos, target, fov)
        path = render(scene, os.path.join(OUT_DIR, f"view_{name}.png"), (360, 540) if name != "face" else (360, 540), 24)
        tiles.append(load_pixels(path))
        labels.append(name)
    save_png(os.path.join(OUT_DIR, "views_sheet.png"), contact_sheet(tiles, 4, labels))
    torch_views(scene, rig)


def torch_views(scene, rig):
    """Como o jogador vê: escuro total e só a lanterna (spot na câmera) a 5 m, 3 m e 1,6 m do rosto."""
    for name in ("Key", "Rim", "Fill", "SideKey"):
        scene.objects[name].data.energy = 0.0
    torch = _light(scene, "Torch", "SPOT", 1400, (0, 0, 0), (0, 1, 0), (1.0, 0.93, 0.8), 0.05)
    torch.data.spot_size = math.radians(48)
    torch.data.spot_blend = 0.25
    cam = scene.camera
    tiles, labels = [], []
    for name, (pos, target, fov) in {"torch5m": ((0.3, 5.2, 1.65), (0, 0, 1.4), 72),
                                     "torch3m": ((0.2, 3.2, 1.65), (0, 0, 1.9), 72),
                                     "torch1m": ((0.15, 1.6, 1.65), (0, 0, 2.3), 72)}.items():
        aim_camera(cam, pos, target, fov)
        torch.location = pos
        torch.rotation_euler = cam.rotation_euler
        path = render(scene, os.path.join(OUT_DIR, f"view_{name}.png"), (480, 270), 32)
        tiles.append(load_pixels(path))
        labels.append(name)
    save_png(os.path.join(OUT_DIR, "torch_sheet.png"), contact_sheet(tiles, 3, labels))


# nome -> (instantes em segundos desde set_anim, velocidade, ponto para olhar)
ANIM_SAMPLES = {
    "idle": ((0.5, 1.7, 2.9, 4.1, 5.3, 6.5), None, None),
    "stare": ((0.5, 1.5, 2.5, 3.5, 4.5, 5.5), None, (3.0, 3.0, 1.6)),
    "walk": ((1.0, 1.15, 1.30, 1.45, 1.60, 1.75), None, None),
    "stalk": ((1.0, 1.2, 1.4, 1.6, 1.8, 2.0), None, None),
    "run": ((1.0, 1.08, 1.16, 1.24, 1.32, 1.40), None, None),
    "attack": ((0.05, 0.15, 0.25, 0.35, 0.6, 1.2), 0.0, None),
    "twitch": ((0.5, 0.62, 0.74, 0.86, 0.98, 1.10), 0.0, None),
    "appear": ((0.2, 0.7, 1.2, 1.8, 2.4, 3.2), 0.0, None),
}


def anim_strip(name, samples=None, size=(260, 440), samples_per_pixel=14):
    """Renderiza a mesma animação em vários instantes, de frente (linha 1) e de perfil (linha 2)."""
    times, speed, look = samples or ANIM_SAMPLES[name]
    scene = fresh_studio_scene()
    build_entity_in(scene)
    from sem_alvorada.entity.rig import EntityRig
    rig = EntityRig(scene)
    rig.set_visible(True)
    rig.eyes(1.0)
    rig.set_transform(0.0, 0.0, 0.0, 0.0)
    rig.set_anim(name)
    if look:
        rig.look_at(*look)
    cameras = (((0.0, 5.6, 1.4), (0, 0, 1.3), 34), ((5.6, 0.0, 1.4), (0, 0, 1.3), 34))
    frames = {view: [] for view in range(len(cameras))}
    clock = 0.0
    for stamp in times:
        while clock < stamp:
            rig.update(1 / 60, speed)
            clock += 1 / 60
        bpy.context.view_layer.update()
        for view, (pos, target, fov) in enumerate(cameras):
            aim_camera(scene.camera, pos, target, fov)
            path = render(scene, os.path.join(OUT_DIR, "_tmp.png"), size, samples_per_pixel)
            frames[view].append(load_pixels(path))
    tiles = frames[0] + frames[1]
    labels = [f"{name} {stamp:.2f}" for stamp in times] * 2
    sheet = contact_sheet(tiles, len(times), labels)
    out = os.path.join(OUT_DIR, f"anim_{name}.png")
    save_png(out, sheet)
    return out


def combine_strips(names=None):
    """Junta a linha de frente (metade de cima) de cada faixa `anim_<nome>.png` numa folha só, reduzida à metade."""
    rows = []
    for name in (names or ANIM_SAMPLES):
        strip = load_pixels(os.path.join(OUT_DIR, f"anim_{name}.png"))
        top = strip[: strip.shape[0] // 2]
        rows.append(0.25 * (top[0::2, 0::2] + top[1::2, 0::2] + top[0::2, 1::2] + top[1::2, 1::2]))
    width = min(row.shape[1] for row in rows)
    out = os.path.join(OUT_DIR, "contact_sheet.png")
    save_png(out, np.concatenate([row[:, :width] for row in rows], axis=0))
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "views"
    os.makedirs(OUT_DIR, exist_ok=True)
    if mode == "views":
        demo_views()
    elif mode == "anims":
        for anim in (sys.argv[2:] or ANIM_SAMPLES):
            print(anim_strip(anim))
        if not sys.argv[2:]:
            print(combine_strips())
    elif mode == "combine":
        print(combine_strips())
