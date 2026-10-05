"""Folha de papel na mão: uma folha de 1 x 1 m que o engine escala para a proporção de cada anotação.

O material de cima é trocado em tempo de execução pelo da anotação que está sendo lida (`Handhelds.set_paper`);
o verso é o papel liso. A altura de ondas e cantos é absoluta (a escala não mexe em Z), então a folha continua
fina e levemente arqueada seja qual for o tamanho.

Referencial do modelo: origem no meio da borda de baixo (onde a mão a segura), a folha sobe por +Y, face para +Z.
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
                curl_corners=((1, 1),), seed=41, bend_x=0.0040, offset=(0.0, 0.5, 0.0))
    return item.to_mesh(OBJECT_NAME)


def add_droop_key(obj):
    """Chave de forma `Droop`: a folha se curva como uma viga em balanço presa pela borda de baixo. O valor é a flecha da
    ponta em metros (o modelo tem 1 m de altura e a escala do engine não mexe em Z, então o deslocamento em Z já é absoluto):
    cada vértice sobe y^2 por metro de valor. Negativo curva para o outro lado."""
    obj.shape_key_add(name="Basis", from_mix=False)
    key = obj.shape_key_add(name="Droop", from_mix=False)
    key.slider_min, key.slider_max = -1.0, 1.0
    for vertex, data in zip(obj.data.vertices, key.data):
        data.co = (vertex.co.x, vertex.co.y, vertex.co.z + vertex.co.y ** 2)


def make(ctx):
    obj = bpy.data.objects.new(OBJECT_NAME, build_mesh())
    add_droop_key(obj)
    obj.hide_viewport = obj.hide_render = True
    ctx.link(obj, C.COL_PLAYER)
    return obj
