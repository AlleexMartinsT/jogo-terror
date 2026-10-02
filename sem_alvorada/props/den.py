"""Escritório de baixo: a escrivaninha do Dan com tampo de couro, luminária de banqueiro, computador, arquivo e o
quadro de cortiça onde ele traça a rota de fuga.

Alturas que o jogo usa: o tampo da escrivaninha fica a 0,76 m (a chave repousa ali). A cortiça fica a 3,4 cm da
parede; o caderno de `Item_NOTE_4` está a 9 cm (ver o relatório: pedido para aproximá-lo da cortiça).
"""
import math

from .. import craft
from . import furniture_forms as forms
from . import materials, tex_den, tex_sala
from .composite import Composite
from .furniture import wall_spot
from .kit import MeshBuilder
from .placement import against_wall, flush_center, floor_z, place

TOP_Z = 0.76
materials.SPECS.update({
    "crt_glass_off": materials.Spec(color=(0.010, 0.013, 0.013), roughness=0.05),
    "pin_red": materials.Spec(color=(0.55, 0.05, 0.04), roughness=0.3),
    "pin_blue": materials.Spec(color=(0.06, 0.12, 0.50), roughness=0.3),
    "pin_yellow": materials.Spec(color=(0.62, 0.50, 0.08), roughness=0.3),
    "yarn_red": materials.Spec(color=(0.45, 0.03, 0.03), roughness=0.9),
    "label_paper": materials.Spec(color=(0.70, 0.66, 0.52), roughness=0.9),
})
tex_sala.SURFACES["leather_green"] = tex_sala.Surface(
    "sala_leather", 0.5, tint=(0.05, 0.12, 0.07), roughness=0.65, rough_swing=0.2, specular=0.3, bump=0.45,
    bump_distance=0.0015, coat=0.04, box=True)
materials.register_builder(
    "leather_green", lambda: tex_sala.build_surface("leather_green", tex_sala.SURFACES["leather_green"]))


# ---------------------------------------------------------------------------
# Escrivaninha
# ---------------------------------------------------------------------------
def _pedestal(wood, trim, cx, depth, drawers):
    """Gaveteiro de 0,44 m: laterais, fundo e frentes almofadadas com puxador de alça e espelho de fechadura."""
    width, height, base = 0.44, 0.68, 0.04
    wood.box(cx, 0.0, base, width, depth - 0.04, height, "walnut_v")
    front = depth / 2 - 0.02
    cursor = base + 0.012
    usable = height - 0.024
    total = sum(drawers)
    for share in drawers:
        h = usable * share / total - 0.008
        wood.box(cx, front + 0.004, cursor, width - 0.022, 0.022, h, "walnut")
        with wood.at(cx, front + 0.016, cursor + h / 2, rx=-90):
            wood.frustum(0, 0, 0, width - 0.1, h - 0.07, width - 0.12, h - 0.085, 0.006, "walnut_v")
        forms.bail_pull(trim, cx, front + 0.021, cursor + h / 2 + 0.008, 0.09, "brass_aged")
        forms.escutcheon(trim, cx, front + 0.0155, cursor + h - 0.025, "brass_aged")
        cursor += h + 0.008


def make_desk(ctx, room, x, y, yaw, *, width, depth, anchor=None, z=None, name=None):
    """Escrivaninha de executivo com dois gaveteiros, gaveta central e tampo de nogueira com couro verde embutido.

    O tampo termina a 0,76 m exatos: é a superfície onde a chave do carro repousa.
    """
    cy = flush_center(room, x, y, yaw, depth)
    asm = Composite(name or "desk", wood=forms.WOOD, round=forms.SMOOTH, trim=forms.SMOOTH, leather=craft.RAW)
    wood, trim = asm.wood, asm.trim
    with asm.at(0, cy, 0):
        forms.slab(asm.round, 0, 0.01, TOP_Z - 0.04, width + 0.04, depth + 0.02, forms.OGEE_EDGE, "walnut", radius=0.05)
        px = width / 2 - 0.22 - 0.01
        _pedestal(wood, trim, px, depth, (1, 1.2, 1.6))
        _pedestal(wood, trim, -px, depth, (1, 1, 1.4))
        wood.box(0, -depth / 2 + 0.03, 0.04, width - 0.9, 0.02, 0.68, "walnut_v")                    # painel traseiro
        wood.box(0, depth / 2 - 0.1, TOP_Z - 0.04 - 0.085, width - 0.9, 0.025, 0.085, "walnut")        # gaveta central
        forms.bail_pull(trim, 0, depth / 2 - 0.083, TOP_Z - 0.04 - 0.045, 0.1, "brass_aged")
        forms.escutcheon(trim, 0.0, depth / 2 - 0.0865, TOP_Z - 0.04 - 0.02, "brass_aged")
        for sx in (-1, 1):
            wood.box(sx * px, 0, 0.0, 0.38, depth - 0.08, 0.04, "tv_black")                           # rodapé recuado
        inset_w, inset_d = width - 0.17, depth - 0.15
        asm.leather.panel(0, 0.0, TOP_Z + 0.0007, inset_w, inset_d, "leather_green", "top")
        for edge_y in (-1, 1):
            trim.box(0, edge_y * inset_d / 2, TOP_Z + 0.0004, inset_w, 0.0025, 0.0006, "gilt")
        for edge_x in (-1, 1):
            trim.box(edge_x * inset_w / 2, 0, TOP_Z + 0.0004, 0.0025, inset_d, 0.0006, "gilt")
    return place(ctx, asm, room, "desk", x, y, yaw, z, name=name, anchor=anchor)


# ---------------------------------------------------------------------------
# Luminária de banqueiro
# ---------------------------------------------------------------------------
def make_bankers_lamp(ctx, room, x, y, z, yaw=0.0):
    """Luminária de banqueiro: base e haste de latão, cúpula de vidro verde em meio cilindro e corrente de puxar."""
    asm = Composite("bankers_lamp", metal=forms.SMOOTH, glass=craft.RAW)
    metal, glass = asm.metal, asm.glass
    metal.lathe([(0.0, 0.0), (0.095, 0.0), (0.1, 0.006), (0.09, 0.016), (0.05, 0.026), (0.03, 0.04), (0.0, 0.04)], 0, 0, 0,
                "brass_aged", seg=forms.seg(20), smooth=True)
    metal.lathe([(0.016, 0.04), (0.014, 0.06), (0.022, 0.07), (0.012, 0.09), (0.011, 0.27), (0.016, 0.285), (0.011, 0.3)],
                0, 0, 0, "brass_aged", seg=forms.seg(14), smooth=True)
    metal.box(0, 0.0, 0.285, 0.05, 0.04, 0.02, "brass_aged")
    radius, length, center_z = 0.075, 0.34, 0.345
    steps = 14

    def arc(t):
        """Ponto (y, z) do meio cilindro da cúpula, de um lado ao outro por cima."""
        return math.cos(math.pi * t) * radius, center_z + math.sin(math.pi * t) * radius * 0.85

    glass.surface(lambda u, v: ((v - 0.5) * length, *arc(u)), steps, 6, "glass_green", smooth=True)
    for side in (-1, 1):
        glass.poly([(side * length / 2, *arc(i / steps)) for i in range(steps + 1)], "glass_green")
    metal.tube((0, 0, 0.295), (0, 0.0, center_z - 0.03), 0.004, "brass_aged", seg=6)
    metal.sphere(0.12, 0.0, 0.31, 0.007, "brass_aged", seg=8, rings=5)
    metal.tube((0.12, 0.0, 0.31), (0.12, 0.0, 0.26), 0.0012, "brass_aged", seg=4)
    return place(ctx, asm, room, "bankers_lamp", x, y, yaw, z, mode="decor")


# ---------------------------------------------------------------------------
# Computador de mesa
# ---------------------------------------------------------------------------
def _monitor(shell, glass, trim):
    """Monitor de tubo de 15 polegadas: carcaça afunilada, tela abaulada apagada e base giratória."""
    stations = [(0.19, 0.40, 0.36, 0.035, 0.0), (0.17, 0.41, 0.37, 0.04, 0.0), (0.04, 0.41, 0.37, 0.05, 0.0),
                (-0.08, 0.34, 0.31, 0.06, 0.0), (-0.17, 0.22, 0.2, 0.06, -0.01), (-0.22, 0.15, 0.13, 0.05, -0.02)]
    rings = []
    for y, w, h, r, shift in stations:
        rings.append([(px, y, 0.1 + h / 2 + shift + pz) for px, pz in forms.rounded_rect(w, h, r, 4)])
    shell.loft(rings, "plastic_beige", True, True, False)

    def screen(u, v):
        a, b = 2 * u - 1, 2 * v - 1
        shrink = 1 - 0.14 * a * a * b * b
        return (0.15 * a * shrink * 1.2, 0.195 + 0.014 * (1 - a * a) * (1 - b * b), 0.28 + 0.13 * b * shrink * 1.1)

    glass.surface(screen, 12, 10, "crt_glass_off", flip=True, smooth=True)
    trim.box(0.12, 0.185, 0.115, 0.018, 0.006, 0.006, "led_red")
    trim.box(-0.05, 0.19, 0.105, 0.12, 0.003, 0.012, "plastic_gray")
    trim.lathe([(0.12, 0.0), (0.125, 0.012), (0.09, 0.02), (0.07, 0.03), (0.0, 0.03)], 0, 0.02, 0.0, "plastic_beige",
               seg=forms.seg(20), smooth=True)
    trim.lathe([(0.07, 0.03), (0.075, 0.06), (0.06, 0.095), (0.0, 0.095)], 0, 0.02, 0.0, "plastic_beige", seg=forms.seg(16),
               smooth=True)


def _keyboard(asm, cx, cy):
    """Teclado: base inclinada, quatro fileiras de teclas e a barra de espaço."""
    with asm.at(cx, cy, 0.0, rx=-5):
        asm.body.soft_box(0, 0, 0.0, 0.46, 0.17, 0.024, "plastic_beige", radius=0.01, edge=0.005)
        for row in range(4):
            count = 13 if row else 12
            for col in range(count):
                asm.trim.box((col - (count - 1) / 2) * 0.0295, 0.06 - row * 0.03, 0.025, 0.0245, 0.0245, 0.0095,
                             "plastic_gray")
        asm.trim.box(0, -0.058, 0.025, 0.2, 0.0245, 0.0095, "plastic_gray")


def make_crt_computer(ctx, room, x, y, z, yaw):
    """Micro dos anos 90: monitor de tubo de 15", teclado bege e mouse com fio, tela apagada."""
    asm = Composite("crt_computer", shell=forms.SMOOTH, glass=craft.RAW, trim=forms.SMOOTH, body=forms.SMOOTH)
    with asm.at(0, 0.0, 0.0):
        _monitor(asm.shell, asm.glass, asm.trim)
    _keyboard(asm, 0.0, 0.31)
    asm.body.soft_box(0.34, 0.31, 0.0, 0.064, 0.105, 0.03, "plastic_beige", radius=0.026, edge=0.012)
    asm.trim.box(0.34, 0.345, 0.031, 0.05, 0.002, 0.0012, "plastic_gray")
    cord = craft.tube_along([(0.34, 0.255, 0.012), (0.33, 0.12, 0.004), (0.2, 0.05, 0.004), (0.12, -0.1, 0.006)], 0.0018,
                            segments=6, resolution=3, name="cabo_mouse")
    cord.materials.append(materials.get("tv_grille"))
    asm.add_mesh(cord)
    asm.body.box(0.34, 0.31, -0.002, 0.2, 0.2, 0.002, "leather_black")
    return place(ctx, asm, room, "computer", x, y, yaw, z, mode="decor")


# ---------------------------------------------------------------------------
# Quadro de cortiça
# ---------------------------------------------------------------------------
BOARD_WIDTH, BOARD_HEIGHT = 0.75, 0.95
BOARD_CORK_DEPTH = 0.034                 # distância da cortiça à parede


def make_cork_board(ctx, room, wall, along, z):
    """Quadro de cortiça de moldura funda com recortes, alfinetes de cabeça colorida e fio vermelho esticado entre eles.

    `z` é a altura do centro. O centro do quadro fica vazio para o caderno do Dan (`Item_NOTE_4`).
    """
    x, y, yaw = wall_spot(room, wall, along)
    asm = Composite("cork_board", frame=forms.SMOOTH, trim=forms.SMOOTH, cork=craft.RAW)
    profile = [(0.0, 0.0), (0.0, BOARD_CORK_DEPTH - 0.004), (0.012, BOARD_CORK_DEPTH + 0.004), (0.05, BOARD_CORK_DEPTH + 0.002),
               (0.054, 0.012), (0.054, 0.0)]
    forms.mitred_frame(asm.frame, 0, 0, 0, BOARD_WIDTH, BOARD_HEIGHT, profile, "oak")
    asm.cork.panel(0, BOARD_CORK_DEPTH - 0.003, 0, BOARD_WIDTH, BOARD_HEIGHT, "cork_board", "front")
    pin_colors = ("pin_red", "pin_blue", "pin_yellow", "pin_red")
    points = {}
    for index, (key, (u, v)) in enumerate(tex_den.CORK_PINS.items()):
        px, pz = (0.5 - u) * BOARD_WIDTH, (0.5 - v) * BOARD_HEIGHT
        points[key] = (px, BOARD_CORK_DEPTH + 0.004, pz)
        asm.trim.sphere(px, BOARD_CORK_DEPTH + 0.0085, pz, 0.0062, pin_colors[index % 4], seg=8, rings=5)
    for first, second in tex_den.CORK_YARN:
        a, b = points[first], points[second]
        mid = ((a[0] + b[0]) / 2, a[1] + 0.004, (a[2] + b[2]) / 2 - 0.0016)
        thread = craft.tube_along([(a[0], a[1] + 0.003, a[2]), mid, (b[0], b[1] + 0.003, b[2])], 0.0008, segments=4,
                                  resolution=3, name="fio")
        thread.materials.append(materials.get("yarn_red"))
        asm.add_mesh(thread)
    return place(ctx, asm, room, "picture", x, y, yaw, floor_z(room) + z, mode="wall", name="cork_board_den")


# ---------------------------------------------------------------------------
# Arquivo de aço
# ---------------------------------------------------------------------------
def make_filing_cabinet(ctx, room, wall, along, *, height=0.78, z=None):
    """Arquivo de aço de duas gavetas: corpo dobrado, frentes com cava de puxar, porta-etiquetas e fechadura."""
    width, depth = 0.46, 0.6
    x, y, yaw = against_wall(room, wall, along, depth)
    asm = Composite("filing_cabinet", steel=forms.SMOOTH, small=forms.SMOOTH)
    steel, small = asm.steel, asm.small
    steel.soft_box(0, 0, 0.03, width, depth, height - 0.03, "steel_filing", radius=0.012, edge=0.008)
    steel.box(0, 0.0, 0.0, width - 0.04, depth - 0.04, 0.03, "tv_black")
    drawer_h = (height - 0.1) / 2
    for row in range(2):
        z0 = 0.05 + row * (drawer_h + 0.012)
        steel.box(0, depth / 2 + 0.003, z0, width - 0.03, 0.016, drawer_h, "steel_filing")
        small.box(0, depth / 2 + 0.0125, z0 + drawer_h - 0.05, 0.16, 0.006, 0.026, "tv_black")        # cava da puxada
        small.box(0, depth / 2 + 0.0135, z0 + drawer_h - 0.088, 0.1, 0.002, 0.045, "label_paper")
        small.box(0, depth / 2 + 0.0155, z0 + drawer_h - 0.088, 0.108, 0.001, 0.052, "chrome")
    small.cylinder(0.17, depth / 2 + 0.012, height - 0.06, 0.008, 0.002, "chrome", seg=forms.seg(10))
    return place(ctx, asm, room, "filing_cabinet", x, y, yaw, z)


# ---------------------------------------------------------------------------
# Papéis
# ---------------------------------------------------------------------------
def make_paper_sheets(ctx, room, x, y, z, count=6, spread=0.2):
    """Folhas impressas (seguro, boletim, laudo) empilhadas fora de prumo, em cima de `z`."""
    m = MeshBuilder("sheets")
    m.finish = craft.RAW
    rng = ctx.rng
    for index in range(count):
        with m.at(rng.uniform(-spread, spread), rng.uniform(-spread, spread) * 0.7, 0.0015 + index * 0.0018,
                  rz=rng.uniform(0, 180)):
            sheet = "sheet_" + "abc"[index % 3]
            m.box(0, 0, 0, 0.21, 0.297, 0.0012, "paper_white", skip=("top",))
            m.panel(0, 0, 0.0013, 0.21, 0.297, sheet, "top")
    return place(ctx, m, room, "papers", x, y, 0.0, z, mode="decor")
