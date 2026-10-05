"""Simulação sem bpy do cérebro da entidade contra um jogador roteirizado.

    python tests/sim_ai.py            # roda todos os cenários, imprime tempo por estado e grava PNGs em out/ai/

O mundo é `LayoutWorldView` (planta, portas que abrem com o tempo), o ruído é o `NoiseSystem` de
verdade e o jogador (`FakePlayer`) anda pela mesma malha de navegação, abre portas e faz o
barulho que o contrato prevê. `tests/test_ai_brain.py` importa estes cenários e confere resultados.
"""
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sem_alvorada import conventions as C  # noqa: E402
from sem_alvorada import layout  # noqa: E402
from sem_alvorada.ai import EntityBrain, LayoutWorldView, NavGrid, Senses  # noqa: E402
from sem_alvorada.ai import nav as nav_module  # noqa: E402
from sem_alvorada.ai.pathfollow import Body, PathFollower  # noqa: E402
from sem_alvorada.ai.worldview import segment_hits_rect  # noqa: E402
from sem_alvorada.audio.noise import NoiseSystem, step_loudness  # noqa: E402

DT = 1.0 / 30.0
GARAGE_HIDEOUT = (16.0, 5.5, 0.0)       # garagem trancada: o jogador "ausente" que ninguém alcança
OUT_DIR = os.path.join(ROOT, "out", "ai")
_SHARED_NAV = []


def shared_nav():
    if not _SHARED_NAV:
        _SHARED_NAV.append(NavGrid.from_layout())
    return _SHARED_NAV[0]


# --------------------------------------------------------------------------
# Jogador roteirizado
# --------------------------------------------------------------------------
class FakePlayer:
    SPEEDS = {"idle": 0.0, "crouch": C.SPEED_CROUCH, "walk": C.SPEED_WALK, "run": C.SPEED_RUN}
    STRIDE = {"crouch": 0.6, "walk": 0.8, "run": 1.3}
    NOISE_KEY = {"crouch": "crouch_walk", "walk": "walk", "run": "run"}

    def __init__(self, world, noise, nav, pos):
        self.world, self.noise, self.nav = world, noise, nav
        layer = nav.layer_at(*pos)
        self.body = Body(pos[0], pos[1], pos[2], layer, 0.0)
        self.follower = PathFollower(world, by="player")
        self.mode = "idle"
        self.crouching = False
        self.flashlight = False
        self.aim = None                      # (x, y, z) que a lanterna mira; None = direção do olhar
        self._stride_left = 0.0
        self._loud_until = 0.0
        self._loud_level = 0.0
        self.clock = 0.0

    @property
    def pos(self):
        return self.body.pos()

    def goto(self, x, y, z, mode="walk"):
        path = self.nav.find_path(self.pos, (x, y, z), lambda _door: 1.0, start_layer=self.body.layer)
        assert path is not None, f"jogador sem caminho até {(x, y, z)}"
        self.follower.set_path(path.points, self.body)
        self.mode = mode
        self.crouching = mode == "crouch"

    def stop(self, crouch=False):
        self.follower.clear()
        self.mode = "idle"
        self.crouching = crouch

    @property
    def moving(self):
        return self.follower.active

    def update(self, dt):
        self.clock += dt
        if not self.follower.active:
            if self.mode != "idle":
                self.mode = "idle"
            return
        before = (self.body.x, self.body.y)
        report = self.follower.step(self.body, self.SPEEDS[self.mode], dt, self.clock)
        moved = report.moved
        if moved > 1e-6:
            self.body.yaw = C.dir_yaw(self.body.x - before[0], self.body.y - before[1])
            self._footsteps(moved)
        if report.arrived:
            self.mode = "idle"

    def _footsteps(self, moved):
        self._stride_left -= moved
        if self._stride_left <= 0.0:
            self._stride_left = self.STRIDE[self.mode]
            surface = self._surface()
            key = self.NOISE_KEY[self.mode]
            loud = step_loudness(key, surface)
            self.noise.emit("player", key, self.pos, loud)
            self._loud_until, self._loud_level = self.clock + 0.6, loud

    def _surface(self):
        if self.body.layer == nav_module.STAIRS:
            return "stairs"
        room = layout.room_at(self.body.x, self.body.y, self.body.z)
        return room.surface if room else "wood"

    def make_noise(self, kind, loudness):
        self.noise.emit("player", kind, self.pos, loudness)
        self._loud_until, self._loud_level = self.clock + 0.6, loudness

    def senses(self, entity_pos):
        if self.aim is not None:
            beam = (self.aim[0] - self.body.x, self.aim[1] - self.body.y, self.aim[2] - (self.body.z + 1.4))
            norm = math.sqrt(sum(v * v for v in beam)) or 1.0
            beam = tuple(v / norm for v in beam)
        else:
            beam = None
        speed = self.SPEEDS[self.mode] if self.follower.active else 0.0
        level = self._loud_level if self.clock < self._loud_until else 0.0
        return Senses(self.pos, self.body.yaw, level, speed, self.crouching, self.flashlight, beam)


# --------------------------------------------------------------------------
# Simulação
# --------------------------------------------------------------------------
class Sim:
    def __init__(self, seed=1, aggression=0, player_at=GARAGE_HIDEOUT, entity_at=layout.ENTITY_SPAWN, hunt=False,
                 entity_yaw=None, entity_pause=0.0):
        self.world = LayoutWorldView()
        self.noise = NoiseSystem(door_openness=self.world.door_openness)
        self.rng = random.Random(seed)
        self.nav = shared_nav()
        self.brain = EntityBrain(self.world, self.noise, self.rng, nav=self.nav)
        self.brain.set_aggression(aggression)
        self.player = FakePlayer(self.world, self.noise, self.nav, player_at)
        self.brain.activate(entity_at, hunt=hunt)
        if entity_yaw is not None:
            self.brain.body.yaw = entity_yaw
        self.brain.pause_left = entity_pause       # como se estivesse numa pausa de patrulha, olhando em frente
        self.time = 0.0
        self.out = None
        self.trace = []            # (t, x, y, z, estado, velocidade, drone, camada)
        self.player_trace = []
        self.state_log = []

    def step(self):
        self.player.update(DT)
        self.world.update(DT)
        self.noise.update(DT)
        self.out = self.brain.update(DT, self.player.senses(self.brain.position))
        self.time += DT
        o = self.out
        self.trace.append((self.time, o.x, o.y, o.z, o.state, o.speed, o.drone, self.brain.body.layer))
        self.player_trace.append(self.player.pos)
        if not self.state_log or self.state_log[-1][1] != o.state:
            self.state_log.append((self.time, o.state))
        return o

    def run(self, seconds, until=None, on_step=None):
        end = self.time + seconds
        while self.time < end:
            out = self.step()
            if on_step:
                on_step(self, out)
            if until and until(self, out):
                return True
        return False

    def states_visited(self):
        return [state for _, state in self.state_log]

    def time_in_state(self):
        return dict(self.brain.stats)

    def rooms_visited(self):
        return sorted(r for r in self.brain.visits)

    def distance_to_player(self):
        px, py, _ = self.player.pos
        return math.hypot(self.out.x - px, self.out.y - py)


# --------------------------------------------------------------------------
# Verificações geométricas sobre um traçado
# --------------------------------------------------------------------------
_WALLS = {level: layout.solid_rects(level) for level in (0, 1)}


def inside_any_wall(x, y, z):
    """O ponto está DENTRO de alguma parede (folga zero)? Usa `layout.solid_rects` do andar da altura z."""
    return any(r.x0 < x < r.x1 and r.y0 < y < r.y1 for r in _WALLS[layout.level_of_z(z)])


def wall_violations(trace):
    """Passos do traçado que estão dentro de uma parede ou cruzam uma (segmentos entre quadros)."""
    bad = []
    for previous, current in zip(trace, trace[1:]):
        level = layout.level_of_z(current[3])
        a, b = (previous[1], previous[2]), (current[1], current[2])
        crossed = False
        if layout.level_of_z(previous[3]) == level and a != b:
            low_x, high_x, low_y, high_y = min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])
            crossed = any(w.x0 < high_x and low_x < w.x1 and w.y0 < high_y and low_y < w.y1
                          and segment_hits_rect(a, b, w) and not _touches_only(a, b, w) for w in _WALLS[level])
        if inside_any_wall(current[1], current[2], current[3]) or crossed:
            bad.append((round(current[0], 2), round(current[1], 2), round(current[2], 2)))
    return bad


def _touches_only(a, b, rect):
    """Segmentos curtos que só encostam na borda (erro numérico) não contam como travessia."""
    inner = layout.Rect(rect.x0 + 0.02, rect.y0 + 0.02, rect.x1 - 0.02, rect.y1 - 0.02)
    return not segment_hits_rect(a, b, inner)


def outside_house(trace):
    return [(round(p[0], 2), round(p[1], 2)) for p in trace if layout.room_at(p[1], p[2], p[3]) is None]


def longest_stillness(trace, states=("patrol", "investigate", "stalk", "chase", "search")):
    """Maior intervalo (s) sem se mover enquanto o estado exigia movimento ou atenção."""
    longest = current = 0.0
    for previous, now in zip(trace, trace[1:]):
        still = math.dist(previous[1:3], now[1:3]) < 1e-4 and now[4] in states
        current = current + (now[0] - previous[0]) if still else 0.0
        longest = max(longest, current)
    return longest


# --------------------------------------------------------------------------
# Cenários
# --------------------------------------------------------------------------
def scenario_patrol(seed=1, seconds=180.0, aggression=0):
    """Jogador ausente (garagem trancada); a entidade patrulha sozinha."""
    sim = Sim(seed, aggression)
    sim.run(seconds)
    return sim


def scenario_investigate(seed=2):
    """Ruído forte-mas-não-tanto de um "jogador falso" no escritório; o jogador de verdade está longe."""
    sim = Sim(seed, entity_at=(6.9, 7.0, 0.0), entity_yaw=C.dir_yaw(0, -1))
    sim.world.set_openness("den_hall", 1.0)
    sim.noise.emit("player", "run", (2.0, 8.0, 0.0), 0.75)
    sim.noise_origin = (2.0, 8.0)
    sim.run(30.0)
    return sim


def scenario_ambient_distraction(seed=3):
    """Telefone tocando na cozinha atrai a entidade que patrulha o hall."""
    sim = Sim(seed, entity_at=(6.9, 6.0, 0.0), entity_yaw=C.dir_yaw(0, 1))
    sim.world.set_openness("kitchen_hall", 1.0)
    sim.noise.emit("ambient", "phone", (10.0, 7.5, 0.9), 0.60, ttl=6.0)
    sim.noise_origin = (10.0, 7.5)
    sim.run(20.0)
    return sim


def scenario_chase_across_floors(seed=4, close_door_behind=True, seconds=70.0):
    """A entidade, já caçando, está ao pé da escada; o jogador, no alto dela, foge até o quarto do casal, fecha a porta e
    espera lá dentro.

    Na escada o ritmo é o dos degraus (C.stairs_speed), tanto para o jogador quanto para a entidade: quem foge pelo plano
    com a entidade a 4 m é alcançado antes de a entidade pisar na escada, então a fuga só tem história quando o jogador já
    está lá em cima."""
    sim = Sim(seed, player_at=(5.6, 8.2, 2.8), entity_at=(5.6, 2.0, 0.0), hunt=True, entity_yaw=C.dir_yaw(0, 1), entity_pause=0.0)
    player = sim.player
    player.flashlight = True
    player.aim = (5.6, 2.0, 1.4)
    phase = {"go": False, "closed": False, "waiting": False}

    def script(s, out):
        if not phase["go"]:
            phase["go"] = True
            player.goto(2.0, 8.6, 2.8, "run")
        if phase["go"] and not phase["closed"] and player.body.layer == nav_module.UPPER and player.body.x < 4.4:
            phase["closed"] = True
            if close_door_behind:
                s.world.close_door("master_hall")
        if phase["closed"] and not player.moving and not phase["waiting"]:
            phase["waiting"] = True
            player.flashlight, player.aim = False, None
        if phase["go"] and not phase["waiting"]:
            player.aim = (out.x, out.y, 1.4)

    sim.run(seconds, until=lambda s, out: out.kill, on_step=script)
    sim.phase = phase
    return sim


def scenario_kill_standing(seed=5, flashlight=True):
    """Jogador parado e à vista; com a lanterna apontada para ela, a entidade o vê de longe."""
    sim = Sim(seed, player_at=(6.9, 2.0, 0.0), entity_at=(6.9, 9.0, 0.0), entity_yaw=C.dir_yaw(0, -1), entity_pause=30.0)
    sim.player.flashlight = flashlight
    sim.player.aim = (6.9, 9.0, 2.2) if flashlight else None
    sim.player.body.yaw = 0.0
    sim.run(40.0, until=lambda s, out: out.kill)
    return sim


def scenario_hide_behind_door(seed=6, lock_after_close=False):
    """Perseguição no andar de cima: o jogador entra no quarto da menina, fecha a porta, corre até o canto
    (o ruído não atravessa a porta fechada) e fica agachado e quieto."""
    sim = Sim(seed, player_at=(5.9, 1.6, 2.8), entity_at=(6.9, 9.0, 2.8), entity_yaw=C.dir_yaw(0, -1), entity_pause=20.0)
    player = sim.player
    player.flashlight = True
    player.aim = (6.9, 9.0, 5.0)
    phase = {"in": False, "closed": False, "hidden": False}

    def script(s, out):
        if not phase["in"] and out.state == "chase":
            phase["in"] = True
            player.aim = None
            player.flashlight = False
            player.goto(3.5, 1.45, 2.8, "run")
        if phase["in"] and not phase["closed"] and player.body.x < 4.0:
            phase["closed"] = True
            s.world.close_door("kids_hall")
            if lock_after_close:          # o quarto da menina tem duas portas: tranca as duas
                s.world.lock("kids_hall")
                s.world.lock("kids_master")
            player.goto(0.6, 4.4, 2.8, "run")
        if phase["closed"] and not player.moving and not phase["hidden"]:
            phase["hidden"] = True
            player.stop(crouch=True)

    sim.run(60.0, on_step=script, until=lambda s, out: out.kill)
    sim.phase = phase
    return sim


def scenario_stalk(seed=7):
    """Jogador agachado e imóvel a 2,8 m da entidade, que está parada olhando na direção dele."""
    sim = Sim(seed, player_at=(6.5, 5.0, 2.8), entity_at=(6.5, 7.8, 2.8), entity_yaw=C.dir_yaw(0, -1), entity_pause=30.0)
    sim.player.stop(crouch=True)
    sim.run(30.0, until=lambda s, out: out.kill)
    return sim


def scenario_wander(seed=8, seconds=300.0, aggression=1, unlock_garage=False):
    """Jogador imortal que vaga pela casa; quando a entidade o mata, ele reaparece longe e ela é reativada."""
    sim = Sim(seed, aggression, player_at=layout.PLAYER_START, entity_at=layout.ENTITY_SPAWN, hunt=True)
    if unlock_garage:
        sim.world.unlock("garage_door")
    rng = random.Random(seed + 100)
    rooms = [r for r in layout.ROOMS if r != "garage"]
    kills = {"count": 0}

    def wander(s, out):
        player = s.player
        if out.kill:
            kills["count"] += 1
            far = max(rooms, key=lambda r: math.dist(layout.ROOMS[r].rect.center, (out.x, out.y)))
            point = s.nav.random_point_in_room(far, rng)
            s.player = FakePlayer(s.world, s.noise, s.nav, point[:3])
            s.brain.activate(s.brain.position, hunt=True)
            return
        if not player.moving and rng.random() < 0.02:
            point = s.nav.random_point_in_room(rng.choice(rooms), rng)
            player.flashlight = rng.random() < 0.5
            player.goto(*point[:3], rng.choice(["walk", "walk", "run", "crouch"]))

    sim.run(seconds, on_step=wander)
    sim.kills = kills["count"]
    return sim


# --------------------------------------------------------------------------
# Relatório e imagens
# --------------------------------------------------------------------------
_STATE_COLORS = {"patrol": (60, 220, 90), "investigate": (240, 220, 60), "stalk": (170, 90, 240),
                 "chase": (255, 50, 50), "search": (60, 220, 240), "attack": (255, 255, 255), "dormant": (90, 90, 90)}


def _plan_image(level, scale=40):
    from tools import pngwrite
    captured = {}
    original = pngwrite.write_png
    pngwrite.write_png = lambda path, image: captured.setdefault("image", image.copy())
    try:
        layout.render_plan("unused.png", scale=scale, level=level)
    finally:
        pngwrite.write_png = original
    return captured["image"]


def write_trajectory_pngs(sim, name, scale=40):
    """Traçado da entidade (cor = estado) e do jogador (magenta) sobre a planta de cada andar."""
    from tools import pngwrite
    os.makedirs(OUT_DIR, exist_ok=True)
    paths = []
    for level in (0, 1):
        image = _plan_image(level, scale)
        height = image.shape[0]

        def plot(x, y, color, size=2):
            px, py = int(round(x * scale)) + 4, height - 4 - int(round(y * scale))
            image[max(py - size // 2, 0):py + size, max(px - size // 2, 0):px + size] = color

        for _, x, y, z, state, *_ in sim.trace[::2]:
            if layout.level_of_z(z) == level:
                plot(x, y, _STATE_COLORS[state])
        for x, y, z in sim.player_trace[::6]:
            if layout.level_of_z(z) == level:
                plot(x, y, (255, 0, 255), 3)
        path = os.path.join(OUT_DIR, f"{name}_andar{level}.png")
        pngwrite.write_png(path, image)
        paths.append(path)
    return paths


def describe(name, sim):
    times = sim.time_in_state()
    total = sum(times.values()) or 1.0
    shares = ", ".join(f"{state} {seconds:5.1f}s ({100 * seconds / total:2.0f}%)" for state, seconds in times.items() if seconds > 0)
    print(f"[{name}] {sim.time:6.1f}s simulados | {shares}")
    print(f"    cômodos visitados: {', '.join(sim.rooms_visited())}")
    print(f"    contadores: {sim.brain.counters} | maior parada: {longest_stillness(sim.trace):.1f}s")


def main():
    scenarios = [
        ("patrulha", scenario_patrol), ("investigar", scenario_investigate),
        ("distracao_telefone", scenario_ambient_distraction), ("perseguicao_andares", scenario_chase_across_floors),
        ("matar_parado", scenario_kill_standing), ("esconder_porta", scenario_hide_behind_door),
        ("espreitar", scenario_stalk), ("vagar", scenario_wander),
    ]
    for name, fn in scenarios:
        sim = fn()
        describe(name, sim)
        write_trajectory_pngs(sim, name)
        print("    sequência:", " -> ".join(f"{s}@{t:.0f}" for t, s in sim.state_log[:14]))
    print(f"PNGs em {OUT_DIR}")


if __name__ == "__main__":
    main()
