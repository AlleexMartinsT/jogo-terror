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
# Itens com pegada por contato. O mapa e a anotação ficam com a garra de antes: a mão está atrás da folha, fora do quadro, e o
# ajuste automático não achou polegar na frente e indicador atrás que o braço alcance (ver docs/MAOS.md).
GERADOS = (C.ITEM_FLASHLIGHT, C.ITEM_KEY, C.ITEM_BATTERY)
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


def preparar(item, pendulo_parado=True, **opcoes):
    """Jogo de palco mínimo com `item` na mão certa. Devolve (jogo, lado). O chaveiro balança (a respiração o excita, até 7
    graus em torno da cabeça), o que desloca as faces da cabeça uns 2 mm da pinça; `pendulo_parado` mede a pegada estática."""
    lado, estado = ITENS[item]
    jogo = maos.montar_jogo_maos(None)
    maos.estado(jogo, **{**estado, **opcoes})
    if pendulo_parado:
        jogo.hands.pendulum.step = lambda dt, accel: None
    assentar(jogo)
    return jogo, lado


def objetos_do_item(jogo, item):
    modelos = jogo.hands.models
    if item == C.ITEM_MAP:
        return [o for o in (modelos.objects[item], *modelos.panels) if o is not None]
    return [modelos.objects[item]]


MATERIAIS = {C.ITEM_FLASHLIGHT: ("flash_aluminum", "flash_knurled", "rubber")}      # o resto é interno ao modelo


def forma_do_item(jogo, item, frame=None):
    """Malha do item no mundo (`frame` None) ou no referencial `frame`; a pilha usa o cilindro analítico."""
    if item == C.ITEM_BATTERY:
        from sem_alvorada.props import handheld_battery
        objeto = jogo.hands.models.objects[item]
        para_item = objeto.matrix_world.inverted() if frame is None else None
        return grasp.CylinderShape(handheld_battery.RADIUS, handheld_battery.LENGTH, para_item)
    if item == C.ITEM_KEY:                           # a cabeça de borracha: 34 x 50 x 10,5 mm (x1,3 da mesa, x0,75 da mão)
        escala = 1.3 * 0.75
        objeto = jogo.hands.models.objects[item]
        return grasp.BoxShape((0.034 * escala / 2, 0.050 * escala / 2, 0.0105 * escala / 2), 0.0036 * escala,
                              objeto.matrix_world.inverted() if frame is None else None)
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
            "tocam": sum(1 for g in folgas if g < 2.5), "deveriam": len(deve)}


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
# Perfil de abertura da mão no alcance
# ---------------------------------------------------------------------------
def abertura_polegar_indicador(jogo, lado):
    """Distância (m) entre a ponta do polegar e a do indicador, lida na armadura avaliada."""
    bpy.context.view_layer.update()
    arma = bpy.data.objects[C.OBJ_BODY_RIG].evaluated_get(bpy.context.evaluated_depsgraph_get())
    ponta = lambda osso: arma.matrix_world @ arma.pose.bones[f"{osso}.{lado}"].tail
    return (ponta("Thumb2") - ponta("Index3")).length


def perfil_de_abertura(item, segundos=2.2, antes=0.5):
    """Grava o alcance até `item` (a tecla E num item na mesa) e devolve {"t", "abertura", "fechamento", "contato", "alcance"}:
    a abertura do polegar ao indicador por quadro (60 Hz), o canal `grip` da mão e os instantes do contato e do fim do alcance."""
    lado = ITENS[item][0]
    jogo = maos.montar_jogo_maos(item if item != C.ITEM_FLASHLIGHT else "FLASHLIGHT")
    maos.estado(jogo, lanterna=item != C.ITEM_FLASHLIGHT)
    alvo = jogo.interact.targets[0].position
    maos.mirar(jogo, (alvo[0], alvo[1], alvo[2] + 0.02))
    for _ in range(int(antes * 60)):
        jogo.tick(1 / 60, InputState())
    t, abertura, fechamento = [], [], []
    inicio = None
    contato = None
    for k in range(int(segundos * 60)):
        jogo.tick(1 / 60, InputState(interact=(k == 0)))
        clip = jogo.hands.runner.clip
        if clip is not None and inicio is None:
            inicio = k / 60
            alcance = clip.tracks[f"{lado}.pos"].end if f"{lado}.pos" in clip.tracks else None
        t.append(k / 60)
        abertura.append(abertura_polegar_indicador(jogo, lado))
        entradas = jogo.hands._grip_inputs.get(lado)
        fechamento.append(float(entradas[0][1]) if entradas else 0.0)
        if contato is None and jogo.hands._visual[lado] is not None:
            contato = k / 60
    return {"t": np.array(t), "abertura": np.array(abertura), "fechamento": np.array(fechamento), "contato": contato,
            "inicio": inicio or 0.0}


# ---------------------------------------------------------------------------
# Gerar os dados: ajusta a mão ao item e fecha os dedos (offline); o jogo só lê sem_alvorada/grasp_data.py
# ---------------------------------------------------------------------------
DADOS = os.path.join(ROOT, "sem_alvorada", "grasp_data.py")


def _item_frame(objeto):
    loc, rot, _ = objeto.matrix_world.decompose()
    return Matrix.LocRotScale(loc, rot, None).inverted()


# folha: a mão segura pela borda, de fora da folha, com o polegar à frente e o indicador atrás
FOLHA_POSICOES = {
    C.ITEM_MAP: tuple((x, y, z) for x in (-0.03, 0.0, 0.03) for y in (-0.03, 0.0, 0.03) for z in (-0.02, 0.0, 0.02)),
    C.ITEM_NOTE: tuple((x, y, z) for x in (-0.03, 0.0, 0.03) for y in (-0.05, -0.03, 0.0) for z in (-0.02, 0.0, 0.02))}


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
    # folha: a mão fica atrás dela, o polegar passa à frente. Parte de todas as orientações do cubo e de algumas posições
    posicoes = FOLHA_POSICOES[item]
    partidas = []
    for r in grasp.cube_rotations():
        if abs((r.to_3x3() @ grasp.S.NEUTRAL_HAND_CAM).col[0].x) > 0.5:           # os dedos não apontam ao longo da folha (X)
            continue
        for p in posicoes:
            m = r.copy()
            m.translation = Vector(p)
            partidas.append(m)
    return (G.Role(pinch=("Index",), thumb="contact", sheet=True,
                   free={"Middle": G.free_row(0.45), "Ring": G.free_row(0.50), "Pinky": G.free_row(0.55)}),
            None, None, None, ("starts", *partidas))


def verificador_de_braco(jogo, item, lado, peso=0.001):
    """O IK do corpo de verdade, para `fit_grip`. Devolve (penalidade, alcancada). A mão pedida vira alvo do braço nas poses
    em que o item aparece (parado, rosto, perto); `penalidade(matriz)` é peso * (desvio de orientação em graus)^2 mais o erro de
    alcance, no pior caso; `alcancada(matriz)` é a mão que o IK entrega na pose parada, no referencial do item, que é
    contra a qual os dedos fecham (o pulso não dobra tudo o que se pede)."""
    from types import SimpleNamespace
    from mathutils import Euler
    from sem_alvorada.body import solver
    arm = jogo.body.arm(lado)
    frame = SimpleNamespace(body_from_world=Matrix.Rotation(-jogo.body._yaw, 3, "Z"), root=Vector(jogo.body._root))
    cam = jogo.hands._cam[0].to_3x3()
    view = (Vector(jogo.hands._cam[0].translation), cam)
    poses = [handclips.pose_matrix(*handclips.MODE_POSES[modo].get((lado, item), handclips.HOLD_ITEM[(lado, item)]))
             for modo in ("hold", "face", "near") if (lado, item) in handclips.MODE_POSES[modo] or modo == "hold"]
    indice = grasp.S.BONE_INDEX[f"Hand.{lado}"]

    def resolver(mao):
        euler = Euler(mao.to_3x3().to_euler("XYZ"))
        arm.set_target(tuple(mao.translation), tuple(math.degrees(a) for a in euler), 1.0)
        arm.wrist_comfort = True
        arm._swivel = 0.0                      # sempre o mesmo ponto de partida: o resultado não depende do que o jogo fez antes
        meta = arm._goal(frame, view)
        return meta, solver.solve(solver.PoseSpec(arms={lado: meta}))

    def penalidade(matriz):
        pior = 0.0
        for pose in poses:
            meta, solucao = resolver(pose @ matriz)
            desvio = math.degrees((meta.hand_q.to_matrix().inverted() @ solucao.world[indice].to_matrix()).to_quaternion().angle)
            erro = max(solucao.reach_error.values()) * 1000.0
            pior = max(pior, desvio * desvio + 4.0 * erro * erro)
        arm.release()
        return peso * pior

    def alcancada(matriz):
        mao = poses[0] @ matriz
        _meta, solucao = resolver(mao)
        arm.release()
        entregue = (frame.body_from_world.inverted() @ solucao.world[indice].to_matrix() @ grasp.S.rest_basis(lado)
                    @ grasp.S.NEUTRAL_HAND_CAM.inverted())
        rotacao = cam.inverted() @ entregue
        resultado = rotacao.to_4x4()
        resultado.translation = mao.translation
        return poses[0].inverted() @ resultado

    return penalidade, alcancada


def ajustar_item(item, jogo=None, inicio=None, **opcoes):
    """Ajusta a mão de `item` (`grasp.fit_grip`) e devolve (matriz da mão no item, Grasp, custo, giro do scan, forma)."""
    jogo, lado = (jogo, ITENS[item][0]) if jogo is not None else preparar(item)
    objetos = objetos_do_item(jogo, item)
    frame = _item_frame(objetos[0])
    papel, materiais, meta, sem_botao, busca = papel_do_item(item)
    forma = forma_do_item(jogo, item, frame)
    alvo = grasp.ItemShape(objetos, frame=frame, materials=meta) if meta else None
    solto = grasp.ItemShape(objetos, frame=frame, materials=sem_botao) if sem_botao else None
    pele = grasp.HandSkin(bpy.data.objects[C.OBJ_BODY], lado)
    extra, alcancada = verificador_de_braco(jogo, item, lado)
    partida = inicio if inicio is not None else handclips.LEGACY_GRIPS[item].matrix.copy()
    resultado = grasp.fit_grip(item, lado, partida, forma, papel, pele, goal_shape=alvo, press_shape=solto, scan=busca,
                               extra=extra, achieved=alcancada, **opcoes)
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
    for item in itens or GERADOS:
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
