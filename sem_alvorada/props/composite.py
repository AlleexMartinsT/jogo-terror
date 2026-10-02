"""Peça composta: vários `MeshBuilder`, cada um com o acabamento que o seu material pede.

Um sofá junta madeira (chanfro firme), estofado (arredondado e subdividido) e metal (aresta fina). Com um
só `MeshBuilder` a receita de acabamento é uma só para a peça inteira, e o chanfro de 18 mm que arredonda
uma almofada destruiria o pé torneado. O `Composite` guarda um construtor por receita, entra no mesmo
sistema de coordenadas em todos de uma vez (`with peça.at(...)`) e, na hora de virar objeto, acaba cada
parte com a sua receita e junta tudo numa malha só. Tem a mesma interface que o `placement.place` espera
de um construtor (`to_mesh`, `bounds`, `tri_count`).
"""
from contextlib import ExitStack, contextmanager

import bpy
from mathutils import Matrix

from .. import craft
from . import tex_sala  # noqa: F401  (registra as texturas e os materiais da sala)
from .kit import MeshBuilder


class Composite:
    """Construtor com um `MeshBuilder` por acabamento. Ex.: `Composite("sofa", wood=craft.FURNITURE, soft=craft.SOFT)`."""

    def __init__(self, name, **finishes):
        self.name = name
        self._parts = {}
        for key, finish in finishes.items():
            builder = MeshBuilder(f"{name}.{key}")
            builder.finish = finish
            self._parts[key] = builder
        self._baked = []
        self._final_bounds = None

    def __getattr__(self, key):
        parts = self.__dict__.get("_parts", {})
        if key in parts:
            return parts[key]
        raise AttributeError(key)

    @contextmanager
    def at(self, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
        """Desloca/gira o sistema de coordenadas de todas as partes ao mesmo tempo."""
        with ExitStack() as stack:
            for part in self._parts.values():
                stack.enter_context(part.at(x, y, z, rx, ry, rz))
            yield self

    def add_mesh(self, mesh):
        """Junta uma malha já pronta (tecido simulado), em coordenadas locais da peça, sem novo acabamento."""
        self._baked.append(mesh)

    # ------------------------------------------------------------------
    # Medidas
    # ------------------------------------------------------------------
    @property
    def tri_count(self):
        baked = sum(len(p.vertices) - 2 for mesh in self._baked for p in mesh.polygons)
        return baked + sum(part.tri_count for part in self._parts.values())

    def bounds(self):
        """((x0, y0, z0), (x1, y1, z1)) de tudo o que a peça contém (fixado quando a malha é gerada)."""
        if self._final_bounds is not None:
            return self._final_bounds
        lows, highs = [], []
        for part in self._parts.values():
            if part.tri_count:
                low, high = part.bounds()
                lows.append(low)
                highs.append(high)
        for mesh in self._baked:
            coords = [vertex.co for vertex in mesh.vertices]
            lows.append(tuple(min(c[i] for c in coords) for i in range(3)))
            highs.append(tuple(max(c[i] for c in coords) for i in range(3)))
        return tuple(min(low[i] for low in lows) for i in range(3)), tuple(max(high[i] for high in highs) for i in range(3))

    def drop_to_floor(self):
        """Apoia a peça no chão depois de girá-la (cadeira caída, por exemplo)."""
        dz = -self.bounds()[0][2]
        for part in self._parts.values():
            if part.tri_count:
                part.translate(dz=dz)
        for mesh in self._baked:
            mesh.transform(Matrix.Translation((0.0, 0.0, dz)))

    # ------------------------------------------------------------------
    # Saída
    # ------------------------------------------------------------------
    def to_mesh(self, name=None):
        """Acaba cada parte com a sua receita e devolve uma única malha com os materiais unidos."""
        name = name or self.name
        self._final_bounds = self.bounds()
        finished = [part.to_mesh(f"{name}.{key}") for key, part in self._parts.items() if part.tri_count]
        joined = craft.join_meshes(finished + self._baked, name)
        for mesh in finished + self._baked:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        self._baked = []
        return joined
