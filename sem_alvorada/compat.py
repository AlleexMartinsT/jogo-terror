"""Diferenças entre versões do Blender (4.2 LTS ... 5.x) concentradas em um só lugar.

Testado em 5.0.1. Em 4.2-4.5 o EEVEE se chama BLENDER_EEVEE_NEXT; em 5.0 voltou a BLENDER_EEVEE.
"""
import bpy


def eevee_id():
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    return "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in ids else "BLENDER_EEVEE"


def use_eevee(scene):
    scene.render.engine = eevee_id()


def new_material(name):
    """Material com nós (Principled BSDF + Material Output) em qualquer versão."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True     # obsoleto no 5.0 (sempre True), necessário antes
    return mat


def bsdf_of(mat):
    return next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")


def set_bsdf(node, base_color=None, roughness=None, metallic=None, emission=None,
             emission_strength=None, alpha=None, specular=None):
    """Define entradas do Principled sem depender dos nomes que mudaram na 4.0."""
    def put(names, value):
        for n in names:
            if n in node.inputs:
                node.inputs[n].default_value = value
                return

    if base_color is not None:
        c = tuple(base_color)
        put(["Base Color"], c if len(c) == 4 else (*c, 1.0))
    if roughness is not None:
        put(["Roughness"], roughness)
    if metallic is not None:
        put(["Metallic"], metallic)
    if specular is not None:
        put(["Specular IOR Level", "Specular"], specular)
    if emission is not None:
        c = tuple(emission)
        put(["Emission Color", "Emission"], c if len(c) == 4 else (*c, 1.0))
    if emission_strength is not None:
        put(["Emission Strength"], emission_strength)
    if alpha is not None:
        put(["Alpha"], alpha)


def link_to_collection(obj, coll):
    """Move obj para a coleção `coll` (tirando de todas as outras)."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def add_relief(mat, color_socket, strength=0.5, distance=0.01):
    """Liga a luminância de uma textura ao relevo (Bump) do material: veios, tijolos, trama de tecido.

    Sem relevo, a lanterna rasante vê uma superfície lisa e pintada; com ele, cada fresta pega luz.
    `distance` é a altura (m) que o branco da textura representa em relação ao preto.
    """
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    gray = nodes.new("ShaderNodeRGBToBW")
    links.new(color_socket, gray.inputs["Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    links.new(gray.outputs["Val"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf_of(mat).inputs["Normal"])
    return bump
