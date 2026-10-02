"""Lugares livres nas faces internas das paredes, para tomadas, interruptores, grelhas e decalques.

Um `Site` é um trecho reto de uma face de parede voltada para um cômodo, já sem as pontas perto de cantos,
guarnições de porta e janela, e sem o lado da escada. Quem posiciona coisas sorteia pontos dentro dele.
"""
import math
from dataclasses import dataclass

from mathutils import Vector

from .. import conventions as C
from .. import layout
from . import moldings

CORNER_MARGIN = 0.25
DOOR_MARGIN = moldings.CASING_WIDTH + 0.14
WINDOW_MARGIN = moldings.CASING_WIDTH + 0.10


@dataclass(frozen=True)
class Site:
    piece: layout.WallPiece
    side: str                 # 'lo' | 'hi': a face voltada para room_lo ou room_hi
    room_id: str
    u0: float                 # trecho utilizável ao longo da parede
    u1: float

    @property
    def level(self):
        return self.piece.level

    @property
    def length(self):
        return self.u1 - self.u0

    @property
    def out(self):
        """Normal da face, apontando para dentro do cômodo."""
        sign = -1.0 if self.side == "lo" else 1.0
        return Vector((0.0, sign, 0.0)) if self.piece.axis == "x" else Vector((sign, 0.0, 0.0))

    @property
    def yaw_degrees(self):
        """Rotação em Z que leva o +Y local do construtor para a normal da face."""
        out = self.out
        return math.degrees(C.dir_yaw(out.x, out.y))

    def face(self):
        half = self.piece.thickness / 2
        return self.piece.pos - half if self.side == "lo" else self.piece.pos + half

    def point(self, u, z, lift=0.0):
        """Ponto de mundo na face da parede (deslocado `lift` para dentro do cômodo) a `u` ao longo dela."""
        n = self.face() + (-lift if self.side == "lo" else lift)
        return (u, n, z) if self.piece.axis == "x" else (n, u, z)

    def contains(self, u, margin=0.0):
        return self.u0 + margin <= u <= self.u1 - margin


def _opening_edges(level):
    """{(eixo, pos, u): margem} nas bordas de portas, arcos e janelas do andar."""
    edges = {}
    for op in layout.OPENINGS.values():
        if op.level != level or op.kind == "garage_door":
            continue
        margin = WINDOW_MARGIN if op.kind == "window" else DOOR_MARGIN
        edges[(op.axis, round(op.pos, 3), round(op.a, 3))] = margin
        edges[(op.axis, round(op.pos, 3), round(op.b, 3))] = margin
    return edges


def sites(level):
    """Todos os sítios utilizáveis de um andar (só peças 'full', as paredes de fora a fora)."""
    edges = _opening_edges(level)
    found = []
    for piece in layout.wall_pieces(level):
        if piece.kind != "full":
            continue
        start = piece.a + edges.get((piece.axis, round(piece.pos, 3), round(piece.a, 3)), CORNER_MARGIN)
        end = piece.b - edges.get((piece.axis, round(piece.pos, 3), round(piece.b, 3)), CORNER_MARGIN)
        for side, room_id in (("lo", piece.room_lo), ("hi", piece.room_hi)):
            if not room_id or end - start < 0.3:
                continue
            for u0, u1 in _without_stairs(piece, side, start, end):
                found.append(Site(piece, side, room_id, u0, u1))
    return found


def _without_stairs(piece, side, start, end):
    """Tira o trecho da parede oeste do hall térreo que fica atrás da escada."""
    stairs = layout.STAIRS
    if piece.level == 0 and piece.axis == "y" and abs(piece.pos - stairs.hole.x0) < 1e-6 and side == "hi":
        spans = [(start, min(end, stairs.y0 - 0.2)), (max(start, stairs.y1 + 0.2), end)]
        return [(a, b) for a, b in spans if b - a > 0.3]
    return [(start, end)]


def sites_in_room(level, room_id):
    return [site for site in sites(level) if site.room_id == room_id]


def next_to_opening(op, room_id, gap=0.12):
    """Sítio e posição `u` logo ao lado do lado da fechadura de uma porta, dentro de `room_id` (ou None)."""
    latch_u = op.b if op.hinge == "a" else op.a
    direction = 1.0 if op.hinge == "a" else -1.0       # sentido, ao longo da parede, de saída do vão
    wanted = latch_u + direction * (moldings.CASING_WIDTH + gap)
    for piece in layout.wall_pieces(op.level):
        if piece.kind != "full" or piece.axis != op.axis or abs(piece.pos - op.pos) > 1e-6:
            continue
        for side, owner in (("lo", piece.room_lo), ("hi", piece.room_hi)):
            if owner == room_id and piece.a + 0.1 <= wanted <= piece.b - 0.1:
                return Site(piece, side, room_id, piece.a, piece.b), wanted
    return None, None
