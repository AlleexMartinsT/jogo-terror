"""A mão como o jogador a vê: o punho no referencial da câmera, medido igual no mocap e no jogo.

Em primeira pessoa só existe o que está dentro do cone da câmera, e o que se vê de uma mão andando é o
deslocamento dela *em relação à cabeça*, não no mundo. Por isso a medida aqui é o punho em coordenadas da
câmera: (direita, frente, cima) em metros, com a escala do Daniel (braço de 0,60 m).

    from tools.movimento_ref import cmu, movimento, egocentrico
    mov = movimento.movimento_de_mocap(cmu.carregar("77_25"))
    medida = egocentrico.medir(mov, "d")          # média, amplitude, frequência, fração dentro do campo de visão

`python -m tools.movimento_ref.egocentrico` mede os clipes de `CATEGORIAS` e grava
`assets/referencia/maos_ego_ref.json`, que os testes usam sem baixar nada.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from tools.movimento_ref.movimento import INDICE  # noqa: E402

BRACO_DANIEL = 0.60                  # ombro até o punho, m (o mesmo L do agente de mãos da fase 4)
FOV_HORIZONTAL = 72.0                # graus, conventions.FOV_DEG (lado maior da imagem, 16:9)
FOV_VERTICAL = 2.0 * np.degrees(np.arctan(np.tan(np.radians(FOV_HORIZONTAL / 2)) * 9.0 / 16.0))
PERTO = 0.12                         # m: mais perto que isso a mão está atrás do plano de corte da câmera
ARQUIVO = os.path.join(ROOT, "assets", "referencia", "maos_ego_ref.json")

# categoria -> (descrição, [(clipe, início, fim)]); início/fim em segundos, None = o clipe todo
CATEGORIAS = {
    "andar": ("andar sem nada nas mãos, 7 pessoas",
              [(c, None, None) for c in ("07_01", "07_06", "08_01", "08_02", "08_03", "16_32", "16_47", "35_01", "35_02",
                                          "38_01", "39_01", "02_01")]),
    "andar_rapido": ("andar rápido (1,5 a 1,6 m/s, a faixa do jogo a 1,7), 1 pessoa, 3 clipes", [(c, None, None) for c in ("08_01", "08_02", "08_03")]),
    "correr": ("correr sem nada nas mãos", [(c, None, None) for c in ("09_01", "09_09", "09_11")]),
    "mala_leve": ("andar carregando uma mala de 2,5 kg numa mão", [("70_01", None, None), ("70_02", None, None)]),
    "mala_media": ("andar carregando uma mala de 5,7 kg", [("70_10", None, None), ("70_12", None, None)]),
    "mala_pesada": ("andar carregando uma mala de 8,8 kg", [("70_03", None, None), ("70_05", None, None)]),
    "busca_cuidadosa": ("andar devagar e procurar, braços à frente do corpo",
                        [("77_25", None, None), ("77_26", None, None), ("77_27", None, None), ("91_18", None, None)]),
    "lanterna": ("olhar em volta com uma lanterna", [("77_05", None, None)]),
    "pronto": ("parado em guarda, braços à frente", [("77_03", None, None)]),
}


JUNTAS_DO_BRACO = ("ombro", "cotovelo", "punho")


def junta_ego(mov, junta, lado, braco=BRACO_DANIEL):
    """[T, 3] (direita, frente, cima) de `junta` ("ombro", "cotovelo" ou "punho") no referencial da câmera, com a
    escala do Daniel. O ombro importa tanto quanto a mão: é a base em que o braço se apoia."""
    giro = mov.cabeca_rot                                       # colunas = eixos locais da câmera (x direita, y cima, z atrás)
    origem = mov.camera if mov.camera is not None else mov.pos[:, INDICE["olho"]]
    local = np.einsum("tji,tj->ti", giro, mov.pos[:, INDICE[f"{junta}_{lado}"]] - origem)
    return np.stack([local[:, 0], -local[:, 2], local[:, 1]], axis=1) * (braco / comprimento_do_braco(mov, lado))


def punho(mov, lado, braco=BRACO_DANIEL):
    return junta_ego(mov, "punho", lado, braco)


def comprimento_do_braco(mov, lado):
    ombro, cotovelo, pulso = (mov.j(f"{nome}_{lado}") for nome in ("ombro", "cotovelo", "punho"))
    return float(np.median(np.linalg.norm(cotovelo - ombro, axis=1) + np.linalg.norm(pulso - cotovelo, axis=1)))


def dentro_do_campo(ego):
    """Fração dos quadros em que o punho cai dentro do cone da câmera (e depois do plano de corte)."""
    direita, frente, cima = ego[:, 0], ego[:, 1], ego[:, 2]
    visivel = (frente > PERTO) & (np.abs(np.degrees(np.arctan2(direita, frente))) < FOV_HORIZONTAL / 2) \
        & (np.abs(np.degrees(np.arctan2(cima, frente))) < FOV_VERTICAL / 2)
    return float(visivel.mean())


def frequencia_dominante(serie, fps, minimo=0.3, maximo=6.0):
    """Frequência (Hz) do maior pico do espectro de `serie` entre `minimo` e `maximo`; 0 se não houver ciclo."""
    serie = np.asarray(serie) - np.mean(serie)
    if len(serie) < fps or np.ptp(serie) < 1e-4:
        return 0.0
    janela = np.hanning(len(serie))
    espectro = np.abs(np.fft.rfft(serie * janela, n=max(len(serie), int(fps * 16))))
    freq = np.fft.rfftfreq(max(len(serie), int(fps * 16)), 1.0 / fps)
    faixa = (freq >= minimo) & (freq <= maximo)
    return float(freq[faixa][np.argmax(espectro[faixa])]) if faixa.any() else 0.0


def medir(mov, lado, junta="punho", so_andando=True, velocidade_minima=0.7):
    """Estatísticas de `junta` do braço `lado` ("e"/"d") no referencial da câmera. Com `so_andando`, só os quadros
    em que o quadril anda a `velocidade_minima` m/s ou mais (os clipes têm paradas e giros que não são marcha)."""
    ego = junta_ego(mov, junta, lado)
    quadril = mov.j("quadril")[:, :2]
    passo = max(1, int(round(mov.fps / 30)))
    velocidade = np.zeros(len(quadril))
    velocidade[passo:] = np.linalg.norm(quadril[passo:] - quadril[:-passo], axis=1) * mov.fps / passo
    quadros = velocidade >= velocidade_minima if so_andando and (velocidade >= velocidade_minima).sum() > mov.fps else \
        np.ones(len(ego), bool)
    ego = ego[quadros]
    if len(ego) < 10:
        return None
    p5, p95 = np.percentile(ego, 5, axis=0), np.percentile(ego, 95, axis=0)
    return {"media": ego.mean(axis=0).round(4).tolist(), "amplitude": (p95 - p5).round(4).tolist(),
            "desvio": ego.std(axis=0).round(4).tolist(),
            "frequencia_frente": round(frequencia_dominante(ego[:, 1], mov.fps), 3),
            "frequencia_cima": round(frequencia_dominante(ego[:, 2], mov.fps), 3),
            "no_campo": round(dentro_do_campo(ego), 3), "quadros": int(quadros.sum()),
            "velocidade_do_quadril": round(float(velocidade[quadros].mean()), 3)}


def medir_clipe(clipe, inicio=None, fim=None):
    from tools.movimento_ref import cmu, movimento
    mov = movimento.movimento_de_mocap(cmu.carregar(clipe), inicio, fim)
    return {junta: {lado: medir(mov, lado, junta) for lado in "ed"} for junta in JUNTAS_DO_BRACO}


def medir_categorias():
    resultado = {}
    for nome, (descricao, clipes) in CATEGORIAS.items():
        porclipe = {}
        for clipe, inicio, fim in clipes:
            try:
                porclipe[clipe] = medir_clipe(clipe, inicio, fim)
            except Exception as erro:                              # clipe que não baixou não derruba os outros
                porclipe[clipe] = {"erro": str(erro)[:80]}
        resultado[nome] = {"descricao": descricao, "clipes": porclipe, "resumo": resumir(porclipe)}
    return resultado


def resumir(porclipe):
    """Mediana entre clipes, por junta e por braço. Quem carrega o objeto é o braço de menor amplitude à frente
    (o outro balança livre): o resumo não decide, quem lê escolhe."""
    resumo = {}
    for junta in JUNTAS_DO_BRACO:
        for lado in "ed":
            medidas = [c[junta][lado] for c in porclipe.values()
                       if isinstance(c, dict) and c.get(junta) and c[junta].get(lado)]
            if medidas:
                resumo.setdefault(junta, {})[lado] = {
                    chave: np.median([m[chave] for m in medidas], axis=0).round(4).tolist()
                    for chave in ("media", "amplitude", "frequencia_frente", "frequencia_cima", "no_campo")}
    return resumo


def main():
    resultado = medir_categorias()
    os.makedirs(os.path.dirname(ARQUIVO), exist_ok=True)
    with open(ARQUIVO, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=1)
    print(f"campo de visão do jogo: {FOV_HORIZONTAL:.0f} x {FOV_VERTICAL:.0f} graus")
    for nome, bloco in resultado.items():
        print(f"\n{nome}: {bloco['descricao']}")
        for junta, lados in bloco["resumo"].items():
            for lado, dados in lados.items():
                direita, frente, cima = dados["media"]
                ad, af, ac = dados["amplitude"]
                print(f"  {junta:8s} {lado}: média (dir {direita:+.2f}, frente {frente:+.2f}, cima {cima:+.2f}) m   "
                      f"amplitude (dir {ad:.2f}, frente {af:.2f}, cima {ac:.2f}) m   "
                      f"freq {dados['frequencia_frente']:.2f}/{dados['frequencia_cima']:.2f} Hz   no campo {dados['no_campo'] * 100:.0f}%")
    print(f"\ngravado em {os.path.relpath(ARQUIVO, ROOT)}")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------------------------------------------------------
# Painéis do que o jogador vê (fase 5)
# ---------------------------------------------------------------------------------------------------------------------------
COR_REAL = "#2a78d6"
COR_JOGO = "#eb6834"
COR_ANTES = "#8a8a86"


def angulos(ego):
    """(azimute, elevação) em graus de pontos (direita, frente, cima) na câmera. NaN para o que está atrás do plano de corte
    (`PERTO`): a câmera não o desenha, e o ângulo de um ponto ao lado do olho não quer dizer nada."""
    ego = np.asarray(ego, float)
    frente = np.where(ego[:, 1] > PERTO, ego[:, 1], np.nan)
    return np.degrees(np.arctan2(ego[:, 0], frente)), np.degrees(np.arctan2(ego[:, 2], frente))


def desenhar_campo(ax, curvas, titulo="", margem=6.0):
    """Eixos de ângulo (azimute x elevação) com a moldura de 72 x 44 graus. `curvas`: [{rotulo, ego [T,3], cor, estilo, media}]."""
    from matplotlib.patches import Rectangle
    meia_h, meia_v = FOV_HORIZONTAL / 2, FOV_VERTICAL / 2
    ax.add_patch(Rectangle((-meia_h, -meia_v), 2 * meia_h, 2 * meia_v, fill=False, ec="#444", lw=1.4))
    ax.axhline(0, color="#ccc", lw=0.6)
    ax.axvline(0, color="#ccc", lw=0.6)
    for curva in curvas:
        az, el = angulos(curva["ego"])
        ax.plot(az, el, color=curva["cor"], ls=curva.get("estilo", "-"), lw=curva.get("largura", 1.2), label=curva["rotulo"], alpha=0.9)
        if curva.get("media", True) and np.isfinite(az).any():
            ax.plot([np.nanmean(az)], [np.nanmean(el)], marker="o", color=curva["cor"], ms=5)
    ax.set_xlim(-meia_h - margem, meia_h + margem)
    ax.set_ylim(-meia_v - margem, meia_v + margem)
    ax.set_aspect("equal")
    ax.set_xlabel("azimute (graus, + direita)")
    ax.set_ylabel("elevação (graus)")
    ax.set_title(titulo, fontsize=9)
    ax.legend(fontsize=7, loc="upper left", framealpha=0.85)


def desenhar_plano(ax, caixas, curvas=(), profundidade=0.30, titulo=""):
    """Plano (direita, cima) da câmera em metros. `caixas`: [{rotulo, media [3], amplitude [3], cor}] desenha o retângulo
    média +- amplitude/2 (percentis 5 a 95) de cada junta; `curvas`: trajetórias [T,3]. Tracejado: o cone da câmera a
    `profundidade` m do olho (onde fica a lanterna)."""
    from matplotlib.patches import Rectangle
    meia_h = profundidade * np.tan(np.radians(FOV_HORIZONTAL / 2))
    meia_v = profundidade * np.tan(np.radians(FOV_VERTICAL / 2))
    ax.add_patch(Rectangle((-meia_h, -meia_v), 2 * meia_h, 2 * meia_v, fill=False, ec="#444", ls="--", lw=1.2))
    ax.annotate(f"campo a {profundidade * 100:.0f} cm", (-meia_h, meia_v), fontsize=7, color="#444", va="bottom")
    ax.plot([0], [0], marker="+", color="#444", ms=9)
    for caixa in caixas:
        media, amplitude = np.asarray(caixa["media"]), np.asarray(caixa["amplitude"])
        ax.add_patch(Rectangle((media[0] - amplitude[0] / 2, media[2] - amplitude[2] / 2), max(amplitude[0], 0.004),
                               max(amplitude[2], 0.004), fc=caixa["cor"], ec=caixa["cor"], alpha=caixa.get("alfa", 0.35), lw=1.0))
        ax.annotate(caixa["rotulo"], (media[0], media[2] + amplitude[2] / 2), fontsize=7, color=caixa["cor"], ha="center", va="bottom")
    for curva in curvas:
        ego = np.asarray(curva["ego"])
        ax.plot(ego[:, 0], ego[:, 2], color=curva["cor"], lw=curva.get("largura", 1.2), label=curva["rotulo"], alpha=0.9)
    ax.set_aspect("equal")
    ax.set_xlabel("direita (m)")
    ax.set_ylabel("cima (m)")
    ax.set_title(titulo, fontsize=9)
    ax.grid(alpha=0.2)


def espectro(serie, fps, maximo=6.0):
    """(frequências, amplitude) do espectro de amplitude (m) de `serie`, sem a média, com janela de Hann."""
    serie = np.asarray(serie, float)
    serie = serie - serie.mean()
    n = max(len(serie), int(fps * 16))
    amplitude = np.abs(np.fft.rfft(serie * np.hanning(len(serie)), n=n)) * 2.0 / np.hanning(len(serie)).sum()
    freq = np.fft.rfftfreq(n, 1.0 / fps)
    dentro = freq <= maximo
    return freq[dentro], amplitude[dentro]
