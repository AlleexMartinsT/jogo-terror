"""Materiais próprios do exterior, registrados no mesmo registro de `materials` ao importar este módulo.

Os que leem por UV (telha, tijolo, tábua) esperam que a geometria sorteie um recorte da imagem por peça;
a grama é um material de nós, com tom que vai do pé escuro à ponta de palha.
"""
from .. import compat
from . import materials, tex_yard

Surface = materials.Surface


def _grass_blade():
    """Capim morto: gradiente de cor ao longo da lâmina (UV.y) multiplicado por um tom sorteado por lâmina (UV.x)."""
    mat, tree, bsdf = materials._new_material("ext_grass")
    uv = tree.nodes.new("ShaderNodeTexCoord").outputs["UV"]
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(uv, split.inputs["Vector"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    stops = [(0.0, (0.014, 0.013, 0.008)), (0.45, (0.050, 0.044, 0.024)), (1.0, (0.115, 0.098, 0.056))]
    while len(ramp.color_ramp.elements) < len(stops):
        ramp.color_ramp.elements.new(0.5)
    for element, (position, color) in zip(ramp.color_ramp.elements, stops):
        element.position, element.color = position, (*color, 1.0)
    tree.links.new(split.outputs["Y"], ramp.inputs["Fac"])
    tone = tree.nodes.new("ShaderNodeMath")
    tone.operation = "MULTIPLY_ADD"
    tone.inputs[1].default_value = 0.7
    tone.inputs[2].default_value = 0.55
    tree.links.new(split.outputs["X"], tone.inputs[0])
    tinted = tree.nodes.new("ShaderNodeMix")
    tinted.data_type = "RGBA"
    tinted.blend_type = "MULTIPLY"
    tinted.inputs[0].default_value = 1.0
    tree.links.new(ramp.outputs["Color"], tinted.inputs[6])
    tree.links.new(tone.outputs[0], tinted.inputs[7])
    tree.links.new(tinted.outputs[2], bsdf.inputs["Base Color"])
    compat.set_bsdf(bsdf, roughness=1.0, specular=0.0)
    mat.use_backface_culling = False
    materials._finish_viewport(mat, (0.09, 0.075, 0.04))
    return mat


def register():
    materials.SURFACES.update({
        "ext_shingle": Surface(tex_yard.shingle_tab, 1.0, specular=0.05, coords="uv", bump=1.0, distance=0.006),
        "ext_brick": Surface(tex_yard.brick_unit, 1.0, specular=0.05, coords="uv", bump=1.0, distance=0.004),
        "ext_mortar": Surface(tex_yard.mortar, 0.6, specular=0.0, bump=0.8, distance=0.004),
        "ext_board": Surface(tex_yard.board_paint, 1.0, specular=0.08, coords="uv", bump=1.0, distance=0.003),
        "ext_gutter": Surface(tex_yard.gutter_paint, 0.8, specular=0.3, bump=0.7, distance=0.002),
        "ext_plaque": Surface(tex_yard.house_number, 1.0, specular=0.3, coords="uv", bump=1.0, distance=0.0015),
        "ext_chalk": Surface(tex_yard.chalk_drawing, 1.0, specular=0.1, coords="uv", bump=0.3, distance=0.0005, render="BLENDED"),
        "ext_sign": Surface(tex_yard.children_sign, 1.0, specular=0.4, coords="uv", bump=0.5, distance=0.001, render="DITHERED"),
    })
    Simple = materials.Simple
    materials.SIMPLE.update({
        "ext_hydrant": Simple((0.30, 0.050, 0.040), 0.5, 0.3, 0.4, variation=0.45, scale=28.0, bump=0.4),
        "ext_sign_yellow": Simple((0.50, 0.40, 0.04), 0.4, 0.2, 0.4, variation=0.25, scale=20.0),
        "ext_bin_green": Simple((0.040, 0.075, 0.050), 0.5, 0.0, 0.3, variation=0.25, scale=30.0),
        "ext_bin_gray": Simple((0.12, 0.125, 0.13), 0.55, 0.0, 0.3, variation=0.25, scale=30.0),
        "ext_pole_metal": Simple((0.12, 0.125, 0.13), 0.45, 0.8, 0.4, variation=0.4, scale=18.0),
        "ext_mailbox": Simple((0.025, 0.027, 0.03), 0.45, 0.7, 0.4, variation=0.35, scale=26.0),
    })
    materials.register_builder("ext_grass", _grass_blade)


register()
