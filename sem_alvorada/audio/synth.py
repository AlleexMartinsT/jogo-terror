"""Gera todos os WAV do jogo a partir das receitas (numpy puro, sem samples externos).

    python -m sem_alvorada.audio.synth                    # escreve assets/audio/*.wav
    python -m sem_alvorada.audio.synth --only door_open   # só um som (ou prefixo, ex.: step_wood)
    python -m sem_alvorada.audio.synth --report           # métricas + PNGs em out/audio/

Cada som usa um gerador de números aleatórios semeado pelo NOME, então o resultado é
idêntico a cada execução e mexer numa receita não muda o som das outras.
"""
import argparse
import os
import sys
import zlib

import numpy as np

from .. import AUDIO_DIR, ROOT_DIR
from . import dsp as D
from .catalog import REQUIRED_SOUNDS, SPECS

MASTER_SEED = 6_12_47
REPORT_DIR = os.path.join(ROOT_DIR, "out", "audio")
BUDGET_BYTES = 20 * 1024 * 1024


def load_recipes():
    """Importa os módulos de receitas (cada um se registra em `catalog.SPECS`)."""
    from . import recipes_ambience, recipes_entity, recipes_foley, recipes_scene  # noqa: F401


def seed_for(name):
    return zlib.crc32(name.encode("utf-8")) ^ MASTER_SEED


def render(name):
    """Sintetiza o som `name` e o normaliza. Devolve (amostras float64, taxa)."""
    load_recipes()
    spec = SPECS[name]
    raw = spec.build(np.random.default_rng(seed_for(name)))
    if spec.loop:
        return D.finalize_loop(raw, spec.peak), spec.sr
    return D.finalize(raw, spec.peak, sr=spec.sr), spec.sr


def wav_path(name, audio_dir=AUDIO_DIR):
    return os.path.join(audio_dir, name + ".wav")


def selected_names(only=None):
    load_recipes()
    names = [n for n in REQUIRED_SOUNDS]
    extra = sorted(set(SPECS) - set(names))
    names += extra
    if only:
        names = [n for n in names if any(n == o or n.startswith(o) for o in only)]
    return names


def render_all(audio_dir=AUDIO_DIR, only=None, log=print):
    """Escreve os WAV e devolve {nome: (amostras, taxa)}."""
    os.makedirs(audio_dir, exist_ok=True)
    rendered = {}
    for name in selected_names(only):
        samples, rate = render(name)
        D.write_wav(wav_path(name, audio_dir), samples, rate)
        rendered[name] = (samples, rate)
    log(f"{len(rendered)} sons em {audio_dir} ({total_bytes(audio_dir) / 1e6:.2f} MB)")
    return rendered


def total_bytes(audio_dir=AUDIO_DIR):
    return sum(os.path.getsize(os.path.join(audio_dir, f)) for f in os.listdir(audio_dir) if f.endswith(".wav"))


def missing_files(audio_dir=AUDIO_DIR):
    return [n for n in REQUIRED_SOUNDS if not os.path.isfile(wav_path(n, audio_dir))]


def ensure_all(audio_dir=AUDIO_DIR, log=print):
    """Gera só o que falta (usado por `audio.build`)."""
    absent = missing_files(audio_dir)
    if absent:
        log(f"gerando {len(absent)} sons ausentes")
        render_all(audio_dir, only=absent, log=log)
    return absent


def manifest_entries(audio_dir=AUDIO_DIR):
    """Lista {name, seconds, rate, loop, bytes} lendo só o cabeçalho de cada WAV."""
    import wave
    from .catalog import loop_names
    load_recipes()
    loops = set(loop_names())
    entries = []
    for name in REQUIRED_SOUNDS:
        path = wav_path(name, audio_dir)
        with wave.open(path, "rb") as fh:
            frames, rate = fh.getnframes(), fh.getframerate()
        entries.append({"name": name, "seconds": round(frames / rate, 3), "rate": rate,
                        "loop": name in loops, "bytes": os.path.getsize(path)})
    return entries


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------
def write_report(rendered, report_dir=REPORT_DIR, sheet_size=5, log=print):
    """Métricas por som em texto e folhas de espectrogramas em PNG."""
    from . import analysis
    from .catalog import SPECS as specs
    os.makedirs(report_dir, exist_ok=True)
    lines = [f"{'som':<20}{'dur(s)':>7}{'kHz':>6}{'pico':>6}{'rms dB':>8}{'zcr/s':>8}{'centroide':>10}{'ataque ms':>10}  loop"]
    for name, (x, sr) in rendered.items():
        s = analysis.describe(x, sr, specs[name].loop)
        seam = f"jump={s['jump_ratio']:.2f} bloco={s['block_diff']:.2f}" if specs[name].loop else ""
        lines.append(f"{name:<20}{s['seconds']:>7.2f}{sr / 1000:>6.1f}{s['peak']:>6.2f}{s['rms_db']:>8.1f}"
                     f"{s['zcr_per_s']:>8.0f}{s['centroid_hz']:>10.0f}{s['attack_ms']:>10.1f}  {seam}")
    path = os.path.join(report_dir, "report.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    log("\n".join(lines))
    _write_sheets(rendered, report_dir, sheet_size, analysis, specs, log)
    return path


def _write_sheets(rendered, report_dir, sheet_size, analysis, specs, log):
    groups = {}
    for name in rendered:
        first_of_family = name.rsplit("_", 1)[-1].isdigit() and not name.endswith("_1") and name.rsplit("_", 1)[0] + "_1" in rendered
        if first_of_family:
            continue
        groups.setdefault(specs[name].group or "misc", []).append(name)
    for group, names in groups.items():
        for k in range(0, len(names), sheet_size):
            chunk = names[k:k + sheet_size]
            entries = [(n, *rendered[n]) for n in chunk]
            analysis.write_sheet(os.path.join(report_dir, f"sheet_{group}_{k // sheet_size + 1}.png"), entries)
    log(f"folhas PNG em {report_dir}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="*", help="nomes ou prefixos a gerar")
    parser.add_argument("--report", action="store_true", help="imprime métricas e escreve PNGs em out/audio/")
    parser.add_argument("--out", default=AUDIO_DIR)
    args = parser.parse_args(argv)
    rendered = render_all(args.out, args.only)
    if args.report:
        write_report(rendered)
    if total_bytes(args.out) > BUDGET_BYTES:
        print("ERRO: passou de 20 MB", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
