"""Roteiro da história: gatilhos, cutscenes e checkpoints.

Sequência: intro -> lanterna -> entrar em `hall_u` (blackout, a caça começa) -> coletar tudo ->
destrancar a porta da garagem (garage_unlock) -> carro (ending). Morte -> death -> tela de fim.
O objetivo na tela é função do `GameState` (ver `GameState.objective`).
"""
from .. import story
from .state import (FLAG_BLACKOUT, FLAG_COLLECT_DONE, FLAG_ENDING, FLAG_GARAGE_UNLOCKED, FLAG_INTRO)

AGGRESSION_HUNT = 0
AGGRESSION_COLLECTED = 1
AGGRESSION_UNLOCKED = 2
TRIGGER_ROOM = "hall_u"


class Director:
    def __init__(self, game):
        self.game = game

    # ---- início ----
    def start_new_game(self, skip_intro=False):
        if skip_intro:
            self.on_cutscene_finished("intro_done")
        else:
            self.game.play_cutscene("intro")

    # ---- gatilhos por posição ----
    def update(self, dt):
        game = self.game
        if (FLAG_BLACKOUT not in game.state.flags and game.state.has_flashlight
                and game.player.room_id == TRIGGER_ROOM):
            game.play_cutscene("blackout")

    # ---- eventos do jogador ----
    def on_item_taken(self, target):
        game, state = self.game, self.game.state
        if state.collect_complete() and FLAG_COLLECT_DONE not in state.flags:
            state.flags.add(FLAG_COLLECT_DONE)
            game.entity.set_aggression(AGGRESSION_COLLECTED)
            game.say(story.COLLECT_DONE, seconds=4.5)
        game.save_checkpoint()

    def on_note_read(self, note_id):
        self.game.save_checkpoint()

    def unlock_garage(self):
        game, state = self.game, self.game.state
        state.unlocked.add("garage")
        state.flags.add(FLAG_GARAGE_UNLOCKED)
        pos = game.doors.center("garage_door")
        game.make_noise("pickup", pos, 0.15, sound="door_unlock")
        game.play_cutscene("garage_unlock")

    def on_car_used(self):
        self.game.play_cutscene("ending")

    def on_player_killed(self):
        self.game.play_cutscene("death")

    # ---- fim de cutscene (chamado pelo host) ----
    def on_cutscene_finished(self, reason):
        game = self.game
        game.end_cutscene()
        handler = {"intro_done": self._after_intro, "blackout_done": self._after_blackout,
                   "unlock_done": self._after_unlock, "death_done": self._after_death,
                   "ending_done": self._after_ending}.get(reason)
        if handler is not None:
            handler()

    def _after_intro(self):
        game = self.game
        game.state.flags.add(FLAG_INTRO)
        game.place_player_at_start()
        game.phase = "play"
        game.say(story.OPENING_LINE, seconds=4.5)
        game.save_checkpoint()

    def _after_blackout(self):
        game = self.game
        game.state.flags.add(FLAG_BLACKOUT)
        if game.lights.power_on:
            game.lights.set_power(False, 0.0)
        if not game.entity.active:
            game.entity.activate()
        game.entity.set_aggression(AGGRESSION_HUNT)
        game.phase = "play"
        game.save_checkpoint(at_player=False)

    def _after_unlock(self):
        game = self.game
        if game.doors.openness("garage_door") < 0.5:
            game.doors.set_openness("garage_door", 1.0)
        game.entity.set_aggression(AGGRESSION_UNLOCKED)
        game.phase = "play"
        game.save_checkpoint()

    def _after_death(self):
        self.game.state.deaths += 1
        self.game.phase = "dead"

    def _after_ending(self):
        self.game.state.flags.add(FLAG_ENDING)
        self.game.phase = "credits"
