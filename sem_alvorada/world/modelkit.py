"""Construtor de sólidos acabados: portas, janelas, escada, luminárias e molduras.

O `MeshBuilder` de `meshkit` guarda polígonos soltos (cada face com vértices próprios), ótimo para
paredes e telhados, mas o modificador Bevel só arredonda arestas entre faces que compartilham vértices.
Aqui cada primitiva (caixa, torneado, varredura) nasce como uma malha conexa, e ao virar objeto passa por
`craft.finish_mesh`: chanfro nas quinas, normais por ângulo, tudo aplicado na malha final.

Este módulo não importa nada de `props`: a etapa `world` roda antes dela e não pode depender do que
outros estão editando.

Convenções:
- comprimentos em metros, ângulos de `at(...)` em graus;
- toda face nasce com a normal para fora (formas fechadas conferem o volume com sinal);
- sem UV por padrão: os materiais projetam a textura em caixa nas coordenadas do OBJETO. Quem precisa de
  controle (tábuas do piso) passa `uv=` por polígono.
"""
import math
from contextlib import contextmanager

import bpy
from mathutils import Euler, Matrix, Vector

from .. import craft
from . import materials

FACES = ("-x", "+x", "-y", "+y", "-z", "+z")
_BOX_RINGS = {
    "-x": (0, 4, 7, 3), "+x": (1, 2, 6, 5), "-y": (0, 1, 5, 4),
    "+y": (3, 7, 6, 2), "-z": (0, 3, 2, 1), "+z": (4, 5, 6, 7),
}

# Receita para peças cujo contorno já é desenhado no perfil (molduras, folhas de porta): não chanfra,
# só deixa lisas as faces suaves e duras as arestas vivas.
PROFILED = craft.Finish(bevel=0.0, smooth_angle=38.0)
# Para peças pequenas e finas (caixilhos, travessas): chanfro de um milímetro, um segmento.
FINE = craft.Finish(bevel=0.0012, bevel_segments=1, bevel_angle=30.0, smooth_angle=40.0)


def detail(ctx, segments):
    """Número de lados de uma peça torneada conforme `ctx.quality` ('low' usa 60%, 'high' 130%)."""
    factor = {"low": 0.6, "medium": 1.0, "high": 1.3}.get(ctx.quality, 1.0)
    return max(5, round(segments * factor))


def _per_segment(vectors, count):
    """Aceita um vetor (repetido) ou uma lista com um vetor por segmento."""
    if len(vectors) == 3 and all(isinstance(c, (int, float)) for c in vectors):
        return [Vector(vectors)] * count
    return [Vector(v) for v in vectors]


def _mitre(vectors, index, segments):
    """Vetor de deslocamento e fator de esticamento do anel `index` entre os segmentos vizinhos."""
    if index == 0:
        return vectors[0], 1.0
    if index == segments:
        return vectors[-1], 1.0
    before, after = vectors[index - 1], vectors[index]
    return before + after, 1.0 / max(1e-6, 1.0 + before.dot(after))


def circle(radius, segments, phase=0.0):
    """Pontos (x, y) anti-horários de um círculo centrado na origem."""
    return [(radius * math.cos(phase + 2 * math.pi * i / segments),
             radius * math.sin(phase + 2 * math.pi * i / segments)) for i in range(segments)]


class ModelBuilder:
    """Acumula sólidos com vértices compartilhados e os entrega como UM objeto acabado."""

    def __init__(self, name, finish=craft.STANDARD):
        self.name = name
        self.finish = finish
        self.material_names = []
        self._points = []
        self._polygons = []
        self._slots = []
        self._uvs = []
        self._transform = Matrix.Identity(4)

    # ------------------------------------------------------------------
    # Infraestrutura
    # ------------------------------------------------------------------
    @contextmanager
    def at(self, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
        """Desloca e gira (graus) o sistema de coordenadas das primitivas dentro do bloco."""
        saved = self._transform
        rotation = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_matrix().to_4x4()
        self._transform = saved @ Matrix.Translation((x, y, z)) @ rotation
        try:
            yield self
        finally:
            self._transform = saved

    def slot_of(self, material_name):
        if material_name not in self.material_names:
            self.material_names.append(material_name)
        return self.material_names.index(material_name)

    def _push(self, local_points):
        start = len(self._points)
        self._points.extend(tuple(self._transform @ Vector(p)) for p in local_points)
        return list(range(start, start + len(local_points)))

    def _add_face(self, ids, material, uv=None):
        self._polygons.append(tuple(ids))
        self._slots.append(self.slot_of(material))
        self._uvs.append(uv)

    def _volume_from(self, first):
        """Volume com sinal das faces a partir de `first`: negativo = normais para dentro."""
        total = 0.0
        for ids in self._polygons[first:]:
            origin = Vector(self._points[ids[0]])
            for a, b in zip(ids[1:], ids[2:]):
                total += origin.dot(Vector(self._points[a]).cross(Vector(self._points[b])))
        return total / 6.0

    def _orient_outward(self, first):
        if self._volume_from(first) < 0:
            for index in range(first, len(self._polygons)):
                self._polygons[index] = tuple(reversed(self._polygons[index]))
                if self._uvs[index] is not None:
                    self._uvs[index] = list(reversed(self._uvs[index]))

    @property
    def triangle_count(self):
        return sum(len(p) - 2 for p in self._polygons)

    # ------------------------------------------------------------------
    # Primitivas
    # ------------------------------------------------------------------
    def poly(self, points, material, uv=None):
        """Polígono solto, anti-horário visto de fora (decalques, vidros, painéis finos)."""
        self._add_face(self._push(points), material, uv)

    def quad(self, a, b, c, d, material, uv=None):
        self.poly((a, b, c, d), material, uv)

    def facing(self, points, toward, material, uv=None):
        """Polígono solto voltado para `toward`: se a normal calculada aponta para o outro lado, inverte a ordem."""
        a, b, c = (self._transform @ Vector(p) for p in points[:3])
        if (b - a).cross(c - a).dot(self._transform.to_3x3() @ Vector(toward)) < 0:
            points = list(points)[::-1]
            uv = list(uv)[::-1] if uv is not None else None
        self.poly(points, material, uv)

    def box(self, x0, y0, z0, x1, y1, z1, material, skip=(), face_materials=None):
        """Caixa alinhada ao sistema atual. `skip` omite faces (chaves de FACES) escondidas."""
        corners = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        ids = self._push(corners)
        overrides = face_materials or {}
        for face in FACES:
            if face not in skip:
                self._add_face([ids[i] for i in _BOX_RINGS[face]], overrides.get(face, material))

    def loft(self, rings, material, caps=(True, True)):
        """Une anéis de pontos 3D (mesmo tamanho; um anel de 1 ponto é ápice) num sólido fechado."""
        first = len(self._polygons)
        ids = [self._push(ring) for ring in rings]
        for level in range(len(rings) - 1):
            lo, hi = ids[level], ids[level + 1]
            count = len(lo) if len(lo) > 1 else len(hi)
            for j in range(count):
                k = (j + 1) % count
                if len(hi) == 1:
                    self._add_face([lo[j], lo[k], hi[0]], material)
                elif len(lo) == 1:
                    self._add_face([hi[k], hi[j], lo[0]], material)
                else:
                    self._add_face([lo[j], lo[k], hi[k], hi[j]], material)
        if caps[0] and len(ids[0]) > 2:
            self._add_face(list(reversed(ids[0])), material)
        if caps[1] and len(ids[-1]) > 2:
            self._add_face(ids[-1], material)
        closed = (caps[0] or len(ids[0]) == 1) and (caps[1] or len(ids[-1]) == 1)
        if closed:
            self._orient_outward(first)

    def lathe(self, profile, material, segments=12, caps=(True, True), center=(0.0, 0.0, 0.0), phase=0.0):
        """Revolve [(raio, altura), ...] em torno do eixo Z local: pés de mesa, balaústres, maçanetas."""
        cx, cy, cz = center
        rings = []
        for radius, height in profile:
            if radius < 1e-6:
                rings.append([(cx, cy, cz + height)])
            else:
                rings.append([(cx + x, cy + y, cz + height) for x, y in circle(radius, segments, phase)])
        self.loft(rings, material, caps)

    def tube(self, start, end, radius, material, segments=8, radius_end=None, caps=(True, True)):
        """Cilindro (ou tronco) entre dois pontos quaisquer."""
        direction = Vector(end) - Vector(start)
        if direction.length < 1e-7:
            return
        rotation = Vector((0, 0, 1)).rotation_difference(direction).to_matrix().to_4x4()
        saved = self._transform
        self._transform = saved @ Matrix.Translation(start) @ rotation
        try:
            self.lathe([(radius, 0.0), (radius if radius_end is None else radius_end, direction.length)],
                       material, segments, caps)
        finally:
            self._transform = saved

    def torus(self, major, minor, material, segments=16, minor_segments=6):
        """Anel no plano XY local (argolas de cortina, arruelas)."""
        rings = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            ca, sa = math.cos(angle), math.sin(angle)
            rings.append([((major + minor * math.cos(2 * math.pi * j / minor_segments)) * ca,
                           (major + minor * math.cos(2 * math.pi * j / minor_segments)) * sa,
                           minor * math.sin(2 * math.pi * j / minor_segments)) for j in range(minor_segments)])
        first = len(self._polygons)
        ids = [self._push(ring) for ring in rings]
        for i in range(segments):
            following = (i + 1) % segments
            for j in range(minor_segments):
                k = (j + 1) % minor_segments
                self._add_face([ids[i][j], ids[following][j], ids[following][k], ids[i][k]], material)
        self._orient_outward(first)

    def sweep(self, profile, points, sides, depth, material, caps=(True, True)):
        """Varre o perfil fechado [(u, v), ...] ao longo da trilha `points`, com quinas em meia-esquadria.

        `sides[i]` é o vetor unitário de `u` no trecho i (um por segmento) e `depth` o de `v`: um vetor só
        (constante) ou uma lista por segmento, quando o "para cima" da moldura gira com a trilha (corrimão
        inclinado). Ambos devem ser perpendiculares à trilha. Em cada quina o anel é deslocado pela média
        dos dois lados, o que desenha a esquadria de uma guarnição sem recortar nada.
        """
        segments = len(points) - 1
        side_vectors = _per_segment(sides, segments)
        depth_vectors = _per_segment(depth, segments)
        rings = []
        for index, point in enumerate(points):
            lateral, stretch_u = _mitre(side_vectors, index, segments)
            vertical, stretch_v = _mitre(depth_vectors, index, segments)
            rings.append([tuple(Vector(point) + lateral * (u * stretch_u) + vertical * (v * stretch_v))
                          for u, v in profile])
        self.loft(rings, material, caps)

    def prism(self, profile, start, end, side, depth, material):
        """Extrusão reta do perfil entre dois pontos (rodapés, sancas, longarinas)."""
        self.sweep(profile, [start, end], [side], depth, material)

    # ------------------------------------------------------------------
    # Saída
    # ------------------------------------------------------------------
    def to_mesh(self, origin=(0.0, 0.0, 0.0)):
        ox, oy, oz = origin
        used = sorted({i for polygon in self._polygons for i in polygon})
        remap = {old: new for new, old in enumerate(used)}
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata([(self._points[i][0] - ox, self._points[i][1] - oy, self._points[i][2] - oz) for i in used],
                         [], [tuple(remap[i] for i in polygon) for polygon in self._polygons])
        for name in self.material_names:
            mesh.materials.append(materials.material_for(name))
        mesh.polygons.foreach_set("material_index", self._slots)
        if any(uv is not None for uv in self._uvs):
            self._write_uv(mesh)
        mesh.update()
        return mesh

    def _write_uv(self, mesh):
        layer = mesh.uv_layers.new(name="UVMap")
        flat = []
        for polygon, uv in zip(self._polygons, self._uvs):
            flat.extend(uv if uv is not None else [(0.0, 0.0)] * len(polygon))
        layer.data.foreach_set("uv", [c for pair in flat for c in pair])

    def build(self, ctx, collection, collision=False, hide=False, origin=(0.0, 0.0, 0.0)):
        """Cria o objeto acabado, liga à coleção e devolve-o (None se não há geometria)."""
        if not self._polygons:
            return None
        mesh = self.to_mesh(origin)
        if self.finish is not None:
            mesh = craft.finish_mesh(mesh, self.finish, ctx.quality)
        obj = bpy.data.objects.new(self.name, mesh)
        obj.location = origin
        ctx.link(obj, collection)
        if collision:
            obj["sa_col"] = 1
        if hide:
            obj.hide_render = True
            obj.hide_viewport = True
        return obj

    def build_mesh(self, origin=(0.0, 0.0, 0.0), quality="medium"):
        """Só a malha acabada (para juntar com outra, como a cortina simulada)."""
        mesh = self.to_mesh(origin)
        return craft.finish_mesh(mesh, self.finish, quality) if self.finish is not None else mesh


def build_combined(ctx, collection, name, builders, origin=(0.0, 0.0, 0.0), collision=False):
    """Um único objeto a partir de vários construtores, cada um com o seu acabamento (chanfro ou perfil)."""
    meshes = [builder.build_mesh(origin, ctx.quality) for builder in builders if builder._polygons]
    if not meshes:
        return None
    joined = craft.join_meshes(meshes, name) if len(meshes) > 1 else meshes[0]
    joined.name = name
    for mesh in meshes:
        if mesh is not joined and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    obj = bpy.data.objects.new(name, joined)
    obj.location = origin
    ctx.link(obj, collection)
    if collision:
        obj["sa_col"] = 1
    return obj
