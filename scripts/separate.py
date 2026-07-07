#!/usr/bin/env python3
"""Phase 4 — 伴奏分离兜底(audio-separator 封装)。

伴奏获取优先级(CLAUDE.md):(1) 官方伴奏 >(2) 从参照翻唱版分离(本脚本默认;
若其人声是 SVC 干声+混响,分离难度低于真人演唱)>(3) 从原版音频分离。

默认用 BS-Roformer(当前 SDR 最高的通用分离模型),可选对伴奏再跑一遍
DeEcho-DeReverb 去除人声混响残留(--dereverb,伴奏里听得到"人声尾巴"时用)。

依赖:audio-separator[gpu](建议装在独立 phase4 env,librosa 版本与 sovits env 冲突)。
模型权重首次运行自动下载到 --model-dir。

默认输入:<project>/refs/ 下唯一的音频文件(mp3/wav/flac/m4a),多个时用 --input 指定。

示例:
  python scripts/separate.py                      # 参照版 → <project>/inst/
  python scripts/separate.py --dereverb           # 伴奏残留人声混响时
  python scripts/separate.py --input 中文原版.mp3  # 兜底的兜底
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

from project_paths import add_project_arg, resolve_project

SEP_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
DEREVERB_MODEL = "UVR-DeEcho-DeReverb.pth"


def die(msg):
    print(f"[separate] 错误: {msg}", file=sys.stderr)
    sys.exit(1)


def pick(paths, *keywords, strip_prefix=""):
    """按关键词(不区分大小写)从输出列表选文件。

    strip_prefix 用来剥掉输出名里的输入文件名前缀——输入若本身叫
    xxx_instrumental.mp3,不剥前缀会让关键词误命中。"""
    for p in paths:
        name = Path(p).name
        if strip_prefix and name.startswith(strip_prefix):
            name = name[len(strip_prefix):]
        name = name.lower()
        if all(k.lower() in name for k in keywords):
            return Path(p)
    return None


def default_input(proj: Path) -> Path:
    refs = proj / "refs"
    auds = sorted(p for p in (refs.iterdir() if refs.is_dir() else [])
                  if p.suffix.lower() in (".mp3", ".wav", ".flac", ".m4a"))
    if len(auds) == 1:
        return auds[0]
    if not auds:
        die(f"{refs} 下没有音频文件,用 --input 指定分离输入")
    die(f"{refs} 下有多个音频 {[p.name for p in auds]},用 --input 指定")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--input", type=Path, default=None,
                    help="默认 <project>/refs/ 下唯一的音频文件")
    ap.add_argument("--outdir", type=Path, default=None,
                    help="默认 <project>/inst")
    ap.add_argument("--model", default=SEP_MODEL)
    ap.add_argument("--dereverb", action="store_true",
                    help="对分离出的伴奏再跑 DeEcho-DeReverb,去人声混响残留")
    ap.add_argument("--model-dir", type=Path,
                    default=Path.home() / ".cache" / "audio-separator-models",
                    help="模型权重缓存目录(首次自动下载)")
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    args = ap.parse_args()
    proj = resolve_project(args)
    args.outdir = args.outdir or proj / "inst"

    args.input = (args.input or default_input(proj)).expanduser()
    if not args.input.is_file():
        die(f"输入不存在: {args.input}")
    if args.device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""  # audio-separator 无显式开关,靠这个禁 GPU

    try:
        from audio_separator.separator import Separator
    except ImportError:
        die("缺 audio-separator,先在 phase4 env 里: pip install 'audio-separator[gpu]'")

    args.outdir.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem

    sep = Separator(output_dir=str(args.outdir),
                    model_file_dir=str(args.model_dir),
                    output_format="wav")
    print(f"[separate] 加载分离模型 {args.model}(首次运行会自动下载)")
    sep.load_model(model_filename=args.model)
    print(f"[separate] 分离 {args.input.name} ...")
    outputs = [args.outdir / Path(p).name for p in sep.separate(str(args.input))]
    print(f"[separate] 分离输出: {[p.name for p in outputs]}")

    inst = (pick(outputs, "instrumental", strip_prefix=stem)
            or pick(outputs, "no vocals", strip_prefix=stem))
    vocals = pick(outputs, "(vocals", strip_prefix=stem)
    if inst is None:
        die(f"没找到 instrumental 输出,实际输出: {[p.name for p in outputs]}")

    inst_final = args.outdir / f"inst_from_{stem}.wav"
    shutil.move(str(inst), inst_final)
    if vocals:
        # 分离出的人声留作时间轴参照(字幕对轴用),不进混音
        shutil.move(str(vocals), args.outdir / f"vocals_ref_{stem}.wav")

    if args.dereverb:
        print(f"[separate] 去混响二遍: {DEREVERB_MODEL}")
        sep.load_model(model_filename=DEREVERB_MODEL)
        outs2 = [args.outdir / Path(p).name for p in sep.separate(str(inst_final))]
        print(f"[separate] 去混响输出: {[p.name for p in outs2]}")
        dry = (pick(outs2, "no reverb", strip_prefix=inst_final.stem)
               or pick(outs2, "noreverb", strip_prefix=inst_final.stem))
        if dry is None:
            die(f"没找到 No Reverb 输出,实际输出: {[p.name for p in outs2]}")
        dry_final = args.outdir / f"inst_from_{stem}_dereverb.wav"
        shutil.move(str(dry), dry_final)
        for p in outs2:  # 丢弃 Reverb 残渣
            if p.exists() and p != dry:
                p.unlink()
        print(f"[separate] 完成 → {dry_final}(与 {inst_final.name} A/B 后选一个)")
    else:
        print(f"[separate] 完成 → {inst_final}")
        print("[separate] 若伴奏里能听到人声混响残留,重跑加 --dereverb")


if __name__ == "__main__":
    main()
