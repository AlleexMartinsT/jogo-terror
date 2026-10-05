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
from tools.movimento_ref.cenarios.base import CenarioAlcance  # noqa: E402
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


def montar_gesto(nome):
    """O `Game` do gesto `nome` de `GESTOS`: palco mínimo com o item e o estado do jogador já preparados."""
    g = GESTOS[nome]
    jogo = montar_jogo_maos(g["item"], g.get("no_chao", False))
    estado(jogo, **g["estado"])
    return jogo


def roteiro_do_gesto(nome):
    """Roteiro do gesto: 0,8 s parado olhando o item (passo 0) e o gesto (passo 1, com a tecla no primeiro quadro)."""
    g = GESTOS[nome]

    def preparar(j):
        j.place_player(*JOGADOR, 0.0)
        if g["item"] is not None:
            alvo = j.interact.targets[0].position if j.interact.targets else (0.0, 1.1, 0.8)
            mirar(j, (alvo[0], alvo[1], alvo[2] + 0.02))
        else:
            j.player.pitch = math.radians(-6.0)

    roteiro = [grava.Passo(0.8, ao_iniciar=preparar, rotulo="esperar")]
    if g.get("giros"):
        roteiro += [grava.Passo(duracao, giro=giro, rotulo=nome) for duracao, giro in g["giros"]]
    else:
        roteiro.append(grava.Passo(g["duracao"], entradas={g["tecla"]: True} if g["tecla"] else {}, rotulo=nome))
    return roteiro


def gravar_gesto_em(jogo, nome):
    """Grava o gesto `nome` em `jogo` (de `montar_gesto`). Devolve (Gravacao, t_inicio): o instante da tecla na gravação."""
    ocupada = jogo.busy_log = []                       # `hands.busy` a cada tique: a duração do gesto (a mão sem controle)
    tique = jogo.tick

    def tique_com_registro(dt, entrada):
        tique(dt, entrada)
        ocupada.append(bool(jogo.hands.busy))
    jogo.tick = tique_com_registro
    rec = grava.gravar(jogo, roteiro_do_gesto(nome), nome=nome, ossos="armadura")
    return rec, rec.passos[1][0]


def gravar_gesto(nome):
    """Monta e grava o gesto `nome`. Devolve (Gravacao, t_inicio, jogo)."""
    jogo = montar_gesto(nome)
    rec, t0 = gravar_gesto_em(jogo, nome)
    return rec, t0, jogo


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
class CenarioMao(CenarioAlcance):
    """Base dos cenários de mão sobre o `CenarioAlcance` do agente 1: o real é o Daniel retargetado com os braços por IK, o
    perfil de velocidade do alcance é comparado ao do mocap e ao de jerk mínimo, e o alinhamento é por início, pico de
    velocidade e chegada do alcance. Aqui entram só o palco com o item (`montar_gesto`) e o roteiro (`roteiro_do_gesto`).

    `clip` e `trecho`: o alcance isolado do mocap (as capturas de pegar do chão, lanterna e anotação têm vários movimentos;
    o trecho escolhido tem um alcance único com R2 do jerk mínimo > 0,8). `lado_mao`: a mão do real; `lado_jogo`: a do jogo."""
    gesto = "chave"
    lado_jogo = "e"
    vel_minima = 0.3
    palco_minimo = True
    vistas = ("frente", "lado", "primeira")
    passo = 1
    margem = 0.0
    alcance_real = "maior"
    alcance_jogo = "maior"

    @property
    def roteiro(self):
        return self.gesto

    def medir(self, mov, qual=None):
        """Como o do agente 1, escolhendo a mão pelo corpo: o real usa `lado_mao`, o jogo `lado_jogo`."""
        original = self.lado_mao
        self.lado_mao = self.lado_jogo if mov.fonte == "jogo" else original
        try:
            return super().medir(mov, qual)
        finally:
            self.lado_mao = original

    def gravar_jogo(self, jogo):
        rec, _t0 = gravar_gesto_em(jogo, self.gesto)
        return rec

    def preparar(self, jogo=None):
        return super().preparar(jogo or montar_gesto(self.gesto))


@registrar
class PegarChao(CenarioMao):
    nome = "pegar_chao"
    titulo = "Pegar do chão (CMU 26_09, descida) contra a pilha no chão"
    resumo = "abaixar e pegar um objeto: o real usa o corpo todo, o jogo só o braço"
    clip = "26_09"
    trecho = (0.7, 2.1)
    lado_mao = "d"
    gesto = "pilha_chao"


@registrar
class Alcancar(CenarioMao):
    nome = "alcancar"
    titulo = "Alcançar (CMU 15_06) contra o alcance até o mapa"
    resumo = "inclinar e alcançar"
    clip = "15_06"
    trecho = (28.6, 30.0)
    lado_mao = "d"
    gesto = "mapa"


@registrar
class LanternaOlhar(CenarioMao):
    nome = "lanterna_olhar"
    titulo = "Levantar a lanterna (CMU 77_05) contra a lanterna do jogo"
    resumo = "olhar em volta com a lanterna: a mão sobe com ela"
    clip = "77_05"
    trecho = (0.8, 1.6)
    lado_mao = "d"
    lado_jogo = "d"
    gesto = "lanterna"


@registrar
class PegarChave(CenarioMao):
    nome = "pegar_chave"
    titulo = "Apanhar as chaves (CMU 22_22) contra o chaveiro"
    resumo = "andar e apanhar chaves jogadas"
    clip = "22_22"
    lado_mao = "d"
    gesto = "chave"
    alcance_real = 0


@registrar
class Pilhas(CenarioMao):
    nome = "pilhas"
    titulo = "Duas mãos (CMU 115_01) contra a troca de pilhas"
    resumo = "pegar uma caixa com as duas mãos"
    clip = "115_01"
    trecho = (2.4, 3.5)
    lado_mao = "d"
    gesto = "troca"
    alcance_jogo = 0              # a primeira subida da mão esquerda até a boca da lanterna

    def recorte_jogo(self, rec):
        """A troca tem vários movimentos seguidos (subir, puxar a pilha velha, encaixar, recolher); o ajuste de jerk mínimo olha
        meia janela além do alcance e leria o puxão seguinte como parte da subida. O recorte termina no vale que fecha a subida."""
        mov, t0 = super().recorte_jogo(rec)
        achados = metricas.detectar_alcances(metricas.perfil_mao(mov, self.lado_jogo), mov.fps, self.vel_minima)
        if len(achados) > 1:
            mov = mov.trecho(0.0, achados[0][1] / mov.fps)
        return mov, t0


@registrar
class Nota(CenarioMao):
    nome = "nota"
    titulo = "Mão ao rosto (CMU 79_38) contra a nota até o rosto"
    resumo = "beber água: a mão sobe ao rosto"
    clip = "79_38"
    trecho = (0.2, 1.2)
    lado_mao = "d"
    gesto = "nota"


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


def medir_filamento(jogo, dt=0.001, series=None):
    """Tempo (ms) de subida de 10 a 90% ao ligar e de descida de 90 a 10% ao desligar, a 1 kHz, com a lanterna do jogo.
    `series` (dict) recebe as curvas de brilho de 1 ms em "subida" e "descida", para os gráficos."""
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
    descida, trilha_descida = tempo(False)
    if series is not None:
        series["subida"], series["descida"] = [float(x) for x in trilha_subida], [float(x) for x in trilha_descida]
    return subida, descida


def medir_piscada(jogo, comprimento=0.13, dt=0.001, series=None):
    """A maior duração contínua (ms) com brilho abaixo de 50% numa rajada de `comprimento` s, e quantas quedas distintas.
    `series` (dict) recebe o brilho de 1 ms em "brilho"."""
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
    if series is not None:
        series["brilho"] = [float(x) for x in trilha]
    baixo = np.array(trilha) < 0.5
    maior, atual, quedas = 0, 0, 0
    for i, b in enumerate(baixo):
        atual = atual + 1 if b else 0
        maior = max(maior, atual)
        if b and (i == 0 or not baixo[i - 1]):
            quedas += 1
    return maior * dt * 1000.0, quedas, float(np.min(trilha))


def medir_atraso_do_feixe(jogo, taxa=40.0, duracao=1.2, dt=1.0 / 120.0, series=None):
    """Gira a câmera a `taxa` graus/s e mede o atraso angular da luz em regime: tau = atraso / taxa (ms).
    `series` (dict) recebe, a cada quadro, a guinada da câmera e o atraso do feixe, em graus ("guinada", "atraso")."""
    fl = jogo.flashlight
    s = jogo.state
    s.has_flashlight, s.flashlight_on, s.battery = True, True, 1.0
    yaw = 0.0
    fl.snap_to_camera(yaw, 0.0)
    guinada, lag = [], []
    for _ in range(int(duracao / dt)):
        yaw += math.radians(taxa) * dt
        fl.update(dt, yaw, 0.0)
        guinada.append(math.degrees(yaw))
        lag.append(abs(math.degrees(fl.offset[1])))
    if series is not None:
        series["guinada"], series["atraso"] = guinada, lag
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
