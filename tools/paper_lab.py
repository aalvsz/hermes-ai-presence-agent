#!/usr/bin/env python3
"""Initialize bounded local paper reimplementation packages."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def labs_root() -> Path:
    runtime = Path(os.environ.get("HERMES_PRESENCE_RUNTIME", ROOT / "runtime")).expanduser()
    return runtime / "paper-labs"


def init_lab(args: argparse.Namespace) -> int:
    if not SLUG_RE.fullmatch(args.slug):
        raise ValueError("slug must contain lowercase letters, numbers, and single dashes")
    destination = labs_root() / args.slug
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"lab already exists and is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata = {
        "slug": args.slug,
        "title": args.title,
        "paper_url": args.paper_url,
        "official_code_url": args.official_code_url,
        "created_at": created,
        "scope": args.scope,
    }
    status = {
        "level": "scaffolded",
        "updated_at": created,
        "claim": args.claim,
        "success_metric": args.metric,
        "evidence": [],
        "limitations": [],
        "github_publication_approved": False,
        "x_publication_approved": False,
    }
    (destination / "paper.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (destination / "STATUS.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    (destination / "EXPERIMENT_LOG.md").write_text(
        f"# Experiment log — {args.title}\n\nCreated: {created}\n\n## Planned claim\n\n{args.claim or 'TBD'}\n\n## Runs\n\nNo runs yet.\n",
        encoding="utf-8",
    )
    (destination / "README.md").write_text(
        f"# {args.title}\n\nPaper: {args.paper_url}\n\nStatus: scaffolded; no reproduction claim.\n\n## Scope\n\n{args.scope or 'TBD'}\n",
        encoding="utf-8",
    )
    (destination / "publication-manifest.json").write_text(
        json.dumps({
            "enabled": False,
            "repository": None,
            "visibility": None,
            "license": None,
            "commit": None,
            "claims": [],
            "disclosure": "AI-assisted implementation; evidence and limitations must be reviewed before publication.",
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "created", "path": str(destination), "metadata": metadata}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)
    init = sub.add_parser("init")
    init.add_argument("--slug", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--paper-url", required=True)
    init.add_argument("--official-code-url")
    init.add_argument("--scope", default="")
    init.add_argument("--claim", default="")
    init.add_argument("--metric", default="")
    init.set_defaults(func=init_lab)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
