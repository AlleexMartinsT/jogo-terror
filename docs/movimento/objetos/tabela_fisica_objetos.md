# Objetos e física: valor físico contra o jogo, antes e depois

ESTIMADO = engenharia lembrada de memória (faixa na nota); DERIVADO = lei física sobre medidas do modelo 3D; MEDIDO = mocap da CMU. Não existe vídeo real de portas, carros ou relógios neste ambiente.

| Grupo | Métrica | Unid. | Física | Jogo antes | Jogo depois | Tolerância | Origem | OK |
|---|---|---|---|---|---|---|---|---|
| porta | abrir: desvio da trajetória de mínima variação de torque | fração do curso | 0 | 2.54e-05 | 2.54e-05 | [-5.00e-03, 5.00e-03] | DERIVADO | sim |
| porta | abrir: velocidade angular de pico | rad/s | 2.68 | 2.68 | 2.68 | +-3% | DERIVADO | sim |
| porta | abrir: aceleração angular de pico | rad/s2 | 7.5 | 7.49 | 7.49 | +-5% | DERIVADO | sim |
| porta | abrir: instante do pico (fração da duração) | - | 0.5 | 0.477 | 0.477 | +-10% | DERIVADO | sim |
| porta | abrir: força na maçaneta, normal (pior das 13 portas) | N | 100 | 79.2 | 79.2 | <= 100 | ESTIMADO | sim |
| porta | abrir: força na maçaneta, apressado (pior das 13 portas) | N | 100 | 112 | 99.5 | <= 100 | ESTIMADO | sim |
| porta | abrir: duração / menor duração que a mão aguenta (pior ritmo) | - | 1 | 1.08 | 1.08 | >= 1 | DERIVADO | sim |
| porta | abrir: menor duração de uma abertura, 13 portas e 2 ritmos | s | 0.8 | 0.924 | 0.924 | >= 0.8 | ESTIMADO | sim |
| mão real | abrir: duração do gesto | s | 1.27 | 0.963 | 0.963 | +-29% | MEDIDO | sim |
| mão real | abrir: instante do pico (fração) | - | 0.463 | 0.5 | 0.5 | +-35.3% | MEDIDO | sim |
| mão real | abrir: razão pico/média da velocidade | - | 1.97 | 1.65 | 1.65 | +-23.6% | MEDIDO | sim |
| porta | abrir: lingueta recolhida quando a folha anda 1,5 mm | 0..1 | 0.8 | 0.959 | 0.959 | >= 0.8 | ESTIMADO | sim |
| porta | fechar: velocidade da ponta ao chegar ao batente | m/s | 0.12 | 5.37e-04 | 0.3 | >= 0.12 | ESTIMADO | sim |
| porta | fechar: lingueta recolhida quando a folha encosta | 0..1 | 0.8 | 0 | 1 | >= 0.8 | DERIVADO | sim |
| porta | fechar: recuo do trinco na maçaneta | mm | 1.48 | 10.4 | 1.47 | [0.3, 4] | ESTIMADO | sim |
| porta | fechar: som do trinco menos o instante da chegada | s | 0 | 4.17e-03 | 4.17e-03 | [-0.03, 0.03] | DERIVADO | sim |
| porta | batida: tempo da folha do aberto ao batente | s | 0.416 | 0.192 | 0.404 | +-15% | ESTIMADO | sim |
| porta | batida: velocidade angular no impacto | rad/s | 4.44 | 9.45 | 4.45 | +-15% | ESTIMADO | sim |
| porta | batida: velocidade da ponta no impacto | m/s | 3.91 | 8.32 | 3.91 | +-15% | ESTIMADO | sim |
| porta | batida: rebote máximo na maçaneta | mm | 3 | 26.1 | 5 | [3, 8] | ESTIMADO | sim |
| porta | batida: estrondo menos o instante do impacto | s | 0 | -5.83e-03 | 2.50e-03 | [-0.03, 0.03] | DERIVADO | sim |
| porta | batida: tempo até a folha assentar depois do impacto | s | 0.6 | 0.137 | 0.196 | <= 0.6 | ESTIMADO | sim |
| porta | inverter aos 35% da abertura: quanto a folha ainda avança | rad | 0.106 | 0.153 | 0.232 | [0.0641, 0.36] | DERIVADO | sim |
| porta | inverter aos 60% da abertura: quanto a folha ainda avança | rad | 0.18 | 0.193 | 0.307 | [0.109, 0.53] | DERIVADO | sim |
| porta | inverter aos 90% da abertura: quanto a folha ainda avança | rad | 0.0237 | 0.0418 | 0.0398 | [0.0143, 0.13] | DERIVADO | sim |
| carro | rodas: deslizamento do ponto de contato / velocidade do centro | - | 0.05 | 1.95 | 1.96e-03 | <= 0.05 | DERIVADO | sim |
| carro | rodas: w R / v (sentido de rolar para a frente) | - | 1 | 1 | 1 | +-3% | DERIVADO | sim |
| carro | rodas: afastamento do fundo do pneu ao terreno | mm | 10 | 36.9 | 2.38 | <= 10 | DERIVADO | sim |
| carro | suspensão: frequência de passeio (vertical) | Hz | 1.19 | 2.6 | 1.19 | [1, 1.5] | ESTIMADO | sim |
| carro | suspensão: frequência de arfagem | Hz | 1.51 | 1.9 | 1.51 | [1, 1.55] | ESTIMADO | sim |
| carro | suspensão: razão de amortecimento | - | 0.3 | 0.3 | 0.3 | +-33.3% | ESTIMADO | sim |
| carro | rolagem: frequência | Hz | 1.3 | 2.3 | 1.3 | +-23.1% | ESTIMADO | sim |
| carro | arfagem: maior diferença contra o meio carro / amplitude total | - | 0 | 1.07 | 0.0103 | [-0.15, 0.15] | DERIVADO | sim |
| carro | arfagem: gradiente na aceleração (nariz para cima = positivo) | rad por m/s2 | 4.48e-03 | -0.0126 | 4.49e-03 | +-20% | DERIVADO | sim |
| carro | arfagem: gradiente na frenagem (nariz para baixo ao frear) | rad por m/s2 | 4.43e-03 | -0.0137 | 4.37e-03 | +-20% | DERIVADO | sim |
| carro | rolagem: gradiente (teto para fora da curva) | rad por m/s2 | 0.0107 | 2.03e-04 | 0.0112 | +-33.3% | ESTIMADO | sim |
| carro | direção: esterçamento que o caminho exige (pico) | graus | 10 | 31.4 | 4.97 | <= 10 | ESTIMADO | sim |
| carro | direção: diferença entre o esterçamento do jogo e o de Ackermann (pior caso) | graus | 0.5 | 35.9 | 0.0211 | <= 0.5 | DERIVADO | sim |
| carro | direção: ângulo entre a frente do carro e a velocidade | graus | 1 | 21 | 0.0355 | <= 1 | DERIVADO | sim |
| carro | direção: volante / roda (sinal e relação) | - | 15 | -9 | 15 | [14, 18] | ESTIMADO | sim |
| carro | motor: frequência dominante do tremor em marcha lenta | Hz | 11.7 | 11.1 | 11.6 | +-12.9% | DERIVADO | sim |
| carro | motor: aceleração vertical RMS em marcha lenta | m/s2 | 0.2 | 2.29 | 0.242 | [0.05, 0.46] | ESTIMADO | sim |
| carro | cena: aceleração máxima pedida ao carro | m/s2 | 3.88 | 0.891 | 0.891 | <= 3.88 | ESTIMADO | sim |
| carro | coelhinho: correlação com o pêndulo composto forçado (sinal e forma) | - | 0.95 | -0.981 | 1 | >= 0.95 | DERIVADO | sim |
| carro | coelhinho: ângulo de pico | graus | 5.88 | 6.06 | 5.91 | +-15% | DERIVADO | sim |
| carro | coelhinho: período de oscilação | s | 0.829 | 0.897 | 0.83 | +-5% | DERIVADO | sim |
| carro | chaveiro: período de oscilação | s | 0.631 | 0.531 | 0.631 | +-5% | DERIVADO | sim |
| portão | velocidade de cruzeiro | m/s | 0.175 | 1.3 | 0.19 | +-14.3% | ESTIMADO | sim |
| portão | velocidade máxima | m/s | 0.22 | 1.41 | 0.19 | <= 0.22 | ESTIMADO | sim |
| portão | aceleração máxima (partida e parada suaves) | m/s2 | 0.35 | 1.44 | 0.324 | <= 0.35 | ESTIMADO | sim |
| portão | duração da subida de 2,3 m | s | 13.1 | 2.58 | 12.2 | [11.5, 16.8] | ESTIMADO | sim |
| portão | folga entre o teto do carro e a folha enquanto o carro passa | m | 0.1 | 0.903 | 0.289 | >= 0.1 | DERIVADO | sim |
| cortina | frequência dominante da bainha | Hz | 0.399 | 0.25 | 0.375 | +-25% | DERIVADO | sim |
| cortina | energia entre 0,3 e 1 Hz (acima de 0,1 Hz) | fração | 0.582 | 0.275 | 0.607 | [0.291, 0.757] | ESTIMADO | sim |
| cortina | perfil de amplitude cima-baixo (maior diferença) | fração da bainha | 0 | 0.0944 | 0.0223 | [-0.15, 0.15] | DERIVADO | sim |
| cortina | fator de crista do deslocamento (rajadas) | - | 4.06 | 2.64 | 3.37 | [2.85, 5.69] | ESTIMADO | sim |
| poeira | velocidade terminal da poeira fina (mediana) | m/s | 0.0575 | 0.45 | 0.0442 | [0.02, 0.1] | DERIVADO | sim |
| poeira | fração de partículas de poeira fina (< 15 cm/s) | fração | 0.605 | 0 | 0.643 | [0.5, 0.8] | ESTIMADO | sim |
| poeira | distância KS da distribuição de log v contra a física | - | 0.2 | 0.653 | 0.174 | <= 0.2 | DERIVADO | sim |
| poeira | tempo de relaxação medido / (v_t / g) nas partículas rápidas | - | 1 | 5.37 | 0.97 | +-40% | DERIVADO | sim |
| luz | incandescente: tempo para cair a 10% ao desligar | s | 0.05 | 1.00e-04 | 0.0458 | +-40% | DERIVADO | sim |
| luz | incandescente: tempo para subir a 90% ao ligar | s | 0.12 | 1.00e-04 | 0.108 | +-40% | DERIVADO | sim |
| luz | fluorescente: tempo para cair a 10% ao desligar | s | 0.02 | 0 | 0 | <= 0.02 | ESTIMADO | sim |
| luz | fluorescente (garagem): frequência das piscadas dentro de uma rajada | Hz | 6 | 0 | 6.58 | [3, 10] | ESTIMADO | sim |
| luz | fluorescente (garagem): profundidade da piscada | 0..1 | 0.8 | 0.25 | 0.93 | >= 0.8 | ESTIMADO | sim |
| luz | fluorescente (garagem): fração do tempo em rajada | fração | 0.45 | 0 | 0.138 | <= 0.45 | ESTIMADO | sim |
| luz | fluorescente (cozinha): frequência das piscadas dentro de uma rajada | Hz | 6 | 0 | 5.7 | [3, 10] | ESTIMADO | sim |
| luz | fluorescente (cozinha): profundidade da piscada | 0..1 | 0.8 | 0.1 | 0.91 | >= 0.8 | ESTIMADO | sim |
| luz | fluorescente (cozinha): fração do tempo em rajada | fração | 0.45 | 0 | 0.0928 | <= 0.45 | ESTIMADO | sim |
| luz | TV de chuvisco: variação RMS da luz da sala | fração | 0.04 | 0.239 | 8.94e-03 | <= 0.04 | ESTIMADO | sim |
| relógio | pêndulo: período medido | s | 2 | nan | 2 | +-1% | DERIVADO | sim |
| relógio | modelo 3D: período do pêndulo que a geometria da haste e da lentilha dá | s | 2 | 1.47 | 2 | +-1% | DERIVADO | sim |
| relógio | pêndulo: amplitude (cada lado) | graus | 2.5 | 0 | 2.47 | [2, 4] | ESTIMADO | sim |
| relógio | tique depois do centro do arco | s | 0.025 | - | 0.0258 | +-60% | ESTIMADO | sim |
| relógio | tique contra o tique do laço de áudio amb_clock_tick (pior) | s | 0.03 | - | 1.30e-11 | <= 0.03 | DERIVADO | sim |
| relógio | ponteiro dos segundos: tiques em 60 s | - | 60 | 0 | 60 | +-2% | DERIVADO | sim |
| relógio | ponteiro dos segundos: avanço por tique | graus | 6 | 0 | 6 | +-2% | DERIVADO | sim |
| relógio | ponteiro dos segundos: ultrapassagem depois do salto | graus | 1.5 | - | 1.41 | <= 1.5 | ESTIMADO | sim |
