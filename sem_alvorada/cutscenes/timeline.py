"""Modelo de dados das cutscenes: planos, enquadramentos, ações e a linha do tempo compilada.

Um `Cutscene` é uma lista de `Shot`. Cada plano tem uma câmera A -> B, legendas, ações
instantâneas (`Cue`), ações contínuas (`Track`) e curvas de efeitos (fade, letterbox, flash,
tremor). Todos os tempos DENTRO de um plano são relativos ao começo dele; `compile_cutscene`
converte tudo para tempo absoluto uma vez só, e o player apenas consulta.
"""
import bisect
from dataclasses import dataclass, field
from typing import Callable

EFFECT_CHANNELS = ("fade", "letterbox", "flash", "shake", "card")


def clamp01(value):
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def ease(name, u):
    """Curvas de aceleração de 0..1 para 0..1."""
    u = clamp01(u)
    if name == "linear":
        return u
    if name == "in":
        return u * u
    if name == "out":
        return 1.0 - (1.0 - u) ** 2
    if name == "smooth":
        return u * u * (3.0 - 2.0 * u)
    if name == "smoother":
        return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)
    raise ValueError(f"curva desconhecida: {name!r}")


@dataclass(frozen=True)
class View:
    """De onde a câmera olha (`eye`), para onde (`target`), com que lente (FOV horizontal) e giro.

    `eye` e `target` podem ser uma tupla (x, y, z) ou uma função `stage -> tupla`, resolvida quando
    a cutscene usa o valor (para partir da posição real do jogador, por exemplo).
    """
    eye: object
    target: object
    fov: float = 62.0
    roll: float = 0.0


@dataclass(frozen=True)
class Line:
    """Legenda: aparece de `start` a `end` (segundos relativos ao plano)."""
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Action:
    """Algo que a cutscene faz no anfitrião. `essential`: precisa acontecer mesmo se o jogador pular."""
    run: Callable
    essential: bool = False

    def __call__(self, stage):
        self.run(stage)


@dataclass(frozen=True)
class Cue:
    """Ação instantânea em `at` segundos (relativo ao plano)."""
    at: float
    action: Action


@dataclass(frozen=True)
class Track:
    """Ação contínua entre `start` e `end`: `apply(stage, f)` recebe f de 0 a 1 (já com a curva)."""
    start: float
    end: float
    apply: Callable
    ease: str = "smooth"


@dataclass(frozen=True)
class Shot:
    duration: float
    view: View
    to: View | None = None            # None: câmera parada (só a mão tremendo)
    ease: str = "smooth"
    handheld: float = 0.25            # 0 = tripé, 1 = câmera muito instável
    follow: str = ""                  # nome de um objeto movido por uma Track cujo deslocamento a câmera acompanha
    lines: tuple = ()
    cues: tuple = ()
    tracks: tuple = ()
    fade: tuple = ()                  # (tempo, valor), ...  valores 0..1
    letterbox: tuple = ()
    flash: tuple = ()
    shake: tuple = ()
    card: tuple = ()                  # opacidade do cartão final


@dataclass(frozen=True)
class Cutscene:
    name: str
    reason: str                       # o que `host.finish` recebe
    shots: tuple
    card: tuple | None = None         # (título, subtítulo) mostrado ao longo da cena (opacidade em `Shot.card`)
    initial: dict = field(default_factory=dict)     # valor dos canais em t=0 (ex.: fade=1)
    cues: tuple = ()                  # ações de tempo ABSOLUTO (atravessam vários planos)
    tracks: tuple = ()


@dataclass
class Timeline:
    """Cutscene compilada: tudo em tempo absoluto, ordenado."""
    cutscene: Cutscene
    total: float
    shots: list                       # (t0, t1, Shot)
    cues: list                        # (t, Action) por ordem de tempo
    tracks: list                      # (t0, t1, Track)
    channels: dict                    # nome -> [(t, valor)] ordenado
    lines: list                       # (t0, t1, texto)

    def shot_at(self, t):
        for t0, t1, shot in self.shots:
            if t < t1:
                return t0, t1, shot
        return self.shots[-1]

    def sample(self, channel, t):
        """Valor do canal em `t`: interpolação linear entre chaves, mantendo o último valor no fim."""
        keys = self.channels[channel]
        times = [k[0] for k in keys]
        i = bisect.bisect_right(times, t)
        if i == 0:
            return keys[0][1]
        if i == len(keys):
            return keys[-1][1]
        (ta, va), (tb, vb) = keys[i - 1], keys[i]
        if tb - ta < 1e-9:
            return vb
        return va + (vb - va) * (t - ta) / (tb - ta)

    def subtitle_at(self, t):
        for t0, t1, text in self.lines:
            if t0 <= t < t1:
                return text, t0, t1
        return "", 0.0, 0.0


def compile_cutscene(cutscene):
    shots, cues, tracks, lines = [], [], [], []
    channels = {name: [(0.0, float(cutscene.initial.get(name, 0.0)))] for name in EFFECT_CHANNELS}
    start = 0.0
    for shot in cutscene.shots:
        end = start + shot.duration
        shots.append((start, end, shot))
        cues += [(start + c.at, c.action) for c in shot.cues]
        tracks += [(start + tr.start, start + tr.end, tr) for tr in shot.tracks]
        lines += [(start + ln.start, start + ln.end, ln.text) for ln in shot.lines]
        for name in EFFECT_CHANNELS:
            channels[name] += [(start + t, float(v)) for t, v in getattr(shot, name)]
        start = end
    cues += [(c.at, c.action) for c in cutscene.cues]
    tracks += [(tr.start, tr.end, tr) for tr in cutscene.tracks]
    for keys in channels.values():
        keys.sort(key=lambda k: k[0])
    cues.sort(key=lambda c: c[0])
    lines.sort(key=lambda ln: ln[0])
    return Timeline(cutscene, start, shots, cues, tracks, channels, lines)

