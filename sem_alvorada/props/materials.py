"""Materiais dos props.

Os nomes canônicos (`conventions.MATERIAL_NAMES`) continuam vindo de `matapi`, que
pede ao módulo world. Aqui ficam só os materiais que existem por causa dos props:
papéis e fotos com textura gerada, vidro, plástico, pelúcia, emissivos (despertador,
TV, luz noturna) e decals com alfa (manchas, marcas de mão).
"""
from collections import namedtuple

import bpy

from .. import compat, matapi
from . import textures

Spec = namedtuple("Spec", "texture color roughness metallic emission emit_color alpha mapping",
                  defaults=(None, (0.5, 0.5, 0.5), 0.85, 0.0, 0.0, None, 1.0, False))


def _tex(name, roughness=0.9, **extra):
    return Spec(texture=name, roughness=roughness, **extra)


def _flat(color, roughness=0.85, metallic=0.0, **extra):
    return Spec(color=color, roughness=roughness, metallic=metallic, **extra)


SPECS = {
    # papéis, quadros e mostradores (a textura é o próprio material)
    **{name: _tex(name) for name in (
        "note_letter", "note_envelope", "note_crayon", "note_newspaper", "note_notebook",
        "note_postit", "note_prescription", "note_tow", "city_map", "cork_clippings",
        "photo_trio", "photo_mother_child", "photo_father_child", "photo_portrait",
        "painting_lake", "painting_barn", "painting_still", "clock_face", "calendar",
        "book_spines", "rug_red", "rug_blue", "rug_runner", "plaid_blanket", "comforter_stars",
        "linen_sheet", "linen_dirty", "shower_curtain", "cardboard", "cardboard_emma",
        "cardboard_toys", "can_labels", "fridge_front", "block_e", "block_m", "block_a",
        "appliance_panel", "laminate", "globe", "veneer_dark", "veneer_mid")},
    "mirror_cracked": _tex("mirror_cracked", 0.15),
    "mirror_plain": _tex("mirror_plain", 0.15),
    # emissivos
    "digits_647": Spec(texture="digits_647", color=(0, 0, 0), emission=2.6),
    "digits_612": Spec(texture="digits_612", color=(0, 0, 0), emission=2.6),
    "digits_dash": Spec(texture="digits_dash", color=(0, 0, 0), emission=1.4),
    "tv_static": Spec(texture="tv_static", color=(0, 0, 0), emission=1.3, mapping=True),
    "lampshade_lit": _flat((0.55, 0.42, 0.24), 0.9, emission=1.6, emit_color=(1.0, 0.72, 0.38)),
    "lampshade_off": _flat((0.45, 0.38, 0.28), 0.9),
    "night_light": _flat((0.7, 0.6, 0.4), 0.5, emission=3.5, emit_color=(1.0, 0.85, 0.55)),
    "lens_glow": _flat((0.8, 0.8, 0.75), 0.1, emission=0.9, emit_color=(0.95, 0.95, 0.85)),
    "led_red": _flat((0.3, 0.0, 0.0), 0.5, emission=4.0, emit_color=(1.0, 0.05, 0.02)),
    "headlight_glass": _flat((0.55, 0.55, 0.50), 0.08, 0.2),
    "tail_light": _flat((0.30, 0.03, 0.03), 0.3, emission=0.15, emit_color=(0.8, 0.05, 0.03)),
    # decals com alfa
    "stain_dark": Spec(texture="stain_dark", roughness=0.5, alpha=1.0),
    "handprints": Spec(texture="handprints", roughness=0.5, alpha=1.0),
    "stain_oil": Spec(texture="stain_oil", roughness=0.3, alpha=1.0),
    # vidros
    "glass_clear": _flat((0.55, 0.60, 0.62), 0.05, alpha=0.22),
    "car_glass": _flat((0.05, 0.08, 0.10), 0.05, alpha=0.30),
    "car_glass_cracked": Spec(texture="windshield_crack", roughness=0.05, alpha=0.9),
    "water_dark": _flat((0.005, 0.012, 0.012), 0.03),
    # metais e plásticos
    "chrome": _flat((0.55, 0.56, 0.58), 0.22, 1.0),
    "brass": _flat((0.45, 0.33, 0.12), 0.35, 0.9),
    "steel_dark": _flat((0.10, 0.10, 0.11), 0.4, 0.9),
    "key_metal": _flat((0.75, 0.72, 0.60), 0.25, 1.0, emission=0.35, emit_color=(1.0, 0.92, 0.65)),
    "flash_body": _flat((0.34, 0.35, 0.38), 0.3, 1.0),
    "flash_grip": _flat((0.05, 0.05, 0.05), 0.7),
    "battery_copper": _flat((0.80, 0.42, 0.10), 0.35, 0.6, emission=0.25, emit_color=(0.9, 0.5, 0.15)),
    "battery_black": _flat((0.04, 0.04, 0.04), 0.4),
    "tape_silver": _flat((0.62, 0.62, 0.64), 0.35, 0.5),
    "porcelain": _flat((0.52, 0.52, 0.48), 0.2),
    "appliance_dark": _flat((0.05, 0.05, 0.06), 0.4),
    "plastic_beige": _flat((0.50, 0.46, 0.36), 0.45),
    "plastic_gray": _flat((0.22, 0.22, 0.23), 0.5),
    # tecidos, couros, pelúcias, brinquedos
    "leather_brown": _flat((0.17, 0.09, 0.05), 0.55),
    "velour_beige": _flat((0.36, 0.30, 0.22), 0.95),
    "coat_dark": _flat((0.07, 0.08, 0.10), 0.95),
    "coat_beige": _flat((0.36, 0.31, 0.23), 0.95),
    "coat_yellow": _flat((0.72, 0.62, 0.10), 0.7),
    "boot_yellow": _flat((0.72, 0.62, 0.08), 0.3),
    "plush_pink": _flat((0.62, 0.32, 0.40), 0.95),
    "plush_yellow": _flat((0.68, 0.58, 0.22), 0.95),
    "plush_white": _flat((0.70, 0.68, 0.63), 0.95),
    "plush_brown": _flat((0.36, 0.23, 0.14), 0.95),
    "plush_blue": _flat((0.26, 0.36, 0.56), 0.95),
    "toy_red": _flat((0.58, 0.10, 0.08), 0.5),
    "toy_blue": _flat((0.10, 0.20, 0.52), 0.5),
    "toy_green": _flat((0.12, 0.42, 0.16), 0.5),
    "toy_yellow": _flat((0.72, 0.62, 0.10), 0.5),
    "rubber_duck": _flat((0.92, 0.76, 0.10), 0.35),
    "painted_pink": _flat((0.62, 0.36, 0.44), 0.7),
    "painted_cream": _flat((0.62, 0.58, 0.45), 0.7),
    "painted_white": _flat((0.58, 0.57, 0.52), 0.6),
    "candle": _flat((0.76, 0.72, 0.60), 0.6),
    "ceramic_cream": _flat((0.64, 0.62, 0.55), 0.3),
    "food_dried": _flat((0.28, 0.20, 0.10), 0.9),
    "pill_orange": _flat((0.70, 0.32, 0.06), 0.3, alpha=0.9),
    "skin_hand": _flat((0.52, 0.38, 0.31), 0.7),
    "sleeve_cloth": _flat((0.22, 0.25, 0.33), 0.95),
    "tire_rubber": _flat((0.035, 0.035, 0.04), 0.9),
    "paper_white": _flat((0.72, 0.70, 0.62), 0.9),
    "carpet_stain": _flat((0.12, 0.04, 0.03), 0.9),
}


def _add_image_node(mat, spec):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = textures.image(spec.texture)
    image_node.interpolation = "Closest"
    image_node.extension = "REPEAT"
    if spec.mapping:
        coords = nodes.new("ShaderNodeTexCoord")
        mapping = nodes.new("ShaderNodeMapping")
        mapping.name = "StaticMapping"        # o engine desloca "Location" a cada quadro para animar o chiado
        links.new(coords.outputs["UV"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], image_node.inputs["Vector"])
    return image_node


def _build(name, spec):
    mat = compat.new_material(name)
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, base_color=spec.color, roughness=spec.roughness, metallic=spec.metallic,
                    specular=0.2 if spec.metallic == 0 else 0.5)
    links = mat.node_tree.links
    if spec.texture:
        image_node = _add_image_node(mat, spec)
        links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
        if spec.emission:
            links.new(image_node.outputs["Color"], bsdf.inputs["Emission Color"])
            compat.set_bsdf(bsdf, emission_strength=spec.emission)
        if spec.alpha < 1.0 or name in ("stain_dark", "handprints", "stain_oil"):
            links.new(image_node.outputs["Alpha"], bsdf.inputs["Alpha"])
    elif spec.emission:
        compat.set_bsdf(bsdf, emission=spec.emit_color or spec.color, emission_strength=spec.emission)
    if spec.texture is None and spec.alpha < 1.0:
        compat.set_bsdf(bsdf, alpha=spec.alpha)
    translucent = spec.alpha < 1.0 or name in ("stain_dark", "handprints", "stain_oil")
    if translucent and hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    mat.diffuse_color = (*spec.color, 1.0)
    return mat


# nome -> função sem argumentos que devolve um Material pronto. Para materiais com nós próprios
# (relevo, mistura de camadas, emissão animada): cada módulo registra os seus sem editar este arquivo.
BUILDERS = {}


def register_builder(name, build):
    BUILDERS[name] = build


def get(name):
    """Material `name`: construtor registrado, senão SPECS dos props, senão o canônico via matapi."""
    existing_custom = bpy.data.materials.get(name)
    if name in BUILDERS:
        return existing_custom if existing_custom is not None else BUILDERS[name]()
    spec = SPECS.get(name)
    if spec is None:
        return matapi.get_material(name)
    existing = bpy.data.materials.get(name)
    return existing if existing is not None else _build(name, spec)
