# Phase 4 流水线 — 分离 / 混音 / 字幕 / 出片

四个脚本,依赖两套环境:

| 脚本 | 干什么 | 环境 |
|---|---|---|
| `scripts/separate.py` | 伴奏分离兜底(BS-Roformer,可选去混响二遍) | conda `phase4` |
| `scripts/mix.py` | 人声链 + 合轨 + -14 LUFS 母带 | conda `phase4` |
| `scripts/make_subs.py` | final.md → 双语 .ass 字幕 | 任意 python3(纯标准库) |
| `scripts/make_release.py` | 封面 + 音频 + 字幕 → release.mp4 | 任意 python3 + ffmpeg |

`phase4` 环境:`conda create -n phase4 python=3.11 -y && conda activate phase4 && pip install -r requirements.txt`。
**不要装进 sovits env**(librosa 版本冲突,见 requirements.txt 注释)。

## 1. 伴奏(优先级顺序,CLAUDE.md 约定)

1. **先找官方伴奏**(中文原版作者发布的伴奏/工程,B 站/5sing/网易云搜)——这步只能你来。
2. 找不到 → 分离爱音版:`python scripts/separate.py`
   → `inst/inst_from_anon_version.wav` + `inst/vocals_ref_anon_version.wav`(后者留作字幕对轴参照)。
   伴奏里听到人声混响残留 → 重跑加 `--dereverb`,两版 A/B。
3. 还不行 → `--input <中文原版音频>`。

## 2. 混音(等 Phase 3 选出 selected.wav 后)

```bash
python scripts/mix.py --inst inst/inst_from_anon_version.wav
# 人声默认 vocal/svc_out/selected.wav,输出 output/final_mix.wav
```

- 对拍不齐 → `--vocal-shift 秒数`(正=人声延后);
- A/B 基准 = `refs/anon_version.mp3`:人声电平(`--vocal-offset`,-1.5 起步)、
  混响量(`--reverb-wet`,0.15 起步)不劣于参照版;
- 每次跑都会打印实测 LUFS/峰值,定稿参数记进 postmortem。

## 3. 字幕

```bash
python3 scripts/make_subs.py        # 首次:生成 refs/line_times.tsv 待填模板
# 填时间轴(对轴参照 inst/vocals_ref_*.wav 或 SynthV 工程),再跑一次:
python3 scripts/make_subs.py        # → output/subs.ass
```

时间格式:秒(`85.3`)或 分:秒(`1:25.3`);结束时间可全留空(自动接到下一行)。
整体不齐时用 `--shift`,不要逐行改。

## 4. 出片

```bash
python3 scripts/make_release.py --cover refs/cover.png
# → output/release.mp4(1080p,静态封面,字幕烧录,时长按音频精确截断)
```

封面图需你准备(任意分辨率,自动加黑边到 16:9)。

## 发布前红线(CLAUDE.md,不可协商)

- [ ] 视频简介署名原填词作者(BV139Gm6REz6 UP 主),最好事先打过招呼
- [ ] B 站 AI 生成内容标注
- [ ] `docs/postmortem.md` 写齐全链参数(sovits 参数、混音参数、时间轴)
