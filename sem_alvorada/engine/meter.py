"""Picos do medidor de som: o pico segura um instante e depois decai devagar."""

HOLD_SECONDS = 0.6
FALL_PER_SECOND = 0.45


class MeterPeaks:
    def __init__(self, keys=("player", "ambient", "entity")):
        self.values = {key: 0.0 for key in keys}
        self._hold = {key: 0.0 for key in keys}

    def update(self, dt, levels):
        for key in self.values:
            level = levels.get(key, 0.0)
            if level >= self.values[key]:
                self.values[key], self._hold[key] = level, HOLD_SECONDS
            elif self._hold[key] > 0:
                self._hold[key] -= dt
            else:
                self.values[key] = max(level, self.values[key] - FALL_PER_SECOND * dt)

    def reset(self):
        for key in self.values:
            self.values[key] = self._hold[key] = 0.0
