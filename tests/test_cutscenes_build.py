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

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import build, cutscenes, entity, layout  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.cutscenes import player as player_module  # noqa: E402
from sem_alvorada.cutscenes import preview, scripts, timeline  # noqa: E402


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
    return scene


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
    assert len(clock.data.polygons) < 120
    lights = [o for o in scene.objects if o.type == "LIGHT" and not o.hide_render]
    assert lights == [], "as luzes de cutscene nascem apagadas e ocultas"
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


def main():
    scene = fresh_scene()
    test_objects(scene)
    test_cabin_light_follows_the_car(scene)
    test_camera_convention(scene)
    test_look_angles_roundtrip()
    test_run_all_in_blender(scene)
    test_skip_in_blender(scene)
    print("test_cutscenes_build: OK")


if __name__ == "__main__":
    main()
