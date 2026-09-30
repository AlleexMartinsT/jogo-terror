"""Infraestrutura dos testes do engine: mundo mínimo derivado da planta, fakes e helpers.

O mundo mínimo tem as mesmas paredes, pisos e escada de `layout` como caixas `sa_col`,
então o caminho do BVH é exercitado sem depender dos módulos world/props.
"""
import math
import os
import sys
from dataclasses import dataclass
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from sem_alvorada import build as build_module  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.engine import builder  # noqa: E402
from sem_alvorada.engine.game import Game  # noqa: E402
from sem_alvorada.engine.inputstate import InputState  # noqa: E402

DT = 1.0 / 30.0
BOX_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


# --------------------------------------------------------------------------
# Cena mínima
# --------------------------------------------------------------------------
def add_box(scene, name, x0, y0, z0, x1, y1, z1, collides=True, hidden=False):
    verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], list(BOX_FACES))
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    if collides:
        obj[C.P_COL] = 1
    obj.hide_viewport = hidden
    return obj


def build_minimal_world(scene, furniture=True):
    """Paredes, pisos, forros e escada de `layout` como caixas de colisão, mais um sofá."""
    for level in (0, 1):
        for index, piece in enumerate(layout.wall_pieces(level)):
            rect = piece.rect2d()
            add_box(scene, f"W{level}_{index}", rect.x0, rect.y0, piece.z0, rect.x1, rect.y1, piece.z1)
        floor_z = layout.LEVEL_Z[level]
        for room_id, rect in layout.floor_rects(level):
            add_box(scene, f"Floor_{room_id}_{level}", rect.x0, rect.y0, floor_z - 0.1, rect.x1, rect.y1, floor_z)
        ceiling_z = layout.CEIL_Z[level]
        for room_id, rect in layout.ceiling_rects(level):
            add_box(scene, f"Ceil_{room_id}_{level}", rect.x0, rect.y0, ceiling_z, rect.x1, rect.y1, ceiling_z + 0.1)
    stairs = layout.STAIRS
    for tread in range(1, stairs.treads + 1):
        y0 = stairs.y0 + (tread - 1) * stairs.tread_depth
        add_box(scene, f"Step_{tread}", stairs.x0, y0, 0.0, stairs.x1, y0 + stairs.tread_depth, tread * stairs.rise)
    if furniture:
        add_box(scene, "COL_sofa", 2.1 - 0.45, 3.9 - 1.0, 0.0, 2.1 + 0.45, 3.9 + 1.0, 0.8, hidden=True)


def fresh_scene():
    scene = build_module.fresh_scene()
    ctx = BuildContext(scene, verbose=False)
    builder.build(ctx)
    return scene


def add_item_objects(scene):
    """Cria Item_* vazios nas posições da planta, como o módulo props faria."""
    for ref, (room, x, y, z, _hint) in layout.ITEM_SPOTS.items():
        item = bpy.data.objects.new(C.N_ITEM + ref, None)
        scene.collection.objects.link(item)
        item.location = (x, y, z + 0.05)
        kind = "note" if ref.startswith("NOTE") else "item"
        item[C.P_INTERACT] = kind
        item[C.P_ID] = ref
        item[C.P_ITEM] = C.ITEM_NOTE if kind == "note" else ref.split("_")[0]
        item[C.P_ROOM] = room


def add_ceiling_lights(scene):
    for room, spots in layout.CEILING_LIGHTS.items():
        for index, (x, y) in enumerate(spots):
            data = bpy.data.lights.new(f"Light_{room}_c{index}", "POINT")
            data.energy = 60.0
            light = bpy.data.objects.new(f"Light_{room}_c{index}", data)
            scene.collection.objects.link(light)
            light.location = (x, y, layout.LEVEL_Z[layout.ROOMS[room].level] + 2.4)
            light[C.P_ROOM] = room
            light[C.P_LIGHT_ENERGY] = 60.0
            light[C.P_LIGHT_FLICKER] = 0.1
            light[C.P_LIGHT_KIND] = "ceiling"


def make_game(world=True, items=False, lights=False, entity=False, cutscenes=False, **kwargs):
    scene = fresh_scene()
    if world:
        build_minimal_world(scene)
    if items:
        add_item_objects(scene)
    if lights:
        add_ceiling_lights(scene)
    return Game(scene, audio=False, entity=entity, cutscenes=cutscenes, **kwargs)


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
@dataclass
class FakeOverlay:
    fade: float = 0.0
    letterbox: float = 0.0
    subtitle: str = ""
    subtitle_alpha: float = 0.0
    card: object = None
    flash: float = 0.0
    shake: float = 0.0


class FakeCutscenePlayer:
    """CutscenePlayer de mentira: dura `seconds`, faz os efeitos essenciais no host e chama finish."""
    REASONS = {"intro": "intro_done", "blackout": "blackout_done", "garage_unlock": "unlock_done",
               "death": "death_done", "ending": "ending_done"}

    def __init__(self, host, seconds=1.0):
        self.host = host
        self.seconds = seconds
        self.left = 0.0
        self.name = None
        self.played = []

    @property
    def active(self):
        return self.name is not None

    def play(self, name, on_done=None):
        self.name, self.left = name, self.seconds
        self.played.append(name)

    def update(self, dt):
        if self.name is None:
            return
        self.left -= dt
        if self.left <= 0:
            self.skip()

    def skip(self):
        name, self.name = self.name, None
        if name == "blackout":
            self.host.set_power(False, 0.0)
            self.host.entity_brain_activate()
        elif name == "garage_unlock":
            self.host.doors.snap("garage_door", 1.0)
        self.host.finish(self.REASONS[name])

    def overlay(self):
        return FakeOverlay(letterbox=1.0, subtitle="legenda", subtitle_alpha=1.0)


class FakeRig:
    def __init__(self):
        self.calls = []
        self.visible = False
        self.transform = None

    def set_transform(self, x, y, z, yaw):
        self.transform = (x, y, z, yaw)

    def set_anim(self, name):
        self.calls.append(("anim", name))

    def update(self, dt, speed=0.0):
        pass

    def look_at(self, x, y, z):
        pass

    def set_visible(self, visible):
        self.visible = visible

    def eyes(self, level):
        self.calls.append(("eyes", level))

    def head_position(self):
        return (0.0, 0.0, 2.5)

    def pose_for_death(self, pos):
        self.calls.append(("death_pose", pos))


class FakeBrain:
    """Cérebro roteirizado: persegue o jogador em linha reta e mata a menos de ENTITY_KILL_DISTANCE."""

    def __init__(self, speed=3.0, hunts=True):
        self.x = self.y = self.z = 0.0
        self.speed = speed
        self.hunts = hunts
        self.aggression = -1
        self.activated_at = None

    def activate(self, pos):
        self.x, self.y, self.z = pos
        self.activated_at = pos

    def set_aggression(self, level):
        self.aggression = level

    def update(self, dt, senses):
        px, py, pz = senses.player_pos
        dx, dy = px - self.x, py - self.y
        dist = math.hypot(dx, dy)
        if self.hunts and dist > 1e-6:
            step = min(self.speed * dt, dist)
            self.x, self.y = self.x + dx / dist * step, self.y + dy / dist * step
            self.z = pz
        kill = self.hunts and dist < C.ENTITY_KILL_DISTANCE and abs(pz - self.z) < 1.0
        return SimpleNamespace(x=self.x, y=self.y, z=self.z, yaw=0.0, speed=self.speed if self.hunts else 0.0,
                               state="chase" if self.hunts else "patrol", anim="run", look_target=None,
                               kill=kill, drone=0.5)


def game_with_fake_entity(hunts=True, cutscene_seconds=1.0, **kwargs):
    brain = FakeBrain(hunts=hunts)
    rig = FakeRig()
    players = []

    def make_cutscenes(host):
        players.append(FakeCutscenePlayer(host, cutscene_seconds))
        return players[0]

    game = make_game(entity=(rig, lambda: brain), cutscenes=make_cutscenes, **kwargs)
    return game, brain, rig, players[0]


# --------------------------------------------------------------------------
# Helpers de simulação
# --------------------------------------------------------------------------
def step(game, inp=None, seconds=DT):
    """Um tick de `seconds`; devolve o InputState (limpo dos edges depois do tick)."""
    inp = inp or InputState()
    game.tick(seconds, inp)
    inp.clear_edges()
    return inp


def run_for(game, seconds, inp=None):
    inp = inp or InputState()
    for _ in range(int(round(seconds / DT))):
        game.tick(DT, inp)
        inp.clear_edges()
    return inp


def start_playing(game):
    """Título -> jogo, sem cutscenes: deixa o jogador no quarto, fase 'play'."""
    game.skip_intro = True
    inp = InputState(confirm=True)
    game.tick(DT, inp)
    inp.clear_edges()
    assert game.phase == "play", game.phase
    return game


def walk(game, seconds, forward=1.0, side=0.0, run=False, crouch=False, yaw_deg=None):
    if yaw_deg is not None:
        game.player.yaw = math.radians(yaw_deg)
    inp = InputState(move_y=forward, move_x=side, run=run, crouch=crouch)
    run_for(game, seconds, inp)


def teleport(game, x, y, z, yaw_deg=0.0):
    game.place_player(x, y, z, math.radians(yaw_deg))


def kinds_logged(game, kind, source="player"):
    return [entry for entry in game.noise_log if entry[0] == source and entry[1] == kind]


def aim_at(game, target_pos):
    """Aponta a câmera do jogador para um ponto do mundo."""
    px, py, pz = game.player.eye_pos
    dx, dy, dz = target_pos[0] - px, target_pos[1] - py, target_pos[2] - pz
    game.player.yaw = math.atan2(-dx, dy)
    game.player.pitch = math.atan2(dz, math.hypot(dx, dy))
