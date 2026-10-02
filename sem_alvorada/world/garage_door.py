"""Portão seccional da garagem: cinco painéis com relevos, fileira de vidros, dobradiças e roldanas, trilhos,
mola de torção, abridor com trilho no teto e cabo de emergência.

`GarageRollup` é o Empty que o runtime e a cutscene erguem (`location.z` até `sa_open_lift`). Os painéis, as
dobradiças e as roldanas são filhos dele e sobem juntos; trilhos, mola e abridor ficam parados na casa.
Tudo que sobe usa materiais que ficam transparentes acima de `GARAGE_DOOR_CLIP_Z`: assim o portão aberto some
dentro do forro em vez de furar o telhado.
"""
import math

import bpy

from .. import compat
from .. import conventions as C
from .. import layout
from . import ext_common as ext
from .materials import GARAGE_DOOR_CLIP_Z

PANELS = 5
PANEL_THICKNESS = 0.045
JOINT_GAP = 0.012
LIFT = 2.3
WINDOWS = 4
STEEL, PAINT, GLASS = "garage_steel", "door_garage_metal", "garage_glass"
TRIM, RUBBER = "garage_trim", "garage_rubber"          # também somem acima do forro: tudo o que sobe com o portão
INNER = PANEL_THICKNESS / 2          # face interna do painel (lado +Y, dentro da garagem)
OUTER = -PANEL_THICKNESS / 2         # face externa, voltada para a rua


def _clipped_material(name, color, roughness, metallic, alpha=None):
    """Material de aço que some acima do forro: mistura com transparente pela altura de mundo."""
    mat = compat.new_material(name)
    bsdf = compat.bsdf_of(mat)
    compat.set_bsdf(bsdf, base_color=color, roughness=roughness, metallic=metallic, alpha=alpha)
    tree = mat.node_tree
    position = tree.nodes.new("ShaderNodeNewGeometry").outputs["Position"]
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(position, split.inputs["Vector"])
    above = tree.nodes.new("ShaderNodeMath")
    above.operation = "GREATER_THAN"
    above.inputs[1].default_value = GARAGE_DOOR_CLIP_Z
    tree.links.new(split.outputs["Z"], above.inputs[0])
    blend = tree.nodes.new("ShaderNodeMixShader")
    clear = tree.nodes.new("ShaderNodeBsdfTransparent")
    tree.links.new(above.outputs[0], blend.inputs[0])
    tree.links.new(bsdf.outputs["BSDF"], blend.inputs[1])
    tree.links.new(clear.outputs["BSDF"], blend.inputs[2])
    output = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    tree.links.new(blend.outputs["Shader"], output.inputs["Surface"])
    mat.diffuse_color = (*color, 1.0)
    if alpha is not None:
        mat.surface_render_method = "BLENDED" if hasattr(mat, "surface_render_method") else None
    return mat


def register_materials():
    ext.register_material(STEEL, lambda: _clipped_material(STEEL, (0.22, 0.225, 0.23), 0.45, 0.85))
    ext.register_material(GLASS, lambda: _clipped_material(GLASS, (0.03, 0.045, 0.055), 0.05, 0.0, alpha=0.3))
    ext.register_material(TRIM, lambda: _clipped_material(TRIM, (0.30, 0.285, 0.24), 0.6, 0.0))
    ext.register_material(RUBBER, lambda: _clipped_material(RUBBER, (0.015, 0.015, 0.017), 0.8, 0.0))


# --------------------------------------------------------------------------------------------
# Peças que sobem com o portão (coordenadas locais do Empty: x a partir do meio do vão, y a partir do eixo da parede)
# --------------------------------------------------------------------------------------------
def _panel_face(m, x0, x1, z0, z1):
    """Relevo da face externa: moldura (travessas e montantes) em volta de campos rebaixados."""
    proud = 0.008
    for z in (z0, z1 - 0.05):
        m.box((x0 + x1) / 2, OUTER - proud / 2, z, x1 - x0, proud, 0.05, PAINT)
    count = 4
    for k in range(count + 1):
        x = x0 + (x1 - x0) * k / count
        m.box(x, OUTER - proud / 2, z0 + 0.05, 0.07, proud, z1 - z0 - 0.10, PAINT)
    m.box((x0 + x1) / 2, OUTER - proud / 2, (z0 + z1) / 2 - 0.004, x1 - x0, proud * 0.6, 0.012, PAINT)    # nervura central


def _window_row(m, x0, x1, z0, z1):
    """Fileira de vidros pequenos na painel de cima: quadro, vidro fundo e um friso fino."""
    span = x1 - x0
    pane_w, pane_h = span / WINDOWS - 0.20, (z1 - z0) - 0.16
    for k in range(WINDOWS):
        cx = x0 + span * (k + 0.5) / WINDOWS
        zc = (z0 + z1) / 2
        for sign in (-1, 1):
            m.box(cx + sign * (pane_w / 2 + 0.014), OUTER - 0.012, zc - pane_h / 2 - 0.014, 0.028, 0.012, pane_h + 0.028, TRIM)
        for sign in (-1, 1):
            m.box(cx, OUTER - 0.012, zc + sign * (pane_h / 2 + 0.014) - 0.014, pane_w + 0.056, 0.012, 0.028, TRIM)
        m.panel(cx, OUTER + 0.012, zc, pane_w, pane_h, GLASS, "back")
        m.box(cx, 0.0, zc - 0.0015, pane_w, 0.004, 0.003, STEEL)


def _panel(m, index, width, height):
    z0 = index * height + JOINT_GAP / 2
    z1 = (index + 1) * height - JOINT_GAP / 2
    x0, x1 = -width / 2, width / 2
    if index == PANELS - 1:
        span = x1 - x0
        lower, upper = z0 + 0.12, z1 - 0.12
        m.box(0.0, 0.0, z0, span, PANEL_THICKNESS, lower - z0, PAINT)
        m.box(0.0, 0.0, upper, span, PANEL_THICKNESS, z1 - upper, PAINT)
        for k in range(WINDOWS + 1):
            cx = x0 + span * k / WINDOWS
            m.box(cx, 0.0, lower, 0.20 if 0 < k < WINDOWS else 0.10, PANEL_THICKNESS, upper - lower, PAINT)
        _window_row(m, x0, x1, lower, upper)
    else:
        m.box(0.0, 0.0, z0, width, PANEL_THICKNESS, z1 - z0, PAINT)
    _panel_face(m, x0, x1, z0, z1)
    m.box(0.0, INNER + 0.006, (z0 + z1) / 2 - 0.02, width - 0.1, 0.012, 0.04, STEEL)         # reforço horizontal por dentro


def _hinges_and_rollers(m, width, height):
    """Dobradiças em cada junta e roldanas nas pontas, presas por um braço em L até o trilho."""
    for joint in range(1, PANELS):
        z = joint * height
        for x in (-width / 2 + 0.07, -width / 4, 0.0, width / 4, width / 2 - 0.07):
            m.box(x, INNER + 0.008, z, 0.075, 0.004, 0.05, STEEL)
            m.cylinder(x, INNER + 0.012, z - 0.012, 0.006, 0.024, STEEL, seg=5)
            for dx in (-0.025, 0.025):
                m.cylinder(x + dx, INNER + 0.011, z - 0.003, 0.0045, 0.004, STEEL, seg=5)
    for joint in range(PANELS + 1):
        z = joint * height if 0 < joint < PANELS else (0.06 if joint == 0 else PANELS * height - 0.06)
        for sign in (-1, 1):
            x = sign * (width / 2 - 0.01)
            m.box(x, INNER + 0.06, z - 0.025, 0.02, 0.12, 0.05, STEEL)
            with m.at(sign * (width / 2 + 0.035), INNER + 0.115, z, ry=90):
                m.cylinder(0, 0, 0, 0.022, 0.016, STEEL, seg=10)


def _handle_and_lock(m, height):
    """Puxador de alumínio e fechadura na face externa do painel do meio."""
    z = 2 * height + height / 2
    m.box(-1.35, OUTER - 0.017, z - 0.05, 0.04, 0.026, 0.10, STEEL)
    m.box(-1.17, OUTER - 0.017, z - 0.05, 0.04, 0.026, 0.10, STEEL)
    m.box(-1.26, OUTER - 0.034, z + 0.045, 0.22, 0.016, 0.018, STEEL)
    m.cylinder(-0.95, OUTER - 0.008, z - 0.03, 0.026, 0.01, STEEL, seg=14)
    m.box(-0.95, OUTER - 0.014, z - 0.045, 0.004, 0.006, 0.026, RUBBER)
    m.box(0.0, OUTER - 0.012, 0.0, 3.9, 0.02, 0.055, RUBBER)                                  # vedação de borracha embaixo


def build_moving_parts(ctx, root, width, height):
    m = ext.builder("GarageRollup_Panels", ext.FINE)
    for index in range(PANELS):
        _panel(m, index, width, height)
    _hinges_and_rollers(m, width, height)
    _handle_and_lock(m, height)
    body = ext.emit(ctx, m, parent=root)
    return body


# --------------------------------------------------------------------------------------------
# Peças fixas
# --------------------------------------------------------------------------------------------
def _casing(ctx, op, piece):
    """Guarnição de três lados nas duas faces da parede, com pingadeira na verga e batente de madeira por dentro."""
    m = ext.builder("GarageFrame", ext.TRIM)
    half = piece.thickness / 2
    wide, proud = 0.12, 0.03
    x0, x1, top = op.a, op.b, op.height
    for side in (-1, 1):
        y0, y1 = sorted((side * half, side * (half + proud)))
        yc, depth = (y0 + y1) / 2 + op.pos, y1 - y0
        for x in (x0 - wide / 2, x1 + wide / 2):
            m.box(x, yc, 0.0, wide, depth, top + wide, "trim_white")
        m.box((x0 + x1) / 2, yc, top, x1 - x0, depth, wide, "trim_white")
        if side < 0:
            m.box((x0 + x1) / 2, yc - 0.02, top + wide, x1 - x0 + 2 * wide + 0.06, depth + 0.04, 0.03, "trim_white")
    for x in (x0, x1):                                  # batente interno (nas laterais e na verga do vão)
        m.box(x + (0.012 if x == x0 else -0.012), op.pos, 0.0, 0.024, piece.thickness, top, "wood_dark")
    m.box((x0 + x1) / 2, op.pos, top - 0.012, x1 - x0, piece.thickness, 0.024, "wood_dark")
    m.box((x0 + x1) / 2, op.pos - 0.12, 0.0, x1 - x0, 0.16, 0.012, "concrete")                  # soleira de concreto
    ext.emit(ctx, m)


def _channel_profile(side, half=0.028, depth=0.03, wall=0.004):
    """Seção em U do trilho: alma do lado de fora (`side` = +1 no trilho direito) e a abertura voltada para o portão.

    O par é (a, b): `a` ao longo da normal do caminho (largura) e `b` ao longo de X (profundidade)."""
    out, inn = side * depth, side * (depth - wall)
    return [(-half, out), (half, out), (half, -out), (half - wall, -out), (half - wall, inn), (-half + wall, inn),
            (-half + wall, -out), (-half, -out)]


def _track_path(y_wall, ceiling):
    """Caminho do trilho: sobe rente à parede, faz a curva e segue horizontal sob o forro."""
    vertical = [(0.0, y_wall, z) for z in (0.04, 0.5, 1.0, 1.5, 2.0)]
    curve = [(0.0, y, z) for _, y, z in ext.arc((0, y_wall + 0.40, 2.0), 0.40, 180, 90, "yz", steps=8)]
    run = [(0.0, y, ceiling) for y in (1.0, 1.7, 2.4)]
    return vertical + curve[1:] + run


def _tracks(ctx, mid):
    m = ext.builder("GarageTracks", ext.PROFILED)
    y_wall = 0.125 + 0.03
    for sign in (-1, 1):
        x = mid + sign * 2.0
        path = [(x, y, z) for _, y, z in _track_path(y_wall, 2.42)]
        ext.sweep_profile(m, path, _channel_profile(sign), STEEL, up=(1.0, 0.0, 0.0))
        for y in (0.5, 1.3, 2.1):
            m.bar((x, y, 2.40), (x - sign * 0.10, y + 0.02, 2.60), 0.018, STEEL)
        for z in (0.5, 1.2, 1.9):
            m.box(x - sign * 0.03, 0.14, z, 0.05, 0.10, 0.06, STEEL)
    ext.emit(ctx, m)


def _springs(ctx, mid):
    """Eixo de torção sobre a verga, duas molas, tambores de cabo e os cabos que descem até o painel de baixo."""
    m = ext.builder("GarageSpring", ext.PROFILED)
    y, z = 0.24, 2.38
    m.tube((mid - 1.95, y, z), (mid + 1.95, y, z), 0.0125, STEEL, seg=8)
    for side in (-1, 1):
        points = ext.helix((y, z), mid + side * 0.10, mid + side * 1.05, 0.045, 22)
        ext.sweep_circle(m, points, 0.0045, STEEL, sides=5)
        with m.at(mid + side * 1.55, y, z, ry=90):
            m.cylinder(0, 0, -0.03, 0.065, 0.06, STEEL, seg=16)
            m.cylinder(0, 0, -0.04, 0.075, 0.012, STEEL, seg=16)
            m.cylinder(0, 0, 0.03, 0.075, 0.012, STEEL, seg=16)
        cable_x = mid + side * 1.55 + side * 0.002
        m.tube((cable_x, y - 0.065, z), (cable_x + side * 0.46, 0.20, 0.10), 0.0035, STEEL, seg=4)
        m.box(mid + side * 1.95, 0.19, z - 0.07, 0.06, 0.06, 0.14, STEEL)
        m.box(mid + side * 0.06, 0.16, z - 0.09, 0.14, 0.035, 0.18, STEEL)
    m.box(mid, 0.185, z - 0.12, 0.30, 0.012, 0.24, STEEL)
    ext.emit(ctx, m)


def _opener(ctx, mid):
    """Motor no teto, trilho em T até a verga, carrinho, braço, cordinha vermelha e botão na parede."""
    m = ext.builder("GarageOpener", ext.FINE)
    m.soft_box(mid, 2.55, 2.20, 0.34, 0.30, 0.22, "plastic_gray", radius=0.04, edge=0.015)
    m.cylinder(mid, 2.40, 2.215, 0.05, 0.02, "toy_yellow", seg=12)
    for sx in (-0.10, 0.10):
        m.tube((mid + sx, 2.45, 2.42), (mid + sx, 2.45, 2.60), 0.006, STEEL, seg=5)
        m.tube((mid + sx, 2.65, 2.42), (mid + sx, 2.65, 2.60), 0.006, STEEL, seg=5)
    m.box(mid, 1.35, 2.31, 0.05, 2.20, 0.075, STEEL)                  # trilho em T: alma
    m.box(mid, 1.35, 2.30, 0.10, 2.20, 0.012, STEEL)                  # aba inferior
    m.box(mid, 0.28, 2.34, 0.16, 0.05, 0.16, STEEL)                   # suporte da verga
    m.box(mid, 0.75, 2.26, 0.07, 0.12, 0.06, "plastic_gray")           # carrinho
    m.bar((mid, 0.78, 2.28), (mid, 0.30, 2.05), 0.018, STEEL)           # braço do portão (levantado, solto)
    cord = [(mid + 0.05, 0.70, 2.26), (mid + 0.07, 0.72, 2.0), (mid + 0.05, 0.74, 1.72), (mid + 0.06, 0.74, 1.55)]
    ext.sweep_circle(m, cord, 0.0028, "toy_red", sides=4)
    m.sphere(mid + 0.06, 0.74, 1.52, 0.022, "toy_red", seg=8, rings=5)
    m.box(mid + 2.45, 0.115, 1.25, 0.075, 0.03, 0.11, "paper_white")     # botão da parede
    m.cylinder(mid + 2.45, 0.131, 1.30, 0.012, 0.006, "toy_red", seg=8)
    wire = [(mid + 2.45, 0.12, 1.34), (mid + 2.45, 0.125, 2.0), (mid + 2.0, 0.13, 2.45), (mid + 0.3, 1.0, 2.52), (mid + 0.15, 2.4, 2.48)]
    ext.sweep_circle(m, wire, 0.0022, "black", sides=4)
    ext.emit(ctx, m)


def _collision(ctx, op):
    blocker = ext.builder("COL_GarageRollup", ext.PROFILED)
    z0 = layout.LEVEL_Z[op.level]
    blocker.box((op.a + op.b) / 2, op.pos, z0, op.b - op.a, 0.10, op.height, "black")
    ext.emit(ctx, blocker, collection=C.COL_COLLISION, collision=True, hide=True)


def build(ctx, op, piece):
    """Cria o portão completo. `op` é `layout.OPENINGS['garage_rollup']` e `piece` a verga da parede (espessura)."""
    ext.start(ctx)
    register_materials()
    mid = op.mid[0]
    root = bpy.data.objects.new(C.OBJ_GARAGE_ROLLUP, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.15
    root.location = (mid, op.pos, layout.LEVEL_Z[op.level])
    root["sa_open_lift"] = LIFT
    root[C.P_ID] = op.id
    root[C.P_ROOM] = "garage"
    ctx.link(root, C.COL_WORLD)
    width, height = op.width - 0.06, op.height / PANELS
    build_moving_parts(ctx, root, width, height)
    _casing(ctx, op, piece)
    _tracks(ctx, mid)
    _springs(ctx, mid)
    _opener(ctx, mid)
    _collision(ctx, op)
