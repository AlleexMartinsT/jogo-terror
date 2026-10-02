"""Pisos: tábuas de madeira individuais (larguras e comprimentos variados, juntas alternadas, chanfro
mínimo) e placas lisas para os demais acabamentos.

As tábuas correm no sentido do maior lado do cômodo. Cada uma recebe um desnível de até 0,4 mm, um
chanfro de 1,6 mm (que desenha o rego entre elas sob a lanterna) e um recorte próprio do veio, sorteado
pelas coordenadas UV: nenhuma tábua repete a vizinha. Embaixo vai uma forração escura, para o rego não
mostrar o vazio.
"""
import random

from .. import layout
from .modelkit import PROFILED, ModelBuilder

BOARD_WIDTHS = (0.089, 0.102, 0.114, 0.127, 0.140)
BOARD_LENGTH = (0.9, 2.4)
MIN_STAGGER = 0.35            # distância mínima entre juntas de fileiras vizinhas
CHAMFER = 0.0016
GAP = 0.0008
HEIGHT_NOISE = 0.0004
UNDERLAY_DEPTH = 0.004
UNDERLAY = "rubber"
WOOD_SURFACES = ("floor_wood", "floor_wood_dark")


def floor_builder(name):
    return ModelBuilder(name, PROFILED)


def add_room_floor(builder, rect, z, material, rng):
    """Piso de um cômodo: tábuas se for madeira, uma placa lisa nos demais casos."""
    if material in WOOD_SURFACES:
        add_planks(builder, rect, z, material, rng)
    else:
        corners = ((rect.x0, rect.y0, z), (rect.x1, rect.y0, z), (rect.x1, rect.y1, z), (rect.x0, rect.y1, z))
        builder.quad(*corners, material)


def add_planks(builder, rect, z, material, rng):
    along_x = rect.w >= rect.h
    length = rect.w if along_x else rect.h
    width = rect.h if along_x else rect.w
    a0, c0 = (rect.x0, rect.y0) if along_x else (rect.y0, rect.x0)
    builder.quad((rect.x0, rect.y0, z - UNDERLAY_DEPTH), (rect.x0, rect.y1, z - UNDERLAY_DEPTH),
                 (rect.x1, rect.y1, z - UNDERLAY_DEPTH), (rect.x1, rect.y0, z - UNDERLAY_DEPTH), UNDERLAY)
    previous_joints = []
    cursor = 0.0
    while cursor < width - 1e-6:
        board_width = min(rng.choice(BOARD_WIDTHS), width - cursor)
        if width - cursor - board_width < 0.04:
            board_width = width - cursor
        joints = _joints(rng, length, previous_joints)
        edges = [0.0] + joints + [length]
        for start, end in zip(edges, edges[1:]):
            _board(builder, along_x, a0 + start, a0 + end, c0 + cursor, c0 + cursor + board_width, z, material, rng)
        previous_joints = joints
        cursor += board_width


def _joints(rng, length, previous):
    """Posições das juntas de topo de uma fileira, afastadas das juntas da fileira anterior."""
    joints = []
    position = rng.uniform(0.25, BOARD_LENGTH[1])
    while position < length - 0.3:
        for _ in range(8):
            if all(abs(position - other) >= MIN_STAGGER for other in previous):
                break
            position += rng.uniform(0.2, 0.6)
        if position < length - 0.3:
            joints.append(position)
        position += rng.uniform(*BOARD_LENGTH)
    return joints


def _board(builder, along_x, a0, a1, c0, c1, z, material, rng):
    """Uma tábua: face de cima e quatro chanfros. (a = ao longo da tábua, c = na largura.)"""
    a0, a1, c0, c1 = a0 + GAP / 2, a1 - GAP / 2, c0 + GAP / 2, c1 - GAP / 2
    top = z + rng.uniform(-HEIGHT_NOISE, HEIGHT_NOISE)
    offset_u, offset_v = rng.random() * 2.0, rng.random() * 0.5
    inner = (a0 + CHAMFER, a1 - CHAMFER, c0 + CHAMFER, c1 - CHAMFER)
    outer = (a0, a1, c0, c1)

    def point(a, c, height):
        return (a, c, height) if along_x else (c, a, height)

    def emit(corners):
        points = [point(a, c, h) for a, c, h in corners]
        uvs = [(a - a0 + offset_u, c - c0 + offset_v) for a, c, _ in corners]
        _upward(builder, points, uvs, material)

    ia0, ia1, ic0, ic1 = inner
    oa0, oa1, oc0, oc1 = outer
    low = top - CHAMFER
    emit([(ia0, ic0, top), (ia1, ic0, top), (ia1, ic1, top), (ia0, ic1, top)])
    emit([(oa0, oc0, low), (oa1, oc0, low), (ia1, ic0, top), (ia0, ic0, top)])
    emit([(oa1, oc0, low), (oa1, oc1, low), (ia1, ic1, top), (ia1, ic0, top)])
    emit([(oa1, oc1, low), (oa0, oc1, low), (ia0, ic1, top), (ia1, ic1, top)])
    emit([(oa0, oc1, low), (oa0, oc0, low), (ia0, ic0, top), (ia0, ic1, top)])


def _upward(builder, points, uvs, material):
    """Polígono voltado para cima: se a normal sai invertida (conforme o sentido da tábua), inverte a ordem."""
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = points[:3]
    normal_z = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    if normal_z < 0:
        points, uvs = points[::-1], uvs[::-1]
    builder.poly(points, material, uvs)


def build_level_floors(ctx, level, collection):
    """Um objeto por tipo de piso: o som dos passos lê `sa_surface` do objeto."""
    z = layout.LEVEL_Z[level]
    rng = random.Random(f"floors:{ctx.seed}:{level}")
    builders = {}
    for room_id, rect in layout.floor_rects(level):
        room = layout.ROOMS[room_id]
        builder = builders.setdefault(room.surface, floor_builder(f"Floor_L{level}_{room.surface}"))
        add_room_floor(builder, rect, z, room.floor_mat, rng)
    objects = []
    for surface, builder in builders.items():
        obj = builder.build(ctx, collection, collision=True)
        obj["sa_surface"] = surface
        objects.append(obj)
    return objects
