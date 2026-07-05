#!/usr/bin/env python3
"""Phase 4 — 出片 v2:封面开场 + 内容图背景 + 动态声波 + 双语字幕 → mp4。

视觉结构(1920x1080 @30fps):
  0s ──封面(--cover,含标题字)── intro-end ──1.5s 淡出──> 内容图(--content)
  全程:底部上方一条随音频起伏的发光声波(showwaves cline,蓝白配色贴画面夜色),
  字幕(output/subs.ass,日大字+中小字)烧录在最底部,与声波不重叠。
  封面另嵌为 mp4 缩略图(attached_pic;B 站投稿封面仍需单独传图)。

对 v1(make_release.py 静态单图)的差异:双图结构 / 声波动画 / 缩略图内嵌。

示例:
  python3 scripts/make_release_v2.py \
      --audio output/preview_mix.wav --out output/preview_v2.mp4 \
      --cover refs/Azuma_Backgroud.png --content refs/Azuma_Content.png
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def die(msg):
    print(f"[release2] 错误: {msg}", file=sys.stderr)
    sys.exit(1)


def esc_filter_path(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def ffprobe_field(path: Path, entries: str) -> str:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries,
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return r.stdout.strip()


def clean_env() -> dict:
    """PyCharm Remote Dev 会把 FONTCONFIG_PATH 指到只有西文字体的私有目录,
    libass 因此找不到 Noto CJK 而渲染豆腐块 —— 指向 JetBrains 缓存时剔除。"""
    env = os.environ.copy()
    for var in ("FONTCONFIG_PATH", "FONTCONFIG_FILE"):
        if "JetBrains" in env.get(var, ""):
            env.pop(var)
    return env


def first_sub_start(subs: Path) -> float:
    """subs.ass 里最早的 Dialogue 开始时间(秒),拿来自动定封面时长。"""
    best = None
    for line in subs.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        h, m, s = line.split(",")[1].split(":")
        t = int(h) * 3600 + int(m) * 60 + float(s)
        best = t if best is None else min(best, t)
    if best is None:
        die(f"{subs} 里没有 Dialogue 行")
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", type=Path, default=PROJECT / "output" / "final_mix.wav")
    ap.add_argument("--cover", type=Path, default=PROJECT / "refs" / "Azuma_Backgroud.png",
                    help="开场封面图(含标题字,兼作 mp4 缩略图)")
    ap.add_argument("--content", type=Path, default=PROJECT / "refs" / "Azuma_Content.png",
                    help="正片背景图")
    ap.add_argument("--subs", type=Path, default=PROJECT / "output" / "subs.ass")
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--out", type=Path, default=PROJECT / "output" / "release_v2.mp4")
    ap.add_argument("--intro-end", type=float, default=None,
                    help="封面开始淡出的秒数;默认=首句字幕前 2s(夹在 4~20s)")
    ap.add_argument("--fade", type=float, default=1.5, help="封面→内容淡出时长")
    ap.add_argument("--wave-height", type=int, default=240)
    ap.add_argument("--wave-y", type=int, default=650,
                    help="声波带顶边 y(默认 650:波带 650-890,字幕区 ~900 起)")
    ap.add_argument("--no-wave", action="store_true")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            die(f"找不到 {tool}")
    for p in (args.audio, args.cover, args.content):
        if not p.is_file():
            die(f"文件不存在: {p}")
    use_subs = not args.no_subs
    if use_subs and not args.subs.is_file():
        die(f"字幕不存在: {args.subs}(先跑 auto_line_times.py + make_subs.py,"
            "或加 --no-subs)")

    env = clean_env()
    if use_subs:
        r = subprocess.run(["fc-match", "Noto Sans CJK JP"], capture_output=True,
                           text=True, env=env)
        if "Noto Sans CJK" not in r.stdout:
            print(f"[release2] ⚠ fc-match 未命中 Noto CJK({r.stdout.strip()}),"
                  "字幕可能变豆腐块", file=sys.stderr)

    try:
        dur = float(ffprobe_field(args.audio, "format=duration"))
    except ValueError:
        die(f"ffprobe 读不到音频时长: {args.audio}")

    intro = args.intro_end
    if intro is None:
        intro = min(max(first_sub_start(args.subs) - 2.0, 4.0), 20.0) if use_subs else 8.0
    fps = args.fps

    # 背景:内容图打底,封面图带 alpha 淡出叠在上面(比 xfade 对循环图输入更稳)
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
        # 声波:单声道 cline 波形,拆成「蓝色模糊光晕 + 亮白主线」两层叠加
        parts += [
            "[2:a]aformat=channel_layouts=mono,"
            f"showwaves=s=1920x{wh}:mode=cline:rate={fps}:scale=sqrt:"
            "colors=0xFFFFFF[wv]",
            "[wv]split[wv1][wv2]",
            "[wv1]format=rgba,colorchannelmixer=rr=0.45:gg=0.58:bb=1.0:aa=0.85,"
            "gblur=sigma=14[wglow]",
            "[wv2]format=rgba,colorchannelmixer=rr=0.88:gg=0.93:bb=1.0:aa=0.75[wcrisp]",
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
           "-i", str(args.cover),                      # 缩略图(不循环,单帧)
           "-filter_complex", ";".join(parts),
           "-map", f"[{last}]", "-map", "2:a", "-map", "3:v",
           "-c:v:0", "libx264", "-preset", "medium", "-crf", str(args.crf),
           "-pix_fmt:v:0", "yuv420p",
           "-c:a", "aac", "-b:a", "320k",
           "-c:v:1", "png", "-disposition:v:1", "attached_pic",
           # -t 按音频时长硬截断(循环图输入是无限流,-shortest 行为不可靠)
           "-t", f"{dur:.3f}", "-movflags", "+faststart", str(args.out)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[release2] 封面 0-{intro:.1f}s → 淡出 {args.fade}s → 内容图;"
          f"时长 {dur:.1f}s")
    print("[release2]", " ".join(cmd))
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        die(f"ffmpeg 失败 (exit={r.returncode})")
    print(f"[release2] 完成 → {args.out}({args.out.stat().st_size / 1e6:.1f} MB)")
    print("[release2] 发布前核对:B 站 AI 生成内容标注 + 原填词作者署名(不可协商)")


if __name__ == "__main__":
    main()
