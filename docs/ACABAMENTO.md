# Acabamento: fase de ambientação e remodelagem

Esta fase **substitui a regra de ouro 5 e parte da 4 do `CONTRACT.md`** (orçamento e texturas). O resto do
contrato continua valendo: nomes de objetos, propriedades `sa_*`, `layout.py`, colisão por proxies `COL_*`,
âncoras, itens, testes.

## O problema que estamos resolvendo

A primeira versão montou o mobiliário com caixas e cilindros de poucos lados. Cada cadeira é um empilhado de
réguas; o lençol da cama é uma laje quadriculada; o carro é um bloco com vidros em caixa; a textura
`Closest` de 128 px dá ao pano uma cara de pixel grosso. Funciona como "protótipo cinza", não como casa.
Nesta fase **cada objeto é redesenhado** para parecer um objeto: forma própria, construção crível, bordas
que pegam luz, material com relevo, marcas de uso. A entidade fica de fora (fase posterior).

Estilo continua sendo Cry of Fear: escuro, sujo, dessaturado, claustrofóbico. Detalhe fino **no objeto**,
decadência **na pintura e nas marcas**. Não é um jogo limpo, é uma casa de 20 anos com um luto dentro.

## Ferramentas

**Dentro do Blender (preferidas, rodam na build do usuário sem instalar nada):**

- `sem_alvorada.craft`: `finish_mesh` (chanfro, suavização por ângulo, subdivisão, desgaste), `drape`
  (simulação de tecido: lençol, cortina, toalha, manta, toalha de mesa), `cloth_grid`, `tube_along`
  (cabos, fios, cordas, tubos de curva), `join_meshes`, `wear`, `shade_by_angle`. Receitas prontas:
  `STANDARD`, `CRISP` (metal, plástico), `FURNITURE` (madeira), `SOFT` (estofado), `WORN` (reboco, madeira
  velha), `RAW`. Leia o docstring do módulo.
- `props.kit.MeshBuilder`: `lathe` (peças torneadas), `loft` (seções transversais: carro, vaso, pia),
  `sphere`, `soft_box`, `extrude` (perfil), `surface`, `torus`, `tube`, `panel`. Cada `MeshBuilder` aplica
  `craft.STANDARD` ao virar malha; troque com `builder.finish = craft.SOFT` (ou `None`).
- Qualquer coisa nativa do Blender via API de dados e `bmesh`: modificadores (Bevel, Subdivision, Solidify,
  Array, Mirror, Displace, Boolean, Screw, Curve), nós de geometria criados por código, curvas com bevel,
  simulação de tecido (cloth) com pressão (almofadas, travesseiros), remesh, Boolean com `manifold`.
  **Aplique tudo** (a malha final não leva modificadores) e **não use `bpy.ops` que dependa de interface**.
- `compat.add_relief(mat, socket_de_cor, strength, distance)`: liga a textura a um Bump. **Superfície
  visível sem relevo está incompleta.**

**Auxiliares fora do Blender (permitidas, só para autoria):** instalados neste ambiente via `pip`:
`trimesh`, `scipy`, `shapely`, `manifold3d`, `mapbox_earcut`, `opensimplex`, `networkx` (use `pip install` para
outras, só PyPI é acessível). Regra: **nenhum módulo de `sem_alvorada/` importa essas bibliotecas**, porque o
Blender do usuário não as tem e `construir.py` precisa continuar funcionando só com o Python do Blender e
numpy. Se uma biblioteca ajudar a desenhar uma malha (booleana robusta, triangulação de contorno com furos,
casco convexo, curva suave), escreva um script em `tools/modelagem/<nome>.py` que gera a malha e a grava em
`assets/models/<nome>.npz` (arrays `verts`, `faces`, opcionais `uvs`, `material_ids`) e carregue o `.npz` no
builder com `craft.load_npz` (mesmo contrato dos arrays). O `.npz` entra no repositório (mantenha < 1 MB cada).

**Não baixe modelos, texturas ou pacotes de assets de terceiros.** Licença e origem ficam incertas e a rede é
restrita. Tudo continua autoral e procedural.

## O que "pronto" significa para um objeto

Passa **todos** estes itens. Quem não passa em algum, justifica no relatório.

1. **Silhueta própria.** Se você troca o material por cinza e o objeto ainda se identifica de longe, passou.
   Cadeira com pernas afuniladas ou torneadas, travessas, encosto com curva; sofá com braços enrolados,
   almofadas separadas, base com pés; geladeira com cantos arredondados, vincos, puxador, borracha de vedação.
2. **Proporção real.** Use medidas de verdade (assento 0,45 m, tampo de mesa 0,75 m, bancada 0,91 m, porta
   2,03 m, cama de casal 1,40 x 1,90, geladeira 1,80 x 0,75 x 0,70). Anote a referência no comentário do
   builder quando não for óbvia.
3. **Nenhuma quina viva onde uma mão toca.** Chanfro de 3 a 10 mm (STANDARD/FURNITURE/CRISP), maior em
   estofados. Arestas realmente duras só onde faz sentido (dobra de chapa, tampo de vidro).
4. **Construção visível.** Gavetas com frente, folga e puxador; portas com almofadas ou rebaixo; parafusos,
   dobradiças, costuras, rebites, tampas, pés reguláveis. Peça repetida (balaústres, ripas, azulejos)
   individual, com variação mínima.
5. **Orgânico é orgânico.** Almofada, travesseiro, colchão, cortina, lençol, roupa, toalha, cobertor, tapete
   amassado: `SOFT` ou `drape`. Nada de "laje com padrão".
6. **Marcas de uso coerentes** com a casa e com a história (ver "Narrativa"): desgaste nas arestas, manchas,
   poeira acumulada, algo fora do lugar. Cada cômodo conta algo diferente.
7. **Material com relevo e variação.** Textura de 256 a 512 px (até 512x512 de área: uma faixa de 1024x128 vale) com filtro **Linear** (o `Closest` fica só
   para o que é pixelado de propósito: mostrador digital, chiado de TV), Bump ligado à textura, rugosidade que
   varia (mancha, gordura, uso). Cores sujas e dessaturadas; nada de cor lisa chapada em superfície grande.
8. **Orçamento.** `conventions.BUDGET_TRIS` (peça comum 25 k, destaque 60 k, carro 90 k, props 650 k, mundo
   450 k, cena 1,2 M). Respeite `ctx.quality`: `low` reduz segmentos e subdivisão, não remove peça.
9. **Não quebra o jogo.** Veja "Restrições de jogo".

### Autoavaliação obrigatória

Para cada objeto ou família de objetos: `python tools/inspect_object.py --blend out/<seu>/x.blend --out
out/<seu>/inspecao <Objeto>` e **abra o PNG** (3 ângulos, luz de estúdio). Compare com o "antes"
(`out/inspecao_antes/`, no início da fase). Se parece caixa, refaça. Iterar pelo menos uma vez por objeto
de destaque é esperado. Para a cena montada use `tools/prints.py` (câmera do jogador + HUD, no escuro,
com lanterna) e `tools/preview.py`: o objeto precisa funcionar nas duas situações, de perto sob luz boa **e**
no escuro rasante da lanterna.

## Narrativa nos objetos (ambientação)

Daniel perdeu a filha há três semanas e a esposa foi embora. A casa ficou **parada no dia do luto**: coisas
da Emma intocadas, coisas de Daniel acumuladas em desordem, coisas da Laura levadas pela metade.

- Quarto de Emma: perfeito, arrumado, pequeno demais para o silêncio. Desenhos, bichos, sapatinhos, luz noturna.
- Quarto do casal: um lado da cama sem desfazer, o outro intocado há semanas; remédios, copo velho, roupa sobre a cadeira.
- Cozinha e sala de jantar: louça acumulada, comida velha, mesa posta para três com um prato quebrado.
- Sala: manta no sofá, TV ligada no chiado, correspondência não aberta, relógio de pé parado às 6:12.
- Escritório: Daniel pesquisando a rota, recortes, café frio, papéis do seguro e da polícia.
- Garagem: o carro batido, o painel de ferramentas com um contorno sem ferramenta, a bicicleta rosa.
- Em toda a casa: poeira, umidade no teto, papel descascando, fios soltos, teias nos cantos altos,
  mofo atrás dos móveis, lâmpada queimada. **Nada gore explícito.**

Cada agente cria, no seu território, **pelo menos 12 peças pequenas de ambientação** que hoje não existem
(livros, garrafas, copos, caixas de remédio, cartas, sapatos, plantas secas, fios, relógio, vaso, brinquedos,
pratos, sacolas, jornais...), posicionadas com lógica (apoiadas, encostadas, caídas), sem bloquear
passagem nem a visada para os itens coletáveis.

## Restrições de jogo (não negociáveis)

- Nomes, coleções e propriedades `sa_*` do contrato **não mudam**. `Item_*`, `Anchor_*`, `Door_*`, `Window_*`,
  `Light_*`, `Car*`, `GarageRollup`, `Stairs_Main`, `ViewModel_Flashlight` continuam existindo, na mesma posição
  e orientação (portas: pivô na dobradiça, folha em +X local).
- A pegada de cada móvel **não cresce** para fora da que `layout.reserved_zones` e a verificação de
  alcançabilidade aceitam; pode encolher. Proxies `COL_*` continuam caixas simples (8 vértices, só yaw) e devem
  cobrir o móvel; itens coletáveis ficam 1,2 cm acima da superfície e **fora** de qualquer proxy.
- Itens (`Item_*`) são objetos de interação: legíveis no escuro (materiais claros, chave com brilho).
- Colisão do jogador usa paredes/pisos/escada (`sa_col`) e os proxies. Detalhe fino não colide.
- `python -m sem_alvorada.build` termina sem etapa falhando e os testes continuam verdes
  (`tests/test_props_layout.py`, `test_world_geometry.py`, `test_integration_build.py`, `test_engine_core.py`,
  `sim_playthrough.py`). Atualize testes que verificavam limites antigos (1.500 triângulos, `Closest`, 256 px).
- Reconstruir duas vezes dá o mesmo resultado (use `ctx.rng`, nunca `random` global).

## Divisão do trabalho (donos de arquivo)

| Agente | Território | Arquivos |
|---|---|---|
| 1 | Casca interna: rodapés, sancas, guarnições, **portas** (folhas com almofadas, dobradiças, maçanetas), **janelas** (caixilhos, trincos, **cortinas por `drape`**), **escada** (balaústres torneados, corrimão, degraus com nariz), pisos (tábuas individuais), forros, tomadas e interruptores, luminárias de teto, materiais do mundo com relevo | `world/shell.py openings.py (exceto o portão) stairs.py lighting.py materials.py texgen.py meshkit.py` + novos |
| 2 | **Exterior e carro**: fachada de tábuas, telhado de telhas individuais, chaminé, calhas, varanda, quintal, rua, calçadas, casas vizinhas, árvores, cerca, caixa de correio, poste, **portão da garagem** e **carro** (carroceria por `loft`, rodas com aro e banda, vidros, faróis, para-choques, interior) | `world/exterior.py roof.py sky.py` (+ trecho do portão em openings.py), `props/car.py` |
| 3 | **Quartos, banheiro, escritório de cima e corredor de cima** | `props/bedrooms.py bathroom.py rooms_upper.py` (+ `office.py` parte "study"), `cutscenes/objects.py` (relógio 6:12 e outros objetos de cutscene) |
| 4 | **Sala, escritório de baixo, hall de entrada e sala de jantar**; peças genéricas (cadeiras, quadros, tapetes, caixas) | `props/living.py entrance.py dining.py furniture.py parts.py` (+ `office.py` parte "den"), funções de sala/escritório/hall/jantar em `rooms_lower.py` |
| 5 | **Cozinha e garagem (interior)**: armários, pia, fogão, geladeira, eletrodomésticos, louça; bancada, ferramentas, prateleiras, freezer, aquecedor, cortador de grama, bicicleta, caixas | `props/kitchen.py garage.py` + funções de cozinha/garagem em `rooms_lower.py` |
| Orquestrador | Itens e documentos (chave, mapa, pilhas, notas, lanterna e viewmodel), `craft.py`, ferramentas, integração e QA | `props/items.py flashlight.py anchors.py`, `craft.py`, `tools/`, `docs/` |

Arquivos compartilhados que **ninguém edita sem necessidade**: `props/kit.py`, `props/placement.py`,
`props/textures.py`, `props/materials.py`. Para texturas novas, crie `props/tex_<seu_modulo>.py` e registre em
`textures.TEXTURES[nome] = função(rng) -> Canvas`; para materiais, `materials.SPECS[nome] = Spec(...)` ou
`materials.register_builder(nome, função)` (material completo com nós próprios, relevo etc.). Importe o seu
módulo de textura no topo do arquivo do cômodo. Funções genéricas de `furniture.py` e `parts.py` mantêm as
assinaturas (o agente 4 melhora o miolo; os demais podem criar variantes próprias nos seus arquivos).

## Ondas de entrega

Cada onda termina com o build verde e testes passando, para o projeto nunca ficar quebrado.

1. **Onda 1 (destaque):** o que o jogador vê de perto e sempre: os móveis grandes de cada cômodo, as
   portas e escadas, o carro, as janelas. Folha de inspeção de cada um.
2. **Onda 2:** o restante da mobília e peças de cena, cortinas e tecidos por `drape`.
3. **Onda 3:** ambientação (as 12+ peças pequenas), sujeira, relevo nos materiais restantes, revisão por
   `tools/prints.py` no escuro com lanterna.

## Relatório (curto, em português)

O que mudou por objeto (antes e depois, com o caminho das folhas de inspeção); contagem de triângulos
por grupo; o que ficou de fora e por quê; ferramentas auxiliares usadas; problemas conhecidos; **duas ou três
decisões de modelagem que valem explicar a quem está aprendendo** (problema, solução, motivo).
