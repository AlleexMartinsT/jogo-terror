"""Arranjo dos cômodos do andar de cima: quarto do casal, quarto da Emma, banheiro, escritório, corredor."""
import math

from .. import layout
from . import ambient_quartos as ambient, bathroom, bedrooms, decor_quartos as decor, hall_quartos as hall, study_quartos as study
from .lights import make_point_light
from .placement import against_wall, floor_z

WARM_LAMP = (1.0, 0.72, 0.42)


def build_master(ctx):
    """Quarto do casal: cama desfeita do lado de Dan, o lado de Laura intocado, espelho coberto por um lençol."""
    room = "master"
    a = layout.ANCHORS
    yaw = lambda name: math.radians(a[name].yaw_deg)    # noqa: E731

    bedrooms.make_double_bed(ctx, room, a["bed_master"].x, a["bed_master"].y, yaw("bed_master"),
                             anchor="bed_master", z=a["bed_master"].z)
    for name in ("nightstand_flash", "nightstand_clock"):
        bedrooms.make_nightstand(ctx, room, a[name].x, a[name].y, yaw(name), anchor=name, z=a[name].z,
                                 name=name, drawer_open=0.08 if name == "nightstand_clock" else 0.0)
    top = floor_z(room) + 0.55                       # topo dos criados-mudos
    bedrooms.make_bedside_clutter(ctx, room, 0.42, 6.34, top + 0.001, -math.pi / 2, "book")
    bedrooms.make_bedside_clutter(ctx, room, 0.27, 8.60, top + 0.001, 0.0, "pills")
    bedrooms.make_table_lamp(ctx, room, 0.30, 8.90, top + 0.001, 0.0, height=0.42, name="lamp_master")
    clock_x, clock_y, clock_yaw = bedrooms.ALARM_CLOCK_POSE
    bedrooms.make_alarm_clock(ctx, room, clock_x, clock_y, top + 0.001, clock_yaw)
    make_point_light(ctx, room, 1, (0.30, 8.90, top + 0.30), 40.0, WARM_LAMP, "lamp", flicker=0.0)
    # Reflexo do abajur na parede: sem ele o criado-mudo da lanterna (nogueira escura, a 2,7 m do abajur) fica
    # preto e o primeiro objetivo do jogo some no escuro.
    make_point_light(ctx, room, 2, (0.50, 6.25, top + 0.45), 8.0, WARM_LAMP, "lamp", radius=0.08)

    x, y, wall_yaw = against_wall(room, "E", 6.9, 0.5)
    bedrooms.make_dresser(ctx, room, x, y, wall_yaw)
    ambient.make_dresser_top(ctx, room, x, y, floor_z(room) + 0.841, wall_yaw)
    bedrooms.make_wall_mirror(ctx, room, "E", 6.9, 1.55, 0.72, 0.95, draped=True)
    x, y, wall_yaw = against_wall(room, "N", 4.2, 0.6)
    bedrooms.make_wardrobe(ctx, room, x, y, wall_yaw)
    bedrooms.make_laundry_basket(ctx, room, 0.38, 5.42)
    bedrooms.make_bedroom_chair(ctx, room, 2.55, 9.42, math.pi)
    bedrooms.make_bench(ctx, room, 2.78, 7.5, -math.pi / 2)
    bedrooms.make_shoes(ctx, room, 2.15, 6.45, math.radians(-70), "dan")
    bedrooms.make_shoes(ctx, room, 1.75, 8.55, -math.pi / 2, "laura")
    ambient.make_fallen_hangers(ctx, room, 3.35, 9.05)

    decor.make_rug(ctx, room, 2.55, 7.5, 0.0, 2.0, 2.4, "up_rug_persian", curl=0.02, name="rug_master")
    decor.make_floor_decal(ctx, room, 2.95, 6.95, 0.6, 0.7, 0.6, "up_stain", z=floor_z(room), lift=0.02)
    decor.make_framed(ctx, room, "S", 0.95, 1.55, 0.5, 0.4, "up_photo_trio")
    decor.make_framed(ctx, room, "S", 2.75, 1.55, 0.34, 0.44, "up_painting_lake", tilt=-3.0)
    decor.make_framed(ctx, room, "N", 0.75, 1.6, 0.5, 0.4, "up_painting_still")
    decor.make_wall_decal(ctx, room, "N", 3.0, 2.1, 0.9, 0.9, "up_damp", name="damp_master")
    decor.make_wall_decal(ctx, room, "S", 4.6, 2.2, 0.7, 0.7, "up_damp", name="damp_master_2")


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
    bedrooms.make_kid_chair(ctx, room, 2.0, 4.10, 0.0)
    decor.make_rug(ctx, room, 2.7, 2.2, 0.0, 2.0, 1.7, "up_rug_kids", round_shape=True, fringe=False, name="rug_kids")
    bedrooms.make_letter_blocks(ctx, room, 2.15, 1.85)
    bedrooms.make_small_shoes(ctx, room, 1.95, 3.55, -math.pi / 2)
    ambient.make_tea_set(ctx, room, 3.1, 2.45)
    bedrooms.make_night_light(ctx, room, "N", 0.95, 0.3)
    bedrooms.make_mobile(ctx, room, 2.7, 2.2)
    make_point_light(ctx, room, 1, (0.95, 4.86, floor_z(room) + 0.42), 4.0, (1.0, 0.78, 0.55), "lamp")
    decor.make_pinned_sheet(ctx, room, "N", 1.62, 1.18, 0.19, 0.26, "up_crayon_house", tilt=-4)
    decor.make_pinned_sheet(ctx, room, "N", 1.88, 1.30, 0.19, 0.26, "up_crayon_family", tilt=3)
    decor.make_pinned_sheet(ctx, room, "N", 2.34, 1.20, 0.19, 0.26, "up_crayon_rabbit", tilt=-2)
    decor.make_framed(ctx, room, "N", 2.9, 1.5, 0.32, 0.42, "up_painting_barn", border=0.03)
    decor.make_framed(ctx, room, "W", 2.5, 1.5, 0.5, 0.4, "up_photo_portrait", frame="up_paint_cream", border=0.03)
    decor.make_wall_decal(ctx, room, "N", 0.62, 1.95, 0.55, 0.55, "up_glow_stars", name="stars_kids")
    decor.make_wall_decal(ctx, room, "W", 0.9, 2.05, 0.55, 0.55, "up_glow_stars", name="stars_kids_2")


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
    ambient.make_toilet_roll(ctx, room, "E", 2.55, 0.65)
    ambient.make_bath_shelf(ctx, room, "E", 1.55, 1.15)
    bathroom.make_towel_bar(ctx, room, "W", 3.3, 1.25)
    decor.make_rug(ctx, room, 10.75, 1.0, 0.0, 0.5, 0.8, "up_rug_cotton", name="rug_bath")
    decor.make_wall_decal(ctx, room, "W", 2.55, 0.85, 0.36, 0.36, "up_handprints", name="handprints_bath")
    decor.make_wall_decal(ctx, room, "N", 11.2, 2.15, 0.8, 0.8, "up_damp", name="damp_bath")


def build_study(ctx):
    """Escritório de cima: o mapa sobre o caderno, a cadeira caída, papéis do seguro e a estante cheia."""
    room = "study"
    a = layout.ANCHORS["study_desk"]
    study.make_desk(ctx, room, a.x, a.y, math.radians(a.yaw_deg), width=1.4, depth=0.65, anchor="study_desk",
                    name="study_desk", z=a.z)
    top = a.z + 0.76
    study.make_notebook(ctx, room, 10.6, 9.42, top + 0.001, math.radians(8))
    study.make_papers(ctx, room, 10.05, 9.45, top + 0.001, count=5)
    study.make_cold_coffee(ctx, room, 10.40, 9.78, top + 0.001)
    study.make_desk_lamp(ctx, room, 11.15, 9.6, top + 0.001, math.pi)
    make_point_light(ctx, room, 1, (11.1, 9.42, top + 0.34), 30.0, WARM_LAMP, "lamp", flicker=0.15)
    study.make_swivel_chair(ctx, room, 10.0, 7.6, math.radians(160), fallen=True)
    study.make_bookcase(ctx, room, "W", 6.4, width=1.6, name="bookcase_study")
    study.make_filing_cabinet(ctx, room, "E", 6.7)
    study.make_globe(ctx, room, 11.5, 7.6)
    bathroom.make_trash_bin(ctx, room, 9.75, 9.55, height=0.30, radius=0.14, overflowing=True)
    ambient.make_newspaper_stack(ctx, room, 9.3, 8.0, 0.2)
    ambient.make_desk_tools(ctx, room, 11.25, 9.38, top + 0.001, math.radians(-20))
    study.make_archive_boxes(ctx, room, 9.0, 5.5, 0.2)
    decor.make_rug(ctx, room, 10.55, 8.5, 0.0, 1.5, 1.1, "up_rug_study", name="rug_study")
    decor.make_framed(ctx, room, "N", 8.55, 1.6, 0.34, 0.44, "up_photo_father_child")
    study.make_wall_map(ctx, room, "S", 9.3, 1.5)
    decor.make_wall_decal(ctx, room, "E", 9.0, 2.1, 0.9, 0.9, "up_damp", name="damp_study")
    decor.make_framed(ctx, room, "S", 8.45, 1.55, 0.3, 0.4, "up_calendar", frame="up_oak", border=0.02)


def build_hall_upper(ctx):
    """Corredor de cima: passadeira, fotos da família, mesinha com o retrato da Emma, flor seca, teias."""
    room = "hall_u"
    hall.make_console(ctx, room, "S", 6.5)
    table_top = floor_z(room) + 0.74
    hall.make_dry_flowers(ctx, room, 6.22, 0.30, table_top)
    hall.make_framed_photo(ctx, room, 6.42, 0.30, table_top, 0.0, "up_photo_portrait", name="frame_emma")
    hall.make_framed_photo(ctx, room, 6.62, 0.27, table_top, 0.3, "up_photo_trio", name="frame_family", width=0.16, height=0.12)
    hall.make_framed_photo(ctx, room, 6.80, 0.30, table_top, -0.2, "up_photo_mother_child", fallen=True, name="frame_fallen")
    hall.make_basket(ctx, room, 7.5, 9.55)
    ambient.make_rain_boots(ctx, room, 5.45, 0.32, 0.25)
    decor.make_rug(ctx, room, 7.0, 5.0, 0.0, 0.75, 7.6, "up_rug_runner", tile_along=True, name="rug_hall")
    for along, art, width in ((3.0, "up_photo_trio", 0.5), (4.4, "up_painting_barn", 0.62), (6.4, "up_photo_mother_child", 0.5)):
        decor.make_framed(ctx, room, "E", along, 1.6, width, width * 0.75, art)
    decor.make_wall_decal(ctx, room, "W", 9.55, 1.15, 0.5, 0.5, "up_handprints", name="handprints_hall")
    for wall, along, flip in (("S", 5.15, False), ("S", 7.85, True), ("N", 7.85, False), ("N", 5.15, True)):
        decor.make_cobweb(ctx, room, wall, along, 2.6, 0.38, flip_u=flip)
