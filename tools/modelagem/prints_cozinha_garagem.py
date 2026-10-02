"""Capturas da cozinha e da garagem como o jogador as vê (escuro, lanterna, HUD), em out/agente5/prints.

Reaproveita `tools/prints.py` (câmera do jogador, EEVEE, HUD rasterizado) e acrescenta cenários só meus:

    LIBGL_ALWAYS_SOFTWARE=1 python tools/modelagem/prints_cozinha_garagem.py cozinha_pia --blend out/agente5/ambiente.blend
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from tools import prints  # noqa: E402

# nome -> (x, y, alvo x, alvo y, pitch em graus). O yaw sai da direção posição -> alvo.
LOOKS = {
    "cozinha_pia": (10.2, 8.1, 10.2, 9.9, -14),
    "cozinha_pia_perto": (10.2, 8.7, 10.2, 9.9, -32),
    "cozinha_fogao": (9.7, 7.9, 11.9, 7.8, -8),
    "cozinha_geladeira": (9.8, 7.0, 11.9, 7.0, -4),
    "cozinha_oeste": (10.3, 6.5, 8.1, 6.4, -6),
    "cozinha_armarios": (10.0, 6.3, 8.1, 6.3, 22),
    "cozinha_coifa": (10.0, 7.8, 11.9, 7.8, 24),
    "cozinha_frigobar": (9.5, 6.55, 8.67, 6.45, -22),
    "cozinha_bateria": (11.0, 8.75, 11.02, 9.55, -34),
    "garagem_bateria": (17.0, 2.75, 18.05, 2.66, -34),
    "garagem_guia": (15.2, 5.4, 15.2, 6.68, -10),
    "cozinha_mesa": (9.95, 8.4, 9.95, 6.9, -22),
    "cozinha_entrada": (8.5, 8.5, 11.0, 7.0, -6),
    "garagem_bancada": (15.7, 3.2, 18.3, 3.2, -10),
    "garagem_estante": (15.2, 4.6, 15.5, 6.9, 4),
    "garagem_freezer": (14.3, 1.7, 12.1, 1.6, -8),
    "garagem_bicicleta": (14.6, 3.2, 12.2, 3.25, -12),
    "garagem_cortador": (15.9, 2.3, 17.9, 1.3, -16),
    "garagem_aquecedor": (16.2, 5.6, 18.0, 6.5, -8),
    "garagem_painel": (16.3, 2.1, 18.4, 2.0, 0),
    "garagem_entrada": (12.7, 5.7, 15.0, 3.0, -6),
}


def _scene(look):
    def build(game):
        prints.equip(game, battery=0.7, spare=2, key=True, map_found=True, batteries_found=3)
        game.lights.set_power(False)
        prints.make_noise(game, 0.0, 0.0)
        x, y, target_x, target_y, pitch = look
        return x, y, 0.0, prints.look_at_yaw(x, y, target_x, target_y), pitch
    return build


def main():
    prints.OUT = os.path.join(ROOT, "out", "agente5", "prints")
    prints.SCENES.update({name: _scene(look) for name, look in LOOKS.items()})
    prints.main()


if __name__ == "__main__":
    main()
