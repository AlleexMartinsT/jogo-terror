"""Cenários das interações: a mão na porta, a leitura com as duas mãos e o pegar baixo (fase 5, agente 3).

    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.interacoes --lista
    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.interacoes pegar_baixo --saida out/f5_3/pegar_baixo

Cada cenário monta a casa de verdade (`grava.montar_jogo(palco=False)`), põe o jogador diante do objeto, aperta o [E] e grava
o quadro a quadro (câmera, mãos, corpo, porta) e as imagens de dois pontos de vista: a câmera do jogador (o que ele vê) e uma
câmera de terceira pessoa, no mesmo instante. A referência real, onde existe, é o mocap da CMU (`assets/referencia/pegar_baixo_ref.json`
para o pegar do chão); para a porta não há clipe e a conferência é com a lei física e com as normas citadas em `docs/MAOS.md`.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.engine import collision  # noqa: E402
from sem_alvorada.engine.inputstate import InputState  # noqa: E402
from tools import prints_maos as pmaos  # noqa: E402
from tools.movimento_ref import grava  # noqa: E402

DT = 1.0 / 60.0
FOCO = 6.0                       # m: só o que está perto do jogador entra no render


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------
def motor_rapido(cena):
    cena.render.engine = "BLENDER_WORKBENCH"
    sombra = cena.display.shading
    sombra.light = "STUDIO"
    sombra.color_type = "TEXTURE"
    sombra.show_cavity = False
    cena.render.film_transparent = False
    cena.render.image_settings.file_format = "PNG"


def renderizar(cena, caminho, tamanho, motor="workbench", amostras=8):
    """Renderiza a câmera ativa da cena e devolve [h, w, 3] uint8."""
    from tools.prints import load_pixels
    cena.render.resolution_x, cena.render.resolution_y = tamanho
    cena.render.resolution_percentage = 100
    cena.render.filepath = caminho
    if motor == "workbench":
        motor_rapido(cena)
    else:
        from sem_alvorada import compat
        compat.use_eevee(cena)
        if hasattr(cena.eevee, "taa_render_samples"):
            cena.eevee.taa_render_samples = amostras
    bpy.ops.render.render(write_still=True)
    return (np.clip(np.flipud(load_pixels(caminho, tamanho)), 0, 1) * 255).astype(np.uint8)


class Terceira:
    """Câmera de terceira pessoa que olha para o corpo do jogador de um ângulo fixo em relação a ele."""

    def __init__(self, jogo, azimute=90.0, distancia=2.6, altura=1.05, fov=45.0):
        self.jogo = jogo
        self.azimute, self.distancia, self.altura = azimute, distancia, altura
        dados = bpy.data.cameras.new("terceira")
        dados.angle = math.radians(fov)
        self.objeto = bpy.data.objects.new("terceira", dados)
        jogo.scene.collection.objects.link(self.objeto)

    def apontar(self, alvo=None):
        jogador = self.jogo.player
        centro = Vector((jogador.x, jogador.y, jogador.z + self.altura)) if alvo is None else Vector(alvo)
        # azimute 0 = câmera atrás do jogador... aqui medido a partir da frente do corpo, no sentido horário visto de cima
        angulo = jogador.yaw + math.radians(self.azimute)
        direcao = Vector((-math.sin(angulo), math.cos(angulo), 0.0))
        posicao = centro + direcao * self.distancia
        posicao.z = jogador.z + 1.25
        self.objeto.location = posicao
        olhar = (centro - posicao).to_track_quat("-Z", "Y")
        self.objeto.rotation_euler = olhar.to_euler()

    def render(self, caminho, tamanho, motor="workbench", alvo=None):
        cena = self.jogo.scene
        antes = cena.camera
        self.apontar(alvo)
        cena.camera = self.objeto
        imagem = renderizar(cena, caminho, tamanho, motor)
        cena.camera = antes
        return imagem


def foco_do_render(jogo, raio=FOCO):
    pmaos.focus_render(jogo.scene, jogo)


def montar(palco=False, pista=8.0):
    jogo = grava.montar_jogo(palco=palco, pista=pista)
    return jogo


def posicionar_diante(jogo, ponto, distancia=0.9, azimutes=(0, 90, 180, 270), altura_olho=None, mirar=None):
    """Põe o jogador a `distancia` do `ponto` (x, y, z) olhando para ele; tenta quatro lados até a mira pegar o alvo."""
    x, y, z = ponto
    nivel_z = layout.LEVEL_Z[layout.level_of_z(z)]
    for azimute in azimutes:
        a = math.radians(azimute)
        px, py = x + distancia * math.sin(a), y - distancia * math.cos(a)
        yaw = math.atan2(-(x - px), (y - py))
        jogo.place_player(px, py, nivel_z, yaw)
        olho_z = nivel_z + (altura_olho or C.PLAYER_EYE_STAND)
        jogo.player.pitch = math.atan2((mirar if mirar is not None else z) - olho_z, math.hypot(x - px, y - py))
        for _ in range(30):
            jogo.tick(DT, InputState())
        yield azimute


# --------------------------------------------------------------------------
# Pegar baixo: gravação e medida
# --------------------------------------------------------------------------
def alvo_do_item(jogo, ref, no_chao=False):
    """O `Interactable` do item `ref`; com `no_chao` o item é posto no piso, debaixo do ponto onde estava."""
    alvo = next(t for t in jogo.interact.targets if t.ref == ref)
    sala, x, y, z, _ = layout.ITEM_SPOTS[ref]
    if no_chao and alvo.obj is not None:
        piso = layout.LEVEL_Z[layout.ROOMS[sala].level]
        baixo = min(v.co.z for v in alvo.obj.data.vertices)
        alvo.obj.location = (alvo.obj.location.x, alvo.obj.location.y, piso + 0.015 - baixo)
        alvo.position = tuple(collision.object_position(alvo.obj))
    return alvo


def mirar_item(jogo, alvo, distancia, azimute):
    """Põe o jogador a `distancia` (horizontal) do item, olhando para ele; True se a mira do jogo o escolheu."""
    posicao = collision.object_position(alvo.obj) if alvo.obj is not None else alvo.position
    x, y, z = posicao
    nivel = layout.LEVEL_Z[layout.level_of_z(z)]
    a = math.radians(azimute)
    px, py = x + distancia * math.sin(a), y - distancia * math.cos(a)
    jogo.place_player(px, py, nivel, math.atan2(-(x - px), (y - py)))
    jogo.player.pitch = math.atan2(z - (nivel + C.PLAYER_EYE_STAND), math.hypot(x - px, y - py))
    for _ in range(20):
        jogo.tick(DT, InputState())
    atual = jogo.interact.current
    return atual is not None and atual.ref == alvo.ref


def preparar_pegar(jogo, ref, distancia=0.7, no_chao=False, lanterna=True):
    """Estado do jogo e posição do jogador para pegar `ref`; devolve (alvo, azimute que funcionou)."""
    pmaos.give(jogo, flashlight=lanterna, on=False)
    if ref == "FLASHLIGHT":
        jogo.state.has_flashlight = False
        jogo.state.collected.discard("FLASHLIGHT")
        jogo.state.flashlight_on = False
    jogo.hands.equip(C.ITEM_FLASHLIGHT if lanterna else None)
    jogo.interact.sync_scene()
    alvo = alvo_do_item(jogo, ref, no_chao)
    for azimute in (0, 90, 180, 270, 45, 135, 225, 315):
        if mirar_item(jogo, alvo, distancia, azimute):
            return alvo, azimute
    raise RuntimeError(f"não achei onde ficar para mirar {ref} a {distancia} m")


def gravar_pegar(jogo, ref, distancia=0.7, no_chao=False, duracao=4.5, espera=0.5, nome=None):
    """Grava o jogador pegando `ref` (aperta o [E] depois de `espera` s). Devolve (gravação, alvo, ponto do item no mundo)."""
    alvo, azimute = preparar_pegar(jogo, ref, distancia, no_chao)
    ponto = tuple(collision.object_position(alvo.obj) if alvo.obj is not None else alvo.position)
    roteiro = [grava.Passo(espera, rotulo="espera"),
               grava.Passo(duracao, entradas={"interact": True}, rotulo="pegar")]
    rec = grava.gravar(jogo, roteiro, nome=nome or f"pegar_{ref}", ossos="armadura")
    rec.meta["item"] = {"ref": ref, "ponto": ponto, "azimute": azimute, "distancia": distancia, "no_chao": no_chao}
    return rec, alvo, ponto


def instante_do_contato(rec):
    """Segundos do contato dos dedos com o item (o ruído "pickup" que o inventário emite no contato)."""
    return next((e[0] for e in rec.eventos if e[1] == "ruido" and e[3] == "pickup"), None)


def medir_pegar(rec):
    """Tabela do pegar baixo no mesmo formato do mocap (`tools.movimento_ref.pegar_baixo.medir_movimento`) mais o que só o
    jogo sabe: onde a palma estava no contato em relação ao item."""
    from tools.movimento_ref import pegar_baixo
    inicio = rec.passos[1][0]
    mov = rec.movimento().trecho(inicio - 0.3)
    medida = pegar_baixo.medir_movimento(mov, rec.nome, "jogo")
    contato = instante_do_contato(rec)
    if medida is None and contato is not None:          # sem mergulho (a fase 4): ainda há o contato e a distância da palma
        medida = {}
    if medida is not None and contato is not None:
        k = int(round(contato * rec.fps))
        palma = rec.palma[k]
        ponto = np.array(rec.meta["item"]["ponto"])
        medida["palma_ao_item_m"] = float(min(np.linalg.norm(palma[0] - ponto), np.linalg.norm(palma[1] - ponto)))
        medida["contato_s"] = round(contato - inicio, 3)
    return medida


# --------------------------------------------------------------------------
# Sequências: o que o jogador vê e o corpo de fora, no mesmo instante
# --------------------------------------------------------------------------
def legendar(imagem, linhas, canto=(6, 6)):
    from tools.movimento_ref.comparar import rotular
    return rotular(imagem, linhas, canto, tamanho=12, fundo=(0, 0, 0, 150))


def gravar_sequencia(jogo, entrada_em, duracao, saida, nome, titulo, fps=15, celula=(640, 360), azimutes=(90.0, 35.0),
                     distancia=2.3, altura=1.15, estado_em=None, motor="workbench", espera=0.0, quadros_chave=6,
                     escurecer=False):
    """Roda `duracao` s no `jogo` (já posto e mirado), apertando o que `entrada_em(t)` devolver (um `InputState` ou None), e
    renderiza a cada 1/`fps` s: a câmera do jogador, o corpo de lado e o corpo em três quartos. Devolve os caminhos do vídeo e da
    folha de contato. `estado_em(jogo)` devolve texto para o canto da primeira pessoa (abertura da porta, profundidade...)."""
    from tools.movimento_ref import comparar
    os.makedirs(saida, exist_ok=True)
    cena = jogo.scene
    cena.camera = jogo.player_cam
    foco_do_render(jogo)
    terceiras = [Terceira(jogo, azimute=a, distancia=distancia, altura=altura) for a in azimutes]
    for _ in range(int(espera / DT)):
        jogo.tick(DT, entrada_em(-1.0) or InputState()) if False else jogo.tick(DT, InputState())
    cada = max(1, int(round(1.0 / DT / fps)))
    pasta = os.path.join(saida, "quadros")
    os.makedirs(pasta, exist_ok=True)
    quadros, primeiras, terceiras_imgs, tempos = [], [], [], []
    total = int(duracao / DT)
    for k in range(total):
        t = k * DT
        entrada = entrada_em(t) or InputState()
        jogo.tick(DT, entrada)
        if k % cada:
            continue
        jogo._sync_camera()
        cena.camera = jogo.player_cam
        primeira = renderizar(cena, os.path.join(pasta, "tmp_p.png"), celula, motor)
        cena.camera = jogo.player_cam
        lado = [t3.render(os.path.join(pasta, f"tmp_{i}.png"), celula, motor) for i, t3 in enumerate(terceiras)]
        cena.camera = jogo.player_cam
        texto = estado_em(jogo) if estado_em else ""
        primeira = legendar(primeira, [f"{titulo}", f"primeira pessoa   t = {t:.2f} s   {texto}"])
        lado = [legendar(img, [f"terceira pessoa ({int(a)} graus)"]) for img, a in zip(lado, azimutes)]
        info = np.full((celula[1], celula[0], 3), (252, 252, 251), np.uint8)
        quadros.append(comparar.grade([primeira, *lado, info], 2)[: 2 * celula[1], : 2 * celula[0]])
        primeiras.append(primeira)
        terceiras_imgs.append(lado[0])
        tempos.append(t)
    caminho_video, _ = comparar.escrever_mp4(iter([q[:, :, :3] for q in quadros]), os.path.join(saida, f"{nome}_video.mp4"), fps)
    escolhidos = np.linspace(0, len(quadros) - 1, quadros_chave).round().astype(int)
    pequenas = []
    for i in escolhidos:
        a = np.array(Image.fromarray(primeiras[i]).resize((480, 270)))
        b = np.array(Image.fromarray(terceiras_imgs[i]).resize((480, 270)))
        pequenas.append(np.concatenate([a, b], axis=0))
    folha = comparar.salvar_png(np.concatenate(pequenas, axis=1), os.path.join(saida, f"{nome}_folha.png"))
    for nome_tmp in os.listdir(pasta):
        if nome_tmp.startswith("tmp_"):
            os.remove(os.path.join(pasta, nome_tmp))
    return caminho_video, folha, tempos


def entrada_unica(instante, **teclas):
    """Um `entrada_em` que aperta `teclas` uma vez, em `instante` s."""
    estado = {"feito": False}

    def entrada(t):
        if t >= instante and not estado["feito"]:
            estado["feito"] = True
            return InputState(**teclas)
        return None
    return entrada


def entradas_em(*pares):
    """`entrada_em` com várias teclas: pares (instante, {tecla: valor})."""
    pendentes = sorted(pares, key=lambda p: p[0])

    def entrada(t):
        if pendentes and t >= pendentes[0][0]:
            return InputState(**pendentes.pop(0)[1])
        return None
    return entrada


from PIL import Image  # noqa: E402


def preparar_casa(lanterna=True, ligada=False, **estado):
    """A casa completa com o jogador, a lanterna na direita e as luzes acesas."""
    jogo = montar(palco=False)
    pmaos.give(jogo, flashlight=lanterna, on=ligada, **estado)
    jogo.hands.equip(C.ITEM_FLASHLIGHT if lanterna else None)
    jogo.lights.set_power(True)
    return jogo


def diante_da_maçaneta(jogo, porta_id, distancia=0.6, lado=1.0, lateral=-0.25):
    """O jogador diante da maçaneta, olhando o centro da folha (a mira do jogo); True se a mira escolheu a porta."""
    porta = jogo.doors.get(porta_id)
    yaw = porta.yaw
    comp = porta.length - 0.07
    kx, ky = porta.hinge[0] + math.cos(yaw) * comp, porta.hinge[1] + math.sin(yaw) * comp
    nx, ny = -math.sin(yaw), math.cos(yaw)
    px, py = kx + lado * nx * distancia + math.cos(yaw) * lateral, ky + lado * ny * distancia + math.sin(yaw) * lateral
    cx, cy, cz = jogo.doors.center(porta_id)
    jogo.place_player(px, py, porta.floor_z, math.atan2(-(cx - px), cy - py))
    jogo.player.pitch = math.atan2(cz - (porta.floor_z + C.PLAYER_EYE_STAND), math.hypot(cx - px, cy - py))
    for _ in range(40):
        jogo.tick(DT, InputState())
    atual = jogo.interact.current
    return atual is not None and atual.ref == porta_id


def texto_da_porta(porta_id):
    def texto(jogo):
        porta = jogo.doors.get(porta_id)
        clipe = jogo.hands.runner.clip
        return f"porta {porta.openness * 100:3.0f}%   mão: {clipe.name if clipe else '-'}"
    return texto


def texto_do_corpo(jogo):
    reach = jogo.player.reach
    clipe = jogo.hands.runner.clip
    return f"olho {jogo.player.camera_pose()[0][2] - jogo.player.z:.2f} m   tronco +{reach.lean:3.0f} graus   mão: {clipe.name if clipe else '-'}"


SEQUENCIAS = {}


def sequencia(nome):
    def registro(funcao):
        SEQUENCIAS[nome] = funcao
        return funcao
    return registro


@sequencia("porta_abrir")
def _porta_abrir(saida, **kw):
    jogo = preparar_casa()
    assert diante_da_maçaneta(jogo, "kids_hall"), "a mira não escolheu a porta"
    return gravar_sequencia(jogo, entrada_unica(1.0, interact=True), 3.6, saida, "porta_abrir",
                            "Abrir a porta (a mão já se preparou olhando a porta)", estado_em=texto_da_porta("kids_hall"), **kw)


@sequencia("porta_abrir_frio")
def _porta_abrir_frio(saida, **kw):
    jogo = preparar_casa()
    assert diante_da_maçaneta(jogo, "kids_hall"), "a mira não escolheu a porta"
    return gravar_sequencia(jogo, entrada_unica(0.05, interact=True), 3.4, saida, "porta_abrir_frio",
                            "Abrir a porta sem aviso (o [E] logo ao chegar)", estado_em=texto_da_porta("kids_hall"), **kw)


@sequencia("porta_trancada")
def _porta_trancada(saida, **kw):
    jogo = preparar_casa()
    porta = jogo.doors.get("front")
    assert jogo.doors.is_locked("front")
    assert diante_da_maçaneta(jogo, "front", distancia=0.6, lado=-1.0 if porta.closed_yaw > 0 else 1.0) or \
        diante_da_maçaneta(jogo, "front", distancia=0.6, lado=1.0), "a mira não escolheu a porta"
    return gravar_sequencia(jogo, entrada_unica(0.6, interact=True), 3.0, saida, "porta_trancada",
                            "Porta trancada: a mão tenta, o punho sacode e para", estado_em=texto_da_porta("front"), **kw)


@sequencia("porta_fechar")
def _porta_fechar(saida, **kw):
    jogo = preparar_casa()
    jogo.doors.snap("kids_hall", 1.0)
    jogo.doors.get("kids_hall").target = 1.0
    achou = any(diante_da_maçaneta(jogo, "kids_hall", 0.55, lado, lateral) for lado in (1.0, -1.0) for lateral in (0.0, 0.3, -0.3))
    assert achou, "a mira não escolheu a porta aberta"
    return gravar_sequencia(jogo, entrada_unica(0.4, interact=True), 3.2, saida, "porta_fechar",
                            "Fechar a porta (a mão empurra enquanto o braço alcança)", estado_em=texto_da_porta("kids_hall"), **kw)


def _ler(saida, modo, **kw):
    jogo = preparar_casa(ligada=True, map_=(modo == "mapa"), notes=("NOTE_1",))
    jogo.hands.equip(C.ITEM_MAP if modo == "mapa" else C.ITEM_NOTE)
    for _ in range(150):
        jogo.tick(DT, InputState())
    jogo.player.pitch = math.radians(-6.0)

    def entrada(t, estado={"abriu": False, "fechou": False}):
        if t >= 0.3 and not estado["abriu"]:
            estado["abriu"] = True
            jogo.hands.use_held()
        if modo == "nota" and t >= 3.4 and not estado["fechou"] and jogo.phase == "reading":
            estado["fechou"] = True
            return InputState(interact=True)
        return None
    titulo = "Ler a anotação com as duas mãos" if modo == "nota" else "Olhar o mapa de perto"
    # a 90 graus e 2,3 m a câmera de fora cai dentro da parede do corredor: perto e em três quartos mostra as mãos e a folha
    kw.setdefault("azimutes", (40.0, -40.0))
    kw.setdefault("distancia", 1.3)
    kw.setdefault("altura", 1.25)
    return gravar_sequencia(jogo, entrada, 5.2 if modo == "nota" else 4.0, saida, f"ler_{modo}", titulo, estado_em=lambda j: f"fase: {j.phase}", **kw)


@sequencia("ler_nota")
def _ler_nota(saida, **kw):
    return _ler(saida, "nota", **kw)


@sequencia("ler_mapa")
def _ler_mapa(saida, **kw):
    return _ler(saida, "mapa", **kw)


def _pegar(saida, nome, titulo, ref, distancia, no_chao=False, lanterna=True, **kw):
    jogo = preparar_casa(lanterna=lanterna)
    alvo, _azimute = preparar_pegar(jogo, ref, distancia, no_chao, lanterna=lanterna)
    jogo.lights.set_power(True)
    return gravar_sequencia(jogo, entrada_unica(0.3, interact=True), 4.6, saida, nome, titulo, estado_em=texto_do_corpo, **kw)


@sequencia("pegar_gaveta")
def _pegar_gaveta(saida, **kw):
    return _pegar(saida, "pegar_gaveta", "Pegar a pilha da gaveta baixa (0,31 m)", "BATTERY_3", 0.9, **kw)


@sequencia("pegar_chao")
def _pegar_chao(saida, **kw):
    return _pegar(saida, "pegar_chao", "Pegar do chão", "BATTERY_3", 0.7, no_chao=True, **kw)


@sequencia("pegar_criado")
def _pegar_criado(saida, **kw):
    return _pegar(saida, "pegar_criado", "A primeira lanterna, no criado-mudo (0,55 m)", "FLASHLIGHT", 0.9, lanterna=False, **kw)


@sequencia("pegar_prateleira")
def _pegar_prateleira(saida, **kw):
    return _pegar(saida, "pegar_prateleira", "A pilha na prateleira baixa de brinquedos (0,51 m)", "BATTERY_1", 0.9, **kw)


@sequencia("pegar_chave")
def _pegar_chave(saida, **kw):
    return _pegar(saida, "pegar_chave", "A chave na escrivaninha (0,77 m): uma curvatura leve", "KEY", 0.9, **kw)


@sequencia("pegar_nota_baixa")
def _pegar_nota_baixa(saida, **kw):
    jogo = preparar_casa(ligada=True)
    alvo, _azimute = preparar_pegar(jogo, "NOTE_3", 0.9)
    jogo.lights.set_power(True)

    def entrada(t, estado={"fechou": False}):
        if t >= 0.3 and not estado.get("abriu"):
            estado["abriu"] = True
            return InputState(interact=True)
        if t >= 4.5 and jogo.phase == "reading" and not estado["fechou"]:
            estado["fechou"] = True
            return InputState(interact=True)
        return None
    return gravar_sequencia(jogo, entrada, 8.0, saida, "pegar_nota_baixa", "A anotação na mesinha de centro (0,44 m): descer, ler, devolver",
                            estado_em=texto_do_corpo, **kw)


# --------------------------------------------------------------------------
# O cenário do `comparar`: CMU 26_09 e os outros 11 clipes contra o jogo, lado a lado
# --------------------------------------------------------------------------
from tools.movimento_ref import cmu, metricas  # noqa: E402
from tools.movimento_ref.cenarios import maos  # noqa: E402
from tools.movimento_ref.cenarios import registrar  # noqa: E402
from tools.movimento_ref.cenarios.base import Alinhamento, Medida  # noqa: E402

# tolerância = cerca de um desvio entre os 12 clipes (pegar_baixo_ref.json: 0,11 m, 0,14 m, 30 graus, 47 graus, 0,28 m, 0,48 s)
CAMPOS_PEGAR_BAIXO = {
    "profundidade_m": ("olho desce", "m", 2, "abs", 0.12),
    "avanco_m": ("olho avança", "m", 2, "abs", 0.25),
    "tronco_graus": ("tronco inclina", "graus", 0, "abs", 35.0),
    "joelho_graus": ("joelho dobra", "graus", 0, "abs", 50.0),
    "quadril_queda_m": ("quadril cai", "m", 2, "abs", 0.30),
    "descida_s": ("descida até 90% do fundo", "s", 2, "abs", 0.55),
    "fundo_s": ("tempo no fundo", "s", 2, "abs", 0.40),
    "subida_s": ("subida", "s", 2, "abs", 0.60),
}
cmu.GRUPOS.setdefault("pegar_baixo", ["26_09", "26_10", "26_11", "69_70", "69_71", "69_75", "69_73", "69_74", "143_10", "143_11",
                                       "111_17", "111_18"])


@registrar
class PegarBaixo(maos.CenarioMao):
    nome = "pegar_baixo"
    titulo = "Pegar do chão: CMU 26_09 e o jogo com o corpo descendo"
    resumo = "abaixar e pegar: o olho desce, o tronco inclina, o joelho dobra e o corpo sobe de novo"
    clip = "26_09"
    trecho = (0.2, 4.0)
    grupo = "pegar_baixo"
    lado_mao = "d"
    gesto = "pilha_chao"
    campos = CAMPOS_PEGAR_BAIXO
    destaques = ("profundidade_m", "tronco_graus", "joelho_graus", "descida_s", "subida_s")
    lento = 0.5
    vistas = ("frente", "lado", "primeira")

    @property
    def roteiro(self):
        return "pegar_chao (corpo)"

    def preparar(self, jogo=None):
        from sem_alvorada.engine import handactions
        jogo = jogo or maos.montar_gesto(self.gesto)
        handactions.ENABLED = True
        return super().preparar(jogo)

    def gravar_jogo(self, jogo):
        def preparar(j):
            j.place_player(0.0, 0.40, 0.0, 0.0)               # a 0,45 m do olho ao item: sem passo, como o clipe (o objeto está nos pés)
            maos.mirar(j, (0.0, 0.85, 0.05))
        roteiro = [grava.Passo(0.8, ao_iniciar=preparar, rotulo="esperar"),
                   grava.Passo(4.6, entradas={"interact": True}, rotulo="pegar_baixo")]
        return grava.gravar(jogo, roteiro, nome=self.nome, ossos="armadura")

    def medir(self, mov, qual=None):
        from tools.movimento_ref import pegar_baixo
        medida = pegar_baixo.medir_movimento(mov, mov.nome, mov.fonte)
        nan = float("nan")
        v = {chave: (medida[chave] if medida else nan) for chave in CAMPOS_PEGAR_BAIXO}
        lado = "e" if mov.fonte == "jogo" else self.lado_mao
        velocidade = metricas.perfil_mao(mov, lado, "punho")
        ajuste = {}
        if medida:
            ajuste = {"inicio": medida["inicio_s"], "fundo": medida["inicio_s"] + medida["descida_s"], "fim": medida["fim_s"],
                      "duracao": medida["fim_s"] - medida["inicio_s"]}
            v["velocidade_pico"] = float(velocidade.max())
        return Medida(v, velocidade, mov.fps, (0, 0), ajuste)

    def alinhar(self, real, jogo):
        a, b = self.medir(real).ajuste, self.medir(jogo).ajuste
        if not a or not b:
            raise RuntimeError("pegar_baixo: sem mergulho do olho no real ou no jogo")
        marcas = ("inicio", "fundo", "fim")
        return Alinhamento([a[m] for m in marcas], [b[m] for m in marcas])

    def fases_chave(self, prep):
        a = prep.marcha_real.ajuste
        return [("em pé", a["inicio"]), ("descendo", 0.5 * (a["inicio"] + a["fundo"])), ("no fundo", a["fundo"] + 0.15),
                ("subindo", 0.5 * (a["fundo"] + a["fim"]))]

    def legenda(self, prep):
        real, jogo = prep.marcha_real.v, prep.marcha_jogo.v
        return ((f"REAL  {prep.real.rotulo}", f"olho desce {real['profundidade_m']:.2f} m"),
                (f"{self.rotulo_jogo}  pegar do chão", f"olho desce {jogo['profundidade_m']:.2f} m"))

    def medidas(self, prep, saida):
        import json
        from tools.movimento_ref import graficos
        arquivos = {}
        linhas = self.linhas(prep)
        n = len(prep.marchas_reais)
        arquivos["tabela"] = graficos.painel_tabela(linhas, os.path.join(saida, "tabela.png"), titulo=self.titulo,
                                                    rotulo_real=f"real ({n} clipes)", rotulo_jogo="jogo")
        with open(os.path.join(saida, "tabela.txt"), "w", encoding="utf-8") as arquivo:
            arquivo.write(f"{self.titulo}\nreal ({n} clipes) x jogo\n\n{metricas.tabela_texto(linhas)}\n")
        arquivos["tabela_txt"] = os.path.join(saida, "tabela.txt")
        arquivos["metricas"] = self.salvar_json(prep, linhas, saida)
        return arquivos, linhas


# --------------------------------------------------------------------------
# Tabela e curvas do pegar baixo: o jogo antes e depois contra os clipes da CMU
# --------------------------------------------------------------------------
CASOS_TABELA = (
    # nome, item, distância do olho (m), no chão, lanterna já na mão
    ("pilha na gaveta (0,31 m), a 0,45 m", "BATTERY_3", 0.45, False, True),
    ("pilha na gaveta (0,31 m), a 0,9 m", "BATTERY_3", 0.9, False, True),
    ("pilha no chão, a 0,55 m", "BATTERY_3", 0.55, True, True),
    ("lanterna no criado-mudo (0,55 m), a 0,9 m", "FLASHLIGHT", 0.9, False, False),
    ("pilha na prateleira (0,51 m), a 0,9 m", "BATTERY_1", 0.9, False, True),
    ("chave na escrivaninha (0,77 m), a 0,9 m", "KEY", 0.9, False, True),
)
CAMPOS_TABELA = ("profundidade_m", "avanco_m", "tronco_graus", "joelho_graus", "quadril_queda_m", "descida_s", "fundo_s", "subida_s",
                 "mao_altura_m")


def medir_caso(caso, ligado):
    """Grava o jogo pegando o item do `caso` com a postura `ligado` (ou sem ela, como na fase 4) e devolve a medida e a gravação."""
    from sem_alvorada.engine import handactions
    nome, ref, distancia, no_chao, lanterna = caso
    jogo = montar(palco=False)
    handactions.ENABLED = ligado
    pmaos.give(jogo, flashlight=lanterna, on=False)
    alvo, _azimute = preparar_pegar(jogo, ref, distancia, no_chao, lanterna=lanterna)
    ponto = tuple(collision.object_position(alvo.obj))
    roteiro = [grava.Passo(0.4, rotulo="espera"), grava.Passo(5.0, entradas={"interact": True}, rotulo="pegar")]
    rec = grava.gravar(jogo, roteiro, nome=f"pegar_{ref}", ossos="fk", cada=2)
    rec.meta["item"] = {"ref": ref, "ponto": ponto, "distancia": distancia, "no_chao": no_chao}
    medida = medir_pegar(rec)
    contato = instante_do_contato(rec)
    return medida, rec, contato


def gerar_tabela(saida):
    """`tabela_pegar_baixo.md/.json` e `curvas_pegar_baixo.png`: cada caso antes e depois, e a referência dos clipes."""
    import json
    from tools.movimento_ref import graficos, pegar_baixo
    os.makedirs(saida, exist_ok=True)
    referencia = json.load(open(pegar_baixo.ARQUIVO, encoding="utf-8"))
    resultados = {}
    for caso in CASOS_TABELA:
        resultados[caso[0]] = {}
        for ligado, rotulo in ((False, "antes"), (True, "depois")):
            medida, rec, contato = medir_caso(caso, ligado)
            resultados[caso[0]][rotulo] = {"medida": medida, "contato_s": contato, "palma_ao_item_m": (medida or {}).get("palma_ao_item_m")}
            print(f"[tabela] {caso[0]} {rotulo}: {None if medida is None else {k: medida[k] for k in CAMPOS_TABELA if k in medida}}", flush=True)
            if ligado and caso[0] == CASOS_TABELA[0][0]:
                rec.salvar(os.path.join(saida, "gravacao_pegar_gaveta.npz"))
    with open(os.path.join(saida, "tabela_pegar_baixo.json"), "w", encoding="utf-8") as arquivo:
        json.dump({"casos": resultados, "referencia": referencia["resumo"]}, arquivo, ensure_ascii=False, indent=1, default=float)
    linhas = ["# Pegar baixo: o jogo antes e depois contra os clipes da CMU", "",
              "Referência (MEDIDO, 12 clipes, escala do Daniel): mediana e faixa entre os clipes, 'curvar' (n = 7) e 'agachar' (n = 5).", "",
              "| métrica | CMU curvar | CMU agachar | " + " | ".join(f"{c[0]} antes | {c[0]} depois" for c in CASOS_TABELA) + " |",
              "|---|---|---|" + "---|---|" * len(CASOS_TABELA)]
    rotulos = {"profundidade_m": "olho desce (m)", "avanco_m": "olho avança (m)", "tronco_graus": "tronco inclina (graus)",
               "joelho_graus": "joelho dobra (graus)", "quadril_queda_m": "quadril cai (m)", "descida_s": "descida até 90% (s)",
               "fundo_s": "no fundo (s)", "subida_s": "subida (s)", "mao_altura_m": "mão no fundo, altura (m)",
               "palma_ao_item_m": "palma ao item no contato (m)"}
    for chave in (*CAMPOS_TABELA, "palma_ao_item_m"):
        celulas = []
        for tecnica in ("curvar", "agachar"):
            r = referencia["resumo"][tecnica].get(chave)
            celulas.append("-" if r is None else f"{r['mediana']:.2f} ({r['min']:.2f} a {r['max']:.2f})")
        for caso in CASOS_TABELA:
            for rotulo in ("antes", "depois"):
                m = resultados[caso[0]][rotulo]["medida"]
                valor = None if m is None else m.get(chave)
                celulas.append("-" if valor is None else f"{valor:.2f}")
        linhas.append(f"| {rotulos[chave]} | " + " | ".join(celulas) + " |")
    with open(os.path.join(saida, "tabela_pegar_baixo.md"), "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas) + "\n")
    print("[tabela] gravada", flush=True)
    return resultados


def gerar_curvas(saida, resultados=None):
    """As curvas normalizadas (descida 0..1, subida 1..2) do olho, do avanço, do tronco e do joelho: faixa dos clipes e o jogo."""
    import json
    import matplotlib.pyplot as plt
    from tools.movimento_ref import graficos, pegar_baixo
    graficos._estilo()
    referencia = json.load(open(pegar_baixo.ARQUIVO, encoding="utf-8"))
    if resultados is None:
        resultados = json.load(open(os.path.join(saida, "tabela_pegar_baixo.json"), encoding="utf-8"))["casos"]
    x = np.linspace(0, 1, 21)
    figura, eixos = plt.subplots(1, 4, figsize=(15, 3.6))
    for eixo, chave, titulo, unidade in zip(eixos, ("profundidade", "avanco", "tronco", "joelho"),
                                            ("Olho desce", "Olho avança", "Tronco inclina", "Joelho dobra"), ("m", "m", "graus", "graus")):
        todas = []
        for clipe in referencia["clipes"]:
            curva = np.concatenate([clipe["descida"][chave], clipe["subida"][chave]])
            todas.append(curva)
            eixo.plot(np.concatenate([x, 1 + x]), curva, color=graficos.COR_REAL, alpha=0.18, linewidth=0.9)
        mediana = np.median(todas, axis=0)
        eixo.plot(np.concatenate([x, 1 + x]), mediana, color=graficos.COR_REAL, linewidth=2.2, label="CMU, 12 clipes (mediana e cada clipe)")
        for caso, dados in resultados.items():
            m = dados["depois"]["medida"]
            if not m or "descida" not in m:
                continue
            curva = np.concatenate([m["descida"][chave], m["subida"][chave]])
            eixo.plot(np.concatenate([x, 1 + x]), curva, color=graficos.COR_JOGO, alpha=0.75, linewidth=1.4)
        eixo.plot([], [], color=graficos.COR_JOGO, linewidth=1.6, label="jogo, 6 casos")
        eixo.set_title(f"{titulo} ({unidade})")
        eixo.set_xlabel("fase: 0 = começa a descer, 1 = no fundo, 2 = de pé de novo")
        if chave == "profundidade":
            eixo.legend(fontsize=8, loc="upper right")
    figura.suptitle("Pegar baixo: a descida e a subida, na fase do gesto", fontsize=11)
    figura.tight_layout()
    caminho = os.path.join(saida, "curvas_pegar_baixo.png")
    figura.savefig(caminho, dpi=130)
    plt.close(figura)
    print(f"[curvas] {caminho}", flush=True)
    return caminho


# --------------------------------------------------------------------------
# A porta: tempos do gesto contra os da porta (palco mínimo com o corpo de verdade)
# --------------------------------------------------------------------------
PORTA_DO_PALCO = "living_hall"          # nível 0 (o piso do palco vai de -60 a 60 m)


def _palco_da_porta(ligado, **estado):
    from sem_alvorada.engine import handactions
    jogo = maos.montar_jogo_maos()
    handactions.ENABLED = ligado
    maos.estado(jogo, **estado)
    jogo.hands.equip(C.ITEM_FLASHLIGHT)
    return jogo


def _diante_da_porta(jogo, aberta=False, trancada=False, distancia=0.6):
    porta = jogo.doors.get(PORTA_DO_PALCO)
    if aberta:
        jogo.doors.snap(PORTA_DO_PALCO, 1.0)
        porta.target = 1.0
    if trancada:
        porta.lock = "front"
        jogo.state.unlocked.discard("front")
    for lado in (1.0, -1.0):
        for lateral in (-0.25, 0.0, 0.3):
            if diante_da_maçaneta(jogo, PORTA_DO_PALCO, distancia, lado, lateral):
                return porta
    raise RuntimeError("a mira não escolheu a porta")


def medir_porta(modo):
    """Tempos de uma abertura (modo "sem_mao", "preparada", "fria"), de uma tentativa na tranca ("trancada") ou de um fechar ("fechar"):
    do [E] até a maçaneta girar, até a folha sair, a duração da folha (de 2% a 98%), até a mão voltar ao braço e a distância
    palma-maçaneta enquanto ela acompanha."""
    jogo = _palco_da_porta(modo != "sem_mao")
    porta = _diante_da_porta(jogo, aberta=modo == "fechar", trancada=modo == "trancada")
    for _ in range(int((1.0 if modo in ("preparada", "sem_mao") else 0.0) / DT)):
        jogo.tick(DT, InputState())
    linhas, entrada = [], InputState(interact=True)
    for k in range(int(4.0 / DT)):
        jogo.tick(DT, entrada)
        entrada = InputState()
        y, a = porta.yaw, porta.length - 0.07
        macaneta = np.array([porta.hinge[0] + math.cos(y) * a, porta.hinge[1] + math.sin(y) * a, porta.floor_z + 0.95])
        palma = np.array(jogo.body.arm("L").hand_world_position())
        clipe = jogo.hands.runner.clip
        linhas.append((k * DT, porta.openness, float(np.linalg.norm(palma - macaneta)), clipe.name if clipe else None, porta.turn))
    t = np.array([l[0] for l in linhas])
    aberto = np.array([l[1] for l in linhas])
    saida = {"modo": modo}
    gira = [l[0] for l in linhas if l[4] > 0.5]
    saida["maçaneta_gira_s"] = gira[0] if gira else None
    movendo = [l[0] for l in linhas if abs(l[1] - linhas[0][1]) > 0.02]
    saida["folha_sai_s"] = movendo[0] if movendo else None
    if modo in ("sem_mao", "preparada", "fria"):
        a, b = next(l[0] for l in linhas if l[1] > 0.02), next((l[0] for l in linhas if l[1] > 0.98), None)
        saida["folha_dura_s"] = None if b is None else b - a
    if modo == "fechar":
        a = next((l[0] for l in linhas if l[1] < 0.98), None)
        b = next((l[0] for l in linhas if l[1] < 0.02), None)
        saida["folha_dura_s"] = None if (a is None or b is None) else b - a
    if modo != "sem_mao":
        com_clipe = [l for l in linhas if l[3] is not None]
        saida["gesto_dura_s"] = (com_clipe[-1][0] - com_clipe[0][0] + DT) if com_clipe else None
        if saida["folha_sai_s"] is not None:
            seguindo = [l[2] for l in linhas if saida["folha_sai_s"] <= l[0] <= saida["folha_sai_s"] + 0.3]
            saida["palma_maçaneta_max_cm_no_empurrao"] = 100 * max(seguindo) if seguindo else None
            saida["palma_maçaneta_no_giro_cm"] = 100 * next((l[2] for l in linhas if saida["maçaneta_gira_s"] is not None and l[0] >= saida["maçaneta_gira_s"]), float("nan"))
    saida["abertura_maxima_na_tranca"] = float(aberto.max()) if modo == "trancada" else None
    return saida


def gerar_tabela_porta(saida):
    import json
    os.makedirs(saida, exist_ok=True)
    resultado = {modo: medir_porta(modo) for modo in ("sem_mao", "preparada", "fria", "trancada", "fechar")}
    with open(os.path.join(saida, "tabela_porta.json"), "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=1, default=float)
    linhas = ["# A mão na porta: tempos (s) do [E] em diante", "",
              "| caso | maçaneta gira | folha sai | folha dura (2% a 98%) | gesto da mão dura | palma-maçaneta no giro (cm) | palma-maçaneta no empurrão, máx. (cm) |",
              "|---|---|---|---|---|---|---|"]
    nomes = {"sem_mao": "sem a mão (fase 4)", "preparada": "com a mão, preparada olhando a porta 1 s", "fria": "com a mão, [E] logo ao chegar",
             "trancada": "porta trancada", "fechar": "fechar a porta aberta"}

    def f(valor, casas=2):
        return "-" if valor is None or (isinstance(valor, float) and math.isnan(valor)) else f"{valor:.{casas}f}"
    for modo, dados in resultado.items():
        # fechar: a mão solta a maçaneta aos 0,2 s e a distância seguinte é de depois da soltura, sem sentido como contato
        contato = modo != "fechar"
        linhas.append(f"| {nomes[modo]} | {f(dados.get('maçaneta_gira_s'))} | {f(dados.get('folha_sai_s'))} | {f(dados.get('folha_dura_s'))} | "
                      f"{f(dados.get('gesto_dura_s'))} | {f(dados.get('palma_maçaneta_no_giro_cm') if contato else None, 1)} | "
                      f"{f(dados.get('palma_maçaneta_max_cm_no_empurrao') if contato else None, 1)} |")
    with open(os.path.join(saida, "tabela_porta.md"), "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas) + "\n")
    print("\n".join(linhas), flush=True)
    return resultado


def main(argv=None):
    import argparse
    import subprocess
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("acao", nargs="?", help="nome de uma sequência, 'tabela', 'curvas' ou 'todas'")
    parser.add_argument("--saida", default=os.path.join(ROOT, "out", "f5_3", "final"))
    parser.add_argument("--lista", action="store_true")
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--motor", default="workbench", choices=("workbench", "eevee"))
    args = parser.parse_args(argv)
    if args.lista or not args.acao:
        print("sequências:", ", ".join(SEQUENCIAS), "\nações: tabela, curvas, todas")
        return
    if args.acao == "tabela":
        gerar_curvas(args.saida, gerar_tabela(args.saida))
    elif args.acao == "curvas":
        gerar_curvas(args.saida)
    elif args.acao == "tabela_porta":
        gerar_tabela_porta(args.saida)
    elif args.acao == "todas":
        for nome in SEQUENCIAS:         # um processo por sequência: cada uma recarrega a casa e solta a memória no fim
            subprocess.run([sys.executable, "-m", "tools.movimento_ref.cenarios.interacoes", nome, "--saida", args.saida,
                            "--fps", str(args.fps), "--motor", args.motor], cwd=ROOT, check=False)
    else:
        os.makedirs(args.saida, exist_ok=True)
        video, folha, _tempos = SEQUENCIAS[args.acao](args.saida, fps=args.fps, motor=args.motor)
        print(f"[{args.acao}] {video}\n[{args.acao}] {folha}")


if __name__ == "__main__":
    main()
