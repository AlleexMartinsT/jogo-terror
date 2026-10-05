"""Cenários de exemplo, os modelos para os outros agentes.

    andar            marcha: o clipe 07_01 (caminhada normal da CMU) contra o jogo andando em linha reta
    alcance_exemplo  gesto da mão: um alcance de 15_06 contra a mão do jogo guiada pelo `por_quadro` do roteiro

Para um cenário novo, copie o mais parecido, troque o clipe, o trecho e o roteiro, e registre-o no seu módulo
(`locomocao.py`, `maos.py` ou `objetos.py`). Quando um desses módulos registrar um nome já usado aqui, o dele vale.
"""
import numpy as np

from . import registrar
from .base import Cenario, CenarioAlcance


@registrar
class Andar(Cenario):
    nome = "andar"
    titulo = "Andar normal (CMU 07_01) contra o jogo"
    resumo = "Caminhada em linha reta: mocap retargetado no Daniel à esquerda, o jogo à direita, alinhados pelo toque do calcanhar."
    clip = "07_01"
    grupo = "andar"               # 12 clipes de 7 pessoas: a faixa de +-1 desvio e o desvio entre pessoas da tabela
    roteiro = "andar 6"
    metodo = "zeni"


def _alcance_de_jerk_minimo(origem, destino, inicio=0.3, duracao=0.8):
    """`por_quadro` que leva o centro da palma direita de `origem` a `destino` (espaço da câmera, metros) em jerk mínimo."""
    origem, destino = np.array(origem, float), np.array(destino, float)

    def passo(jogo, t, _k):
        s = min(max((t - inicio) / duracao, 0.0), 1.0)
        f = 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5
        jogo.body.arm("R").set_target(tuple(origem + f * (destino - origem)), (0.0, 0.0, 0.0), 1.0)
    return passo


@registrar
class AlcanceExemplo(CenarioAlcance):
    nome = "alcance_exemplo"
    titulo = "Alcance da mão direita (CMU 15_06) contra a mão do jogo"
    resumo = "Exemplo de gesto: mostra como alinhar por início, pico de velocidade e chegada do alcance."
    clip = "15_06"
    trecho = (0.4, 1.7)
    lado_mao = "d"
    alcance_real = 0
    alcance_jogo = 0
    vel_minima = 0.3

    @property
    def roteiro(self):
        from .. import grava
        return [grava.Passo(1.6, por_quadro=_alcance_de_jerk_minimo((0.20, -0.40, -0.18), (0.16, -0.12, -0.55)), rotulo="alcance")]
