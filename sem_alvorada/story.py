"""Texto e narrativa (pt-BR). Sem dependência de bpy.

Premissa: Harlan Ridge, Ohio, um domingo. O despertador marca 6:47, mas o sol
deveria ter nascido às 6:12. Daniel Harper (41) está sozinho em casa. Há três semanas a
filha, Emma (7), morreu num acidente na Rota 33, ao amanhecer, com o sol nos olhos dele.
Laura, a esposa, foi para a casa da irmã em Dayton. O sol que não nasce, o rádio que repete
"seis e doze" e o homem alto de olhos brancos são o mesmo peso: a manhã do acidente.

Mecânica em fala: o Alto não enxerga bem, ele ESCUTA. O que faz barulho, ele encontra.
"""

TITLE = "SEM ALVORADA"
SUBTITLE = "Harlan Ridge, Ohio. Domingo, 6:47."

# --------------------------------------------------------------------------
# Objetivos (só aparecem no menu de pausa)
# --------------------------------------------------------------------------
OBJ_TAKE_FLASHLIGHT = "Pegar a lanterna no criado-mudo."
OBJ_LEAVE_ROOM = "Sair do quarto."
OBJ_COLLECT = "Achar a chave do carro, o mapa da cidade e 3 pilhas reserva."
OBJ_GARAGE = "Destrancar a porta da garagem (cozinha)."
OBJ_CAR = "Entrar no carro."

# Rótulos da lista de coleta
LABEL_KEY = "Chave do carro"
LABEL_MAP = "Mapa da cidade"
LABEL_BATTERIES = "Pilhas reserva"

# --------------------------------------------------------------------------
# Dicas de interação
# --------------------------------------------------------------------------
PROMPT_PICKUP = "[E] Pegar"
PROMPT_READ = "[E] Ler"
PROMPT_OPEN = "[E] Abrir"
PROMPT_CLOSE = "[E] Fechar"
PROMPT_CAR = "[E] Entrar no carro"
PROMPT_UNLOCK_GARAGE = "[E] Destrancar"

ITEM_PROMPTS = {
    "FLASHLIGHT": "[E] Pegar a lanterna",
    "KEY": "[E] Pegar a chave do carro",
    "MAP": "[E] Pegar o mapa da cidade",
    "BATTERY": "[E] Pegar pilhas",
    "NOTE": "[E] Ler",
}

# Estados que o personagem NÃO fala: aparecem como dica de interação, sem o [E] quando não há o que fazer.
PROMPT_LOCKED = {"front": "Trancada por fora", "back": "Trancada", "garage": "Trancada"}
PROMPT_LOCKED_DEFAULT = "Trancada"
PROMPT_CAR_LOCKED = "Trancado"
PROMPT_LOOK = "Lá fora só existe o preto"

# Falas do personagem: só estas e as de PICKED/COLLECT_DONE (a regra está em docs/FASE3.md).
OPENING_LINE = "Sem sol, de novo. Preciso de luz. A lanterna, no criado-mudo."
PICKED = {
    "FLASHLIGHT": "A lanterna. A pilha já não é nova.",
    "KEY": "A chave do carro. O chaveiro ainda tem o coelhinho dela.",
    "MAP": "O mapa da cidade. Uma estrada que não seja a Rota 33.",
    "BATTERY": "Pilhas reserva.",
}
COLLECT_DONE = "Tenho tudo. Agora a garagem."

# --------------------------------------------------------------------------
# Documentos (NOTE_1..NOTE_7). Título curto + corpo (quebre em linhas de ~46 colunas).
# --------------------------------------------------------------------------
NOTES = {
    "NOTE_1": ("Bilhete da Laura",
               "Dan,\n\nfui para a casa da Karen, em Dayton.\n"
               "Não consigo mais acordar do seu lado e te\nver na janela, esperando o sol.\n\n"
               "Come alguma coisa. Toma o remédio.\nLiga quando conseguir dizer o nome dela.\n\n"
               "L."),
    "NOTE_2": ("Desenho da Emma",
               "Giz de cera. A nossa casa, um sol amarelo\nenorme e, ao lado, um homem muito alto,\n"
               "todo preto, com dois círculos brancos\nno lugar dos olhos.\n\n"
               "Embaixo, com letra torta:\n\"o moço alto não gosta de barulho.\nele só vem quando a gente esquece\nde ficar quietinha.\"\n\n"
               "A data é de agosto. Antes de tudo."),
    "NOTE_3": ("Recorte de jornal",
               "HARLAN RIDGE GAZETTE, edição de terça\n\nMENINA DE 7 ANOS MORRE NA ROTA 33\n\n"
               "O acidente ocorreu às 6h12, com o sol\nbaixo no horizonte. O motorista, Daniel H.,\n41, disse à polícia:\n"
               "\"O sol estava nos meus olhos.\nEu não vi nada. Eu não vi nada.\""),
    "NOTE_4": ("Anotações do Dan",
               "Dia 19. O sol não nasceu de novo.\nO rádio só repete: seis e doze.\n\n"
               "Ele só se mexe quando eu faço barulho.\nSe eu ficar parado, ele passa reto.\n"
               "A luz da lanterna ele vê de longe.\n\n"
               "Preciso da chave e do mapa. Pela Rota 33\nnão dá. Nunca mais."),
    "NOTE_5": ("Bilhete na geladeira",
               "Sertralina 50 mg. Tomar de manhã.\n(De manhã?)\n\n"
               "Guardei pilhas em vários cantos da casa.\nA luz vive caindo e você nunca lembra\nonde deixou as coisas.\n\n"
               "Come alguma coisa. -L."),
    "NOTE_6": ("Receita do Dr. Mills",
               "Sessão 4.\n\n\"A manhã não veio porque o senhor não\nestá deixando. A escuridão é o único\nlugar onde ainda consegue vê-la.\"\n\n"
               "Tarefa: sair de casa. Dirigir até o\namanhecer. Não parar."),
    "NOTE_7": ("Guia do reboque",
               "PÁTIO MUNICIPAL - LIBERAÇÃO DE VEÍCULO\nTitular: Daniel Harper\nDanos: frente, lado do passageiro.\n\n"
               "Retirado há duas semanas.\n\nNa garagem desde então.\nNunca foi ligado."),
}

# --------------------------------------------------------------------------
# Falas de cutscene (tempo = ordem; A3 distribui a duração). Voz interior do Dan.
# --------------------------------------------------------------------------
CUTSCENE_TEXT = {
    "intro": [
        "6:47.",
        "O sol devia ter nascido às 6:12.",
        "Trinta e cinco minutos. A janela continua preta.",
        "Como ontem. Como anteontem.",
        "(rádio) ...seis e doze... seis e doze... seis e doze...",
        "Preciso sair daqui. Chave. Mapa. Luz.",
    ],
    "blackout": [
        "A luz...",
        "Não. Não faz barulho.",
        "Ele está parado lá no fim do corredor. Não se mexe.",
        "Se eu ficar quieto, ele passa. Se eu ficar quieto...",
    ],
    "garage_unlock": [
        "Abriu.",
        "(um estrondo no andar de cima)",
        "Ele ouviu.",
    ],
    "death": [
        "",
    ],
    "ending": [
        "A chave gira. O motor pega de primeira.",
        "Rota 33. Eu devia ter parado de dirigir naquela manhã.",
        "Eu vejo você. Eu vejo. Desculpa, Emma.",
        "...",
        "6:12.",
    ],
}
ENDING_CARD = ("Ainda não amanheceu.",
               "Mas a janela está um pouco mais clara do que da última vez.")

DEATH_CARD = "VOCÊ NÃO FICOU QUIETO O SUFICIENTE."
DEATH_RETRY = "[ENTER] Tentar de novo    [ESC] Sair"

# Dicas de carregamento / rodapé de menu
TIPS = [
    "Agachar (C) faz menos barulho. Tapete abafa os passos.",
    "Ele escuta. Ele vê a lanterna de longe. Ele não vê no escuro.",
    "Portas fechadas seguram o som. Portas batidas, não.",
    "O zumbido de uma geladeira esconde o que você faz por perto.",
    "Quando o zumbido dele para, ele está perto.",
    "Segure Q ou Tab e mova o mouse para escolher o que levar na mão esquerda.",
]

CONTROLS = [
    ("W A S D", "andar"),
    ("Mouse", "olhar"),
    ("Shift", "correr (barulhento)"),
    ("C / Ctrl", "agachar (silencioso)"),
    ("F", "lanterna"),
    ("R", "trocar pilhas"),
    ("E", "interagir"),
    ("Q / Tab", "roda de itens (segurar)"),
    ("Esc", "pausar"),
]
