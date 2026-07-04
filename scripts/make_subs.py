#!/usr/bin/env python3
"""Phase 4 — 从 lyrics/final.md 生成双语 .ass 字幕(日语大字 + 中文小字)。

时间轴来自 refs/line_times.tsv(行号<TAB>开始<TAB>结束[<TAB>备注]):
- 首次运行若无该文件,自动生成待填模板后退出;
- 时间写秒(85.3)或 分:秒(1:25.3)都行;结束留空 = 下一行开始前 0.1s,
  末行留空 = 开始 + --last-dur;
- 对轴参照:inst/vocals_ref_*.wav(分离出的爱音版人声)或 SynthV 工程小节时间。

示例:
  python scripts/make_subs.py                 # 生成 output/subs.ass
  python scripts/make_subs.py --shift 0.35    # 整体延后 0.35s(与 mix 的 vocal-shift 联动)
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

ASS_HEADER = """[Script Info]
Title: 念张师 日语版
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: JP,Noto Sans CJK JP,64,&H00FFFFFF,&H00FFFFFF,&H00202020,&H80000000,0,0,0,0,100,100,0,0,1,3,0,2,60,60,96,1
Style: CN,Noto Sans CJK SC,44,&H00D8D8D8,&H00FFFFFF,&H00202020,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,60,60,36,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def die(msg):
    print(f"[subs] 错误: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_lyrics(md_path: Path):
    """解析 final.md 的歌词表格 → {行号: (日语, 中文)}。"""
    lines = {}
    for raw in md_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|", raw)
        if not m:
            continue
        cells = [c.strip() for c in raw.split("|")]
        # cells[0] 空、[1] 行号、[2] 日语、[3] 罗马音、[4] 中文
        if len(cells) < 5:
            continue
        lines[int(cells[1])] = (cells[2], cells[4])
    if not lines:
        die(f"{md_path} 里没解析到歌词表格行")
    return lines


def parse_time(s: str) -> float:
    s = s.strip()
    if not s:
        raise ValueError("空")
    if ":" in s:
        mm, ss = s.rsplit(":", 1)
        return int(mm) * 60 + float(ss)
    return float(s)


def fmt_ass(t: float) -> str:
    # 整数厘秒运算再拆位:先 divmod 后对秒四舍五入会产出 0:01:60.00 这类非法时间戳
    cs = max(round(t * 100), 0)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def sanitize(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\\", "/")


def write_template(times_path: Path, lyrics: dict):
    rows = ["# 行号\t开始\t结束\t参考(勿改动列顺序;结束可留空)"]
    for n in sorted(lyrics):
        rows.append(f"{n}\t\t\t{lyrics[n][0]}")
    times_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lyrics", type=Path, default=PROJECT / "lyrics" / "final.md")
    ap.add_argument("--times", type=Path, default=PROJECT / "refs" / "line_times.tsv")
    ap.add_argument("--out", type=Path, default=PROJECT / "output" / "subs.ass")
    ap.add_argument("--shift", type=float, default=0.0, help="整体平移秒数,正=延后")
    ap.add_argument("--gap", type=float, default=0.1, help="自动结束时间距下一行的间隙")
    ap.add_argument("--last-dur", type=float, default=5.0, help="末行无结束时间时的时长")
    args = ap.parse_args()

    if not args.lyrics.is_file():
        die(f"歌词不存在: {args.lyrics}")
    lyrics = parse_lyrics(args.lyrics)

    if not args.times.is_file():
        write_template(args.times, lyrics)
        die(f"时间轴文件不存在,已生成待填模板: {args.times}\n"
            "        填好每行开始时间后重跑(对轴参照 inst/vocals_ref_*.wav)")

    starts, ends = {}, {}
    # utf-8-sig:Windows 记事本/Excel 导出的 BOM 不该让文件解析失败
    for i, raw in enumerate(args.times.read_text(encoding="utf-8-sig").splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        cols = raw.split("\t")
        try:
            n = int(cols[0])
        except ValueError:
            die(f"{args.times}:{i} 行号解析失败: {raw!r}")
        if n in starts:
            die(f"{args.times}:{i} 行号 {n} 重复出现(复制行后忘了改行号?)")
        start_str = cols[1].strip() if len(cols) > 1 else ""
        if not start_str:
            die(f"{args.times}:{i} 行 {n} 的开始时间还没填")
        try:
            starts[n] = parse_time(start_str) + args.shift
        except ValueError:
            die(f"{args.times}:{i} 行 {n} 开始时间格式不对: {start_str!r}"
                "(用秒 85.3 或 分:秒 1:25.3)")
        end_str = cols[2].strip() if len(cols) > 2 else ""
        if end_str:
            try:
                ends[n] = parse_time(end_str) + args.shift
            except ValueError:
                die(f"{args.times}:{i} 行 {n} 结束时间格式不对: {end_str!r}")

    missing = sorted(set(lyrics) - set(starts))
    if missing:
        die(f"这些行还没有时间: {missing}")
    unknown = sorted(set(starts) - set(lyrics))
    if unknown:
        die(f"时间轴里有歌词中不存在的行号: {unknown}(检查是否笔误)")
    order = sorted(starts)
    for a, b in zip(order, order[1:]):
        if starts[b] <= starts[a]:
            die(f"行 {b} 开始时间 ({starts[b]:.2f}) 不晚于行 {a} ({starts[a]:.2f}),检查时间轴")

    events = []
    for idx, n in enumerate(order):
        start = starts[n]
        end = ends.get(n, starts[order[idx + 1]] - args.gap if idx + 1 < len(order)
                       else start + args.last_dur)
        if end <= start:
            die(f"行 {n} 结束 ({end:.2f}) 不晚于开始 ({start:.2f})")
        jp, cn = (sanitize(t) for t in lyrics[n])
        events.append(f"Dialogue: 0,{fmt_ass(start)},{fmt_ass(end)},JP,,0,0,0,,{jp}")
        events.append(f"Dialogue: 0,{fmt_ass(start)},{fmt_ass(end)},CN,,0,0,0,,{cn}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(ASS_HEADER + "\n".join(events) + "\n", encoding="utf-8-sig")
    print(f"[subs] 完成: {len(order)} 行 → {args.out}")


if __name__ == "__main__":
    main()
