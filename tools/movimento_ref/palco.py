"""Palco de estúdio: dois corpos do Daniel lado a lado (real à esquerda, jogo à direita) sob as mesmas câmeras.

    palco = Palco(640, 360)
    palco.vista("lado")                         # frente, lado, costas, topo, tres_quartos
    palco.pose_real(retarget, k)                # quadro k do Daniel retargetado (retarget.py)
    palco.pose_jogo(gravacao, j)                # quadro j da gravação do jogo (grava.py)
    palco.render("out/x/lado.png")
    palco.vista("primeira_pessoa", lado="real") # a câmera nos olhos: uma imagem por corpo

Tudo na mesma cena: o corpo "real" é uma cópia de `PlayerBody` movida pelo mocap retargetado e o corpo "jogo" é outra cópia
que reproduz, osso a osso, a pose gravada do `PlayerBody` do jogo. As câmeras são as mesmas para os dois.

Esteira: cada corpo fica parado no seu pedestal e o PISO anda por baixo dele, com o deslocamento real do corpo (e a rotação
da guinada). O piso é um xadrez de 0,5 m com listras; se o pé desliza, o olho vê o pé andar em relação ao xadrez.
Isto é o que permite colocar um mocap a 1,4 m/s e um jogo a 2,6 m/s no mesmo quadro sem que um saia da imagem.

Motor: Workbench (rápido, sem GPU) com textura, cavidade e contorno. `Palco.eevee()` liga o EEVEE para quadros de destaque.
Marcações de identidade (não fazem parte do corpo do jogo): esfera da cabeça e anel no chão, azul no real e laranja no jogo,
as mesmas cores dos gráficos. A malha do jogo não tem cabeça (primeira pessoa); a esfera deixa a silhueta legível.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Matrix, Quaternion, Vector  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.body import skeleton as S  # noqa: E402

COR_REAL = (0.165, 0.471, 0.839, 1.0)       # mesmas cores de graficos.py (azul e laranja)
COR_JOGO = (0.922, 0.408, 0.204, 1.0)
VISTAS = ("frente", "lado", "costas", "topo", "tres_quartos", "primeira_pessoa")
SEPARACAO = 1.25                             # metros do centro do palco a cada pedestal
BLOCO = 1.0                                  # lado, em metros, de um bloco do xadrez (2x2 quadrados de 0,5 m)

# vista -> (azimute da câmera em graus a partir de +Y no sentido horário visto de cima, elevação, distância, altura do alvo)
CAMERAS = {
    "frente": (0.0, 4.0, 5.0, 0.95),            # câmera em +Y, à frente do corpo, olhando para ele
    "costas": (180.0, 4.0, 5.0, 0.95),
    "lado": (90.0, 4.0, 5.0, 0.95),             # câmera à direita do corpo (+X): anda para a direita da imagem
    "tres_quartos": (45.0, 16.0, 5.2, 0.95),
    "topo": (0.0, 89.0, 6.2, 0.0),
}
FOV_TERCEIRA = 40.0


def _vetor(x):
    return Vector((float(x[0]), float(x[1]), float(x[2])))


# --------------------------------------------------------------------------
# Um corpo no palco
# --------------------------------------------------------------------------
class Fantoche:
    """Cópia de `PlayerBody` + `PlayerBody_Rig` com a pose dirigida por quaternions, não pelo `BodyRig`."""

    def __init__(self, cena, rig_fonte, malha_fonte, nome, cor):
        self.cena = cena
        self.cor = cor
        self.rig = rig_fonte.copy()
        self.rig.name = f"{nome}_Rig"
        self.malha = malha_fonte.copy()
        self.malha.name = nome
        for obj in (self.rig, self.malha):
            for colecao in list(obj.users_collection):
                colecao.objects.unlink(obj)
            cena.collection.objects.link(obj)
        self.malha.parent = self.rig
        self.malha.matrix_parent_inverse = Matrix.Identity(4)
        self.malha.data = self.malha.data.copy()
        self._materiais_de_exibicao()
        for modificador in self.malha.modifiers:
            if modificador.type == "ARMATURE":
                modificador.object = self.rig
        self.malha.hide_viewport = self.malha.hide_render = False
        self.rig.hide_viewport = self.rig.hide_render = False
        if hasattr(self.malha, "visible_shadow"):
            self.malha.visible_shadow = True
        self.ossos = []
        for nome_osso in S.BONE_ORDER:
            osso = self.rig.pose.bones[nome_osso]
            repouso = osso.bone.matrix_local.to_3x3().to_quaternion()
            self.ossos.append((osso, repouso, repouso.inverted()))
        self.marcas = self._criar_marcas(nome)
        self.tronco = None

    def _materiais_de_exibicao(self):
        """Cores de exibição para o Workbench: o corpo do jogo usa texturas procedurais que o Workbench não lê."""
        from sem_alvorada.body import materials as M
        cores = {"skin": (0.80, 0.58, 0.46), "nail": (0.90, 0.78, 0.72), "flannel": (0.55, 0.13, 0.10),
                 "denim": (0.17, 0.24, 0.40), "denim_hip": (0.17, 0.24, 0.40), "leather": (0.30, 0.18, 0.10),
                 "sole": (0.10, 0.09, 0.08), "button": (0.85, 0.82, 0.75), "metal": (0.65, 0.65, 0.68),
                 "lace": (0.88, 0.86, 0.80), "gold": (0.85, 0.68, 0.20)}
        dados = self.malha.data
        for indice, nome in enumerate(M.SLOT_ORDER):
            material = bpy.data.materials.new(f"{self.malha.name}_{nome}")
            material.use_nodes = False
            material.diffuse_color = (*cores[nome], 1.0)
            if indice < len(dados.materials):
                dados.materials[indice] = material

    # ---- marcações de identidade ----
    def _criar_marcas(self, nome):
        import bmesh
        material = bpy.data.materials.new(f"{nome}_cor")
        material.diffuse_color = self.cor
        material.use_nodes = False

        def esfera(sufixo, raio, segmentos, aneis):
            malha = bpy.data.meshes.new(f"{nome}_{sufixo}")
            construtor = bmesh.new()
            bmesh.ops.create_uvsphere(construtor, u_segments=segmentos, v_segments=aneis, radius=raio)
            construtor.to_mesh(malha)
            construtor.free()
            obj = bpy.data.objects.new(f"{nome}_{sufixo}", malha)
            obj.data.materials.append(material)
            obj.color = self.cor
            self.cena.collection.objects.link(obj)
            obj.parent = self.rig
            obj.parent_type = "BONE"
            obj.parent_bone = "Neck"
            return obj

        # o filho de um osso tem a origem na ponta dele; o centro da cabeça fica 4,5 cm além, ao longo do osso
        cabeca = esfera("cabeca", 0.098, 20, 12)
        cabeca.location = (0.0, 0.045, 0.0)
        nariz = esfera("nariz", 0.028, 10, 6)
        repouso = self.rig.pose.bones["Neck"].bone.matrix_local.to_3x3()
        # a frente do corpo (+Y do corpo) escrita no referencial do osso: local = R^-1 @ v
        nariz.location = repouso.inverted() @ Vector((0.0, 0.095, -0.03)) + Vector((0.0, 0.045, 0.0))
        return {"cabeca": cabeca, "nariz": nariz, "anel": self._anel(nome, material), "material": material}

    def _anel(self, nome, material):
        """Anel fino colorido no chão ao redor do pedestal (a identidade vista de cima e de longe)."""
        import bmesh
        malha = bpy.data.meshes.new(f"{nome}_anel")
        construtor = bmesh.new()
        angulos = np.linspace(0, 2 * math.pi, 64, endpoint=False)
        externo = [construtor.verts.new((0.64 * math.cos(a), 0.64 * math.sin(a), 0.004)) for a in angulos]
        interno = [construtor.verts.new((0.56 * math.cos(a), 0.56 * math.sin(a), 0.004)) for a in angulos]
        for i in range(64):
            j = (i + 1) % 64
            construtor.faces.new((externo[i], externo[j], interno[j], interno[i]))
        construtor.to_mesh(malha)
        construtor.free()
        anel = bpy.data.objects.new(f"{nome}_anel", malha)
        anel.data.materials.append(material)
        anel.color = self.cor
        self.cena.collection.objects.link(anel)
        return anel

    # ---- visibilidade ----
    def visivel(self, sim):
        for obj in (self.malha, self.rig, self.marcas["cabeca"], self.marcas["nariz"], self.marcas["anel"]):
            obj.hide_render = obj.hide_viewport = not sim

    def mostrar_marcas(self, sim):
        for chave in ("cabeca", "nariz", "anel"):
            self.marcas[chave].hide_render = self.marcas[chave].hide_viewport = not sim

    # ---- pose ----
    def colocar(self, centro, guinada, z=0.0):
        self.rig.location = (centro[0], centro[1], z)
        self.rig.rotation_euler = (0.0, 0.0, guinada)
        anel = self.marcas["anel"]
        anel.location = (centro[0], centro[1], 0.0)

    def aplicar_solver(self, locais, deslocamento_quadril, escala_peito=(1.0, 1.0, 1.0)):
        """`locais` [B,4] (w,x,y,z) na convenção do solver; `deslocamento_quadril` em eixos do corpo."""
        for i, (osso, repouso, repouso_inv) in enumerate(self.ossos):
            osso.rotation_quaternion = repouso_inv @ Quaternion(tuple(locais[i])) @ repouso
        osso, repouso, repouso_inv = self.ossos[0]
        osso.location = repouso_inv @ _vetor(deslocamento_quadril)
        self.rig.pose.bones["Chest"].scale = tuple(escala_peito)

    def aplicar_gravado(self, pose_b, quadril_loc, escala_peito):
        """Reproduz a pose como ela foi escrita na armadura do jogo (`rotation_quaternion` de cada pose bone)."""
        for i, (osso, _repouso, _inv) in enumerate(self.ossos):
            osso.rotation_quaternion = tuple(pose_b[i])
        self.ossos[0][0].location = tuple(quadril_loc)
        self.rig.pose.bones["Chest"].scale = tuple(escala_peito)

    def posicoes(self):
        """Cabeça de cada osso no mundo (palco), [B, 3], da armadura avaliada agora."""
        avaliada = self.rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mundo = avaliada.matrix_world
        return np.array([tuple(mundo @ avaliada.pose.bones[nome].head) for nome in S.BONE_ORDER])

    def olho(self):
        """Posição do olho no mundo (palco), do esqueleto avaliado agora."""
        avaliada = self.rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        pescoco = avaliada.pose.bones["Neck"]
        repouso = pescoco.bone.matrix_local.to_3x3()
        q_abs = pescoco.matrix.to_3x3() @ repouso.inverted()
        return avaliada.matrix_world @ (pescoco.head + q_abs @ S.EYE_FROM_C7)


# --------------------------------------------------------------------------
# Piso de esteira
# --------------------------------------------------------------------------
def imagem_xadrez(nome="xadrez_palco", tamanho=1024):
    """Xadrez de 2x2 quadrados por bloco, com um fio vermelho em volta de cada bloco para o olho enxergar deslocamentos
    finos. É gravado em PNG e carregado do disco: o Workbench não mostra imagens geradas na memória."""
    existente = bpy.data.images.get(nome)
    if existente is not None:
        return existente
    from PIL import Image
    n = tamanho
    quadrado = n // 2
    y, x = np.mgrid[0:n, 0:n]
    claro = np.array([200, 200, 194], np.uint8)
    escuro = np.array([118, 120, 122], np.uint8)
    imagem = np.where(((x // quadrado) + (y // quadrado))[..., None] % 2 == 0, claro, escuro).astype(np.uint8)
    fio = 6
    for coord in (x, y):
        imagem[(coord < fio) | (coord >= n - fio)] = np.array([205, 46, 38], np.uint8)
    caminho = os.path.join(ROOT, "out", "f4_1", f"{nome}.png")
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    Image.fromarray(imagem).save(caminho)
    img = bpy.data.images.load(caminho)
    img.name = nome
    img.colorspace_settings.name = "sRGB"
    return img


class Piso:
    """Retângulo com xadrez cujas UVs andam: o chão desliza por baixo do corpo que fica parado."""

    def __init__(self, cena, nome):
        self.cena = cena
        self.malha = bpy.data.meshes.new(nome)
        self.malha.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
        self.malha.uv_layers.new(name="UVMap")
        self.obj = bpy.data.objects.new(nome, self.malha)
        cena.collection.objects.link(self.obj)
        material = bpy.data.materials.new(f"{nome}_mat")
        material.use_nodes = True
        arvore = material.node_tree
        for no in list(arvore.nodes):
            arvore.nodes.remove(no)
        saida = arvore.nodes.new("ShaderNodeOutputMaterial")
        bsdf = arvore.nodes.new("ShaderNodeBsdfPrincipled")
        textura = arvore.nodes.new("ShaderNodeTexImage")
        textura.image = imagem_xadrez()
        textura.interpolation = "Linear"
        textura.extension = "REPEAT"
        arvore.links.new(textura.outputs["Color"], bsdf.inputs["Base Color"])
        arvore.links.new(bsdf.outputs["BSDF"], saida.inputs["Surface"])
        arvore.nodes.active = textura
        self.malha.materials.append(material)
        self.meia_largura = self.meia_profundidade = 1.0
        self.azimute = 0.0

    def dimensionar(self, centro, azimute, largura, profundidade):
        """Posição e tamanho do retângulo no palco. `azimute`: giro (rad) do eixo X do retângulo em torno de Z."""
        self.meia_largura, self.meia_profundidade = largura / 2.0, profundidade / 2.0
        self.azimute = azimute
        self.obj.location = (centro[0], centro[1], 0.0)
        self.obj.rotation_euler = (0.0, 0.0, azimute)
        self.malha.vertices.foreach_set("co", np.array([(-self.meia_largura, -self.meia_profundidade, 0), (self.meia_largura, -self.meia_profundidade, 0),
                                                         (self.meia_largura, self.meia_profundidade, 0), (-self.meia_largura, self.meia_profundidade, 0)],
                                                        np.float32).ravel())
        self.malha.update()

    def visivel(self, sim):
        self.obj.hide_render = self.obj.hide_viewport = not sim

    def deslocar(self, centro, posicao_mundo, guinada_inicial):
        """UVs: o ponto do piso sob o vértice `v` (no palco) é o ponto do mundo `posicao_mundo + Rz(psi0) (v - centro)`."""
        c, s = math.cos(self.azimute), math.sin(self.azimute)
        c0, s0 = math.cos(guinada_inicial), math.sin(guinada_inicial)
        uv = []
        for lx, ly in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            lx, ly = lx * self.meia_largura, ly * self.meia_profundidade
            vx, vy = c * lx - s * ly, s * lx + c * ly                # offset do vértice ao centro, no palco
            wx = posicao_mundo[0] + c0 * vx - s0 * vy
            wy = posicao_mundo[1] + s0 * vx + c0 * vy
            uv.extend((wx / BLOCO, wy / BLOCO))
        self.malha.uv_layers["UVMap"].data.foreach_set("uv", [uv[0], uv[1], uv[2], uv[3], uv[4], uv[5], uv[6], uv[7]])


# --------------------------------------------------------------------------
# O palco
# --------------------------------------------------------------------------
class Palco:
    def __init__(self, largura=640, altura=360, motor="workbench"):
        from sem_alvorada import build as build_module
        from sem_alvorada.body import build as build_body
        from sem_alvorada.buildctx import BuildContext
        self.cena = build_module.fresh_scene()
        contexto = BuildContext(self.cena, verbose=False)
        contexto.stage = "body"
        build_body(contexto)
        bpy.context.view_layer.update()
        rig = bpy.data.objects[C.OBJ_BODY_RIG]
        malha = bpy.data.objects[C.OBJ_BODY]
        self.real = Fantoche(self.cena, rig, malha, "real", COR_REAL)
        self.jogo = Fantoche(self.cena, rig, malha, "jogo", COR_JOGO)
        for original in (rig, malha):
            original.hide_render = original.hide_viewport = True
        self.piso_real, self.piso_jogo = Piso(self.cena, "piso_real"), Piso(self.cena, "piso_jogo")
        self.postes = self._criar_postes()
        self.largura, self.altura = largura, altura
        self.vista_atual = None
        self.camera = self._criar_camera()
        self._configurar_render(motor)
        self._luzes()
        self.pedestal = {"real": (-SEPARACAO, 0.0), "jogo": (SEPARACAO, 0.0)}
        self._origem = {"real": None, "jogo": None}      # (x, y, guinada) do primeiro quadro de cada corpo, no mundo dele
        # um arquivo por processo: várias comparações podem rodar ao mesmo tempo
        self.arquivo_temporario = os.path.join(ROOT, "out", "movimento", f"_quadro_{os.getpid()}.png")
        os.makedirs(os.path.dirname(self.arquivo_temporario), exist_ok=True)

    # ---- montagem ----
    def _criar_camera(self):
        dados = bpy.data.cameras.new("camera_palco")
        dados.sensor_fit = "HORIZONTAL"
        dados.lens_unit = "FOV"
        dados.angle = math.radians(FOV_TERCEIRA)
        dados.clip_start, dados.clip_end = 0.05, 200.0
        camera = bpy.data.objects.new("camera_palco", dados)
        self.cena.collection.objects.link(camera)
        self.cena.camera = camera
        return camera

    def _criar_postes(self):
        """Postes finos ao longe, parados no palco: dão à câmera dos olhos um horizonte com relevo para o balanço da
        cabeça aparecer (só entram na primeira pessoa)."""
        import bmesh
        material = bpy.data.materials.new("poste_palco")
        material.use_nodes = False
        material.diffuse_color = (0.22, 0.24, 0.30, 1.0)
        postes = []
        for i, (x, y) in enumerate(((-3.2, 7.0), (2.6, 9.0), (-1.0, 12.5), (4.5, 14.0), (-5.0, 16.0), (0.8, 19.0), (-2.6, 22.0))):
            malha = bpy.data.meshes.new(f"poste_{i}")
            construtor = bmesh.new()
            bmesh.ops.create_cone(construtor, cap_ends=True, segments=8, radius1=0.07, radius2=0.07, depth=3.2)
            construtor.to_mesh(malha)
            construtor.free()
            poste = bpy.data.objects.new(f"poste_{i}", malha)
            poste.data.materials.append(material)
            poste.location = (x, y, 1.6)
            self.cena.collection.objects.link(poste)
            poste.hide_render = poste.hide_viewport = True
            postes.append(poste)
        return postes

    def _configurar_render(self, motor):
        cena = self.cena
        cena.render.resolution_x, cena.render.resolution_y = self.largura, self.altura
        cena.render.resolution_percentage = 100
        cena.render.image_settings.file_format = "PNG"
        cena.render.image_settings.color_mode = "RGB"
        cena.view_settings.view_transform = "Standard"
        cena.view_settings.look = "None"
        cena.render.film_transparent = False
        mundo = bpy.data.worlds.new("mundo_palco")
        mundo.use_nodes = False
        mundo.color = (0.60, 0.63, 0.66)
        cena.world = mundo
        if motor == "eevee":
            self.eevee()
        else:
            self.workbench()

    def workbench(self):
        cena = self.cena
        cena.render.engine = "BLENDER_WORKBENCH"
        sombra = cena.display.shading
        sombra.light = "STUDIO"
        sombra.color_type = "TEXTURE"
        sombra.show_cavity = True
        sombra.cavity_type = "BOTH"
        sombra.cavity_ridge_factor = 1.0
        sombra.cavity_valley_factor = 1.2
        sombra.show_object_outline = True
        sombra.object_outline_color = (0.05, 0.05, 0.06)
        sombra.show_shadows = True
        sombra.shadow_intensity = 0.35
        sombra.show_specular_highlight = False
        cena.display.render_aa = "8"
        self.motor = "workbench"

    def eevee(self, amostras=16):
        from sem_alvorada import compat
        compat.use_eevee(self.cena)
        try:
            self.cena.eevee.taa_render_samples = amostras
        except AttributeError:
            pass
        self.motor = "eevee"

    def _luzes(self):
        dados = bpy.data.lights.new("sol_palco", "SUN")
        dados.energy = 3.0
        dados.angle = math.radians(25)
        sol = bpy.data.objects.new("sol_palco", dados)
        sol.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
        self.cena.collection.objects.link(sol)
        dados = bpy.data.lights.new("preenche_palco", "AREA")
        dados.energy = 200.0
        dados.size = 5.0
        area = bpy.data.objects.new("preenche_palco", dados)
        area.location = (-3.0, -3.0, 4.0)
        area.rotation_euler = (math.radians(55), 0.0, math.radians(-40))
        self.cena.collection.objects.link(area)

    # ---- vistas ----
    def vista(self, nome, lado="ambos", fov=None):
        """Posiciona câmera, pedestais e pisos. Na primeira pessoa, `lado` ("real" ou "jogo") escolhe qual corpo aparece."""
        if nome not in VISTAS:
            raise KeyError(f"vista desconhecida: {nome!r} (use {', '.join(VISTAS)})")
        self.vista_atual, self.lado_atual = nome, lado
        for poste in self.postes:
            poste.hide_render = poste.hide_viewport = nome != "primeira_pessoa"
        if nome == "primeira_pessoa":
            return self._vista_primeira_pessoa(lado)
        azimute, elevacao, distancia, altura_alvo = CAMERAS[nome]
        az, el = math.radians(azimute), math.radians(elevacao)
        # câmera a `azimute` graus de +Y, no sentido horário visto de cima: (sin az, cos az) é para onde ela fica
        direcao = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
        alvo = Vector((0.0, 0.0, altura_alvo))
        self.camera.location = alvo + direcao * distancia
        if nome == "topo":
            self.camera.rotation_euler = (0.0, 0.0, 0.0)                      # olha para baixo, topo da imagem = +Y
        else:
            apontar = (alvo - self.camera.location)
            self.camera.rotation_euler = apontar.to_track_quat("-Z", "Y").to_euler()
        self.camera.data.angle = math.radians(fov or FOV_TERCEIRA)
        direita = Vector((-math.cos(az), math.sin(az), 0.0))                  # eixo horizontal da imagem (frente x cima)
        if nome == "topo":
            direita = Vector((1.0, 0.0, 0.0))
        self.pedestal = {"real": (-direita.x * SEPARACAO, -direita.y * SEPARACAO), "jogo": (direita.x * SEPARACAO, direita.y * SEPARACAO)}
        azimute_piso = math.atan2(direita.y, direita.x)
        for lado_corpo, piso in (("real", self.piso_real), ("jogo", self.piso_jogo)):
            piso.dimensionar(self.pedestal[lado_corpo], azimute_piso, 2 * SEPARACAO - 0.12, 5.5)
            piso.visivel(True)
        for corpo in (self.real, self.jogo):
            corpo.visivel(True)
            corpo.mostrar_marcas(True)
        self.real.colocar(self.pedestal["real"], 0.0)
        self.jogo.colocar(self.pedestal["jogo"], 0.0)

    def _vista_primeira_pessoa(self, lado):
        corpo, piso, outro, outro_piso = (self.real, self.piso_real, self.jogo, self.piso_jogo) if lado == "real" \
            else (self.jogo, self.piso_jogo, self.real, self.piso_real)
        outro.visivel(False)
        outro_piso.visivel(False)
        corpo.visivel(True)
        corpo.mostrar_marcas(False)
        self.pedestal[lado] = (0.0, 0.0)
        piso.dimensionar((0.0, 0.0), 0.0, 60.0, 60.0)
        piso.visivel(True)
        corpo.colocar((0.0, 0.0), 0.0)
        self.camera.data.angle = math.radians(C.FOV_DEG)

    # ---- origem de cada corpo (primeiro quadro do trecho) ----
    def origem(self, lado, xy, guinada):
        self._origem[lado] = (float(xy[0]), float(xy[1]), float(guinada))

    # ---- poses ----
    def _atualizar_piso(self, lado, xy, guinada, z=0.0):
        corpo = self.real if lado == "real" else self.jogo
        piso = self.piso_real if lado == "real" else self.piso_jogo
        x0, y0, g0 = self._origem[lado]
        centro = self.pedestal[lado]
        corpo.colocar(centro, guinada - g0, z)
        piso.deslocar(centro, (xy[0], xy[1]), g0)

    @staticmethod
    def _quaternions(tabela, k):
        """Interpola quaternions [..., 4] entre os quadros vizinhos de k (fracionário): nlerp com o sinal alinhado."""
        i0 = int(np.clip(math.floor(k), 0, len(tabela) - 1))
        i1 = min(i0 + 1, len(tabela) - 1)
        f = float(np.clip(k - i0, 0.0, 1.0))
        a, b = tabela[i0], tabela[i1]
        sinal = np.where((a * b).sum(axis=-1, keepdims=True) < 0, -1.0, 1.0)
        q = a * (1 - f) + b * sinal * f
        return q / np.linalg.norm(q, axis=-1, keepdims=True)

    @staticmethod
    def _linear(tabela, k):
        i0 = int(np.clip(math.floor(k), 0, len(tabela) - 1))
        i1 = min(i0 + 1, len(tabela) - 1)
        f = float(np.clip(k - i0, 0.0, 1.0))
        return tabela[i0] * (1 - f) + tabela[i1] * f

    def pose_real(self, alvo, k):
        """Quadro k (pode ser fracionário) de um `Retarget`."""
        raiz = self._linear(alvo.raiz, k)
        if self._origem["real"] is None:
            self.origem("real", alvo.raiz[0, :2], alvo.raiz[0, 3])
        self.real.aplicar_solver(self._quaternions(alvo.locais, k), self._linear(alvo.deslocamento_quadril, k))
        self._atualizar_piso("real", raiz[:2], raiz[3], raiz[2])

    def pose_jogo(self, gravacao, j):
        """Quadro j (pode ser fracionário) de uma `Gravacao` com ossos."""
        raiz = self._linear(gravacao.raiz, j)
        if self._origem["jogo"] is None:
            self.origem("jogo", gravacao.raiz[0, :2], gravacao.raiz[0, 3])
        self.jogo.aplicar_gravado(self._quaternions(gravacao.pose_b, j), self._linear(gravacao.quadril_loc, j),
                                  self._linear(gravacao.escala_peito, j))
        self._atualizar_piso("jogo", raiz[:2], raiz[3], raiz[2] - gravacao.raiz[0, 2])

    def para_palco(self, lado, ponto_mundo, raiz_xy, z_base=0.0):
        """Converte um ponto do mundo do corpo `lado` para o palco: tira o deslocamento da raiz, gira pela guinada inicial
        (o mesmo movimento do piso) e põe no pedestal."""
        g0 = self._origem[lado][2]
        dx, dy = ponto_mundo[0] - raiz_xy[0], ponto_mundo[1] - raiz_xy[1]
        c, s = math.cos(-g0), math.sin(-g0)
        centro = self.pedestal[lado]
        return Vector((centro[0] + c * dx - s * dy, centro[1] + s * dx + c * dy, ponto_mundo[2] - z_base))

    def rotacao_para_palco(self, lado, rotacao_mundo):
        """Orientação (3x3) de uma câmera do mundo do corpo `lado`, vista do palco."""
        g0 = self._origem[lado][2]
        return np.array(Matrix.Rotation(-g0, 3, "Z")) @ np.asarray(rotacao_mundo)

    def camera_na_primeira_pessoa(self, posicao_palco, rotacao_palco):
        """Põe a câmera do palco no olhar dado (posição e matriz de câmera do Blender, ambas já em coordenadas do palco)."""
        self.camera.location = posicao_palco
        self.camera.rotation_euler = Matrix(np.asarray(rotacao_palco).tolist()).to_euler()

    def olho_do_corpo(self, lado):
        """Olho (palco) do esqueleto posado do corpo `lado`."""
        bpy.context.view_layer.update()
        return (self.real if lado == "real" else self.jogo).olho()

    # ---- saída ----
    def render(self, caminho=None):
        caminho = caminho or self.arquivo_temporario
        self.cena.render.filepath = caminho
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
        return caminho

    def render_array(self):
        """Renderiza e devolve a imagem como array uint8 [altura, largura, 3]."""
        from PIL import Image
        caminho = self.render()
        with Image.open(caminho) as imagem:
            return np.array(imagem.convert("RGB"))

    def projetar(self, ponto):
        """Pixel (x, y, de cima) onde o ponto do palco aparece na câmera atual; None se atrás dela."""
        from bpy_extras.object_utils import world_to_camera_view
        bpy.context.view_layer.update()
        p = world_to_camera_view(self.cena, self.camera, Vector(ponto))
        if p.z <= 0:
            return None
        return (p.x * self.largura, (1.0 - p.y) * self.altura)
