"""Formas reutilizáveis de móveis: tampos moldurados, pernas torneadas, almofadas, braços enrolados, molduras.

Cada função desenha dentro de um `MeshBuilder` já em andamento, nas coordenadas locais do móvel (origem
no centro da base, frente = +Y, Z para cima), como as de `parts.py`. As formas orgânicas (almofada) são
geradas direto por anéis de seção; as demais usam `loft`, `lathe` e `extrude` do kit.
"""
import math

from .. import craft
from . import kit
from . import tex_sala  # noqa: F401  (registra as texturas e os materiais de tudo que usa estas formas)
from .kit import rounded_rect


# Receitas de acabamento das partes de uma `Composite` (ver `composite.py`). Só a marcenaria de caixas leva chanfro:
# peças torneadas, lajes moldadas e ferragens já têm o perfil curvo, e um chanfro em cima multiplicaria os triângulos.
WOOD = craft.Finish(bevel=0.004, bevel_segments=1, smooth_angle=48)
WOOD_HERO = craft.Finish(bevel=0.005, bevel_segments=2, smooth_angle=48)
SMOOTH = craft.Finish(bevel=0.0, smooth_angle=55)
PADDING = craft.Finish(bevel=0.0, subsurf=1, smooth_angle=70)


def smooth01(t):
    """Degrau suave de 0 a 1 (zero abaixo de 0 e um acima de 1)."""
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def seg(count):
    """Número de lados de um torno ou anel; a qualidade 'low' corta pela metade, sem remover a peça."""
    return max(8, count // 2) if kit.QUALITY == "low" else count


# ---------------------------------------------------------------------------
# Lajes moldadas: tampos de mesa, soquetes, cornijas
# ---------------------------------------------------------------------------
OGEE_EDGE = ((0.0, 0.026), (0.006, 0.012), (0.012, 0.004), (0.017, 0.0), (0.031, 0.0), (0.035, 0.003),
             (0.038, 0.008), (0.040, 0.014))                       # tampo de 40 mm, borda em S
BULLNOSE_EDGE = ((0.0, 0.006), (0.004, 0.001), (0.010, 0.0), (0.026, 0.0), (0.032, 0.001), (0.036, 0.004),
                 (0.038, 0.009))
THIN_EDGE = ((0.0, 0.018), (0.004, 0.006), (0.010, 0.0), (0.025, 0.0), (0.031, 0.003), (0.035, 0.008))
CORNICE = ((0.0, 0.0), (0.012, 0.0), (0.016, -0.006), (0.024, -0.010), (0.034, -0.012), (0.040, -0.012),
           (0.044, -0.008), (0.048, 0.0))                          # cornija que avança (inset negativo)


def slab(m, cx, cy, z0, width, depth, levels, mat, radius=0.02, corner_points=4, uv=1.0):
    """Laje retangular de cantos arredondados cujo contorno encolhe (ou cresce) segundo `levels`.

    `levels`: [(altura acima de z0, recuo do contorno), ...] de baixo para cima. Como todos os anéis têm o
    mesmo número de pontos, o perfil vale também nos cantos: é uma moldura sem emendas.
    """
    rings = []
    for height, inset in levels:
        outline = rounded_rect(width - 2 * inset, depth - 2 * inset, max(radius - inset, 0.002), corner_points)
        rings.append([(cx + x, cy + y, z0 + height) for x, y in outline])
    m.loft(rings, mat, True, True, False, uv)


# ---------------------------------------------------------------------------
# Torno
# ---------------------------------------------------------------------------
# (fração do raio máximo, fração da altura) de baixo para cima
LEG_PROFILES = {
    "baluster": ((0.50, 0.0), (0.56, 0.04), (0.44, 0.09), (0.40, 0.14), (0.62, 0.22), (0.92, 0.33), (1.0, 0.40),
                 (0.88, 0.50), (0.58, 0.60), (0.50, 0.70), (0.64, 0.78), (0.76, 0.84), (0.60, 0.88), (0.68, 1.0)),
    "spindle": ((0.70, 0.0), (0.55, 0.05), (0.50, 0.15), (0.80, 0.22), (0.62, 0.30), (0.48, 0.45), (0.60, 0.55),
                (0.95, 0.62), (0.60, 0.72), (0.70, 0.80), (1.0, 0.86), (0.80, 1.0)),
    "tapered": ((0.45, 0.0), (0.48, 0.03), (0.40, 0.045), (0.56, 0.08), (0.78, 0.5), (0.96, 0.95), (1.0, 1.0)),
    "bun": ((0.62, 0.0), (0.92, 0.10), (1.0, 0.22), (0.82, 0.38), (0.42, 0.48), (0.50, 0.58), (0.58, 1.0)),
}


def turned_leg(m, cx, cy, z0, height, radius, mat, style="baluster", sides=16):
    """Perna torneada de `height` m e raio máximo `radius`, apoiada em z0."""
    profile = [(radius * r, height * t) for r, t in LEG_PROFILES[style]]
    m.lathe(profile, cx, cy, z0, mat, seg=seg(sides), smooth=True)


def round_knob(m, cx, y, cz, radius, mat, facing=1.0):
    """Puxador de gaveta redondo e torneado, saindo da frente (facing 1 = +Y, -1 = -Y)."""
    with m.at(cx, y, cz, rx=-90 * facing):
        m.lathe([(radius * 0.55, 0.0), (radius * 0.4, 0.006), (radius * 0.55, 0.012), (radius, 0.022),
                 (radius * 0.95, 0.028), (radius * 0.5, 0.032), (0.0, 0.0335)], 0, 0, 0, mat, seg=seg(14), smooth=True)


def bail_pull(m, cx, y, cz, spread, mat, plate_mat=None, facing=1.0):
    """Puxador em alça de latão sobre duas rosetas, para gavetas de escrivaninha e cômoda."""
    plate_mat = plate_mat or mat
    for side in (-1, 1):
        px = cx + side * spread / 2
        with m.at(px, y, cz, rx=-90 * facing):
            m.lathe([(0.011, 0.0), (0.011, 0.003), (0.008, 0.005), (0.004, 0.0065), (0.0, 0.0065)], 0, 0, 0,
                    plate_mat, seg=seg(10), smooth=True)
    rise = 0.012
    anchors = [(cx - spread / 2, y + facing * 0.006, cz), (cx - spread / 2, y + facing * (0.006 + rise), cz - 0.004),
               (cx + spread / 2, y + facing * (0.006 + rise), cz - 0.004), (cx + spread / 2, y + facing * 0.006, cz)]
    for start, end in zip(anchors, anchors[1:]):
        m.tube(start, end, 0.0032, mat, seg=6, smooth=True)


def escutcheon(m, cx, y, cz, mat, facing=1.0):
    """Espelho de fechadura (placa de latão com a boca da chave)."""
    with m.at(cx, y, cz, rx=-90 * facing):
        m.lathe([(0.012, 0.0), (0.012, 0.002), (0.008, 0.003), (0.0, 0.003)], 0, 0, 0, mat, seg=seg(10), smooth=True)
    m.box(cx, y + facing * 0.0032, cz - 0.006, 0.003, 0.0012, 0.011, "black")


# ---------------------------------------------------------------------------
# Almofadas e estofados
# ---------------------------------------------------------------------------
def cushion(m, cx, cy, z0, width, depth, thickness, mat, *, squareness=3.2, corner=0.30, crown=0.0,
            dimple=0.0, dimple_at=(0.0, 0.0), wrinkle=0.0, phase=0.0, sides=6, rings=14):
    """Almofada: casca fechada de seções retangulares arredondadas que encolhem até os polos.

    `squareness` (expoente da superelipse): 2 = elipsoide, 4 = quase caixa de quinas redondas.
    `crown` abaulamento do topo (m); `dimple` profundidade do botão do capitonê (m) em `dimple_at`
    (fração do tamanho, a partir do centro); `wrinkle` amplitude (m) de ondulação suave do tecido.
    Devolve [(seno, contorno)] dos anéis, para passar o vivo (`piping_at`) onde o tampo encontra a lateral.
    """
    corner_points = max(3, sides // 2 + 1) if kit.QUALITY == "low" else sides
    half_height = thickness / 2
    radius_corner = corner * min(width, depth)
    ring_count = rings if kit.QUALITY != "low" else max(8, rings - 4)
    dent = dimple * math.exp(-((dimple_at[0] / 0.07) ** 2 + (dimple_at[1] / 0.07) ** 2))
    rows = [[(cx, cy, z0)]]
    kept = []
    for k in range(1, ring_count):
        sine = math.sin(math.pi / 2 * (-1 + 2 * k / ring_count))
        scale = (1 - abs(sine) ** squareness) ** (1 / squareness)
        outline = rounded_rect(width * scale, depth * scale, max(radius_corner * scale, 0.002), corner_points)
        z_base = z0 + half_height + sine * half_height
        ring = []
        for x, y in outline:
            lift = 0.0
            if sine > 0:
                lift += crown * (1 - scale) ** 2
                lift -= dimple * math.exp(-(((x / width - dimple_at[0]) / 0.07) ** 2 + ((y / depth - dimple_at[1]) / 0.07) ** 2))
            if wrinkle:
                lift += wrinkle * math.sin(7.0 * x + phase) * math.sin(6.0 * y + 1.7 * phase) * (1 - scale * 0.5)
            ring.append((cx + x, cy + y, z_base + lift))
        rows.append(ring)
        kept.append((sine, ring))
    rows.append([(cx, cy, z0 + thickness + crown - dent)])
    m.loft(rows, mat, False, False, True)
    return kept


def piping_at(m, rows, sine, radius, mat, grow=0.0035):
    """Vivo (cordão de costura) no anel de `cushion` mais próximo de `sine`, um pouco para fora do tecido."""
    _, ring = min(rows, key=lambda row: abs(row[0] - sine))
    center_x = sum(p[0] for p in ring) / len(ring)
    center_y = sum(p[1] for p in ring) / len(ring)
    outline = []
    for x, y, z in ring:
        away = math.hypot(x - center_x, y - center_y) or 1.0
        outline.append((x + (x - center_x) / away * grow, y + (y - center_y) / away * grow, z))
    piping_loop(m, outline, radius, mat)


def piping_loop(m, outline, radius, mat, sides=5):
    """Vivo (cordão de costura) em volta de um contorno fechado de pontos 3D."""
    for index, start in enumerate(outline):
        m.tube(start, outline[(index + 1) % len(outline)], radius, mat, seg=sides, smooth=True, caps=(False, False))


def rolled_arm(m, cx, y0, y1, z0, half_width, roll_z, mat):
    """Braço enrolado de sofá: perfil em pirulito extrudado ao longo de Y, de y0 (fundo) a y1 (frente).

    O rolo tem raio `half_width / cos(35 graus)` para o arco encontrar a lateral reta sem degrau.
    Devolve o raio do rolo (para o disco decorativo da frente).
    """
    roll_radius = half_width / math.cos(math.radians(35))
    profile = [(cx - half_width, z0), (cx + half_width, z0)]
    arc_steps = 14
    for step in range(arc_steps + 1):
        angle = math.radians(-35 + 250 * step / arc_steps)
        profile.append((cx + roll_radius * math.cos(angle), roll_z + roll_radius * math.sin(angle)))
    m.extrude(profile, "xz", y0, y1, mat)
    return roll_radius


def scroll_face(m, cx, y, cz, radius, mat, button_mat=None):
    """Disco levemente abaulado na frente do braço enrolado, com um botão no meio."""
    with m.at(cx, y, cz, rx=-90):
        m.lathe([(radius, 0.0), (radius, 0.004), (radius * 0.93, 0.010), (radius * 0.72, 0.015), (radius * 0.42, 0.012),
                 (radius * 0.20, 0.006), (0.0, 0.004)], 0, 0, 0, mat, seg=seg(20), smooth=True)
        m.sphere(0, 0, 0.006, 0.011, button_mat or mat, seg=seg(10), rings=5, squash=0.55)


def button(m, cx, cy, cz, mat, radius=0.012):
    """Botão forrado do capitonê."""
    m.sphere(cx, cy, cz, radius, mat, seg=seg(10), rings=5, squash=0.6)


# ---------------------------------------------------------------------------
# Molduras
# ---------------------------------------------------------------------------
def mitred_frame(m, cx, cy, cz, width, height, profile, mat):
    """Moldura retangular com esquadria a 45 graus, no plano XZ voltada para +Y.

    `profile`: [(recuo para fora a partir da abertura, profundidade em Y), ...] da borda de dentro para a de fora.
    A abertura é `width` x `height`; a moldura cresce para fora dela.
    """
    rings = []
    for outward, depth in profile:
        half_w, half_h = width / 2 + outward, height / 2 + outward
        rings.append([(cx + half_w, cy + depth, cz - half_h), (cx + half_w, cy + depth, cz + half_h),
                      (cx - half_w, cy + depth, cz + half_h), (cx - half_w, cy + depth, cz - half_h)])
    m.loft(rings, mat, False, False, False, orient=False)
