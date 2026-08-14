import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "paper_lab.py"


def run(tmp_path, *args):
    env = os.environ.copy()
    env["HERMES_PRESENCE_RUNTIME"] = str(tmp_path)
    return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, env=env)


def test_initializes_a_non_publishing_scaffold(tmp_path):
    result = run(
        tmp_path,
        "init",
        "--slug", "bounded-paper",
        "--title", "A bounded paper",
        "--paper-url", "https://arxiv.org/abs/2608.00001",
        "--claim", "Match one reported unit-test invariant",
        "--metric", "all invariant fixtures pass",
    )
    assert result.returncode == 0, result.stderr
    lab = Path(json.loads(result.stdout)["path"])
    status = json.loads((lab / "STATUS.json").read_text())
    publication = json.loads((lab / "publication-manifest.json").read_text())
    assert status["level"] == "scaffolded"
    assert status["evidence"] == []
    assert publication["enabled"] is False


def test_refuses_to_overwrite_an_existing_lab(tmp_path):
    args = (
        "init", "--slug", "bounded-paper", "--title", "A bounded paper",
        "--paper-url", "https://arxiv.org/abs/2608.00001",
    )
    assert run(tmp_path, *args).returncode == 0
    second = run(tmp_path, *args)
    assert second.returncode == 2
    assert "already exists" in second.stderr
