# Fase 4: movimento verídico

Documento de trabalho dos agentes da fase 4. Vale junto com `docs/FASE3.md` (contratos de corpo, mãos, portas,
cutscenes), que continua em vigor. Em caso de conflito, este arquivo ganha para o que é de movimento.

## O que o usuário pediu

> O foco agora vai ser nos mínimos detalhes de movimentação, tanto de objeto quanto do protagonista, use
> referências de movimentação real para adaptar, coloque sempre lado a lado para averiguar a proximidade ao
> verídico, diferentes ângulos devem comportar o mesmo movimento coeso, no final traga para mim amostrar em
> fotos e vídeos do movimento e estado com comparação com os cenários reais que você usar de referência.

Traduzindo em regras de trabalho:

1. **Referência real onde ela existe.** Corpo humano: captura de movimento (mocap) de pessoas reais. Objeto
   passivo (porta, pêndulo, portão, carro): a física do fenômeno, com as fórmulas e os números de engenharia
   escritos no código e conferidos por simulação independente. Nada de "referência" inventada.
2. **Lado a lado, sempre.** Toda mudança de movimento é julgada num painel [real | jogo] com a mesma câmera e a
   mesma linha do tempo, alinhadas pela FASE do movimento (a passada, o alcance), não pelo relógio.
3. **Coesão entre ângulos.** O movimento é um só, em 3D. Frente, lado, costas, topo e primeira pessoa mostram o
   mesmo gesto: a câmera dos olhos, o corpo, os sons de passo e as sombras obedecem à mesma fase.
4. **Número antes de olho, olho antes de "pronto".** Cada afirmação de proximidade vem com uma métrica medida do
   clipe real e do jogo, e uma imagem.
5. **Honestidade sobre a fonte.** Todo relatório separa: (a) medido de mocap real, (b) derivado de uma lei física,
   (c) valor de engenharia ou de livro-texto lembrado de memória (marque como ESTIMADO e diga a faixa). Se uma
   referência real não pôde ser obtida, diga isso, não contorne.

## O acervo real: mocap da CMU

Pessoas reais capturadas a 120 Hz (CMU Graphics Lab Motion Capture Database, conversão BVH de cgspeed; a CMU não
restringe o uso). Está em `github.com/Shriinivas/cmubvh`, acessível SÓ por `raw.githubusercontent.com` (o resto da
internet, inclusive wikimedia, youtube e o site da CMU, está bloqueado neste ambiente).

Já prontos, em `tools/movimento_ref/`:

- `bvh.py`: `parse(texto)` e `Mocap` com cinemática direta. `Mocap.world()` devolve `(posições [T, J, 3],
  rotações [T, J, 3, 3])` em metros no mundo do jogo (X direita, Y frente, Z cima), esqueleto virado para +Y no
  primeiro quadro. Unidade do arquivo = 1/0.45 polegada; verificado: a caminhada 07_01 sai a 1,36 m/s.
- `cmu.py`: `buscar("texto")`, `baixar(id)`, `carregar(id, inicio, fim)` (cache em `out/referencia/cmu/`) e o dicionário
  `REFERENCIAS` com os clipes escolhidos. `python -m tools.movimento_ref.cmu` baixa todos (19 MB).
- `assets/referencia/cmu_index.json`: os 2.505 clipes do acervo com descrição (`buscar` procura nele).

Velocidades REAIS medidas nesses clipes (média da velocidade horizontal do quadril; altura do quadril em pé ~0,95 m):

| Referência | Clipe | Velocidade | Observação |
|---|---|---|---|
| andar | 07_01 | 1,36 m/s | caminhada comum |
| andar (outra pessoa) | 08_01 | 1,60 m/s (p90 1,78) | andar rápido |
| andar devagar | 07_04 | 0,93 m/s | |
| andar e parar | 16_33 | 0,71 m/s | desaceleração até parar |
| correr | 09_01 | 3,54 m/s (p90 3,87) | |
| esgueirar | 77_14 | 1,05 m/s | "careful creeping" |
| andar agachado | 136_09 | 0,64 m/s | quadril a 0,82 m |
| furtivo | 17_03 | 0,44 m/s (com pausas) | 53 s, use trechos |
| escada | 83_27 | subida | |
| olhar com lanterna | 77_05 | 4,3 s | uma lanterna na mão |

**O jogo hoje anda a 2,6 m/s (`C.SPEED_WALK`) e corre a 4,6 m/s.** O primeiro é um trote, não uma caminhada
(o passo de 1,15 m fica curto demais e o pé desliza no chão); o segundo é uma corrida de velocista. A fase 4 corrige
a CAUSA (velocidades coerentes com o que o corpo humano faz), não o sintoma: veja o agente 2.

Faixas de livro-texto para caminhada adulta em 1,3 a 1,4 m/s (lembradas de memória, ESTIMADAS, servem de sanidade;
o que vale é a métrica do clipe): cadência 105 a 120 passos/min; comprimento do passo ~0,41 x altura (0,65 a 0,75 m);
apoio ~60% do ciclo e balanço ~40%; duplo apoio ~10% por passo; oscilação vertical da cabeça 4 a 5 cm pico a pico e
lateral 3 a 4 cm; rotação da pelve ±4 graus e do tronco em oposição; flexão de joelho ~18 graus no apoio e ~60 graus no
balanço; quadril -10 a +30 graus; balanço dos braços oposto às pernas, ombro ±15 a 30 graus. Corrida a ~3,5 m/s:
cadência 160 a 170 passos/min, fase de voo, joelho 90 graus ou mais no balanço, inclinação do tronco 5 a 10 graus.

## Ferramentas já instaladas

`numpy`, `matplotlib` e `imageio-ffmpeg` (ffmpeg estático: `imageio_ffmpeg.get_ffmpeg_exe()`, com libx264). `bpy` 5.0.1
(e o 4.2 em `/tmp/claude-0/-home-user-jogo-terror/23c0bab3-1a1d-5fb9-af99-ff615b1d7764/scratchpad/bpy42` para conferência de
compatibilidade). Render rápido sem GPU: motor `BLENDER_WORKBENCH` (uma fração de segundo por quadro); EEVEE por
software leva de 1 a 3 minutos por quadro na casa inteira, então reserve-o para poucos quadros de destaque.

## Divisão de trabalho (4 agentes)

| Agente | É dono de | Pode tocar com cuidado |
|---|---|---|
| **1. Infra de comparação** | `tools/movimento_ref/` (menos `bvh.py` e `cmu.py`, que já existem e ele pode estender), `tests/test_movimento_ref.py` (novo) | `README.md` (seção do movimento) |
| **2. Locomoção e cabeça** | `body/locomotion.py`, `body/poses.py`, `body/rig.py` (só o que for locomoção), `engine/player.py`, `engine/flashlight.py` (só o balanço da luz com a cabeça), `cutscenes/camera.py` (modos de mão: walk, drive, panic, lying, sitting), `conventions.py` (velocidades), `audio/` (só a sincronia dos passos) | `ai/` e `entity/` (só o escalonamento das velocidades da entidade), `engine/game.py` |
| **3. Mãos e itens** | `engine/hands.py`, `engine/handclips.py`, `engine/handtrack.py`, `engine/handheld.py`, `body/fingers.py`, `body/handframe.py`, `props/handheld_*.py` | `engine/flashlight.py` (só o liga/desliga e o piscar), `body/solver.py` (só IK de braço) |
| **4. Objetos e física** | `engine/doors.py`, `cutscenes/anim.py`, `world/doors.py`, `props/car*.py` (só movimento), cortinas, relógio de pêndulo, portão da garagem, luzes | `engine/lights.py`, `cutscenes/scene_*.py` (só velocidades de objetos) |

Quem precisa de algo fora do seu território pede ao dono pelo relatório (o orquestrador integra).

### Agente 1: infraestrutura de referência e comparação

Entrega em dois marcos. **Marco 1 (primeiro, rápido, os agentes 2 a 4 dependem dele):** escreva
"ESTADO: MARCO 1 PRONTO" no topo de `tools/movimento_ref/__init__.py` com o guia de uso, e entregue:

- `grava.py`: grava o JOGO executando uma linha do tempo de entradas (`InputState`) em modo sem janela e devolve
  por quadro: tempo, posição/guinada/inclinação do jogador, pose da câmera, posição mundial de cada osso do `PlayerBody`
  (leia a armadura avaliada), alvos e dedos das mãos, abertura das portas, eventos de ruído (`game.noise_log`). Ele
  precisa funcionar com o `.blend` completo (`out/estado_f3.blend`, ou o que o build gerar) e também num palco vazio
  só com o corpo (rápido). Taxa de gravação: a do jogo (60 Hz), reamostrável.
- `metricas.py`: funções puras sobre posições `[T, J, 3]` (e rotações): detecção de apoio e toque do calcanhar,
  comprimento de passada e de passo, cadência, % de apoio, duplo apoio, deslizamento do pé (velocidade do pé em
  contato com o chão), altura do quadril, oscilação vertical e lateral da cabeça, ângulos de quadril/joelho/tornozelo
  /pelve/tronco/ombro/cotovelo ao longo do ciclo (média e desvio por % do ciclo), perfil de velocidade da mão e ajuste
  de jerk mínimo para alcances, velocidade angular da cabeça. Duas famílias de entrada com o mesmo formato de saída:
  mocap (CMU) e gravação do jogo, para compará-las diretamente.
- `graficos.py`: figuras de matplotlib padronizadas (real em uma cor com faixa de ±1 desvio, jogo em outra; eixo
  em % do ciclo ou segundos normalizados) e tabelas métrica por métrica com a diferença e a tolerância.
- Teste `tests/test_movimento_ref.py` do que for puro (BVH conhecido, métricas em movimento sintético).

**Marco 2:** o painel 3D e o vídeo.
- `retarget.py`: aplica um `Mocap` ao `PlayerBody` do jogo (mesma malha e armadura do jogador: "o Daniel fazendo o
  movimento real"), por casamento de direção de cada segmento (coxa, canela, pé, coluna, ombro, braço, antebraço,
  mão, cabeça) com as proporções do Daniel, mantendo os pés no chão. Documente os limites (dedos, torção).
- `palco.py`: palco de estúdio no Blender (piso xadrez para o olho enxergar deslizamento, luz suave, câmeras
  nomeadas: `frente`, `lado`, `costas`, `topo`, `tres_quartos`, `primeira_pessoa`) onde dois corpos aparecem lado a lado
  (real à esquerda, jogo à direita), no mesmo quadro de cada câmera. A primeira pessoa mostra duas câmeras (a dos olhos
  do mocap e a do jogo) lado a lado.
- `comparar.py` e linha de comando `python -m tools.movimento_ref.comparar <cenario> --vistas frente,lado,topo,primeira
  --saida out/movimento/<cenario>`: gera quadros, folha de contato por fases-chave (toque do calcanhar, apoio médio,
  saída do pé, balanço médio), gráficos, tabela de métricas e um MP4 (H.264, 30 quadros/s, painéis [real | jogo] em
  cada vista, com a legenda do clipe e a métrica no canto). Registro de cenários em `cenarios/` (um módulo por área:
  `locomocao.py` fica com o agente 2, `maos.py` com o agente 3, `objetos.py` com o agente 4; você escreve a classe base
  `Cenario` e um exemplo funcionando, "andar").
- Coesão entre ângulos: um teste que prova que, no mesmo instante, todas as câmeras mostram o mesmo estado (mesmas
  posições mundiais dos ossos) e que a câmera em primeira pessoa e o corpo estão em fase (o ponto mais baixo da
  cabeça acontece no duplo apoio, a câmera sobe e desce com a passada).

### Agente 2: locomoção e cabeça do protagonista

Compare o jogo com 07_01, 08_01, 07_04, 16_33, 09_01, 16_17, 17_03, 77_14, 136_09, 83_27 e 13_35 e adapte até as
métricas ficarem dentro de tolerância (diga a tolerância e justifique). Pontos obrigatórios:

- **Velocidades.** Recalibre `C.SPEED_WALK`, `SPEED_RUN` e `SPEED_CROUCH` para valores coerentes com o corpo
  humano (a referência está na tabela; sugestão de partida: andar 1,7 a 1,9 m/s, correr 3,8 a 4,2 m/s, agachado 0,8
  a 1,0 m/s), e escalone as velocidades da entidade (`ai/`, `entity/`) mantendo as MESMAS razões (a entidade caminha
  mais devagar que o jogador corre, mais rápido que ele agachado, etc.). Rode `tests/test_ai_*.py`,
  `tests/sim_ai.py`, `tests/sim_playthrough.py`: o jogo continua completável e a dificuldade relativa se mantém
  (reporte os tempos de travessia antes e depois). Se a casa ficar lenta demais, diga com números e proponha, não
  decida sozinho contra a física.
- **Passada.** Comprimento do passo proporcional à velocidade e à altura (relação real), cadência, fase de voo na
  corrida, % de apoio e duplo apoio, pé sem deslizar (meça a velocidade do pé em contato), calcanhar-pontas.
  Pelve e tronco em oposição, braços balançando, joelho e tornozelo com as curvas do clipe.
- **Cabeça e câmera.** Bobbing vertical e lateral, inclinação (roll) e a suavização por amplitude real; a câmera dos
  olhos e o corpo em fase; respiração (parado e ofegante); olhar em volta; frear e parar (16_33); curvas (16_17);
  agachar e levantar; escada (83_27, 13_35: o pé entra no degrau sem atravessar, pelve acompanha).
- **Sons de passo no instante do toque do calcanhar** (hoje são disparados por distância percorrida): sincronize com os
  eventos de contato da própria animação.
- **Câmera de cutscene:** os modos de mão `walk`, `panic`, `drive`, `lying`, `sitting` em `cutscenes/camera.py` com
  amplitudes e frequências medidas (cabeça em caminhada e corrida nos clipes), e as transições deitado -> sentado ->
  em pé comparadas com 111_09 (levantar da cadeira) e 13_01.
- Cenários de comparação em `tools/movimento_ref/cenarios/locomocao.py`: andar, andar_devagar, parar, correr, curva,
  agachado, furtivo, escada.

### Agente 3: mãos, itens e lanterna

Referências: 26_09 (abaixar e pegar), 15_06 (alcançar), 77_05 (olhar com lanterna), 22_22 (apanhar chaves), 81_05
(empurrar), 91_18 (cuidado olhando em volta) e a física de pêndulo/mola para o que balança.

- **Alcances.** Perfil de velocidade da mão em sino (jerk mínimo), pico perto de 40 a 50% da duração, duração
  coerente com a distância (lei de Fitts, ~0,5 a 0,9 s para 0,3 a 0,6 m), ombro, cotovelo e punho em fase, olhar
  que antecipa a mão. Compare cada gesto de pegar do jogo com os alcances do mocap, painel [real | jogo].
- **Lanterna na mão.** Postura do braço que segura (ombro/cotovelo/punho de 77_05), estabilidade, atraso do feixe de luz
  em relação à cabeça (hoje `SWAY_FOLLOW`) com a latência angular de um olhar real, levantar e apontar. Liga/desliga:
  tempo de subida da lâmpada incandescente (ESTIMADO ~20 a 80 ms) em vez de degrau; piscar de pilha fraca como
  rajadas de mau contato (milissegundos) e não como pulsos longos.
- **Chaveiro, folha, mapa:** pêndulo do chaveiro com período e amortecimento da física (T = 2 pi raiz(L/g) para um
  pêndulo composto; calcule com o comprimento real do modelo e confira em simulação independente), folha com inércia
  e dobra, mapa desdobrando.
- **Troca de pilhas:** as duas mãos em fase, sem atravessar.
- **Dedos:** transições entre presets com a coordenação real (flexão de falanges em cascata), polegar sem abdução
  excessiva, sem estrangular a manga.
- Cenários em `tools/movimento_ref/cenarios/maos.py`: pegar_chao, alcancar, lanterna_olhar, pegar_chave, pilhas, nota.

### Agente 4: objetos e física

Referência é a física, escrita como modelo independente e comparada ao movimento do jogo no mesmo painel
[modelo físico | jogo] (e, onde houver mocap, mãos reais empurrando: 81_05 e 56_0x "lift open window").

- **Porta:** corpo rígido em dobradiça, empurrado por uma mão (impulso curto, ESTIMADO 0,2 a 0,5 s) com atrito
  de dobradiça e amortecimento; curva de velocidade angular em sino, fechar por inércia/mola de fecho, trinco com
  rebote, batida. Compare as 13 portas, aberta devagar, normal, apressada, e a inversão no meio. A porta e a
  maçaneta (lingueta) em fase. Lei: o movimento sai da simulação (ou é provado equivalente a ela), não de uma curva
  desenhada a olho.
- **Pêndulo do relógio de pé:** período real (um pêndulo de segundos tem L ~ 0,994 m e T = 2 s), amplitude
  pequena, ponteiro dos segundos que dá passos, badalada em fase; confira com o modelo da sala (`props/clock.py`).
- **Cortinas** (vento: oscilação lenta de 0,3 a 1 Hz com rajadas), **poeira** caindo (velocidade terminal de
  partículas de poeira, poucos cm/s), **portão da garagem** (abridor residencial ~15 a 20 cm/s ESTIMADO, partida e
  parada suaves; hoje sobe 2,3 m em ~4 s na cutscene: decida entre velocidade real com corte de câmera ou aceleração
  declarada e justificada), **carro** (0 a 100 km/h em ~10 s para um sedã dos anos 90, caturra/rolagem de
  suspensão com frequência natural de 1 a 1,5 Hz e amortecimento ~0,3 ESTIMADOS, rodas rolando sem deslizar:
  rotação = velocidade/raio, vibração do motor em marcha lenta), **luzes** (incandescente demora dezenas de ms;
  fluorescente com mau reator pisca em rajadas de 3 a 10 Hz), **TV**.
- Cenários em `tools/movimento_ref/cenarios/objetos.py`: porta, pendulo_relogio, chaveiro, portao, carro, cortina.

## Regras de convivência (as da fase 3 continuam)

- Edite só o seu território; arquivos compartilhados só com edições pequenas e aditivas via `Edit`, depois de reler.
  Não faça `git commit/push` e NUNCA `git checkout/restore/stash/reset` (só leia com `git status/diff/log`).
- Testes são scripts com `assert`; rode com `LIBGL_ALWAYS_SOFTWARE=1`. Antes de entregar rode os do seu território,
  `tests/test_engine_core.py`, `tests/test_body.py`, `tests/test_hands.py`, `tests/test_doors.py`,
  `tests/test_cutscenes_*.py`, `tests/test_integration_build.py` e `tests/sim_playthrough.py`.
- CPU compartilhada entre quatro agentes (4 núcleos): Workbench para desenvolvimento, EEVEE só para poucos quadros de
  destaque, resoluções pequenas (640x360), sem builds completos desnecessários (`--stages`, `SA_ROOMS=`).
- Saída temporária em `out/f4_<seu_numero>/`. O que for entregável (gráficos e vídeos finais) o agente 1 e o
  orquestrador reúnem em `docs/movimento/`; cada agente deixa em `out/f4_<n>/final/` os seus melhores painéis.
- Limite de uso da API: deixe o código sempre num estado em que os testes do núcleo passam; o orquestrador retoma você.
- Compatibilidade: Blender 4.2 LTS e 5.0. Estilo do projeto (português, comentários só onde a razão não é óbvia).
- **Relatório final** (o orquestrador repassa ao usuário): por arquivo o que mudou; a tabela real x jogo antes e
  depois (métrica, valor real, valor do jogo antes, valor do jogo depois, tolerância); o que ficou de fora e por quê;
  o que é MEDIDO, DERIVADO e ESTIMADO; e duas ou três decisões explicadas em linguagem simples (problema, solução,
  motivo).
