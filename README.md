# svc-cover-pipeline

A command-line pipeline for producing AI singing covers: source vocals are
synthesized in Synthesizer V, converted to the target voice with
[so-vits-svc 4.1](https://github.com/svc-develop-team/so-vits-svc), then mixed,
subtitled, and rendered into a release video with ffmpeg.

The repository separates the reusable pipeline from song data: `scripts/` is
song-agnostic, and each song lives in its own project directory. Every script
takes `--project <dir>` (default: the `$SVC_PROJECT` environment variable),
and resolves all of its default paths inside that directory. `sample/` is a
complete example project taken from a real production.

## Contents

- [Layout](#layout)
- [Requirements](#requirements)
- [Workflow](#workflow)
- [Sample project](#sample-project)
- [Attribution and usage](#attribution-and-usage)
- [License](#license)

## Layout

```
svc-cover-pipeline/
├── scripts/                  # generic pipeline — song-agnostic
│   ├── project_paths.py      #   shared --project resolution
│   ├── new_project.py        #   scaffold a new song project
│   ├── separate.py           #   split reference audio into instrumental + vocals (BS-Roformer)
│   ├── svc_infer.py          #   so-vits-svc inference over a parameter grid
│   ├── mix.py                #   vocal chain, loudness-matched mixdown (-14 LUFS)
│   ├── auto_line_times.py    #   ASR subtitle-timing draft (faster-whisper + DP alignment)
│   ├── make_subs.py          #   bilingual .ass subtitles from lyrics + timing
│   ├── make_release.py       #   static-cover release video
│   └── make_release_v2.py    #   two-image release video with animated waveform
├── requirements.txt
├── sample/                   # example project — see "Sample project" below
└── <project>/                # one directory per song, created by new_project.py
    ├── refs/                 #   reference audio, mora budget, subtitle timing
    ├── lyrics/               #   drafts and final.md (lyrics / romaji / gloss)
    ├── vocal/                #   SynthV dry vocal; svc_out/ = conversion results
    ├── models/               #   so-vits-svc model dir (G_*.pth + config.json, optional diffusion)
    ├── inst/                 #   instrumental (provided or separated)
    ├── output/               #   mix, subtitles, release video
    └── docs/                 #   per-song notes and comparison tables
```

## Requirements

- Python 3.11, system ffmpeg.
- `pip install -r requirements.txt` in a dedicated environment for separation,
  mixing, and ASR alignment. Do not install it into the so-vits-svc
  environment; the pinned librosa versions conflict.
- A local so-vits-svc 4.1-Stable checkout with its own environment for
  `svc_infer.py` (passed via `--svc-repo`, interpreter via `--python`).
- `make_subs.py` and `make_release*.py` need only the standard library and
  ffmpeg.

## Workflow

```sh
python scripts/new_project.py mysong
# Put reference audio in mysong/refs/ and the SVC model dir in mysong/models/<name>/.

# 1. Instrumental + reference vocals from the reference track
python scripts/separate.py --project mysong

# 2. Write lyrics, synthesize the dry vocal in SynthV, export to
#    mysong/vocal/synthv_source.wav, then run the conversion grid
python scripts/svc_infer.py --project mysong --svc-repo ~/so-vits-svc -t 0
# Blind-pick a result and copy it to mysong/vocal/svc_out/selected.wav.

# 3. Mix against the instrumental
python scripts/mix.py --project mysong --inst mysong/inst/<instrumental>.wav

# 4. Subtitles: ASR timing draft, then render .ass
python scripts/auto_line_times.py --project mysong
python scripts/make_subs.py --project mysong

# 5. Release video
python scripts/make_release_v2.py --project mysong \
    --cover mysong/refs/cover.png --content mysong/refs/content.png
```

Every script supports `--help`; defaults not listed here follow the
`<project>/` layout above.

## Sample project

`sample/` is a snapshot of the text assets from a finished production — a
Japanese-language cover of "Nian Zhang Shi" converted to the voice of Higashi
Yukiren. It shows what each part of a project directory looks like in practice:

- `sample/lyrics/` — draft revisions (v1 → v3) and `final.md`, a
  lyrics / romaji / English-gloss table with per-line mora counts
- `sample/refs/` — the mora budget and subtitle-timing TSVs, cover art
- `sample/docs/` — phase-by-phase working notes: mora verification, SynthV
  tuning notes, the SVC parameter-grid comparison, and mixing/release notes

Audio, video, and model weights are excluded (see `.gitignore`); only the
text and image assets that document the process are kept.

## Attribution and usage

Covers produced with this pipeline are for personal, non-commercial use. When
publishing, credit the original composer and lyricist (including the author of
any lyric version yours derives from) and follow your platform's AI-generated
content labeling rules. Voice models, audio, and model weights are not tracked
in this repository.

## License

The pipeline code is licensed under the GNU General Public License v3.0; see
[LICENSE](LICENSE). Song data under project directories (lyrics, reference
material) is not covered by this license and remains subject to the rights of
its original authors.
