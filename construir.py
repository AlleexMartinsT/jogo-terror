"""Reconstrói o SemAlvorada.blend do zero, por código.

Com o Blender instalado:   blender -b --python construir.py -- --quality medium
Com o módulo bpy (pip):    python construir.py --quality medium

Aceita as mesmas opções de `python -m sem_alvorada.build` (--stages, --out, --strict, --quality).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sem_alvorada.build import main  # noqa: E402

# Dentro do Blender tudo depois do "--" é nosso; fora dele, são os argumentos normais.
argumentos = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
sys.exit(main(argumentos))
