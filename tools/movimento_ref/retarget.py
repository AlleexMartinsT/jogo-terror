"""Retarget: o Daniel (o corpo do jogo) fazendo o movimento de uma pessoa real capturada.

    from tools.movimento_ref import cmu, retarget
    alvo = retarget.retargetar(cmu.carregar("07_01", 0.1, 2.6))       # Retarget
    alvo.raiz                # [T, 4] x, y, z (chão), guinada do corpo no mundo (já na escala do Daniel)
    alvo.locais              # [T, B, 4] quaternions locais na convenção do solver (body/solver.py), ordem skeleton.BONE_ORDER
    alvo.movimento()         # Movimento (movimento.py) do Daniel retargetado: mesmas métricas do mocap e do jogo
    alvo.erro_de_juntas()    # distância (m) de cada junta ao mocap escalado: a qualidade do retarget em números

Como funciona (casamento de direção, osso a osso, no referencial do corpo):
    1. O corpo todo é uma cópia do mocap com a escala `s` = perna do Daniel / perna da pessoa (translação, alturas e
       passada escalam juntas; um pé parado no chão continua parado). O chão é o do tornozelo plano: o tornozelo do Daniel
       fica a 8,5 cm do piso quando o pé está plano, como no jogo.
    2. A guinada do corpo é a direção da pelve, suavizada. O quadril (Hips) recebe a orientação completa da pelve
       (direita, frente); o resto é relativo a ela.
    3. Cada osso recebe a rotação que leva a sua direção de repouso à direção do segmento correspondente do mocap, olhando
       do pai para o filho (`W_osso = W_pai @ q`, com `q` a rotação local do solver). Quando a direção não basta (pernas e
       braços, pés, mãos, coluna), um segundo vetor fecha o giro em torno do osso: o eixo do joelho/cotovelo (dobradiça
       comum, como em `solver._chain_frames`), o "para cima" do pé, os eixos da palma, a linha dos ombros.
    4. O antebraço reparte a torção entre `Forearm`, `ForearmRoll` e `Hand` na proporção do solver (62% no meio).

Mapa mocap -> Daniel:
    Hips (pelve completa: linha dos quadris + coluna) | Spine1 <- LowerBack->Spine | Spine2 <- Spine->Spine1 |
    Spine3 <- Spine1->Neck1 | Neck <- Neck1->Head (+ eixo direito da cabeça) | Clavicle <- Shoulder->Arm |
    UpperArm <- Arm->ForeArm | Forearm, ForearmRoll <- ForeArm->Hand | Hand <- quadro da mão do mocap |
    Thigh <- UpLeg->Leg | Shin <- Leg->Foot | Foot <- Foot->ToeBase | Toe <- ToeBase->ponta do pé.

LIMITES (o que este retarget NÃO reproduz; olhe o quadro antes de tirar conclusões):
    - Dedos: o BVH da CMU tem um dedo (indicador) e um polegar sem articulações. Os dedos do Daniel ficam no preset
      "relaxed" o tempo todo.
    - Torção dos ossos longos: a rotação do braço e da coxa em torno do próprio eixo vem da dobradiça (plano do joelho
      e do cotovelo), não de medida. Em membro esticado a dobradiça é a do quadro anterior.
    - Proporções: o Daniel tem tronco e braços proporcionalmente mais longos que o esqueleto da CMU (que tem tronco
      curto); por isso, no casamento de direção, as mãos NÃO chegam aos mesmos pontos do espaço que as do mocap
      (`bracos="ik"` leva o punho ao ponto escalado pelo braço, para cenas de alcance). Pernas: o tornozelo erra
      até ~2 cm na fase de balanço (joelho muito dobrado) e ~1 cm no apoio; o pé de apoio não escorrega mais que o do mocap.
    - A cabeça do Daniel não existe na malha (primeira pessoa): o palco acrescenta uma esfera de marcação. O olhar vem
      da cabeça do mocap (`olhar_pos` e `olhar_rot`), o osso `Neck` só acompanha a direção do pescoço.
    - Rotações do pé são as do mocap (rolagem pela linha pé-ponta); a ponta do pé (`Toe`) copia o dedão do mocap.
    - Sem corpo sólido: nada impede a mão de atravessar a coxa ou o tronco se o mocap as aproxima mais do que o
      volume do Daniel permite (ombros e barriga mais largos).
"""
import math
from dataclasses import dataclass, field

import bpy  # noqa: F401
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from sem_alvorada.body import fingers as F
from sem_alvorada.body import skeleton as S
from sem_alvorada.body.solver import ArmGoal, PoseSpec, solve

from .metricas import comprimento_perna, estimar_piso, gaussiano
from .movimento import ALTURA_TORNOZELO, INDICE, JUNTAS, MAPA_DANIEL, Movimento, movimento_de_mocap

ROLL_SHARE = 0.62                  # a mesma fração da torção do antebraço que o solver entrega ao ForearmRoll
EIXO_Z = np.array([0.0, 0.0, 1.0])
PERNA_DANIEL = float(np.linalg.norm(np.array(S.BONE_MAP["Shin.L"].head) - np.array(S.BONE_MAP["Thigh.L"].head))
                     + np.linalg.norm(np.array(S.BONE_MAP["Foot.L"].head) - np.array(S.BONE_MAP["Shin.L"].head)))
BRACO_DANIEL = float(S.UPPER_ARM_LEN + S.FOREARM_LEN)


# --------------------------------------------------------------------------
# Álgebra de quadros
# --------------------------------------------------------------------------
def unitario(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def quadro(direcao, dica):
    """Matriz 3x3 de colunas (direção, dica ortogonalizada, produto vetorial). Define uma orientação completa."""
    a = unitario(np.asarray(direcao, float))
    h = np.asarray(dica, float)
    h = h - a * (a @ h)
    if np.linalg.norm(h) < 1e-6:                      # dica paralela à direção: qualquer perpendicular serve
        h = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        h = h - a * (a @ h)
    h = unitario(h)
    return np.stack([a, h, np.cross(a, h)], axis=1)


def arco(de, para):
    """Rotação (3x3) de menor ângulo que leva o vetor `de` a `para`."""
    de, para = unitario(np.asarray(de, float)), unitario(np.asarray(para, float))
    eixo = np.cross(de, para)
    seno, cosseno = np.linalg.norm(eixo), float(de @ para)
    if seno < 1e-9:
        if cosseno > 0:
            return np.eye(3)
        ortogonal = unitario(np.cross(de, [1.0, 0.0, 0.0] if abs(de[0]) < 0.9 else [0.0, 1.0, 0.0]))
        return 2.0 * np.outer(ortogonal, ortogonal) - np.eye(3)
    k = eixo / seno
    cruz = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + seno * cruz + (1.0 - cosseno) * cruz @ cruz


def para_quaternion(r):
    return Matrix(r.tolist()).to_quaternion()


def de_quaternion(q):
    return np.array(q.to_matrix())


def torcao_em_torno(r, eixo):
    """Ângulo (rad) de torção da rotação `r` em torno de `eixo` (decomposição swing-twist)."""
    q = Matrix(r.tolist()).to_quaternion()
    projecao = np.array([q.x, q.y, q.z]) @ eixo
    angulo = 2.0 * math.atan2(projecao, q.w)
    return (angulo + math.pi) % (2.0 * math.pi) - math.pi


def rotacao_z(angulo):
    c, s = math.cos(angulo), math.sin(angulo)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


# --------------------------------------------------------------------------
# Resultado
# --------------------------------------------------------------------------
@dataclass
class Retarget:
    nome: str
    fps: float
    escala: float
    raiz: np.ndarray                  # [T, 4] x, y, z, guinada
    locais: np.ndarray                # [T, B, 4] w, x, y, z de cada osso (convenção do solver)
    deslocamento_quadril: np.ndarray  # [T, 3] hips_shift no espaço do corpo
    olhar_pos: np.ndarray             # [T, 3] olho (mundo), do esqueleto retargetado
    olhar_rot: np.ndarray             # [T, 3, 3] orientação do olhar (convenção de câmera do Blender)
    origem: Movimento = None          # o mocap canônico de que veio
    _solucoes: dict = field(default_factory=dict, repr=False)

    @property
    def quadros(self):
        return len(self.raiz)

    def especificacao(self, k):
        """`PoseSpec` do quadro k, pronta para `solver.solve`."""
        rot = {nome: Quaternion(tuple(self.locais[k, i])) for i, nome in enumerate(S.BONE_ORDER)}
        return PoseSpec(hips_shift=Vector(self.deslocamento_quadril[k]), rot=rot)

    def solucao(self, k):
        if k not in self._solucoes:
            self._solucoes[k] = solve(self.especificacao(k))
        return self._solucoes[k]

    def cabecas(self, k):
        """Posição mundial da cabeça de cada osso no quadro k: [B, 3]."""
        solucao = self.solucao(k)
        x, y, z, guinada = self.raiz[k]
        giro = Matrix.Rotation(guinada, 3, "Z")
        return np.array([tuple(Vector((x, y, z)) + giro @ solucao.head[i]) for i in range(len(S.BONE_ORDER))])

    def movimento(self, nome=None):
        """O Daniel retargetado como `Movimento` canônico (mesmas juntas do mocap e do jogo)."""
        total = self.quadros
        pos = np.zeros((total, len(JUNTAS), 3))
        indice = {n: i for i, n in enumerate(S.BONE_ORDER)}
        for k in range(total):
            solucao = self.solucao(k)
            x, y, z, guinada = self.raiz[k]
            raiz = Vector((x, y, z))
            giro = Matrix.Rotation(guinada, 3, "Z")
            cabeca = lambda i: np.array(raiz + giro @ solucao.head[i])           # noqa: E731
            for canonica, osso in MAPA_DANIEL.items():
                pos[k, INDICE[canonica]] = cabeca(indice[osso])
            pos[k, INDICE["cabeca"]] = np.array(raiz + giro @ solucao.tail("Neck"))
            pos[k, INDICE["ponta_e"]] = np.array(raiz + giro @ solucao.tail("Toe.L"))
            pos[k, INDICE["ponta_d"]] = np.array(raiz + giro @ solucao.tail("Toe.R"))
        pos[:, INDICE["olho"]] = self.olhar_pos
        meta = dict(self.origem.meta) if self.origem is not None else {}
        eixo = S.BONE_MAP["Neck"].head - S.BONE_MAP["Spine2"].head
        meta.update(tronco_repouso=math.degrees(math.atan2(eixo.y, eixo.z)), retarget=True, escala=self.escala)
        return Movimento(nome or f"{self.nome} (Daniel)", "mocap", self.fps, pos, cabeca_rot=self.olhar_rot.copy(),
                         piso=0.0, meta=meta)

    def erro_de_juntas(self):
        """Distância (m) entre cada junta canônica do Daniel e a do mocap escalado/transladado: {junta: (média, máx)}."""
        alvo = self.alvo_escalado()
        meu = self.movimento().pos
        erro = np.linalg.norm(meu - alvo, axis=2)
        return {JUNTAS[j]: (float(erro[:, j].mean()), float(erro[:, j].max())) for j in range(len(JUNTAS))
                if JUNTAS[j] not in ("olho",)}

    def alvo_escalado(self):
        """Posições do mocap depois da escala/translação/altura do retarget: o que o Daniel tenta alcançar."""
        origem = self.origem
        quadril = (origem.j("coxa_e") + origem.j("coxa_d")) / 2.0
        piso_tornozelo = estimar_piso(origem)[0]
        base = quadril[0, :2]
        saida = origem.pos.copy()
        saida[:, :, :2] = (saida[:, :, :2] - base) * self.escala
        saida[:, :, 2] = ALTURA_TORNOZELO + self.escala * (saida[:, :, 2] - piso_tornozelo)
        return saida


# --------------------------------------------------------------------------
# O retarget
# --------------------------------------------------------------------------
REPOUSO = {nome: np.array(S.BONE_MAP[nome].rest_dir) for nome in S.BONE_ORDER}
INDICE_OSSO = {nome: i for i, nome in enumerate(S.BONE_ORDER)}
PAI = S.PARENT_INDEX


def _juntas_mocap(clip, posicoes, pontas):
    """Atalho: posição [T,3] de cada junta do BVH que o retarget usa."""
    def p(nome):
        return posicoes[:, clip.index(nome)]
    grupos = {"raiz": p("Hips"), "lombar": p("Spine"), "peito": p("Spine1"), "pescoco": p("Neck1"), "cabeca": p("Head")}
    for lado, prefixo in (("L", "Left"), ("R", "Right")):
        grupos[f"clavicula_{lado}"] = p(f"{prefixo}Shoulder")
        grupos[f"ombro_{lado}"] = p(f"{prefixo}Arm")
        grupos[f"cotovelo_{lado}"] = p(f"{prefixo}ForeArm")
        grupos[f"punho_{lado}"] = p(f"{prefixo}Hand")
        grupos[f"dedos_{lado}"] = p(f"{prefixo}HandIndex1")
        grupos[f"coxa_{lado}"] = p(f"{prefixo}UpLeg")
        grupos[f"joelho_{lado}"] = p(f"{prefixo}Leg")
        grupos[f"tornozelo_{lado}"] = p(f"{prefixo}Foot")
        grupos[f"bola_{lado}"] = p(f"{prefixo}ToeBase")
        grupos[f"ponta_{lado}"] = pontas[f"{prefixo}ToeBase"]
    return grupos


# eixos de cada mão e pé do BVH, no referencial de repouso (eixos do mundo do jogo, pose zero do arquivo)
MAO_BVH = {"L": (np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, -1.0])),      # dedos para fora, palma para baixo
           "R": (np.array([-1.0, 0.0, 0.0]), np.array([0.0, 0.0, -1.0]))}


def retargetar(clip, inicio=None, fim=None, bracos="direcao", nome=None, suavizar_guinada=0.25):
    """Aplica um `bvh.Mocap` ao Daniel. `bracos`: "direcao" (casamento de direção, o padrão) ou "ik" (o punho vai ao ponto
    escalado pelo braço; para cenas em que a mão tem de chegar a um lugar)."""
    mov = movimento_de_mocap(clip, inicio, fim, nome)
    a = int(round((0.1 if inicio is None else inicio) * clip.fps))
    b = clip.frames if fim is None else int(round(fim * clip.fps))
    posicoes, rotacoes, pontas = clip.world_com_pontas()
    posicoes, rotacoes = posicoes[a:b], rotacoes[a:b]
    pontas = {k: v[a:b] for k, v in pontas.items()}
    j = _juntas_mocap(clip, posicoes, pontas)
    total = len(posicoes)

    escala = PERNA_DANIEL / comprimento_perna(mov)
    piso_tornozelo = estimar_piso(mov)[0]
    quadril_mocap = (j["coxa_L"] + j["coxa_R"]) / 2.0
    base = quadril_mocap[0, :2]

    def escalar(ponto):
        saida = np.empty_like(ponto)
        saida[..., :2] = (ponto[..., :2] - base) * escala
        saida[..., 2] = ALTURA_TORNOZELO + escala * (ponto[..., 2] - piso_tornozelo)
        return saida

    # guinada do corpo: direção da pelve, suavizada
    direita = (j["coxa_R"] - j["coxa_L"])[:, :2]
    frente = np.stack([-direita[:, 1], direita[:, 0]], axis=1)
    frente = gaussiano(frente / np.linalg.norm(frente, axis=1, keepdims=True), suavizar_guinada, clip.fps)
    guinada = np.unwrap(np.arctan2(frente[:, 1], frente[:, 0]) - math.pi / 2)

    quadril_dan = escalar(quadril_mocap)
    raiz = np.zeros((total, 4))
    raiz[:, :2] = quadril_dan[:, :2]
    raiz[:, 3] = guinada
    locais = np.zeros((total, len(S.BONE_ORDER), 4))
    deslocamento = np.zeros((total, 3))
    olhar_pos = np.zeros((total, 3))
    olhar_rot = mov.cabeca_rot.copy()
    memoria_dobradica = {nome: None for nome in ("Thigh.L", "Thigh.R", "UpperArm.L", "UpperArm.R")}
    braco_mocap = float(np.mean([np.linalg.norm(j[f"cotovelo_{lado}"] - j[f"ombro_{lado}"], axis=1).mean()
                                 + np.linalg.norm(j[f"punho_{lado}"] - j[f"cotovelo_{lado}"], axis=1).mean() for lado in "LR"]))
    escala_braco = BRACO_DANIEL / braco_mocap
    rest_hinge = {nome: np.array(S.HINGE_REST[nome]) for nome in S.HINGE_REST}
    rest_mao = {lado: np.array(S.rest_basis(lado)) for lado in "LR"}

    for k in range(total):
        giro = rotacao_z(-guinada[k])                         # mundo -> corpo

        def direcao(de, para):
            return giro @ (j[para][k] - j[de][k])

        world = {}                                            # osso -> W (3x3) no corpo
        local = {}
        maos_alvo = {}

        def atribuir(nome, w):
            pai = PAI[INDICE_OSSO[nome]]
            w_pai = world[S.BONE_ORDER[pai]] if pai >= 0 else np.eye(3)
            world[nome] = w
            local[nome] = w_pai.T @ w

        # --- pelve: linha dos quadris e coluna
        direita_corpo = unitario(giro @ (j["coxa_R"][k] - j["coxa_L"][k]))
        coluna = unitario(giro @ (j["peito"][k] - j["raiz"][k]))
        frente_corpo = unitario(np.cross(coluna, direita_corpo))
        cima = np.cross(direita_corpo, frente_corpo)
        atribuir("Hips", np.stack([direita_corpo, frente_corpo, cima], axis=1))

        # --- coluna: três segmentos, torção repartida entre a pelve e a linha dos ombros
        direita_ombros = unitario(giro @ (j["ombro_R"][k] - j["ombro_L"][k]))
        segmentos = (("Spine1", "raiz", "lombar"), ("Spine2", "lombar", "peito"), ("Spine3", "peito", "pescoco"))
        for passo, (osso, de, para) in enumerate(segmentos, start=1):
            dica = unitario((1 - passo / 3) * direita_corpo + (passo / 3) * direita_ombros)
            alvo = quadro(direcao(de, para), dica)
            atribuir(osso, alvo @ quadro(REPOUSO[osso], [1.0, 0.0, 0.0]).T)

        # --- pescoço e cabeça: direção do pescoço, eixo direito da cabeça
        direita_cabeca = giro @ olhar_rot[k][:, 0]
        atribuir("Neck", quadro(direcao("pescoco", "cabeca"), direita_cabeca) @ quadro(REPOUSO["Neck"], [1.0, 0.0, 0.0]).T)

        for lado in "LR":
            sinal = 1.0 if lado == "R" else -1.0
            # --- clavícula e braço
            atribuir(f"Clavicle.{lado}", _swing(world, f"Clavicle.{lado}", direcao(f"clavicula_{lado}", f"ombro_{lado}")))
            cima_dir = direcao(f"ombro_{lado}", f"cotovelo_{lado}")
            baixo_dir = direcao(f"cotovelo_{lado}", f"punho_{lado}")
            nome_braco = f"UpperArm.{lado}"
            dobradica = _dobradica(cima_dir, baixo_dir, memoria_dobradica, nome_braco, rest_hinge[nome_braco], world["Clavicle." + lado])
            atribuir(nome_braco, quadro(cima_dir, dobradica) @ quadro(REPOUSO[nome_braco], rest_hinge[nome_braco]).T)
            antebraco = f"Forearm.{lado}"
            atribuir(antebraco, quadro(baixo_dir, dobradica) @ quadro(REPOUSO[antebraco], rest_hinge[nome_braco]).T)
            # mão: quadro completo do mocap; a torção entre antebraço e mão é repartida com o ForearmRoll
            f_rest, p_rest = MAO_BVH[lado]
            f_mundo, p_mundo = giro @ rotacoes[k, clip.index(("Left" if lado == "L" else "Right") + "Hand")] @ f_rest, \
                giro @ rotacoes[k, clip.index(("Left" if lado == "L" else "Right") + "Hand")] @ p_rest
            alvo_mao = quadro(f_mundo, p_mundo) @ rest_mao[lado].T
            maos_alvo[lado] = (alvo_mao, direcao(f"ombro_{lado}", f"punho_{lado}"), cima_dir)
            eixo_ant = REPOUSO[antebraco]
            relativa = world[antebraco].T @ alvo_mao
            torcao = torcao_em_torno(relativa, eixo_ant)
            w_roll = world[antebraco] @ de_quaternion(Quaternion(Vector(eixo_ant), torcao * ROLL_SHARE))
            atribuir(f"ForearmRoll.{lado}", w_roll)
            atribuir(f"Hand.{lado}", alvo_mao)

            # --- perna
            coxa_dir = direcao(f"coxa_{lado}", f"joelho_{lado}")
            canela_dir = direcao(f"joelho_{lado}", f"tornozelo_{lado}")
            nome_coxa = f"Thigh.{lado}"
            dobradica = _dobradica(coxa_dir, canela_dir, memoria_dobradica, nome_coxa, rest_hinge[nome_coxa], world["Hips"])
            atribuir(nome_coxa, quadro(coxa_dir, dobradica) @ quadro(REPOUSO[nome_coxa], rest_hinge[nome_coxa]).T)
            atribuir(f"Shin.{lado}", quadro(canela_dir, dobradica) @ quadro(REPOUSO[f"Shin.{lado}"], rest_hinge[nome_coxa]).T)
            # pé e dedão: direção do segmento, "para cima" do pé do mocap
            prefixo = "Left" if lado == "L" else "Right"
            cima_pe = giro @ rotacoes[k, clip.index(prefixo + "Foot")] @ EIXO_Z
            atribuir(f"Foot.{lado}", quadro(direcao(f"tornozelo_{lado}", f"bola_{lado}"), cima_pe)
                     @ quadro(REPOUSO[f"Foot.{lado}"], EIXO_Z).T)
            atribuir(f"Toe.{lado}", quadro(direcao(f"bola_{lado}", f"ponta_{lado}"), cima_pe)
                     @ quadro(REPOUSO[f"Toe.{lado}"], EIXO_Z).T)

        # ossos que o mocap não descreve ficam em repouso (dedos recebem o preset relaxado depois)
        for i, osso in enumerate(S.BONE_ORDER):
            if osso not in local:
                local[osso] = np.eye(3)
        for i, osso in enumerate(S.BONE_ORDER):
            q = para_quaternion(local[osso])
            locais[k, i] = (q.w, q.x, q.y, q.z)
        for lado in "LR":
            for osso, q in F.finger_rotations(lado, F.RELAXED_CURLS, F.RELAXED_SPREAD).items():
                locais[k, INDICE_OSSO[osso]] = (q.w, q.x, q.y, q.z)

        # altura e posição do quadril: o centro das articulações das coxas vai ao ponto escalado do mocap
        especificacao = PoseSpec(hips_shift=Vector((0.0, 0.0, 0.0)),
                                 rot={osso: Quaternion(tuple(locais[k, i])) for i, osso in enumerate(S.BONE_ORDER)})
        for _passada in range(2):
            solucao = solve(especificacao)
            centro = (solucao.head[INDICE_OSSO["Thigh.L"]] + solucao.head[INDICE_OSSO["Thigh.R"]]) / 2.0
            desejado = Vector((0.0, 0.0, quadril_dan[k, 2]))
            especificacao.hips_shift = especificacao.hips_shift + (desejado - centro)
        if bracos == "ik":
            for lado in "LR":
                alvo_mao, corda, cima_dir = maos_alvo[lado]
                ombro = solucao.head[INDICE_OSSO[f"UpperArm.{lado}"]]
                curva = cima_dir - corda * (cima_dir @ corda) / max(corda @ corda, 1e-9)
                sinal = 1.0 if lado == "R" else -1.0
                polo = Vector(curva / np.linalg.norm(curva)) if np.linalg.norm(curva) > 0.02 else Vector((sinal * 0.35, -0.30, -1.0))
                especificacao.arms[lado] = ArmGoal(ombro + Vector(corda * escala_braco), para_quaternion(alvo_mao), polo, 1.0)
            solucao = solve(especificacao)
            for lado in "LR":
                for osso in (f"UpperArm.{lado}", f"Forearm.{lado}", f"ForearmRoll.{lado}", f"Hand.{lado}"):
                    q = solucao.local[INDICE_OSSO[osso]]
                    locais[k, INDICE_OSSO[osso]] = (q.w, q.x, q.y, q.z)
        deslocamento[k] = tuple(especificacao.hips_shift)
        raiz[k, 2] = 0.0
        olho = solucao.head[INDICE_OSSO["Neck"]] + solucao.world[INDICE_OSSO["Neck"]] @ S.EYE_FROM_C7
        olhar_pos[k] = np.array([raiz[k, 0], raiz[k, 1], 0.0]) + np.array(Matrix.Rotation(guinada[k], 3, "Z") @ olho)

    return Retarget(nome or clip.name, clip.fps, escala, raiz, locais, deslocamento, olhar_pos, olhar_rot, origem=mov)


def _swing(world, nome, direcao_corpo):
    """W do osso `nome` que leva a sua direção de repouso à direção pedida, sem torção relativa ao pai."""
    pai = S.BONE_ORDER[PAI[INDICE_OSSO[nome]]]
    w_pai = world[pai]
    local = arco(REPOUSO[nome], w_pai.T @ direcao_corpo)
    return w_pai @ local


def _dobradica(cima, baixo, memoria, nome, repouso_dobradica, w_pai):
    """Eixo da dobradiça (normal do plano do membro) no corpo, como `solver._chain_frames`: corda x curvatura. Em
    membro esticado, vale o do quadro anterior."""
    corda = cima + baixo
    curvatura = cima - corda * (cima @ corda) / (corda @ corda)
    if np.linalg.norm(curvatura) > 0.02 * np.linalg.norm(cima):
        eixo = unitario(np.cross(corda, curvatura))
        memoria[nome] = eixo
        return eixo
    if memoria[nome] is not None:
        return memoria[nome]
    memoria[nome] = w_pai @ repouso_dobradica
    return memoria[nome]
