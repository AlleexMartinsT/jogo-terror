"""Entra e sai do modo de jogo na interface do Blender, guardando tudo o que muda para restaurar.

Cada passo é defensivo: uma propriedade que não exista nesta versão do Blender é ignorada,
e a restauração roda mesmo que a entrada tenha falhado pela metade.
"""
import bpy

RENDER_HEIGHT = 720
SPACE_FLAGS = ("show_region_ui", "show_region_toolbar", "show_region_header", "show_region_tool_header",
               "show_region_hud", "show_region_asset_shelf", "show_gizmo")
SHADING_FLAGS = ("type", "use_compositor")


def find_view3d(window_manager):
    """(janela, área, região WINDOW) do primeiro editor 3D encontrado, ou None."""
    for window in window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                if region is not None:
                    return window, area, region
    return None


def _region_of(area):
    return next(r for r in area.regions if r.type == "WINDOW")


class PlayView:
    """Estado da interface antes do jogo + os passos para entrar e sair dele."""

    def __init__(self, window, area, scene):
        self.window = window
        self.area = area
        self.scene = scene
        self.region = _region_of(area)
        self.made_fullscreen = False
        self._saved = {}

    @property
    def space(self):
        return self.area.spaces.active

    # ---- entrar ----
    def enter(self, camera):
        self._enter_fullscreen()
        space = self.space
        self._saved = {
            "space": {name: getattr(space, name) for name in SPACE_FLAGS if hasattr(space, name)},
            "shading": {name: getattr(space.shading, name) for name in SHADING_FLAGS if hasattr(space.shading, name)},
            "overlays": space.overlay.show_overlays,
            "perspective": space.region_3d.view_perspective,
            "camera": self.scene.camera,
            "resolution": (self.scene.render.resolution_x, self.scene.render.resolution_y,
                           self.scene.render.resolution_percentage),
        }
        for name in self._saved["space"]:
            setattr(space, name, False)
        space.overlay.show_overlays = False
        space.shading.type = "RENDERED"
        if hasattr(space.shading, "use_compositor"):
            space.shading.use_compositor = "ALWAYS"
        self._match_render_aspect()
        self.scene.camera = camera
        space.region_3d.view_perspective = "CAMERA"
        self._fit_camera_frame()
        self.window.cursor_modal_set("NONE")
        self.warp_to_center()

    def _enter_fullscreen(self):
        if self.window.screen.show_fullscreen:
            return
        try:
            with bpy.context.temp_override(window=self.window, area=self.area, region=self.region):
                bpy.ops.screen.screen_full_area(use_hide_panels=True)
            self.made_fullscreen = True
            found = find_view3d(bpy.context.window_manager)
            if found is not None and found[0] == self.window:
                self.area, self.region = found[1], found[2]
        except RuntimeError as error:
            print(f"[engine] não consegui maximizar a área 3D ({error}); seguindo sem isso", flush=True)

    def _match_render_aspect(self):
        """A vista de câmera mostra o quadro do render: iguala a proporção à da janela para preencher tudo."""
        render = self.scene.render
        aspect = self.region.width / max(self.region.height, 1)
        render.resolution_y = RENDER_HEIGHT
        render.resolution_x = max(320, round(RENDER_HEIGHT * aspect))
        render.resolution_percentage = 100

    def _fit_camera_frame(self):
        try:
            with bpy.context.temp_override(window=self.window, area=self.area, region=self.region):
                bpy.ops.view3d.view_center_camera()
        except RuntimeError as error:
            print(f"[engine] view_center_camera falhou ({error}); o quadro pode não preencher a janela", flush=True)

    # ---- mouse ----
    @property
    def center(self):
        return (self.region.x + self.region.width // 2, self.region.y + self.region.height // 2)

    def warp_to_center(self):
        self.window.cursor_warp(*self.center)

    # ---- sair ----
    def restore(self):
        """Devolve a interface ao que era. Seguro chamar mais de uma vez."""
        saved, self._saved = self._saved, {}
        steps = [self._restore_cursor]
        if saved:
            steps.append(lambda: self._restore_view(saved))
        steps.append(self._restore_fullscreen)
        for step in steps:
            try:
                step()
            except (RuntimeError, ReferenceError, AttributeError) as error:
                print(f"[engine] restauração parcial ({error})", flush=True)

    def _restore_cursor(self):
        self.window.cursor_modal_restore()

    def _restore_view(self, saved):
        space, scene = self.space, self.scene
        for name, value in saved["space"].items():
            setattr(space, name, value)
        for name, value in saved["shading"].items():
            setattr(space.shading, name, value)
        space.overlay.show_overlays = saved["overlays"]
        space.region_3d.view_perspective = saved["perspective"]
        scene.camera = saved["camera"]
        scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = saved["resolution"]

    def _restore_fullscreen(self):
        if not self.made_fullscreen:
            return
        self.made_fullscreen = False
        found = find_view3d(bpy.context.window_manager)
        if found is None:
            return
        window, area, region = found
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.screen.screen_full_area()
