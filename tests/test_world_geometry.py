"""Testes do módulo world: construção, portas, colisão, escada, materiais, luzes e qualidade.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_world_geometry.py

Constrói só a etapa `world` (em out/world/) e confere o contrato da seção 4 de docs/CONTRACT.md
com asserts e raios num BVHTree feito só com as malhas `sa_col`.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from sem_alvorada import build, layout  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.world import lighting, materials, quality  # noqa: E402

OUT = os.path.join(ROOT, "out", "world", "test_geometry.blend")
STATIC_TRIANGLE_BUDGET = C.BUDGET_TRIS["scene_total"]
WORLD_TRIANGLE_BUDGET = C.BUDGET_TRIS["world_total"]
RAY_HEIGHT = 1.0
STAIR_TOLERANCE = 0.02
MAX_TEXTURE_SIDE = 1024
MAX_TEXTURE_PIXELS = 512 * 512 * 2


_STATE = {}


def world_scene():
    """Constrói a etapa uma única vez por processo (pytest chama cada teste em separado)."""
    if "scene" not in _STATE:
        failures = build.run(["world"], OUT, strict=True)
        assert not failures, failures
        _STATE["scene"] = bpy.context.scene
    return _STATE["scene"]


def world_bvh():
    if "bvh" not in _STATE:
        _STATE["bvh"] = collision_bvh(world_scene())
    return _STATE["bvh"]


def triangles(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def collision_bvh(scene):
    """BVH em coordenadas de mundo com todas as malhas sa_col (inclusive proxies ocultos)."""
    points, polygons = [], []
    for obj in scene.objects:
        if obj.type != "MESH" or not obj.get(C.P_COL):
            continue
        base = len(points)
        points.extend(tuple(obj.matrix_world @ v.co) for v in obj.data.vertices)
        polygons.extend(tuple(base + i for i in p.vertices) for p in obj.data.polygons)
    return BVHTree.FromPolygons(points, polygons)


def first_hit(bvh, origin, direction, distance):
    return bvh.ray_cast(Vector(origin), Vector(direction).normalized(), distance)


# --------------------------------------------------------------------------
def test_doors():
    scene = world_scene()
    for op in layout.doors():
        pivot = scene.objects[C.N_DOOR + op.id]
        placement = layout.door_transform(op)
        assert pivot.type == "EMPTY", pivot.name
        assert pivot[C.P_ID] == op.id
        assert pivot[C.P_INTERACT] == "door"
        assert pivot[C.P_LOCK] == op.lock
        assert math.isclose(pivot[C.P_DOOR_CLOSED], placement["closed_yaw"], abs_tol=1e-6)
        assert math.isclose(pivot[C.P_DOOR_OPEN], placement["open_yaw"], abs_tol=1e-6)
        assert math.isclose(pivot.rotation_euler.z, placement["closed_yaw"], abs_tol=1e-6)
        swing = (pivot[C.P_DOOR_OPEN] - pivot[C.P_DOOR_CLOSED] + math.pi) % (2 * math.pi) - math.pi
        assert math.isclose(abs(swing), math.pi / 2, abs_tol=1e-6), f"{op.id}: giro de {math.degrees(swing)} graus"
        assert (pivot.location - Vector(placement["hinge"])).length < 1e-5, op.id

        leaf = scene.objects[f"DoorLeaf_{op.id}"]
        assert leaf.parent is pivot and scene.objects[f"DoorHandle_{op.id}"].parent is pivot
        xs = [v.co.x for v in leaf.data.vertices]
        ys = [v.co.y for v in leaf.data.vertices]
        zs = [v.co.z for v in leaf.data.vertices]
        assert math.isclose(min(xs), 0.0, abs_tol=1e-6), f"{op.id}: a folha deve nascer na dobradiça, em +X"
        assert math.isclose(max(xs), op.width - 0.02, abs_tol=1e-6), op.id
        assert abs(max(zs) - layout.DOOR_H) < 0.02 and min(zs) >= 0.0
        assert abs(min(ys) + max(ys)) < 1e-6 and 0.03 < max(ys) - min(ys) < 0.08, f"{op.id}: espessura"
        assert f"DoorFrame_{op.id}" in scene.objects
        assert not leaf.get(C.P_COL), "portas não entram na colisão estática"
    assert len(layout.doors()) == sum(1 for o in scene.objects if o.name.startswith(C.N_DOOR))


def test_door_leaf_closes_the_gap():
    scene = world_scene()
    """Com o yaw fechado, a folha (em +X local) cobre exatamente o vão: extremidades na parede."""
    for op in layout.doors():
        pivot = scene.objects[C.N_DOOR + op.id]
        leaf = scene.objects[f"DoorLeaf_{op.id}"]
        far = pivot.matrix_world @ Vector((max(v.co.x for v in leaf.data.vertices), 0.0, 0.0))
        along = far.x if op.axis == "x" else far.y
        other_edge = op.b if op.hinge == "a" else op.a
        assert abs(along - other_edge) < 0.03, f"{op.id}: folha termina em {along:.3f}, vão em {other_edge:.3f}"


def test_windows_garage_and_sun():
    scene = world_scene()
    for op in layout.windows():
        window = scene.objects[C.N_WINDOW + op.id]
        assert window[C.P_INTERACT] == "look" and window[C.P_PROMPT] == "[E] Olhar"
    rollup = scene.objects[C.OBJ_GARAGE_ROLLUP]
    assert rollup.type == "EMPTY" and rollup["sa_open_lift"] == 2.3
    op = layout.OPENINGS["garage_rollup"]
    assert abs(rollup.location.x - op.mid[0]) < 1e-6 and rollup.location.z == 0.0
    assert any(child.name.startswith("GarageRollup_Panels") for child in rollup.children)

    from sem_alvorada.world import sky
    disc = scene.objects["BlackSun_Disc"]
    direction = (disc.matrix_world.translation - Vector(sky.SUN_ANCHOR)).normalized()
    assert (direction - sky.sun_direction()).length < 0.01, "o disco deve estar na direção de SUN_RING"
    assert disc.matrix_world.translation.z > 15.0


def test_collision_exists():
    scene = world_scene()
    solid = [o for o in scene.objects if o.get(C.P_COL)]
    names = {o.name for o in solid}
    for expected in ("Walls_L0", "Walls_L1", "Stairs_Main"):
        assert expected in names, expected
    assert any(n.startswith("Floor_L0_") for n in names) and any(n.startswith("Floor_L1_") for n in names)
    assert not any(n.startswith("Ceiling") or n.startswith("Roof") for n in names)
    for o in solid:
        if o.name.startswith("COL_"):
            assert o.hide_render and o.hide_viewport, o.name
            assert C.COL_COLLISION in [c.name for c in o.users_collection], o.name


def test_openings_are_passable_and_walls_solid():
    bvh = world_bvh()
    for op in layout.OPENINGS.values():
        if op.kind not in ("door", "arch"):
            continue
        z = layout.LEVEL_Z[op.level] + RAY_HEIGHT
        mx, my = op.mid
        along = (1.0, 0.0) if op.axis == "y" else (0.0, 1.0)
        start = (mx - along[0] * 1.5, my - along[1] * 1.5, z)
        hit = first_hit(bvh, start, (*along, 0.0), 3.0)
        assert hit[0] is None, f"{op.id}: raio pelo meio do vão bateu em {hit[0]}"
    check_room_to_room_paths(bvh)
    for level in (0, 1):
        for piece in layout.wall_pieces(level):
            if piece.kind != "full" or piece.b - piece.a < 0.4:
                continue
            mid = (piece.a + piece.b) / 2
            z = piece.z0 + RAY_HEIGHT
            if piece.axis == "x":
                start, direction = (mid, piece.pos - 0.8, z), (0.0, 1.0, 0.0)
            else:
                start, direction = (piece.pos - 0.8, mid, z), (1.0, 0.0, 0.0)
            hit = first_hit(bvh, start, direction, 1.6)
            assert hit[0] is not None, f"parede {piece.axis}={piece.pos} [{piece.a},{piece.b}] sem colisão"
    for op in layout.windows():
        z = layout.LEVEL_Z[op.level] + op.sill + op.height / 2
        mx, my = op.mid
        along = (1.0, 0.0) if op.axis == "y" else (0.0, 1.0)
        hit = first_hit(bvh, (mx - along[0], my - along[1], z), (*along, 0.0), 2.0)
        assert hit[0] is not None, f"janela {op.id} deixa passar"
    rollup = layout.OPENINGS["garage_rollup"]
    hit = first_hit(bvh, (rollup.mid[0], -1.0, 1.0), (0, 1, 0), 2.0)
    assert hit[0] is not None, "o portão fechado deve bloquear"


def crosses_stairwell(a, b):
    """True se o segmento a-b (em planta) atravessa a caixa da escada, onde os degraus e o
    guarda-corpo bloqueiam de propósito."""
    zone = layout.STAIRS.hole.inflate(0.2)
    return any(zone.contains(a[0] + (b[0] - a[0]) * t / 20, a[1] + (b[1] - a[1]) * t / 20) for t in range(21))


def check_room_to_room_paths(bvh):
    """Do centro de um cômodo, pelo meio da porta ou do arco, ao centro do vizinho: nada no caminho."""
    checked = 0
    for op in layout.OPENINGS.values():
        if op.kind not in ("door", "arch") or len(op.rooms) != 2:
            continue
        z = layout.LEVEL_Z[op.level] + RAY_HEIGHT
        mid = op.mid
        for room_id in op.rooms:
            centre = layout.ROOMS[room_id].rect.center
            if crosses_stairwell(centre, mid):
                continue
            gap = Vector((mid[0] - centre[0], mid[1] - centre[1], 0.0))
            hit = first_hit(bvh, (*centre, z), tuple(gap), gap.length)
            assert hit[0] is None, f"{room_id} -> {op.id}: caminho bloqueado em {tuple(round(c, 2) for c in hit[0])}"
            checked += 1
    assert checked >= 20, checked


def test_stairs_match_layout():
    bvh = world_bvh()
    stairs = layout.STAIRS
    samples = 0
    y = stairs.y0 + 0.03
    while y < stairs.y1 - 0.03:
        for x in (stairs.x0 + 0.1, (stairs.x0 + stairs.x1) / 2, stairs.x1 - 0.1):
            hit = first_hit(bvh, (x, y, 5.0), (0, 0, -1), 6.0)
            assert hit[0] is not None, (x, y)
            expected = layout.stairs_height(x, y)
            assert abs(hit[0].z - expected) <= STAIR_TOLERANCE, f"({x:.2f},{y:.2f}): {hit[0].z:.3f} != {expected:.3f}"
            samples += 1
        y += 0.07
    assert samples > 150


def test_floor_hole_and_landing():
    scene, bvh = world_scene(), world_bvh()
    stairs = layout.STAIRS
    hit = first_hit(bvh, (5.5, 5.0, 5.0), (0, 0, -1), 6.0)
    assert hit[0].z < 2.75, "o piso do andar 1 deve ter o furo da escada"
    assert abs(first_hit(bvh, (7.0, 5.0, 5.0), (0, 0, -1), 6.0)[0].z - 2.8) < 1e-6
    assert abs(first_hit(bvh, (5.6, stairs.y1 + 0.3, 5.0), (0, 0, -1), 6.0)[0].z - 2.8) < 1e-6
    assert abs(first_hit(bvh, (2.5, 2.5, 1.0), (0, 0, -1), 2.0)[0].z) < 1e-6
    ceiling = bvh_of(scene, "Ceiling_L0")
    assert ceiling.ray_cast(Vector((2.5, 2.5, 1.0)), Vector((0, 0, 1)), 3.0)[0] is not None


def bvh_of(scene, name):
    obj = scene.objects[name]
    points = [tuple(obj.matrix_world @ v.co) for v in obj.data.vertices]
    return BVHTree.FromPolygons(points, [tuple(p.vertices) for p in obj.data.polygons])


def test_normals_face_outward():
    scene = world_scene()
    """Raios vindos de fora de sólidos fechados devem encontrar faces voltadas para eles."""
    leaf = bvh_of(scene, "DoorLeaf_master_hall")
    pivot = scene.objects["Door_master_hall"]
    centre = pivot.matrix_world @ Vector((0.4, 0.0, 1.0))
    for direction in ((0, 1, 0), (0, -1, 0), (1, 0, 0)):
        d = Vector(direction)
        location, normal, _, _ = leaf.ray_cast(centre - d * 2.0, d, 3.0)
        assert location is not None and normal.dot(d) < 0, f"folha: normal invertida vindo de {direction}"
    roof = bvh_of(scene, "Roof_Main")
    location, normal, _, _ = roof.ray_cast(Vector((6.0, 2.0, 20.0)), Vector((0, 0, -1)), 30.0)
    assert location is not None and normal.z > 0, "telha voltada para cima"
    location, normal, _, _ = roof.ray_cast(Vector((6.0, -0.4, 0.0)), Vector((0, 0, 1)), 30.0)
    assert location is not None and normal.z < 0, "beiral voltado para baixo"
    walls = bvh_of(scene, "Walls_L0")
    location, normal, _, _ = walls.ray_cast(Vector((4.0, -3.0, 1.0)), Vector((0, 1, 0)), 10.0)
    assert location is not None and normal.y < 0, "face externa da fachada sul"


def test_budget_and_materials():
    scene = world_scene()
    meshes = [o for o in scene.objects if o.type == "MESH"]
    visible = [o for o in meshes if not o.hide_render]
    total = sum(triangles(o) for o in visible)
    print(f"  {len(meshes)} malhas, {total} triângulos visíveis, {len(scene.objects)} objetos")
    assert total < WORLD_TRIANGLE_BUDGET < STATIC_TRIANGLE_BUDGET, total
    for obj in meshes:
        assert obj.data.materials and all(m is not None for m in obj.data.materials), f"{obj.name} sem material"
        used = {p.material_index for p in obj.data.polygons}
        assert max(used) < len(obj.data.materials), obj.name
    assert not [o for o in scene.objects if o.type == "LIGHT" and o.data.use_shadow], "luz de ambiente com sombra"


def test_every_canonical_material_is_built():
    world_scene()
    for name in materials.all_names():
        mat = materials.build_material(name)
        assert mat is not None and mat.name == name, name
        assert bpy.data.materials.get(name) is mat
    assert materials.build_material("nao_existe") is None
    images = [i for i in bpy.data.images if i.name != "Render Result"]
    assert images and all(i.packed_file is not None for i in images), "imagens precisam estar empacotadas"


def test_world_textures_are_smooth_and_sized():
    """Texturas do mundo: filtro Linear, no máximo 1024 px de lado e 0,5 Mpx; imagens de canais em Non-Color.
    (Materiais de outros módulos, como os dos props, têm regras próprias e ficam de fora.)"""
    world_scene()
    for name in materials.all_names():
        mat = bpy.data.materials[name]
        for node in (mat.node_tree.nodes if mat.node_tree else []):
            if node.bl_idname != "ShaderNodeTexImage":
                continue
            assert node.interpolation == "Linear", f"{name}: interpolação {node.interpolation}"
            width, height = node.image.size
            assert max(width, height) <= MAX_TEXTURE_SIDE and width * height <= MAX_TEXTURE_PIXELS, \
                f"{name}: textura {width}x{height}"
            if node.image.name.endswith("_channels"):
                assert node.image.colorspace_settings.name == "Non-Color", node.image.name


def test_ceiling_lights():
    scene = world_scene()
    expected = [(room, i) for room, spots in layout.CEILING_LIGHTS.items() for i in range(len(spots))]
    lights = [o for o in scene.objects if o.type == "LIGHT"]
    assert len(lights) == len(expected) <= 30
    for room, index in expected:
        light = scene.objects[f"{C.N_LIGHT}{room}_c{index}"]
        assert light.data.type == "POINT" and not light.data.use_shadow
        assert light[C.P_ROOM] == room and light[C.P_LIGHT_ENERGY] > 0
        assert 0.0 <= light[C.P_LIGHT_FLICKER] <= 1.0 and light[C.P_LIGHT_KIND] in ("ceiling", "fluorescent")
        spot = layout.CEILING_LIGHTS[room][index]
        assert abs(light.location.x - spot[0]) < 1e-6 and abs(light.location.y - spot[1]) < 1e-6
        assert f"Fixture_{room}_c{index}" in scene.objects
        assert layout.room_at(*light.location).id == room
    lighting.apply_power(scene, False)
    assert all(o.data.energy == 0 for o in lights)
    lighting.apply_power(scene, True)
    assert all(o.data.energy == o[C.P_LIGHT_ENERGY] for o in lights)


INTERIOR_PREFIXES = ("Door", "Window_", "Curtain_", "Stairs_", "Fixture", "Floor_", "Ceiling_", "Walls_", "Trim_",
                     "WallDetails_", "Decals_", "Webs_", "Peeling_", "Slab_", "ArchFrame_")
INTERIOR_TRIANGLE_BUDGET = 250_000


def interior_objects(scene):
    return [o for o in scene.objects if o.type == "MESH" and not o.hide_render and o.name.startswith(INTERIOR_PREFIXES)]


def test_interior_shell_budget():
    scene = world_scene()
    total = sum(triangles(o) for o in interior_objects(scene))
    print(f"  casca interna: {total} triângulos em {len(interior_objects(scene))} objetos")
    assert total < INTERIOR_TRIANGLE_BUDGET, total


def test_doors_are_built_not_boxed():
    """Folha com almofadas, três dobradiças e maçanetas torneadas: nada de caixa com relevo."""
    scene = world_scene()
    for op in layout.doors():
        leaf, handle = scene.objects[f"DoorLeaf_{op.id}"], scene.objects[f"DoorHandle_{op.id}"]
        assert triangles(leaf) >= 200, f"{op.id}: folha com {triangles(leaf)} triângulos"
        assert triangles(handle) >= 800, f"{op.id}: ferragens com {triangles(handle)} triângulos"
        assert any(m.name.startswith("brass") for m in handle.data.materials), op.id
        assert triangles(scene.objects[f"DoorFrame_{op.id}"]) >= 150, f"{op.id}: batente"


def test_windows_have_sashes_and_coverings():
    scene = world_scene()
    from sem_alvorada.world import windows
    for op in layout.windows():
        window = scene.objects[C.N_WINDOW + op.id]
        assert triangles(window) >= 400, f"{op.id}: janela com {triangles(window)} triângulos"
        style = windows.STYLES.get(op.id, windows.WindowStyle())
        curtain = scene.objects.get(f"Curtain_{op.id}")
        assert (curtain is not None) == (style.covering != "none"), op.id
        if curtain is not None:
            assert curtain.parent is window


def test_den_curtain_leaves_the_cork_board_free():
    """O quadro de cortiça do escritório ocupa a parede oeste a partir de y=9,07: a cortina fica ao sul de y=9."""
    scene = world_scene()
    curtain = scene.objects["Curtain_w_den_w"]
    ys = [(curtain.matrix_world @ v.co).y for v in curtain.data.vertices]
    assert max(ys) <= 9.0, f"cortina chega a y={max(ys):.3f}"


def test_fixtures_come_in_pairs():
    """O engine esconde todo `Fixture_*` na queda de energia: a peça apagada precisa ficar num objeto à parte."""
    scene = world_scene()
    for room, spots in layout.CEILING_LIGHTS.items():
        for index in range(len(spots)):
            glow = scene.objects[f"Fixture_{room}_c{index}"]
            base = scene.objects[f"FixtureBase_{room}_c{index}"]
            assert glow["sa_glow"] == 1.0 and glow[C.P_ROOM] == room
            assert "sa_glow" not in base and triangles(base) >= 30
            assert not base.name.startswith("Fixture_")


def test_wood_floors_are_individual_boards():
    scene = world_scene()
    for name in ("Floor_L0_wood", "Floor_L1_wood"):
        floor = scene.objects[name]
        assert len(floor.data.polygons) > 400, f"{name}: {len(floor.data.polygons)} faces"
        assert floor.data.uv_layers, f"{name} sem UV (cada tábua sorteia o seu veio)"
        heights = [(floor.matrix_world @ v.co).z for v in floor.data.vertices]
        level = layout.LEVEL_Z[1 if name.endswith("L1_wood") else 0]
        assert max(heights) - level < 0.001 and level - min(heights) < 0.006


def test_stairs_have_runner_railing_and_turned_balusters():
    scene = world_scene()
    stairs = layout.STAIRS
    runner = bvh_of(scene, "Stairs_Runner")
    for i in (2, 7, 12):
        y = stairs.y0 + (i - 0.5) * stairs.tread_depth
        hit = runner.ray_cast(Vector((5.6, y, 5.0)), Vector((0, 0, -1)), 6.0)[0]
        assert hit is not None, f"passadeira ausente no degrau {i}"
        top = stairs.z0 + i * stairs.rise
        assert top - 0.001 <= hit.z <= top + 0.04, f"degrau {i}: passadeira a {hit.z - top:.3f} m do topo"
    railing = scene.objects["Stairs_Railing"]
    assert triangles(railing) > 8000 and any(m.name == "wood_dark" for m in railing.data.materials)
    assert not scene.objects["Stairs_Railing"].get(C.P_COL), "balaústres não colidem (os proxies COL_ cuidam disso)"


def test_every_textured_material_has_relief():
    """Superfície visível sem relevo está incompleta: cada material de superfície liga um Bump à textura.
    (Decalques de mancha são só cor com alfa; os `ext_*` do exterior têm teste próprio.)"""
    world_scene()
    for name in materials.SURFACES:
        if name.startswith(("decal_", "ext_")):
            continue
        mat = bpy.data.materials[name]
        assert any(n.bl_idname == "ShaderNodeBump" for n in mat.node_tree.nodes), f"{name} sem Bump"


def test_quality_levels():
    scene = world_scene()
    for level in quality.LEVELS:
        skipped = quality.apply(scene, level)
        assert scene.get("sa_quality") == level
        assert scene.eevee.use_raytracing == (level != "low")
        post = getattr(scene, "compositing_node_group", None) or scene.node_tree
        assert post is not None and len(post.nodes) >= 4
        print(f"  qualidade {level}: {len(post.nodes)} nós no compositor, ignorados: {skipped}")
    world = scene.world
    assert world is not None and world.use_nodes
    quality.apply(scene, "medium")


def main():
    ranked = sorted(globals().items(), key=lambda item: _ORDER.index(item[0]) if item[0] in _ORDER else 99)
    tests = [function for name, function in ranked if name.startswith("test_") and callable(function)]
    for function in tests:
        function()
        print(f"ok  {function.__name__}")
    print("test_world_geometry: tudo certo")


_ORDER = ["test_doors", "test_door_leaf_closes_the_gap", "test_windows_garage_and_sun", "test_collision_exists",
          "test_openings_are_passable_and_walls_solid", "test_stairs_match_layout", "test_floor_hole_and_landing",
          "test_normals_face_outward", "test_budget_and_materials", "test_every_canonical_material_is_built",
          "test_world_textures_are_smooth_and_sized", "test_interior_shell_budget", "test_doors_are_built_not_boxed",
          "test_windows_have_sashes_and_coverings", "test_den_curtain_leaves_the_cork_board_free",
          "test_fixtures_come_in_pairs",
          "test_wood_floors_are_individual_boards", "test_stairs_have_runner_railing_and_turned_balusters",
          "test_every_textured_material_has_relief",
          "test_ceiling_lights", "test_quality_levels"]


if __name__ == "__main__":
    main()
