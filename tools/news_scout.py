#!/usr/bin/env python3
"""Small, dependency-free RSS/Atom and Hugging Face paper aggregator."""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "news_sources.json"
USER_AGENT = "HermesAIPresence/1.0 (+local research aggregator)"


def runtime_root() -> Path:
    return Path(os.environ.get("HERMES_PRESENCE_RUNTIME", ROOT / "runtime")).expanduser()


def clean_text(value: str | None) -> str:
    value = unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch(url: str, timeout: float = 20.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/json, text/xml;q=0.9, */*;q=0.5"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def child_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in node:
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in names and child.text:
            return child.text
    return ""


def entry_link(node: ET.Element) -> str:
    for child in node:
        if child.tag.rsplit("}", 1)[-1].lower() == "link":
            href = child.attrib.get("href")
            if href and child.attrib.get("rel", "alternate") in {"alternate", ""}:
                return href
            if child.text:
                return child.text.strip()
    return ""


def parse_feed(payload: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    items = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}]
    results: list[dict[str, Any]] = []
    for node in items:
        title = clean_text(child_text(node, ("title",)))
        link = entry_link(node)
        summary = clean_text(child_text(node, ("description", "summary", "content")))
        published_raw = child_text(node, ("pubdate", "published", "updated", "date"))
        published = parse_date(published_raw)
        if not title or not link:
            continue
        uid = hashlib.sha256(f"{source['name']}\0{link}".encode()).hexdigest()[:20]
        results.append({
            "id": uid,
            "source": source["name"],
            "category": source.get("category", "other"),
            "title": title,
            "url": link,
            "summary": summary[:1200],
            "published_at": published.isoformat().replace("+00:00", "Z") if published else None,
            "source_kind": "feed",
        })
    return results


def parse_hf_papers(payload: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    raw = json.loads(payload)
    rows = raw if isinstance(raw, list) else raw.get("papers", raw.get("data", []))
    results: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        paper = row.get("paper", row) if isinstance(row, dict) else {}
        paper_id = str(paper.get("id") or paper.get("paperId") or "").strip()
        title = clean_text(paper.get("title"))
        if not paper_id or not title:
            continue
        published = parse_date(row.get("publishedAt") or paper.get("publishedAt") or paper.get("published_at"))
        summary = clean_text(paper.get("summary") or paper.get("ai_summary") or row.get("summary"))
        results.append({
            "id": hashlib.sha256(f"hf\0{paper_id}".encode()).hexdigest()[:20],
            "source": source["name"],
            "category": source.get("category", "papers"),
            "title": title,
            "url": f"https://huggingface.co/papers/{paper_id}",
            "summary": summary[:1200],
            "published_at": published.isoformat().replace("+00:00", "Z") if published else None,
            "source_kind": "huggingface_daily_papers",
            "paper_id": paper_id,
            "github_url": paper.get("githubRepo") or paper.get("github_url"),
        })
    return results


def collect(config: dict[str, Any], since: datetime | None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for source in config.get("feeds", []):
        try:
            items.extend(parse_feed(fetch(source["url"]), source))
        except (OSError, urllib.error.URLError, ET.ParseError, ValueError) as exc:
            errors.append({"source": source.get("name", source.get("url", "unknown")), "error": str(exc)})
    hf = config.get("huggingface_daily_papers")
    if hf:
        try:
            items.extend(parse_hf_papers(fetch(hf["url"]), hf))
        except (OSError, urllib.error.URLError, ValueError) as exc:
            errors.append({"source": hf.get("name", hf.get("url", "unknown")), "error": str(exc)})

    deduped: dict[str, dict[str, Any]] = {item["url"]: item for item in items}
    filtered = []
    for item in deduped.values():
        published = parse_date(item.get("published_at"))
        if since and published and published < since:
            continue
        filtered.append(item)
    filtered.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    return filtered, errors


def balanced_limit(items: list[dict[str, Any]], per_source: int, total: int) -> list[dict[str, Any]]:
    """Prevent high-volume feeds such as arXiv from crowding out all other sources."""
    source_counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for item in items:
        source = item["source"]
        if source_counts.get(source, 0) >= per_source:
            continue
        selected.append(item)
        source_counts[source] = source_counts.get(source, 0) + 1
        if len(selected) >= total:
            break
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--since-hours", type=float, default=72)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--per-source-limit", type=int, default=12)
    parser.add_argument("--write-snapshot", action="store_true")
    args = parser.parse_args(argv)
    if args.since_hours <= 0 or args.limit <= 0 or args.per_source_limit <= 0:
        parser.error("--since-hours, --limit, and --per-source-limit must be positive")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    generated = datetime.now(timezone.utc)
    since = generated - timedelta(hours=args.since_hours)
    items, errors = collect(config, since)
    source_counts: dict[str, int] = {}
    for item in items:
        source_counts[item["source"]] = source_counts.get(item["source"], 0) + 1
    selected = balanced_limit(items, args.per_source_limit, args.limit)
    result = {
        "generated_at": generated.isoformat().replace("+00:00", "Z"),
        "since": since.isoformat().replace("+00:00", "Z"),
        "count": len(selected),
        "total_candidates": len(items),
        "source_counts": source_counts,
        "items": selected,
        "errors": errors,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.write_snapshot:
        destination = runtime_root() / "news" / f"snapshot-{generated.strftime('%Y%m%dT%H%M%SZ')}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")
        result["snapshot"] = str(destination)
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
