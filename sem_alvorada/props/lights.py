"""Luzes de peças (abajures, TV, luz noturna, painel do carro): `Light_<room>_p<n>`.

O runtime liga só as luzes dos cômodos vizinhos ao jogador e escala `sa_base_energy`;
por isso todas nascem sem sombra (só a lanterna projeta sombra) e com as propriedades `sa_*`.
"""
import bpy

from .. import conventions as C


def make_point_light(ctx, room, index, position, energy, color, kind="lamp", flicker=0.0,
                     radius=0.06, parent=None):
    """Cria `Light_<room>_p<index>` e a liga a SA_Props. Devolve o objeto."""
    name = f"{C.N_LIGHT}{room}_p{index}"
    data = bpy.data.lights.new(name, "POINT")
    data.energy = energy
    data.color = color
    data.shadow_soft_size = radius
    data.use_shadow = False
    light = bpy.data.objects.new(name, data)
    light.location = position
    light[C.P_ROOM] = room
    light[C.P_LIGHT_ENERGY] = energy
    light[C.P_LIGHT_FLICKER] = flicker
    light[C.P_LIGHT_KIND] = kind
    ctx.link(light, C.COL_PROPS)
    if parent is not None:
        keep_world_position(light, parent)
    return light


def keep_world_position(child, parent):
    """Parenteia sem mover o filho: `location` continua sendo a posição de mundo em repouso."""
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
