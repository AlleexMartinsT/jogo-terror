"""Camada de UI sem GUI: valida por introspecção as chamadas de API que só rodam numa janela real
(blf, gpu, Window, eventos, shading, overlay, operadores de tela) e simula a sessão com janela falsa.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_engine_ui_api.py
"""
import inspect
import os
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_engine_fakes as fk  # noqa: E402
from test_engine_fakes import make_game, start_playing  # noqa: E402

import blf  # noqa: E402
import bpy  # noqa: E402

from sem_alvorada.engine import canvas, controls, operator, windowing  # noqa: E402
from sem_alvorada.engine.session import MAX_CONSECUTIVE_ERRORS, PlaySession  # noqa: E402


def enum_ids(prop):
    return {item.identifier for item in prop.enum_items}


def test_space_shading_overlay_properties_exist():
    space_props = {p.identifier for p in bpy.types.SpaceView3D.bl_rna.properties}
    for name in ("show_region_ui", "show_region_toolbar", "show_region_header", "show_region_tool_header",
                 "show_region_hud", "show_gizmo", "shading", "overlay", "region_3d", "camera"):
        assert name in space_props, name
    assert set(windowing.SPACE_FLAGS) - {"show_region_asset_shelf"} <= space_props
    shading = bpy.types.View3DShading.bl_rna.properties
    assert "RENDERED" in enum_ids(shading["type"]) and "ALWAYS" in enum_ids(shading["use_compositor"])
    assert set(windowing.SHADING_FLAGS) <= set(shading.keys())
    assert "show_overlays" in bpy.types.View3DOverlay.bl_rna.properties
    assert "CAMERA" in enum_ids(bpy.types.RegionView3D.bl_rna.properties["view_perspective"])
    assert "show_fullscreen" in bpy.types.Screen.bl_rna.properties


def test_window_and_operator_api():
    functions = bpy.types.Window.bl_rna.functions
    for name in ("cursor_warp", "cursor_modal_set", "cursor_modal_restore"):
        assert name in functions, name
    assert [p.identifier for p in functions["cursor_warp"].parameters] == ["x", "y"]
    assert "NONE" in enum_ids(functions["cursor_modal_set"].parameters[0])
    assert "use_hide_panels" in bpy.ops.screen.screen_full_area.get_rna_type().properties
    assert hasattr(bpy.ops.view3d, "view_center_camera")
    assert hasattr(bpy.types.Context, "temp_override")
    timer_doc = bpy.app.timers.register.__doc__
    assert "persistent" in timer_doc and "first_interval" in timer_doc
    assert "event_timer_add" in bpy.types.WindowManager.bl_rna.functions
    assert hasattr(bpy.types.SpaceView3D, "draw_handler_add") and hasattr(bpy.types.SpaceView3D, "draw_handler_remove")
    operator.register()
    assert {"quality", "skip_intro", "debug"} <= set(bpy.ops.sa.play.get_rna_type().properties.keys())


def test_event_types_used_by_controls_exist():
    valid = enum_ids(bpy.types.Event.bl_rna.properties["type"])
    used = set(controls.MOVE_KEYS) | controls.RUN_KEYS | controls.CROUCH_KEYS | set(controls.EDGE_KEYS)
    used |= set(controls.DEBUG_KEYS) | {"TIMER", "MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "WINDOW_DEACTIVATE"}
    assert used <= valid, used - valid
    values = enum_ids(bpy.types.Event.bl_rna.properties["value"])
    assert {"PRESS", "RELEASE", "DOUBLE_CLICK"} <= values
    event_props = {p.identifier for p in bpy.types.Event.bl_rna.properties}
    assert {"mouse_x", "mouse_y", "is_repeat", "type", "value"} <= event_props


def test_blf_and_gpu_signatures():
    expected = {"size": ("fontid", "size"), "color": ("fontid", "r", "g", "b", "a"),
                "position": ("fontid", "x", "y", "z"), "draw": ("fontid", "text"),
                "dimensions": ("fontid", "text"), "shadow": ("fontid", "level", "r", "g", "b", "a"),
                "shadow_offset": ("fontid", "x", "y"), "enable": ("fontid", "option"), "load": ("filepath",)}
    for name, params in expected.items():
        doc = getattr(blf, name).__doc__
        signature = re.search(r"function:: %s\(([^)]*)\)" % name, doc).group(1)
        assert tuple(p.strip() for p in signature.split(",")) == params, (name, signature)
    assert hasattr(blf, "SHADOW")
    import gpu
    assert hasattr(gpu.state, "blend_set") and hasattr(gpu.shader, "from_builtin")
    from gpu_extras.batch import batch_for_shader
    assert "indices" in inspect.signature(batch_for_shader).parameters


def test_gpu_canvas_replays_recorded_operations_in_order():
    """GpuCanvas.flush chama blf/gpu com os mesmos dados que o Canvas gravou (com gpu e blf substituídos)."""
    calls = []

    class FakeBlf:
        SHADOW = 1

        def __getattr__(self, name):
            return lambda *args: calls.append((name, args)) or (10.0, 10.0)

    class FakeBatch:
        def draw(self, shader):
            calls.append(("batch.draw", shader))

    fake_gpu = SimpleNamespace(state=SimpleNamespace(blend_set=lambda mode: calls.append(("blend", mode))),
                               shader=SimpleNamespace(from_builtin=lambda name: name))
    fake_extras = SimpleNamespace(batch_for_shader=lambda shader, kind, content, indices=None: (
        calls.append(("batch", kind, len(content["pos"]), len(content["color"]), len(indices))) or FakeBatch()))
    surface = canvas.GpuCanvas(1280, 720, 1)
    surface.rect(0, 0, 10, 10, (1, 1, 1, 1))
    surface.rect(20, 0, 10, 10, (1, 0, 0, 1))
    surface.text(5, 5, "oi", 12, (1, 1, 1, 1))
    surface.rect(0, 0, 5, 5, (0, 0, 0, 1))
    saved = {name: sys.modules.get(name) for name in ("blf", "gpu", "gpu_extras", "gpu_extras.batch")}
    sys.modules.update({"blf": FakeBlf(), "gpu": fake_gpu, "gpu_extras": fake_extras, "gpu_extras.batch": fake_extras})
    try:
        surface.flush()
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    kinds = [c[0] for c in calls]
    assert kinds[0] == "blend" and kinds[-1] == "blend"
    batches = [c for c in calls if c[0] == "batch"]
    assert [b[2] for b in batches] == [8, 4] and all(b[4] == 4 for b in batches[:1]), batches
    assert kinds.index("draw") > kinds.index("batch") and kinds.count("batch") == 2
    assert not surface.ops


class FakeWindow:
    def __init__(self):
        self.warps = []

    def cursor_warp(self, x, y):
        self.warps.append((x, y))


class FakeView:
    def __init__(self):
        self.region = SimpleNamespace(x=0, y=0, width=1280, height=720)
        self.window = FakeWindow()
        self.area = SimpleNamespace(tag_redraw=lambda: None)
        self.restored = 0
        self.center = (640, 360)

    def warp_to_center(self):
        self.window.cursor_warp(*self.center)

    def sync_size(self):
        pass

    def restore(self):
        self.restored += 1


def event(kind, value="NOTHING", x=0, y=0, repeat=False):
    return SimpleNamespace(type=kind, value=value, mouse_x=x, mouse_y=y, is_repeat=repeat)


def make_session(**kwargs):
    game = start_playing(make_game(world=True, **kwargs))
    scene = game.scene
    context = SimpleNamespace(window=None, scene=scene, window_manager=SimpleNamespace(
        event_timer_remove=lambda timer: None))
    session = PlaySession(context, "medium", False, False)
    session.game, session.view = game, FakeView()
    session._last_mouse = session.view.center          # o que start() faz
    session.model = game.hud_model()
    return session


def test_session_keys_mouse_and_timer():
    session = make_session()
    game = session.game
    start = game.player.feet
    session.handle_event(event("W", "PRESS"))
    for _ in range(45):
        session.handle_event(event("TIMER"))
    assert session.controls.inp.move_y == 1.0
    session.handle_event(event("W", "RELEASE"))
    assert session.controls.inp.move_y == 0.0
    yaw = game.player.yaw
    session.handle_event(event("MOUSEMOVE", x=640 + 100, y=360))     # 100 px à direita
    session.handle_event(event("TIMER"))
    assert game.player.yaw < yaw, "mouse à direita deveria virar para a direita (yaw diminui)"
    assert abs((yaw - game.player.yaw) - 100 * controls.MOUSE_SENSITIVITY) < 1e-6
    session.handle_event(event("MOUSEMOVE", x=640 + 100 + 200, y=360 + 50))        # longe do centro: reposiciona
    assert session.view.window.warps, "não reposicionou o cursor"
    session.handle_event(event("MOUSEMOVE", x=640, y=360))                        # eco do warp: sem giro
    session.handle_event(event("TIMER"))
    yaw_after = game.player.yaw
    session.handle_event(event("TIMER"))
    assert game.player.yaw == yaw_after
    assert session.model["phase"] == "play" and game.player.feet != start
    assert session.errors_in_a_row == 0 and not game.error_text


def test_session_survives_warp_that_does_nothing():
    session = make_session()
    game = session.game
    yaw = game.player.yaw
    session.handle_event(event("MOUSEMOVE", x=1000, y=360))               # aciona o warp (que não vai funcionar)
    session.handle_event(event("MOUSEMOVE", x=1010, y=360))               # o cursor continuou por perto
    session.handle_event(event("TIMER"))
    assert session.errors_in_a_row == 0
    assert abs((yaw - game.player.yaw) - (1000 - 640 + 10) * controls.MOUSE_SENSITIVITY) < 1e-6, (
        "sem warp, o deslocamento deve continuar contando")


def test_session_pause_then_second_escape_quits_and_restores():
    session = make_session()
    assert session.handle_event(event("ESC", "PRESS"))
    session.handle_event(event("TIMER"))
    assert session.game.phase == "paused"
    session.handle_event(event("ESC", "RELEASE"))
    keep_going = session.handle_event(event("ESC", "PRESS"))
    still = session.handle_event(event("TIMER")) if keep_going else False
    assert not still and session.finished and session.view.restored == 1
    assert session.handle_event(event("TIMER")) is False


def test_session_window_focus_loss_pauses_and_releases_keys():
    session = make_session()
    session.handle_event(event("W", "PRESS"))
    session.handle_event(event("WINDOW_DEACTIVATE"))
    assert session.game.phase == "paused" and session.controls.inp.move_y == 0.0


def test_session_error_is_reported_once_then_shows_and_exits():
    session = make_session()
    game = session.game

    def broken_tick(dt, inp):
        raise ValueError("falha de teste")

    game.tick = broken_tick
    printed = []
    import builtins
    original_print = builtins.print
    builtins.print = lambda *a, **k: printed.append(a)
    try:
        assert session.handle_event(event("TIMER"))
        assert game.error_text.startswith("ValueError") and session.model["error"]
        for _ in range(3):
            session.handle_event(event("TIMER"))
        assert len([p for p in printed if p and "ERRO durante a partida" in str(p[0])]) == 1, "registrou mais de uma vez"
    finally:
        builtins.print = original_print
    assert session.handle_event(event("ESC", "PRESS")) is False, "Esc com erro deveria sair na hora"
    assert session.finished and session.view.restored == 1
    session2 = make_session()
    session2.game.tick = broken_tick
    builtins.print = lambda *a, **k: None
    try:
        alive = True
        for _ in range(MAX_CONSECUTIVE_ERRORS + 2):
            alive = session2.handle_event(event("TIMER"))
            if not alive:
                break
    finally:
        builtins.print = original_print
    assert not alive and session2.view.restored == 1, "erros em sequência deveriam devolver a interface"


def test_leave_scene_restores_file_state():
    game = start_playing(make_game(world=True, items=True, lights=True))
    game.debug_cheat("give_all")
    game.state.flashlight_on = True
    game.lights.set_power(False, 0.0)
    fk.run_for(game, 0.5)
    game.doors.snap("kids_hall", 1.0)
    game.leave_scene()
    scene = game.scene
    assert all(not o.hide_viewport for o in scene.objects if o.name.startswith("Item_"))
    assert all(not l.obj.hide_viewport and l.obj.data.energy == l.base_energy for l in game.lights.lights)
    assert game.doors.openness("kids_hall") == 0.0 and scene.camera is game.player_cam
    assert scene.objects["ViewModel_Flashlight"].hide_viewport


# --------------------------------------------------------------------------
# PlayView com um bpy falso: entra e sai do modo de jogo devolvendo a interface
# --------------------------------------------------------------------------
class FakeSpace:
    def __init__(self):
        for name in windowing.SPACE_FLAGS:
            setattr(self, name, True)
        self.shading = SimpleNamespace(type="SOLID", use_compositor="DISABLED")
        self.overlay = SimpleNamespace(show_overlays=True)
        self.region_3d = SimpleNamespace(view_perspective="PERSP")


class FakeScreenWorld:
    """Uma janela com um editor 3D; screen_full_area troca a tela por uma temporária (e de volta)."""

    def __init__(self):
        self.space = FakeSpace()
        self.region = SimpleNamespace(type="WINDOW", x=10, y=20, width=1600, height=900)
        self.area = SimpleNamespace(type="VIEW_3D", regions=[self.region], spaces=SimpleNamespace(active=self.space),
                                    tag_redraw=lambda: None)
        self.window = SimpleNamespace(screen=SimpleNamespace(show_fullscreen=False, areas=[self.area]),
                                      cursor_log=[], warp_log=[])
        self.window.cursor_modal_set = lambda name: self.window.cursor_log.append(("set", name))
        self.window.cursor_modal_restore = lambda: self.window.cursor_log.append(("restore",))
        self.window.cursor_warp = lambda x, y: self.window.warp_log.append((x, y))
        self.toggles = 0
        self.fail_centering = False
        self.manager = SimpleNamespace(windows=[self.window])
        self.ops = SimpleNamespace(
            screen=SimpleNamespace(screen_full_area=self._toggle),
            view3d=SimpleNamespace(view_center_camera=self._center))
        self.context = SimpleNamespace(window_manager=self.manager, temp_override=self._override)

    def _override(self, **kwargs):
        import contextlib
        return contextlib.nullcontext()

    def _toggle(self, use_hide_panels=False):
        self.toggles += 1
        self.window.screen.show_fullscreen = not self.window.screen.show_fullscreen

    def _center(self):
        if self.fail_centering:
            raise RuntimeError("poll falhou")


def with_fake_bpy(world, action):
    real = windowing.bpy
    windowing.bpy = SimpleNamespace(context=world.context, ops=world.ops)
    try:
        return action()
    finally:
        windowing.bpy = real


def test_playview_enter_then_restore_brings_back_the_interface():
    world = FakeScreenWorld()
    scene = fk.fresh_scene()
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    original_camera = scene.camera = None
    view = windowing.PlayView(world.window, world.area, scene)
    with_fake_bpy(world, lambda: view.enter(scene.objects["PlayerCam"]))
    space = world.space
    assert world.toggles == 1 and view.made_fullscreen
    assert not any(getattr(space, name) for name in windowing.SPACE_FLAGS) and not space.overlay.show_overlays
    assert space.shading.type == "RENDERED" and space.shading.use_compositor == "ALWAYS"
    assert space.region_3d.view_perspective == "CAMERA" and scene.camera.name == "PlayerCam"
    assert scene.render.resolution_y == 720 and abs(scene.render.resolution_x / 720 - 1600 / 900) < 0.01
    assert world.window.cursor_log == [("set", "NONE")] and world.window.warp_log == [(10 + 800, 20 + 450)]
    with_fake_bpy(world, view.restore)
    assert world.toggles == 2 and not world.window.screen.show_fullscreen
    assert all(getattr(space, name) for name in windowing.SPACE_FLAGS) and space.overlay.show_overlays
    assert space.shading.type == "SOLID" and space.shading.use_compositor == "DISABLED"
    assert space.region_3d.view_perspective == "PERSP" and scene.camera is original_camera
    assert (scene.render.resolution_x, scene.render.resolution_y) == (1280, 720)
    assert world.window.cursor_log[-1] == ("restore",)
    with_fake_bpy(world, view.restore)
    assert world.toggles == 2, "restaurar duas vezes não pode alternar a tela de novo"


def test_playview_tolerates_failures_and_still_unfullscreens():
    world = FakeScreenWorld()
    world.fail_centering = True
    scene = fk.fresh_scene()
    view = windowing.PlayView(world.window, world.area, scene)
    with_fake_bpy(world, lambda: view.enter(scene.objects["PlayerCam"]))
    assert view._saved, "view_center_camera falhando não pode abortar a entrada"
    del world.space.shading
    broken = windowing.PlayView(FakeScreenWorld().window, world.area, scene)
    broken.made_fullscreen = True
    try:
        with_fake_bpy(world, lambda: broken.enter(scene.objects["PlayerCam"]))
    except AttributeError:
        pass
    with_fake_bpy(world, broken.restore)
    assert not broken.made_fullscreen, "entrada interrompida deve ainda devolver a tela cheia"


def test_playview_resizes_frame_when_region_changes():
    world = FakeScreenWorld()
    scene = fk.fresh_scene()
    view = windowing.PlayView(world.window, world.area, scene)
    with_fake_bpy(world, lambda: view.enter(scene.objects["PlayerCam"]))
    world.region.width, world.region.height = 1920, 1080
    with_fake_bpy(world, view.sync_size)
    assert abs(scene.render.resolution_x / scene.render.resolution_y - 16 / 9) < 0.01


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok      {name}", flush=True)
        except Exception as error:      # noqa: BLE001
            import traceback
            failures += 1
            print(f"FALHOU  {name}: {error!r}", flush=True)
            traceback.print_exc()
    print(f"{len(tests) - failures}/{len(tests)} testes de UI passaram")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
