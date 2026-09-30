"""Dublê do módulo `aud` para testar o AudioEngine sem placa de som.

Imita só o que o engine usa: `Sound.file/cache/lowpass`, `Device.play/lock/unlock/stopAll`, as
propriedades 3D de `Handle` e do `Device`. Registra tudo o que aconteceu em `Device.plays`.
Com `spatial=False` as propriedades 3D lançam `AudError`, como o `aud.Device()` do Blender
sem OpenAL ("Device is not a 3D device!").
"""
import os

DISTANCE_MODEL_INVERSE_CLAMPED = 4


class AudError(Exception):
    """Equivalente de `aud.error`."""


class FakeSound:
    def __init__(self, path, filters=()):
        self.path = path
        self.filters = tuple(filters)
        self.cached = False

    def cache(self):
        clone = FakeSound(self.path, self.filters)
        clone.cached = True
        return clone

    def lowpass(self, frequency, Q=0.5):   # noqa: N803 - mesmo nome do aud
        return FakeSound(self.path, self.filters + (("lowpass", float(frequency)),))

    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def cutoff(self):
        return min((f for kind, f in self.filters if kind == "lowpass"), default=None)


class _SoundFactory:
    @staticmethod
    def file(path):
        if not os.path.isfile(path):
            raise AudError(f"arquivo não encontrado: {path}")
        return FakeSound(path)


class FakeHandle:
    def __init__(self, device, sound):
        self._device = device
        self.sound = sound
        self.status = True
        self.stopped = False
        self._values = {"volume": 1.0, "pitch": 1.0, "loop_count": 0, "position": 0.0, "keep": False}
        self._spatial_values = {"location": (0.0, 0.0, 0.0), "relative": False, "attenuation": 1.0,
                                "distance_reference": 1.0, "distance_maximum": 3.4e38}

    def stop(self):
        self.stopped, self.status = True, False
        return True

    def __getattr__(self, name):
        values, spatial = self.__dict__.get("_values", {}), self.__dict__.get("_spatial_values", {})
        if name in values:
            return values[name]
        if name in spatial:
            self._require_spatial()
            return spatial[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name.startswith("_") or name in ("sound", "status", "stopped"):
            object.__setattr__(self, name, value)
        elif name in self._values:
            self._values[name] = value
        elif name in self._spatial_values:
            self._require_spatial()
            self._spatial_values[name] = value
        else:
            object.__setattr__(self, name, value)

    def _require_spatial(self):
        if not self._device.spatial:
            raise AudError("Device is not a 3D device!")


class FakeDevice:
    def __init__(self, spatial=True, rate=48000.0):
        self.spatial = spatial
        self.rate = rate
        self.volume = 1.0
        self.plays = []
        self.lock_depth = 0
        self.stop_all_calls = 0
        self._listener = {"listener_location": (0.0, 0.0, 0.0), "listener_orientation": (1.0, 0.0, 0.0, 0.0),
                          "distance_model": 0, "doppler_factor": 1.0, "speed_of_sound": 343.3}

    def play(self, sound, keep=False):
        handle = FakeHandle(self, sound)
        self.plays.append(handle)
        return handle

    def lock(self):
        self.lock_depth += 1

    def unlock(self):
        self.lock_depth -= 1

    def stopAll(self):     # noqa: N802
        self.stop_all_calls += 1
        for handle in self.plays:
            handle.stop()

    def __getattr__(self, name):
        listener = self.__dict__.get("_listener", {})
        if name in listener:
            if not self.spatial:
                raise AudError("Device is not a 3D device!")
            return listener[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name != "_listener" and name in self.__dict__.get("_listener", {}):
            if not self.spatial:
                raise AudError("Device is not a 3D device!")
            self._listener[name] = value
        else:
            object.__setattr__(self, name, value)

    def alive(self):
        return [h for h in self.plays if not h.stopped]


class FakeAud:
    """Substitui `import aud`. `has_device=False` reproduz o Blender sem saída de áudio (rate 0)."""
    error = AudError
    DISTANCE_MODEL_INVERSE_CLAMPED = DISTANCE_MODEL_INVERSE_CLAMPED
    Sound = _SoundFactory

    def __init__(self, spatial=True, has_device=True):
        self._spatial, self._has_device = spatial, has_device
        self.devices = []

    def Device(self):      # noqa: N802
        device = FakeDevice(self._spatial, rate=48000.0 if self._has_device else 0.0)
        self.devices.append(device)
        return device
