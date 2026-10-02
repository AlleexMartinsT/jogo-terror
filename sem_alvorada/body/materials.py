"""Materiais do corpo: pele, unha, flanela, jeans, couro, borracha, botão, metal, cadarço.

Cada material de tecido ou pele junta uma textura de ATLAS (UVMap: desgaste, sujeira, costuras) com uma de
LADRILHO (UVTile: trama, xadrez, poros) e usa o alfa de cada uma como altura do relevo. As imagens são
geradas por `tex` (≤ 512x512), empacotadas no .blend e usam filtro Linear.
"""
import numpy as np

import bpy

from .. import compat
from . import tex

# nome do slot -> (cor linear, rugosidade, metálico) dos materiais sem textura
FLAT = {
    "sole": ((0.040, 0.040, 0.042), 0.88, 0.0),
    "button": ((0.50, 0.46, 0.36), 0.35, 0.0),
    "metal": ((0.42, 0.38, 0.30), 0.35, 0.9),
    "lace": ((0.42, 0.36, 0.27), 0.95, 0.0),
}
SLOT_ORDER = ["skin", "nail", "flannel", "denim", "denim_hip", "leather", "sole", "button", "metal", "lace"]


def _image(name, array):
    existing = bpy.data.images.get(name)
    if existing is not None:
        return existing
    height, width = array.shape[:2]
    image = bpy.data.images.new(name, width, height, alpha=True)
    image.pixels.foreach_set(np.ascontiguousarray(array, np.float32).ravel())
    image.alpha_mode = "CHANNEL_PACKED"
    image.pack()
    image.update()
    return image


def _image_node(tree, image, uv_name):
    uv = tree.nodes.new("ShaderNodeUVMap")
    uv.uv_map = uv_name
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    node.interpolation = "Linear"
    node.extension = "REPEAT"
    tree.links.new(uv.outputs["UV"], node.inputs["Vector"])
    return node


def _multiply(tree, a, b):
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    tree.links.new(a, mix.inputs[6])
    tree.links.new(b, mix.inputs[7])
    return mix.outputs[2]


def textured(name, *, atlas=None, tile=None, color=(0.5, 0.5, 0.5), roughness=0.8, metallic=0.0, specular=0.3,
             relief=1.0, distance=0.003, tile_relief=0.5, tile_distance=0.0008, tint=None):
    """Material com atlas e/ou ladrilho. `atlas`/`tile`: arrays (H,W,4) de `tex`."""
    mat = compat.new_material(name)
    tree, links = mat.node_tree, mat.node_tree.links
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, base_color=color, roughness=roughness, metallic=metallic, specular=specular)
    colors, bumps = [], []
    if atlas is not None:
        node = _image_node(tree, _image(f"{name}_atlas", atlas), "UVMap")
        colors.append(node.outputs["Color"])
        bumps.append((node.outputs["Alpha"], relief, distance))
    if tile is not None:
        node = _image_node(tree, _image(f"{name}_tile", tile), "UVTile")
        colors.append(node.outputs["Color"])
        bumps.append((node.outputs["Alpha"], tile_relief, tile_distance))
    out = colors[0]
    for extra in colors[1:]:
        out = _multiply(tree, out, extra)
    if tint is not None:
        solid = tree.nodes.new("ShaderNodeRGB")
        solid.outputs[0].default_value = (*tint, 1.0)
        out = _multiply(tree, out, solid.outputs[0])
    links.new(out, bsdf.inputs["Base Color"])
    normal = None
    for height, strength, dist in bumps:
        bump = tree.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = strength
        bump.inputs["Distance"].default_value = dist
        links.new(height, bump.inputs["Height"])
        if normal is not None:
            links.new(normal, bump.inputs["Normal"])
        normal = bump.outputs["Normal"]
    if normal is not None:
        links.new(normal, bsdf.inputs["Normal"])
    mat.diffuse_color = (*color, 1.0)
    return mat


def _skin():
    return textured("body_skin", atlas=tex.atlas_skin(), color=(0.5, 0.35, 0.3), roughness=0.58, specular=0.35,
                    relief=1.0, distance=0.0045)


def _nail():
    return textured("body_nail", atlas=tex.atlas_nail(), color=(0.6, 0.45, 0.42), roughness=0.22, specular=0.6,
                    relief=0.6, distance=0.0008)


def _flannel():
    return textured("body_flannel", atlas=tex.atlas_flannel(), tile=tex.tile_flannel(), color=(0.3, 0.12, 0.1),
                    roughness=0.95, specular=0.15, relief=0.6, distance=0.002, tile_relief=0.9, tile_distance=0.0022)


def _denim():
    return textured("body_denim", atlas=tex.atlas_denim_legs(), tile=tex.tile_denim(), color=(0.12, 0.16, 0.26),
                    roughness=0.9, specular=0.15, relief=0.8, distance=0.0016, tile_relief=0.9, tile_distance=0.0012)


def _denim_hip():
    return textured("body_denim_hip", atlas=tex.atlas_denim_hip(), tile=tex.tile_denim(), color=(0.12, 0.16, 0.26),
                    roughness=0.9, specular=0.15, relief=0.8, distance=0.0016, tile_relief=0.9, tile_distance=0.0012)


def _leather():
    return textured("body_leather", atlas=tex.atlas_leather(), tile=tex.tile_leather(), color=(0.2, 0.1, 0.06),
                    roughness=0.5, specular=0.4, relief=0.9, distance=0.002, tile_relief=1.0, tile_distance=0.0025)


BUILDERS = {"skin": _skin, "nail": _nail, "flannel": _flannel, "denim": _denim, "denim_hip": _denim_hip, "leather": _leather}


def get(name):
    """Material do slot `name` (cria na primeira vez)."""
    full = f"body_{name}"
    existing = bpy.data.materials.get(full)
    if existing is not None:
        return existing
    if name in BUILDERS:
        return BUILDERS[name]()
    color, roughness, metallic = FLAT[name]
    mat = compat.new_material(full)
    compat.set_bsdf(compat.bsdf_of(mat), base_color=color, roughness=roughness, metallic=metallic,
                    specular=0.3 if metallic == 0 else 0.5)
    mat.diffuse_color = (*color, 1.0)
    return mat


def slot_materials():
    return [get(name) for name in SLOT_ORDER]


def slot_index(name):
    return SLOT_ORDER.index(name)
