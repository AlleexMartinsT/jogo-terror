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
from .camera import Aim, Hand, Impact, Rig
from .curves import Curve, Key, Path
from .staging import (BED_LAMP, CLOCK_GLOW, EYE, GAMEPLAY_FOV, MASTER_CURTAINS, add, anchor, blink, curve, path,
                      say, step_cues, toward_sun, window_vantage, yaw_of, ahead)
from .timeline import Cue, Cutscene, Shot

DURATION = 37.0
WALK_FROM, WALK_TO = 23.5, 29.8


def _walk_points():
    window = window_vantage("w_master_n")
    return [(window[0], window[1], window[2]), (2.45, 8.70, 4.45), (3.25, 8.30, 4.45), (3.38, 7.25, 4.45),
            (3.15, 6.25, 4.45), (2.55, 5.85, 4.45)]


def _eye_path():
    clock_eye = (1.15, 8.52, 3.64)
    window = _walk_points()
    start = layout.PLAYER_START
    end = (start[0], start[1], start[2] + EYE)
    walk = [Key(WALK_FROM + (WALK_TO - WALK_FROM) * f, p) for f, p in zip((0.0, 0.17, 0.36, 0.58, 0.80, 0.92), window)]
    return Path([
        Key(0.0, clock_eye, True),
        Key(5.8, (1.13, 8.50, 3.65)),
        Key(8.6, (1.12, 8.47, 3.86)),
        Key(10.6, (1.12, 8.42, 4.10)),
        Key(12.2, (1.14, 8.44, 4.14)),
        Key(13.6, (1.18, 8.50, 4.02)),
        Key(15.4, (1.34, 8.62, 4.38)),
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
    sun = toward_sun(window_eye)
    floor_shoes = (1.74, 8.56, 2.86)

    eye = _eye_path()
    def heading(t, lead=1.4, z=4.2):
        x, y, _ = eye.at(min(t + lead, WALK_TO + 0.5))
        return (x, y, z)

    look = Aim.toward(eye, [
        (0.0, clock, True),
        (5.6, add(clock, (0.0, 0.02, 0.0))),
        (7.6, (0.30, 9.0, 3.60)),
        (9.6, (0.9, 9.6, 4.35)),
        (11.6, toward_sun((1.12, 8.42, 4.12))),
        (13.4, floor_shoes),
        (15.2, floor_shoes[:2] + (3.5,)),
        (17.2, toward_sun(window_eye)),
        (WALK_FROM - 1.0, toward_sun(window_eye)),
        (WALK_FROM + 0.8, heading(WALK_FROM + 0.8)),
        (WALK_FROM + 2.4, heading(WALK_FROM + 2.4)),
        (WALK_FROM + 4.0, heading(WALK_FROM + 4.0)),
        (WALK_TO - 0.2, add(end_eye, (-3.0, 0.0, -0.3))),
        (WALK_TO + 1.3, add(end_eye, (0.0, -3.0, -0.3))),
        (WALK_TO + 2.8, ahead(end_eye, yaw, 6.0)),
        (DURATION - 0.01, ahead(end_eye, yaw, 6.0), True),
    ], distance=2.0)
    fov = curve((0.0, 44.0), (5.5, 40.0), (8.5, 52.0), (12.0, 60.0), (14.0, 66.0), (17.5, 56.0), (23.5, 48.0),
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

    lids = blink((0.0, 1.0), (1.8, 1.0), (2.5, 0.55), (2.9, 0.85), (3.6, 0.3), (4.3, 0.62), (5.2, 0.0),
                 (9.4, 0.0), (9.9, 0.9), (10.3, 0.0))
    cues = (
        Cue(0.0, act.power(False)),
        Cue(0.0, act.cut_light(CLOCK_GLOW, 5.0)),
        Cue(0.0, act.body_show(True)),
        Cue(0.0, act.body_pose("lying_bed")),
        Cue(0.0, act.actor("curtains", lambda st: anim.CurtainWind(MASTER_CURTAINS, 0.5, Curve(
            [(0.0, 0.25), (16.0, 0.6), (26.0, 1.0), (DURATION, 0.5)])))),
        Cue(0.0, act.actor("clock", lambda st: anim.ClockGlitch((6.1, 7.6, 15.9)))),
        Cue(0.0, act.actor("clock_glow", lambda st: anim.EmissionPulse("digits_647", lambda t: anim.clock_level(t)))),
        Cue(0.5, act.sound("alarm_beep", clock, 0.5)),
        Cue(1.3, act.sound("alarm_beep", clock, 0.5)),
        Cue(2.6, act.loop("radio", "amb_radio_static", 0.25)),
        Cue(5.9, act.loop("radio", "amb_radio_static", 0.55)),
        Cue(8.0, act.body_pose("sit_bed", 2.0)),
        Cue(8.2, act.sound("creak_1", None, 0.5)),
        Cue(9.4, act.sound("cloth_rustle_1", None, 0.4)),
        Cue(11.2, act.sound("flash_on", None, 0.5)),
        Cue(11.2, act.cut_light(BED_LAMP, 28.0)),
        Cue(13.8, act.sound("step_carpet_1", None, 0.4)),
        Cue(14.9, act.body_pose("stand", 1.4)),
        Cue(16.5, act.sound("breath_calm", None, 0.4)),
        Cue(22.0, act.loop("radio", "amb_radio_static", 0.8)),
        Cue(28.0, act.sound("power_hum", None, 0.5)),
        Cue(28.0, act.power(True, 0.3)),
        Cue(32.5, act.stop_loop("radio")),
        Cue(DURATION - 0.05, act.cut_light(CLOCK_GLOW, 0.0)),
        Cue(DURATION - 0.05, act.place_player(start[0], start[1], start[2], yaw)),
        *step_cues(rig, WALK_FROM, WALK_TO + 0.4, ("step_carpet_1", "step_carpet_2", "step_carpet_3", "step_carpet_4"), 0.45),
    )
    lines = (say("intro", 0, 5.4, 7.6), say("intro", 1, 15.2, 18.6), say("intro", 2, 18.9, 22.2),
             say("intro", 3, 22.5, 25.6), say("intro", 4, 25.9, 30.2), say("intro", 5, 31.4, 36.0))
    shot = Shot(DURATION, cam=rig, name="acordar", lines=lines, cues=cues,
                fade=((0.0, 1.0), (0.5, 1.0), (1.4, 0.0)),
                letterbox=((0.0, 0.0), (2.0, 1.0), (30.5, 1.0), (35.0, 0.0)),
                shake=((0.0, 0.0), (14.0, 0.0), (14.2, 0.15), (15.5, 0.0)),
                lids=lids)
    return Cutscene("intro", "intro_done", (shot,), initial={"fade": 1.0})
