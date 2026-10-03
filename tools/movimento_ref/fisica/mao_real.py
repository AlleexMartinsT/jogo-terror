"""Gestos da mão de pessoas reais (mocap da CMU) para conferir a duração e o perfil de velocidade dos empurrões.

O mocap não tem porta nem carro; tem mãos que empurram (81_05 a 82_07: "push heavy object") e que erguem uma
janela (56_03 a 56_08: "lift open window"). Daqui sai o que é MEDIDO: duração, comprimento do trajeto, pico de
velocidade e em que fração do gesto o pico acontece, para comparar com a mão que abre a porta do jogo.
"""
import numpy as np

from .. import cmu

CLIPES_ERGUER = ("56_03", "56_04", "56_05", "56_06", "56_08")
CLIPES_EMPURRAR = ("81_05", "81_06", "81_07", "82_06", "82_07", "134_06")
SUAVIZA = 9                      # amostras (75 ms a 120 Hz): tira o ruído da captura sem apagar o gesto


def _suavizar(sinal, janela=SUAVIZA):
    nucleo = np.ones(janela) / janela
    pad = janela // 2
    ext = np.pad(sinal, ((pad, pad), (0, 0)), mode="edge")
    return np.stack([np.convolve(ext[:, c], nucleo, mode="valid") for c in range(sinal.shape[1])], axis=1)


def gestos(clip_id, mao="RightHand", comprimento=(0.35, 1.6), duracao=(0.3, 2.2), vmin=0.12):
    """Acha os gestos da mão: trechos entre dois mínimos de velocidade, relativos ao quadril (tira a caminhada).

    Devolve lista de dicts com `t0`, `duracao`, `trajeto` (m), `v_pico` (m/s), `fracao_pico` (0..1), `dz`, e o perfil
    de velocidade reamostrado em 50 pontos (`perfil`, normalizado pelo pico).
    """
    clip = cmu.carregar(clip_id)
    posicoes, _ = clip.world()
    mao_i, quadril = clip.index(mao), clip.index("Hips")
    relativa = posicoes[:, mao_i] - posicoes[:, quadril]          # tira o andar do corpo todo
    altura = _suavizar(posicoes[:, mao_i])[:, 2]
    velocidade = np.linalg.norm(np.gradient(_suavizar(relativa), axis=0), axis=1) * clip.fps
    # mínimos locais abaixo de `vmin` separam os gestos
    baixo = velocidade < vmin
    fronteiras = np.nonzero(np.diff(baixo.astype(int)) != 0)[0] + 1
    inicio_gesto = [k for k in fronteiras if baixo[k - 1] and not baixo[k]]
    fim_gesto = [k for k in fronteiras if not baixo[k - 1] and baixo[k]]
    resultado = []
    for a in inicio_gesto:
        b = next((k for k in fim_gesto if k > a), None)
        if b is None:
            continue
        seg = velocidade[a:b]
        dur = (b - a) / clip.fps
        trajeto = float(np.sum(seg) / clip.fps)
        if not (duracao[0] <= dur <= duracao[1] and comprimento[0] <= trajeto <= comprimento[1]):
            continue
        # um gesto de verdade tem UM pico: descarta trechos com vários (mexer a mão à toa)
        pico = int(np.argmax(seg))
        v_pico = float(seg[pico])
        if np.sum(seg > 0.6 * v_pico) / len(seg) > 0.75 and v_pico < 0.4:
            continue
        perfil = np.interp(np.linspace(0, len(seg) - 1, 50), np.arange(len(seg)), seg) / v_pico
        resultado.append({"clip": clip_id, "t0": a / clip.fps, "duracao": dur, "trajeto": trajeto, "v_pico": v_pico,
                          "fracao_pico": pico / max(len(seg) - 1, 1), "dz": float(altura[b - 1] - altura[a]),
                          "razao_pico_media": v_pico * dur / trajeto,
                          "perfil": perfil})
    return resultado


def resumo(lista):
    """Média e desvio das medidas de uma lista de gestos."""
    campos = ("duracao", "trajeto", "v_pico", "fracao_pico", "razao_pico_media")
    return {c: (float(np.mean([g[c] for g in lista])), float(np.std([g[c] for g in lista]))) for c in campos} \
        | {"n": len(lista)}


def gestos_de_erguer(mao="RightHand"):
    """Mão subindo (dz > 0,25 m): erguer a janela."""
    out = []
    for clip_id in CLIPES_ERGUER:
        out += [g for g in gestos(clip_id, mao) if g["dz"] > 0.25]
    return out


def gestos_de_empurrar(mao="RightHand"):
    out = []
    for clip_id in CLIPES_EMPURRAR:
        out += gestos(clip_id, mao, comprimento=(0.3, 1.6))
    return out
