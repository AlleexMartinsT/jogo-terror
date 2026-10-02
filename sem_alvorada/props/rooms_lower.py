"""Arranjo dos cômodos do térreo e da garagem: sala, escritório, entrada, jantar, cozinha, garagem."""
import math

from .. import conventions as C
from .. import layout
from . import ambience, bookcase, car, clock, den, dining, entrance, furniture, living, phone, tv
from .lights import make_point_light

WARM_LAMP = (1.0, 0.72, 0.42)
TV_BLUE = (0.62, 0.78, 1.0)


def _anchor_yaw(name):
    return math.radians(layout.ANCHORS[name].yaw_deg)


def build_living(ctx):
    """Sala: a TV chiando para um sofá vazio, o relógio de pé parado, um retrato de bruços no console."""
    room = "living"
    a = layout.ANCHORS
    living.make_sofa(ctx, room, a["sofa_living"].x, a["sofa_living"].y, _anchor_yaw("sofa_living"), anchor="sofa_living",
                     z=a["sofa_living"].z)
    tv.make_tv_console(ctx, room, a["tv_living"].x, a["tv_living"].y, _anchor_yaw("tv_living"), anchor="tv_living",
                       z=a["tv_living"].z)
    clock.make_grandfather_clock(ctx, room, a["grandfather_clock"].x, a["grandfather_clock"].y,
                                 _anchor_yaw("grandfather_clock"), anchor="grandfather_clock", z=a["grandfather_clock"].z)
    living.make_coffee_table(ctx, room, 3.05, 4.15, -math.pi / 2)
    living.make_armchair(ctx, room, 3.3, 1.6, C.dir_yaw(4.7 - 3.3, 3.9 - 1.6))
    living.make_floor_lamp(ctx, room, 0.45, 4.35)
    make_point_light(ctx, room, 2, (0.45, 4.35, 1.45), 25.0, WARM_LAMP, "lamp")
    make_point_light(ctx, room, 1, (4.15, 3.9, 0.85), 14.0, TV_BLUE, "tv", flicker=0.7, radius=0.15)
    bookcase.make_bookcase(ctx, room, "W", 5.25, width=1.2, height=1.75, shelves=4, name="bookcase_living")
    furniture.make_rug(ctx, room, 2.95, 3.9, 0.0, 2.5, 2.3, "rug_living")
    furniture.make_floor_decal(ctx, room, 3.55, 3.2, 0.4, 0.8, 0.7, "stain_dark")
    furniture.make_photo_frame(ctx, room, 4.65, 4.3, 0.552, math.pi / 2, "photo_portrait", fallen=True, name="frame_fallen_living")
    furniture.make_picture(ctx, room, "S", 4.0, 1.5, 0.5, 0.4, "photo_trio")
    furniture.make_picture(ctx, room, "N", 0.8, 1.5, 0.5, 0.36, "painting_lake")
    furniture.make_picture(ctx, room, "E", 5.25, 1.5, 0.4, 0.5, "photo_mother_child")
    furniture.make_picture(ctx, room, "E", 2.6, 1.55, 0.6, 0.42, "painting_barn")
    ambience.make_newspaper(ctx, room, 2.24, 3.9, 0.472, 0.35)
    ambience.make_slippers(ctx, room, 2.68, 3.12, math.radians(100), z=0.015)
    ambience.make_toy_blocks(ctx, room, 3.85, 2.8, z=0.015)
    ambience.make_pill_and_glass(ctx, room, 4.62, 3.42, 0.55)
    entrance.make_dead_plant(ctx, room, 4.6, 5.5, 0.0, height=0.85)


def build_den(ctx):
    """Escritório do térreo: a escrivaninha do Dan com a chave, o quadro de cortiça e os cafés esquecidos."""
    room = "den"
    a = layout.ANCHORS["desk_den"]
    den.make_desk(ctx, room, a.x, a.y, _anchor_yaw("desk_den"), width=1.6, depth=0.7, anchor="desk_den",
                  name="desk_den", z=a.z)
    top = 0.76
    den.make_crt_computer(ctx, room, 1.2, 9.58, top, math.radians(200))
    den.make_bankers_lamp(ctx, room, 2.28, 9.55, top, math.pi)
    make_point_light(ctx, room, 1, (2.22, 9.4, top + 0.34), 28.0, WARM_LAMP, "lamp", flicker=0.1)
    den.make_paper_sheets(ctx, room, 1.62, 9.45, top + 0.001, count=6, spread=0.18)
    for cx, cy in ((1.75, 9.68), (2.45, 9.27), (1.52, 9.27)):
        furniture.make_cup(ctx, room, cx, cy, top)
    phone.make_telephone(ctx, room, 2.36, 9.76, top, math.pi)
    ambience.make_pen_cup(ctx, room, 1.5, 9.8, top)
    ambience.make_pill_and_glass(ctx, room, 1.92, 9.8, top)
    furniture.make_chair(ctx, room, 1.75, 8.6, 0.25, style="office", cushion="leather_brown")
    den.make_cork_board(ctx, room, "W", 9.5, 1.5)
    bookcase.make_bookcase(ctx, room, "E", 7.2, width=1.6, height=1.6, shelves=4, name="bookcase_den")
    den.make_filing_cabinet(ctx, room, "S", 3.4)
    ambience.make_whisky_set(ctx, room, 3.28, 6.38, 0.78)
    ambience.make_folder_stack(ctx, room, 3.58, 6.36, 0.78)
    ambience.make_wastebasket(ctx, room, 2.78, 9.5)
    living.make_armchair(ctx, room, 0.85, 6.9, C.dir_yaw(1.6, 1.6), fabric="fabric_red", worn=True)
    furniture.make_box_stack(ctx, room, 4.25, 6.4, 0.3, [(1.0, 0, 0, 0), (0.85, 0.0, 0.03, 12), (0.7, 0.02, 0.0, -8)])
    furniture.make_rug(ctx, room, 2.4, 8.0, 0.0, 2.0, 1.5, "rug_den")
    den.make_paper_sheets(ctx, room, 2.9, 8.5, 0.014, count=5, spread=0.3)
    furniture.make_picture(ctx, room, "N", 4.3, 1.55, 0.4, 0.5, "painting_still")
    furniture.make_picture(ctx, room, "S", 3.4, 1.6, 0.34, 0.3, "photo_father_child")


def build_hall_ground(ctx):
    """Entrada: calçados de toda a família, o casaco amarelo da Emma e as fotos subindo a escada."""
    room = "hall_g"
    entrance.make_shoe_rack(ctx, room, "S", 5.72)
    entrance.make_umbrella_stand(ctx, room, 5.21, 0.33)
    entrance.make_coat_rack(ctx, room, 7.38, 0.48)
    furniture.make_side_table(ctx, room, "E", 5.2, width=1.1, depth=0.38, height=0.82, name="hall_console")
    phone.make_telephone(ctx, room, 7.75, 4.85, 0.82, math.pi / 2)
    furniture.make_photo_frame(ctx, room, 7.76, 5.6, 0.82, math.pi / 2 + 0.1, "photo_trio")
    entrance.make_hall_mirror(ctx, room, "E", 5.2, 1.55, 0.7, 0.9)
    entrance.make_key_rack(ctx, room, "E", 3.5, 1.4)
    furniture.make_side_table(ctx, room, "N", 6.5, width=0.8, depth=0.32, height=0.74, name="hall_plant_table")
    entrance.make_dead_plant(ctx, room, 6.5, 9.64, 0.74)
    arts = ("photo_trio", "photo_mother_child", "painting_lake", "photo_father_child", "photo_portrait", "painting_barn",
            "photo_trio")
    for (y, height), art in zip(entrance.stair_photo_slots(), arts):
        furniture.make_picture(ctx, room, "W", y, height, 0.36, 0.28, art)
    furniture.make_rug(ctx, room, 6.9, 0.7, 0.0, 0.9, 0.6, "doormat")
    entrance.make_floor_mail(ctx, room, 6.42, 0.52)
    ambience.make_backpack(ctx, room, 5.5, 0.9, 2.4)


def build_dining(ctx):
    """Jantar: a mesa posta para três, a cadeira da Emma puxada para fora, o prato quebrado e as flores que secaram."""
    room = "dining"
    dining.make_dining_table(ctx, room, 10.45, 2.5)
    furniture.make_rug(ctx, room, 10.45, 2.5, 0.0, 2.7, 1.9, "rug_dining")
    for x in (9.95, 10.95):
        furniture.make_chair(ctx, room, x, 1.78, 0.0, cushion="fabric_red", tucked=True)
    furniture.make_chair(ctx, room, 9.95, 3.22, math.pi, cushion="fabric_red", tucked=True)
    furniture.make_chair(ctx, room, 10.98, 3.50, math.pi + 0.55, cushion="plush_pink", booster="plush_yellow")
    furniture.make_chair(ctx, room, 9.3, 2.55, -math.pi / 2 + 0.12, cushion="fabric_red", tucked=True)
    furniture.make_chair(ctx, room, 11.62, 2.5, math.pi / 2, cushion="fabric_red")
    dining.make_sideboard(ctx, room, "E", 1.2)
    furniture.make_photo_frame(ctx, room, 11.72, 0.75, 0.85, math.pi / 2, "photo_mother_child", fallen=True,
                               name="frame_fallen_dining")
    dining.make_broken_plate(ctx, room, 9.7, 1.15, 0.6)
    furniture.make_picture(ctx, room, "E", 3.1, 1.55, 0.9, 0.6, "painting_lake")
    furniture.make_picture(ctx, room, "N", 8.55, 1.5, 0.4, 0.5, "photo_trio")
    furniture.make_picture(ctx, room, "N", 11.5, 1.5, 0.36, 0.46, "painting_still")
    furniture.make_picture(ctx, room, "W", 3.8, 1.5, 0.5, 0.4, "painting_barn")


def build_kitchen(ctx):
    """Cozinha: louça por lavar, o zumbido da geladeira coberta de desenhos e o frigobar com o post-it."""
    from . import kitchen_room
    kitchen_room.build(ctx)


def build_garage(ctx):
    """Garagem: o carro batido, a bancada com o que sobrou do Dan, a bicicleta rosa e a caixa com o nome dela."""
    from . import garage_room
    car.make_car(ctx)
    garage_room.build(ctx)
