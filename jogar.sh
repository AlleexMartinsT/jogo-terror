#!/usr/bin/env bash
# Abre o jogo no Blender. Para usar outra instalação: BLENDER=/opt/blender-5.0/blender ./jogar.sh
# Argumentos extras vão para o jogo: ./jogar.sh --quality low --skip-intro
cd "$(dirname "$0")" || exit 1
exec "${BLENDER:-blender}" SemAlvorada.blend --python play.py -- "$@"
