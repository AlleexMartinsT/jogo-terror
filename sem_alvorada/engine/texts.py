"""Textos da interface que não pertencem à narrativa (story.py). pt-BR, sem emojis."""

METER_TITLE = "SOM"
METER_LABELS = {"player": "VOCÊ", "ambient": "AMBIENTE", "entity": "ENTIDADE"}
METER_THRESHOLD_HINT = "marca: acima daqui ele escuta você"

HUD_FLASHLIGHT = "LANTERNA [F]"
HUD_NO_CHARGE = "SEM CARGA"
HUD_SWAP_HINT = "[R] trocar a pilha"
HUD_STAMINA = "FÔLEGO"
MSG_BATTERY_GOOD = "A pilha ainda está boa."     # só o flashlight.py usa; sai quando ele parar de falar

# Roda de itens (Q ou Tab): um nome por setor, na ordem de inventory.SLOTS.
WHEEL_LABELS = {"FLASHLIGHT": "Lanterna", "BATTERY": "Pilhas", "KEY": "Chave", "MAP": "Mapa", "NOTE": "Anotações"}
WHEEL_IN_HAND = "NA MÃO"
WHEEL_TAKE = "PEGAR"

READER_CLOSE = "[E] fechar"

PAUSE_TITLE = "PAUSADO"
PAUSE_OBJECTIVE = "OBJETIVO"
PAUSE_COLLECT = "COLETA"
PAUSE_CONTROLS = "CONTROLES"
PAUSE_HELP = "[ENTER] continuar    [ESC] sair"
TITLE_START = "[ENTER] começar    [ESC] sair"
CREDITS_LINES = [
    "SEM ALVORADA",
    "Feito inteiramente no Blender, com Python.",
    "Nenhum modelo, textura ou som foi baixado.",
]
CREDITS_BACK = "[ENTER] voltar ao título"

ERROR_BANNER = "ERRO NO JOGO: {message}  (veja o console do Blender)"

# Texto do datablock LEIA-ME embutido no .blend (build de engine).
README_LINES = [
    "SEM ALVORADA - como jogar",
    "",
    "1. No editor de texto do Blender, abra o texto 'jogar.py' e clique em Executar (Alt+P).",
    "   Alternativa pelo terminal, na raiz do projeto:",
    "       blender SemAlvorada.blend --python play.py -- --quality medium",
    "",
    "2. A área 3D ocupa a janela inteira. Esc pausa; um segundo Esc sai e devolve a interface.",
    "",
    "Controles:",
    "   W A S D      andar",
    "   Mouse        olhar",
    "   Shift        correr (gasta fôlego, faz barulho)",
    "   C ou Ctrl    agachar (silencioso)",
    "   F            liga e desliga a lanterna",
    "   R            troca a pilha da lanterna",
    "   E            interagir (pegar, ler, abrir portas)",
    "   Enter        confirmar nos menus",
    "   Espaço       pular cena",
    "",
    "Objetivo: ache a chave do carro, o mapa da cidade e 3 pilhas reserva, destranque",
    "a porta da garagem (cozinha), entre no carro e fuja.",
    "",
    "O Alto escuta melhor do que enxerga. O medidor SOM, no canto inferior esquerdo,",
    "mostra o que você faz de barulho (VOCÊ), o ruído que esconde você (AMBIENTE)",
    "e o que você ouve dele (ENTIDADE).",
    "",
    "Opções de linha de comando (depois de '--'):",
    "   --quality low|medium|high   qualidade gráfica",
    "   --skip-intro                pula a cena de abertura",
    "   --debug                     mostra posição, cômodo e teclas de teste (F1 a F4)",
]
