"""Materiais dos cômodos de cima: textura de 256 a 512 px com filtro Linear, relevo, rugosidade variável.

Cada material é descrito por um `Surface` e montado como grafo de nós próprio:

    UV -> Mapping (escala e giro) -> Imagem -> [x tinta] -> [sujeira por ruído 3D] -> Base Color
                                       |-> brilho -> Map Range -> Roughness
                                       |-> brilho -> Bump -> Normal

O `scale` é em repetições por unidade de UV; os UVs do `MeshBuilder` já são em metros, então `scale=2` repete
a imagem a cada 0,5 m. Os nomes começam com `up_` (andar de cima) para não colidir com os de outros módulos.
"""
import math
from dataclasses import dataclass

from .. import compat
from . import materials, tex_papeis, tex_quartos, tex_tecidos, textures  # noqa: F401  (importar registra as texturas)

WHITE = (1.0, 1.0, 1.0)


@dataclass(frozen=True)
class Surface:
    texture: str = None
    color: tuple = (0.5, 0.5, 0.5)       # usado quando não há textura
    tint: tuple = WHITE                  # multiplica a textura (cor do pano, da tinta)
    scale: float = 1.0
    rotate: float = 0.0                  # graus; 90 faz o veio da madeira subir
    roughness: tuple = (0.7, 0.9)        # (mais liso, mais áspero): o brilho da textura escolhe
    metallic: float = 0.0
    relief: tuple = (0.4, 0.002)         # (força, altura em m do branco sobre o preto); None desliga
    dirt: float = 0.0                    # 0..1: manchas de sujeira em ruído 3D por cima
    dirt_color: tuple = (0.08, 0.07, 0.05)
    dust: float = 0.0                    # 0..1: poeira nas faces voltadas para cima (prateleiras, tampos), em manchas
    alpha: float = 1.0                   # < 1 deixa o material translúcido
    use_texture_alpha: bool = False      # decals e teias: o canal alfa da imagem recorta
    emission: float = 0.0
    sheen: float = 0.0


SURFACES = {}


def _paint(tint, **extra):
    return Surface("up_paint", tint=tint, scale=2.0, roughness=(0.50, 0.85), relief=(0.35, 0.0012), dust=0.35, **extra)


def _cloth(tint, texture="up_weave", **extra):
    settings = dict(texture=texture, tint=tint, scale=2.0, roughness=(0.88, 1.0), relief=(0.55, 0.0009), sheen=0.3, dirt=0.2)
    settings.update(extra)
    return Surface(**settings)


def _fur(tint):
    return Surface("up_fur", tint=tint, scale=3.0, roughness=(0.95, 1.0), relief=(0.8, 0.003), sheen=0.5, dirt=0.15)


SURFACES.update({
    # madeira (o sufixo _v gira a textura: veio vertical em pernas e montantes)
    "up_walnut": Surface("up_wood_dark", roughness=(0.32, 0.62), relief=(0.55, 0.0020), dust=0.5),
    "up_walnut_v": Surface("up_wood_dark", rotate=90, roughness=(0.32, 0.62), relief=(0.55, 0.0020), dust=0.5),
    "up_oak": Surface("up_wood_mid", roughness=(0.36, 0.66), relief=(0.55, 0.0020), dust=0.5),
    "up_oak_v": Surface("up_wood_mid", rotate=90, roughness=(0.36, 0.66), relief=(0.55, 0.0020), dust=0.5),
    "up_paint_cream": _paint((0.78, 0.70, 0.52)),
    "up_paint_cream_v": _paint((0.78, 0.70, 0.52), rotate=90),
    "up_paint_pink": _paint((0.72, 0.42, 0.50)),
    "up_paint_pink_v": _paint((0.72, 0.42, 0.50), rotate=90),
    "up_paint_white": _paint((0.70, 0.69, 0.64)),
    "up_paint_white_v": _paint((0.70, 0.69, 0.64), rotate=90),
    "up_paint_blue": _paint((0.22, 0.32, 0.50)),
    "up_paint_red": _paint((0.62, 0.12, 0.09)),
    "up_paint_green": _paint((0.15, 0.40, 0.19)),
    "up_paint_yellow": _paint((0.78, 0.66, 0.14)),
    # roupa de cama, tecidos, felpa
    "up_sheet": _cloth((0.88, 0.85, 0.76), dirt=0.28, dirt_color=(0.30, 0.22, 0.10)),
    "up_pillowcase": _cloth((0.84, 0.82, 0.73), dirt=0.30, dirt_color=(0.32, 0.24, 0.12)),
    "up_duvet": _cloth(WHITE, "up_tartan", dirt=0.22, scale=1.4),
    "up_comforter": _cloth(WHITE, "up_stars_fabric", scale=1.5, dirt=0.12),
    "up_cloth_dark": _cloth((0.12, 0.13, 0.16)),
    "up_cloth_beige": _cloth((0.52, 0.45, 0.34)),
    "up_cloth_gray": _cloth((0.28, 0.28, 0.30)),
    "up_cloth_red": _cloth((0.42, 0.10, 0.09)),
    "up_cloth_blue": _cloth((0.14, 0.20, 0.36)),
    "up_cloth_white": _cloth((0.80, 0.78, 0.70), dirt=0.3),
    "up_denim": _cloth((0.17, 0.25, 0.44), "up_twill"),
    "up_towel_green": Surface("up_terry", tint=(0.52, 0.60, 0.54), scale=3.0, roughness=(0.95, 1.0), relief=(0.9, 0.003), dirt=0.3),
    "up_towel_pink": Surface("up_terry", tint=(0.66, 0.46, 0.42), scale=3.0, roughness=(0.95, 1.0), relief=(0.9, 0.003), dirt=0.3),
    "up_lampshade_off": _cloth((0.62, 0.52, 0.36), dirt=0.3),
    "up_lampshade_lit": _cloth((0.62, 0.52, 0.36), emission=1.7, dirt=0.15, sheen=0.0),
    "up_fur_white": _fur((0.95, 0.92, 0.84)),
    "up_fur_brown": _fur((0.50, 0.32, 0.20)),
    "up_fur_pink": _fur((0.90, 0.48, 0.58)),
    "up_fur_yellow": _fur((0.96, 0.80, 0.34)),
    "up_fur_blue": _fur((0.38, 0.52, 0.80)),
    "up_fur_gray": _fur((0.52, 0.52, 0.54)),
    # tapetes
    "up_rug_persian": Surface("up_rug_persian", roughness=(0.95, 1.0), relief=(0.9, 0.004), sheen=0.2),
    "up_rug_kids": Surface("up_rug_kids", roughness=(0.95, 1.0), relief=(0.9, 0.004)),
    "up_rug_runner": Surface("up_rug_runner", roughness=(0.95, 1.0), relief=(0.9, 0.004)),
    "up_rug_cotton": Surface("up_rug_cotton", roughness=(0.95, 1.0), relief=(0.9, 0.004), scale=1.0),
    # duros
    "up_porcelain": Surface("up_porcelain", scale=1.5, roughness=(0.10, 0.34), relief=(0.12, 0.0004), dust=0.25),
    "up_ceramic": Surface("up_porcelain", tint=(1.15, 1.02, 0.80), scale=3.0, roughness=(0.14, 0.38), relief=(0.1, 0.0004)),
    "up_steel": Surface("up_steel", scale=1.5, roughness=(0.38, 0.62), relief=(0.35, 0.0008), metallic=0.25, dust=0.5),
    "up_wicker": Surface("up_wicker", scale=3.0, roughness=(0.65, 0.9), relief=(0.9, 0.003)),
    "up_leather": Surface("up_leather", scale=2.0, roughness=(0.38, 0.70), relief=(0.6, 0.0012), dust=0.3),
    "up_plastic_beige": Surface("up_plastic", tint=(0.62, 0.56, 0.42), scale=2.0, roughness=(0.38, 0.55), relief=(0.15, 0.0004)),
    "up_plastic_black": Surface("up_plastic", tint=(0.07, 0.07, 0.075), scale=2.0, roughness=(0.30, 0.50), relief=(0.15, 0.0004)),
    "up_plastic_gray": Surface("up_plastic", tint=(0.26, 0.26, 0.28), scale=2.0, roughness=(0.35, 0.55), relief=(0.15, 0.0004)),
    "up_plastic_white": Surface("up_plastic", tint=(0.66, 0.65, 0.60), scale=2.0, roughness=(0.30, 0.50), relief=(0.15, 0.0004)),
    "up_rubber_yellow": Surface(color=(0.62, 0.52, 0.07), roughness=(0.28, 0.28), relief=None),
    "up_wood_stem": Surface(color=(0.22, 0.15, 0.08), roughness=(0.9, 0.9), relief=None),
    "up_rug_study": Surface("up_rug_study", roughness=(0.95, 1.0), relief=(0.9, 0.004), sheen=0.2),
    "up_rubber": Surface(color=(0.035, 0.035, 0.04), roughness=(0.85, 0.85)),
    "up_water": Surface(color=(0.004, 0.011, 0.012), roughness=(0.02, 0.02), relief=None),
    "up_glass": Surface(color=(0.55, 0.60, 0.62), roughness=(0.04, 0.04), alpha=0.22, relief=None),
    "up_glass_amber": Surface(color=(0.30, 0.16, 0.04), roughness=(0.05, 0.05), alpha=0.55, relief=None),
    "up_pill_bottle": Surface(color=(0.62, 0.28, 0.04), roughness=(0.18, 0.18), alpha=0.88, relief=None),
    # papéis, livros, quadros, espelhos
    **{f"up_block_{letter}": Surface(f"up_block_{letter}", roughness=(0.45, 0.7), relief=(0.3, 0.0008)) for letter in "ema"},
    "up_globe": Surface("up_globe", roughness=(0.3, 0.5), relief=(0.2, 0.001)),
    "up_books": Surface("up_books", roughness=(0.55, 0.85), relief=(0.5, 0.0008)),
    "up_paper_policy": Surface("up_paper_policy", roughness=(0.85, 0.95), relief=(0.15, 0.0003)),
    "up_paper_report": Surface("up_paper_report", roughness=(0.85, 0.95), relief=(0.15, 0.0003)),
    "up_paper_notes": Surface("up_paper_notes", roughness=(0.85, 0.95), relief=(0.15, 0.0003)),
    "up_newsprint": Surface("up_newsprint", roughness=(0.9, 0.95), relief=(0.2, 0.0003)),
    "up_paper_blank": Surface(color=(0.70, 0.68, 0.58), roughness=(0.9, 0.9), relief=None),
    **{f"up_{kind}": Surface(f"up_{kind}", roughness=(0.45, 0.6), relief=(0.25, 0.0004))
       for kind in ("photo_trio", "photo_mother_child", "photo_father_child", "photo_portrait", "painting_lake",
                    "painting_barn", "painting_still", "wall_map", "calendar", "crayon_house", "crayon_family",
                    "crayon_rabbit")},
    "up_mirror_cracked": Surface("up_mirror_cracked", roughness=(0.04, 0.3), metallic=0.3, relief=(0.2, 0.0005)),
    "up_mirror_plain": Surface("up_mirror_plain", roughness=(0.05, 0.35), metallic=0.3, relief=None),
    "up_curtain_vinyl": Surface("up_curtain_vinyl", scale=1.0, roughness=(0.25, 0.5), relief=(0.2, 0.001), alpha=0.92),
    # decals com alfa
    "up_stain": Surface("up_stain", roughness=(0.35, 0.35), relief=None, use_texture_alpha=True),
    "up_damp": Surface("up_damp", roughness=(0.9, 0.9), relief=None, use_texture_alpha=True),
    "up_stain_ring": Surface("up_stain_ring", roughness=(0.4, 0.4), relief=None, use_texture_alpha=True),
    "up_handprints": Surface("up_handprints", roughness=(0.45, 0.45), relief=None, use_texture_alpha=True),
    "up_cobweb": Surface("up_cobweb", roughness=(0.9, 0.9), relief=None, use_texture_alpha=True),
    "up_glow_stars": Surface("up_glow_stars", roughness=(0.7, 0.7), relief=None, use_texture_alpha=True, emission=0.35),
})


# ---------------------------------------------------------------------------
# Construção do grafo de nós
# ---------------------------------------------------------------------------
def _socket(node, identifier, outputs=False):
    sockets = node.outputs if outputs else node.inputs
    return next(s for s in sockets if s.identifier == identifier)


def _mapped_image(mat, spec):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (spec.scale, spec.scale, spec.scale)
    mapping.inputs["Rotation"].default_value[2] = math.radians(spec.rotate)
    image = nodes.new("ShaderNodeTexImage")
    image.image = textures.image(spec.texture)
    image.interpolation = "Linear"
    image.extension = "REPEAT"
    links.new(coords.outputs["UV"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], image.inputs["Vector"])
    return image, coords


def _multiply(mat, base_socket, tint):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    _socket(mix, "Factor_Float").default_value = 1.0
    links.new(base_socket, _socket(mix, "A_Color"))
    _socket(mix, "B_Color").default_value = (*tint, 1.0)
    return _socket(mix, "Result_Color", outputs=True)


def _dirty(mat, color_socket, coords, spec):
    """Manchas de sujeira em ruído 3D (coordenada de objeto, em metros) por cima do albedo."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    noise_node = nodes.new("ShaderNodeTexNoise")
    noise_node.inputs["Scale"].default_value = 4.0
    noise_node.inputs["Detail"].default_value = 5.0
    ramp = nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.38
    ramp.inputs["From Max"].default_value = 0.72
    ramp.inputs["To Max"].default_value = spec.dirt
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    links.new(coords.outputs["Object"], noise_node.inputs["Vector"])
    links.new(noise_node.outputs["Fac"], ramp.inputs["Value"])
    links.new(ramp.outputs["Result"], _socket(mix, "Factor_Float"))
    links.new(color_socket, _socket(mix, "A_Color"))
    _socket(mix, "B_Color").default_value = (*spec.dirt_color, 1.0)
    return _socket(mix, "Result_Color", outputs=True)


def _dusty(mat, color_socket, coords, spec):
    """Poeira só nas faces que olham para cima (normal de mundo · Z), em manchas de ruído: tampos e prateleiras."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    geometry = nodes.new("ShaderNodeNewGeometry")
    facing_up = nodes.new("ShaderNodeVectorMath")
    facing_up.operation = "DOT_PRODUCT"
    facing_up.inputs[1].default_value = (0.0, 0.0, 1.0)
    top_only = nodes.new("ShaderNodeMapRange")
    top_only.inputs["From Min"].default_value = 0.75
    top_only.inputs["From Max"].default_value = 0.98
    patches = nodes.new("ShaderNodeTexNoise")
    patches.inputs["Scale"].default_value = 14.0
    patches.inputs["Detail"].default_value = 4.0
    patchy = nodes.new("ShaderNodeMapRange")
    patchy.inputs["From Min"].default_value = 0.30
    patchy.inputs["From Max"].default_value = 0.70
    patchy.inputs["To Min"].default_value = 0.25
    amount = nodes.new("ShaderNodeMath")
    amount.operation = "MULTIPLY"
    scaled = nodes.new("ShaderNodeMath")
    scaled.operation = "MULTIPLY"
    scaled.inputs[1].default_value = spec.dust
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    links.new(geometry.outputs["Normal"], facing_up.inputs[0])
    links.new(facing_up.outputs["Value"], top_only.inputs["Value"])
    links.new(coords.outputs["Object"], patches.inputs["Vector"])
    links.new(patches.outputs["Fac"], patchy.inputs["Value"])
    links.new(top_only.outputs["Result"], amount.inputs[0])
    links.new(patchy.outputs["Result"], amount.inputs[1])
    links.new(amount.outputs["Value"], scaled.inputs[0])
    links.new(scaled.outputs["Value"], _socket(mix, "Factor_Float"))
    links.new(color_socket, _socket(mix, "A_Color"))
    _socket(mix, "B_Color").default_value = (0.36, 0.34, 0.30, 1.0)
    return _socket(mix, "Result_Color", outputs=True)


def _roughness_from_brightness(mat, bsdf, image_color, spec):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    gray = nodes.new("ShaderNodeRGBToBW")
    ramp = nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = spec.roughness[1]      # escuro: áspero
    ramp.inputs["To Max"].default_value = spec.roughness[0]      # claro: gasto e liso
    links.new(image_color, gray.inputs["Color"])
    links.new(gray.outputs["Val"], ramp.inputs["Value"])
    links.new(ramp.outputs["Result"], bsdf.inputs["Roughness"])


def build_surface(name, spec):
    """Material `name` com os nós descritos por `spec`."""
    mat = compat.new_material(name)
    links = mat.node_tree.links
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, base_color=spec.color, roughness=sum(spec.roughness) / 2, metallic=spec.metallic,
                    specular=0.35 if spec.metallic == 0 else 0.5)
    if spec.texture:
        image, coords = _mapped_image(mat, spec)
        color = image.outputs["Color"]
        if spec.tint != WHITE:
            color = _multiply(mat, color, spec.tint)
        if spec.dirt > 0:
            color = _dirty(mat, color, coords, spec)
        if spec.dust > 0:
            color = _dusty(mat, color, coords, spec)
        links.new(color, bsdf.inputs["Base Color"])
        if spec.roughness[0] != spec.roughness[1]:
            _roughness_from_brightness(mat, bsdf, image.outputs["Color"], spec)
        if spec.relief:
            compat.add_relief(mat, image.outputs["Color"], *spec.relief)
        if spec.emission:
            links.new(color, bsdf.inputs["Emission Color"])
            compat.set_bsdf(bsdf, emission_strength=spec.emission)
        if spec.use_texture_alpha:
            links.new(image.outputs["Alpha"], bsdf.inputs["Alpha"])
    elif spec.emission:
        compat.set_bsdf(bsdf, emission=spec.color, emission_strength=spec.emission)
    if spec.sheen and "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = spec.sheen
    if spec.alpha < 1.0:
        compat.set_bsdf(bsdf, alpha=spec.alpha)
    if (spec.alpha < 1.0 or spec.use_texture_alpha) and hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    mat.diffuse_color = (*spec.color, 1.0)
    return mat


def register_all():
    for name, spec in SURFACES.items():
        materials.register_builder(name, lambda name=name, spec=spec: build_surface(name, spec))


register_all()
