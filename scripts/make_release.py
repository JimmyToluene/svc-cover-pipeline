#!/usr/bin/env python3
"""Phase 4 — 出片:静态封面 + 成品音频 + 字幕 → release.mp4(ffmpeg 一条命令)。

默认把 .ass 烧进画面(B 站兼容最稳);--soft 改为 mkv 软字幕(保留样式,体积小,
但 B 站会转码,烧录仍是首选)。

示例:
  python scripts/make_release.py --cover refs/cover.png
  python scripts/make_release.py --cover refs/cover.png --no-subs   # 无字幕版
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from project_paths import add_project_arg, resolve_project


def die(msg):
    print(f"[release] 错误: {msg}", file=sys.stderr)
    sys.exit(1)


def esc_filter_path(p: Path) -> str:
    # ffmpeg filter 参数里的路径转义(':' 和 "'" 是分隔符)
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def audio_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        die(f"ffprobe 读不到音频时长: {path}\n{r.stderr[-500:]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--audio", type=Path, default=None,
                    help="默认 <project>/output/final_mix.wav")
    ap.add_argument("--cover", type=Path, required=True, help="静态封面图(png/jpg)")
    ap.add_argument("--subs", type=Path, default=None,
                    help="默认 <project>/output/subs.ass")
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--soft", action="store_true", help="软字幕 mkv(默认烧录 mp4)")
    ap.add_argument("--out", type=Path, default=None,
                    help="默认 <project>/output/release.mp4(--soft 时 .mkv)")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--fps", type=int, default=24)
    args = ap.parse_args()
    proj = resolve_project(args)
    args.audio = args.audio or proj / "output" / "final_mix.wav"
    args.subs = args.subs or proj / "output" / "subs.ass"

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            die(f"找不到 {tool}(sovits env 里有:PATH=~/miniforge3/envs/sovits/bin:$PATH)")
    args.audio, args.cover, args.subs = (p.expanduser() for p in
                                         (args.audio, args.cover, args.subs))
    for p in (args.audio, args.cover):
        if not p.is_file():
            die(f"文件不存在: {p}")
    use_subs = not args.no_subs
    if use_subs and not args.subs.is_file():
        die(f"字幕不存在: {args.subs}(先跑 make_subs.py,或加 --no-subs)")

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
    # 用 -t 按音频时长硬截断:-shortest 会因混流缓冲让静止画面拖过音频结尾几秒,
    # 而修它的 -fflags +shortest 在 ffmpeg 8 上已不可用
    dur = audio_duration(args.audio)
    cmd += ["-t", f"{dur:.3f}", "-movflags", "+faststart", str(out)]

    print("[release]", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        die(f"ffmpeg 失败 (exit={r.returncode})")
    size_mb = out.stat().st_size / 1e6
    print(f"[release] 完成 → {out}({size_mb:.1f} MB)")
    print("[release] 发布前核对:B 站 AI 生成内容标注 + 原填词作者署名(不可协商)")


if __name__ == "__main__":
    main()
