# Movimento: o jogo contra referências reais (fase 4)

O pedido da fase 4: levar a movimentação do protagonista e dos objetos aos detalhes mínimos, usando movimento real como referência, comparando lado a lado, com ângulos diferentes mostrando o mesmo movimento, e entregar fotos e vídeos dessa comparação.

Tudo que está aqui foi gerado por código do repositório e está em `docs/movimento/` (fotos em JPEG, vídeos em MP4). Para refazer: `python -m tools.movimento_ref.comparar --lista` mostra os cenários e `python -m tools.movimento_ref.publicar` reúne os arquivos finais.

## O que é "real" aqui

Não foi possível obter vídeo real de portas, carros, relógios ou lanternas: o ambiente só alcança o PyPI e o `raw.githubusercontent.com`. Então a referência é de dois tipos, e cada número neste documento carrega o seu:

| Rótulo | Significa | Onde vale |
|---|---|---|
| **MEDIDO** | tirado de captura de movimento humano (CMU Graphics Lab, 2.505 clipes em BVH, 120 Hz), medido pelo mesmo código nos dois lados | andar, correr, agachar, parar, curvar, escada, alcançar, empurrar |
| **DERIVADO** | consequência de uma lei física escrita à parte (pêndulo composto, mínima variação de torque, rolar sem deslizar, filtro térmico do filamento), sem importar o código do jogo | porta, pêndulo, chaveiro, rodas do carro, arfagem, poeira, luz |
| **ESTIMADO** | número de engenharia sem fonte medida aqui (esforço de mão, massa de porta, rigidez de pano), sempre com a faixa declarada no código e no teste | forças, massas, tempos de mola |

Onde só existe ESTIMADO, a tabela diz isso na coluna de origem. Nenhum painel de objeto é "porta real contra porta do jogo": é o modelo físico contra o jogo, e a única fonte medida em objetos é a mão humana empurrando (CMU 81_05).

## Como a comparação é feita

- **Mesmo corpo dos dois lados.** O clipe da CMU é retargetado para o mesmo modelo do jogador (o Daniel, 54 ossos). Assim a diferença que se vê é de movimento, não de modelo. O erro angular do retarget é de 1,2° rms (`docs/movimento/referencia/retarget_*.jpg`).
- **Azul é real, laranja é jogo.** Em todos os painéis. A cabeça do corpo do jogo não tem malha, então o palco põe uma esfera de identidade (azul no real, laranja no jogo).
- **Alinhado por fase, não por relógio.** Cadências diferem (110 contra 124 passos por minuto), então os dois são alinhados no toque do calcanhar (marcha) ou em início, pico e chegada (alcance). A legenda diz o fator de velocidade.
- **Esteira.** O corpo fica parado e o piso xadrez anda, com as UVs deslocadas pelo deslocamento real. É assim que se vê o pé deslizar ou não.
- **Seis ângulos, um movimento.** Frente, lado, costas, topo, três quartos e primeira pessoa. A pose é aplicada antes e independente da câmera. O teste de coerência (`tests/test_movimento_ref.py`) confere que a posição de cada osso no referencial do corpo é idêntica entre vistas (6e-8 m) e que a projeção de cada junta cai no pixel esperado (5e-5 px). Nos objetos, o teste equivalente é `tests/test_objetos_3d.py` (ponta da porta a menos de 1 mm entre jogo, modelo e câmeras).
- **Câmera dos olhos em fase com o corpo.** O ponto mais baixo da cabeça cai no duplo apoio em 100% dos passos, tanto no real quanto no jogo (0,14 do passo depois do toque, real 0,18).

## Locomoção

Antes da fase 4 o jogo andava a 2,6 m/s, que é um trote: passo de 1,15 m, 35% do tempo no ar, o pé deslizando. Agora a passada sai de leis medidas em 44 caminhadas, 27 corridas e 2 agachados.

| | Antes | Depois |
|---|---|---|
| Andar | 2,6 m/s | 1,7 m/s |
| Correr | 4,6 m/s | 4,0 m/s (fôlego dura 4,5 s: 18 m em vez de 20,7 m) |
| Agachado | 1,2 m/s | 0,8 m/s |
| Escada | no ritmo do corredor | 1,5 passos por segundo, 0,45 m/s (CMU: 0,42 m/s) |
| Parar | freada constante de 6 m/s² | 0,65 s de qualquer velocidade |
| Entidade (patrulha / espreita / perseguição) | 1,5 / 0,9 / 4,1 m/s | 0,98 / 0,60 / 3,57 m/s, escalada com as razões do jogador (a perseguição segue a 89% da corrida) |

Andar a 1,7 m/s contra a faixa de 1,55 a 1,80 m/s da CMU (10 clipes). Tolerância é um desvio entre as pessoas reais.

| Métrica | Real | Antes | Depois | Tol. |
|---|---|---|---|---|
| velocidade (m/s) | 1,67 | 2,60 | 1,72 | 0,20 |
| cadência (passos/min) | 120 | 136 | 124 | 12 |
| passo (m) | 0,83 | 1,15 | 0,83 | 0,08 |
| apoio (% da passada) | 64,3 | 32,3 | 66,1 | 4 |
| fase de voo (%) | 0 | 35,3 | 0 | 4 |
| deslize do pé (m) | 0,038 | 0,071 | 0,036 | 0,030 |
| oscilação lateral da cabeça (m) | 0,049 | 0,024 | 0,045 | 0,015 |
| joelho no apoio (graus) | 40,9 | 16,2 | 38,1 | 8 |
| rotação da pelve (graus pico a pico) | 14,3 | 0 | 15,0 | 5 |
| velocidade angular da cabeça RMS (graus/s) | 25,6 | 0,9 | 22,7 | 9 |

Métricas dentro da tolerância (de 30): andar 9 para **30**, andar devagar 8 para 23, correr 10 para 24, agachado 8 para 19. Mais: o som do passo sai no toque do calcanhar (erro de até 17 ms), agachar e levantar levam 0,35 s como no real, a respiração é de 0,25 Hz parado e 0,61 Hz sem fôlego.

Arquivos: `docs/movimento/locomocao/` (`andar_folha.jpg`, `andar_curvas.jpg`, `andar_antes_depois.jpg`, `andar_video.mp4` e os equivalentes de correr, agachado, parar, curva, escada).

**O que continua diferente**
- **Agachado.** O jogo baixa o olho a 1,05 m (quase ajoelhado). O mocap só dobra os joelhos: olho a 1,26 m. O ritmo bate e a postura não. É a causa dos 11 pontos que ficam fora no agachado. Subir para cerca de 1,30 m muda onde dá para se esconder e a colisão (`engine/collision.py:312`), então não mexi: é decisão de jogo.
- **Corrida.** 4,0 m/s fica acima de qualquer clipe do conjunto (máximo 3,8). Velocidade, passo e extensão do quadril ficam acima do real por isso. O deslize do pé é de 8,8 cm contra 1,9 cm: a bola do pé anda enquanto a sola rola (o tornozelo desliza 2,6 cm).
- **Curva.** O real perde 21% da velocidade ao virar. O jogo não: com mouse isso viraria atraso de entrada.
- **Joelho no meio do apoio** fica reto (cerca de 6°, real 10°), visível em `andar_curvas.jpg`.
- **Escada.** O jogo dá 1,5 passos por segundo e o real 1,04. A velocidade horizontal bate (0,47 contra 0,42 m/s) porque o degrau do jogo tem 0,30 m de fundo e o passo do clipe avança cerca de 0,40 m. O palco não tem degraus, então não há vídeo nem folha de contato da escada, só tabela e série.
- **Furtivo.** Só 15 de 30 métricas dentro. A única referência (91_18) é uma pessoa olhando em volta, não uma marcha.

## Mãos e itens

Cada gesto de pegar agora dura o que a distância pede, pela lei medida em 199 alcances limpos da CMU: `T = 0,628 + 0,145 · D/L` segundos (desvio 0,22 s), com o pico de velocidade a 48,6% do gesto. O executor interpola em jerk mínimo. Chave e mapa estavam rápidos demais (0,33 e 0,42 s) e a pilha lenta demais (1,10 s). Hoje todos ficam em 0,78 a 0,83 s.

| Métrica | Fonte | Real ou lei | Antes | Depois |
|---|---|---|---|---|
| alcance, lanterna (s) | MEDIDO | 0,78 | 0,58 | 0,83 |
| alcance, pilha (s) | MEDIDO | 0,78 | 1,10 | 0,83 |
| alcance, chave (s) | MEDIDO | 0,78 | 0,33 | 0,83 |
| pico da velocidade (% do gesto) | MEDIDO | 47 | 52 | 48 |
| pico / média (jerk mínimo é 1,875) | MEDIDO | 1,88 | 2,86 | 1,77 |
| cotovelo no meio da tela (quadros) | MEDIDO | 0 | 97 | 0 |
| feixe: atraso atrás da câmera (ms) | MEDIDO | 77 | 103 | 69 |
| lâmpada: subida de 10 a 90% (ms) | ESTIMADO | 20 a 80 | 0 (degrau) | 31 |
| chaveiro: período do balanço (s) | DERIVADO | 0,785 | 0,669 | 0,787 |
| polegar, ângulo com os dedos (graus) | ESTIMADO | 30 a 40 | 56 | 31 |

26 de 27 linhas com tolerância ficam dentro. A que fica fora é o punho acima do ombro com a lanterna parada (+0,03 contra −0,27 do real), de propósito: na altura real a lanterna sai do campo de visão.

Custo de jogo: o gesto completo de pegar passou de 2,05 para 2,49 s, então a espera de uma troca de item no inventário subiu de 2,4 para 3,2 s.

Arquivos: `docs/movimento/maos/` (`antes_depois_<item>.jpg` são renders EEVEE do que o jogador vê, antes e depois; `<cenario>_folha.jpg`, `_perfil.jpg` e `_video.mp4` comparam o jogo com um clipe).

**Leia as folhas de mãos com cuidado.** O clipe real é uma tarefa diferente da do jogo (15_06 estica o braço a 0,85 m, o jogo leva o mapa ao peito; 115_01 pega uma caixa com as duas mãos). O que se compara é o **perfil de velocidade e o tempo**, não a pose. Cada clipe é n = 1; a lei do jogo vem de n = 199, e três dos clipes estão a 1,5 a 2 desvios abaixo da média dela.

**O que continua diferente**
- **Pegar do chão.** O real é uma curvatura do corpo todo em 1,8 s. O jogo usa só o braço em 0,8 s. Falta o tronco inclinar e agachar.
- **Mão na maçaneta** (clipe 81_05) não existe no jogo.
- **Manga da camisa.** Termina a 0,17 m do cotovelo, uns 8 cm antes do pulso (`shape_shirt.CUFF_END`): com a manga arregaçada o antebraço aparece nu. Conferi só a olho.

## Objetos

Fonte única medida: a mão humana empurrando (CMU 81_05, duração 1,27 ± 0,42 s; a abertura de porta do jogo dura 0,96 s e fica dentro de um desvio). Todo o resto é física. 75 métricas, todas dentro da tolerância depois da fase (tabela completa em `docs/movimento/objetos/tabela_fisica_objetos.md`).

| Objeto | Métrica | Física | Antes | Depois | Origem |
|---|---|---|---|---|---|
| porta | força de pico na maçaneta, 13 portas, apressado (N) | até 100 | 112 | 99,5 | ESTIMADO |
| porta | batida: tempo (s) | 0,416 | 0,192 | 0,404 | ESTIMADO |
| porta | batida: velocidade da ponta no impacto (m/s) | 3,9 | 8,3 | 3,9 | ESTIMADO |
| porta | batida: rebote na maçaneta (mm) | 3 a 8 | 26 | 5 | ESTIMADO |
| porta | fechar: lingueta recolhida na chegada | ao menos 0,8 | 0 | 1,0 | DERIVADO |
| carro | rodas: deslizamento do contato / velocidade | até 0,05 | 1,95 | 0,002 | DERIVADO |
| carro | arfagem, gradiente na aceleração | +0,0045 | −0,0126 | +0,0045 | DERIVADO |
| carro | passeio / arfagem (Hz) | 1,19 / 1,51 | 2,6 / 1,9 | 1,19 / 1,51 | ESTIMADO |
| carro | pneu afastado do terreno (mm) | até 10 | 37 | 2,4 | DERIVADO |
| coelhinho | período do pêndulo (s) | 0,829 | 0,897 | 0,830 | DERIVADO |
| portão da garagem | subida de 2,3 m (s) | 11,5 a 16,8 | 2,6 | 12,2 | ESTIMADO |
| cortina | frequência da bainha (Hz) | 0,399 | 0,25 | 0,375 | DERIVADO |
| poeira | velocidade terminal da poeira fina (m/s) | 0,02 a 0,10 | 0,45 | 0,044 | DERIVADO |
| luz | incandescente: tempo a 90% ao ligar (s) | 0,12 | 0,0001 | 0,108 | DERIVADO |
| luz | TV: variação RMS | até 4% | 24% | 0,9% | ESTIMADO |
| relógio | período do pêndulo (s) | 2,00 | 1,47 | 2,00 | DERIVADO |
| relógio | avanço do ponteiro dos segundos por tique (graus) | 6 | 0 | 6,0 | DERIVADO |

Três coisas que a comparação achou de verdade:

1. **O carro tinha três sinais invertidos** (arfagem, coelhinho, giro das rodas). Todos liam a aceleração no eixo Y do mundo, que é negativa quando o carro anda para a frente. As rodas rolavam ao contrário: o ponto de contato andava a 2 vezes a velocidade do carro. Agora tudo é medido no referencial do carro.
2. **A batida de porta pedia cerca de 5 kN na mão** para durar 0,19 s. Com a força que uma mão faz, dura 0,40 s. Dois testes antigos tinham esse desenho de 0,2 s e foram ajustados (`test_doors`, `test_engine_core`).
3. **O portão subia a 1,3 m/s** (2,6 s). Um abridor real sobe a 0,19 m/s (12 s). A cena de saída foi reajustada para o carro esperar a folha subir (folga de 0,29 m sobre o teto do carro).

**Os vídeos de objetos têm duas famílias, e o nome diz qual.**
- `render3d_*.mp4` e `*_folha.jpg`: o objeto 3D real do jogo, renderizado no Blender, com o resultado do modelo físico como fantasma azul translúcido no mesmo espaço (planta, frente ou lado, câmera do jogador). Todas as câmeras mostram o mesmo instante.
- `esquema_*.mp4` e `grafico_*.jpg`: desenhos feitos com matplotlib a partir dos números. Servem para ler as curvas, não como imagem do jogo.

O fantasma do carro é um envelope (duas caixas e quatro rodas com raios em cruz, mais o pêndulo equivalente do coelhinho). Só a pose vem do modelo, não a forma. O corpo do carro anda os mesmos centímetros nos dois porque o percurso é compartilhado de propósito. O que o modelo calcula por conta própria é a arfagem, a altura, o giro das rodas, o coelhinho e o contato com o terreno.

Diferença entre jogo e modelo vista nos renders: porta de 25 kg 2 a 3 graus no fechamento (cerca de 4 cm na ponta), relógio 0,01 grau, arfagem do carro 0,01 grau. A trajetória de abertura da porta é a quíntica do jogo e a de mínima variação de torque do modelo: elas diferem em 0,003% do curso. Isso confirma a curva escolhida, não é validação independente dela.

## Efeito no ritmo do jogo

Andar mais devagar e subir escada no ritmo dos degraus muda o jogo, e não é pouco.

| | Fase 3 | Fase 4 |
|---|---|---|
| Quarto até a porta da garagem, andando | 9,2 s | 20,2 s |
| Idem, correndo | 6,5 s | 18,0 s |
| Robô joga a história inteira (com cutscenes) | 165 s | 199 s |
| Robô, 5 min com a entidade ligada: mortes | 5 | 29 |

A casa ficou cerca de 2,2 vezes mais lenta andando. A velocidade menor responde por 1,5 vezes, e a subida da escada (cerca de 9 s no lugar de 2) pelo resto.

As 29 mortes do robô são um laço, não um desequilíbrio geral: depois da primeira, quase todas ocorrem na escada (a cada 8 a 12 s, alternando entre o meio da subida e o alto). O robô não tem cautela nenhuma, atravessa a escada com a entidade rondando, e agora fica nove segundos nela. Um jogador que espera e se esconde não entra nesse laço, mas o ponto de estrangulamento da escada ficou mais caro. Se a casa ficar pesada de atravessar, a alavanca é `STAIRS_STEPS_PER_SECOND` em `conventions.py` (a 1,8 passos por segundo cada travessia perde cerca de 1,4 s, e a escada se afasta do real).

## Decisões em aberto

- **Profundidade do agachado.** Real 1,26 m, jogo 1,05 m. Mudar altera esconderijos e colisão.
- **Ritmo da escada.** Está no real (0,45 m/s). Mais rápido é mais jogável e menos fiel.
- **Relógio de pé.** Antes estava parado às 6:12 e ainda tinha som de tique-taque. Agora o pêndulo balança, o ponteiro dos segundos dá passos de 6 graus e as horas e os minutos ficam em 6:12: um relógio que anda sem o tempo passar. Se preferir parado, `clockwork.CLOCK_RUNS = False`.
- **Curva sem perda de velocidade** e **pegar do chão sem inclinar o tronco**: ficaram de fora por custo de jogabilidade ou de escopo.

## Testes

Blender 5.0.1: toda a suíte de `tests/` passa (33 arquivos, incluindo `sim_ai` e `sim_playthrough`). Blender 4.2: tudo passa menos dois pontos que já eram assim na fase 3 e não são do jogo: `test_engine_hud::test_render_screenshots` usa `blf.bind_imbuf`, que só existe no 5.x, e `test_engine_ui_api` termina com falha de segmentação ao fechar o Blender, depois de passar os 16 testes.

Testes novos da fase: `test_movimento_ref` (28), `test_locomocao` (21), `test_maos_movimento` (22), `test_objetos_fisica` (130 métricas travadas) e `test_objetos_3d` (5).

## Mapa do código

- `tools/movimento_ref/`: infraestrutura. `bvh.py` e `cmu.py` (leitura e catálogo da CMU), `movimento.py` (formato comum), `metricas.py` (iguais para mocap e jogo), `retarget.py`, `palco.py` (seis vistas), `comparar.py` (linha de comando), `grava.py` (gravador do jogo sem janela), `graficos.py`, `cenarios/` (locomoção, mãos, objetos), `fisica/` (modelos físicos independentes e renders 3D), `publicar.py`.
- `sem_alvorada/gait.py` e `gait_data.py` (gerado): a matemática da passada, pura e sem bpy. Os dados saem de `tools/marcha/extrair.py` e `assets/referencia/marcha_ref.json`.
- Contrato original da fase, com o que foi pedido a cada agente: `docs/FASE4.md`.
