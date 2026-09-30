"""Roteiro das cinco cutscenes: só dados (planos, câmeras, legendas, ações).

Toda posição vem de `layout` (âncoras, aberturas, jogador, entidade, rua, Sol Negro); assim a cutscene
acompanha a casa se alguma medida mudar. Textos vêm de `story.CUTSCENE_TEXT` por índice: mudar a ordem
lá sem atualizar aqui quebra o teste `test_cutscenes_player.py`.

Convenção de tempos: dentro de um `Shot`, relativos ao começo do plano; em `Cutscene.cues/tracks`,
absolutos em segundos.
"""
import math

from .. import conventions as C
from .. import layout, story
from . import actions as act
from .timeline import Cue, Cutscene, Line, Shot, Track, View

ROAD_FACING = 0.0                  # yaw da entidade parada na rua: olha para +Y, para a casa
CLOCK_NAMES = ("alarm", "despert", "relogio")    # nomes que o módulo props pode ter dado ao despertador (hoje: AlarmClock)
EYE = C.PLAYER_EYE_STAND
FLOOR_1 = layout.LEVEL_Z[1]
GAMEPLAY_FOV = C.FOV_DEG

CLOCK_GLOW = "CutLight_ClockGlow"
BED_LAMP = "CutLight_BedLamp"
DAWN_LIGHT = "CutLight_Dawn"
DAWN_GLOW = "Cut_DawnGlow"
END_CLOCK = "Cut_EndClock"
ROAD_LIGHT = "CutLight_Road"
CORRIDOR_RIM = "CutLight_CorridorRim"


# --------------------------------------------------------------------------
# Geometria derivada da planta
# --------------------------------------------------------------------------
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


def gameplay_view(eye, yaw):
    """A vista exata da câmera do jogador: olhos, horizonte à frente, FOV do jogo."""
    return View(eye, ahead(eye, yaw, 6.0), GAMEPLAY_FOV)


# --------------------------------------------------------------------------
# INTRO
# --------------------------------------------------------------------------
def build_intro():
    clock = anchor("nightstand_clock", dz=0.62)
    bed = layout.ANCHORS["bed_master"]
    # o despertador olha para +X: a câmera precisa estar a leste dele, na borda norte da cama
    lying_eye = (1.15, 8.50, bed.z + 0.86)
    near_clock_eye = (0.82, 8.60, bed.z + 0.77)
    sitting_eye = (bed.x - 0.30, bed.y + 0.25, bed.z + 1.40)
    window_eye = window_vantage("w_master_n")
    radio_eye = (1.05, 8.55, bed.z + 0.95)
    start_eye = (layout.PLAYER_START[0], layout.PLAYER_START[1], layout.PLAYER_START[2] + EYE)
    start_yaw = math.radians(layout.PLAYER_START_YAW_DEG)

    shots = (
        Shot(3.6, View(lying_eye, clock, 44.0), handheld=0.08,
             fade=((0.0, 1.0), (2.4, 1.0), (3.5, 0.0)), letterbox=((0.0, 0.0), (2.0, 1.0)),
             cues=(Cue(0.0, act.power(False)),
                   Cue(0.0, act.cut_light(CLOCK_GLOW, 5.0)),
                   Cue(0.5, act.sound("alarm_beep", clock, 0.5)),
                   Cue(1.3, act.sound("alarm_beep", clock, 0.5)))),
        Shot(5.4, View(lying_eye, clock, 44.0), View(near_clock_eye, clock, 34.0), handheld=0.10,
             lines=(say("intro", 0, 0.5, 3.4),),
             cues=(Cue(3.0, act.loop("radio", "amb_radio_static", 0.25)),)),
        Shot(7.0, View(near_clock_eye, clock, 34.0), View(sitting_eye, toward_sun(sitting_eye), 58.0),
             handheld=0.22, lines=(say("intro", 1, 1.0, 4.6),),
             cues=(Cue(0.6, act.sound("flash_on", None, 0.5)), Cue(0.6, act.cut_light(BED_LAMP, 28.0)))),
        Shot(8.5, View(sitting_eye, toward_sun(sitting_eye), 58.0), View(window_eye, toward_sun(window_eye), 42.0),
             handheld=0.30,
             lines=(say("intro", 2, 0.4, 4.4), say("intro", 3, 4.9, 7.9)),
             cues=(Cue(3.0, act.sound("creak_1", window_eye, 0.5)),)),
        Shot(6.0, View(window_eye, toward_sun(window_eye), 42.0), View(radio_eye, clock, 38.0),
             ease="smoother", handheld=0.28, lines=(say("intro", 4, 0.6, 5.6),),
             cues=(Cue(0.2, act.loop("radio", "amb_radio_static", 0.75)),
                   Cue(0.2, act.cut_light(CLOCK_GLOW, 5.0))),
             shake=((0.0, 0.0), (3.5, 0.30), (6.0, 0.10))),
        Shot(6.5, View(radio_eye, clock, 38.0), gameplay_view(start_eye, start_yaw), handheld=0.15,
             lines=(say("intro", 5, 1.0, 5.6),),
             cues=(Cue(0.8, act.sound("flash_on", None, 0.5)), Cue(0.8, act.power(True, 0.3)),
                   Cue(4.4, act.stop_loop("radio")),
                   Cue(6.45, act.cut_light(CLOCK_GLOW, 0.0)),
                   Cue(6.45, act.place_player(layout.PLAYER_START[0], layout.PLAYER_START[1],
                                              layout.PLAYER_START[2], start_yaw))),
             letterbox=((4.6, 1.0), (6.4, 0.0))),
    )
    return Cutscene("intro", "intro_done", shots, initial={"fade": 1.0})


# --------------------------------------------------------------------------
# BLACKOUT
# --------------------------------------------------------------------------
def blackout_vantage():
    """Onde o jogador fica durante o apagão: no corredor, a ~4,5 m da entidade, longe da abertura da escada."""
    hall = layout.ROOMS["hall_u"].rect
    sight = layout.ENTITY_FIRST_SIGHT
    return (hall.x1 - 1.0, sight[1] - 4.5, sight[2])


def build_blackout():
    vantage = blackout_vantage()
    sight = layout.ENTITY_FIRST_SIGHT
    eye = (vantage[0], vantage[1], vantage[2] + EYE)
    face_yaw = yaw_of(vantage, sight)
    entity_yaw = yaw_of(sight, vantage)
    entity_head = (sight[0], sight[1], sight[2] + 2.5)
    wall_glance = (sight[0] - 3.0, sight[1] + 0.2, sight[2] + 1.6)      # para onde ele "olha" antes de notar o jogador

    def player_eye(stage):
        return stage.player.eye

    def player_ahead(stage):
        return stage.player.ahead(3.0)

    def player_glance(stage):
        return stage.player.ahead(3.0, stage.player.eye_z - 0.35)

    shots = (
        Shot(3.2, View(player_eye, player_ahead, GAMEPLAY_FOV), View(player_eye, player_glance, GAMEPLAY_FOV),
             handheld=0.2, lines=(say("blackout", 0, 0.6, 2.5),), letterbox=((0.0, 0.0), (1.2, 1.0)),
             cues=(Cue(0.1, act.power(True, 0.65)), Cue(0.5, act.sound("creak_1", None, 0.6)),
                   Cue(2.6, act.sound("blackout_thunk", None, 1.0)),
                   Cue(2.6, act.power(False)), Cue(2.6, act.flashlight(False)),
                   Cue(2.6, act.cut_light(CORRIDOR_RIM, 0.0))),
             fade=((2.55, 0.0), (2.62, 1.0)), shake=((2.5, 0.0), (2.6, 0.6), (3.2, 0.0))),
        Shot(4.0, View(eye, entity_head, GAMEPLAY_FOV), handheld=0.12,
             lines=(say("blackout", 1, 1.4, 3.6),),
             cues=(Cue(0.05, act.place_player(vantage[0], vantage[1], vantage[2], face_yaw)),
                   Cue(0.05, act.entity_place(sight, entity_yaw, "stare", 0.0)),
                   Cue(0.1, act.silence(9.0)),
                   Cue(1.6, act.loop("heartbeat", "heartbeat", 0.5))),
             fade=((0.0, 1.0), (1.0, 1.0), (2.6, 0.0))),
        Shot(4.5, View(eye, entity_head, GAMEPLAY_FOV), View(eye, entity_head, 46.0), handheld=0.15,
             lines=(say("blackout", 2, 0.9, 4.2),),
             cues=(Cue(0.3, act.entity_eyes(0.55)), Cue(0.45, act.entity_eyes(0.0)),
                   Cue(0.7, act.entity_eyes(1.0)), Cue(0.7, act.sound("ent_stinger", sight, 0.8)),
                   Cue(0.75, act.entity_anim("twitch")),
                   Cue(0.75, act.cut_light(CORRIDOR_RIM, 6.0)),
                   Cue(2.0, act.flashlight(True)), Cue(2.12, act.flashlight(False)),
                   Cue(2.5, act.flashlight(True)), Cue(2.65, act.flashlight(False))),
             shake=((0.0, 0.05), (2.0, 0.25), (4.5, 0.10))),
        Shot(5.0, View(eye, entity_head, 46.0), View(eye, entity_head, 34.0), handheld=0.28,
             cues=(Cue(0.2, act.entity_anim("stare")),
                   Cue(1.0, act.sound("ent_breath", sight, 0.7)),
                   Cue(2.2, act.flashlight(True)),
                   Cue(2.6, act.sound("ent_whisper", sight, 0.6))),
             shake=((0.0, 0.10), (5.0, 0.35))),
        Shot(4.5, View(eye, entity_head, 34.0), gameplay_view(eye, face_yaw), ease="smoother", handheld=0.2,
             lines=(say("blackout", 3, 0.4, 4.0),),
             cues=(Cue(0.0, act.flashlight(True)),
                   Cue(4.4, act.stop_loop("heartbeat")),
                   Cue(4.45, act.activate_brain())),
             letterbox=((3.4, 1.0), (4.4, 0.0)), shake=((0.0, 0.35), (4.5, 0.0))),
    )
    starts = [sum(shot.duration for shot in shots[:i]) for i in range(len(shots))]
    looks = (Track(starts[1] + 0.05, starts[3] + 0.4, act.entity_look(wall_glance), "linear"),
             Track(starts[3] + 0.4, starts[4] + 4.4, act.entity_look(eye, rate=70.0), "linear"))
    return Cutscene("blackout", "blackout_done", shots, initial={"fade": 0.0}, tracks=looks)


# --------------------------------------------------------------------------
# GARAGE_UNLOCK
# --------------------------------------------------------------------------
def build_garage_unlock():
    handle, side = door_handle("garage_door", "kitchen")

    def offset(dist_side, along, dz):
        return (handle[0] + side[0] * dist_side, handle[1] + side[1] * dist_side + along, handle[2] + dz)

    lock_far = offset(0.75, -0.12, 0.10)
    lock_near = offset(0.42, -0.06, 0.05)
    door_mid = layout.OPENINGS["garage_door"].mid
    door_focus = (door_mid[0], door_mid[1], 1.15)
    hall_door = layout.OPENINGS["kitchen_hall"].mid

    def player_eye(stage):
        return stage.player.eye

    def look_up(stage):
        x, y, z = stage.player.eye
        return (x + 0.6, y - 0.3, z + 1.7)

    def look_hall(stage):
        return (hall_door[0], hall_door[1], stage.player.eye_z - 0.1)

    def final_yaw(stage):
        p = stage.player
        return yaw_of((p.x, p.y), (hall_door[0], hall_door[1]))

    shots = (
        Shot(2.6, View(lock_far, handle, 42.0), View(lock_near, handle, 38.0), handheld=0.12,
             letterbox=((0.0, 0.0), (0.8, 1.0)),
             cues=(Cue(0.3, act.sound("key_jingle", handle, 0.8)),)),
        Shot(1.6, View(lock_near, handle, 38.0), View(lock_near, handle, 33.0), handheld=0.08,
             cues=(Cue(0.4, act.sound("door_unlock", handle, 1.0)),)),
        Shot(4.0, View(player_eye, door_focus, 62.0), View(player_eye, door_focus, 56.0), handheld=0.2,
             lines=(say("garage_unlock", 0, 0.5, 2.2),),
             cues=(Cue(0.2, act.sound("door_creak_long", door_focus, 0.7)),),
             tracks=(Track(0.2, 3.4, act.door_openness("garage_door"), "smooth"),)),
        Shot(3.3, View(player_eye, door_focus, 56.0), View(player_eye, look_up, 66.0), ease="in", handheld=0.3,
             lines=(say("garage_unlock", 1, 0.5, 2.9),),
             cues=(Cue(0.15, act.sound("ent_door_break", None, 1.0)),
                   Cue(0.15, act.sound("thud_2", None, 0.9)),
                   Cue(0.5, act.silence(3.0))),
             shake=((0.1, 0.0), (0.2, 0.9), (3.3, 0.15)), flash=((0.12, 0.0), (0.2, 0.25), (0.6, 0.0))),
        Shot(3.2, View(player_eye, look_up, 66.0), View(player_eye, look_hall, GAMEPLAY_FOV),
             ease="smoother", handheld=0.25, lines=(say("garage_unlock", 2, 0.5, 2.7),),
             cues=(Cue(2.9, act.place_player(lambda st: st.player.x, lambda st: st.player.y,
                                             lambda st: st.player.z, final_yaw)),
                   Cue(3.0, act.activate_brain())),
             letterbox=((2.2, 1.0), (3.1, 0.0)), shake=((0.0, 0.15), (3.2, 0.0))),
    )
    return Cutscene("garage_unlock", "unlock_done", shots)


# --------------------------------------------------------------------------
# DEATH
# --------------------------------------------------------------------------
def build_death():
    def eye(stage):
        return stage.player.eye

    def entity_head_now(stage):
        return stage.entity_head()

    def player_ahead(stage):
        return stage.player.ahead(2.0)

    def face(stage):
        """Onde o rosto vai parar: à frente dos olhos, na direção da entidade."""
        ex, ey, ez = stage.player.eye
        hx, hy, _ = stage.entity_head()
        dx, dy = hx - ex, hy - ey
        length = math.hypot(dx, dy) or 1.0
        return (ex + dx / length * 0.42, ey + dy / length * 0.42, ez)

    shots = (
        Shot(0.75, View(eye, player_ahead, 68.0), View(eye, entity_head_now, 58.0), ease="out", handheld=0.5,
             cues=(Cue(0.0, act.entity_eyes(1.0)), Cue(0.0, act.entity_anim("attack")),
                   Cue(0.05, act.sound("ent_scream", None, 1.0)), Cue(0.05, act.silence(6.0))),
             shake=((0.0, 0.35), (0.75, 0.6))),
        Shot(0.7, View(eye, entity_head_now, 58.0), View(eye, face, 46.0), ease="in", handheld=0.6,
             tracks=(Track(0.0, 0.62, act.entity_lunge(eye), "in"),),
             cues=(Cue(0.55, act.sound("death_hit", None, 1.0)),),
             flash=((0.5, 0.0), (0.62, 0.8), (1.0, 0.0)), shake=((0.0, 0.6), (0.62, 1.0))),
        Shot(1.7, View(eye, face, 46.0), View(eye, face, 36.0), handheld=0.7,
             cues=(Cue(0.2, act.sound("ent_static_burst", None, 0.8)),
                   Cue(0.4, act.entity_eyes(1.0))),
             shake=((0.0, 1.0), (1.7, 1.0))),
        Shot(1.5, View(eye, face, 36.0), handheld=0.0,
             cues=(Cue(0.0, act.sound("death_hit", None, 1.0)), Cue(0.0, act.stop_all()),
                   Cue(1.3, act.entity_hide())),
             fade=((0.0, 0.0), (0.001, 1.0)), shake=((0.0, 0.0), (0.001, 0.0)), flash=((0.0, 0.0), (0.001, 0.0))),
    )
    return Cutscene("death", "death_done", shots)


# --------------------------------------------------------------------------
# ENDING
# --------------------------------------------------------------------------
def build_ending():
    car = layout.ANCHORS["car"]
    car_home = (car.x, car.y, car.z)
    driver_eye = anchor("car_driver_eye")
    eye_offset = tuple(d - c for d, c in zip(driver_eye, car_home))
    road = layout.ENTITY_ROAD_POS
    car_stop = (car.x, road[1] + 6.4, car.z)
    rollup = layout.OPENINGS["garage_rollup"]
    rollup_mid = (rollup.mid[0], rollup.pos, 1.1)
    lift = 2.3

    clock = anchor("nightstand_clock", dz=0.62)
    bed = layout.ANCHORS["bed_master"]
    near_clock_eye = (0.60, 8.15, bed.z + 0.70)
    close_clock_eye = (0.66, 8.45, bed.z + 0.67)
    sitting_eye = (bed.x - 0.35, bed.y + 0.15, bed.z + 1.35)
    window_eye = window_vantage("w_master_n")

    ignition = add(driver_eye, (-0.05, -0.55, -0.42))
    dashboard = add(driver_eye, (-0.45, -1.4, -0.2))
    road_horizon = (car.x, road[1] - 12.0, driver_eye[2] - 0.05)
    entity_head = (road[0], road[1], road[2] + 2.48)
    exterior_eye = (car.x - 5.5, -4.6, 1.25)
    entity_yaw = ROAD_FACING

    def in_car(view_target, fov):
        return View(driver_eye, view_target, fov)

    shots = (
        Shot(7.0, in_car(ignition, 56.0), in_car(dashboard, 60.0), handheld=0.16,
             fade=((0.0, 1.0), (1.4, 0.0)), letterbox=((0.0, 0.0), (1.5, 1.0)),
             lines=(say("ending", 0, 1.8, 6.4),),
             cues=(Cue(0.4, act.sound("car_door", driver_eye, 0.9)),
                   Cue(1.7, act.sound("key_jingle", driver_eye, 0.7)),
                   Cue(3.0, act.sound("car_start", driver_eye, 1.0)),
                   Cue(3.6, act.loop("engine", "car_idle", 0.7)))),
        Shot(5.5, in_car(dashboard, 60.0), in_car(rollup_mid, 62.0), ease="smoother", handheld=0.2,
             cues=(Cue(0.4, act.sound("garage_rollup", rollup_mid, 1.0)),
                   Cue(3.4, act.headlights(True)),
                   Cue(3.4, act.cut_light(ROAD_LIGHT, 30.0)))),
        Shot(5.0, View(exterior_eye, (car.x, 0.8, 1.0), 62.0), View(exterior_eye, (car.x, -5.5, 1.0), 56.0),
             handheld=0.14, ease="smooth",
             lines=(say("ending", 1, 0.6, 4.6),),
             cues=(Cue(0.0, act.entity_place(road, entity_yaw, "stare", 0.0, erect=True)),)),
        Shot(5.0, in_car(road_horizon, 62.0), in_car(entity_head, 58.0), follow="Car", handheld=0.2, ease="smooth"),
        Shot(8.5, in_car(entity_head, 58.0), in_car(entity_head, 40.0), follow="Car", handheld=0.32,
             lines=(say("ending", 2, 1.4, 6.6),),
             cues=(Cue(0.2, act.sound("ent_stinger", road, 0.9)),
                   Cue(6.9, act.sound("ent_static_burst", None, 1.0))),
             tracks=(Track(0.0, 1.8, act.eyes_ramp(0.0, 1.0), "smooth"),),
             shake=((0.0, 0.1), (6.6, 0.5), (8.5, 0.9)),
             flash=((6.9, 0.0), (7.5, 1.0))),
        Shot(4.0, View(near_clock_eye, clock, 34.0), View(close_clock_eye, clock, 32.0), handheld=0.10,
             lines=(say("ending", 3, 0.9, 2.5),),
             flash=((0.0, 1.0), (0.7, 1.0), (2.8, 0.0)),
             cues=(Cue(0.0, act.stop_loop("engine")), Cue(0.0, act.entity_hide()),
                   Cue(0.0, act.headlights(False)), Cue(0.0, act.cut_light(ROAD_LIGHT, 0.0)),
                   Cue(0.0, act.hide_matching(anchor("nightstand_clock", dz=0.45), 0.55, CLOCK_NAMES)),
                   Cue(0.0, act.show(END_CLOCK)),
                   Cue(0.0, act.cut_light(CLOCK_GLOW, 4.0)))),
        Shot(5.0, View(close_clock_eye, clock, 32.0), View(sitting_eye, toward_sun(sitting_eye), 52.0),
             ease="smoother", handheld=0.2, lines=(say("ending", 4, 0.5, 3.0),)),
        Shot(6.5, View(sitting_eye, toward_sun(sitting_eye), 52.0), View(window_eye, toward_sun(window_eye), 40.0),
             handheld=0.24),
        Shot(8.0, View(window_eye, toward_sun(window_eye), 40.0), View(window_eye, toward_sun(window_eye), 38.0),
             handheld=0.2, fade=((0.0, 0.0), (2.4, 1.0)), card=((2.4, 0.0), (3.6, 1.0)),
             letterbox=((5.5, 1.0), (7.0, 0.0))),
    )
    starts = {}
    t = 0.0
    for index, shot in enumerate(shots):
        starts[index] = t
        t += shot.duration
    dawn_start = starts[5]
    tracks = (
        Track(starts[1] + 0.6, starts[1] + 4.6, act.lift_object(C.OBJ_GARAGE_ROLLUP, 0.0, lift), "smooth"),
        Track(starts[1] + 3.2, starts[4] - 1.5, act.move_object(C.OBJ_CAR, car_home, car_stop), "smooth"),
        Track(dawn_start, dawn_start + 20.0, act.light_ramp(DAWN_LIGHT, 0.0, 90.0), "linear"),
    )
    cues = (Cue(dawn_start, act.show(DAWN_GLOW)),)
    return Cutscene("ending", "ending_done", shots, card=story.ENDING_CARD, initial={"fade": 1.0},
                    tracks=tracks, cues=cues)


BUILDERS = {
    "intro": build_intro,
    "blackout": build_blackout,
    "garage_unlock": build_garage_unlock,
    "death": build_death,
    "ending": build_ending,
}

NAMES = tuple(BUILDERS)
_built = {}


def get(name):
    """Devolve a cutscene `name` (montada uma vez só)."""
    if name not in BUILDERS:
        raise KeyError(f"cutscene desconhecida: {name!r}; use uma de {NAMES}")
    if name not in _built:
        _built[name] = BUILDERS[name]()
    return _built[name]
