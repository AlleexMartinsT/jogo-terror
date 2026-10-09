"""Gravador do jogo: executa uma linha do tempo de entradas no `Game` sem janela e guarda o que aconteceu por quadro.

    from tools.movimento_ref import grava
    jogo = grava.montar_jogo()                              # .blend completo (out/estado_completo_<versão>.blend), jogador numa pista livre
    jogo = grava.montar_jogo(palco=True)                    # só o corpo e o piso: ~10x mais rápido de montar
    rec = grava.gravar(jogo, grava.roteiro_de_texto("andar 5; parar 1; correr 3; agachar 2; virar 90 1.5"))
    mov = rec.movimento()                                   # `Movimento` (movimento.py) para metricas/graficos
    rec.salvar("out/f4_1/andar.npz"); rec = grava.Gravacao.carregar("out/f4_1/andar.npz")

Linha de comando (grava, resume as métricas e salva):
    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.grava "andar 6" --palco --saida out/f4_1/andar.npz

O que sai por quadro (taxa do jogo, 60 Hz; `cada=2` grava a 30 Hz sem mudar o passo da simulação):
    t, jogador (x, y, z, guinada, inclinação, velocidade, correndo, agachado, olho, fase do passo, bob, fôlego),
    câmera (posição, euler, matriz), todos os ossos do PlayerBody (cabeça e ponta de cada osso, no mundo),
    a pose dos ossos como gravada na armadura (para reproduzir o corpo em outro palco), olho do corpo,
    mãos (centro da palma, alvo no espaço da câmera, peso do alvo, dedos), abertura das portas,
    eventos: ruído do jogo (`game.noise_log`) e sons pedidos (`game.audio`, passos inclusive).

Os ossos vêm da armadura AVALIADA (`matrix_world @ pose_bone.head`), exatamente o que um render veria.
`ossos="fk"` lê o resultado do solver (sem avaliar a cena: bem mais rápido); o teste de coesão prova que os dois dão o mesmo.
Gravar muda o estado do jogo (o tempo passa, `noise_log` e o histórico do áudio nulo são esvaziados a cada quadro e
devolvidos ao final): use um jogo próprio para gravar.

Convenção dos giros: `giro` em graus/s, positivo = para a esquerda (a guinada do jogador cresce no sentido anti-horário);
`arfagem` em graus/s, positivo = olhar para cima.
"""
import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Matrix, Quaternion, Vector  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.body import skeleton as S  # noqa: E402
from sem_alvorada.engine.inputstate import InputState  # noqa: E402

from .movimento import INDICE, JUNTAS, MAPA_DANIEL, Movimento  # noqa: E402

# Um .blend salvo no Blender 5.x não abre no 4.2 (e vice-versa): cada versão guarda o seu cache.
BLEND_COMPLETO = os.path.join(ROOT, "out", "estado_completo_%d.%d.blend" % bpy.app.version[:2])
DT_JOGO = 1.0 / 60.0
OSSOS = list(S.BONE_ORDER)
OSSO_INDICE = {nome: i for i, nome in enumerate(OSSOS)}
PORTAS = sorted(op.id for op in layout.doors())


# --------------------------------------------------------------------------
# Roteiro: a linha do tempo de entradas
# --------------------------------------------------------------------------
@dataclass
class Passo:
    """Um trecho do roteiro: as mesmas entradas durante `duracao` segundos."""
    duracao: float
    mover: float = 0.0                 # +1 anda para a frente, -1 para trás
    lado: float = 0.0                  # +1 anda para a direita
    correr: bool = False
    agachar: bool = False
    giro: float = 0.0                  # graus/s, + esquerda
    arfagem: float = 0.0               # graus/s, + para cima
    entradas: dict = field(default_factory=dict)       # edges do primeiro quadro: {"interact": True, "flashlight": True}
    ao_iniciar: object = None          # função(jogo) chamada antes do primeiro quadro (abrir porta, mudar estado...)
    por_quadro: object = None          # função(jogo, t, k) chamada antes de CADA tick: t = segundos no passo, k = índice (mãos, alvos)
    rotulo: str = ""


def andar(segundos, **kw):
    return Passo(segundos, mover=1.0, rotulo=kw.pop("rotulo", "andar"), **kw)


def correr(segundos, **kw):
    return Passo(segundos, mover=1.0, correr=True, rotulo=kw.pop("rotulo", "correr"), **kw)


def parar(segundos, **kw):
    return Passo(segundos, rotulo=kw.pop("rotulo", "parar"), **kw)


def agachar(segundos, **kw):
    """Parado, agachado."""
    return Passo(segundos, agachar=True, rotulo=kw.pop("rotulo", "agachar"), **kw)


def andar_agachado(segundos, **kw):
    return Passo(segundos, mover=1.0, agachar=True, rotulo=kw.pop("rotulo", "agachado"), **kw)


def virar(graus, segundos, andando=True, **kw):
    """Gira `graus` (+ esquerda) em `segundos`, andando (padrão) ou parado."""
    return Passo(segundos, mover=1.0 if andando else 0.0, giro=graus / segundos, rotulo=kw.pop("rotulo", "virar"), **kw)


def olhar(graus, segundos, **kw):
    """Inclina o olhar `graus` (+ para cima) em `segundos`, parado."""
    return Passo(segundos, arfagem=graus / segundos, rotulo=kw.pop("rotulo", "olhar"), **kw)


def apertar(segundos=0.2, **entradas):
    """Um edge de entrada (interact, flashlight, reload) e a espera depois."""
    return Passo(segundos, entradas=entradas, rotulo="+".join(entradas))


_FABRICAS = {"andar": (andar, 1), "correr": (correr, 1), "parar": (parar, 1), "agachar": (agachar, 1),
             "agachado": (andar_agachado, 1), "virar": (virar, 2), "olhar": (olhar, 2)}


def roteiro_de_texto(texto):
    """"andar 5; parar 1; virar 90 1.5; correr 3" -> [Passo, ...]. Verbos: andar, correr, parar, agachar, agachado
    (anda agachado), virar GRAUS SEGUNDOS (anda e gira; "virar -90 1 parado" gira parado), olhar GRAUS SEGUNDOS."""
    passos = []
    for trecho in texto.split(";"):
        partes = trecho.split()
        if not partes:
            continue
        verbo, args = partes[0], partes[1:]
        if verbo not in _FABRICAS:
            raise ValueError(f"verbo desconhecido no roteiro: {verbo!r} (use {', '.join(_FABRICAS)})")
        fabrica, n = _FABRICAS[verbo]
        numeros = [float(a) for a in args[:n]]
        extras = {"andando": False} if verbo == "virar" and "parado" in args[n:] else {}
        passos.append(fabrica(*numeros, **extras))
    return passos


def duracao_total(roteiro):
    return sum(passo.duracao for passo in roteiro)


# --------------------------------------------------------------------------
# Montagem do jogo
# --------------------------------------------------------------------------
def _caixa_de_colisao(scene, nome, x0, y0, z0, x1, y1, z1):
    vertices = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
    malha = bpy.data.meshes.new(nome)
    malha.from_pydata(vertices, [], list(faces))
    malha.update()
    obj = bpy.data.objects.new(nome, malha)
    scene.collection.objects.link(obj)
    obj[C.P_COL] = 1
    obj.hide_render = True
    return obj


def cena_palco():
    """Cena mínima: câmera do jogador, o corpo (armadura e malha) e um piso grande de colisão."""
    from sem_alvorada import build as build_module
    from sem_alvorada.body import build as build_body
    from sem_alvorada.buildctx import BuildContext
    from sem_alvorada.engine import builder
    scene = build_module.fresh_scene()
    ctx = BuildContext(scene, verbose=False)
    builder.build(ctx)
    ctx.stage = "body"
    build_body(ctx)
    _caixa_de_colisao(scene, "COL_piso_palco", -60.0, -60.0, -0.5, 60.0, 60.0, 0.0)
    bpy.context.view_layer.update()
    return scene


def cena_completa(blend=BLEND_COMPLETO):
    """Abre o .blend completo; se ele não existe, constrói (leva ~100 s)."""
    if not os.path.exists(blend):
        from sem_alvorada import build as build_module
        os.makedirs(os.path.dirname(os.path.abspath(blend)), exist_ok=True)
        build_module.run(None, blend)
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
    return bpy.context.scene


def achar_pista(jogo, comprimento=8.0, nivel=0, folga=0.1):
    """(x, y, z, yaw) de um ponto de partida de onde o jogador anda `comprimento` m em linha reta sem tocar nada
    (paredes, móveis, folhas de porta) nem sair do piso do `nivel`. A de maior folga lateral ganha."""
    from sem_alvorada.engine import collision
    col = jogo.collision
    z0 = layout.LEVEL_Z[nivel]
    altura = 1.8
    portas = [d.segment for d in jogo.doors.doors.values() if d.level == nivel]

    def livre(x, y):
        if layout.room_at(x, y, z0) is None:
            return False
        dx, dy = col.push_out(x, y, z0, C.PLAYER_RADIUS + folga, altura)
        if abs(dx) + abs(dy) > 1e-6:
            return False
        chao = col.ground(x, y, z0)
        if chao is None or abs(chao - z0) > 0.03:
            return False
        for x0, y0, x1, y1, espessura in portas:
            px, py = collision.closest_on_segment(x, y, x0, y0, x1, y1)
            if math.hypot(x - px, y - py) < C.PLAYER_RADIUS + espessura + 0.1:
                return False
        return True

    melhor = None
    direcoes = ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (-1.0, 0.0, 0.0))
    for ix in range(0, 76):
        for iy in range(0, 42):
            x, y = ix * 0.25, iy * 0.25
            if not livre(x, y):
                continue
            for dx, dy, _ in direcoes:
                passos = int(comprimento / 0.5)
                if all(livre(x + dx * 0.5 * k, y + dy * 0.5 * k) for k in range(1, passos + 1)):
                    # folga lateral: quão longe das paredes (testa a 1 m de cada lado no meio)
                    lateral = 0
                    for lado in (-1.0, 1.0):
                        for dist in (0.5, 1.0, 1.5):
                            mx, my = x + dx * comprimento / 2 - dy * lado * dist, y + dy * comprimento / 2 + dx * lado * dist
                            lateral += dist if livre(mx, my) else 0
                    if melhor is None or lateral > melhor[0]:
                        yaw = math.atan2(-dx, dy)
                        melhor = (lateral, (x, y, z0, yaw))
    if melhor is None:
        raise RuntimeError(f"nenhuma pista livre de {comprimento} m no nível {nivel}")
    return melhor[1]


def montar_jogo(palco=False, blend=BLEND_COMPLETO, pista=8.0, nivel=0, **kw):
    """`Game` sem janela, fase "play", jogador no início de uma pista livre de `pista` metros olhando ao longo dela.

    `palco=True` monta só o corpo e o piso (segundos em vez de minutos). `kw` vai ao `Game`."""
    from sem_alvorada.engine.game import Game
    scene = cena_palco() if palco else cena_completa(blend)
    opcoes = dict(audio=False, entity=False, cutscenes=False)
    opcoes.update(kw)
    jogo = Game(scene, **opcoes)
    jogo.skip_intro = True
    entrada = InputState(confirm=True)
    jogo.tick(DT_JOGO, entrada)
    entrada.clear_edges()
    if jogo.phase != "play":
        raise RuntimeError(f"o jogo não entrou em 'play' (fase {jogo.phase})")
    if palco:
        x, y, z, yaw = 0.0, 0.0, 0.0, 0.0
    else:
        x, y, z, yaw = achar_pista(jogo, pista, nivel)
    jogo.place_player(x, y, z, yaw)
    for _ in range(3):
        jogo.tick(DT_JOGO, InputState())
    jogo.noise_log.clear()
    return jogo


# --------------------------------------------------------------------------
# Leitura dos ossos
# --------------------------------------------------------------------------
class LeitorOssos:
    """Lê a pose do corpo do jogador: armadura avaliada ("armadura") ou resultado do solver ("fk")."""

    def __init__(self, corpo, modo="armadura"):
        self.corpo = corpo
        self.modo = modo
        self.armadura = getattr(corpo, "armature", None)
        self.disponivel = self.armadura is not None
        if self.disponivel:
            self.nomes = [pb.name for pb in self.armadura.pose.bones]
            self.ordem = [self.nomes.index(n) for n in OSSOS]
            self.repouso = {pb.name: pb.bone.matrix_local.to_3x3() for pb in self.armadura.pose.bones}

    def ler(self):
        """(cabeças [B,3], pontas [B,3], olho [3], pose_b [B,4], quadril_loc [3], escala_peito [3], raiz [4])."""
        if self.modo == "fk" and getattr(self.corpo, "_solution", None) is not None:
            return self._ler_fk()
        return self._ler_armadura()

    def _ler_armadura(self):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        avaliada = self.armadura.evaluated_get(depsgraph)
        mundo = avaliada.matrix_world
        rotacao_mundo = mundo.to_3x3()
        osso = avaliada.pose.bones
        cabecas = np.zeros((len(OSSOS), 3))
        pontas = np.zeros((len(OSSOS), 3))
        for i, nome in enumerate(OSSOS):
            pb = osso[nome]
            cabecas[i] = mundo @ pb.head
            pontas[i] = mundo @ pb.tail
        pescoco = osso["Neck"]
        q_absoluta = pescoco.matrix.to_3x3() @ self.repouso["Neck"].inverted()
        olho = mundo @ (pescoco.head + q_absoluta @ S.EYE_FROM_C7)
        original = self.armadura.pose.bones
        pose_b = np.array([tuple(original[nome].rotation_quaternion) for nome in OSSOS])
        quadril_loc = np.array(original["Hips"].location)
        escala = np.array(original["Chest"].scale)
        raiz = np.array([*self.armadura.location, self.armadura.rotation_euler.z])
        return cabecas, pontas, np.array(olho), pose_b, quadril_loc, escala, raiz

    def _ler_fk(self):
        solucao, corpo = self.corpo._solution, self.corpo
        raiz_pos, guinada = corpo._root, corpo._yaw
        giro = Matrix.Rotation(guinada, 3, "Z")
        cabecas = np.array([tuple(raiz_pos + giro @ solucao.head[i]) for i in range(len(OSSOS))])
        pontas = np.array([tuple(raiz_pos + giro @ solucao.tail(nome)) for nome in OSSOS])
        pescoco = OSSO_INDICE["Neck"]
        olho = raiz_pos + giro @ (solucao.head[pescoco] + solucao.world[pescoco] @ S.EYE_FROM_C7)
        pose_b = np.array([tuple(corpo._bones[i][0].rotation_quaternion) for i in range(len(OSSOS))])
        quadril_loc = np.array(corpo._bones[0][0].location)
        escala = np.array(corpo._bones[OSSO_INDICE["Chest"]][0].scale)
        raiz = np.array([*raiz_pos, guinada])
        return cabecas, pontas, np.array(olho), pose_b, quadril_loc, escala, raiz


# --------------------------------------------------------------------------
# A gravação
# --------------------------------------------------------------------------
@dataclass
class Gravacao:
    nome: str
    fps: float
    t: np.ndarray                              # [N] segundos desde o início
    jogador: dict                              # nome -> [N]
    camera_pos: np.ndarray                     # [N, 3]
    camera_rot: np.ndarray                     # [N, 3, 3] convenção de câmera do Blender
    cabecas: np.ndarray = None                 # [N, B, 3] cabeça de cada osso, mundo (B = len(OSSOS))
    pontas: np.ndarray = None                  # [N, B, 3] ponta (tail)
    olho_corpo: np.ndarray = None              # [N, 3]
    pose_b: np.ndarray = None                  # [N, B, 4] rotation_quaternion de cada pose bone
    quadril_loc: np.ndarray = None             # [N, 3]
    escala_peito: np.ndarray = None            # [N, 3]
    raiz: np.ndarray = None                    # [N, 4] x, y, z, guinada da armadura
    palma: np.ndarray = None                   # [N, 2, 3] centro da palma (esquerda, direita), mundo
    alvo_mao: np.ndarray = None                # [N, 2, 3] alvo da mão no espaço da câmera (NaN sem alvo)
    peso_alvo: np.ndarray = None               # [N, 2]
    dedos: np.ndarray = None                   # [N, 2, 5] curvas dos dedos (polegar ao mindinho)
    abertura_dedos: np.ndarray = None          # [N, 2]
    portas: np.ndarray = None                  # [N, len(PORTAS)] abertura 0..1
    eventos: list = field(default_factory=list)       # [(segundos, tipo, detalhe...)]
    passos: list = field(default_factory=list)        # [(inicio, fim, rotulo)] do roteiro
    meta: dict = field(default_factory=dict)

    @property
    def quadros(self):
        return len(self.t)

    @property
    def tem_ossos(self):
        return self.cabecas is not None

    # ---- conversão ----
    def movimento(self, piso="auto", usar_camera=True):
        """`Movimento` canônico (movimento.py). `piso`: "auto" = z do jogador no início (pista plana); None = estimar."""
        if not self.tem_ossos:
            raise RuntimeError("gravação sem ossos (ossos='nenhum'): não há corpo para medir")
        pos = np.zeros((self.quadros, len(JUNTAS), 3))
        for canonica, osso in MAPA_DANIEL.items():
            pos[:, INDICE[canonica]] = self.cabecas[:, OSSO_INDICE[osso]]
        pos[:, INDICE["cabeca"]] = self.pontas[:, OSSO_INDICE["Neck"]]
        pos[:, INDICE["ponta_e"]] = self.pontas[:, OSSO_INDICE["Toe.L"]]
        pos[:, INDICE["ponta_d"]] = self.pontas[:, OSSO_INDICE["Toe.R"]]
        pos[:, INDICE["olho"]] = self.olho_corpo
        if piso == "auto":
            piso = float(self.jogador["z"][0])
        eixo = S.BONE_MAP["Neck"].head - S.BONE_MAP["Spine2"].head
        meta = dict(self.meta, tronco_repouso=math.degrees(math.atan2(eixo.y, eixo.z)))
        return Movimento(self.nome, "jogo", self.fps, pos, cabeca_rot=self.camera_rot.copy(),
                         camera=self.camera_pos.copy() if usar_camera else None, piso=piso,
                         eventos=[(e[0], e[1], e[2:]) for e in self.eventos], meta=meta)

    def movimento_do_passo(self, passo, margem=0.7, **kw):
        """`Movimento` só do miolo de um passo do roteiro (por índice ou rótulo; a primeira ocorrência), sem os
        `margem` segundos iniciais de aceleração. `kw` vai a `movimento`."""
        if isinstance(passo, str):
            indice = next(i for i, p in enumerate(self.passos) if p[2] == passo)
        else:
            indice = passo
        inicio, fim, _rotulo = self.passos[indice]
        return self.movimento(**kw).trecho(inicio + margem, fim)

    def trecho(self, inicio=0.0, fim=None):
        """Recorte em segundos (zera o relógio no início do trecho)."""
        a = int(round(inicio * self.fps))
        b = self.quadros if fim is None else min(self.quadros, int(round(fim * self.fps)))
        novo = {}
        for chave, valor in self.__dict__.items():
            if isinstance(valor, np.ndarray) and valor.shape[:1] == (self.quadros,):
                novo[chave] = valor[a:b].copy()
            elif chave == "jogador":
                novo[chave] = {k: v[a:b].copy() for k, v in valor.items()}
            else:
                novo[chave] = valor
        novo["t"] = novo["t"] - novo["t"][0] if len(novo["t"]) else novo["t"]
        novo["eventos"] = [(e[0] - inicio, *e[1:]) for e in self.eventos if a / self.fps <= e[0] < b / self.fps]
        return Gravacao(**novo)

    # ---- disco ----
    def salvar(self, caminho):
        os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
        arrays = {}
        for chave, valor in self.__dict__.items():
            if isinstance(valor, np.ndarray):
                arrays[chave] = valor
        for chave, valor in self.jogador.items():
            arrays[f"jogador__{chave}"] = valor
        texto = json.dumps({"nome": self.nome, "fps": self.fps, "eventos": self.eventos, "passos": self.passos,
                            "meta": self.meta, "campos_jogador": list(self.jogador)}, ensure_ascii=False, default=float)
        np.savez_compressed(caminho, _json=np.array(texto), **arrays)

    @classmethod
    def carregar(cls, caminho):
        with np.load(caminho, allow_pickle=False) as arquivo:
            dados = json.loads(str(arquivo["_json"]))
            campos = {chave: arquivo[chave] for chave in arquivo.files if chave != "_json" and not chave.startswith("jogador__")}
            jogador = {chave: arquivo[f"jogador__{chave}"] for chave in dados["campos_jogador"]}
        return cls(nome=dados["nome"], fps=dados["fps"], jogador=jogador, eventos=[tuple(e) for e in dados["eventos"]],
                   passos=[tuple(p) for p in dados["passos"]], meta=dados["meta"], **campos)


def _vetor(valor):
    return np.array([valor.x, valor.y, valor.z])


def _estado_mao(corpo, lado):
    """(palma mundo [3], alvo [3], peso, curvas [5], abertura) de um braço; NaN onde o braço não informa."""
    braco = corpo.arm(lado)
    palma = braco.hand_world_position() if hasattr(braco, "hand_world_position") else None
    alvo = getattr(braco, "_target", None)
    curvas = getattr(braco, "_curls", None)
    return (np.array(palma) if palma is not None else np.full(3, np.nan),
            _vetor(alvo) if alvo is not None else np.full(3, np.nan),
            float(getattr(braco, "_weight", 0.0) or 0.0),
            np.array(curvas, float) if curvas is not None else np.full(5, np.nan),
            float(getattr(braco, "_spread", 0.0) or 0.0))


CAMPOS_JOGADOR = ("x", "y", "z", "z_visual", "guinada", "inclinacao", "velocidade", "correndo", "agachado", "olho",
                  "fase_passo", "bob_lateral", "bob_vertical", "folego", "lanterna")


def gravar(jogo, roteiro, nome="gravacao", ossos="armadura", cada=1, prefacio=0.0, mao_livre=True):
    """Executa `roteiro` (lista de `Passo`) em `jogo` e devolve a `Gravacao`.

    ossos: "armadura" (avaliada, padrão), "fk" (resultado do solver, rápido) ou "nenhum" (só jogador e câmera).
    cada: grava 1 de cada `cada` quadros (a simulação roda sempre a 60 Hz).
    prefacio: segundos parado antes de gravar (deixa o corpo assentar)."""
    jogador = jogo.player
    leitor = LeitorOssos(jogo.body, ossos) if ossos != "nenhum" else None
    if leitor is not None and not leitor.disponivel:
        leitor = None
    tem_ossos = leitor is not None
    amostras = {chave: [] for chave in CAMPOS_JOGADOR}
    camera_pos, camera_rot = [], []
    listas = {k: [] for k in ("cabecas", "pontas", "olho_corpo", "pose_b", "quadril_loc", "escala_peito", "raiz",
                               "palma", "alvo_mao", "peso_alvo", "dedos", "abertura_dedos", "portas")}
    tempos, eventos, passos_marcados, avisos = [], [], [], []
    ruido_antes, sons_antes = list(jogo.noise_log), None
    audio = jogo.audio
    guarda_audio = hasattr(audio, "played") and hasattr(audio, "footsteps")
    if guarda_audio:
        sons_antes = (list(audio.played), list(audio.footsteps))
        audio.played.clear()
        audio.footsteps.clear()
    jogo.noise_log.clear()
    entrada = InputState()
    relogio = 0.0
    tique = 0

    def amostrar():
        nonlocal relogio
        tempos.append(relogio)
        amostras["x"].append(jogador.x), amostras["y"].append(jogador.y), amostras["z"].append(jogador.z)
        amostras["z_visual"].append(jogador.z_visual)
        amostras["guinada"].append(jogador.yaw), amostras["inclinacao"].append(jogador.pitch)
        amostras["velocidade"].append(jogador.speed), amostras["correndo"].append(float(jogador.running))
        amostras["agachado"].append(float(jogador.crouching)), amostras["olho"].append(jogador.eye)
        amostras["fase_passo"].append(jogador.stride_phase)
        lateral, vertical = jogador.bob_offset()
        amostras["bob_lateral"].append(lateral), amostras["bob_vertical"].append(vertical)
        amostras["folego"].append(jogador.stamina)
        amostras["lanterna"].append(float(getattr(jogo.flashlight, "intensity", 0.0)))
        camera = jogo.player_cam
        camera_pos.append(tuple(camera.location))
        camera_rot.append(np.array(Euler(camera.rotation_euler, "XYZ").to_matrix()))
        listas["portas"].append([jogo.doors.doors[p].openness if p in jogo.doors.doors else 0.0 for p in PORTAS])
        if tem_ossos:
            bpy.context.view_layer.update()
            cabecas, pontas, olho, pose_b, loc, escala, raiz = leitor.ler()
            for chave, valor in (("cabecas", cabecas), ("pontas", pontas), ("olho_corpo", olho), ("pose_b", pose_b),
                                 ("quadril_loc", loc), ("escala_peito", escala), ("raiz", raiz)):
                listas[chave].append(valor)
        if mao_livre:
            estados = [_estado_mao(jogo.body, lado) for lado in "LR"]
            listas["palma"].append([e[0] for e in estados]), listas["alvo_mao"].append([e[1] for e in estados])
            listas["peso_alvo"].append([e[2] for e in estados]), listas["dedos"].append([e[3] for e in estados])
            listas["abertura_dedos"].append([e[4] for e in estados])

    def colher_eventos():
        for fonte, tipo, volume, _t in list(jogo.noise_log):
            eventos.append((relogio, "ruido", fonte, tipo, float(volume)))
        jogo.noise_log.clear()
        if guarda_audio:
            for som in list(audio.played):
                eventos.append((relogio, "som", som[0], float(som[2]) if len(som) > 2 else 1.0))
            for piso, intensidade in list(audio.footsteps):
                eventos.append((relogio, "passo_som", piso, float(intensidade)))
            audio.played.clear()
            audio.footsteps.clear()

    if prefacio > 0:
        for _ in range(int(round(prefacio / DT_JOGO))):
            jogo.tick(DT_JOGO, InputState())
        jogo.noise_log.clear()
    for passo in roteiro:
        inicio = relogio
        if passo.ao_iniciar is not None:
            passo.ao_iniciar(jogo)
        for k in range(max(1, int(round(passo.duracao / DT_JOGO)))):
            entrada = InputState(move_y=passo.mover, move_x=passo.lado, run=passo.correr, crouch=passo.agachar,
                                 look_dx=-math.radians(passo.giro) * DT_JOGO, look_dy=math.radians(passo.arfagem) * DT_JOGO)
            if k == 0:
                for chave, valor in passo.entradas.items():
                    setattr(entrada, chave, valor)
            if passo.por_quadro is not None:
                passo.por_quadro(jogo, k * DT_JOGO, k)
            jogo.tick(DT_JOGO, entrada)
            relogio += DT_JOGO
            tique += 1
            colher_eventos()
            if (tique - 1) % cada == 0:
                amostrar()
        passos_marcados.append((inicio, relogio, passo.rotulo))
        if passo.mover and passo.duracao > 1.0 and jogador.speed < 0.3:
            avisos.append(f"o jogador parou de andar durante '{passo.rotulo}' (parede à frente?): a pista é curta para o roteiro")

    jogo.noise_log.extend(ruido_antes)
    if guarda_audio:
        audio.played.extend(sons_antes[0])
        audio.footsteps.extend(sons_antes[1])
    n = len(tempos)
    gravacao = Gravacao(nome=nome, fps=1.0 / (DT_JOGO * cada), t=np.array(tempos),
                        jogador={k: np.array(v) for k, v in amostras.items()},
                        camera_pos=np.array(camera_pos).reshape(n, 3), camera_rot=np.array(camera_rot).reshape(n, 3, 3),
                        eventos=eventos, passos=passos_marcados,
                        meta={"avisos": avisos, "inicio": [float(jogador.x), float(jogador.y), float(jogador.z), float(jogador.yaw)],
                              "ossos": ossos if tem_ossos else "nenhum", "cada": cada, "ossos_nomes": OSSOS,
                              "portas": PORTAS, "palco": bool(jogo.scene.objects.get("COL_piso_palco")),
                              "velocidades": {"andar": C.SPEED_WALK, "correr": C.SPEED_RUN, "agachado": C.SPEED_CROUCH}})
    if tem_ossos:
        for chave in ("cabecas", "pontas", "olho_corpo", "pose_b", "quadril_loc", "escala_peito", "raiz"):
            setattr(gravacao, chave, np.array(listas[chave]))
    if mao_livre:
        for chave in ("palma", "alvo_mao", "peso_alvo", "dedos", "abertura_dedos"):
            setattr(gravacao, chave, np.array(listas[chave], float))
    gravacao.portas = np.array(listas["portas"], float).reshape(n, len(PORTAS))
    return gravacao


# --------------------------------------------------------------------------
# Terminal
# --------------------------------------------------------------------------
def resumo(rec):
    """Texto curto: duração, avisos e, com ossos, as principais métricas de cada trecho de movimento do roteiro."""
    from . import metricas
    linhas = [f"{rec.nome}: {rec.quadros} quadros a {rec.fps:g} Hz ({rec.t[-1]:.1f} s), "
              f"{len(rec.eventos)} eventos ({sum(1 for e in rec.eventos if e[1] == 'ruido')} de ruído)"]
    linhas += [f"  AVISO: {aviso}" for aviso in rec.meta.get("avisos", [])]
    if not rec.tem_ossos:
        return "\n".join(linhas)
    chaves = ("velocidade", "cadencia", "passada", "passo", "apoio_pct", "duplo_apoio_passo_pct", "voo_pct",
              "deslize_apoio", "cabeca_osc_vert", "cabeca_osc_lat")
    for i, (inicio, fim, rotulo) in enumerate(rec.passos):
        if fim - inicio < 1.8 or rotulo in ("parar", "olhar", "agachar"):
            continue
        marcha = metricas.medir_tudo(rec.movimento_do_passo(i))
        valores = "  ".join(f"{c}={marcha.v[c]:.3g}" for c in chaves if np.isfinite(marcha.v.get(c, np.nan)))
        linhas.append(f"  [{inicio:4.1f}-{fim:4.1f} s] {rotulo}: {valores}")
    return "\n".join(linhas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roteiro", help='por exemplo "andar 5; parar 1; correr 3"')
    ap.add_argument("--palco", action="store_true", help="só corpo e piso (rápido)")
    ap.add_argument("--blend", default=BLEND_COMPLETO)
    ap.add_argument("--ossos", default="armadura", choices=("armadura", "fk", "nenhum"))
    ap.add_argument("--cada", type=int, default=1)
    ap.add_argument("--saida", help="grava a gravação neste .npz")
    ap.add_argument("--nome", default="gravacao")
    args = ap.parse_args(argv)
    jogo = montar_jogo(palco=args.palco, blend=args.blend)
    rec = gravar(jogo, roteiro_de_texto(args.roteiro), nome=args.nome, ossos=args.ossos, cada=args.cada, prefacio=0.3)
    print(resumo(rec))
    if args.saida:
        rec.salvar(args.saida)
        print("salvo em", args.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None))
