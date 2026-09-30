"""SEM ALVORADA: jogo de terror psicológico feito inteiramente no Blender."""
import os

VERSION = "0.1.0"
TITULO = "SEM ALVORADA"

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PACKAGE_DIR)
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")
BLEND_PATH = os.path.join(ROOT_DIR, "SemAlvorada.blend")
