"""Fluidez das câmeras das cutscenes: amostra cada uma a 60 Hz e cobra continuidade.

    python tests/test_cutscenes_fluency.py

Prova, sem renderizar nada, que fora dos CORTES DECLARADOS (`Shot.cut`) a posição, a rotação (sem salto de
quaternion nem dupla cobertura) e o FOV da câmera não têm descontinuidades, com limites de velocidade e de
aceleração razoáveis. Pancadas (`Impact`) e tremor forte (canal `shake` acima de 0,3) têm limites mais soltos,
mas continuam sem salto de posição. Também mede o custo por quadro das animações de objetos.
"""
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from cutscene_fakes import host_for  # noqa: E402
from sem_alvorada.cutscenes import NAMES, CutscenePlayer, camera, scripts, timeline  # noqa: E402

HZ = 60
DT = 1.0 / HZ

# limites: por quadro a 60 Hz (salto) e por segundo (velocidade, aceleração)
NORMAL = {"pos_step": 0.075, "rot_step": 2.6, "fov_step": 0.6, "speed": 4.6, "accel": 14.0, "ang_speed": 150.0,
          "ang_accel": 2200.0, "fov_rate": 38.0}
VIOLENT = {"pos_step": 0.12, "rot_step": 7.0, "fov_step": 1.6, "speed": 7.0, "accel": 170.0, "ang_speed": 420.0,
           "ang_accel": 11000.0, "fov_rate": 90.0}

DECLARED_CUTS = {"intro": [0.0], "blackout": [0.0, 3.6], "garage_unlock": [0.0], "death": [0.0],
                 "ending": [0.0, 8.4, 12.8, 19.4]}


def sample(name):
    """[(t, pos, quat, fov_deg, plano)] a 60 Hz de uma execução com dt fixo."""
    host = host_for(name)
    player = CutscenePlayer(host)
    player.play(name)
    cam = host.objects["CutsceneCam"]
    tl = player._run.timeline
    out = []
    while player.active:
        out.append((player.time, tuple(cam.location), tuple(cam.rotation_quaternion), math.degrees(cam.data.angle),
                    tl.shot_index(player.time)))
        player.update(DT)
    assert player.errors == [], player.errors
    return out


def violent_windows(name):
    """Intervalos [a, b] em que a câmera pode ser sacudida de verdade: pancadas declaradas e tremor forte."""
    tl = timeline.compile_cutscene(scripts.get(name))
    windows = []
    for (t0, t1, shot), rig in zip(tl.shots, tl.rigs):
        for hit in rig.impacts:
            windows.append((t0 + hit.at - 0.02, t0 + hit.at + 0.9))
    keys = tl.channels["shake"]
    for (ta, va), (tb, vb) in zip(keys, keys[1:]):
        if max(va, vb) > 0.3:
            windows.append((ta, tb + 0.15))
    return windows


def in_windows(t, windows):
    return any(a <= t <= b for a, b in windows)


def analyse(name):
    tl = timeline.compile_cutscene(scripts.get(name))
    cuts = [t0 for t0, t1, shot in tl.shots if shot.cut]
    frames = sample(name)
    windows = violent_windows(name)
    worst = {}

    def note(kind, value, t):
        if value > worst.get(kind, (0.0, 0.0))[0]:
            worst[kind] = (value, t)

    def limits(t):
        return VIOLENT if in_windows(t, windows) else NORMAL

    steps = []
    for (ta, pa, qa, fa, ia), (tb, pb, qb, fb, ib) in zip(frames, frames[1:]):
        if ia != ib and tl.shots[ib][2].cut:
            steps.append(None)
            continue
        dot = sum(a * b for a, b in zip(qa, qb))
        assert dot > 0.0, f"{name}: o quaternion mudou de hemisfério (dupla cobertura) em t={tb:.2f}"
        dp, dr, df = math.dist(pa, pb), math.degrees(camera.angle_between(qa, qb)), abs(fb - fa)
        lim = limits(tb)
        assert dp <= lim["pos_step"], f"{name}: salto de posição {dp:.3f} m em t={tb:.2f}"
        assert dr <= lim["rot_step"], f"{name}: salto de rotação {dr:.2f} graus em t={tb:.2f}"
        assert df <= lim["fov_step"], f"{name}: salto de FOV {df:.2f} graus em t={tb:.2f}"
        note("pos_step", dp / lim["pos_step"], tb)
        note("rot_step", dr / lim["rot_step"], tb)
        steps.append((tb, dp / DT, dr / DT, df / DT))
    # velocidade e aceleração (diferenças dos passos): ignora o quadro do corte e o seguinte
    for a, b in zip(steps, steps[1:]):
        if a is None or b is None:
            continue
        t = b[0]
        lim = limits(t)
        dv = abs(b[1] - a[1]) / DT
        dw = abs(b[2] - a[2]) / DT
        assert b[1] <= lim["speed"], f"{name}: velocidade {b[1]:.2f} m/s em t={t:.2f}"
        assert b[2] <= lim["ang_speed"], f"{name}: velocidade angular {b[2]:.0f} graus/s em t={t:.2f}"
        assert b[3] <= lim["fov_rate"], f"{name}: o FOV muda {b[3]:.0f} graus/s em t={t:.2f}"
        assert dv <= lim["accel"], f"{name}: aceleração {dv:.1f} m/s2 em t={t:.2f}"
        assert dw <= lim["ang_accel"], f"{name}: aceleração angular {dw:.0f} graus/s2 em t={t:.2f}"
        note("speed", b[1] / lim["speed"], t)
        note("ang_speed", b[2] / lim["ang_speed"], t)
        note("accel", dv / lim["accel"], t)
        note("ang_accel", dw / lim["ang_accel"], t)
    return cuts, frames, worst


def test_declared_cuts():
    for name in NAMES:
        tl = timeline.compile_cutscene(scripts.get(name))
        cuts = [round(t0, 3) for t0, t1, shot in tl.shots if shot.cut]
        assert cuts == DECLARED_CUTS[name], (name, cuts)
        names = [shot.name for _, _, shot in tl.shots]
        print(f"  {name}: cortes declarados em {cuts} ({', '.join(names)})")


def test_cameras_are_continuous_outside_the_cuts():
    for name in NAMES:
        cuts, frames, worst = analyse(name)
        pct = {k: f"{v[0] * 100:.0f}% do limite (t={v[1]:.1f})" for k, v in worst.items()}
        print(f"  {name}: {len(frames)} quadros a {HZ} Hz sem saltos; pior caso: {pct}")


def test_continuous_joins_have_no_jump():
    """Se algum plano declarar `cut=False`, o último quadro do anterior e o primeiro dele coincidem."""
    for name in NAMES:
        tl = timeline.compile_cutscene(scripts.get(name))
        frames = sample(name)
        for t0, t1, shot in tl.shots:
            if shot.cut or t0 == 0.0:
                continue
            index = next(i for i, shot in enumerate(tl.shots) if shot[0] == t0)
            before = max((f for f in frames if f[4] < index), key=lambda f: f[0])
            after = min((f for f in frames if f[4] >= index), key=lambda f: f[0])
            assert math.dist(before[1], after[1]) < NORMAL["pos_step"] * 1.5, (name, t0)
            assert math.degrees(camera.angle_between(before[2], after[2])) < NORMAL["rot_step"] * 1.5, (name, t0)
            assert abs(before[3] - after[3]) < NORMAL["fov_step"] * 2, (name, t0)


def test_rotation_never_flips_sign():
    """Tomadas que dão a volta (intro: meia-volta; morte: queda) não podem trocar q por -q no meio do caminho."""
    for name in ("intro", "death", "ending"):
        frames = sample(name)
        tl = timeline.compile_cutscene(scripts.get(name))
        for a, b in zip(frames, frames[1:]):
            if a[4] != b[4] and tl.shots[b[4]][2].cut:
                continue
            assert sum(x * y for x, y in zip(a[2], b[2])) > 0.0, (name, b[0])


def test_object_animation_cost_per_frame():
    """O conjunto de atores (cortinas, poeira, faíscas, carro, pêndulos, portão, luzes) custa < 3 ms por quadro em média."""
    for name in ("intro", "blackout", "garage_unlock", "ending"):
        host = host_for(name)
        player = CutscenePlayer(host)
        player.play(name)
        stage = player._run.stage
        costs = []
        original = stage.update_actors

        def timed(dt, late=False):
            started = time.perf_counter()
            original(dt, late)
            if not late:
                costs.append(time.perf_counter() - started)
        stage.update_actors = timed
        while player.active:
            player.update(DT)
        mean_ms = 1000.0 * sum(costs) / len(costs)
        peak_ms = 1000.0 * max(costs)
        print(f"  {name}: atores {mean_ms:.2f} ms por quadro em média (pico {peak_ms:.2f} ms)")
        assert mean_ms < 3.0, (name, mean_ms)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        print(fn.__name__)
        fn()
    print("test_cutscenes_fluency: OK")


if __name__ == "__main__":
    main()
