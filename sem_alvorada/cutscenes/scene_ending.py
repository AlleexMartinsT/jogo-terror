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
from .body_actor import BodyDriver, BodyPose, HandActor, HandKey, root_for
from .scene_intro import LYING_EYE, SIT_EYE, SIT_YAW
from .camera import Hand, Impact, Rig, axis_rotation
from .curves import Curve, Key, Path
from .staging import (BED_LAMP, CAR_CABIN, CLOCK_GLOW, CLOCK_NAMES, DAWN_LIGHT, DRIVEWAY_LIGHT, END_CLOCK,
                      MASTER_CURTAINS, ROAD_FACING, ROAD_LIGHT, add, anchor, curve, looking, path, say,
                      toward_sun, window_vantage)
from .timeline import Cue, Cutscene, Shot, Track
from .. import story

SHOT_A, SHOT_X, SHOT_B, SHOT_C = 0.0, 8.4, 12.8, 19.4
TOTAL = 38.0
CRANK, CATCH = 2.2, 3.5
ROLLUP_START, ROLLUP_SECONDS = 5.0, 3.0
MOVE_START, MOVE_END = 8.4, 15.6
DRIVER_END = SHOT_C

DRIVER = (-0.45, -0.55, 1.22)                     # olhos do motorista sentado, no espaço do carro
LEAN = (-0.30, -0.30, 1.20)                       # inclinado sobre a coluna: o único ponto de onde o volante não esconde a fechadura
LOCK = (-0.38, 0.22, 0.845)                       # topo da fechadura da ignição
HUB = (-0.45, 0.13, 0.90)
BUNNY = (0.08, 0.265, 1.12)
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

    def figure_head(stage):
        return stage.to_local("Car", (road[0], road[1], road[2] + 2.05))

    def car_point(dx=0.0, dy=0.0, dz=0.0):
        return lambda st: add(st.mount_transform("Car")[0], (dx, dy, dz))

    # ---------------------------------------------------------------- A: ignição e painel (nos olhos do motorista)
    rig_a = Rig(
        eye=path((0.0, DRIVER, True), (1.2, LEAN), (3.0, LEAN), (4.3, add(DRIVER, (0.0, 0.0, 0.02))), (6.2, add(DRIVER, (0.0, 0.0, 0.03))),
                 (SHOT_X, add(DRIVER, (0.0, 0.0, 0.03)), True)),
        look=looking((0.0, HUB, True), (1.3, LOCK), (3.0, LOCK), (4.4, BUNNY), (5.5, BUNNY), (6.8, add(AHEAD, (0.0, 0.0, -0.1))),
                     (SHOT_X, AHEAD, True)),
        fov=curve((0.0, 58.0), (1.4, 50.0), (3.0, 50.0), (4.4, 56.0), (6.0, 64.0), (SHOT_X, 68.0)),
        roll=curve((0.0, 3.0), (1.3, 6.0), (3.0, 6.0), (4.5, 1.0), (6.0, 0.0), (SHOT_X, 0.0)),
        hand=Hand("drive", Curve([(0.0, 1.2), (3.5, 1.0), (SHOT_X, 0.8)])),
        impacts=(Impact(CATCH, 1.5, 9.0, 4.0, 0.7),),
        focus=curve((0.0, 0.9), (1.4, 0.55), (3.0, 0.55), (4.4, 1.15), (5.6, 1.15), (6.8, 3.2), (SHOT_X, 3.6)),
        fstop=curve((0.0, 2.0), (3.0, 2.0), (5.6, 3.2), (SHOT_X, 5.6)),
        mount=C.OBJ_CAR)
    # o motorista: sentado na pose "driving"; para alcançar a ignição o corpo todo se inclina para a frente com a câmera
    drive_root, lean_root = root_for("driving", DRIVER, 0.0), root_for("driving", LEAN, 0.0)
    peer_root = root_for("driving", (-0.40, -0.12, 1.12), 0.0)
    body_a = (BodyPose(0.0, "driving", 0.0, Path([Key(0.0, drive_root), Key(1.2, lean_root), Key(3.0, lean_root),
                                                     Key(4.4, drive_root), Key(SHOT_B + 0.4, drive_root),
                                                     Key(SHOT_B + 2.6, peer_root), Key(SHOT_C, peer_root)]), 0.0,
                       mount=C.OBJ_CAR),)
    rim = lambda angle: add(HUB, (0.19 * math.cos(angle), 0.19 * 0.423 * math.sin(angle), 0.19 * 0.906 * math.sin(angle)))  # noqa: E731

    def toward_hub(point):
        return (HUB[0] - point[0], HUB[1] - point[1], HUB[2] - point[2])
    left_rim, right_rim = rim(math.radians(150)), rim(math.radians(30))
    left_hand = HandActor("L", [HandKey(0.0, left_rim, fingers=(0.5, 0.37, 0.78), palm=toward_hub(left_rim), grip="grip_cylinder"),
                                HandKey(SHOT_X, left_rim, fingers=(0.5, 0.37, 0.78), palm=toward_hub(left_rim), grip="grip_cylinder")],
                          space=C.OBJ_CAR)
    key_hold = lambda t, dz=0.0: add(LOCK, (0.015, -0.01, 0.075 + dz))  # noqa: E731
    right_hand = HandActor("R", [
        HandKey(0.9, add(LOCK, (0.13, -0.17, 0.20)), fingers=(-0.5, 0.6, -0.6), palm=(-1.0, 0.0, -0.2), weight=0.0, grip="pinch"),
        HandKey(1.4, add(LOCK, (0.08, -0.10, 0.15)), fingers=(-0.5, 0.6, -0.6), palm=(-1.0, 0.0, -0.2), grip="pinch"),
        HandKey(1.9, key_hold(0.0), fingers=(-0.4, 0.6, -0.7), palm=(-1.0, 0.0, -0.2), grip="pinch"),
        HandKey(2.6, key_hold(0.0), fingers=(-0.2, 0.7, -0.7), palm=(-1.0, -0.4, -0.2), grip="pinch"),
        HandKey(3.1, add(LOCK, (0.10, -0.14, 0.18)), fingers=(-0.5, 0.6, -0.6), palm=(-1.0, 0.0, -0.2), grip="relaxed"),
        HandKey(3.9, right_rim, fingers=(-0.5, 0.37, 0.78), palm=toward_hub(right_rim), grip="grip_cylinder"),
        HandKey(SHOT_X, right_rim, fingers=(-0.5, 0.37, 0.78), palm=toward_hub(right_rim), grip="grip_cylinder"),
    ], space=C.OBJ_CAR)
    cues_a = (
        Cue(0.0, act.body_show(True)),
        Cue(0.0, act.actor("body", lambda st: BodyDriver(body_a))),
        Cue(0.0, act.actor("hand_l", lambda st: left_hand)),
        Cue(0.0, act.actor("hand_r", lambda st: right_hand)),
        Cue(0.0, act.cut_light(CAR_CABIN, 35.0)),
        Cue(0.0, act.actor("car", lambda st: anim.CarMotion(car_home, car_stop, MOVE_START, MOVE_END, crank_start=CRANK,
                                                              catch=CATCH, lights_on=CRANK))),
        Cue(0.0, act.actor("bunny", lambda st: anim.CharmPendulum("Cut_Bunny", 0.2, 0.5, "car"))),
        Cue(0.0, act.actor("wheel", lambda st: anim.SteeringWheel("Cut_Wheel"))),
        Cue(0.0, act.actor("key", lambda st: anim.PropPath(
            "Cut_Key", Path([Key(1.1, add(LOCK, (0.10, -0.15, 0.14))), Key(1.9, LOCK, True), Key(DRIVER_END, LOCK, True)]),
            key_rotation, 1.1, 19.1, also=("Cut_KeyCharm",), mount=C.OBJ_CAR))),
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
        Cue(CATCH + 0.05, act.cut_light(CAR_CABIN, 6.0)),            # sobra um brilho fraco do painel: a cabine não some no escuro
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
    exterior_eye = (car.x - 1.5, road[1] + 1.5, 1.0)           # no meio da rua, de frente para a rampa (o Sol Negro aparece no alto)
    rig_x = Rig(
        eye=path((0.0, exterior_eye, True), (dur_x, add(exterior_eye, (-0.4, -0.8, 0.05)), True)),
        look=looking((0.0, car_point(0.0, -1.0, 0.9), True), (dur_x, car_point(0.0, -2.4, 0.8), True)),
        fov=curve((0.0, 52.0), (dur_x, 46.0)),
        hand=Hand("stand", 0.5),
        impacts=(Impact(1.7, 0.4, 5.0, 4.0, 5.0),),
        focus="auto", fstop=curve((0.0, 4.5), (dur_x, 4.5)))
    shot_x = Shot(dur_x, cam=rig_x, name="saida", cut=True,
                  cues=(Cue(0.0, act.entity_place(road, ROAD_FACING, "stare", 0.0, erect=True)),),
                  lines=(say("ending", 1, 1.0, 4.2),))

    # ---------------------------------------------------------------- B: a rua, o Alto, a estática
    dur_b = SHOT_C - SHOT_B
    peer = (-0.40, -0.12, 1.12)                      # o rosto dele é alto demais para o para-brisa: o motorista se inclina e se abaixa
    rig_b = Rig(
        eye=path((0.0, add(DRIVER, (0.0, 0.0, 0.03)), True), (2.6, peer), (dur_b, add(peer, (0.0, 0.03, 0.0)), True)),
        look=looking((0.0, AHEAD, True), (1.2, AHEAD), (3.0, figure_head), (dur_b, figure_head, True)),
        fov=curve((0.0, 64.0), (2.0, 56.0), (4.5, 48.0), (dur_b, 42.0)),
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
    dur_c = TOTAL - SHOT_C
    near_clock = (0.66, 8.45, LYING_EYE[2])
    sitting = SIT_EYE
    window = window_vantage("w_master_n")
    rig_c = Rig(
        eye=path((0.0, near_clock, True), (3.4, (0.82, 8.46, 3.62)), (7.0, sitting), (11.0, add(window, (-0.1, -0.3, 0.0))),
                 (dur_c, window, True)),
        look=looking((0.0, clock, True), (2.6, clock), (5.0, (0.9, 9.4, 4.2)), (7.4, toward_sun(sitting)), (dur_c, toward_sun(window), True)),
        fov=curve((0.0, 32.0), (3.0, 34.0), (7.0, 52.0), (11.0, 46.0), (dur_c, 40.0)),
        roll=curve((0.0, 6.0), (3.0, 5.0), (6.0, 1.0), (dur_c, 0.0)),
        hand=(((0.0, Hand("lying", 1.0)), (4.0, Hand("sitting", 1.0)), (9.5, Hand("stand", 1.0)))),
        focus=curve((0.0, 0.55), (3.0, 0.55), (6.0, 2.0), (dur_c, 2.0)),
        fstop=curve((0.0, 2.2), (6.0, 3.6), (dur_c, 4.5)))
    lying_root = root_for("lying_bed", near_clock, -math.pi / 2)
    sit_root = root_for("sit_bed", sitting, SIT_YAW)
    stand_yaw = math.radians(-25.0)
    stand_root = root_for("stand", window, stand_yaw)
    body_c = (BodyPose(0.0, "lying_bed", 0.0, lying_root, -math.pi / 2),
              BodyPose(3.0, "sit_bed", 2.6, Path([Key(3.0, lying_root), Key(5.6, sit_root)]),
                       Curve([(3.0, -math.pi / 2), (5.6, SIT_YAW)])),
              BodyPose(9.0, "stand", 2.0, Path([Key(9.0, sit_root), Key(11.0, stand_root)]),
                       Curve([(9.0, SIT_YAW), (11.0, stand_yaw)])))
    cues_c = (
        *(Cue(0.0, act.stop_actor(key)) for key in ("car", "bunny", "wheel", "key", "key_charm", "dash", "dash2", "dash3",
                                                      "rollup")),
        Cue(0.0, act.stop_loop("engine")),
        Cue(0.0, act.entity_hide()),
        Cue(0.0, act.headlights(False)),
        Cue(0.0, act.cut_light(ROAD_LIGHT, 0.0)),
        Cue(0.0, act.cut_light(DRIVEWAY_LIGHT, 0.0)),
        Cue(0.0, act.hide_matching(anchor("nightstand_clock", dz=0.45), 0.55, CLOCK_NAMES)),
        Cue(0.0, act.show(END_CLOCK)),
        Cue(0.0, act.cut_light(CLOCK_GLOW, 4.0)),
        Cue(0.0, act.cut_light(BED_LAMP, 28.0)),
        Cue(0.0, act.actor("body", lambda st: BodyDriver(body_c))),
        Cue(0.0, act.actor("curtains", lambda st: anim.CurtainWind(MASTER_CURTAINS, 0.5, Curve([(0.0, 0.2), (dur_c, 0.8)])))),
        Cue(0.0, act.actor("dawn_light", lambda st: anim.EmissionPulse("cut_clock_digits", lambda t: 0.94 + 0.06 * math.sin(t * 1.3)))),
    )
    tracks_c = (Track(0.0, 20.0, act.light_ramp(DAWN_LIGHT, 0.0, 90.0), "linear"),
                Track(4.0, 18.0, act.dawn_ramp(0.0, 1.0), "smooth"))
    shot_c = Shot(dur_c, cam=rig_c, name="amanha", cut=True, cues=cues_c, tracks=tracks_c,
                  lines=(say("ending", 3, 0.9, 2.5), say("ending", 4, 4.0, 6.6)),
                  flash=((0.0, 1.0), (0.7, 1.0), (2.8, 0.0)),
                  shake=((0.0, 0.0),),
                  fade=((0.0, 0.0), (dur_c - 4.0, 0.0), (dur_c - 1.6, 1.0)),
                  card=((dur_c - 3.6, 0.0), (dur_c - 2.4, 1.0)),
                  letterbox=((0.0, 1.0), (dur_c - 1.8, 1.0), (dur_c, 0.0)))
    return Cutscene("ending", "ending_done", (shot_a, shot_x, shot_b, shot_c), card=story.ENDING_CARD,
                    initial={"fade": 1.0})

