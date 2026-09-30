"""Reprodução 3D dos sons sobre o módulo `aud` do Blender.

O engine nunca lança exceção para o jogo: sem `aud`, sem placa de som ou com qualquer erro do
dispositivo, ele passa a ser um no-op silencioso e registra o motivo UMA vez no log.

Oclusão: um som posicional cujo caminho até o ouvinte passa por porta fechada ou por outro
andar é tocado numa versão `lowpass` do WAV (mais abafada) e com o volume reduzido. O caminho
é o mesmo do sistema de ruído (grafo de cômodos), então o que a entidade "ouve pouco" o
jogador também ouve abafado.
"""
import logging
import math
import os
import random
import time
from dataclasses import dataclass

from .. import AUDIO_DIR
from . import noise as noise_module

LOG = logging.getLogger("sem_alvorada.audio")

# Distância de referência (m) em que o som toca a 100%: sons enormes carregam mais longe.
_REFERENCE_DISTANCE = {
    "default": 1.5, "ent_scream": 7.0, "ent_stinger": 8.0, "ent_door_break": 5.0, "ent_growl": 4.0,
    "ent_drone": 4.0, "ent_step": 3.0, "door_slam": 4.0, "blackout_thunk": 8.0, "glass_break": 3.5,
    "phone_ring": 3.0, "clock_chime": 3.0, "thud": 3.0, "car_": 4.0, "garage_rollup": 4.0, "death_hit": 8.0,
}
_ROLLOFF = 1.0
_MAX_DISTANCE = 60.0

# Oclusão por camadas: (corte do lowpass em Hz ou None, multiplicador de volume)
OCCLUSION_TIERS = ((None, 1.0), (1600.0, 0.6), (650.0, 0.3))
_CROSSFADE_SECONDS = 0.3
_STOP_FADE_SECONDS = 0.12
_STEP_VARIATIONS = 4


def reference_distance(name):
    for prefix, value in _REFERENCE_DISTANCE.items():
        if prefix != "default" and name.startswith(prefix):
            return value
    return _REFERENCE_DISTANCE["default"]


def listener_quaternion(yaw):
    """Quaternião (w, x, y, z) de um ouvinte olhando para `yaw` no mundo do Blender.

    O aud usa a convenção da câmera do Blender (olha para -Z local, topo em +Y local); para
    olhar horizontalmente giramos 90 graus em X e depois `yaw` em Z (yaw 0 olha para +Y).
    """
    cz, sz = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    c = s = math.sqrt(0.5)
    return (cz * c, cz * s, sz * s, sz * c)


def forward_of(quaternion):
    """Direção para onde o ouvinte olha (a mesma conta do OpenAL no audaspace)."""
    w, x, y, z = quaternion
    return (-2.0 * (w * y + x * z), 2.0 * (x * w - z * y), 2.0 * (x * x + y * y) - 1.0)


def occlusion_tier(path):
    """0 = limpo, 1 = uma porta fechada no caminho, 2 = outro andar ou duas portas ou mais."""
    if path.floors >= 1 or path.closed_doors >= 1.5:
        return 2
    return 1 if path.closed_doors >= 0.25 else 0


@dataclass
class _LoopVoice:
    name: str
    handle: object
    tier: int
    pos: tuple
    volume: float
    pitch: float
    fading_in: object = None        # (handle_novo, progresso) durante troca de camada de oclusão
    fading_out: list = None


class SoundBank:
    """Carrega os WAV pelo `aud`, mantém em cache (buffer na RAM) e cria as versões abafadas sob demanda."""

    def __init__(self, aud, audio_dir):
        self._aud, self._dir = aud, audio_dir
        self._sounds = {}
        self._reported = set()

    def path_of(self, name):
        return os.path.join(self._dir, name + ".wav")

    def get(self, name, tier=0):
        key = (name, tier)
        if key in self._sounds:
            return self._sounds[key]
        sound = None
        if tier == 0:
            sound = self._load(name)
        else:
            base = self.get(name, 0)
            cutoff = OCCLUSION_TIERS[tier][0]
            if base is not None and cutoff:
                sound = self._safely(lambda: base.lowpass(cutoff).cache(), name)
        self._sounds[key] = sound
        return sound

    def _load(self, name):
        return self._safely(lambda: self._aud.Sound.file(self.path_of(name)).cache(), name)

    def _safely(self, make, name):
        try:
            return make()
        except Exception as exc:     # noqa: BLE001 - arquivo ausente ou formato ruim não pode derrubar o jogo
            if name not in self._reported:
                self._reported.add(name)
                LOG.warning("som '%s' indisponível: %s", name, exc)
            return None

    def preload(self, names):
        """Carrega todos os `names`; devolve a lista dos que falharam."""
        return [name for name in names if self.get(name) is None]


class AudioEngine:
    def __init__(self, audio_dir=AUDIO_DIR, enabled=True, aud_module=None, device=None, rng=None,
                 door_openness=None, clock=time.monotonic):
        self.audio_dir = audio_dir
        self._now = clock
        self.enabled = enabled
        self._rng = rng or random.Random(1347)
        self._paths = noise_module.NoiseSystem(door_openness)
        self._aud = None
        self._device = None
        self._bank = None
        self._spatial = False
        self._warned = False
        self._closed = False
        self._master = 1.0
        self._listener_pos = (0.0, 0.0, 0.0)
        self._loops = {}
        self._dying = []
        self._last_variation = {}
        self._clock = None
        if enabled:
            self._open(aud_module, device)

    # ---- inicialização e estado ------------------------------------------
    def _open(self, aud_module, device):
        aud = aud_module or self._import_aud()
        if aud is None:
            return
        self._aud = aud
        self._bank = SoundBank(aud, self.audio_dir)
        try:
            device = device or aud.Device()
            if not getattr(device, "rate", 0):
                raise RuntimeError("nenhum dispositivo de saída de áudio")
            self._device = device
        except Exception as exc:     # noqa: BLE001
            self._disable(f"sem dispositivo de áudio ({exc})")
            return
        self._spatial = self._probe_spatial()
        if not self._spatial:
            LOG.info("dispositivo sem áudio 3D: usando atenuação por volume")

    def _import_aud(self):
        try:
            import bpy  # noqa: F401 - no pacote pip, importar bpy é o que registra o módulo aud
            import aud
            return aud
        except Exception as exc:     # noqa: BLE001
            self._disable(f"módulo aud indisponível ({exc})")
            return None

    def _probe_spatial(self):
        try:
            self._device.listener_location = (0.0, 0.0, 0.0)
            self._device.doppler_factor = 0.0
            self._device.distance_model = self._aud.DISTANCE_MODEL_INVERSE_CLAMPED
            return True
        except Exception:     # noqa: BLE001
            return False

    def _disable(self, reason):
        self._device = None
        if not self._warned:
            self._warned = True
            LOG.warning("áudio desativado: %s", reason)

    @property
    def available(self):
        """True se há um dispositivo de saída funcionando."""
        return self._device is not None and not self._closed

    @property
    def spatial(self):
        return self.available and self._spatial

    def set_door_openness(self, door_openness):
        self._paths.set_door_openness(door_openness)

    def sound(self, name, tier=0):
        """O objeto `aud.Sound` em cache de `name` (`tier` 1 e 2 são as versões abafadas), ou None."""
        return self._bank.get(name, tier) if self._bank else None

    def preload(self, names):
        """Carrega os WAV no cache (mesmo sem dispositivo, se o `aud` existir). Devolve os que falharam."""
        return self._bank.preload(names) if self._bank else list(names)

    # ---- ouvinte e relógio interno -----------------------------------------
    def update_listener(self, pos, yaw):
        """Chame uma vez por quadro: posiciona o ouvinte, reavalia a oclusão e avança os fades."""
        if not self.available:
            return
        self._listener_pos = tuple(float(v) for v in pos)
        self._guard(self._push_listener, yaw)
        self._tick()

    def _push_listener(self, yaw):
        if self._spatial:
            self._device.listener_location = self._listener_pos
            self._device.listener_orientation = listener_quaternion(yaw)

    def _tick(self):
        now = self._now()
        dt = 0.0 if self._clock is None else min(now - self._clock, 0.25)
        self._clock = now
        self._advance_fades(dt)
        for voice in list(self._loops.values()):
            if voice.pos is not None:
                self._refresh_loop_occlusion(voice)

    # ---- oclusão e atenuação --------------------------------------------------
    def _tier_for(self, pos):
        if pos is None:
            return 0
        return occlusion_tier(self._paths.path_between(pos, self._listener_pos))

    def _distance_gain(self, name, pos):
        """Mesma curva do OpenAL (inverse clamped) para dispositivos sem áudio 3D."""
        reference = reference_distance(name)
        distance = min(max(math.dist(pos, self._listener_pos), reference), _MAX_DISTANCE)
        return reference / (reference + _ROLLOFF * (distance - reference))

    def _configure(self, handle, name, pos, volume, pitch, tier):
        gain = OCCLUSION_TIERS[tier][1]
        if pos is None:
            if self._spatial:
                handle.relative = True
                handle.location = (0.0, 0.0, 0.0)
        elif self._spatial:
            handle.relative = False
            handle.location = tuple(pos)
            handle.distance_reference = reference_distance(name)
            handle.attenuation = _ROLLOFF
            handle.distance_maximum = _MAX_DISTANCE
        else:
            gain *= self._distance_gain(name, pos)
        handle.volume = max(volume * gain, 0.0)
        handle.pitch = pitch

    def _start(self, name, pos, volume, pitch, tier, looping):
        sound = self._bank.get(name, tier) or (self._bank.get(name, 0) if tier else None)
        if sound is None:
            return None
        self._device.lock()
        try:
            handle = self._device.play(sound)
            self._configure(handle, name, pos, volume, pitch, tier)
            if looping:
                handle.loop_count = -1
        finally:
            self._device.unlock()
        return handle

    def _guard(self, action, *args):
        """Executa uma chamada ao aud; qualquer erro desativa o áudio em vez de derrubar o jogo."""
        try:
            return action(*args)
        except Exception as exc:     # noqa: BLE001
            self._disable(f"erro do dispositivo ({exc})")
            return None

    # ---- API pública ---------------------------------------------------------
    def play(self, name, pos=None, volume=1.0, pitch=1.0):
        """Toca um som uma vez. Com `pos` (x, y, z) é posicional; sem `pos` toca "dentro da cabeça"."""
        if not self.available:
            return None
        return self._guard(lambda: self._start(name, pos, volume, pitch, self._tier_for(pos), False))

    def loop(self, key, name, pos=None, volume=1.0, pitch=1.0):
        """Cria ou atualiza um loop persistente identificado por `key`."""
        if not self.available:
            return None
        self._guard(self._loop_impl, key, name, pos, volume, pitch)

    def _loop_impl(self, key, name, pos, volume, pitch):
        voice = self._loops.get(key)
        if voice is not None and voice.name != name:
            self.stop(key, fade=_STOP_FADE_SECONDS)
            voice = None
        tier = self._tier_for(pos)
        if voice is None:
            handle = self._start(name, pos, volume, pitch, tier, True)
            if handle is not None:
                self._loops[key] = _LoopVoice(name, handle, tier, pos, volume, pitch)
            return
        voice.pos, voice.volume, voice.pitch = pos, volume, pitch
        self._apply_loop_state(voice)

    def _apply_loop_state(self, voice):
        """Aplica posição, tom e volume atuais; durante a troca de camada o volume fica com o fade."""
        handles = [voice.handle] + ([voice.fading_in[0]] if voice.fading_in else [])
        for handle in handles:
            if voice.pos is not None and self._spatial:
                handle.location = tuple(voice.pos)
            handle.pitch = voice.pitch
        if voice.fading_in is None:
            voice.handle.volume = self._loop_target(voice, voice.tier)

    def _refresh_loop_occlusion(self, voice):
        tier = self._tier_for(voice.pos)
        if tier != voice.tier and voice.fading_in is None:
            new_handle = self._start(voice.name, voice.pos, 0.0, voice.pitch, tier, True)
            if new_handle is not None:
                try:
                    new_handle.position = voice.handle.position
                except Exception:     # noqa: BLE001 - alguns backends não permitem seek
                    pass
                voice.fading_in = [new_handle, 0.0, tier]
        elif voice.fading_in is None:
            self._apply_loop_state(voice)

    def _advance_fades(self, dt):
        for voice in list(self._loops.values()):
            if voice.fading_in is None:
                continue
            new_handle, progress, tier = voice.fading_in
            progress = min(1.0, progress + dt / _CROSSFADE_SECONDS)
            target_new = self._loop_target(voice, tier)
            target_old = self._loop_target(voice, voice.tier)
            new_handle.volume = target_new * progress
            voice.handle.volume = target_old * (1.0 - progress)
            if progress >= 1.0:
                voice.handle.stop()
                voice.handle, voice.tier, voice.fading_in = new_handle, tier, None
            else:
                voice.fading_in[1] = progress
        for entry in list(self._dying):
            handle, volume, remaining = entry
            remaining -= dt
            if remaining <= 0.0:
                handle.stop()
                self._dying.remove(entry)
            else:
                handle.volume = volume * remaining / _STOP_FADE_SECONDS
                entry[2] = remaining

    def _loop_target(self, voice, tier):
        gain = OCCLUSION_TIERS[tier][1]
        if voice.pos is not None and not self._spatial:
            gain *= self._distance_gain(voice.name, voice.pos)
        return max(voice.volume * gain, 0.0)

    def stop(self, key=None, fade=0.0):
        """Para o loop `key` (todos, se None). Com `fade` > 0 baixa o volume antes de parar."""
        if not self.available and not self._loops:
            return
        keys = list(self._loops) if key is None else [key]
        for name in keys:
            voice = self._loops.pop(name, None)
            if voice is None:
                continue
            for handle in [voice.handle] + ([voice.fading_in[0]] if voice.fading_in else []):
                self._retire(handle, fade)

    def _retire(self, handle, fade):
        try:
            if fade > 0.0 and self.available:
                self._dying.append([handle, getattr(handle, "volume", 1.0), fade])
            else:
                handle.stop()
        except Exception:     # noqa: BLE001 - handle já morto
            pass

    def pick_variation(self, prefix, count):
        """Sorteia 1..count sem repetir a variação anterior de `prefix`."""
        options = [i for i in range(1, count + 1) if i != self._last_variation.get(prefix)]
        choice = self._rng.choice(options)
        self._last_variation[prefix] = choice
        return f"{prefix}_{choice}"

    def play_variant(self, prefix, count, pos=None, volume=1.0, pitch=1.0):
        """Toca `prefix_N` com N sorteado sem repetição (rangidos, baques, passos da entidade). Devolve o nome."""
        name = self.pick_variation(prefix, count)
        self.play(name, pos, volume, pitch)
        return name

    def footstep(self, surface, intensity, pos=None):
        """Passo no piso `surface` (wood, carpet, tile, concrete, stairs), volume pela `intensity` 0..1."""
        surface = surface if surface in ("wood", "carpet", "tile", "concrete", "stairs") else "wood"
        strength = min(max(float(intensity), 0.0), 1.0)
        return self.play_variant(f"step_{surface}", _STEP_VARIATIONS, pos,
                                 volume=0.25 + 0.75 * strength, pitch=self._rng.uniform(0.94, 1.06))

    def set_master(self, volume):
        self._master = min(max(float(volume), 0.0), 1.5)
        if self.available:
            self._guard(setattr, self._device, "volume", self._master)

    @property
    def master(self):
        return self._master

    def shutdown(self):
        """Para tudo e solta o dispositivo. Depois disto o engine vira no-op."""
        for voice in list(self._loops.values()):
            self._retire(voice.handle, 0.0)
            if voice.fading_in:
                self._retire(voice.fading_in[0], 0.0)
        self._loops.clear()
        for handle, _, _ in self._dying:
            self._retire(handle, 0.0)
        self._dying.clear()
        if self._device is not None:
            self._guard(self._device.stopAll)
        self._closed = True
        self._device = None
