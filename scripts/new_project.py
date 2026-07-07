#!/usr/bin/env python3
"""脚手架:新建一个翻唱工程目录(scripts/ 管线的输入布局)。

用法:
  python scripts/new_project.py <工程名或路径>

之后所有脚本加 --project <工程名> 即可指向它(或 export AIMAD_PROJECT=<工程名>)。
各子目录放什么见 CLAUDE.md 的目录结构说明。
"""

import sys
from pathlib import Path

from project_paths import REPO, SUBDIRS


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    p = Path(sys.argv[1]).expanduser()
    if not p.is_absolute():
        p = REPO / p
    for sub in SUBDIRS:
        (p / sub).mkdir(parents=True, exist_ok=True)
    print(f"[new_project] 已创建 {p} 及子目录: {', '.join(SUBDIRS)}")
    print("[new_project] 下一步:refs/ 放参照音频,models/ 放 SVC 模型目录,"
          "lyrics/ 走 Phase 0-1")


if __name__ == "__main__":
    main()
