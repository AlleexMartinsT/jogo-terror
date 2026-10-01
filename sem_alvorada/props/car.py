"""O carro da família: sedã americano de 4,6 m, batido na frente do lado do passageiro (guia do reboque).

Origem no centro da base, frente = +Y local, motorista à esquerda (-X local). O casco é feito de
painéis (laterais extrudadas com cavas de roda, capô, teto, vidros) em vez de um bloco maciço, para
que o interior seja visível por fora e a partir dos olhos do motorista no final do jogo.
"""
import math

import bpy

from .. import conventions as C
from .. import layout, story
from . import parts
from .kit import MeshBuilder
from .lights import keep_world_position, make_point_light
from .placement import make_collision_box

HALF_WIDTH = 0.95
WHEEL_RADIUS = 0.33
WHEEL_Y = 1.40
WHEEL_X = 0.80
ARCH_RADIUS = 0.42
ARCH_CENTER_Z = 0.30
BELTLINE = 0.98
ROOF = 1.40


def _arch_points(center_y):
    """Pontos (y, z) do arco da cava de roda, indo do lado da frente para o de trás."""
    z_start = 0.40
    t0 = math.asin((z_start - ARCH_CENTER_Z) / ARCH_RADIUS)
    steps = 6
    return [(center_y + ARCH_RADIUS * math.cos(t0 + (math.pi - 2 * t0) * i / steps),
             ARCH_CENTER_Z + ARCH_RADIUS * math.sin(t0 + (math.pi - 2 * t0) * i / steps)) for i in range(steps + 1)]


def _side_profile(damaged):
    """Contorno (y, z) da lateral: cavas de roda embaixo, linha do capô e do porta-malas em cima."""
    front_bottom, front_top, hood_end = (2.30, 0.42), (2.30, 0.72), (1.90, 0.86)
    if damaged:
        front_bottom, front_top, hood_end = (2.12, 0.46), (2.06, 0.60), (1.82, 0.78)
    outline = [front_bottom]
    outline += _arch_points(WHEEL_Y)
    outline += _arch_points(-WHEEL_Y)
    outline += [(-2.30, 0.42), (-2.30, 0.90), (-1.55, 1.00), (0.85, BELTLINE), hood_end, front_top]
    return outline


def _body_panels(m):
    """Laterais, capô amassado, porta-malas, para-choques, faróis, lanternas e assoalho."""
    for side, damaged in ((-1, False), (1, True)):
        x0, x1 = (HALF_WIDTH - 0.06, HALF_WIDTH) if side > 0 else (-HALF_WIDTH, -HALF_WIDTH + 0.06)
        m.extrude(_side_profile(damaged), "yz", x0, x1, "car_paint")
    _hood(m)
    m.box(0, -1.9, 0.90, 1.8, 0.8, 0.03, "car_paint", skip=("bottom",))
    m.box(0, 0.93, 0.93, 1.8, 0.14, 0.05, "car_paint")
    m.box(-0.46, 2.285, 0.40, 0.92, 0.03, 0.32, "car_paint")
    with m.at(0.0, 2.285, 0.40, rz=-9):                       # metade direita do focinho, empurrada para trás
        m.box(0.42, -0.06, 0.0, 0.84, 0.03, 0.26, "car_paint")
    m.box(-0.47, 2.36, 0.36, 0.95, 0.10, 0.17, "chrome")
    with m.at(0.0, 2.34, 0.36, rz=-9):
        m.box(0.42, -0.08, 0.0, 0.84, 0.10, 0.15, "chrome")
    m.box(0, -2.35, 0.36, 1.90, 0.10, 0.20, "chrome")
    m.panel(-0.1, 2.302, 0.60, 0.9, 0.14, "black", "front")
    for i in range(3):
        m.box(-0.1, 2.31, 0.55 + i * 0.045, 0.9, 0.012, 0.012, "chrome")
    m.box(-0.66, 2.30, 0.52, 0.34, 0.05, 0.14, "headlight_glass")
    with m.at(0.60, 2.18, 0.50, rz=-16):
        m.box(0, 0, 0, 0.34, 0.05, 0.13, "headlight_glass")
    m.panel(-0.05, 2.42, 0.35, 0.30, 0.13, "paper_white", "front")
    for side in (-1, 1):
        m.box(side * 0.68, -2.30, 0.68, 0.5, 0.04, 0.14, "tail_light")
    m.panel(0, -2.41, 0.62, 0.30, 0.15, "paper_white", "back")
    m.box(0, -0.1, 0.34, 1.80, 4.5, 0.03, "black")
    m.box(0, 0.86, 0.36, 1.8, 0.03, 0.60, "black")
    m.box(0, -1.52, 0.36, 1.8, 0.03, 0.62, "black")
    m.tube((0.55, -2.15, 0.36), (0.55, -2.52, 0.32), 0.03, "steel_dark", seg=6)


def _hood(m):
    """Capô como superfície: o canto dianteiro direito afundou onde o carro bateu."""
    def fn(u, v):
        x = -0.90 + 1.80 * u
        y = 0.90 + 1.38 * v
        z = BELTLINE - 0.24 * v ** 1.3
        dent = 0.11 * math.exp(-(((x - 0.62) / 0.42) ** 2 + ((y - 2.12) / 0.45) ** 2))
        ripple = 0.015 * math.sin(y * 14 + x * 5) * math.exp(-(((x - 0.62) / 0.6) ** 2 + ((y - 2.12) / 0.6) ** 2))
        return (x, y, z - dent + ripple)

    m.surface(fn, 6, 6, "car_paint", uv_size=(1.8, 1.4), flip=True)


def _cabin(m):
    """Colunas, teto com forro, vidros (o para-brisa trinca do lado do passageiro) e detalhes das portas."""
    for s in (-1, 1):
        m.bar((s * 0.865, 0.85, BELTLINE), (s * 0.72, 0.27, ROOF), 0.07, "car_paint")
        m.bar((s * 0.885, -0.25, BELTLINE), (s * 0.735, -0.25, ROOF), 0.06, "car_paint")
        m.bar((s * 0.85, -1.50, 1.0), (s * 0.72, -0.98, ROOF), 0.13, "car_paint")
        m.bar((s * 0.72, 0.27, ROOF), (s * 0.72, -0.98, ROOF), 0.05, "car_paint")
        m.bar((s * 0.90, 0.85, BELTLINE), (s * 0.90, -1.5, 1.0), 0.05, "chrome")
        m.quad((s * 0.87, 0.80, 1.0), (s * 0.87, -0.22, 1.0), (s * 0.735, -0.22, 1.37), (s * 0.735, 0.30, 1.37),
               "car_glass")
        m.quad((s * 0.87, -0.28, 1.0), (s * 0.86, -1.42, 1.0), (s * 0.735, -0.98, 1.37), (s * 0.735, -0.28, 1.37),
               "car_glass")
        for y in (0.80, -0.25, -1.35):
            m.box(s * 0.955, y, 0.44, 0.008, 0.012, 0.54, "black")
        for y in (-0.05, -0.55):
            m.box(s * 0.965, y, 0.88, 0.014, 0.15, 0.025, "chrome")
        m.box(s * 0.885, -0.33, 0.42, 0.03, 2.2, 0.52, "velour_beige")
        m.box(s * 1.0, 0.72, 1.04, 0.08, 0.12, 0.10, "plastic_gray")
    m.quad((-0.84, 0.85, BELTLINE + 0.01), (0.84, 0.85, BELTLINE + 0.01), (0.70, 0.29, ROOF - 0.02),
           (-0.70, 0.29, ROOF - 0.02), "car_glass_cracked", uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    m.quad((-0.82, -1.48, 1.01), (0.82, -1.48, 1.01), (0.70, -1.0, ROOF - 0.02), (-0.70, -1.0, ROOF - 0.02),
           "car_glass")
    m.box(0, -0.36, ROOF - 0.02, 1.44, 1.32, 0.04, "car_paint", mats={"bottom": "velour_beige"})
    for x in (-0.42, 0.42):
        m.box(x, 0.16, 1.33, 0.36, 0.22, 0.02, "velour_beige")


def _seat(m, x, y):
    m.soft_box(x, y, 0.36, 0.52, 0.50, 0.15, "velour_beige", radius=0.05, edge=0.03)
    with m.at(x, y - 0.27, 0.46, rx=12):
        m.soft_box(0, 0, 0, 0.52, 0.14, 0.56, "velour_beige", radius=0.05, edge=0.03)
    m.soft_box(x, y - 0.35, 1.0, 0.26, 0.10, 0.18, "velour_beige", radius=0.03, edge=0.02)


def _dashboard(m):
    """Painel: relógio 6:12 verde emissivo, rádio, porta-luvas, volante e coluna de direção."""
    m.soft_box(0, 0.62, 0.50, 1.76, 0.42, 0.48, "plastic_gray", radius=0.05, edge=0.03)
    m.soft_box(-0.45, 0.42, 0.96, 0.56, 0.16, 0.12, "black", radius=0.04, edge=0.02)
    m.panel(0.05, 0.405, 0.80, 0.13, 0.06, "digits_dash", "back")
    m.panel(0.05, 0.405, 0.66, 0.30, 0.09, "black", "back")
    m.panel(0.48, 0.405, 0.72, 0.40, 0.20, "steel_dark", "back")
    m.soft_box(0, -0.30, 0.34, 0.24, 0.9, 0.24, "plastic_gray", radius=0.03, edge=0.02)
    hub = (-0.45, 0.10, 0.92)
    with m.at(*hub, rx=65):
        m.torus(0, 0, 0, 0.19, 0.016, "black", seg=14, seg_minor=5)
        m.cylinder(0, 0, -0.02, 0.05, 0.04, "black", seg=6)
        for angle in (90, 210, 330):
            end = (0.18 * math.cos(math.radians(angle)), 0.18 * math.sin(math.radians(angle)), 0)
            m.bar((0, 0, 0), end, 0.02, "black")
    m.tube(hub, (-0.45, 0.36, 0.72), 0.03, "plastic_gray", seg=6)
    m.tube((0.0, 0.29, 1.37), (0.0, 0.30, 1.28), 0.006, "steel_dark", seg=4)
    m.box(0, 0.30, 1.22, 0.22, 0.03, 0.07, "black")


def _interior(m):
    _seat(m, -0.45, -0.75)
    _seat(m, 0.45, -0.75)
    m.soft_box(0, -1.22, 0.36, 1.55, 0.55, 0.15, "velour_beige", radius=0.05, edge=0.03)
    with m.at(0, -1.47, 0.46, rx=10):
        m.soft_box(0, 0, 0, 1.55, 0.14, 0.55, "velour_beige", radius=0.05, edge=0.03)
    m.soft_box(0.55, -1.2, 0.51, 0.38, 0.34, 0.30, "plush_pink", radius=0.05, edge=0.03)       # cadeirinha da Emma
    m.box(0.55, -1.36, 0.80, 0.38, 0.06, 0.26, "plush_pink")
    parts.rabbit(m, 0.09, 0.30, 1.08, 0.22)                                                    # coelhinho no retrovisor
    m.tube((0.09, 0.30, 1.28), (0.09, 0.30, 1.22), 0.004, "steel_dark", seg=3)
    _dashboard(m)


def build_body_mesh():
    m = MeshBuilder("Car_Body")
    _body_panels(m)
    _cabin(m)
    _interior(m)
    return m


def build_wheel_mesh(name):
    """Pneu e calota; o eixo é o X local e a origem, o centro da roda (o runtime gira em torno de X)."""
    m = MeshBuilder(name)
    with m.at(0, 0, 0, ry=90):
        m.lathe([(0.19, -0.11), (0.29, -0.11), (0.33, -0.08), (0.33, 0.08), (0.29, 0.11), (0.19, 0.11)],
                0, 0, 0, "tire_rubber", seg=12, smooth=False)
        m.cylinder(0, 0, -0.112, 0.19, 0.224, "metal", seg=12, caps=(True, True))
        m.cylinder(0, 0, 0.104, 0.07, 0.02, "chrome", seg=8)
        m.cylinder(0, 0, -0.124, 0.07, 0.02, "chrome", seg=8)
    return m


def _new_object(ctx, name, mesh_builder, parent, location):
    obj = bpy.data.objects.new(name, mesh_builder.to_mesh(name))
    obj.location = location
    obj.parent = parent
    ctx.link(obj, C.COL_PROPS)
    return obj


def _marker(ctx, name, world_position, parent, display="PLAIN_AXES", size=0.2):
    marker = bpy.data.objects.new(name, None)
    marker.empty_display_type = display
    marker.empty_display_size = size
    marker.location = world_position
    ctx.link(marker, C.COL_PROPS)
    keep_world_position(marker, parent)
    return marker


def _headlight(ctx, name, x, parent):
    lamp_data = bpy.data.lights.new(name, "SPOT")
    lamp_data.energy = 0.0
    lamp_data.spot_size = math.radians(62)
    lamp_data.spot_blend = 0.45
    lamp_data.use_shadow = False
    lamp_data.color = (1.0, 0.94, 0.78)
    lamp = bpy.data.objects.new(name, lamp_data)
    lamp.location = (x, 2.34, 0.58)
    lamp.rotation_euler = (math.radians(86), 0.0, 0.0)
    lamp.parent = parent
    lamp["sa_base_energy"] = 900.0
    lamp["sa_kind"] = "headlight"
    lamp["sa_on"] = 0
    lamp[C.P_ROOM] = "garage"
    ctx.link(lamp, C.COL_PROPS)
    return lamp


def make_car(ctx):
    """Cria `Car` (raiz), corpo, rodas, faróis desligados, olhos do motorista e ponto de interação."""
    anchor = layout.ANCHORS["car"]
    root = bpy.data.objects.new(C.OBJ_CAR, None)
    root.empty_display_type = "ARROWS"
    root.empty_display_size = 0.6
    root.location = anchor.pos
    root.rotation_euler = (0.0, 0.0, math.radians(anchor.yaw_deg))
    root[C.P_ID] = "car"
    root[C.P_ROOM] = "garage"
    ctx.link(root, C.COL_PROPS)
    body = _new_object(ctx, "Car_Body", build_body_mesh(), root, (0, 0, 0))
    body["sa_tris"] = sum(len(p.vertices) - 2 for p in body.data.polygons)
    for suffix, x, y in (("FL", -WHEEL_X, WHEEL_Y), ("FR", WHEEL_X, WHEEL_Y), ("RL", -WHEEL_X, -WHEEL_Y),
                         ("RR", WHEEL_X, -WHEEL_Y)):
        name = f"Car_Wheel_{suffix}"
        _new_object(ctx, name, build_wheel_mesh(name), root, (x, y, WHEEL_RADIUS))
    _headlight(ctx, "Car_Headlight_L", -0.66, root)
    _headlight(ctx, "Car_Headlight_R", 0.66, root)
    bpy.context.view_layer.update()          # matrix_world do root precisa estar atual antes de parentear os marcadores
    eye = layout.ANCHORS["car_driver_eye"]
    _marker(ctx, "Car_DriverEye", eye.pos, root, "SPHERE", 0.1)
    door_point = layout.ANCHORS["car_interact"]
    interact = _marker(ctx, "Car_Interact", (door_point.x, door_point.y, 0.95), root, "CUBE", 0.35)
    interact[C.P_INTERACT] = "car"
    interact[C.P_ID] = "car"
    interact[C.P_PROMPT] = story.PROMPT_CAR
    make_collision_box(ctx, "car", *anchor.pos, math.radians(anchor.yaw_deg),
                       (-HALF_WIDTH - 0.02, -2.42, 0.30), (HALF_WIDTH + 0.02, 2.42, ROOF + 0.05))
    make_point_light(ctx, "garage", 1, (anchor.x + 0.45, anchor.y - 0.30, 0.95), 0.6, (0.4, 1.0, 0.55), "lamp",
                     parent=root)
    return root
