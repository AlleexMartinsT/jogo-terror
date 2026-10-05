"""Registro dos cenários de comparação. Um cenário diz o que comparar (qual mocap, qual roteiro no jogo, quais métricas);
`comparar.py` faz o resto (retarget, palco, quadros, vídeo, gráficos, tabela).

    python -m tools.movimento_ref.comparar --lista
    python -m tools.movimento_ref.comparar andar --vistas frente,lado,topo,primeira --saida out/movimento/andar

Quem escreve cenários:
    locomocao.py (agente 2), maos.py (agente 3), objetos.py (agente 4) e exemplo.py (aqui). Cada módulo define subclasses de
    `Cenario` (base.py) decoradas com `@registrar`; os módulos que existirem são importados sozinhos na primeira consulta.
    Um nome repetido substitui o anterior (a ordem é exemplo, locomocao, maos, objetos), de modo que "andar" do exemplo
    cede lugar a um "andar" de locomocao.py quando ele existir.
"""
import importlib

from .base import Alinhamento, Cenario, Preparado, Real  # noqa: F401

REGISTRO = {}
MODULOS = ("exemplo", "locomocao", "maos", "objetos")
_carregado = False
avisos = []


def registrar(classe):
    """Decorador: registra a subclasse de `Cenario` pelo seu atributo `nome`."""
    if not getattr(classe, "nome", None):
        raise ValueError(f"{classe.__name__} precisa de um atributo `nome`")
    REGISTRO[classe.nome] = classe
    return classe


def carregar():
    """Importa os módulos de cenários que existem. Erros de importação viram avisos (um módulo quebrado não derruba os outros)."""
    global _carregado
    if _carregado:
        return
    _carregado = True
    for modulo in MODULOS:
        try:
            importlib.import_module(f".{modulo}", __name__)
        except ModuleNotFoundError as erro:
            if erro.name != f"{__name__}.{modulo}":
                avisos.append(f"cenarios.{modulo}: {erro}")
        except Exception as erro:       # noqa: BLE001
            avisos.append(f"cenarios.{modulo}: {type(erro).__name__}: {erro}")


def obter(nome):
    """Instância do cenário `nome`."""
    carregar()
    if nome not in REGISTRO:
        raise KeyError(f"cenário {nome!r} não existe; use um de: {', '.join(sorted(REGISTRO)) or '(nenhum)'}")
    return REGISTRO[nome]()


def listar():
    """[(nome, título)] ordenado."""
    carregar()
    return sorted((nome, classe.titulo) for nome, classe in REGISTRO.items())
