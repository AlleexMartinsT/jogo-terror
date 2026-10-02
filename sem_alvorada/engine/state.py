"""Estado persistente da partida: inventário, progresso da história e checkpoint.

Não conhece bpy, portanto pode ser testado e serializado à vontade.
"""
import copy
from dataclasses import dataclass, field

from .. import conventions as C
from .. import story

FLAG_INTRO = "intro_done"
FLAG_BLACKOUT = "blackout_done"
FLAG_COLLECT_DONE = "collect_done"
FLAG_GARAGE_UNLOCKED = "garage_unlocked"
FLAG_ENDING = "ending_done"

# Campos que voltam ao valor do checkpoint em restore(); `deaths` fica de fora de propósito.
_SNAPSHOT_FIELDS = ("has_flashlight", "flashlight_on", "battery", "spare_batteries", "batteries_found",
                    "has_key", "has_map", "collected", "notes_read", "unlocked", "flags")


@dataclass
class GameState:
    has_flashlight: bool = False
    flashlight_on: bool = False
    battery: float = C.BATTERY_MAX
    spare_batteries: int = C.START_SPARE_BATTERIES
    batteries_found: int = 0          # pilhas ENCONTRADAS (contam para o portão), mesmo as já usadas
    has_key: bool = False
    has_map: bool = False
    collected: set = field(default_factory=set)    # ids de Item_* recolhidos: "KEY", "BATTERY_2"...
    notes_read: set = field(default_factory=set)
    unlocked: set = field(default_factory=set)     # travas destrancadas: {"garage"}
    flags: set = field(default_factory=set)
    deaths: int = 0

    def find_flashlight(self):
        """O jogador encontrou a lanterna: ela já foi usada, então a carga não nasce cheia."""
        self.has_flashlight = True
        self.battery = min(self.battery, C.FLASHLIGHT_FOUND_CHARGE)

    def have(self, item_type):
        if item_type == C.ITEM_KEY:
            return int(self.has_key)
        if item_type == C.ITEM_MAP:
            return int(self.has_map)
        if item_type == C.ITEM_BATTERY:
            return self.batteries_found
        return 0

    def collect_status(self):
        """Linhas da lista de coleta do HUD."""
        labels = {C.ITEM_KEY: story.LABEL_KEY, C.ITEM_MAP: story.LABEL_MAP,
                  C.ITEM_BATTERY: story.LABEL_BATTERIES}
        return [{"label": labels[kind], "have": min(self.have(kind), need), "need": need,
                 "done": self.have(kind) >= need}
                for kind, need in C.GATE_REQUIRES.items()]

    def missing_labels(self):
        return [row["label"] for row in self.collect_status() if not row["done"]]

    def collect_complete(self):
        return all(row["done"] for row in self.collect_status())

    def is_locked(self, lock):
        return bool(lock) and lock not in self.unlocked

    @property
    def objective(self):
        """O objetivo é função do estado: continua coerente depois de restore()."""
        if FLAG_ENDING in self.flags:
            return ""
        if FLAG_GARAGE_UNLOCKED in self.flags:
            return story.OBJ_CAR
        if self.collect_complete():
            return story.OBJ_GARAGE
        if FLAG_BLACKOUT in self.flags:
            return story.OBJ_COLLECT
        if self.has_flashlight:
            return story.OBJ_LEAVE_ROOM
        return story.OBJ_TAKE_FLASHLIGHT

    def snapshot(self):
        return {name: copy.deepcopy(getattr(self, name)) for name in _SNAPSHOT_FIELDS}

    def restore(self, snapshot):
        for name in _SNAPSHOT_FIELDS:
            setattr(self, name, copy.deepcopy(snapshot[name]))
