# Métricas medidas nos clipes reais de referência (CMU)

Medido com `tools/movimento_ref/metricas.py` (MEDIDO, não estimado). Passadas = passadas completas observadas (pés esquerdo e direito somados); com menos de 3 trate como indicativo. Velocidade é a do quadril.

## Marcha

| clipe | gesto | método | passadas | v (m/s) | cad. (passos/min) | passada (m) | passo (m) | apoio (%) | 2x apoio (%) | voo (%) | quadril (m) | cabeça vert. (cm) | cabeça lat. (cm) | joelho apoio (°) | joelho balanço (°) | tronco (°) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 07_01 | andar | zeni | 2 | 1.38 | 107 | 1.50 | 0.75 | 64 | 15 | 0 | 0.98 | 4.0 | 6.1 | 34 | 67 | -9 |
| 08_01 | andar_2 | zeni | 1 | 1.60 | 113 | -- | 0.86 | 65 | 13 | 0 | 0.95 | 3.0 | 5.4 | 41 | 72 | -3 |
| 07_04 | andar_devagar | zeni | 3 | 0.95 | 81 | 1.39 | 0.67 | 65 | 17 | 0 | 0.98 | 3.1 | 8.9 | 32 | 64 | -9 |
| 16_33 | andar_parar | zeni | 0 | -- | -- | -- | -- | -- | -- | -- | 0.99 | 2.4 | -- | -- | -- | -- |
| 09_01 | correr | altura | 1 | 3.59 | 164 | -- | 1.35 | 32 | 0 | 36 | 1.03 | 8.0 | 3.9 | 42 | 105 | 13 |
| 16_17 | curva | zeni | 5 | 0.86 | 105 | 0.87 | 0.46 | 72 | 23 | 0 | 0.99 | 2.0 | 9.1 | 25 | 63 | -1 |
| 17_03 | furtivo | zeni | 32 | 0.44 | 42 | 1.10 | -0.26 | 41 | 6 | 42 | 0.88 | 10.7 | 44.8 | 80 | 73 | 38 |
| 77_14 | rastejar | zeni | 14 | 1.11 | 147 | 0.77 | 0.16 | 68 | 17 | 4 | 0.85 | 2.1 | 30.6 | 61 | 60 | 40 |
| 136_09 | agachado | zeni | 9 | 0.85 | 94 | 1.05 | 0.53 | 73 | 22 | 0 | 0.87 | 1.5 | 6.5 | 79 | 104 | 45 |
| 83_27 | escada | zeni | 5 | 0.52 | 86 | 0.73 | 0.37 | 71 | 23 | 0 | 1.04 | 3.1 | 7.5 | 31 | 81 | 5 |
| 13_35 | degraus | zeni | 6 | 0.27 | 50 | 0.45 | 0.28 | 68 | 12 | 6 | 1.35 | 6.6 | 20.3 | 58 | 80 | 7 |
| 91_18 | cuidado | zeni | 17 | 0.38 | 54 | 1.03 | 0.50 | 60 | 8 | 21 | 0.90 | 1.8 | 18.6 | 25 | 52 | -7 |

## Gestos da mão (perfil de velocidade do melhor alcance)

| clipe | gesto | mão | início (s) | duração (s) | distância (m) | pico (m/s) | pico em % da duração | pico/média | R² jerk mínimo |
|---|---|---|---|---|---|---|---|---|---|
| 26_09 | pegar_chao | dir. | 0.22 | 3.41 | 1.75 | 1.15 | 70 | 2.24 | -0.55 |
| 15_06 | alcancar | dir. | 27.57 | 2.01 | 1.59 | 1.76 | 67 | 2.23 | -1.52 |
| 81_05 | empurrar | esq. | 0.57 | 1.12 | 0.71 | 1.23 | 46 | 1.95 | 0.92 |
| 77_05 | lanterna | dir. | 0.81 | 1.29 | 1.48 | 2.04 | 55 | 1.77 | -0.37 |
| 22_22 | pegar_chaves | dir. | 0.01 | 1.42 | 1.13 | 1.75 | 49 | 2.21 | 0.74 |
| 111_09 | levantar | esq. | 1.43 | 1.95 | 1.02 | 1.46 | 39 | 2.80 | 0.19 |
| 13_01 | sentar_levantar | esq. | 10.44 | 1.59 | 1.12 | 1.11 | 47 | 1.56 | -1.36 |

Jerk mínimo teórico: pico em 50% da duração, pico/média = 1,875, R² = 1.
