"""Cenários dos objetos: o jogo contra a FÍSICA (não há mocap de porta, carro ou relógio; o que há de mocap é a mão).

    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.comparar porta --saida out/movimento/porta
    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.comparar carro --saida out/movimento/carro

Cenários: porta, pendulo_relogio, chaveiro, portao, carro, cortina. Cada um roda o jogo sem janela (`fisica/grava.py`), roda o
modelo físico independente (`fisica/*.py`), escreve a tabela métrica a métrica (valor físico, jogo antes, jogo depois, tolerância,
origem DERIVADO/ESTIMADO/MEDIDO), os painéis [modelo | jogo | sobrepostos] e o vídeo lado a lado (MP4, 30 quadros/s).

Os vídeos são esquemas desenhados a partir das posições (vista de cima da porta, vista de frente do relógio, de lado do carro e
do portão): quem se move é o objeto, e os dois lados vêm de fontes independentes. Fonte de cada número:
  MEDIDO   a mão que empurra e ergue (mocap CMU 56_03..08, 81_05..82_07): duração, pico e razão pico/média do gesto;
  DERIVADO leis sobre medidas do modelo 3D: I = m L^2 / 3, pêndulo composto, Bernoulli da cortina, Stefan-Boltzmann, rolar sem
           deslizar, Ackermann, Schiller-Naumann;
  ESTIMADO massa da folha, atrito da dobradiça, limites de força da mão, frequências de passeio, abridor de 15 a 20 cm/s, etc.
"""
import os

from . import registrar
from .base import Cenario


def _escrever_tabela(saida, nome, lista):
    from ..fisica import medidas
    caminho = os.path.join(saida, f"{nome}_tabela.md")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(medidas.tabela_markdown(lista) + "\n")
    return caminho


class CenarioObjeto(Cenario):
    """Base dos objetos: sem corpo no vídeo, então `executar` faz tudo com as ferramentas de `fisica/`."""
    filtro_metricas = ()              # trechos de nome que escolhem as métricas do cenário
    paineis = ()                      # nomes das funções de `fisica.paineis` (recebem os dados via `dados`)
    video = ""                        # chave de `fisica.video.CENAS`
    lento = 1.0
    vistas = ("topo",)

    def metricas(self):
        raise NotImplementedError

    def dados(self):
        """(g, g0, s, s0, p, p0, amb, amb0, r) de `paineis.todas_as_metricas`; só os cenários que precisam pedem."""
        raise NotImplementedError

    def executar(self, saida, vistas=None, video=True, **opcoes):
        from ..fisica import paineis, video as videos
        os.makedirs(saida, exist_ok=True)
        antigo = paineis.SAIDA
        paineis.SAIDA = saida
        arquivos = {}
        try:
            lista = self.metricas()
            arquivos["tabela"] = _escrever_tabela(saida, self.nome, lista)
            arquivos["tabela_ok"] = f"{sum(m.ok for m in lista)}/{len(lista)} métricas dentro da faixa"
            for k, caminho in enumerate(self.fazer_paineis(paineis)):
                arquivos[f"painel_{k}"] = caminho
        finally:
            paineis.SAIDA = antigo
        if video and self.video:
            arquivos["video"] = videos.gerar(self.video, saida)
        for chave, valor in arquivos.items():
            print(f"[{self.nome}] {chave}: {valor}")
        return arquivos

    def fazer_paineis(self, paineis):
        return []


@registrar
class Porta(CenarioObjeto):
    nome = "porta"
    titulo = "Porta: folha de 25 kg numa dobradiça, empurrada por uma mão, contra a simulação (e a mão do mocap)"
    resumo = ("Abrir andando, ritmos, as 13 portas, inverter no meio, fechar com trinco e bater. A quíntica do jogo é a trajetória de "
              "mínima variação de torque; o esforço da mão tem de ficar abaixo de 100 N; a batida é um golpe de 400 N por 0,15 s.")
    video = "porta"

    def _g(self):
        from ..fisica import comparar_porta, medidas
        g = comparar_porta.gravar()
        return g, medidas.carregar_gravacao("porta")

    def metricas(self):
        from ..fisica import comparar_porta
        g, _ = self._g()
        return comparar_porta.metricas_com_antes(g)

    def fazer_paineis(self, paineis):
        g, g0 = self._g()
        return [paineis.painel_porta_abrir(g, g0), paineis.painel_porta_empurrao(), paineis.painel_porta_fecha_batida(g, g0),
                paineis.painel_porta_inverte(g, g0), paineis.painel_porta_13(g, g0), paineis.painel_mao_real(g)]


@registrar
class PenduloRelogio(CenarioObjeto):
    nome = "pendulo_relogio"
    titulo = "Relógio de pé: pêndulo de segundos (T = 2 s), tique depois do centro e ponteiro dos segundos em degraus de 6 graus"
    resumo = "l_eq = 0,994 m; o modelo 3D antigo tinha 0,54 m (T = 1,47 s). O tique cai 25 ms depois do centro e junto do laço de áudio."
    video = "relogio"

    def metricas(self):
        from ..fisica import comparar_relogio, grava
        return comparar_relogio.tabela_antes(comparar_relogio.metricas(grava.relogio()))

    def fazer_paineis(self, paineis):
        from ..fisica import grava
        return [paineis.painel_relogio(grava.relogio())]


class _Carro(CenarioObjeto):
    def _dados(self):
        from ..fisica import comparar_carro, medidas
        s, p = comparar_carro.gravar()
        return s, p, medidas.carregar_gravacao("carro"), medidas.carregar_gravacao("portao")

    def metricas(self):
        from ..fisica import comparar_carro
        s, p, _, _ = self._dados()
        return [m for m in comparar_carro.metricas_com_antes(s, p) if self.filtro(m)]

    def filtro(self, metrica):
        return True


@registrar
class Chaveiro(_Carro):
    nome = "chaveiro"
    titulo = "Coelhinho do retrovisor e chaveiro: pêndulo composto (comprimento e inércia da malha) forçado pelo carro"
    resumo = "l_eq = I/(m d) da malha: 0,171 m (T = 0,83 s) e 0,099 m (T = 0,63 s); antes eram 0,20 e 0,07 e o sentido era o contrário."
    video = "charm"

    def filtro(self, m):
        return "coelhinho" in m.nome or "chaveiro" in m.nome

    def fazer_paineis(self, paineis):
        s, p, s0, p0 = self._dados()
        return [paineis.painel_charm(s, s0)]


@registrar
class Portao(_Carro):
    nome = "portao"
    titulo = "Portão da garagem: abridor residencial a ~19 cm/s com partida e parada suaves (2,3 m em ~12 s)"
    resumo = "Antes sobe 2,3 m em 3 s (0,77 m/s médio, 1,4 m/s de pico). Agora liga no início da cena e o carro só passa com folga."
    video = "portao"

    def filtro(self, m):
        return m.grupo == "portão"

    def fazer_paineis(self, paineis):
        s, p, s0, p0 = self._dados()
        return [paineis.painel_portao(p, p0, s, s0)]


@registrar
class Carro(_Carro):
    nome = "carro"
    titulo = "Carro: arfagem do meio carro, rodas rolando sem deslizar, Ackermann, volante 15:1, marcha lenta e o chão do mundo"
    resumo = "Sedã de 1500 kg, 0 a 100 km/h em 10 s; suspensão a 1,15 e 1,30 Hz com zeta 0,3. Corrigidos: arfagem e rodas ao contrário."
    video = "carro"

    def filtro(self, m):
        return m.grupo == "carro" and "coelhinho" not in m.nome and "chaveiro" not in m.nome

    def fazer_paineis(self, paineis):
        s, p, s0, p0 = self._dados()
        return [paineis.painel_carro_suspensao(s, s0), paineis.painel_carro_rodas(s, s0)]


@registrar
class Cortina(CenarioObjeto):
    nome = "cortina"
    titulo = "Cortina ao vento: modos de um pano pendurado excitados por vento turbulento (e poeira e luzes do ambiente)"
    resumo = "f_n = j_0n sqrt(g/H)/(4 pi): 0,40 / 0,92 / 1,44 Hz para 2,26 m; antes a cortina balançava a 0,13 a 0,25 Hz."
    video = "cortina"

    def _g(self):
        from ..fisica import comparar_ambiente, medidas
        return comparar_ambiente.gravar(), {n: medidas.carregar_gravacao(n) for n in ("cortina", "poeira", "luzes")}

    def metricas(self):
        from ..fisica import comparar_ambiente
        g, _ = self._g()
        return comparar_ambiente.metricas_com_antes(g)

    def fazer_paineis(self, paineis):
        g, g0 = self._g()
        return [paineis.painel_cortina(g["cortina"], g0["cortina"]), paineis.painel_poeira(g["poeira"], g0["poeira"]),
                paineis.painel_luz(g["luzes"], g0["luzes"])]
