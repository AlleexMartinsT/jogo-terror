"""Lanterna: o item no criado-mudo e o viewmodel (a lanterna na mão do jogador).

Lanterna de alumínio de duas pilhas, ~24 cm. O corpo é uma peça torneada (perfil revolvido) com anéis de
ranhura, um trecho de moleta (relevo no material), botão de borracha ao lado, cabeça em sino com
refletor cromado e lente. O viewmodel não traz mão nem manga: a mão é do corpo do jogador (`body`), que
a põe em volta do cano. Ele vem em dois objetos, o cano e a tampa da cauda, porque a tampa abre na troca
de pilhas (dobradiça no lado direito da boca do cano).

Orientação: a forma é construída ao longo de +Z com a cauda em z=0 e a lente em z=HEAD_END. O botão fica no
lado -Y. O item é deitado ao longo de Y (botão para cima); o viewmodel é girado 180 graus em X para a lente
olhar para -Z (a frente da câmera), com a origem no centro do punho.
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
CAP_END = 0.0156             # a tampa da cauda vai até aqui; dali em diante é o cano
VIEWMODEL_SEG = 24           # a lanterna na mão aparece grande, mas o orçamento dela é de ~2,6 mil triângulos
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


def _build_body(item, seg=36, split=False, eyelet=True, bevel_segments=3):
    """Corpo da lanterna. Com `split` o cano termina aberto em CAP_END e a tampa fica por conta de `_build_cap`."""
    metal = item.part(SMOOTH_ONLY)
    cut = next(i for i, (_r, z) in enumerate(_BODY_PROFILE) if z >= CAP_END - 1e-9)
    profile = _BODY_PROFILE[cut:] if split else _BODY_PROFILE
    metal.lathe(profile, 0, 0, 0.0, "flash_aluminum", seg=seg, smooth=True, cap_top=False, cap_bottom=not split)
    metal.lathe(_GRIP_PROFILE, 0, 0, 0.0, "flash_knurled", seg=seg, smooth=True, cap_bottom=False, cap_top=False,
                uv=KNURL_UV)
    metal.lathe(_REFLECTOR_PROFILE, 0, 0, 0.0, "chrome", seg=seg - 4, smooth=True, cap_bottom=False, cap_top=False)
    metal.sphere(0, 0, 0.1905, 0.0058, "brass", seg=12, rings=8)
    metal.cylinder(0, 0, 0.2040, 0.0258, 0.0009, "glass_clear", seg=seg, smooth=True)
    if eyelet:
        detail = item.part(FINE_METAL)
        detail.torus(0, 0, 0.0030, 0.0070, 0.0013, "chrome", seg=20, seg_minor=6, rx=90)       # olhal da cinta
    rubber = item.part(craft.Finish(bevel=0.0012 if bevel_segments > 2 else 0.0, bevel_segments=bevel_segments,
                                    smooth_angle=70))
    rubber.soft_box(0, -BODY_RADIUS - 0.0008, 0.1160, 0.0150, 0.0100, 0.0230, "rubber", radius=0.0045,
                    edge=0.0025, corner_points=5 if bevel_segments > 2 else 3, smooth=True)
    rubber.soft_box(0, -BODY_RADIUS - 0.0024, 0.1200, 0.0110, 0.0040, 0.0150, "rubber", radius=0.0030,
                    edge=0.0016, corner_points=5 if bevel_segments > 2 else 3, smooth=True)
    if split:                                    # a boca aberta do cano: luva escura por dentro e o contato de latão
        sleeve = item.part(SMOOTH_ONLY)
        sleeve.lathe([(BODY_RADIUS, CAP_END), (0.0176, CAP_END + 0.0006), (0.0176, 0.046)], 0, 0, 0.0, "black",
                     seg=seg, smooth=True, cap_bottom=False, cap_top=False)
        sleeve.cylinder(0, 0, 0.0455, 0.0150, 0.0010, "brass", seg=16, smooth=True)


def _build_cap(item, seg=36):
    """A tampa da cauda: calota com borda, como a primeira parte do perfil do corpo."""
    cap = item.part(SMOOTH_ONLY)
    cut = next(i for i, (_r, z) in enumerate(_BODY_PROFILE) if z >= CAP_END - 1e-9)
    cap.lathe(_BODY_PROFILE[:cut + 1], 0, 0, 0.0, "flash_aluminum", seg=seg, smooth=True, cap_top=False)
    cap.lathe([(0.0160, CAP_END), (0.0150, CAP_END - 0.0010), (0.0, CAP_END - 0.0010)], 0, 0, 0.0, "black", seg=seg,
              smooth=True, cap_bottom=False, cap_top=False)


def flashlight_shape(item):
    _build_body(item)


def build_item_mesh():
    """Lanterna deitada no criado-mudo: eixo ao longo de Y, botão para cima, apoiada na cabeça e na cauda."""
    item = Assembly(C.N_ITEM + C.ITEM_FLASHLIGHT)
    lean = math.degrees(math.asin((HEAD_RADIUS - 0.0194) / HEAD_END))
    with item.at(0.0, -HEAD_END / 2, HEAD_RADIUS, rx=lean):
        with item.at(rx=-90):
            flashlight_shape(item)
    return item


def build_viewmodel_mesh():
    """O cano na mão: origem no punho, lente para -Z local e botão para +Y. Sem mão: ela é do corpo."""
    item = Assembly(C.OBJ_VIEW_FLASH)
    with item.at(rx=180):
        with item.at(0.0, 0.0, -GRIP_CENTER):
            _build_body(item, seg=VIEWMODEL_SEG, split=True, eyelet=False, bevel_segments=2)
    return item


def build_cap_mesh():
    """A tampa da cauda no referencial do viewmodel, com a origem na dobradiça (lado direito da boca do cano)."""
    item = Assembly(C.OBJ_VIEW_FLASH + "_Cap")
    with item.at(-BODY_RADIUS, 0.0, -(GRIP_CENTER - CAP_END)):
        with item.at(rx=180):
            with item.at(0.0, 0.0, -GRIP_CENTER):
                _build_cap(item, seg=VIEWMODEL_SEG)
    return item


def make_viewmodel(ctx):
    """`ViewModel_Flashlight` e a tampa, ocultos na cena; o engine pendura o conjunto na câmera. Os outros itens
    que as mãos seguram (chaveiro, mapa, pilha, folha) nascem junto, em `handheld_set`."""
    from . import handheld_set
    builder = build_viewmodel_mesh()
    obj = bpy.data.objects.new(C.OBJ_VIEW_FLASH, builder.to_mesh(C.OBJ_VIEW_FLASH))
    obj.hide_viewport = True
    obj.hide_render = True
    obj["sa_barrel_axis"] = "-Z"
    ctx.link(obj, C.COL_PLAYER)
    cap = bpy.data.objects.new(C.OBJ_VIEW_FLASH + "_Cap", build_cap_mesh().to_mesh(C.OBJ_VIEW_FLASH + "_Cap"))
    cap.parent = obj
    cap.location = (BODY_RADIUS, 0.0, GRIP_CENTER - CAP_END)
    cap.hide_viewport = cap.hide_render = True
    ctx.link(cap, C.COL_PLAYER)
    handheld_set.make_handhelds(ctx)
    return obj
