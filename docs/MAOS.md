# Mãos do Daniel: o que o jogador vê (fase 5)

Uma seção por agente, cada uma com a pesquisa que fez, o que mediu e o que ficou de fora. O contrato está em `docs/FASE5.md` e o método de comparação (rótulos MEDIDO, DERIVADO e ESTIMADO) em `docs/FASE4.md`.

---

## Agente 1: mãos que andam (balanço, apoio e inércia)

Arquivos: `sem_alvorada/handsway.py` (matemática pura), `sem_alvorada/engine/handsway.py` (liga ao jogo), `tools/movimento_ref/egocentrico.py` (painéis do campo de visão), `tools/movimento_ref/cenarios/maos_andando.py` (medição, tabela, painéis), `tests/test_maos_andando.py` (23 testes). Painéis, tabela, vídeos e fotos em `out/f5_1/final/`.

### O que estava errado

Medido no referencial da câmera (direita, frente, cima), com a lanterna na mão direita e o jogo a 1,7 m/s:

- **A mão afundava ao andar.** A mola de antes (`handheld.Sway`) fazia a mão seguir o *head bob* *somado* ao da câmera: a câmera cai 3,4 cm quando o corpo anda (queda do quadril, MEDIDO nas tabelas de marcha) e a mão caía mais 3,4 cm em relação a ela: dois bobs. Parada, a palma fica 13,0 cm abaixo do olho; andando, 16,3 cm; correndo, 18,3 cm. Correndo, só a cabeça da lanterna aparecia na beirada de baixo do quadro e a palma nunca entrava no campo (0% dos quadros).
- **Não havia movimento frente-trás** (0,0 cm de amplitude), e o vaivém vertical e o lateral eram os da cabeça (2,06 Hz), não os de um braço apoiado no ombro (a passada, 1 Hz, que é a do ombro real).
- **No giro do mouse a mão ia para o mesmo lado do giro** (3,8 cm para a esquerda quando se vira à esquerda). Com o corpo atrás do olhar (atraso de 145 ms a 180 graus/s, MEDIDO na fase 4) a mão, que está no corpo, tem de aparecer indo para o lado oposto.
- Nada respondia a arrancar, parar nem ao toque do calcanhar; correr e andar balançavam igual; agachado a mão balançava 6,3 cm de lado (a oscilação da cabeça passada à mão).
- O chaveiro era excitado só pelo movimento da mão *em relação à câmera*: a cabeça que sobe e desce não o balançava.

### O modelo

`handsway.CarryHand`, uma por mão. Em uma frase: **a mão é uma massa na ponta de uma mola com amortecedor (o antebraço) presa ao ombro do corpo do jogador**. O que se vê é a soma de quatro coisas, todas nos eixos da câmera:

1. **o ombro em relação à câmera**, sem a parte lenta (filtro passa-alta de 1,2 s: olhar para baixo é postura, não balanço), com um ganho por eixo que leva o ombro do corpo à amplitude do ombro real na mesma velocidade;
2. **a extensão da mola**, `x'' + 2 zeta w x' + w^2 x = -a_ombro`: responde à *aceleração* do ombro no mundo, não à posição. A velocidade constante a mão anda junto sem atraso nenhum; ao arrancar fica para trás e ao parar segue em frente e assenta;
3. **o braço de alavanca do peito**: o peito gira sobre os quadris mais devagar que a cabeça (o atraso de 70 a 170 ms da fase 4), e uma mão 35 cm à frente do ombro varre de lado (`LEVER_SHARE` = 0,6 do geométrico);
4. **o afastamento do modo** (correr: o cotovelo fecha e a mão sobe 4,5 cm, recua 2,5 cm e vai 1,5 cm para dentro, em 0,25 s) e o **toque do calcanhar** (um impulso de 0,10 m/s andando e 0,45 m/s correndo, espalhado em 40 ms).

Mais a rotação do punho em graus: cancela metade da inclinação e da rolagem que a cabeça faz por passada (o feixe fica mais firme que a cabeça), soma a respiração (0,20 graus de amplitude parado, 0,55 sem fôlego, na fase do peito do corpo) e a deriva postural (três senos de 0,19 a 1,00 Hz por eixo, 0,10 graus, o triplo com o fôlego esgotado). A guinada do feixe continua sendo do `Flashlight` (latência de 77 ms, agente 2).

A mola é integrada pela solução exata do degrau de aceleração em cada quadro (estável em qualquer `dt`; a 60 Hz o Euler errava uns 8% o pico de um impulso). Frequências e amortecimentos: andar 3,8 Hz e 0,45, correr 4,4 Hz e 0,60, agachado 4,0 Hz e 0,55 (ESTIMADO: 3 a 5 Hz e 0,4 a 0,7, `docs/FASE5.md`), com a frequência caindo com a massa do item na mão (lanterna de 0,30 kg: 3,8 para 3,5 Hz).

No jogo: `Hands.update` chama `HandSway.update` uma vez por quadro (câmera, ombros do corpo, fase da passada, fôlego) e `_pose_hand` lê `offset(side)`. A classe antiga continua em `handheld.Sway`; `cenarios/maos_andando.SwayAntigo` a recoloca na mesma interface para as fotos e vídeos de antes.

### Pesquisa

Resultados de busca, não revisão sistemática. Onde a fonte é fraca, o texto diz. Os de `docs/FASE5.md` (Collins 2009, Pontzer 2009, J Exp Biol 2020, tremor) continuam valendo e não repito.

- **Atenuação do passo do quadril à cabeça.** Pelve, ombro e cabeça atenuam a aceleração do passo em sequência, com coeficientes que não dependem da velocidade (coeficientes por segmento: pelve para ombro e ombro para cabeça); o ombro é o elo que o braço apoia. Só o texto de resumo foi lido; a aceleração vertical é descrita como quase constante. <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2596778/> e <https://link.springer.com/article/10.1186/1743-0003-5-30>. Uso: o ombro, e não a cabeça, é a base da mão.
- **Transiente do toque do calcanhar.** Andando, o crânio recebe cerca de 0,5 g e a tíbia 5 g (calcanhar duro); correndo, o impacto chega à cabeça em menos de 10 ms e é atenuado em cada segmento a caminho dela, em proporção que muda com a velocidade. <https://clinicalgaitanalysis.com/teach-in/transient/responses.html>, <https://lida.sport-iat.de/ta/Record/4046464>, <https://cris.utec.edu.pe/es/publications/modeling-of-heel-strike-transients-during-running/>. Uso: o impulso `HEEL_KICK` (ESTIMADO), de 30 a 50 ms.
- **Cabeça, depois tronco, ao virar.** Olhos, cabeça e tronco giram nessa ordem, a cabeça começa de 0,2 a 0,6 s antes do tronco em curvas andando (obstáculos) e fica mais virada para dentro da curva que o tronco; com o olhar fixo os segmentos giram juntos. A latência de 0,07 a 0,17 s do jogo é a medida na fase 4, com mouse; estes estudos são de curvas andando. <https://ntrs.nasa.gov/citations/20140003759>, <https://link.springer.com/article/10.1007/s00221-008-1525-3>, <https://www.doi.org/10.1007/S002210000533>. Uso: o peito atrás do olhar e o braço de alavanca.
- **Frequências do braço.** A ressonância do conjunto mão e braço medida em vibração fica entre 7 e 12 Hz (braço, ombro, pescoço e costas), e só aparece quando o ombro pode se mexer. Isto é tecido apertando uma ferramenta, não controle postural de um cotovelo dobrado; nenhuma fonte achada dá a frequência e o amortecimento de um antebraço que sustenta um objeto leve. Por isso 3 a 5 Hz e 0,4 a 0,7 seguem ESTIMADOS. <https://stacks.cdc.gov/view/cdc/189796>, <https://www.mechanics-industry.org/10.1051/meca/2014060>.
- **Carregar com a mão.** Carregar na mão reduz a oscilação do ombro e a rotação do tronco; o braço fica perto do quadril ou do ombro; restringir o balanço aumenta a taxa de passos. Nenhum estudo achado mede o objeto na mão. <https://documentserver.uhasselt.be/bitstream/1942/33892/1/10.1186_s12984-021-00844-0.pdf>, <https://en.wikipedia.org/wiki/Arm_swing_in_human_locomotion>. Uso: a mão acompanha o ombro, não balança como o braço livre.
- **Deriva e fadiga.** O tremor postural cresce com a fadiga e com a carga, mais nas bandas de baixa frequência (2 a 4 Hz) e também fora do eixo da gravidade; tem picos de 2 a 4 e 8 a 12 Hz com carga e um único pico abaixo de 2 Hz no eixo frente-trás. Não achei estudo de amplitude da deriva de 1 Hz em função da fadiga: o 0,10 a 0,30 graus é ESTIMADO. <https://core.ac.uk/works/125841703>, <https://iris.unicas.it/retrieve/c314950f-b3b8-4746-bcf7-483e3fc338eb/sensors-25-06502-v2.pdf>, <https://repository.derby.ac.uk/download/7e3856cd001ad2b04dc2d34b071643e1724840fb3850dc1212b3840751733bb3/800523/Lakie%20et%20al%20%282015%29%20-%20Increased%20gravitational%20force%20reveals%20the%20mechanical%2C%20resonant%20nature%20of%20physiological%20tremor.pdf>.

**O que não existe como medida.** Não há clipe de ninguém andando com uma lanterna na mão e o cotovelo dobrado. Os clipes de lanterna (77_05) são alguém parado olhando em volta; os de carregar (70_xx mala, 111_36 e 113_26 caixa) têm o braço esticado ou as duas mãos e a cabeça girando em relação ao tronco. O que é medido é o ombro e o braço livre no referencial da câmera, o atraso do tronco e as velocidades. A mão que carrega é comparada com a lei do modelo (DERIVADO) e com a ordem de grandeza da pesquisa (ESTIMADO).

### Resultados

A tabela inteira (38 linhas com critério mais as sem critério) está em `out/f5_1/final/tabela_maos_andando.md` e `.png`; **37 das 38 linhas com critério ficam dentro da tolerância**. As principais, em centímetros pico a pico (percentis 5 a 95) no referencial da câmera:

| Linha | Real ou lei | Antes | Depois | Origem |
|---|---|---|---|---|
| ombro direito andando, lado / frente / cima | 1,2 / 2,5 / 3,5 | 1,1 / 3,0 / 3,3 | 1,1 / 3,3 / 3,4 | MEDIDO (CMU 08_01 a 08_03, 1,5 a 1,6 m/s) |
| punho esquerdo livre, frente / cima | 63,7 / 20,5 | 61,9 / 17,8 | 61,9 / 17,8 | MEDIDO (o corpo não mudou) |
| cotovelo esquerdo livre, lado | 10,4 | 5,6 | 5,6 | MEDIDO, **fora da tolerância** (ficou de fora) |
| olhar 60 graus para baixo, punho esquerdo, cima | 63,7 | 56,8 | 57,1 | MEDIDO (CMU girada) |
| palma da lanterna andando, lado / frente / cima | 1 a 5 cada | 4,1 / 0,0 / 2,5 | 3,3 / 2,8 / 3,6 | ESTIMADO (ombro real + mola) |
| palma andando, frequência da subida e descida | passada 0,96 ou passo 1,92 Hz | 2,06 | 1,0 | MEDIDO (ombro real: 0,8 a 1,0 Hz) |
| palma correndo, lado / frente / cima | 1 a 7 cada | 2,8 / 0,0 / 4,0 | 5,4 / 3,2 / 5,7 | ESTIMADO |
| palma agachado, lado / frente / cima | 1 a 5 cada | 6,3 / 0,0 / 0,8 | 0,7 / 1,2 / 0,9 | ESTIMADO |
| correr menos andar, palma sobe | +5 (ombro) a +19 (mão livre) | -2,0 | +4,4 | MEDIDO no ombro, ESTIMADO na mão |
| partida de 5 m/s2, recuo da mão | 1,3 | 0,0 | 1,2 | DERIVADO (resposta ao degrau) |
| parada de 1,7 m/s em 0,65 s, avanço | 0,7 | 0,0 | 0,8 | DERIVADO |
| giro de 180 graus/s, tronco atrás do olhar | 70 a 170 ms | n/d | 145 ms | MEDIDO (fase 4) |
| giro de 180 graus/s, varrida lateral da mão | até 7 cm (peito soldado) | 3,8 para o lado errado | 4,0 para o lado certo | DERIVADO |
| parado, inclinação do feixe, pico a pico (graus) | 0,3 a 0,6 | 0,45 (e 1,4 de movimento da mão) | 0,3; mão parada a 0,5 mm | ESTIMADO |
| deriva do feixe, amplitude (graus) | 0,1 a 0,3 | 0 | 0,10 parado, 0,30 esgotado | ESTIMADO |

Entrega em `out/f5_1/final/`: `tabela_maos_andando.md` e `.png`; `painel_ego_andar.png`, `painel_ego_correr.png` e `painel_ego_agachado.png` (a trajetória da mão no referencial da câmera, o braço livre da CMU contra o do jogo, a palma da lanterna antes e depois, o campo de visão de 72 x 44 graus, as séries no tempo e o espectro); `painel_transientes.png` (partida, parada e giro do mouse); e, para andar, correr, andar e parar, agachado (estúdio) e subir a escada (casa escura), `video_<nome>.mp4` com a folha `video_<nome>_folha.png` (câmera do jogador, antes à esquerda e depois à direita, 20 quadros por segundo). `gravacoes/` guarda os `.npz` de onde tudo sai; `python -m tools.movimento_ref.cenarios.maos_andando medir` os refaz.

Uma advertência sobre as fotos: a mão aparece **maior e mais alta** depois, e isso é de propósito, não é a pegada que mudou (a pegada é do agente 2). Antes a mão afundava 3,3 cm ao andar e 5,3 correndo, e só a ponta aparecia na beirada; agora ela fica onde o gesto a pôs e sobe 4,5 cm ao correr.

Testes: 23 em `tests/test_maos_andando.py`, entre eles a transmissibilidade da mola contra a lei (2% de erro de 1 a 4,5 Hz, com o ganho do estimador de aceleração a 60 Hz), a resposta ao degrau de aceleração e ao toque do calcanhar contra integrações independentes, o ombro e o braço livre contra a CMU, o atraso do tronco, o olhar para baixo sem salto de velocidade e o balanço do chaveiro contra um pêndulo independente excitado pela aceleração da palma (correlação passa de 0,7).

### Decisões

- **Problema:** a mão afundava ao andar e saía do quadro correndo. **Solução:** presa ao ombro do corpo, com a aceleração dele como entrada da mola. **Motivo:** o balanço do ombro em relação à cabeça é medido (1 a 3 cm), e é o que uma mão apoiada nele tem de fazer; a mola de antes dobrava o bob da cabeça.
- **Problema:** a 3 Hz de mola a mão balançava mais que a cabeça no mundo. **Solução:** 3,8 Hz (e 4,4 correndo). **Motivo:** com a lanterna na mão a ressonância caía a 2,7 Hz, perto dos 2,06 Hz do passo; o braço faz o contrário (amortece).
- **Problema:** o chaveiro balançava só pelo movimento da mão. **Solução:** o pêndulo sente a aceleração do pivô no mundo (a cabeça que sobe e desce o balança, parar o lança para a frente), e o toque do calcanhar e o filtro de aceleração foram espalhados para o pêndulo não ser excitado por picos de um quadro (sem isso, andando, ele passava de 60 graus pico a pico). **Motivo:** é a física do pêndulo composto da fase 4, só que com a entrada certa. Andando, em regime, ele balança 48 graus pico a pico para o lado e 42 para a frente (rms 10 graus), até 90 na partida (a aceleração de 5 m/s2 vale 27 graus de quase-estático); a oscilação para a frente passa de -14 para +20 graus entre o toque do calcanhar esquerdo e o direito, o máximo logo depois do direito, como a desaceleração do toque manda. Correndo ele varre 150 graus pico a pico e chega ao limite de 75 graus.
- **Problema:** o filtro passa-alta guardava por segundos um quadro ruim logo depois de pôr o corpo noutro lugar (3 s de saturação). **Solução:** constante de tempo curta nos primeiros segundos e reinício ao ver um salto do ombro, do peito ou do corpo. **Motivo:** teletransporte, checkpoint e fim de cena acontecem de verdade.
- **Decisão que mexe no jogo:** a mão da lanterna aparece mais (a palma entra no quadro andando e correndo) e correndo fica mais alta e perto. Um quadro de lanterna só com a cabeça aparecendo na beirada era o que o jogo mostrava; o que o corpo real faz é elevar o braço.

### O que ficou de fora

- O cotovelo livre esquerdo balança 5,6 cm de lado contra 10,4 cm no real: o braço livre do `Locomotion` só flexiona no plano sagital (o punho, que também recebe a torção do tronco, bate: 9,8 contra 9,0).
- **Olhar para baixo:** o balanço do braço livre bate com a CMU girada (amplitudes dentro de 15%), mas a posição média do punho fica uns 10 cm mais baixa e 9 cm mais perto, e ele entra no quadro uns 10 graus depois (a 60 graus: 17% dos quadros no jogo, 39% na referência). A referência gira a cabeça em torno do olho, sem a translação do olho em torno do pescoço nem a flexão do tronco, então não sei dizer qual dos dois está certo. Não mexi no corpo.
- **Escada:** a câmera sobe em rampa (`Z_FOLLOW_STAIRS`), então a mão não leva um impulso por degrau; ela balança a 0,75 Hz, o ritmo dos degraus, com 2,5 / 1,5 / 3,0 cm (lado, frente, cima).
- O tremor de 8 Hz não entra: de 0,02 a 0,05 graus no punho, menos de um pixel a 1280 x 720.
- O pêndulo do chaveiro continua com 0,08 de amortecimento (fase 4). Andando balança +-24 graus em regime, no alto do razoável (com 0,2 seriam +-15); correndo vai ao limite de 75 graus, e eu não sei se uma chave real faz tanto. Não mudei o amortecimento porque não há medida de chaveiro na mão.
- A pose e o ângulo da mão que segura (cotovelo, punho, pegada) são do agente 2; esta mão acompanha o que ele escrever, só soma o balanço. A rotação por mouse do feixe também é dele (`Flashlight.offset`); a minha é só a translação do giro do tronco.
- **Sim do robô (`sim_playthrough`)**: a história completa leva 202 s contra 201,8 s com o modelo desligado (os mesmos objetivos, a menos de 0,6 s); na caçada o robô morreu 14 vezes (e 29 em outra rodada da mesma versão: o número oscila), e os dois `objetivos que falharam: KEY, KEY` da caçada são os mesmos com o modelo ligado e desligado.
- **Vídeos:** estúdio (andar, correr, andar e parar, agachado) e casa escura (escada). A casa escura andando em linha reta não foi renderizada: o começo do corredor do jogo tem um brilho que estoura o quadro e a esteira de teste (`--esteira`) precisou de outro trecho.

---

## Agente 3: interações (porta, leitura, pegar baixo)

Arquivos novos: `sem_alvorada/engine/posture.py` (a postura de alcance, matemática pura), `sem_alvorada/engine/handactions.py` (pegar baixo, mão na porta, mão preparada, leitura com as duas mãos), `tools/movimento_ref/pegar_baixo.py` (medida do pegar do chão no mocap, gera `assets/referencia/pegar_baixo_ref.json`), `tools/movimento_ref/cenarios/interacoes.py` (sequências, tabelas, cenário `pegar_baixo` do `comparar`), `tests/test_maos_interacao.py` (18 testes). Painéis, vídeos e tabelas em `out/f5_3/final/`.

### O que estava errado

- **Pegar baixo era só o braço.** O alcance parava a 0,52 m do olho e o item subia sozinho até a mão (`GLIDE`, 0,4 s). Uma pilha na gaveta baixa (0,31 m) ou a lanterna no criado-mudo (0,55 m, o primeiro gesto do jogo) ficava a 0,7 a 1,0 m da palma quando os dedos "fechavam". O real é uma curva do corpo todo (olho 0,75 a 0,85 m mais baixo), medida abaixo.
- **A porta abria sozinha.** A maçaneta virava 0,05 s depois do [E], a folha saía em 0,32 s e nenhuma mão chegava perto dela. O ponto "mão na maçaneta" ficou aberto na fase 4.
- **Ler era uma mão só.** A folha ficava a 30 cm do olho, em pé, segurada por baixo, e a mão da lanterna parada ao lado, sem ligação com o papel. Com o leitor aberto o jogo congelava tudo, até a respiração.

### Pesquisa

Resultados de busca, não revisão sistemática. A ferramenta de leitura de páginas estava bloqueada neste ambiente (DNS), então o que está abaixo vem dos trechos que a busca devolveu, não dos artigos inteiros: onde só li o resumo, diz.

- **Abrir porta, cinemática do braço e do punho.** Há medidas de braço e punho abrindo portas com maçaneta redonda e alavanca (captura com 10 câmeras, nove voluntários; tese da Strathclyde com 6 câmeras Vicon e capítulo só de porta), de trajetórias e forças em 29 portas e 15 gavetas de casas e de um escritório (Georgia Tech), e de pessoas indo até uma porta e abrindo-a, com e sem copo na mão. Não consegui os números por articulação, só os resumos. Uso: a ordem do gesto (alcançar, pegada, giro, empurrar ou puxar, soltar) e a faixa funcional do antebraço. <https://boneandjoint.org.uk/Article/10.1302/1358-992X.94BSUPP_XXXVI.BORS2011-065>, <https://stax.strath.ac.uk/concern/theses/1n79h434j>, <https://repository.gatech.edu/entities/publication/3bda8452-1c99-48f3-b85e-89d30b3726b1>, <https://archive.measuringbehavior.org/mb2008/individual_papers/Symposium%20Fikkert/Symposium_Fikkert_Egges.pdf>, <https://scholarlycommons.pacific.edu/shs-all/341>.
- **Quanto o antebraço gira.** A faixa funcional é de 50 graus de pronação a 50 de supinação (Kapandji, citado por um artigo de terapia ocupacional), contra 71 e 81 graus de amplitude total; mexer uma chave de fenda usa em média 77,6 graus; quem tem o antebraço travado compensa com o ombro e o tronco. Nenhuma fonte dá o ângulo de uma maçaneta. <https://sage.cnpereading.com/doi/10.5014/ajot.2023.050238>, <https://pure.ewha.ac.kr/en/publications/limited-forearm-motion-compensated-by-thoracohumeral-kinematics-w/>. Uso: o giro do punho de 42 graus além dos 38 da chegada (80 graus de supinação no total) é ESTIMADO e fica dentro dos 81 de amplitude.
- **Norma da maçaneta.** A norma pede ferragem que se opere com uma mão, sem pegada firme, pinça ou torção do punho, e força de ativação de no máximo 5 lbf (22,2 N); maçaneta redonda em geral não cumpre (pede torção); a BHMA A156.2 limita o torque a 28 lbf-in nas alavancas. Nenhuma norma dá ângulo de giro. <https://kc.allegion.com/kb/article/are-all-levers-ada-compliant>, <https://idighardware.com/2023/07/accessibility-requirements/>. Uso: a maçaneta do jogo é redonda, então o punho gira de verdade, e a pegada é de torção, não de alavanca.
- **Abertura da mão ao alcançar.** O pico da velocidade do punho vem em 33 a 40% do movimento e a abertura máxima dos dedos em 60 a 70% (controles de um estudo de reabilitação, 39,5% e 69,7%); dedos fecham depois, até o contato; a pré-forma já aparece a uns 45% do tempo. Nenhum dos estudos usa maçaneta. <https://pmc.ncbi.nlm.nih.gov/articles/PMC8891374/table/T2>, <https://bicr.atr.jp/~kawato/Ppdf/YaopingEBR05r.pdf>. Uso: a mão abre durante o alcance e é aberta a 60%, o mesmo perfil do `handclips.reach`.
- **Curvar contra agachar.** No levantamento do chão a diferença grande entre as duas técnicas está no joelho; picos sagitais de um modelo de exoesqueleto (agachar contra curvar-se): coluna lombar 57 e 56 graus, quadril 58 e 48, joelho 52 e 16, tornozelo 19 e 12. Cada fase (descer e subir) leva cerca de 2 s em tarefas lentas de laboratório, e a velocidade de levantar a carga fica perto de 0,6 m/s nas duas. A coluna sofre mais ao se curvar (momentos, compressão e cisalhamento maiores). <https://pmc.ncbi.nlm.nih.gov/articles/PMC2651112>, <https://arxiv.org/pdf/1910.01184>, <https://bmcmusculoskeletdisord.biomedcentral.com/counter/pdf/10.1186/1471-2474-10-15>. Uso: só como conferência de ordem de grandeza; os números do jogo vêm do mocap (abaixo), que dá o corpo todo no tempo.
- **Ler com o material na mão.** A distância de leitura de texto de mão difere da de uma tela fixa (Ergonomics, 1995), e inclinar o papel para o rosto mantém a página toda na mesma distância focal; o ângulo de visada dirige a flexão da cabeça e do pescoço (tablets), e olhar o papel plano na mesa pede flexão de pescoço parecida com a do celular. Não achei estudo de papel segurado com as duas mãos nem a inclinação em graus. <https://stars.library.ucf.edu/scopus1990/1968>, <https://ergoweb.com/?p=29426>, <https://www.sciencedaily.com/releases/2012/01/120125091055.htm>. Uso: 35 a 40 cm (FASE5), o papel inclinado 12 graus (ESTIMADO) e o rosto, não o pescoço, que se aproxima.
- **Cabeça e olho ao ler andando.** Cabeça e olhos se coordenam de outro jeito lendo do que andando: movimentos de olho disparados pela cabeça são cerca de duas vezes mais lentos ao ler. <https://pmc.ncbi.nlm.nih.gov/articles/PMC10080958/>. Uso: nada direto; foi lido para decidir não mexer o olhar (o que o jogador faz com o mouse é dele).

**O que não existe como medida.** Não há clipe de porta com maçaneta, de mão segurando papel com polegares nas bordas nem de lanterna na mão enquanto lê. O pegar baixo tem 12 clipes. O jogo é comparado, na porta, com a lei de alcance da fase 4 e as ordens de grandeza acima (tudo rotulado). O clipe 81_05 (empurrar objeto pesado) entra só como referência do tempo.

### Medido na CMU: pegar baixo

`python -m tools.movimento_ref.pegar_baixo` (12 clipes: 26_09 a 26_11, 69_70 a 69_75, 143_10, 143_11, 111_17, 111_18; os 115_xx saíram, o olho mergulha neles em 0,3 s, de 3 a 6 vezes mais depressa). Escala do Daniel (olho a 1,65 m). Cada pessoa escolhe um ponto de um contínuo, e o ângulo do tronco é o que muda ao longo dele:

| | agachar (tronco 24 a 45 graus) | curvar de pernas retas (tronco 100 graus) |
|---|---|---|
| olho desce (MEDIDO) | 0,78 m (0,60 a 0,85) | 0,78 m (0,74 a 0,83) |
| joelho dobra (MEDIDO) | 87 graus (51 a 137) | 24 graus (3 a 125) |
| quadril cai (MEDIDO) | 0,70 m | 0,05 a 0,11 m |
| olho acima do punho que pega (MEDIDO) | 0,55 a 0,78 m, mediana 0,63 | idem |
| ombro ao punho no fundo (MEDIDO) | 0,46 a 0,57 m | idem |
| descida até 90% do fundo, fundo, subida (MEDIDO) | 0,95 s (0,52 a 2,22), 0,35 s, 1,30 s | 1,11 s (0,89 a 1,99), 0,62 s, 0,93 s |

A cabeça fica, ao fim, quase em cima do objeto (o punho fica de 0,26 m atrás a 0,07 m à frente do olho).

### O que mudou

**Pegar baixo** (`posture.py`, `handactions.pickup_clip`, `Player`, `Locomotion`):

1. A geometria decide: onde está o item em relação ao olho (distância horizontal, lado, altura), qual mão, onde está o ombro de verdade (`BodyRig.shoulder_world`). A menor postura (`posture.dip_to_reach`) que põe o item a 0,56 m do ombro (DERIVADO: 85% do alcance de 0,66 m) com a cabeça no máximo 0,90 m mais baixa e, no mínimo, 0,60 m acima da mão (MEDIDO). Se não chega, o corpo ainda avança até 0,30 m (ESTIMADO).
2. A câmera desce, avança e o tronco se inclina em jerk mínimo (`Player.camera_pose`, `ReachPosture`): a técnica é o ângulo do tronco, que cresce de 50 graus por metro de descida (agachar) a 130 (curvar), e perto agacha, longe se curva. O quadril acompanha sozinho (a cabeça é a câmera; o `Locomotion` já derruba o quadril para pôr o pescoço no ponto), e o joelho dobra pelo IK; a cabeça pende à frente do C7 em 45% da curvatura do tronco (MEDIDO: o vetor C7 a olho gira cerca de 0,7 vezes o ângulo do tronco, dos quais o olhar para baixo dá uns 20 graus). A pelve gira 38% da curvatura, não a coluna (a coluna toda dava as costas arredondadas).
3. A mão sai 25% da descida depois do tronco (a mão passa de 10% da distância depois de o tronco ter descido uns 20%, nos clipes, ESTIMADO) e o alcance leva `move_time(distância no mundo, da mão solta ao item)`. O corpo sobe quando os dedos fecham (evento `rise`, essencial: um gesto interrompido ou uma cutscene também fazem o corpo subir).
4. **Passo assistido.** O jogo deixa interagir a 2 m e o braço chega a 0,6 m. Nos clipes de 69_70 a 69_75 a pessoa anda até o objeto antes de se curvar, então, se o item está a mais de 0,45 m do olho, o corpo anda até ele ficar a 0,35 m, no máximo 0,70 m, em passo lento (metade da velocidade de andar, a passada normal do `Player`); o que a colisão não deixa (prateleira, mesa) é ensaiado antes (`feasible_step`) e a postura leva em conta o que sobrou. Qualquer tecla de andar cancela. Não mexi em velocidade, cadência nem altura do olho.

**A mão na porta** (`handactions.DoorHand`, `DoorManager.toggle(delay=...)`, `Interact._use_door`):

1. A mão esquerda (a direita segura a lanterna; sem lanterna, a direita) alcança a maçaneta (cabeça de latão, 0,95 m do piso, a 7 cm da borda), abre os dedos até 60% do alcance, pousa a palma sobre ela, fecha os dedos, gira o antebraço (supinação de 38 para 80 graus), acompanha a maçaneta pelo arco da folha a cada quadro (a posição vem do `DoorManager`: a trilha da mão é calculada ao vivo, `LiveTrack`), solta quando o braço não alcança mais ou aos 60% do movimento da folha (abrir) e volta ao braço em 0,5 s.
2. A folha espera a mão: `toggle(delay)` atrasa a maçaneta, a folha e os sons pelo tempo de chegar e fechar os dedos. A duração do movimento da folha não mudou (conferida: 0,87 s de 2% a 98% com e sem a mão).
3. **A mão se prepara sozinha.** Olhando a porta de perto (o centro da folha na mira, a maçaneta a até 0,95 m do olho, andando a menos de 1 m/s) por 0,3 s, a mão sai até 7,5 cm da maçaneta e espera; o [E] só fecha os dedos. Sem isso a folha esperaria 0,7 s a mais em cada abertura. Para fechar e para portas trancadas não se prepara (fechar é decisão do jogador; a trancada se descobre tentando).
4. Porta trancada: a mão chega, o punho gira 26 graus e para, e sacode 3 vezes em 0,05 s (o mesmo `RATTLE_BOUNCE` da folha); depois solta. Fechar: a mão segue a maçaneta o quanto o braço alcança e solta; a folha termina de fechar sozinha.
5. Sem gesto (a porta abre como na fase 4): mão esquerda com item na mão, correndo ou com pressa, maçaneta fora do alcance, corpo falso (`NullArm.shoulder_world_position` devolve None). Chave de comparação: `SA_MAOS_INTERACAO=0` desliga o pegar baixo, o passo e a porta.

**Ler** (`handclips.FACE_ITEM`, `NEAR_ITEM`, `READ_LANTERN`, `handactions.with_reading_hand`, `Game._tick_reading`):

1. A folha a 38,8 cm do olho (centro) com o topo inclinado 12 graus (ESTIMADO), o centro 6,7 graus abaixo da linha do olhar (DERIVADO da pose) e a 38,8 cm (FASE5: 35 a 40 cm). A mão da lanterna vem para a borda direita da folha com o polegar solto na margem, e a luz aponta para a página; isso está no clipe de levantar a folha, porque com o leitor aberto o jogo não atualizava as mãos. Para o mapa, a mesma coisa com a direita mais afastada.
2. Com o leitor aberto o jogo agora atualiza o corpo, as mãos e a respiração (o resto do mundo continua pausado: a pilha não gasta); a folha se mexe com a respiração do punho, 0,20 grau em repouso e 0,55 sem fôlego, do `handsway` do agente 1.
3. Nota baixa (mesa de centro, 0,44 m): o mesmo pegar baixo e a mesma subida. Nota na parede: o passo até ela, o campo de visão que fecha 17% (FOV_ZOOM, já existia) e o recuo sem salto (conferido em `test_hands`).

### Resultados

#### Pegar baixo: o jogo antes e depois contra a CMU

Cada coluna do jogo é um item de verdade da casa, a partir da distância dita, medida por `python -m tools.movimento_ref.cenarios.interacoes tabela` (`out/f5_3/final/tabela_pegar_baixo.md`, curvas em `curvas_pegar_baixo.png`). As duas primeiras colunas são o MEDIDO nos 12 clipes (mediana e faixa). Tudo na tabela é MEDIDO no jogo ou na CMU; a linha "fase 4" é o jogo antes desta fase, medido do mesmo jeito.

| métrica | CMU curvar (n=7) | CMU agachar (n=5) | gaveta 0,31 m, a 0,45 m | gaveta 0,31 m, a 0,9 m | chão, a 0,55 m | criado-mudo 0,55 m, a 0,9 m | prateleira 0,51 m, a 0,9 m | escrivaninha 0,77 m, a 0,9 m |
|---|---|---|---|---|---|---|---|---|
| olho desce (m) | 0.78 (0.48 a 0.83) | 0.78 (0.60 a 0.85) | 0.69 | 0.70 | 0.85 | 0.47 | 0.51 | 0.27 |
| olho avança (m) | 0.20 (0.11 a 0.55) | 0.17 (0.04 a 0.30) | 0.50 | 0.33 | 0.42 | 0.27 | 0.48 | 0.37 |
| tronco inclina (graus) | 72.90 (37.20 a 115.90) | 45.40 (23.50 a 102.60) | 59.50 | 60.40 | 54.20 | 51.70 | 76.30 | 40.00 |
| joelho dobra (graus) | 23.80 (3.10 a 124.90) | 86.80 (51.40 a 137.40) | 107.10 | 84.70 | 121.00 | 55.30 | 41.90 | 48.00 |
| quadril cai (m) | 0.11 (0.05 a 0.75) | 0.70 (0.14 a 0.72) | 0.41 | 0.43 | 0.61 | 0.25 | 0.12 | 0.12 |
| descida até 90% (s) | 1.11 (0.89 a 1.99) | 0.95 (0.52 a 2.22) | 0.80 | 0.87 | 0.90 | 0.67 | 0.63 | 0.43 |
| no fundo (s) | 0.62 (0.34 a 0.84) | 0.35 (0.15 a 0.57) | 0.60 | 0.60 | 0.63 | 0.63 | 0.73 | 0.77 |
| subida (s) | 0.93 (0.77 a 2.40) | 1.30 (0.53 a 2.10) | 0.73 | 0.73 | 0.83 | 0.57 | 0.60 | 0.43 |
| palma ao item no contato, fase 4 (m) | - | - | 0.90 | 1.09 | 1.21 | 0.90 | 0.96 | 0.65 |
| palma ao item no contato, agora (m) | - | - | 0.03 | 0.03 | 0.07 | 0.04 | 0.27 | 0.17 |

- O corpo desce 0,47 a 0,85 m; a CMU, 0,78 m (0,48 a 0,85). O que fica menos fundo (escrivaninha, 0,27 m) é o item que fica a 0,77 m do chão: a chave só pede uma curvatura leve, como a pessoa real faria.
- A palma chega a 3 a 7 cm do item em quatro dos seis casos (antes: 0,65 a 1,21 m). Prateleira e escrivaninha ficam a 0,27 e 0,17 m: o móvel impede o corpo de avançar o que falta; o item sobe o resto, como na fase 4, só que menos.
- Duração do gesto do [E] até a mão fechar com o corpo de volta: cerca de 3,3 s contra 2,5 s antes (MEDIDO no jogo, do [E] até o corpo de volta em pé).
- Painel contra a CMU, clipe 26_09 (`out/f5_3/final/pegar_baixo_cmu/`: `folha_contato.png`, `video.mp4`, `tabela.txt`): 6 de 8 métricas dentro da tolerância. As duas de fora são contra a mediana dos 12 clipes e as duas ficam dentro da faixa deles: o olho avança 0,49 m (mediana 0,22, tolerância 0,25; faixa dos clipes 0,04 a 0,55) e o joelho dobra 137 graus (mediana 66, tolerância 50; faixa 3 a 137). O item está no chão, 0,55 m à frente, e o jogo escolhe o agachado fundo, que a CMU também faz (agachar: 87 graus, 51 a 137).

#### A mão na porta: tempos do [E] em diante

Não há clipe de porta na CMU, então a tabela abaixo é o jogo contra ele mesmo (sem a mão, fase 4) e contra a lei de alcance da fase 4 (`handclips.move_time`, MEDIDO em 199 alcances, não de porta). Tudo é MEDIDO no jogo, quadro a quadro, com `tabela_porta`. Na linha de fechar, o "palma-maçaneta" não vale e foi deixado em branco: a mão solta aos 0,2 s e o que se mediria depois é a distância até uma maçaneta que se afasta com a folha; a maçaneta "gira" aos 1,95 s porque é o trinco assentando no fim do fechar.

| caso | maçaneta gira | folha sai | folha dura (2% a 98%) | gesto da mão dura | palma-maçaneta no giro (cm) | palma-maçaneta no empurrão, máx. (cm) |
|---|---|---|---|---|---|---|
| caso | maçaneta gira | folha sai | folha dura (2% a 98%) | gesto da mão dura | palma-maçaneta no giro (cm) | palma-maçaneta no empurrão, máx. (cm) |
|---|---|---|---|---|---|---|
| sem a mão (fase 4) | 0.05 | 0.32 | 0.87 | - | - | - |
| com a mão, preparada olhando a porta 1 s | 0.18 | 0.43 | 0.87 | 1.58 | 8.5 | 7.6 |
| com a mão, [E] logo ao chegar | 0.77 | 1.03 | 0.87 | 2.17 | 7.7 | 7.3 |
| porta trancada | - | - | - | 1.77 | - | - |
| fechar a porta aberta | 1.95 | 0.95 | 0.93 | 2.60 | - | - |

Contra a lei e as ordens de grandeza (a coluna "rótulo" diz de onde vem o valor de referência):

| grandeza | referência | rótulo da referência | jogo antes | jogo agora |
|---|---|---|---|---|
| tempo de alcançar e fechar os dedos na maçaneta | `move_time` da fase 4: cerca de 0,6 a 0,75 s para um alcance de 0,3 a 0,5 m | MEDIDO (alcances da CMU, não de porta) | 0 (a porta mexia sem mão) | 0,77 s com o [E] logo ao chegar (MEDIDO no jogo); 0,18 s se a mão já estava pronta |
| folha começa a mexer depois do [E] | a folha tem de esperar a pegada: sem pegada não há força | ESTIMADO (lógica física, sem número) | 0,32 s | 0,43 s preparada, 1,03 s fria (MEDIDO no jogo) |
| duração do movimento da folha (2% a 98%) | FASE5 pede o gesto casado com 0,9 a 1,4 s de abertura; a duração da folha é da fase 4 e não foi tocada | contrato | 0,87 s | 0,87 s (MEDIDO; a diferença com e sem a mão é menor que 0,04 s, testada) |
| abertura dos dedos ao alcançar | pico em 60 a 70% do movimento (33 a 40% para a velocidade do punho) | MEDIDO em estudos de reabilitação (só resumos) | sem mão | 60% (DERIVADO do perfil de `handclips.reach`) |
| giro do punho na maçaneta redonda | faixa funcional do antebraço: 50 graus de pronação a 50 de supinação (71 a 81 de amplitude total) | MEDIDO em literatura de terapia ocupacional, só o resumo | sem mão | 80 graus de supinação (38 de chegada mais 42 de giro): dentro da amplitude total, acima da faixa funcional; ESTIMADO, não separei o que cabe ao ombro e ao cotovelo |
| palma ao centro da maçaneta (esfera de 5 cm) | raio 2,5 cm mais a espessura da palma: uns 5 a 7 cm | ESTIMADO | sem mão | 7,7 a 8,5 cm no giro, 7,3 a 7,6 cm no máximo do empurrão (MEDIDO no jogo) |
| porta trancada: giro e sacudida | a maçaneta trava na ponta do giro; a mão não vence a trava | ESTIMADO | folha chacoalhava sozinha | punho gira 26 graus, sacode 3 vezes em 0,05 s, solta; gesto de 1,77 s (MEDIDO no jogo) |

#### Ler: a folha na mão

| grandeza | referência | rótulo | jogo antes | jogo agora |
|---|---|---|---|---|
| distância do centro da folha ao olho | 35 a 40 cm (FASE5) | contrato; resumos de ergonomia de leitura de material na mão, sem número | 30 cm | 38,8 cm (DERIVADO da pose, testado) |
| inclinação do topo da folha | levemente inclinada; sem número encontrado | ESTIMADO | 0 graus, em pé | 12 graus; o centro fica 6,7 graus abaixo da linha do olhar (DERIVADO da pose) |
| mão que não segura o papel | polegar na borda da folha | contrato | parada ao lado da lanterna | a mão da lanterna vem à borda direita da folha (testado: está mais perto do lugar de ler que do de segurar, a menos de 5 cm) |
| respiração com o leitor aberto | a folha acompanha o punho | contrato | tudo congelado | mexe 0,20 grau em repouso e 0,55 sem fôlego (`handsway`, do agente 1); o mundo continua pausado |
| entrada e saída | sem salto | contrato | n/a | maior passo da mão por quadro abaixo do limite do teste, nota na parede sem salto na saída |

Painéis (primeira e terceira pessoa, vídeos de 10 a 15 quadros por segundo, Workbench): `porta_abrir`, `porta_abrir_frio`, `porta_trancada`, `porta_fechar`, `ler_nota`, `ler_mapa`, `pegar_gaveta`, `pegar_chao`, `pegar_criado`, `pegar_prateleira`, `pegar_chave`, `pegar_nota_baixa` (`_video.mp4` e `_folha.png` de cada um em `out/f5_3/final/`). Na leitura a mão esquerda que segura a folha fica quase toda abaixo do quadro (só um pedaço do polegar aparece na borda inferior esquerda); a direita, a da lanterna, aparece inteira. Vê-se a esquerda melhor no painel de terceira pessoa.

#### Testes e partida simulada

- `tests/test_maos_interacao.py`: 18 testes, passam no Blender 5.0.1 e no 4.2. Varredura no 5.0.1: test_hands (33), test_body, test_engine_core (38), test_inventory (27), test_speech_rule (4), test_cutscenes_player, test_movimento_ref, test_locomocao, test_maos_movimento (22), test_doors (34), test_objetos_fisica, todos verdes.
- `tests/sim_playthrough.py`, gesto ligado contra desligado (`SA_MAOS_INTERACAO=0`): a história termina em 202,3 s contra 198,4 s (MEDIDO; o robô abre as portas e pega os itens com o gesto, nada travou); na caçada de 5 min simulados as mortes são 14 contra 29; "objetivos que falharam: KEY, KEY" é igual nos dois (já existia na fase 4). A diferença de mortes não é um efeito projetado: o gesto atrasa a abertura das portas e muda por onde o robô cruza a casa; não a uso como medida de nada.

### Decisões

- **Problema: o item voava até a mão. Solução: a postura e o passo, não mais alcance.** Motivo: esticar o braço de 0,52 para 0,7 m não faria sentido no corpo (o cotovelo sai do quadro e o punho quebra); a pessoa real se curva, e a medida dela está no mocap. O custo é a duração do gesto: de 2,5 s para 3,3 s por item baixo. O sim_playthrough da história passou de 198,4 s para 202,3 s (+3,9 s).
- **Problema: a mão leva 0,7 s para sair debaixo do quadro e a porta respondia em 0,32 s. Solução: a mão se prepara sozinha olhando a porta de perto e a folha espera a mão.** Motivo: sem preparar, a folha sai 0,71 s depois do [E] (medido); preparada, 0,11 s depois do que saía. A duração do movimento da folha não mudou. Quem preferir a porta instantânea: `SA_MAOS_INTERACAO=0`.
- **Problema: o jogador aperta o [E] a 2 m de um item ou porta e o braço não chega. Solução: o passo assistido para itens (o jogo anda por ele, 0,7 m no máximo, cancelável) e, para portas, só gesto quando a maçaneta está ao alcance.** Motivo: ou o item voa, ou o jogador anda; escolhi a segunda, que é o que as pessoas fazem. É uma decisão de jogo: o jogador se move sem apertar tecla, devagar e por pouco. Para desligar: `handactions.STEP_MAX = 0`.
- **Problema: ler com as duas mãos, mas a direita segura a lanterna. Solução: a mão da lanterna vem ao papel com o polegar solto na margem e a luz na página; a folha fica na esquerda.** Motivo: não dá para largar a lanterna no escuro. Os dedos são os de antes até a pegada por contato do agente 2 cobrir folha e mapa.

### O que ficou de fora

- **A batida de porta.** Com pressa (correndo ou mais de 1,3 vezes o passo) a porta fecha ou abre como na fase 4, sem mão: esperar 0,6 s a mão contradiz a pressa. A mão que se retira e o corpo que recua ao bater não foram feitos.
- **Porta com item na mão esquerda** (chave, mapa, pilha, nota): sem gesto, para não guardar e tirar o item a cada porta. Guardar e voltar custa 0,6 s a mais por porta; a mão direita não serve, tem a lanterna.
- **Maçaneta fora do alcance** (mais de 0,62 m do ombro com 0,30 m de inclinação e, nas portas que empurram, o passo de 0,7 m): sem gesto. Quem aperta o [E] a 2 m de uma porta vê o que via antes.
- **Item longe demais** mesmo depois do passo (prateleira atrás de um móvel): a mão para onde o braço chega e o item sobe o resto (a pilha da prateleira infantil e a chave da escrivaninha ficam a 0,2 a 0,4 m da palma no contato, ver tabela). Era pior antes (0,9 a 1,0 m).
- **Fechar a porta**: a mão acompanha a maçaneta por cerca de 0,2 s, não pelo arco todo, porque a maçaneta de uma porta aberta a 90 graus se afasta 1,2 m do corpo parado. Uma pessoa real daria um passo com ela.
- **O rosto que se aproxima ao ler** só existe na nota da parede (passo mais zoom). Nas outras o papel já está a 38 cm.
- **A pegada de porta e papel**: curvas de dedo fixas (esfera: 0,52 a 0,68; folha: as de antes). Quando o agente 2 entregar a pegada por contato, a maçaneta (esfera de 5 cm) é o primeiro caso novo.
- **Painel lado a lado com o 81_05 (empurrar) e com o 15_06 (alcançar)**: não fiz. Só o pegar baixo tem painel contra a CMU (26_09). Para a porta e a leitura não há clipe: os painéis são do jogo, de primeira e terceira pessoa.
- **EEVEE**: os vídeos e folhas da casa são Workbench (EEVEE leva minutos por quadro na casa); não há quadros EEVEE desta fase.


---

## Agente 2: lanterna e pegadas

Arquivos novos: `sem_alvorada/body/grasp.py` (fechamento dos dedos por contato, ajuste da mão no item, medida na pele), `sem_alvorada/grasp_data.py` (o resultado, gerado), `sem_alvorada/engine/gripdrive.py` (dos canais de um clipe às juntas), `sem_alvorada/engine/lanternaim.py` (elevação do braço, giro do cano para ler, quando bater), `tools/movimento_ref/cenarios/pegadas.py` (medida, gerador, fotos, painéis), `tests/test_pegadas.py` (14 testes). Alterados de forma aditiva: `body/fingers.py` (rotações de um dedo à parte, cascata com metas por junta), `body/rig.py` e `engine/fallbacks.py` (`set_finger_joints`), `engine/handclips.py` (garras e pose da lanterna, canais `grip` e `press`, pré-forma, `palm_tap`), `engine/hands.py` (ganchos), `engine/flashlight.py` (avisa a piscada). Painéis e tabelas em `out/f5_2/final/`.

### O que estava errado

Medido na malha de pele já deformada pelo esqueleto (a do corpo no jogo) contra a malha do item, em milímetros. Penetração é o quanto o ponto mais fundo da pele entra no item; folga é a menor distância à superfície.

- **Lanterna**: o mindinho entrava 11,6 mm no cano e o polegar 9,1 mm; o indicador ficava a 21,2 mm e o médio a 12,2 mm do cano; a palma a 8,8 mm. Só 2 das 5 partes que deviam tocar tocavam.
- **Pilha na palma**: o polegar entrava 3,8 mm; indicador, médio, anelar e mindinho flutuavam a 38, 37, 28 e 12 mm.
- **Chave**: o polegar a 51 mm da cabeça, o indicador a 14 mm, o médio e o anelar atravessavam 2,2 e 4,7 mm. Não havia pinça.
- **Mapa e anotação**: nenhum dedo toca a folha (20 a 53 mm), e o polegar, que devia estar na frente, não está.
- **A mão da lanterna**: o punho dobrava 57 a 61 graus nos gestos (o limite do solver é 72) porque o cano rolava 62 graus em torno do eixo para a palma ficar sob ele.
- **A mão abria quase nada ao alcançar**: o curl ia de relaxado a "aberto" (indicador de 0,22 a 0,16) e ficava parado até o contato, sem pico e sem fechar antes de tocar.
- **O polegar do interruptor**: um empurrão de 0,32 no curl que decaía exponencialmente, sem curso nem tempo de interruptor.

### Pesquisa

Resultados de busca, não revisão sistemática. A ferramenta de leitura de páginas estava bloqueada neste ambiente (DNS), então o que está abaixo vem dos trechos que a busca devolveu, não dos artigos inteiros; onde só li o resumo, diz.

- **Flexão dos dedos numa pegada de cilindro** (tomografia, 10 homens, cilindros de 10, 60 e 120 mm): no de 60 mm o indicador flexiona MCP 39,7, PIP 48,0 e DIP 35,2 graus, o médio 46,3, 48,1 e 34,5. Cilindro mais fino pede mais flexão, e a PIP passa a ser a maior (no de 10 mm a PIP é maior que MCP e DIP, no de 120 não há diferença). A razão DIP/PIP é menor no cilindro fino. Li só o resumo e uma linha da tabela (o texto da tabela veio truncado). Shimawaki et al. 2019: <https://onlinelibrary.wiley.com/doi/10.1155/2019/2839648> e <https://pmc.ncbi.nlm.nih.gov/articles/PMC6339738>
- **Modelo de pegada por contato**: um modelo cinemático da mão que "enrola" os dedos no cilindro previu os ângulos com 2,8 +- 12,2 graus de erro médio (bom para MCP e PIP, pior para DIP). Buchholz e Armstrong: <https://deepblue.lib.umich.edu/items/86e3c0b4-2785-43b5-b962-bb890894c683>. O contato na pegada de força é discreto (pontas dos dedos e cabeças dos metacarpos), não contínuo: <https://pure.psu.edu/en/publications/is-power-grasping-contact-continuous-or-discrete/>
- **Pré-forma**: a abertura máxima vem em cerca de 60% do gesto (dois estudos), 2/3 (outro) ou depois de 75% (revisão e um estudo de 2024), e cresce linearmente com o tamanho do objeto, com uma margem de segurança acima dele. As fontes não concordam num número, daí a faixa de 60 a 75%. Resumos apenas: <https://link.springer.com/doi/10.1007/BF00240965>, <https://eprints.soton.ac.uk/272553/1/HillISB2011.pdf>, <https://link.springer.com/article/10.1007/s00426-024-01947-8>, <https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2012.00332/pdf>
- **Punho**: as tarefas do dia a dia cabem em 60 graus de extensão, 54 de flexão, 40 de desvio ulnar e 17 de radial, e a maioria cabe em 70% disso (40 graus de flexão e de extensão) (40 adultos, 1991): <https://mayoclinic.elsevierpure.com/en/publications/functional-ranges-of-motion-of-the-wrist-joint/>. Punho neutro (reto) é a recomendação geral de ergonomia, sem número neste conjunto.
- **Pinça**: com o indicador fundido na PIP a 40 a 50 graus a pinça polegar-indicador fica mais natural (o vão de pinça cai 10 a 14%): <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3827381/> e o grupo de trabalhos de pinça que a busca devolveu (<https://pmc.ncbi.nlm.nih.gov/articles/PMC4330130>). Não achei ângulos de pinça de referência.
- **Bater na lanterna que pisca**: o mau contato da pilha é a causa comum de uma lanterna que pisca ou apaga, e bater ou sacudir a reassenta por um instante (fabricantes mandam limpar os contatos; fóruns descrevem a batida). Sem medida de quando, quantas vezes nem de que jeito. <https://help.fenix-store.com/en-US/why-does-the-ld30r-happen-to-flicker-340412>, <https://www.candlepowerforums.com/threads/flickering-flashlights.184666/post-2292792>
- **Tempo de reação visual simples**: 200 a 250 ms (190 a 220 ms em estudantes, 300 ms em testes com teclado de notebook): <https://www.dovepress.com/evaluation-of-simple-visual-reaction-time-of-different-colored-light-s-peer-reviewed-fulltext-article-OPTO>
- **Pegada de lanterna**: o que está em `docs/FASE5.md` (patente Streamlight, técnicas de busca). Não achei estudo que meça cotovelo ou punho. **Tempo de um dedo sobre uma tecla** (dwell): a busca não devolveu um número, só que a distribuição é normal; usei 80 a 150 ms de memória, ESTIMADO.

### Como o fechamento por contato funciona

`HandSkin` leva os vértices de pele de cada osso da mão (a malha do corpo no repouso) junto com as falanges; `HandKinematics` faz a cinemática com as mesmas rotações do esqueleto (`fingers.finger_quaternions`), e uma conferência contra a armadura avaliada deu 0,2 a 0,4 mm de erro. Cada dedo parte de uma pré-forma quase esticada e fecha rumo ao padrão de uma pegada de força (MCP 0,70, PIP 0,82 e DIP 0,66 do curso, 57, 82 e 44 graus no indicador: o padrão de Shimawaki com 20% a mais de flexão por o cano ser mais fino, ESTIMADO). As três juntas avançam juntas, na proporção do padrão. A falange que toca a malha trava a junta que a move e as de trás dela; as da frente continuam até tocar (o dedo se enrola no cano). O contato sai de bisseção (14 passos), então a folga final é de centésimos de milímetro e nenhuma falange entra. O polegar da lanterna paira a 3 mm do botão (busca por coordenadas em 3 ângulos, sem atravessar o cano), e o polegar apertado cede 1 mm no botão (curso ESTIMADO, a borracha cede).

`fit_grip` ajusta onde a mão fica no item (6 graus de liberdade, mais uma busca de giro em torno do cano) para a palma encostar sem entrar (folga alvo 3 mm na lanterna, 0,8 na pilha) e os dedos fecharem com contato, e fecha os dedos contra a mão que o IK do corpo de fato entrega naquela pose (o pulso não dobra tudo o que se pede). Isso roda uma vez, offline (`python -m tools.movimento_ref.cenarios.pegadas gerar`, 70 s), e grava `grasp_data.py`: o jogo só lê números. O chaveiro e a pilha, cujas malhas têm normais misturadas ou pontas abertas (o sinal de "dentro" não vale), usam a forma analítica da parte que a mão toca (caixa arredondada da cabeça, cilindro da pilha); a lanterna usa a malha (alumínio, moleta e borracha; o refletor, o vidro e o latão são internos).

No jogo, cada mão tem um canal `grip` (cinco valores, 0 a 1: quanto cada dedo já se fechou NO item) e, na direita, `press` (o interruptor). A pose dos dedos é a mistura, junta por junta, do curl livre com a pose fechada por contato. A cascata (`FingerCascade`) passou a aceitar uma meta por junta, com 40, 66 e 92 ms de constante acumulada: a base sai na frente e a ponta chega depois (conferido em teste).

### Tabela: pele contra a malha do item (MEDIDO, mm)

Penetração máxima / folga mínima de cada parte da mão, no repouso. "Deve tocar" é o que a pegada pede; "livre" é o que fica solto de propósito. Tabela completa em `out/f5_2/final/tabela_penetracao_folga.png` e `.txt`.

| Item | Parte | Deve tocar | Antes: penetra / folga | Depois: penetra / folga |
|---|---|---|---|---|
| lanterna | polegar | livre (paira) | 9,1 / 0,0 | 0,0 / 0,0 |
| lanterna | indicador | sim | 0,0 / 21,2 | 0,0 / 0,0 |
| lanterna | médio | sim | 0,0 / 12,2 | 0,0 / 0,0 |
| lanterna | anelar | sim | 0,1 / 0,0 | 0,0 / 0,0 |
| lanterna | mindinho | sim | 11,6 / 0,0 | 0,0 / 0,0 |
| lanterna | palma | sim | 0,0 / 8,8 | 0,0 / 3,1 |
| pilha | polegar | sim | 3,8 / 0,0 | 0,0 / 0,7 |
| pilha | indicador | sim | 0,0 / 38,3 | 0,1 / 0,0 |
| pilha | médio | sim | 0,0 / 36,7 | 0,2 / 0,0 |
| pilha | anelar, mindinho | livre | 0,0 / 27,7 e 11,8 | 0,2 / 0,0 |
| pilha | palma | sim | 0,0 / 6,5 | 0,0 / 0,5 |
| chave | polegar | sim | 0,0 / 50,9 | 0,0 / 2,0 |
| chave | indicador | sim | 0,0 / 13,8 | 0,8 / 0,0 |
| chave | médio, anelar | livre | 2,2 e 4,7 / 0,0 | 0,0 / 3,0 e 5,4 |
| chave | mindinho | livre | 0,0 / 1,9 | 0,0 / 14,8 |
| mapa e anotação | polegar, dedos | sim | 0,0 / 20 a 53 | sem mudança (ver o que ficou de fora) |

Resumo (penetração máxima; folga média das partes que devem tocar): lanterna 11,6 mm e 8,5 mm antes, 0,008 mm e 0,6 mm depois; pilha 3,8 e 20,4 antes, 0,2 e 0,3 depois; chave 4,7 e 32,3 antes, 0,8 e 1,0 depois. Tocam (folga menor que 2,5 mm): lanterna 2 de 5 antes e 4 de 5 depois (a palma fica a 3,1 mm de propósito: a palma de verdade cede), pilha 1 de 4 e 4 de 4, chave 0 de 2 e 2 de 2.

Duas ressalvas de método. O chaveiro balança (a respiração o excita, até 7 graus em torno da cabeça) e isso desloca as faces da cabeça uns 2 mm da pinça; a tabela é com o pêndulo parado (a medida com ele solto deu 2,1 mm de penetração no indicador e 4,3 de folga no polegar). E o contato da pele é a folga de uma malha rígida contra outra: a polpa de um dedo real cede cerca de 1 mm, que não está no modelo.

### Postura de segurar a lanterna

| Medida | CMU 77_05 | Antes | Depois | Origem |
|---|---|---|---|---|
| flexão do punho parado (graus) | sem medida (neutro: 0 a 20) | 57 a 60 | 13 | MEDIDO no jogo |
| flexão do cotovelo (graus, 0 = esticado) | 119 | 107 | 110 | MEDIDO (CMU e jogo) |
| braço a quantos graus da vertical | 42 | 58 | 56 | MEDIDO |
| punho acima do ombro / comprimento do braço | -0,27 | +0,09 | +0,09 | MEDIDO |
| flexão máxima do punho na troca de pilha | | 61 | 52 | MEDIDO no jogo |
| na recusa | | 61 | 41 | MEDIDO no jogo |
| na primeira pegada (instante 0,9 s do alcance) | | 70 | 70 | MEDIDO, não mudou |

O que mudou é o giro do cano em torno do eixo (`FLASH_ROLL`: de -62 para +60 graus) junto com a mão ajustada ao cano: o punho passou de quase no limite do solver a quase reto, e o cotovelo continua entre 100 e 120. O braço fica mais alto que o real (56 graus da vertical contra 42, punho acima do ombro contra abaixo) de propósito: a mão da lanterna tem de aparecer no quadro de 72 x 44 graus, e 27% do braço abaixo do ombro põe o punho fora do campo (a lanterna cai a 32 graus abaixo do eixo, com 22 de meia-altura de quadro). A busca (4 mil poses, solver de verdade) com a lanterna no quadro e o feixe a cerca de 1 m da mira escolheu a posição (0,135, -0,095, -0,300) m e a inclinação (8, 6, -6) graus, como já era, e só trocou o giro. O antebraço não entra no quadro: o punho está a 18 graus abaixo do centro e o antebraço, que segue para trás e para baixo, fica fora do campo (0 cm visíveis na busca). Pedi a busca com recompensa de antebraço visível e o solver sempre o põe fora; se quiser mostrá-lo, a mão tem de ir uns 5 cm para baixo e para a direita, e a lanterna sai do quadro.

### Apontar a luz

O atraso do feixe atrás da câmera já estava (69 ms medidos na fase 4 contra 77 ms do mocap, constante `SWAY_FOLLOW`; não mexi). O que entrou é o braço: o antebraço acompanha o passo do olhar só em parte. No mocap 91_18 (olhar em volta com cuidado, 29 graus de passo da cabeça) a inclinação da elevação do punho contra o passo da cabeça é -0,13 (direita) e -0,08 (esquerda): a mão fica onde está (MEDIDO, um clipe). No 77_05 deu 1,19, mas ali a mão sobe junto para levantar a lanterna, então não vale (confundido). `lanternaim.LanternAim` usa `FOLLOW` = 0,3 (ESTIMADO) com uma constante de 90 ms e gira a mão em torno do ombro (`shoulder_world_position`, do agente 3) por `-LIMIT tanh(0,7 passo / LIMIT)`, com `LIMIT` = 10 graus, sem girar o cano: o feixe continua indo para onde se olha.

| Passo do olhar | Mão em relação à câmera (altura, cm) | Flexão do punho (graus) |
|---|---|---|
| 0 | 0 (referência) | 15 |
| +20 | -5,8 | 31 |
| +40 | -7,0 | 43 |
| +60 | -7,3 | 54 |
| -30 | +2,9 | 3 |

Olhar para cima faz a mão descer uns 7 cm em relação à câmera e saturar; olhar para baixo a faz subir. Antes a mão ia junto com a câmera (0 cm). O punho nunca passa de 54 graus (o conforto do solver começa em 55).

### Gestos

- **Interruptor** (F, e o clique do primeiro uso e da troca de pilhas): o polegar desce em 45 ms, sustenta 40 ms e sobe em 75 ms, 160 ms no total (ESTIMADO: a busca não achou número; fica na faixa de 80 a 150 ms de um dedo sobre uma tecla, um pouco acima porque o interruptor é de borracha), com 1 mm de curso. A luz muda no instante da tecla, e o polegar chega ao botão 45 ms depois: abaixo do que se percebe como atraso entre toque e luz. Não mudei isso para não somar latência ao jogo. Teste: o polegar sai do repouso e volta.
- **Batida na palma** (`palm_tap`, ESTIMADO; não há medida de batida): quando a pilha fraca faz a luz piscar e a mão esquerda está livre, a esquerda sobe de baixo do quadro, bate com a palma na lateral do cano, a 8 cm do punho, e volta; a direita sente 7 mm e 2 graus. A decisão sai 0,35 s depois da piscada (reação visual de 200 a 300 ms mais decidir), com probabilidade 0,6, e nunca mais de uma vez por 12 s. Com a pilha no mínimo e a luz piscando 2 vezes por segundo deu 5 batidas em 60 s (uma a cada 12,5 s). Dura 1,6 s (0,8 s até a batida, porque o braço parte de baixo do quadro), então chega depois de a piscada acabar; não conserta a luz (não mexi na jogabilidade). Não bate com item na esquerda, na roda de itens, lendo ou durante outro gesto.
- **Giro do cano para ler**: com o jogador lendo (nota na parede, mapa perto, leitor aberto) o cano gira 17 graus para baixo e a mão desce 1,2 cm, vai 2 cm para o centro e 3 cm para trás (mola de 7 por segundo, uns 0,3 s para assentar). `Hands.set_lantern_reading(True)` é o gancho para as outras interações; a detecção automática usa `_reading_job` e `_left_mode`.

### Pré-forma da mão no alcance

A abertura (polegar a indicador, MEDIDA na armadura avaliada) chega ao máximo em 66 a 67% do alcance e fecha rumo ao item; antes era um platô quase plano até o contato (pico indefinido: 71 a 100%, o argmax de uma reta) e fechava só depois de tocar.

| Item | Pico (% do alcance) | Abertura máxima (cm) | No contato (cm) | Depois do contato (cm) |
|---|---|---|---|---|
| lanterna | 66 (antes: platô) | 8,4 (antes 7,4) | 3,4 (antes 7,4) | 2,9 a 4,1 |
| chave | 66 (antes: platô) | 8,2 (antes 7,4) | 5,0 (antes 7,4) | 3,7 a 3,9 |
| pilha | 67 (antes: platô) | 8,4 (antes 7,4) | 4,9 (antes 7,4) | 1,8 |

A faixa real é de 60 a 75% (as fontes divergem). A abertura de 8 cm não foi calibrada com o tamanho do item (a literatura diz que cresce com ele, e a margem acima do objeto é de poucos centímetros): é um valor só para os três, ESTIMADO. Figura: `out/f5_2/final/perfil_de_abertura.png`.

### Decisões (problema, solução, motivo)

1. **Os dedos fechavam por curva fixa, o item ficava onde a mão não alcançava.** Fechei os dedos contra a malha do item, por bisseção, na pele de verdade. Motivo: dá número (penetração e folga) e vale para qualquer item novo, em vez de ajuste a olho por item.
2. **A mão mais certa para o cano põe o polegar do outro lado do interruptor.** A garra de antes pedia a palma sob o cano, e o botão ficava a 73 mm do polegar. Busquei o giro da mão em torno do cano e achei o lado em que o polegar alcança o botão sem atravessar o cano. Isso muda como a lanterna aparece de lado, e por isso girei o cano para o punho ficar reto.
3. **Resolvi o IK de verdade dentro do ajuste.** A mão que o corpo entrega não é a que se pede quando o pulso passa de 55 graus: no começo os dedos fechavam contra uma mão que não existia (9,7 mm de penetração no mindinho na pilha, por 6 centésimos de grau de diferença na junta). Agora o fechamento é contra a mão entregue, e o ajuste pune pulso perto do limite.
4. **Pilha e chave usam forma analítica.** A malha da pilha tem a ponta aberta e a do chaveiro tem normais misturadas, então o sinal "dentro ou fora" trocava de lado com um centésimo de grau de diferença. Medir contra um cilindro e uma caixa é mais honesto que medir contra uma malha em que o sinal não vale (e desprezo relevos de até 1,5 mm da cabeça do chaveiro).
5. **Os dados são gerados e o jogo só lê.** Resolver no início do jogo levaria 0,3 s por item e travaria o primeiro quadro do alcance; o arquivo `grasp_data.py` é pequeno, e o teste mede a pele de novo e quebra se alguém mexer na mão ou no modelo.
6. **Mão mais alta que a real, de propósito.** Ver a tabela de postura: o quadro de 44 graus de altura obriga.

### O que ficou de fora

- **Mapa e anotação sem pegada por contato.** Procurei a mão atrás da folha com o polegar na frente (24 orientações da mão, várias posições, ajuste fino, com e sem o braço no custo) e não achei uma que o braço alcance sem atravessar a folha: o polegar precisa dar a volta na borda e os outros dedos ficam do outro lado, e os melhores resultados eram o polegar na frente com a mão inteira também na frente (custo alto), ou o antebraço dobrado no limite. A garra de antes continua (a mão fica atrás da folha, fora do quadro, sem atravessá-la: 0 mm de penetração, 20 a 53 mm de folga); a leitura do agente 3 trata das mãos na folha. Quem retomar: a busca está em `pegadas.papel_do_item`, `grasp.cube_rotations` e `fit_grip(scan=("starts", ...))`, só falta um critério melhor para a folha (a borda da folha como o lugar do contato, não a face).
- **Maçaneta**: o agente 3 pediu a pegada de uma esfera; `grasp.Role` e `fit_grip` servem (é só dar a malha e o papel), mas não foi feito.
- **A pegada da chave tem o médio, o anelar e o mindinho soltos** (curl fixo 0,42 a 0,56), com 3 a 15 mm de folga da cabeça, em vez de um 'grip' de chaveiro com os dedos enrolados nas argolas.
- **A abertura máxima da pré-forma não escala com o item** (ver acima).
- **A primeira pegada ainda dobra o punho até 70 graus** no instante 0,9 s do alcance, o mesmo valor de antes; vem do braço subindo do quadril para a mesa com a mão virada, não da pegada. Não mexi.
- **O polegar do interruptor não aparece no quadro do jogador**: fica do lado do cano oposto à câmera, então o aperto só se vê pelo movimento da mão e pela luz.
- **Os vídeos** são de primeira pessoa em EEVEE a 480 x 270 e 12 quadros por segundo (EEVEE leva segundos por quadro); a batida e o interruptor não têm painel de estúdio próprio, só aparecem no vídeo e nos testes.

### Testes

`tests/test_pegadas.py`: 14 testes (envelope do interruptor, cascata por junta, equivalência das rotações, mistura do `grip`, padrão de flexão de uma pegada de força, penetração e contato por item, pegada da chave, punho neutro e cotovelo de 100 a 120 graus, elevação parcial, giro do cano, interruptor, uma batida por rajada e só com a esquerda livre, pico da abertura entre 58 e 78% do alcance). Passam no Blender 5.0.1 e no 4.2. Também passam (5.0.1): `test_hands` (33), `test_body`, `test_engine_core` (38), `test_inventory` (27), `test_speech_rule` (4), `test_cutscenes_player`, `test_movimento_ref`, `test_locomocao`, `test_maos_movimento` (22), `test_doors` (34) e `sim_playthrough` (história em 202,3 s contra 198,5 s na linha de base da fase 5, a diferença vem dos gestos das outras frentes; os mesmos dois `objetivos que falharam: KEY, KEY` da caçada).
