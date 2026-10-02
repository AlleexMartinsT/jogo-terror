"""Módulo world: a casa, o exterior, os materiais, as luzes de teto e a atmosfera.

`build(ctx)` cria tudo em ordem; cada parte registra o que fez com `ctx.log`.
"""
from . import decals, details, exterior, lighting, openings, quality, roof, shell, sky, stairs


def build(ctx):
    shell.build(ctx)
    openings.build(ctx)
    stairs.build(ctx)
    details.build(ctx)
    decals.build(ctx)
    roof.build(ctx)
    lighting.build(ctx)
    exterior.build(ctx)
    sky.build(ctx)
    skipped = quality.apply(ctx.scene, ctx.quality)
    ctx.log(f"qualidade '{ctx.quality}' aplicada" + (f"; ignorado: {'; '.join(skipped)}" if skipped else ""))
