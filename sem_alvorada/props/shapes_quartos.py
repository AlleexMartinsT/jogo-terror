"""Formas por anéis dos cômodos de cima: banheira, vaso, cuba, tampo com furo, assento.

Os anéis (listas de pontos 3D com a mesma contagem) alimentam `MeshBuilder.loft`, que une um anel ao próximo;
quando a lista vai da base, sobe pela parede de fora, passa pela borda e desce pela parede de dentro, o loft
fecha uma casca com espessura: é como uma peça de louça é feita, sem booleana.
"""
import math

import bmesh

from .. import craft
from . import kit
from .kit import MeshBuilder, rounded_rect


class WeldedBuilder(MeshBuilder):
    """`MeshBuilder` que solda vértices coincidentes antes do acabamento.

    Faces soltas (quads de `annulus`) não compartilham vértices, então o chanfro não enxerga as arestas entre
    elas. Soldar primeiro deixa o chanfro e o sombreamento por ângulo tratarem a peça como um sólido.
    """

    def to_mesh(self, name=None):
        finish, self.finish = self.finish, None
        mesh = super().to_mesh(name)
        self.finish = finish
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        return craft.finish_mesh(mesh, finish, kit.QUALITY) if finish is not None else mesh


def oval_ring(half_x, half_y, z, *, cx=0.0, cy=0.0, back_half_y=None, exponent=2.4, points=28):
    """Anel superelíptico (ovo achatado) no plano XY: `back_half_y` dá uma metade de trás diferente da da frente."""
    ring = []
    back = half_y if back_half_y is None else back_half_y
    for k in range(points):
        angle = 2 * math.pi * k / points
        ca, sa = math.cos(angle), math.sin(angle)
        radius_y = half_y if sa >= 0 else back
        ring.append((cx + half_x * math.copysign(abs(ca) ** (2 / exponent), ca),
                     cy + radius_y * math.copysign(abs(sa) ** (2 / exponent), sa), z))
    return ring


def rect_ring(length, width, corner, z, *, inset=0.0, corner_points=5):
    """Anel de retângulo de cantos arredondados (comprimento em X, largura em Y), recuado em `inset` por lado."""
    outline = rounded_rect(length - 2 * inset, width - 2 * inset, max(corner - inset, 0.02), corner_points)
    return [(x, y, z) for x, y in outline]


def annulus(m, outer, inner, mat, *, thickness, z_top):
    """Placa com furo entre dois contornos de mesma contagem de pontos: tampo, assento, aro de pia.

    `outer` e `inner` são listas de (x, y) no mesmo sentido; o furo atravessa a placa e as paredes do furo e da
    borda ganham faces próprias, então o resultado é um sólido fechado.
    """
    z_bottom = z_top - thickness
    count = len(outer)
    for k in range(count):
        n = (k + 1) % count
        quads = (
            ((outer[k], z_top), (outer[n], z_top), (inner[n], z_top), (inner[k], z_top)),
            ((inner[k], z_bottom), (inner[n], z_bottom), (outer[n], z_bottom), (outer[k], z_bottom)),
            ((outer[k], z_bottom), (outer[n], z_bottom), (outer[n], z_top), (outer[k], z_top)),
            ((inner[n], z_bottom), (inner[k], z_bottom), (inner[k], z_top), (inner[n], z_top)),
        )
        for corners in quads:
            m.quad(*[(p[0], p[1], z) for p, z in corners], mat)


def ellipse_outline(half_x, half_y, cx=0.0, cy=0.0, points=28, exponent=2.0):
    return [(cx + half_x * math.copysign(abs(math.cos(2 * math.pi * k / points)) ** (2 / exponent), math.cos(2 * math.pi * k / points)),
             cy + half_y * math.copysign(abs(math.sin(2 * math.pi * k / points)) ** (2 / exponent), math.sin(2 * math.pi * k / points)))
            for k in range(points)]
