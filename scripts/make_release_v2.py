#!/usr/bin/env python3
"""Phase 4 — release v2: cover intro + content-image background + animated waveform + bilingual subtitles → mp4.

Visual structure (1920x1080 @30fps):
  0s ── cover (--cover, includes title text) ── intro-end ── 1.5s fade-out ──> content image (--content)
  Throughout: a glowing waveform above the bottom edge that moves with the audio
  (showwaves cline, blue/white palette to match the nighttime art); subtitles
  (output/subs.ass, large Japanese + small Chinese) are burned in at the very
  bottom, clear of the waveform.
  The cover is also embedded as the mp4 thumbnail (attached_pic; the Bilibili
  upload cover still has to be uploaded separately).

Differences from v1 (make_release.py, single static image): two-image structure /
waveform animation / embedded thumbnail.

Example:
  python3 scripts/make_release_v2.py \
      --cover nianzhangshi/refs/Azuma_Cover_v2.png \
      --content nianzhangshi/refs/Azuma_Content_v2.png
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from project_paths import add_project_arg, resolve_project


def die(msg):
    print(f"[release2] error: {msg}", file=sys.stderr)
    sys.exit(1)


def esc_filter_path(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def ffprobe_field(path: Path, entries: str) -> str:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries,
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return r.stdout.strip()


def clean_env() -> dict:
    """PyCharm Remote Dev points FONTCONFIG_PATH at a private directory that only
    has Western fonts, so libass can't find Noto CJK and renders tofu — drop the
    vars when they point into the JetBrains cache."""
    env = os.environ.copy()
    for var in ("FONTCONFIG_PATH", "FONTCONFIG_FILE"):
        if "JetBrains" in env.get(var, ""):
            env.pop(var)
    return env


def first_sub_start(subs: Path) -> float:
    """Earliest Dialogue start time (seconds) in subs.ass; used to auto-set the cover duration."""
    best = None
    for line in subs.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        h, m, s = line.split(",")[1].split(":")
        t = int(h) * 3600 + int(m) * 60 + float(s)
        best = t if best is None else min(best, t)
    if best is None:
        die(f"no Dialogue lines in {subs}")
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--audio", type=Path, default=None,
                    help="default: <project>/output/final_mix.wav")
    ap.add_argument("--cover", type=Path, required=True,
                    help="intro cover image (includes title text; doubles as the mp4 thumbnail)")
    ap.add_argument("--content", type=Path, required=True, help="main background image")
    ap.add_argument("--subs", type=Path, default=None,
                    help="default: <project>/output/subs.ass")
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <project>/output/release_v2.mp4")
    ap.add_argument("--intro-end", type=float, default=None,
                    help="when the cover starts fading out (seconds); default = 2s before the first subtitle (clamped to 4-20s)")
    ap.add_argument("--fade", type=float, default=1.5, help="cover→content fade-out duration")
    ap.add_argument("--wave-height", type=int, default=240)
    ap.add_argument("--wave-y", type=int, default=650,
                    help="top edge y of the waveform band (default 650: band spans 650-890, subtitle area starts ~900)")
    ap.add_argument("--no-wave", action="store_true")
    ap.add_argument("--wave-alpha", type=float, default=0.75,
                    help="opacity of the main waveform line, 0-1; 1.0 recommended on bright backgrounds")
    ap.add_argument("--wave-glow-alpha", type=float, default=0.85,
                    help="waveform glow opacity, 0-1")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()
    proj = resolve_project(args)
    args.audio = args.audio or proj / "output" / "final_mix.wav"
    args.subs = args.subs or proj / "output" / "subs.ass"
    args.out = args.out or proj / "output" / "release_v2.mp4"

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            die(f"{tool} not found")
    for p in (args.audio, args.cover, args.content):
        if not p.is_file():
            die(f"file not found: {p}")
    use_subs = not args.no_subs
    if use_subs and not args.subs.is_file():
        die(f"subtitles not found: {args.subs} (run auto_line_times.py + make_subs.py first, "
            "or pass --no-subs)")

    env = clean_env()
    if use_subs:
        r = subprocess.run(["fc-match", "Noto Sans CJK JP"], capture_output=True,
                           text=True, env=env)
        if "Noto Sans CJK" not in r.stdout:
            print(f"[release2] ⚠ fc-match did not resolve Noto CJK ({r.stdout.strip()}); "
                  "subtitles may render as tofu", file=sys.stderr)

    try:
        dur = float(ffprobe_field(args.audio, "format=duration"))
    except ValueError:
        die(f"ffprobe could not read the audio duration: {args.audio}")

    intro = args.intro_end
    if intro is None:
        intro = min(max(first_sub_start(args.subs) - 2.0, 4.0), 20.0) if use_subs else 8.0
    fps = args.fps

    # Background: content image underneath, cover overlaid on top with an alpha
    # fade-out (more robust than xfade for looped-image inputs)
    scale = ("scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,"
             "crop=1920:1080,setsar=1,fps={fps}".format(fps=fps))
    parts = [
        f"[0:v]{scale}[bg]",
        f"[1:v]{scale},format=yuva420p,"
        f"fade=t=out:st={intro:.2f}:d={args.fade}:alpha=1[cov]",
        "[bg][cov]overlay=x=0:y=0:shortest=0[base]",
    ]
    last = "base"
    if not args.no_wave:
        wh = args.wave_height
        # Waveform: mono cline waveform, split into two stacked layers:
        # a blurred blue glow + a crisp bright-white main line
        parts += [
            "[2:a]aformat=channel_layouts=mono,"
            f"showwaves=s=1920x{wh}:mode=cline:rate={fps}:scale=sqrt:"
            "colors=0xFFFFFF[wv]",
            "[wv]split[wv1][wv2]",
            "[wv1]format=rgba,colorchannelmixer=rr=0.45:gg=0.58:bb=1.0:"
            f"aa={args.wave_glow_alpha},gblur=sigma=14[wglow]",
            "[wv2]format=rgba,colorchannelmixer=rr=0.88:gg=0.93:bb=1.0:"
            f"aa={args.wave_alpha}[wcrisp]",
            f"[{last}][wglow]overlay=x=0:y={args.wave_y}[b1]",
            f"[b1][wcrisp]overlay=x=0:y={args.wave_y}[b2]",
        ]
        last = "b2"
    if use_subs:
        parts.append(f"[{last}]subtitles=filename="
                     f"'{esc_filter_path(args.subs.resolve())}'[vout]")
        last = "vout"
    else:
        parts.append(f"[{last}]null[vout]")
        last = "vout"

    cmd = ["ffmpeg", "-y",
           "-loop", "1", "-framerate", str(fps), "-i", str(args.content),
           "-loop", "1", "-framerate", str(fps), "-i", str(args.cover),
           "-i", str(args.audio),
           "-i", str(args.cover),                      # thumbnail (not looped, single frame)
           "-filter_complex", ";".join(parts),
           "-map", f"[{last}]", "-map", "2:a", "-map", "3:v",
           "-c:v:0", "libx264", "-preset", "medium", "-crf", str(args.crf),
           "-pix_fmt:v:0", "yuv420p",
           "-c:a", "aac", "-b:a", "320k",
           "-c:v:1", "png", "-disposition:v:1", "attached_pic",
           # hard-cut with -t to the audio duration (looped image inputs are
           # infinite streams, so -shortest behaves unreliably)
           "-t", f"{dur:.3f}", "-movflags", "+faststart", str(args.out)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[release2] cover 0-{intro:.1f}s → {args.fade}s fade-out → content image; "
          f"duration {dur:.1f}s")
    print("[release2]", " ".join(cmd))
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        die(f"ffmpeg failed (exit={r.returncode})")
    print(f"[release2] done → {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")
    print("[release2] before publishing, verify: Bilibili AI-generated-content label "
          "+ credit to the original lyricist (non-negotiable)")


if __name__ == "__main__":
    main()
