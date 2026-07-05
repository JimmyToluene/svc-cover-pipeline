#!/usr/bin/env python3
"""Phase 4 — ASR 自动生成字幕时间轴(refs/line_times.tsv 初稿)。

原理:对分离人声(inst/vocals_ref_anon_version.wav)跑 faster-whisper 词级时间戳,
词流假名化后与 lyrics/final.md 的 25 行做单调 DP 对齐,行首/行尾时间写入
refs/line_times.tsv(make_subs.py 的输入格式,含结束时间,避免间奏字幕悬挂)。

时间基:参照人声与 preview_mix/final_mix 一致(mix.py vocal-shift=0,仅尾部垫 3s),
时间戳可直接用于成品字幕;若 mix 时用了 --vocal-shift,make_subs.py --shift 同值。

ASR 对歌声转写不完美,输出是**初稿**:发布前抽查 4-6 行(第 1 行、副歌 7/21、
间奏后的 11/17)。整体偏移用 make_subs.py --shift,不逐行改。

用法(phase4 env,首跑会下载 whisper 模型):
  conda run -n phase4 python scripts/auto_line_times.py             # 写 tsv
  conda run -n phase4 python scripts/auto_line_times.py --dry-run   # 只看对齐表
"""

import argparse
import difflib
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_subs import parse_lyrics  # noqa: E402


def die(msg):
    print(f"[align] 错误: {msg}", file=sys.stderr)
    sys.exit(1)


KANA_RE = re.compile(r"[ぁ-ゖー]")


def make_kana_fn():
    import pykakasi
    kks = pykakasi.kakasi()

    def to_kana(text: str) -> str:
        hira = "".join(w["hira"] for w in kks.convert(text))
        return "".join(KANA_RE.findall(hira))

    return to_kana


def transcribe(vocals: Path, model_name: str, device: str):
    from faster_whisper import WhisperModel
    compute = "float16" if device == "cuda" else "int8"
    print(f"[align] 加载 whisper {model_name} ({device}/{compute})…")
    model = WhisperModel(model_name, device=device, compute_type=compute)
    kwargs = dict(language="ja", word_timestamps=True,
                  vad_filter=True, condition_on_previous_text=False, beam_size=5)
    try:
        segments, info = model.transcribe(str(vocals), **kwargs)
        segments = list(segments)  # 生成器在此触发实际推理
    except RuntimeError as e:
        if device == "cuda" and "libcublas" in str(e):
            # ctranslate2 要 CUDA12 的 cublas/cudnn;env 里是 CUDA13 时借 pip 包:
            # pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 并把两个 lib 目录
            # 加进 LD_LIBRARY_PATH。这里先降级 CPU 保证能出结果。
            print("[align] ⚠ CUDA 库缺 libcublas.so.12,降级 CPU/int8(慢但可用)")
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            segments, info = model.transcribe(str(vocals), **kwargs)
            segments = list(segments)
        else:
            raise
    words = []
    for seg in segments:
        for w in seg.words or []:
            t = w.word.strip()
            if t:
                words.append((w.start, w.end, t))
    print(f"[align] ASR: {len(words)} 词,音频 {info.duration:.1f}s")
    return words


def align(lines_kana, words_kana, max_span=40, skip_penalty=0.5):
    """单调 DP:词流切成 len(lines) 个连续组(组间允许跳词)。

    f[i][k] = 前 i 个词、已完成 k 行的最优分。返回每行 (词起, 词止) 下标。
    """
    W, L = len(words_kana), len(lines_kana)
    NEG = float("-inf")
    f = [[NEG] * (L + 1) for _ in range(W + 1)]
    bp = [[None] * (L + 1) for _ in range(W + 1)]
    f[0][0] = 0.0
    # 前缀假名串,快速取词段文本
    pref = [""]
    for wk in words_kana:
        pref.append(pref[-1] + wk)

    for i in range(W + 1):
        for k in range(L + 1):
            if f[i][k] == NEG:
                continue
            if i < W:  # 跳过词 i(间奏杂音/幻听)
                cand = f[i][k] - skip_penalty
                if cand > f[i + 1][k]:
                    f[i + 1][k], bp[i + 1][k] = cand, ("skip", i, k)
            if k < L:  # 词 i..j-1 归为第 k 行
                target = lines_kana[k]
                for j in range(i + 1, min(i + max_span, W) + 1):
                    chunk = pref[j][len(pref[i]):]
                    if len(chunk) > 2 * len(target) + 6:
                        break
                    sim = difflib.SequenceMatcher(None, target, chunk).ratio()
                    cand = f[i][k] + sim * max(len(target), 1)
                    if cand > f[j][k + 1]:
                        f[j][k + 1], bp[j][k + 1] = cand, ("line", i, k)
    # 允许尾部跳词:取 f[i][L] 最优
    best_i = max(range(W + 1), key=lambda i: f[i][L])
    if f[best_i][L] == NEG:
        die("DP 对齐失败(ASR 词数太少?先 --dry-run 看转写结果)")
    spans, i, k = [None] * L, best_i, L
    while k > 0 or (bp[i][k] is not None):
        move = bp[i][k]
        if move is None:
            break
        kind, pi, pk = move
        if kind == "line":
            spans[pk] = (pi, i)
            i, k = pi, pk
        else:
            i, k = pi, pk
    if any(s is None for s in spans):
        die("DP 回溯不完整,提高 --max-span 再试")
    return spans, f[best_i][L]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vocals", type=Path,
                    default=PROJECT / "inst" / "vocals_ref_anon_version.wav")
    ap.add_argument("--lyrics", type=Path, default=PROJECT / "lyrics" / "final.md")
    ap.add_argument("--out", type=Path, default=PROJECT / "refs" / "line_times.tsv")
    ap.add_argument("--model", default="large-v3-turbo")
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    ap.add_argument("--max-span", type=int, default=40, help="一行最多吃多少个 ASR 词")
    ap.add_argument("--lead-in", type=float, default=0.15, help="字幕相对发声提前秒数")
    ap.add_argument("--tail", type=float, default=0.35, help="行尾字幕延留秒数")
    ap.add_argument("--dry-run", action="store_true", help="只打印对齐表,不写文件")
    args = ap.parse_args()

    for p in (args.vocals, args.lyrics):
        if not p.is_file():
            die(f"文件不存在: {p}")
    lyrics = parse_lyrics(args.lyrics)  # {n: (jp, cn)}
    order = sorted(lyrics)
    to_kana = make_kana_fn()
    lines_kana = [to_kana(lyrics[n][0]) for n in order]

    words = transcribe(args.vocals, args.model, args.device)
    if len(words) < len(order):
        die(f"ASR 只出了 {len(words)} 词,少于 {len(order)} 行,无法对齐")
    words_kana = [to_kana(t) for _, _, t in words]

    spans, score = align(lines_kana, words_kana, max_span=args.max_span)
    print(f"[align] DP 总分 {score:.1f}(满分≈{sum(len(k) for k in lines_kana)})\n")

    rows, warn = [], []
    print(f"{'行':>3} {'开始':>7} {'结束':>7} {'相似度':>5}  ASR 转写 → 歌词")
    for idx, n in enumerate(order):
        wi, wj = spans[idx]
        start, end = words[wi][0], words[wj - 1][1]
        asr_text = "".join(t for _, _, t in words[wi:wj])
        sim = difflib.SequenceMatcher(
            None, lines_kana[idx], "".join(words_kana[wi:wj])).ratio()
        flag = " ⚠" if sim < 0.5 else ""
        print(f"{n:>3} {start:>7.2f} {end:>7.2f} {sim:>5.0%}{flag}  "
              f"{asr_text} → {lyrics[n][0]}")
        if sim < 0.5:
            warn.append(n)
        rows.append((n, start, end))

    # 字幕化:提前量/延留,且不与相邻行重叠
    out_rows = []
    for idx, (n, start, end) in enumerate(rows):
        s = max(start - args.lead_in, 0.0)
        e = end + args.tail
        if idx + 1 < len(rows):
            e = min(e, rows[idx + 1][1] - args.lead_in - 0.10)
        if idx > 0 and s < out_rows[-1][2] + 0.05:
            s = out_rows[-1][2] + 0.05
        if e <= s:
            e = s + 0.8
        out_rows.append((n, s, e))

    if warn:
        print(f"\n[align] ⚠ 相似度<50% 的行: {warn} —— 这几行时间可能不准,重点抽查")
    if args.dry_run:
        print("[align] --dry-run,未写文件")
        return
    hdr = ("# 行号\t开始\t结束\t参考(勿改动列顺序;结束可留空)\n"
           "# 本文件由 scripts/auto_line_times.py(ASR)自动生成,是初稿;\n"
           "# 发布前抽查第 1/7/11/17/21 行,整体偏移用 make_subs.py --shift 修\n")
    body = "".join(f"{n}\t{s:.2f}\t{e:.2f}\t{lyrics[n][0]}\n" for n, s, e in out_rows)
    args.out.write_text(hdr + body, encoding="utf-8")
    print(f"[align] 写入 {args.out}({len(out_rows)} 行)")


if __name__ == "__main__":
    main()
