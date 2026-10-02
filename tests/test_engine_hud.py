"""Testes do HUD e das telas sem GPU: lógica de desenho sobre o Canvas gravador e renderização
CPU (numpy + blf em ImBuf) para conferir o visual em PNG (out/engine/hud_*.png).

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_engine_hud.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import test_engine_fakes as fk  # noqa: E402
from test_engine_fakes import InputState, game_with_fake_entity, run_for, start_playing, step, teleport, walk  # noqa: E402

import blf  # noqa: E402
import bpy  # noqa: E402
import imbuf  # noqa: E402

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout, story  # noqa: E402
from sem_alvorada.engine import hud, inventory, screens, texts  # noqa: E402
from sem_alvorada.engine.canvas import Canvas, load_hud_font  # noqa: E402
from tools import pngwrite  # noqa: E402
from tools.rasterpoly import blend_polygon  # noqa: E402

OUT = os.path.join(fk.ROOT, "out", "engine")
WIDTH, HEIGHT = 1280, 720


class RasterCanvas(Canvas):
    """Renderiza as operações gravadas numa imagem numpy: retângulos por mistura alfa, textos via blf/ImBuf."""

    def __init__(self, width, height):
        super().__init__(width, height)
        self.font_id = load_hud_font()

    def text_width(self, string, size):
        blf.size(self.font_id, size)
        return blf.dimensions(self.font_id, string)[0]

    def render(self, background):
        frame = background.astype(np.float32).copy()
        run = []
        for op in self.ops:
            if op[0] == "text":
                run.append(op)
                continue
            self._blit_texts(frame, run)
            run = []
            if op[0] == "poly":
                blend_polygon(frame, list(op[1]), op[2])
            else:
                self._blend_rect(frame, op)
        self._blit_texts(frame, run)
        return frame

    def _blend_rect(self, frame, op):
        _kind, x, y, w, h, color = op
        x0, x1 = max(0, int(round(x))), min(self.width, int(round(x + w)))
        y0, y1 = max(0, int(round(y))), min(self.height, int(round(y + h)))
        if x1 <= x0 or y1 <= y0:
            return
        alpha = color[3]
        region = frame[y0:y1, x0:x1]
        region[:] = region * (1.0 - alpha) + np.array(color[:3], np.float32) * alpha

    def _blit_texts(self, frame, texts_run):
        if not texts_run:
            return
        layer = imbuf.new((self.width, self.height))
        with blf.bind_imbuf(self.font_id, layer):
            for _kind, x, y, string, size, color in texts_run:
                blf.size(self.font_id, size)
                blf.color(self.font_id, *color)
                blf.position(self.font_id, x, y, 0)
                blf.draw_buffer(self.font_id, string)
        path = os.path.join(OUT, "_text_layer.png")
        imbuf.write(layer, filepath=path)
        image = bpy.data.images.load(path)
        pixels = np.empty(self.width * self.height * 4, np.float32)
        image.pixels.foreach_get(pixels)
        bpy.data.images.remove(image)
        pixels = pixels.reshape(self.height, self.width, 4)
        alpha = pixels[..., 3:4]
        frame[:] = frame * (1.0 - alpha) + pixels[..., :3] * alpha


def gradient_backdrop():
    """Fundo que lembra uma cena escura: degradê frio com uma mancha de luz, para avaliar a legibilidade."""
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    glow = np.exp(-(((x - WIDTH * 0.55) / 260) ** 2 + ((y - HEIGHT * 0.45) / 180) ** 2))
    base = np.stack([0.05 + 0.32 * glow, 0.055 + 0.30 * glow, 0.06 + 0.24 * glow], axis=-1)
    return base


def save(frame, name):
    os.makedirs(OUT, exist_ok=True)
    image = (np.clip(np.flipud(frame), 0, 1) * 255).astype(np.uint8)
    path = os.path.join(OUT, f"hud_{name}.png")
    pngwrite.write_png(path, image)
    return path


def draw_model(model, background=None):
    canvas = RasterCanvas(WIDTH, HEIGHT)
    screens.draw_frame(canvas, model)
    return canvas, canvas.render(gradient_backdrop() if background is None else background)


def texts_of(canvas):
    return [op[3] for op in canvas.ops if op[0] == "text"]


def rects_of(canvas):
    return [op for op in canvas.ops if op[0] == "rect"]


def playing_game():
    """Partida no quarto com lanterna, chave e duas pilhas; a bateria já saiu da tela e o medidor dormiu."""
    game, brain, rig, cutscenes = game_with_fake_entity(hunts=False, debug=True)
    start_playing(game)
    st = game.state
    st.has_flashlight, st.flashlight_on, st.battery, st.spare_batteries = True, True, 0.62, 2
    st.has_key, st.batteries_found = True, 1
    game.save_checkpoint()
    game.message_text, game._message_left = "", 0.0
    run_for(game, hud_model_idle_seconds())
    return game


def hud_model_idle_seconds():
    """Tempo suficiente para a bateria sair da tela e o medidor voltar a dormir."""
    from sem_alvorada.engine import hudmodel
    return max(hudmodel.BATTERY_SHOW_SECONDS, hudmodel.METER_HOLD_SECONDS + hudmodel.METER_FADE_SECONDS) + 1.0


def busy_scene(game):
    """Um instante de ação: passos altos, ambiente da cozinha, a bateria acabada de ligar e uma fala."""
    teleport(game, 10.0, 6.5, 0.0, 0)
    walk(game, 1.2, run=True)
    game.say(story.PICKED["KEY"])
    step(game, InputState(flashlight=True))
    run_for(game, 0.2)
    return game


def test_hud_draws_every_phase_and_expected_texts():
    game = playing_game()
    busy_scene(game)
    seen = {}
    for phase in ("title", "cutscene", "play", "reading", "paused", "dead", "credits"):
        game.phase = phase
        game.reader_note = "NOTE_1" if phase == "reading" else None
        if phase == "cutscene":
            game.cutscenes.play("intro")
        canvas = RasterCanvas(WIDTH, HEIGHT)
        screens.draw_frame(canvas, game.hud_model())
        assert canvas.ops, phase
        seen[phase] = texts_of(canvas)
    play = seen["play"]
    for expected in ("VOCÊ", texts.HUD_FLASHLIGHT):
        assert expected in play, expected
    gone = {texts.METER_LABELS["ambient"], texts.PAUSE_OBJECTIVE, texts.PAUSE_COLLECT, story.LABEL_KEY,
            story.LABEL_BATTERIES, story.OBJ_TAKE_FLASHLIGHT}
    assert not gone & set(play), "o HUD de jogo não traz objetivo, coleta nem ambiente"
    assert not any("PILHAS" in line.upper() and "x" in line for line in play), "sem contagem de pilhas no canto"
    paused = seen["paused"]
    assert texts.PAUSE_TITLE in paused and texts.PAUSE_OBJECTIVE in paused and game.state.objective in " ".join(paused)
    for expected in (texts.METER_LABELS["ambient"], texts.METER_LABELS["entity"], story.LABEL_KEY, story.LABEL_MAP,
                     "Q / Tab"):
        assert expected in paused, expected
    assert any(story.LABEL_BATTERIES in line and "1/3" in line for line in paused)
    assert story.TITLE in "".join(seen["title"]) and story.CONTROLS[0][0] in seen["title"]
    assert story.NOTES["NOTE_1"][0] in seen["reading"]
    assert story.DEATH_RETRY in seen["dead"] and any(story.ENDING_CARD[0] in t for t in seen["credits"])
    assert "legenda" in seen["cutscene"]


def test_noise_meter_geometry_tracks_levels_and_threshold():
    model = {"labels": {"player": "VOCÊ", "ambient": "AMBIENTE", "entity": "ENTIDADE"},
             "levels": {"player": 0.5, "ambient": 0.1, "entity": 0.3},
             "peaks": {"player": 0.7, "ambient": 0.1, "entity": 0.3}, "hear_threshold": 0.08,
             "alpha": 1.0, "entity_audible": True}
    canvas = Canvas(WIDTH, HEIGHT)
    hud.draw_noise_meter(canvas, model)
    u = canvas.scale
    fills = [r for r in rects_of(canvas) if abs(r[4] - hud.METER_BAR_H * u) < 1e-6]
    widths = sorted({round(r[3], 3) for r in fills})
    assert round(hud.METER_BAR_W * u * hud.display_level(0.5), 3) in widths
    assert round(hud.METER_BAR_W * u * hud.display_level(0.3), 3) in widths, "ENTIDADE audível ganha a sua barra"
    assert round(hud.METER_BAR_W * u * hud.display_level(0.1), 3) not in widths, "AMBIENTE fica para a pausa"
    assert texts_of(canvas) == ["VOCÊ", "ENTIDADE"], texts_of(canvas)
    ticks = [r for r in rects_of(canvas) if abs(r[3] - 1.5 * u) < 1e-6 and r[4] > hud.METER_BAR_H * u]
    assert ticks, "sem marcador do limiar de audição"
    model["entity_audible"] = False
    silent = Canvas(WIDTH, HEIGHT)
    hud.draw_noise_meter(silent, model)
    assert texts_of(silent) == ["VOCÊ"], "ENTIDADE só aparece enquanto é audível"
    assert hud.display_level(0.08) > 0.2 and hud.display_level(1.0) == 1.0 and hud.display_level(0.0) == 0.0
    audible = Canvas(WIDTH, HEIGHT)
    model["levels"]["player"] = 0.02
    hud.draw_noise_meter(audible, model)
    assert not any(r[5] == hud.WARNING and abs(r[4] - hud.METER_BAR_H * u) < 1e-6 for r in rects_of(audible)
                   if r[3] > 1.6 * u), "barra deveria ficar neutra abaixo do limiar"


def test_scale_follows_window_height():
    for height in (480, 720, 1440):
        canvas = Canvas(int(height * 16 / 9), height)
        screens.draw_frame(canvas, playing_game().hud_model())
        for op in canvas.ops:
            if op[0] == "rect":
                assert op[1] >= -1 and op[2] >= -1 and op[1] + op[3] <= canvas.width + 1, (height, op)


def test_long_texts_wrap_inside_the_screen():
    canvas = Canvas(WIDTH, HEIGHT)
    lines = screens.wrap_text(canvas, story.OBJ_COLLECT + " " + story.PICKED["KEY"], 16, WIDTH * 0.3)
    assert len(lines) >= 2 and all(canvas.text_width(line, 16) <= WIDTH * 0.3 + 1 for line in lines)


def test_idle_gameplay_hud_is_just_the_crosshair_and_a_faint_meter():
    game = playing_game()
    model = game.hud_model()
    model["debug"] = None
    canvas = Canvas(WIDTH, HEIGHT)
    screens.draw_frame(canvas, model)
    assert texts_of(canvas) == ["VOCÊ"], texts_of(canvas)
    alphas = [op[5][3] for op in canvas.ops if op[0] == "rect"]
    assert max(alphas) < 0.3, "em silêncio o medidor fica quase transparente"
    assert any(op[0] == "poly" for op in canvas.ops), "a mira é um ponto"


def test_battery_appears_after_a_gesture_and_stays_below_a_quarter():
    game = playing_game()
    assert game.hud_model()["battery"]["alpha"] == 0.0
    step(game, InputState(flashlight=True))                       # desliga
    assert game.hud_model()["battery"]["alpha"] == 1.0
    canvas = Canvas(WIDTH, HEIGHT)
    screens.draw_frame(canvas, game.hud_model())
    assert texts.HUD_FLASHLIGHT in texts_of(canvas)
    run_for(game, 6.0)
    assert game.hud_model()["battery"]["alpha"] == 0.0, "a bateria sai da tela sozinha"
    step(game, InputState(reload=True))                           # só tentar trocar já mostra a bateria
    assert game.hud_model()["battery"]["alpha"] > 0.0
    run_for(game, 6.0)
    game.state.battery = 0.2
    run_for(game, 0.5)
    assert game.hud_model()["battery"]["alpha"] == 1.0, "abaixo de 25% a bateria fica sempre à vista"
    game.state.battery = 0.0
    game.state.flashlight_on = False
    canvas = Canvas(WIDTH, HEIGHT)
    screens.draw_frame(canvas, game.hud_model())
    assert texts.HUD_NO_CHARGE in texts_of(canvas) and texts.HUD_SWAP_HINT in texts_of(canvas)
    game.state.spare_batteries = 0
    canvas = Canvas(WIDTH, HEIGHT)
    screens.draw_frame(canvas, game.hud_model())
    assert texts.HUD_NO_CHARGE in texts_of(canvas) and texts.HUD_SWAP_HINT not in texts_of(canvas)


def test_stamina_only_shows_when_running_out():
    game = playing_game()
    assert game.hud_model()["stamina_alpha"] == 0.0
    game.player.stamina = 0.6
    assert game.hud_model()["stamina_alpha"] == 0.0
    game.player.stamina = 0.35
    assert 0.0 < game.hud_model()["stamina_alpha"] < 1.0
    game.player.stamina = 0.1
    assert game.hud_model()["stamina_alpha"] == 1.0
    canvas = Canvas(WIDTH, HEIGHT)
    screens.draw_frame(canvas, game.hud_model())
    assert texts.HUD_STAMINA in texts_of(canvas)


def test_meter_wakes_with_noise_then_sleeps_and_shows_the_entity_when_audible():
    game = playing_game()
    quiet = game.hud_model()["noise"]["alpha"]
    teleport(game, 10.0, 6.5, 0.0, 0)
    walk(game, 1.0, run=True)
    loud = game.hud_model()["noise"]
    assert loud["alpha"] > 0.9 and quiet < 0.25 and loud["levels"]["player"] >= loud["hear_threshold"]
    run_for(game, 12.0)                 # o ruído do jogador leva ~8 s para decair abaixo do que acorda o medidor
    assert game.hud_model()["noise"]["alpha"] < 0.25, "o medidor volta a dormir em silêncio"
    px, py, pz = game.player.feet
    game.noise.emit("entity", "step_chase", (px + 1.5, py, pz), 0.9)
    run_for(game, 0.3)
    noise = game.hud_model()["noise"]
    assert noise["entity_audible"] and noise["alpha"] > 0.5
    canvas = Canvas(WIDTH, HEIGHT)
    model = game.hud_model()
    model["debug"] = None
    screens.draw_frame(canvas, model)
    assert texts_of(canvas) == ["VOCÊ", "ENTIDADE"], texts_of(canvas)


def test_interaction_prompt_marks_blocked_states():
    game = playing_game()
    model = game.hud_model()
    model["prompt"], model["prompt_blocked"] = story.PROMPT_LOCKED["front"], True
    blocked = Canvas(WIDTH, HEIGHT)
    hud.draw_crosshair(blocked, model)
    assert story.PROMPT_LOCKED["front"] in texts_of(blocked)
    assert any(op[0] == "rect" and op[5][:3] == hud.WARNING[:3] for op in blocked.ops)
    model["prompt"], model["prompt_blocked"] = story.PROMPT_OPEN, False
    normal = Canvas(WIDTH, HEIGHT)
    hud.draw_crosshair(normal, model)
    assert texts_of(normal) == [story.PROMPT_OPEN]
    assert not any(op[0] == "rect" and op[5][:3] == hud.WARNING[:3] for op in normal.ops)


def tile_plates(canvas):
    """Os cinco retângulos cheios dos setores da roda (os contornos têm lado menor que o setor)."""
    size = hud.WHEEL_TILE * canvas.scale
    return [op for op in rects_of(canvas) if abs(op[3] - size) < 1e-6 and abs(op[4] - size) < 1e-6]


def wheel_inputs(dx=0.0, dy=0.0, held=True):
    return InputState(wheel_held=held, wheel_dx=dx, wheel_dy=dy)


def test_wheel_draws_five_tiles_with_names_counts_and_the_selected_one_lighter():
    game = playing_game()
    st = game.state
    st.has_map = True
    st.notes_read.add("NOTE_1")
    game.hands.held = C.ITEM_FLASHLIGHT
    step(game, wheel_inputs(0.0, 0.0))
    step(game, wheel_inputs(0.18, 0.0))                           # mouse à direita: segundo setor depois do topo = chave
    wheel = game.hud_model()["wheel"]
    assert wheel["open"] and [s["kind"] for s in wheel["slots"]] == list(inventory.SLOTS)
    selected = [s["kind"] for s in wheel["slots"] if s["selected"]]
    assert selected == [C.ITEM_BATTERY], selected                  # 90 graus a partir do topo cai no setor das pilhas
    assert wheel["name"] == texts.WHEEL_LABELS[C.ITEM_BATTERY] and wheel["caption"] == texts.WHEEL_TAKE
    assert [s["count"] for s in wheel["slots"]] == [None, 2, None, None, None]
    assert [s["kind"] for s in wheel["slots"] if s["held"]] == [C.ITEM_FLASHLIGHT]
    canvas = Canvas(WIDTH, HEIGHT)
    screens.draw_frame(canvas, game.hud_model())
    drawn = texts_of(canvas)
    assert texts.WHEEL_LABELS[C.ITEM_BATTERY] in drawn and "x2" in drawn
    plates = tile_plates(canvas)
    assert len(plates) == 5
    brightest = max(plates, key=lambda op: op[5][3] * sum(op[5][:3]))
    battery_center = hud.wheel_center(WIDTH / 2, HEIGHT / 2, 1, 5, hud.WHEEL_RADIUS * canvas.scale)
    assert abs(brightest[1] + brightest[3] / 2 - battery_center[0]) < 1e-6, "o setor escolhido é o mais claro"
    step(game, wheel_inputs(held=False))
    assert not game.hud_model()["wheel"]["open"] and game.hands.held == C.ITEM_BATTERY


def test_wheel_marks_unavailable_sectors_dim_and_hides_the_crosshair():
    game = playing_game()
    step(game, wheel_inputs())
    model = game.hud_model()
    owned = [s["kind"] for s in model["wheel"]["slots"] if s["owned"]]
    assert owned == [C.ITEM_FLASHLIGHT, C.ITEM_BATTERY, C.ITEM_KEY]
    canvas = Canvas(WIDTH, HEIGHT)
    screens.draw_frame(canvas, model)
    alphas = [round(op[5][3], 2) for op in tile_plates(canvas)]
    assert alphas.count(0.3) == 2, "mapa e anotações ainda não existem: setores apagados"
    step(game, wheel_inputs(0.0, 0.0))
    crosshair = Canvas(WIDTH, HEIGHT)
    hud.draw_crosshair(crosshair, model)
    assert len(crosshair.ops) >= 1
    shown = Canvas(WIDTH, HEIGHT)
    hud.draw_gameplay(shown, model)
    cx, cy = WIDTH / 2, HEIGHT / 2
    assert not [op for op in shown.ops if op[0] == "poly" and abs(sum(p[0] for p in op[1]) / len(op[1]) - cx) < 0.01
                and abs(sum(p[1] for p in op[1]) / len(op[1]) - cy) < 0.01 and len(op[1]) == 12], "mira escondida com a roda"


def test_respawn_clears_the_screen_instead_of_speaking():
    game, brain, rig, cutscenes = game_with_fake_entity(hunts=False)
    start_playing(game)
    game.state.has_flashlight = True
    game.save_checkpoint()
    game.phase = "dead"
    step(game)
    step(game, InputState(confirm=True))
    assert game.phase == "play" and game.hud_model()["fade_in"] > 0.9
    canvas = Canvas(WIDTH, HEIGHT)
    screens.draw_frame(canvas, game.hud_model())
    assert any(op[0] == "rect" and op[3] == WIDTH and op[5][3] > 0.8 for op in canvas.ops)
    run_for(game, 2.0)
    assert game.hud_model()["fade_in"] == 0.0


def test_canvas_poly_line_disc_and_ring_stay_inside_their_bounds():
    canvas = Canvas(200, 100)
    canvas.disc(50, 50, 10, hud.PAPER)
    canvas.ring(120, 50, 20, 4, hud.PAPER)
    canvas.line(10, 10, 60, 10, 4, hud.PAPER)
    canvas.poly([(0, 0), (10, 0)], hud.PAPER)                     # menos de três pontos: ignorado
    kinds = [op[0] for op in canvas.ops]
    assert kinds.count("poly") == 1 + 56 + 1 and len(kinds) == 58
    xs = [p[0] for op in canvas.ops[1:57] for p in op[1]]
    assert abs(min(xs) - 100) < 1e-6 and abs(max(xs) - 140) < 1e-6
    line = canvas.ops[-1][1]
    assert abs(max(p[1] for p in line) - 12) < 1e-6 and abs(min(p[1] for p in line) - 8) < 1e-6
    frame = np.zeros((100, 200, 3), np.float32)
    raster = RasterCanvas(200, 100)
    raster.ops = canvas.ops
    painted = raster.render(frame)
    assert painted[50, 50].min() > 0.5 and painted[50, 120].max() == 0.0 and painted[50, 101].min() > 0.5


def test_render_screenshots():
    os.makedirs(OUT, exist_ok=True)
    game = playing_game()
    busy_scene(game)
    game.interact.current = game.interact.targets[0]
    frames = {}
    for phase in ("play", "title", "paused", "dead", "credits"):
        game.phase = phase
        frames[phase] = save(draw_model(game.hud_model())[1], phase)
    game.phase = "reading"
    game.reader_note = "NOTE_3"
    frames["reading"] = save(draw_model(game.hud_model())[1], "reading")
    game.phase, game.reader_note = "play", None
    game.state.has_map = True
    game.state.notes_read.add("NOTE_1")
    game.hands.held = C.ITEM_BATTERY
    step(game, wheel_inputs())
    for name, (dx, dy) in {"wheel_pilhas": (0.2, 0.05), "wheel_chave": (0.1, -0.2)}.items():
        step(game, wheel_inputs(dx, dy))
        frames[name] = save(draw_model(game.hud_model())[1], name)
    step(game, wheel_inputs(held=False))
    game.phase = "cutscene"
    game.cutscenes.play("intro")
    model = game.hud_model()
    model["overlay"].update(letterbox=1.0, subtitle="Ele está parado lá no fim do corredor. Não se mexe.",
                            subtitle_alpha=1.0, fade=0.0)
    frames["cutscene"] = save(draw_model(model)[1], "cutscene")
    model["overlay"].update(letterbox=0.0, subtitle="", card=story.ENDING_CARD, fade=1.0)
    frames["card"] = save(draw_model(model)[1], "card")
    model["overlay"].update(card=None, fade=0.0, flash=0.6)
    frames["flash"] = save(draw_model(model)[1], "flash")
    for path in frames.values():
        assert os.path.getsize(path) > 2000, path
    print("capturas:", ", ".join(sorted(os.path.basename(p) for p in frames.values())))


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok      {name}", flush=True)
        except Exception as error:      # noqa: BLE001
            import traceback
            failures += 1
            print(f"FALHOU  {name}: {error!r}", flush=True)
            traceback.print_exc()
    print(f"{len(tests) - failures}/{len(tests)} testes de HUD passaram")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
