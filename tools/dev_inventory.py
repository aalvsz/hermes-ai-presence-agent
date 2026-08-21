#!/usr/bin/env python3
"""Read-only metadata inventory of Git repositories below a development root.

This is deliberately a catalog, not a source-code ingest. It records repository
identity, Git state, languages, manifests, and small project signals so the
contribution scout can match public opportunities to the user's local work.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "target",
    "vendor",
    "checkpoints",
    "outputs",
    "artifacts",
    "cache",
    "caches",
}
EXTENSIONS = {
    ".py": "Python",
    ".pyi": "Python",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".h": "C/C++",
    ".hpp": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".rs": "Rust",
    ".go": "Go",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
    ".tex": "TeX",
}
MANIFESTS = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "environment.yml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "CMakeLists.txt",
    "Makefile",
    "Package.swift",
}


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)
    if result.returncode:
        return ""
    return result.stdout.strip()


def sanitize_remote(value: str) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value if "://" in value else "https://" + value)
    host = parsed.hostname or ""
    path = parsed.path.strip("/")
    if not host or not path:
        return None
    return f"{host}/{path.removesuffix('.git')}"


def _is_repo(path: Path) -> bool:
    marker = path / ".git"
    return marker.is_dir() or marker.is_file()


def find_repositories(root: Path) -> list[Path]:
    found: list[Path] = []
    for current, dirs, _files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not name.startswith(".hermes")]
        path = Path(current)
        if _is_repo(path):
            found.append(path)
            dirs[:] = [name for name in dirs if name != ".git"]
    return sorted(found)


def inspect_repository(repo: Path, root: Path) -> dict[str, Any]:
    tracked = _git(repo, "ls-files", "-z")
    names = [name for name in tracked.split("\0") if name]
    languages = Counter(EXTENSIONS.get(Path(name).suffix.lower()) for name in names)
    languages.pop(None, None)
    status = _git(repo, "status", "--porcelain", "--untracked-files=no")
    branch = _git(repo, "branch", "--show-current") or _git(repo, "rev-parse", "--short", "HEAD")
    return {
        "path": str(repo),
        "relative_path": str(repo.relative_to(root)),
        "name": repo.name,
        "branch_or_revision": branch,
        "dirty_tracked": bool(status),
        "tracked_file_count": len(names),
        "languages": dict(sorted(languages.items(), key=lambda pair: (-pair[1], pair[0]))),
        "manifests": sorted(name for name in MANIFESTS if (repo / name).is_file()),
        "top_level_entries": sorted(
            entry.name for entry in repo.iterdir() if entry.name not in SKIP_DIRS and not entry.name.startswith(".git")
        )[:80],
        "origin": sanitize_remote(_git(repo, "remote", "get-url", "origin")),
        "last_commit_at": _git(repo, "log", "-1", "--format=%cI") or None,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Development repository inventory",
        "",
        f"Scanned: `{report['scanned_at']}`",
        f"Repositories found: **{len(report['repositories'])}**",
        "",
        "This is metadata only: no project code was executed and no full source tree was copied into the report.",
        "",
        "| Repository | Languages | Tracked files | Git state |",
        "| --- | --- | ---: | --- |",
    ]
    for item in report["repositories"]:
        languages = ", ".join(item["languages"].keys()) or "unknown"
        state = "dirty" if item["dirty_tracked"] else "clean"
        lines.append(f"| `{item['relative_path']}` | {languages} | {item['tracked_file_count']} | {state} |")
    return "\n".join(lines) + "\n"


def build_report(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    repos = [inspect_repository(repo, root) for repo in find_repositories(root)] if root.is_dir() else []
    return {"schema_version": 1, "scanned_at": dt.datetime.now(dt.timezone.utc).isoformat(), "root": str(root), "repositories": repos}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("HERMES_DEV_ROOT", "dev")),
        help="development root (default: HERMES_DEV_ROOT or ./dev)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("runtime/dev-inventory"))
    args = parser.parse_args(argv)
    report = build_report(args.root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "inventory.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "inventory.md").write_text(markdown(report))
    print(f"wrote {args.output_dir / 'inventory.json'} and {args.output_dir / 'inventory.md'} ({len(report['repositories'])} repositories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
