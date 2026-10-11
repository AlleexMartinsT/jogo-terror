"""Como a mão da lanterna acompanha o olhar: elevação parcial, giro do cano para ler e a batida quando a luz pisca.

Elevação. O feixe segue a câmera com a constante de tempo medida (`flashlight.SWAY_FOLLOW`, 77 ms), mas o braço não: quem olha
para cima não leva a lanterna junto na mesma medida, o ombro fica no tronco e o antebraço sobe menos que o olhar. No mocap
91_18 (olhar em volta com cuidado, 29 graus de passo da cabeça) a inclinação da elevação do punho contra o passo da cabeça é
-0,13 (direita) e -0,08 (esquerda): a mão fica onde está. O jogo precisa da lanterna à vista, então a mão acompanha o
passo em `FOLLOW` (ESTIMADO, 0,3) e o que sobra gira em torno do ombro, limitado a `LIMIT`: poucos centímetros, o punho gira
para o cano continuar apontando para onde se olha.

Leitura. De perto o cano gira para fora da superfície (a luz de frente estoura o papel): a mão baixa e vira o cano uns 17
graus, e o feixe passa a raspar a folha.

Batida. ESTIMADO (uma prática comum, sem medida): quando a pilha fraca faz a luz piscar, de vez em quando a mão esquerda livre
sobe e bate na lateral do cano. Nunca mais de uma vez por rajada: depois de uma batida, `REFRACTORY` s de calma.
"""
import math

from mathutils import Matrix, Vector

FOLLOW = 0.30                      # fração do passo da cabeça que a mão acompanha (ESTIMADO; 91_18: perto de 0)
LIMIT = math.radians(10.0)         # quanto a mão pode girar em torno do ombro em relação à câmera
ELEVATION_TAU = 0.09               # s: o antebraço atrás da cabeça, da ordem dos 77 ms medidos no 77_05
READING_RATE = 7.0                 # 1/s: com que rapidez o cano gira para ler
READING_TILT = math.radians(17.0)
READING_SHIFT = Vector((-0.020, -0.012, 0.030))
SHOULDER_DEFAULT = Vector((0.19, -0.25, 0.05))    # ombro direito no espaço da câmera, em pé e olhando em frente
TAP_REACTION = 0.35                # s da piscada ao início do gesto: o tempo de reação visual (200 a 300 ms) e decidir
TAP_PROBABILITY = 0.6
REFRACTORY = 12.0


class LanternAim:
    """Estado da elevação e da leitura. `update` devolve (deslocamento da mão, giro) a somar à pose da mão direita."""

    ENGAGE_TAU = 0.15                 # s: a mão assume ou larga o acompanhamento sem pulo quando um gesto começa ou acaba

    def __init__(self):
        self.pitch = 0.0
        self.reading = 0.0
        self.engage = 0.0

    def reset(self):
        self.pitch = self.reading = self.engage = 0.0

    def update(self, dt, camera_pitch, reading, engaged, hand, shoulder=None):
        """`camera_pitch`: passo da cabeça (rad, positivo olhando para cima). `reading`: 0 ou 1. `engaged`: 0 ou 1, se a mão está
        segurando a lanterna parada (nos gestos de pegar quem manda é o clipe). `hand`, `shoulder`: no espaço da câmera."""
        self.pitch += (camera_pitch - self.pitch) * (1.0 - math.exp(-dt / ELEVATION_TAU))
        self.reading += (reading - self.reading) * (1.0 - math.exp(-READING_RATE * dt))
        self.engage += (engaged - self.engage) * (1.0 - math.exp(-dt / self.ENGAGE_TAU))
        engaged = self.engage
        phi = -LIMIT * math.tanh((1.0 - FOLLOW) * self.pitch / LIMIT) * engaged
        pivot = Vector(shoulder) if shoulder is not None else SHOULDER_DEFAULT
        moved = pivot + Matrix.Rotation(phi, 3, "X") @ (Vector(hand) - pivot)
        shift = (moved - Vector(hand)) + READING_SHIFT * self.reading * engaged
        return shift, (-READING_TILT * self.reading * engaged, 0.10 * self.reading * engaged, 0.0)


class TapScheduler:
    """Decide quando a mão esquerda bate no cano: uma batida por rajada de piscadas, depois de um tempo de reação."""

    def __init__(self, rng):
        self.rng = rng
        self.due = None
        self.last = -1e9

    def reset(self):
        self.due = None
        self.last = -1e9

    def noticed(self, now):
        """A luz acabou de piscar por mau contato."""
        if self.due is not None or now - self.last < REFRACTORY:
            return
        if self.rng.random() < TAP_PROBABILITY:
            self.due = now + TAP_REACTION

    def ready(self, now):
        """True uma vez, quando chegou a hora (o chamador diz se a mão está livre; se não está, a batida se perde)."""
        if self.due is None or now < self.due:
            return False
        self.due = None
        self.last = now
        return True
