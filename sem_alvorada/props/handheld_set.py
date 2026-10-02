"""Os objetos que as mãos seguram, criados na etapa props, ocultos até o jogo usá-los.

`flashlight.make_viewmodel` chama `make_handhelds`. Orçamento: o conjunto todo (com a lanterna e a tampa)
fica abaixo de 6 mil triângulos (`tests/test_hands_models.py`). Idempotente: apaga o que uma execução anterior
criou antes de criar de novo.
"""
import bpy

from . import handheld_battery, handheld_key, handheld_map, handheld_paper

OBJECT_NAMES = (handheld_key.OBJECT_NAME, *handheld_map.NAMES, handheld_battery.OBJECT_NAME,
                handheld_paper.OBJECT_NAME)


def make_handhelds(ctx):
    for name in OBJECT_NAMES:
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
    objects = [handheld_key.make(ctx), *handheld_map.make(ctx), handheld_battery.make(ctx), handheld_paper.make(ctx)]
    ctx.log(f"itens na mão criados: {', '.join(obj.name for obj in objects)}")
    return objects
