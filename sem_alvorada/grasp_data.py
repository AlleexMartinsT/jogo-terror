"""Pegadas calculadas por contato (gerado por `python -m tools.movimento_ref.cenarios.pegadas gerar`; não edite).

GRIPS: a mão no referencial do item (posição, direção dos dedos, direção da palma). GRASPS: curls por junta
(polegar ao mindinho, base à ponta) da mão fechada no item e da pré-forma aberta. ROLL_SHIFT: quanto a mão
girou em torno do eixo do item, em graus (a lanterna gira o contrário para a mão ficar onde estava).
"""
GRIPS = {'FLASHLIGHT': ((-0.025, 0.018, 0.00075), (0.55995, 0.8083, -0.18194), (0.76874, -0.58877, -0.24978)), 'KEY': ((-0.029, -0.013, 0.053), (-0.02513, 0.22872, -0.97317), (0.7212, -0.66998, -0.17609)), 'BATTERY': ((0.0, -0.036, 0.024), (0.03834, 0.48711, -0.8725), (0.06846, 0.86981, 0.48862))}
GRASPS = {'FLASHLIGHT': {'side': 'R', 'closed': [[0.0196, 0.0, 0.0], [0.6598, 0.773, 0.6224], [0.6955, 0.7923, 0.6379], [0.6902, 0.7863, 0.633], [0.6382, 0.7255, 0.5709]], 'preform': [[0.3, 0.25, 0.25], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1]], 'pressed': [0.0581, 0.0, 0.0]}, 'KEY': {'side': 'L', 'closed': [[0.0, 0.4938, 0.4981], [0.2368, 0.62, 0.5], [0.42, 0.441, 0.357], [0.5, 0.525, 0.425], [0.56, 0.588, 0.476]], 'preform': [[0.3, 0.25, 0.25], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1]], 'pressed': None}, 'BATTERY': {'side': 'L', 'closed': [[0.3, 0.15, 0.5137], [0.3725, 0.58, 0.44], [0.4481, 0.6, 0.46], [0.3173, 0.62, 0.48], [0.2969, 0.41, 0.5]], 'preform': [[0.3, 0.25, 0.25], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1]], 'pressed': None}}
ROLL_SHIFT = {'FLASHLIGHT': -180.0, 'KEY': 0.0, 'BATTERY': 0.0}
