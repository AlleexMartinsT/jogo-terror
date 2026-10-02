"""Testes do corpo do jogador (pacote `sem_alvorada/body`): armadura, malha, locomoção, IK, dedos, poses, contrato.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_body.py
"""
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Euler, Matrix, Quaternion, Vector  # noqa: E402

from sem_alvorada import body, build  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.body import fingers as F  # noqa: E402
from sem_alvorada.body import skeleton as S  # noqa: E402
from sem_alvorada.body import solver as V  # noqa: E402
from sem_alvorada.body.locomotion import Locomotion  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.engine.fallbacks import NullArm, NullBody  # noqa: E402

DT = 1.0 / 60.0
TRIANGLE_BUDGET = 30_000
CLIP_START = 0.05
EXPECTED_BONES = (["Hips", "Spine1", "Spine2", "Spine3", "Neck"]
                  + [f"{b}.{s}" for s in "LR" for b in ("Clavicle", "UpperArm", "Forearm", "Hand", "Thigh", "Shin", "Foot")]
                  + [f"{f}{i}.{s}" for s in "LR" for f in ("Index", "Middle", "Ring", "Pinky") for i in (1, 2, 3)]
                  + [f"Thumb{i}.{s}" for s in "LR" for i in (0, 1, 2)])


class FakePlayer:
    """O que o BodyRig lê de engine.player.Player."""

    def __init__(self):
        self.x = self.y = self.z_visual = 0.0
        self.yaw = self.pitch = 0.0
        self.speed = 0.0
        self.running = False
        self.crouching = False
        self.eye = C.PLAYER_EYE_STAND
        self.stride_phase = 0.0
        self.breathing_hard = False

    def camera_pose(self, bob=(0.0, 0.0)):
        lateral, vertical = bob
        position = (self.x + math.cos(self.yaw) * lateral, self.y + math.sin(self.yaw) * lateral,
                    self.z_visual + self.eye + vertical)
        return position, (math.pi / 2 + self.pitch, lateral * 0.35, self.yaw)

    def walk(self, dt, speed=2.6, running=False):
        """Anda `dt` segundos para a frente (cada pi de fase é um passo)."""
        stride = 1.6 if running else 1.15
        self.speed, self.running = speed, running
        self.x += -math.sin(self.yaw) * speed * dt
        self.y += math.cos(self.yaw) * speed * dt
        self.stride_phase += speed * dt / stride * math.pi


def fresh_scene():
    scene = build.fresh_scene()
    ctx = BuildContext(scene, verbose=False)
    ctx.stage = "body"
    body.build(ctx)
    bpy.context.view_layer.update()
    return scene


def settle(rig, player, seconds, running=False, speed=2.6, bob=(0.0, 0.0)):
    for _ in range(int(seconds / DT)):
        if speed > 0:
            player.walk(DT, speed, running)
        else:
            player.speed = 0.0
        rig.update(DT, player, bob)


# --------------------------------------------------------------------------
def test_objects_and_budget(scene):
    rig_obj, mesh_obj = scene.objects[C.OBJ_BODY_RIG], scene.objects[C.OBJ_BODY]
    assert rig_obj.type == "ARMATURE" and mesh_obj.type == "MESH"
    assert mesh_obj.parent is rig_obj
    for obj in (rig_obj, mesh_obj):
        assert [c.name for c in obj.users_collection] == [C.COL_PLAYER], obj.name
        assert not obj.name.startswith(C.N_COL)
        assert C.P_INTERACT not in obj and C.P_COL not in obj, "o corpo não pode virar colisão nem alvo"
    assert any(m.type == "ARMATURE" and m.object is rig_obj for m in mesh_obj.modifiers)
    names = {b.name for b in rig_obj.data.bones}
    missing = [b for b in EXPECTED_BONES if b not in names]
    assert not missing, f"ossos ausentes: {missing}"
    for side in "LR":
        fingers = [n for n in names if n.endswith("." + side) and n.startswith(("Index", "Middle", "Ring", "Pinky", "Thumb"))]
        assert len(fingers) == 15, f"{side}: {len(fingers)} ossos de dedo (esperado 5 dedos x 3)"
    tris = sum(len(p.vertices) - 2 for p in mesh_obj.data.polygons)
    assert tris <= TRIANGLE_BUDGET, f"{tris} triângulos (limite {TRIANGLE_BUDGET})"
    for material in mesh_obj.data.materials:
        for node in material.node_tree.nodes:
            if node.bl_idname == "ShaderNodeTexImage" and node.image:
                assert max(node.image.size) <= 512 or node.image.size[0] * node.image.size[1] <= 512 * 512, node.image.name
                assert node.interpolation == "Linear", f"{material.name}: filtro {node.interpolation}"
    print(f"  {tris} triângulos, {len(names)} ossos")


def test_weights(scene):
    mesh = scene.objects[C.OBJ_BODY].data
    bad_sum, orphans = [], 0
    for vertex in mesh.vertices:
        if not vertex.groups:
            orphans += 1
            continue
        total = sum(g.weight for g in vertex.groups)
        if abs(total - 1.0) > 0.02:
            bad_sum.append((vertex.index, round(total, 3)))
    assert orphans == 0, f"{orphans} vértices sem peso"
    assert not bad_sum, f"{len(bad_sum)} vértices com soma de pesos != 1, ex.: {bad_sum[:3]}"


def test_parity_with_null_body(scene):
    rig = body.BodyRig(scene)
    public = lambda cls: {n for n in dir(cls) if not n.startswith("_")}      # noqa: E731
    assert public(body.BodyRig) == public(NullBody), (public(body.BodyRig) ^ public(NullBody))
    assert public(type(rig.arm("R"))) == public(NullArm), (public(type(rig.arm("R"))) ^ public(NullArm))
    assert rig.arm("L") is not rig.arm("R") and rig.arm("R").ready is True and NullArm.ready is False
    assert rig.arm("R").hand_world_position() is not None


def test_pose_matches_blender(scene):
    """O que o solver calcula é o que a armadura mostra (conjugação das rotações de repouso correta)."""
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    rig.arm("R").set_target((0.18, -0.10, -0.45), (10, 20, 60), 1.0)
    rig.arm("L").set_target((-0.15, -0.18, -0.38), (0, 0, -30), 0.7)
    rig.arm("R").set_fingers(F.PRESETS["fist"][0])
    player.pitch = math.radians(-20)
    settle(rig, player, 0.8)
    bpy.context.view_layer.update()
    armature = scene.objects[C.OBJ_BODY_RIG]
    worst = 0.0
    for name in ("Hand.R", "Hand.L", "Index3.R", "Thumb2.L", "Shin.R", "Spine3", "Forearm.L", "ForearmRoll.R"):
        expected = rig._solution.head[S.BONE_INDEX[name]]
        actual = armature.pose.bones[name].head
        worst = max(worst, (expected - actual).length)
    assert worst < 2e-4, f"solver e Blender divergem {worst * 1000:.3f} mm"
    print(f"  divergência máxima solver x Blender: {worst * 1000:.4f} mm")


def test_arm_ik_reaches_target(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    player.x, player.y, player.yaw = 3.0, -2.0, math.radians(35)
    for side, sign in (("R", 1), ("L", -1)):
        arm = rig.arm(side)
        for target, rotation in (((0.18 * sign, -0.12, -0.42), (0, 0, 0)), ((0.10 * sign, -0.05, -0.30), (0, 0, 70 * sign)),
                                 ((0.22 * sign, 0.0, -0.45), (-30, 0, 0)), ((0.12 * sign, -0.30, -0.35), (20, 40, 0))):
            arm.set_target(target, rotation, 1.0)
            settle(rig, player, 0.3, speed=0.0)
            position, euler = player.camera_pose()
            cam_matrix = Euler(euler, "XYZ").to_matrix()
            want = Vector(position) + cam_matrix @ Vector(target)
            got = Vector(arm.hand_world_position())
            assert (want - got).length < 0.005, (side, target, round((want - got).length, 4))
        arm.set_target((0.5 * sign, 0.4, -2.0), (0, 0, 0), 1.0)           # longe demais: o braço esticado não passa do alcance
        settle(rig, player, 0.3, speed=0.0)
        shoulder = rig._root + Matrix.Rotation(rig._yaw, 3, "Z") @ rig._solution.head[S.BONE_INDEX[f"UpperArm.{side}"]]
        wrist = rig._root + Matrix.Rotation(rig._yaw, 3, "Z") @ rig._solution.head[S.BONE_INDEX[f"Hand.{side}"]]
        reach = S.BONE_MAP[f"UpperArm.{side}"].length + S.BONE_MAP[f"Forearm.{side}"].length + S.BONE_MAP[f"ForearmRoll.{side}"].length
        assert (wrist - shoulder).length <= reach + 1e-3, "o braço esticou além do próprio comprimento"
        arm.release()
        settle(rig, player, 0.1, speed=0.0)
        assert arm._weight == 0.0 and not arm._has_target


def test_arm_weight_blends(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    arm = rig.arm("R")
    settle(rig, player, 0.3, speed=0.0)
    free = Vector(arm.hand_world_position())
    arm.set_target((0.18, -0.10, -0.45), (0, 0, 0), 1.0)
    settle(rig, player, 0.2, speed=0.0)
    full = Vector(arm.hand_world_position())
    arm.set_target((0.18, -0.10, -0.45), (0, 0, 0), 0.5)
    settle(rig, player, 0.2, speed=0.0)
    half = Vector(arm.hand_world_position())
    assert (free - full).length > 0.4
    assert 0.1 < (half - free).length < (full - free).length - 0.05, "weight intermediário deve ficar entre as duas poses"


def test_arms_swing_when_free(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    settle(rig, player, 0.8)
    samples = []
    for _ in range(90):
        player.walk(DT)
        rig.update(DT, player)
        samples.append(rig._solution.head[S.BONE_INDEX["Hand.R"]].y - rig._solution.head[S.BONE_INDEX["Hand.L"]].y)
    assert max(samples) > 0.1 and min(samples) < -0.1, "os braços soltos devem balançar em oposição"


def test_gait_periodic_and_symmetric():
    loco = Locomotion()
    player = FakePlayer()
    for _ in range(120):
        player.walk(DT)
        loco.step(DT, player, (0.0, 0.0))
    base = player.stride_phase

    def feet(phase):
        player.stride_phase = phase
        frame = loco.step(1e-4, player, (0.0, 0.0))
        return {side: frame.spec.legs[side].ankle.copy() for side in "LR"}

    for fraction in (0.0, 0.17, 0.4, 0.63, 0.9):
        phase = base + fraction * 2.0 * math.pi
        now, later = feet(phase), feet(phase + 2.0 * math.pi)
        for side in "LR":
            assert (now[side] - later[side]).length < 1e-3, f"ciclo não periódico ({side}, {fraction})"
        half = feet(phase + math.pi)
        for side, other in (("L", "R"), ("R", "L")):
            a, b = now[side], half[other]
            assert abs((a.y) - (b.y)) < 2e-3 and abs(a.z - b.z) < 2e-3, "esquerda e direita defasadas de meio ciclo"
    extent = [feet(base + t * 0.1)["L"].y for t in range(63)]
    assert max(extent) - min(extent) > 0.6, "passada curta demais"
    lows = [feet(base + t * 0.1)["L"].z for t in range(63)]
    assert min(lows) >= S.ANKLE_Z - 1e-3, "o tornozelo afundou abaixo da altura de repouso"
    assert max(lows) - min(lows) > 0.08, "o pé não levanta no balanço"


def test_feet_follow_stride_phase(scene):
    """Um passo por pi: o pé da frente troca a cada meio ciclo."""
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    settle(rig, player, 1.0)
    forward_foot = []
    for _ in range(240):
        player.walk(DT)
        rig.update(DT, player)
        left, right = rig._solution.head[S.BONE_INDEX["Foot.L"]].y, rig._solution.head[S.BONE_INDEX["Foot.R"]].y
        forward_foot.append("L" if left > right else "R")
    changes = sum(1 for a, b in zip(forward_foot, forward_foot[1:]) if a != b)
    steps = player.stride_phase / math.pi
    assert changes >= int(240 * DT * 2.6 / 1.15) - 1, f"{changes} trocas de pé em {steps:.1f} passos"


def test_crouch_and_run(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    settle(rig, player, 1.0, speed=0.0)
    stand_hips = rig._solution.head[S.BONE_INDEX["Hips"]].z
    stand_knee = rig._solution.head[S.BONE_INDEX["Shin.R"]]
    player.crouching, player.eye = True, C.PLAYER_EYE_CROUCH
    settle(rig, player, 1.0, speed=0.0)
    crouch_hips = rig._solution.head[S.BONE_INDEX["Hips"]].z
    knee = rig._solution.head[S.BONE_INDEX["Shin.R"]]
    assert stand_hips - crouch_hips > 0.30, f"quadril desceu só {stand_hips - crouch_hips:.2f} m ao agachar"
    assert knee.y > stand_knee.y + 0.15, "joelho deve avançar ao agachar"
    spine_top = rig._solution.head[S.BONE_INDEX["Neck"]]
    assert spine_top.y > rig._solution.head[S.BONE_INDEX["Hips"]].y + 0.1, "tronco deve inclinar para a frente agachado"
    ankle = rig._solution.head[S.BONE_INDEX["Foot.R"]]
    assert abs(ankle.z - S.ANKLE_Z) < 0.02, "pés devem continuar no chão agachado"
    player.crouching, player.eye = False, C.PLAYER_EYE_STAND
    settle(rig, player, 1.0, speed=0.0)
    settle(rig, player, 1.0, speed=4.6, running=True)
    lean = rig._solution.head[S.BONE_INDEX["Neck"]].y - rig._solution.head[S.BONE_INDEX["Hips"]].y
    assert lean > 0.05, "correr inclina o tronco"


def test_chest_follows_camera(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    for pitch in (-85, -45, 0, 30, 60):
        player.pitch = math.radians(pitch)
        settle(rig, player, 0.5, speed=0.0)
        neck = rig._solution.head[S.BONE_INDEX["Neck"]]
        eye = Vector(player.camera_pose()[0])
        local = rig._root + Matrix.Rotation(rig._yaw, 3, "Z") @ neck
        assert (eye - local).length < 0.40 and local.z < eye.z - 0.05, (pitch, tuple(local), tuple(eye))
    player.pitch = 0.0
    for turn in range(10):
        player.yaw += math.radians(18)
        rig.update(DT, player)
    assert 0 < abs(player.yaw - rig._yaw) < math.radians(70), "o corpo deve atrasar um pouco em relação à câmera"


def test_stairs_and_height_follow(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    for step in range(60):
        player.z_visual = 0.05 * step / 10
        player.walk(DT, 1.2)
        rig.update(DT, player)
    assert abs(rig._root.z - player.z_visual) < 1e-6
    assert rig._solution.head[S.BONE_INDEX["Foot.L"]].z < S.ANKLE_Z + 0.3


def test_finger_presets():
    def tips(name, side="R"):
        curls, spread = F.preset(name)
        spec = V.PoseSpec(rot=F.finger_rotations(side, curls, spread))
        solution = V.solve(spec)
        palm = solution.point_on(f"Hand.{side}", S.BONE_MAP[f"Hand.{side}"].head + S.palm_offset(side))
        return solution, palm

    for name in F.PRESETS:
        for side in "LR":
            tips(name, side)
    flat, _ = tips("flat")
    fist, palm = tips("fist")
    point, _ = tips("point")
    relaxed, _ = tips("relaxed")
    open_hand, _ = tips("open")

    def spread_of(solution):
        return (solution.tail("Index3.R") - solution.tail("Pinky3.R")).length

    def extent(solution, finger):
        return (solution.tail(f"{finger}3.R") - solution.head[S.BONE_INDEX[f"{finger}1.R"]]).length

    full = {f: sum(S.PHALANX[f]) for f in S.FINGERS}
    assert all(extent(flat, f) > 0.97 * full[f] for f in S.FINGERS), "flat: dedos esticados"
    assert extent(point, "Index") > 0.97 * full["Index"] and extent(point, "Middle") < 0.6 * full["Middle"], "point: indicador reto, médio fechado"
    assert all(extent(fist, f) < 0.62 * full[f] for f in S.FINGERS), "fist: dedos fechados"
    for finger in S.FINGERS:
        assert (fist.tail(f"{finger}3.R") - palm).length < 0.07, f"fist: ponta do {finger} longe da palma"
    assert extent(relaxed, "Middle") < extent(flat, "Middle") and extent(relaxed, "Middle") > extent(fist, "Middle")
    assert spread_of(open_hand) > spread_of(flat) + 0.01, "spread abre os dedos"
    grip, _ = tips("grip_cylinder")
    pinch, _ = tips("pinch")
    gap = (pinch.tail("Thumb2.R") - pinch.tail("Index3.R")).length
    assert gap < 0.025, f"pinch: polegar e indicador a {gap * 1000:.0f} mm"
    assert (grip.tail("Thumb2.R") - grip.tail("Index3.R")).length < 0.09
    left, _ = tips("fist", "L")
    mirrored = Vector((-left.tail("Index3.L").x, left.tail("Index3.L").y, left.tail("Index3.L").z))
    assert (mirrored - fist.tail("Index3.R")).length < 2e-3, "mãos esquerda e direita espelhadas"


def test_set_fingers_blend(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    arm = rig.arm("R")
    arm.set_fingers(F.PRESETS["fist"][0], 0.0, 1.0)
    rig.update(0.5, FakePlayer())
    closed = arm._curls[2]
    arm.set_fingers(F.PRESETS["flat"][0], 0.0, 0.5)
    assert abs(arm._goal_curls[2] - closed * 0.5) < 1e-6, "blend=0.5 percorre metade do caminho"
    arm.release()
    rig.update(0.5, FakePlayer())
    assert all(abs(a - b) < 1e-3 for a, b in zip(arm._curls, F.RELAXED_CURLS))


def test_held_objects_follow_hand(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    cube = bpy.data.objects.new("_held", bpy.data.meshes.new("_held"))
    scene.collection.objects.link(cube)
    arm = rig.arm("R")
    arm.set_target((0.2, -0.1, -0.4), (0, 0, 0), 1.0)
    settle(rig, player, 0.3, speed=0.0)
    arm.hold(cube)
    settle(rig, player, 0.1, speed=0.0)
    assert (cube.matrix_world.translation - Vector(arm.hand_world_position())).length < 1e-4
    arm.set_target((0.1, -0.2, -0.5), (0, 0, 0), 1.0)
    settle(rig, player, 0.2, speed=0.0)
    assert (cube.matrix_world.translation - Vector(arm.hand_world_position())).length < 1e-4
    arm.hold(cube, (0.0, 0.0, -0.1))
    settle(rig, player, 0.05, speed=0.0)
    expected = Vector(arm.hand_world_position()) + player_camera_matrix(player) @ Vector((0.0, 0.0, -0.1))
    assert (cube.matrix_world.translation - expected).length < 1e-3, "o offset está no referencial da mão (câmera com rotation 0)"
    arm.drop(cube)
    spot = cube.matrix_world.translation.copy()
    settle(rig, player, 0.2, speed=0.0)
    arm.set_target((0.0, 0.0, -0.3), (0, 0, 0), 1.0)
    settle(rig, player, 0.2, speed=0.0)
    assert (cube.matrix_world.translation - spot).length < 1e-6, "depois do drop o objeto não segue mais a mão"
    bpy.data.objects.remove(cube)
    arm.release()


def player_camera_matrix(player):
    return Euler(player.camera_pose()[1], "XYZ").to_matrix()


def test_poses(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    rig.place(2.0, 3.0, 0.5, math.radians(90))
    for name in ("stand", "lying_bed", "sit_bed", "driving"):
        rig.pose(name, 0.0)
        solution = rig._solution
        assert all(math.isfinite(c) for head in solution.head for c in head), name
    rig.pose("lying_bed", 0.0)
    neck = rig._solution.head[S.BONE_INDEX["Neck"]]
    foot = rig._solution.head[S.BONE_INDEX["Foot.L"]]
    hips = rig._solution.head[S.BONE_INDEX["Hips"]]
    assert neck.y < hips.y - 0.3 and foot.y > hips.y + 0.5, "deitado: cabeça atrás, pés à frente"
    assert abs(hips.z - 0.10) < 0.05 and max(h.z for h in rig._solution.head) < 0.35, "deitado: tudo rente ao apoio"
    rig.pose("sit_bed", 0.0)
    knee = rig._solution.head[S.BONE_INDEX["Shin.R"]]
    hips = rig._solution.head[S.BONE_INDEX["Hips"]]
    assert knee.y > hips.y + 0.35 and abs(knee.z - hips.z) < 0.12, "sentado: coxa na horizontal"
    assert rig._solution.head[S.BONE_INDEX["Neck"]].z > hips.z + 0.40, "sentado: tronco ereto"
    rig.pose("driving", 0.0)
    rig.pose("stand", 1.0)
    assert rig._blend.active
    for _ in range(70):
        rig.update(DT, None)
    assert not rig._blend.active
    hips = rig._solution.head[S.BONE_INDEX["Hips"]]
    assert abs(hips.z - S.PELVIS_Z) < 0.01, "de volta em pé"
    try:
        rig.pose("voar")
    except KeyError:
        pass
    else:
        raise AssertionError("pose desconhecida deveria falhar")
    assert abs(rig.armature.location.x - 2.0) < 1e-6 and abs(rig.armature.location.y - 3.0) < 1e-6
    rig.reset()
    assert rig._mode == "follow"


def test_attach_view(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    camera = bpy.data.objects.new("_cutcam", bpy.data.cameras.new("_cutcam"))
    scene.collection.objects.link(camera)
    camera.location = (5.0, 5.0, 1.6)
    camera.rotation_euler = (math.pi / 2, 0.0, math.radians(180))
    rig.place(5.0, 5.0, 0.0, math.radians(180))
    rig.attach_view(camera)
    arm = rig.arm("R")
    arm.set_target((0.2, -0.1, -0.4), (0, 0, 0), 1.0)
    rig.update(DT, None)
    want = Vector(camera.location) + camera.rotation_euler.to_matrix() @ Vector((0.2, -0.1, -0.4))
    assert (Vector(arm.hand_world_position()) - want).length < 0.005
    rig.attach_view(None)
    rig.reset()
    bpy.data.objects.remove(camera)


def test_nothing_crosses_the_clip_plane(scene):
    """Nenhum vértice do corpo perto do olho nos ângulos de visão (pitch -85 a +60), parado, andando e agachado."""
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    mesh_obj = scene.objects[C.OBJ_BODY]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    player = FakePlayer()
    closest = 1e9
    for crouching in (False, True):
        player.crouching = crouching
        player.eye = C.PLAYER_EYE_CROUCH if crouching else C.PLAYER_EYE_STAND
        for pitch in (-85, -60, -30, 0, 30, 60):
            player.pitch = math.radians(pitch)
            for speed, running in ((0.0, False), (2.6, False), (4.6, True)):
                if crouching and running:
                    continue
                settle(rig, player, 0.5, running=running, speed=speed)
                bpy.context.view_layer.update()
                evaluated = mesh_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                mesh = evaluated.to_mesh()
                position, euler = player.camera_pose()
                inverse = (Matrix.Translation(position) @ Euler(euler, "XYZ").to_matrix().to_4x4()).inverted()
                world = evaluated.matrix_world
                for vertex in mesh.vertices:
                    local = inverse @ (world @ vertex.co)
                    distance = local.length
                    closest = min(closest, distance)
                evaluated.to_mesh_clear()
    assert closest > 0.10, f"vértice a {closest * 100:.1f} cm do olho: o plano de corte ({CLIP_START * 100:.0f} cm) pode atravessar o corpo"
    print(f"  vértice mais próximo do olho: {closest * 100:.1f} cm")


def test_update_cost(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(True)
    player = FakePlayer()
    rig.arm("R").set_target((0.2, -0.1, -0.4), (0, 0, 20), 1.0)
    rig.arm("L").set_fingers(F.PRESETS["grip_cylinder"][0])
    settle(rig, player, 0.5)
    total = 0.0
    frames = 600
    for i in range(frames):
        player.walk(DT, 2.6 if i % 200 < 150 else 4.6, i % 200 >= 150)
        started = time.perf_counter()
        rig.update(DT, player, (0.01 * math.sin(i * 0.1), 0.01 * math.sin(i * 0.2)))
        total += time.perf_counter() - started
    per_frame = total / frames * 1000.0
    assert per_frame < 2.0, f"{per_frame:.2f} ms por quadro (limite 2 ms)"
    print(f"  update: {per_frame:.3f} ms por quadro")


def test_hidden_costs_nothing(scene):
    rig = body.BodyRig(scene)
    rig.set_visible(False)
    started = time.perf_counter()
    for _ in range(1000):
        rig.update(DT, FakePlayer())
    assert (time.perf_counter() - started) / 1000 < 5e-5
    assert scene.objects[C.OBJ_BODY].hide_viewport and scene.objects[C.OBJ_BODY].hide_render


def test_game_uses_the_body():
    """O Game encontra o BodyRig, mostra o corpo nas fases de jogo e o atualiza todo quadro."""
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_engine_fakes as fk
    scene = fk.fresh_scene()
    fk.build_minimal_world(scene)
    ctx = BuildContext(scene, verbose=False)
    ctx.stage = "body"
    body.build(ctx)
    game = fk.start_playing(fk.Game(scene, audio=False, entity=False, cutscenes=False))
    assert isinstance(game.body, body.BodyRig), type(game.body)
    assert game.body.visible, "o corpo aparece na fase play"
    fk.teleport(game, 2.1, 1.5, 0.0, 0)
    fk.walk(game, 1.0)
    assert game.body._solution is not None and game.body._frame_ms < 2.0, game.body._frame_ms
    game.phase = "title"
    game.tick(DT, fk.InputState())
    assert not game.body.visible, "o corpo some no título"
    game.phase = "play"
    game.tick(DT, fk.InputState())
    assert game.body.visible


def test_body_does_not_cast_flashlight_shadow(scene):
    mesh_obj = scene.objects[C.OBJ_BODY]
    if hasattr(mesh_obj, "visible_shadow"):
        assert mesh_obj.visible_shadow is False


def main():
    scene = fresh_scene()
    tests = [test_objects_and_budget, test_weights, test_parity_with_null_body, test_pose_matches_blender,
             test_arm_ik_reaches_target, test_arm_weight_blends, test_arms_swing_when_free,
             test_gait_periodic_and_symmetric, test_feet_follow_stride_phase, test_crouch_and_run,
             test_chest_follows_camera, test_stairs_and_height_follow, test_finger_presets,
             test_set_fingers_blend, test_held_objects_follow_hand, test_poses, test_attach_view,
             test_nothing_crosses_the_clip_plane, test_update_cost, test_hidden_costs_nothing,
             test_body_does_not_cast_flashlight_shadow, test_game_uses_the_body]
    failures = []
    for fn in tests:
        print(fn.__name__)
        try:
            fn(scene) if fn.__code__.co_argcount else fn()
        except AssertionError as error:
            failures.append((fn.__name__, error))
            print(f"  FALHOU: {error}")
    if failures:
        print(f"test_body: {len(failures)} falha(s): " + ", ".join(n for n, _ in failures))
        sys.exit(1)
    print("test_body: OK")


if __name__ == "__main__":
    main()
