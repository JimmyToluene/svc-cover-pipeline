#!/usr/bin/env python3
"""Phase 4 — mix (vocal chain + instrumental sum + loudness targeting).

Vocal chain (starting parameters from CLAUDE.md, all values tunable, user A/Bs the final call):
  normalize to -20 LUFS before the chain → 80Hz highpass (two stages, 12dB/oct)
  → light compression (-18dB threshold, 2.5:1)
  → plate reverb (wet 15%, 3s of tail padding to avoid truncation)
Summing: vocal loudness = instrumental loudness + vocal-offset (default -1.5 LU,
i.e. 1.5 below the instrumental)
Mastering: brickwall limiter + iterative make-up gain, converging on -14 LUFS
(Bilibili standard), true peak (4x oversampled) kept at -1 dBTP.

Dependencies: pedalboard, pyloudnorm, soundfile, numpy (, resampy only when sample rates differ).

Paths: resolved relative to the --project project directory by default (see project_paths.py).

Examples:
  python scripts/mix.py --inst <project>/inst/instrumental.wav
  python scripts/mix.py ... --vocal-shift 0.35     # delay the vocal by 0.35s to line up with the beat
  python scripts/mix.py ... --reverb-wet 0.22 --vocal-offset -1.0   # A/B fine-tuning
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pyloudnorm
import soundfile as sf
from pedalboard import Compressor, HighpassFilter, Limiter, Pedalboard, Reverb

from project_paths import add_project_arg, resolve_project


def die(msg):
    print(f"[mix] error: {msg}", file=sys.stderr)
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
        die("loudness measurement returned -inf (is the input essentially silence?)")
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--vocal", type=Path, default=None,
                    help="default <project>/vocal/svc_out/selected.wav")
    ap.add_argument("--inst", type=Path, required=True, help="instrumental wav")
    ap.add_argument("--out", type=Path, default=None,
                    help="default <project>/output/final_mix.wav")
    ap.add_argument("--vocal-shift", type=float, default=0.0,
                    help="shift the vocal by this many seconds, positive = later, negative = earlier (for beat alignment)")
    ap.add_argument("--vocal-offset", type=float, default=-1.5,
                    help="vocal loudness relative to the instrumental (LU), negative = quieter vocal")
    ap.add_argument("--hp", type=float, default=80.0, help="vocal highpass in Hz")
    ap.add_argument("--comp-threshold", type=float, default=-18.0,
                    help="compressor threshold in dB (applied to the vocal already normalized to -20 LUFS, so compression depth is reproducible)")
    ap.add_argument("--comp-ratio", type=float, default=2.5)
    ap.add_argument("--reverb-wet", type=float, default=0.15)
    ap.add_argument("--reverb-room", type=float, default=0.5,
                    help="0-1; keep it medium-small for a plate feel")
    ap.add_argument("--target-lufs", type=float, default=-14.0)
    ap.add_argument("--save-stems", action="store_true",
                    help="also export the processed vocal stem, handy for troubleshooting")
    args = ap.parse_args()
    proj = resolve_project(args)
    args.vocal = args.vocal or proj / "vocal" / "svc_out" / "selected.wav"
    args.out = args.out or proj / "output" / "final_mix.wav"

    for p in (args.vocal, args.inst):
        if not p.expanduser().is_file():
            die(f"file not found: {p}")

    vocal, sr_v = load_audio(args.vocal.expanduser())
    inst, sr_i = load_audio(args.inst.expanduser())
    if sr_v != sr_i:
        try:
            import resampy
        except ImportError:
            die(f"vocal is {sr_v}Hz but instrumental is {sr_i}Hz; resampy is needed: pip install resampy")
        print(f"[mix] resampling vocal {sr_v} → {sr_i}")
        vocal = resampy.resample(vocal.T, sr_v, sr_i).T.astype(np.float32)
    sr = sr_i

    # Vocal shift
    shift = int(round(args.vocal_shift * sr))
    if shift > 0:
        vocal = np.vstack([np.zeros((shift, vocal.shape[1]), dtype=np.float32), vocal])
    elif shift < 0:
        if -shift >= len(vocal):
            die("--vocal-shift moves the vocal earlier than its own length")
        vocal = vocal[-shift:]

    # Convert everything to stereo before any loudness measurement: BS.1770 sums
    # both channels, so upmixing mono to stereo adds +3 LU — doing it later would
    # leave the vocal 3dB hotter than the target
    vocal, inst = to_stereo(vocal), to_stereo(inst)
    meter = pyloudnorm.Meter(sr)

    # Normalize the vocal to a fixed level before the chain: compression depth then
    # depends only on the threshold parameter, not on whatever level the SVC happened to output
    PRE_CHAIN_LUFS = -20.0
    l_raw = lufs(meter, vocal)
    vocal *= 10 ** ((PRE_CHAIN_LUFS - l_raw) / 20)

    # Pad the tail with silence so the reverb has room to decay (pedalboard's
    # offline render output length = input length, which would clip the tail)
    TAIL_S = 3.0
    vocal = np.vstack([vocal, np.zeros((int(TAIL_S * sr), 2), dtype=np.float32)])

    # Vocal processing chain (two cascaded highpasses = 12dB/oct; a single stage
    # at 6dB/oct can't tame the lows)
    chain = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=args.hp),
        HighpassFilter(cutoff_frequency_hz=args.hp),
        Compressor(threshold_db=args.comp_threshold, ratio=args.comp_ratio,
                   attack_ms=10, release_ms=150),
        Reverb(room_size=args.reverb_room, damping=0.5,
               wet_level=args.reverb_wet, dry_level=1.0 - args.reverb_wet,
               width=1.0),
    ])
    vocal = chain(vocal.T, sr).T  # pedalboard's interface is (ch, frames)

    # Loudness alignment: vocal = instrumental + offset
    l_inst, l_vocal = lufs(meter, inst), lufs(meter, vocal)
    gain_db = (l_inst + args.vocal_offset) - l_vocal
    vocal *= 10 ** (gain_db / 20)
    print(f"[mix] instrumental {l_inst:.1f} LUFS, vocal after chain {l_vocal:.1f} LUFS, "
          f"vocal gain {gain_db:+.1f} dB (target offset {args.vocal_offset:+.1f} LU)")

    # Sum the tracks
    n = max(len(vocal), len(inst))
    pad = lambda x: np.vstack([x, np.zeros((n - len(x), 2), dtype=np.float32)])
    mix = pad(vocal) + pad(inst)

    # Mastering: brickwall limiter squashes transient peaks + iterative make-up gain
    # converges on the target loudness. pedalboard.Limiter (JUCE) has automatic gain
    # compensation with a fixed 0 dBFS output ceiling, so the recipe is: after
    # limiting, pull everything back by CEIL_DB for true-peak headroom, and if
    # loudness dropped, add gain and limit again.
    def true_peak_db(x):
        try:
            import resampy
            y = resampy.resample(x.T, sr, sr * 4).T  # approximate inter-sample peaks
        except ImportError:
            y = x
        return 20 * np.log10(max(np.abs(y).max(), 1e-9))

    CEIL_DB = -1.2   # sample-peak ceiling, leaving 0.2dB for 4x-oversampled inter-sample peaks
    limiter = Pedalboard([Limiter(threshold_db=-1.0, release_ms=100)])
    l_mix = lufs(meter, mix)
    pre = mix * 10 ** ((args.target_lufs - l_mix) / 20)
    for i in range(3):
        mix = limiter(pre.T, sr).T * 10 ** (CEIL_DB / 20)
        err = args.target_lufs - lufs(meter, mix)
        if abs(err) < 0.3:
            break
        pre *= 10 ** (err / 20)   # add back however much loudness the limiter ate, before re-limiting
    gr = 20 * np.log10(max(np.abs(pre).max(), 1e-9)) - CEIL_DB
    if gr > 6:
        print(f"[mix] warning: the limiter is shaving about {gr:.0f} dB off the peaks, "
              "transients may sound noticeably dulled; consider lowering --target-lufs", file=sys.stderr)
    tp = true_peak_db(mix)
    if tp > -1.0:   # safety net: inter-sample peaks still over, pull back slightly
        mix *= 10 ** ((-1.0 - tp) / 20)
    l_final = lufs(meter, mix)
    print(f"[mix] pre-master {l_mix:.1f} LUFS → final {l_final:.1f} LUFS, "
          f"true peak {true_peak_db(mix):.1f} dBTP (target {args.target_lufs} LUFS / ≤-1)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.out, mix, sr, subtype="PCM_24")
    print(f"[mix] done → {args.out}")
    if args.save_stems:
        stem_path = args.out.with_name(args.out.stem + "_vocal_stem.wav")
        sf.write(stem_path, pad(vocal), sr, subtype="PCM_24")
        print(f"[mix] vocal stem → {stem_path}")
    print(f"[mix] next step: A/B against the reference version under {proj.name}/refs/"
          " (vocal level / reverb amount / overall loudness)")


if __name__ == "__main__":
    main()
