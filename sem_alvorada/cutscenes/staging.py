"""Geometria e atalhos de roteiro compartilhados pelas cinco cutscenes.

Toda posição vem de `layout` (âncoras, aberturas, jogador, entidade, rua, Sol Negro); assim a cutscene
acompanha a casa se alguma medida mudar. Textos vêm de `story.CUTSCENE_TEXT` por índice: mudar a ordem
lá sem atualizar os roteiros quebra o teste `test_cutscenes_player.py`.
"""
import math

from .. import conventions as C
from .. import layout, story
from .curves import Curve, Key, Path, walk_keys
from .timeline import Cue, Line
from . import actions as act

EYE = C.PLAYER_EYE_STAND
GAMEPLAY_FOV = C.FOV_DEG
ROAD_FACING = 0.0                  # yaw da entidade parada na rua: olha para +Y, para a casa
CLOCK_NAMES = ("alarm", "despert", "relogio")    # nomes que o módulo props pode ter dado ao despertador (hoje: AlarmClock)

CLOCK_GLOW = "CutLight_ClockGlow"
BED_LAMP = "CutLight_BedLamp"
DAWN_LIGHT = "CutLight_Dawn"
END_CLOCK = "Cut_EndClock"
ROAD_LIGHT = "CutLight_Road"
DRIVEWAY_LIGHT = "CutLight_Driveway"
CAR_CABIN = "CutLight_CarCabin"
CORRIDOR_RIM = "CutLight_CorridorRim"
MASTER_CURTAINS = ("Curtain_w_master_n", "Curtain_w_master_w")


def anchor(name, dx=0.0, dy=0.0, dz=0.0):
    a = layout.ANCHORS[name]
    return (a.x + dx, a.y + dy, a.z + dz)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def yaw_of(a, b):
    """Yaw do Blender de quem está em `a` olhando para `b`."""
    return C.dir_yaw(b[0] - a[0], b[1] - a[1])


def ahead(eye, yaw, distance, z=None):
    dx, dy = C.yaw_dir(yaw)
    return (eye[0] + dx * distance, eye[1] + dy * distance, eye[2] if z is None else z)


def sun_direction():
    az = math.radians(layout.SUN_RING["azimuth_deg"])
    el = math.radians(layout.SUN_RING["elevation_deg"])
    return (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))


def toward_sun(eye, distance=60.0):
    return add(eye, tuple(c * distance for c in sun_direction()))


def window_center(op_id):
    op = layout.OPENINGS[op_id]
    mid_x, mid_y = op.mid
    return (mid_x, mid_y, layout.LEVEL_Z[op.level] + op.sill + op.height / 2)


def window_vantage(op_id, back=1.6, eye_z=None):
    """Onde ficar (dentro do quarto) para ver o Sol Negro pelo centro da janela `op_id`.

    O raio parte do Sol, cruza o centro da janela e chega aos olhos depois de `back` metros; falha alto
    se, com a planta atual, o Sol deixaria de aparecer pela janela.
    """
    op = layout.OPENINGS[op_id]
    sun = sun_direction()
    cx, cy, cz = window_center(op_id)
    eye_z = layout.LEVEL_Z[op.level] + EYE if eye_z is None else eye_z
    eye = (cx - sun[0] * back, cy - sun[1] * back, eye_z)
    crossing_z = eye_z + sun[2] * back
    top = layout.LEVEL_Z[op.level] + op.sill + op.height
    if not (layout.LEVEL_Z[op.level] + op.sill < crossing_z < top):
        raise ValueError(f"o Sol não aparece pela janela {op_id} a partir de z={eye_z}")
    return eye


def say(name, index, start, end):
    return Line(story.CUTSCENE_TEXT[name][index], start, end)


def door_handle(op_id, side_room):
    """Centro do trinco de uma porta fechada e a direção (+-1 em X ou Y) do lado onde fica `side_room`."""
    op = layout.OPENINGS[op_id]
    frame = layout.door_transform(op)
    hx, hy, _ = frame["hinge"]
    reach = frame["width"] - 0.14
    handle = (hx + math.cos(frame["closed_yaw"]) * reach, hy + math.sin(frame["closed_yaw"]) * reach, 1.0)
    room = layout.ROOMS[side_room].rect
    cx, cy = room.center
    if op.axis == "y":
        side = (-1.0, 0.0) if cx < op.pos else (1.0, 0.0)
    else:
        side = (0.0, -1.0) if cy < op.pos else (0.0, 1.0)
    return handle, side


def player_eye(stage):
    return stage.player.eye


def player_gaze(stage):
    return stage.player.gaze()


# --------------------------------------------------------------------------
# Atalhos de câmera
# --------------------------------------------------------------------------
def path(*keys, rest=True, tension=1.0):
    """Caminho 3D: cada chave é `(t, ponto)` ou `(t, ponto, True)` (a câmera para ali)."""
    return Path([Key(*k) if not isinstance(k, Key) else k for k in keys], rest_ends=rest, tension=tension)


def curve(*keys, rest=True):
    return Curve([Key(*k) if not isinstance(k, Key) else k for k in keys], rest_ends=rest)


def blink(*times_and_values):
    """Chaves densas de uma curva suave (as curvas de efeito do timeline são lineares): (t, v) com smoothstep entre elas."""
    keys = []
    for (t0, v0), (t1, v1) in zip(times_and_values, times_and_values[1:]):
        steps = max(2, int((t1 - t0) / 0.05))
        for k in range(steps):
            u = k / steps
            keys.append((t0 + (t1 - t0) * u, v0 + (v1 - v0) * u * u * (3 - 2 * u)))
    keys.append(times_and_values[-1])
    return tuple(keys)


def step_cues(rig, t0, t1, names, volume=0.5, offset=0.0):
    """Um `Cue` de som de passo a cada passo que a câmera de `rig` (com `walk=True`) dá entre `t0` e `t1` (tempo do plano)."""
    cues, count = [], 0
    previous, _ = rig.step_phase(t0, None)
    t = t0
    while t < t1:
        t += 0.02
        phase, gain = rig.step_phase(t, None)
        if gain > 0.2 and int(phase) > int(previous):
            cues.append(Cue(t + offset, act.sound(names[count % len(names)], None, volume)))
            count += 1
        previous = phase
    return tuple(cues)
