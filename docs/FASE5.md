# Fase 5: as mãos do Daniel, como o jogador as vê

Contrato de trabalho dos três agentes e registro da pesquisa. Vale junto com `docs/FASE4.md` (método de comparação, rótulos MEDIDO, DERIVADO e ESTIMADO, regras de convivência) e `docs/MOVIMENTO.md` (o que a fase 4 entregou).

## O pedido do usuário

> Agora o foco é nos detalhes do personagem, por exemplo, o movimento das mãos enquanto anda, tudo baseado no que o jogador vê em primeira pessoa, a maneira como segura com a lanterna, interage, e etc, quero movimentos naturais e reais, use da web para pesquisar como funciona o corpo humano em tal movimento e etc

Traduzindo: o critério de sucesso é o **quadro que o jogador vê**. Mão que está certa no mundo e fora do quadro não conta; mão que aparece no quadro e se mexe como nenhuma mão real se mexe também não.

## O que o jogador vê hoje (linha de base, medida e fotografada)

Câmera de 72 x 44 graus (`conventions.FOV_DEG`, lado maior da imagem). Fotos do estado de hoje: `out/f5/base_*/folha_*.png` (andar, correr, parado, com a lanterna na mão direita).

- A mão direita aparece só no canto inferior direito: a cabeça da lanterna e os nós dos dedos. O antebraço nunca entra no quadro. Correndo, a mão sai do quadro em metade dos instantes.
- O balanço da mão é uma mola de segunda ordem que segue o *head bob* (`handheld.Sway`: lateral e vertical) e o giro da câmera. Não há movimento no eixo frente-trás, nada acompanha o toque do calcanhar, não há resposta à aceleração (arrancar e parar), correr e andar balançam igual com ganho igual, e o corpo não atrasa em relação ao olhar.
- A mão esquerda vazia nunca aparece andando (e é assim na vida: ver abaixo). Itens na mão esquerda seguem a mesma mola.
- Só existem a respiração (`Sway.step`) e o vaivém da mola. Não há deriva postural lenta do feixe, nem tremor que cresça com o cansaço.
- A mão não se aproxima de nada para interagir: portas abrem sem mão (`Mão na maçaneta` ficou de fora na fase 4), pegar do chão usa só o braço (o real é uma curvatura do corpo todo em 1,8 s), os dedos fecham por curvas fixas, sem contato com a malha do objeto.

## Pesquisa na web: o que o corpo humano faz

Resultados de busca, não revisão sistemática. Onde a fonte é fraca, o texto diz. O que sair daqui como número é ESTIMADO até um agente medir.

**Balanço dos braços.** É em grande parte passivo: um modelo de caminhada sem torque nos braços reproduz o balanço humano, e segurar os braços parados custa cerca de 12% mais energia. A amplitude e a fase dependem de músculo também, e caem sem ele. Os braços funcionam como massas amortecedoras que reduzem o giro do tronco e da cabeça. Carregar peso nos braços altera a amplitude do balanço.
- Collins, Adamczyk e Kuo (2009): <https://pmc.ncbi.nlm.nih.gov/articles/PMC2817299>
- Efeito de cargas nos braços, J Exp Biol 2020: <https://cob.silverchair.com/jeb/article-pdf/223/23/jeb216119/1981344/jeb216119.pdf>
- Pontzer et al. (2009), controle e função do balanço dos braços ao andar e correr, tronco e ombros como elos elásticos: <https://cob.silverchair.com/jeb/article-pdf/1267759/523.pdf>

**Objeto carregado e passo.** O braço usa controle antecipado para amortecer o movimento e dissipar a reação do toque do calcanhar, estabilizando o que carrega. Consequência para o jogo: a lanterna e o feixe ficam mais parados no mundo do que a cabeça, e o que se vê é a *cabeça* subindo e descendo em relação a eles. A orientação da cabeça fica estável perto da horizontal apesar de 1 a 25 cm de translação vertical entre tarefas (fonte menos precisa).

**Pegada de lanterna.** Não achei estudo que meça o ângulo do cotovelo. Patentes (Streamlight) descrevem a pegada natural: palma e dedos envolvem a parte de trás, polegar e indicador estendidos para a frente pelo corpo da lanterna. Fabricantes dizem que a lanterna comum obriga o punho a dobrar para manter o feixe adiante. Técnicas táticas de busca mantêm o braço junto ao corpo ("neck index") e o braço estendido tende a dobrar o cotovelo. Ergonomia de câmera de mão: com o cotovelo apoiado no tronco e o antebraço sem pronação ou supinação extrema, a carga muscular é menor.
- <https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12196398>
- <https://www.americanrifleman.org/content/basic-flashlight-techniques/>
- <https://www.ergonomics.jp/official/wp-content/uploads/gddb/54-evaluation_result.pdf>

**Pegada de força (cilindro).** Dedos parcialmente fechados com a palma; a flexão máxima é nas articulações MCP e a menor nas DIP; os contatos são discretos (quatro a cinco, nas pontas dos dedos e nas cabeças dos metacarpos), não um envolvimento contínuo. O modelo de Buchholz e Armstrong prevê a postura "enrolando" os dedos no objeto e foi validado em cilindros de vários diâmetros.
- <https://deepblue.lib.umich.edu/items/86e3c0b4-2785-43b5-b962-bb890894c683>
- <https://pure.psu.edu/en/publications/is-power-grasping-contact-continuous-or-discrete/>

**Alcançar e pegar.** O pico de velocidade do punho vem cedo, em cerca de 33 a 40% do movimento, e a abertura máxima da mão vem depois, em 60 a 75%: a mão se abre durante o transporte e se fecha no contato (a duração do alcance e a lei dela já foram medidas na fase 4). Os olhos chegam ao alvo antes da mão, de 40 a 100 ms (revisão antiga) até 100 a 300 ms (estudo recente).
- <https://pmc.ncbi.nlm.nih.gov/articles/PMC5594073/table/T2>
- <https://www.psych.mcgill.ca/labs/mcl/pdf/EBR_amattar2002.pdf>

**Tremor.** O tremor fisiológico da mão tem pico entre 6 e 12 Hz (cerca de 8 Hz na postura). Num estudo pequeno, 0,12 a 0,24 mm em repouso e 33 a 216% mais com o braço estendido; cargas leves (100 a 200 g) reduzem. A 30 cm do olho isso é invisível na mão; no feixe de luz, que amplifica o ângulo, é discreto.
- <https://fz.kiev.ua/index.php?abs=1671>

**Portas.** Maçanetas ficam entre 86 e 122 cm do piso. Alavancas dispensam pegada completa; puxadores redondos pedem pegada de 30 a 40 mm de diâmetro. Empurrar e puxar até 22 N (5 lbf) em portas internas é o limite de acessibilidade, e cerca de 67 N (15 lbf) o máximo de norma. Um projetista afirma que a alavanca levemente abaixo da horizontal deixa o punho em posição natural ao empurrar (opinião, não medida).
- <https://sydneyaccessconsultants.com.au/articles/101-issue-7-door-opening-requirements.html>
- <https://brass-works.co.uk/blog/post/science-behind-ergonomic-door-handle-design>

**Leitura.** Distância de leitura com o material na mão: 35 a 40 cm (celular, 36 a 37 cm em pé e sentado), cotovelos dobrados junto ao corpo. Não achei dado específico de mapa de papel.
- <https://pmc.ncbi.nlm.nih.gov/articles/PMC8093538>

**Respiração em repouso.** 12 a 20 por minuto (0,2 a 0,33 Hz). O jogo usa 0,25 Hz parado e 0,61 Hz sem fôlego, dentro do esperado.

## Medido na CMU: o braço no referencial da câmera

Ferramenta nova: `tools/movimento_ref/egocentrico.py` (`python -m tools.movimento_ref.egocentrico` regera `assets/referencia/maos_ego_ref.json`). Mede ombro, cotovelo e punho em (direita, frente, cima), em metros, com a escala do Daniel (braço de 0,60 m), no mesmo referencial da câmera, para o mocap e para o jogo.

Andando livre (12 clipes, 7 pessoas) e correndo (3 clipes), mediana entre clipes, braço direito. Amplitude é de pico a pico (percentis 5 a 95):

| Junta | Andar: média (dir, frente, cima) | Andar: amplitude | Correr: média | Correr: amplitude |
|---|---|---|---|---|
| Ombro | +0,24, −0,11, −0,25 | 0,01, 0,03, 0,02 | +0,20, −0,14, −0,20 | 0,02, 0,05, 0,02 |
| Cotovelo | +0,23, −0,13, −0,60 | 0,08, 0,21, 0,03 | +0,25, −0,29, −0,51 | 0,11, 0,32, 0,11 |
| Punho | +0,26, −0,05, −0,80 | 0,09, 0,39, 0,11 | +0,24, −0,11, −0,61 | 0,07, 0,39, 0,17 |

O que isso diz:
- **O ombro quase não se mexe em relação à cabeça**: 1 a 2 cm de lado, 3 a 5 cm para a frente e para trás, 2 cm de altura. É a base em que o braço se apoia. Uma mão com o cotovelo dobrado, segurando algo, tem como suporte esse ponto parado, não o balanço do braço livre.
- **O braço livre balança 40 a 50 cm para a frente e para trás** (a 0,94 Hz, um ciclo por passada) e pouco na vertical (10 cm), e a mão fica uns 80 cm *abaixo* do olho e 26 cm ao lado.
- **Nenhuma mão cai dentro do campo de visão** (72 x 44 graus) em marcha livre, andando ou correndo: a mão está quase na vertical abaixo do olho (80 cm abaixo, a menos de 10 cm da frente) e o campo cobre só 22 graus para baixo. O jogador só vê as mãos andando se olhar para baixo, ou quando o jogo as põe de propósito no quadro.
- Carregando uma mala numa mão (clipes 70_xx, mala leve), uma mão balança 26 cm no eixo frente-trás e a outra 48 cm; com a mala pesada a amplitude lateral das duas sobe para 27 a 34 cm (o JSON tem as três cargas). Os clipes `77_xx` (busca cuidadosa, lanterna, em guarda) são indicativos: são poses de guarda com a cabeça girando em relação ao tronco, não marcha limpa.

Regra de trabalho que sai disso: a mão da lanterna **tem de aparecer** no quadro (concessão de jogo, igual a qualquer jogo em primeira pessoa), mas deve **se mexer** como uma mão apoiada num ombro quase parado: poucos centímetros de movimento relativo à câmera, com fase e frequência certas, atraso certo no giro, resposta ao toque do calcanhar e à partida e à parada. Qualquer amplitude que fuja disso precisa de justificativa escrita.

## Divisão do trabalho

Três agentes, três territórios. Cada um entrega código, testes, painéis comparativos e um relatório final no formato da fase 4 (por arquivo, tabela real ou lei contra jogo antes e depois, MEDIDO, DERIVADO e ESTIMADO, decisões em problema, solução e motivo). **Cada um faz a própria pesquisa na web para o seu assunto**, cita as URLs no relatório e acrescenta uma seção com elas em `docs/MAOS.md` (arquivo novo, uma seção por agente, sem mexer nas dos outros).

### Agente 1: mãos que andam (balanço, apoio, inércia)

Território: `sem_alvorada/handsway.py` (novo, matemática pura sem bpy, na linha de `gait.py`), `sem_alvorada/engine/handsway.py` (novo, o que liga isso ao `Hands`), as linhas de `Hands._pose_hand` que usam `self.sway` e `handheld.Sway` (substituir por um modelo novo; a classe antiga pode ficar com um alias), `tools/movimento_ref/egocentrico.py` (extensões, painel do campo de visão), `tests/test_maos_andando.py`, `tools/movimento_ref/cenarios/maos_andando.py`.

Tarefas:
1. **Medir o jogo hoje** no mesmo referencial: gravar (`grava`) andar, correr, agachar, parar e arrancar com a lanterna na direita e a esquerda livre, e com chave, mapa ou pilha na esquerda; aplicar `egocentrico.junta_ego` e comparar com `assets/referencia/maos_ego_ref.json`. Ombro e cotovelo do jogo contra o real; a mão que carrega a lanterna contra a estimativa física abaixo.
2. **Modelo novo da mão que carrega**: a mão apoiada no ombro (quase parado, 1 a 5 cm) com o antebraço como mola-amortecedor (frequência natural em torno de 3 a 5 Hz, razão de amortecimento 0,4 a 0,7, ESTIMADO), alimentado por aceleração do tronco e da cabeça e não só pelo bob: eixo frente-trás, resposta ao toque do calcanhar (a cabeça desce, o antebraço absorve), diferença entre andar, correr e agachar (correndo o cotovelo fecha e a mão sobe, medir nos clipes 09_xx), partida e parada (a mão continua um pouco, depois assenta), escada (degrau a degrau).
3. **Corpo atrás do olhar**: quando o jogador gira o mouse, o tronco (e o braço preso a ele) atrasa de 0,07 a 0,17 s em relação à cabeça (MEDIDO na fase 4). A mão deve girar com esse atraso no referencial da câmera, em vez de só uma mola de giro.
4. **Deriva postural e respiração** na mão e no feixe: respiração em 0,2 a 0,33 Hz parado (já existe, conferir a amplitude em graus), deriva lenta do feixe em 0,2 a 1 Hz (ESTIMADO, ordem de 0,1 a 0,3 grau), crescendo com o cansaço (`player.breathing_hard`); o tremor de 8 Hz só entra se for visível no feixe.
5. **Mão esquerda com item andando**: chave pendurada nos dedos (o pêndulo já existe, conferir fase com o passo), mapa dobrado junto ao peito, pilha na palma, nota; e **mão esquerda vazia ao olhar para baixo** (inclinação de câmera de 30 a 60 graus mostra os dois braços: o balanço deles tem de bater com a tabela da CMU, e não deve haver salto quando a mão entra ou sai do quadro).
6. Painéis: o jogo contra o real **no referencial da câmera** (trajetória da mão no plano direita-cima com a moldura do campo de visão, série no tempo, espectro), e vídeos de primeira pessoa (estúdio e casa escura) andando, correndo, agachado, parando, subindo escada. Entregar em `out/f5_1/final/`.

### Agente 2: lanterna e pegadas

Território: `sem_alvorada/body/grasp.py` (novo: fechamento dos dedos por contato), `body/fingers.py`, `engine/flashlight.py`, `engine/handclips.py`, `props/handheld_*.py` (só para pontos de apoio e superfícies de contato), `Hands._place_item` e `Hands._apply_extras`, `tests/test_pegadas.py`, `tools/movimento_ref/cenarios/pegadas.py`.

Tarefas:
1. **Fechar os dedos por contato**: cada dedo e o polegar fecham articulação por articulação (MCP, depois PIP, depois DIP, com a proporção de flexão de uma pegada real) até tocar a malha do item (BVH do item), parando no contato. Conta a distância medida: dedos que atravessam a malha e vão ficar no ar são defeito. Pegadas: lanterna (pegada de força no cilindro, polegar sobre o interruptor, indicador ao longo do corpo se for o caso), chave (argola entre polegar e indicador, o resto relaxado), pilha (na palma, polegar e dois dedos), anotação e mapa (polegar na frente, dedos atrás, um por canto). Teste: a penetração máxima e a folga média por dedo.
2. **Postura de segurar a lanterna**: posição e orientação em câmera, cotovelo de 100 a 120 graus, punho neutro (a CMU 77_05 mede cotovelo de 119 graus e braço a 42 graus da vertical), antebraço entrando pelo canto inferior direito se o campo de visão deixar. Fotos antes e depois no estúdio e na casa escura.
3. **Apontar a luz**: o feixe segue o olhar com atraso (a latência cabeça para braço medida foi de 77 ms, tau) e o antebraço acompanha o ângulo de elevação do olhar só em parte (a mão não vai ao alto quando se olha para cima: pequena rotação do punho e subida de poucos centímetros). Limite de ângulo para não quebrar o punho.
4. **Gestos da lanterna**: ligar e desligar (polegar pressiona o interruptor: curso e tempo), a **batida na palma** quando a pilha pisca (comportamento real e comum; ESTIMADO, discreto, nunca mais de uma vez por rajada de piscadas), rotação do cano para ler uma superfície de perto.
5. **Pré-forma da mão no alcance**: a abertura dos dedos cresce durante o transporte, com o máximo em 60 a 75% do gesto, e fecha no contato (hoje os dedos fecham por curva fixa). Integrar com a duração por lei do `handclips`.
6. Painéis: antes e depois por item (estúdio, EEVEE, 3 ou 4 ângulos de câmera de estúdio e a câmera do jogador), tabela de penetração e folga por dedo, perfil de abertura. Entregar em `out/f5_2/final/`.

### Agente 3: interações (porta, leitura, pegar baixo)

Território: `sem_alvorada/engine/handactions.py` (novo: clipes de porta, leitura e pegar do chão, registrados no `Hands` por um gancho aditivo), `engine/interact.py` e `engine/doors.py` (só para disparar e sincronizar com o movimento da porta), `engine/player.py` e `body/rig.py` (só o necessário para o corpo inclinar ao pegar baixo, aditivo), `tests/test_maos_interacao.py`, `tools/movimento_ref/cenarios/interacoes.py`.

Tarefas:
1. **Mão na porta**: alcançar a maçaneta (altura de 86 a 122 cm, a das portas do jogo está em `layout`), abrir a mão antes do contato, fechar sobre a maçaneta (a pegada do Agente 2 serve; até lá, curvas fixas), girar o punho (maçaneta redonda: supinar e pronar; alavanca se houver), empurrar ou puxar com a mão acompanhando a maçaneta pelo arco da porta (a posição da maçaneta no mundo vem do `DoorManager`), soltar. Fechar a porta, a batida (a mão se retira, o corpo recua um pouco), e porta trancada (a mão tenta, o punho sacode e para). A trajetória da mão obedece a lei de alcance já medida; a duração do gesto casa com a abertura da porta (0,9 a 1,4 s, não pode alongá-la).
2. **Ler**: anotação e mapa com duas mãos a 35 a 40 cm do olho, polegares nas bordas, o papel levemente inclinado, o rosto se aproxima um pouco, a respiração move o papel. Anotação na parede: a mão e a cabeça chegam perto; sair do gesto sem salto.
3. **Pegar baixo**: o item no chão ou na prateleira baixa pede flexão do tronco e dos joelhos, não só do braço: o corpo desce e inclina (a CMU 26_09 e 111_09 medem a curva de 1,8 s), a câmera acompanha, os pés ficam no chão. Isso fecha o ponto aberto na fase 4.
4. **Itens principais** (chave, mapa, pilha, lanterna): conferir que o gesto de pegar de cada um continua único e coerente com a mão que anda, e que o jogador pode se mexer durante o gesto sem artefato.
5. Painéis: a sequência de cada interação em primeira pessoa e em terceira pessoa (câmera do palco, o corpo todo), lado a lado com um clipe da CMU quando houver (empurrar: 81_05, alcançar: 15_06, pegar do chão: 26_09, levantar: 111_09). Vídeos curtos. Entregar em `out/f5_3/final/`.

## Regras de convivência (as mesmas da fase 4)

- **Ninguém faz `git commit` ou `git push`.** O orquestrador faz o snapshot. Nunca `git checkout`, `restore`, `stash` ou `reset`.
- Arquivos compartilhados: `engine/hands.py`, `engine/handclips.py`, `body/rig.py`, `body/solver.py`, `body/fingers.py`, `conventions.py`, `README.md`. Antes de editar, **releia o arquivo** (outro agente pode ter mexido); edite pouco e de forma aditiva; rode os testes do arquivo depois de cada edição. Não apague código de outro agente.
- Para desenvolvimento, Workbench em 640x360. EEVEE só nos quadros finais (os cenários do estúdio em EEVEE a 640x360 custam uns 3 s por quadro). Saídas em `out/f5_<n>/`, painéis finais em `out/f5_<n>/final/`.
- Para gravar o jogo: `grava.montar_jogo(palco=False, pista=8.0)` (usa `out/estado_completo_<versão>.blend`; se não existir, constrói). `tests/` e `tools/prints_maos.py` mostram como preparar lanterna, itens e câmera. O fundo do estúdio (`prints_maos.studio`) é fixo no mundo: para andar, prenda-o à câmera.
- Testes que precisam passar no fim (Blender 5.0.1; no 4.2 quando possível): `test_hands`, `test_body`, `test_engine_core`, `test_inventory`, `test_speech_rule`, `test_cutscenes_player`, `test_movimento_ref`, `test_locomocao`, `test_maos_movimento`, `test_doors`, mais os novos de cada agente. `sim_playthrough` não pode piorar.
- Não mexer na velocidade, na cadência ou na altura do olho (fase 4). Se uma mudança de mão exigir isso, parar e dizer.
- **Honestidade**: cada número de relatório leva MEDIDO, DERIVADO ou ESTIMADO. Se uma referência real não existe (não há clipe de porta nem de lanterna de mão andando), dizer isso na tabela, e comparar com a lei física ou com a ordem de grandeza da pesquisa, não com um clipe que faz outra coisa.

## Como o orquestrador vai conferir

Fotos e vídeos da câmera do jogador, antes e depois, para cada comportamento; o painel do referencial da câmera (real contra jogo); tabela de números com origem; testes; e uma leitura honesta do que ainda destoa. O que o jogador não vê, ou vê pior que antes, conta como regressão.
