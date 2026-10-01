"""Modelos dos itens coletáveis: chave, pilhas, mapa e as sete notas.

São os objetos que o jogador pega, vira e lê de perto sob a lanterna. Por isso cada um tem construção
própria (lâmina fresada, rótulo de pilha, dobras de papel), e não caixas com textura.

Várias peças precisam de acabamento diferente no mesmo objeto (chanfro fino no metal, nenhum no papel).
`Assembly` junta partes com receitas distintas numa malha só.
"""
import math
from contextlib import contextmanager

from mathutils import Euler, Matrix

from .. import craft
from . import paper, parts, tex_itens  # noqa: F401  (tex_itens registra texturas e materiais ao ser importado)
from .kit import MeshBuilder, circle_points, rounded_rect

PAPER = craft.RAW
FINE_METAL = craft.Finish(bevel=0.0006, bevel_segments=2, smooth_angle=45)
SMOOTH_ONLY = craft.Finish(bevel=0.0, smooth_angle=55)
SOFT_RUBBER = craft.Finish(bevel=0.0012, bevel_segments=3, smooth_angle=70)


class Assembly:
    """Várias partes (cada uma com sua receita de acabamento) que viram uma malha só."""

    def __init__(self, name):
        self.name = name
        self.parts = []
        self._frame = Matrix.Identity(4)

    @contextmanager
    def at(self, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
        """Mesma convenção de `MeshBuilder.at`; vale para as partes criadas dentro do bloco."""
        saved = self._frame
        rotation = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_matrix().to_4x4()
        self._frame = saved @ Matrix.Translation((x, y, z)) @ rotation
        try:
            yield self
        finally:
            self._frame = saved

    def part(self, finish=SMOOTH_ONLY):
        builder = MeshBuilder(self.name)
        builder.finish = finish
        builder._xf = self._frame.copy()
        self.parts.append(builder)
        return builder

    def bounds(self):
        lows, highs = zip(*(part.bounds() for part in self.parts if part._faces))
        return (tuple(min(v[i] for v in lows) for i in range(3)),
                tuple(max(v[i] for v in highs) for i in range(3)))

    def to_mesh(self, name=None):
        meshes = [part.to_mesh(f"{name or self.name}_p{index}") for index, part in enumerate(self.parts)
                  if part._faces]
        return craft.join_meshes(meshes, name or self.name)


def _prism(m, outline, z0, z1, mat, uv_scale=40.0):
    """Extrusão vertical de um contorno anti-horário (pode ser côncavo): topo, fundo e laterais."""
    top = [(x, y, z1) for x, y in outline]
    m.poly(top, mat, uv=[(x * uv_scale, y * uv_scale) for x, y in outline])
    m.poly([(x, y, z0) for x, y in reversed(outline)], mat)
    count = len(outline)
    for index in range(count):
        a, b = outline[index], outline[(index + 1) % count]
        m.quad((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1), mat)


# ---------------------------------------------------------------------------
# Chave do carro
# ---------------------------------------------------------------------------
def build_key():
    """Chave de carro: lâmina fresada com dentes, cabeça de borracha com miolo cromado, argola dupla,
    três elos e o coelhinho de pelúcia da Emma. Um pouco maior que o real (1,3x) para ser mirada."""
    k = 1.3
    item = Assembly("Item_KEY")

    blade = item.part(FINE_METAL)
    width, length = 0.0085 * k, 0.047 * k
    outline = [(-width / 2, 0.0), (-width / 2, -length + 0.004 * k), (-width / 2 + 0.0022 * k, -length),
               (width / 2 - 0.0022 * k, -length)]
    for tooth in range(5):
        low = -length + 0.0045 * k + tooth * 0.0074 * k
        depth = (0.0016, 0.0030, 0.0021, 0.0033, 0.0014)[tooth] * k
        outline += [(width / 2, low), (width / 2 - depth, low + 0.0008 * k),
                    (width / 2 - depth, low + 0.0030 * k), (width / 2, low + 0.0038 * k)]
    outline.append((width / 2, 0.0))
    _prism(blade, outline, 0.0, 0.0022 * k, "key_metal")
    blade.box(-width * 0.12, -length * 0.5, 0.0022 * k, 0.0012 * k, length * 0.82, 0.0004 * k, "key_metal")
    blade.box(0.0, 0.0038 * k, 0.0, 0.0125 * k, 0.0075 * k, 0.0035 * k, "chrome")

    head = item.part(SMOOTH_ONLY)
    head.soft_box(0, 0.0345 * k, 0.0, 0.034 * k, 0.050 * k, 0.0105 * k, "black", radius=0.0115 * k,
                  edge=0.0036 * k, corner_points=6, smooth=True)
    head.cylinder(0, 0.0395 * k, 0.0105 * k, 0.0088 * k, 0.0009 * k, "chrome", seg=28, smooth=True)
    head.cylinder(0, 0.0395 * k, 0.0114 * k, 0.0046 * k, 0.0004 * k, "black", seg=20, smooth=True)
    head.soft_box(0, 0.0215 * k, 0.0105 * k, 0.0120 * k, 0.0070 * k, 0.0016 * k, "rubber", radius=0.0030 * k,
                  edge=0.0007 * k, corner_points=4, smooth=True)
    head.soft_box(0, 0.0620 * k, 0.0105 * k, 0.0080 * k, 0.0060 * k, 0.0014 * k, "rubber", radius=0.0026 * k,
                  edge=0.0006 * k, corner_points=4, smooth=True)

    rings = item.part(FINE_METAL)
    rings.torus(0, 0.0660 * k, 0.0060 * k, 0.0046 * k, 0.0013 * k, "chrome", seg=20, seg_minor=6)
    for turn, tilt in enumerate((12.0, 16.0)):
        rings.torus(0, 0.0840 * k + turn * 0.0010 * k, 0.0046 * k + turn * 0.0012 * k, 0.0125 * k, 0.00075 * k,
                    "key_metal", seg=36, seg_minor=5, rx=tilt)
    for link in range(3):
        y = 0.1060 * k + link * 0.0080 * k
        rings.torus(0, y, 0.0036 * k, 0.0042 * k, 0.0010 * k, "chrome", seg=14, seg_minor=5,
                    rx=0.0 if link % 2 == 0 else 78.0)

    plush = item.part(craft.Finish(bevel=0.0, smooth_angle=70))
    with plush.at(0.0, 0.1360 * k, 0.0, rz=28):
        parts.rabbit(plush, 0, 0, 0, 0.20 * k)
    return item


# ---------------------------------------------------------------------------
# Pilhas
# ---------------------------------------------------------------------------
def _cell(m, radius, length, label_mat="battery_label"):
    """Uma pilha D deitada ao longo de +Z: base com anel, rótulo, selo de plástico, tampa e polo positivo."""
    seg = 28
    can = [(0.0, 0.0), (radius * 0.55, 0.0), (radius * 0.78, 0.0008), (radius * 0.86, 0.0030),
           (radius * 0.86, 0.0075)]
    m.lathe(can, 0, 0, 0.0, "chrome", seg=seg, smooth=True, cap_top=False)
    wrap_rings = [circle_points(0, 0, z, radius, seg) for z in (0.0065, length - 0.0075)]
    m.loft(wrap_rings, label_mat, cap_start=False, cap_end=False, smooth=True, orient=False, uv_grid=True)
    top = [(radius * 1.0, length - 0.0075), (radius * 0.84, length - 0.0070), (radius * 0.80, length - 0.0046),
           (radius * 0.58, length - 0.0030), (radius * 0.40, length - 0.0007), (radius * 0.34, length),
           (radius * 0.24, length + 0.0012), (radius * 0.20, length + 0.0030), (radius * 0.12, length + 0.0034),
           (0.0, length + 0.0034)]
    m.lathe(top, 0, 0, 0.0, "chrome", seg=seg, smooth=True, cap_bottom=False, cap_top=False)
    m.cylinder(0, 0, length - 0.0038, radius * 0.80, 0.0014, "black", seg=seg, smooth=True, caps=(False, False))


def build_battery_pair():
    """Duas pilhas D presas por fita prateada, com a ponta da fita levantada."""
    item = Assembly("Item_BATTERY")
    radius, length, gap = 0.0188, 0.0640, 0.0005
    cells = item.part(SMOOTH_ONLY)
    for side in (-1, 1):
        with cells.at(side * (radius + gap), -length / 2, radius, rx=-90):
            _cell(cells, radius, length)
    tape = item.part(PAPER)
    half_len = 0.0075
    outline = _stadium(2 * radius + gap + 0.0006, radius + 0.0007, 24)
    rings = [[(x, y, radius + z) for x, z in reversed(outline)] for y in (-half_len, half_len)]   # sentido que aponta para fora
    tape.loft(rings, "tape_silver", cap_start=False, cap_end=False, smooth=True, orient=False)
    return item


def _stadium(width, half_height, per_end):
    """Contorno (x, z) de um 'comprimido': duas semicircunferências ligadas, centrado em z=0."""
    radius = half_height
    center = width / 2 - radius
    points = []
    for index in range(per_end + 1):
        angle = -math.pi / 2 + math.pi * index / per_end
        points.append((center + radius * math.cos(angle), radius * math.sin(angle)))
    for index in range(per_end + 1):
        angle = math.pi / 2 + math.pi * index / per_end
        points.append((-center + radius * math.cos(angle), radius * math.sin(angle)))
    return [(x, z) for x, z in points]


# ---------------------------------------------------------------------------
# Mapa dobrado em sanfona
# ---------------------------------------------------------------------------
def build_map():
    """Mapa rodoviário dobrado em três e meio aberto: o painel de baixo apoiado, o do meio levantado e o
    de cima caindo de volta. Cada painel é uma folha com espessura, ondulação e canto levantado."""
    item = Assembly("Item_MAP")
    m = item.part(PAPER)
    panel_w, panel_l = 0.118, 0.172
    # ângulos relativos entre painéis: sobe 24 graus, depois desce 48 e o terceiro painel volta à mesa
    angles = (0.0, 24.0, -48.0)
    thirds = ((0.0, 0.0, 1 / 3, 1.0), (1 / 3, 0.0, 2 / 3, 1.0), (2 / 3, 0.0, 1.0, 1.0))
    hinge_x, hinge_z, heading = -panel_w * 1.5, 0.0, 0.0
    for index, (angle, uv_rect) in enumerate(zip(angles, thirds)):
        heading += angle
        with m.at(hinge_x, 0.0, hinge_z, ry=-heading):
            paper.sheet(m, panel_w, panel_l, "city_map", "paper_back", thickness=0.0005, nu=14, nv=18,
                        offset=(panel_w / 2, 0.0, 0.0), wave=0.0010, curl=0.006 if index == 2 else 0.003,
                        curl_corners=((1, 1),) if index == 2 else ((1, -1),), uv_rect=uv_rect, seed=index + 1,
                        bend_x=0.0012)
        hinge_x += panel_w * math.cos(math.radians(heading))
        hinge_z += panel_w * math.sin(math.radians(heading))
    return item


# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------
def build_note_letter():
    """Bilhete da Laura: envelope aberto com a aba levantada e a carta dobrada em três saindo dele."""
    item = Assembly("Item_NOTE_1")
    m = item.part(PAPER)
    paper.sheet(m, 0.168, 0.108, "note_envelope", "paper_back", thickness=0.0012, nu=10, nv=8, wave=0.0006,
                bend_x=0.0014, seed=3, yaw_deg=-4)
    with m.at(0.0, 0.0, 0.0, rz=-4):
        paper.triangle_flap(m, 0.168, 0.058, 0.054, 24, "paper_back", "paper_back", z=0.0013)
    paper.sheet(m, 0.112, 0.150, "note_letter", "paper_back", thickness=0.0006, nu=12, nv=18, curl=0.004,
                curl_corners=((1, 1), (-1, 1)), crease=("y", 0.017, 3.0), offset=(0.012, 0.050, 0.0016), yaw_deg=7,
                seed=5, uv_rect=(0, 0, 1, 1))
    return item


def build_note_drawing():
    """Desenho de giz de cera: folha grande com dois cantos enrolados, dobra de gaveta e giz em volta."""
    item = Assembly("Item_NOTE_2")
    m = item.part(PAPER)
    paper.sheet(m, 0.214, 0.292, "note_crayon", "paper_back", thickness=0.0005, nu=18, nv=24, curl=0.016,
                curl_corners=((1, 1), (-1, -1)), crease=("y", 0.02, 1.4), wave=0.0012, seed=11)
    wax = item.part(craft.Finish(bevel=0.0004, bevel_segments=2, smooth_angle=40))
    for index, (x, y, yaw, color) in enumerate(((0.145, -0.060, 25.0, "toy_red"), (0.160, -0.030, 70.0, "toy_red"))):
        length = 0.058 if index == 0 else 0.030
        with wax.at(x, y, 0.0035, rx=-90, rz=yaw):
            wax.cylinder(0, 0, -length / 2, 0.0036, length, color, seg=10, smooth=True, r_top=0.0036)
            wax.cylinder(0, 0, length / 2, 0.0036, 0.007, color, seg=10, smooth=True, r_top=0.0008)
            wax.cylinder(0, 0, -length / 2 + 0.006, 0.0039, length * 0.65, "paper_white", seg=10, smooth=True)
    return item


def build_note_clipping():
    """Recorte de jornal rasgado nas quatro bordas, levemente enrolado, preso por um clipe."""
    item = Assembly("Item_NOTE_3")
    m = item.part(PAPER)
    paper.sheet(m, 0.148, 0.172, "note_newspaper", "paper_back", thickness=0.0004, nu=16, nv=20, tear=0.0055,
                curl=0.010, curl_corners=((-1, 1), (1, -1)), wave=0.0010, seed=17, yaw_deg=-3)
    clip = item.part(FINE_METAL)
    for dy in (0.0, -0.0035, -0.0070):                                    # arame do clipe: três voltas
        clip.torus(0.062, 0.070 + dy, 0.0030, 0.0038, 0.00055, "chrome", seg=14, seg_minor=4, rx=90)
    return item


def build_note_notebook():
    """Folha de caderno espiral, de pé, presa por um percevejo vermelho; borda esquerda picotada."""
    item = Assembly("Item_NOTE_4")
    m = item.part(PAPER)
    with m.at(0.0, 0.0, 0.0, rx=90, rz=180):
        paper.sheet(m, 0.190, 0.250, "note_notebook", "paper_back", thickness=0.0005, nu=14, nv=20, scallop=7,
                    tear=0.0012, tear_edges="b", curl=0.012, curl_corners=((1, -1),), wave=0.0008, seed=23,
                    offset=(0.0, 0.0, 0.0))
    pin = item.part(SOFT_RUBBER)
    with pin.at(0.0, 0.0006, 0.088, rx=-90):          # +Z local aponta para o cômodo, a agulha entra na parede
        pin.cylinder(0, 0, 0.0, 0.0085, 0.0036, "toy_red", seg=18, smooth=True, r_top=0.0075)
        pin.cylinder(0, 0, 0.0036, 0.0035, 0.0050, "toy_red", seg=14, smooth=True, r_top=0.0030)
        pin.cylinder(0, 0, -0.0060, 0.0009, 0.0060, "chrome", seg=8, smooth=True, r_top=0.0003)
    return item


def build_note_postit():
    """Post-it amarelo grudado na geladeira, com a borda de baixo desgrudando; de pé, frente em +Y."""
    item = Assembly("Item_NOTE_5")
    m = item.part(PAPER)
    with m.at(0.0, 0.0, 0.0, rx=90, rz=180):
        paper.sheet(m, 0.085, 0.085, "note_postit", "paper_back", thickness=0.0004, nu=8, nv=10, curl=0.010,
                    curl_corners=((1, -1), (-1, -1)), wave=0.0004, seed=29)
    return item


def build_note_prescription():
    """Receita do Dr. Mills sobre outra folha já amarelada, no bloco com cola na borda de cima."""
    item = Assembly("Item_NOTE_6")
    m = item.part(PAPER)
    paper.sheet(m, 0.104, 0.142, "paper_back", "paper_back", thickness=0.0008, nu=8, nv=10, yaw_deg=9,
                offset=(0.010, -0.007, 0.0), wave=0.0006, seed=31)
    paper.sheet(m, 0.100, 0.136, "note_prescription", "paper_back", thickness=0.0005, nu=12, nv=16, curl=0.006,
                curl_corners=((1, -1),), offset=(0.0, 0.0, 0.0010), yaw_deg=-6, wave=0.0008, seed=33)
    glue = item.part(craft.Finish(bevel=0.0003, bevel_segments=2, smooth_angle=60))
    glue.box(0.006, 0.0675, 0.0, 0.098, 0.0045, 0.0022, "paper_white")
    return item


def build_note_tow_slip():
    """Guia do pátio em duas vias: a branca por baixo, a amarela por cima, levantada, com grampo no canto."""
    item = Assembly("Item_NOTE_7")
    m = item.part(PAPER)
    paper.sheet(m, 0.126, 0.172, "note_tow", "paper_back", thickness=0.0006, nu=10, nv=14, tear=0.0030,
                tear_edges="l", uv_rect=(0, 0.5, 1, 1), offset=(0.0, 0.0, 0.0), wave=0.0006, seed=37)
    with m.at(0.0, 0.0, 0.0011, rx=0):
        paper.sheet(m, 0.126, 0.086, "note_tow", "paper_back", thickness=0.0006, nu=10, nv=8, curl=0.012,
                    curl_corners=((1, 1), (-1, 1)), uv_rect=(0, 0, 1, 0.5), offset=(0.0, 0.043, 0.0),
                    tear=0.0025, tear_edges="l", seed=39)
    staple = item.part(FINE_METAL)
    staple.bar((-0.054, 0.076, 0.0022), (-0.044, 0.076, 0.0022), 0.0009, "chrome")
    staple.bar((-0.054, 0.076, 0.0022), (-0.054, 0.076, 0.0006), 0.0006, "chrome")
    staple.bar((-0.044, 0.076, 0.0022), (-0.044, 0.076, 0.0006), 0.0006, "chrome")
    return item
