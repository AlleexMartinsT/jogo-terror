# Modelagem assistida

Scripts que usam bibliotecas **fora do Blender** (trimesh, manifold3d, shapely, scipy...) para desenhar malhas
difíceis: booleanas robustas, contornos com furos, curvas suaves. Cada script grava um `.npz` em
`assets/models/`, e o builder do jogo carrega com `sem_alvorada.craft.load_npz`. Assim o `.blend` é
reconstruído só com o Python do Blender e numpy.

Formato do `.npz`: `verts` (V,3); `faces` (F,3) ou (F,4) com -1 para completar triângulos; opcionais
`material_ids` (F,) e `uvs` (F,k,2).

Rode a partir da raiz: `python tools/modelagem/tampo_com_cuba.py`. Mantenha cada `.npz` abaixo de 1 MB.
