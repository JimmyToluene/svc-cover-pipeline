#!/usr/bin/env python3
"""Phase 4 — 混音(人声链 + 伴奏合轨 + 响度对标)。

人声链(CLAUDE.md 起始参数,数值全部可调,用户 A/B 定稿):
  链前规整到 -20 LUFS → 高通 80Hz(两级 12dB/oct)→ 轻压缩(-18dB 阈值 2.5:1)
  → plate 混响(wet 15%,尾部垫 3s 防截断)
合轨:人声响度 = 伴奏响度 + vocal-offset(默认 -1.5 LU,即比伴奏低 1.5)
母带:整体拉到 -14 LUFS(B 站标准),真峰值(4x 过采样)守 -1 dBTP。

依赖:pedalboard, pyloudnorm, soundfile, numpy(,resampy 仅采样率不一致时)。

路径:默认相对 --project 工程目录(见 project_paths.py)。

示例:
  python scripts/mix.py --inst <project>/inst/伴奏.wav
  python scripts/mix.py ... --vocal-shift 0.35     # 人声整体延后 0.35s 对拍
  python scripts/mix.py ... --reverb-wet 0.22 --vocal-offset -1.0   # A/B 微调
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pyloudnorm
import soundfile as sf
from pedalboard import Compressor, HighpassFilter, Pedalboard, Reverb

from project_paths import add_project_arg, resolve_project


def die(msg):
    print(f"[mix] 错误: {msg}", file=sys.stderr)
    sys.exit(1)


def load_audio(path: Path):
    data, sr = sf.read(path, dtype="float32", always_2d=True)  # (frames, ch)
    return data, sr


def to_stereo(x):
    if x.shape[1] == 1:
        return np.repeat(x, 2, axis=1)
    if x.shape[1] > 2:
        return x[:, :2]
    return x


def lufs(meter, x):
    v = meter.integrated_loudness(x)
    if not np.isfinite(v):
        die("响度测量得到 -inf(输入基本是静音?)")
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--vocal", type=Path, default=None,
                    help="默认 <project>/vocal/svc_out/selected.wav")
    ap.add_argument("--inst", type=Path, required=True, help="伴奏 wav")
    ap.add_argument("--out", type=Path, default=None,
                    help="默认 <project>/output/final_mix.wav")
    ap.add_argument("--vocal-shift", type=float, default=0.0,
                    help="人声整体平移秒数,正=延后负=提前(对拍用)")
    ap.add_argument("--vocal-offset", type=float, default=-1.5,
                    help="人声相对伴奏的响度差(LU),负=人声更小")
    ap.add_argument("--hp", type=float, default=80.0, help="人声高通 Hz")
    ap.add_argument("--comp-threshold", type=float, default=-18.0,
                    help="压缩阈值 dB(作用于已规整到 -20 LUFS 的人声,深度可复现)")
    ap.add_argument("--comp-ratio", type=float, default=2.5)
    ap.add_argument("--reverb-wet", type=float, default=0.15)
    ap.add_argument("--reverb-room", type=float, default=0.5,
                    help="0-1,plate 质感取中等偏小")
    ap.add_argument("--target-lufs", type=float, default=-14.0)
    ap.add_argument("--save-stems", action="store_true",
                    help="额外导出处理后的人声 stem,便于排查")
    args = ap.parse_args()
    proj = resolve_project(args)
    args.vocal = args.vocal or proj / "vocal" / "svc_out" / "selected.wav"
    args.out = args.out or proj / "output" / "final_mix.wav"

    for p in (args.vocal, args.inst):
        if not p.expanduser().is_file():
            die(f"文件不存在: {p}")

    vocal, sr_v = load_audio(args.vocal.expanduser())
    inst, sr_i = load_audio(args.inst.expanduser())
    if sr_v != sr_i:
        try:
            import resampy
        except ImportError:
            die(f"人声 {sr_v}Hz 与伴奏 {sr_i}Hz 采样率不同,需要 resampy: pip install resampy")
        print(f"[mix] 重采样人声 {sr_v} → {sr_i}")
        vocal = resampy.resample(vocal.T, sr_v, sr_i).T.astype(np.float32)
    sr = sr_i

    # 人声平移
    shift = int(round(args.vocal_shift * sr))
    if shift > 0:
        vocal = np.vstack([np.zeros((shift, vocal.shape[1]), dtype=np.float32), vocal])
    elif shift < 0:
        if -shift >= len(vocal):
            die("--vocal-shift 提前量超过人声长度")
        vocal = vocal[-shift:]

    # 先统一立体声再做一切响度测量:BS.1770 对双声道求和,单声道升立体声 +3 LU,
    # 后升会让人声比目标偏热 3dB
    vocal, inst = to_stereo(vocal), to_stereo(inst)
    meter = pyloudnorm.Meter(sr)

    # 链前把人声规整到固定电平:压缩深度只取决于阈值参数,不取决于 SVC 输出的碰巧电平
    PRE_CHAIN_LUFS = -20.0
    l_raw = lufs(meter, vocal)
    vocal *= 10 ** ((PRE_CHAIN_LUFS - l_raw) / 20)

    # 尾部垫静音,给混响衰减留空间(pedalboard 离线渲染输出长度=输入长度,会截尾)
    TAIL_S = 3.0
    vocal = np.vstack([vocal, np.zeros((int(TAIL_S * sr), 2), dtype=np.float32)])

    # 人声处理链(高通两级串联 = 12dB/oct,单级只有 6dB/oct 压不住低频)
    chain = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=args.hp),
        HighpassFilter(cutoff_frequency_hz=args.hp),
        Compressor(threshold_db=args.comp_threshold, ratio=args.comp_ratio,
                   attack_ms=10, release_ms=150),
        Reverb(room_size=args.reverb_room, damping=0.5,
               wet_level=args.reverb_wet, dry_level=1.0 - args.reverb_wet,
               width=1.0),
    ])
    vocal = chain(vocal.T, sr).T  # pedalboard 接口是 (ch, frames)

    # 响度对齐:人声 = 伴奏 + offset
    l_inst, l_vocal = lufs(meter, inst), lufs(meter, vocal)
    gain_db = (l_inst + args.vocal_offset) - l_vocal
    vocal *= 10 ** (gain_db / 20)
    print(f"[mix] 伴奏 {l_inst:.1f} LUFS,人声链后 {l_vocal:.1f} LUFS,"
          f"人声增益 {gain_db:+.1f} dB(目标差 {args.vocal_offset:+.1f} LU)")

    # 合轨
    n = max(len(vocal), len(inst))
    pad = lambda x: np.vstack([x, np.zeros((n - len(x), 2), dtype=np.float32)])
    mix = pad(vocal) + pad(inst)

    # 母带:拉到目标响度;真峰值(4x 过采样估计)超 -1dB 才整体回拉
    # (透明处理,不用 pedalboard.Limiter——它带自动增益补偿,会把响度顶回去)
    def true_peak_db(x):
        try:
            import resampy
            y = resampy.resample(x.T, sr, sr * 4).T  # 采样间峰值近似
        except ImportError:
            y = x
        return 20 * np.log10(max(np.abs(y).max(), 1e-9))

    l_mix = lufs(meter, mix)
    mix *= 10 ** ((args.target_lufs - l_mix) / 20)
    tp = true_peak_db(mix)
    if tp > -1.0:
        mix *= 10 ** ((-1.0 - tp) / 20)
        print(f"[mix] 真峰值 {tp:.1f} dBTP 超限,整体回拉 {-1.0 - tp:.1f} dB"
              "(最终响度会略低于目标,属正常)")
    l_final = lufs(meter, mix)
    print(f"[mix] 母带前 {l_mix:.1f} LUFS → 最终 {l_final:.1f} LUFS,"
          f"真峰值 {true_peak_db(mix):.1f} dBTP(目标 {args.target_lufs} LUFS / ≤-1)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.out, mix, sr, subtype="PCM_24")
    print(f"[mix] 完成 → {args.out}")
    if args.save_stems:
        stem_path = args.out.with_name(args.out.stem + "_vocal_stem.wav")
        sf.write(stem_path, pad(vocal), sr, subtype="PCM_24")
        print(f"[mix] 人声 stem → {stem_path}")
    print(f"[mix] 下一步:与 {proj.name}/refs/ 下的参照版做 A/B"
          "(人声电平/混响量/整体响度)")


if __name__ == "__main__":
    main()
