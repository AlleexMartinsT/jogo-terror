"""O Alto: humanoide de 2,65 m, errado de propósito (contrato 4 e 5.3).

    entity.build(ctx)              constrói Entity, Entity_Rig, Entity_Body, Entity_Eyes, Entity_EyeLight
    entity.rig.EntityRig(scene)    controle em tempo de execução (sem UI)
"""
from .assemble import create_entity


def build(ctx):
    create_entity(ctx)


def __getattr__(name):
    # importa a rig só quando alguém pede, para `entity.build` não depender da animação
    if name in ("rig", "EntityRig"):
        from . import rig
        return rig if name == "rig" else rig.EntityRig
    raise AttributeError(name)
