import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from dev_inventory import build_report, sanitize_remote


class DevInventoryTests(unittest.TestCase):
    def test_sanitize_remote_drops_credentials_and_git_suffix(self):
        self.assertEqual(sanitize_remote("https://alice:secret@github.com/example/project.git"), "github.com/example/project")

    def test_inventory_empty_root_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build_report(Path(directory))
        self.assertEqual(report["repositories"], [])


if __name__ == "__main__":
    unittest.main()
