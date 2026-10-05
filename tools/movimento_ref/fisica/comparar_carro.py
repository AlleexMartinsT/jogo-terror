"""Carro, coelhinho, volante e portão da garagem: grava o jogo, roda o modelo físico e monta a tabela de métricas.

    python -m tools.movimento_ref.fisica.comparar_carro [--antes]
"""
import json
import math
import os
import sys

import numpy as np

from . import carro as K
from . import grava, medidas

Metrica = medidas.Metrica
GRUPO = "carro"
GRUPO_PORTAO = "portão"
RAIZ_DADOS = os.path.join(medidas.SAIDA, "tmp", "blend_dados.json")
# o código de antes (cópia em out/f4_4/tmp/anim.py) tinha estas molas; a gravação antiga não guardou o dado
SUSPENSAO_ANTES = {"f_vertical": 2.6, "f_arfagem": 1.9, "zeta": 0.30, "f_rolagem": 2.3, "zeta_rolagem": 0.28}


# --------------------------------------------------------------------------
# Geometria: as matrizes do Blender (euler XYZ: R = Rz Ry Rx)
# --------------------------------------------------------------------------
def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler_xyz(e):
    return _rz(e[2]) @ _ry(e[1]) @ _rx(e[0])


RODAS = {"FL": (-0.8, 1.45, 0.33), "FR": (0.8, 1.45, 0.33), "RL": (-0.8, -1.45, 0.33), "RR": (0.8, -1.45, 0.33)}


def _material_do_fundo(R_roda, R_carro):
    """Ponto do pneu (no espaço da roda) que está mais embaixo no mundo agora: o ponto de contato."""
    mundo_para_roda = (R_carro @ R_roda).T
    return mundo_para_roda @ np.array([0.0, 0.0, -K.RAIO_RODA])


def cubo(s, k, indice):
    """Posição da roda no espaço do carro no quadro k (a gravação antiga tinha os cubos fixos)."""
    if "roda_pos" in s:
        return np.array(s["roda_pos"][k, indice])
    return np.array(RODAS[("FL", "FR", "RL", "RR")[indice]])


def deslizamento_das_rodas(s):
    """Razão entre a velocidade horizontal do ponto de contato do pneu e a do centro da roda (0 = rola sem deslizar)."""
    fps, n = s["fps"], len(s["t"])
    quadros = np.arange(2, n - 2)
    parados = np.abs(np.gradient(s["pos"][:, 1], 1.0 / fps)) < 0.05
    razoes = []
    for lado, indice in (("FL", 0), ("RR", 3)):
        contato = np.zeros((n, 3))
        centro = np.zeros((n, 3))
        for k in range(n):
            Rc = euler_xyz(s["euler"][k])
            centro[k] = s["pos"][k] + Rc @ cubo(s, k, indice)
        # o ponto material é o que está embaixo no quadro k; a posição dele nos vizinhos usa a mesma coordenada local
        for k in quadros:
            Rc, Rw = euler_xyz(s["euler"][k]), euler_xyz(s["roda"][k, indice])
            ponto = _material_do_fundo(Rw, Rc)
            def mundo(j):
                return s["pos"][j] + euler_xyz(s["euler"][j]) @ (cubo(s, j, indice) + euler_xyz(s["roda"][j, indice]) @ ponto)
            contato[k] = (mundo(k + 1) - mundo(k - 1)) * fps / 2.0
        v_centro = np.gradient(centro, 1.0 / fps, axis=0)
        mover = (~parados)[quadros] & (np.linalg.norm(v_centro[quadros, :2], axis=1) > 0.3)
        razoes.append(float(np.sqrt(np.mean(np.sum(contato[quadros][mover][:, :2] ** 2, axis=1)))
                            / np.sqrt(np.mean(np.sum(v_centro[quadros][mover][:, :2] ** 2, axis=1)))))
    return max(razoes)


def razao_de_rolamento(s):
    """-(dtheta/dt) R / v_frente: 1 quando w = v/R no sentido certo (o giro em torno de +X é negativo para a frente)."""
    fps = s["fps"]
    giro = np.unwrap(s["roda"][:, 0, 0])
    w = np.gradient(giro, 1.0 / fps)
    v = s["sinais"]["speed"]
    mover = np.abs(v) > 0.5
    return float(np.median(-w[mover] * K.RAIO_RODA / v[mover]))


def folga_das_rodas_no_chao(s):
    """Maior |altura do fundo do pneu - altura do terreno| (m) das quatro rodas durante a saída."""
    fps, n = s["fps"], len(s["t"])
    pior = 0.0
    passo = max(1, int(fps // 30))
    for k in range(0, n, passo):
        Rc = euler_xyz(s["euler"][k])
        for indice in range(4):
            centro = s["pos"][k] + Rc @ cubo(s, k, indice)
            fundo = centro[2] - K.RAIO_RODA * math.cos(s["euler"][k][0]) * math.cos(s["euler"][k][1])
            pior = max(pior, abs(fundo - float(K.altura_do_chao(centro[1]))))
    return pior


def arfagem_do_jogo(s):
    return s["euler"][:, 0]


def referencia_do_carro(s):
    """O meio carro e o coelhinho do modelo independente, sobre o percurso analítico da cena (sem a correção de volante)."""
    t = s["t"]
    tempos = s["tempos"]
    total = s["parada"][1] - s["home"][1]
    percurso, _, a_mundo = K.percurso_jerk_minimo(t, tempos["move_start"], tempos["move_end"], total)
    y = s["home"][1] + percurso
    a_frente = -a_mundo                                        # o carro anda para -Y: frente = -Y
    z, theta, z_origem = K.suspensao(t, lambda x: np.interp(x, t, y), lambda x: np.interp(x, t, a_frente))
    return {"t": t, "y": y, "a_frente": a_frente, "theta": theta, "z_origem": z_origem}


def eixo_traseiro(s):
    """Posição (x, y) do centro do eixo traseiro ao longo da gravação."""
    return np.array([(s["pos"][k] + euler_xyz(s["euler"][k]) @ np.array([0.0, -K.ENTRE_EIXOS / 2.0, 0.0]))[:2]
                     for k in range(len(s["t"]))])


def curvatura_do_caminho(s):
    """Curvatura (1/m, positiva = esquerda) da trajetória do eixo traseiro: taxa de guinada / velocidade do eixo.

    Como o eixo traseiro anda para onde o carro aponta, a guinada medida é o rumo do caminho."""
    fps = s["fps"]
    v = np.linalg.norm(np.gradient(eixo_traseiro(s), 1.0 / fps, axis=0), axis=1)
    taxa = np.gradient(np.unwrap(s["euler"][:, 2]), 1.0 / fps)
    k = np.zeros_like(v)
    mover = v > 0.5
    k[mover] = taxa[mover] / v[mover]
    return k


def angulo_de_deriva(s):
    """Ângulo entre o eixo da frente do carro e a velocidade do centro do eixo traseiro (graus): zero se não derrapa."""
    v = np.gradient(eixo_traseiro(s), 1.0 / s["fps"], axis=0)
    yaw = s["euler"][:, 2]
    frente = np.stack([-np.sin(yaw), np.cos(yaw)], axis=1)
    rapido = np.linalg.norm(v, axis=1) > 0.3
    cos = np.sum(v * frente, axis=1) / np.maximum(np.linalg.norm(v, axis=1), 1e-9)
    return float(np.degrees(np.max(np.arccos(np.clip(cos[rapido], -1, 1)))))


def aceleracao_lateral_local(s):
    """Aceleração do centro na direção +X do carro (m/s2), a partir das posições gravadas."""
    fps = s["fps"]
    a = np.gradient(np.gradient(s["pos"][:, :2], 1.0 / fps, axis=0), 1.0 / fps, axis=0)
    yaw = s["euler"][:, 2]
    direita = np.stack([np.cos(yaw), np.sin(yaw)], axis=1)
    return np.sum(a * direita, axis=1)


def gradiente_de_rolagem(s):
    """Inclinação de rolagem por aceleração lateral (rad por m/s2), ajuste por mínimos quadrados: roll = -g a_lat."""
    janela = max(3, int(s["fps"] // 3))                        # média de 1/3 s: tira o tremor do motor e o ruído da derivada
    suave = lambda x: np.convolve(x, np.ones(janela) / janela, mode="same")      # noqa: E731
    v = np.gradient(eixo_traseiro(s), 1.0 / s["fps"], axis=0)
    a = suave(-np.sum(v ** 2, axis=1) * curvatura_do_caminho(s))      # aceleração centrípeta v^2 kappa, para o lado de dentro
    roll = suave(s["euler"][:, 1])
    mover = np.abs(s["sinais"]["speed"]) > 0.3
    a, roll = a[mover], roll[mover]
    return float(-(a @ roll) / (a @ a))


def vibracao_de_marcha_lenta(s):
    """(frequência dominante em Hz, aceleração vertical RMS em m/s2) do tremor com o motor ligado e o carro parado."""
    t, fps = s["t"], s["fps"]
    janela = (t > s["tempos"]["catch"] + 1.0) & (t < s["tempos"]["move_start"] - 0.2)
    z = s["pos"][janela, 2]
    z = z - np.mean(z)
    espectro = np.abs(np.fft.rfft(z * np.hanning(len(z))))
    freq = np.fft.rfftfreq(len(z), 1.0 / fps)
    alvo = freq > 3.0
    dominante = float(freq[alvo][np.argmax(espectro[alvo])])
    acel = np.gradient(np.gradient(z, 1.0 / fps), 1.0 / fps)
    return dominante, float(np.sqrt(np.mean(acel ** 2)))


def razao_do_volante(s):
    """Ângulo do volante / esterçamento das rodas (com sinal), onde o esterçamento passa de 0,5 grau."""
    q = s["volante"]
    eixo = np.array([0.0, -math.sin(math.radians(65.0)), math.cos(math.radians(65.0))])
    angulo = 2.0 * np.arctan2(q[:, 1:] @ eixo, q[:, 0])
    steer = s["sinais"]["steer"]
    forte = np.abs(steer) > math.radians(0.5)
    if not forte.any():
        return float("nan")
    return float(np.median(angulo[forte] / steer[forte]))


def dados_do_modelo():
    with open(RAIZ_DADOS, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def comprimento_equivalente(nome):
    dados = dados_do_modelo()[nome]
    I = np.array(dados["I_origem"])
    return K.pendulo_composto(float(I[0, 0]), dados["volume"], abs(dados["cm"][2]))


# --------------------------------------------------------------------------
def metricas(s, p, referencia=None):
    """s = gravação do carro, p = gravação do portão. `referencia` evita refazer o meio carro."""
    out = []
    add = out.append
    ref = referencia or referencia_do_carro(s)
    t = s["t"]
    sus = s.get("suspensao") or SUSPENSAO_ANTES
    f_vert, f_arf = K.frequencias_proprias()

    # ---- rodas
    add(Metrica.limite_max(GRUPO, "rodas: deslizamento do ponto de contato / velocidade do centro", "-", 0.05,
                           deslizamento_das_rodas(s), nota="0 = rola sem deslizar; 2 = gira ao contrário"))
    add(Metrica.igual(GRUPO, "rodas: w R / v (sentido de rolar para a frente)", "-", 1.0, razao_de_rolamento(s), 0.03))
    add(Metrica.limite_max(GRUPO, "rodas: afastamento do fundo do pneu ao terreno", "mm", 10.0,
                           1000.0 * folga_das_rodas_no_chao(s), fonte="DERIVADO",
                           nota="terreno lido do mundo 3D; sobra a arfagem de ~0,3 grau"))

    # ---- suspensão
    add(Metrica("carro", "suspensão: frequência de passeio (vertical)", "Hz", f_vert, sus["f_vertical"], 1.0, 1.5,
                fonte="ESTIMADO", nota="sedã macio: 1,0 a 1,5 Hz"))
    add(Metrica("carro", "suspensão: frequência de arfagem", "Hz", f_arf, sus["f_arfagem"], 1.0, 1.55, fonte="ESTIMADO"))
    add(Metrica("carro", "suspensão: razão de amortecimento", "-", 0.30, sus["zeta"], 0.2, 0.4, fonte="ESTIMADO"))
    add(Metrica("carro", "rolagem: frequência", "Hz", 1.3, sus["f_rolagem"], 1.0, 1.6, fonte="ESTIMADO"))
    theta_jogo, theta_ref = arfagem_do_jogo(s), ref["theta"]
    amplitude = float(np.ptp(theta_ref))
    erro = float(np.max(np.abs(theta_jogo - theta_ref)))
    add(Metrica.igual(GRUPO, "arfagem: maior diferença contra o meio carro / amplitude total", "-", 0.0, erro / amplitude, 0.15,
                      relativa=False, nota="mesma aceleração, mesmo chão; o meio carro é integrado por scipy (RK45)"))
    # o sentido: aceleração para a frente levanta o nariz (agacha atrás); frear derruba
    k_acel = int(np.argmax(ref["a_frente"]))
    k_freio = int(np.argmin(ref["a_frente"]))
    din_ref = ref["theta"]
    estrada = np.array([(float(K.altura_do_chao(y - K.ENTRE_EIXOS / 2)) - float(K.altura_do_chao(y + K.ENTRE_EIXOS / 2)))
                        / K.ENTRE_EIXOS for y in ref["y"]])
    grad_ref = (din_ref[k_acel] - estrada[k_acel]) / ref["a_frente"][k_acel]
    grad_jogo = (theta_jogo[k_acel] - estrada[k_acel]) / ref["a_frente"][k_acel]
    add(Metrica.igual(GRUPO, "arfagem: gradiente na aceleração (nariz para cima = positivo)", "rad por m/s2", float(grad_ref),
                      float(grad_jogo), 0.20, nota="m h / K_theta, com a rigidez dos eixos a 1,15 e 1,30 Hz"))
    freio_ref = (din_ref[k_freio] - estrada[k_freio]) / ref["a_frente"][k_freio]
    freio_jogo = (theta_jogo[k_freio] - estrada[k_freio]) / ref["a_frente"][k_freio]
    add(Metrica.igual(GRUPO, "arfagem: gradiente na frenagem (nariz para baixo ao frear)", "rad por m/s2", float(freio_ref),
                      float(freio_jogo), 0.20))

    # ---- rolagem e direção
    add(Metrica("carro", "rolagem: gradiente (teto para fora da curva)", "rad por m/s2", K.GRADIENTE_ROLAGEM,
                gradiente_de_rolagem(s), math.radians(4) / K.G, math.radians(8) / K.G, fonte="ESTIMADO",
                nota="4 a 8 graus por g; sinal positivo = o corpo se inclina contra a aceleração lateral"))
    kappa = curvatura_do_caminho(s)
    delta = np.degrees(np.arctan(K.ENTRE_EIXOS * kappa))
    add(Metrica.limite_max(GRUPO, "direção: esterçamento que o caminho exige (pico)", "graus", 10.0, float(np.max(np.abs(delta))),
                           fonte="ESTIMADO", nota="o carro sai reto da garagem; o limite físico é 35 graus"))
    steer = np.degrees(s["sinais"]["steer"])
    mover = np.abs(s["sinais"]["speed"]) > 0.5                 # a curvatura medida só vale com o carro andando
    add(Metrica.limite_max(GRUPO, "direção: diferença entre o esterçamento do jogo e o de Ackermann (pior caso)", "graus", 0.5,
                           float(np.max(np.abs(steer[mover] - delta[mover]))), nota="delta = atan(L kappa)"))
    add(Metrica.limite_max(GRUPO, "direção: ângulo entre a frente do carro e a velocidade", "graus", 1.0, angulo_de_deriva(s),
                           nota="a baixa velocidade o carro anda para onde aponta"))
    razao = razao_do_volante(s)
    add(Metrica("carro", "direção: volante / roda (sinal e relação)", "-", K.RELACAO_DIRECAO, razao, 14.0, 18.0, fonte="ESTIMADO",
                nota="direção hidráulica americana, 14:1 a 18:1; positivo = esquerda gira para a esquerda"))

    # ---- motor
    f_idle, a_idle = vibracao_de_marcha_lenta(s)
    add(Metrica.igual(GRUPO, "motor: frequência dominante do tremor em marcha lenta", "Hz", K.vibracao_marcha_lenta()[0], f_idle,
                      1.5, relativa=False, nota="700 rpm / 60 (1a ordem); a ignição do V6 (35 Hz) passa de Nyquist a 60 quadros/s"))
    add(Metrica("carro", "motor: aceleração vertical RMS em marcha lenta", "m/s2", 0.2, a_idle, K.ACEL_MARCHA_LENTA_RMS[0],
                K.ACEL_MARCHA_LENTA_RMS[1] * 1.15, fonte="ESTIMADO", nota="0,05 a 0,4 m/s2 no assoalho"))

    # ---- aceleração que a cena pede contra o que o carro pode
    pico = float(np.max(np.abs(s["sinais"]["accel"])))
    add(Metrica.limite_max(GRUPO, "cena: aceleração máxima pedida ao carro", "m/s2", K.aceleracao_a_fundo(1.5, K.potencia_para_10s()),
                           pico, fonte="ESTIMADO", nota="a fundo, a ~1,5 m/s: tração de 1a marcha (0 a 100 em 10 s)"))

    # ---- coelhinho e chaveiro
    lbunny = comprimento_equivalente("Cut_Bunny")
    ref_bunny = K.simular_pendulo(t, lbunny, 0.04, lambda x: float(np.interp(x, t, ref["a_frente"])))
    compensa = 1.0 if "comprimentos" in s else 0.35           # o código de antes só descontava 35% da arfagem do corpo
    mundo_x = s["coelho"][:, 0] + compensa * s["euler"][:, 0]   # ângulo contra a vertical do mundo (para a frente = +)
    corr = float(np.corrcoef(mundo_x, ref_bunny)[0, 1])
    add(Metrica.limite_min(GRUPO, "coelhinho: correlação com o pêndulo composto forçado (sinal e forma)", "-", 0.95, corr,
                           nota="o coelhinho vai para trás quando o carro acelera e para a frente quando freia"))
    pico_jogo, pico_ref = float(np.max(np.abs(mundo_x))), float(np.max(np.abs(ref_bunny)))
    add(Metrica.igual(GRUPO, "coelhinho: ângulo de pico", "graus", math.degrees(pico_ref), math.degrees(pico_jogo), 0.15))
    periodo_jogo = 2 * math.pi * math.sqrt(s["comprimentos"]["bunny"] / K.G) if "comprimentos" in s else 2 * math.pi * math.sqrt(0.2 / K.G)
    add(Metrica.igual(GRUPO, "coelhinho: período de oscilação", "s", 2 * math.pi * math.sqrt(lbunny / K.G), periodo_jogo, 0.05,
                      nota=f"comprimento equivalente I/(m d) da malha: {lbunny:.3f} m"))
    lkey = comprimento_equivalente("Cut_KeyCharm")
    periodo_key = 2 * math.pi * math.sqrt(s["comprimentos"]["key"] / K.G) if "comprimentos" in s else 2 * math.pi * math.sqrt(0.07 / K.G)
    add(Metrica.igual(GRUPO, "chaveiro: período de oscilação", "s", 2 * math.pi * math.sqrt(lkey / K.G), periodo_key, 0.05,
                      nota=f"comprimento equivalente da malha: {lkey:.3f} m"))

    # ---- portão
    out += metricas_portao(p, s)
    return out


def metricas_portao(p, s=None):
    out = []
    add = out.append
    t, z, fps = p["t"], p["z"], p["fps"]
    janela = max(3, int(fps // 2))                            # a corrente folgada e as guias chacoalham: o abridor é a média
    zs = np.convolve(z, np.ones(janela) / janela, mode="same")
    v = np.gradient(zs, 1.0 / fps)
    a = np.gradient(v, 1.0 / fps)
    corpo = (t > p["inicio"] + 0.3) & (t < p["inicio"] + p["duracao"] - 0.3)
    cruzeiro = (t > p["inicio"] + p["duracao"] * 0.3) & (t < p["inicio"] + p["duracao"] * 0.7)
    add(Metrica("portão", "velocidade de cruzeiro", "m/s", 0.175, float(np.median(v[cruzeiro])), 0.15, 0.20, fonte="ESTIMADO",
                nota="abridor residencial 15 a 20 cm/s"))
    add(Metrica.limite_max("portão", "velocidade máxima", "m/s", 0.22, float(np.max(v)), fonte="ESTIMADO"))
    add(Metrica.limite_max("portão", "aceleração máxima (partida e parada suaves)", "m/s2", 0.35, float(np.max(np.abs(a[corpo]))),
                           fonte="ESTIMADO", nota="rampa de 0,5 a 2 s até a velocidade de cruzeiro"))
    subida = np.nonzero(z >= 0.98 * p["altura"])[0]
    duracao = float(t[subida[0]] - t[np.nonzero(z > 0.002)[0][0]])
    add(Metrica("portão", "duração da subida de 2,3 m", "s", 2.3 / 0.175, duracao, 2.3 / 0.20, 2.3 / 0.15 + 1.5, fonte="ESTIMADO"))
    if s is not None:
        y_frente = s["pos"][:, 1] - 2.42                       # para-choque dianteiro (o carro anda para -Y)
        y_tras = s["pos"][:, 1] + 2.42
        sob_a_folha = (y_frente < 0.158) & (y_tras > -0.064)      # a folha ocupa y de -0,064 a 0,158
        if sob_a_folha.any():
            folga = np.interp(s["t"][sob_a_folha], t, z) - (s["pos"][sob_a_folha, 2] + K.TETO)
            add(Metrica.limite_min("portão", "folga entre o teto do carro e a folha enquanto o carro passa", "m", 0.10,
                                   float(np.min(folga)), fonte="DERIVADO", nota="o teto tem 1,40 m"))
    return out


def gravar():
    return grava.carro(), grava.portao()


def metricas_com_antes(s, p):
    lista = metricas(s, p)
    antes_s, antes_p = medidas.carregar_gravacao("carro"), medidas.carregar_gravacao("portao")
    if antes_s is not None and antes_p is not None:
        medidas.completar_antes(lista, metricas(antes_s, antes_p))
    return lista


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    s, p = gravar()
    if "--antes" in argv:
        medidas.salvar_gravacao("carro", s)
        medidas.salvar_gravacao("portao", p)
    lista = metricas_com_antes(s, p)
    print(medidas.tabela_markdown(lista))
    return lista


if __name__ == "__main__":
    main()
