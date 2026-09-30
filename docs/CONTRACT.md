# SEM ALVORADA: contrato técnico entre módulos

Jogo de terror psicológico em primeira pessoa, feito **inteiramente no Blender** (modelos, texturas,
áudio e lógica, tudo gerado por código Python). Visual e clima de **Cry of Fear**: escuro, sujo,
dessaturado, baixa resolução, lanterna como única fonte confiável de luz.

Leia este documento inteiro antes de escrever código. Ele é a fonte de verdade sobre nomes,
APIs e responsabilidades. Se algo aqui for ambíguo, escolha a interpretação mais simples e
registre a decisão no relatório final.

---

## 0. O jogo em um parágrafo

Domingo, 6:47, Harlan Ridge, Ohio. O sol deveria ter nascido às 6:12 e a janela continua preta.
Daniel Harper acorda sozinho numa casa americana de dois andares. Ele precisa juntar a **chave do
carro**, o **mapa da cidade** e **3 pilhas reserva** (há 5 espalhadas) para destrancar a porta que
leva à **garagem**, entrar no carro e fugir. Enquanto isso, **o Alto** (humanoide de 2,65 m, pele
cinza-cadavérica, olhos brancos brilhantes) anda pela casa. Ele **escuta** melhor do que enxerga:
o jogo gira em torno dos **níveis de som** do jogador, do ambiente e da entidade.
Texto do jogo, HUD e legendas: **português do Brasil**. Enredo e falas prontas em `sem_alvorada/story.py`.

## 1. Regras de ouro

1. **Nada externo.** Nenhum modelo, textura, som, fonte ou addon baixado. Tudo é criado por código
   com `bpy`, `bmesh`, `mathutils`, `numpy`, `aud`, `gpu`, `blf` e a biblioteca padrão.
2. **Blender 5.0.1 é o alvo de teste** (`pip` já instalou o módulo `bpy` neste contêiner). Deve continuar
   funcionando em 4.2 LTS+: use `sem_alvorada.compat` para o que mudou entre versões (EEVEE, Principled).
   Não use `bpy.ops` que dependam de UI/contexto de janela dentro dos *builders* (prefira `bmesh`/`from_pydata`).
3. **Builders são determinísticos** (use `ctx.rng`, nunca `random` global) e **idempotentes por etapa**.
4. **Texturas geradas** (numpy → `bpy.data.images.new` → `img.pixels.foreach_set` → `img.pack()`)
   precisam ser **empacotadas** ou somem ao salvar. Tamanho 64-256 px, `interpolation = 'Closest'`
   nos nós de imagem (visual GoldSrc/PS1).
5. **Orçamento** (roda em EEVEE ao vivo na viewport): geometria estática total < 150 k tris; cada prop
   ≤ 1,5 k tris (carro ≤ 6 k, entidade ≤ 8 k); ≤ 30 luzes na cena (o runtime liga só as vizinhas ao jogador);
   materiais compartilhados; nada de modificadores pesados (subsurf/boolean) deixados ativos.
6. **Cada agente escreve só na sua pasta** (seção 2). Precisa mudar arquivo alheio? Peça no relatório final.
   Não rode `git commit`/`git push`: o orquestrador faz isso.
7. **Estilo de código** (o dono do projeto lê e está aprendendo):
   - Código como um desenvolvedor sênior escreveria num projeto real, legível para quem está aprendendo.
   - Comentários **só** onde há razão, decisão ou comportamento não óbvio. Nada de "cria um cubo".
   - Nomes específicos do domínio. **Proibido**: `data`, `result`, `temp`, `helper`, `utils`, `example`, `stuff`, `obj1`.
   - Funções curtas, sem abstração por abstração. Sem padrões de projeto só porque existem.
   - Docstrings e comentários em português; identificadores em inglês (como o restante do pacote).
   - Sem emojis em código, logs ou texto do jogo.
8. **Teste o que construiu, com os olhos.** Renderize com `tools/preview.py` e **abra os PNG** (a ferramenta
   Read mostra imagens). Não declare pronto sem ter visto. Rode com `LIBGL_ALWAYS_SOFTWARE=1`.

## 2. Estrutura e donos

```
sem_alvorada/
  __init__.py conventions.py layout.py story.py compat.py buildctx.py matapi.py build.py   <- orquestrador (não edite)
  world/      (Agente 1) casa, texturas, materiais, luzes, exterior, pós-processamento
  props/      (Agente 2) móveis, itens, documentos, carro, viewmodel da lanterna, âncoras
  entity/     (Agente 3) o Alto: modelo, rig, animação procedural, texturas
  cutscenes/  (Agente 3) roteiro e player de cutscenes
  engine/     (Agente 4) jogador, lanterna, interação, portas, luzes, HUD, menus, operador modal, launcher
  audio/      (Agente 5) síntese de som (numpy), reprodução 3D (aud), sistema de ruído
  ai/         (Agente 5) cérebro da entidade: percepção, estados, navegação
tools/preview.py  tools/pngwrite.py            <- orquestrador
tests/test_<modulo>*.py                         <- cada agente cria os seus
docs/CONTRACT.md                                <- este arquivo
```

Comandos úteis (na raiz do repositório):

```
python -m sem_alvorada.layout                   # valida a planta e escreve out/planta_andar{0,1}.png
python -m sem_alvorada.build --stages world     # constrói só uma etapa (ver ordem em build.STAGES)
python -m sem_alvorada.build --stages world,props --out out/parcial.blend
python tools/preview.py --blend out/parcial.blend --view "sala:2.5,3,1.65,-90,0" --engine cycles --fill 0.1
```

Ordem de construção: `world → props → entity → cutscenes → ai → audio → engine`.
Cada pacote expõe `build(ctx)` em `__init__.py` (recebe `BuildContext`, ver `buildctx.py`).

## 3. Módulos compartilhados (já prontos, não edite)

- **`layout.py`**: planta. `ROOMS`, `OPENINGS`, `STAIRS`, `ANCHORS`, `ITEM_SPOTS`, `CEILING_LIGHTS`, `ROAD`,
  `SUN_RING`, `wall_pieces(level)` (paredes já recortadas por portas/janelas), `floor_rects`, `ceiling_rects`,
  `door_transform(op)`, `links()/neighbors()/room_path()` (grafo de cômodos), `room_at(x,y,z)`,
  `stairs_height(x,y)`, `solid_rects(level)` (colisão 2D de paredes), `reserved_zones(level)` (móveis não ocupam).
  **A geometria da casa DEVE derivar daqui.** Rode `python -m sem_alvorada.layout` e olhe o PNG.
- **`conventions.py`**: nomes de coleções/objetos, chaves de propriedades customizadas (`P_*`), constantes de
  jogabilidade (velocidades, lanterna, **tabelas de ruído**), paleta e lista de materiais canônicos.
- **`matapi.py`**: `get_material(nome)` e `assign(obj, nome)`. Devolve um material válido sempre (cai num liso da
  paleta se `world.materials` ainda não tem o nome).
- **`compat.py`**: `eevee_id()`, `use_eevee()`, `new_material()`, `bsdf_of()`, `set_bsdf()`.
- **`story.py`**: todo o texto do jogo (notas, prompts, legendas de cutscene).

Coordenadas: metros, Z para cima, rua ao sul (y=0), fundos ao norte (y=10). **Yaw** = `rotation_euler.z`:
`yaw=0` olha para +Y; `-90°` olha para +X; direção = `(-sin(yaw), cos(yaw))` (`conventions.yaw_dir`).
Piso do andar 0: z=0. Piso do andar 1: z=2.8. Pé-direito 2,6 m.

## 4. Convenções da cena `.blend`

**Coleções**: `SA_World`, `SA_Props`, `SA_Items`, `SA_Entity`, `SA_Cutscene`, `SA_Player`, `SA_Collision`
(use `ctx.link(obj, conventions.COL_PROPS)` etc.).

**Origem e frente de peças**: móveis têm a origem no **centro da base** (contato com o piso) e a **frente
é +Y local**, então `rotation_euler.z = yaw` de `layout.ANCHORS`. Itens: origem no centro visual do objeto.

**Colisão**: um objeto colide se tiver `obj["sa_col"] = 1`. Paredes/pisos/escada do `world` recebem isso.
Móveis e carro colidem por **proxies em caixa** `COL_<nome>` (cubo de 8 vértices, só yaw, sem pitch/roll,
`hide_render=True`, `hide_viewport=True`, coleção `SA_Collision`, `sa_col=1`). Detalhes finos não colidem.
Portas **não** entram na colisão estática (o runtime trata a folha como segmento pelo ângulo).

**Portas** (dono: world): para cada `Opening` com `kind == 'door'`:
- Empty pivô `Door_<id>` na dobradiça (`layout.door_transform(op)["hinge"]`), `rotation_euler.z = closed_yaw`.
- Propriedades: `sa_id=<id>`, `sa_interact='door'`, `sa_closed_yaw`, `sa_open_yaw`, `sa_lock` (o `lock` do Opening).
- Filhos: `DoorLeaf_<id>` (mesh modelado em **+X local** a partir do pivô, largura `b-a-0.02`, altura `DOOR_H`, espessura ~0.04 centrada em Y=0), `DoorHandle_<id>`.
- Batente `DoorFrame_<id>` faz parte do mundo. Arcos não têm porta.
**Janelas**: `Window_<id>` com moldura e cortinas (sem vidro refletivo); `sa_interact='look'`, `sa_prompt="[E] Olhar"`.
**Portão da garagem**: `GarageRollup` (Empty na `layout.OPENINGS['garage_rollup']`, z=0) com painéis como filhos;
`sa_open_lift=2.3` (m). Abrir = subir `location.z` até `sa_open_lift`.

**Luzes** (dono: world = teto; props = abajures/TV/etc.): nome `Light_<room>_c<n>` (teto) ou `Light_<room>_p<n>`
(peças). Propriedades: `sa_room`, `sa_base_energy` (W), `sa_flicker` (0..1), `sa_kind`. Sombras **desligadas**
nas luzes de ambiente (só a lanterna projeta sombra). Luzes de teto também têm um `Fixture_<room>_c<n>` (mesh emissivo).

**Itens e documentos** (dono: props): `Item_FLASHLIGHT`, `Item_KEY`, `Item_MAP`, `Item_BATTERY_1..5`,
`Item_NOTE_1..7` na coleção `SA_Items`. Propriedades: `sa_interact` (`'item'` ou `'note'`), `sa_item`
(`FLASHLIGHT|KEY|MAP|BATTERY|NOTE`), `sa_id` (igual ao sufixo, ex. `BATTERY_3`), `sa_prompt`, `sa_room`.
Posição: perto de `layout.ITEM_SPOTS[id]` **sobre o móvel indicado** (o objeto é a verdade, o runtime lê dele).
Todos visíveis à lanterna: precisam de material claro/legível no escuro (a chave brilha, o mapa é papel claro).
**Âncoras**: para cada nome em `layout.ANCHORS` o módulo props cria o móvel indicado **exatamente** ali e um
Empty `Anchor_<nome>` (mesma posição/yaw).
**Carro**: `Car` (Empty raiz na âncora `car`) com carroceria, rodas (`Car_Wheel_FL/FR/RL/RR`), interior visível do banco do
motorista (volante, painel, retrovisor, relógio do painel 6:12 emissivo), faróis `Car_Headlight_L/R` (SPOT, **desligados**),
`Car_DriverEye` (Empty na âncora `car_driver_eye`), `Car_Interact` (na âncora `car_interact`, `sa_interact='car'`,
`sa_prompt="[E] Entrar no carro"`). O runtime/cutscene move o `Car` inteiro.
**Viewmodel**: `ViewModel_Flashlight` (lanterna na mão, origem no punho, cano apontando para **-Z local**, oculto na cena, o engine pendura na câmera).

**Jogador** (dono: engine): `PlayerCam` (câmera, `lens` para FOV 72°), `Flashlight` (SPOT filho da câmera,
sombras ligadas), coleção `SA_Player`.
**Entidade** (dono: entity): Empty raiz `Entity` (**pés na origem, frente = +Y local**) na coleção `SA_Entity`; filhos:
armadura `Entity_Rig`, malha `Entity_Body`, `Entity_Eyes` (emissivo branco), luz `Entity_EyeLight` (POINT branco fraco).
**Cutscene**: câmera `CutsceneCam` (dono: cutscenes).

## 5. APIs por módulo

Tudo em Python simples, com *duck typing*. Onde um módulo depende de outro, **programe contra esta seção** e teste
com um *fake* seu; não espere o outro terminar.

### 5.1 `world` (Agente 1)
- `world.build(ctx)`: cria `SA_World` completo: pisos, lajes (`layout.floor_rects`), forros, paredes (`layout.wall_pieces`),
  batentes, portas (4), janelas, escada (`Stairs_Main` + corrimão), telhado (`ROOF`), garagem (portão), **exterior**
  (rua `layout.ROAD`, calçada, gramado, entrada de carros, casas vizinhas apagadas em silhueta, árvores secas,
  poste morto, caixa de correio), **o Sol Negro** (`layout.SUN_RING`: disco preto com coroa fina emissiva no
  horizonte nordeste), luzes de teto, `World` (céu quase preto, neblina), pós-processamento.
- `world.materials.build_material(name) -> Material` para **todos** os nomes de `conventions.MATERIAL_NAMES`
  (papel de parede sujo, madeira, carpete, azulejo, concreto, telhas, ...). Texturas procedurais em numpy,
  64-256 px, `Closest`. Usar `compat` para o Principled. Cache por nome.
- `world.texgen`: funções de textura reutilizáveis (ruído, manchas, veios de madeira, padrões).
- `world.quality.apply(scene, level)` com `'low'|'medium'|'high'`: configura EEVEE (sombras, raytracing, AO, bloom,
  volumétrico, amostras) e o compositor/tela (vinheta, granulação, dessaturação). O launcher chama isso.
- `world.lighting.apply_power(scene, on: bool)` (opcional): liga/desliga em bloco as luzes `Light_*` de ambiente.
  O runtime também controla luzes individualmente por `sa_room`, `sa_base_energy`, `sa_flicker`.
- Pós-processamento estilo Cry of Fear: dessaturação, contraste, vinheta, granulação, leve aberração. Tente o
  compositor em tempo real (no 5.0 é `scene.compositing_node_group`; no 4.x `scene.node_tree` com `use_nodes`) e
  `space.shading.use_compositor='ALWAYS'`. Se algum nó não existir na versão, degrade sem quebrar o build.
- **Escuridão de verdade**: luz ambiente do mundo ≈ 0.002; a casa começa com luzes de teto amareladas e fracas.

### 5.2 `props` (Agente 2)
- `props.build(ctx)`: mobília por cômodo (respeitando `layout.reserved_zones`), decoração, bagunça, itens,
  notas, carro, viewmodel, âncoras, proxies `COL_*`, luzes de peças. Cada cômodo com personalidade
  (quarto da menina intocado, escritório com cortiça de recortes, cozinha com pratos por lavar...). Manchas/sangue
  discretos, fotos de família, o relógio de pé parado às 6:12, o despertador marcando 6:47.
- `props.textures` (interno): mapa da cidade (ruas em grade, rio, "Rota 33" riscada), fotos, chiado de TV, papel.
- Cada prop é uma função `make_<coisa>(ctx, x, y, z, yaw, ...) -> Object` com malha low-poly via `bmesh`.
- Documentos (`Item_NOTE_n`) são papéis/objetos legíveis no chão de sombra; o texto vem de `story.NOTES`.

### 5.3 `entity` (Agente 3)
- `entity.build(ctx)`: cria a entidade (ver 4). Alta (`ENTITY_HEIGHT` 2,65 m), humanoide **errada**: membros longos
  demais, tronco fino, pescoço comprido, cabeça pequena e ligeiramente inclinada, sem boca ou nariz, dedos longos,
  roupa rasgada escura, pele cinza pálida, **olhos brancos brilhantes**. Estilo low-poly GoldSrc, 1 osso por vértice
  ou peças rígidas em ossos. ≤ 8 k tris. Esqueleto com ossos de: quadril, coluna x3, pescoço, cabeça, ombros, braços,
  antebraços, mãos, coxas, canelas, pés.
- `entity.rig.EntityRig(scene)` (runtime, sem UI):
  - `set_transform(x, y, z, yaw)`
  - `set_anim(name)` com `name in ('idle','stalk','walk','run','attack','stare','twitch','appear')`
  - `update(dt, speed)`: avança animação **procedural** (senos + ruído, sem depender de `scene.frame_set`); `speed` em m/s
    ajusta a cadência da passada.
  - `look_at(x, y, z)`: cabeça segue um ponto (limitada). `set_visible(bool)`.
  - `eyes(level: float)`: brilho dos olhos (0..1; 1 = branco intenso, emissão alta + `Entity_EyeLight`).
  - `head_position() -> (x,y,z)`; propriedade `visible`.
  - `pose_for_death(player_eye_pos)`: pose de agarrar (usada na cutscene de morte).
- Texturas próprias (pele, roupa) dentro do pacote `entity`, materiais `entity_skin`, `entity_cloth`, `entity_eye`.

### 5.4 `cutscenes` (Agente 3)
Player de cutscenes **puramente lógico**: atualiza a câmera e chama o "anfitrião" (*host*, implementado pelo engine).
- `cutscenes.CutscenePlayer(host)` com: `play(name, on_done=None)`, `update(dt)`, `active -> bool`, `skip()`,
  `overlay() -> Overlay` (dataclass: `fade` 0..1 preto, `letterbox` 0..1, `subtitle: str`, `subtitle_alpha`,
  `card: (titulo, subtitulo) | None`, `flash` 0..1 branco, `shake` 0..1). O HUD do engine desenha o overlay.
- Nomes: `'intro'`, `'blackout'`, `'garage_unlock'`, `'death'`, `'ending'` (textos em `story.CUTSCENE_TEXT`).
  - **intro**: escuro → despertador 6:47 (âncora `nightstand_clock`) → câmera da cama → janela norte do quarto mostrando o
    Sol Negro → rádio chiando → levanta. Termina posicionando o jogador em `layout.PLAYER_START`.
  - **blackout**: ao sair do quarto o corredor perde a luz (piscadas, tunk), a entidade aparece parada no fundo
    (`layout.ENTITY_FIRST_SIGHT`), olhos acendem, a cabeça gira; corta de volta ao jogo e ativa a caça.
  - **garage_unlock**: closes da fechadura, clique, porta abre, estrondo lá em cima, cabeça vira.
  - **death**: a entidade agarra (posição do jogador), rosto gigante, olhos brancos, corte seco para o preto.
  - **ending**: entra no carro, chave, `GarageRollup` sobe, o carro sai pela entrada até a rua, faróis acendem e a
    entidade está parada no meio da estrada (`layout.ENTITY_ROAD_POS`), flash branco, corte para o relógio 6:12 no
    quarto com a janela um pouco mais clara, `story.ENDING_CARD`.
- Cada plano ("shot"): duração, câmera A→B (posição/alvo/FOV, curva ease), efeitos (legenda, som, luz, tremor, fade),
  ações no host. Dados em `cutscenes/scripts.py`, interpolação em `cutscenes/player.py`. Posições devem vir de
  `layout.ANCHORS`/`layout.*`, nunca números soltos que percam sincronia com a casa.
- **Host** (Protocol que o engine implementa; você programa contra ele e testa com um fake):
  `host.scene`; `host.set_camera(obj|None)` (None restaura a câmera do jogador); `host.audio.play(name, pos=None, volume=1, pitch=1)`;
  `host.entity` (EntityRig); `host.set_power(on: bool, flicker: float = 0)`; `host.flash_light(seconds)`;
  `host.set_flashlight(on: bool)`; `host.doors.set_openness(door_id, f)` e `host.doors.snap(door_id, f)`;
  `host.place_player(x, y, z, yaw)`; `host.player_state() -> (x, y, z, yaw, eye_z)`;
  `host.get_object(name)`; `host.noise_silence(seconds)`; `host.entity_brain_activate()`;
  `host.finish(reason)` (`'intro_done'|'blackout_done'|'unlock_done'|'death_done'|'ending_done'`).

### 5.5 `engine` (Agente 4)
Núcleo **sem UI** + camada fina de UI. O núcleo roda headless em testes.
- `engine.build(ctx)`: cria `PlayerCam`, `Flashlight` (SPOT filho da câmera, sombras, `spot_size` 48°, `spot_blend` ~0.25,
  energia de `conventions.FLASH_ENERGY`), pendura `ViewModel_Flashlight`, coleção `SA_Player`, texto de instruções
  no .blend (`Text` datablock `LEIA-ME`), e configurações de cena para jogar.
- `engine.game.Game(scene, quality='medium', audio=True)`: dono de todo o runtime.
  `tick(dt, inp: InputState)`, `state: GameState`, `new_game()`, `restart_from_checkpoint()`, `hud_model() -> dict`.
  `InputState`: `move_x, move_y` (-1..1), `look_dx, look_dy` (radianos), `run, crouch`, e *edges* de um quadro:
  `interact, flashlight, reload, pause, confirm, skip, cancel`.
- Subsistemas (arquivos livres, mas com estes papéis): `player` (movimento, colisão, escada, stamina, agachar, *head bob*,
  passos com ruído por piso), `flashlight` (bateria, tremida, pisca, troca de pilha), `doors` (`DoorManager`: abrir/fechar,
  trancas, segmento de colisão por ângulo, `openness(id)`, `set_openness`, `snap`), `interact` (seleção do interagível
  mais centralizado ≤ `INTERACT_RANGE` com linha de visada), `lights` (energia por `sa_room` só nos cômodos próximos,
  apagão, pisca), `director` (gatilhos de história), `hud` (desenho `gpu`/`blf`), `operator` (`sa.play`, modal),
  `launcher.start()`.
- **Colisão** via `mathutils.bvhtree.BVHTree` dos objetos com `sa_col`, círculo do jogador de `PLAYER_RADIUS`, deslizando
  nas paredes, degrau até `PLAYER_STEP_HEIGHT`, altura do piso por raio para baixo (escada funciona). Portas fechadas
  bloqueiam. Deve ter fallback em `layout.solid_rects` para testes sem malhas.
- **Fluxo do jogo**: título → `intro` → jogo → pegar lanterna → sair do quarto (entrar em `hall_u`) → `blackout` → caça
  → coletar tudo (`conventions.GATE_REQUIRES`, pilhas contam **encontradas**) → destrancar `Door_garage_door` (interagir
  com tudo em mãos) → `garage_unlock` → entrar na garagem → interagir com o carro → `ending`. Morte → `death` → tela de
  fim de jogo → tentar de novo a partir do último *checkpoint* (a cada item/nota). Objetivo na tela (`story.OBJ_*`).
- **HUD** (cantos discretos, tipografia pequena, cor de papel envelhecido): bateria da lanterna (barrinhas) e pilhas
  reserva; lista de coleta (chave, mapa, pilhas x/3); dica de interação; mensagens curtas; **medidor de som**
  (ver 6) sempre visível; overlay de cutscene (letterbox, legenda, fade, cartão); leitor de notas (pausa o mundo);
  título, pausa, fim de jogo, créditos.
- **Operador modal**: captura mouse (`window.cursor_warp` + `cursor_modal_set('NONE')`), timer 1/60, WASD/Shift/C/F/R/E/Esc,
  esconde UI do Blender (área 3D maximizada, `overlay` desligado, câmera `PlayerCam`, sombreamento `RENDERED`,
  `use_compositor='ALWAYS'`), restaura tudo ao sair. Deve ser iniciável por `blender SemAlvorada.blend --python play.py`
  e também ao abrir o .blend e rodar o texto `LEIA-ME`/`jogar` no editor de texto.
- `play.py` (raiz): launcher. Aceita `-- --quality low|medium|high --skip-intro --debug`.
- **Testes sem GUI**: `tests/test_engine_*.py` e `tests/sim_playthrough.py` simulam uma partida completa por
  `Game.tick` com entradas roteirizadas (pegar tudo e chegar ao carro com a entidade desativada; depois com ela ligada
  para checar que o cérebro persegue e mata).

### 5.6 `audio` (Agente 5)
- `audio.synth`: gera **todos** os WAV (numpy, mono 16-bit, 44,1 kHz ou 22,05 kHz nos loops longos) em
  `assets/audio/` (`python -m sem_alvorada.audio.synth`). Total < 20 MB. Sem samples externos: ruído filtrado,
  osciladores, envelopes, formantes, convolução simples de reverb.
- `audio.build(ctx)` regenera os WAV se faltarem e empacota a lista em um `Text` datablock `SA_AUDIO_MANIFEST`.
- **Catálogo mínimo de sons** (nomes de arquivo sem `.wav`; outros módulos vão pedir por estes nomes):
  - passos: `step_wood_1..4`, `step_carpet_1..4`, `step_tile_1..4`, `step_concrete_1..4`, `step_stairs_1..4`
  - portas: `door_open`, `door_close`, `door_slam`, `door_locked`, `door_unlock`, `door_creak_long`
  - itens: `pickup`, `battery_pickup`, `battery_insert`, `paper_rustle`, `key_jingle`, `map_unfold`
  - lanterna: `flash_on`, `flash_off`, `flash_flicker`
  - corpo: `breath_calm` (loop), `breath_heavy` (loop), `heartbeat` (loop), `gasp`
  - ambientes (loops): `amb_house`, `amb_fridge`, `amb_clock_tick`, `amb_wind`, `amb_tv_static`, `amb_garage_hum`, `amb_music_box`, `amb_radio_static`
  - eventos: `creak_1..3`, `thud_1..2`, `phone_ring`, `glass_break`, `clock_chime`
  - entidade: `ent_drone` (loop grave), `ent_breath` (loop), `ent_step_1..4` (pesados), `ent_step_stalk_1..2` (macios),
    `ent_growl`, `ent_scream`, `ent_whisper`, `ent_door_break`, `ent_stinger`, `ent_static_burst`
  - cutscene: `blackout_thunk`, `power_hum` (loop), `car_start`, `car_idle` (loop), `car_door`, `garage_rollup`, `alarm_beep`, `death_hit`
- `audio.engine.AudioEngine(audio_dir=AUDIO_DIR, enabled=True)` sobre o módulo `aud` do Blender (funciona headless; sem
  dispositivo de áudio ele vira *no-op* silencioso e loga uma vez):
  `update_listener(pos, yaw)`, `play(name, pos=None, volume=1.0, pitch=1.0) -> handle|None`,
  `loop(key, name, pos=None, volume=1.0, pitch=1.0)` (cria/atualiza um loop persistente), `stop(key)`,
  `footstep(surface, intensity, pos=None)` (sorteia variação, evita repetir), `set_master(v)`, `shutdown()`.
  Som 3D de verdade (`Handle.location`, atenuação por distância, `relative`) e **oclusão**: sons de outro cômodo com
  porta fechada saem abafados (versão filtrada `lowpass` do som ou queda de volume).

### 5.7 `audio.noise` (Agente 5): sistema de ruído (o foco do jogo)
`NoiseSystem(door_openness=callable)` (`door_openness(door_id) -> 0..1`, padrão: tudo fechado):
- `emit(source, kind, pos, loudness, ttl=1.5)`: `source in ('player','entity','ambient')`; `kind` é chave de
  `conventions.NOISE_PLAYER/NOISE_ENTITY/NOISE_AMBIENT_EVENTS`; `loudness` 0..1 na fonte (o chamador já aplica o
  multiplicador de piso).
- `update(dt)`: envelhece e descarta eventos.
- `level_at(pos, source=None) -> float`: quanto um ouvinte em `pos` percebe agora (0..1), somando/limitando eventos
  ativos após propagação e **mascaramento**.
- `heard_by_entity(pos) -> list[HeardEvent]`: eventos do jogador/ambiente que a entidade em `pos` consegue ouvir
  (loudness efetiva ≥ `HEAR_THRESHOLD`≈0.08), com `pos_source`, `loudness`, `kind`, `age`.
- `ambient_level(room_id) -> float`: base `layout.ROOMS[..].ambient` + eventos ambientais ativos.
- `hud_levels() -> dict(player=, ambient=, entity=)` suavizado (subida rápida, queda lenta) para o medidor.
**Regras de propagação** (números em `conventions.NOISE_*`): a energia viaja pelo **grafo de cômodos**
(`layout.links()`), não pela distância euclidiana pura: `efetivo = fonte * (1 - NOISE_DECAY_PER_M*comprimento_do_caminho)`;
cada **porta fechada** no caminho subtrai `NOISE_DOOR_CLOSED_LOSS` (aberta: 0; arco: 0), mudar de andar subtrai
`NOISE_FLOOR_LOSS`. Mesmo cômodo: só distância. **Mascaramento**: `efetivo -= NOISE_MASK_FACTOR * ambient_level(sala do ouvinte)`.
Isso cria as decisões do jogo: agachar/tapete/abafar com portas; a cozinha (geladeira 0.22) "esconde" você; correr no
tile ecoa pela casa; bater porta chama a entidade.

### 5.8 `ai` (Agente 5)
- `ai.build(ctx)`: **assa a malha de navegação** (grade 0,25 m por andar, obstáculos = `layout.solid_rects` + proxies `COL_*`
  + escada como conector) num `Text` datablock `SA_NAV` (JSON), para o runtime carregar rápido e os testes não
  dependerem de BVH.
- `ai.brain.EntityBrain(world_view, noise, rng, nav=None)` (nav é carregado de `SA_NAV`, ou construído da planta):
  - Estados de `conventions.ENTITY_STATES`: `dormant, patrol, investigate, stalk, chase, search, attack`.
  - `activate(pos)`, `set_aggression(level: 0|1|2)`, `update(dt, senses) -> BrainOutput`.
  - `senses` (dataclass do engine): `player_pos, player_yaw, player_level, player_speed, player_crouching,
    flashlight_on, flashlight_dir`.
  - `BrainOutput`: `x, y, z, yaw, speed, state, anim` (`'idle'|'stalk'|'walk'|'run'|'attack'|'stare'`), `look_target|None`,
    `kill: bool`, `drone: float` (0..1, volume do zumbido; **0 durante `stalk`**: o silêncio avisa).
  - **World view** (o engine implementa): `line_of_sight(a, b) -> bool`, `door_openness(id)`, `open_door(id, by)`,
    `is_locked(id)`, `room_at(x, y, z)`.
  - **Audição**: consulta `noise.heard_by_entity`; som acima do limiar leva a `investigate` (alvo = origem do som com erro
    inversamente proporcional ao volume); som forte ou repetido leva a `chase`.
  - **Visão**: cone de ~110°, linha de visada livre, alcance `FLASH_RANGE_VISION` se a lanterna estiver ligada e apontando
    para ele, `DARK_VISION_RANGE` no escuro; agachado/parado reduz. A "consciência" **sobe aos poucos** (0..1); ≥ 0.6 vira `chase`.
  - `stalk`: quando o jogador está próximo e quieto, ele se aproxima devagar e **em silêncio** (drone 0, passos macios).
  - `chase`: persegue o último ponto conhecido (`ENTITY_SPEED_CHASE`), abre portas no caminho, sobe escadas; perdeu o
    jogador por > 4 s → `search` (8 s vasculhando) → `patrol`.
  - `attack`/`kill` quando `distance < ENTITY_KILL_DISTANCE` com linha de visada.
  - A entidade nunca sai da casa; a porta da garagem trancada não a deixa passar até destrancar; a agressividade sobe
    quando o engine muda o nível (`set_aggression`).
  - Tudo determinístico com `rng`. Sem atalhos: usa a mesma malha de navegação e as mesmas portas que o jogador.

## 6. Som e ruído: o desenho de jogo (para todos)

Três fontes, três níveis, sempre visíveis ao jogador no **medidor de som** (3 barras, canto inferior esquerdo):
`VOCÊ` (o que seu corpo emite agora), `AMBIENTE` (ruído de fundo do cômodo, que te esconde), `ENTIDADE` (o que você
ouve dela). O que cada um faz:

| Ação do jogador | Ruído (0..1) | Observação |
|---|---|---|
| parado | 0.00 | respiração só se sem fôlego (0.06) |
| agachado andando | 0.08 | lento (1.2 m/s) |
| andando | 0.30 | × piso: carpete 0.55, madeira 1.0, azulejo 1.15, escada 1.35 |
| correndo | 0.75 | gasta fôlego; 4.6 m/s |
| abrir/fechar porta | 0.30 / 0.35 | bater (fechar correndo): 0.90 |
| pegar item, clicar lanterna, trocar pilha | 0.15 / 0.10 / 0.18 | |
| degrau que range | 0.55 | aleatório na escada |

Ambiente: base por cômodo em `layout.ROOMS[..].ambient` (cozinha 0.22 por causa da geladeira; garagem 0.12; quartos ~0.02) +
eventos pontuais (`NOISE_AMBIENT_EVENTS`: rangido, baque, telefone, chiado da TV, relógio) que **também atraem a
entidade** (distração que o jogador pode aproveitar) e podem **mascarar**.
Entidade: zumbido grave contínuo `drone` que cresce com a proximidade e **some quando ela espreita** (o silêncio é o alerta),
passos pesados na perseguição (0.85), suaves ao espreitar (0.10), respiração, rosnado ao avistar, grito ao matar.
Ela também reage a **luz**: a lanterna acesa a denuncia de longe (18 m) mas é a única forma de ver.

## 7. Fluxo de dados por quadro (engine é o maestro)

```
Operator (eventos) -> InputState -> Game.tick(dt, inp)
   1. cutscene ativa? CutscenePlayer.update(dt); só desenha overlay; retorna.
   2. Player.update: movimento, colisão, stamina; gera passos -> Game.make_noise('player', kind, pos, loud*piso, sound)
   3. Flashlight.update (bateria), DoorManager.update, LightManager.update
   4. NoiseSystem.update(dt)
   5. EntityBrain.update(dt, senses) -> BrainOutput -> EntityRig.set_transform/set_anim/update/look_at
   6. AudioEngine: listener, loops (drone da entidade conforme BrainOutput.drone, ambiente do cômodo, batimentos por perigo)
   7. Interact: seleção + ação; Director: gatilhos (pickup, entrar em cômodo, itens completos)
   8. HUD lê Game.hud_model() (inclui noise.hud_levels()).
```
`Game.make_noise(kind, pos, loudness, sound=None, source='player')` toca o som (via `audio.play`) **e** registra o ruído
(via `noise.emit`): as duas coisas nunca ficam dessincronizadas.

## 8. Ferramentas e testes

- `tools/preview.py`: render headless (workbench/cycles/eevee) a partir de câmeras `nome:x,y,z,yaw,pitch`.
  Cycles é o melhor para conferir materiais em ~10 s; para paredes/proporções basta `--engine workbench --fill 1`.
  Use `--hide "Roof*"` para ver dentro da casa de cima. **Olhe as imagens.**
- Testes são scripts Python simples com `assert` e `main()` (rodam com `python tests/test_x.py` e com pytest).
  Prefixe com o módulo: `tests/test_world_*.py`, `test_props_*.py`, `test_entity_*.py`, `test_cutscenes_*.py`,
  `test_engine_*.py`, `test_audio_*.py`, `test_ai_*.py`.
- Sempre exporte `LIBGL_ALWAYS_SOFTWARE=1`. Renders de EEVEE em software levam dezenas de segundos: prefira Cycles/Workbench
  para iterar e use EEVEE só para a checagem final de uma ou duas vistas.
- Não deixe arquivos grandes em `out/` fora do `.gitignore` (já ignorado). Use `out/` para renders e `.blend` parciais.

## 9. Relatório final de cada agente (curto, em português)

1. O que ficou pronto (arquivos e APIs públicas, com assinaturas).
2. O que testou e como (comandos), com resultado; o que **não** conseguiu validar.
3. Desvios do contrato e pedidos para outros módulos.
4. Problemas conhecidos.
5. **Duas ou três decisões de projeto que valem explicar a quem está aprendendo**, no formato *problema → solução → motivo*
   (por que foi feito assim e o que aconteceria na versão ingênua).
