"""Reúne as fotos e os vídeos finais da fase 4 em `docs/movimento/`, que é o que vai para o repositório.

`out/` fica fora do git (passa de 200 MB entre quadros, gravações e rascunhos). Aqui entra só o que
o leitor precisa ver: PNG vira JPEG (cerca de um quinto do tamanho, sem perda que se note em painel
de texto e render) e os MP4 são copiados como saíram dos geradores.

    python -m tools.movimento_ref.publicar            # copia o que existir, avisa o que faltar
    python -m tools.movimento_ref.publicar --lista    # só mostra o plano

Quem gera cada arquivo está em `docs/MOVIMENTO.md`.
"""
import argparse
import os
import shutil
import sys

from PIL import Image

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SAIDA = os.path.join(RAIZ, "docs", "movimento")
LARGURA_MAXIMA = 2000
QUALIDADE_JPEG = 86

LOCOMOCAO = "out/f4_2/final"
MAOS = "out/f4_3/final"
OBJETOS = "out/f4_4/final"
REFERENCIA = "out/f4_1/final"


def _por_cenario(pasta, cenarios, arquivos):
    for cenario in cenarios:
        for origem, destino in arquivos:
            yield f"{pasta}/{cenario}/{origem}", f"{cenario}_{destino}"


def plano():
    """Lista de (origem relativa a RAIZ, grupo, nome de destino). Imagem .png sai como .jpg."""
    itens = []
    marcha = ("andar", "andar_devagar", "correr", "agachado")
    for origem, nome in _por_cenario(LOCOMOCAO, marcha, [("folha_contato.png", "folha.png"), ("curvas.png", "curvas.png"),
                                                          ("antes_depois.png", "antes_depois.png"),
                                                          ("apoios.png", "apoios.png")]):
        itens.append((origem, "locomocao", nome))
    for cenario in ("andar", "correr", "agachado"):
        itens.append((f"{LOCOMOCAO}/{cenario}/video.mp4", "locomocao", f"{cenario}_video.mp4"))
    for origem, nome in _por_cenario(LOCOMOCAO, ("parar", "curva"), [("folha_contato.png", "folha.png"),
                                                                     ("series.png", "series.png"),
                                                                     ("video.mp4", "video.mp4")]):
        itens.append((origem, "locomocao", nome))
    itens += [(f"{LOCOMOCAO}/escada/series.png", "locomocao", "escada_series.png"),
              (f"{LOCOMOCAO}/andar/tabela.png", "locomocao", "andar_tabela.png")]

    for nome in ("alcance_perfis", "chaveiro_pendulo", "lanterna_luz", "tabela"):
        itens.append((f"{MAOS}/{nome}.png", "maos", f"{nome}.png"))
    for item in ("lanterna", "pilha", "chave", "mapa", "nota", "troca"):
        itens.append((f"{MAOS}/maos_{item}_antes_depois.png", "maos", f"antes_depois_{item}.png"))
    for cenario in ("alcancar", "lanterna_olhar", "pegar_chave", "pilhas", "nota", "pegar_chao"):
        base = f"{MAOS}/paineis/{cenario}"
        itens += [(f"{base}/folha_contato.png", "maos", f"{cenario}_folha.png"),
                  (f"{base}/alcance.png", "maos", f"{cenario}_perfil.png"),
                  (f"{base}/video.mp4", "maos", f"{cenario}_video.mp4")]

    for objeto in ("porta_25kg", "porta_40kg", "relogio", "carro"):
        base = f"{OBJETOS}/blender/render3d_{objeto}"
        itens += [(f"{base}.mp4", "objetos", f"render3d_{objeto}.mp4"),
                  (f"{base}_folha.png", "objetos", f"render3d_{objeto}_folha.png")]
    for objeto in ("porta_25kg", "relogio", "carro"):
        itens.append((f"{OBJETOS}/blender/render3d_{objeto}_eevee.png", "objetos", f"render3d_{objeto}_eevee.png"))
    for grafico in ("porta_abrir", "porta_fecha_e_batida", "porta_empurrao_e_esforco", "porta_mao_real", "carro_arfagem",
                    "carro_rodas_direcao", "charm_pendulos", "portao_garagem", "relogio_pendulo", "cortina_modos",
                    "poeira_queda", "luz_incandescente_fluorescente_tv"):
        itens.append((f"{OBJETOS}/grafico_{grafico}.png", "objetos", f"grafico_{grafico}.png"))
    itens += [(f"{OBJETOS}/esquema_cortina.mp4", "objetos", "esquema_cortina.mp4"),
              (f"{OBJETOS}/esquema_portao.mp4", "objetos", "esquema_portao.mp4"),
              (f"{OBJETOS}/tabela_fisica_objetos.md", "objetos", "tabela_fisica_objetos.md")]

    for clipe in ("07_01", "09_01", "136_09", "26_09"):
        itens.append((f"{REFERENCIA}/retarget_{clipe}.png", "referencia", f"retarget_{clipe}.png"))
    itens.append((f"{REFERENCIA}/referencias_medidas.md", "referencia", "referencias_medidas.md"))
    return itens


def _jpeg(origem, destino):
    imagem = Image.open(origem).convert("RGB")
    if imagem.width > LARGURA_MAXIMA:
        imagem = imagem.resize((LARGURA_MAXIMA, round(imagem.height * LARGURA_MAXIMA / imagem.width)), Image.LANCZOS)
    imagem.save(destino, "JPEG", quality=QUALIDADE_JPEG, optimize=True)


def publicar(so_listar=False):
    copiados, faltando, bytes_total = 0, [], 0
    for origem, grupo, nome in plano():
        caminho = os.path.join(RAIZ, origem)
        if not os.path.exists(caminho):
            faltando.append(origem)
            continue
        if nome.endswith(".png"):
            nome = nome[:-4] + ".jpg"
        destino = os.path.join(SAIDA, grupo, nome)
        if so_listar:
            print(f"{origem}  ->  docs/movimento/{grupo}/{nome}")
            continue
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        if nome.endswith(".jpg"):
            _jpeg(caminho, destino)
        else:
            shutil.copyfile(caminho, destino)
        copiados += 1
        bytes_total += os.path.getsize(destino)
    if not so_listar:
        print(f"{copiados} arquivos em docs/movimento ({bytes_total / 1e6:.1f} MB)")
    for origem in faltando:
        print(f"  faltando: {origem}")
    return 0 if not faltando else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lista", action="store_true")
    sys.exit(publicar(parser.parse_args().lista))
