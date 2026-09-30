"""Acesso único a materiais por nome canônico (conventions.MATERIAL_NAMES).

O módulo `world` (texturas procedurais, estilo Cry of Fear) implementa
`world.materials.build_material(name) -> bpy.types.Material`. Enquanto ele não
existe ou não conhece o nome, cai num material liso pela paleta, para que
props/entidade possam ser desenvolvidos e testados sozinhos.
"""
import bpy

from . import compat
from . import conventions as C

_FALLBACK_SUFFIX = "_flat"


def _flat(name):
    key = C.PALETTE.get(name)
    if key is None:
        key = C.PALETTE.get(name.split("_")[0], (0.25, 0.25, 0.25))
    mat = compat.new_material(name + _FALLBACK_SUFFIX)
    rough = 0.3 if "metal" in name else 0.85
    compat.set_bsdf(compat.bsdf_of(mat), base_color=key, roughness=rough,
                    metallic=0.6 if "metal" in name else 0.0)
    if name == "emit_white":
        compat.set_bsdf(compat.bsdf_of(mat), emission=(1, 1, 1), emission_strength=4.0)
    return mat


def get_material(name):
    """Material canônico `name`. Sempre devolve um material válido."""
    existing = bpy.data.materials.get(name)
    if existing is not None:
        return existing
    try:
        from .world import materials as wm     # implementado pelo módulo world
        mat = wm.build_material(name)
        if mat is not None:
            return mat
    except (ImportError, AttributeError):
        pass
    return _flat(name)


def assign(obj, name):
    """Atribui o material canônico ao objeto (substitui os slots)."""
    mat = get_material(name)
    if obj.data.materials:
        obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat
