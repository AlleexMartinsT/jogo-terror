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
from . import kit, mat_quartos, materials  # noqa: F401  (mat_quartos registra os materiais up_* ao ser importado)
from .kit import MeshBuilder


# receitas de acabamento dos quartos (ver `craft.Finish`). Chanfro de 1 segmento já pega luz e custa um quarto do de 3.
WOOD = craft.Finish(bevel=0.004, bevel_segments=1, bevel_angle=45.0, smooth_angle=50.0)        # móvel comum
HERO_WOOD = craft.Finish(bevel=0.006, bevel_segments=2, bevel_angle=45.0, smooth_angle=50.0)    # cama, guarda-roupa
PAINTED = craft.Finish(bevel=0.005, bevel_segments=1, bevel_angle=45.0, smooth_angle=50.0)
METAL = craft.Finish(bevel=0.0025, bevel_segments=1, bevel_angle=45.0, smooth_angle=45.0)
UPHOLSTERY = craft.Finish(bevel=0.0, subsurf=1, smooth_angle=80.0)       # `soft_box` já arredonda; a subdivisão suaviza
CLOTH = craft.Finish(bevel=0.0, subsurf=0, smooth_angle=65.0)            # pano e papel: só sombreamento
PLUSH = craft.Finish(bevel=0.0, subsurf=0, smooth_angle=180.0)           # pelúcia e roupa pendurada: tudo liso


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

    def part(self, finish=craft.FURNITURE, name=None, builder_class=MeshBuilder):
        """Novo builder da peça com a receita `finish` (None = malha crua)."""
        builder = builder_class(name or f"{self.name}_{len(self.builders)}")
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
                corners.extend((tuple(float(c) for c in coords.min(axis=0)), tuple(float(c) for c in coords.max(axis=0))))
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
