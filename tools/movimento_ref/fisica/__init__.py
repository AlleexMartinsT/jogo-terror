"""Física dos objetos do jogo (agente 4 da fase 4): modelos independentes e comparação com o movimento do jogo.

Cada módulo traz, para um objeto, três coisas:

    modelo   código físico escrito do zero (fórmula fechada ou integração numérica) que NÃO importa nada de
             `sem_alvorada`: é a referência. Cada constante diz a sua origem:
                 DERIVADO  sai de uma lei (Newton, pêndulo, Stefan-Boltzmann...) a partir de medidas do modelo 3D
                 ESTIMADO  valor de engenharia lembrado de memória, com a faixa; não foi medido aqui
                 MEDIDO    saiu de captura de movimento real (CMU, `tools.movimento_ref.cmu`)
    grava    roda o código do jogo (`engine/doors.py`, `cutscenes/anim.py`, ...) sem janela e devolve as séries
    medidas  a tabela métrica a métrica: valor físico, jogo antes, jogo depois, tolerância

Módulos: porta, mao_real, relogio, charm, portao, carro, cortina, luz. `relatorio` junta tudo em
out/f4_4/final/. As gravações "antes" (jogo sem as correções da fase 4) ficam em out/f4_4/antes/*.json.
"""
