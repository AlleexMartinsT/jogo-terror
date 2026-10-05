"""Testes da locomoção do jogador contra o mocap da CMU: velocidades, passada, apoios, ângulos, cabeça, passos e escada.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_locomocao.py            # tudo (o gravador monta um palco: ~1 min; a escada abre a casa)
    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_locomocao.py --rapido    # sem a escada (não abre a casa)
    python tests/test_locomocao.py --puro                              # só o que não precisa de bpy

A referência é `assets/referencia/marcha_ref.json` (gerado por `python -m tools.marcha.extrair` a partir dos BVH da CMU:
o teste não baixa nada). As métricas e as tolerâncias são as de `tools.movimento_ref.metricas.CAMPOS_MARCHA`, que são um
desvio-padrão ENTRE PESSOAS REAIS; onde o jogo precisa de outra regra, ela está em CONHECIDOS com o motivo:

    um pé apoiado mais firme que o mocap não é defeito     deslize_apoio e deslize_vel_p95 valem só para cima
    velocidade, passada e passo da corrida                 4,0 m/s está acima de qualquer corrida do conjunto (até 3,8 m/s)
    altura do quadril                                      a raiz Hips do mocap fica ~9 cm acima das juntas do quadril;
                                                           compara-se a razão da JUNTA do quadril pela perna
    agachado                                               o jogo agacha até a vista a 1,05 m; o mocap só dobra os joelhos
"""
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import numpy as np  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import gait  # noqa: E402
from sem_alvorada import gait_data as D  # noqa: E402

REFERENCIA = os.path.join(ROOT, "assets", "referencia", "marcha_ref.json")
with open(REFERENCIA, encoding="utf-8") as _arquivo:
    REF = json.load(_arquivo)

UNILATERAL = ("deslize_apoio", "deslize_vel_p95")       # só passam do real para cima
JUNTA_QUADRIL = "razao_quadril"                          # altura da junta do quadril / (perna + tornozelo), 1,0 = perna esticada

# por cenário: {métrica: (maior |jogo - real| aceito, motivo)}. Fora desta lista vale a tolerância de CAMPOS_MARCHA.
CONHECIDOS = {
    "andar": {},
    "andar_normal": {
        "apoio_pct": (6.0, "o jogo apoia 5 pontos de % a mais a 1,3 m/s (interpola andar lento e rápido)"),
        "duplo_apoio_passo_pct": (5.5, "idem"), "duplo_apoio_ciclo_pct": (10.5, "idem"),
        "quadril_altura": (0.08, "raiz Hips x junta"),
        "cabeca_w_inclinacao_rms": (6.5, "a trepidação por passada da cabeça de pessoas reais não está nas curvas médias"),
    },
    "andar_devagar": {
        "passada": (0.16, "passo curto: a lei do passo extrapola abaixo do nó mais lento"),
        "apoio_pct": (5.5, "o jogo apoia 4 pontos de % a mais a 0,95 m/s"), "duplo_apoio_passo_pct": (5.5, "idem"),
        "duplo_apoio_ciclo_pct": (10.0, "idem"), "quadril_altura": (0.08, "raiz Hips x junta"),
        "joelho_apoio_max": (11.5, "joelho dobra 9 graus a mais no apoio a 0,95 m/s"),
        "cabeca_w_inclinacao_rms": (6.0, "trepidação por passada"),
    },
    "correr": {
        "velocidade": (0.8, "4,0 m/s: acima de qualquer corrida do conjunto"),
        "passada": (0.55, "a passada cresce com a velocidade (lei do passo da corrida)"),
        "passo": (0.27, "idem"),
        "deslize_apoio": (0.11, "ponta do pé e bola andam 6 a 9 cm enquanto a sola rola (a tabela mede o tornozelo)"),
        "quadril_altura": (0.14, "raiz Hips x junta"),
        "quadril_min": (12.5, "o passo de 4,0 m/s é 13% maior que o das corridas medidas, e a extensão do quadril cresce com ele"),
    },
    "agachado": {
        "quadril_altura": (0.5, "profundidade: o jogo agacha até a vista a 1,05 m"),
        "joelho_apoio_max": (65.0, "idem"), "joelho_balanco_max": (60.0, "idem"),
        "quadril_min": (30.0, "idem"), "quadril_max": (40.0, "idem"),
        "tornozelo_min": (50.0, "idem"), "tornozelo_max": (50.0, "idem"),
        "tronco_inclinacao": (10.0, "idem"),
        "cabeca_w_rms": (9.0, "com 2 clipes de uma pessoa, a trepidação da cabeça não está nas curvas médias"),
        "cabeca_w_p95": (25.0, "idem"), "cabeca_w_inclinacao_rms": (5.5, "idem"),
    },
}
# métricas que só dizem respeito à profundidade do agachado e ficam de fora do agachado
SO_PROFUNDIDADE = ("quadril_altura", "joelho_apoio_max", "joelho_balanco_max", "quadril_min", "quadril_max", "tornozelo_min",
                   "tornozelo_max", "tronco_inclinacao")


def media_real(faixa, chave):
    return REF["faixas"][faixa]["resumo"][chave]["media"]


# --------------------------------------------------------------------------
# Puro: velocidades, lei do passo, tabelas
# --------------------------------------------------------------------------
def teste_velocidades_humanas():
    """Andar 1,7 a 1,9 m/s, correr 3,8 a 4,2 m/s, agachado 0,8 a 1,0 m/s; escada pelos degraus; passo de andar < correr."""
    assert 1.7 <= C.SPEED_WALK <= 1.9 and 3.8 <= C.SPEED_RUN <= 4.2 and 0.8 <= C.SPEED_CROUCH <= 1.0
    assert C.SPEED_CROUCH < C.SPEED_WALK < C.SPEED_RUN
    from sem_alvorada import layout
    for modo, velocidade in (("walk", C.SPEED_WALK), ("run", C.SPEED_RUN), ("crouch", C.SPEED_CROUCH)):
        na_escada = C.STAIRS_STEPS_PER_SECOND[modo] * layout.STAIRS.tread_depth
        assert na_escada < velocidade, (modo, na_escada)
    assert abs(C.stairs_speed(C.SPEED_WALK) - C.STAIRS_RATIO_WALK * C.SPEED_WALK) < 1e-6
    assert abs(C.stairs_speed(C.SPEED_RUN) - C.STAIRS_RATIO_RUN * C.SPEED_RUN) < 0.05
    return f"andar {C.SPEED_WALK}, correr {C.SPEED_RUN}, agachado {C.SPEED_CROUCH} m/s"


def teste_entidade_escalada_na_mesma_proporcao():
    """A entidade mantém as razões de antes (patrulha 0,58, espreita 0,35 e perseguição 0,89 de andar, andar e correr)."""
    razoes = {"patrulha / andar": (C.ENTITY_SPEED_PATROL / C.SPEED_WALK, 1.5 / 2.6),
              "espreita / andar": (C.ENTITY_SPEED_STALK / C.SPEED_WALK, 0.9 / 2.6),
              "perseguição / correr": (C.ENTITY_SPEED_CHASE / C.SPEED_RUN, 4.1 / 4.6)}
    for nome, (agora, antes) in razoes.items():
        assert abs(agora - antes) < 0.015 * max(antes, 1.0), (nome, agora, antes)
    from sem_alvorada.ai import brain, tuning
    assert brain.MAX_CHASE_SPEED <= C.SPEED_RUN, "a perseguição no nível máximo não passa da corrida do jogador"
    assert tuning.BrainTuning().stalk_quiet_speed < C.SPEED_WALK
    return ", ".join(f"{n} {a:.3f}" for n, (a, _) in razoes.items())


def teste_referencia_e_tabelas_coerentes():
    """O JSON de referência e as tabelas do jogo vêm do mesmo extrator: as cinco faixas existem e as velocidades dos nós batem."""
    for faixa in ("andar_lento", "andar", "andar_rapido", "correr", "agachado"):
        assert faixa in REF["faixas"] and REF["faixas"][faixa]["resumo"]["velocidade"]["n"] >= 2, faixa
    for modo, nos in D.NOS.items():
        assert nos and all(len(n["curvas"]["cab_z"]) == D.PONTOS for n in nos), modo
    pares = (("walk", 0, "andar_lento"), ("walk", 1, "andar"), ("walk", 2, "andar_rapido"), ("run", 0, "correr"), ("crouch", 0, "agachado"))
    for modo, i, faixa in pares:
        no = D.NOS[modo][i]
        v_no = no.get("velocidade", no.get("v"))
        v_ref = REF["faixas"][faixa]["resumo"]["velocidade"]
        assert abs(v_no - v_ref["mediana"]) < 0.08 * v_ref["mediana"], (faixa, v_no, v_ref)
    return "5 faixas, nós e referência na mesma velocidade"


def teste_lei_do_passo_segue_o_mocap():
    """Cadência e passo da lei do jogo ficam a 6% de cada faixa do mocap (nos nós) e crescem com a velocidade."""
    for faixa, velocidade, crouch in (("andar_lento", None, 0.0), ("andar", None, 0.0), ("andar_rapido", None, 0.0), ("correr", None, 0.0)):
        v = media_real(faixa, "velocidade")
        pesos = gait.mode_weights(v, crouch)
        passo = gait.step_length(v, pesos)
        cadencia = v / passo * 60.0
        assert abs(passo - media_real(faixa, "passo")) < 0.06 * media_real(faixa, "passo"), (faixa, passo)
        assert abs(cadencia - media_real(faixa, "cadencia")) < 0.06 * media_real(faixa, "cadencia"), (faixa, cadencia)
    passos = [gait.step_length(v, gait.mode_weights(v, 0.0)) for v in np.linspace(0.5, 4.2, 40)]
    assert all(b >= a - 1e-9 for a, b in zip(passos, passos[1:])), "o passo nunca diminui com a velocidade"
    cadencia_andar = C.SPEED_WALK / gait.step_length(C.SPEED_WALK, gait.mode_weights(C.SPEED_WALK, 0.0)) * 60.0
    cadencia_correr = C.SPEED_RUN / gait.step_length(C.SPEED_RUN, gait.mode_weights(C.SPEED_RUN, 0.0)) * 60.0
    assert 110 <= cadencia_andar <= 135 and 150 <= cadencia_correr <= 180, (cadencia_andar, cadencia_correr)
    return f"andar {cadencia_andar:.0f} passos/min, correr {cadencia_correr:.0f}"


def teste_tabelas_simetricas_e_toque_em_zero():
    """A fase 0 é o toque do calcanhar esquerdo e o direito é o esquerdo meio ciclo depois; os pés são periódicos."""
    for velocidade, crouch in ((1.0, 0.0), (1.7, 0.0), (4.0, 0.0), (0.8, 1.0)):
        a = gait.evaluate(0.13, velocidade, crouch)
        b = gait.evaluate(0.13 + 0.5, velocidade, crouch)
        for chave in ("pe_frente", "pe_alt", "pe"):
            assert abs(a.values[chave] - b.other[chave]) < 1e-6, (velocidade, chave)
        periodico = gait.evaluate(1.13, velocidade, crouch)
        assert abs(periodico.values["pe_frente"] - a.values["pe_frente"]) < 1e-6
    toque = gait.evaluate(0.0, C.SPEED_WALK)
    meio = gait.evaluate(0.15, C.SPEED_WALK)
    assert toque.values["pe_frente"] > meio.values["pe_frente"], "no toque o pé esquerdo está à frente do quadril"
    return "simétricas, periódicas, toque em c = 0"


# --------------------------------------------------------------------------
# Gravador: roteiros no jogo (palco mínimo)
# --------------------------------------------------------------------------
class Banco:
    """Cada roteiro roda uma vez, num palco novo, e fica guardado."""
    gravacoes = {}

    @classmethod
    def gravar(cls, nome, roteiro, ossos="armadura"):
        from tools.movimento_ref import grava
        if nome not in cls.gravacoes:
            jogo = grava.montar_jogo(palco=True)
            cls.gravacoes[nome] = grava.gravar(jogo, roteiro, nome=nome, ossos=ossos, prefacio=0.3)
        return cls.gravacoes[nome]

    @classmethod
    def andar(cls):
        from tools.movimento_ref import grava
        return cls.gravar("andar", [grava.andar(9)])

    @classmethod
    def devagar(cls):
        from tools.movimento_ref import grava
        return cls.gravar("devagar", [grava.Passo(10, mover=0.55, rotulo="andar")])

    @classmethod
    def normal(cls):
        from tools.movimento_ref import grava
        return cls.gravar("normal", [grava.Passo(9, mover=0.78, rotulo="andar")])

    @classmethod
    def correr(cls):
        from tools.movimento_ref import grava
        return cls.gravar("correr", [grava.correr(4)])

    @classmethod
    def agachado(cls):
        from tools.movimento_ref import grava
        return cls.gravar("agachado", [grava.agachar(1.0), grava.andar_agachado(10)])


def medir(rec, passo, metodo, margem):
    from tools.movimento_ref import metricas
    mov = rec.movimento_do_passo(passo, margem=margem)
    return mov, metricas.medir_tudo(mov, metodo)


def comparar(cenario, faixa, v, mov):
    """Lista de falhas de `v` (escalares do jogo) contra a faixa de referência, com as exceções de CONHECIDOS."""
    from tools.marcha import extrair
    from tools.movimento_ref import metricas
    conhecidos = CONHECIDOS[cenario]
    falhas = []
    for chave, (rotulo, unidade, casas, tipo, valor) in metricas.CAMPOS_MARCHA.items():
        real = REF["faixas"][faixa]["resumo"].get(chave, {}).get("media", float("nan"))
        jogo = v.get(chave, float("nan"))
        if not (np.isfinite(real) and np.isfinite(jogo)):
            continue
        if cenario == "agachado" and chave in SO_PROFUNDIDADE and chave not in conhecidos:
            continue
        tolerancia = abs(real) * valor if tipo == "rel" else valor
        dif = jogo - real
        if chave in conhecidos:
            limite = conhecidos[chave][0]
            if abs(dif) > limite:
                falhas.append(f"{rotulo}: jogo {jogo:.3f}, real {real:.3f}, dif {dif:+.3f} passa do limite conhecido {limite}")
            continue
        ok = dif <= tolerancia if chave in UNILATERAL else abs(dif) <= tolerancia
        if not ok:
            falhas.append(f"{rotulo}: jogo {jogo:.3f}, real {real:.3f}, dif {dif:+.3f}, tolerância {tolerancia:.3f}")
    razao_jogo = extrair.razao_quadril(mov)
    razao_real = media_real(faixa, JUNTA_QUADRIL)
    if cenario != "agachado" and abs(razao_jogo - razao_real) > 0.03:
        falhas.append(f"altura da junta do quadril / perna: jogo {razao_jogo:.3f}, real {razao_real:.3f}")
    return falhas


def teste_andar_contra_caminhadas_rapidas():
    """1,7 m/s contra as caminhadas de 1,55 a 1,80 m/s: as 30 métricas de marcha dentro da tolerância."""
    mov, marcha = medir(Banco.andar(), 0, "zeni", 0.7)
    falhas = comparar("andar", "andar_rapido", marcha.v, mov)
    assert not falhas, "\n    " + "\n    ".join(falhas)
    return f"{marcha.v['velocidade']:.2f} m/s, {marcha.v['cadencia']:.0f} passos/min, passo {marcha.v['passo']:.2f} m"


def teste_andar_normal_e_devagar():
    """Meia entrada e 55%: dentro da tolerância, menos o que está em CONHECIDOS."""
    saida = []
    for nome, rec, faixa in (("andar_normal", Banco.normal(), "andar"), ("andar_devagar", Banco.devagar(), "andar_lento")):
        mov, marcha = medir(rec, 0, "zeni", 0.7)
        falhas = comparar(nome, faixa, marcha.v, mov)
        assert not falhas, f"{nome}:\n    " + "\n    ".join(falhas)
        saida.append(f"{nome} {marcha.v['velocidade']:.2f} m/s")
    return ", ".join(saida)


def teste_correr_contra_corridas():
    """4,0 m/s: cadência, apoio, voo, oscilação da cabeça e os ângulos das juntas ficam na faixa do mocap."""
    mov, marcha = medir(Banco.correr(), 0, "altura", 1.0)
    falhas = comparar("correr", "correr", marcha.v, mov)
    assert not falhas, "\n    " + "\n    ".join(falhas)
    assert abs(marcha.v["velocidade"] - C.SPEED_RUN) < 0.12 * C.SPEED_RUN, marcha.v["velocidade"]
    assert marcha.v["voo_pct"] > 25.0, "há fase de voo na corrida"
    return f"{marcha.v['velocidade']:.2f} m/s, {marcha.v['cadencia']:.0f} passos/min, voo {marcha.v['voo_pct']:.0f}%"


def teste_agachado_no_ritmo_do_mocap():
    """Ritmo, apoio, oscilação e braços do agachado batem com 136_09 e 136_10; a profundidade é outra (ver o cabeçalho)."""
    mov, marcha = medir(Banco.agachado(), 1, "zeni", 0.7)
    falhas = comparar("agachado", "agachado", marcha.v, mov)
    assert not falhas, "\n    " + "\n    ".join(falhas)
    assert 0.7 <= marcha.v["velocidade"] <= 1.0
    return f"{marcha.v['velocidade']:.2f} m/s, {marcha.v['cadencia']:.0f} passos/min, apoio {marcha.v['apoio_pct']:.0f}%"


def teste_cabeca_em_fase_com_o_corpo():
    """O ponto mais baixo da cabeça cai no duplo apoio, 0,18 do passo (andar) e 0,26 (correr) depois do toque do calcanhar
    (MEDIDO em 10 caminhadas e 24 corridas, dispersão entre clipes 0,03), e a cabeça oscila na frequência dos passos."""
    from tools.movimento_ref import metricas
    esperado = {"andar": (Banco.andar(), 0, "zeni", 0.7, 0.18), "correr": (Banco.correr(), 0, "altura", 1.0, 0.26)}
    relato = []
    for nome, (rec, passo, metodo, margem, fase_real) in esperado.items():
        mov = rec.movimento_do_passo(passo, margem=margem)
        eventos = metricas.eventos_marcha(mov, metodo)
        altura = mov.cabeca_pos()[:, 2]
        fases, _ = metricas.fases_do_ponto_baixo_por_passo(altura, eventos)
        fase = float(np.angle(np.exp(2j * np.pi * fases).mean()) / (2 * np.pi) % 1.0)
        assert abs(fase - fase_real) <= 0.08, f"{nome}: cabeça e pés fora de fase: ponto baixo em {fase:.2f} do passo, real {fase_real}"
        cadencia = metricas.medir_marcha(mov, metodo).v["cadencia"]
        f_cabeca = metricas.frequencia_dominante(altura, mov.fps, 1.0, 6.0)
        assert abs(f_cabeca - cadencia / 60.0) < 0.08 * cadencia / 60.0, (nome, f_cabeca, cadencia / 60.0)
        if nome == "andar":
            no_duplo = metricas.cabeca_baixa_no_duplo_apoio(altura, eventos)
            assert no_duplo >= 0.9, f"a cabeça deve estar mais baixa no duplo apoio: {no_duplo}"
        relato.append(f"{nome} {fase:.2f}")
    return "ponto baixo da cabeça no passo: " + ", ".join(relato)


def teste_passos_no_toque_do_calcanhar():
    """Cada som de passo cai no toque do calcanhar da animação (a 3 quadros), no mesmo número e na mesma ordem; nenhum parado."""
    from tools.movimento_ref import metricas
    relato = []
    for nome, rec, metodo, passo in (("andar", Banco.andar(), "zeni", 0), ("correr", Banco.correr(), "altura", 0)):
        inicio, fim, _ = rec.passos[passo]
        mov = rec.movimento_do_passo(passo, margem=0.0)
        eventos = metricas.eventos_marcha(mov, metodo)
        toques = np.sort(np.concatenate([eventos.tempos("toque", "e"), eventos.tempos("toque", "d")])) + inicio
        sons = np.array([e[0] for e in rec.eventos if e[1] == "ruido" and e[3] in ("walk", "run", "crouch") and inicio < e[0] <= fim])
        sons = sons[sons > inicio + 0.7]
        toques = toques[toques > inicio + 0.7]
        assert len(sons) >= 4, (nome, len(sons))
        erros = [float(np.min(np.abs(toques - s))) for s in sons[:-1]]
        limite = 3.5 / rec.fps if nome == "andar" else 4.5 / rec.fps
        assert max(erros) <= limite, f"{nome}: som de passo a {max(erros) * 1000:.0f} ms do toque (limite {limite * 1000:.0f})"
        assert abs(len(sons) - len(toques)) <= 2, (nome, len(sons), len(toques))
        relato.append(f"{nome}: {len(sons)} sons, erro máximo {max(erros) * 1000:.0f} ms")
    parado = Banco.gravar("parado", [__import__("tools.movimento_ref.grava", fromlist=["x"]).parar(3.0)])
    assert not [e for e in parado.eventos if e[1] == "ruido" and e[3] in ("walk", "run", "crouch")], "parado não faz som de passo"
    return "; ".join(relato)


def teste_parar_e_arrancar():
    """Soltar a tecla leva 0,4 a 1,0 s (90% a 10% da velocidade), andando ou correndo; sem velocidade negativa; arrancar
    chega a 90% em 0,25 a 0,8 s (143_03 mede 0,68 s até 4,9 m/s; 16_33 para de 0,9 m/s em 0,7 s)."""
    from tools.movimento_ref import grava
    relato = []
    for nome, roteiro, antes in (("parar_andando", [grava.andar(3), grava.parar(2)], 3.0),
                                 ("parar_correndo", [grava.correr(3), grava.parar(2)], 3.0)):
        rec = Banco.gravar(nome, roteiro, ossos="nenhum")
        v = rec.jogador["velocidade"]
        t = rec.t
        cruzeiro = float(v[int((antes - 0.3) * rec.fps)])
        i0 = int(round(antes * rec.fps))
        a = i0 + int(np.argmax(v[i0:] < 0.9 * cruzeiro))
        b = i0 + int(np.argmax(v[i0:] < 0.1 * cruzeiro))
        duracao = float(t[b] - t[a])
        assert 0.4 <= duracao <= 1.0, f"{nome}: freada de {duracao:.2f} s"
        assert v.min() >= -1e-6
        relato.append(f"{nome} {duracao:.2f} s")
    rec = Banco.gravar("arrancar", [grava.parar(0.5), grava.andar(3)], ossos="nenhum")
    v = rec.jogador["velocidade"]
    t = rec.t
    i0 = int(round(0.5 * rec.fps))
    cruzeiro = float(v[-1])
    chegou = i0 + int(np.argmax(v[i0:] >= 0.9 * cruzeiro))
    subida = float(t[chegou] - t[i0])
    assert 0.25 <= subida <= 0.8, f"arrancada de {subida:.2f} s"
    relato.append(f"arrancar {subida:.2f} s")
    return ", ".join(relato)


def teste_inclinar_para_dentro_da_curva():
    """Virando à esquerda andando, a câmera rola para a esquerda (como 16_17: 3,1 graus), nunca mais que 7 graus (5 de inclinação + 1 de passada); virando à
    direita, para a direita; parado olhando em volta, nada."""
    from tools.movimento_ref import grava
    de_esquerda = Banco.gravar("curva_e", [grava.andar(2), grava.virar(90, 1.0), grava.andar(1)], ossos="nenhum")
    de_direita = Banco.gravar("curva_d", [grava.andar(2), grava.virar(-90, 1.0), grava.andar(1)], ossos="nenhum")
    parado = Banco.gravar("olhar", [grava.parar(1), grava.virar(90, 0.5, andando=False), grava.parar(1)], ossos="nenhum")

    def rolagem(rec):
        direita = rec.camera_rot[:, :, 0]               # eixo "direita" da câmera
        return np.degrees(np.arcsin(np.clip(direita[:, 2], -1, 1)))
    e, d, p = rolagem(de_esquerda), rolagem(de_direita), rolagem(parado)
    assert 1.5 <= e.max() <= 7.0 and -7.0 <= d.min() <= -1.5, (e.max(), d.min())      # 5 graus de inclinação + 1 da passada
    assert np.abs(p).max() < 0.4, f"parado e girando não inclina: {np.abs(p).max():.2f}"
    return f"esquerda +{e.max():.1f} graus, direita {d.min():.1f}, parado {np.abs(p).max():.2f}"


def teste_corpo_acompanha_o_olhar():
    """Girando a cabeça parado, a pelve vai atrás com 0,03 a 0,25 s de atraso (77_01, 139_26 e 77_05: 0,07 a 0,17 s) e o corpo
    não fica mais de 75 graus para trás (nesses clipes a cabeça passa de 60 a 100 graus sobre a pelve)."""
    from tools.movimento_ref import grava, metricas
    rec = Banco.gravar("olhar_em_volta", [grava.parar(1.0), grava.virar(120, 0.5, andando=False), grava.parar(1.0),
                                          grava.virar(-120, 0.5, andando=False), grava.parar(1.0)])
    mov = rec.movimento()
    fps = mov.fps

    def guinada(vetores):
        return np.degrees(np.unwrap(np.arctan2(vetores[:, 1], vetores[:, 0])))
    coxas = mov.j("coxa_d") - mov.j("coxa_e")
    pelve = guinada(np.stack([-coxas[:, 1], coxas[:, 0]], axis=1))
    olhar = mov.cabeca_rot @ np.array([0.0, 0.0, -1.0])
    cabeca = guinada(olhar[:, :2])
    dif = cabeca - pelve - np.median((cabeca - pelve)[:30])
    vc = np.gradient(metricas.gaussiano(cabeca, 0.05, fps))
    vp = np.gradient(metricas.gaussiano(pelve, 0.05, fps))
    lags = np.arange(0, int(0.6 * fps))
    corr = [np.dot(vc[:len(vc) - l], vp[l:]) for l in lags]
    atraso = float(lags[int(np.argmax(corr))] / fps)
    assert 0.03 <= atraso <= 0.25, f"a pelve atrasa {atraso:.2f} s"
    assert np.abs(dif).max() <= 75.0, f"o corpo fica {np.abs(dif).max():.0f} graus atrás do olhar"
    return f"pelve atrasa {atraso:.2f} s, no máximo {np.abs(dif).max():.0f} graus atrás"


def teste_agachar_e_levantar():
    """A vista desce (e volta) em 0,25 a 0,50 s de 10% a 90% do caminho, como em 136_09 (0,35 s), sem passar do alvo."""
    from tools.movimento_ref import grava
    rec = Banco.gravar("agachar", [grava.parar(0.5), grava.agachar(2.0), grava.parar(2.0)], ossos="nenhum")
    olho, t = rec.jogador["olho"], rec.t
    alto, baixo = float(olho[0]), float(olho.min())
    assert abs(alto - C.PLAYER_EYE_STAND) < 0.01 and abs(baixo - C.PLAYER_EYE_CROUCH) < 0.03, (alto, baixo)
    meio = int(np.argmin(olho))

    def tempo(a, b, nivel):
        alvo = alto + nivel * (baixo - alto)
        alvo_antes = np.argmax(olho[a:b] <= alvo) if baixo < alto else np.argmax(olho[a:b] >= alvo)
        return float(t[a + alvo_antes])
    descida = tempo(0, meio + 1, 0.9) - tempo(0, meio + 1, 0.1)
    # subida: do fundo de volta a 10% e 90% da altura em pé
    fundo_ate_fim = olho[meio:]
    t10 = t[meio + int(np.argmax(fundo_ate_fim >= baixo + 0.1 * (alto - baixo)))]
    t90 = t[meio + int(np.argmax(fundo_ate_fim >= baixo + 0.9 * (alto - baixo)))]
    subida = float(t90 - t10)
    assert 0.25 <= descida <= 0.5 and 0.25 <= subida <= 0.5, (descida, subida)
    assert olho.max() <= C.PLAYER_EYE_STAND + 0.005 and olho.min() >= C.PLAYER_EYE_CROUCH - 0.005, "sem passar do alvo"
    return f"descer {descida:.2f} s, levantar {subida:.2f} s"


def teste_respiracao_parado():
    """Parado a cabeça sobe e desce na respiração de repouso (0,25 Hz, 2 mm de amplitude, MEDIDO em 6 clipes parados) e
    balança de lado menos de 1 cm; nada disso passa de 1 cm na vertical."""
    from tools.movimento_ref import grava, metricas
    rec = Banco.gravar("respirar", [grava.parar(14)], ossos="nenhum")
    vertical = rec.jogador["bob_vertical"][int(2 * rec.fps):]
    lateral = rec.jogador["bob_lateral"][int(2 * rec.fps):]
    f = metricas.frequencia_dominante(vertical, rec.fps, 0.1, 1.0)
    assert abs(f - 0.25) <= 0.06, f"respiração a {f:.2f} Hz"
    assert 0.0015 <= np.ptp(vertical) <= 0.01, np.ptp(vertical)
    assert np.ptp(lateral) < 0.02, np.ptp(lateral)
    return f"{f:.2f} Hz, {1000 * np.ptp(vertical):.1f} mm pico a pico na vertical, {1000 * np.ptp(lateral):.1f} mm de lado"


def teste_respiracao_ofegante():
    """Sem fôlego a respiração acelera de 0,25 para perto de 0,65 Hz (35 a 45 por minuto, ESTIMADO) e a cabeça sobe e desce
    mais; o fôlego volta e ela se acalma."""
    from tools.movimento_ref import grava
    jogo = grava.montar_jogo(palco=True)
    jogador = jogo.player
    for _ in range(int(4.3 * 60)):
        jogo.tick(grava.DT_JOGO, grava.InputState(move_y=1.0, run=True))
    assert jogador.breathing_hard, "depois de correr o fôlego está abaixo do limite"
    fase0 = jogador.breath_phase
    for _ in range(60):
        jogo.tick(grava.DT_JOGO, grava.InputState())
    frequencia = (jogador.breath_phase - fase0) / (2 * math.pi)
    assert 0.40 <= frequencia <= 0.70, f"respiração ofegante a {frequencia:.2f} Hz"
    mistura = jogador.breath_mix
    for _ in range(int(14 * 60)):
        jogo.tick(grava.DT_JOGO, grava.InputState())
    assert not jogador.breathing_hard and jogador.breath_mix < 0.2, (jogador.stamina, jogador.breath_mix)
    return f"{frequencia:.2f} Hz sem fôlego (mistura {mistura:.2f}), volta a {0.25:.2f} Hz com o fôlego"


def teste_cabeca_e_corpo_do_mesmo_ritmo_ao_acelerar():
    """Ao arrancar e parar a passada e a câmera andam juntas: a fase só avança quando o jogador anda (nada de pé deslizando
    parado) e a amplitude da cabeça cai a quase zero parado."""
    from tools.movimento_ref import grava
    rec = Banco.gravar("ritmo", [grava.andar(3), grava.parar(2)], ossos="nenhum")
    fase = rec.jogador["fase_passo"]
    v = rec.jogador["velocidade"]
    parado = np.nonzero(v < 0.02)[0]
    parado = parado[parado > int(3.8 * rec.fps)]
    assert len(parado) > 30
    assert np.ptp(fase[parado]) < 0.2, f"a fase anda {np.ptp(fase[parado]):.2f} rad com o jogador parado"
    vertical = rec.jogador["bob_vertical"]
    assert np.ptp(vertical[int(1 * rec.fps):int(3 * rec.fps)]) > 0.02, "andando a cabeça sobe e desce"
    assert np.ptp(vertical[parado]) < 0.008, "parada a cabeça só respira"
    return "a fase e a amplitude acompanham a velocidade"


# --------------------------------------------------------------------------
# Escada (abre a casa inteira)
# --------------------------------------------------------------------------
def teste_escada():
    """Subir os 15 degraus: ritmo de 1,3 a 1,7 passos/s, velocidade horizontal 0,3 a 0,6 m/s, a bola do pé nunca abaixo do
    degrau (a ponta, no máximo 6 cm), a cabeça sobe quase em rampa (oscilação de 5 a 10 cm, como 83_27 a 83_35)."""
    from sem_alvorada import layout
    from tools.movimento_ref import grava, metricas
    from tools.movimento_ref.cenarios import locomocao
    jogo = grava.montar_jogo(palco=False)

    def colocar(j):
        j.place_player(5.6, 2.0, 0.0, 0.0)
    rec = grava.gravar(jogo, [grava.Passo(10.0, mover=1.0, ao_iniciar=colocar, rotulo="escada")], nome="escada", ossos="armadura", prefacio=0.3)
    mov = rec.movimento(piso=0.0)
    valores, (a, b) = locomocao.medir_escada(mov)
    assert 1.3 <= valores["escada_passos_s"] <= 1.7, valores
    assert 0.3 <= valores["escada_vel_horiz"] <= 0.6, valores
    assert 0.05 <= valores["escada_osc_cabeca"] <= 0.10, valores
    z = rec.jogador["z"]
    subindo = np.nonzero((z > 0.3) & (z < 2.5))[0]
    degrau = {}
    for nome, junta, deslocamento in (("bola", "bola", 0.040), ("ponta", "ponta", 0.035)):
        penetracao = []
        for lado in "ed":
            p = mov.j(f"{junta}_{lado}")
            altura = np.array([layout.stairs_height(x, y) if layout.stairs_height(x, y) is not None else np.nan for x, y in p[:, :2]])
            penetracao.append((p[:, 2] - deslocamento) - altura)
        pior = float(np.nanmin(np.concatenate([x[subindo[0]:subindo[-1]] for x in penetracao])))
        degrau[nome] = pior
    assert degrau["bola"] >= -0.012, f"a bola do pé atravessa o degrau em {-100 * degrau['bola']:.1f} cm"
    assert degrau["ponta"] >= -0.06, f"a ponta do pé atravessa o espelho em {-100 * degrau['ponta']:.1f} cm"
    velocidade_na_escada = np.linalg.norm(np.diff(np.stack([rec.jogador["x"], rec.jogador["y"]], 1), axis=0), axis=1) * rec.fps
    teto = C.stairs_speed(C.SPEED_WALK)       # a entrada freia de 1,7 m/s ao ritmo dos degraus em ~0,7 s
    assert velocidade_na_escada[subindo[0] + int(rec.fps):subindo[-1] - 10].max() <= teto + 0.05, velocidade_na_escada.max()
    return (f"{valores['escada_passos_s']:.2f} passos/s, {valores['escada_vel_horiz']:.2f} m/s, cabeça {100 * valores['escada_osc_cabeca']:.1f} cm, "
            f"bola {100 * degrau['bola']:+.1f} cm, ponta {100 * degrau['ponta']:+.1f} cm do degrau")


GRUPOS = (("puro", [teste_velocidades_humanas, teste_entidade_escalada_na_mesma_proporcao, teste_referencia_e_tabelas_coerentes,
                    teste_lei_do_passo_segue_o_mocap, teste_tabelas_simetricas_e_toque_em_zero]),
          ("jogo", [teste_andar_contra_caminhadas_rapidas, teste_andar_normal_e_devagar, teste_correr_contra_corridas,
                    teste_agachado_no_ritmo_do_mocap, teste_cabeca_em_fase_com_o_corpo, teste_passos_no_toque_do_calcanhar,
                    teste_parar_e_arrancar, teste_inclinar_para_dentro_da_curva, teste_corpo_acompanha_o_olhar, teste_agachar_e_levantar, teste_respiracao_parado, teste_respiracao_ofegante,
                    teste_cabeca_e_corpo_do_mesmo_ritmo_ao_acelerar]),
          ("casa", [teste_escada]))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    grupos = [g for g in GRUPOS if not (("--puro" in argv and g[0] != "puro") or ("--rapido" in argv and g[0] == "casa"))]
    falhas = 0
    for _nome_grupo, testes in grupos:
        for teste in testes:
            inicio = time.time()
            try:
                nota = teste()
                print(f"  ok   {teste.__name__:52s} {time.time() - inicio:5.1f}s" + (f"  ({nota})" if nota else ""), flush=True)
            except Exception as erro:       # noqa: BLE001
                falhas += 1
                print(f"  FALHOU {teste.__name__}: {type(erro).__name__}: {erro}", flush=True)
    print("test_locomocao OK" if not falhas else f"test_locomocao: {falhas} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
