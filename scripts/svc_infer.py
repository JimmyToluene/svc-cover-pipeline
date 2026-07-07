#!/usr/bin/env python3
"""Phase 3 — so-vits-svc 4.1 参数网格跑批。

封装 so-vits-svc 4.1-Stable 的 inference_main.py:
自动检测 <project>/models/ 里的模型文件(唯一含 config.json 的子目录,或直接
--model-dir 指定),按 transpose × cluster_ratio × f0_predictor × (浅扩散)
网格逐个推理,结果收集到 <project>/vocal/svc_out/(文件名编码参数),
并生成/追加 <project>/docs/svc_grid.md 盲听对比表。

依赖:仅标准库 + 系统 ffmpeg(输入下混单声道用)。
so-vits-svc 自身的依赖属于其 checkout 的环境,用 --python 指定该环境的解释器。

示例:
  python scripts/svc_infer.py --svc-repo ~/so-vits-svc -t 0 12 --dry-run
"""

import argparse
import datetime
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from project_paths import add_project_arg, resolve_project


def die(msg):
    print(f"[svc_infer] 错误: {msg}", file=sys.stderr)
    sys.exit(1)


def default_model_dir(proj: Path) -> Path:
    """<project>/models 本身是模型目录就用它;否则要求恰好一个含 config.json 的子目录。"""
    root = proj / "models"
    if (root / "config.json").is_file():
        return root
    cands = (sorted(d for d in root.iterdir()
                    if d.is_dir() and (d / "config.json").is_file())
             if root.is_dir() else [])
    if len(cands) == 1:
        return cands[0]
    if not cands:
        die(f"{root} 下没找到模型目录(需含 config.json),用 --model-dir 指定")
    die(f"{root} 下有多个模型目录 {[d.name for d in cands]},用 --model-dir 指定")


def detect_model(model_dir: Path):
    """返回 dict: gen/config 必有;cluster/feature_index/diff_model/diff_config 可无。"""
    if not model_dir.is_dir():
        die(f"模型目录不存在: {model_dir}")

    gens = sorted(model_dir.glob("G_*.pth"))
    if not gens:
        gens = [p for p in model_dir.glob("*.pth") if not p.name.startswith("D_")]
    if not gens:
        die(f"{model_dir} 里没有生成器权重 (G_*.pth)")
    # 多个 checkpoint 时取步数最大的;取最后一段数字,避免名字里的采样率/版本号干扰
    def step(p):
        m = re.findall(r"\d+", p.stem)
        return int(m[-1]) if m else -1
    gen = max(gens, key=step)

    config = model_dir / "config.json"
    if not config.is_file():
        cands = list(model_dir.glob("*.json"))
        if len(cands) == 1:
            config = cands[0]
        else:
            die(f"{model_dir} 里没有 config.json")

    feature_index = next(iter(model_dir.glob("*.pkl")), None)
    cluster = next(iter(model_dir.glob("kmeans*.pt")), None)

    diff_model = diff_config = None
    for d, pat in ((model_dir / "diffusion", "*.pt"), (model_dir, "model_*.pt")):
        # 根目录用窄模式,避免把 kmeans*.pt 误认成扩散模型
        pts = [p for p in d.glob(pat) if not p.name.startswith("kmeans")] if d.is_dir() else []
        yamls = list(d.glob("*.yaml")) if d.is_dir() else []
        if pts and yamls:
            diff_model, diff_config = max(pts, key=step), yamls[0]
            break

    return {
        "gen": gen, "config": config,
        "cluster": cluster, "feature_index": feature_index,
        "diff_model": diff_model, "diff_config": diff_config,
    }


def read_config(config_path: Path):
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    spk = list(cfg.get("spk", {}).keys())
    if not spk:
        die(f"{config_path} 里没有 spk 表,无法确定 -s 说话人名")
    encoder = cfg.get("model", {}).get("speech_encoder")
    if encoder is None:
        # 缺 speech_encoder 字段 = 4.0 时代模型,4.1 推理前必须补上
        print("[svc_infer] 警告: config.json 缺 model.speech_encoder,疑似 4.0 模型。"
              '需在 model 块补 "speech_encoder": "vec256l9"(ssl_dim=256 时)再跑。',
              file=sys.stderr)
        encoder = "vec256l9?"
    sr = cfg.get("data", {}).get("sampling_rate", 44100)
    return spk, encoder, sr


def prepare_input(src: Path, svc_repo: Path, sr: int, dry: bool) -> str:
    """下混单声道 + 重采样到模型采样率,放进 svc repo 的 raw/。返回 clean_name。"""
    raw_dir = svc_repo / "raw"
    clean_name = src.stem + ".wav"
    cmd = ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", str(sr),
           "-acodec", "pcm_s16le", str(raw_dir / clean_name)]
    print("[svc_infer] 输入预处理:", " ".join(cmd))
    if not dry:
        if shutil.which("ffmpeg") is None:
            die("找不到 ffmpeg,请先安装(输入需下混单声道:sovits 对立体声 wav 只取左声道)")
        raw_dir.mkdir(exist_ok=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            die(f"ffmpeg 失败:\n{r.stderr[-2000:]}")
    return clean_name


def out_name(stem, f0p, t, cr, use_fr, shd, args):
    parts = [stem, f"f0{f0p}", f"t{t:+d}"]
    if cr > 0:
        parts.append(f"cr{cr}" + ("fr" if use_fr else "km"))
    if shd:
        parts.append(f"shd{args.k_step}")
    # 非默认的次要参数也编进文件名,防止两次跑批互相覆盖
    if args.noice_scale != 0.4:
        parts.append(f"ns{args.noice_scale:g}")
    if args.slice_db != -50:
        parts.append(f"sd{args.slice_db}")
    if args.clip:
        parts.append(f"cl{args.clip:g}")
    return "_".join(parts) + ".wav"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--svc-repo", required=True, type=Path,
                    help="so-vits-svc 4.1-Stable checkout 路径")
    ap.add_argument("--input", type=Path, default=None,
                    help="SynthV 导出的干声 wav,默认 <project>/vocal/synthv_source.wav")
    ap.add_argument("--model-dir", type=Path, default=None,
                    help="默认自动检测 <project>/models/ 下唯一的模型目录")
    ap.add_argument("--speaker", default=None,
                    help="config.json spk 表中的说话人名,默认取第一个")
    ap.add_argument("-t", "--transpose", type=int, nargs="+", default=[0],
                    help="半音变调网格,如: -t 0 12 -12")
    ap.add_argument("--cr", type=float, nargs="+", default=None,
                    help="聚类/特征检索占比网格;默认:模型带 kmeans/index 时 "
                         "{0, 0.3, 0.5},否则 {0}")
    ap.add_argument("--f0", nargs="+", default=["rmvpe"],
                    choices=["crepe", "pm", "dio", "harvest", "rmvpe", "fcpe"],
                    help="f0 预测器网格(注意 sovits CLI 自身默认是 pm,这里默认 rmvpe)")
    ap.add_argument("--shd", choices=["auto", "off", "only"], default="auto",
                    help="浅扩散:auto=模型带扩散时每组参数加跑一版;only=只跑浅扩散版")
    ap.add_argument("--k-step", type=int, default=100, help="浅扩散步数")
    ap.add_argument("--noice-scale", type=float, default=0.4)
    ap.add_argument("--slice-db", type=int, default=-50,
                    help="切片阈值;干声保留呼吸声用 -50(sovits README 建议)")
    ap.add_argument("--clip", type=float, default=0, help="强制切片秒数,0=自动")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--python", default=sys.executable,
                    help="运行 inference_main.py 用的解释器(sovits 环境)")
    ap.add_argument("--dry-run", action="store_true", help="只打印命令不执行")
    args = ap.parse_args()
    proj = resolve_project(args)
    out_dir = proj / "vocal" / "svc_out"
    grid_md = proj / "docs" / "svc_grid.md"

    svc_repo = args.svc_repo.expanduser().resolve()
    args.input = (args.input or proj / "vocal" / "synthv_source.wav").expanduser()
    if not (svc_repo / "inference_main.py").is_file():
        die(f"{svc_repo} 不是 so-vits-svc checkout(缺 inference_main.py)")
    if not args.input.is_file():
        die(f"输入不存在: {args.input}")
    if not args.dry_run and shutil.which(args.python) is None \
            and not Path(args.python).expanduser().is_file():
        die(f"--python 解释器不存在: {args.python}")

    model_dir = (args.model_dir.expanduser().resolve() if args.model_dir
                 else default_model_dir(proj))
    m = detect_model(model_dir)
    speakers, encoder, sr = read_config(m["config"])
    speaker = args.speaker or speakers[0]
    if speaker not in speakers:
        die(f"说话人 {speaker!r} 不在 config.json spk 表里,可选: {speakers}")

    cluster_asset = m["feature_index"] or m["cluster"]
    use_fr = m["feature_index"] is not None
    ratios = args.cr if args.cr is not None else ([0.0, 0.3, 0.5] if cluster_asset else [0.0])
    dropped = [r for r in ratios if r > 0 and not cluster_asset]
    if dropped:
        print(f"[svc_infer] 模型没带 kmeans/特征检索,跳过 cr={dropped}", file=sys.stderr)
        ratios = [r for r in ratios if r == 0 or cluster_asset] or [0.0]

    has_diff = m["diff_model"] is not None
    if args.shd != "off" and not has_diff:
        if args.shd == "only":
            die("--shd only 但模型目录里没有扩散模型 (model_*.pt + *.yaml)")
        print("[svc_infer] 模型没带扩散,只跑纯 sovits 版", file=sys.stderr)
    shd_variants = {"off": [False], "only": [True],
                    "auto": [False, True] if has_diff else [False]}[args.shd]

    # 浅扩散的 vocoder 是 yaml 里 cwd 相对路径,不预检会跑到一半才炸
    if True in shd_variants:
        mt = re.search(r"^\s*ckpt:\s*(\S+)", m["diff_config"].read_text(encoding="utf-8"),
                       re.M)
        voc_rel = mt.group(1) if mt else "pretrain/nsf_hifigan/model"
        if not (svc_repo / voc_rel).is_file():
            msg = (f"浅扩散 vocoder 缺失: {svc_repo / voc_rel}"
                   f"(diffusion.yaml vocoder.ckpt={voc_rel},见 docs/svc_model_notes.md)")
            if args.dry_run:
                print(f"[svc_infer] 警告: {msg}", file=sys.stderr)
            elif args.shd == "only":
                die(msg)
            else:
                print(f"[svc_infer] 警告: {msg},跳过浅扩散版", file=sys.stderr)
                shd_variants = [False]

    print(f"[svc_infer] 模型: {m['gen'].name}  encoder={encoder}  sr={sr}  "
          f"speaker={speaker}")
    print(f"[svc_infer] 检索资产: {cluster_asset.name if cluster_asset else '无'}"
          f"{'(特征检索)' if use_fr else '(聚类)' if cluster_asset else ''}  "
          f"扩散: {m['diff_model'].name if has_diff else '无'}")

    clean_name = prepare_input(args.input.resolve(), svc_repo, sr, args.dry_run)
    stem = args.input.stem

    # whisper-ppg 编码器不加 -cl 25 -lg 1 会推理失败(sovits README 特例)
    clip, lg = args.clip, 0.0
    if str(encoder).startswith("whisper"):
        clip, lg = 25, 1
        print("[svc_infer] whisper-ppg 编码器:强制 -cl 25 -lg 1", file=sys.stderr)

    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir = svc_repo / "results"
    rows, failures = [], 0

    interrupted = False
    for f0p, t, cr, shd in itertools.product(args.f0, args.transpose,
                                             ratios, shd_variants):
        cmd = [args.python, "inference_main.py",
               "-m", str(m["gen"]), "-c", str(m["config"]),
               "-n", clean_name, "-t", str(t), "-s", speaker,
               "-f0p", f0p, "-wf", "wav", "-d", args.device,
               "-ns", str(args.noice_scale),
               "-sd", str(args.slice_db),
               "-cl", str(clip), "-lg", str(lg)]
        if cr > 0:
            cmd += ["-cr", str(cr), "-cm", str(cluster_asset)]
            if use_fr:
                cmd += ["-fr"]
        if shd:
            cmd += ["-shd", "-dm", str(m["diff_model"]),
                    "-dc", str(m["diff_config"]),
                    "-ks", str(args.k_step)]

        dst = out_dir / out_name(stem, f0p, t, cr, use_fr, shd, args)
        print(f"\n[svc_infer] → {dst.name}\n  " + " ".join(cmd))
        if args.dry_run:
            continue

        try:
            # 记 mtime 而非文件集合:同参数重跑时 sovits 会覆盖同名产物,
            # 只看"新增文件"会把成功的重跑误判成失败
            before = ({p: p.stat().st_mtime for p in results_dir.glob("*.wav")}
                      if results_dir.is_dir() else {})
            t0 = time.time()
            # torch>=2.6 默认 weights_only=True,会拒载 fairseq/ContentVec 等
            # 2023 年代 checkpoint 里的自定义类;这些文件本就是用户选择信任的模型资产
            r = subprocess.run(cmd, cwd=svc_repo,
                               env={**os.environ,
                                    "TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD": "1"})
            dur = time.time() - t0
            after = {p: p.stat().st_mtime for p in results_dir.glob("*.wav")}
            new = sorted((p for p, mt in after.items() if before.get(p) != mt),
                         key=after.get)
            if r.returncode != 0 or not new:
                print(f"[svc_infer] 失败 (exit={r.returncode}, "
                      f"新产物 {len(new)} 个)", file=sys.stderr)
                failures += 1
                rows.append((dst.name, f0p, t, cr, shd, f"失败 exit={r.returncode}"))
                continue
            if len(new) > 1:
                print(f"[svc_infer] 警告: 产生 {len(new)} 个新 wav,"
                      f"只收集最新的,其余留在 {results_dir}", file=sys.stderr)
            shutil.move(str(new[-1]), dst)
            rows.append((dst.name, f0p, t, cr, shd, f"{dur:.0f}s"))
        except KeyboardInterrupt:  # Ctrl-C 不丢已完成的行,照常写对比表
            print("\n[svc_infer] 中断:已完成的组合仍写入对比表", file=sys.stderr)
            failures += 1
            rows.append((dst.name, f0p, t, cr, shd, "中断"))
            interrupted = True
            break
        except Exception as e:  # 单组失败不拖垮整个网格,表里留痕
            print(f"[svc_infer] 异常: {e}", file=sys.stderr)
            failures += 1
            rows.append((dst.name, f0p, t, cr, shd, f"异常 {type(e).__name__}"))

    if args.dry_run:
        print("\n[svc_infer] dry-run 结束,未执行推理")
        return

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    if not grid_md.exists():
        lines += ["# Phase 3 — so-vits-svc 参数网格盲听对比\n",
                  "备注列由用户盲听后填写;selected.wav = 最终选定版。\n"]
    lines += [f"\n## 批次 {stamp} — 输入 `{args.input.name}`,"
              f"模型 `{m['gen'].name}`,speaker `{speaker}`\n",
              "| 文件 (vocal/svc_out/) | f0 | trans | cr | 浅扩散 | 耗时/状态 | 盲听备注 |",
              "|---|---|---|---|---|---|---|"]
    for name, f0p, t, cr, shd, status in rows:
        cell = name.replace("|", "\\|")
        lines.append(f"| `{cell}` | {f0p} | {t:+d} | {cr} | "
                     f"{'k=' + str(args.k_step) if shd else '—'} | {status} | |")
    with grid_md.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    ok = len(rows) - failures
    print(f"\n[svc_infer] 完成: {ok}/{len(rows)} 成功 → {out_dir}")
    print(f"[svc_infer] 对比表已追加: {grid_md}")
    if interrupted:
        sys.exit(130)
    if failures:
        sys.exit(2)


if __name__ == "__main__":
    main()
