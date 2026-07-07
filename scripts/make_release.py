#!/usr/bin/env python3
"""Phase 4 — release: static cover + final audio + subtitles → release.mp4 (single ffmpeg command).

By default the .ass subtitles are burned into the video (most reliable for
Bilibili); --soft switches to mkv soft subtitles (keeps the styling, smaller
file, but Bilibili re-encodes anyway, so burning in is still the first choice).

Examples:
  python scripts/make_release.py --cover refs/cover.png
  python scripts/make_release.py --cover refs/cover.png --no-subs   # no-subtitles version
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from project_paths import add_project_arg, resolve_project


def die(msg):
    print(f"[release] error: {msg}", file=sys.stderr)
    sys.exit(1)


def esc_filter_path(p: Path) -> str:
    # escape the path for ffmpeg filter arguments (':' and "'" are delimiters)
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def audio_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        die(f"ffprobe could not read the audio duration: {path}\n{r.stderr[-500:]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--audio", type=Path, default=None,
                    help="default: <project>/output/final_mix.wav")
    ap.add_argument("--cover", type=Path, required=True, help="static cover image (png/jpg)")
    ap.add_argument("--subs", type=Path, default=None,
                    help="default: <project>/output/subs.ass")
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--soft", action="store_true",
                    help="soft subtitles in mkv (default: burn into mp4)")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <project>/output/release.mp4 (.mkv with --soft)")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--fps", type=int, default=24)
    args = ap.parse_args()
    proj = resolve_project(args)
    args.audio = args.audio or proj / "output" / "final_mix.wav"
    args.subs = args.subs or proj / "output" / "subs.ass"

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            die(f"{tool} not found (the sovits env has it: PATH=~/miniforge3/envs/sovits/bin:$PATH)")
    args.audio, args.cover, args.subs = (p.expanduser() for p in
                                         (args.audio, args.cover, args.subs))
    for p in (args.audio, args.cover):
        if not p.is_file():
            die(f"file not found: {p}")
    use_subs = not args.no_subs
    if use_subs and not args.subs.is_file():
        die(f"subtitles not found: {args.subs} (run make_subs.py first, or pass --no-subs)")

    out = args.out or (proj / "output" / ("release.mkv" if args.soft else "release.mp4"))
    out.parent.mkdir(parents=True, exist_ok=True)

    vf = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
          "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black")
    if use_subs and not args.soft:
        vf += f",subtitles=filename='{esc_filter_path(args.subs.resolve())}'"

    cmd = ["ffmpeg", "-y",
           "-loop", "1", "-framerate", str(args.fps), "-i", str(args.cover),
           "-i", str(args.audio)]
    if use_subs and args.soft:
        cmd += ["-i", str(args.subs)]
    cmd += ["-vf", vf,
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "medium",
            "-crf", str(args.crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "320k"]
    if use_subs and args.soft:
        cmd += ["-c:s", "ass", "-map", "0:v", "-map", "1:a", "-map", "2:s"]
    # Hard-cut with -t to the audio duration: -shortest lets the still image run
    # a few seconds past the end of the audio due to muxer buffering, and the
    # fix for that (-fflags +shortest) is no longer available in ffmpeg 8
    dur = audio_duration(args.audio)
    cmd += ["-t", f"{dur:.3f}", "-movflags", "+faststart", str(out)]

    print("[release]", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        die(f"ffmpeg failed (exit={r.returncode})")
    size_mb = out.stat().st_size / 1e6
    print(f"[release] done → {out} ({size_mb:.1f} MB)")
    print("[release] before publishing, verify: Bilibili AI-generated-content label "
          "+ credit to the original lyricist (non-negotiable)")


if __name__ == "__main__":
    main()
