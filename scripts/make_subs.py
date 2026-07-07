#!/usr/bin/env python3
"""Phase 4 — 从 <project>/lyrics/final.md 生成双语 .ass 字幕(日语大字 + 中文小字)。

时间轴来自 <project>/refs/line_times.tsv(行号<TAB>开始<TAB>结束[<TAB>备注]):
- 首次运行若无该文件,自动生成待填模板后退出;
- 时间写秒(85.3)或 分:秒(1:25.3)都行;结束留空 = 下一行开始前 0.1s,
  末行留空 = 开始 + --last-dur;
- 行号带后缀 r(如 7r)= 该行歌词的重复演唱(副歌 reprise),可与本尊共存;
- 音频里没唱到的行可以缺席,但必须加 --partial 明示(防止漏填时间轴);
- 对轴参照:inst/vocals_ref_*.wav(分离出的爱音版人声)或 SynthV 工程小节时间。

示例:
  python scripts/make_subs.py                 # 生成 <project>/output/subs.ass
  python scripts/make_subs.py --shift 0.35    # 整体延后 0.35s(与 mix 的 vocal-shift 联动)
"""

import argparse
import re
import sys
from pathlib import Path

from project_paths import add_project_arg, resolve_project

ASS_HEADER = """[Script Info]
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: JP,Noto Sans CJK JP,64,&H00FFFFFF,&H00FFFFFF,&H00202020,&H80000000,0,0,0,0,100,100,0,0,1,3,0,2,60,60,96,1
Style: CN,Noto Sans CJK JP,44,&H00D8D8D8,&H00FFFFFF,&H00202020,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,60,60,36,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# --board:歌词定位到背景图的固定留白区(粉笔感:无描边+轻模糊),坐标用
# --board-jp/--board-cn 按图实测调。默认值按 nianzhangshi 工程的
# Azuma_Content_v2.png 内框实测(1672x941 → 1920x1080 等比放大 1.1483):
# 内饰线框 x 155-705 / y 110-545 → 缩放后中心 x≈494,JP y≈340 / CN y≈432。
BOARD_HEADER = """[Script Info]
Title: {title}(定位排版)
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: JP,Noto Sans CJK JP,38,&H00F2F6FF,&H00FFFFFF,&H00202020,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1
Style: CN,Noto Sans CJK JP,28,&H00C8D2E6,&H00FFFFFF,&H00202020,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
BOARD_FX = r"\blur0.8"


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
    add_project_arg(ap)
    ap.add_argument("--lyrics", type=Path, default=None,
                    help="默认 <project>/lyrics/final.md")
    ap.add_argument("--times", type=Path, default=None,
                    help="默认 <project>/refs/line_times.tsv")
    ap.add_argument("--out", type=Path, default=None,
                    help="默认 <project>/output/subs.ass(--board 时 subs_board.ass)")
    ap.add_argument("--title", default=None,
                    help="ASS Script Info 标题,默认取工程目录名")
    ap.add_argument("--shift", type=float, default=0.0, help="整体平移秒数,正=延后")
    ap.add_argument("--gap", type=float, default=0.1, help="自动结束时间距下一行的间隙")
    ap.add_argument("--last-dur", type=float, default=5.0, help="末行无结束时间时的时长")
    ap.add_argument("--partial", action="store_true",
                    help="允许部分歌词行没有时间(音频里未唱到的行)")
    ap.add_argument("--board", action="store_true",
                    help="定位排版:歌词 \\pos 到背景图固定留白区(坐标见 --board-jp/cn)")
    ap.add_argument("--board-jp", type=int, nargs=2, default=(494, 340),
                    metavar=("X", "Y"), help="--board 时日语行中心坐标(1920x1080 系)")
    ap.add_argument("--board-cn", type=int, nargs=2, default=(494, 432),
                    metavar=("X", "Y"), help="--board 时中文行中心坐标")
    args = ap.parse_args()
    proj = resolve_project(args)
    args.lyrics = args.lyrics or proj / "lyrics" / "final.md"
    args.times = args.times or proj / "refs" / "line_times.tsv"
    if args.out is None:
        args.out = proj / "output" / ("subs_board.ass" if args.board else "subs.ass")
    title = args.title or proj.name
    board_pos = {"JP": tuple(args.board_jp), "CN": tuple(args.board_cn)}

    if not args.lyrics.is_file():
        die(f"歌词不存在: {args.lyrics}")
    lyrics = parse_lyrics(args.lyrics)

    if not args.times.is_file():
        write_template(args.times, lyrics)
        die(f"时间轴文件不存在,已生成待填模板: {args.times}\n"
            "        填好每行开始时间后重跑(对轴参照 inst/vocals_ref_*.wav)")

    entries = []  # (start, end|None, 行号, 是否重复)
    seen_primary = set()
    # utf-8-sig:Windows 记事本/Excel 导出的 BOM 不该让文件解析失败
    for i, raw in enumerate(args.times.read_text(encoding="utf-8-sig").splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        cols = raw.split("\t")
        n_str = cols[0].strip()
        repeat = n_str.endswith("r")
        try:
            n = int(n_str[:-1] if repeat else n_str)
        except ValueError:
            die(f"{args.times}:{i} 行号解析失败: {raw!r}")
        if not repeat:
            if n in seen_primary:
                die(f"{args.times}:{i} 行号 {n} 重复出现(重复演唱段用 {n}r 标记)")
            seen_primary.add(n)
        if n not in lyrics:
            die(f"{args.times}:{i} 歌词里没有第 {n} 行(检查是否笔误)")
        start_str = cols[1].strip() if len(cols) > 1 else ""
        if not start_str:
            die(f"{args.times}:{i} 行 {n_str} 的开始时间还没填")
        try:
            start = parse_time(start_str) + args.shift
        except ValueError:
            die(f"{args.times}:{i} 行 {n_str} 开始时间格式不对: {start_str!r}"
                "(用秒 85.3 或 分:秒 1:25.3)")
        end = None
        end_str = cols[2].strip() if len(cols) > 2 else ""
        if end_str:
            try:
                end = parse_time(end_str) + args.shift
            except ValueError:
                die(f"{args.times}:{i} 行 {n_str} 结束时间格式不对: {end_str!r}")
        entries.append((start, end, n, repeat))

    missing = sorted(set(lyrics) - seen_primary)
    if missing:
        if not args.partial:
            die(f"这些行还没有时间: {missing}(音频里确实没唱的行,加 --partial)")
        print(f"[subs] 注意: {len(missing)} 行不在时间轴上(音频未唱): {missing}")
    entries.sort(key=lambda e: e[0])
    for a, b in zip(entries, entries[1:]):
        if b[0] <= a[0]:
            die(f"行 {b[2]} 开始时间 ({b[0]:.2f}) 不晚于前一条 ({a[0]:.2f}),检查时间轴")

    events = []
    for idx, (start, end, n, _rep) in enumerate(entries):
        if end is None:
            end = (entries[idx + 1][0] - args.gap if idx + 1 < len(entries)
                   else start + args.last_dur)
        if end <= start:
            die(f"行 {n} 结束 ({end:.2f}) 不晚于开始 ({start:.2f})")
        jp, cn = (sanitize(t) for t in lyrics[n])
        for style, text in (("JP", jp), ("CN", cn)):
            fx = ""
            if args.board:
                x, y = board_pos[style]
                fx = f"{{\\pos({x},{y}){BOARD_FX}}}"
            events.append(f"Dialogue: 0,{fmt_ass(start)},{fmt_ass(end)},"
                          f"{style},,0,0,0,,{fx}{text}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    header = (BOARD_HEADER if args.board else ASS_HEADER).format(title=title)
    args.out.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    print(f"[subs] 完成: {len(entries)} 条 → {args.out}")


if __name__ == "__main__":
    main()
