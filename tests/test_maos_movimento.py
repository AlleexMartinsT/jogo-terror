"""Testes do movimento das mãos, dos itens e da lanterna contra o mocap real (CMU) e contra as leis da física.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_maos_movimento.py

Tolerâncias e a fonte de cada número estão em `tools/movimento_ref/cenarios/maos.py` e em
`assets/referencia/maos_ref.json` (MEDIDO nos clipes da CMU; os testes não precisam dos clipes, só do JSON). O que vem de
física é DERIVADO e conferido por uma integração numérica independente; o que é de engenharia é ESTIMADO e está marcado.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import numpy as np  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.engine import flashlight as flashlight_module  # noqa: E402
from sem_alvorada.engine import handclips as K  # noqa: E402
from sem_alvorada.engine import handheld, handtrack  # noqa: E402
from tools.movimento_ref import metricas  # noqa: E402
from tools.movimento_ref.cenarios import maos, maos_tabela  # noqa: E402

REF = maos.referencia()
_CACHE = {}


def memo(chave, fabrica):
    if chave not in _CACHE:
        _CACHE[chave] = fabrica()
    return _CACHE[chave]


def perto(valor, esperado, tolerancia, nome):
    assert abs(valor - esperado) <= tolerancia, f"{nome}: {valor:.4f}, esperado {esperado:.4f} +- {tolerancia}"


# --------------------------------------------------------------------------
# Executor: jerk mínimo (sem jogo)
# --------------------------------------------------------------------------
def test_stop_to_stop_motion_is_minimum_jerk():
    """Entre duas chaves paradas o perfil é o de jerk mínimo: pico a 50% da duração e 1,875 vezes a velocidade média."""
    curva = handtrack.track((0.0, (0.0, 0.0, 0.0), "stop"), (0.8, (0.3, 0.4, 0.0), "stop"))
    t = np.arange(0.0, 0.8, 1e-3)
    pos = np.array([curva.sample(x) for x in t])
    v = np.linalg.norm(np.gradient(pos, 1e-3, axis=0), axis=1)
    perto(t[np.argmax(v)] / 0.8, 0.5, 0.01, "pico em fração da duração")
    perto(v.max() / (0.5 / 0.8), 1.875, 0.01, "pico / velocidade média")
    assert abs(v[0]) < 1e-2 and abs(v[-1]) < 1e-2, "parte e chega parado"
    modelo = metricas.jerk_minimo(0.5, 0.8, 1000.0)[:len(v)]
    n = min(len(modelo), len(v))
    assert np.corrcoef(v[:n], modelo[:n])[0, 1] > 0.9999, "idêntico ao modelo de metricas.jerk_minimo"


def test_rotation_tracks_follow_the_same_phase_as_positions():
    """Ombro, cotovelo e punho em fase: a rotação anda com o mesmo perfil da posição (mesma fase em cada instante)."""
    pos = handtrack.track((0.0, 0.0, "stop"), (0.6, 1.0, "stop"))
    rot = handtrack.QuatTrack([handtrack.Key(0.0, (1.0, 0.0, 0.0, 0.0), True), handtrack.Key(0.6, (math.cos(0.5), math.sin(0.5), 0.0, 0.0), True)])
    for t in np.linspace(0.0, 0.6, 25):
        fase_pos = pos.sample(t)[0]
        w, x = rot.sample(t)[:2]
        angulo = 2.0 * math.atan2(abs(x), w)              # 0 .. 1 rad
        perto(angulo / 1.0, fase_pos, 0.02, f"fase da rotação em t={t:.2f}")


def test_through_keys_never_overshoot_and_stay_c1():
    curva = handtrack.track((0.0, 0.0, "stop"), (0.4, 0.5), (0.8, 1.0, "stop"), (1.0, 1.0, "stop"), (1.5, 0.0, "stop"))
    amostras = [curva.sample(i / 500.0)[0] for i in range(751)]
    assert min(amostras) >= -1e-9 and max(amostras) <= 1.0 + 1e-9
    v = np.diff(amostras) * 500.0
    assert np.max(np.abs(np.diff(v))) < 0.2, "velocidade contínua (sem degraus)"


# --------------------------------------------------------------------------
# Lei de tempo dos movimentos e dos clipes
# --------------------------------------------------------------------------
def test_movement_time_law_matches_the_measured_regression():
    lei = REF["lei_do_alcance"]
    assert lei["n"] >= 150, "a lei sai de dezenas de clipes e de 150 alcances ou mais"
    for distancia in (0.4, 0.6, 0.8):
        nominal = K.move_time(distancia)
        t6_da_lei = lei["a"] + lei["b"] * distancia / K.ARM_LENGTH
        perto(nominal * 0.869, t6_da_lei, 0.02, f"duração a 6% de {distancia} m")
    assert K.move_time(0.05) < K.move_time(0.3) < K.move_time(0.7), "mais longe leva mais tempo"
    assert K.move_time(0.0) == K.MOVE_MIN
    assert abs(K.move_time(K.MEASURED_FROM * K.ARM_LENGTH) - (K.MOVE_A + K.MOVE_B * K.MEASURED_FROM)) < 1e-9, "contínua na emenda"


def test_every_reach_in_every_pickup_clip_uses_the_law():
    for fabrica in (K.lantern_first, K.battery_pickup, K.key_pickup, K.map_pickup, K.note_pickup):
        for alcance in (0.55, 0.9):
            clip = fabrica(alcance)
            chaves = clip.tracks[f"{clip.meta['side']}.pos"].keys
            primeira_parada = next(k for k in chaves if k.stop)
            perto(primeira_parada.t, alcance, 1e-9, f"{clip.name}: o contato chega à duração do alcance")
            assert primeira_parada.space == "grasp" and chaves[0].space == "rest", "do braço solto ao ponto de pegar"


def test_pickups_are_shorter_than_the_old_worst_case_and_reach_has_the_real_duration():
    assert K.lantern_first().duration < 2.88, "a primeira lanterna não ficou mais longa que a de antes (2,88 s)"
    for fabrica in (K.lantern_first, K.battery_pickup, K.key_pickup, K.map_pickup):
        assert fabrica().duration < 3.3
    assert 0.6 <= K.REACH_DEFAULT <= 1.0, K.REACH_DEFAULT


# --------------------------------------------------------------------------
# Gestos de pegar no jogo
# --------------------------------------------------------------------------
def gestos():
    return memo("gestos", maos_tabela.medir_gestos)


def test_reach_duration_peak_and_shape_within_the_measured_band():
    lei, forma = REF["lei_do_alcance"], REF["forma_do_alcance"]
    for nome, g in gestos().items():
        assert "t6" in g, f"{nome}: nenhum alcance detectado"
        esperado = lei["a"] + lei["b"] * g["distancia"] / maos.BRACO_DANIEL
        perto(g["t6"], esperado, 0.25, f"{nome}: duração a 6% (D={g['distancia']:.2f} m)")
        perto(100 * g["pico_fracao"], 100 * lei["pico_fracao"][0], 2 * 100 * lei["pico_fracao"][1], f"{nome}: pico em % da duração (dois desvios do real)")
        perto(g["pico_razao"], 1.875, 0.35, f"{nome}: pico / média")
        assert g["r2"] > 0.7, f"{nome}: R2 do jerk mínimo {g['r2']:.2f}"
    medio = np.mean([g["pico_razao"] for g in gestos().values()])
    perto(medio, forma["pico_razao"][0], 0.25, "pico / média médio contra o real")


def test_the_hand_never_pauses_in_the_middle_of_a_reach():
    """Um alcance é um sino só: a velocidade do punho não tem vale a meio caminho (antes havia dois picos)."""
    for nome, g in gestos().items():
        v = np.array(g["perfil"])
        n = len(v)
        meio = v[int(0.25 * n):int(0.75 * n)]
        assert meio.min() > 0.55 * v.max(), f"{nome}: a velocidade cai a {meio.min() / v.max():.2f} do pico no meio do alcance"


def test_elbow_stays_out_of_the_middle_of_the_screen():
    for nome, g in gestos().items():
        assert g["cotovelo_no_centro"] == 0, f"{nome}: o cotovelo ficou {g['cotovelo_no_centro']} quadros no meio da tela"


def test_wrist_never_bends_past_what_a_wrist_can():
    """O pulso real dobra até ~70 graus somando flexão e desvio; o solver comprime acima de 55 e nunca passa de 72
    (antes encostava no limite de 80, e a manga ficava apertada no punho)."""
    for nome, g in gestos().items():
        assert g["dobra_do_pulso"] <= 73.0, f"{nome}: pulso dobrado a {g['dobra_do_pulso']:.0f} graus"
    assert memo("postura", maos_tabela.medir_posicao_de_segurar)["dobra_do_pulso"] <= 73.0


def test_pickup_gestures_are_not_longer_than_the_busy_limit():
    for nome, g in gestos().items():
        assert g["duracao_total"] < 3.3, f"{nome}: a mão ficou {g['duracao_total']:.2f} s sem controle"


# --------------------------------------------------------------------------
# Lanterna na mão: postura, atraso do feixe, lâmpada
# --------------------------------------------------------------------------
def test_flashlight_arm_posture_follows_the_capture():
    medido = ref = REF["lanterna"]
    postura = memo("postura", maos_tabela.medir_posicao_de_segurar)
    perto(postura["cotovelo"], ref["cotovelo"], 15.0, "flexão do cotovelo")
    perto(postura["elevacao"], ref["elevacao"], 18.0, "braço em relação à vertical")
    perto(postura["razao"], ref["razao"], 0.10, "distância punho-ombro / braço")
    assert medido["cotovelo"] > 100.0


def test_beam_lag_matches_the_head_to_arm_latency_of_a_real_look_around():
    jogo = maos.montar_jogo_maos()
    tau = maos.medir_atraso_do_feixe(jogo)
    perto(tau, REF["lanterna"]["tau_ms"], 25.0, "constante de tempo do feixe (ms)")
    perto(tau, 1000.0 / flashlight_module.SWAY_FOLLOW, 8.0, "tau = 1 / SWAY_FOLLOW")


def test_lamp_ramps_like_a_filament_and_flicker_is_millisecond_bursts():
    jogo = maos.montar_jogo_maos()
    subida, descida = maos.medir_filamento(jogo)
    assert 20.0 <= subida <= 80.0, f"subida de {subida:.0f} ms (ESTIMADO 20 a 80)"
    assert 20.0 <= descida <= 100.0, f"descida de {descida:.0f} ms"
    jogo = maos.montar_jogo_maos()
    maior, quedas, fundo = maos.medir_piscada(jogo)
    assert maior <= 60.0, f"abertura de {maior:.0f} ms: pulso longo, não mau contato"
    assert quedas >= 1 and fundo < 0.5, (quedas, fundo)
    # o comportamento de jogo continua: carga ao encontrar e de 2 a 4 piscadas (test_hands cobre o gesto inteiro)
    assert abs(C.FLASHLIGHT_FOUND_CHARGE - 0.78) < 1e-9 and 2 <= len(K.FLICKER_BURSTS) <= 4


def test_flicker_current_has_only_short_openings():
    aberturas = [(b - a) * 0.15 for a, b in flashlight_module.CHATTER]
    assert max(aberturas) * 1000 < 60.0 and len(aberturas) >= 2
    # a média por quadro conserva a carga: o quadro de 100 ms que contém a rajada inteira vê (comprimento - aberturas) / 100 ms
    comprimento = 0.13
    media = flashlight_module.burst_average(0.0, comprimento, comprimento)
    esperado = 1.0 - sum(b - a for a, b in flashlight_module.CHATTER) + (flashlight_module.BURST_SURGE - 1.0) * flashlight_module.BURST_SURGE_TIME / comprimento
    perto(media, esperado, 1e-9, "média da corrente da rajada")


# --------------------------------------------------------------------------
# Chaveiro (pêndulo composto), folha e mapa
# --------------------------------------------------------------------------
def test_keychain_is_a_compound_pendulum_checked_by_an_independent_integration():
    jogo = maos.montar_jogo_maos()
    malha = jogo.hands.models.objects[C.ITEM_KEY].data
    info = handheld.compound_pendulum(malha)
    # conferência da massa e da inércia por fora do módulo: soma ponto a ponto a partir dos polígonos
    nomes = [m.name for m in malha.materials]
    area = {}
    for p in malha.polygons:
        area[nomes[p.material_index]] = area.get(nomes[p.material_index], 0.0) + p.area
    massa = inercia = com_y = 0.0
    for p in malha.polygons:
        n = nomes[p.material_index]
        m = handheld.KEY_MASS_G.get(n, 0.0) * 1e-3 * p.area / area[n]
        massa += m
        com_y += m * p.center.y
        inercia += m * (p.center.x ** 2 + p.center.y ** 2)
    d = -com_y / massa
    perto(info["mass"], massa, 1e-9, "massa")
    perto(info["length_roll"], inercia / (massa * d), 1e-6, "comprimento equivalente L = I / (m d)")
    assert 0.08 <= info["length_roll"] <= 0.20, "um chaveiro de 3 cm de pegada pende como um pêndulo de 8 a 20 cm"
    # o engine usa esse comprimento
    perto(jogo.hands.pendulum.lengths[0], info["length_roll"], 1e-9, "Pendulum.lengths")
    # período de pequenas oscilações: 2 pi raiz(L / g)
    t, theta = maos.medir_pendulo_do_engine(jogo, angulo0=0.05, duracao=8.0)
    periodo, zeta = maos.periodo_e_decaimento(t, theta)
    perto(periodo, 2 * math.pi * math.sqrt(info["length_roll"] / maos.G), 0.02, "período do engine")
    # integração independente (RK4 do corpo rígido, a partir de I, m e d) com a mesma razão de amortecimento
    ti, thi = maos.pendulo_independente(info["inertia_roll"], info["mass"], info["d"], jogo.hands.pendulum.damping_ratio, 0.2)
    periodo_i, zeta_i = maos.periodo_e_decaimento(ti, thi)
    t2, th2 = maos.medir_pendulo_do_engine(jogo, angulo0=0.2, duracao=6.0)
    periodo_e, zeta_e = maos.periodo_e_decaimento(t2, th2)
    perto(periodo_e / periodo_i, 1.0, 0.03, "período engine / integração independente (amplitude 11 graus)")
    perto(zeta_e, zeta_i, 0.01, "amortecimento engine contra integração independente")
    # amplitude finita: o período cresce ~ (1 + a^2 / 16) e o engine acompanha
    grande = maos.medir_pendulo_do_engine(jogo, angulo0=1.0, duracao=8.0)
    periodo_g, _ = maos.periodo_e_decaimento(*grande)
    ti3, thi3 = maos.pendulo_independente(info["inertia_roll"], info["mass"], info["d"], jogo.hands.pendulum.damping_ratio, 1.0, duracao=8.0)
    perto(periodo_g / maos.periodo_e_decaimento(ti3, thi3)[0], 1.0, 0.03, "período a 57 graus")


def test_paper_is_a_cantilever_with_inertia():
    folha = handheld.PaperSheet(0.16)
    esperado = maos.frequencia_da_folha_teorica(0.16)
    perto(folha.omega, esperado, 1e-9, "primeiro modo da viga em balanço")
    # no regime linear (carga pequena) a flecha é rho a L^4 / (8 EI)
    carga = 0.2
    perto(folha.target(carga), maos.flecha_da_folha_teorica(0.16, carga), 0.002, "flecha estática")
    # saturação: nunca passa de 55% do comprimento
    assert folha.target(100.0) <= handheld.PaperSheet.MAX_SAG * 0.16 + 1e-9
    # inércia: a ponta não acompanha de uma vez, e uma folha maior é mais lenta
    for _ in range(3):
        folha.step(1 / 60, 9.81)
    assert 0.0 < folha.value < folha.target(9.81), "sobe com atraso"
    assert handheld.PaperSheet(0.29).omega < handheld.PaperSheet(0.085).omega


def test_held_note_droops_by_inertia_through_the_model_shape_key():
    from sem_alvorada.engine.inputstate import InputState
    jogo = maos.montar_jogo_maos()
    maos.estado(jogo, notas=("NOTE_1",), segurar=C.ITEM_NOTE)
    obj = jogo.hands.models.objects[C.ITEM_NOTE]
    assert obj.data.shape_keys is not None and "Droop" in obj.data.shape_keys.key_blocks, "o modelo da folha tem a chave Droop"
    valores = []
    for _ in range(120):
        jogo.tick(1 / 60, InputState())
        valores.append(obj.data.shape_keys.key_blocks["Droop"].value)
    assert max(abs(v) for v in valores) > 0.004, "a gravidade dobra a folha presa pela borda"
    assert max(abs(v) for v in valores) < 0.8 * jogo.hands.models.sheet.length, "a flecha satura (com o sobressalto do amortecimento de 0,35)"
    # sem a nota na mão a folha volta reta
    jogo.hands.equip(None)
    for _ in range(120):
        jogo.tick(1 / 60, InputState())
    assert abs(obj.data.shape_keys.key_blocks["Droop"].value) < 1e-9


def test_map_panels_open_with_a_spring_and_settle():
    mola = handheld.FoldSpring(19.0)
    mola.step(0.0, 174.0)
    valores = [mola.step(1 / 60, 0.0) for _ in range(120)]
    assert valores[0] < 174.0 and valores[2] < valores[0], "começa a abrir"
    assert abs(valores[-1]) < 1.0, "assenta no aberto"
    assert min(valores) > -0.2 * 174.0, "passa pouco do ponto (sobressalto pequeno)"


# --------------------------------------------------------------------------
# Troca de pilhas e dedos
# --------------------------------------------------------------------------
def test_battery_swap_hands_in_phase_and_clear_of_the_flashlight():
    troca = memo("troca", maos_tabela.medir_troca)
    folga = memo("folga", maos_tabela.medir_folga_da_troca)
    assert 1.4 <= troca["duracao"] <= 2.3, troca["duracao"]
    assert troca["defasagem_inicio"] < 0.1, f"as mãos saem com {1000 * troca['defasagem_inicio']:.0f} ms de diferença"
    assert folga >= 12.0, f"a palma esquerda chegou a {folga:.1f} mm do corpo da lanterna (meia espessura da palma: 12 mm)"


def test_thumb_is_not_over_abducted_and_fingers_close_in_cascade():
    dedos = maos_tabela.medir_dedos()
    for chave in ("polegar_aberta", "polegar_concha"):
        assert 20.0 <= dedos[chave] <= 50.0, f"{chave}: {dedos[chave]:.0f} graus (relaxado: 30 a 40)"
    cascata = maos_tabela.medir_cascata()["cascata_ms"]
    assert 20.0 <= cascata <= 100.0, f"a ponta do dedo atrasa {cascata:.0f} ms da base ao fechar"


def test_finger_rotations_still_work_without_joint_curls():
    from sem_alvorada.body import fingers as F
    a = F.finger_rotations("R", (0.5, 0.4, 0.3, 0.2, 0.1), 0.2)
    b = F.finger_rotations("R", (0.5, 0.4, 0.3, 0.2, 0.1), 0.2, [[c, c, c] for c in (0.5, 0.4, 0.3, 0.2, 0.1)])
    assert set(a) == set(b) and all(a[k].rotation_difference(b[k]).angle < 1e-6 for k in a)
    assert len(a) == 15


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
    print(f"{len(testes) - falhas}/{len(testes)} testes do movimento das mãos passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
