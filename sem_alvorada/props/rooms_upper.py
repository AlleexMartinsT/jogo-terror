"""Arranjo dos cômodos do andar de cima: quarto do casal, quarto da Emma, banheiro, escritório, corredor."""
import math

from .. import layout
from . import bathroom, bedrooms, furniture, office
from .lights import make_point_light
from .placement import against_wall, floor_z

WARM_LAMP = (1.0, 0.72, 0.42)


def build_master(ctx):
    """Quarto do casal: cama desarrumada, o lado da Laura vazio, espelho coberto por um lençol."""
    room = "master"
    a = layout.ANCHORS
    yaw = lambda name: math.radians(a[name].yaw_deg)    # noqa: E731

    bedrooms.make_double_bed(ctx, room, a["bed_master"].x, a["bed_master"].y, yaw("bed_master"),
                             anchor="bed_master", z=a["bed_master"].z)
    for name in ("nightstand_flash", "nightstand_clock"):
        bedrooms.make_nightstand(ctx, room, a[name].x, a[name].y, yaw(name), anchor=name, z=a[name].z,
                                 name=name)
    top = floor_z(room) + 0.55                       # topo dos criados-mudos
    bedrooms.make_bedside_clutter(ctx, room, 0.42, 6.34, top + 0.001, -math.pi / 2, "book")
    bedrooms.make_bedside_clutter(ctx, room, 0.27, 8.60, top + 0.001, 0.0, "pills")
    bedrooms.make_table_lamp(ctx, room, 0.30, 8.90, top + 0.001, 0.0, height=0.42, name="lamp_master")
    bedrooms.make_alarm_clock(ctx, room, 0.44, 8.74, top + 0.001, -math.pi / 2)
    make_point_light(ctx, room, 1, (0.30, 8.90, top + 0.30), 40.0, WARM_LAMP, "lamp", flicker=0.0)

    x, y, wall_yaw = against_wall(room, "E", 6.9, 0.5)
    bedrooms.make_dresser(ctx, room, x, y, wall_yaw)
    bedrooms.make_wall_mirror(ctx, room, "E", 6.9, 1.55, 0.72, 0.95, draped=True)
    x, y, wall_yaw = against_wall(room, "N", 4.2, 0.6)
    bedrooms.make_wardrobe(ctx, room, x, y, wall_yaw)
    bedrooms.make_laundry_basket(ctx, room, 0.38, 5.42)
    furniture.make_chair(ctx, room, 2.55, 9.42, math.pi, cushion="fabric_red")

    furniture.make_rug(ctx, room, 2.55, 7.5, 0.0, 2.0, 2.4, "rug_red")
    furniture.make_floor_decal(ctx, room, 2.95, 6.95, 0.6, 0.7, 0.6, "stain_dark", z=floor_z(room), lift=0.02)
    furniture.make_picture(ctx, room, "S", 0.95, 1.55, 0.5, 0.4, "photo_trio")
    furniture.make_picture(ctx, room, "S", 2.75, 1.55, 0.34, 0.44, "painting_lake")
    furniture.make_picture(ctx, room, "N", 0.75, 1.6, 0.5, 0.4, "painting_still")


def build_kids(ctx):
    """Quarto da Emma: tudo no lugar, a cama feita, a luz noturna ainda acesa."""
    room = "kids"
    a = layout.ANCHORS
    bedrooms.make_kids_bed(ctx, room, a["kids_bed"].x, a["kids_bed"].y, math.radians(a["kids_bed"].yaw_deg),
                           anchor="kids_bed", z=a["kids_bed"].z)
    bedrooms.make_toy_shelf(ctx, room, "S", 0.75)
    bedrooms.make_toy_chest(ctx, room, "S", 4.0)
    bedrooms.make_doll_house(ctx, room, "E", 2.75)
    bedrooms.make_kid_desk(ctx, room, "N", 2.0)
    furniture.make_chair(ctx, room, 2.0, 4.10, 0.0, style="kid", tucked=True)
    furniture.make_rug(ctx, room, 2.7, 2.2, 0.0, 2.0, 1.7, "rug_blue", round_shape=True)
    bedrooms.make_letter_blocks(ctx, room, 2.15, 1.85)
    bedrooms.make_small_shoes(ctx, room, 1.95, 3.55, -math.pi / 2)
    bedrooms.make_night_light(ctx, room, "N", 0.95, 0.3)
    make_point_light(ctx, room, 1, (0.95, 4.86, floor_z(room) + 0.42), 4.0, (1.0, 0.78, 0.55), "lamp")
    furniture.make_picture(ctx, room, "N", 1.65, 1.45, 0.32, 0.42, "painting_still")
    furniture.make_picture(ctx, room, "N", 2.35, 1.45, 0.32, 0.42, "painting_barn")
    furniture.make_picture(ctx, room, "W", 2.5, 1.5, 0.5, 0.4, "photo_portrait")


def build_bath(ctx):
    """Banheiro: banheira cheia de água parada, espelho rachado, marcas de mão pequenas perto da porta."""
    room = "bath"
    a = layout.ANCHORS["bath_sink"]
    bathroom.make_vanity(ctx, room, a.x, a.y, math.radians(a.yaw_deg), anchor="bath_sink", z=a.z)
    bathroom.make_medicine_cabinet(ctx, room, "N", 9.1, 1.3)
    bathroom.make_bathtub(ctx, room, "E", 1.0)
    bathroom.make_shower_curtain(ctx, room, 11.14, 0.16, 1.84, 0.9)
    bathroom.make_toilet(ctx, room, "E", 3.2)
    bathroom.make_trash_bin(ctx, room, 11.62, 2.4)
    bathroom.make_towel_bar(ctx, room, "W", 3.3, 1.25)
    furniture.make_rug(ctx, room, 10.75, 1.0, 0.0, 0.45, 0.75, "rug_runner")
    furniture.make_wall_decal(ctx, room, "W", 2.55, 0.85, 0.36, 0.36, "handprints")


def build_study(ctx):
    """Escritório de cima: o mapa sobre o caderno, a cadeira caída, papéis e a estante cheia."""
    room = "study"
    a = layout.ANCHORS["study_desk"]
    office.make_desk(ctx, room, a.x, a.y, math.radians(a.yaw_deg), width=1.4, depth=0.65, anchor="study_desk",
                     name="study_desk", z=a.z)
    top = a.z + 0.76
    office.make_notebook(ctx, room, 10.6, 9.42, top + 0.001, math.radians(8))
    office.make_papers(ctx, room, 10.05, 9.45, top + 0.001, count=5)
    office.make_desk_lamp(ctx, room, 11.15, 9.6, top + 0.001, math.pi)
    make_point_light(ctx, room, 1, (11.1, 9.42, top + 0.34), 30.0, WARM_LAMP, "lamp", flicker=0.15)
    furniture.make_chair(ctx, room, 10.0, 8.15, math.radians(160), style="office", fallen=True, cushion="leather_brown")
    office.make_bookcase(ctx, room, "W", 6.4, width=1.6, name="bookcase_study")
    office.make_filing_cabinet(ctx, room, "E", 6.7)
    office.make_globe(ctx, room, 11.5, 7.6)
    furniture.make_box_stack(ctx, room, 9.0, 5.5, 0.2, [(1.0, 0, 0, 0), (0.8, 0.03, 0.0, 16)])
    furniture.make_rug(ctx, room, 10.55, 8.5, 0.0, 1.5, 1.1, "rug_blue")
    furniture.make_picture(ctx, room, "N", 8.55, 1.6, 0.34, 0.44, "photo_father_child")
    furniture.make_picture(ctx, room, "S", 9.3, 1.6, 0.3, 0.4, "calendar", frame="wood_mid")


def build_hall_upper(ctx):
    """Corredor de cima: passadeira, fotos da família, mesinha com o retrato da Emma, marcas de mão."""
    room = "hall_u"
    furniture.make_side_table(ctx, room, "S", 6.5, width=0.8, depth=0.32)
    table_top = floor_z(room) + 0.74
    furniture.make_photo_frame(ctx, room, 6.3, 0.3, table_top, 0.0, "photo_portrait", name="frame_emma")
    furniture.make_basket(ctx, room, 7.5, 9.55)
    furniture.make_rug(ctx, room, 7.0, 5.0, 0.0, 0.75, 7.6, "rug_runner", tile_along=True)
    for along, art, width in ((3.0, "photo_trio", 0.5), (4.4, "painting_barn", 0.62), (6.4, "photo_mother_child", 0.5)):
        furniture.make_picture(ctx, room, "E", along, 1.6, width, width * 0.75, art)
    furniture.make_wall_decal(ctx, room, "W", 9.55, 1.15, 0.5, 0.5, "handprints")
