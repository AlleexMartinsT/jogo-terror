"""Monta o dicionário que o HUD e as telas desenham. Não toca GPU nem bpy: dá para testar direto."""
from .. import conventions as C
from .. import story
from . import texts
from .fallbacks import HEAR_THRESHOLD

OVERLAY_FIELDS = ("fade", "letterbox", "subtitle", "subtitle_alpha", "card", "flash", "shake")
OVERLAY_IDLE = {"fade": 0.0, "letterbox": 0.0, "subtitle": "", "subtitle_alpha": 0.0,
                "card": None, "flash": 0.0, "shake": 0.0}


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


def _battery_block(game):
    state = game.state
    return {"has": state.has_flashlight, "level": state.battery, "on": state.flashlight_on,
            "spare": state.spare_batteries, "low": state.battery < C.BATTERY_LOW,
            "critical": state.battery < C.BATTERY_CRITICAL, "swapping": game.flashlight.swap_left > 0}


def _noise_block(game):
    levels = game.noise_levels()
    return {"levels": levels, "peaks": dict(game.meter.values), "hear_threshold": hear_threshold(),
            "labels": dict(texts.METER_LABELS)}


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
    prompt = game.interact.current
    return {
        "phase": game.phase,
        "time": game.clock,
        "battery": _battery_block(game),
        "collect": state.collect_status(),
        "objective": state.objective,
        "prompt": game.interact.prompt_for(prompt) if prompt is not None else None,
        "message": game.message_text,
        "message_alpha": game.message_alpha,
        "noise": _noise_block(game),
        "stamina": player.stamina,
        "exhausted": player.exhausted,
        "crouching": player.crouching,
        "overlay": overlay_dict(game.cutscenes),
        "note": _note_block(game),
        "title": {"name": story.TITLE, "subtitle": story.SUBTITLE, "controls": story.CONTROLS,
                  "tip": game.title_tip},
        "death": {"card": story.DEATH_CARD, "retry": story.DEATH_RETRY, "deaths": state.deaths},
        "ending": {"card": story.ENDING_CARD, "credits": texts.CREDITS_LINES},
        "debug": _debug_line(game) if game.debug else None,
        "error": game.error_text,
    }
