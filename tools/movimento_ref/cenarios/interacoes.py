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
from tools import prints_maos as maos  # noqa: E402
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
    maos.focus_render(jogo.scene, jogo)


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
    maos.give(jogo, flashlight=lanterna, on=False)
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
    if medida is not None and contato is not None:
        k = int(round(contato * rec.fps))
        palma = rec.palma[k]
        ponto = np.array(rec.meta["item"]["ponto"])
        medida["palma_ao_item_m"] = float(min(np.linalg.norm(palma[0] - ponto), np.linalg.norm(palma[1] - ponto)))
        medida["contato_s"] = round(contato - inicio, 3)
    return medida
