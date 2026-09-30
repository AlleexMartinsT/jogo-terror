"""Arranjo dos cômodos do térreo e da garagem: sala, escritório, entrada, jantar, cozinha, garagem."""
import math

from .. import conventions as C
from .. import layout
from . import bathroom, bedrooms, car, dining, entrance, furniture, garage, kitchen, living, office
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
    living.make_tv_console(ctx, room, a["tv_living"].x, a["tv_living"].y, _anchor_yaw("tv_living"), anchor="tv_living",
                           z=a["tv_living"].z)
    living.make_grandfather_clock(ctx, room, a["grandfather_clock"].x, a["grandfather_clock"].y,
                                  _anchor_yaw("grandfather_clock"), anchor="grandfather_clock", z=a["grandfather_clock"].z)
    living.make_coffee_table(ctx, room, 3.05, 4.15, -math.pi / 2)
    living.make_armchair(ctx, room, 3.3, 1.6, C.dir_yaw(4.7 - 3.3, 3.9 - 1.6))
    living.make_floor_lamp(ctx, room, 0.45, 4.35)
    make_point_light(ctx, room, 2, (0.45, 4.35, 1.45), 25.0, WARM_LAMP, "lamp")
    make_point_light(ctx, room, 1, (4.15, 3.9, 0.85), 14.0, TV_BLUE, "tv", flicker=0.7, radius=0.15)
    office.make_bookcase(ctx, room, "W", 5.25, width=1.2, height=1.75, shelves=4, name="bookcase_living")
    furniture.make_rug(ctx, room, 2.95, 3.9, 0.0, 2.5, 2.3, "rug_red")
    furniture.make_floor_decal(ctx, room, 3.55, 3.2, 0.4, 0.8, 0.7, "stain_dark")
    furniture.make_photo_frame(ctx, room, 4.65, 4.3, 0.552, math.pi / 2, "photo_portrait", fallen=True, name="frame_fallen_living")
    furniture.make_picture(ctx, room, "S", 4.0, 1.5, 0.5, 0.4, "photo_trio")
    furniture.make_picture(ctx, room, "N", 0.8, 1.5, 0.5, 0.36, "painting_lake")
    furniture.make_picture(ctx, room, "E", 5.25, 1.5, 0.4, 0.5, "photo_mother_child")
    furniture.make_picture(ctx, room, "E", 2.6, 1.55, 0.6, 0.42, "painting_barn")


def build_den(ctx):
    """Escritório do térreo: a escrivaninha do Dan com a chave, o quadro de cortiça e os cafés esquecidos."""
    room = "den"
    a = layout.ANCHORS["desk_den"]
    office.make_desk(ctx, room, a.x, a.y, _anchor_yaw("desk_den"), width=1.6, depth=0.7, anchor="desk_den",
                     name="desk_den", z=a.z)
    top = 0.76
    office.make_crt_computer(ctx, room, 1.2, 9.5, top, math.radians(200))
    office.make_desk_lamp(ctx, room, 2.28, 9.55, top, math.pi)
    make_point_light(ctx, room, 1, (2.22, 9.4, top + 0.34), 28.0, WARM_LAMP, "lamp", flicker=0.1)
    office.make_papers(ctx, room, 1.62, 9.45, top + 0.001, count=6, spread=0.18)
    for cx, cy in ((1.75, 9.65), (2.42, 9.25), (0.98, 9.28)):
        furniture.make_cup(ctx, room, cx, cy, top)
    furniture.make_chair(ctx, room, 1.75, 8.6, 0.25, style="office", cushion="fabric_gray")
    furniture.make_picture(ctx, room, "W", 9.45, 1.5, 0.75, 0.95, "cork_clippings", frame="wood_mid")
    office.make_bookcase(ctx, room, "E", 7.2, width=1.6, height=1.6, shelves=4, name="bookcase_den")
    office.make_filing_cabinet(ctx, room, "S", 3.4)
    living.make_armchair(ctx, room, 0.85, 6.9, C.dir_yaw(1.6, 1.6), fabric="fabric_red", worn=True)
    furniture.make_box_stack(ctx, room, 4.25, 6.4, 0.3, [(1.0, 0, 0, 0), (0.85, 0.0, 0.03, 12), (0.7, 0.02, 0.0, -8)])
    furniture.make_rug(ctx, room, 2.4, 8.0, 0.0, 2.0, 1.5, "rug_blue")
    office.make_papers(ctx, room, 2.9, 8.5, 0.014, count=5, spread=0.3)
    furniture.make_picture(ctx, room, "N", 4.3, 1.55, 0.4, 0.5, "painting_still")
    furniture.make_picture(ctx, room, "S", 3.4, 1.6, 0.34, 0.3, "photo_father_child")


def build_hall_ground(ctx):
    """Entrada: calçados de toda a família, o casaco amarelo da Emma e as fotos subindo a escada."""
    room = "hall_g"
    entrance.make_shoe_rack(ctx, room, "S", 5.72)
    entrance.make_umbrella_stand(ctx, room, 5.21, 0.33)
    entrance.make_coat_rack(ctx, room, 7.38, 0.48)
    furniture.make_side_table(ctx, room, "E", 5.2, width=1.1, depth=0.38, height=0.82, name="hall_console")
    living.make_telephone(ctx, room, 7.75, 4.85, 0.82, math.pi / 2)
    furniture.make_photo_frame(ctx, room, 7.76, 5.6, 0.82, math.pi / 2 + 0.1, "photo_trio")
    bedrooms.make_wall_mirror(ctx, room, "E", 5.2, 1.55, 0.7, 0.9)
    furniture.make_side_table(ctx, room, "N", 6.5, width=0.8, depth=0.32, height=0.74, name="hall_plant_table")
    entrance.make_dead_plant(ctx, room, 6.5, 9.7, 0.74)
    arts = ("photo_trio", "photo_mother_child", "painting_lake", "photo_father_child", "photo_portrait", "painting_barn", "photo_trio")
    for (y, height), art in zip(entrance.stair_photo_slots(), arts):
        furniture.make_picture(ctx, room, "W", y, height, 0.36, 0.28, art)
    furniture.make_rug(ctx, room, 6.9, 0.7, 0.0, 0.9, 0.6, "rug_runner")


def build_dining(ctx):
    """Jantar: a mesa posta, cadeiras fora do lugar, um prato quebrado e a cadeirinha rosa da Emma."""
    room = "dining"
    dining.make_dining_table(ctx, room, 10.45, 2.5)
    furniture.make_rug(ctx, room, 10.45, 2.5, 0.0, 2.7, 1.9, "rug_blue")
    for x in (9.95, 10.95):
        furniture.make_chair(ctx, room, x, 1.78, 0.0, cushion="fabric_red")
    furniture.make_chair(ctx, room, 9.95, 3.22, math.pi, cushion="plush_pink")
    furniture.make_chair(ctx, room, 10.98, 3.50, math.pi + 0.55, cushion="fabric_red")
    furniture.make_chair(ctx, room, 9.25, 2.5, -math.pi / 2, cushion="fabric_red")
    furniture.make_chair(ctx, room, 11.62, 2.5, math.pi / 2, cushion="fabric_red")
    dining.make_sideboard(ctx, room, "E", 1.2)
    furniture.make_photo_frame(ctx, room, 11.72, 0.75, 0.85, math.pi / 2, "photo_mother_child", fallen=True,
                               name="frame_fallen_dining")
    dining.make_broken_plate(ctx, room, 9.7, 1.15, 0.6)
    furniture.make_picture(ctx, room, "E", 1.2, 1.55, 0.9, 0.6, "painting_lake")
    furniture.make_picture(ctx, room, "N", 8.55, 1.5, 0.4, 0.5, "photo_trio")
    furniture.make_picture(ctx, room, "N", 11.5, 1.5, 0.36, 0.46, "painting_still")
    furniture.make_picture(ctx, room, "W", 3.8, 1.5, 0.5, 0.4, "painting_barn")


def build_kitchen(ctx):
    """Cozinha: louça por lavar, o zumbido da geladeira coberta de desenhos e o frigobar com o post-it."""
    room = "kitchen"
    a = layout.ANCHORS
    kitchen.make_fridge(ctx, room, a["fridge"].x, a["fridge"].y, _anchor_yaw("fridge"), anchor="fridge", z=a["fridge"].z)
    kitchen.make_sink_unit(ctx, room, a["kitchen_counter"].x, a["kitchen_counter"].y, _anchor_yaw("kitchen_counter"),
                           anchor="kitchen_counter", z=a["kitchen_counter"].z)
    kitchen.make_stove(ctx, room, "E", 7.9)
    kitchen.make_corner_counter(ctx, room, 10.85, 8.32, 11.875, 9.875)
    top = kitchen.COUNTER_HEIGHT
    kitchen.make_microwave(ctx, room, 11.58, 8.8, top, math.pi / 2)
    kitchen.make_coffee_maker(ctx, room, 11.63, 9.62, top, math.pi)
    kitchen.make_base_cabinet(ctx, room, "W", 5.62, 0.9, depth=0.55, name="counter_west_a")
    kitchen.make_mini_fridge(ctx, room, "W", 6.40)
    kitchen.make_base_cabinet(ctx, room, "W", 7.16, 0.88, depth=0.55, name="counter_west_b")
    kitchen.make_wall_cabinets(ctx, room, "W", 6.4, 2.4)
    kitchen.make_wall_cabinets(ctx, room, "N", 9.78, 0.44, ajar=False)
    kitchen.make_kitchen_table(ctx, room, 9.95, 6.9)
    furniture.make_chair(ctx, room, 9.95, 7.55, math.pi, cushion="fabric_red", tucked=True)
    furniture.make_chair(ctx, room, 9.95, 6.25, 0.0, cushion="fabric_red", tucked=True)
    bathroom.make_trash_bin(ctx, room, 8.4, 7.8, height=0.5, radius=0.17, overflowing=True)
    furniture.make_picture(ctx, room, "S", 8.55, 1.5, 0.3, 0.4, "calendar", frame="wood_mid")


def build_garage(ctx):
    """Garagem: o carro batido, a bancada com o que sobrou do Dan, a bicicleta rosa e a caixa com o nome dela."""
    room = "garage"
    car.make_car(ctx)
    a = layout.ANCHORS["workbench"]
    garage.make_workbench(ctx, room, a.x, a.y, _anchor_yaw("workbench"), anchor="workbench", z=a.z)
    garage.make_tool_panel(ctx, room, "E", 1.95, 1.65)
    garage.make_garage_shelves(ctx, room, "N", 16.15)
    garage.make_chest_freezer(ctx, room, "W", 1.6)
    garage.make_kids_bicycle(ctx, room, 12.4, 3.25, 0.0)
    garage.make_water_heater(ctx, room, 18.05, 6.5)
    garage.make_lawn_mower(ctx, room, 17.85, 1.3, math.radians(10))
    furniture.make_box_stack(ctx, room, 12.55, 0.6, 0.0, [(1.0, 0, 0, 0), (0.9, 0.0, 0.0, 8), (0.8, 0.03, 0.0, -6)],
                             label="cardboard_emma")
    furniture.make_box_stack(ctx, room, 12.5, 4.3, 0.0, [(0.9, 0, 0, 0), (0.7, 0.0, 0.0, 14)], label="cardboard_toys")
    furniture.make_floor_decal(ctx, room, 15.35, 1.5, 0.3, 1.1, 0.9, "stain_oil", lift=0.006)
