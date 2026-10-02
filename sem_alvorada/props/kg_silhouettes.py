"""Silhuetas 2D das ferramentas do painel da garagem (dados puros, sem bpy).

Uma única fonte de formas serve a dois usos: `garage_tools` extruda estes polígonos para modelar a ferramenta,
e `tex_cozinha_garagem` contorna os mesmos polígonos à caneta no painel. É por isso que o contorno da ferramenta
que sumiu (o martelo) bate exatamente com o martelo que está em cima da bancada.

Coordenadas (u, v) em metros com a ferramenta pendurada: origem no furo de pendurar, u para a direita,
v para cima (a ferramenta desce, então v é negativo).
"""

HAMMER_HANDLE = [(-0.0125, -0.30), (0.0125, -0.30), (0.0105, -0.12), (-0.0105, -0.12)]
HAMMER_HEAD = [(-0.072, -0.12), (0.062, -0.12), (0.066, -0.098), (0.062, -0.074), (0.05, -0.066), (0.012, -0.066),
               (-0.012, -0.07), (-0.05, -0.052), (-0.085, -0.025), (-0.088, -0.045), (-0.062, -0.085), (-0.072, -0.1)]
HAMMER_OUTLINE = [(-0.0125, -0.30), (0.0125, -0.30), (0.0105, -0.12), (0.062, -0.12), (0.066, -0.098), (0.062, -0.074),
                  (0.05, -0.066), (0.012, -0.066), (-0.012, -0.07), (-0.05, -0.052), (-0.085, -0.025), (-0.088, -0.045),
                  (-0.062, -0.085), (-0.0105, -0.12)]

WRENCH = [(-0.011, -0.2), (0.011, -0.2), (0.012, -0.075), (0.032, -0.062), (0.034, -0.03), (0.02, -0.005), (0.004, -0.018),
          (0.004, -0.045), (-0.012, -0.045), (-0.012, -0.015), (-0.03, -0.005), (-0.036, -0.03), (-0.03, -0.062),
          (-0.012, -0.075)]

PLIERS_OUTLINE = [(-0.005, -0.005), (0.005, -0.005), (0.015, -0.04), (0.02, -0.07), (0.017, -0.095), (0.032, -0.205),
                  (0.013, -0.208), (0.0, -0.125), (-0.013, -0.208), (-0.032, -0.205), (-0.017, -0.095), (-0.02, -0.07),
                  (-0.015, -0.04)]

def _teeth(start, end, count, depth):
    """Dentes de serra ao longo de um segmento: zigue-zague com `depth` de altura, inclinado para a frente."""
    points = []
    for index in range(count):
        t0, t1 = index / count, (index + 0.8) / count
        base0 = (start[0] + (end[0] - start[0]) * t0, start[1] + (end[1] - start[1]) * t0)
        base1 = (start[0] + (end[0] - start[0]) * t1, start[1] + (end[1] - start[1]) * t1)
        points += [(base0[0] + depth, base0[1]), (base1[0], base1[1])]
    return points


_SAW_TOOTH_EDGE = _teeth((0.0, -0.45), (0.044, -0.17), 22, 0.0035)
SAW_BLADE = [(-0.022, -0.45)] + _SAW_TOOTH_EDGE + [(0.044, -0.1), (-0.036, -0.1), (-0.04, -0.17)]
SAW_HANDLE = [(-0.04, -0.1), (0.044, -0.1), (0.05, -0.07), (0.052, -0.035), (0.04, -0.012), (0.0, -0.005), (-0.04, -0.012),
              (-0.05, -0.04), (-0.046, -0.075)]
SAW_OUTLINE = [(-0.022, -0.45)] + _SAW_TOOTH_EDGE + [(0.044, -0.1), (0.05, -0.07), (0.052, -0.035), (0.04, -0.012), (0.0, -0.005),
                                                      (-0.04, -0.012), (-0.05, -0.04), (-0.046, -0.075), (-0.04, -0.1),
                                                      (-0.04, -0.17)]

SCREWDRIVER_OUTLINE = [(-0.015, -0.0), (0.015, 0.0), (0.017, -0.04), (0.012, -0.1), (0.004, -0.1), (0.003, -0.26),
                       (-0.003, -0.26), (-0.004, -0.1), (-0.012, -0.1), (-0.017, -0.04)]

# nome -> (x da placa em metros desde a esquerda, z do furo de pendurar desde a base, contorno)
PANEL_SLOTS = {
    "wrench": (0.26, 0.80, WRENCH),
    "pliers": (0.52, 0.80, PLIERS_OUTLINE),
    "hammer": (0.82, 0.78, HAMMER_OUTLINE),
    "saw": (1.18, 0.82, SAW_OUTLINE),
    "driver_flat": (1.45, 0.78, SCREWDRIVER_OUTLINE),
    "driver_cross": (1.55, 0.78, SCREWDRIVER_OUTLINE),
}
MISSING = "hammer"
