<img src="assets/thanks_banner_v2.svg" width="340" align="right" alt="Special thanks to Claude Fable">

<h1>SVC-Cover-Pipeline</h1>

A command-line pipeline for AI singing covers: 

Synthesizer V source vocals →
[so-vits-svc 4.1](https://github.com/svc-develop-team/so-vits-svc) voice
conversion → mix, subtitles, and release video with ffmpeg.

`scripts/` is song-agnostic; each song lives in its own project directory,
selected with `--project <dir>` (default `$SVC_PROJECT`). `sample/` is a
complete example from a real production.

## Showcase

<div align="center">
  <a href="https://www.bilibili.com/video/BV14kMh6WEH9/">
    <img src="southeast_ascetic_mountain_funk/refs/Cover.png" width="680"
         alt="Southeast Yukiren Mountain Funk: cover art, links to the Bilibili video">
  </a>
  <p>
    <b>《東南苦行山》でも冬雪蓮がベースを抱えた｜東南雪蓮山 Funk Remix</b><br>
    <i>Dōngnán Xuelian Mountain Funk Remix | Fan-made Meme Edit</i><br>
    <sub>A funk cover of "Dongnan Shan" in Higashi Yukiren's voice:
    separation, SVC, mix, and release video all produced with this pipeline.</sub>
  </p>
  <p>
    <a href="https://www.bilibili.com/video/BV14kMh6WEH9/">
      <img src="https://img.shields.io/badge/Bilibili-%E2%96%B6%EF%B8%8E%20Watch-00A1D6?style=for-the-badge&logo=bilibili&logoColor=white"
           alt="Watch on Bilibili"></a>
    &nbsp;
    <a href="https://www.youtube.com/watch?v=Qq7K7ZKNZag">
      <img src="https://img.shields.io/badge/YouTube-%E2%96%B6%EF%B8%8E%20Watch-FF0000?style=for-the-badge&logo=youtube&logoColor=white"
           alt="Watch on YouTube"></a>
  </p>
  <sub>Published with an AI-generated-content label ·
  project files in <a href="southeast_ascetic_mountain_funk/"><code>southeast_ascetic_mountain_funk/</code></a></sub>
</div>

## Contents

- [Layout](#layout)
- [Requirements](#requirements)
- [Workflow](#workflow)
- [Example projects](#example-projects)
- [Attribution and usage](#attribution-and-usage)
- [Acknowledgments](#acknowledgments)
- [License](#license)

## Layout

```
SVC-Cover-Pipeline/
├── scripts/                  # generic pipeline: song-agnostic
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
├── assets/                   # README art
├── sample/                   # example project: see "Example projects" below
├── southeast_ascetic_mountain_funk/   # released cover: see "Showcase" above
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

## Example projects

Two real productions are included as examples. Audio, video, and model weights
are excluded (see `.gitignore`); only the text and image assets that document
the process are kept.

### `sample/`: "Nian Zhang Shi" (Japanese adaptation)

A Japanese-language cover with adapted lyrics, converted to the voice of
Higashi Yukiren. The fullest example of the lyric-writing phases:

- `lyrics/`: draft revisions (v1 → v3) and `final.md`, a
  lyrics / romaji / English-gloss table with per-line mora counts
- `refs/`: the mora budget and subtitle-timing TSVs, cover art
- `docs/`: phase-by-phase working notes covering mora verification, SynthV
  tuning, the SVC parameter-grid comparison, and mixing/release

### `southeast_ascetic_mountain_funk/`: "Dongnan Shan" funk cover (released)

A direct cover (no lyric adaptation) whose source vocals came from the
original track via separation + dereverb instead of SynthV. The released
video is linked in [Showcase](#showcase):

- `lyrics/final.md`: original Chinese lyrics with a Japanese subtitle gloss
- `refs/`: ASR-aligned subtitle timing, extracted melody MIDI, cover art
- `docs/`: MIDI extraction report and the SVC parameter grid

## Attribution and usage

Covers produced with this pipeline are for personal, non-commercial use. When
publishing, credit the original composer and lyricist (including the author of
any lyric version yours derives from) and follow your platform's AI-generated
content labeling rules. Voice models, audio, and model weights are not tracked
in this repository.

## Acknowledgments

This project is developed with [Claude Code](https://claude.com/claude-code)
(Claude Fable 5): pipeline scripts, lyric revision tooling, and documentation
were written in collaboration, with the model credited as co-author in the
commit history. Listening judgments, SynthV tuning, and final picks are human.

## License

The pipeline code is licensed under the GNU General Public License v3.0; see
[LICENSE](LICENSE). Song data under project directories (lyrics, reference
material) is not covered by this license and remains subject to the rights of
its original authors.
