# Phase 2/3 实操指南 — SynthV 干声 + sovits 环境 + 跑网格

两条线可并行;线 2 约 30–60 分钟一次搞定,线 1 是主要工作量。
机器:RTX 4090 48G / 驱动 580(CUDA 12 兼容),conda 26.x。

## 线 2 — so-vits-svc 4.1 环境(可先做,做完能立刻冒烟测试)

```bash
# 1. 系统依赖(svc_infer.py 的输入下混要用,当前机器没装)
sudo apt install -y ffmpeg unzip

# 2. 独立环境(官方钉老版本 Python;3.10 实测 fairseq 还装得上,再高容易翻车)
conda create -n sovits python=3.10 -y
conda activate sovits

# 3. 代码(4.1-Stable 分支)
git clone -b 4.1-Stable --depth 1 https://github.com/svc-develop-team/so-vits-svc.git ~/so-vits-svc
cd ~/so-vits-svc

# 4. 依赖:先 torch 后 requirements;fairseq 装失败的话单独 pip install fairseq==0.12.2,
#    还失败就把 env 重建成 python=3.9
pip install torch torchaudio
pip install -r requirements.txt

# 5. 两个必需权重 → pretrain/
wget -O pretrain/checkpoint_best_legacy_500.pt \
  https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt
wget https://github.com/yxlllc/RMVPE/releases/download/230917/rmvpe.zip
unzip rmvpe.zip -d /tmp/rmvpe && mv /tmp/rmvpe/model.pt pretrain/rmvpe.pt && rm rmvpe.zip

# 6.(可选,浅扩散用)vocoder。优先去模型发布页找 nsf_hifigan_finetuned;
#    找不到就用标准版顶上,软链一下让 diffusion.yaml 的非标准路径也能解析:
wget https://github.com/openvpi/vocoders/releases/download/nsf-hifigan-v1/nsf_hifigan_20221211.zip
unzip nsf_hifigan_20221211.zip -d pretrain/ && rm nsf_hifigan_20221211.zip
ln -s nsf_hifigan pretrain/nsf_hifigan_finetuned
```

**冒烟测试(不用等 SynthV)**:随便一段带人声的音频就行,质量无所谓,
只验证整条链能跑通(模型加载、rmvpe、输出收集):

```bash
cd ~/ai_mad
ffmpeg -ss 60 -t 15 -i refs/anon_version.mp3 /tmp/smoke.wav
python3 scripts/svc_infer.py --svc-repo ~/so-vits-svc \
    --python ~/miniforge3/envs/sovits/bin/python \
    --input /tmp/smoke.wav -t 0 --shd off
# 听 vocal/svc_out/smoke_f0rmvpe_t+0.wav:出来是东雪莲音色(哪怕背景有伴奏糊着)= 链路 OK
# 装了 vocoder 的话把 --shd off 去掉,顺便验证浅扩散
```

冒烟产物听完删掉即可(`rm vocal/svc_out/smoke_*`,`docs/svc_grid.md` 里对应批次段落也删掉)。

## 线 1 — SynthV 干声(主要工作量)

细节以 `docs/synthv_notes.md` 为准,这里是操作顺序:

1. 新工程,采样率 48kHz,先对 `refs/anon_version.mp3` 定 BPM 和小节线。
2. 逐句听写音高/时值进钢琴卷帘(以 mp3 为准),每句音符数 = `refs/mora_budget.tsv`
   配额(行 23 是 14)。
3. 歌词输入:框选一句的全部音符 → 粘贴 `lyrics/synthv_input.txt` 对应行
   (空格分隔按音符逐个分配)。促音 t 分配不对时,把该音符歌词手动改 っ(音素 cl)。
4. 专项检查:促音/長音各占一个音符(so-っ-to、cho-o-ku);行 23 拆音
   (づ/な 中时值长者对半拆给 け,け ≥ 1/16 音符)。
5. 按 `docs/synthv_notes.md` 分段调教(主歌 A 克制 → 副歌 vibrato 直进颤出 →
   行 19 气声极值 → 行 20 说教感顶点 → 行 25 渐弱收)。全局 vibrato depth ~0.6 倍起。
6. 双声库各导一版干声:**无混响、无效果器**,48kHz WAV →
   `vocal/synthv_source_a.wav`(男声库)/ `_b.wav`(女声库)。
   每路线做到"发音无错、乐句成立"即可先交转换,别过度精调。
7. 走完 `docs/synthv_notes.md` 文末的导出核对清单。

## 汇合 — Phase 3 网格与盲听

```bash
# 每个声库各跑一次粗网格(约 6 个组合/声库:3 个变调 × 有无浅扩散)
python3 scripts/svc_infer.py --svc-repo ~/so-vits-svc \
    --python ~/miniforge3/envs/sovits/bin/python \
    --input vocal/synthv_source_a.wav -t 0 12 -12
python3 scripts/svc_infer.py --svc-repo ~/so-vits-svc \
    --python ~/miniforge3/envs/sovits/bin/python \
    --input vocal/synthv_source_b.wav -t 0 12 -12
```

盲听 `vocal/svc_out/`,备注写进 `docs/svc_grid.md`。判断标准:

- **transpose 方向**:声音发闷、像压着嗓子 → 该 +12;发尖、假声感、咬字碎 → 该 −12;
  自然贴脸 → 0 对了。男声库路线大概率要 +12。
- **浅扩散 (shd) 版**:电音感/金属毛刺明显减少 → 选 shd;听不出差别 → 选非 shd(省事)。
- **两路线对比**:哪个声库转出来更像东雪莲本人唱歌、咬字更清楚,就定哪条路线。

选定后:

```bash
cp vocal/svc_out/<你选中的文件>.wav vocal/svc_out/selected.wav
```

然后告诉我选了哪版 + 简单说下为什么(记进 postmortem),Phase 3 完,进 Phase 4 混音。
