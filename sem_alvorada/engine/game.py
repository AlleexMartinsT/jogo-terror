"""Game: o dono do runtime. Junta os subsistemas e roda um quadro por `tick(dt, inp)`.

Fases: title -> cutscene -> play <-> (reading | paused) -> dead | credits.
Sem GPU nem janela: o operador modal só traduz teclas em InputState e desenha o `hud_model()`.
"""
import importlib
import math
import random
from collections import deque

import bpy  # noqa: F401 - no bpy via pip, `mathutils` só existe depois deste import
from mathutils import Vector

from .. import conventions as C
from .. import layout
from .. import story
from . import collision, texts
from .ambience import Ambience
from .director import Director
from .doors import DoorManager
from .entity_runtime import EntityRuntime
from .fallbacks import FallbackNoise, NullAudio
from .flashlight import Flashlight
from .host import CutsceneHost, WorldView
from .hudmodel import build_hud_model
from .inputstate import InputState
from .interact import Interact
from .lights import LightManager
from .meter import MeterPeaks
from .player import Player
from .state import FLAG_BLACKOUT, GameState

MAX_DT = 0.1
MESSAGE_SECONDS = 3.5
BODY_KINDS = frozenset({"walk", "run", "crouch_walk", "breath_heavy", "pickup", "flash_click",
                        "battery_swap", "stairs_creak"})
CUTSCENE_REASON = {"intro": "intro_done", "blackout": "blackout_done", "garage_unlock": "unlock_done",
                   "death": "death_done", "ending": "ending_done"}
RESPAWN_HINT_SECONDS = 4.0


def _import_class(module_name, class_name):
    try:
        module = importlib.import_module(f"{__package__.rsplit('.', 1)[0]}.{module_name}")
        return getattr(module, class_name)
    except (ImportError, AttributeError) as error:
        print(f"[engine] {module_name}.{class_name} indisponível ({error})", flush=True)
        return None


class Game:
    def __init__(self, scene, quality="medium", audio=True, *, entity=True, cutscenes=True,
                 seed=1347, debug=False):
        """`entity`: True (importa entity/ai), False (dormente) ou (rig, brain_factory) para testes.
        `cutscenes`: True (importa), False (sem cutscenes) ou uma fábrica `host -> player`."""
        self.scene = scene
        self.quality = quality
        self.debug = debug
        self.seed = seed
        self.rng = random.Random(seed)
        self.state = GameState()
        self.phase = "title"
        self.skip_intro = False
        self.quit_requested = False
        self.clock = 0.0
        self.fps = 60.0
        self.error_text = ""
        self.reader_note = None
        self.message_text = ""
        self.message_alpha = 0.0
        self._message_left = 0.0
        self._silence_until = -1.0
        self.checkpoint = None
        self.current_cutscene = None
        self.cutscene_history = []        # nomes das cutscenes já iniciadas (resumo dos testes)
        self.cutscene_camera = None
        self.peak_noise = 0.0
        self.noise_log = deque(maxlen=500)     # (fonte, tipo, volume, tempo): para testes e depuração
        self.title_tip = self.rng.choice(story.TIPS)
        self._breath_loop = False
        self._heartbeat_loop = False
        self._audio_ducked = False
        self.player_cam = scene.objects.get(C.OBJ_PLAYER_CAM)

        self.collision = collision.build_collision(scene)
        self.doors = DoorManager(self, scene)
        self.audio = self._make_audio(audio)
        self.noise = self._make_noise()
        self.player = Player(self, self.collision)
        self.flashlight = Flashlight(self, scene.objects.get(C.OBJ_FLASHLIGHT), scene.objects.get(C.OBJ_VIEW_FLASH))
        self.lights = LightManager(scene)
        self.interact = Interact(self, scene)
        self.director = Director(self)
        self.ambience = Ambience(self)
        self.world_view = WorldView(self)
        self.meter = MeterPeaks()
        parts = entity if isinstance(entity, tuple) else None
        self.entity = EntityRuntime(self, enabled=bool(entity), parts=parts)
        self.host = CutsceneHost(self)
        self.cutscenes = self._make_cutscenes(cutscenes)
        self._sync_camera()

    # ---- montagem com degradação graciosa ----
    def _make_audio(self, enabled):
        if enabled:
            engine_class = _import_class("audio.engine", "AudioEngine")
            if engine_class is not None:
                try:
                    return engine_class(door_openness=self.doors.openness)
                except Exception as error:      # noqa: BLE001 - sem som é melhor que sem jogo
                    print(f"[engine] AudioEngine falhou ({error}); usando áudio nulo", flush=True)
        return NullAudio()

    def _make_noise(self):
        noise_class = _import_class("audio.noise", "NoiseSystem")
        if noise_class is not None:
            try:
                return noise_class(door_openness=self.doors.openness)
            except Exception as error:          # noqa: BLE001
                print(f"[engine] NoiseSystem falhou ({error}); usando o ruído reserva", flush=True)
        return FallbackNoise(self.doors.openness)

    def _make_cutscenes(self, cutscenes):
        if callable(cutscenes):
            return cutscenes(self.host)
        if cutscenes:
            player_class = _import_class("cutscenes", "CutscenePlayer")
            if player_class is not None:
                try:
                    return player_class(self.host)
                except Exception as error:      # noqa: BLE001
                    print(f"[engine] CutscenePlayer falhou ({error}); sem cutscenes", flush=True)
        return None

    # ---- serviços usados pelos subsistemas ----
    def sound(self, name, pos=None, volume=1.0):
        self.audio.play(name, pos, volume)

    def make_noise(self, kind, pos, loudness, sound=None, source="player"):
        """Toca o som e registra o ruído na mesma chamada, para nunca dessincronizarem."""
        loudness = max(0.0, min(1.0, loudness))
        if sound is not None:
            spatial = None if source == "player" and kind in BODY_KINDS else pos
            if isinstance(sound, tuple):
                self.audio.footstep(sound[1], loudness, spatial)       # ("footstep", piso)
            else:
                self.audio.play(sound, spatial, 0.25 + 0.75 * loudness)
        if source != "entity" and self.clock < self._silence_until:
            return
        self.noise.emit(source, kind, pos, loudness)
        self.noise_log.append((source, kind, round(loudness, 3), round(self.clock, 2)))
        if source == "player":
            self.peak_noise = max(self.peak_noise, loudness)

    def silence_noise(self, seconds):
        self._silence_until = self.clock + seconds
        self.noise.silence(seconds)

    def say(self, text, seconds=MESSAGE_SECONDS):
        self.message_text = text
        self._message_left = self._message_total = seconds

    def open_note(self, note_id):
        self.reader_note = note_id
        self.phase = "reading"

    def noise_levels(self):
        levels = self.noise.hud_levels()
        return {key: float(levels.get(key, 0.0)) for key in ("player", "ambient", "entity")}

    # ---- ciclo de vida da partida ----
    def new_game(self, skip_intro=None):
        skip_intro = self.skip_intro if skip_intro is None else skip_intro
        fresh = GameState()
        self.state.restore(fresh.snapshot())
        self.state.deaths = 0
        self._reset_world()
        self.place_player_at_start()
        self.checkpoint = None
        self.clock = 0.0
        self.director.start_new_game(skip_intro)

    def _reset_world(self):
        self.doors.reset()
        self.interact.sync_scene()
        self.lights.set_power(True, 0.0)
        self.entity.reset()
        self.ambience.reset()
        self.meter.reset()
        self.flashlight.swap_left = 0.0
        self.player.reset_body()
        self.reader_note = None
        self.message_text, self._message_left = "", 0.0

    def place_player_at_start(self):
        x, y, z = layout.PLAYER_START
        self.place_player(x, y, z, math.radians(layout.PLAYER_START_YAW_DEG))

    def place_player(self, x, y, z, yaw):
        self.player.place(x, y, z, yaw)
        self.flashlight.snap_to_camera(yaw, 0.0)
        self._sync_camera()

    def save_checkpoint(self, at_player=True):
        """Grava o estado da partida. `at_player=False` mantém a posição do checkpoint anterior: o apagão
        marca o progresso, mas o retry não deve nascer no corredor, ao lado da entidade."""
        player = self.player
        here = (player.x, player.y, player.z, player.yaw)
        previous = self.checkpoint["pos"] if self.checkpoint else here
        self.checkpoint = {"state": self.state.snapshot(), "pos": here if at_player else previous}

    def restart_from_checkpoint(self):
        """Volta ao último checkpoint (após a morte). A entidade reaparece longe do jogador."""
        if self.checkpoint is None:
            self.new_game(skip_intro=True)
            return
        self.state.restore(self.checkpoint["state"])
        self._reset_world()
        self._rebuild_world_from_state()
        x, y, z, yaw = self.checkpoint["pos"]
        self.place_player(x, y, z, yaw)
        self.end_cutscene()
        if FLAG_BLACKOUT in self.state.flags:
            self.entity.activate(self.entity.respawn_point((x, y, z)), hunt=False)
        self.phase = "play"
        self.say(texts.MSG_RESPAWN, RESPAWN_HINT_SECONDS)

    def _rebuild_world_from_state(self):
        if "garage" in self.state.unlocked:
            self.doors.snap("garage_door", 1.0)
        self.lights.set_power(FLAG_BLACKOUT not in self.state.flags, 0.0)
        self.interact.sync_scene()
        level = 2 if "garage" in self.state.unlocked else 1 if self.state.collect_complete() else 0
        self.entity.set_aggression(level)

    # ---- cutscenes ----
    def play_cutscene(self, name):
        self.current_cutscene = name
        self.cutscene_history.append(name)
        self.phase = "cutscene"
        self.audio.stop("breath_heavy")
        self.audio.stop("heartbeat")
        self._breath_loop = self._heartbeat_loop = False
        if self.cutscenes is None:
            self._run_missing_cutscene(name)
            return
        self.cutscenes.play(name)
        if not self.cutscenes.active:
            self.director.on_cutscene_finished(CUTSCENE_REASON[name])

    def _run_missing_cutscene(self, name):
        """Sem o módulo cutscenes: aplica só o efeito de jogo que a cena teria causado."""
        if name == "blackout":
            self.lights.set_power(False, 0.0)
            self.entity.activate()
        elif name == "garage_unlock":
            self.doors.set_openness("garage_door", 1.0)
        elif name == "death":
            self.sound("death_hit")
            self.sound("ent_scream")
        self.director.on_cutscene_finished(CUTSCENE_REASON[name])

    def end_cutscene(self):
        self.current_cutscene = None
        self.set_active_camera(None)

    def set_active_camera(self, obj):
        self.cutscene_camera = obj
        self.scene.camera = obj or self.player_cam

    # ---- quadro ----
    def tick(self, dt, inp):
        dt = min(max(dt, 0.0), MAX_DT)
        if dt > 0:
            self.fps += (1.0 / dt - self.fps) * 0.05
        self._tick_message(dt)
        self._duck_audio_when_paused()
        {"title": self._tick_title, "cutscene": self._tick_cutscene, "play": self._tick_play,
         "reading": self._tick_reading, "paused": self._tick_paused, "dead": self._tick_dead,
         "credits": self._tick_credits}[self.phase](dt, inp)
        self._sync_camera()
        self._update_listener()
        self.meter.update(dt, self.noise_levels())

    def _tick_message(self, dt):
        self._message_left = max(0.0, self._message_left - dt)
        if self._message_left <= 0:
            self.message_text, self.message_alpha = "", 0.0
            return
        elapsed = self._message_total - self._message_left
        self.message_alpha = min(1.0, elapsed / 0.15, self._message_left / 0.6)

    def _tick_title(self, dt, inp):
        self._idle_world(dt)
        if inp.cancel:
            self.quit_requested = True
        elif inp.confirm:
            self.new_game()

    def _tick_cutscene(self, dt, inp):
        if inp.skip and self.cutscenes is not None:
            self.cutscenes.skip()
        if self.cutscenes is not None:
            self.cutscenes.update(dt)
            if self.phase == "cutscene" and self.current_cutscene and not self.cutscenes.active:
                self.director.on_cutscene_finished(CUTSCENE_REASON[self.current_cutscene])
        if self.phase == "cutscene":
            self._idle_world(dt)

    def _idle_world(self, dt):
        """O que continua vivo fora do jogo: portas, luzes, ruído e a lanterna (sem viewmodel)."""
        self.clock += dt
        self.doors.update(dt)
        self.lights.update(dt, self.player.room_id)
        self.noise.update(dt)
        self.flashlight.update(dt, self.player.yaw, self.player.pitch, show_viewmodel=False)

    def _tick_play(self, dt, inp):
        if inp.pause:
            self.phase = "paused"
            return
        self.clock += dt
        player = self.player
        player.update(dt, inp)
        if inp.flashlight:
            self.flashlight.toggle()
        if inp.reload:
            self.flashlight.reload()
        lateral, vertical = player.bob_offset()
        self.flashlight.update(dt, player.yaw, player.pitch, bob=(lateral, vertical))
        self.doors.update(dt, player)
        self.lights.update(dt, player.room_id)
        self.noise.update(dt)
        self._tick_entity(dt)
        self._tick_audio()
        if self.phase != "play":
            return
        self.interact.update(player.eye_pos, player.forward())
        if inp.interact and self.interact.current is not None:
            self.interact.use(self.interact.current)
        if self.phase == "play":
            self.director.update(dt)
            self.ambience.update(dt, FLAG_BLACKOUT in self.state.flags)

    def _tick_reading(self, dt, inp):
        if inp.interact or inp.confirm or inp.cancel or inp.pause or inp.skip:
            self.reader_note = None
            self.phase = "play"
            self.sound("paper_rustle", None, 0.6)

    def _tick_paused(self, dt, inp):
        if inp.cancel:
            self.quit_requested = True
        elif inp.confirm or inp.pause:
            self.phase = "play"

    def _tick_dead(self, dt, inp):
        self._idle_world(dt)
        if inp.cancel:
            self.quit_requested = True
        elif inp.confirm:
            self.restart_from_checkpoint()

    def _tick_credits(self, dt, inp):
        self._idle_world(dt)
        if inp.cancel:
            self.quit_requested = True
        elif inp.confirm:
            self.phase = "title"

    # ---- entidade e áudio por quadro ----
    def _senses(self):
        player = self.player
        return self.entity.senses_class(
            player_pos=player.feet, player_yaw=player.yaw,
            player_level=self.noise.level_at(player.feet, "player"), player_speed=player.speed,
            player_crouching=player.crouching,
            flashlight_on=self.state.flashlight_on and self.flashlight.intensity > 0.05,
            flashlight_dir=player.forward())

    def _tick_entity(self, dt):
        self.noise.set_listener(self.player.feet)
        output = self.entity.update(dt, self._senses())
        if output is not None and output.kill:
            self.director.on_player_killed()

    def _duck_audio_when_paused(self):
        paused = self.phase == "paused"
        if paused != self._audio_ducked:
            self._audio_ducked = paused
            self.audio.set_master(0.25 if paused else 1.0)

    def _tick_audio(self):
        player = self.player
        hard = player.breathing_hard
        if hard != self._breath_loop:
            self._breath_loop = hard
            if not hard:
                self.audio.stop("breath_heavy")
        if hard:
            self.audio.loop("breath_heavy", "breath_heavy", None, min(1.0, 1.2 - player.stamina))
        danger = self.entity.danger(player.feet)
        beating = danger > 0.15
        if beating:
            self.audio.loop("heartbeat", "heartbeat", None, min(1.0, danger), 0.9 + 0.35 * danger)
        elif self._heartbeat_loop:
            self.audio.stop("heartbeat")
        self._heartbeat_loop = beating

    # ---- câmera ----
    def _sync_camera(self):
        cam = self.player_cam
        if self.cutscene_camera is None and cam is not None:
            position, rotation = self.player.camera_pose()
            cam.location = position
            cam.rotation_euler = rotation

    def _update_listener(self):
        """O ouvinte do áudio acompanha a câmera ativa (jogador ou cutscene). Uma vez por quadro."""
        if self.cutscene_camera is None:
            self.audio.update_listener(self.player.eye_pos, self.player.yaw)
            return
        matrix = collision.world_matrix(self.cutscene_camera)
        forward = matrix.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        self.audio.update_listener(tuple(matrix.translation), math.atan2(-forward.x, forward.y))

    # ---- interface ----
    def hud_model(self):
        return build_hud_model(self)

    def report_error(self, error):
        self.error_text = f"{type(error).__name__}: {error}"

    def debug_cheat(self, name):
        """Atalhos de teste (só com --debug): give_all, to_garage, entity_off."""
        state = self.state
        if name == "give_all":
            state.has_flashlight, state.has_key, state.has_map = True, True, True
            state.batteries_found, state.spare_batteries = 3, 3
            state.collected |= {"FLASHLIGHT", "KEY", "MAP", "BATTERY_1", "BATTERY_2", "BATTERY_3"}
            self.interact.sync_scene()
            self.say("[debug] tudo coletado")
        elif name == "to_garage":
            self.place_player(13.4, 5.85, 0.0, math.radians(-90))
        elif name == "entity_off":
            self.entity.reset()
        elif name == "blackout":
            self.play_cutscene("blackout")

    def leave_scene(self):
        """Devolve a cena editável ao estado do arquivo: luzes acesas, portas fechadas, itens à vista."""
        self.state.collected.clear()
        self.interact.sync_scene()
        self.doors.reset()
        self.lights.restore_all()
        self.flashlight.restore_scene()
        self.entity.reset()
        self.set_active_camera(None)

    def shutdown(self):
        self.audio.shutdown()


__all__ = ["Game", "InputState"]
