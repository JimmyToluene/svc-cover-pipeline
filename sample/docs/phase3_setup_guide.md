# Phase 2/3 Hands-On Guide — SynthV Dry Vocal + sovits Environment + Running the Grid

The two tracks can run in parallel; track 2 takes about 30–60 minutes in one sitting, track 1 is the bulk of the work.
Machine: RTX 4090 48G / driver 580 (CUDA 12 compatible), conda 26.x.

## Track 2 — so-vits-svc 4.1 environment (can be done first; enables an immediate smoke test once finished)

> 2026-07-04 implementation log (track 2 complete, smoke test passed 2/2, including shallow diffusion;
> **the user has listened and confirmed the smoke-test output is Higashi Yukiren's voice**, closing the loop on pipeline validation):
> the checkout's actual path is `~/so-vits-sv` (missing a c), env = conda `sovits`
> (python 3.10, **torch 2.5.1+cu124** — downgraded after hitting two era-mismatch pitfalls on 2.12, see step 4).
> ffmpeg was installed into the env (conda-forge) rather than system-wide, so running svc_infer.py needs the
> `PATH=~/miniforge3/envs/sovits/bin:$PATH` prefix, or activate the env first.
> The vocoder uses the standard version symlinked to stand in for the finetuned one (`nsf_hifigan_finetuned -> nsf_hifigan`).
> svc_infer.py injects TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 into its subprocesses (in case torch gets upgraded someday).
> Measured on the 4090: 15s of audio takes 4-5s per combination; the whole 6-combination grid takes about half a minute.

```bash
# 1. System dependencies (needed by svc_infer.py's input downmix; no sudo → install via conda, see the log above)
sudo apt install -y ffmpeg unzip

# 2. Dedicated environment (upstream pins an old Python; 3.10 verified to still install fairseq — anything newer tends to blow up)
conda create -n sovits python=3.10 -y
conda activate sovits

# 3. Code (4.1-Stable branch)
git clone -b 4.1-Stable --depth 1 https://github.com/svc-develop-team/so-vits-svc.git ~/so-vits-svc
cd ~/so-vits-svc

# 4. Dependencies: torch first, then requirements. Two [verified pitfalls]:
#    (a) pip>=24.1 rejects omegaconf 2.0.x's legacy metadata → fairseq resolution becomes unsolvable; downgrade pip first;
#    (b) torch must be pinned to 2.5.1 (same era as sovits 4.1): torch>=2.6's weights_only
#        default refuses to load fairseq checkpoints, and torchaudio>=2.9's load() additionally requires torchcodec.
pip install "pip<24.1"
pip install torch==2.5.1 torchaudio==2.5.1
pip install -r requirements.txt

# 5. Two required weights → pretrain/
wget -O pretrain/checkpoint_best_legacy_500.pt \
  https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt
wget https://github.com/yxlllc/RMVPE/releases/download/230917/rmvpe.zip
unzip rmvpe.zip -d /tmp/rmvpe && mv /tmp/rmvpe/model.pt pretrain/rmvpe.pt && rm rmvpe.zip

# 6. (Optional, for shallow diffusion) vocoder. First look for nsf_hifigan_finetuned on the model's release page;
#    if it can't be found, use the standard version instead and symlink it so diffusion.yaml's non-standard path also resolves:
wget https://github.com/openvpi/vocoders/releases/download/nsf-hifigan-v1/nsf_hifigan_20221211.zip
unzip nsf_hifigan_20221211.zip -d pretrain/ && rm nsf_hifigan_20221211.zip
ln -s nsf_hifigan pretrain/nsf_hifigan_finetuned
```

**Smoke test (no need to wait for SynthV)**: any clip with vocals will do, quality irrelevant —
it only verifies the whole chain runs (model loading, rmvpe, output collection):

```bash
cd ~/ai_mad
ffmpeg -ss 60 -t 15 -i refs/anon_version.mp3 /tmp/smoke.wav
python3 scripts/svc_infer.py --svc-repo ~/so-vits-svc \
    --python ~/miniforge3/envs/sovits/bin/python \
    --input /tmp/smoke.wav -t 0 --shd off
# Listen to vocal/svc_out/smoke_f0rmvpe_t+0.wav: if it comes out in Higashi Yukiren's voice (even with instrumental bleed smearing the background) = the chain is OK
# If the vocoder is installed, drop --shd off and verify shallow diffusion while you're at it
```

Once you've listened, the smoke-test output can be deleted (`rm vocal/svc_out/smoke_*`, and delete the corresponding batch section in `docs/svc_grid.md`).

## Track 1 — SynthV dry vocal (the bulk of the work)

`docs/synthv_notes.md` is authoritative for the details; this is the order of operations:

1. New project, sample rate 48kHz; first set the BPM and bar lines against `refs/anon_version.mp3`.
2. Transcribe pitch/timing by ear, line by line, into the piano roll (the mp3 is authoritative); each line's note count = the `refs/mora_budget.tsv`
   budget (line 23 is 14).
3. Lyric input: box-select all notes of one line → paste the corresponding line of `lyrics/synthv_input.txt`
   (space-separated tokens are assigned note by note). If a geminate (sokuon) t is assigned wrong, manually change that note's lyric to っ (phoneme cl).
4. Targeted checks: geminates (sokuon) and long vowels (chōon) each occupy one note (so-っ-to, cho-o-ku); the line 23 note split
   (whichever of づ/な has the longer duration gets split in half to give a note to け; け ≥ a 1/16-note).
5. Tune section by section per `docs/synthv_notes.md` (verse A restrained → chorus vibrato straight-in-vibrato-out →
   line 19 breathiness maximum → line 20 lecturing-tone peak → line 25 fade-out finish). Start with global vibrato depth at ~0.6x.
6. Export the dry vocal (**single female-voice-database route**, decided 2026-07-04): **no reverb, no effects**,
   48kHz WAV → `vocal/synthv_source.wav` (the batch script's default input).
   Reaching "no pronunciation errors, phrases hold together" is enough to hand off for conversion — don't over-polish.
7. Go through the export checklist at the end of `docs/synthv_notes.md`.

## Merge point — Phase 3 grid and blind listening

```bash
# The female voice database is close to Higashi Yukiren's range, so run only t=0 first (2 combinations: pure sovits / shallow diffusion)
export PATH=~/miniforge3/envs/sovits/bin:$PATH
python3 scripts/svc_infer.py --svc-repo ~/so-vits-sv \
    --python ~/miniforge3/envs/sovits/bin/python \
    --input vocal/synthv_source.wav -t 0
# Only if it sounds muffled/shrill (octave suspect) run the extra pass: ... -t 12 -12
```

Blind-listen to `vocal/svc_out/` and write your notes into `docs/svc_grid.md`. Criteria:

- **transpose direction**: sounds muffled, like singing with a pressed throat → needs +12; sounds shrill, falsetto-like, articulation crumbles → needs −12;
  natural and convincing → 0 is correct. The male-voice-database route almost certainly needs +12.
- **Shallow diffusion (shd) version**: electronic/metallic artifacts clearly reduced → pick shd; can't hear a difference → pick non-shd (simpler).
- **Comparing the two routes**: whichever voice database's output sounds more like Higashi Yukiren herself singing, with clearer articulation, wins.

Once picked:

```bash
cp vocal/svc_out/<your_chosen_file>.wav vocal/svc_out/selected.wav
```

Then tell me which version you picked + briefly why (it goes into the postmortem); Phase 3 is done, on to Phase 4 mixing.
