#!/usr/bin/env python3
"""Local approval ledger for drafts destined for public channels."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"^[A-Z0-9-]{8,40}$")


def queue_dir() -> Path:
    runtime = Path(os.environ.get("HERMES_PRESENCE_RUNTIME", ROOT / "runtime")).expanduser()
    return runtime / "content"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def draft_path(draft_id: str) -> Path:
    if not ID_RE.fullmatch(draft_id):
        raise ValueError("invalid draft id")
    return queue_dir() / f"{draft_id}.json"


def load_draft(draft_id: str) -> dict[str, Any]:
    return json.loads(draft_path(draft_id).read_text(encoding="utf-8"))


def new_id() -> str:
    return "DRAFT-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")[:22]


def cmd_enqueue(args: argparse.Namespace) -> int:
    text = args.text.strip()
    if not text:
        raise ValueError("draft text is empty")
    if args.kind == "tweet" and len(text) > 280:
        raise ValueError(f"tweet draft is {len(text)} characters; maximum is 280")
    draft_id = new_id()
    payload = {
        "id": draft_id,
        "kind": args.kind,
        "state": "draft",
        "text": text,
        "character_count": len(text),
        "sources": list(dict.fromkeys(args.source or [])),
        "evidence": list(dict.fromkeys(args.evidence or [])),
        "created_at": now(),
        "approval": None,
        "publication": None,
    }
    atomic_write(draft_path(draft_id), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    records = []
    if queue_dir().exists():
        for path in sorted(queue_dir().glob("DRAFT-*.json"), reverse=True):
            record = json.loads(path.read_text(encoding="utf-8"))
            records.append({key: record.get(key) for key in ("id", "kind", "state", "character_count", "created_at")})
    print(json.dumps(records, ensure_ascii=False, indent=2))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    print(json.dumps(load_draft(args.id), ensure_ascii=False, indent=2))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    record = load_draft(args.id)
    expected = f"APPROVE POST {args.id}"
    if args.confirmation != expected:
        raise ValueError(f"confirmation must be exactly: {expected}")
    if record.get("state") == "published":
        raise ValueError("draft is already published")
    record["state"] = "approved"
    record["approval"] = {"phrase": expected, "approved_at": now()}
    atomic_write(draft_path(args.id), record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def cmd_record_publication(args: argparse.Namespace) -> int:
    record = load_draft(args.id)
    if record.get("state") != "approved" or not record.get("approval"):
        raise ValueError("draft is not approved")
    if not args.receipt.strip():
        raise ValueError("publication receipt is required")
    record["state"] = "published"
    record["publication"] = {"receipt": args.receipt.strip(), "published_at": now()}
    atomic_write(draft_path(args.id), record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--kind", choices=("tweet", "thread", "github_announcement"), default="tweet")
    enqueue.add_argument("--text", required=True)
    enqueue.add_argument("--source", action="append")
    enqueue.add_argument("--evidence", action="append")
    enqueue.set_defaults(func=cmd_enqueue)
    listing = sub.add_parser("list")
    listing.set_defaults(func=cmd_list)
    show = sub.add_parser("show")
    show.add_argument("id")
    show.set_defaults(func=cmd_show)
    approve = sub.add_parser("approve")
    approve.add_argument("id")
    approve.add_argument("--confirmation", required=True)
    approve.set_defaults(func=cmd_approve)
    publication = sub.add_parser("record-publication")
    publication.add_argument("id")
    publication.add_argument("--receipt", required=True)
    publication.set_defaults(func=cmd_record_publication)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
