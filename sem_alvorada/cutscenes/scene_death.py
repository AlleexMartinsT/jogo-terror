"""DEATH (~3,4 s): o bote do Alto sem parar o tempo. Um plano só, os olhos do jogador, do susto ao preto.

Batidas (tempo absoluto, s):
     0.00  a vista exata do jogador; a cabeça gira para ela (se não olhava); a lanterna falha
     0.15  o bote: ela alcança o rosto (lente fecha, 72 -> 46 graus)
     0.55  o golpe: pancada, flash branco, "death_hit"
     0.75  a câmera é puxada para trás e cai (cai um quarto de volta, o ombro bate)
     1.45  o chão: pancada seca; ela, curvada, assoma sobre a lente com os olhos brancos
     2.9   corte seco para o preto (sem fade) com o segundo golpe; o jogo mostra a tela de fim
"""
import math

from . import actions as act
from .camera import Hand, Impact, Rig
from .curves import Curve, Key, Path
from .staging import curve, looking, player_eye, player_gaze
from .timeline import Cue, Cutscene, Shot, Track

DURATION = 3.5
CUT = 2.9
FALL_BACK = 0.30


def toward_entity(stage):
    """Direção horizontal (unitária) do jogador para a entidade, fixada quando a cutscene começa."""
    def compute(st):
        ex, ey, _ = st.entity_head()
        p = st.player
        dx, dy = ex - p.x, ey - p.y
        length = math.hypot(dx, dy) or 1.0
        return (dx / length, dy / length)
    return stage.memo("toward_entity", compute)


def fallen(back, drop):
    """Ponto dos olhos caindo: `back` metros para trás (longe dela) e `drop` metros abaixo da altura dos olhos."""
    def at(stage):
        dx, dy = toward_entity(stage)
        x, y, z = stage.player.eye
        return (x - dx * back, y - dy * back, max(z - drop, stage.player.z + 0.16))
    return at


def entity_head_now(stage):
    return stage.entity_head()


def build():
    def face(stage):
        """Onde o rosto vai parar no bote: à frente dos olhos, na direção da entidade."""
        dx, dy = toward_entity(stage)
        x, y, z = stage.player.eye
        return (x + dx * 0.42, y + dy * 0.42, z)

    eye = Path([Key(0.0, player_eye, True), Key(0.45, fallen(0.02, 0.0)), Key(0.78, fallen(0.10, 0.04)),
                Key(1.10, fallen(0.20, 0.55)), Key(1.48, fallen(FALL_BACK, 1.30)), Key(1.75, fallen(FALL_BACK + 0.04, 1.40)),
                Key(2.5, fallen(FALL_BACK + 0.08, 1.43)), Key(DURATION - 0.01, fallen(FALL_BACK + 0.10, 1.44), True)])
    look = looking((0.0, player_gaze, True), (0.30, entity_head_now), (1.0, entity_head_now),
                   (1.5, entity_head_now), (DURATION - 0.01, entity_head_now, True))
    rig = Rig(eye, look,
              fov=curve((0.0, 72.0), (0.35, 60.0), (0.8, 46.0), (1.5, 44.0), (2.6, 38.0), (DURATION - 0.01, 36.0)),
              roll=curve((0.0, 0.0), (0.7, 5.0), (1.45, 22.0), (2.2, 30.0), (DURATION - 0.01, 31.0)),
              hand=Hand("panic", Curve([(0.0, 0.6), (0.6, 1.0), (CUT, 1.4)])),
              impacts=(Impact(0.58, 1.9, 7.0, 5.0, 1.0), Impact(1.48, 2.2, 7.0, 5.5, 2.0), Impact(1.85, 0.8, 6.0, 4.5, 4.0)))
    cues = (
        Cue(0.0, act.entity_eyes(1.0)),
        Cue(0.0, act.entity_anim("attack")),
        Cue(0.0, act.flashlight_follows(True)),
        Cue(0.0, act.flash_hand(1.0)),
        Cue(0.05, act.sound("ent_scream", None, 1.0)),
        Cue(0.05, act.silence(6.0)),
        Cue(0.40, act.flashlight(False)),
        Cue(0.50, act.sound("gasp", None, 0.6)),
        Cue(0.58, act.sound("death_hit", None, 1.0)),
        Cue(1.40, act.sound("thud_1", None, 1.0)),
        Cue(1.95, act.sound("ent_static_burst", None, 0.8)),
        Cue(CUT, act.sound("death_hit", None, 1.0)),
        Cue(CUT, act.stop_all()),
        Cue(CUT + 0.4, act.entity_hide()),
    )
    tracks = (Track(0.12, 0.72, act.entity_lunge(player_eye), "in"),)
    shot = Shot(DURATION, cam=rig, name="bote", cues=cues, tracks=tracks,
                flash=((0.5, 0.0), (0.6, 0.85), (0.95, 0.0)),
                fade=((CUT - 0.001, 0.0), (CUT, 1.0)),
                shake=((0.0, 0.35), (0.6, 1.0), (CUT - 0.01, 1.0), (CUT, 0.0)))
    return Cutscene("death", "death_done", (shot,))
