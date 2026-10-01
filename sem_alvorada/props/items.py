"""Itens coletáveis e as sete notas: um modelo distinto para cada um, legível sob a lanterna.

Cada item nasce com a origem no centro visual e é apoiado na superfície informada (`rest_z`) pelo
ponto mais baixo da malha. As notas presas na parede (caderno na cortiça, post-it no frigobar)
são construídas de pé, com a frente em +Y, e giradas para o cômodo.
"""
import math

import bpy

from .. import conventions as C
from .. import layout, story
from . import kitchen, parts
from .flashlight import build_item_mesh
from .kit import MeshBuilder

FLAT_NOTE_THICKNESS = 0.003
REST_CLEARANCE = 0.012      # folga sob o item: o raio da interação não pode nascer dentro de uma malha


# ---------------------------------------------------------------------------
# Modelos dos itens principais
# ---------------------------------------------------------------------------
def build_key():
    """Chave do carro de cabeça de borracha, argola e o coelhinho de pelúcia da Emma no chaveiro."""
    m = MeshBuilder("Item_KEY")
    k = 1.3                                              # um pouco maior que o real, para ser mirada
    m.soft_box(0, 0.045 * k, 0, 0.032 * k, 0.05 * k, 0.011 * k, "black", radius=0.008, edge=0.003)
    m.box(0, 0.05 * k, 0.011 * k, 0.012 * k, 0.014 * k, 0.002 * k, "chrome")
    m.box(0, 0.0, 0.0, 0.012 * k, 0.05 * k, 0.0035 * k, "key_metal")
    for i in range(4):
        m.box(0.0075 * k, -0.004 * k - i * 0.0085 * k, 0.0, 0.006 * k, 0.004 * k, 0.0035 * k, "key_metal")
    m.torus(0, 0.078 * k, 0.004, 0.016 * k, 0.0021 * k, "key_metal", seg=10, seg_minor=4)
    for i in range(3):
        m.torus(0.01 * k + i * 0.012 * k, 0.104 * k + i * 0.008 * k, 0.004, 0.005 * k, 0.0012 * k, "key_metal",
                seg=6, seg_minor=3)
    with m.at(0.052 * k, 0.128 * k, 0.0, rz=30):
        parts.rabbit(m, 0, 0, 0, 0.42 * k)
    return m


def build_map():
    """Mapa dobrado em sanfona, meio aberto: três painéis formando um zigue-zague com o mapa da cidade."""
    m = MeshBuilder("Item_MAP")
    panel_w, panel_h, rise = 0.115, 0.17, 0.03
    xs = [(-1.5 + i) * panel_w * 0.93 for i in range(4)]
    zs = [0.0, rise, 0.0, rise]
    for i in range(3):
        u0, u1 = i / 3, (i + 1) / 3
        m.quad((xs[i], -panel_h / 2, zs[i]), (xs[i + 1], -panel_h / 2, zs[i + 1]), (xs[i + 1], panel_h / 2, zs[i + 1]),
               (xs[i], panel_h / 2, zs[i]), "city_map", uv=[(u0, 0), (u1, 0), (u1, 1), (u0, 1)])
    m.box(xs[0] - 0.004, 0, 0.0, 0.006, panel_h, 0.006, "paper_white")
    return m


def build_battery_pair():
    """Duas pilhas D presas por uma fita prateada; cobre e preto, com o polo positivo em relevo."""
    m = MeshBuilder("Item_BATTERY")
    radius, length = 0.0215, 0.078
    for side in (-1, 1):
        with m.at(side * (radius + 0.001), -length / 2, radius, rx=-90):
            m.cylinder(0, 0, 0, radius, length * 0.4, "battery_black", seg=10)
            m.cylinder(0, 0, length * 0.4, radius, length * 0.6, "battery_copper", seg=10)
            m.cylinder(0, 0, length, radius * 0.35, 0.005, "chrome", seg=6)
    m.box(0, 0, -0.002, 4 * radius + 0.006, 0.012, 2 * radius + 0.004, "tape_silver")
    return m


# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------
def _sheet(m, width, length, texture, z=0.0, yaw=0.0, offset=(0.0, 0.0)):
    """Folha deitada (face para cima), com o verso claro; `length` corre ao longo de Y."""
    with m.at(offset[0], offset[1], z, rz=math.degrees(yaw)):
        m.panel(0, 0, FLAT_NOTE_THICKNESS, width, length, texture, "top")
        m.box(0, 0, 0, width, length, FLAT_NOTE_THICKNESS, "paper_white", skip=("top",))


def build_note_letter():
    """Bilhete da Laura: envelope creme com a carta dobrada para fora."""
    m = MeshBuilder("Item_NOTE_1")
    _sheet(m, 0.12, 0.16, "note_letter", z=0.0, yaw=0.0, offset=(0.0, 0.05))
    _sheet(m, 0.17, 0.115, "note_envelope", z=FLAT_NOTE_THICKNESS, yaw=0.0, offset=(0.0, -0.02))
    return m


def build_note_drawing():
    """Desenho de giz de cera numa folha grande, com um toco de giz vermelho ao lado."""
    m = MeshBuilder("Item_NOTE_2")
    _sheet(m, 0.21, 0.29, "note_crayon")
    with m.at(0.15, -0.05, 0.007, rx=-90, rz=25):
        m.cylinder(0, 0, -0.03, 0.006, 0.06, "toy_red", seg=6)
    return m


def build_note_clipping():
    """Recorte de jornal rasgado: contorno irregular com mapeamento de UV retangular."""
    m = MeshBuilder("Item_NOTE_3")
    w, h = 0.15, 0.17
    outline = [(-0.50, -0.46), (-0.22, -0.50), (0.05, -0.44), (0.30, -0.50), (0.50, -0.45), (0.46, -0.1), (0.50, 0.2),
               (0.42, 0.50), (0.12, 0.44), (-0.14, 0.50), (-0.46, 0.46), (-0.50, 0.1)]
    top = [(x * w, y * h, FLAT_NOTE_THICKNESS) for x, y in outline]
    m.poly(top, "note_newspaper", uv=[(x + 0.5, y + 0.5) for x, y in outline])
    m.poly([(x, y, 0.0) for x, y, _ in reversed(top)], "paper_white")
    return m


def build_note_notebook():
    """Folha de caderno espiral presa com um percevejo vermelho; de pé, frente em +Y."""
    m = MeshBuilder("Item_NOTE_4")
    m.panel(0, 0, 0, 0.19, 0.25, "note_notebook", "front")
    m.panel(0, -FLAT_NOTE_THICKNESS, 0, 0.19, 0.25, "paper_white", "back")
    with m.at(0, 0.0, 0.085, rx=-90):
        m.cylinder(0, 0, 0, 0.009, 0.004, "toy_red", seg=8)
        m.cylinder(0, 0, 0.004, 0.0035, 0.006, "toy_red", seg=6)
    return m


def build_note_postit():
    """Post-it amarelo grudado na porta do frigobar; de pé, frente em +Y."""
    m = MeshBuilder("Item_NOTE_5")
    m.panel(0, 0, 0, 0.085, 0.085, "note_postit", "front")
    m.box(0, -0.0015, 0.03, 0.05, 0.001, 0.02, "tape_silver")
    return m


def build_note_prescription():
    """Receita do Dr. Mills: folha pequena de receituário sobre outra, já amarelada."""
    m = MeshBuilder("Item_NOTE_6")
    _sheet(m, 0.10, 0.14, "linen_dirty", z=0.0, yaw=0.15, offset=(0.012, -0.008))
    _sheet(m, 0.10, 0.135, "note_prescription", z=FLAT_NOTE_THICKNESS, yaw=-0.08)
    return m


def build_note_tow_slip():
    """Guia do pátio: formulário em três vias, dobrado ao meio com a via amarela levantada."""
    m = MeshBuilder("Item_NOTE_7")
    m.box(0, -0.045, 0, 0.125, 0.085, FLAT_NOTE_THICKNESS, "paper_white", skip=("top",))
    m.panel(0, -0.045, FLAT_NOTE_THICKNESS, 0.125, 0.085, "note_tow", "top", uv_rect=(0, 0, 1, 0.5))
    with m.at(0, 0.0, FLAT_NOTE_THICKNESS, rx=8):
        m.panel(0, 0.04, 0.0, 0.125, 0.085, "note_tow", "top", uv_rect=(0, 0.5, 1, 1))
    return m


# ---------------------------------------------------------------------------
# Colocação
# ---------------------------------------------------------------------------
# id -> (construtor, x, y, z da superfície, yaw em graus, modo). z é a superfície onde o item repousa;
# no modo 'wall' é o centro do item, já na altura em que fica preso.
def _placements():
    fridge_x, fridge_y, fridge_z = kitchen.mini_fridge_front()
    return {
        "FLASHLIGHT": (build_item_mesh, 0.40, 6.08, 2.8 + 0.55, 0.0, "rest"),
        "KEY": (build_key, 2.00, 9.32, 0.76, 70.0, "rest"),
        "MAP": (build_map, 10.60, 9.42, 2.8 + 0.76 + 0.021, 8.0, "rest"),
        "BATTERY_1": (build_battery_pair, 0.62, 0.30, 0.5 + 2.8, 15.0, "rest"),
        "BATTERY_2": (build_battery_pair, 9.32, 4.70, 2.8 + 0.90, 100.0, "rest"),
        "BATTERY_3": (build_battery_pair, 4.285, 3.50, 0.30, 35.0, "rest"),
        "BATTERY_4": (build_battery_pair, 11.02, 9.55, kitchen.COUNTER_HEIGHT, 80.0, "rest"),
        "BATTERY_5": (build_battery_pair, 18.05, 2.66, 0.90, 10.0, "rest"),
        "NOTE_1": (build_note_letter, 0.56, 8.86, 2.8 + 0.55, 90.0, "rest"),
        "NOTE_2": (build_note_drawing, 1.35, 3.90, 2.8 + 0.44, -90.0 + 6.0, "rest"),
        "NOTE_3": (build_note_clipping, 3.05, 4.15, 0.422, 35.0, "rest"),
        "NOTE_4": (build_note_notebook, 0.165, 9.42, 1.5, -90.0, "wall"),
        "NOTE_5": (build_note_postit, fridge_x + 0.004, fridge_y + 0.05, fridge_z + 0.12, -90.0, "wall"),
        "NOTE_6": (build_note_prescription, 11.62, 6.72, 2.8 + 0.78, 20.0, "rest"),
        "NOTE_7": (build_note_tow_slip, 15.2, 6.68, 1.005, 12.0, "rest"),
    }


def _prompt(item_id, kind):
    if kind == C.ITEM_NOTE:
        return f"{story.ITEM_PROMPTS[kind]}: {story.NOTES[item_id][0]}"
    return story.ITEM_PROMPTS[kind]


def _create_item(ctx, item_id, builder, x, y, z, yaw_deg, mode):
    kind = item_id.split("_")[0]
    mesh_builder = builder()
    mesh_builder.name = C.N_ITEM + item_id
    if mode == "rest":
        z += REST_CLEARANCE - mesh_builder.bounds()[0][2]
    obj = bpy.data.objects.new(C.N_ITEM + item_id, mesh_builder.to_mesh(C.N_ITEM + item_id))
    obj.location = (x, y, z)
    obj.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    obj[C.P_INTERACT] = "note" if kind == C.ITEM_NOTE else "item"
    obj[C.P_ITEM] = kind
    obj[C.P_ID] = item_id
    obj[C.P_PROMPT] = _prompt(item_id, kind)
    obj[C.P_ROOM] = layout.ITEM_SPOTS[item_id][0]
    obj["sa_mount"] = mode
    if kind == C.ITEM_NOTE:
        obj["sa_title"] = story.NOTES[item_id][0]
    ctx.link(obj, C.COL_ITEMS)
    return obj


def make_items(ctx):
    """Cria os 15 itens (lanterna, chave, mapa, 5 pilhas, 7 notas) e devolve os objetos."""
    return [_create_item(ctx, item_id, *spec) for item_id, spec in _placements().items()]
