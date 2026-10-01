"""Pré-visualização dos props em contexto (ferramenta de desenvolvimento, não faz parte do jogo).

    python -m sem_alvorada.props.preview_rooms --rooms master,kids --fill 0.15
    python -m sem_alvorada.props.preview_rooms --rooms living --flash        # só a lanterna
    python -m sem_alvorada.props.preview_rooms --rooms items --flash         # vistas dos itens

Monta uma casca provisória (pisos e paredes lisos, sem forro) a partir do layout, roda
`props.build` e renderiza as câmeras de `VIEWS` com Cycles em baixa resolução.
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sem_alvorada import build as project_build  # noqa: E402
from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.buildctx import BuildContext  # noqa: E402
from sem_alvorada.props import kit, placement  # noqa: E402
from tools import preview  # noqa: E402

OUT_DIR = os.path.join(ROOT, "out", "props")
EYE = 1.55

# nome da vista -> (câmera, alvo); z relativo ao piso do cômodo
VIEWS = {
    "master": [("a", (4.6, 5.35, 1.6), (1.2, 7.6, 0.6)), ("b", (1.9, 5.3, 1.6), (3.6, 9.4, 0.8)),
               ("c", (1.4, 9.5, 1.7), (4.6, 6.3, 0.7))],
    "kids": [("a", (4.6, 4.6, 1.6), (1.0, 2.6, 0.5)), ("b", (2.5, 0.5, 1.6), (2.2, 4.6, 0.7)),
             ("c", (0.4, 1.0, 1.6), (4.4, 3.2, 0.5))],
    "bath": [("a", (8.4, 1.4, 1.6), (11.2, 2.4, 0.6)), ("b", (11.5, 4.5, 1.6), (9.0, 1.0, 0.7)),
             ("c", (10.0, 0.5, 1.6), (9.2, 4.9, 1.1))],
    "study": [("a", (8.6, 5.4, 1.6), (11.0, 9.3, 0.7)), ("b", (11.6, 9.4, 1.6), (8.4, 6.0, 0.7))],
    "hall_u": [("a", (6.6, 0.5, 1.6), (6.8, 9.0, 0.8)), ("b", (6.8, 9.6, 1.6), (6.6, 1.0, 0.8))],
    "hall_g": [("a", (6.6, 0.6, 1.6), (6.9, 6.0, 0.9)), ("b", (7.2, 9.6, 1.6), (5.3, 1.5, 0.9)),
               ("c", (5.5, 4.0, 1.4), (7.9, 5.0, 1.0))],
    "living": [("a", (0.6, 0.6, 1.6), (4.4, 4.0, 0.6)), ("b", (4.6, 1.2, 1.6), (0.8, 4.6, 0.6)),
               ("c", (1.0, 5.6, 1.6), (4.5, 1.5, 0.6))],
    "den": [("a", (4.5, 6.5, 1.6), (1.4, 9.3, 0.8)), ("b", (2.5, 6.4, 1.6), (0.3, 9.4, 1.2)),
            ("c", (0.5, 9.4, 1.6), (4.5, 6.5, 0.6))],
    "dining": [("a", (8.4, 0.5, 1.6), (11.0, 3.0, 0.6)), ("b", (11.6, 4.6, 1.6), (8.5, 0.6, 0.6))],
    "kitchen": [("a", (8.5, 5.4, 1.6), (11.4, 8.4, 0.9)), ("b", (11.5, 5.2, 1.6), (8.3, 8.0, 0.9)),
                ("c", (9.0, 9.6, 1.6), (11.6, 6.9, 0.9))],
    "garage": [("a", (13.0, 6.4, 1.6), (16.0, 2.0, 0.8)), ("b", (18.2, 0.6, 1.6), (13.0, 4.6, 0.9)),
               ("c", (12.6, 0.6, 1.6), (18.0, 3.2, 0.9))],
    "garage_shelf": [("a", (15.3, 5.3, 1.7), (15.4, 6.7, 1.0)), ("b", (14.6, 5.6, 1.0), (15.3, 6.7, 1.0))],
    "car": [("out", (13.2, 0.4, 1.7), (15.6, 3.0, 0.6)), ("drv", (15.95, 3.45, 1.28), (15.6, 0.0, 1.0)),
            ("back", (17.6, 5.8, 1.6), (15.5, 2.0, 0.6))],
}


def build_provisional_shell(ctx):
    """Pisos e paredes lisos (sem forro), só para dar contexto às renderizações."""
    shell = ctx.coll("SA_World")
    for level in (0, 1):
        z = layout.LEVEL_Z[level]
        for room_id, rect in layout.floor_rects(level):
            builder = kit.MeshBuilder(f"_floor_{room_id}")
            builder.box(*rect.center, z - 0.1, rect.w, rect.h, 0.1, "wood_dark")
            obj = bpy.data.objects.new(f"_floor_{room_id}", builder.to_mesh())
            shell.objects.link(obj)
        for piece in layout.wall_pieces(level):
            rect = piece.rect2d()
            builder = kit.MeshBuilder("_wall")
            builder.box(*rect.center, piece.z0, rect.w, rect.h, piece.z1 - piece.z0, "wall_beige")
            obj = bpy.data.objects.new("_wall", builder.to_mesh())
            shell.objects.link(obj)
    # laje entre andares, com o furo da escada
    for room_id, rect in layout.floor_rects(1):
        pass


def look_at_view(name, cam, target, floor):
    dx, dy, dz = target[0] - cam[0], target[1] - cam[1], (target[2] + floor) - (cam[2] + floor)
    yaw = math.degrees(math.atan2(-dx, dy))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return (name, (cam[0], cam[1], cam[2] + floor), yaw, pitch)


def attach_flash(scene, energy=C.FLASH_ENERGY):
    cam = preview._camera(scene, 72.0)
    light_data = bpy.data.lights.new("_PreviewFlash", "SPOT")
    light_data.energy = energy
    light_data.spot_size = math.radians(C.FLASH_SPOT_DEG)
    light_data.spot_blend = 0.25
    light_data.shadow_soft_size = 0.02
    flash = bpy.data.objects.new("_PreviewFlash", light_data)
    scene.collection.objects.link(flash)
    flash.parent = cam
    return flash


def set_room_fill(scene, room, power):
    """Ponto de luz temporário no meio do cômodo, sob o pé-direito (a casca de pré-visualização não tem forro)."""
    if room not in layout.ROOMS:
        room = "garage"
    rect = layout.ROOMS[room].rect
    fill = scene.objects.get("_RoomFill")
    if fill is None:
        data = bpy.data.lights.new("_RoomFill", "POINT")
        fill = bpy.data.objects.new("_RoomFill", data)
        scene.collection.objects.link(fill)
    fill.data.energy = power
    fill.data.shadow_soft_size = 0.4
    fill.location = (*rect.center, layout.LEVEL_Z[layout.ROOMS[room].level] + 2.35)


def item_views(scene):
    """Uma vista por item (lanterna de frente): de cima e de lado para os apoiados, de frente para os presos na parede."""
    views = []
    for obj in sorted(scene.objects, key=lambda o: o.name):
        if not obj.name.startswith(C.N_ITEM):
            continue
        target = obj.matrix_world.translation
        if obj.get("sa_mount") == "wall":
            fx, fy = C.yaw_dir(obj.rotation_euler.z)
            eye = target + Vector((fx * 0.75, fy * 0.75, 0.25))
        else:
            room = layout.ROOMS[obj[C.P_ROOM]].rect
            to_center = Vector((room.center[0] - target.x, room.center[1] - target.y, 0.0))
            to_center = to_center.normalized() if to_center.length > 0.01 else Vector((0.0, -1.0, 0.0))
            eye = target + to_center * 0.75 + Vector((0.0, 0.0, 0.6))
        views.append(look_at_view(obj.name, tuple(eye), tuple(target), 0.0))
    return views


def viewmodel_views(scene):
    """Mostra o viewmodel (oculto no jogo) flutuando no escuro, de lado e de trás da mão."""
    obj = scene.objects[C.OBJ_VIEW_FLASH]
    obj.hide_render = False
    obj.location = (16.0, -4.0, 1.4)
    obj.rotation_euler = (math.radians(90), 0, 0)
    pos = Vector(obj.location)
    return [look_at_view("viewmodel_side", tuple(pos + Vector((0.9, 0.0, 0.0))), tuple(pos), 0.0),
            look_at_view("viewmodel_fp", tuple(pos + Vector((0.12, -0.75, 0.2))), tuple(pos + Vector((0.0, 0.15, 0.0))), 0.0)]


def render_room_views(scene, rooms, args):
    if "items" in rooms or "viewmodel" in rooms:
        extra = item_views(scene) if "items" in rooms else viewmodel_views(scene)
        preview.render_views(scene, extra, os.path.join(OUT_DIR, "v"), "cycles", tuple(args.res), args.samples,
                             0.002 if args.flash else args.fill, args.exposure, args.fov)
        rooms = [r for r in rooms if r not in ("items", "viewmodel")]
    for room in rooms:
        floor = layout.LEVEL_Z[layout.ROOMS[room].level] if room in layout.ROOMS else 0.0
        set_room_fill(scene, "garage" if room == "car" else room, 0.0 if args.flash else args.room_light)
        views = [look_at_view(f"{room}_{suffix}", cam, tgt, floor) for suffix, cam, tgt in VIEWS[room]]
        preview.render_views(scene, views, os.path.join(OUT_DIR, "v"), "cycles", tuple(args.res),
                             args.samples, 0.002 if args.flash else args.fill, args.exposure, 72.0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rooms", default="all")
    ap.add_argument("--fill", type=float, default=0.15)
    ap.add_argument("--flash", action="store_true", help="só a lanterna (mundo quase preto)")
    ap.add_argument("--room-light", type=float, default=520.0, help="potência (W) da luz temporária do cômodo")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--fov", type=float, default=72.0, help="campo de visão; use ~28 nas vistas de itens")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--save", default="")
    args = ap.parse_args(argv)
    args.res = [int(v) for v in args.res.lower().split("x")]
    rooms = list(VIEWS) if args.rooms == "all" else args.rooms.split(",")

    scene = project_build.fresh_scene()
    ctx = BuildContext(scene)
    build_provisional_shell(ctx)
    from sem_alvorada import props
    ctx.stage = "props"
    props.build(ctx)
    bpy.context.view_layer.update()            # matrix_world dos objetos novos, usada nas vistas dos itens
    problems = placement.validate_layout(scene)
    for line in problems:
        print("AVISO:", line)
    print(f"[preview] {len(problems)} avisos de planta")
    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save))
    if args.no_render:
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    if args.flash:
        attach_flash(scene)
    render_room_views(scene, rooms, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
