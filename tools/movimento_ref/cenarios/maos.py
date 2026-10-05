"""Cenários das mãos, dos itens e da lanterna: o jogo contra o mocap real (CMU) e contra as leis da física.

    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.maos --lista
    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.maos_tabela medir out/f4_3/jogo_depois.json   # mede o jogo
    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.comparar pegar_chave --saida out/movimento/pegar_chave
    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.maos --gerar-referencia          # remede o mocap

Cenários (registrados na classe base `Cenario` de `base.py`): pegar_chao, alcancar, lanterna_olhar, pegar_chave, pilhas, nota.

Fonte de cada número (o relatório separa as três):
  MEDIDO   dos clipes reais da CMU, com as funções de `metricas.py` (perfil_mao, detectar_alcances, ajuste_jerk_minimo,
           velocidade_angular_cabeca); os valores ficam em `assets/referencia/maos_ref.json` (gerado por --gerar-referencia);
  DERIVADO de uma lei física (pêndulo composto, viga em balanço, filamento), conferida por integração numérica;
  ESTIMADO valor de engenharia lembrado de memória, sempre marcado, com a faixa.

O jogo é gravado num palco mínimo (corpo real, mesa, itens; sem a casa): `montar_jogo_maos`.
"""
import argparse
import json
import math
import os
import sys
from dataclasses import replace

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import numpy as np  # noqa: E402

from tools.movimento_ref import cmu, grava, metricas  # noqa: E402
from tools.movimento_ref.cenarios import registrar  # noqa: E402
from tools.movimento_ref.cenarios.base import Alinhamento, Cenario, Preparado, Real  # noqa: E402
from tools.movimento_ref.movimento import movimento_de_mocap  # noqa: E402

REFERENCIA = os.path.join(ROOT, "assets", "referencia", "maos_ref.json")
BRACO_DANIEL = 0.60                        # ombro-punho do Daniel (m): 0,335 + 0,265
VEL_MINIMA = 0.35                          # pico mínimo (m/s) de um alcance para o detector
G = 9.81

# Clipes de cada medida (ids da CMU). Os dois primeiros conjuntos são de gestos isolados de uma mão ou das duas.
CLIPES_LEI = ["15_06", "15_07", "22_22", "22_23", "23_22", "23_23", "26_09", "69_68", "69_69", "69_70", "69_71", "69_72", "69_73",
              "69_74", "69_75", "111_17", "111_18", "115_01", "79_36", "79_38", "79_40", "80_25", "80_40", "13_09", "14_37",
              "62_19", "144_22", "144_23", "144_24", "144_25"]
CLIPES_FORMA = ["22_22", "22_23", "23_22", "23_23", "26_09", "115_01", "111_17", "111_18", "79_36", "79_38", "79_40", "80_25",
                "80_40", "62_19", "69_70", "69_72", "69_73"]
CLIPES_OLHAR = ["69_68", "69_69", "69_70", "69_71", "69_72", "69_73", "69_74", "69_75", "115_01", "111_17", "111_18", "26_09",
                "22_22", "79_38", "79_40", "80_40", "13_09", "62_19"]


# --------------------------------------------------------------------------
# Medidas no formato comum (`Movimento`): as mesmas funções para o mocap e para o jogo
# --------------------------------------------------------------------------
def relativo_ao_quadril(mov):
    """Movimento com todas as juntas relativas ao quadril: tira a caminhada e o balanço do corpo todo da mão."""
    return replace(mov, pos=mov.pos - mov.pos[:, 0:1, :])


def comprimento_braco(mov, lado):
    """Ombro-punho (m), da geometria do próprio `Movimento` (mediana: o braço dobra e estica, o osso não)."""
    cotovelo, ombro, punho = (mov.j(f"{n}_{lado}") for n in ("cotovelo", "ombro", "punho"))
    return float(np.median(np.linalg.norm(cotovelo - ombro, axis=1) + np.linalg.norm(punho - cotovelo, axis=1)))


def correlacao_jerk_minimo(velocidade):
    tau = np.linspace(0.0, 1.0, len(velocidade))
    modelo = 30.0 * tau ** 2 * (1.0 - tau) ** 2
    return float(np.corrcoef(velocidade, modelo)[0, 1]) if len(velocidade) > 4 else float("nan")


def alcances_da_mao(mov, lado, vel_minima=VEL_MINIMA, a_partir_de=0.0):
    """Todos os alcances da mão `lado` ("e"/"d") do `Movimento` `mov` (já relativo ao quadril, se for o caso).
    Devolve uma lista de dicts: início/fim (s), duração a 6% do pico (`t6`), distância reta e percorrida, retidão,
    correlação com o jerk mínimo e o ajuste de `metricas.ajuste_jerk_minimo` (duração nominal, pico em fração, razão
    pico/média, R2)."""
    velocidade = metricas.perfil_mao(mov, lado)
    punho = mov.j(f"punho_{lado}")
    saida = []
    for a, b in metricas.detectar_alcances(velocidade, mov.fps, vel_minima=vel_minima, fracao=0.06):
        if a / mov.fps < a_partir_de or b - a < 4:
            continue
        trecho = velocidade[a:b]
        reta = float(np.linalg.norm(punho[b - 1] - punho[a]))
        caminho = float(trecho.sum() / mov.fps)
        ajuste = metricas.ajuste_jerk_minimo(velocidade, a, b, mov.fps)
        saida.append(dict(inicio=a / mov.fps, fim=b / mov.fps, t6=(b - a) / mov.fps, reta=reta, caminho=caminho,
                          retidao=reta / caminho if caminho > 0 else 0.0, corr=correlacao_jerk_minimo(trecho),
                          pico_fracao=float(np.argmax(trecho) / len(trecho)), pico=float(trecho.max()),
                          ajuste=ajuste, a=a, b=b))
    return saida


def gesto_limpo(r, braco):
    return r["corr"] > 0.9 and r["retidao"] > 0.85 and r["reta"] / braco >= 0.3


# --------------------------------------------------------------------------
# O real: tudo que sai do mocap e vai para assets/referencia/maos_ref.json
# --------------------------------------------------------------------------
def medir_lei_do_alcance():
    """T(6%) = a + b D/L sobre os alcances limpos dos clipes de CLIPES_LEI, e a forma do perfil de velocidade."""
    linhas = []
    for cid in CLIPES_LEI:
        clip = cmu.carregar(cid, inicio=2 / 120.0)
        mov = relativo_ao_quadril(movimento_de_mocap(clip))
        for lado in "ed":
            braco = comprimento_braco(mov, lado)
            for r in alcances_da_mao(mov, lado):
                if gesto_limpo(r, braco):
                    linhas.append((cid, braco, r))
    dl = np.array([r["reta"] / braco for _, braco, r in linhas])
    t6 = np.array([r["t6"] for _, _, r in linhas])
    pico = np.array([r["pico_fracao"] for _, _, r in linhas])
    matriz = np.vstack([np.ones_like(dl), dl]).T
    a, b = np.linalg.lstsq(matriz, t6, rcond=None)[0]
    residuo = t6 - matriz @ np.array([a, b])
    faixas = []
    for lo, hi in ((0.3, 0.6), (0.6, 0.9), (0.9, 1.2), (1.2, 3.0)):
        m = (dl >= lo) & (dl < hi)
        if m.any():
            faixas.append(dict(de=lo, ate=hi, n=int(m.sum()), t6_media=float(t6[m].mean()), t6_desvio=float(t6[m].std()),
                               pico_medio=float(pico[m].mean())))
    return dict(n=len(linhas), clipes=sorted({c for c, _, _ in linhas}), a=float(a), b=float(b), desvio=float(residuo.std()),
                r2=float(1 - (residuo ** 2).sum() / ((t6 - t6.mean()) ** 2).sum()), pico_fracao=[float(pico.mean()), float(pico.std())],
                braco_medio=float(np.mean([braco for _, braco, _ in linhas])), faixas=faixas)


def medir_forma_do_alcance():
    """Forma do perfil de velocidade dos alcances isolados (ajuste de jerk mínimo com R2 > 0,8)."""
    pico, razao, r2, quantos = [], [], [], 0
    for cid in CLIPES_FORMA:
        clip = cmu.carregar(cid, inicio=2 / 120.0)
        mov = relativo_ao_quadril(movimento_de_mocap(clip))
        for lado in "ed":
            braco = comprimento_braco(mov, lado)
            for r in alcances_da_mao(mov, lado):
                aj = r["ajuste"]
                if aj and aj["r2_jerk_minimo"] > 0.8 and r["retidao"] > 0.85 and r["reta"] / braco >= 0.3:
                    pico.append(aj["pico_fracao"]); razao.append(aj["pico_razao"]); r2.append(aj["r2_jerk_minimo"]); quantos += 1
    return dict(n=quantos, pico_fracao=[float(np.mean(pico)), float(np.std(pico))], pico_razao=[float(np.mean(razao)), float(np.std(razao))],
                r2=[float(np.mean(r2)), float(np.std(r2))])


def angulo(a, b):
    a = a / np.linalg.norm(a, axis=-1, keepdims=True)
    b = b / np.linalg.norm(b, axis=-1, keepdims=True)
    return np.degrees(np.arccos(np.clip((a * b).sum(-1), -1.0, 1.0)))


def postura_do_braco(mov, lado="d"):
    """Ângulos do braço por quadro, referidos à gravidade (valem para o mocap e para o jogo): flexão do cotovelo (0 = esticado),
    elevação do braço em relação à vertical, razão punho-ombro / comprimento do braço e altura do punho acima do ombro / L."""
    ombro, cotovelo, punho = (mov.j(f"{n}_{lado}") for n in ("ombro", "cotovelo", "punho"))
    braco, antebraco = cotovelo - ombro, punho - cotovelo
    comprimento = np.linalg.norm(braco, axis=1) + np.linalg.norm(antebraco, axis=1)
    return dict(cotovelo=180.0 - angulo(-braco, antebraco), elevacao=angulo(braco, np.array([0.0, 0.0, -1.0])),
                razao=np.linalg.norm(punho - ombro, axis=1) / comprimento, altura=(punho - ombro)[:, 2] / comprimento)


def medir_lanterna_real():
    """77_05 (olhar em volta com a lanterna na mão direita): postura do braço que a segura e atraso do antebraço em relação
    à cabeça (correlação cruzada das velocidades de guinada e constante de tempo de primeira ordem)."""
    clip = cmu.carregar("77_05", inicio=2 / 120.0)
    mov = movimento_de_mocap(clip)
    t = mov.t
    segurando = (t > 1.5) & (t < 3.0)               # lanterna levantada (a mão sobe a 1 m a partir de 1,3 s)
    postura = postura_do_braco(mov, "d")
    saida = {k: float(np.mean(v[segurando])) for k, v in postura.items()}
    saida["braco"] = comprimento_braco(mov, "d")
    # atraso do antebraço em relação ao olhar: guinada de cada um e velocidade de guinada
    olhar = mov.cabeca_rot @ np.array([0.0, 0.0, -1.0])
    antebraco = mov.j("punho_d") - mov.j("cotovelo_d")

    def guinada(v):
        g = np.degrees(np.unwrap(np.arctan2(-v[:, 0], v[:, 1])))
        return metricas.gaussiano(g[:, None], 0.025, mov.fps)[:, 0]

    mascara = (t > 0.9) & (t < 4.2)
    vh = np.gradient(guinada(olhar), 1 / mov.fps)[mascara]
    va = np.gradient(guinada(antebraco), 1 / mov.fps)[mascara]
    atrasos = np.arange(-30, 31)
    cc = []
    for L in atrasos:
        x, y = (vh[:len(vh) - L], va[L:]) if L >= 0 else (vh[-L:], va[:len(va) + L])
        cc.append(np.corrcoef(x, y)[0, 1])
    k = int(np.argmax(cc))
    taus = np.linspace(0.01, 0.3, 117)
    melhor = None
    for tau in taus:
        alfa = 1 - math.exp(-1 / (mov.fps * tau))
        s, saida_lp = 0.0, np.zeros_like(vh)
        for i, x in enumerate(vh):
            s += alfa * (x - s)
            saida_lp[i] = s
        ganho = float((saida_lp * va).sum() / (saida_lp * saida_lp).sum())
        erro = float(((va - ganho * saida_lp) ** 2).sum())
        if melhor is None or erro < melhor[0]:
            melhor = (erro, tau)
    atraso = np.abs(np.degrees(0) + (guinada(antebraco) - guinada(olhar))[mascara])
    saida.update(atraso_xcorr_ms=float(atrasos[k] * 1000.0 / mov.fps), correlacao=float(cc[k]), tau_ms=float(melhor[1] * 1000.0))
    forte = np.abs(vh) > 100.0
    desvio = (guinada(antebraco) - guinada(olhar))[mascara]
    desvio = desvio - np.median(desvio)
    saida["tau_razao_ms"] = float(1000.0 * np.median(np.abs(desvio[forte]) / np.abs(vh[forte]))) if forte.any() else float("nan")
    w = metricas.velocidade_angular_cabeca(mov)
    saida["cabeca_w_p50"], saida["cabeca_w_p95"] = float(np.percentile(w["total"], 50)), float(np.percentile(w["total"], 95))
    saida["cabeca_w_max"] = float(w["total"].max())
    return saida


def medir_bimanual():
    """Defasagem entre o início dos movimentos das duas mãos em gestos com as duas mãos (115_01: pegar a caixa dobrando
    na cintura; 62_19: abrir uma caixa)."""
    defasagens = []
    for cid in ("115_01", "62_19", "13_09"):
        clip = cmu.carregar(cid, inicio=2 / 120.0)
        mov = relativo_ao_quadril(movimento_de_mocap(clip))
        por_lado = {lado: alcances_da_mao(mov, lado) for lado in "ed"}
        for re in por_lado["e"]:
            vizinhos = [rd for rd in por_lado["d"] if abs(rd["inicio"] - re["inicio"]) < 0.6 and abs(rd["pico"] - re["pico"]) < 0.6 * re["pico"] + 0.5]
            if vizinhos:
                rd = min(vizinhos, key=lambda x: abs(x["inicio"] - re["inicio"]))
                defasagens.append(abs(rd["inicio"] - re["inicio"]))
    return dict(n=len(defasagens), defasagem_mediana=float(np.median(defasagens)) if defasagens else float("nan"),
                defasagem_p75=float(np.percentile(defasagens, 75)) if defasagens else float("nan"))


def medir_olhar_antes_da_mao():
    """Em quantos ms o olhar chega à meio caminho do alvo antes de a mão sair (poucos alcances: indicativo)."""
    saidas = []
    for cid in CLIPES_OLHAR:
        clip = cmu.carregar(cid, inicio=2 / 120.0)
        mov = movimento_de_mocap(clip)
        rel = relativo_ao_quadril(mov)
        olhar = mov.cabeca_rot @ np.array([0.0, 0.0, -1.0])
        olhar = metricas.gaussiano(olhar, 0.05, mov.fps)
        olhar /= np.linalg.norm(olhar, axis=1, keepdims=True)
        for lado in "ed":
            braco = comprimento_braco(mov, lado)
            for r in alcances_da_mao(rel, lado):
                if not gesto_limpo(r, braco) or r["reta"] < 0.30:
                    continue
                alvo = mov.j(f"punho_{lado}")[r["b"] - 1] - mov.j("olho")
                alvo /= np.linalg.norm(alvo, axis=1, keepdims=True)
                erro = angulo(olhar, alvo)
                a0 = max(0, r["a"] - int(1.2 * mov.fps))
                inicio, fim = np.median(erro[a0:a0 + max(3, int(0.1 * mov.fps))]), erro[r["b"] - 1]
                if inicio - fim < 8.0:
                    continue
                meio = fim + 0.5 * (inicio - fim)
                k = np.where(erro[a0:r["b"]] < meio)[0]
                if len(k):
                    saidas.append(r["inicio"] - (a0 + k[0]) / mov.fps)
    return dict(n=len(saidas), adianta_s=float(np.median(saidas)) if saidas else float("nan"),
                fracao_adiantada=float(np.mean(np.array(saidas) > 0)) if saidas else float("nan"))


def gerar_referencia(caminho=REFERENCIA):
    """Remede tudo no mocap e grava o JSON que os testes e as tabelas usam."""
    dados = dict(fonte="CMU Graphics Lab Motion Capture Database (conversão BVH de cgspeed), medido por tools/movimento_ref/cenarios/maos.py",
                 lei_do_alcance=medir_lei_do_alcance(), forma_do_alcance=medir_forma_do_alcance(), lanterna=medir_lanterna_real(),
                 bimanual=medir_bimanual(), olhar=medir_olhar_antes_da_mao())
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=1)
    return dados


def referencia():
    """O JSON de assets/referencia/maos_ref.json (gerado na primeira vez, se não existir)."""
    if not os.path.exists(REFERENCIA):
        return gerar_referencia()
    with open(REFERENCIA, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def tempo_do_alcance(distancia, braco=BRACO_DANIEL):
    """T(6%) em segundos que a lei medida dá para um alcance de `distancia` m com um braço de `braco` m."""
    lei = referencia()["lei_do_alcance"]
    return lei["a"] + lei["b"] * distancia / braco


# --------------------------------------------------------------------------
# O palco do jogo e os gestos gravados
# --------------------------------------------------------------------------
ITENS = {"FLASHLIGHT": "FLASHLIGHT", "KEY": "KEY", "MAP": "MAP", "BATTERY_1": "BATTERY", "NOTE_1": "NOTE"}
MESA = (-0.6, 0.95, 0.6, 1.45, 0.78)             # x0, y0, x1, y1, topo (m)
JOGADOR = (0.0, 0.0, 0.0)


def montar_jogo_maos(item=None, no_chao=False):
    """`Game` sem janela num palco mínimo: corpo, os modelos que as mãos seguram, uma mesa e o `item` (ref de
    `layout.ITEM_SPOTS`, ex. "KEY") sobre ela, ou no chão. O jogador está na origem olhando para +Y, fase "play"."""
    import bpy
    from sem_alvorada import build as build_module
    from sem_alvorada import conventions as C
    from sem_alvorada.body import build as build_body
    from sem_alvorada.buildctx import BuildContext
    from sem_alvorada.engine import builder
    from sem_alvorada.engine.game import Game
    from sem_alvorada.engine.inputstate import InputState
    from sem_alvorada.props import flashlight as props_flashlight

    scene = build_module.fresh_scene()
    ctx = BuildContext(scene, verbose=False)
    ctx.stage = "body"
    build_body(ctx)
    ctx.stage = "props"
    props_flashlight.make_viewmodel(ctx)
    ctx.stage = "engine"
    builder.build(ctx)
    grava._caixa_de_colisao(scene, "COL_piso_palco", -60.0, -60.0, -0.5, 60.0, 60.0, 0.0)
    grava._caixa_de_colisao(scene, "COL_mesa", *MESA[:2], 0.0, *MESA[2:4], MESA[4])
    if item is not None:
        x, y, z = (0.0, 0.85, 0.03) if no_chao else (0.0, 1.10, MESA[4] + 0.03)
        obj = bpy.data.objects.new(C.N_ITEM + item, None)
        scene.collection.objects.link(obj)
        obj.location = (x, y, z)
        nota = item.startswith("NOTE")
        obj[C.P_INTERACT] = "note" if nota else "item"
        obj[C.P_ID] = item
        obj[C.P_ITEM] = C.ITEM_NOTE if nota else item.split("_")[0]
        obj[C.P_ROOM] = "master"
    bpy.context.view_layer.update()
    jogo = Game(scene, audio=False, entity=False, cutscenes=False)
    jogo.skip_intro = True
    entrada = InputState(confirm=True)
    jogo.tick(1 / 60, entrada)
    entrada.clear_edges()
    jogo.place_player(*JOGADOR, 0.0)
    for _ in range(3):
        jogo.tick(1 / 60, InputState())
    return jogo


def mirar(jogo, ponto):
    """Aponta a câmera do jogador para `ponto` (mundo)."""
    px, py, pz = jogo.player.eye_pos
    dx, dy, dz = ponto[0] - px, ponto[1] - py, ponto[2] - pz
    jogo.player.yaw = math.atan2(-dx, dy)
    jogo.player.pitch = math.atan2(dz, math.hypot(dx, dy))


def estado(jogo, lanterna=True, ligada=True, carga=0.78, pilhas=0, chave=False, mapa=False, notas=(), segurar=None):
    s = jogo.state
    s.has_flashlight, s.flashlight_on, s.battery = lanterna, lanterna and ligada, carga
    s.spare_batteries = s.batteries_found = pilhas
    s.has_key, s.has_map = chave, mapa
    s.notes_read |= set(notas)
    if lanterna:
        s.collected.add("FLASHLIGHT")
    jogo.interact.sync_scene()
    if segurar is not None:
        jogo.hands.equip(segurar)


# Gestos gravados: (item no palco, no chão?, preparo do estado, mão que mede, teclas, duração)
GESTOS = {
    "lanterna": dict(item="FLASHLIGHT", lado="d", estado=dict(lanterna=False), tecla="interact", duracao=3.6),
    "pilha": dict(item="BATTERY_1", lado="e", estado=dict(), tecla="interact", duracao=3.4),
    "pilha_chao": dict(item="BATTERY_1", lado="e", estado=dict(), tecla="interact", duracao=3.4, no_chao=True),
    "chave": dict(item="KEY", lado="e", estado=dict(), tecla="interact", duracao=3.6),
    "mapa": dict(item="MAP", lado="e", estado=dict(), tecla="interact", duracao=3.8),
    "nota": dict(item="NOTE_1", lado="e", estado=dict(), tecla="interact", duracao=2.6),
    "troca": dict(item=None, lado="d", estado=dict(carga=0.2, pilhas=2, segurar="BATTERY"), tecla="reload", duracao=2.8),
    "segurar": dict(item=None, lado="d", estado=dict(), tecla=None, duracao=3.0),
    # olhar em volta com a lanterna acesa: guinadas de 60 graus em ~0,5 s (a cabeça do 77_05 faz 50 a 140 graus em 0,2 a 0,6 s)
    "varrer": dict(item=None, lado="d", estado=dict(), tecla=None, duracao=3.2,
                   giros=((0.5, 120.0), (0.2, 0.0), (0.9, -120.0), (0.2, 0.0), (0.8, 90.0), (0.6, 0.0))),
}


def gravar_gesto(nome):
    """Grava o gesto `nome` de `GESTOS` no jogo. Devolve (Gravacao, t_inicio): o instante, na gravação, da tecla."""
    g = GESTOS[nome]
    jogo = montar_jogo_maos(g["item"], g.get("no_chao", False))
    estado(jogo, **g["estado"])

    def preparar(j):
        j.place_player(*JOGADOR, 0.0)
        if g["item"] is not None:
            alvo = j.interact.targets[0].position if j.interact.targets else (0.0, 1.1, 0.8)
            mirar(j, (alvo[0], alvo[1], alvo[2] + 0.02))
        else:
            j.player.pitch = math.radians(-6.0)

    ocupada = jogo.busy_log = []                       # `hands.busy` a cada tique: a duração do gesto (a mão sem controle)
    tique = jogo.tick

    def tique_com_registro(dt, entrada):
        tique(dt, entrada)
        ocupada.append(bool(jogo.hands.busy))
    jogo.tick = tique_com_registro
    roteiro = [grava.Passo(0.8, ao_iniciar=preparar, rotulo="esperar")]
    if g.get("giros"):
        roteiro += [grava.Passo(duracao, giro=giro, rotulo=nome) for duracao, giro in g["giros"]]
    else:
        roteiro.append(grava.Passo(g["duracao"], entradas={g["tecla"]: True} if g["tecla"] else {}, rotulo=nome))
    rec = grava.gravar(jogo, roteiro, nome=nome, ossos="armadura")
    return rec, rec.passos[1][0], jogo


def duracao_ocupada(jogo):
    """Segundos em que a mão ficou sem controle do jogador (`hands.busy`) no gesto gravado por `gravar_gesto`."""
    log = np.array(jogo.busy_log, bool)
    return float(log.sum() / 60.0)


def alcance_do_jogo(rec, lado, t_inicio, vel_minima=VEL_MINIMA):
    """O primeiro alcance da mão `lado` depois da tecla, medido nas mesmas funções do real (punho relativo ao quadril)."""
    mov = relativo_ao_quadril(rec.movimento())
    achados = alcances_da_mao(mov, lado, vel_minima=vel_minima, a_partir_de=t_inicio)
    return (achados[0] if achados else None), mov


# --------------------------------------------------------------------------
# Cenários registrados
# --------------------------------------------------------------------------
class ResultadoMao:
    """O que `Cenario.medir` devolve para gestos de mão: escalares em `.v`, sem curvas de marcha."""

    def __init__(self, v, perfil=None):
        self.v, self.curvas, self.eventos, self.perfil = v, {}, None, perfil


def melhor_alcance(mov, lado, vel_minima=0.3):
    """O alcance de maior pico (e ao menos 15 cm) da mão `lado` de um `Movimento` já relativo ao quadril."""
    achados = [r for r in alcances_da_mao(mov, lado, vel_minima=vel_minima) if r["reta"] >= 0.15]
    return max(achados, key=lambda r: r["pico"]) if achados else None


def marcas_de_fase(r):
    """Início, pico de velocidade e fim de um alcance: as marcas que alinham o real ao jogo."""
    return [r["inicio"], r["inicio"] + r["pico_fracao"] * (r["fim"] - r["inicio"]), r["fim"]]


class CenarioMao(Cenario):
    """Base dos cenários de mão: declare `clip`, `lado_real`, `gesto` (chave de `GESTOS`) e, se quiser, `trecho`.

    O real é o Daniel retargetado com os braços por IK (`retarget.retargetar(bracos="ik")`: o punho vai ao ponto do mocap
    escalado pelo comprimento do braço, então distâncias e velocidades já estão na escala do Daniel). O alinhamento é por fase:
    início, pico de velocidade e fim do alcance em cada relógio."""
    lado_real = "d"
    gesto = "chave"
    relativo = True               # punho relativo ao quadril; False quando o corpo todo se move com a mão (agachar para pegar)
    palco_minimo = True
    vistas = ("frente", "lado", "primeira")
    lento = 0.5
    destaques = ("alcance_t6", "alcance_pico_fracao", "alcance_pico_razao", "alcance_r2")

    def carregar_real(self):
        from .. import retarget
        clip = cmu.carregar(self.clip)
        inicio, fim = self.trecho
        alvo = retarget.retargetar(clip, inicio, fim, bracos="ik")
        return Real(f"CMU {self.clip}", alvo.origem, alvo, [alvo.origem], descricao=self.resumo)

    def medir(self, mov, lado=None, a_partir_de=None, relativo=None):
        rel = relativo_ao_quadril(mov) if (self.relativo if relativo is None else relativo) else mov
        lado = lado or self.lado_real
        r = melhor_alcance(rel, lado) if a_partir_de is None else next(iter(alcances_da_mao(rel, lado, a_partir_de=a_partir_de)), None)
        v = {}
        if r is not None:
            aj = r["ajuste"] or {}
            v = dict(alcance_t6=r["t6"], alcance_distancia=r["reta"], alcance_pico_fracao=100 * r["pico_fracao"],
                     alcance_pico_razao=aj.get("pico_razao", float("nan")), alcance_r2=aj.get("r2_jerk_minimo", float("nan")),
                     alcance_pico=r["pico"])
        resultado = ResultadoMao(v, metricas.perfil_mao(rel, lado))
        resultado.alcance = r
        return resultado

    def preparar(self, jogo=None):
        real = self.carregar_real()
        rec, t0, _jogo = gravar_gesto(self.gesto)
        lado_jogo = GESTOS[self.gesto]["lado"]
        mov_jogo = rec.movimento()
        daniel = real.alvo.movimento()
        medida_real = self.medir(daniel)
        medida_jogo = self.medir(mov_jogo, lado_jogo, a_partir_de=t0, relativo=True)
        r_real, r_jogo = medida_real.alcance, medida_jogo.alcance
        if r_real is not None and r_jogo is not None:
            alinhamento = Alinhamento(marcas_de_fase(r_real), marcas_de_fase(r_jogo))
        else:
            alinhamento = Alinhamento([0.0], [t0])
        real.movimento = daniel
        return Preparado(self, real, rec, mov_jogo, 0.0, alinhamento, medida_real, [medida_real], medida_jogo)

    def fases_chave(self, prep):
        r = prep.marcha_real.alcance
        if r is None:
            duracao = prep.real.movimento.duracao
            return [(f"{int(100 * f)}%", f * duracao) for f in (0.15, 0.4, 0.65, 0.9)]
        a, b = r["inicio"], r["fim"]
        return [("antes do alcance", max(0.0, a - 0.15)), ("meio da subida", a + 0.3 * (b - a)), ("pico de velocidade", a + r["pico_fracao"] * (b - a)),
                ("fim do alcance", b)]

    def legenda(self, prep):
        v_real, v_jogo = prep.marcha_real.v, prep.marcha_jogo.v
        real = (f"REAL  {prep.real.rotulo}", f"alcance {v_real.get('alcance_t6', float('nan')):.2f} s, {v_real.get('alcance_distancia', float('nan')):.2f} m")
        jogo = (f"{self.rotulo_jogo}  {self.gesto}", f"alcance {v_jogo.get('alcance_t6', float('nan')):.2f} s, {v_jogo.get('alcance_distancia', float('nan')):.2f} m")
        return real, jogo

    def executar(self, saida, vistas=None, fps=30, celula=None, video=True, folha=True, preparado=None, max_quadros=None, motor="workbench", **_):
        """Tabela do alcance, perfil de velocidade, folha de contato [real | jogo] e vídeo."""
        import time
        from .. import comparar
        inicio = time.time()
        os.makedirs(saida, exist_ok=True)
        celula = celula or comparar.CELULA
        vistas = comparar.normalizar_vistas(vistas or self.vistas)
        primeira = "primeira_pessoa" in vistas
        terceira = [v for v in vistas if v != "primeira_pessoa"]
        prep = preparado or self.preparar()
        arquivos = self.medidas(prep, saida)
        desenhista = DesenhistaMao(prep, celula, motor)
        if folha:
            caminho, _fases = comparar.folha_de_contato(desenhista, saida, terceira, primeira)
            arquivos["folha_contato"] = caminho
        if video and prep.marcha_real.alcance is not None:
            r = prep.marcha_real.alcance
            t_ini, t_fim = max(0.0, r["inicio"] - 0.3), min(prep.real.movimento.duracao, r["fim"] + 0.5)
            total = int((t_fim - t_ini) / self.lento * fps)
            t_max_jogo = prep.gravacao.t[-1]
            while total > 1 and float(prep.alinhamento.jogo_de_real(t_ini + ((total - 1) / fps) * self.lento)) > t_max_jogo:
                total -= 1
            if max_quadros:
                total = min(total, max_quadros)
            colunas = 3 if len(terceira) + (2 if primeira else 0) + 1 > 4 else 2

            def quadros():
                for n in range(total):
                    t_real = t_ini + (n / fps) * self.lento
                    yield comparar._quadro_video(desenhista, terceira, primeira, t_real, f"quadro {n + 1}/{total}", colunas)

            caminho, escritos = comparar.escrever_mp4(quadros(), os.path.join(saida, "video.mp4"), fps)
            arquivos["video"] = caminho
        print(f"[maos] {self.nome}: {', '.join(f'{k}={v}' for k, v in arquivos.items())} em {time.time() - inicio:.0f} s", flush=True)
        return arquivos

    def medidas(self, prep, saida):
        """perfil.png (velocidade do punho normalizada pelo alcance, real e jogo) e metricas.json."""
        from .. import graficos
        arquivos = {}
        perfis = []
        for rotulo, resultado, cor in (("real (Daniel retargetado)", prep.marcha_real, graficos.COR_REAL), ("jogo", prep.marcha_jogo, graficos.COR_JOGO)):
            r = resultado.alcance
            if r is not None:
                perfis.append((rotulo, resultado.perfil[r["a"]:r["b"]], 120.0 if "real" in rotulo else 60.0, cor))
        if perfis:
            r = prep.marcha_jogo.alcance
            arquivos["perfil"] = graficos.painel_alcance(perfis, os.path.join(saida, "perfil.png"),
                                                         titulo=f"{self.titulo}: velocidade do punho no alcance",
                                                         modelo=(r["reta"], r["t6"]) if r else None)
        registro = dict(cenario=self.nome, real=prep.marcha_real.v, jogo=prep.marcha_jogo.v)
        with open(os.path.join(saida, "metricas.json"), "w", encoding="utf-8") as arquivo:
            json.dump(registro, arquivo, ensure_ascii=False, indent=1, default=float)
        arquivos["metricas"] = os.path.join(saida, "metricas.json")
        return arquivos


def _desenhista():
    from .. import comparar

    class DesenhistaMao(comparar.Desenhista):
        """O `Desenhista` do comparar sem os eventos de marcha: o painel de texto mostra as métricas do alcance."""

        def __init__(self, prep, celula=comparar.CELULA, motor="workbench"):
            from tools.movimento_ref.palco import Palco
            self.prep, self.celula = prep, celula
            self.palco = Palco(celula[0], celula[1], motor)
            self.alvo, self.rec = prep.real.alvo, prep.gravacao
            self.palco.origem("real", self.alvo.raiz[0, :2], self.alvo.raiz[0, 3])
            self.palco.origem("jogo", self.rec.raiz[0, :2], self.rec.raiz[0, 3])

        def painel_info(self, t_real, fase_texto=""):
            from PIL import Image, ImageDraw
            prep, cen = self.prep, self.prep.cenario
            imagem = np.full((self.celula[1], self.celula[0], 3), (252, 252, 251), np.uint8)
            (real1, real2), (jogo1, jogo2) = cen.legenda(prep)
            linhas = [(cen.titulo, comparar.TINTA, True, 15), ("", comparar.TINTA, False, 8), (real1, comparar.AZUL, True, 13),
                      (real2, comparar.TINTA_SUAVE, False, 12), (jogo1, comparar.LARANJA, True, 13), (jogo2, comparar.TINTA_SUAVE, False, 12),
                      ("", comparar.TINTA, False, 8),
                      (f"câmera lenta x{cen.lento:g}; o jogo toca na fase do real (x{prep.alinhamento.razao(t_real):.2f})", comparar.TINTA_SUAVE, False, 11),
                      (fase_texto, comparar.TINTA_SUAVE, False, 11), ("", comparar.TINTA, False, 8)]
            for chave, rotulo in (("alcance_t6", "duração (s)"), ("alcance_pico_fracao", "pico em % da duração"),
                                  ("alcance_pico_razao", "pico / média"), ("alcance_r2", "R2 do jerk mínimo")):
                real, jogo = prep.marcha_real.v.get(chave, float("nan")), prep.marcha_jogo.v.get(chave, float("nan"))
                linhas.append((f"{rotulo}:  real {real:.2f}   jogo {jogo:.2f}", comparar.TINTA, False, 12))
            tela = Image.fromarray(imagem)
            d = ImageDraw.Draw(tela)
            y = 8
            for texto, cor, negrito, tamanho in linhas:
                d.text((10, y), texto, font=comparar.fonte(tamanho, negrito), fill=cor)
                y += tamanho + 6
            return np.array(tela)
    return DesenhistaMao


class _Preguica:
    def __getattr__(self, nome):
        return getattr(_desenhista(), nome)

    def __call__(self, *a, **k):
        return _desenhista()(*a, **k)


DesenhistaMao = _Preguica()           # só importa comparar (e o palco) quando alguém desenha


@registrar
class PegarChao(CenarioMao):
    nome = "pegar_chao"
    titulo = "Pegar do chão (CMU 26_09) contra a pilha no chão"
    resumo = "abaixar e pegar um objeto"
    clip = "26_09"
    lado_real = "e"
    gesto = "pilha_chao"
    relativo = False              # no mocap o corpo todo abaixa com a mão; no jogo só o braço estica (a cobrar do corpo)


@registrar
class Alcancar(CenarioMao):
    nome = "alcancar"
    titulo = "Alcançar (CMU 15_06) contra o alcance do mapa"
    resumo = "inclinar e alcançar"
    clip = "15_06"
    trecho = (0.2, 6.0)
    gesto = "mapa"
    lado_real = "e"


@registrar
class LanternaOlhar(CenarioMao):
    nome = "lanterna_olhar"
    titulo = "Olhar em volta com a lanterna (CMU 77_05) contra a lanterna na mão"
    resumo = "lanterna na mão direita, olhar em volta"
    clip = "77_05"
    gesto = "varrer"
    lado_real = "d"


@registrar
class PegarChave(CenarioMao):
    nome = "pegar_chave"
    titulo = "Apanhar as chaves (CMU 22_22) contra o chaveiro"
    resumo = "andar e apanhar chaves jogadas"
    clip = "22_22"
    gesto = "chave"
    lado_real = "d"


@registrar
class Pilhas(CenarioMao):
    nome = "pilhas"
    titulo = "Duas mãos (CMU 115_01) contra a troca de pilhas"
    resumo = "pegar uma caixa com as duas mãos"
    clip = "115_01"
    gesto = "troca"
    lado_real = "d"


@registrar
class Nota(CenarioMao):
    nome = "nota"
    titulo = "Mão ao rosto (CMU 79_38) contra a nota até o rosto"
    resumo = "beber água: mão ao rosto"
    clip = "79_38"
    gesto = "nota"
    lado_real = "d"


# --------------------------------------------------------------------------
# Física dos itens e da luz (DERIVADO) e conferência independente
# --------------------------------------------------------------------------
def pendulo_independente(inercia, massa, distancia, amortecimento, angulo0, duracao=6.0, passo=1e-4):
    """Integra, com RK4 e sem usar nada do engine, o corpo rígido pendurado: I th'' + c th' + m g d sin(th) = 0.
    Devolve (t, theta). `amortecimento` é a razão zeta = c / (2 raiz(I m g d))."""
    w2 = massa * G * distancia / inercia
    c = 2.0 * amortecimento * math.sqrt(w2)           # c / I
    n = int(duracao / passo)
    t = np.arange(n + 1) * passo
    saida = np.zeros(n + 1)
    th, om = angulo0, 0.0
    saida[0] = th

    def f(th, om):
        return om, -w2 * math.sin(th) - c * om
    for i in range(n):
        k1 = f(th, om)
        k2 = f(th + 0.5 * passo * k1[0], om + 0.5 * passo * k1[1])
        k3 = f(th + 0.5 * passo * k2[0], om + 0.5 * passo * k2[1])
        k4 = f(th + passo * k3[0], om + passo * k3[1])
        th += passo / 6.0 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        om += passo / 6.0 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        saida[i + 1] = th
    return t, saida


def periodo_e_decaimento(t, theta):
    """Período (s, entre cruzamentos ascendentes por zero) e razão de amortecimento (decremento logarítmico dos picos)."""
    sobe = np.where((theta[:-1] < 0) & (theta[1:] >= 0))[0]
    if len(sobe) < 2:
        return float("nan"), float("nan")
    instantes = [t[i] - theta[i] * (t[i + 1] - t[i]) / (theta[i + 1] - theta[i]) for i in sobe]
    periodo = float(np.mean(np.diff(instantes)))
    picos = [theta[a:b].max() for a, b in zip(sobe[:-1], sobe[1:])]
    if len(picos) < 2 or picos[0] <= 0 or picos[-1] <= 0:
        return periodo, float("nan")
    delta = math.log(picos[0] / picos[-1]) / (len(picos) - 1)
    return periodo, float(delta / math.sqrt(4 * math.pi ** 2 + delta ** 2))


def medir_pendulo_do_engine(jogo, angulo0=0.2, duracao=6.0):
    """Solta o `Pendulum` do engine com `angulo0` rad e mede período e amortecimento em passos de 1/60 s."""
    p = jogo.hands.pendulum
    p.reset()
    p.angle[0] = angulo0
    dt = 1.0 / 60.0
    n = int(duracao / dt)
    t = np.arange(n + 1) * dt
    theta = np.zeros(n + 1)
    theta[0] = angulo0
    for i in range(n):
        p.step(dt, (0.0, 0.0))
        theta[i + 1] = p.angle[0]
    p.reset()
    return t, theta


def medir_filamento(jogo, dt=0.001):
    """Tempo (ms) de subida de 10 a 90% ao ligar e de descida de 90 a 10% ao desligar, a 1 kHz, com a lanterna do jogo."""
    fl = jogo.flashlight
    s = jogo.state
    s.has_flashlight, s.battery = True, 1.0
    s.flashlight_on = False
    for _ in range(300):
        fl.update(dt, 0.0, 0.0)

    def tempo(subindo):
        s.flashlight_on = subindo
        trilha = []
        for _ in range(600):
            fl.update(dt, 0.0, 0.0)
            trilha.append(fl.intensity)
        trilha = np.array(trilha)
        alvo = (0.1, 0.9) if subindo else (0.9, 0.1)
        a = int(np.argmax(trilha >= alvo[0])) if subindo else int(np.argmax(trilha <= alvo[0]))
        b = int(np.argmax(trilha >= alvo[1])) if subindo else int(np.argmax(trilha <= alvo[1]))
        return 1000.0 * (b - a) * dt, trilha
    subida, trilha_subida = tempo(True)
    descida, _ = tempo(False)
    return subida, descida


def medir_piscada(jogo, comprimento=0.13, dt=0.001):
    """A maior duração contínua (ms) com brilho abaixo de 50% numa rajada de `comprimento` s, e quantas quedas distintas."""
    fl = jogo.flashlight
    s = jogo.state
    s.has_flashlight, s.battery, s.flashlight_on = True, 1.0, True
    for _ in range(300):
        fl.update(dt, 0.0, 0.0)
    fl.burst(comprimento)
    trilha = []
    for _ in range(int((comprimento + 0.3) / dt)):
        fl.update(dt, 0.0, 0.0)
        trilha.append(fl.intensity)
    baixo = np.array(trilha) < 0.5
    maior, atual, quedas = 0, 0, 0
    for i, b in enumerate(baixo):
        atual = atual + 1 if b else 0
        maior = max(maior, atual)
        if b and (i == 0 or not baixo[i - 1]):
            quedas += 1
    return maior * dt * 1000.0, quedas, float(np.min(trilha))


def medir_atraso_do_feixe(jogo, taxa=40.0, duracao=1.2, dt=1.0 / 120.0):
    """Gira a câmera a `taxa` graus/s e mede o atraso angular da luz em regime: tau = atraso / taxa (ms)."""
    fl = jogo.flashlight
    s = jogo.state
    s.has_flashlight, s.flashlight_on, s.battery = True, True, 1.0
    yaw = 0.0
    fl.snap_to_camera(yaw, 0.0)
    for _ in range(int(duracao / dt)):
        yaw += math.radians(taxa) * dt
        fl.update(dt, yaw, 0.0)
    atraso = abs(fl.offset[1])
    return 1000.0 * atraso / math.radians(taxa)


def flecha_da_folha_teorica(comprimento, aceleracao=G, rigidez=2.5e-4, densidade=0.08):
    """Flecha da ponta (m) da viga em balanço sob carga distribuída: d = rho_a a L^4 / (8 EI) (regime linear)."""
    return densidade * aceleracao * comprimento ** 4 / (8.0 * rigidez)


def frequencia_da_folha_teorica(comprimento, rigidez=2.5e-4, densidade=0.08):
    """Primeiro modo da viga em balanço, w = 3,516 / L^2 raiz(EI / rho_a), em rad/s."""
    return 3.516 / comprimento ** 2 * math.sqrt(rigidez / densidade)


# --------------------------------------------------------------------------
# Tabela completa e figuras
# --------------------------------------------------------------------------
def principal(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lista", action="store_true")
    ap.add_argument("--gerar-referencia", action="store_true", help="remede o mocap e grava assets/referencia/maos_ref.json")
    args = ap.parse_args(argv)
    if args.lista:
        for nome, titulo in [(c.nome, c.titulo) for c in (PegarChao, Alcancar, LanternaOlhar, PegarChave, Pilhas, Nota)]:
            print(f"{nome:16s} {titulo}")
        return
    if args.gerar_referencia:
        dados = gerar_referencia()
        print(json.dumps(dados, ensure_ascii=False, indent=1))
        return


if __name__ == "__main__":
    principal()
