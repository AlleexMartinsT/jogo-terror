"""Pilha D na mão: uma célula só do par de mesa, do tamanho de uma D de verdade.

Referencial do modelo: origem no centro da pilha, deitada com o eixo ao longo de X (polo positivo para +X), como
repousa na palma da mão esquerda.
"""
import math

import bpy
from mathutils import Matrix

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
    mesh = item.to_mesh(OBJECT_NAME)
    mesh.transform(Matrix.Rotation(math.pi / 2, 4, "Y"))         # o eixo da pilha (Z) passa para X
    mesh.update()
    return mesh


def make(ctx):
    obj = bpy.data.objects.new(OBJECT_NAME, build_mesh())
    obj.hide_viewport = obj.hide_render = True
    ctx.link(obj, C.COL_PLAYER)
    return obj
