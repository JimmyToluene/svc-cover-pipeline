#!/usr/bin/env python3
"""通用工程路径解析 — 所有脚本共享的 --project 机制。

repo 布局:scripts/ 是通用管线,每首歌一个工程目录(含 refs/lyrics/vocal/
inst/models/output/docs 七个子目录)。脚本内所有默认路径都相对工程目录解析。

工程目录的确定顺序:
  1. 命令行 --project(绝对路径,或相对 repo 根)
  2. 环境变量 SVC_PROJECT
  3. 默认 nianzhangshi

新开工程:python scripts/new_project.py <名字> 脚手架一套空目录。
"""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SUBDIRS = ("refs", "lyrics", "lyrics/drafts", "vocal", "vocal/svc_out",
           "models", "inst", "output", "docs")


def add_project_arg(ap):
    ap.add_argument("--project", type=Path,
                    default=Path(os.environ.get("SVC_PROJECT", "nianzhangshi")),
                    help="工程目录(绝对路径或相对 repo 根;"
                         "默认 $SVC_PROJECT,否则 nianzhangshi)")


def resolve_project(args) -> Path:
    """把 args.project 解析成存在的绝对路径,顺便挂到 args.project 上返回。"""
    p = args.project.expanduser()
    if not p.is_absolute():
        p = REPO / p
    if not p.is_dir():
        print(f"[project] 错误: 工程目录不存在: {p}\n"
              f"          新开工程: python scripts/new_project.py {args.project}",
              file=sys.stderr)
        sys.exit(1)
    args.project = p.resolve()
    return args.project
