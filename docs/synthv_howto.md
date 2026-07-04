# SynthV 从零实操 — 免费路线 + 旋律 MIDI 导入(2026-07-04 调研核实)

目标:一条唱着 **v3 新歌词** 的干净干声 → `vocal/synthv_source.wav`。
本文只讲怎么做出来;逐句怎么唱见 `docs/synthv_notes.md`。

## 0. 选哪个版本(调研结论,已核对官方文档)

| 路线 | 成本 | 关键限制 | 判定 |
|---|---|---|---|
| **Studio 1 Basic + 日语 AI lite 声库** | 全免费 | lite 音质上限低、渲染锁 Prefer Speed;3 轨(够);参数面板(tension/breathiness)**可用** | **推荐,先走这条** |
| Studio 2 Core(免费)+ Mai 2 | 免费 | 只有 DAW 插件形态(无独立界面),发放机制不明 | 备选 |
| Studio 2 Pro 14 天试用 | 免费试用 | **试用声库禁止导出音频** —— 对我们没用 | 排除 |
| Studio 2 Pro 买断 | ~$99 + 声库 | 无 | lite 质量真不够再说 |

要点:
- **Studio 2 不兼容 V1 lite 声库**(官方明确);免费路线只能用老版 Studio 1 Basic。
- **Dreamtonics 已宣布停止分发自家 lite 声库**,资源服务器目前还在服——
  **尽快下载囤好**。
- lite 的音质上限对本工程影响有限:SVC 会整体替换音色,**咬字清晰度**才是
  要保住的东西。先试,糊了再考虑付费版。

## 1. 下载安装(一次性,约 20 分钟)

1. 编辑器:Studio 1 Basic 安装包(AHS 官方还挂着):
   <https://www.ah-soft.com/trial/synth-v.html>(Windows/macOS/Linux 都有)
2. 声库(lite 目录,选一个日语女声 AI lite,下 `.svpk`):
   <https://resource.dreamtonics.com/download/English/Voice%20Databases/Lite%20Voice%20Databases/>
   候选:**Saki AI Lite**(最常用)、小春六花(rikka-ai-lite)、夏色花梨、鶴巻マキ、
   重音テト。装法:SynthV 里 拖入 .svpk 或双击。
3. 授权红线:lite 输出**非商用**(B 站不开充电/商单),发布文案必须标注
   「Synthesizer V ○○ AI ライト版使用」。这条写进发布 checklist。

## 2. 建工程(参数都已测好)

- 新建工程,**BPM 132.5**(librosa 实测;若对拍发现是半/倍拍就 66.25/265),4/4。
- 把 `refs/anon_version.mp3` 拖进伴奏轨(instrumental track)做对拍参照。

## 3. 导入旋律 MIDI(省掉逐句扒谱)

`refs/vocals_ref_anon_version_basic_pitch.mid` 是从分离人声自动转写的旋律
(basic-pitch,386 音符,音域 F3–C6,人声 16.1s 进)。File → Import 进主音轨后修剪:

- **目标音符数 342**(mora 总量 341 + 行 23 拆音 1),现有 386,多出的 ~40 个是
  转写碎片:删掉极短音(< 1/32)、合并同音高的破碎连音、明显八度跳错的孤立音。
- 逐行核对:每句音符数必须等于 `refs/mora_budget.tsv` 该行配额(行 23 = 14)。
  这是硬校验,对不上就说明该句修剪错了,别硬贴歌词。
- 时值对不准的音符对照伴奏轨/原曲手动拖齐。自动转写的音高错误集中在
  乐句首尾和气声处,重点检查。

## 4. 贴歌词

框选一句的全部音符 → 粘贴 `lyrics/synthv_input.txt` 对应行(空格分隔,
一个 token 一个音符)。然后按 `lyrics/final.md` 的「演唱口径标注」检查:
促音/長音各占一音符(so-っ-to、cho-o-ku)、(休止) 处不填音符、行 11 唱 shi-zu、
行 16 唱 ho-e。促音分配错时把该音符歌词手动改 っ。

## 5. 调教 → 导出

- 按 `docs/synthv_notes.md` 分段处理(它就是为这一步写的)。
- 导出:Render 面板 → WAV,采样率有 48000 就选,没有就 44100(跑批脚本会
  自动重采样,无所谓),**不挂任何效果器** → `vocal/synthv_source.wav`。
- 交付前走 `docs/synthv_notes.md` 文末核对清单。

## 常见坑

- lite 声库渲染模式锁 Prefer Speed:导出前找不到质量选项是正常的,就这么导。
- 罗马音贴上去发音不对时,检查は/へ:输入文件里已按发音写成 wa/e,
  若手动补词别写成假名助词原形。
- BPM 如果和你听感对不上(觉得慢一倍),按 66.25 建工程,MIDI 时值不受影响
  (MIDI 里存的是绝对时间换算)。
