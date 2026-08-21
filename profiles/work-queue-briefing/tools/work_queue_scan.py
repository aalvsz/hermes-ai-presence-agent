#!/usr/bin/env python3
"""Read-only GitHub/GitLab work-queue scanner for the Multiverse office.

The scanner asks the already-authenticated CLIs for open items assigned to the
current user. It never prints credentials, fetches bodies/comments/diffs, or
uses a write endpoint. Partial results are preserved when one provider is not
available.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


class ProviderError(RuntimeError):
    """A safe provider error that does not include command environments."""


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _run(command: list[str]) -> str:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise ProviderError(f"{command[0]} is not installed") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "provider request failed").strip().splitlines()
        raise ProviderError(detail[-1] if detail else "provider request failed")
    return result.stdout


def _json(command: list[str]) -> Any:
    try:
        return json.loads(_run(command))
    except json.JSONDecodeError as exc:
        raise ProviderError("provider returned invalid JSON") from exc


def _labels(item: dict[str, Any]) -> list[str]:
    values = item.get("labels") or []
    return sorted(
        {
            str(value.get("name", value) if isinstance(value, dict) else value)
            for value in values
            if str(value.get("name", value) if isinstance(value, dict) else value).strip()
        }
    )


def normalize_github(item: dict[str, Any]) -> dict[str, Any]:
    # GitHub returns an empty object for pull_request on some search results,
    # so presence of the field—not truthiness—is the discriminator.
    pull = "pull_request" in item
    repo = item.get("repository") or {}
    return {
        "provider": "github",
        "kind": "pull_request" if pull else "issue",
        "repository": repo.get("full_name") or repo.get("name") or "unknown",
        "number": item.get("number"),
        "title": str(item.get("title") or ""),
        "url": item.get("html_url") or "",
        "updated_at": item.get("updated_at"),
        "labels": _labels(item),
        "draft": bool(item.get("draft")) if pull else None,
    }


def normalize_gitlab(item: dict[str, Any], kind: str) -> dict[str, Any]:
    project = item.get("references") or {}
    return {
        "provider": "gitlab",
        "kind": kind,
        "repository": project.get("full") or item.get("web_url", "").split("/-/")[0].rsplit("/", 1)[-1] or "unknown",
        "number": item.get("iid") or item.get("id"),
        "title": str(item.get("title") or ""),
        "url": item.get("web_url") or "",
        "updated_at": item.get("updated_at") or item.get("updatedAt"),
        "labels": sorted(str(label) for label in (item.get("labels") or []) if str(label).strip()),
        "draft": bool(item.get("draft")) if kind == "merge_request" else None,
    }


def scan_github(run: Callable[[list[str]], Any]) -> list[dict[str, Any]]:
    # Search resolves the authenticated identity server-side through @me; no
    # login is written to the report.
    raw = run(
        [
            "gh",
            "api",
            "search/issues?q=assignee%3A%40me%20is%3Aopen&per_page=100",
        ]
    )
    return [normalize_github(item) for item in (raw.get("items") or [])]


def scan_gitlab(run: Callable[[list[str]], Any]) -> list[dict[str, Any]]:
    issues = run(["glab", "api", "issues?scope=assigned_to_me&state=opened&per_page=100"])
    merge_requests = run(["glab", "api", "merge_requests?scope=assigned_to_me&state=opened&per_page=100"])
    return [normalize_gitlab(item, "issue") for item in (issues or [])] + [
        normalize_gitlab(item, "merge_request") for item in (merge_requests or [])
    ]


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Assigned work summary",
        "",
        f"Scanned: `{report['scanned_at']}`",
        "",
        "Read-only metadata for open GitHub/GitLab issues and pull/merge requests assigned to the authenticated user.",
        "",
    ]
    if not report["items"]:
        lines.append("No assigned open items were returned by the available providers.")
    for provider in ("github", "gitlab"):
        items = [item for item in report["items"] if item["provider"] == provider]
        lines += [f"## {provider.title()}", ""]
        if not items:
            lines.append("No items returned.")
            lines.append("")
            continue
        for kind in ("issue", "pull_request", "merge_request"):
            subset = [item for item in items if item["kind"] == kind]
            if not subset:
                continue
            heading = {"issue": "Issues", "pull_request": "Pull requests", "merge_request": "Merge requests"}[kind]
            lines += [f"### {heading}", ""]
            for item in subset:
                suffix = f" — updated {item['updated_at']}" if item.get("updated_at") else ""
                lines.append(f"- [{item['repository']} !{item['number']} {item['title']}]({item['url']}){suffix}")
            lines.append("")
    if report["errors"]:
        lines += ["## Provider notes", ""]
        lines.extend(f"- {provider}: {message}" for provider, message in report["errors"].items())
        lines.append("")
    lines += ["## Boundaries", "", "- No descriptions, comments, diffs, credentials, or mutation endpoints were requested.", "- Recheck each item before acting; this report is a prioritization aid, not an action authorization.", ""]
    return "\n".join(lines)


def build_report(runner: Callable[[list[str]], Any] = _json) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for provider, scan in (("github", scan_github), ("gitlab", scan_gitlab)):
        try:
            items.extend(scan(runner))
        except ProviderError as exc:
            errors[provider] = str(exc)
        except (KeyError, TypeError, ValueError) as exc:
            errors[provider] = f"unexpected response shape: {exc}"
    items.sort(key=lambda item: (item["provider"], item["kind"], item["repository"], item["number"] or 0))
    return {"schema_version": 1, "scanned_at": now_utc(), "items": items, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("runtime/work-queue"))
    args = parser.parse_args(argv)
    report = build_report()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "report.md").write_text(markdown(report))
    print(f"wrote {args.output_dir / 'report.json'} and {args.output_dir / 'report.md'}")
    return 0 if report["items"] or report["errors"] == {} else 2


if __name__ == "__main__":
    raise SystemExit(main())
