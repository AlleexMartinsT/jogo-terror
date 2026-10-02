"""CutscenePlayer: executa os planos e as ações no anfitrião (`host`) do engine.

O player é puramente lógico: não desenha nada. A cada `update(dt)` ele
    1. dispara as ações (`Cue`), aplica as trilhas contínuas (`Track`) e avança os atores (vento, carro, pêndulos);
    2. avalia o `Rig` do plano e posiciona a `CutsceneCam` (posição, rotação, FOV, foco, mão, pancadas);
    3. anima a entidade e o corpo do jogador, se estiverem em cena;
e `overlay()` diz ao HUD o que desenhar (fade, letterbox, legenda, cartão, flash).
"""
import math
import os
from dataclasses import dataclass

from .. import conventions as C
from . import camera, scripts
from .camera import camera_quaternion, look_angles  # noqa: F401  (a API antiga; testes e ferramentas importam daqui)
from .curves import clamp01, ease, noise
from .stage import Stage
from .timeline import compile_cutscene

SUBTITLE_FADE = 0.35            # segundos de entrada/saída de cada legenda
FOCUS_FOLLOW = 7.0              # 1/s: o foco automático alcança o alvo sem pulo
LID_DISTANCE = 0.055            # as pálpebras ficam coladas na lente
LID_MARGIN = math.radians(6.0)
FLASH_HAND_RAD = math.radians(2.6)
DOF_DEFAULT = os.environ.get("SA_CUTSCENE_DOF", "1") != "0"


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

    def __init__(self, timeline, stage, camera_obj, on_done):
        self.timeline = timeline
        self.stage = stage
        self.camera = camera_obj
        self.on_done = on_done
        self.t = 0.0
        self.next_cue = 0
        self.tracks_done = [False] * len(timeline.tracks)
        self.shot = -1
        self.focus = None             # estado do filtro do foco automático
        self.quaternion = None


class CutscenePlayer:
    def __init__(self, host, dof=None):
        """`dof`: False desliga a profundidade de campo da câmera de cutscene (padrão: ligada, ver SA_CUTSCENE_DOF)."""
        self.host = host
        self.dof = DOF_DEFAULT if dof is None else dof
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
        camera_obj = stage.obj(C.OBJ_CUT_CAM)
        if camera_obj is None:
            stage.errors.append(f"objeto {C.OBJ_CUT_CAM} não existe: rode a etapa 'cutscenes' do build")
        else:
            stage.safe("set_camera", self.host.set_camera, camera_obj)
        self._run = _Run(timeline, stage, camera_obj, on_done)
        self._step(self._run, 0.0)

    def update(self, dt):
        run = self._run
        if run is None:
            return
        dt = max(0.0, dt)
        run.t = min(run.t + dt, run.timeline.total)
        self._step(run, dt)
        if run.t >= run.timeline.total:
            self._finish(run)

    def skip(self):
        """Pula a cutscene: roda o que muda o estado do jogo e termina."""
        run = self._run
        if run is None:
            return
        stage, timeline = run.stage, run.timeline
        stage.skipping = True
        # na ordem do tempo, como numa execução completa: uma trilha só chega ao fim depois das ações que a precedem
        pending = [(t, 0, action) for t, action in timeline.cues[run.next_cue:] if action.essential]
        pending += [(t1, 1, (stage, track)) for index, (t0, t1, track) in enumerate(timeline.tracks)
                    if not run.tracks_done[index]]
        for _, kind, item in sorted(pending, key=lambda entry: (entry[0], entry[1])):
            if kind == 0:
                stage.safe(f"cue {item.run.__qualname__}", item, stage)
            else:
                stage.safe(f"track {item[1].apply.__qualname__}", item[1].apply, stage, 1.0)
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
        stage = run.stage
        stage.t, stage.dt = run.t, dt
        self._fire_cues(run)
        self._apply_tracks(run)
        stage.update_actors(dt)
        self._place_camera(run, dt)
        stage.update_actors(dt, late=True)
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

    def _place_camera(self, run, dt):
        cam = run.camera
        if cam is None:
            return
        tl, stage = run.timeline, run.stage
        index = tl.shot_index(run.t)
        t0, _, shot = tl.shots[index]
        rig = tl.rigs[index]
        if index != run.shot:
            run.shot, run.focus = index, None
        stress = clamp01(tl.sample("shake", run.t))
        state = camera.evaluate(rig, run.t - t0, stage, stress, self.dof)
        self._smooth_focus(run, rig, state, dt)
        position, q = self._world_pose(stage, state)
        q = camera.keep_hemisphere(q, run.quaternion)
        run.quaternion = q
        cam.location = position
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = q
        stage.camera_pose = (position, q)
        stage.safe("lens", camera.apply_lens, cam, state)
        self._apply_lids(run, tl.sample("lids", run.t), state.fov)
        if stage.flashlight_follows:
            self._carry_flashlight(stage, position, q)

    @staticmethod
    def _world_pose(stage, state):
        q = camera_quaternion(state.yaw, state.pitch, state.roll)
        if not state.mount:
            return state.eye, q
        origin, qm = stage.mount_transform(state.mount)
        r = camera.rotate(qm, state.eye)
        return (origin[0] + r[0], origin[1] + r[1], origin[2] + r[2]), camera.qmul(qm, q)

    @staticmethod
    def _smooth_focus(run, rig, state, dt):
        """O foco automático segue o alvo com um atraso curto: troca de alvo vira rack focus, não pulo."""
        if state.focus is None or rig.focus != "auto":
            run.focus = None
            return
        if run.focus is None:
            run.focus = state.focus
        else:
            run.focus += (state.focus - run.focus) * (1.0 - math.exp(-FOCUS_FOLLOW * max(dt, 1e-4)))
        state.focus = run.focus

    def _apply_lids(self, run, closed, fov):
        """Pálpebras: dois planos colados na lente (filhos da câmera). 0 aberto, 1 fechado."""
        stage = run.stage
        top, bottom = stage.touch(stage.obj("Cut_LidTop")), stage.touch(stage.obj("Cut_LidBottom"))
        if top is None or bottom is None:
            return
        visible = closed > 0.002
        for lid in (top, bottom):
            if lid.hide_render == visible:
                stage.set_hidden(lid, not visible)
        if not visible:
            return
        half_v = math.atan(math.tan(math.radians(fov) / 2.0) * C.RES_Y / C.RES_X)
        open_edge = half_v + LID_MARGIN + math.radians(4.0)
        shut_edge = -math.radians(2.0)
        edge = open_edge + (shut_edge - open_edge) * ease("smooth", closed)
        y = math.tan(edge) * LID_DISTANCE
        top.location = (0.0, y, -LID_DISTANCE)
        bottom.location = (0.0, -y, -LID_DISTANCE)

    def _carry_flashlight(self, stage, position, q):
        """A lanterna do jogo é filha da PlayerCam, parada durante a cutscene: leva-a para a mão do Daniel."""
        pcam = stage.touch(stage.obj(C.OBJ_PLAYER_CAM))
        if pcam is None:
            return
        hand = stage.flash_hand
        if hand > 0.0:
            t = stage.t
            tremor = camera.qmul(camera.axis_rotation("x", FLASH_HAND_RAD * hand * noise(t * 31.0, 3.0)),
                                 camera.qmul(camera.axis_rotation("y", FLASH_HAND_RAD * hand * noise(t * 27.0, 4.0)),
                                             camera.axis_rotation("z", FLASH_HAND_RAD * hand * noise(t * 23.0, 5.0))))
            q = camera.qmul(q, tremor)
        yaw, pitch = stage.flash_aim
        if yaw or pitch:
            q = camera.qmul(q, camera.qmul(camera.axis_rotation("y", math.radians(yaw)),
                                           camera.axis_rotation("x", math.radians(pitch))))
        pcam.location = position
        pcam.rotation_mode = "QUATERNION"
        pcam.rotation_quaternion = q

    def _animate_entity(self, run, dt):
        entity = getattr(run.stage.host, "entity", None)
        if entity is not None and getattr(entity, "visible", False):
            run.stage.safe("entity.update", entity.update, dt, run.stage.entity_speed)

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
