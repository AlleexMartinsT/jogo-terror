"""INTRO (~38 s): um único plano contínuo, os olhos do Daniel.

Batidas (tempo absoluto, s):
     0.0  escuro; despertador apitando, rádio baixo; as pálpebras pesadas
     2.5  entreabre: o vermelho do mostrador borrado (foco curto, diafragma aberto)
     5.5  olhos abertos, o foco firma no 6:47; a legenda "6:47."; o mostrador pisca 6:12 junto do rádio
     8.0  rola e senta (cama, lençol): a câmera sobe girando para a janela; o abajur acende
    12.5  os pés no chão: o olhar cai, o tapete, os sapatos
    15.0  em pé, a janela: o Sol Negro entre as barras, a cortina respira
    24.0  vira e dá a volta na cama (passos no tapete); a luz do teto volta tremendo
    31.0  chega ao PLAYER_START, gira para a porta e entrega a câmera ao jogador (posição, yaw e FOV iguais)
"""
import math

from .. import layout
from . import actions as act
from . import anim
from .body_actor import BodyDriver, BodyFollow, BodyPose, HandActor, HandKey, root_for
from .camera import Aim, Hand, Impact, Rig
from .curves import Curve, Key, Path
from .staging import (BED_LAMP, CLOCK_GLOW, EYE, GAMEPLAY_FOV, MASTER_CURTAINS, add, ahead, anchor, blink, curve, say,
                      step_cues, toward_sun, window_vantage)
from .timeline import Cue, Cutscene, Shot

DURATION = 37.0
WALK_FROM, WALK_TO = 23.5, 29.8
# olhos nas poses do corpo (a altura do plano do colchão sai da pose: 3,388 m)
LYING_EYE = (1.15, 8.50, 3.572)
SIT_EYE = (1.00, 8.44, 4.17)
STAND_EYE = (1.34, 8.62, 4.45)
LAMP_SWITCH = (0.43, 8.84, 3.52)


def _walk_points():
    window = window_vantage("w_master_n")
    return [(window[0], window[1], window[2]), (2.45, 8.70, 4.45), (3.25, 8.30, 4.45), (3.38, 7.25, 4.45),
            (3.15, 6.25, 4.45), (2.55, 5.85, 4.45)]


def _eye_path():
    window = _walk_points()
    start = layout.PLAYER_START
    end = (start[0], start[1], start[2] + EYE)
    walk = [Key(WALK_FROM + (WALK_TO - WALK_FROM) * f, p) for f, p in zip((0.0, 0.17, 0.36, 0.58, 0.80, 0.92), window)]
    return Path([
        Key(0.0, LYING_EYE, True),
        Key(5.8, add(LYING_EYE, (-0.02, -0.02, 0.01))),
        Key(8.6, (1.06, 8.47, 3.88)),
        Key(10.6, add(SIT_EYE, (0.0, 0.0, -0.03))),
        Key(12.2, SIT_EYE),
        Key(13.6, add(SIT_EYE, (0.05, 0.05, -0.12))),
        Key(15.4, add(STAND_EYE, (0.0, 0.0, -0.07))),
        Key(17.5, window[0], False),
        Key(WALK_FROM - 1.2, window[0]),
        *walk[1:],
        Key(WALK_TO + 0.5, end, True),
        Key(DURATION - 0.01, end, True),
    ], rest_ends=True)


def build():
    clock = anchor("nightstand_clock", dz=0.62)
    start = layout.PLAYER_START
    yaw = math.radians(layout.PLAYER_START_YAW_DEG)
    end_eye = (start[0], start[1], start[2] + EYE)
    window_eye = window_vantage("w_master_n")
    floor_shoes = (1.74, 8.56, 2.86)

    eye = _eye_path()
    def heading(t, lead=1.4, z=4.2):
        x, y, _ = eye.at(min(t + lead, WALK_TO + 0.5))
        return (x, y, z)

    look = Aim.toward(eye, [
        (0.0, clock, True),
        (5.6, add(clock, (0.0, 0.02, 0.0))),
        (7.4, (0.32, 8.92, 3.62)),                       # a mão vai ao abajur
        (8.8, (0.34, 8.96, 3.80)),
        (10.2, (2.0, 10.0, 4.25)),
        (11.8, toward_sun(SIT_EYE)),
        (13.3, floor_shoes),
        (14.4, floor_shoes[:2] + (3.4,)),
        (16.0, toward_sun(window_eye)),
        (17.4, toward_sun(window_eye)),
        (WALK_FROM - 1.0, toward_sun(window_eye)),
        (WALK_FROM + 0.8, heading(WALK_FROM + 0.8)),
        (WALK_FROM + 2.4, heading(WALK_FROM + 2.4)),
        (WALK_FROM + 4.0, heading(WALK_FROM + 4.0)),
        (WALK_TO - 0.2, add(end_eye, (-3.0, 0.0, -0.3))),
        (WALK_TO + 1.3, add(end_eye, (0.0, -3.0, -0.3))),
        (WALK_TO + 2.8, ahead(end_eye, yaw, 6.0)),
        (DURATION - 0.01, ahead(end_eye, yaw, 6.0), True),
    ], distance=2.0)
    fov = curve((0.0, 44.0), (5.5, 40.0), (8.5, 52.0), (12.0, 58.0), (14.0, 66.0), (17.5, 54.0), (22.0, 44.0), (23.5, 46.0),
                (WALK_FROM + 3.0, 66.0), (WALK_TO + 2.0, GAMEPLAY_FOV), (DURATION - 0.01, GAMEPLAY_FOV))
    roll = curve((0.0, 7.0), (5.0, 6.0), (8.4, 9.0), (10.6, -2.5), (13.0, 0.0), (DURATION - 0.01, 0.0))
    amount_lying = Curve([(0.0, 1.2), (6.0, 1.0), (DURATION, 0.7)])
    hand = ((0.0, Hand("lying", amount_lying)),
            (8.0, Hand("sitting", 1.1)),
            (WALK_FROM - 0.6, Hand("walk", Curve([(0.0, 0.0), (WALK_FROM + 0.6, 1.0), (WALK_TO, 0.9),
                                                  (WALK_TO + 1.6, 0.15), (DURATION - 0.01, 0.0)]))))
    rig = Rig(eye, look, fov, roll, hand,
              impacts=(Impact(14.1, 0.5, 4.0, 4.2, 1.0),),                    # os pés tocam o chão
              focus=curve((0.0, 0.14), (2.4, 0.14), (5.4, 0.70), (9.0, 0.70), (11.0, 2.2), (13.4, 0.9), (15.5, 2.0),
                          (18.0, 1.9), (WALK_FROM - 0.5, 1.9), (WALK_FROM + 1.5, 3.5), (DURATION - 0.01, 5.0)),
              fstop=curve((0.0, 1.2), (5.5, 2.8), (13.0, 3.6), (WALK_FROM, 5.6), (DURATION - 0.01, 8.0)),
              walk=True)

    lying_root = root_for("lying_bed", LYING_EYE, -math.pi / 2)
    sit_root = root_for("sit_bed", SIT_EYE, 0.0)
    stand_yaw = math.radians(-25.0)
    stand_root = root_for("stand", STAND_EYE, stand_yaw)
    body_plan = (
        BodyPose(0.0, "lying_bed", 0.0, lying_root, -math.pi / 2),
        BodyPose(7.8, "sit_bed", 2.6, Path([Key(7.8, lying_root), Key(10.4, sit_root)]),
                 Curve([(7.8, -math.pi / 2), (10.4, 0.0)])),
        BodyPose(14.4, "stand", 1.8, Path([Key(14.4, sit_root), Key(16.2, stand_root)]),
                 Curve([(14.4, 0.0), (16.2, stand_yaw)])),
        BodyFollow(WALK_FROM - 0.8),
    )
    hands = (
        # a mão esquerda busca o abajur no criado-mudo e aperta o botão
        HandActor("L", [HandKey(7.5, (0.85, 8.20, 3.62), fingers=(-0.6, 0.6, 0.0), palm=(0.0, 0.0, -1.0), weight=0.0),
                        HandKey(8.1, (0.60, 8.55, 3.60), fingers=(-0.6, 0.7, 0.0), palm=(0.0, 0.0, -1.0), grip="relaxed"),
                        HandKey(8.5, LAMP_SWITCH, fingers=(-0.6, 0.7, -0.2), palm=(0.0, 0.0, -1.0), grip="point"),
                        HandKey(8.7, add(LAMP_SWITCH, (0.0, 0.0, -0.012)), fingers=(-0.6, 0.7, -0.2), palm=(0.0, 0.0, -1.0), grip="point"),
                        HandKey(9.2, (0.85, 8.20, 3.70), fingers=(-0.6, 0.6, 0.0), palm=(0.0, 0.0, -1.0), weight=0.0)], space="world"),
        # a mão direita esfrega o rosto: cobre a lente por um instante (junto da piscada pesada)
        HandActor("R", [HandKey(9.2, (0.16, -0.30, -0.34), fingers=(0.0, 1.0, 0.0), palm=(0.0, 0.0, 1.0), weight=0.0, grip="relaxed"),
                        HandKey(9.65, (0.05, -0.04, -0.12), fingers=(0.0, 1.0, 0.1), palm=(0.0, 0.0, 1.0), grip="flat"),
                        HandKey(9.95, (-0.04, 0.0, -0.11), fingers=(0.0, 1.0, 0.1), palm=(0.0, 0.0, 1.0), grip="flat"),
                        HandKey(10.5, (0.16, -0.30, -0.34), fingers=(0.0, 1.0, 0.0), palm=(0.0, 0.0, 1.0), weight=0.0, grip="relaxed")],
                  space="camera"),
    )
    lids = blink((0.0, 1.0), (1.8, 1.0), (2.5, 0.55), (2.9, 0.85), (3.6, 0.3), (4.3, 0.62), (5.2, 0.0),
                 (9.4, 0.0), (9.9, 0.9), (10.3, 0.0))
    cues = (
        Cue(0.0, act.power(False)),
        Cue(0.0, act.cut_light(CLOCK_GLOW, 5.0)),
        Cue(0.0, act.body_show(True)),
        Cue(0.0, act.actor("body", lambda st: BodyDriver(body_plan))),
        *(Cue(0.0, act.actor(f"hand_{i}", lambda st, h=hand: h)) for i, hand in enumerate(hands)),
        Cue(0.0, act.actor("curtains", lambda st: anim.CurtainWind(MASTER_CURTAINS, 0.5, Curve(
            [(0.0, 0.25), (16.0, 0.6), (26.0, 1.0), (DURATION, 0.5)])))),
        Cue(0.0, act.actor("clock", lambda st: anim.ClockGlitch((6.1, 7.6, 15.9)))),
        Cue(0.0, act.actor("clock_glow", lambda st: anim.EmissionPulse("digits_647", lambda t: anim.clock_level(t)))),
        Cue(0.5, act.sound("alarm_beep", clock, 0.5)),
        Cue(1.3, act.sound("alarm_beep", clock, 0.5)),
        Cue(2.6, act.loop("radio", "amb_radio_static", 0.25)),
        Cue(5.9, act.loop("radio", "amb_radio_static", 0.55)),
        Cue(8.2, act.sound("creak_1", None, 0.5)),
        Cue(9.4, act.sound("cloth_rustle_1", None, 0.4)),
        Cue(8.5, act.sound("flash_on", None, 0.5)),
        Cue(8.5, act.cut_light(BED_LAMP, 28.0)),
        Cue(13.8, act.sound("step_carpet_1", None, 0.4)),
        Cue(16.5, act.sound("breath_calm", None, 0.4)),
        Cue(22.0, act.loop("radio", "amb_radio_static", 0.8)),
        Cue(22.4, act.sound("power_hum", None, 0.5)),
        Cue(22.4, act.power(True, 0.55)),
        Cue(30.0, act.power(True, 0.0)),
        Cue(32.5, act.stop_loop("radio")),
        Cue(DURATION - 0.05, act.cut_light(CLOCK_GLOW, 0.0)),
        Cue(DURATION - 0.05, act.place_player(start[0], start[1], start[2], yaw)),
        *step_cues(rig, WALK_FROM, WALK_TO + 0.4, ("step_carpet_1", "step_carpet_2", "step_carpet_3", "step_carpet_4"), 0.45),
    )
    lines = (say("intro", 0, 5.4, 7.6), say("intro", 1, 15.2, 18.6), say("intro", 2, 18.9, 22.2),
             say("intro", 3, 22.5, 25.6), say("intro", 4, 25.9, 30.2), say("intro", 5, 31.4, 36.0))
    shot = Shot(DURATION, cam=rig, name="acordar", lines=lines, cues=cues,
                fade=((0.0, 1.0), (0.5, 1.0), (1.4, 0.0)),
                letterbox=((0.0, 0.0), (6.0, 0.0), (7.5, 1.0), (30.5, 1.0), (35.0, 0.0)),
                shake=((0.0, 0.0), (14.0, 0.0), (14.2, 0.15), (15.5, 0.0)),
                lids=lids)
    return Cutscene("intro", "intro_done", (shot,), initial={"fade": 1.0})
