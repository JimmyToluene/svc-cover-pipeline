#!/usr/bin/env python3
"""Phase 4 — instrumental separation fallback (audio-separator wrapper).

Instrumental sourcing priority (see CLAUDE.md): (1) official instrumental >
(2) separate from the reference cover version (this script's default; when its
vocals are an SVC dry vocal plus reverb, separation is easier than for a real
human performance) > (3) separate from the original recording.

Uses BS-Roformer by default (currently the highest-SDR general-purpose
separation model). Optionally run DeEcho-DeReverb on the instrumental
afterwards to strip residual vocal reverb (--dereverb, for when you can hear a
"vocal tail" in the instrumental).

Dependencies: audio-separator[gpu] (install it in a separate phase4 env; its
librosa requirement conflicts with the sovits env). Model weights are
downloaded automatically to --model-dir on first run.

Default input: the single audio file (mp3/wav/flac/m4a) under <project>/refs/;
use --input when there is more than one.

Examples:
  python scripts/separate.py                        # reference version → <project>/inst/
  python scripts/separate.py --dereverb             # when the instrumental has residual vocal reverb
  python scripts/separate.py --input original.mp3   # fallback of the fallback
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

from project_paths import add_project_arg, resolve_project

SEP_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
DEREVERB_MODEL = "UVR-DeEcho-DeReverb.pth"


def die(msg):
    print(f"[separate] error: {msg}", file=sys.stderr)
    sys.exit(1)


def pick(paths, *keywords, strip_prefix=""):
    """Pick a file from the output list by keywords (case-insensitive).

    strip_prefix removes the input filename prefix from the output name — if
    the input itself is called xxx_instrumental.mp3, the keywords would match
    spuriously without stripping it."""
    for p in paths:
        name = Path(p).name
        if strip_prefix and name.startswith(strip_prefix):
            name = name[len(strip_prefix):]
        name = name.lower()
        if all(k.lower() in name for k in keywords):
            return Path(p)
    return None


def default_input(proj: Path) -> Path:
    refs = proj / "refs"
    auds = sorted(p for p in (refs.iterdir() if refs.is_dir() else [])
                  if p.suffix.lower() in (".mp3", ".wav", ".flac", ".m4a"))
    if len(auds) == 1:
        return auds[0]
    if not auds:
        die(f"no audio files under {refs}; specify the separation input with --input")
    die(f"multiple audio files under {refs}: {[p.name for p in auds]}; specify one with --input")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--input", type=Path, default=None,
                    help="default: the single audio file under <project>/refs/")
    ap.add_argument("--outdir", type=Path, default=None,
                    help="default: <project>/inst")
    ap.add_argument("--model", default=SEP_MODEL)
    ap.add_argument("--dereverb", action="store_true",
                    help="run DeEcho-DeReverb on the separated instrumental to strip residual vocal reverb")
    ap.add_argument("--model-dir", type=Path,
                    default=Path.home() / ".cache" / "audio-separator-models",
                    help="model weight cache directory (auto-downloaded on first run)")
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    args = ap.parse_args()
    proj = resolve_project(args)
    args.outdir = args.outdir or proj / "inst"

    args.input = (args.input or default_input(proj)).expanduser()
    if not args.input.is_file():
        die(f"input not found: {args.input}")
    if args.device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""  # audio-separator has no explicit switch; this is how we disable the GPU

    try:
        from audio_separator.separator import Separator
    except ImportError:
        die("audio-separator missing; in the phase4 env run: pip install 'audio-separator[gpu]'")

    args.outdir.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem

    sep = Separator(output_dir=str(args.outdir),
                    model_file_dir=str(args.model_dir),
                    output_format="wav")
    print(f"[separate] loading separation model {args.model} (downloads automatically on first run)")
    sep.load_model(model_filename=args.model)
    print(f"[separate] separating {args.input.name} ...")
    outputs = [args.outdir / Path(p).name for p in sep.separate(str(args.input))]
    print(f"[separate] separation outputs: {[p.name for p in outputs]}")

    inst = (pick(outputs, "instrumental", strip_prefix=stem)
            or pick(outputs, "no vocals", strip_prefix=stem))
    vocals = pick(outputs, "(vocals", strip_prefix=stem)
    if inst is None:
        die(f"no instrumental output found; actual outputs: {[p.name for p in outputs]}")

    inst_final = args.outdir / f"inst_from_{stem}.wav"
    shutil.move(str(inst), inst_final)
    if vocals:
        # keep the separated vocals as a timing reference (for subtitle alignment);
        # they don't go into the mix
        shutil.move(str(vocals), args.outdir / f"vocals_ref_{stem}.wav")

    if args.dereverb:
        print(f"[separate] dereverb second pass: {DEREVERB_MODEL}")
        sep.load_model(model_filename=DEREVERB_MODEL)
        outs2 = [args.outdir / Path(p).name for p in sep.separate(str(inst_final))]
        print(f"[separate] dereverb outputs: {[p.name for p in outs2]}")
        dry = (pick(outs2, "no reverb", strip_prefix=inst_final.stem)
               or pick(outs2, "noreverb", strip_prefix=inst_final.stem))
        if dry is None:
            die(f"no 'No Reverb' output found; actual outputs: {[p.name for p in outs2]}")
        dry_final = args.outdir / f"inst_from_{stem}_dereverb.wav"
        shutil.move(str(dry), dry_final)
        for p in outs2:  # discard the reverb-only leftovers
            if p.exists() and p != dry:
                p.unlink()
        print(f"[separate] done → {dry_final} (A/B against {inst_final.name} and keep one)")
    else:
        print(f"[separate] done → {inst_final}")
        print("[separate] if you can hear residual vocal reverb in the instrumental, rerun with --dereverb")


if __name__ == "__main__":
    main()
