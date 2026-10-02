# Modelagem assistida

Scripts que usam bibliotecas **fora do Blender** (trimesh, manifold3d, shapely, scipy...) para desenhar malhas
difíceis: booleanas robustas, contornos com furos, curvas suaves. Cada script grava um `.npz` em
`assets/models/`, e o builder do jogo carrega com `sem_alvorada.craft.load_npz`. Assim o `.blend` é
reconstruído só com o Python do Blender e numpy.

Formato do `.npz`: `verts` (V,3); `faces` (F,3) ou (F,4) com -1 para completar triângulos; opcionais
`material_ids` (F,) e `uvs` (F,k,2).

Rode a partir da raiz: `python tools/modelagem/tampo_com_cuba.py`. Mantenha cada `.npz` abaixo de 1 MB.

## Carroceria do carro (`carro_carroceria.py`)

Loft de seções transversais (`sem_alvorada/props/car_shape.py`, a mesma fonte que o construtor usa para
encaixar faróis e vidros) mais booleanas com `manifold3d`: arcos de roda em dois degraus, frestas de porta,
capô e porta-malas de 5 mm, bolsões de farol, grade, lanterna e maçaneta, cabine oca com colunas e vãos de
vidro. Grava `assets/models/carro_carroceria.npz` (cerca de 160 KB) com `material_ids`
(0 tinta, 1 plástico preto, 2 painéis internos, 3 carpete, 4 borracha, 5 forro). O amassado da frente é
aplicado depois, no Blender (`props/car_damage.py`). Rode `python tools/modelagem/carro_carroceria.py`
sempre que mudar `car_shape.py`.

## Dedos do corpo (`corpo_dedos.py`)

Não gera malha: ajusta com `scipy` os números dos dedos do corpo do jogador (`sem_alvorada/body`). `pinca` acha a
chave fechada do polegar de modo que polegar e indicador se toquem no preset `pinch`; `lanterna` acha os `curls` e a
inclinação do cano que fecham a mão em volta de um cilindro de 3,7 cm (`grip_cylinder`, `GRIP_ANGLE`). O jogo só lê
os números colados em `body/fingers.py` e `body/handframe.py`.
