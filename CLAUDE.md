# CLAUDE.md — 《念张师》日语版 · 东雪莲音色 AI 翻唱工程

## 项目目标

产出一首完整的《念张师》日语填词版 AI 翻唱成品(WAV/FLAC + 可发布 MP4),
音色为东雪莲(so-vits-svc 4.1 模型),源人声由 Synthesizer V 合成。

最终交付物:

1. `lyrics/final.md` — 日语歌词定稿(含罗马音、中文对照、逐行 mora 标注)
2. `output/final_mix.wav` — 混音成品
3. `output/release.mp4` — 带静态封面 + 字幕的发布版视频
4. `docs/postmortem.md` — 参数记录,便于复现

## 背景(不要跳过)

- 《念张师》是张雪峰主题歌曲,旋律为中文原版的**原创作曲**(不是《千恋万花》BGM,
  此前的判断是错的)。主旋律工程/MIDI 网上有人发布过,Phase 0 优先去找。
- 已存在一版日语填词(B 站 BV139Gm6REz6,爱音音色),歌词已公开。
  **本工程以该版歌词为 v1 起点做修订**,不是从零填词。爱音版音频
  (`refs/anon_version.mp3`)是核心参照输入,用途:mora/时值核对、
  SynthV 逐句对拍、混音 A/B 基准、伴奏分离兜底。
- 因此最终歌词是爱音版填词的**衍生修订版**。个人自娱没有问题;
  若公开发布,必须署名原填词作者(视频 UP 主),最好事先打个招呼。
  这一条不可协商,写在成品 `docs/postmortem.md` 和发布文案里。
- 东雪莲音色 = 用户本地已下载的 **so-vits-svc 4.1** 模型(路径见下)。该模型由
  真实歌声数据训练,SVC 适性好。本工程仅限个人娱乐用途;若发布,遵守 B 站
  AI 生成内容标注规则。
- 用户懂 ML、懂日语基础、有本地 GPU。不要解释什么是 so-vits-svc,直接干活。

## 分工边界(重要)

**Claude 负责(可自动化):**

- 日语歌词创作、mora 对齐校验、罗马音生成
- 所有脚本:音频批处理、so-vits-svc 推理封装、ffmpeg 混音链、字幕文件生成
- 参数实验的记录与对比表

**必须由用户手动完成(Claude 无法听音频,不要假装能):**

- 提供旋律参照:每行音符数/mora 配额(Phase 0 的输入,格式见下)
- SynthV 里的钢琴卷帘输入与调教(Claude 只产出歌词+音高建议文本)
- 混音的最终听感判断(Claude 给初始参数,用户 A/B)

每个 Phase 结束时明确列出"需要你做的事",然后停下等输入。不要在缺少用户输入时
用假设数据继续推进。

## 目录结构

```
nenzhangshi-jp/
├── CLAUDE.md
├── refs/                  # 参照输入
│   ├── anon_version.mp3   # 爱音版音频(用户提供,时值/混音/伴奏参照)
│   └── mora_budget.tsv    # 格式: 行号<TAB>mora数<TAB>v1对应句
├── lyrics/
│   ├── drafts/
│   │   ├── v1.md          # 爱音版原文照录(不动它,作为 diff 基线)
│   │   └── v2.md, v3.md...
│   └── final.md
├── vocal/
│   ├── synthv_source.wav  # 用户从 SynthV 导出的干声
│   └── svc_out/           # 各参数组合的转换结果,文件名含参数
├── models/
│   └── higashi_yukiren/   # so-vits-svc 4.1 模型 (G_*.pth + config.json
│                          #  + 可选 kmeans/特征检索 + 可选 diffusion)
├── inst/                  # 伴奏(用户提供或 UVR 分离)
├── scripts/
├── output/
└── docs/
```

## 工作阶段

### Phase 0 — 旋律参照建立

- 逐行统计 v1 歌词的 mora 数,生成 `refs/mora_budget.tsv`。v1 已与旋律
  对齐演唱过,是最可靠的配额来源。長音、促音、撥音各计 1;拗音计 1。
- 用户对照 `refs/anon_version.mp3` 抽查 4-6 行(重点副歌),确认统计与
  实际音符对应,注意 v1 演唱中可能存在一音多字/一字多音的处理,发现即标注。
- DoD:mora 配额经用户确认写入 tsv,后续所有修订以此为不变量基准。

### Phase 1 — 歌词修订(以 v1 为基线,改动最小化原则)

v1 = 爱音版原文,照录进 `lyrics/drafts/v1.md`,永不修改,作为 diff 基线。

修订分三个 pass,每个 pass 出一版:

- **Pass A(v2)— 硬错误修正**:只改语法/用词错误,不动没病的句子。已知问题清单
  (逐条核对,可能不止这些):「逃げわず」不成立(→ 逃げずに 或重写该句);
  「歩い続ながら」缺假名(→ 歩き続けながら,注意 mora 会 +1,需处理);
  「チャーク」→「チョーク」;全部罗马音重新生成,不信任 v1 的标注
  (已知 ukabu 被标成 ugabu 等)。「忘られず」是古语但可唱可懂,默认保留,标注存疑。
- **Pass B(v3)— 可唱性打磨**:对照 `refs/anon_version.mp3` 逐句听感检查
  (这步用户听,Claude 出 checklist):高音/长音落在闭口元音的句子、
  拗音密集拗口的句子,给替换方案。
- **Pass C(可选)— 表达提升**:v1 里达意但平的句子给升级选项,一句一个备选,
  用户逐条采纳。不整段重写,改动幅度由用户控制。

每版输出:日语 / 罗马音(重新生成) / 中文回译 + 与 v1 的逐行 diff 表(改了什么、为什么)。
**Mora 不变量**:任何修改后该行 mora 数必须等于 v1 该行 mora 数,除非同时给出
SynthV 拆音/连音方案并标注。

创作规范(修改句适用):

- **Mora 严格对齐**:一个音符 = 一个 mora。長音(ー)、促音(っ)、撥音(ん)各计
  1 mora 且各占一个音符;拗音(きゃ)计 1 mora。每行写完立即标注 mora 数并与配额核对,
  不匹配的行不进入下一版。
- **可唱性**:长音/高音处优先开口元音(a/o/e);避免连续い段+う段的含混段落;
  句尾避免以促音收尾;ん 不放在乐句最高音上。
- **基调**:v1 的感怀师恩抒情路线保持不变,修订不改变歌曲性格。
  Pass C 若做"莲式"口语化偏移,单独出分支版本,不混入主线。
- 每版草稿输出三栏:日语 / 罗马音 / 中文回译。罗马音供 SynthV 输入用,
  按 SynthV 日语音素习惯写(は助词写 wa)。
- DoD:用户确认定稿 → `lyrics/final.md`,同时生成 `lyrics/synthv_input.txt`
  (纯歌词,按乐句分行,方便逐句粘贴进 SynthV)。

### Phase 2 — 源人声合成(SynthV,用户主导)

- Claude 产出:`docs/synthv_notes.md` — 逐句的演唱处理建议(哪里加气声、
  哪里 vibrato 收敛、张雪峰式"说教感"乐句用 tension 参数模拟)。
- 用户导出 48kHz WAV 干声到 `vocal/synthv_source.wav`。
- 声库:**女声库单路线**(2026-07-04 用户定案,原"男/女双路线都试"作废)。
  选接近东雪莲音域的女声库,transpose≈0;"说教感"用 tension/断句做,不靠声库性别。
- DoD:干声文件就位,用户确认发音无明显错误。

### Phase 3 — SVC 音色转换(so-vits-svc 4.1)

- 前置(用户准备):so-vits-svc **4.1-Stable** 本地 checkout 及其推理环境;
  checkout 的 `pretrain/` 下放好:与模型 config.json `model.speech_encoder`
  匹配的编码器权重(默认 vec768l12 → `checkpoint_best_legacy_500.pt`)、
  `rmvpe.pt`;若用浅扩散或增强器,另需 `pretrain/nsf_hifigan/`。
- `models/higashi_yukiren/` 放:`G_*.pth` + `config.json`(必需);可选
  `kmeans_10000.pt`(聚类)或 `feature_and_index.pkl`(特征检索)、
  扩散模型(`model_*.pt` + `diffusion.yaml`)。有什么脚本自动检测什么。
- `scripts/svc_infer.py`:封装 `inference_main.py` 推理,参数网格跑批,
  输出收集到 `vocal/svc_out/`,文件名编码参数
  (如 `synthv_source_a_f0rmvpe_t+0_cr0.3km.wav`,km=聚类/fr=特征检索)。
- 起始参数:f0 predictor = **rmvpe**(CLI 默认是 pm,必须显式传);
  transpose 按 Phase 2 所选声库与东雪莲音域差决定(先跑 0 和 ±12);
  聚类/特征检索占比 -cr 网格 {0, 0.3, 0.5}(越高越贴目标音色、咬字越糊;
  模型没带 kmeans/index 就固定 0);noice_scale 0.4 不动。
  **绝不开 -a(auto f0)**——唱歌必严重跑调;-eh 增强器不开
  (对训练充分的模型是反效果)。
- 模型带扩散时:同网格各加跑一版 -shd(浅扩散,k_step 100),
  出电音/金属感时优先选浅扩散版。
- 生成 `docs/svc_grid.md` 对比表,用户盲听选优。
- DoD:用户选定一版 → `vocal/svc_out/selected.wav`。

### Phase 4 — 混音与出片

- `scripts/mix.py`(pedalboard/pyloudnorm):人声链 = 高通 80Hz → 轻压缩 →
  plate reverb(wet 15% 起)→ 与伴奏合轨,人声 -1~-2 LUFS 相对伴奏起步。
- 伴奏获取,按优先级:(1) 找中文原版作者发布的官方伴奏/工程;
  (2) 从 `refs/anon_version.mp3` 分离——它的人声是 SVC 干声混响,
  分离难度低于真人演唱,`scripts/separate.py`(audio-separator 包,
  BS-Roformer)+ 去混响;
  (3) 从中文原版音频分离。mp3 有损,分离后高频损失可接受(梗曲标准)。
- 混音基准:成品与 `refs/anon_version.mp3` 做 A/B,人声电平、混响量、
  响度对齐到不劣于参照版。
- 字幕:从 `lyrics/final.md` 生成 `.ass`(日语+中文双行),时间轴需用户
  提供每句起始时间或从 SynthV 工程导出。
- `output/release.mp4` = 静态封面 + 音频 + 字幕(ffmpeg 一条命令,写进脚本)。
- DoD:用户听感通过,响度 -14 LUFS(B 站标准)。

## 约束与红线

- 本工程歌词是爱音版填词的衍生修订。公开发布时必须署名原填词作者;
  `lyrics/final.md` 头部固定保留来源声明,任何一版都不许删。
- 不引用真实第三方(除张雪峰公开语录梗、东雪莲公开直播梗外)的真人姓名。
- 所有脚本用 Python,依赖写进 `requirements.txt`,GPU 相关脚本加
  `--device` 参数,默认 cuda。
- 每个 Phase 的产物 commit 一次,commit message 格式 `phase{N}: <内容>`。
- 遇到需要听音频才能判断的问题,直接说"这步需要你听",给出判断标准,不要猜。

## 已知风险

| 风险                           | 缓解                                                        |
| ------------------------------ | ----------------------------------------------------------- |
| mora 配额估算错误导致歌词返工  | Phase 0 用户人工核对是硬门槛,不许跳                         |
| SynthV 声库与东雪莲音域差过大  | 已选贴近音域的女声库;仍不合再用 Phase 3 变调网格 ±12 覆盖    |
| SVC 模型训练数据不含歌唱高音区 | 东雪莲模型含真实歌声,风险低;若高音发虚,歌词侧可微调该句元音 |
| 分离伴奏残留人声               | 优先找官方/UTAU 社区现成伴奏,分离是兜底                     |
