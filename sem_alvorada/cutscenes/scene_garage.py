"""GARAGE_UNLOCK (~14,6 s): a chave na tranca, a porta cedendo e o estrondo no andar de cima. Um plano só, nos olhos do Daniel.

Batidas (tempo absoluto, s):
     0.0  a vista exata do jogador diante da porta; a câmera avança até a tranca (foco curto na fechadura)
     1.2  o chaveiro entra pela direita (a mão, se houver corpo); o coelhinho balança
     3.0  a chave gira, o trinco estala ("door_unlock"); a chave sai
     3.9  a porta destranca e abre com a curva do jogo; a câmera recua, abre a lente: a garagem escura
     6.6  estrondo lá em cima: tranco na câmera, a lanterna falha, poeira cai do forro; o olhar sobe
     9.0  "Ele ouviu": a cabeça vira devagar para a porta da cozinha; volta à posição e à vista de jogo
"""
import math

from .. import layout
from . import actions as act
from . import anim
from .body_actor import BodyDriver, BodyFollow, HandActor, HandKey
from .camera import Hand, Impact, Rig, axis_rotation, qmul
from .curves import Curve, Key, Path
from .staging import GAMEPLAY_FOV, add, ahead, curve, door_handle, looking, path, player_eye, player_gaze, say, yaw_of
from .timeline import Cue, Cutscene, Shot, Track

DURATION = 14.6
THUD = 6.6


def build():
    handle, side = door_handle("garage_door", "kitchen")
    view = (-side[0], -side[1])                               # de onde o jogador olha para a porta
    right = (view[1], -view[0])

    def at(back, across, z):
        """Ponto no lado da cozinha: `back` metros para trás da porta, `across` para a direita de quem olha, altura z."""
        return (handle[0] + side[0] * back + right[0] * across, handle[1] + side[1] * back + right[1] * across, z)

    lock = at(0.035, 0.0, 1.10)                               # a placa do ferrolho, acima da maçaneta
    lock_close = at(0.55, 0.10, 1.26)
    back_off = at(0.95, 0.06, 1.55)
    door_mid = layout.OPENINGS["garage_door"].mid
    door_focus = (door_mid[0], door_mid[1], 1.15)
    beyond = (door_mid[0] + 1.6, door_mid[1], 1.35)
    hall_door = layout.OPENINGS["kitchen_hall"].mid
    hall_look = (hall_door[0], hall_door[1], 1.45)

    def final_yaw(stage):
        p = stage.player
        return yaw_of((p.x, p.y), (hall_door[0], hall_door[1]))

    look_up = (back_off[0] + view[0] * 0.5, back_off[1] + view[1] * 0.5 + 0.2, back_off[2] + 1.5)

    def ahead_final(stage):
        p = stage.player
        return ahead(p.eye, final_yaw(stage), 6.0, p.eye_z)

    eye = path((0.0, player_eye, True), (2.4, lock_close), (3.6, add(lock_close, (view[0] * -0.03, view[1] * -0.03, 0.0))),
               (6.0, back_off), (8.2, add(back_off, (-view[0] * 0.12, -view[1] * 0.12, -0.04))),
               (11.0, player_eye), (DURATION - 0.01, player_eye, True))
    look = looking((0.0, player_gaze, True), (1.0, lock), (3.6, lock), (4.5, door_focus), (6.1, beyond), (THUD + 0.04, beyond), (7.3, look_up),
                (8.7, look_up), (11.6, hall_look),
                (DURATION - 0.01, ahead_final, True))
    rig = Rig(eye, look,
              fov=curve((0.0, GAMEPLAY_FOV), (2.4, 54.0), (3.6, 52.0), (5.0, 62.0), (THUD, 68.0), (8.6, 70.0),
                        (11.6, GAMEPLAY_FOV), (DURATION - 0.01, GAMEPLAY_FOV)),
              roll=curve((0.0, 0.0), (THUD, 0.0), (THUD + 0.3, 2.5), (8.8, 0.0), (DURATION - 0.01, 0.0)),
              hand=Hand("walk", Curve([(0.0, 0.8), (3.8, 0.4), (THUD, 0.5), (11.0, 0.7), (DURATION - 0.01, 0.0)])),
              impacts=(Impact(THUD + 0.05, 1.8, 5.5, 3.6, 0.5), Impact(THUD + 0.45, 0.7, 7.0, 4.5, 2.1)),
              focus=curve((0.0, 2.2), (1.6, 0.8), (3.6, 0.55), (4.5, 1.6), (6.0, 2.6), (DURATION - 0.01, 2.6)),
              fstop=curve((0.0, 4.0), (1.6, 2.0), (3.6, 1.8), (6.0, 3.2), (DURATION - 0.01, 5.6)))

    # a chave: entra pela direita, encaixa, gira um quarto e sai (posições no mundo, ancoradas na fechadura)
    key_in = at(0.035 + 0.30, 0.16, 0.94)
    key_near = at(0.035 + 0.10, 0.04, 1.05)
    key_path = Path([Key(1.0, key_in), Key(2.5, key_near), Key(2.9, add(lock, (side[0] * 0.012, side[1] * 0.012, 0.0)), True),
                     Key(3.5, add(lock, (side[0] * 0.012, side[1] * 0.012, 0.0)), True), Key(4.1, key_in)],
                    rest_ends=True)
    base = qmul(axis_rotation("z", math.atan2(-side[1], -side[0])), axis_rotation("y", -math.pi / 2))

    def key_rotation(t, stage):
        turn = 0.0 if t < 3.0 else min(1.0, (t - 3.0) / 0.35) * (math.pi / 2) if t < 3.5 else (math.pi / 2) * max(0.0, 1.0 - (t - 3.5) / 0.35)
        wiggle = 0.12 * math.sin(t * 5.0) * (1.0 if t < 2.6 else 0.0)
        return qmul(base, qmul(axis_rotation("z", turn), axis_rotation("x", wiggle)))

    # a mão esquerda segura a chave (a direita fica com a lanterna, fora do quadro): pega o bordo do arco e leva até a placa
    tip_dir = (-side[0], -side[1], 0.0)

    def grip_at(t, weight=1.0, turn=0.0):
        tip = key_path.at(t)
        bow = (tip[0] - tip_dir[0] * 0.055, tip[1] - tip_dir[1] * 0.055, tip[2])
        return HandKey(t, (bow[0] - tip_dir[0] * 0.05, bow[1] - tip_dir[1] * 0.05, bow[2] - 0.012),
                       fingers=tip_dir, palm=(right[0], right[1], -0.3), weight=weight, grip="pinch")
    hand_keys = [grip_at(0.9, 0.0), grip_at(1.3), grip_at(1.8), grip_at(2.3), grip_at(2.6), grip_at(2.9), grip_at(3.2),
                 grip_at(3.5), grip_at(3.8), grip_at(4.1, 0.0)]
    cues = (
        Cue(0.0, act.flashlight_follows(True)),
        Cue(0.0, act.flash_hand(0.35)),
        Cue(0.0, act.body_show(True)),
        Cue(0.0, act.actor("body", lambda st: BodyDriver([BodyFollow(0.0)]))),
        Cue(0.0, act.actor("hand_key", lambda st: HandActor("L", hand_keys, space="world"))),
        Cue(0.0, act.actor("key", lambda st: anim.PropPath("Cut_Key", key_path, key_rotation, 1.0, 4.1, also=("Cut_KeyCharm",)))),
        Cue(0.0, act.actor("charm", lambda st: anim.CharmPendulum("Cut_KeyCharm", 0.07, 0.35, "prop:Cut_Key"))),
        Cue(1.1, act.sound("hand_reach", None, 0.4)),
        Cue(1.4, act.sound("key_jingle", handle, 0.8)),
        Cue(2.7, act.sound("key_jingle", handle, 0.4)),
        Cue(3.2, act.sound("door_unlock", handle, 1.0)),
        Cue(3.9, act.open_door("garage_door", 1.7)),
        Cue(3.9, act.sound("door_creak_long", door_focus, 0.7)),
        Cue(THUD, act.sound("ent_door_break", None, 1.0)),
        Cue(THUD, act.sound("thud_2", None, 0.9)),
        Cue(THUD, act.actor("dust", lambda st: anim.DustFall((st.player.x, st.player.y), 1.7, 2.6, 0.0, THUD, 1.8, 2.0, 1.4))),
        Cue(THUD + 0.1, act.silence(3.0)),
        Cue(THUD + 0.02, act.flashlight(False)), Cue(THUD + 0.14, act.flashlight(True)),
        Cue(THUD + 0.3, act.flashlight(False)), Cue(THUD + 0.38, act.flashlight(True)),
        Cue(THUD + 0.62, act.flashlight(False)), Cue(THUD + 0.66, act.flashlight(True)),
        Cue(9.5, act.sound("breath_calm", None, 0.5)),
        Cue(DURATION - 0.1, act.place_player(lambda st: st.player.x, lambda st: st.player.y, lambda st: st.player.z, final_yaw)),
        Cue(DURATION - 0.05, act.activate_brain()),
    )
    aim_yaw = Curve([(0.0, 0.0), (0.9, 0.0), (1.8, 9.0), (4.2, 9.0), (5.4, 0.0), (DURATION, 0.0)])
    aim_pitch = Curve([(0.0, 0.0), (0.9, 0.0), (1.8, 2.0), (4.2, 2.0), (5.4, 0.0), (DURATION, 0.0)])
    shot = Shot(DURATION, cam=rig, name="tranca", cues=cues, tracks=(Track(0.0, DURATION, act.flash_aim(DURATION, aim_yaw, aim_pitch), "linear"),),
                lines=(say("garage_unlock", 0, 3.9, 5.7), say("garage_unlock", 1, THUD + 0.3, THUD + 2.4),
                       say("garage_unlock", 2, 9.3, 11.9)),
                letterbox=((0.0, 0.0), (0.9, 1.0), (11.8, 1.0), (13.8, 0.0)),
                shake=((THUD - 0.02, 0.0), (THUD + 0.03, 0.9), (THUD + 1.4, 0.15), (9.0, 0.0)),
                flash=((THUD - 0.02, 0.0), (THUD + 0.04, 0.22), (THUD + 0.4, 0.0)))
    return Cutscene("garage_unlock", "unlock_done", (shot,))

