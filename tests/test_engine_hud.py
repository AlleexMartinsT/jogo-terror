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

from sem_alvorada import layout, story  # noqa: E402
from sem_alvorada.engine import hud, screens, texts  # noqa: E402
from sem_alvorada.engine.canvas import Canvas, load_hud_font  # noqa: E402
from tools import pngwrite  # noqa: E402

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
    game, brain, rig, cutscenes = game_with_fake_entity(hunts=False, debug=True)
    start_playing(game)
    st = game.state
    st.has_flashlight, st.flashlight_on, st.battery, st.spare_batteries = True, True, 0.32, 2
    st.has_key, st.batteries_found = True, 1
    game.save_checkpoint()
    return game


def busy_scene(game):
    """Um instante de ação: passos altos, ambiente da cozinha, uma dica de interação e uma mensagem."""
    teleport(game, 10.0, 6.5, 0.0, 0)
    walk(game, 1.2, run=True)
    game.say(story.PICKED["KEY"])
    run_for(game, 0.4)
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
    for expected in ("VOCÊ", "AMBIENTE", "ENTIDADE", texts.HUD_OBJECTIVE, texts.HUD_FLASHLIGHT, story.LABEL_KEY):
        assert expected in play, expected
    assert any(story.LABEL_BATTERIES in line and "1/3" in line for line in play)
    assert story.TITLE in "".join(seen["title"]) and story.CONTROLS[0][0] in seen["title"]
    assert texts.PAUSE_TITLE in seen["paused"] and story.NOTES["NOTE_1"][0] in seen["reading"]
    assert story.DEATH_RETRY in seen["dead"] and any(story.ENDING_CARD[0] in t for t in seen["credits"])
    assert "legenda" in seen["cutscene"]


def test_noise_meter_geometry_tracks_levels_and_threshold():
    model = {"labels": {"player": "VOCÊ", "ambient": "AMBIENTE", "entity": "ENTIDADE"},
             "levels": {"player": 0.5, "ambient": 0.1, "entity": 0.0},
             "peaks": {"player": 0.7, "ambient": 0.1, "entity": 0.0}, "hear_threshold": 0.08}
    canvas = Canvas(WIDTH, HEIGHT)
    hud.draw_noise_meter(canvas, model)
    u = canvas.scale
    fills = [r for r in rects_of(canvas) if abs(r[4] - hud.METER_BAR_H * u) < 1e-6]
    widths = sorted({round(r[3], 3) for r in fills})
    assert round(hud.METER_BAR_W * u * hud.display_level(0.5), 3) in widths
    assert round(hud.METER_BAR_W * u * hud.display_level(0.1), 3) in widths
    ticks = [r for r in rects_of(canvas) if abs(r[3] - 1.5 * u) < 1e-6 and r[4] > hud.METER_BAR_H * u]
    assert ticks, "sem marcador do limiar de audição"
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
    lines = screens.wrap_text(canvas, story.LOCKED_MSGS["garage"] + " " + texts.MSG_GARAGE_NEEDS.format(
        missing="Chave do carro, Mapa da cidade"), 16, WIDTH * 0.6)
    assert len(lines) >= 2 and all(canvas.text_width(line, 16) <= WIDTH * 0.6 + 1 for line in lines)


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
