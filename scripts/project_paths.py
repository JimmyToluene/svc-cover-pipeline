#!/usr/bin/env python3
"""Shared project path resolution — the --project mechanism used by every script.

Repo layout: scripts/ is the song-agnostic pipeline; each song gets its own
project directory (with the seven subdirectories refs/lyrics/vocal/inst/models/
output/docs). All default paths inside the scripts resolve relative to the
project directory.

The project directory is determined in this order:
  1. --project on the command line (absolute, or relative to the repo root)
  2. the SVC_PROJECT environment variable
  3. the default, nianzhangshi

To start a new project: python scripts/new_project.py <name> scaffolds an empty
directory tree.
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
                    help="project directory (absolute or relative to the repo root; "
                         "default $SVC_PROJECT, else nianzhangshi)")


def resolve_project(args) -> Path:
    """Resolve args.project to an existing absolute path, store it back on args.project, and return it."""
    p = args.project.expanduser()
    if not p.is_absolute():
        p = REPO / p
    if not p.is_dir():
        print(f"[project] error: project directory does not exist: {p}\n"
              f"          create it with: python scripts/new_project.py {args.project}",
              file=sys.stderr)
        sys.exit(1)
    args.project = p.resolve()
    return args.project
