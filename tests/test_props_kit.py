"""Testes das primitivas do kit de modelagem (props/kit.py): orientação, UVs e medidas.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_props_kit.py
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import bmesh  # noqa: E402  (precisa vir depois do bpy no módulo pip)

from sem_alvorada.props import textures  # noqa: E402
from sem_alvorada.props.kit import MeshBuilder  # noqa: E402

def rotated_box(builder):
    with builder.at(0.5, 0.2, 0.1, 10, 20, 30):
        builder.box(0, 0, 0, 0.4, 0.2, 0.3, "metal")


CLOSED_SHAPES = {
    "box": lambda m: m.box(0, 0, 0, 1, 1, 1, "metal"),
    "frustum": lambda m: m.frustum(0, 0, 0, 1, 1, 0.5, 0.5, 1, "metal"),
    "cylinder": lambda m: m.cylinder(0, 0, 0, 0.5, 1, "metal", seg=8),
    "cone": lambda m: m.cylinder(0, 0, 0, 0.5, 1, "metal", seg=8, r_top=0),
    "lathe": lambda m: m.lathe([(0.3, 0), (0.5, 0.4), (0.2, 0.8), (0, 1)], 0, 0, 0, "metal"),
    "soft_box": lambda m: m.soft_box(0, 0, 0, 1, 0.6, 0.3, "metal", radius=0.1, edge=0.04),
    "wedge": lambda m: m.wedge(0, 0, 0, 1, 1, 0.5, "metal"),
    "tube": lambda m: m.tube((0, 0, 0), (0.5, 0.3, 1), 0.05, "metal"),
    "bar": lambda m: m.bar((0, 0, 0), (0.5, 0.3, 1), 0.05, "metal"),
    "torus": lambda m: m.torus(0, 0, 0, 0.3, 0.05, "metal", rx=40),
    "sphere": lambda m: m.sphere(0, 0, 0.5, 0.3, "metal"),
    "extruded_l": lambda m: m.extrude([(0, 0), (1, 0), (1, 0.3), (0.3, 0.3), (0.3, 1), (0, 1)], "xy", 0, 0.4, "metal"),
    "rotated_box": lambda m: rotated_box(m),
}


def signed_volume(builder):
    mesh = builder.to_mesh("kit_test")
    bm = bmesh.new()
    bm.from_mesh(mesh)
    volume = bm.calc_volume(signed=True)
    bm.free()
    return volume, mesh


def test_closed_shapes_point_outward():
    for name, make in CLOSED_SHAPES.items():
        builder = MeshBuilder(name)
        make(builder)
        volume, _ = signed_volume(builder)
        assert volume > 0, f"{name}: volume com sinal {volume} (normais para dentro)"


def test_every_loop_has_a_uv():
    builder = MeshBuilder("uv")
    builder.box(0, 0, 0, 1, 1, 1, "metal")
    builder.cylinder(2, 0, 0, 0.3, 1, "metal")
    mesh = builder.to_mesh("uv_test")
    assert len(mesh.uv_layers[0].data) == len(mesh.loops)


def test_box_uv_uses_world_scale():
    builder = MeshBuilder("scale")
    builder.box(0, 0, 0, 2, 2, 2, "metal", uv=1.0)
    mesh = builder.to_mesh("scale_test")
    coords = [tuple(d.uv) for d in mesh.uv_layers[0].data]
    assert max(u for u, _ in coords) - min(u for u, _ in coords) == 2.0


def test_panel_keeps_texture_upright():
    builder = MeshBuilder("panel")
    builder.panel(0, 0, 1, 1, 2, "metal", "front", (0, 0, 1, 1))
    mesh = builder.to_mesh("panel_test")
    loops = {tuple(round(c, 3) for c in mesh.vertices[mesh.loops[i].vertex_index].co): tuple(mesh.uv_layers[0].data[i].uv)
             for i in range(len(mesh.loops))}
    top = [uv for co, uv in loops.items() if co[2] > 1.5]
    bottom = [uv for co, uv in loops.items() if co[2] < 1.5]
    assert all(v == 1.0 for _, v in top) and all(v == 0.0 for _, v in bottom)
    right_of_viewer = [uv for co, uv in loops.items() if co[0] < 0]       # de frente (+Y) a direita de quem olha é -X
    assert all(u == 1.0 for u, _ in right_of_viewer)


def test_bounds_and_drop_to_floor():
    builder = MeshBuilder("drop")
    with builder.at(0, 0, 0, rx=90):
        builder.box(0, 0, 0, 1, 1, 1, "metal")
    builder.drop_to_floor()
    lo, hi = builder.bounds()
    assert abs(lo[2]) < 1e-6 and abs(hi[2] - 1.0) < 1e-6


def test_tri_count_matches_blender():
    builder = MeshBuilder("tris")
    builder.soft_box(0, 0, 0, 1, 1, 1, "metal")
    builder.sphere(0, 0, 2, 0.3, "metal")
    builder.finish = None          # a contagem do builder é da geometria crua, sem chanfro
    mesh = builder.to_mesh("tris_test")
    assert builder.tri_count == sum(len(p.vertices) - 2 for p in mesh.polygons)


def test_textures_are_small_and_power_of_two_friendly():
    for name in textures.TEXTURES:
        canvas = textures.canvas_for(name)
        assert 24 <= canvas.width <= 256 and 24 <= canvas.height <= 256, f"{name}: {canvas.width}x{canvas.height}"
        assert canvas.px.shape == (canvas.height, canvas.width, 4)
        assert not math.isnan(float(canvas.px.sum())), name


def test_textures_are_deterministic():
    first = textures.canvas_for("city_map").pixels()
    second = textures.canvas_for("city_map").pixels()
    assert (first == second).all()


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print("ok", test.__name__)
    print("kit OK")
    return 0


if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sys.exit(main())
