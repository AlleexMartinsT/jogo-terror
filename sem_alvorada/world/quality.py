"""Níveis de qualidade do EEVEE e pós-processamento estilo Cry of Fear.

`apply(scene, 'low'|'medium'|'high')` configura o EEVEE (sombras, GI, neblina volumétrica), o
mapeamento de tons e um compositor em tempo real com: brilho nas emissões (glare), aberração
cromática leve, dessaturação, contraste, vinheta e granulação.

Cada ajuste é tentado separadamente: se o Blender não conhece uma propriedade ou um nó, o item
é anotado no relatório devolvido e o restante segue (o build nunca quebra por isso).

Compositor: no Blender 5.x a árvore vive em `scene.compositing_node_group` (um grupo de nós
com saída "Image"); no 4.x, em `scene.node_tree` com `use_nodes`. O launcher precisa de
`space.shading.use_compositor = 'ALWAYS'` para ver o efeito na viewport.
"""
import bpy

from .. import compat
from . import sky

LEVELS = ("low", "medium", "high")
POST_TREE_NAME = "SA_Post"
GRAIN_PHASE_NODE = "SA_GrainPhase"

EEVEE_LEVELS = {
    "low": dict(
        use_shadows=True, shadow_ray_count=1, shadow_step_count=4, shadow_resolution_scale=0.5,
        shadow_pool_size="128", light_threshold=0.05, taa_samples=6, use_raytracing=False, use_fast_gi=False,
        volumetric_tile_size="16", volumetric_samples=16, use_volumetric_shadows=False,
    ),
    "medium": dict(
        use_shadows=True, shadow_ray_count=1, shadow_step_count=6, shadow_resolution_scale=0.75,
        shadow_pool_size="256", light_threshold=0.02, taa_samples=8, use_raytracing=True,
        ray_tracing_method="SCREEN", use_fast_gi=True, fast_gi_method="AMBIENT_OCCLUSION_ONLY",
        fast_gi_resolution="4", fast_gi_ray_count=2, fast_gi_step_count=6,
        volumetric_tile_size="8", volumetric_samples=24, use_volumetric_shadows=False,
    ),
    "high": dict(
        use_shadows=True, shadow_ray_count=2, shadow_step_count=8, shadow_resolution_scale=1.0,
        shadow_pool_size="512", light_threshold=0.01, taa_samples=16, use_raytracing=True,
        ray_tracing_method="SCREEN", use_fast_gi=True, fast_gi_method="GLOBAL_ILLUMINATION",
        fast_gi_resolution="2", fast_gi_ray_count=2, fast_gi_step_count=8,
        volumetric_tile_size="4", volumetric_samples=48, use_volumetric_shadows=True,
    ),
}
RAY_TRACING_LEVELS = {
    "low": {}, "medium": dict(resolution_scale="4", use_denoise=True),
    "high": dict(resolution_scale="2", use_denoise=True),
}
FOG_DENSITY = {"low": 0.0, "medium": 0.012, "high": 0.02}
GRAIN_AMOUNT = {"low": 0.0, "medium": 0.06, "high": 0.08}
DISPERSION = {"low": 0.0, "medium": 0.004, "high": 0.006}
SATURATION = 0.72
CONTRAST = 6.0
VIGNETTE_STRENGTH = 1.3
BLOOM_STRENGTH = 0.35
EXPOSURE = 0.0


def apply(scene, level="medium"):
    """Configura `scene` para o nível dado e devolve a lista de itens que o Blender recusou."""
    if level not in LEVELS:
        raise ValueError(f"nível de qualidade desconhecido: {level!r}")
    skipped = []
    compat.use_eevee(scene)
    _apply_properties(scene.eevee, EEVEE_LEVELS[level], skipped, "eevee")
    _apply_properties(scene.eevee.ray_tracing_options, RAY_TRACING_LEVELS[level], skipped, "ray_tracing")
    _apply_color_management(scene, skipped)
    _apply_fog(scene, level, skipped)
    _apply_post(scene, level, skipped)
    scene["sa_quality"] = level
    return skipped


def _apply_properties(target, values, skipped, prefix):
    for name, value in values.items():
        try:
            setattr(target, name, value)
        except (AttributeError, TypeError, ValueError) as error:
            skipped.append(f"{prefix}.{name}: {error}")


def _apply_color_management(scene, skipped):
    settings = scene.view_settings
    for transform in ("AgX", "Standard"):
        try:
            settings.view_transform = transform
            break
        except (TypeError, ValueError):
            continue
    settings.exposure = EXPOSURE
    settings.gamma = 1.0
    scene.render.use_motion_blur = False


def _apply_fog(scene, level, skipped):
    sky.set_fog_density(scene, FOG_DENSITY[level])
    _apply_properties(scene.eevee, dict(volumetric_end=60.0, volumetric_start=0.1), skipped, "eevee")


# --------------------------------------------------------------------------
# Compositor
# --------------------------------------------------------------------------
def _post_tree(scene):
    """Árvore do compositor, recriada do zero a cada chamada (idempotente)."""
    if hasattr(scene, "compositing_node_group"):
        old = bpy.data.node_groups.get(POST_TREE_NAME)
        if old is not None:
            bpy.data.node_groups.remove(old)
        tree = bpy.data.node_groups.new(POST_TREE_NAME, "CompositorNodeTree")
        scene.compositing_node_group = tree
        return tree, True
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    return tree, False


def _output_node(tree, grouped):
    if grouped:
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        node = tree.nodes.new("NodeGroupOutput")
        return node, node.inputs[0]
    node = tree.nodes.new("CompositorNodeComposite")
    return node, node.inputs["Image"]


def _mix(tree, blend, color_a, color_b):
    node = tree.nodes.new("ShaderNodeMix")
    node.data_type = "RGBA"
    node.blend_type = blend
    node.inputs[0].default_value = 1.0
    tree.links.new(color_a, node.inputs[6])
    tree.links.new(color_b, node.inputs[7])
    return node.outputs[2]


def _math(tree, operation, *operands):
    node = tree.nodes.new("ShaderNodeMath")
    node.operation = operation
    for index, value in enumerate(operands):
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = value
        else:
            tree.links.new(value, node.inputs[index])
    return node.outputs[0]


def _vignette(tree, image_socket, coords):
    centered = tree.nodes.new("ShaderNodeVectorMath")
    centered.operation = "SUBTRACT"
    tree.links.new(coords.outputs["Normalized"], centered.inputs[0])
    centered.inputs[1].default_value = (0.5, 0.5, 0.0)
    squared = tree.nodes.new("ShaderNodeVectorMath")
    squared.operation = "DOT_PRODUCT"
    tree.links.new(centered.outputs["Vector"], squared.inputs[0])
    tree.links.new(centered.outputs["Vector"], squared.inputs[1])
    falloff = _math(tree, "MULTIPLY_ADD", squared.outputs["Value"], -VIGNETTE_STRENGTH, 1.0)
    gain = _math(tree, "MAXIMUM", falloff, 0.2)
    return _mix(tree, "MULTIPLY", image_socket, gain)


def _vignette_from_mask(tree, image_socket):
    """Vinheta para compositores sem coordenadas: elipse clara desfocada multiplicada pela imagem."""
    mask = tree.nodes.new("CompositorNodeEllipseMask")
    mask.x, mask.y = 0.5, 0.5
    mask.mask_width, mask.mask_height = 0.95, 0.95
    blur = tree.nodes.new("CompositorNodeBlur")
    blur.filter_type = "GAUSS"
    blur.use_relative = True
    blur.factor_x = blur.factor_y = 30
    tree.links.new(mask.outputs["Mask"], blur.inputs["Image"])
    floor = 1.0 - VIGNETTE_STRENGTH * 0.5
    lift = tree.nodes.new("CompositorNodeMath")
    lift.operation = "MULTIPLY_ADD"
    tree.links.new(blur.outputs["Image"], lift.inputs[0])
    lift.inputs[1].default_value = 1.0 - floor
    lift.inputs[2].default_value = floor
    mix = tree.nodes.new("CompositorNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 1.0
    tree.links.new(image_socket, mix.inputs[1])
    tree.links.new(lift.outputs["Value"], mix.inputs[2])
    return mix.outputs["Image"]


def _grain(tree, image_socket, coords, amount):
    noise = tree.nodes.new("ShaderNodeTexWhiteNoise")
    noise.noise_dimensions = "4D"
    tree.links.new(coords.outputs["Pixel"], noise.inputs["Vector"])
    phase = tree.nodes.new("ShaderNodeValue")
    phase.name = GRAIN_PHASE_NODE
    frame = tree.nodes.new("CompositorNodeSceneTime")
    tree.links.new(_math(tree, "ADD", phase.outputs[0], frame.outputs["Frame"]), noise.inputs["W"])
    centered = _math(tree, "MULTIPLY_ADD", noise.outputs["Value"], 2 * amount, 1.0 - amount)
    return _mix(tree, "MULTIPLY", image_socket, centered)


def _stage(skipped, description, build):
    """Roda a montagem de um estágio do compositor; se falhar, anota e devolve None."""
    try:
        return build()
    except Exception as error:      # noqa: BLE001 - degradar sem quebrar o build é a regra aqui
        skipped.append(f"compositor/{description}: {error}")
        return None


def _apply_post(scene, level, skipped):
    tree, grouped = _stage(skipped, "árvore", lambda: _post_tree(scene)) or (None, False)
    if tree is None:
        return
    render = tree.nodes.new("CompositorNodeRLayers")
    output, output_socket = _output_node(tree, grouped)
    image = render.outputs["Image"]

    def image_coordinates():
        node = tree.nodes.new("CompositorNodeImageCoordinates")     # só existe a partir do 5.0
        tree.links.new(render.outputs["Image"], node.inputs["Image"])
        return node

    coords = _stage(skipped, "coordenadas", image_coordinates)

    def bloom():
        node = tree.nodes.new("CompositorNodeGlare")
        if "Type" in node.inputs:
            node.inputs["Type"].default_value = "Bloom"
            node.inputs["Quality"].default_value = "Medium" if level != "high" else "High"
            node.inputs["Threshold"].default_value = 0.8
            node.inputs["Strength"].default_value = BLOOM_STRENGTH
            node.inputs["Size"].default_value = 0.4
        else:
            node.glare_type = "BLOOM"
            node.quality = "MEDIUM" if level != "high" else "HIGH"
            node.threshold = 0.8
            node.mix = -0.6          # -1 só a imagem original, +1 só o brilho
            node.size = 6
        tree.links.new(image, node.inputs["Image"])
        return node.outputs["Image"]

    def aberration():
        node = tree.nodes.new("CompositorNodeLensdist")
        node.inputs["Dispersion"].default_value = DISPERSION[level]
        tree.links.new(image, node.inputs["Image"])
        return node.outputs["Image"]

    def grading():
        node = tree.nodes.new("CompositorNodeHueSat")
        node.inputs["Saturation"].default_value = SATURATION
        tree.links.new(image, node.inputs["Image"])
        contrast = tree.nodes.new("CompositorNodeBrightContrast")
        contrast.inputs["Contrast"].default_value = CONTRAST
        tree.links.new(node.outputs["Image"], contrast.inputs["Image"])
        return contrast.outputs["Image"]

    stages = [("bloom", bloom, level != "low"), ("aberração", aberration, DISPERSION[level] > 0),
              ("cor", grading, True)]
    for description, build, enabled in stages:
        if enabled:
            produced = _stage(skipped, description, build)
            image = produced or image
    if coords is not None:
        image = _stage(skipped, "vinheta", lambda: _vignette(tree, image, coords)) or image
        if GRAIN_AMOUNT[level] > 0:
            image = _stage(skipped, "granulação", lambda: _grain(tree, image, coords, GRAIN_AMOUNT[level])) or image
    else:
        # Compositor do 4.x: sem coordenadas de imagem nem ruído, só dá para uma vinheta por máscara.
        image = _stage(skipped, "vinheta (máscara)", lambda: _vignette_from_mask(tree, image)) or image
    tree.links.new(image, output_socket)


def set_grain_phase(scene, phase):
    """A granulação só anima se alguém avança a fase (o engine chama a cada quadro)."""
    tree = getattr(scene, "compositing_node_group", None) or getattr(scene, "node_tree", None)
    node = tree.nodes.get(GRAIN_PHASE_NODE) if tree else None
    if node is not None:
        node.outputs[0].default_value = phase
