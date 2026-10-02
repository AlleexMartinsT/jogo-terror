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
    kind: str                # 'six_panel' | 'glazed' (vidros na fileira de cima) | 'screen' (tela em cima) | 'flush'
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
    lowest_row = (BOTTOM_RAIL, LOCK_RAIL[0])
    if kind == "flush":
        return LeafSpec(kind, width, height, ())
    columns = _columns(width, 2)
    if kind == "screen":
        lower = tuple(Field(x0, lowest_row[0], x1, lowest_row[1], "panel") for x0, x1 in columns)
        upper = Field(STILE + 0.02, LOCK_RAIL[1], width - STILE - 0.02, top, "screen")
        return LeafSpec(kind, width, height, lower + (upper,))
    short_row = (top - 0.315, top)
    rows = [(lowest_row, "panel"), ((LOCK_RAIL[1], short_row[0] - MID_RAIL), "panel"),
            (short_row, "glass" if kind == "glazed" else "panel")]
    return LeafSpec(kind, width, height, tuple(Field(x0, z0, x1, z1, material)
                                               for (z0, z1), material in rows for x0, x1 in columns))


def rail_bands(spec):
    """Faixas horizontais (z0, z1) sem vão: onde a fibra da madeira corre ao longo da largura da folha."""
    bands, cursor = [], 0.0
    for z0, z1 in sorted({(f.z0, f.z1) for f in spec.fields}):
        if z0 > cursor + 1e-6:
            bands.append((cursor, z0))
        cursor = max(cursor, z1)
    if cursor < spec.height - 1e-6:
        bands.append((cursor, spec.height))
    return bands
