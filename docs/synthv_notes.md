# Phase 2 — SynthV 逐句演唱处理建议

基线:`lyrics/final.md`(v3 定稿)+ `lyrics/synthv_input.txt`(逐句罗马音,
一个 token = 一个音符)。时值/音高对拍以 `refs/anon_version.mp3` 为准,逐句听写。

## 声库与全局设置

- 双路线并行(CLAUDE.md 约定):**路线 A** 男声库(说教感占优,SVC 变调
  负担看音域差);**路线 B** 接近东雪莲音域的女声库(SVC transpose≈0 优先)。
  每路线只需做到"发音无错、乐句成立"即可交 Phase 3 试转,先别精调。
- 工程采样率 48kHz,导出 48kHz WAV 干声(无混响!)→ `vocal/synthv_source.wav`。
  路线 A/B 各导一版时命名 `synthv_source_a.wav` / `_b.wav`。
- 输入方式:逐句框选音符后粘贴 `synthv_input.txt` 对应行(空格分隔会按音符
  逐个分配);促音 t 若分配不对,把该音符歌词手动改成 っ 或音素 cl。
- 全局参数起点:vibrato depth 全局先压到 ~0.6 倍(东雪莲原声 vibrato 不重,
  SVC 会保留源的 pitch 曲线);loudness 曲线后期不画,交给混音。

## 分段处理

### 主歌 A(行 1–4)— 叙事,克制

- 音量中低,vibrato 基本关(仅乐句尾轻微),tension 中性。
- 行 1「a ka ru ku」与行 3「to do ku」句尾闭口 u:缩短尾音符 10–20%
  并接 breath,避免拖虚。
- 行 4 是本段落点:「shi me su」前微渐强,tension +10~15% 做"示す"的笃定感
  (张雪峰式断言)。

### 预副歌(行 5–6)

- 行 5 情绪抬升起点,「ko wa ku te」四连音咬字清楚,不加滑音。
- 行 6 (休止) 前的「i ru」干净收掉;「mu ko u mi zu」逐字顿感
  (音符间 gap 5–10ms 或降 legato),做破釜沉舟的语气。

### 副歌 1(行 7–10)— 全曲 hook

- 整体 loudness +,乐句尾长音开 vibrato(depth 中等、onset 延迟 0.2–0.3s,
  即直音进、颤音出)。
- 行 7「wa su ra re zu」尾音 zu 闭口:直音保持为主,vibrato 浅,防发虚。
- 行 8「so t to so t to」加 breathiness +20~30%,气声耳语感;
  「tsu na gu」收回正常。
- 行 10「ku re ta」开口 a 收尾,可以放心给长音和渐强,本段最舒展的落点。

### 主歌 B(行 11–14)— 私密,回忆

- 音量回落,比主歌 A 更贴麦的感觉:breathiness 全段 +10~15%。
- 行 11 唱 shi zu 截断(见 final.md 口径),尾音轻放不压。
- 行 12 引号内「mi ra i wa ma da to o i」是老师的话:tension +,vibrato 关,
  音符间略断开(说话感);引号外「e ga o de ho me te」正常唱,形成对比。
- 行 13–14 逐句渐强,给行 15 铺垫;「u ka bu」尾音短收。

### 行 15–16(主歌 B 落点)

- 行 15「do n na」重音在 do,ん 不在高音上(旋律如与此冲突,回来标注)。
- 行 16「ho e」两音(演唱口径),乐句渐强推向桥段;e 开口,可拖。

### 桥段(行 17–20)

- 行 17 (休止) 前后两半句对比:前半轻,后半「to o ku e yu ku」渐强。
- 行 19 全曲最静:breathiness 最大值区,「so ba ni」几乎气声,
  (休止) 给足,「ki mi no ko e」每字放慢咬字。
- 行 20 老师引言收桥段:同行 12 处理(tension +、vibrato 关、断开),
  「i ke ru」最后一字转笃定直音拖满——这句是"说教感"的顶点。

### 副歌 2(行 21–25)— 最大动态

- 行 21/22/24 同副歌 1 处理,整体 loudness 再 +。
- **行 23 拆音(唯一改动过音符数的行)**:对照 mp3 找「づ」「な」中时值较长者
  对半拆给「け」(预判拆 な)。拆完后「け」音符 ≥ 1/16 音符时值,
  否则改拆另一个;k 辅音务必清晰(SVC 转换保不住源头就糊的清辅音)。
- 行 25 全曲收尾:「zu t to」促音顿感强调;「ko ko ro ni」末字 ni 闭口——
  直音进、极浅 vibrato,音量做 fade 渐弱收,不要强推(i 元音强推必虚)。
  尾后留一拍气声 breath 音符(SynthV 的 br)更自然,可选。

## 导出核对清单(交 Phase 3 前)

- [ ] 逐句对照 mp3:音符数 == 罗马音 token 数(行 23 为 14)
- [ ] 促音/長音音符分配正确(so-っ-to;cho-o-ku)
- [ ] 无任何混响/效果器,干声导出 48kHz WAV
- [ ] 听一遍:无明显错误发音(尤其 wa/ha、e/he 助词)
- [ ] 文件就位:`vocal/synthv_source_a.wav`(男声库)/ `_b.wav`(女声库)
