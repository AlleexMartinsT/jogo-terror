"""Testes da malha de navegação: cobertura, paredes, portas, escada, serialização e assar pela cena.

    python tests/test_ai_nav.py      (ou pytest)
"""
import math
import os
import random
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sem_alvorada import layout  # noqa: E402
from sem_alvorada.ai import nav as N  # noqa: E402
from sem_alvorada.ai.nav import NavGrid  # noqa: E402

GRID = NavGrid.from_layout()
START = layout.PLAYER_START


def strictly_inside_wall(x, y, level):
    return any(r.x0 < x < r.x1 and r.y0 < y < r.y1 for r in layout.solid_rects(level))


def path_points_dense(path, step=0.05):
    for a, b in zip(path.points, path.points[1:]):
        length = math.hypot(b.x - a.x, b.y - a.y)
        for k in range(int(length / step) + 1):
            t = k * step / length if length else 0.0
            yield a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.layer if a.layer == b.layer else b.layer


def test_every_room_is_reachable_and_nothing_walkable_touches_a_wall():
    assert GRID.reachable_rooms(START) == set(layout.ROOMS)
    for level in (0, 1):
        grid_x, grid_y = N._centers(N.CELL)
        closest = np.full(grid_x.shape, np.inf)
        for rect in layout.solid_rects(level):
            closest = np.minimum(closest, N._rect_gap(grid_x, grid_y, rect))
        assert closest[GRID.walk[level]].min() >= N.CLEARANCE - 1e-9, "célula andável colada em parede"


def test_nothing_outside_the_house_is_walkable():
    for layer in (N.GROUND, N.UPPER, N.STAIRS):
        for iy, ix in zip(*np.nonzero(GRID.walk[layer])):
            x, y = GRID.center_of(int(ix), int(iy))
            z = GRID.height_at(layer, y)
            assert layout.room_at(x, y, z) is not None, (layer, x, y)
    assert not GRID.point_ok(N.GROUND, 19.0, 5.0) and not GRID.point_ok(N.GROUND, 6.5, -0.5)
    assert not GRID.point_ok(N.GROUND, 6.5, 10.4), "atrás da porta dos fundos não há chão"


def test_paths_never_cross_walls_and_hit_door_centres():
    rng = random.Random(3)
    rooms = list(layout.ROOMS)
    for _ in range(60):
        a, b = rng.choice(rooms), rng.choice(rooms)
        pa, pb = GRID.random_point_in_room(a, rng), GRID.random_point_in_room(b, rng)
        path = GRID.find_path(pa[:3], pb[:3], lambda door: 0.0 if door != "garage_door" else None, start_layer=pa[3])
        if b == "garage" or a == "garage":
            assert path is None or a == b
            continue
        assert path is not None, (a, b)
        for x, y, layer in path_points_dense(path):
            level = 1 if layer == N.UPPER else 0
            assert not strictly_inside_wall(x, y, level), (a, b, round(x, 2), round(y, 2))
        for waypoint in path.points:
            if waypoint.door:
                assert (waypoint.x, waypoint.y) == layout.OPENINGS[waypoint.door].mid


def test_stairs_connect_floors_with_a_smooth_ramp():
    path = GRID.find_path((1.9, 5.85, 2.8), (10.0, 7.5, 0.0))
    layers = [w.layer for w in path.points]
    assert N.STAIRS in layers and layers[0] == N.UPPER and layers[-1] == N.GROUND
    heights = [w.z for w in path.points]
    assert heights[0] == 2.8 and heights[-1] == 0.0
    on_stairs = [w for w in path.points if w.layer == N.STAIRS]
    assert all(a.z >= b.z - 1e-9 for a, b in zip(on_stairs, on_stairs[1:])), "descendo: z só diminui"
    assert path.cost < 35.0
    up = GRID.find_path((10.0, 7.5, 0.0), (1.9, 5.85, 2.8))
    assert up.points[-1].z == 2.8 and any(w.layer == N.STAIRS for w in up.points)


def test_stairs_only_enter_through_the_ends():
    """O corrimão fecha as laterais: nenhuma célula do térreo ao lado da escada leva a ela."""
    stairs_cells = {(ix, iy) for iy, ix in zip(*np.nonzero(GRID.walk[N.STAIRS]))}
    for (ix, iy) in stairs_cells:
        for neighbour, _ in GRID.neighbours((N.STAIRS, int(ix), int(iy))):
            if neighbour[0] != N.STAIRS:
                assert int(iy) in (min(y for _, y in stairs_cells), max(y for _, y in stairs_cells))


def test_locked_doors_are_impassable_and_closed_doors_cost_time():
    kitchen, garage = (10.0, 7.5, 0.0), (16.0, 5.5, 0.0)
    assert GRID.find_path(kitchen, garage, lambda door: None if door == "garage_door" else 0.0) is None
    open_path = GRID.find_path(kitchen, garage, lambda door: 0.0)
    assert open_path is not None and any(w.door == "garage_door" for w in open_path.points)
    cheap = GRID.find_path((3.5, 1.45, 0.0), (6.5, 1.45, 0.0), lambda door: 0.0)
    pricey = GRID.find_path((3.5, 1.45, 0.0), (6.5, 1.45, 0.0), lambda door: 50.0 if door == "living_hall" else 0.0)
    assert any(w.door == "living_hall" for w in cheap.points)
    assert not any(w.door == "living_hall" for w in pricey.points), "com a porta cara, dá a volta pelo escritório"
    assert pricey.cost > cheap.cost


def test_nearest_walkable_and_layer_detection():
    assert GRID.layer_at(1.0, 1.0, 0.0) == N.GROUND and GRID.layer_at(1.0, 1.0, 2.8) == N.UPPER
    assert GRID.layer_at(5.6, 5.0, 1.4) == N.STAIRS
    assert GRID.nearest_walkable(N.GROUND, 5.05, 5.0) is not None     # dentro da parede: acha a célula vizinha
    assert GRID.nearest_walkable(N.GROUND, -5.0, -5.0, radius=1.0) is None


def test_pathfinding_is_fast():
    rng = random.Random(5)
    start = time.time()
    for _ in range(40):
        a, b = rng.choice(list(layout.ROOMS)), rng.choice(list(layout.ROOMS))
        pa, pb = GRID.random_point_in_room(a, rng), GRID.random_point_in_room(b, rng)
        GRID.find_path(pa[:3], pb[:3], lambda door: 0.0, start_layer=pa[3])
    assert time.time() - start < 3.0


def test_json_roundtrip_preserves_the_grid_and_paths():
    clone = NavGrid.from_json(GRID.to_json())
    for layer in (N.GROUND, N.UPPER, N.STAIRS):
        assert np.array_equal(clone.walk[layer], GRID.walk[layer])
    a = GRID.find_path((1.9, 5.85, 2.8), (10.0, 7.5, 0.0))
    b = clone.find_path((1.9, 5.85, 2.8), (10.0, 7.5, 0.0))
    assert [(w.x, w.y, w.door) for w in a.points] == [(w.x, w.y, w.door) for w in b.points]
    assert len(GRID.to_json()) < 40000, "cabe folgado num Text do Blender"


def test_obstacles_are_avoided_and_bake_keeps_every_room_connected():
    box = [(2.0, 2.0), (3.0, 2.0), (3.0, 3.0), (2.0, 3.0)]
    grid = NavGrid.from_layout({0: [box]})
    assert not grid.point_ok(N.GROUND, 2.5, 2.5) and not grid.point_ok(N.GROUND, 1.9, 2.5)
    path = grid.find_path((0.8, 2.5, 0.0), (4.4, 2.5, 0.0))
    assert path is not None
    for x, y, _ in path_points_dense(path):
        assert not (1.9 < x < 3.1 and 1.9 < y < 3.1), "o caminho passou pela caixa inflada"
    blocker = [(11.9, 5.3), (12.6, 5.3), (12.6, 6.4), (11.9, 6.4)]          # tampa a porta da garagem
    messages = []
    baked, clearance = N.bake({0: [blocker]}, log=messages.append)
    assert set(layout.ROOMS) <= baked.reachable_rooms(), "a malha assada nunca pode isolar cômodos"
    assert messages, "o fallback precisa ser registrado"


def test_bake_from_scene_writes_and_reads_the_sa_nav_text():
    import bpy
    from sem_alvorada import ai
    from sem_alvorada.buildctx import BuildContext
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2.5, 2.5, 0.5))
    cube = bpy.context.active_object
    cube.name = "COL_test_box"
    cube.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    short = bpy.data.objects.new("COL_low_rug", bpy.data.meshes.new("rug"))       # sem vértices altos: ignorado
    bpy.context.scene.collection.objects.link(short)
    ai.build(BuildContext(bpy.context.scene, verbose=False))
    text = bpy.data.texts.get(N.TEXT_NAME)
    assert text is not None and text.as_string().startswith("{")
    loaded = N.load_from_scene()
    assert loaded is not None and loaded.obstacles == 1
    assert not loaded.point_ok(N.GROUND, 2.5, 2.5) and loaded.point_ok(N.GROUND, 6.9, 5.0)
    assert set(layout.ROOMS) <= loaded.reachable_rooms()
    ai.build(BuildContext(bpy.context.scene, verbose=False))                      # idempotente
    assert len([t for t in bpy.data.texts if t.name == N.TEXT_NAME]) == 1


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} testes passaram")


if __name__ == "__main__":
    main()
