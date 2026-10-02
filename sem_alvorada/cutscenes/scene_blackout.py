"""BLACKOUT (~17 s): a queda de luz em cascata, a lâmpada que estoura e o Alto no fim do corredor.

Batidas (tempo absoluto, s):
     0.0  a vista exata do jogador; a casa tremula; as luzes morrem uma a uma, das mais longe para a mais perto
     3.0  a lâmpada de cima estoura (faíscas, estampido) e tudo apaga, até a lanterna
     3.6  corte no escuro: o jogador já está no fim do corredor, de frente para ele (teletransporte escondido no preto)
     6.4  a lanterna volta tremendo na mão: o feixe acha a figura imóvel, a 4,5 m
     8.8  os olhos acendem, ele se contorce; a lanterna morre
    10.2  no escuro, só os olhos: ele dá uma passada lenta em direção à câmera, de um passo a outro
    14.8  a lanterna volta; a câmera assenta na vista de jogo, olhando para ele; o cérebro acorda dali
"""
import math

from .. import layout
from . import actions as act
from . import anim
from .camera import Hand, Impact, Rig
from .curves import Curve, Key, Path
from .staging import (CORRIDOR_RIM, EYE, GAMEPLAY_FOV, add, curve, looking, path, player_eye, player_gaze, say,
                      yaw_of)
from .timeline import Cue, Cutscene, Shot, Track

CASCADE_START, BURST = 1.0, 3.0
SHOT_A, TOTAL = 3.6, 17.2
ENTITY_ADVANCE = 1.0                  # metros que ele anda em direção ao jogador


def blackout_vantage():
    """Onde o jogador fica durante o apagão: no corredor, a ~4,5 m da entidade, longe da abertura da escada."""
    hall = layout.ROOMS["hall_u"].rect
    sight = layout.ENTITY_FIRST_SIGHT
    return (hall.x1 - 1.0, sight[1] - 4.5, sight[2])


def hall_light(stage):
    """A luz do corredor mais próxima do jogador: nome do objeto e posição."""
    options = layout.CEILING_LIGHTS["hall_u"]
    x, y = min(options, key=lambda p: math.dist(p, stage.player.eye[:2]))
    index = options.index((x, y))
    return f"Light_hall_u_c{index}", (x, y, layout.LEVEL_Z[1] + 2.24)


def cascade_plan(stage):
    """Todas as luzes ao redor morrem, das mais distantes às mais próximas; a última (a de cima) estoura."""
    px, py, _ = stage.player.eye
    burst_name, _ = hall_light(stage)
    others = []
    for room in ("hall_u", "master", "kids", "bath", "study"):
        for index, (x, y) in enumerate(layout.CEILING_LIGHTS.get(room, [])):
            name = f"Light_{room}_c{index}"
            if name != burst_name:
                others.append((math.dist((x, y), (px, py)), name))
    others.sort(reverse=True)
    step = (BURST - 0.35 - CASCADE_START) / max(len(others) - 1, 1)
    plan = [(name, CASCADE_START + k * step, "die") for k, (_, name) in enumerate(others)]
    plan.append((burst_name, BURST, "burst"))
    return plan


def lamp_point(stage):
    return hall_light(stage)[1]


def build():
    vantage = blackout_vantage()
    sight = layout.ENTITY_FIRST_SIGHT
    eye = (vantage[0], vantage[1], vantage[2] + EYE)
    face_yaw = yaw_of(vantage, sight)
    entity_yaw = yaw_of(sight, vantage)
    head = (sight[0], sight[1], sight[2] + 1.9)
    near_sight = (sight[0], sight[1] - ENTITY_ADVANCE, sight[2])
    near_head = (head[0], head[1] - ENTITY_ADVANCE, head[2])
    wall_glance = (sight[0] - 3.0, sight[1] + 0.2, sight[2] + 1.6)      # para onde ele "olha" antes de notar o jogador
    t = lambda x: x - SHOT_A                       # noqa: E731  tempo absoluto -> tempo do plano B
    dur_b = TOTAL - SHOT_A

    rig_a = Rig(
        eye=path((0.0, player_eye, True), (SHOT_A, player_eye, True)),
        look=looking((0.0, player_gaze, True), (0.5, player_gaze), (BURST - 0.1, lamp_point), (SHOT_A, lamp_point, True)),
        fov=curve((0.0, GAMEPLAY_FOV), (2.6, 64.0), (SHOT_A, 62.0)),
        roll=curve((0.0, 0.0), (BURST, 0.0), (BURST + 0.4, -3.0), (SHOT_A, -3.0)),
        hand=Hand("stand", Curve([(0.0, 0.7), (BURST, 1.4), (SHOT_A, 1.0)])),
        impacts=(Impact(BURST, 1.5, 6.0, 4.4, 2.0),),
    )
    shot_a = Shot(SHOT_A, cam=rig_a, name="queda", lines=(say("blackout", 0, 0.5, 2.5),),
                  letterbox=((0.0, 0.0), (1.2, 1.0)),
                  cues=(Cue(0.0, act.flashlight_follows(True)),
                        Cue(0.1, act.power(True, 0.65)),
                        Cue(0.0, act.actor("cascade", lambda st: anim.LightCascade(cascade_plan(st)))),
                        Cue(0.5, act.sound("creak_1", None, 0.6)),
                        Cue(1.2, act.sound("flash_flicker", None, 0.5)),
                        Cue(2.0, act.sound("flash_flicker", None, 0.6)),
                        Cue(BURST - 0.02, act.sound("glass_break", None, 0.8)),
                        Cue(BURST, act.sound("blackout_thunk", None, 1.0)),
                        Cue(BURST, act.actor("sparks", lambda st: anim.SparkBurst(add(lamp_point(st), (0.0, 0.0, -0.1)), BURST))),
                        Cue(BURST + 0.05, act.power(False)),
                        Cue(BURST + 0.05, act.flashlight(False)),
                        Cue(BURST + 0.05, act.cut_light(CORRIDOR_RIM, 0.0))),
                  fade=((BURST + 0.7, 0.0), (BURST + 0.85, 1.0)),
                  shake=((BURST - 0.1, 0.0), (BURST, 0.6), (SHOT_A, 0.0)))

    # --- plano B: o mesmo "corte no escuro" até a vista de jogo. Os olhos só se afastam e voltam: terminam no vantage.
    eye_b = Path([Key(0.0, eye, True), Key(t(9.0), add(eye, (0.0, 0.07, -0.03))), Key(t(12.8), add(eye, (0.0, 0.16, -0.05))),
                  Key(t(14.6), eye), Key(dur_b, eye, True)])
    look_b = looking((0.0, head, True), (t(9.6), add(head, (0.0, 0.0, 0.05))), (t(13.4), add(near_head, (0.0, 0.0, 0.1))),
                     (t(15.8), near_head), (dur_b, near_head, True))
    fov_b = curve((0.0, GAMEPLAY_FOV), (t(8.8), 66.0), (t(10.4), 54.0), (t(13.8), 50.0), (dur_b, GAMEPLAY_FOV))
    rig_b = Rig(eye_b, look_b, fov_b,
                roll=curve((0.0, 0.0), (t(8.8), 0.0), (t(9.2), 2.5), (t(10.4), 0.0), (dur_b, 0.0)),
                hand=Hand("stand", Curve([(0.0, 0.9), (t(8.8), 1.6), (t(12.0), 1.2), (dur_b, 0.0)])),
                impacts=(Impact(t(8.8), 1.1, 6.5, 4.8, 3.0),),
                focus=curve((0.0, 4.5), (dur_b, 4.5)), fstop=curve((0.0, 2.2), (dur_b, 3.4)))
    flicker_on = ((6.4, True), (6.5, False), (6.62, True), (6.7, False), (6.95, True))
    flicker_off = ((9.7, False), (9.82, True), (9.95, False), (10.05, True), (10.15, False))
    flicker_back = ((13.9, True), (14.0, False), (14.2, True), (14.5, True))
    cues_b = [
        Cue(t(3.7), act.place_player(vantage[0], vantage[1], vantage[2], face_yaw)),
        Cue(t(3.7), act.entity_place(sight, entity_yaw, "stare", 0.0)),
        Cue(t(3.8), act.silence(11.0)),
        Cue(t(4.4), act.loop("heartbeat", "heartbeat", 0.5)),
        Cue(t(4.6), act.sound("ent_drone", sight, 0.4)),
        Cue(t(6.4), act.sound("flash_on", None, 0.7)),
        Cue(t(6.4), act.flash_hand(0.8)),
        Cue(t(8.8), act.entity_eyes(0.55)), Cue(t(8.95), act.entity_eyes(0.0)), Cue(t(9.1), act.entity_eyes(1.0)),
        Cue(t(9.1), act.sound("ent_stinger", sight, 0.8)),
        Cue(t(9.15), act.entity_anim("twitch")),
        Cue(t(9.15), act.cut_light(CORRIDOR_RIM, 6.0)),
        Cue(t(9.9), act.sound("flash_flicker", None, 0.7)),
        Cue(t(10.05), act.entity_anim("stare")),
        Cue(t(10.3), act.sound("ent_breath", sight, 0.7)),
        Cue(t(10.4), act.entity_anim("stalk")),
        Cue(t(10.4), act.entity_speed(ENTITY_ADVANCE / 3.0)),
        Cue(t(13.4), act.entity_stands("stare")),
        Cue(t(13.7), act.sound("ent_whisper", near_sight, 0.6)),
        Cue(t(13.9), act.sound("flash_on", None, 0.7)),
        Cue(t(14.6), act.flash_hand(0.0)),
        Cue(dur_b + SHOT_A - 0.5, act.stop_loop("heartbeat")),
        Cue(t(TOTAL - 0.05), act.activate_brain(near_sight)),
        Cue(t(TOTAL - 0.05), act.flashlight(True)),
    ]
    cues_b += [Cue(t(a), act.flashlight(on)) for a, on in flicker_on + flicker_off + flicker_back]
    cues_b += [Cue(t(10.7 + 0.95 * k), act.sound(("ent_step_stalk_1", "ent_step_stalk_2")[k % 2], near_sight, 0.55))
               for k in range(3)]
    tracks_b = (Track(t(4.0), t(10.1), act.entity_look(wall_glance), "linear"),
                Track(t(10.1), t(TOTAL), act.entity_look(eye, rate=70.0), "linear"),
                Track(t(10.4), t(13.4), act.entity_walk(sight, near_sight, entity_yaw), "linear"))
    shot_b = Shot(dur_b, cam=rig_b, name="escuro_e_luz", cut=True,
                  lines=(say("blackout", 1, t(4.5), t(6.7)), say("blackout", 2, t(6.9), t(10.4)),
                         say("blackout", 3, t(11.2), t(15.8))),
                  cues=tuple(cues_b), tracks=tracks_b,
                  fade=((0.0, 1.0), (t(4.8), 1.0), (t(6.2), 0.0)),
                  letterbox=((t(13.8), 1.0), (t(16.2), 0.0)),
                  shake=((t(8.8), 0.1), (t(9.4), 0.5), (t(10.4), 0.2), (t(13.8), 0.3), (dur_b, 0.0)))
    return Cutscene("blackout", "blackout_done", (shot_a, shot_b), initial={"fade": 0.0})
