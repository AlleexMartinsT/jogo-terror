"""Materiais procedurais da casa e do exterior (`build_material` atende `conventions.MATERIAL_NAMES`).

Decisões que valem saber:
- As texturas são geradas em numpy (`tex_*`), empacotadas no .blend e lidas com interpolação Linear. Cada
  superfície traz DUAS imagens: a cor (sRGB) e uma imagem de dados com altura (R), rugosidade (G) e opacidade
  (B). A altura vira Bump e a rugosidade varia pixel a pixel (gordura, desgaste, verniz).
- O mapeamento padrão é por caixa nas coordenadas de OBJETO, não por UV. Assim qualquer malha (as minhas, as
  de props feitas com bmesh sem UV) recebe textura sem esticar, na mesma densidade de texels por metro em
  todas as superfícies. Pisos de tábuas individuais usam UV (cada tábua sorteia um recorte do veio).
- Paredes e pisos multiplicam uma segunda camada de sujeira grande (8 m), que quebra a repetição do padrão
  curto e coloca a sujeira onde ela aparece na vida real (rente ao piso, no teto).
- Para registrar um material novo sem editar este arquivo: `SURFACES[nome] = Surface(...)`,
  `SIMPLE[nome] = Simple(...)` ou `BUILDERS[nome] = função`.
"""
from dataclasses import dataclass
from typing import Callable, Optional

import bpy
import numpy as np

from .. import compat
from .. import conventions as C
from . import tex_decals, tex_doors, tex_exterior, tex_floors, tex_interior, texgen

WALL_OVERLAY = ("ov_wall", (8.0, 8.0, 2.8))     # 8 m de largura por 2,8 m (um pé-direito)
FLOOR_OVERLAY = ("ov_floor", (8.0, 8.0, 8.0))
CEILING_OVERLAY = ("ov_ceiling", (8.0, 8.0, 8.0))
GARAGE_DOOR_CLIP_Z = 2.85                        # acima disso o portão aberto some (entra no forro)
STAIR_RISE = 2.8 / 15                            # altura de cada espelho (layout.STAIRS.rise)

FOG_MATERIAL = "fog_dust"
FOG_NODE = "SA_Fog"
FOG_COLOR = (0.55, 0.60, 0.68, 1.0)
FOG_ANISOTROPY = 0.35

OVERLAY_MAKERS = {
    "ov_wall": tex_interior.wall_grime_overlay,
    "ov_floor": tex_interior.floor_grime_overlay,
    "ov_ceiling": tex_interior.ceiling_grime_overlay,
}


@dataclass(frozen=True)
class Surface:
    """Como uma superfície texturizada é montada."""
    make: Callable                      # rng -> texgen.Maps (ou só a matriz de cor, no formato antigo)
    tile: float                         # metros por repetição em X (e em Y, se `tile_y` faltar)
    tile_v: Optional[float] = None      # metros por repetição em Z (padrão: igual a `tile`)
    tile_y: Optional[float] = None      # metros por repetição em Y (padrão: igual a `tile`)
    roughness: float = 0.9              # vale quando a textura não traz rugosidade
    specular: float = 0.15
    overlay: Optional[tuple] = None
    culled: bool = False
    bump: float = 0.7                   # força do Bump
    distance: float = 0.004             # metros entre o preto e o branco do mapa de altura
    coords: str = "object"              # 'object' (caixa) | 'uv'
    offset: tuple = (0.0, 0.0, 0.0)     # deslocamento da textura, em unidades de repetição
    render: str = ""                    # 'BLENDED' | 'DITHERED' para materiais com opacidade
    back: Optional[tuple] = None        # cor do verso (papel de parede descolado mostra o avesso claro)
    images: str = ""                    # reaproveita as imagens de outro material (mesma textura, outro uso)


@dataclass(frozen=True)
class Simple:
    """Material liso com variação procedural leve (latão, plástico, aço): sem imagem."""
    color: tuple
    roughness: float = 0.5
    metallic: float = 0.0
    specular: float = 0.4
    variation: float = 0.25             # quanto o ruído escurece/clareia a cor
    scale: float = 90.0                 # frequência do ruído (1/m)
    bump: float = 0.15


def _tex_planks_light(rng):
    return tex_floors.wood_planks(rng)


SURFACES = {
    "wall_wallpaper": Surface(tex_interior.wallpaper, 1.06, specular=0.1, overlay=WALL_OVERLAY, bump=0.8,
                              distance=0.0016),
    "wall_paint_dirty": Surface(tex_interior.paint_dirty, 1.0, specular=0.2, overlay=WALL_OVERLAY, bump=0.9,
                                distance=0.0035),
    "wall_tile_bath": Surface(tex_interior.bathroom_wall_tile, 1.2, specular=0.55, overlay=WALL_OVERLAY, bump=1.0,
                              distance=0.0045),
    "wall_garage": Surface(tex_interior.garage_block, 1.6, specular=0.1, overlay=WALL_OVERLAY, bump=1.0,
                           distance=0.007),
    "wall_brick_ext": Surface(tex_exterior.brick, 0.96, specular=0.05, bump=1.0, distance=0.007),
    "wall_siding_ext": Surface(tex_exterior.clapboard, 0.64, specular=0.1, overlay=WALL_OVERLAY, bump=1.0,
                               distance=0.010),
    "floor_wood": Surface(tex_floors.wood_planks, 2.0, tile_y=0.5, specular=0.3, overlay=FLOOR_OVERLAY, bump=0.7,
                          distance=0.0014, coords="uv"),
    "floor_wood_dark": Surface(tex_floors.wood_planks_dark, 2.0, tile_y=0.5, specular=0.3, overlay=FLOOR_OVERLAY,
                               bump=0.7, distance=0.0014, coords="uv"),
    "floor_carpet": Surface(tex_floors.carpet, 0.5, specular=0.0, overlay=FLOOR_OVERLAY, bump=0.9, distance=0.007),
    "floor_linoleum": Surface(tex_floors.linoleum, 1.0, specular=0.4, overlay=FLOOR_OVERLAY, bump=0.9,
                              distance=0.0035),
    "floor_tile_bath": Surface(tex_floors.bathroom_floor_tile, 1.0, specular=0.5, overlay=FLOOR_OVERLAY, bump=1.0,
                               distance=0.004),
    "floor_concrete": Surface(tex_floors.concrete, 2.0, specular=0.12, overlay=FLOOR_OVERLAY, bump=0.9,
                              distance=0.006),
    "ceiling": Surface(tex_interior.ceiling_plaster, 1.0, specular=0.0, overlay=CEILING_OVERLAY, culled=True,
                       bump=1.0, distance=0.003),
    "roof_shingle": Surface(tex_exterior.shingles, 0.96, specular=0.05, bump=1.0, distance=0.008),
    "door_wood": Surface(tex_doors.door_stained, 0.9, 2.05, specular=0.3, bump=0.9, distance=0.0018),
    "door_front": Surface(tex_doors.door_front_stained, 0.9, 2.05, specular=0.35, bump=0.9, distance=0.0018),
    "door_paint": Surface(tex_doors.door_painted_cream_a, 0.9, 2.05, specular=0.25, bump=0.9, distance=0.0018),
    "door_paint_b": Surface(tex_doors.door_painted_cream_b, 0.9, 2.05, specular=0.25, bump=0.9, distance=0.0018),
    "door_kids": Surface(tex_doors.door_kids_painted, 0.9, 2.05, specular=0.25, bump=0.9, distance=0.0018),
    "door_back": Surface(tex_doors.door_back_painted, 0.9, 2.05, specular=0.25, bump=0.9, distance=0.0018),
    "door_steel": Surface(tex_doors.door_steel, 0.9, 2.05, specular=0.4, bump=0.8, distance=0.0025),
    "trim_white": Surface(tex_interior.trim_paint, 0.64, specular=0.2, overlay=WALL_OVERLAY, bump=0.8,
                          distance=0.0014),
    "stairs_wood": Surface(tex_floors.wood_stairs, 1.2, tile_y=0.3, tile_v=0.3, specular=0.35, overlay=FLOOR_OVERLAY,
                           bump=0.7, distance=0.0016, offset=(0.0, -0.6667, 0.0)),
    "stairs_riser": Surface(tex_floors.stairs_riser, 1.2, tile_y=0.3, tile_v=STAIR_RISE, specular=0.2, bump=0.8,
                            distance=0.0016),
    "carpet_runner": Surface(tex_floors.carpet_runner, 0.7, tile_y=4.9, specular=0.0, bump=1.0, distance=0.006,
                             coords="uv"),
    "curtain": Surface(tex_interior.curtain_fabric, 0.64, specular=0.0, bump=0.9, distance=0.003),
    "curtain_green": Surface(lambda rng: tex_interior.curtain_fabric(rng, base=(0.085, 0.115, 0.082)), 0.64,
                             specular=0.0, bump=0.9, distance=0.003),
    "curtain_kids": Surface(lambda rng: tex_interior.curtain_fabric(rng, base=(0.30, 0.255, 0.13)), 0.64,
                            specular=0.0, bump=0.9, distance=0.003),
    "window_glass": Surface(tex_doors.window_glass, 0.64, specular=0.6, render="BLENDED", bump=0.2, distance=0.0005),
    "frosted_glass": Surface(tex_doors.frosted_glass, 0.64, specular=0.3, render="BLENDED", bump=0.3,
                             distance=0.0008),
    "screen_mesh": Surface(tex_doors.screen_mesh, 0.05, specular=0.2, render="DITHERED", bump=0.2, distance=0.001),
    "wall_peel": Surface(tex_interior.wallpaper, 1.06, specular=0.1, overlay=WALL_OVERLAY, bump=0.8, distance=0.0016,
                         back=(0.46, 0.44, 0.37), images="wall_wallpaper"),
    "decal_plaster": Surface(tex_decals.plaster_patch, 1.0, coords="uv", render="BLENDED", bump=1.0, distance=0.004),
    "decal_mold": Surface(tex_decals.mold_blotch, 1.0, coords="uv", render="BLENDED", bump=0.0),
    "decal_crack": Surface(tex_decals.wall_crack, 1.0, coords="uv", render="BLENDED", bump=1.0, distance=0.004),
    "decal_damp": Surface(tex_decals.damp_stain, 1.0, coords="uv", render="BLENDED", bump=0.0),
    "decal_cobweb": Surface(tex_decals.cobweb, 1.0, coords="uv", render="DITHERED", bump=0.0),
    "decal_ghost": Surface(tex_decals.picture_ghost, 1.0, coords="uv", render="BLENDED", bump=0.0),
    "decal_height": Surface(tex_decals.height_marks, 1.0, coords="uv", render="BLENDED", bump=0.0),
    "decal_mouse": Surface(tex_decals.mouse_hole, 1.0, coords="uv", render="BLENDED", bump=0.0),
    "decal_drip": Surface(tex_decals.drip_streaks, 1.0, coords="uv", render="BLENDED", bump=0.0),
    "decal_soot": Surface(tex_decals.soot_halo, 1.0, coords="uv", render="BLENDED", bump=0.0),
    "decal_dirt": Surface(tex_decals.dirt_halo, 1.0, coords="uv", render="BLENDED", bump=0.0),
    "asphalt": Surface(tex_exterior.asphalt, 3.0, specular=0.05, bump=1.0, distance=0.012),
    "road_paint": Surface(tex_exterior.road_paint, 0.64, specular=0.05, bump=0.6, distance=0.002),
    "grass_dead": Surface(tex_exterior.dead_grass, 2.0, specular=0.0, bump=0.8, distance=0.02),
    "sidewalk": Surface(tex_exterior.sidewalk, 1.5, specular=0.08, bump=0.9, distance=0.006),
    "bark": Surface(tex_exterior.bark, 0.5, specular=0.0, bump=1.0, distance=0.02),
    "fence_wood": Surface(tex_exterior.picket_paint, 0.64, specular=0.05, bump=0.9, distance=0.003),
}

# Peças de ferragem, plástico e metal (sem imagem): cor, rugosidade, metálico.
SIMPLE = {
    "brass_worn": Simple((0.40, 0.29, 0.10), 0.34, 0.95, 0.5, variation=0.35, scale=140.0),
    "steel_hardware": Simple((0.30, 0.30, 0.31), 0.42, 0.9, 0.5, variation=0.3, scale=160.0),
    "iron_black": Simple((0.045, 0.045, 0.05), 0.55, 0.8, 0.4, variation=0.2, scale=80.0),
    "plastic_ivory": Simple((0.42, 0.40, 0.32), 0.45, 0.0, 0.4, variation=0.15, scale=60.0),
    "plastic_white_aged": Simple((0.40, 0.385, 0.34), 0.5, 0.0, 0.35, variation=0.18, scale=45.0),
    "plastic_black": Simple((0.03, 0.03, 0.032), 0.4, 0.0, 0.4, variation=0.1, scale=70.0),
    "painted_metal": Simple((0.20, 0.205, 0.195), 0.55, 0.5, 0.35, variation=0.3, scale=35.0),
    "blinds_plastic": Simple((0.40, 0.375, 0.30), 0.5, 0.0, 0.35, variation=0.25, scale=40.0),
    "fixture_metal": Simple((0.33, 0.32, 0.30), 0.38, 0.85, 0.5, variation=0.3, scale=100.0),
    "rope_cotton": Simple((0.30, 0.27, 0.20), 0.95, 0.0, 0.1, variation=0.3, scale=200.0),
    "tape_gray": Simple((0.30, 0.30, 0.28), 0.55, 0.0, 0.2, variation=0.2, scale=30.0),
    "milk_glass_dead": Simple((0.30, 0.29, 0.235), 0.28, 0.0, 0.45, variation=0.18, scale=18.0, bump=0.05),
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
GRAIN_BUMP = {"grit": 0.003, "wood_grain": 0.0015, "fabric_weave": 0.002}

# Materiais com construtor próprio (nós sob medida). Outros módulos registram aqui os seus.
BUILDERS = {}


def register_builder(name, build):
    BUILDERS[name] = build


# --------------------------------------------------------------------------
# Imagens
# --------------------------------------------------------------------------
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


def channel_image(name, maps):
    """Imagem de canais (Non-Color): R = altura, G = rugosidade, B = opacidade. Devolve None sem nenhum dos três."""
    if maps.height is None and maps.rough is None and maps.alpha is None:
        return None
    existing = bpy.data.images.get(name)
    if existing is not None:
        return existing
    height, width, _ = maps.color.shape
    pixels = np.ones((height, width, 4), np.float32)
    pixels[..., 0] = 0.5 if maps.height is None else maps.height
    pixels[..., 1] = 0.8 if maps.rough is None else maps.rough
    pixels[..., 2] = 1.0 if maps.alpha is None else maps.alpha
    image = bpy.data.images.new(name, width, height, alpha=False)
    image.pixels.foreach_set(pixels.ravel())
    image.pack()
    image.colorspace_settings.name = "Non-Color"
    image["sa_channels"] = "".join(c for c, field in (("h", maps.height), ("r", maps.rough), ("a", maps.alpha))
                                   if field is not None)
    return image


def as_maps(made):
    """Aceita o formato antigo (só a matriz de cor) e o novo (`texgen.Maps`)."""
    return made if isinstance(made, texgen.Maps) else texgen.Maps(made)


def _overlay_image(name):
    existing = bpy.data.images.get(name)
    if existing is not None:
        return existing
    return image_from_array(name, OVERLAY_MAKERS[name](texgen.rng_for(name)))


# --------------------------------------------------------------------------
# Nós
# --------------------------------------------------------------------------
def _coordinates(tree, spec):
    node = tree.nodes.new("ShaderNodeTexCoord")
    return node.outputs["UV" if spec.coords == "uv" else "Object"]


def _mapping(tree, coords, scale, offset=(0.0, 0.0, 0.0)):
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = tuple(1.0 / s for s in scale)
    mapping.inputs["Location"].default_value = offset
    tree.links.new(coords, mapping.inputs["Vector"])
    return mapping.outputs["Vector"]


def _image_node(tree, vector, image, box=True):
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    node.interpolation = "Linear"
    node.extension = "REPEAT"
    if box:
        node.projection = "BOX"
        node.projection_blend = 0.0
    tree.links.new(vector, node.inputs["Vector"])
    return node


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


def _try_set(target, attribute, value):
    try:
        setattr(target, attribute, value)
    except (AttributeError, TypeError, ValueError):
        pass


def _wire_channels(tree, bsdf, channels_node, spec, has_height, has_rough, has_alpha):
    """Liga a imagem de dados: R altura -> Bump -> Normal, G -> Rugosidade, B -> Alfa."""
    split = tree.nodes.new("ShaderNodeSeparateColor")
    tree.links.new(channels_node.outputs["Color"], split.inputs["Color"])
    if has_height:
        bump = tree.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = spec.bump
        bump.inputs["Distance"].default_value = spec.distance
        tree.links.new(split.outputs["Red"], bump.inputs["Height"])
        tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if has_rough:
        tree.links.new(split.outputs["Green"], bsdf.inputs["Roughness"])
    if has_alpha:
        tree.links.new(split.outputs["Blue"], bsdf.inputs["Alpha"])


# --------------------------------------------------------------------------
# Construtores por tipo
# --------------------------------------------------------------------------
def _surface_images(name, spec):
    """(imagem de cor, imagem de dados, canais reais, cor média). Gera uma vez e reaproveita pelo nome."""
    key = spec.images or name
    color_image = bpy.data.images.get(f"tex_{key}")
    if color_image is None:
        maps = as_maps(spec.make(texgen.rng_for(key)))
        color_image = image_from_array(f"tex_{key}", maps.color)
        color_image["sa_average"] = _mean_color(maps.color)
        if channel_image(f"tex_{key}_channels", maps) is None:
            color_image["sa_channels"] = ""
    channels_image = bpy.data.images.get(f"tex_{key}_channels")
    channels = channels_image.get("sa_channels", "") if channels_image is not None else ""
    return color_image, channels_image, channels, tuple(color_image["sa_average"])


def _textured(name, spec):
    mat, tree, bsdf = _new_material(name)
    color_image, channels_image, channels, average = _surface_images(name, spec)
    box = spec.coords != "uv"
    scale = (spec.tile, spec.tile_y or spec.tile, spec.tile_v or spec.tile)
    if not box:
        scale = (spec.tile, spec.tile_y or spec.tile, 1.0)
    coords = _coordinates(tree, spec)
    vector = _mapping(tree, coords, scale, spec.offset)
    color = _image_node(tree, vector, color_image, box).outputs["Color"]
    if spec.back:
        color = _paper_back(tree, color, spec.back)
    if spec.overlay:
        overlay_name, overlay_scale = spec.overlay
        overlay_coords = tree.nodes.new("ShaderNodeTexCoord").outputs["Object"]
        grime = _image_node(tree, _mapping(tree, overlay_coords, overlay_scale), _overlay_image(overlay_name))
        color = _multiply(tree, color, grime.outputs["Color"])
        average = tuple(c * 0.85 for c in average)
    tree.links.new(color, bsdf.inputs["Base Color"])
    compat.set_bsdf(bsdf, roughness=spec.roughness, specular=spec.specular)
    has_alpha = "a" in channels
    if channels_image is not None:
        _wire_channels(tree, bsdf, _image_node(tree, vector, channels_image, box), spec, "h" in channels,
                       "r" in channels, has_alpha)
    else:
        compat.add_relief(mat, color, spec.bump * 0.5, spec.distance)
    if has_alpha:
        _try_set(mat, "surface_render_method", spec.render or "BLENDED")
        _try_set(mat, "use_transparent_shadow", True)
        mat.use_backface_culling = False
    else:
        mat.use_backface_culling = spec.culled
    _finish_viewport(mat, average)
    return mat


def _paper_back(tree, front, back_color):
    """Mistura a cor da frente com a do verso conforme a face vista: papel descolado mostra o avesso."""
    geometry = tree.nodes.new("ShaderNodeNewGeometry")
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MIX"
    tree.links.new(geometry.outputs["Backfacing"], mix.inputs[0])
    tree.links.new(front, mix.inputs[6])
    mix.inputs[7].default_value = (*back_color, 1.0)
    return mix.outputs[2]


def _simple(name, spec):
    """Metal ou plástico com ruído procedural: a cor e a rugosidade oscilam, o relevo é quase nulo."""
    mat, tree, bsdf = _new_material(name)
    compat.set_bsdf(bsdf, base_color=spec.color, roughness=spec.roughness, metallic=spec.metallic,
                    specular=spec.specular)
    coords = tree.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = spec.scale
    noise.inputs["Detail"].default_value = 6.0
    tree.links.new(coords, noise.inputs["Vector"])
    tone = tree.nodes.new("ShaderNodeMapRange")
    tone.inputs["From Min"].default_value = 0.3
    tone.inputs["From Max"].default_value = 0.7
    tone.inputs["To Min"].default_value = 1.0 - spec.variation
    tone.inputs["To Max"].default_value = 1.0 + spec.variation * 0.5
    tree.links.new(noise.outputs["Fac"], tone.inputs["Value"])
    base = tree.nodes.new("ShaderNodeRGB")
    base.outputs[0].default_value = (*spec.color, 1.0)
    scaled = tree.nodes.new("ShaderNodeMix")
    scaled.data_type = "RGBA"
    scaled.blend_type = "MULTIPLY"
    scaled.inputs[0].default_value = 1.0
    tree.links.new(base.outputs[0], scaled.inputs[6])
    tree.links.new(tone.outputs["Result"], scaled.inputs[7])
    tree.links.new(scaled.outputs[2], bsdf.inputs["Base Color"])
    rough = tree.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = max(0.05, spec.roughness - 0.15)
    rough.inputs["To Max"].default_value = min(1.0, spec.roughness + 0.25)
    tree.links.new(noise.outputs["Fac"], rough.inputs["Value"])
    tree.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = spec.bump
    bump.inputs["Distance"].default_value = 0.0008
    tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    _finish_viewport(mat, spec.color)
    return mat


def _basic(name):
    """Cor lisa da paleta com granulado sutil e relevo (ou sem, para materiais que devem ser puros)."""
    grain_kind, tile, roughness, metallic, specular = BASIC_LOOKS.get(name, ("grit", 0.5, 0.85, 0.0, 0.12))
    for prefix, kind in GRAIN_BY_PREFIX.items():
        if name.startswith(prefix):
            grain_kind = kind
    base = C.PALETTE[name]
    mat, tree, bsdf = _new_material(name)
    compat.set_bsdf(bsdf, base_color=base, roughness=roughness, metallic=metallic, specular=specular)
    if grain_kind:
        maps = as_maps(getattr(tex_exterior, grain_kind)(texgen.rng_for(f"tex_{grain_kind}")))
        image = image_from_array(f"tex_{grain_kind}", maps.color)
        coords = tree.nodes.new("ShaderNodeTexCoord").outputs["Object"]
        vector = _mapping(tree, coords, (tile, tile, tile))
        grain_color = _image_node(tree, vector, image).outputs["Color"]
        tint_node = tree.nodes.new("ShaderNodeRGB")
        tint_node.outputs[0].default_value = (*base, 1.0)
        tree.links.new(_multiply(tree, tint_node.outputs[0], grain_color), bsdf.inputs["Base Color"])
        packed = channel_image(f"tex_{grain_kind}_channels", maps)
        if packed is not None:
            bump_spec = Surface(None, tile, bump=0.5, distance=GRAIN_BUMP.get(grain_kind, 0.002))
            _wire_channels(tree, bsdf, _image_node(tree, vector, packed), bump_spec, maps.height is not None, False,
                           False)
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


def _garage_door_metal():
    """Chapa do portão; acima de GARAGE_DOOR_CLIP_Z fica transparente (some dentro do forro)."""
    mat, tree, bsdf = _new_material("door_garage_metal")
    maps = as_maps(tex_exterior.garage_door_paint(texgen.rng_for("door_garage_metal")))
    image = image_from_array("tex_door_garage_metal", maps.color)
    coords = tree.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    vector = _mapping(tree, coords, (0.64, 0.64, 0.64))
    tree.links.new(_image_node(tree, vector, image).outputs["Color"], bsdf.inputs["Base Color"])
    compat.set_bsdf(bsdf, roughness=0.55, specular=0.3, metallic=0.2)
    packed = channel_image("tex_door_garage_metal_channels", maps)
    if packed is not None:
        spec = Surface(None, 0.64, bump=0.7, distance=0.003)
        _wire_channels(tree, bsdf, _image_node(tree, vector, packed), spec, True, True, False)
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
    _finish_viewport(mat, _mean_color(maps.color))
    return mat


def _glow_material(name, base_color, emission_color, strength):
    """Luminária: emissão lida da propriedade `sa_glow` do OBJETO, então um único material
    serve a todas as luminárias e o runtime apaga cada uma mudando só a propriedade."""
    mat, tree, bsdf = _new_material(name)
    compat.set_bsdf(bsdf, base_color=base_color, roughness=0.5)
    attribute = tree.nodes.new("ShaderNodeAttribute")
    attribute.attribute_type = "OBJECT"
    attribute.attribute_name = '["sa_glow"]'
    scale = tree.nodes.new("ShaderNodeMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = strength
    tree.links.new(attribute.outputs["Fac"], scale.inputs[0])
    compat.set_bsdf(bsdf, emission=emission_color)
    tree.links.new(scale.outputs[0], bsdf.inputs["Emission Strength"])
    _finish_viewport(mat, emission_color)
    return mat


def _fixture_glow():
    return _glow_material("fixture_glow", (0.05, 0.045, 0.035), (1.0, 0.78, 0.5), 5.0)


def _fixture_milk_glass():
    """Vidro leitoso de plafon: a mesma emissão controlada por `sa_glow`, mais amarelada."""
    return _glow_material("fixture_milk_glass", (0.30, 0.28, 0.22), (1.0, 0.80, 0.55), 4.2)


def _fixture_tube():
    """Tubo fluorescente: luz fria."""
    return _glow_material("fixture_tube", (0.55, 0.60, 0.62), (0.82, 0.93, 1.0), 6.0)


def _led_smoke_red():
    """LED vermelho do detector de fumaça: pequeno e sempre aceso."""
    mat, tree, bsdf = _new_material("led_smoke_red")
    compat.set_bsdf(bsdf, base_color=(0.3, 0.0, 0.0), roughness=0.4, emission=(1.0, 0.04, 0.02),
                    emission_strength=3.0)
    _finish_viewport(mat, (1.0, 0.04, 0.02))
    return mat


def _fog_dust():
    """Neblina de poeira: Volume Scatter num material só de volume (sem superfície)."""
    mat, tree, bsdf = _new_material(FOG_MATERIAL)
    tree.nodes.remove(bsdf)
    fog = tree.nodes.new("ShaderNodeVolumeScatter")
    fog.name = FOG_NODE
    fog.inputs["Color"].default_value = FOG_COLOR
    fog.inputs["Density"].default_value = 0.0
    fog.inputs["Anisotropy"].default_value = FOG_ANISOTROPY
    output = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    tree.links.new(fog.outputs["Volume"], output.inputs["Volume"])
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
        "fixture_milk_glass": _fixture_milk_glass,
        "fixture_tube": _fixture_tube,
        "led_smoke_red": _led_smoke_red,
        "night_silhouette": lambda: _flat("night_silhouette", (0.006, 0.007, 0.009)),
        "sun_black": lambda: _flat("sun_black", (0.0, 0.0, 0.0)),
        "sun_corona": _sun_corona,
        "fog_dust": _fog_dust,
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
    if name in BUILDERS:
        return BUILDERS[name]()
    if name in SURFACES:
        return _textured(name, SURFACES[name])
    if name in SIMPLE:
        return _simple(name, SIMPLE[name])
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


SPECIAL_NAMES = ("fog_dust", "door_garage_metal", "fixture_glow", "fixture_milk_glass", "fixture_tube",
                 "led_smoke_red", "night_silhouette",
                 "sun_black", "sun_corona")


def all_names():
    """Todos os nomes que `build_material` atende: canônicos do contrato mais os extras da casca."""
    registered = set(SURFACES) | set(SIMPLE) | set(BUILDERS) | set(SPECIAL_NAMES) | {"glass_night"}
    extras = registered - set(C.MATERIAL_NAMES)
    return tuple(C.MATERIAL_NAMES) + tuple(sorted(extras))
