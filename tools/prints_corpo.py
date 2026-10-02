"""Capturas do corpo do jogador, como a câmera dele vê: no escuro com a lanterna e em luz de estúdio.

    LIBGL_ALWAYS_SOFTWARE=1 python tools/prints_corpo.py [--res 640x360] [--samples 6] [--out out/f3_2/corpo]
                                                         [--cenas parado,meio_passo,...] [--blend SemAlvorada.blend]

Abre o .blend, refaz a etapa `body` (assim o corpo novo aparece mesmo num arquivo gerado antes dele), liga o Game
de verdade (colisão, mãos, lanterna) e fotografa as cenas de `CENAS`. Cada cena sai em dois quadros, `<cena>_escuro.png`
e `<cena>_estudio.png`, e todas viram uma folha de contato (`folha_corpo.png`, escuro à esquerda, estúdio à direita,
na ordem de `CENAS`). `legenda.txt` diz qual linha é qual.

Cenas "de jogo" deixam o Game andar sozinho (as mãos são as do `Hands`); as de "mãos" desligam o `Hands` e mandam
os braços direto, para julgar a modelagem e as empunhaduras.
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

import bpy  # noqa: E402,I001
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import BLEND_PATH, compat  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.engine.game import Game, InputState  # noqa: E402
from sem_alvorada.engine.state import FLAG_BLACKOUT  # noqa: E402
from tools import pngwrite  # noqa: E402
from tools.prints import equip, load_pixels, look_at_yaw, render_player_view  # noqa: E402

DT = 1.0 / 30.0
ROOM = {"x": 2.4, "y": 1.2, "alvo": (3.4, 4.2)}          # sala de estar: piso de madeira, parede e sofá à frente

# nome: dict(pitch graus, tecla/andar, mãos). "mao": lado -> (alvo na câmera, rotação em graus, preset de dedos)
CENAS = {
    "parado_olhando_baixo": dict(pitch=-72, texto="parado, olhando quase para baixo: peito, cinto, coxas e botas"),
    "parado_olhando_45": dict(pitch=-48, texto="parado, olhando 48 graus para baixo"),
    "meio_passo": dict(pitch=-70, andar=0.46, texto="no meio de um passo (a passada mostra o pé da frente)"),
    "agachado": dict(pitch=-62, agachar=True, texto="agachado, olhando para baixo"),
    "correndo": dict(pitch=-38, andar=0.5, correr=True, texto="correndo"),
    "maos_flat": dict(pitch=-8, maos=True, mao={"R": ((0.19, -0.13, -0.40), (-10, 0, 0), "flat"), "L": ((-0.19, -0.13, -0.40), (-10, 0, 0), "flat")},
                      texto="as duas mãos erguidas, dedos esticados (flat)"),
    "maos_pinch": dict(pitch=-8, maos=True, mao={"R": ((0.16, -0.12, -0.36), (0, 0, 20), "pinch"), "L": ((-0.16, -0.12, -0.36), (0, 0, -20), "pinch")},
                       texto="as duas mãos erguidas, pinça (pinch)"),
    "maos_punho": dict(pitch=-8, maos=True, mao={"R": ((0.17, -0.15, -0.38), (0, 0, 60), "fist"), "L": ((-0.17, -0.15, -0.38), (0, 0, -60), "fist")},
                       texto="as duas mãos erguidas, punhos fechados (fist)"),
    "lanterna_na_mao": dict(pitch=-14, texto="partida normal: lanterna na mão direita, esquerda solta (Hands)"),
}


def refresh_body(scene):
    """Apaga o corpo que o .blend traz e constrói o atual."""
    for name in (C.OBJ_BODY, C.OBJ_BODY_RIG):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
    for datablocks in (bpy.data.meshes, bpy.data.armatures):
        for block in [b for b in datablocks if b.name in (C.OBJ_BODY, C.OBJ_BODY_RIG) and b.users == 0]:
            datablocks.remove(block)
    for material in [m for m in bpy.data.materials if m.name.startswith("body_")]:
        bpy.data.materials.remove(material)
    for image in [i for i in bpy.data.images if i.name.startswith("body_")]:
        bpy.data.images.remove(image)
    from sem_alvorada import body
    ctx = BuildContext(scene, verbose=False)
    ctx.stage = "body"
    body.build(ctx)


def settle(game, seconds, **inputs):
    inp = InputState(**inputs)
    for _ in range(int(round(seconds / DT))):
        game.tick(DT, inp)
        inp.clear_edges()


def prepare_game(scene):
    from sem_alvorada.world import quality
    quality.apply(scene, "medium")
    game = Game(scene, quality="medium", audio=False, debug=False)
    game.new_game(skip_intro=True)
    game.phase = "play"
    game.state.flags.add(FLAG_BLACKOUT)
    equip(game, battery=0.8, spare=2, flashlight_on=True, batteries_found=2)
    game.state.has_flashlight = True
    return game


def place_scene(game, config):
    x, y = ROOM["x"], ROOM["y"]
    yaw = look_at_yaw(x, y, *ROOM["alvo"])
    game.lights.set_power(False)
    game.place_player(x, y, 0.0, math.radians(yaw))
    game.player.pitch = math.radians(config["pitch"])
    settle(game, 0.5)
    game.player.pitch = math.radians(config["pitch"])
    if config.get("agachar"):
        settle(game, 0.9, crouch=True)
        game.player.pitch = math.radians(config["pitch"])
    elif config.get("andar"):
        speed_kwargs = dict(move_y=1.0, run=bool(config.get("correr")))
        settle(game, config["andar"], **speed_kwargs)
        game.player.pitch = math.radians(config["pitch"])
        game.place_player(game.player.x, game.player.y, 0.0, game.player.yaw)   # congela no instante do passo
        game.player.pitch = math.radians(config["pitch"])
    if config.get("maos"):
        game.hands.update = lambda dt, bob=None: None
        for side, (target, rotation, preset) in config["mao"].items():
            from sem_alvorada.body import fingers
            arm = game.body.arm(side)
            arm.set_target(target, rotation, 1.0)
            arm.set_fingers(*fingers.preset(preset))
        for _ in range(8):
            game.body.update(DT, game.player, game.player.bob_offset())
    game.flashlight.snap_to_camera(game.player.yaw, game.player.pitch)        # a luz já aponta para onde a câmera olha
    settle(game, 0.12)
    game.player.pitch = math.radians(config["pitch"])
    game._sync_camera()


def hide_viewmodel_if_hands_off(scene, config):
    model = scene.objects.get(C.OBJ_VIEW_FLASH)
    if model is not None and config.get("maos"):
        model.hide_render = model.hide_viewport = True


def studio_lights(scene, game):
    """Duas luzes de área e um fundo claro em volta da câmera: o modelo sem o escuro."""
    created = []
    world = scene.world
    saved = None
    if world is not None and world.use_nodes:
        background = world.node_tree.nodes.get("Background")
        if background is not None:
            saved = (tuple(background.inputs["Color"].default_value), background.inputs["Strength"].default_value)
            background.inputs["Color"].default_value = (0.55, 0.56, 0.58, 1.0)
            background.inputs["Strength"].default_value = 0.8
    position = Vector(game.player.eye_pos)
    for name, offset, energy in (("key", (0.8, -0.6, 1.2), 260.0), ("fill", (-1.2, 0.6, 0.6), 120.0)):
        data = bpy.data.lights.new(f"_estudio_{name}", "AREA")
        data.energy, data.size = energy, 1.5
        light = bpy.data.objects.new(f"_estudio_{name}", data)
        light.location = position + Vector(offset)
        light.rotation_euler = (Vector(game.player.eye_pos) - Vector((0, 0, 0.7)) - light.location).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(light)
        created.append(light)
    return created, saved


def remove_studio(scene, created, saved):
    for light in created:
        bpy.data.objects.remove(light, do_unlink=True)
    if saved is not None and scene.world is not None:
        background = scene.world.node_tree.nodes.get("Background")
        background.inputs["Color"].default_value, background.inputs["Strength"].default_value = saved[0], saved[1]


def capture(scene, game, path, size, samples):
    render_player_view(scene, path, size, samples)
    return load_pixels(path, size)


def save_sheet(rows, path):
    """rows: lista de (quadro_escuro, quadro_estudio); a imagem final tem uma linha por cena."""
    lines = []
    for dark, studio in rows:
        lines.append(np.concatenate([dark, studio], axis=1))
    sheet = np.concatenate(lines[::-1], axis=0)
    pngwrite.write_png(path, (np.clip(np.flipud(sheet), 0, 1) * 255).astype(np.uint8))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--blend", default=BLEND_PATH)
    parser.add_argument("--out", default=os.path.join(ROOT, "out", "f3_2", "corpo"))
    parser.add_argument("--res", default="640x360")
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--cenas", default=",".join(CENAS))
    parser.add_argument("--so", choices=["escuro", "estudio"], help="só um dos dois estilos de luz")
    args = parser.parse_args()
    size = tuple(int(v) for v in args.res.lower().split("x"))
    os.makedirs(args.out, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    scene = bpy.context.scene
    refresh_body(scene)
    compat.use_eevee(scene)
    rows, legend = [], []
    for name in args.cenas.split(","):
        config = CENAS[name]
        started = time.time()
        frames = {}
        game = prepare_game(scene)
        place_scene(game, config)
        hide_viewmodel_if_hands_off(scene, config)
        for style in ("escuro", "estudio"):
            if args.so and style != args.so:
                frames[style] = np.zeros((size[1], size[0], 3), np.float32)
                continue
            lights = saved = None
            if style == "estudio":
                game.lights.set_power(True, 0.0)
                lights, saved = studio_lights(scene, game)
            path = os.path.join(args.out, f"{name}_{style}.png")
            raw = capture(scene, game, path + ".raw.png", size, args.samples)
            pngwrite.write_png(path, (np.clip(np.flipud(raw), 0, 1) * 255).astype(np.uint8))
            os.remove(path + ".raw.png")
            frames[style] = raw
            if lights:
                remove_studio(scene, lights, saved)
        game.leave_scene()
        rows.append((frames["escuro"], frames["estudio"]))
        legend.append(f"{len(legend) + 1}. {name}: {config['texto']}")
        print(f"[prints_corpo] {name} em {time.time() - started:.0f}s", flush=True)
    save_sheet(rows, os.path.join(args.out, "folha_corpo.png"))
    with open(os.path.join(args.out, "legenda.txt"), "w", encoding="utf-8") as handle:
        handle.write("Folha de contato do corpo: cada linha uma cena, escuro com lanterna à esquerda, estúdio à direita.\n")
        handle.write("\n".join(legend) + "\n")
    print(f"[prints_corpo] {os.path.join(args.out, 'folha_corpo.png')}", flush=True)


if __name__ == "__main__":
    main()
