"""Folha de papel na mão: uma folha de 1 x 1 m que o engine escala para a proporção de cada anotação.

O material de cima é trocado em tempo de execução pelo da anotação que está sendo lida (`Handhelds.set_paper`);
o verso é o papel liso. A altura de ondas e cantos é absoluta (a escala não mexe em Z), então a folha continua
fina e levemente arqueada seja qual for o tamanho.

Referencial do modelo: origem no centro da folha, face para +Z.
"""
import bpy

from .. import conventions as C
from . import paper
from .item_models import PAPER, Assembly

OBJECT_NAME = "ViewModel_Paper"


def build_mesh():
    item = Assembly(OBJECT_NAME)
    sheet = item.part(PAPER)
    paper.sheet(sheet, 1.0, 1.0, "note_letter", "paper_back", thickness=0.0005, nu=6, nv=8, wave=0.0030, curl=0.0060,
                curl_corners=((1, 1),), seed=41, bend_x=0.0040)
    return item.to_mesh(OBJECT_NAME)


def make(ctx):
    obj = bpy.data.objects.new(OBJECT_NAME, build_mesh())
    obj.hide_viewport = obj.hide_render = True
    ctx.link(obj, C.COL_PLAYER)
    return obj
