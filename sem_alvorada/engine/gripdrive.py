"""Dos canais de um clipe às juntas dos dedos: a pegada por contato (`grasp_data`) no lugar de curvas de curl fixas.

Cada mão tem cinco curls livres (o que os clipes sempre escreveram: mão aberta, relaxada, em concha) e, agora, cinco
valores de `grip`, de 0 a 1: quanto cada dedo já se fechou NO ITEM que a mão segura. Com `grip` = 1 a pose é a que
`tools/movimento_ref/cenarios/pegadas.py gerar` calculou por contato com a malha (sem penetração, folga de décimos de
milímetro); com 0 vale o curl livre. No meio os dois se misturam junta por junta, o que dá a pré-forma de quem alcança: a
mão abre além do tamanho do item e fecha até o contato (`handclips.reach`).

Matemática pura (sem bpy): serve ao jogo, ao teste e às medidas de perfil de abertura.
"""
from .. import conventions as C
from .. import grasp_data

# O interruptor com o polegar. ESTIMADO (não há medida de interruptor de lanterna): descer 45 ms, sustentar 40 ms e subir 75 ms,
# no total 160 ms, dentro da faixa de 80 a 150 ms que um dedo costuma ficar sobre uma tecla.
PRESS_DOWN, PRESS_HOLD, PRESS_UP = 0.045, 0.040, 0.075
PRESS_TOTAL = PRESS_DOWN + PRESS_HOLD + PRESS_UP


def press_envelope(age):
    """Quanto o polegar afundou o interruptor (0 a 1) `age` s depois de começar a apertar; 0 fora da janela."""
    if age < 0.0 or age >= PRESS_TOTAL:
        return 0.0
    if age < PRESS_DOWN:
        x = age / PRESS_DOWN
        return x * x * (3.0 - 2.0 * x)
    if age < PRESS_DOWN + PRESS_HOLD:
        return 1.0
    x = (age - PRESS_DOWN - PRESS_HOLD) / PRESS_UP
    return 1.0 - x * x * (3.0 - 2.0 * x)


def _mix(a, b, u):
    return a + (b - a) * min(1.0, max(0.0, u))


class GripDrive:
    """Junta as pegadas de `grasp_data` e entrega as juntas de uma mão a cada quadro."""

    def __init__(self, data=None):
        self.data = grasp_data.GRASPS if data is None else data

    def has(self, kind):
        return kind in self.data

    def joints(self, kind, curl, grip, press=0.0):
        """[5][3] curls por junta de uma mão que segura `kind`, ou None se o item não tem pegada calculada.

        `curl`: os cinco curls livres; `grip`: cinco fechamentos (0 a 1); `press`: afundamento do interruptor (só o polegar)."""
        pose = self.data.get(kind)
        if pose is None:
            return None
        rows = []
        for finger in range(5):
            free = (curl[finger],) * 3
            closed = pose["closed"][finger]
            if finger == 0 and press > 0.0 and pose.get("pressed"):
                closed = [_mix(a, b, press) for a, b in zip(closed, pose["pressed"])]
            rows.append([_mix(f, c, grip[finger]) for f, c in zip(free, closed)])
        return rows

    def closed_for(self, kind):
        return None if kind not in self.data else self.data[kind]["closed"]


def uniform(value):
    """Cinco fechamentos iguais."""
    return (float(value),) * 5


HOLDING = uniform(1.0)
EMPTY = uniform(0.0)
FLASHLIGHT = C.ITEM_FLASHLIGHT
