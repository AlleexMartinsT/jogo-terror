"""Panos dos quartos: lençol, edredom, coberta, toalha e roupa, simulados com `craft.drape`; travesseiros inflados.

O pano nasce plano alguns centímetros acima dos objetos que vão segurá-lo e cai na simulação do Blender.
Os colliders são montados a partir dos builders do móvel, nas mesmas coordenadas locais do pano.
"""
import math
from contextlib import contextmanager

import bmesh
import bpy
from mathutils import Matrix

from .. import craft
from . import kit, materials

COLLIDER_NAME = "_cloth_collider"
COLLIDER_FRICTION = 60.0       # sem atrito alto o pano escorrega inteiro para fora da cama


def grid_density(cell):
    """Tamanho de célula da grade do pano conforme a qualidade do build (maior no `low`)."""
    return cell * {"low": 1.5, "medium": 1.0, "high": 0.8}.get(kit.QUALITY, 1.0)


@contextmanager
def colliders(*sources, floor=None):
    """Objetos temporários na cena para o pano colidir: builders do móvel, malhas prontas e (opcional) o piso.

    `floor` é a altura do piso no sistema local do móvel; cria uma laje larga ali.
    """
    scene = bpy.context.scene
    created = []
    try:
        for source in sources:
            if hasattr(source, "to_mesh"):
                saved = source.finish
                source.finish = None
                mesh = source.to_mesh(COLLIDER_NAME)
                source.finish = saved
            else:
                mesh = source.copy()
            holder = bpy.data.objects.new(COLLIDER_NAME, mesh)
            scene.collection.objects.link(holder)
            created.append(holder)
        if floor is not None:
            plane = bpy.data.meshes.new(COLLIDER_NAME)
            half = 3.0
            plane.from_pydata([(-half, -half, floor), (half, -half, floor), (half, half, floor), (-half, half, floor)],
                              [], [(0, 1, 2, 3)])
            holder = bpy.data.objects.new(COLLIDER_NAME, plane)
            scene.collection.objects.link(holder)
            created.append(holder)
        for holder in created:
            modifier = holder.modifiers.new("craft_collision", "COLLISION")
            modifier.settings.thickness_outer = 0.004
            modifier.settings.use_culling = False
            modifier.settings.cloth_friction = COLLIDER_FRICTION
        yield created
    finally:
        for holder in created:
            mesh = holder.data
            scene.collection.objects.unlink(holder)
            bpy.data.objects.remove(holder)
            bpy.data.meshes.remove(mesh)


def _assign_flat_uv(mesh, origin, uv_scale):
    """UV do pano em repouso: metros a partir da quina, para a trama não esticar nas dobras."""
    layer = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        layer.data[loop.index].uv = ((co.x - origin[0]) * uv_scale, (co.y - origin[1]) * uv_scale)


def settle_cloth(width, depth, center, z, hold, material, *, cell=0.06, wrinkles=0.0, seed=0, uv_scale=1.0,
                 thickness=0.0, subsurf=1, frames=60, floor=None, limits=None, fold=None, **physics):
    """Pano de `width` x `depth` m centrado em `center` (x, y), solto de altura `z` sobre `hold` (lista de fontes).

    `wrinkles` (m) ondula a malha de partida: o pano assenta mantendo dobras, em vez de cair liso.
    `thickness` > 0 dá espessura ao pano (edredom, toalha grossa). `fold` = (x0, x1, y0, y1) começa o pano já
    dobrado para baixo nessas linhas (None desliga um lado): o que passa da linha pende vertical, rente ao móvel,
    em vez de cair solto e escorregar para fora da pegada. `limits` prende o resultado a uma caixa (x0, x1, y0, y1).
    Devolve a malha em coordenadas locais.
    """
    nx = max(4, int(round(width / grid_density(cell))))
    ny = max(4, int(round(depth / grid_density(cell))))
    origin = (center[0] - width / 2, center[1] - depth / 2, z)
    mesh = craft.cloth_grid(width, depth, nx, ny, origin)
    if wrinkles:
        _ripple(mesh, wrinkles, seed)
    _assign_flat_uv(mesh, origin, uv_scale)
    if fold:
        _fold_edges(mesh, fold, z)
    with colliders(*hold, floor=floor) as holders:
        settled = craft.drape(mesh, holders, frames=frames, subsurf=subsurf, **physics)
    if thickness:
        settled = craft.bake_mesh(settled, lambda holder: _solidify(holder, thickness))
        _orient_outward(settled)
    if limits:
        _squeeze_outward(settled, fold, limits)
    settled.materials.clear()
    settled.materials.append(materials.get(material))
    return settled


def _beyond(value, low, high):
    """(distância além da linha mais próxima, posição da linha) de `value`; linhas None não existem."""
    if high is not None and value > high:
        return value - high, high
    if low is not None and value < low:
        return low - value, low
    return 0.0, None


def _fold_edges(mesh, fold, z_top, gap=0.014):
    """Dobra a malha plana para baixo nas linhas `fold`; as faces dos cantos (dobradas nos dois eixos) somem."""
    x0, x1, y0, y1 = fold
    bm = bmesh.new()
    bm.from_mesh(mesh)

    def overshoot(vertex):
        return _beyond(vertex.co.x, x0, x1), _beyond(vertex.co.y, y0, y1)

    def folds_both_ways(vertex):
        (dx, _), (dy, _) = overshoot(vertex)
        return dx > 0 and dy > 0

    corner_faces = [face for face in bm.faces if any(folds_both_ways(v) for v in face.verts)]
    bmesh.ops.delete(bm, geom=corner_faces, context="FACES")
    for vertex in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(vertex)
    for vertex in bm.verts:
        (dx, line_x), (dy, line_y) = overshoot(vertex)
        if dx:
            vertex.co.x = line_x + (gap if vertex.co.x > line_x else -gap)
        if dy:
            vertex.co.y = line_y + (gap if vertex.co.y > line_y else -gap)
        vertex.co.z = z_top - dx - dy
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _squeeze_outward(mesh, fold, limits):
    """Mantém o pano dentro de `limits` comprimindo o que passou da linha de dobra, sem achatar camadas.

    Cortar com `min/max` cola tudo no mesmo plano (a espessura some e o pano fica preto na luz). Aqui o
    deslocamento além da linha é multiplicado por um fator único por lado, então a ordem das camadas e a
    forma das dobras se mantêm, só mais rentes ao móvel.
    """
    fold = fold or (None, None, None, None)
    limit_x0, limit_x1, limit_y0, limit_y1 = limits
    for axis, lines, bounds in ((0, (fold[0], fold[1]), (limit_x0, limit_x1)), (1, (fold[2], fold[3]), (limit_y0, limit_y1))):
        for line, bound, sign in ((lines[0], bounds[0], -1), (lines[1], bounds[1], 1)):
            if line is None:
                continue
            reach = max((vertex.co[axis] - line) * sign for vertex in mesh.vertices)
            allowed = (bound - line) * sign
            if reach > allowed > 0:
                factor = allowed / reach
                for vertex in mesh.vertices:
                    if (vertex.co[axis] - line) * sign > 0:
                        vertex.co[axis] = line + (vertex.co[axis] - line) * factor
    mesh.update()


def _orient_outward(mesh):
    """Normais de um pano com espessura (casca fechada) todas para fora, com sombreamento liso."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for face in bm.faces:
        face.smooth = True
    bm.to_mesh(mesh)
    bm.free()


def _ripple(mesh, amplitude, seed):
    """Ondulação de baixa frequência na malha de partida (soma de senos de fase sorteada)."""
    import random
    rng = random.Random(seed)
    waves = [(rng.uniform(3, 12), rng.uniform(3, 12), rng.uniform(0, math.tau), rng.uniform(0, math.tau)) for _ in range(5)]
    for vertex in mesh.vertices:
        offset = sum(math.sin(vertex.co.x * ax + px) * math.sin(vertex.co.y * ay + py) for ax, ay, px, py in waves)
        vertex.co.z += amplitude * offset / 2.5
    mesh.update()


def _solidify(holder, thickness):
    modifier = holder.modifiers.new("craft_solidify", "SOLIDIFY")
    modifier.thickness = thickness
    modifier.offset = 0.0


# ---------------------------------------------------------------------------
# Travesseiro: forma inflada calculada (a simulação com pressão do Blender fica instável e custa 30 s por peça)
# ---------------------------------------------------------------------------
def pillow(width, depth, height, material, *, dent=0.0, dent_at=(0.0, 0.0), lean=0.0, seed=0, uv_scale=1.0,
           cells=10):
    """Travesseiro de duas faces costuradas na borda, com cantos em orelha e uma depressão opcional (cabeça).

    A face de cima sobe `height` no centro; a de baixo é mais achatada, apoiada na cama. `lean` (rad) inclina
    o conjunto em torno do eixo X. Origem na base, centro do travesseiro.
    """
    import random
    rng = random.Random(seed)
    phase = [rng.uniform(0, math.tau) for _ in range(4)]
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    top, bottom = [], []

    def thickness_at(u, v):
        edge = (1 - abs(u) ** 2.3) ** 0.55 * (1 - abs(v) ** 2.3) ** 0.55
        return max(edge, 0.0)

    for side, grid in ((1, top), (-1, bottom)):
        for j in range(cells + 1):
            row = []
            for i in range(cells + 1):
                u, v = -1 + 2 * i / cells, -1 + 2 * j / cells
                body = thickness_at(u, v)
                z = height * body * (1.0 if side > 0 else 0.35)
                if side > 0 and dent:
                    d2 = ((u - dent_at[0]) ** 2 + (v - dent_at[1]) ** 2) / 0.16
                    z -= dent * math.exp(-d2) * body
                    z += 0.006 * math.sin(u * 9 + phase[0]) * math.sin(v * 7 + phase[1]) * body
                row.append(bm.verts.new((u * width / 2, v * depth / 2, z * side)))
            grid.append(row)
    for grid, flip in ((top, False), (bottom, True)):
        for j in range(cells):
            for i in range(cells):
                corners = [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
                face = bm.faces.new(corners[::-1] if flip else corners)
                for loop, corner in zip(face.loops, corners[::-1] if flip else corners):
                    loop[uv_layer].uv = (corner.co.x * uv_scale, corner.co.y * uv_scale)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    mesh = bpy.data.meshes.new("pillow")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(materials.get(material))
    lowest = min(v.co.z for v in mesh.vertices)
    mesh.transform(Matrix.Translation((0, 0, -lowest)))
    if lean:
        mesh.transform(Matrix.Rotation(lean, 4, "X"))
    mesh.update()
    return craft.finish_mesh(mesh, craft.Finish(bevel=0.0, subsurf=1, smooth_angle=180.0), kit.QUALITY)
