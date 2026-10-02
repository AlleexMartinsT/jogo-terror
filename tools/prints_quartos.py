"""Capturas dos cômodos de cima como o jogador veria: lanterna acesa, luz de teto apagada.

    LIBGL_ALWAYS_SOFTWARE=1 python tools/prints_quartos.py <cenario> --blend out/agente3/full.blend [--res 960x540]

Acrescenta cenários a `tools/prints.py` (que cuida do render, do HUD e do jogo) sem editá-lo. Cada cenário devolve
(x, y, z, yaw, pitch) da câmera do jogador e prepara luzes e lanterna.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import prints  # noqa: E402


def dark_with_flashlight(game, battery=0.7):
    prints.equip(game, battery=battery, spare=2, key=True, batteries_found=2)
    game.lights.set_power(False)
    prints.make_noise(game, 0.0, 0.0)


def looking_at(game, eye, target, pitch=-4, z=2.8):
    dark_with_flashlight(game)
    return eye[0], eye[1], z, prints.look_at_yaw(eye[0], eye[1], target[0], target[1]), pitch


SCENES = {
    "q_cama": lambda game: looking_at(game, (3.3, 6.2), (1.2, 7.6), -12),
    "q_cabeceira": lambda game: looking_at(game, (1.6, 9.3), (0.4, 8.8), -22),
    "q_armario": lambda game: looking_at(game, (3.6, 7.2), (4.2, 9.6), -2),
    "q_comoda": lambda game: looking_at(game, (3.0, 6.0), (4.7, 6.9), -4),
    "q_emma_cama": lambda game: looking_at(game, (3.4, 2.9), (1.2, 3.9), -14),
    "q_emma_estante": lambda game: looking_at(game, (2.6, 2.2), (0.8, 0.3), -8),
    "q_emma_casa": lambda game: looking_at(game, (3.0, 3.6), (4.7, 2.8), -6),
    "q_emma_mesa": lambda game: looking_at(game, (3.0, 3.2), (2.0, 4.7), -10),
    "q_banheira": lambda game: looking_at(game, (9.3, 2.6), (11.4, 1.0), -8),
    "q_pia": lambda game: looking_at(game, (9.6, 2.4), (9.1, 4.6), -10),
    "q_escritorio": lambda game: looking_at(game, (9.1, 7.2), (10.7, 9.3), -12),
    "q_estante": lambda game: looking_at(game, (10.4, 6.5), (8.2, 6.4), -4),
    "q_corredor": lambda game: looking_at(game, (6.5, 1.3), (6.5, 6.0), -2),
}

if __name__ == "__main__":
    prints.SCENES.update(SCENES)
    prints.main()
