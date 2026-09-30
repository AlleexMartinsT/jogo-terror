"""Ferramenta de desenvolvimento: renderiza quadros de uma cutscene num .blend real.

    python -m sem_alvorada.cutscenes.preview --blend out/cutscenes/full.blend --cutscene intro \
        --exposure 1.5 --samples 32

Um `PreviewHost` simples faz o papel do engine (luzes, portas, lanterna, entidade). O player roda de
verdade, a câmera `CutsceneCam` é renderizada com Cycles e o overlay (fade, letterbox, legenda, flash,
cartão) é composto por cima em numpy. Saída: out/cutscenes/<nome>_<n>.png e <nome>_sheet.png.
"""
import argparse
import math
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.cutscenes import scripts, timeline  # noqa: E402
from sem_alvorada.cutscenes.player import CutscenePlayer  # noqa: E402

OUT_DIR = os.path.join(ROOT, "out", "cutscenes")
FLASHLIGHT_ENERGY = C.FLASH_ENERGY

# estado do mundo no INÍCIO de cada cutscene (o engine decide isso no jogo de verdade)
START_STATE = {
    "intro": {"power": False, "flashlight": False, "player": (*layout.PLAYER_START[:3], 0.0)},
    "blackout": {"power": True, "flashlight": True, "player": (5.6, 8.65, 2.8, math.radians(-90))},
    "garage_unlock": {"power": False, "flashlight": True, "player": (11.1, 5.85, 0.0, math.radians(-90))},
    "death": {"power": False, "flashlight": True, "player": (6.6, 5.2, 2.8, 0.0)},
    "ending": {"power": False, "flashlight": False, "player": (16.5, 3.6, 0.0, math.radians(90))},
}


class RecordingAudio:
    def __init__(self):
        self.log = []

    def play(self, name, pos=None, volume=1.0, pitch=1.0):
        self.log.append(("play", name))

    def loop(self, key, name, pos=None, volume=1.0, pitch=1.0):
        self.log.append(("loop", name))

    def stop(self, key):
        self.log.append(("stop", key))


class PreviewDoors:
    def __init__(self, scene):
        self.scene = scene

    def snap(self, door_id, openness):
        pivot = self.scene.objects.get(C.N_DOOR + door_id)
        if pivot is None:
            return
        closed, opened = pivot[C.P_DOOR_CLOSED], pivot[C.P_DOOR_OPEN]
        pivot.rotation_euler.z = closed + (opened - closed) * openness

    set_openness = snap


class PreviewHost:
    """Um engine de mentira: só o suficiente para as cutscenes acontecerem numa cena real."""

    def __init__(self, scene, start):
        self.scene = scene
        self.audio = RecordingAudio()
        self.doors = PreviewDoors(scene)
        self.entity = self._entity()
        self.state = start["player"]
        self.finished = []
        self._lights = [(o, o.get(C.P_LIGHT_ENERGY, o.data.energy)) for o in scene.objects
                        if o.type == "LIGHT" and o.name.startswith(C.N_LIGHT)]
        self._flashlight = self._make_flashlight()
        self.set_power(start["power"])
        self.set_flashlight(start["flashlight"])

    def _entity(self):
        from sem_alvorada.entity.rig import EntityRig
        return EntityRig(self.scene)

    def _make_flashlight(self):
        data = bpy.data.lights.new("PreviewFlashlight", "SPOT")
        data.spot_size = math.radians(C.FLASH_SPOT_DEG)
        data.spot_blend = 0.25
        data.energy = 0.0
        data.color = (1.0, 0.93, 0.8)
        obj = bpy.data.objects.new("PreviewFlashlight", data)
        self.scene.collection.objects.link(obj)
        cam = self.scene.objects.get(C.OBJ_CUT_CAM)
        if cam is not None:
            obj.parent = cam
        return obj

    def set_camera(self, obj):
        self.scene.camera = obj or self.scene.objects.get(C.OBJ_PLAYER_CAM) or self.scene.camera

    def get_object(self, name):
        return self.scene.objects.get(name)

    def player_state(self):
        x, y, z, yaw = self.state
        return (x, y, z, yaw, z + C.PLAYER_EYE_STAND)

    def place_player(self, x, y, z, yaw):
        self.state = (x, y, z, yaw)

    def set_power(self, on, flicker=0.0):
        factor = (0.55 if flicker else 1.0) if on else 0.0
        for obj, base in self._lights:
            obj.data.energy = base * factor

    def flash_light(self, seconds):
        pass

    def set_flashlight(self, on):
        self._flashlight.data.energy = FLASHLIGHT_ENERGY if on else 0.0

    def noise_silence(self, seconds):
        pass

    def entity_brain_activate(self):
        pass

    def finish(self, reason):
        self.finished.append(reason)


# --------------------------------------------------------------------------
# Composição do overlay em numpy
# --------------------------------------------------------------------------
def _ascii(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def compose_overlay(image, overlay, label=""):
    """Aplica fade, flash, letterbox, legenda e cartão a `image` (h, w, 3 float)."""
    from sem_alvorada.entity import sheet
    out = np.clip(image * (1.0 - overlay.fade), 0.0, 1.0)
    out = out * (1.0 - overlay.flash) + overlay.flash
    height, width = out.shape[:2]
    bar = int(overlay.letterbox * height * 0.11)
    if bar:
        out[:bar] = 0.0
        out[height - bar:] = 0.0
    if overlay.subtitle and overlay.subtitle_alpha > 0.02:
        text = _ascii(overlay.subtitle)
        scale = 2
        max_chars = max(10, width // (6 * scale) - 2)
        lines, current = [], ""
        for word in text.split():
            if len(current) + len(word) + 1 > max_chars:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        lines.append(current)
        y = height - bar - 12 - len(lines) * 9 * scale
        for line in lines:
            x = max(4, (width - len(line) * 6 * scale) // 2)
            sheet.draw_text(out, line, x, y, scale=scale, color=(0.9, 0.87, 0.7) if overlay.subtitle_alpha > 0.6 else (0.4, 0.38, 0.3))
            y += 9 * scale
    if overlay.card:
        for i, line in enumerate(overlay.card):
            text = _ascii(line)
            x = max(4, (width - len(text) * 12) // 2)
            sheet.draw_text(out, text, x, height // 2 - 20 + i * 24, scale=2, color=(0.85, 0.82, 0.7))
    if label:
        sheet.draw_text(out, label, 4, 4, scale=1, color=(0.5, 1.0, 0.5))
    return out


def setup_cycles(scene, res, samples, exposure):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    scene.cycles.max_bounces = 4
    scene.render.threads = 2
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.exposure = exposure


def default_times(name):
    tl = timeline.compile_cutscene(scripts.get(name))
    return [t0 + (t1 - t0) * fraction for t0, t1, _ in tl.shots for fraction in (0.5,)]


def render_frames(scene, name, times, res=(640, 360), samples=32, exposure=0.0, out_dir=OUT_DIR):
    from sem_alvorada.entity import sheet
    os.makedirs(out_dir, exist_ok=True)
    setup_cycles(scene, res, samples, exposure)
    host = PreviewHost(scene, START_STATE[name])
    player = CutscenePlayer(host)
    player.play(name)
    tiles, labels = [], []
    for index, target in enumerate(sorted(times)):
        while player.active and player.time < target - 1e-6:
            player.update(min(1 / 30, target - player.time))
        if not player.active:
            break
        overlay = player.overlay()
        path = os.path.join(out_dir, f"{name}_{index:02d}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        frame = compose_overlay(sheet.load_pixels(path), overlay)
        sheet.save_png(path, frame)
        tiles.append(frame)
        labels.append(f"{name} {player.time:5.1f}S")
        print(f"[cutscene] {path} (t={player.time:.1f}s, fade={overlay.fade:.2f}) erros={player.errors}", flush=True)
    if tiles:
        columns = 3
        sheet.save_png(os.path.join(out_dir, f"{name}_sheet.png"), sheet.contact_sheet(tiles, columns, labels))
    return host


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(OUT_DIR, "full.blend"))
    ap.add_argument("--cutscene", required=True, choices=scripts.NAMES)
    ap.add_argument("--times", default="", help="segundos separados por vírgula (padrão: meio de cada plano)")
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--exposure", type=float, default=0.0)
    args = ap.parse_args(argv)
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    times = [float(t) for t in args.times.split(",")] if args.times else default_times(args.cutscene)
    res = tuple(int(v) for v in args.res.lower().split("x"))
    render_frames(bpy.context.scene, args.cutscene, times, res, args.samples, args.exposure)


if __name__ == "__main__":
    main()
