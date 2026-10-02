"""Quadros-chave das animações de mão, vistos pela câmera do jogador, com o corpo real, em folha de contato.

    LIBGL_ALWAYS_SOFTWARE=1 python tools/prints_maos.py <cenario> [--blend out/f3_3/dev.blend]
        [--res 640x360] [--samples 6] [--dark] [--times 0.2,0.6,1.0] [--out out/f3_3]

Cenários (`SCENES`): lanterna (primeira vez), pilha, chave, mapa, nota, nota_parede, troca (R), recusa,
segurando_<item> (roda), mapa_rosto. Cada um prepara o estado, aperta as teclas nos instantes certos e
renderiza os quadros pedidos; a folha tem o tempo de cada quadro. O mundo é o do `.blend` (build parcial serve:
`SA_ROOMS=master,items,viewmodel,anchors python -m sem_alvorada.build --stages world,props,body,engine`).
"""
import argparse
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from sem_alvorada import BLEND_PATH  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.engine import collision  # noqa: E402
from sem_alvorada.engine.game import Game, InputState  # noqa: E402
from sem_alvorada.engine.state import FLAG_BLACKOUT  # noqa: E402
from tools.prints import load_pixels, look_at_yaw, render_player_view  # noqa: E402

DT = 1.0 / 30.0
OPTIONS = {}
DEV_BLEND = os.path.join(ROOT, "out", "f3_3", "dev.blend")
FOCUS_RADIUS = 6.5            # só o que está perto do jogador entra no render: o resto da casa só custa tempo
NIGHTSTAND = (0.40, 6.20, 3.41)
STAND = (1.35, 5.85, 2.8)           # a ~1 m do criado-mudo da lanterna, como o jogador costuma parar


class Scene:
    """Um cenário: estado inicial, teclas por instante e instantes a fotografar."""

    def __init__(self, prepare, presses, times, pose=STAND, aim=NIGHTSTAND, pitch=None):
        self.prepare, self.presses, self.times = prepare, presses, times
        self.pose, self.aim, self.pitch = pose, aim, pitch


def aim_pose(game, scene):
    """Põe o jogador na pose do cenário olhando para `aim`; sem `pitch`, a mira sobe/desce até o ponto exato."""
    x, y, z = scene.pose
    game.place_player(x, y, z, math.radians(look_at_yaw(x, y, scene.aim[0], scene.aim[1])))
    if scene.pitch is None:
        dz = scene.aim[2] - (z + C.PLAYER_EYE_STAND)
        scene.pitch = math.degrees(math.atan2(dz, math.hypot(scene.aim[0] - x, scene.aim[1] - y)))
    game.player.pitch = math.radians(scene.pitch)


def give(game, flashlight=True, key=False, map_=False, batteries=0, notes=(), charge=0.78, on=True):
    on = on and not OPTIONS.get("off")
    state = game.state
    state.has_flashlight, state.flashlight_on, state.battery = flashlight, flashlight and on, charge
    state.has_key, state.has_map = key, map_
    state.spare_batteries = state.batteries_found = batteries
    state.notes_read |= set(notes)
    if flashlight:
        state.collected.add("FLASHLIGHT")
    game.interact.sync_scene()


def move_item(game, ref, x, y, surface=3.35):
    """Põe o item real (`Item_<ref>`) sobre o criado-mudo, para a mão ter o que pegar do modelo de verdade."""
    target = next(t for t in game.interact.targets if t.ref == ref)
    obj = target.obj
    if obj is not None:
        low = min(v.co.z for v in obj.data.vertices) if obj.type == "MESH" else 0.0
        obj.location = (x, y, surface + 0.012 - low)
        target.position = tuple(collision.object_position(obj))
    else:
        target.position = (x, y, surface + 0.05)
    game.state.collected.discard(ref)
    return target


def prepare_pickup(ref, **given):
    def prepare(game):
        give(game, **given)
        if given.get("flashlight", True) is False:
            game.state.collected.discard("FLASHLIGHT")
        move_item(game, ref, NIGHTSTAND[0], NIGHTSTAND[1])
        game.interact.sync_scene()
    return prepare


def press_interact_at(seconds):
    return {seconds: dict(interact=True)}


def prepare_hold(kind, **given):
    def prepare(game):
        give(game, **given)
        game.hands.equip(kind)
    return prepare


def prepare_swap(game):
    give(game, batteries=2, charge=0.22)
    game.hands.equip(C.ITEM_FLASHLIGHT)


def prepare_map_face(game):
    give(game, map_=True)
    game.hands.equip(C.ITEM_MAP)


def prepare_note(game):
    give(game, notes=("NOTE_1",))


SCENES = {
    "lanterna": Scene(prepare_pickup("FLASHLIGHT", flashlight=False),
                      press_interact_at(0.1), [0.0, 0.25, 0.45, 0.62, 0.8, 1.05, 1.35, 1.6, 1.75, 1.9, 2.3, 2.7, 3.2]),
    "pilha": Scene(prepare_pickup("BATTERY_1"), press_interact_at(0.1),
                   [0.0, 0.3, 0.55, 0.72, 0.95, 1.2, 1.5, 1.8, 2.0]),
    "chave": Scene(prepare_pickup("KEY"), press_interact_at(0.1),
                   [0.0, 0.3, 0.55, 0.8, 1.0, 1.2, 1.4, 1.7, 2.0]),
    "mapa": Scene(prepare_pickup("MAP"), press_interact_at(0.1),
                  [0.0, 0.3, 0.55, 0.9, 1.2, 1.5, 1.8, 2.1, 2.4, 2.8]),
    "nota": Scene(prepare_note, press_interact_at(0.1), [0.0, 0.3, 0.55, 0.8, 1.05, 1.3], pose=(1.3, 8.5, 2.8),
                  aim=(0.40, 8.80, 3.36)),
    "nota_parede": Scene(lambda g: give(g), press_interact_at(0.1), [0.0, 0.3, 0.55, 0.8, 1.0, 1.4], pose=(1.5, 9.3, 0.0),
                         aim=(0.18, 9.42, 1.5)),
    "troca": Scene(prepare_swap, {0.2: dict(reload=True)}, [0.0, 0.2, 0.45, 0.7, 0.95, 1.2, 1.45, 1.65],
                   pose=STAND, aim=(0.0, 6.2, 3.0), pitch=-6.0),
    "recusa": Scene(lambda g: give(g, batteries=0, charge=0.5), {0.2: dict(reload=True)}, [0.0, 0.25, 0.4, 0.55, 0.8],
                    pose=STAND, aim=(0.0, 6.2, 3.0), pitch=-6.0),
    "segurando_chave": Scene(prepare_hold(C.ITEM_KEY, key=True), {}, [1.0, 1.4, 1.8], pose=STAND, aim=(0.0, 6.2, 3.0),
                             pitch=-6.0),
    "segurando_mapa": Scene(prepare_hold(C.ITEM_MAP, map_=True), {}, [1.0], pose=STAND, aim=(0.0, 6.2, 3.0), pitch=-6.0),
    "segurando_pilha": Scene(prepare_hold(C.ITEM_BATTERY, batteries=2), {}, [1.0], pose=STAND, aim=(0.0, 6.2, 3.0),
                             pitch=-6.0),
    "segurando_nota": Scene(prepare_hold(C.ITEM_NOTE, notes=("NOTE_1",)), {}, [1.0], pose=STAND, aim=(0.0, 6.2, 3.0),
                            pitch=-6.0),
    "livre": Scene(lambda g: give(g), {}, [0.8], pose=STAND, aim=(0.0, 6.2, 3.0), pitch=-6.0),
    "mapa_rosto": Scene(prepare_map_face, {1.0: "use_held"}, [0.9, 1.2, 1.5, 1.9, 2.4], pose=STAND,
                        aim=(0.0, 6.2, 3.0), pitch=-6.0),
}


def focus_render(scene, game):
    """Esconde do render o que está longe do jogador (outros cômodos, exterior), mantendo luzes próximas."""
    px, py, pz = game.player.eye_pos
    keep = {C.COL_PLAYER}
    for obj in scene.objects:
        if any(c.name in keep for c in obj.users_collection) or obj.type == "CAMERA":
            continue
        matrix = collision.world_matrix(obj)
        x, y, z = matrix.translation
        if obj.type == "MESH" and obj.bound_box:
            corners = [matrix @ __import__("mathutils").Vector(c) for c in obj.bound_box]
            x = sum(c.x for c in corners) / 8
            y = sum(c.y for c in corners) / 8
            z = sum(c.z for c in corners) / 8
        near = math.hypot(x - px, y - py) < FOCUS_RADIUS and abs(z - pz) < 2.4
        large = obj.type == "MESH" and max(obj.dimensions) > 9.0
        if not (near or large) and not obj.hide_render:
            obj.hide_render = True


def freeze_hands(game, text):
    """Troca as mãos por poses fixas, para olhar a orientação da mão sem animação."""
    from sem_alvorada.body import fingers
    poses = []
    for part in text.split(";"):
        side, numbers = part.split("=")
        values = numbers.split(",")
        preset = values[6] if len(values) > 6 else "relaxed"
        curls = tuple(float(v) for v in values[6:11]) if len(values) >= 11 else fingers.preset(preset)[0]
        poses.append((side, tuple(float(v) for v in values[:3]), tuple(float(v) for v in values[3:6]), curls))

    def update(dt, bob):
        for side, pos, rot, curls in poses:
            arm = game.body.arm(side)
            arm.set_target(pos, rot, 1.0)
            arm.set_fingers(curls, 0.0, 1.0)
        game.hands.models.hide_all()

    game.hands.update = update


def studio(scene, game):
    """Estúdio: sem casa, só o jogador, os itens e um fundo cinza com luz suave. Serve para julgar a mão e a garra."""
    from mathutils import Vector
    for obj in scene.objects:
        if obj.type == "CAMERA" or any(c.name in (C.COL_PLAYER, C.COL_ITEMS) for c in obj.users_collection):
            continue
        obj.hide_render = True
    position, rotation = game.player.camera_pose()
    forward = Vector((-math.sin(game.player.yaw) * math.cos(game.player.pitch),
                      math.cos(game.player.yaw) * math.cos(game.player.pitch), math.sin(game.player.pitch)))
    bpy.ops.mesh.primitive_plane_add(size=9.0, location=Vector(position) + forward * 2.4)
    plane = bpy.context.object
    plane.rotation_euler = (math.pi / 2 + game.player.pitch, 0.0, game.player.yaw)
    material = bpy.data.materials.new("estudio_fundo")
    material.diffuse_color = (0.18, 0.19, 0.2, 1.0)
    plane.scale = (1.0, 1.0, 1.0)
    plane.data.materials.append(material)
    sun = bpy.data.objects.new("estudio_sol", bpy.data.lights.new("estudio_sol", "SUN"))
    sun.data.energy = 2.5
    sun.rotation_euler = (math.radians(55), 0.0, game.player.yaw + math.radians(25))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("estudio_luz", bpy.data.lights.new("estudio_luz", "POINT"))
    fill.data.energy = 60.0
    fill.data.shadow_soft_size = 0.4
    fill.location = Vector(position) + Vector((0.0, 0.0, 0.25)) + forward * 0.1
    scene.collection.objects.link(fill)
    game.lights.set_power(False)
    world = scene.world or bpy.data.worlds.new("estudio")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.55, 0.57, 0.62, 1.0)
        background.inputs["Strength"].default_value = 1.2


def render_frame(scene, game, path, size, samples):
    game._sync_camera()
    render_player_view(scene, path, size, samples)
    return (np.clip(np.flipud(load_pixels(path, size)), 0, 1) * 255).astype(np.uint8)


def contact_sheet(frames, labels, columns, out_path):
    height, width = frames[0].shape[:2]
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (columns * width, rows * height), (10, 10, 12))
    for index, (frame, label) in enumerate(zip(frames, labels)):
        tile = Image.fromarray(frame)
        ImageDraw.Draw(tile).text((8, 6), label, fill=(255, 235, 120))
        sheet.paste(tile, ((index % columns) * width, (index // columns) * height))
    sheet.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cenario", choices=sorted(SCENES))
    parser.add_argument("--blend", default=DEV_BLEND if os.path.exists(DEV_BLEND) else BLEND_PATH)
    parser.add_argument("--res", default="640x360")
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--dark", action="store_true", help="apagão: só a lanterna ilumina")
    parser.add_argument("--hold", default="", help="sobrescreve a pose parada: LADO:ITEM=x,y,z,rx,ry,rz (; separa vários)")
    parser.add_argument("--pose", default="", help="mão fixa sem animação: LADO=x,y,z,rx,ry,rz[,preset] (; separa)")
    parser.add_argument("--off", action="store_true", help="lanterna apagada")
    parser.add_argument("--studio", action="store_true", help="fundo cinza, sem a casa")
    parser.add_argument("--times", default="")
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--out", default=os.path.join(ROOT, "out", "f3_3"))
    args = parser.parse_args()
    size = tuple(int(v) for v in args.res.lower().split("x"))
    OPTIONS["off"] = args.off
    from sem_alvorada.engine import handclips
    for spec_text in filter(None, args.hold.split(";")):
        key, numbers = spec_text.split("=")
        side, item = key.split(":")
        values = [float(v) for v in numbers.split(",")]
        handclips.HOLD_ITEM[(side, item)] = (tuple(values[:3]), tuple(values[3:]))
    os.makedirs(args.out, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    scene = bpy.context.scene
    from sem_alvorada.world import quality
    quality.apply(scene, "medium")
    game = Game(scene, quality="medium", audio=False, entity=False, cutscenes=False)
    game.new_game(skip_intro=True)
    game.phase = "play"
    spec = SCENES[args.cenario]
    game.state.flags.add(FLAG_BLACKOUT)
    game.lights.set_power(not args.dark)
    spec.prepare(game)
    if args.pose:
        freeze_hands(game, args.pose)
    aim_pose(game, spec)
    times = [float(t) for t in args.times.split(",")] if args.times else spec.times
    for _ in range(int(0.5 / DT)):
        game.place_player(*spec.pose, game.player.yaw)
        game.player.pitch = math.radians(spec.pitch)
        game.tick(DT, InputState())
    scene.camera = game.player_cam
    studio(scene, game) if args.studio else focus_render(scene, game)

    frames, labels = [], []
    clock = 0.0
    fired = set()
    started = time.time()
    pending = sorted(times)
    last = max(pending)
    while pending:
        presses = next((v for t, v in spec.presses.items() if abs(t - clock) < DT / 2), None)
        if presses is not None and clock in fired:
            presses = None
        fired.add(clock)
        inp = InputState()
        if presses == "use_held":
            game.hands.use_held()
        elif presses:
            for name, value in presses.items():
                setattr(inp, name, value)
        game.tick(DT, inp)
        if os.environ.get("MAOS_LOG"):
            vm = game.hands.models.objects.get(C.ITEM_FLASHLIGHT)
            lantern = tuple(round(c, 3) for c in vm.matrix_basis.translation) if vm else None
            hand = game.hands.last.get("R")
            print(f"t={clock:.2f} busy={game.hands.busy} cur={game.interact.current and game.interact.current.ref} "
                  f"vis={sorted(game.hands.visible_kinds())} lantern={lantern} hand={hand and tuple(round(c, 3) for c in hand[0])} "
                  f"I={game.flashlight.intensity:.2f}", flush=True)
        game.player.pitch = math.radians(spec.pitch)
        clock += DT
        if pending and clock + 1e-6 >= pending[0]:
            moment = pending.pop(0)
            path = os.path.join(args.out, f"raw_{args.cenario}_{moment:.2f}.png")
            frames.append(render_frame(scene, game, path, size, args.samples))
            labels.append(f"{args.cenario} t={moment:.2f}s I={game.flashlight.intensity:.2f}")
        if clock > last + 1.0:
            break
    out_path = os.path.join(args.out, f"maos_{args.cenario}.png")
    contact_sheet(frames, labels, args.columns, out_path)
    print(f"[maos] {out_path}: {len(frames)} quadros em {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
