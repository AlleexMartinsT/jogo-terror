"""Céu noturno e o Sol Negro.

O `World` é quase preto, com uma faixa fraca de luz fria no horizonte (é ela que desenha as
casas e árvores como silhuetas) e um halo cinza-quente em volta do Sol Negro. O disco e a
coroa são malhas a 140 m, para o disco preto cobrir o halo e a coroa brilhar de verdade.

O nó `SA_DawnGain` multiplica o halo: a cena final pode chamar `set_dawn` para deixar o
horizonte "um pouco mais claro".
"""
import math

import bpy
from mathutils import Vector

from .. import conventions as C
from .. import layout
from . import materials
from .meshkit import MeshBuilder, empty

SUN_ANCHOR = (2.5, 10.0, 4.4)       # centro da janela w_master_n: dali o disco fica concêntrico com o halo
CORONA_SCALE = 1.7                  # raio da malha da coroa em múltiplos do raio do disco
DISC_SIDES = 48
DAWN_GAIN_NODE = "SA_DawnGain"

HORIZON_RAMP = [(0.00, (0.090, 0.100, 0.125)), (0.12, (0.045, 0.052, 0.068)),
                (0.35, (0.014, 0.017, 0.026)), (1.00, (0.0015, 0.0018, 0.0032))]
HALO_RAMP = [(0.000, (0.060, 0.050, 0.038)), (0.056, (0.052, 0.044, 0.034)), (0.170, (0.022, 0.021, 0.020)),
             (0.450, (0.008, 0.009, 0.011)), (1.000, (0.0, 0.0, 0.0))]


def sun_direction():
    """Vetor unitário para o Sol Negro (azimute medido do norte para leste)."""
    ring = layout.SUN_RING
    azimuth, elevation = math.radians(ring["azimuth_deg"]), math.radians(ring["elevation_deg"])
    return Vector((math.sin(azimuth) * math.cos(elevation), math.cos(azimuth) * math.cos(elevation),
                   math.sin(elevation)))


def build(ctx):
    build_world(ctx.scene)
    build_black_sun(ctx)
    build_fog_boxes(ctx)
    ctx.log("céu, neblina interna e Sol Negro")


def _ramp(tree, stops, factor_socket):
    node = tree.nodes.new("ShaderNodeValToRGB")
    node.color_ramp.interpolation = "LINEAR"
    elements = node.color_ramp.elements
    while len(elements) < len(stops):
        elements.new(0.5)
    for element, (position, color) in zip(elements, stops):
        element.position = position
        element.color = (*color, 1.0)
    tree.links.new(factor_socket, node.inputs["Fac"])
    return node.outputs["Color"]


def _math(tree, operation, a, b=None, clamp=False):
    node = tree.nodes.new("ShaderNodeMath")
    node.operation = operation
    node.use_clamp = clamp
    for index, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = value
        else:
            tree.links.new(value, node.inputs[index])
    return node.outputs[0]


def build_world(scene):
    world = bpy.data.worlds.get("SA_World") or bpy.data.worlds.new("SA_World")
    scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()
    coords = tree.nodes.new("ShaderNodeTexCoord")
    heading = tree.nodes.new("ShaderNodeVectorMath")
    heading.operation = "NORMALIZE"
    tree.links.new(coords.outputs["Generated"], heading.inputs[0])
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(heading.outputs["Vector"], split.inputs["Vector"])

    elevation = _math(tree, "POWER", _math(tree, "ABSOLUTE", split.outputs["Z"]), 0.5)
    horizon = _ramp(tree, HORIZON_RAMP, elevation)

    toward_sun = tree.nodes.new("ShaderNodeVectorMath")
    toward_sun.operation = "DOT_PRODUCT"
    toward_sun.inputs[1].default_value = tuple(sun_direction())
    tree.links.new(heading.outputs["Vector"], toward_sun.inputs[0])
    angle = _math(tree, "ARCCOSINE", toward_sun.outputs["Value"], clamp=False)
    halo = _ramp(tree, HALO_RAMP, angle)

    dawn = tree.nodes.new("ShaderNodeVectorMath")
    dawn.name = DAWN_GAIN_NODE
    dawn.operation = "SCALE"
    dawn.inputs["Scale"].default_value = 1.0
    tree.links.new(halo, dawn.inputs[0])
    total = tree.nodes.new("ShaderNodeVectorMath")
    total.operation = "ADD"
    tree.links.new(horizon, total.inputs[0])
    tree.links.new(dawn.outputs["Vector"], total.inputs[1])

    background = tree.nodes.new("ShaderNodeBackground")
    tree.links.new(total.outputs["Vector"], background.inputs["Color"])
    output = tree.nodes.new("ShaderNodeOutputWorld")
    tree.links.new(background.outputs["Background"], output.inputs["Surface"])

    return world


def set_dawn(scene, amount):
    """0 = noite (padrão); 1 = horizonte e halo bem mais claros. Usado no final do jogo."""
    node = scene.world.node_tree.nodes.get(DAWN_GAIN_NODE)
    if node is not None:
        node.inputs["Scale"].default_value = 1.0 + 3.0 * amount


def build_fog_boxes(ctx):
    """Neblina só DENTRO da casa e da garagem (uma caixa de volume para cada bloco).

    Um volume no World apaga o céu no EEVEE (o fundo vira preto assim que existe qualquer
    densidade), e o céu com o Sol Negro é justamente o que a janela do quarto mostra."""
    blocks = {"FogBox_House": (layout.HOUSE_RECT, layout.CEIL_Z[1]),
              "FogBox_Garage": (layout.ROOMS["garage"].rect, layout.CEIL_Z[0])}
    for name, (rect, top) in blocks.items():
        builder = MeshBuilder(name)
        builder.box(rect.x0 + 0.1, rect.y0 + 0.1, 0.0, rect.x1 - 0.1, rect.y1 - 0.1, top - 0.05, materials.FOG_MATERIAL)
        box = builder.build(ctx, C.COL_WORLD)
        box.display_type = "WIRE"
        box.hide_select = True
        box.visible_shadow = False


def set_fog_density(scene, density):
    """Densidade da neblina interna (0 = desligada). Os materiais são compartilhados."""
    mat = bpy.data.materials.get(materials.FOG_MATERIAL)
    node = mat.node_tree.nodes.get(materials.FOG_NODE) if mat and mat.node_tree else None
    if node is not None:
        node.inputs["Density"].default_value = density


def _disc_mesh(name, material):
    """Disco de raio 1 no plano XY, com a normal em +Z."""
    builder = MeshBuilder(name)
    builder.polygon([(math.cos(2 * math.pi * i / DISC_SIDES), math.sin(2 * math.pi * i / DISC_SIDES), 0.0)
                     for i in range(DISC_SIDES)], material)
    return builder


def build_black_sun(ctx):
    ring = layout.SUN_RING
    direction = sun_direction()
    radius = ring["distance"] * math.tan(math.radians(ring["radius_deg"]))
    facing = (-direction).to_track_quat("Z", "Y").to_euler()

    root = empty(ctx, "BlackSun", C.COL_WORLD, tuple(Vector(SUN_ANCHOR) + direction * ring["distance"]))
    root.rotation_euler = facing
    root["sa_kind"] = "black_sun"
    # +Z local aponta para a casa: o disco fica 0,6 m na frente da coroa para cobri-la
    for name, material, scale, toward_viewer in (("BlackSun_Corona", "sun_corona", radius * CORONA_SCALE, 0.0),
                                                 ("BlackSun_Disc", "sun_black", radius, 0.6)):
        disc = _disc_mesh(name, material).build(ctx, C.COL_WORLD)
        disc.parent = root
        disc.location = (0.0, 0.0, toward_viewer)
        disc.scale = (scale, scale, scale)
