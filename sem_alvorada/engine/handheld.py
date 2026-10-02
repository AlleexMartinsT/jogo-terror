"""Os objetos que as mãos seguram e a física leve deles.

`Handhelds` acha na cena os modelos construídos pela etapa props (`props/handheld_*.py`), pendura na
câmera do jogador, esconde até serem usados e os posiciona no espaço da câmera. Se um modelo não existe
(cena de teste, .blend antigo) tudo continua: só não há o que desenhar.

A física é de mentira e barata: um pêndulo para o chaveiro e molas amortecidas para a inércia e a respiração.
"""
import math

import bpy  # noqa: F401 - `mathutils` só existe depois deste import
from mathutils import Euler, Matrix

from .. import conventions as C

MODEL_NAMES = {C.ITEM_FLASHLIGHT: "ViewModel_Flashlight", C.ITEM_KEY: "ViewModel_Key", C.ITEM_MAP: "ViewModel_Map",
               C.ITEM_BATTERY: "ViewModel_Battery", C.ITEM_NOTE: "ViewModel_Paper"}
CAP_NAME = "ViewModel_Flashlight_Cap"
MAP_PANEL_NAMES = ("ViewModel_Map_P2", "ViewModel_Map_P3")

# Anotação -> (material do papel, largura, altura em metros). Mesmas medidas dos modelos de mesa.
NOTE_LOOK = {
    "NOTE_1": ("note_letter", 0.112, 0.150), "NOTE_2": ("note_crayon", 0.214, 0.292),
    "NOTE_3": ("note_newspaper", 0.148, 0.172), "NOTE_4": ("note_notebook", 0.190, 0.250),
    "NOTE_5": ("note_postit", 0.085, 0.085), "NOTE_6": ("note_prescription", 0.100, 0.136),
    "NOTE_7": ("note_tow", 0.126, 0.172),
}
NOTE_FALLBACK = NOTE_LOOK["NOTE_1"]


class Handhelds:
    def __init__(self, scene, camera):
        self.camera = camera
        self.objects = {kind: scene.objects.get(name) for kind, name in MODEL_NAMES.items()}
        self.cap = scene.objects.get(CAP_NAME)
        self.panels = tuple(scene.objects.get(name) for name in MAP_PANEL_NAMES)
        self._shown = {}
        for kind, obj in self.objects.items():
            if obj is None:
                continue
            if obj.parent is None and camera is not None:
                obj.parent = camera
                obj.matrix_parent_inverse = Matrix.Identity(4)
            for part in (obj, *self._parts(kind)):
                if part is not None and hasattr(part, "visible_shadow"):
                    part.visible_shadow = False
        self.hide_all()

    def _parts(self, kind):
        if kind == C.ITEM_FLASHLIGHT:
            return (self.cap,)
        if kind == C.ITEM_MAP:
            return self.panels
        return ()

    @property
    def available(self):
        return {kind for kind, obj in self.objects.items() if obj is not None}

    # ---- visibilidade ----
    def present(self, kind, visible):
        obj = self.objects.get(kind)
        if obj is None or self._shown.get(kind) == visible:
            return
        self._shown[kind] = visible
        for part in (obj, *self._parts(kind)):
            if part is not None:
                part.hide_viewport = part.hide_render = not visible

    def hide_all(self):
        for kind in MODEL_NAMES:
            self._shown.pop(kind, None)
            self.present(kind, False)

    def restore_scene(self):
        """Devolve os objetos ao arquivo: ocultos e na origem do pai."""
        self.hide_all()
        for obj in self.objects.values():
            if obj is not None:
                obj.matrix_basis = Matrix.Identity(4)

    # ---- pose ----
    def place(self, kind, matrix, scale=None):
        obj = self.objects.get(kind)
        if obj is None:
            return
        if scale is not None:
            matrix = matrix @ Matrix.Diagonal((*scale, 1.0))
        obj.matrix_basis = matrix

    def set_cap(self, degrees):
        if self.cap is not None:
            self.cap.rotation_euler = (0.0, math.radians(degrees), 0.0)

    def set_map_folds(self, first, second):
        """Ângulos (graus) das duas dobras do mapa; 0 = aberto."""
        for panel, angle in zip(self.panels, (first, second)):
            if panel is not None:
                panel.rotation_euler = (0.0, -math.radians(angle), 0.0)

    def set_paper(self, note_id):
        """A folha na mão ganha a textura e a proporção da anotação lida. Devolve o tamanho (largura, altura)."""
        material, width, height = NOTE_LOOK.get(note_id, NOTE_FALLBACK)
        obj = self.objects.get(C.ITEM_NOTE)
        if obj is not None and obj.material_slots:
            wanted = bpy.data.materials.get(material)
            if wanted is not None and obj.material_slots[0].material is not wanted:
                obj.material_slots[0].material = wanted
        return width, height


# ---------------------------------------------------------------------------
# Física leve
# ---------------------------------------------------------------------------
class Pendulum:
    """Chaveiro pendurado pelo pivô: dois ângulos (lateral e para a frente) que respondem à aceleração da mão.

    `length` é a distância do pivô ao centro de massa. O amortecimento é baixo: depois de um puxão o chaveiro
    faz algumas oscilações e para em cerca de um segundo e meio."""
    LIMIT = math.radians(75.0)
    SUBSTEP = 1.0 / 240.0

    def __init__(self, length=0.11, damping_ratio=0.13):
        self.length = length
        self.omega0 = math.sqrt(9.81 / length)
        self.damping = 2.0 * damping_ratio * self.omega0
        self.angle = [0.0, 0.0]            # (lateral em torno de Z, para a frente em torno de X), radianos
        self.speed = [0.0, 0.0]

    def reset(self):
        self.angle, self.speed = [0.0, 0.0], [0.0, 0.0]

    def kick(self, lateral, forward=0.0):
        """Empurrão instantâneo (rad/s)."""
        self.speed[0] += lateral
        self.speed[1] += forward

    def step(self, dt, accel):
        """`accel` = (lateral, para a frente) do pivô em m/s², no espaço da câmera."""
        steps = max(1, int(math.ceil(dt / self.SUBSTEP)))
        h = dt / steps
        for _ in range(steps):
            for i in (0, 1):
                a = (-self.omega0 ** 2 * math.sin(self.angle[i]) - self.damping * self.speed[i]
                     - accel[i] / self.length * math.cos(self.angle[i]))
                self.speed[i] += a * h
                self.angle[i] += self.speed[i] * h
                if abs(self.angle[i]) > self.LIMIT:
                    self.angle[i] = math.copysign(self.LIMIT, self.angle[i])
                    self.speed[i] *= -0.3

    def matrix(self):
        """Rotação em torno do pivô (a origem do modelo)."""
        return Euler((self.angle[1], 0.0, self.angle[0]), "XYZ").to_matrix().to_4x4()


class PivotAcceleration:
    """Aceleração suavizada de um ponto a partir das posições quadro a quadro."""

    def __init__(self, limit=14.0, rate=22.0):
        self.limit, self.rate = limit, rate
        self.reset()

    def reset(self):
        self._previous = None
        self._velocity = None
        self.value = (0.0, 0.0)

    def update(self, dt, position):
        if self._previous is None or dt <= 0:
            self._previous = position
            return self.value
        velocity = tuple((a - b) / dt for a, b in zip(position, self._previous))
        self._previous = position
        if self._velocity is not None:
            lateral = (velocity[0] - self._velocity[0]) / dt
            forward = -(velocity[2] - self._velocity[2]) / dt
            mix = min(1.0, self.rate * dt)
            self.value = tuple(max(-self.limit, min(self.limit, old + (new - old) * mix))
                               for old, new in zip(self.value, (lateral, forward)))
        self._velocity = velocity
        return self.value


class Sway:
    """Inércia e respiração de um item na mão: uma mola amortecida segue o balanço da câmera.

    `step` devolve o deslocamento (x, y, z) e a rotação (graus) a somar à pose da mão."""
    OMEGA = 11.0
    ZETA = 0.65

    def __init__(self, phase=0.0, gain=1.0):
        self.phase = phase
        self.gain = gain
        self.reset()

    def reset(self):
        self.offset = [0.0, 0.0]
        self.speed = [0.0, 0.0]

    def step(self, dt, clock, bob, yaw_rate, pitch_rate, hard_breathing):
        target = (bob[0] * self.gain - max(-4.0, min(4.0, yaw_rate)) * 0.011,
                  bob[1] * self.gain - max(-4.0, min(4.0, pitch_rate)) * 0.009)
        steps = max(1, int(math.ceil(dt / (1.0 / 120.0))))
        h = dt / steps
        for _ in range(steps):
            for i in (0, 1):
                a = self.OMEGA ** 2 * (target[i] - self.offset[i]) - 2.0 * self.ZETA * self.OMEGA * self.speed[i]
                self.speed[i] += a * h
                self.offset[i] += self.speed[i] * h
        rate, amplitude = (0.55, 0.0052) if hard_breathing else (0.24, 0.0024)
        breath = math.sin(math.tau * rate * clock + self.phase)
        x, y = self.offset
        pos = (x, y + amplitude * breath, 0.0)
        rot = (-y * 120.0 + 0.45 * breath * (2.0 if hard_breathing else 1.0), -x * 70.0, -x * 55.0)
        return pos, rot
