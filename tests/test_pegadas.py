"""Testes das pegadas: dedos que fecham por contato, postura e pontaria da lanterna, interruptor, batida e pré-forma da mão.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_pegadas.py

A penetração e a folga são medidas na malha de pele de verdade (a do corpo já deformada pelo esqueleto) contra a malha do item,
em milímetros (`tools/movimento_ref/cenarios/pegadas.py`). Os números de referência vêm de `docs/MAOS.md`: o que é MEDIDO (a pele
no jogo), DERIVADO (o padrão de flexão de uma pegada de força, de Shimawaki et al.) ou ESTIMADO (tempo do interruptor, a batida).
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402,F401 - `mathutils` só existe depois dele
import numpy as np  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import grasp_data  # noqa: E402
from sem_alvorada.body import fingers as F  # noqa: E402
from sem_alvorada.body import skeleton as S  # noqa: E402
from sem_alvorada.body import solver  # noqa: E402
from sem_alvorada.engine import gripdrive, lanternaim  # noqa: E402
from sem_alvorada.engine.inputstate import InputState  # noqa: E402
from tools.movimento_ref.cenarios import maos, pegadas  # noqa: E402

_CACHE = {}


def memo(chave, fabrica):
    if chave not in _CACHE:
        _CACHE[chave] = fabrica()
    return _CACHE[chave]


def medida(item):
    """(jogo, {parte: {pen, gap}}) do item na mão, no repouso."""
    def fabricar():
        jogo, lado = pegadas.preparar(item)
        return jogo, pegadas.medir_item(jogo, item, lado)
    return memo(("pele", item), fabricar)


def flexao_do_pulso(jogo, lado):
    solucao = jogo.body._solution
    antebraco, mao = S.BONE_INDEX[f"Forearm.{lado}"], S.BONE_INDEX[f"Hand.{lado}"]
    relativa = solucao.world[antebraco].to_matrix().inverted() @ solucao.world[mao].to_matrix()
    _giro, dobra = solver._twist_swing(relativa.to_quaternion(), solver._REST_DIR[antebraco])
    return math.degrees(dobra.angle)


def flexao_do_cotovelo(jogo, lado):
    cabeca = lambda nome: np.array(jogo.body._solution.head[S.BONE_INDEX[nome]])
    ombro, cotovelo, punho = cabeca(f"UpperArm.{lado}"), cabeca(f"Forearm.{lado}"), cabeca(f"Hand.{lado}")
    a, b = ombro - cotovelo, punho - cotovelo
    return 180.0 - math.degrees(math.acos(float(a @ b / np.linalg.norm(a) / np.linalg.norm(b))))


# ---------------------------------------------------------------------------
# Matemática pura
# ---------------------------------------------------------------------------
def test_switch_press_envelope_is_down_hold_up():
    assert gripdrive.press_envelope(-0.01) == 0.0 and gripdrive.press_envelope(gripdrive.PRESS_TOTAL + 0.01) == 0.0
    assert gripdrive.press_envelope(gripdrive.PRESS_DOWN + 0.01) == 1.0, "o polegar sustenta o interruptor um instante"
    subida = [gripdrive.press_envelope(t) for t in np.linspace(0.0, gripdrive.PRESS_DOWN, 20)]
    assert all(b >= a - 1e-9 for a, b in zip(subida, subida[1:])), "desce sem voltar"
    assert 0.08 <= gripdrive.PRESS_TOTAL <= 0.20, "um dedo fica de 80 a 150 ms sobre uma tecla (ESTIMADO)"


def test_cascade_with_per_joint_goals_keeps_the_base_ahead():
    cascata = F.FingerCascade((0.0,) * 5)
    meta = [[0.6, 0.8, 0.5]] * 5
    for _ in range(3):
        cascata.step(1 / 60, meta)
    base, meio, ponta = cascata.joint[1]
    assert base > meio > ponta > 0.0, "a base sai na frente: a falange da ponta chega depois"
    for _ in range(120):
        cascata.step(1 / 60, meta)
    assert all(abs(a - b) < 1e-3 for a, b in zip(cascata.joint[1], meta[1])), "cada junta chega à própria meta"


def test_finger_quaternions_match_finger_rotations():
    curls = (0.3, 0.5, 0.6, 0.7, 0.4)
    todas = F.finger_rotations("L", curls, 0.1)
    for indice, dedo in enumerate(S.FINGERS, start=1):
        proprias = F.finger_quaternions("L", dedo, (curls[indice],) * 3, 0.1)
        for osso, q in zip(S.finger_bones("L", dedo), proprias):
            assert todas[osso].rotation_difference(q).angle < 1e-6


def test_grip_drive_blends_free_curl_into_the_contact_pose():
    dados = gripdrive.GripDrive()
    livre = dados.joints(C.ITEM_FLASHLIGHT, (0.3,) * 5, gripdrive.EMPTY)
    fechada = dados.joints(C.ITEM_FLASHLIGHT, (0.3,) * 5, gripdrive.HOLDING)
    metade = dados.joints(C.ITEM_FLASHLIGHT, (0.3,) * 5, gripdrive.uniform(0.5))
    assert livre[1] == [0.3, 0.3, 0.3]
    assert fechada[1] == grasp_data.GRASPS[C.ITEM_FLASHLIGHT]["closed"][1]
    assert all(min(a, b) <= m <= max(a, b) for a, b, m in zip(livre[1], fechada[1], metade[1]))
    assert dados.joints(C.ITEM_NOTE, (0.3,) * 5, gripdrive.HOLDING) is None, "item sem pegada calculada cai nos curls de antes"
    apertado = dados.joints(C.ITEM_FLASHLIGHT, (0.3,) * 5, gripdrive.HOLDING, press=1.0)
    assert apertado[0] != fechada[0] and apertado[1] == fechada[1], "o interruptor só mexe no polegar"


def test_the_power_grip_closes_in_the_flexion_pattern_of_a_real_cylinder_grip():
    """Shimawaki et al. (2019), cilindros: a PIP flexiona mais que a MCP e que a DIP; no cilindro fino a diferença cresce."""
    for dedo in (1, 2, 3, 4):
        mcp, pip, dip = grasp_data.GRASPS[C.ITEM_FLASHLIGHT]["closed"][dedo]
        assert pip >= mcp - 0.02 and pip > dip, f"dedo {dedo}: MCP {mcp:.2f}, PIP {pip:.2f}, DIP {dip:.2f}"
        assert 0.25 < mcp < 0.80 and 0.35 < pip < 0.90 and 0.2 < dip < 0.75


# ---------------------------------------------------------------------------
# Contato: a pele contra a malha do item, dedo por dedo (MEDIDO)
# ---------------------------------------------------------------------------
def test_flashlight_power_grip_touches_without_entering_the_barrel():
    _jogo, partes = medida(C.ITEM_FLASHLIGHT)
    assert max(p["pen"] for p in partes.values()) < 1.0, {k: round(v["pen"], 2) for k, v in partes.items()}
    for dedo in ("Index", "Middle", "Ring", "Pinky"):
        assert partes[dedo]["gap"] < 2.5, f"{dedo} a {partes[dedo]['gap']:.1f} mm do cano"
    assert partes["Palm"]["gap"] < 6.0, f"a palma a {partes['Palm']['gap']:.1f} mm do cano"


def test_battery_in_the_palm_is_cupped_by_the_fingers():
    _jogo, partes = medida(C.ITEM_BATTERY)
    assert max(p["pen"] for p in partes.values()) < 1.0
    for parte in ("Palm", "Thumb", "Index", "Middle", "Ring"):
        assert partes[parte]["gap"] < 2.5, f"{parte} a {partes[parte]['gap']:.1f} mm da pilha"


def test_key_is_pinched_between_thumb_and_index():
    _jogo, partes = medida(C.ITEM_KEY)
    assert max(p["pen"] for p in partes.values()) < 1.5, {k: round(v["pen"], 2) for k, v in partes.items()}
    assert partes["Thumb"]["gap"] < 3.0 and partes["Index"]["gap"] < 3.0
    assert partes["Pinky"]["gap"] > 3.0, "os outros dedos ficam relaxados, longe da cabeça"


# ---------------------------------------------------------------------------
# Postura e pontaria
# ---------------------------------------------------------------------------
def test_flashlight_hold_has_neutral_wrist_and_the_elbow_bent_like_a_held_light():
    jogo, _lado = memo(("jogo", C.ITEM_FLASHLIGHT), lambda: pegadas.preparar(C.ITEM_FLASHLIGHT))
    assert flexao_do_pulso(jogo, "R") < 25.0, f"punho dobrado {flexao_do_pulso(jogo, 'R'):.0f} graus"
    assert 100.0 <= flexao_do_cotovelo(jogo, "R") <= 120.0, f"cotovelo {flexao_do_cotovelo(jogo, 'R'):.0f} graus"


def test_the_arm_follows_the_gaze_pitch_only_in_part():
    jogo, _lado = pegadas.preparar(C.ITEM_FLASHLIGHT)

    def mao_com(passo_graus):
        for _ in range(100):
            jogo.player.pitch = math.radians(passo_graus)
            jogo.tick(1 / 60, InputState())
        return np.array(jogo.hands.last["R"][0]), flexao_do_pulso(jogo, "R")
    parada, _ = mao_com(0.0)
    cima, punho_cima = mao_com(40.0)
    muito_cima, _ = mao_com(70.0)
    descida = parada[1] - cima[1]
    assert 0.03 < descida < 0.10, f"a mão desce {descida * 100:.1f} cm ao olhar 40 graus para cima: poucos centímetros"
    assert abs((parada[1] - muito_cima[1]) - descida) < 0.02, "satura: não foge do quadro olhando mais para cima"
    assert punho_cima < 60.0, f"o punho dobra {punho_cima:.0f} graus (limite do solver: 72)"
    baixo, _ = mao_com(-30.0)
    assert baixo[1] > parada[1] - 0.005, "olhando para baixo a mão sobe, não desce"


def test_reading_tilts_the_barrel_away_from_the_page():
    jogo, _lado = pegadas.preparar(C.ITEM_FLASHLIGHT)
    antes = jogo.hands.last["R"][1]
    jogo.hands.set_lantern_reading(True)
    for _ in range(90):
        jogo.tick(1 / 60, InputState())
    depois = jogo.hands.last["R"][1]
    giro = max(abs(a - b) for a, b in zip(antes, depois))
    assert 8.0 < giro < 40.0, f"o cano girou {giro:.1f} graus para ler"
    jogo.hands.set_lantern_reading(False)
    for _ in range(90):
        jogo.tick(1 / 60, InputState())
    assert max(abs(a - b) for a, b in zip(antes, jogo.hands.last["R"][1])) < 3.0, "volta ao normal sem sobra"


# ---------------------------------------------------------------------------
# Interruptor e batida
# ---------------------------------------------------------------------------
def test_pressing_the_switch_moves_the_thumb_down_and_back():
    jogo, _lado = pegadas.preparar(C.ITEM_FLASHLIGHT)
    braco = jogo.body.arm("R")
    repouso = list(braco._cascade.joint[0])
    maximo = 0.0
    for k in range(40):
        jogo.tick(1 / 60, InputState(flashlight=(k == 0)))
        maximo = max(maximo, max(abs(a - b) for a, b in zip(braco._cascade.joint[0], repouso)))
    assert maximo > 0.003, "o polegar não se mexe no interruptor"
    assert max(abs(a - b) for a, b in zip(braco._cascade.joint[0], repouso)) < 1e-3, "o polegar volta ao repouso"


def test_palm_tap_comes_once_per_burst_and_only_with_the_left_hand_free():
    def rodar(segundos, mao_esquerda=None):
        jogo, _lado = pegadas.preparar(C.ITEM_FLASHLIGHT)
        if mao_esquerda is not None:
            maos.estado(jogo, lanterna=True, chave=True, segurar=mao_esquerda)
        for _ in range(120):
            jogo.tick(1 / 60, InputState())
        batidas, atual = [], None
        for k in range(int(segundos * 60)):
            jogo.state.battery = 0.10
            jogo.state.flashlight_on = True
            jogo.tick(1 / 60, InputState())
            clip = jogo.hands.runner.clip
            nome = clip.name if clip else None
            if nome == "palm_tap" and atual != "palm_tap":
                batidas.append(k / 60)
            atual = nome
        return batidas
    livre = rodar(45.0)
    assert livre, "com a pilha fraca e a esquerda livre a mão bate no cano"
    assert all(b - a >= lanternaim.REFRACTORY - 0.5 for a, b in zip(livre, livre[1:])), f"batidas em {livre}"
    assert not rodar(30.0, C.ITEM_KEY), "com um item na esquerda a mão não bate"


# ---------------------------------------------------------------------------
# Pré-forma da mão no alcance
# ---------------------------------------------------------------------------
def test_hand_opens_wider_than_the_item_at_two_thirds_of_the_reach_and_closes_at_contact():
    """Alcances reais: a abertura máxima vem em 60 a 75% do gesto (Jeannerod 1984; Smeets e Brenner 1999) e a mão fecha até o contato."""
    for item in (C.ITEM_FLASHLIGHT, C.ITEM_KEY):
        perfil = memo(("abertura", item), lambda item=item: pegadas.perfil_de_abertura(item))
        t, abertura = perfil["t"], perfil["abertura"]
        inicio, contato = perfil["inicio"], perfil["contato"]
        janela = (t >= inicio) & (t <= contato)
        pico = int(np.argmax(np.where(janela, abertura, -1.0)))
        fracao = (t[pico] - inicio) / (contato - inicio)
        assert 0.58 <= fracao <= 0.78, f"{item}: abertura máxima em {fracao * 100:.0f}% do alcance"
        assert abertura[pico] > 1.5 * abertura[int(contato * 60)], f"{item}: a mão não fecha rumo ao item"


def main():
    testes = [(nome, fn) for nome, fn in sorted(globals().items()) if nome.startswith("test_") and callable(fn)]
    falhas = 0
    for nome, fn in testes:
        try:
            fn()
            print(f"ok      {nome}", flush=True)
        except Exception as erro:      # noqa: BLE001 - queremos ver todas as falhas de uma vez
            falhas += 1
            import traceback
            print(f"FALHOU  {nome}: {erro!r}", flush=True)
            traceback.print_exc()
    print(f"{len(testes) - falhas}/{len(testes)} testes das pegadas passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
