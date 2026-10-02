"""ENDING (~38 s): a chave na ignição, o motor, o portão subindo, o carro saindo, o Alto na rua e a manhã que quase chega.

Batidas (tempo absoluto, s):
     0.0  o escuro some; a câmera nos olhos do motorista, sobre a fechadura; o chaveiro com o coelhinho
     2.2  a chave gira, o motor de arranque (os faróis caem de tensão); 3.5 o motor pega: o painel acende, tudo vibra
     3.7  a câmera sobe até o para-brisa; o coelhinho do retrovisor balança; 5.0 o portão de enrolar sobe (mola e abridor)
     8.4  corte para fora: o carro sai da garagem na rampa, suspensão e rodas, os faróis varrendo o jardim
    12.8  de volta aos olhos do motorista: o carro para; o Alto está na rua, no feixe dos faróis; a lente fecha
    18.0  estática, flash branco
    19.4  o despertador marca 6:12; a câmera sobe da cama, a janela está um pouco mais clara; o cartão final
"""
import math

from .. import conventions as C
from .. import layout
from . import actions as act
from . import anim
from .camera import Hand, Impact, Rig, axis_rotation
from .curves import Curve, Key, Path
from .staging import (BED_LAMP, CAR_CABIN, CLOCK_GLOW, CLOCK_NAMES, DAWN_LIGHT, DRIVEWAY_LIGHT, END_CLOCK,
                      MASTER_CURTAINS, ROAD_FACING, ROAD_LIGHT, add, anchor, blink, curve, path, say, toward_sun,
                      window_vantage)
from .timeline import Cue, Cutscene, Shot, Track
from .. import story

SHOT_A, SHOT_X, SHOT_B, SHOT_C = 0.0, 8.4, 12.8, 19.4
TOTAL = 38.0
CRANK, CATCH = 2.2, 3.5
ROLLUP_START, ROLLUP_SECONDS = 5.0, 3.0
MOVE_START, MOVE_END = 8.4, 15.6
DRIVER_END = SHOT_C

DRIVER = (-0.45, -0.55, 1.20)                     # olhos do motorista, no espaço do carro
LOCK = (-0.38, 0.22, 0.835)                       # topo da fechadura da ignição
CLUSTER = (-0.45, 0.40, 0.80)
MIRROR = (0.04, 0.30, 1.19)
AHEAD = (-0.10, 3.2, 1.22)


def dash_level(t):
    """Painel e mostrador: apagados, tremem com a bateria na partida e firmam quando o motor pega."""
    if t < CRANK:
        return 0.04
    if t < CATCH:
        return 0.15 + 0.35 * (0.5 + 0.5 * math.sin((t - CRANK) * 29.0))
    ramp = min(1.0, (t - CATCH) / 0.5)
    return 0.3 + 0.7 * ramp * (0.94 + 0.06 * math.sin(t * 1.7))


def key_rotation(t, stage):
    turn = -math.radians(58.0) * min(1.0, max(0.0, (t - 2.05) / 0.45))
    return axis_rotation("z", turn)


def build():
    car = layout.ANCHORS["car"]
    car_home = (car.x, car.y, car.z)
    road = layout.ENTITY_ROAD_POS
    car_stop = (car.x, road[1] + 6.0, car.z - 0.054)
    chest = (road[0], road[1], road[2] + 1.55)
    entity_head = (road[0], road[1], road[2] + 2.5)

    def figure(stage):
        return stage.to_local("Car", chest)

    def car_point(dx=0.0, dy=0.0, dz=0.0):
        return lambda st: add(st.mount_transform("Car")[0], (dx, dy, dz))

    # ---------------------------------------------------------------- A: ignição e painel (nos olhos do motorista)
    rig_a = Rig(
        eye=path((0.0, DRIVER, True), (3.2, (-0.45, -0.55, 1.215)), (6.0, (-0.45, -0.54, 1.25)), (SHOT_X, (-0.45, -0.55, 1.25), True)),
        look=path((0.0, LOCK, True), (2.9, LOCK), (3.9, CLUSTER), (5.2, add(AHEAD, (0.0, 0.0, -0.05))), (6.6, add(AHEAD, (0.0, 0.0, 0.05))),
                  (SHOT_X, add(AHEAD, (0.0, 0.0, 0.0)), True)),
        fov=curve((0.0, 58.0), (3.0, 52.0), (3.9, 56.0), (5.6, 66.0), (SHOT_X, 70.0)),
        roll=curve((0.0, 4.0), (3.4, 1.0), (5.5, 0.0), (SHOT_X, 0.0)),
        hand=Hand("drive", Curve([(0.0, 1.2), (3.5, 1.0), (SHOT_X, 0.8)])),
        impacts=(Impact(CATCH, 1.5, 9.0, 4.0, 0.7),),
        focus=curve((0.0, 0.85), (3.0, 0.8), (4.0, 0.72), (5.6, 3.2), (SHOT_X, 3.6)),
        fstop=curve((0.0, 2.0), (3.0, 2.0), (5.6, 4.0), (SHOT_X, 5.6)),
        mount=C.OBJ_CAR)
    cues_a = (
        Cue(0.0, act.body_show(True)),
        Cue(0.0, act.body_pose("driving")),
        Cue(0.0, act.cut_light(CAR_CABIN, 35.0)),
        Cue(0.0, act.actor("car", lambda st: anim.CarMotion(car_home, car_stop, MOVE_START, MOVE_END, crank_start=CRANK,
                                                              catch=CATCH, lights_on=CRANK))),
        Cue(0.0, act.actor("bunny", lambda st: anim.CharmPendulum("Cut_Bunny", 0.2, 0.5, "car"))),
        Cue(0.0, act.actor("wheel", lambda st: anim.SteeringWheel("Cut_Wheel"))),
        Cue(0.0, act.actor("key", lambda st: anim.PropPath(
            "Cut_Key", Path([Key(1.2, add(LOCK, (-0.11, -0.12, 0.13))), Key(1.9, LOCK, True), Key(DRIVER_END, LOCK, True)]),
            key_rotation, 1.2, 19.1, also=("Cut_KeyCharm",), mount=C.OBJ_CAR))),
        Cue(0.0, act.actor("key_charm", lambda st: anim.CharmPendulum("Cut_KeyCharm", 0.07, 0.35, "car"))),
        Cue(0.0, act.actor("dash", lambda st: anim.EmissionPulse("car_cluster", dash_level))),
        Cue(0.0, act.actor("dash2", lambda st: anim.EmissionPulse("digits_dash", dash_level))),
        Cue(0.0, act.actor("dash3", lambda st: anim.EmissionPulse("car_radio", dash_level))),
        Cue(0.0, act.actor("rollup", lambda st: anim.GarageLift(ROLLUP_START, ROLLUP_SECONDS))),
        Cue(0.4, act.sound("car_door", None, 0.9)),
        Cue(1.2, act.sound("hand_reach", None, 0.4)),
        Cue(1.55, act.sound("key_jingle", None, 0.7)),
        Cue(CRANK, act.sound("car_start", None, 1.0)),
        Cue(CATCH, act.loop("engine", "car_idle", 0.7)),
        Cue(CATCH + 0.05, act.cut_light(CAR_CABIN, 0.0)),
        Cue(ROLLUP_START - 0.1, act.sound("garage_rollup", None, 1.0)),
        Cue(ROLLUP_START + 0.5, act.cut_light(DRIVEWAY_LIGHT, 2500.0)),
    )
    shot_a = Shot(SHOT_X - SHOT_A, cam=rig_a, name="ignicao", cues=cues_a,
                  lines=(say("ending", 0, 1.4, 4.4),),
                  fade=((0.0, 1.0), (1.3, 0.0)),
                  letterbox=((0.0, 0.0), (1.5, 1.0)),
                  shake=((CRANK, 0.0), (CRANK + 0.3, 0.35), (CATCH - 0.05, 0.4), (CATCH + 0.4, 0.0)))

    # ---------------------------------------------------------------- X: de fora, o carro sai da garagem
    dur_x = SHOT_B - SHOT_X
    exterior_eye = (car.x - 5.6, -4.3, 1.1)
    rig_x = Rig(
        eye=path((0.0, exterior_eye, True), (dur_x, add(exterior_eye, (0.9, -0.5, 0.1)), True)),
        look=path((0.0, car_point(0.0, -1.0, 0.9), True), (dur_x, car_point(0.0, -1.2, 0.8), True)),
        fov=curve((0.0, 54.0), (dur_x, 46.0)),
        hand=Hand("stand", 0.5),
        impacts=(Impact(1.7, 0.4, 5.0, 4.0, 5.0),),
        focus="auto", fstop=curve((0.0, 4.5), (dur_x, 4.5)))
    shot_x = Shot(dur_x, cam=rig_x, name="saida", cut=True,
                  cues=(Cue(0.0, act.entity_place(road, ROAD_FACING, "stare", 0.0, erect=True)),),
                  lines=(say("ending", 1, 1.0, 4.2),))

    # ---------------------------------------------------------------- B: a rua, o Alto, a estática
    dur_b = SHOT_C - SHOT_B
    rig_b = Rig(
        eye=path((0.0, (-0.45, -0.55, 1.25), True), (dur_b, (-0.45, -0.55, 1.25), True)),
        look=path((0.0, AHEAD, True), (1.4, AHEAD), (3.0, figure), (dur_b, figure, True)),
        fov=curve((0.0, 64.0), (2.0, 54.0), (4.5, 40.0), (dur_b, 30.0)),
        roll=curve((0.0, 0.0), (dur_b, 0.0)),
        hand=Hand("drive", Curve([(0.0, 0.7), (dur_b, 1.3)])),
        focus=curve((0.0, 3.2), (1.2, 0.9), (2.4, 0.9), (3.4, 6.0), (dur_b, 6.0)),
        fstop=curve((0.0, 4.0), (1.2, 2.0), (3.4, 2.8), (dur_b, 2.8)),
        mount=C.OBJ_CAR)
    cues_b = (
        Cue(0.0, act.cut_light(ROAD_LIGHT, 1800.0)),
        Cue(0.2, act.sound("ent_stinger", road, 0.9)),
        Cue(5.6, act.sound("ent_static_burst", None, 1.0)),
    )
    shot_b = Shot(dur_b, cam=rig_b, name="rua", cut=True, cues=cues_b,
                  lines=(say("ending", 2, 1.8, 5.4),),
                  tracks=(Track(1.2, 3.0, act.eyes_ramp(0.0, 1.0), "smooth"),),
                  shake=((0.0, 0.1), (3.4, 0.35), (5.6, 0.9), (dur_b, 0.9)),
                  flash=((5.6, 0.0), (6.4, 1.0)))

    # ---------------------------------------------------------------- C: 6:12, a janela mais clara, o cartão
    clock = anchor("nightstand_clock", dz=0.62)
    bed = layout.ANCHORS["bed_master"]
    dur_c = TOTAL - SHOT_C
    near_clock = (0.66, 8.45, bed.z + 0.67)
    sitting = (1.12, 8.42, 4.12)
    window = window_vantage("w_master_n")
    rig_c = Rig(
        eye=path((0.0, near_clock, True), (3.4, (0.82, 8.46, 3.62)), (7.0, sitting), (11.0, add(window, (-0.1, -0.3, 0.0))),
                 (dur_c, window, True)),
        look=path((0.0, clock, True), (2.6, clock), (5.0, (0.9, 9.4, 4.2)), (7.4, toward_sun(sitting)), (dur_c, toward_sun(window), True)),
        fov=curve((0.0, 32.0), (3.0, 34.0), (7.0, 52.0), (11.0, 46.0), (dur_c, 40.0)),
        roll=curve((0.0, 6.0), (3.0, 5.0), (6.0, 1.0), (dur_c, 0.0)),
        hand=(((0.0, Hand("lying", 1.0)), (4.0, Hand("sitting", 1.0)), (9.5, Hand("stand", 1.0)))),
        focus=curve((0.0, 0.55), (3.0, 0.55), (6.0, 2.0), (dur_c, 2.0)),
        fstop=curve((0.0, 2.2), (6.0, 3.6), (dur_c, 4.5)))
    cues_c = (
        Cue(0.0, act.stop_loop("engine")),
        Cue(0.0, act.entity_hide()),
        Cue(0.0, act.headlights(False)),
        Cue(0.0, act.cut_light(ROAD_LIGHT, 0.0)),
        Cue(0.0, act.cut_light(DRIVEWAY_LIGHT, 0.0)),
        Cue(0.0, act.hide_matching(anchor("nightstand_clock", dz=0.45), 0.55, CLOCK_NAMES)),
        Cue(0.0, act.show(END_CLOCK)),
        Cue(0.0, act.cut_light(CLOCK_GLOW, 4.0)),
        Cue(0.0, act.cut_light(BED_LAMP, 28.0)),
        Cue(0.0, act.body_pose("lying_bed")),
        Cue(0.0, act.actor("curtains", lambda st: anim.CurtainWind(MASTER_CURTAINS, 0.5, Curve([(0.0, 0.2), (dur_c, 0.8)])))),
        Cue(0.0, act.actor("dawn_light", lambda st: anim.EmissionPulse("cut_clock_digits", lambda t: 0.94 + 0.06 * math.sin(t * 1.3)))),
        Cue(3.0, act.body_pose("sit_bed", 2.4)),
        Cue(10.5, act.body_pose("stand", 1.4)),
    )
    tracks_c = (Track(0.0, 20.0, act.light_ramp(DAWN_LIGHT, 0.0, 90.0), "linear"),
                Track(4.0, 18.0, act.dawn_ramp(0.0, 1.0), "smooth"))
    shot_c = Shot(dur_c, cam=rig_c, name="amanha", cut=True, cues=cues_c, tracks=tracks_c,
                  lines=(say("ending", 3, 0.9, 2.5), say("ending", 4, 4.0, 6.6)),
                  flash=((0.0, 1.0), (0.7, 1.0), (2.8, 0.0)),
                  fade=((0.0, 0.0), (dur_c - 4.0, 0.0), (dur_c - 1.6, 1.0)),
                  card=((dur_c - 3.6, 0.0), (dur_c - 2.4, 1.0)),
                  letterbox=((0.0, 1.0), (dur_c - 1.8, 1.0), (dur_c, 0.0)))
    return Cutscene("ending", "ending_done", (shot_a, shot_x, shot_b, shot_c), card=story.ENDING_CARD,
                    initial={"fade": 1.0})

