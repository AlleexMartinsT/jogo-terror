"""Peça composta: várias malhas com receitas de acabamento diferentes unidas em um único objeto.

Um `MeshBuilder` aplica UMA receita (`craft.Finish`) à malha inteira, mas um móvel mistura madeira (chanfro),
estofado (subdivisão) e pano simulado (já pronto). `Assembly` guarda uma lista de builders, cada um com a sua
receita, mais malhas prontas, e entrega tudo junto com a mesma interface que `placement.place` espera
(`to_mesh`, `bounds`).
"""
import bpy
import numpy as np
from mathutils import Matrix

from .. import craft
from . import kit, materials
from .kit import MeshBuilder


def segments(count):
    """Número de lados de peças torneadas, ajustado pela qualidade do build (nunca menos de 8)."""
    factor = {"low": 0.6, "medium": 1.0, "high": 1.4}.get(kit.QUALITY, 1.0)
    return max(8, int(round(count * factor)))


class Assembly:
    """Conjunto de `MeshBuilder` (cada um com seu acabamento) e de malhas prontas, juntos num só `Mesh`."""

    def __init__(self, name):
        self.name = name
        self.builders = []
        self.baked = []
        self._bounds = None

    def part(self, finish=craft.FURNITURE, name=None):
        """Novo builder da peça com a receita `finish` (None = malha crua)."""
        builder = MeshBuilder(name or f"{self.name}_{len(self.builders)}")
        builder.finish = finish
        self.builders.append(builder)
        return builder

    def add_mesh(self, mesh, material_name, offset=(0.0, 0.0, 0.0), matrix=None):
        """Acrescenta uma malha pronta (pano simulado, travesseiro). Suas coordenadas já são as do móvel."""
        transform = Matrix.Translation(offset) if matrix is None else matrix
        mesh.transform(transform)
        if not mesh.materials:
            mesh.materials.append(materials.get(material_name))
        self.baked.append(mesh)
        return mesh

    @property
    def tri_count(self):
        built = sum(builder.tri_count for builder in self.builders)
        return built + sum(len(p.vertices) - 2 for mesh in self.baked for p in mesh.polygons)

    def bounds(self):
        """((x0, y0, z0), (x1, y1, z1)) de tudo; fica guardado porque `to_mesh` consome as malhas prontas."""
        if self._bounds is None:
            corners = [corner for builder in self.builders if builder._faces for corner in builder.bounds()]
            for mesh in self.baked:
                coords = np.empty(len(mesh.vertices) * 3, np.float32)
                mesh.vertices.foreach_get("co", coords)
                coords = coords.reshape(-1, 3)
                corners.extend((tuple(coords.min(axis=0)), tuple(coords.max(axis=0))))
            xs, ys, zs = zip(*corners)
            self._bounds = ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))
        return self._bounds

    def to_mesh(self, name=None):
        self.bounds()
        meshes = [builder.to_mesh() for builder in self.builders if builder._faces]
        meshes.extend(self.baked)
        joined = craft.join_meshes(meshes, name or self.name)
        for mesh in meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        return joined
