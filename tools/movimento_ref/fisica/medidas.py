"""Tabela métrica a métrica: valor físico, jogo antes, jogo depois, tolerância, origem do número."""
import json
import math
import os
import pickle
from dataclasses import asdict, dataclass, field

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SAIDA = os.path.join(RAIZ, "out", "f4_4")
ANTES = os.path.join(SAIDA, "antes")
DEPOIS = os.path.join(SAIDA, "depois")
FINAL = os.path.join(SAIDA, "final")
FONTES = ("DERIVADO", "ESTIMADO", "MEDIDO")


@dataclass
class Metrica:
    """Uma afirmação de proximidade: `jogo` tem de cair em [`lo`, `hi`], a faixa em torno do valor físico."""
    grupo: str
    nome: str
    unidade: str
    fisico: float
    jogo: float
    lo: float
    hi: float
    fonte: str = "DERIVADO"
    antes: float = None
    nota: str = ""

    def __post_init__(self):
        assert self.fonte in FONTES, self.fonte

    @classmethod
    def igual(cls, grupo, nome, unidade, fisico, jogo, tol, relativa=True, **extra):
        """O jogo tem de ficar a `tol` do valor físico (fração dele, ou absoluta com `relativa=False`)."""
        folga = abs(fisico) * tol if relativa else tol
        return cls(grupo, nome, unidade, fisico, jogo, fisico - folga, fisico + folga, **extra)

    @classmethod
    def limite_max(cls, grupo, nome, unidade, limite, jogo, **extra):
        return cls(grupo, nome, unidade, limite, jogo, -math.inf, limite, **extra)

    @classmethod
    def limite_min(cls, grupo, nome, unidade, limite, jogo, **extra):
        return cls(grupo, nome, unidade, limite, jogo, limite, math.inf, **extra)

    @property
    def ok(self):
        return self.lo <= self.jogo <= self.hi

    @property
    def tolerancia(self):
        """Texto da tolerância para a tabela."""
        if math.isinf(self.lo):
            return f"<= {_formata(self.hi)}"
        if math.isinf(self.hi):
            return f">= {_formata(self.lo)}"
        centro = 0.5 * (self.lo + self.hi)
        metade = 0.5 * (self.hi - self.lo)
        if abs(centro - self.fisico) < 1e-9 * max(1.0, abs(self.fisico)) and self.fisico:
            return f"+-{metade / abs(self.fisico) * 100:.3g}%"
        return f"[{_formata(self.lo)}, {_formata(self.hi)}]"

    @property
    def antes_ok(self):
        return None if self.antes is None else self.lo <= self.antes <= self.hi

    def chave(self):
        return f"{self.grupo}/{self.nome}"


def _formata(valor, casas=3):
    if valor is None:
        return "-"
    magnitude = abs(valor)
    if magnitude != 0 and (magnitude >= 1000 or magnitude < 0.01):
        return f"{valor:.2e}"
    return f"{valor:.{casas}g}"


def tabela_markdown(medidas):
    linhas = ["| Grupo | Métrica | Unid. | Física | Jogo antes | Jogo depois | Tolerância | Origem | OK |",
              "|---|---|---|---|---|---|---|---|---|"]
    for m in medidas:
        linhas.append(f"| {m.grupo} | {m.nome} | {m.unidade} | {_formata(m.fisico)} | {_formata(m.antes)} | "
                      f"{_formata(m.jogo)} | {m.tolerancia} | {m.fonte} | {'sim' if m.ok else 'NÃO'} |")
    return "\n".join(linhas)


def salvar_gravacao(grupo, series, pasta=ANTES):
    """Guarda as séries gravadas do jogo (dict aninhado de arrays). `pasta=ANTES` congela o jogo sem as correções."""
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, f"{grupo}.pkl"), "wb") as arquivo:
        pickle.dump(series, arquivo)


def carregar_gravacao(grupo, pasta=ANTES):
    caminho = os.path.join(pasta, f"{grupo}.pkl")
    if not os.path.exists(caminho):
        return None
    with open(caminho, "rb") as arquivo:
        return pickle.load(arquivo)


def completar_antes(depois, antes):
    """Copia para `depois[i].antes` o valor jogo da mesma métrica calculada sobre a gravação do jogo antigo."""
    guardado = {m.chave(): m.jogo for m in antes}
    for m in depois:
        m.antes = guardado.get(m.chave())
    return depois


def salvar_json(medidas, nome):
    os.makedirs(FINAL, exist_ok=True)
    with open(os.path.join(FINAL, f"{nome}.json"), "w", encoding="utf-8") as arquivo:
        json.dump([asdict(m) | {"ok": m.ok, "tolerancia": m.tolerancia} for m in medidas], arquivo, indent=1,
                  ensure_ascii=False, default=lambda valor: str(valor))
