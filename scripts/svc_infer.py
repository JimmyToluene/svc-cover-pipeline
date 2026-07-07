#!/usr/bin/env python3
"""Phase 3 — so-vits-svc 4.1 parameter grid batch runner.

Wraps inference_main.py from so-vits-svc 4.1-Stable:
auto-detects the model under <project>/models/ (the single subdirectory
containing config.json, or pass --model-dir explicitly), runs inference over
the transpose × cluster_ratio × f0_predictor × (shallow diffusion) grid,
collects the results into <project>/vocal/svc_out/ (parameters encoded in
the filenames), and creates/appends the blind-listening comparison table
<project>/docs/svc_grid.md.

Dependencies: standard library only + system ffmpeg (to downmix the input
to mono). so-vits-svc's own dependencies belong to its checkout's
environment; point --python at that environment's interpreter.

Example:
  python scripts/svc_infer.py --svc-repo ~/so-vits-svc -t 0 12 --dry-run
"""

import argparse
import datetime
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from project_paths import add_project_arg, resolve_project


def die(msg):
    print(f"[svc_infer] error: {msg}", file=sys.stderr)
    sys.exit(1)


def default_model_dir(proj: Path) -> Path:
    """Use <project>/models itself if it is a model dir; otherwise require exactly one subdirectory containing config.json."""
    root = proj / "models"
    if (root / "config.json").is_file():
        return root
    cands = (sorted(d for d in root.iterdir()
                    if d.is_dir() and (d / "config.json").is_file())
             if root.is_dir() else [])
    if len(cands) == 1:
        return cands[0]
    if not cands:
        die(f"no model directory found under {root} (must contain config.json); use --model-dir")
    die(f"multiple model directories under {root}: {[d.name for d in cands]}; pick one with --model-dir")


def detect_model(model_dir: Path):
    """Return a dict: gen/config are required; cluster/feature_index/diff_model/diff_config are optional."""
    if not model_dir.is_dir():
        die(f"model directory does not exist: {model_dir}")

    gens = sorted(model_dir.glob("G_*.pth"))
    if not gens:
        gens = [p for p in model_dir.glob("*.pth") if not p.name.startswith("D_")]
    if not gens:
        die(f"no generator weights (G_*.pth) in {model_dir}")
    # With multiple checkpoints, pick the highest step count; use the last number
    # in the name so sample rates / version numbers don't throw us off
    def step(p):
        m = re.findall(r"\d+", p.stem)
        return int(m[-1]) if m else -1
    gen = max(gens, key=step)

    config = model_dir / "config.json"
    if not config.is_file():
        cands = list(model_dir.glob("*.json"))
        if len(cands) == 1:
            config = cands[0]
        else:
            die(f"no config.json in {model_dir}")

    feature_index = next(iter(model_dir.glob("*.pkl")), None)
    cluster = next(iter(model_dir.glob("kmeans*.pt")), None)

    diff_model = diff_config = None
    for d, pat in ((model_dir / "diffusion", "*.pt"), (model_dir, "model_*.pt")):
        # Use a narrow pattern in the root dir so kmeans*.pt isn't mistaken for a diffusion model
        pts = [p for p in d.glob(pat) if not p.name.startswith("kmeans")] if d.is_dir() else []
        yamls = list(d.glob("*.yaml")) if d.is_dir() else []
        if pts and yamls:
            diff_model, diff_config = max(pts, key=step), yamls[0]
            break

    return {
        "gen": gen, "config": config,
        "cluster": cluster, "feature_index": feature_index,
        "diff_model": diff_model, "diff_config": diff_config,
    }


def read_config(config_path: Path):
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    spk = list(cfg.get("spk", {}).keys())
    if not spk:
        die(f"no spk table in {config_path}; cannot determine the -s speaker name")
    encoder = cfg.get("model", {}).get("speech_encoder")
    if encoder is None:
        # A missing speech_encoder field means a 4.0-era model; it must be added
        # before running 4.1 inference
        print("[svc_infer] warning: config.json is missing model.speech_encoder — looks like a 4.0 model. "
              'Add "speech_encoder": "vec256l9" to the model block (when ssl_dim=256) before running.',
              file=sys.stderr)
        encoder = "vec256l9?"
    sr = cfg.get("data", {}).get("sampling_rate", 44100)
    return spk, encoder, sr


def prepare_input(src: Path, svc_repo: Path, sr: int, dry: bool) -> str:
    """Downmix to mono + resample to the model's sample rate, into the svc repo's raw/. Returns clean_name."""
    raw_dir = svc_repo / "raw"
    clean_name = src.stem + ".wav"
    cmd = ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", str(sr),
           "-acodec", "pcm_s16le", str(raw_dir / clean_name)]
    print("[svc_infer] input preprocessing:", " ".join(cmd))
    if not dry:
        if shutil.which("ffmpeg") is None:
            die("ffmpeg not found, please install it (input must be downmixed to mono: sovits only takes the left channel of a stereo wav)")
        raw_dir.mkdir(exist_ok=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            die(f"ffmpeg failed:\n{r.stderr[-2000:]}")
    return clean_name


def out_name(stem, f0p, t, cr, use_fr, shd, args):
    parts = [stem, f"f0{f0p}", f"t{t:+d}"]
    if cr > 0:
        parts.append(f"cr{cr}" + ("fr" if use_fr else "km"))
    if shd:
        parts.append(f"shd{args.k_step}")
    # Encode non-default secondary parameters into the filename too,
    # so two batch runs don't overwrite each other
    if args.noice_scale != 0.4:
        parts.append(f"ns{args.noice_scale:g}")
    if args.slice_db != -50:
        parts.append(f"sd{args.slice_db}")
    if args.clip:
        parts.append(f"cl{args.clip:g}")
    return "_".join(parts) + ".wav"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--svc-repo", required=True, type=Path,
                    help="path to the so-vits-svc 4.1-Stable checkout")
    ap.add_argument("--input", type=Path, default=None,
                    help="dry vocal wav exported from SynthV, default <project>/vocal/synthv_source.wav")
    ap.add_argument("--model-dir", type=Path, default=None,
                    help="default: auto-detect the single model directory under <project>/models/")
    ap.add_argument("--speaker", default=None,
                    help="speaker name from the config.json spk table, defaults to the first one")
    ap.add_argument("-t", "--transpose", type=int, nargs="+", default=[0],
                    help="semitone transpose grid, e.g.: -t 0 12 -12")
    ap.add_argument("--cr", type=float, nargs="+", default=None,
                    help="cluster/feature-retrieval ratio grid; default: "
                         "{0, 0.3, 0.5} when the model ships kmeans/index, else {0}")
    ap.add_argument("--f0", nargs="+", default=["rmvpe"],
                    choices=["crepe", "pm", "dio", "harvest", "rmvpe", "fcpe"],
                    help="f0 predictor grid (note the sovits CLI itself defaults to pm; here the default is rmvpe)")
    ap.add_argument("--shd", choices=["auto", "off", "only"], default="auto",
                    help="shallow diffusion: auto=also run a shallow-diffusion pass per parameter combo "
                         "when the model has diffusion; only=run only the shallow-diffusion passes")
    ap.add_argument("--k-step", type=int, default=100, help="shallow diffusion steps")
    ap.add_argument("--noice-scale", type=float, default=0.4)
    ap.add_argument("--slice-db", type=int, default=-50,
                    help="slicing threshold; use -50 to keep breaths in dry vocals (per the sovits README)")
    ap.add_argument("--clip", type=float, default=0, help="forced slice length in seconds, 0=auto")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--python", default=sys.executable,
                    help="interpreter used to run inference_main.py (the sovits environment)")
    ap.add_argument("--dry-run", action="store_true", help="print commands without executing them")
    args = ap.parse_args()
    proj = resolve_project(args)
    out_dir = proj / "vocal" / "svc_out"
    grid_md = proj / "docs" / "svc_grid.md"

    svc_repo = args.svc_repo.expanduser().resolve()
    args.input = (args.input or proj / "vocal" / "synthv_source.wav").expanduser()
    if not (svc_repo / "inference_main.py").is_file():
        die(f"{svc_repo} is not a so-vits-svc checkout (inference_main.py missing)")
    if not args.input.is_file():
        die(f"input not found: {args.input}")
    if not args.dry_run and shutil.which(args.python) is None \
            and not Path(args.python).expanduser().is_file():
        die(f"--python interpreter not found: {args.python}")

    model_dir = (args.model_dir.expanduser().resolve() if args.model_dir
                 else default_model_dir(proj))
    m = detect_model(model_dir)
    speakers, encoder, sr = read_config(m["config"])
    speaker = args.speaker or speakers[0]
    if speaker not in speakers:
        die(f"speaker {speaker!r} is not in the config.json spk table, choices: {speakers}")

    cluster_asset = m["feature_index"] or m["cluster"]
    use_fr = m["feature_index"] is not None
    ratios = args.cr if args.cr is not None else ([0.0, 0.3, 0.5] if cluster_asset else [0.0])
    dropped = [r for r in ratios if r > 0 and not cluster_asset]
    if dropped:
        print(f"[svc_infer] model has no kmeans/feature index, skipping cr={dropped}", file=sys.stderr)
        ratios = [r for r in ratios if r == 0 or cluster_asset] or [0.0]

    has_diff = m["diff_model"] is not None
    if args.shd != "off" and not has_diff:
        if args.shd == "only":
            die("--shd only, but there is no diffusion model (model_*.pt + *.yaml) in the model directory")
        print("[svc_infer] model has no diffusion, running plain sovits passes only", file=sys.stderr)
    shd_variants = {"off": [False], "only": [True],
                    "auto": [False, True] if has_diff else [False]}[args.shd]

    # The shallow-diffusion vocoder path in the yaml is cwd-relative; without a
    # pre-check the run would only blow up halfway through
    if True in shd_variants:
        mt = re.search(r"^\s*ckpt:\s*(\S+)", m["diff_config"].read_text(encoding="utf-8"),
                       re.M)
        voc_rel = mt.group(1) if mt else "pretrain/nsf_hifigan/model"
        if not (svc_repo / voc_rel).is_file():
            msg = (f"shallow-diffusion vocoder missing: {svc_repo / voc_rel}"
                   f" (diffusion.yaml vocoder.ckpt={voc_rel}, see docs/svc_model_notes.md)")
            if args.dry_run:
                print(f"[svc_infer] warning: {msg}", file=sys.stderr)
            elif args.shd == "only":
                die(msg)
            else:
                print(f"[svc_infer] warning: {msg}, skipping shallow-diffusion passes", file=sys.stderr)
                shd_variants = [False]

    print(f"[svc_infer] model: {m['gen'].name}  encoder={encoder}  sr={sr}  "
          f"speaker={speaker}")
    print(f"[svc_infer] retrieval asset: {cluster_asset.name if cluster_asset else 'none'}"
          f"{' (feature retrieval)' if use_fr else ' (cluster)' if cluster_asset else ''}  "
          f"diffusion: {m['diff_model'].name if has_diff else 'none'}")

    clean_name = prepare_input(args.input.resolve(), svc_repo, sr, args.dry_run)
    stem = args.input.stem

    # The whisper-ppg encoder fails at inference without -cl 25 -lg 1
    # (special case in the sovits README)
    clip, lg = args.clip, 0.0
    if str(encoder).startswith("whisper"):
        clip, lg = 25, 1
        print("[svc_infer] whisper-ppg encoder: forcing -cl 25 -lg 1", file=sys.stderr)

    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir = svc_repo / "results"
    rows, failures = [], 0

    interrupted = False
    for f0p, t, cr, shd in itertools.product(args.f0, args.transpose,
                                             ratios, shd_variants):
        cmd = [args.python, "inference_main.py",
               "-m", str(m["gen"]), "-c", str(m["config"]),
               "-n", clean_name, "-t", str(t), "-s", speaker,
               "-f0p", f0p, "-wf", "wav", "-d", args.device,
               "-ns", str(args.noice_scale),
               "-sd", str(args.slice_db),
               "-cl", str(clip), "-lg", str(lg)]
        if cr > 0:
            cmd += ["-cr", str(cr), "-cm", str(cluster_asset)]
            if use_fr:
                cmd += ["-fr"]
        if shd:
            cmd += ["-shd", "-dm", str(m["diff_model"]),
                    "-dc", str(m["diff_config"]),
                    "-ks", str(args.k_step)]

        dst = out_dir / out_name(stem, f0p, t, cr, use_fr, shd, args)
        print(f"\n[svc_infer] → {dst.name}\n  " + " ".join(cmd))
        if args.dry_run:
            continue

        try:
            # Track mtimes rather than the file set: on a same-parameter re-run
            # sovits overwrites the identically-named output, so looking only at
            # "new files" would misread a successful re-run as a failure
            before = ({p: p.stat().st_mtime for p in results_dir.glob("*.wav")}
                      if results_dir.is_dir() else {})
            t0 = time.time()
            # torch>=2.6 defaults to weights_only=True, which refuses to load the
            # custom classes inside 2023-era checkpoints (fairseq/ContentVec etc.);
            # these files are model assets the user has already chosen to trust
            r = subprocess.run(cmd, cwd=svc_repo,
                               env={**os.environ,
                                    "TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD": "1"})
            dur = time.time() - t0
            after = {p: p.stat().st_mtime for p in results_dir.glob("*.wav")}
            new = sorted((p for p, mt in after.items() if before.get(p) != mt),
                         key=after.get)
            if r.returncode != 0 or not new:
                print(f"[svc_infer] failed (exit={r.returncode}, "
                      f"{len(new)} new outputs)", file=sys.stderr)
                failures += 1
                rows.append((dst.name, f0p, t, cr, shd, f"failed exit={r.returncode}"))
                continue
            if len(new) > 1:
                print(f"[svc_infer] warning: {len(new)} new wavs produced, "
                      f"collecting only the newest; the rest stay in {results_dir}", file=sys.stderr)
            shutil.move(str(new[-1]), dst)
            rows.append((dst.name, f0p, t, cr, shd, f"{dur:.0f}s"))
        except KeyboardInterrupt:  # on Ctrl-C keep the finished rows and still write the comparison table
            print("\n[svc_infer] interrupted: completed combos are still written to the comparison table", file=sys.stderr)
            failures += 1
            rows.append((dst.name, f0p, t, cr, shd, "interrupted"))
            interrupted = True
            break
        except Exception as e:  # one failed combo shouldn't take down the whole grid; leave a trace in the table
            print(f"[svc_infer] exception: {e}", file=sys.stderr)
            failures += 1
            rows.append((dst.name, f0p, t, cr, shd, f"error {type(e).__name__}"))

    if args.dry_run:
        print("\n[svc_infer] dry run finished, no inference executed")
        return

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    if not grid_md.exists():
        lines += ["# Phase 3 — so-vits-svc parameter grid blind-listening comparison\n",
                  "The notes column is filled in by the user after blind listening; selected.wav = the final pick.\n"]
    lines += [f"\n## Batch {stamp} — input `{args.input.name}`, "
              f"model `{m['gen'].name}`, speaker `{speaker}`\n",
              "| File (vocal/svc_out/) | f0 | trans | cr | shallow diff | time/status | listening notes |",
              "|---|---|---|---|---|---|---|"]
    for name, f0p, t, cr, shd, status in rows:
        cell = name.replace("|", "\\|")
        lines.append(f"| `{cell}` | {f0p} | {t:+d} | {cr} | "
                     f"{'k=' + str(args.k_step) if shd else '—'} | {status} | |")
    with grid_md.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    ok = len(rows) - failures
    print(f"\n[svc_infer] done: {ok}/{len(rows)} succeeded → {out_dir}")
    print(f"[svc_infer] comparison table appended: {grid_md}")
    if interrupted:
        sys.exit(130)
    if failures:
        sys.exit(2)


if __name__ == "__main__":
    main()
