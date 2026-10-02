# Fase 3: animação, corpo, HUD e inventário

Documento de trabalho dos cinco agentes. Vale tanto quanto `docs/CONTRACT.md` e `docs/ACABAMENTO.md`
(o padrão de modelagem continua o de lá). Em caso de conflito, este arquivo ganha para o que é da fase 3.

## O que o usuário pediu, em ordem

1. **Cutscenes bem animadas e fluidas.**
2. **Pegar itens com uma animação leve, simples e única por tipo de item.** Exemplo dado: a lanterna é pega
   desligada, ligada, e pisca algumas vezes, sinalizando que a bateria não está em 100%.
3. **Portas abrindo suavemente, com chance de ranger.** O ranger é ruído: pode alertar a entidade se ela estiver perto.
4. **Corpo visível em primeira pessoa** (olhar para baixo mostra tronco, braços, pernas e pés do Daniel).
5. **HUD com pouca informação.** Objetivos só no menu de pausa (Esc). O personagem só fala quando o jogo
   começa e quando pega um item principal.
6. **Inventário em roda**: segura a tecla, mexe o mouse na direção do setor, solta. No máximo cinco itens seguráveis.

A entidade (o Alto) continua fora de escopo para modelagem. Animação dela dentro das cutscenes é permitida.

## Decisões de projeto (já tomadas; não reabrir sem motivo forte)

**Duas mãos.** A lanterna fica na **mão direita** o tempo todo, desde que o jogador a tenha. A **roda escolhe o que vai na mão esquerda.**

**Cinco setores, fixos, sentido horário a partir do topo:**

| Setor | Tipo (`C.ITEM_*`) | Na mão esquerda | Uso |
|---|---|---|---|
| 1 topo | `FLASHLIGHT` | mão esquerda livre (só a lanterna) | F liga/desliga |
| 2 | `BATTERY` | uma pilha D na palma | R troca as pilhas da lanterna |
| 3 | `KEY` | chaveiro com o coelhinho balançando | tilinta quando o jogador corre |
| 4 | `MAP` | mapa da cidade aberto | E, sem alvo na mira, aproxima o mapa do rosto |
| 5 | `NOTE` | a última anotação lida | E, sem alvo na mira, reabre o leitor |

Setor de item que o jogador não tem fica apagado e não pode ser escolhido. Cada tipo é um setor: por isso o
máximo é cinco. Pilhas contam como um setor com número (o estoque). Anotações só entram na roda depois da primeira lida.

**O mundo não pausa com a roda aberta.** O mouse deixa de girar a câmera enquanto a tecla está apertada. O jogador
continua andando. Soltar sem ter movido o mouse (dentro da zona morta) mantém o que está na mão.

**Teclas:** roda = `Q` ou `Tab` (segurar); lanterna `F`; pilhas `R`; interagir `E`; pausa `Esc`.

**Fala do personagem (`Game.say`)** só em dois momentos: logo que a partida começa (depois da abertura) e ao pegar
um item principal (lanterna, chave, mapa, cada pilha reserva; mais a fala de "tenho tudo" quando o último chega).
Todo o resto (porta trancada, lanterna morta, sem pilha, nada lá fora) deixa de ser fala: vira estado visual
(a dica de interação muda de texto, o ícone da bateria pisca, a mão tenta e a porta não cede). Legendas das
cutscenes continuam, são outra coisa.

**HUD de jogo**, só isto: mira (um ponto) e, quando há alvo, a dica de interação; um medidor de som mínimo (a
barra VOCÊ com a marca do limiar de audição e um indicador quando a ENTIDADE é audível; AMBIENTE vai para a
pausa), que fica quase transparente quando tudo está em silêncio; a bateria da lanterna só aparece por alguns
segundos ao ligar, ao trocar, e continuamente abaixo de 25%; o fôlego só quando está acabando; a roda quando aberta;
o leitor de notas. **Nada de lista de objetivos, nada de contagem de pilhas reserva no canto.**
**Menu de pausa (Esc):** objetivo atual, lista de coleta (chave, mapa, pilhas x/3), medidor de ambiente, controles.

**Canal de ruído das interações.** Tudo que o jogador faz com as mãos continua a ser ruído no `NoiseSystem`
(`Game.make_noise`), com os valores de `conventions.NOISE_PLAYER`.

## Territórios

Cada agente edita **só** o que está na sua linha. Arquivos compartilhados (última coluna) aceitam edições
pequenas e aditivas, feitas com `Edit` depois de reler o arquivo, nunca reescrevendo-o por inteiro.

| Agente | É dono de | Pode tocar com cuidado |
|---|---|---|
| **1. Inventário, HUD e falas** | `engine/inventory.py`, `engine/hud.py`, `engine/hudmodel.py`, `engine/screens.py`, `engine/canvas.py`, `engine/texts.py`, `engine/controls.py`, `engine/director.py`, `engine/interact.py`, `story.py` (tudo menos `CUTSCENE_TEXT`), `tests/test_engine_hud.py`, `tests/test_engine_ui_api.py`, `tests/test_inventory.py` (novo) | `engine/game.py` (fases `paused` e `play`, mensagens), `README.md` (controles) |
| **2. Corpo do jogador** | `sem_alvorada/body/` (pacote novo), registro da etapa `body` em `build.py`, `tests/test_body.py` (novo), `tools/prints_corpo.py` (novo) | `conventions.py` (constantes `OBJ_BODY*`), `engine/fallbacks.py` (`NullBody`/`NullArm`), `engine/builder.py` (câmera: plano de corte, FOV) |
| **3. Animação dos itens** | `engine/hands.py`, `engine/flashlight.py`, `engine/state.py` (carga inicial da bateria), `engine/handheld.py` (novo), `props/flashlight.py`, `props/item_models.py`, `props/handheld_*.py` (novos), `tests/test_hands.py` (novo) | `engine/interact.py` (só a ponte `_take` e `_read`), `engine/game.py` (só `toggle_flashlight`, `reload_flashlight`), `props/items.py`, `conventions.py` |
| **4. Cutscenes** | `cutscenes/` inteiro, `tests/test_cutscenes_*.py`, `tools/` de captura de cutscene, `story.CUTSCENE_TEXT` | `engine/host.py`, `engine/director.py` (só gatilhos de cutscene), `entity/motion.py` (só poses para as cenas) |
| **5. Portas e som** | `engine/doors.py`, `world/doors.py`, `world/doorspec.py`, `audio/` inteiro (catálogo, receitas, ruído), `ai/` (só o que for necessário para reagir ao ranger), `tests/test_audio_*.py`, `tests/test_ai_*.py`, `tests/test_doors.py` (novo) | `conventions.py` (tabelas de ruído), `engine/player.py` (só passos e escada) |

Quem precisa de uma mudança fora do seu território **pede ao dono** no relatório final (o orquestrador integra),
a menos que seja a ponte já descrita aqui.

## Contratos entre módulos

### Corpo (agente 2 entrega, agentes 3 e 4 usam)

Pacote `sem_alvorada/body/`, exportando `BodyRig`. O `Game` já o procura e cai em `NullBody` se não existir
(`engine/fallbacks.py` tem a interface completa em versão vazia: **esse arquivo é a especificação de métodos**).

```python
body = BodyRig(scene)
body.set_visible(bool)                        # o Game liga nas fases play/paused/reading
body.update(dt, player, bob)                  # todo quadro; player = engine.player.Player; bob = (lateral, vertical)
body.place(x, y, z, yaw)                      # fora do jogador (cutscenes)
body.pose(name, seconds=0.0)                  # poses de corpo inteiro: "stand", "lying_bed", "sit_bed", "driving"
body.reset()
arm = body.arm("L" | "R")                     # ArmControl
arm.set_target(position, rotation_deg, weight)   # mão no ESPAÇO DA CÂMERA: X direita, Y cima, -Z frente, metros
arm.set_fingers(curls, spread=0.0, blend=1.0)    # curls = 5 valores 0..1 (polegar ao mindinho)
arm.release(blend=1.0)                        # volta à pose solta (braço caído, mão relaxada, fora do quadro)
arm.hold(obj, offset=None) / arm.drop(obj)    # prende um objeto ao osso da mão
arm.hand_world_position()                     # (x, y, z) do centro da palma
arm.ready                                     # True quando a rig real existe
```

- O corpo anda com `player.x, y, z_visual`, `yaw`, `pitch`, `speed`, `running`, `crouching`, `stride_phase` (cada π é um passo).
- A cabeça não aparece (o corte do pescoço fica atrás da câmera). Olhar para baixo mostra peito, camisa de flanela,
  barriga, cinto, coxas, joelhos e tênis. O corpo fica atrás do eixo da câmera o bastante para o plano de corte
  não atravessar os ombros.
- Pernas: ciclo de caminhada sincronizado com `stride_phase`, agachar, correr, parar, subir escada. Respiração no peito.
  Tronco acompanha o `pitch` e o giro (o corpo atrasa um pouco em relação à câmera).
- Os braços resolvem por IK de dois ossos até o alvo (reaproveite a matemática de `entity/skeleton.py`). Com
  `weight=0` voltam à pose solta; `weight` intermediário mistura. Sem alvo, os braços balançam de leve com o passo.
- Orçamento: corpo completo ≤ 30 mil triângulos; texturas ≤ 512x512 por área, filtro Linear.
- Câmera de referência dos alvos: a `PlayerCam`. Em cutscene, `body.attach_view(camera_obj)` troca a referência.

### Mãos (agente 3 entrega, agente 1 usa)

`engine/hands.py`, classe `Hands`. O `Game` já a chama; a versão atual é um esqueleto sem animação.

```python
hands.held                      # tipo na mão esquerda (C.ITEM_*; FLASHLIGHT = esquerda livre) ou None
hands.busy                      # True durante animação sem interrupção; o Game ignora [E] enquanto isso
hands.pickup(target, on_contact, on_done=None)   # target = engine.interact.Interactable; devolve False se ocupada
hands.equip(kind, on_done=None)                  # troca o item da mão esquerda (a roda chama isto)
hands.toggle_flashlight() / hands.reload_flashlight()   # F e R
hands.begin_read(note_id, on_open) / hands.end_read()   # anotações no chão e no inventário
hands.update(dt, bob)           # todo quadro de jogo
hands.reset()                   # novo jogo e checkpoint
```

- `on_contact()` é o instante em que os dedos tocam o item: ali o item some da cena e o inventário muda.
- Animações **únicas por tipo**, curtas (0,6 a 1,4 s), com antecipação, ação e acomodação; mão e antebraço entram
  pelo canto do quadro, nunca teletransportam. Nada de animação que dure tanto que o jogador sinta que perdeu o controle.
- **Lanterna (primeira vez):** a mão direita pega o item desligado, traz para a altura do peito, o polegar clica,
  a luz acende e **pisca duas ou três vezes** (a lanterna já foi usada: a carga inicial passa a ser `C.FLASHLIGHT_FOUND_CHARGE = 0.78`,
  constante nova em `conventions.py`, aplicada em `GameState` quando o jogador a encontra), estabiliza e a mão assume a posição de segurar. Daí em diante F é só o clique.
- A lanterna viva (`Flashlight`) e o viewmodel passam a ser a mesma coisa que a mão direita segura. O viewmodel
  atual (`props/flashlight.py`, que traz uma mão e uma manga embutidas) perde essa mão: quem fornece a mão agora é o corpo.
- **Chave:** a mão esquerda ergue o chaveiro e o balança uma vez (pêndulo simples). **Mapa:** desdobra em dois tempos.
  **Pilhas:** recolhe na palma, olha e guarda; R usa as duas mãos (a esquerda leva a pilha à lanterna). **Anotação:**
  pega a folha, traz até o rosto e abre o leitor; ao fechar, a folha desce.
- Enquanto `held` não for `FLASHLIGHT`, a mão esquerda mostra o objeto e o balanço/respiração deste continua.

### Inventário (agente 1 entrega, agente 3 usa)

`engine/inventory.py`, classe `Inventory` (esqueleto presente). O `Game` chama `inventory.update(dt, inp)` antes
do jogador e zera `look_dx/look_dy` se `inventory.wheel_open`.

```python
inventory.owned()               # tipos que o jogador tem, na ordem dos setores
inventory.count(kind)           # pilhas: estoque; anotações: quantas lidas; demais: 0/1
inventory.held                  # = hands.held
inventory.wheel_open, inventory.selection
inventory.update(dt, inp)       # inp.wheel_held (nível), inp.wheel_dx, inp.wheel_dy (acumulado do mouse)
inventory.on_collected(kind)    # depois do pickup
inventory.hud_block()           # dict para o HUD
```

- Direção do mouse -> setor: ângulo do vetor acumulado `(wheel_dx, wheel_dy)` desde que a roda abriu, zona morta de
  ~0,06 rad acumulados. Soltar a tecla com um setor destacado e disponível chama `hands.equip(setor)`.
- A roda é desenhada em `screens.py`/`hud.py` com as primitivas do `Canvas` (retângulos, linhas, texto). Ícones
  simples feitos de formas: lanterna, pilha, chave, mapa dobrado, folha. Sons de interface em `audio` (abaixo).

### Portas e ranger (agente 5)

- `DoorManager.toggle` continua devolvendo `'opened' | 'closed' | 'slammed' | 'locked'`.
- Movimento: curva com aceleração e desaceleração, sem passos lineares; interromper no meio continua suave.
  Duração normal 0,9 a 1,4 s; batida mais rápida; fechar com trinco final.
- **Ranger:** cada porta tem `creak_chance`. Sorteio a cada abrir/fechar, com mais chance se o jogador está apressado,
  menos se está agachado ou se a porta foi aberta devagar. Se range, toca `door_creak_N` e emite ruído
  `door_creak` (nível em `C.NOISE_PLAYER`, alto o bastante para atravessar uma sala e baixo o bastante para
  não alertar a casa inteira). A entidade a até ~8 m (sem porta fechada no caminho) deve ir investigar; a 25 m, não.
- Teste obrigatório do comportamento da IA: `tests/test_doors.py` ou extensão de `tests/sim_ai.py`.

### Nomes de som combinados (agente 5 sintetiza, os outros usam já)

Quem usa pode chamar `game.sound(nome)` desde já; som ausente não derruba o jogo, mas o teste do catálogo cobra.

| Quem usa | Nomes |
|---|---|
| portas | `door_creak_1`..`door_creak_4`, `door_handle`, `door_latch`, `door_open_soft` |
| mãos/itens | `hand_reach`, `flash_pickup`, `flash_click_on`, `flash_click_off`, `flash_flicker_burst`, `key_pickup`, `battery_clack`, `map_fold`, `paper_pick` |
| corpo | `cloth_rustle_1`..`cloth_rustle_3` (roupa se mexendo, bem baixo) |
| interface | `ui_wheel_open`, `ui_wheel_tick`, `ui_wheel_close` |

Os sons que já existem (`flash_on`, `flash_off`, `key_jingle`, `battery_insert`, `map_unfold`, `paper_rustle`, `pickup`...)
seguem valendo; os novos podem substituí-los onde fizer sentido.

## Cutscenes (agente 4)

Objetivo é **fluidez e vida**: nada de câmera que desliza entre dois pontos parada diante de um cenário imóvel.

- Caminhos de câmera com mais de dois pontos (spline suave, velocidade contínua nas emendas), variação de lente
  e foco/respiração coerentes, corte de ação em vez de fade onde a cena pede.
- Objetos animados: portas, cortinas, o portão da garagem, o carro, luzes, o rádio, o relógio, a TV.
- O corpo do jogador aparece quando a câmera é a dos olhos dele (`host.show_body(True)`): mãos, antebraços, o
  levantar da cama, a chave girando na ignição, a mão no volante.
- A entidade usa a animação que já existe (`entity/motion.py`), com as poses extras que as cenas pedirem.
- Mantém o contrato: `CutscenePlayer`, `Overlay`, `host.finish(reason)`, ações `essential`, `skip()`.
- Verificar com quadros (`python -m sem_alvorada.cutscenes.preview`), fluidez em taxa de quadros alta (posição e
  rotação da câmera sem saltos: teste numérico de continuidade) e que pular continua funcionando.

## Processo e regras de convivência

- **Estilo:** o do projeto e das preferências do usuário: português, comentários só onde a razão não é óbvia, nomes específicos,
  funções pequenas, sem abstração de enfeite. Nada de emoji, nada de travessão como marca de estilo.
- **Testes são scripts com `assert`** (`python tests/arquivo.py`). Rode com `LIBGL_ALWAYS_SOFTWARE=1`.
  Antes de entregar, rode ao menos os do seu território e `tests/test_engine_core.py` e `tests/test_integration_build.py`.
- **CPU compartilhada.** São cinco agentes em quatro núcleos. Builds completos levam ~2 min: evite repeti-los; use
  `python -m sem_alvorada.build --stages ...`, `SA_ROOMS=` e capturas pequenas (640x360, 4 a 8 amostras). Capturas finais só no fim.
- **Saída temporária** em `out/f3_<seu_numero>/` (ignorada pelo git). **Não faça commit nem push**; o orquestrador faz.
- **Limite de uso da API:** se uma chamada falhar por limite, o orquestrador retoma você. Deixe o código sempre
  num estado em que `python tests/test_engine_core.py` passa; trabalho pela metade fica atrás de uma flag ou num módulo ainda não importado.
- **Compatibilidade:** o jogo precisa continuar rodando no Blender 4.2 LTS e 5.0.
- **Orçamento de triângulos da cena:** hoje 963 mil, teto 1,2 milhão (`conventions.BUDGET_TRIS`). Corpo ≤ 30 mil;
  itens na mão ≤ 6 mil no total; o resto é de quem já tinha.
- **Relatório final** (o orquestrador repassa ao usuário): o que mudou por arquivo, números (triângulos, tempos,
  testes), o que ficou de fora e por quê, problemas conhecidos, e duas ou três decisões de implementação explicadas em
  linguagem simples no formato problema -> solução -> motivo.
