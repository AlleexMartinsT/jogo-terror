"""Uma partida na GUI: liga o Game, os controles, o mouse capturado e o HUD a uma janela do Blender.

O operador `sa.play` é só uma casca: eventos entram em `handle_event`, o desenho sai por `draw`.
Regra de ouro deste arquivo: o usuário nunca fica preso. Qualquer exceção é registrada, mostrada
no HUD e, se insistir, encerra a partida e devolve a interface.
"""
import time
import traceback

import bpy

from .. import conventions as C
from . import canvas, screens
from .controls import Controls
from .game import Game
from .windowing import PlayView

TICK_SECONDS = 1.0 / 60.0
MAX_FRAME = 0.1
MAX_CONSECUTIVE_ERRORS = 90
RECENTER_FRACTION = 0.18       # só reposiciona o cursor quando ele se afasta do centro por mais que isso


class PlaySession:
    def __init__(self, context, quality="medium", skip_intro=False, debug=False):
        self.context = context
        self.window = context.window
        self.scene = context.scene
        self.debug = debug
        self.view = None
        self.game = None
        self.controls = Controls(debug=debug)
        self.model = None
        self.timer = None
        self.draw_handle = None
        self.font_id = 0
        self.errors_in_a_row = 0
        self.last_error = ""
        self.draw_failed = False
        self.finished = False
        self._last_time = time.perf_counter()
        self._last_mouse = None
        self._pre_warp = None
        self._quality = quality
        self._skip_intro = skip_intro

    # ---- ciclo de vida ----
    def start(self, window, area):
        self.window = window
        self.view = PlayView(window, area, self.scene)
        self._apply_quality()
        self.game = Game(self.scene, quality=self._quality, audio=True, debug=self.debug)
        self.game.skip_intro = self._skip_intro
        self.view.enter(self.scene.objects[C.OBJ_PLAYER_CAM])
        self.font_id = canvas.load_hud_font()
        self.model = self.game.hud_model()
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), "WINDOW", "POST_PIXEL")
        self.timer = self.context.window_manager.event_timer_add(TICK_SECONDS, window=window)
        self._last_time = time.perf_counter()
        self._last_mouse = self.view.center

    def _apply_quality(self):
        try:
            from ..world import quality
        except ImportError:
            return
        try:
            quality.apply(self.scene, self._quality)
        except Exception as error:      # noqa: BLE001 - qualidade é opcional; o jogo precisa abrir
            print(f"[engine] world.quality.apply falhou ({error})", flush=True)

    def finish(self):
        """Encerra e restaura tudo. Idempotente."""
        if self.finished:
            return
        self.finished = True
        if self.timer is not None:
            self.context.window_manager.event_timer_remove(self.timer)
            self.timer = None
        if self.draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle, "WINDOW")
            self.draw_handle = None
        if self.game is not None:
            self._safely(self.game.leave_scene)
            self._safely(self.game.shutdown)
        if self.view is not None:
            self.view.restore()

    @staticmethod
    def _safely(action):
        try:
            action()
        except Exception:      # noqa: BLE001 - na saída tudo deve ser tentado
            traceback.print_exc()

    # ---- eventos ----
    def handle_event(self, event):
        """Devolve True enquanto a partida continua e False quando acabou."""
        if self.finished:
            return False
        try:
            self._dispatch(event)
        except Exception as error:      # noqa: BLE001 - ver docstring do módulo
            self._register_error(error)
        if self.game is not None and (self.game.quit_requested or self.errors_in_a_row > MAX_CONSECUTIVE_ERRORS):
            self.finish()
            return False
        return True

    def _dispatch(self, event):
        kind = event.type
        if kind == "TIMER":
            self._tick()
        elif kind == "MOUSEMOVE":
            self._mouse(event)
        elif kind == "WINDOW_DEACTIVATE":
            self.controls.reset()
            if self.game.phase == "play":
                self.game.phase = "paused"
        elif kind in ("INBETWEEN_MOUSEMOVE", "TIMER_REPORT"):
            return
        else:
            self._key(event)

    def _key(self, event):
        value = "PRESS" if event.value == "DOUBLE_CLICK" else event.value    # duas batidas rápidas em E contam
        if value not in ("PRESS", "RELEASE"):
            return
        if event.type == "ESC" and value == "PRESS" and self.game.error_text:
            self.game.quit_requested = True       # com o jogo em erro, Esc sai direto
            return
        self.controls.key(event.type, value, getattr(event, "is_repeat", False))

    def _mouse(self, event):
        x, y = event.mouse_x, event.mouse_y
        cx, cy = self.view.center
        if self._last_mouse is None:
            self._last_mouse = (x, y)
        if self._pre_warp is not None:
            origin, self._pre_warp = self._pre_warp, None
            if abs(x - cx) <= 3 and abs(y - cy) <= 3:     # eco do nosso próprio cursor_warp
                self._last_mouse = (x, y)
                return
            self._last_mouse = origin                     # o warp não funcionou: usa o deslocamento real
        dx, dy = x - self._last_mouse[0], y - self._last_mouse[1]
        self._last_mouse = (x, y)
        if dx or dy:
            self.controls.mouse(dx, dy)
        limit = min(self.view.region.width, self.view.region.height) * RECENTER_FRACTION
        if abs(x - cx) > limit or abs(y - cy) > limit:
            self._pre_warp = (x, y)
            self.view.warp_to_center()
            self._last_mouse = (cx, cy)

    # ---- quadro ----
    def _tick(self):
        now = time.perf_counter()
        dt = min(now - self._last_time, MAX_FRAME)
        self._last_time = now
        for request in self.controls.take_debug_requests():
            self.game.debug_cheat(request)
        try:
            self.game.tick(dt, self.controls.inp)
            self.errors_in_a_row = 0
        finally:
            self.controls.inp.clear_edges()
        self.model = self.game.hud_model()
        self.view.sync_size()
        self.view.area.tag_redraw()

    def _register_error(self, error):
        self.errors_in_a_row += 1
        message = f"{type(error).__name__}: {error}"
        if message != self.last_error:
            self.last_error = message
            print("[engine] ERRO durante a partida:", flush=True)
            traceback.print_exc()
        if self.game is not None:
            self.game.report_error(error)
            if self.model is not None:
                self.model["error"] = self.game.error_text

    # ---- desenho ----
    def draw(self):
        """Draw handler POST_PIXEL. Só desenha na área da partida e nunca lança exceção."""
        if self.finished or self.draw_failed or self.model is None:
            return
        region = bpy.context.region
        if region is None or region.as_pointer() != self.view.region.as_pointer():
            return
        try:
            surface = canvas.GpuCanvas(region.width, region.height, self.font_id)
            screens.draw_frame(surface, self.model)
            surface.flush()
        except Exception:      # noqa: BLE001 - erro de desenho não pode derrubar a partida
            self.draw_failed = True
            print("[engine] o HUD falhou e foi desligado nesta partida:", flush=True)
            traceback.print_exc()
