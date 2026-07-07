#!/usr/bin/env python3
"""Scaffolding: create a new cover-song project directory (the input layout for the scripts/ pipeline).

Usage:
  python scripts/new_project.py <project name or path>

Afterwards, point any script at it with --project <name> (or export
SVC_PROJECT=<name>). See the directory-structure section in CLAUDE.md for what
goes in each subdirectory.
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
    print(f"[new_project] created {p} with subdirectories: {', '.join(SUBDIRS)}")
    print("[new_project] next steps: put the reference audio in refs/ and the SVC "
          "model directory in models/, then work through Phase 0-1 for lyrics/")


if __name__ == "__main__":
    main()
