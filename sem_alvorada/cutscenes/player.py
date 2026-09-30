"""CutscenePlayer: interpola os planos e executa as ações no anfitrião (`host`) do engine.

O player é puramente lógico: não desenha nada. A cada `update(dt)` ele
    1. dispara as ações (`Cue`) cujo tempo chegou e aplica as trilhas contínuas (`Track`);
    2. posiciona a `CutsceneCam` (posição, alvo, FOV, mão trêmula, tremor);
    3. anima a entidade, se ela estiver visível;
e `overlay()` diz ao HUD o que desenhar (fade, letterbox, legenda, cartão, flash).
"""
import math
from dataclasses import dataclass

from .. import conventions as C
from . import scripts
from .stage import Stage
from .timeline import compile_cutscene, ease, clamp01

SUBTITLE_FADE = 0.35            # segundos de entrada/saída de cada legenda
BREATH_HZ = 0.27


@dataclass
class Overlay:
    """O que o HUD desenha por cima do jogo durante uma cutscene."""
    fade: float = 0.0                 # 0..1 preto
    letterbox: float = 0.0            # 0..1 das barras
    subtitle: str = ""
    subtitle_alpha: float = 0.0
    card: tuple | None = None         # (título, subtítulo) ou None
    flash: float = 0.0                # 0..1 branco
    shake: float = 0.0                # 0..1: a câmera já treme sozinha; serve para o HUD tremer junto
    card_alpha: float = 1.0           # extensão do contrato: opacidade do cartão


class _Run:
    """Estado de uma cutscene em andamento."""

    def __init__(self, timeline, stage, camera, on_done):
        self.timeline = timeline
        self.stage = stage
        self.camera = camera
        self.on_done = on_done
        self.t = 0.0
        self.next_cue = 0
        self.tracks_done = [False] * len(timeline.tracks)


# --------------------------------------------------------------------------
# Câmera
# --------------------------------------------------------------------------
def _mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


def _axis_rotation(axis, radians):
    s = math.sin(radians / 2.0)
    return (math.cos(radians / 2.0), s if axis == "x" else 0.0, 0.0, s if axis == "z" else 0.0)


def camera_quaternion(yaw, pitch, roll):
    """Quaternion (w, x, y, z) de uma câmera do Blender que olha na direção de `yaw`/`pitch` com `roll`.

    A câmera olha para -Z local: girar 90 graus em X deita o eixo de visão no plano do chão (olhando +Y).
    """
    q = _axis_rotation("z", yaw)
    q = _mul(q, _axis_rotation("x", math.pi / 2.0 + pitch))
    return _mul(q, _axis_rotation("z", roll))


def look_angles(eye, target):
    """(yaw, pitch) em radianos para olhar de `eye` a `target`."""
    dx, dy, dz = (t - e for e, t in zip(eye, target))
    return C.dir_yaw(dx, dy), math.atan2(dz, math.hypot(dx, dy))


def _noise(t, seed):
    return (math.sin(t * 1.00 + seed) + 0.6 * math.sin(t * 2.37 + seed * 1.9)
            + 0.3 * math.sin(t * 5.11 + seed * 2.7)) / 1.9


def handheld_offsets(t, amount, shake):
    """(dx, dy, dz, dyaw, dpitch, droll): mão que respira e treme; `shake` (0..1) acrescenta sacudidas rápidas."""
    slow = amount
    fast = shake
    breath = math.sin(t * 2.0 * math.pi * BREATH_HZ)
    pos = (0.010 * slow * _noise(t * 0.9, 1.0) + 0.030 * fast * _noise(t * 9.0, 11.0),
           0.010 * slow * _noise(t * 0.8, 2.0) + 0.030 * fast * _noise(t * 8.0, 12.0),
           0.008 * slow * breath + 0.010 * slow * _noise(t * 1.1, 3.0) + 0.040 * fast * _noise(t * 10.0, 13.0))
    rot = (math.radians(0.35 * slow * _noise(t * 0.7, 4.0) + 1.4 * fast * _noise(t * 8.5, 14.0)),
           math.radians(0.30 * slow * _noise(t * 0.8, 5.0) + 1.2 * fast * _noise(t * 9.5, 15.0)),
           math.radians(0.30 * slow * _noise(t * 0.6, 6.0) + 1.6 * fast * _noise(t * 7.5, 16.0)))
    return (*pos, *rot)


class CutscenePlayer:
    def __init__(self, host):
        self.host = host
        self._run = None
        self._last_errors = ()

    # ------------------------------------------------------------------ API do contrato
    @property
    def active(self):
        return self._run is not None

    @property
    def name(self):
        return self._run.timeline.cutscene.name if self._run else ""

    @property
    def time(self):
        return self._run.t if self._run else 0.0

    @property
    def errors(self):
        """Erros de chamadas ao host durante a cutscene atual (vazio quando tudo correu bem)."""
        return list(self._run.stage.errors) if self._run else list(self._last_errors)

    def play(self, name, on_done=None):
        """Começa a cutscene `name`. `on_done()` roda depois de `host.finish(reason)`."""
        if self._run is not None:
            self._release(self._run)
        timeline = compile_cutscene(scripts.get(name))
        stage = Stage(self.host)
        camera = stage.obj(C.OBJ_CUT_CAM)
        if camera is None:
            stage.errors.append(f"objeto {C.OBJ_CUT_CAM} não existe: rode a etapa 'cutscenes' do build")
        else:
            stage.safe("set_camera", self.host.set_camera, camera)
        self._run = _Run(timeline, stage, camera, on_done)
        self._step(self._run, 0.0)

    def update(self, dt):
        run = self._run
        if run is None:
            return
        run.t = min(run.t + max(0.0, dt), run.timeline.total)
        self._step(run, dt)
        if run.t >= run.timeline.total:
            self._finish(run)

    def skip(self):
        """Pula a cutscene: roda o que muda o estado do jogo e termina."""
        run = self._run
        if run is None:
            return
        stage, timeline = run.stage, run.timeline
        for index, (t0, t1, track) in enumerate(timeline.tracks):
            if not run.tracks_done[index]:
                stage.safe(f"track {track.apply.__qualname__}", track.apply, stage, 1.0)
        for t, action in timeline.cues[run.next_cue:]:
            if action.essential:
                stage.safe(f"cue {action.run.__qualname__}", action, stage)
        run.t = timeline.total
        self._finish(run)

    def overlay(self):
        run = self._run
        if run is None:
            return Overlay()
        tl, t = run.timeline, run.t
        text, t0, t1 = tl.subtitle_at(t)
        alpha = 0.0
        if text:
            alpha = clamp01(min((t - t0) / SUBTITLE_FADE, (t1 - t) / SUBTITLE_FADE))
        card_alpha = clamp01(tl.sample("card", t))
        cutscene = tl.cutscene
        return Overlay(
            fade=clamp01(tl.sample("fade", t)),
            letterbox=clamp01(tl.sample("letterbox", t)),
            subtitle=text,
            subtitle_alpha=alpha,
            card=cutscene.card if (cutscene.card and card_alpha > 0.001) else None,
            flash=clamp01(tl.sample("flash", t)),
            shake=clamp01(tl.sample("shake", t)),
            card_alpha=card_alpha if cutscene.card else 0.0,
        )

    # ------------------------------------------------------------------ passos internos
    def _step(self, run, dt):
        self._fire_cues(run)
        self._apply_tracks(run)
        self._place_camera(run)
        self._animate_entity(run, dt)

    def _fire_cues(self, run):
        cues = run.timeline.cues
        while run.next_cue < len(cues) and cues[run.next_cue][0] <= run.t + 1e-9:
            action = cues[run.next_cue][1]
            run.next_cue += 1
            run.stage.safe(f"cue {action.run.__qualname__}", action, run.stage)

    def _apply_tracks(self, run):
        for index, (t0, t1, track) in enumerate(run.timeline.tracks):
            if run.t < t0 or run.tracks_done[index]:
                continue
            if run.t >= t1:
                run.stage.safe(f"track {track.apply.__qualname__}", track.apply, run.stage, 1.0)
                run.tracks_done[index] = True
            else:
                fraction = ease(track.ease, (run.t - t0) / (t1 - t0))
                run.stage.safe(f"track {track.apply.__qualname__}", track.apply, run.stage, fraction)

    def _place_camera(self, run):
        cam = run.camera
        if cam is None:
            return
        t0, t1, shot = run.timeline.shot_at(run.t)
        stage = run.stage
        f = ease(shot.ease, (run.t - t0) / (t1 - t0)) if shot.to is not None else 0.0
        a = shot.view
        b = shot.to or shot.view
        eye = _lerp3(stage.resolve(a.eye), stage.resolve(b.eye), f)
        target = _lerp3(stage.resolve(a.target), stage.resolve(b.target), f)
        if shot.follow:
            shift = stage.offset(shot.follow)
            eye, target = _add3(eye, shift), _add3(target, shift)
        fov = a.fov + (b.fov - a.fov) * f
        roll = math.radians(a.roll + (b.roll - a.roll) * f)

        shake = clamp01(run.timeline.sample("shake", run.t))
        dx, dy, dz, dyaw, dpitch, droll = handheld_offsets(run.t, shot.handheld, shake)
        yaw, pitch = look_angles(eye, target)
        cam.location = (eye[0] + dx, eye[1] + dy, eye[2] + dz)
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = camera_quaternion(yaw + dyaw, pitch + dpitch, roll + droll)
        cam.data.angle = math.radians(fov)

    def _animate_entity(self, run, dt):
        entity = getattr(run.stage.host, "entity", None)
        if entity is not None and getattr(entity, "visible", False):
            run.stage.safe("entity.update", entity.update, dt, 0.0)

    def _release(self, run):
        run.stage.finish_up()
        self._last_errors = tuple(run.stage.errors)
        self._run = None

    def _finish(self, run):
        self._release(run)
        run.stage.safe("set_camera(None)", self.host.set_camera, None)
        reason = run.timeline.cutscene.reason
        self.host.finish(reason)
        if run.on_done is not None:
            run.on_done()


def _lerp3(a, b, f):
    return tuple(x + (y - x) * f for x, y in zip(a, b))


def _add3(a, b):
    return tuple(x + y for x, y in zip(a, b))
