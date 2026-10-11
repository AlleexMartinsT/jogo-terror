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

Fotos e vídeos (câmera do jogador, antes à esquerda e depois à direita): `out/f5_1/final/`.

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
- Vídeos de agachar, parar e escada estão em `out/f5_1/final/`; a casa escura foi feita só andando e na escada.
- Três testes de `test_maos_movimento` (troca de pilhas, duração do alcance da lanterna, velocidade no meio do alcance) e um de `test_speech_rule` (tempo para pegar a chave) falham com a pegada nova de lanterna do agente 2, e falham do mesmo jeito com o meu modelo desligado; não são desta seção.
