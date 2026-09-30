"""Materiais procedurais da casa e do exterior (`build_material` atende `conventions.MATERIAL_NAMES`).

Decisões que valem saber:
- As texturas são geradas em numpy (`texgen`), empacotadas no .blend e lidas com interpolação
  `Closest` (visual GoldSrc / Cry of Fear).
- O mapeamento é por caixa nas coordenadas de OBJETO, não por UV. Assim qualquer malha (as
  minhas, as de props feitas com bmesh sem UV) recebe textura sem esticar, na mesma densidade
  de texels por metro em todas as superfícies.
- Paredes e pisos multiplicam uma segunda camada de sujeira grande (8 m), que quebra a repetição
  do padrão curto e coloca a sujeira onde ela aparece na vida real (rente ao piso, no teto).
"""
from dataclasses import dataclass
from typing import Callable, Optional

import bpy
import numpy as np

from .. import compat
from .. import conventions as C
from . import texgen

WALL_OVERLAY = ("ov_wall", (8.0, 8.0, 2.8))     # 8 m de largura por 2,8 m (um pé-direito)
FLOOR_OVERLAY = ("ov_floor", (8.0, 8.0, 8.0))
GARAGE_DOOR_CLIP_Z = 2.85                        # acima disso o portão aberto some (entra no forro)

EXTRA_MATERIAL_NAMES = (
    "wall_siding_ext", "door_garage_metal", "fixture_glow", "asphalt", "road_paint", "grass_dead",
    "sidewalk", "bark", "fence_wood", "night_silhouette", "sun_black", "sun_corona",
)


@dataclass(frozen=True)
class Surface:
    """Como uma superfície texturizada é montada."""
    make: Callable
    tile: float                         # metros por repetição horizontal
    tile_v: Optional[float] = None      # metros por repetição vertical (padrão: igual a `tile`)
    roughness: float = 0.9
    specular: float = 0.15
    overlay: Optional[tuple] = None
    culled: bool = False


def _dark_wood_floor(rng):
    return texgen.wood_planks(rng, base=(0.15, 0.09, 0.055), vertical=True)


SURFACES = {
    "wall_wallpaper": Surface(texgen.wallpaper, 1.0, roughness=0.93, specular=0.08, overlay=WALL_OVERLAY),
    "wall_paint_dirty": Surface(texgen.paint_dirty, 1.0, roughness=0.85, specular=0.2, overlay=WALL_OVERLAY),
    "wall_tile_bath": Surface(texgen.bathroom_wall_tile, 1.2, roughness=0.32, specular=0.55, overlay=WALL_OVERLAY),
    "wall_garage": Surface(texgen.garage_block, 1.6, roughness=0.9, specular=0.1, overlay=WALL_OVERLAY),
    "wall_brick_ext": Surface(texgen.brick, 0.96, roughness=0.95, specular=0.05),
    "wall_siding_ext": Surface(texgen.clapboard, 0.64, roughness=0.88, specular=0.1, overlay=WALL_OVERLAY),
    "floor_wood": Surface(texgen.wood_planks, 1.0, roughness=0.5, specular=0.3, overlay=FLOOR_OVERLAY),
    "floor_wood_dark": Surface(_dark_wood_floor, 1.0, roughness=0.45, specular=0.3, overlay=FLOOR_OVERLAY),
    "floor_carpet": Surface(texgen.carpet, 1.0, roughness=1.0, specular=0.0, overlay=FLOOR_OVERLAY),
    "floor_linoleum": Surface(texgen.linoleum, 1.0, roughness=0.4, specular=0.4, overlay=FLOOR_OVERLAY),
    "floor_tile_bath": Surface(texgen.bathroom_floor_tile, 1.0, roughness=0.3, specular=0.5, overlay=FLOOR_OVERLAY),
    "floor_concrete": Surface(texgen.concrete, 2.0, roughness=0.85, specular=0.12, overlay=FLOOR_OVERLAY),
    "ceiling": Surface(texgen.ceiling_plaster, 1.0, roughness=1.0, specular=0.0, overlay=FLOOR_OVERLAY, culled=True),
    "roof_shingle": Surface(texgen.shingles, 0.96, roughness=0.95, specular=0.05),
    "door_wood": Surface(texgen.door_wood, 0.9, 2.05, roughness=0.6, specular=0.25),
    "trim_white": Surface(texgen.trim_paint, 0.64, roughness=0.7, specular=0.2, overlay=WALL_OVERLAY),
    "stairs_wood": Surface(texgen.wood_stairs, 1.0, roughness=0.5, specular=0.3, overlay=FLOOR_OVERLAY),
    "curtain": Surface(texgen.curtain_fabric, 0.64, roughness=1.0, specular=0.0),
    "asphalt": Surface(texgen.asphalt, 3.0, roughness=0.95, specular=0.05),
    "road_paint": Surface(texgen.road_paint, 0.64, roughness=0.9, specular=0.05),
    "grass_dead": Surface(texgen.dead_grass, 2.0, roughness=1.0, specular=0.0),
    "sidewalk": Surface(texgen.sidewalk, 1.5, roughness=0.9, specular=0.08),
    "bark": Surface(texgen.bark, 0.5, roughness=1.0, specular=0.0),
    "fence_wood": Surface(texgen.picket_paint, 0.64, roughness=0.9, specular=0.05),
}

# Básicos da paleta: (textura de granulado, escala em metros, rugosidade, metálico, especular)
BASIC_LOOKS = {
    "metal": ("grit", 0.5, 0.42, 0.85, 0.5),
    "car_paint": (None, 1.0, 0.32, 0.4, 0.6),
    "black": (None, 1.0, 0.8, 0.0, 0.1),
    "rubber": (None, 1.0, 0.9, 0.0, 0.1),
    "blood": (None, 1.0, 0.18, 0.0, 0.6),
    "glass_dark": (None, 1.0, 0.05, 0.0, 0.9),
    "skin_grey": (None, 1.0, 0.7, 0.0, 0.2),
    "paper": ("grit", 0.5, 0.95, 0.0, 0.05),
}
GRAIN_BY_PREFIX = {"wood_": "wood_grain", "fabric_": "fabric_weave", "carpet_": "fabric_weave"}


def _to_srgb(linear):
    linear = np.clip(linear, 0.0, 1.0)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * np.power(linear, 1 / 2.4) - 0.055)


def image_from_array(name, linear_rgb):
    """Imagem de 8 bits sRGB empacotada no .blend (senão some ao salvar)."""
    existing = bpy.data.images.get(name)
    if existing is not None:
        return existing
    height, width, _ = linear_rgb.shape
    image = bpy.data.images.new(name, width, height, alpha=False)
    pixels = np.ones((height, width, 4), np.float32)
    pixels[..., :3] = _to_srgb(linear_rgb)
    image.pixels.foreach_set(pixels.ravel())
    # Não mexa em colorspace_settings antes do pack(): o Blender 5.0 então ignora o empacotamento
    # de imagens geradas, e a textura viraria uma cor lisa ao reabrir o .blend.
    image.pack()
    return image


def _texture_image(name, make):
    existing = bpy.data.images.get(name)
    if existing is not None:
        return existing
    return image_from_array(name, make(texgen.rng_for(name)))


# --------------------------------------------------------------------------
# Nós
# --------------------------------------------------------------------------
def _box_texture(tree, coords, image, scale):
    """Textura por projeção em caixa nas coordenadas de objeto; devolve o socket de cor."""
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = tuple(1.0 / s for s in scale)
    tree.links.new(coords, mapping.inputs["Vector"])
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    node.interpolation = "Closest"
    node.projection = "BOX"
    node.projection_blend = 0.0
    node.extension = "REPEAT"
    tree.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
    return node.outputs["Color"]


def _multiply(tree, color_a, color_b):
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    tree.links.new(color_a, mix.inputs[6])
    tree.links.new(color_b, mix.inputs[7])
    return mix.outputs[2]


def _new_material(name):
    mat = compat.new_material(name)
    return mat, mat.node_tree, compat.bsdf_of(mat)


def _mean_color(array):
    return tuple(float(v) for v in array.reshape(-1, 3).mean(axis=0))


def _finish_viewport(mat, color):
    """Cor de viewport (Workbench) igual à média da textura."""
    mat.diffuse_color = (*color, 1.0)


# --------------------------------------------------------------------------
# Construtores por tipo
# --------------------------------------------------------------------------
def _textured(name, spec):
    mat, tree, bsdf = _new_material(name)
    array = spec.make(texgen.rng_for(name))
    image = image_from_array(f"tex_{name}", array)
    coords = tree.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    color = _box_texture(tree, coords, image, (spec.tile, spec.tile, spec.tile_v or spec.tile))
    average = _mean_color(array)
    if spec.overlay:
        overlay_name, overlay_scale = spec.overlay
        maker = texgen.wall_grime_overlay if overlay_name == "ov_wall" else texgen.floor_grime_overlay
        grime = _texture_image(overlay_name, maker)
        color = _multiply(tree, color, _box_texture(tree, coords, grime, overlay_scale))
        average = tuple(c * 0.85 for c in average)
    tree.links.new(color, bsdf.inputs["Base Color"])
    compat.set_bsdf(bsdf, roughness=spec.roughness, specular=spec.specular)
    mat.use_backface_culling = spec.culled
    _finish_viewport(mat, average)
    return mat


def _basic(name):
    """Cor lisa da paleta com granulado sutil (ou sem, para materiais que devem ser puros)."""
    grain_kind, tile, roughness, metallic, specular = BASIC_LOOKS.get(name, ("grit", 0.5, 0.85, 0.0, 0.12))
    for prefix, kind in GRAIN_BY_PREFIX.items():
        if name.startswith(prefix):
            grain_kind = kind
    base = C.PALETTE[name]
    mat, tree, bsdf = _new_material(name)
    compat.set_bsdf(bsdf, base_color=base, roughness=roughness, metallic=metallic, specular=specular)
    if grain_kind:
        grain = _texture_image(f"tex_{grain_kind}", getattr(texgen, grain_kind))
        coords = tree.nodes.new("ShaderNodeTexCoord").outputs["Object"]
        grain_color = _box_texture(tree, coords, grain, (tile, tile, tile))
        tint_node = tree.nodes.new("ShaderNodeRGB")
        tint_node.outputs[0].default_value = (*base, 1.0)
        tree.links.new(_multiply(tree, tint_node.outputs[0], grain_color), bsdf.inputs["Base Color"])
    if name == "emit_white":
        compat.set_bsdf(bsdf, base_color=(1, 1, 1), emission=(1, 1, 1), emission_strength=4.0)
    _finish_viewport(mat, base)
    return mat


def _glass_night():
    mat, tree, bsdf = _new_material("glass_night")
    compat.set_bsdf(bsdf, base_color=(0.02, 0.03, 0.04), roughness=0.04, specular=0.9, alpha=0.3)
    _try_set(mat, "surface_render_method", "BLENDED")
    mat.use_backface_culling = False
    _finish_viewport(mat, (0.02, 0.03, 0.04))
    return mat


def _try_set(target, attribute, value):
    try:
        setattr(target, attribute, value)
    except (AttributeError, TypeError, ValueError):
        pass


def _garage_door_metal():
    """Chapa do portão; acima de GARAGE_DOOR_CLIP_Z fica transparente (some dentro do forro)."""
    mat, tree, bsdf = _new_material("door_garage_metal")
    array = texgen.garage_door_paint(texgen.rng_for("door_garage_metal"))
    image = image_from_array("tex_door_garage_metal", array)
    coords = tree.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    tree.links.new(_box_texture(tree, coords, image, (0.64, 0.64, 0.64)), bsdf.inputs["Base Color"])
    compat.set_bsdf(bsdf, roughness=0.55, specular=0.3, metallic=0.2)
    position = tree.nodes.new("ShaderNodeNewGeometry").outputs["Position"]
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(position, split.inputs["Vector"])
    above = tree.nodes.new("ShaderNodeMath")
    above.operation = "GREATER_THAN"
    above.inputs[1].default_value = GARAGE_DOOR_CLIP_Z
    tree.links.new(split.outputs["Z"], above.inputs[0])
    clear = tree.nodes.new("ShaderNodeBsdfTransparent")
    blend = tree.nodes.new("ShaderNodeMixShader")
    tree.links.new(above.outputs[0], blend.inputs[0])
    tree.links.new(bsdf.outputs["BSDF"], blend.inputs[1])
    tree.links.new(clear.outputs["BSDF"], blend.inputs[2])
    output = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    tree.links.new(blend.outputs["Shader"], output.inputs["Surface"])
    _finish_viewport(mat, _mean_color(array))
    return mat


def _fixture_glow():
    """Luminária: emissão lida da propriedade `sa_glow` do OBJETO, então um único material
    serve a todas as luminárias e o runtime apaga cada uma mudando só a propriedade."""
    mat, tree, bsdf = _new_material("fixture_glow")
    compat.set_bsdf(bsdf, base_color=(0.05, 0.045, 0.035), roughness=0.5)
    attribute = tree.nodes.new("ShaderNodeAttribute")
    attribute.attribute_type = "OBJECT"
    attribute.attribute_name = '["sa_glow"]'
    scale = tree.nodes.new("ShaderNodeMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = 5.0
    tree.links.new(attribute.outputs["Fac"], scale.inputs[0])
    emission_color = (1.0, 0.78, 0.5)
    compat.set_bsdf(bsdf, emission=emission_color)
    tree.links.new(scale.outputs[0], bsdf.inputs["Emission Strength"])
    _finish_viewport(mat, emission_color)
    return mat


def _sun_corona():
    """Coroa do Sol Negro: emissão que nasce na borda do disco e some com a distância, sobre um
    disco de raio 1 (a escala do objeto define o tamanho; as coordenadas de objeto ignoram escala)."""
    mat, tree, bsdf = _new_material("sun_corona")
    tree.nodes.remove(bsdf)
    coords = tree.nodes.new("ShaderNodeTexCoord")
    radius = tree.nodes.new("ShaderNodeVectorMath")
    radius.operation = "LENGTH"
    tree.links.new(coords.outputs["Object"], radius.inputs[0])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    elements = ramp.color_ramp.elements
    stops = [(0.0, 0.0), (0.55, 0.0), (0.585, 1.0), (0.605, 0.55), (0.66, 0.14), (0.8, 0.03), (1.0, 0.0)]
    while len(elements) < len(stops):
        elements.new(0.5)
    for element, (position, value) in zip(elements, stops):
        element.position = position
        element.color = (value, value, value, 1.0)
    tree.links.new(radius.outputs["Value"], ramp.inputs["Fac"])
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 0.72, 0.42, 1.0)
    emission.inputs["Strength"].default_value = 11.0
    clear = tree.nodes.new("ShaderNodeBsdfTransparent")
    blend = tree.nodes.new("ShaderNodeMixShader")
    tree.links.new(ramp.outputs["Color"], blend.inputs[0])
    tree.links.new(clear.outputs["BSDF"], blend.inputs[1])
    tree.links.new(emission.outputs["Emission"], blend.inputs[2])
    output = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    tree.links.new(blend.outputs["Shader"], output.inputs["Surface"])
    _try_set(mat, "surface_render_method", "BLENDED")
    _finish_viewport(mat, (1.0, 0.72, 0.42))
    return mat


def _flat(name, color, roughness=1.0, specular=0.0):
    mat, tree, bsdf = _new_material(name)
    compat.set_bsdf(bsdf, base_color=color, roughness=roughness, specular=specular)
    _finish_viewport(mat, color)
    return mat


def _special(name):
    builders = {
        "glass_night": _glass_night,
        "door_garage_metal": _garage_door_metal,
        "fixture_glow": _fixture_glow,
        "night_silhouette": lambda: _flat("night_silhouette", (0.006, 0.007, 0.009)),
        "sun_black": lambda: _flat("sun_black", (0.0, 0.0, 0.0)),
        "sun_corona": _sun_corona,
    }
    return builders[name]() if name in builders else None


# --------------------------------------------------------------------------
# API pública
# --------------------------------------------------------------------------
def build_material(name):
    """Material canônico `name` (cacheado por nome), ou None se o nome for desconhecido."""
    existing = bpy.data.materials.get(name)
    if existing is not None:
        return existing
    if name in SURFACES:
        return _textured(name, SURFACES[name])
    special = _special(name)
    if special is not None:
        return special
    if name in C.PALETTE:
        return _basic(name)
    return None


def material_for(name):
    """Como `build_material`, mas nunca devolve None: nome desconhecido é erro do chamador."""
    mat = build_material(name)
    if mat is None:
        raise KeyError(f"material desconhecido: {name}")
    return mat


def all_names():
    return tuple(C.MATERIAL_NAMES) + EXTRA_MATERIAL_NAMES
