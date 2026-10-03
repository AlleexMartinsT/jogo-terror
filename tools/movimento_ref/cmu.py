"""Acervo de captura de movimento da CMU (pessoas reais), por trás de um cache local.

Fonte dos dados: CMU Graphics Lab Motion Capture Database, na conversão BVH de cgspeed, espelhada em
github.com/Shriinivas/cmubvh. A CMU "não coloca restrições ao uso do conjunto de dados". O jogo não depende disto:
é material de conferência (tools/ e tests/ de movimento).

    from tools.movimento_ref import cmu
    cmu.buscar("flashlight")            # [(id, quadros, descricao), ...]
    clip = cmu.carregar("07_01")        # Mocap (120 Hz); baixa na primeira vez e guarda em out/referencia/cmu
    clip = cmu.carregar("17_03", inicio=4.0, fim=12.0)     # só um trecho, em segundos

Rede: só `raw.githubusercontent.com` responde neste ambiente (github.com e mocap.cs.cmu.edu estão bloqueados);
o download usa o `curl` do sistema, que já conhece o proxy e o certificado.
"""
import io
import json
import os
import subprocess
import zipfile

import numpy as np

from . import bvh

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDICE = os.path.join(RAIZ, "assets", "referencia", "cmu_index.json")
CACHE = os.path.join(RAIZ, "out", "referencia", "cmu")
ESPELHO = "https://raw.githubusercontent.com/Shriinivas/cmubvh/main/"


def _indice():
    with open(INDICE, encoding="utf-8") as arquivo:
        return {item["id"]: item for item in json.load(arquivo)}


def buscar(texto):
    """Clipes cuja descrição contém `texto` (sem diferenciar maiúsculas): [(id, quadros, descrição)]."""
    chave = texto.lower()
    return [(i["id"], i["frames"], i["descricao"]) for i in _indice().values() if chave in i["descricao"].lower()]


def baixar(clip_id):
    """Garante o BVH em `CACHE` e devolve o caminho."""
    destino = os.path.join(CACHE, f"{clip_id}.bvh")
    if os.path.exists(destino):
        return destino
    item = _indice().get(clip_id)
    if item is None:
        raise KeyError(f"clipe {clip_id!r} não está no índice")
    os.makedirs(CACHE, exist_ok=True)
    resposta = subprocess.run(["curl", "-sS", "-L", "-m", "180", ESPELHO + item["caminho"]],
                              capture_output=True, check=True)
    with zipfile.ZipFile(io.BytesIO(resposta.stdout)) as pacote:
        nome = next(n for n in pacote.namelist() if n.lower().endswith(".bvh"))
        with open(destino, "wb") as arquivo:
            arquivo.write(pacote.read(nome))
    return destino


def carregar(clip_id, inicio=None, fim=None):
    """Mocap do clipe, opcionalmente só entre `inicio` e `fim` (segundos)."""
    with open(baixar(clip_id), encoding="utf-8") as arquivo:
        clip = bvh.parse(arquivo.read(), clip_id)
    if inicio is not None or fim is not None:
        a = int(round((inicio or 0.0) * clip.fps))
        b = int(round((fim if fim is not None else clip.duration) * clip.fps))
        clip.data = np.ascontiguousarray(clip.data[a:b])
    return clip


# O conjunto que a fase 4 usa como referência. Cada entrada diz POR QUE o clipe está aqui.
REFERENCIAS = {
    "andar": ("07_01", "caminhada normal, 1,36 m/s"),
    "andar_2": ("08_01", "outra pessoa andando"),
    "andar_devagar": ("07_04", "andar devagar"),
    "andar_parar": ("16_33", "andar devagar e parar"),
    "correr": ("09_01", "corrida"),
    "curva": ("16_17", "andar e virar 90 graus à esquerda"),
    "furtivo": ("17_03", "andar furtivamente (silencioso)"),
    "rastejar": ("77_14", "andar com cuidado, esgueirando"),
    "agachado": ("136_09", "andar agachado"),
    "escada": ("83_27", "subir escada andando"),
    "degraus": ("13_35", "subir três degraus"),
    "lanterna": ("77_05", "olhar em volta com lanterna"),
    "cuidado": ("91_18", "andar com cuidado olhando em volta"),
    "pegar_chao": ("26_09", "abaixar e pegar um objeto"),
    "alcancar": ("15_06", "inclinar e alcançar"),
    "empurrar": ("81_05", "empurrar objeto pesado"),
    "levantar": ("111_09", "levantar de uma cadeira"),
    "sentar_levantar": ("13_01", "sentar e levantar de banco"),
    "pegar_chaves": ("22_22", "andar e apanhar chaves jogadas"),
}


if __name__ == "__main__":
    for nome, (clip_id, motivo) in REFERENCIAS.items():
        caminho = baixar(clip_id)
        print(f"{nome:15s} {clip_id}  {os.path.getsize(caminho) / 1e3:7.0f} KB  {motivo}")
