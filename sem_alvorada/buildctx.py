"""Contexto compartilhado pelas etapas de construção do .blend."""
import random

import bpy

from . import conventions as C


class BuildContext:
    """Passado a `build(ctx)` de cada módulo.

    - ctx.scene: cena onde tudo é criado
    - ctx.coll(name): coleção SA_* (criada e ligada à cena sob demanda)
    - ctx.rng: random.Random determinístico (mesmo .blend a cada build)
    - ctx.log(msg): mensagens de progresso
    """

    def __init__(self, scene=None, seed=1347, quality="medium", verbose=True):
        self.scene = scene or bpy.context.scene
        self.rng = random.Random(seed)
        self.seed = seed
        self.quality = quality      # 'low' | 'medium' | 'high': afeta densidade de detalhe e sombras
        self.verbose = verbose
        self.stage = ""

    def coll(self, name):
        c = bpy.data.collections.get(name)
        if c is None:
            c = bpy.data.collections.new(name)
        if c.name not in self.scene.collection.children:
            self.scene.collection.children.link(c)
        return c

    def link(self, obj, coll_name):
        """Liga obj à coleção (removendo de outras onde estiver)."""
        target = self.coll(coll_name)
        for c in list(obj.users_collection):
            if c is not target:
                c.objects.unlink(obj)
        if obj.name not in target.objects:
            target.objects.link(obj)
        return obj

    def log(self, msg):
        if self.verbose:
            print(f"[{self.stage or 'build'}] {msg}", flush=True)
