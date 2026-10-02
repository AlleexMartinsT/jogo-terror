"""Materiais do carro, montados com nós procedurais.

Tinta, poeira, ferrugem e sujeira de pista não cabem bem numa imagem: o carro anda, gira e é visto de
perto, e uma imagem teria resolução fixa. Os nós usam as coordenadas de OBJETO (a carroceria está em
coordenadas locais do carro), então a ferrugem fica no rodapé e a poeira em cima, e tudo acompanha o carro.

`register()` liga cada nome a uma função em `materials.BUILDERS`; o resto do código só pede pelo nome.
"""
import bpy

from .. import compat
from . import materials, textures

IMPACT_CENTER = (0.66, 2.24, 0.68)      # onde o carro bateu (lado do passageiro, na frente)

PAINT_DARK = (0.062, 0.115, 0.185)
PAINT_FADED = (0.125, 0.170, 0.225)
DUST = (0.19, 0.18, 0.16)
RUST = (0.115, 0.050, 0.026)
BARE_METAL = (0.30, 0.31, 0.32)


class Graph:
    """Atalhos para montar nós sem repetir `nodes.new` e `links.new` a cada linha."""

    def __init__(self, material):
        self.material = material
        self.tree = material.node_tree
        self.nodes, self.links = self.tree.nodes, self.tree.links
        self.bsdf = compat.bsdf_of(material)
        self.coords = self.nodes.new("ShaderNodeTexCoord")

    def put(self, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.links.new(value, socket)
        else:
            if socket.type == "RGBA" and len(value) == 3:
                value = (*value, 1.0)
            socket.default_value = value

    def node(self, kind, **settings):
        node = self.nodes.new(kind)
        for key, value in settings.items():
            setattr(node, key, value)
        return node

    def noise(self, scale, detail=3.0, roughness=0.55, vector=None, distortion=0.0):
        node = self.node("ShaderNodeTexNoise")
        self.put(node.inputs["Vector"], vector or self.coords.outputs["Object"])
        self.put(node.inputs["Scale"], scale)
        self.put(node.inputs["Detail"], detail)
        self.put(node.inputs["Roughness"], roughness)
        self.put(node.inputs["Distortion"], distortion)
        return node.outputs["Fac"]

    def remap(self, value, low, high, out_low=0.0, out_high=1.0, smooth=True):
        """Mapeia [low, high] para [out_low, out_high] (suave por padrão) sem sair do intervalo."""
        node = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP" if smooth else "LINEAR", clamp=True)
        for index, item in enumerate((value, low, high, out_low, out_high)):
            self.put(node.inputs[index], item)
        return node.outputs[0]

    def math(self, operation, a, b=None, clamp=False):
        node = self.node("ShaderNodeMath", operation=operation, use_clamp=clamp)
        self.put(node.inputs[0], a)
        if b is not None:
            self.put(node.inputs[1], b)
        return node.outputs[0]

    def mix(self, factor, a, b):
        node = self.node("ShaderNodeMix", data_type="RGBA")
        self.put(node.inputs[0], factor)
        self.put(node.inputs[6], a)
        self.put(node.inputs[7], b)
        return node.outputs[2]

    def ramp(self, factor, stops):
        node = self.node("ShaderNodeValToRGB")
        elements = node.color_ramp.elements
        while len(elements) < len(stops):
            elements.new(0.5)
        for element, (position, color) in zip(elements, stops):
            element.position = position
            element.color = (*color, 1.0)
        self.put(node.inputs["Fac"], factor)
        return node.outputs["Color"]

    def axis(self, vector, name):
        split = self.node("ShaderNodeSeparateXYZ")
        self.put(split.inputs["Vector"], vector)
        return split.outputs[name]

    def distance_to(self, point):
        node = self.node("ShaderNodeVectorMath", operation="DISTANCE")
        self.put(node.inputs[0], self.coords.outputs["Object"])
        node.inputs[1].default_value = point
        return node.outputs["Value"]

    def bump(self, height, strength, distance):
        node = self.node("ShaderNodeBump")
        self.put(node.inputs["Height"], height)
        self.put(node.inputs["Strength"], strength)
        self.put(node.inputs["Distance"], distance)
        self.links.new(node.outputs["Normal"], self.bsdf.inputs["Normal"])
        return node

    def surface(self, color=None, roughness=None, metallic=None, coat=None, emission=None, emission_strength=None):
        """Liga as entradas do Principled (cada uma pode ser um valor ou um socket)."""
        names = {"Base Color": color, "Roughness": roughness, "Metallic": metallic, "Coat Weight": coat,
                 "Emission Color": emission, "Emission Strength": emission_strength}
        for name, value in names.items():
            if value is not None and name in self.bsdf.inputs:
                self.put(self.bsdf.inputs[name], value)


def _new(name):
    material = compat.new_material(name)
    return Graph(material)


def _blended(material):
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "BLENDED"
    else:
        material.blend_method = "BLEND"
    material.use_backface_culling = False


def _image(graph, texture_name, vector=None):
    """Nó de imagem com filtro linear (as texturas do carro têm 256 a 512 px e são vistas de perto)."""
    node = graph.node("ShaderNodeTexImage", interpolation="Linear", extension="EXTEND")
    node.image = textures.image(texture_name)
    graph.put(node.inputs["Vector"], vector or graph.coords.outputs["UV"])
    return node


# --------------------------------------------------------------------------------------------
# Tinta
# --------------------------------------------------------------------------------------------
def _paint_masks(graph):
    """Máscaras 0..1 da carroceria: sol (oxidação), poeira, ferrugem e a área do amassado."""
    height = graph.axis(graph.coords.outputs["Object"], "Z")
    facing_up = graph.axis(graph.coords.outputs["Normal"], "Z")
    blotch, patch, grain = graph.noise(2.4), graph.noise(9.0, 4.0), graph.noise(60.0, 2.0)
    sun = graph.math("MULTIPLY", graph.remap(facing_up, 0.45, 0.95), graph.remap(blotch, 0.35, 0.75, 0.25, 0.8))
    low = graph.remap(height, 0.55, 0.20)                      # respingo de lama sobe das rodas
    dust = graph.math("ADD", graph.math("MULTIPLY", graph.remap(facing_up, 0.3, 0.95), graph.remap(patch, 0.3, 0.8, 0.05, 0.38)),
                      graph.math("MULTIPLY", low, graph.remap(patch, 0.3, 0.7, 0.15, 0.6)), clamp=True)
    rust_noise = graph.math("ADD", patch, graph.math("MULTIPLY", low, 0.45))
    rust = graph.remap(rust_noise, 0.90, 1.06)
    impact = graph.remap(graph.distance_to(IMPACT_CENTER), 0.62, 0.20)
    impact = graph.math("MULTIPLY", impact, graph.remap(graph.noise(14.0, 3.0), 0.25, 0.6, 0.35, 1.0))
    return {"sun": sun, "dust": dust, "rust": rust, "impact": impact, "grain": grain, "patch": patch}


def build_paint():
    """Tinta azul desbotada: clareada pelo sol em cima, poeira, ferrugem embaixo e metal exposto no amassado."""
    graph = _new("car_body_paint")
    masks = _paint_masks(graph)
    color = graph.mix(masks["sun"], PAINT_DARK, PAINT_FADED)
    color = graph.mix(masks["dust"], color, DUST)
    color = graph.mix(masks["rust"], color, RUST)
    color = graph.mix(masks["impact"], color, graph.mix(masks["patch"], BARE_METAL, RUST))
    rough = graph.math("ADD", 0.30, graph.math("ADD", graph.math("MULTIPLY", masks["sun"], 0.25),
                                               graph.math("MULTIPLY", graph.math("MAXIMUM", masks["dust"], masks["rust"]), 0.55)),
                       clamp=True)
    metal = graph.math("MULTIPLY", 0.45, graph.math("SUBTRACT", 1.0, graph.math("MAXIMUM", masks["rust"], masks["dust"]), clamp=True))
    graph.surface(color=color, roughness=rough, metallic=metal, coat=graph.math("MULTIPLY", 0.4, graph.math("SUBTRACT", 1.0, masks["sun"])))
    graph.bump(graph.math("ADD", graph.math("MULTIPLY", masks["grain"], 0.35), graph.math("MULTIPLY", masks["rust"], 0.9)),
               0.5, 0.0025)
    return graph.material


# --------------------------------------------------------------------------------------------
# Metais, borrachas e plásticos
# --------------------------------------------------------------------------------------------
def build_chrome():
    """Cromado velho: espelho opaco, manchas de oxidação e pontos de ferrugem perto do chão."""
    graph = _new("car_chrome")
    height = graph.axis(graph.coords.outputs["Object"], "Z")
    haze = graph.remap(graph.noise(7.0, 4.0), 0.4, 0.85, 0.0, 0.7)
    pits = graph.math("MULTIPLY", graph.remap(graph.noise(70.0, 1.0), 0.66, 0.8), graph.remap(height, 0.8, 0.3, 0.2, 0.8))
    color = graph.mix(pits, graph.mix(haze, (0.66, 0.68, 0.70), (0.30, 0.30, 0.29)), RUST)
    graph.surface(color=color, roughness=graph.math("ADD", 0.14, graph.math("MULTIPLY", haze, 0.35)),
                  metallic=graph.math("SUBTRACT", 1.0, graph.math("MULTIPLY", pits, 0.8)))
    graph.bump(graph.math("MULTIPLY", pits, 0.6), 0.4, 0.001)
    return graph.material


def _rubbery(name, color, roughness, bump_scale, bump_strength):
    graph = _new(name)
    wear = graph.remap(graph.noise(9.0, 3.0), 0.35, 0.8)
    graph.surface(color=graph.mix(wear, color, tuple(c * 2.2 + 0.015 for c in color)), roughness=roughness, metallic=0.0)
    graph.bump(graph.noise(bump_scale, 2.0), bump_strength, 0.002)
    return graph.material


def build_rubber():
    return _rubbery("car_rubber", (0.014, 0.014, 0.016), 0.78, 140.0, 0.4)


def build_black_plastic():
    return _rubbery("car_black_plastic", (0.020, 0.020, 0.022), 0.62, 90.0, 0.5)


def build_tire():
    """Flanco do pneu: borracha preta com letras em relevo e poeira clara só em manchas."""
    graph = _new("car_tire")
    sidewall = _image(graph, "car_tire_sidewall")
    dust = graph.remap(graph.noise(6.0, 4.0), 0.55, 0.9, 0.0, 0.32)
    base = graph.mix(dust, (0.020, 0.020, 0.022), (0.17, 0.16, 0.14))
    lettering = graph.remap(sidewall.outputs["Color"], 0.08, 0.2)
    graph.surface(color=graph.mix(lettering, base, (0.30, 0.30, 0.28)), roughness=0.8, metallic=0.0)
    graph.bump(graph.math("ADD", sidewall.outputs["Color"], graph.noise(120.0, 2.0)), 0.6, 0.002)
    return graph.material


def build_tread():
    """Banda de rodagem: borracha gasta, mais clara no meio onde roda no asfalto, com terra nos sulcos."""
    graph = _new("car_tire_tread")
    dirt = graph.remap(graph.noise(8.0, 4.0), 0.4, 0.85, 0.0, 0.5)
    graph.surface(color=graph.mix(dirt, (0.028, 0.028, 0.03), (0.13, 0.115, 0.09)), roughness=0.9, metallic=0.0)
    graph.bump(graph.noise(200.0, 2.0), 0.7, 0.002)
    return graph.material


def build_rim():
    """Aro de aço pintado de cinza-grafite, descascado e com ferrugem escorrida dos parafusos."""
    graph = _new("car_rim")
    height = graph.axis(graph.coords.outputs["Object"], "Z")
    rust = graph.remap(graph.math("ADD", graph.noise(10.0, 4.0), graph.math("MULTIPLY", graph.remap(height, 0.1, -0.1), 0.15)), 0.62, 0.95)
    color = graph.mix(rust, (0.085, 0.09, 0.095), RUST)
    graph.surface(color=color, roughness=graph.math("ADD", 0.45, graph.math("MULTIPLY", rust, 0.4)), metallic=graph.math("SUBTRACT", 0.7, graph.math("MULTIPLY", rust, 0.7)))
    graph.bump(graph.noise(80.0, 2.0), 0.3, 0.002)
    return graph.material


# --------------------------------------------------------------------------------------------
# Vidros e lentes
# --------------------------------------------------------------------------------------------
def _glass(name, texture=None):
    graph = _new(name)
    film = graph.remap(graph.noise(4.0, 4.0), 0.4, 0.85, 0.0, 0.6)
    streaks = graph.remap(graph.noise(vector=graph.coords.outputs["Object"], scale=18.0, detail=2.0), 0.5, 0.8, 0.0, 0.5)
    haze = graph.math("MAXIMUM", film, streaks)
    color = graph.mix(haze, (0.04, 0.06, 0.07), (0.30, 0.31, 0.3))
    alpha = graph.math("ADD", 0.22, graph.math("MULTIPLY", haze, 0.28))
    if texture:
        crack = _image(graph, texture)
        color = graph.mix(crack.outputs["Alpha"], color, (0.8, 0.86, 0.9))
        alpha = graph.math("MAXIMUM", alpha, crack.outputs["Alpha"], clamp=True)
    graph.surface(color=color, roughness=0.05)
    graph.put(graph.bsdf.inputs["Alpha"], alpha)
    _blended(graph.material)
    return graph.material


def build_glass():
    return _glass("car_glass_clear")


def build_windshield():
    return _glass("car_windshield", "car_windshield_crack")


def build_lens_clear():
    """Lente do farol: policarbonato amarelado com nervuras horizontais."""
    graph = _new("car_lens_clear")
    ribs = graph.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z")
    graph.put(ribs.inputs["Vector"], graph.coords.outputs["Object"])
    graph.put(ribs.inputs["Scale"], 90.0)
    graph.surface(color=(0.45, 0.43, 0.34), roughness=0.08)
    graph.put(graph.bsdf.inputs["Alpha"], 0.2)
    graph.bump(ribs.outputs["Fac"], 0.25, 0.001)
    _blended(graph.material)
    return graph.material


def _tail_lens(name, color, glow):
    graph = _new(name)
    cells = graph.node("ShaderNodeTexVoronoi")
    graph.put(cells.inputs["Vector"], graph.coords.outputs["Object"])
    graph.put(cells.inputs["Scale"], 140.0)
    graph.surface(color=color, roughness=0.12, emission=color, emission_strength=glow)
    graph.put(graph.bsdf.inputs["Alpha"], 0.82)
    graph.bump(cells.outputs["Distance"], 0.3, 0.001)
    _blended(graph.material)
    return graph.material


def build_tail_red():
    return _tail_lens("car_tail_red", (0.42, 0.02, 0.015), 0.18)


def build_tail_amber():
    return _tail_lens("car_tail_amber", (0.55, 0.22, 0.02), 0.12)


def build_lamp_glow():
    """Lente que acende com os faróis: lê a propriedade `sa_glow` do objeto (como as luminárias da casa)."""
    graph = _new("car_lens_glow")
    glow = graph.node("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name='["sa_glow"]')
    graph.surface(color=(0.5, 0.48, 0.4), roughness=0.08, emission=(1.0, 0.92, 0.72),
                  emission_strength=graph.math("MULTIPLY", glow.outputs["Fac"], 40.0))
    return graph.material


# --------------------------------------------------------------------------------------------
# Interior
# --------------------------------------------------------------------------------------------
def _fabric(name, color, stain, weave_scale):
    graph = _new(name)
    blotch = graph.remap(graph.noise(5.0, 4.0), 0.35, 0.8)
    wear = graph.remap(graph.noise(2.0, 3.0), 0.4, 0.8)
    base = graph.mix(blotch, color, stain)
    base = graph.mix(graph.math("MULTIPLY", wear, 0.35), base, (0.09, 0.075, 0.055))
    graph.surface(color=base, roughness=0.96, metallic=0.0)
    graph.bump(graph.noise(weave_scale, 1.0, 0.7), 0.6, 0.002)
    return graph.material


def build_velour():
    return _fabric("car_velour", (0.30, 0.245, 0.17), (0.17, 0.13, 0.085), 220.0)


def build_headliner():
    return _fabric("car_headliner", (0.34, 0.31, 0.24), (0.20, 0.15, 0.09), 120.0)


def build_carpet():
    return _fabric("car_carpet", (0.12, 0.10, 0.085), (0.05, 0.04, 0.035), 260.0)


def build_dash_plastic():
    """Painel: plástico marrom-acinzentado, craquelado pelo sol."""
    graph = _new("car_dash_plastic")
    sun = graph.remap(graph.axis(graph.coords.outputs["Normal"], "Z"), 0.3, 0.95)
    cracks = graph.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    graph.put(cracks.inputs["Vector"], graph.coords.outputs["Object"])
    graph.put(cracks.inputs["Scale"], 28.0)
    base = graph.mix(graph.math("MULTIPLY", sun, 0.5), (0.055, 0.05, 0.045), (0.16, 0.14, 0.115))
    graph.surface(color=base, roughness=0.6, metallic=0.0)
    graph.bump(graph.math("ADD", graph.noise(150.0, 2.0), graph.remap(cracks.outputs["Distance"], 0.0, 0.04)), 0.4, 0.002)
    return graph.material


def build_door_trim():
    """Forro de porta e laterais: vinil bege escurecido, mais sujo perto do chão."""
    graph = _new("car_door_trim")
    height = graph.axis(graph.coords.outputs["Object"], "Z")
    dirt = graph.math("MULTIPLY", graph.remap(height, 0.8, 0.35), graph.remap(graph.noise(8.0, 4.0), 0.3, 0.8, 0.3, 1.0))
    graph.surface(color=graph.mix(dirt, (0.26, 0.215, 0.15), (0.09, 0.07, 0.05)), roughness=0.7, metallic=0.0)
    graph.bump(graph.noise(110.0, 2.0), 0.35, 0.002)
    return graph.material


def _emissive_panel(name, texture, strength, bright_only=False):
    graph = _new(name)
    image = _image(graph, texture)
    color = image.outputs["Color"]
    glow = color
    if bright_only:
        luminance = graph.math("MULTIPLY", graph.math("ADD", graph.axis(color, "X"), graph.axis(color, "Y")), 0.5)
        glow = graph.mix(graph.remap(luminance, 0.45, 0.8), (0.0, 0.0, 0.0), color)
    graph.surface(color=color, roughness=0.15, emission=glow, emission_strength=strength)
    return graph.material


def build_cluster():
    return _emissive_panel("car_cluster", "car_cluster", 0.9, bright_only=True)


def build_radio():
    return _emissive_panel("car_radio", "car_radio", 0.25)


def build_plate():
    graph = _new("car_plate")
    image = _image(graph, "car_plate")
    graph.surface(color=image.outputs["Color"], roughness=0.35, metallic=0.2)
    graph.bump(graph.math("SUBTRACT", 1.0, graph.axis(image.outputs["Color"], "X")), 0.3, 0.0015)
    return graph.material


BUILDERS = {
    "car_body_paint": build_paint, "car_chrome": build_chrome, "car_rubber": build_rubber,
    "car_black_plastic": build_black_plastic, "car_tire": build_tire, "car_tire_tread": build_tread, "car_rim": build_rim,
    "car_glass_clear": build_glass, "car_windshield": build_windshield, "car_lens_clear": build_lens_clear,
    "car_tail_red": build_tail_red, "car_tail_amber": build_tail_amber, "car_lens_glow": build_lamp_glow,
    "car_velour": build_velour, "car_headliner": build_headliner, "car_carpet": build_carpet,
    "car_dash_plastic": build_dash_plastic, "car_door_trim": build_door_trim, "car_cluster": build_cluster,
    "car_radio": build_radio, "car_plate": build_plate,
}


def register():
    for name, build in BUILDERS.items():
        materials.register_builder(name, build)
