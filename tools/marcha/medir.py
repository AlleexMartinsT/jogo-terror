"""Métricas de marcha sobre "pontos nomeados": a MESMA função mede o mocap da CMU e o corpo do jogo.

Um `Captura` é um dicionário de trajetórias [T, 3] (mundo do jogo: X direita, Y frente, Z cima, metros) mais a taxa
de quadros e, opcionalmente, rotações [T, 3, 3] da cabeça e da pelve. Pontos usados:

    pelvis hip_L hip_R knee_L knee_R ankle_L ankle_R toe_L toe_R (toe = bola do pé)
    neck head shoulder_L shoulder_R elbow_L elbow_R wrist_L wrist_R

Os ângulos são definidos só com esses pontos (segmentos), então valem para qualquer esqueleto:
    quadril   ângulo da coxa (quadril->joelho) com a vertical, no plano sagital; + = joelho à frente
    joelho    180 graus menos o ângulo entre coxa e canela (0 = estendido)
    pe        inclinação do pé (tornozelo->bola) com o horizonte, + = ponta para cima, menos o valor do pé plano
    tornozelo ângulo canela-pé menos o valor do pé plano (+ = dorsiflexão)
    ombro     ângulo do braço (ombro->cotovelo) com a vertical, + = cotovelo à frente
    cotovelo  180 graus menos o ângulo entre braço e antebraço
    pelve_yaw, tronco_yaw   giro das linhas dos quadris e dos ombros em relação ao rumo (menos a média)
    tronco_incl             inclinação do tronco (pelve->pescoço) para a frente, em graus
O "pé plano" é o instante do apoio médio de cada passada (o pé está plano no chão).
"""
from dataclasses import dataclass, field

import numpy as np

SIDES = ("L", "R")
NAMES = ["pelvis", "neck", "head"] + [f"{p}_{s}" for s in SIDES for p in
                                      ("hip", "knee", "ankle", "toe", "shoulder", "elbow", "wrist")]

CMU_MAP = {"pelvis": "Hips", "neck": "Neck", "head": "Head",
           "hip_L": "LeftUpLeg", "knee_L": "LeftLeg", "ankle_L": "LeftFoot", "toe_L": "LeftToeBase",
           "hip_R": "RightUpLeg", "knee_R": "RightLeg", "ankle_R": "RightFoot", "toe_R": "RightToeBase",
           "shoulder_L": "LeftArm", "elbow_L": "LeftForeArm", "wrist_L": "LeftHand",
           "shoulder_R": "RightArm", "elbow_R": "RightForeArm", "wrist_R": "RightHand"}


@dataclass
class Captura:
    pts: dict
    fps: float
    head_rot: np.ndarray = None          # [T, 3, 3] orientação da cabeça (ou da câmera)
    nome: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def frames(self):
        return len(self.pts["pelvis"])

    def cortar(self, a, b):
        pts = {k: v[a:b] for k, v in self.pts.items()}
        rot = None if self.head_rot is None else self.head_rot[a:b]
        return Captura(pts, self.fps, rot, self.nome, dict(self.extra))


def de_mocap(clip, nome=None, inicio=None, fim=None):
    """`Captura` a partir de um `bvh.Mocap` da CMU."""
    pos, rot = clip.world()
    ix = {n: i for i, n in enumerate(clip.joints)}
    pts = {k: pos[:, ix[v]].copy() for k, v in CMU_MAP.items()}
    cap = Captura(pts, clip.fps, rot[:, ix["Head"]].copy(), nome or clip.name)
    cap.extra["rot_pelvis"] = rot[:, ix["Hips"]].copy()
    a = int(round((inicio or 0.0) * clip.fps)) if inicio is not None else 0
    a = max(a, 4)                                   # o primeiro quadro da conversão BVH é um pulo de inicialização
    b = int(round(fim * clip.fps)) if fim is not None else None
    return cap.cortar(a, b)


def euler_xyz_para_matriz(e):
    """Matrizes [T, 3, 3] de ângulos de Euler XYZ do Blender (R = Rz Ry Rx), e: [T, 3] radianos."""
    cx, cy, cz = np.cos(e[:, 0]), np.cos(e[:, 1]), np.cos(e[:, 2])
    sx, sy, sz = np.sin(e[:, 0]), np.sin(e[:, 1]), np.sin(e[:, 2])
    R = np.zeros((len(e), 3, 3))
    R[:, 0, 0] = cz * cy
    R[:, 0, 1] = cz * sy * sx - sz * cx
    R[:, 0, 2] = cz * sy * cx + sz * sx
    R[:, 1, 0] = sz * cy
    R[:, 1, 1] = sz * sy * sx + cz * cx
    R[:, 1, 2] = sz * sy * cx - cz * sx
    R[:, 2, 0] = -sy
    R[:, 2, 1] = cy * sx
    R[:, 2, 2] = cy * cx
    return R


def de_jogo(dados, nome="jogo", fps=60.0, inicio_s=0.0, fim_s=None):
    """`Captura` a partir de uma gravação do jogo (dict de arrays com os pontos, `cam_p` e `cam_r`)."""
    pts = {k: np.asarray(dados[k], float) for k in NAMES if k in dados}
    pts["head"] = np.asarray(dados["cam_p"], float)
    rot = euler_xyz_para_matriz(np.asarray(dados["cam_r"], float))
    cap = Captura(pts, fps, rot, nome)
    a = int(round(inicio_s * fps))
    b = None if fim_s is None else int(round(fim_s * fps))
    return cap.cortar(a, b)


# --------------------------------------------------------------------------
# Utilitários
# --------------------------------------------------------------------------
def media_movel(x, n):
    """Média móvel centrada de `n` amostras (n ímpar), com as bordas por reflexão."""
    n = max(1, int(n) | 1)
    if n == 1:
        return x.copy()
    pad = n // 2
    pad_x = np.concatenate([x[pad:0:-1], x, x[-2:-pad - 2:-1]], axis=0) if len(x) > pad + 1 else np.pad(x, ((pad, pad),) + ((0, 0),) * (x.ndim - 1), mode="edge")
    kernel = np.ones(n) / n
    if x.ndim == 1:
        return np.convolve(pad_x, kernel, mode="valid")[:len(x)]
    return np.stack([np.convolve(pad_x[:, k], kernel, mode="valid")[:len(x)] for k in range(x.shape[1])], axis=1)


def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def rumo(cap, janela_s=1.0):
    """Direção horizontal do deslocamento da pelve, suavizada: vetores unitários [T, 2] (frente)."""
    xy = cap.pts["pelvis"][:, :2]
    sm = media_movel(xy, int(janela_s * cap.fps))
    v = np.gradient(sm, axis=0) * cap.fps
    # onde a pelve quase não anda, herda o rumo do vizinho
    speed = np.linalg.norm(v, axis=1)
    h = unit(v)
    last = h[np.argmax(speed > 0.2)] if np.any(speed > 0.2) else np.array([0.0, 1.0])
    for i in range(len(h)):
        if speed[i] > 0.2:
            last = h[i]
        else:
            h[i] = last
    return h


def lateral_de(h):
    """Direita do rumo: (h_y, -h_x)."""
    return np.stack([h[:, 1], -h[:, 0]], axis=1)


def vel_media(cap, janela_s=0.0):
    p = cap.pts["pelvis"][:, :2]
    d = np.linalg.norm(p[-1] - p[0])
    return d / ((cap.frames - 1) / cap.fps)


def alongar(cap, name, h, ref=None):
    """Componente do ponto `name` (menos `ref`, que é um ponto [T,3]) ao longo do rumo, lateral e vertical."""
    p = cap.pts[name] if isinstance(name, str) else name
    if ref is not None:
        p = p - ref
    lat = lateral_de(h)
    return np.stack([np.sum(p[:, :2] * h, axis=1), np.sum(p[:, :2] * lat, axis=1), p[:, 2]], axis=1)


def angulo_entre(a, b):
    """Ângulo (graus) entre vetores [T, 3]."""
    c = np.sum(unit(a) * unit(b), axis=1)
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def angulo_sagital(seg, h):
    """Ângulo (graus) de um segmento [T,3] com a vertical para baixo no plano (rumo, vertical): + = ponta à frente."""
    along = np.sum(seg[:, :2] * h, axis=1)
    return np.degrees(np.arctan2(along, -seg[:, 2]))


# --------------------------------------------------------------------------
# Eventos: toque do calcanhar, saída do pé
# --------------------------------------------------------------------------
def _runs(flag):
    """[(inicio, fim_exclusivo)] dos trechos verdadeiros."""
    out, start = [], None
    for i, v in enumerate(flag):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(flag)))
    return out


def chao_ajustado(z, fps, janela_s=0.5):
    """Altura `z` menos a reta que passa pelos mínimos de janelas de `janela_s` (o chão do estúdio inclina um pouco
    em alguns clipes). Em chão plano a reta é horizontal."""
    w = max(3, int(janela_s * fps))
    xs, ys = [], []
    for a in range(0, len(z) - w + 1, w):
        k = a + int(np.argmin(z[a:a + w]))
        xs.append(k)
        ys.append(z[k])
    if len(xs) < 2:
        return z - (min(z) if len(z) else 0.0)
    coef = np.polyfit(xs, ys, 1)
    return z - np.polyval(coef, np.arange(len(z))) if abs(coef[0]) * fps < 0.25 else z - np.min(ys)


def velocidade3d(p, fps):
    """Rapidez (m/s) de uma trajetória [T, 3], derivada central sobre 3 quadros suavizados."""
    sm = media_movel(p, 3)
    return np.linalg.norm(np.gradient(sm, axis=0), axis=1) * fps


def contatos(cap, lim=0.028, vmax=None):
    """Máscara booleana de contato com o chão por pé: {'L': [T], 'R': [T]}.

    Contato = o calcanhar (tornozelo) OU a bola do pé a menos de `lim` metros do chão local (o mínimo das alturas, com
    a reta de inclinação do estúdio removida) E esse ponto se movendo a menos de `vmax` m/s. O critério de altura
    sozinho confundiria o arrastar da ponta no começo e no fim do balanço; o de velocidade sozinho, a parada do pé
    no ar. Trechos de poucos quadros são descartados."""
    if vmax is None:
        vmax = max(0.9, 0.5 * vel_media(cap))           # na corrida o pé ainda desliza ao tocar o chão (ver relatório)
    out = {}
    for s in SIDES:
        flag = np.zeros(cap.frames, bool)
        for name, extra in ((f"ankle_{s}", 0.012), (f"toe_{s}", 0.0)):
            z = chao_ajustado(cap.pts[name][:, 2], cap.fps)
            flag |= (z < lim + extra) & (velocidade3d(cap.pts[name], cap.fps) < vmax)
        short = max(2, int(0.025 * cap.fps))
        for _ in range(2):
            for x, y in _runs(~flag):
                if y - x <= short and x > 0 and y < len(flag):
                    flag[x:y] = True
            for x, y in _runs(flag):
                if y - x <= short:
                    flag[x:y] = False
        out[s] = flag
    return out


def eventos(cap):
    """Toques do calcanhar (HS) e saídas do pé (TO), por pé, como listas de índices de quadro."""
    flag = contatos(cap)
    ev = {}
    for s in SIDES:
        runs = _runs(flag[s])
        # descarta o primeiro e o último trecho se tocam a borda do clipe (incompletos)
        full = [(a, b) for a, b in runs if a > 0 and b < len(flag[s])]
        ev[s] = {"HS": [a for a, _ in full], "TO": [b for _, b in full], "runs": full}
    ev["flag"] = flag
    return ev


# --------------------------------------------------------------------------
# Métricas escalares
# --------------------------------------------------------------------------
def medir(cap, ev=None):
    """Dicionário de métricas escalares de marcha (ver tabela no relatório). Valores NaN quando não aplicável."""
    ev = ev or eventos(cap)
    fps, n = cap.fps, cap.frames
    h = rumo(cap)
    speed = vel_media(cap)
    pel = cap.pts["pelvis"]
    out = {"vel": speed, "duracao": n / fps}
    hs_all = sorted([(i, s) for s in SIDES for i in ev[s]["HS"]])
    # passada e cadência: tempo entre toques do mesmo pé
    strides = []
    for s in SIDES:
        t = np.array(ev[s]["HS"], float) / fps
        strides += list(np.diff(t))
    strides = [x for x in strides if 0.3 < x < 3.0]
    out["T_passada"] = float(np.mean(strides)) if strides else np.nan
    out["cadencia"] = 120.0 / out["T_passada"] if strides else np.nan          # passos/min
    out["comp_passada"] = speed * out["T_passada"] if strides else np.nan
    # comprimento do passo: separação dos tornozelos ao longo do rumo no toque do calcanhar
    steps = []
    for i, s in hs_all:
        o = "R" if s == "L" else "L"
        if 0 <= i < n:
            d = (cap.pts[f"ankle_{s}"][i, :2] - cap.pts[f"ankle_{o}"][i, :2]) @ h[i]
            steps.append(abs(d))
    out["comp_passo"] = float(np.mean(steps)) if steps else np.nan
    # apoio, duplo apoio, voo
    flag = ev["flag"]
    both = flag["L"] & flag["R"]
    none = ~flag["L"] & ~flag["R"]
    sl = slice(0, n)
    for s in SIDES:
        for a, b in ev[s]["runs"]:
            pass
    stance = []
    for s in SIDES:
        for (a, b), nxt in zip(ev[s]["runs"], ev[s]["HS"][1:]):
            nxt_i = nxt
            if nxt_i > a:
                stance.append((b - a) / (nxt_i - a))
    out["apoio_pct"] = 100.0 * float(np.mean(stance)) if stance else np.nan
    # restringe duplo apoio/voo ao trecho coberto por passadas completas
    lo = min([ev[s]["HS"][0] for s in SIDES if ev[s]["HS"]], default=0)
    hi = max([ev[s]["HS"][-1] for s in SIDES if ev[s]["HS"]], default=n)
    if hi > lo:
        out["duplo_apoio_pct"] = 100.0 * float(np.mean(both[lo:hi]))      # do tempo todo (duas janelas por ciclo)
        out["voo_pct"] = 100.0 * float(np.mean(none[lo:hi]))
    else:
        out["duplo_apoio_pct"] = out["voo_pct"] = np.nan
    # deslizamento do pé: velocidade horizontal (no solo) do tornozelo e da bola no apoio médio
    slides = []
    for s in SIDES:
        ank, toe = cap.pts[f"ankle_{s}"], cap.pts[f"toe_{s}"]
        for a, b in ev[s]["runs"]:
            m = b - a
            if m < 6:
                continue
            i0, i1 = a + int(0.25 * m), b - int(0.25 * m)
            if i1 - i0 < 3:
                continue
            for p in (ank, toe):
                seg = p[i0:i1, :2]
                v = np.linalg.norm(np.diff(seg, axis=0), axis=1) * fps
                slides.append(np.linalg.norm(seg[-1] - seg[0]) / ((i1 - i0 - 1) / fps) if len(seg) > 1 else 0.0)
    out["desliza_pe"] = float(np.mean(slides)) if slides else np.nan          # m/s, média (deslocamento líquido)
    # cabeça
    out.update(_cabeca(cap, h, ev))
    out["altura_pelve"] = float(np.mean(pel[:, 2]) - np.percentile(0.5 * (cap.pts["ankle_L"][:, 2] + cap.pts["ankle_R"][:, 2]), 3))
    return out


def _cabeca(cap, h, ev):
    """Oscilações da cabeça relativas ao caminho suavizado, medidas nas passadas completas."""
    fps = cap.fps
    T = None
    hs = ev["L"]["HS"] if len(ev["L"]["HS"]) >= 2 else ev["R"]["HS"]
    if len(hs) < 2:
        return {}
    T = float(np.mean(np.diff(hs))) / fps
    win = int(round(T * fps))
    head = cap.pts["head"]
    sm = media_movel(head, win)
    rel = alongar(cap, head - sm, h)           # (frente, lateral, vertical) em relação à média de uma passada
    a, b = hs[0], hs[-1]
    out = {}
    per_stride_z, per_stride_y = [], []
    for i in range(len(hs) - 1):
        seg = slice(hs[i], hs[i + 1])
        per_stride_z.append(np.ptp(rel[seg, 2]))
        per_stride_y.append(np.ptp(rel[seg, 1]))
    out["cab_vert_pp"] = float(np.mean(per_stride_z))
    out["cab_lat_pp"] = float(np.mean(per_stride_y))
    if cap.head_rot is not None:
        ang = _angulos_cabeca(cap, h, win)
        for k in ("roll", "pitch", "yaw"):
            out[f"cab_{k}_pp"] = float(np.mean([np.ptp(ang[k][hs[i]:hs[i + 1]]) for i in range(len(hs) - 1)]))
    return out


def _angulos_cabeca(cap, h, win):
    """Roll, pitch e yaw (graus) da cabeça em relação à sua orientação média local (janela de uma passada)."""
    R = cap.head_rot
    n = len(R)
    mean = media_movel(R.reshape(n, 9), win).reshape(n, 3, 3)
    u, _s, vt = np.linalg.svd(mean)
    mean = u @ vt
    rel = R @ np.swapaxes(mean, 1, 2)          # rotação do mundo que leva a média à atual
    # vetor de rotação (pequenos ângulos): parte antissimétrica
    w = 0.5 * np.stack([rel[:, 2, 1] - rel[:, 1, 2], rel[:, 0, 2] - rel[:, 2, 0], rel[:, 1, 0] - rel[:, 0, 1]], axis=1)
    lat = lateral_de(h)
    along = w[:, 0] * h[:, 0] + w[:, 1] * h[:, 1]          # em torno da frente: roll (+ = cai para a direita)
    side = w[:, 0] * lat[:, 0] + w[:, 1] * lat[:, 1]       # em torno da direita: pitch (+ = olha para cima)
    return {"roll": -np.degrees(np.arcsin(np.clip(along, -1, 1))),
            "pitch": np.degrees(np.arcsin(np.clip(side, -1, 1))),
            "yaw": np.degrees(np.arcsin(np.clip(w[:, 2], -1, 1)))}


# --------------------------------------------------------------------------
# Curvas por % da passada
# --------------------------------------------------------------------------
def series(cap):
    """Séries temporais [T] usadas nas curvas (graus e metros) e o rumo [T, 2]."""
    h = rumo(cap)
    s = {}
    pel = cap.pts["pelvis"]
    lat = lateral_de(h)
    for side in SIDES:
        hip, knee, ankle, toe = (cap.pts[f"{k}_{side}"] for k in ("hip", "knee", "ankle", "toe"))
        s[f"quadril_{side}"] = angulo_sagital(knee - hip, h)
        s[f"joelho_{side}"] = 180.0 - angulo_entre(hip - knee, ankle - knee)
        foot = toe - ankle
        s[f"pe_{side}"] = np.degrees(np.arctan2(foot[:, 2], np.sum(foot[:, :2] * h, axis=1)))
        s[f"tornozelo_{side}"] = angulo_entre(knee - ankle, toe - ankle)
        sh, el, wr = (cap.pts[f"{k}_{side}"] for k in ("shoulder", "elbow", "wrist"))
        s[f"ombro_{side}"] = angulo_sagital(el - sh, h)
        s[f"cotovelo_{side}"] = 180.0 - angulo_entre(sh - el, wr - el)
    for nome, a, b in (("pelve_yaw", "hip_L", "hip_R"), ("tronco_yaw", "shoulder_L", "shoulder_R")):
        d = cap.pts[b][:, :2] - cap.pts[a][:, :2]
        s[nome] = np.degrees(np.arctan2(np.sum(d * h, axis=1), np.sum(d * lat, axis=1)))     # + = lado direito à frente
    d = cap.pts["neck"] - pel
    s["tronco_incl"] = np.degrees(np.arctan2(np.sum(d[:, :2] * h, axis=1), d[:, 2]))
    obl = cap.pts["hip_R"][:, 2] - cap.pts["hip_L"][:, 2]
    width = np.linalg.norm(cap.pts["hip_R"] - cap.pts["hip_L"], axis=1)
    s["pelve_roll"] = np.degrees(np.arcsin(np.clip(obl / np.maximum(width, 1e-6), -1, 1)))
    return s, h


# curvas que mudam de sinal quando o pé de referência troca (lateral e giros); as outras valem para os dois pés
ESPELHADAS = ("pelve_yaw", "tronco_yaw", "pelve_roll", "cab_y", "pelvis_y", "cab_roll", "cab_yaw", "pe_lateral")
SOMENTE_PE = ("quadril", "joelho", "pe", "tornozelo")


def curvas_por_passada(cap, ev=None, pontos=101):
    """Todas as passadas do clipe, cada uma normalizada para 0..100% (do toque do calcanhar de um pé ao seguinte do
    MESMO pé). Devolve ({nome: array [passadas, pontos]}, T_passada).

    Pé direito entra espelhado: o que o pé esquerdo faz de 0 a 100% o direito faz de 50 a 150%, então todas as passadas
    contam como "a do pé que toca em 0%". Curvas dos braços são as do braço OPOSTO ao pé que toca em 0%. Distâncias
    da cabeça e da pelve são relativas à média de uma passada (tira a trajetória), em metros."""
    ev = ev or eventos(cap)
    s, h = series(cap)
    n = cap.frames
    hs0 = ev["L"]["HS"] if len(ev["L"]["HS"]) >= 2 else ev["R"]["HS"]
    if len(hs0) < 2:
        return {}, float("nan")
    T = float(np.mean(np.diff(hs0)))
    win = int(round(T))
    pel_sm = media_movel(cap.pts["pelvis"], win)
    head_rel = alongar(cap, cap.pts["head"] - media_movel(cap.pts["head"], win), h)
    pel_rel = alongar(cap, cap.pts["pelvis"] - pel_sm, h)
    ang = _angulos_cabeca(cap, h, win) if cap.head_rot is not None else None
    collect = {}
    grid = np.arange(n)

    def add(key, arr, a, b):
        collect.setdefault(key, []).append(np.interp(np.linspace(a, b, pontos), grid, arr))

    for side in SIDES:
        other = "R" if side == "L" else "L"
        sign = 1.0 if side == "L" else -1.0
        foot = alongar(cap, cap.pts[f"ankle_{side}"] - pel_sm, h)
        toe = alongar(cap, cap.pts[f"toe_{side}"] - pel_sm, h)
        for a, b in zip(ev[side]["HS"][:-1], ev[side]["HS"][1:]):
            if b - a < 8 or not (0.35 < (b - a) / cap.fps < 2.5):
                continue
            for base in SOMENTE_PE:
                add(base, s[f"{base}_{side}"], a, b)
            add("ombro", s[f"ombro_{other}"], a, b)
            add("cotovelo", s[f"cotovelo_{other}"], a, b)
            for base in ("pelve_yaw", "tronco_yaw", "pelve_roll"):
                add(base, (s[base] - np.mean(s[base][a:b])) * sign, a, b)
            add("tronco_incl", s["tronco_incl"], a, b)
            add("cab_z", head_rel[:, 2], a, b)
            add("cab_y", head_rel[:, 1] * sign, a, b)
            add("pelvis_z", pel_rel[:, 2], a, b)
            add("pelvis_y", pel_rel[:, 1] * sign, a, b)
            add("pe_frente", foot[:, 0], a, b)
            add("pe_lateral", foot[:, 1] * sign, a, b)
            add("pe_alt", foot[:, 2], a, b)
            add("bola_frente", toe[:, 0], a, b)
            add("bola_alt", toe[:, 2], a, b)
            if ang is not None:
                add("cab_roll", ang["roll"] * sign, a, b)
                add("cab_pitch", ang["pitch"], a, b)
                add("cab_yaw", ang["yaw"] * sign, a, b)
    out = {k: np.array(v) for k, v in collect.items()}
    # pé plano = apoio médio (a partir de 25% a 35% da passada, onde o pé está inteiro no chão)
    for key in ("pe", "tornozelo"):
        if key in out:
            out[key] = out[key] - out[key][:, 25:35].mean(axis=1, keepdims=True)
    # altura do pé em relação à altura média do apoio médio (tira o chão inclinado)
    for key in ("pe_alt", "bola_alt"):
        if key in out:
            out[key] = out[key] - out[key][:, 25:35].mean(axis=1, keepdims=True)
    return out, T


def media_curvas(lista):
    """Junta saídas de `curvas_por_passada` de vários clipes: {nome: (média[pontos], desvio[pontos], n)}."""
    pool = {}
    for curvas in lista:
        for k, v in curvas.items():
            pool.setdefault(k, []).append(v)
    return {k: (np.concatenate(v).mean(axis=0), np.concatenate(v).std(axis=0), len(np.concatenate(v))) for k, v in pool.items()}


def eventos_ciclo(cap, ev=None):
    """Percentual médio da passada (HS do pé que toca em 0%) em que o pé oposto toca (~50%) e cada pé sai do chão."""
    ev = ev or eventos(cap)
    toes, opp = [], []
    for side in SIDES:
        other = "R" if side == "L" else "L"
        hs = ev[side]["HS"]
        for a, b in zip(hs[:-1], hs[1:]):
            to = [t for t in ev[side]["TO"] if a < t < b]
            ho = [t for t in ev[other]["HS"] if a < t < b]
            to_o = [t for t in ev[other]["TO"] if a < t < b]
            if to:
                toes.append((to[0] - a) / (b - a))
            if ho:
                opp.append((ho[0] - a) / (b - a))
    return {"TO_pct": 100 * float(np.mean(toes)) if toes else np.nan,
            "HS_oposto_pct": 100 * float(np.mean(opp)) if opp else np.nan}
