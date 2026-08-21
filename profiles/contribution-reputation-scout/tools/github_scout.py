#!/usr/bin/env python3
"""Read-only GitHub contribution-opportunity scanner.

The scores in this program are *friendliness signals*, not a prediction that a
pull request will be accepted.  It deliberately leaves issue claims, comments,
branches, and pull requests to the human-selected follow-up workflow.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable


NON_MEMBER_ASSOCIATIONS = {"NONE", "FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR", "CONTRIBUTOR"}
FIRST_TIME_ASSOCIATIONS = {"FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR"}
FRIENDLY_LABELS = {"good first issue", "good-first-issue", "help wanted", "help-wanted"}
BLOCKING_WORDS = {"blocked", "stale", "wontfix", "won't fix", "duplicate", "on hold", "waiting"}
BROAD_SCOPE_PHRASES = {"tracking issue", "tracking:", "umbrella", "roadmap", "implement missing ops", "support all"}
PROCESS_FILES = {"code_of_conduct", "contributing", "issue_template", "pull_request_template", "license"}


class GitHubAPIError(RuntimeError):
    """A safe error which never includes command environment or tokens."""


def utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def parse_github_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_bot(item: dict[str, Any]) -> bool:
    user = item.get("user") or {}
    login = str(user.get("login", "")).lower()
    kind = str(user.get("type", "")).lower()
    return kind == "bot" or login.endswith("[bot]") or login.endswith("-bot")


def text_blob(item: dict[str, Any]) -> str:
    labels = " ".join(str((x or {}).get("name", "")) for x in item.get("labels", []))
    return " ".join(str(item.get(k, "")) for k in ("title", "body", "state_reason")) + " " + labels


def score_repository(
    pull_requests: Iterable[dict[str, Any]],
    community: dict[str, Any] | None,
    candidate_count: int,
    pushed_at: str | None = None,
    now: dt.datetime | None = None,
    archived: bool = False,
) -> dict[str, Any]:
    """Calculate an interpretable 0-100 contribution friendliness score."""
    now = now or utcnow()
    prs = [p for p in pull_requests if not is_bot(p)]
    merged = [p for p in prs if p.get("merged_at")]
    non_member = [p for p in merged if str(p.get("author_association", "")).upper() in NON_MEMBER_ASSOCIATIONS]
    first_time = [p for p in non_member if str(p.get("author_association", "")).upper() in FIRST_TIME_ASSOCIATIONS]
    sample = len(merged)
    non_member_rate = len(non_member) / sample if sample else 0.0
    first_time_rate = len(first_time) / sample if sample else 0.0

    files = (community or {}).get("files") or {}
    process_count = sum(1 for key in PROCESS_FILES if files.get(key))
    process_score = round(20 * min(process_count / 4, 1))
    history_reliability = min(1.0, sample / 10)
    history_score = round((11 * non_member_rate + 24 * first_time_rate) * history_reliability)
    issue_score = min(15, candidate_count * 5)
    sample_score = min(15, round(sample * 1.5))
    pushed = parse_github_time(pushed_at)
    age_days = (now - pushed).days if pushed else None
    if age_days is None:
        freshness_score = 0
    elif age_days <= 7:
        freshness_score = 15
    elif age_days <= 30:
        freshness_score = 12
    elif age_days <= 90:
        freshness_score = 8
    elif age_days <= 180:
        freshness_score = 4
    else:
        freshness_score = 0
    score = min(100, history_score + process_score + issue_score + freshness_score + sample_score)
    if archived:
        score = 0

    # Confidence expresses amount/quality of observed evidence, not quality of a repo.
    confidence = min(100, round(sample_score * 2.5 + process_score * 1.5 + min(15, candidate_count * 5) * 1.5))
    return {
        "contribution_friendliness_score": score,
        "evidence_confidence": confidence,
        "evidence_confidence_band": "high" if confidence >= 75 else "medium" if confidence >= 50 else "low",
        "score_band": "archived" if archived else "high priority" if score >= 75 else "investigate manually" if score >= 55 else "low priority",
        "score_components": {
            "historical_non_member_associated_openness": history_score,
            "accessible_process": process_score,
            "current_friendly_issues": issue_score,
            "repository_freshness": freshness_score,
            "evidence_coverage": sample_score,
        },
        "samples": {"closed_prs_examined": len(prs), "merged_prs_examined": sample, "non_member_associated_merged_prs": len(non_member), "first_time_relation_merges": len(first_time), "open_candidate_issues": candidate_count},
        "non_member_association_counts": dict(Counter(str(p.get("author_association", "UNKNOWN")).upper() for p in non_member)),
        "non_member_merge_examples": [
            {
                "number": p.get("number"),
                "url": p.get("html_url"),
                "author": (p.get("user") or {}).get("login"),
                "author_association": p.get("author_association"),
                "merged_at": p.get("merged_at"),
            }
            for p in non_member[:5]
        ],
        "process_signals": {key: bool(files.get(key)) for key in sorted(PROCESS_FILES)},
        "notes": ["Scores are contribution-friendliness signals, never acceptance probabilities.", "GitHub author association does not establish employer or organizational affiliation. Non-member-associated merges require manual verification before they can be described as external contributions."],
    }


def score_issue(
    issue: dict[str, Any],
    now: dt.datetime | None = None,
    stale_issue_days: int = 120,
) -> dict[str, Any]:
    """Gate and score an issue without implying it is ready to claim."""
    now = now or utcnow()
    reasons: list[str] = []
    if issue.get("pull_request"):
        reasons.append("This API result is a pull request, not an issue.")
    if is_bot(issue):
        reasons.append("Bot-authored issue.")
    if issue.get("assignee") or issue.get("assignees"):
        reasons.append("Issue appears assigned.")
    blob = text_blob(issue).lower()
    if any(word in blob for word in BLOCKING_WORDS):
        reasons.append("Issue has a blocking/stale label or status clue.")
    updated = parse_github_time(issue.get("updated_at"))
    if updated and (now - updated).days > stale_issue_days:
        reasons.append(f"Issue has not been updated in more than {stale_issue_days} days.")
    if "linked pull request" in blob or "already fixed" in blob or "in progress" in blob:
        reasons.append("Issue text suggests linked work or work in progress.")

    labels = {str((x or {}).get("name", "")).lower() for x in issue.get("labels", [])}
    scope_warnings = [phrase for phrase in sorted(BROAD_SCOPE_PHRASES) if phrase in blob]
    score = 30
    if labels & FRIENDLY_LABELS:
        score += 30
    if issue.get("body"):
        score += 10
    if updated and (now - updated).days <= 30:
        score += 15
    if "test" in blob:
        score += 5
    if "documentation" in blob or "docs" in blob:
        score += 5
    if scope_warnings:
        score -= 25
    if reasons:
        score = 0
    return {"issue_number": issue.get("number"), "title": issue.get("title", ""), "url": issue.get("html_url", ""), "candidate_score": max(0, min(100, score)), "eligible_for_human_review": not reasons, "gates": reasons, "scope_warnings": scope_warnings, "requires_timeline_validation": True, "labels": sorted(labels), "updated_at": issue.get("updated_at"), "assignee_logins": [a.get("login") for a in issue.get("assignees", []) if a.get("login")]}


class GitHubClient:
    def __init__(self, fetch: Callable[[str], Any] | None = None) -> None:
        self.fetch = fetch or self._gh_fetch

    @staticmethod
    def _gh_fetch(endpoint: str) -> Any:
        command = ["gh", "api", "-H", "Accept: application/vnd.github+json", endpoint]
        try:
            result = subprocess.run(command, text=True, capture_output=True, check=False)
        except FileNotFoundError as exc:
            raise GitHubAPIError("GitHub CLI (gh) is not installed. Install it and run 'gh auth login'.") from exc
        if result.returncode:
            detail = (result.stderr or result.stdout or "GitHub API request failed").strip().splitlines()[-1]
            raise GitHubAPIError(f"GitHub API request failed for {endpoint}: {detail}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubAPIError(f"GitHub API returned invalid JSON for {endpoint}.") from exc

    def get(self, endpoint: str) -> Any:
        return self.fetch(endpoint)


def fetch_repo_report(
    client: GitHubClient,
    repo: str,
    lookback_days: int,
    stale_issue_days: int = 120,
    max_closed_pull_requests: int = 100,
    max_candidates_per_repository: int = 10,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    metadata = client.get(f"/repos/{repo}")
    limitations = [
        "This report does not inspect every discussion, PR timeline, CLA/DCO rule, or maintainer capacity.",
        "A human must read current CONTRIBUTING guidance and confirm an issue is unclaimed before acting.",
    ]
    evidence_errors: dict[str, list[str]] = {}
    try:
        community = client.get(f"/repos/{repo}/community/profile")
    except (GitHubAPIError, KeyError) as exc:
        community = None
        limitations.append("The community profile endpoint was unavailable; process signals are unknown.")
        evidence_errors.setdefault("community_profile", []).append(str(exc))
    try:
        raw_prs = client.get(
            f"/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page={max_closed_pull_requests}"
        )
    except (GitHubAPIError, KeyError) as exc:
        raw_prs = []
        limitations.append("The recent pull-request sample was unavailable; historical openness is unknown.")
        evidence_errors.setdefault("pull_requests", []).append(str(exc))
    cutoff = now - dt.timedelta(days=lookback_days)
    prs = [p for p in raw_prs if (parse_github_time(p.get("closed_at")) or now) >= cutoff]
    issues: dict[int, dict[str, Any]] = {}
    for label in ("good first issue", "good-first-issue", "help wanted", "help-wanted"):
        endpoint = f"/repos/{repo}/issues?state=open&labels={label.replace(' ', '%20')}&sort=updated&direction=desc&per_page=100"
        try:
            label_issues = client.get(endpoint)
        except (GitHubAPIError, KeyError) as exc:
            evidence_errors.setdefault("issue_queries", []).append(f"{label}: {exc}")
            continue
        for issue in label_issues:
            if not issue.get("pull_request"):
                issues[int(issue["number"])] = issue
    if evidence_errors.get("issue_queries"):
        limitations.append("One or more friendly-label issue queries failed; candidate inventory is incomplete.")
    candidates = [score_issue(issue, now, stale_issue_days) for issue in issues.values()]
    candidates.sort(key=lambda item: (-item["candidate_score"], item["issue_number"] or 0))
    candidates = candidates[:max_candidates_per_repository]
    eligible = [item for item in candidates if item["eligible_for_human_review"]]
    score = score_repository(
        prs,
        community,
        len(eligible),
        pushed_at=metadata.get("pushed_at"),
        now=now,
        archived=bool(metadata.get("archived")),
    )
    return {"repository": repo, "repository_url": metadata.get("html_url", f"https://github.com/{repo}"), "description": metadata.get("description"), "default_branch": metadata.get("default_branch"), "archived": bool(metadata.get("archived")), "pushed_at": metadata.get("pushed_at"), "score": score, "candidates": candidates, "evidence_errors": evidence_errors, "limitations": limitations, "scanned_at": now.isoformat()}


def markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Contribution opportunity scan", "", f"Scanned: `{report['scanned_at']}`", "", "This is a read-only evidence report. Scores are **not** acceptance probabilities.", "", "| Repository | Friendliness | Confidence | Eligible issues |", "| --- | ---: | ---: | ---: |"]
    for item in report["repositories"]:
        score = item["score"]
        lines.append(f"| [{item['repository']}]({item['repository_url']}) | {score['contribution_friendliness_score']}/100 | {score['evidence_confidence']}/100 | {score['samples']['open_candidate_issues']} |")
    for item in report["repositories"]:
        lines += ["", f"## {item['repository']}", "", f"{item.get('description') or 'No repository description available.'}", "", f"Score band: **{item['score']['score_band']}**. Recent merged PR sample: {item['score']['samples']['merged_prs_examined']}; non-member-associated merges: {item['score']['samples']['non_member_associated_merged_prs']} (affiliation not established).", ""]
        eligible = [c for c in item["candidates"] if c["eligible_for_human_review"]]
        if eligible:
            lines += ["Potential issues requiring human validation:", ""]
            for candidate in eligible[:10]:
                lines.append(f"- [#{candidate['issue_number']} {candidate['title']}]({candidate['url']}) — candidate score {candidate['candidate_score']}/100.")
        else:
            lines.append("No currently eligible candidate surfaced from the friendly-label queries.")
    if report.get("errors"):
        lines += ["", "## Scan errors", ""]
        for error in report["errors"]:
            lines.append(f"- `{error['repository']}`: {error['error']}")
    lines += ["", "## Limitations", "", "- Do not claim an issue or open a PR based on this report alone.", "- Recheck the issue, contribution guide, CLA/DCO, and maintainer requests immediately before starting work."]
    return "\n".join(lines) + "\n"


def load_config(path: Path) -> tuple[list[str], dict[str, int]]:
    data = json.loads(path.read_text())
    repos = data.get("repositories", data) if isinstance(data, dict) else data
    names = [entry["repo"] if isinstance(entry, dict) else entry for entry in repos]
    if not all(isinstance(name, str) and "/" in name for name in names):
        raise ValueError("config repositories must be owner/name strings or objects with a repo field")
    configured_defaults = data.get("defaults", {}) if isinstance(data, dict) else {}
    defaults = {
        "lookback_days": int(configured_defaults.get("lookback_days", 180)),
        "stale_issue_days": int(configured_defaults.get("stale_issue_days", 120)),
        "max_closed_pull_requests": int(configured_defaults.get("max_closed_pull_requests", 100)),
        "max_candidates_per_repository": int(configured_defaults.get("max_candidates_per_repository", 10)),
    }
    return names, defaults


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/repositories.json"))
    parser.add_argument("--repos", help="Comma-separated owner/repo subset")
    parser.add_argument("--lookback-days", type=int)
    parser.add_argument("--stale-issue-days", type=int)
    parser.add_argument("--max-closed-pull-requests", type=int)
    parser.add_argument("--max-candidates-per-repository", type=int)
    parser.add_argument("--output-dir", type=Path, default=Path("runtime/scans"))
    parser.add_argument("--offline-fixtures", type=Path, help="JSON mapping of GitHub API endpoint to response, for deterministic offline runs")
    args = parser.parse_args(argv)
    configured_repos, defaults = load_config(args.config)
    args.lookback_days = defaults["lookback_days"] if args.lookback_days is None else args.lookback_days
    args.stale_issue_days = defaults["stale_issue_days"] if args.stale_issue_days is None else args.stale_issue_days
    args.max_closed_pull_requests = defaults["max_closed_pull_requests"] if args.max_closed_pull_requests is None else args.max_closed_pull_requests
    args.max_candidates_per_repository = defaults["max_candidates_per_repository"] if args.max_candidates_per_repository is None else args.max_candidates_per_repository
    for option_name in (
        "lookback_days",
        "stale_issue_days",
        "max_closed_pull_requests",
        "max_candidates_per_repository",
    ):
        if getattr(args, option_name) < 1:
            parser.error(f"--{option_name.replace('_', '-')} must be positive")
    if args.max_closed_pull_requests > 100:
        parser.error("--max-closed-pull-requests cannot exceed GitHub's per-page limit of 100")
    repos = [x.strip() for x in args.repos.split(",") if x.strip()] if args.repos else configured_repos
    fixtures: dict[str, Any] | None = None
    if args.offline_fixtures:
        fixtures = json.loads(args.offline_fixtures.read_text())
        client = GitHubClient(lambda endpoint: fixtures[endpoint])
    else:
        client = GitHubClient()
    results = []
    errors = []
    for repo in repos:
        try:
            results.append(
                fetch_repo_report(
                    client,
                    repo,
                    args.lookback_days,
                    stale_issue_days=args.stale_issue_days,
                    max_closed_pull_requests=args.max_closed_pull_requests,
                    max_candidates_per_repository=args.max_candidates_per_repository,
                )
            )
        except (GitHubAPIError, KeyError, ValueError) as exc:
            errors.append({"repository": repo, "error": str(exc)})
            print(f"scanner warning for {repo}: {exc}", file=sys.stderr)
    report = {"schema_version": 1, "scanned_at": utcnow().isoformat(), "settings": {"lookback_days": args.lookback_days, "stale_issue_days": args.stale_issue_days, "max_closed_pull_requests": args.max_closed_pull_requests, "max_candidates_per_repository": args.max_candidates_per_repository}, "repositories": results, "errors": errors, "disclaimer": "Friendliness scores are not acceptance probabilities. GitHub author association does not establish affiliation. This scanner makes no account or repository changes."}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "report.md").write_text(markdown_report(report))
    print(f"wrote {args.output_dir / 'report.json'} and {args.output_dir / 'report.md'}")
    return 0 if results else 2


if __name__ == "__main__":
    raise SystemExit(main())
