"""Materiais da cozinha e da garagem: textura filtrada, relevo, rugosidade que varia e marcas de uso.

Todo material de superfície (`SURFACES`) liga os mesmos quatro sinais, tirados de uma imagem RGBA em que o
alfa é a altura (ver `tex_cozinha_garagem`):

* cor: a própria imagem, escurecida pela sujeira e clareada nas quinas gastas;
* rugosidade: a altura remapeada entre dois valores (riscos e poros mudam o brilho);
* relevo: a altura num nó Bump, que a lanterna rasante transforma em veio, poro e arranhão;
* marcas de uso por objeto: o atributo de vértice `sa_wear` gravado por `kg_shapes.paint_wear`
  (R quina gasta, G sujeira que sobe do chão). Sem o atributo o material se comporta como sem desgaste.

Importar este módulo registra texturas e materiais; `kg_shapes` o importa, então qualquer peça montada com
`Assembly` já encontra os nomes `kg_*`.
"""
from collections import namedtuple
from functools import partial

from .. import compat
from . import materials, tex_cozinha_garagem, tex_cozinha_papeis, textures

Surface = namedtuple("Surface", "texture roughness metallic bump distance specular grime edge_color viewport",
                     defaults=(None, (0.5, 0.8), 0.0, 0.3, 0.003, 0.4, 0.6, None, (0.4, 0.4, 0.4)))

GRIME_COLOR = (0.30, 0.26, 0.20, 1.0)

SURFACES = {
    "kg_oak": Surface("kg_oak", (0.50, 0.78), bump=0.30, distance=0.0028, grime=0.8, edge_color=(0.46, 0.32, 0.18),
                      viewport=(0.28, 0.17, 0.09)),
    "kg_oak_v": Surface("kg_oak_v", (0.50, 0.78), bump=0.30, distance=0.0028, grime=0.8, edge_color=(0.46, 0.32, 0.18),
                        viewport=(0.28, 0.17, 0.09)),
    "kg_pine": Surface("kg_pine", (0.55, 0.85), bump=0.35, distance=0.003, grime=0.9, edge_color=(0.62, 0.50, 0.32),
                       viewport=(0.45, 0.35, 0.2)),
    "kg_bench_wood": Surface("kg_bench_wood", (0.5, 0.9), bump=0.55, distance=0.004, grime=0.9,
                             edge_color=(0.55, 0.40, 0.22), viewport=(0.38, 0.27, 0.15)),
    "kg_laminate": Surface("kg_laminate", (0.30, 0.55), bump=0.18, distance=0.0012, grime=0.5, edge_color=(0.32, 0.32, 0.28),
                           viewport=(0.36, 0.38, 0.34)),
    "kg_enamel": Surface("kg_enamel", (0.22, 0.48), bump=0.08, distance=0.001, specular=0.55, grime=0.7,
                         edge_color=(0.30, 0.28, 0.26), viewport=(0.6, 0.58, 0.5)),
    "kg_enamel_black": Surface("kg_enamel_black", (0.18, 0.40), bump=0.08, distance=0.001, specular=0.6, grime=0.8,
                               edge_color=(0.30, 0.30, 0.31), viewport=(0.12, 0.12, 0.13)),
    "kg_enamel_yellow": Surface("kg_enamel_yellow", (0.25, 0.55), bump=0.1, distance=0.001, specular=0.5, grime=0.8,
                                edge_color=(0.30, 0.27, 0.22), viewport=(0.62, 0.56, 0.4)),
    "kg_steel": Surface("kg_steel", (0.26, 0.50), metallic=0.85, bump=0.10, distance=0.0008, specular=0.5, grime=0.5,
                        edge_color=(0.75, 0.75, 0.74), viewport=(0.5, 0.5, 0.5)),
    "kg_chrome": Surface("kg_steel", (0.14, 0.34), metallic=0.8, bump=0.0, specular=0.5, grime=0.3,
                         edge_color=None, viewport=(0.6, 0.6, 0.6)),
    "kg_castiron": Surface("kg_castiron", (0.55, 0.85), metallic=0.55, bump=0.4, distance=0.0015, grime=0.5,
                           viewport=(0.08, 0.08, 0.08)),
    "kg_porcelain": Surface("kg_porcelain", (0.10, 0.30), bump=0.06, distance=0.0006, specular=0.6, grime=0.4,
                            viewport=(0.7, 0.68, 0.6)),
    "kg_porcelain_band": Surface("kg_porcelain_band", (0.10, 0.30), bump=0.06, distance=0.0006, specular=0.6, grime=0.4,
                                 viewport=(0.7, 0.68, 0.6)),
    "kg_shelf_paint": Surface("kg_shelf_paint", (0.40, 0.75), bump=0.3, distance=0.0015, grime=0.8,
                              edge_color=(0.20, 0.18, 0.17), viewport=(0.3, 0.34, 0.33)),
    "kg_bike_pink": Surface("kg_bike_pink", (0.30, 0.62), bump=0.25, distance=0.0012, grime=0.6,
                            edge_color=(0.22, 0.18, 0.17), viewport=(0.6, 0.35, 0.45)),
    "kg_bike_tube": Surface("kg_bike_tube", (0.30, 0.62), bump=0.15, distance=0.0008, grime=0.5,
                            edge_color=(0.30, 0.22, 0.2), viewport=(0.6, 0.35, 0.45)),
    "kg_mower_red": Surface("kg_mower_red", (0.35, 0.75), bump=0.25, distance=0.0015, grime=0.9,
                            edge_color=(0.22, 0.17, 0.15), viewport=(0.5, 0.1, 0.08)),
    "kg_plastic_beige": Surface("kg_plastic_beige", (0.35, 0.65), bump=0.15, distance=0.0008, grime=0.7,
                                edge_color=(0.7, 0.66, 0.55), viewport=(0.6, 0.55, 0.42)),
    "kg_plastic_dark": Surface("kg_plastic_dark", (0.35, 0.65), bump=0.15, distance=0.0008, grime=0.5,
                               edge_color=(0.35, 0.35, 0.36), viewport=(0.15, 0.15, 0.16)),
    "kg_plastic_white": Surface("kg_plastic_white", (0.35, 0.65), bump=0.15, distance=0.0008, grime=0.7,
                                edge_color=(0.7, 0.68, 0.62), viewport=(0.65, 0.64, 0.6)),
    "kg_pegboard": Surface("kg_pegboard", (0.7, 0.95), bump=0.9, distance=0.002, specular=0.1, grime=0.8,
                           viewport=(0.5, 0.38, 0.25)),
    "kg_aluminum": Surface("kg_aluminum", (0.30, 0.55), metallic=0.8, bump=0.1, distance=0.0008, specular=0.5, grime=0.7,
                           edge_color=(0.8, 0.8, 0.78), viewport=(0.6, 0.6, 0.6)),
    "kg_tool_steel": Surface("kg_tool_steel", (0.35, 0.7), metallic=0.8, bump=0.25, distance=0.0012, grime=0.6,
                             edge_color=(0.65, 0.65, 0.66), viewport=(0.3, 0.3, 0.32)),
    "kg_toolbox_red": Surface("kg_toolbox_red", (0.35, 0.7), bump=0.25, distance=0.0012, grime=0.8,
                              edge_color=(0.30, 0.25, 0.22), viewport=(0.5, 0.1, 0.07)),
    "kg_tin": Surface("kg_tin", (0.35, 0.7), metallic=0.7, bump=0.25, distance=0.0012, grime=0.7,
                      edge_color=(0.7, 0.7, 0.68), viewport=(0.5, 0.5, 0.5)),
    "kg_heater": Surface("kg_heater", (0.25, 0.55), bump=0.1, distance=0.001, specular=0.5, grime=0.9,
                         edge_color=(0.3, 0.28, 0.26), viewport=(0.6, 0.58, 0.52)),
    "kg_rubber": Surface("kg_rubber", (0.70, 0.95), bump=0.2, distance=0.001, grime=0.2, viewport=(0.05, 0.05, 0.05)),
    "kg_tire": Surface("kg_tire", (0.75, 0.95), bump=0.9, distance=0.003, grime=0.4, viewport=(0.05, 0.05, 0.05)),
    "kg_vinyl_red": Surface("kg_vinyl_red", (0.30, 0.55), bump=0.45, distance=0.0015, specular=0.5, grime=0.7,
                            edge_color=(0.50, 0.25, 0.20), viewport=(0.35, 0.07, 0.06)),
    "kg_towel": Surface("kg_towel", (0.85, 1.0), bump=0.5, distance=0.0008, specular=0.1, grime=0.5,
                        viewport=(0.5, 0.3, 0.25)),
    "kg_food_old": Surface("kg_food_old", (0.55, 0.9), bump=0.9, distance=0.004, specular=0.2, grime=0.0,
                           viewport=(0.25, 0.18, 0.1)),
    **{name: Surface(name, (0.8, 0.95), bump=0.4, distance=0.002, specular=0.15, grime=0.8, viewport=(0.45, 0.34, 0.22))
       for name in ("kg_box_plain", "kg_box_emma", "kg_box_toys", "kg_box_xmas", "kg_box_docs", "kg_box_kitchen")},
}


# nome -> (cor sRGB, rugosidade, metálico) para peças pequenas que dispensam textura
FLATS = {
    "kg_brass": ((0.50, 0.36, 0.14), 0.38, 0.85),
    "kg_copper": ((0.60, 0.30, 0.15), 0.34, 0.9),
    "kg_toe": ((0.10, 0.075, 0.055), 0.85, 0.0),
    "kg_gasket": ((0.035, 0.035, 0.035), 0.7, 0.0),
    "kg_sponge_yellow": ((0.50, 0.40, 0.06), 0.95, 0.0),
    "kg_sponge_green": ((0.06, 0.18, 0.05), 0.95, 0.0),
    "kg_detergent": ((0.12, 0.40, 0.12), 0.3, 0.0),
    "kg_vinyl_black": ((0.06, 0.055, 0.06), 0.45, 0.0),
    "kg_gauge": ((0.80, 0.78, 0.70), 0.35, 0.0),
    "kg_speaker": ((0.09, 0.09, 0.10), 0.7, 0.0),
    "kg_tarp": ((0.035, 0.05, 0.04), 0.7, 0.0),
    "kg_oil_yellow": ((0.50, 0.36, 0.03), 0.35, 0.0),
    "kg_hose": ((0.035, 0.09, 0.035), 0.55, 0.0),
    "kg_cord_orange": ((0.50, 0.17, 0.02), 0.5, 0.0),
    "kg_amber_glass": ((0.35, 0.18, 0.05), 0.08, 0.0),
    "kg_trash_bag": ((0.08, 0.08, 0.09), 0.35, 0.0),
    "kg_coffee": ((0.07, 0.04, 0.025), 0.12, 0.0),
    "kg_bread_crust": ((0.42, 0.28, 0.14), 0.9, 0.0),
    "kg_rotten_fruit": ((0.14, 0.04, 0.025), 0.55, 0.0),
    "kg_mold_orange": ((0.42, 0.22, 0.04), 0.8, 0.0),
    "kg_banana_black": ((0.05, 0.035, 0.02), 0.6, 0.0),
    "kg_spice": ((0.45, 0.19, 0.08), 0.9, 0.0),
    "kg_cardboard_tube": ((0.42, 0.32, 0.20), 0.9, 0.0),
}


def _mix_node(nodes, blend):
    node = nodes.new("ShaderNodeMix")
    node.data_type = "RGBA"
    node.blend_type = blend
    return node


def _color_inputs(node):
    """Sockets (A, B, resultado) da variante de cor do nó Mix, que tem sockets homônimos para float e vetor."""
    colors = [s for s in node.inputs if s.type == "RGBA"]
    return colors[0], colors[1], next(s for s in node.outputs if s.type == "RGBA")


def _build_surface(name, spec):
    mat = compat.new_material(name)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, base_color=(*spec.viewport, 1.0), metallic=spec.metallic, specular=spec.specular)

    image = textures.image(spec.texture)
    image.alpha_mode = "CHANNEL_PACKED"
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Linear"
    tex.extension = "REPEAT"

    wear = nodes.new("ShaderNodeAttribute")
    wear.attribute_type = "GEOMETRY"
    wear.attribute_name = "sa_wear"
    split = nodes.new("ShaderNodeSeparateColor")
    links.new(wear.outputs["Color"], split.inputs["Color"])

    color = tex.outputs["Color"]
    if spec.grime > 0:
        grime_fac = nodes.new("ShaderNodeMath")
        grime_fac.operation = "MULTIPLY"
        grime_fac.inputs[1].default_value = spec.grime
        links.new(split.outputs["Green"], grime_fac.inputs[0])
        darken = _mix_node(nodes, "MULTIPLY")
        a, b, out = _color_inputs(darken)
        links.new(grime_fac.outputs["Value"], darken.inputs[0])
        links.new(color, a)
        b.default_value = GRIME_COLOR
        color = out
    if spec.edge_color:
        reveal = _mix_node(nodes, "MIX")
        a, b, out = _color_inputs(reveal)
        links.new(split.outputs["Red"], reveal.inputs[0])
        links.new(color, a)
        b.default_value = (*spec.edge_color, 1.0)
        color = out
    links.new(color, bsdf.inputs["Base Color"])

    remap = nodes.new("ShaderNodeMapRange")
    remap.inputs["To Min"].default_value, remap.inputs["To Max"].default_value = spec.roughness
    links.new(tex.outputs["Alpha"], remap.inputs["Value"])
    links.new(remap.outputs["Result"], bsdf.inputs["Roughness"])
    if spec.bump > 0:
        compat.add_relief(mat, tex.outputs["Alpha"], spec.bump, spec.distance)
    mat.diffuse_color = (*spec.viewport, 1.0)
    return mat


def _build_decal(name, texture, roughness):
    """Marca com alfa (mancha, teia) rente a uma superfície; a imagem traz o alfa de verdade."""
    mat = compat.new_material(name)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, roughness=roughness, specular=0.3)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = textures.image(texture)
    tex.interpolation = "Linear"
    tex.extension = "CLIP"
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    return mat


def _build_flat(name, color, roughness, metallic):
    mat = compat.new_material(name)
    compat.set_bsdf(compat.bsdf_of(mat), base_color=(*color, 1.0), roughness=roughness, metallic=metallic,
                    specular=0.5 if metallic else 0.3)
    mat.diffuse_color = (*color, 1.0)
    return mat


PAPERS = ("kg_label_blue", "kg_label_green", "kg_label_red", "kg_label_oil", "kg_label_soap", "kg_drawing_house", "kg_drawing_family", "kg_postit_remedio", "kg_postit_doutor", "kg_calendar", "kg_clock_face")


def _build_paper(name):
    """Papel ou mostrador: textura filtrada, relevo leve do traço (cera, caneta) e brilho fosco."""
    mat = compat.new_material(name)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, roughness=0.85, specular=0.2)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = textures.image(name)
    tex.interpolation = "Linear"
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    compat.add_relief(mat, tex.outputs["Color"], 0.25, 0.0006)
    return mat


DECALS = {
    "kg_oil_stain": ("kg_oil_stain", 0.25),
    "kg_cobweb": ("kg_cobweb", 0.9),
    "kg_grease": ("kg_grease", 0.35),
    "kg_smudge": ("kg_smudge", 0.45),
    "kg_outline": ("kg_outline", 0.6),
}


def register():
    tex_cozinha_garagem.register()
    tex_cozinha_papeis.register()
    for name, spec in SURFACES.items():
        materials.register_builder(name, partial(_build_surface, name, spec))
    for name in PAPERS:
        materials.register_builder(name, partial(_build_paper, name))
    for name, (color, roughness, metallic) in FLATS.items():
        materials.register_builder(name, partial(_build_flat, name, color, roughness, metallic))
    for name, (texture, roughness) in DECALS.items():
        materials.register_builder(name, partial(_build_decal, name, texture, roughness))


register()
