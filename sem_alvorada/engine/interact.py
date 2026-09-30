"""Interação: escolhe o objeto mais centralizado na mira e executa a ação do [E].

Os alvos vêm dos objetos com `sa_interact`; itens que a cena não trouxe entram como alvos
virtuais nas posições de `layout.ITEM_SPOTS`, para o jogo continuar completável.
"""
import math
from dataclasses import dataclass
from typing import Optional

from mathutils import Vector

from .. import conventions as C
from .. import layout
from .. import story
from . import collision, texts

CONE = math.radians(12.0)
DOOR_EXTRA_REACH = 0.3
SIGHT_MARGIN = 0.08
RADIUS = {"item": 0.10, "note": 0.15, "door": 0.45, "look": 0.5, "car": 0.6}
STORY_SOUND = {C.ITEM_FLASHLIGHT: "pickup", C.ITEM_KEY: "key_jingle", C.ITEM_MAP: "map_unfold",
               C.ITEM_BATTERY: "battery_pickup", C.ITEM_NOTE: "paper_rustle"}


@dataclass
class Interactable:
    kind: str                      # item | note | door | look | car
    ref: str                       # sa_id: KEY, NOTE_3, kitchen_hall...
    item: str = ""                 # tipo do item (sa_item)
    obj: Optional[object] = None
    position: Optional[tuple] = None
    prompt: str = ""

    @property
    def key(self):
        return f"{self.kind}:{self.ref}"


def _bounds_center(obj):
    """Centro da caixa do objeto em coordenadas de mundo (a origem, se não for malha)."""
    matrix = collision.world_matrix(obj)
    if obj.type != "MESH" or not obj.bound_box:
        return tuple(matrix.translation)
    corners = [matrix @ Vector(corner) for corner in obj.bound_box]
    return tuple(sum(c[i] for c in corners) / 8.0 for i in range(3))


class Interact:
    def __init__(self, game, scene):
        self.game = game
        self.targets = []
        self.current = None
        self.missing_from_scene = []
        self._index_scene(scene)
        self._add_virtual_items()
        self._add_doors()

    # ---- montagem do índice ----
    def _index_scene(self, scene):
        for obj in scene.objects:
            kind = obj.get(C.P_INTERACT)
            if kind not in ("item", "note", "look", "car"):
                continue
            ref = obj.get(C.P_ID) or obj.name.split("_", 1)[-1]
            item = obj.get(C.P_ITEM, C.ITEM_NOTE if kind == "note" else "")
            position = _bounds_center(obj) if kind in ("look", "car") else collision.object_position(obj)
            if kind == "car":
                position = (position[0], position[1], position[2] + 1.0)
            self.targets.append(Interactable(kind, ref, item, obj, position, obj.get(C.P_PROMPT, "")))

    def _add_virtual_items(self):
        known = {t.ref for t in self.targets if t.kind in ("item", "note")}
        for ref, (_room, x, y, z, _hint) in layout.ITEM_SPOTS.items():
            if ref in known:
                continue
            self.missing_from_scene.append(C.N_ITEM + ref)
            kind = "note" if ref.startswith("NOTE") else "item"
            item = C.ITEM_NOTE if kind == "note" else ref.split("_")[0]
            self.targets.append(Interactable(kind, ref, item, None, (x, y, z + 0.05)))
        if not any(t.kind == "car" for t in self.targets):
            anchor = layout.ANCHORS["car_interact"]
            self.missing_from_scene.append(C.N_ANCHOR + "car_interact")
            self.targets.append(Interactable("car", "car", "", None, (anchor.x, anchor.y, anchor.z + 1.0)))

    def _add_doors(self):
        for door_id in self.game.doors.doors:
            self.targets.append(Interactable("door", door_id))

    # ---- consultas ----
    def position(self, target):
        if target.kind == "door":
            return self.game.doors.center(target.ref)
        return target.position

    def is_active(self, target):
        if target.kind == "item":
            return target.ref not in self.game.state.collected
        return True

    def prompt_for(self, target):
        if target.kind == "door":
            return self._door_prompt(target.ref)
        if target.prompt:
            return target.prompt
        if target.kind == "item":
            return story.ITEM_PROMPTS.get(target.item, story.PROMPT_PICKUP)
        return {"note": story.PROMPT_READ, "look": "[E] Olhar", "car": story.PROMPT_CAR}[target.kind]

    def _door_prompt(self, door_id):
        doors = self.game.doors
        if doors.is_locked(door_id):
            garage_ready = doors.get(door_id).lock == "garage" and self.game.state.collect_complete()
            return story.PROMPT_UNLOCK_GARAGE if garage_ready else story.PROMPT_OPEN
        return story.PROMPT_CLOSE if doors.is_open(door_id) else story.PROMPT_OPEN

    def select(self, eye, forward):
        """O alvo mais centralizado dentro do alcance e da visada, ou None."""
        best, best_ratio = None, 1.0
        for target in self.targets:
            if not self.is_active(target):
                continue
            pos = self.position(target)
            offset = (pos[0] - eye[0], pos[1] - eye[1], pos[2] - eye[2])
            distance = math.sqrt(sum(c * c for c in offset))
            reach = C.INTERACT_RANGE + (DOOR_EXTRA_REACH if target.kind == "door" else 0.0)
            if distance > reach or distance < 1e-6:
                continue
            cosine = sum(f * c for f, c in zip(forward, offset)) / distance
            angle = math.acos(max(-1.0, min(1.0, cosine)))
            tolerance = CONE + math.atan2(RADIUS[target.kind], max(distance, 0.1))
            ratio = angle / tolerance
            if ratio >= best_ratio or not self._clear_view(eye, pos, distance, target):
                continue
            best, best_ratio = target, ratio
        return best

    def _clear_view(self, eye, pos, distance, target):
        shrink = (distance - SIGHT_MARGIN) / distance
        end = tuple(e + (p - e) * shrink for e, p in zip(eye, pos))
        ignore = target.ref if target.kind == "door" else None
        return self.game.collision.line_clear(eye, end) and not self.game.doors.blocks_sight(eye, end, ignore)

    def update(self, eye, forward):
        self.current = self.select(eye, forward)
        return self.current

    # ---- ações ----
    def use(self, target):
        action = {"item": self._take, "note": self._read, "door": self._use_door,
                  "look": self._look, "car": self._enter_car}[target.kind]
        action(target)

    def _take(self, target):
        game, state = self.game, self.game.state
        item = target.item
        if item == C.ITEM_FLASHLIGHT:
            state.has_flashlight = True
        elif item == C.ITEM_KEY:
            state.has_key = True
        elif item == C.ITEM_MAP:
            state.has_map = True
        elif item == C.ITEM_BATTERY:
            state.batteries_found += 1
            state.spare_batteries += 1
        state.collected.add(target.ref)
        self.sync_scene()
        text = story.PICKED.get(item, story.PROMPT_PICKUP)
        if item == C.ITEM_FLASHLIGHT:
            text += " " + texts.MSG_FLASHLIGHT_HINT
        game.make_noise("pickup", game.player.feet, C.NOISE_PLAYER["pickup"], sound=STORY_SOUND[item])
        game.say(text)
        game.director.on_item_taken(target)

    def _read(self, target):
        game = self.game
        game.make_noise("pickup", game.player.feet, C.NOISE_PLAYER["pickup"], sound=STORY_SOUND[C.ITEM_NOTE])
        game.state.notes_read.add(target.ref)
        game.open_note(target.ref)
        game.director.on_note_read(target.ref)

    def _use_door(self, target):
        game = self.game
        door = game.doors.get(target.ref)
        if game.doors.is_locked(target.ref):
            if door.lock == "garage" and game.state.collect_complete():
                game.director.unlock_garage()
                return
            game.doors.toggle(target.ref)
            text = story.LOCKED_MSGS.get(door.lock, "Trancada.")
            if door.lock == "garage":
                text += " " + texts.MSG_GARAGE_NEEDS.format(missing=", ".join(game.state.missing_labels()))
            game.say(text)
            return
        hurried = game.player.running or game.player.speed > C.SPEED_WALK * 1.3
        game.doors.toggle(target.ref, hurried=hurried)

    def _look(self, target):
        self.game.say(story.NOTHING_OUTSIDE)

    def _enter_car(self, target):
        if "garage" not in self.game.state.unlocked:
            self.game.say(texts.MSG_CAR_LOCKED)
            return
        self.game.director.on_car_used()

    # ---- cena ----
    def sync_scene(self):
        """Esconde os itens recolhidos e reexibe os demais (checkpoint, novo jogo)."""
        collected = self.game.state.collected
        for target in self.targets:
            if target.kind == "item" and target.obj is not None:
                hidden = target.ref in collected
                target.obj.hide_viewport = target.obj.hide_render = hidden
