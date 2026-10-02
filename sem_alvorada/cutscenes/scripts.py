"""Roteiro das cinco cutscenes de SEM ALVORADA: o registro e o plano de batidas.

Cada cena mora no seu módulo (`scene_*.py`, só dados: planos, câmeras, legendas, ações); a geometria e os atalhos
comuns ficam em `staging.py`. Auditoria da versão anterior e o que mudou:

    cena           antes                                        agora
    intro          6 planos A -> B, quarto parado, fade          1 plano contínuo (os olhos): pálpebras, foco que firma,
                                                                 rádio e mostrador 6:12, senta, pés no chão, janela, dá a
                                                                 volta na cama e entrega o jogador sem salto
    blackout       fade, teletransporte, entidade parada         queda de luz em cascata, lâmpada que estoura, lanterna
                                                                 tremendo, o Alto dá uma passada lenta, cérebro acorda dali
    garage_unlock  planos fixos em posições inventadas           1 plano na vista do jogador: mão com a chave na tranca, porta
                                                                 que abre com a curva do jogo, estrondo, poeira do forro
    death          4 planos, 4,7 s, lente trava                  1 plano de 3,5 s: bote, golpe, queda ao chão, corte seco
    ending         carro deslizando como uma caixa               ignição, painel, motor, coelhinho, portão, saída na rampa
                                                                 com suspensão e rodas, o Alto no feixe, 6:12 e o cartão

Tempos dentro de um plano são relativos ao começo dele; em `Cutscene.cues/tracks`, absolutos.
"""
from . import scene_blackout, scene_death, scene_ending, scene_garage, scene_intro
from .staging import (BED_LAMP, CAR_CABIN, CLOCK_GLOW, CLOCK_NAMES, CORRIDOR_RIM, DAWN_LIGHT, DRIVEWAY_LIGHT,  # noqa: F401
                      END_CLOCK, EYE, GAMEPLAY_FOV, ROAD_FACING, ROAD_LIGHT, add, ahead, anchor, door_handle, say,
                      sun_direction, toward_sun, window_center, window_vantage, yaw_of)
from .scene_blackout import blackout_vantage  # noqa: F401

BUILDERS = {
    "intro": scene_intro.build,
    "blackout": scene_blackout.build,
    "garage_unlock": scene_garage.build,
    "death": scene_death.build,
    "ending": scene_ending.build,
}

# nomes que ferramentas e testes antigos usavam
build_intro, build_blackout, build_garage_unlock = scene_intro.build, scene_blackout.build, scene_garage.build
build_death, build_ending = scene_death.build, scene_ending.build

NAMES = tuple(BUILDERS)
_built = {}


def get(name):
    """Devolve a cutscene `name` (montada uma vez só)."""
    if name not in BUILDERS:
        raise KeyError(f"cutscene desconhecida: {name!r}; use uma de {NAMES}")
    if name not in _built:
        _built[name] = BUILDERS[name]()
    return _built[name]
