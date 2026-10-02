"""As mãos do jogador: pegar, segurar e usar itens, com animação.

A direita segura a lanterna o tempo todo; a esquerda mostra o item escolhido na roda (ou fica livre, e então
`held` vale `FLASHLIGHT`). Cada gesto é um clipe de dados (`handclips`) tocado por um executor que toca um
por vez, dispara os eventos em ordem e emenda qualquer troca sem salto (`handtrack`). Aqui ficam as decisões:
qual clipe, o que acontece no jogo em cada evento (`contact`, `light_on`, `swap_insert`...) e como as poses
viram alvos do braço (`body.arm(lado)`), objetos na mão (`handheld`) e luz (`Flashlight.lantern_matrix`).

Sem `BodyRig` (NullBody) os itens aparecem flutuando nas posições da câmera; com ele, a mesma pose vira o
alvo da mão. O contrato com o resto do jogo está em `docs/FASE3.md`.
"""
import math

import bpy  # noqa: F401 - `mathutils` só existe depois deste import
from mathutils import Euler, Matrix, Vector

from .. import conventions as C
from . import collision
from . import handclips as K
from .handheld import Handhelds, Pendulum, PivotAcceleration, Sway
from .handtrack import ClipPlayer, number

FOV_ZOOM = 0.17                  # quanto o campo de visão fecha quando o rosto "se aproxima" de uma nota na parede
MAP_LOOK_SECONDS = 1.6           # o mapa fica diante do rosto este tempo, se o jogador não apertar E de novo
CLICK_DECAY = 9.0
WALL_NOTES = frozenset({"NOTE_4", "NOTE_5"})        # presas na parede quando o alvo não traz `sa_mount`
RIGHT_LOCKED = frozenset({"lantern", "swap", "refuse"})


class _Job:
    """O que o clipe em curso quer dizer para o jogo."""
    __slots__ = ("kind", "target", "item", "on_contact", "on_done", "on_open", "note_id", "origin")

    def __init__(self, kind, target=None, item=None, on_contact=None, on_done=None, on_open=None,
                 note_id=None, origin=None):
        self.kind, self.target, self.item = kind, target, item
        self.on_contact, self.on_done, self.on_open = on_contact, on_done, on_open
        self.note_id, self.origin = note_id, origin


class Hands:
    def __init__(self, game):
        self.game = game
        self.runner = ClipPlayer()
        self.models = Handhelds(game.scene, game.player_cam)
        self.pendulum = Pendulum()
        self.pivot = PivotAcceleration()
        self.sway = {"R": Sway(0.0, 1.0), "L": Sway(1.7, 0.8)}
        self.last = {}                          # última pose entregue por lado: (pos, rot, curl, peso)
        self._base_fov = None
        self._clock = 0.0
        self._active = False
        self._released = {"R": False, "L": False}
        self._zoom_applied = 0.0
        self._previous_look = None
        self._previous_step = None
        self._last_note = None
        self._paper_size = (0.12, 0.16)
        self._lifted = None
        self._cam = (Matrix.Identity(4), Matrix.Identity(4))
        self.reset()

    # ---- consultas ----
    @property
    def held(self):
        """Tipo na mão esquerda; `FLASHLIGHT` = esquerda livre; None = sem lanterna e sem nada."""
        if self._held is not None:
            return self._held
        return C.ITEM_FLASHLIGHT if self.game.state.has_flashlight else None

    @property
    def busy(self):
        clip = self.runner.clip
        return (clip is not None and not clip.interruptible) or self._after is not None

    @property
    def last_note(self):
        notes = self.game.state.notes_read
        if self._last_note in notes:
            return self._last_note
        return sorted(notes)[-1] if notes else None

    def visible_kinds(self):
        return {kind for kind in self._visual.values() if kind is not None}

    # ---- ciclo de vida ----
    def reset(self):
        """Novo jogo ou checkpoint: o estado de jogo já foi restaurado, nada do que estava em curso vale."""
        self._restore_lifted_note()
        self.runner = ClipPlayer()
        self._job = None
        self._reading_job = None
        self._held = None
        self._persist_left = None
        self._goal = None
        self._after = None
        self._on_equipped = []
        self._left_mode = "hold"
        self._look_left = 0.0
        self._click = 0.0
        self._visual = {"R": None, "L": None}
        self._base_key = None
        self._previous_step = None
        for sway in self.sway.values():
            sway.reset()
        self.pendulum.reset()
        self.pivot.reset()
        self._hide_everything()

    def suspend(self):
        """O jogo saiu do controle do jogador (cutscene, título, morte): termina o gesto no estado e esconde tudo."""
        if not self._active:
            return
        self._after, self._on_equipped, self._goal = None, [], self._persist_left
        if self.runner.active:
            self.runner.abort(self._fire)
        self._job = self._reading_job = None
        self.runner = ClipPlayer()
        self._visual = {"R": None, "L": None}
        self._base_key = None
        self._hide_everything()

    def restore_scene(self):
        """Devolve os objetos ao estado do arquivo (ao sair do jogo)."""
        self._restore_lifted_note()
        self._hide_everything()
        self.models.restore_scene()

    def _hide_everything(self):
        self._active = False
        self.models.hide_all()
        flashlight = self.game.flashlight
        flashlight.lantern_matrix = None
        flashlight.swap_left = 0.0
        body = self.game.body
        for side in ("R", "L"):
            body.arm(side).release()
            self._released[side] = True
        self._apply_zoom(0.0)

    def _restore_lifted_note(self):
        target = self._lifted
        self._lifted = None
        if target is not None and target.obj is not None:
            target.obj.hide_viewport = target.obj.hide_render = False

    # ---- pegar ----
    def pickup(self, target, on_contact, on_done=None):
        """Estende a mão até o `Interactable`. `on_contact()` roda quando os dedos tocam o item (é ali que o
        inventário muda); `on_done()` roda quando a mão volta ao repouso. Devolve False se não puder começar."""
        if self.busy:
            return False
        item = target.item
        factory = {C.ITEM_FLASHLIGHT: K.lantern_first, C.ITEM_BATTERY: K.battery_pickup,
                   C.ITEM_KEY: K.key_pickup, C.ITEM_MAP: K.map_pickup}.get(item)
        if factory is None:                               # item sem gesto próprio: pega na hora
            on_contact()
            if on_done is not None:
                on_done()
            return True
        job = _Job("lantern" if item == C.ITEM_FLASHLIGHT else "pickup", target, item, on_contact, on_done)
        if item == C.ITEM_FLASHLIGHT:
            self._interrupt()
            self._start(factory(), job)
        else:
            self._when_left_free(lambda: self._start(factory(), job))
        return True

    # ---- segurar ----
    def equip(self, kind, on_done=None):
        """Coloca `kind` na mão esquerda (FLASHLIGHT ou None deixam a esquerda livre). False se a mão está ocupada."""
        if self.busy:
            return False
        goal = None if kind in (None, C.ITEM_FLASHLIGHT) else kind
        self._held = goal
        self._goal = goal
        if on_done is not None:
            self._on_equipped.append(on_done)
        clip = self.runner.clip
        if clip is None:
            self._equip_step()
        elif not clip.name.startswith("stow"):
            self._interrupt()          # só chega aqui um gesto interruptível; o fim dele continua a troca
        return True                    # (um guardar em curso segue até o fim e então traz o item novo)

    def _when_left_free(self, action):
        """Guarda o que a esquerda segura (se segura algo) e então roda `action`."""
        self._goal = None
        self._held = None
        self._after = action
        if self.runner.active:
            self._interrupt()
        else:
            self._equip_step()

    def _equip_step(self):
        if self.runner.active:
            return
        if self._persist_left != self._goal:
            if self._persist_left is not None:
                self._start(K.stow(self._persist_left), _Job("equip"))
            else:
                self._start(K.draw(self._goal), _Job("equip"))
            return
        callbacks, self._on_equipped = self._on_equipped, []
        for callback in callbacks:
            callback()
        action, self._after = self._after, None
        if action is not None:
            action()

    # ---- lanterna ----
    def toggle_flashlight(self):
        """F: só o clique do polegar. A luz muda no mesmo quadro; a mão responde com um toque curto."""
        if not self.game.state.has_flashlight or self._right_locked():
            return
        self.game.flashlight.toggle()
        self._click = 1.0

    def reload_flashlight(self):
        """R: troca as pilhas com as duas mãos; sem pilha reserva (ou com a carga ainda boa) é um gesto de recusa."""
        flashlight = self.game.flashlight
        if not self.game.state.has_flashlight or self._right_locked() or self.busy:
            return
        reason = flashlight.reload_blocker()
        if reason == "busy":
            return
        if reason is not None:
            self._interrupt()
            self._start(K.refuse(), _Job("refuse"))
            return
        if self._persist_left in (C.ITEM_KEY, C.ITEM_MAP, C.ITEM_NOTE):
            self._when_left_free(self._begin_swap)
        else:
            self._interrupt()
            self._begin_swap()

    def _begin_swap(self):
        spare_after = self.game.state.spare_batteries - 1
        palm = self._persist_left == C.ITEM_BATTERY
        left_end = C.ITEM_BATTERY if palm and spare_after > 0 else None
        if palm:
            self._persist_left = self._goal = self._held = left_end
        self._start(K.swap(C.ITEM_BATTERY if palm else None, left_end), _Job("swap"))

    def _right_locked(self):
        return self._job is not None and self._job.kind in RIGHT_LOCKED

    # ---- leitura ----
    def begin_read(self, note_id, on_open):
        """Levanta a folha até o rosto e então chama `on_open()` (que abre o leitor). O gesto vence qualquer
        outro: se a mão estava ocupada com algo interruptível, ele termina na hora."""
        target = self._note_target(note_id)
        self._last_note = note_id
        self._paper_size = self.models.set_paper(note_id)
        job = _Job("read", target, C.ITEM_NOTE, on_open=on_open, note_id=note_id)
        if target is None:
            job.origin = "held" if self._persist_left == C.ITEM_NOTE else "pocket"
            if job.origin == "held":
                self._interrupt()
                self._start(K.note_raise(False), job)
            else:
                self._when_left_free(lambda: self._start(K.note_raise(True), job))
            return True
        job.origin = "wall" if self._is_wall_note(target) else "floor"
        factory = K.note_wall if job.origin == "wall" else K.note_pickup
        self._when_left_free(lambda: self._start(factory(), job))
        return True

    def end_read(self):
        """O leitor fechou: a folha volta ao lugar (ou desce), ou a mão recua da parede."""
        job = self._reading_job
        if job is None:
            return
        self._reading_job = None
        self._interrupt()
        clip = {"floor": K.note_putback, "wall": K.note_retreat, "held": K.note_to_hold,
                "pocket": lambda: K.stow(C.ITEM_NOTE)}[job.origin]()
        self._start(clip, _Job("lower", job.target, C.ITEM_NOTE, origin=job.origin))

    def use_held(self):
        """E sem alvo na mira: o mapa vem ao rosto (e volta no segundo E ou depois de um tempo); a anotação
        reabre o leitor. Devolve True se a mão fez algo."""
        if self._left_mode == "near" and not self.runner.active:
            self._start(K.map_back(), _Job("look", origin="back"))
            return True
        if self.busy:
            return False
        if self._persist_left == C.ITEM_MAP:
            self._interrupt()
            self._start(K.map_near(), _Job("look", origin="near"))
            return True
        note = self.last_note
        if self._persist_left == C.ITEM_NOTE and note is not None:
            return self.begin_read(note, lambda: self.game.open_note(note))
        return False

    def _note_target(self, note_id):
        current = self.game.interact.current
        if current is not None and current.kind == "note" and current.ref == note_id:
            return current
        return None

    @staticmethod
    def _is_wall_note(target):
        mount = target.obj.get("sa_mount") if target.obj is not None else None
        return mount == "wall" if mount is not None else target.ref in WALL_NOTES

    # ---- executor ----
    def _start(self, clip, job):
        self._job = job
        self.runner.start(clip)

    def _interrupt(self):
        if self.runner.active:
            self.runner.abort(self._fire)

    def _fire(self, event):
        handler = getattr(self, f"_on_{event.name}", None)
        if handler is not None:
            handler(event.arg)

    def _on_sound(self, name):
        self.game.sound(name, None, 0.8)

    def _on_contact(self, _):
        job = self._job
        if job.kind == "read":
            self._lift_world_note(job.target)
            return
        if job.item == C.ITEM_FLASHLIGHT:
            self.game.state.find_flashlight()       # antes do contato terminar: o checkpoint já leva a carga certa
        job.on_contact()

    def _on_touch(self, _):
        pass

    def _on_show(self, arg):
        side, kind = arg
        self._visual[side] = kind

    def _on_hide(self, side):
        self._visual[side] = None

    def _on_set_left(self, kind):
        self._persist_left = kind
        if kind != C.ITEM_MAP:
            self._left_mode = "hold"

    def _on_light_on(self, _):
        self.game.flashlight.switch(True)
        self._click = 1.0

    def _on_burst(self, index):
        start, length = K.FLICKER_BURSTS[index]
        self.game.flashlight.burst(length)
        self.game.sound("flash_flicker_burst", None, 0.8)

    def _on_swap_begin(self, _):
        self.game.flashlight.begin_swap(self.runner.clip.duration)

    def _on_swap_insert(self, _):
        self.game.flashlight.finish_swap()
        self.game.sound("battery_insert", None, 0.8)

    def _on_swap_end(self, _):
        self.game.flashlight.end_swap()

    def _on_open(self, _):
        job = self._job
        self._reading_job = job
        if job.on_open is not None:
            job.on_open()

    def _on_putback(self, _):
        self._restore_lifted_note()
        self._visual["L"] = None

    def _on_done(self, _):
        job, self._job = self._job, None
        self._settle_visuals()
        if job is not None and job.kind == "look":
            near = job.origin == "near" and self._persist_left == C.ITEM_MAP
            self._left_mode = "near" if near else "hold"
            self._look_left = MAP_LOOK_SECONDS
        if job is not None and job.on_done is not None:
            job.on_done()
        self._equip_step()

    def _lift_world_note(self, target):
        """A folha sai do lugar com a mão: o objeto de mesa some até ela voltar."""
        self._restore_lifted_note()
        if target is not None and target.obj is not None:
            target.obj.hide_viewport = target.obj.hide_render = True
            self._lifted = target

    def _settle_visuals(self):
        """Fim de um gesto: cada mão passa a mostrar só o que fica nela em repouso."""
        paper = self._reading_job is not None and self._reading_job.origin in ("floor", "held", "pocket")
        self._visual["L"] = C.ITEM_NOTE if paper else self._persist_left

    # ---- quadro a quadro ----
    def update(self, dt, bob):
        """Todo quadro de jogo. `bob` é (lateral, vertical) do head bob em metros."""
        game = self.game
        self._active = True
        self._clock += dt
        self._update_camera_matrix()
        channels = self.runner.update(dt, self._base, self._anchors(), self._fire)
        self._tick_look_timer(dt)
        yaw_rate, pitch_rate = self._look_rates(dt)
        flashlight = game.flashlight
        if flashlight.swap_left > 0 and self.runner.clip is not None and self.runner.clip.name == "swap":
            flashlight.swap_left = max(1e-3, self.runner.clip.duration - self.runner.time)
        self._click = max(0.0, self._click - CLICK_DECAY * dt)
        hard = game.player.breathing_hard
        self._pose_hand("R", channels, dt, bob, yaw_rate, pitch_rate, hard)
        self._pose_hand("L", channels, dt, bob, yaw_rate, pitch_rate, hard)
        self._apply_extras(channels, dt)
        self._apply_visibility()

    def _tick_look_timer(self, dt):
        if self._left_mode == "near" and not self.runner.active:
            self._look_left -= dt
            if self._look_left <= 0:
                self._start(K.map_back(), _Job("look", origin="back"))

    def _look_rates(self, dt):
        player = self.game.player
        previous, self._previous_look = self._previous_look, (player.yaw, player.pitch)
        if previous is None or dt <= 0:
            return 0.0, 0.0
        yaw = (player.yaw - previous[0] + math.pi) % math.tau - math.pi
        return yaw / dt, (player.pitch - previous[1]) / dt

    # ---- base (repouso) ----
    def _base(self):
        self._visual["R"] = C.ITEM_FLASHLIGHT if self.game.state.has_flashlight else None
        left = self._visual["L"]
        mode = "hold"
        if left == C.ITEM_NOTE and self._reading_job is not None:
            mode = "face"
        elif left == C.ITEM_MAP and self._left_mode == "near":
            mode = "near"
        key = (self._visual["R"], left, mode)
        if key != self._base_key:
            self._base_key = key
            self.runner.rebase()
        channels = {**K.rest_channels("R", self._visual["R"]), **K.rest_channels("L", left, mode)}
        channels.update({name: number(value) for name, value in K.EXTRAS.items()})
        return channels

    def _anchors(self):
        clip, job = self.runner.clip, self._job
        if clip is None or job is None or not clip.meta.get("grasp") or job.target is None:
            return None
        point = self._world_point(job.target)
        reach = Vector(point)
        if reach.length > K.REACH_LIMIT:
            reach *= K.REACH_LIMIT / reach.length
        reach.z = min(reach.z, -0.20)
        return {f"{clip.meta['grasp']}.pos": tuple(reach)}

    # ---- mundo -> câmera ----
    def _update_camera_matrix(self):
        position, rotation = self.game.player.camera_pose()
        matrix = Euler(rotation, "XYZ").to_matrix().to_4x4()
        matrix.translation = Vector(position)
        self._cam = (matrix, matrix.inverted())

    def _world_point(self, target):
        """Posição do alvo no espaço da câmera."""
        position = collision.object_position(target.obj) if target.obj is not None else target.position
        return self._cam[1] @ Vector(position)

    def _world_model_matrix(self, target, kind):
        """Pose, no espaço da câmera, que o modelo da mão teria se estivesse onde o item de mesa está."""
        if target.obj is not None:
            world = collision.world_matrix(target.obj)
        else:
            world = Matrix.Translation(Vector(target.position))
        return self._cam[1] @ world @ K.ITEM_TO_MODEL[kind]

    # ---- poses ----
    def _pose_hand(self, side, channels, dt, bob, yaw_rate, pitch_rate, hard):
        pos = Vector(channels[f"{side}.pos"])
        rot = list(channels[f"{side}.rot"])
        curl = list(channels[f"{side}.curl"])
        weight = channels[f"{side}.w"][0]
        attach = channels[f"{side}.attach"][0]
        sway_pos, sway_rot = self.sway[side].step(dt, self._clock, bob, yaw_rate, pitch_rate, hard)
        pos += Vector(sway_pos)
        rot = [a + b for a, b in zip(rot, sway_rot)]
        if side == "R":
            pitch, yaw = self.game.flashlight.offset
            rot[0] += math.degrees(pitch) * 1.4
            rot[1] += math.degrees(yaw) * 1.4
            pos.y -= 0.006 * self._click
            curl[0] = min(1.0, curl[0] + 0.32 * self._click)
        self.last[side] = (tuple(pos), tuple(rot), tuple(curl), weight)
        self._drive_arm(side, tuple(pos), tuple(rot), tuple(curl), weight)
        kind = self._visual[side]
        if kind is not None:
            self._place_item(kind, pos, rot, attach, dt)
        elif side == "R":
            self.game.flashlight.lantern_matrix = None

    def _drive_arm(self, side, pos, rot, curl, weight):
        arm = self.game.body.arm(side)
        if weight > 0.01:
            arm.set_target(pos, rot, min(1.0, weight))
            arm.set_fingers(tuple(min(1.0, max(0.0, c)) for c in curl))
            self._released[side] = False
        elif not self._released[side]:
            arm.release()
            self._released[side] = True

    def _place_item(self, kind, pos, rot, attach, dt):
        hand = K.pose_matrix(pos, rot)
        carried = K.GRIPS[kind].item_of(hand)
        matrix, scale = self._blend_with_world(kind, carried, attach)
        if kind == C.ITEM_KEY:
            self._tick_key(dt, matrix)
            matrix = matrix @ self.pendulum.matrix()
        elif kind == C.ITEM_NOTE:
            scale = (scale[0] * self._paper_size[0], scale[1] * self._paper_size[1], scale[2])
        if kind == C.ITEM_FLASHLIGHT:
            self.game.flashlight.lantern_matrix = matrix
        self.models.place(kind, matrix, scale)

    def _blend_with_world(self, kind, carried, attach):
        """Antes de preso à mão o item ainda está onde o mundo o deixou: mistura as duas poses."""
        scale = K.WORLD_SCALE.get(kind, 1.0)
        job, clip = self._job, self.runner.clip
        if attach >= 0.999 or job is None or job.target is None or clip is None or not clip.meta.get("world_item"):
            return carried, (1.0, 1.0, 1.0)
        mix = max(0.0, min(1.0, attach))
        mix = mix * mix * (3.0 - 2.0 * mix)
        world = self._world_model_matrix(job.target, kind)
        position = world.translation.lerp(carried.translation, mix)
        rotation = world.to_quaternion().slerp(carried.to_quaternion(), mix)
        blended = rotation.to_matrix().to_4x4()
        blended.translation = position
        uniform = scale + (1.0 - scale) * mix
        return blended, (uniform, uniform, uniform)

    def _tick_key(self, dt, matrix):
        accel = self.pivot.update(dt, tuple(matrix.translation))
        self.pendulum.step(dt, accel)
        player = self.game.player
        step = int(player.stride_phase // math.pi)
        if self._previous_step is not None and step != self._previous_step and player.running and player.speed > 1.0:
            self.pendulum.kick(0.9, 0.3)
            self.game.make_noise("key_jingle", player.feet, C.NOISE_PLAYER["key_jingle"], sound="key_jingle")
        self._previous_step = step

    def _apply_extras(self, channels, dt):
        self.models.set_cap(channels["x.cap"][0])
        self.models.set_map_folds(channels["x.fold1"][0], channels["x.fold2"][0])
        self._apply_zoom(channels["x.zoom"][0])

    def _apply_zoom(self, amount):
        cam = self.game.player_cam
        if cam is None or cam.data is None or abs(amount - self._zoom_applied) < 1e-4:
            return
        if self._base_fov is None:
            self._base_fov = cam.data.angle
        self._zoom_applied = amount
        cam.data.angle = self._base_fov * (1.0 - FOV_ZOOM * amount)

    def _apply_visibility(self):
        shown = self.visible_kinds()
        for kind in self.models.objects:
            self.models.present(kind, kind in shown)
        if C.ITEM_KEY not in shown:
            self.pivot.reset()
            self.pendulum.reset()
