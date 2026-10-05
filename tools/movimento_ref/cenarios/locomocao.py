"""Cenários de locomoção do jogador (agente 2): o jogo contra caminhadas, corridas, paradas, curvas e escadas da CMU.

    andar          1,7 m/s (SPEED_WALK, tecla cheia) contra as caminhadas de 1,55 a 1,80 m/s
    andar_normal   meia entrada do analógico (1,3 m/s) contra as de 1,20 a 1,45 m/s
    andar_devagar  entrada a 55% (0,95 m/s) contra as de 0,85 a 1,15 m/s
    correr         4,0 m/s (SPEED_RUN) contra as corridas da CMU (3,0 a 3,8 m/s: não há corrida mais rápida no conjunto)
    agachado       andar agachado (0,8 m/s) contra 136_09 e 136_10
    furtivo        entrada a 33% (0,56 m/s) contra 91_18 (andar com cuidado, olhando em volta)
    parar          andar e soltar a tecla contra 16_33 (andar devagar e parar)
    curva          andar girando 90 graus contra 16_17 (andar e virar à esquerda)
    escada         subir a escada da casa contra 83_27 a 83_35

Os seis primeiros usam as métricas de marcha de `metricas.CAMPOS_MARCHA` (as do agente 1) contra os clipes da faixa de
velocidade do jogo, não contra o grupo geral "andar" de 1,2 a 1,6 m/s: comparar 1,7 m/s com 1,35 m/s faz a cadência, o passo
e a altura do quadril parecerem errados por causa da velocidade e não do movimento. Os clipes de cada faixa vêm de
`assets/referencia/marcha_ref.json`, o mesmo arquivo que gera as tabelas do jogo (`python -m tools.marcha.extrair`).

Os três últimos medem o que a marcha não mede (freada, curva, escada) com escalares calculados aqui, iguais para o mocap e
para o jogo.

    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.comparar andar --vistas frente,lado,topo,primeira --saida out/f4_2/final/andar
"""
import json
import os

import numpy as np

from . import registrar
from .base import Alinhamento, Cenario

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REFERENCIA = os.path.join(RAIZ, "assets", "referencia", "marcha_ref.json")
PERNA_DANIEL = 0.845
_faixas = {}


def faixa_de(nome):
    """Clipes e escalares de uma faixa de `assets/referencia/marcha_ref.json`."""
    if not _faixas:
        with open(REFERENCIA, encoding="utf-8") as arquivo:
            _faixas.update(json.load(arquivo)["faixas"])
    return _faixas[nome]


def _passos(*itens):
    """Roteiro com entradas analógicas: [(segundos, mover, giro graus/s)]."""
    from .. import grava
    return [grava.Passo(s, mover=mover, giro=giro, rotulo=rotulo) for s, mover, giro, rotulo in itens]


# --------------------------------------------------------------------------
# Marcha em linha reta
# --------------------------------------------------------------------------
class _Faixa(Cenario):
    """Marcha contra os clipes de uma faixa de velocidade."""
    faixa = None
    excluir = ()
    recortar = False        # só o trecho andando de cada clipe (o mocap de agachado começa em pé)

    def _clipes(self):
        return [c for c in faixa_de(self.faixa)["clipes"] if c not in self.excluir]

    def carregar_real(self):
        from .. import cmu
        from ..movimento import movimento_de_mocap
        from ...marcha import extrair
        if self.recortar:
            self.trecho = extrair.janela_andando(movimento_de_mocap(cmu.carregar(self.clip)))
        real = super().carregar_real()
        grupo = []
        for clip in self._clipes():
            mov = movimento_de_mocap(cmu.carregar(clip))
            grupo.append(extrair.trecho_andando(mov) if self.recortar else mov)
        real.grupo = grupo
        return real


@registrar
class Andar(_Faixa):
    nome = "andar"
    titulo = "Andar (1,7 m/s) contra caminhadas rápidas da CMU"
    resumo = "Tecla cheia de andar: o jogo contra as caminhadas de 1,55 a 1,80 m/s, alinhados pelo toque do calcanhar."
    clip = "08_01"
    faixa = "andar_rapido"
    roteiro = "andar 9"
    margem = 0.7
    metodo = "zeni"


@registrar
class AndarNormal(_Faixa):
    nome = "andar_normal"
    titulo = "Andar a 1,3 m/s contra caminhadas normais da CMU"
    resumo = "Meia entrada do analógico (78%): o jogo na faixa de 1,20 a 1,45 m/s."
    clip = "07_01"
    faixa = "andar"
    margem = 0.7
    metodo = "zeni"

    @property
    def roteiro(self):
        return _passos((9.0, 0.78, 0.0, "andar 78%"))


@registrar
class AndarDevagar(_Faixa):
    nome = "andar_devagar"
    titulo = "Andar devagar (0,95 m/s) contra caminhadas lentas da CMU"
    resumo = "Entrada a 55% do analógico: o jogo na faixa de 0,85 a 1,15 m/s."
    clip = "07_04"
    faixa = "andar_lento"
    margem = 0.7
    metodo = "zeni"

    @property
    def roteiro(self):
        return _passos((10.0, 0.55, 0.0, "andar 55%"))


@registrar
class Correr(_Faixa):
    nome = "correr"
    titulo = "Correr (4,0 m/s) contra corridas da CMU"
    resumo = ("Corrida a 4,0 m/s. O conjunto da CMU vai até 3,8 m/s, então velocidade, passada e passo ficam acima do real "
              "de propósito; cadência, apoio, voo e ângulos são comparáveis.")
    clip = "09_01"
    faixa = "correr"
    excluir = ("16_55", "16_56", "02_03")           # trotes lentos de cadência alta (200 passos/min), não corridas
    roteiro = "correr 4"            # o fôlego dura 4,5 s correndo (STAMINA_DRAIN)
    margem = 1.0
    metodo = "altura"


@registrar
class Agachado(_Faixa):
    nome = "agachado"
    titulo = "Andar agachado (0,8 m/s) contra 136_09 e 136_10"
    resumo = ("Ritmo comparável; a profundidade não: o jogo agacha até a vista a 1,05 m do chão, o mocap só dobra os joelhos "
              "(vista a 1,38 m), então ângulos de quadril, joelho e altura do quadril ficam fora.")
    clip = "136_09"
    faixa = "agachado"
    recortar = True
    roteiro = "agachar 1; agachado 10"
    passo = 1
    margem = 0.7
    metodo = "zeni"


@registrar
class Furtivo(_Faixa):
    nome = "furtivo"
    titulo = "Andar com cuidado (0,56 m/s) contra 91_18"
    resumo = ("Entrada a 33% do analógico, abaixo da velocidade em que a entidade ainda considera o jogador quieto (0,99 m/s). "
              "A referência é um só clipe, de uma pessoa que anda devagar olhando em volta (17_03 e 77_14 andam de lado ou "
              "em ziguezague e não servem como marcha em linha reta).")
    clip = "91_18"
    recortar = True
    margem = 0.7
    metodo = "zeni"

    @property
    def roteiro(self):
        return _passos((9.0, 0.33, 0.0, "andar 33%"))

    def _clipes(self):
        return [self.clip]


# --------------------------------------------------------------------------
# Escalares dos cenários que a marcha não cobre
# --------------------------------------------------------------------------
def _gauss(sinal, sigma, fps):
    from .. import metricas
    return metricas.gaussiano(sinal, sigma, fps)


def _angulo(vetores):
    return np.degrees(np.unwrap(np.arctan2(vetores[:, 1], vetores[:, 0])))


def _t50(tempo, serie, a, b, fps):
    """Instante em que a série cumpre metade da sua mudança entre o início (`a`) e o fim (`b`) do trecho."""
    inicio = np.median(serie[a:a + max(3, int(0.05 * fps))])
    fim = np.median(serie[b - max(3, int(0.05 * fps)):b])
    alvo = inicio + 0.5 * (fim - inicio)
    passou = (serie[a:b] - alvo) * np.sign(fim - inicio) >= 0
    return float(tempo[a + int(np.argmax(passou))])


def medir_parada(mov):
    """Freada: ({escalar: valor}, (quadro em que a velocidade cai abaixo de 90%, 10%, 3%)).

    v0 é a mediana da velocidade nos quadros acima de 60% do máximo (o trecho andando); a distância é a percorrida do
    90% até o repouso, dita em segundos de caminhada (distância / v0)."""
    from .. import metricas
    fps = mov.fps
    quadril = mov.j("quadril")
    v = metricas.velocidade_horizontal(quadril, fps, 0.10)
    v0 = float(np.median(v[v > 0.6 * v.max()]))
    final = int(np.argmax(v)) + int(np.argmax(v[int(np.argmax(v)):] < 0.03 * v0 + 0.01))
    antes = np.nonzero(v[:final] >= 0.9 * v0)[0]
    a = int(antes[-1]) if len(antes) else 0
    b = a + int(np.argmax(v[a:] < 0.1 * v0))
    meio = a + int(np.argmax(v[a:] < 0.5 * v0))
    trajeto = _gauss(quadril[:, :2], 0.05, fps)
    distancia = float(np.linalg.norm(np.diff(trajeto[a:final + 1], axis=0), axis=1).sum())
    cabeca = mov.cabeca_pos()[:, 2]
    fim_parado = min(len(cabeca), final + int(0.4 * fps))
    dz = float(np.median(cabeca[max(final, fim_parado - int(0.4 * fps)):fim_parado]) - np.median(cabeca[max(0, a - int(1.0 * fps)):a]))
    return ({"parar_v0": v0, "parar_tempo_90_50": (meio - a) / fps, "parar_tempo_90_10": (b - a) / fps,
             "parar_tempo_ate_parar": (final - a) / fps, "parar_dist_s": distancia / v0, "parar_cabeca_dz": dz},
            (a, b, final))


def medir_curva(mov):
    """Curva: ({escalar: valor}, (quadro de início, de fim, sinal)) com sinal +1 para a esquerda.

    A janela é onde o rumo do quadril gira a mais de 25% da velocidade de giro máxima. Cabeça, pelve e trajetória são
    comparadas pelo instante em que cumprem metade da mudança de rumo (suavizados em 0,15 s para tirar a oscilação do passo)."""
    fps = mov.fps
    t = np.arange(mov.quadros) / fps
    quadril = mov.j("quadril")
    xy = _gauss(quadril[:, :2], 0.20, fps)
    velocidade = np.gradient(xy, axis=0) * fps
    rapidez = np.linalg.norm(velocidade, axis=1)
    rumo = _angulo(velocidade)
    giro = np.gradient(_gauss(rumo, 0.10, fps)) * fps
    from .. import metricas
    ativo = np.abs(giro) > 0.25 * np.abs(giro).max()
    a, b = max(metricas._corridas(ativo), key=lambda r: r[1] - r[0])
    sinal = 1.0 if giro[a:b].mean() >= 0 else -1.0
    quadris = mov.j("coxa_d") - mov.j("coxa_e")
    pelve = _angulo(np.stack([-quadris[:, 1], quadris[:, 0]], axis=1))
    olhar = mov.cabeca_rot @ np.array([0.0, 0.0, -1.0])
    cabeca = _angulo(olhar[:, :2])
    ia, ib = max(0, a - int(0.4 * fps)), min(mov.quadros - 1, b + int(0.6 * fps))
    marcas = {nome: _t50(t, _gauss(serie, 0.15, fps), ia, ib, fps) for nome, serie in (("rumo", rumo), ("pelve", pelve), ("cabeca", cabeca))}
    tronco = mov.j("c7") - quadril
    esquerda = np.stack([-np.sin(np.radians(rumo)), np.cos(np.radians(rumo))], axis=1)
    inclinacao = _gauss(np.degrees(np.arctan2((tronco[:, :2] * esquerda).sum(axis=1), tronco[:, 2])), 0.30, fps)
    rolagem = _gauss(np.degrees(np.arcsin(np.clip(mov.cabeca_rot[:, 2, 0], -1, 1))), 0.10, fps)
    antes = slice(max(0, a - int(1.0 * fps)), a)
    angulo = abs(rumo[min(len(rumo) - 1, b + int(0.2 * fps))] - rumo[max(0, a - int(0.2 * fps))])
    return ({"curva_angulo": float(angulo), "curva_duracao": (b - a) / fps,
             "curva_vel_razao": float(rapidez[a:b].mean() / max(rapidez[antes].mean(), 1e-6)),
             "curva_cabeca_antecipa": marcas["rumo"] - marcas["cabeca"], "curva_pelve_atraso": marcas["pelve"] - marcas["cabeca"],
             "curva_rolagem_cabeca": float((sinal * rolagem[a:b]).max() - np.median(sinal * rolagem[antes])),
             "curva_inclinacao_tronco": float((sinal * inclinacao[a:b]).max() - np.median(sinal * inclinacao[antes]))},
            (a, b, sinal))


def janela_subida(mov):
    """(quadro inicial, final) do trecho de subida estável: a cabeça sobe a mais de 45% da velocidade vertical p85, sem as
    pontas (0,3 s ou 15% de cada lado, o que for maior)."""
    from .. import metricas
    fps = mov.fps
    z = _gauss(mov.cabeca_pos()[:, 2], 0.25, fps)
    subida = np.gradient(z) * fps
    corridas = metricas._corridas(subida > 0.45 * np.percentile(subida, 85))
    if not corridas:
        return None
    a, b = max(corridas, key=lambda r: r[1] - r[0])
    corte = max(int(0.3 * fps), int(0.15 * (b - a)))      # a entrada e a saída da escada não são marcha de escada
    a, b = a + corte, b - corte
    return (a, b) if b - a >= fps else None


def medir_escada(mov):
    """Escada: ({escalar: valor}, (quadro inicial, final)). A oscilação da cabeça é o vertical sem a reta de subida, em
    metros de Daniel (escalada pela perna); a frequência dominante dessa oscilação é a de passos por segundo."""
    from .. import metricas
    janela = janela_subida(mov)
    if janela is None:
        return {}, (0, 0)
    a, b = janela
    fps = mov.fps
    cabeca = mov.cabeca_pos()[:, 2]
    t = np.arange(b - a) / fps
    reta = np.polyfit(t, cabeca[a:b], 1)
    residuo = cabeca[a:b] - np.polyval(reta, t)
    escala = PERNA_DANIEL / metricas.comprimento_perna(mov)
    xy = _gauss(mov.j("quadril")[:, :2], 0.2, fps)
    horizontal = float(np.linalg.norm(np.gradient(xy, axis=0), axis=1)[a:b].mean() * fps)
    passos_s = float(metricas.frequencia_dominante(residuo, fps))
    return ({"escada_passos_s": passos_s, "escada_osc_cabeca": float(np.ptp(residuo) * escala),
             "escada_subida_vel": float(reta[0]), "escada_vel_horiz": horizontal,
             "escada_subida_passo": float(reta[0] / max(passos_s, 1e-6))}, (a, b))


CAMPOS_PARAR = {
    "parar_v0": ("velocidade antes de parar", "m/s", 2, "rel", 0.15),
    "parar_tempo_90_50": ("freada: de 90% a 50% da velocidade", "s", 2, "abs", 0.20),
    "parar_tempo_90_10": ("freada: de 90% a 10% da velocidade", "s", 2, "abs", 0.50),
    "parar_dist_s": ("distância até parar, em segundos de caminhada", "s", 2, "abs", 0.20),
    "parar_cabeca_dz": ("cabeça parada, em relação a andando", "m", 3, "abs", 0.02),
}
CAMPOS_CURVA = {
    "curva_angulo": ("mudança de rumo", "graus", 0, "abs", 20.0),
    "curva_vel_razao": ("velocidade na curva / antes", "", 2, "abs", 0.15),
    "curva_cabeca_antecipa": ("cabeça adianta o rumo", "s", 2, "abs", 0.15),
    "curva_pelve_atraso": ("pelve atrasa em relação à cabeça", "s", 2, "abs", 0.15),
    "curva_rolagem_cabeca": ("rolagem da cabeça para dentro", "graus", 1, "abs", 2.5),
    "curva_inclinacao_tronco": ("inclinação do tronco para dentro", "graus", 1, "abs", 3.0),
}
CAMPOS_ESCADA = {
    "escada_passos_s": ("passos por segundo", "1/s", 2, "rel", 0.30),
    "escada_osc_cabeca": ("oscilação vertical da cabeça (sem a subida)", "m", 3, "abs", 0.025),
    "escada_vel_horiz": ("velocidade horizontal", "m/s", 2, "rel", 0.40),
    "escada_subida_passo": ("subida por passo (degrau)", "m", 3, "abs", 0.08),
}


class _Perfil(_Faixa):
    """Cenário de um gesto com escalares próprios (`extras`): a marcha padrão continua em `.v`, os campos da tabela são os do gesto."""
    extras = None                   # função(Movimento) -> ({escalar: valor}, marcas)
    campos = None
    palco_minimo = True
    destaques = ()
    chaves_legenda = ()

    def medir(self, mov):
        from .. import metricas
        try:
            marcha = metricas.medir_tudo(mov, self.metodo)
        except Exception:                # noqa: BLE001  (um gesto sem passadas completas não tem marcha)
            marcha = metricas.Marcha()
        valores, marcas = self.extras(mov)
        marcha.v.update(valores)
        marcha.series["marcas"] = marcas
        return marcha

    def marcas(self, mov):
        return self.extras(mov)[1]

    def legenda(self, prep):
        def linhas(rotulo, marcha, escala_rotulo):
            partes = [f"{marcha.v.get(c, float('nan')):.2f}" for c in self.chaves_legenda]
            return (rotulo, " | ".join(partes))
        nome_roteiro = self.roteiro if isinstance(self.roteiro, str) else self.nome
        return (linhas(f"REAL  {prep.real.rotulo}", prep.marcha_real, ""),
                linhas(f"{self.rotulo_jogo}  {nome_roteiro[:24]}", prep.marcha_jogo, ""))

    def estado_instantaneo(self, prep, t_real, t_jogo):
        return []

    def medidas(self, prep, saida):
        """Tabela do gesto, json e a figura das séries (`figura`)."""
        from .. import graficos, metricas
        arquivos = {}
        linhas = self.linhas(prep)
        n = len(prep.marchas_reais)
        rotulo_real = f"real ({n} clipes)" if n > 1 else f"real ({prep.real.rotulo})"
        arquivos["tabela"] = graficos.painel_tabela(linhas, os.path.join(saida, "tabela.png"), titulo=self.titulo,
                                                    rotulo_real=rotulo_real, rotulo_jogo="jogo")
        with open(os.path.join(saida, "tabela.txt"), "w", encoding="utf-8") as arquivo:
            arquivo.write(f"{self.titulo}\n{rotulo_real} x jogo ({self.nome})\n\n{metricas.tabela_texto(linhas)}\n")
        arquivos["tabela_txt"] = os.path.join(saida, "tabela.txt")
        arquivos["series"] = self.figura(prep, os.path.join(saida, "series.png"))
        arquivos["metricas"] = self.salvar_json(prep, linhas, saida)
        return arquivos, linhas

    def figura(self, prep, caminho):
        raise NotImplementedError

    def _par_de_series(self, prep, caminho, titulo, unidade, extrair):
        """Duas séries sobre o tempo alinhado ao início do gesto: `extrair(mov, marcha) -> (t, y)` para o real e o jogo."""
        from .. import graficos
        graficos._estilo()
        import matplotlib.pyplot as plt
        figura, ax = plt.subplots(figsize=(8.0, 3.4))
        for rotulo, mov, marcha, cor in (("real", prep.real.movimento, prep.marcha_real, graficos.COR_REAL),
                                         ("jogo", prep.jogo, prep.marcha_jogo, graficos.COR_JOGO)):
            for nome, (t, y), estilo in extrair(mov, marcha):
                ax.plot(t, y, color=cor, linewidth=1.8, linestyle=estilo, label=f"{rotulo} {nome}".strip())
        ax.set_xlabel("segundos desde o início do gesto")
        ax.set_ylabel(unidade)
        ax.set_title(titulo, loc="left")
        ax.legend(loc="best", ncol=2)
        figura.tight_layout()
        return graficos._salvar(figura, caminho)


@registrar
class Parar(_Perfil):
    nome = "parar"
    titulo = "Parar de andar (soltar a tecla) contra 16_33"
    resumo = ("Andar a 1,05 m/s (a velocidade de 16_33) e soltar a tecla. O jogo para em ~0,7 s; a pessoa de 16_33 leva ~1,4 s: "
              "o jogo é mais responsivo de propósito (STOP_TIME em conventions.py).")
    clip = "16_33"
    faixa = None
    metodo = "zeni"
    campos = CAMPOS_PARAR
    destaques = ("parar_tempo_90_10", "parar_dist_s")
    chaves_legenda = ("parar_v0", "parar_tempo_90_10")
    extras = staticmethod(medir_parada)

    @property
    def roteiro(self):
        return _passos((3.0, 0.62, 0.0, "andar"), (2.5, 0.0, 0.0, "parar"))

    def _clipes(self):
        return [self.clip]

    def recorte_jogo(self, rec):
        return rec.movimento().trecho(0.6, None), 0.6

    def alinhar(self, real, jogo):
        a_real, a_jogo = self.marcas(real)[0], self.marcas(jogo)[0]
        b_real, b_jogo = self.marcas(real)[1], self.marcas(jogo)[1]
        return Alinhamento([a_real / real.fps, b_real / real.fps], [a_jogo / jogo.fps, b_jogo / jogo.fps])

    def fases_chave(self, prep):
        a, b, final = prep.marcha_real.series["marcas"]
        fps = prep.real.movimento.fps
        return [("andando", max(0.1, a / fps - 0.5)), ("começa a frear", a / fps), ("meio da freada", (a + b) / 2 / fps),
                ("parado", min(final / fps, prep.real.movimento.duracao - 0.05))]

    def figura(self, prep, caminho):
        from .. import metricas

        def serie(mov, marcha):
            a = marcha.series["marcas"][0]
            v = metricas.velocidade_horizontal(mov.j("quadril"), mov.fps, 0.10)
            t = np.arange(len(v)) / mov.fps - a / mov.fps
            return [("velocidade", (t, v), "-")]
        return self._par_de_series(prep, caminho, "Velocidade do quadril ao parar (0 = começa a frear)", "m/s", serie)


@registrar
class Curva(_Perfil):
    nome = "curva"
    titulo = "Andar e virar 90 graus (à esquerda) contra 16_17"
    resumo = ("Andar a 1,05 m/s girando 72 graus em 0,8 s (o rumo do quadril, que 16_17 muda em 74). A cabeça vai à frente, o corpo a segue, e a cabeça e o tronco "
              "inclinam para dentro da curva. O jogo não reduz a velocidade na curva (o mocap perde ~20%).")
    clip = "16_17"
    faixa = None
    metodo = "zeni"
    campos = CAMPOS_CURVA
    destaques = ("curva_cabeca_antecipa", "curva_rolagem_cabeca")
    chaves_legenda = ("curva_angulo", "curva_cabeca_antecipa")
    extras = staticmethod(medir_curva)

    @property
    def roteiro(self):
        return _passos((2.0, 0.62, 0.0, "andar"), (0.8, 0.62, 90.0, "virar"), (2.0, 0.62, 0.0, "andar"))

    def _clipes(self):
        return [self.clip]

    def recorte_jogo(self, rec):
        return rec.movimento().trecho(0.6, None), 0.6

    def alinhar(self, real, jogo):
        (ar, br, _), (aj, bj, _) = self.marcas(real), self.marcas(jogo)
        return Alinhamento([ar / real.fps, br / real.fps], [aj / jogo.fps, bj / jogo.fps])

    def fases_chave(self, prep):
        a, b, _ = prep.marcha_real.series["marcas"]
        fps = prep.real.movimento.fps
        return [("antes da curva", max(0.1, a / fps - 0.4)), ("início", a / fps), ("meio", (a + b) / 2 / fps),
                ("fim", min(b / fps + 0.2, prep.real.movimento.duracao - 0.05))]

    def figura(self, prep, caminho):
        def serie(mov, marcha):
            a, _b, sinal = marcha.series["marcas"]
            fps = mov.fps
            t = np.arange(mov.quadros) / fps - a / fps
            olhar = mov.cabeca_rot @ np.array([0.0, 0.0, -1.0])
            cabeca = _angulo(olhar[:, :2])
            d = mov.j("coxa_d") - mov.j("coxa_e")
            pelve = _angulo(np.stack([-d[:, 1], d[:, 0]], axis=1))
            return [("cabeça", (t, sinal * (_gauss(cabeca, 0.15, fps) - cabeca[max(0, a - int(0.5 * fps))])), "-"),
                    ("pelve", (t, sinal * (_gauss(pelve, 0.15, fps) - pelve[max(0, a - int(0.5 * fps))])), (0, (4, 2)))]
        return self._par_de_series(prep, caminho, "Rumo da cabeça e da pelve na curva (0 = início do giro)", "graus", serie)


@registrar
class Escada(_Perfil):
    nome = "escada"
    titulo = "Subir a escada da casa contra 83_27 a 83_35"
    resumo = ("Subir os 15 degraus (18,7 cm) da casa. O ritmo é de 1,5 passos/s; a CMU sobe a 1,0 a 1,2 passos/s em degraus de "
              "12 a 16 cm. Os pés ficam sobre os degraus e a cabeça sobe em rampa com a oscilação medida.")
    clip = "83_27"
    faixa = None
    metodo = "zeni"
    campos = CAMPOS_ESCADA
    palco_minimo = False
    destaques = ("escada_passos_s", "escada_osc_cabeca")
    chaves_legenda = ("escada_passos_s", "escada_osc_cabeca")
    extras = staticmethod(medir_escada)
    lento = 0.4
    vistas = ("lado", "frente", "primeira")
    clipes_reais = ("83_27", "83_28", "83_29", "83_30", "83_31", "83_32", "83_34", "83_35")

    @property
    def roteiro(self):
        from .. import grava

        def colocar(jogo):
            jogo.place_player(5.6, 2.0, 0.0, 0.0)
        return [grava.Passo(10.0, mover=1.0, ao_iniciar=colocar, rotulo="escada")]

    def _clipes(self):
        return list(self.clipes_reais)

    def recorte_jogo(self, rec):
        mov = rec.movimento()
        a, b = janela_subida(mov) or (0, mov.quadros)
        inicio = max(0.0, a / mov.fps - 1.0)
        return mov.trecho(inicio, None), inicio

    def alinhar(self, real, jogo):
        (ar, br), (aj, bj) = self.marcas(real), self.marcas(jogo)
        return Alinhamento([ar / real.fps, br / real.fps], [aj / jogo.fps, bj / jogo.fps])

    def fases_chave(self, prep):
        a, b = prep.marcha_real.series["marcas"]
        fps = prep.real.movimento.fps
        return [(f"{int(100 * f)}% da subida", (a + f * (b - a)) / fps) for f in (0.0, 0.33, 0.66, 1.0)]

    def figura(self, prep, caminho):
        def serie(mov, marcha):
            a, b = marcha.series["marcas"]
            fps = mov.fps
            cabeca = mov.cabeca_pos()[:, 2]
            t = np.arange(b - a) / fps
            residuo = cabeca[a:b] - np.polyval(np.polyfit(t, cabeca[a:b], 1), t)
            return [("cabeça sem a subida", (t, residuo * 100), "-")]
        return self._par_de_series(prep, caminho, "Oscilação vertical da cabeça subindo (sem a reta de subida)", "cm", serie)
