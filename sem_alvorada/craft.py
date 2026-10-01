"""Acabamento de malhas: o que separa "caixas empilhadas" de um objeto com cara de objeto.

Tudo usa ferramentas nativas do Blender (modificadores avaliados pelo depsgraph, bmesh, simulação de
tecido) e roda em modo headless. O resultado é sempre uma malha NOVA com os modificadores já aplicados:
o .blend final não carrega modificadores, só geometria.

Três ideias resolvem quase tudo:

* **Chanfro**: nenhuma quina real é perfeitamente viva. Uma faixa de 3 a 10 mm ao redor de cada aresta
  pega a luz da lanterna e desenha o contorno do objeto. É o maior ganho de realismo por unidade de esforço.
* **Normais por ângulo**: superfícies suaves ficam lisas, arestas agudas continuam duras. Sem isso, um
  cilindro de 12 lados parece um cilindro de 12 lados.
* **Desgaste**: um deslocamento mínimo por ruído tira a perfeição de CAD (madeira empenada, reboco irregular).

Para formas orgânicas (almofada, assento de vaso, travesseiro) use `subsurf`; para tecido caído sobre
algo (lençol, manta, cortina, toalha) use `drape`.
"""
import math
from dataclasses import dataclass, replace

import bmesh
import bpy
from mathutils import Vector, noise


@dataclass(frozen=True)
class Finish:
    """Receita de acabamento de uma malha."""
    bevel: float = 0.004              # largura do chanfro em metros; 0 desliga
    bevel_segments: int = 2           # 1 = quina chata, 2-3 = arredondada
    bevel_angle: float = 28.0         # só arestas mais agudas que isto (graus) recebem chanfro
    smooth_angle: float = 42.0        # arestas além deste ângulo ficam duras no sombreamento
    subsurf: int = 0                  # níveis de subdivisão Catmull-Clark (formas orgânicas)
    wear: float = 0.0                 # amplitude do ruído de desgaste, em metros
    wear_scale: float = 0.18          # tamanho (m) das ondulações do desgaste
    seed: int = 0


# receitas prontas
STANDARD = Finish(bevel=0.004, bevel_segments=2)                   # padrão do kit: custa pouco e já pega luz
CRISP = Finish(bevel=0.0025, bevel_segments=2)                       # metal, plástico, eletrodomésticos
FURNITURE = Finish(bevel=0.006, bevel_segments=3, smooth_angle=48)   # madeira e móveis em geral
SOFT = Finish(bevel=0.018, bevel_segments=4, smooth_angle=75, subsurf=1)      # estofados, travesseiros
WORN = Finish(bevel=0.005, bevel_segments=2, wear=0.0035, wear_scale=0.22)     # reboco, madeira velha
RAW = Finish(bevel=0.0, subsurf=0, smooth_angle=180.0)               # não mexer

_QUALITY_SEGMENTS = {"low": -1, "medium": 0, "high": 1}


# --------------------------------------------------------------------------
# Núcleo: aplicar modificadores a uma malha e devolver a malha resultante
# --------------------------------------------------------------------------
def bake_mesh(mesh, configure):
    """Aplica os modificadores que `configure(obj)` adicionar e devolve uma malha nova.

    O objeto temporário só existe durante a avaliação: o depsgraph precisa de um objeto numa cena
    para calcular modificadores, mas nada fica para trás.
    """
    scene = bpy.context.scene
    holder = bpy.data.objects.new("_craft_holder", mesh)
    scene.collection.objects.link(holder)
    try:
        configure(holder)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = holder.evaluated_get(depsgraph)
        baked = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
    finally:
        scene.collection.objects.unlink(holder)
        bpy.data.objects.remove(holder)
    return baked


def _scaled(spec, quality):
    shift = _QUALITY_SEGMENTS.get(quality, 0)
    if shift == 0:
        return spec
    segments = max(1, spec.bevel_segments + shift)
    subsurf = max(0, spec.subsurf + (shift if spec.subsurf else 0))
    return replace(spec, bevel_segments=segments, subsurf=subsurf)


def finish_mesh(mesh, spec=FURNITURE, quality="medium"):
    """Chanfro + subdivisão + desgaste + normais por ângulo. Devolve uma malha nova (a original é removida)."""
    spec = _scaled(spec, quality)
    if spec is RAW or (spec.bevel <= 0 and spec.subsurf <= 0 and spec.wear <= 0):
        shade_by_angle(mesh, spec.smooth_angle)
        return mesh

    def configure(holder):
        if spec.bevel > 0:
            bevel = holder.modifiers.new("craft_bevel", "BEVEL")
            bevel.width = spec.bevel
            bevel.segments = spec.bevel_segments
            bevel.limit_method = "ANGLE"
            bevel.angle_limit = math.radians(spec.bevel_angle)
            bevel.affect = "EDGES"
            bevel.profile = 0.5
        if spec.subsurf > 0:
            subsurf = holder.modifiers.new("craft_subsurf", "SUBSURF")
            subsurf.levels = spec.subsurf
            subsurf.render_levels = spec.subsurf
            subsurf.quality = 3

    baked = bake_mesh(mesh, configure)
    if spec.wear > 0:
        wear(baked, spec.wear, spec.wear_scale, spec.seed)
    shade_by_angle(baked, spec.smooth_angle)
    old_name = mesh.name
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)
        baked.name = old_name
    return baked


# --------------------------------------------------------------------------
# Sombreamento e desgaste
# --------------------------------------------------------------------------
def shade_by_angle(mesh, angle_deg=42.0):
    """Faces lisas; arestas mais agudas que `angle_deg` ficam marcadas como duras."""
    if angle_deg >= 179.0:
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        return mesh
    limit = math.radians(angle_deg)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for face in bm.faces:
        face.smooth = True
    for edge in bm.edges:
        faces = edge.link_faces
        if len(faces) == 2:
            edge.smooth = faces[0].normal.angle(faces[1].normal, 0.0) <= limit
        else:
            edge.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def wear(mesh, amount, scale=0.18, seed=0):
    """Desloca cada vértice ao longo da normal por um ruído suave: tira a perfeição de CAD."""
    offset = Vector((seed * 17.31, seed * 5.77, seed * 9.13))
    for vertex in mesh.vertices:
        sample = noise.noise((vertex.co + offset) / max(scale, 1e-4), noise_basis="PERLIN_ORIGINAL")
        vertex.co += vertex.normal * (sample * amount)
    mesh.update()
    return mesh


def jitter(mesh, amount, seed=0):
    """Ruído por vértice (sem coerência espacial): para cascalho, terra, tecido amassado muito fino."""
    import random
    rng = random.Random(seed)
    for vertex in mesh.vertices:
        vertex.co += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * amount
    mesh.update()
    return mesh


# --------------------------------------------------------------------------
# Tecido: lençol, manta, cortina, toalha
# --------------------------------------------------------------------------
def cloth_grid(width, depth, nx, ny, origin=(0.0, 0.0, 0.0)):
    """Malha plana de `width` x `depth` m, `nx` x `ny` células, no plano XY a partir de `origin`."""
    ox, oy, oz = origin
    verts = [(ox + width * i / nx, oy + depth * j / ny, oz) for j in range(ny + 1) for i in range(nx + 1)]
    faces = [(j * (nx + 1) + i, j * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i)
             for j in range(ny) for i in range(nx)]
    mesh = bpy.data.meshes.new("cloth_grid")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def drape(cloth_mesh, colliders, frames=70, mass=0.25, stiffness=12.0, bending=6.0, pin_group=None,
          thickness=0.012, pressure=None, subsurf=1, settle_frames=20):
    """Deixa um pano cair sobre `colliders` (lista de objetos com malha) e devolve a malha assentada.

    A simulação é a do próprio Blender: o pano começa onde a malha foi criada (normalmente alguns
    centímetros acima dos objetos), cai, enrosca nas bordas e para. `pressure` (> 0) infla o pano como um
    travesseiro: use uma malha fechada (duas grades coladas) nesse caso.

    Os colliders precisam estar linkados à cena e ter coordenadas finais. Devolve a malha de saída
    (já com `subsurf` aplicado para suavizar as dobras).
    """
    scene = bpy.context.scene
    cloth_obj = bpy.data.objects.new("_craft_cloth", cloth_mesh)
    scene.collection.objects.link(cloth_obj)
    previous_frame = scene.frame_current
    try:
        for target in colliders:
            if "COLLISION" not in {m.type for m in target.modifiers}:
                modifier = target.modifiers.new("craft_collision", "COLLISION")
                modifier.settings.thickness_outer = 0.004
                modifier.settings.use_culling = False
        cloth = cloth_obj.modifiers.new("craft_cloth", "CLOTH")
        settings = cloth.settings
        settings.mass = mass
        settings.tension_stiffness = stiffness
        settings.compression_stiffness = stiffness
        settings.shear_stiffness = stiffness
        settings.bending_stiffness = bending
        settings.quality = 8
        if pin_group:
            settings.vertex_group_mass = pin_group
        if pressure:
            settings.use_pressure = True
            settings.uniform_pressure_force = pressure
        cloth.collision_settings.use_collision = True
        cloth.collision_settings.distance_min = thickness
        cloth.collision_settings.use_self_collision = True
        cloth.collision_settings.self_distance_min = thickness * 0.8
        cloth.point_cache.frame_start = 1
        cloth.point_cache.frame_end = frames + settle_frames

        scene.frame_set(1)
        for frame in range(2, frames + settle_frames + 1):
            scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = cloth_obj.evaluated_get(depsgraph)
        settled = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
    finally:
        scene.frame_set(previous_frame)
        scene.collection.objects.unlink(cloth_obj)
        bpy.data.objects.remove(cloth_obj)
        for target in colliders:
            for modifier in [m for m in target.modifiers if m.name == "craft_collision"]:
                target.modifiers.remove(modifier)
    for polygon in settled.polygons:
        polygon.use_smooth = True
    if subsurf:
        settled = bake_mesh(settled, lambda holder: _add_subsurf(holder, subsurf))
        for polygon in settled.polygons:
            polygon.use_smooth = True
    return settled


def _add_subsurf(holder, levels):
    modifier = holder.modifiers.new("craft_subsurf", "SUBSURF")
    modifier.levels = levels
    modifier.render_levels = levels


# --------------------------------------------------------------------------
# Curvas: cabos, fios, cordas, corrimãos
# --------------------------------------------------------------------------
def tube_along(points, radius, segments=8, resolution=6, taper=None, name="tube"):
    """Malha de um tubo de `radius` m seguindo `points` (curva suave por Catmull-Rom). Retorna uma malha.

    `taper` opcional: função t(0..1) -> fator de raio. Usa o objeto curva do Blender e converte.
    """
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = resolution
    curve.bevel_depth = radius
    curve.bevel_resolution = max(1, segments // 2 - 1)
    curve.use_fill_caps = True
    spline = curve.splines.new("NURBS" if len(points) > 3 else "POLY")
    spline.points.add(len(points) - 1)
    for point, (x, y, z) in zip(spline.points, points):
        point.co = (x, y, z, 1.0)
    spline.order_u = min(4, len(points))
    spline.use_endpoint_u = True
    if taper:
        for index, point in enumerate(spline.points):
            point.radius = taper(index / max(1, len(points) - 1))
    holder = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(holder)
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = holder.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
    finally:
        bpy.context.scene.collection.objects.unlink(holder)
        bpy.data.objects.remove(holder)
        bpy.data.curves.remove(curve)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return mesh


def join_meshes(meshes, name="joined"):
    """Une várias malhas numa só preservando materiais (a ordem dos slots é a da primeira aparição)."""
    bm = bmesh.new()
    slots = []
    for mesh in meshes:
        remap = {}
        for index, material in enumerate(mesh.materials):
            if material not in slots:
                slots.append(material)
            remap[index] = slots.index(material)
        scratch = bmesh.new()
        scratch.from_mesh(mesh)
        for face in scratch.faces:
            face.material_index = remap.get(face.material_index, 0)
        scratch.to_mesh(mesh)
        scratch.free()
        bm.from_mesh(mesh)
    result = bpy.data.meshes.new(name)
    bm.to_mesh(result)
    bm.free()
    for material in slots:
        result.materials.append(material)
    return result


def load_npz(path, materials=(), name=None):
    """Malha gravada por um script de `tools/modelagem/` (autoria com bibliotecas fora do Blender).

    Formato do `.npz`: `verts` (V, 3) float; `faces` (F, k) int com k = 3 ou 4 (use -1 para completar
    triângulos numa tabela de quadriláteros); opcionais `material_ids` (F,) e `uvs` (F, k, 2).
    `materials`: lista de materiais do Blender, indexada por `material_ids`.
    """
    import numpy as np
    arrays = np.load(path)
    polygons = [tuple(int(i) for i in face if i >= 0) for face in arrays["faces"]]
    mesh = bpy.data.meshes.new(name or str(path).rsplit("/", 1)[-1].rsplit(".", 1)[0])
    mesh.from_pydata([tuple(map(float, v)) for v in arrays["verts"]], [], polygons)
    for material in materials:
        mesh.materials.append(material)
    if "material_ids" in arrays:
        mesh.polygons.foreach_set("material_index", [int(i) for i in arrays["material_ids"]])
    if "uvs" in arrays:
        layer = mesh.uv_layers.new(name="UVMap")
        flat = [pair for face, uv in zip(polygons, arrays["uvs"]) for pair in uv[:len(face)]]
        layer.data.foreach_set("uv", [float(c) for pair in flat for c in pair])
    mesh.update()
    return mesh
