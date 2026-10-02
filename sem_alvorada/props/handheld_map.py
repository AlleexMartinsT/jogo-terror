"""Mapa na mão: três painéis articulados, para o mapa desdobrar de verdade.

`ViewModel_Map` é o primeiro painel; o segundo e o terceiro são filhos em cadeia, cada um com a origem na
dobradiça (borda esquerda). O engine gira o segundo em torno de Y pelo primeiro ângulo e o terceiro pelo
segundo. Fechado é um Z de três folhas, aberto é uma tira plana. O mesmo tamanho do `item_models.build_map`.

Referencial do primeiro painel: origem no meio da borda esquerda, a folha corre para +X e +-Y, face para +Z.
"""
import bpy

from .. import conventions as C
from . import paper
from .item_models import PAPER, Assembly

PANEL_WIDTH, PANEL_LENGTH = 0.118, 0.172
NAMES = ("ViewModel_Map", "ViewModel_Map_P2", "ViewModel_Map_P3")
THIRDS = ((0.0, 0.0, 1 / 3, 1.0), (1 / 3, 0.0, 2 / 3, 1.0), (2 / 3, 0.0, 1.0, 1.0))


def build_panel(index):
    item = Assembly(NAMES[index])
    sheet = item.part(PAPER)
    paper.sheet(sheet, PANEL_WIDTH, PANEL_LENGTH, "city_map", "paper_back", thickness=0.0005, nu=6, nv=8,
                offset=(PANEL_WIDTH / 2, 0.0, 0.0), wave=0.0008, curl=0.004 if index == 2 else 0.0,
                curl_corners=((1, 1),), uv_rect=THIRDS[index], seed=index + 1, bend_x=0.0010)
    return item.to_mesh(NAMES[index])


def make(ctx):
    panels = []
    for index, name in enumerate(NAMES):
        obj = bpy.data.objects.new(name, build_panel(index))
        obj.hide_viewport = obj.hide_render = True
        if panels:
            obj.parent = panels[-1]
            obj.location = (PANEL_WIDTH, 0.0, 0.0)
        ctx.link(obj, C.COL_PLAYER)
        panels.append(obj)
    return panels
