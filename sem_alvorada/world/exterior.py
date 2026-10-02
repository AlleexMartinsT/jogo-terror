"""Exterior: gramado, rua, calçadas, fachada de tábuas, varanda, cerca, quintal, árvores, vizinhas e horizonte.

O jogador quase nunca sai da casa, mas a janela do quarto olha para fora e o final atravessa a rua. Por isso
o exterior existe inteiro, só que escuro: casas e árvores são silhuetas contra o brilho fraco do horizonte
(ver `sky`) e só ganham detalhe sob a lanterna ou os faróis do carro.

Cada parte mora num módulo próprio (`street`, `utilities`, `facade`, `porch`, `fence`, `yard`, `grass`,
`playthings`, `trees`, `neighbors`); aqui ficam o chão, o horizonte e a ordem de montagem.
"""
import math

from .. import layout
from . import (ext_common as ext, facade, fence, grass, neighbors, playthings, porch, street, trees, utilities,
               yard)

GROUND_Z = -0.12
WORLD_EXTENT = (-170.0, 190.0)      # gramado e horizonte cobrem esta faixa em x e y
HORIZON_RADIUS = 155.0
SILHOUETTE = "night_silhouette"

# Peças pequenas de ambientação do exterior: o que a família deixou para trás (ver `docs/ACABAMENTO.md`, "Narrativa").
AMBIENCE = (
    "jornais enrolados em saco plástico na varanda", "vaso com a planta morta na varanda", "capacho gasto", "caixa de correio com cartas e bandeira levantada",
    "jornal em tubo azul esquecido no chão", "lixeira tombada com o lixo espalhado", "triciclo rosa da Emma tombado no gramado", "bola murcha",
    "balanço com a corrente arrebentada", "piscina de plástico seca com folhas", "tabela de basquete torta na entrada", "rastelo encostado na garagem",
    "desenho de giz (amarelinha, EMMA e sol) na entrada de carros", "mangueira enrolada ao lado da torneira", "placa 'criança brincando' torta",
    "condensador do ar-condicionado", "antena de TV de alumínio no telhado", "hidrante com correntinha", "medidor de luz na parede da garagem",
)


def build(ctx):
    ext.start(ctx)
    _ground(ctx)
    street.build(ctx)
    utilities.build(ctx)
    facade.build(ctx)
    porch.build(ctx)
    fence.build(ctx)
    yard.build(ctx)
    grass.build(ctx)
    playthings.build(ctx)
    trees.build(ctx)
    neighbors.build(ctx)
    _horizon(ctx)
    ctx.log("exterior: rua, calçadas, fachada, varanda, cerca, quintal, grama, árvores, vizinhos e horizonte")


def _ground(ctx):
    """Gramado: o chão inteiro, exceto a faixa da rua (a rua e as calçadas têm a própria malha)."""
    low, high = WORLD_EXTENT
    m = ext.builder("Ground_Grass", ext.PROFILED)
    front = layout.LAWN_FRONT
    for rect in ((low, front.y0, high, high), (low, low, high, layout.ROAD.y0 - 2.0)):
        x0, y0, x1, y1 = rect
        m.quad((x0, y0, GROUND_Z), (x1, y0, GROUND_Z), (x1, y1, GROUND_Z), (x0, y1, GROUND_Z), "grass_dead")
    ext.emit(ctx, m)


def _horizon(ctx):
    """Anel de colinas e mata baixa ao redor: recorta o céu com uma linha irregular, sempre abaixo do Sol Negro."""
    rng = ext.rng_for(ctx, "horizon")
    m = ext.builder("Horizon", ext.PROFILED)
    centre_x, centre_y = 6.0, 5.0
    steps = 96
    heights = [rng.uniform(4.0, 9.5) for _ in range(steps)]
    for i in range(steps):
        a0, a1 = 2 * math.pi * i / steps, 2 * math.pi * (i + 1) / steps
        p0 = (centre_x + HORIZON_RADIUS * math.cos(a0), centre_y + HORIZON_RADIUS * math.sin(a0))
        p1 = (centre_x + HORIZON_RADIUS * math.cos(a1), centre_y + HORIZON_RADIUS * math.sin(a1))
        h0, h1 = heights[i], heights[(i + 1) % steps]
        m.quad((p1[0], p1[1], GROUND_Z), (p0[0], p0[1], GROUND_Z), (p0[0], p0[1], h0), (p1[0], p1[1], h1), SILHOUETTE)
    ext.emit(ctx, m)
