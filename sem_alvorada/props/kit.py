"""Kit de modelagem low-poly usado por todos os props.

Um `MeshBuilder` acumula vértices e faces em coordenadas locais do móvel
(origem no centro da base, frente = +Y, Z para cima) e só no fim vira um `Mesh`
do Blender. Assim as peças são montadas sem `bpy.ops`, sem contexto de UI, e
podem ser medidas (caixa delimitadora, triângulos) antes de existirem na cena.

Convenções:
- Comprimentos em metros; ângulos de `at(...)` em graus.
- Toda face nasce com a normal para fora. Formas fechadas (loft, extrusão, toro)
  conferem o volume com sinal e se viram sozinhas se saírem invertidas.
- UVs: se o chamador não informar, cada face recebe projeção "de caixa" em
  escala de mundo (`uv` = repetições por metro), então texturas não esticam.
"""
import math
from contextlib import contextmanager

from mathutils import Euler, Matrix, Vector

from . import materials

FACE_ORDER = {
    "bottom": (0, 3, 2, 1),
    "top": (4, 5, 6, 7),
    "back": (0, 1, 5, 4),      # -Y
    "front": (2, 3, 7, 6),     # +Y
    "right": (1, 2, 6, 5),     # +X
    "left": (3, 0, 4, 7),      # -X
}


def circle_points(cx, cy, z, radius, seg, phase=0.0):
    """Pontos anti-horários de um círculo horizontal."""
    return [(cx + radius * math.cos(phase + 2 * math.pi * i / seg),
             cy + radius * math.sin(phase + 2 * math.pi * i / seg), z) for i in range(seg)]


def rounded_rect(width, depth, radius, corner_points=2):
    """Contorno (x, y) anti-horário de um retângulo com cantos arredondados/chanfrados.

    `corner_points=2` gera um chanfro; valores maiores arredondam de verdade.
    """
    radius = max(0.0, min(radius, width / 2 - 1e-4, depth / 2 - 1e-4))
    if radius < 1e-4:
        hx, hy = width / 2, depth / 2
        return [(hx, -hy), (hx, hy), (-hx, hy), (-hx, -hy)]
    outline = []
    centers = [(width / 2 - radius, depth / 2 - radius), (-(width / 2 - radius), depth / 2 - radius),
               (-(width / 2 - radius), -(depth / 2 - radius)), (width / 2 - radius, -(depth / 2 - radius))]
    for quadrant, (ccx, ccy) in enumerate(centers):
        for k in range(corner_points):
            angle = math.pi / 2 * (quadrant + k / (corner_points - 1))
            outline.append((ccx + radius * math.cos(angle), ccy + radius * math.sin(angle)))
    return outline


def _newell_normal(points):
    nx = ny = nz = 0.0
    count = len(points)
    for i in range(count):
        x0, y0, z0 = points[i]
        x1, y1, z1 = points[(i + 1) % count]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def projected_uv(points, scale):
    """UV de caixa: projeta pelo eixo dominante da normal, em `scale` repetições por metro."""
    nx, ny, nz = _newell_normal(points)
    if abs(nz) >= max(abs(nx), abs(ny)):
        return [(x * scale, y * scale) for x, y, _ in points]
    length = math.hypot(nx, ny) or 1.0
    tx, ty = -ny / length, nx / length      # horizontal para a direita de quem olha de fora
    return [((x * tx + y * ty) * scale, z * scale) for x, y, z in points]


class MeshBuilder:
    """Acumula geometria com materiais por face. Veja `to_mesh` para criar o Mesh."""

    def __init__(self, name):
        self.name = name
        self.materials = []
        self._verts = []
        self._faces = []
        self._uvs = []
        self._face_slot = []
        self._face_smooth = []
        self._xf = Matrix.Identity(4)

    # ------------------------------------------------------------------
    # Infraestrutura
    # ------------------------------------------------------------------
    @contextmanager
    def at(self, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
        """Desloca/gira o sistema de coordenadas para as primitivas dentro do bloco."""
        saved = self._xf
        rotation = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_matrix().to_4x4()
        self._xf = saved @ Matrix.Translation((x, y, z)) @ rotation
        try:
            yield self
        finally:
            self._xf = saved

    def _slot(self, material_name):
        if material_name not in self.materials:
            self.materials.append(material_name)
        return self.materials.index(material_name)

    def _push(self, local_points):
        base = len(self._verts)
        self._verts.extend(tuple(self._xf @ Vector(p)) for p in local_points)
        return list(range(base, base + len(local_points)))

    def _face(self, ids, local_points, mat, smooth=False, uv=None, uv_scale=1.0):
        self._faces.append(tuple(ids))
        self._uvs.append(list(uv) if uv is not None else projected_uv(local_points, uv_scale))
        self._face_slot.append(self._slot(mat))
        self._face_smooth.append(smooth)

    def _flip_faces(self, first):
        for i in range(first, len(self._faces)):
            self._faces[i] = tuple(reversed(self._faces[i]))
            self._uvs[i] = list(reversed(self._uvs[i]))

    def _enclosed_volume(self, first):
        volume = 0.0
        for ids in self._faces[first:]:
            p0 = Vector(self._verts[ids[0]])
            for a, b in zip(ids[1:], ids[2:]):
                volume += p0.dot(Vector(self._verts[a]).cross(Vector(self._verts[b])))
        return volume / 6.0

    def _orient_outward(self, first):
        if self._enclosed_volume(first) < 0:
            self._flip_faces(first)

    # ------------------------------------------------------------------
    # Medidas
    # ------------------------------------------------------------------
    @property
    def tri_count(self):
        return sum(len(f) - 2 for f in self._faces)

    def bounds(self):
        """((x0, y0, z0), (x1, y1, z1)) de todos os vértices usados."""
        used = {i for f in self._faces for i in f}
        xs, ys, zs = zip(*(self._verts[i] for i in used))
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def translate(self, dx=0.0, dy=0.0, dz=0.0):
        self._verts = [(x + dx, y + dy, z + dz) for x, y, z in self._verts]

    def drop_to_floor(self):
        """Apoia a peça no chão depois de girá-la (cadeira caída, por exemplo)."""
        self.translate(dz=-self.bounds()[0][2])

    def include(self, other, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
        """Copia a geometria de outro builder para este, sob a transformação dada."""
        with self.at(x, y, z, rx, ry, rz):
            base = len(self._verts)
            self._verts.extend(tuple(self._xf @ Vector(p)) for p in other._verts)
            for ids, uv, slot, smooth in zip(other._faces, other._uvs, other._face_slot, other._face_smooth):
                self._faces.append(tuple(base + i for i in ids))
                self._uvs.append(list(uv))
                self._face_slot.append(self._slot(other.materials[slot]))
                self._face_smooth.append(smooth)

    # ------------------------------------------------------------------
    # Primitivas
    # ------------------------------------------------------------------
    def quad(self, p0, p1, p2, p3, mat, uv=None, uv_scale=1.0, double=False):
        ids = self._push([p0, p1, p2, p3])
        self._face(ids, [p0, p1, p2, p3], mat, uv=uv, uv_scale=uv_scale)
        if double:
            back_uv = None if uv is None else list(reversed(uv))
            self._face(list(reversed(ids)), [p3, p2, p1, p0], mat, uv=back_uv, uv_scale=uv_scale)

    def poly(self, points, mat, uv=None, uv_scale=1.0):
        """Polígono qualquer (anti-horário visto de fora)."""
        ids = self._push(points)
        self._face(ids, points, mat, uv=uv, uv_scale=uv_scale)

    def panel(self, cx, cy, cz, width, height, mat, facing="front", uv_rect=(0, 0, 1, 1), double=False):
        """Retângulo vertical (ou horizontal se facing for top/bottom) com UV explícito.

        `facing`: para onde a frente aponta (front=+Y, back=-Y, right=+X, left=-X, top=+Z).
        `width` corre para a direita de quem olha de frente; `height`, para cima
        (em top/bottom, ao longo de Y).
        """
        hw, hh = width / 2, height / 2
        if facing == "front":
            pts = [(cx + hw, cy, cz - hh), (cx - hw, cy, cz - hh), (cx - hw, cy, cz + hh), (cx + hw, cy, cz + hh)]
        elif facing == "back":
            pts = [(cx - hw, cy, cz - hh), (cx + hw, cy, cz - hh), (cx + hw, cy, cz + hh), (cx - hw, cy, cz + hh)]
        elif facing == "right":
            pts = [(cx, cy - hw, cz - hh), (cx, cy + hw, cz - hh), (cx, cy + hw, cz + hh), (cx, cy - hw, cz + hh)]
        elif facing == "left":
            pts = [(cx, cy + hw, cz - hh), (cx, cy - hw, cz - hh), (cx, cy - hw, cz + hh), (cx, cy + hw, cz + hh)]
        elif facing == "top":
            pts = [(cx - hw, cy - hh, cz), (cx + hw, cy - hh, cz), (cx + hw, cy + hh, cz), (cx - hw, cy + hh, cz)]
        elif facing == "bottom":
            pts = [(cx - hw, cy + hh, cz), (cx + hw, cy + hh, cz), (cx + hw, cy - hh, cz), (cx - hw, cy - hh, cz)]
        else:
            raise ValueError(facing)
        u0, v0, u1, v1 = uv_rect
        self.quad(*pts, mat, uv=[(u0, v0), (u1, v0), (u1, v1), (u0, v1)], double=double)

    def box(self, cx, cy, z0, width, depth, height, mat, uv=1.0, mats=None, skip=()):
        """Caixa apoiada em z0. `mats` troca o material de faces (front/back/left/right/top/bottom)."""
        x0, x1 = cx - width / 2, cx + width / 2
        y0, y1 = cy - depth / 2, cy + depth / 2
        z1 = z0 + height
        corners = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        ids = self._push(corners)
        for face, order in FACE_ORDER.items():
            if face in skip:
                continue
            face_mat = (mats or {}).get(face, mat)
            self._face([ids[i] for i in order], [corners[i] for i in order], face_mat, uv_scale=uv)

    def frustum(self, cx, cy, z0, w0, d0, w1, d1, height, mat, ox=0.0, oy=0.0, uv=1.0, mats=None, skip=()):
        """Tronco retangular: base w0 x d0 em z0, topo w1 x d1 deslocado (ox, oy)."""
        z1 = z0 + height
        tx, ty = cx + ox, cy + oy
        corners = [(cx - w0 / 2, cy - d0 / 2, z0), (cx + w0 / 2, cy - d0 / 2, z0),
                   (cx + w0 / 2, cy + d0 / 2, z0), (cx - w0 / 2, cy + d0 / 2, z0),
                   (tx - w1 / 2, ty - d1 / 2, z1), (tx + w1 / 2, ty - d1 / 2, z1),
                   (tx + w1 / 2, ty + d1 / 2, z1), (tx - w1 / 2, ty + d1 / 2, z1)]
        ids = self._push(corners)
        for face, order in FACE_ORDER.items():
            if face in skip:
                continue
            face_mat = (mats or {}).get(face, mat)
            self._face([ids[i] for i in order], [corners[i] for i in order], face_mat, uv_scale=uv)

    def loft(self, rings, mat, cap_start=True, cap_end=True, smooth=False, uv=1.0, orient=True, uv_grid=False):
        """Une anéis de pontos (mesmo número de pontos, exceto um anel de 1 ponto = ápice).

        Os anéis vão na ordem em que a peça cresce. Se a forma for fechada (tampas ou ápices nas
        duas pontas) o volume é orientado para fora; formas abertas confiam na ordem dos anéis
        (anti-horário visto de +Z, ou o sentido que o chamador escolher).
        """
        first = len(self._faces)
        ring_ids = [self._push(r) for r in rings]
        path = [0.0]
        for a, b in zip(rings, rings[1:]):
            path.append(path[-1] + (Vector(_centroid(b)) - Vector(_centroid(a))).length)
        for level in range(len(rings) - 1):
            lo, hi = rings[level], rings[level + 1]
            lo_ids, hi_ids = ring_ids[level], ring_ids[level + 1]
            arc = _arc_lengths(lo if len(lo) > 1 else hi)
            v0, v1 = path[level] * uv, path[level + 1] * uv
            count = len(lo) if len(lo) > 1 else len(hi)
            if uv_grid:
                v0, v1 = level / (len(rings) - 1), (level + 1) / (len(rings) - 1)
            for j in range(count):
                k = (j + 1) % count
                u0, u1 = (j / count, (j + 1) / count) if uv_grid else (arc[j] * uv, arc[j + 1] * uv)
                if len(hi) == 1:
                    tri = [lo_ids[j], lo_ids[k], hi_ids[0]]
                    pts = [lo[j], lo[k], hi[0]]
                    self._face(tri, pts, mat, smooth, [(u0, v0), (u1, v0), ((u0 + u1) / 2, v1)])
                elif len(lo) == 1:
                    tri = [hi_ids[k], hi_ids[j], lo_ids[0]]
                    pts = [hi[k], hi[j], lo[0]]
                    self._face(tri, pts, mat, smooth, [(u1, v1), (u0, v1), ((u0 + u1) / 2, v0)])
                else:
                    quad = [lo_ids[j], lo_ids[k], hi_ids[k], hi_ids[j]]
                    pts = [lo[j], lo[k], hi[k], hi[j]]
                    self._face(quad, pts, mat, smooth, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
        if cap_start and len(rings[0]) > 2:
            self._face(list(reversed(ring_ids[0])), list(reversed(rings[0])), mat, uv_scale=uv)
        if cap_end and len(rings[-1]) > 2:
            self._face(ring_ids[-1], rings[-1], mat, uv_scale=uv)
        closed = (cap_start or len(rings[0]) == 1) and (cap_end or len(rings[-1]) == 1)
        if orient and closed:
            self._orient_outward(first)

    def cylinder(self, cx, cy, z0, radius, height, mat, seg=8, r_top=None, smooth=False,
                 caps=(True, True), uv=1.0, phase=0.0):
        """Cilindro/tronco vertical; `r_top=0` vira cone."""
        top_radius = radius if r_top is None else r_top
        bottom = circle_points(cx, cy, z0, radius, seg, phase)
        top = circle_points(cx, cy, z0 + height, top_radius, seg, phase) if top_radius > 1e-6 \
            else [(cx, cy, z0 + height)]
        self.loft([bottom, top], mat, caps[0], caps[1] and top_radius > 1e-6, smooth, uv)

    def lathe(self, profile, cx, cy, z0, mat, seg=12, smooth=True, cap_bottom=True, cap_top=True, uv=1.0):
        """Revolve um perfil [(raio, z), ...] de baixo para cima; raio 0 vira ápice."""
        rings = [circle_points(cx, cy, z0 + z, r, seg) if r > 1e-6 else [(cx, cy, z0 + z)] for r, z in profile]
        self.loft(rings, mat, cap_bottom, cap_top, smooth, uv)

    def sphere(self, cx, cy, cz, radius, mat, seg=10, rings=6, smooth=True, squash=1.0):
        """Esfera com UV equiretangular (globo, olhos, cabeças de pelúcia); `squash` achata em Z."""
        rows = [[(cx, cy, cz - radius * squash)]]
        for row in range(1, rings):
            phi = math.pi * row / rings
            rows.append(circle_points(cx, cy, cz - radius * squash * math.cos(phi), radius * math.sin(phi), seg))
        rows.append([(cx, cy, cz + radius * squash)])
        self.loft(rows, mat, False, False, smooth, uv_grid=True)

    def soft_box(self, cx, cy, z0, width, depth, height, mat, radius=0.05, edge=0.02,
                 corner_points=2, uv=1.0, smooth=False):
        """Caixa com cantos verticais arredondados e arestas chanfradas (almofadas, colchões, eletrodomésticos)."""
        edge = min(edge, height / 2 - 1e-4)
        levels = [(0.0, edge), (edge, 0.0), (height - edge, 0.0), (height, edge)]
        rings = []
        for dz, inset in levels:
            outline = rounded_rect(width - 2 * inset, depth - 2 * inset, max(radius - inset, 0.002), corner_points)
            rings.append([(cx + x, cy + y, z0 + dz) for x, y in outline])
        self.loft(rings, mat, True, True, smooth, uv)

    def extrude(self, profile, plane, start, end, mat, uv=1.0):
        """Extruda um perfil 2D. `plane`: 'xy' (sobe em Z), 'yz' (corre em X) ou 'xz' (corre em Y)."""
        mapping = {"xy": lambda u, v, t: (u, v, t), "yz": lambda u, v, t: (t, u, v),
                   "xz": lambda u, v, t: (u, t, v)}[plane]
        self.loft([[mapping(u, v, start) for u, v in profile], [mapping(u, v, end) for u, v in profile]],
                  mat, True, True, False, uv)

    def wedge(self, cx, cy, z0, width, depth, height, mat, high="back", uv=1.0):
        """Rampa: alta no lado `high` (back = -Y, front = +Y)."""
        y_high = -depth / 2 if high == "back" else depth / 2
        y_low = -y_high
        profile = [(cy + y_low, z0), (cy + y_high, z0), (cy + y_high, z0 + height)]
        self.extrude(profile, "yz", cx - width / 2, cx + width / 2, mat, uv)

    def tube(self, p0, p1, radius, mat, seg=6, r_end=None, caps=(True, True), smooth=False, phase=0.0):
        """Cilindro entre dois pontos quaisquer (pernas inclinadas, canos, guidão)."""
        direction = Vector(p1) - Vector(p0)
        length = direction.length
        if length < 1e-6:
            return
        rotation = Vector((0, 0, 1)).rotation_difference(direction).to_matrix().to_4x4()
        saved = self._xf
        self._xf = saved @ Matrix.Translation(p0) @ rotation
        try:
            self.cylinder(0, 0, 0, radius, length, mat, seg, r_end, smooth, caps, phase=phase)
        finally:
            self._xf = saved

    def bar(self, p0, p1, thickness, mat, caps=(True, True)):
        """Barra de seção quadrada entre dois pontos."""
        self.tube(p0, p1, thickness / math.sqrt(2), mat, seg=4, caps=caps, phase=math.pi / 4)

    def torus(self, cx, cy, cz, major, minor, mat, seg=14, seg_minor=5, rx=0.0, ry=0.0, rz=0.0):
        """Anel (volante, aro de roda). Nasce no plano XY; gire com rx/ry/rz."""
        with self.at(cx, cy, cz, rx, ry, rz):
            first = len(self._faces)
            rings = []
            for i in range(seg):
                angle = 2 * math.pi * i / seg
                ca, sa = math.cos(angle), math.sin(angle)
                rings.append([((major + minor * math.cos(2 * math.pi * j / seg_minor)) * ca,
                               (major + minor * math.cos(2 * math.pi * j / seg_minor)) * sa,
                               minor * math.sin(2 * math.pi * j / seg_minor)) for j in range(seg_minor)])
            ids = [self._push(r) for r in rings]
            for i in range(seg):
                nxt = (i + 1) % seg
                for j in range(seg_minor):
                    k = (j + 1) % seg_minor
                    quad = [ids[i][j], ids[nxt][j], ids[nxt][k], ids[i][k]]
                    pts = [rings[i][j], rings[nxt][j], rings[nxt][k], rings[i][k]]
                    self._face(quad, pts, mat, smooth=True)
            self._orient_outward(first)

    def surface(self, fn, nu, nv, mat, uv_size=(1.0, 1.0), uv=1.0, flip=False, double=False, smooth=False):
        """Malha paramétrica aberta (pano, cortina): `fn(u, v)` com u, v em [0, 1] devolve (x, y, z)."""
        grid = [[fn(i / nu, j / nv) for j in range(nv + 1)] for i in range(nu + 1)]
        ids = [self._push(column) for column in grid]
        su, sv = uv_size[0] * uv, uv_size[1] * uv
        for i in range(nu):
            for j in range(nv):
                quad = [ids[i][j], ids[i + 1][j], ids[i + 1][j + 1], ids[i][j + 1]]
                pts = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
                coords = [(i / nu * su, j / nv * sv), ((i + 1) / nu * su, j / nv * sv),
                          ((i + 1) / nu * su, (j + 1) / nv * sv), (i / nu * su, (j + 1) / nv * sv)]
                if flip:
                    quad, pts, coords = quad[::-1], pts[::-1], coords[::-1]
                self._face(quad, pts, mat, smooth, coords)
                if double:
                    self._face(quad[::-1], pts[::-1], mat, smooth, coords[::-1])

    # ------------------------------------------------------------------
    # Saída
    # ------------------------------------------------------------------
    def to_mesh(self, name=None):
        """Cria o `bpy.types.Mesh` (só com os vértices usados) e atribui os materiais."""
        import bpy
        used = sorted({i for f in self._faces for i in f})
        remap = {old: new for new, old in enumerate(used)}
        mesh = bpy.data.meshes.new(name or self.name)
        mesh.from_pydata([self._verts[i] for i in used], [], [tuple(remap[i] for i in f) for f in self._faces])
        for slot_name in self.materials:
            mesh.materials.append(materials.get(slot_name))
        mesh.polygons.foreach_set("material_index", self._face_slot)
        mesh.polygons.foreach_set("use_smooth", self._face_smooth)
        layer = mesh.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", [c for face_uv in self._uvs for uv_pair in face_uv for c in uv_pair])
        mesh.update()
        return mesh


def _centroid(points):
    count = len(points)
    return (sum(p[0] for p in points) / count, sum(p[1] for p in points) / count,
            sum(p[2] for p in points) / count)


def _arc_lengths(ring):
    """Comprimento acumulado ao longo do contorno fechado (para o U das laterais)."""
    lengths = [0.0]
    for i in range(len(ring)):
        a, b = Vector(ring[i]), Vector(ring[(i + 1) % len(ring)])
        lengths.append(lengths[-1] + (b - a).length)
    return lengths
