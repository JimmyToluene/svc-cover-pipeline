#!/usr/bin/env python3
"""Phase 4 — generate bilingual .ass subtitles (large Japanese + small Chinese) from <project>/lyrics/final.md.

Timing comes from <project>/refs/line_times.tsv (line no<TAB>start<TAB>end[<TAB>note]):
- On the first run, if the file is missing, a fill-in template is generated and the script exits;
- Times may be written in seconds (85.3) or min:sec (1:25.3); a blank end = 0.1s
  before the next line starts, a blank end on the last line = start + --last-dur;
- A line number with an "r" suffix (e.g. 7r) marks a repeat performance of that
  lyric line (chorus reprise) and can coexist with the original;
- Lines not sung in the audio may be absent, but you must pass --partial explicitly
  (guards against timeline entries being forgotten);
- Timing references: inst/vocals_ref_*.wav (the separated Anon-version vocals) or
  bar times from the SynthV project.

Examples:
  python scripts/make_subs.py                 # writes <project>/output/subs.ass
  python scripts/make_subs.py --shift 0.35    # delay everything by 0.35s (in step with mix's vocal-shift)
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
Style: JP,Noto Sans CJK JP,64,{main_color},&H00FFFFFF,{outline_color},&H80000000,0,0,0,0,100,100,0,0,1,3,0,2,60,60,96,1
Style: CN,Noto Sans CJK JP,44,{sub_color},&H00FFFFFF,{outline_color},&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,60,60,36,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# --board: pin the lyrics to a fixed blank area of the background image
# (chalk look: no outline + slight blur); tune the coordinates with
# --board-jp/--board-cn per the actual image. Defaults were measured on the
# nianzhangshi project's Azuma_Content_v2.png inner frame (1672x941 → 1920x1080
# uniform scale 1.1483): inner trim frame x 155-705 / y 110-545 → after scaling,
# center x≈494, JP y≈340 / CN y≈432.
BOARD_HEADER = """[Script Info]
Title: {title} (board layout)
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: JP,Noto Sans CJK JP,38,{main_color},&H00FFFFFF,{outline_color},&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1
Style: CN,Noto Sans CJK JP,28,{sub_color},&H00FFFFFF,{outline_color},&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
BOARD_FX = r"\blur0.8"

# Default (main, sub, outline) colors per layout mode; overridden by --color-*
DEFAULT_COLORS = {
    False: ("&H00FFFFFF", "&H00D8D8D8", "&H00202020"),   # bottom subtitles
    True: ("&H00F2F6FF", "&H00C8D2E6", "&H00202020"),    # --board pinned layout
}


def ass_color(hexstr: str) -> str:
    """#RRGGBB → ASS &H00BBGGRR."""
    h = hexstr.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        die(f"color must be in #RRGGBB format: {hexstr!r}")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def die(msg):
    print(f"[subs] error: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_lyrics(md_path: Path):
    """Parse the lyrics table in final.md → {line no: (Japanese, Chinese)}."""
    lines = {}
    for raw in md_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|", raw)
        if not m:
            continue
        cells = [c.strip() for c in raw.split("|")]
        # cells[0] empty, [1] line no, [2] Japanese, [3] romaji, [4] Chinese
        if len(cells) < 5:
            continue
        lines[int(cells[1])] = (cells[2], cells[4])
    if not lines:
        die(f"no lyrics table rows parsed from {md_path}")
    return lines


def parse_time(s: str) -> float:
    s = s.strip()
    if not s:
        raise ValueError("empty")
    if ":" in s:
        mm, ss = s.rsplit(":", 1)
        return int(mm) * 60 + float(ss)
    return float(s)


def fmt_ass(t: float) -> str:
    # Do the math in integer centiseconds, then split: divmod first and rounding
    # the seconds afterwards can produce invalid timestamps like 0:01:60.00
    cs = max(round(t * 100), 0)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def sanitize(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\\", "/")


def write_template(times_path: Path, lyrics: dict):
    rows = ["# line\tstart\tend\treference (keep the column order; end may be left blank)"]
    for n in sorted(lyrics):
        rows.append(f"{n}\t\t\t{lyrics[n][0]}")
    times_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--lyrics", type=Path, default=None,
                    help="default <project>/lyrics/final.md")
    ap.add_argument("--times", type=Path, default=None,
                    help="default <project>/refs/line_times.tsv")
    ap.add_argument("--out", type=Path, default=None,
                    help="default <project>/output/subs.ass (subs_board.ass with --board)")
    ap.add_argument("--title", default=None,
                    help="ASS Script Info title, defaults to the project directory name")
    ap.add_argument("--shift", type=float, default=0.0, help="shift everything by this many seconds, positive = later")
    ap.add_argument("--gap", type=float, default=0.1, help="gap before the next line when the end time is auto-derived")
    ap.add_argument("--last-dur", type=float, default=5.0, help="duration of the last line when it has no end time")
    ap.add_argument("--partial", action="store_true",
                    help="allow some lyric lines to have no timing (lines not sung in the audio)")
    ap.add_argument("--board", action="store_true",
                    help="pinned layout: \\pos the lyrics onto a fixed blank area of the background image (coords via --board-jp/cn)")
    ap.add_argument("--board-jp", type=int, nargs=2, default=(494, 340),
                    metavar=("X", "Y"), help="center of the Japanese line with --board (1920x1080 space)")
    ap.add_argument("--board-cn", type=int, nargs=2, default=(494, 432),
                    metavar=("X", "Y"), help="center of the Chinese line with --board")
    ap.add_argument("--color-main", default=None, metavar="#RRGGBB",
                    help="main (large) line color, default white")
    ap.add_argument("--color-sub", default=None, metavar="#RRGGBB",
                    help="secondary (small) line color, default light gray")
    ap.add_argument("--color-outline", default=None, metavar="#RRGGBB",
                    help="outline color shared by both lines, default dark gray")
    args = ap.parse_args()
    proj = resolve_project(args)
    args.lyrics = args.lyrics or proj / "lyrics" / "final.md"
    args.times = args.times or proj / "refs" / "line_times.tsv"
    if args.out is None:
        args.out = proj / "output" / ("subs_board.ass" if args.board else "subs.ass")
    title = args.title or proj.name
    board_pos = {"JP": tuple(args.board_jp), "CN": tuple(args.board_cn)}

    if not args.lyrics.is_file():
        die(f"lyrics not found: {args.lyrics}")
    lyrics = parse_lyrics(args.lyrics)

    if not args.times.is_file():
        write_template(args.times, lyrics)
        die(f"timeline file not found, a fill-in template has been generated: {args.times}\n"
            "        fill in each line's start time and rerun (timing reference: inst/vocals_ref_*.wav)")

    entries = []  # (start, end|None, line no, is repeat)
    seen_primary = set()
    # utf-8-sig: a BOM from Windows Notepad/Excel exports shouldn't break parsing
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
            die(f"{args.times}:{i} could not parse line number: {raw!r}")
        if not repeat:
            if n in seen_primary:
                die(f"{args.times}:{i} line number {n} appears twice (mark repeated passages as {n}r)")
            seen_primary.add(n)
        if n not in lyrics:
            die(f"{args.times}:{i} the lyrics have no line {n} (check for a typo)")
        start_str = cols[1].strip() if len(cols) > 1 else ""
        if not start_str:
            die(f"{args.times}:{i} start time for line {n_str} is not filled in yet")
        try:
            start = parse_time(start_str) + args.shift
        except ValueError:
            die(f"{args.times}:{i} bad start time format for line {n_str}: {start_str!r}"
                " (use seconds 85.3 or min:sec 1:25.3)")
        end = None
        end_str = cols[2].strip() if len(cols) > 2 else ""
        if end_str:
            try:
                end = parse_time(end_str) + args.shift
            except ValueError:
                die(f"{args.times}:{i} bad end time format for line {n_str}: {end_str!r}")
        entries.append((start, end, n, repeat))

    missing = sorted(set(lyrics) - seen_primary)
    if missing:
        if not args.partial:
            die(f"these lines have no timing yet: {missing} (if they really aren't sung in the audio, pass --partial)")
        print(f"[subs] note: {len(missing)} lines are not on the timeline (not sung in the audio): {missing}")
    entries.sort(key=lambda e: e[0])
    for a, b in zip(entries, entries[1:]):
        if b[0] <= a[0]:
            die(f"line {b[2]} start time ({b[0]:.2f}) is not after the previous entry ({a[0]:.2f}), check the timeline")

    events = []
    for idx, (start, end, n, _rep) in enumerate(entries):
        if end is None:
            end = (entries[idx + 1][0] - args.gap if idx + 1 < len(entries)
                   else start + args.last_dur)
        if end <= start:
            die(f"line {n} end ({end:.2f}) is not after its start ({start:.2f})")
        jp, cn = (sanitize(t) for t in lyrics[n])
        for style, text in (("JP", jp), ("CN", cn)):
            fx = ""
            if args.board:
                x, y = board_pos[style]
                fx = f"{{\\pos({x},{y}){BOARD_FX}}}"
            events.append(f"Dialogue: 0,{fmt_ass(start)},{fmt_ass(end)},"
                          f"{style},,0,0,0,,{fx}{text}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    d_main, d_sub, d_outline = DEFAULT_COLORS[args.board]
    header = (BOARD_HEADER if args.board else ASS_HEADER).format(
        title=title,
        main_color=ass_color(args.color_main) if args.color_main else d_main,
        sub_color=ass_color(args.color_sub) if args.color_sub else d_sub,
        outline_color=(ass_color(args.color_outline) if args.color_outline
                       else d_outline))
    args.out.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    print(f"[subs] done: {len(entries)} lines → {args.out}")


if __name__ == "__main__":
    main()
