"""Formato comum de movimento: o mesmo recipiente para mocap real (CMU) e para gravação do jogo.

Tudo que compara "real" com "jogo" (metricas, graficos, comparar) lê um `Movimento`: posições mundiais das
mesmas juntas canônicas, no mesmo referencial (X direita, Y frente, Z cima, metros) e com os mesmos nomes. Quem
produz o `Movimento` é que sabe de onde cada junta vem:

    movimento_de_mocap(clip)         # CMU, por MAPA_CMU
    Gravacao.movimento()             # jogo, por MAPA_DANIEL (grava.py)

Este módulo é numpy puro: roda em qualquer Python, sem `bpy`.

Convenções:
    esquerda/direita  do próprio corpo (esquerda do Daniel fica em -X quando ele olha para +Y)
    olho              ponto entre os olhos. No mocap é a junta da cabeça mais um deslocamento fixo na cabeça; no jogo
                      sai do osso Neck (o mesmo `EYE_FROM_C7` que posiciona a câmera)
    cabeca_rot        [T,3,3] orientação do olhar na convenção de câmera do Blender (colunas: direita, cima, trás), de
                      modo que `cabeca_rot @ (0,0,-1)` é para onde a pessoa olha. No mocap, o quadro inicial define "olhar
                      nivelado para a frente"; só as variações dali em diante são medidas.
    piso              z do chão sob a pessoa; None = estimar a partir dos pés (metricas.estimar_piso)
"""
from dataclasses import dataclass, field, replace

import numpy as np

JUNTAS = ("quadril", "lombar",
          "coxa_e", "joelho_e", "tornozelo_e", "bola_e", "ponta_e",
          "coxa_d", "joelho_d", "tornozelo_d", "bola_d", "ponta_d",
          "c7", "cabeca", "olho",
          "ombro_e", "cotovelo_e", "punho_e",
          "ombro_d", "cotovelo_d", "punho_d")
INDICE = {nome: i for i, nome in enumerate(JUNTAS)}

# Segmentos para desenhar o esqueleto de linhas (junta, junta)
OSSOS = (("quadril", "coxa_e"), ("coxa_e", "joelho_e"), ("joelho_e", "tornozelo_e"), ("tornozelo_e", "bola_e"),
         ("bola_e", "ponta_e"),
         ("quadril", "coxa_d"), ("coxa_d", "joelho_d"), ("joelho_d", "tornozelo_d"), ("tornozelo_d", "bola_d"),
         ("bola_d", "ponta_d"),
         ("quadril", "lombar"), ("lombar", "c7"), ("c7", "cabeca"), ("cabeca", "olho"),
         ("c7", "ombro_e"), ("ombro_e", "cotovelo_e"), ("cotovelo_e", "punho_e"),
         ("c7", "ombro_d"), ("ombro_d", "cotovelo_d"), ("cotovelo_d", "punho_d"))

# junta canônica -> junta do BVH da CMU (as exceções, calculadas: `olho` e `ponta_*`, o "End Site" do pé)
MAPA_CMU = {"quadril": "Hips", "lombar": "Spine",
            "coxa_e": "LeftUpLeg", "joelho_e": "LeftLeg", "tornozelo_e": "LeftFoot", "bola_e": "LeftToeBase",
            "coxa_d": "RightUpLeg", "joelho_d": "RightLeg", "tornozelo_d": "RightFoot", "bola_d": "RightToeBase",
            "c7": "Neck1", "cabeca": "Head",
            "ombro_e": "LeftArm", "cotovelo_e": "LeftForeArm", "punho_e": "LeftHand",
            "ombro_d": "RightArm", "cotovelo_d": "RightForeArm", "punho_d": "RightHand"}

# junta canônica -> cabeça do osso do Daniel (sem_alvorada/body/skeleton.py); `cabeca` e `ponta_*` são as
# pontas (tail) de Neck e Toe
MAPA_DANIEL = {"quadril": "Hips", "lombar": "Spine2",
               "coxa_e": "Thigh.L", "joelho_e": "Shin.L", "tornozelo_e": "Foot.L", "bola_e": "Toe.L",
               "coxa_d": "Thigh.R", "joelho_d": "Shin.R", "tornozelo_d": "Foot.R", "bola_d": "Toe.R",
               "c7": "Neck",
               "ombro_e": "UpperArm.L", "cotovelo_e": "Forearm.L", "punho_e": "Hand.L",
               "ombro_d": "UpperArm.R", "cotovelo_d": "Forearm.R", "punho_d": "Hand.R"}

# Do osso do pé à sola: o tornozelo do Daniel fica a 8,5 cm do chão. Serve só para estimar o piso do mocap
# (o chão do BVH não tem altura conhecida); o erro dessa suposição vira erro de altura do quadril, não de ritmo.
ALTURA_TORNOZELO = 0.085
# deslocamento do olho a partir da junta `Head` do BVH: à frente e acima do crânio (m)
OLHO_FRENTE, OLHO_CIMA = 0.085, 0.075
CAMERA_NIVELADA = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])    # olha para +Y, nivelada


@dataclass
class Movimento:
    nome: str
    fonte: str                       # "mocap" | "jogo"
    fps: float
    pos: np.ndarray                  # [T, len(JUNTAS), 3]
    cabeca_rot: np.ndarray = None    # [T, 3, 3]
    camera: np.ndarray = None        # [T, 3] posição real da câmera (só o jogo; no mocap, o olho)
    piso: float = None
    eventos: list = field(default_factory=list)      # [(segundos, tipo, detalhe)]
    meta: dict = field(default_factory=dict)

    @property
    def quadros(self):
        return self.pos.shape[0]

    @property
    def duracao(self):
        return self.quadros / self.fps

    @property
    def t(self):
        return np.arange(self.quadros) / self.fps

    def j(self, nome):
        """Trajetória [T, 3] da junta canônica `nome`."""
        return self.pos[:, INDICE[nome]]

    def cabeca_pos(self):
        """Ponto que representa a cabeça nas medidas: a câmera do jogador no jogo, o olho no mocap."""
        return self.camera if self.camera is not None else self.j("olho")

    def trecho(self, inicio=0.0, fim=None):
        """Recorte entre `inicio` e `fim` (segundos)."""
        a = int(round(inicio * self.fps))
        b = self.quadros if fim is None else int(round(fim * self.fps))
        a, b = max(0, a), min(self.quadros, b)
        return replace(self, pos=self.pos[a:b].copy(),
                       cabeca_rot=None if self.cabeca_rot is None else self.cabeca_rot[a:b].copy(),
                       camera=None if self.camera is None else self.camera[a:b].copy(),
                       eventos=[(t - inicio, k, d) for t, k, d in self.eventos if a / self.fps <= t < b / self.fps])

    def reamostrar(self, fps):
        """Interpola para outra taxa (por exemplo 120 Hz do mocap para 30 do vídeo)."""
        alvo = np.arange(0.0, (self.quadros - 1) / self.fps + 1e-9, 1.0 / fps)
        return amostrar(self, alvo, fps)


def _interp(tempos, dados, alvo):
    """Interpolação linear de um array [T, ...] nos instantes `alvo`."""
    indice = np.interp(alvo, tempos, np.arange(len(tempos)))
    a = np.floor(indice).astype(int)
    b = np.minimum(a + 1, len(tempos) - 1)
    peso = (indice - a).reshape((-1,) + (1,) * (dados.ndim - 1))
    return dados[a] * (1.0 - peso) + dados[b] * peso


def _ortonormalizar(matrizes):
    u, _s, vt = np.linalg.svd(matrizes)
    return u @ vt


def amostrar(mov, alvo, fps):
    """`Movimento` avaliado nos instantes `alvo` (segundos); `fps` é a taxa do resultado (para os vídeos
    reamostrados com fase deformada ela é a taxa do vídeo, não a dos dados originais)."""
    tempos = mov.t
    return replace(mov, fps=fps, pos=_interp(tempos, mov.pos, alvo),
                   cabeca_rot=None if mov.cabeca_rot is None else _ortonormalizar(_interp(tempos, mov.cabeca_rot, alvo)),
                   camera=None if mov.camera is None else _interp(tempos, mov.camera, alvo),
                   eventos=list(mov.eventos))


def media_rotacoes(matrizes):
    """Rotação média (SVD da soma): serve para o 'olhar nivelado' do quadro inicial do mocap."""
    return _ortonormalizar(matrizes.sum(axis=0))


def movimento_de_mocap(clip, inicio=None, fim=None, nome=None):
    """`Movimento` a partir de um `bvh.Mocap`. `inicio`/`fim` em segundos recortam o clipe. Sem `inicio`, os primeiros
    0,1 s são descartados: os clipes da CMU começam numa pose de calibração que salta para a marcha em ~4 quadros."""
    inicio = 0.1 if inicio is None else inicio
    posicoes, rotacoes, pontas = clip.world_com_pontas()
    a = int(round(inicio * clip.fps))
    b = clip.frames if fim is None else int(round(fim * clip.fps))
    posicoes, rotacoes = posicoes[a:b], rotacoes[a:b]
    pontas = {k: v[a:b] for k, v in pontas.items()}
    pos = np.zeros((posicoes.shape[0], len(JUNTAS), 3))
    for canonica, osso in MAPA_CMU.items():
        pos[:, INDICE[canonica]] = posicoes[:, clip.index(osso)]
    for lado, osso in (("e", "LeftToeBase"), ("d", "RightToeBase")):
        pos[:, INDICE[f"ponta_{lado}"]] = pontas[osso]
    cabeca = rotacoes[:, clip.index("Head")]
    # quadro de referência do olhar: média dos primeiros 0,4 s, tratada como "nivelado, olhando +Y"
    n0 = max(1, int(0.4 * clip.fps))
    inicial = media_rotacoes(cabeca[:n0])
    cabeca_rot = cabeca @ (inicial.T @ CAMERA_NIVELADA)
    # o deslocamento do olho, escrito no quadro da cabeça (onde ele é fixo)
    no_cranio = inicial.T @ np.array([0.0, OLHO_FRENTE, OLHO_CIMA])
    pos[:, INDICE["olho"]] = pos[:, INDICE["cabeca"]] + np.einsum("tij,j->ti", cabeca, no_cranio)
    # o trajeto começa na origem
    pos[:, :, :2] -= pos[0, INDICE["quadril"], :2]
    return Movimento(nome or clip.name, "mocap", clip.fps, pos, cabeca_rot=cabeca_rot, camera=None,
                     meta={"unidade_m": clip.unit, "clipe": clip.name, "tronco_repouso": _tronco_em_repouso(clip)})


def _tronco_em_repouso(clip):
    """Inclinação (graus, + para a frente) do eixo lombar -> base do pescoço na pose zero do BVH."""
    repouso = np.zeros((len(clip.joints), 3))
    for j, pai in enumerate(clip.parent):
        repouso[j] = clip.offset[j] + (repouso[pai] if pai >= 0 else 0.0)
    eixo = repouso[clip.index("Neck1")] - repouso[clip.index("Spine")]      # eixos do arquivo: Y para cima, Z para a frente
    return float(np.degrees(np.arctan2(eixo[2], eixo[1])))
