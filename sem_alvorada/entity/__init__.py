"""O Alto: humanoide de 2,65 m, errado de propósito (contrato 4 e 5.3).

    entity.build(ctx)              constrói Entity, Entity_Rig, Entity_Body, Entity_Eyes, Entity_EyeLight
    entity.rig.EntityRig(scene)    controle em tempo de execução (sem UI): animação, olhar, olhos, pose de morte

Arquivos: `skeleton` (ossos, cinemática, IK), `motion` (animações procedurais), `model` (malha),
`textures`/`materials` (pele, tecido, olhos), `assemble` (monta a hierarquia), `sheet` (ferramenta de
desenvolvimento para renderizar folhas de contato).
"""
from .assemble import create_entity
from .rig import EntityRig


def build(ctx):
    create_entity(ctx)


__all__ = ["build", "EntityRig"]
