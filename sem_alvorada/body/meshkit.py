"""Ferramentas de malha para o corpo: anéis de seção, varreduras (lofts) e pesos por vértice.

Só numpy. Cada peça do corpo (manga, perna da calça, dedo) é uma sequência de anéis ao longo de um
caminho; cada vértice nasce com seus pesos de osso e as duas UVs (atlas e repetição em escala de mundo).
A mesma peça desenhada para a mão direita vira a esquerda por uma base com determinante negativo:
`Mesh.transform` inverte o sentido das faces quando isso acontece.
"""
import math

import numpy as np


# --------------------------------------------------------------------------
# Curvas e funções de forma
# --------------------------------------------------------------------------
def smoothstep(x, low=0.0, high=1.0):
    t = np.clip((np.asarray(x, dtype=float) - low) / (high - low), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def interp(xs, ys):
    """Interpolação cúbica suave (Catmull-Rom com tangentes limitadas) por pontos (xs crescente)."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    slopes = np.zeros_like(ys)
    if len(xs) > 2:
        slopes[1:-1] = (ys[2:] - ys[:-2]) / (xs[2:] - xs[:-2])
        deltas = (ys[1:] - ys[:-1]) / (xs[1:] - xs[:-1])
        for i in range(1, len(xs) - 1):          # sem sobressalto: a tangente não passa do dobro dos vizinhos
            lim = 2.0 * min(abs(deltas[i - 1]), abs(deltas[i]))
            if deltas[i - 1] * deltas[i] <= 0:
                slopes[i] = 0.0
            else:
                slopes[i] = math.copysign(min(abs(slopes[i]), lim), slopes[i])
        slopes[0], slopes[-1] = deltas[0], deltas[-1]
    elif len(xs) == 2:
        slopes[:] = (ys[1] - ys[0]) / (xs[1] - xs[0])

    def f(x):
        x = np.asarray(x, dtype=float)
        index = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
        x0, x1 = xs[index], xs[index + 1]
        h = x1 - x0
        t = np.clip((x - x0) / h, 0.0, 1.0)
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1
        h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2
        h11 = t ** 3 - t ** 2
        return h00 * ys[index] + h10 * h * slopes[index] + h01 * ys[index + 1] + h11 * h * slopes[index + 1]
    return f


def polyline_curve(points, samples=None):
    """Caminho suave por `points` (N,3): devolve f(t) -> (posição, tangente unitária) para t em [0,1] por comprimento."""
    pts = np.asarray(points, dtype=float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    param = cum / total
    fx = [interp(param, pts[:, k]) for k in range(3)]

    def f(t):
        t = np.asarray(t, dtype=float)
        pos = np.stack([fx[k](t) for k in range(3)], axis=-1)
        h = 1e-3
        ahead = np.stack([fx[k](np.clip(t + h, 0, 1)) for k in range(3)], axis=-1)
        behind = np.stack([fx[k](np.clip(t - h, 0, 1)) for k in range(3)], axis=-1)
        tan = ahead - behind
        tan /= np.maximum(np.linalg.norm(tan, axis=-1, keepdims=True), 1e-9)
        return pos, tan
    f.length = total
    return f


def perpendicular_frame(tangent, hint):
    """Dois eixos unitários perpendiculares à tangente: (a, b), com `a` o mais próximo de `hint`."""
    tangent = np.asarray(tangent, dtype=float)
    hint = np.asarray(hint, dtype=float)
    a = hint - tangent * np.dot(hint, tangent)
    norm = np.linalg.norm(a)
    if norm < 1e-6:
        alt = np.array([0.0, 1.0, 0.0]) if abs(tangent[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
        a = alt - tangent * np.dot(alt, tangent)
        norm = np.linalg.norm(a)
    a /= norm
    b = np.cross(tangent, a)
    return a, b


# --------------------------------------------------------------------------
# Anéis
# --------------------------------------------------------------------------
class Ring:
    """Seção transversal: centro, dois eixos, semi-eixos, expoente de superelipse e ajustes por vértice."""
    __slots__ = ("center", "ax", "ay", "rx", "ry", "n", "radial", "offset", "weights", "shift")

    def __init__(self, center, ax, ay, rx, ry, n=2.0, radial=None, offset=None, weights=None, shift=(0.0, 0.0)):
        self.center = np.asarray(center, dtype=float)
        self.ax, self.ay = np.asarray(ax, dtype=float), np.asarray(ay, dtype=float)
        self.rx, self.ry, self.n = rx, ry, n
        self.radial = radial          # função (theta) -> fator de raio (array), ou array (sides,)
        self.offset = offset          # função (theta) -> (sides,3) deslocamentos absolutos, ou array
        self.weights = weights        # dict osso->peso, ou função (theta) -> lista de dicts
        self.shift = shift            # deslocamento do centro da seção nos eixos (ax, ay)


def section_points(ring, thetas):
    c, s = np.cos(thetas), np.sin(thetas)
    e = 2.0 / ring.n
    x = ring.rx * np.sign(c) * np.abs(c) ** e
    y = ring.ry * np.sign(s) * np.abs(s) ** e
    if ring.radial is not None:
        factor = ring.radial(thetas) if callable(ring.radial) else ring.radial
        x, y = x * factor, y * factor
    x = x + ring.shift[0]
    y = y + ring.shift[1]
    pts = ring.center[None, :] + x[:, None] * ring.ax[None, :] + y[:, None] * ring.ay[None, :]
    if ring.offset is not None:
        pts = pts + (ring.offset(thetas) if callable(ring.offset) else ring.offset)
    return pts


# --------------------------------------------------------------------------
# Malha
# --------------------------------------------------------------------------
class Mesh:
    """Malha mutável: vértices, faces com UV por canto, material por face e pesos por vértice."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.uv0 = []
        self.uv1 = []
        self.material = []
        self.weights = []
        self.sharp = []              # por face: True se a face deve ficar sem suavização
        self.region = []             # por vértice: rótulo da peça (depuração e pesos)

    # -- tamanho ---------------------------------------------------------
    def triangles(self):
        return sum(len(f) - 2 for f in self.faces)

    # -- construção ------------------------------------------------------
    def add_vertex(self, point, weights, region=""):
        self.verts.append((float(point[0]), float(point[1]), float(point[2])))
        self.weights.append(weights)
        self.region.append(region)
        return len(self.verts) - 1

    def add_face(self, ids, uv0, uv1, material, sharp=False):
        self.faces.append(tuple(ids))
        self.uv0.append(tuple(uv0))
        self.uv1.append(tuple(uv1))
        self.material.append(material)
        self.sharp.append(sharp)

    def merge(self, other):
        base = len(self.verts)
        self.verts.extend(other.verts)
        self.weights.extend(other.weights)
        self.region.extend(other.region)
        self.faces.extend(tuple(base + i for i in f) for f in other.faces)
        self.uv0.extend(other.uv0)
        self.uv1.extend(other.uv1)
        self.material.extend(other.material)
        self.sharp.extend(other.sharp)
        return self

    def transform(self, matrix, translation=(0.0, 0.0, 0.0), rename=None):
        """Aplica x' = M x + t a todos os vértices. Inverte as faces se o determinante for negativo."""
        m = np.asarray(matrix, dtype=float)
        pts = np.asarray(self.verts, dtype=float) @ m.T + np.asarray(translation, dtype=float)
        self.verts = [tuple(p) for p in pts]
        if np.linalg.det(m) < 0:
            self.faces = [tuple(reversed(f)) for f in self.faces]
            self.uv0 = [tuple(reversed(f)) for f in self.uv0]
            self.uv1 = [tuple(reversed(f)) for f in self.uv1]
        if rename is not None:
            self.weights = [{rename(k): v for k, v in w.items()} for w in self.weights]
        return self

    def shift_uv0(self, du, dv, materials=None):
        """Desloca o atlas das faces (opcionalmente só as de certos materiais): a mão esquerda usa outra metade."""
        for i, face in enumerate(self.uv0):
            if materials is None or self.material[i] in materials:
                self.uv0[i] = tuple((u + du, v + dv) for u, v in face)
        return self

    def copy(self):
        clone = Mesh()
        clone.merge(self)
        return clone

    def array(self):
        return np.asarray(self.verts, dtype=float)

    def set_array(self, pts):
        self.verts = [tuple(p) for p in pts]

    # -- varredura -------------------------------------------------------
    def sweep(self, rings, sides, material, *, closed_start=False, closed_end=False, phase=0.0, region="",
              uv0_rect=(0.0, 0.0, 1.0, 1.0), uv_tile=0.1, v_scale=None, start_end_material=None,
              sharp=False, seam_angle=None):
        """Liga os anéis em sequência com quadriláteros (e fecha as pontas com leque se pedido).

        `uv0_rect`: retângulo do atlas (u0, v0, u1, v1); u dá a volta, v corre ao longo. `uv1` é em escala de
        mundo: metros do arco e do caminho divididos por `uv_tile`. Devolve a lista de índices por anel.
        """
        thetas = phase + 2.0 * math.pi * np.arange(sides) / sides
        rows, ring_pts = [], []
        for ring in rings:
            pts = section_points(ring, thetas)
            ring_pts.append(pts)
            if callable(ring.weights):
                weights = ring.weights(thetas)
            else:
                weights = [ring.weights] * sides
            rows.append([self.add_vertex(pts[j], weights[j], region) for j in range(sides)])
        # comprimento do caminho e do arco para as UVs
        centers = np.array([r.center + 0.0 for r in rings])
        path = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(centers, axis=0), axis=1))])
        u0, v0, u1, v1 = uv0_rect
        total = path[-1] if path[-1] > 1e-9 else 1.0
        arcs = []
        for pts in ring_pts:
            edge = np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1)
            arcs.append(np.concatenate([[0.0], np.cumsum(edge)]))
        for r in range(len(rings) - 1):
            for j in range(sides):
                k = (j + 1) % sides
                ids = (rows[r][j], rows[r][k], rows[r + 1][k], rows[r + 1][j])
                ua, ub = u0 + (u1 - u0) * j / sides, u0 + (u1 - u0) * (j + 1) / sides
                va, vb = v0 + (v1 - v0) * path[r] / total, v0 + (v1 - v0) * path[r + 1] / total
                uv0 = ((ua, va), (ub, va), (ub, vb), (ua, vb))
                uv1 = ((arcs[r][j] / uv_tile, path[r] / uv_tile), (arcs[r][j + 1] / uv_tile, path[r] / uv_tile),
                       (arcs[r + 1][j + 1] / uv_tile, path[r + 1] / uv_tile), (arcs[r + 1][j] / uv_tile, path[r + 1] / uv_tile))
                self.add_face(ids, uv0, uv1, material, sharp)
        if closed_start:
            self._cap(rows[0], rings[0], thetas, material if start_end_material is None else start_end_material,
                      reverse=True, region=region, uv0_rect=uv0_rect)
        if closed_end:
            self._cap(rows[-1], rings[-1], thetas, material if start_end_material is None else start_end_material,
                      reverse=False, region=region, uv0_rect=uv0_rect)
        return rows

    def _cap(self, row, ring, thetas, material, reverse, region, uv0_rect):
        weights = ring.weights(thetas)[0] if callable(ring.weights) else ring.weights
        center = self.add_vertex(ring.center + ring.shift[0] * ring.ax + ring.shift[1] * ring.ay, weights, region)
        u0, v0, u1, v1 = uv0_rect
        mid = ((u0 + u1) / 2, (v0 + v1) / 2)
        sides = len(row)
        for j in range(sides):
            k = (j + 1) % sides
            ids = (center, row[k], row[j]) if reverse else (center, row[j], row[k])
            uv = (mid, mid, mid)
            self.add_face(ids, uv, uv, material)

    def grid(self, points, material, weights, *, region="", uv0_rect=(0, 0, 1, 1), uv_tile=0.1, flip=False, sharp=False):
        """Malha de quadriláteros por uma grade (R, C, 3) de pontos (peças abertas: unhas, cintos, línguas)."""
        pts = np.asarray(points, dtype=float)
        rows_n, cols_n = pts.shape[:2]
        ids = [[self.add_vertex(pts[r, c], weights(r, c) if callable(weights) else weights, region)
                for c in range(cols_n)] for r in range(rows_n)]
        u0, v0, u1, v1 = uv0_rect
        for r in range(rows_n - 1):
            for c in range(cols_n - 1):
                quad = (ids[r][c], ids[r][c + 1], ids[r + 1][c + 1], ids[r + 1][c])
                ua, ub = u0 + (u1 - u0) * c / (cols_n - 1), u0 + (u1 - u0) * (c + 1) / (cols_n - 1)
                va, vb = v0 + (v1 - v0) * r / (rows_n - 1), v0 + (v1 - v0) * (r + 1) / (rows_n - 1)
                uv0 = ((ua, va), (ub, va), (ub, vb), (ua, vb))
                uv1 = tuple((np.linalg.norm(pts[r2, c2] - pts[0, 0]) / uv_tile, 0.0) for r2, c2 in
                            ((r, c), (r, c + 1), (r + 1, c + 1), (r + 1, c)))
                if flip:
                    quad, uv0, uv1 = tuple(reversed(quad)), tuple(reversed(uv0)), tuple(reversed(uv1))
                self.add_face(quad, uv0, uv1, material, sharp)
        return ids


# --------------------------------------------------------------------------
# Pesos
# --------------------------------------------------------------------------
def ramp(value, low, high):
    return float(smoothstep(value, low, high))


def blend_two(a, b, t):
    """{a: 1-t, b: t} sem pesos zerados."""
    t = min(max(t, 0.0), 1.0)
    out = {}
    if t < 0.999:
        out[a] = 1.0 - t
    if t > 0.001:
        out[b] = t
    return out


def blend_chain(bones, centers, value, width):
    """Pesos para uma cadeia de ossos. `centers[i]` é a posição (em `value`) da junta entre `bones[i]` e `bones[i+1]`;
    `width` é a meia-largura da zona de mistura em volta de cada junta (número ou lista, uma por junta)."""
    widths = width if isinstance(width, (list, tuple)) else [width] * len(centers)
    beyond = [1.0] + [ramp(value, c - w, c + w) for c, w in zip(centers, widths)] + [0.0]
    weights = {}
    for i, bone in enumerate(bones):
        w = beyond[i] - beyond[i + 1]
        if w > 1e-3:
            weights[bone] = w
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


def normalize(weights):
    total = sum(weights.values())
    if total <= 0:
        return weights
    return {k: v / total for k, v in weights.items() if v / total > 1e-3}
