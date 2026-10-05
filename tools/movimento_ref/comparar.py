"""Comparação real x jogo de ponta a ponta: retarget, palco, quadros, folha de contato, gráficos, tabela e vídeo.

    LIBGL_ALWAYS_SOFTWARE=1 python -m tools.movimento_ref.comparar andar --vistas frente,lado,topo,primeira \\
        --saida out/movimento/andar
    python -m tools.movimento_ref.comparar --lista                       # cenários registrados (cenarios/)
    python -m tools.movimento_ref.comparar --folha-retarget 07_01 --saida out/movimento/retarget_07_01

Saída em `--saida`:
    video.mp4              H.264, 30 quadros/s; vistas em grade, cada uma com [real | jogo] no mesmo quadro (a primeira pessoa
                           são duas câmeras, uma por corpo); legenda do clipe, velocidade, fase e contato dos pés
    folha_contato.png      as quatro fases-chave (toque do calcanhar, apoio médio, saída do pé, balanço médio) em todas as vistas
    quadros/               cada célula da folha de contato, em PNG
    curvas.png             ângulos e oscilações por % do ciclo (real: média +-1 desvio de vários clipes; jogo)
    tabela.png, tabela.txt métrica por métrica: real, desvio entre as pessoas reais, jogo, diferença e tolerância
    apoios.png             diagrama de apoios dos dois pés
    metricas.json          os escalares de tudo isso

Vistas: frente, lado, costas, topo, tres_quartos, primeira (= primeira_pessoa). O vídeo mostra o real em tempo real x `lento`
(padrão 0,5) e toca o jogo na MESMA FASE: cada ciclo do jogo ocupa o tempo do ciclo correspondente do real, porque as duas
cadências são diferentes. A legenda diz o fator de velocidade do jogo.
"""
import argparse
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from tools.movimento_ref import cenarios, graficos, metricas  # noqa: E402

CELULA = (640, 360)
AZUL, LARANJA = (42, 120, 214), (235, 104, 52)
TINTA, TINTA_SUAVE = (11, 11, 11), (82, 81, 78)
ALIAS_VISTA = {"primeira": "primeira_pessoa", "primeira_pessoa": "primeira_pessoa"}


# --------------------------------------------------------------------------
# Desenho de texto e montagem de imagens
# --------------------------------------------------------------------------
_fontes = {}


def fonte(tamanho, negrito=False):
    chave = (tamanho, negrito)
    if chave not in _fontes:
        import matplotlib
        nome = "DejaVuSans-Bold.ttf" if negrito else "DejaVuSans.ttf"
        _fontes[chave] = ImageFont.truetype(os.path.join(matplotlib.get_data_path(), "fonts", "ttf", nome), tamanho)
    return _fontes[chave]


def rotular(imagem, linhas, canto, cor=(255, 255, 255), fundo=(0, 0, 0, 150), tamanho=14, negrito_primeira=True, ancora="esq"):
    """Escreve `linhas` (str ou lista) na imagem [h, w, 3] uint8, numa caixa translúcida. `canto` = (x, y) do canto
    superior esquerdo (ou direito, com ancora="dir"). Devolve a imagem."""
    linhas = [linhas] if isinstance(linhas, str) else list(linhas)
    base = Image.fromarray(imagem).convert("RGBA")
    camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
    desenho = ImageDraw.Draw(camada)
    larguras = [desenho.textlength(t, font=fonte(tamanho, negrito_primeira and i == 0)) for i, t in enumerate(linhas)]
    largura, altura = max(larguras) + 12, len(linhas) * (tamanho + 5) + 6
    x, y = canto
    if ancora == "dir":
        x -= largura
    desenho.rectangle([x, y, x + largura, y + altura], fill=fundo)
    for i, texto in enumerate(linhas):
        desenho.text((x + 6, y + 4 + i * (tamanho + 5)), texto, font=fonte(tamanho, negrito_primeira and i == 0), fill=cor)
    return np.array(Image.alpha_composite(base, camada).convert("RGB"))


def grade(celulas, colunas, fundo=(252, 252, 251)):
    """Junta imagens do mesmo tamanho em linhas de `colunas`; células ausentes ficam em branco."""
    altura, largura = celulas[0].shape[:2]
    linhas = int(math.ceil(len(celulas) / colunas))
    tela = np.full((linhas * altura, colunas * largura, 3), fundo, np.uint8)
    for i, celula in enumerate(celulas):
        r, c = divmod(i, colunas)
        tela[r * altura:(r + 1) * altura, c * largura:(c + 1) * largura] = celula
    return tela


def salvar_png(imagem, caminho):
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    Image.fromarray(imagem).save(caminho)
    return caminho


def escrever_mp4(quadros, caminho, fps=30, qualidade=7):
    """Grava uma sequência de imagens [h, w, 3] uint8 em MP4 H.264 (yuv420p). `quadros` pode ser um gerador."""
    import imageio_ffmpeg
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    quadros = iter(quadros)
    primeiro = next(quadros)
    altura, largura = primeiro.shape[:2]
    escritor = imageio_ffmpeg.write_frames(caminho, (largura, altura), fps=fps, codec="libx264", quality=qualidade,
                                           pix_fmt_in="rgb24", pix_fmt_out="yuv420p", macro_block_size=2,
                                           output_params=["-movflags", "+faststart"])
    escritor.send(None)
    escritor.send(np.ascontiguousarray(primeiro).tobytes())
    total = 1
    for quadro in quadros:
        escritor.send(np.ascontiguousarray(quadro).tobytes())
        total += 1
    escritor.close()
    return caminho, total


# --------------------------------------------------------------------------
# Quadros do palco
# --------------------------------------------------------------------------
def normalizar_vistas(vistas):
    if isinstance(vistas, str):
        vistas = [v for v in vistas.split(",") if v]
    saida = []
    for v in vistas:
        v = ALIAS_VISTA.get(v.strip(), v.strip())
        if v not in saida:
            saida.append(v)
    return saida


def _rotacao_interpolada(tabela, k):
    i0 = int(np.clip(math.floor(k), 0, len(tabela) - 1))
    i1 = min(i0 + 1, len(tabela) - 1)
    f = float(np.clip(k - i0, 0.0, 1.0))
    m = tabela[i0] * (1 - f) + tabela[i1] * f
    u, _s, vt = np.linalg.svd(m)
    return u @ vt


class Desenhista:
    """Renderiza o par real x jogo de um cenário preparado, em qualquer instante do relógio do real."""

    def __init__(self, prep, celula=CELULA, motor="workbench"):
        from tools.movimento_ref.palco import Palco
        self.prep = prep
        self.celula = celula
        self.palco = Palco(celula[0], celula[1], motor)
        self.alvo = prep.real.alvo
        self.rec = prep.gravacao
        self.palco.origem("real", self.alvo.raiz[0, :2], self.alvo.raiz[0, 3])
        j0 = prep.jogo_t0 * self.rec.fps
        self.palco.origem("jogo", self.rec.raiz[int(j0), :2], self.rec.raiz[int(j0), 3])

    def tempos(self, t_real):
        """(índice fracionário no retarget, índice fracionário na gravação, segundos no recorte do jogo)."""
        prep = self.prep
        t_jogo = float(prep.alinhamento.jogo_de_real(t_real))
        return t_real * self.alvo.fps, (prep.jogo_t0 + t_jogo) * self.rec.fps, t_jogo

    def _poses(self, k, j):
        self.palco.pose_real(self.alvo, k)
        self.palco.pose_jogo(self.rec, j)

    def terceira_pessoa(self, vista, t_real):
        k, j, _ = self.tempos(t_real)
        self.palco.vista(vista)
        self._poses(k, j)
        imagem = self.palco.render_array()
        (real1, real2), (jogo1, jogo2) = self.prep.cenario.legenda(self.prep)
        metade = imagem.shape[1] // 2
        imagem = rotular(imagem, [real1, real2], (4, 4), cor=(255, 255, 255), fundo=(*AZUL, 215), tamanho=12)
        imagem = rotular(imagem, [jogo1, jogo2], (metade + 4, 4), cor=(255, 255, 255), fundo=(*LARANJA, 215), tamanho=12)
        return rotular(imagem, vista, (4, imagem.shape[0] - 24), tamanho=12, negrito_primeira=False, fundo=(0, 0, 0, 120))

    def primeira_pessoa(self, lado, t_real):
        palco, rec, alvo = self.palco, self.rec, self.alvo
        k, j, _ = self.tempos(t_real)
        palco.vista("primeira_pessoa", lado)
        self._poses(k, j)
        if lado == "real":
            posicao = palco.olho_do_corpo("real")
            rotacao = palco.rotacao_para_palco("real", _rotacao_interpolada(alvo.olhar_rot, k))
        else:
            raiz = palco._linear(rec.raiz, j)
            camera = palco._linear(rec.camera_pos, j)
            posicao = palco.para_palco("jogo", camera, raiz[:2], rec.raiz[0, 2])
            rotacao = palco.rotacao_para_palco("jogo", _rotacao_interpolada(rec.camera_rot, j))
        palco.camera_na_primeira_pessoa(posicao, rotacao)
        imagem = palco.render_array()
        cor = AZUL if lado == "real" else LARANJA
        return rotular(imagem, "REAL (olhos do mocap)" if lado == "real" else "JOGO (câmera do jogador)", (4, 4),
                       fundo=(*cor, 215), tamanho=12)

    def painel_info(self, t_real, fase_texto=""):
        """Célula de texto: o que se vê, a velocidade relativa do jogo e quais pés tocam o chão agora."""
        prep = self.prep
        cen = prep.cenario
        celula = np.full((self.celula[1], self.celula[0], 3), (252, 252, 251), np.uint8)
        (real1, real2), (jogo1, jogo2) = cen.legenda(prep)
        k, j, t_jogo = self.tempos(t_real)
        razao = prep.alinhamento.razao(t_real)
        linhas = [(cen.titulo, TINTA, True, 15), ("", TINTA, False, 8), (real1, AZUL, True, 13), (real2, TINTA_SUAVE, False, 12),
                  (jogo1, LARANJA, True, 13), (jogo2, TINTA_SUAVE, False, 12), ("", TINTA, False, 8),
                  (prep.real.descricao, TINTA_SUAVE, False, 11) if prep.real.descricao else ("", TINTA, False, 4),
                  (f"câmera lenta x{cen.lento:g}; o jogo toca na fase do real (x{razao:.2f} da velocidade do jogo)", TINTA_SUAVE, False, 11),
                  (fase_texto, TINTA_SUAVE, False, 11)]
        imagem = Image.fromarray(celula)
        d = ImageDraw.Draw(imagem)
        y = 8
        for texto, cor, negrito, tamanho in linhas:
            d.text((10, y), texto, font=fonte(tamanho, negrito), fill=cor)
            y += tamanho + 6
        # estado do instante (no marcha: quais pés tocam o chão; no alcance: a velocidade da mão)
        y += 6
        for linha in cen.estado_instantaneo(prep, t_real, t_jogo):
            rotulo, cor = linha["rotulo"], linha["cor"]
            d.text((10, y), rotulo, font=fonte(12, True), fill=cor)
            for i, (texto, cheio) in enumerate(linha["itens"]):
                x = 72 + i * 150
                if cheio is not None:
                    d.ellipse([x, y + 1, x + 14, y + 15], fill=cor if cheio else (252, 252, 251), outline=cor, width=2)
                    x += 20
                d.text((x, y), texto, font=fonte(12), fill=TINTA)
            y += 26
        # métricas do cenário, real x jogo (valores medidos nos trechos, não do instante)
        y += 6
        d.text((10, y), "métrica", font=fonte(11, True), fill=TINTA_SUAVE)
        d.text((330, y), "real", font=fonte(11, True), fill=AZUL)
        d.text((410, y), "jogo", font=fonte(11, True), fill=LARANJA)
        d.text((490, y), "tolerância", font=fonte(11, True), fill=TINTA_SUAVE)
        y += 17
        tabela = {l.chave: l for l in cen.linhas(prep)}
        for chave in cen.destaques:
            if chave not in tabela:
                continue
            linha = tabela[chave]
            d.text((10, y), f"{linha.rotulo} ({linha.unidade})", font=fonte(11), fill=TINTA)
            d.text((330, y), f"{linha.real:.{linha.casas}f}", font=fonte(11), fill=TINTA)
            d.text((410, y), f"{linha.jogo:.{linha.casas}f}", font=fonte(11), fill=TINTA)
            d.text((490, y), f"+-{linha.tolerancia:.{linha.casas}f}  " + ("dentro" if linha.ok else "FORA"), font=fonte(11, linha.ok is False),
                   fill=TINTA if linha.ok else (190, 40, 30))
            y += 16
        return np.array(imagem)


def _quadro_video(desenhista, vistas_terceira, primeira, t_real, fase_texto, colunas):
    celulas = [desenhista.terceira_pessoa(v, t_real) for v in vistas_terceira]
    if primeira:
        celulas.append(desenhista.primeira_pessoa("real", t_real))
        celulas.append(desenhista.primeira_pessoa("jogo", t_real))
    celulas.append(desenhista.painel_info(t_real, fase_texto))
    return grade(celulas, colunas)


# --------------------------------------------------------------------------
# Folha de contato
# --------------------------------------------------------------------------
def folha_de_contato(desenhista, saida, vistas_terceira, primeira, redutor=0.75):
    prep = desenhista.prep
    fases = prep.cenario.fases_chave(prep)
    linhas, nomes_arquivo = [], []
    pasta = os.path.join(saida, "quadros")
    for nome, t_real in fases:
        coluna = []
        for vista in vistas_terceira:
            imagem = desenhista.terceira_pessoa(vista, t_real)
            salvar_png(imagem, os.path.join(pasta, f"{_slug(nome)}_{vista}.png"))
            coluna.append(imagem)
        if primeira:
            real = desenhista.primeira_pessoa("real", t_real)
            jogo = desenhista.primeira_pessoa("jogo", t_real)
            salvar_png(real, os.path.join(pasta, f"{_slug(nome)}_primeira_real.png"))
            salvar_png(jogo, os.path.join(pasta, f"{_slug(nome)}_primeira_jogo.png"))
            reduzido = [np.array(Image.fromarray(i).resize((i.shape[1] // 2, i.shape[0] // 2), Image.LANCZOS)) for i in (real, jogo)]
            coluna.append(np.concatenate(reduzido, axis=1))
        linhas.append((nome, t_real, coluna))
    # uma coluna por fase, uma linha por vista
    quantidade = max(len(c) for _, _, c in linhas)
    largura = desenhista.celula[0]
    colunas_img = []
    for nome, t_real, coluna in linhas:
        cabecalho = np.full((40, largura, 3), (252, 252, 251), np.uint8)
        imagem = Image.fromarray(cabecalho)
        d = ImageDraw.Draw(imagem)
        d.text((8, 4), nome, font=fonte(16, True), fill=TINTA)
        d.text((8, 24), f"real t = {t_real:.2f} s   jogo t = {float(prep.alinhamento.jogo_de_real(t_real)):.2f} s", font=fonte(11), fill=TINTA_SUAVE)
        colunas_img.append(np.concatenate([np.array(imagem)] + coluna, axis=0))
    folha = np.concatenate(colunas_img, axis=1)
    if redutor != 1.0:
        folha = np.array(Image.fromarray(folha).resize((int(folha.shape[1] * redutor), int(folha.shape[0] * redutor)), Image.LANCZOS))
    caminho = salvar_png(folha, os.path.join(saida, "folha_contato.png"))
    return caminho, [(n, t) for n, t, _ in linhas]


def _slug(texto):
    tabela = str.maketrans("áàâãéêíóôõúç ", "aaaaeeiooouc_")
    return texto.lower().translate(tabela).replace("/", "_")


# --------------------------------------------------------------------------
# Métricas, gráficos e tabela
# --------------------------------------------------------------------------
def medidas(prep, saida):
    """Gráficos, tabela e json do cenário (o gancho `Cenario.medidas`). Devolve ({nome: caminho}, linhas)."""
    return prep.cenario.medidas(prep, saida)


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------
def executar_corpo(cenario, saida, vistas, fps=30, celula=CELULA, video=True, folha=True, preparado=None,
                   max_quadros=None, motor="workbench"):
    inicio = time.time()
    os.makedirs(saida, exist_ok=True)
    vistas = normalizar_vistas(vistas)
    primeira = "primeira_pessoa" in vistas
    terceira = [v for v in vistas if v != "primeira_pessoa"]
    prep = preparado or cenario.preparar()
    print(f"[comparar] {cenario.nome}: preparado em {time.time() - inicio:.1f} s", flush=True)
    arquivos, linhas = medidas(prep, saida)
    print(f"[comparar] gráficos e tabela em {time.time() - inicio:.1f} s", flush=True)
    desenhista = Desenhista(prep, celula, motor)
    if folha:
        caminho, fases = folha_de_contato(desenhista, saida, terceira, primeira)
        arquivos["folha_contato"] = caminho
        print(f"[comparar] folha de contato em {time.time() - inicio:.1f} s", flush=True)
    if video:
        duracao_real = prep.real.movimento.duracao
        n_celulas = len(terceira) + (2 if primeira else 0) + 1
        colunas = 3 if n_celulas > 4 else 2
        total = int(duracao_real / cenario.lento * fps)
        # não passa do que a gravação do jogo cobre
        t_max_jogo = prep.gravacao.t[-1] - prep.jogo_t0
        while total > 1 and float(prep.alinhamento.jogo_de_real(((total - 1) / fps) * cenario.lento)) > t_max_jogo:
            total -= 1
        if max_quadros:
            total = min(total, max_quadros)
        fases_texto = f"quadro {{n}}/{total}"

        def quadros():
            for n in range(total):
                t_real = (n / fps) * cenario.lento
                yield _quadro_video(desenhista, terceira, primeira, t_real, fases_texto.format(n=n + 1), colunas)
                if n % 30 == 0:
                    print(f"[comparar]   quadro {n + 1}/{total} ({time.time() - inicio:.0f} s)", flush=True)

        caminho, escritos = escrever_mp4(quadros(), os.path.join(saida, "video.mp4"), fps)
        arquivos["video"] = caminho
        print(f"[comparar] vídeo: {escritos} quadros em {time.time() - inicio:.1f} s", flush=True)
    resumo = [f"{cenario.nome}: {cenario.titulo}", f"gerado em {time.time() - inicio:.0f} s"] + \
             [f"  {k:14s} {v}" for k, v in arquivos.items()]
    fora = [l for l in linhas if l.ok is False]
    resumo.append(f"  métricas: {sum(1 for l in linhas if l.ok)} dentro da tolerância, {len(fora)} fora")
    with open(os.path.join(saida, "resumo.txt"), "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(resumo) + "\n")
    print("\n".join(resumo), flush=True)
    arquivos["linhas"] = linhas
    return arquivos


# --------------------------------------------------------------------------
# Folha de conferência do retarget: mocap em linhas sobre o Daniel retargetado
# --------------------------------------------------------------------------
def folha_retarget(clip_id, saida, tempos=(0.2, 0.5, 0.9, 1.3), vistas=("frente", "lado"), inicio=None, fim=None, celula=CELULA,
                   bracos="direcao"):
    """Daniel retargetado (real) com o esqueleto do mocap em linhas verdes por cima, em duas vistas, em vários instantes."""
    from tools.movimento_ref import cmu, retarget
    from tools.movimento_ref.movimento import OSSOS, INDICE
    from tools.movimento_ref.palco import Palco
    alvo = retarget.retargetar(cmu.carregar(clip_id), inicio, fim, bracos=bracos)
    palco = Palco(celula[0], celula[1])
    palco.origem("real", alvo.raiz[0, :2], alvo.raiz[0, 3])
    escalado = alvo.alvo_escalado()
    linhas = []
    for t in tempos:
        k = min(t * alvo.fps, alvo.quadros - 1)
        linha = []
        for vista in vistas:
            palco.vista(vista)
            palco.jogo.visivel(False)
            palco.piso_jogo.visivel(False)
            # a vista do palco põe o real à esquerda; aqui ele fica sozinho, no centro do quadro
            palco.pedestal["real"] = (0.0, 0.0)
            palco.piso_real.dimensionar((0.0, 0.0), palco.piso_real.azimute, 4.0, 5.5)
            palco.pose_real(alvo, k)
            imagem = palco.render_array()
            i = int(round(k))
            raiz = alvo.raiz[i]
            pontos = {}
            for nome in INDICE:
                p = palco.para_palco("real", escalado[i, INDICE[nome]], raiz[:2])
                pontos[nome] = palco.projetar(p)
            camada = Image.fromarray(imagem)
            d = ImageDraw.Draw(camada)
            for a, b in OSSOS:
                if pontos[a] and pontos[b]:
                    d.line([pontos[a], pontos[b]], fill=(30, 220, 90), width=2)
            for nome, ponto in pontos.items():
                if ponto:
                    d.ellipse([ponto[0] - 3, ponto[1] - 3, ponto[0] + 3, ponto[1] + 3], outline=(20, 120, 50), fill=(30, 220, 90))
            imagem = rotular(np.array(camada), [f"{vista}  t = {t:.2f} s", "Daniel retargetado + mocap (verde)"], (4, 4), tamanho=12)
            linha.append(imagem)
        linhas.append(np.concatenate(linha, axis=1))
    folha = np.concatenate(linhas, axis=0)
    caminho = salvar_png(folha, os.path.join(saida, f"retarget_{clip_id}.png"))
    erro = alvo.erro_de_juntas()
    with open(os.path.join(saida, f"retarget_{clip_id}.txt"), "w", encoding="utf-8") as arquivo:
        arquivo.write(f"retarget {clip_id}: escala {alvo.escala:.3f}\n")
        for junta, (media, maximo) in erro.items():
            arquivo.write(f"  {junta:14s} erro médio {media * 100:5.1f} cm   máx {maximo * 100:5.1f} cm\n")
    return caminho


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cenario", nargs="?", help="nome do cenário (veja --lista)")
    ap.add_argument("--vistas", default="frente,lado,topo,primeira")
    ap.add_argument("--saida", help="pasta de saída (padrão out/movimento/<cenario>)")
    ap.add_argument("--lista", action="store_true")
    ap.add_argument("--sem-video", action="store_true")
    ap.add_argument("--sem-folha", action="store_true")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--celula", default="640x360")
    ap.add_argument("--max-quadros", type=int)
    ap.add_argument("--lento", type=float, help="fator de câmera lenta (padrão do cenário)")
    ap.add_argument("--eevee", action="store_true", help="EEVEE em vez de Workbench (lento: só para quadros de destaque)")
    ap.add_argument("--folha-retarget", metavar="CLIPE", help="só a folha de conferência do retarget de um clipe CMU")
    args = ap.parse_args(argv)
    if args.lista:
        for nome, titulo in cenarios.listar():
            print(f"  {nome:20s} {titulo}")
        for aviso in cenarios.avisos:
            print("  aviso:", aviso)
        return 0
    celula = tuple(int(v) for v in args.celula.lower().split("x"))
    if args.folha_retarget:
        saida = args.saida or os.path.join(ROOT, "out", "movimento", f"retarget_{args.folha_retarget}")
        print(folha_retarget(args.folha_retarget, saida, celula=celula))
        return 0
    if not args.cenario:
        ap.error("diga o cenário (ou --lista)")
    cenario = cenarios.obter(args.cenario)
    if args.lento:
        cenario.lento = args.lento
    saida = args.saida or os.path.join(ROOT, "out", "movimento", args.cenario)
    cenario.executar(saida, args.vistas, fps=args.fps, celula=celula, video=not args.sem_video, folha=not args.sem_folha,
                     max_quadros=args.max_quadros, motor="eevee" if args.eevee else "workbench")
    return 0


if __name__ == "__main__":
    sys.exit(main())
