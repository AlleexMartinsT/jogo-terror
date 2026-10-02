"""Mobília dos quartos: casal (Dan e Laura) e da menina (Emma).

Fachada: cada peça mora no módulo do seu conjunto (`bedroom_master`, `bedroom_storage`, `bedroom_extras`,
`bedroom_kids`) e é reexportada aqui, que é o nome que `rooms_upper` e `rooms_lower` conhecem.
"""
from .bedroom_extras import make_bedroom_chair, make_bench, make_laundry_basket, make_shoes, make_wall_mirror  # noqa: F401
from .bedroom_kids import (make_doll_house, make_kid_chair, make_kid_desk, make_kids_bed, make_letter_blocks,  # noqa: F401
                           make_mobile, make_night_light, make_small_shoes, make_toy_chest, make_toy_shelf)
from .bedroom_master import (ALARM_CLOCK_POSE, make_alarm_clock, make_bedside_clutter, make_double_bed,  # noqa: F401
                             make_nightstand, make_table_lamp)
from .bedroom_storage import make_dresser, make_wardrobe  # noqa: F401
