"""Geometria derivada das paredes da fachada, compartilhada pela casca e pelos rodapés."""
from collections import defaultdict

from .. import layout


def exterior_corners(level):
    """Cantos convexos da fachada: {(x, y): (dx, dy, topo)}, (dx, dy) aponta para dentro."""
    ends = defaultdict(lambda: {"x": set(), "y": set(), "top": 0.0})
    for piece in layout.wall_pieces(level):
        if not piece.exterior:
            continue
        for value, direction in ((piece.a, 1), (piece.b, -1)):
            point = (value, piece.pos) if piece.axis == "x" else (piece.pos, value)
            record = ends[(round(point[0], 3), round(point[1], 3))]
            record[piece.axis].add(direction)
            record["top"] = max(record["top"], piece.z1)
    corners = {}
    for (x, y), record in ends.items():
        if len(record["x"]) != 1 or len(record["y"]) != 1:
            continue
        dx, dy = next(iter(record["x"])), next(iter(record["y"]))
        outside = layout.room_at(x - dx * 0.5, y - dy * 0.5, layout.LEVEL_Z[level] + 0.1)
        if outside is None:
            corners[(x, y)] = (dx, dy, record["top"])
    return corners
