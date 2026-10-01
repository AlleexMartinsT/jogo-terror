"""Som ambiente da casa: loops presos aos móveis e a voz dos eventos aleatórios.

Quem sorteia e registra os eventos (rangido, baque, telefone...) é o `NoiseSystem`, porque eles
também entram no cálculo de ruído: o jogador pode usá-los como cobertura e a entidade os investiga.
Aqui só tocamos o WAV correspondente, na posição do evento.
"""
from .. import layout

REFRESH_SECONDS = 0.5
LEVEL_PENALTY_M = 6.0      # som de outro andar conta como mais longe
EVENT_VOLUME = (0.35, 0.65)   # volume mínimo e ganho sobre a força do ruído
# Chiado de TV troca de padrão poucas vezes por segundo; a 60 quadros parece água correndo.
STATIC_STEPS_PER_SECOND = 12

# chave do loop, som, âncora (ou posição fixa, ou None), volume, alcance em metros
LOOPS = [
    ("house", "amb_house", None, 0.30, None),
    ("fridge", "amb_fridge", "fridge", 0.55, 9.0),
    ("clock", "amb_clock_tick", "grandfather_clock", 0.35, 8.0),
    ("tv", "amb_tv_static", "tv_living", 0.40, 8.0),
    ("garage", "amb_garage_hum", (15.0, 3.5, 0.0), 0.40, 9.0),
    ("music_box", "amb_music_box", "kids_bed", 0.25, 5.0),
    ("radio", "amb_radio_static", "nightstand_clock", 0.35, 6.0),
]


def _anchor_pos(anchor):
    return layout.ANCHORS[anchor].pos if isinstance(anchor, str) else anchor


def _event_sound(event, rng):
    try:
        from ..audio.noise import sound_for_event
    except ImportError:
        return None
    return sound_for_event(event, rng)


def _find_static_mappings():
    """Nós 'StaticMapping' (criados pelos props) cujo deslocamento anima o chiado da TV."""
    import bpy
    found = []
    for material in bpy.data.materials:
        tree = material.node_tree
        node = tree.nodes.get("StaticMapping") if tree else None
        if node is not None:
            found.append(node)
    return found


class Ambience:
    def __init__(self, game):
        self.game = game
        self._refresh_left = 0.0
        self._playing = set()
        self._static_nodes = None
        self._static_left = 0.0

    def reset(self):
        for key in list(self._playing):
            self.game.audio.stop("amb_" + key)
        self._playing.clear()
        self._refresh_left = 0.0

    def update(self, dt, events_enabled):
        self._animate_static(dt)
        self._refresh_left -= dt
        if self._refresh_left <= 0:
            self._refresh_left = REFRESH_SECONDS
            self._refresh_loops()
        if events_enabled:
            game = self.game
            for event in game.noise.schedule_ambient_events(dt, game.rng, game.player.room_id):
                self._play_event(event)

    def _animate_static(self, dt):
        self._static_left -= dt
        if self._static_left > 0:
            return
        self._static_left = 1.0 / STATIC_STEPS_PER_SECOND
        if self._static_nodes is None:
            self._static_nodes = _find_static_mappings()
        rng = self.game.rng
        for node in self._static_nodes:
            node.inputs["Location"].default_value = (rng.random(), rng.random(), 0.0)

    def _play_event(self, event):
        sound = _event_sound(event, self.game.rng)
        if sound is not None:
            low, gain = EVENT_VOLUME
            self.game.audio.play(sound, event.pos, low + gain * event.loudness)

    def _distance(self, pos):
        player = self.game.player
        penalty = LEVEL_PENALTY_M if layout.level_of_z(pos[2]) != player.level else 0.0
        return ((pos[0] - player.x) ** 2 + (pos[1] - player.y) ** 2) ** 0.5 + penalty

    def _refresh_loops(self):
        audio = self.game.audio
        for key, sound, anchor, volume, reach in LOOPS:
            name = "amb_" + key
            if anchor is None:
                audio.loop(name, sound, None, volume)
                self._playing.add(key)
                continue
            pos = _anchor_pos(anchor)
            if self._distance(pos) <= reach:
                audio.loop(name, sound, pos, volume)
                self._playing.add(key)
            elif key in self._playing:
                audio.stop(name)
                self._playing.discard(key)
