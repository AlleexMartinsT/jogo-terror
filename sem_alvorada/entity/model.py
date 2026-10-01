"""Geometria do Alto: malha low-poly feita de tubos elípticos ("anéis" ao longo de cada membro).

Tudo é medido a partir das constantes de `skeleton.py`, então o corpo nunca sai de sincronia
com os ossos. Cada vértice carrega pesos de osso; nas juntas o anel é dividido 50/50 entre os
dois ossos para o cotovelo/joelho dobrar sem abrir buraco (estilo GoldSrc "suavizado").

Proporções propositalmente ERRADAS: braços que chegam ao joelho, tronco fino, pescoço longo,
cabeça pequena, dedos de 20 cm e nenhuma boca ou nariz.
"""
import math
from dataclasses import dataclass, field

import bpy
from mathutils import Vector

from . import materials as M
from . import skeleton as S

X_AXIS = Vector((1.0, 0.0, 0.0))
Y_AXIS = Vector((0.0, 1.0, 0.0))
Z_AXIS = Vector((0.0, 0.0, 1.0))

SLOT_SKIN, SLOT_CLOTH = 0, 1
BODY_UV_HEAD = (0.0, 0.5, 0.5, 1.0)         # ver atlas em textures.py
BODY_UV_LIMB = (0.5, 0.0, 1.0, 1.0)
CLOTH_UV_PER_METER = 2.4                    # repetições da trama por metro

HEAD_SIDES = 12
# (z, semi-largura x, semi-profundidade y, deslocamento y do centro)
HEAD_RINGS = (
    (2.41, 0.046, 0.050, 0.000),
    (2.44, 0.062, 0.070, 0.006),
    (2.48, 0.076, 0.090, 0.012),
    (2.53, 0.084, 0.098, 0.014),
    (2.58, 0.084, 0.098, 0.010),
    (2.62, 0.070, 0.082, 0.000),
    (2.645, 0.044, 0.054, -0.006),
)
EYE_Z = 2.535
EYE_X = 0.038
EYE_WIDTH = 0.052
EYE_HEIGHT = 0.026
EYE_SLANT_DEG = 13.0


def _smooth(value, low, high):
    t = min(max((value - low) / (high - low), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


@dataclass
class Ring:
    """Uma secção transversal: centro, semi-eixos e pesos de osso (dict ou função do ângulo)."""
    center: Vector
    rx: float
    ry: float
    weights: object
    drop: tuple = field(default_factory=tuple)      # descida em Z por vértice (bainha rasgada)


class MeshBuilder:
    def __init__(self):
        self.coords, self.vertex_weights = [], []
        self.faces, self.face_uvs, self.face_slots = [], [], []

    def vertex(self, co, weights):
        self.coords.append((co.x, co.y, co.z))
        self.vertex_weights.append(weights)
        return len(self.coords) - 1

    def face(self, indices, uvs, slot):
        self.faces.append(tuple(indices))
        self.face_uvs.append(tuple(uvs))
        self.face_slots.append(slot)

    def tube(self, rings, sides, slot, uv_box, ax=X_AXIS, ay=Y_AXIS, start_angle=0.0,
             cap_start=False, cap_end=False, v_per_meter=None):
        """Liga os anéis em sequência com quadriláteros; opcionalmente fecha as pontas com leque."""
        direction = rings[-1].center - rings[0].center
        flip = ax.cross(ay).dot(direction) < 0
        u0, v0, u1, v1 = uv_box
        distances = [0.0]
        for a, b in zip(rings, rings[1:]):
            distances.append(distances[-1] + (b.center - a.center).length)
        total = distances[-1] or 1.0

        ring_index = []
        for ring in rings:
            row = []
            for j in range(sides):
                angle = start_angle + 2.0 * math.pi * j / sides
                point = ring.center + ax * (math.cos(angle) * ring.rx) + ay * (math.sin(angle) * ring.ry)
                if ring.drop:
                    point = point - Z_AXIS * ring.drop[j]
                weights = ring.weights(angle) if callable(ring.weights) else ring.weights
                row.append(self.vertex(point, weights))
            ring_index.append(row)

        def v_at(r):
            if v_per_meter is not None:
                return v0 + distances[r] * v_per_meter
            return v0 + (v1 - v0) * distances[r] / total

        for r in range(len(rings) - 1):
            for j in range(sides):
                k = (j + 1) % sides
                quad = (ring_index[r][j], ring_index[r][k], ring_index[r + 1][k], ring_index[r + 1][j])
                ua, ub = u0 + (u1 - u0) * j / sides, u0 + (u1 - u0) * (j + 1) / sides
                uvs = ((ua, v_at(r)), (ub, v_at(r)), (ub, v_at(r + 1)), (ua, v_at(r + 1)))
                if flip:
                    quad, uvs = quad[::-1], uvs[::-1]
                self.face(quad, uvs, slot)

        for enabled, r, at_end in ((cap_start, 0, False), (cap_end, len(rings) - 1, True)):
            if enabled:
                self._cap(rings[r], ring_index[r], sides, slot, uv_box, at_end != flip)

    def _cap(self, ring, row, sides, slot, uv_box, outward_forward):
        u0, v0, u1, v1 = uv_box
        weights = ring.weights(0.0) if callable(ring.weights) else ring.weights
        center = self.vertex(ring.center, weights)
        uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
        for j in range(sides):
            k = (j + 1) % sides
            a1, a2 = 2 * math.pi * j / sides, 2 * math.pi * k / sides
            tri = (center, row[j], row[k]) if outward_forward else (center, row[k], row[j])
            uvs = ((uc, vc), (uc + 0.05 * math.cos(a1), vc + 0.05 * math.sin(a1)),
                   (uc + 0.05 * math.cos(a2), vc + 0.05 * math.sin(a2)))
            if not outward_forward:
                uvs = (uvs[0], uvs[2], uvs[1])
            self.face(tri, uvs, slot)


def _panel_weights(coverage):
    """Pesos de uma aba do sobretudo: cada quadrante da bainha segue a sua aba; `coverage` 0..1 sobe com a queda."""
    def weights(angle):
        x, y = math.cos(angle), math.sin(angle)
        front, right = _smooth(y, -0.4, 0.4), _smooth(x, -0.4, 0.4)
        parts = {"CoatFront.R": front * right, "CoatFront.L": front * (1 - right),
                 "CoatBack.R": (1 - front) * right, "CoatBack.L": (1 - front) * (1 - right)}
        result = {"Hips": 1.0 - coverage}
        result.update({name: coverage * w for name, w in parts.items() if coverage * w > 0.01})
        return result
    return weights


def _shoulder_weights(angle):
    x = math.cos(angle)
    result = {"Spine3": 1.0}
    for side, value in (("R", x), ("L", -x)):
        share = 0.55 * _smooth(value, 0.35, 0.9)
        if share > 0.01:
            result[f"Shoulder.{side}"] = share
            result["Spine3"] -= share
    return result


def _ring(x, y, z, rx, ry, weights, drop=()):
    return Ring(Vector((x, y, z)), rx, ry, weights, drop)


def _half(a, b):
    return {a: 0.5, b: 0.5}


def build_torso_and_coat(mb):
    """Sobretudo inteiro: gola, tronco fino e saia rasgada até a canela."""
    hem_drop = (0.16, 0.0, 0.10, 0.02, 0.20, 0.0, 0.14, 0.03, 0.18, 0.0, 0.08, 0.02)
    rings = [
        _ring(0, 0, 0.50, 0.30, 0.22, _panel_weights(1.0), hem_drop),
        _ring(0, 0, 0.68, 0.285, 0.21, _panel_weights(0.88)),
        _ring(0, 0, 0.88, 0.26, 0.19, _panel_weights(0.58)),
        _ring(0, 0, 1.06, 0.235, 0.17, _panel_weights(0.25)),
        _ring(0, 0, S.HIP_Z, 0.19, 0.13, {"Hips": 1.0}),
        _ring(0, 0, 1.36, 0.165, 0.115, _half("Hips", "Spine1")),
        _ring(0, 0, 1.49, 0.155, 0.108, {"Spine1": 1.0}),
        _ring(0, 0, 1.62, 0.155, 0.105, _half("Spine1", "Spine2")),
        _ring(0, 0, 1.75, 0.162, 0.110, {"Spine2": 1.0}),
        _ring(0, 0, 1.88, 0.175, 0.120, _half("Spine2", "Spine3")),
        _ring(0, 0, 2.01, 0.190, 0.125, {"Spine3": 1.0}),
        _ring(0, 0, 2.12, 0.205, 0.115, _shoulder_weights),
        _ring(0, 0, 2.19, 0.150, 0.100, _shoulder_weights),
        _ring(0, 0, 2.25, 0.075, 0.070, {"Spine3": 1.0}),
    ]
    mb.tube(rings, 12, SLOT_CLOTH, (0.0, 0.0, 2.0, 1.0), cap_end=True, v_per_meter=CLOTH_UV_PER_METER)


def build_neck_and_head(mb):
    neck = [
        _ring(0, 0, 2.16, 0.052, 0.052, _half("Spine3", "Neck")),
        _ring(0, 0, 2.28, 0.040, 0.040, {"Neck": 1.0}),
        _ring(0, 0, S.HEAD_BASE_Z + 0.01, 0.043, 0.043, _half("Neck", "Head")),
    ]
    mb.tube(neck, 8, SLOT_SKIN, (0.5, 0.85, 1.0, 1.0))
    head = [_ring(0, cy, z, rx, ry, {"Head": 1.0}) for z, rx, ry, cy in HEAD_RINGS]
    # a costura da textura fica atrás da cabeça: o rosto (frente, +Y) cai no meio do quadrante
    mb.tube(head, HEAD_SIDES, SLOT_SKIN, BODY_UV_HEAD, start_angle=-math.pi / 2, cap_end=True)


def _lerp(a, b, t):
    return a + (b - a) * t


def build_arm(mb, side):
    sx = S.side_sign(side)
    shoulder_x, elbow_x, wrist_x = (sx * S.ARM_SPREAD[k] for k in ("shoulder", "elbow", "wrist"))
    upper, fore, hand = f"UpperArm.{side}", f"Forearm.{side}", f"Hand.{side}"

    sleeve = [
        _ring(shoulder_x, 0, S.SHOULDER_Z + 0.04, 0.060, 0.056, _half("Spine3", upper)),
        _ring(shoulder_x, 0, S.SHOULDER_Z - 0.06, 0.056, 0.052, {upper: 1.0}),
        _ring(_lerp(shoulder_x, elbow_x, 0.55), 0, _lerp(S.SHOULDER_Z, S.ELBOW_Z, 0.55), 0.048, 0.046, {upper: 1.0}),
        _ring(elbow_x, 0, S.ELBOW_Z + 0.02, 0.043, 0.042, _half(upper, fore),
              drop=(0.0, 0.05, 0.0, 0.09, 0.0, 0.03, 0.0, 0.07)),
    ]
    mb.tube(sleeve, 8, SLOT_CLOTH, (0.0, 0.0, 1.0, 1.0), cap_start=True, v_per_meter=CLOTH_UV_PER_METER)

    forearm = [
        _ring(elbow_x, 0, S.ELBOW_Z, 0.038, 0.036, _half(upper, fore)),
        _ring(_lerp(elbow_x, wrist_x, 0.5), 0, _lerp(S.ELBOW_Z, S.WRIST_Z, 0.5), 0.034, 0.033, {fore: 1.0}),
        _ring(wrist_x, 0, S.WRIST_Z, 0.024, 0.026, _half(fore, hand)),
    ]
    mb.tube(forearm, 8, SLOT_SKIN, BODY_UV_LIMB)

    palm = [
        _ring(wrist_x, 0, S.WRIST_Z, 0.020, 0.030, _half(fore, hand)),
        _ring(wrist_x, 0, S.WRIST_Z - 0.09, 0.016, 0.044, {hand: 1.0}),
        _ring(wrist_x, 0, S.HAND_END_Z, 0.014, 0.046, {hand: 1.0}),
    ]
    mb.tube(palm, 8, SLOT_SKIN, (0.5, 0.0, 0.75, 0.3), cap_end=True)

    for finger in S.FINGER_NAMES:
        a, b = f"{finger}A.{side}", f"{finger}B.{side}"
        y, length = S.FINGER_Y[finger], S.FINGER_LENGTH[finger]
        z0 = S.HAND_END_Z + 0.01
        joints = [
            _ring(wrist_x, y, z0, 0.011, 0.010, _half(hand, a)),
            _ring(wrist_x, y, S.HAND_END_Z - length * 0.5, 0.009, 0.008, _half(a, b)),
            _ring(wrist_x, y, S.HAND_END_Z - length, 0.005, 0.005, {b: 1.0}),
        ]
        mb.tube(joints, 4, SLOT_SKIN, (0.75, 0.0, 1.0, 0.3), start_angle=math.pi / 4, cap_end=True)

    thumb_bone = f"Thumb.{side}"
    thumb = [
        _ring(wrist_x, 0.045, S.WRIST_Z - 0.05, 0.012, 0.011, _half(hand, thumb_bone)),
        _ring(wrist_x, 0.062, S.WRIST_Z - 0.13, 0.009, 0.009, {thumb_bone: 1.0}),
        _ring(wrist_x, 0.080, S.WRIST_Z - 0.22, 0.005, 0.005, {thumb_bone: 1.0}),
    ]
    mb.tube(thumb, 4, SLOT_SKIN, (0.75, 0.0, 1.0, 0.3), start_angle=math.pi / 4, cap_end=True)


def build_leg(mb, side):
    sx = S.side_sign(side)
    x = sx * S.LEG_SPREAD
    thigh, shin, foot = f"Thigh.{side}", f"Shin.{side}", f"Foot.{side}"

    trousers = [
        _ring(x, 0, S.HIP_Z, 0.088, 0.088, {thigh: 1.0}),
        _ring(x, 0, 0.95, 0.075, 0.075, {thigh: 1.0}),
        _ring(x, 0, S.KNEE_Z + 0.03, 0.060, 0.060, _half(thigh, shin),
              drop=(0.0, 0.06, 0.0, 0.10, 0.0, 0.04, 0.0, 0.08)),
    ]
    mb.tube(trousers, 8, SLOT_CLOTH, (0.0, 0.0, 1.0, 1.0), v_per_meter=CLOTH_UV_PER_METER)

    calf = [
        _ring(x, 0, S.KNEE_Z, 0.048, 0.050, _half(thigh, shin)),
        _ring(x, 0, 0.38, 0.038, 0.040, {shin: 1.0}),
        _ring(x, 0, S.ANKLE_Z + 0.02, 0.028, 0.030, _half(shin, foot)),
    ]
    mb.tube(calf, 8, SLOT_SKIN, BODY_UV_LIMB)

    weights = {foot: 1.0}
    sole = [                                    # ao longo de +Y; secção no plano XZ
        _ring(x, -0.065, 0.050, 0.032, 0.050, {foot: 0.7, shin: 0.3}),
        _ring(x, 0.050, 0.040, 0.036, 0.040, weights),
        _ring(x, 0.190, 0.022, 0.040, 0.022, weights),
        _ring(x, 0.300, 0.012, 0.024, 0.012, weights),
    ]
    mb.tube(sole, 8, SLOT_SKIN, (0.5, 0.0, 1.0, 0.25), ay=Z_AXIS, cap_start=True, cap_end=True)


def build_body_geometry():
    mb = MeshBuilder()
    build_torso_and_coat(mb)
    build_neck_and_head(mb)
    for side in ("L", "R"):
        build_arm(mb, side)
        build_leg(mb, side)
    return mb


def head_surface_y(x, z):
    """Y da superfície da frente da cabeça em (x, z), interpolando os anéis da elipse."""
    rings = HEAD_RINGS
    for (z0, rx0, ry0, cy0), (z1, rx1, ry1, cy1) in zip(rings, rings[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            rx, ry, cy = _lerp(rx0, rx1, t), _lerp(ry0, ry1, t), _lerp(cy0, cy1, t)
            return cy + ry * math.sqrt(max(1.0 - (x / rx) ** 2, 0.0))
    raise ValueError(f"z={z} fora da cabeça")


def build_eyes_geometry():
    """Dois olhos amendoados, colados na frente da cabeça, inclinados para baixo nas pontas externas."""
    mb = MeshBuilder()
    outline = [(-0.5, 0.0), (-0.25, 0.5), (0.25, 0.5), (0.5, 0.0), (0.25, -0.5), (-0.25, -0.5)]
    for side_x in (-EYE_X, EYE_X):
        slant = math.radians(EYE_SLANT_DEG) * (1 if side_x > 0 else -1)
        corners = []
        for ox, oz in outline + [(0.0, 0.0)]:
            lx, lz = ox * EYE_WIDTH, oz * EYE_HEIGHT
            px = side_x + lx * math.cos(slant) - lz * math.sin(slant)
            pz = EYE_Z + lx * math.sin(slant) + lz * math.cos(slant)
            corners.append(mb.vertex(Vector((px, head_surface_y(px, pz) + 0.004, pz)), {"Head": 1.0}))
        center = corners[-1]
        for i in range(6):
            mb.face((center, corners[i], corners[(i + 1) % 6]), ((0.5, 0.5),) * 3, 0)
    return mb


def _mesh_from_builder(name, mb, materials):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(mb.coords, [], mb.faces)
    for mat in materials:
        mesh.materials.append(mat)
    for poly, slot in zip(mesh.polygons, mb.face_slots):
        poly.material_index = slot
    uv_layer = mesh.uv_layers.new(name="UVMap")
    flat_uv = [c for face in mb.face_uvs for uv in face for c in uv]
    uv_layer.data.foreach_set("uv", flat_uv)
    mesh.update()
    mesh.validate()
    return mesh


def _apply_weights(obj, mb):
    groups = {}
    for name in S.BONE_ORDER:
        groups[name] = obj.vertex_groups.new(name=name)
    for index, weights in enumerate(mb.vertex_weights):
        for bone_name, weight in weights.items():
            if weight > 0.001:
                groups[bone_name].add([index], weight, "REPLACE")


def create_body_object(materials):
    mb = build_body_geometry()
    mesh = _mesh_from_builder("Entity_Body", mb, [materials[M.SKIN], materials[M.CLOTH]])
    obj = bpy.data.objects.new("Entity_Body", mesh)
    _apply_weights(obj, mb)
    return obj


def create_eyes_object(materials):
    mb = build_eyes_geometry()
    mesh = _mesh_from_builder("Entity_Eyes", mb, [materials[M.EYE]])
    obj = bpy.data.objects.new("Entity_Eyes", mesh)
    _apply_weights(obj, mb)
    return obj


def triangle_count(obj):
    mesh = obj.data
    return sum(len(p.vertices) - 2 for p in mesh.polygons)
