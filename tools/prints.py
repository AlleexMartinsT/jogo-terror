"""Gera capturas do jogo como o jogador veria: câmera do jogador no EEVEE + HUD desenhado por cima.

    LIBGL_ALWAYS_SOFTWARE=1 python tools/prints.py <cenario> [--res 1280x720] [--samples 16]

Cenários: veja `SCENES` (cômodos no escuro com lanterna, notas e título). O exterior é quase preto no
jogo; para ele existe `tools/vista_estudio.py`.
O HUD é rasterizado na CPU pelo mesmo `Canvas` que o jogo desenha com `gpu`/`blf`, então o layout é o real.
Útil para ver o resultado sem abrir a GUI do Blender (ex.: em servidor sem tela).
"""
import argparse
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import bpy  # noqa: E402,I001  (precisa vir antes de blf e imbuf, que são carregados por ele)
import blf  # noqa: E402
import imbuf  # noqa: E402
import numpy as np  # noqa: E402

from sem_alvorada import BLEND_PATH, compat, layout  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada.engine import screens  # noqa: E402
from sem_alvorada.engine.canvas import Canvas, load_hud_font  # noqa: E402
from sem_alvorada.engine.state import FLAG_BLACKOUT  # noqa: E402
from sem_alvorada.engine.game import Game, InputState  # noqa: E402
from tools import pngwrite  # noqa: E402
from tools.rasterpoly import blend_polygon  # noqa: E402

OUT = os.path.join(ROOT, "out", "prints")


class RasterCanvas(Canvas):
    """Reproduz em numpy as operações que o HUD gravaria para a GPU (retângulos e polígonos com alfa, texto via ImBuf)."""

    def __init__(self, width, height):
        super().__init__(width, height)
        self.font_id = load_hud_font()

    def text_width(self, string, size):
        blf.size(self.font_id, size)
        return blf.dimensions(self.font_id, string)[0]

    def render(self, background):
        frame = background.astype(np.float32).copy()
        pending_text = []
        for op in self.ops:
            if op[0] == "text":
                pending_text.append(op)
                continue
            self._blit_texts(frame, pending_text)
            pending_text = []
            if op[0] == "poly":
                blend_polygon(frame, list(op[1]), op[2])
            else:
                self._blend_rect(frame, op)
        self._blit_texts(frame, pending_text)
        return frame

    def _blend_rect(self, frame, op):
        _kind, x, y, w, h, color = op
        x0, x1 = max(0, int(round(x))), min(self.width, int(round(x + w)))
        y0, y1 = max(0, int(round(y))), min(self.height, int(round(y + h)))
        if x1 > x0 and y1 > y0:
            alpha = color[3]
            region = frame[y0:y1, x0:x1]
            region[:] = region * (1.0 - alpha) + np.array(color[:3], np.float32) * alpha

    def _blit_texts(self, frame, text_ops):
        if not text_ops:
            return
        layer = imbuf.new((self.width, self.height))
        with blf.bind_imbuf(self.font_id, layer):
            for _kind, x, y, string, size, color in text_ops:
                blf.size(self.font_id, size)
                blf.color(self.font_id, *color)
                blf.position(self.font_id, x, y, 0)
                blf.draw_buffer(self.font_id, string)
        layer_path = os.path.join(OUT, "_text_layer.png")
        imbuf.write(layer, filepath=layer_path)
        image = bpy.data.images.load(layer_path)
        pixels = np.empty(self.width * self.height * 4, np.float32)
        image.pixels.foreach_get(pixels)
        bpy.data.images.remove(image)
        pixels = pixels.reshape(self.height, self.width, 4)
        frame[:] = frame * (1.0 - pixels[..., 3:4]) + pixels[..., :3] * pixels[..., 3:4]


# --------------------------------------------------------------------------
# Cenários: cada um devolve (x, y, z, yaw_graus, pitch_graus) e prepara o estado do jogo
# --------------------------------------------------------------------------
def look_at_yaw(x, y, target_x, target_y):
    return math.degrees(C.dir_yaw(target_x - x, target_y - y))


def equip(game, battery=0.62, spare=2, key=False, map_found=False, batteries_found=2, flashlight_on=True):
    state = game.state
    state.has_flashlight, state.flashlight_on = True, flashlight_on
    state.battery, state.spare_batteries = battery, spare
    state.has_key, state.has_map = key, map_found
    state.batteries_found = batteries_found
    state.collected |= {"FLASHLIGHT"}


def settle(game, seconds=0.5):
    for _ in range(int(seconds * 30)):
        game.tick(1 / 30, InputState())


def make_noise(game, player_level, entity_level):
    pos = (game.player.x, game.player.y, game.player.z)
    if player_level:
        game.noise.emit("player", "run" if player_level > 0.5 else "walk", pos, player_level)
    if entity_level:
        ex, ey, ez = layout.ENTITY_FIRST_SIGHT
        game.noise.emit("entity", "step_chase", (ex, ey, ez), entity_level)


def scene_quarto(game):
    game.lights.set_power(True)
    x, y = 4.4, 6.4
    return x, y, 2.8, look_at_yaw(x, y, 0.8, 7.0), -5


def scene_lanterna(game):
    """Perto do criado-mudo: a dica de interação pede para pegar a lanterna."""
    game.lights.set_power(True)
    x, y = 1.55, 5.7
    return x, y, 2.8, look_at_yaw(x, y, 0.4, 6.2), -38


def scene_corredor(game):
    equip(game, battery=0.62, spare=2, key=True, batteries_found=2)
    game.lights.set_power(False)
    make_noise(game, 0.30, 0.55)
    return 6.5, 4.4, 2.8, 0.0, -1


def scene_cozinha(game):
    equip(game, battery=0.48, spare=3, key=True, map_found=True, batteries_found=3)
    game.lights.set_power(False)
    make_noise(game, 0.08, 0.0)
    x, y = 10.3, 6.0
    return x, y, 0.0, look_at_yaw(x, y, 12.0, 5.85), -4


def scene_cozinha_ampla(game):
    equip(game, battery=0.70, spare=2, key=True, batteries_found=2)
    game.lights.set_power(False)
    make_noise(game, 0.08, 0.0)
    x, y = 8.6, 5.7
    return x, y, 0.0, look_at_yaw(x, y, 11.0, 9.3), -6


def scene_sala_tv(game):
    equip(game, battery=0.55, spare=1, flashlight_on=True, batteries_found=1)
    game.lights.set_power(False)
    make_noise(game, 0.0, 0.0)
    return 0.9, 3.9, 0.0, look_at_yaw(0.9, 3.9, 4.7, 3.9), -2


def scene_garagem(game):
    equip(game, battery=0.30, spare=1, key=True, map_found=True, batteries_found=3)
    game.lights.set_power(False)
    make_noise(game, 0.30, 0.18)
    x, y = 13.2, 5.9
    return x, y, 0.0, look_at_yaw(x, y, 15.5, 3.2), -6


def scene_escada(game):
    equip(game, battery=0.85, spare=0, batteries_found=0)
    game.lights.set_power(False)
    make_noise(game, 0.55, 0.0)
    return 6.7, 1.7, 0.0, 0.0, 14


def scene_nota(game):
    equip(game)
    game.lights.set_power(False)
    game.phase, game.reader_note = "reading", "NOTE_3"
    return 2.0, 4.6, 0.0, look_at_yaw(2.0, 4.6, 2.1, 4.6), -55


def scene_titulo(game):
    game.phase = "title"
    return 6.5, 2.0, 0.0, 0.0, 6


def hush(game):
    """Tira a fala de abertura da tela: os cenários de HUD mostram só o que o HUD mostra sozinho."""
    game.message_text, game._message_left = "", 0.0


def scene_hud_trancada(game):
    """HUD de jogo: mira com a dica "Trancada" (estado, não fala), bateria recém-ligada e a barra VOCÊ acordada."""
    equip(game, battery=0.74, spare=2, key=False, batteries_found=1)
    game.lights.set_power(False)
    make_noise(game, 0.30, 0.0)
    game.hud_fades.battery_left = 3.0
    hush(game)
    return 9.95, 5.85, 0.0, look_at_yaw(9.95, 5.85, 14.0, 5.85), -4


def scene_hud_silencio(game):
    """Tudo calmo: só a mira e uma barra de som quase transparente."""
    equip(game, battery=0.74, spare=2, key=True, batteries_found=2)
    game.lights.set_power(False)
    make_noise(game, 0.0, 0.0)
    hush(game)
    return 0.9, 3.9, 0.0, look_at_yaw(0.9, 3.9, 4.7, 3.9), -2


def scene_hud_perigo(game):
    """A entidade é audível, a bateria está abaixo de 25% e o fôlego acabando."""
    equip(game, battery=0.17, spare=1, key=True, batteries_found=2)
    game.lights.set_power(False)
    make_noise(game, 0.55, 0.6)
    game.player.stamina = 0.18
    hush(game)
    return 6.5, 4.4, 2.8, 0.0, -1


def scene_hud_sem_carga(game):
    """Lanterna sem carga e com pilha reserva: o aviso é visual, o jogador não fala."""
    equip(game, battery=0.0, spare=1, key=True, batteries_found=2, flashlight_on=False)
    game.lights.set_power(False)
    make_noise(game, 0.0, 0.0)
    hush(game)
    return 9.0, 6.0, 0.0, look_at_yaw(9.0, 6.0, 11.8, 8.8), -10


def scene_pausa(game):
    """Menu de pausa: objetivo, lista de coleta, medidor completo e controles."""
    equip(game, battery=0.62, spare=2, key=True, batteries_found=2)
    game.state.flags.add(FLAG_BLACKOUT)
    game.lights.set_power(False)
    make_noise(game, 0.30, 0.2)
    game.phase = "paused"
    return 10.3, 6.0, 0.0, look_at_yaw(10.3, 6.0, 12.0, 5.85), -4


def scene_roda(game):
    """A roda aberta com mapa, anotação, chave e pilhas; o mouse é movido por `open_wheel` depois do assentamento."""
    equip(game, battery=0.62, spare=2, key=True, map_found=True, batteries_found=2)
    game.state.notes_read.add("NOTE_1")
    game.lights.set_power(False)
    make_noise(game, 0.0, 0.0)
    hush(game)
    game.hands.held = C.ITEM_FLASHLIGHT
    return 10.3, 6.0, 0.0, look_at_yaw(10.3, 6.0, 12.0, 5.85), -4


# cenário -> movimento do mouse (rad acumulados, dx para a direita, dy para cima) com Q apertado
WHEEL_MOVES = {"roda_pilhas": (0.19, 0.06), "roda_mapa": (-0.12, -0.2)}


def open_wheel(game, movement):
    """Segura Q por alguns quadros e então move o mouse, como o jogador faria."""
    held = dict(wheel_held=True)
    for _ in range(3):
        game.tick(1 / 30, InputState(**held))
    dx, dy = movement
    for _ in range(4):
        game.tick(1 / 30, InputState(wheel_dx=dx / 4, wheel_dy=dy / 4, **held))


def lit(game, x, y, target, pitch, z=0.0, power=False, flashlight_on=True, **equipment):
    """Posição de câmera no escuro, com a lanterna acesa, olhando para `target` (x, y)."""
    equip(game, battery=0.7, spare=2, flashlight_on=flashlight_on, batteries_found=2, **equipment)
    game.lights.set_power(power)
    make_noise(game, 0.0, 0.0)
    return x, y, z, look_at_yaw(x, y, *target), pitch


UPPER = layout.LEVEL_Z[1]

# (x, y, alvo, pitch, z). Os do andar de cima somam UPPER ao z.
AMBIENTACAO = {
    "sala_sofa": ((0.9, 2.3), (2.5, 4.0), -12, 0.0),
    "sala_acesa": ((2.4, 1.2), (3.4, 4.2), -12, 0.0),
    "sala_relogio": ((2.4, 3.2), (3.6, 5.55), 4, 0.0),
    "sala_mesinha": ((1.6, 4.8), (3.05, 4.15), -28, 0.0),
    "escritorio_mesa": ((3.4, 7.6), (1.7, 9.4), -14, 0.0),
    "escritorio_cortica": ((1.6, 8.3), (0.1, 9.45), 0, 0.0),
    "hall_porta": ((6.4, 4.2), (6.9, 0.5), -2, 0.0),
    "hall_telefone": ((6.2, 6.4), (7.8, 4.9), -6, 0.0),
    "jantar_mesa": ((8.6, 4.3), (10.4, 2.5), -16, 0.0),
    "jantar_aparador": ((9.6, 3.9), (11.7, 1.4), -6, 0.0),
    "cozinha_fogao": ((9.0, 6.0), (11.8, 8.8), -10, 0.0),
    "garagem_portao": ((18.0, 1.8), (14.6, 0.1), 8, 0.0),
    "quarto_menina": ((4.4, 4.3), (1.2, 1.2), -12, UPPER),
    "quarto_casal": ((4.4, 5.8), (1.0, 8.4), -14, UPPER),
    "banheiro": ((8.6, 4.3), (11.0, 1.2), -10, UPPER),
    "escritorio_cima": ((8.6, 5.8), (11.2, 9.0), -10, UPPER),
    "casal_cama": ((3.3, 6.2), (1.2, 7.6), -12, UPPER),
    "casal_cabeceira": ((1.6, 9.3), (0.4, 8.8), -22, UPPER),
    "casal_armario": ((3.6, 7.2), (4.2, 9.6), -2, UPPER),
    "casal_comoda": ((3.0, 6.0), (4.7, 6.9), -4, UPPER),
    "menina_cama": ((3.4, 2.9), (1.2, 3.9), -14, UPPER),
    "menina_estante": ((2.6, 2.2), (0.8, 0.3), -8, UPPER),
    "menina_casa": ((3.0, 3.6), (4.7, 2.8), -6, UPPER),
    "menina_mesa": ((3.0, 3.2), (2.0, 4.7), -10, UPPER),
    "banheiro_banheira": ((9.3, 2.6), (11.4, 1.0), -8, UPPER),
    "banheiro_pia": ((9.6, 2.4), (9.1, 4.6), -10, UPPER),
    "escritorio_cima_mesa": ((9.1, 7.2), (10.7, 9.3), -12, UPPER),
    "escritorio_cima_estante": ((10.4, 6.5), (8.2, 6.4), -4, UPPER),
    "corredor_cima": ((6.5, 1.3), (6.5, 6.0), -2, UPPER),
}


LUZ_ACESA = {"sala_acesa"}      # o estado do começo da partida, antes do apagão


def _ambientacao(nome):
    def cena(game):
        origem, alvo, pitch, z = AMBIENTACAO[nome]
        return lit(game, *origem, alvo, pitch, z=z, power=nome in LUZ_ACESA)
    return cena


HUD_SCENES = {"hud_trancada": scene_hud_trancada, "hud_silencio": scene_hud_silencio, "hud_perigo": scene_hud_perigo,
              "hud_sem_carga": scene_hud_sem_carga, "pausa": scene_pausa, "roda_pilhas": scene_roda,
              "roda_mapa": scene_roda}

SCENES = {"cozinha_ampla": scene_cozinha_ampla, "quarto": scene_quarto, "lanterna": scene_lanterna, "corredor": scene_corredor, "cozinha": scene_cozinha,
          "sala_tv": scene_sala_tv, "garagem": scene_garagem, "escada": scene_escada,
          "nota": scene_nota, "titulo": scene_titulo}
SCENES.update({nome: _ambientacao(nome) for nome in AMBIENTACAO})
SCENES.update(HUD_SCENES)


def render_player_view(scene, path, resolution, samples):
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    compat.use_eevee(scene)
    for name in ("taa_render_samples",):
        if hasattr(scene.eevee, name):
            setattr(scene.eevee, name, samples)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def load_pixels(path, size):
    image = bpy.data.images.load(path)
    pixels = np.empty(size[0] * size[1] * 4, np.float32)
    image.pixels.foreach_get(pixels)
    bpy.data.images.remove(image)
    return pixels.reshape(size[1], size[0], 4)[..., :3]


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("cenario", choices=sorted(SCENES))
    parser.add_argument("--res", default="1280x720")
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--blend", default=BLEND_PATH)
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args()
    OUT = args.out
    size = tuple(int(v) for v in args.res.lower().split("x"))
    os.makedirs(OUT, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    scene = bpy.context.scene
    from sem_alvorada.world import quality
    quality.apply(scene, "medium")
    game = Game(scene, quality="medium", audio=False, debug=False)
    game.new_game(skip_intro=True)
    game.phase = "play"
    if args.cenario not in ("quarto", "lanterna"):
        game.state.flags.add(FLAG_BLACKOUT)      # sem isso, entrar em hall_u dispara a cutscene do apagão

    x, y, z, yaw_deg, pitch_deg = SCENES[args.cenario](game)
    game.place_player(x, y, z, math.radians(yaw_deg))
    game.player.pitch = math.radians(pitch_deg)
    settle(game, 0.4)
    game.player.pitch = math.radians(pitch_deg)
    game.place_player(x, y, z, math.radians(yaw_deg))
    game.player.pitch = math.radians(pitch_deg)
    game._sync_camera()
    if args.cenario in WHEEL_MOVES:
        open_wheel(game, WHEEL_MOVES[args.cenario])
    if args.cenario in ("corredor",):
        from sem_alvorada.entity.rig import EntityRig
        rig = EntityRig(scene)
        ex, ey, ez = layout.ENTITY_FIRST_SIGHT
        rig.set_visible(True)
        rig.set_anim("stare")
        rig.set_transform(ex, ey, ez, math.pi)
        rig.eyes(1.0)
        rig.update(0.1, 0.0)
    scene.camera = game.player_cam

    raw_path = os.path.join(OUT, f"raw_{args.cenario}.png")
    started = time.time()
    render_player_view(scene, raw_path, size, args.samples)
    print(f"[prints] {args.cenario}: render em {time.time() - started:.0f}s", flush=True)

    background = load_pixels(raw_path, size)
    canvas = RasterCanvas(*size)
    screens.draw_frame(canvas, game.hud_model())
    frame = canvas.render(background)
    final = (np.clip(np.flipud(frame), 0, 1) * 255).astype(np.uint8)
    final_path = os.path.join(OUT, f"{args.cenario}.png")
    pngwrite.write_png(final_path, final)
    print(f"[prints] {final_path}", flush=True)


if __name__ == "__main__":
    main()
