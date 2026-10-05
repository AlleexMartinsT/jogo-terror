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
FILL_NAME = "HandFill"
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
        self.fill = scene.objects.get(FILL_NAME)
        if self.fill is not None and self.fill.parent is None and camera is not None:
            self.fill.parent = camera
            self.fill.matrix_parent_inverse = Matrix.Identity(4)
        self._shown = {}
        self.folds = (FoldSpring(19.0), FoldSpring(14.0))
        self.sheet = PaperSheet()
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

    def key_pendulum_lengths(self):
        """Comprimentos equivalentes (lateral, para a frente) do chaveiro, da malha do modelo; sem o modelo, 0,11 m."""
        obj = self.objects.get(C.ITEM_KEY)
        if obj is None or obj.type != "MESH" or not obj.data.polygons:
            return (0.11, 0.11)
        info = compound_pendulum(obj.data)
        return (info["length_roll"], info["length_pitch"])

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
        self.light_hands(False)

    def light_hands(self, on):
        """A luz de preenchimento das mãos acende enquanto há algo na mão."""
        if self.fill is not None:
            self.fill.hide_viewport = self.fill.hide_render = not on

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

    def set_map_folds(self, first, second, dt=0.0):
        """Ângulos (graus) das duas dobras do mapa; 0 = aberto. Os painéis dobram para trás do primeiro (longe da
        câmera), então desdobrar nunca passa uma folha grande diante do rosto. Com `dt` cada dobra segue o ângulo pedido
        como uma mola (`FoldSpring`); sem `dt` vai direto."""
        for panel, spring, angle in zip(self.panels, self.folds, (first, second)):
            if dt > 0.0:
                angle = spring.step(dt, angle)
            else:
                spring.value, spring.speed = angle, 0.0
            if panel is not None:
                panel.rotation_euler = (0.0, math.radians(angle), 0.0)

    def set_sheet_droop(self, meters):
        """Flecha da ponta da folha (m) pela chave de forma `Droop` do modelo (se ele a tem)."""
        obj = self.objects.get(C.ITEM_NOTE)
        keys = obj.data.shape_keys if obj is not None else None
        if keys is not None and "Droop" in keys.key_blocks:
            keys.key_blocks["Droop"].value = meters

    def set_paper(self, note_id):
        """A folha na mão ganha a textura e a proporção da anotação lida. Devolve o tamanho (largura, altura)."""
        material, width, height = NOTE_LOOK.get(note_id, NOTE_FALLBACK)
        self.sheet.set_length(height)
        obj = self.objects.get(C.ITEM_NOTE)
        if obj is not None and obj.material_slots:
            wanted = bpy.data.materials.get(material)
            if wanted is not None and obj.material_slots[0].material is not wanted:
                obj.material_slots[0].material = wanted
        return width, height


# ---------------------------------------------------------------------------
# Física leve
# ---------------------------------------------------------------------------
# Massas (g) de cada material do chaveiro de mão, ESTIMADAS (um chaveiro de carro com controle pesa de 25 a 40 g):
# lâmina e argolas de aço, miolo cromado, cabeça de plástico com a placa do controle, borrachas e o coelho de pelúcia.
# A geometria vem da malha `ViewModel_Key`; só a massa é estimada.
KEY_MASS_G = {"key_metal": 6.0, "chrome": 4.0, "black": 14.0, "rubber": 1.0, "plush_white": 5.5, "plush_pink": 0.5}
GRAVITY = 9.81


def compound_pendulum(mesh, masses=None):
    """O chaveiro como corpo rígido pendurado pelo pivô (a origem da malha, onde os dedos pinçam a cabeça).

    A massa de cada material é espalhada pela sua superfície (um ponto por polígono, ponderado pela área). Devolve
    {mass (kg), com (centro de massa, m), d (distância vertical do pivô ao centro de massa, m), inertia_roll (kg m2, balanço
    lateral, em torno de Z), inertia_pitch (para a frente, em torno de X), length_roll, length_pitch}. O comprimento
    equivalente é o do pêndulo simples de mesmo período, L = I / (m d), e o período pequeno vale T = 2 pi raiz(L / g)."""
    masses = KEY_MASS_G if masses is None else masses
    names = [m.name if m else "" for m in mesh.materials]
    area = {}
    for polygon in mesh.polygons:
        name = names[polygon.material_index] if polygon.material_index < len(names) else ""
        area[name] = area.get(name, 0.0) + polygon.area
    points = []
    for polygon in mesh.polygons:
        name = names[polygon.material_index] if polygon.material_index < len(names) else ""
        grams = masses.get(name, 0.0)
        if grams > 0.0 and area.get(name, 0.0) > 0.0:
            points.append((grams * 1e-3 * polygon.area / area[name], polygon.center.x, polygon.center.y, polygon.center.z))
    total = sum(m for m, *_ in points)
    cx = sum(m * x for m, x, _, _ in points) / total
    cy = sum(m * y for m, _, y, _ in points) / total
    cz = sum(m * z for m, _, _, z in points) / total
    roll = sum(m * (x * x + y * y) for m, x, y, _ in points)           # gira em torno de Z (balanço lateral)
    pitch = sum(m * (y * y + z * z) for m, _, y, z in points)           # gira em torno de X (para a frente)
    d = -cy                                                               # o chaveiro pende para -Y
    return {"mass": total, "com": (cx, cy, cz), "d": d, "inertia_roll": roll, "inertia_pitch": pitch,
            "length_roll": roll / (total * d), "length_pitch": pitch / (total * d)}


class Pendulum:
    """Chaveiro pendurado pelo pivô: dois ângulos (lateral e para a frente) que respondem à aceleração da mão.

    `lengths` são os comprimentos equivalentes (lateral, para a frente) do pêndulo composto, L = I / (m d), da malha
    (`compound_pendulum`). A equação é a do corpo rígido, theta'' = -(g / L) sin(theta) - 2 zeta w0 theta' - (a / L) cos(theta),
    com `a` a aceleração horizontal do pivô. O amortecimento (`damping_ratio`) é ESTIMADO: o ar quase não amortece um
    objeto assim, mas a pinça dos dedos atrita no pivô; 0,08 faz o balanço cair a 10% em ~3 s."""
    LIMIT = math.radians(75.0)
    SUBSTEP = 1.0 / 240.0

    def __init__(self, lengths=(0.11, 0.11), damping_ratio=0.08):
        lengths = (lengths, lengths) if isinstance(lengths, (int, float)) else tuple(lengths)
        self.lengths = lengths
        self.length = sum(lengths) / 2.0
        self.omega0s = [math.sqrt(GRAVITY / length) for length in lengths]
        self.omega0 = sum(self.omega0s) / 2.0
        self.dampings = [2.0 * damping_ratio * w for w in self.omega0s]
        self.damping_ratio = damping_ratio
        self.angle = [0.0, 0.0]            # (lateral em torno de Z, para a frente em torno de X), radianos
        self.speed = [0.0, 0.0]

    def period(self, amplitude=0.0, axis=0):
        """Período (s) de pequenas oscilações, 2 pi raiz(L/g), com a correção de amplitude finita (1 + a^2/16)."""
        return 2.0 * math.pi / self.omega0s[axis] * (1.0 + amplitude * amplitude / 16.0)

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
                a = (-self.omega0s[i] ** 2 * math.sin(self.angle[i]) - self.dampings[i] * self.speed[i]
                     - accel[i] / self.lengths[i] * math.cos(self.angle[i]))
                self.speed[i] += a * h
                self.angle[i] += self.speed[i] * h
                if abs(self.angle[i]) > self.LIMIT:
                    self.angle[i] = math.copysign(self.LIMIT, self.angle[i])
                    self.speed[i] *= -0.3

    def matrix(self):
        """Rotação em torno do pivô (a origem do modelo)."""
        return Euler((self.angle[1], 0.0, self.angle[0]), "XYZ").to_matrix().to_4x4()


class PaperSheet:
    """A folha presa pela borda de baixo é uma viga em balanço que a gravidade e a aceleração da mão dobram.

    Papel de 80 g/m2 (ESTIMADO: E ~ 3 GPa, espessura 0,1 mm, rigidez à flexão EI = 2,5e-4 N m por metro de largura):
      * flecha da ponta sob carga distribuída, d = rho_a a L^4 / (8 EI): ~2 cm por m/s2 numa folha de 15 cm, então a
        gravidade sozinha a faria cair além do próprio comprimento; a flecha satura em `MAX_SAG` do comprimento;
      * primeiro modo de vibração, w = 3,516 / L^2 raiz(EI / rho_a): 8,7 rad/s (1,4 Hz) em 15 cm e 2,3 rad/s em 29 cm;
      * amortecimento do ar alto para uma folha, zeta ~ 0,35.
    `step` recebe a componente da gravidade efetiva (g menos a aceleração do apoio) na normal da folha e devolve a flecha
    da ponta em metros (positiva = a ponta cai para o lado de trás da folha)."""
    BENDING = 2.5e-4            # N m por metro de largura
    DENSITY = 0.080             # kg/m2
    ZETA = 0.35
    MAX_SAG = 0.55              # fração do comprimento

    def __init__(self, length=0.16):
        self.set_length(length)
        self.value = 0.0
        self.speed = 0.0

    def set_length(self, length):
        self.length = length
        self.omega = 3.516 / length ** 2 * math.sqrt(self.BENDING / self.DENSITY)

    def reset(self):
        self.value = self.speed = 0.0

    def target(self, normal_accel):
        raw = self.DENSITY * normal_accel * self.length ** 4 / (8.0 * self.BENDING)
        limit = self.MAX_SAG * self.length
        return limit * math.tanh(raw / limit)

    def step(self, dt, normal_accel):
        target = self.target(normal_accel)
        steps = max(1, int(math.ceil(dt / (1.0 / 240.0))))
        h = dt / steps
        for _ in range(steps):
            accel = self.omega ** 2 * (target - self.value) - 2.0 * self.ZETA * self.omega * self.speed
            self.speed += accel * h
            self.value += self.speed * h
        return self.value


class FoldSpring:
    """Um painel do mapa que gira na dobradiça como uma mola amortecida rumo ao ângulo pedido: o papel dobrado abre um pouco
    atrás da mão e passa do ponto (sobressalto de ~10%) antes de assentar. O painel mais longe da mão é mais lento.
    ESTIMADO: frequências de 3 a 2,2 Hz e zeta 0,6."""

    def __init__(self, omega, zeta=0.6):
        self.omega, self.zeta = omega, zeta
        self.value = None
        self.speed = 0.0

    def reset(self):
        self.value, self.speed = None, 0.0

    def step(self, dt, target):
        if self.value is None:
            self.value = target
        steps = max(1, int(math.ceil(dt / (1.0 / 240.0))))
        h = dt / steps
        for _ in range(steps):
            accel = self.omega ** 2 * (target - self.value) - 2.0 * self.zeta * self.omega * self.speed
            self.speed += accel * h
            self.value += self.speed * h
        return self.value


class SupportAcceleration:
    """Aceleração 3D (m/s2, no mundo) de um ponto, a partir das posições quadro a quadro, suavizada e limitada."""

    def __init__(self, limit=20.0, rate=18.0):
        self.limit, self.rate = limit, rate
        self.reset()

    def reset(self):
        self._previous = None
        self._velocity = None
        self.value = (0.0, 0.0, 0.0)

    def update(self, dt, position):
        if self._previous is None or dt <= 0:
            self._previous = position
            return self.value
        velocity = tuple((a - b) / dt for a, b in zip(position, self._previous))
        self._previous = position
        if self._velocity is not None:
            mix = min(1.0, self.rate * dt)
            raw = tuple((v1 - v0) / dt for v0, v1 in zip(self._velocity, velocity))
            self.value = tuple(max(-self.limit, min(self.limit, old + (new - old) * mix)) for old, new in zip(self.value, raw))
        self._velocity = velocity
        return self.value


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
