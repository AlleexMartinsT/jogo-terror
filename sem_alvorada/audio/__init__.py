"""Áudio do jogo: síntese sonora (numpy), motor 3D sobre `aud` e sistema de ruído.

Módulos:
- `synth`   gera os WAV (`python -m sem_alvorada.audio.synth`); receitas em `recipes_*`
- `engine`  AudioEngine: reprodução 3D, oclusão, cache e no-op sem dispositivo
- `noise`   NoiseSystem: o ruído do jogador, do ambiente e da entidade (sem bpy)
"""
import json

MANIFEST_TEXT = "SA_AUDIO_MANIFEST"


def build(ctx):
    """Regenera os WAV que faltarem e grava a lista de sons no Text `SA_AUDIO_MANIFEST`."""
    import bpy

    from . import synth

    synth.ensure_all(log=ctx.log)
    entries = synth.manifest_entries()
    text = bpy.data.texts.get(MANIFEST_TEXT) or bpy.data.texts.new(MANIFEST_TEXT)
    text.clear()
    text.write(json.dumps({"directory": "assets/audio", "sounds": entries}, indent=1))
    total = sum(e["bytes"] for e in entries)
    ctx.log(f"{len(entries)} sons no manifesto ({total / 1e6:.1f} MB)")
