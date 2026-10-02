"""Formas e montagem compartilhadas pela cozinha e pela garagem.

O `MeshBuilder` do kit aplica UM acabamento a tudo o que acumula. Num eletrodoméstico isso atrapalha:
o chanfro que pega luz numa quina de porta estraga um tubo de torneira (cada aresta de um cilindro de
8 lados tem 45 graus e também seria chanfrada). A `Assembly` resolve separando a peça por papel:

* `hard`: chapas, caixas, tampos (chanfro de 2 a 4 mm);
* `crisp`: metal fino e plástico (chanfro menor);
* `round`: peças torneadas, tubos e fios (sem chanfro, só suavização por ângulo);
* `soft`: estofado e tecido grosso (subdivisão).

No fim as malhas viram um único objeto, com a mesma interface que o `placement.place` espera
(`to_mesh` e `bounds`), então a `Assembly` entra no lugar de um `MeshBuilder` sem mudar nada.
"""
import math
from contextlib import ExitStack, contextmanager

import bpy
import numpy as np
from mathutils import Vector

from .. import craft
from . import kit, mat_cozinha_garagem  # noqa: F401  (o import registra os materiais kg_*)

ROUND = craft.Finish(bevel=0.0, smooth_angle=52.0)
HARD = craft.Finish(bevel=0.004, bevel_segments=2, smooth_angle=44.0)
CHAMFER = craft.Finish(bevel=0.003, bevel_segments=1, smooth_angle=40.0)
FINE = craft.Finish(bevel=0.0018, bevel_segments=1, smooth_angle=40.0)
PADDED = craft.Finish(bevel=0.008, bevel_segments=2, smooth_angle=75.0)         # estofado e miolo mole, sem subdivisão

WEAR_ATTRIBUTE = "sa_wear"


def segments(base, minimum=6):
    """Número de lados de um torneado conforme a qualidade do build (sempre par)."""
    scale = {"low": 0.6, "medium": 1.0, "high": 1.5}.get(kit.QUALITY, 1.0)
    return max(minimum, int(round(base * scale / 2)) * 2)


def arc_points(cx, cy, radius, start_deg, end_deg, count):
    """Pontos (x, y) de um arco, do ângulo inicial ao final (inclusive)."""
    return [(cx + radius * math.cos(math.radians(start_deg + (end_deg - start_deg) * i / (count - 1))),
             cy + radius * math.sin(math.radians(start_deg + (end_deg - start_deg) * i / (count - 1))))
            for i in range(count)]


class ShapeBuilder(kit.MeshBuilder):
    """`MeshBuilder` com mais formas: malhas do Blender (curvas, `.npz`), coroas e seções arredondadas."""

    def add_mesh(self, mesh, material, uv_scale=1.0):
        """Copia a geometria de uma malha do Blender para este builder, sob a transformação atual.

        `material` é um nome ou uma lista de nomes indexada pelo `material_index` da malha. A malha de
        origem é descartada se ninguém mais a usa (tubos de curva, peças carregadas de `.npz`).
        """
        names = [material] if isinstance(material, str) else list(material)
        coords = [tuple(vertex.co) for vertex in mesh.vertices]
        base = len(self._verts)
        self._verts.extend(tuple(self._xf @ Vector(point)) for point in coords)
        uv_layer = mesh.uv_layers.active
        for polygon in mesh.polygons:
            ids = [base + index for index in polygon.vertices]
            points = [coords[index] for index in polygon.vertices]
            uv = [tuple(uv_layer.data[loop].uv) for loop in polygon.loop_indices] if uv_layer else None
            name = names[min(polygon.material_index, len(names) - 1)]
            self._face(ids, points, name, polygon.use_smooth, uv, uv_scale)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    def tube_path(self, points, radius, material, sides=8, resolution=6, taper=None):
        """Tubo curvo (cano, guidão, cabo, mangueira) por uma curva suave que passa pelos pontos."""
        mesh = craft.tube_along(points, radius, segments=sides, resolution=resolution, taper=taper)
        self.add_mesh(mesh, material)

    def annulus(self, outer, inner, z0, z1, material, uv=1.0):
        """Coroa vertical: aro entre dois contornos (x, y) anti-horários com o mesmo número de pontos, de z0 a z1."""
        assert len(outer) == len(inner)
        rings = {"to": [(x, y, z1) for x, y in outer], "bo": [(x, y, z0) for x, y in outer],
                 "ti": [(x, y, z1) for x, y in inner], "bi": [(x, y, z0) for x, y in inner]}
        ids = {key: self._push(ring) for key, ring in rings.items()}
        # (anel, deslocamento) de cada canto; a ordem dá a normal para fora do aro
        sides = (((("to", 0), ("to", 1), ("ti", 1), ("ti", 0))),      # topo
                 ((("bo", 1), ("bo", 0), ("bi", 0), ("bi", 1))),      # base
                 ((("bo", 0), ("bo", 1), ("to", 1), ("to", 0))),      # parede externa
                 ((("bi", 1), ("bi", 0), ("ti", 0), ("ti", 1))))      # parede interna
        count = len(outer)
        for j in range(count):
            for side in sides:
                corners = [(key, (j + step) % count) for key, step in side]
                self._face([ids[key][index] for key, index in corners], [rings[key][index] for key, index in corners],
                           material, uv_scale=uv)

    def wrap(self, profile, cx, cy, z0, material, seg=16):
        """Faixa torneada com UV de 0 a 1 em volta e ao longo do perfil: rótulos de lata, garrafa e frasco."""
        rings = [kit.circle_points(cx, cy, z0 + z, r, seg) for r, z in profile]
        self.loft(rings, material, False, False, True, uv_grid=True)

    def dial(self, cx, y, cz, radius, material, sides=28):
        """Disco no plano XZ olhando para +Y, com UV centrado (0 a 1): mostradores, tampas pintadas, rótulos."""
        points, uv = [], []
        for index in range(sides):
            angle = 2 * math.pi * index / sides
            dx, dz = radius * math.sin(angle), radius * math.cos(angle)
            points.append((cx + dx, y, cz + dz))
            uv.append((0.5 - dx / (2 * radius), 0.5 + dz / (2 * radius)))
        self.poly(points, material, uv=uv)

    def rounded_loft(self, sections, material, corner_points=4, caps=(True, True), uv=1.0):
        """Sólido de seções retangulares arredondadas.

        Cada seção é `(z, largura, profundidade, raio, dx, dy)`: dx e dy deslocam o centro da seção
        (carenagem inclinada, para-lama). Todas têm o mesmo número de pontos, então o loft liga direto.
        """
        rings = []
        for z, width, depth, radius, dx, dy in sections:
            outline = kit.rounded_rect(width, depth, radius, corner_points)
            rings.append([(dx + x, dy + y, z) for x, y in outline])
        self.loft(rings, material, caps[0], caps[1], False, uv)

    def turned_bowl(self, cx, cy, z0, outer_profile, thickness, material, seg=16):
        """Tigela, copo ou panela: perfil externo (raio, z) de baixo para cima, espessura de parede constante.

        O perfil interno é o externo recuado `thickness`, o que dá borda e fundo grossos sem furar a malha.
        """
        inner = [(max(r - thickness, 0.0), z) for r, z in outer_profile[1:]]
        floor = outer_profile[0][1] + thickness
        profile = [(0.0, outer_profile[0][1])] + list(outer_profile) + [(r, z) for r, z in reversed(inner) if z >= floor]
        profile += [(0.0, floor)]
        self.lathe(profile, cx, cy, z0, material, seg=seg, smooth=True, cap_bottom=False, cap_top=False)


class PrebuiltMesh:
    """Adaptador para uma malha pronta (pano de `drape`, peça de `.npz`) poder passar por `placement.place`."""

    def __init__(self, mesh):
        self._mesh = mesh

    def to_mesh(self, name=None):
        if name:
            self._mesh.name = name
        return self._mesh

    def bounds(self):
        coords = np.array([tuple(v.co) for v in self._mesh.vertices])
        return tuple(coords.min(axis=0)), tuple(coords.max(axis=0))


class Assembly:
    """Uma peça feita de várias malhas com acabamentos diferentes, unidas num só objeto."""

    ROLES = {"hard": HARD, "crisp": craft.CRISP, "round": ROUND, "soft": PADDED}

    def __init__(self, name, hard=None, wear=None):
        self.name = name
        self.parts = {role: ShapeBuilder(f"{name}_{role}") for role in self.ROLES}
        for role, finish in self.ROLES.items():
            self.parts[role].finish = finish
        if hard is not None:
            self.parts["hard"].finish = hard
        self.wear = wear

    hard = property(lambda self: self.parts["hard"])
    crisp = property(lambda self: self.parts["crisp"])
    round = property(lambda self: self.parts["round"])
    soft = property(lambda self: self.parts["soft"])

    @contextmanager
    def at(self, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
        """Aplica o mesmo deslocamento/giro a todas as malhas da peça."""
        with ExitStack() as stack:
            for builder in self.parts.values():
                stack.enter_context(builder.at(x, y, z, rx, ry, rz))
            yield self

    def _filled(self):
        return [builder for builder in self.parts.values() if builder._faces]

    @property
    def tri_count(self):
        return sum(builder.tri_count for builder in self._filled())

    def bounds(self):
        boxes = [builder.bounds() for builder in self._filled()]
        low = tuple(min(box[0][axis] for box in boxes) for axis in range(3))
        high = tuple(max(box[1][axis] for box in boxes) for axis in range(3))
        return low, high

    def to_mesh(self, name=None):
        name = name or self.name
        meshes = [builder.to_mesh(f"{name}_{role}") for role, builder in self.parts.items() if builder._faces]
        joined = craft.join_meshes(meshes, name)
        for mesh in meshes:
            bpy.data.meshes.remove(mesh)
        if self.wear:
            paint_wear(joined, **self.wear)
        return joined


# ---------------------------------------------------------------------------
# Marcas de uso por vértice: sujeira que sobe do chão, desgaste nas quinas, variação por objeto
# ---------------------------------------------------------------------------
def paint_wear(mesh, grime_height=0.35, edge_gain=1.0, seed=0):
    """Grava o atributo de cor `sa_wear` por vértice: R = quina gasta, G = sujeira, B = variação.

    O material lê o atributo (nó Attribute) e escurece a sujeira, clareia a quina gasta e varia o tom.
    Quem não tem o atributo vê zero, então o mesmo material serve a objetos sem essa marcação.
    """
    count = len(mesh.vertices)
    if not count:
        return
    coords = np.empty(count * 3, np.float32)
    mesh.vertices.foreach_get("co", coords)
    coords = coords.reshape(count, 3)
    edge = _edge_wear(mesh, count) * edge_gain
    rng = np.random.default_rng(seed)
    phase = rng.uniform(0, 100, 3)
    noise = 0.5 + 0.5 * np.sin(coords[:, 0] * 7.3 + phase[0]) * np.sin(coords[:, 1] * 5.1 + phase[1]) \
        * np.sin(coords[:, 2] * 9.7 + phase[2])
    rise = np.clip(1.0 - coords[:, 2] / max(grime_height, 1e-3), 0.0, 1.0) ** 1.5
    grime = np.clip(rise * (0.55 + 0.45 * noise) + 0.15 * noise * (coords[:, 2] < 1.2), 0.0, 1.0)
    variation = rng.uniform(0.0, 1.0)
    colors = np.stack([np.clip(edge, 0, 1), grime, np.full(count, variation), np.ones(count)], axis=1).astype(np.float32)
    attribute = mesh.color_attributes.new(WEAR_ATTRIBUTE, "FLOAT_COLOR", "POINT")
    attribute.data.foreach_set("color", colors.ravel())
    mesh.update()


def _edge_wear(mesh, count):
    """Por vértice: quão agudamente se encontram as faces vizinhas (0 liso, 1 quina viva), em numpy."""
    polygons = len(mesh.polygons)
    if not polygons:
        return np.zeros(count, np.float32)
    normals = np.empty(polygons * 3, np.float32)
    mesh.polygons.foreach_get("normal", normals)
    normals = normals.reshape(polygons, 3)
    loop_vertex = np.empty(len(mesh.loops), np.int32)
    mesh.loops.foreach_get("vertex_index", loop_vertex)
    starts = np.empty(polygons, np.int32)
    totals = np.empty(polygons, np.int32)
    mesh.polygons.foreach_get("loop_start", starts)
    mesh.polygons.foreach_get("loop_total", totals)
    loop_polygon = np.repeat(np.arange(polygons), totals)
    summed = np.zeros((count, 3), np.float32)
    np.add.at(summed, loop_vertex, normals[loop_polygon])
    lengths = np.linalg.norm(summed, axis=1)
    mean = summed / np.maximum(lengths, 1e-6)[:, None]
    alignment = np.einsum("ij,ij->i", normals[loop_polygon], mean[loop_vertex])
    worst = np.ones(count, np.float32)
    np.minimum.at(worst, loop_vertex, alignment)
    return np.clip((1.0 - worst) * 2.2, 0.0, 1.0)


def front_limited_box(asm, front_y, top=None):
    """Caixa de colisão (x0, y0, z0, x1, y1, z1) da montagem cortada em `front_y` (ferragens e puxadores que saem
    da frente não aumentam o proxy) e, com `top`, na altura do tampo (itens apoiados em cima ficam fora do volume)."""
    low, high = asm.bounds()
    return [(low[0], low[1], 0.0, high[0], min(high[1], front_y), high[2] if top is None else min(high[2], top))]
