"""Materiais do Alto: `entity_skin`, `entity_cloth` e `entity_eye`.

As texturas nascem em numpy (`textures.py`), viram imagens empacotadas no .blend e entram
no Principled com interpolação `Closest`, para o visual pixelado de GoldSrc.
"""
import bpy
import numpy as np

from .. import compat
from . import textures

SKIN = "entity_skin"
CLOTH = "entity_cloth"
EYE = "entity_eye"

EYE_COLOR = (0.88, 0.94, 1.0)
EYE_MAX_STRENGTH = 14.0


def _packed_image(name, pixels):
    """Cria (ou recria) uma imagem RGBA a partir de um array (h, w, 3) e a empacota."""
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    height, width = pixels.shape[:2]
    image = bpy.data.images.new(name, width, height, alpha=False)
    rgba = np.ones((height, width, 4), np.float32)
    rgba[..., :3] = pixels
    image.pixels.foreach_set(rgba.ravel())
    image.colorspace_settings.name = "sRGB"
    image.pack()
    return image


def _textured_material(name, image, roughness, specular):
    mat = compat.new_material(name)
    tree = mat.node_tree
    bsdf = compat.bsdf_of(mat)
    tex = tree.nodes.get("EntityTexture") or tree.nodes.new("ShaderNodeTexImage")
    tex.name = "EntityTexture"
    tex.image = image
    tex.interpolation = "Closest"
    for link in list(tex.outputs["Color"].links):
        tree.links.remove(link)
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    compat.set_bsdf(bsdf, roughness=roughness, metallic=0.0, specular=specular)
    return mat


def build_skin(rng):
    image = _packed_image("entity_skin_tex", textures.skin_texture(rng))
    return _textured_material(SKIN, image, roughness=0.78, specular=0.25)


def build_cloth(rng):
    image = _packed_image("entity_cloth_tex", textures.cloth_texture(rng))
    return _textured_material(CLOTH, image, roughness=0.95, specular=0.05)


def build_eye():
    mat = compat.new_material(EYE)
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, base_color=EYE_COLOR, roughness=1.0, emission=EYE_COLOR,
                    emission_strength=EYE_MAX_STRENGTH)
    return mat


def build_all(rng):
    return {SKIN: build_skin(rng), CLOTH: build_cloth(rng), EYE: build_eye()}


def set_eye_strength(level):
    """Brilho dos olhos: 0 = apagados, 1 = branco intenso."""
    mat = bpy.data.materials.get(EYE)
    if mat is None:
        return
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, emission_strength=EYE_MAX_STRENGTH * max(0.0, min(1.0, level)))
