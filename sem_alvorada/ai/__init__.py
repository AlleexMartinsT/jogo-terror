"""Cérebro da entidade: malha de navegação, percepção e máquina de estados.

- `nav`       grade de 0,25 m por andar, A* e suavização (`NavGrid`)
- `brain`     `EntityBrain` (estados dormant, patrol, investigate, stalk, chase, search, attack)
- `worldview` o que o cérebro pede ao engine + `LayoutWorldView` (só planta) para testes
Nada aqui exige bpy, exceto `build` (que grava a malha assada no Text `SA_NAV`).
"""
from .brain import BrainOutput, EntityBrain
from .nav import NavGrid
from .perception import Senses
from .tuning import BrainTuning
from .worldview import LayoutWorldView, WorldView

__all__ = ["BrainOutput", "BrainTuning", "EntityBrain", "LayoutWorldView", "NavGrid", "Senses", "WorldView", "build"]


def build(ctx):
    """Assa a malha de navegação (planta + proxies COL_* da cena) no Text `SA_NAV`."""
    import bpy

    from .. import conventions as C
    from . import nav

    proxies = [o for o in bpy.data.objects if o.name.startswith(C.N_COL) and o.type == "MESH"]
    footprints = nav.collision_footprints(proxies)
    grid, clearance = nav.bake(footprints, log=ctx.log)
    text = bpy.data.texts.get(nav.TEXT_NAME) or bpy.data.texts.new(nav.TEXT_NAME)
    text.clear()
    text.write(grid.to_json())
    walkable = {layer: int(grid.walk[layer].sum()) for layer in grid.walk}
    ctx.log(f"malha assada: {len(proxies)} proxies, folga {clearance:.2f} m, células andáveis {walkable}")
