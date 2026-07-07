# 东雪莲 so-vits-svc 4.1 模型包 — 清点与重命名记录

下载包原名:`AI东雪莲翻唱模型、数据集/`(2026-07-04 移入,原文件名 → 现路径):

| 原文件名 | 现路径 (models/higashi_yukiren/) | 大小 | 说明 |
|---|---|---|---|
| Sovits4.1东雪莲主模型.pth | `G_azuma_release.pth` | 154 MB | 生成器,已压缩发布版(完整 G 约 540MB,推理够用,不能继续训练) |
| Sovits4.1东雪莲主配置文件.json | `config.json` | 4 KB | 见下方要点 |
| Sovits4.1东雪莲扩散模型.pt | `diffusion/model_azuma.pt` | 211 MB | 浅扩散模型 |
| Sovits4.1东雪莲扩散配置文件.yaml | `diffusion/diffusion.yaml` | 4 KB | k_step_max=0(全程扩散,-shd 和 -od 都可用) |
| 东雪莲唱歌数据集7.15.zip | `dataset/azuma_vocal_dataset_7.15.zip` | 2.1 GB | 训练数据(2194 条 wav),推理不需要,仅存档 |

整个 `models/` 已加入 .gitignore(此前只有 `*.pth`,.pt/.zip 会被误 commit)。

## config.json 要点

- **speaker 名:`AzumaVocal`**(`scripts/svc_infer.py` 自动读取,-s 传这个)
- speech_encoder: **vec768l12**(4.1 默认),ssl_dim 768
- sampling_rate: 44100,单说话人
- 无聚类模型/特征检索索引 → 跑批时 cluster_infer_ratio 固定 0,该维度不用扫

## 推理前置(so-vits-svc checkout 的 pretrain/ 下)

1. `pretrain/checkpoint_best_legacy_500.pt` — ContentVec 编码器权重(vec768l12 必需)。
   可用 199MB 的 hubert_base.pt 改名替代(官方 README 称效果一致)。
2. `pretrain/rmvpe.pt` — f0 预测(yxlllc/RMVPE 230917 版,解压后 model.pt 改名)。
3. **浅扩散专用**:diffusion.yaml 里 vocoder 路径是
   `pretrain/nsf_hifigan_finetuned/model`(**非标准路径**,模型作者微调过的
   vocoder,下载包里没有)。跑 -shd 前二选一:
   - 找模型发布页要 nsf_hifigan_finetuned;
   - 或把标准 nsf_hifigan_20221211 放到该路径 / 把 yaml 的 vocoder.ckpt 改回
     `pretrain/nsf_hifigan/model`(音质可能与作者预期略有差异)。

纯 sovits 推理(不开 -shd/-eh)只需要前两项。
