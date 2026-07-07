#!/usr/bin/env python3
"""Phase 4 — ASR-based automatic subtitle timing (first draft of <project>/refs/line_times.tsv).

How it works: run faster-whisper with word-level timestamps on the separated
vocals (default: the single vocals_ref_*.wav under <project>/inst/), convert
the word stream to kana, then align it against the lyric lines in
lyrics/final.md with a monotonic DP. Line start/end times are written to
refs/line_times.tsv (the input format for make_subs.py, end times included so
subtitles don't linger through instrumental breaks).

Time base: the reference vocals line up with preview_mix/final_mix (mix.py
vocal-shift=0, only 3s of tail padding), so the timestamps can be used for the
final subtitles as-is; if you mixed with --vocal-shift, pass the same value to
make_subs.py --shift.

ASR transcription of singing is imperfect, so the output is a FIRST DRAFT:
spot-check 4-6 lines before release (the first line, the chorus, and lines
right after instrumental breaks are the most error-prone). Fix global offsets
with make_subs.py --shift rather than editing lines one by one.

Usage (phase4 env; the first run downloads the whisper model):
  conda run -n phase4 python scripts/auto_line_times.py             # write the tsv
  conda run -n phase4 python scripts/auto_line_times.py --dry-run   # just print the alignment table
"""

import argparse
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_subs import parse_lyrics  # noqa: E402
from project_paths import add_project_arg, resolve_project  # noqa: E402


def die(msg):
    print(f"[align] error: {msg}", file=sys.stderr)
    sys.exit(1)


def default_vocals(proj: Path) -> Path:
    cands = sorted((proj / "inst").glob("vocals_ref_*.wav"))
    if len(cands) == 1:
        return cands[0]
    if not cands:
        die(f"no vocals_ref_*.wav under {proj / 'inst'} (run separate.py first), "
            "or specify one with --vocals")
    die(f"multiple reference vocals under {proj / 'inst'}: {[p.name for p in cands]}; "
        "specify one with --vocals")


KANA_RE = re.compile(r"[ぁ-ゖー]")
HAN_RE = re.compile(r"[一-鿿]")


def make_norm_fn(lang: str):
    """Normalizer for lyric/ASR words: ja = kana-ize (align at the reading level), zh = keep Han characters only."""
    if lang == "ja":
        import pykakasi
        kks = pykakasi.kakasi()

        def to_kana(text: str) -> str:
            hira = "".join(w["hira"] for w in kks.convert(text))
            return "".join(KANA_RE.findall(hira))

        return to_kana

    def to_han(text: str) -> str:
        return "".join(HAN_RE.findall(text))

    return to_han


def transcribe(vocals: Path, model_name: str, device: str, lang: str):
    from faster_whisper import WhisperModel
    compute = "float16" if device == "cuda" else "int8"
    print(f"[align] loading whisper {model_name} ({device}/{compute})…")
    model = WhisperModel(model_name, device=device, compute_type=compute)
    kwargs = dict(language=lang, word_timestamps=True,
                  vad_filter=True, condition_on_previous_text=False, beam_size=5)
    try:
        segments, info = model.transcribe(str(vocals), **kwargs)
        segments = list(segments)  # consuming the generator triggers the actual inference
    except RuntimeError as e:
        if device == "cuda" and "libcublas" in str(e):
            # ctranslate2 needs CUDA 12's cublas/cudnn; when the env is on CUDA 13,
            # borrow the pip packages: pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
            # and add both lib directories to LD_LIBRARY_PATH. For now, fall back to
            # CPU so we still get a result.
            print("[align] ⚠ CUDA libs missing libcublas.so.12; falling back to CPU/int8 (slow but works)")
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
    print(f"[align] ASR: {len(words)} words, audio {info.duration:.1f}s")
    return words


def align(lines_kana, words_kana, max_span=40, skip_penalty=0.5):
    """Monotonic DP: split the word stream into len(lines) consecutive groups (words may be skipped between groups).

    f[i][k] = best score after consuming i words with k lines completed.
    Returns (word start, word end) indices for each line.
    """
    W, L = len(words_kana), len(lines_kana)
    NEG = float("-inf")
    f = [[NEG] * (L + 1) for _ in range(W + 1)]
    bp = [[None] * (L + 1) for _ in range(W + 1)]
    f[0][0] = 0.0
    # prefix kana strings, for fast lookup of a word span's text
    pref = [""]
    for wk in words_kana:
        pref.append(pref[-1] + wk)

    for i in range(W + 1):
        for k in range(L + 1):
            if f[i][k] == NEG:
                continue
            if i < W:  # skip word i (interlude noise / hallucination)
                cand = f[i][k] - skip_penalty
                if cand > f[i + 1][k]:
                    f[i + 1][k], bp[i + 1][k] = cand, ("skip", i, k)
            if k < L:  # assign words i..j-1 to line k
                target = lines_kana[k]
                for j in range(i + 1, min(i + max_span, W) + 1):
                    chunk = pref[j][len(pref[i]):]
                    if len(chunk) > 2 * len(target) + 6:
                        break
                    sim = difflib.SequenceMatcher(None, target, chunk).ratio()
                    cand = f[i][k] + sim * max(len(target), 1)
                    if cand > f[j][k + 1]:
                        f[j][k + 1], bp[j][k + 1] = cand, ("line", i, k)
    # allow skipping trailing words: take the best f[i][L]
    best_i = max(range(W + 1), key=lambda i: f[i][L])
    if f[best_i][L] == NEG:
        die("DP alignment failed (too few ASR words? Try --dry-run to inspect the transcription)")
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
        die("DP backtrace incomplete; retry with a higher --max-span")
    return spans, f[best_i][L]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--vocals", type=Path, default=None,
                    help="vocals to align against; default: the single vocals_ref_*.wav under <project>/inst/")
    ap.add_argument("--lyrics", type=Path, default=None,
                    help="default: <project>/lyrics/final.md")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <project>/refs/line_times.tsv")
    ap.add_argument("--model", default="large-v3-turbo")
    ap.add_argument("--lang", default="ja", choices=["ja", "zh"],
                    help="lyrics language: ja = align on kana, zh = align on Han characters")
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    ap.add_argument("--max-span", type=int, default=40,
                    help="max number of ASR words a single line may absorb")
    ap.add_argument("--lead-in", type=float, default=0.15,
                    help="seconds a subtitle appears ahead of the vocal onset")
    ap.add_argument("--tail", type=float, default=0.35,
                    help="seconds a subtitle lingers past the end of the line")
    ap.add_argument("--dry-run", action="store_true",
                    help="only print the alignment table, write nothing")
    args = ap.parse_args()
    proj = resolve_project(args)
    args.vocals = args.vocals or default_vocals(proj)
    args.lyrics = args.lyrics or proj / "lyrics" / "final.md"
    args.out = args.out or proj / "refs" / "line_times.tsv"

    for p in (args.vocals, args.lyrics):
        if not p.is_file():
            die(f"file not found: {p}")
    lyrics = parse_lyrics(args.lyrics)  # {n: (main line, sub line)}
    order = sorted(lyrics)
    norm = make_norm_fn(args.lang)
    lines_kana = [norm(lyrics[n][0]) for n in order]

    words = transcribe(args.vocals, args.model, args.device, args.lang)
    if len(words) < len(order):
        die(f"ASR produced only {len(words)} words, fewer than {len(order)} lines; cannot align")
    words_kana = [norm(t) for _, _, t in words]

    spans, score = align(lines_kana, words_kana, max_span=args.max_span)
    print(f"[align] DP total score {score:.1f} (max ≈ {sum(len(k) for k in lines_kana)})\n")

    rows, warn = [], []
    print(f"{'ln':>3} {'start':>7} {'end':>7} {'sim':>5}  ASR transcription → lyric")
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

    # subtitle shaping: lead-in/tail padding, without overlapping adjacent lines
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
        print(f"\n[align] ⚠ lines with similarity < 50%: {warn} — their timing may be off; spot-check these first")
    if args.dry_run:
        print("[align] --dry-run, nothing written")
        return
    hdr = ("# line\tstart\tend\treference (keep the column order; end may be left blank)\n"
           "# Auto-generated by scripts/auto_line_times.py (ASR) — this is a first draft;\n"
           "# spot-check the first line / chorus / post-interlude lines before release; fix global offsets with make_subs.py --shift\n")
    body = "".join(f"{n}\t{s:.2f}\t{e:.2f}\t{lyrics[n][0]}\n" for n, s, e in out_rows)
    args.out.write_text(hdr + body, encoding="utf-8")
    print(f"[align] wrote {args.out} ({len(out_rows)} lines)")


if __name__ == "__main__":
    main()
