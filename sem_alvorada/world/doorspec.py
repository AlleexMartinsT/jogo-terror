"""Desenho das folhas de porta: onde ficam longarinas, travessas, almofadas, vidros e telas.

A geometria (`doors`) e a textura (`tex_doors`) leem as MESMAS medidas, em metros no espaço da folha
(origem na dobradiça, X ao longo da largura, Z para cima). Assim a tinta racha exatamente nas juntas e a
sujeira se acumula nos cantos das almofadas, em vez de a textura "adivinhar" onde elas estão.

Medidas de uma porta residencial americana: folha de 36 x 80 polegadas (0,91 x 2,03 m), longarinas de
10 cm, travessa de fechadura a 0,95 m do piso (altura da maçaneta).
"""
from dataclasses import dataclass

LEAF_THICKNESS = 0.04
STILE = 0.10                 # largura das longarinas laterais e do montante central
BOTTOM_RAIL = 0.19
LOCK_RAIL = (0.85, 1.05)     # a maçaneta fica no meio desta faixa
MID_RAIL = 0.11
TOP_RAIL = 0.11
KNOB_HEIGHT = 0.95
KNOB_INSET = 0.07            # distância do centro da maçaneta à borda livre


@dataclass(frozen=True)
class Field:
    """Um vão da folha: retângulo (x0, z0, x1, z1) e o que o preenche."""
    x0: float
    z0: float
    x1: float
    z1: float
    kind: str                # 'panel' (almofada), 'glass', 'screen'

    @property
    def rect(self):
        return (self.x0, self.z0, self.x1, self.z1)


@dataclass(frozen=True)
class LeafSpec:
    kind: str                # 'six_panel' | 'glazed' | 'screen' | 'flush'
    width: float
    height: float
    fields: tuple


def _columns(width, count):
    """Faixas (x0, x1) entre longarinas e montantes."""
    gap = (width - 2 * STILE - (count - 1) * STILE) / count
    return [(STILE + i * (gap + STILE), STILE + i * (gap + STILE) + gap) for i in range(count)]


def leaf_spec(kind, width, height):
    """Disposição dos vãos de cada tipo de folha."""
    top = height - TOP_RAIL
    rows_below = (BOTTOM_RAIL, LOCK_RAIL[0])
    if kind == "flush":
        return LeafSpec(kind, width, height, ())
    if kind == "six_panel":
        rows = [rows_below, (LOCK_RAIL[1], height - TOP_RAIL - 0.315 - MID_RAIL), (height - TOP_RAIL - 0.315, top)]
        columns = _columns(width, 2)
        return LeafSpec(kind, width, height, tuple(Field(x0, z0, x1, z1, "panel")
                                                   for z0, z1 in rows for x0, x1 in columns))
    upper_kind = "glass" if kind == "glazed" else "screen"
    lower = tuple(Field(x0, rows_below[0], x1, rows_below[1], "panel") for x0, x1 in _columns(width, 2))
    upper = (Field(STILE + 0.02, LOCK_RAIL[1], width - STILE - 0.02, top, upper_kind),)
    return LeafSpec(kind, width, height, lower + upper)


def rail_rects(spec):
    """Retângulos de travessas e longarinas (para a textura reconhecer fibra horizontal e vertical)."""
    if not spec.fields:
        return [(0.0, 0.0, spec.width, spec.height)]
    return [(0.0, 0.0, STILE, spec.height), (spec.width - STILE, 0.0, spec.width, spec.height),
            (0.0, 0.0, spec.width, BOTTOM_RAIL), (0.0, LOCK_RAIL[0], spec.width, LOCK_RAIL[1]),
            (0.0, spec.height - TOP_RAIL, spec.width, spec.height)]
