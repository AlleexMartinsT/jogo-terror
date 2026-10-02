"""Fábricas de ações (`Cue`) e de trilhas contínuas (`Track.apply`) usadas pelos roteiros.

Convenção: ações que MUDAM O ESTADO DO JOGO (energia, porta, posição do jogador, entidade, cérebro)
são `essential=True`: se o jogador pular a cutscene, elas rodam mesmo assim. Som, luz cosmética, atores,
corpo e câmera não são essenciais.
"""
import math

from .curves import Curve, Path, as_curve, clamp01, lerp3
from .timeline import Action

Vec = tuple


# --------------------------------------------------------------------------
# Som e luz
# --------------------------------------------------------------------------
def sound(name, pos=None, volume=1.0, pitch=1.0):
    return Action(lambda st: st.sound(name, st.resolve(pos), volume, pitch))


def loop(key, name, volume=1.0):
    return Action(lambda st: st.loop(key, name, volume))


def stop_loop(key):
    return Action(lambda st: st.stop_loop(key))


def silence(seconds):
    return Action(lambda st: st.safe("noise_silence", st.host.noise_silence, seconds))


def power(on, flicker=0.0):
    return Action(lambda st: st.safe("set_power", st.host.set_power, on, flicker), essential=True)


def flashlight(on):
    return Action(lambda st: st.safe("set_flashlight", st.host.set_flashlight, on), essential=True)


def flashlight_follows(on=True):
    """A lanterna do jogo passa a seguir a câmera da cutscene (com o tremor da mão); a PlayerCam volta no fim."""
    def run(stage):
        stage.flashlight_follows = on
    return Action(run)


def flash_hand(level):
    """Quanto a lanterna treme na mão do Daniel (0..1)."""
    def run(stage):
        stage.flash_hand = level
    return Action(run)


def cut_light(name, energy):
    """Liga (energia > 0) ou apaga uma luz `CutLight_*`."""
    return Action(lambda st: st.set_light(name, energy))


def house_light(name, gain):
    """Realça ou escurece uma luz da casa (`Light_*`) por cima do que o LightManager decidiu."""
    return Action(lambda st: st.house_light(name, gain))


def headlights(on):
    return Action(lambda st: st.headlights(on))


def stop_all():
    return Action(lambda st: st.stop_all_loops())


def show(name, visible=True):
    return Action(lambda st: st.set_visible(name, visible))


def hide_matching(anchor_pos, radius, needles, unless=("nightstand", "col_", "anchor", "light", "cut")):
    """Esconde objetos cujo nome contém alguma das palavras (e nenhuma de `unless`) perto de `anchor_pos`."""
    def run(stage):
        scene = getattr(stage.host, "scene", None)
        if scene is None:
            return
        for obj in scene.objects:
            lowered = obj.name.lower()
            if not any(n in lowered for n in needles) or any(u in lowered for u in unless):
                continue
            x, y, z = obj.matrix_world.translation
            if math.dist((x, y), anchor_pos[:2]) < radius and abs(z - anchor_pos[2]) < 0.8:
                stage.set_hidden(obj, True)
    return Action(run)


# --------------------------------------------------------------------------
# Atores (animação de objetos que dura vários quadros; ver anim.py)
# --------------------------------------------------------------------------
def actor(key, factory):
    """Começa um ator. `factory(stage)` cria uma instância nova a cada execução (o ator tem estado) e pode olhar o palco."""
    return Action(lambda st: st.start_actor(key, factory(st)))


def stop_actor(key):
    return Action(lambda st: st.stop_actor(key))


# --------------------------------------------------------------------------
# Jogador, portas e cérebro
# --------------------------------------------------------------------------
def place_player(x, y, z, yaw):
    """Reposiciona o jogador. Cada argumento pode ser número ou função `stage -> número`."""
    def run(stage):
        stage.safe("place_player", stage.host.place_player, *(stage.resolve(v) for v in (x, y, z, yaw)))
    return Action(run, essential=True)


def activate_brain(pos=None):
    """Acorda o cérebro da entidade. `pos` (ponto ou função) diz onde a cutscene a deixou, para seguir dali."""
    def run(stage):
        where = stage.resolve(pos)
        if where is None:
            stage.safe("entity_brain_activate", stage.host.entity_brain_activate)
            return
        try:
            stage.host.entity_brain_activate(where)
        except TypeError:                          # host antigo, sem o argumento
            stage.safe("entity_brain_activate", stage.host.entity_brain_activate)
        except Exception as exc:                   # noqa: BLE001
            stage.errors.append(f"entity_brain_activate: {exc!r}")
    return Action(run, essential=True)


def open_door(door_id, seconds=1.4):
    """Abre a porta com o movimento do jogo (`doors.set_openness`, a mesma curva suave das portas).

    Ao pular, a porta é posta aberta na hora (o Director cobraria isso de qualquer jeito).
    """
    def run(stage):
        doors = stage.host.doors
        if stage.skipping:
            stage.safe("doors.snap", doors.snap, door_id, 1.0)
        else:
            stage.safe("doors.set_openness", doors.set_openness, door_id, 1.0, 1.0 / seconds)
    return Action(run, essential=True)


# --------------------------------------------------------------------------
# Entidade
# --------------------------------------------------------------------------
def entity_place(pos, yaw, anim="idle", eyes=0.0, visible=True, erect=False):
    """Coloca a entidade em `pos` olhando para `yaw` (radianos) com a animação dada.

    `erect`: ao ar livre ela fica de pé com os 2,65 m; dentro de casa a rig a curva para caber sob o forro.
    """
    def run(stage):
        entity = stage.entity
        if erect:
            stage.stand_tall(entity)
        x, y, z = stage.resolve(pos)
        entity.set_visible(visible)
        entity.set_transform(x, y, z, stage.resolve(yaw))
        entity.set_anim(anim)
        entity.eyes(eyes)
    return Action(run, essential=True)


def entity_anim(name):
    return Action(lambda st: st.entity.set_anim(name), essential=True)


def entity_eyes(level):
    return Action(lambda st: st.entity.eyes(level), essential=True)


def entity_look(target, rate=None):
    """Trilha: a cabeça segue `target` (tupla ou função) enquanto durar. `rate` em graus/s, se a rig aceitar.

    A rig só mantém o olhar enquanto for renovado, então isto roda todo quadro da trilha.
    """
    def apply(stage, f):
        entity = stage.entity
        if rate is not None and hasattr(entity, "look_rate"):
            entity.look_rate = rate
        entity.look_at(*stage.resolve(target))
    return apply


def entity_hide():
    return Action(lambda st: st.entity.set_visible(False), essential=True)


def entity_walk(start, end, yaw, anim="stalk"):
    """Trilha: a entidade anda de `start` a `end` (passo constante) e a rig anima o passo no ritmo da velocidade.

    Use com `Track(..., ease="linear")`: a velocidade é distância / duração, que a trilha não conhece, então
    o roteiro passa a duração em `entity_walk_speed`. Aqui `f` só interpola a posição.
    """
    def apply(stage, f):
        entity = stage.entity
        x, y, z = lerp3(stage.resolve(start), stage.resolve(end), f)
        entity.set_transform(x, y, z, stage.resolve(yaw))
        if f < 1.0:
            entity.set_anim(anim)
    return apply


def entity_speed(value):
    """Velocidade (m/s) que o passo da entidade usa a partir daqui; 0 a faz parar no lugar."""
    def run(stage):
        stage.entity_speed = value
    return Action(run, essential=True)


def entity_stands(anim):
    """Termina a caminhada: para o passo e põe a animação `anim`."""
    def run(stage):
        stage.entity_speed = 0.0
        stage.entity.set_anim(anim)
    return Action(run, essential=True)


# --------------------------------------------------------------------------
# Corpo do jogador (BodyRig; sem ele, NullBody e tudo isto vira nada)
# --------------------------------------------------------------------------
def body_show(on=True):
    """Mostra o corpo do Daniel na cutscene e prende a referência dos braços à câmera da cutscene."""
    def run(stage):
        stage.show_body(on)
        if on:
            stage.body_call("attach_view", stage.obj("CutsceneCam"))
    return Action(run)


def body_pose(name, seconds=0.0):
    return Action(lambda st: st.body_call("pose", name, seconds))


def body_place(x, y, z, yaw):
    def run(stage):
        stage.body_call("place", *(stage.resolve(v) for v in (x, y, z, yaw)))
    return Action(run)


def arm_release(side, blend=0.6):
    def run(stage):
        arm = stage.arm(side)
        if arm is not None:
            stage.safe("arm.release", arm.release, blend)
    return Action(run)


class HandKey:
    """Uma chave da mão: no espaço da câmera (X direita, Y cima, -Z frente, metros), rotação em graus, peso do IK, dedos."""
    __slots__ = ("t", "pos", "rot", "weight", "curls", "spread")

    def __init__(self, t, pos, rot=(0.0, 0.0, 0.0), weight=1.0, curls=(0.25,) * 5, spread=0.0):
        self.t, self.pos, self.rot, self.weight, self.curls, self.spread = t, pos, rot, weight, curls, spread


def hand_track(side, duration, keys):
    """Trilha da mão `side` ("L"/"R"): percorre `keys` (tempos relativos ao começo da trilha, em segundos)."""
    keys = sorted(keys, key=lambda k: k.t)
    pos = Path([(k.t, k.pos) for k in keys], rest_ends=False)
    rot = Path([(k.t, k.rot) for k in keys], rest_ends=False)
    weight = Curve([(k.t, k.weight) for k in keys], rest_ends=False)
    spread = Curve([(k.t, k.spread) for k in keys], rest_ends=False)
    curls = [Curve([(k.t, k.curls[i]) for k in keys], rest_ends=False) for i in range(5)]

    def apply(stage, f):
        arm = stage.arm(side)
        if arm is None:
            return
        t = f * duration
        stage.safe("arm.set_target", arm.set_target, pos.at(t), rot.at(t), clamp01(weight(t)))
        stage.safe("arm.set_fingers", arm.set_fingers, [clamp01(c(t)) for c in curls], spread(t))
    return apply


# --------------------------------------------------------------------------
# Trilhas contínuas: recebem (stage, f) com f de 0 a 1
# --------------------------------------------------------------------------
def dawn_ramp(start, end):
    """O céu clareia de `start` a `end` (0 = noite, 1 = horizonte e halo bem mais claros)."""
    def apply(stage, f):
        stage.set_dawn(start + (end - start) * f)
    return apply


def eyes_ramp(start, end):
    def apply(stage, f):
        stage.entity.eyes(start + (end - start) * f)
    return apply


def light_ramp(name, start, end):
    def apply(stage, f):
        energy = start + (end - start) * f
        stage.set_light(name, energy)
    return apply


def entity_lunge(eye, amount_start=0.0, amount_end=1.0):
    """Leva a entidade até o agarrão sobre o rosto do jogador (`eye` fixa: posição dos olhos)."""
    def apply(stage, f):
        stage.entity.pose_for_death(stage.resolve(eye), amount_start + (amount_end - amount_start) * f)
    return apply


def curve_value(curve, setter):
    """Trilha genérica: `setter(stage, valor)` com `curve(t_local)`; `f` vira o tempo da curva (0..duração da curva)."""
    curve = as_curve(curve)
    span = curve.times[-1]

    def apply(stage, f):
        setter(stage, curve(f * span))
    return apply
