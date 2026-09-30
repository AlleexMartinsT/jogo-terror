"""Objetos que só existem para as cutscenes: câmera, luzes de apoio, relógio 6:12 e brilho da aurora.

Tudo nasce oculto/apagado; as ações do roteiro ligam quando precisam (`CutLight_*` com energia 0
ficam ocultas para não gastar o orçamento de luzes da cena).
"""
import math

import bpy
from mathutils import Vector

from .. import compat
from .. import conventions as C
from .. import layout
from . import scripts as sc

CAMERA_FOV_DEG = 60.0

SEGMENTS = {          # segmentos de um display de sete: (x0, z0, x1, z1) numa célula 1 x 2
    "top": (0.1, 1.8, 0.9, 2.0), "mid": (0.1, 0.9, 0.9, 1.1), "bot": (0.1, 0.0, 0.9, 0.2),
    "tl": (0.0, 1.0, 0.2, 1.9), "tr": (0.8, 1.0, 1.0, 1.9),
    "bl": (0.0, 0.1, 0.2, 1.0), "br": (0.8, 0.1, 1.0, 1.0),
}
DIGITS = {"6": ("top", "mid", "bot", "tl", "bl", "br"), "1": ("tr", "br"),
          "2": ("top", "tr", "mid", "bl", "bot")}


def _place(obj, ctx, hidden=False):
    ctx.link(obj, C.COL_CUTSCENE)
    obj.hide_viewport = obj.hide_render = hidden
    return obj


def create_camera(ctx):
    data = bpy.data.cameras.new(C.OBJ_CUT_CAM)
    data.sensor_fit = "HORIZONTAL"           # `angle` é o FOV horizontal, como o do jogador
    data.angle = math.radians(CAMERA_FOV_DEG)
    data.clip_start = 0.03
    data.clip_end = 400.0
    cam = bpy.data.objects.new(C.OBJ_CUT_CAM, data)
    first_eye = sc.anchor("nightstand_clock", 0.28, -1.1, 0.75)
    cam.location = first_eye
    cam.rotation_mode = "QUATERNION"
    return _place(cam, ctx)


def _light(ctx, name, kind, color, location, target=None, size=0.05, area=None):
    data = bpy.data.lights.new(name, kind)
    data.color = color
    data.energy = 0.0
    data.use_shadow = False
    if kind == "AREA":
        data.shape = "RECTANGLE"
        data.size, data.size_y = area
    else:
        data.shadow_soft_size = size
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    if target is not None:
        obj.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    return _place(obj, ctx, hidden=True)


def create_lights(ctx):
    clock = layout.ANCHORS["nightstand_clock"]
    _light(ctx, sc.CLOCK_GLOW, "POINT", (1.0, 0.12, 0.07), (clock.x + 0.16, clock.y, clock.z + 0.72))
    _light(ctx, sc.BED_LAMP, "POINT", (1.0, 0.72, 0.42), (clock.x + 0.05, clock.y + 0.12, clock.z + 1.05), size=0.12)
    window = sc.window_center("w_master_n")
    _light(ctx, sc.DAWN_LIGHT, "AREA", (0.55, 0.68, 0.95), (window[0], window[1] + 0.9, window[2]),
           target=(window[0], window[1] - 3.0, window[2] - 0.6), area=(2.6, 1.6))
    road = layout.ENTITY_ROAD_POS
    _light(ctx, sc.ROAD_LIGHT, "SPOT", (0.85, 0.9, 1.0), (road[0], road[1] + 6.0, 3.4),
           target=(road[0], road[1], 1.4), size=0.4)
    sight = layout.ENTITY_FIRST_SIGHT
    _light(ctx, sc.CORRIDOR_RIM, "POINT", (0.55, 0.68, 1.0), (sight[0], sight[1] + 0.9, sight[2] + 2.3), size=0.2)


def _emissive_material(name, color, strength):
    mat = compat.new_material(name)
    compat.set_bsdf(compat.bsdf_of(mat), base_color=color, roughness=1.0, emission=color,
                    emission_strength=strength)
    return mat


def _flat_material(name, color):
    mat = compat.new_material(name)
    compat.set_bsdf(compat.bsdf_of(mat), base_color=color, roughness=0.6)
    return mat


def _digit_quads(glyph, x0, z0, width, height):
    """Retângulos (x0, z0, x1, z1) dos segmentos acesos de um dígito posicionado em (x0, z0)."""
    quads = []
    for name in DIGITS[glyph]:
        a, b, c, d = SEGMENTS[name]
        quads.append((x0 + a * width, z0 + b * height / 2, x0 + c * width, z0 + d * height / 2))
    return quads


def create_end_clock(ctx):
    """Despertador digital marcando 6:12, no lugar do da cabeceira, para o plano final."""
    anchor = layout.ANCHORS["nightstand_clock"]
    width, depth, height = 0.17, 0.06, 0.085
    top = 0.55
    y_front = depth / 2
    verts, faces = [], []

    def box(x0, x1, y0, y1, z0, z1):
        base = len(verts)
        verts.extend((x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1))
        faces.extend(tuple(base + i for i in f) for f in
                     [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])

    box(-width / 2, width / 2, -depth / 2, y_front, 0.0, height)
    body_faces = list(faces)
    glyph_x = {"6": -0.052, "1": -0.002, "2": 0.030}      # 6 : 1 2  (o ":" vai à parte, em x=-0.014)
    digit_w, digit_h, digit_z = 0.022, 0.048, 0.018
    lit = []
    for glyph, gx in glyph_x.items():
        for x0, z0, x1, z1 in _digit_quads(glyph, gx, digit_z, digit_w, digit_h):
            base = len(verts)
            verts.extend([(x0, y_front + 0.001, z0), (x1, y_front + 0.001, z0),
                          (x1, y_front + 0.001, z1), (x0, y_front + 0.001, z1)])
            lit.append((base, base + 1, base + 2, base + 3))
    for dz in (0.028, 0.048):                        # os dois pontos do ":"
        base = len(verts)
        cx, cz = -0.014, digit_z + dz
        verts.extend([(cx - 0.003, y_front + 0.001, cz - 0.003), (cx + 0.003, y_front + 0.001, cz - 0.003),
                      (cx + 0.003, y_front + 0.001, cz + 0.003), (cx - 0.003, y_front + 0.001, cz + 0.003)])
        lit.append((base, base + 1, base + 2, base + 3))

    mesh = bpy.data.meshes.new(sc.END_CLOCK)
    mesh.from_pydata(verts, [], body_faces + lit)
    mesh.materials.append(_flat_material("cut_clock_case", (0.03, 0.03, 0.035)))
    mesh.materials.append(_emissive_material("cut_clock_digits", (1.0, 0.05, 0.03), 9.0))
    for index, poly in enumerate(mesh.polygons):
        poly.material_index = 1 if index >= len(body_faces) else 0
    mesh.update()
    obj = bpy.data.objects.new(sc.END_CLOCK, mesh)
    obj.location = (anchor.x, anchor.y, anchor.z + top)
    obj.rotation_euler = (0.0, 0.0, math.radians(anchor.yaw_deg))
    return _place(obj, ctx, hidden=True)


def create_dawn_glow(ctx):
    """Plano emissivo cinza-azulado logo fora da janela norte do quarto: a "janela um pouco mais clara"."""
    window = sc.window_center("w_master_n")
    op = layout.OPENINGS["w_master_n"]
    half_w, half_h = op.width / 2 + 0.6, op.height / 2 + 0.6
    y = op.pos + layout.WALL_T_EXT / 2 + 0.15
    verts = [(-half_w, 0, -half_h), (half_w, 0, -half_h), (half_w, 0, half_h), (-half_w, 0, half_h)]
    mesh = bpy.data.meshes.new(sc.DAWN_GLOW)
    mesh.from_pydata(verts, [], [(0, 3, 2, 1)])           # normal para -Y: vista de dentro do quarto
    mesh.materials.append(_emissive_material("cut_dawn_glow", (0.36, 0.45, 0.62), 1.4))
    obj = bpy.data.objects.new(sc.DAWN_GLOW, mesh)
    obj.location = (window[0], y, window[2])
    return _place(obj, ctx, hidden=True)


def create_all(ctx):
    create_camera(ctx)
    create_lights(ctx)
    create_end_clock(ctx)
    create_dawn_glow(ctx)
