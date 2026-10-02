"""Os objetos que as mãos seguram, criados na etapa props, ocultos até o jogo usá-los.

`flashlight.make_viewmodel` chama `make_handhelds`. Orçamento: o conjunto todo (com a lanterna e a tampa)
fica abaixo de 6 mil triângulos (`tests/test_hands_models.py`). Idempotente: apaga o que uma execução anterior
criou antes de criar de novo.
"""
import bpy

from .. import conventions as C
from . import handheld_battery, handheld_key, handheld_map, handheld_paper

FILL_NAME = "HandFill"
FILL_WATTS = 1.4
FILL_REACH = 0.85            # m: só alcança as mãos e o que elas seguram
OBJECT_NAMES = (handheld_key.OBJECT_NAME, *handheld_map.NAMES, handheld_battery.OBJECT_NAME,
                handheld_paper.OBJECT_NAME, FILL_NAME)


def make_fill(ctx):
    """Luz mínima junto às mãos: no escuro total a lanterna ilumina a frente, nunca a própria mão, e sem isto o
    jogador não veria a silhueta do que segura. Sem sombra e de alcance curto, não acende o cômodo."""
    data = bpy.data.lights.get(FILL_NAME) or bpy.data.lights.new(FILL_NAME, "POINT")
    data.energy = FILL_WATTS
    data.color = (1.0, 0.92, 0.80)
    data.use_shadow = False
    data.shadow_soft_size = 0.15
    if hasattr(data, "use_custom_distance"):
        data.use_custom_distance = True
        data.cutoff_distance = FILL_REACH
    obj = bpy.data.objects.new(FILL_NAME, data)
    obj.location = (0.0, -0.06, -0.10)
    obj.hide_viewport = obj.hide_render = True
    ctx.link(obj, C.COL_PLAYER)
    return obj


def make_handhelds(ctx):
    for name in OBJECT_NAMES:
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
    objects = [handheld_key.make(ctx), *handheld_map.make(ctx), handheld_battery.make(ctx), handheld_paper.make(ctx),
               make_fill(ctx)]
    ctx.log(f"itens na mão criados: {', '.join(obj.name for obj in objects)}")
    return objects
