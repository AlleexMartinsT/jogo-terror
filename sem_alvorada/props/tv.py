"""TV de tubo de 20 polegadas sobre um console de nogueira, com videocassete e a gaveta aberta.

A tela é o material `tv_screen`, que mantém o nó `StaticMapping` que o engine desloca para animar o
chiado. O console mede 1,20 x 0,50 x 0,55 m e a TV senta no tampo (z = 0,55). A gaveta da esquerda está
puxada 28 cm e o fundo dela fica a 0,30 m: é onde repousa `Item_BATTERY_3`, então a posição e a altura
dessa gaveta não mudam.
"""
import math

from .. import compat, craft
from . import furniture_forms as forms
from . import materials
from .composite import Composite
from .kit import rounded_rect
from .placement import flush_center, place

CONSOLE_WIDTH, CONSOLE_DEPTH, CONSOLE_HEIGHT = 1.2, 0.5, 0.55
DRAWER_PULL = 0.28                       # quanto a gaveta da esquerda está puxada
DRAWER_FLOOR_TOP = 0.30                  # a pilha repousa aqui (items.py)
SCREEN_CENTER_X = -0.07

materials.SPECS.update({
    "tv_shell": materials.Spec(color=(0.085, 0.07, 0.058), roughness=0.5),
    "tv_black": materials.Spec(color=(0.012, 0.012, 0.013), roughness=0.55),
    "tv_grille": materials.Spec(color=(0.02, 0.018, 0.016), roughness=0.9),
    "vcr_body": materials.Spec(color=(0.03, 0.03, 0.032), roughness=0.4),
    "vcr_face": materials.Spec(color=(0.10, 0.10, 0.105), roughness=0.4),
    "vhs_label": materials.Spec(color=(0.62, 0.58, 0.46), roughness=0.8),
})


def build_screen_material():
    """Tela de tubo: chiado emissivo com cantos escurecidos e brilho de vidro. Guarda o `StaticMapping`."""
    from .textures import image
    mat = compat.new_material("tv_screen")
    tree, links = mat.node_tree, mat.node_tree.links
    bsdf = compat.bsdf_of(mat)
    coords = tree.nodes.new("ShaderNodeTexCoord")
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.name = "StaticMapping"          # o engine desloca "Location" a cada quadro para animar o chiado
    links.new(coords.outputs["UV"], mapping.inputs["Vector"])
    static = tree.nodes.new("ShaderNodeTexImage")
    static.image = image("tv_static")
    static.interpolation, static.extension = "Closest", "REPEAT"
    links.new(mapping.outputs["Vector"], static.inputs["Vector"])
    centered = tree.nodes.new("ShaderNodeVectorMath")
    centered.operation = "DISTANCE"
    centered.inputs[1].default_value = (0.5, 0.5, 0.0)
    links.new(coords.outputs["UV"], centered.inputs[0])
    falloff = tree.nodes.new("ShaderNodeMapRange")
    falloff.inputs["From Min"].default_value, falloff.inputs["From Max"].default_value = 0.30, 0.72
    falloff.inputs["To Min"].default_value, falloff.inputs["To Max"].default_value = 1.0, 0.25
    links.new(centered.outputs["Value"], falloff.inputs["Value"])
    glow = tree.nodes.new("ShaderNodeMix")
    glow.data_type, glow.blend_type = "RGBA", "MULTIPLY"
    glow.inputs[0].default_value = 1.0
    links.new(static.outputs["Color"], glow.inputs[6])
    links.new(falloff.outputs["Result"], glow.inputs[7])
    compat.set_bsdf(bsdf, base_color=(0.0, 0.0, 0.0), roughness=0.06, specular=0.6, emission_strength=1.3)
    links.new(glow.outputs[2], bsdf.inputs["Emission Color"])
    mat.diffuse_color = (0.5, 0.55, 0.6, 1.0)
    return mat


materials.register_builder("tv_screen", build_screen_material)


# ---------------------------------------------------------------------------
# Console
# ---------------------------------------------------------------------------
def _console(wood, round_part, trim, depth):
    """Carcaça do console: soquete, laterais, divisórias, prateleira do vídeo, portas almofadadas e gavetas."""
    half_w = CONSOLE_WIDTH / 2
    plinth = 0.06
    wood.box(0, -0.015, 0, CONSOLE_WIDTH - 0.08, depth - 0.05, plinth, "walnut")
    for side in (-1, 1):
        wood.box(side * (half_w - 0.01), 0, plinth, 0.02, depth, CONSOLE_HEIGHT - plinth - 0.04, "walnut_v")
    for divider_x in (-0.2, 0.2):
        wood.box(divider_x, 0, plinth, 0.02, depth - 0.02, CONSOLE_HEIGHT - plinth - 0.04, "walnut_v")
    wood.box(0, 0, plinth, CONSOLE_WIDTH - 0.04, depth - 0.02, 0.016, "walnut")
    wood.box(0.0, 0, 0.255, 0.38, depth - 0.04, 0.016, "walnut")                    # prateleira do vídeo
    wood.box(0, -depth / 2 + 0.01, plinth, CONSOLE_WIDTH - 0.04, 0.008, CONSOLE_HEIGHT - plinth - 0.04, "tv_black")
    forms.slab(round_part, 0, 0.01, CONSOLE_HEIGHT - 0.04, CONSOLE_WIDTH + 0.04, depth + 0.02, forms.BULLNOSE_EDGE, "walnut",
               radius=0.025)
    front = depth / 2
    # porta almofadada da direita
    _paneled_door(wood, 0.40, front, 0.085, 0.37, 0.405, "walnut")
    forms.round_knob(trim, 0.255, front + 0.026, 0.30, 0.016, "brass_aged")
    # porta baixa da esquerda (sob a gaveta puxada)
    _paneled_door(wood, -0.40, front, 0.085, 0.37, 0.185, "walnut")
    forms.round_knob(trim, -0.255, front + 0.026, 0.19, 0.014, "brass_aged")


def _paneled_door(wood, cx, front, z0, width, height, mat, stile=0.05):
    """Folha de porta com moldura (montantes e travessas) e almofada em relevo."""
    thick = 0.02
    wood.box(cx, front + thick / 2 - 0.004, z0, width, thick, height, mat)
    wood.box(cx, front + thick - 0.004 + 0.002, z0 + stile * 0.7, width - 2 * stile, 0.004, height - 2 * stile * 0.7, "walnut_v")
    with wood.at(cx, front + thick - 0.004 + 0.004, z0 + height / 2, rx=-90):
        wood.frustum(0, 0, 0, width - 2.6 * stile, height - 1.4 * stile, width - 3.4 * stile, height - 2.2 * stile,
                     0.006, "walnut_v")


def _drawer_pulled(wood, trim, depth, front):
    """Gaveta da esquerda, puxada: frente almofadada, caixa de cauda-de-andorinha simples e fundo a 0,30 m."""
    cx = -0.4
    drawer_front_y = front + DRAWER_PULL
    box_len = 0.40
    box_w = 0.36
    wall = 0.014
    floor_z = DRAWER_FLOOR_TOP - 0.012
    wood.box(cx, drawer_front_y - 0.01, 0.285, 0.395, 0.022, 0.205, "walnut")                      # frente
    wood.box(cx, drawer_front_y + 0.011, 0.31, 0.30, 0.004, 0.155, "walnut_v")
    forms.round_knob(trim, cx, drawer_front_y + 0.013, 0.39, 0.016, "brass_aged")
    # caixa: fundo, laterais, traseira
    wood.box(cx, drawer_front_y - 0.02 - box_len / 2, floor_z, box_w, box_len, 0.012, "oak")
    for side in (-1, 1):
        wood.box(cx + side * (box_w / 2 - wall / 2), drawer_front_y - 0.02 - box_len / 2, floor_z, wall, box_len, 0.12, "oak_v")
    wood.box(cx, drawer_front_y - 0.02 - box_len + wall / 2, floor_z, box_w, wall, 0.12, "oak_v")
    wood.box(cx, 0, 0.268, 0.38, CONSOLE_DEPTH - 0.02, 0.016, "walnut")          # travessa sob a gaveta


# ---------------------------------------------------------------------------
# Videocassete
# ---------------------------------------------------------------------------
def _vcr(body, trim, cx, cy, z0):
    """Videocassete 90s: caixa preta, frente com portinhola, display verde, botões e LED."""
    body.soft_box(cx, cy, z0, 0.38, 0.26, 0.085, "vcr_body", radius=0.012, edge=0.006)
    front = cy + 0.13
    trim.box(cx, front + 0.0015, z0 + 0.014, 0.36, 0.003, 0.057, "vcr_face")
    trim.box(cx - 0.04, front + 0.004, z0 + 0.044, 0.21, 0.004, 0.022, "tv_black")             # portinhola da fita
    trim.panel(cx + 0.11, front + 0.0042, z0 + 0.052, 0.07, 0.02, "digits_dash", "front")      # display
    for i in range(5):
        trim.box(cx - 0.12 + i * 0.026, front + 0.004, z0 + 0.018, 0.016, 0.004, 0.008, "plastic_gray")
    trim.box(cx + 0.14, front + 0.004, z0 + 0.026, 0.01, 0.004, 0.006, "led_red")
    for fx in (-0.15, 0.15):
        trim.box(cx + fx, cy, z0 - 0.006, 0.03, 0.03, 0.006, "rubber")


def _vhs_tape(body, trim, cx, cy, z0, yaw=0.0):
    """Fita VHS deitada: carcaça preta, rótulo e janela dos rolos."""
    with body.at(cx, cy, z0, rz=yaw):
        body.box(0, 0, 0, 0.19, 0.103, 0.025, "tv_black")
        trim.box(0, 0.0, 0.0252, 0.14, 0.07, 0.0015, "vhs_label")
        trim.box(0, -0.05, 0.0252, 0.1, 0.014, 0.001, "tv_grille")


# ---------------------------------------------------------------------------
# TV de tubo
# ---------------------------------------------------------------------------
def _screen_contour(count, half_w, half_h, rounding=0.16):
    """Pontos (x, z) do contorno de uma tela de tubo: retângulo com cantos puxados para dentro."""
    points = []
    for i in range(count):
        t = i / count * 4
        side, f = int(t), t - int(t)
        a, b = [(1, -1 + 2 * f), (1 - 2 * f, 1), (-1, 1 - 2 * f), (-1 + 2 * f, -1)][side]
        shrink = 1 - rounding * a * a * b * b
        points.append((half_w * a * shrink, half_h * b * shrink))
    return points


def _tv_shell(shell, z0, front_y):
    """Carcaça: frente curva, flancos cheios e traseira afunilada até o pescoço do tubo."""
    stations = [  # (y, largura, altura, raio dos cantos, deslocamento vertical do centro)
        (front_y, 0.560, 0.440, 0.040, 0.0), (front_y - 0.018, 0.580, 0.458, 0.050, 0.0),
        (front_y - 0.110, 0.580, 0.458, 0.062, 0.0), (front_y - 0.205, 0.545, 0.430, 0.075, 0.004),
        (front_y - 0.290, 0.440, 0.350, 0.090, 0.012), (front_y - 0.360, 0.300, 0.236, 0.085, 0.026),
        (front_y - 0.395, 0.200, 0.160, 0.070, 0.036)]
    rings = []
    for y, width, height, radius, shift in stations:
        outline = rounded_rect(width, height, radius, 4)
        rings.append([(x, y, z0 + 0.003 + height / 2 + shift + v) for x, v in outline])
    shell.loft(rings, "tv_shell", True, True, False)


def _tv_screen_and_bezel(shell, glass, trim, z0, front_y):
    """Vidro abaulado dentro de uma moldura de plástico em declive."""
    cx, cz = SCREEN_CENTER_X, z0 + 0.003 + 0.225
    half_w, half_h = 0.205, 0.165
    count = 40
    inner = _screen_contour(count, half_w, half_h)
    outer = _screen_contour(count, half_w + 0.028, half_h + 0.028)
    ring_specs = [(inner, front_y + 0.002), (_scaled(inner, 1.0), front_y + 0.012),
                  (outer, front_y + 0.014), (_scaled(outer, 1.02), front_y + 0.0)]
    rings = [[(cx + x, y, cz + v) for x, v in contour] for contour, y in ring_specs]
    shell.loft(rings, "tv_black", False, False, False, orient=False)

    def bulged(u, v):
        a, b = 2 * u - 1, 2 * v - 1
        shrink = 1 - 0.16 * a * a * b * b
        dome = (1 - a * a) * (1 - b * b)
        return (cx + half_w * a * shrink, front_y + 0.004 + 0.018 * dome, cz + half_h * b * shrink)

    glass.surface(bulged, 14, 12, "tv_screen", uv_size=(1.0, 1.0), flip=True, smooth=True)


def _scaled(contour, factor):
    return [(x * factor, v * factor) for x, v in contour]


def _tv_controls(trim, z0, front_y):
    """Faixa lateral com grade do alto-falante, dois botões giratórios e fileira de teclas."""
    panel_x, panel_w = 0.215, 0.092
    base = z0 + 0.003
    trim.box(panel_x, front_y + 0.003, base + 0.045, panel_w, 0.006, 0.35, "walnut_v")
    for i in range(8):
        trim.box(panel_x, front_y + 0.0065, base + 0.255 + i * 0.0165, panel_w - 0.03, 0.002, 0.007, "tv_grille")
    for index, knob_z in enumerate((0.205, 0.140)):
        with trim.at(panel_x, front_y + 0.006, base + knob_z, rx=-90):
            trim.lathe([(0.0225, 0.0), (0.0225, 0.006), (0.017, 0.012), (0.0185, 0.024), (0.0, 0.025)], 0, 0, 0,
                       "tv_black", seg=forms.seg(16), smooth=True)
            trim.box(0.0, 0.012, 0.0245, 0.003, 0.016, 0.002, "plastic_beige")
    for i in range(4):
        trim.box(panel_x - 0.027 + i * 0.018, front_y + 0.009, base + 0.075, 0.012, 0.006, 0.026, "plastic_gray")
    trim.box(panel_x + 0.025, front_y + 0.0075, base + 0.05, 0.016, 0.004, 0.008, "led_red")
    trim.box(SCREEN_CENTER_X, front_y + 0.007, base + 0.026, 0.07, 0.003, 0.012, "chrome")


def _tv_back(shell, trim, z0, front_y):
    """Fendas de ventilação no topo e pés de borracha."""
    for i in range(7):
        shell.box(SCREEN_CENTER_X, front_y - 0.03 - i * 0.0105, z0 + 0.003 + 0.4585, 0.28, 0.0045, 0.002, "tv_black")
    for fx in (-0.22, 0.22):
        for fy in (front_y - 0.04, front_y - 0.3):
            trim.box(fx, fy, z0, 0.04, 0.04, 0.003, "rubber")


def _rabbit_ears(trim, shell, z0, front_y):
    """Antena de coelho: base abaulada e duas hastes telescópicas em V, de pontas esféricas."""
    top = z0 + 0.003 + 0.4605
    cx, cy = -0.05, front_y - 0.10
    with trim.at(cx, cy, top):
        trim.lathe([(0.05, 0.0), (0.05, 0.008), (0.04, 0.02), (0.02, 0.028), (0.0, 0.03)], 0, 0, 0, "plastic_gray",
                   seg=forms.seg(16), smooth=True)
    for side in (-1, 1):
        start = (cx + side * 0.012, cy, top + 0.028)
        direction = (side * math.sin(math.radians(36)), -0.18, math.cos(math.radians(36)))
        length_unit = math.sqrt(sum(c * c for c in direction))
        point = start
        for radius, length in ((0.0036, 0.15), (0.0029, 0.14), (0.0022, 0.13)):
            end = tuple(point[i] + direction[i] / length_unit * length for i in range(3))
            trim.tube(point, end, radius, "chrome", seg=8, smooth=True)
            point = end
        trim.sphere(*point, 0.007, "chrome", seg=8, rings=5)


def _cable(asm, points, radius, material):
    """Cabo de borracha seguindo uma curva suave (já nas coordenadas locais do móvel)."""
    mesh = craft.tube_along(points, radius, segments=8, name="cabo")
    mesh.materials.append(materials.get(material))
    asm.add_mesh(mesh)


def _antenna_cable(asm, z0, front_y):
    """Cabo coaxial da antena: desce da base, contorna a traseira e vai até o chão atrás do console."""
    base = (-0.05, front_y - 0.10, z0 + 0.003 + 0.4605)
    _cable(asm, [base, (base[0] - 0.02, front_y - 0.2, base[2] + 0.03), (-0.2, front_y - 0.38, z0 + 0.34),
                 (-0.26, front_y - 0.42, z0 + 0.0), (-0.3, front_y - 0.4, 0.02), (-0.5, front_y - 0.33, 0.0)], 0.0035, "tv_black")


def _crt_television(asm, z0, front_y):
    shell = asm.shell
    _tv_shell(shell, z0, front_y)
    _tv_screen_and_bezel(shell, asm.glass, asm.trim, z0, front_y)
    _tv_controls(asm.trim, z0, front_y)
    _tv_back(shell, asm.trim, z0, front_y)
    _rabbit_ears(asm.trim, shell, z0, front_y)
    _antenna_cable(asm, z0, front_y)


def make_tv_console(ctx, room, x, y, yaw, *, anchor=None, z=None):
    """Console de nogueira com a TV de tubo em cima e o videocassete embaixo; a gaveta da esquerda está puxada."""
    depth = CONSOLE_DEPTH
    cy = flush_center(room, x, y, yaw, depth)
    asm = Composite("tv_living", wood=forms.WOOD, round=forms.SMOOTH, shell=forms.SMOOTH, glass=craft.RAW,
                    trim=forms.SMOOTH, body=forms.SMOOTH)
    with asm.at(0, cy, 0):
        _console(asm.wood, asm.round, asm.trim, depth)
        _drawer_pulled(asm.wood, asm.trim, depth, depth / 2)
        _vcr(asm.body, asm.trim, 0.0, 0.0, 0.271)
        _vhs_tape(asm.body, asm.trim, 0.0, 0.0, 0.076, yaw=0.15)
        _vhs_tape(asm.body, asm.trim, 0.02, 0.01, 0.101, yaw=-0.2)
        _crt_television(asm, CONSOLE_HEIGHT, 0.185)
        _cable(asm, [(0.0, cy - 0.20, 0.58), (0.0, cy - 0.235, 0.50), (0.04, cy - 0.235, 0.30), (0.1, cy - 0.23, 0.02),
                     (0.3, cy - 0.2, 0.0)], 0.004, "rubber")
    # o proxy cobre o console e a TV, mas não a gaveta puxada (onde repousa a pilha)
    body = (-0.62, cy - depth / 2, 0.0, 0.62, cy + depth / 2, CONSOLE_HEIGHT)
    television = (-0.31, cy - 0.24, CONSOLE_HEIGHT, 0.31, cy + 0.21, 1.03)
    return place(ctx, asm, room, "tv_console", x, y, yaw, z, name="tv_living", anchor=anchor,
                 collision=[body, television])
