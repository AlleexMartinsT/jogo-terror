"""Classe base dos cenários de comparação e os objetos que ela troca com `comparar.py`.

Um cenário de CORPO (andar, correr, pegar do chão...) só precisa declarar atributos; o que faltar tem um padrão de marcha:

    @registrar
    class Correr(Cenario):
        nome = "correr"
        titulo = "Correr"
        clip = "09_01"                  # id CMU do clipe do vídeo (cmu.REFERENCIAS, cmu.buscar)
        grupo = "correr"                # cmu.GRUPOS: vários clipes reais para a faixa de +-1 desvio (opcional)
        roteiro = "correr 4"            # roteiro do jogo (grava.roteiro_de_texto) ou lista de grava.Passo
        passo = 0                       # qual passo do roteiro medir e mostrar
        metodo = "altura"               # eventos da marcha: "zeni" (andar) ou "altura" (correr)

Para outros tipos de gesto, sobrescreva os ganchos (cada um com o padrão de marcha):

    carregar_real()            -> Real: o movimento de referência e o Daniel retargetado
    gravar_jogo(jogo)          -> Gravacao: executa o roteiro no `Game`
    recorte_jogo(rec)          -> (Movimento, t0): o trecho medido da gravação e onde ele começa na gravação
    alinhar(real, jogo)        -> Alinhamento: marcas de FASE em cada relógio (toque do calcanhar, início e fim do alcance...)
    fases_chave(prep)          -> [(nome, segundos no relógio do real)]: os quadros da folha de contato
    medir(mov)                 -> Marcha (ou qualquer objeto com .v, .curvas, .eventos): as métricas do cenário
    legenda(prep)              -> (texto do real, texto do jogo): o que aparece no vídeo
    executar(saida, ...)       -> tudo: sobrescreva só para gestos que não têm corpo no vídeo (portas, pêndulos), usando
                                  as funções de comparar.py (escrever_mp4, grade, rotular, ...) para o que servir.

Alinhamento é por FASE, não por relógio: o real e o jogo têm cadências diferentes, então o vídeo toca cada ciclo do jogo no
tempo do ciclo do real (mostrando o fator de velocidade na legenda).
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Real:
    rotulo: str                       # "CMU 07_01"
    movimento: object                 # Movimento do mocap (relógio do recorte, 0 = início)
    alvo: object = None               # Retarget do Daniel, ou None quando o cenário não tem corpo
    grupo: list = field(default_factory=list)     # Movimentos de vários clipes: a faixa de +-1 desvio e a tolerância
    descricao: str = ""


@dataclass
class Alinhamento:
    """Pares de marcas de fase: `real[i]` e `jogo[i]` são o MESMO instante do gesto (cada um no seu relógio)."""
    real: np.ndarray
    jogo: np.ndarray

    def __post_init__(self):
        self.real, self.jogo = np.asarray(self.real, float), np.asarray(self.jogo, float)
        if len(self.real) != len(self.jogo) or len(self.real) < 1:
            raise ValueError("o alinhamento precisa de ao menos uma marca em cada relógio, em igual número")

    @staticmethod
    def _mapear(x, de, para):
        """Interpolação linear por partes de `de` para `para`; fora das marcas continua com a inclinação da ponta."""
        if len(de) == 1:
            return x - de[0] + para[0]
        x = np.asarray(x, float)
        dentro = np.interp(x, de, para)
        inclinacao_ini = (para[1] - para[0]) / (de[1] - de[0])
        inclinacao_fim = (para[-1] - para[-2]) / (de[-1] - de[-2])
        antes, depois = x < de[0], x > de[-1]
        dentro = np.where(antes, para[0] + (x - de[0]) * inclinacao_ini, dentro)
        return np.where(depois, para[-1] + (x - de[-1]) * inclinacao_fim, dentro)

    def jogo_de_real(self, t_real):
        return self._mapear(t_real, self.real, self.jogo)

    def real_de_jogo(self, t_jogo):
        return self._mapear(t_jogo, self.jogo, self.real)

    def razao(self, t_real):
        """Segundos de jogo por segundo de real em torno de `t_real` (1 = mesma velocidade; <1 = o jogo é mais rápido)."""
        passo = 1e-3
        return float((self.jogo_de_real(t_real + passo) - self.jogo_de_real(t_real - passo)) / (2 * passo))


@dataclass
class Preparado:
    """Tudo que `comparar.py` precisa para renderizar e medir, depois de `Cenario.preparar`."""
    cenario: object
    real: Real
    gravacao: object                  # Gravacao do jogo
    jogo: object                      # Movimento do trecho medido do jogo
    jogo_t0: float                    # segundos, na gravação, em que `jogo` começa
    alinhamento: Alinhamento
    marcha_real: object = None
    marchas_reais: list = field(default_factory=list)
    marcha_jogo: object = None


class Cenario:
    nome = ""
    titulo = ""
    resumo = ""
    # --- referência real
    clip = "07_01"
    trecho = (None, None)             # recorte do clipe, em segundos (None: todo, sem os 0,1 s iniciais de calibração)
    grupo = None                      # chave de cmu.GRUPOS
    bracos = "direcao"                # "direcao" ou "ik" (retarget.py)
    # --- jogo
    roteiro = "andar 6"
    passo = 0                         # índice do passo do roteiro que se mede e se mostra
    margem = 0.8                      # segundos iniciais do passo descartados (aceleração)
    palco_minimo = True               # grava no palco vazio; False abre o .blend completo
    prefacio = 0.3
    # --- medida
    metodo = "zeni"                   # eventos da marcha (metricas.eventos_marcha)
    campos = None                     # tabela de tolerâncias (metricas.CAMPOS_MARCHA quando None)
    # --- vídeo
    lento = 0.5                       # fator de câmera lenta (0,5 = metade da velocidade)
    vistas = ("frente", "lado", "topo", "primeira")
    rotulo_jogo = "JOGO"

    # ------------------------------------------------------------------ ganchos com padrão de marcha
    def carregar_real(self):
        from .. import cmu, metricas, retarget
        from ..movimento import movimento_de_mocap
        clip = cmu.carregar(self.clip)
        inicio, fim = self.trecho
        alvo = retarget.retargetar(clip, inicio, fim, bracos=self.bracos)
        movimento = alvo.origem
        grupo = []
        if self.grupo:
            grupo = [movimento_de_mocap(cmu.carregar(c)) for c in cmu.GRUPOS[self.grupo]]
        return Real(f"CMU {self.clip}", movimento, alvo, grupo or [movimento], descricao=dict(
            (v[0], v[1]) for v in cmu.REFERENCIAS.values()).get(self.clip, ""))

    def gravar_jogo(self, jogo):
        from .. import grava
        roteiro = grava.roteiro_de_texto(self.roteiro) if isinstance(self.roteiro, str) else self.roteiro
        return grava.gravar(jogo, roteiro, nome=self.nome, ossos="armadura", prefacio=self.prefacio)

    def recorte_jogo(self, rec):
        inicio, fim, _ = rec.passos[self.passo]
        return rec.movimento().trecho(inicio + self.margem, fim), inicio + self.margem

    def medir(self, mov):
        from .. import metricas
        return metricas.medir_tudo(mov, self.metodo)

    def medir_jogo(self, mov):
        """Como `medir`, para o trecho do jogo (gestos escolhem o alcance do jogo e do real por critérios diferentes)."""
        return self.medir(mov)

    def alinhar(self, real, jogo):
        """Marcas = toques do calcanhar esquerdo dos dois lados (o mesmo evento do ciclo)."""
        from .. import metricas
        toques_real = metricas.eventos_marcha(real, self.metodo).tempos("toque", "e")
        toques_jogo = metricas.eventos_marcha(jogo, self.metodo).tempos("toque", "e")
        n = min(len(toques_real), len(toques_jogo))
        if n < 1:
            raise RuntimeError(f"cenário {self.nome}: sem toque do calcanhar esquerdo para alinhar a fase")
        return Alinhamento(toques_real[:n], toques_jogo[:n])

    def fases_chave(self, prep):
        """Quatro quadros do ciclo: toque do calcanhar, apoio médio, saída do pé, balanço médio (relógio do real)."""
        from .. import metricas
        eventos = metricas.eventos_marcha(prep.real.movimento, self.metodo)
        toques, saidas = eventos.tempos("toque", "e"), eventos.tempos("saida", "e")
        for i in range(len(toques) - 1):
            saida = saidas[(saidas > toques[i]) & (saidas < toques[i + 1])]
            if len(saida):
                a, s, b = toques[i], saida[0], toques[i + 1]
                return [("toque do calcanhar", a), ("apoio médio", (a + s) / 2), ("saída do pé", s),
                        ("balanço médio", (s + b) / 2)]
        total = prep.real.movimento.duracao
        return [(f"{int(100 * f)}%", f * total) for f in (0.1, 0.35, 0.6, 0.85)]

    destaques = ("cadencia", "passo", "apoio_pct", "deslize_apoio", "cabeca_osc_vert")      # métricas no canto do vídeo

    def legenda(self, prep):
        """((linha 1, linha 2) do real, (linha 1, linha 2) do jogo) para o vídeo; cada linha cabe em ~38 caracteres."""
        v_real, v_jogo = prep.marcha_real.v, prep.marcha_jogo.v
        escala = prep.real.alvo.escala if prep.real.alvo is not None else 1.0
        real = (f"REAL  {prep.real.rotulo}", f"{v_real.get('velocidade', float('nan')) * escala:.2f} m/s no Daniel")
        nome_roteiro = self.roteiro if isinstance(self.roteiro, str) else self.nome
        jogo = (f"{self.rotulo_jogo}  {nome_roteiro[:24]}", f"{v_jogo.get('velocidade', float('nan')):.2f} m/s")
        return real, jogo

    # ------------------------------------------------------------------ tabela, gráficos e estado do instante
    def linhas(self, prep):
        """Linhas da tabela real x jogo (metricas.Linha): o real é a média dos clipes do grupo."""
        from .. import metricas
        real_v = metricas.v_medio(prep.marchas_reais)
        dispersao = metricas.dispersao_populacao([m.v for m in prep.marchas_reais], self.campos)
        return metricas.comparar_metricas(real_v, prep.marcha_jogo.v, self.campos, dispersao=dispersao)

    def medidas(self, prep, saida):
        """Gráficos, tabela e json. Devolve ({nome: caminho}, linhas). Padrão: marcha."""
        import json
        import os
        from .. import graficos, metricas
        arquivos = {}
        linhas = self.linhas(prep)
        titulo = self.titulo
        n_clipes = len(prep.marchas_reais)
        rotulo_real = f"real ({n_clipes} clipes)" if n_clipes > 1 else f"real ({prep.real.rotulo})"
        arquivos["tabela"] = graficos.painel_tabela(linhas, os.path.join(saida, "tabela.png"), titulo=titulo,
                                                    rotulo_real=rotulo_real, rotulo_jogo="jogo")
        with open(os.path.join(saida, "tabela.txt"), "w", encoding="utf-8") as arquivo:
            arquivo.write(f"{titulo}\n{rotulo_real} x jogo ({self.roteiro})\n\n{metricas.tabela_texto(linhas)}\n")
        arquivos["tabela_txt"] = os.path.join(saida, "tabela.txt")
        arquivos["curvas"] = graficos.painel_curvas(prep.marchas_reais, prep.marcha_jogo, os.path.join(saida, "curvas.png"),
                                                    titulo=titulo, rotulo_real=rotulo_real, rotulo_jogo="jogo")
        arquivos["apoios"] = graficos.diagrama_apoios(prep.real.movimento, prep.jogo, os.path.join(saida, "apoios.png"),
                                                      titulo="Apoios dos pés", metodo=self.metodo,
                                                      janela=(0, min(prep.real.movimento.duracao, prep.jogo.duracao)))
        arquivos["metricas"] = self.salvar_json(prep, linhas, saida)
        return arquivos, linhas

    def salvar_json(self, prep, linhas, saida):
        import json
        import os
        from .. import metricas
        registro = {"cenario": self.nome, "real": metricas.v_medio(prep.marchas_reais), "jogo": prep.marcha_jogo.v,
                    "dispersao_real": metricas.dispersao_populacao([m.v for m in prep.marchas_reais]),
                    "clipes_reais": [m.nome for m in prep.real.grupo],
                    "tabela": [{"chave": l.chave, "real": l.real, "jogo": l.jogo, "dif": l.diferenca, "tol": l.tolerancia, "ok": l.ok}
                               for l in linhas], "avisos": prep.gravacao.meta.get("avisos", [])}
        caminho = os.path.join(saida, "metricas.json")
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(registro, arquivo, ensure_ascii=False, indent=1, default=float)
        return caminho

    def estado_instantaneo(self, prep, t_real, t_jogo):
        """Linhas do painel de texto do vídeo para este instante: [{"rotulo", "cor", "itens": [(texto, cheio|None)]}].
        Padrão da marcha: quais pés tocam o chão."""
        import numpy as np
        from .. import metricas
        cache = getattr(prep, "_eventos_cache", None)
        if cache is None:
            cache = prep._eventos_cache = (metricas.eventos_marcha(prep.real.movimento, self.metodo),
                                           metricas.eventos_marcha(prep.jogo, self.metodo))
        saida = []
        for rotulo, cor, eventos, t, fps in (("REAL", (42, 120, 214), cache[0], t_real, prep.real.movimento.fps),
                                             ("JOGO", (235, 104, 52), cache[1], t_jogo, prep.jogo.fps)):
            indice = int(np.clip(round(t * fps), 0, len(eventos.contato["e"]) - 1))
            itens = []
            for lado, nome in (("e", "pé esq."), ("d", "pé dir.")):
                no_chao = bool(eventos.contato[lado][indice])
                itens.append((f"{nome} {'no chão' if no_chao else 'no ar'}", no_chao))
            saida.append({"rotulo": rotulo, "cor": cor, "itens": itens})
        return saida

    # ------------------------------------------------------------------ montagem
    def preparar(self, jogo=None):
        """Carrega o real, grava o jogo, mede os dois e alinha. `jogo`: um `Game` já montado (senão monta um)."""
        from .. import grava
        real = self.carregar_real()
        if jogo is None:
            jogo = grava.montar_jogo(palco=self.palco_minimo)
        rec = self.gravar_jogo(jogo)
        mov_jogo, t0 = self.recorte_jogo(rec)
        marcha_jogo = self.medir_jogo(mov_jogo)
        marchas_reais = [self.medir(m) for m in real.grupo]
        marcha_real = self.medir(real.movimento)
        alinhamento = self.alinhar(real.movimento, mov_jogo)
        return Preparado(self, real, rec, mov_jogo, t0, alinhamento, marcha_real, marchas_reais, marcha_jogo)

    def executar(self, saida, vistas=None, **opcoes):
        """Roda a comparação completa (padrão: corpo). Devolve o dict de arquivos gerados."""
        from .. import comparar
        return comparar.executar_corpo(self, saida, vistas or self.vistas, **opcoes)


# --------------------------------------------------------------------------
# Gestos da mão
# --------------------------------------------------------------------------
# chave: (rótulo, unidade, casas, tipo de tolerância, valor). Tolerâncias de partida; quem tuna o gesto pode trocá-las.
CAMPOS_ALCANCE = {
    "duracao": ("duração do alcance", "s", 2, "rel", 0.25),
    "distancia": ("distância percorrida pela mão", "m", 2, "rel", 0.20),
    "velocidade_pico": ("velocidade de pico da mão", "m/s", 2, "rel", 0.25),
    "pico_fracao": ("instante do pico (fração da duração)", "", 2, "abs", 0.08),
    "pico_razao": ("pico / velocidade média (jerk mínimo = 1,875)", "", 2, "abs", 0.30),
    "r2_jerk_minimo": ("R2 do ajuste ao jerk mínimo", "", 2, "abs", 0.15),
}


@dataclass
class Medida:
    """O que `CenarioAlcance.medir` devolve: o mesmo formato de `Marcha` (`.v`, `.curvas`, `.eventos`) mais o perfil."""
    v: dict
    velocidade: np.ndarray = None     # m/s por quadro da mão que alcança
    fps: float = 0.0
    janela: tuple = (0, 0)            # quadros do alcance escolhido
    ajuste: dict = field(default_factory=dict)
    curvas: dict = field(default_factory=dict)
    eventos: object = None


class CenarioAlcance(Cenario):
    """Gesto da mão (alcançar, pegar, empurrar, olhar com a lanterna). Declare o clipe, o trecho dele e o roteiro; o resto
    compara o PERFIL DE VELOCIDADE do alcance com o do mocap e com o de jerk mínimo, e alinha pela fase do alcance (início,
    pico de velocidade, chegada)."""
    lado_mao = "d"
    junta_mao = "punho"
    bracos = "ik"                     # as mãos têm de chegar aonde o braço do Daniel alcança, não onde o do mocap alcançou
    vel_minima = 0.4                  # m/s: abaixo disso não é um alcance
    alcance_real = "maior"            # n-ésimo alcance detectado (0, 1, ...) ou "maior" (maior pico de velocidade)
    alcance_jogo = "maior"
    campos = CAMPOS_ALCANCE
    destaques = ("duracao", "distancia", "velocidade_pico", "pico_fracao", "pico_razao")
    metodo = None
    lento = 0.4
    margem = 0.0

    def _escolher(self, alcances, velocidade, qual):
        if not alcances:
            return None
        if qual == "maior":
            return max(alcances, key=lambda par: velocidade[par[0]:par[1]].max())
        return alcances[min(int(qual), len(alcances) - 1)]

    def medir(self, mov, qual=None):
        from .. import metricas
        qual = self.alcance_real if qual is None else qual
        velocidade = metricas.perfil_mao(mov, self.lado_mao, self.junta_mao)
        alcances = metricas.detectar_alcances(velocidade, mov.fps, self.vel_minima)
        escolhido = self._escolher(alcances, velocidade, qual)
        nan = float("nan")
        v = {chave: nan for chave in CAMPOS_ALCANCE}
        ajuste = {}
        if escolhido is not None:
            ajuste = metricas.ajuste_jerk_minimo(velocidade, escolhido[0], escolhido[1], mov.fps)
            v.update({chave: ajuste[chave] for chave in CAMPOS_ALCANCE if chave in ajuste})
            v["n_alcances"] = float(len(alcances))
        return Medida(v, velocidade, mov.fps, escolhido or (0, 0), ajuste)

    def alinhar(self, real, jogo):
        medida_real = self.medir(real, self.alcance_real)
        medida_jogo = self.medir(jogo, self.alcance_jogo)
        if not medida_real.ajuste or not medida_jogo.ajuste:
            raise RuntimeError(f"cenário {self.nome}: sem alcance detectado (real: {bool(medida_real.ajuste)}, jogo: "
                               f"{bool(medida_jogo.ajuste)}); confira o trecho do clipe e o roteiro")

        def marcas(m):
            a = m.ajuste
            return [a["inicio"], a["inicio"] + a["pico_fracao"] * a["duracao"], a["inicio"] + a["duracao"]]
        return Alinhamento(marcas(medida_real), marcas(medida_jogo))

    def medir_jogo(self, mov):
        return self.medir(mov, self.alcance_jogo)

    def fases_chave(self, prep):
        a = prep.marcha_real.ajuste
        t0, T = a["inicio"], a["duracao"]
        return [("inicio do alcance", t0), ("subida da velocidade", t0 + 0.25 * T),
                ("pico de velocidade", t0 + a["pico_fracao"] * T), ("chegada", t0 + T)]

    def legenda(self, prep):
        real, jogo = prep.marcha_real, prep.marcha_jogo
        nome_roteiro = self.roteiro if isinstance(self.roteiro, str) else self.nome
        return ((f"REAL  {prep.real.rotulo}", f"{real.v['duracao']:.2f} s, {real.v['distancia']:.2f} m"),
                (f"{self.rotulo_jogo}  {nome_roteiro[:24]}", f"{jogo.v['duracao']:.2f} s, {jogo.v['distancia']:.2f} m"))

    def linhas(self, prep):
        from .. import metricas
        return metricas.comparar_metricas(metricas.v_medio(prep.marchas_reais), prep.marcha_jogo.v, self.campos,
                                          dispersao=metricas.dispersao_populacao([m.v for m in prep.marchas_reais], self.campos))

    def estado_instantaneo(self, prep, t_real, t_jogo):
        import numpy as np
        saida = []
        for rotulo, cor, medida, t in (("REAL", (42, 120, 214), prep.marcha_real, t_real), ("JOGO", (235, 104, 52), prep.marcha_jogo, t_jogo)):
            i = int(np.clip(round(t * medida.fps), 0, len(medida.velocidade) - 1))
            v = float(medida.velocidade[i])
            saida.append({"rotulo": rotulo, "cor": cor, "itens": [(f"mão {v:.2f} m/s", v > 0.2 * medida.v["velocidade_pico"])]})
        return saida

    def medidas(self, prep, saida):
        import os
        import numpy as np
        from .. import graficos, metricas
        arquivos = {}
        linhas = self.linhas(prep)
        n = len(prep.marchas_reais)
        rotulo_real = f"real ({n} clipes)" if n > 1 else f"real ({prep.real.rotulo})"
        arquivos["tabela"] = graficos.painel_tabela(linhas, os.path.join(saida, "tabela.png"), titulo=self.titulo,
                                                    rotulo_real=rotulo_real, rotulo_jogo="jogo")
        with open(os.path.join(saida, "tabela.txt"), "w", encoding="utf-8") as arquivo:
            arquivo.write(f"{self.titulo}\n{rotulo_real} x jogo ({self.roteiro})\n\n{metricas.tabela_texto(linhas)}\n")
        arquivos["tabela_txt"] = os.path.join(saida, "tabela.txt")

        def normalizado(medida):
            a = medida.ajuste
            t = a["inicio"] + np.linspace(-0.15, 1.15, 131) * a["duracao"]
            tempos = np.arange(len(medida.velocidade)) / medida.fps
            return np.interp(t, tempos, medida.velocidade)
        perfis = [(prep.real.rotulo, normalizado(prep.marcha_real), 0, graficos.COR_REAL),
                  ("jogo", normalizado(prep.marcha_jogo), 0, graficos.COR_JOGO)]
        arquivos["alcance"] = graficos.painel_alcance(perfis, os.path.join(saida, "alcance.png"), titulo=self.titulo,
                                                      modelo=(prep.marcha_real.v["distancia"], prep.marcha_real.v["duracao"]))
        arquivos["metricas"] = self.salvar_json(prep, linhas, saida)
        return arquivos, linhas
