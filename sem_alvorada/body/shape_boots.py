"""Botas de couro surradas: sola de borracha com salto, vira, cabedal com bico, cano, ilhoses, cadarço e língua.

Pé direito construído e espelhado. Coordenadas: a origem do osso Foot (tornozelo) em y = 0, a sola no chão em z = 0,
calcanhar em y = -0,067 e bico em y = +0,26. Tamanho 43 (pé de 28 cm).
"""
import math

import numpy as np

from . import meshkit as K
from . import skeleton as S
from . import tex

LEATHER, SOLE, LACE, METAL = "leather", "sole", "lace", "metal"
NEUTRAL = (0.0, 0.0, 0.02, 0.02)
Y_HEEL, Y_TOE = -0.067, 0.2600
OUTLINE_N = 56

# y, meia-largura do lado de fora; o lado de dentro é mais estreito no arco
_WIDTH = ((-0.0670, 0.000), (-0.0640, 0.0150), (-0.0560, 0.0262), (-0.0420, 0.0338), (-0.0100, 0.0372), (0.0400, 0.0385),
          (0.0900, 0.0445), (0.1300, 0.0495), (0.1700, 0.0495), (0.2050, 0.0455), (0.2350, 0.0340), (0.2500, 0.0215),
          (0.2575, 0.0085), (0.2600, 0.000))
_WO = K.interp([w[0] for w in _WIDTH], [w[1] for w in _WIDTH])
HEEL_THICK, FORE_THICK = 0.034, 0.021


def sole_top(y):
    """Altura do topo da sola em y: mais grossa no salto, mais fina na frente."""
    return float(FORE_THICK + (HEEL_THICK - FORE_THICK) * (1.0 - K.smoothstep(y, -0.03, 0.10)))


def outline(inset=0.0, count=OUTLINE_N):
    """Contorno (x, y) do pé direito, anti-horário visto de cima, a partir do centro do calcanhar. Local ao pé (x = 0 no eixo)."""
    ys = np.linspace(Y_HEEL, Y_TOE, 40)
    outer = [(float(_WO(y)), y) for y in ys]
    inner = [(-float(_WO(y)) * (1.0 - 0.07 * math.exp(-((y - 0.04) / 0.06) ** 2)), y) for y in ys[::-1]]
    pts = np.array(outer[1:] + inner[1:-1])
    # reamostra por comprimento de arco para espaçar bem os vértices
    closed = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0, cum[-1], count, endpoint=False)
    xs, ys2 = np.interp(t, cum, closed[:, 0]), np.interp(t, cum, closed[:, 1])
    out = np.stack([xs, ys2], axis=1)
    if inset:
        normals = np.zeros_like(out)
        nxt, prv = np.roll(out, -1, axis=0), np.roll(out, 1, axis=0)
        tangent = nxt - prv
        normals[:, 0], normals[:, 1] = tangent[:, 1], -tangent[:, 0]
        normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
        out = out - normals * inset
    return out


def _foot_weights(y, z=0.0):
    w = K.blend_chain(["Foot.R", "Toe.R"], [0.135], y, 0.025)
    if z > 0.11:
        share = K.ramp(z, 0.11, 0.20) * 0.55
        w = {k: v * (1 - share) for k, v in w.items()}
        w["Shin.R"] = share
    return K.normalize(w)


def _ring_from_outline(pts, z, offsets=None, inset=0.0):
    z_arr = np.full(len(pts), z) if np.isscalar(z) else np.asarray(z)
    xyz = np.stack([S.LEG_X + pts[:, 0], pts[:, 1], z_arr], axis=1)
    weights = [_foot_weights(float(p[1])) for p in pts]
    return K.Ring((S.LEG_X, 0.095, float(np.mean(z_arr))), (1, 0, 0), (0, 1, 0), 1.0, 1.0, points=xyz, weights=lambda th, w=weights: w)


def build_sole():
    """Sola de borracha: base chata no chão, lateral chanfrada, topo ligeiramente menor para a vira."""
    mesh = K.Mesh()
    base = outline(0.0015)
    full = outline(0.0)
    top_in = outline(0.0035)
    tops = np.array([sole_top(y) for y in full[:, 1]])
    rings = [_ring_from_outline(base, 0.0), _ring_from_outline(full, tops * 0.12),
             _ring_from_outline(full, tops * 0.80), _ring_from_outline(top_in, tops)]
    mesh.sweep(rings, OUTLINE_N, SOLE, phase=0.0, region="sole", uv0_rect=NEUTRAL, uv_tile=0.05, closed_start=True,
               closed_end=True)
    return mesh


def build_welt():
    """Vira: filete de couro costurado onde o cabedal encontra a sola."""
    mesh = K.Mesh()
    pts = outline(0.0008)
    rings = []
    for index in range(OUTLINE_N):
        x, y = pts[index]
        tangent = pts[(index + 1) % OUTLINE_N] - pts[index - 1]
        tangent /= max(np.linalg.norm(tangent), 1e-9)
        outward = np.array([tangent[1], -tangent[0], 0.0])
        z = sole_top(float(y)) + 0.0015
        rings.append(K.Ring((S.LEG_X + x, y, z), outward, np.array([0.0, 0.0, 1.0]), 0.0030, 0.0026, n=2.2,
                            weights=_foot_weights(float(y))))
    mesh.sweep(rings, 8, LEATHER, phase=0.0, region="welt", uv0_rect=NEUTRAL, uv_tile=0.05, loop=True)
    return mesh


# (y, meia-largura do cabedal, altura do topo acima da sola)
UPPER_STATIONS = ((-0.0655, 0.0100, 0.060), (-0.0620, 0.0190, 0.150), (-0.0540, 0.0285, 0.190), (-0.0380, 0.0360, 0.205),
                  (-0.0150, 0.0395, 0.205), (0.0100, 0.0405, 0.185), (0.0350, 0.0410, 0.142), (0.0600, 0.0415, 0.112),
                  (0.0850, 0.0450, 0.092), (0.1100, 0.0482, 0.077), (0.1400, 0.0480, 0.065), (0.1750, 0.0460, 0.056),
                  (0.2050, 0.0425, 0.048), (0.2300, 0.0335, 0.039), (0.2480, 0.0220, 0.030), (0.2570, 0.0105, 0.020),
                  (0.2595, 0.0030, 0.010))
_UH = K.interp([s[0] for s in UPPER_STATIONS], [s[2] for s in UPPER_STATIONS])
_UW = K.interp([s[0] for s in UPPER_STATIONS], [s[1] for s in UPPER_STATIONS])


def upper_surface(x, y):
    """Z do cabedal em (x relativo ao eixo do pé, y): a superelipse da seção."""
    top, hw = sole_top(y) + float(_UH(y)), max(float(_UW(y)), 1e-4)
    base = sole_top(y)
    h = (top - base)
    return base + h * max(0.0, 1.0 - abs(x / hw) ** 2.6) ** (1.0 / 2.6)


def _upper_features(y, noise_phase):
    def radial(thetas):
        delta = np.zeros_like(thetas)
        hw = float(_UW(y))
        x = hw * np.cos(thetas)
        top = np.clip(np.sin(thetas), 0.0, 1.0)
        gap = (1.0 - K.smoothstep(np.abs(x), 0.0125, 0.0160)) * K.smoothstep(y, 0.030, 0.045) * (1.0 - K.smoothstep(y, 0.128, 0.140))
        delta -= 0.0030 * gap * top
        quarter = np.exp(-((np.abs(x) - 0.0200) / 0.0045) ** 2) * K.smoothstep(y, 0.030, 0.045) * (1.0 - K.smoothstep(y, 0.128, 0.140))
        delta += 0.0014 * quarter * top
        delta += 0.0016 * np.exp(-((y - 0.185) / 0.0035) ** 2) * top                   # costura do bico
        delta += 0.0024 * K.smoothstep(y, 0.185, 0.215) * (1.0 - K.smoothstep(y, 0.250, 0.258)) * top    # biqueira
        # vincos de flexão atrás da junta dos dedos
        delta -= 0.0030 * np.exp(-((y - 0.115) / 0.022) ** 2) * (0.5 + 0.5 * np.cos(2 * math.pi * (y - 0.1) / 0.014)) * top
        delta += 0.0020 * np.sin(6.0 * thetas + 9.0 * y + noise_phase)
        return 1.0 + delta / max(hw, 0.01)
    return radial


def build_upper():
    mesh = K.Mesh()
    rings = []
    stations = [s[0] for s in UPPER_STATIONS]
    ys = sorted(set(stations + [0.02, 0.05, 0.075, 0.1, 0.125, 0.155, 0.19, 0.22, -0.05, -0.025]))
    ys = [y for y in ys if Y_HEEL < y < Y_TOE - 0.0004]
    for index, y in enumerate(ys):
        base = sole_top(y)
        hw, h = float(_UW(y)), float(_UH(y))

        def per_vertex(thetas, y=y, base=base, h=h):
            return [_foot_weights(y, base + 0.5 * h * (1.0 + math.sin(t))) for t in thetas]
        rings.append(K.Ring((S.LEG_X, y, base + h / 2.0), (1, 0, 0), (0, 0, 1), hw, h / 2.0, n=2.6,
                            radial=_upper_features(y, 0.9 * index), weights=per_vertex))
    mesh.sweep(rings, 24, LEATHER, phase=0.0, region="boot_upper", uv0_rect=tex.LEATHER_ATLAS["R"], uv_tile=tex.LEATHER_TILE,
               closed_start=True, closed_end=True)
    return mesh


def build_laces():
    """Cadarço em X sobre o peito do pé, ilhoses de metal e as pontas soltas."""
    mesh = K.Mesh()
    ys = [0.052, 0.0705, 0.089, 0.1075, 0.126]
    half_gap = 0.0150
    lift = 0.0030
    for left, right in zip(ys, ys[1:]):
        for a, b in ((-half_gap, half_gap), (half_gap, -half_gap)):
            points = []
            for k in range(5):
                t = k / 4
                x = a + (b - a) * t
                y = left + (right - left) * t
                points.append((S.LEG_X + x, y, upper_surface(x, y) + lift + 0.0016 + 0.0012 * math.sin(math.pi * t)))
            rings = []
            for p, q in zip(points, points[1:] + [points[-1]]):
                tangent = np.array(q) - np.array(p) if q != p else np.array(points[-1]) - np.array(points[-2])
                tangent /= np.linalg.norm(tangent)
                ay, _ = K.perpendicular_frame(tangent, np.array([0.0, 0.0, 1.0]))
                rings.append(K.Ring(p, np.cross(ay, tangent), ay, 0.0018, 0.0011, n=2.2, weights={"Foot.R": 1.0}))
            mesh.sweep(rings, 6, LACE, phase=0.0, region="lace", uv0_rect=NEUTRAL, uv_tile=0.02)
    for y in ys:
        for x in (-half_gap, half_gap):
            z = upper_surface(x, y) + lift
            rings = [K.Ring((S.LEG_X + x, y, z + dz), (1, 0, 0), (0, 1, 0), r, r, weights={"Foot.R": 1.0})
                     for dz, r in ((0.0, 0.0034), (0.0010, 0.0036), (0.0018, 0.0026), (0.0020, 0.0016))]
            mesh.sweep(rings, 10, METAL, phase=0.0, region="eyelet", uv0_rect=NEUTRAL, uv_tile=0.02, closed_end=True)
    # laço: duas pontas que sobram para os lados
    y_top = ys[-1]
    for side, direction in ((-1, -1), (1, 1)):
        base = (S.LEG_X + side * 0.012, y_top + 0.004, upper_surface(side * 0.012, y_top) + lift + 0.003)
        points = [base, (base[0] + direction * 0.020, base[1] + 0.010, base[2] + 0.005),
                  (base[0] + direction * 0.035, base[1] + 0.004, base[2] - 0.004), (base[0] + direction * 0.040, base[1] - 0.010, base[2] - 0.016)]
        rings = []
        for p, q in zip(points, points[1:] + [points[-1]]):
            tangent = np.array(q) - np.array(p) if q != p else np.array(points[-1]) - np.array(points[-2])
            tangent /= np.linalg.norm(tangent)
            ay, _ = K.perpendicular_frame(tangent, np.array([0.0, 0.0, 1.0]))
            rings.append(K.Ring(p, np.cross(ay, tangent), ay, 0.0018, 0.0011, weights={"Foot.R": 1.0}))
        mesh.sweep(rings, 6, LACE, phase=0.0, region="lace_end", uv0_rect=NEUTRAL, uv_tile=0.02, closed_end=True)
    return mesh


def build_boot_right():
    mesh = build_sole()
    mesh.merge(build_welt())
    mesh.merge(build_upper())
    mesh.merge(build_laces())
    return mesh


def mirror_boot(mesh):
    mesh.transform(np.diag([-1.0, 1.0, 1.0]), rename=lambda name: name.replace(".R", ".L"))
    return mesh.shift_uv0(0.5, 0.0, materials=(LEATHER,))
