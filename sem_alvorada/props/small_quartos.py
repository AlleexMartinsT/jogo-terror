"""Peças pequenas de ambientação dos cômodos de cima: livros, copos, remédios, porta-retratos, sapatos.

Todas desenham num `MeshBuilder` em andamento (coordenadas locais do móvel ou do bloco `with m.at(...)`).
Os livros usam o atlas `up_books`: lombada, cor da capa e corte das folhas saem da mesma imagem.
"""
import math

from . import tex_papeis
from .assembly_quartos import segments
from .kit import FACE_ORDER, MeshBuilder

SPINE_W, SPINE_H, PATCH_H = tex_papeis.SPINE_W, tex_papeis.SPINE_H, tex_papeis.PATCH_H
ATLAS_W, ATLAS_H = tex_papeis.BOOK_ATLAS_SIZE
BOOK_STYLES = len(tex_papeis.BOOK_COLORS)


class UvBuilder(MeshBuilder):
    """`MeshBuilder` com caixas de UV explícito por face (livros mapeados num atlas)."""

    def box_uv(self, cx, cy, z0, width, depth, height, mat, face_uv, default_uv):
        """Caixa apoiada em z0; `face_uv` mapeia nome da face -> retângulo (u0, v0, u1, v1) do atlas."""
        x0, x1, y0, y1, z1 = cx - width / 2, cx + width / 2, cy - depth / 2, cy + depth / 2, z0 + height
        corners = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        ids = self._push(corners)
        for face, order in FACE_ORDER.items():
            u0, v0, u1, v1 = face_uv.get(face, default_uv)
            self._face([ids[i] for i in order], [corners[i] for i in order], mat,
                       uv=[(u0, v0), (u1, v0), (u1, v1), (u0, v1)])


def _atlas_rect(x0, y0, x1, y1):
    """Retângulo do atlas dado em pixels (origem no topo) convertido em UV (origem embaixo)."""
    return (x0 / ATLAS_W, 1 - y1 / ATLAS_H, x1 / ATLAS_W, 1 - y0 / ATLAS_H)


def spine_rect(style):
    return _atlas_rect(style * SPINE_W, 0, (style + 1) * SPINE_W, SPINE_H)


def cover_rect(style):
    x = style * SPINE_W + SPINE_W / 2
    return _atlas_rect(x - 4, SPINE_H + 6, x + 4, SPINE_H + PATCH_H - 6)


def pages_rect():
    return _atlas_rect(8, SPINE_H + PATCH_H + 4, ATLAS_W - 8, ATLAS_H - 4)


def book(m, cx, cy, z0, thickness, depth, height, style):
    """Livro de capa dura em pé, com a lombada voltada para +Y (deite-o com `with m.at(..., ry=90)`).

    O volume é a capa (caixa inteira) mais o bloco de folhas, um pouco menor, aparecendo nas bordas, que dá a
    fresta entre a capa e as páginas.
    """
    style %= BOOK_STYLES
    mat = "up_books"
    cover = cover_rect(style)
    m.box_uv(cx, cy, z0, thickness, depth, height, mat, {"front": spine_rect(style)}, cover)
    inset = 0.0035
    m.box_uv(cx, cy - inset / 2, z0 + inset, thickness - 2 * inset - 0.004, depth - inset, height - 2 * inset, mat,
             {}, pages_rect())


def book_flat(m, cx, cy, z0, thickness, depth, height, style, *, yaw=0.0):
    """Livro deitado sobre uma superfície em z0, com a lombada para o lado +Y local (girado por `yaw` graus)."""
    with m.at(cx, cy, z0 + thickness / 2, rz=yaw, ry=90):
        book(m, 0, 0, -height / 2, thickness, depth, height, style)


def glass_tumbler(m, cx, cy, z0, radius=0.032, height=0.095, water=0.35):
    """Copo de vidro alto com um resto de água parada (e um anel de poeira na superfície)."""
    m.lathe([(radius * 0.78, 0.0), (radius * 0.85, 0.004), (radius, 0.01), (radius * 1.04, height)], cx, cy, z0,
            "up_glass", seg=segments(18), smooth=True, cap_bottom=True, cap_top=False)
    m.cylinder(cx, cy, z0 + 0.006, radius * 0.9, height * water, "up_water", seg=segments(16), r_top=radius * 0.97)


def pill_bottle(m, cx, cy, z0, radius=0.018, height=0.075):
    """Frasco âmbar com tampa branca serrilhada e rótulo de papel."""
    m.lathe([(radius * 0.92, 0), (radius, 0.003), (radius, height * 0.78), (radius * 0.72, height * 0.88),
             (radius * 0.72, height)], cx, cy, z0, "up_pill_bottle", seg=segments(16), smooth=True, cap_top=False)
    m.cylinder(cx, cy, z0 + height - 0.002, radius * 0.78, 0.016, "up_plastic_white", seg=segments(14))
    m.cylinder(cx, cy, z0 + 0.012, radius * 1.015, height * 0.45, "up_paper_blank", seg=segments(16))


def tablets(m, cx, cy, z0, count=4, spread=0.04):
    """Comprimidos brancos espalhados (discos achatados com sulco)."""
    for index in range(count):
        angle = index * 2.4
        with m.at(cx + spread * math.cos(angle) * (0.4 + 0.2 * index), cy + spread * math.sin(angle) * (0.5 + 0.1 * index),
                  z0, rz=index * 37):
            m.cylinder(0, 0, 0, 0.0045, 0.0028, "up_plastic_white", seg=10, r_top=0.0042)


def photo_stand(m, cx, cy, z0, art, *, width=0.13, height=0.17, frame="up_walnut", border=0.012, tilt=-8):
    """Porta-retrato de mesa com cavalete: moldura em quatro barras, foto, vidro e escora."""
    with m.at(cx, cy, z0, rx=tilt):
        depth = 0.014
        m.box(0, 0, 0.0, width + 2 * border, depth, border, frame)
        m.box(0, 0, height + border, width + 2 * border, depth, border, frame)
        for side in (-1, 1):
            m.box(side * (width + border) / 2, 0, border, border, depth, height, frame)
        m.panel(0, depth / 2 - 0.0035, border + height / 2, width, height, art, "front")
        m.panel(0, -depth / 2 + 0.002, border + height / 2, width + 2 * border, height + 2 * border, "up_paint_cream", "back")
    m.box(cx, cy - 0.022, z0, 0.035, 0.006, height * 0.7, frame)


# (y, meia-largura, z da sola, z do topo) do calcanhar à ponta; formas em superelipse
SHOE_SECTIONS = ((-0.145, 0.040, 0.012, 0.100), (-0.105, 0.046, 0.010, 0.104), (-0.03, 0.051, 0.008, 0.088),
                 (0.05, 0.053, 0.008, 0.060), (0.11, 0.047, 0.008, 0.045), (0.15, 0.031, 0.009, 0.032))


def shoe(m, cx, cy, z0, upper, *, yaw=0.0, scale=1.0, sole="up_rubber", tilt=0.0):
    """Um sapato (calcanhar em -Y, ponta em +Y): cabedal em seções superelípticas, sola e salto."""
    with m.at(cx, cy, z0, rz=yaw, ry=tilt):
        rings = []
        for y, half_width, z_bottom, z_top in SHOE_SECTIONS:
            half_height, center = (z_top - z_bottom) / 2 * scale, (z_top + z_bottom) / 2 * scale
            ring = []
            for k in range(12):
                angle = 2 * math.pi * k / 12
                ca, sa = math.cos(angle), math.sin(angle)
                ring.append((half_width * scale * math.copysign(abs(ca) ** 0.7, ca), y * scale,
                             center + half_height * math.copysign(abs(sa) ** 0.7, sa)))
            rings.append(ring)
        m.loft(rings, upper, cap_start=True, cap_end=True, smooth=True)
        m.soft_box(0, 0.005 * scale, 0.0, 0.108 * scale, 0.31 * scale, 0.014 * scale, sole, radius=0.04 * scale, edge=0.004 * scale)
        m.box(0, -0.12 * scale, 0.0, 0.08 * scale, 0.07 * scale, 0.026 * scale, sole)
