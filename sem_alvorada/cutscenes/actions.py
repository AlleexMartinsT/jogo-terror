"""Fábricas de ações (`Cue`) e de trilhas contínuas (`Track.apply`) usadas pelos roteiros.

Convenção: ações que MUDAM O ESTADO DO JOGO (energia, porta, posição do jogador, entidade, cérebro)
são `essential=True`: se o jogador pular a cutscene, elas rodam mesmo assim. Som, luz cosmética e
câmera não são essenciais.
"""
import math

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


def cut_light(name, energy):
    """Liga (energia > 0) ou apaga uma luz `CutLight_*`."""
    return Action(lambda st: st.set_light(name, energy))


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
# Jogador, portas e cérebro
# --------------------------------------------------------------------------
def place_player(x, y, z, yaw):
    """Reposiciona o jogador. Cada argumento pode ser número ou função `stage -> número`."""
    def run(stage):
        stage.safe("place_player", stage.host.place_player, *(stage.resolve(v) for v in (x, y, z, yaw)))
    return Action(run, essential=True)


def activate_brain():
    return Action(lambda st: st.safe("entity_brain_activate", st.host.entity_brain_activate), essential=True)


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


# --------------------------------------------------------------------------
# Trilhas contínuas: recebem (stage, f) com f de 0 a 1
# --------------------------------------------------------------------------
def _lerp3(a, b, f):
    return tuple(x + (y - x) * f for x, y in zip(a, b))


def door_openness(door_id, start=0.0, end=1.0):
    def apply(stage, f):
        stage.safe("doors.snap", stage.host.doors.snap, door_id, start + (end - start) * f)
    return apply


def move_object(name, start: Vec, end: Vec):
    """Move um objeto (se existir) e registra o deslocamento para câmeras que o acompanham."""
    def apply(stage, f):
        stage.moved[name] = tuple((e - s) * f for s, e in zip(start, end))
        obj = stage.obj(name)
        if obj is not None:
            obj.location = _lerp3(start, end, f)
    return apply


def lift_object(name, start_z, end_z):
    """Sobe/desce só o Z de um objeto (portão da garagem)."""
    def apply(stage, f):
        obj = stage.obj(name)
        if obj is not None:
            obj.location.z = start_z + (end_z - start_z) * f
    return apply


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
