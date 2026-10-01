"""Folhas de papel com espessura: curvatura, cantos levantados, vinco, borda rasgada e furos de espiral.

Um papel de verdade nunca é um retângulo plano. Aqui cada folha é uma grade de pontos (topo) com um
espaçamento igual abaixo (fundo) e tiras de borda, de modo que a luz rasante pega a espessura e as
ondulações. O vinco é uma "tenda" (duas águas); o canto levantado é uma curva suave.
"""
import math
import random



def _edge_wobble(rng, amount):
    """Função t -> deslocamento >= 0 ao longo de uma borda: rasgo irregular, mas contínuo."""
    phases = [rng.uniform(0, math.tau) for _ in range(3)]
    freqs = [rng.uniform(5.0, 9.0), rng.uniform(13.0, 21.0), rng.uniform(31.0, 47.0)]
    weights = [0.55, 0.30, 0.15]

    def wobble(t):
        value = sum(w * math.sin(f * t + p) for w, f, p in zip(weights, freqs, phases))
        return amount * (0.5 + 0.5 * value)

    return wobble


def _corner_lift(x, y, half_w, half_l, corners, curl):
    """Levanta cantos: máximo no canto, cai suavemente até ~45% da diagonal."""
    lift = 0.0
    for sx, sy in corners:
        dx = (half_w - sx * x) / (2 * half_w)
        dy = (half_l - sy * y) / (2 * half_l)
        distance = math.hypot(dx, dy)
        if distance < 0.45:
            lift = max(lift, curl * (1.0 - distance / 0.45) ** 2)
    return lift


def sheet(m, width, length, top_mat, back_mat="paper_back", *, thickness=0.0005, nu=12, nv=16,
          offset=(0.0, 0.0, 0.0), yaw_deg=0.0, curl=0.0, curl_corners=((1, 1),), wave=0.0,
          crease=None, tear=0.0, tear_edges="trbl", scallop=0, uv_rect=(0.0, 0.0, 1.0, 1.0), seed=0,
          bend_x=0.0):
    """Adiciona uma folha ao builder `m`. Origem no centro; `length` corre ao longo de Y.

    - `curl`: altura (m) dos cantos levantados em `curl_corners` ((+1,+1) = canto superior direito).
    - `crease`: (eixo 'x'|'y', posição, ângulo em graus): vinco em tenda; as bordas descem do vinco.
    - `tear`: amplitude (m) do rasgo irregular nas bordas de `tear_edges` (t=cima, r=direita, b=baixo, l=esquerda).
    - `scallop`: número de furos de espiral rasgados na borda esquerda (caderno).
    - `bend_x`: abaulamento (m) no sentido de X (papel apoiado em algo, envelope cheio).
    - A folha termina com o ponto mais baixo em z=0 (+ offset), para repousar numa superfície.
    """
    rng = random.Random(seed)
    half_w, half_l = width / 2, length / 2
    wobble = {edge: _edge_wobble(rng, tear) for edge in "trbl"}
    phase_a, phase_b = rng.uniform(0, math.tau), rng.uniform(0, math.tau)

    grid = []
    for i in range(nu + 1):
        column = []
        for j in range(nv + 1):
            u, v = i / nu, j / nv
            x, y = (u - 0.5) * width, (v - 0.5) * length
            if tear > 0:
                if i == 0 and "l" in tear_edges:
                    x += wobble["l"](v)
                if i == nu and "r" in tear_edges:
                    x -= wobble["r"](v)
                if j == 0 and "b" in tear_edges:
                    y += wobble["b"](u)
                if j == nv and "t" in tear_edges:
                    y -= wobble["t"](u)
            if scallop and i == 0:
                hole = 0.5 + 0.5 * math.cos(math.tau * scallop * v)
                x += 0.0045 * hole ** 3 + rng.uniform(0, 0.0008)
            z = wave * math.sin(2.3 * x / width * math.pi + phase_a) * math.sin(1.7 * y / length * math.pi + phase_b)
            z += bend_x * (1.0 - (2 * u - 1) ** 2)
            z += _corner_lift(x, y, half_w, half_l, curl_corners, curl) if curl else 0.0
            if crease:
                axis, at, angle = crease
                coordinate = x if axis == "x" else y
                z -= math.tan(math.radians(angle)) * abs(coordinate - at)
            column.append([x, y, z])
        grid.append(column)

    lowest = min(point[2] for column in grid for point in column)
    yaw = math.radians(yaw_deg)
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)

    def place(point, drop=0.0):
        x, y, z = point
        return (offset[0] + x * cos_y - y * sin_y, offset[1] + x * sin_y + y * cos_y, offset[2] + z - lowest - drop)

    top = [[place(p) for p in column] for column in grid]
    bottom = [[place(p, thickness) for p in column] for column in grid]
    u0, v0, u1, v1 = uv_rect

    def uv_of(i, j):
        return (u0 + (u1 - u0) * i / nu, v0 + (v1 - v0) * j / nv)

    for i in range(nu):
        for j in range(nv):
            quad = [top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1]]
            m.quad(*quad, top_mat, uv=[uv_of(i, j), uv_of(i + 1, j), uv_of(i + 1, j + 1), uv_of(i, j + 1)])
            under = [bottom[i][j + 1], bottom[i + 1][j + 1], bottom[i + 1][j], bottom[i][j]]
            m.quad(*under, back_mat, uv=[uv_of(i, j + 1), uv_of(i + 1, j + 1), uv_of(i + 1, j), uv_of(i, j)])
    for j in range(nv):
        m.quad(top[0][j], top[0][j + 1], bottom[0][j + 1], bottom[0][j], back_mat)
        m.quad(top[nu][j + 1], top[nu][j], bottom[nu][j], bottom[nu][j + 1], back_mat)
    for i in range(nu):
        m.quad(top[i + 1][0], top[i][0], bottom[i][0], bottom[i + 1][0], back_mat)
        m.quad(top[i][nv], top[i + 1][nv], bottom[i + 1][nv], bottom[i][nv], back_mat)
    return top


def triangle_flap(m, base_width, height, hinge_y, angle_deg, outer_mat, inner_mat, z=0.0, thickness=0.0005):
    """Aba triangular de envelope articulada em y=hinge_y, aberta `angle_deg` para cima."""
    with m.at(0.0, hinge_y, z, rx=angle_deg):
        outer = [(-base_width / 2, 0.0, thickness), (base_width / 2, 0.0, thickness), (0.0, height, thickness)]
        m.poly(outer, outer_mat, uv=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)])
        inner = [(x, y, 0.0) for x, y, _ in reversed(outer)]
        m.poly(inner, inner_mat, uv=[(0.5, 1.0), (1.0, 0.0), (0.0, 0.0)])

