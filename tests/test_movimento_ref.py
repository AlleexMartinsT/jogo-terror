"""Testes da infraestrutura de comparação de movimento (tools/movimento_ref): BVH, métricas, gravador, figuras.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_movimento_ref.py            # tudo (o gravador monta um palco: ~10 s)
    python tests/test_movimento_ref.py --puro                              # só o que não precisa de bpy

Três grupos:
    puro       BVH conhecido, reamostragem, métricas em marcha sintética de números conhecidos, jerk mínimo, velocidade
               angular, tabela, figuras
    real       os clipes da CMU (se estiverem em cache ou baixáveis): 07_01 anda a 1,36 m/s com ~110 passos/min e ~0,75 m
               de passo; 09_01 corre com cadência de corrida e fase de voo
    gravador   o `Game` sem janela (palco mínimo): roteiro, taxa, ossos pela armadura x pelo solver, determinismo, disco
"""
import math
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import numpy as np  # noqa: E402

from tools.movimento_ref import bvh, cmu, graficos, metricas  # noqa: E402
from tools.movimento_ref import movimento as mv  # noqa: E402

SAIDA = os.path.join(ROOT, "out", "f4_1", "testes")


def aproximadamente(valor, esperado, tolerancia, nome):
    assert abs(valor - esperado) <= tolerancia, f"{nome}: {valor:.4f}, esperado {esperado:.4f} +- {tolerancia}"


# --------------------------------------------------------------------------
# BVH conhecido
# --------------------------------------------------------------------------
BVH_PEQUENO = """HIERARCHY
ROOT Raiz
{
\tOFFSET 0 0 0
\tCHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation
\tJOINT Filho
\t{
\t\tOFFSET 0 1 0
\t\tCHANNELS 3 Zrotation Yrotation Xrotation
\t\tEnd Site
\t\t{
\t\t\tOFFSET 0 0 1
\t\t}
\t}
}
MOTION
Frames: 3
Frame Time: 0.1
0 0 0 0 0 0 0 0 0
1 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 90
"""


def teste_bvh_conhecido():
    clip = bvh.parse(BVH_PEQUENO, "pequeno")
    assert clip.joints == ["Raiz", "Filho"] and clip.parent == [-1, 0]
    assert clip.frames == 3 and abs(clip.fps - 10.0) < 1e-9
    posicoes, rotacoes, pontas = clip.world_com_pontas(face_forward=False)
    u = bvh.CMU_UNIT_M
    # quadro 0: tudo em repouso. O filho fica a 1 unidade acima (eixo Y do arquivo = Z do mundo)
    assert np.allclose(posicoes[0, 1], [0, 0, 1 * u]), posicoes[0, 1]
    # a ponta (End Site em +Z do arquivo = -Y do mundo) fica 1 unidade atrás do filho
    assert np.allclose(pontas["Filho"][0], [0, -1 * u, 1 * u]), pontas["Filho"][0]
    # quadro 1: a raiz anda 1 unidade em X do arquivo
    assert np.allclose(posicoes[1, 0], [1 * u, 0, 0])
    # quadro 2: o filho gira 90 graus em torno de X do arquivo; o End Site (0,0,1) vira (0,-1,0) e cai na origem
    assert np.allclose(pontas["Filho"][2], [0, 0, 0], atol=1e-9), pontas["Filho"][2]
    assert np.allclose(np.linalg.det(rotacoes[2, 1]), 1.0)
    # a norma da ponta ao filho não muda com a rotação
    assert abs(np.linalg.norm(pontas["Filho"][2] - posicoes[2, 1]) - u) < 1e-9


def teste_movimento_reamostrar():
    t = np.arange(0, 1.0, 1 / 120)
    pos = np.zeros((len(t), len(mv.JUNTAS), 3))
    pos[:, mv.INDICE["quadril"], 1] = 2.0 * t                       # 2 m/s
    mov = mv.Movimento("linha", "mocap", 120.0, pos, piso=0.0)
    lento = mov.reamostrar(30.0)
    assert lento.fps == 30.0 and abs(lento.quadros - 30) <= 1
    deslocamento = np.diff(lento.j("quadril")[:, 1]) * 30.0
    assert np.allclose(deslocamento, 2.0, atol=1e-9)
    recorte = mov.trecho(0.25, 0.5)
    assert abs(recorte.duracao - 0.25) < 1e-9


# --------------------------------------------------------------------------
# Marcha sintética de números conhecidos
# --------------------------------------------------------------------------
def marcha_sintetica(passo=0.70, cadencia=110.0, apoio=0.62, segundos=8.0, fps=120.0, bob=0.02, balanco=0.015, deslize=0.0):
    """Andador de dois pés com tudo conhecido: avança `passo` m a cada passo, `cadencia` passos/min, `apoio` do ciclo
    com o pé parado no chão. O pé de apoio recua `deslize` m em relação ao chão durante o apoio (0: fixo)."""
    t = np.arange(0.0, segundos, 1.0 / fps)
    ritmo = cadencia / 60.0                          # passos/s
    velocidade = passo * ritmo
    ciclo = 2.0 / ritmo                              # s por passada
    pos = np.zeros((len(t), len(mv.JUNTAS), 3))
    quadril_z = 0.95
    quadril = np.stack([balanco * np.sin(2 * np.pi * t / ciclo + 0.7),
                        velocidade * t,
                        quadril_z + (bob / 2.0) * np.sin(2 * np.pi * ritmo * t + 1.0)], axis=1)
    pos[:, mv.INDICE["quadril"]] = quadril
    passada = 2.0 * passo
    for lado, fase0 in (("e", 0.0), ("d", 0.5)):
        fase = ((t / ciclo + fase0) % 1.0)
        indice_ciclo = np.floor(t / ciclo + fase0)
        # posição do pé no chão: no apoio fica em y0 (fixo); no balanço vai de y0 a y0 + passada (suave)
        y_apoio = (indice_ciclo * passada) - passada * fase0 + 0.0
        em_apoio = fase < apoio
        balanco_frac = np.clip((fase - apoio) / (1.0 - apoio), 0.0, 1.0)
        suave = balanco_frac * balanco_frac * (3 - 2 * balanco_frac)
        y_pe = np.where(em_apoio, y_apoio - deslize * (fase / apoio), y_apoio - deslize + (passada + deslize) * suave)
        altura = np.where(em_apoio, 0.0, 0.10 * np.sin(np.pi * balanco_frac) ** 0.5)     # sai e pousa com velocidade vertical
        x_pe = (-0.09 if lado == "e" else 0.09)
        pos[:, mv.INDICE[f"tornozelo_{lado}"]] = np.stack([np.full_like(t, x_pe), y_pe, 0.085 + altura], axis=1)
        pos[:, mv.INDICE[f"bola_{lado}"]] = pos[:, mv.INDICE[f"tornozelo_{lado}"]] + np.array([0.0, 0.11, -0.045])
        pos[:, mv.INDICE[f"ponta_{lado}"]] = pos[:, mv.INDICE[f"tornozelo_{lado}"]] + np.array([0.0, 0.17, -0.050])
        pos[:, mv.INDICE[f"coxa_{lado}"]] = quadril + np.array([x_pe, 0.0, -0.05])
        pos[:, mv.INDICE[f"joelho_{lado}"]] = (pos[:, mv.INDICE[f"coxa_{lado}"]] + pos[:, mv.INDICE[f"tornozelo_{lado}"]]) / 2.0
        pos[:, mv.INDICE[f"ombro_{lado}"]] = quadril + np.array([2 * x_pe, 0.0, 0.47])
        pos[:, mv.INDICE[f"cotovelo_{lado}"]] = pos[:, mv.INDICE[f"ombro_{lado}"]] + np.array([0.0, 0.0, -0.30])
        pos[:, mv.INDICE[f"punho_{lado}"]] = pos[:, mv.INDICE[f"cotovelo_{lado}"]] + np.array([0.0, 0.0, -0.26])
    pos[:, mv.INDICE["c7"]] = quadril + np.array([0.0, 0.0, 0.52])
    pos[:, mv.INDICE["cabeca"]] = quadril + np.array([0.0, 0.0, 0.64])
    pos[:, mv.INDICE["olho"]] = quadril + np.array([0.0, 0.08, 0.70])
    return mv.Movimento("sintetica", "mocap", fps, pos, piso=0.0), dict(velocidade=velocidade, ritmo=ritmo, passada=passada)


def teste_marcha_sintetica():
    mov, verdade = marcha_sintetica()
    r = metricas.medir_marcha(mov)
    aproximadamente(r.v["velocidade"], verdade["velocidade"], 0.03, "velocidade")
    aproximadamente(r.v["cadencia"], 110.0, 1.0, "cadência")
    aproximadamente(r.v["passada"], 1.40, 0.03, "passada")
    aproximadamente(r.v["passo"], 0.70, 0.03, "passo")
    aproximadamente(r.v["apoio_pct"], 62.0, 3.5, "apoio")
    assert r.v["deslize_apoio"] < 0.01, r.v["deslize_apoio"]
    aproximadamente(r.v["cabeca_osc_vert"], 0.02, 0.003, "oscilação vertical da cabeça")
    aproximadamente(r.v["cabeca_osc_lat"], 0.03, 0.006, "oscilação lateral da cabeça")
    aproximadamente(r.v["quadril_altura"], 0.95, 0.02, "altura do quadril")
    assert r.v["duplo_apoio_passo_pct"] > 8.0, "apoio de 62% deve dar duplo apoio de ~12% por passo"
    assert r.curvas["joelho"].n >= 4 and r.curvas["joelho"].media.shape == (101,)


def teste_deslize_do_pe():
    """O pé que recua 12 cm no chão durante o apoio tem de aparecer como deslize; o fixo, não."""
    fixo, _ = marcha_sintetica(deslize=0.0)
    escorrega, _ = marcha_sintetica(deslize=0.12)
    d0 = metricas.medir_marcha(fixo).v["deslize_apoio"]
    d1 = metricas.medir_marcha(escorrega).v["deslize_apoio"]
    assert d0 < 0.01, d0
    assert 0.06 < d1 < 0.14, d1


def teste_froude_escolhe_o_metodo():
    mov, _ = marcha_sintetica(passo=0.70, cadencia=110.0)
    assert metricas.eventos_marcha(mov, "auto").toque["e"].size == metricas.eventos_marcha(mov, "zeni").toque["e"].size


def teste_angulos_de_postura_conhecida():
    """Postura estática com coxa 30 graus à frente e canela 30 graus atrás: joelho 60, quadril 30."""
    mov, _ = marcha_sintetica(segundos=1.0)
    n = mov.quadros
    pos = mov.pos.copy()
    quadril = np.array([0.0, 0.0, 1.0])
    pos[:, mv.INDICE["quadril"]] = quadril
    for lado, x in (("e", -0.09), ("d", 0.09)):
        coxa = quadril + np.array([x, 0.0, -0.05])
        a = math.radians(30)
        joelho = coxa + 0.4 * np.array([0.0, math.sin(a), -math.cos(a)])
        tornozelo = joelho + 0.4 * np.array([0.0, -math.sin(a), -math.cos(a)])
        pos[:, mv.INDICE[f"coxa_{lado}"]] = coxa
        pos[:, mv.INDICE[f"joelho_{lado}"]] = joelho
        pos[:, mv.INDICE[f"tornozelo_{lado}"]] = tornozelo
        pos[:, mv.INDICE[f"bola_{lado}"]] = tornozelo + np.array([0.0, 0.11, -0.045])
        pos[:, mv.INDICE[f"ponta_{lado}"]] = tornozelo + np.array([0.0, 0.17, -0.050])
        # cotovelo a 90 graus: braço para baixo, antebraço para a frente
        ombro = quadril + np.array([2 * x, 0.0, 0.47])
        pos[:, mv.INDICE[f"ombro_{lado}"]] = ombro
        pos[:, mv.INDICE[f"cotovelo_{lado}"]] = ombro + np.array([0.0, 0.0, -0.30])
        pos[:, mv.INDICE[f"punho_{lado}"]] = ombro + np.array([0.0, 0.26, -0.30])
    pos[:, mv.INDICE["c7"]] = quadril + np.array([0.0, 0.0, 0.52])
    estatico = mv.Movimento("postura", "mocap", mov.fps, pos, piso=0.0)
    a = metricas.angulos(estatico)
    for lado in "ed":
        aproximadamente(np.median(a[f"joelho_{lado}"]), 60.0, 0.5, "joelho")
        aproximadamente(np.median(a[f"quadril_{lado}"]), 30.0, 0.5, "quadril")
        aproximadamente(np.median(a[f"cotovelo_{lado}"]), 90.0, 0.5, "cotovelo")
        aproximadamente(np.median(a[f"ombro_{lado}"]), 0.0, 0.5, "ombro")
    aproximadamente(np.median(a["tronco_incl"]), 0.0, 0.5, "tronco")


def teste_sinal_da_dorsiflexao():
    """Joelho à frente do tornozelo com o pé plano é dorsiflexão (+); o mesmo pé com a canela vertical vale 0."""
    mov, _ = marcha_sintetica(segundos=1.0)
    pos = mov.pos.copy()
    n = mov.quadros
    for lado, x in (("e", -0.09), ("d", 0.09)):
        tornozelo = np.array([x, 0.0, 0.085])
        inclinacao = np.where(np.arange(n) < n // 2, 0.0, math.radians(10))          # joelho 10 graus à frente
        joelho = tornozelo + 0.4 * np.stack([np.zeros(n), np.sin(inclinacao), np.cos(inclinacao)], axis=1)
        pos[:, mv.INDICE[f"tornozelo_{lado}"]] = tornozelo
        pos[:, mv.INDICE[f"joelho_{lado}"]] = joelho
        pos[:, mv.INDICE[f"coxa_{lado}"]] = joelho + np.array([0.0, 0.0, 0.4])
        pos[:, mv.INDICE[f"bola_{lado}"]] = tornozelo + np.array([0.0, 0.11, -0.045])
        pos[:, mv.INDICE[f"ponta_{lado}"]] = tornozelo + np.array([0.0, 0.17, -0.050])
    a = metricas.angulos(mv.Movimento("dorsi", "mocap", mov.fps, pos, piso=0.0))["tornozelo_e"]
    aproximadamente(a[n // 2 + 5] - a[5], 10.0, 0.6, "dorsiflexão com o joelho à frente")


def teste_rotacao_da_pelve():
    """A pelve que oscila +-4 graus a 1 Hz, sobre uma frente que anda reto, mede 8 graus pico a pico."""
    mov, _ = marcha_sintetica(segundos=6.0)
    pos = mov.pos.copy()
    t = mov.t
    giro = np.radians(4.0) * np.sin(2 * np.pi * 1.0 * t)
    quadril = pos[:, mv.INDICE["quadril"]]
    for lado, x in (("e", -0.09), ("d", 0.09)):
        pos[:, mv.INDICE[f"coxa_{lado}"], 0] = quadril[:, 0] + x * np.cos(giro)
        pos[:, mv.INDICE[f"coxa_{lado}"], 1] = quadril[:, 1] + x * np.sin(giro)
    girada = mv.Movimento("pelve", "mocap", mov.fps, pos, piso=0.0)
    a = metricas.angulos(girada)["pelve_rot"]
    aproximadamente(np.ptp(a[120:-120]), 8.0, 0.8, "pelve pico a pico")


# --------------------------------------------------------------------------
# Mão: jerk mínimo; cabeça: velocidade angular
# --------------------------------------------------------------------------
def teste_jerk_minimo():
    fps = 120.0
    distancia, duracao = 0.40, 0.60
    t = np.arange(0.0, 1.5, 1.0 / fps)
    tau = np.clip((t - 0.4) / duracao, 0, 1)
    x = distancia * (10 * tau ** 3 - 15 * tau ** 4 + 6 * tau ** 5)
    pos = np.zeros((len(t), len(mv.JUNTAS), 3))
    pos[:, mv.INDICE["punho_d"], 0] = x
    mov = mv.Movimento("alcance", "mocap", fps, pos, piso=0.0)
    velocidade = metricas.perfil_mao(mov, "d", suavizar_s=0.0)
    alcances = metricas.detectar_alcances(velocidade, fps)
    assert len(alcances) == 1, alcances
    a, b = alcances[0]
    ajuste = metricas.ajuste_jerk_minimo(velocidade, a, b, fps)
    aproximadamente(ajuste["pico_fracao"], 0.5, 0.05, "pico do jerk mínimo")
    aproximadamente(ajuste["pico_razao"], 1.875, 0.12, "razão pico/média")
    aproximadamente(ajuste["distancia"], distancia, 0.02, "distância")
    aproximadamente(ajuste["duracao"], duracao, 0.05, "duração")
    assert ajuste["r2_jerk_minimo"] > 0.97, ajuste
    # um movimento a velocidade constante NÃO se ajusta ao jerk mínimo
    plano = np.full(72, 0.67)
    assert metricas.ajuste_jerk_minimo(plano, 0, 72, fps)["r2_jerk_minimo"] < 0.3


def teste_velocidade_angular_da_cabeca():
    fps = 60.0
    t = np.arange(0.0, 2.0, 1.0 / fps)
    angulo = np.radians(30.0) * t                                  # 30 graus/s em torno de Z
    c, s = np.cos(angulo), np.sin(angulo)
    giro_z = np.zeros((len(t), 3, 3))
    giro_z[:, 0, 0], giro_z[:, 0, 1], giro_z[:, 1, 0], giro_z[:, 1, 1], giro_z[:, 2, 2] = c, -s, s, c, 1.0
    rot = giro_z @ mv.CAMERA_NIVELADA
    pos = np.zeros((len(t), len(mv.JUNTAS), 3))
    mov = mv.Movimento("giro", "mocap", fps, pos, cabeca_rot=rot, piso=0.0)
    w = metricas.velocidade_angular_cabeca(mov, suavizar_s=0.0)
    aproximadamente(np.median(w["total"]), 30.0, 0.5, "velocidade angular total")
    aproximadamente(np.median(w["guinada"]), 30.0, 0.5, "guinada")
    assert np.median(w["inclinacao"]) < 0.5


# --------------------------------------------------------------------------
# Tabela e figuras
# --------------------------------------------------------------------------
def teste_tabela_e_figuras():
    real, _ = marcha_sintetica(passo=0.75, cadencia=110.0)
    jogo, _ = marcha_sintetica(passo=1.15, cadencia=135.0, apoio=0.5, deslize=0.2)
    mr, mj = metricas.medir_tudo(real), metricas.medir_tudo(jogo)
    linhas = metricas.comparar_metricas(mr.v, mj.v)
    por_chave = {l.chave: l for l in linhas}
    assert por_chave["passo"].ok is False and por_chave["passo"].diferenca > 0.3
    assert por_chave["cadencia"].ok is False
    assert por_chave["quadril_altura"].ok is True
    assert "passo" in metricas.tabela_texto(linhas)
    dispersao = metricas.dispersao_populacao([mr.v, mj.v])
    assert dispersao["cadencia"][2] == 2
    os.makedirs(SAIDA, exist_ok=True)
    for caminho in (graficos.painel_curvas(mr, mj, os.path.join(SAIDA, "curvas.png"), titulo="teste"),
                    graficos.painel_tabela(linhas, os.path.join(SAIDA, "tabela.png"), titulo="teste"),
                    graficos.diagrama_apoios(real, jogo, os.path.join(SAIDA, "apoios.png"), janela=(0, 4)),
                    graficos.curva_unica(mr, mj, "joelho", os.path.join(SAIDA, "joelho.png"))):
        assert os.path.getsize(caminho) > 4000, caminho


# --------------------------------------------------------------------------
# Clipes reais da CMU
# --------------------------------------------------------------------------
def carregar_clipe(clip_id):
    try:
        return mv.movimento_de_mocap(cmu.carregar(clip_id))
    except Exception as erro:       # noqa: BLE001 - sem rede e sem cache, os testes reais saem do caminho
        print(f"  (clipe {clip_id} indisponível: {erro})")
        return None


def teste_clipe_andar_07_01():
    mov = carregar_clipe("07_01")
    if mov is None:
        return "pulado"
    r = metricas.medir_tudo(mov)
    aproximadamente(r.v["velocidade"], 1.36, 0.06, "velocidade de 07_01")
    aproximadamente(r.v["cadencia"], 110.0, 6.0, "cadência de 07_01")
    aproximadamente(r.v["passo"], 0.75, 0.05, "passo de 07_01")
    aproximadamente(r.v["passada"], 1.50, 0.08, "passada de 07_01")
    assert 55.0 < r.v["apoio_pct"] < 70.0, r.v["apoio_pct"]
    assert r.v["voo_pct"] < 1.0
    assert 0.025 < r.v["cabeca_osc_vert"] < 0.07, r.v["cabeca_osc_vert"]
    assert r.v["deslize_apoio"] < 0.05, r.v["deslize_apoio"]
    assert 55.0 < r.v["joelho_balanco_max"] < 80.0, r.v["joelho_balanco_max"]


def teste_clipe_correr_09_01():
    mov = carregar_clipe("09_01")
    if mov is None:
        return "pulado"
    r = metricas.medir_tudo(mov)
    aproximadamente(r.v["velocidade"], 3.54, 0.25, "velocidade de 09_01")
    assert 150.0 < r.v["cadencia"] < 180.0, r.v["cadencia"]
    assert r.v["voo_pct"] > 15.0, r.v["voo_pct"]
    assert r.v["apoio_pct"] < 45.0, r.v["apoio_pct"]
    assert r.v["joelho_balanco_max"] > 85.0


def teste_andar_devagar_mais_lento_que_andar():
    lento, normal = carregar_clipe("07_04"), carregar_clipe("07_01")
    if lento is None or normal is None:
        return "pulado"
    a, b = metricas.medir_marcha(lento).v, metricas.medir_marcha(normal).v
    assert a["velocidade"] < b["velocidade"] and a["cadencia"] < b["cadencia"] and a["passo"] < b["passo"]


# --------------------------------------------------------------------------
# Gravador (precisa de bpy)
# --------------------------------------------------------------------------
def teste_roteiro_de_texto():
    from tools.movimento_ref import grava
    passos = grava.roteiro_de_texto("andar 5; parar 1; virar -90 1.5; correr 3; agachar 2; olhar 30 1; virar 90 1 parado")
    assert [p.rotulo for p in passos] == ["andar", "parar", "virar", "correr", "agachar", "olhar", "virar"]
    assert abs(grava.duracao_total(passos) - 14.5) < 1e-9
    assert passos[2].giro == -60.0 and passos[2].mover == 1.0 and passos[6].mover == 0.0
    try:
        grava.roteiro_de_texto("voar 3")
    except ValueError:
        pass
    else:
        raise AssertionError("verbo desconhecido deveria falhar")


class Cena:
    """Monta o palco uma vez só para todos os testes do gravador."""
    jogo = None

    @classmethod
    def obter(cls):
        if cls.jogo is None:
            from tools.movimento_ref import grava
            cls.jogo = grava.montar_jogo(palco=True)
        return cls.jogo


def teste_gravador_taxa_e_conteudo():
    from tools.movimento_ref import grava
    jogo = Cena.obter()
    rec = grava.gravar(jogo, grava.roteiro_de_texto("andar 3; parar 1"), nome="t1", ossos="fk", prefacio=0.2)
    assert rec.quadros == 240 and abs(rec.fps - 60.0) < 1e-9
    assert np.allclose(np.diff(rec.t), 1 / 60)
    assert rec.cabecas.shape == (240, len(grava.OSSOS), 3) and rec.pontas.shape == rec.cabecas.shape
    assert rec.camera_pos.shape == (240, 3) and rec.camera_rot.shape == (240, 3, 3)
    assert rec.portas.shape == (240, len(grava.PORTAS)) and len(grava.PORTAS) == 13
    assert rec.dedos.shape == (240, 2, 5) and rec.palma.shape == (240, 2, 3)
    from sem_alvorada import conventions as C
    assert rec.jogador["velocidade"][120] > 0.8 * C.SPEED_WALK and rec.jogador["velocidade"][-1] < 0.3
    ruido = [e for e in rec.eventos if e[1] == "ruido"]
    assert len(ruido) >= 3 and all(e[3] in ("walk", "run", "crouch_walk") for e in ruido), ruido[:4]
    assert [p[2] for p in rec.passos] == ["andar", "parar"]
    # o jogador anda para +Y (guinada 0) na velocidade de andar do jogo: 3 s vão a ~3 x SPEED_WALK
    deslocamento = rec.jogador["y"][-1] - rec.jogador["y"][0]
    assert 2.3 * C.SPEED_WALK < deslocamento < 3.1 * C.SPEED_WALK, deslocamento
    assert not rec.meta["avisos"], rec.meta["avisos"]
    # 30 Hz: metade dos quadros, mesmo relógio
    rec30 = grava.gravar(jogo, grava.roteiro_de_texto("parar 1"), ossos="nenhum", cada=2)
    assert rec30.quadros == 30 and abs(rec30.fps - 30.0) < 1e-9 and not rec30.tem_ossos


def teste_ossos_armadura_igual_solver():
    """Os ossos lidos da armadura avaliada têm de coincidir com o que o solver calculou (FK): a mesma pose, dois caminhos."""
    from tools.movimento_ref import grava
    import bpy
    jogo = Cena.obter()
    leitor_armadura = grava.LeitorOssos(jogo.body, "armadura")
    leitor_fk = grava.LeitorOssos(jogo.body, "fk")
    maior = 0.0
    from sem_alvorada.engine.inputstate import InputState
    entrada = InputState(move_y=1.0, run=True)
    for quadro in range(90):
        if quadro == 60:
            entrada = InputState(move_y=0.0, crouch=True, look_dy=-0.01)
        jogo.tick(1 / 60, entrada)
        if quadro % 10 == 5:
            bpy.context.view_layer.update()
            a, b = leitor_armadura.ler(), leitor_fk.ler()
            for x, y in zip(a[:3], b[:3]):
                maior = max(maior, float(np.abs(x - y).max()))
            assert np.abs(a[3] - b[3]).max() < 1e-6          # os quaternions escritos são os mesmos
    assert maior < 2e-3, f"armadura x solver divergem em até {maior * 1000:.2f} mm"
    return f"diferença máxima {maior * 1000:.3f} mm"


def teste_gravacao_deterministica_e_disco():
    from tools.movimento_ref import grava
    roteiro = "andar 2; virar 45 1; parar 0.5"
    jogo = Cena.obter()
    jogo.place_player(0.0, 0.0, 0.0, 0.0)
    jogo.body.reset()
    for _ in range(30):
        from sem_alvorada.engine.inputstate import InputState
        jogo.tick(1 / 60, InputState())
    a = grava.gravar(jogo, grava.roteiro_de_texto(roteiro), nome="a", ossos="fk")
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "a.npz")
        a.salvar(caminho)
        b = grava.Gravacao.carregar(caminho)
    assert b.nome == "a" and b.quadros == a.quadros
    assert np.allclose(a.cabecas, b.cabecas) and np.allclose(a.camera_rot, b.camera_rot)
    assert b.eventos == [tuple(e) for e in a.eventos] or len(b.eventos) == len(a.eventos)
    assert np.allclose(a.jogador["guinada"], b.jogador["guinada"])
    # virar 45 graus em 1 s: a guinada final difere da inicial em ~45 graus (+ esquerda)
    giro = math.degrees(a.jogador["guinada"][-1] - a.jogador["guinada"][0])
    aproximadamente(giro, 45.0, 3.0, "giro do roteiro")
    trecho = a.trecho(0.5, 2.0)
    assert abs(trecho.t[0]) < 1e-9 and abs(trecho.quadros - 90) <= 1


def teste_movimento_do_jogo():
    """A gravação vira `Movimento` com os mesmos nomes de juntas do mocap e a marcha do jogo sai medida."""
    from tools.movimento_ref import grava
    jogo = Cena.obter()
    jogo.place_player(0.0, 0.0, 0.0, 0.0)
    rec = grava.gravar(jogo, grava.roteiro_de_texto("andar 5"), nome="m", ossos="fk", prefacio=0.3)
    mov = rec.movimento()
    assert mov.pos.shape[1:] == (len(mv.JUNTAS), 3) and mov.fonte == "jogo" and mov.camera is not None
    # o olho calculado do esqueleto coincide com a câmera do jogador, a menos do balanço de cabeça do corpo
    folga = np.linalg.norm(mov.j("olho") - mov.camera, axis=1)
    assert folga.max() < 0.12, f"olho do corpo a {folga.max():.3f} m da câmera"
    from sem_alvorada import conventions as C
    r = metricas.medir_marcha(mov.trecho(1.0, 5.0), "zeni")
    aproximadamente(r.v["velocidade"], C.SPEED_WALK, 0.12 * C.SPEED_WALK, "velocidade do jogo")
    assert np.isfinite(r.v["cadencia"]) and np.isfinite(r.v["passo"])


GRUPOS = (("puro", [teste_bvh_conhecido, teste_movimento_reamostrar, teste_marcha_sintetica, teste_deslize_do_pe,
                    teste_froude_escolhe_o_metodo, teste_angulos_de_postura_conhecida, teste_sinal_da_dorsiflexao, teste_rotacao_da_pelve,
                    teste_jerk_minimo, teste_velocidade_angular_da_cabeca, teste_tabela_e_figuras]),
          ("real", [teste_clipe_andar_07_01, teste_clipe_correr_09_01, teste_andar_devagar_mais_lento_que_andar]),
          ("gravador", [teste_roteiro_de_texto, teste_gravador_taxa_e_conteudo, teste_ossos_armadura_igual_solver,
                        teste_gravacao_deterministica_e_disco, teste_movimento_do_jogo]))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    grupos = [g for g in GRUPOS if not ("--puro" in argv and g[0] != "puro" and g[0] != "real")]
    falhas = 0
    for nome_grupo, testes in grupos:
        for teste in testes:
            inicio = time.time()
            try:
                nota = teste()
                print(f"  ok   {teste.__name__:52s} {time.time() - inicio:5.1f}s" + (f"  ({nota})" if nota else ""))
            except Exception as erro:       # noqa: BLE001
                falhas += 1
                print(f"  FALHOU {teste.__name__}: {type(erro).__name__}: {erro}")
    print("test_movimento_ref OK" if not falhas else f"test_movimento_ref: {falhas} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
