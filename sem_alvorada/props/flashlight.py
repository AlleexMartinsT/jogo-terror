"""Lanterna: o item no criado-mudo e o viewmodel (a lanterna na mão do jogador).

Lanterna de alumínio de duas pilhas, ~24 cm. O corpo é uma peça torneada (perfil revolvido) com anéis de
ranhura, um trecho de moleta (relevo no material), botão de borracha ao lado, cabeça em sino com
refletor cromado e lente. No viewmodel soma-se uma mão: palma, quatro dedos que contornam o cano,
polegar sobre o botão e punho de flanela.

Orientação: a forma é construída ao longo de +Z com a cauda em z=0 e a lente em z=HEAD_END. O botão fica no
lado -Y. O item é deitado ao longo de Y (botão para cima); o viewmodel é girado 180 graus em X para a lente
olhar para -Z (a frente da câmera).
"""
import math

import bpy

from .. import conventions as C
from .. import craft
from .item_models import FINE_METAL, SMOOTH_ONLY, Assembly

BODY_RADIUS = 0.0186
HEAD_RADIUS = 0.0292
HEAD_END = 0.2068
GRIP_CENTER = 0.073          # o punho fecha em volta daqui
KNURL_UV = 250.0             # 1 m de superfície = 250 repetições da textura: um losango a cada 4 mm

_BODY_PROFILE = [
    (0.0, 0.0), (0.0100, 0.0), (0.0165, 0.0016), (0.0190, 0.0055), (0.0194, 0.0125), (0.0188, 0.0150),
    (0.0186, 0.0156), (0.0186, 0.0505), (0.0178, 0.0510), (0.0178, 0.0530), (0.0186, 0.0535),
    (0.0186, 0.0900), (0.0178, 0.0905), (0.0178, 0.0925), (0.0186, 0.0930), (0.0186, 0.1500),
    (0.0192, 0.1580), (0.0214, 0.1680), (0.0258, 0.1760), (0.0276, 0.1805), (0.0278, 0.1850),
    (0.0278, 0.2000), (0.0292, 0.2010), (0.0292, 0.2060), (0.0262, 0.2068), (0.0255, 0.2055),
]
_GRIP_PROFILE = [(0.0186, 0.0540), (0.0191, 0.0546), (0.0191, 0.0884), (0.0186, 0.0890)]
_REFLECTOR_PROFILE = [(0.0255, 0.2055), (0.0238, 0.2020), (0.0205, 0.1965), (0.0158, 0.1915),
                      (0.0108, 0.1880), (0.0062, 0.1862), (0.0, 0.1858)]


def _build_body(item):
    metal = item.part(SMOOTH_ONLY)
    metal.lathe(_BODY_PROFILE, 0, 0, 0.0, "flash_aluminum", seg=36, smooth=True, cap_top=False)
    metal.lathe(_GRIP_PROFILE, 0, 0, 0.0, "flash_knurled", seg=36, smooth=True, cap_bottom=False, cap_top=False,
                uv=KNURL_UV)
    metal.lathe(_REFLECTOR_PROFILE, 0, 0, 0.0, "chrome", seg=32, smooth=True, cap_bottom=False, cap_top=False)
    metal.sphere(0, 0, 0.1905, 0.0058, "brass", seg=12, rings=8)
    metal.cylinder(0, 0, 0.2040, 0.0258, 0.0009, "glass_clear", seg=36, smooth=True)
    detail = item.part(FINE_METAL)
    detail.torus(0, 0, 0.0030, 0.0070, 0.0013, "chrome", seg=20, seg_minor=6, rx=90)       # olhal da cinta
    rubber = item.part(craft.Finish(bevel=0.0012, bevel_segments=3, smooth_angle=70))
    rubber.soft_box(0, -BODY_RADIUS - 0.0008, 0.1160, 0.0150, 0.0100, 0.0230, "rubber", radius=0.0045,
                    edge=0.0025, corner_points=5, smooth=True)
    rubber.soft_box(0, -BODY_RADIUS - 0.0024, 0.1200, 0.0110, 0.0040, 0.0150, "rubber", radius=0.0030,
                    edge=0.0016, corner_points=5, smooth=True)


def _hand(item):
    """Mão direita segurando o cano: dedos em arco ao redor do cano, polegar sobre o botão, punho de flanela."""
    skin = item.part(craft.Finish(bevel=0.0, smooth_angle=80))
    grip_radius = 0.0193
    fingers = ((0.0925, 0.0082), (0.0732, 0.0086), (0.0540, 0.0080), (0.0364, 0.0069))   # (z, raio) do indicador ao mínimo
    for z, radius in fingers:
        path_radius = grip_radius + radius * 0.92
        angle, previous = 128.0, None
        for sweep, taper in ((74.0, 1.0), (58.0, 0.93), (44.0, 0.82)):
            nxt = angle + sweep
            start = (path_radius * math.cos(math.radians(angle)), path_radius * math.sin(math.radians(angle)), z)
            end = (path_radius * math.cos(math.radians(nxt)), path_radius * math.sin(math.radians(nxt)), z)
            skin.tube(start, end, radius * taper, "skin_hand", seg=10, r_end=radius * taper * 0.94, smooth=True)
            skin.sphere(*end, radius * taper * 0.97, "skin_hand", seg=10, rings=6)
            angle = nxt
        skin.sphere(path_radius * math.cos(math.radians(128)), path_radius * math.sin(math.radians(128)), z,
                    radius * 1.08, "skin_hand", seg=10, rings=6)
    skin.soft_box(0.002, 0.0345, 0.022, 0.058, 0.021, 0.086, "skin_hand", radius=0.016, edge=0.008,
                  corner_points=5, smooth=True)
    skin.tube((0.024, 0.022, 0.016), (0.003, -0.0232, 0.052), 0.0112, "skin_hand", seg=10, r_end=0.0092, smooth=True)
    skin.tube((0.003, -0.0232, 0.052), (0.004, -0.0224, 0.098), 0.0092, "skin_hand", seg=10, r_end=0.0072, smooth=True)
    skin.sphere(0.004, -0.0224, 0.098, 0.0072, "skin_hand", seg=10, rings=6)
    skin.box(0.004, -0.0293, 0.0925, 0.0074, 0.0016, 0.0092, "paper_white")                      # unha
    cuff = item.part(craft.Finish(bevel=0.0, smooth_angle=80))
    elbow = (0.060, 0.064, -0.150)
    cuff.tube((0.016, 0.0355, 0.012), (0.036, 0.050, -0.060), 0.0285, "skin_hand", seg=14, r_end=0.0300, smooth=True)
    cuff.tube((0.024, 0.041, -0.012), elbow, 0.0385, "sleeve_cloth", seg=16, r_end=0.0455, smooth=True)
    cuff.torus(*(0.024, 0.041, -0.012), 0.0375, 0.0050, "sleeve_cloth", seg=22, seg_minor=7, rx=-62, ry=-14)


def flashlight_shape(item, hand=False):
    _build_body(item)
    if hand:
        _hand(item)


def build_item_mesh():
    """Lanterna deitada no criado-mudo: eixo ao longo de Y, botão para cima, apoiada na cabeça e na cauda."""
    item = Assembly(C.N_ITEM + C.ITEM_FLASHLIGHT)
    lean = math.degrees(math.asin((HEAD_RADIUS - 0.0194) / HEAD_END))
    with item.at(0.0, -HEAD_END / 2, HEAD_RADIUS, rx=lean):
        with item.at(rx=-90):
            flashlight_shape(item)
    return item


def build_viewmodel_mesh():
    """Origem no punho, cano para -Z local. Gira-se a forma 180 graus em X para a lente olhar para -Z."""
    item = Assembly(C.OBJ_VIEW_FLASH)
    with item.at(rx=180):
        with item.at(0.0, 0.0, -GRIP_CENTER):
            flashlight_shape(item, hand=True)
    return item


def make_viewmodel(ctx):
    """`ViewModel_Flashlight`: oculto na cena; o engine o pendura na câmera."""
    builder = build_viewmodel_mesh()
    obj = bpy.data.objects.new(C.OBJ_VIEW_FLASH, builder.to_mesh(C.OBJ_VIEW_FLASH))
    obj.hide_viewport = True
    obj.hide_render = True
    obj["sa_barrel_axis"] = "-Z"
    ctx.link(obj, C.COL_PLAYER)
    return obj
