"""Pilha D na mão: uma célula só do par de mesa, do tamanho de uma D de verdade.

Referencial do modelo: origem no centro da pilha, eixo ao longo de Z (polo positivo para +Z).
"""
import bpy

from .. import conventions as C
from .item_models import SMOOTH_ONLY, Assembly, _cell

OBJECT_NAME = "ViewModel_Battery"
RADIUS = 0.0170
LENGTH = 0.0610
SEGMENTS = 20


def build_mesh():
    item = Assembly(OBJECT_NAME)
    part = item.part(SMOOTH_ONLY)
    with part.at(0.0, 0.0, -LENGTH / 2):
        _cell(part, RADIUS, LENGTH, seg=SEGMENTS)
    return item.to_mesh(OBJECT_NAME)


def make(ctx):
    obj = bpy.data.objects.new(OBJECT_NAME, build_mesh())
    obj.hide_viewport = obj.hide_render = True
    ctx.link(obj, C.COL_PLAYER)
    return obj
