"""Métricas de movimento sobre `Movimento` (movimento.py): as mesmas funções para mocap real e para gravação do jogo.

Numpy puro. Nada aqui sabe de onde vêm as posições; por isso a comparação real x jogo é direta.

    marcha = medir_marcha(movimento)             # Marcha: .v (escalares), .curvas (por % do ciclo), .eventos
    linhas = comparar_metricas(marcha_real.v, marcha_jogo.v)       # tabela com diferença e tolerância
    perfil = perfil_mao(movimento, "d"); alcances = detectar_alcances(perfil)
    ajuste = ajuste_jerk_minimo(perfil, *alcances[0])
    w = velocidade_angular_cabeca(movimento)

Definições (todas sobre posições, para não depender de como cada esqueleto guarda rotações):

    contato do pé        o pé está "no chão" quando o ponto mais baixo entre tornozelo e bola do pé está a menos de
                         `tol_altura` do chão E a menor velocidade horizontal dos dois é menor que `tol_vel`.
                         Tornozelo baixo cobre o calcanhar, bola baixa cobre a ponta; juntos cobrem o rolamento.
    toque do calcanhar   primeiro quadro de um contato; saída do pé: primeiro quadro depois dele
    passada              distância horizontal entre dois toques sucessivos do mesmo pé
    passo                distância, na direção do avanço, entre os tornozelos no toque de um pé (à frente) e o outro (atrás)
    cadência             passos por minuto = 60 / intervalo médio entre toques sucessivos de pés opostos
    apoio                tempo de contato do pé / tempo da passada
    duplo apoio          tempo com os dois pés em contato. "passo_pct" é cada um dos dois duplos apoios da passada, em % da
                         passada (o "~10%" dos livros); "ciclo_pct" é o total (~20%)
    deslize do pé        deslocamento horizontal de um ponto do pé (tornozelo, bola, ponta) enquanto ele está encostado no
                         chão, por apoio (0 = pé fixo)
    ângulos              no plano sagital do corpo (frente suavizada x vertical); hip e joelho positivos = flexão,
                         tornozelo positivo = dorsiflexão (zero com o pé plano e a canela vertical), tronco positivo = inclinado
                         para a frente em relação ao repouso do esqueleto (`Movimento.meta["tronco_repouso"]`)
    ciclo                de um toque do calcanhar ao seguinte do mesmo pé, reamostrado em 101 pontos (0..100 %)
"""
from dataclasses import dataclass, field

import numpy as np

from .movimento import ALTURA_TORNOZELO, INDICE

CICLO_PONTOS = 101
ALTURA_BOLA = 0.040                  # a bola do pé do Daniel, no chão (Toe.L, skeleton.py)
ALTURA_PONTA = 0.035                 # a ponta do pé (tail de Toe.L)
PERNA_REFERENCIA = 0.85              # quadril-tornozelo do Daniel em pé (m): as tolerâncias de altura escalam com isto
NAN = float("nan")


# --------------------------------------------------------------------------
# Sinais básicos
# --------------------------------------------------------------------------
def gaussiano(sinal, sigma_s, fps):
    """Suaviza ao longo do eixo 0 com um núcleo gaussiano (bordas espelhadas)."""
    sigma = sigma_s * fps
    if sigma < 0.3 or len(sinal) < 3:
        return np.asarray(sinal, float)
    raio = int(np.ceil(3.0 * sigma))
    kernel = np.exp(-0.5 * (np.arange(-raio, raio + 1) / sigma) ** 2)
    kernel /= kernel.sum()
    sinal = np.asarray(sinal, float)
    plano = sinal.reshape(len(sinal), -1)
    raio = min(raio, len(plano) - 1)
    kernel = kernel[len(kernel) // 2 - raio: len(kernel) // 2 + raio + 1]
    kernel /= kernel.sum()
    saida = np.empty_like(plano)
    for coluna in range(plano.shape[1]):
        preenchido = np.pad(plano[:, coluna], raio, mode="reflect")
        saida[:, coluna] = np.convolve(preenchido, kernel, mode="valid")
    return saida.reshape(sinal.shape)


def derivada(sinal, fps):
    return np.gradient(np.asarray(sinal, float), axis=0) * fps


def velocidade_horizontal(pos, fps, suavizar_s=0.03):
    return np.linalg.norm(derivada(gaussiano(pos, suavizar_s, fps), fps)[:, :2], axis=1)


def _angulo_assinado_2d(a, b):
    """Ângulo de `a` para `b` no plano XY, positivo no sentido anti-horário visto de cima (graus)."""
    return np.degrees(np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], (a * b).sum(axis=1)))


def _unitario(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def _sagital(vetor, frente):
    """(componente à frente, componente vertical) de vetores [T,3] no plano sagital definido por `frente` [T,2]."""
    return (vetor[:, :2] * frente).sum(axis=1), vetor[:, 2]


# --------------------------------------------------------------------------
# Chão, contatos e eventos
# --------------------------------------------------------------------------
def comprimento_perna(mov):
    """Quadril-tornozelo médio em pé (m): ancora tolerâncias e normalizações ao tamanho da pessoa."""
    total = 0.0
    for lado in "ed":
        total += (np.linalg.norm(mov.j(f"coxa_{lado}") - mov.j(f"joelho_{lado}"), axis=1).mean()
                  + np.linalg.norm(mov.j(f"joelho_{lado}") - mov.j(f"tornozelo_{lado}"), axis=1).mean())
    return total / 2.0


def estimar_piso(mov):
    """z com o pé plano no chão, como (tornozelo, bola, ponta). Com `mov.piso` conhecido usa as alturas do Daniel;
    sem ele, o percentil 5 da altura (o pé passa ao menos 5% do tempo plano em qualquer marcha)."""
    if mov.piso is not None:
        return mov.piso + ALTURA_TORNOZELO, mov.piso + ALTURA_BOLA, mov.piso + ALTURA_PONTA
    saida = []
    for junta in ("tornozelo", "bola", "ponta"):
        alturas = np.concatenate([mov.j(f"{junta}_e")[:, 2], mov.j(f"{junta}_d")[:, 2]])
        saida.append(float(np.percentile(alturas, 5)))
    return tuple(saida)


def altura_do_piso(mov):
    """z do chão sob a pessoa (m), coerente com `estimar_piso`."""
    return estimar_piso(mov)[0] - ALTURA_TORNOZELO


def _limpar(mascara, fps, minimo_ligado=0.06, minimo_desligado=0.04):
    """Remove contatos mais curtos que `minimo_ligado` e fecha vãos menores que `minimo_desligado` (segundos)."""
    saida = mascara.copy()
    for valor, minimo in ((False, minimo_desligado), (True, minimo_ligado)):
        corridas = _corridas(saida == valor)
        for a, b in corridas:
            if a == 0 or b == len(saida):
                continue                       # as pontas do recorte não são curtas por causa do recorte
            if (b - a) / fps < minimo:
                saida[a:b] = not valor
    return saida


def _corridas(mascara):
    """Pares (início, fim exclusivo) de cada trecho de True."""
    if len(mascara) == 0:
        return []
    d = np.diff(np.concatenate([[0], mascara.astype(int), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def _tres_pontos(mov, lado):
    """Alturas relativas ao chão e velocidades horizontais de tornozelo, bola e ponta do pé: ([3, T], [3, T])."""
    piso = estimar_piso(mov)
    alturas, velocidades = [], []
    for junta, base in zip(("tornozelo", "bola", "ponta"), piso):
        trajeto = mov.j(f"{junta}_{lado}")
        alturas.append(trajeto[:, 2] - base)
        velocidades.append(velocidade_horizontal(trajeto, mov.fps))
    return np.array(alturas), np.array(velocidades)


def contatos_por_altura(mov, lado, tol_altura=None, tol_vel=None):
    """Máscara [T] de pé em contato, só por altura e velocidade (independe do ritmo da marcha; serve a estágios
    sem passada, como ficar em pé ou subir degraus). Veja `eventos_marcha` para os eventos da marcha."""
    escala = comprimento_perna(mov) / PERNA_REFERENCIA
    tol_altura = 0.030 * escala if tol_altura is None else tol_altura
    tol_vel = 0.5 * escala if tol_vel is None else tol_vel
    alturas, velocidades = _tres_pontos(mov, lado)
    return _limpar((alturas.min(axis=0) < tol_altura) & (velocidades.min(axis=0) < tol_vel), mov.fps)


def pe_plano(mov, lado, tol_altura=None):
    """Máscara [T] com tornozelo, bola e ponta do pé perto do chão ao mesmo tempo."""
    escala = comprimento_perna(mov) / PERNA_REFERENCIA
    tol_altura = 0.022 * escala if tol_altura is None else tol_altura
    alturas, _ = _tres_pontos(mov, lado)
    return alturas.max(axis=0) < tol_altura


def _picos(sinal, fps, proeminencia, distancia_s=0.30, janela_s=0.55):
    """Índices dos máximos locais de `sinal` com proeminência mínima, afastados por `distancia_s`. Os extremos do
    recorte não valem como pico: não dá para saber se continuariam subindo."""
    n = len(sinal)
    meia = max(1, int(round(distancia_s * fps / 2)))
    larga = max(meia + 1, int(round(janela_s * fps)))
    candidatos = []
    for i in range(meia, n - meia):
        trecho = sinal[i - meia:i + meia + 1]
        if i != i - meia + int(np.argmax(trecho)):
            continue
        esquerda = sinal[max(0, i - larga):i + 1].min()
        direita = sinal[i:min(n, i + larga + 1)].min()
        if sinal[i] - max(esquerda, direita) >= proeminencia:
            candidatos.append(i)
    return np.array(candidatos, int)


def _eventos_zeni(mov):
    """Toque do calcanhar e saída do pé: candidatos por Zeni et al. (2008) refinados pela altura do pé.

    Candidato: toque = tornozelo no ponto mais à frente do quadril, saída = ponta do pé no ponto mais atrás. Esses
    pontos acontecem um pouco antes do pouso e um pouco depois do descolar (o pé ainda recua em relação ao quadril
    enquanto acelera para o balanço), o que alongaria o apoio em ~5 pontos. O refino procura perto de cada candidato
    o quadro em que o pé de fato encosta (algum ponto a menos de ~3 cm do chão) e o último em que a bola ou a ponta
    ainda estão no chão."""
    _inst, frente = frentes(mov)
    quadril = mov.j("quadril")[:, :2]
    escala = comprimento_perna(mov) / PERNA_REFERENCIA
    proeminencia = 0.10 * escala
    fps = mov.fps
    toque, saida = {}, {}
    for lado in "ed":
        a = ((mov.j(f"tornozelo_{lado}")[:, :2] - quadril) * frente).sum(axis=1)
        b = ((mov.j(f"ponta_{lado}")[:, :2] - quadril) * frente).sum(axis=1)
        a, b = gaussiano(a, 0.02, fps), gaussiano(b, 0.02, fps)
        candidatos_toque, candidatos_saida = _picos(a, fps, proeminencia), _picos(-b, fps, proeminencia)
        alturas, _velocidades = _tres_pontos(mov, lado)
        n = mov.quadros
        refinados = []
        for c in candidatos_toque:
            janela = np.arange(max(0, c - int(0.05 * fps)), min(n, c + int(0.30 * fps)))
            no_chao = janela[alturas[:, janela].min(axis=0) < 0.032 * escala]
            refinados.append(int(no_chao[0]) if len(no_chao) else int(c))
        toque[lado] = np.array(sorted(set(refinados)), int)
        refinados = []
        for c in candidatos_saida:
            janela = np.arange(max(0, c - int(0.25 * fps)), min(n, c + 1))
            no_chao = janela[alturas[1:, janela].min(axis=0) < 0.020 * escala]
            refinados.append(int(no_chao[-1]) + 1 if len(no_chao) else int(c))
        saida[lado] = np.array(sorted(set(refinados)), int)
    return toque, saida


@dataclass
class Eventos:
    """Toques do calcanhar e saídas do pé, em índices de quadro, por lado ("e", "d")."""
    toque: dict
    saida: dict
    contato: dict
    fps: float

    def tempos(self, tipo, lado):
        return getattr(self, tipo)[lado] / self.fps

    def todos_toques(self):
        """[(índice, lado)] ordenado no tempo."""
        pares = [(int(i), lado) for lado in "ed" for i in self.toque[lado]]
        return sorted(pares)


FROUDE_CORRIDA = 0.7          # v²/(g·perna): o ser humano troca andar por correr perto de 0,5; 0,7 já é corrida franca
LIMIAR_ALTURA_CORRIDA = (0.045, 1.0)       # (m escalado pela perna, m/s) do método "altura"


def eventos_marcha(mov, metodo="auto"):
    """Toques, saídas e máscaras de contato.

    "zeni": posição do pé em relação ao quadril (toque = tornozelo mais à frente, saída = ponta mais atrás). Vale
            para caminhada; na corrida acusa o fim do balanço, antes do contato.
    "altura": pé em contato quando o ponto mais baixo está perto do chão e lento. Vale para corrida (mede o voo);
            na caminhada falha nas pontas do apoio, onde o calcanhar e a ponta ainda mal descolam do piso.
    "auto": "altura" se o número de Froude (v²/(g·perna)) passa de `FROUDE_CORRIDA`, senão "zeni". Um jogo que "anda"
            depressa demais cai em "altura": um cenário que quer medir sua caminhada como caminhada passa `metodo="zeni"`."""
    if metodo == "auto":
        quadril = mov.j("quadril")
        velocidade = np.linalg.norm(quadril[-1, :2] - quadril[0, :2]) / max(mov.duracao, 1e-9)
        froude = velocidade ** 2 / (9.81 * comprimento_perna(mov))
        metodo = "altura" if froude > FROUDE_CORRIDA else "zeni"
    if metodo == "zeni":
        toque, saida = _eventos_zeni(mov)
        contato = {}
        for lado in "ed":
            mascara = np.zeros(mov.quadros, bool)
            for t in toque[lado]:
                depois = saida[lado][saida[lado] > t]
                proximo = toque[lado][toque[lado] > t]
                fim = depois[0] if len(depois) else mov.quadros
                if len(proximo) and fim > proximo[0]:
                    fim = t                                     # sem saída antes do toque seguinte: apoio sem dado
                mascara[t:fim] = True
            antes = saida[lado][saida[lado] < (toque[lado][0] if len(toque[lado]) else mov.quadros)]
            if len(antes) and (not len(toque[lado]) or antes[0] < toque[lado][0]):
                mascara[:antes[0]] = True                         # apoio já em curso no primeiro quadro
            contato[lado] = mascara
        return Eventos(toque, saida, contato, mov.fps)
    toque, saida, contato = {}, {}, {}
    escala = comprimento_perna(mov) / PERNA_REFERENCIA
    for lado in "ed":
        mascara = contatos_por_altura(mov, lado, LIMIAR_ALTURA_CORRIDA[0] * escala, LIMIAR_ALTURA_CORRIDA[1])
        contato[lado] = mascara
        corridas = _corridas(mascara)
        # um contato que já existia no primeiro quadro (ou segue no último) não tem toque (saída) observado
        toque[lado] = np.array([a for a, b in corridas if a > 0], int)
        saida[lado] = np.array([b for a, b in corridas if b < len(mascara)], int)
    return Eventos(toque, saida, contato, mov.fps)


# --------------------------------------------------------------------------
# Referencial do corpo e ângulos
# --------------------------------------------------------------------------
def frentes(mov, suavizar_s=0.5):
    """(frente da pelve instantânea [T,2], frente suavizada [T,2]): a segunda é o rumo, sem a rotação da pelve."""
    direita = (mov.j("coxa_d") - mov.j("coxa_e"))[:, :2]
    instantanea = _unitario(np.stack([-direita[:, 1], direita[:, 0]], axis=1))
    suave = _unitario(gaussiano(instantanea, suavizar_s, mov.fps))
    return instantanea, suave


def angulos(mov):
    """Dict de séries [T] em graus. Veja o topo do módulo para as definições."""
    _inst, f = frentes(mov)
    saida = {}
    tronco = mov.j("c7") - mov.j("lombar")
    tf, tz = _sagital(tronco, f)
    # o eixo lombar -> base do pescoço não é vertical em nenhum esqueleto em repouso (CMU 0,5 grau, Daniel 2 graus à
    # frente): a inclinação é medida a partir do repouso de cada um (`meta["tronco_repouso"]`)
    inclinacao_tronco = np.degrees(np.arctan2(tf, tz)) - mov.meta.get("tronco_repouso", 0.0)
    saida["tronco_incl"] = inclinacao_tronco
    for lado in "ed":
        coxa, joelho = mov.j(f"coxa_{lado}"), mov.j(f"joelho_{lado}")
        tornozelo, bola = mov.j(f"tornozelo_{lado}"), mov.j(f"bola_{lado}")
        cf, cz = _sagital(joelho - coxa, f)
        coxa_incl = np.degrees(np.arctan2(cf, -cz))
        sf, sz = _sagital(tornozelo - joelho, f)
        canela_incl = np.degrees(np.arctan2(sf, -sz))
        pf, pz = _sagital(bola - tornozelo, f)
        pe_incl = np.degrees(np.arctan2(pz, pf))
        plano = pe_plano(mov, lado)
        repouso = np.median(pe_incl[plano]) if plano.any() else np.median(pe_incl)
        saida[f"quadril_{lado}"] = coxa_incl + inclinacao_tronco
        saida[f"joelho_{lado}"] = coxa_incl - canela_incl
        saida[f"tornozelo_{lado}"] = pe_incl - canela_incl - repouso
        af, az = _sagital(mov.j(f"cotovelo_{lado}") - mov.j(f"ombro_{lado}"), f)
        saida[f"ombro_{lado}"] = np.degrees(np.arctan2(af, -az))
        cima = _unitario(mov.j(f"ombro_{lado}") - mov.j(f"cotovelo_{lado}"))
        baixo = _unitario(mov.j(f"punho_{lado}") - mov.j(f"cotovelo_{lado}"))
        saida[f"cotovelo_{lado}"] = 180.0 - np.degrees(np.arccos(np.clip((cima * baixo).sum(axis=1), -1, 1)))
    inst_pelve, _ = frentes(mov)
    ombros = (mov.j("ombro_d") - mov.j("ombro_e"))[:, :2]
    inst_torax = _unitario(np.stack([-ombros[:, 1], ombros[:, 0]], axis=1))
    saida["pelve_rot"] = _angulo_assinado_2d(f, inst_pelve)
    saida["torax_rot"] = _angulo_assinado_2d(f, inst_torax)
    return saida


# --------------------------------------------------------------------------
# Ciclos e curvas
# --------------------------------------------------------------------------
@dataclass
class Curva:
    """Uma grandeza ao longo do ciclo: `ciclos` é [n, 101], um por passada observada."""
    ciclos: np.ndarray
    unidade: str = ""

    @property
    def media(self):
        return self.ciclos.mean(axis=0) if len(self.ciclos) else np.full(CICLO_PONTOS, NAN)

    @property
    def desvio(self):
        return self.ciclos.std(axis=0) if len(self.ciclos) > 1 else np.zeros(CICLO_PONTOS)

    @property
    def n(self):
        return len(self.ciclos)

    @staticmethod
    def juntar(curvas):
        """Junta os ciclos de várias gravações (por exemplo vários clipes reais) numa só faixa."""
        partes = [c.ciclos for c in curvas if len(c.ciclos)]
        unidade = curvas[0].unidade if curvas else ""
        return Curva(np.concatenate(partes) if partes else np.zeros((0, CICLO_PONTOS)), unidade)


def normalizar_ciclo(sinal, inicio, fim):
    """Reamostra sinal[inicio:fim+1] em 101 pontos (0..100 % do ciclo)."""
    x = np.arange(inicio, fim + 1)
    alvo = np.linspace(inicio, fim, CICLO_PONTOS)
    return np.interp(alvo, x, np.asarray(sinal, float)[inicio:fim + 1])


def _ciclos_de(sinal, eventos, lado, espelho=1.0, remover="nada"):
    saida = []
    toques = eventos.toque[lado]
    for a, b in zip(toques[:-1], toques[1:]):
        if b - a < 3:
            continue
        ciclo = normalizar_ciclo(sinal, a, b) * espelho
        if remover == "media":
            ciclo = ciclo - ciclo.mean()
        elif remover == "linha":
            ciclo = ciclo - np.linspace(ciclo[0], ciclo[-1], CICLO_PONTOS)
            ciclo = ciclo - ciclo.mean()
        saida.append(ciclo)
    return np.array(saida).reshape(-1, CICLO_PONTOS)


def _curva_dois_lados(nome_e, nome_d, series, eventos, espelhar=False, remover="nada", unidade="graus"):
    e = _ciclos_de(series[nome_e], eventos, "e", 1.0, remover)
    d = _ciclos_de(series[nome_d], eventos, "d", -1.0 if espelhar else 1.0, remover)
    return Curva(np.concatenate([e, d]), unidade)


def _eixo_lateral(frente):
    return np.stack([frente[:, 1], -frente[:, 0]], axis=1)


@dataclass
class Marcha:
    v: dict = field(default_factory=dict)
    curvas: dict = field(default_factory=dict)
    eventos: Eventos = None
    series: dict = field(default_factory=dict)


def medir_marcha(mov, metodo="auto"):
    """Todas as métricas de marcha/corrida de um `Movimento`. Sem passadas completas, os campos de ritmo ficam NaN.
    `metodo`: veja `eventos_marcha` ("zeni" para medir uma caminhada, "altura" para uma corrida)."""
    fps = mov.fps
    eventos = eventos_marcha(mov, metodo)
    series = angulos(mov)
    _inst, frente = frentes(mov)
    v = {chave: NAN for chave in CAMPOS_MARCHA}
    quadril = mov.j("quadril")
    piso = altura_do_piso(mov)
    v["quadril_altura"] = float(np.mean(quadril[:, 2] - piso))
    v["perna"] = float(comprimento_perna(mov))
    toques = eventos.todos_toques()
    v["n_toques"] = float(len(toques))

    cabeca = mov.cabeca_pos()
    janelas_passo = [(a, b) for (a, la), (b, lb) in zip(toques[:-1], toques[1:]) if la != lb and b - a >= 3]
    if len(toques) >= 3:
        primeiro, ultimo = toques[0][0], toques[-1][0]
        tempo = (ultimo - primeiro) / fps
        if tempo > 0:
            # comprimento do trajeto do quadril no chão (levemente suavizado, o clipe todo, para a borda não encolher o
            # trecho) por tempo: vale em linha reta, em curva e em passos laterais
            trajeto = gaussiano(quadril[:, :2], 0.08, fps)[primeiro:ultimo + 1]
            v["velocidade"] = float(np.linalg.norm(np.diff(trajeto, axis=0), axis=1).sum() / tempo)
        intervalos = np.array([(b - a) / fps for (a, la), (b, lb) in zip(toques[:-1], toques[1:]) if la != lb])
        if len(intervalos):
            v["cadencia"] = float(60.0 / intervalos.mean())
        v.update(_passos_e_passadas(mov, eventos, frente))
        v.update(_fases_apoio(mov, eventos, toques))
        v.update(_deslize(mov, eventos))
    v.update(_oscilacoes(mov, cabeca, quadril, frente, eventos, janelas_passo, piso))

    curvas = {}
    if eventos.toque["e"].size > 1 or eventos.toque["d"].size > 1:
        for grandeza in ("quadril", "joelho", "tornozelo", "ombro", "cotovelo"):
            curvas[grandeza] = _curva_dois_lados(f"{grandeza}_e", f"{grandeza}_d", series, eventos)
        for grandeza in ("pelve_rot", "torax_rot"):
            curvas[grandeza] = _curva_dois_lados(grandeza, grandeza, series, eventos, espelhar=True)
        curvas["tronco_incl"] = _curva_dois_lados("tronco_incl", "tronco_incl", series, eventos)
        series["cabeca_z"] = cabeca[:, 2]
        series["quadril_z"] = quadril[:, 2] - piso
        lateral = _eixo_lateral(frente)
        series["cabeca_x"] = ((cabeca[:, :2] - cabeca[0, :2]) * lateral).sum(axis=1)
        curvas["cabeca_z"] = _curva_dois_lados("cabeca_z", "cabeca_z", series, eventos, remover="media", unidade="m")
        curvas["quadril_z"] = _curva_dois_lados("quadril_z", "quadril_z", series, eventos, remover="media", unidade="m")
        curvas["cabeca_x"] = _curva_dois_lados("cabeca_x", "cabeca_x", series, eventos, espelhar=True, remover="linha",
                                              unidade="m")
        v.update(_extremos_articulares(curvas))
    return Marcha(v, curvas, eventos, series)


def _maior_corrida(mascara, minimo=3):
    corridas = [(a, b) for a, b in _corridas(mascara) if b - a >= minimo]
    return max(corridas, key=lambda par: par[1] - par[0]) if corridas else None


def apoios(mov, eventos):
    """Um registro por apoio completo (toque e saída observados): lado, toque, saída, onde o tornozelo pousou
    ("pegada") e o deslize.

    Deslize: tornozelo, bola e ponta do pé são, cada um, "pontos de apoio" enquanto estão a menos de 2,2 cm (escalado
    pela perna) do chão. Um ponto realmente apoiado não anda; o maior deslocamento horizontal que algum deles faz
    durante o miolo (sem 15% de cada ponta) do seu trecho apoiado é o deslize do apoio, e a maior velocidade
    que ele tem ali, a velocidade do pé."""
    fps = mov.fps
    escala = comprimento_perna(mov) / PERNA_REFERENCIA
    limite = 0.022 * escala
    registros = []
    for lado in "ed":
        trajetos = [mov.j(f"{junta}_{lado}") for junta in ("tornozelo", "bola", "ponta")]
        alturas, velocidades = _tres_pontos(mov, lado)
        for t in eventos.toque[lado]:
            depois = eventos.saida[lado][eventos.saida[lado] > t]
            if not len(depois):
                continue
            s = int(depois[0])
            proximo = eventos.toque[lado][eventos.toque[lado] > t]
            if len(proximo) and proximo[0] < s:
                continue
            deslizes, picos, janelas = [], [], []
            for trajeto, altura, velocidade in zip(trajetos, alturas, velocidades):
                corrida = _maior_corrida(altura[t:s + 1] < limite)
                if corrida is None:
                    continue
                a, b = t + corrida[0], t + corrida[1] - 1
                corte = int(0.15 * (b - a))                     # as pontas do trecho são o pé pousando e saindo
                a, b = a + corte, b - corte
                deslizes.append(float(np.linalg.norm((trajeto[b] - trajeto[a])[:2])))
                picos.append(float(velocidade[a:b + 1].max()))
                janelas.append((a, b))
            plano = bool(deslizes)
            if plano:
                a, b = janelas[0]                              # a pegada é do tornozelo, mesmo que ele fique no ar
            else:
                a, b = t + int(0.25 * (s - t)), t + int(0.60 * (s - t))
            registros.append({"lado": lado, "toque": int(t), "saida": s, "janela": (a, b),
                              "pegada": trajetos[0][(a + b) // 2, :2].copy(), "plano": plano,
                              "deslize": max(deslizes) if plano else NAN, "velocidade": max(picos) if plano else NAN})
    return sorted(registros, key=lambda r: r["toque"])


def _passos_e_passadas(mov, eventos, frente):
    """Passada: mesma pegada do mesmo pé, de um apoio ao seguinte. Passo: de uma pegada à do pé oposto, na direção do
    avanço. A pegada é a posição do tornozelo com o pé plano: tira a diferença entre calcanhar e tornozelo."""
    saida = {}
    registros = apoios(mov, eventos)
    passadas = []
    for lado in "ed":
        proprios = [r for r in registros if r["lado"] == lado]
        for a, b in zip(proprios[:-1], proprios[1:]):
            passadas.append(np.linalg.norm(b["pegada"] - a["pegada"]))
    if passadas:
        saida["passada"] = float(np.mean(passadas))
    passos, larguras = [], []
    for a, b in zip(registros[:-1], registros[1:]):
        if a["lado"] == b["lado"]:
            continue
        rumo = frente[(b["toque"] + a["toque"]) // 2]
        dif = b["pegada"] - a["pegada"]
        passos.append(float(dif @ rumo))
        larguras.append(abs(float(dif @ np.array([rumo[1], -rumo[0]]))))
    if passos:
        saida["passo"] = float(np.mean(passos))
        saida["largura_passo"] = float(np.mean(larguras))
    return saida


def _fases_apoio(mov, eventos, toques):
    fps = mov.fps
    saida = {}
    apoios, duplos, voos = [], [], []
    for lado in "ed":
        t, s = eventos.toque[lado], eventos.saida[lado]
        for a, b in zip(t[:-1], t[1:]):
            fim = s[(s > a) & (s < b)]
            if len(fim):
                apoios.append((fim[0] - a) / (b - a))
    if apoios:
        saida["apoio_pct"] = float(100.0 * np.mean(apoios))
    primeiro, ultimo = toques[0][0], toques[-1][0]
    if ultimo > primeiro:
        janela = slice(primeiro, ultimo)
        e, d = eventos.contato["e"][janela], eventos.contato["d"][janela]
        duplo = float(np.mean(e & d))
        voo = float(np.mean(~e & ~d))
        intervalos = [(b - a) / fps for (a, la), (b, lb) in zip(toques[:-1], toques[1:]) if la != lb]
        passos_por_s = len(intervalos) / max(sum(intervalos), 1e-9)
        saida["duplo_apoio_ciclo_pct"] = 100.0 * duplo
        saida["duplo_apoio_passo_pct"] = 100.0 * duplo / 2.0     # dois duplos apoios por ciclo, um por passo
        saida["voo_pct"] = 100.0 * voo
    return saida


def _deslize(mov, eventos):
    """Deslize mediano por apoio e velocidade p95 do ponto apoiado (veja `apoios`)."""
    registros = [r for r in apoios(mov, eventos) if r["plano"]]
    saida = {}
    if registros:
        saida["deslize_apoio"] = float(np.median([r["deslize"] for r in registros]))
        saida["deslize_vel_p95"] = float(np.percentile([r["velocidade"] for r in registros], 95))
    return saida


def _oscilacoes(mov, cabeca, quadril, frente, eventos, janelas_passo, piso):
    """Pico a pico da cabeça e do quadril, vertical por passo e lateral por passada (tendência linear removida)."""
    saida = {}
    verticais, quadris = [], []
    for a, b in janelas_passo:
        verticais.append(np.ptp(_sem_linha(cabeca[a:b + 1, 2])))
        quadris.append(np.ptp(_sem_linha(quadril[a:b + 1, 2])))
    if verticais:
        saida["cabeca_osc_vert"] = float(np.mean(verticais))
        saida["quadril_osc_vert"] = float(np.mean(quadris))
    laterais = []
    lateral = _eixo_lateral(frente)
    for lado in "ed":
        t = eventos.toque[lado]
        for a, b in zip(t[:-1], t[1:]):
            x = ((cabeca[a:b + 1, :2] - cabeca[a, :2]) * lateral[a:b + 1]).sum(axis=1)
            laterais.append(np.ptp(_sem_linha(x)))
    if laterais:
        saida["cabeca_osc_lat"] = float(np.mean(laterais))
    return saida


def _sem_linha(sinal):
    return sinal - np.linspace(sinal[0], sinal[-1], len(sinal))


def _extremos_articulares(curvas):
    """Picos por fase do ciclo, calculados sobre a média das curvas."""
    saida = {}
    if "joelho" in curvas and curvas["joelho"].n:
        joelho = curvas["joelho"].media
        saida["joelho_apoio_max"] = float(joelho[:40].max())            # flexão de carga, 0-40 % do ciclo
        saida["joelho_balanco_max"] = float(joelho[55:].max())           # flexão no balanço
    if "quadril" in curvas and curvas["quadril"].n:
        quadril = curvas["quadril"].media
        saida["quadril_min"], saida["quadril_max"] = float(quadril.min()), float(quadril.max())
    if "tornozelo" in curvas and curvas["tornozelo"].n:
        tornozelo = curvas["tornozelo"].media
        saida["tornozelo_min"], saida["tornozelo_max"] = float(tornozelo.min()), float(tornozelo.max())
    for nome, chave in (("pelve_rot", "pelve_rot_pp"), ("torax_rot", "torax_rot_pp"), ("ombro", "ombro_pp")):
        if nome in curvas and curvas[nome].n:
            media = curvas[nome].media
            saida[chave] = float(media.max() - media.min())
    if "cotovelo" in curvas and curvas["cotovelo"].n:
        saida["cotovelo_medio"] = float(curvas["cotovelo"].media.mean())
    if "tronco_incl" in curvas and curvas["tronco_incl"].n:
        saida["tronco_inclinacao"] = float(curvas["tronco_incl"].media.mean())
    return saida


# --------------------------------------------------------------------------
# Fase da cabeça em relação à passada (usado no teste de coesão)
# --------------------------------------------------------------------------
def fase_do_ponto_baixo(altura, eventos, lado="e"):
    """Em que fração do ciclo (0..1, do toque do calcanhar `lado` ao seguinte) a altura é mínima, média dos ciclos
    (média circular, para não errar perto de 0 e 1)."""
    ciclos = _ciclos_de(altura, eventos, lado, 1.0, "media")
    if not len(ciclos):
        return NAN
    fases = np.argmin(ciclos, axis=1) / (CICLO_PONTOS - 1)
    angulo = np.angle(np.exp(2j * np.pi * fases).mean())
    return float((angulo / (2 * np.pi)) % 1.0)


def fases_do_duplo_apoio(eventos, lado="e"):
    """Intervalos (fração do ciclo do pé `lado`) em que os dois pés tocam o chão, médios; lista de (início, fim)."""
    saida = []
    toques = eventos.toque[lado]
    ambos = eventos.contato["e"] & eventos.contato["d"]
    mascaras = []
    for a, b in zip(toques[:-1], toques[1:]):
        mascaras.append(normalizar_ciclo(ambos.astype(float), a, b) > 0.5)
    if not mascaras:
        return saida
    media = np.mean(mascaras, axis=0) > 0.5
    return [(a / (CICLO_PONTOS - 1), (b - 1) / (CICLO_PONTOS - 1)) for a, b in _corridas(media)]


def fases_do_ponto_baixo_por_passo(altura, eventos):
    """Em cada passo (de um toque do calcanhar ao toque do pé oposto), a fração do passo (0..1) em que `altura` é mínima,
    sem a tendência linear do passo. Devolve (fases [n], duplo apoio [n, 2]): o intervalo do passo (fração) em que os dois
    pés tocam o chão (NaN, NaN se não há)."""
    toques = eventos.todos_toques()
    ambos = eventos.contato["e"] & eventos.contato["d"]
    fases, duplos = [], []
    for (a, la), (b, lb) in zip(toques[:-1], toques[1:]):
        if la == lb or b - a < 4:
            continue
        trecho = _sem_linha(np.asarray(altura[a:b + 1], float))
        fases.append(float(np.argmin(trecho) / (len(trecho) - 1)))
        # o duplo apoio do passo é o que começa no toque (o pé anterior ainda no chão); o do fim já é do passo seguinte
        parcial = ambos[a:b + 1]
        fim = int(np.argmin(parcial)) if (not parcial.all() and parcial[0]) else 0
        duplos.append((0.0, (fim - 1) / (len(trecho) - 1)) if fim > 0 else (NAN, NAN))
    return np.array(fases), np.array(duplos).reshape(-1, 2)


def cabeca_baixa_no_duplo_apoio(altura, eventos, folga=0.08):
    """Fração dos passos em que o ponto mais baixo da cabeça cai no duplo apoio (com `folga` de fração do passo para
    cada lado). Sem duplo apoio no movimento, devolve 0 (a condição não se cumpre)."""
    fases, duplos = fases_do_ponto_baixo_por_passo(altura, eventos)
    if not len(fases):
        return NAN
    dentro = [np.isfinite(d0) and d0 - folga <= f <= d1 + folga for f, (d0, d1) in zip(fases, duplos)]
    return float(np.mean(dentro))


def frequencia_dominante(sinal, fps, minimo=0.5, maximo=6.0):
    """Frequência (Hz) do maior pico do espectro de `sinal` entre `minimo` e `maximo` (tendência removida, janela de Hann)."""
    sinal = np.asarray(sinal, float)
    sinal = sinal - np.polyval(np.polyfit(np.arange(len(sinal)), sinal, 1), np.arange(len(sinal)))
    janela = np.hanning(len(sinal))
    n = 8 * len(sinal)
    espectro = np.abs(np.fft.rfft(sinal * janela, n))
    frequencias = np.fft.rfftfreq(n, 1.0 / fps)
    faixa = (frequencias >= minimo) & (frequencias <= maximo)
    return float(frequencias[faixa][np.argmax(espectro[faixa])])


# --------------------------------------------------------------------------
# Mãos: perfil de velocidade e jerk mínimo
# --------------------------------------------------------------------------
def perfil_mao(mov, lado="d", junta="punho", suavizar_s=0.04):
    """Velocidade escalar da mão (m/s) por quadro: a norma da derivada 3D da trajetória suavizada."""
    pos = gaussiano(mov.j(f"{junta}_{lado}"), suavizar_s, mov.fps)
    return np.linalg.norm(derivada(pos, mov.fps), axis=1)


def detectar_alcances(velocidade, fps, vel_minima=0.25, fracao=0.08, duracao_minima=0.20, vale=0.30):
    """Trechos (início, fim exclusivo) de cada movimento da mão: picos acima de `vel_minima` separados por vales que caem
    abaixo de `vale` x o menor dos dois picos; cada trecho se estende até a velocidade cair a `fracao` do seu pico."""
    v = np.asarray(velocidade, float)
    n = len(v)
    picos = [i for i in range(1, n - 1) if v[i] >= vel_minima and v[i] >= v[i - 1] and v[i] > v[i + 1]]
    if not picos:
        return []
    grupos = [[picos[0]]]
    for anterior, atual in zip(picos[:-1], picos[1:]):
        fundo = v[anterior:atual + 1].min()
        if fundo < vale * min(v[anterior], v[atual]):
            grupos.append([atual])
        else:
            grupos[-1].append(atual)
    cortes = [0]
    for g_ant, g_atual in zip(grupos[:-1], grupos[1:]):
        trecho = v[g_ant[-1]:g_atual[0] + 1]
        cortes.append(g_ant[-1] + int(np.argmin(trecho)))
    cortes.append(n)
    alcances = []
    for grupo, limite_esq, limite_dir in zip(grupos, cortes[:-1], cortes[1:]):
        pico = max(grupo, key=lambda i: v[i])
        limite = fracao * v[pico]
        a = pico
        while a > limite_esq and v[a - 1] > limite:
            a -= 1
        b = pico
        while b < limite_dir - 1 and v[b + 1] > limite:
            b += 1
        if (b + 1 - a) / fps >= duracao_minima:
            alcances.append((a, b + 1))
    return alcances


def ajuste_jerk_minimo(velocidade, inicio, fim, fps):
    """Ajusta o perfil de velocidade de um alcance ao de jerk mínimo, v(t) = 30 (D/T) s²(1-s)² com s = (t - t0)/T.

    O trecho [inicio, fim) só diz onde olhar: T e t0 saem de uma busca por mínimos quadrados (a detecção corta as
    pontas lentas, que o modelo tem). Devolve duração T, distância D (integral da velocidade), instante do pico medido
    (fração de T; jerk mínimo = 0,5), razão pico/(D/T) (jerk mínimo = 1,875) e o R² do ajuste."""
    velocidade = np.asarray(velocidade, float)
    if fim - inicio < 4:
        return {}
    janela = (fim - inicio) / fps
    a = max(0, inicio - int(0.5 * janela * fps))
    b = min(len(velocidade), fim + int(0.5 * janela * fps))
    v = velocidade[a:b]
    t = (np.arange(a, b) + 0.5) / fps
    D = float(v.sum() / fps)
    ss_tot = float(((v - v.mean()) ** 2).sum())
    melhor = None
    for T in janela * np.linspace(0.9, 1.7, 33):
        for t0 in inicio / fps + janela * np.linspace(-0.5, 0.3, 33):
            s = (t - t0) / T
            dentro = (s > 0) & (s < 1)
            modelo = np.where(dentro, 30.0 * (D / T) * np.clip(s, 0, 1) ** 2 * (1 - np.clip(s, 0, 1)) ** 2, 0.0)
            erro = float(((v - modelo) ** 2).sum())
            if melhor is None or erro < melhor[0]:
                melhor = (erro, T, t0)
    erro, T, t0 = melhor
    pico = float(t[int(np.argmax(v))])
    r2 = 0.0 if ss_tot < 1e-9 else 1.0 - erro / ss_tot
    return {"duracao": float(T), "distancia": D, "pico_fracao": float((pico - t0) / T),
            "pico_razao": float(v.max() / max(D / T, 1e-9)), "r2_jerk_minimo": float(r2),
            "velocidade_pico": float(v.max()), "inicio": float(t0)}


def jerk_minimo(distancia, duracao, fps):
    """Perfil de velocidade teórico (m/s) de um alcance de `distancia` m em `duracao` s."""
    n = max(2, int(round(duracao * fps)))
    tau = (np.arange(n) + 0.5) / n
    return 30.0 * distancia / duracao * tau ** 2 * (1.0 - tau) ** 2


# --------------------------------------------------------------------------
# Cabeça: velocidade angular
# --------------------------------------------------------------------------
def velocidade_angular_cabeca(mov, suavizar_s=0.02):
    """Velocidade angular do olhar (graus/s) por quadro: dict com 'total', 'guinada' (em torno de Z) e 'inclinacao'
    (o resto: arfagem + rolagem). Vazio se não há orientação."""
    if mov.cabeca_rot is None or mov.quadros < 3:
        return {}
    r = mov.cabeca_rot
    relativa = r[1:] @ np.transpose(r[:-1], (0, 2, 1))             # rotação de t para t+1, em eixos do mundo
    cos = np.clip((np.trace(relativa, axis1=1, axis2=2) - 1.0) / 2.0, -1.0, 1.0)
    angulo = np.arccos(cos)
    eixo = np.stack([relativa[:, 2, 1] - relativa[:, 1, 2], relativa[:, 0, 2] - relativa[:, 2, 0],
                     relativa[:, 1, 0] - relativa[:, 0, 1]], axis=1)
    eixo = _unitario(eixo)
    w = eixo * (np.degrees(angulo) * mov.fps)[:, None]
    w = gaussiano(w, suavizar_s, mov.fps)
    total = np.linalg.norm(w, axis=1)
    guinada = np.abs(w[:, 2])
    return {"total": total, "guinada": guinada, "inclinacao": np.sqrt(np.maximum(total ** 2 - guinada ** 2, 0.0)),
            "w": w}


def resumo_cabeca(mov):
    """Escalares da velocidade angular da cabeça (RMS e p95, graus/s) para a tabela."""
    w = velocidade_angular_cabeca(mov)
    if not w:
        return {}
    return {"cabeca_w_rms": float(np.sqrt(np.mean(w["total"] ** 2))), "cabeca_w_p95": float(np.percentile(w["total"], 95)),
            "cabeca_w_guinada_rms": float(np.sqrt(np.mean(w["guinada"] ** 2))),
            "cabeca_w_inclinacao_rms": float(np.sqrt(np.mean(w["inclinacao"] ** 2)))}


# --------------------------------------------------------------------------
# Tabela real x jogo
# --------------------------------------------------------------------------
# chave: (rótulo, unidade, casas, tipo de tolerância, valor). "rel": fração do valor real; "abs": na unidade.
# TOLERÂNCIA = um desvio-padrão ENTRE PESSOAS REAIS (medido nos 12 clipes de cmu.GRUPOS["andar"], 7 pessoas, 1,2 a 1,6 m/s),
# arredondado para cima, ou um piso de engenharia quando as pessoas variam menos que o erro de medida (oscilações da cabeça e do
# quadril, deslize). Ou seja: o jogo está "dentro" quando uma pessoa real qualquer poderia ter feito aquilo. Desvios medidos
# (velocidade 0,14 m/s; cadência 4,5; passo 0,059 m; apoio 3,3%; duplo apoio 3,3%; joelho 4,3 e 2,7 graus; quadril 8,0 e 2,1;
# tornozelo 6,0 e 6,3; pelve 4,0; tórax 2,7; braço 17; cotovelo 2,9; tronco 2,3; cabeça vertical 0,6 cm e lateral 0,6 cm;
# velocidade angular da cabeça 7,7 graus/s). Quem tuna um gesto pode apertar ou afrouxar passando outra tabela a
# `comparar_metricas` (ou `Cenario.campos`).
CAMPOS_MARCHA = {
    "velocidade": ("velocidade do quadril", "m/s", 2, "rel", 0.12),
    "cadencia": ("cadência", "passos/min", 0, "rel", 0.10),
    "passada": ("comprimento da passada", "m", 2, "rel", 0.10),
    "passo": ("comprimento do passo", "m", 2, "rel", 0.10),
    "largura_passo": ("largura do passo", "m", 3, "abs", 0.04),
    "apoio_pct": ("apoio (% da passada)", "%", 1, "abs", 4.0),
    "duplo_apoio_passo_pct": ("duplo apoio, cada um (% da passada)", "%", 1, "abs", 4.0),
    "duplo_apoio_ciclo_pct": ("duplo apoio, total (% da passada)", "%", 1, "abs", 8.0),
    "voo_pct": ("fase de voo (% da passada)", "%", 1, "abs", 4.0),
    "deslize_apoio": ("deslize do pé no apoio", "m", 3, "abs", 0.03),
    "deslize_vel_p95": ("velocidade do pé em contato (p95)", "m/s", 2, "abs", 0.30),
    "quadril_altura": ("altura do quadril", "m", 3, "rel", 0.05),
    "quadril_osc_vert": ("oscilação vertical do quadril (pico a pico)", "m", 3, "abs", 0.015),
    "cabeca_osc_vert": ("oscilação vertical da cabeça", "m", 3, "abs", 0.015),
    "cabeca_osc_lat": ("oscilação lateral da cabeça", "m", 3, "abs", 0.015),
    "joelho_apoio_max": ("joelho: flexão no apoio", "graus", 1, "abs", 8.0),
    "joelho_balanco_max": ("joelho: flexão no balanço", "graus", 1, "abs", 8.0),
    "quadril_min": ("quadril: extensão máxima", "graus", 1, "abs", 10.0),
    "quadril_max": ("quadril: flexão máxima", "graus", 1, "abs", 6.0),
    "tornozelo_min": ("tornozelo: mínimo (plantiflexão)", "graus", 1, "abs", 9.0),
    "tornozelo_max": ("tornozelo: máximo (dorsiflexão)", "graus", 1, "abs", 9.0),
    "pelve_rot_pp": ("rotação da pelve (pico a pico)", "graus", 1, "abs", 5.0),
    "torax_rot_pp": ("rotação do tórax (pico a pico)", "graus", 1, "abs", 5.0),
    "ombro_pp": ("balanço do braço (pico a pico)", "graus", 1, "abs", 18.0),
    "cotovelo_medio": ("flexão média do cotovelo", "graus", 1, "abs", 8.0),
    "tronco_inclinacao": ("inclinação média do tronco", "graus", 1, "abs", 4.0),
    "cabeca_w_rms": ("velocidade angular da cabeça (RMS)", "graus/s", 1, "rel", 0.35),
    "cabeca_w_p95": ("velocidade angular da cabeça (p95)", "graus/s", 1, "rel", 0.50),
    "cabeca_w_guinada_rms": ("cabeça: guinada (RMS)", "graus/s", 1, "rel", 0.55),
    "cabeca_w_inclinacao_rms": ("cabeça: arfagem+rolagem (RMS)", "graus/s", 1, "rel", 0.30),
}


def medir_tudo(mov, metodo="auto"):
    """`Marcha` com as métricas de marcha e de cabeça juntas em `.v`."""
    marcha = medir_marcha(mov, metodo)
    for chave in ("cabeca_w_rms", "cabeca_w_p95", "cabeca_w_guinada_rms", "cabeca_w_inclinacao_rms"):
        marcha.v.setdefault(chave, NAN)
    marcha.v.update(resumo_cabeca(mov))
    return marcha


@dataclass
class Linha:
    chave: str
    rotulo: str
    unidade: str
    real: float
    jogo: float
    diferenca: float
    tolerancia: float
    ok: object                     # True, False ou None (sem dado)
    casas: int
    desvio_real: float = NAN       # desvio entre as pessoas/clipes reais, quando se tem vários


def comparar_metricas(real, jogo, campos=None, so_com_dado=True, dispersao=None):
    """Tabela métrica por métrica: valor real, valor do jogo, diferença (jogo - real), tolerância e se passa.
    `real` e `jogo` são dicts de escalares (`Marcha.v`). `campos` troca a tabela de tolerâncias; `dispersao`
    (`dispersao_populacao`) acrescenta o desvio entre os clipes reais a cada linha."""
    campos = CAMPOS_MARCHA if campos is None else campos
    linhas = []
    for chave, (rotulo, unidade, casas, tipo, valor) in campos.items():
        r, j = real.get(chave, NAN), jogo.get(chave, NAN)
        if so_com_dado and not (np.isfinite(r) or np.isfinite(j)):
            continue
        tolerancia = abs(r) * valor if tipo == "rel" and np.isfinite(r) else valor
        dif = j - r
        ok = bool(abs(dif) <= tolerancia) if np.isfinite(dif) else None
        desvio = dispersao[chave][1] if dispersao and chave in dispersao and dispersao[chave][2] > 1 else NAN
        linhas.append(Linha(chave, rotulo, unidade, r, j, dif, tolerancia, ok, casas, desvio))
    return linhas


def v_medio(lista_v):
    """Média, campo a campo, dos escalares de vários clipes reais (ignora os NaN). Aceita objetos com `.v` ou dicts."""
    lista_v = [getattr(m, "v", m) for m in lista_v]
    saida = {}
    for chave in set().union(*[set(v) for v in lista_v]) if lista_v else []:
        valores = np.array([v.get(chave, NAN) for v in lista_v], float)
        valores = valores[np.isfinite(valores)]
        saida[chave] = float(valores.mean()) if len(valores) else NAN
    return saida


def dispersao_populacao(lista_v, chaves=None):
    """Média e desvio de cada escalar entre várias pessoas/clipes reais: {chave: (média, desvio, n)}. `chaves`: quais
    (padrão: os de `CAMPOS_MARCHA`)."""
    saida = {}
    for chave in (CAMPOS_MARCHA if chaves is None else chaves):
        valores = np.array([v.get(chave, NAN) for v in lista_v], float)
        valores = valores[np.isfinite(valores)]
        if len(valores):
            saida[chave] = (float(valores.mean()), float(valores.std()), int(len(valores)))
    return saida


def tabela_texto(linhas):
    """A tabela como texto alinhado (terminal e relatórios)."""
    cabecalho = f"{'métrica':44s} {'unid.':10s} {'real':>9s} {'jogo':>9s} {'dif.':>9s} {'tol.':>7s}  ok"
    saida = [cabecalho, "-" * len(cabecalho)]
    for l in linhas:
        def fmt(x):
            return "   --" if not np.isfinite(x) else f"{x:.{l.casas}f}"
        marca = "--" if l.ok is None else ("sim" if l.ok else "NAO")
        saida.append(f"{l.rotulo:44s} {l.unidade:10s} {fmt(l.real):>9s} {fmt(l.jogo):>9s} {fmt(l.diferenca):>9s} "
                     f"{fmt(l.tolerancia):>7s}  {marca}")
    return "\n".join(saida)
