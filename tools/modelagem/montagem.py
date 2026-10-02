"""Junta várias folhas de inspeção (PNG) numa só imagem, uma sobre a outra, para olhar de uma vez.

    python tools/modelagem/montagem.py out/agente5/montagem.png out/agente5/insp/a.png out/agente5/insp/b.png
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from tools import pngwrite  # noqa: E402


def load_rgb(path):
    image = bpy.data.images.load(path)
    width, height = image.size
    pixels = np.empty(width * height * 4, np.float32)
    image.pixels.foreach_get(pixels)
    bpy.data.images.remove(image)
    return np.flipud(pixels.reshape(height, width, 4)[..., :3])


def main(argv):
    out, sheets = argv[0], argv[1:]
    frames = [load_rgb(path) for path in sheets]
    width = max(frame.shape[1] for frame in frames)
    padded = [np.pad(frame, ((0, 0), (0, width - frame.shape[1]), (0, 0))) for frame in frames]
    pngwrite.write_png(out, (np.clip(np.concatenate(padded, axis=0), 0, 1) * 255).astype(np.uint8))
    print(out)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
