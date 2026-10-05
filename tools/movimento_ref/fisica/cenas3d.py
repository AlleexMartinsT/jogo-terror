"""Cenas 3D dos objetos: o objeto real do jogo na pose da gravação e o fantasma azul do modelo físico, no mesmo espaço.

Cada cena tem `janela` (início e fim, s), `cameras` (nome -> objeto câmera), `pose(t)` (aplica TODAS as poses, jogo e modelo, sem
tocar nas câmeras, exceto as que seguem o objeto, que andam por uma função do próprio instante), `dados(t)` (o que a gravação e o
modelo mandam, para os testes), `quadro(t)` (pose + uma imagem por câmera + as células das curvas), `video` e `folha`.

A gravação do jogo é feita ANTES, uma vez, pelos mesmos atores do jogo (grava.py); o render só aplica a gravação nos objetos reais do
.blend. Por isso as câmeras mostram sempre o mesmo instante: a pose não depende da câmera.
"""
import math
import os

import bpy  # antes de mathutils, que só existe depois dele
import numpy as np
from mathutils import Vector

from . import carro as K, grava, porta as P, relogio as R
from .render3d import AZUL, SAIDA, Palco, ocultar_longe

PRETO = (13, 13, 13)
COR_AZUL_PIL = (42, 120, 214)
COR_LARANJA_PIL = (235, 104, 52)
CINZA = (82, 81, 78)


def _rotular(imagem, linhas, canto, **opcoes):
    from tools.movimento_ref import comparar
    return comparar.rotular(imagem, linhas, canto, **opcoes)


def bpy_obj(nome, opcional=False):
    obj = bpy.data.objects.get(nome)
    if obj is None and not opcional:
        raise KeyError(nome)
    return obj


def bpy_empty(nome, local, pai=None, inversa=None, rotacao=None):
    obj = bpy.data.objects.new(nome, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = pai
    if inversa is not None:
        obj.matrix_parent_inverse = inversa.copy()
    obj.location = local
    if rotacao is not None:
        obj.rotation_euler = rotacao
    obj["fantasma"] = True
    return obj


def atualizar():
    bpy.context.view_layer.update()


# --------------------------------------------------------------------------
# Células de curva (PIL: rápido e sem matplotlib dentro do laço de render)
# --------------------------------------------------------------------------
def celula_curva(tempos, series, t, titulo, unidade, janela=None, tamanho=(640, 360), marcas=()):
    """Gráfico simples: `series` = [(rótulo, y, cor_rgb)], cursor em `t`, `marcas` = [(instante, rótulo)] em linhas tracejadas."""
    from PIL import Image, ImageDraw
    from tools.movimento_ref import comparar
    largura, altura = tamanho
    imagem = Image.new("RGB", tamanho, (252, 252, 251))
    d = ImageDraw.Draw(imagem)
    x0, x1, y0, y1 = 62, largura - 18, 58, altura - 44
    tempos = np.asarray(tempos)
    t0, t1 = janela if janela else (float(tempos[0]), float(tempos[-1]))
    dentro = (tempos >= t0) & (tempos <= t1)
    ys = np.concatenate([np.asarray(s[1])[dentro] for s in series])
    lo, hi = float(ys.min()), float(ys.max())
    pad = 0.08 * ((hi - lo) or 1.0)
    lo, hi = lo - pad, hi + pad

    def px(tt, yy):
        return (x0 + (tt - t0) / (t1 - t0) * (x1 - x0), y1 - (yy - lo) / (hi - lo) * (y1 - y0))
    for k in range(5):
        yy = lo + (hi - lo) * k / 4
        d.line([px(t0, yy), px(t1, yy)], fill=(228, 227, 222), width=1)
        d.text((8, px(t0, yy)[1] - 7), f"{yy:.3g}", fill=CINZA, font=comparar.fonte(11))
    passo_t = 1 if (t1 - t0) <= 12 else 2
    for k in range(int(math.ceil(t0)), int(t1) + 1, passo_t):
        d.text((px(k, lo)[0] - 4, y1 + 6), f"{k}", fill=CINZA, font=comparar.fonte(11))
    for instante, rotulo in marcas:
        if t0 <= instante <= t1:
            xm = px(instante, lo)[0]
            for ym in range(int(y0), int(y1), 8):
                d.line([(xm, ym), (xm, ym + 3)], fill=(160, 158, 150), width=1)
            d.text((xm + 3, y0 - 12), rotulo, fill=CINZA, font=comparar.fonte(10))
    for n, (rotulo, y, cor) in enumerate(series):
        y = np.asarray(y)
        idx = np.nonzero(dentro)[0]
        passo = max(1, len(idx) // 600)
        d.line([px(tempos[i], y[i]) for i in idx[::passo]], fill=cor, width=5 if n == 0 else 2)     # o 1o (modelo) fica por baixo, mais grosso
    d.line([px(t, lo), px(t, hi)], fill=PRETO, width=1)
    d.text((62, 8), titulo, fill=PRETO, font=comparar.fonte(13, True))
    d.text((x1 - 70, altura - 22), "segundos", fill=CINZA, font=comparar.fonte(11))
    d.text((8, 14), unidade, fill=CINZA, font=comparar.fonte(11))
    lx = x0 + 4
    for rotulo, _, cor in series:
        d.line([(lx, 38), (lx + 20, 38)], fill=cor, width=3)
        d.text((lx + 26, 31), rotulo, fill=PRETO, font=comparar.fonte(11))
        lx += 30 + d.textlength(rotulo, font=comparar.fonte(11)) + 14
    return np.array(imagem)


class Cena:
    """Base: guarda o palco, a janela de tempo e monta o quadro [câmeras..., curvas...] em `colunas` colunas."""
    nome = ""
    titulo = ""
    janela = (0.0, 1.0)
    colunas = 2
    cameras = {}
    oculto_em = {}                                         # câmera -> objetos que ela não deve ver (por exemplo o casco translúcido)

    def pose(self, t):
        raise NotImplementedError

    def dados(self, t):
        raise NotImplementedError

    def curvas(self, t):
        return []

    def rotulos(self, t):
        return {}

    def destaques(self):
        """[(instante, descrição)] para a folha de contato."""
        raise NotImplementedError

    def nome_camera(self, nome):
        return {"planta": "PLANTA (ortogonal, de cima)", "frente": "FRENTE (ortogonal)", "jogador": "JOGADOR (perspectiva, olhos a 1,65 m)",
                "lado": "LADO (ortogonal)", "rua": "RUA (perspectiva)", "perto": "DE PERTO (ortogonal)",
                "corte": "CORTE DE CIMA (ortogonal)", "mostrador": "MOSTRADOR (ortogonal)", "dentro": "DENTRO DO CARRO (corte, ortogonal)"}.get(nome, nome)

    def imagens(self, t):
        self.pose(t)                                       # todas as poses ANTES de qualquer câmera
        saida = {}
        for nome, cam in self.cameras.items():
            escondidos = self.oculto_em.get(nome, ())
            for obj in escondidos:
                obj.hide_render = True
            saida[nome] = self.palco.render(cam)
            for obj in escondidos:
                obj.hide_render = False
        return saida

    def celula_camera(self, nome, imagem, t):
        return _rotular(imagem.copy(), [self.nome_camera(nome)] + self.rotulos(t).get(nome, []), (6, 6), tamanho=13)

    def faixa(self, largura, linhas):
        """Faixa de título no alto do quadro (fundo claro, letras escuras): título, instante e legenda das cores."""
        from PIL import Image, ImageDraw
        from tools.movimento_ref import comparar
        imagem = Image.new("RGB", (largura, 14 + 20 * len(linhas)), (252, 252, 251))
        d = ImageDraw.Draw(imagem)
        for i, texto in enumerate(linhas):
            d.text((8, 7 + 20 * i), texto, fill=PRETO, font=comparar.fonte(14 if i == 0 else 12, i == 0))
        x = largura - 330
        d.rectangle([x, 9, x + 16, 25], fill=COR_LARANJA_PIL)
        d.text((x + 22, 9), "jogo (objeto real)", fill=PRETO, font=comparar.fonte(12))
        d.rectangle([x + 160, 9, x + 176, 25], fill=COR_AZUL_PIL)
        d.text((x + 182, 9), "modelo (fantasma)", fill=PRETO, font=comparar.fonte(12))
        return np.array(imagem)

    def quadro(self, t, imagens=None):
        from tools.movimento_ref import comparar
        imgs = imagens or self.imagens(t)
        celulas = [self.celula_camera(nome, imgs[nome], t) for nome in self.cameras] + self.curvas(t)
        grade = comparar.grade(celulas, self.colunas)
        faixa = self.faixa(grade.shape[1], [self.titulo, f"t = {t:5.2f} s   render 3D (Workbench) do .blend do jogo; o jogo reproduz a gravação, "
                                                         f"o modelo físico é o fantasma translúcido"])
        return np.concatenate([faixa, grade], axis=0)

    def tempos(self, fps):
        t0, t1 = self.janela
        return t0 + np.arange(int(round((t1 - t0) * fps))) / fps

    def video(self, caminho, fps=20, ao_quadro=None):
        from tools.movimento_ref import comparar

        def quadros():
            for k, t in enumerate(self.tempos(fps)):
                if ao_quadro:
                    ao_quadro(k, t)
                yield self.quadro(float(t))
        return comparar.escrever_mp4(quadros(), caminho, fps=fps)

    def folha(self, caminho, instantes=None, escala=0.75):
        """Folha de contato: uma linha por instante, uma coluna por câmera (mesma gravação, mesmo instante em cada linha)."""
        from PIL import Image
        from tools.movimento_ref import comparar
        instantes = instantes or self.destaques()
        linhas = []
        for t, descricao in instantes:
            imgs = self.imagens(t)
            celulas = []
            for i, nome in enumerate(self.cameras):
                celula = self.celula_camera(nome, imgs[nome], t)
                if i == 0:
                    celula = _rotular(celula, [f"t = {t:.2f} s", descricao], (6, celula.shape[0] - 46), tamanho=13)
                celulas.append(celula)
            linhas.append(np.concatenate(celulas, axis=1))
        folha = np.concatenate(linhas, axis=0)
        h, w = folha.shape[:2]
        folha = np.array(Image.fromarray(folha).resize((int(w * escala), int(h * escala)), Image.LANCZOS))
        faixa = self.faixa(folha.shape[1], [self.titulo, "folha de contato: cada linha é um instante, as colunas são câmeras diferentes da MESMA gravação"])
        return comparar.salvar_png(np.concatenate([faixa, folha], axis=0), caminho)

    def hero(self, caminho, t, camera, amostras=24):
        """Um quadro de destaque no EEVEE (o resto é Workbench)."""
        from sem_alvorada import compat
        self.pose(t)
        cena = self.palco.cena
        motor = cena.render.engine
        compat.use_eevee(cena)
        try:
            cena.eevee.taa_render_samples = amostras
        except AttributeError:
            pass
        try:
            cena.render.filepath = caminho
            cena.camera = self.cameras[camera]
            atualizar()
            bpy.ops.render.render(write_still=True)
        finally:
            cena.render.engine = motor
        return caminho


# --------------------------------------------------------------------------
# Porta
# --------------------------------------------------------------------------
class CenaPorta(Cena):
    """Uma porta do jogo (DoorManager sobre a cena real) contra o modelo de corpo rígido na dobradiça (fisica/porta.py)."""

    def __init__(self, palco, porta_id="master_hall", pesada=False):
        from sem_alvorada import layout
        from sem_alvorada.engine import doors as door_module
        self.palco, self.porta_id, self.pesada = palco, porta_id, pesada
        self.nome = f"porta_{porta_id}"
        self.jogo = grava.JogoMinimo(False, 4.6 if pesada else 2.6)
        self.jogo.rng = grava.Sempre()
        self.gerente = door_module.DoorManager(self.jogo, palco.cena)
        self.porta = self.gerente.get(porta_id)
        self.massa = self.porta.mass
        plano = layout.door_transform(layout.OPENINGS[porta_id])
        self.dobradica = Vector(plano["hinge"])
        self.yaw_fechada, self.yaw_aberta = self.porta.closed_yaw, self.porta.open_yaw
        self.comprimento = self.porta.length
        quarto = "do quarto do jogador" if porta_id == "master_hall" else "da frente"
        self.titulo = (f"Porta {quarto} ({porta_id}, {self.massa:.0f} kg): " +
                       ("aberta com pressa e batida" if pesada else "abrir, fechar até o trinco, abrir e bater"))
        self.eventos = ([(0.2, "abre_apressado"), (3.4, "bate")] if pesada else [(0.2, "abre"), (3.2, "fecha"), (6.2, "snap"), (6.25, "bate")])
        self.janela = (0.0, 5.4 if pesada else 7.4)
        self._simular_jogo()
        self._modelo()
        self._objetos()
        self._cameras()

    # ---- o jogo roda uma vez, a 240 Hz; os objetos recebem a pose na hora de renderizar
    def _simular_jogo(self, fps=240.0):
        n = int(self.janela[1] * fps)
        dt = 1.0 / fps
        self.t_jogo = np.arange(n) * dt
        self.abertura = np.zeros(n)
        self.giro = np.zeros(n)
        self.durs = {}
        ev = list(self.eventos)
        for k in range(n):
            agora = k * dt
            while ev and agora >= ev[0][0] - dt / 2:
                _, tipo = ev.pop(0)
                if tipo in ("abre", "abre_apressado", "fecha"):
                    self.gerente.toggle(self.porta_id, hurried=tipo == "abre_apressado")
                    self.durs[tipo] = self.porta.glide.seconds if self.porta.glide is not None else 0.0
                elif tipo == "snap":
                    self.gerente.snap(self.porta_id, 1.0)
                elif tipo == "bate":
                    self.gerente.toggle(self.porta_id, hurried=True)
                    self.durs["bate"] = self.porta.glide.seconds if self.porta.glide is not None else 0.0
            self.gerente.update(dt, None)
            self.jogo.clock += dt
            self.abertura[k], self.giro[k] = self.porta.openness, self.porta.turn
        self.gerente.snap(self.porta_id, 0.0)

    def _modelo(self):
        """Ângulo do modelo físico (rad) por instante, na mesma sequência de eventos (fisica/porta.py, sem importar o jogo)."""
        arco = P.ABERTURA
        t = self.t_jogo
        theta = np.zeros_like(t)
        durs = self.durs
        sim, t_sim, w, tip = P.golpe_de_porta(massa=self.massa)
        cache = {}

        def guiada(dur):
            if dur not in cache:
                cache[dur] = P.trajetoria_minima_variacao_de_torque(dur, self.massa)[:2]
            return cache[dur]
        for k, x in enumerate(t):
            if self.pesada:
                if x < 3.4:
                    tm, th = guiada(durs["abre_apressado"])
                    theta[k] = float(np.interp(x - 0.2 - 0.14, tm, th, left=0.0, right=arco))
                else:
                    tau = x - 3.4
                    theta[k] = float(np.interp(tau, sim["t"], sim["theta"])) if tau <= t_sim else 0.0
            else:
                if x < 3.2:
                    tm, th = guiada(durs["abre"])
                    theta[k] = float(np.interp(x - 0.2 - 0.14, tm, th, left=0.0, right=arco))
                elif x < 6.2:
                    tm, th = guiada(durs["fecha"])
                    theta[k] = float(np.interp(x - 3.2, tm, arco - th, left=arco, right=0.0))
                elif x < 6.25:
                    theta[k] = arco
                else:
                    tau = x - 6.25
                    theta[k] = float(np.interp(tau, sim["t"], sim["theta"])) if tau <= t_sim else 0.0
        self.theta_modelo = theta

    def _objetos(self):
        p = self.palco
        self.pivo = bpy_obj(f"Door_{self.porta_id}")
        self.marca_jogo = p.esfera("marca_jogo", 0.035, p.material_marca("laranja"), self.pivo, (self.comprimento, 0.0, 1.0))
        azul = p.material_fantasma("fantasma_azul", AZUL, 0.5)
        self.pivo_modelo = bpy_empty("fantasma_pivo", self.dobradica)
        p.caixa("fantasma_folha", 0.0, -0.03, 0.0, self.comprimento, 0.03, 2.03, azul, self.pivo_modelo)
        self.marca_modelo = p.esfera("marca_modelo", 0.024, p.material_marca("azul", AZUL), self.pivo_modelo, (self.comprimento, 0.0, 1.0))

    def _cameras(self):
        p = self.palco
        fechada = Vector((math.cos(self.yaw_fechada), math.sin(self.yaw_fechada), 0.0))
        aberta = Vector((math.cos(self.yaw_aberta), math.sin(self.yaw_aberta), 0.0))
        lado_do_giro = aberta - fechada * aberta.dot(fechada)        # normal da parede, do lado para onde a folha gira
        lado_do_giro.normalize()
        quarto = self.dobradica + (fechada + aberta) * (0.5 * self.comprimento)   # centro do quarto de círculo varrido pela folha
        quarto.z = self.dobradica.z
        meio = quarto + Vector((0, 0, 1.0))
        self.centro = quarto
        ocultar_longe(p, quarto, 9.0)
        distancia = 8.0
        self.cameras = {
            "planta": p.nova_camera("cam_planta", quarto + Vector((0, 0, 2.6)), ortografica=2.6, rotacao=(0, 0, 0)),
            # elevação vista do lado para onde a folha gira; o corte de câmera tira o que está entre ela e a porta (móveis, paredes)
            "frente": p.nova_camera("cam_frente", meio + lado_do_giro * distancia, alvo=meio, ortografica=3.0,
                                    corte=(distancia - 1.4, distancia + 1.0)),
            "jogador": p.nova_camera("cam_jogador", quarto - aberta * 1.9 + Vector((0, 0, 1.65)), alvo=meio, fov=70.0),
        }

    def _indice(self, t):
        return min(max(int(round(t * 240.0)), 0), len(self.abertura) - 1)

    def pose(self, t):
        k = self._indice(t)
        yaw = self.yaw_fechada + (self.yaw_aberta - self.yaw_fechada) * float(self.abertura[k])
        self.pivo.rotation_euler.z = yaw
        bolt = bpy_obj(f"DoorBolt_{self.porta_id}", opcional=True)
        if bolt is not None:
            from sem_alvorada.engine import doors as door_module
            bolt.location.x = self.porta.bolt_rest - door_module.BOLT_STROKE * float(self.giro[k])
        modelo = self.yaw_fechada + (self.yaw_aberta - self.yaw_fechada) * float(self.theta_modelo[k] / P.ABERTURA)
        self.pivo_modelo.rotation_euler.z = modelo
        atualizar()

    def dados(self, t):
        """(ponta do jogo no mundo, ponta do modelo no mundo) conforme os DADOS (gravação e modelo), sem olhar os objetos."""
        k = self._indice(t)
        yaw_j = self.yaw_fechada + (self.yaw_aberta - self.yaw_fechada) * float(self.abertura[k])
        yaw_m = self.yaw_fechada + (self.yaw_aberta - self.yaw_fechada) * float(self.theta_modelo[k] / P.ABERTURA)

        def ponta(yaw):
            return self.dobradica + Vector((self.comprimento * math.cos(yaw), self.comprimento * math.sin(yaw), 1.0))
        return ponta(yaw_j), ponta(yaw_m)

    def rotulos(self, t):
        k = self._indice(t)
        graus_j = math.degrees(self.abertura[k] * P.ABERTURA)
        graus_m = math.degrees(self.theta_modelo[k])
        return {"planta": [f"jogo {graus_j:5.1f} graus   modelo {graus_m:5.1f} graus", f"maçaneta {self.giro[k]:.0%}"]}

    def curvas(self, t):
        return [celula_curva(self.t_jogo, [("modelo físico", np.degrees(self.theta_modelo), COR_AZUL_PIL),
                                           ("jogo", np.degrees(self.abertura * P.ABERTURA), COR_LARANJA_PIL)], t,
                             f"ângulo da folha ({self.massa:.0f} kg)", "graus", janela=self.janela)]

    def destaques(self):
        if self.pesada:
            return [(0.75, "abrindo com pressa"), (1.6, "aberta"), (3.55, "batida: a folha volta"), (3.75, "fecha no batente")]
        return [(0.8, "abrindo (mão empurra)"), (1.8, "aberta"), (3.75, "fechando até o trinco"), (6.45, "aberta e solta: bate")]


# --------------------------------------------------------------------------
# Pêndulo do relógio de pé
# --------------------------------------------------------------------------
def _cruzamentos(t, theta):
    """(instantes, sentido) dos cruzamentos do zero, por interpolação linear."""
    sinal = np.sign(theta)
    k = np.nonzero(sinal[1:] * sinal[:-1] < 0)[0]
    instantes = t[k] + (0 - theta[k]) * (t[k + 1] - t[k]) / (theta[k + 1] - theta[k])
    return instantes, np.sign(theta[k + 1] - theta[k])


class CenaRelogio(Cena):
    """O mecanismo do relógio do jogo (engine/clockwork.py) movendo o pêndulo e o ponteiro dos segundos reais."""
    colunas = 3

    def __init__(self, palco, inicio=8.0, duracao=8.0):
        self.palco = palco
        self.nome = "relogio_de_pe"
        self.titulo = "Relógio de pé: pêndulo de segundos (T = 2 s) e ponteiro dos segundos a cada tique"
        self.janela = (inicio, inicio + duracao)
        self._gravar()
        self._modelo()
        self._objetos()
        self._cameras()

    def _gravar(self, fps=240.0):
        g = grava.relogio(self.janela[1] + 1.0, fps)
        self.fps = fps
        self.t_jogo, self.theta_jogo, self.mao_jogo, self.tiques_jogo = g["t"], g["theta"], g["mao"], g["tiques"]

    def _modelo(self):
        """Pêndulo composto com escape (fisica/relogio.py), com a fase alinhada ao jogo no primeiro cruzamento da janela.

        A fase é o único parâmetro livre: o período, a amplitude e o decaimento são do modelo (haste que dá T = 2 s)."""
        l_eq = R.comprimento_equivalente(R.comprimento_para_periodo(2.0))
        t_m, th_m, tiques_m = R.simular(self.janela[1] + 8.0, l_eq, fps=self.fps)
        cz_j, sentido_j = _cruzamentos(self.t_jogo, self.theta_jogo)
        i = int(np.searchsorted(cz_j, self.janela[0] - 1.0))
        cz_m, sentido_m = _cruzamentos(t_m, th_m)
        j = next(j for j in range(len(cz_m)) if sentido_m[j] == sentido_j[i])
        atraso = cz_j[i] - cz_m[j]
        self.fase_modelo = atraso
        self.theta_modelo = np.interp(self.t_jogo - atraso, t_m, th_m)
        self.tiques_modelo = tiques_m + atraso
        # o ponteiro do modelo é a escada ideal de 6 graus por tique, alinhada ao do jogo no começo da janela
        i_tique = int(np.searchsorted(self.tiques_jogo, self.janela[0]))
        t_ref = 0.5 * (self.tiques_jogo[i_tique - 1] + self.tiques_jogo[i_tique])      # entre dois tiques: sem ambiguidade de degrau
        degraus = R.posicao_do_segundeiro(self.tiques_modelo, self.t_jogo)
        k_ref = int(np.searchsorted(self.t_jogo, t_ref))
        deslocamento = self.mao_jogo[k_ref] - np.radians(degraus[k_ref])
        self.mao_modelo = np.radians(degraus) + deslocamento

    def _objetos(self):
        p = self.palco
        self.pendulo = bpy_obj("grandfather_clock_pendulum")
        self.ponteiro = bpy_obj("grandfather_clock_seconds")
        from sem_alvorada.props import clock
        self.comprimento = clock.PENDULUM_LENGTH
        azul = p.material_fantasma("fantasma_azul", AZUL, 0.55)
        marca_azul = p.material_marca("azul", AZUL)
        marca_laranja = p.material_marca("laranja")
        pai = self.pendulo.parent
        self.eixo_modelo = bpy_empty("fantasma_pendulo", self.pendulo.location, pai, self.pendulo.matrix_parent_inverse)
        p.caixa("fantasma_haste", -0.003, -0.003, -self.comprimento, 0.003, 0.003, 0.0, azul, self.eixo_modelo)
        p.cilindro("fantasma_lentilha", R.R_LENTILHA, 0.014, azul, 36, self.eixo_modelo, (0.0, 0.0, -self.comprimento), eixo="y")
        self.marca_modelo = p.esfera("marca_modelo", 0.008, marca_azul, self.eixo_modelo, (0.0, 0.0, -self.comprimento))
        self.marca_jogo = p.esfera("marca_jogo", 0.014, marca_laranja, self.pendulo, (0.0, 0.0, -self.comprimento))
        self.eixo_mao = bpy_empty("fantasma_segundos", self.ponteiro.location, self.ponteiro.parent, self.ponteiro.matrix_parent_inverse)
        p.caixa("fantasma_ponteiro", -0.0015, -0.0015, -0.032, 0.0015, 0.0015, 0.135, azul, self.eixo_mao)
        p.esfera("marca_ponteiro_modelo", 0.004, marca_azul, self.eixo_mao, (0.0, 0.0, 0.135))
        p.esfera("marca_ponteiro_jogo", 0.006, marca_laranja, self.ponteiro, (0.0, 0.0, 0.135))

    def _cameras(self):
        p = self.palco
        atualizar()
        pivo = self.pendulo.matrix_world.translation.copy()
        self.pivo = pivo
        ocultar_longe(p, pivo - Vector((0, 0, 0.6)), 7.0)
        centro_lentilha = pivo - Vector((0, 0, self.comprimento))
        d = 6.0
        mao = self.ponteiro.matrix_world.translation.copy()
        frente = Vector((0.0, -1.0, 0.0))               # o relógio olha para -Y no mundo
        self.cameras = {
            "frente": p.nova_camera("cam_frente", Vector((pivo.x, pivo.y, 0.93)) + frente * d, alvo=Vector((pivo.x, pivo.y, 0.93)), ortografica=2.1,
                                    corte=(d - 0.9, d + 1.0)),
            "perto": p.nova_camera("cam_perto", Vector((pivo.x, pivo.y, centro_lentilha.z + 0.02)) + frente * d,
                                   alvo=Vector((pivo.x, pivo.y, centro_lentilha.z + 0.02)), ortografica=0.55, corte=(d - 0.9, d + 1.0)),
            "corte": p.nova_camera("cam_corte", Vector((pivo.x, pivo.y - 0.10, 5.0)), ortografica=0.7, rotacao=(0, 0, 0),
                                   corte=(5.0 - (centro_lentilha.z + 0.20), 5.6)),
            "mostrador": p.nova_camera("cam_mostrador", Vector((pivo.x, pivo.y, mao.z)) + frente * d, alvo=Vector((pivo.x, pivo.y, mao.z)),
                                       ortografica=0.40, corte=(d - 0.9, d + 1.0)),
        }

    def _indice(self, t):
        return min(max(int(round(t * self.fps)) - 1, 0), len(self.t_jogo) - 1)

    def pose(self, t):
        k = self._indice(t)
        self.pendulo.rotation_euler[1] = float(self.theta_jogo[k])
        self.ponteiro.rotation_euler[1] = -float(self.mao_jogo[k])
        self.eixo_modelo.rotation_euler[1] = float(self.theta_modelo[k])
        self.eixo_mao.rotation_euler[1] = -float(self.mao_modelo[k])
        atualizar()

    def dados(self, t):
        """(lentilha do jogo no mundo, lentilha do modelo no mundo) pelo ângulo gravado e pelo ângulo do modelo."""
        k = self._indice(t)
        matriz = self.pendulo.parent.matrix_world @ self.pendulo.matrix_parent_inverse

        def lentilha(theta):
            # rotação em torno do eixo Y local: (0, 0, -L) vai para (-L sin, 0, -L cos)
            local = Vector((-self.comprimento * math.sin(theta), 0.0, -self.comprimento * math.cos(theta)))
            return matriz @ (Vector(self.pendulo.location) + local)
        return lentilha(float(self.theta_jogo[k])), lentilha(float(self.theta_modelo[k]))

    def rotulos(self, t):
        k = self._indice(t)
        return {"frente": [f"jogo {math.degrees(self.theta_jogo[k]):+5.2f} graus   modelo {math.degrees(self.theta_modelo[k]):+5.2f} graus"],
                "corte": ["a frente do relógio fica para baixo"],
                "mostrador": [f"jogo {math.degrees(self.mao_jogo[k]):6.1f} graus   modelo {math.degrees(self.mao_modelo[k]):6.1f} graus"]}

    def curvas(self, t):
        tq = [(float(x), "") for x in self.tiques_jogo if self.janela[0] <= x <= self.janela[1]]
        return [celula_curva(self.t_jogo, [("modelo físico", np.degrees(self.theta_modelo), COR_AZUL_PIL),
                                           ("jogo", np.degrees(self.theta_jogo), COR_LARANJA_PIL)], t,
                             "ângulo do pêndulo (tracejado: tiques do escape)", "graus", janela=self.janela, marcas=tq),
                celula_curva(self.t_jogo, [("modelo físico", np.degrees(self.mao_modelo), COR_AZUL_PIL),
                                           ("jogo", np.degrees(self.mao_jogo), COR_LARANJA_PIL)], t,
                             "ponteiro dos segundos: 6 graus por tique", "graus", janela=self.janela, marcas=tq)]

    def destaques(self):
        cz, sentido = _cruzamentos(self.t_jogo, self.theta_jogo)
        i = int(np.searchsorted(cz, self.janela[0] + 0.3))
        c0, c1, c2 = cz[i], cz[i + 1], cz[i + 2]
        return [(c0 + (c1 - c0) / 2.0, "lentilha numa ponta do arco"),
                (c1 + 0.012, "no centro do arco, 12 ms antes do tique"),
                (c1 + (c2 - c1) / 2.0, "na outra ponta do arco"),
                (c2 + 0.06, "centro de novo: o ponteiro dos segundos avançou 6 graus")]


# --------------------------------------------------------------------------
# Carro saindo da garagem
# --------------------------------------------------------------------------
class CenaCarro(Cena):
    """O carro da cena final (CarMotion, CharmPendulum, SteeringWheel, GarageLift) contra o meio carro e o pêndulo do modelo."""
    colunas = 3

    def __init__(self, palco, inicio=7.5, fim=16.5):
        self.palco = palco
        self.nome = "carro_saindo_da_garagem"
        self.titulo = "Carro saindo da garagem: arfagem, rodas, coelhinho do retrovisor e portão de enrolar"
        self.janela = (inicio, fim)
        self._gravar()
        self._modelo()
        self._objetos()
        self._cameras()

    def _gravar(self, fps=240.0):
        s = grava.carro(self.janela[1] + 0.5, fps)
        p = grava.portao(self.janela[1] + 0.5, fps)
        self.s, self.p, self.fps = s, p, fps
        self.t_jogo = s["t"]

    def _modelo(self):
        from . import comparar_carro as CC
        s = self.s
        ref = CC.referencia_do_carro(s)
        self.ref = ref
        t = s["t"]
        self.y_modelo = ref["y"]
        self.theta_modelo = ref["theta"]
        self.z_modelo = ref["z_origem"]
        l_coelho = CC.comprimento_equivalente("Cut_Bunny")
        self.l_coelho = l_coelho
        self.coelho_modelo = K.simular_pendulo(t, l_coelho, 0.04, lambda x: float(np.interp(x, t, ref["a_frente"])))   # contra a vertical do mundo
        self.coelho_jogo = s["coelho"][:, 0] + s["euler"][:, 0]
        self.percurso = -(self.y_modelo - s["home"][1])           # distância andada para a frente (m)

    def _objetos(self):
        p = self.palco
        self.carro = bpy_obj("Car")
        self.rodas = {n: bpy_obj(f"Car_Wheel_{n}") for n in ("FL", "FR", "RL", "RR")}
        self.coelho = bpy_obj("Cut_Bunny")
        self.volante = bpy_obj("Cut_Wheel")
        self.portao = bpy_obj("GarageRollup")
        self.volante.rotation_mode = "QUATERNION"
        azul = p.material_fantasma("fantasma_azul", AZUL, 0.30)
        azul_forte = p.material_fantasma("fantasma_azul_forte", AZUL, 0.60)
        marca_azul = p.material_marca("azul", AZUL)
        marca_laranja = p.material_marca("laranja")
        home = self.s["home"]
        self.casco = bpy_empty("fantasma_carro", (home[0], home[1], home[2]), rotacao=(0.0, 0.0, math.pi))
        # envelope do corpo (caixas: a saia e a cabine) na pose do meio carro; só a pose é do modelo
        self.partes_do_casco = [
            p.caixa("fantasma_saia", -1.0, -2.40, 0.25, 1.0, 2.40, 0.88, azul, self.casco),
            p.caixa("fantasma_cabine", -0.85, -1.55, 0.88, 0.85, 0.95, K.TETO, azul, self.casco),
        ]
        self.pivo_coelho_modelo = bpy_empty("fantasma_coelho", tuple(self.coelho.location), self.casco)
        p.caixa("fantasma_fio", -0.002, -0.002, -self.l_coelho, 0.002, 0.002, 0.0, azul_forte, self.pivo_coelho_modelo)
        self.partes_do_casco.append(p.esfera("fantasma_coelho_massa", 0.02, marca_azul, self.pivo_coelho_modelo, (0.0, 0.0, -self.l_coelho)))
        p.esfera("marca_coelho_jogo", 0.03, marca_laranja, self.coelho, (0.0, 0.0, -self.l_coelho))
        self.rodas_modelo = {}
        for nome, (sx, sy) in {"FL": (-1, 1), "FR": (1, 1), "RL": (-1, -1), "RR": (1, -1)}.items():
            eixo = bpy_empty(f"fantasma_roda_{nome}", (0, 0, 0))
            p.cilindro(f"fantasma_pneu_{nome}", K.RAIO_RODA, 0.23, azul_forte, 28, eixo)
            for a in (0.0, math.pi / 2.0):                  # raios em cruz: sem eles um cilindro girando não mostra o giro
                raio = p.caixa(f"fantasma_raio_{nome}_{a:.1f}", -0.125, -K.RAIO_RODA * 0.94, -0.012, 0.125, K.RAIO_RODA * 0.94, 0.012, marca_azul, eixo)
                raio.rotation_euler.x = a
                raio.show_in_front = True
            self.rodas_modelo[nome] = (eixo, sx, sy)

    def _cameras(self):
        p = self.palco
        home = self.s["home"]
        x0 = home[0]
        ocultar_longe(p, (x0, -1.0, 0.0), 17.0)
        self.camera_lado_x = x0 - 20.0
        self.cameras = {
            "planta": p.nova_camera("cam_planta", (x0, -1.2, 14.0), ortografica=13.5, rotacao=(0.0, 0.0, -math.pi / 2.0)),
            "lado": p.nova_camera("cam_lado", (self.camera_lado_x, home[1], 1.0), alvo=(x0, home[1], 1.0), ortografica=7.0, corte=(18.4, 26.0)),
            "rua": p.nova_camera("cam_rua", (x0 + 7.0, -13.5, 1.9), alvo=(x0, -1.5, 0.9), fov=48.0),
            "dentro": p.nova_camera("cam_dentro", (x0 - 6.0, home[1], 1.0), alvo=(x0, home[1], 1.0), ortografica=1.3, corte=(5.55, 8.0)),
        }
        self.oculto_em = {"dentro": self.partes_do_casco[:2]}

    def _indice(self, t):
        return min(max(int(round(t * self.fps)), 0), len(self.t_jogo) - 1)

    def _chao(self, y):
        return float(K.altura_do_chao(y))

    def pose(self, t):
        k = self._indice(t)
        s = self.s
        self.carro.location = tuple(s["pos"][k])
        self.carro.rotation_euler = tuple(s["euler"][k])
        for i, nome in enumerate(("FL", "FR", "RL", "RR")):
            self.rodas[nome].location = tuple(s["roda_pos"][k, i])
            self.rodas[nome].rotation_euler = tuple(s["roda"][k, i])
        self.coelho.rotation_euler = tuple(s["coelho"][k])
        self.volante.rotation_quaternion = tuple(s["volante"][k])
        self.portao.location.z = float(self.p["z"][min(k, len(self.p["z"]) - 1)])
        # ---- modelo físico: meio carro, rodas que rolam sem deslizar, pêndulo forçado pela aceleração
        home = s["home"]
        y = float(self.y_modelo[k])
        self.casco.location = (home[0], y, float(self.z_modelo[k]))
        self.casco.rotation_euler = (float(self.theta_modelo[k]), 0.0, math.pi)
        self.pivo_coelho_modelo.rotation_euler = (float(self.coelho_modelo[k] - self.theta_modelo[k]), 0.0, 0.0)
        giro = float(self.percurso[k]) / K.RAIO_RODA                   # rolar para -Y é girar para +X no mundo
        for nome, (eixo, sx, sy) in self.rodas_modelo.items():
            y_roda = y - sy * K.ENTRE_EIXOS / 2.0                       # yaw = pi: a frente do carro aponta para -Y
            eixo.location = (home[0] - sx * K.BITOLA / 2.0, y_roda, K.RAIO_RODA + self._chao(y_roda))
            eixo.rotation_euler = (giro, 0.0, 0.0)
        # as câmeras que seguem o carro andam pelo instante, nunca pela imagem
        self.cameras["lado"].location.y = float(s["pos"][k, 1])
        self.cameras["dentro"].location.y = float(s["pos"][k, 1])
        atualizar()
        pivo = self.coelho.matrix_world.translation
        self.cameras["dentro"].location.y = pivo.y
        self.cameras["dentro"].location.z = pivo.z - 0.12
        atualizar()

    def dados(self, t):
        """(centro do carro do jogo, centro do carro do modelo) e a arfagem de cada um, só dos dados."""
        k = self._indice(t)
        return (Vector(self.s["pos"][k]), Vector((self.s["home"][0], float(self.y_modelo[k]), float(self.z_modelo[k]))),
                float(self.s["euler"][k, 0]), float(self.theta_modelo[k]))

    def rotulos(self, t):
        k = self._indice(t)
        v = float(self.s["sinais"]["speed"][k])
        return {"planta": [f"velocidade {abs(v) * 3.6:4.1f} km/h",
                           f"arfagem  jogo {math.degrees(self.s['euler'][k, 0]):+5.2f}  modelo {math.degrees(self.theta_modelo[k]):+5.2f} graus"],
                "dentro": [f"coelhinho  jogo {math.degrees(self.coelho_jogo[k]):+5.1f}  modelo {math.degrees(self.coelho_modelo[k]):+5.1f} graus"],
                "rua": [f"portão a {float(self.p['z'][min(k, len(self.p['z']) - 1)]):.2f} m"]}

    def curvas(self, t):
        t_ = self.t_jogo
        return [celula_curva(t_, [("modelo físico", np.degrees(self.theta_modelo), COR_AZUL_PIL),
                                  ("jogo", np.degrees(self.s["euler"][:, 0]), COR_LARANJA_PIL)], t,
                             "arfagem do corpo (nariz para cima +)", "graus", janela=self.janela),
                celula_curva(t_, [("modelo físico", np.degrees(self.coelho_modelo), COR_AZUL_PIL),
                                  ("jogo", np.degrees(self.coelho_jogo), COR_LARANJA_PIL)], t,
                             "coelhinho contra a vertical (para a frente +)", "graus", janela=self.janela)]

    def destaques(self):
        t = self.s["tempos"]
        centro_y = self.s["pos"][:, 1]
        # a frente do carro (a 2,43 m do centro, para -Y) cruza o plano do portão em y = 0; a traseira, quando o centro chega a y = -2,42
        t_nariz = float(self.t_jogo[int(np.argmax(centro_y <= 2.43))])
        t_traseira = float(self.t_jogo[int(np.argmax(centro_y <= -2.42))])
        return [(t["move_start"] + 0.9, "arrancando: o nariz sobe e o coelhinho vai para trás"),
                (t_nariz, "o nariz passa pelo portão"),
                (t_traseira, "a traseira passa pelo portão: já na rampa da entrada"),
                (t["move_end"] - 1.5, "freando: o nariz desce e o coelhinho vai para a frente")]


# --------------------------------------------------------------------------
# Saída: um MP4 e uma folha de contato por objeto
# --------------------------------------------------------------------------
CENAS = {                                 # nome: (fábrica, câmera do quadro de destaque, instante dele (None = o 1o destaque), quadros/s)
    "porta_25kg": (lambda palco: CenaPorta(palco, "master_hall"), "jogador", 0.9, 24),
    "porta_40kg": (lambda palco: CenaPorta(palco, "front", pesada=True), "jogador", 0.9, 24),
    "relogio": (lambda palco: CenaRelogio(palco), "perto", None, 20),
    "carro": (lambda palco: CenaCarro(palco), "rua", None, 20),
}


def gerar(nomes=None, saida=SAIDA, video=True, folha=True, eevee=False):
    """Gera `render3d_<nome>.mp4`, `render3d_<nome>_folha.png` (4 instantes) e, se pedido, `render3d_<nome>_eevee.png`."""
    import time
    os.makedirs(saida, exist_ok=True)
    for nome in nomes or CENAS:
        fabrica, camera_destaque, t_destaque, fps = CENAS[nome]
        inicio = time.time()
        palco = Palco()
        cena = fabrica(palco)
        print(f"[{nome}] cena montada em {time.time() - inicio:.1f} s", flush=True)
        if folha:
            caminho = cena.folha(os.path.join(saida, f"render3d_{nome}_folha.png"))
            print(f"[{nome}] {caminho} ({time.time() - inicio:.0f} s)", flush=True)
        if video:
            caminho, quadros = cena.video(os.path.join(saida, f"render3d_{nome}.mp4"), fps)
            print(f"[{nome}] {caminho}: {quadros} quadros a {fps} por segundo ({time.time() - inicio:.0f} s)", flush=True)
        if eevee:
            t = t_destaque if t_destaque is not None else cena.destaques()[1][0]
            caminho = cena.hero(os.path.join(saida, f"render3d_{nome}_eevee.png"), t, camera_destaque)
            print(f"[{nome}] {caminho} ({time.time() - inicio:.0f} s)", flush=True)


def main(argv=None):
    import sys
    argv = sys.argv[1:] if argv is None else argv
    nomes = [a for a in argv if not a.startswith("--")] or None
    gerar(nomes, video="--sem-video" not in argv, folha="--sem-folha" not in argv, eevee="--eevee" in argv)


if __name__ == "__main__":
    main()
