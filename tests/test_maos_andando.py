"""Testes da mão que carrega enquanto o corpo anda (fase 5): `sem_alvorada/handsway.py` e `engine/handsway.py`.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_maos_andando.py

Dois grupos. O primeiro é matemática pura: a mola do antebraço contra a lei de segunda ordem (DERIVADO: a transmissibilidade
relativa, a resposta ao degrau de aceleração e ao impulso do calcanhar, escritas aqui à parte e não importadas do módulo), a
passa-alta, o braço de alavanca, a deriva e a respiração em graus. O segundo grava o jogo no palco e mede no referencial da
câmera: o ombro e o braço livre contra a CMU na mesma velocidade (MEDIDO, `assets/referencia/maos_ego_ref.json`), a mão que carrega
contra a ordem de grandeza da pesquisa (ESTIMADO, e dito), a partida, a parada, o giro do mouse, o olhar para baixo e o chaveiro.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import numpy as np  # noqa: E402

from sem_alvorada import gait  # noqa: E402
from sem_alvorada import handsway as H  # noqa: E402
from tools.movimento_ref import egocentrico as E  # noqa: E402

IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
WALK, RUN, CROUCH = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
DT = 1.0 / 60.0
_CACHE = {}


def memo(chave, fabrica):
    if chave not in _CACHE:
        _CACHE[chave] = fabrica()
    return _CACHE[chave]


def perto(valor, esperado, tolerancia, nome):
    assert abs(valor - esperado) <= tolerancia, f"{nome}: {valor:.5f}, esperado {esperado:.5f} +- {tolerancia}"


def drive(hand, seconds, shoulder_of_t, weights=WALK, mass=0.0, follow_camera=True, dt=DT, start=0.0):
    """Anda `seconds` s com o ombro em `shoulder_of_t(t)` (mundo). A câmera acompanha o ombro (ficam a uma distância fixa), então só a
    mola trabalha. Devolve a lista de extensões (x, y, z) por quadro."""
    out = []
    for k in range(int(round(seconds / dt))):
        t = start + (k + 1) * dt
        shoulder = shoulder_of_t(t)
        camera = tuple(s - c for s, c in zip(shoulder, (0.2, -0.2, 0.05))) if follow_camera else (0.0, 0.0, 0.0)
        hand.step(dt, IDENTITY, camera, shoulder, weights, mass)
        out.append(tuple(hand.extension))
    return np.array(out)


# --------------------------------------------------------------------------
# A mola contra a lei
# --------------------------------------------------------------------------
def test_vertical_bob_matches_the_transmissibility_law():
    """Um ombro que sobe e desce senoidalmente move a mão em relação a ele na razão r^2 / raiz((1 - r^2)^2 + (2 zeta r)^2)."""
    amplitude = 0.02
    for frequency in (1.0, 2.06, 3.0, 4.5):
        hand = H.CarryHand(1.0)
        natural = H.natural_frequency(WALK, 0.0)
        zeta = H.damping_ratio(WALK)
        extension = drive(hand, 8.0, lambda t: (0.0, 0.0, amplitude * math.sin(math.tau * frequency * t)), follow_camera=True)
        # a câmera acompanha o ombro: a coordenada "cima" da câmera é o eixo y do mundo? aqui os eixos são os do mundo (z cima)
        measured = np.ptp(extension[int(4.0 / DT):, 2]) / 2.0
        expected = amplitude * H.relative_transmissibility(frequency, natural / math.tau, zeta)
        perto(measured / expected, 1.0, 0.04, f"razão simulada/lei a {frequency} Hz")


def test_constant_velocity_leaves_no_lag():
    """Andar a velocidade constante não estica a mola: o ombro e a mão andam juntos (o amortecedor age na velocidade relativa)."""
    hand = H.CarryHand(1.0)
    extension = drive(hand, 4.0, lambda t: (0.0, 1.7 * t, 0.0))
    assert np.abs(extension[int(2.0 / DT):]).max() < 5e-5, np.abs(extension[int(2.0 / DT):]).max()


def test_start_peak_matches_the_step_response():
    """Aceleração de 7 m/s2 (a de arrancar, `C.ACCEL_START`): o pico da extensão é (a / w^2) (1 + exp(-pi zeta / raiz(1 - zeta^2)))."""
    accel = 7.0
    hand = H.CarryHand(1.0)

    def shoulder(t):
        return (0.0, 0.5 * accel * t * t, 0.0)
    extension = drive(hand, 0.6, shoulder)
    natural = H.natural_frequency(WALK, 0.0)
    zeta = H.damping_ratio(WALK)
    expected = accel / natural ** 2 * (1.0 + math.exp(-math.pi * zeta / math.sqrt(1.0 - zeta ** 2)))
    perto(-extension[:, 1].min() / expected, 1.0, 0.04, "pico do degrau de aceleração")
    assert -0.06 < extension[:, 1].min() < -0.005, "a mão fica uns centímetros para trás ao arrancar"


def test_stop_continues_forward_then_settles():
    """Frear de 1,7 m/s em 0,65 s: a mão passa um pouco para a frente do ponto de repouso e assenta em menos de 1 s."""
    hand = H.CarryHand(1.0)
    decel = 1.7 / 0.65

    def shoulder(t):
        if t < 1.0:
            return (0.0, 1.7 * t, 0.0)
        s = min(t - 1.0, 0.65)
        return (0.0, 1.7 + 1.7 * s - 0.5 * decel * s * s, 0.0)
    extension = drive(hand, 3.0, shoulder)
    peak = extension[:, 1].max()
    assert 0.003 < peak < 0.06, f"a mão devia seguir {peak * 100:.1f} cm além do repouso ao parar"
    assert np.abs(extension[int(2.4 / DT):, 1]).max() < 0.1 * peak, "e assentar depois da parada"


def test_heel_strike_impulse_response():
    """O impulso do calcanhar `v0` dá extensão máxima (v0 / wd) exp(-zeta w tp) sen(wd tp), tp = atan(wd / (zeta w)) / wd."""
    for weights, strength in ((WALK, H.HEEL_KICK["walk"]), (RUN, H.HEEL_KICK["run"])):
        hand = H.CarryHand(1.0)
        hand.heel_strike(strength, forward=0.0)
        natural, zeta = H.natural_frequency(weights, 0.0), H.damping_ratio(weights)
        damped = natural * math.sqrt(1.0 - zeta ** 2)
        peak_time = math.atan2(damped, zeta * natural) / damped
        expected = strength / damped * math.exp(-zeta * natural * peak_time) * math.sin(damped * peak_time)
        # a câmera e o ombro parados, só o impulso: a mão desce (y, nos eixos da câmera) e volta
        low = 0.0
        for _ in range(int(1.0 / DT)):
            hand.step(DT, IDENTITY, (0.0, 0.0, 0.0), (0.2, -0.2, 0.05), weights)
            low = min(low, hand.extension[1])
        perto(-low / expected, 1.0, 0.05, "pico do impulso do calcanhar")
    assert 0.002 < H.HEEL_KICK["walk"] / H.natural_frequency(WALK, 0.0) < 0.012, "andando o toque é de milímetros"
    assert 0.010 < H.HEEL_KICK["run"] / H.natural_frequency(RUN, 0.0) < 0.030, "correndo, de poucos centímetros"


def test_the_extension_is_a_world_vector_when_the_camera_turns():
    """A mão deslocada de um lado continua deslocada do mesmo lado do MUNDO se a câmera gira: nos eixos da câmera ela gira ao contrário."""
    axes_after = ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0))         # câmera virada 90 graus
    moved = H.carry_over(IDENTITY, axes_after, (0.01, 0.0, 0.0))
    assert max(abs(a - b) for a, b in zip(moved, (0.0, 0.01, 0.0))) < 1e-9 or max(abs(a - b) for a, b in zip(moved, (0.0, -0.01, 0.0))) < 1e-9
    back = H.carry_over(axes_after, IDENTITY, moved)
    assert max(abs(a - b) for a, b in zip(back, (0.01, 0.0, 0.0))) < 1e-9, "ida e volta devolvem o vetor"


def test_teleport_is_not_an_impulse():
    """Pôr o corpo 10 m adiante (checkpoint, fim de cena) não vira aceleração: a mão continua parada."""
    hand = H.CarryHand(1.0)
    drive(hand, 1.0, lambda t: (0.0, 1.7 * t, 0.0))
    extension = drive(hand, 1.0, lambda t: (0.0, 1.7 * t + 10.0, 0.0), start=1.0)
    assert np.abs(extension).max() < 5e-4, np.abs(extension).max()


def test_highpass_keeps_the_gait_and_drops_the_posture():
    filtro = H.HighPass(H.ANCHOR_HIGHPASS_S)
    out = [filtro.step(DT, (0.05,))[0] for _ in range(int(8.0 / DT))]
    assert abs(out[-1]) < 0.05 * 0.01, "uma postura que muda e fica (olhar para baixo) sai em alguns segundos"
    for frequency, minimum in ((1.0, 0.98), (2.0, 0.99), (0.13, 0.65)):
        filtro = H.HighPass(H.ANCHOR_HIGHPASS_S)
        serie = [filtro.step(DT, (math.sin(math.tau * frequency * k * DT),))[0] for k in range(int(20.0 / DT))]
        assert np.ptp(serie[int(10 / DT):]) / 2.0 > minimum * 0.99 or frequency < 0.5, (frequency, np.ptp(serie))
    filtro = H.HighPass(H.ANCHOR_HIGHPASS_S)
    serie = [filtro.step(DT, (math.sin(math.tau * 1.0 * k * DT),))[0] for k in range(int(20.0 / DT))]
    assert np.ptp(serie[int(10 / DT):]) / 2.0 > 0.98, "o passo (1 Hz) atravessa o filtro com mais de 98% da amplitude"


def test_lever_shift_follows_the_chest_and_has_the_right_sign():
    """O peito que fica atrás do olhar (guinada negativa, o mouse virou à esquerda) leva a mão para a direita da câmera."""
    shoulder = (0.18, -0.21, 0.05)
    hand = (0.14, -0.13, -0.30)
    lever = 0.35
    behind = H.lever_shift(math.radians(-12.0), hand, shoulder)
    perto(behind[0], H.LEVER_SHARE * lever * math.sin(math.radians(12.0)), 2e-3, "deslocamento lateral por 12 graus de atraso")
    assert behind[0] > 0.03, "para a direita"
    assert H.lever_shift(math.radians(12.0), hand, shoulder)[0] < 0.0, "peito à esquerda do olhar: mão à esquerda"
    assert H.lever_shift(0.0, hand, shoulder) == (0.0, 0.0, 0.0)


def test_natural_frequency_falls_with_the_item_mass():
    free = H.natural_frequency(WALK, 0.0)
    with_lantern = H.natural_frequency(WALK, H.ITEM_MASS["flashlight"])
    perto(with_lantern / free, math.sqrt(H.EFFECTIVE_ARM_MASS / (H.EFFECTIVE_ARM_MASS + H.ITEM_MASS["flashlight"])), 1e-9, "raiz de M / (M + m)")
    assert 2.0 * math.pi * 3.0 <= free <= 2.0 * math.pi * 5.0, "dentro da faixa de 3 a 5 Hz da estimativa"
    for modo in (WALK, RUN, CROUCH):
        assert 0.4 <= H.damping_ratio(modo) <= 0.7, "razão de amortecimento de 0,4 a 0,7"
        assert 2.0 * math.pi * 3.0 <= H.natural_frequency(modo, 0.0) <= 2.0 * math.pi * 5.0
    assert H.natural_frequency(RUN, 0.0) > H.natural_frequency(WALK, 0.0), "correndo o braço fica mais rígido"


def test_breath_and_drift_in_degrees_and_fatigue_triples_the_drift():
    hand = H.CarryHand(1.0, 0)
    rest = np.array([hand.rotation(k * 0.05, 0.0, 0.0, WALK, 2.0 * math.pi * 0.25 * k * 0.05, 0.0, 0.0) for k in range(int(300 / 0.05))])
    assert 0.20 < np.abs(rest[:, 0]).max() < 0.34, f"inclinação parada: {np.abs(rest[:, 0]).max():.3f} graus (respiração 0,20 + deriva 0,10)"
    tired = np.array([hand.rotation(k * 0.05, 0.0, 0.0, WALK, 2.0 * math.pi * 0.65 * k * 0.05, 1.0, 1.0) for k in range(int(300 / 0.05))])
    assert 0.6 < np.abs(tired[:, 0]).max() < 0.95, f"sem fôlego: {np.abs(tired[:, 0]).max():.3f} graus"
    drift_rest = np.array([H.drift_angles(k * 0.05, 0, 0.0) for k in range(int(600 / 0.05))])
    drift_tired = np.array([H.drift_angles(k * 0.05, 0, 1.0) for k in range(int(600 / 0.05))])
    ratio = np.abs(drift_tired).max(axis=0) / np.abs(drift_rest).max(axis=0)
    assert np.allclose(ratio, 1.0 + H.DRIFT_FATIGUE_GAIN, atol=1e-6), ratio
    assert np.abs(drift_rest).max() <= H.DRIFT_DEG * 1.0001 and np.abs(drift_rest).max() > 0.5 * H.DRIFT_DEG
    # a deriva é lenta: nada acima de 1 Hz (a mais rápida é a de 1,00 Hz) e sem tremor de 8 Hz
    freq = np.fft.rfftfreq(len(drift_rest), 0.05)
    spectrum = np.abs(np.fft.rfft(drift_rest[:, 0]))
    assert freq[np.argmax(spectrum)] < 1.0 and spectrum[freq > 1.2].max() < 0.05 * spectrum.max()


def test_wrist_cancels_part_of_the_head_wobble():
    hand = H.CarryHand(1.0, 0)
    base = hand.rotation(0.0, 0.0, 0.0, WALK, 0.0, 0.0, 0.0)
    wobble = hand.rotation(0.0, math.radians(2.0), math.radians(1.0), WALK, 0.0, 0.0, 0.0)
    perto(wobble[0] - base[0], -H.WRIST_STABILIZE["walk"] * 2.0, 1e-9, "inclinação cancelada")
    perto(wobble[2] - base[2], -H.WRIST_STABILIZE["walk"] * 1.0, 1e-9, "rolagem cancelada")
    assert wobble[1] == base[1], "a guinada é do feixe (Flashlight, 77 ms), não do punho"


def test_run_lifts_and_pulls_the_hand_in_gradually():
    hand = H.CarryHand(1.0)
    drive(hand, 0.05, lambda t: (0.0, 0.0, 0.0), weights=RUN)
    first = hand.mode_offset[1]
    drive(hand, 2.0, lambda t: (0.0, 0.0, 0.0), weights=RUN, start=0.05)
    assert first < 0.3 * H.RUN_OFFSET[1], "a mão sobe aos poucos (o cotovelo leva ~0,25 s para fechar)"
    perto(hand.mode_offset[1], H.RUN_OFFSET[1], 5e-4, "subida em regime")
    left = H.CarryHand(-1.0)
    drive(left, 2.0, lambda t: (0.0, 0.0, 0.0), weights=RUN)
    perto(left.mode_offset[0], -H.RUN_OFFSET[0], 5e-4, "o lado esquerdo aproxima da linha do corpo para o outro lado")


# --------------------------------------------------------------------------
# O jogo no referencial da câmera
# --------------------------------------------------------------------------
def game_and_cases():
    def build():
        from tools.movimento_ref.cenarios import maos_andando as M
        return M, M.preparar_jogo(palco=True)
    return memo("jogo", build)


def case(name, variant="depois", item=None):
    def record():
        from tools.movimento_ref.cenarios import maos_andando as M
        M_, game = game_and_cases()
        if item is not None:
            game = memo(("jogo", item), lambda: M_.preparar_jogo(palco=True, item_esquerda=item))
        return M_.gravar_caso(game, name, variant)
    return memo(("caso", name, variant, item), record)


def stats(name, key, variant="depois", window=None):
    from tools.movimento_ref.cenarios import maos_andando as M
    rec, extras = case(name, variant)
    ego = M.ego_do_jogo(rec, window or M.CASOS[name].janela)
    return M.estatisticas(ego[key])


def test_free_arm_swing_matches_cmu_at_the_same_speed():
    """Braço livre (esquerdo) a 1,7 m/s contra 08_01 a 08_03 (1,5 a 1,6 m/s): a amplitude do cotovelo e do punho dentro de 25%."""
    real = E_ref("andar_rapido")
    for joint, tolerance in (("cotovelo", 0.25), ("punho", 0.25)):
        game = stats("andar", (joint, "e"))
        for axis, name in ((1, "frente"), (2, "cima")):
            if real[joint]["e"]["amplitude"][axis] < 0.1:
                continue
            ratio = game["amplitude"][axis] / real[joint]["e"]["amplitude"][axis]
            assert 1 - tolerance <= ratio <= 1 + tolerance, f"{joint} {name}: jogo/real = {ratio:.2f}"
    wrist = stats("andar", ("punho", "e"))
    perto(wrist["freq_frente"], 1.0, 0.13, "frequência do balanço do punho livre (a passada)")


def E_ref(category):
    from tools.movimento_ref.cenarios import maos_andando as M
    return M.referencia(category)


def test_shoulder_moves_like_the_real_one():
    """O ombro em relação à câmera (a base da mão): amplitudes dentro de 50% da CMU na mesma velocidade, frequência de uma passada."""
    real = E_ref("andar_rapido")["ombro"]["d"]
    shoulder = stats("andar", ("ombro", "d"))
    for axis in range(3):
        ratio = shoulder["amplitude"][axis] / max(real["amplitude"][axis], 1e-3)
        assert 0.6 <= ratio <= 1.6, f"ombro, eixo {axis}: jogo/real = {ratio:.2f}"
    assert 0.8 <= shoulder["freq_cima"] <= 1.2, shoulder["freq_cima"]


def test_carried_hand_moves_a_few_centimeters_and_stays_in_the_frame():
    """A palma da lanterna: poucos centímetros por eixo, em ritmo de passada ou de passo, sempre no quadro andando e a maior parte do
    tempo correndo. Sem referência real para uma lanterna na mão (ESTIMADO): a faixa é a da pesquisa, 1 a 5 cm, e o ombro real."""
    from tools.movimento_ref.cenarios import maos_andando as M
    walk = stats("andar", ("alvo", "d"))
    assert np.all(walk["amplitude"] > 0.008) and np.all(walk["amplitude"] < 0.06), walk["amplitude"]
    assert 0.8 <= walk["freq_cima"] <= 2.3, walk["freq_cima"]
    run = stats("correr", ("alvo", "d"))
    assert np.all(run["amplitude"] < 0.09), run["amplitude"]
    crouch = stats("agachado", ("alvo", "d"))
    assert np.all(crouch["amplitude"] < 0.5 * np.maximum(walk["amplitude"], 0.01)), "agachado a mão balança menos que andando"
    rec, extras = case("andar")
    lens = M.lente_ego(extras, M.CASOS["andar"].janela)
    assert E.dentro_do_campo(lens) > 0.99, "a lente da lanterna fica no quadro andando"
    rec, extras = case("correr")
    lens = M.lente_ego(extras, M.CASOS["correr"].janela)
    assert E.dentro_do_campo(lens) > 0.95, "e correndo"


def test_run_is_different_from_walk():
    walk, run = stats("andar", ("alvo", "d")), stats("correr", ("alvo", "d"))
    assert run["media"][2] > walk["media"][2] + 0.02, "correndo a mão sobe (o cotovelo fecha)"
    assert run["media"][1] < walk["media"][1] - 0.01, "e chega mais perto do corpo"


def test_start_pushes_the_hand_back_and_stop_lets_it_go_on():
    from tools.movimento_ref.cenarios import maos_andando as M
    _, start = case("arrancar")
    a, b = int(1.4 * 60), int(2.6 * 60)
    peak_back = start["extensao"][a:b, 2].max()                 # z da câmera aponta para trás
    assert 0.003 < peak_back < 0.06, f"ao arrancar a mão fica {peak_back * 100:.1f} cm para trás"
    _, stop = case("parar")
    a = int(3.0 * 60)
    peak_forward = -stop["extensao"][a:a + 90, 2].min()
    assert 0.003 < peak_forward < 0.06, f"ao parar a mão segue {peak_forward * 100:.1f} cm adiante"
    settled = np.abs(stop["extensao"][int(4.6 * 60):int(5.8 * 60)]).max()
    assert settled < 0.003, f"e assenta ({settled * 1000:.1f} mm de sobra)"


def test_turning_the_mouse_trunk_lags_the_head_and_the_hand_follows_the_chest():
    from tools.movimento_ref.cenarios import maos_andando as M
    rec, extras = case("giro")
    omega = 180.0
    lag = extras["atraso"].max()
    tau = lag / omega
    assert 0.07 <= tau <= 0.17, f"atraso do tronco atrás do olhar: {tau * 1000:.0f} ms (MEDIDO na fase 4: 70 a 170 ms)"
    lateral = extras["deslocamento"][:, 0].max()
    assert 0.015 < lateral < 0.08, f"a mão varre {lateral * 100:.1f} cm para o lado oposto ao giro"
    assert extras["deslocamento"][:, 0].min() > -0.03, "e não para o lado errado"
    _, walking = case("giro_andando")
    assert walking["atraso"].max() < lag, "andando o corpo acompanha mais depressa (a taxa cresce com a passada)"


def test_looking_down_the_free_arm_swings_like_the_real_one_and_does_not_jump():
    """Cotovelo e punho esquerdos com a cabeça a 30, 45, 60 e 75 graus para baixo: amplitude contra a CMU girada, e sem salto de
    velocidade (a velocidade máxima fica abaixo de 1,15 vez a do percentil 99: o braço é sempre o mesmo, só a câmera gira)."""
    from tools.movimento_ref.cenarios import maos_andando as M
    clips = ("08_01", "08_02", "08_03")
    for degrees in (30, 45, 60, 75):
        name = f"olhar_{degrees}"
        rec, _ = case(name)
        ego = M.ego_do_jogo(rec, M.CASOS[name].janela)
        for joint in ("cotovelo", "punho"):
            game = M.estatisticas(ego[(joint, "e")])
            real = M.estatisticas(M.real_rotacionado(clips, joint, "e", degrees))
            for axis in (1, 2):
                if real["amplitude"][axis] > 0.1:
                    ratio = game["amplitude"][axis] / real["amplitude"][axis]
                    assert 0.7 <= ratio <= 1.3, f"{degrees} graus, {joint}, eixo {axis}: jogo/real = {ratio:.2f}"
            speed = np.linalg.norm(np.diff(ego[(joint, "e")], axis=0), axis=1) * 60.0
            assert speed.max() < 1.15 * np.percentile(speed, 99), f"salto de velocidade no {joint} a {degrees} graus"
    rec, _ = case("olhar_75")
    wrist = M.estatisticas(M.ego_do_jogo(rec, M.CASOS["olhar_75"].janela)[("punho", "e")])
    assert wrist["no_campo"] > 0.15, "olhando 75 graus para baixo o punho livre entra no quadro"


def test_rest_breath_and_fatigue_in_the_hand_at_rest():
    from tools.movimento_ref.cenarios import maos_andando as M
    rec, extras = case("parado")
    a, b = 60, len(extras["rotacao"])
    pitch = np.ptp(extras["rotacao"][a:b, 0])
    assert 0.25 < pitch < 0.9, f"inclinação do feixe parado: {pitch:.2f} graus pico a pico"
    assert np.ptp(extras["deslocamento"][a:b], axis=0).max() < 0.004, "parado a mão não se mexe em centímetros"
    game, _ = game_and_cases()
    assert game is not None


def test_key_pendulum_swings_with_the_world_acceleration_of_the_pivot():
    """O chaveiro na mão esquerda andando: o ângulo que o jogo calcula bate com um pêndulo independente excitado pela aceleração
    MUNDIAL da palma (segunda diferença da posição da palma, projetada nos eixos da câmera)."""
    from sem_alvorada import conventions as C
    from sem_alvorada.engine.handheld import compound_pendulum  # noqa: F401
    from tools.movimento_ref.cenarios import maos_andando as M
    rec, extras = case("andar", item=C.ITEM_KEY)
    a, b = int(2.0 * 60), int(6.0 * 60)
    angles = extras["pendulo"][a:b]
    assert np.ptp(angles[:, 1]) > math.radians(1.0), "o chaveiro balança andando"
    frequency = E.frequencia_dominante(angles[:, 1], 60.0, 0.5, 4.0)
    assert 0.8 <= frequency <= 2.3, f"no ritmo da passada ou do passo: {frequency} Hz"
    palm = rec.palma[:, 0]
    axes = rec.camera_rot
    accel = np.zeros((len(palm), 3))
    accel[2:] = (palm[2:] - 2 * palm[1:-1] + palm[:-2]) * 3600.0
    lateral = np.einsum("ti,ti->t", accel, axes[:, :, 0])
    forward = -np.einsum("ti,ti->t", accel, axes[:, :, 2])
    length = 0.154
    omega0 = math.sqrt(9.81 / length)
    series = {}
    for index, drive_axis in enumerate((lateral, forward)):
        theta = speed = 0.0
        out = []
        for value in np.clip(drive_axis, -14.0, 14.0):
            for _ in range(4):
                acceleration = -omega0 ** 2 * math.sin(theta) - 2 * 0.08 * omega0 * speed - value / length * math.cos(theta)
                speed += acceleration * (1 / 240)
                theta += speed * (1 / 240)
            out.append(theta)
        series[index] = np.array(out)[a:b]
    corr = np.corrcoef(series[1] - series[1].mean(), angles[:, 1] - angles[:, 1].mean())[0, 1]
    assert corr > 0.7, f"correlação do balanço para a frente com o pêndulo independente: {corr:.2f}"


def test_hands_accept_the_old_model_as_a_drop_in():
    from tools.movimento_ref.cenarios import maos_andando as M
    antes, _ = case("andar", variant="antes")
    depois, _ = case("andar", variant="depois")
    a = M.estatisticas(M.ego_do_jogo(antes, M.CASOS["andar"].janela)[("alvo", "d")])
    d = M.estatisticas(M.ego_do_jogo(depois, M.CASOS["andar"].janela)[("alvo", "d")])
    assert a["amplitude"][1] < 0.002, "a mola de antes não mexia a mão para a frente e para trás"
    assert d["amplitude"][1] > 0.01, "o modelo novo mexe"


TESTS = [
    test_vertical_bob_matches_the_transmissibility_law, test_constant_velocity_leaves_no_lag,
    test_start_peak_matches_the_step_response, test_stop_continues_forward_then_settles, test_heel_strike_impulse_response,
    test_the_extension_is_a_world_vector_when_the_camera_turns, test_teleport_is_not_an_impulse,
    test_highpass_keeps_the_gait_and_drops_the_posture, test_lever_shift_follows_the_chest_and_has_the_right_sign,
    test_natural_frequency_falls_with_the_item_mass, test_breath_and_drift_in_degrees_and_fatigue_triples_the_drift,
    test_wrist_cancels_part_of_the_head_wobble, test_run_lifts_and_pulls_the_hand_in_gradually,
    test_free_arm_swing_matches_cmu_at_the_same_speed, test_shoulder_moves_like_the_real_one,
    test_carried_hand_moves_a_few_centimeters_and_stays_in_the_frame, test_run_is_different_from_walk,
    test_start_pushes_the_hand_back_and_stop_lets_it_go_on,
    test_turning_the_mouse_trunk_lags_the_head_and_the_hand_follows_the_chest,
    test_looking_down_the_free_arm_swings_like_the_real_one_and_does_not_jump, test_rest_breath_and_fatigue_in_the_hand_at_rest,
    test_key_pendulum_swings_with_the_world_acceleration_of_the_pivot, test_hands_accept_the_old_model_as_a_drop_in,
]


def main():
    failures = 0
    for test in TESTS:
        try:
            test()
            print(f"ok      {test.__name__}")
        except Exception as error:      # noqa: BLE001
            failures += 1
            import traceback
            print(f"FALHOU  {test.__name__}: {error!r}")
            traceback.print_exc()
    total = len(TESTS)
    print(f"{total - failures}/{total} testes das mãos que andam passaram")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
