"""Testes do módulo `entity`: modelo, hierarquia do contrato e rig procedural.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_entity_rig.py
"""
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import build, layout  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada import entity  # noqa: E402
from sem_alvorada.entity import model, motion, skeleton  # noqa: E402
from sem_alvorada.entity.rig import EntityRig  # noqa: E402

FRAMES = 300
DT = 1.0 / 60.0
# limites (graus) para a rotação local de cada osso no espaço da armadura; generosos, só pegam dobras absurdas
ANGLE_LIMIT = {"UpperArm": 185, "Forearm": 150, "Thigh": 130, "Shin": 150, "Spine": 75, "Neck": 90,
               "Head": 110, "Hand": 90, "Foot": 80, "Hips": 60, "Shoulder": 40, "Coat": 60}
DEFAULT_LIMIT = 130


def fresh_entity_scene():
    scene = build.fresh_scene()
    ctx = BuildContext(scene, verbose=False)
    ctx.stage = "entity"
    entity.build(ctx)
    bpy.context.view_layer.update()
    return scene


def limit_for(bone_name):
    for prefix, limit in ANGLE_LIMIT.items():
        if bone_name.startswith(prefix):
            return limit
    return DEFAULT_LIMIT


def finite(values):
    return all(math.isfinite(v) for v in values)


def test_hierarchy_and_budget(scene):
    root = scene.objects[C.OBJ_ENTITY]
    assert root.type == "EMPTY"
    children = {c.name: c for c in root.children}
    for name in ("Entity_Rig", "Entity_Body", "Entity_Eyes", "Entity_EyeLight"):
        assert name in children, f"{name} deveria ser filho de Entity"
        assert C.COL_ENTITY in [c.name for c in children[name].users_collection] or name == "Entity_EyeLight"
    assert children["Entity_Rig"].type == "ARMATURE"
    assert children["Entity_EyeLight"].data.type == "POINT"
    assert C.COL_ENTITY in [c.name for c in root.users_collection]
    for mat in ("entity_skin", "entity_cloth", "entity_eye"):
        assert mat in bpy.data.materials, mat
    for tex in ("entity_skin_tex", "entity_cloth_tex"):
        assert bpy.data.images[tex].packed_file is not None, f"{tex} precisa estar empacotada"
        assert bpy.data.images[tex].size[0] <= 128
    for name in ("Entity_Body", "Entity_Eyes"):
        assert any(m.type == "ARMATURE" and m.object == children["Entity_Rig"]
                   for m in children[name].modifiers), name
    tris = model.triangle_count(children["Entity_Body"]) + model.triangle_count(children["Entity_Eyes"])
    assert tris <= 8000, f"{tris} triângulos (limite 8000)"
    print(f"  hierarquia ok, {tris} triângulos, {len(skeleton.BONES)} ossos")


def test_proportions(scene):
    body = scene.objects["Entity_Body"]
    coords = [v.co for v in body.data.vertices]
    top = max(v.z for v in coords)
    bottom = min(v.z for v in coords)
    assert abs(top - C.ENTITY_HEIGHT) < 0.03, f"altura {top:.3f} m"
    assert bottom > -0.005 and bottom < 0.01, f"pés fora do chão: {bottom:.3f}"
    assert top > layout.DOOR_H * 1.25, "precisa ser bem mais alto que uma porta"
    finger_groups = {g.index for g in body.vertex_groups if g.name.startswith(skeleton.FINGER_NAMES)}
    hand_tip = min(v.co.z for v in body.data.vertices if any(g.group in finger_groups for g in v.groups))
    assert 0.25 < hand_tip < 0.7, f"mãos deveriam chegar à altura dos joelhos, fim em z={hand_tip:.2f}"
    knee_z = skeleton.KNEE_Z
    assert hand_tip < knee_z + 0.05
    print(f"  altura {top:.2f} m, pontas dos dedos em z={hand_tip:.2f} (joelho {knee_z:.2f})")


def sample_bounds(rig):
    """Confere cada junta do quadro atual: finita e dentro de uma caixa plausível."""
    solution = rig.motion.last
    for name, head in solution.head.items():
        assert finite(head), f"{name} com NaN"
        assert abs(head.x) < 2.2 and abs(head.y) < 2.4 and -0.05 < head.z < 3.1, f"{name} em {tuple(head)}"
    for name, q in solution.local.items():
        assert finite(q), f"{name} quaternion com NaN"
        angle = math.degrees(q.angle)
        assert angle <= limit_for(name), f"{name} girou {angle:.0f} graus (limite {limit_for(name)})"
    for foot in skeleton.foot_bones():
        assert skeleton.sole_height(solution, foot) > -0.02, f"{foot} afundou no chão"
    for side in ("L", "R"):
        assert solution.tail(f"Forearm.{side}").z > -0.03, "mão atravessou o chão"
    for b in skeleton.BONES:                       # membros rígidos: comprimento nunca muda
        if b.parent is None:
            continue
        parent = skeleton.bone(b.parent)
        offset = (solution.head[b.name] - solution.head[b.parent]).length
        assert abs(offset - (b.head - parent.head).length) < 1e-3, f"{b.name} esticou"


def test_all_animations(scene):
    rig = EntityRig(scene)
    rig.set_transform(3.0, 4.0, 0.0, 0.7)
    rig.set_visible(True)
    for anim in motion.ANIMATIONS:
        rig.set_anim(anim)
        for frame in range(FRAMES):
            speed = None if frame % 97 else 0.0            # de vez em quando o passo para
            rig.update(DT, speed)
            sample_bounds(rig)
            head = rig.head_position()
            assert finite(head) and 0.4 < head[2] < 2.8, f"{anim}: cabeça em {head}"
            top = rig.motion.last.tail("Head").z + rig.position.z
            assert top <= rig.head_limit + 0.03 + rig.position.z, f"{anim}: a cabeça passou do forro ({top:.2f} m)"
        print(f"  {anim}: {FRAMES} quadros ok")
    rig.set_anim("run")
    for _ in range(120):
        rig.update(DT, 4.1)
    # velocidades absurdas não quebram nada
    for speed in (0.0, 0.01, 12.0, 100.0):
        rig.update(DT, speed)
        sample_bounds(rig)


def test_stoops_indoors_and_stands_tall_outside(scene):
    rig = EntityRig(scene)
    rig.set_transform(0.0, 0.0, 0.0, 0.0)
    rig.set_visible(True)
    rig.set_anim("idle")
    for _ in range(60):
        rig.update(DT)
    indoor = rig.motion.last.tail("Head").z
    assert indoor <= motion.INDOOR_HEAD_LIMIT + 0.02, indoor
    assert indoor < layout.CEIL_Z[0] - 0.1, "a cabeça precisa ficar sob o forro de 2,6 m"
    rig.head_limit = None                                 # na estrada do final ele se ergue inteiro
    for _ in range(60):
        rig.update(DT)
    outdoor = rig.motion.last.tail("Head").z
    assert outdoor > 2.5, f"ereto deveria passar de 2,5 m: {outdoor:.2f}"
    rig.head_limit = motion.INDOOR_HEAD_LIMIT
    print(f"  curvado dentro de casa ({indoor:.2f} m) e ereto fora ({outdoor:.2f} m)")


def test_pose_matches_blender(scene):
    """A cinemática do módulo tem de coincidir com a avaliada pelo Blender (conjugação B = R^-1 Q R)."""
    rig = EntityRig(scene)
    rig.set_transform(2.0, -1.0, 0.0, 1.1)
    rig.set_visible(True)
    for anim in ("stalk", "run", "attack", "twitch"):
        rig.set_anim(anim)
        for _ in range(90):
            rig.update(DT)
        bpy.context.view_layer.update()
        worst = 0.0
        for name in ("Head", "Hand.R", "Hand.L", "Shin.R", "Foot.L", "Forearm.L", "Spine3", "FingerTip" if False else "IndexB.R"):
            expected = rig.joint_world(name)
            evaluated = rig.armature.matrix_world @ rig.armature.pose.bones[name].head
            worst = max(worst, (expected - evaluated).length)
        assert worst < 0.01, f"{anim}: diferença de {worst * 100:.1f} cm entre cinemática e Blender"
        print(f"  {anim}: cinemática = Blender (erro {worst * 1000:.2f} mm)")


def follow(rig, point, frames):
    """Renova o look_at todo quadro, como o cérebro e as cutscenes fazem."""
    for _ in range(frames):
        rig.look_at(*point)
        rig.update(DT)


def test_look_at(scene):
    rig = EntityRig(scene)
    rig.set_transform(0.0, 0.0, 0.0, 0.0)
    rig.set_visible(True)
    rig.set_anim("stare")
    behind = (0.0, -6.0, 1.6)                             # atrás dele: limitado
    rig.look_at(*behind)
    rig.update(DT)
    assert abs(rig.look_angles[0]) <= rig.look_rate * DT + 1e-6, "a cabeça girou rápido demais"
    follow(rig, behind, 240)
    yaw, pitch = rig.look_angles
    assert abs(yaw) <= motion.LOOK_LIMIT_YAW + 1e-6, yaw
    assert motion.LOOK_LIMIT_PITCH_UP >= pitch >= -motion.LOOK_LIMIT_PITCH_DOWN
    follow(rig, (4.0, 4.0, 1.7), 240)                     # pela direita dele (+X)
    yaw, _ = rig.look_angles
    assert -60 < yaw < -30, f"deveria olhar ~45 graus para a direita (guinada negativa): {yaw:.1f}"
    rig.look_rate = 40.0                                  # cutscenes podem pedir uma virada lenta
    follow(rig, (-4.0, 4.0, 1.7), 30)
    assert rig.look_angles[0] < 0 and rig.look_angles[0] > -60 + 40 * 0.5 + 1, "a virada lenta respeita look_rate"
    rig.look_rate = 220.0
    for _ in range(120):                                  # sem renovar, o olhar expira e a cabeça relaxa
        rig.update(DT)
    assert rig.motion.look_weight < 0.01, "o olhar deveria expirar sem renovação"
    rig.look_at(4.0, 4.0, 1.7)
    rig.look_at(None)
    rig.update(DT)
    assert rig.motion.look_weight <= 1.0
    print("  olhar limitado, suave, com taxa ajustável e que expira")


def test_eyes_visibility_transform(scene):
    rig = EntityRig(scene)
    light = scene.objects["Entity_EyeLight"]
    rig.set_visible(False)
    assert not rig.visible and scene.objects["Entity_Body"].hide_viewport
    rig.set_visible(True)
    assert rig.visible and not scene.objects["Entity_Body"].hide_render
    rig.eyes(0.0)
    assert light.data.energy == 0.0
    rig.eyes(1.0)
    assert light.data.energy > 5.0
    mat = bpy.data.materials["entity_eye"]
    strength = mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value
    assert strength > 5.0, strength
    rig.eyes(7.0)                                         # acima do limite: satura em 1
    assert rig.eye_level == 1.0
    rig.set_transform(5.0, 6.0, 2.8, math.pi / 2)
    root = scene.objects[C.OBJ_ENTITY]
    assert tuple(round(v, 3) for v in root.location) == (5.0, 6.0, 2.8)
    assert abs(root.rotation_euler.z - math.pi / 2) < 1e-6
    for _ in range(30):
        rig.update(DT)
    x, y, z = rig.head_position()
    assert abs(x - 5.0) < 0.5 and abs(y - 6.0) < 0.5 and 2.8 + 2.0 < z < 2.8 + 2.8, (x, y, z)
    rig.set_visible(False)
    rig.update(DT)                                        # oculto: não faz nada, mas não quebra
    print("  olhos, visibilidade e transform ok")


def test_death_pose(scene):
    rig = EntityRig(scene)
    rig.set_visible(True)
    eye = Vector((10.0, 4.0, 1.65))
    rig.set_transform(10.0, 6.0, 0.0, math.pi)
    rig.set_anim("attack")
    for _ in range(40):
        rig.update(DT)
    for step in range(0, 11):
        rig.pose_for_death(tuple(eye), step / 10.0)
        rig.update(DT)
        sample_bounds(rig)
    head = Vector(rig.head_position())
    assert abs(head.z - eye.z) < 0.12, f"rosto deveria estar na altura dos olhos: {head.z:.2f} x {eye.z:.2f}"
    horizontal = math.hypot(head.x - eye.x, head.y - eye.y)
    assert 0.25 < horizontal < 0.6, f"rosto a {horizontal:.2f} m da câmera"
    hand = rig.joint_world("Hand.R")
    assert (hand - eye).length < 1.0, "as mãos deveriam alcançar o jogador"
    print(f"  agarrão: rosto a {horizontal:.2f} m, altura {head.z:.2f} m")
    rig.set_anim("idle")                                  # sair do modo de morte
    rig.update(DT)


def test_update_cost(scene):
    rig = EntityRig(scene)
    rig.set_visible(True)
    rig.set_anim("run")
    for _ in range(30):
        rig.update(DT)
    start = time.perf_counter()
    for _ in range(300):
        rig.update(DT, 4.1)
    per_frame_ms = (time.perf_counter() - start) / 300 * 1000
    assert per_frame_ms < 8.0, f"update lento: {per_frame_ms:.2f} ms"
    print(f"  update: {per_frame_ms:.2f} ms por quadro")


def test_bad_inputs(scene):
    rig = EntityRig(scene)
    try:
        rig.set_anim("voar")
    except ValueError:
        pass
    else:
        raise AssertionError("animação inválida deveria levantar ValueError")
    rig.set_anim("idle")
    rig.update(0.0)
    rig.update(0.5)
    sample_bounds(rig)


def main():
    scene = fresh_entity_scene()
    tests = [test_hierarchy_and_budget, test_proportions, test_all_animations, test_stoops_indoors_and_stands_tall_outside,
             test_pose_matches_blender,
             test_look_at, test_eyes_visibility_transform, test_death_pose, test_update_cost, test_bad_inputs]
    for fn in tests:
        print(fn.__name__)
        fn(scene)
    print("test_entity_rig: OK")


if __name__ == "__main__":
    main()
