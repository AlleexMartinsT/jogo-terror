"""Monta o dicionário que o HUD e as telas desenham. Não toca GPU nem bpy: dá para testar direto."""
from .. import conventions as C
from .. import story
from . import texts
from .fallbacks import HEAR_THRESHOLD
from .inventory import SLOTS

OVERLAY_FIELDS = ("fade", "letterbox", "subtitle", "subtitle_alpha", "card", "flash", "shake")
OVERLAY_IDLE = {"fade": 0.0, "letterbox": 0.0, "subtitle": "", "subtitle_alpha": 0.0,
                "card": None, "flash": 0.0, "shake": 0.0}

BATTERY_SHOW_SECONDS = 3.5      # quanto a bateria fica na tela depois de ligar, desligar, trocar ou tentar trocar
BATTERY_FADE_OUT = 0.8
METER_QUIET_ALPHA = 0.18        # opacidade do medidor quando tudo está em silêncio
METER_HOLD_SECONDS = 1.6        # depois do último barulho ele continua visível por este tempo, e então apaga
METER_FADE_SECONDS = 1.0
PLAYER_NOISE_NOTICEABLE = 0.03  # nível do jogador a partir do qual o medidor acorda
ENTITY_AUDIBLE = 0.04           # nível da entidade a partir do qual o jogador a escuta
STAMINA_FADE_START = 0.45       # o fôlego aparece quando cai abaixo disto e fica pleno abaixo de STAMINA_FULL
STAMINA_FULL = 0.25
RESPAWN_FADE_SECONDS = 1.4      # a tela clareia depois que o jogador volta ao último lugar seguro


def hear_threshold():
    try:
        from ..audio import noise
        return float(getattr(noise, "HEAR_THRESHOLD", HEAR_THRESHOLD))
    except ImportError:
        return HEAR_THRESHOLD


def overlay_dict(cutscenes):
    """Converte o Overlay do CutscenePlayer em dict (campos ausentes ficam neutros)."""
    if cutscenes is None or not cutscenes.active:
        return dict(OVERLAY_IDLE)
    overlay = cutscenes.overlay()
    return {name: getattr(overlay, name, OVERLAY_IDLE[name]) for name in OVERLAY_FIELDS}


class HudFades:
    """O que o HUD mostra só por um tempo: a bateria depois de um gesto com a lanterna, o medidor depois de
    barulho e o clareamento depois de voltar de uma morte. Observa o jogo uma vez por quadro (`observe`)."""

    def __init__(self):
        self._phase = None          # última fase vista; o reset não a apaga: o retry reinicia o mundo ainda como "dead"
        self.reset()

    def reset(self):
        self.battery_left = 0.0
        self.meter_hold = 0.0
        self.meter_alpha = METER_QUIET_ALPHA
        self.respawn_left = 0.0
        self._flashlight_on = None          # None até o primeiro quadro: o estado inicial não é um gesto
        self._swapping = False

    def observe(self, game, dt, inp):
        self._observe_battery(game, dt, inp)
        self._observe_meter(game, dt)
        self._observe_respawn(game.phase, dt)

    def _observe_battery(self, game, dt, inp):
        state = game.state
        swapping = getattr(game.flashlight, "swap_left", 0.0) > 0
        toggled = self._flashlight_on is not None and state.flashlight_on != self._flashlight_on
        gesture = game.phase == "play" and (inp.flashlight or inp.reload)
        if state.has_flashlight and (gesture or toggled or (swapping and not self._swapping)):
            self.battery_left = BATTERY_SHOW_SECONDS
        else:
            self.battery_left = max(0.0, self.battery_left - dt)
        self._flashlight_on, self._swapping = state.flashlight_on, swapping

    def _observe_meter(self, game, dt):
        levels = game.noise_levels()
        awake = levels["player"] >= PLAYER_NOISE_NOTICEABLE or levels["entity"] >= ENTITY_AUDIBLE
        self.meter_hold = METER_HOLD_SECONDS if awake else max(0.0, self.meter_hold - dt)
        target = METER_QUIET_ALPHA + (1.0 - METER_QUIET_ALPHA) * min(1.0, self.meter_hold / METER_FADE_SECONDS)
        rate = 10.0 if target > self.meter_alpha else 1.5          # acorda depressa, adormece devagar
        self.meter_alpha += (target - self.meter_alpha) * min(1.0, rate * dt)

    def _observe_respawn(self, phase, dt):
        if self._phase == "dead" and phase == "play":
            self.respawn_left = RESPAWN_FADE_SECONDS
        else:
            self.respawn_left = max(0.0, self.respawn_left - dt)
        self._phase = phase

    # ---- consultas do modelo ----
    def battery_alpha(self, low):
        """Abaixo de BATTERY_LOW a bateria fica sempre na tela; fora disso, só logo depois de um gesto."""
        if low:
            return 1.0
        if self.battery_left <= 0:
            return 0.0
        return min(1.0, self.battery_left / BATTERY_FADE_OUT)

    @property
    def fade_in(self):
        return self.respawn_left / RESPAWN_FADE_SECONDS


def stamina_alpha(stamina, exhausted):
    """O fôlego só aparece quando está acabando; cansado de vez, fica pleno."""
    if exhausted:
        return 1.0
    return max(0.0, min(1.0, (STAMINA_FADE_START - stamina) / (STAMINA_FADE_START - STAMINA_FULL)))


def _battery_block(game):
    state = game.state
    low = state.battery < C.BATTERY_LOW
    return {"has": state.has_flashlight, "level": state.battery, "on": state.flashlight_on,
            "spare": state.spare_batteries, "low": low, "critical": state.battery < C.BATTERY_CRITICAL,
            "swapping": getattr(game.flashlight, "swap_left", 0.0) > 0, "dead": state.battery <= 0,
            "can_swap": state.spare_batteries > 0, "alpha": game.hud_fades.battery_alpha(low)}


def _noise_block(game):
    levels = game.noise_levels()
    return {"levels": levels, "peaks": dict(game.meter.values), "hear_threshold": hear_threshold(),
            "labels": dict(texts.METER_LABELS), "alpha": game.hud_fades.meter_alpha,
            "entity_audible": levels["entity"] >= ENTITY_AUDIBLE}


def _wheel_block(game):
    block = game.inventory.hud_block()
    slots = [{"kind": kind, "label": texts.WHEEL_LABELS[kind], "owned": kind in block["owned"],
              "selected": kind == block["selection"], "held": kind == block["held"],
              "count": block["counts"][kind] if kind == C.ITEM_BATTERY else None, "fresh": kind in block["fresh"]}
             for kind in SLOTS]
    focus = block["selection"] or block["held"]
    caption = (texts.WHEEL_IN_HAND if focus == block["held"] else texts.WHEEL_TAKE) if focus else ""
    return {"open": block["open"], "slots": slots, "pointer": block["pointer"],
            "name": texts.WHEEL_LABELS[focus] if focus else "", "caption": caption}


def _note_block(game):
    if game.reader_note is None:
        return None
    title, body = story.NOTES[game.reader_note]
    return {"id": game.reader_note, "title": title, "body": body}


def _debug_line(game):
    player = game.player
    out = game.entity.output
    entity = f"{out.state} d={game.entity.distance_to(player.feet):.1f}" if out else "dormente"
    return (f"pos=({player.x:.1f},{player.y:.1f},{player.z:.1f}) sala={player.room_id} "
            f"fase={game.phase} ent={entity} luzes={game.lights.lit_count()} "
            f"col={game.collision.kind} fps={game.fps:.0f}")


def build_hud_model(game):
    """Tudo o que o HUD precisa para desenhar um quadro."""
    state = game.state
    player = game.player
    target = game.interact.current
    return {
        "phase": game.phase,
        "time": game.clock,
        "battery": _battery_block(game),
        "collect": state.collect_status(),
        "objective": state.objective,
        "prompt": game.interact.prompt_for(target) if target is not None else None,
        "prompt_blocked": target is not None and game.interact.is_blocked(target),
        "message": game.message_text,
        "message_alpha": game.message_alpha,
        "noise": _noise_block(game),
        "stamina": player.stamina,
        "stamina_alpha": stamina_alpha(player.stamina, player.exhausted),
        "exhausted": player.exhausted,
        "crouching": player.crouching,
        "wheel": _wheel_block(game),
        "fade_in": game.hud_fades.fade_in,
        "overlay": overlay_dict(game.cutscenes),
        "note": _note_block(game),
        "title": {"name": story.TITLE, "subtitle": story.SUBTITLE, "controls": story.CONTROLS,
                  "tip": game.title_tip},
        "death": {"card": story.DEATH_CARD, "retry": story.DEATH_RETRY, "deaths": state.deaths},
        "ending": {"card": story.ENDING_CARD, "credits": texts.CREDITS_LINES},
        "debug": _debug_line(game) if game.debug else None,
        "error": game.error_text,
    }
