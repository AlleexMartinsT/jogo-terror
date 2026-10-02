"""Testes do carro, do portão da garagem e do exterior (fase de acabamento).

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_exterior_car.py

O carro é construído sozinho numa cena vazia; o exterior e o telhado também (sem a casca), o que torna o teste
rápido. O portão é conferido na cena do `world` completo, que o `test_world_geometry` também usa.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import build, layout, story  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.props import car, car_shape, kit  # noqa: E402
from sem_alvorada.world import exterior, garage_door, roof  # noqa: E402

MODEL = os.path.join(ROOT, "assets", "models", "carro_carroceria.npz")
EXTERIOR_BUDGET = 230_000


def triangles(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def fresh(stage):
    scene = build.fresh_scene()
    ctx = BuildContext(scene)
    ctx.stage = stage
    kit.set_quality(ctx.quality)
    return scene, ctx


def signature(scene):
    """Contagem de vértices, soma ponderada das coordenadas e posição de cada objeto."""
    out = {}
    for obj in scene.objects:
        if obj.type == "MESH":
            out[obj.name] = (len(obj.data.vertices), round(sum(v.co.x + 2 * v.co.y + 3 * v.co.z for v in obj.data.vertices), 3))
        out[obj.name + ":at"] = tuple(round(c, 4) for c in obj.location)
    return out


# --------------------------------------------------------------------------------------------
# Carro
# --------------------------------------------------------------------------------------------
def build_car():
    scene, ctx = fresh("props")
    car.make_car(ctx)
    bpy.context.view_layer.update()
    return scene


def test_car_contract():
    scene = build_car()
    root = scene.objects[C.OBJ_CAR]
    anchor = layout.ANCHORS["car"]
    assert root.type == "EMPTY" and (Vector(root.location) - Vector(anchor.pos)).length < 1e-6
    assert abs(root.rotation_euler.z - math.radians(anchor.yaw_deg)) < 1e-6
    for suffix in ("FL", "FR", "RL", "RR"):
        wheel = scene.objects[f"Car_Wheel_{suffix}"]
        assert wheel.parent is root
        zs = [v.co.z for v in wheel.data.vertices]
        assert abs(min(zs) + car_shape.WHEEL_RADIUS) < 0.01 and abs(max(zs) - car_shape.WHEEL_RADIUS) < 0.01, "origem no centro da roda"
    for side in ("L", "R"):
        lamp = scene.objects[f"Car_Headlight_{side}"]
        assert lamp.data.type == "SPOT" and lamp.data.energy == 0.0 and lamp["sa_base_energy"] > 0
    eye = scene.objects["Car_DriverEye"]
    assert (eye.matrix_world.translation - Vector(layout.ANCHORS["car_driver_eye"].pos)).length < 1e-3
    interact = scene.objects["Car_Interact"]
    assert interact[C.P_INTERACT] == "car" and interact[C.P_PROMPT] == story.PROMPT_CAR
    proxy = scene.objects["COL_car"]
    assert len(proxy.data.vertices) == 8 and proxy.get(C.P_COL) and proxy.hide_render and proxy.hide_viewport
    light = scene.objects["Light_garage_p1"]
    assert light.get(C.P_LIGHT_KIND) == "lamp" and light.parent is root


def test_car_budget_and_materials():
    scene = build_car()
    car_meshes = [o for o in scene.objects if o.type == "MESH" and o.name.startswith("Car_")]
    total = sum(triangles(o) for o in car_meshes)
    print(f"  carro: {total} triângulos em {len(car_meshes)} malhas")
    assert total <= C.BUDGET_TRIS["car"], total
    assert triangles(scene.objects["Car_Body"]) <= C.BUDGET_TRIS["car"]
    for obj in car_meshes:
        assert obj.data.materials and all(m is not None for m in obj.data.materials), obj.name
        assert max(p.material_index for p in obj.data.polygons) < len(obj.data.materials), obj.name
    body_materials = {m.name for m in scene.objects["Car_Body"].data.materials}
    for required in ("car_body_paint", "digits_dash", "car_velour", "plush_white", "car_cluster", "car_plate"):
        assert required in body_materials, f"Car_Body sem o material {required}"
    for material in bpy.data.materials:
        if material.users and material.name.startswith("car_") and material.node_tree:
            for node in material.node_tree.nodes:
                if node.bl_idname == "ShaderNodeTexImage":
                    assert node.interpolation == "Linear", f"{material.name}: filtro {node.interpolation}"
                    assert node.image.packed_file is not None and max(node.image.size) <= 1024, material.name


def test_car_is_damaged_on_the_passenger_side():
    """A frente do lado do passageiro (+X local) recuou em relação ao lado do motorista."""
    body = build_car().objects["Car_Body"]

    def front_extent(sign):
        ys = [v.co.y for v in body.data.vertices if sign * v.co.x > 0.35 and v.co.y > 1.5 and 0.3 < v.co.z < 0.7]
        return max(ys)

    assert front_extent(-1) - front_extent(1) > 0.10, (front_extent(-1), front_extent(1))


def test_car_fits_its_collision_box():
    scene = build_car()
    body = scene.objects["Car_Body"]
    xs = [v.co.x for v in body.data.vertices]
    ys = [v.co.y for v in body.data.vertices]
    zs = [v.co.z for v in body.data.vertices]
    body_only = [abs(v.co.x) for v in body.data.vertices if v.co.z < 0.97]
    assert max(body_only) < car.HALF_WIDTH + 0.03, "a chapa cabe na caixa de colisão"
    assert max(abs(min(xs)), max(xs)) < 1.18, "os espelhos podem passar da caixa, mas pouco"
    assert max(abs(min(ys)), max(ys)) < 2.45
    roof_tops = [v.co.z for v in body.data.vertices if -1.0 < v.co.y < 0.2 and abs(v.co.x) < 0.7]
    assert max(roof_tops) < car_shape.ROOF_Z + 0.06 and min(zs) > -0.01
    assert max(zs) < 2.1, "só a antena passa do teto"


def test_car_model_file():
    data = np.load(MODEL)
    assert set(data.files) >= {"verts", "faces", "material_ids"}
    assert os.path.getsize(MODEL) < 1_000_000
    assert data["faces"].max() < len(data["verts"]) and data["material_ids"].max() < len(car.SHELL_MATERIALS)


def test_car_is_deterministic():
    first = signature(build_car())
    second = signature(build_car())
    assert first == second


# --------------------------------------------------------------------------------------------
# Exterior, telhado e portão
# --------------------------------------------------------------------------------------------
def build_exterior():
    scene, ctx = fresh("world")
    roof.build(ctx)
    exterior.build(ctx)
    bpy.context.view_layer.update()
    return scene


def test_exterior_pieces_and_budget():
    scene = build_exterior()
    names = {o.name for o in scene.objects}
    for required in ("Roof_Main", "Roof_Garage", "Roof_Shingles", "Roof_Chimney", "Roof_Gutters", "Roof_Gables", "Facade_Clapboard", "Porch",
                     "Street", "Sidewalks", "StreetFurniture", "Fence", "Yard", "Grass_Tufts", "Playthings", "Trees_Near", "Trees_Far",
                     "Neighbors", "Horizon", "Ground_Grass"):
        assert required in names, required
    meshes = [o for o in scene.objects if o.type == "MESH" and not o.hide_render]
    total = sum(triangles(o) for o in meshes)
    print(f"  exterior e telhado: {total} triângulos em {len(meshes)} malhas")
    assert total <= EXTERIOR_BUDGET, total
    assert not [o for o in scene.objects if o.get(C.P_COL)], "o exterior não colide (só paredes, pisos e proxies colidem)"
    for obj in meshes:
        assert obj.data.materials and all(m is not None for m in obj.data.materials), obj.name


def test_shingles_and_facade_face_outward():
    scene = build_exterior()
    tiles = scene.objects["Roof_Shingles"]
    ups = [p for p in tiles.data.polygons if p.normal.z > 0.2]
    assert len(tiles.data.polygons) > 8000 and len(ups) > len(tiles.data.polygons) * 0.4, "telhas individuais em fiadas"
    facade = scene.objects["Facade_Clapboard"]
    inside = [v for v in facade.data.vertices if v.co.z > 0.3 and layout.room_at(v.co.x, v.co.y, v.co.z, margin=-0.2) is not None]
    assert not inside, f"{len(inside)} vértices de tábua dentro de cômodos"
    deck = scene.objects["Roof_Main"]
    highest = max(v.co.z for v in deck.data.vertices)
    assert abs(highest - layout.ROOF["ridge_z"]) < 0.05


def test_chimney_is_made_of_individual_bricks():
    scene = build_exterior()
    chimney = scene.objects["Roof_Chimney"]
    assert len(chimney.data.polygons) > 3000
    zs = [v.co.z for v in chimney.data.vertices]
    assert max(zs) > 8.3 and min(zs) < -0.3


def test_ambience_pieces_exist():
    scene = build_exterior()
    assert len(exterior.AMBIENCE) >= 12
    names = {o.name for o in scene.objects}
    assert {"Yard", "Playthings", "Porch", "Driveway_Chalk"} <= names


def test_exterior_is_deterministic():
    first = signature(build_exterior())
    second = signature(build_exterior())
    assert first == second


def test_garage_door_moves_and_clips():
    scene, ctx = fresh("world")
    op = layout.OPENINGS["garage_rollup"]

    class Piece:
        thickness = layout.WALL_T_EXT

    garage_door.build(ctx, op, Piece())
    bpy.context.view_layer.update()
    root = scene.objects[C.OBJ_GARAGE_ROLLUP]
    assert root.type == "EMPTY" and root["sa_open_lift"] == 2.3 and root[C.P_ID] == "garage_rollup"
    assert abs(root.location.x - op.mid[0]) < 1e-6 and root.location.z == 0.0
    panels = [child for child in root.children if child.name.startswith("GarageRollup_Panels")]
    assert len(panels) == 1
    body = panels[0]
    xs = [v.co.x for v in body.data.vertices]
    zs = [v.co.z for v in body.data.vertices]
    assert max(xs) <= op.width / 2 + 0.08 and min(xs) >= -op.width / 2 - 0.08, "só as roldanas passam da largura dos painéis"
    assert min(zs) >= -0.01 and abs(max(zs) - op.height) < 0.05, "painéis cobrem o vão de 2,2 m"
    # tudo que sobe com o portão precisa sumir acima do forro (material com mistura transparente)
    for material in body.data.materials:
        kinds = {n.bl_idname for n in material.node_tree.nodes}
        assert "ShaderNodeBsdfTransparent" in kinds, f"{material.name} não some acima do forro"
    for name in ("GarageFrame", "GarageTracks", "GarageSpring", "GarageOpener", "COL_GarageRollup"):
        assert name in scene.objects, name
    assert scene.objects["COL_GarageRollup"].get(C.P_COL)
    assert triangles(body) > 2000, "painéis com relevo, dobradiças e roldanas"


def main():
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print("test_exterior_car: tudo certo")


if __name__ == "__main__":
    main()
