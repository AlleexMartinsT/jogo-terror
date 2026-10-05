"""Trava o movimento dos objetos do jogo dentro das tolerâncias do modelo físico (fase 4, agente 4).

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_objetos_fisica.py

Os modelos físicos estão em tools/movimento_ref/fisica/ (código independente, sem importar `sem_alvorada`); o jogo é gravado
sem janela por `grava.py` e cada métrica tem uma faixa (DERIVADO de uma lei, ESTIMADO de engenharia, MEDIDO de mocap da CMU).
Cada teste imprime a tabela do seu objeto e falha se alguma métrica sair da faixa.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from sem_alvorada.engine import clockwork, doors as door_module, lights  # noqa: E402
from tools.movimento_ref.fisica import carro as K  # noqa: E402
from tools.movimento_ref.fisica import (comparar_ambiente, comparar_carro, comparar_porta, comparar_relogio, grava,  # noqa: E402
                                        luz, medidas, porta as P, relogio as R)


def exigir(lista, grupos=None):
    erradas = [m for m in lista if not m.ok and (grupos is None or m.grupo in grupos)]
    if erradas:
        print(medidas.tabela_markdown(erradas))
    assert not erradas, [f"{m.grupo}: {m.nome} jogo={m.jogo:.4g} faixa=[{m.lo:.4g}, {m.hi:.4g}]" for m in erradas]


# --------------------------------------------------------------------------
# Os modelos independentes batem com as leis e entre si
# --------------------------------------------------------------------------
def test_door_physics_closed_forms():
    assert abs(P.inercia(25.0) - 25.0 * 0.88 ** 2 / 3.0) < 1e-12
    assert abs(P.forca_pico_jerk_minimo(1.1, 25.0) - 61.1) < 1.0
    assert abs(P.tempo_minimo(100.0, 25.0) - 0.858) < 0.01
    t, theta, *_ = P.trajetoria_minima_variacao_de_torque(1.1, 25.0)
    x, _, _ = P.jerk_minimo(t / 1.1)
    assert np.max(np.abs(theta / P.ABERTURA - x)) < 1e-3, "com atrito pequeno o ótimo de torque é o jerk mínimo"
    _, t_chegada, w, ponta = P.golpe_de_porta()
    assert 0.35 < t_chegada < 0.5 and 3.0 < ponta < 5.0, (t_chegada, ponta)


def test_game_door_constants_match_the_independent_model():
    """O jogo e o modelo repetem as constantes de propósito (o modelo não importa o jogo): aqui elas não podem divergir."""
    assert door_module.HINGE_MU == P.MU_DOBRADICA and door_module.HINGE_RADIUS == P.RAIO_ATRITO
    assert door_module.HINGE_VISCOUS == P.VISCOSO
    assert door_module.FORCE_COMFORT == P.F_CONFORTO and door_module.FORCE_REVERSE == P.F_REVERTER
    assert door_module.FORCE_SLAM == P.F_PICO and door_module.RESTITUTION == P.RESTITUICAO
    assert abs(door_module.AIR_DRAG * 0.88 ** 4 - P.coeficiente_ar()) < 1e-9
    for nome, massa in P.MASSAS.items():
        assert door_module.KINDS[nome].mass == massa, nome


def test_pendulum_clock_physics():
    haste = R.comprimento_para_periodo(2.0)
    assert abs(R.comprimento_equivalente(haste) - 0.9937) < 1e-3, "pêndulo de segundos: l_eq = 0,994 m"
    assert abs(clockwork.EQUIVALENT_LENGTH - R.comprimento_equivalente(haste)) < 1e-3
    from sem_alvorada.props import clock
    assert abs(clock.PENDULUM_LENGTH - haste) < 0.002, "a haste do modelo 3D é a que dá T = 2 s"


def test_incandescent_filament_model():
    desliga, liga = luz.tempos_de_resposta()
    assert 0.03 < desliga < 0.08 and 0.07 < liga < 0.2, (desliga, liga)
    assert abs(luz.expoente_de_planck() - 9.26) < 0.1
    assert abs(lights.FILAMENT_TAU - luz.constante_de_tempo()) < 1e-3 and abs(lights.FILAMENT_N - luz.expoente_de_planck()) < 0.01


def test_car_physics_numbers():
    assert abs(K.tempo_0_a_100(K.potencia_para_10s()) - 10.0) < 0.05
    f_vertical, f_arfagem = K.frequencias_proprias()
    assert 1.0 <= f_vertical <= 1.5 and 1.0 <= f_arfagem <= 1.55
    assert abs(K.vibracao_marcha_lenta()[0] - 11.67) < 0.05
    assert abs(2 * K.RAIO_RODA - 0.668) < 0.01, "pneu 205/70R15 (D = 0,668 m; o modelo 3D usa R = 0,33)"


# --------------------------------------------------------------------------
# O jogo contra o modelo
# --------------------------------------------------------------------------
def test_doors_follow_the_physical_model():
    g = comparar_porta.gravar()
    lista = comparar_porta.metricas(g)         # o mocap vem de out/referencia/cmu (baixado uma vez); sem ele só pula essas linhas
    print(f"  portas: {sum(m.ok for m in lista)}/{len(lista)} métricas dentro da faixa")
    exigir(lista)


def test_all_thirteen_doors_open_within_hand_force_limits():
    g = comparar_porta.gravar()
    linhas = comparar_porta.tabela_13_portas(g)
    assert len(linhas) == 13
    for linha in linhas:
        assert linha["forca_apressado"] <= P.F_CONFORTO + 1.0, linha
        assert linha["dur_apressado"] >= linha["t_min_100N"] - 0.01, linha
        assert 0.9 <= linha["dur_normal"] <= 1.4 and 0.9 <= linha["dur_apressado"] <= 1.4, linha


def test_car_charm_wheels_and_garage_follow_the_physical_model():
    s, p = comparar_carro.gravar()
    lista = comparar_carro.metricas(s, p)
    print(f"  carro e portão: {sum(m.ok for m in lista)}/{len(lista)} métricas dentro da faixa")
    exigir(lista)


def test_curtains_dust_and_lights_follow_the_physical_model():
    g = comparar_ambiente.gravar()
    lista = comparar_ambiente.metricas(g)
    print(f"  cortina, poeira e luzes: {sum(m.ok for m in lista)}/{len(lista)} métricas dentro da faixa")
    exigir(lista)


def test_clock_follows_the_physical_model():
    lista = comparar_relogio.metricas(grava.relogio())
    print(f"  relógio: {sum(m.ok for m in lista)}/{len(lista)} métricas dentro da faixa")
    exigir(lista)


def test_clock_chime_waits_for_a_tick():
    mecanismo = clockwork.ClockWork(None)
    mecanismo.pendulum = grava.ObjetoFalso(clockwork.PENDULUM)
    mecanismo.sync()
    for _ in range(30):
        mecanismo.update(1 / 60)
    espera = mecanismo.next_tick_in()
    assert 0.0 <= espera <= 1.0
    assert abs(mecanismo.omega) > 0.0


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        print(fn.__name__)
        fn()
    print("test_objetos_fisica: OK")


if __name__ == "__main__":
    main()
