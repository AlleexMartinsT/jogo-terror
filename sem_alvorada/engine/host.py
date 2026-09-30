"""Costuras com outros módulos: o host das cutscenes e a visão de mundo da IA.

Ambos são finos: só repassam para os subsistemas do `Game`. Os contratos estão em
docs/CONTRACT.md (seções 5.4 e 5.8).
"""
import bpy

from .. import layout


class NullEntityRig:
    """Ocupa o lugar do EntityRig quando o módulo `entity` não está disponível."""
    visible = False

    def set_transform(self, x, y, z, yaw):
        pass

    def set_anim(self, name):
        pass

    def update(self, dt, speed=0.0):
        pass

    def look_at(self, x, y, z):
        pass

    def set_visible(self, visible):
        pass

    def eyes(self, level):
        pass

    def head_position(self):
        return (0.0, 0.0, 0.0)

    def pose_for_death(self, player_eye_pos):
        pass


class CutsceneHost:
    """Implementa o Protocol de host da seção 5.4 sobre o Game."""

    def __init__(self, game):
        self.game = game

    @property
    def scene(self):
        return self.game.scene

    @property
    def audio(self):
        return self.game.audio

    @property
    def entity(self):
        return self.game.entity.rig or NullEntityRig()

    @property
    def doors(self):
        return self.game.doors

    def set_camera(self, obj):
        """Câmera da cena; None devolve a câmera do jogador."""
        self.game.set_active_camera(obj)

    def set_power(self, on, flicker=0.0):
        self.game.lights.set_power(on, flicker)

    def flash_light(self, seconds):
        self.game.flashlight.strobe(seconds)

    def set_flashlight(self, on):
        self.game.flashlight.set_on(on)

    def place_player(self, x, y, z, yaw):
        self.game.place_player(x, y, z, yaw)

    def player_state(self):
        player = self.game.player
        return (player.x, player.y, player.z, player.yaw, player.z + player.eye)

    def get_object(self, name):
        return self.game.scene.objects.get(name) or bpy.data.objects.get(name)

    def noise_silence(self, seconds):
        self.game.silence_noise(seconds)

    def entity_brain_activate(self):
        self.game.entity.activate()

    def finish(self, reason):
        self.game.director.on_cutscene_finished(reason)


class WorldView:
    """O que o cérebro da entidade pode perguntar ao mundo (seção 5.8). Mesmas portas e paredes do jogador."""

    def __init__(self, game):
        self.game = game

    def line_of_sight(self, a, b):
        return self.game.collision.line_clear(a, b) and not self.game.doors.blocks_sight(a, b)

    def door_openness(self, door_id):
        return self.game.doors.openness(door_id)

    def open_door(self, door_id, by="entity"):
        return self.game.doors.open_door(door_id, by)

    def is_locked(self, door_id):
        return self.game.doors.is_locked(door_id)

    def room_at(self, x, y, z=0.0):
        """Id do cômodo (str) ou None fora da casa, como `ai.worldview.WorldView` espera."""
        room = layout.room_at(x, y, z)
        return room.id if room else None
