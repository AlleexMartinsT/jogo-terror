"""Grava o movimento do JOGO (código real de `engine/` e `cutscenes/`) sem janela, para comparar com a física.

Nada aqui renderiza: roda os mesmos atores e gerenciadores que o jogo roda, com um anfitrião mínimo, e devolve
séries de numpy. As funções são determinísticas (semente fixa), então "antes" e "depois" são comparáveis.
"""
import math
import os
import random
import sys
from types import SimpleNamespace

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from sem_alvorada import layout  # noqa: E402
from sem_alvorada.engine import doors as door_module  # noqa: E402
from sem_alvorada.engine.state import GameState  # noqa: E402

ABERTURA = math.pi / 2


# --------------------------------------------------------------------------
# Portas
# --------------------------------------------------------------------------
class JogoMinimo:
    """O que o DoorManager lê do Game, registrando sons e ruídos com o instante em que aconteceram."""

    def __init__(self, agachado=False, velocidade=2.6, semente=1):
        self.state = GameState()
        self.state.unlocked |= {"front", "back", "garage"}       # as três trancadas
        self.rng = random.Random(semente)
        self.clock = 0.0
        self.player = SimpleNamespace(crouching=agachado, speed=velocidade, x=-50.0, y=-50.0, level=0,
                                      feet=(-50.0, -50.0, 0.0))
        self.sons = []                    # (instante, nome)
        self.ruidos = []
        self.noise = None

    def sound(self, name, pos=None, volume=1.0):
        self.sons.append((self.clock, name))

    def make_noise(self, kind, pos, loudness, sound=None, source="player", opening=""):
        self.ruidos.append((self.clock, kind))
        if sound:
            self.sons.append((self.clock, sound))


class Sempre(random.Random):
    """Sorteio que nunca faz a porta ranger (o ranger não muda o movimento)."""

    def random(self):
        return 0.999999


PASSOS = {"normal": dict(agachado=False, velocidade=2.6, apressado=False),
          "apressado": dict(agachado=False, velocidade=4.6, apressado=True),
          "devagar": dict(agachado=False, velocidade=0.0, apressado=False),
          "agachado": dict(agachado=True, velocidade=1.2, apressado=False)}


def ids_das_portas():
    return [op.id for op in layout.doors()]


def porta(porta_id="kids_master", ritmo="normal", inicio="fechada", inverte_em=None, fps=240.0, segundos=3.5):
    """Abre (ou fecha, com `inicio="aberta"`) uma porta e grava a folha a `fps`.

    `inverte_em`: segundos APÓS o clique em que o jogador aperta E de novo. Devolve um dict de séries:
        t, x (0..1 da abertura), theta (rad), omega (rad/s), alpha (rad/s2), turn (maçaneta/lingueta 0..1)
    mais `sons` [(t, nome)], `duracao` (segundos do planejamento, quando houver) e `t_clique`.
    """
    config = PASSOS[ritmo]
    jogo = JogoMinimo(config["agachado"], config["velocidade"])
    jogo.rng = Sempre()
    manager = door_module.DoorManager(jogo, None)
    door = manager.get(porta_id)
    if inicio == "aberta":
        manager.snap(porta_id, 1.0)
    dt = 1.0 / fps
    n = int(round(segundos * fps))
    t = np.arange(n) * dt
    x = np.zeros(n)
    v = np.zeros(n)
    a = np.zeros(n)
    turn = np.zeros(n)
    resultado = manager.toggle(porta_id, hurried=config["apressado"])
    duracao = door.glide.seconds if door.glide is not None else 0.0
    revertido = False
    for k in range(n):
        if inverte_em is not None and not revertido and k * dt >= inverte_em:
            manager.toggle(porta_id, hurried=config["apressado"])
            revertido = True
        manager.update(dt, None)
        jogo.clock += dt
        x[k], v[k], a[k], turn[k] = door.openness, door.velocity, door.accel, door.turn
    return {"t": t, "x": x, "theta": x * ABERTURA, "omega": v * ABERTURA, "alpha": a * ABERTURA, "turn": turn,
            "sons": jogo.sons, "duracao": duracao, "resultado": resultado, "porta": porta_id, "kind": door.kind,
            "ritmo": ritmo}


# --------------------------------------------------------------------------
# Atores das cutscenes (carro, pêndulos, volante, portão, cortinas, poeira, luzes)
# --------------------------------------------------------------------------
class ObjetoFalso:
    """Só o que os atores leem e escrevem num objeto do Blender."""

    def __init__(self, nome, props=None, malha=None):
        self.name = nome
        self.location = [0.0, 0.0, 0.0]
        self.rotation_euler = (0.0, 0.0, 0.0)
        self.rotation_mode = "XYZ"
        self.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        self.scale = (1.0, 1.0, 1.0)
        self.hide_viewport = self.hide_render = False
        self.data = malha
        self.props = props or {}

    def get(self, chave, padrao=None):
        return self.props.get(chave, padrao)


class _Vertices:
    def __init__(self, coordenadas):
        self.coords = np.asarray(coordenadas, np.float32).reshape(-1, 3)

    def __len__(self):
        return len(self.coords)

    def foreach_get(self, atributo, buffer):
        buffer[:] = self.coords.reshape(-1)

    def foreach_set(self, atributo, valores):
        self.coords = np.asarray(valores, np.float32).reshape(-1, 3).copy()


class MalhaFalsa:
    def __init__(self, coordenadas):
        self.vertices = _Vertices(coordenadas)

    def update(self):
        pass


class AnfitriaoFalso:
    def __init__(self, objetos):
        self.objetos = objetos
        self.scene = None

    def get_object(self, nome):
        return self.objetos.get(nome)

    def player_state(self):
        return (0.0, 0.0, 0.0, 0.0, 1.65)


def anim_antes():
    """O `cutscenes/anim.py` de ANTES da fase 4 (cópia em out/f4_4/tmp/anim.py), carregado como módulo irmão."""
    import importlib.util
    caminho = os.path.join(RAIZ, "out", "f4_4", "tmp", "anim.py")
    spec = importlib.util.spec_from_file_location("sem_alvorada.cutscenes.anim_antes", caminho,
                                                  submodule_search_locations=None)
    modulo = importlib.util.module_from_spec(spec)
    modulo.__package__ = "sem_alvorada.cutscenes"
    spec.loader.exec_module(modulo)
    return modulo


def _palco(objetos):
    from sem_alvorada.cutscenes.stage import Stage
    return Stage(AnfitriaoFalso(objetos))


def rodar_palco(palco, duracao, fps, ao_quadro):
    """Avança os atores do palco quadro a quadro; `ao_quadro(k, t)` colhe os dados."""
    dt = 1.0 / fps
    for k in range(int(round(duracao * fps))):
        palco.t = k * dt
        palco.dt = dt
        palco.update_actors(dt)
        ao_quadro(k, palco.t)
    assert not palco.errors, palco.errors


def carro(duracao=20.0, fps=120.0):
    """O carro da cena final (CarMotion) com o coelhinho, o chaveiro e o volante, como em scene_ending.build()."""
    from sem_alvorada import conventions as C
    from sem_alvorada.cutscenes import anim, scene_ending as E
    nomes = [C.OBJ_CAR, "Car_Wheel_FL", "Car_Wheel_FR", "Car_Wheel_RL", "Car_Wheel_RR", "Cut_Bunny", "Cut_KeyCharm", "Cut_Wheel"]
    objetos = {n: ObjetoFalso(n) for n in nomes}
    cubos = {"FL": (-0.8, 1.45, 0.33), "FR": (0.8, 1.45, 0.33), "RL": (-0.8, -1.45, 0.33), "RR": (0.8, -1.45, 0.33)}
    for lado, posicao in cubos.items():
        objetos[f"Car_Wheel_{lado}"].location = list(posicao)
    palco = _palco(objetos)
    ancora = layout.ANCHORS["car"]
    home = (ancora.x, ancora.y, ancora.z)
    parada = (ancora.x, layout.ENTITY_ROAD_POS[1] + 6.0, ancora.z - 0.054)
    palco.start_actor("car", anim.CarMotion(home, parada, E.MOVE_START, E.MOVE_END, crank_start=E.CRANK, catch=E.CATCH,
                                            lights_on=E.CRANK))
    palco.start_actor("bunny", anim.CharmPendulum("Cut_Bunny", anim.BUNNY_LENGTH, source="car"))
    palco.start_actor("key_charm", anim.CharmPendulum("Cut_KeyCharm", anim.KEY_CHARM_LENGTH, source="car"))
    palco.start_actor("wheel", anim.SteeringWheel("Cut_Wheel"))
    n = int(round(duracao * fps))
    s = {"t": np.zeros(n), "pos": np.zeros((n, 3)), "euler": np.zeros((n, 3)), "coelho": np.zeros((n, 3)),
         "chaveiro": np.zeros((n, 3)), "roda": np.zeros((n, 4, 3)), "roda_pos": np.zeros((n, 4, 3)),
         "volante": np.zeros((n, 4))}
    sinais = {k: np.zeros(n) for k in ("accel", "lateral", "speed", "engine", "steer", "pitch", "roll", "travel")}

    def colhe(k, t):
        s["t"][k] = t
        s["pos"][k] = objetos[C.OBJ_CAR].location
        s["euler"][k] = objetos[C.OBJ_CAR].rotation_euler
        s["coelho"][k] = objetos["Cut_Bunny"].rotation_euler
        s["chaveiro"][k] = objetos["Cut_KeyCharm"].rotation_euler
        s["volante"][k] = objetos["Cut_Wheel"].rotation_quaternion
        for i, lado in enumerate(("FL", "FR", "RL", "RR")):
            s["roda"][k, i] = objetos[f"Car_Wheel_{lado}"].rotation_euler
            s["roda_pos"][k, i] = objetos[f"Car_Wheel_{lado}"].location
        car = palco.signals.get("car", {})
        for chave in sinais:
            sinais[chave][k] = car.get(chave, 0.0)
    rodar_palco(palco, duracao, fps, colhe)
    s["sinais"] = sinais
    s["suspensao"] = _info_suspensao(palco.actors["car"])
    s["comprimentos"] = {"bunny": palco.actors["bunny"]._x.length, "key": palco.actors["key_charm"]._x.length}
    s["fps"] = fps
    s["home"] = home
    s["parada"] = parada
    s["tempos"] = {"move_start": E.MOVE_START, "move_end": E.MOVE_END, "crank": E.CRANK, "catch": E.CATCH}
    return s


def _info_suspensao(ator):
    """Frequências (Hz) e razão de amortecimento da suspensão do ator CarMotion, lidas das molas dele."""
    if hasattr(ator, "_suspension"):                       # meio carro: modos do sistema 2x2 (vertical e arfagem)
        h = ator._suspension
        m, i = 1500.0, h.inertia
        k_zz, k_zt, k_tt = h.k_front + h.k_rear, h.a * h.k_front - h.b * h.k_rear, h.a ** 2 * h.k_front + h.b ** 2 * h.k_rear
        massa = np.array([[m, 0.0], [0.0, i]])
        rigidez = np.array([[k_zz, k_zt], [k_zt, k_tt]])
        autovalores = np.sort(np.linalg.eigvals(np.linalg.solve(massa, rigidez)).real)
        zeta = h.c_front / (2.0 * math.sqrt(h.k_front * m * h.b / (h.a + h.b)))
        roll = ator._roll
        return {"f_vertical": math.sqrt(autovalores[0]) / (2 * math.pi), "f_arfagem": math.sqrt(autovalores[1]) / (2 * math.pi),
                "zeta": zeta, "f_rolagem": math.sqrt(roll.k) / (2 * math.pi), "zeta_rolagem": roll.c / (2 * math.sqrt(roll.k))}
    return {}


def portao(duracao=14.0, fps=120.0):
    """O portão de enrolar da cena final (GarageLift): altura da folha ao longo do tempo."""
    from sem_alvorada import conventions as C
    from sem_alvorada.cutscenes import anim, scene_ending as E
    objeto = ObjetoFalso(C.OBJ_GARAGE_ROLLUP, props={"sa_open_lift": 2.3})
    palco = _palco({C.OBJ_GARAGE_ROLLUP: objeto})
    palco.start_actor("rollup", anim.GarageLift(E.ROLLUP_START, E.ROLLUP_SECONDS))
    n = int(round(duracao * fps))
    z = np.zeros(n)
    t_ = np.zeros(n)

    def colhe(k, t):
        t_[k], z[k] = t, objeto.location[2]
    rodar_palco(palco, duracao, fps, colhe)
    return {"t": t_, "z": z, "fps": fps, "inicio": E.ROLLUP_START, "duracao": E.ROLLUP_SECONDS, "altura": 2.3}


def cortina(duracao=120.0, fps=60.0, forca=0.5, gust=None, nomes=("Curtain_w_master_n", "Curtain_w_master_w"), antes=False):
    """CurtainWind sobre a malha real da cortina do quarto (vértices lidos do .blend). Devolve o deslocamento de
    algumas linhas (altura abaixo da barra) numa coluna do meio e noutra a 1/4 da largura."""
    from sem_alvorada.cutscenes import anim as anim_novo
    from sem_alvorada.cutscenes.curves import Curve
    anim = anim_antes() if antes else anim_novo
    pasta = os.path.join(RAIZ, "out", "f4_4", "tmp")
    objetos = {n: ObjetoFalso(n, malha=MalhaFalsa(np.load(os.path.join(pasta, f"{n}.npy")))) for n in nomes}
    repouso = np.load(os.path.join(pasta, f"{nomes[0]}.npy"))
    palco = _palco(objetos)
    gust = gust or Curve([(0.0, 1.0), (duracao, 1.0)])         # vento constante: o espectro mede a física, não a curva de cena
    palco.start_actor("curtains", anim.CurtainWind(nomes, forca, gust))
    z, x = repouso[:, 2], repouso[:, 0]
    topo, base = float(z.max()), float(z.min())
    fracoes = np.linspace(0.1, 1.0, 10)
    altura_h = (topo - z) / (topo - base)
    colunas_cheias = [xv for xv in np.unique(np.round(x, 2))
                      if (np.abs(x - xv) < 0.02).sum() >= 30 and altura_h[np.abs(x - xv) < 0.02].min() < 0.05
                      and altura_h[np.abs(x - xv) < 0.02].max() > 0.98]              # colunas de ponta a ponta (a malha tem pregas)
    colunas = tuple(min(colunas_cheias, key=lambda c: abs(c - alvo)) for alvo in (0.0, x.min() + 0.25 * (x.max() - x.min())))
    indices = []
    for coluna in colunas:
        mesma = np.nonzero(np.abs(x - coluna) < 0.02)[0]
        indices.append([int(mesma[np.argmin(np.abs(altura_h[mesma] - f))]) for f in fracoes])
    n = int(round(duracao * fps))
    saida = np.zeros((n, 2, len(fracoes), 3))
    t_ = np.zeros(n)
    malha = objetos[nomes[0]].data

    def colhe(k, t):
        t_[k] = t
        deslocado = malha.vertices.coords - repouso
        for c in range(2):
            saida[k, c] = deslocado[indices[c]]
    rodar_palco(palco, duracao, fps, colhe)
    return {"t": t_, "deslocamento": saida, "fracoes": fracoes, "altura": topo - base, "fps": fps,
            "largura": float(x.max() - x.min())}


def poeira(duracao=10.0, fps=60.0, antes=False):
    """DustFall como na cena da garagem: altura de cada partícula e quando ela vive."""
    from sem_alvorada.cutscenes import anim as anim_novo, objects as O
    anim = anim_antes() if antes else anim_novo
    objeto = ObjetoFalso(O.OBJ_DUST, malha=MalhaFalsa(np.zeros((O.DUST_PARTICLES * 4, 3))))
    palco = _palco({O.OBJ_DUST: objeto})
    inicio = 1.0
    ator = anim.DustFall((6.0, 5.0), 1.7, 2.6, 0.0, inicio, 1.8, 2.0, 1.4)
    palco.start_actor("dust", ator)
    n = int(round(duracao * fps))
    z = np.zeros((n, O.DUST_PARTICLES))
    t_ = np.zeros(n)
    tamanho = np.zeros((n, O.DUST_PARTICLES))
    malha = objeto.data

    def colhe(k, t):
        t_[k] = t
        v = malha.vertices.coords.reshape(O.DUST_PARTICLES, 4, 3)
        z[k] = v[:, :, 2].mean(axis=1)
        tamanho[k] = np.ptp(v[:, :, 2], axis=1) / 2.0
    rodar_palco(palco, duracao, fps, colhe)
    return {"t": t_, "z": z, "tamanho": tamanho, "inicio": inicio, "teto": 2.6, "fps": fps}


def luz_cascata(fps=240.0, morte=1.0, modo="die"):
    """Brilho relativo de uma luz na queda em cascata (LightCascade.gain), do tremor à morte."""
    from sem_alvorada.cutscenes import anim
    cascata = anim.LightCascade([("Light_x", morte, modo)])
    t = np.arange(int(round((morte + 1.0) * fps))) / fps
    return {"t": t, "ganho": np.array([cascata.gain(x, morte, modo) for x in t]), "morte": morte, "fps": fps}


def luz_pisca(quantidade, semente, tipo="ceiling", duracao=120.0, fps=240.0):
    """Brilho relativo de uma luz que pisca, pela função que o `LightManager` usa para o tipo (`quantidade` de 0 a 1)."""
    from sem_alvorada.engine import lights
    funcao = {"fluorescent": getattr(lights, "burst_flicker_gain", lights.flicker_gain),
              "tv": getattr(lights, "tv_gain", lights.flicker_gain)}.get(tipo, lights.flicker_gain)
    t = np.arange(int(round(duracao * fps))) / fps
    return {"t": t, "ganho": np.array([funcao(x, quantidade, semente) for x in t]), "fps": fps, "quantidade": quantidade,
            "tipo": tipo}


def luz_liga_desliga(tipo="ceiling", fps=240.0):
    """Energia de uma luz de verdade do LightManager quando a energia da casa cai (t=0,5 s) e volta (t=1,5 s)."""
    from sem_alvorada.engine import lights
    nome = "Light_kitchen_c0"
    luz = ObjetoFalso(nome, props={"sa_room": "kitchen", "sa_base_energy": 100.0, "sa_flicker": 0.0, "sa_kind": tipo},
                      malha=SimpleNamespace(energy=100.0, users=1))
    luz.type = "LIGHT"
    gerente = lights.LightManager(SimpleNamespace(objects=[luz]))
    dt = 1.0 / fps
    n = int(round(3.0 * fps))
    energia = np.zeros(n)
    for k in range(n):
        if k == int(0.5 * fps):
            gerente.set_power(False)
        if k == int(1.5 * fps):
            gerente.set_power(True)
        gerente.update(dt, "kitchen")
        energia[k] = luz.data.energy
    return {"t": np.arange(n) * dt, "energia": energia, "base": 100.0, "tipo": tipo, "fps": fps}


def luzes():
    return {"cascata": luz_cascata(),
            "pisca": {"fluorescente_garagem": luz_pisca(0.25, 1.9, "fluorescent"),
                      "fluorescente_cozinha": luz_pisca(0.10, 3.6, "fluorescent"),
                      "tv": luz_pisca(0.7, 5.3, "tv"), "abajur": luz_pisca(0.1, 7.1, "lamp"),
                      "apagao": luz_pisca(0.65, 8.8, "ceiling")},
            "liga_desliga": {tipo: luz_liga_desliga(tipo) for tipo in ("ceiling", "lamp", "fluorescent")}}


def relogio(duracao=60.0, fps=60.0):
    """O mecanismo do relógio de pé (engine/clockwork.py): ângulo do pêndulo, posição do ponteiro dos segundos e os tiques.

    O laço de áudio `amb_clock_tick` começa em t = 0 (a fase é sincronizada nesse instante, como o Ambience faz) e tem um tique
    em 0,5 s, 1,5 s, 2,5 s..."""
    from sem_alvorada.engine import clockwork
    pendulo, ponteiro = ObjetoFalso(clockwork.PENDULUM), ObjetoFalso(clockwork.SECOND_HAND)
    cena = SimpleNamespace(objects={clockwork.PENDULUM: pendulo, clockwork.SECOND_HAND: ponteiro})
    mecanismo = clockwork.ClockWork(cena)
    mecanismo.update(1.0 / fps)                      # um quadro antes do laço (o pêndulo já vinha balançando)
    for _ in range(37):
        mecanismo.update(1.0 / fps)
    mecanismo.sync()
    mecanismo.time = 0.0
    n = int(duracao * fps)
    t = (np.arange(n) + 1) / fps                    # o estado gravado no quadro k é o do fim dele
    theta, mao = np.zeros(n), np.zeros(n)
    tiques = []
    ultimo = None
    for k in range(n):
        mecanismo.update(1.0 / fps)
        theta[k] = pendulo.rotation_euler[1]
        mao[k] = -ponteiro.rotation_euler[1]
        if mecanismo.last_tick is not None and mecanismo.last_tick != ultimo:
            ultimo = mecanismo.last_tick
            tiques.append(ultimo)
    return {"t": t, "theta": theta, "mao": mao, "tiques": np.array(tiques), "fps": fps,
            "equivalente": clockwork.EQUIVALENT_LENGTH, "amplitude": clockwork.AMPLITUDE}
