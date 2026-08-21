import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from work_queue_scan import ProviderError, build_report, normalize_github, normalize_gitlab


class WorkQueueScanTests(unittest.TestCase):
    def test_normalize_github_issue_and_pull_request(self):
        issue = normalize_github(
            {
                "number": 4,
                "title": "Fix it",
                "html_url": "https://github.com/a/b/issues/4",
                "updated_at": "2026-08-21T10:00:00Z",
                "labels": [{"name": "bug"}],
                "repository": {"full_name": "a/b"},
            }
        )
        self.assertEqual(issue["kind"], "issue")
        self.assertEqual(issue["repository"], "a/b")
        pull = normalize_github({"number": 5, "pull_request": {}, "repository": {"full_name": "a/b"}})
        self.assertEqual(pull["kind"], "pull_request")

    def test_normalize_gitlab_merge_request(self):
        item = normalize_gitlab(
            {
                "iid": 9,
                "title": "Improve tests",
                "web_url": "https://gitlab.example/group/project/-/merge_requests/9",
                "references": {"full": "group/project!9"},
                "labels": ["ready"],
            },
            "merge_request",
        )
        self.assertEqual(item["repository"], "group/project!9")
        self.assertEqual(item["kind"], "merge_request")

    def test_build_report_preserves_partial_provider_failure(self):
        calls = []

        def runner(command):
            calls.append(command)
            if command[0] == "gh":
                return {"items": [{"number": 1, "title": "Issue", "repository": {"full_name": "a/b"}}]}
            raise ProviderError("GitLab unavailable")

        report = build_report(runner)
        self.assertEqual(len(report["items"]), 1)
        self.assertIn("gitlab", report["errors"])
        self.assertEqual(len(report["items"]), 1)


if __name__ == "__main__":
    unittest.main()
