"""Lanterna estilo Maglite: a mesma forma serve ao item sobre o criado-mudo e ao viewmodel na mão do jogador."""
import bpy

from .. import conventions as C
from .kit import MeshBuilder

BODY_RADIUS = 0.0195
TAIL_LENGTH = 0.015
GRIP_END = 0.17
HEAD_END = 0.225
GRIP_CENTER = 0.085      # o punho fecha em volta daqui


def flashlight_shape(m):
    """Lanterna ao longo de +Z: cauda em z=0, lente em z=0.225. Metal claro, anéis de borracha e lente com brilho."""
    m.cylinder(0, 0, 0, BODY_RADIUS + 0.001, TAIL_LENGTH, "chrome", seg=10)
    m.cylinder(0, 0, TAIL_LENGTH, BODY_RADIUS, GRIP_END - TAIL_LENGTH, "chrome", seg=10)
    for z in (0.045, 0.075, 0.105, 0.135):
        m.cylinder(0, 0, z, BODY_RADIUS + 0.0015, 0.014, "flash_grip", seg=10)
    m.box(0, BODY_RADIUS + 0.003, 0.03, 0.012, 0.007, 0.022, "flash_grip")
    m.cylinder(0, 0, GRIP_END, BODY_RADIUS, HEAD_END - GRIP_END - 0.012, "chrome", seg=10, r_top=0.03)
    m.cylinder(0, 0, HEAD_END - 0.012, 0.0315, 0.012, "chrome", seg=10)
    m.cylinder(0, 0, HEAD_END - 0.004, 0.026, 0.005, "lens_glow", seg=10, caps=(True, True))


def build_item_mesh():
    """Item no chão/criado-mudo: deitado ao longo de Y, centrado."""
    m = MeshBuilder("Item_FLASHLIGHT")
    with m.at(0, -HEAD_END / 2, BODY_RADIUS, rx=-90):
        flashlight_shape(m)
    return m


def _hand(m):
    """Mão fechando o punho (em coordenadas da lanterna, eixo Z) e o antebraço saindo para trás (+Z)."""
    skin = "skin_hand"
    m.soft_box(0, -0.004, GRIP_CENTER - 0.004, 0.056, 0.05, 0.085, skin, radius=0.014, edge=0.008)
    for i in range(4):
        z = GRIP_CENTER - 0.032 + i * 0.02
        m.soft_box(0, 0.024, z, 0.05, 0.02, 0.017, skin, radius=0.007, edge=0.004)
    with m.at(0.03, 0.015, GRIP_CENTER + 0.03, rz=20, rx=-20):
        m.soft_box(0, 0, 0, 0.022, 0.018, 0.055, skin, radius=0.007, edge=0.004)
    with m.at(0, -0.01, GRIP_CENTER + 0.045, rx=-14):
        m.frustum(0, 0, 0, 0.055, 0.05, 0.075, 0.07, 0.07, "sleeve_cloth", oy=-0.01)


def build_viewmodel_mesh():
    """Origem no punho, cano para -Z local. Gira-se a forma 180 graus em X para a lente olhar para -Z."""
    m = MeshBuilder(C.OBJ_VIEW_FLASH)
    with m.at(0, 0, 0, rx=180):
        with m.at(0, 0, -GRIP_CENTER):
            flashlight_shape(m)
            _hand(m)
    return m


def make_viewmodel(ctx):
    """`ViewModel_Flashlight`: oculto na cena; o engine o pendura na câmera."""
    builder = build_viewmodel_mesh()
    obj = bpy.data.objects.new(C.OBJ_VIEW_FLASH, builder.to_mesh(C.OBJ_VIEW_FLASH))
    obj.hide_viewport = True
    obj.hide_render = True
    obj["sa_barrel_axis"] = "-Z"
    ctx.link(obj, C.COL_PLAYER)
    return obj
