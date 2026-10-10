"""Pegadas calculadas por contato (gerado por `python -m tools.movimento_ref.cenarios.pegadas gerar`; não edite).

GRIPS: a mão no referencial do item (posição, direção dos dedos, direção da palma). GRASPS: curls por junta
(polegar ao mindinho, base à ponta) da mão fechada no item e da pré-forma aberta. ROLL_SHIFT: quanto a mão
girou em torno do eixo do item, em graus (a lanterna gira o contrário para a mão ficar onde estava).
"""
GRIPS = {'FLASHLIGHT': ((-0.025, 0.018, 0.00075), (0.55995, 0.8083, -0.18194), (0.76874, -0.58877, -0.24978)), 'KEY': ((-0.0395, -0.013, 0.053), (0.04388, 0.26615, -0.96293), (0.75053, -0.64494, -0.14406)), 'BATTERY': ((-0.012, -0.03, 0.033), (0.49693, 0.30902, -0.81091), (-0.16146, 0.95106, 0.26348))}
GRASPS = {'FLASHLIGHT': {'side': 'R', 'closed': [[0.0196, 0.0, 0.0], [0.6598, 0.773, 0.6224], [0.6955, 0.7923, 0.6379], [0.6902, 0.7863, 0.633], [0.6382, 0.7255, 0.5709]], 'preform': [[0.3, 0.25, 0.25], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1]], 'pressed': [0.0581, 0.0, 0.0]}, 'KEY': {'side': 'L', 'closed': [[0.0, 0.1374, 0.498], [0.2731, 0.62, 0.5], [0.42, 0.441, 0.357], [0.47, 0.495, 0.395], [0.56, 0.588, 0.476]], 'preform': [[0.3, 0.25, 0.25], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1]], 'pressed': None}, 'BATTERY': {'side': 'L', 'closed': [[0.1925, 0.0515, 0.4996], [0.5, 0.58, 0.44], [0.3055, 0.6, 0.46], [0.1, 0.12, 0.1], [0.1217, 0.4271, 0.5]], 'preform': [[0.3, 0.25, 0.25], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1], [0.1, 0.12, 0.1]], 'pressed': None}}
ROLL_SHIFT = {'FLASHLIGHT': -180.0, 'KEY': 0.0, 'BATTERY': 0.0}
