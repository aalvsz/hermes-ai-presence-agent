import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).parents[1] / "tools" / "github_scout.py"
SPEC = importlib.util.spec_from_file_location("github_scout", MODULE)
scout = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(scout)


def pr(number, association="NONE", merged=True, user_type="User"):
    return {"number": number, "merged_at": "2026-08-01T00:00:00Z" if merged else None, "closed_at": "2026-08-01T00:00:00Z", "author_association": association, "user": {"login": f"user{number}", "type": user_type}}


class GitHubScoutTests(unittest.TestCase):
    def test_bot_filtering_does_not_count_as_non_member_evidence(self):
        bot = pr(1, "NONE", user_type="Bot")
        human = pr(2, "FIRST_TIME_CONTRIBUTOR")
        result = scout.score_repository([bot, human], {"files": {"contributing": "CONTRIBUTING.md", "license": "LICENSE"}}, 1)
        self.assertEqual(result["samples"]["merged_prs_examined"], 1)
        self.assertEqual(result["samples"]["non_member_associated_merged_prs"], 1)
        self.assertEqual(result["non_member_association_counts"], {"FIRST_TIME_CONTRIBUTOR": 1})

    def test_issue_gates_assigned_stale_and_linked_work(self):
        issue = {"number": 7, "title": "Help wanted", "body": "Already fixed in linked pull request", "labels": [{"name": "good first issue"}], "assignees": [{"login": "someone"}], "updated_at": "2025-01-01T00:00:00Z", "user": {"login": "human", "type": "User"}}
        result = scout.score_issue(issue, scout.dt.datetime(2026, 8, 18, tzinfo=scout.dt.timezone.utc))
        self.assertFalse(result["eligible_for_human_review"])
        self.assertEqual(result["candidate_score"], 0)
        self.assertGreaterEqual(len(result["gates"]), 3)

    def test_repository_score_has_declared_components_and_archive_gate(self):
        pull_requests = [pr(number, "FIRST_TIME_CONTRIBUTOR") for number in range(10)]
        community = {"files": {key: f"{key}.md" for key in scout.PROCESS_FILES}}
        now = scout.dt.datetime(2026, 8, 18, tzinfo=scout.dt.timezone.utc)
        result = scout.score_repository(
            pull_requests,
            community,
            3,
            pushed_at="2026-08-17T00:00:00Z",
            now=now,
        )
        self.assertEqual(result["contribution_friendliness_score"], 100)
        self.assertEqual(sum(result["score_components"].values()), 100)
        archived = scout.score_repository(
            pull_requests,
            community,
            3,
            pushed_at="2026-08-17T00:00:00Z",
            now=now,
            archived=True,
        )
        self.assertEqual(archived["contribution_friendliness_score"], 0)
        self.assertEqual(archived["score_band"], "archived")

    def test_tracking_issue_is_demoted_and_requires_timeline_validation(self):
        issue = {
            "number": 9,
            "title": "Tracking issue for all backend work",
            "body": "Tests are welcome.",
            "labels": [{"name": "help wanted"}],
            "assignees": [],
            "updated_at": "2026-08-17T00:00:00Z",
            "user": {"login": "human", "type": "User"},
        }
        result = scout.score_issue(
            issue,
            scout.dt.datetime(2026, 8, 18, tzinfo=scout.dt.timezone.utc),
        )
        self.assertTrue(result["eligible_for_human_review"])
        self.assertLess(result["candidate_score"], 80)
        self.assertIn("tracking issue", result["scope_warnings"])
        self.assertTrue(result["requires_timeline_validation"])

    def test_per_evidence_failure_preserves_repository_report(self):
        repo = "org/repo"

        def fetch(endpoint):
            if endpoint == f"/repos/{repo}":
                return {"html_url": f"https://github.com/{repo}", "default_branch": "main"}
            if "/community/profile" in endpoint or "/pulls?" in endpoint:
                raise scout.GitHubAPIError("fixture endpoint unavailable")
            if "labels=good%20first%20issue" in endpoint:
                return [{"number": 3, "title": "Small docs fix", "body": "add a test", "labels": [{"name": "good first issue"}], "updated_at": "2026-08-17T00:00:00Z", "html_url": f"https://github.com/{repo}/issues/3", "user": {"login": "human", "type": "User"}}]
            if "labels=help%20wanted" in endpoint:
                raise scout.GitHubAPIError("one label query unavailable")
            return []

        report = scout.fetch_repo_report(
            scout.GitHubClient(fetch),
            repo,
            180,
            now=scout.dt.datetime(2026, 8, 18, tzinfo=scout.dt.timezone.utc),
        )
        self.assertEqual(report["repository"], repo)
        self.assertEqual(len(report["candidates"]), 1)
        self.assertIn("community_profile", report["evidence_errors"])
        self.assertIn("pull_requests", report["evidence_errors"])
        self.assertIn("issue_queries", report["evidence_errors"])

    def test_cli_offline_fixtures_write_both_reports(self):
        repo = "org/repo"
        fixtures = {
            f"/repos/{repo}": {"html_url": "https://github.com/org/repo", "description": "test", "default_branch": "main"},
            f"/repos/{repo}/community/profile": {"files": {"contributing": "CONTRIBUTING.md", "license": "LICENSE", "issue_template": "ISSUE.md"}},
            f"/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=5": [pr(1, "FIRST_TIMER")],
            f"/repos/{repo}/issues?state=open&labels=good%20first%20issue&sort=updated&direction=desc&per_page=100": [{"number": 2, "title": "Docs test", "body": "add test", "labels": [{"name": "good first issue"}], "updated_at": "2026-08-10T00:00:00Z", "html_url": "https://github.com/org/repo/issues/2", "user": {"login": "human", "type": "User"}}],
            f"/repos/{repo}/issues?state=open&labels=good-first-issue&sort=updated&direction=desc&per_page=100": [],
            f"/repos/{repo}/issues?state=open&labels=help%20wanted&sort=updated&direction=desc&per_page=100": [],
            f"/repos/{repo}/issues?state=open&labels=help-wanted&sort=updated&direction=desc&per_page=100": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "repos.json"
            offline = root / "fixtures.json"
            output = root / "out"
            config.write_text(json.dumps({"defaults": {"lookback_days": 90, "stale_issue_days": 30, "max_closed_pull_requests": 5, "max_candidates_per_repository": 2}, "repositories": [repo]}))
            offline.write_text(json.dumps(fixtures))
            self.assertEqual(scout.main(["--config", str(config), "--offline-fixtures", str(offline), "--output-dir", str(output)]), 0)
            self.assertTrue((output / "report.json").exists())
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["settings"]["lookback_days"], 90)
            self.assertEqual(report["settings"]["stale_issue_days"], 30)
            self.assertEqual(report["settings"]["max_closed_pull_requests"], 5)
            self.assertEqual(report["settings"]["max_candidates_per_repository"], 2)
            markdown = (output / "report.md").read_text()
            self.assertIn("acceptance probabilities", markdown)
            self.assertIn("#2 Docs test", markdown)


if __name__ == "__main__":
    unittest.main()
