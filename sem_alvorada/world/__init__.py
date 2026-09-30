"""Módulo world: a casa, o exterior, os materiais, as luzes de teto e a atmosfera.

`build(ctx)` cria tudo em ordem; cada parte registra o que fez com `ctx.log`.
"""
from . import shell


def build(ctx):
    shell.build(ctx)
