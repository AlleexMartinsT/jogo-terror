"""Pegadas: como os dedos seguram cada item, medido na pele e fotografado de várias câmeras.

    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.pegadas medir out/f5_2/depois_pele.json
    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.pegadas fotos out/f5_2/fotos [--motor eevee]

`medir` segura cada item (lanterna na direita; chave, pilha, mapa e anotação na esquerda), deixa o corpo assentar e mede
na MALHA DE PELE já deformada pelo esqueleto: a penetração máxima e a folga mínima de cada parte da mão (polegar, quatro
dedos e palma) contra a malha do item, em milímetros. `fotos` renderiza o mesmo estado de quatro câmeras de estúdio e da
câmera do jogador. As funções servem também ao `tests/test_pegadas.py` e aos painéis de antes e depois.
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from sem_alvorada import compat  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.body import grasp  # noqa: E402
from sem_alvorada.engine import handclips  # noqa: E402
from sem_alvorada.engine.inputstate import InputState  # noqa: E402
from tools.movimento_ref.cenarios import maos  # noqa: E402

# item -> (lado da mão, estado do jogo que o põe na mão)
ITENS = {
    C.ITEM_FLASHLIGHT: ("R", {}),
    C.ITEM_KEY: ("L", dict(chave=True, segurar=C.ITEM_KEY)),
    C.ITEM_BATTERY: ("L", dict(pilhas=2, segurar=C.ITEM_BATTERY)),
    C.ITEM_MAP: ("L", dict(mapa=True, segurar=C.ITEM_MAP)),
    C.ITEM_NOTE: ("L", dict(notas=("NOTE_1",), segurar=C.ITEM_NOTE)),
}
FOLHAS = (C.ITEM_MAP, C.ITEM_NOTE)
# quem deve tocar o item em cada pegada (o resto é "livre": a folga dele não é defeito)
CONTATOS = {
    C.ITEM_FLASHLIGHT: ("Index", "Middle", "Ring", "Pinky", "Palm"),
    C.ITEM_KEY: ("Thumb", "Index"),
    C.ITEM_BATTERY: ("Palm", "Thumb", "Index", "Middle"),
    C.ITEM_MAP: ("Thumb", "Index", "Middle"),
    C.ITEM_NOTE: ("Thumb", "Index", "Middle"),
}


def assentar(jogo, segundos=2.5):
    """Deixa as mãos e o corpo chegarem ao repouso e atualiza o grafo de dependências."""
    for _ in range(int(segundos * 60)):
        jogo.tick(1 / 60, InputState())
    jogo._sync_camera()
    bpy.context.view_layer.update()


def preparar(item, **opcoes):
    """Jogo de palco mínimo com `item` na mão certa. Devolve (jogo, lado)."""
    lado, estado = ITENS[item]
    jogo = maos.montar_jogo_maos(None)
    maos.estado(jogo, **{**estado, **opcoes})
    assentar(jogo)
    return jogo, lado


def objetos_do_item(jogo, item):
    modelos = jogo.hands.models
    if item == C.ITEM_MAP:
        return [o for o in (modelos.objects[item], *modelos.panels) if o is not None]
    return [modelos.objects[item]]


MATERIAIS = {C.ITEM_FLASHLIGHT: ("flash_aluminum", "flash_knurled", "rubber")}      # o resto é interno ao modelo


def forma_do_item(jogo, item, frame=None):
    return grasp.ItemShape(objetos_do_item(jogo, item), frame=frame, sheet=item in FOLHAS, materials=MATERIAIS.get(item))


def medir_item(jogo, item, lado):
    """{parte: {pen, gap, touch}} em mm para o item na mão `lado`, na pele deformada de agora."""
    corpo = bpy.data.objects[C.OBJ_BODY]
    return grasp.measure_skin(corpo, forma_do_item(jogo, item), lado)


def resumo(medidas, item):
    """Penetração máxima, folga média dos que devem tocar e quantos tocam de fato (folga < 2 mm)."""
    deve = CONTATOS[item]
    folgas = [medidas[p]["gap"] for p in deve]
    return {"pen_max": max(m["pen"] for m in medidas.values()), "folga_media": sum(folgas) / len(folgas),
            "tocam": sum(1 for g in folgas if g < 2.0), "deveriam": len(deve)}


def medir_tudo(saida=None, itens=None, **opcoes):
    resultado = {}
    for item in itens or ITENS:
        jogo, lado = preparar(item, **opcoes)
        resultado[item] = {"lado": lado, "partes": medir_item(jogo, item, lado)}
        resultado[item]["resumo"] = resumo(resultado[item]["partes"], item)
        print(item, lado, {k: (round(v["pen"], 1), round(v["gap"], 1)) for k, v in resultado[item]["partes"].items()},
              resultado[item]["resumo"], flush=True)
    if saida:
        os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
        with open(saida, "w", encoding="utf-8") as arquivo:
            json.dump(resultado, arquivo, ensure_ascii=False, indent=1)
    return resultado


# ---------------------------------------------------------------------------
# Gerar os dados: ajusta a mão ao item e fecha os dedos (offline); o jogo só lê sem_alvorada/grasp_data.py
# ---------------------------------------------------------------------------
DADOS = os.path.join(ROOT, "sem_alvorada", "grasp_data.py")


def _item_frame(objeto):
    loc, rot, _ = objeto.matrix_world.decompose()
    return Matrix.LocRotScale(loc, rot, None).inverted()


def papel_do_item(item):
    """(Role, materiais da malha, materiais da meta do polegar, materiais do item sem o botão, giro de busca)."""
    G = grasp
    if item == C.ITEM_FLASHLIGHT:
        return (G.Role(power=("Index", "Middle", "Ring", "Pinky"), thumb="hover", thumb_hover=0.003, palm_gap=0.003),
                MATERIAIS[item], ("rubber",), ("flash_aluminum", "flash_knurled"), ("Z", *range(-180, 180, 20)))
    if item == C.ITEM_KEY:
        return (G.Role(pinch=("Index",), thumb="contact", free={"Middle": G.free_row(0.42), "Ring": G.free_row(0.50),
                                                                 "Pinky": G.free_row(0.56)}), None, None, None, None)
    if item == C.ITEM_BATTERY:
        return (G.Role(cup=("Index", "Middle", "Ring", "Pinky"), thumb="contact", palm_gap=0.0008), None, None, None, None)
    return (G.Role(pinch=("Index", "Middle", "Ring"), thumb="contact", sheet=True, free={"Pinky": G.free_row(0.30)}),
            None, None, None, None)


def verificador_de_braco(jogo, item, lado, peso=0.004):
    """Penalidade para `fit_grip`: o braço tem de alcançar a mão em todas as poses em que o item aparece (parado, rosto,
    perto). Pede ao IK do corpo de verdade e soma peso * (desvio de orientação em graus)^2 mais o erro de alcance."""
    from types import SimpleNamespace
    from mathutils import Euler
    from sem_alvorada.body import solver
    arm = jogo.body.arm(lado)
    frame = SimpleNamespace(body_from_world=Matrix.Rotation(-jogo.body._yaw, 3, "Z"), root=Vector(jogo.body._root))
    view = (Vector(jogo.hands._cam[0].translation), jogo.hands._cam[0].to_3x3())
    poses = [handclips.pose_matrix(*handclips.MODE_POSES[modo].get((lado, item), handclips.HOLD_ITEM[(lado, item)]))
             for modo in ("hold", "face", "near") if (lado, item) in handclips.MODE_POSES[modo] or modo == "hold"]
    indice = grasp.S.BONE_INDEX[f"Hand.{lado}"]

    def penalidade(matriz):
        pior = 0.0
        for pose in poses:
            mao = pose @ matriz
            euler = Euler(mao.to_3x3().to_euler("XYZ"))
            arm.set_target(tuple(mao.translation), tuple(math.degrees(a) for a in euler), 1.0)
            arm.wrist_comfort = True
            meta = arm._goal(frame, view)
            solucao = solver.solve(solver.PoseSpec(arms={lado: meta}))
            desvio = math.degrees((meta.hand_q.to_matrix().inverted() @ solucao.world[indice].to_matrix()).to_quaternion().angle)
            erro = max(solucao.reach_error.values()) * 1000.0
            pior = max(pior, desvio * desvio + 4.0 * erro * erro)
        arm.release()
        return peso * pior
    return penalidade


def ajustar_item(item, jogo=None, inicio=None, **opcoes):
    """Ajusta a mão de `item` (`grasp.fit_grip`) e devolve (matriz da mão no item, Grasp, custo, giro do scan, forma)."""
    jogo, lado = (jogo, ITENS[item][0]) if jogo is not None else preparar(item)
    objetos = objetos_do_item(jogo, item)
    frame = _item_frame(objetos[0])
    papel, materiais, meta, sem_botao, busca = papel_do_item(item)
    forma = grasp.ItemShape(objetos, frame=frame, sheet=item in FOLHAS, materials=materiais)
    alvo = grasp.ItemShape(objetos, frame=frame, materials=meta) if meta else None
    solto = grasp.ItemShape(objetos, frame=frame, materials=sem_botao) if sem_botao else None
    pele = grasp.HandSkin(bpy.data.objects[C.OBJ_BODY], lado)
    partida = inicio if inicio is not None else handclips.LEGACY_GRIPS[item].matrix
    resultado = grasp.fit_grip(item, lado, partida, forma, papel, pele, goal_shape=alvo, press_shape=solto, scan=busca,
                               extra=verificador_de_braco(jogo, item, lado), **opcoes)
    return (*resultado, forma)


def gerar(itens=None):
    """Roda `ajustar_item` para cada item e regrava `sem_alvorada/grasp_data.py` (mantém o que não foi refeito)."""
    dados = {"grips": {}, "grasps": {}, "roll": {}}
    try:
        from sem_alvorada import grasp_data
        dados["grips"].update(grasp_data.GRIPS)
        dados["grasps"].update(grasp_data.GRASPS)
        dados["roll"].update(grasp_data.ROLL_SHIFT)
    except ImportError:
        pass
    for item in itens or ITENS:
        matriz, g, custo, giro, _forma = ajustar_item(item)
        dados["grips"][item] = tuple(tuple(round(v, 5) for v in vec) for vec in grasp.grip_from_matrix(matriz))
        dados["grasps"][item] = {"side": g.side, "closed": [[round(v, 4) for v in row] for row in g.closed],
                                 "preform": [[round(v, 4) for v in row] for row in g.preform],
                                 "pressed": [round(v, 4) for v in g.pressed] if g.pressed else None}
        dados["roll"][item] = round(giro, 3)
        print(item, "custo", round(custo, 5), "giro", giro, {k: (v[0], round(v[1], 3)) for k, v in g.touches.items()}, flush=True)
    linhas = ['"""Pegadas calculadas por contato (gerado por `python -m tools.movimento_ref.cenarios.pegadas gerar`; não edite).',
              "", "GRIPS: a mão no referencial do item (posição, direção dos dedos, direção da palma). GRASPS: curls por junta",
              "(polegar ao mindinho, base à ponta) da mão fechada no item e da pré-forma aberta. ROLL_SHIFT: quanto a mão",
              "girou em torno do eixo do item, em graus (a lanterna gira o contrário para a mão ficar onde estava).", '"""',
              f"GRIPS = {dados['grips']!r}", f"GRASPS = {dados['grasps']!r}", f"ROLL_SHIFT = {dados['roll']!r}", ""]
    with open(DADOS, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas))
    print("gravado", DADOS)


# ---------------------------------------------------------------------------
# Estúdio: fundo cinza, luz suave e câmeras ao redor da mão
# ---------------------------------------------------------------------------
class Estudio:
    """Põe câmeras de estúdio ao redor do item na mão e renderiza (Workbench rápido ou EEVEE)."""
    VISTAS = {            # nome: (direção do olho ao alvo no mundo, distância m)
        "direita": ((-1.0, 0.0, 0.0), 0.34), "frente": ((0.0, 1.0, 0.0), 0.36),
        "cima": ((0.0, 0.05, -1.0), 0.40), "tres_quartos": ((-0.6, 0.7, -0.35), 0.38),
        "esquerda": ((1.0, 0.0, 0.0), 0.34), "atras": ((0.0, -1.0, -0.15), 0.36),
    }

    def __init__(self, jogo, largura=640, altura=360, motor="workbench"):
        self.jogo, self.largura, self.altura, self.motor = jogo, largura, altura, motor
        self.cena = bpy.context.scene
        dados = bpy.data.cameras.new("estudio_camera")
        dados.lens = 50.0
        self.camera = bpy.data.objects.new("estudio_camera", dados)
        self.cena.collection.objects.link(self.camera)
        self._luzes()

    def _luzes(self):
        sol = bpy.data.objects.new("estudio_sol", bpy.data.lights.new("estudio_sol", "SUN"))
        sol.data.energy = 3.0
        sol.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30))
        self.cena.collection.objects.link(sol)
        mundo = self.cena.world or bpy.data.worlds.new("estudio")
        self.cena.world = mundo
        mundo.use_nodes = True
        fundo = mundo.node_tree.nodes.get("Background")
        if fundo is not None:
            fundo.inputs["Color"].default_value = (0.52, 0.54, 0.58, 1.0)
            fundo.inputs["Strength"].default_value = 1.1

    def _configurar(self, amostras=12):
        render = self.cena.render
        render.resolution_x, render.resolution_y, render.resolution_percentage = self.largura, self.altura, 100
        render.image_settings.file_format = "PNG"
        if self.motor == "workbench":
            render.engine = "BLENDER_WORKBENCH"
            shading = self.cena.display.shading
            shading.light, shading.color_type = "STUDIO", "MATERIAL"
            shading.show_cavity = False
        else:
            compat.use_eevee(self.cena)
            if hasattr(self.cena.eevee, "taa_render_samples"):
                self.cena.eevee.taa_render_samples = amostras

    def alvo(self, item):
        """Centro do item na mão, no mundo."""
        return Vector(self.jogo.hands.models.objects[item].matrix_world.translation)

    def foto(self, item, vista, caminho, deslocamento=(0.0, 0.0, 0.0), distancia=None, lente=None):
        direcao, dist = self.VISTAS[vista]
        alvo = self.alvo(item) + Vector(deslocamento)
        olhar = Vector(direcao).normalized()
        self.camera.location = alvo - olhar * (distancia or dist)
        self.camera.rotation_euler = olhar.to_track_quat("-Z", "Y").to_euler()
        self.camera.data.lens = lente or 50.0
        self.cena.camera = self.camera
        self._configurar()
        self.cena.render.filepath = caminho
        bpy.ops.render.render(write_still=True)
        return caminho

    def foto_do_jogador(self, caminho):
        """O quadro que o jogador vê (câmera do jogo, 72 graus)."""
        self.cena.camera = self.jogo.player_cam
        self._configurar()
        self.cena.render.filepath = caminho
        bpy.ops.render.render(write_still=True)
        return caminho


def fotografar(item, pasta, vistas=("direita", "frente", "cima", "tres_quartos"), motor="workbench", rotulo="", **opcoes):
    jogo, _lado = preparar(item, **opcoes)
    estudio = Estudio(jogo, motor=motor)
    os.makedirs(pasta, exist_ok=True)
    caminhos = [estudio.foto(item, v, os.path.join(pasta, f"{item.lower()}_{rotulo}{v}.png")) for v in vistas]
    caminhos.append(estudio.foto_do_jogador(os.path.join(pasta, f"{item.lower()}_{rotulo}jogador.png")))
    return caminhos


def principal(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return
    comando, resto = argv[0], argv[1:]
    if comando == "medir":
        medir_tudo(resto[0] if resto else None)
    elif comando == "gerar":
        gerar(resto or None)
    elif comando == "fotos":
        motor = "eevee" if "--motor" in resto and resto[resto.index("--motor") + 1] == "eevee" else "workbench"
        pasta = resto[0]
        for item in ITENS:
            print(fotografar(item, pasta, motor=motor), flush=True)


if __name__ == "__main__":
    principal()
