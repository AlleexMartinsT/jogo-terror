"""Objetos que só existem para as cutscenes: câmera, luzes de apoio, relógio 6:12, pálpebras, poeira, faíscas,
a chave com o chaveiro e as peças do carro que se mexem (coelhinho do retrovisor e volante).

Tudo nasce oculto/apagado; as ações do roteiro ligam quando precisam (`CutLight_*` com energia 0
ficam ocultas para não gastar o orçamento de luzes da cena).

O coelhinho e o volante vêm de dentro da malha `Car_Body` (uma malha só, amassada): `split_car_parts` acha as
faces que coincidem com a geometria dessas peças e as passa para objetos próprios, com o pivô no lugar certo.
Visualmente o carro fica idêntico; só passa a haver peças que giram.
"""
import math

import bpy
from mathutils import Vector

from .. import compat
from .. import conventions as C
from .. import layout
from ..props import bedroom_master as bedroom
from ..props import car_interior, kit, parts, textures
from . import scripts as sc

DUST_PARTICLES = 140
SPARK_PARTICLES = 28
BUNNY_PIVOT = (0.08, 0.265, 1.225)            # onde a linha do coelhinho prende no retrovisor (espaço do carro)
OBJ_BUNNY, OBJ_WHEEL, OBJ_KEY, OBJ_CHARM = "Cut_Bunny", "Cut_Wheel", "Cut_Key", "Cut_KeyCharm"
OBJ_DUST, OBJ_SPARKS, OBJ_LID_TOP, OBJ_LID_BOTTOM = "Cut_Dust", "Cut_Sparks", "Cut_LidTop", "Cut_LidBottom"
CUT_NAMES = (OBJ_BUNNY, OBJ_WHEEL, OBJ_KEY, OBJ_CHARM, OBJ_DUST, OBJ_SPARKS, OBJ_LID_TOP, OBJ_LID_BOTTOM)

CAMERA_FOV_DEG = 60.0


def _place(obj, ctx, hidden=False):
    ctx.link(obj, C.COL_CUTSCENE)
    obj.hide_viewport = obj.hide_render = hidden
    return obj


def create_camera(ctx):
    camera_data = bpy.data.cameras.new(C.OBJ_CUT_CAM)
    camera_data.sensor_fit = "HORIZONTAL"    # `angle` é o FOV horizontal, como o do jogador
    camera_data.angle = math.radians(CAMERA_FOV_DEG)
    camera_data.clip_start = 0.03
    camera_data.clip_end = 400.0
    cam = bpy.data.objects.new(C.OBJ_CUT_CAM, camera_data)
    first_eye = sc.anchor("nightstand_clock", 0.28, -1.1, 0.75)
    cam.location = first_eye
    cam.rotation_mode = "QUATERNION"
    return _place(cam, ctx)


def _light(ctx, name, kind, color, location, target=None, size=0.05, area=None):
    light_data = bpy.data.lights.new(name, kind)
    light_data.color = color
    light_data.energy = 0.0
    light_data.use_shadow = False
    if kind == "AREA":
        light_data.shape = "RECTANGLE"
        light_data.size, light_data.size_y = area
    else:
        light_data.shadow_soft_size = size
    obj = bpy.data.objects.new(name, light_data)
    obj.location = location
    if target is not None:
        obj.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    return _place(obj, ctx, hidden=True)


def parent_to_car(obj, ctx):
    """Se o módulo props já criou o `Car`, a luz anda com ele (mantendo a posição de mundo atual)."""
    car_obj = bpy.data.objects.get(C.OBJ_CAR)
    if car_obj is not None:
        bpy.context.view_layer.update()      # sem isso matrix_world do carro ainda é a identidade
        obj.parent = car_obj
        obj.matrix_parent_inverse = car_obj.matrix_world.inverted()


def create_lights(ctx):
    car = layout.ANCHORS["car"]
    clock = layout.ANCHORS["nightstand_clock"]
    _light(ctx, sc.CLOCK_GLOW, "POINT", (1.0, 0.12, 0.07), (clock.x + 0.16, clock.y, clock.z + 0.72))
    _light(ctx, sc.BED_LAMP, "POINT", (1.0, 0.72, 0.42), (clock.x + 0.05, clock.y + 0.12, clock.z + 1.05), size=0.12)
    window = sc.window_center("w_master_n")
    _light(ctx, sc.DAWN_LIGHT, "AREA", (0.55, 0.68, 0.95), (window[0], window[1] + 0.9, window[2]),
           target=(window[0], window[1] - 3.0, window[2] - 0.6), area=(2.6, 1.6))
    _light(ctx, sc.DRIVEWAY_LIGHT, "SPOT", (0.62, 0.72, 1.0), (10.5, -6.5, 4.8), target=(car.x, -2.0, 0.8), size=0.5)
    cabin = _light(ctx, sc.CAR_CABIN, "POINT", (0.75, 0.82, 1.0), (car.x + 0.45, car.y + 1.10, 1.35), size=0.1)
    parent_to_car(cabin, ctx)
    road = layout.ENTITY_ROAD_POS
    _light(ctx, sc.ROAD_LIGHT, "SPOT", (0.85, 0.9, 1.0), (road[0], road[1] + 6.0, 3.4),
           target=(road[0], road[1], 1.4), size=0.4)
    sight = layout.ENTITY_FIRST_SIGHT
    _light(ctx, sc.CORRIDOR_RIM, "POINT", (0.55, 0.68, 1.0), (sight[0], sight[1] + 0.9, sight[2] + 2.3), size=0.2)


def _display_material(name="cut_clock_digits", strength=7.0):
    """Mostrador 6:12 do relógio final: a mesma imagem do despertador, emissiva e mais forte (é o foco do plano)."""
    mat = compat.new_material(name)
    bsdf = compat.bsdf_of(mat)
    image = mat.node_tree.nodes.new("ShaderNodeTexImage")
    image.image = textures.image("digits_612")
    image.interpolation = "Closest"           # mostrador digital: pixel de propósito
    mat.node_tree.links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
    mat.node_tree.links.new(image.outputs["Color"], bsdf.inputs["Emission Color"])
    compat.set_bsdf(bsdf, base_color=(0, 0, 0), roughness=0.4, emission_strength=strength)
    return mat


def create_end_clock(ctx):
    """Despertador marcando 6:12, no lugar exato do da cabeceira (que o roteiro esconde), para o plano final."""
    anchor = layout.ANCHORS["nightstand_clock"]
    x, y, yaw = bedroom.ALARM_CLOCK_POSE
    top = 0.55
    _display_material()
    mesh = bedroom.alarm_clock_assembly("cut_clock_digits", sc.END_CLOCK).to_mesh(sc.END_CLOCK)
    obj = bpy.data.objects.new(sc.END_CLOCK, mesh)
    obj.location = (x, y, anchor.z + top + 0.001)
    obj.rotation_euler = (0.0, 0.0, yaw)
    return _place(obj, ctx, hidden=True)


# --------------------------------------------------------------------------
# Materiais simples de efeito
# --------------------------------------------------------------------------
def _effect_material(name, color, emission, strength, roughness=0.9):
    mat = compat.new_material(name)
    compat.set_bsdf(compat.bsdf_of(mat), base_color=color, roughness=roughness, emission=emission,
                    emission_strength=strength)
    return mat


def _particle_mesh(name, count, material):
    """Malha de `count` losangos de 4 vértices; as posições reais vêm do ator a cada quadro."""
    mesh = bpy.data.meshes.new(name)
    verts = [(0.0, 0.0, 0.0)] * (count * 4)
    faces = [(4 * k, 4 * k + 1, 4 * k + 2, 4 * k + 3) for k in range(count)]
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    return mesh


def create_dust(ctx):
    """Poeira e lascas de reboco (o estrondo no andar de cima)."""
    mat = _effect_material("cut_dust", (0.45, 0.42, 0.37), (0.45, 0.42, 0.36), 0.7, roughness=1.0)
    obj = bpy.data.objects.new(OBJ_DUST, _particle_mesh(OBJ_DUST, DUST_PARTICLES, mat))
    obj.visible_shadow = False
    return _place(obj, ctx, hidden=True)


def create_sparks(ctx):
    """Faíscas da lâmpada que estoura."""
    mat = _effect_material("cut_spark", (1.0, 0.7, 0.3), (1.0, 0.72, 0.32), 60.0)
    obj = bpy.data.objects.new(OBJ_SPARKS, _particle_mesh(OBJ_SPARKS, SPARK_PARTICLES, mat))
    obj.visible_shadow = False
    return _place(obj, ctx, hidden=True)


def _lid_material():
    """Pálpebra: pele escura e avermelhada que deixa a luz passar de leve; a borda é macia (transparência em rampa)."""
    mat = compat.new_material("cut_eyelid")
    mat.node_tree.nodes.clear()
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new("ShaderNodeTexCoord")
    split = nodes.new("ShaderNodeSeparateXYZ")
    absolute = nodes.new("ShaderNodeMath")
    absolute.operation = "ABSOLUTE"
    ramp = nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.0, 0.010
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (0.20, 0.032, 0.020, 1.0)
    emission.inputs["Strength"].default_value = 1.0
    clear = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(coords.outputs["Object"], split.inputs["Vector"])
    links.new(split.outputs["Y"], absolute.inputs[0])
    links.new(absolute.outputs["Value"], ramp.inputs["Value"])
    links.new(ramp.outputs["Result"], mix.inputs["Fac"])
    links.new(clear.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    try:
        mat.surface_render_method = "BLENDED"            # EEVEE 4.2 e 5.0; o Cycles ignora
    except (AttributeError, TypeError):
        pass
    return mat


def create_lids(ctx, cam):
    """Duas pálpebras coladas na lente (filhas da câmera): o player as fecha e abre por `Shot.lids`."""
    mat = _lid_material()
    for name, sign in ((OBJ_LID_TOP, 1.0), (OBJ_LID_BOTTOM, -1.0)):
        mesh = bpy.data.meshes.new(name)
        w, h = 0.30, 0.30
        mesh.from_pydata([(-w, 0.0, 0.0), (w, 0.0, 0.0), (w, sign * h, 0.0), (-w, sign * h, 0.0)], [],
                         [(0, 1, 2, 3) if sign > 0 else (3, 2, 1, 0)])
        mesh.materials.append(mat)
        mesh.update()
        lid = bpy.data.objects.new(name, mesh)
        lid.parent = cam
        lid.visible_shadow = False
        _place(lid, ctx, hidden=True)


def create_key(ctx):
    """A chave do carro (latão, ponta em Z=0, arco no alto) e o chaveiro com o coelhinho da Emma (objeto filho)."""
    kit.set_quality(getattr(ctx, "quality", "medium"))
    m = kit.MeshBuilder(OBJ_KEY)
    m.box(0.0, 0.0, 0.0, 0.0085, 0.0022, 0.034, "key_metal")
    for k, width in enumerate((0.0030, 0.0042, 0.0028, 0.0038)):
        m.box(0.0040, 0.0, 0.004 + k * 0.0065, width, 0.0022, 0.0035, "key_metal")
    m.box(0.0, 0.0, 0.034, 0.014, 0.0030, 0.004, "key_metal")
    m.torus(0.0, 0.0, 0.049, 0.0105, 0.0032, "key_metal", seg=18, seg_minor=6, rx=90)
    mesh = m.to_mesh(OBJ_KEY)
    key = bpy.data.objects.new(OBJ_KEY, mesh)
    _place(key, ctx, hidden=True)
    c = kit.MeshBuilder(OBJ_CHARM)
    c.torus(0.0, 0.0, -0.006, 0.0075, 0.0018, "steel_dark", seg=14, seg_minor=5, rx=0)
    for k in range(3):
        c.torus(0.0, 0.0, -0.016 - 0.0085 * k, 0.0045, 0.0012, "steel_dark", seg=10, seg_minor=4, rx=90 * (k % 2))
    with c.at(0.0, 0.0, -0.118):
        parts.rabbit(c, 0.0, 0.0, 0.0, 0.17)
    charm = bpy.data.objects.new(OBJ_CHARM, c.to_mesh(OBJ_CHARM))
    charm.parent = key
    charm.location = (0.0, 0.0, 0.049)
    _place(charm, ctx, hidden=True)


# --------------------------------------------------------------------------
# Peças do carro que se mexem
# --------------------------------------------------------------------------
def _wheel_rim(m):
    """O aro, o cubo, os raios e o botão do volante: o mesmo código de `car_interior.steering_wheel`, sem a coluna."""
    plastic = car_interior.PLASTIC
    with m.at(*car_interior.WHEEL_HUB, rx=65):
        m.torus(0, 0, 0, 0.19, 0.0165, plastic, seg=28, seg_minor=8)
        m.soft_box(0, 0, -0.025, 0.115, 0.115, 0.05, plastic, radius=0.03, edge=0.012, corner_points=4)
        for angle in (90, 210, 330):
            end = (0.178 * math.cos(math.radians(angle)), 0.178 * math.sin(math.radians(angle)), 0)
            m.bar((0, 0, 0), end, 0.024, plastic)
        m.cylinder(0, 0, 0.026, 0.034, 0.003, "car_rim", seg=14)
        m.torus(0, 0, 0.0285, 0.028, 0.0025, "car_rim", seg=14, seg_minor=4)


def _hanging_rabbit(m):
    """A linha e o coelhinho pendurados no retrovisor: o mesmo código de `car_interior.headliner_details`."""
    mirror_y = 0.325
    m.tube((0.08, mirror_y - 0.06, 1.225), (0.08, mirror_y - 0.06, 1.095), 0.0025, "paper_white", seg=3)
    with m.at(0.08, mirror_y - 0.06, 1.01, rx=-4, rz=170):
        parts.rabbit(m, 0, 0, 0, 0.42)


def _probe_points(build):
    m = car_interior.interior_builder()
    build(m)
    return [tuple(v) for v in m._verts], len(m._faces)


def _remove_faces(mesh, drop_ids=None, keep_ids=None, shift=(0.0, 0.0, 0.0)):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    doomed = [f for f in bm.faces if (f.index in drop_ids if drop_ids is not None else f.index not in keep_ids)]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    if any(shift):
        bmesh.ops.translate(bm, vec=Vector(shift), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def split_car_part(ctx, name, build, pivot, min_match=0.9):
    """Passa de `Car_Body` para o objeto `name` as faces que coincidem com a geometria gerada por `build`.

    O pivô (espaço do carro) vira a origem do novo objeto, filho do `Car`. Devolve o objeto, ou None se a malha
    do carro não bate com a receita (o carro mudou): nesse caso nada é alterado e a cutscene segue sem a peça.
    """
    from mathutils.kdtree import KDTree
    body = bpy.data.objects.get("Car_Body")
    car = bpy.data.objects.get(C.OBJ_CAR)
    if body is None or car is None or bpy.data.objects.get(name) is not None:
        return bpy.data.objects.get(name)
    points, face_count = _probe_points(build)
    tree = KDTree(len(points))
    for index, point in enumerate(points):
        tree.insert(point, index)
    tree.balance()
    mesh = body.data
    close = [tree.find(v.co)[2] < 2e-4 for v in mesh.vertices]
    taken = {p.index for p in mesh.polygons if all(close[v] for v in p.vertices)}
    if len(taken) < min_match * face_count:
        print(f"[cutscenes] {name}: só {len(taken)} de {face_count} faces coincidem em Car_Body; peça não separada", flush=True)
        return None
    part = mesh.copy()
    part.name = name
    _remove_faces(part, keep_ids=taken, shift=tuple(-c for c in pivot))
    _remove_faces(mesh, drop_ids=taken)
    body["sa_tris"] = sum(len(p.vertices) - 2 for p in mesh.polygons)
    obj = bpy.data.objects.new(name, part)
    obj.parent = car
    obj.location = pivot
    ctx.link(obj, C.COL_PROPS)
    return obj


def split_car_parts(ctx):
    split_car_part(ctx, OBJ_BUNNY, _hanging_rabbit, BUNNY_PIVOT)
    split_car_part(ctx, OBJ_WHEEL, _wheel_rim, car_interior.WHEEL_HUB)


def purge():
    """Apaga os objetos e as malhas de efeito (para recriar sobre um .blend já montado, sem refazer o build inteiro)."""
    for name in CUT_NAMES:
        obj = bpy.data.objects.get(name)
        if obj is not None and name not in (OBJ_BUNNY, OBJ_WHEEL):       # as peças do carro não voltam para Car_Body
            data = obj.data
            bpy.data.objects.remove(obj)
            if data is not None and data.users == 0:
                bpy.data.meshes.remove(data)


def create_all(ctx):
    cam = create_camera(ctx)
    create_lights(ctx)
    create_end_clock(ctx)
    create_lids(ctx, cam)
    create_dust(ctx)
    create_sparks(ctx)
    create_key(ctx)
    split_car_parts(ctx)


def rebuild(scene):
    """Recria os objetos de cutscene sobre um .blend já montado (câmera, luzes, efeitos). Usado pelo preview."""
    from ..buildctx import BuildContext
    collection = bpy.data.collections.get(C.COL_CUTSCENE)
    for obj in list(collection.objects) if collection else []:
        data = obj.data
        bpy.data.objects.remove(obj)
        if data is not None and getattr(data, "users", 1) == 0:
            (bpy.data.meshes if isinstance(data, bpy.types.Mesh) else bpy.data.cameras if isinstance(data, bpy.types.Camera)
             else bpy.data.lights).remove(data)
    ctx = BuildContext(scene, verbose=False)
    create_all(ctx)
    if bpy.data.objects.get(C.OBJ_BODY_RIG) is None:            # .blend de antes da etapa `body`
        try:
            from .. import body
            body.build(ctx)
        except Exception as error:                              # noqa: BLE001 - sem corpo as cenas seguem
            print(f"[cutscenes] corpo não montado: {error}", flush=True)
    bpy.context.view_layer.update()
