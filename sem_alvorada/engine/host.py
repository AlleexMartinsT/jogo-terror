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

    @property
    def body(self):
        """O corpo do jogador (BodyRig ou NullBody); `show_body` decide se aparece na cutscene."""
        return self.game.body

    def show_body(self, visible):
        self.game.body_in_cutscene = bool(visible)

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

    def entity_brain_activate(self, pos=None):
        """Acorda o cérebro; `pos` (opcional) é onde a cutscene deixou a entidade, para ela seguir dali sem salto."""
        self.game.entity.activate(pos)

    def player_pitch(self):
        """Inclinação da cabeça do jogador: a primeira vista da cutscene é exatamente a do jogo."""
        return self.game.player.pitch

    def set_light_gain(self, name, gain):
        """Realça ou escurece uma luz da casa por nome (a queda de luz em cascata do apagão)."""
        self.game.lights.set_gain(name, gain)

    def body_tick(self, dt):
        """Avança o corpo do jogador durante a cutscene (poses e braços), se ele estiver visível."""
        body = self.game.body
        if getattr(body, "visible", False):
            body.update(dt, self.game.player, (0.0, 0.0))

    def finish(self, reason):
        self.game.director.on_cutscene_finished(reason)


class WorldView:
    """O que o cérebro da entidade pode perguntar ao mundo (seção 5.8). Mesmas portas e paredes do jogador."""

    def __init__(self, game):
        self.game = game

    def line_of_sight(self, a, b):
        """Visada livre entre dois pontos (x, y, z). Andares diferentes só se enxergam pelo vão da escada."""
        if layout.level_of_z(a[2]) != layout.level_of_z(b[2]) and not self._both_in_stairwell(a, b):
            return False
        return self.game.collision.line_clear(a, b) and not self.game.doors.blocks_sight(a, b)

    @staticmethod
    def _both_in_stairwell(a, b):
        hole = layout.STAIRS.hole.inflate(0.6)
        return hole.contains(a[0], a[1]) and hole.contains(b[0], b[1])

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
