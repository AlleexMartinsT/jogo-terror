"""Testes das cutscenes dentro do Blender: objetos criados, convenção da câmera e execução ponta a ponta.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_cutscenes_build.py

Usa a etapa `entity` de verdade e o `PreviewHost` (um engine de mentira) sobre uma cena sem casa:
basta para provar que o player fala bem com objetos reais do Blender (luzes, câmera, rig).
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import time  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import build, cutscenes, entity, layout  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.cutscenes import anim, camera, objects, preview, scripts, timeline  # noqa: E402
from sem_alvorada.cutscenes import player as player_module  # noqa: E402
from sem_alvorada.cutscenes.stage import Stage  # noqa: E402


LIGHTS = (scripts.CLOCK_GLOW, scripts.BED_LAMP, scripts.DAWN_LIGHT, scripts.ROAD_LIGHT, scripts.CORRIDOR_RIM,
          scripts.DRIVEWAY_LIGHT, scripts.CAR_CABIN)


def fresh_scene():
    scene = build.fresh_scene()
    ctx = BuildContext(scene, verbose=False)
    car = layout.ANCHORS["car"]                     # o módulo props cria o Car; aqui basta um Empty no mesmo lugar
    car_root = bpy.data.objects.new(C.OBJ_CAR, None)
    car_root.location, car_root.rotation_euler = (car.x, car.y, car.z), (0.0, 0.0, math.radians(car.yaw_deg))
    scene.collection.objects.link(car_root)
    for stage, module in (("entity", entity), ("cutscenes", cutscenes)):
        ctx.stage = stage
        module.build(ctx)
    bpy.context.view_layer.update()
    return scene, ctx


def test_objects(scene):
    cam = scene.objects[C.OBJ_CUT_CAM]
    assert cam.type == "CAMERA" and cam.data.sensor_fit == "HORIZONTAL"
    assert C.COL_CUTSCENE in [c.name for c in cam.users_collection]
    for name in LIGHTS:
        light = scene.objects[name]
        assert light.type == "LIGHT" and light.data.energy == 0.0 and light.hide_render, name
        assert name.startswith("CutLight_")
    clock = scene.objects[scripts.END_CLOCK]
    assert clock.hide_render and clock.hide_viewport
    assert sum(len(p.vertices) - 2 for p in clock.data.polygons) < C.BUDGET_TRIS["prop"]
    lights = [o for o in scene.objects if o.type == "LIGHT" and not o.hide_render]
    assert lights == [], "as luzes de cutscene nascem apagadas e ocultas"
    for name in (objects.OBJ_DUST, objects.OBJ_SPARKS, objects.OBJ_KEY, objects.OBJ_CHARM, objects.OBJ_LID_TOP,
                 objects.OBJ_LID_BOTTOM):
        assert scene.objects[name].hide_render, f"{name} nasce oculto"
    assert len(scene.objects[objects.OBJ_DUST].data.vertices) == 4 * objects.DUST_PARTICLES
    assert scene.objects[objects.OBJ_LID_TOP].parent == cam and scene.objects[objects.OBJ_LID_BOTTOM].parent == cam
    assert scene.objects[objects.OBJ_CHARM].parent == scene.objects[objects.OBJ_KEY]
    tris = sum(len(p.vertices) - 2 for n in (objects.OBJ_KEY, objects.OBJ_CHARM) for p in scene.objects[n].data.polygons)
    assert tris < 6000, "chave e chaveiro cabem nos 6 mil triângulos de itens na mão"
    print("  objetos de cutscene criados, ocultos e apagados")


def test_cabin_light_follows_the_car(scene):
    """A luz da cabine nasce parentada ao Car sem sair do lugar, e anda junto com ele."""
    cabin = scene.objects[scripts.CAR_CABIN]
    car = scene.objects[C.OBJ_CAR]
    anchor = layout.ANCHORS["car"]
    cabin.hide_viewport = False                     # objetos ocultos não entram na avaliação do depsgraph
    bpy.context.view_layer.update()
    expected = Vector((anchor.x + 0.45, anchor.y + 1.10, 1.35))
    assert cabin.parent == car
    assert (cabin.matrix_world.translation - expected).length < 1e-4, tuple(cabin.matrix_world.translation)
    car.location.y -= 5.0
    bpy.context.view_layer.update()
    assert abs(cabin.matrix_world.translation.y - (expected.y - 5.0)) < 1e-4
    car.location.y += 5.0
    cabin.hide_viewport = True
    bpy.context.view_layer.update()
    print("  luz da cabine acompanha o carro")


def test_camera_convention(scene):
    """camera_quaternion tem de fazer a câmera olhar exatamente para onde (yaw, pitch) mandam."""
    cam = scene.objects[C.OBJ_CUT_CAM]
    cam.rotation_mode = "QUATERNION"
    for yaw_deg in (-170, -90, 0, 35, 90, 180):
        for pitch_deg in (-40, 0, 25, 60):
            yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
            cam.rotation_quaternion = player_module.camera_quaternion(yaw, pitch, 0.0)
            bpy.context.view_layer.update()
            basis = cam.matrix_world.to_3x3()
            view = basis @ Vector((0, 0, -1))
            dx, dy = C.yaw_dir(yaw)
            expected = Vector((dx * math.cos(pitch), dy * math.cos(pitch), math.sin(pitch)))
            assert (view - expected).length < 1e-5, (yaw_deg, pitch_deg, tuple(view), tuple(expected))
            up = basis @ Vector((0, 1, 0))
            assert up.z > 0, "a câmera não pode estar de cabeça para baixo"
    rolled = player_module.camera_quaternion(0.0, 0.0, math.radians(10))
    cam.rotation_quaternion = rolled
    bpy.context.view_layer.update()
    tilt = (cam.matrix_world.to_3x3() @ Vector((0, 1, 0))).x
    assert abs(abs(tilt) - math.sin(math.radians(10))) < 1e-5, "roll gira em torno do eixo de visão"
    print("  convenção yaw/pitch/roll igual à dos yaws do jogo")


def test_look_angles_roundtrip():
    eye = (2.0, 3.0, 1.5)
    for target in ((5.0, 3.0, 1.5), (2.0, 9.0, 4.0), (-1.0, -2.0, 0.2)):
        yaw, pitch = player_module.look_angles(eye, target)
        dx, dy = C.yaw_dir(yaw)
        direction = Vector((dx * math.cos(pitch), dy * math.cos(pitch), math.sin(pitch)))
        want = (Vector(target) - Vector(eye)).normalized()
        assert (direction - want).length < 1e-6


def test_run_all_in_blender(scene):
    for name in scripts.NAMES:
        start = preview.START_STATE[name]
        host = preview.PreviewHost(scene, start)
        player = cutscenes.CutscenePlayer(host)
        player.play(name)
        assert scene.camera == scene.objects[C.OBJ_CUT_CAM]
        cam = scene.objects[C.OBJ_CUT_CAM]
        while player.active:
            player.update(1 / 30)
            host.tick(1 / 30)
            if player.active:
                assert all(math.isfinite(v) for v in cam.location)
                assert 20 < math.degrees(cam.data.angle) < 100
        expected = timeline.compile_cutscene(scripts.get(name)).total
        assert host.finished == [scripts.get(name).reason]
        # as ações só podem falhar por falta de casa/carro, nunca por erro de API
        allowed = ("get_object(Car)", "get_object(GarageRollup)", "get_object(Car_Headlight", "get_object(Door_")
        unexpected = [e for e in player.errors if not any(a in e for a in allowed)]
        assert unexpected == [], (name, unexpected)
        for light in LIGHTS:
            assert scene.objects[light].data.energy == 0.0, (name, light)
        assert scene.objects[scripts.END_CLOCK].hide_render, "o relógio do final volta a ficar oculto"
        for lid in (objects.OBJ_LID_TOP, objects.OBJ_LID_BOTTOM):
            assert scene.objects[lid].hide_render, "as pálpebras voltam a ficar ocultas"
        assert scene.objects[objects.OBJ_DUST].hide_render and scene.objects[objects.OBJ_SPARKS].hide_render
        print(f"  {name}: {expected:.1f} s de cutscene rodaram no Blender sem erro")
        host.entity.set_visible(False)


def test_skip_in_blender(scene):
    for name in scripts.NAMES:
        host = preview.PreviewHost(scene, preview.START_STATE[name])
        player = cutscenes.CutscenePlayer(host)
        player.play(name)
        player.update(2.0)
        player.skip()
        assert host.finished == [scripts.get(name).reason]
        host.entity.set_visible(False)
    print("  skip em objetos reais ok")


def test_lens_and_depth_of_field_on_a_real_camera(scene):
    """FOV, foco e diafragma chegam à câmera de verdade (mesma API `camera.data.dof` no Blender 4.2 e no 5.0)."""
    cam = scene.objects[C.OBJ_CUT_CAM]
    state = camera.CameraState((0, 0, 0), 0.0, 0.0, 0.0, 50.0, 1.7, 2.8, 1.7)
    camera.apply_lens(cam, state)
    assert abs(math.degrees(cam.data.angle) - 50.0) < 1e-4
    assert cam.data.dof.use_dof and abs(cam.data.dof.focus_distance - 1.7) < 1e-5 and abs(cam.data.dof.aperture_fstop - 2.8) < 1e-5
    state.focus = None
    camera.apply_lens(cam, state)
    assert not cam.data.dof.use_dof
    print(f"  FOV e profundidade de campo na câmera do Blender {bpy.app.version_string}")


def test_body_eye_offsets_match_the_body_solver():
    """`body_actor.EYE_LOCAL` (onde ficam os olhos em cada pose) ainda bate com `body.solver` + `body.poses`."""
    from sem_alvorada.body import poses, solver
    from sem_alvorada.body import skeleton as S
    from sem_alvorada.cutscenes import body_actor
    rest_eye = S.BONE_MAP["Neck"].head + S.EYE_FROM_C7
    for name, expected in body_actor.EYE_LOCAL.items():
        data = poses.pose_data(name)
        solution = solver.solve(solver.PoseSpec(hips_shift=data["shift"], rot=data["rot"]))
        eye = solution.point_on("Neck", rest_eye)
        assert (eye - Vector(expected)).length < 0.01, (name, tuple(eye), expected)
    print("  olhos de cada pose do corpo coincidem com o solver do corpo")


def curtain_mesh(name, columns=64, rows=60):
    """Cortina de ~3,9 mil vértices como as do jogo (largura em X, altura em Z, depth em Y negativo)."""
    mesh = bpy.data.meshes.new(name)
    xs, zs = np.linspace(-1.5, 1.5, columns), np.linspace(-1.46, 0.8, rows)
    verts = [(x, -0.2 + 0.05 * math.sin(x * 9.0), z) for z in zs for x in xs]
    faces = [(r * columns + c, r * columns + c + 1, (r + 1) * columns + c + 1, (r + 1) * columns + c)
             for r in range(rows - 1) for c in range(columns - 1)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


class _Host:
    """O mínimo que o Stage pede para rodar atores sobre objetos reais."""

    def __init__(self, scene):
        self.scene = scene

    def get_object(self, name):
        return bpy.data.objects.get(name)

    def player_state(self):
        return (0.0, 0.0, 0.0, 0.0, 1.65)


def test_object_animation_cost_in_blender(scene):
    """Cortinas (3 x 3,8 mil vértices), poeira, faíscas, carro e pêndulos juntos: média por quadro < 3 ms."""
    names = ("Curtain_w_master_n", "Curtain_w_master_w", "Curtain_w_kids_w")
    originals = {}
    for name in names:
        obj = curtain_mesh(name)
        originals[name] = np.array([tuple(v.co) for v in obj.data.vertices], np.float32)
    stage = Stage(_Host(scene))
    stage.start_actor("curtains", anim.CurtainWind(names, 1.0))
    stage.start_actor("dust", anim.DustFall((6.0, 5.0), 1.5, 2.6, 0.0, 0.0, 1.0))
    stage.start_actor("sparks", anim.SparkBurst((6.0, 5.0, 2.5), 0.0))
    stage.start_actor("car", anim.CarMotion((15.5, 3.0, 0.0), (15.5, -5.0, -0.054), 0.5, 6.0, crank_start=0.0, catch=1.0))
    stage.start_actor("bunny", anim.CharmPendulum(objects.OBJ_BUNNY if bpy.data.objects.get(objects.OBJ_BUNNY) else "Cut_Key"))
    stage.start_actor("rollup", anim.GarageLift(0.5, 3.0))
    stage.start_actor("wheel", anim.SteeringWheel())
    assert stage.errors == [], stage.errors
    costs = []
    for frame in range(240):
        stage.t = frame / 60.0
        started = time.perf_counter()
        stage.update_actors(1 / 60)
        costs.append(time.perf_counter() - started)
    assert stage.errors == [], stage.errors
    mean_ms, peak_ms = 1000.0 * sum(costs) / len(costs), 1000.0 * max(costs)
    print(f"  atores com malhas reais: {mean_ms:.2f} ms por quadro em média (pico {peak_ms:.2f} ms)")
    assert mean_ms < 3.0, mean_ms
    moved = max(float(np.abs(np.array([tuple(v.co) for v in bpy.data.objects[n].data.vertices]) - originals[n]).max()) for n in names)
    assert 0.02 < moved < 0.5, moved
    stage.finish_up()
    for name in names:
        restored = np.array([tuple(v.co) for v in bpy.data.objects[name].data.vertices], np.float32)
        assert np.allclose(restored, originals[name], atol=1e-6), name
        bpy.data.objects.remove(bpy.data.objects[name])


def test_car_parts_are_split_from_the_body(scene, ctx):
    """O coelhinho e o volante saem de `Car_Body` com as mesmas faces e o pivô no lugar."""
    from sem_alvorada.props import car_interior, kit
    kit.set_quality("medium")
    car_root = bpy.data.objects[C.OBJ_CAR]
    body_mesh = car_interior.build_interior().to_mesh("Car_Body")
    body = bpy.data.objects.new("Car_Body", body_mesh)
    body.parent = car_root
    bpy.context.scene.collection.objects.link(body)
    before = sum(len(p.vertices) - 2 for p in body_mesh.polygons)
    objects.split_car_parts(ctx)
    bunny, wheel = bpy.data.objects.get(objects.OBJ_BUNNY), bpy.data.objects.get(objects.OBJ_WHEEL)
    assert bunny is not None and wheel is not None
    tris = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (body, bunny, wheel)}
    assert sum(tris.values()) == before, (tris, before)
    assert tris[objects.OBJ_BUNNY] > 100 and tris[objects.OBJ_WHEEL] > 300
    assert bunny.parent == car_root and (Vector(bunny.location) - Vector(objects.BUNNY_PIVOT)).length < 1e-6
    hub = Vector(car_interior.WHEEL_HUB)
    assert (Vector(wheel.location) - hub).length < 1e-6
    centre = sum((Vector(v.co) for v in wheel.data.vertices), Vector()) / len(wheel.data.vertices)
    assert centre.length < 0.12, "o volante está centrado no pivô (o cubo)"
    assert max(v.co.z for v in bunny.data.vertices) < 0.01, "a linha do coelhinho nasce no pivô e o resto pende abaixo"
    objects.split_car_parts(ctx)                                   # idempotente: não separa duas vezes
    assert sum(len(p.vertices) - 2 for p in body.data.polygons) == before - tris[objects.OBJ_BUNNY] - tris[objects.OBJ_WHEEL]
    print(f"  coelhinho ({tris[objects.OBJ_BUNNY]} tri) e volante ({tris[objects.OBJ_WHEEL]} tri) separados do carro sem perder faces")


def main():
    scene, ctx = fresh_scene()
    test_objects(scene)
    test_cabin_light_follows_the_car(scene)
    test_camera_convention(scene)
    test_look_angles_roundtrip()
    test_lens_and_depth_of_field_on_a_real_camera(scene)
    test_object_animation_cost_in_blender(scene)
    test_car_parts_are_split_from_the_body(scene, ctx)
    test_body_eye_offsets_match_the_body_solver()
    test_run_all_in_blender(scene)
    test_skip_in_blender(scene)
    print("test_cutscenes_build: OK")


if __name__ == "__main__":
    main()
