"""Construtor de malhas por listas de polígonos, com material por face.

A casa inteira é feita de caixas e polígonos planos. Em vez de chamar bpy.ops (que depende
de contexto de janela), cada peça é acumulada aqui e vira um único objeto no final. Isso
mantém poucos objetos na cena, o que importa para a viewport ao vivo.

As texturas dos materiais usam coordenadas de objeto com projeção em caixa, então as malhas
não precisam de UVs: o padrão fica colado ao mundo e nunca estica.
"""
import math

import bpy

from . import materials

FACES = ("-x", "+x", "-y", "+y", "-z", "+z")


class MeshBuilder:
    """Acumula polígonos (vértices próprios por face, sombreamento chapado)."""

    def __init__(self, name):
        self.name = name
        self.points = []
        self.polygons = []
        self.polygon_slots = []
        self.material_names = []

    def slot_of(self, material_name):
        if material_name not in self.material_names:
            self.material_names.append(material_name)
        return self.material_names.index(material_name)

    def polygon(self, corners, material):
        """Polígono convexo e plano; a ordem anti-horária vista de fora define a normal."""
        start = len(self.points)
        self.points.extend(tuple(c) for c in corners)
        self.polygons.append(tuple(range(start, start + len(corners))))
        self.polygon_slots.append(self.slot_of(material))

    def quad(self, a, b, c, d, material):
        self.polygon((a, b, c, d), material)

    def box(self, x0, y0, z0, x1, y1, z1, material, skip=(), face_materials=None):
        """Caixa alinhada aos eixos. `face_materials` troca o material de faces específicas
        (chaves de FACES); `skip` omite faces escondidas para poupar triângulos."""
        corners = {
            "-x": ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
            "+x": ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)),
            "-y": ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
            "+y": ((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)),
            "-z": ((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)),
            "+z": ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
        }
        overrides = face_materials or {}
        for face in FACES:
            if face not in skip:
                self.polygon(corners[face], overrides.get(face, material))

    def beam(self, start, end, width, height, material, up=(0.0, 0.0, 1.0), skip_ends=False):
        """Barra de seção retangular entre dois pontos (corrimãos, vigas inclinadas).

        `width` é medida na horizontal perpendicular à barra e `height` ao longo de `up`.
        """
        axis = _normalized(_sub(end, start))
        side = _normalized(_cross(axis, up))
        lift = _normalized(_cross(side, axis))
        hw, hh = width / 2, height / 2
        ring = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]

        def corner(origin, offset):
            return tuple(origin[i] + side[i] * offset[0] + lift[i] * offset[1] for i in range(3))

        near = [corner(start, o) for o in ring]
        far = [corner(end, o) for o in ring]
        for i in range(4):
            j = (i + 1) % 4
            self.quad(near[i], near[j], far[j], far[i], material)
        if not skip_ends:
            self.polygon(near[::-1], material)
            self.polygon(far, material)

    def prism(self, outline, z0, z1, material, cap_materials=None):
        """Extrusão vertical de um contorno 2D anti-horário (colunas, dutos, tampas)."""
        n = len(outline)
        for i in range(n):
            (ax, ay), (bx, by) = outline[i], outline[(i + 1) % n]
            self.quad((ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1), material)
        caps = cap_materials or (material, material)
        self.polygon([(x, y, z0) for x, y in reversed(outline)], caps[0])
        self.polygon([(x, y, z1) for x, y in outline], caps[1])

    def cylinder(self, u, v, w0, w1, radius, material, sides=8, radius_top=None, caps=True, axis="z"):
        """Cilindro (ou tronco de cone se `radius_top` difere) com eixo em x, y ou z.

        (u, v) é o centro no plano perpendicular ao eixo e w0..w1 o trecho ao longo dele.
        Os eixos são mapeados por permutação cíclica para manter as normais para fora.
        """
        top = radius if radius_top is None else radius_top
        place = _AXIS_PLACEMENT[axis]
        ring_bottom = [(u + radius * math.cos(a), v + radius * math.sin(a)) for a in _angles(sides)]
        ring_top = [(u + top * math.cos(a), v + top * math.sin(a)) for a in _angles(sides)]
        for i in range(sides):
            j = (i + 1) % sides
            self.quad(place(*ring_bottom[i], w0), place(*ring_bottom[j], w0),
                      place(*ring_top[j], w1), place(*ring_top[i], w1), material)
        if caps:
            self.polygon([place(*p, w1) for p in ring_top], material)
            self.polygon([place(*p, w0) for p in reversed(ring_bottom)], material)

    def extrude_profile(self, profile, wall_axis, n0, n1, material):
        """Extrude um perfil (u, z) ao longo da normal de uma parede.

        `wall_axis` é o eixo em que a parede corre ('x' ou 'y'); u é a coordenada
        absoluta nesse eixo, z a altura, e n0..n1 o trecho na direção da espessura.
        """
        if _signed_area(profile) < 0:
            profile = profile[::-1]
        flip = wall_axis == "x"

        def world(u, z, n):
            return (u, n, z) if wall_axis == "x" else (n, u, z)

        def emit(corners):
            self.polygon(corners[::-1] if flip else corners, material)

        emit([world(u, z, n1) for u, z in profile])
        emit([world(u, z, n0) for u, z in reversed(profile)])
        for i in range(len(profile)):
            (ua, za), (ub, zb) = profile[i], profile[(i + 1) % len(profile)]
            emit([world(ua, za, n0), world(ub, zb, n0), world(ub, zb, n1), world(ua, za, n1)])

    def build(self, ctx, collection, collision=False, hide=False, origin=(0.0, 0.0, 0.0)):
        """Cria o objeto, liga à coleção `collection` e devolve-o (ou None se vazio).

        Os pontos são dados em coordenadas de mundo; `origin` move a origem do objeto
        para esse ponto sem mexer na geometria (útil para pivôs e âncoras de interação).
        """
        if not self.polygons:
            return None
        ox, oy, oz = origin
        local_points = [(x - ox, y - oy, z - oz) for x, y, z in self.points]
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(local_points, [], self.polygons)
        mesh.polygons.foreach_set("material_index", self.polygon_slots)
        for name in self.material_names:
            mesh.materials.append(materials.material_for(name))
        mesh.update()
        mesh.validate()
        obj = bpy.data.objects.new(self.name, mesh)
        obj.location = origin
        ctx.link(obj, collection)
        if collision:
            obj["sa_col"] = 1
        if hide:
            obj.hide_render = True
            obj.hide_viewport = True
        return obj


_AXIS_PLACEMENT = {
    "z": lambda u, v, w: (u, v, w),
    "x": lambda u, v, w: (w, u, v),
    "y": lambda u, v, w: (v, w, u),
}


def _signed_area(profile):
    return sum(profile[i][0] * profile[(i + 1) % len(profile)][1] - profile[(i + 1) % len(profile)][0] * profile[i][1]
               for i in range(len(profile))) / 2


def _angles(sides):
    return [2 * math.pi * i / sides for i in range(sides)]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _normalized(v):
    length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / length, v[1] / length, v[2] / length)


def empty(ctx, name, collection, location=(0.0, 0.0, 0.0), rotation_z=0.0, parent=None):
    """Empty simples (pivôs de porta, raízes de grupos)."""
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.15
    obj.location = location
    obj.rotation_euler.z = rotation_z
    ctx.link(obj, collection)
    if parent is not None:
        obj.parent = parent
    return obj


def attach(obj, parent, location=(0.0, 0.0, 0.0)):
    """Filia `obj` a `parent` sem herdar transformação inversa (posição local explícita)."""
    obj.parent = parent
    obj.location = location
    return obj
