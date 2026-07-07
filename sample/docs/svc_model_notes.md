# Higashi Yukiren so-vits-svc 4.1 Model Package — Inventory and Renaming Log

Original download package name: `AI东雪莲翻唱模型、数据集/` ("AI Higashi Yukiren cover model & dataset"; moved in 2026-07-04, original filenames → current paths):

| Original filename | Current path (models/higashi_yukiren/) | Size | Notes |
|---|---|---|---|
| Sovits4.1东雪莲主模型.pth | `G_azuma_release.pth` | 154 MB | Generator, compressed release build (full G is ~540MB; sufficient for inference, cannot be trained further) |
| Sovits4.1东雪莲主配置文件.json | `config.json` | 4 KB | See key points below |
| Sovits4.1东雪莲扩散模型.pt | `diffusion/model_azuma.pt` | 211 MB | Shallow diffusion model |
| Sovits4.1东雪莲扩散配置文件.yaml | `diffusion/diffusion.yaml` | 4 KB | k_step_max=0 (full-depth diffusion; both -shd and -od are usable) |
| 东雪莲唱歌数据集7.15.zip | `dataset/azuma_vocal_dataset_7.15.zip` | 2.1 GB | Training data (2194 wav files); not needed for inference, archived only |

The entire `models/` directory has been added to .gitignore (previously only `*.pth` was ignored, so .pt/.zip files could be committed by mistake).

## config.json key points

- **Speaker name: `AzumaVocal`** (`scripts/svc_infer.py` reads it automatically and passes it as -s)
- speech_encoder: **vec768l12** (the 4.1 default), ssl_dim 768
- sampling_rate: 44100, single speaker
- No cluster model / feature-retrieval index → cluster_infer_ratio stays fixed at 0 in batch runs; that dimension needs no sweep

## Inference prerequisites (under pretrain/ in the so-vits-svc checkout)

1. `pretrain/checkpoint_best_legacy_500.pt` — ContentVec encoder weights (required for vec768l12).
   The 199MB hubert_base.pt, renamed, works as a substitute (the official README says the results are identical).
2. `pretrain/rmvpe.pt` — f0 prediction (yxlllc/RMVPE 230917 build; rename model.pt after unzipping).
3. **Shallow diffusion only**: the vocoder path in diffusion.yaml is
   `pretrain/nsf_hifigan_finetuned/model` (a **non-standard path** — a vocoder fine-tuned by the
   model's author, not included in the download package). Before running -shd, do one of:
   - Ask the model's release page for nsf_hifigan_finetuned;
   - Or put the standard nsf_hifigan_20221211 at that path / change the yaml's vocoder.ckpt back to
     `pretrain/nsf_hifigan/model` (the sound may differ slightly from what the author intended).

Plain sovits inference (without -shd/-eh) only needs the first two.
