"""Renders do Blender (Workbench) dos objetos REAIS do jogo, com o modelo físico como fantasma azul no mesmo espaço 3D.

    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.fisica.cenas3d [porta_25kg porta_40kg relogio carro] [--sem-video] [--eevee]

Palco: o `.blend` completo do build (out/integration/full.blend, que já traz o pêndulo e o ponteiro do relógio); o forro, o telhado,
as árvores e o corpo do jogador ficam ocultos para as câmeras de planta e de lado enxergarem dentro da casa. Os objetos do jogo são
movidos pelo CÓDIGO DO JOGO (`DoorManager`, `CarMotion`, `GarageLift`, `CharmPendulum`, `ClockWork`) sobre os objetos reais; o modelo
físico (fisica/porta.py, carro.py, relogio.py) vira um objeto translúcido azul na pose que ele manda. Cada quadro: primeiro todas as poses,
depois as câmeras, uma a uma. Então a pose não depende da câmera e a vista de planta, a de lado e a do jogador mostram o MESMO instante.

Cores: jogo com a cor natural do material (marcas laranja nos pontos medidos), modelo físico em azul translúcido (#2a78d6).
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

BLEND = os.path.join(ROOT, "out", "integration", "full.blend")
SAIDA = os.path.join(ROOT, "out", "f4_4", "final", "blender")
LARGURA, ALTURA = 640, 360
AZUL = (0.165, 0.471, 0.839)
LARANJA = (0.922, 0.408, 0.204)
OCULTAR = ("Ceiling_", "Roof_", "Trees_", "Neighbors", "Grass_Tufts", "PlayerBody", "Porch_Light", "FogBox_")


class Palco:
    """Cena do Blender pronta para renderizar os objetos reais e os fantasmas."""

    def __init__(self, largura=LARGURA, altura=ALTURA, caminho=BLEND):
        bpy.ops.wm.open_mainfile(filepath=caminho)
        self.cena = bpy.context.scene
        self.largura, self.altura = largura, altura
        self.fantasmas = []
        self._preparar()
        self.camera = None
        self._tmp = os.path.join(ROOT, "out", "f4_4", "tmp", f"render3d_{os.getpid()}.png")
        os.makedirs(os.path.dirname(self._tmp), exist_ok=True)

    # ------------------------------------------------------------------ cena
    def _preparar(self):
        cena = self.cena
        cena.render.engine = "BLENDER_WORKBENCH"
        cena.render.resolution_x, cena.render.resolution_y = self.largura, self.altura
        cena.render.resolution_percentage = 100
        cena.render.image_settings.file_format = "PNG"
        cena.display.render_aa = "FXAA"                    # 8 amostras custam 2,5x mais (rasterização em software) e a diferença não aparece
        sombreado = cena.display.shading
        sombreado.light = "STUDIO"
        sombreado.color_type = "MATERIAL"
        sombreado.show_object_outline = True
        sombreado.object_outline_color = (0.05, 0.05, 0.05)
        sombreado.show_cavity = False
        sombreado.show_shadows = False
        cena.world.color = (0.55, 0.57, 0.60)
        for material in bpy.data.materials:
            nos = material.node_tree.nodes if material.node_tree else []
            bsdf = next((n for n in nos if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is not None:
                c = bsdf.inputs["Base Color"].default_value
                material.diffuse_color = (c[0], c[1], c[2], 1.0)
            if "glass" in material.name or "windshield" in material.name:
                material.diffuse_color = (0.75, 0.88, 1.0, 0.12)
                self._transparente(material)
        for obj in bpy.data.objects:
            if obj.name.startswith(OCULTAR):
                obj.hide_render = obj.hide_viewport = True

    @staticmethod
    def _transparente(material):
        if hasattr(material, "blend_method"):
            material.blend_method = "BLEND"
        try:
            material.surface_render_method = "BLENDED"
        except (AttributeError, TypeError):
            pass
        material.use_backface_culling = False

    @staticmethod
    def _nos(material, cor, alfa, emissao):
        """Árvore de nós mínima (Principled com a cor e a alfa) para o EEVEE; o Workbench lê `diffuse_color`."""
        try:
            material.use_nodes = True
        except (AttributeError, TypeError):
            return
        arvore = material.node_tree
        bsdf = next((n for n in arvore.nodes if n.type == "BSDF_PRINCIPLED"), None) if arvore else None
        if bsdf is None:
            return
        bsdf.inputs["Base Color"].default_value = (*cor, 1.0)
        bsdf.inputs["Alpha"].default_value = alfa
        for nome in ("Emission Color", "Emission"):
            if nome in bsdf.inputs:
                bsdf.inputs[nome].default_value = (*cor, 1.0)
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emissao

    def material_fantasma(self, nome, cor=AZUL, alfa=0.38):
        material = bpy.data.materials.new(nome)
        material.diffuse_color = (*cor, alfa)
        self._transparente(material)
        self._nos(material, cor, alfa, 0.6)
        return material

    def material_marca(self, nome, cor=LARANJA):
        material = bpy.data.materials.new(nome)
        material.diffuse_color = (*cor, 1.0)
        self._nos(material, cor, 1.0, 0.25)
        return material

    # ------------------------------------------------------------------ objetos auxiliares
    def malha(self, nome, vertices, faces, material, pai=None, local=(0, 0, 0)):
        dados = bpy.data.meshes.new(nome)
        dados.from_pydata([tuple(v) for v in vertices], [], [tuple(f) for f in faces])
        dados.update()
        dados.materials.append(material)
        obj = bpy.data.objects.new(nome, dados)
        self.cena.collection.objects.link(obj)
        obj.parent = pai
        obj.location = local
        obj["fantasma"] = True
        return obj

    def caixa(self, nome, x0, y0, z0, x1, y1, z1, material, pai=None, local=(0, 0, 0)):
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        return self.malha(nome, v, f, material, pai, local)

    def esfera(self, nome, raio, material, pai=None, local=(0, 0, 0), na_frente=True):
        """Marca esférica de um ponto medido; `na_frente` a desenha por cima da geometria (um dado não fica atrás da folha)."""
        import bmesh
        dados = bpy.data.meshes.new(nome)
        malha = bmesh.new()
        bmesh.ops.create_icosphere(malha, subdivisions=2, radius=raio)
        malha.to_mesh(dados)
        malha.free()
        dados.materials.append(material)
        obj = bpy.data.objects.new(nome, dados)
        self.cena.collection.objects.link(obj)
        obj.parent = pai
        obj.location = local
        obj.show_in_front = na_frente
        obj["fantasma"] = True
        return obj

    def cilindro(self, nome, raio, comprimento, material, lados=28, pai=None, local=(0, 0, 0), eixo="x"):
        """Cilindro centrado na origem com o eixo ao longo de X (a roda do carro) ou de Y (a lentilha do pêndulo)."""
        v, f = [], []
        for k in range(lados):
            a = 2 * math.pi * k / lados
            c, s = raio * math.cos(a), raio * math.sin(a)
            h = comprimento / 2
            v += [(-h, c, s), (h, c, s)] if eixo == "x" else [(c, -h, s), (c, h, s)]
        for k in range(lados):
            j = (k + 1) % lados
            f.append((2 * k, 2 * j, 2 * j + 1, 2 * k + 1))
        f.append(tuple(2 * k for k in reversed(range(lados))))
        f.append(tuple(2 * k + 1 for k in range(lados)))
        return self.malha(nome, v, f, material, pai, local)

    # ------------------------------------------------------------------ câmeras
    def nova_camera(self, nome, local, alvo=None, ortografica=None, lente=None, fov=None, rotacao=None, corte=None):
        dados = bpy.data.cameras.new(nome)
        dados.sensor_fit = "HORIZONTAL"
        dados.clip_start, dados.clip_end = corte or (0.05, 200.0)
        if ortografica:
            dados.type = "ORTHO"
            dados.ortho_scale = ortografica
        elif fov:
            dados.angle = math.radians(fov)
        elif lente:
            dados.lens = lente
        cam = bpy.data.objects.new(nome, dados)
        self.cena.collection.objects.link(cam)
        cam.location = local
        if rotacao is not None:
            cam.rotation_euler = rotacao
        elif alvo is not None:
            self.mirar(cam, alvo)
        return cam

    @staticmethod
    def mirar(cam, alvo, cima="Y"):
        direcao = Vector(alvo) - Vector(cam.location)
        cam.rotation_euler = direcao.to_track_quat("-Z", cima).to_euler()

    def render(self, cam):
        self.cena.camera = cam
        self.cena.render.filepath = self._tmp
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
        from PIL import Image
        with Image.open(self._tmp) as imagem:
            return np.array(imagem.convert("RGB"))

    def projetar(self, cam, ponto):
        """(x, y) em pixels (y de cima) onde o ponto do mundo aparece na câmera; None se estiver atrás dela."""
        from bpy_extras.object_utils import world_to_camera_view
        bpy.context.view_layer.update()
        p = world_to_camera_view(self.cena, cam, Vector(ponto))
        if p.z <= 0:
            return None
        return (p.x * self.largura, (1.0 - p.y) * self.altura)


def ocultar_longe(palco, centro, raio, manter=()):
    """Esconde do render os objetos pequenos que estão a mais de `raio` m de `centro` (velocidade do Workbench).

    As matrizes do mundo são atualizadas antes: um objeto recém-criado ainda tem matriz identidade e pareceria estar na origem.
    Os objetos de marcação (propriedade `fantasma`) nunca são escondidos.
    """
    bpy.context.view_layer.update()
    centro = Vector(centro)
    for obj in bpy.data.objects:
        if obj.type not in ("MESH",) or obj.name.startswith(manter) or obj.get("fantasma") or len(obj.data.polygons) > 20000:
            continue
        caixa = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        meio = sum(caixa, Vector()) / 8.0
        if (meio - centro).length > raio:
            obj.hide_render = True
