"""Mede o que as mãos, os itens e a lanterna fazem no jogo e monta a tabela métrica a métrica contra o real e a física.

    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.maos_tabela medir out/f4_3/jogo_depois.json
    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.cenarios.maos_tabela tabela out/f4_3/final \\
        --antes out/f4_3/jogo_antes.json --depois out/f4_3/jogo_depois.json

`medir` roda o jogo que estiver em `sem_alvorada` (para o "antes", rode a partir de uma cópia do commit anterior); `tabela`
junta os dois JSON com o real (assets/referencia/maos_ref.json) e escreve tabela.txt, tabela.png, tabela.json e os gráficos.
A fonte de cada linha é MEDIDO (mocap CMU), DERIVADO (lei física conferida numericamente) ou ESTIMADO (valor de engenharia).
"""
import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import numpy as np  # noqa: E402

from tools.movimento_ref import metricas  # noqa: E402
from tools.movimento_ref.cenarios import maos  # noqa: E402
from tools.movimento_ref.metricas import Linha  # noqa: E402

NAN = float("nan")
GESTOS_PEGAR = ("lanterna", "pilha", "pilha_chao", "chave", "mapa", "nota")


# --------------------------------------------------------------------------
# O jogo
# --------------------------------------------------------------------------
def _cotovelo_no_centro(rec, lado, mascara):
    """Quadros em que o cotovelo do braço `lado` cai no meio da tela (|x| < 0,35 da profundidade, |y| < 0,25)."""
    from tools.movimento_ref.grava import OSSO_INDICE
    cotovelo = rec.cabecas[:, OSSO_INDICE[f"Forearm.{'L' if lado == 'e' else 'R'}"]]
    local = np.einsum("tji,tj->ti", rec.camera_rot, cotovelo - rec.camera_pos)           # direita, cima, trás
    profundidade = -local[:, 2]
    central = (profundidade > 0.10) & (np.abs(local[:, 0]) < 0.35 * profundidade) & (np.abs(local[:, 1]) < 0.25 * profundidade)
    return int((central & mascara).sum())


def dobra_do_pulso(rec, lado, mascara):
    """Ângulo (graus) entre o antebraço e a mão, percentil 95 dos quadros em `mascara`: quanto o pulso dobra no gesto. Um pulso
    dobrado ao limite aperta o punho da manga ("estrangula"); o limite do solver é 80 graus."""
    from tools.movimento_ref.grava import OSSO_INDICE
    sufixo = "L" if lado == "e" else "R"
    cotovelo = rec.cabecas[:, OSSO_INDICE[f"Forearm.{sufixo}"]]
    pulso = rec.cabecas[:, OSSO_INDICE[f"Hand.{sufixo}"]]
    ponta = rec.pontas[:, OSSO_INDICE[f"Hand.{sufixo}"]]
    angulos = maos.angulo(pulso - cotovelo, ponta - pulso)
    return float(np.percentile(angulos[mascara], 95)) if mascara.any() else NAN


def medir_gestos():
    saida = {}
    for nome in GESTOS_PEGAR:
        g = maos.GESTOS[nome]
        rec, t0, jogo = maos.gravar_gesto(nome)
        r, rel = maos.alcance_do_jogo(rec, g["lado"], t0)
        indice = 0 if g["lado"] == "e" else 1
        com_peso = rec.peso_alvo[:, indice] > 0.02
        depois = np.where(com_peso & (rec.t >= t0))[0]
        dados = dict(duracao_total=maos.duracao_ocupada(jogo), dobra_do_pulso=dobra_do_pulso(rec, g["lado"], com_peso),
                     cotovelo_no_centro=_cotovelo_no_centro(rec, g["lado"], com_peso))
        if r is not None:
            aj = r["ajuste"] or {}
            perfil = metricas.perfil_mao(rel, g["lado"])[r["a"]:r["b"]]
            dados.update(t6=r["t6"], distancia=r["reta"], pico_fracao=r["pico_fracao"], pico=r["pico"], corr=r["corr"],
                         pico_fracao_ajuste=aj.get("pico_fracao", NAN), pico_razao=aj.get("pico_razao", NAN),
                         r2=aj.get("r2_jerk_minimo", NAN), t_ajuste=aj.get("duracao", NAN), inicio=r["inicio"] - t0,
                         perfil=[float(x) for x in perfil], fps=rel.fps)
        saida[nome] = dados
    return saida


def medir_posicao_de_segurar():
    rec, t0, jogo = maos.gravar_gesto("segurar")
    mov = rec.movimento()
    final = (mov.t > mov.t[-1] - 1.0)
    postura = maos.postura_do_braco(mov, "d")
    saida = {k: float(np.mean(v[final])) for k, v in postura.items()}
    saida["dobra_do_pulso"] = dobra_do_pulso(rec, "d", final)
    return saida


def medir_troca():
    rec, t0, jogo = maos.gravar_gesto("troca")
    fps = rec.fps
    duracao = maos.duracao_ocupada(jogo)
    saidas = {}
    for indice, lado in ((0, "e"), (1, "d")):
        alvo = rec.alvo_mao[:, indice]
        v = np.linalg.norm(np.gradient(np.nan_to_num(alvo), 1 / fps, axis=0), axis=1)
        v = v[int(t0 * fps):]
        pico = v.max() if len(v) else 0.0
        saidas[lado] = float(np.argmax(v > 0.1 * pico) / fps) if pico > 0 else NAN
    return dict(duracao=duracao, defasagem_inicio=abs(saidas["e"] - saidas["d"]))


def medir_folga_da_troca():
    """Menor distância (mm) entre o centro da palma esquerda e a superfície do corpo da lanterna enquanto a pilha entra."""
    import math as m
    from mathutils import Euler, Matrix, Vector
    jogo = maos.montar_jogo_maos()
    maos.estado(jogo, carga=0.2, pilhas=2, segurar="BATTERY")
    from sem_alvorada.engine.inputstate import InputState
    for _ in range(60):
        jogo.tick(1 / 60, InputState())
    jogo.hands.reload_flashlight()
    menor = 9.0
    for i in range(int(3.0 / (1 / 60))):
        jogo.tick(1 / 60, InputState())
        lm = jogo.flashlight.lantern_matrix
        if lm is None:
            continue
        pos, rot = jogo.player.camera_pose()
        camera = Euler(rot, "XYZ").to_matrix().to_4x4()
        camera.translation = Vector(pos)
        local = (camera @ lm).inverted() @ Vector(jogo.body.arm("L").hand_world_position())
        if -0.20 < local.z < 0.015:
            menor = min(menor, m.hypot(local.x, local.y) - 0.0194)
    return menor * 1000.0


def medir_fisica():
    jogo = maos.montar_jogo_maos()
    saida = {}
    subida, descida = maos.medir_filamento(jogo)
    saida["filamento_subida_ms"], saida["filamento_descida_ms"] = subida, descida
    jogo = maos.montar_jogo_maos()
    abertura, quedas, fundo = maos.medir_piscada(jogo)
    saida["piscada_abertura_ms"], saida["piscada_quedas"], saida["piscada_fundo"] = abertura, quedas, fundo
    jogo = maos.montar_jogo_maos()
    saida["feixe_tau_ms"] = maos.medir_atraso_do_feixe(jogo)
    # chaveiro
    jogo = maos.montar_jogo_maos()
    t, theta = maos.medir_pendulo_do_engine(jogo)
    saida["pendulo_periodo"], saida["pendulo_zeta"] = maos.periodo_e_decaimento(t, theta)
    p = jogo.hands.pendulum
    saida["pendulo_comprimento"] = float(getattr(p, "length", NAN))
    saida["pendulo_trilha"] = [float(x) for x in theta[::6]]
    # pêndulo composto derivado da malha
    obj = jogo.hands.models.objects.get("KEY")
    try:
        from sem_alvorada.engine import handheld
        info = handheld.compound_pendulum(obj.data)
        saida["pendulo_derivado"] = dict(info)
    except Exception:       # noqa: BLE001 - o "antes" não tem o cálculo
        saida["pendulo_derivado"] = None
    # polegar relaxado: ângulo entre o polegar e o eixo dos dedos, preset "relaxed" sem fechar (curl 0)
    saida.update(medir_dedos())
    return saida


def medir_dedos():
    from sem_alvorada.body import fingers as F
    from sem_alvorada.body import skeleton as S
    from sem_alvorada.body import solver as V
    lado = "L"
    f, p, t = S.hand_frame(lado)
    saida = {}
    for rotulo, curls in (("aberta", (0.0, 0.0, 0.0, 0.0, 0.0)), ("concha", (0.18, 0.34, 0.40, 0.46, 0.52))):
        q = F.finger_rotations(lado, curls, 0.0)
        sol = V.solve(V.PoseSpec(rot=q))
        base = sol.head[S.BONE_INDEX[f"Thumb0.{lado}"]]
        ponta = sol.tail(f"Thumb2.{lado}")
        d = ponta - base
        saida[f"polegar_{rotulo}"] = math.degrees(math.acos(max(-1.0, min(1.0, d.normalized().dot(f)))))
    return saida


def medir_cascata():
    """Atraso (ms) entre a base e a ponta de um dedo ao fechar a mão de uma vez: junta da base 50%, da ponta 50% (60 Hz)."""
    jogo = maos.montar_jogo_maos()
    braco = jogo.body.arm("R")
    dt = 1.0 / 240.0
    braco.release(1.0)
    for _ in range(240):
        jogo.body.update(dt, jogo.player, (0.0, 0.0))
    braco.set_target((0.2, -0.15, -0.4), (0, 0, 0), 1.0)
    tempos = {}
    trilha = {"base": [], "ponta": []}
    for i in range(int(0.6 / dt)):
        braco.set_target((0.2, -0.15, -0.4), (0, 0, 0), 1.0)
        braco.set_fingers((1, 1, 1, 1, 1), 0.0)
        jogo.body.update(dt, jogo.player, (0.0, 0.0))
        casc = getattr(braco, "_cascade", None)
        if casc is not None:
            trilha["base"].append(casc.joint[1][0])
            trilha["ponta"].append(casc.joint[1][2])
        else:
            trilha["base"].append(braco._curls[1])
            trilha["ponta"].append(braco._curls[1])
    base, ponta = np.array(trilha["base"]), np.array(trilha["ponta"])
    inicial = base[0]
    alvo = 1.0
    meio = inicial + 0.5 * (alvo - inicial)
    tb = float(np.argmax(base >= meio) * dt)
    tp = float(np.argmax(ponta >= meio) * dt)
    return dict(cascata_ms=1000.0 * (tp - tb))


def medir_tudo():
    return dict(gestos=medir_gestos(), segurar=medir_posicao_de_segurar(), troca=medir_troca(), folga_troca_mm=medir_folga_da_troca(),
                fisica=medir_fisica(), dedos=medir_cascata())


# --------------------------------------------------------------------------
# A tabela
# --------------------------------------------------------------------------
def _linha(chave, rotulo, unidade, real, antes, depois, tolerancia, casas=2, fonte=""):
    """Linha de `metricas.Linha`; `diferenca` = depois - real. O estado é o do "depois"; a fonte vai no rótulo."""
    ok = bool(abs(depois - real) <= tolerancia) if np.isfinite(depois) and np.isfinite(real) else None
    linha = Linha(chave, f"{rotulo} [{fonte}]" if fonte else rotulo, unidade, real, depois, depois - real if np.isfinite(real) else NAN,
                  tolerancia, ok, casas)
    linha.antes = antes
    return linha


def depois_dobra(depois):
    return float(np.nanmean([depois["gestos"][g].get("dobra_do_pulso", NAN) for g in GESTOS_PEGAR]))


def montar_linhas(antes, depois, ref):
    lei = ref["lei_do_alcance"]
    forma = ref["forma_do_alcance"]
    lant = ref["lanterna"]
    linhas = []
    for nome in GESTOS_PEGAR:
        a, d = antes["gestos"].get(nome, {}), depois["gestos"].get(nome, {})
        if "t6" not in d:
            continue
        real = lei["a"] + lei["b"] * d["distancia"] / maos.BRACO_DANIEL
        linhas.append(_linha(f"t6_{nome}", f"alcance: duração a 6% do pico, {nome} (D={d['distancia']:.2f} m)", "s", real, a.get("t6", NAN),
                             d["t6"], 0.25, 2, "MEDIDO"))
    for chave, rotulo, indice, tol, casas, pct in (("pico_fracao", "alcance: pico da velocidade em % da duração", 0, 8.0, 0, True),):
        pass
    medias = lambda dic, campo: float(np.nanmean([dic["gestos"][g].get(campo, NAN) for g in GESTOS_PEGAR if campo in dic["gestos"].get(g, {})]))  # noqa: E731
    linhas.append(_linha("pico_fracao", "alcance: pico da velocidade, % da duração (média dos gestos)", "%", 100 * forma["pico_fracao"][0] if forma["n"] else 100 * lei["pico_fracao"][0],
                         100 * medias(antes, "pico_fracao"), 100 * medias(depois, "pico_fracao"), 8.0, 0, "MEDIDO"))
    linhas.append(_linha("pico_razao", "alcance: pico / velocidade média (jerk mínimo = 1,875)", "", forma["pico_razao"][0], medias(antes, "pico_razao"),
                         medias(depois, "pico_razao"), 0.25, 2, "MEDIDO"))
    linhas.append(_linha("r2", "alcance: R2 do ajuste ao jerk mínimo", "", forma["r2"][0], medias(antes, "r2"), medias(depois, "r2"), 0.15, 2, "MEDIDO"))
    linhas.append(_linha("duracao_total", "gesto de pegar: duração total (média dos 6)", "s", NAN, medias(antes, "duracao_total"),
                         medias(depois, "duracao_total"), 3.0, 2, "decisão"))
    linhas.append(_linha("cotovelo_centro", "cotovelo no meio da tela durante o gesto (soma dos 6)", "quadros", 0.0,
                         float(sum(antes["gestos"][g]["cotovelo_no_centro"] for g in GESTOS_PEGAR)),
                         float(sum(depois["gestos"][g]["cotovelo_no_centro"] for g in GESTOS_PEGAR)), 0.0, 0, "MEDIDO"))
    linhas.append(_linha("dobra_pulso", "pulso dobrado, p95 (média dos 6 gestos; limite 72)", "graus", NAN, medias(antes, "dobra_do_pulso"),
                         medias(depois, "dobra_do_pulso"), 72.0, 0, "ESTIMADO <= 72"))
    linhas[-1].ok = bool(depois_dobra(depois) <= 72.5)
    sa, sd = antes["segurar"], depois["segurar"]
    linhas.append(_linha("dobra_pulso_seg", "pulso dobrado com a lanterna parada", "graus", NAN, sa["dobra_do_pulso"], sd["dobra_do_pulso"], 72.0, 0, "ESTIMADO <= 72"))
    linhas[-1].ok = bool(sd["dobra_do_pulso"] <= 72.5)
    linhas.append(_linha("seg_cotovelo", "lanterna parada: flexão do cotovelo", "graus", lant["cotovelo"], sa["cotovelo"], sd["cotovelo"], 15.0, 0, "MEDIDO"))
    linhas.append(_linha("seg_elevacao", "lanterna parada: braço em relação à vertical", "graus", lant["elevacao"], sa["elevacao"], sd["elevacao"], 18.0, 0, "MEDIDO"))
    linhas.append(_linha("seg_razao", "lanterna parada: distância punho-ombro / braço", "", lant["razao"], sa["razao"], sd["razao"], 0.10, 2, "MEDIDO"))
    linhas.append(_linha("seg_altura", "lanterna parada: punho acima do ombro / braço", "", lant["altura"], sa["altura"], sd["altura"], 0.15, 2, "MEDIDO"))
    fa, fd = antes["fisica"], depois["fisica"]
    linhas.append(_linha("feixe_tau", "feixe: constante de tempo atrás da câmera", "ms", lant["tau_ms"], fa["feixe_tau_ms"], fd["feixe_tau_ms"], 25.0, 0, "MEDIDO"))
    linhas.append(_linha("fil_subida", "lâmpada: subida de 10 a 90%", "ms", 50.0, fa["filamento_subida_ms"], fd["filamento_subida_ms"], 30.0, 0, "ESTIMADO 20-80"))
    linhas.append(_linha("fil_descida", "lâmpada: descida de 90 a 10%", "ms", 60.0, fa["filamento_descida_ms"], fd["filamento_descida_ms"], 40.0, 0, "ESTIMADO 20-100"))
    linhas.append(_linha("piscada_ms", "pilha fraca: maior abertura do contato (brilho < 50%)", "ms", 30.0, fa["piscada_abertura_ms"], fd["piscada_abertura_ms"], 30.0, 0, "ESTIMADO ms"))
    derivado = fd.get("pendulo_derivado")
    periodo_fisico = 2 * math.pi * math.sqrt(derivado["length_roll"] / maos.G) if derivado else NAN
    linhas.append(_linha("pendulo_T", "chaveiro: período, 2 pi raiz(L/g) do pêndulo composto da malha", "s", periodo_fisico, fa["pendulo_periodo"], fd["pendulo_periodo"], 0.03, 3, "DERIVADO"))
    linhas.append(_linha("pendulo_zeta", "chaveiro: razão de amortecimento", "", 0.08, fa["pendulo_zeta"], fd["pendulo_zeta"], 0.03, 3, "ESTIMADO 0,03-0,15"))
    ta, td = antes["troca"], depois["troca"]
    linhas.append(_linha("troca_dur", "troca de pilhas: duração", "s", NAN, ta["duracao"], td["duracao"], 2.2, 2, "decisão"))
    linhas.append(_linha("troca_defasagem", "troca de pilhas: defasagem de início das duas mãos", "ms", 1000 * ref["bimanual"]["defasagem_mediana"],
                         1000 * ta["defasagem_inicio"], 1000 * td["defasagem_inicio"], 100.0, 0, "MEDIDO"))
    linhas.append(_linha("troca_folga", "troca de pilhas: palma esquerda a pelo menos 12 mm do corpo da lanterna", "mm", 12.0,
                         antes["folga_troca_mm"], depois["folga_troca_mm"], 1e9, 1, "geometria"))
    linhas[-1].ok = bool(depois["folga_troca_mm"] >= 12.0)
    linhas.append(_linha("polegar_aberta", "mão aberta: ângulo do polegar ao eixo dos dedos", "graus", 35.0, fa["polegar_aberta"], fd["polegar_aberta"], 12.0, 0, "ESTIMADO 30-40"))
    linhas.append(_linha("polegar_concha", "mão em concha: ângulo do polegar ao eixo dos dedos", "graus", 35.0, fa["polegar_concha"], fd["polegar_concha"], 12.0, 0, "ESTIMADO 30-40"))
    linhas.append(_linha("cascata", "dedo fechando: atraso da junta da ponta em relação à da base", "ms", 50.0, antes["dedos"]["cascata_ms"],
                         depois["dedos"]["cascata_ms"], 30.0, 0, "ESTIMADO"))
    return linhas


def texto_da_tabela(linhas):
    cab = f"{'métrica [fonte]':92s} {'unid.':8s} {'real':>8s} {'antes':>8s} {'depois':>8s} {'tol.':>7s}  estado"
    saida = [cab, "-" * len(cab)]
    for l in linhas:
        def fmt(x):
            return "--" if x is None or not np.isfinite(x) else f"{x:.{l.casas}f}"
        estado = "--" if l.ok is None else ("dentro" if l.ok else "FORA")
        tol = "--" if l.tolerancia > 1e8 else fmt(l.tolerancia)
        saida.append(f"{l.rotulo:92s} {l.unidade:8s} {fmt(l.real):>8s} {fmt(l.antes):>8s} {fmt(l.jogo):>8s} {tol:>7s}  {estado}")
    return "\n".join(saida)


def figuras(pasta, antes, depois, ref):
    from tools.movimento_ref import graficos
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(pasta, exist_ok=True)
    arquivos = {}
    # 1. perfis de velocidade dos alcances, antes x depois x jerk mínimo
    figura, eixos = plt.subplots(2, 3, figsize=(15, 7.2), sharey=False)
    for ax, nome in zip(eixos.flat, GESTOS_PEGAR):
        for rotulo, dados, cor in (("antes", antes, "#9a9a95"), ("depois", depois, graficos.COR_JOGO)):
            g = dados["gestos"].get(nome, {})
            if "perfil" in g:
                v = np.array(g["perfil"])
                ax.plot((np.arange(len(v)) + 0.5) / len(v) * 100, v, color=cor, linewidth=2.0, label=f"jogo {rotulo}")
        d = depois["gestos"].get(nome, {})
        if "perfil" in d:
            modelo = metricas.jerk_minimo(d["distancia"], d["t6"], 200.0)
            ax.plot((np.arange(len(modelo)) + 0.5) / len(modelo) * 100, modelo, color=graficos.COR_REAL, linewidth=1.6, linestyle=(0, (4, 3)),
                    label="jerk mínimo (D e T do jogo)")
        ax.set_title(nome, loc="left")
        ax.set_xlabel("% da duração do alcance")
        ax.set_ylabel("m/s")
        ax.legend(loc="upper right", fontsize=8)
    figura.suptitle("Perfil de velocidade do punho no alcance: jogo antes e depois contra o jerk mínimo (pico a 50%; real: 49 +- 6%)", x=0.01, ha="left")
    figura.tight_layout()
    arquivos["perfis"] = os.path.join(pasta, "alcance_perfis.png")
    figura.savefig(arquivos["perfis"], dpi=110)
    plt.close(figura)
    # 2. pêndulo do chaveiro: engine antes, depois e o corpo rígido integrado à parte
    fa, fd = antes["fisica"], depois["fisica"]
    figura, ax = plt.subplots(figsize=(8.5, 3.6))
    passo = 6.0 / 60.0
    for rotulo, f, cor in (("antes (L fixo 0,11 m, zeta 0,13)", fa, "#9a9a95"), ("depois (pêndulo composto da malha, zeta 0,08)", fd, graficos.COR_JOGO)):
        y = np.array(f["pendulo_trilha"])
        ax.plot(np.arange(len(y)) * passo, np.degrees(y), color=cor, linewidth=2, label=rotulo)
    info = fd.get("pendulo_derivado")
    if info:
        t, theta = maos.pendulo_independente(info["inertia_roll"], info["mass"], info["d"], 0.08, 0.2)
        ax.plot(t, np.degrees(theta), color=graficos.COR_REAL, linewidth=1.3, linestyle=(0, (4, 3)), label="corpo rígido, RK4 independente")
    ax.set_xlabel("segundos"); ax.set_ylabel("graus"); ax.set_title("Chaveiro solto a 11,5 graus: período e amortecimento", loc="left")
    ax.legend(loc="upper right", fontsize=8)
    figura.tight_layout()
    arquivos["pendulo"] = os.path.join(pasta, "chaveiro_pendulo.png")
    figura.savefig(arquivos["pendulo"], dpi=110)
    plt.close(figura)
    return arquivos


def montar_tabela(pasta, antes, depois):
    from tools.movimento_ref import graficos
    ref = maos.referencia()
    linhas = montar_linhas(antes, depois, ref)
    os.makedirs(pasta, exist_ok=True)
    texto = texto_da_tabela(linhas)
    with open(os.path.join(pasta, "tabela.txt"), "w", encoding="utf-8") as arquivo:
        arquivo.write("Mãos, itens e lanterna: real (CMU) ou lei física x jogo antes x jogo depois\n"
                      "estado = o 'depois' dentro da tolerância do real\n\n" + texto + "\n")
    registro = [dict(chave=l.chave, rotulo=l.rotulo, unidade=l.unidade, real=l.real, antes=l.antes, depois=l.jogo, tolerancia=l.tolerancia,
                     ok=l.ok) for l in linhas]
    with open(os.path.join(pasta, "tabela.json"), "w", encoding="utf-8") as arquivo:
        json.dump(registro, arquivo, ensure_ascii=False, indent=1, default=float)
    arquivos = figuras(pasta, antes, depois, ref)
    try:
        arquivos["tabela"] = graficos.painel_tabela(linhas, os.path.join(pasta, "tabela.png"), titulo="Mãos, itens e lanterna (antes e depois no texto)",
                                                    rotulo_real="real/lei", rotulo_jogo="depois")
    except Exception as erro:       # noqa: BLE001
        print("tabela.png não gerada:", erro)
    print(texto)
    return linhas, arquivos


def principal(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    m = sub.add_parser("medir")
    m.add_argument("saida")
    t = sub.add_parser("tabela")
    t.add_argument("pasta")
    t.add_argument("--antes", required=True)
    t.add_argument("--depois", required=True)
    args = ap.parse_args(argv)
    if args.comando == "medir":
        dados = medir_tudo()
        os.makedirs(os.path.dirname(os.path.abspath(args.saida)), exist_ok=True)
        with open(args.saida, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=1, default=float)
        print("medido:", args.saida)
    else:
        with open(args.antes, encoding="utf-8") as a, open(args.depois, encoding="utf-8") as d:
            montar_tabela(args.pasta, json.load(a), json.load(d))


if __name__ == "__main__":
    principal()
