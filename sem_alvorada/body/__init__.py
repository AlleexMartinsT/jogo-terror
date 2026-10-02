"""Corpo do jogador em primeira pessoa (Daniel Harper, 1,80 m): armadura, malha e controle em tempo de execução.

ESTADO: MARCO 1 PRONTO (e marcos 2 e 3 entregues). A rig funciona de ponta a ponta: armadura de 54 ossos,
`BodyRig(scene)` com a mesma superfície pública de `NullBody`, IK de dois ossos nos braços (com giro do cotovelo
para a mão alcançar a orientação pedida), dedos com presets, locomoção (passos na fase de `player.stride_phase`,
degraus da escada, agachar, correr, respirar, tronco que acompanha o olhar), poses de cutscene e a etapa "body"
do build (antes de "engine"). O modelo tem camisa de flanela xadrez com carcela, bolsos, botões, gola e punhos
dobrados, jeans com cós, passantes e cinto de couro com fivela, botas com cadarço, mãos com falanges, unhas,
tendões, veias e aliança na esquerda; texturas procedurais de 512x512 com relevo.

Como usar (mãos, agente 3):
    arm = game.body.arm("R")                                  # "L" ou "R"
    arm.set_target((0.20, -0.12, -0.42), (0, 0, 0), weight)   # centro da palma no espaço da câmera (X direita,
                                                              # Y cima, -Z frente, m); alcance ~0,5 m à frente
    arm.set_fingers(*body.fingers.preset("grip_cylinder"))    # ou curls=(polegar..mindinho, 0..1), spread
    arm.hold(obj, (0, 0, -0.03)); arm.drop(obj)               # offset no referencial da mão (ver handframe.py)
    arm.release(blend)                                        # volta à pose solta; blend = fração do caminho por chamada
    body.hand_rotation(fingers=(0, 0, -1), palm=(-1, 0, 0))   # Euler (graus) a partir de para onde a mão aponta
    # lanterna: set_fingers(*fingers.preset("grip_cylinder")); set_target(pos, body.grip_rotation("R", barrel=(0, .05, -1)), 1)
    #           hold(obj, body.grip_offset("R"))   # obj com o cano ao longo de -Z e a origem no meio da pegada
`weight` e `blend` agem por chamada: chame todo quadro com o valor que sua animação pede.

Como usar (cutscenes, agente 4): `host.show_body(True)`; `body.place(x, y, z, yaw)` assume o corpo (fica assim até
`body.reset()`); `body.pose("lying_bed" | "sit_bed" | "driving" | "stand", seconds)` e `body.update(dt, None)` por
quadro para animar a transição e a respiração; `body.attach_view(camera_obj)` define a câmera dos alvos dos braços.
Em "stand" o `z` de `place` é o chão; nas outras poses é o plano onde o quadril apoia (colchão, assento).
Ao terminar a cena chame `body.reset()` (o `Game` já o chama em novo jogo e checkpoint).

    body.build(ctx)                  etapa "body" do build: cria PlayerBody_Rig e PlayerBody na coleção do jogador
    body.BodyRig(scene)              controle (contrato em docs/FASE3.md, seção "Corpo"); mesma superfície de NullBody
    body.fingers.PRESETS             presets: relaxed, open, flat, grip_cylinder, pinch, point, hold_card, cradle, hook, fist

Arquivos: `skeleton` (ossos e medidas), `solver` (FK e IK de dois ossos com dobradiça comum), `locomotion`
(pernas, tronco, respiração), `fingers`, `handframe`, `poses`, `rig` (BodyRig e ArmControl), `meshkit` e `shape_*`
(modelagem), `materials`, `assemble` (monta na cena).
"""
from . import fingers
from .handframe import grip_offset, grip_rotation, hand_rotation
from .rig import BodyRig


def build(ctx):
    from . import assemble, meshkit
    from . import skeleton as S
    meshkit.set_quality(ctx.quality)
    rig, body, data = assemble.create_body(ctx)
    ctx.log(f"corpo: {assemble.triangle_count(body)} triângulos, {len(S.BONES)} ossos")


__all__ = ["BodyRig", "build", "fingers", "grip_offset", "grip_rotation", "hand_rotation"]
