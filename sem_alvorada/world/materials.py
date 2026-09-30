"""Materiais da casa (versão provisória da etapa 1: cores lisas)."""
import bpy

from .. import compat
from .. import conventions as C

EXTRA_COLORS = {
    "wall_wallpaper": (0.27, 0.25, 0.20), "wall_paint_dirty": (0.22, 0.25, 0.21),
    "wall_tile_bath": (0.40, 0.44, 0.42), "wall_garage": (0.20, 0.21, 0.21),
    "wall_brick_ext": (0.22, 0.10, 0.07), "wall_siding_ext": (0.30, 0.31, 0.27),
    "floor_wood": (0.24, 0.15, 0.09), "floor_wood_dark": (0.13, 0.08, 0.05),
    "floor_carpet": (0.12, 0.16, 0.13), "floor_linoleum": (0.28, 0.26, 0.19),
    "floor_tile_bath": (0.36, 0.40, 0.40), "floor_concrete": (0.20, 0.20, 0.19),
    "ceiling": (0.45, 0.44, 0.40), "roof_shingle": (0.07, 0.07, 0.08),
    "door_wood": (0.14, 0.08, 0.05), "trim_white": (0.50, 0.48, 0.42),
    "stairs_wood": (0.15, 0.09, 0.05), "glass_night": (0.02, 0.03, 0.04),
    "curtain": (0.22, 0.15, 0.13),
}


def build_material(name):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    color = C.PALETTE.get(name) or EXTRA_COLORS.get(name) or (0.25, 0.25, 0.25)
    mat = compat.new_material(name)
    compat.set_bsdf(compat.bsdf_of(mat), base_color=color, roughness=0.9)
    mat.diffuse_color = (*color, 1.0)
    return mat


def material_for(name):
    return build_material(name)
