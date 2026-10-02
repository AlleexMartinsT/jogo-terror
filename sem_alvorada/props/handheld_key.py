"""Chaveiro na mão: o mesmo modelo de mesa (`item_models.build_key`) com menos segmentos e virado para pender.

Referencial do modelo: origem no centro da cabeça de borracha (onde o polegar e o indicador pinçam), o chaveiro
pendurado para -Y (lâmina para cima, argolas e coelhinho para baixo), a face de cima da chave para +Z (a câmera).
A escala já vem embutida: o da mesa é 1,3x o real para ser mirado; na mão fica 0,75 dele.
"""
import math

import bpy
from mathutils import Matrix, Vector

from .. import conventions as C
from .item_models import build_key

OBJECT_NAME = "ViewModel_Key"
PIVOT = (0.0, 0.0345 * 1.3, 0.0105 * 1.3 / 2)      # centro da cabeça no referencial do Item_KEY
HAND_SCALE = 0.75


def build_mesh():
    mesh = build_key(detail=0.5).to_mesh(OBJECT_NAME)
    mesh.transform(Matrix.Scale(HAND_SCALE, 4) @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Translation(-Vector(PIVOT)))
    mesh.update()
    return mesh


def make(ctx):
    obj = bpy.data.objects.new(OBJECT_NAME, build_mesh())
    obj.hide_viewport = obj.hide_render = True
    ctx.link(obj, C.COL_PLAYER)
    return obj
