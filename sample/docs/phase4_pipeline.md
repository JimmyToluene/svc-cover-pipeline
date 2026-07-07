# Phase 4 Pipeline — Separation / Mixing / Subtitles / Release

Four scripts, two environments:

| Script | What it does | Environment |
|---|---|---|
| `scripts/separate.py` | Instrumental separation fallback (BS-Roformer, optional second de-reverb pass) | conda `phase4` |
| `scripts/mix.py` | Vocal chain + track merge + -14 LUFS mastering | conda `phase4` |
| `scripts/make_subs.py` | final.md → bilingual .ass subtitles | any python3 (stdlib only) |
| `scripts/make_release.py` | Cover + audio + subtitles → release.mp4 | any python3 + ffmpeg |

The `phase4` environment: `conda create -n phase4 python=3.11 -y && conda activate phase4 && pip install -r requirements.txt`.
**Do not install it into the sovits env** (librosa version conflict, see the comment in requirements.txt).

## 1. Instrumental (priority order, per the CLAUDE.md convention)

1. **Look for an official instrumental first** (instrumental/project files published by the author of the original Chinese version; search Bilibili/5sing/NetEase Cloud Music) — only you can do this step.
2. Not found → separate the Anon version: `python scripts/separate.py`
   → `inst/inst_from_anon_version.wav` + `inst/vocals_ref_anon_version.wav` (keep the latter as a subtitle-timing reference).
   If you hear vocal reverb residue in the instrumental → rerun with `--dereverb` and A/B the two versions.
3. Still no good → `--input <original Chinese audio>`.

## 2. Mixing (after Phase 3 has produced selected.wav)

```bash
python scripts/mix.py --inst inst/inst_from_anon_version.wav
# vocal defaults to vocal/svc_out/selected.wav, output goes to output/final_mix.wav
```

- Timing misaligned → `--vocal-shift <seconds>` (positive = delay the vocal);
- A/B baseline = `refs/anon_version.mp3`: vocal level (`--vocal-offset`, start at -1.5) and
  reverb amount (`--reverb-wet`, start at 0.15) must be no worse than the reference version;
- Every run prints the measured LUFS/peak; record the final parameters in the postmortem.

## 3. Subtitles

```bash
python3 scripts/make_subs.py        # first run: generates the refs/line_times.tsv template to fill in
# fill in the timeline (align against inst/vocals_ref_*.wav or the SynthV project), then run again:
python3 scripts/make_subs.py        # → output/subs.ass
```

Time format: seconds (`85.3`) or min:sec (`1:25.3`); end times may all be left blank (each extends automatically to the next line).
If everything is uniformly off, use `--shift`; do not adjust line by line.
A line number with an `r` suffix (`7r`) = that lyric line is sung a second time; lines not sung in the audio may be absent, but then add `--partial`.

A first-draft timeline can be generated automatically (ASR word-level alignment, needs a GPU; still spot-check before release):

```bash
conda run -n phase4 python scripts/auto_line_times.py --dry-run   # inspect the alignment table first
conda run -n phase4 python scripts/auto_line_times.py             # writes line_times.tsv
```

The current `refs/line_times.tsv` (2026-07-05) is a hand-curated version: ASR + RMS segmentation cross-verified,
following the audio's actual 20-line structure (see the appendix in docs/phase0_notes.md). Do not blindly rerun and overwrite it.

## 4. Release video

v1 (static single image):

```bash
python3 scripts/make_release.py --cover refs/cover.png
# → output/release.mp4 (1080p, static cover, subtitles burned in, duration cut precisely to the audio)
```

v2 (cover intro + content-image background + bilingual subtitles; the main route since 2026-07-05):

```bash
# Bottom-subtitle version (main line):
python3 scripts/make_release_v2.py \
    --audio output/preview_mix.wav --out output/preview_v2.mp4 --no-wave \
    --cover refs/Azuma_Cover_v2.png --content refs/Azuma_Content_v2.png
# Blackboard-lyrics version (variant: lyrics written inside the empty blackboard in Content_v2):
python3 scripts/make_subs.py --partial --board       # → output/subs_board.ass
python3 scripts/make_release_v2.py \
    --audio output/preview_mix.wav --out output/preview_v2_board.mp4 --no-wave \
    --cover refs/Azuma_Cover_v2.png --content refs/Azuma_Content_v2.png \
    --subs output/subs_board.ass
# Image sources (newly delivered by the user 2026-07-05, generated with ChatGPT): Azuma_Cover_v2 = cover
# ("Nian Zhang Shi" / AI cover version / to the teacher in our memories), Azuma_Content_v2 = empty
# blackboard night scene; the old Azuma_Backgroud/Azuma_Content are deprecated and moved out of refs/
# (recover them from git history 59563f2 if needed).
# The cover is shown until 2s before the first line, then fades out over 1.5s; the cover also serves as the mp4 thumbnail.
# Waveform animation: user decided against it (2026-07-05); always pass --no-wave (the flag is kept as a spare).
```

Pitfall: PyCharm Remote Dev points `FONTCONFIG_PATH` at a private directory containing only Western fonts,
so libass cannot find Noto CJK → tofu-block subtitles. make_release_v2.py already strips that variable automatically;
when burning subtitles with ffmpeg by hand, remember `env -u FONTCONFIG_PATH`. The CJK fonts are at
`~/.local/share/fonts/NotoSansCJKjp-*.otf` (the CN style also uses the JP fonts, which include Simplified Chinese glyphs).

## Pre-release red lines (CLAUDE.md, non-negotiable)

- [ ] Credit the original lyricist (uploader of BV139Gm6REz6) in the video description; ideally reach out to them beforehand
- [ ] Bilibili AI-generated-content label
- [ ] Write the full-pipeline parameters into `docs/postmortem.md` (sovits parameters, mix parameters, timeline)
