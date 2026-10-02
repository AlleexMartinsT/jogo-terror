"""Forma do sedã: medidas e curvas que o script de modelagem e o construtor do carro compartilham.

Não importa `bpy`: o mesmo código desenha a carroceria nas ferramentas de autoria (`tools/modelagem/
carro_carroceria.py`, que faz as booleanas e grava um `.npz`) e posiciona faróis, para-choques e vidros
dentro do Blender. Assim as peças soltas sempre encostam na chapa.

Coordenadas locais do carro: origem no centro da base, frente = +Y, motorista em -X, Z para cima.
Referência de proporção: sedã grande americano dos anos 90 (entre-eixos de 2,90 m, largura 1,88 m).
"""
import numpy as np

HALF_LENGTH = 2.26          # chapa, sem os para-choques (que avançam até 2,42)
WHEEL_Y = 1.45              # entre-eixos de 2,90 m
WHEEL_X = 0.80
WHEEL_RADIUS = 0.33
ARCH_RADIUS = 0.385
BELT_Z = 1.00               # linha da cintura: topo das portas, base dos vidros
ROOF_Z = 1.40
FLOOR_Z = 0.20              # fundo do assoalho
COWL_Y = 0.98               # base do para-brisa
REAR_GLASS_BASE_Y = -1.60   # base do vidro traseiro, onde começa o porta-malas

FRONT_DOOR = (0.82, -0.24)       # (borda dianteira, borda traseira) em y
REAR_DOOR = (-0.24, -1.03)
DOOR_BOTTOM_Z = 0.30
HANDLE_Y = (-0.10, -0.92)         # y das maçanetas das portas dianteira e traseira
GROOVE_WIDTH = 0.0050
GROOVE_DEPTH = 0.0075


def smooth_curve(points):
    """Interpolação cúbica monótona (Fritsch-Carlson) por `points` [(x, y), ...]; devolve f(x) vetorizada.

    Monótona significa que a curva nunca passa por cima de um ponto de controle: sem as ondulações que
    um spline comum cria entre pontos próximos, o que importa para um perfil de capô.
    """
    xs = np.array([p[0] for p in points], float)
    ys = np.array([p[1] for p in points], float)
    steps, slopes = np.diff(xs), np.diff(ys) / np.diff(xs)
    tangents = np.zeros_like(ys)
    for k in range(1, len(xs) - 1):
        if slopes[k - 1] * slopes[k] > 0:
            w1, w2 = 2 * steps[k] + steps[k - 1], steps[k] + 2 * steps[k - 1]
            tangents[k] = (w1 + w2) / (w1 / slopes[k - 1] + w2 / slopes[k])
    tangents[0], tangents[-1] = slopes[0], slopes[-1]

    def evaluate(x):
        x = np.asarray(x, float)
        k = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
        t = (x - xs[k]) / steps[k]
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return h00 * ys[k] + h10 * steps[k] * tangents[k] + h01 * ys[k + 1] + h11 * steps[k] * tangents[k + 1]

    return evaluate


def smoothstep(edge0, edge1, x):
    t = np.clip((np.asarray(x, float) - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# Perfis ao longo do comprimento (y). Valores lidos de uma vista lateral e de uma vista de cima.
_DECK_Z = smooth_curve([(-2.26, 0.950), (-2.15, 0.980), (-1.90, 1.010), (-1.60, 1.022), (-1.40, 1.000),
                        (0.90, 1.000), (1.10, 0.985), (1.55, 0.935), (2.00, 0.880), (2.26, 0.815)])


def deck_z(y):
    """Altura do centro do capô, da cabine (cintura) e do porta-malas."""
    return _DECK_Z(y)


def half_width(y):
    """Meia-largura máxima da chapa: reta no meio e arredondada nos cantos em planta."""
    t = np.clip((np.abs(np.asarray(y, float)) - 1.92) / (HALF_LENGTH - 1.92), 0.0, 1.0)
    hip = 0.011 * np.exp(-(((np.abs(np.asarray(y, float)) - WHEEL_Y) / 0.55) ** 2))     # volume do para-lama sobre a roda
    return 0.94 + hip - 0.30 * (1.0 - np.sqrt(1.0 - t ** 2))


def nose_y(x):
    """y (positivo) do fim da chapa na frente/traseira em |x|: reto no centro e contornando o canto."""
    x = np.abs(np.asarray(x, float))
    u = np.clip((x - 0.64) / 0.30, 0.0, 1.0)
    return np.where(x <= 0.64, HALF_LENGTH, 1.92 + 0.34 * np.sqrt(1.0 - u * u))


def bottom_z(y):
    """Fundo da carroceria: sobe nas pontas (spoiler dianteiro, saia traseira)."""
    return FLOOR_Z + 0.22 * smoothstep(1.85, HALF_LENGTH, np.abs(np.asarray(y, float))) ** 1.5


def crown(y):
    """Quanto o centro do capô/porta-malas sobe em relação à quina com o para-lama."""
    y = np.asarray(y, float)
    return 0.040 * smoothstep(COWL_Y, 1.35, y) + 0.022 * smoothstep(REAR_GLASS_BASE_Y, -1.85, y)


def side_offset(z):
    """Quanto a lateral se afasta da largura máxima em cada altura: barriga em z=0,7 e tumblehome acima."""
    z = np.asarray(z, float)
    shoulder = 0.011 * np.exp(-(((z - 0.80) / 0.05) ** 2))                  # vinco suave na altura do ombro
    return np.where(z >= 0.70, 0.78 * (z - 0.70) ** 2, 0.30 * (0.70 - z) ** 2) - shoulder


def side_x(y, z):
    """Posição x (lado +X) da chapa lateral na altura z, na estação y."""
    return half_width(y) - side_offset(z)


def hood_x_half(y):
    """Meia-largura do capô (entre as quinas dos para-lamas)."""
    return half_width(y) - 0.115


def hood_surface_z(x, y):
    """Altura da superfície do capô/porta-malas em (x, y), com abaulamento e vinco central."""
    x = np.abs(np.asarray(x, float))
    reach = np.maximum(hood_x_half(y), 0.2)
    bulge = crown(y) * (x / reach) ** 2
    ridge = 0.0045 * np.exp(-(x / 0.07) ** 2) * smoothstep(COWL_Y, 1.3, np.asarray(y, float))
    return deck_z(y) - bulge + ridge


# --------------------------------------------------------------------------------------------
# Seção transversal
# --------------------------------------------------------------------------------------------
def _round_corner(previous, corner, following, setback, steps):
    """Troca o vértice `corner` por um arco (Bézier quadrático) que começa e termina a `setback` do vértice."""
    a, c, b = (np.asarray(p, float) for p in (previous, corner, following))
    to_a, to_b = a - c, b - c
    start = c + to_a / np.linalg.norm(to_a) * min(setback, np.linalg.norm(to_a) * 0.45)
    end = c + to_b / np.linalg.norm(to_b) * min(setback, np.linalg.norm(to_b) * 0.45)
    t = np.linspace(0.0, 1.0, steps)[:, None]
    return (1 - t) ** 2 * start + 2 * (1 - t) * t * c + t ** 2 * end


def _round_path(points, setbacks, steps=4):
    """Polilinha com os cantos listados em `setbacks` {índice: recuo} arredondados."""
    out = []
    for index, point in enumerate(points):
        if index in setbacks:
            out.extend(_round_corner(points[index - 1], point, points[index + 1], setbacks[index], steps))
        else:
            out.append(np.asarray(point, float))
    return np.array(out)


SIDE_FRACTIONS = (0.0, 0.08, 0.18, 0.29, 0.40, 0.52, 0.64, 0.75, 0.84, 0.92)
DECK_FRACTIONS = (0.10, 0.20, 0.31, 0.43, 0.56, 0.70, 0.85, 1.0)


def _crest(y):
    """Quina entre a lateral e o capô/cintura: (x, z). Duas passagens, porque x depende de z e z de x."""
    top, lift = float(deck_z(y)), float(crown(y))
    x = float(side_x(y, top - 1.35 * lift))
    z = float(hood_surface_z(x, y))
    return float(side_x(y, z)), z


def half_section(y):
    """Metade direita (x >= 0) da seção na estação y: do centro do fundo, subindo pela lateral, até o centro do topo.

    Sempre devolve o mesmo número de pontos, para os anéis do loft casarem ponto a ponto.
    """
    y = float(y)
    width, low = float(half_width(y)), float(bottom_z(y))
    crest_x, crest_z = _crest(y)
    start = low + 0.07
    points = [(0.0, low), (0.58 * width / 0.94, low), (float(side_x(y, start)) - 0.03, low)]
    points += [(float(side_x(y, z)), z) for z in (start + (crest_z - start) * f for f in SIDE_FRACTIONS)]
    crest_index = len(points)
    points.append((crest_x, crest_z))
    points += [(crest_x * (1.0 - u), float(hood_surface_z(crest_x * (1.0 - u), y))) for u in DECK_FRACTIONS]
    return _round_path(points, {2: 0.05, crest_index: 0.045})


def full_section(y):
    """Anel fechado (M, 3) da seção na estação y: lado +X do fundo ao topo, depois o espelho no lado -X."""
    right = half_section(y)
    left = right[-2:0:-1].copy()
    left[:, 0] *= -1.0
    ring = np.concatenate([right, left])
    return np.column_stack([ring[:, 0], np.full(len(ring), float(y)), ring[:, 1]])


def stations():
    """Posições y dos anéis do loft: densas nas pontas, onde a curvatura muda depressa."""
    ends = np.array([0.0, 0.006, 0.02, 0.045, 0.08, 0.13, 0.20])
    near_ends = HALF_LENGTH - ends
    middle = np.arange(-(HALF_LENGTH - 0.28), (HALF_LENGTH - 0.28) + 1e-6, 0.06)
    return np.unique(np.round(np.concatenate([-near_ends, middle, near_ends]), 4))


# --------------------------------------------------------------------------------------------
# Cabine (teto, colunas e vidros)
# --------------------------------------------------------------------------------------------
WINDSHIELD_BASE = (COWL_Y, BELT_Z)       # (y, z) da linha do para-brisa
WINDSHIELD_TOP = (0.28, ROOF_Z)
REAR_GLASS_TOP = (-1.00, ROOF_Z - 0.005)
REAR_GLASS_BASE = (REAR_GLASS_BASE_Y, 1.035)
PILLAR_B = (-0.215, -0.265)               # (borda dianteira, borda traseira) do pilar B
GLASS_RECESS = 0.022                      # quanto o vidro entra na casca da cabine


def cabin_half_width(z):
    """Meia-largura da cabine na altura z: pende para dentro 0,40 m a cada metro (tumblehome)."""
    return 0.872 - 0.40 * (np.asarray(z, float) - BELT_Z)


def cabin_taper(y):
    """Fator de largura da cabine em y: afunila para trás (coluna C) e levemente para a frente."""
    y = np.asarray(y, float)
    return 1.0 - 0.07 * smoothstep(-0.9, -1.7, y) - 0.03 * smoothstep(0.45, 1.05, y)


def _line_y(top, base, z):
    return top[0] + (base[0] - top[0]) * (z - top[1]) / (base[1] - top[1])


def a_pillar_y(z):
    """y da linha do pilar A / plano do para-brisa na altura z."""
    return _line_y(WINDSHIELD_TOP, WINDSHIELD_BASE, z)


def c_pillar_y(z):
    """y da linha do pilar C / plano do vidro traseiro na altura z."""
    return _line_y(REAR_GLASS_TOP, REAR_GLASS_BASE, z)


def _inward(top, base):
    """Deslocamento (dy, dz) de GLASS_RECESS para dentro da cabine, perpendicular à linha base-topo."""
    direction = np.array([top[0] - base[0], top[1] - base[1]], float)
    direction /= np.linalg.norm(direction)
    outward = np.array([-direction[1], direction[0]])
    if outward[1] < 0:
        outward = -outward
    return -outward * GLASS_RECESS


def side_window_polygons():
    """Contornos (y, z) dos vidros laterais: porta dianteira e porta traseira."""
    sill, header = BELT_Z + 0.045, ROOF_Z - 0.060
    front = [(a_pillar_y(sill) - 0.10, sill), (PILLAR_B[0], sill), (PILLAR_B[0], header),
             (a_pillar_y(header) - 0.095, header)]
    rear = [(PILLAR_B[1], sill), (c_pillar_y(sill) + 0.17, sill), (c_pillar_y(header) + 0.22, header),
            (PILLAR_B[1], header)]
    return {"front": front, "rear": rear}


def side_window_surface_x(z):
    """x do plano do vidro lateral (um pouco para dentro da chapa)."""
    return cabin_half_width(z) - GLASS_RECESS


def _sloped_glass(top, base, z_low, z_high, inset_x, line_y):
    """Quadrilátero 3D no plano inclinado entre `base` e `top`: (-x, baixo), (+x, baixo), (+x, alto), (-x, alto)."""
    dy, dz = _inward(top, base)
    corners = []
    for z, sign in ((z_low, -1), (z_low, 1), (z_high, 1), (z_high, -1)):
        y_on_plane = float(line_y(z))
        half = float(cabin_half_width(z)) * float(cabin_taper(y_on_plane)) - inset_x
        corners.append((sign * half, y_on_plane + dy, z + dz))
    return np.array(corners)


def glass_polygons():
    """Vidros planos (4 cantos 3D cada): para-brisa, vidro traseiro e os quatro laterais (p = passageiro, d = motorista)."""
    glass = {
        "windshield": _sloped_glass(WINDSHIELD_TOP, WINDSHIELD_BASE, BELT_Z + 0.025, ROOF_Z - 0.075, 0.062, a_pillar_y),
        "rear": _sloped_glass(REAR_GLASS_TOP, REAR_GLASS_BASE, REAR_GLASS_BASE[1] + 0.03, REAR_GLASS_TOP[1] - 0.055,
                              0.115, c_pillar_y),
    }
    for name, polygon in side_window_polygons().items():
        for sign, tag in ((1, "p"), (-1, "d")):
            glass[f"side_{name}_{tag}"] = np.array([(sign * float(side_window_surface_x(z)), y, z) for y, z in polygon])
    return glass
