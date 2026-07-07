# SynthV from Zero, Hands-On — Free Route + Melody MIDI Import (researched and verified 2026-07-04)

Goal: one clean dry vocal singing the **v3 new lyrics** → `vocal/synthv_source.wav`.
This doc only covers how to produce it; line-by-line singing directions are in `docs/synthv_notes.md`.

## 0. Which version to use (research conclusions, checked against official docs)

| Route | Cost | Key limitations | Verdict |
|---|---|---|---|
| **Studio 1 Basic + Japanese AI lite voice database** | Completely free | lite quality ceiling is low, rendering locked to Prefer Speed; 3 tracks (enough); parameter panel (tension/breathiness) **is available** | **Recommended, start here** |
| Studio 2 Core (free) + Mai 2 | Free | DAW-plugin form only (no standalone app), distribution mechanism unclear | Backup |
| Studio 2 Pro 14-day trial | Free trial | **Trial voice databases forbid audio export** — useless for us | Ruled out |
| Studio 2 Pro purchase | ~$99 + voice database | None | Revisit only if lite quality truly falls short |

Key points:
- **Studio 2 is not compatible with V1 lite voice databases** (officially stated); the free route can only use the older Studio 1 Basic.
- **Dreamtonics has announced it is discontinuing distribution of its own lite voice databases**; the resource server is still up for now —
  **download and stockpile them ASAP**.
- The lite quality ceiling has limited impact on this project: SVC will replace the timbre wholesale; **articulation clarity** is
  what must be preserved. Try it first; consider the paid version only if it comes out mushy.

## 1. Download & install (one-time, ~20 minutes)

1. Editor: Studio 1 Basic installer (still hosted on AHS's official site):
   <https://www.ah-soft.com/trial/synth-v.html> (Windows/macOS/Linux all available)
2. Voice database (lite directory; pick one Japanese female AI lite, download the `.svpk`):
   <https://resource.dreamtonics.com/download/English/Voice%20Databases/Lite%20Voice%20Databases/>
   Candidates: **Saki AI Lite** (most commonly used), 小春六花 (rikka-ai-lite), 夏色花梨, 鶴巻マキ,
   重音テト. To install: drag the .svpk into SynthV or double-click it.
3. License red line: lite output is **non-commercial** (no Bilibili charging/sponsored content), and the release
   description must state 「Synthesizer V ○○ AI ライト版使用」. Add this to the release checklist.

## 2. Create the project (parameters already measured)

- New project, **BPM 132.5** (measured with librosa; if beat-matching reveals it is half/double time, use 66.25/265), 4/4.
- Drag `refs/anon_version.mp3` into an instrumental track as a beat-matching reference.

## 3. Import the melody MIDI (skips transcribing the melody line by line)

`refs/vocals_ref_anon_version_basic_pitch.mid` is the melody auto-transcribed from the separated vocals
(basic-pitch, 386 notes, range F3–C6, vocals enter at 16.1s). File → Import into the main vocal track, then trim:

- **Target note count is 342** (total mora count 341 + 1 note split on line 23); there are currently 386. The ~40 extras are
  transcription fragments: delete very short notes (< 1/32), merge fragmented slurs at the same pitch, and remove isolated notes with obvious octave-jump errors.
- Verify line by line: each line's note count must equal that line's quota in `refs/mora_budget.tsv` (line 23 = 14).
  This is a hard check — a mismatch means that line was trimmed wrong; do not force the lyrics onto it anyway.
- Drag notes with off timing into place against the instrumental track / original song. The auto-transcription's pitch errors
  cluster at phrase starts/ends and breathy passages — check those closely.

## 4. Paste the lyrics

Box-select all notes of one line → paste the corresponding line from `lyrics/synthv_input.txt` (space-separated,
one token per note). Then check against the "singing convention notes" in `lyrics/final.md`:
geminate (sokuon) / long vowel (chōon) each take one note (so-っ-to, cho-o-ku), leave (rest) positions without notes, line 11 is sung shi-zu,
line 16 is sung ho-e. If a sokuon lands on the wrong note, manually change that note's lyric to っ.

## 5. Tuning → export

- Work section by section per `docs/synthv_notes.md` (it was written for exactly this step).
- Export: Render panel → WAV; pick 48000 for the sample rate if offered, otherwise 44100 (the batch script
  resamples automatically, so it doesn't matter), **with no effects applied** → `vocal/synthv_source.wav`.
- Before handing it off, go through the checklist at the end of `docs/synthv_notes.md`.

## Common pitfalls

- lite voice databases lock the render mode to Prefer Speed: it is normal not to find a quality option before export — just export as is.
- If pasted romaji is pronounced wrong, check は/へ: the input file already writes them phonetically as wa/e;
  if you add words by hand, do not write the kana particles in their orthographic form.
- If the BPM doesn't match what you hear (feels twice as slow), build the project at 66.25; MIDI note timing is unaffected
  (MIDI stores absolute time, converted).
