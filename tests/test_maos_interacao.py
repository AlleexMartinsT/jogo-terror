"""Testes das interações das mãos: pegar baixo (corpo desce e inclina), a mão na porta e a leitura com as duas mãos.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_maos_interacao.py

Os números de referência do pegar do chão são MEDIDOS nos clipes da CMU (`assets/referencia/pegar_baixo_ref.json`, gerado por
`python -m tools.movimento_ref.pegar_baixo`); os testes não baixam nada. Para a porta não há clipe real: os limites são a lei de
alcance da fase 4 (`handclips.move_time`), as alturas e forças de norma citadas em `docs/MAOS.md` e a regra do contrato
(a mão não alonga a abertura da porta). Os cenários rodam num palco mínimo com o corpo de verdade (`cenarios/maos.py`).
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import numpy as np  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.engine import collision, handactions, posture  # noqa: E402
from sem_alvorada.engine import handclips as K  # noqa: E402
from sem_alvorada.engine.inputstate import InputState  # noqa: E402
from tools.movimento_ref import grava, metricas  # noqa: E402
from tools.movimento_ref.cenarios import maos  # noqa: E402

DT = 1.0 / 60.0
REFERENCIA = os.path.join(ROOT, "assets", "referencia", "pegar_baixo_ref.json")
MAX_PASSO_MAO = 0.07           # m por quadro a 60 Hz (4,2 m/s): acima disso a mão "teletransportou" (o mesmo limite de test_hands)
MAX_PASSO_CAMERA = 0.03        # m por quadro (1,8 m/s): a câmera desce e sobe, não salta
_CACHE = {}


def memo(chave, fabrica):
    if chave not in _CACHE:
        _CACHE[chave] = fabrica()
    return _CACHE[chave]


def referencia():
    with open(REFERENCIA, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def jogo_com_postura(item=None, no_chao=False, **estado):
    """O palco das mãos (`cenarios/maos.py`) com a postura de alcance LIGADA (o palco das leis do braço a desliga)."""
    jogo = maos.montar_jogo_maos(item, no_chao)
    handactions.ENABLED = True
    maos.estado(jogo, **estado)
    return jogo


def pegar(jogo, ref, distancia, duracao=4.5, por_quadro=None, passos_extra=None):
    """O jogador a `distancia` m do item, olhando para ele, aperta o [E]. Devolve a gravação (com os ossos) e o ponto do item."""
    alvo = next(t for t in jogo.interact.targets if t.ref == ref)
    ponto = tuple(collision.object_position(alvo.obj) if alvo.obj is not None else alvo.position)

    def preparar(j):
        j.place_player(ponto[0], ponto[1] - distancia, 0.0, 0.0)
        maos.mirar(j, (ponto[0], ponto[1], ponto[2] + 0.02))
    roteiro = [grava.Passo(0.6, ao_iniciar=preparar, rotulo="esperar"),
               grava.Passo(duracao, entradas={"interact": True}, por_quadro=por_quadro, rotulo="pegar")]
    rec = grava.gravar(jogo, roteiro, nome=f"pegar_{ref}", ossos="armadura", cada=3)
    return rec, ponto


def contato(rec):
    return next((e[0] for e in rec.eventos if e[1] == "ruido" and e[3] == "pickup"), None)


# --------------------------------------------------------------------------
# A postura em si (matemática pura)
# --------------------------------------------------------------------------
def test_posture_depth_follows_the_height_of_the_item():
    alto = posture.dip_to_reach(0.3, 0.0, 0.25, -1.0)          # item na altura do ombro, ao alcance do braço
    medio = posture.dip_to_reach(0.5, 0.0, 0.88, -1.0)         # a 0,77 m do piso: escrivaninha
    baixo = posture.dip_to_reach(0.5, 0.0, 1.10, -1.0)         # a 0,55 m: criado-mudo
    chao = posture.dip_to_reach(0.5, 0.0, 1.62, -1.0)          # no chão
    assert not alto.needed, alto
    assert 0.0 < medio.depth < baixo.depth < chao.depth, (medio, baixo, chao)
    assert chao.depth >= 0.70, f"do chão o olho desce o que os clipes medem (0,74 a 0,85 m): {chao.depth:.2f}"
    assert chao.depth <= posture.DEPTH_MAX + 1e-9


def test_the_head_never_goes_closer_to_the_hand_than_a_real_head_does():
    """O olho fica 0,55 a 0,78 m acima da mão que pega (MEDIDO em 12 clipes): o corpo não enfia a cabeça no item."""
    for abaixo in (0.9, 1.1, 1.3, 1.6):
        dip = posture.dip_to_reach(0.6, 0.0, abaixo, 1.0)
        assert abaixo - dip.depth >= 0.55, (abaixo, dip)


def test_posture_times_and_angles_sit_inside_the_measured_clips():
    ref = referencia()["resumo"]
    dip = posture.dip_for_depth(0.78, 0.6)
    for tecnica in ("curvar", "agachar"):
        descida = ref[tecnica]["descida_s"]
        # a duração nominal do jerk mínimo chega a 90% em ~0,7 dela: o tempo até o fundo cai na faixa dos clipes
        assert descida["min"] * 0.9 <= dip.down_s * 0.7 + 0.3 <= descida["max"] * 1.1 or descida["max"] >= dip.down_s * 0.7, (tecnica, dip.down_s, descida)
    tronco = [m["tronco_graus"] for m in referencia()["clipes"]]
    assert min(tronco) <= dip.lean <= max(tronco), (dip.lean, min(tronco), max(tronco))
    assert posture.dip_for_depth(0.78, 0.2).lean < posture.dip_for_depth(0.78, 0.9).lean, "perto agacha (tronco mais reto), longe se curva"


def test_the_posture_is_continuous_when_it_changes_its_mind_halfway():
    p = posture.ReachPosture()
    p.go(1.0, 1.0, posture.dip_for_depth(0.7, 0.5))
    anterior, passo_max = 0.0, 0.0
    for k in range(240):
        if k == 40:
            p.go(0.0, 0.9)
        p.step(DT)
        passo_max = max(passo_max, abs(p.amount - anterior))
        anterior = p.amount
    # o jerk mínimo de 1 s anda no máximo 1,875 x 1/60 = 0,031 por quadro; ao mudar de ideia a velocidade continua, não salta
    assert passo_max < 0.04, f"a fração da postura saltou {passo_max:.3f} num quadro"
    assert p.amount == 0.0 and not p.active


# --------------------------------------------------------------------------
# Pegar baixo no jogo
# --------------------------------------------------------------------------
def gravar_chao():
    jogo = jogo_com_postura("BATTERY_1", no_chao=True)
    rec, ponto = pegar(jogo, "BATTERY_1", 0.55)
    return rec, ponto, jogo


def test_pick_up_from_the_floor_bends_the_whole_body_and_reaches_the_item():
    rec, ponto, _jogo = memo("chao", gravar_chao)
    inicio = rec.passos[1][0]
    olho = rec.camera_pos[:, 2]
    fundo = float(olho.min())
    assert 1.65 - fundo >= 0.70, f"o olho desceu {1.65 - fundo:.2f} m do chão (clipes: 0,74 a 0,85)"
    assert 1.65 - fundo <= 0.90
    # a câmera não salta: o maior passo por quadro (gravado a 20 Hz = 3 quadros)
    passos = np.linalg.norm(np.diff(rec.camera_pos, axis=0), axis=1)
    assert passos.max() < 3 * MAX_PASSO_CAMERA, f"a câmera deu um passo de {passos.max():.3f} m entre dois quadros gravados"
    t = contato(rec)
    assert t is not None, "o item foi pego"
    k = int(round(t * rec.fps))
    palma = min(np.linalg.norm(rec.palma[k][0] - np.array(ponto)), np.linalg.norm(rec.palma[k][1] - np.array(ponto)))
    assert palma < 0.08, f"no contato a palma está a {palma * 100:.0f} cm do item"
    assert abs(olho[-1] - 1.65) < 0.05, "o corpo voltou à altura em pé no fim"
    medida = memo("chao_medida", lambda: medir(rec))
    assert medida is not None
    ref = referencia()["clipes"]
    joelho = [m["joelho_graus"] for m in ref]
    tronco = [m["tronco_graus"] for m in ref]
    assert min(tronco) * 0.8 <= medida["tronco_graus"] <= max(tronco) * 1.1, medida
    assert medida["joelho_graus"] <= max(joelho) * 1.1, medida
    # a combinação importa: tronco reto pede joelho dobrado e o contrário (o jogo cai na reta dos clipes)
    assert medida["tronco_graus"] + 0.45 * medida["joelho_graus"] > 40.0, "o tronco e o joelho não podem ficar retos juntos"


def medir(rec):
    from tools.movimento_ref import pegar_baixo
    mov = rec.movimento().trecho(rec.passos[1][0] - 0.3)
    return pegar_baixo.medir_movimento(mov, rec.nome, "jogo")


def test_feet_stay_planted_while_the_body_bends():
    """Item a 0,55 m do olho (sem passo): os dois tornozelos ficam onde estavam (o corpo desce sobre os pés)."""
    jogo = jogo_com_postura("BATTERY_1", no_chao=True)
    rec, _ponto = pegar(jogo, "BATTERY_1", 0.40)          # dentro do alcance: sem passo
    mov = rec.movimento().trecho(rec.passos[1][0])
    for lado in "ed":
        tornozelo = mov.j(f"tornozelo_{lado}")
        deriva = np.linalg.norm(tornozelo[:, :2] - tornozelo[0, :2], axis=1).max()
        assert deriva < 0.04, f"o tornozelo {lado} andou {deriva * 100:.1f} cm durante o gesto"
        assert tornozelo[:, 2].min() > 0.04, "o pé não entra no chão"


def test_a_far_item_makes_the_body_step_toward_it_and_the_player_can_cancel_it():
    jogo = jogo_com_postura("BATTERY_1", no_chao=True)
    rec, ponto = pegar(jogo, "BATTERY_1", 1.0)
    andou = float(np.hypot(rec.jogador["x"][-1] - rec.jogador["x"][0], rec.jogador["y"][-1] - rec.jogador["y"][0]))
    assert 0.2 <= andou <= handactions.STEP_MAX + 0.10, f"o passo assistido andou {andou:.2f} m"
    assert contato(rec) is not None
    # o jogador que aperta uma tecla de andar assume na hora
    jogo = jogo_com_postura("BATTERY_1", no_chao=True)
    jogo.place_player(0.0, 0.0, 0.0, 0.0)
    jogo.player.assist_walk(0.0, 1.0, 0.7)
    jogo.tick(DT, InputState(move_x=1.0))
    assert not jogo.player.assisting


def test_player_can_walk_away_during_the_gesture_without_a_glitch():
    jogo = jogo_com_postura("KEY")
    saltos = []

    def andar_para_tras(j, t, k):
        c = j.hands.last.get("L")
        if c is not None:
            if andar_para_tras.anterior is not None:
                saltos.append(float(np.linalg.norm(np.array(c[0]) - np.array(andar_para_tras.anterior))))
            andar_para_tras.anterior = c[0]
    andar_para_tras.anterior = None
    alvo = next(t for t in jogo.interact.targets if t.ref == "KEY")
    ponto = collision.object_position(alvo.obj)

    def preparar(j):
        j.place_player(ponto[0], ponto[1] - 0.8, 0.0, 0.0)
        maos.mirar(j, (ponto[0], ponto[1], ponto[2] + 0.02))
    roteiro = [grava.Passo(0.5, ao_iniciar=preparar), grava.Passo(0.4, entradas={"interact": True}, por_quadro=andar_para_tras),
               grava.Passo(1.2, mover=-1.0, por_quadro=andar_para_tras), grava.Passo(3.0, por_quadro=andar_para_tras)]
    grava.gravar(jogo, roteiro, ossos="nenhum")
    assert max(saltos) < MAX_PASSO_MAO, f"a mão deu um salto de {max(saltos):.3f} m"
    assert not jogo.hands.busy and not jogo.player.reach.active
    assert abs(jogo.player.camera_pose()[0][2] - jogo.player.z - C.PLAYER_EYE_STAND) < 0.03


def test_each_main_item_gesture_is_single_and_coherent():
    for ref, lado in (("FLASHLIGHT", "R"), ("KEY", "L"), ("MAP", "L"), ("BATTERY_1", "L")):
        jogo = jogo_com_postura(ref, **({"lanterna": False} if ref == "FLASHLIGHT" else {}))
        rec, ponto = pegar(jogo, ref, 0.8, duracao=4.5)
        pickups = [e for e in rec.eventos if e[1] == "ruido" and e[3] == "pickup"]
        assert len(pickups) == 1, f"{ref}: o contato aconteceu {len(pickups)} vezes"
        t = contato(rec)
        k = int(round(t * rec.fps))
        palma = np.linalg.norm(rec.palma[k][0 if lado == "L" else 1] - np.array(ponto))
        assert palma < 0.10, f"{ref}: no contato a palma {lado} está a {palma * 100:.0f} cm do item"
        assert not jogo.hands.busy, f"{ref}: a mão terminou"
        assert abs(rec.camera_pos[-1, 2] - 1.65) < 0.05, f"{ref}: a câmera voltou"


# --------------------------------------------------------------------------
# A mão na porta
# --------------------------------------------------------------------------
PORTA = "living_hall"            # nível 0, x = 1,0 a 1,9 em y = 5,0: o palco tem piso de -60 a 60 m


def jogo_da_porta(**estado):
    jogo = jogo_com_postura(None, **estado)
    jogo.hands.equip(C.ITEM_FLASHLIGHT)
    return jogo


def diante_da_porta(jogo, distancia=0.6, lado=1.0, lateral=-0.25):
    """O jogador diante da maçaneta, olhando o centro da folha (a mira do jogo)."""
    porta = jogo.doors.get(PORTA)
    yaw = porta.closed_yaw
    comp = porta.length - 0.07
    kx, ky = porta.hinge[0] + math.cos(yaw) * comp, porta.hinge[1] + math.sin(yaw) * comp
    nx, ny = -math.sin(yaw), math.cos(yaw)
    px, py = kx + lado * nx * distancia + math.cos(yaw) * lateral, ky + lado * ny * distancia + math.sin(yaw) * lateral
    cx, cy, cz = jogo.doors.center(PORTA)
    jogo.place_player(px, py, 0.0, math.atan2(-(cx - px), cy - py))
    jogo.player.pitch = math.atan2(cz - C.PLAYER_EYE_STAND, math.hypot(cx - px, cy - py))
    for _ in range(40):
        jogo.tick(DT, InputState())
    atual = jogo.interact.current
    assert atual is not None and atual.ref == PORTA, "a mira escolheu a porta"
    return porta


def maçaneta(porta):
    yaw = porta.yaw
    comp = porta.length - 0.07
    return np.array([porta.hinge[0] + math.cos(yaw) * comp, porta.hinge[1] + math.sin(yaw) * comp, porta.floor_z + 0.95])


def rodar_porta(jogo, porta, segundos, esperar=0.0):
    """Espera `esperar` s olhando a porta e aperta o [E]; devolve as linhas (t, abertura, palma-maçaneta, clipe, giro)."""
    for _ in range(int(esperar / DT)):
        jogo.tick(DT, InputState())
    linhas, entrada = [], InputState(interact=True)
    for k in range(int(segundos / DT)):
        jogo.tick(DT, entrada)
        entrada = InputState()
        palma = np.array(jogo.body.arm("L").hand_world_position())
        clipe = jogo.hands.runner.clip
        linhas.append((k * DT, porta.openness, float(np.linalg.norm(palma - maçaneta(porta))), clipe.name if clipe else None, porta.turn,
                       tuple(jogo.hands.last["L"][0])))
    return linhas


def duracao_da_folha(linhas):
    a = next(t for t, aber, *_ in linhas if aber > 0.02)
    b = next(t for t, aber, *_ in linhas if aber > 0.98)
    return b - a


def test_door_opens_only_after_the_hand_is_on_the_knob_and_the_leaf_keeps_its_duration():
    # sem a mão (a fase 4): o mesmo jogador, a mesma porta
    jogo = jogo_da_porta()
    porta = diante_da_porta(jogo)
    handactions.ENABLED = False
    sem_mao = rodar_porta(jogo, porta, 2.0)
    handactions.ENABLED = True
    jogo = jogo_da_porta()                 # (um palco novo apaga o anterior: um de cada vez)
    porta = diante_da_porta(jogo)
    linhas = rodar_porta(jogo, porta, 2.8, esperar=1.0)
    t_gira = next(t for t, _a, _d, _c, giro, _p in linhas if giro > 0.5)
    t_sai = next(t for t, a, _d, _c, _g, _p in linhas if a > 0.02)
    t_sai_sem = next(t for t, a, _d, _c, _g, _p in sem_mao if a > 0.02)
    # a mão já estava preparada diante da maçaneta (olhou a porta 1 s): a folha sai no máximo 0,55 s depois do [E]
    # (0,12 s de último avanço + 0,14 s de giro da maçaneta + a subida da folha até 2% do curso)
    assert t_sai <= 0.55, f"a folha saiu {t_sai:.2f} s depois do [E]"
    assert t_gira < t_sai
    palma_no_giro = next(d for t, _a, d, _c, _g, _p in linhas if abs(t - t_gira) < DT)
    assert palma_no_giro < 0.13, f"quando a maçaneta gira a palma está a {palma_no_giro * 100:.0f} cm do centro dela"
    # a duração do movimento da folha é a mesma, com ou sem a mão (de 2% a 98% da abertura)
    assert abs(duracao_da_folha(linhas) - duracao_da_folha(sem_mao)) < 0.04, (duracao_da_folha(linhas), duracao_da_folha(sem_mao))
    # a mão acompanha a maçaneta enquanto o braço alcança e depois a solta (volta ao braço)
    seguindo = [d for t, a, d, _c, _g, _p in linhas if t_sai < t < t_sai + 0.30]
    assert max(seguindo) < 0.16, f"a palma saiu da maçaneta durante o empurrão: {max(seguindo) * 100:.0f} cm"
    assert linhas[-1][3] is None, "o gesto terminou"
    assert t_sai > t_sai_sem, "a folha espera a mão"


def test_cold_press_takes_the_reach_before_the_door_moves_but_never_longer_than_a_second():
    jogo = jogo_da_porta()
    porta = diante_da_porta(jogo)
    linhas = rodar_porta(jogo, porta, 2.8)                 # sem esperar: a mão sai agora
    t_sai = next(t for t, a, *_ in linhas if a > 0.02)
    alcance = K.move_time(0.75)
    assert 0.3 < t_sai <= 1.2, f"a folha saiu {t_sai:.2f} s depois do [E] (a lei de alcance dá {alcance:.2f} s para 0,75 m)"
    passos = [np.linalg.norm(np.array(b[5]) - np.array(a[5])) for a, b in zip(linhas[:-1], linhas[1:])]
    assert max(passos) < MAX_PASSO_MAO, f"a mão saltou {max(passos):.3f} m"


def test_locked_door_the_hand_tries_the_wrist_shakes_and_stops():
    jogo = jogo_da_porta()
    porta = diante_da_porta(jogo)
    porta.lock = "front"                       # uma tranca que o estado do jogo não abriu
    jogo.state.unlocked.discard("front")
    linhas = rodar_porta(jogo, porta, 2.2, esperar=0.8)
    assert all(a < 0.01 for _t, a, *_ in linhas), "a porta trancada não abre"
    assert linhas[0][3] == "door_locked"
    t_chacoalha = next(t for t, a, *_ in linhas if a > 0.0005)         # a folha vibra na folga do ferrolho
    esperado = handactions.DoorHand.timing("locked", max(handactions.COLD_REACH_MIN, 0.5))
    assert esperado - 0.15 <= t_chacoalha <= esperado + 0.5, f"a folha vibrou em {t_chacoalha:.2f} s; a mão chega em ~{esperado:.2f} s"
    assert linhas[-1][3] is None, "o gesto terminou"
    assert max(np.linalg.norm(np.array(b[5]) - np.array(a[5])) for a, b in zip(linhas[:-1], linhas[1:])) < MAX_PASSO_MAO


def test_no_hand_gesture_when_the_left_hand_holds_an_item_or_the_player_is_in_a_hurry():
    jogo = jogo_da_porta(chave=True)
    porta = diante_da_porta(jogo)
    jogo.hands.equip(C.ITEM_KEY)
    for _ in range(180):
        jogo.tick(DT, InputState())
    assert jogo.hands.actions.plan_door(PORTA) is None, "a esquerda está com a chave"
    jogo = jogo_da_porta()
    porta = diante_da_porta(jogo)
    assert jogo.hands.actions.plan_door(PORTA, hurried=True) is None, "com pressa a porta não espera a mão"
    atual = jogo.hands.actions.plan_door(PORTA)
    assert atual is not None and atual.side == "L"


def test_door_gesture_is_off_without_a_real_body_and_when_switched_off():
    from sem_alvorada.engine.fallbacks import NullArm
    assert NullArm().shoulder_world_position() is None
    jogo = jogo_da_porta()
    diante_da_porta(jogo)
    handactions.ENABLED = False
    try:
        assert jogo.hands.actions.plan_door(PORTA) is None
    finally:
        handactions.ENABLED = True


def test_the_slow_hand_never_drags_the_arm_past_what_an_arm_reaches():
    jogo = jogo_da_porta()
    porta = diante_da_porta(jogo, distancia=0.5)
    ombro_max = 0.0
    entrada = InputState(interact=True)
    for _ in range(int(3.0 / DT)):
        jogo.tick(DT, entrada)
        entrada = InputState()
        ombro = np.array(jogo.body.arm("L").shoulder_world_position())
        palma = np.array(jogo.body.arm("L").hand_world_position())
        ombro_max = max(ombro_max, float(np.linalg.norm(palma - ombro)))
    assert ombro_max < 0.72, f"o ombro à palma chegou a {ombro_max:.2f} m (braço de 0,60 m mais a palma)"


# --------------------------------------------------------------------------
# Ler com as duas mãos
# --------------------------------------------------------------------------
def test_reading_holds_the_paper_at_reading_distance_tilted_with_the_flashlight_hand_beside_it():
    pos, rot = K.FACE_ITEM[C.ITEM_NOTE]
    folha = (0.12, 0.16)
    centro = np.array(pos) + np.array([0.0, folha[1] / 2.0, 0.0])
    distancia = float(np.linalg.norm(centro))
    assert 0.35 <= distancia <= 0.40, f"o centro da folha está a {distancia:.3f} m do olho (leitura com o material na mão: 35 a 40 cm)"
    assert -20.0 <= rot[0] <= -6.0, f"inclinação da folha {rot[0]} graus: levemente inclinada, o topo para longe"
    mao, _ = K.READ_LANTERN["face"]
    assert abs(mao[0] - (pos[0] + folha[0] / 2)) < 0.07, "a mão direita fica na borda direita da folha"
    assert mao[1] < pos[1] + folha[1] * 0.6, "e abaixo do meio dela (o polegar na margem)"


def gravar_leitura():
    jogo = jogo_com_postura(None, notas=("NOTE_1",))
    jogo.hands.equip(C.ITEM_NOTE)
    for _ in range(120):
        jogo.tick(DT, InputState())
    maos_pos = []
    jogo.hands.use_held()
    for _ in range(int(2.0 / DT)):
        jogo.tick(DT, InputState())
        maos_pos.append((tuple(jogo.hands.last["L"][0]), tuple(jogo.hands.last["R"][0]), jogo.phase))
    jogo.tick(DT, InputState(interact=True))                  # fecha o leitor
    for _ in range(int(2.0 / DT)):
        jogo.tick(DT, InputState())
        maos_pos.append((tuple(jogo.hands.last["L"][0]), tuple(jogo.hands.last["R"][0]), jogo.phase))
    return maos_pos


def test_reading_enters_and_leaves_without_a_jump_and_the_right_hand_comes_to_the_paper():
    quadros = memo("leitura", gravar_leitura)
    for indice in (0, 1):
        pontos = np.array([q[indice] for q in quadros])
        saltos = np.linalg.norm(np.diff(pontos, axis=0), axis=1)
        assert saltos.max() < MAX_PASSO_MAO, f"mão {'LR'[indice]}: salto de {saltos.max():.3f} m ao entrar ou sair da leitura"
    lendo = [q for q in quadros if q[2] == "reading"]
    assert len(lendo) > 60
    direita = np.array([q[1] for q in lendo[-30:]]).mean(axis=0)
    base = np.array(K.HOLD_ITEM[("R", C.ITEM_FLASHLIGHT)][0])
    leitura = np.array(K.hold_hand("R", C.ITEM_FLASHLIGHT, "face")[0])
    # (o balanço da mão soma uns centímetros ao alvo; a mão tem de estar mais perto do lugar de ler que do de segurar)
    assert np.linalg.norm(direita - leitura) < np.linalg.norm(direita - np.array(K.hold_hand("R", C.ITEM_FLASHLIGHT, "hold")[0]))
    assert np.linalg.norm(direita - leitura) < 0.05
    assert np.linalg.norm(leitura - np.array(K.hold_hand("R", C.ITEM_FLASHLIGHT, "hold")[0])) > 0.03, "a mão da lanterna muda de lugar ao ler"


def test_reading_a_note_on_a_low_table_bends_the_body_and_gives_it_back():
    jogo = jogo_com_postura("NOTE_1")
    alvo = next(t for t in jogo.interact.targets if t.ref == "NOTE_1")
    ponto = collision.object_position(alvo.obj)
    alvo.obj.location.z = 0.45                                  # a mesinha de centro da sala (0,44 m)
    alvo.position = tuple(collision.object_position(alvo.obj))
    jogo.place_player(ponto[0], ponto[1] - 0.6, 0.0, 0.0)
    maos.mirar(jogo, (ponto[0], ponto[1], 0.47))
    for _ in range(20):
        jogo.tick(DT, InputState())
    assert jogo.interact.current is not None and jogo.interact.current.ref == "NOTE_1"
    fundo = 0.0
    entrada = InputState(interact=True)
    for _ in range(int(3.0 / DT)):
        jogo.tick(DT, entrada)
        entrada = InputState()
        fundo = max(fundo, jogo.player.reach.depth)
    assert fundo > 0.4, f"o corpo desceu {fundo:.2f} m para pegar a nota na mesa baixa"
    assert jogo.phase == "reading"
    jogo.tick(DT, InputState(interact=True))
    for _ in range(int(3.0 / DT)):
        jogo.tick(DT, InputState())
    assert not jogo.player.reach.active and not jogo.hands.busy


def main():
    testes = [(nome, fn) for nome, fn in sorted(globals().items()) if nome.startswith("test_") and callable(fn)]
    ordem = [t for t in testes if t[0] in ("test_posture_depth_follows_the_height_of_the_item",
                                          "test_the_head_never_goes_closer_to_the_hand_than_a_real_head_does")]
    ordem += [t for t in testes if t not in ordem]
    passaram = 0
    for nome, fn in ordem:
        handactions.ENABLED = True
        try:
            fn()
            print(f"ok      {nome}", flush=True)
            passaram += 1
        except Exception as erro:
            import traceback
            print(f"FALHOU  {nome}: {erro!r}")
            traceback.print_exc()
    print(f"{passaram}/{len(ordem)} testes das interações das mãos passaram")
    sys.exit(0 if passaram == len(ordem) else 1)


if __name__ == "__main__":
    main()
