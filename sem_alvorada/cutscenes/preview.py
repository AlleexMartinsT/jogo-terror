"""Ferramenta de desenvolvimento: renderiza quadros de uma cutscene num .blend real.

    python -m sem_alvorada.cutscenes.preview --blend out/f3_4/base.blend --cutscene intro \
        --times 2,8,20 --res 640x360 --samples 12 --out out/f3_4/intro

Um `PreviewHost` simples faz o papel do engine (luzes, portas, lanterna, entidade). O player roda de
verdade, a câmera `CutsceneCam` é renderizada com Cycles e o overlay (fade, letterbox, legenda, flash,
cartão) é composto por cima em numpy. Saída: <out>/<nome>_<n>.png e <nome>_sheet.png.

`--rebuild` recria câmera, luzes, pálpebras, poeira, chave e as peças do carro sobre um .blend já montado,
sem refazer o build de 2 minutos.
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
from mathutils import Vector  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.cutscenes import scripts, timeline  # noqa: E402
from sem_alvorada.cutscenes.player import CutscenePlayer  # noqa: E402
from sem_alvorada.engine.fallbacks import NullBody  # noqa: E402

OUT_DIR = os.path.join(ROOT, "out", "cutscenes")
DEFAULT_BLEND = os.path.join(ROOT, "out", "f3_4", "base.blend")
FLASHLIGHT_ENERGY = C.FLASH_ENERGY
STEP = 1 / 30

# estado do mundo no INÍCIO de cada cutscene (o engine decide isso no jogo de verdade)
START_STATE = {
    "intro": {"power": False, "flashlight": False, "player": (*layout.PLAYER_START[:3], 0.0)},
    "blackout": {"power": True, "flashlight": True, "player": (5.6, 3.4, 2.8, math.radians(0))},
    "garage_unlock": {"power": False, "flashlight": True, "player": (11.1, 5.85, 0.0, math.radians(-90)),
                      "pitch": math.radians(-4)},
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
    """Portas de mentira: `set_openness` anima com a mesma curva mínima-sacudida (quíntica) das portas do jogo."""

    def __init__(self, scene):
        self.scene = scene
        self.glides = {}                    # id -> [início, destino, duração, decorrido]

    def _write(self, door_id, openness):
        pivot = self.scene.objects.get(C.N_DOOR + door_id)
        if pivot is None:
            return
        closed, opened = pivot[C.P_DOOR_CLOSED], pivot[C.P_DOOR_OPEN]
        pivot.rotation_euler.z = closed + (opened - closed) * openness

    def snap(self, door_id, openness):
        self.glides.pop(door_id, None)
        self._write(door_id, openness)

    def set_openness(self, door_id, fraction, speed=None):
        pivot = self.scene.objects.get(C.N_DOOR + door_id)
        if pivot is None:
            return
        closed, opened = pivot[C.P_DOOR_CLOSED], pivot[C.P_DOOR_OPEN]
        now = (pivot.rotation_euler.z - closed) / ((opened - closed) or 1.0)
        seconds = abs(fraction - now) / speed if speed else 1.3
        self.glides[door_id] = [now, fraction, max(seconds, 0.2), 0.0]

    def update(self, dt):
        for door_id, glide in list(self.glides.items()):
            glide[3] = min(glide[3] + dt, glide[2])
            u = glide[3] / glide[2]
            self._write(door_id, glide[0] + (glide[1] - glide[0]) * (u ** 3 * (u * (u * 6 - 15) + 10)))
            if glide[3] >= glide[2]:
                del self.glides[door_id]


class PreviewHost:
    """Um engine de mentira: só o suficiente para as cutscenes acontecerem numa cena real."""

    def __init__(self, scene, start):
        self.scene = scene
        self.audio = RecordingAudio()
        self.doors = PreviewDoors(scene)
        self.entity = self._entity()
        self.body = self._body()
        self.state = start["player"]
        self._pitch = start.get("pitch", 0.0)
        self.finished = []
        self._flash_on = False
        self.power = start["power"]
        self.gains = {}
        self._lights = [(o, o.get(C.P_LIGHT_ENERGY, o.data.energy)) for o in scene.objects
                        if o.type == "LIGHT" and o.name.startswith(C.N_LIGHT)]
        self._flashlight = scene.objects.get(C.OBJ_FLASHLIGHT) or self._make_flashlight()
        self._player_cam = scene.objects.get(C.OBJ_PLAYER_CAM)
        self._aim_flashlight()
        self.set_power(start["power"])
        self.set_flashlight(start["flashlight"])
        self.brain_calls = []

    def _entity(self):
        from sem_alvorada.entity.rig import EntityRig
        return EntityRig(self.scene)

    def _body(self):
        """O corpo de verdade se o .blend o tem (como o `Game`); senão o NullBody."""
        try:
            from sem_alvorada.body import BodyRig
            return BodyRig(self.scene)
        except Exception:                                   # noqa: BLE001
            return NullBody()

    def _make_flashlight(self):
        light_data = bpy.data.lights.new("PreviewFlashlight", "SPOT")
        light_data.spot_size = math.radians(C.FLASH_SPOT_DEG)
        light_data.spot_blend = 0.25
        light_data.energy = 0.0
        light_data.color = (1.0, 0.93, 0.8)
        obj = bpy.data.objects.new("PreviewFlashlight", light_data)
        self.scene.collection.objects.link(obj)
        return obj

    def _aim_flashlight(self):
        """A PlayerCam (pai da lanterna) fica nos olhos do jogador, como no jogo."""
        x, y, z, yaw = self.state
        if self._player_cam is not None:
            self._player_cam.rotation_mode = "XYZ"
            self._player_cam.location = (x, y, z + C.PLAYER_EYE_STAND)
            self._player_cam.rotation_euler = (math.pi / 2 + self._pitch, 0.0, yaw)

    def set_camera(self, obj):
        self.scene.camera = obj or self.scene.objects.get(C.OBJ_PLAYER_CAM) or self.scene.camera

    def get_object(self, name):
        return self.scene.objects.get(name)

    def player_state(self):
        x, y, z, yaw = self.state
        return (x, y, z, yaw, z + C.PLAYER_EYE_STAND)

    def player_pitch(self):
        return self._pitch

    def place_player(self, x, y, z, yaw):
        self.state = (x, y, z, yaw)
        self._pitch = 0.0
        self._aim_flashlight()

    def set_power(self, on, flicker=0.0):
        self.power = on
        self._apply_lights(0.55 if (on and flicker) else 1.0)

    def set_light_gain(self, name, gain):
        if abs(gain - 1.0) < 1e-6:
            self.gains.pop(name, None)
        else:
            self.gains[name] = gain
        self._apply_lights(1.0)

    def _apply_lights(self, flicker_factor):
        for obj, base in self._lights:
            keep = flicker_factor if self.power else 0.0
            obj.data.energy = base * keep * self.gains.get(obj.name, 1.0)
        for obj in self.scene.objects:
            if obj.name.startswith("Fixture_"):
                obj.hide_viewport = obj.hide_render = not self.power

    def flash_light(self, seconds):
        pass

    def set_flashlight(self, on):
        self._flash_on = on
        self._flashlight.data.energy = FLASHLIGHT_ENERGY if on else 0.0

    def noise_silence(self, seconds):
        pass

    def entity_brain_activate(self, pos=None):
        self.brain_calls.append(pos)

    def tick(self, dt):
        self.doors.update(dt)
        self._adapt_flashlight()

    def _adapt_flashlight(self):
        """Como o `Flashlight` do jogo: perto de uma superfície a luz recua da lente e o olho se adapta (menos brilho)."""
        cam = self._player_cam
        if cam is None or not self._flash_on:
            return
        from sem_alvorada.engine import flashlight as game_flashlight
        bpy.context.view_layer.update()
        origin = cam.matrix_world.translation
        forward = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        hit, location, _, _, _, _ = self.scene.ray_cast(bpy.context.evaluated_depsgraph_get(), origin, forward,
                                                        distance=game_flashlight.FULL_POWER_DISTANCE)
        wall = (location - origin).length if hit else game_flashlight.FULL_POWER_DISTANCE
        forward_offset = min(game_flashlight.LIGHT_FORWARD_MAX, max(game_flashlight.LIGHT_FORWARD_MIN,
                                                                      wall - game_flashlight.WALL_GAP))
        self._flashlight.location = (game_flashlight.LIGHT_XY[0], game_flashlight.LIGHT_XY[1], -forward_offset)
        ratio = min(1.0, wall / game_flashlight.FULL_POWER_DISTANCE)
        gain = max(game_flashlight.CLOSE_GAIN_FLOOR, ratio ** game_flashlight.CLOSE_GAIN_EXPONENT)
        self._flashlight.data.energy = FLASHLIGHT_ENERGY * gain if self._flash_on else 0.0

    def show_body(self, visible):
        self.body.set_visible(visible)

    def finish(self, reason):
        self.finished.append(reason)


# --------------------------------------------------------------------------
# Composição do overlay em numpy
# --------------------------------------------------------------------------
def _ascii(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _wrap(text, max_chars):
    lines, current = [], ""
    for word in text.split():
        if len(current) + len(word) + 1 > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return lines + [current]


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
    scale = 2
    max_chars = max(10, width // (6 * scale) - 2)
    if overlay.subtitle and overlay.subtitle_alpha > 0.02:
        lines = _wrap(_ascii(overlay.subtitle), max_chars)
        y = height - bar - 12 - len(lines) * 9 * scale
        dim = overlay.subtitle_alpha <= 0.6
        for line in lines:
            sheet.draw_text(out, line, max(4, (width - len(line) * 6 * scale) // 2), y, scale=scale,
                            color=(0.4, 0.38, 0.3) if dim else (0.9, 0.87, 0.7))
            y += 9 * scale
    if overlay.card:
        y = height // 2 - 30
        for text in overlay.card:
            for line in _wrap(_ascii(text), max_chars):
                sheet.draw_text(out, line, max(4, (width - len(line) * 6 * scale) // 2), y, scale=scale,
                                color=(0.85, 0.82, 0.7))
                y += 9 * scale
            y += 12
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


def _prepare_death(host):
    """No jogo a entidade já está colada no jogador quando mata."""
    px, py, pz, pyaw = host.state
    dx, dy = C.yaw_dir(pyaw)
    host.entity.set_visible(True)
    host.entity.set_transform(px + dx * 1.1, py + dy * 1.1, pz, pyaw + math.pi)
    host.entity.set_anim("attack")
    host.entity.eyes(0.6)


def _scout_lamp(scene, watts):
    """Luz de depuração presa à câmera (só para conferir enquadramento e geometria no escuro): `--lamp watts`."""
    data = bpy.data.lights.new("ScoutLamp", "POINT")
    data.energy = watts
    data.shadow_soft_size = 0.3
    obj = bpy.data.objects.new("ScoutLamp", data)
    scene.collection.objects.link(obj)
    return obj


def render_frames(scene, name, times, res=(640, 360), samples=32, exposure=0.0, out_dir=OUT_DIR, fill=0.0,
                  prefix=None, columns=3, lamp=0.0):
    from sem_alvorada.entity import sheet
    os.makedirs(out_dir, exist_ok=True)
    prefix = prefix or name
    setup_cycles(scene, res, samples, exposure)
    if fill > 0:                         # luz branca no mundo, só para conferir enquadramento e geometria
        from tools import preview as tools_preview
        tools_preview._apply_fill(scene, fill)
    host = PreviewHost(scene, START_STATE[name])
    if name == "death":
        _prepare_death(host)
    scout = _scout_lamp(scene, lamp) if lamp > 0 else None
    player = CutscenePlayer(host)
    player.play(name)
    host.tick(0.0)
    tiles, labels = [], []
    for index, target in enumerate(sorted(times)):
        while player.active and player.time < target - 1e-6:
            step = min(STEP, target - player.time)
            player.update(step)
            if player.active:
                host.tick(step)
        if not player.active:
            break
        overlay = player.overlay()
        if scout is not None:
            cam = scene.camera
            scout.location = cam.matrix_world.translation + cam.matrix_world.to_quaternion() @ Vector((0.0, 0.25, -0.1))
        path = os.path.join(out_dir, f"{prefix}_{index:02d}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        frame = compose_overlay(sheet.load_pixels(path), overlay)
        sheet.save_png(path, frame)
        tiles.append(frame)
        labels.append(f"{name} {player.time:5.1f}S")
        print(f"[cutscene] {path} (t={player.time:.1f}s, fade={overlay.fade:.2f}) erros={player.errors}", flush=True)
    if tiles:
        sheet.save_png(os.path.join(out_dir, f"{prefix}_sheet.png"), sheet.contact_sheet(tiles, columns, labels))
    return host


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=DEFAULT_BLEND)
    ap.add_argument("--cutscene", required=True, choices=scripts.NAMES)
    ap.add_argument("--times", default="", help="segundos separados por vírgula (padrão: meio de cada plano)")
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--tag", default="", help="sufixo do nome dos arquivos (para não sobrescrever a folha completa)")
    ap.add_argument("--out", default=OUT_DIR, help="pasta de saída (a padrão é compartilhada com o orquestrador)")
    ap.add_argument("--fill", type=float, default=0.0, help="luz de mundo para depuração (0 = escuro de verdade)")
    ap.add_argument("--columns", type=int, default=3)
    ap.add_argument("--lamp", type=float, default=0.0, help="luz de depuração (watts) presa à câmera, para conferir a geometria no escuro")
    ap.add_argument("--rebuild", action="store_true", help="recria os objetos de cutscene sobre o .blend antes de renderizar")
    args = ap.parse_args(argv)
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    if args.rebuild:
        from sem_alvorada.cutscenes import objects
        objects.rebuild(bpy.context.scene)
    times = [float(t) for t in args.times.split(",")] if args.times else default_times(args.cutscene)
    res = tuple(int(v) for v in args.res.lower().split("x"))
    render_frames(bpy.context.scene, args.cutscene, times, res, args.samples, args.exposure, out_dir=args.out,
                  fill=args.fill, prefix=f"{args.cutscene}_{args.tag}" if args.tag else None, columns=args.columns,
                  lamp=args.lamp)


if __name__ == "__main__":
    main()
